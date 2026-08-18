"""
CHANTIER PERTE — Phase 2 : perte MSE asymétrique (étape A, paramètre unique k)
==============================================================================
EXPÉRIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI aux modèles
canoniques. Aucun modèle sauvegardé. H25 JAMAIS chargé. Rien dans le rapport.

Objectif
--------
Tester si viser un quantile haut (via MSE asymétrique) RELÈVE la PR-AUC
(= gain de séparabilité réel, plafond relevé) ou seulement RECALE le point de
fonctionnement (comme sample_weight Phase 1, qui plafonnait dès W=2).
C'est le test décisif de la faille audit n°1.

Perte MSE asymétrique — définition exacte
-----------------------------------------
  résidu r = pred − obs   (sous-prédiction = r < 0)
  gradient  g = r   si r ≥ 0 ;  g = k·r si r < 0
  hessien   h = 1   si r ≥ 0 ;  h = k   si r < 0   (constant par morceau, > 0)
  Optimum visé : quantile τ = k/(k+1).
    k=1→médiane(0.5) k=2→0.67 k=3→0.75 k=5→0.83 k=9→0.9 k=19→0.95

GARDE-FOU (exécuté EN PREMIER) : k=1 custom DOIT reproduire reg:squarederror
natif à l'identique (allclose). Sinon ARRÊT.

Protocole (identique Phase 1)
-----------------------------
  train      = H22 (Gilamont 8501260 exclu) + H23
  validation = H24   ;   H25 jamais chargé
  Grille k ∈ {1, 2, 3, 5, 9, 19}. Balayage PAR SEGMENT (BAS/HAUT).
  Iso-tout sauf la perte : 158 features, ADR-CF09, seed=42, segmentation.
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

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
TARGET         = "target_voyageurs_2eme_classe"
GRILLE_K       = [1, 2, 3, 5, 9, 19]

# ADR-CF09 — iso hyperparamètres canoniques (objective remplacé par custom)
BASE_PARAMS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", random_state=SEED,
    enable_categorical=True, verbosity=0,
)

def make_obj(k):
    """Objectif custom XGBoost (sklearn API : obj(y_true, y_pred) -> grad, hess)."""
    kf = float(k)
    def obj(y_true, y_pred):
        r = y_pred - y_true               # résidu = pred − obs
        neg = r < 0                        # sous-prédiction
        grad = np.where(neg, kf * r, r)
        hess = np.where(neg, kf, 1.0)
        return grad, hess
    return obj

print("=" * 78)
print("CHANTIER PERTE — Phase 2 : MSE asymétrique, balayage k (VALIDATION H24)")
print("=" * 78)

# ── 0. Dataset (lecture seule + intégrité) ──────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash attendu {HASH_ATTENDU}, obtenu {file_hash}"
print(f"\n── 0. Dataset ──  Hash SHA256[:8] = {file_hash} ✓ (lecture seule)")

df = pd.read_parquet(PARQUET)
with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158
print(f"  {len(df):,} lignes  |  {len(FEATS)} features ✓")

# ── 1. Split VALIDATION (H25 jeté) ──────────────────────────────────────────
h22_all  = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = (
    (h22_all["id_gare_depart_bpuic"].astype("int64")  == GILAMONT_BPUIC) |
    (h22_all["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC)
)
train = pd.concat([h22_all[~mask_gil].copy(),
                   df[df["horaire_annee_horaire"] == "H23"].copy()], ignore_index=True)
valid = df[df["horaire_annee_horaire"] == "H24"].copy()
del df

def prep_X(d, feats=FEATS):
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

X_tr = {"bas": prep_X(train[mask_b_tr]), "haut": prep_X(train[mask_h_tr])}
X_va = {"bas": prep_X(valid[mask_b_va]), "haut": prep_X(valid[mask_h_va])}
y_tr = {"bas": train.loc[mask_b_tr, TARGET].values.astype("float64"),
        "haut": train.loc[mask_h_tr, TARGET].values.astype("float64")}
y_va = {"bas": valid.loc[mask_b_va, TARGET].values.astype("float64"),
        "haut": valid.loc[mask_h_va, TARGET].values.astype("float64")}
y_va_g = valid[TARGET].values.astype("float64")
# base_score = moyenne train du segment (fixée sur custom ET natif → contrôle exact)
BASE_SCORE = {seg: float(y_tr[seg].mean()) for seg in ("bas", "haut")}

tour_key = {
    "bas":    list(zip(valid.loc[mask_b_va, "base_date"], valid.loc[mask_b_va, "horaire_numero_train"])),
    "haut":   list(zip(valid.loc[mask_h_va, "base_date"], valid.loc[mask_h_va, "horaire_numero_train"])),
    "global": list(zip(valid["base_date"], valid["horaire_numero_train"])),
}
print(f"  TRAIN BAS={mask_b_tr.sum():,} HAUT={mask_h_tr.sum():,}  |  "
      f"VALID BAS={mask_b_va.sum():,} HAUT={mask_h_va.sum():,}")
print(f"  VALID surcharges >63 : BAS={int((y_va['bas']>SEUIL).sum())} "
      f"HAUT={int((y_va['haut']>SEUIL).sum())} GLOBAL={int((y_va_g>SEUIL).sum())}")

# ── 2. GARDE-FOU : k=1 custom == reg:squarederror natif ─────────────────────
print("\n── 2. GARDE-FOU contrôle k=1 (custom vs reg:squarederror natif) ──")
ctrl_ok = True
for seg in ("bas", "haut"):
    m_nat = xgb.XGBRegressor(objective="reg:squarederror",
                             base_score=BASE_SCORE[seg], **BASE_PARAMS)
    m_nat.fit(X_tr[seg], y_tr[seg])
    m_cus = xgb.XGBRegressor(objective=make_obj(1),
                             base_score=BASE_SCORE[seg], **BASE_PARAMS)
    m_cus.fit(X_tr[seg], y_tr[seg])
    p_nat = m_nat.predict(X_va[seg]).astype("float64")
    p_cus = m_cus.predict(X_va[seg]).astype("float64")
    close = np.allclose(p_nat, p_cus, rtol=1e-5, atol=1e-4)
    maxdiff = float(np.abs(p_nat - p_cus).max())
    print(f"  {seg.upper():>4} : allclose={close}  max|Δpred|={maxdiff:.3e}")
    ctrl_ok = ctrl_ok and close

if not ctrl_ok:
    print("\n  ✗ ÉCHEC CONTRÔLE : k=1 custom ne reproduit PAS reg:squarederror.")
    print("    Dérivation/implémentation à corriger. ARRÊT — pas de balayage.")
    raise SystemExit(1)
print("  ✓ Contrôle validé : k=1 custom ≡ reg:squarederror. Balayage autorisé.")

# ── 3. Métriques ────────────────────────────────────────────────────────────
def pr_auc_troncon(yt, yp, seuil=SEUIL):
    yb = (yt > seuil).astype(int)
    return float(average_precision_score(yb, yp)) if yb.sum() else None

def pr_auc_tour(keys, yt, yp, seuil=SEUIL):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp})
    agg = g.groupby("k").agg(mo=("obs", "max"), mp=("pred", "max"))
    yb = (agg["mo"].values > seuil).astype(int)
    if yb.sum() == 0:
        return None
    return float(average_precision_score(yb, agg["mp"].values))

def metrics_block(yt, yp, keys):
    z = yt > SEUIL
    le = ~z
    res = yp - yt
    return {
        "n_obs":        int(len(yt)),
        "n_gt63":       int(z.sum()),
        "bias_gt63":    float(res[z].mean())  if z.sum()  else None,
        "mae_gt63":     float(np.abs(res[z]).mean()) if z.sum() else None,
        "bias_le63":    float(res[le].mean()) if le.sum() else None,
        "mae_global":   float(mean_absolute_error(yt, yp)),
        "r2_global":    float(r2_score(yt, yp)),
        "pr_auc_troncon": pr_auc_troncon(yt, yp),
        "pr_auc_tour":  pr_auc_tour(keys, yt, yp),
    }

# ── 4. Balayage k PAR SEGMENT ───────────────────────────────────────────────
print("\n── 4. Balayage k ∈ {1,2,3,5,9,19} ──")
rows = []
for k in GRILLE_K:
    t0 = time.time()
    preds = {}
    for seg in ("bas", "haut"):
        m = xgb.XGBRegressor(objective=make_obj(k), base_score=BASE_SCORE[seg], **BASE_PARAMS)
        m.fit(X_tr[seg], y_tr[seg])
        preds[seg] = m.predict(X_va[seg]).astype("float64")
    yp_g = np.empty(len(valid))
    yp_g[mask_b_va] = preds["bas"]
    yp_g[mask_h_va] = preds["haut"]

    m_b = metrics_block(y_va["bas"],  preds["bas"],  tour_key["bas"])
    m_h = metrics_block(y_va["haut"], preds["haut"], tour_key["haut"])
    m_g = metrics_block(y_va_g, yp_g, tour_key["global"])
    tau = k / (k + 1)
    for seg, m in [("bas", m_b), ("haut", m_h), ("global", m_g)]:
        rows.append({"k": k, "tau": round(tau, 3), "segment": seg, **m})
    print(f"  k={k:>2} (τ={tau:.2f}) ({time.time()-t0:>4.0f}s)  "
          f"GLOB biais>63={m_g['bias_gt63']:+7.2f} MAE>63={m_g['mae_gt63']:6.2f} "
          f"biais≤63={m_g['bias_le63']:+5.2f} MAEglob={m_g['mae_global']:5.3f} "
          f"R²={m_g['r2_global']:.4f} PRAUC_tr={m_g['pr_auc_troncon']:.4f} "
          f"PRAUC_tour={m_g['pr_auc_tour']:.4f}")

res = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
res.to_csv(OUT / "balayage_mse_asym_h24.csv", index=False)
(OUT / "balayage_mse_asym_h24.json").write_text(json.dumps({
    "experiment": "CHANTIER PERTE Phase 2 — MSE asymétrique, balayage k",
    "statut": "EXPÉRIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact",
    "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; H25 jamais touché",
    "perte": "g=r si r>=0 sinon k*r ; h=1 si r>=0 sinon k ; optimum quantile tau=k/(k+1)",
    "controle_k1": "k=1 custom ≡ reg:squarederror natif (allclose validé)",
    "dataset_hash": HASH_ATTENDU, "n_features": len(FEATS), "seuil": SEUIL, "seed": SEED,
    "grille_k": GRILLE_K, "hyperparams": "ADR-CF09 (objective custom)",
    "n_train": int(len(train)), "n_valid_h24": int(len(valid)),
    "resultats": rows,
}, indent=2, ensure_ascii=False))

# ── 5. Tables de compromis ──────────────────────────────────────────────────
def print_table(seg):
    sub = res[res["segment"] == seg].sort_values("k")
    print(f"\n{'─'*86}\nTABLE — segment {seg.upper()}   (validation H24)\n{'─'*86}")
    print(f"{'k':>3} {'τ':>5} | {'biais>63':>9} | {'MAE>63':>7} | {'biais≤63':>8} | "
          f"{'MAEglob':>8} | {'R²glob':>7} | {'PRAUC_tr':>8} | {'PRAUC_to':>8}")
    print("-" * 86)
    base = sub[sub["k"] == 1].iloc[0]
    for _, r in sub.iterrows():
        print(f"{int(r['k']):>3} {r['tau']:>5.2f} | {r['bias_gt63']:>+9.2f} | {r['mae_gt63']:>7.2f} | "
              f"{r['bias_le63']:>+8.2f} | {r['mae_global']:>8.3f} | {r['r2_global']:>7.4f} | "
              f"{r['pr_auc_troncon']:>8.4f} | {r['pr_auc_tour']:>8.4f}")
    last = sub.iloc[-1]
    print(f"    ΔPR-AUC (k={int(last['k'])} vs k=1) : tronçon={last['pr_auc_troncon']-base['pr_auc_troncon']:+.4f}"
          f"  tour={last['pr_auc_tour']-base['pr_auc_tour']:+.4f}")

for seg in ["bas", "haut", "global"]:
    print_table(seg)

print(f"\n{'='*78}\nFichiers : {OUT/'balayage_mse_asym_h24.csv'}")
print("ARRÊT — aucun k choisi, aucun réentraînement final. Comparer à sample_weight Phase 1.")
print("=" * 78)
