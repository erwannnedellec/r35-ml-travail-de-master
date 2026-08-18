"""
CHANTIER PERTE — Phase 3 : confirmation H25 des candidats k=2 et W=2
====================================================================
EXPÉRIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI au modèle
canonique (chargé en lecture seule). Aucun modèle sauvegardé. RAPPORT de
généralisation UNIQUEMENT — PAS de sélection, PAS d'adoption, rien dans le rapport.

Cadrage
-------
k=2 (MSE asym) et W=2 (sample_weight) ont DÉJÀ été choisis sur la validation H24.
Ce passage H25 rapporte si le gain de validation GÉNÉRALISE au test. Ce n'est PAS
une sélection sur holdout (on ne compare pas k=1/2/3 pour choisir). L'adoption
reste différée à la consolidation finale.

Protocole (iso-canonique sauf le levier de perte)
-------------------------------------------------
  train = H22 (Gilamont 8501260 exclu) + H23 + H24 = 801 282 obs  (Split C canonique)
  test  = H25 = 309 252 obs
  3 modèles, iso-tout (158 feats, ADR-CF09, seed=42, segmentation BAS/HAUT) sauf perte :
    CANONIQUE : reg:squarederror — modèles enrichi_seg_*_416bb90b.json chargés (réf.)
    k=2       : MSE asym (g=r/h=1 si r≥0 ; g=2r/h=2 si r<0)
    W=2       : sample_weight (2 si charge>63 sinon 1), reg:squarederror

Garde-fou
---------
  (A) modèles canoniques chargés → reproduisent les métriques H25 publiées (metadata).
  (B) k=1 custom tri-annuel (base_score=mean) → reproduit le canonique (valide le
      chemin objectif-custom + l'init base_score sur le protocole tri-annuel).
"""

import json, hashlib, time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_perte"
MODEL_DIR = ROOT / "models" / "enrichi_seg"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
TARGET         = "target_voyageurs_2eme_classe"

BASE_PARAMS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", random_state=SEED,
    enable_categorical=True, verbosity=0,
)

# Métriques H25 canoniques publiées (metadata v1.9) — pour garde-fou (A)
CANON_PUBLIE = {
    "bas":    {"r2": 0.5868201570605139, "mae": 8.169355239485666,
               "mae_gt63": 27.202408980766403, "bias_gt63": -26.507214227270467,
               "pr_auc": 0.468682360770091},
    "haut":   {"r2": 0.4333585691963404, "mae": 6.38913175142802,
               "mae_gt63": 42.40157375519708, "bias_gt63": -42.26554917769144,
               "pr_auc": 0.3451901542137515},
    "global": {"r2": 0.6013368502570057, "mae": 7.711681017757034,
               "mae_gt63": 29.09278924069142, "bias_gt63": -28.467140694392942,
               "pr_auc": 0.44897336321162107},
}

def make_obj(k):
    kf = float(k)
    def obj(y_true, y_pred):
        r = y_pred - y_true
        neg = r < 0
        return np.where(neg, kf * r, r), np.where(neg, kf, 1.0)
    return obj

print("=" * 80)
print("CHANTIER PERTE — Phase 3 : confirmation H25 (canonique / k=2 / W=2)")
print("=" * 80)

# ── 0. Dataset ──────────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Dataset ──  Hash {file_hash} ✓ (lecture seule)")
df = pd.read_parquet(PARQUET)
with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158

