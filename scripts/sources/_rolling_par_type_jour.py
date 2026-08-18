"""
_rolling_par_type_jour.py
==========================
Utilitaire de rolling window conditionnel par type de jour.

Utilisé par build_dim_profil_train.py et build_dim_correspondances_vevey.py
pour calculer des statistiques glissantes qui ne traversent que les occurrences
du même type de jour (ouvrable, samedi, dimanche_ferie).

Conventions du projet
---------------------
- Le paramètre lag défaut à 0 : la fenêtre inclut l'observation courante.
  La responsabilité du décalage opérationnel J-2 appartient exclusivement à
  la jointure dans add_istdaten_to_raw_stacked.py (base_date = date + 2j).
  Ne pas passer lag=2 ici — cela créerait un double-décalage (J-4 ou plus
  selon le type de jour).
- Groupe par service_id (encode déjà l'année horaire) — pas de chevauchement
  entre deux services du même numéro de train à des horaires différents.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_par_type_jour(
    df: pd.DataFrame,
    group_key: str | list[str],
    date_col: str,
    type_jour_col: str,
    value_col: str,
    n_occurrences: int,
    min_periods: int,
    lag: int = 0,
    stat: str = "mean",
) -> pd.Series:
    """Rolling window conditionnel par type de jour.

    Pour chaque (group_key, date), retourne une statistique calculée sur les
    ``n_occurrences`` dernières occurrences du **même type de jour** que la
    date courante, décalées de ``lag`` occurrences.

    Ordre garanti : shift(lag) est appliqué AVANT rolling(n_occurrences).
    Avec lag=0 (défaut), la fenêtre inclut l'observation courante.

    Le décalage opérationnel J-2 est géré par la jointure dans
    add_istdaten_to_raw_stacked.py, pas ici. Ne pas passer lag=2 — cela
    créerait un double-décalage (J-4 ou plus selon le type de jour).

    Args:
        df: DataFrame avec colonnes group_key, date_col, type_jour_col, value_col.
            N'a pas besoin d'être trié à l'avance.
        group_key: Nom(s) de colonne(s) identifiant le groupe (service_id ou
            liste de colonnes pour une clé composite).
        date_col: Colonne de date (datetime ou date).
        type_jour_col: Colonne catégorielle de type de jour (ex. "ouvrable").
        value_col: Colonne numérique sur laquelle calculer la statistique.
        n_occurrences: Taille de la fenêtre (nombre d'occurrences du même
            type de jour).
        min_periods: Nombre minimum d'observations valides pour calculer.
        lag: Décalage en nombre d'occurrences du même type de jour (défaut 0).
        stat: "mean", "std" ou "sum". Pour pct_en_retard, passer une colonne
            booléenne (0/1) en value_col et stat="mean".

    Returns:
        pd.Series alignée sur l'index de df.

    Raises:
        ValueError: Si ``stat`` est inconnu.
    """
    if stat not in {"mean", "std", "sum"}:
        raise ValueError(f"Statistique inconnue : {stat!r}. Attendu : 'mean', 'std' ou 'sum'.")

    result = pd.Series(np.nan, index=df.index, dtype="float64")

    # Normaliser group_key en liste pour le groupby multi-colonnes
    gk = [group_key] if isinstance(group_key, str) else list(group_key)

    for type_jour, sub in df.groupby(type_jour_col, dropna=True):
        sub = sub.copy()

        for _, grp in sub.groupby(gk, sort=False):
            grp_sorted = grp.sort_values(date_col)
            serie = grp_sorted[value_col].astype("float64")
            shifted = serie.shift(lag)

            if stat == "mean":
                rolled = shifted.rolling(n_occurrences, min_periods=min_periods).mean()
            elif stat == "std":
                rolled = shifted.rolling(n_occurrences, min_periods=min_periods).std()
            else:  # sum
                rolled = shifted.rolling(n_occurrences, min_periods=min_periods).sum()

            result.loc[grp_sorted.index] = rolled.values

    return result
