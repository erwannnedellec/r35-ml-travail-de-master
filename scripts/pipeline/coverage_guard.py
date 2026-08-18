"""
Garde de couverture mutualisable des dimensions événementielles (ADR-076).

Le défaut narcisses du gel précédent (corrigé par ADR-076) était un MÉCANISME SANS RAPPEL : une dim
tirée d'une constante calendaire figée à une année passée s'oublie sans bruit
quand les données avancent, là où les dims adossées à une source externe
re-parsée (manifestations : PDFs annuels ; ski : périodes officielles tenues à
jour) se maintiennent seules. Cette garde est le rappel manquant : au point où
la dim rencontre les données (le join du consommateur), elle échoue bruyamment
si la dim ne couvre pas la fin de la dernière période de données.

Conçue MUTUALISABLE : une seule fonction, réutilisable par les consommateurs
d'autres dims événementielles (ski à l'horizon H27, dont la ligne H26 s'arrête
au jour d'ouverture ; manifestations). Pour le gel ADR-076 elle est CÂBLÉE pour
narcisses seul ; son extension aux autres dims est une recommandation NON
appliquée (elle changerait leurs parquets, hors périmètre). Ne PAS la câbler sur
une dim dont la non-couverture est factuelle et volontaire (covid : zéro 2025).
"""

from __future__ import annotations

import pandas as pd


def assert_dim_couvre_periode_donnees(
    donnees_dates: pd.Series,
    dim_dates: pd.Series,
    *,
    nom_dim: str,
    adr: str = "ADR-076",
) -> None:
    """Échoue si la dimension ne couvre pas l'année la plus récente des données.

    Verdict à la granularité de l'ANNÉE : la dernière année couverte par la dim
    doit être supérieure ou égale à la dernière année présente dans les données.
    Suffisant pour intercepter le défaut narcisses (données 2025 présentes, dim
    narcisses arrêtée à 2024). Data-driven : la fin de la période de données est
    lue dans les données elles-mêmes, pas dans une constante (sinon on recrée la
    fragilité de la borne figée).

    Args:
        donnees_dates : dates observées dans les données (ex. df["base_date"]).
        dim_dates     : dates couvertes par la dimension (ex. dim["date"]).
        nom_dim       : nom de la dimension, pour le message d'erreur.
        adr           : ADR de référence cité dans le message.

    Raises:
        ValueError : si la dim ne couvre pas la fin de la période de données.
    """
    donnees = pd.to_datetime(donnees_dates, errors="coerce")
    dim = pd.to_datetime(dim_dates, errors="coerce")
    if donnees.notna().sum() == 0 or dim.notna().sum() == 0:
        return  # rien à comparer (données ou dim vides)

    annee_donnees = int(donnees.dt.year.max())
    annee_dim = int(dim.dt.year.max())
    if annee_dim < annee_donnees:
        raise ValueError(
            f"Garde de couverture ({nom_dim}) : la dimension s'arrête en {annee_dim} "
            f"alors que les données vont jusqu'en {annee_donnees}. Le producteur de "
            f"la dimension doit être étendu pour couvrir la fin de la période de "
            f"données (défaut de mécanisme sans rappel, {adr})."
        )
