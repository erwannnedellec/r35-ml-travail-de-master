"""
tests/pipeline/test_histo_shift_dynamique.py
=============================================
Tests unitaires de la logique de shift dynamique des features histo_*
dans add_features_to_raw_stacked.py.

Aligné sur le comportement courant (ADR-062 + ADR-066, dataset ba493568) :

- Clé de groupement 5-termes (GROUP_KEYS) :
    base_sens × creneau_anchor_30 × cal_type_jour_3classes
    × id_gare_depart_bpuic × id_gare_arrivee_bpuic   (clé tronçon, ADR-062 §2)
- Cutoff MENSUEL composé (décision T-1 + ingestion APC), PAS le lag J-2 d'ADR-008 :
  pour une ligne de date D, le lag est la dernière occurrence du même groupe dont
  la date est ≤ cutoff_mensuel(D). Sur une série mensuelle (15 de chaque mois),
  le lag d'un mois pointe vers le mois précédent.

L'arithmétique exacte du cutoff et la présence du tronçon dans la clé sont
vérifiées au build sur données réelles par ``_assert_histo_conformite_adr_cf18``
(garde-fou in-pipeline) ; ces tests couvrent les invariants unitaires
(observed=True, fenêtre win7 cohérente, indépendance des groupes, NaN initial).

Usage
-----
    pytest tests/pipeline/test_histo_shift_dynamique.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ajouter scripts/ au chemin (tests/pipeline/ → parents[2] = racine projet)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from pipeline.add_features_to_raw_stacked import (  # noqa: E402
    add_derived_features,
    SEUIL_UM_2EME,
    _cutoff_mensuel_seuils,
)

# ---------------------------------------------------------------------------
# Constantes de test
# ---------------------------------------------------------------------------

_LAG2_COL = "histo_voyageurs_2eme_classe_lag2"
_WIN7_MEAN_COL = "histo_voyageurs_2eme_classe_win7_mean"
_WIN7_MAX_COL = "histo_voyageurs_2eme_classe_win7_max"

# Tronçon de référence pour les fixtures (clé 5-termes constante).
_SENS = "VV -> PLEI"
_CRENEAU = "08h00"
_TYPE = "ouvrable"
_DEP_BPUIC = 1000
_ARR_BPUIC = 2000


# ---------------------------------------------------------------------------
# Helper : construction d'une ligne minimale (clé 5-termes complète)
# ---------------------------------------------------------------------------

def _row(
    date: str,
    target_2eme: float,
    *,
    type_jour: str = _TYPE,
    creneau: str = _CRENEAU,
    dep_bpuic: int = _DEP_BPUIC,
    arr_bpuic: int = _ARR_BPUIC,
    sens: str = _SENS,
) -> dict:
    """Retourne un dict avec toutes les colonnes requises par add_derived_features
    (les 5 GROUP_KEYS + date + targets + colonnes calendaires/offre)."""
    return {
        # --- clé de groupement 5-termes (ADR-062) ---
        "base_sens": sens,
        "creneau_anchor_30": creneau,
        "cal_type_jour_3classes": type_jour,
        "id_gare_depart_bpuic": dep_bpuic,
        "id_gare_arrivee_bpuic": arr_bpuic,
        # --- date + cibles ---
        "base_date": pd.Timestamp(date),
        "target_voyageurs_1ere_classe": 2.0,
        "target_voyageurs_2eme_classe": float(target_2eme),
        # --- calendaires / offre requises par add_derived_features ---
        "cal_heure_depart": 8,
        "cal_minute_depart": 0,
        "cal_heure_arrivee": 8,
        "cal_minute_arrivee": 30,
        "base_offre_1ere_classe": 10.0,
        "base_offre_2eme_classe": 100.0,
    }


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _serie_mensuelle(targets: list[float], start_month: str = "2024-01", **kw) -> pd.DataFrame:
    """Série d'occurrences au 15 de mois consécutifs (cutoff mensuel → lag = mois précédent)."""
    starts = pd.date_range(start=f"{start_month}-01", periods=len(targets), freq="MS")
    dates = starts + pd.Timedelta(days=14)  # le 15 de chaque mois
    return _make_df([_row(str(d.date()), t, **kw) for d, t in zip(dates, targets)])


# ===========================================================================
# Test 0 — Sanity : le cutoff est mensuel composé, pas J-2
# ===========================================================================

