"""
Ajoute le calendrier et les vacances/fériés vaudois à stage_02 (→ stage_03_calendrier).

Le grain de jointure est la date de circulation. La dimension source est
produite par scripts/build_dim_vacances_feries_vaud.py.

En plus de la jointure brute, le script calcule ``cal_type_jour``, une
catégorie métier à 9 niveaux (ponts, veilles/lendemains de fériés, etc.)
qui synthétise la nature du jour pour la modélisation.

Sources
-------
- data/processed/stage_02_annee_horaire.parquet
- data/dimension/dim_vacances_feries_vaud.parquet

Sortie
------
- data/processed/stage_03_calendrier.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_01_ANNEE, STAGE_02_CALENDRIER, DIM_VACANCES_FERIES  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402
from pipeline.utils import non_missing_mask  # noqa: E402

DATE_KEY_COLUMN = "base_date"
ANNEE_HORAIRE_COLUMN = "horaire_annee_horaire"
MERGE_DATE_COLUMN = "_date_jointure_vacances_feries_vaud"

# Colonnes extraites de la dimension (noms internes, avant prefixage)
DIM_PULL_COLUMNS = [
    "annee_civile",
    "mois",
    "jour",
    "jour_semaine_iso",
    "jour_semaine",
    "is_weekend",
    "is_vacances_scolaires_vaud",
    "is_ferie_vaud",
]

BOOLEAN_FEATURE_COLUMNS = [
    "is_weekend",
    "is_vacances_scolaires_vaud",
    "is_ferie_vaud",
]

# Colonnes temporaires ajoutees pour le calcul du type_jour (supprimees ensuite)
TEMP_CALENDAR_COLUMNS = ["_is_pont", "_is_veille_ferie", "_is_lendemain_ferie"]

TYPE_JOUR_CATEGORIES = [
    "dimanche_ou_ferie",
    "pont",
    "veille_ferie",
    "lendemain_ferie",
    "samedi_vacances",
    "samedi_hors_vacances",
    "vendredi_hors_vacances",
    "ouvrable_vacances",
    "ouvrable_hors_vacances",
]

# Catégories agrégées pour les rolling windows ISTDATEN (profil_train, correspondances).
# Regroupent les 9 classes métier en 3 classes comportementales stables.
TYPE_JOUR_3CLASSES = ["ouvrable", "samedi", "dimanche_ferie"]

_TYPE_JOUR_9_TO_3: dict[str, str] = {
    "dimanche_ou_ferie": "dimanche_ferie",
    "pont":              "ouvrable",
    "veille_ferie":      "ouvrable",
    "lendemain_ferie":   "ouvrable",
    "samedi_vacances":   "samedi",
    "samedi_hors_vacances": "samedi",
    "vendredi_hors_vacances": "ouvrable",
    "ouvrable_vacances": "ouvrable",
    "ouvrable_hors_vacances": "ouvrable",
}

# Renommage des colonnes calendrier/evenement avec prefixes semantiques
DIMENSION_COLUMN_RENAMES = {
    "annee_civile":             "cal_annee_civile",
    "mois":                     "cal_mois",
    "jour":                     "cal_jour",
    "jour_semaine_iso":         "cal_jour_semaine_iso",
    "jour_semaine":             "cal_jour_semaine",
    "is_weekend":               "cal_is_weekend",
    "is_vacances_vaud":         "event_is_vacances_vaud",
    "is_ferie_vaud":            "event_is_ferie_vaud",
    "is_vacances_ou_ferie_vaud": "event_is_vacances_ou_ferie_vaud",
    "type_jour":                "cal_type_jour",
    "type_jour_3classes":       "cal_type_jour_3classes",
}

# Colonnes presentes dans la sortie (noms prefixes) — utilisees pour le drop idempotent et l'ordre
DIMENSION_FEATURE_COLUMNS = [
    "cal_annee_civile",
    "cal_mois",
    "cal_mois_horaire",
    "cal_jour",
    "cal_jour_semaine_iso",
    "cal_jour_semaine",
    "cal_is_weekend",
    "event_is_vacances_vaud",
    "event_is_ferie_vaud",
    "event_is_vacances_ou_ferie_vaud",
    "cal_type_jour",
    "cal_type_jour_3classes",
]


# -----------------------------------------------------------------------------
# Lecture et validation
# -----------------------------------------------------------------------------

DIM_DATE_KEY = "date"


def read_dim_vacances_feries() -> pd.DataFrame:
    dim = read_stage(DIM_VACANCES_FERIES, DIM_VACANCES_FERIES.with_suffix(".csv"))

    required_columns = {DIM_DATE_KEY, *DIM_PULL_COLUMNS}
    missing_columns = sorted(required_columns - set(dim.columns))
    if missing_columns:
        raise ValueError(
            "Colonnes manquantes dans dim_vacances_feries_vaud: "
            f"{missing_columns}"
        )

    dim = dim[[DIM_DATE_KEY, *DIM_PULL_COLUMNS]].copy()
    dim[DIM_DATE_KEY] = parse_dates(dim[DIM_DATE_KEY], "dimension.date")

    duplicate_mask = dim[DIM_DATE_KEY].duplicated(keep=False)
    if duplicate_mask.any():
        examples = dim.loc[duplicate_mask, DIM_DATE_KEY].head(5)
        raise ValueError(
            "Dates dupliquees dans dim_vacances_feries_vaud: "
            f"{examples.dt.strftime('%Y-%m-%d').tolist()}"
        )

    for column in BOOLEAN_FEATURE_COLUMNS:
        dim[column] = dim[column].astype(bool)

    return dim.sort_values(DIM_DATE_KEY).reset_index(drop=True)


def parse_dates(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce").dt.normalize()
    invalid_mask = non_missing_mask(values) & parsed.isna()
    if invalid_mask.any():
        examples = values.loc[invalid_mask].drop_duplicates().head(5).tolist()
        raise ValueError(f"Dates invalides dans {column}: {examples}")

    return parsed


# -----------------------------------------------------------------------------
# Calendrier metier (pont / veille / lendemain)
# -----------------------------------------------------------------------------

def build_date_calendar(dim: pd.DataFrame) -> pd.DataFrame:
    """Calcule is_pont, is_veille_ferie, is_lendemain_ferie a partir de la dimension calendrier."""
    cal = dim[[DIM_DATE_KEY, "is_ferie_vaud", "is_weekend"]].copy()
    cal = cal.sort_values(DIM_DATE_KEY).reset_index(drop=True)

    one_day = pd.Timedelta(days=1)
    non_working_map = dict(zip(cal[DIM_DATE_KEY], cal["is_ferie_vaud"] | cal["is_weekend"]))
    ferie_map = dict(zip(cal[DIM_DATE_KEY], cal["is_ferie_vaud"]))

    prev_dates = cal[DIM_DATE_KEY] - one_day
    next_dates = cal[DIM_DATE_KEY] + one_day

    cal["_prev_non_working"] = prev_dates.map(non_working_map).fillna(True).astype(bool)
    cal["_next_non_working"] = next_dates.map(non_working_map).fillna(True).astype(bool)
    cal["_next_is_ferie"] = next_dates.map(ferie_map).fillna(False).astype(bool)
    cal["_prev_is_ferie"] = prev_dates.map(ferie_map).fillna(False).astype(bool)

    is_weekday = ~cal["is_weekend"].astype(bool)
    not_ferie = ~cal["is_ferie_vaud"].astype(bool)

    # Pont : jour ouvrable encadre de deux jours non travailles (ferie ou weekend)
    cal["_is_pont"] = is_weekday & not_ferie & cal["_prev_non_working"] & cal["_next_non_working"]
    # Veille de ferie : jour ouvrable dont le lendemain est un ferie
    cal["_is_veille_ferie"] = is_weekday & not_ferie & cal["_next_is_ferie"]
    # Lendemain de ferie : jour ouvrable dont la veille etait un ferie
    cal["_is_lendemain_ferie"] = is_weekday & not_ferie & cal["_prev_is_ferie"]

    return cal[[DIM_DATE_KEY, "_is_pont", "_is_veille_ferie", "_is_lendemain_ferie"]]


def compute_type_jour(enriched: pd.DataFrame) -> pd.Series:
    """Calcule type_jour selon 9 categories metier, par priorite decroissante."""
    iso = pd.to_numeric(enriched["jour_semaine_iso"], errors="coerce")
    is_ferie = enriched["is_ferie_vaud"].astype(bool)
    is_vacances = enriched["is_vacances_vaud"].astype(bool)
    is_weekend = enriched["is_weekend"].astype(bool)
    is_pont = enriched["_is_pont"].astype(bool)
    is_veille = enriched["_is_veille_ferie"].astype(bool)
    is_lendemain = enriched["_is_lendemain_ferie"].astype(bool)

    is_weekday = ~is_weekend
    not_ferie = ~is_ferie
    not_pont = ~is_pont

    conditions = [
        is_ferie | (iso == 7),                                            # dimanche_ou_ferie
        is_weekday & not_ferie & is_pont,                                 # pont
        is_weekday & not_ferie & not_pont & is_veille,                    # veille_ferie
        is_weekday & not_ferie & not_pont & is_lendemain,                 # lendemain_ferie
        (iso == 6) & is_vacances,                                         # samedi_vacances
        (iso == 6) & ~is_vacances,                                        # samedi_hors_vacances
        (iso == 5) & not_ferie & not_pont & ~is_vacances,                 # vendredi_hors_vacances
        is_weekday & not_ferie & not_pont & is_vacances,                  # ouvrable_vacances
        is_weekday & not_ferie & not_pont,                                # ouvrable_hors_vacances
    ]

    return pd.Series(
        np.select(conditions, TYPE_JOUR_CATEGORIES, default="ouvrable_hors_vacances"),
        index=enriched.index,
        dtype="string",
    )


# -----------------------------------------------------------------------------
# Jointure
# -----------------------------------------------------------------------------

def add_vacances_feries_to_raw_stacked(
    raw_stacked: pd.DataFrame,
    dim_vacances_feries: pd.DataFrame,
) -> pd.DataFrame:
    if DATE_KEY_COLUMN not in raw_stacked.columns:
        raise ValueError(f"Colonne {DATE_KEY_COLUMN} absente de raw_stacked_annee_horaire")

    # Drop idempotent : supprime les colonnes de sortie si le script est relance sur donnees deja prefixees
    enriched = raw_stacked.drop(columns=DIMENSION_FEATURE_COLUMNS, errors="ignore").copy()
    enriched[MERGE_DATE_COLUMN] = parse_dates(enriched[DATE_KEY_COLUMN], "raw.date")

    # La dimension utilise "date" comme cle (nom interne non prefixe)
    dim_renamed = dim_vacances_feries.rename(columns={"date": MERGE_DATE_COLUMN})
    enriched = enriched.merge(
        dim_renamed,
        how="left",
        on=MERGE_DATE_COLUMN,
        validate="many_to_one",
    )

    if len(enriched) != len(raw_stacked):
        raise ValueError("La jointure vacances/feries a modifie le nombre de lignes")

    unmatched_mask = enriched["is_ferie_vaud"].isna()
    if unmatched_mask.any():
        examples = (
            enriched.loc[unmatched_mask, MERGE_DATE_COLUMN]
            .drop_duplicates()
            .sort_values()
            .head(10)
        )
        raise ValueError(
            f"{int(unmatched_mask.sum()):,} ligne(s) sans dimension vacances/feries. "
            f"Exemples de dates: {examples.dt.strftime('%Y-%m-%d').tolist()}"
        )

    # Jointure calendrier pour le calcul du type_jour (pendant que MERGE_DATE_COLUMN est dispo)
    calendar = build_date_calendar(dim_vacances_feries)
    enriched = enriched.merge(
        calendar.rename(columns={"date": MERGE_DATE_COLUMN}),
        how="left",
        on=MERGE_DATE_COLUMN,
    )

    enriched = enriched.drop(columns=[MERGE_DATE_COLUMN])

    # Calcul des variables finales avec noms internes (prefixage apres)
    enriched["is_vacances_vaud"] = enriched["is_vacances_scolaires_vaud"]
    enriched["is_vacances_ou_ferie_vaud"] = enriched["is_vacances_vaud"] | enriched["is_ferie_vaud"]
    enriched = enriched.drop(columns=["is_vacances_scolaires_vaud"])

    enriched["type_jour"] = compute_type_jour(enriched)
    enriched["type_jour_3classes"] = (
        enriched["type_jour"].map(_TYPE_JOUR_9_TO_3).astype("category")
    )
    enriched = enriched.drop(columns=TEMP_CALENDAR_COLUMNS)

    # Prefixage des colonnes calendrier/evenement
    enriched = enriched.rename(columns=DIMENSION_COLUMN_RENAMES)

    # cal_mois_horaire : position ordinale dans l'annee horaire sur 13 positions.
    # Chaque annee horaire contient DEUX mois de decembre :
    #   - Decembre d'ouverture (ex. dec.2015 pour H16) -> position  1  "Dec↑"
    #   - Janvier -> fevrier -> ... -> novembre           -> positions 2-12
    #   - Decembre de cloture (ex. dec.2016 pour H16) -> position 13  "Dec↓"
    # Cela evite de confondre le debut et la fin de l'annee horaire lors des analyses saisonnieres.
    # Extraction de l'annee numerique a partir du code "H16" -> 16 -> annee_civile_cloture = 2016
    horaire_num = pd.to_numeric(enriched[ANNEE_HORAIRE_COLUMN].str[1:], errors="coerce")
    annee_civile_cloture = (2000 + horaire_num).astype("Int16")

    # Base : formule originale (Dec → 1, Jan → 2, …, Nov → 12)
    mois_h = ((enriched["cal_mois"] - 12) % 12 + 1).astype("Int8")

    # Reclassification du Decembre de cloture en position 13
    closing_dec = (enriched["cal_mois"] == 12) & (enriched["cal_annee_civile"] == annee_civile_cloture)
    mois_h[closing_dec] = pd.array([13] * int(closing_dec.sum()), dtype="Int8")

    enriched["cal_mois_horaire"] = mois_h

    insert_after = (
        enriched.columns.get_loc(ANNEE_HORAIRE_COLUMN) + 1
        if ANNEE_HORAIRE_COLUMN in enriched.columns
        else enriched.columns.get_loc(DATE_KEY_COLUMN) + 1
    )
    raw_columns = [
        column for column in enriched.columns if column not in DIMENSION_FEATURE_COLUMNS
    ]
    ordered_columns = [
        *raw_columns[:insert_after],
        *DIMENSION_FEATURE_COLUMNS,
        *raw_columns[insert_after:],
    ]

    return enriched[ordered_columns]


# -----------------------------------------------------------------------------
# Resume
# -----------------------------------------------------------------------------

def print_summary(enriched: pd.DataFrame) -> None:
    print("\nJointure vacances / feries Vaud:")
    print(f"  lignes               : {len(enriched):,}")
    print(f"  dates distinctes     : {enriched[DATE_KEY_COLUMN].nunique():,}")
    print(f"  event_is_vacances_vaud     : {int(enriched['event_is_vacances_vaud'].sum()):,}")
    print(f"  event_is_ferie_vaud        : {int(enriched['event_is_ferie_vaud'].sum()):,}")
    print(f"  event_is_vacances_ou_ferie : {int(enriched['event_is_vacances_ou_ferie_vaud'].sum()):,}")
    print("\n  cal_type_jour (lignes):")
    counts = enriched["cal_type_jour"].value_counts()
    for cat in TYPE_JOUR_CATEGORIES:
        n = int(counts.get(cat, 0))
        print(f"    {cat:<30}: {n:>10,}")
    print("\n  cal_type_jour_3classes (lignes):")
    counts3 = enriched["cal_type_jour_3classes"].value_counts()
    for cat in TYPE_JOUR_3CLASSES:
        n = int(counts3.get(cat, 0))
        print(f"    {cat:<20}: {n:>10,}")


def main() -> None:
    raw_stacked = read_stage(STAGE_01_ANNEE, STAGE_01_ANNEE.with_suffix(".csv"))
    dim_vacances_feries = read_dim_vacances_feries()
    enriched = add_vacances_feries_to_raw_stacked(raw_stacked, dim_vacances_feries)

    write_stage(enriched, STAGE_02_CALENDRIER)
    print_summary(enriched)


if __name__ == "__main__":
    main()
