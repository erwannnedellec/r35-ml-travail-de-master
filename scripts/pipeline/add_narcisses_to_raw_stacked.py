"""
Ajoute la saison des narcisses à stage_03c_covid (→ stage_03d_narcisses).

Join par date : chaque tronçon APC reçoit un flag indiquant si le jour
est dans la fenêtre de floraison des narcisses aux Pléiades.

Colonnes ajoutées
-----------------
event_is_saison_narcisses   bool   — True si dans la fenêtre de floraison
event_narcisses_source      string — "regle_calendaire" ou "officiel"
                                     | "hors_saison" si hors fenêtre

Sources
-------
- data/processed/stage_03c_covid.parquet  (produit par add_covid_to_raw_stacked.py)
- data/dimension/dim_narcisses.parquet    (produit par sources/build_dim_narcisses.py)

Sortie
------
- data/processed/stage_03d_narcisses.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_narcisses_to_raw_stacked.py``

Anti-leakage J-1
-----------------
La fenêtre est calendaire fixe, connue à J-1 sans observation du jour J.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    STAGE_03C_COVID,
    STAGE_03D_NARCISSES,
    DIM_NARCISSES,
)
from pipeline.io import read_stage, write_stage  # noqa: E402
from pipeline.coverage_guard import assert_dim_couvre_periode_donnees  # noqa: E402


def add_narcisses(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    # Garde de couverture (ADR-076) : le build échoue si dim_narcisses ne couvre
    # pas la fin de la période de données. Rappel du mécanisme, câblé pour
    # narcisses seul dans ce gel (voir coverage_guard.py).
    assert_dim_couvre_periode_donnees(
        df["base_date"], dim["date"], nom_dim="dim_narcisses",
    )

    dim_join = dim[["date", "is_saison_narcisses", "narcisses_source"]].copy()
    dim_join["date"] = pd.to_datetime(dim_join["date"])

    enriched = df.merge(
        dim_join,
        how="left",
        left_on="base_date",
        right_on="date",
    ).drop(columns=["date"])

    if len(enriched) != len(df):
        raise ValueError("Le join narcisses a modifié le nombre de lignes")

    enriched["event_is_saison_narcisses"] = (
        enriched["is_saison_narcisses"].infer_objects(copy=False).fillna(False).astype(bool)
    )
    enriched["event_narcisses_source"] = (
        enriched["narcisses_source"].fillna("hors_saison").astype("string")
    )

    return enriched.drop(columns=["is_saison_narcisses", "narcisses_source"])


def main() -> None:
    df  = read_stage(STAGE_03C_COVID, STAGE_03C_COVID.with_suffix(".csv"))
    dim = read_stage(DIM_NARCISSES, DIM_NARCISSES.with_suffix(".csv"))

    enriched = add_narcisses(df, dim)
    write_stage(enriched, STAGE_03D_NARCISSES)

    n_flag = int(enriched["event_is_saison_narcisses"].sum())
    pct    = n_flag / len(enriched) * 100
    print(f"\nTronçons en saison narcisses : {n_flag:,} / {len(enriched):,} ({pct:.1f}%)")

    print("\nRépartition par année horaire :")
    summary = (
        enriched.groupby("horaire_annee_horaire")["event_is_saison_narcisses"]
        .agg(n_flag="sum", n_total="count")
        .assign(pct=lambda d: d["n_flag"] / d["n_total"] * 100)
    )
    for annee, row in summary.iterrows():
        print(f"  {annee} : {int(row['n_flag']):,} / {int(row['n_total']):,} ({row['pct']:.1f}%)")


if __name__ == "__main__":
    main()
