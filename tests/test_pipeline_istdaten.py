"""
tests/test_pipeline_istdaten.py
================================
Tests de validation du pipeline ISTDATEN refondu.

Périmètre
---------
1. Convention de ponctualité (seuil 180s, valeur absolue) au grain tronçon
2. Logique J-2 : aucune feature ISTDATEN ne porte la valeur du jour J
3. Cohérence des correspondances Vevey (_in_ et _out_)
4. Jointure J-2 par train × jour et par tronçon

Les tests n'utilisent pas les données réelles (trop lentes à charger) mais
des DataFrames synthétiques reproduisant la structure des tables de fait.

Usage
-----
    pytest tests/test_pipeline_istdaten.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sources"))

from sources.build_dim_profil_train import (
    SEUIL_PONCTUALITE_SEC,
    _agreger_troncon_jour,
    _ajouter_service_id,
    _reconstruire_troncons,
)
from sources.build_dim_correspondances_vevey import (
    FENETRE_IN_AMONT_MIN,
    FENETRE_IN_AVAL_MIN,
    _calculer_correspondances_in,
)
from pipeline.add_istdaten_to_raw_stacked import _joindre_train_jour_j_moins_2

# bpuic fictifs : 1000=VV (km=0.0), 2000=GIL (km=1.21)
_KM = {1000: 0.0, 2000: 1.21}

BPUIC_VV = 1000
BPUIC_GIL = 2000

DATE_REF = pd.Timestamp("2023-01-15")  # dimanche → type 'dimanche_ferie'


def _arret_minimal(
    train: int,
    bpuic: int,
    nom: str,
    date: pd.Timestamp,
    retard_dep: float | None = 30.0,
    statut_dep: str = "REAL",
) -> dict:
    h = date + pd.Timedelta(hours=8)
    return {
        "date": date,
        "numero_train": train,
        "bpuic": bpuic,
        "haltestellen_name": nom,
        "horaire_depart": h,
        "horaire_arrivee": h - pd.Timedelta(minutes=2),
        "reel_depart": h + pd.Timedelta(seconds=retard_dep or 0),
        "reel_arrivee": pd.NaT,
        "statut_depart": statut_dep,
        "statut_arrivee": "UNBEKANNT",
        "retard_depart_sec": retard_dep,
        "retard_arrivee_sec": None,
        "is_annule": False,
        "is_supplementaire": False,
    }


@pytest.fixture
def fact_istdaten_minimal() -> pd.DataFrame:
    """Table de fait ISTDATEN minimale : 2 trains × 2 arrêts sur 10 jours."""
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    rows = []
    for d in dates:
        for train, retard in [(100, 30.0), (200, -60.0)]:
            rows.append(_arret_minimal(train, BPUIC_VV, "VV", d, retard_dep=retard))
            rows.append(_arret_minimal(train, BPUIC_GIL, "GIL", d, retard_dep=retard))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests — convention ponctualité (seuil 180s, valeur absolue)
# ---------------------------------------------------------------------------


class TestConventionPonctualite:
    def _troncon_avec_retard(self, retard_sec: float) -> pd.DataFrame:
        """Retourne agg tronçon avec un seul train ayant retard_dep_troncon_sec donné.

        VV part à 8h00 (h_dep=480 min depuis minuit) et GIL à 8h12.
        Les horaires distincts garantissent l'ordre de tri correct.
        """
        base = DATE_REF
        h_vv = base + pd.Timedelta(hours=8)
        h_gil = base + pd.Timedelta(hours=8, minutes=12)
        df_fact = pd.DataFrame([
            {
                "date": base,
                "numero_train": 100,
                "bpuic": BPUIC_VV,
                "haltestellen_name": "VV",
                "horaire_depart": h_vv,
                "horaire_arrivee": h_vv - pd.Timedelta(minutes=2),
                "reel_depart": h_vv + pd.Timedelta(seconds=retard_sec),
                "reel_arrivee": pd.NaT,
                "statut_depart": "REAL",
                "statut_arrivee": "UNBEKANNT",
                "retard_depart_sec": retard_sec,
                "retard_arrivee_sec": None,
                "is_annule": False,
                "is_supplementaire": False,
            },
            {
                "date": base,
                "numero_train": 100,
                "bpuic": BPUIC_GIL,
                "haltestellen_name": "GIL",
                "horaire_depart": h_gil,
                "horaire_arrivee": h_gil - pd.Timedelta(minutes=2),
                "reel_depart": h_gil,
                "reel_arrivee": pd.NaT,
                "statut_depart": "REAL",
                "statut_arrivee": "UNBEKANNT",
                "retard_depart_sec": 0.0,
                "retard_arrivee_sec": None,
                "is_annule": False,
                "is_supplementaire": False,
            },
        ])
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        return _agreger_troncon_jour(troncons)

    def test_seuil_ponctualite_est_180s(self) -> None:
        """Le seuil de ponctualité doit être de 180 secondes."""
        assert SEUIL_PONCTUALITE_SEC == 180

    def test_retard_sous_seuil_non_en_retard(self) -> None:
        """Retard de 60s < 180s → is_en_retard_dep = 0."""
        agg = self._troncon_avec_retard(60.0)
        assert agg["is_en_retard_dep"].iloc[0] == 0.0

    def test_retard_au_seuil_en_retard(self) -> None:
        """Retard de 180s = seuil → is_en_retard_dep = 1."""
        agg = self._troncon_avec_retard(180.0)
        assert agg["is_en_retard_dep"].iloc[0] == 1.0

    def test_retard_dessus_seuil_en_retard(self) -> None:
        """Retard de 300s > 180s → is_en_retard_dep = 1."""
        agg = self._troncon_avec_retard(300.0)
        assert agg["is_en_retard_dep"].iloc[0] == 1.0

    def test_depart_en_avance_non_en_retard(self) -> None:
        """Retard négatif (-600s) → is_en_retard_dep = 0 (les avances ne sont pas des retards)."""
        agg = self._troncon_avec_retard(-600.0)
        assert agg["is_en_retard_dep"].iloc[0] == 0.0


# ---------------------------------------------------------------------------
# Tests — logique J-2 (pas de leakage)
# ---------------------------------------------------------------------------


class TestLogiqueJMoins2:
    def test_jointure_decale_de_deux_jours(self) -> None:
        """La jointure APC ← ISTDATEN par train × jour décale de +2 jours (J-2)."""
        base_date = pd.Timestamp("2023-06-15")
        df_apc = pd.DataFrame([{
            "base_date": base_date,
            "horaire_numero_train": 100,
            "autre_col": "x",
        }])

        df_ist_j_moins_2 = pd.DataFrame([{
            "date": pd.Timestamp("2023-06-13"),
            "numero_train": 100,
            "ist_feature": 42.0,
        }])
        df_ist_j_moins_1 = pd.DataFrame([{
            "date": pd.Timestamp("2023-06-14"),
            "numero_train": 100,
            "ist_feature": 99.0,
        }])

        # J-2 doit matcher
        result_j2 = _joindre_train_jour_j_moins_2(df_apc, df_ist_j_moins_2)
        assert result_j2["ist_feature"].iloc[0] == 42.0, (
            "La jointure doit utiliser J-2 (date + 2 jours = base_date)"
        )

        # J-1 ne doit PAS matcher
        result_j1 = _joindre_train_jour_j_moins_2(df_apc, df_ist_j_moins_1)
        assert result_j1["ist_feature"].isna().all(), (
            "La jointure ne doit pas utiliser J-1 (leakage opérationnel)"
        )

    def test_jointure_ne_modifie_pas_le_nombre_de_lignes(self) -> None:
        """La jointure J-2 par train × jour est many_to_one : pas de doublons."""
        base_date = pd.Timestamp("2023-06-15")
        df_apc = pd.DataFrame([
            {"base_date": base_date, "horaire_numero_train": 100},
            {"base_date": base_date, "horaire_numero_train": 200},
        ])
        df_ist = pd.DataFrame([
            {"date": pd.Timestamp("2023-06-13"), "numero_train": 100, "ist_feature": 1.0},
            {"date": pd.Timestamp("2023-06-13"), "numero_train": 200, "ist_feature": 2.0},
        ])
        result = _joindre_train_jour_j_moins_2(df_apc, df_ist)
        assert len(result) == len(df_apc)


# ---------------------------------------------------------------------------
# Tests — correspondances Vevey (_in_)
# ---------------------------------------------------------------------------


def _make_trains_vevey_in(date: pd.Timestamp) -> pd.DataFrame:
    """Trains R35 partant de Vevey à 9h et 10h."""
    return pd.DataFrame([
        {
            "date": date,
            "numero_train": 100,
            "ist_service_id": "100_09h00",
            "horaire_depart": date + pd.Timedelta(hours=9),
            "reel_depart": pd.NaT,
            "statut_depart": "UNBEKANNT",
        },
        {
            "date": date,
            "numero_train": 200,
            "ist_service_id": "200_10h00",
            "horaire_depart": date + pd.Timedelta(hours=10),
            "reel_depart": pd.NaT,
            "statut_depart": "UNBEKANNT",
        },
    ])


def _make_feeder(
    date: pd.Timestamp,
    h_min: int,
    retard_sec: float | None = 0.0,
) -> pd.DataFrame:
    arr = date + pd.Timedelta(minutes=h_min)
    reel = arr + pd.Timedelta(seconds=retard_sec) if retard_sec is not None else pd.NaT
    return pd.DataFrame([{
        "date": date,
        "horaire_arrivee_feeder": arr,
        "reel_arrivee_feeder": reel,
        "retard_feeder_sec": retard_sec,
    }])


class TestCorrespondancesVeveyIn:
    def test_feeder_dans_fenetre_est_compte(self) -> None:
        """Un feeder arrivant 3 min avant le départ est dans la fenêtre [1, 5]."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        # Train 100 à 9h, feeder à 8h57 → délai = 3 min → dans [1, 5]
        feeders = _make_feeder(date, h_min=9 * 60 - 3, retard_sec=0.0)

        result = _calculer_correspondances_in(trains, feeders)
        t100 = result[result["numero_train"] == 100]

        assert t100["ist_corresp_in_n_theoriques_j"].iloc[0] == 1
        assert t100["ist_corresp_in_n_garanties_j"].iloc[0] == 1

    def test_feeder_hors_fenetre_25min_avant(self) -> None:
        """Un feeder à 25 min avant (> 5 min) est hors fenêtre théorique."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        feeders = _make_feeder(date, h_min=9 * 60 - 25, retard_sec=0.0)

        result = _calculer_correspondances_in(trains, feeders)
        t100 = result[result["numero_train"] == 100]
        assert t100["ist_corresp_in_n_theoriques_j"].iloc[0] == 0

    def test_feeder_hors_fenetre_0min_avant(self) -> None:
        """Un feeder arrivant au moment du départ (délai = 0 min < 1 min) est hors fenêtre."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        feeders = _make_feeder(date, h_min=9 * 60, retard_sec=0.0)

        result = _calculer_correspondances_in(trains, feeders)
        t100 = result[result["numero_train"] == 100]
        assert t100["ist_corresp_in_n_theoriques_j"].iloc[0] == 0

    def test_feeder_hors_fenetre_effectif_non_garantie(self) -> None:
        """Un feeder théoriquement dans la fenêtre mais dont l'arrivée effective est hors fenêtre n'est pas garanti."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        # Feeder à 3 min (théorique) mais retard 600s → arrive à +10 min → hors fenêtre effective
        feeders = _make_feeder(date, h_min=9 * 60 - 3, retard_sec=600.0)

        result = _calculer_correspondances_in(trains, feeders)
        t100 = result[result["numero_train"] == 100]
        assert t100["ist_corresp_in_n_theoriques_j"].iloc[0] == 1
        assert t100["ist_corresp_in_n_garanties_j"].iloc[0] == 0

    def test_sans_feeder_comptages_zero(self) -> None:
        """Sans feeder, n_theoriques et n_garanties valent 0 (pas NaN)."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        feeders = pd.DataFrame(
            columns=["date", "horaire_arrivee_feeder", "reel_arrivee_feeder", "retard_feeder_sec"]
        )
        result = _calculer_correspondances_in(trains, feeders)
        assert (result["ist_corresp_in_n_theoriques_j"] == 0).all()
        assert (result["ist_corresp_in_n_garanties_j"] == 0).all()

    def test_taux_garantie_borne_0_1(self) -> None:
        """Le taux de garantie _in_ est toujours dans [0, 1]."""
        date = pd.Timestamp("2023-06-01")
        trains = _make_trains_vevey_in(date)
        # Feeder 1 : 3 min avant, à l'heure → garantie
        # Feeder 2 : 2 min avant, retard 300s → arrive après le départ → non garantie
        feeders = pd.concat([
            _make_feeder(date, h_min=9 * 60 - 3, retard_sec=0.0),
            _make_feeder(date, h_min=9 * 60 - 2, retard_sec=300.0),
        ])
        result = _calculer_correspondances_in(trains, feeders)
        taux = result["ist_corresp_in_pct_garanties_j"].dropna()
        assert (taux >= 0).all() and (taux <= 1).all()

    def test_fenetre_constantes(self) -> None:
        """Les constantes de fenêtre _in_ correspondent aux valeurs validées."""
        assert FENETRE_IN_AMONT_MIN == 5
        assert FENETRE_IN_AVAL_MIN == 1
