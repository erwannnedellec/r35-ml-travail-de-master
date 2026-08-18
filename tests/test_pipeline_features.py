"""
tests/test_pipeline_features.py
================================
Tests de validation de _ajouter_service_id_complet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline.add_features_to_raw_stacked import _ajouter_service_id_complet


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestServiceIdComplet:
    def test_identifiant_stable_par_train_jour(self):
        """Tous les tronçons d'un même train-jour reçoivent le même service_id."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:12:00"),
                "troncon": "VV-GIL",
            },
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:25:00"),
                "troncon": "GIL-CHTV",
            },
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:40:00"),
                "troncon": "CHTV-LCHV",
            },
        ])
        result = _ajouter_service_id_complet(df)
        assert result["horaire_service_id_complet"].nunique() == 1
        assert result["horaire_service_id_complet"].iloc[0] == "1308_07h12"

    def test_format_attendu(self):
        """L'identifiant suit le format {numero}_{HH}h{MM}."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:09:00"),
            },
        ])
        result = _ajouter_service_id_complet(df)
        sid = result["horaire_service_id_complet"].iloc[0]
        assert sid == "1308_07h09"
        # format général : "digits_HHhMM"
        import re
        assert re.match(r"^\d+_\d{2}h\d{2}$", sid), f"Format inattendu : {sid!r}"

    def test_fallback_NA_si_origine_manquante(self):
        """Train sans datetime valide reçoit l'identifiant {numero}_NA."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 9999,
                "base_depart_datetime": pd.NaT,
            },
        ])
        result = _ajouter_service_id_complet(df)
        assert result["horaire_service_id_complet"].iloc[0] == "9999_NA"

    def test_trains_distincts_meme_jour(self):
        """Deux trains différents le même jour produisent des identifiants distincts."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:12:00"),
            },
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1310,
                "base_depart_datetime": pd.Timestamp("2024-01-10 08:12:00"),
            },
        ])
        result = _ajouter_service_id_complet(df)
        assert result["horaire_service_id_complet"].nunique() == 2
        assert "1308_07h12" in result["horaire_service_id_complet"].values
        assert "1310_08h12" in result["horaire_service_id_complet"].values

    def test_meme_numero_jours_differents(self):
        """Le même train le même horaire sur deux jours produit le même identifiant."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:12:00"),
            },
            {
                "base_date": pd.Timestamp("2024-01-11"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-11 07:12:00"),
            },
        ])
        result = _ajouter_service_id_complet(df)
        assert result["horaire_service_id_complet"].nunique() == 1
        assert result["horaire_service_id_complet"].iloc[0] == "1308_07h12"

    def test_longueur_preservee(self):
        """Le merge ne crée pas ni ne supprime de lignes."""
        df = _make_df([
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:12:00"),
            },
            {
                "base_date": pd.Timestamp("2024-01-10"),
                "horaire_numero_train": 1308,
                "base_depart_datetime": pd.Timestamp("2024-01-10 07:25:00"),
            },
        ])
        result = _ajouter_service_id_complet(df)
        assert len(result) == len(df)
