#!/usr/bin/env python3
"""
c02_baseline_m0.py — baseline M0 (APC + calendrier), modele GLOBAL, sur ba493568.

Adapte q9_baseline_m0_158cond.py. M0 = features cal_* + histo_* extraites des 158f
(baseline minimal : signal APC historique + calendrier structurel, sans source externe).
UN seul XGBoost GLOBAL (non segmente), HP canoniques, seed 42, threads=1.

Difference assumee vs q9 historique : Split C standard (train H22 hors Gilamont + H23 + H24),
au lieu du H22-H24 plein de q9 (harmonisation de la suite de confirmation, documentee ici).
M0 n'a pas d'artefact ba493568 archive -> model_reproduction = sans objet.

Evaluation H25 bas/haut/global (format preenregistre). Sortie : c02_baseline_m0.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402


def main() -> int:
    print("=== c02 — baseline M0 (cal_ + histo_) GLOBAL, Split C, ba493568 ===")
    H.assert_dataset()
    feats = H.load_features_158()
    feats_m0 = [f for f in feats if f.startswith("cal_") or f.startswith("histo_")]
    n_cal = sum(f.startswith("cal_") for f in feats_m0)
    n_histo = sum(f.startswith("histo_") for f in feats_m0)
    assert len(feats_m0) == 31, f"M0 attendu 31 (cal_+histo_), obtenu {len(feats_m0)}"
    print(f"  M0 : {len(feats_m0)} features ({n_cal} cal_ + {n_histo} histo_)")

    df = H.load_dataset()
    train, test = H.split_c(df)
    print(f"  Split C : train={len(train)} | test H25={len(test)}")

    t0 = time.time()
    pred, _ = H.train_global(train, test, feats_m0)
    dt = time.time() - t0
    metrics = H.metrics_by_segment(test, pred)
    for s in ("bas", "haut", "global"):
        m = metrics[s]
        print(f"  [{s:6}] R2={m['r2']:.6f} [{m['r2_ci_lo']:.4f};{m['r2_ci_hi']:.4f}] "
              f"MAE={m['mae']:.3f} PR-AUC={m['pr_auc']:.4f} n={m['n_obs']}")

    payload = {
        "script": "c02_baseline_m0.py",
        "role": "baseline M0 (APC + calendrier), modele global, evaluation H25",
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)),
                             extra={"model_type": "GLOBAL (un XGBoost, sans segmentation)",
                                    "features_m0": feats_m0, "n_features_m0": len(feats_m0),
                                    "n_cal": n_cal, "n_histo": n_histo,
                                    "hyperparams": "ADR-052 (300/6/0.1/0.8/0.8, seed=42)",
                                    "note_split": "Split C (harmonise) vs q9 historique H22-H24 plein",
                                    "duree_entrainement_s": round(dt, 1)}),
        "metriques_h25": metrics,
        "model_reproduction": {"archived": None, "retrained": None, "identical": None,
                               "note": "sans objet : pas d'artefact M0 ba493568 archive"},
    }
    out = H.write_json("c02_baseline_m0.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)} (train {dt:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
