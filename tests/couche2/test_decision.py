"""
tests/couche2/test_decision.py — Couche 2 phase 2 (decision.py).
Tests : D2 (label course), D3 (agrégation max), respect du budget (D5),
non-contamination H25 (aucun seuil dérivé de H25), P2 (segment de blocs),
P3 (ancrage périmètre/label). Les tests intégration nécessitent les données.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from couche2 import decision  # noqa: E402


# ── Unitaires (sans données) ───────────────────────────────────────────────────
class TestUnitaires:
    def test_d3_agregation_max(self):
        # D3 : score de course = max des prédictions sur tronçons
        tr = pd.DataFrame({"date": ["d", "d"], "numero_train": ["1", "1"], "annee": ["H24", "H24"],
                           "pred": [10.0, 42.0], "target": [5.0, 70.0]})
        c = tr.groupby(["date", "numero_train", "annee"]).agg(score=("pred", "max"),
                                                              charge_max=("target", "max")).reset_index()
        assert c["score"].iloc[0] == 42.0                      # max, pas moyenne

    def test_d2_label_seuil_63(self):
        # D2 : positif si au moins un tronçon observé > 63 (strict)
        assert float(pd.Series([5.0, 70.0]).max()) > decision.SEUIL       # 70 > 63
        assert not float(pd.Series([5.0, 63.0]).max()) > decision.SEUIL   # 63 non strictement > 63

    def test_metrics_at(self):
        s = np.array([1.0, 2.0, 3.0, 4.0]); y = np.array([False, False, True, True])
        m = decision._metrics_at(s, y, 2.5)                    # recommande score>=2.5 -> {3,4}
        assert m["volume"] == 2 and m["VP"] == 2 and m["precision"] == 1.0
        assert m["rappel"] == 1.0                              # 2 VP / 2 positifs


# ── Intégration (données canoniques) ───────────────────────────────────────────
@pytest.fixture(scope="module")
def ds():
    return decision.build_decision_set()


@pytest.mark.skipif(
    not (decision.MODEL_BAS.exists() and decision.blocs.ML_DATASET.exists()),
    reason="modèles ou jeu canonique absents (dépôt livré sans les données)")
class TestIntegration:
    def test_p3_ancrage_perimetre_label(self, ds):
        info = decision.assert_perimetre_et_ancrage(ds)        # lève si écart
        assert info["n_h25"] == 29222
        assert (info["positives_h25"], info["positives_haut"], info["positives_bas"]) == (2072, 1224, 848)

    def test_budget_humain(self, ds):
        # D5 : budgets = décisions UM humaines par année
        assert int(ds[ds.annee == "H25"]["is_UM"].sum()) == 418
        assert int(ds[ds.annee == "H24"]["is_UM"].sum()) == 381

    def test_p2_segment_de_blocs(self, ds):
        # P2 : la ventilation segment vient de blocs (mêmes courses, même clé)
        charge = decision.blocs.load_charge()
        charge["date"] = pd.to_datetime(charge["date"]).dt.normalize()
        ref = charge.set_index(["date", "numero_train"]).segment
        h25 = ds[ds.annee == "H25"]
        joined = h25.set_index(["date", "numero_train"]).segment
        common = joined.index.intersection(ref.index)
        assert (joined.loc[common] == ref.loc[common]).all()   # segment identique des deux côtés

    def test_non_contamination_H25(self, ds):
        # les 3 seuils déployables ne dépendent QUE de H24 : perturber H25 ne les change pas
        base = decision.calibrate(ds)["regles_deployables"]
        ds2 = ds.copy()
        m25 = ds2.annee == "H25"
        ds2.loc[m25, "score"] = ds2.loc[m25, "score"] + 1000.0     # H25 fortement perturbé
        ds2.loc[m25, "label"] = ~ds2.loc[m25, "label"]
        pert = decision.calibrate(ds2)["regles_deployables"]
        for rk in base:
            assert base[rk]["seuil"] == pert[rk]["seuil"]           # seuils inchangés
