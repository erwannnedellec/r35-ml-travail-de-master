"""
Prépare les données MétéoSuisse CHD horaires.

Granularité : horaire (codes paramètres en h0/h1/hs).
Migration depuis 10 min (codes s0/z0/z1) vers horaire effectuée en 2026-05.
Motivation : alignement avec les prévisions horaires MétéoSuisse disponibles
en exploitation J-1 (cf. ADR-022).

La station CHD (Château-d'Oex, ~1000 m) sert de proxy pour les conditions
altitude des tronçons haut (gares d'ordre > 10, au-delà de Blonay vers les
Pléiades, ~1350 m).

Opérations réalisées
--------------------
- lecture des exports historiques CHD horaires ;
- validation de la station ;
- parsing de ``reference_timestamp`` (UTC) ;
- conversion numérique des paramètres météo ;
- suppression des colonnes 100 % vides ;
- contrôle des doublons temporels ;
- production d'un rapport de qualité par paramètre.

Sources
-------
- data/external/meteosuisse/ogd-smn_chd_h_historical_2010-2019.csv
- data/external/meteosuisse/ogd-smn_chd_h_historical_2020-2029.csv
- data/external/meteosuisse/ogd-smn_meta_parameters.csv

Sorties
-------
- data/processed/sources/meteo_chd_clean.parquet
- data/processed/sources/meteo_chd_clean.csv
- data/processed/sources/meteo_chd_parameter_quality.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import EXTERNAL, SOURCES  # noqa: E402


# ---------------------------------------------------------------------------
# Paramètres d'entrée / sortie
# ---------------------------------------------------------------------------

RAW_METEO_PATHS = [
    EXTERNAL / "meteosuisse" / "ogd-smn_chd_h_historical_2010-2019.csv",
    EXTERNAL / "meteosuisse" / "ogd-smn_chd_h_historical_2020-2029.csv",
]
META_PARAMETERS_PATH = EXTERNAL / "meteosuisse" / "ogd-smn_meta_parameters.csv"

OUTPUT_PARQUET_PATH = SOURCES / "meteo_chd_clean.parquet"
OUTPUT_CSV_PATH     = SOURCES / "meteo_chd_clean.csv"
OUTPUT_QUALITY_PATH = SOURCES / "meteo_chd_parameter_quality.csv"

STATION_ABBR = "CHD"
REFERENCE_TIMESTAMP_COLUMN = "reference_timestamp"
METEO_KEY_COLUMNS = ["station_abbr", REFERENCE_TIMESTAMP_COLUMN]

# Noms explicites pour les codes horaires MétéoSuisse (h0/h1/hs).
# Les codes sont conservés dans le rapport qualité pour traçabilité.
METEO_PARAMETER_RENAMES = {
    # Température
    "tre200h0":  "temperature_air_2m_c",
    "tre200hn":  "temperature_air_2m_min_c",
    "tre200hx":  "temperature_air_2m_max_c",
    "tre005h0":  "temperature_sol_5cm_c",
    "tre005hn":  "temperature_sol_5cm_min_c",
    # Humidité / rosée
    "ure200h0":  "humidite_relative_2m_pourcent",
    "pva200h0":  "pression_vapeur_2m_hpa",
    "tde200h0":  "point_rosee_2m_c",
    # Pression
    "prestah0":  "pression_station_hpa",
    "pp0qffh0":  "pression_qff_hpa",
    "pp0qnhh0":  "pression_qnh_hpa",
    "ppz700h0":  "geopotentiel_700hpa_gpm",
    "ppz850h0":  "geopotentiel_850hpa_gpm",
    # Vent
    "dkl010h0":  "direction_vent_degre",
    "fkl010h0":  "vitesse_vent_scalaire_m_s",
    "fkl010h1":  "rafale_vent_1s_m_s",
    "fkl010h3":  "rafale_vent_3s_m_s",
    "fu3010h0":  "vitesse_vent_km_h",
    "fu3010h1":  "rafale_vent_1s_km_h",
    "fu3010h3":  "rafale_vent_3s_km_h",
    "fve010h0":  "vitesse_vent_vectorielle_m_s",
    "wcc006h0":  "couverture_nuageuse_pourcent",
    # Précipitations / rayonnement / neige
    "rre150h0":  "precipitations_mm",
    "htoauths":  "hauteur_neige_cm",
    "gre000h0":  "rayonnement_global_w_m2",
    "oli000h0":  "rayonnement_infrarouge_entrant_w_m2",
    "olo000h0":  "rayonnement_infrarouge_sortant_w_m2",
    "osr000h0":  "albedo_pourcent",
    "ods000h0":  "rayonnement_diffus_w_m2",
    "sre000h0":  "duree_ensoleillement_min",
    "erefaoh0":  "evapotranspiration_ref_mm",
    # Températures sol (instantanées)
    "tso005hs":  "temperature_sol_5cm_instantane_c",
    "tso010hs":  "temperature_sol_10cm_instantane_c",
    "tso020hs":  "temperature_sol_20cm_instantane_c",
}


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def non_missing_mask(values: pd.Series) -> pd.Series:
    """Identifie les valeurs non manquantes et non vides dans une série."""
    strings = values.astype("string").str.strip()
    return strings.notna() & strings.ne("")


def read_raw_meteo() -> pd.DataFrame:
    """Lit et concatène les exports MétéoSuisse CHD bruts."""
    missing_paths = [path for path in RAW_METEO_PATHS if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(f"Fichier(s) météo CHD introuvable(s) : {missing_paths}")

    frames = []
    for path in RAW_METEO_PATHS:
        frame = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype="string")
        frame["source_file"] = path.name
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


def read_parameter_metadata() -> pd.DataFrame:
    """Lit le dictionnaire des paramètres MétéoSuisse si disponible."""
    if not META_PARAMETERS_PATH.exists():
        return pd.DataFrame()

    return pd.read_csv(META_PARAMETERS_PATH, sep=";", encoding="latin1", dtype="string")


def add_parameter_metadata(quality: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les descriptions officielles au rapport qualité."""
    metadata = read_parameter_metadata()
    if metadata.empty:
        return quality

    keep_columns = [
        "parameter_shortname",
        "parameter_description_fr",
        "parameter_description_en",
        "parameter_group_fr",
        "parameter_group_en",
        "parameter_granularity",
        "parameter_unit",
    ]
    available_columns = [col for col in keep_columns if col in metadata.columns]

    return quality.merge(
        metadata[available_columns],
        left_on="code_meteosuisse",
        right_on="parameter_shortname",
        how="left",
    ).drop(columns=["parameter_shortname"], errors="ignore")