class TestCutoffMensuel:
    def test_cutoff_pointe_mois_precedent(self):
        """Pour le 15 mars, le seuil est le dernier jour de février (mois précédent)."""
        seuils = _cutoff_mensuel_seuils(np.array([np.datetime64("2024-03-15")]))
        assert pd.Timestamp(seuils[0]) == pd.Timestamp("2024-02-29")

    def test_cutoff_nest_pas_j_moins_2(self):
        """Le cutoff est à ~1 mois, jamais à J-2 (régression ADR-008)."""
        d = np.datetime64("2024-03-15")
        seuil = pd.Timestamp(_cutoff_mensuel_seuils(np.array([d]))[0])
        gap = (pd.Timestamp("2024-03-15") - seuil).days
        assert gap >= 10, f"gap cutoff = {gap} j (un lag J-2 donnerait ~2 j)"


# ===========================================================================
# Test 1 — observed=True : pas de lignes fantômes avec dtype category
# ===========================================================================

class TestObservedTrue:
    """Avec un dtype category contenant des catégories non utilisées, le groupby
    ne doit pas créer de lignes fantômes (observed=True, ADR-037)."""

    def test_row_count_preserved_avec_categorical(self):
        df = _serie_mensuelle([10, 20, 30, 40, 50])
        df["cal_type_jour_3classes"] = pd.Categorical(
            df["cal_type_jour_3classes"], categories=["ouvrable", "samedi", "dimanche_ferie"]
        )
        assert str(df["cal_type_jour_3classes"].dtype) == "category"

        enriched = add_derived_features(df)

        assert len(enriched) == len(df), (
            f"Nombre de lignes modifié : {len(df)} → {len(enriched)}. "
            "Probable bug observed=False (lignes fantômes créées par groupby)."
        )


# ===========================================================================
# Test 2 — Shift dynamique mensuel : lag = occurrence du mois précédent
# ===========================================================================

class TestShiftMensuel:
    """Sur une série au 15 de chaque mois, le cutoff mensuel fait pointer le lag
    vers le 15 du mois précédent (la 1ère occurrence n'a pas d'antécédent)."""

    def test_premiere_occurrence_nan(self):
        df = _serie_mensuelle([10, 20, 30])
        enriched = add_derived_features(df)
        lag0 = enriched.loc[enriched["base_date"] == pd.Timestamp("2024-01-15"), _LAG2_COL].iloc[0]
        assert np.isnan(lag0), "1ère occurrence : aucun mois consolidé → lag NaN"

    @pytest.mark.parametrize("query_date,expected_lag", [
        ("2024-02-15", 10.0),   # cutoff = 31 jan → 15 jan (target 10)
        ("2024-03-15", 20.0),   # cutoff = 29 fév → 15 fév (target 20)
        ("2024-04-15", 30.0),   # cutoff = 31 mar → 15 mar (target 30)
    ])
    def test_lag_est_mois_precedent(self, query_date, expected_lag):
        df = _serie_mensuelle([10, 20, 30, 40])
        enriched = add_derived_features(df)
        lag = enriched.loc[enriched["base_date"] == pd.Timestamp(query_date), _LAG2_COL].iloc[0]
        assert lag == pytest.approx(expected_lag), (
            f"Pour {query_date} : attendu lag={expected_lag} (mois précédent), obtenu {lag}."
        )


# ===========================================================================
# Test 3 — Couverture lag2 ≥ 95 % par type_jour sur stage_08 réel
# ===========================================================================

_STAGE08_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "stage_08_features.parquet"


@pytest.mark.skipif(
    not _STAGE08_PATH.exists(),
    reason=f"stage_08_features.parquet absent ({_STAGE08_PATH}) — run pipeline d'abord",
)
class TestCouvertureStage08:
    """Sur le stage_08 réel, histo_voyageurs_2eme_classe_lag2 doit avoir une
    couverture ≥ 95 % pour chaque type_jour."""

    @pytest.fixture(scope="class")
    def stage08(self):
        return pd.read_parquet(
            _STAGE08_PATH,
            columns=[_LAG2_COL, "cal_type_jour_3classes", "horaire_annee_horaire"],
        )

    @pytest.mark.parametrize("type_jour", ["ouvrable", "samedi", "dimanche_ferie"])
    def test_couverture_lag2_par_type_jour(self, stage08, type_jour):
        sub = stage08[stage08["cal_type_jour_3classes"] == type_jour]
        assert len(sub) > 0, f"Aucune ligne pour type_jour={type_jour}"
        coverage = sub[_LAG2_COL].notna().mean()
        assert coverage >= 0.95, (
            f"[{type_jour}] Couverture lag2 = {coverage:.4f} < seuil 0.95. "
            "Vérifier observed=True / cutoff mensuel dans le pipeline."
        )


