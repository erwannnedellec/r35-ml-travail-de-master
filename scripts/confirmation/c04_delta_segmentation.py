#!/usr/bin/env python3
"""
c04_delta_segmentation.py — decomposition 2x2 complete (subsume c05).

Grille {M0, 158f} x {global, segmente}, Split C, ba493568 :
  - M0_global      : XGBoost global, 31 features (cal_ + histo_)         [reentraine]
  - M0_seg         : 2 XGBoost segmentes, 31 features                    [reentraine]
  - 158_global     : XGBoost global, 158 features                        [reentraine]
  - 158_seg (gel)  : modeles couche 1 GELES e4ddfccd/df6a11c5            [lecture seule]

Fournit d'un bloc :
  - Delta enrichissement = 158 - M0 (a global fixe, et a segmente fixe), par segment ;
  - Delta segmentation   = segmente - global (a M0 fixe, et a 158 fixe), par segment ;
  - Delta total          = 158_seg - M0_global, par segment.

Couvre donc c04 ET c05 (delta enrichissement). c05 non produit (redondant).
Model_reproduction : 158_seg = gel reutilise (identique par construction) ; les cellules
reentrainees n'ont pas d'artefact archive -> sans objet.

Sortie : outputs/confirmation/c04_delta_segmentation.json.
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

SEGMENTS = ("bas", "haut", "global")


def r2_of(cell):
    return {s: cell[s]["r2"] for s in SEGMENTS}


def diff(a, b):
    return {s: a[s] - b[s] for s in SEGMENTS}


def main() -> int:
    print("=== c04 — decomposition 2x2 (M0/158 x global/seg), Split C, ba493568 ===")
    H.assert_dataset()
    feats = H.load_features_158()
    feats_m0 = [f for f in feats if f.startswith("cal_") or f.startswith("histo_")]
    assert len(feats_m0) == 31
    df = H.load_dataset()
    train, test = H.split_c(df)
    print(f"  Split C : train={len(train)} | test H25={len(test)}")

    cells, durees = {}, {}

    def timed(name, fn):
        t0 = time.time()
        pred = fn()
        cells[name] = H.metrics_by_segment(test, pred)
        durees[name] = round(time.time() - t0, 1)
        r = r2_of(cells[name])
        print(f"  [{name:12}] R2 bas={r['bas']:.4f} haut={r['haut']:.4f} global={r['global']:.4f} ({durees[name]}s)")

    timed("M0_global", lambda: H.train_global(train, test, feats_m0)[0])
    timed("M0_seg", lambda: H.train_segmented(train, test, feats_m0)[0])
    timed("158_global", lambda: H.train_global(train, test, feats)[0])
    timed("158_seg_gel", lambda: H.frozen_predict(test, feats))   # modeles geles (lecture seule)

    r = {k: r2_of(v) for k, v in cells.items()}
    decomposition_r2 = {
        "delta_enrichissement_158_moins_M0": {
            "a_global_fixe": diff(r["158_global"], r["M0_global"]),
            "a_segmente_fixe": diff(r["158_seg_gel"], r["M0_seg"]),
        },
        "delta_segmentation_seg_moins_global": {
            "a_M0_fixe": diff(r["M0_seg"], r["M0_global"]),
            "a_158_fixe": diff(r["158_seg_gel"], r["158_global"]),
        },
        "delta_total_158seg_moins_M0global": diff(r["158_seg_gel"], r["M0_global"]),
    }

    payload = {
        "script": "c04_delta_segmentation.py",
        "role": "decomposition 2x2 R2 H25 (delta segmentation + delta enrichissement) ; subsume c05",
        "meta": H.meta_block(models_loaded=True, n_train=int(len(train)), n_test=int(len(test)),
                             extra={"grille": "{M0(31f), 158f} x {global, segmente}",
                                    "n_features_m0": len(feats_m0), "n_features_full": len(feats),
                                    "hyperparams": "ADR-052 (300/6/0.1/0.8/0.8, seed=42)",
                                    "cellule_158_seg": "modeles GELES e4ddfccd/df6a11c5 (lecture seule)",
                                    "durees_s": durees}),
        "cellules_metriques_h25": cells,
        "decomposition_r2": decomposition_r2,
        "model_reproduction": {
            "158_seg_gel": {"archived": {"bas": H.HASH_MODEL_BAS, "haut": H.HASH_MODEL_HAUT},
                            "retrained": None, "identical": True,
                            "note": "gel reutilise en lecture seule (non reentraine)"},
            "cellules_reentrainees": {"archived": None, "retrained": None, "identical": None,
                                      "note": "sans objet : M0/158-global n'ont pas d'artefact ba493568 archive"},
        },
    }
    out = H.write_json("c04_delta_segmentation.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
