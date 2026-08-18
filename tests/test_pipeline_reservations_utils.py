"""
tests/test_pipeline_reservations_utils.py
==========================================
Tests unitaires de reservations_utils.py.

Couvre : build_line_order_from_ml, get_troncons_elementaires, eclate_reservation,
is_scolaire, is_tour_operator.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline.reservations_utils import (
    build_line_order_from_ml,
    eclate_reservation,
    get_troncons_elementaires,
    is_scolaire,
    is_tour_operator,
)


# ---------------------------------------------------------------------------
# Fixtures communes
# ---------------------------------------------------------------------------

#: Topologie complète ligne R35 sans GIL (H23/H24)
LINE_H23 = [
    "VV", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL",
    "BLON", "PRLZ", "TUS", "CHEV", "BCHX", "FAY", "OND", "LAL", "PLEI",
]

#: Topologie H22 avec GIL
LINE_H22 = [
    "VV", "GIL", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL",
    "BLON", "PRLZ", "TUS", "CHEV", "BCHX", "FAY", "OND", "LAL", "PLEI",
]

GARE_MAP_TEST = {
    "Vevey":       "VV",
    "Gilamont":    "GIL",
    "Les Pléiades":"PLEI",
    "Blonay":      "BLON",
}

def _dim_gare_h22() -> pd.DataFrame:
    """dim_gare simulé avec GIL (H22)."""
    rows = [
        ("VV",   0), ("GIL",  1), ("VVVI", 2), ("HTV",  4),
        ("CHTV", 5), ("STLE", 6), ("STLV", 7), ("CHIZ", 8),
        ("CHBL", 9), ("BLON",10), ("PRLZ",11), ("TUS", 12),
        ("CHEV",13), ("BCHX",14), ("FAY", 15), ("OND", 16),
        ("LAL", 17), ("PLEI",18),
    ]
    return pd.DataFrame(rows, columns=["abreviation", "ordre"])


def _dim_gare_h23() -> pd.DataFrame:
    """dim_gare simulé sans GIL (H23/H24)."""
    return _dim_gare_h22()[_dim_gare_h22().abreviation != "GIL"].reset_index(drop=True)


def _ml_annee(gares: list[str]) -> pd.DataFrame:
    """Simule un sous-ensemble ml_dataset avec ces gares."""
    rows = [{"id_gare_depart": g1, "id_gare_arrivee": g2}
            for g1, g2 in zip(gares, gares[1:])]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# build_line_order_from_ml
# ---------------------------------------------------------------------------

class TestBuildLineOrder:
    def test_h22_inclut_gil(self):
        """H22 : GIL présent dans ml → GIL dans la LINE_ORDER."""
        gares_h22 = LINE_H22
        df_ml = _ml_annee(gares_h22)
        result = build_line_order_from_ml(df_ml, _dim_gare_h22())
        assert "GIL" in result

    def test_h23_exclut_gil(self):
        """H23 : GIL absent de ml → GIL absent de la LINE_ORDER (test régression Cause E)."""
        gares_h23 = LINE_H23
        df_ml = _ml_annee(gares_h23)
        result = build_line_order_from_ml(df_ml, _dim_gare_h23())
        assert "GIL" not in result

    def test_ordre_preservé(self):
        """La séquence est triée par ordre croissant (bas → haut)."""
        df_ml = _ml_annee(LINE_H23)
        result = build_line_order_from_ml(df_ml, _dim_gare_h23())
        assert result[0] == "VV"
        assert result[-1] == "PLEI"

    def test_h23_longueur(self):
        """H23 sans GIL : 17 gares actives."""
        df_ml = _ml_annee(LINE_H23)
        result = build_line_order_from_ml(df_ml, _dim_gare_h23())
        assert len(result) == 17


# ---------------------------------------------------------------------------
# get_troncons_elementaires
# ---------------------------------------------------------------------------

class TestGetTroncons:
    def test_montant_vv_plei(self):
        """VV → PLEI (H23) : 16 tronçons élémentaires."""
        result = get_troncons_elementaires("VV", "PLEI", LINE_H23)
        assert result is not None
        assert len(result) == 16

    def test_descendant_plei_blon(self):
        """PLEI → BLON (descendant) : 8 tronçons."""
        result = get_troncons_elementaires("PLEI", "BLON", LINE_H23)
        assert result is not None
        assert len(result) == 8
        # Premier tronçon : PLEI → LAL
        assert result[0] == ("PLEI", "LAL")

    def test_meme_gare_retourne_liste_vide(self):
        """VV → VV : liste vide (pas de tronçons)."""
        result = get_troncons_elementaires("VV", "VV", LINE_H23)
        assert result == []

    def test_gare_inconnue_retourne_none(self):
        """Gare inconnue : retourne None (cas orphelin)."""
        result = get_troncons_elementaires("XYZ", "PLEI", LINE_H23)
        assert result is None

    def test_troncons_adjacents(self):
        """VV → VVVI : exactement 1 tronçon."""
        result = get_troncons_elementaires("VV", "VVVI", LINE_H23)
        assert result == [("VV", "VVVI")]

    def test_direction_sens_descendant_correct(self):
        """BLON → VV : premier tronçon BLON → CHBL."""
        result = get_troncons_elementaires("BLON", "VV", LINE_H23)
        assert result is not None
        assert result[0] == ("BLON", "CHBL")
        assert result[-1] == ("VVVI", "VV")

    def test_h22_avec_gil(self):
        """H22 VV → VVVI passe par GIL : 2 tronçons (VV→GIL, GIL→VVVI)."""
        result = get_troncons_elementaires("VV", "VVVI", LINE_H22)
        assert result == [("VV", "GIL"), ("GIL", "VVVI")]


# ---------------------------------------------------------------------------
# eclate_reservation
# ---------------------------------------------------------------------------

class TestEclateReservation:
    def _make_row(self, dep: str = "Vevey", arr: str = "Les Pléiades", pax: int = 20) -> pd.Series:
        return pd.Series({
            "gare_depart":    dep,
            "gare_arrivee":   arr,
            "pax_2c":         pax,
            "num_dossier":    42,
            "annee_horaire":  "H23",
        })

    def test_eclate_basique(self):
        """Vevey → Les Pléiades (H23) : 16 lignes enfants, pax_2c constant."""
        row = self._make_row("Vevey", "Les Pléiades", 30)
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        assert len(result) == 16
        assert all(r["pax_2c"] == 30 for r in result)
        assert all(not r.get("orphelin", False) for r in result)

    def test_pax_inchange_sur_troncons(self):
        """Le pax_2c est identique sur tous les tronçons enfants."""
        row = self._make_row("Vevey", "Blonay", 50)
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        pax_values = {r["pax_2c"] for r in result}
        assert pax_values == {50}

    def test_gare_non_mappee_retourne_orphelin(self):
        """Gare hors GARE_MAP → orphelin avec raison 'gare_non_reconnue'."""
        row = pd.Series({"gare_depart": "Zurich", "gare_arrivee": "Les Pléiades", "pax_2c": 10})
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        assert len(result) == 1
        assert result[0]["orphelin"] is True
        assert result[0]["raison"] == "gare_non_reconnue"

    def test_meme_gare_retourne_liste_vide(self):
        """Même gare départ = arrivée : liste vide (aucun tronçon)."""
        row = self._make_row("Vevey", "Vevey")
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        assert result == []

    def test_troncon_depart_arrivee_presents(self):
        """Chaque ligne enfant a troncon_depart et troncon_arrivee."""
        row = self._make_row("Vevey", "Blonay")
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        for r in result:
            assert "troncon_depart" in r
            assert "troncon_arrivee" in r

    def test_heritage_colonnes_parent(self):
        """Les colonnes parent (num_dossier, annee_horaire) sont héritées."""
        row = self._make_row()
        result = eclate_reservation(row, LINE_H23, GARE_MAP_TEST)
        for r in result:
            assert r["num_dossier"] == 42
            assert r["annee_horaire"] == "H23"


# ---------------------------------------------------------------------------
# is_scolaire
# ---------------------------------------------------------------------------

class TestIsScolaire:
    def test_keyword_uape(self):
        assert is_scolaire("UAPE Grand-Pré", "CFF SA") is True

    def test_keyword_ecole(self):
        assert is_scolaire("Ecole primaire Vevey", None) is True

    def test_keyword_classe(self):
        assert is_scolaire("Classe 6B Montreux", "MOB") is True

    def test_keyword_schule(self):
        assert is_scolaire("Primarschule Bern", "") is True

    def test_negatif(self):
        assert is_scolaire("Kuoni AG", "Kuoni SA") is False

    def test_none_safe(self):
        assert is_scolaire(None, None) is False

    def test_nan_safe(self):
        assert is_scolaire(float("nan"), float("nan")) is False

    def test_vide_safe(self):
        assert is_scolaire("", "") is False

    def test_case_insensitive(self):
        assert is_scolaire("ÉCOLE DU LAC", None) is True


# ---------------------------------------------------------------------------
# is_tour_operator
# ---------------------------------------------------------------------------

class TestIsTourOperator:
    def test_keyword_kuoni(self):
        assert is_tour_operator("Kuoni AG, Zürich") is True

    def test_keyword_ake(self):
        assert is_tour_operator("AKE-Eisenbahntouristik GmbH") is True

    def test_keyword_tui(self):
        assert is_tour_operator("TUI Deutschland") is True

    def test_negatif(self):
        assert is_tour_operator("CFF SA, Gare de Fribourg") is False

    def test_none_safe(self):
        assert is_tour_operator(None) is False

    def test_nan_safe(self):
        assert is_tour_operator(float("nan")) is False

    def test_case_insensitive(self):
        assert is_tour_operator("KUONI TRAVEL") is True
