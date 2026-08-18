import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    RAW,
    DIMENSION,
    APC_STACKED,
    RAW_DUPLICATES,
)

RAW_DIR                    = RAW
OUTPUT_PATH                = APC_STACKED.with_suffix(".csv")
PARQUET_OUTPUT_PATH        = APC_STACKED
DUPLICATES_PATH            = RAW_DUPLICATES.with_suffix(".csv")
DUPLICATES_PARQUET_PATH    = RAW_DUPLICATES
STATION_DIMENSION_PATH     = DIMENSION / "gare_abreviation.csv"
TRAFFIC_POINT_PATH         = DIMENSION / "full-world-traffic-point.csv"
TRAFFIC_POINT_FALLBACK_PATH = DIMENSION / "gare_GIL_CLIE.csv"

DATE_COLUMNS = {"date": "%d.%m.%Y"}
TRAIN_DIRECTION_BY_PARITY = {
    0: "PLEI -> VV",
    1: "VV -> PLEI",
}

STRING_COLUMNS = [
    "source_file",
    "gare_depart",
    "gare_arrivee",
    "code_justification",
    "mode_comptage",
    "source",
]

INTEGER_COLUMNS = [
    "numero_train",
    "code_et",
    "code_debiteur",
    "code_offre",
    "troncon_tgl",
    "tx_equipement_afz_1ere_classe",
    "tx_equipement_afz_2eme_classe",
    "offre_1ere_classe",
    "offre_2eme_classe",
    "voyageurs_1ere_classe",
    "voyageurs_2eme_classe",
    "groupes_1ere_classe",
    "groupes_2eme_classe",
    "places_disponibles_1ere_classe",
    "places_disponibles_2eme_classe",
    "passagers_montant_1ere_classe",
    "passagers_montant_2eme_classe",
    "passagers_descendants_1ere_classe",
    "passagers_descendants_2eme_classe",
    "divergence_horaire",
]

FLOAT_COLUMNS = [
    "distance_km",
    "tx_occupation_1ere_classe",
    "tx_occupation_2eme_classe",
]

# Colonnes du schema normalise (apres apply_schema) representant le contenu brut.
# Utilisees pour le dedoublonnage : elles correspondent aux colonnes du CSV source
# apres suppression de type_jour et remplacement de depart/arrivee par les datetimes.
RAW_SCHEMA_COLUMNS = [
    "date",
    "numero_train",
    "code_et",
    "code_debiteur",
    "gare_depart",
    "gare_arrivee",
    "code_offre",
    "troncon_tgl",
    "tx_equipement_afz_1ere_classe",
    "tx_equipement_afz_2eme_classe",
    "offre_1ere_classe",
    "offre_2eme_classe",
    "voyageurs_1ere_classe",
    "voyageurs_2eme_classe",
    "groupes_1ere_classe",
    "groupes_2eme_classe",
    "places_disponibles_1ere_classe",
    "places_disponibles_2eme_classe",
    "passagers_montant_1ere_classe",
    "passagers_montant_2eme_classe",
    "passagers_descendants_1ere_classe",
    "passagers_descendants_2eme_classe",
    "code_justification",
    "depart_datetime",
    "arrivee_datetime",
    "divergence_horaire",
    "mode_comptage",
    "source",
    "distance_km",
    "tx_occupation_1ere_classe",
    "tx_occupation_2eme_classe",
]

