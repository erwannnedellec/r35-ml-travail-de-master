"""
Ajoute les indicateurs d'emploi STATENT 500 m à stage_06_statpop (→ stage_06b_statent).

Pour chaque tronçon, 4 features sont ajoutées :
  spatial_gare_depart_emplois_500m_total      emploi total  buffer Voronoï 500 m, gare départ
  spatial_gare_depart_emplois_500m_services   emploi tertiaire, gare départ
  spatial_gare_arrivee_emplois_500m_total     emploi total, gare arrivée
  spatial_gare_arrivee_emplois_500m_services  emploi tertiaire, gare arrivée

Mapping causal Z-3 (ADR-064)
------------------------------
STATENT PUBJAHR = ERHJAHR + 2 (vérifié sur 9 millesimes 2015-2023). Borne conservatrice :
millesime Y disponible opérationnellement à partir du 1er janvier Y+3.
→ observation année civile Z utilise millesime Z-3.

  Z=2021 → 2018 | Z=2022 → 2019 | Z=2023 → 2020 | Z=2024 → 2021 | Z=2025 → 2022

Les observations H16-H20 (non présentes dans ml_dataset) reçoivent NaN (millesime Z-3
antérieur à 2018, absent de statent_clean_causal.parquet) — accepté.

Source canonique
----------------
data/processed/sources/statent_clean_causal.parquet  (91 lignes : 5 millesimes × 17-18 gares
+ VVVI reconstruit via topologie H23, ADR-064)

Sources
-------
- data/processed/stage_06_statpop.parquet       (produit par add_statpop_to_raw_stacked…py)
- data/processed/sources/statent_clean_causal.parquet

Sortie
------
- data/processed/stage_06b_statent.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_statent_to_raw_stacked.py``
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_06_STATPOP, STAGE_06B_STATENT, STATENT_CLEAN  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WRITE_CSV = os.environ.get("WRITE_CSV", "").strip().lower() in {"1", "true", "yes"}

# Mapping causal Z-3 : année civile Z → millesime STATENT Z-3.
# Couverture : 2021-2025 (millesimes 2018-2022 dans statent_clean_causal).
# H16-H20 (années civiles < 2021) → millesime absent → NaN implémenté par left join.
STATENT_MAPPING: dict[int, int] = {
    2021: 2018,
    2022: 2019,
    2023: 2020,
    2024: 2021,
    2025: 2022,
}

# Colonnes à joindre depuis statent_clean_causal (sans clés de jointure)
STATENT_VALUE_COLS = ["emplois_500m_total", "emplois_500m_services"]

# Préfixes colonnes output
SIDES = {
    "depart":  "id_gare_depart",
    "arrivee": "id_gare_arrivee",
}


def _resolve_statent_millesime(df: pd.DataFrame) -> pd.Series:
    """Résout le millesime STATENT (Z-3) depuis l'année calendaire de base_date."""
    annee_cal = pd.to_datetime(df["base_date"], errors="coerce").dt.year
    millesime = annee_cal.map(STATENT_MAPPING).astype("Int64")
    return millesime


def add_statent(df: pd.DataFrame, statent: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les 4 features emploi STATENT par jointure causal Z-3."""
    millesime = _resolve_statent_millesime(df)
    df = df.copy()
    df["_statent_millesime"] = millesime

    statent_join = statent[["annee_enquete_statent", "gare_abreviation"] + STATENT_VALUE_COLS].copy()
    statent_join["annee_enquete_statent"] = statent_join["annee_enquete_statent"].astype("Int64")

    for side, id_col in SIDES.items():
        side_join = statent_join.rename(columns={
            "annee_enquete_statent": "_statent_millesime",
            "gare_abreviation":      id_col,
            "emplois_500m_total":    f"spatial_gare_{side}_emplois_500m_total",
            "emplois_500m_services": f"spatial_gare_{side}_emplois_500m_services",
        })
        df = df.merge(
            side_join,
            on=["_statent_millesime", id_col],
            how="left",
            validate="many_to_one",
        )
        if len(df) != len(millesime):
            raise ValueError(f"Jointure STATENT {side} a modifié le nombre de lignes")

    df = df.drop(columns=["_statent_millesime"])

    # Dtypes finaux
    for side in SIDES:
        for feat in ["emplois_500m_total", "emplois_500m_services"]:
            col = f"spatial_gare_{side}_{feat}"
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float32")

    return df


def main() -> None:
    log.info("=== stage_06b : add_statent_to_raw_stacked ===")

    df = read_stage(STAGE_06_STATPOP)
    log.info("stage_06 chargé : %d lignes, %d colonnes", len(df), df.shape[1])

    statent = pd.read_parquet(STATENT_CLEAN)
    log.info("statent_clean_causal : %d lignes, millesimes %s",
             len(statent), sorted(statent["annee_enquete_statent"].unique()))

    df_out = add_statent(df, statent)

    # Vérification NaN sur H22-H25 (périmètre ml_dataset)
    for ah, cal_years in [("H22", [2021, 2022]), ("H23", [2022, 2023]),
                          ("H24", [2023, 2024]), ("H25", [2024, 2025])]:
        mask_ah = df_out["horaire_annee_horaire"] == ah
        n_nan = df_out.loc[mask_ah, "spatial_gare_depart_emplois_500m_total"].isna().sum()
        log.info("  %s : NaN emplois_500m_total départ = %d / %d",
                 ah, n_nan, mask_ah.sum())

    log.info("Sortie : %d lignes, %d colonnes", len(df_out), df_out.shape[1])
    write_stage(df_out, STAGE_06B_STATENT, write_csv=WRITE_CSV)
    log.info("=== stage_06b terminé ===")


if __name__ == "__main__":
    main()
