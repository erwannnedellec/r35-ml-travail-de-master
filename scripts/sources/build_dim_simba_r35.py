"""
build_dim_simba_r35.py
======================
Produit la table de dimension ``dim_simba_r35.parquet`` à partir de
``simba_expansion_troncons.parquet``.

Grain de sortie
---------------
(simba_millesime × simba_numero_train × gare_depart × gare_arrivee)

Pour chaque combinaison, les proportions suivantes sont calculées :

  Proportions tarifaires (parts sur les voyageurs DWV totaux) :
    simba_part_ga            — voyageurs avec abonnement GA
    simba_part_mobilis       — voyageurs avec titre Mobilis Riviera
    simba_part_billet_hta    — voyageurs avec billet HTA
    simba_part_spar          — voyageurs avec billet Spar/promotionnel
    simba_part_jeunes        — voyageurs avec titre Jeunes
    simba_part_abonnement    — autres abonnements
    simba_part_militaire     — voyageurs militaires
    simba_part_autre         — autres titres

  Proportions de correspondances :
    simba_part_corresp_amont — voyageurs avec zubringer (train amont renseigné)
    simba_part_corresp_aval  — voyageurs avec anschluss (train aval renseigné)

  Proportion de classe :
    simba_part_premiere_classe — voyageurs en 1ère classe

  Proportion OD :
    simba_part_intra_r35     — voyageurs dont l'origine ET la destination
                               sont dans le périmètre des 17 gares R35

  Volume total (pour traçabilité — à exclure du ml_dataset, cf. ADR-026) :
    simba_voyageurs_dwv_total

Règle anti-leakage (ADR-026)
---------------------------
``simba_voyageurs_dwv_total`` est conservé dans cette table de dimension pour
permettre l'audit et la vérification de cohérence, mais il est **exclu du
ml_dataset** par ``build_ml_dataset.py``.

Inputs
------
  data/processed/sources/simba_expansion_troncons.parquet

Outputs
-------
  data/dimension/dim_simba_r35.parquet

Usage
-----
    python scripts/sources/build_dim_simba_r35.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import SIMBA_EXPANSION, DIM_SIMBA_R35  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Familles tarifaires attendues (cf. build_fact_simba_r35.py)
FAMILLES_TARIFAIRES: list[str] = [
    "GA",
    "Mobilis Riviera",
    "Billet HTA",
    "Spar / promotionnel",
    "Jeunes",
    "Abonnement",
    "Militaire",
    "Autre",
]

# Suffixes de colonnes de proportion tarifaire → nom de feature
FAMILLE_A_FEATURE: dict[str, str] = {
    "GA":                 "simba_part_ga",
    "Mobilis Riviera":    "simba_part_mobilis",
    "Billet HTA":         "simba_part_billet_hta",
    "Spar / promotionnel": "simba_part_spar",
    "Jeunes":             "simba_part_jeunes",
    "Abonnement":         "simba_part_abonnement",
    "Militaire":          "simba_part_militaire",
    "Autre":              "simba_part_autre",
}

# Clé de grain de la dimension
CLE_GRAIN: list[str] = [
    "simba_millesime",
    "simba_numero_train",
    "gare_depart",
    "gare_arrivee",
]

# Gares R35 pour calcul part_intra_r35
GARES_R35: frozenset[str] = frozenset({
    "VV", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL",
    "BLON", "PRLZ", "TUS", "CHEV", "BCHX", "FAY", "OND", "LAL", "PLEI",
})


def calculer_parts_tarifaires(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les proportions tarifaires par grain.

    Pour chaque famille tarifaire, somme les DWV de cette famille et divise
    par le total DWV du grain (train × tronçon × millésime).

    Args:
        df: DataFrame d'expansion avec simba_titre_famille et simba_voyageurs_dwv.

    Returns:
        DataFrame pivot avec une colonne de proportion par famille.
    """
    # Somme DWV par grain × famille
    pivot = (
        df.groupby(CLE_GRAIN + ["simba_titre_famille"])["simba_voyageurs_dwv"]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
    )

    # Ajouter les familles manquantes (certains millésimes peuvent ne pas avoir toutes les familles)
    for famille in FAMILLES_TARIFAIRES:
        if famille not in pivot.columns:
            pivot[famille] = 0.0

    # Total DWV par grain
    pivot["_total_dwv"] = pivot[list(FAMILLES_TARIFAIRES)].sum(axis=1)

    # Calcul des proportions
    for famille, feature in FAMILLE_A_FEATURE.items():
        pivot[feature] = pivot[famille] / pivot["_total_dwv"].replace(0, pd.NA)

    # Conserver le volume total pour traçabilité
    pivot = pivot.rename(columns={"_total_dwv": "simba_voyageurs_dwv_total"})

    # Supprimer les colonnes de famille brutes (labels non normalisés)
    cols_a_supprimer = [c for c in pivot.columns if c in FAMILLES_TARIFAIRES]
    pivot = pivot.drop(columns=cols_a_supprimer)

    return pivot


