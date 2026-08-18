"""
add_simba_to_raw_stacked.py
===========================
Ajoute les features structurelles SIMBA FQkal à stage_08_features (→ stage_09_simba).

Règle de jointure (ADR-026 — lag N-1)
--------------------------------------
Pour chaque ligne du stage_08 dont l'année horaire est H(Y), le millésime
SIMBA utilisé est Y-1 :

    simba_millesime = année_horaire_vers_entier(horaire_annee_horaire) - 1

Exemples :
    H24 → SIMBA 2023
    H23 → SIMBA 2022
    H22 → SIMBA 2021 (absent → toutes features simba_* = NaN pour H22)

Cette règle est symétrique au mapping STATPOP_YEAR_TO_HORAIRE de l'ADR-025 et
garantit la cohérence entre régime d'entraînement et régime d'exploitation
(SIMBA N est publié avec 4–5 mois de latence, donc toujours indisponible à J-1).

Jointure
--------
Clé de jointure :
    stage_08  : (id_simba_millesime, horaire_numero_train, id_gare_depart, id_gare_arrivee)
    dim_simba : (simba_millesime, simba_numero_train, gare_depart, gare_arrivee)

Type : LEFT JOIN (many_to_one) — aucune perte de lignes tolérée.

Invariants
----------
- Nombre de lignes = nombre de lignes du stage_08 (invariant many-to-one).
- Les features simba_* sont NaN pour H22 (SIMBA 2021 absent) et pour les
  tronçons sans correspondance dans la dimension (cas marginal).

Sources
-------
- data/processed/stage_08_features.parquet
- data/dimension/dim_simba_r35.parquet

Sortie
------
- data/processed/stage_09_simba.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_simba_to_raw_stacked.py``
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_08_FEATURES, STAGE_09_SIMBA, DIM_SIMBA_R35  # noqa: E402
from pipeline.io import read_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WRITE_CSV = os.environ.get("WRITE_CSV", "").strip().lower() in {"1", "true", "yes"}
CHUNK_SIZE = 100_000

# Colonnes de jointure côté pipeline
COL_ANNEE_HORAIRE   = "horaire_annee_horaire"
COL_NUMERO_TRAIN    = "horaire_numero_train"
COL_GARE_DEPART     = "id_gare_depart"
COL_GARE_ARRIVEE    = "id_gare_arrivee"
COL_MILLESIME_JOIN  = "id_simba_millesime"   # colonne temporaire de jointure
COL_TRONCON_MIN     = "_simba_gare_min"      # clé normalisée direction-agnostique
COL_TRONCON_MAX     = "_simba_gare_max"      # clé normalisée direction-agnostique

# Colonnes de jointure côté dimension
DIM_MILLESIME   = "simba_millesime"
DIM_TRAIN       = "simba_numero_train"
DIM_DEPART      = "gare_depart"
DIM_ARRIVEE     = "gare_arrivee"

# Features simba_* à inclure dans le dataset ML (sans le volume brut — cf. ADR-026)
FEATURES_SIMBA_ML: list[str] = [
    "simba_part_ga",
    "simba_part_mobilis",
    "simba_part_billet_hta",
    "simba_part_spar",
    "simba_part_jeunes",
    "simba_part_abonnement",
    "simba_part_militaire",
    "simba_part_autre",
    "simba_part_corresp_amont",
    "simba_part_corresp_aval",
    "simba_part_premiere_classe",
    "simba_part_intra_r35",
]

# simba_voyageurs_dwv_total est conservé dans dim_simba_r35 pour l'audit
# mais n'est pas propagé dans stage_09 (cf. ADR-026 — redondance avec lags APC)
FEATURES_SIMBA_TOTAL = FEATURES_SIMBA_ML  # seules les proportions passent dans le stage

# Convention de traçabilité SIMBA (ADR-041).
# Deux phénomènes couverts : H22 (SIMBA 2021 indisponible, ADR-026) et H25 trains
# renumérotés sans match dans SIMBA 2024 (refonte horaire 2024→2025).
# Ces colonnes sont des métadonnées, à exclure du training via COLS_EXCLUES.
SIMBA_SOURCE_COL_DEPART  = "simba_source_depart"
SIMBA_SOURCE_COL_ARRIVEE = "simba_source_arrivee"


def annee_horaire_vers_millesime_simba(annee_horaire: str) -> int:
    """Mappe une année horaire vers le millésime SIMBA à utiliser (lag N-1).

    Args:
        annee_horaire: Code de l'année horaire (ex. 'H24').

    Returns:
        Millésime SIMBA correspondant (ex. 2023 pour H24).

    Example:
        >>> annee_horaire_vers_millesime_simba('H24')
        2023
        >>> annee_horaire_vers_millesime_simba('H22')
        2021
    """
    return 2000 + int(annee_horaire[1:]) - 1


def ajouter_colonne_millesime_simba(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule la colonne de jointure simba_millesime (lag N-1) pour chaque ligne.

    Args:
        df: Chunk du stage_08 avec colonne horaire_annee_horaire.

    Returns:
        DataFrame enrichi d'une colonne id_simba_millesime (Int64).
    """
    df = df.copy()
    df[COL_MILLESIME_JOIN] = (
        df[COL_ANNEE_HORAIRE]
        .map(annee_horaire_vers_millesime_simba)
        .astype("Int64")
    )
    return df


