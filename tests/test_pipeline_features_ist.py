"""
tests/test_pipeline_features_ist.py
=====================================
Tests de validation des features ISTDATEN refondues.

Couvre :
  - _rolling_par_type_jour : filtrage par type de jour, lag J-2
  - build_dim_profil_train : grain tronçon, rolling par type de jour
  - build_dim_correspondances_vevey : fenêtres in/out, propagation
  - cal_type_jour_3classes : mapping depuis is_ferie_vaud + jour_semaine_iso
  - Absence de chevauchement cross-horaire via service_id
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sources"))

from _rolling_par_type_jour import rolling_par_type_jour
from sources.build_dim_profil_train import (
    SEUIL_PONCTUALITE_SEC,
    _agreger_troncon_jour,
    _reconstruire_troncons,
    _ajouter_service_id,
)
from sources.build_dim_correspondances_vevey import (
    BPUIC_VEVEY,
    FENETRE_IN_AMONT_MIN,
    FENETRE_IN_AVAL_MIN,
    FENETRE_OUT_AMONT_MIN,
    FENETRE_OUT_AVAL_MIN,
    _calculer_correspondances_in,
    _calculer_correspondances_out,
    _r35_partant_vevey,
    _r35_arrivant_vevey,
)

# bpuic fictifs : 1000=VV (km=0.0), 2000=GIL (km=1.21), 3000=CHTV (km=4.50)
_KM = {1000: 0.0, 2000: 1.21, 3000: 4.50}

DATE_A = pd.Timestamp("2024-01-08")  # lundi = ouvrable
DATE_B = pd.Timestamp("2024-01-09")  # mardi = ouvrable
DATE_C = pd.Timestamp("2024-01-13")  # samedi
DATE_D = pd.Timestamp("2024-01-14")  # dimanche

BPUIC_VV = 1000
BPUIC_GIL = 2000
BPUIC_CHTV = 3000


# ===========================================================================
# Utilitaires de construction des fixtures
# ===========================================================================


def _arret(
    train: int,
    bpuic: int,
    nom: str,
    h_dep_min: int,
    *,
    statut_dep: str = "UNBEKANNT",
    statut_arr: str = "UNBEKANNT",
    reel_dep_min: int | None = None,
    reel_arr_min: int | None = None,
    retard_dep: float | None = None,
    retard_arr: float | None = None,
    annule: bool = False,
    date: pd.Timestamp = DATE_A,
) -> dict:
    base = date
    h_dep = base + pd.Timedelta(minutes=h_dep_min)
    r_dep = base + pd.Timedelta(minutes=reel_dep_min) if reel_dep_min is not None else pd.NaT
    r_arr = base + pd.Timedelta(minutes=reel_arr_min) if reel_arr_min is not None else pd.NaT
    return {
        "date": date,
        "numero_train": train,
        "bpuic": bpuic,
        "haltestellen_name": nom,
        "horaire_depart": h_dep,
        "horaire_arrivee": h_dep - pd.Timedelta(minutes=2),
        "reel_depart": r_dep,
        "reel_arrivee": r_arr,
        "statut_depart": statut_dep,
        "statut_arrivee": statut_arr,
        "retard_depart_sec": retard_dep,
        "retard_arrivee_sec": retard_arr,
        "is_annule": annule,
        "is_supplementaire": False,
    }


def _make_istdaten_2trains() -> pd.DataFrame:
    """Deux trains VV→GIL sur DATE_A."""
    return pd.DataFrame([
        _arret(100, BPUIC_VV,  "VV",  420, retard_dep=60.0,  retard_arr=None,  statut_dep="REAL"),
        _arret(100, BPUIC_GIL, "GIL", 432, retard_dep=120.0, retard_arr=90.0,  statut_dep="REAL", statut_arr="REAL"),
        _arret(200, BPUIC_VV,  "VV",  450, retard_dep=0.0,   retard_arr=None,  statut_dep="REAL"),
        _arret(200, BPUIC_GIL, "GIL", 462, retard_dep=300.0, retard_arr=250.0, statut_dep="REAL", statut_arr="REAL"),
    ])


# ===========================================================================
# Tests : _rolling_par_type_jour
# ===========================================================================


class TestRollingParTypeJour:
    def _make_simple_df(self) -> pd.DataFrame:
        """Série ouvrable + samedi sur le même service_id."""
        rows = []
        for i, (d, tj) in enumerate([
            (DATE_A, "ouvrable"),  # lundi J0
            (DATE_B, "ouvrable"),  # mardi J1
            (DATE_C, "samedi"),    # samedi J5
            (DATE_D, "dimanche_ferie"),  # dimanche J6
        ]):
            rows.append({"date": d, "service_id": "1308_07h12",
                          "cal_type_jour_3classes": tj, "valeur": float(i + 1)})
        return pd.DataFrame(rows)

    def test_filtrage_type_jour(self) -> None:
        """Le rolling ouvrable ignore les samedis et dimanches dans la fenêtre."""
        df = self._make_simple_df()
        result = rolling_par_type_jour(
            df, group_key="service_id", date_col="date",
            type_jour_col="cal_type_jour_3classes", value_col="valeur",
            n_occurrences=3, min_periods=1, lag=0, stat="mean",
        )
        # Pour DATE_A (ouvrable, i=0, valeur=1) : fenêtre de 3, mais seule obs ouvrable → mean=1.0
        idx_a = df[df["date"] == DATE_A].index[0]
        assert result.loc[idx_a] == pytest.approx(1.0)

        # Pour DATE_B (ouvrable, i=1, valeur=2) : 2 obs ouvrables → mean(1, 2)=1.5
        idx_b = df[df["date"] == DATE_B].index[0]
        assert result.loc[idx_b] == pytest.approx(1.5)

        # Le samedi ne compte que les samedis dans sa fenêtre (1 obs → mean=3.0)
        idx_c = df[df["date"] == DATE_C].index[0]
        assert result.loc[idx_c] == pytest.approx(3.0)

    def test_lag_j_minus_2(self) -> None:
        """Avec lag=2, la première obs et la deuxième obs reçoivent NaN."""
        rows = [
            {"date": pd.Timestamp(f"2024-01-0{d}"), "service_id": "S1",
             "cal_type_jour_3classes": "ouvrable", "valeur": float(d)}
            for d in range(1, 6)
        ]
        df = pd.DataFrame(rows)
        result = rolling_par_type_jour(
            df, group_key="service_id", date_col="date",
            type_jour_col="cal_type_jour_3classes", value_col="valeur",
            n_occurrences=3, min_periods=1, lag=2, stat="mean",
        )
        # J0 et J1 → NaN (shift(2) fait remonter à avant le début)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        # J2 : shifted val = [J0] → mean=1.0
        assert result.iloc[2] == pytest.approx(1.0)

    def test_groupes_independants(self) -> None:
        """Deux service_ids distincts : les rolling ne se croisent pas."""
        rows = []
        for sid, valeur in [("S1", 10.0), ("S2", 99.0)]:
            rows.append({"date": DATE_A, "service_id": sid,
                          "cal_type_jour_3classes": "ouvrable", "valeur": valeur})
        df = pd.DataFrame(rows)
        result = rolling_par_type_jour(
            df, group_key="service_id", date_col="date",
            type_jour_col="cal_type_jour_3classes", value_col="valeur",
            n_occurrences=3, min_periods=1, lag=0, stat="mean",
        )
        s1_result = result.loc[df["service_id"] == "S1"].values[0]
        s2_result = result.loc[df["service_id"] == "S2"].values[0]
        assert s1_result == pytest.approx(10.0)
        assert s2_result == pytest.approx(99.0)

    def test_stat_sum(self) -> None:
        """stat='sum' compte correctement les booléens."""
        rows = [
            {"date": pd.Timestamp(f"2024-01-0{d}"), "service_id": "S1",
             "cal_type_jour_3classes": "ouvrable", "valeur": float(d % 2)}  # alternance 0/1
            for d in range(1, 6)
        ]
        df = pd.DataFrame(rows)
        result = rolling_par_type_jour(
            df, group_key="service_id", date_col="date",
            type_jour_col="cal_type_jour_3classes", value_col="valeur",
            n_occurrences=3, min_periods=1, lag=0, stat="sum",
        )
        # J4 (index 4) : fenêtre [J2, J3, J4] = [1, 0, 1] → sum = 2
        assert result.iloc[4] == pytest.approx(2.0)

    def test_stat_inconnu_leve_erreur(self) -> None:
        df = pd.DataFrame([{"date": DATE_A, "service_id": "S1",
                             "cal_type_jour_3classes": "ouvrable", "valeur": 1.0}])
        with pytest.raises(ValueError, match="Statistique inconnue"):
            rolling_par_type_jour(
                df, group_key="service_id", date_col="date",
                type_jour_col="cal_type_jour_3classes", value_col="valeur",
                n_occurrences=3, min_periods=1, stat="median",
            )


# ===========================================================================
# Tests : build_dim_profil_train — grain tronçon
# ===========================================================================


class TestGrainTronconProfilTrain:
    def test_grain_troncon_correct(self) -> None:
        """dim_profil_train a bien le grain (date × train × dep × arr × sens)."""
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        # 2 trains × 1 tronçon chacun
        assert len(troncons) == 2
        assert "gare_depart_bpuic" in troncons.columns
        assert "gare_arrivee_bpuic" in troncons.columns
        assert "sens" in troncons.columns

    def test_retard_dep_propagé_sur_troncon(self) -> None:
        """Le retard de départ (gare amont) est bien attaché au tronçon."""
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        train_100 = troncons[troncons["numero_train"] == 100]
        assert train_100["retard_dep_troncon_sec"].iloc[0] == pytest.approx(60.0)

    def test_retard_arr_propagé_sur_troncon(self) -> None:
        """Le retard d'arrivée (gare aval) est bien attaché au tronçon."""
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        train_100 = troncons[troncons["numero_train"] == 100]
        assert train_100["retard_arr_troncon_sec"].iloc[0] == pytest.approx(90.0)

    def test_sens_deduit_correctement(self) -> None:
        """VV→GIL (km 0→1.21) doit donner sens 'VV -> PLEI'."""
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        assert (troncons["sens"] == "VV -> PLEI").all()

    def test_bool_retard_seuil(self) -> None:
        """is_en_retard_{dep,arr} = 1 si retard >= 180s, sinon 0.

        Fixture : train 100 → retard_dep(VV)=60s, retard_arr(GIL)=90s (tous < 180s)
                  train 200 → retard_dep(VV)=0s,  retard_arr(GIL)=250s (arr >= 180s)
        """
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        agg = _agreger_troncon_jour(troncons)

        train_100 = agg[agg["numero_train"] == 100]
        train_200 = agg[agg["numero_train"] == 200]

        # Train 100 : retard_dep(VV)=60s < 180s → is_en_retard_dep=0
        assert train_100["is_en_retard_dep"].iloc[0] == 0.0
        # Train 100 : retard_arr(GIL)=90s < 180s → is_en_retard_arr=0
        assert train_100["is_en_retard_arr"].iloc[0] == 0.0
        # Train 200 : retard_dep(VV)=0s < 180s → is_en_retard_dep=0
        assert train_200["is_en_retard_dep"].iloc[0] == 0.0
        # Train 200 : retard_arr(GIL)=250s >= 180s → is_en_retard_arr=1
        assert train_200["is_en_retard_arr"].iloc[0] == 1.0

    def test_train_annule_exclu(self) -> None:
        """Un train annulé n'apparaît pas dans les tronçons."""
        df_fact = _make_istdaten_2trains().copy()
        df_fact.loc[df_fact["numero_train"] == 100, "is_annule"] = True
        df_fact = _ajouter_service_id(df_fact)
        troncons = _reconstruire_troncons(df_fact, _KM)
        assert 100 not in troncons["numero_train"].values

    def test_service_id_format(self) -> None:
        """ist_service_id suit le format {numero}_{HH}h{MM}."""
        df_fact = _make_istdaten_2trains()
        df_fact = _ajouter_service_id(df_fact)
        import re
        for sid in df_fact["ist_service_id"].dropna().unique():
            assert re.match(r"^\d+_\d{2}h\d{2}$", sid), f"Format inattendu : {sid!r}"