# Renommage final des colonnes avec prefixes semantiques.
# Applique apres le dedoublonnage, avant l'ecriture des fichiers de sortie.
FINAL_COLUMN_RENAMES: dict[str, str] = {
    # id_ : identifiants techniques non utilises directement comme features
    "source_file":                          "id_source_file",
    "gare_depart":                          "id_gare_depart",
    "gare_arrivee":                         "id_gare_arrivee",
    "gare_depart_bpuic":                    "id_gare_depart_bpuic",
    "gare_arrivee_bpuic":                   "id_gare_arrivee_bpuic",
    "code_et":                              "id_code_et",
    "code_debiteur":                        "id_code_debiteur",
    "code_offre":                           "id_code_offre",
    "code_justification":                   "id_code_justification",
    "mode_comptage":                        "id_mode_comptage",
    "source":                               "id_source",
    # target_ : variable cible
    "voyageurs_1ere_classe":                "target_voyageurs_1ere_classe",
    "voyageurs_2eme_classe":                "target_voyageurs_2eme_classe",
    # base_ : variables brutes utiles issues de la donnee APC/course
    "date":                                 "base_date",
    "sens":                                 "base_sens",
    "depart_datetime":                      "base_depart_datetime",
    "arrivee_datetime":                     "base_arrivee_datetime",
    "duree_troncon_minutes":                "base_duree_troncon_minutes",
    "offre_1ere_classe":                    "base_offre_1ere_classe",
    "offre_2eme_classe":                    "base_offre_2eme_classe",
    "groupes_1ere_classe":                  "base_groupes_1ere_classe",
    "groupes_2eme_classe":                  "base_groupes_2eme_classe",
    "places_disponibles_1ere_classe":       "base_places_disponibles_1ere_classe",
    "places_disponibles_2eme_classe":       "base_places_disponibles_2eme_classe",
    "passagers_montant_1ere_classe":        "base_passagers_montant_1ere_classe",
    "passagers_montant_2eme_classe":        "base_passagers_montant_2eme_classe",
    "passagers_descendants_1ere_classe":    "base_passagers_descendants_1ere_classe",
    "passagers_descendants_2eme_classe":    "base_passagers_descendants_2eme_classe",
    "tx_equipement_afz_1ere_classe":        "base_tx_equipement_afz_1ere_classe",
    "tx_equipement_afz_2eme_classe":        "base_tx_equipement_afz_2eme_classe",
    "tx_occupation_1ere_classe":            "base_tx_occupation_1ere_classe",
    "tx_occupation_2eme_classe":            "base_tx_occupation_2eme_classe",
    "divergence_horaire":                   "base_divergence_horaire",
    # horaire_ : structure de l'offre/horaire
    "numero_train":                         "horaire_numero_train",
    "troncon_tgl":                          "horaire_troncon_tgl",
    # cal_ : calendrier (composantes temporelles du trajet)
    "heure_depart":                         "cal_heure_depart",
    "minute_depart":                        "cal_minute_depart",
    "heure_arrivee":                        "cal_heure_arrivee",
    "minute_arrivee":                       "cal_minute_arrivee",
    # spatial_ : troncon, gare, altitude, territoire
    "distance_km":                          "spatial_distance_km",
    "gare_depart_nom":                      "spatial_gare_depart_nom",
    "gare_depart_locality_name":            "spatial_gare_depart_localite",
    "gare_depart_ordre":                    "spatial_gare_depart_ordre",
    "gare_depart_km":                       "spatial_gare_depart_km",
    "gare_depart_lv95East":                 "spatial_gare_depart_lv95east",
    "gare_depart_lv95North":                "spatial_gare_depart_lv95north",
    "gare_depart_wgs84East":                "spatial_gare_depart_wgs84east",
    "gare_depart_wgs84North":               "spatial_gare_depart_wgs84north",
    "gare_depart_height":                   "spatial_gare_depart_altitude",
    "gare_arrivee_nom":                     "spatial_gare_arrivee_nom",
    "gare_arrivee_locality_name":           "spatial_gare_arrivee_localite",
    "gare_arrivee_ordre":                   "spatial_gare_arrivee_ordre",
    "gare_arrivee_km":                      "spatial_gare_arrivee_km",
    "gare_arrivee_lv95East":                "spatial_gare_arrivee_lv95east",
    "gare_arrivee_lv95North":               "spatial_gare_arrivee_lv95north",
    "gare_arrivee_wgs84East":               "spatial_gare_arrivee_wgs84east",
    "gare_arrivee_wgs84North":              "spatial_gare_arrivee_wgs84north",
    "gare_arrivee_height":                  "spatial_gare_arrivee_altitude",
}


def rename_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in FINAL_COLUMN_RENAMES.items() if k in df.columns})


