"""
tests/test_pipeline_vmcv_train_jour.py
=======================================
Tests pour build_dim_vmcv_par_train_jour.py (ADR-021 — décision à l'embarquement).

Périmètre
---------
1. Constantes de configuration (KM_SEUIL_BAS, KM_SEUIL_HAUT, GRAIN, fenêtres)
2. Identification des arrêts VMCV proches — retourne désormais gare_r35_km (ADR-021)
3. Mapping directionnel : 5 cas (haut seul, bas seul, haut+bas, zone intermédiaire, 2 lignes)
4. Feature vmcv_n_lignes_concurrentes (statique depuis le mapping)
5. Features vmcv_min_attente_min et vmcv_delta_attente_min
6. Feature vmcv_delta_frequence_h avec auto-inclusion R35
7. Grain : 1 ligne par (date, numero_train, sens), colonnes exactes

Usage
-----
    pytest tests/test_pipeline_vmcv_train_jour.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sources"))

from sources.build_dim_vmcv_par_train_jour import (
    FENETRE_ATTENTE_AMONT_MIN,
    FENETRE_ATTENTE_AVAL_MIN,
    FENETRE_FREQUENCE_MIN,
    GRAIN,
    KM_SEUIL_BAS,
    KM_SEUIL_HAUT,
    RAYON_PROXIMITE_M,
    _calculer_features,
    _construire_mapping_directionnel,
    _haversine_vec,
    _identifier_arrets_vmcv_proches,
)

# ---------------------------------------------------------------------------
# Constantes partagées
# ---------------------------------------------------------------------------

DATE_REF = pd.Timestamp("2023-06-01")

BPUIC_VV    = 1000   # km=0.0  → bas de ligne
BPUIC_BLONAY = 2000  # km=6.0  → haut de ligne

BPUIC_VMCV_A = 9001  # arrêt VMCV près de VV
BPUIC_VMCV_B = 9002  # arrêt VMCV près de Blonay

LON_REF  = 0.0
LAT_REF  = 0.0
LAT_100M = 0.000898   # ~100m au nord
LAT_300M = 0.002694   # ~300m au nord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_r35_train(
    date: pd.Timestamp = DATE_REF,
    numero_train: int = 100,
    sens: str = "VV -> PLEI",
    gare_dep_bpuic: int = BPUIC_VV,
    h_dep_min: int = 8 * 60,
) -> pd.DataFrame:
    return pd.DataFrame([{
        "date":                date,
        "numero_train":        numero_train,
        "sens":                sens,
        "gare_dep_r35_bpuic":  gare_dep_bpuic,
        "h_dep_r35":           date + pd.Timedelta(minutes=h_dep_min),
    }])


def _make_vmcv_passage(
    date: pd.Timestamp = DATE_REF,
    bpuic_vmcv: int = BPUIC_VMCV_A,
    h_dep_min: int = 8 * 60 - 3,
    linien_text: str = "202",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "date":        date,
        "linien_text": linien_text,
        "bpuic_vmcv":  bpuic_vmcv,
        "h_dep_vmcv":  date + pd.Timedelta(minutes=h_dep_min),
    }])


def _make_mapping(
    gare_r35_bpuic: int = BPUIC_VV,
    sens: str = "VV -> PLEI",
    bpuic_vmcv: int = BPUIC_VMCV_A,
    linien_text: str = "202",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "gare_r35_bpuic": gare_r35_bpuic,
        "sens":           sens,
        "bpuic_vmcv":     bpuic_vmcv,
        "linien_text":    linien_text,
    }])


def _empty_vmcv_passages() -> pd.DataFrame:
    return pd.DataFrame({
        "date":        pd.Series([], dtype="datetime64[ns]"),
        "linien_text": pd.Series([], dtype=str),
        "bpuic_vmcv":  pd.Series([], dtype=int),
        "h_dep_vmcv":  pd.Series([], dtype="datetime64[ns]"),
    })


def _empty_mapping() -> pd.DataFrame:
    return pd.DataFrame({
        "gare_r35_bpuic": pd.Series([], dtype=int),
        "sens":           pd.Series([], dtype=str),
        "bpuic_vmcv":     pd.Series([], dtype=int),
        "linien_text":    pd.Series([], dtype=str),
    })


# ---------------------------------------------------------------------------
# Tests — constantes de configuration
# ---------------------------------------------------------------------------


class TestConstantesADR23:
    def test_km_seuil_bas(self) -> None:
        assert KM_SEUIL_BAS == 4.0

    def test_km_seuil_haut(self) -> None:
        assert KM_SEUIL_HAUT == 5.5

    def test_grain_trois_cles(self) -> None:
        assert GRAIN == ["date", "numero_train", "sens"]

    def test_rayon_200m(self) -> None:
        assert RAYON_PROXIMITE_M == 200

    def test_fenetres(self) -> None:
        assert FENETRE_ATTENTE_AMONT_MIN == 5
        assert FENETRE_ATTENTE_AVAL_MIN  == 30
        assert FENETRE_FREQUENCE_MIN     == 30


# ---------------------------------------------------------------------------
# Tests — identification des arrêts proches (nouvelle colonne gare_r35_km)
# ---------------------------------------------------------------------------


class TestIdentificationArretsProches:
    def test_retourne_colonne_km(self) -> None:
        """_identifier_arrets_vmcv_proches retourne gare_r35_km (nouveau ADR-021)."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        stop = pd.DataFrame([{
            "linien_text": "202", "bpuic": BPUIC_VMCV_A,
            "lon": LON_REF, "lat": LAT_100M,
        }])
        result = _identifier_arrets_vmcv_proches(gares, stop, frozenset({"202"}), 200)
        assert "gare_r35_km" in result.columns
        assert result.iloc[0]["gare_r35_km"] == pytest.approx(0.0)

    def test_arret_dans_rayon_inclus(self) -> None:
        """Un arrêt à ~100m est inclus (rayon = 200m)."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        stop = pd.DataFrame([{
            "linien_text": "202", "bpuic": BPUIC_VMCV_A,
            "lon": LON_REF, "lat": LAT_100M,
        }])
        result = _identifier_arrets_vmcv_proches(gares, stop, frozenset({"202"}), 200)
        assert len(result) == 1
        assert result.iloc[0]["bpuic_vmcv"] == BPUIC_VMCV_A

    def test_arret_hors_rayon_exclu(self) -> None:
        """Un arrêt à ~300m est exclu (rayon = 200m)."""
        gares = pd.DataFrame([{
            "bpuic": BPUIC_VV, "km": 0.0,
            "wgs84East": LON_REF, "wgs84North": LAT_REF,
        }])
        stop = pd.DataFrame([{
            "linien_text": "202", "bpuic": BPUIC_VMCV_A,
            "lon": LON_REF, "lat": LAT_300M,
        }])
        result = _identifier_arrets_vmcv_proches(gares, stop, frozenset({"202"}), 200)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests — mapping directionnel (test D2 de l'ADR-021)
# ---------------------------------------------------------------------------


class TestMappingDirectionnel:
    def test_ligne_haut_uniquement_vv_vers_plei(self) -> None:
        """Ligne near haut (km=6.0≥5.5) uniquement → sens VV→PLEI seulement."""
        arrets = pd.DataFrame([{
            "gare_r35_bpuic": BPUIC_BLONAY, "gare_r35_km": 6.0,
            "bpuic_vmcv": BPUIC_VMCV_B, "linien_text": "202",
        }])
        result = _construire_mapping_directionnel(arrets)
        assert set(result["sens"]) == {"VV -> PLEI"}

    def test_ligne_bas_uniquement_plei_vers_vv(self) -> None:
        """Ligne near bas (km=2.0≤4.0) uniquement → sens PLEI→VV seulement."""
        arrets = pd.DataFrame([{
            "gare_r35_bpuic": BPUIC_VV, "gare_r35_km": 2.0,
            "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202",
        }])
        result = _construire_mapping_directionnel(arrets)
        assert set(result["sens"]) == {"PLEI -> VV"}

    def test_ligne_haut_et_bas_deux_sens(self) -> None:
        """Ligne near haut ET near bas → les deux sens sont générés."""
        arrets = pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_VV,     "gare_r35_km": 2.0,
             "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},
            {"gare_r35_bpuic": BPUIC_BLONAY,  "gare_r35_km": 6.0,
             "bpuic_vmcv": BPUIC_VMCV_B, "linien_text": "202"},
        ])
        result = _construire_mapping_directionnel(arrets)
        assert set(result["sens"]) == {"VV -> PLEI", "PLEI -> VV"}

    def test_ligne_zone_intermediaire_exclue(self) -> None:
        """Ligne near zone intermédiaire (km=4.5, ni ≤4.0 ni ≥5.5) → exclue."""
        arrets = pd.DataFrame([{
            "gare_r35_bpuic": 3000, "gare_r35_km": 4.5,
            "bpuic_vmcv": 9003, "linien_text": "202",
        }])
        result = _construire_mapping_directionnel(arrets)
        assert len(result) == 0

    def test_deux_lignes_independantes(self) -> None:
        """Ligne A near haut, ligne B near bas → chaque ligne n'apparaît que dans son sens."""
        arrets = pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_BLONAY, "gare_r35_km": 6.0,
             "bpuic_vmcv": BPUIC_VMCV_B, "linien_text": "A"},
            {"gare_r35_bpuic": BPUIC_VV,     "gare_r35_km": 2.0,
             "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "B"},
        ])
        result = _construire_mapping_directionnel(arrets)
        assert set(result.loc[result["linien_text"] == "A", "sens"]) == {"VV -> PLEI"}
        assert set(result.loc[result["linien_text"] == "B", "sens"]) == {"PLEI -> VV"}

    def test_arrets_vides_retourne_vide(self) -> None:
        """Aucun arrêt → mapping vide."""
        arrets = pd.DataFrame(
            columns=["gare_r35_bpuic", "gare_r35_km", "bpuic_vmcv", "linien_text"]
        )
        result = _construire_mapping_directionnel(arrets)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests — feature vmcv_n_lignes_concurrentes