def calculer_parts_correspondances(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les proportions de correspondances amont et aval par grain.

    Args:
        df: DataFrame d'expansion avec simba_corresp_amont_tu, simba_corresp_aval_tu
            et simba_voyageurs_dwv.

    Returns:
        DataFrame avec simba_part_corresp_amont et simba_part_corresp_aval par grain.
    """
    agg = df.groupby(CLE_GRAIN).agg(
        dwv_total=("simba_voyageurs_dwv", "sum"),
        dwv_corresp_amont=(
            "simba_voyageurs_dwv",
            lambda x: x[df.loc[x.index, "simba_corresp_amont_tu"].notna()].sum(),
        ),
        dwv_corresp_aval=(
            "simba_voyageurs_dwv",
            lambda x: x[df.loc[x.index, "simba_corresp_aval_tu"].notna()].sum(),
        ),
    ).reset_index()

    agg["simba_part_corresp_amont"] = agg["dwv_corresp_amont"] / agg["dwv_total"].replace(0, pd.NA)
    agg["simba_part_corresp_aval"] = agg["dwv_corresp_aval"] / agg["dwv_total"].replace(0, pd.NA)

    return agg[CLE_GRAIN + ["simba_part_corresp_amont", "simba_part_corresp_aval"]]


def calculer_part_premiere_classe(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule la proportion de voyageurs en 1ère classe par grain.

    Args:
        df: DataFrame avec simba_classe et simba_voyageurs_dwv.

    Returns:
        DataFrame avec simba_part_premiere_classe par grain.
    """
    agg = df.groupby(CLE_GRAIN).agg(
        dwv_total=("simba_voyageurs_dwv", "sum"),
        dwv_1ere=("simba_voyageurs_dwv", lambda x: x[df.loc[x.index, "simba_classe"] == 1].sum()),
    ).reset_index()

    agg["simba_part_premiere_classe"] = agg["dwv_1ere"] / agg["dwv_total"].replace(0, pd.NA)
    return agg[CLE_GRAIN + ["simba_part_premiere_classe"]]


def calculer_part_intra_r35(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule la proportion de voyageurs dont l'OD est entièrement interne à R35.

    Une OD est intra-R35 si l'origine du voyage (quell) ET la destination (ziel)
    sont toutes deux dans les 17 gares R35.

    Args:
        df: DataFrame avec simba_origine_voyage, simba_destination_voyage,
            simba_voyageurs_dwv.

    Returns:
        DataFrame avec simba_part_intra_r35 par grain.
    """
    df = df.copy()
    df["est_intra_r35"] = (
        df["simba_origine_voyage"].isin(GARES_R35)
        & df["simba_destination_voyage"].isin(GARES_R35)
    )

    agg = df.groupby(CLE_GRAIN).agg(
        dwv_total=("simba_voyageurs_dwv", "sum"),
        dwv_intra=("simba_voyageurs_dwv", lambda x: x[df.loc[x.index, "est_intra_r35"]].sum()),
    ).reset_index()

    agg["simba_part_intra_r35"] = agg["dwv_intra"] / agg["dwv_total"].replace(0, pd.NA)
    return agg[CLE_GRAIN + ["simba_part_intra_r35"]]


def construire_dimension(df_exp: pd.DataFrame) -> pd.DataFrame:
    """Assemble toutes les features en une seule table de dimension.

    Args:
        df_exp: DataFrame simba_expansion_troncons.

    Returns:
        DataFrame au grain CLE_GRAIN avec toutes les features simba_*.
    """
    df_tarif = calculer_parts_tarifaires(df_exp)
    df_corresp = calculer_parts_correspondances(df_exp)
    df_classe = calculer_part_premiere_classe(df_exp)
    df_intra = calculer_part_intra_r35(df_exp)

    dim = df_tarif
    for df_extra in [df_corresp, df_classe, df_intra]:
        dim = dim.merge(df_extra, on=CLE_GRAIN, how="left", validate="one_to_one")

    assert not dim.duplicated(CLE_GRAIN).any(), "Clé de grain non unique dans dim_simba_r35"
    return dim


def sanity_check(dim: pd.DataFrame) -> None:
    """Vérifie les invariants de la table de dimension.

    Args:
        dim: DataFrame dim_simba_r35 final.

    Raises:
        AssertionError: Si un invariant est violé.
    """
    # Les proportions tarifaires doivent être toutes dans [0, 1]
    cols_parts = [c for c in dim.columns if c.startswith("simba_part_")]
    for col in cols_parts:
        hors_borne = dim[col].dropna()
        hors_borne = hors_borne[(hors_borne < -1e-6) | (hors_borne > 1.0 + 1e-6)]
        assert len(hors_borne) == 0, (
            f"Proportions hors [0,1] dans {col} : {hors_borne.describe()}"
        )

    # La somme des parts tarifaires doit être ≈ 1
    cols_tarif = list(FAMILLE_A_FEATURE.values())
    somme = dim[cols_tarif].sum(axis=1)
    hors_somme = somme.dropna()
    hors_somme = hors_somme[(hors_somme < 0.99) | (hors_somme > 1.01)]
    if len(hors_somme) > 0:
        log.warning(
            "%d lignes avec somme parts tarifaires hors [0.99, 1.01] (bruit numérique acceptable)",
            len(hors_somme),
        )

    log.info(
        "Sanity checks OK : %d lignes, %d colonnes, aucune proportion hors [0,1]",
        len(dim), dim.shape[1],
    )


def main() -> None:
    """Produit dim_simba_r35.parquet depuis simba_expansion_troncons.parquet."""
    df_exp = read_stage(SIMBA_EXPANSION)
    log.info("Expansion chargée : %d lignes, %d colonnes", len(df_exp), df_exp.shape[1])

    dim = construire_dimension(df_exp)
    sanity_check(dim)

    write_stage(dim, DIM_SIMBA_R35)

    print("\n=== Récapitulatif dim_simba_r35 ===")
    print(f"Grain : {CLE_GRAIN}")
    print(f"Lignes : {len(dim):,}")
    print(f"Colonnes : {dim.shape[1]}")
    print(f"Millésimes : {sorted(dim['simba_millesime'].unique())}")
    print(f"Trains : {dim['simba_numero_train'].nunique()}")
    print(f"NaN sur simba_part_ga : {dim['simba_part_ga'].isna().sum():,} lignes")
    print("\nColonnes :")
    for col in dim.columns:
        print(f"  {col}")


if __name__ == "__main__":
    main()
