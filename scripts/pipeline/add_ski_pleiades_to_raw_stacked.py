"""
Ajoute le flag d'ouverture du domaine skiable des Pléiades → stage_03b_ski.

Join par date : chaque tronçon APC reçoit un flag indiquant si la station
de ski des Pléiades est officiellement ouverte ce jour-là.

Couverture
----------
Saisons H20–H25 : données officielles (PDFs Coopérative des Pléiades).
Saisons H16–H19 : reconstruction empirique (règle dérivée de H20–H25).
  Voir build_dim_ski_pleiades_avec_reconstruction.py pour le détail de la règle.

Colonnes ajoutées
-----------------
event_is_ski_ouvert   bool   — True si le domaine skiable est ouvert
event_ski_source      string — "officiel" (H20–H25) | "reconstruit" (H16–H19)
                               | "hors_saison" (jours sans ski)

Sources
-------
- data/processed/stage_03_manifestations.parquet  (produit par add_manifestations_riviera…py)
- data/dimension/dim_ski_pleiades.parquet          (produit par sources/build_dim_ski_pleiades_avec_reconstruction.py)

Sortie
------
- data/processed/stage_03b_ski.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_ski_pleiades_to_raw_stacked.py``

Anti-leakage J-1
----------------
Le calendrier d'exploitation des remontées mécaniques est publié avant l'ouverture
de la saison. Aucune fuite temporelle.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_03_MANIFESTATIONS,
    STAGE_03B_SKI,
    DIM_SKI_PLEIADES,
)
from pipeline.io import read_stage, write_stage  # noqa: E402


def add_ski(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    dim_join = dim[["date", "is_ski_ouvert", "ski_source"]].copy()
    dim_join["date"] = pd.to_datetime(dim_join["date"])

    enriched = df.merge(
        dim_join,
        how="left",
        left_on="base_date",
        right_on="date",
    ).drop(columns=["date"])

    if len(enriched) != len(df):
        raise ValueError("Le join ski a modifié le nombre de lignes")

    enriched["event_is_ski_ouvert"] = (
        enriched["is_ski_ouvert"].infer_objects(copy=False).fillna(False).astype(bool)
    )
    enriched["event_ski_source"] = (
        enriched["ski_source"].fillna("hors_saison").astype("string")
    )

    return enriched.drop(columns=["is_ski_ouvert", "ski_source"])


def main() -> None:
    df  = read_stage(STAGE_03_MANIFESTATIONS, STAGE_03_MANIFESTATIONS.with_suffix(".csv"))
    dim = read_stage(DIM_SKI_PLEIADES, DIM_SKI_PLEIADES.with_suffix(".csv"))

    enriched = add_ski(df, dim)
    write_stage(enriched, STAGE_03B_SKI)

    n_flag = int(enriched["event_is_ski_ouvert"].sum())
    pct    = n_flag / len(enriched) * 100
    print(f"\nTronçons avec ski ouvert : {n_flag:,} / {len(enriched):,} ({pct:.1f}%)")

    print("\nRépartition par source :")
    for src, grp in enriched.groupby("event_ski_source", observed=True):
        n_ski = int(grp["event_is_ski_ouvert"].sum())
        print(f"  {src:<15}: {n_ski:,} tronçons-jours avec ski ouvert")

    print("\nRépartition par année horaire :")
    summary = (
        enriched.groupby("horaire_annee_horaire")["event_is_ski_ouvert"]
        .agg(n_flag="sum", n_total="count")
        .assign(pct=lambda d: d["n_flag"] / d["n_total"] * 100)
    )
    for annee, row in summary.iterrows():
        print(f"  {annee} : {int(row['n_flag']):,} / {int(row['n_total']):,} ({row['pct']:.1f}%)")


if __name__ == "__main__":
    main()