# ---------------------------------------------------------------------------


class TestNLignesConcurrentes:
    def test_une_ligne_dans_mapping(self) -> None:
        """1 ligne dans le mapping → n_lignes = 1."""
        r35 = _make_r35_train()
        result = _calculer_features(r35, _empty_vmcv_passages(), _make_mapping())
        assert result["vmcv_n_lignes_concurrentes"].iloc[0] == 1

    def test_deux_lignes_distinctes(self) -> None:
        """2 lignes distinctes → n_lignes = 2."""
        r35 = _make_r35_train()
        mapping = pd.DataFrame([
            {"gare_r35_bpuic": BPUIC_VV, "sens": "VV -> PLEI",
             "bpuic_vmcv": BPUIC_VMCV_A, "linien_text": "202"},
            {"gare_r35_bpuic": BPUIC_VV, "sens": "VV -> PLEI",
             "bpuic_vmcv": 9003,          "linien_text": "215"},
        ])
        result = _calculer_features(r35, _empty_vmcv_passages(), mapping)
        assert result["vmcv_n_lignes_concurrentes"].iloc[0] == 2

    def test_mapping_vide_zero(self) -> None:
        """Aucune ligne pour cette gare/sens → n_lignes = 0."""
        r35 = _make_r35_train()
        result = _calculer_features(r35, _empty_vmcv_passages(), _empty_mapping())
        assert result["vmcv_n_lignes_concurrentes"].iloc[0] == 0


