"""
tests/couche2/test_blocs.py
===========================
Tests du module canonique src/couche2/blocs.py :
  - parsing set-dedup (une rame ne s'accouple pas à elle-même)
  - signature de composition, fixture t1421 (course UM partielle, cas des 77)
  - mécanisme de whitelist (vide) + anomalies tolérées
  - garde-fou anti-doublon (tolère les 2 connus, RuntimeError sur tout nouveau)
  - comptes canoniques figés (garde-fou de régression) — nécessite les données + hash
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from couche2 import blocs  # noqa: E402


# ─────────────────────────── parsing set-dedup ────────────────────────────────
class TestParsing:
    def test_um_reelle(self):
        assert blocs.parse_rails("7505,7506") == frozenset({"7505", "7506"})

    def test_doublon_ecriture_est_simple(self):
        # cœur de l'arbitrage : un véhicule ne s'accouple pas à lui-même
        assert blocs.parse_rails("7508,7508") == frozenset({"7508"})
        assert len(blocs.parse_rails("7506,7506")) == 1

    def test_bus_et_vide(self):
        assert blocs.parse_rails("BUS") == frozenset()
        assert blocs.parse_rails(None) == frozenset()

    def test_raw_conserve_doublon(self):
        assert blocs._raw_rails("7508,7508") == ["7508", "7508"]  # brut = pour le garde-fou


# ─────────────────────── signature de composition (option 1) ──────────────────
class TestSignature:
    def test_um_simple_paire(self):
        is_um, compo, vehicles = blocs.course_signature(["7505,7506"])
        assert is_um is True
        assert compo == ("7505", "7506")
        assert vehicles == ("7505", "7506")

    def test_fixture_t1421_partielle(self):
        # 2023-10-06 t1421 : VV->BLON = 7502 (simple) | BLON->PLEI = 7502+7505 (UM)
        # une des 77 courses UM partielles -> UM entière, signature = jambe UM {7502,7505}
        is_um, compo, vehicles = blocs.course_signature(["7502", "7502,7505"])
        assert is_um is True
        assert compo == ("7502", "7505")          # rattachée au bloc de cette signature
        assert vehicles == ("7502", "7505")

    def test_releve_deux_simples_nest_pas_um(self):
        # deux jambes simples de véhicules différents (relève) != UM
        is_um, compo, vehicles = blocs.course_signature(["7502", "7505"])
        assert is_um is False
        assert compo == ()

    def test_doublon_course_est_simple(self):
        is_um, compo, _ = blocs.course_signature(["7508,7508"])
        assert is_um is False and compo == ()


# ─────────────────────────── whitelist & anomalies ────────────────────────────
class TestWhitelist:
    def test_corrections_vide(self):
        assert blocs.WHITELIST_CORRECTIONS == []            # aucune correction altérant la donnée

    def test_deux_anomalies_tolerees_declarees(self):
        tol = blocs.DOUBLONS_SAISIE_TOLERES
        assert len(tol) == 2
        cles = {(t["date"], t["numero_train"]) for t in tol}
        assert cles == {("2023-11-24", "1334"), ("2024-06-26", "1334")}
        for t in tol:                                        # structure tracée complète
            assert set(t) >= {"date", "numero_train", "composition", "disposition", "source"}


# ─────────────────────────── garde-fou anti-doublon ───────────────────────────
class TestGardeFouDoublon:
    def _df(self, rows):
        return pd.DataFrame(rows, columns=["date", "numero_train", "CompositionOrdreVehicules"])

    def test_tolere_les_deux_connus(self):
        df = self._df([
            (pd.Timestamp("2023-11-24"), "1334", "7508,7508"),
            (pd.Timestamp("2024-06-26"), "1334", "7506,7506"),
            (pd.Timestamp("2025-01-01"), "1400", "7505,7506"),   # UM saine
        ])
        blocs.check_no_unexpected_duplicates(df)             # ne doit PAS lever

    def test_leve_sur_nouveau_doublon(self):
        df = self._df([
            (pd.Timestamp("2025-03-15"), "1500", "7501,7501"),   # NOUVEAU doublon non listé
        ])
        with pytest.raises(RuntimeError, match="doublon"):
            blocs.check_no_unexpected_duplicates(df)


# ───────────────── comptes canoniques figés (intégration données) ─────────────
_DATA_OK = blocs.ML_DATASET.exists() and blocs.ROTATIONS.exists() and blocs.APC_STACKED.exists()


@pytest.mark.skipif(not _DATA_OK, reason="données canoniques absentes de l'environnement")
class TestComptesCanoniques:
    """Garde-fou de régression : fige les comptes canoniques (2026-07)."""

    @pytest.fixture(scope="class")
    def res(self):
        blocs.assert_canonical_dataset()                     # hash ba493568 dur
        return blocs.compute_baseline()

    def test_um_914_881(self, res):
        assert res["meta"]["n_UM_total"] == 914
        assert res["meta"]["n_UM_appariees_APC"] == 881

    def test_course_headline_intact(self, res):
        g = res["course"]["assises"]["global"]
        assert g["VP"] == 203 and g["FP"] == 678 and g["FN"] == 4845
        assert g["precision"] == pytest.approx(203 / 881, abs=1e-9)   # 23,0 % préservé
        assert g["rappel"] == pytest.approx(203 / 5048, abs=1e-9)

    def test_bloc_canonique_identite_composition(self, res):
        b = res["bloc"]["assises"]["bloc_canonique_identite_composition"]
        assert b["base_um_mesurees"] == 881
        assert b["n_blocs"] == 621
        assert b["justif_course"] == 203
        assert b["justif_bloc"] == 357               # 40,5 % PÉRIODE TOTALE (identité-composition)
        assert b["heritage"] == 154
        # R1 : fourchette RESTREINTE H25 (label shift => >> période totale)
        h25 = b["annee"]["H25"]
        assert (h25["justif_bloc"], h25["base_um_mesurees"]) == (246, 418)   # 58,9 % H25
        assert h25["heritage"] == 106

    def test_bloc_sensibilite_consecutivite_simple(self, res):
        # E1 : variante de robustesse conservée et étiquetée dans le JSON
        b = res["bloc"]["assises"]["bloc_sensibilite_consecutivite_simple"]
        assert b["n_blocs"] == 532
        assert b["justif_bloc"] == 403               # 45,7 % PÉRIODE TOTALE (consécutivité simple)
        assert b["heritage"] == 200
        assert b["annee"]["H25"]["justif_bloc"] == 279 and b["annee"]["H25"]["base_um_mesurees"] == 418  # 66,8 % H25
        # la variante canonique est un sous-ensemble strict : elle ne peut que retirer
        canon = res["bloc"]["assises"]["bloc_canonique_identite_composition"]
        assert canon["justif_bloc"] < b["justif_bloc"]
        assert canon["annee"]["H25"]["justif_bloc"] < b["annee"]["H25"]["justif_bloc"]

    def test_tour_permissif(self, res):
        t = res["tour"]["assises"]
        assert t["n_tours_UM"] == 1047
        assert t["precision_permissive"] == pytest.approx(0.7335, abs=5e-4)

    def test_ventilation_annee(self, res):
        a = res["course"]["assises"]["annee"]
        assert (a["H23"]["VP"], a["H23"]["UM_deployees"]) == (9, 82)
        assert (a["H24"]["VP"], a["H24"]["UM_deployees"]) == (54, 381)
        assert (a["H25"]["VP"], a["H25"]["UM_deployees"]) == (140, 418)   # 33,5 %

    def test_reference_phase2_H25(self, res):
        # D5 (C1) : barre iso-budget phase 2 = COUPLE précision-rappel humain H25 grain course
        ref = res["reference_phase2_course_H25"]
        assert ref["budget_UM_H25"] == 418               # courses-UM humaines DANS H25
        assert ref["n_surcharges_H25"] == 2072           # VP+FN = surcharges >63 en H25
        assert ref["global"]["VP"] == 140 and ref["global"]["FP"] == 278 and ref["global"]["FN"] == 1932
        assert ref["global"]["precision"] == pytest.approx(140 / 418, abs=1e-9)   # 33,5 %
        assert ref["global"]["rappel"] == pytest.approx(140 / 2072, abs=1e-9)     # 6,8 %
        # R4 : n de surcharges par segment (dénominateurs du rappel segmenté H25)
        assert ref["segment"]["haut"]["VP"] == 138 and ref["segment"]["haut"]["n_surcharges"] == 1224  # rappel 11,3 %
        assert ref["segment"]["bas"]["VP"] == 2 and ref["segment"]["bas"]["n_surcharges"] == 848        # rappel 0,24 %
