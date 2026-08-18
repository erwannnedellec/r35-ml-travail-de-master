"""
Ajoute l'année horaire à stage_01_stacked (→ stage_02_annee_horaire).

La dimension source ``annees_horaires.csv`` contient les dates de début/fin
de chaque année horaire CFF. La jointure est faite par intervalle de dates
(IntervalIndex) plutôt que par jointure exacte, car une date de circulation
n'est pas directement encodée avec son année horaire dans les données APC.

Sources
-------
- data/processed/stage_01_stacked.parquet   (produit par stack_raw_csv.py)
- data/dimension/annees_horaires.csv

Sortie
------
- data/processed/stage_02_annee_horaire.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/add_annee_horaire_to_raw_stacked.py``
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import APC_STACKED, STAGE_01_ANNEE, DIM_ANNEES_HORAIRES  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402
from pipeline.utils import non_missing_mask  # noqa: E402

ANNEES_HORAIRES_PATH = DIM_ANNEES_HORAIRES



def parse_date_column(values: pd.Series, column: str, date_format: str) -> pd.Series:
    strings = values.astype("string").str.strip()
    strings = strings.mask(strings.eq(""), pd.NA)
    parsed = pd.to_datetime(strings, format=date_format, errors="coerce")

    invalid_mask = non_missing_mask(values) & parsed.isna()
    if invalid_mask.any():
        examples = values.loc[invalid_mask].drop_duplicates().head(5).tolist()
        raise ValueError(f"Valeurs invalides dans {column}: {examples}")

    return parsed


def load_annees_horaires(path: Path = ANNEES_HORAIRES_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dimension annees horaires introuvable: {path}")

    annees = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype="string")
    required_columns = {"Annee", "Debut", "Fin"}
    missing_columns = sorted(required_columns - set(annees.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans {path}: {missing_columns}")

    annees = annees[["Annee", "Debut", "Fin"]].rename(
        columns={
            "Annee": "annee_horaire",
            "Debut": "debut_annee_horaire",
            "Fin": "fin_annee_horaire",
        }
    )
    annees["annee_horaire"] = annees["annee_horaire"].astype("string").str.strip()
    annees = annees.loc[annees["annee_horaire"].notna() & annees["annee_horaire"].ne("")].copy()

    annees["debut_annee_horaire"] = parse_date_column(
        annees["debut_annee_horaire"],
        "debut_annee_horaire",
        "%d.%m.%Y",
    )
    annees["fin_annee_horaire"] = parse_date_column(
        annees["fin_annee_horaire"],
        "fin_annee_horaire",
        "%d.%m.%Y",
    )

    annees = annees.loc[annees["debut_annee_horaire"].notna()].copy()

    invalid_interval_mask = (
        annees["fin_annee_horaire"].notna()
        & annees["fin_annee_horaire"].lt(annees["debut_annee_horaire"])
    )
    if invalid_interval_mask.any():
        examples = annees.loc[
            invalid_interval_mask,
            ["annee_horaire", "debut_annee_horaire", "fin_annee_horaire"],
        ].head(5)
        raise ValueError(f"Intervalles annees horaires invalides:\n{examples}")

    annees = annees.sort_values("debut_annee_horaire").reset_index(drop=True)
    effective_fin = annees["fin_annee_horaire"].fillna(pd.Timestamp.max)
    next_debut = annees["debut_annee_horaire"].shift(-1)
    overlap_mask = next_debut.notna() & effective_fin.ge(next_debut)
    if overlap_mask.any():
        examples = annees.loc[
            overlap_mask,
            ["annee_horaire", "debut_annee_horaire", "fin_annee_horaire"],
        ].head(5)
        raise ValueError(f"Intervalles annees horaires chevauchants:\n{examples}")

    # Controle symetrique du precedent : contiguite. Le controle de recouvrement
    # ci-dessus borne le risque de double affectation d'une date ; sans son
    # symetrique, une date orpheline entre deux annees horaires ne serait
    # detectee qu'indirectement, a l'echec du join. La regle est stricte :
    # debut(N) == fin(N-1) + 1 jour. Les lignes sans borne de fin (derniere
    # annee ouverte, millesimes futurs non renseignes) sont ignorees, la
    # contiguite n'etant pas verifiable pour elles.
    gap_mask = (
        annees["fin_annee_horaire"].notna()
        & next_debut.notna()
        & next_debut.ne(annees["fin_annee_horaire"] + pd.Timedelta(days=1))
    )
    if gap_mask.any():
        examples = pd.DataFrame(
            {
                "annee_horaire": annees.loc[gap_mask, "annee_horaire"],
                "fin_annee_horaire": annees.loc[gap_mask, "fin_annee_horaire"],
                "debut_annee_horaire_suivante": next_debut.loc[gap_mask],
            }
        ).head(5)
        raise ValueError(f"Trou entre annees horaires consecutives:\n{examples}")

    return annees


DATE_COL = "base_date"
ANNEE_HORAIRE_COL = "horaire_annee_horaire"

# ADR-038 : extension du périmètre à H25 (toutes sources ingérées, juin 2026).
ANNEE_HORAIRE_MAX = "H25"


def add_annee_horaire(raw_stacked: pd.DataFrame, annees_horaires: pd.DataFrame) -> pd.DataFrame:
    if DATE_COL not in raw_stacked.columns:
        raise ValueError(f"Colonne {DATE_COL} absente de raw_stacked")

    enriched = raw_stacked.drop(columns=[ANNEE_HORAIRE_COL], errors="ignore").copy()
    dates = pd.to_datetime(enriched[DATE_COL], errors="coerce")
    invalid_date_mask = enriched[DATE_COL].notna() & dates.isna()
    if invalid_date_mask.any():
        examples = enriched.loc[invalid_date_mask, DATE_COL].drop_duplicates().head(5).tolist()
        raise ValueError(f"Dates invalides dans raw_stacked: {examples}")

    interval_end = annees_horaires["fin_annee_horaire"].fillna(pd.Timestamp.max)
    intervals = pd.IntervalIndex.from_arrays(
        annees_horaires["debut_annee_horaire"],
        interval_end,
        closed="both",
    )
    interval_index = intervals.get_indexer(dates)

    unmatched_mask = interval_index < 0
    if unmatched_mask.any():
        examples = dates.loc[unmatched_mask].drop_duplicates().sort_values().head(10)
        raise ValueError(
            f"{int(unmatched_mask.sum()):,} ligne(s) sans annee horaire. "
            f"Exemples de dates: {examples.dt.strftime('%Y-%m-%d').tolist()}"
        )

    annee_horaire = annees_horaires["annee_horaire"].iloc[interval_index].reset_index(drop=True)
    annee_horaire = annee_horaire.astype("string")

    insert_at = enriched.columns.get_loc(DATE_COL) + 1
    enriched.insert(insert_at, ANNEE_HORAIRE_COL, annee_horaire)
    return enriched


def main() -> None:
    raw_stacked = read_stage(APC_STACKED, APC_STACKED.with_suffix(".csv"))
    annees_horaires = load_annees_horaires()
    enriched = add_annee_horaire(raw_stacked, annees_horaires)

    if len(enriched) != len(raw_stacked):
        raise ValueError("La transformation a modifie le nombre de lignes")

    n_avant = len(enriched)
    enriched = enriched[enriched[ANNEE_HORAIRE_COL] <= ANNEE_HORAIRE_MAX].copy()
    n_apres = len(enriched)
    if n_avant != n_apres:
        print(f"Filtre <= {ANNEE_HORAIRE_MAX} : {n_avant - n_apres:,} lignes supprimées ({n_avant:,} → {n_apres:,})")

    write_stage(enriched, STAGE_01_ANNEE)

    print("Repartition par annee horaire:")
    for annee_horaire, count in enriched[ANNEE_HORAIRE_COL].value_counts().sort_index().items():
        print(f"  {annee_horaire}: {count:,}")


if __name__ == "__main__":
    main()