def build_clean_meteo(raw_meteo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nettoie les mesures CHD et retourne la table propre + rapport qualité."""
    missing_columns = sorted(set(METEO_KEY_COLUMNS) - set(raw_meteo.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans les fichiers CHD : {missing_columns}")

    meteo = raw_meteo.copy()
    meteo["station_abbr"] = meteo["station_abbr"].astype("string").str.strip()
    unexpected_stations = sorted(
        set(meteo.loc[meteo["station_abbr"].notna(), "station_abbr"]) - {STATION_ABBR}
    )
    if unexpected_stations:
        raise ValueError(f"Station(s) inattendue(s) dans les fichiers CHD : {unexpected_stations}")

    raw_timestamps = meteo[REFERENCE_TIMESTAMP_COLUMN].copy()
    meteo[REFERENCE_TIMESTAMP_COLUMN] = pd.to_datetime(
        meteo[REFERENCE_TIMESTAMP_COLUMN].astype("string").str.strip(),
        format="%d.%m.%Y %H:%M",
        errors="coerce",
    )
    invalid_timestamp_mask = meteo[REFERENCE_TIMESTAMP_COLUMN].isna()
    if invalid_timestamp_mask.any():
        examples = raw_timestamps.loc[invalid_timestamp_mask].head(5).tolist()
        raise ValueError(f"Horodatages CHD invalides : {examples}")

    value_columns = [
        column
        for column in meteo.columns
        if column not in [*METEO_KEY_COLUMNS, "source_file"]
    ]

    quality_rows = []
    for column in value_columns:
        raw_values = meteo[column]
        non_missing = non_missing_mask(raw_values)
        numeric = pd.to_numeric(raw_values, errors="coerce")
        invalid_numeric_mask = non_missing & numeric.isna()
        if invalid_numeric_mask.any():
            examples = raw_values.loc[invalid_numeric_mask].drop_duplicates().head(5).tolist()
            raise ValueError(f"Valeurs invalides dans CHD/{column} : {examples}")

        meteo[column] = numeric.astype("float64")
        non_missing_count = int(meteo[column].notna().sum())
        quality_rows.append(
            {
                "code_meteosuisse": column,
                "nom_colonne_propre": METEO_PARAMETER_RENAMES.get(column, column),
                "raw_non_empty_count": int(non_missing.sum()),
                "numeric_non_missing_count": non_missing_count,
                "missing_count": int(meteo[column].isna().sum()),
                "missing_ratio": float(meteo[column].isna().mean()),
                "invalid_numeric_count": int(invalid_numeric_mask.sum()),
                "kept_in_clean_table": non_missing_count > 0,
                "drop_reason": "100% missing" if non_missing_count == 0 else pd.NA,
            }
        )

    quality = pd.DataFrame(quality_rows).sort_values(
        ["kept_in_clean_table", "nom_colonne_propre"],
        ascending=[False, True],
    )
    quality = add_parameter_metadata(quality)

    kept_source_columns = quality.loc[quality["kept_in_clean_table"], "code_meteosuisse"].tolist()
    kept_renames = {
        source: METEO_PARAMETER_RENAMES.get(source, source)
        for source in kept_source_columns
    }
    duplicate_clean_names = pd.Series(list(kept_renames.values())).duplicated(keep=False)
    if duplicate_clean_names.any():
        duplicated = sorted(pd.Series(list(kept_renames.values()))[duplicate_clean_names].unique())
        raise ValueError(f"Noms de colonnes propres dupliqués dans CHD : {duplicated}")

    clean = (
        meteo[[*METEO_KEY_COLUMNS, *kept_source_columns]]
        .rename(columns=kept_renames)
        .sort_values(REFERENCE_TIMESTAMP_COLUMN)
    )

    duplicate_timestamp_mask = clean[REFERENCE_TIMESTAMP_COLUMN].duplicated(keep=False)
    if duplicate_timestamp_mask.any():
        examples = (
            clean.loc[duplicate_timestamp_mask, REFERENCE_TIMESTAMP_COLUMN]
            .drop_duplicates()
            .head(5)
            .tolist()
        )
        raise ValueError(f"Horodatages CHD dupliqués : {examples}")

    return clean.reset_index(drop=True), quality.reset_index(drop=True)


def print_summary(clean: pd.DataFrame, quality: pd.DataFrame) -> None:
    """Affiche un résumé de contrôle après nettoyage."""
    kept_count = int(quality["kept_in_clean_table"].sum())
    dropped_count = int((~quality["kept_in_clean_table"]).sum())
    timestamps = clean[REFERENCE_TIMESTAMP_COLUMN]
    expected = pd.date_range(timestamps.min(), timestamps.max(), freq="h")
    missing_timestamps = expected.difference(pd.DatetimeIndex(timestamps))

    print("\nNettoyage MétéoSuisse CHD (Château-d'Oex) — horaire :")
    print(f"  lignes propres              : {len(clean):,}")
    print(f"  paramètres conservés        : {kept_count:,}")
    print(f"  paramètres supprimés vides  : {dropped_count:,}")
    print(f"  début                       : {timestamps.min()}")
    print(f"  fin                         : {timestamps.max()}")
    print(f"  trous horaires              : {len(missing_timestamps):,}")

    snow_col = "hauteur_neige_cm"
    if snow_col in clean.columns:
        snow_available = int(clean[snow_col].notna().sum())
        print(f"  observations neige CHD      : {snow_available:,} / {len(clean):,}")

    if dropped_count:
        dropped = quality.loc[~quality["kept_in_clean_table"], "code_meteosuisse"].tolist()
        print("\nColonnes supprimées car 100 % vides :")
        print("  " + ", ".join(dropped))


def main() -> None:
    raw_meteo = read_raw_meteo()
    clean, quality = build_clean_meteo(raw_meteo)

    OUTPUT_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(OUTPUT_PARQUET_PATH, index=False)
    clean.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    quality.to_csv(OUTPUT_QUALITY_PATH, index=False, encoding="utf-8-sig")

    print(f"{len(clean):,} lignes écrites dans {OUTPUT_PARQUET_PATH}")
    print(f"{len(quality):,} lignes écrites dans {OUTPUT_QUALITY_PATH}")
    print_summary(clean, quality)


if __name__ == "__main__":
    main()
