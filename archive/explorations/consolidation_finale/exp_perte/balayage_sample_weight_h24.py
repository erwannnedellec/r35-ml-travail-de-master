"""
CHANTIER PERTE — Phase 1 : balayage sample_weight sur la zone >63
==================================================================
EXPÉRIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI aux modèles
canoniques (enrichi_seg_*_416bb90b.json). Aucune écriture dans le rapport.
Aucun modèle sauvegardé. Diagnostic + balayage UNIQUEMENT.

Question
--------
Le modèle canonique (XGBoost MSE reg:squarederror) sous-prédit en zone >63
(biais global −28,5 sur H25). Pondérer les obs >63 à l'entraînement
(sample_weight) réduit-il ce biais, et SURTOUT cela touche-t-il à la
séparabilité (PR-AUC) ou seulement au point de fonctionnement ?

Protocole de VALIDATION (strict)
--------------------------------
  train      = H22 (tronçons Gilamont 8501260 exclus, ADR-CF21) + H23
  validation = H24
  H25        = JAMAIS chargé / JAMAIS touché pour le choix du poids.

  Poids binaire : w = 1 si charge ≤ 63, w = W si charge > 63.
  W appliqué sur le label réel target_voyageurs_2eme_classe à l'entraînement.
  Grille W ∈ {1, 2, 3, 5, 10, 20}  (W=1 = contrôle = MSE non pondéré).

  Iso-tout sauf le poids : mêmes 158 features, mêmes hyperparamètres
  (ADR-CF09), même seed=42, même segmentation BAS/HAUT. Seul sample_weight varie.

Métriques tabulées (par segment BAS/HAUT + GLOBAL, pour chaque W)
----------------------------------------------------------------
  bias_gt63     : mean(pred − obs) sur obs réellement > 63
  mae_gt63      : MAE sur obs > 63
  mae_global    : MAE sur toute la masse (coût)
  r2_global     : R² global
  pr_auc_troncon: average_precision(label = obs>63, score = pred)
  pr_auc_tour   : idem au grain tour ; clé tour = (base_date, horaire_numero_train),
                  score = max pred / tour, label = max obs/tour > 63
"""

import json, hashlib, time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_perte"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"

HASH_ATTENDU   = "416bb90b"   # vérification intégrité dataset (lecture seule)
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
TARGET         = "target_voyageurs_2eme_classe"
GRILLE_W       = [1, 2, 3, 5, 10, 20]

# ADR-CF09 — iso hyperparamètres canoniques
XGB_PARAMS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    objective="reg:squarederror", tree_method="hist",
    random_state=SEED, enable_categorical=True, verbosity=0,
)

print("=" * 76)
print("CHANTIER PERTE — Phase 1 : balayage sample_weight zone >63 (VALIDATION H24)")
print("=" * 76)

# ── 0. Dataset (lecture seule + check intégrité) ─────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash attendu {HASH_ATTENDU}, obtenu {file_hash}"
print(f"\n── 0. Dataset ──\n  Hash SHA256[:8] = {file_hash} ✓ (intègre, lecture seule)")

df = pd.read_parquet(PARQUET)
with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158, f"Attendu 158 features, obtenu {len(FEATS)}"
print(f"  {len(df):,} lignes × {len(df.columns)} cols  |  {len(FEATS)} features ✓")