# ---------------------------------------------------------------------------
# Tests — features vmcv_min_attente_min et vmcv_delta_attente_min
# ---------------------------------------------------------------------------


class TestAttente:
    def test_vmcv_avant_r35_dans_fenetre(self) -> None:
        """VMCV à h−3min → _attente = (h−3)−(h−5) = 2min, delta = 5−2 = 3."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 - 3)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert result["vmcv_min_attente_min"].iloc[0]   == pytest.approx(2.0)
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(3.0)

    def test_vmcv_apres_r35_dans_fenetre(self) -> None:
        """VMCV à h+5min → _attente = 5+5 = 10min, delta = 5−10 = −5."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 + 5)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert result["vmcv_min_attente_min"].iloc[0]   == pytest.approx(10.0)
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(-5.0)

    def test_vmcv_trop_tot_nan(self) -> None:
        """VMCV à h−10min < (h−5min) = borne inférieure → hors fenêtre → NaN."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 - 10)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_min_attente_min"].iloc[0])
        assert pd.isna(result["vmcv_delta_attente_min"].iloc[0])

    def test_vmcv_trop_tard_nan(self) -> None:
        """VMCV à h+40min > (h+30min) = borne supérieure → hors fenêtre → NaN."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 + 40)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_min_attente_min"].iloc[0])

    def test_meilleur_vmcv_selectionne(self) -> None:
        """2 VMCV dans fenêtre : min_attente = plus petite attente (VMCV le plus proche)."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = pd.concat([
            _make_vmcv_passage(h_dep_min=8 * 60 - 3),   # attente = 2min
            _make_vmcv_passage(h_dep_min=8 * 60 + 10),  # attente = 15min
        ], ignore_index=True)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert result["vmcv_min_attente_min"].iloc[0]   == pytest.approx(2.0)
        assert result["vmcv_delta_attente_min"].iloc[0] == pytest.approx(3.0)

    def test_aucun_vmcv_nan(self) -> None:
        """Sans alternative VMCV (passages vides), attente et delta sont NaN."""
        r35 = _make_r35_train()
        result = _calculer_features(r35, _empty_vmcv_passages(), _make_mapping())
        assert pd.isna(result["vmcv_min_attente_min"].iloc[0])
        assert pd.isna(result["vmcv_delta_attente_min"].iloc[0])


# ---------------------------------------------------------------------------
# Tests — feature vmcv_delta_frequence_h
# ---------------------------------------------------------------------------


class TestDeltaFrequence:
    def test_zero_vmcv_nan(self) -> None:
        """0 VMCV dans ±30min → delta_frequence = NaN."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        result = _calculer_features(r35, _empty_vmcv_passages(), _make_mapping())
        assert pd.isna(result["vmcv_delta_frequence_h"].iloc[0])

    def test_un_vmcv_un_r35_delta_zero(self) -> None:
        """1 VMCV dans ±30min, 1 R35 (auto-inclusion) → delta = 1−1 = 0."""
        r35 = _make_r35_train(h_dep_min=8 * 60, numero_train=100)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 - 5)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(0.0)

    def test_trois_vmcv_un_r35_delta_positif(self) -> None:
        """3 VMCV dans ±30min, 1 R35 → delta = 3−1 = 2."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = pd.concat([
            _make_vmcv_passage(h_dep_min=8 * 60 - 20),
            _make_vmcv_passage(h_dep_min=8 * 60 - 5),
            _make_vmcv_passage(h_dep_min=8 * 60 + 10),
        ], ignore_index=True)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert result["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(2.0)

    def test_un_vmcv_trois_r35_delta_negatif(self) -> None:
        """1 VMCV dans ±30min, 3 R35 dans ±30min → delta = 1−3 = −2 pour le train central."""
        r35 = pd.concat([
            _make_r35_train(h_dep_min=8 * 60 - 20, numero_train=100),
            _make_r35_train(h_dep_min=8 * 60,      numero_train=101),
            _make_r35_train(h_dep_min=8 * 60 + 20, numero_train=102),
        ], ignore_index=True)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 - 5)
        result = _calculer_features(r35, vmcv, _make_mapping())
        row_101 = result[result["numero_train"] == 101]
        assert row_101["vmcv_delta_frequence_h"].iloc[0] == pytest.approx(-2.0)

    def test_vmcv_hors_freq_window_nan(self) -> None:
        """VMCV à h+60min (>30min) → 0 VMCV dans ±30min → NaN."""
        r35 = _make_r35_train(h_dep_min=8 * 60)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 + 60)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert pd.isna(result["vmcv_delta_frequence_h"].iloc[0])


# ---------------------------------------------------------------------------
# Tests — grain et colonnes de sortie
# ---------------------------------------------------------------------------


class TestGrainEtColonnes:
    def test_une_ligne_par_grain(self) -> None:
        """_calculer_features retourne exactement 1 ligne par (date, numero_train, sens)."""
        r35 = pd.concat([
            _make_r35_train(numero_train=100, sens="VV -> PLEI"),
            _make_r35_train(numero_train=101, sens="VV -> PLEI"),
            _make_r35_train(numero_train=100, sens="PLEI -> VV", gare_dep_bpuic=BPUIC_BLONAY),
        ], ignore_index=True)
        vmcv = _make_vmcv_passage(h_dep_min=8 * 60 - 5)
        result = _calculer_features(r35, vmcv, _make_mapping())
        assert len(result) == len(r35)
        assert result.duplicated(subset=GRAIN).sum() == 0

    def test_colonnes_exactes(self) -> None:
        """L'output contient exactement GRAIN + 4 features, rien de plus."""
        r35 = _make_r35_train()
        result = _calculer_features(r35, _empty_vmcv_passages(), _empty_mapping())
        expected = set(GRAIN + [
            "vmcv_n_lignes_concurrentes",
            "vmcv_min_attente_min",
            "vmcv_delta_attente_min",
            "vmcv_delta_frequence_h",
        ])
        assert set(result.columns) == expected

    def test_n_lignes_est_entier(self) -> None:
        """vmcv_n_lignes_concurrentes est un entier (pas float/NaN)."""
        r35 = _make_r35_train()
        result = _calculer_features(r35, _empty_vmcv_passages(), _empty_mapping())
        assert result["vmcv_n_lignes_concurrentes"].dtype in ("int64", "int32", "int")
        assert result["vmcv_n_lignes_concurrentes"].notna().all()


# ---------------------------------------------------------------------------
# Tests — haversine (inchangé, validé ici pour non-régression)
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_distance_nulle(self) -> None:
        d = _haversine_vec(0.0, 0.0, pd.Series([0.0]), pd.Series([0.0]))
        assert d.iloc[0] == pytest.approx(0.0, abs=1e-3)

    def test_distance_100m(self) -> None:
        d = _haversine_vec(LON_REF, LAT_REF, pd.Series([LON_REF]), pd.Series([LAT_100M]))
        assert d.iloc[0] == pytest.approx(100.0, rel=0.01)

    def test_distance_300m(self) -> None:
        d = _haversine_vec(LON_REF, LAT_REF, pd.Series([LON_REF]), pd.Series([LAT_300M]))
        assert d.iloc[0] == pytest.approx(300.0, rel=0.01)