# ── 1. Split C tri-annuel ───────────────────────────────────────────────────
h22 = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = (
    (h22["id_gare_depart_bpuic"].astype("int64")  == GILAMONT_BPUIC) |
    (h22["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC)
)
train = pd.concat([h22[~mask_gil].copy(),
                   df[df["horaire_annee_horaire"].isin(["H23", "H24"])].copy()],
                  ignore_index=True)
h25 = df[df["horaire_annee_horaire"] == "H25"].copy()
del df
assert len(train) == 801282, f"train {len(train)} != 801282"
assert len(h25)   == 309252, f"H25 {len(h25)} != 309252"
print(f"── 1. Split C ──  train={len(train):,}  test H25={len(h25):,} ✓")

def prep_X(d, feats=FEATS):
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X

mb_tr = (train["spatial_segment"] == "bas").values
mh_tr = (train["spatial_segment"] == "haut").values
mb_te = (h25["spatial_segment"] == "bas").values
mh_te = (h25["spatial_segment"] == "haut").values

X_tr = {"bas": prep_X(train[mb_tr]), "haut": prep_X(train[mh_tr])}
X_te = {"bas": prep_X(h25[mb_te]),   "haut": prep_X(h25[mh_te])}
X_te_g = prep_X(h25)
y_tr = {"bas": train.loc[mb_tr, TARGET].values.astype("float64"),
        "haut": train.loc[mh_tr, TARGET].values.astype("float64")}
y_te = {"bas": h25.loc[mb_te, TARGET].values.astype("float64"),
        "haut": h25.loc[mh_te, TARGET].values.astype("float64")}
y_te_g = h25[TARGET].values.astype("float64")
BASE_SCORE = {seg: float(y_tr[seg].mean()) for seg in ("bas", "haut")}

tkey = {
    "bas":    list(zip(h25.loc[mb_te, "base_date"], h25.loc[mb_te, "horaire_numero_train"])),
    "haut":   list(zip(h25.loc[mh_te, "base_date"], h25.loc[mh_te, "horaire_numero_train"])),
    "global": list(zip(h25["base_date"], h25["horaire_numero_train"])),
}

def pr_auc_tr(yt, yp):
    yb = (yt > SEUIL).astype(int)
    return float(average_precision_score(yb, yp)) if yb.sum() else None

def pr_auc_to(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp})
    agg = g.groupby("k").agg(mo=("obs", "max"), mp=("pred", "max"))
    yb = (agg["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, agg["mp"].values)) if yb.sum() else None

def metrics_block(yt, yp, keys):
    z = yt > SEUIL; le = ~z; res = yp - yt
    return {
        "n_obs": int(len(yt)), "n_gt63": int(z.sum()),
        "r2_global": float(r2_score(yt, yp)),
        "mae_global": float(mean_absolute_error(yt, yp)),
        "bias_gt63": float(res[z].mean()) if z.sum() else None,
        "mae_gt63": float(np.abs(res[z]).mean()) if z.sum() else None,
        "bias_le63": float(res[le].mean()) if le.sum() else None,
        "pr_auc_troncon": pr_auc_tr(yt, yp),
        "pr_auc_tour": pr_auc_to(keys, yt, yp),
    }

def assemble_global(p_bas, p_haut):
    g = np.empty(len(h25)); g[mb_te] = p_bas; g[mh_te] = p_haut; return g

def all_metrics(p_bas, p_haut):
    g = assemble_global(p_bas, p_haut)
    return {"bas": metrics_block(y_te["bas"], p_bas, tkey["bas"]),
            "haut": metrics_block(y_te["haut"], p_haut, tkey["haut"]),
            "global": metrics_block(y_te_g, g, tkey["global"])}

# ── 2. CANONIQUE (modèles chargés, lecture seule) + garde-fou (A) ───────────
print("\n── 2. CANONIQUE — chargement modèles 416bb90b (lecture seule) ──")
def load_canon(name):
    m = xgb.XGBRegressor(); m.load_model(str(MODEL_DIR / name)); return m
mc_b = load_canon("enrichi_seg_bas_416bb90b.json")
mc_h = load_canon("enrichi_seg_haut_416bb90b.json")
pc_b = mc_b.predict(X_te["bas"]).astype("float64")
pc_h = mc_h.predict(X_te["haut"]).astype("float64")
M_CANON = all_metrics(pc_b, pc_h)

print("  Garde-fou (A) — reproduction métriques publiées :")
ga_ok = True
for seg in ("bas", "haut", "global"):
    got, pub = M_CANON[seg], CANON_PUBLIE[seg]
    dr2 = abs(got["r2_global"] - pub["r2"])
    dbi = abs(got["bias_gt63"] - pub["bias_gt63"])
    dpa = abs(got["pr_auc_troncon"] - pub["pr_auc"])
    ok = dr2 < 1e-6 and dbi < 1e-6 and dpa < 1e-6
    ga_ok = ga_ok and ok
    print(f"    {seg:>6}: R²={got['r2_global']:.6f}(Δ{dr2:.1e}) "
          f"biais>63={got['bias_gt63']:+.4f}(Δ{dbi:.1e}) "
          f"PR-AUC={got['pr_auc_troncon']:.6f}(Δ{dpa:.1e}) {'✓' if ok else '✗'}")
print(f"  Garde-fou (A) : {'✓ canonique reproduit' if ga_ok else '✗ ÉCART'}")

# ── 3. Garde-fou (B) : k=1 custom tri-annuel ≈ canonique ────────────────────
print("\n── 3. Garde-fou (B) — k=1 custom tri-annuel vs canonique ──")
for seg, pc in [("bas", pc_b), ("haut", pc_h)]:
    m1 = xgb.XGBRegressor(objective=make_obj(1), base_score=BASE_SCORE[seg], **BASE_PARAMS)
    m1.fit(X_tr[seg], y_tr[seg])
    p1 = m1.predict(X_te[seg]).astype("float64")
    r2_1 = r2_score(y_te[seg], p1)
    print(f"    {seg:>4}: k1 R²={r2_1:.6f}  canon R²={M_CANON[seg]['r2_global']:.6f}  "
          f"Δ={abs(r2_1-M_CANON[seg]['r2_global']):.2e}  max|Δpred vs canon|={np.abs(p1-pc).max():.3e}")

# ── 4. k=2 (MSE asym) tri-annuel ────────────────────────────────────────────
print("\n── 4. k=2 (MSE asym) tri-annuel ──")
t0 = time.time(); pk = {}
for seg in ("bas", "haut"):
    m = xgb.XGBRegressor(objective=make_obj(2), base_score=BASE_SCORE[seg], **BASE_PARAMS)
    m.fit(X_tr[seg], y_tr[seg]); pk[seg] = m.predict(X_te[seg]).astype("float64")
M_K2 = all_metrics(pk["bas"], pk["haut"])
print(f"  fait en {time.time()-t0:.0f}s")

# ── 5. W=2 (sample_weight) tri-annuel, reg:squarederror ─────────────────────
print("── 5. W=2 (sample_weight) tri-annuel ──")
t0 = time.time(); pw = {}
for seg in ("bas", "haut"):
    w = np.where(y_tr[seg] > SEUIL, 2.0, 1.0)
    m = xgb.XGBRegressor(objective="reg:squarederror", **BASE_PARAMS)
    m.fit(X_tr[seg], y_tr[seg], sample_weight=w); pw[seg] = m.predict(X_te[seg]).astype("float64")
M_W2 = all_metrics(pw["bas"], pw["haut"])
print(f"  fait en {time.time()-t0:.0f}s")

# ── 6. Sauvegarde + tables ──────────────────────────────────────────────────
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "confirmation_h25_k2_w2.json").write_text(json.dumps({
    "experiment": "CHANTIER PERTE Phase 3 — confirmation H25 k=2 / W=2",
    "statut": "EXPÉRIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact, rien adopté",
    "protocole": "train Split C tri-annuel H22(Gil exclu)+H23+H24 → test H25 ; iso sauf perte",
    "garde_fou_A_canonique_reproduit": bool(ga_ok),
    "dataset_hash": HASH_ATTENDU, "n_features": len(FEATS), "seuil": SEUIL, "seed": SEED,
    "metrics_h25": {"canonique": M_CANON, "k2_mse_asym": M_K2, "w2_sample_weight": M_W2},
}, indent=2, ensure_ascii=False))

LABELS = [("canonique", M_CANON), ("k=2 asym", M_K2), ("W=2 sw", M_W2)]
def table(seg):
    print(f"\n{'─'*92}\nTABLE H25 — segment {seg.upper()}  (n_obs={M_CANON[seg]['n_obs']:,}, n>63={M_CANON[seg]['n_gt63']})\n{'─'*92}")
    print(f"{'modèle':>11} | {'R²glob':>7} | {'MAEglob':>8} | {'biais>63':>9} | {'MAE>63':>7} | "
          f"{'biais≤63':>8} | {'PRAUC_tr':>8} | {'PRAUC_to':>8}")
    print("-" * 92)
    for lab, M in LABELS:
        m = M[seg]
        print(f"{lab:>11} | {m['r2_global']:>7.4f} | {m['mae_global']:>8.3f} | {m['bias_gt63']:>+9.2f} | "
              f"{m['mae_gt63']:>7.2f} | {m['bias_le63']:>+8.2f} | {m['pr_auc_troncon']:>8.4f} | {m['pr_auc_tour']:>8.4f}")

for seg in ("bas", "haut", "global"):
    table(seg)

print(f"\n{'='*80}\nFichier : {OUT/'confirmation_h25_k2_w2.json'}")
print("ARRÊT — rapport de généralisation seul. Rien adopté, canonique intact.")
print("=" * 80)
