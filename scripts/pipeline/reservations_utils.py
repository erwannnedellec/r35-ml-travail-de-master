"""
reservations_utils.py
=====================
Utilitaires de transformation des réservations de groupes ResSys
pour la pipeline R35.

Factorisation des fonctions du notebook ``02_data_understanding_ressys.ipynb``
(sections §1, §5.1, §5.2, §6.1).

Voir ADR-035 pour les décisions méthodologiques associées.
Voir notebook 02_ressys §9.4 pour le diagnostic du bug topologie GIL (Cause E),
motivation principale de ``build_line_order_from_ml``.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes publiques
# ---------------------------------------------------------------------------

#: Renommage colonnes brutes de l'export ResSys → noms normalisés snake_case (02_ressys §1, COL_RENAME).
COL_RENAME: dict[str, str] = {
    "Date de commande":          "date_commande",
    "Numéro de dossier":         "num_dossier",
    "Train N°":                  "numero_train",
    "Lieu de départ":            "gare_depart",
    "Lieu d'arrivée":            "gare_arrivee",
    "Date de voyage":            "date_voyage",
    "Catégorie de train":        "cat_train",
    "Transportunternehmen Reise":"tu",
    "Reiseart":                  "reiseart",
    "Partenaire commercial":     "partenaire",
    "Nom/Nom de groupe":         "nom_groupe",
    "Passagers 1ère cl.":        "pax_1c",
    "Passagers 2ème cl.":        "pax_2c",
    "Canal de vente":            "canal",
    "Lieu de vente":             "lieu_vente",
    "Pays":                      "pays",
    "Marché":                    "marche",
    "Sprache":                   "langue",
    "Statut de la réservation":  "statut",
}

#: Mapping nom de gare complet (export ResSys) → abréviation R35 (02_ressys §5.1).
GARE_MAP: dict[str, str] = {
    "Vevey":                 "VV",
    "Vevey Vignerons":       "VVVI",
    "Gilamont":              "GIL",
    "Hauteville":            "HTV",
    "Château-d'Hauteville":  "CHTV",
    "St-Légier-Gare":        "STLE",
    "St-Légier-Village":     "STLV",
    "La Chiésaz":            "CHIZ",
    "Château-de-Blonay":     "CHBL",
    "Blonay":                "BLON",
    "Prélaz-sur-Blonay":     "PRLZ",
    "Tusinge":               "TUS",
    "Les Chevalleyres":      "CHEV",
    "Bois-de-Chexbres":      "BCHX",
    "Fayaux":                "FAY",
    "Ondallaz-L'Alliaz":     "OND",
    "Lally":                 "LAL",
    "Les Pléiades":          "PLEI",
}

#: Statut réservation confirmée (seul statut utilisé pour les features J-1, ADR-035 §2.5).
STATUT_ABGESCHLOSSEN: str = "50 Abgeschlossen"

#: Seuil de latence minimum en jours — réservations connues à J-1 (ADR-035 §2.4).
LEAD_DAYS_MIN: int = 1

#: Keywords scolaires — sur ``nom_groupe`` + ``partenaire`` (ADR-035 §2.6, heuristique).
KEYWORDS_SCOLAIRE: tuple[str, ...] = (
    "ecole", "école", "scolaire", "classe", "school",
    "schule", "uape", "gym", "college", "enfant",
)

#: Keywords tour-opérateur — sur ``partenaire`` (ADR-035 §2.6, heuristique).
KEYWORDS_TOUR_OPERATOR: tuple[str, ...] = (
    "kuoni", "ake", "eisenbahn", "globus", "hotelplan",
    "tui", "tourisme", "tourism", "reise",
)


# ---------------------------------------------------------------------------
# Topologie
# ---------------------------------------------------------------------------

def build_line_order_from_ml(
    df_ml_annee: pd.DataFrame,
    dim_gare: pd.DataFrame,
) -> list[str]:
    """Déduit la topologie active de l'année à partir des tronçons présents dans ml_dataset.

    Corrige le bug topologie GIL identifié en notebook 02_ressys §9.4 (ADR-035 §2.3) :
    la LINE_ORDER statique issue de ``dim_gare`` incluait GIL pour toutes les
    années alors que GIL n'est desservi qu'en H22. En déduisant la topologie
    depuis les tronçons réels du ml_dataset, chaque année ne contient que ses
    gares actives.

    Parameters
    ----------
    df_ml_annee:
        Sous-ensemble du ml_dataset pour une seule année horaire.
        Doit contenir les colonnes ``id_gare_depart`` et ``id_gare_arrivee``.
    dim_gare:
        Table de référence des gares R35.
        Doit contenir les colonnes ``abreviation`` et ``ordre``.

    Returns
    -------
    list[str]
        Séquence ordonnée des abréviations de gares, du bas vers le haut
        de la ligne (VV → PLEI).
    """
    gares_actives = (
        set(df_ml_annee["id_gare_depart"].dropna().unique())
        | set(df_ml_annee["id_gare_arrivee"].dropna().unique())
    )
    return (
        dim_gare[dim_gare["abreviation"].isin(gares_actives)]
        .sort_values("ordre")["abreviation"]
        .tolist()
    )


def get_troncons_elementaires(
    gare_dep_code: str,
    gare_arr_code: str,
    line_order: list[str],
) -> list[tuple[str, str]] | None:
    """Retourne la liste ordonnée des tronçons élémentaires entre deux gares.

    Parameters
    ----------
    gare_dep_code:
        Abréviation de la gare de départ (ex. ``"VV"``).
    gare_arr_code:
        Abréviation de la gare d'arrivée (ex. ``"PLEI"``).
    line_order:
        Séquence ordonnée des gares (output de ``build_line_order_from_ml``).

    Returns
    -------
    list[tuple[str, str]]
        Liste de paires (depart, arrivee) des tronçons élémentaires parcourus,
        dans le sens du voyage. Liste vide si gare_dep == gare_arr.
    None
        Si l'une des gares n'est pas dans ``line_order`` (cas orphelin).
    """
    if gare_dep_code not in line_order or gare_arr_code not in line_order:
        return None

    idx_dep = line_order.index(gare_dep_code)
    idx_arr = line_order.index(gare_arr_code)

    if idx_dep == idx_arr:
        return []

    if idx_dep < idx_arr:
        segment = line_order[idx_dep : idx_arr + 1]
    else:
        segment = line_order[idx_arr : idx_dep + 1]
        segment = segment[::-1]

    return [(segment[i], segment[i + 1]) for i in range(len(segment) - 1)]


def eclate_reservation(
    row: pd.Series,
    line_order: list[str],
    gare_map: dict[str, str],
) -> list[dict]:
    """Éclate une réservation (voyage logique) en tronçons élémentaires.

    Chaque ligne enfant hérite de toutes les colonnes de la ligne parent et
    reçoit ``troncon_depart`` et ``troncon_arrivee`` pour les tronçons élémentaires.
    Les lignes orphelines (gare inconnue ou hors topologie) reçoivent
    ``orphelin=True`` et ``raison`` renseigné.

    Parameters
    ----------
    row:
        Ligne du DataFrame réservations après renommage (COL_RENAME).
    line_order:
        Topologie active de l'année horaire.
    gare_map:
        Mapping nom complet → abréviation (GARE_MAP).

    Returns
    -------
    list[dict]
        Liste de dicts (un par tronçon élémentaire). Liste vide si même gare
        départ/arrivée.
    """
    dep = gare_map.get(str(row.get("gare_depart", "")))
    arr = gare_map.get(str(row.get("gare_arrivee", "")))

    if dep is None or arr is None:
        return [{"orphelin": True, "raison": "gare_non_reconnue", **row.to_dict()}]

    troncons = get_troncons_elementaires(dep, arr, line_order)

    if troncons is None:
        return [{"orphelin": True, "raison": "gare_hors_topologie", **row.to_dict()}]

    if len(troncons) == 0:
        return []

    base = row.to_dict()
    result = []
    for tdep, tarr in troncons:
        child = base.copy()
        child["troncon_depart"] = tdep
        child["troncon_arrivee"] = tarr
        child["orphelin"] = False
        result.append(child)
    return result


# ---------------------------------------------------------------------------
# Heuristiques de classification
# ---------------------------------------------------------------------------

def is_scolaire(nom_groupe: str | None, partenaire: str | None) -> bool:
    """Heuristique de classification scolaire par keywords (ADR-035 §2.6).

    Recherche dans la concaténation lowercasée de ``nom_groupe`` et
    ``partenaire``. Heuristique approximative — validation MOB recommandée
    sur un échantillon de 50 réservations.

    Parameters
    ----------
    nom_groupe:
        Valeur de la colonne ``nom_groupe`` (peut être None ou NaN).
    partenaire:
        Valeur de la colonne ``partenaire`` (peut être None ou NaN).

    Returns
    -------
    bool
        True si au moins un keyword scolaire est présent.
    """
    combined = (
        ("" if nom_groupe is None or (isinstance(nom_groupe, float)) else str(nom_groupe))
        + " "
        + ("" if partenaire is None or (isinstance(partenaire, float)) else str(partenaire))
    ).lower()
    return any(kw in combined for kw in KEYWORDS_SCOLAIRE)


def is_tour_operator(partenaire: str | None) -> bool:
    """Heuristique de classification tour-opérateur par keywords (ADR-035 §2.6).

    Recherche dans ``partenaire`` lowercasé. Heuristique approximative.

    Parameters
    ----------
    partenaire:
        Valeur de la colonne ``partenaire`` (peut être None ou NaN).

    Returns
    -------
    bool
        True si au moins un keyword tour-opérateur est présent.
    """
    if partenaire is None or isinstance(partenaire, float):
        return False
    s = str(partenaire).lower()
    return any(kw in s for kw in KEYWORDS_TOUR_OPERATOR)