def charger_dimension_simba() -> pd.DataFrame:
    """Charge dim_simba_r35.parquet et prépare les clés de jointure.

    Returns:
        DataFrame dim_simba avec colonnes de jointure typées correctement.

    Raises:
        FileNotFoundError: Si dim_simba_r35.parquet est absent.
    """
    dim = read_stage(DIM_SIMBA_R35)
    dim[DIM_MILLESIME] = dim[DIM_MILLESIME].astype("Int64")
    dim[DIM_TRAIN]     = dim[DIM_TRAIN].astype("Int64")
    dim[DIM_DEPART]    = dim[DIM_DEPART].astype("string")
    dim[DIM_ARRIVEE]   = dim[DIM_ARRIVEE].astype("string")
    log.info(
        "dim_simba_r35 chargée : %d lignes, millésimes %s",
        len(dim), sorted(dim[DIM_MILLESIME].dropna().unique().tolist()),
    )
    return dim


def preparer_cles_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Caste les colonnes de jointure et ajoute les clés normalisées direction-agnostiques.

    La dimension SIMBA contient uniquement les tronçons dans le sens ascendant
    (gare de départ à ordre inférieur → gare d'arrivée à ordre supérieur).
    L'APC enregistre les tronçons dans les deux sens. On normalise via
    (_simba_gare_min, _simba_gare_max) = (min, max) des deux gares, ce qui
    rend la jointure bidirectionnelle.

    Args:
        df: Chunk du stage_08 enrichi de id_simba_millesime.

    Returns:
        Chunk avec types de jointure alignés sur dim_simba_r35 et clés normalisées.
    """
    df = df.copy()
    df[COL_MILLESIME_JOIN] = df[COL_MILLESIME_JOIN].astype("Int64")
    df[COL_NUMERO_TRAIN]   = df[COL_NUMERO_TRAIN].astype("Int64")
    gare_dep = df[COL_GARE_DEPART].astype("string")
    gare_arr = df[COL_GARE_ARRIVEE].astype("string")
    # Clés normalisées : min et max alphabétique des deux gares
    df[COL_TRONCON_MIN] = pd.concat([gare_dep, gare_arr], axis=1).min(axis=1)
    df[COL_TRONCON_MAX] = pd.concat([gare_dep, gare_arr], axis=1).max(axis=1)
    return df


def preparer_dimension_cles_normalisees(dim: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les clés normalisées direction-agnostiques à la dimension SIMBA.

    La dimension contient uniquement les tronçons ascendants. On ajoute
    les colonnes (_simba_gare_min, _simba_gare_max) = (gare_depart, gare_arrivee)
    puisque dans la dimension gare_depart < gare_arrivee alphabétiquement
    pour les tronçons ascendants.

    Args:
        dim: dim_simba_r35 chargée.

    Returns:
        Dimension enrichie des clés normalisées.
    """
    dim = dim.copy()
    gare_dep = dim[DIM_DEPART].astype("string")
    gare_arr = dim[DIM_ARRIVEE].astype("string")
    dim[COL_TRONCON_MIN] = pd.concat([gare_dep, gare_arr], axis=1).min(axis=1)
    dim[COL_TRONCON_MAX] = pd.concat([gare_dep, gare_arr], axis=1).max(axis=1)
    return dim


def joindre_simba(chunk: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """Joint le chunk avec la dimension SIMBA (LEFT JOIN many-to-one).

    La jointure utilise des clés normalisées direction-agnostiques
    (_simba_gare_min, _simba_gare_max) pour couvrir les tronçons dans les
    deux sens (ascendant et descendant). Un tronçon BLON→CHBL (descendant)
    reçoit les mêmes features structurelles que CHBL→BLON (ascendant).

    Args:
        chunk: Chunk du stage_08 enrichi de id_simba_millesime et des clés normalisées.
        dim: dim_simba_r35 avec clés normalisées ajoutées.

    Returns:
        Chunk enrichi des features simba_*.

    Raises:
        AssertionError: Si la jointure modifie le nombre de lignes.
    """
    n_avant = len(chunk)

    # Sélectionner uniquement les features ML + clés normalisées dans la dimension
    dim_reduite = dim[
        [DIM_MILLESIME, DIM_TRAIN, COL_TRONCON_MIN, COL_TRONCON_MAX]
        + [f for f in FEATURES_SIMBA_ML if f in dim.columns]
    ]

    enrichi = chunk.merge(
        dim_reduite,
        how="left",
        left_on=[COL_MILLESIME_JOIN, COL_NUMERO_TRAIN, COL_TRONCON_MIN, COL_TRONCON_MAX],
        right_on=[DIM_MILLESIME, DIM_TRAIN, COL_TRONCON_MIN, COL_TRONCON_MAX],
        validate="many_to_one",
    )

    assert len(enrichi) == n_avant, (
        f"La jointure SIMBA a modifié le nombre de lignes : "
        f"{n_avant} → {len(enrichi)}"
    )

    # Colonnes de traçabilité SIMBA (ADR-041).
    # simba_part_ga est non-NaN si et seulement si la jointure a trouvé un match
    # (présent dans tous les millésimes SIMBA actifs).
    mask_match = enrichi["simba_part_ga"].notna()
    enrichi[SIMBA_SOURCE_COL_DEPART] = pd.Series(
        "manquant_simba_n_minus_1", index=enrichi.index, dtype="string"
    )
    enrichi[SIMBA_SOURCE_COL_ARRIVEE] = pd.Series(
        "manquant_simba_n_minus_1", index=enrichi.index, dtype="string"
    )
    enrichi.loc[mask_match, SIMBA_SOURCE_COL_DEPART] = "match_simba_n_minus_1"
    enrichi.loc[mask_match, SIMBA_SOURCE_COL_ARRIVEE] = "match_simba_n_minus_1"

    # Supprimer les colonnes de clé temporaires
    enrichi = enrichi.drop(
        columns=[DIM_MILLESIME, DIM_TRAIN, COL_MILLESIME_JOIN,
                 COL_TRONCON_MIN, COL_TRONCON_MAX],
        errors="ignore",
    )

    return enrichi


def iter_stage_08(chunk_size: int = CHUNK_SIZE):
    """Lit stage_08 par batches pour limiter l'empreinte mémoire.

    Yields:
        Chunks pandas du stage_08.

    Raises:
        FileNotFoundError: Si ni le parquet ni le CSV ne sont trouvables.
    """
    if STAGE_08_FEATURES.exists():
        for batch in pq.ParquetFile(STAGE_08_FEATURES).iter_batches(batch_size=chunk_size):
            yield batch.to_pandas()
        return
    csv = STAGE_08_FEATURES.with_suffix(".csv")
    if csv.exists():
        yield from pd.read_csv(csv, encoding="utf-8-sig", low_memory=False, chunksize=chunk_size)
        return
    raise FileNotFoundError(
        f"Stage 08 introuvable : {STAGE_08_FEATURES}\n"
        "Exécuter d'abord : python scripts/pipeline/add_features_to_raw_stacked.py"
    )


def main() -> None:
    """Produit stage_09_simba.parquet depuis stage_08_features et dim_simba_r35."""
    dim = charger_dimension_simba()
    dim = preparer_dimension_cles_normalisees(dim)

    STAGE_09_SIMBA.parent.mkdir(parents=True, exist_ok=True)
    parquet_writer = None
    csv_path = STAGE_09_SIMBA.with_suffix(".csv")
    csv_header = True

    total_lignes = 0
    nan_par_annee: dict[str, int] = {}
    total_par_annee: dict[str, int] = {}

    try:
        for num_chunk, chunk in enumerate(iter_stage_08(), start=1):
            chunk = ajouter_colonne_millesime_simba(chunk)
            chunk = preparer_cles_chunk(chunk)
            enrichi = joindre_simba(chunk, dim)

            # Comptage NaN pour rapport final
            for annee in enrichi[COL_ANNEE_HORAIRE].unique():
                sous = enrichi[enrichi[COL_ANNEE_HORAIRE] == annee]
                nan_par_annee[annee] = nan_par_annee.get(annee, 0) + int(
                    sous["simba_part_ga"].isna().sum()
                )
                total_par_annee[annee] = total_par_annee.get(annee, 0) + len(sous)

            total_lignes += len(enrichi)

            table = pa.Table.from_pandas(enrichi, preserve_index=False)
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(
                    STAGE_09_SIMBA, table.schema, compression="snappy"
                )
            else:
                table = table.cast(parquet_writer.schema)
            parquet_writer.write_table(table)

            if WRITE_CSV:
                enrichi.to_csv(
                    csv_path,
                    mode="w" if csv_header else "a",
                    header=csv_header,
                    index=False,
                    encoding="utf-8-sig" if csv_header else "utf-8",
                )
                csv_header = False

            log.info("Chunk %d : %d lignes traitées", num_chunk, len(enrichi))
    finally:
        if parquet_writer is not None:
            parquet_writer.close()

    print(f"\n  parquet : {STAGE_09_SIMBA}  ({total_lignes:,} lignes)")
    if WRITE_CSV:
        print(f"  csv     : {csv_path}")

    print("\nDistribution NaN sur simba_part_ga par année horaire :")
    for annee in sorted(total_par_annee):
        n_nan = nan_par_annee.get(annee, 0)
        n_tot = total_par_annee[annee]
        pct = 100 * n_nan / n_tot if n_tot > 0 else 0.0
        simba_mil = annee_horaire_vers_millesime_simba(annee)
        print(f"  {annee} → SIMBA {simba_mil} : {n_nan:,}/{n_tot:,} NaN ({pct:.1f} %)")

    # Vérification de cohérence ADR-041 : colonnes simba_source_*
    n_total_global = sum(total_par_annee.values())
    n_nan_global   = sum(nan_par_annee.values())
    n_match   = n_total_global - n_nan_global
    n_manquant = n_nan_global
    print(f"\n=== Vérification cohérence SIMBA (ADR-041) ===")
    print(f"  match_simba_n_minus_1    : {n_match:,}")
    print(f"  manquant_simba_n_minus_1 : {n_manquant:,}")
    print(f"  Total : {n_match + n_manquant:,} (attendu = {n_total_global:,})")
    print("\n=== Distribution simba_source_depart par année horaire ===")
    for annee in sorted(total_par_annee):
        n_nan  = nan_par_annee.get(annee, 0)
        n_tot  = total_par_annee[annee]
        n_m    = n_tot - n_nan
        print(f"  {annee:<5}  match={n_m:>8,}  manquant={n_nan:>8,}  total={n_tot:>8,}")


if __name__ == "__main__":
    main()