# ===========================================================================
# Tests : correspondances — fenêtres et propagation
# ===========================================================================


def _make_r35_partant(date: pd.Timestamp = DATE_A, h_dep_min: int = 420) -> pd.DataFrame:
    """Un train R35 partant de Vevey à h_dep_min."""
    dep = date + pd.Timedelta(minutes=h_dep_min)
    return pd.DataFrame([{
        "date": date,
        "numero_train": 1308,
        "ist_service_id": "1308_07h00",
        "horaire_depart": dep,
        "reel_depart": pd.NaT,
        "statut_depart": "UNBEKANNT",
    }])


def _make_r35_arrivant(date: pd.Timestamp = DATE_A, h_arr_min: int = 480) -> pd.DataFrame:
    """Un train R35 arrivant à Vevey à h_arr_min."""
    arr = date + pd.Timedelta(minutes=h_arr_min)
    return pd.DataFrame([{
        "date": date,
        "numero_train": 1421,
        "ist_service_id": "1421_06h30",
        "horaire_arrivee": arr,
        "reel_arrivee": pd.NaT,
        "statut_arrivee": "UNBEKANNT",
    }])


def _make_feeders_vevey(date: pd.Timestamp, h_min: int, retard_sec: float | None = 0.0) -> pd.DataFrame:
    """Un feeder CFF arrivant à Vevey à h_min avec retard optionnel."""
    arr = date + pd.Timedelta(minutes=h_min)
    reel = arr + pd.Timedelta(seconds=retard_sec) if retard_sec is not None else pd.NaT
    return pd.DataFrame([{
        "date": date,
        "horaire_arrivee_feeder": arr,
        "reel_arrivee_feeder": reel,
        "retard_feeder_sec": retard_sec,
    }])


