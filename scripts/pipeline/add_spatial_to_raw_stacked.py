"""
Ajoute spatial_segment et spatial_denivele_troncon_m à stage_03d
(→ stage_03e_spatial).

spatial_gare_depart_ordre et spatial_gare_arrivee_ordre sont déjà présents
depuis stage_01 (jointure APC × dim_gare lors du stacking). Ce stage calcule
spatial_segment (nécessaire dès stage_04_meteo pour le mapping station météo
VEV/CHD) et spatial_denivele_troncon_m (ADR-057).

Règle métier bas/haut — crémaillère comme critère :
  bas  : les deux gares ont ordre <= 10 (plaine, Blonay incluse comme terminus bas)
  haut : au moins une des deux gares a ordre > 10 (le tronçon touche la crémaillère)

Blonay (ordre 10) est classée bas quand elle est associée à une gare de plaine,
et haut quand elle est associée à une gare au-delà (Prélaz, Lally, Les Pléiades).
La règle reflète la réalité opérationnelle : dès qu'un tronçon touche la
crémaillère, c'est le contexte météorologique d'altitude (CHD) qui prévaut.

Le cas "mixte" disparaît par construction de cette règle.

spatial_denivele_troncon_m = altitude_arrivee − altitude_depart, en mètres,
signé selon le sens réel de circulation (montée positive, descente négative).
Les altitudes sont lues depuis dim_gare.csv (source de vérité incluant GIL et
CLIE, cf. ADR-057) plutôt que depuis les colonnes spatial_gare_*_altitude du
stage courant, qui héritent d'un NaN pour GIL/CLIE issu du fallback sans
altitude de stack_raw_csv.py.

Sources
-------
- data/processed/stage_03d_narcisses.parquet
- data/dimension/dim_gare.csv  (colonnes abreviation, height — ADR-057)

Sortie
------
- data/processed/stage_03e_spatial.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_03D_NARCISSES, STAGE_03E_SPATIAL, DIM_GARE_CSV  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402


def add_spatial_segment(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    dep_ordre = pd.to_numeric(result["spatial_gare_depart_ordre"], errors="coerce")
    arr_ordre = pd.to_numeric(result["spatial_gare_arrivee_ordre"], errors="coerce")
    has_both = dep_ordre.notna() & arr_ordre.notna()

    # Règle métier : un tronçon est "haut" dès qu'il touche la crémaillère
    # (au moins une des deux gares au-delà de Blonay, ordre > 10).
    # "bas" : les deux gares en plaine (ordre <= 10, Blonay incluse).
    # Le cas "mixte" disparaît par construction.
    segment = pd.Series(pd.NA, index=result.index, dtype=object)
    segment[has_both & (dep_ordre <= 10) & (arr_ordre <= 10)] = "bas"
    segment[has_both & ((dep_ordre > 10) | (arr_ordre > 10))] = "haut"
    result["spatial_segment"] = segment.astype("category")

    return result


def add_denivele_troncon(df: pd.DataFrame, dim_gare_csv: Path) -> pd.DataFrame:
    """Ajoute spatial_denivele_troncon_m : dénivelé signé du tronçon en mètres.

    Les altitudes sont lues depuis dim_gare.csv (source de vérité) afin
    d'inclure GIL et CLIE, dont l'altitude est NaN dans dim_gare.parquet
    (héritage du fallback sans height de stack_raw_csv.py).

    Args:
        df: DataFrame avec les colonnes id_gare_depart et id_gare_arrivee
            contenant les abréviations de gare.
        dim_gare_csv: Chemin vers data/dimension/dim_gare.csv, qui doit
            contenir les colonnes abreviation et height (altitude en mètres).

    Returns:
        Copie du DataFrame avec la colonne spatial_denivele_troncon_m ajoutée.
        Dénivelé positif = montée, négatif = descente. NaN si l'altitude d'une
        des deux gares est absente de dim_gare.csv.

    Raises:
        AssertionError: si le nombre de lignes change après l'opération
            (diagnostic de jointure incorrecte avec duplication).
    """
    n_before = len(df)

    dim = pd.read_csv(dim_gare_csv, usecols=["abreviation", "height"])
    dim["height"] = pd.to_numeric(dim["height"], errors="coerce").astype("Float64")
    altitude: dict[str, float] = dim.set_index("abreviation")["height"].to_dict()

    result = df.copy()
    alt_dep = result["id_gare_depart"].map(altitude).astype("Float64")
    alt_arr = result["id_gare_arrivee"].map(altitude).astype("Float64")
    result["spatial_denivele_troncon_m"] = alt_arr - alt_dep

    assert len(result) == n_before, (
        f"Nombre de lignes modifié après ajout du dénivelé : {len(result)} ≠ {n_before}"
    )

    return result


def print_summary(enriched: pd.DataFrame) -> None:
    counts = enriched["spatial_segment"].value_counts(dropna=False)
    total = len(enriched)
    print("\nspatial_segment :")
    for val, n in counts.items():
        print(f"  {str(val):<8} {n:>10,}  ({100 * n / total:.1f} %)")
    n_na_seg = int(enriched["spatial_segment"].isna().sum())
    if n_na_seg:
        print(f"  AVERTISSEMENT : {n_na_seg:,} valeurs NaN (gares inconnues de dim_gare)")

    denivele = enriched["spatial_denivele_troncon_m"]
    n_na_den = int(denivele.isna().sum())
    print(f"\nspatial_denivele_troncon_m :")
    print(f"  min={denivele.min():.1f} m  max={denivele.max():.1f} m  mean={denivele.mean():.1f} m")
    if n_na_den:
        gares_nan = (
            enriched.loc[denivele.isna(), ["id_gare_depart", "id_gare_arrivee"]]
            .stack()
            .unique()
            .tolist()
        )
        print(f"  AVERTISSEMENT : {n_na_den:,} NaN — gares sans altitude : {gares_nan}")
    else:
        print("  0 NaN — toutes les gares ont une altitude.")


def main() -> None:
    df = read_stage(STAGE_03D_NARCISSES)
    enriched = add_spatial_segment(df)
    enriched = add_denivele_troncon(enriched, DIM_GARE_CSV)
    write_stage(enriched, STAGE_03E_SPATIAL)
    print_summary(enriched)


if __name__ == "__main__":
    main()
