"""
Stage 04b — Enrichissement avec features météo journalières (agrégats J, J-1, J+1).

Ajoute 18 nouvelles features `meteo_*_j` à stage_04_meteo (→ stage_04b_meteo_j).

Justification empirique : les features horaires actuelles (`meteo_*_h`) sont absentes
du top 20 SHAP. Le notebook 02d_diagnostic_features_meteo.ipynb montre que les agrégats
journaliers ont un signal fondamentalement différent pour précipitations (r=0.47),
ensoleillement (r=0.58) et vent (r=0.59) par rapport aux valeurs horaires ponctuelles.
(cf. ADR-028)

--- Features locales (station selon spatial_segment — identique à meteo_*_h) ---

  Niveau 1 — agrégats J :
    meteo_temperature_max_j          °C     T° max du jour J
    meteo_precip_total_j             mm     Σ précipitations du jour J
    meteo_ensol_total_j              min    Σ ensoleillement du jour J
    meteo_vent_max_j                 km/h   Rafale max du jour J

  Niveau 3 — contexte J-1 et J+1 :
    meteo_precip_total_j_moins_1     mm     Σ précipitations J-1
    meteo_ensol_total_j_moins_1      min    Σ ensoleillement J-1
    meteo_precip_total_j_plus_1      mm     Σ précipitations J+1
    meteo_ensol_total_j_plus_1       min    Σ ensoleillement J+1

  Niveau 4 — rayonnement global :
    meteo_rayon_global_moy_j         W/m²   Rayonnement global moyen du jour J

--- Features destination (station selon base_sens — identique à meteo_destination_*_h) ---

  Niveau 2 — agrégats J :
    meteo_destination_temperature_max_j
    meteo_destination_precip_total_j
    meteo_destination_ensol_total_j
    meteo_destination_vent_max_j

  Niveau 3 — contexte J-1 et J+1 :
    meteo_destination_precip_total_j_moins_1
    meteo_destination_ensol_total_j_moins_1
    meteo_destination_precip_total_j_plus_1
    meteo_destination_ensol_total_j_plus_1

  Niveau 4 — rayonnement global destination :
    meteo_destination_rayon_global_moy_j

--- Mapping spatial unifié (cf. ADR-028) ---

  Toutes les features météo — horaires (`meteo_*_h`, stage_04) et journalières
  (`meteo_*_j`, stage_04b) — utilisent le même critère de rattachement à la station :

  Features locales :
    spatial_segment == "bas"  → station VEV (Vevey/Corseaux, ~380 m)
    spatial_segment == "haut" → station CHD (Château-d'Oex, ~1000 m)

  Features destination :
    base_sens == "VV -> PLEI" (montant)   → CHD
    base_sens == "PLEI -> VV" (descendant) → VEV

  Ce mapping est strictement identique à add_meteo_to_raw_stacked.py (stage_04).
  Blonay (620m) est rattachée à CHD dès qu'elle est la gare haute d'un tronçon :
  choix assumé, aligné sur la frontière opérationnelle de la R35 (crémaillère,
  changement de matériel roulant). Cf. ADR-028.

Sources
-------
- data/processed/stage_04_meteo.parquet
- data/processed/sources/meteo_vev_clean.parquet
- data/processed/sources/meteo_chd_clean.parquet

Sortie
------
- data/processed/stage_04b_meteo_j.parquet
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_04_METEO,
    STAGE_04B_METEO_J,
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

# Colonnes requises dans les parquets météo propres
REQUIRED_METEO_COLS = [
    "reference_timestamp",
    "temperature_air_2m_c",
    "precipitations_mm",
    "duree_ensoleillement_min",
    "rafale_vent_1s_km_h",
    "rayonnement_global_w_m2",
]

SEUIL_MANQUANTS = 0.02  # warning si taux NaN > 2%

# Toutes les nouvelles features produites par ce stage (18 au total)
FEATURES_J = [
    # Niveau 1 — local J
    "meteo_temperature_max_j",
    "meteo_precip_total_j",
    "meteo_ensol_total_j",
    "meteo_vent_max_j",
    # Niveau 2 — destination J
    "meteo_destination_temperature_max_j",
    "meteo_destination_precip_total_j",
    "meteo_destination_ensol_total_j",
    "meteo_destination_vent_max_j",
    # Niveau 3 — local J-1 et J+1
    "meteo_precip_total_j_moins_1",
    "meteo_ensol_total_j_moins_1",
    "meteo_precip_total_j_plus_1",
    "meteo_ensol_total_j_plus_1",
    # Niveau 3 — destination J-1 et J+1
    "meteo_destination_precip_total_j_moins_1",
    "meteo_destination_ensol_total_j_moins_1",
    "meteo_destination_precip_total_j_plus_1",
    "meteo_destination_ensol_total_j_plus_1",
    # Niveau 4 — rayonnement global J
    "meteo_rayon_global_moy_j",
    "meteo_destination_rayon_global_moy_j",
]


# ---------------------------------------------------------------------------
# Chargement et préparation des sources météo
# ---------------------------------------------------------------------------

def load_meteo_clean(path: Path, station: str) -> pd.DataFrame:
    """Charge un parquet météo propre et valide les colonnes requises."""
    meteo = read_stage(path)
    missing = sorted(set(REQUIRED_METEO_COLS) - set(meteo.columns))
    if missing:
        raise ValueError(f"Colonnes manquantes dans {station} ({path.name}) : {missing}")
    for col in REQUIRED_METEO_COLS[1:]:  # skip reference_timestamp
        meteo[col] = pd.to_numeric(meteo[col], errors="coerce").astype("float64")
    meteo["reference_timestamp"] = pd.to_datetime(meteo["reference_timestamp"], errors="coerce")
    return meteo[REQUIRED_METEO_COLS].copy()


def build_aggregats_journaliers(meteo: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les agrégats journaliers depuis les observations horaires.

    Args:
        meteo: Table horaire avec colonnes REQUIRED_METEO_COLS.

    Returns:
        Table avec une ligne par date et 5 colonnes d'agrégats.
    """
    meteo = meteo.copy()
    meteo["date"] = meteo["reference_timestamp"].dt.date

    agg = (
        meteo.groupby("date")
        .agg(
            temperature_max_j    =("temperature_air_2m_c",   "max"),
            precip_total_j       =("precipitations_mm",       "sum"),
            ensol_total_j        =("duree_ensoleillement_min", "sum"),
            vent_max_j           =("rafale_vent_1s_km_h",      "max"),
            rayon_global_moy_j   =("rayonnement_global_w_m2",  "mean"),
        )
        .reset_index()
    )
    agg["date"] = pd.to_datetime(agg["date"])
    return agg


