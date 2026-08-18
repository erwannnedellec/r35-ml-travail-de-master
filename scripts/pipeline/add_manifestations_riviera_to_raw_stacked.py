"""
Ajoute les manifestations Montreux Riviera Tourisme à stage_02 (→ stage_03).

Join par date : chaque tronçon APC reçoit des indicateurs indiquant si une
manifestation se déroule ce jour-là, avec détail par zone géographique
et flags pour les événements signature R35.

Colonnes ajoutées
-----------------
event_is_manifestation_riviera          bool  — au moins une manifestation ce jour
event_n_manifestations_riviera          Int8  — total manifestations simultanées
event_n_manifestations_zone_directe_j   Int8  — manifestations en zone directe R35
event_n_manifestations_zone_indirecte_j Int8  — manifestations en zone indirecte
event_n_manifestations_hors_zone_j      Int8  — manifestations hors zone (contrôle)
event_n_manifestations_vevey_j          Int8  — manifestations à Vevey (zone directe)
event_n_manifestations_st_legier_j      Int8  — manifestations à Saint-Légier (zone directe)
event_n_manifestations_blonay_j         Int8  — manifestations à Blonay/Pléiades (zone directe)
event_is_montreux_jazz                  bool  — Montreux Jazz Festival
event_is_marche_noel                    bool  — Marché de Noël de Montreux
event_is_montreux_noel                  bool  — Montreux Noël (zone indirecte)

Sources
-------
- data/processed/stage_02_calendrier.parquet      (produit par add_vacances_feries_vaud…py)
- data/dimension/dim_manifestations_riviera.parquet (produit par build_dim_manifestations_riviera.py)

Sortie
------
- data/processed/stage_03_manifestations.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py``

Anti-leakage J-1
----------------
Toutes les features sont déterminables à J-1 : les manifestations sont
planifiées à l'avance et publiées par Montreux Riviera Tourisme.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_02_CALENDRIER,
    STAGE_03_MANIFESTATIONS,
    DIM_MANIFESTATIONS_RIVIERA,
)
from pipeline.io import read_stage, write_stage  # noqa: E402

# (src_col, dst_col, dtype) — ordre identique aux assignations originales.
# bool : fillna(False) + infer_objects pour éviter les FutureWarnings pandas.
# Int8 : fillna(0), nullable int.
_COL_CASTS: list[tuple[str, str, str]] = [
    ("is_manifestation_riviera",         "event_is_manifestation_riviera",         "bool"),
    ("n_manifestations_riviera",          "event_n_manifestations_riviera",          "Int8"),
    ("n_manifestations_zone_directe_j",   "event_n_manifestations_zone_directe_j",   "Int8"),
    ("n_manifestations_zone_indirecte_j", "event_n_manifestations_zone_indirecte_j", "Int8"),
    ("n_manifestations_hors_zone_j",      "event_n_manifestations_hors_zone_j",      "Int8"),
    ("is_montreux_jazz",                  "event_is_montreux_jazz",                  "bool"),
    ("is_marche_noel",                    "event_is_marche_noel",                    "bool"),
    ("is_montreux_noel",                  "event_is_montreux_noel",                  "bool"),
    ("n_manifestations_vevey_j",          "event_n_manifestations_vevey_j",          "Int8"),
    ("n_manifestations_st_legier_j",      "event_n_manifestations_st_legier_j",      "Int8"),
    ("n_manifestations_blonay_j",         "event_n_manifestations_blonay_j",         "Int8"),
]
_NEW_COLS = [src for src, _, _ in _COL_CASTS]


def add_manifestations(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    dim_join = dim[["date"] + _NEW_COLS].copy()
    dim_join["date"] = pd.to_datetime(dim_join["date"])

    enriched = df.merge(
        dim_join,
        how="left",
        left_on="base_date",
        right_on="date",
    ).drop(columns=["date"])

    if len(enriched) != len(df):
        raise ValueError("Le join manifestations a modifié le nombre de lignes")

    for src, dst, dtype in _COL_CASTS:
        if dtype == "bool":
            enriched[dst] = enriched[src].infer_objects(copy=False).fillna(False).astype(bool)
        else:
            enriched[dst] = enriched[src].fillna(0).astype(dtype)

    return enriched.drop(columns=_NEW_COLS)


def main() -> None:
    df  = read_stage(STAGE_02_CALENDRIER, STAGE_02_CALENDRIER.with_suffix(".csv"))
    dim = read_stage(DIM_MANIFESTATIONS_RIVIERA, DIM_MANIFESTATIONS_RIVIERA.with_suffix(".csv"))

    enriched = add_manifestations(df, dim)
    write_stage(enriched, STAGE_03_MANIFESTATIONS)

    n_flag = int(enriched["event_is_manifestation_riviera"].sum())
    pct    = n_flag / len(enriched) * 100
    print(f"\nTronçons avec manifestation Riviera : {n_flag:,} / {len(enriched):,} ({pct:.1f}%)")

    n_jazz       = int(enriched["event_is_montreux_jazz"].sum())
    n_noel       = int(enriched["event_is_marche_noel"].sum())
    n_montreux_noel = int(enriched["event_is_montreux_noel"].sum())
    print(f"  dont Montreux Jazz  : {n_jazz:,} tronçons-jours")
    print(f"  dont Marché Noël MX : {n_noel:,} tronçons-jours")
    print(f"  dont Montreux Noël  : {n_montreux_noel:,} tronçons-jours")

    print("\nRépartition par année horaire :")
    summary = (
        enriched.groupby("horaire_annee_horaire")[
            [
                "event_is_manifestation_riviera",
                "event_n_manifestations_zone_directe_j",
                "event_n_manifestations_zone_indirecte_j",
                "event_n_manifestations_hors_zone_j",
            ]
        ]
        .agg(
            n_flag=("event_is_manifestation_riviera", "sum"),
            n_total=("event_is_manifestation_riviera", "count"),
            zone_directe_sum=("event_n_manifestations_zone_directe_j", "sum"),
            zone_indirecte_sum=("event_n_manifestations_zone_indirecte_j", "sum"),
            hors_zone_sum=("event_n_manifestations_hors_zone_j", "sum"),
        )
    )
    for annee, row in summary.iterrows():
        pct_a = row["n_flag"] / row["n_total"] * 100
        print(
            f"  {annee} : {int(row['n_flag']):,}/{int(row['n_total']):,} ({pct_a:.1f}%) "
            f"| directe={int(row['zone_directe_sum'])} "
            f"indirecte={int(row['zone_indirecte_sum'])} "
            f"hors={int(row['hors_zone_sum'])}"
        )


if __name__ == "__main__":
    main()