def _make_cff_departs_vevey(date: pd.Timestamp, h_min: int, retard_sec: float | None = 0.0) -> pd.DataFrame:
    """Un CFF partant de Vevey à h_min avec retard optionnel."""
    dep = date + pd.Timedelta(minutes=h_min)
    reel = dep + pd.Timedelta(seconds=retard_sec) if retard_sec is not None else pd.NaT
    return pd.DataFrame([{
        "date": date,
        "horaire_depart_cff": dep,
        "reel_depart_cff": reel,
        "retard_cff_sec": retard_sec,
    }])


class TestCorrespondanceIn:
    def test_feeder_dans_fenetre_theorique(self) -> None:
        """Un feeder arrivant 3 min avant le départ R35 est dans la fenêtre théorique [1, 5]."""
        trains = _make_r35_partant(h_dep_min=420)
        feeders = _make_feeders_vevey(DATE_A, h_min=417)  # 3 min avant → dans [1, 5]
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_theoriques_j"].iloc[0] == 1

    def test_feeder_hors_fenetre_trop_tot(self) -> None:
        """Un feeder arrivant 25 min avant (> 5 min) est hors fenêtre."""
        trains = _make_r35_partant(h_dep_min=420)
        feeders = _make_feeders_vevey(DATE_A, h_min=395)  # 25 min avant → hors [1, 5]
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_theoriques_j"].iloc[0] == 0

    def test_feeder_hors_fenetre_trop_tard(self) -> None:
        """Un feeder arrivant en même temps que le départ (délai = 0 < 1 min) est hors fenêtre."""
        trains = _make_r35_partant(h_dep_min=420)
        feeders = _make_feeders_vevey(DATE_A, h_min=420)  # 0 min avant → hors [1, 5]
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_theoriques_j"].iloc[0] == 0

    def test_feeder_garantie_si_arrivee_effective_dans_fenetre(self) -> None:
        """Un feeder dont l'arrivée effective est dans la fenêtre effective est garanti."""
        trains = _make_r35_partant(h_dep_min=420)
        # Feeder à 3 min théorique, retard 60s → arr_effective = 417+1 = 418 min → dans [415, 419]
        feeders = _make_feeders_vevey(DATE_A, h_min=417, retard_sec=60.0)
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_garanties_j"].iloc[0] == 1

    def test_feeder_non_garantie_si_arrivee_effective_hors_fenetre(self) -> None:
        """Un feeder dont l'arrivée effective dépasse le départ R35 n'est pas garanti."""
        trains = _make_r35_partant(h_dep_min=420)
        # Feeder à 3 min théorique, retard 300s (5 min) → arr_effective = 417+5 = 422 min > 419
        feeders = _make_feeders_vevey(DATE_A, h_min=417, retard_sec=300.0)
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_garanties_j"].iloc[0] == 0

    def test_pct_garanties_entre_0_et_1(self) -> None:
        """Le taux de garantie est toujours dans [0, 1]."""
        trains = _make_r35_partant(h_dep_min=420)
        # Feeder 1 : 3 min, retard 60s → garanti ; Feeder 2 : 2 min, retard 300s → non garanti
        feeders = pd.concat([
            _make_feeders_vevey(DATE_A, h_min=417, retard_sec=60.0),
            _make_feeders_vevey(DATE_A, h_min=418, retard_sec=300.0),
        ])
        result = _calculer_correspondances_in(trains, feeders)
        pct = result["ist_corresp_in_pct_garanties_j"].iloc[0]
        assert 0.0 <= pct <= 1.0

    def test_aucun_feeder_donne_zero(self) -> None:
        """Sans feeder, n_theoriques et n_garanties valent 0 (pas NaN)."""
        trains = _make_r35_partant(h_dep_min=420)
        feeders = pd.DataFrame(columns=["date", "horaire_arrivee_feeder", "reel_arrivee_feeder", "retard_feeder_sec"])
        result = _calculer_correspondances_in(trains, feeders)
        assert result["ist_corresp_in_n_theoriques_j"].iloc[0] == 0
        assert result["ist_corresp_in_n_garanties_j"].iloc[0] == 0


