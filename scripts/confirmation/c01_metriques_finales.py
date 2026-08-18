#!/usr/bin/env python3
"""
c01_metriques_finales.py — replay LECTURE SEULE des modeles couche 1 GELES.

Recharge les modeles figes (enrichi_seg_{bas,haut}_ba493568.json) via
decision.load_troncon_predictions() (aucun reentrainement), recalcule les metriques
finales H25 (bas/haut/global, format preenregistre) et ASSERTE leur concordance
avec enrichi_seg_metadata.json (R2, n_obs, n_gt63, prevalence).

GATE de la suite : si la concordance echoue, STOP (rien d'autre ne doit tourner).
Ecrit outputs/confirmation/c01_metriques_finales.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

sys.path.insert(0, str(H.ROOT / "src"))
from couche2 import decision  # noqa: E402

TOL_R2 = 1e-4
TOL_PREV = 1e-6


def main() -> int:
    print("=== c01 — metriques finales H25 (replay lecture seule des modeles geles) ===")

    # -- integrite (dur) : dataset ba493568 + modeles e4ddfccd/df6a11c5 --
    H.assert_dataset()
    model_hashes = {"bas": H.sha8(H.MODEL_DIR / "enrichi_seg_bas_ba493568.json"),
                    "haut": H.sha8(H.MODEL_DIR / "enrichi_seg_haut_ba493568.json")}
    model_hashes_ok = (model_hashes["bas"] == H.HASH_MODEL_BAS and
                       model_hashes["haut"] == H.HASH_MODEL_HAUT)

    # -- predictions figees (grain troncon), H25 seul --
    tr = decision.load_troncon_predictions()          # asserte dataset + modeles
    h25 = tr[tr["annee"] == "H25"].copy()
    if len(h25) != H.N_TEST_H25:
        raise RuntimeError(f"STOP : n_test H25={len(h25)} != {H.N_TEST_H25} attendu.")

    computed = {}
    for s in ("bas", "haut"):
        m = h25["spatial_segment"] == s
        computed[s] = H.seg_metrics(h25.loc[m, "target"].values, h25.loc[m, "pred"].values)
    computed["global"] = H.seg_metrics(h25["target"].values, h25["pred"].values)

    # -- concordance avec la metadata canonique --
    meta = json.loads(H.METADATA.read_text())
    ref = meta["metrics_h25"]
    checks, all_ok = {}, True
    for seg in ("bas", "haut", "global"):
        c, r = computed[seg], ref[seg]
        seg_ok = {
            "r2": abs(c["r2"] - r["r2"]) < TOL_R2,
            "n_obs": c["n_obs"] == r["n_obs"],
            "n_gt63": c["n_gt63"] == r["n_gt63"],
            "prevalence": abs(c["prevalence"] - r["prevalence"]) < TOL_PREV,
        }
        checks[seg] = {
            "r2_calcule": c["r2"], "r2_metadata": r["r2"], "r2_delta": c["r2"] - r["r2"],
            "n_obs_calcule": c["n_obs"], "n_obs_metadata": r["n_obs"],
            "n_gt63_calcule": c["n_gt63"], "n_gt63_metadata": r["n_gt63"],
            "concordant": all(seg_ok.values()), "detail": seg_ok,
        }
        all_ok = all_ok and all(seg_ok.values())
        print(f"  [{seg:6}] R2 calcule={c['r2']:.6f} metadata={r['r2']:.6f} "
              f"delta={c['r2']-r['r2']:+.2e} concordant={all(seg_ok.values())}")

    concordance_ok = all_ok and model_hashes_ok

    payload = {
        "script": "c01_metriques_finales.py",
        "role": "replay lecture seule des modeles geles + concordance metadata (GATE)",
        "meta": H.meta_block(models_loaded=True, n_test=len(h25),
                             extra={"model_hashes_calcules": model_hashes,
                                    "model_hashes_concordants": model_hashes_ok}),
        "metriques_h25": computed,
        "concordance_metadata": {"tol_r2": TOL_R2, "tol_prevalence": TOL_PREV,
                                 "par_segment": checks,
                                 "empreintes_modeles_ok": model_hashes_ok,
                                 "GATE_ok": concordance_ok},
        "model_reproduction": {"note": "c01 ne reentraine pas : concordance = metriques recalculees "
                               "vs metadata + empreintes des fichiers modeles figes",
                               "archived": {"bas": H.HASH_MODEL_BAS, "haut": H.HASH_MODEL_HAUT},
                               "retrained": None, "identical": None},
    }
    out = H.write_json("c01_metriques_finales.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")

    if not concordance_ok:
        print("\n" + "!" * 72)
        print("STOP — concordance c01 ECHOUE. La suite ne doit pas se poursuivre.")
        print("  empreintes modeles OK :", model_hashes_ok)
        for seg, d in checks.items():
            if not d["concordant"]:
                print(f"  [{seg}] non concordant : {d['detail']}")
        print("!" * 72)
        return 1

    print("[GATE OK] concordance metadata + empreintes modeles verifiees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