# ---------------------------------------------------------------------------
# Jointure des agrégats journaliers (J, J-1, J+1)
# ---------------------------------------------------------------------------

def join_agg_journaliers(
    df: pd.DataFrame,
    agg_vev: pd.DataFrame,
    agg_chd: pd.DataFrame,
    date_col: str,
    sens_col: str,
    segment_col: str,
) -> pd.DataFrame:
    """
    Joint les agrégats journaliers pour les features locales et destination.

    Mapping station — identique à add_meteo_to_raw_stacked.py (stage_04) :
      Local      : spatial_segment == "haut" → CHD ; "bas" → VEV
      Destination: base_sens == "VV -> PLEI"  → CHD ; "PLEI -> VV" → VEV

    Args:
        df: DataFrame du stage courant.
        agg_vev: Agrégats journaliers VEV.
        agg_chd: Agrégats journaliers CHD.
        date_col: Colonne de date de jointure dans df (ex : "_date_j").
        sens_col: Colonne base_sens dans df.
        segment_col: Colonne spatial_segment dans df.

    Returns:
        df enrichi des colonnes locales et destination pour l'offset de date considéré.
    """
    result = df.copy()

    vev_keyed = agg_vev.rename(columns={
        "date":               date_col,
        "temperature_max_j":  "_vev_temperature_max",
        "precip_total_j":     "_vev_precip_total",
        "ensol_total_j":      "_vev_ensol_total",
        "vent_max_j":         "_vev_vent_max",
        "rayon_global_moy_j": "_vev_rayon_global_moy",
    })
    chd_keyed = agg_chd.rename(columns={
        "date":               date_col,
        "temperature_max_j":  "_chd_temperature_max",
        "precip_total_j":     "_chd_precip_total",
        "ensol_total_j":      "_chd_ensol_total",
        "vent_max_j":         "_chd_vent_max",
        "rayon_global_moy_j": "_chd_rayon_global_moy",
    })

    result = result.merge(vev_keyed, on=date_col, how="left")
    result = result.merge(chd_keyed, on=date_col, how="left")

    is_haut     = result[segment_col].astype(str) == "haut"
    is_montant  = result[sens_col].astype(str) == "VV -> PLEI"

    params = ["temperature_max", "precip_total", "ensol_total", "vent_max", "rayon_global_moy"]

    for param in params:
        if date_col == "_date_j":
            feat_local = f"meteo_{param}_j"
            feat_dest  = f"meteo_destination_{param}_j"
        elif date_col == "_date_j_moins_1":
            feat_local = f"meteo_{param}_j_moins_1"
            feat_dest  = f"meteo_destination_{param}_j_moins_1"
        else:
            feat_local = f"meteo_{param}_j_plus_1"
            feat_dest  = f"meteo_destination_{param}_j_plus_1"

        if feat_local in FEATURES_J:
            result[feat_local] = np.where(
                is_haut,
                result[f"_chd_{param}"],
                result[f"_vev_{param}"],
            ).astype("float64")

        if feat_dest in FEATURES_J:
            result[feat_dest] = np.where(
                is_montant,
                result[f"_chd_{param}"],
                result[f"_vev_{param}"],
            ).astype("float64")

    temp_cols = [c for c in result.columns if c.startswith("_vev_") or c.startswith("_chd_")]
    result = result.drop(columns=temp_cols + [date_col], errors="ignore")

    return result