class TestCorrespondanceOut:
    def test_cff_dans_fenetre_theorique(self) -> None:
        """Un CFF partant 3 min après l'arrivée R35 est dans la fenêtre [1, 5] min."""
        trains = _make_r35_arrivant(h_arr_min=480)
        departs = _make_cff_departs_vevey(DATE_A, h_min=483)  # +3 min → dans [1, 5]
        result = _calculer_correspondances_out(trains, departs)
        assert result["ist_corresp_out_n_theoriques_j"].iloc[0] == 1

    def test_cff_hors_fenetre_trop_tot(self) -> None:
        """Un CFF partant avant l'arrivée R35 est hors fenêtre."""
        trains = _make_r35_arrivant(h_arr_min=480)
        departs = _make_cff_departs_vevey(DATE_A, h_min=479)  # -1 min → hors [1, 5]
        result = _calculer_correspondances_out(trains, departs)
        assert result["ist_corresp_out_n_theoriques_j"].iloc[0] == 0

    def test_cff_hors_fenetre_trop_tard(self) -> None:
        """Un CFF partant 8 min après est hors fenêtre."""
        trains = _make_r35_arrivant(h_arr_min=480)
        departs = _make_cff_departs_vevey(DATE_A, h_min=488)  # +8 min → hors [1, 5]
        result = _calculer_correspondances_out(trains, departs)
        assert result["ist_corresp_out_n_theoriques_j"].iloc[0] == 0

    def test_pct_garanties_entre_0_et_1(self) -> None:
        """Le taux de garantie _out_ est dans [0, 1]."""
        trains = _make_r35_arrivant(h_arr_min=480)
        departs = pd.concat([
            _make_cff_departs_vevey(DATE_A, h_min=482, retard_sec=0.0),
            _make_cff_departs_vevey(DATE_A, h_min=484, retard_sec=0.0),
        ])
        result = _calculer_correspondances_out(trains, departs)
        pct = result["ist_corresp_out_pct_garanties_j"].iloc[0]
        assert 0.0 <= pct <= 1.0

    def test_aucun_cff_donne_zero(self) -> None:
        """Sans CFF, n_theoriques et n_garanties valent 0 (pas NaN)."""
        trains = _make_r35_arrivant(h_arr_min=480)
        departs = pd.DataFrame(columns=["date", "horaire_depart_cff", "reel_depart_cff", "retard_cff_sec"])
        result = _calculer_correspondances_out(trains, departs)
        assert result["ist_corresp_out_n_theoriques_j"].iloc[0] == 0
        assert result["ist_corresp_out_n_garanties_j"].iloc[0] == 0


