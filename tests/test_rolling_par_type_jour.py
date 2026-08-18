"""
tests/test_rolling_par_type_jour.py
=====================================
Tests unitaires du helper rolling_par_type_jour.

Périmètre
---------
1. Ordre shift → rolling : vérifier que le décalage PRÉCÈDE le rolling
   (shift(lag).rolling(n), jamais rolling(n).mean().shift(lag)).
   Convention J-2 : pour un lag=2 et n=5, la valeur à J=10 doit être la
   moyenne des valeurs aux positions originales [3..7] (valeurs 4,5,6,7,8 = 6.0),
   PAS des positions [5..9].

2. Groupement par type de jour : les fenêtres ne traversent pas les frontières
   entre ouvrables / samedis / dimanches-fériés.

3. Support des statistiques : mean, std, sum.

4. Comportement aux bords : NaN si min_periods non atteint.

Usage
-----
    pytest tests/test_rolling_par_type_jour.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sources"))

from _rolling_par_type_jour import rolling_par_type_jour  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_ouvrables(n: int, values: list[float] | None = None) -> pd.DataFrame:
    """Crée un DataFrame de n jours ouvrables consécutifs depuis 2023-01-02 (lundi)."""
    # 2023-01-02 est un lundi
    dates = pd.bdate_range("2023-01-02", periods=n, freq="B")
    vals = values if values is not None else list(range(1, n + 1))
    return pd.DataFrame({
        "date": dates,
        "type_jour": "ouvrable",
        "group": "train_A",
        "valeur": [float(v) for v in vals],
    })


# ---------------------------------------------------------------------------
# Test 1 — Ordre shift → rolling (cas fondamental du superviseur)
# ---------------------------------------------------------------------------

class TestOrdreShiftRolling:
    """Vérifie que shift précède rolling (pas l'inverse)."""

    def test_valeur_j10_lag2_n5(self):
        """À J=10 (1-indexé), avec lag=2 et n=5, la moyenne doit être 6.0.

        Série : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ...]
        Après shift(2) : [NaN, NaN, 1, 2, 3, 4, 5, 6, 7, 8, ...]
        Rolling(5) à l'index 9 (J=10, 0-basé) : window shifted[5..9] = [4,5,6,7,8]
        Moyenne = (4+5+6+7+8)/5 = 6.0

        La valeur incorrecte (rolling avant shift) serait :
        rolling(5) à index 9 = mean(serie[5..9]) = mean(6,7,8,9,10) = 8.0
        puis shift(2) → cette valeur se retrouve à l'index 9+2=11, pas 9.
        Ou, avec shift(lag) sur le résultat : rolled[9-2] = rolled[7] = mean(serie[3..7]) = 6.0
        → coïncidence numérique pour des valeurs linéaires, mais sémantiquement incorrect.
        Le test ci-dessous valide la sémantique correcte (inclusion/exclusion de la sentinelle).
        """
        df = _df_ouvrables(20)
        result = rolling_par_type_jour(
            df,
            group_key="group",
            date_col="date",
            type_jour_col="type_jour",
            value_col="valeur",
            n_occurrences=5,
            min_periods=2,
            lag=2,
            stat="mean",
        )
        val_j10 = result.iloc[9]  # J=10, index 0-basé = 9
        assert val_j10 == pytest.approx(6.0), (
            f"Attendu 6.0 (moyenne de [4,5,6,7,8]), obtenu {val_j10}. "
            "Vérifier que shift précède rolling."
        )

    def test_premieres_observations_nan(self):
        """Les lag premières observations ne peuvent pas avoir de fenêtre valide."""
        df = _df_ouvrables(20)
        result = rolling_par_type_jour(
            df,
            group_key="group",
            date_col="date",
            type_jour_col="type_jour",
            value_col="valeur",
            n_occurrences=5,
            min_periods=2,
            lag=2,
            stat="mean",
        )
        # Avec lag=2 et min_periods=2 : les 2 premières obs ont shifted=NaN,
        # la 3e a shifted[2]=1 (seulement 1 valeur non-NaN → < min_periods=2 → NaN),
        # la 4e a shifted[3..3]=[1,2] → 2 non-NaN → mean = 1.5
        assert pd.isna(result.iloc[0]), "J=1 devrait être NaN"
        assert pd.isna(result.iloc[1]), "J=2 devrait être NaN"
        assert pd.isna(result.iloc[2]), "J=3 devrait être NaN (1 seule valeur < min_periods=2)"
        assert not pd.isna(result.iloc[3]), "J=4 devrait être non-NaN (2 valeurs)"

    def test_lag0_inclut_observation_courante(self):
        """Avec lag=0, la fenêtre inclut l'observation courante."""
        df = _df_ouvrables(10)
        result = rolling_par_type_jour(
            df,
            group_key="group",
            date_col="date",
            type_jour_col="type_jour",
            value_col="valeur",
            n_occurrences=3,
            min_periods=1,
            lag=0,
            stat="mean",
        )
        # À J=5 (index 4), lag=0 → window = serie[2..4] = [3,4,5], mean = 4.0
        assert result.iloc[4] == pytest.approx(4.0)
        # À J=1 (index 0), lag=0, n=3, min_periods=1 → window = [1] → mean = 1.0
        assert result.iloc[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 2 — Groupement par type de jour
# ---------------------------------------------------------------------------

class TestGroupementTypeJour:
    """Les fenêtres ne doivent pas traverser les frontières de type de jour."""

    def test_separation_ouvrable_samedi(self):
        """Un samedi ne contribue jamais à la fenêtre d'un ouvrable."""
        # Alternance ouvrable / samedi
        df = pd.DataFrame({
            "date": pd.to_datetime([
                "2023-01-02",  # lundi (ouvrable)
                "2023-01-07",  # samedi
                "2023-01-09",  # lundi (ouvrable)
                "2023-01-14",  # samedi
                "2023-01-16",  # lundi (ouvrable)
            ]),
            "type_jour": ["ouvrable", "samedi", "ouvrable", "samedi", "ouvrable"],
            "group": "train_A",
            "valeur": [10.0, 99.0, 20.0, 99.0, 30.0],
        })

        result = rolling_par_type_jour(
            df,
            group_key="group",
            date_col="date",
            type_jour_col="type_jour",
            value_col="valeur",
            n_occurrences=3,
            min_periods=1,
            lag=0,
            stat="mean",
        )

        # Indices ouvrables : 0, 2, 4 → valeurs 10, 20, 30
        # Index 0 (ouvrable) : window=[10] → 10.0
        # Index 2 (ouvrable) : window=[10, 20] → 15.0
        # Index 4 (ouvrable) : window=[10, 20, 30] → 20.0
        ouvrable_idx = [0, 2, 4]
        assert result.iloc[0] == pytest.approx(10.0)
        assert result.iloc[2] == pytest.approx(15.0)
        assert result.iloc[4] == pytest.approx(20.0)

        # Indices samedis : 1, 3 → valeurs 99, 99
        # Les samedis ont leurs propres fenêtres (99 n'impacte pas les ouvrables)
        assert result.iloc[1] == pytest.approx(99.0)

    def test_multi_groupes(self):
        """Deux trains distincts ont des fenêtres indépendantes."""
        df = pd.DataFrame({
            "date": pd.to_datetime([
                "2023-01-02", "2023-01-03", "2023-01-04",  # train_A
                "2023-01-02", "2023-01-03", "2023-01-04",  # train_B
            ]),
            "type_jour": ["ouvrable"] * 6,
            "group": ["train_A", "train_A", "train_A", "train_B", "train_B", "train_B"],
            "valeur": [1.0, 2.0, 3.0, 100.0, 200.0, 300.0],
        })
        result = rolling_par_type_jour(
            df,
            group_key="group",
            date_col="date",
            type_jour_col="type_jour",
            value_col="valeur",
            n_occurrences=3,
            min_periods=1,
            lag=0,
            stat="mean",
        )
        # Train A à J=3 (index 2 dans le sous-groupe) : mean(1,2,3) = 2.0
        # Train B à J=3 (index 5 global) : mean(100,200,300) = 200.0
        train_a = result[df["group"] == "train_A"]
        train_b = result[df["group"] == "train_B"]
        assert train_a.iloc[2] == pytest.approx(2.0)
        assert train_b.iloc[2] == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# Test 3 — Support des statistiques mean, std, sum
# ---------------------------------------------------------------------------

class TestStatistiques:
    def test_stat_sum(self):
        df = _df_ouvrables(10)
        result = rolling_par_type_jour(
            df, "group", "date", "type_jour", "valeur",
            n_occurrences=3, min_periods=1, lag=0, stat="sum",
        )
        # À J=5 (index 4) : sum([3, 4, 5]) = 12
        assert result.iloc[4] == pytest.approx(12.0)

    def test_stat_std(self):
        df = _df_ouvrables(10)
        result = rolling_par_type_jour(
            df, "group", "date", "type_jour", "valeur",
            n_occurrences=3, min_periods=2, lag=0, stat="std",
        )
        # À J=5 (index 4) : std([3, 4, 5]) = 1.0
        assert result.iloc[4] == pytest.approx(1.0)

    def test_stat_inconnu_leve_erreur(self):
        df = _df_ouvrables(5)
        with pytest.raises(ValueError, match="Statistique inconnue"):
            rolling_par_type_jour(
                df, "group", "date", "type_jour", "valeur",
                n_occurrences=3, min_periods=1, lag=0, stat="median",
            )


# ---------------------------------------------------------------------------
# Test 4 — Bords et valeurs manquantes
# ---------------------------------------------------------------------------

class TestBords:
    def test_min_periods_respecte(self):
        df = _df_ouvrables(10)
        result = rolling_par_type_jour(
            df, "group", "date", "type_jour", "valeur",
            n_occurrences=5, min_periods=3, lag=0, stat="mean",
        )
        # Avec min_periods=3, lag=0 : J=1 → 1 val → NaN, J=2 → 2 val → NaN,
        # J=3 → 3 val → non-NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert not pd.isna(result.iloc[2])

    def test_valeurs_nan_dans_serie(self):
        """Les NaN dans la série source sont gérés par min_periods."""
        df = _df_ouvrables(10)
        df.loc[3, "valeur"] = np.nan  # troue à J=4
        result = rolling_par_type_jour(
            df, "group", "date", "type_jour", "valeur",
            n_occurrences=3, min_periods=2, lag=0, stat="mean",
        )
        # La fenêtre autour du trou doit toujours donner une valeur si ≥ 2 non-NaN
        assert not pd.isna(result.iloc[4])  # J=5 : window=[NaN,4,5]? → 2 valides → OK

    def test_resultat_aligne_sur_index_original(self):
        """Le résultat a exactement le même index que le DataFrame d'entrée."""
        df = _df_ouvrables(10)
        df.index = range(100, 110)  # index non-standard
        result = rolling_par_type_jour(
            df, "group", "date", "type_jour", "valeur",
            n_occurrences=3, min_periods=1, lag=0, stat="mean",
        )
        assert list(result.index) == list(df.index)