# ---------------------------------------------------------------------------
# Contrôle qualité
# ---------------------------------------------------------------------------

def check_missing_rates(df: pd.DataFrame) -> None:
    """Logge un WARNING pour chaque feature dépassant le seuil de 2%."""
    for col in FEATURES_J:
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
    """Affiche un résumé de contrôle après enrichissement."""
    n = len(enriched)
    print(f"\nStage 04b — features météo journalières : {n:,} lignes, {enriched.shape[1]} colonnes")

    print("\nMapping spatial_segment → station (nouvelles features journalières) :")
    seg_counts = enriched["spatial_segment"].value_counts(dropna=False)
    for seg, cnt in seg_counts.sort_index().items():
        station = "CHD" if str(seg) == "haut" else "VEV"
        print(f"  {str(seg):<6} → {station} : {cnt:>10,}  ({100 * cnt / n:.1f} %)")

    print("\nNaN par feature :")
    for col in FEATURES_J:
        n_nan = int(enriched[col].isna().sum())
        pct   = 100 * n_nan / n
        flag  = " ← WARNING > 2 %" if pct > 100 * SEUIL_MANQUANTS else ""
        print(f"  {col:<52s}  {pct:5.1f} %{flag}")

    if "horaire_annee_horaire" in enriched.columns:
        print("\nNaN par année horaire (précipitations J+1 — cas J+1 fin H24 attendu) :")
        for feat in ["meteo_precip_total_j_plus_1", "meteo_ensol_total_j_plus_1"]:
            print(f"  {feat} :")
            for ah, grp in enriched.groupby("horaire_annee_horaire"):
                n_nan = int(grp[feat].isna().sum())
                pct = 100 * n_nan / len(grp)
                print(f"    {ah} : {pct:.1f}% NaN")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = read_stage(STAGE_04_METEO)
    n_in = len(df)
    log.info("stage_04_meteo : %d lignes, %d colonnes", n_in, df.shape[1])

    for col in ("spatial_segment", "base_sens", "base_date"):
        if col not in df.columns:
            raise ValueError(f"Colonne requise absente de stage_04 : {col!r}")

    meteo_vev = load_meteo_clean(METEO_VEV_CLEAN, "VEV")
    meteo_chd = load_meteo_clean(METEO_CHD_CLEAN, "CHD")
    log.info("VEV : %d heures | CHD : %d heures", len(meteo_vev), len(meteo_chd))

    agg_vev = build_aggregats_journaliers(meteo_vev)
    agg_chd = build_aggregats_journaliers(meteo_chd)
    log.info("Agrégats VEV : %d jours | CHD : %d jours", len(agg_vev), len(agg_chd))

    n_haut = int((df["spatial_segment"] == "haut").sum())
    n_bas  = int((df["spatial_segment"] == "bas").sum())
    log.info("spatial_segment → VEV (bas) : %d lignes | CHD (haut) : %d lignes", n_bas, n_haut)

    base_date = pd.to_datetime(df["base_date"], errors="coerce")
    df["_date_j"]         = base_date.dt.normalize()
    df["_date_j_moins_1"] = (base_date - pd.Timedelta(days=1)).dt.normalize()
    df["_date_j_plus_1"]  = (base_date + pd.Timedelta(days=1)).dt.normalize()

    n_nat = int(df["_date_j"].isna().sum())
    if n_nat:
        log.warning("%d clé(s) de date J invalide(s) — features journalières NaN pour ces lignes.", n_nat)

    for date_col in ["_date_j", "_date_j_moins_1", "_date_j_plus_1"]:
        df = join_agg_journaliers(
            df,
            agg_vev,
            agg_chd,
            date_col=date_col,
            sens_col="base_sens",
            segment_col="spatial_segment",
        )
        log.info("Jointure %s terminée", date_col)

    if len(df) != n_in:
        raise ValueError(
            f"La jointure journalière a modifié le nombre de lignes : {n_in} → {len(df)}"
        )

    missing_features = [f for f in FEATURES_J if f not in df.columns]
    if missing_features:
        raise ValueError(f"Features manquantes après jointure : {missing_features}")

    check_missing_rates(df)
    write_stage(df, STAGE_04B_METEO_J)
    print_summary(df)


if __name__ == "__main__":
    main()
