#!/usr/bin/env python3
"""
c03_baseline_lineaire.py — baseline lineaire regularisee (Ridge) sur les 158 features.

NOUVEAU (aucune baseline lineaire n'existait dans le depot). Ridge (sklearn.linear_model),
alpha par defaut (1.0) + validation grossiere sur H24 (sweep d'alphas, PAS de tuning fin).
Split C standard, seed 42, threads=1. Evaluation H25 bas/haut/global.

Pretraitement (un modele lineaire n'a pas la tolerance native de XGBoost) :
  - NUMERIQUES (152 : 24 Int + 128 float) : imputation par la MEDIANE DU TRAIN + standardisation.
    XGBoost route les NaN nativement (branche apprise) ; Ridge exige des entrees completes,
    d'ou l'imputation mediane (choix documente ici).
  - CATEGORIELLES (6, faible cardinalite, 0 % NaN) : most_frequent + one-hot (handle_unknown=ignore).
Modele GLOBAL (un Ridge) ; metriques ventilees bas/haut/global sur H25.
Pas d'artefact archive -> model_reproduction = sans objet.

Sortie : outputs/confirmation/c03_baseline_lineaire.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

ALPHA_DEFAUT = 1.0
ALPHAS_SWEEP = [0.1, 1.0, 10.0, 100.0, 1000.0]


def build_design(d, feats, cat_cols, num_cols):
    """DataFrame des 158 features : categorielles en str, numeriques en float64 (NaN preserves)."""
    X = d[feats].copy()
    for c in cat_cols:
        X[c] = X[c].astype("string").astype("object")
    for c in num_cols:
        X[c] = X[c].astype("float64")
    return X


def make_pipeline(cat_cols, num_cols, alpha):
    num = Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())])
    cat = Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                    ("oh", OneHotEncoder(handle_unknown="ignore"))])
    pre = ColumnTransformer([("num", num, num_cols), ("cat", cat, cat_cols)])
    return Pipeline([("pre", pre), ("ridge", Ridge(alpha=alpha, random_state=H.SEED))])


def main() -> int:
    print("=== c03 — baseline lineaire Ridge (158 features), Split C, ba493568 ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()

    cat_cols = [c for c in feats if str(df[c].dtype) in ("object", "string", "category")]
    num_cols = [c for c in feats if c not in cat_cols]
    print(f"  features : {len(num_cols)} numeriques (imputation mediane) + {len(cat_cols)} categorielles (one-hot)")

    train, test = H.split_c(df)
    Xtr = build_design(train, feats, cat_cols, num_cols); ytr = H.y_of(train)
    Xte = build_design(test, feats, cat_cols, num_cols)

    # -- validation grossiere sur H24 (sweep alpha, PAS de tuning fin) --
    fit_mask = train["horaire_annee_horaire"].isin(["H22", "H23"]).values
    val_mask = (train["horaire_annee_horaire"] == "H24").values
    Xfit, yfit = Xtr[fit_mask], ytr[fit_mask]
    Xval, yval = Xtr[val_mask], ytr[val_mask]
    sweep = {}
    print("  validation grossiere H24 (R2 global) :")
    for a in ALPHAS_SWEEP:
        pipe = make_pipeline(cat_cols, num_cols, a).fit(Xfit, yfit)
        r2v = float(r2_score(yval, pipe.predict(Xval)))
        sweep[str(a)] = r2v
        print(f"    alpha={a:<7} R2_H24={r2v:.6f}")
    best_alpha = float(max(sweep, key=sweep.get))

    # -- headline : Ridge alpha par defaut, refit sur tout le train Split C --
    t0 = time.time()
    pipe = make_pipeline(cat_cols, num_cols, ALPHA_DEFAUT).fit(Xtr, ytr)
    pred = pipe.predict(Xte).astype("float64")
    dt = time.time() - t0
    metrics = H.metrics_by_segment(test, pred)
    for s in ("bas", "haut", "global"):
        m = metrics[s]
        print(f"  [{s:6}] R2={m['r2']:.6f} [{m['r2_ci_lo']:.4f};{m['r2_ci_hi']:.4f}] "
              f"MAE={m['mae']:.3f} PR-AUC={m['pr_auc']:.4f} n={m['n_obs']}")

    payload = {
        "script": "c03_baseline_lineaire.py",
        "role": "baseline lineaire regularisee (Ridge) sur 158 features, evaluation H25",
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)),
                             extra={"modele": "Ridge (sklearn.linear_model), GLOBAL",
                                    "alpha_headline": ALPHA_DEFAUT,
                                    "n_features_entree": len(feats),
                                    "n_numeriques": len(num_cols), "n_categorielles": len(cat_cols),
                                    "categorielles": cat_cols,
                                    "imputation": "numeriques = mediane du train ; categorielles = "
                                    "most_frequent + one-hot (handle_unknown=ignore)",
                                    "note_nan": "XGBoost route les NaN nativement ; Ridge exige des "
                                    "entrees completes -> imputation mediane du train (documentee)",
                                    "standardisation": "StandardScaler sur les numeriques",
                                    "duree_entrainement_s": round(dt, 1)}),
        "validation_grossiere_H24": {"alphas": sweep, "meilleur_alpha_H24": best_alpha,
                                     "note": "sweep informatif (fit H22-H23, val H24) ; headline = alpha defaut 1.0, PAS de tuning fin"},
        "metriques_h25": metrics,
        "model_reproduction": {"archived": None, "retrained": None, "identical": None,
                               "note": "sans objet : pas d'artefact lineaire archive"},
    }
    out = H.write_json("c03_baseline_lineaire.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)} (train {dt:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
