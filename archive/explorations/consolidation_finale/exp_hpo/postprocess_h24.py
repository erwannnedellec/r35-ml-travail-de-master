"""Post-traitement HPO (lit le CSV des trials — pas de ré-optimisation).
Recalcule la référence ADR-CF09 (2 fits rapides, pour PR-AUC tour complet),
extrait les points Pareto, écrit le JSON de synthèse et imprime les tables.
Hors canonique, H25 jamais chargé, hash 416bb90b intact."""
import json, hashlib
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_hpo"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"
HASH_ATTENDU, GIL, SEUIL, SEED = "416bb90b", 8501260, 63, 42
TARGET = "target_voyageurs_2eme_classe"
HP_ACTUELS = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
                  colsample_bytree=0.8, min_child_weight=1, reg_lambda=1.0, reg_alpha=0.0, gamma=0.0)
FIXED = dict(objective="reg:squarederror", tree_method="hist", random_state=SEED,
             enable_categorical=True, verbosity=0, n_jobs=-1)

assert hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8] == HASH_ATTENDU
df = pd.read_parquet(PARQUET)
FEATS = json.load(open(FEAT_JSON))["features"]
h22 = df[df["horaire_annee_horaire"] == "H22"]
gil = (h22["id_gare_depart_bpuic"].astype("int64") == GIL) | (h22["id_gare_arrivee_bpuic"].astype("int64") == GIL)
train = pd.concat([h22[~gil].copy(), df[df["horaire_annee_horaire"] == "H23"].copy()], ignore_index=True)
valid = df[df["horaire_annee_horaire"] == "H24"].copy()
del df
def prep_X(d):
    X = d[[c for c in FEATS if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"): X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"): X[c] = X[c].astype("float64")
    return X
mtr = {s: (train["spatial_segment"] == s).values for s in ("bas", "haut")}
mva = {s: (valid["spatial_segment"] == s).values for s in ("bas", "haut")}
X_tr = {s: prep_X(train[mtr[s]]) for s in ("bas", "haut")}
X_va = {s: prep_X(valid[mva[s]]) for s in ("bas", "haut")}
y_tr = {s: train.loc[mtr[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_va = {s: valid.loc[mva[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
tkey = {s: list(zip(valid.loc[mva[s], "base_date"], valid.loc[mva[s], "horaire_numero_train"])) for s in ("bas", "haut")}
def pr_tour(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp}).groupby("k").agg(mo=("obs","max"), mp=("pred","max"))
    yb = (g["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, g["mp"].values)) if yb.sum() else None
def eval_seg(s, p):
    m = xgb.XGBRegressor(**p, **FIXED); m.fit(X_tr[s], y_tr[s]); yp = m.predict(X_va[s]).astype("float64")
    yt = y_va[s]; z = yt > SEUIL; r = yp - yt
    return {"r2": float(r2_score(yt, yp)), "bias_gt63": float(r[z].mean()), "abs_bias_gt63": float(abs(r[z].mean())),
            "mae_gt63": float(np.abs(r[z]).mean()), "mae_global": float(mean_absolute_error(yt, yp)),
            "pr_auc_troncon": float(average_precision_score(z.astype(int), yp)), "pr_auc_tour": pr_tour(tkey[s], yt, yp)}

ref = {s: eval_seg(s, HP_ACTUELS) for s in ("bas", "haut")}
trials = pd.read_csv(OUT / "tuning_optuna_h24_trials.csv")
HPCOLS = [c for c in trials.columns if c.startswith("hp_")]

def metrics_row(r):
    return {"r2": float(r["r2"]), "bias_gt63": float(r["bias_gt63"]), "abs_bias_gt63": float(r["abs_bias_gt63"]),
            "mae_gt63": float(r["mae_gt63"]), "mae_global": float(r["mae_global"]),
            "pr_auc_troncon": float(r["pr_auc_troncon"]), "pr_auc_tour": float(r["pr_auc_tour"]),
            "params": {c[3:]: (float(r[c]) if "." in str(r[c]) or "e" in str(r[c]).lower() else r[c]) for c in HPCOLS}}

summary = {"experiment": "CHANTIER HPO — Optuna multi-objectif validation H24",
           "statut": "EXPÉRIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact",
           "methode": "Optuna TPE multi-objectif [max R²_H24, min |biais>63_H24|], pas de CV aléatoire",
           "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; H25 jamais touché",
           "perte": "reg:squarederror", "n_trials": 50, "seed": SEED, "dataset_hash": HASH_ATTENDU,
           "hp_actuels_adr_cf09": HP_ACTUELS, "reference_h24": ref, "pareto": {}}
for s in ("bas", "haut"):
    par = trials[(trials.segment == s) & (trials.is_pareto)].copy()
    rs = par["r2"].values; bsv = par["abs_bias_gt63"].values
    rn = (rs - rs.min()) / (np.ptp(rs) + 1e-12); bn = (bsv - bsv.min()) / (np.ptp(bsv) + 1e-12)
    knee = par.iloc[int(np.argmin((1 - rn) ** 2 + bn ** 2))]
    summary["pareto"][s] = {"n_pareto": int(len(par)),
        "best_R2": metrics_row(par.loc[par["r2"].idxmax()]),
        "best_bias": metrics_row(par.loc[par["abs_bias_gt63"].idxmin()]),
        "knee": metrics_row(knee)}
def _native(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    raise TypeError(str(type(o)))
(OUT / "tuning_optuna_h24_resultats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=_native))

for s in ("bas", "haut"):
    p = summary["pareto"][s]; r = ref[s]
    print(f"\n{'─'*96}\nTABLE H24 — segment {s.upper()}  ({p['n_pareto']} pts Pareto)  HP actuels vs Pareto\n{'─'*96}")
    print(f"{'config':>22} | {'R²':>7} | {'biais>63':>9} | {'MAE>63':>7} | {'MAEglob':>8} | {'PRAUC_tr':>8} | {'PRAUC_to':>8}")
    print("-" * 96)
    def row(lab, m):
        print(f"{lab:>22} | {m['r2']:>7.4f} | {m['bias_gt63']:>+9.2f} | {m['mae_gt63']:>7.2f} | {m['mae_global']:>8.3f} | {m['pr_auc_troncon']:>8.4f} | {(m['pr_auc_tour'] or 0):>8.4f}")
    row("HP actuels (CF09)", r); row("Pareto best-R²", p["best_R2"]); row("Pareto knee", p["knee"]); row("Pareto best-biais", p["best_bias"])
    b = p["best_R2"]
    print(f"  Δ best-R² vs actuels : R²={b['r2']-r['r2']:+.4f}  biais>63={b['bias_gt63']-r['bias_gt63']:+.2f}  "
          f"PRAUC_tr={b['pr_auc_troncon']-r['pr_auc_troncon']:+.4f}  PRAUC_to={(b['pr_auc_tour'] or 0)-(r['pr_auc_tour'] or 0):+.4f}")
    print(f"  best-R² params : {p['best_R2']['params']}")
print("\nJSON → tuning_optuna_h24_resultats.json")