STATION_DIMENSION_RENAME = {
    "Gare_BPUIC": "bpuic",
    "Gare_abreviation": "abreviation",
    "Gare_nom": "nom",
    "Gare_Gare_localityName": "locality_name",
    "Gare_Ordre": "ordre",
    "Gare_Gare_km": "km",
}
STATION_DIMENSION_VALUE_COLUMNS = [
    "bpuic",
    "nom",
    "locality_name",
    "ordre",
    "km",
]
TRAFFIC_POINT_KEY_COLUMN = "number"
TRAFFIC_POINT_DATE_COLUMNS = ["validFrom", "validTo", "editionDate", "creationDate"]
TRAFFIC_POINT_COORDINATE_COLUMNS = [
    "lv95East",
    "lv95North",
    "wgs84East",
    "wgs84North",
    "height",
]
TRAFFIC_POINT_FALLBACK_RENAME = {
    "Gare_Gare_BPUIC": TRAFFIC_POINT_KEY_COLUMN,
    "Gare_lv95East": "lv95East",
    "Gare_lv95North": "lv95North",
    "Gare_wgs84East": "wgs84East",
    "Gare__wgs84North": "wgs84North",
}


def load_csv(path: Path, expected_columns: Optional[list[str]] = None) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    if expected_columns is not None and list(df.columns) != expected_columns:
        missing = sorted(set(expected_columns) - set(df.columns))
        extra = sorted(set(df.columns) - set(expected_columns))
        raise ValueError(
            f"Colonnes differentes dans {path}: "
            f"missing={missing or 'aucune'}, extra={extra or 'aucune'}"
        )

    df.insert(0, "source_file", path.name)
    return df


def non_missing_mask(values: pd.Series) -> pd.Series:
    strings = values.astype("string").str.strip()
    return strings.notna() & strings.ne("")


def raise_for_invalid_values(column: str, values: pd.Series, invalid_mask: pd.Series) -> None:
    if not invalid_mask.any():
        return

    examples = values.loc[invalid_mask].drop_duplicates().head(5).tolist()
    raise ValueError(f"Valeurs invalides dans {column}: {examples}")