# ===========================================================================
# Test 4 — Indépendance des groupes (clé tronçon) : 1ère obs de chaque groupe NaN
# ===========================================================================

class TestIndependanceGroupes:
    """Deux tronçons distincts (gares bpuic différentes) sont des groupes
    indépendants : la 1ère occurrence de chacun a lag NaN, et l'historique
    d'un tronçon ne contamine pas l'autre (ADR-062 §2)."""

    def test_premiere_obs_deux_troncons(self):
        # Groupe A : tronçon 1000→2000 ; Groupe B : tronçon 2000→3000
        a = _serie_mensuelle([10, 20, 30], dep_bpuic=1000, arr_bpuic=2000)
        b = _serie_mensuelle([11, 22, 33], dep_bpuic=2000, arr_bpuic=3000)
        enriched = add_derived_features(pd.concat([a, b], ignore_index=True))

        for dep, arr in [(1000, 2000), (2000, 3000)]:
            first = enriched.loc[
                (enriched["id_gare_depart_bpuic"] == dep)
                & (enriched["id_gare_arrivee_bpuic"] == arr)
                & (enriched["base_date"] == pd.Timestamp("2024-01-15")),
                _LAG2_COL,
            ].iloc[0]
            assert np.isnan(first), f"1ère obs tronçon {dep}→{arr} doit avoir lag NaN"

    def test_lag_isole_par_troncon(self):
        """Le lag de février du tronçon B = sa propre valeur de janvier (11), pas A (10)."""
        a = _serie_mensuelle([10, 20], dep_bpuic=1000, arr_bpuic=2000)
        b = _serie_mensuelle([11, 22], dep_bpuic=2000, arr_bpuic=3000)
        enriched = add_derived_features(pd.concat([a, b], ignore_index=True))
        lag_b_fev = enriched.loc[
            (enriched["id_gare_depart_bpuic"] == 2000)
            & (enriched["id_gare_arrivee_bpuic"] == 3000)
            & (enriched["base_date"] == pd.Timestamp("2024-02-15")),
            _LAG2_COL,
        ].iloc[0]
        assert lag_b_fev == pytest.approx(11.0)


# ===========================================================================
# Test 5 — Cohérence interne de la fenêtre win7
# ===========================================================================

class TestWin7Invariants:
    """win7_max ≥ win7_mean et win7_n_surcharges ∈ [0, 7] sur toutes lignes non-NaN."""

    @pytest.fixture
    def df_12_mois(self) -> pd.DataFrame:
        # 12 occurrences mensuelles avec valeurs variées (dont des surcharges > seuil 63)
        return _serie_mensuelle([20, 45, 80, 110, 35, 95, 60, 15, 100, 50, 75, 30])

    def test_win7_max_gte_win7_mean(self, df_12_mois):
        enriched = add_derived_features(df_12_mois)
        mask = enriched[_WIN7_MAX_COL].notna() & enriched[_WIN7_MEAN_COL].notna()
        assert mask.sum() > 0, "Aucune ligne non-NaN — vérifier la fixture"
        violations = (enriched.loc[mask, _WIN7_MAX_COL] < enriched.loc[mask, _WIN7_MEAN_COL]).sum()
        assert violations == 0, (
            f"{violations} lignes violent win7_max ≥ win7_mean — bug de calcul de fenêtre."
        )

    def test_win7_n_surcharges_consistant(self, df_12_mois):
        col_nsur = "histo_voyageurs_2eme_classe_win7_n_surcharges"
        enriched = add_derived_features(df_12_mois)
        mask = enriched[col_nsur].notna() & enriched[_WIN7_MAX_COL].notna()

        assert (enriched.loc[mask, col_nsur] >= 0).all()
        assert (enriched.loc[mask, col_nsur] <= 7).all()

        # Si win7_max ≤ seuil → toutes les obs de la fenêtre sont sous le seuil → n_surcharges = 0
        mask_no_sur = mask & (enriched[_WIN7_MAX_COL] <= SEUIL_UM_2EME)
        if mask_no_sur.sum() > 0:
            assert (enriched.loc[mask_no_sur, col_nsur] == 0).all()