# ===========================================================================
# Tests : cal_type_jour_3classes — mapping
# ===========================================================================


class TestTypeJour3Classes:
    def _to_3classes(self, is_ferie: bool, iso: int) -> str:
        """Recalcule cal_type_jour_3classes depuis les colonnes sources."""
        import numpy as np
        return np.where(
            is_ferie or iso == 7,
            "dimanche_ferie",
            np.where(iso == 6, "samedi", "ouvrable"),
        )

    def test_dimanche_est_dimanche_ferie(self) -> None:
        assert self._to_3classes(False, 7) == "dimanche_ferie"

    def test_ferie_est_dimanche_ferie(self) -> None:
        assert self._to_3classes(True, 1) == "dimanche_ferie"  # lundi férié

    def test_samedi_est_samedi(self) -> None:
        assert self._to_3classes(False, 6) == "samedi"

    def test_samedi_ferie_est_dimanche_ferie(self) -> None:
        # Un samedi férié (ex. 1er janvier 2022) est classé dimanche_ferie
        assert self._to_3classes(True, 6) == "dimanche_ferie"

    def test_lundi_est_ouvrable(self) -> None:
        assert self._to_3classes(False, 1) == "ouvrable"

    def test_vendredi_est_ouvrable(self) -> None:
        assert self._to_3classes(False, 5) == "ouvrable"


