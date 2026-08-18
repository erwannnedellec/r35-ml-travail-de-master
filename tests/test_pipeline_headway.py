"""
tests/test_pipeline_headway.py
================================
Tests de validation du calcul de headway ISTDATEN par tronçon × sens.

Aligné sur le comportement courant (ADR-067, dataset ba493568) :
- Headway calculé sur la GRILLE PLANIFIÉE connue à J-1 : seul ``horaire_depart``
  (théorique) est utilisé. Aucun usage de ``reel_depart`` ni du statut réalisé.
- Aucun filtre de statut : les trains annulés (``is_annule=True``) et les
  suppléments (``is_supplementaire=True``) sont INCLUS — ils font partie de la
  grille connue à J-1.
- Premier / dernier train du jour sur un tronçon × sens : headway = NaN, et le
  flag ``ist_headway_{avant_is_first,apres_is_last}_of_day`` vaut 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sources.build_dim_headway import (
    _calculer_headway,
    _reconstruire_troncons,
)

# bpuic fictifs pour les tests : 1000=VV (km=0.0), 2000=GIL (km=1.21)
_KM = {1000: 0.0, 2000: 1.21}


def _arret(
    train: int,
    bpuic: int,
    nom: str,
    h_dep_min: int,
    *,
    annule: bool = False,
    supp: bool = False,
    date: pd.Timestamp = pd.Timestamp("2023-06-01"),
) -> dict:
    """Un arrêt ISTDATEN minimal (grille planifiée : seul horaire_depart compte)."""
    return {
        "date": date,
        "numero_train": train,
        "bpuic": bpuic,
        "haltestellen_name": nom,
        "horaire_depart": date + pd.Timedelta(minutes=h_dep_min),
        "is_annule": annule,
        "is_supplementaire": supp,
    }


def _make_istdaten_minimal() -> pd.DataFrame:
    """3 trains VV→GIL + 1 train GIL→VV sur la même date."""
    return pd.DataFrame([
        _arret(100, 1000, "VV",  420),   # 07:00 VV
        _arret(100, 2000, "GIL", 430),   # 07:10 GIL
        _arret(200, 1000, "VV",  435),   # 07:15 VV
        _arret(200, 2000, "GIL", 445),   # 07:25 GIL
        _arret(300, 1000, "VV",  465),   # 07:45 VV
        _arret(300, 2000, "GIL", 475),   # 07:55 GIL
        _arret(1421, 2000, "GIL", 440),  # 07:20 GIL (sens inverse)
        _arret(1421, 1000, "VV",  450),  # 07:30 VV
    ])


def _pipeline(df: pd.DataFrame) -> pd.DataFrame:
    troncons = _reconstruire_troncons(df, _KM)
    return _calculer_headway(troncons)


class TestHeadwayDouble:
    def test_premier_train_nan_et_flag_avant(self) -> None:
        """Premier train du jour sur un tronçon : avant=NaN, flag first=1."""
        result = _pipeline(_make_istdaten_minimal())
        t = result[(result["numero_train"] == 100) & (result["sens"] == "VV -> PLEI")]
        assert np.isnan(t["ist_headway_avant_min"].iloc[0])
        assert t["ist_headway_avant_is_first_of_day"].iloc[0] == 1

    def test_dernier_train_nan_et_flag_apres(self) -> None:
        """Dernier train du jour sur un tronçon : apres=NaN, flag last=1."""
        result = _pipeline(_make_istdaten_minimal())
        t = result[(result["numero_train"] == 300) & (result["sens"] == "VV -> PLEI")]
        assert np.isnan(t["ist_headway_apres_min"].iloc[0])
        assert t["ist_headway_apres_is_last_of_day"].iloc[0] == 1

    def test_train_milieu_journee_deux_valeurs(self) -> None:
        """Train 200 entre 100 (07:00) et 300 (07:45) : avant=15, apres=30."""
        result = _pipeline(_make_istdaten_minimal())
        t = result[(result["numero_train"] == 200) & (result["sens"] == "VV -> PLEI")]
        assert t["ist_headway_avant_min"].iloc[0] == 15.0
        assert t["ist_headway_apres_min"].iloc[0] == 30.0
        # Train du milieu : ni premier ni dernier
        assert t["ist_headway_avant_is_first_of_day"].iloc[0] == 0
        assert t["ist_headway_apres_is_last_of_day"].iloc[0] == 0

    def test_sens_independants(self) -> None:
        """Train PLEI→VV seul dans son sens : avant=NaN et apres=NaN, flags=1."""
        result = _pipeline(_make_istdaten_minimal())
        t = result[result["numero_train"] == 1421]
        assert np.isnan(t["ist_headway_avant_min"].iloc[0])
        assert np.isnan(t["ist_headway_apres_min"].iloc[0])
        assert t["ist_headway_avant_is_first_of_day"].iloc[0] == 1
        assert t["ist_headway_apres_is_last_of_day"].iloc[0] == 1

    def test_train_annule_inclus(self) -> None:
        """ADR-067 : un train annulé fait partie de la grille planifiée → INCLUS.

        L'annulation n'est pas connue à J-1 ; le train annulé compte comme
        prédécesseur. 200 doit donc avoir avant=10 (depuis l'annulé à 07:05),
        et non 15 (depuis 100 à 07:00)."""
        df = _make_istdaten_minimal().copy()
        annule = pd.DataFrame([
            _arret(150, 1000, "VV",  425, annule=True),  # 07:05, annulé
            _arret(150, 2000, "GIL", 435, annule=True),
        ])
        df = pd.concat([df, annule], ignore_index=True)
        result = _pipeline(df)
        t = result[(result["numero_train"] == 200) & (result["sens"] == "VV -> PLEI")]
        assert t["ist_headway_avant_min"].iloc[0] == 10.0

    def test_train_supplementaire_inclus(self) -> None:
        """ADR-067 : un supplément (planifié en amont) compte normalement."""
        df = _make_istdaten_minimal().copy()
        supp = pd.DataFrame([
            _arret(400, 1000, "VV",  480, supp=True),  # 08:00, supplémentaire
            _arret(400, 2000, "GIL", 490, supp=True),
        ])
        df = pd.concat([df, supp], ignore_index=True)
        result = _pipeline(df)
        t = result[(result["numero_train"] == 400) & (result["sens"] == "VV -> PLEI")]
        # avant = 480 - 465 = 15 min (depuis train 300 à 07:45)
        assert t["ist_headway_avant_min"].iloc[0] == 15.0
        # 400 devient le dernier train du jour sur ce tronçon
        assert np.isnan(t["ist_headway_apres_min"].iloc[0])
        assert t["ist_headway_apres_is_last_of_day"].iloc[0] == 1

    def test_horaire_theorique_uniquement(self) -> None:
        """Seul horaire_depart compte : reel_depart n'existe pas / n'est pas lu.

        Deux trains à 07:00 et 07:20 (théorique) → headway = 20 min, quels que
        soient les retards réels (non disponibles à J-1)."""
        df = pd.DataFrame([
            _arret(10, 1000, "VV",  420),  # 07:00
            _arret(10, 2000, "GIL", 430),
            _arret(20, 1000, "VV",  440),  # 07:20
            _arret(20, 2000, "GIL", 450),
        ])
        result = _pipeline(df)
        t = result[(result["numero_train"] == 20) & (result["sens"] == "VV -> PLEI")]
        assert t["ist_headway_avant_min"].iloc[0] == 20.0

    def test_grain_output_correct(self) -> None:
        """L'output contient les 11 colonnes attendues (dont les 2 flags)."""
        result = _pipeline(_make_istdaten_minimal())
        expected = {
            "date", "numero_train",
            "gare_depart_bpuic", "gare_depart",
            "gare_arrivee_bpuic", "gare_arrivee",
            "sens",
            "ist_headway_avant_min", "ist_headway_apres_min",
            "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day",
        }
        assert set(result.columns) == expected
        # 3 tronçons VV→GIL + 1 tronçon GIL→VV
        assert len(result) == 4

    def test_headway_non_negatif(self) -> None:
        """Aucun headway observé (hors NaN) ne doit être négatif."""
        result = _pipeline(_make_istdaten_minimal())
        for col in ["ist_headway_avant_min", "ist_headway_apres_min"]:
            observe = result.loc[result[col].notna(), col]
            assert (observe >= 0).all()

    def test_coherence_nan_flag(self) -> None:
        """NaN ⟺ flag=1 sur chaque paire (valeur, flag)."""
        result = _pipeline(_make_istdaten_minimal())
        for col, flag in [
            ("ist_headway_avant_min", "ist_headway_avant_is_first_of_day"),
            ("ist_headway_apres_min", "ist_headway_apres_is_last_of_day"),
        ]:
            assert (result[col].isna() == (result[flag] == 1)).all()