def load_station_dimension(path: Path = STATION_DIMENSION_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dimension gare introuvable: {path}")

    dimension = pd.read_csv(path, encoding="utf-8-sig")
    missing_columns = sorted(set(STATION_DIMENSION_RENAME) - set(dimension.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans {path}: {missing_columns}")

    dimension = dimension[list(STATION_DIMENSION_RENAME)].rename(
        columns=STATION_DIMENSION_RENAME
    )

    for column in ["abreviation", "bpuic", "nom", "locality_name"]:
        dimension[column] = dimension[column].astype("string").str.strip()
        dimension.loc[dimension[column].eq(""), column] = pd.NA

    # The source file contains footer/blank rows after the station table.
    dimension = dimension.dropna(subset=["abreviation"]).copy()

    duplicate_mask = dimension["abreviation"].duplicated(keep=False)
    if duplicate_mask.any():
        examples = dimension.loc[duplicate_mask, "abreviation"].drop_duplicates().head(5)
        raise ValueError(
            f"Abreviations de gare dupliquees dans {path}: {examples.tolist()}"
        )

    for column in ["ordre"]:
        values = dimension[column]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_mask = non_missing_mask(values) & numeric.isna()
        raise_for_invalid_values(column, values, invalid_mask)

        non_integer_mask = numeric.notna() & numeric.mod(1).ne(0)
        raise_for_invalid_values(column, values, non_integer_mask)

        dimension[column] = numeric.astype("Int64")

    values = dimension["km"]
    numeric = pd.to_numeric(values, errors="coerce")
    invalid_mask = non_missing_mask(values) & numeric.isna()
    raise_for_invalid_values("km", values, invalid_mask)
    dimension["km"] = numeric.astype("Float64")

    values = dimension["bpuic"]
    numeric = pd.to_numeric(values, errors="coerce")
    invalid_mask = non_missing_mask(values) & numeric.isna()
    raise_for_invalid_values("bpuic", values, invalid_mask)
    dimension["bpuic"] = numeric.astype("Int64")

    return dimension[["abreviation", *STATION_DIMENSION_VALUE_COLUMNS]]


def load_traffic_point_coordinates(path: Path = TRAFFIC_POINT_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dimension full-world traffic point introuvable: {path}")

    required_columns = [
        TRAFFIC_POINT_KEY_COLUMN,
        *TRAFFIC_POINT_DATE_COLUMNS,
        *TRAFFIC_POINT_COORDINATE_COLUMNS,
    ]
    traffic_points = pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        usecols=required_columns,
        dtype="string",
    )

    values = traffic_points[TRAFFIC_POINT_KEY_COLUMN]
    numeric = pd.to_numeric(values, errors="coerce")
    invalid_mask = non_missing_mask(values) & numeric.isna()
    raise_for_invalid_values(TRAFFIC_POINT_KEY_COLUMN, values, invalid_mask)
    traffic_points[TRAFFIC_POINT_KEY_COLUMN] = numeric.astype("Int64")
    traffic_points = traffic_points.dropna(subset=[TRAFFIC_POINT_KEY_COLUMN]).copy()

    for column in TRAFFIC_POINT_DATE_COLUMNS:
        traffic_points[column] = traffic_points[column].astype("string").str.strip()
        traffic_points.loc[traffic_points[column].eq(""), column] = pd.NA

    for column in TRAFFIC_POINT_COORDINATE_COLUMNS:
        values = traffic_points[column]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_mask = non_missing_mask(values) & numeric.isna()
        raise_for_invalid_values(column, values, invalid_mask)
        traffic_points[column] = numeric.astype("Float64")

    has_coordinates = traffic_points[TRAFFIC_POINT_COORDINATE_COLUMNS].notna().any(axis=1)
    traffic_points = traffic_points.loc[has_coordinates].copy()

    # Keep the most recent validity slice per number. Dates are ISO-like strings;
    # lexical ordering keeps 9999-12-31 as the open-ended/latest value.
    for column in TRAFFIC_POINT_DATE_COLUMNS:
        traffic_points[f"_{column}_sort"] = traffic_points[column].fillna("")

    latest_valid_to = traffic_points.groupby(TRAFFIC_POINT_KEY_COLUMN)["_validTo_sort"].transform("max")
    traffic_points = traffic_points.loc[traffic_points["_validTo_sort"].eq(latest_valid_to)].copy()

    latest_valid_from = traffic_points.groupby(TRAFFIC_POINT_KEY_COLUMN)["_validFrom_sort"].transform("max")
    traffic_points = traffic_points.loc[traffic_points["_validFrom_sort"].eq(latest_valid_from)].copy()

    coordinates = (
        traffic_points.groupby(TRAFFIC_POINT_KEY_COLUMN, dropna=False)[TRAFFIC_POINT_COORDINATE_COLUMNS]
        .mean()
        .reset_index()
    )

    duplicate_mask = coordinates[TRAFFIC_POINT_KEY_COLUMN].duplicated(keep=False)
    if duplicate_mask.any():
        examples = (
            coordinates.loc[duplicate_mask, TRAFFIC_POINT_KEY_COLUMN]
            .drop_duplicates()
            .head(5)
        )
        raise ValueError(
            f"Numeros full-world dupliques apres selection de version: {examples.tolist()}"
        )

    return coordinates


def load_traffic_point_fallback_coordinates(
    path: Path = TRAFFIC_POINT_FALLBACK_PATH,
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=[TRAFFIC_POINT_KEY_COLUMN, *TRAFFIC_POINT_COORDINATE_COLUMNS])

    fallback = pd.read_csv(path, encoding="utf-8-sig")
    missing_columns = sorted(set(TRAFFIC_POINT_FALLBACK_RENAME) - set(fallback.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans {path}: {missing_columns}")

    fallback = fallback[list(TRAFFIC_POINT_FALLBACK_RENAME)].rename(
        columns=TRAFFIC_POINT_FALLBACK_RENAME
    )

    values = fallback[TRAFFIC_POINT_KEY_COLUMN]
    numeric = pd.to_numeric(values, errors="coerce")
    invalid_mask = non_missing_mask(values) & numeric.isna()
    raise_for_invalid_values(TRAFFIC_POINT_KEY_COLUMN, values, invalid_mask)
    fallback[TRAFFIC_POINT_KEY_COLUMN] = numeric.astype("Int64")
    fallback = fallback.dropna(subset=[TRAFFIC_POINT_KEY_COLUMN]).copy()

    for column in ["lv95East", "lv95North", "wgs84East", "wgs84North"]:
        values = fallback[column]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_mask = non_missing_mask(values) & numeric.isna()
        raise_for_invalid_values(column, values, invalid_mask)
        fallback[column] = numeric.astype("Float64")

    fallback["height"] = pd.Series(pd.NA, index=fallback.index, dtype="Float64")

    duplicate_mask = fallback[TRAFFIC_POINT_KEY_COLUMN].duplicated(keep=False)
    if duplicate_mask.any():
        examples = (
            fallback.loc[duplicate_mask, TRAFFIC_POINT_KEY_COLUMN]
            .drop_duplicates()
            .head(5)
        )
        raise ValueError(f"BPUIC dupliques dans {path}: {examples.tolist()}")

    return fallback[[TRAFFIC_POINT_KEY_COLUMN, *TRAFFIC_POINT_COORDINATE_COLUMNS]]


def load_combined_traffic_point_coordinates() -> pd.DataFrame:
    coordinates = load_traffic_point_coordinates()
    fallback = load_traffic_point_fallback_coordinates()

    if fallback.empty:
        return coordinates

    fallback_only = fallback.loc[
        ~fallback[TRAFFIC_POINT_KEY_COLUMN].isin(coordinates[TRAFFIC_POINT_KEY_COLUMN])
    ].copy()

    if fallback_only.empty:
        return coordinates

    return pd.concat([coordinates, fallback_only], ignore_index=True)


def add_station_dimension(
    df: pd.DataFrame,
    station_dimension: pd.DataFrame,
    station_column: str,
    prefix: str,
) -> pd.DataFrame:
    dimension = station_dimension.rename(
        columns={
            "abreviation": f"{prefix}_abreviation",
            **{
                column: f"{prefix}_{column}"
                for column in STATION_DIMENSION_VALUE_COLUMNS
            },
        }
    )
    dimension_key = f"{prefix}_abreviation"

    enriched = df.merge(
        dimension,
        how="left",
        left_on=station_column,
        right_on=dimension_key,
        validate="many_to_one",
    )

    if len(enriched) != len(df):
        raise ValueError(
            f"Le join dimension gare sur {station_column} a modifie le nombre de lignes"
        )

    unmatched = (
        enriched.loc[enriched[station_column].notna() & enriched[dimension_key].isna(), station_column]
        .drop_duplicates()
        .sort_values()
    )
    if not unmatched.empty:
        print(
            f"Attention: {len(unmatched)} abreviation(s) de {station_column} "
            f"sans correspondance dans {STATION_DIMENSION_PATH}: {unmatched.tolist()}"
        )

    return enriched.drop(columns=[dimension_key])


def enrich_station_dimensions(df: pd.DataFrame) -> pd.DataFrame:
    station_dimension = load_station_dimension()
    enriched = add_station_dimension(
        df,
        station_dimension,
        station_column="gare_depart",
        prefix="gare_depart",
    )
    enriched = add_station_dimension(
        enriched,
        station_dimension,
        station_column="gare_arrivee",
        prefix="gare_arrivee",
    )
    return enriched


def add_traffic_point_coordinates(
    df: pd.DataFrame,
    traffic_point_coordinates: pd.DataFrame,
    bpuic_column: str,
    prefix: str,
) -> pd.DataFrame:
    coordinates = traffic_point_coordinates.rename(
        columns={
            TRAFFIC_POINT_KEY_COLUMN: f"{prefix}_traffic_point_number",
            **{
                column: f"{prefix}_{column}"
                for column in TRAFFIC_POINT_COORDINATE_COLUMNS
            },
        }
    )
    coordinate_key = f"{prefix}_traffic_point_number"

    enriched = df.merge(
        coordinates,
        how="left",
        left_on=bpuic_column,
        right_on=coordinate_key,
        validate="many_to_one",
    )

    if len(enriched) != len(df):
        raise ValueError(
            f"Le join full-world sur {bpuic_column} a modifie le nombre de lignes"
        )

    unmatched = (
        enriched.loc[enriched[bpuic_column].notna() & enriched[coordinate_key].isna(), bpuic_column]
        .drop_duplicates()
        .sort_values()
    )
    if not unmatched.empty:
        print(
            f"Attention: {len(unmatched)} BPUIC de {bpuic_column} "
            f"sans coordonnees dans {TRAFFIC_POINT_PATH}: {unmatched.tolist()}"
        )

    return enriched.drop(columns=[coordinate_key])


def enrich_traffic_point_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    traffic_point_coordinates = load_combined_traffic_point_coordinates()
    enriched = add_traffic_point_coordinates(
        df,
        traffic_point_coordinates,
        bpuic_column="gare_depart_bpuic",
        prefix="gare_depart",
    )
    enriched = add_traffic_point_coordinates(
        enriched,
        traffic_point_coordinates,
        bpuic_column="gare_arrivee_bpuic",
        prefix="gare_arrivee",
    )
    return enriched


def apply_schema(df: pd.DataFrame) -> pd.DataFrame:
    typed = df.copy()

    for column in STRING_COLUMNS:
        typed[column] = typed[column].astype("string").str.strip()
        typed.loc[typed[column].eq(""), column] = pd.NA

    # Supprime type_jour : sera remplace par jour_semaine via la dimension vacances/feries.
    typed = typed.drop(columns=["type_jour"], errors="ignore")

    for column, date_format in DATE_COLUMNS.items():
        values = typed[column].astype("string").str.strip()
        parsed = pd.to_datetime(values, format=date_format, errors="coerce")
        invalid_mask = non_missing_mask(values) & parsed.isna()
        raise_for_invalid_values(column, values, invalid_mask)
        typed[column] = parsed

    # Parse les heures de depart et d'arrivee, extrait les composantes temporelles
    # et construit des timestamps complets en les combinant avec la date de circulation.
    depart_values = typed["depart"].astype("string").str.strip()
    depart_parsed = pd.to_datetime(depart_values, format="%H:%M", errors="coerce")
    invalid_mask = non_missing_mask(depart_values) & depart_parsed.isna()
    raise_for_invalid_values("depart", depart_values, invalid_mask)

    arrivee_values = typed["arrivee"].astype("string").str.strip()
    arrivee_parsed = pd.to_datetime(arrivee_values, format="%H:%M", errors="coerce")
    invalid_mask = non_missing_mask(arrivee_values) & arrivee_parsed.isna()
    raise_for_invalid_values("arrivee", arrivee_values, invalid_mask)

    dates = typed["date"].dt.normalize()
    depart_td = pd.to_timedelta(
        depart_parsed.dt.hour * 60 + depart_parsed.dt.minute, unit="min"
    )
    arrivee_td = pd.to_timedelta(
        arrivee_parsed.dt.hour * 60 + arrivee_parsed.dt.minute, unit="min"
    )

    depart_datetime = dates + depart_td
    arrivee_datetime = dates + arrivee_td

    # Arrivee le lendemain si l'heure d'arrivee est inferieure a l'heure de depart.
    next_day_mask = arrivee_td.lt(depart_td).fillna(False)
    arrivee_datetime = arrivee_datetime.copy()
    arrivee_datetime.loc[next_day_mask] += pd.Timedelta(days=1)

    duree_minutes = (arrivee_datetime - depart_datetime).dt.total_seconds() / 60

    # Insere les nouvelles colonnes a la position de depart/arrivee (ordre inverse
    # car chaque insert(pos) decale les suivantes d'une position vers la droite).
    depart_pos = typed.columns.get_loc("depart")
    typed = typed.drop(columns=["depart", "arrivee"])

    for name, values in reversed([
        ("depart_datetime", depart_datetime),
        ("heure_depart", depart_parsed.dt.hour.astype("Int64")),
        ("minute_depart", depart_parsed.dt.minute.astype("Int64")),
        ("arrivee_datetime", arrivee_datetime),
        ("heure_arrivee", arrivee_parsed.dt.hour.astype("Int64")),
        ("minute_arrivee", arrivee_parsed.dt.minute.astype("Int64")),
        ("duree_troncon_minutes", duree_minutes.astype("Float64")),
    ]):
        typed.insert(depart_pos, name, values)

    for column in INTEGER_COLUMNS:
        values = typed[column]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_mask = non_missing_mask(values) & numeric.isna()
        raise_for_invalid_values(column, values, invalid_mask)

        non_integer_mask = numeric.notna() & numeric.mod(1).ne(0)
        raise_for_invalid_values(column, values, non_integer_mask)

        typed[column] = numeric.astype("Int64")

    for column in FLOAT_COLUMNS:
        values = typed[column]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_mask = non_missing_mask(values) & numeric.isna()
        raise_for_invalid_values(column, values, invalid_mask)
        typed[column] = numeric.astype("Float64")

    return typed


def add_train_direction(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    sens = pd.Series(pd.NA, index=enriched.index, dtype="string")

    for parity, direction in TRAIN_DIRECTION_BY_PARITY.items():
        mask = enriched["numero_train"].mod(2).eq(parity).fillna(False)
        sens.loc[mask] = direction

    if "sens" in enriched.columns:
        enriched["sens"] = sens
        return enriched

    insert_at = enriched.columns.get_loc("numero_train") + 1
    enriched.insert(insert_at, "sens", sens)
    return enriched


def print_duplicate_summary(duplicates: pd.DataFrame, expected_columns: list[str]) -> None:
    print(f"{len(duplicates):,} occurrences de doublons exportees dans {DUPLICATES_PATH}")

    print("Occurrences de doublons par fichier source:")
    for source_file, count in duplicates["source_file"].value_counts().items():
        print(f"  {source_file}: {count:,}")

    source_combinations = (
        duplicates.groupby(expected_columns, dropna=False)["source_file"]
        .apply(lambda sources: " + ".join(sorted(sources.unique())))
        .value_counts()
    )

    print("Groupes de doublons par combinaison de fichiers:")
    for source_combination, count in source_combinations.items():
        print(f"  {source_combination}: {count:,}")


def main() -> None:
    csv_paths = sorted(RAW_DIR.glob("*.csv"))

    if not csv_paths:
        raise FileNotFoundError(f"Aucun fichier CSV trouve dans {RAW_DIR}")

    first = pd.read_csv(csv_paths[0], encoding="utf-8-sig", nrows=0)
    raw_csv_columns = list(first.columns)

    stacked = pd.concat(
        [load_csv(path, raw_csv_columns) for path in csv_paths],
        ignore_index=True,
    )
    stacked = apply_schema(stacked)
    stacked = add_train_direction(stacked)
    stacked = enrich_station_dimensions(stacked)
    stacked = enrich_traffic_point_coordinates(stacked)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    duplicate_mask = stacked.duplicated(subset=RAW_SCHEMA_COLUMNS, keep=False)
    duplicates = stacked.loc[duplicate_mask].copy()
    duplicated_rows_count = int(stacked.duplicated(subset=RAW_SCHEMA_COLUMNS, keep="first").sum())

    if duplicates.empty:
        if DUPLICATES_PATH.exists():
            DUPLICATES_PATH.unlink()
        if DUPLICATES_PARQUET_PATH.exists():
            DUPLICATES_PARQUET_PATH.unlink()
    else:
        duplicates.to_csv(DUPLICATES_PATH, index=False, encoding="utf-8-sig")
        duplicates.to_parquet(DUPLICATES_PARQUET_PATH, index=False)

    stacked_without_duplicates = stacked.drop_duplicates(
        subset=RAW_SCHEMA_COLUMNS,
        keep="first",
        ignore_index=True,
    )
    stacked_without_duplicates = rename_output_columns(stacked_without_duplicates)
    stacked_without_duplicates.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    stacked_without_duplicates.to_parquet(PARQUET_OUTPUT_PATH, index=False)

    print(f"{len(csv_paths)} fichiers empiles")
    print(f"{len(stacked):,} lignes lues avant dedoublonnage")
    print(f"{duplicated_rows_count:,} lignes doublons supprimees")
    print(f"{len(stacked_without_duplicates):,} lignes ecrites dans {OUTPUT_PATH}")
    print(f"{len(stacked_without_duplicates):,} lignes ecrites dans {PARQUET_OUTPUT_PATH}")

    if duplicates.empty:
        print("Aucun doublon detecte")
    else:
        print_duplicate_summary(duplicates, RAW_SCHEMA_COLUMNS)


if __name__ == "__main__":
    main()
