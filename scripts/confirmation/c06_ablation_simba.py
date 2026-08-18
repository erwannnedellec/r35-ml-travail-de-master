#!/usr/bin/env python3
"""
c06_ablation_simba.py — ablation SIMBA : 158f (canonique) vs 170f (158 + 12 simba_*).

Adapte retrait_simba_158f.py sur ba493568. Deux bras reentraines (Split C, HP canoniques,
seed 42, threads=1) :
  - 158f segmente = modele canonique. Comme reentrainement sur Split C, il DOIT reproduire
    l'empreinte archivee e4ddfccd/df6a11c5 (invariance inter-generations). Divergence = STOP.
  - 170f segmente = 158 + les 12 features simba_part_*.
Delta R2 par segment = 158f - 170f (effet du RETRAIT de SIMBA). Chiffres seuls.

Sortie : outputs/confirmation/c06_ablation_simba.json.
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

SIMBA_12 = [
    "simba_part_ga", "simba_part_mobilis", "simba_part_billet_hta",
    "simba_part_spar", "simba_part_jeunes", "simba_part_abonnement",
    "simba_part_militaire", "simba_part_autre", "simba_part_corresp_amont",
    "simba_part_corresp_aval", "simba_part_premiere_classe", "simba_part_intra_r35",
]
SEGMENTS = ("bas", "haut", "global")


def main() -> int:
    print("=== c06 — ablation SIMBA (158f vs 170f), Split C, ba493568 ===")
    H.assert_dataset()
    feats_158 = H.load_features_158()
    df = H.load_dataset()
    missing = [c for c in SIMBA_12 if c not in df.columns]
    assert not missing, f"features simba manquantes : {missing}"
    feats_170 = feats_158 + SIMBA_12
    assert len(feats_170) == 170
    train, test = H.split_c(df)
    print(f"  Split C : train={len(train)} | test H25={len(test)}")

    # -- bras 158f (canonique) : reentrainement + reproduction d'empreinte (GARDE) --
    t0 = time.time()
    pred_158, models_158 = H.train_segmented(train, test, feats_158)
    repro = H.reproduce_and_hash_segmented(models_158)
    dt_158 = time.time() - t0
    print(f"  158f : reproduction empreintes = {repro['all_identical']} "
          f"(bas {repro['bas']['retrained']} / haut {repro['haut']['retrained']}) ({dt_158:.0f}s)")
    if not repro["all_identical"]:
        payload = {"script": "c06_ablation_simba.py", "STOP": True,
                   "raison": "le reentrainement 158f segmente NE reproduit PAS e4ddfccd/df6a11c5",
                   "model_reproduction": repro,
                   "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)))}
        H.write_json("c06_ablation_simba.json", payload)
        print("!" * 72 + "\nSTOP c06 : empreinte 158f non reproduite. Rapport ecrit, arret.\n" + "!" * 72)
        return 1
    metrics_158 = H.metrics_by_segment(test, pred_158)

    # -- bras 170f (158 + 12 simba_*) --
    t1 = time.time()
    pred_170, _ = H.train_segmented(train, test, feats_170)
    dt_170 = time.time() - t1
    metrics_170 = H.metrics_by_segment(test, pred_170)

    delta_r2_158_moins_170 = {s: metrics_158[s]["r2"] - metrics_170[s]["r2"] for s in SEGMENTS}
    for s in SEGMENTS:
        print(f"  [{s:6}] R2 158f={metrics_158[s]['r2']:.6f} | 170f={metrics_170[s]['r2']:.6f} "
              f"| delta(158-170)={delta_r2_158_moins_170[s]:+.6f}")

    payload = {
        "script": "c06_ablation_simba.py",
        "role": "ablation SIMBA : 158f (canonique) vs 170f (158 + 12 simba_part_*), delta R2 H25",
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)),
                             extra={"features_simba_ajoutees": SIMBA_12,
                                    "n_features_158": 158, "n_features_170": 170,
                                    "hyperparams": "ADR-052 (300/6/0.1/0.8/0.8, seed=42)",
                                    "durees_s": {"train_158f": round(dt_158, 1), "train_170f": round(dt_170, 1)}}),
        "metriques_h25_158f": metrics_158,
        "metriques_h25_170f": metrics_170,
        "delta_r2_158f_moins_170f": delta_r2_158_moins_170,
        "model_reproduction": {
            "bras_158f": repro,
            "bras_170f": {"archived": None, "retrained": None, "identical": None,
                          "note": "sans objet : pas d'artefact 170f ba493568 archive"},
        },
    }
    out = H.write_json("c06_ablation_simba.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
