"""
Ajoute le flag COVID à stage_03b_ski (→ stage_03c_covid).

Join par date : chaque tronçon APC reçoit les indicateurs de restriction
COVID actifs ce jour-là.

Colonnes ajoutées
-----------------
event_is_covid_restrictions   bool   — True si restrictions officielles actives
event_covid_phase             string — phase : normal | semi_confinement |
                                       mesures_renforcees | certificat_obligatoire

Sources
-------
- data/processed/stage_03b_ski.parquet   (produit par add_ski_pleiades_to_raw_stacked.py)
- data/dimension/dim_covid.parquet       (produit par sources/build_dim_covid.py)

Sortie
------
- data/processed/stage_03c_covid.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_covid_to_raw_stacked.py``

Anti-leakage J-1
----------------
Les phases COVID sont connues a posteriori mais leur date d'effet officielle
est publiée le jour J ou avant (ordonnances fédérales). Aucune fuite temporelle.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_03B_SKI,
    STAGE_03C_COVID,
    DIM_COVID,
)
from pipeline.io import read_stage, write_stage  # noqa: E402


def add_covid(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    dim_join = dim[["date", "is_covid_restrictions", "covid_phase"]].copy()
    dim_join["date"] = pd.to_datetime(dim_join["date"])

    enriched = df.merge(
        dim_join,
        how="left",
        left_on="base_date",
        right_on="date",
    ).drop(columns=["date"])

    if len(enriched) != len(df):
        raise ValueError("Le join COVID a modifié le nombre de lignes")

    enriched["event_is_covid_restrictions"] = (
        enriched["is_covid_restrictions"].infer_objects(copy=False).fillna(False).astype(bool)
    )
    enriched["event_covid_phase"] = (
        enriched["covid_phase"].fillna("normal").astype("string")
    )

    return enriched.drop(columns=["is_covid_restrictions", "covid_phase"])


def main() -> None:
    df  = read_stage(STAGE_03B_SKI, STAGE_03B_SKI.with_suffix(".csv"))
    dim = read_stage(DIM_COVID, DIM_COVID.with_suffix(".csv"))

    enriched = add_covid(df, dim)
    write_stage(enriched, STAGE_03C_COVID)

    n_flag = int(enriched["event_is_covid_restrictions"].sum())
    pct    = n_flag / len(enriched) * 100
    print(f"\nTronçons avec restrictions COVID : {n_flag:,} / {len(enriched):,} ({pct:.1f}%)")

    print("\nRépartition par phase COVID :")
    phase_summary = (
        enriched.groupby("event_covid_phase", observed=True)["event_is_covid_restrictions"]
        .count()
        .sort_index()
    )
    for phase, n in phase_summary.items():
        print(f"  {phase:<30}: {int(n):,} tronçons-jours")

    print("\nRépartition par année horaire :")
    summary = (
        enriched.groupby("horaire_annee_horaire")["event_is_covid_restrictions"]
        .agg(n_flag="sum", n_total="count")
        .assign(pct=lambda d: d["n_flag"] / d["n_total"] * 100)
    )
    for annee, row in summary.iterrows():
        print(f"  {annee} : {int(row['n_flag']):,} / {int(row['n_total']):,} ({row['pct']:.1f}%)")


if __name__ == "__main__":
    main()