# ── 1. Split VALIDATION : train H22(no Gil)+H23 ; valid H24. H25 jeté. ───────
print("\n── 1. Split VALIDATION (H25 jamais chargé) ──")
h22_all  = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = (
    (h22_all["id_gare_depart_bpuic"].astype("int64")  == GILAMONT_BPUIC) |
    (h22_all["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC)
)
h22_valid = h22_all[~mask_gil].copy()
h23       = df[df["horaire_annee_horaire"] == "H23"].copy()
train     = pd.concat([h22_valid, h23], ignore_index=True)
valid     = df[df["horaire_annee_horaire"] == "H24"].copy()   # H24 = validation
del df  # libère H25 + reste : non utilisé pour le choix du poids

n_gil = int(mask_gil.sum())
print(f"  H22 total={len(h22_all):,}  Gilamont exclus={n_gil:,} ({n_gil/len(h22_all):.1%})")
print(f"  TRAIN (H22_valid + H23) = {len(train):,}")
print(f"  VALID (H24)             = {len(valid):,}")

# ── prep_X iso-canonique (q_all_v18) ─────────────────────────────────────────
def prep_X(d: pd.DataFrame, feats=FEATS) -> pd.DataFrame:
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X

mask_b_tr = (train["spatial_segment"] == "bas").values
mask_h_tr = (train["spatial_segment"] == "haut").values
mask_b_va = (valid["spatial_segment"] == "bas").values
mask_h_va = (valid["spatial_segment"] == "haut").values

X_tr_b, X_tr_h = prep_X(train[mask_b_tr]), prep_X(train[mask_h_tr])
X_va_b, X_va_h = prep_X(valid[mask_b_va]), prep_X(valid[mask_h_va])
y_tr_b = train.loc[mask_b_tr, TARGET].values.astype("float64")
y_tr_h = train.loc[mask_h_tr, TARGET].values.astype("float64")
y_va_b = valid.loc[mask_b_va, TARGET].values.astype("float64")
y_va_h = valid.loc[mask_h_va, TARGET].values.astype("float64")
y_va_g = valid[TARGET].values.astype("float64")

print(f"  TRAIN  BAS={mask_b_tr.sum():,}  HAUT={mask_h_tr.sum():,}")
print(f"  VALID  BAS={mask_b_va.sum():,}  HAUT={mask_h_va.sum():,}")
print(f"  VALID surcharges >63 : BAS={int((y_va_b>SEUIL).sum())}  "
      f"HAUT={int((y_va_h>SEUIL).sum())}  GLOBAL={int((y_va_g>SEUIL).sum())}")

# tour key sur VALID (pour PR-AUC tour)
tour_key_b = list(zip(valid.loc[mask_b_va, "base_date"], valid.loc[mask_b_va, "horaire_numero_train"]))
tour_key_h = list(zip(valid.loc[mask_h_va, "base_date"], valid.loc[mask_h_va, "horaire_numero_train"]))
tour_key_g = list(zip(valid["base_date"], valid["horaire_numero_train"]))

def pr_auc_troncon(y_true, y_pred, seuil=SEUIL):
    y_bin = (y_true > seuil).astype(int)
    return float(average_precision_score(y_bin, y_pred)) if y_bin.sum() > 0 else None

def pr_auc_tour(tour_keys, y_true, y_pred, seuil=SEUIL):
    g = pd.DataFrame({"k": tour_keys, "obs": y_true, "pred": y_pred})
    agg = g.groupby("k").agg(max_obs=("obs", "max"), max_pred=("pred", "max"))
    y_bin = (agg["max_obs"].values > seuil).astype(int)
    if y_bin.sum() == 0:
        return None, len(agg), 0
    return float(average_precision_score(y_bin, agg["max_pred"].values)), len(agg), int(y_bin.sum())

def metrics_block(y_true, y_pred, tour_keys):
    mask_z = y_true > SEUIL
    n_z = int(mask_z.sum())
    res_z = y_pred[mask_z] - y_true[mask_z]
    pa_tr = pr_auc_troncon(y_true, y_pred)
    pa_to, n_tours, n_tours_pos = pr_auc_tour(tour_keys, y_true, y_pred)
    return {
        "n_obs":        int(len(y_true)),
        "n_gt63":       n_z,
        "bias_gt63":    float(res_z.mean())          if n_z else None,
        "mae_gt63":     float(np.abs(res_z).mean())  if n_z else None,
        "mae_global":   float(mean_absolute_error(y_true, y_pred)),
        "r2_global":    float(r2_score(y_true, y_pred)),
        "pr_auc_troncon": pa_tr,
        "pr_auc_tour":  pa_to,
        "n_tours":      n_tours,
        "n_tours_gt63": n_tours_pos,
    }

# ── 2. Balayage W ────────────────────────────────────────────────────────────
print("\n── 2. Balayage W ∈ {1,2,3,5,10,20} ──")
rows = []
for W in GRILLE_W:
    t0 = time.time()
    w_tr_b = np.where(y_tr_b > SEUIL, float(W), 1.0)
    w_tr_h = np.where(y_tr_h > SEUIL, float(W), 1.0)

    mb = xgb.XGBRegressor(**XGB_PARAMS); mb.fit(X_tr_b, y_tr_b, sample_weight=w_tr_b)
    mh = xgb.XGBRegressor(**XGB_PARAMS); mh.fit(X_tr_h, y_tr_h, sample_weight=w_tr_h)

    yp_b = mb.predict(X_va_b).astype("float64")
    yp_h = mh.predict(X_va_h).astype("float64")
    yp_g = np.empty(len(valid))
    yp_g[mask_b_va] = yp_b
    yp_g[mask_h_va] = yp_h

    m_b = metrics_block(y_va_b, yp_b, tour_key_b)
    m_h = metrics_block(y_va_h, yp_h, tour_key_h)
    m_g = metrics_block(y_va_g, yp_g, tour_key_g)
    for seg, m in [("bas", m_b), ("haut", m_h), ("global", m_g)]:
        rows.append({"W": W, "segment": seg, **m})
    print(f"  W={W:>2}  ({time.time()-t0:>4.0f}s)  "
          f"GLOB biais>63={m_g['bias_gt63']:+7.2f}  MAE>63={m_g['mae_gt63']:6.2f}  "
          f"MAEglob={m_g['mae_global']:5.3f}  R²={m_g['r2_global']:.4f}  "
          f"PRAUC_tr={m_g['pr_auc_troncon']:.4f}  PRAUC_tour={m_g['pr_auc_tour']:.4f}")

res = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
res.to_csv(OUT / "balayage_sample_weight_h24.csv", index=False)
(OUT / "balayage_sample_weight_h24.json").write_text(
    json.dumps({
        "experiment": "CHANTIER PERTE Phase 1 — balayage sample_weight zone >63",
        "statut": "EXPÉRIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact",
        "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; H25 jamais touché",
        "dataset_hash": HASH_ATTENDU, "n_features": len(FEATS), "seuil": SEUIL, "seed": SEED,
        "grille_W": GRILLE_W, "hyperparams": "ADR-CF09",
        "poids": "w=1 si charge<=63, w=W si charge>63 (label réel)",
        "n_train": int(len(train)), "n_valid_h24": int(len(valid)),
        "resultats": rows,
    }, indent=2, ensure_ascii=False))

# ── 3. Tables de compromis (par segment) ─────────────────────────────────────
def print_table(seg):
    sub = res[res["segment"] == seg].sort_values("W")
    print(f"\n{'─'*76}\nTABLE — segment {seg.upper()}   (validation H24)\n{'─'*76}")
    print(f"{'W':>3} | {'biais>63':>9} | {'MAE>63':>7} | {'MAEglob':>8} | "
          f"{'R²glob':>7} | {'PRAUC_tron':>10} | {'PRAUC_tour':>10}")
    print("-" * 76)
    base = sub[sub["W"] == 1].iloc[0]
    for _, r in sub.iterrows():
        d_tr = r["pr_auc_troncon"] - base["pr_auc_troncon"]
        d_to = r["pr_auc_tour"]    - base["pr_auc_tour"]
        print(f"{int(r['W']):>3} | {r['bias_gt63']:>+9.2f} | {r['mae_gt63']:>7.2f} | "
              f"{r['mae_global']:>8.3f} | {r['r2_global']:>7.4f} | "
              f"{r['pr_auc_troncon']:>10.4f} | {r['pr_auc_tour']:>10.4f}")
    print(f"    (ΔPR-AUC vs W=1 au W max : tronçon={d_tr:+.4f}, tour={d_to:+.4f})")

for seg in ["bas", "haut", "global"]:
    print_table(seg)

print(f"\n{'='*76}\nFichiers : {OUT/'balayage_sample_weight_h24.csv'}")
print("ARRÊT — aucun W choisi, aucun réentraînement final. Décision conjointe au vu de la courbe.")
print("=" * 76)
