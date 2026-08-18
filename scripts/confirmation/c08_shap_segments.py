#!/usr/bin/env python3
"""
c08_shap_segments.py — ranking mean|SHAP| complet par segment (LECTURE SEULE).

Generalise phase4_shap_narcisses.py : SHAP exacts XGBoost (booster pred_contribs=True)
sur les modeles GELES enrichi_seg_{bas,haut}_ba493568.json, sur H25 (grain troncon).
Produit le ranking mean|SHAP| complet par segment, top 20, et un combine pondere par
n_obs. Aucun reentrainement.

Sorties : outputs/confirmation/c08_shap_ranks_{bas,haut}.csv + c08_shap_segments.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

TOP = 20


def main() -> int:
    print("=== c08 — SHAP par segment (mean|SHAP|, modeles geles) ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    h25 = df[df["horaire_annee_horaire"] == "H25"]

    per_seg, csv_paths = {}, {}
    combined = np.zeros(len(feats)); n_tot = 0
    for seg in ("bas", "haut"):
        model_file = H.MODEL_DIR / f"enrichi_seg_{seg}_ba493568.json"
        assert H.sha8(model_file) == (H.HASH_MODEL_BAS if seg == "bas" else H.HASH_MODEL_HAUT), \
            f"empreinte modele {seg} non canonique"
        m = xgb.XGBRegressor(); m.load_model(str(model_file))
        sub = h25[h25["spatial_segment"] == seg]
        X = H.prep_X(sub, feats)[feats]                       # ordre canonique des 158
        dm = xgb.DMatrix(X, enable_categorical=True)
        contribs = m.get_booster().predict(dm, pred_contribs=True)   # (n, 159) : derniere col = biais
        mabs = np.abs(contribs[:, :-1]).mean(axis=0)          # mean|SHAP| par feature
        total = float(mabs.sum())

        rank_df = pd.DataFrame({"feature": feats, "mean_abs_shap": mabs})
        rank_df = rank_df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
        rank_df["rang"] = rank_df.index + 1
        rank_df["pct_du_total"] = rank_df["mean_abs_shap"] / total * 100
        csv = H.OUT_DIR / f"c08_shap_ranks_{seg}.csv"
        H.OUT_DIR.mkdir(parents=True, exist_ok=True)
        rank_df.to_csv(csv, index=False)
        csv_paths[seg] = str(csv.relative_to(H.ROOT))

        per_seg[seg] = {
            "n_obs": int(len(sub)), "somme_mean_abs_shap": total,
            "top20": [{"rang": int(r.rang), "feature": r.feature,
                       "mean_abs_shap": float(r.mean_abs_shap),
                       "pct_du_total": float(r.pct_du_total)}
                      for r in rank_df.head(TOP).itertuples(index=False)],
        }
        combined += mabs * len(sub); n_tot += len(sub)
        print(f"  [{seg}] n={len(sub)} | top1={rank_df.iloc[0].feature} "
              f"({rank_df.iloc[0].pct_du_total:.1f}%) | fichier={csv.name}")

    combined /= n_tot
    ctotal = float(combined.sum())
    comb_df = pd.DataFrame({"feature": feats, "mean_abs_shap": combined})
    comb_df = comb_df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    comb_df["rang"] = comb_df.index + 1
    comb_df["pct_du_total"] = comb_df["mean_abs_shap"] / ctotal * 100
    comb_csv = H.OUT_DIR / "c08_shap_ranks_combine.csv"
    comb_df.to_csv(comb_csv, index=False)
    csv_paths["combine"] = str(comb_csv.relative_to(H.ROOT))

    payload = {
        "script": "c08_shap_segments.py",
        "role": "ranking mean|SHAP| complet par segment (modeles geles, H25, grain troncon)",
        "meta": H.meta_block(models_loaded=True, n_test=int(len(h25)),
                             extra={"methode": "XGBoost pred_contribs=True (SHAP exact)",
                                    "n_features": len(feats), "top_exporte": TOP,
                                    "csv": csv_paths}),
        "par_segment": per_seg,
        "combine_pondere_n": {
            "top20": [{"rang": int(r.rang), "feature": r.feature,
                       "mean_abs_shap": float(r.mean_abs_shap),
                       "pct_du_total": float(r.pct_du_total)}
                      for r in comb_df.head(TOP).itertuples(index=False)],
        },
    }
    out = H.write_json("c08_shap_segments.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)} + {len(csv_paths)} CSV")
    return 0


if __name__ == "__main__":
    sys.exit(main())
