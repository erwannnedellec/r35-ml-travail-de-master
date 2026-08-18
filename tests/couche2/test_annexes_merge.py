"""
Non-regression : le merge resa2c d'annexes.py ne collisionne pas (fix couche2).

`build_decision_set()` porte deja une colonne `resa2c` (D3) ; `compute_annexes()`
construit sa propre table `resa` (ml-derivee) et la merge. Sans precaution, les deux
`resa2c` collisionnaient en `resa2c_x`/`resa2c_y` et `d2["resa2c"]` levait KeyError
(defaut pre-existant revele par la regeneration ba493568). Ce test verrouille le contrat :
le merge passe et les colonnes/cles attendues (dont le plancher X6 qui consomme resa2c)
sont presentes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

_MODELS_OK = (
    (ROOT / "models/enrichi_seg/enrichi_seg_bas_ba493568.json").exists()
    and (ROOT / "models/enrichi_seg/enrichi_seg_haut_ba493568.json").exists()
    and (ROOT / "data/processed/ml_dataset.parquet").exists()
)


@pytest.mark.skipif(not _MODELS_OK, reason="dataset/modeles ba493568 absents (hors env de donnees)")
def test_annexes_merge_resa2c_sans_collision():
    from couche2 import annexes

    res = annexes.compute_annexes()  # build_decision_set + merge resa (le point de collision)

    assert isinstance(res, dict)
    # Le plancher X6 consomme resa2c ; sa presence prouve que le merge a reussi.
    assert "X6_plancher_demande_annoncee" in res
    x6 = res["X6_plancher_demande_annoncee"]
    for annee in ("H24", "H25"):
        assert annee in x6, f"plancher {annee} absent"
        assert "n" in x6[annee]
    # Ancrage de perimetre (garde couche 2) coherent.
    assert res["meta"]["n_courses_H25"] == 29222
    assert res["meta"]["n_positives_H25"] == 2072
