"""
Ajoute 9 features météo horaires à stage_03e_spatial (→ stage_04_meteo).

Remplace les anciens add_meteo_vev_to_raw_stacked_annee_horaire.py (stage_04)
et add_meteo_chd_to_raw_stacked.py (stage_05), qui produisaient des features
agrégées à la journée.

Granularité : horaire (migration 10 min → horaire, 2026-05, cf. ADR-022).

--- Groupe 1 : features locales au tronçon (source selon spatial_segment) ---

  meteo_temperature_h           °C     moyenne horaire          (tre200h0)
  meteo_precipitation_mm_h      mm     total horaire            (rre150h0)
  meteo_ensoleillement_min_h    min    total horaire            (sre000h0)
  meteo_vent_max_h              km/h   rafale max 1 s horaire   (fu3010h1)
  meteo_neige_binaire_h         0/1    flag neige (logique station)

La source (VEV ou CHD) est résolue selon spatial_segment :
  bas   (ordre <= 10) → station VEV (Vevey/Corseaux, ~380 m)
  haut  (ordre > 10)  → station CHD (Château-d'Oex, ~1000 m)
  mixte (traversée frontière, inexistant en pratique) → NaN + WARNING

Note : meteo_neige_cm_h (htoauths) a été retirée — shift d'instrumentation
  train/test (capteur absent avant 2023, cf. ADR-022 §6).

--- Groupe 2 : features destination / anticipation comportementale ---

  meteo_destination_temperature_h         °C    station selon sens du train
  meteo_destination_precipitation_mm_h    mm    station selon sens du train
  meteo_destination_ensoleillement_min_h  min   station selon sens du train
  meteo_destination_vent_max_h            km/h  station selon sens du train

La source est résolue selon base_sens (valeurs observées : "VV -> PLEI" et
"PLEI -> VV") :
  montant  (VV -> PLEI)   → destination Les Pléiades → station CHD
  descendant (PLEI -> VV) → destination Vevey         → station VEV

Hypothèse comportementale : la décision de prendre le train dépend davantage
des conditions anticipées à destination que des conditions au tronçon courant.
XGBoost et SHAP arbitrent entre les deux logiques (cf. ADR-022 §2).

Note : meteo_destination_neige_cm_h retirée — même shift d'instrumentation
  que meteo_neige_cm_h (cf. ADR-022 §6).

--- Colonnes temporaires ---
Les colonnes _vev_* et _chd_* sont supprimées avant écriture.

Fuseaux horaires
----------------
Les timestamps MétéoSuisse sont en UTC (naive dans les fichiers parquet).
Les horaires R35 (base_depart_datetime) sont en heure locale Europe/Zurich.
La clé de jointure est construite en convertissant base_depart_datetime vers
UTC puis en tronquant à l'heure.

  hiver (UTC+1) : départ 08h00 local → 07h00 UTC → record MétéoSuisse 07:00
  été   (UTC+2) : départ 08h00 local → 06h00 UTC → record MétéoSuisse 06:00

Logique du flag neige binaire (seule feature dont la logique varie par station)
  VEV (bas)  : précipitations > 0 ET température < 2°C
  CHD (haut) : hauteur_neige_cm > 0 OU (précipitations > 0 ET température < 2°C)

Seuil de qualité : WARNING si taux de manquants > 2 %. Le script continue
(mode warning, pas d'exception). La décision de durcissement viendra après
analyse des résultats.

Sources
-------
- data/processed/stage_03e_spatial.parquet
- data/processed/sources/meteo_vev_clean.parquet
- data/processed/sources/meteo_chd_clean.parquet

Sortie
------
- data/processed/stage_04_meteo.parquet
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_03E_SPATIAL,
    STAGE_04_METEO,
    METEO_VEV_CLEAN,
    METEO_CHD_CLEAN,
)
from pipeline.io import read_stage, write_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REFERENCE_TIMESTAMP_COLUMN = "reference_timestamp"

# Colonnes brutes requises dans les clean parquets
REQUIRED_METEO_COLUMNS = [
    "temperature_air_2m_c",
    "precipitations_mm",
    "duree_ensoleillement_min",
    "rafale_vent_1s_km_h",
    "hauteur_neige_cm",
]

SNOW_TEMPERATURE_THRESHOLD_C = 2.0
RAIN_THRESHOLD_MM = 0.0

SEUIL_MANQUANTS = 0.02  # warning si taux > 2 %

# 5 features locales au tronçon + 4 features destination = 9 au total.
# meteo_neige_cm_h, meteo_destination_neige_cm_h et event_ski_neige_si_ouvert_h
# ont été retirées (shift d'instrumentation htoauths, cf. ADR-022 §6).
METEO_FEATURE_COLUMNS = [
    # Groupe 1 — locales au tronçon (source selon spatial_segment)
    "meteo_temperature_h",
    "meteo_precipitation_mm_h",
    "meteo_ensoleillement_min_h",
    "meteo_vent_max_h",
    "meteo_neige_binaire_h",
    # Groupe 2 — destination / anticipation comportementale (source selon base_sens)
    "meteo_destination_temperature_h",
    "meteo_destination_precipitation_mm_h",
    "meteo_destination_ensoleillement_min_h",
    "meteo_destination_vent_max_h",
]


# ---------------------------------------------------------------------------
# Lecture et validation des tables météo propres
# ---------------------------------------------------------------------------

def load_meteo_clean(path: Path, station: str) -> pd.DataFrame:
    """Charge un parquet météo propre et valide les colonnes requises."""
    meteo = read_stage(path)

    required = {REFERENCE_TIMESTAMP_COLUMN, "station_abbr", *REQUIRED_METEO_COLUMNS}
    missing = sorted(required - set(meteo.columns))
    if missing:
        raise ValueError(f"Colonnes manquantes dans {station} ({path.name}) : {missing}")

    meteo[REFERENCE_TIMESTAMP_COLUMN] = pd.to_datetime(
        meteo[REFERENCE_TIMESTAMP_COLUMN], errors="coerce"
    )
    if meteo[REFERENCE_TIMESTAMP_COLUMN].isna().any():
        raise ValueError(f"Horodatages invalides dans {station}")

    unexpected = sorted(
        set(meteo["station_abbr"].dropna().astype(str)) - {station}
    )
    if unexpected:
        raise ValueError(f"Station(s) inattendue(s) dans {path.name} : {unexpected}")

    for col in REQUIRED_METEO_COLUMNS:
        meteo[col] = pd.to_numeric(meteo[col], errors="coerce").astype("float64")

    return (
        meteo[[REFERENCE_TIMESTAMP_COLUMN, *REQUIRED_METEO_COLUMNS]]
        .sort_values(REFERENCE_TIMESTAMP_COLUMN)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Clé de jointure UTC
# ---------------------------------------------------------------------------

def build_join_key_utc(df: pd.DataFrame) -> pd.Series:
    """
    Convertit base_depart_datetime (naive Europe/Zurich) vers une clé UTC tronquée
    à l'heure pour la jointure avec les timestamps MétéoSuisse (UTC).

    Gestion des cas limites DST :
      nonexistent='shift_forward' : heure inexistante (passage heure été) → heure suivante
      ambiguous='NaT'             : heure ambiguë (passage heure hiver, 2h locales) → NaT
                                    (cas rarissime hors plage opérationnelle R35)
    """
    depart = pd.to_datetime(df["base_depart_datetime"], errors="coerce")

    local_aware = depart.dt.tz_localize(
        "Europe/Zurich",
        nonexistent="shift_forward",
        ambiguous="NaT",
    )
    utc_aware = local_aware.dt.tz_convert("UTC")
    return utc_aware.dt.floor("h").dt.tz_localize(None)


# ---------------------------------------------------------------------------
# Jointure horaire VEV et CHD
# ---------------------------------------------------------------------------

def join_meteo_station(
    df: pd.DataFrame,
    meteo: pd.DataFrame,
    prefix: str,
) -> pd.DataFrame:
    """
    Joint les mesures d'une station météo sur la clé UTC horaire.
    Produit des colonnes temporaires préfixées (_vev_* ou _chd_*).
    """
    meteo_keyed = meteo.rename(columns={
        REFERENCE_TIMESTAMP_COLUMN: "_ts_utc",
        "temperature_air_2m_c":      f"_{prefix}_temperature_h",
        "precipitations_mm":          f"_{prefix}_precipitation_mm_h",
        "duree_ensoleillement_min":   f"_{prefix}_ensoleillement_min_h",
        "rafale_vent_1s_km_h":        f"_{prefix}_vent_max_h",
        "hauteur_neige_cm":           f"_{prefix}_neige_cm_h",
    })

    return df.merge(
        meteo_keyed,
        left_on="_ts_utc_join",
        right_on="_ts_utc",
        how="left",
    ).drop(columns=["_ts_utc"], errors="ignore")


# ---------------------------------------------------------------------------
# Construction des 6 features finales
# ---------------------------------------------------------------------------

def build_meteo_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construit les 6 features météo finales en résolvant la station selon
    spatial_segment. Les colonnes temporaires _vev_* et _chd_* sont supprimées.
    """
    result = df.copy()
    seg = result["spatial_segment"].astype(str)

    is_bas   = seg == "bas"
    is_haut  = seg == "haut"
    # Note : avec la règle "haut = au moins une gare > 10" (cf. stage_03e),
    # le cas "mixte" n'est jamais produit. Code défensif conservé pour
    # robustesse, mais ne devrait jamais s'activer.
    is_mixte = seg == "mixte"

    if is_mixte.any():
        n_mixte = int(is_mixte.sum())
        log.warning(
            "%d tronçon(s) avec spatial_segment='mixte' — features météo mises à NaN. "
            "Ce cas est inexistant dans les données APC actuelles ; vérifier la pipeline "
            "si ce nombre est > 0.",
            n_mixte,
        )

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_temperature_h"] = np.where(
        is_bas,  result["_vev_temperature_h"],
        np.where(is_haut, result["_chd_temperature_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_precipitation_mm_h"] = np.where(
        is_bas,  result["_vev_precipitation_mm_h"],
        np.where(is_haut, result["_chd_precipitation_mm_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_ensoleillement_min_h"] = np.where(
        is_bas,  result["_vev_ensoleillement_min_h"],
        np.where(is_haut, result["_chd_ensoleillement_min_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_vent_max_h"] = np.where(
        is_bas,  result["_vev_vent_max_h"],
        np.where(is_haut, result["_chd_vent_max_h"], np.nan),
    ).astype("float64")

    # Logique neige binaire : varie selon la station source (specs ADR-022)
    # VEV (bas)  : précipitations > seuil ET température < 2°C
    # CHD (haut) : hauteur_neige > 0 OU (précipitations > seuil ET température < 2°C)
    #   Pré-2023 : htoauths absent (NaN) → chd_neige > 0 est False → retombe
    #   proprement sur la pluie froide (comportement OR robuste aux NaN pandas).
    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    vev_precip  = pd.to_numeric(result["_vev_precipitation_mm_h"], errors="coerce")
    vev_temp    = pd.to_numeric(result["_vev_temperature_h"],       errors="coerce")
    chd_precip  = pd.to_numeric(result["_chd_precipitation_mm_h"], errors="coerce")
    chd_temp    = pd.to_numeric(result["_chd_temperature_h"],       errors="coerce")
    chd_neige   = pd.to_numeric(result["_chd_neige_cm_h"],          errors="coerce")

    neige_vev = (vev_precip > RAIN_THRESHOLD_MM) & (vev_temp < SNOW_TEMPERATURE_THRESHOLD_C)
    neige_chd = (chd_neige > 0) | (
        (chd_precip > RAIN_THRESHOLD_MM) & (chd_temp < SNOW_TEMPERATURE_THRESHOLD_C)
    )

    neige_binaire_raw = np.where(
        is_bas,  neige_vev.astype("float64"),
        np.where(is_haut, neige_chd.astype("float64"), np.nan),
    )
    result["meteo_neige_binaire_h"] = pd.array(neige_binaire_raw, dtype="Int8")

    # --- Groupe 2 : features destination (station selon sens du train) ---
    # base_sens : "VV -> PLEI" = montant → destination Les Pléiades → CHD
    #             "PLEI -> VV" = descendant → destination Vevey      → VEV
    sens = result["base_sens"].astype(str)
    is_montant    = sens == "VV -> PLEI"
    is_descendant = sens == "PLEI -> VV"

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_destination_temperature_h"] = np.where(
        is_montant,    result["_chd_temperature_h"],
        np.where(is_descendant, result["_vev_temperature_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_destination_precipitation_mm_h"] = np.where(
        is_montant,    result["_chd_precipitation_mm_h"],
        np.where(is_descendant, result["_vev_precipitation_mm_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_destination_ensoleillement_min_h"] = np.where(
        is_montant,    result["_chd_ensoleillement_min_h"],
        np.where(is_descendant, result["_vev_ensoleillement_min_h"], np.nan),
    ).astype("float64")

    # Justification qualitative : [à compléter — codes du corpus thèse]
    # Référence littérature : [à compléter]
    result["meteo_destination_vent_max_h"] = np.where(
        is_montant,    result["_chd_vent_max_h"],
        np.where(is_descendant, result["_vev_vent_max_h"], np.nan),
    ).astype("float64")

    # Suppression des colonnes temporaires
    temp_cols = [c for c in result.columns if c.startswith("_vev_") or c.startswith("_chd_")]
    result = result.drop(columns=temp_cols + ["_ts_utc_join"])

    return result


# ---------------------------------------------------------------------------
# Contrôle qualité manquants
# ---------------------------------------------------------------------------

def check_missing_rates(df: pd.DataFrame) -> None:
    """Logge un WARNING pour chaque feature météo dépassant le seuil de 2 %."""
    for col in METEO_FEATURE_COLUMNS:
        ratio = float(df[col].isna().mean())
        if ratio > SEUIL_MANQUANTS:
            log.warning(
                "Taux de manquants élevé sur %s : %.1f %% (seuil : %.0f %%)",
                col, 100 * ratio, 100 * SEUIL_MANQUANTS,
            )


# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------

def print_summary(enriched: pd.DataFrame) -> None:
    n = len(enriched)
    print("\nFeatures météo horaires ajoutées :")
    for col in METEO_FEATURE_COLUMNS:
        n_missing = int(enriched[col].isna().sum())
        ratio = 100 * n_missing / n
        flag = " ← WARNING > 2 %" if ratio > 100 * SEUIL_MANQUANTS else ""
        print(f"  {col:<42s}  manquants = {n_missing:>8,}  ({ratio:5.1f} %){flag}")

    seg_counts = enriched["spatial_segment"].value_counts(dropna=False)
    print("\nspatial_segment :")
    for val, cnt in seg_counts.items():
        print(f"  {str(val):<8}  {cnt:>10,}  ({100 * cnt / n:.1f} %)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = read_stage(STAGE_03E_SPATIAL)
    log.info("stage_03e_spatial : %d lignes, %d colonnes", len(df), df.shape[1])

    meteo_vev = load_meteo_clean(METEO_VEV_CLEAN, "VEV")
    meteo_chd = load_meteo_clean(METEO_CHD_CLEAN, "CHD")
    log.info("VEV : %d heures | CHD : %d heures", len(meteo_vev), len(meteo_chd))

    # Clé de jointure UTC
    df["_ts_utc_join"] = build_join_key_utc(df)
    n_nat = int(df["_ts_utc_join"].isna().sum())
    if n_nat:
        log.warning(
            "%d clé(s) de jointure NaT (heure locale ambiguë DST) — features météo NaN pour ces lignes.",
            n_nat,
        )

    # Jointures horaires des deux stations
    df = join_meteo_station(df, meteo_vev, "vev")
    df = join_meteo_station(df, meteo_chd, "chd")

    # Construction des 9 features finales
    enriched = build_meteo_features(df)

    if len(enriched) != len(df):
        raise ValueError(
            f"La jointure météo a modifié le nombre de lignes : {len(df)} → {len(enriched)}"
        )

    check_missing_rates(enriched)
    write_stage(enriched, STAGE_04_METEO)
    print_summary(enriched)


if __name__ == "__main__":
    main()
