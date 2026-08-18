"""
tests/test_pipeline_vmcv.py
============================
DEPRECATED — Design ADR-020 (grain tronçon) remplacé par ADR-021.
Voir tests/test_pipeline_vmcv_train_jour.py pour le design actuel.

Périmètre original
------------------
1. Identification des arrêts VMCV proches (200m, ligne active)
2. Construction du mapping tronçons (les deux sens, même ligne)
3. Reconstruction des tronçons VMCV (filtre sens chronologique)
4. Calcul des deltas attente, trajet et fréquence
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Tous les tests de ce fichier sont marqués DEPRECATED — ADR-020 remplacé par ADR-021.
pytestmark = pytest.mark.skip(
    reason="Design ADR-020 remplacé par ADR-021 — voir test_pipeline_vmcv_train_jour.py"
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sources"))

from sources.build_dim_vmcv_par_troncon import (
    FENETRE_ATTENTE_AMONT_MIN,
    FENETRE_ATTENTE_AVAL_MIN,
    FENETRE_FREQUENCE_MIN,
    GRAIN,
    RAYON_PROXIMITE_M,
    _calculer_deltas,
    _construire_mapping_troncons,
    _haversine_vec,
    _identifier_arrets_vmcv_proches,
    _reconstruire_troncons_vmcv,
)

# ---------------------------------------------------------------------------
# Constantes partagées
# ---------------------------------------------------------------------------

DATE_REF = pd.Timestamp("2023-06-01")

# BPUICs fictifs pour les gares R35 (VV et GIL)
BPUIC_VV = 1000
BPUIC_GIL = 2000

# BPUICs fictifs pour les arrêts VMCV
BPUIC_VMCV_A = 9001   # près de VV
BPUIC_VMCV_B = 9002   # près de GIL

# Coordonnées de référence : équateur, 1° lat ≈ 111 320 m
# → 100m ≈ 0.000898°, 300m ≈ 0.002694°
LON_REF = 0.0
LAT_REF = 0.0
LAT_100M = 0.000898   # ~100m au nord
LAT_300M = 0.002694   # ~300m au nord


# ---------------------------------------------------------------------------
# Helpers partagés
# ---------------------------------------------------------------------------


def _make_gares_r35() -> pd.DataFrame:
    """Deux gares R35 adjacentes : VV (km=0) et GIL (km=1.21)."""
    return pd.DataFrame([
        {"bpuic": BPUIC_VV,  "km": 0.00, "wgs84East": LON_REF, "wgs84North": LAT_REF},
        {"bpuic": BPUIC_GIL, "km": 1.21, "wgs84East": LON_REF, "wgs84North": LAT_100M},
    ])


def _make_mapping() -> pd.DataFrame:
    """Mapping tronçon VV→GIL avec ligne 202."""
    return pd.DataFrame([{
        "gare_depart_bpuic": BPUIC_VV, "gare_arrivee_bpuic": BPUIC_GIL,
        "sens": "VV -> PLEI",
        "bpuic_vmcv_dep": BPUIC_VMCV_A, "bpuic_vmcv_arr": BPUIC_VMCV_B,
        "linien_text": "202",
    }])


def _make_r35_troncon(
    h_dep_min: int,
    trajet_min: float = 10.0,
    train: int = 100,
    date: pd.Timestamp = DATE_REF,
) -> pd.DataFrame:
    h = date + pd.Timedelta(minutes=h_dep_min)
    return pd.DataFrame([{
        "date": date, "numero_train": train,
        "gare_depart_bpuic": BPUIC_VV, "gare_arrivee_bpuic": BPUIC_GIL,
        "sens": "VV -> PLEI",
        "h_dep_r35": h,
        "h_arr_r35": h + pd.Timedelta(minutes=trajet_min),
        "trajet_r35_min": float(trajet_min),
    }])


def _make_vmcv_troncon(
    h_dep_min: int,
    trajet_min: float = 8.0,
    fahrt: str = "F1",
    date: pd.Timestamp = DATE_REF,
) -> pd.DataFrame:
    h = date + pd.Timedelta(minutes=h_dep_min)
    return pd.DataFrame([{
        "date": date, "linien_text": "202", "fahrt": fahrt,
        "bpuic_vmcv_dep": BPUIC_VMCV_A, "bpuic_vmcv_arr": BPUIC_VMCV_B,
        "h_dep_vmcv": h,
        "h_arr_vmcv": h + pd.Timedelta(minutes=trajet_min),
        "trajet_vmcv_min": float(trajet_min),
    }])


def _empty_vmcv_troncons() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.Series([], dtype="datetime64[ns]"),
        "linien_text": pd.Series([], dtype=str),
        "fahrt": pd.Series([], dtype=str),
        "bpuic_vmcv_dep": pd.Series([], dtype=int),
        "bpuic_vmcv_arr": pd.Series([], dtype=int),
        "h_dep_vmcv": pd.Series([], dtype="datetime64[ns]"),
        "h_arr_vmcv": pd.Series([], dtype="datetime64[ns]"),
        "trajet_vmcv_min": pd.Series([], dtype=float),
    })


def _empty_mapping() -> pd.DataFrame:
    return pd.DataFrame({
        "gare_depart_bpuic": pd.Series([], dtype=int),
        "gare_arrivee_bpuic": pd.Series([], dtype=int),
        "sens": pd.Series([], dtype=str),
        "bpuic_vmcv_dep": pd.Series([], dtype=int),
        "bpuic_vmcv_arr": pd.Series([], dtype=int),
        "linien_text": pd.Series([], dtype=str),
    })


# ---------------------------------------------------------------------------
# Tests — constantes de configuration
# ---------------------------------------------------------------------------


class TestConstantes:
    def test_rayon_proximite_200m(self) -> None:
        assert RAYON_PROXIMITE_M == 200

    def test_fenetre_attente(self) -> None:
        assert FENETRE_ATTENTE_AMONT_MIN == 5
        assert FENETRE_ATTENTE_AVAL_MIN == 30

    def test_fenetre_frequence(self) -> None:
        assert FENETRE_FREQUENCE_MIN == 30

    def test_grain_cinq_cles(self) -> None:
        assert GRAIN == [
            "date", "numero_train",
            "gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
        ]


# ---------------------------------------------------------------------------
# Tests — identification des arrêts VMCV proches
# ---------------------------------------------------------------------------


class TestIdentificationArretsProches:
    def _make_arret(self, bpuic: int, lon: float, lat: float, ligne: str) -> pd.DataFrame:
        return pd.DataFrame([{
            "linien_text": ligne, "bpuic": bpuic, "lon": lon, "lat": lat,
        }])

    def test_arret_dans_rayon_inclus(self) -> None:
        """Un arrêt à ~100m de la gare R35 est inclus (rayon = 200m)."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        arret = self._make_arret(BPUIC_VMCV_A, LON_REF, LAT_100M, "202")
        result = _identifier_arrets_vmcv_proches(gares, arret, frozenset({"202"}), 200)
        assert len(result) == 1
        assert result.iloc[0]["gare_r35_bpuic"] == BPUIC_VV
        assert result.iloc[0]["bpuic_vmcv"] == BPUIC_VMCV_A

    def test_arret_hors_rayon_exclu(self) -> None:
        """Un arrêt à ~300m de la gare R35 est exclu (rayon = 200m)."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        arret = self._make_arret(BPUIC_VMCV_A, LON_REF, LAT_300M, "202")
        result = _identifier_arrets_vmcv_proches(gares, arret, frozenset({"202"}), 200)
        assert len(result) == 0

    def test_ligne_inactive_exclue(self) -> None:
        """Un arrêt d'une ligne non active est exclu même à 50m."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        arret = self._make_arret(BPUIC_VMCV_A, LON_REF, LAT_100M, "999")
        result = _identifier_arrets_vmcv_proches(gares, arret, frozenset({"202"}), 200)
        assert len(result) == 0

    def test_arret_sans_coordonnees_exclu(self) -> None:
        """Un arrêt sans coordonnées (lon=NaN) est exclu."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        arret = pd.DataFrame([{
            "linien_text": "202", "bpuic": BPUIC_VMCV_A, "lon": float("nan"), "lat": float("nan"),
        }])
        result = _identifier_arrets_vmcv_proches(gares, arret, frozenset({"202"}), 200)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests — construction du mapping tronçons
# ---------------------------------------------------------------------------


class TestMappingTroncons:
    def _make_arrets_proches(self) -> pd.DataFrame:
        """VV et GIL ont chacune un arrêt VMCV ligne 202."""
        return pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_VV,  "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},
            {"gare_r35_bpuic": BPUIC_GIL, "bpuic_vmcv": BPUIC_VMCV_B, "linien_text": "202"},
        ])

    def test_deux_sens_generes(self) -> None:
        """Pour deux gares adjacentes avec VMCV, les deux sens sont générés."""
        gares = _make_gares_r35()
        arrets = self._make_arrets_proches()
        mapping = _construire_mapping_troncons(gares, arrets)
        assert len(mapping) == 2
        assert set(mapping["sens"]) == {"VV -> PLEI", "PLEI -> VV"}

    def test_colonnes_mapping(self) -> None:
        """Le mapping contient les 6 colonnes attendues."""
        gares = _make_gares_r35()
        arrets = self._make_arrets_proches()
        mapping = _construire_mapping_troncons(gares, arrets)
        for col in ["gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
                    "bpuic_vmcv_dep", "bpuic_vmcv_arr", "linien_text"]:
            assert col in mapping.columns, f"Colonne manquante : {col}"

    def test_ligne_differente_pas_de_match(self) -> None:
        """Si les deux gares ont des lignes VMCV différentes, aucun tronçon créé."""
        gares = _make_gares_r35()
        arrets = pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_VV,  "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},
            {"gare_r35_bpuic": BPUIC_GIL, "bpuic_vmcv": BPUIC_VMCV_B, "linien_text": "215"},
        ])
        mapping = _construire_mapping_troncons(gares, arrets)
        assert len(mapping) == 0

    def test_meme_bpuic_vmcv_exclu(self) -> None:
        """Une paire avec le même arrêt VMCV aux deux extrémités est exclue."""
        gares = _make_gares_r35()
        arrets = pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_VV,  "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},
            {"gare_r35_bpuic": BPUIC_GIL, "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},  # même stop
        ])
        mapping = _construire_mapping_troncons(gares, arrets)
        assert len(mapping) == 0


# ---------------------------------------------------------------------------
# Tests — reconstruction des tronçons VMCV
# ---------------------------------------------------------------------------


class TestReconstruireTronconVmcv:
    def _make_passages(
        self,
        date: pd.Timestamp,
        fahrt: str,
        h_dep_min: int,
        h_arr_min: int,
    ) -> pd.DataFrame:
        """Deux lignes de passage (dep au stop A, arr au stop B)."""
        base = date
        return pd.DataFrame([
            {
                "date": base, "linien_text": "202", "fahrt": fahrt,
                "bpuic": BPUIC_VMCV_A,
                "h_dep_eff": base + pd.Timedelta(minutes=h_dep_min),
                "h_arr_eff": pd.NaT,
            },
            {
                "date": base, "linien_text": "202", "fahrt": fahrt,
                "bpuic": BPUIC_VMCV_B,
                "h_dep_eff": pd.NaT,
                "h_arr_eff": base + pd.Timedelta(minutes=h_arr_min),
            },
        ])

    def test_paire_chronologique_incluse(self) -> None:
        """Une paire VMCV avec h_dep < h_arr (10min) produit un tronçon valide."""
        passages = self._make_passages(DATE_REF, "F1", h_dep_min=480, h_arr_min=490)
        result = _reconstruire_troncons_vmcv(passages, _make_mapping())
        assert len(result) == 1
        assert result["trajet_vmcv_min"].iloc[0] == pytest.approx(10.0)

    def test_paire_inverse_exclue(self) -> None:
        """Une paire VMCV avec h_dep > h_arr (sens inverse) est exclue."""
        passages = self._make_passages(DATE_REF, "F1", h_dep_min=540, h_arr_min=480)
        result = _reconstruire_troncons_vmcv(passages, _make_mapping())
        assert len(result) == 0

    def test_plusieurs_fahrt_distincts(self) -> None:
        """Plusieurs fahrts distincts produisent des tronçons distincts."""
        p1 = self._make_passages(DATE_REF, "F1", h_dep_min=480, h_arr_min=490)
        p2 = self._make_passages(DATE_REF, "F2", h_dep_min=510, h_arr_min=520)
        result = _reconstruire_troncons_vmcv(pd.concat([p1, p2], ignore_index=True), _make_mapping())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests — calcul delta_attente
# ---------------------------------------------------------------------------


class TestDeltaAttente:
    def test_vmcv_avant_r35_delta_positif(self) -> None:
        """VMCV part 3min avant R35 → dans la fenêtre [−5, +30] → delta_attente = 3."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        # VMCV à 3min avant R35 : dans [h−5, h+30] ✓
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 3)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(3.0)

    def test_vmcv_apres_r35_delta_negatif(self) -> None:
        """VMCV part 5min après R35 → dans [−5, +30] → delta_attente = −5."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 + 5)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(-5.0)

    def test_vmcv_trop_tot_nan(self) -> None:
        """VMCV part 10min avant R35 → hors fenêtre AMONT (> 5min) → NaN."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        # Fenêtre attente : [h_dep_r35 − 5min, h_dep_r35 + 30min]
        # VMCV à -10min < borne inférieure → hors fenêtre
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 10)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_delta_attente_min"].iloc[0])

    def test_vmcv_trop_tard_nan(self) -> None:
        """VMCV part 40min après R35 (> AVAL=30) → hors fenêtre → NaN."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 + 40)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_delta_attente_min"].iloc[0])

    def test_sans_alternative_vmcv_nan(self) -> None:
        """Sans alternative VMCV (mapping vide), les 3 features sont NaN."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        result = _calculer_deltas(r35, _empty_vmcv_troncons(), _empty_mapping())
        assert pd.isna(result["vmcv_delta_attente_min"].iloc[0])
        assert pd.isna(result["vmcv_delta_trajet_min"].iloc[0])
        assert pd.isna(result["vmcv_delta_frequence_h"].iloc[0])

    def test_meilleur_vmcv_selectionne(self) -> None:
        """Parmi plusieurs VMCV dans la fenêtre, le meilleur (max delta) est retenu."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        # VMCV à -3min (delta=3) et à +5min (delta=-5) → max = 3
        vmcv = pd.concat([
            _make_vmcv_troncon(h_dep_min=8 * 60 - 3, fahrt="F1"),
            _make_vmcv_troncon(h_dep_min=8 * 60 + 5, fahrt="F2"),
        ], ignore_index=True)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Tests — calcul delta_trajet
# ---------------------------------------------------------------------------


class TestDeltaTrajet:
    def test_vmcv_plus_rapide_delta_positif(self) -> None:
        """R35 = 15min, VMCV = 8min → delta_trajet = 7 (VMCV plus rapide)."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, trajet_min=15.0)
        # VMCV 3min avant R35 : dans la fenêtre attente [−5, +30]
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 3, trajet_min=8.0)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_trajet_min"].iloc[0] == pytest.approx(7.0)

    def test_vmcv_plus_lent_delta_negatif(self) -> None:
        """R35 = 8min, VMCV = 15min → delta_trajet = −7 (R35 plus rapide)."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, trajet_min=8.0)
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 3, trajet_min=15.0)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_trajet_min"].iloc[0] == pytest.approx(-7.0)

    def test_delta_trajet_moyenne_journaliere_deux_vmcv(self) -> None:
        """2 VMCV le même jour : delta_trajet utilise la moyenne journalière (6+10)/2=8."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, trajet_min=10.0)
        # Les deux VMCV sont sur le même jour → moyenne journalière = (6+10)/2 = 8min
        vmcv = pd.concat([
            _make_vmcv_troncon(h_dep_min=8 * 60 - 3, trajet_min=6.0, fahrt="F1"),
            _make_vmcv_troncon(h_dep_min=8 * 60 + 5, trajet_min=10.0, fahrt="F2"),
        ], ignore_index=True)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_trajet_min"].iloc[0] == pytest.approx(2.0)

    def test_delta_trajet_utilise_moyenne_journaliere(self) -> None:
        """delta_trajet inclut les VMCV hors fenêtre attente (moyenne journalière)."""
        r35 = _make_r35_troncon(h_dep_min=14 * 60, trajet_min=10.0)
        vmcv = pd.concat([
            # VMCV à 8h : trajet 6min — hors fenêtre attente du R35 à 14h [13h55, 14h30]
            _make_vmcv_troncon(h_dep_min=8 * 60, trajet_min=6.0, fahrt="F1"),
            # VMCV à 14h-3min : trajet 10min — dans fenêtre attente
            _make_vmcv_troncon(h_dep_min=14 * 60 - 3, trajet_min=10.0, fahrt="F2"),
        ], ignore_index=True)
        # Moyenne journalière = (6+10)/2 = 8min → delta = 10 - 8 = 2
        # Avec l'ancienne logique (fenêtre attente seule) : delta = 10 - 10 = 0
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_trajet_min"].iloc[0] == pytest.approx(2.0)

    def test_delta_trajet_nan_si_aucun_vmcv_jour(self) -> None:
        """Aucun VMCV pour ce jour → moyenne journalière = NaN → delta_trajet = NaN."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, trajet_min=10.0)
        result = _calculer_deltas(r35, _empty_vmcv_troncons(), _make_mapping())
        assert pd.isna(result["vmcv_delta_trajet_min"].iloc[0])


# ---------------------------------------------------------------------------
# Tests — calcul delta_frequence
# ---------------------------------------------------------------------------


class TestDeltaFrequence:
    def test_vmcv_plus_frequent_delta_positif(self) -> None:
        """3 VMCV dans ±30min, 1 R35 → delta_freq = 3 − 1 = 2."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        # 3 VMCV dans ±30min
        vmcv = pd.concat([
            _make_vmcv_troncon(h_dep_min=8 * 60 - 20, fahrt="F1"),
            _make_vmcv_troncon(h_dep_min=8 * 60 - 5,  fahrt="F2"),
            _make_vmcv_troncon(h_dep_min=8 * 60 + 10, fahrt="F3"),
        ], ignore_index=True)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(2.0)

    def test_vmcv_moins_frequent_delta_negatif(self) -> None:
        """1 VMCV dans ±30min, 3 R35 → delta_freq = 1 − 3 = −2."""
        r35 = pd.concat([
            _make_r35_troncon(h_dep_min=8 * 60 - 20, train=100),
            _make_r35_troncon(h_dep_min=8 * 60,      train=101),
            _make_r35_troncon(h_dep_min=8 * 60 + 20, train=102),
        ], ignore_index=True)
        # Seul train 101 est ciblé pour le calcul ; les 3 R35 sont dans ±30min de chacun
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 5, fahrt="F1")
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        # Pour le train 101 : vmcv_count=1 (F1 in ±30min), r35_count=3 (trains 100,101,102)
        row_101 = result[result["numero_train"] == 101]
        assert row_101["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(-2.0)

    def test_sans_vmcv_freq_window_nan(self) -> None:
        """Sans VMCV dans ±30min, delta_frequence = NaN."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60)
        # VMCV 60min après R35 : hors ±30min
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 + 60)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_delta_frequence_h"].iloc[0])

    def test_nb_lignes_inchange(self) -> None:
        """Le calcul ne modifie pas le nombre de lignes R35."""
        r35 = pd.concat([
            _make_r35_troncon(h_dep_min=8 * 60, train=100),
            _make_r35_troncon(h_dep_min=8 * 60, train=200),
        ], ignore_index=True)
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 3)
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert len(result) == len(r35)

    def test_delta_frequence_inclut_train_courant(self) -> None:
        """1 R35 isolé (aucun autre R35 dans ±30min), 0 VMCV → NaN (auto-inclusion sans effet)."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, train=100)
        result = _calculer_deltas(r35, _empty_vmcv_troncons(), _make_mapping())
        assert pd.isna(result["vmcv_delta_frequence_h"].iloc[0])

    def test_delta_frequence_train_seul_avec_vmcv(self) -> None:
        """1 R35 isolé, 1 VMCV dans ±30min → delta_freq = 1 − 1 = 0 (auto-inclusion)."""
        r35 = _make_r35_troncon(h_dep_min=8 * 60, train=100)
        vmcv = _make_vmcv_troncon(h_dep_min=8 * 60 - 5, fahrt="F1")
        result = _calculer_deltas(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests — haversine vectorisé
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_distance_nulle(self) -> None:
        """Distance entre deux points identiques = 0."""
        d = _haversine_vec(0.0, 0.0, pd.Series([0.0]), pd.Series([0.0]))
        assert d.iloc[0] == pytest.approx(0.0, abs=1e-3)

    def test_distance_100m(self) -> None:
        """Distance vers un point à ~100m (au nord) ≈ 100m."""
        d = _haversine_vec(LON_REF, LAT_REF, pd.Series([LON_REF]), pd.Series([LAT_100M]))
        assert d.iloc[0] == pytest.approx(100.0, rel=0.01)

    def test_distance_300m(self) -> None:
        """Distance vers un point à ~300m (au nord) ≈ 300m."""
        d = _haversine_vec(LON_REF, LAT_REF, pd.Series([LON_REF]), pd.Series([LAT_300M]))
        assert d.iloc[0] == pytest.approx(300.0, rel=0.01)
