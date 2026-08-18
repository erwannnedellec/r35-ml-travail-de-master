#!/usr/bin/env python3
"""
Persiste la courbe precision-rappel de la couche 2 (H25, grain course) et ses points
de fonctionnement, pour la figure de la section 4.7.1 du memoire.

Pourquoi ce script existe. `src/couche2/decision.py` calcule la courbe dans
`evaluate_h25()` sous la cle `_pr_curve`, s'en sert pour la figure PNG, puis la RETIRE
avant d'ecrire `q_couche2_eval_ba493568.json` (elle pese ~1,5 Mo pour 29 209 points).
Le generateur du manuscrit, lui, a besoin de la courbe. Ce script la re-derive par le
meme chemin et la persiste, sans modifier le code gele de la couche 2.

Lecture seule stricte sur les artefacts canoniques. Ecrit un seul fichier :
    outputs/couche2/q_couche2_pr_courbe_ba493568.json
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import blocs, decision  # noqa: E402

CALIB = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"
OUT = ROOT / "outputs/couche2/q_couche2_pr_courbe_ba493568.json"
REGLES = ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")


def main() -> None:
    blocs.assert_canonical_dataset()
    if not CALIB.is_file():
        raise SystemExit(f"[ARRET] calibration absente : {CALIB.relative_to(ROOT)} — "
                         "lancer d'abord scripts/experiences/phase4_migration_ba493568.py")

    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)
    calib = json.loads(CALIB.read_text())
    ev = decision.evaluate_h25(ds, calib)

    points = {
        "humain": ev["humain_H25"]["global"],
        "top_k_protocolaire": {"k": ev["headline_top_k_protocolaire"]["k"],
                               **ev["headline_top_k_protocolaire"]["global"]},
    }
    for rk in REGLES:
        points[rk] = {"seuil": calib["regles_deployables"][rk]["seuil"],
                      **ev["deployable_menu"][rk]["seuil_fige"]["global"]}

    payload = {
        "meta": {
            "hash": blocs.HASH_CANONIQUE,
            "grain": "course",
            "perimetre": f"H25 iso {info['n_h25']} / {info['positives_h25']} surcharges",
            "source": "src/couche2/decision.py evaluate_h25 (lecture seule des modeles geles "
                      "e4ddfccd/df6a11c5)",
            "note": "courbe PR persistee pour la figure du manuscrit (section 4.7.1) ; "
                    "_pr_curve n'est pas conservee dans q_couche2_eval_ba493568.json",
        },
        "pr_curve": ev["_pr_curve"],
        "points": points,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    n = len(payload["pr_curve"]["precision"])
    print(f"[OK] {OUT.relative_to(ROOT)} — {n} points de courbe, "
          f"{len(points)} points de fonctionnement")


if __name__ == "__main__":
    main()