# ===========================================================================
# Tests : service_id — pas de chevauchement cross-horaire
# ===========================================================================


class TestServiceIdCrossHoraire:
    def test_meme_numero_horaire_different_service_id_different(self) -> None:
        """Le même numéro de train avec une heure d'origine différente → service_ids distincts."""
        df = pd.DataFrame([
            # Train 1308 en H23 : premier départ à 07h12
            _arret(1308, BPUIC_VV, "VV", 432, date=pd.Timestamp("2023-06-01")),
            _arret(1308, BPUIC_GIL, "GIL", 444, date=pd.Timestamp("2023-06-01")),
            # Train 1308 en H24 : premier départ à 07h15 (recadencé)
            _arret(1308, BPUIC_VV, "VV", 435, date=pd.Timestamp("2024-06-01")),
            _arret(1308, BPUIC_GIL, "GIL", 447, date=pd.Timestamp("2024-06-01")),
        ])
        df = _ajouter_service_id(df)
        ids = df.groupby("date")["ist_service_id"].first()
        assert ids.iloc[0] != ids.iloc[1], (
            "Deux horaires différents pour le même numéro de train doivent "
            "produire des service_ids distincts."
        )

    def test_meme_service_meme_id(self) -> None:
        """Le même service sur deux jours consécutifs → même service_id."""
        df = pd.DataFrame([
            _arret(1308, BPUIC_VV, "VV", 432, date=DATE_A),
            _arret(1308, BPUIC_GIL, "GIL", 444, date=DATE_A),
            _arret(1308, BPUIC_VV, "VV", 432, date=DATE_B),
            _arret(1308, BPUIC_GIL, "GIL", 444, date=DATE_B),
        ])
        df = _ajouter_service_id(df)
        ids = df.groupby("date")["ist_service_id"].first()
        assert ids.iloc[0] == ids.iloc[1]
