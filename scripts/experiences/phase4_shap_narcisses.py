#!/usr/bin/env python3
"""
Phase 4e — SHAP des features narcisses, generation ba493568 (ADR-076).
Rang et magnitude de event_is_saison_narcisses / event_narcisses_source vs le
rang 84/158 et 2,5 % d'epoque. Utilise les SHAP exacts XGBoost (pred_contribs).
Threads=1 (ADR-076).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
HASH = "ba493568"
MODEL_DIR = ROOT / "models/enrichi_seg"
NARC = ["event_is_saison_narcisses", "event_narcisses_source"]


def prep_X(d, feats):
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X


def main():
    feats = json.loads((ROOT / "outputs/couche2/features_158f_sans_simba.json").read_text())["features"]
    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    h25 = df[df["horaire_annee_horaire"] == "H25"]

    per_model, combined = {}, np.zeros(len(feats))
    n_tot = 0
    for seg in ("bas", "haut"):
        m = xgb.XGBRegressor(); m.load_model(str(MODEL_DIR / f"enrichi_seg_{seg}_{HASH}.json"))
        sub = h25[h25["spatial_segment"] == seg]
        X = prep_X(sub, feats)[feats]  # ordre canonique des 158
        dm = xgb.DMatrix(X, enable_categorical=True)
        contribs = m.get_booster().predict(dm, pred_contribs=True)  # (n, 159) derniere col = biais
        mabs = np.abs(contribs[:, :-1]).mean(axis=0)                # mean|SHAP| par feature
        order = np.argsort(mabs)[::-1]
        rank = {f: int(np.where(order == feats.index(f))[0][0]) + 1 for f in NARC}
        total = mabs.sum()
        per_model[seg] = {
            "n": int(len(sub)),
            **{f: {"rang": rank[f], "mean_abs_shap": float(mabs[feats.index(f)]),
                   "pct_du_total": float(mabs[feats.index(f)] / total * 100)} for f in NARC},
        }
        combined += mabs * len(sub); n_tot += len(sub)

    combined /= n_tot
    order = np.argsort(combined)[::-1]
    total = combined.sum()
    comb = {f: {"rang": int(np.where(order == feats.index(f))[0][0]) + 1,
                "mean_abs_shap": float(combined[feats.index(f)]),
                "pct_du_total": float(combined[feats.index(f)] / total * 100)} for f in NARC}

    out = {"generation": HASH, "reference_416bb90b": {"event_is_saison_narcisses": {"rang": 84, "pct": 2.5}},
           "par_modele": per_model, "combine_pondere_n": comb}
    (ROOT / f"outputs/couche2/phase4_shap_narcisses_{HASH}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print("=== SHAP narcisses (ba493568) ===")
    for seg in ("bas", "haut"):
        for f in NARC:
            d = per_model[seg][f]
            print(f"  [{seg}] {f}: rang {d['rang']}/158, {d['pct_du_total']:.2f}% du total")
    print("  --- combine (pondere n_obs) ---")
    for f in NARC:
        print(f"  {f}: rang {comb[f]['rang']}/158, {comb[f]['pct_du_total']:.2f}% (ref epoque event_is_saison_narcisses: 84/158, 2.5%)")


if __name__ == "__main__":
    main()
