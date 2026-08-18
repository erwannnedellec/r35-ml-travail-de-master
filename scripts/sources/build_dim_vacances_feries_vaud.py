"""
Construit une dimension journaliere vacances scolaires et jours feries vaudois.

Le grain principal de sortie est une ligne par date. La table est concue pour
etre jointe plus tard aux donnees APC sur la date de circulation, comme les
tables meteo et STATPOP deja preparees pour le modele R35.

Sources vacances scolaires
--------------------------
- vacances_scolaires/Vacances_scolaires_vaudoises.pdf
- vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf

Les deux PDF locaux couvrent 2014-2015 a 2020-2021, puis 2022-2023 a
2030-2031. Le millesime 2021-2022, absent du dossier local, est complete avec
le calendrier officiel Vaud 2018-2026 publie sur vd.ch afin d'eviter un trou
dans les futures jointures.

Sources jours feries
--------------------
Les jours feries officiels vaudois retenus sont ceux listes par l'Etat de Vaud:
1er et 2 janvier, Vendredi Saint, Lundi de Paques, Ascension, Lundi de
Pentecote, 1er aout, Lundi du Jeune et Noel. Le jour de conge supplementaire
de l'administration cantonale, en principe le 26 decembre, n'est pas marque
comme jour ferie officiel.

Sorties
-------
- data/dimension/dim_vacances_feries_vaud.csv
- data/dimension/dim_vacances_feries_vaud.parquet
- data/dimension/dim_vacances_feries_vaud_evenements.csv
- data/dimension/dim_vacances_feries_vaud_evenements.parquet
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd


# -----------------------------------------------------------------------------
# Parametres d'entree / sortie
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VACANCES_SCOLAIRES_DIR = PROJECT_ROOT / "data" / "external" / "vacances_scolaires"

LOCAL_SOURCE_PDFS = [
    VACANCES_SCOLAIRES_DIR / "Vacances_scolaires_vaudoises.pdf",
    VACANCES_SCOLAIRES_DIR / "def_calendrier_vacances_scolaires_2023_2031.pdf",
]

OUTPUT_CSV_PATH = PROJECT_ROOT / "data" / "dimension" / "dim_vacances_feries_vaud.csv"
OUTPUT_PARQUET_PATH = (
    PROJECT_ROOT / "data" / "dimension" / "dim_vacances_feries_vaud.parquet"
)
OUTPUT_EVENTS_CSV_PATH = (
    PROJECT_ROOT / "data" / "dimension" / "dim_vacances_feries_vaud_evenements.csv"
)
OUTPUT_EVENTS_PARQUET_PATH = (
    PROJECT_ROOT / "data" / "dimension" / "dim_vacances_feries_vaud_evenements.parquet"
)

LOCAL_SOURCE_2014_2021 = "data/external/vacances_scolaires/Vacances_scolaires_vaudoises.pdf"
LOCAL_SOURCE_2023_2031 = (
    "data/external/vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf"
)
OFFICIAL_SOURCE_2018_2026 = (
    "https://www.vd.ch/fileadmin/user_upload/themes/formation/"
    "Vacances_scolaires/dfjc_calendrier_vacances_scolaires_2018_2026.pdf"
)
OFFICIAL_PUBLIC_HOLIDAYS_SOURCE = (
    "https://www.vd.ch/formation/jours-feries-et-vacances-scolaires/"
    "jours-feries-et-vacances-scolaires-2026"
)


# -----------------------------------------------------------------------------
# Calendrier scolaire Vaud
# -----------------------------------------------------------------------------

SCHOOL_YEAR_COLUMNS = [
    "annee_scolaire_vaud",
    "source_document",
    "rentree_scolaire",
    "lundi_jeune",
    "vacances_automne_debut",
    "vacances_automne_fin",
    "vacances_hiver_debut",
    "vacances_hiver_fin",
    "relaches_debut",
    "relaches_fin",
    "vacances_paques_debut",
    "vacances_paques_fin",
    "pont_ascension_debut",
    "pont_ascension_fin",
    "lundi_pentecote",
    "fin_annee_scolaire",
    "vacances_ete_debut",
    "vacances_ete_fin",
]

DATE_COLUMNS = SCHOOL_YEAR_COLUMNS[2:]

# Donnees transcrites depuis les PDF de vacances scolaires vaudoises.
# Chaque periode est inclusive: date_debut et date_fin sont toutes deux marquees.
SCHOOL_YEAR_DATA = [
    (
        "2014-2015",
        LOCAL_SOURCE_2014_2021,
        "2014-08-25",
        "2014-09-22",
        "2014-10-11",
        "2014-10-26",
        "2014-12-20",
        "2015-01-04",
        "2015-02-21",
        "2015-03-01",
        "2015-04-03",
        "2015-04-19",
        "2015-05-14",
        "2015-05-15",
        "2015-05-25",
        "2015-07-03",
        "2015-07-04",
        "2015-08-23",
    ),
    (
        "2015-2016",
        LOCAL_SOURCE_2014_2021,
        "2015-08-24",
        "2015-09-21",
        "2015-10-10",
        "2015-10-25",
        "2015-12-19",
        "2016-01-03",
        "2016-02-20",
        "2016-02-28",
        "2016-03-25",
        "2016-04-10",
        "2016-05-05",
        "2016-05-06",
        "2016-05-16",
        "2016-07-01",
        "2016-07-02",
        "2016-08-21",
    ),
    (
        "2016-2017",
        LOCAL_SOURCE_2014_2021,
        "2016-08-22",
        "2016-09-19",
        "2016-10-15",
        "2016-10-30",
        "2016-12-23",
        "2017-01-08",
        "2017-02-18",
        "2017-02-26",
        "2017-04-08",
        "2017-04-23",
        "2017-05-25",
        "2017-05-26",
        "2017-06-05",
        "2017-06-30",
        "2017-07-01",
        "2017-08-20",
    ),
    (
        "2017-2018",
        LOCAL_SOURCE_2014_2021,
        "2017-08-21",
        "2017-09-18",
        "2017-10-07",
        "2017-10-22",
        "2017-12-23",
        "2018-01-07",
        "2018-02-17",
        "2018-02-25",
        "2018-03-30",
        "2018-04-15",
        "2018-05-10",
        "2018-05-11",
        "2018-05-21",
        "2018-07-06",
        "2018-07-07",
        "2018-08-26",
    ),
    (
        "2018-2019",
        LOCAL_SOURCE_2014_2021,
        "2018-08-27",
        "2018-09-17",
        "2018-10-13",
        "2018-10-28",
        "2018-12-22",
        "2019-01-06",
        "2019-02-23",
        "2019-03-03",
        "2019-04-13",
        "2019-04-28",
        "2019-05-30",
        "2019-05-31",
        "2019-06-10",
        "2019-07-05",
        "2019-07-06",
        "2019-08-25",
    ),
    (
        "2019-2020",
        LOCAL_SOURCE_2014_2021,
        "2019-08-26",
        "2019-09-16",
        "2019-10-12",
        "2019-10-27",
        "2019-12-21",
        "2020-01-05",
        "2020-02-15",
        "2020-02-23",
        "2020-04-10",
        "2020-04-26",
        "2020-05-21",
        "2020-05-22",
        "2020-06-01",
        "2020-07-03",
        "2020-07-04",
        "2020-08-23",
    ),
    (
        "2020-2021",
        LOCAL_SOURCE_2014_2021,
        "2020-08-24",
        "2020-09-21",
        "2020-10-10",
        "2020-10-25",
        "2020-12-19",
        "2021-01-03",
        "2021-02-20",
        "2021-02-28",
        "2021-04-02",
        "2021-04-18",
        "2021-05-13",
        "2021-05-14",
        "2021-05-24",
        "2021-07-02",
        "2021-07-03",
        "2021-08-22",
    ),
    (
        "2021-2022",
        OFFICIAL_SOURCE_2018_2026,
        "2021-08-23",
        "2021-09-20",
        "2021-10-16",
        "2021-10-31",
        "2021-12-24",
        "2022-01-09",
        "2022-02-19",
        "2022-02-27",
        "2022-04-15",
        "2022-05-01",
        "2022-05-26",
        "2022-05-27",
        "2022-06-06",
        "2022-07-01",
        "2022-07-02",
        "2022-08-21",
    ),
    (
        "2022-2023",
        LOCAL_SOURCE_2023_2031,
        "2022-08-22",
        "2022-09-19",
        "2022-10-15",
        "2022-10-30",
        "2022-12-24",
        "2023-01-08",
        "2023-02-11",
        "2023-02-19",
        "2023-04-07",
        "2023-04-23",
        "2023-05-18",
        "2023-05-19",
        "2023-05-29",
        "2023-06-30",
        "2023-07-01",
        "2023-08-20",
    ),
    (
        "2023-2024",
        LOCAL_SOURCE_2023_2031,
        "2023-08-21",
        "2023-09-18",
        "2023-10-14",
        "2023-10-29",
        "2023-12-23",
        "2024-01-07",
        "2024-02-10",
        "2024-02-18",
        "2024-03-29",
        "2024-04-14",
        "2024-05-09",
        "2024-05-10",
        "2024-05-20",
        "2024-06-28",
        "2024-06-29",
        "2024-08-18",
    ),
    (
        "2024-2025",
        LOCAL_SOURCE_2023_2031,
        "2024-08-19",
        "2024-09-16",
        "2024-10-12",
        "2024-10-27",
        "2024-12-21",
        "2025-01-05",
        "2025-02-15",
        "2025-02-23",
        "2025-04-12",
        "2025-04-27",
        "2025-05-29",
        "2025-05-30",
        "2025-06-09",
        "2025-06-27",
        "2025-06-28",
        "2025-08-17",
    ),
    (
        "2025-2026",
        LOCAL_SOURCE_2023_2031,
        "2025-08-18",
        "2025-09-22",
        "2025-10-11",
        "2025-10-26",
        "2025-12-20",
        "2026-01-04",
        "2026-02-14",
        "2026-02-22",
        "2026-04-03",
        "2026-04-19",
        "2026-05-14",
        "2026-05-15",
        "2026-05-25",
        "2026-06-26",
        "2026-06-27",
        "2026-08-16",
    ),
    (
        "2026-2027",
        LOCAL_SOURCE_2023_2031,
        "2026-08-17",
        "2026-09-21",
        "2026-10-10",
        "2026-10-25",
        "2026-12-24",
        "2027-01-10",
        "2027-02-06",
        "2027-02-14",
        "2027-03-26",
        "2027-04-11",
        "2027-05-06",
        "2027-05-07",
        "2027-05-17",
        "2027-07-02",
        "2027-07-03",
        "2027-08-22",
    ),
    (
        "2027-2028",
        LOCAL_SOURCE_2023_2031,
        "2027-08-23",
        "2027-09-20",
        "2027-10-09",
        "2027-10-24",
        "2027-12-24",
        "2028-01-09",
        "2028-02-12",
        "2028-02-20",
        "2028-04-14",
        "2028-04-30",
        "2028-05-25",
        "2028-05-26",
        "2028-06-05",
        "2028-06-30",
        "2028-07-01",
        "2028-08-20",
    ),
    (
        "2028-2029",
        LOCAL_SOURCE_2023_2031,
        "2028-08-21",
        "2028-09-18",
        "2028-10-14",
        "2028-10-29",
        "2028-12-23",
        "2029-01-07",
        "2029-02-10",
        "2029-02-18",
        "2029-03-30",
        "2029-04-15",
        "2029-05-10",
        "2029-05-11",
        "2029-05-21",
        "2029-06-29",
        "2029-06-30",
        "2029-08-19",
    ),
    (
        "2029-2030",
        LOCAL_SOURCE_2023_2031,
        "2029-08-20",
        "2029-09-17",
        "2029-10-13",
        "2029-10-28",
        "2029-12-22",
        "2030-01-06",
        "2030-02-16",
        "2030-02-24",
        "2030-04-19",
        "2030-05-05",
        "2030-05-30",
        "2030-05-31",
        "2030-06-10",
        "2030-07-05",
        "2030-07-06",
        "2030-08-25",
    ),
    (
        "2030-2031",
        LOCAL_SOURCE_2023_2031,
        "2030-08-26",
        "2030-09-16",
        "2030-10-12",
        "2030-10-27",
        "2030-12-21",
        "2031-01-05",
        "2031-02-15",
        "2031-02-23",
        "2031-04-11",
        "2031-04-27",
        "2031-05-22",
        "2031-05-23",
        "2031-06-02",
        "2031-07-04",
        "2031-07-05",
        "2031-08-24",
    ),
]

SCHOOL_EVENT_CONFIG = [
    ("lundi_jeune", "lundi_jeune", "lundi_jeune", "Lundi du Jeune federal", False),
    (
        "vacances_automne",
        "vacances_automne_debut",
        "vacances_automne_fin",
        "Vacances d'automne",
        True,
    ),
    (
        "vacances_hiver",
        "vacances_hiver_debut",
        "vacances_hiver_fin",
        "Vacances d'hiver",
        True,
    ),
    ("relaches", "relaches_debut", "relaches_fin", "Relaches", True),
    (
        "vacances_paques",
        "vacances_paques_debut",
        "vacances_paques_fin",
        "Vacances de Paques",
        True,
    ),
    (
        "pont_ascension",
        "pont_ascension_debut",
        "pont_ascension_fin",
        "Pont de l'Ascension",
        False,
    ),
    (
        "lundi_pentecote",
        "lundi_pentecote",
        "lundi_pentecote",
        "Lundi de Pentecote",
        False,
    ),
    (
        "vacances_ete",
        "vacances_ete_debut",
        "vacances_ete_fin",
        "Vacances d'ete",
        True,
    ),
]

SCHOOL_MARKER_CONFIG = [
    (
        "rentree_scolaire",
        "rentree_scolaire",
        "Rentree scolaire",
        "is_rentree_scolaire_vaud",
    ),
    (
        "fin_annee_scolaire",
        "fin_annee_scolaire",
        "Fin de l'annee scolaire",
        "is_fin_annee_scolaire_vaud",
    ),
]

WEEKDAY_LABELS = {
    0: "lundi",
    1: "mardi",
    2: "mercredi",
    3: "jeudi",
    4: "vendredi",
    5: "samedi",
    6: "dimanche",
}


# -----------------------------------------------------------------------------
# Fonctions calendrier
# -----------------------------------------------------------------------------

def pipe_join(values) -> str:
    cleaned = sorted({str(value).strip() for value in values if str(value).strip()})
    return "|".join(cleaned)


def easter_sunday(year: int) -> date:
    """Calcule le dimanche de Paques gregorien."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def federal_fast_monday(year: int) -> date:
    """Retourne le lundi qui suit le Jeune federal."""
    current = date(year, 9, 1)
    days_until_sunday = (6 - current.weekday()) % 7
    first_sunday = current + timedelta(days=days_until_sunday)
    third_sunday = first_sunday + timedelta(days=14)
    return third_sunday + timedelta(days=1)


