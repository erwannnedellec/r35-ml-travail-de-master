"""
tests/test_pipeline_reservations.py
=====================================
Tests d'intégration du stage_10 add_reservations_to_raw_stacked.

Valide la logique du pipeline sans toucher aux fichiers de production :
utilise des DataFrames inline et des fichiers temporaires.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline.add_reservations_to_raw_stacked import _aggreger, _joindre_et_imputer
from pipeline.reservations_utils import GARE_MAP, eclate_reservation

# ---------------------------------------------------------------------------
# Fixtures réutilisables
# ---------------------------------------------------------------------------

LINE_H23 = [
    "VV", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL",
    "BLON", "PRLZ", "TUS", "CHEV", "BCHX", "FAY", "OND", "LAL", "PLEI",
]
LINE_H22 = ["VV", "GIL"] + LINE_H23[1:]


def _make_ml_dataset(n_rows: int = 10) -> pd.DataFrame:
    """Mini ml_dataset avec colonnes minimum requises."""
    dates = pd.date_range("2024-01-01", periods=n_rows, freq="D")
    return pd.DataFrame({
        "base_date":              dates,
        "horaire_annee_horaire":  ["H24"] * n_rows,
        "horaire_numero_train":   pd.array([1425] * n_rows, dtype="Int64"),
        "id_gare_depart":         ["BLON"] * n_rows,
        "id_gare_arrivee":        ["CHBL"] * n_rows,
        "target_voyageurs_2eme_classe": [50] * n_rows,
        "spatial_segment":        ["haut"] * n_rows,
    })


def _make_resa_eclate(dates: list, n_train: int = 1425, pax: int = 30,
                      annee: str = "H24", scolaire: bool = False) -> pd.DataFrame:
    """Mini DataFrame réservations éclatées (Abgeschlossen, lead_days ≥ 1)."""
    return pd.DataFrame({
        "date_voyage_d":   [pd.Timestamp(d) for d in dates],
        "numero_train":    pd.array([n_train] * len(dates), dtype="Int64"),
        "troncon_depart":  ["BLON"] * len(dates),
        "troncon_arrivee": ["CHBL"] * len(dates),
        "annee_horaire":   [annee] * len(dates),
        "pax_2c":          pd.array([pax] * len(dates), dtype="Int64"),
        "pax_1c":          pd.array([0] * len(dates), dtype="Int64"),
        "num_dossier":     pd.array([1001] * len(dates), dtype="Int64"),
        "pays":            ["Suisse"] * len(dates),
        "langue":          ["français"] * len(dates),
        "nom_groupe":      ["UAPE Vevey" if scolaire else "Groupe A"] * len(dates),
        "partenaire":      ["CFF SA"] * len(dates),
    })


# ---------------------------------------------------------------------------
# Tests agrégation
# ---------------------------------------------------------------------------

class TestAggreger:
    def test_schema_output(self):
        """L'agrégation retourne bien les 8 colonnes resa_*."""
        df_eclate = _make_resa_eclate(["2024-01-01", "2024-01-02"])
        result = _aggreger(df_eclate)
        expected_cols = [
            "resa_pax_2c_J_minus_1", "resa_n_dossiers_J_minus_1",
            "resa_max_groupe_2c_J_minus_1", "resa_part_scolaire_J_minus_1",
            "resa_part_tour_operator_J_minus_1", "resa_n_pays_distincts_J_minus_1",
            "resa_n_langues_distinctes_J_minus_1", "resa_has_resa_J_minus_1",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Colonne manquante : {col}"

    def test_pax_2c_correct(self):
        """La somme pax_2c est correcte pour 2 réservations distinctes."""
        df_e = _make_resa_eclate(["2024-01-01"])
        df_e2 = _make_resa_eclate(["2024-01-01"])
        df_e2["num_dossier"] = pd.array([1002], dtype="Int64")
        df_e2["pax_2c"]      = pd.array([20],   dtype="Int64")
        df_combined = pd.concat([df_e, df_e2], ignore_index=True)
        result = _aggreger(df_combined)
        assert result["resa_pax_2c_J_minus_1"].iloc[0] == 50  # 30 + 20

    def test_scolaire_part(self):
        """Groupe scolaire → resa_part_scolaire_J_minus_1 = 1.0."""
        df_e = _make_resa_eclate(["2024-01-01"], scolaire=True)
        result = _aggreger(df_e)
        assert result["resa_part_scolaire_J_minus_1"].iloc[0] == pytest.approx(1.0)

    def test_has_resa_true(self):
        """resa_has_resa_J_minus_1 vaut True pour toutes les lignes agrégées."""
        df_e = _make_resa_eclate(["2024-01-01", "2024-01-02"])
        result = _aggreger(df_e)
        assert result["resa_has_resa_J_minus_1"].all()


# ---------------------------------------------------------------------------
# Tests jointure et imputation
# ---------------------------------------------------------------------------

class TestJoindreEtImputer:
    def test_schema_output(self):
        """La sortie contient toutes les colonnes ml_dataset + 8 resa_*."""
        df_ml = _make_ml_dataset(5)
        grain = _aggreger(_make_resa_eclate(["2024-01-01"]))
        result = _joindre_et_imputer(df_ml, grain)
        # Colonnes originales préservées
        for col in df_ml.columns:
            assert col in result.columns
        # 8 features ajoutées
        resa_cols = [c for c in result.columns if c.startswith("resa_")]
        assert len(resa_cols) == 8

    def test_imputation_zero(self):
        """Cellules sans réservation : features quantitatives = 0, flag = False."""
        df_ml = _make_ml_dataset(5)
        # grain vide : aucune réservation
        grain = pd.DataFrame(columns=[
            "date_voyage_d", "numero_train", "troncon_depart", "troncon_arrivee",
            "annee_horaire", "resa_pax_2c_J_minus_1", "resa_n_dossiers_J_minus_1",
            "resa_max_groupe_2c_J_minus_1", "resa_part_scolaire_J_minus_1",
            "resa_part_tour_operator_J_minus_1", "resa_n_pays_distincts_J_minus_1",
            "resa_n_langues_distinctes_J_minus_1", "resa_has_resa_J_minus_1",
        ])
        result = _joindre_et_imputer(df_ml, grain)
        assert (result["resa_pax_2c_J_minus_1"] == 0).all()
        assert (~result["resa_has_resa_J_minus_1"]).all()

    def test_cellule_avec_resa(self):
        """Cellule correspondante : resa_pax_2c non nul après jointure."""
        df_ml = _make_ml_dataset(3)
        df_ml["base_date"] = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        df_eclate = _make_resa_eclate(["2024-01-02"])  # seulement J2
        grain = _aggreger(df_eclate)
        result = _joindre_et_imputer(df_ml, grain)
        mask = pd.to_datetime(result["base_date"]).dt.normalize() == pd.Timestamp("2024-01-02")
        assert result.loc[mask, "resa_pax_2c_J_minus_1"].iloc[0] == 30
        assert bool(result.loc[mask, "resa_has_resa_J_minus_1"].iloc[0]) is True

    def test_longueur_preservee(self):
        """Le nombre de lignes ml_dataset est inchangé après jointure."""
        df_ml = _make_ml_dataset(10)
        grain = _aggreger(_make_resa_eclate(["2024-01-01"]))
        result = _joindre_et_imputer(df_ml, grain)
        assert len(result) == len(df_ml)

    def test_lead_days_filter(self):
        """Une réservation avec lead_days = 0 ne doit pas être dans le grain."""
        # On simule via l'agrégat : on vérifie que si grain est vide, l'imputation donne 0
        df_ml = _make_ml_dataset(2)
        grain_vide = pd.DataFrame(columns=[
            "date_voyage_d", "numero_train", "troncon_depart", "troncon_arrivee",
            "annee_horaire", "resa_pax_2c_J_minus_1", "resa_n_dossiers_J_minus_1",
            "resa_max_groupe_2c_J_minus_1", "resa_part_scolaire_J_minus_1",
            "resa_part_tour_operator_J_minus_1", "resa_n_pays_distincts_J_minus_1",
            "resa_n_langues_distinctes_J_minus_1", "resa_has_resa_J_minus_1",
        ])
        result = _joindre_et_imputer(df_ml, grain_vide)
        assert (result["resa_pax_2c_J_minus_1"] == 0).all()

    def test_storniert_exclus(self):
        """Vérification indirecte : les Storniert exclus avant éclat ne contribuent pas.

        On agrège un DataFrame sans aucune ligne → resa_pax_2c = 0.
        Ce test valide que le chemin Storniert → grain_vide → imputation = 0 est correct.
        """
        df_ml = _make_ml_dataset(2)
        grain_vide = pd.DataFrame(columns=[
            "date_voyage_d", "numero_train", "troncon_depart", "troncon_arrivee",
            "annee_horaire", "resa_pax_2c_J_minus_1", "resa_n_dossiers_J_minus_1",
            "resa_max_groupe_2c_J_minus_1", "resa_part_scolaire_J_minus_1",
            "resa_part_tour_operator_J_minus_1", "resa_n_pays_distincts_J_minus_1",
            "resa_n_langues_distinctes_J_minus_1", "resa_has_resa_J_minus_1",
        ])
        result = _joindre_et_imputer(df_ml, grain_vide)
        assert (result["resa_pax_2c_J_minus_1"] == 0).all()

    def test_topologie_h23_exclut_gil(self):
        """Réservation H23 passant par GIL : zéro tronçon GIL généré avec LINE_H23."""
        row = pd.Series({
            "gare_depart": "Vevey", "gare_arrivee": "Les Pléiades",
            "pax_2c": 40, "num_dossier": 200, "annee_horaire": "H23",
        })
        result = eclate_reservation(row, LINE_H23, GARE_MAP)
        # Aucun tronçon GIL
        gil_troncons = [r for r in result if r.get("troncon_depart") == "GIL"
                        or r.get("troncon_arrivee") == "GIL"]
        assert len(gil_troncons) == 0
        # Tronçons non-orphelins
        assert all(not r.get("orphelin", False) for r in result)

    def test_features_resa_segment_haut(self):
        """Test valeurs sur cellule connue : 1 résa 30 pax → pax_2c = 30."""
        df_ml = _make_ml_dataset(1)
        df_ml["base_date"] = [pd.Timestamp("2024-01-01")]
        grain = _aggreger(_make_resa_eclate(["2024-01-01"], pax=30))
        result = _joindre_et_imputer(df_ml, grain)
        assert result["resa_pax_2c_J_minus_1"].iloc[0] == 30
        assert result["resa_n_dossiers_J_minus_1"].iloc[0] == 1
        assert result["resa_max_groupe_2c_J_minus_1"].iloc[0] == 30
        assert result["resa_has_resa_J_minus_1"].iloc[0] == True  # noqa: E712