def read_school_years() -> pd.DataFrame:
    school_years = pd.DataFrame(SCHOOL_YEAR_DATA, columns=SCHOOL_YEAR_COLUMNS)
    for column in DATE_COLUMNS:
        school_years[column] = pd.to_datetime(school_years[column], format="%Y-%m-%d")

    return school_years


def validate_source_pdfs() -> None:
    missing_paths = [path for path in LOCAL_SOURCE_PDFS if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(f"PDF source introuvable(s): {missing_paths}")


def validate_school_years(school_years: pd.DataFrame) -> None:
    duplicate_years = school_years["annee_scolaire_vaud"].duplicated(keep=False)
    if duplicate_years.any():
        examples = school_years.loc[duplicate_years, "annee_scolaire_vaud"].tolist()
        raise ValueError(f"Annees scolaires dupliquees: {examples}")

    previous_end = None
    for row in school_years.sort_values("rentree_scolaire").itertuples(index=False):
        if previous_end is not None and row.rentree_scolaire != previous_end + pd.Timedelta(days=1):
            raise ValueError(
                "Trou ou chevauchement entre annees scolaires: "
                f"{previous_end.date()} -> {row.rentree_scolaire.date()}"
            )
        previous_end = row.vacances_ete_fin

        if row.rentree_scolaire.weekday() != 0:
            raise ValueError(f"Rentree non lundi pour {row.annee_scolaire_vaud}")
        if row.lundi_jeune.weekday() != 0:
            raise ValueError(f"Lundi du Jeune non lundi pour {row.annee_scolaire_vaud}")
        if row.pont_ascension_debut.weekday() != 3:
            raise ValueError(f"Pont de l'Ascension ne commence pas jeudi pour {row.annee_scolaire_vaud}")
        if row.pont_ascension_fin.weekday() != 4:
            raise ValueError(f"Pont de l'Ascension ne finit pas vendredi pour {row.annee_scolaire_vaud}")
        if row.lundi_pentecote.weekday() != 0:
            raise ValueError(f"Lundi de Pentecote non lundi pour {row.annee_scolaire_vaud}")
        if row.fin_annee_scolaire.weekday() != 4:
            raise ValueError(f"Fin d'annee scolaire non vendredi pour {row.annee_scolaire_vaud}")

        for event_type, start_column, end_column, _label, _is_vacation in SCHOOL_EVENT_CONFIG:
            start_date = getattr(row, start_column)
            end_date = getattr(row, end_column)
            if start_date > end_date:
                raise ValueError(
                    f"Periode invalide {event_type} pour {row.annee_scolaire_vaud}: "
                    f"{start_date.date()} > {end_date.date()}"
                )


def build_school_events(school_years: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for school_year in school_years.itertuples(index=False):
        for event_type, start_column, end_column, label, is_vacation in SCHOOL_EVENT_CONFIG:
            start_date = getattr(school_year, start_column)
            end_date = getattr(school_year, end_column)
            rows.append(
                {
                    "famille_evenement_vaud": "conge_scolaire_vaud",
                    "annee_scolaire_vaud": school_year.annee_scolaire_vaud,
                    "annee_civile": int(start_date.year),
                    "type_evenement_vaud": event_type,
                    "nom_evenement_vaud": label,
                    "date_debut": start_date,
                    "date_fin": end_date,
                    "nombre_jours": int((end_date - start_date).days) + 1,
                    "is_conge_scolaire_vaud": True,
                    "is_vacances_scolaires_vaud": bool(is_vacation),
                    "is_ferie_vaud": False,
                    "source_document": school_year.source_document,
                }
            )

        for marker_type, marker_column, label, _flag_column in SCHOOL_MARKER_CONFIG:
            marker_date = getattr(school_year, marker_column)
            rows.append(
                {
                    "famille_evenement_vaud": "repere_scolaire_vaud",
                    "annee_scolaire_vaud": school_year.annee_scolaire_vaud,
                    "annee_civile": int(marker_date.year),
                    "type_evenement_vaud": marker_type,
                    "nom_evenement_vaud": label,
                    "date_debut": marker_date,
                    "date_fin": marker_date,
                    "nombre_jours": 1,
                    "is_conge_scolaire_vaud": False,
                    "is_vacances_scolaires_vaud": False,
                    "is_ferie_vaud": False,
                    "source_document": school_year.source_document,
                }
            )

    return pd.DataFrame(rows).sort_values(["date_debut", "type_evenement_vaud"])


def build_public_holidays(start_year: int, end_year: int) -> pd.DataFrame:
    rows = []
    for year in range(start_year, end_year + 1):
        easter = easter_sunday(year)
        holiday_rows = [
            (date(year, 1, 1), "nouvel_an", "Nouvel An"),
            (date(year, 1, 2), "deux_janvier", "2 janvier"),
            (easter - timedelta(days=2), "vendredi_saint", "Vendredi Saint"),
            (easter + timedelta(days=1), "lundi_paques", "Lundi de Paques"),
            (easter + timedelta(days=39), "ascension", "Ascension"),
            (easter + timedelta(days=50), "lundi_pentecote", "Lundi de Pentecote"),
            (date(year, 8, 1), "fete_nationale", "Fete nationale"),
            (federal_fast_monday(year), "lundi_jeune", "Lundi du Jeune"),
            (date(year, 12, 25), "noel", "Noel"),
        ]
        for holiday_date, holiday_type, holiday_label in holiday_rows:
            rows.append(
                {
                    "famille_evenement_vaud": "ferie_vaud",
                    "annee_scolaire_vaud": pd.NA,
                    "annee_civile": year,
                    "type_evenement_vaud": holiday_type,
                    "nom_evenement_vaud": holiday_label,
                    "date_debut": pd.Timestamp(holiday_date),
                    "date_fin": pd.Timestamp(holiday_date),
                    "nombre_jours": 1,
                    "is_conge_scolaire_vaud": False,
                    "is_vacances_scolaires_vaud": False,
                    "is_ferie_vaud": True,
                    "source_document": OFFICIAL_PUBLIC_HOLIDAYS_SOURCE,
                }
            )

    return pd.DataFrame(rows).sort_values(["date_debut", "type_evenement_vaud"])


def expand_events_to_dates(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    conges = events.loc[events["is_conge_scolaire_vaud"]].copy()
    for event in conges.itertuples(index=False):
        for event_date in pd.date_range(event.date_debut, event.date_fin, freq="D"):
            rows.append(
                {
                    "date": event_date,
                    "annee_scolaire_vaud": event.annee_scolaire_vaud,
                    "type_conge_scolaire_vaud": event.type_evenement_vaud,
                    "nom_conge_scolaire_vaud": event.nom_evenement_vaud,
                    "is_vacances_scolaires_vaud": event.is_vacances_scolaires_vaud,
                    "source_vacances_scolaires_vaud": event.source_document,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "annee_scolaire_vaud",
                "type_conge_scolaire_vaud",
                "nom_conge_scolaire_vaud",
                "is_vacances_scolaires_vaud",
                "source_vacances_scolaires_vaud",
            ]
        )

    expanded = pd.DataFrame(rows)
    return (
        expanded.groupby("date", as_index=False)
        .agg(
            annee_scolaire_vaud_conge=("annee_scolaire_vaud", pipe_join),
            type_conge_scolaire_vaud=("type_conge_scolaire_vaud", pipe_join),
            nom_conge_scolaire_vaud=("nom_conge_scolaire_vaud", pipe_join),
            is_vacances_scolaires_vaud=("is_vacances_scolaires_vaud", "max"),
            source_vacances_scolaires_vaud=("source_vacances_scolaires_vaud", pipe_join),
        )
        .reset_index(drop=True)
    )


def aggregate_public_holidays(public_holidays: pd.DataFrame) -> pd.DataFrame:
    holidays = public_holidays.copy()
    holidays = holidays.rename(
        columns={
            "date_debut": "date",
            "type_evenement_vaud": "type_ferie_vaud",
            "nom_evenement_vaud": "nom_ferie_vaud",
            "source_document": "source_ferie_vaud",
        }
    )

    return (
        holidays.groupby("date", as_index=False)
        .agg(
            type_ferie_vaud=("type_ferie_vaud", pipe_join),
            nom_ferie_vaud=("nom_ferie_vaud", pipe_join),
            source_ferie_vaud=("source_ferie_vaud", pipe_join),
        )
        .reset_index(drop=True)
    )


def build_date_dimension(
    school_years: pd.DataFrame,
    school_events: pd.DataFrame,
    public_holidays: pd.DataFrame,
) -> pd.DataFrame:
    start_date = school_years["rentree_scolaire"].min()
    end_date = school_years["vacances_ete_fin"].max()
    dim = pd.DataFrame({"date": pd.date_range(start_date, end_date, freq="D")})

    dim["annee_civile"] = dim["date"].dt.year.astype("int16")
    dim["mois"] = dim["date"].dt.month.astype("int8")
    dim["jour"] = dim["date"].dt.day.astype("int8")
    dim["jour_semaine_iso"] = dim["date"].dt.isocalendar().day.astype("int8")
    dim["jour_semaine"] = dim["date"].dt.weekday.map(WEEKDAY_LABELS)
    dim["is_weekend"] = dim["jour_semaine_iso"].isin([6, 7])

    dim["annee_scolaire_vaud"] = pd.NA
    dim["source_annee_scolaire_vaud"] = pd.NA
    for school_year in school_years.itertuples(index=False):
        mask = dim["date"].between(
            school_year.rentree_scolaire,
            school_year.vacances_ete_fin,
            inclusive="both",
        )
        dim.loc[mask, "annee_scolaire_vaud"] = school_year.annee_scolaire_vaud
        dim.loc[mask, "source_annee_scolaire_vaud"] = school_year.source_document

    for _marker_type, marker_column, _label, flag_column in SCHOOL_MARKER_CONFIG:
        marker_dates = set(school_years[marker_column])
        dim[flag_column] = dim["date"].isin(marker_dates)

    expanded_school_events = expand_events_to_dates(school_events)
    dim = dim.merge(expanded_school_events, on="date", how="left")
    dim["is_conge_scolaire_vaud"] = dim["type_conge_scolaire_vaud"].notna()
    dim["is_vacances_scolaires_vaud"] = dim["is_vacances_scolaires_vaud"].eq(True)
    dim["is_pont_ascension_scolaire_vaud"] = (
        dim["type_conge_scolaire_vaud"].fillna("").str.contains("pont_ascension")
    )
    dim = dim.drop(columns=["annee_scolaire_vaud_conge"], errors="ignore")

    expanded_public_holidays = aggregate_public_holidays(public_holidays)
    dim = dim.merge(expanded_public_holidays, on="date", how="left")
    dim["is_ferie_vaud"] = dim["type_ferie_vaud"].notna()
    dim["is_conge_scolaire_ou_ferie_vaud"] = (
        dim["is_conge_scolaire_vaud"] | dim["is_ferie_vaud"]
    )

    return dim[
        [
            "date",
            "annee_civile",
            "mois",
            "jour",
            "jour_semaine_iso",
            "jour_semaine",
            "is_weekend",
            "annee_scolaire_vaud",
            "source_annee_scolaire_vaud",
            "is_rentree_scolaire_vaud",
            "is_fin_annee_scolaire_vaud",
            "is_conge_scolaire_vaud",
            "is_vacances_scolaires_vaud",
            "is_pont_ascension_scolaire_vaud",
            "type_conge_scolaire_vaud",
            "nom_conge_scolaire_vaud",
            "source_vacances_scolaires_vaud",
            "is_ferie_vaud",
            "type_ferie_vaud",
            "nom_ferie_vaud",
            "source_ferie_vaud",
            "is_conge_scolaire_ou_ferie_vaud",
        ]
    ].copy()


# -----------------------------------------------------------------------------
# Controles qualite
# -----------------------------------------------------------------------------

def validate_events(school_events: pd.DataFrame, public_holidays: pd.DataFrame) -> None:
    conges = school_events.loc[school_events["is_conge_scolaire_vaud"]].copy()
    expanded = expand_events_to_dates(conges)
    if expanded["date"].duplicated().any():
        examples = expanded.loc[expanded["date"].duplicated(keep=False), "date"].head(5)
        raise ValueError(f"Conges scolaires chevauchants: {examples.dt.date.tolist()}")

    public_duplicate_dates = public_holidays["date_debut"].duplicated(keep=False)
    if public_duplicate_dates.any():
        examples = public_holidays.loc[public_duplicate_dates, ["date_debut", "type_evenement_vaud"]]
        raise ValueError(f"Jours feries dupliques:\n{examples.head(10)}")

    public_by_type_year = public_holidays.set_index(["annee_civile", "type_evenement_vaud"])
    for event in conges.itertuples(index=False):
        if event.type_evenement_vaud not in {"lundi_jeune", "pont_ascension", "lundi_pentecote"}:
            continue

        public_type = {
            "lundi_jeune": "lundi_jeune",
            "pont_ascension": "ascension",
            "lundi_pentecote": "lundi_pentecote",
        }[event.type_evenement_vaud]
        public_date = public_by_type_year.loc[
            (event.date_debut.year, public_type),
            "date_debut",
        ]
        if event.date_debut != public_date:
            raise ValueError(
                f"Incoherence {event.type_evenement_vaud} {event.annee_scolaire_vaud}: "
                f"{event.date_debut.date()} != {public_date.date()}"
            )


def validate_dimension(dim: pd.DataFrame) -> None:
    if dim["date"].duplicated().any():
        raise ValueError("Dates dupliquees dans la dimension finale")

    if dim["annee_scolaire_vaud"].isna().any():
        examples = dim.loc[dim["annee_scolaire_vaud"].isna(), "date"].head(5)
        raise ValueError(f"Dates sans annee scolaire: {examples.dt.date.tolist()}")

    missing_source = dim.loc[
        dim["is_conge_scolaire_vaud"] & dim["source_vacances_scolaires_vaud"].isna(),
        "date",
    ]
    if not missing_source.empty:
        raise ValueError(
            "Conges scolaires sans source documentaire: "
            f"{missing_source.dt.date.head(5).tolist()}"
        )


def print_summary(dim: pd.DataFrame, events: pd.DataFrame) -> None:
    print("\nDimension vacances / feries Vaud:")
    print(f"  lignes journalieres       : {len(dim):,}")
    print(f"  debut                     : {dim['date'].min().date()}")
    print(f"  fin                       : {dim['date'].max().date()}")
    print(f"  annees scolaires          : {dim['annee_scolaire_vaud'].nunique():,}")
    print(f"  jours conge scolaire      : {int(dim['is_conge_scolaire_vaud'].sum()):,}")
    print(f"  jours vacances scolaires  : {int(dim['is_vacances_scolaires_vaud'].sum()):,}")
    print(f"  jours feries vaudois      : {int(dim['is_ferie_vaud'].sum()):,}")

    event_counts = events["famille_evenement_vaud"].value_counts().sort_index()
    print("\nEvenements sources:")
    for event_family, count in event_counts.items():
        print(f"  {event_family}: {count:,}")


def main() -> None:
    validate_source_pdfs()
    school_years = read_school_years()
    validate_school_years(school_years)

    start_year = int(school_years["rentree_scolaire"].dt.year.min())
    end_year = int(school_years["vacances_ete_fin"].dt.year.max())
    school_events = build_school_events(school_years)
    public_holidays = build_public_holidays(start_year, end_year)
    public_holidays = public_holidays.loc[
        public_holidays["date_debut"].between(
            school_years["rentree_scolaire"].min(),
            school_years["vacances_ete_fin"].max(),
            inclusive="both",
        )
    ].copy()
    validate_events(school_events, public_holidays)

    events = pd.concat([school_events, public_holidays], ignore_index=True).sort_values(
        ["date_debut", "famille_evenement_vaud", "type_evenement_vaud"]
    )
    dim = build_date_dimension(school_years, school_events, public_holidays)
    validate_dimension(dim)

    OUTPUT_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    dim.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    dim.to_parquet(OUTPUT_PARQUET_PATH, index=False)
    events.to_csv(OUTPUT_EVENTS_CSV_PATH, index=False, encoding="utf-8-sig")
    events.to_parquet(OUTPUT_EVENTS_PARQUET_PATH, index=False)

    print(f"{len(dim):,} lignes ecrites dans {OUTPUT_CSV_PATH}")
    print(f"{len(dim):,} lignes ecrites dans {OUTPUT_PARQUET_PATH}")
    print(f"{len(events):,} evenements ecrits dans {OUTPUT_EVENTS_CSV_PATH}")
    print(f"{len(events):,} evenements ecrits dans {OUTPUT_EVENTS_PARQUET_PATH}")
    print_summary(dim, events)


if __name__ == "__main__":
    main()
