"""
Construit la dimension des tours de service de la R35 (ligne CEV).

Sources
-------
data/external/rotations/rotations_23_25.csv — données de planification CEV

Grain
-----
1 ligne par (date × numéro_train × véhicule).
Deux cas produisent plusieurs lignes pour le même numéro de train :
  - Découplage/couplage à BLON : deux véhicules, deux segments distincts
    (ex. CHEV→BLON + BLON→VV).
  - UM : deux véhicules pour le même segment (même depart/arrivee).
Les segments d'un même véhicule sur un même jour forment un tour de service
(id_tour_service = "{date}_{loc}", ex. "2024-01-15_7508").

Sortie
------
data/dimension/dim_rotations_r35.parquet   grain : course affectée dans un tour
  Colonnes :
    date                      datetime64[ns] — jour calendaire (minuit UTC)
    annee_horaire             string         — ex. "H23", "H24"
    id_tour_service           string         — "{date}_{loc}"
    horaire_numero_train      string         — numéro de course (ex. "1304")
    id_gare_depart            string         — abréviation gare de départ
    id_gare_arrivee           string         — abréviation gare d'arrivée
    base_sens                 string         — "montee" (impair) ou "descente" (pair)
    ordre_dans_tour           Int16          — rang 1-based dans le tour (tri par n° train)
    point_changement_possible bool           — arrivée en VV ou BLON
    train_vide                bool           — course de repositionnement (hors service)
    source_version            string         — nom du fichier source

Limites connues
---------------
- cal_heure_depart absent de la source (pas de colonne horaire dans les rotations).
- Couverture : mai 2023 – décembre 2025 (H23 partiel + H24 + H25).
- Trains spéciaux (TrainType='Spécial'/'Formation'), bus de remplacement,
  véhicules d'infrastructure exclus.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import DIMENSION, EXTERNAL  # noqa: E402

SOURCE_FILE = EXTERNAL / "rotations" / "rotations_23_25.csv"
ANNEES_CSV  = DIMENSION / "annees_horaires.csv"
OUTPUT      = DIMENSION / "dim_rotations_r35.parquet"

# Numéros de véhicule rail valides : uniquement des chiffres (ex. 7508, 2501, 6002)
_RAIL_LOC_PATTERN = r"^\d+$"

# Points de changement de composition sur la R35
POINTS_CHANGEMENT = {"VV", "BLON"}


def _load_annees_horaires() -> pd.DataFrame:
    ah = pd.read_csv(ANNEES_CSV, sep=";", encoding="utf-8-sig")
    ah = ah[ah["Debut"].notna() & ah["Fin"].notna()].copy()
    ah["debut_dt"] = pd.to_datetime(ah["Debut"], format="%d.%m.%Y")
    ah["fin_dt"]   = pd.to_datetime(ah["Fin"],   format="%d.%m.%Y")
    return ah[["Annee", "debut_dt", "fin_dt"]]


def _assign_annee_horaire(dates: pd.Series, ah: pd.DataFrame) -> pd.Series:
    result = pd.array([""] * len(dates), dtype="string")
    for _, row in ah.iterrows():
        mask = (dates >= row["debut_dt"]) & (dates <= row["fin_dt"])
        result[mask.values] = row["Annee"]
    return pd.Series(result, index=dates.index, dtype="string")


def build_dim() -> pd.DataFrame:
    raw = pd.read_csv(SOURCE_FILE, sep=";", encoding="utf-8-sig")
    raw["TrainDate"] = pd.to_datetime(raw["TrainDate"])

    # Filtres : voyageurs réguliers, véhicule rail connu, gares renseignées
    mask = (
        (raw["TrainProprietaire"] == "voy")
        & (raw["TrainType"] == "Régulier")
        & raw["CompositionLoc"].notna()
        & raw["CompositionLoc"].str.match(_RAIL_LOC_PATTERN, na=False)
        & raw["CompositionDepart"].notna()
        & (raw["CompositionDepart"].str.strip() != "")
        & raw["CompositionArrivee"].notna()
    )
    df = raw[mask].copy()

    # Annee horaire
    ah = _load_annees_horaires()
    df["annee_horaire"] = _assign_annee_horaire(df["TrainDate"], ah).values

    # Tour de service : véhicule × jour (un véhicule = un tour quotidien)
    df["id_tour_service"] = (
        df["TrainDate"].dt.strftime("%Y-%m-%d") + "_" + df["CompositionLoc"]
    )

    # Sens : numéro pair → descente (vers VV), numéro impair → montée (vers PLEI)
    num_int = df["TrainNumeroTrain"].str.extract(r"^(\d+)", expand=False).astype(int)
    df["base_sens"] = pd.array(
        ["descente" if (n % 2 == 0) else "montee" for n in num_int],
        dtype="string",
    )

    # Ordre dans le tour : tri par numéro de train (encode l'heure de départ)
    df = df.sort_values(["id_tour_service", "TrainNumeroTrain"])
    df["ordre_dans_tour"] = (
        df.groupby("id_tour_service").cumcount() + 1
    ).astype("Int16")

    # Point de changement de composition possible
    df["point_changement_possible"] = df["CompositionArrivee"].isin(POINTS_CHANGEMENT)

    df["source_version"] = "rotations_23_25.csv"

    dim = df.rename(columns={
        "TrainDate":          "date",
        "TrainNumeroTrain":   "horaire_numero_train",
        "CompositionDepart":  "id_gare_depart",
        "CompositionArrivee": "id_gare_arrivee",
        "TrainVide":          "train_vide",
    })[[
        "date",
        "annee_horaire",
        "id_tour_service",
        "horaire_numero_train",
        "id_gare_depart",
        "id_gare_arrivee",
        "base_sens",
        "ordre_dans_tour",
        "point_changement_possible",
        "train_vide",
        "source_version",
    ]]

    dim["date"]                      = pd.to_datetime(dim["date"]).dt.normalize()
    dim["annee_horaire"]             = dim["annee_horaire"].astype("string")
    dim["id_tour_service"]           = dim["id_tour_service"].astype("string")
    dim["horaire_numero_train"]      = dim["horaire_numero_train"].astype("string")
    dim["id_gare_depart"]            = dim["id_gare_depart"].astype("string")
    dim["id_gare_arrivee"]           = dim["id_gare_arrivee"].astype("string")
    dim["base_sens"]                 = dim["base_sens"].astype("string")
    dim["point_changement_possible"] = dim["point_changement_possible"].astype(bool)
    dim["train_vide"]                = dim["train_vide"].astype(bool)
    dim["source_version"]            = dim["source_version"].astype("string")

    return dim.sort_values(
        ["date", "id_tour_service", "ordre_dans_tour"]
    ).reset_index(drop=True)


def validate(dim: pd.DataFrame) -> None:
    if dim.empty:
        raise ValueError("dim_rotations_r35 est vide")

    # Grain : date × numéro_train × gare_depart × tour_service (= date_véhicule)
    # Plusieurs lignes par numéro de train sont normales :
    #   - UM : même depart/arrivee, deux véhicules distincts
    #   - Découplage BLON / LAL : même véhicule, deux segments (departs différents)
    dup = dim.loc[
        dim.duplicated(
            subset=["date", "horaire_numero_train", "id_gare_depart", "id_tour_service"],
            keep=False,
        )
    ]
    if not dup.empty:
        cols = ["date", "horaire_numero_train", "id_gare_depart", "id_tour_service"]
        sample = dup[cols].head(3).to_dict("records")
        raise ValueError(
            f"Doublons date×train×depart×tour ({len(dup)} lignes) : {sample}"
        )

    n_sans_ah = (dim["annee_horaire"] == "").sum()
    if n_sans_ah > 0:
        raise ValueError(
            f"{n_sans_ah} lignes sans annee_horaire — vérifier annees_horaires.csv"
        )


def print_summary(dim: pd.DataFrame) -> None:
    n_tours   = dim["id_tour_service"].nunique()
    n_courses = len(dim)
    print(f"\nDimension rotations R35 (ligne CEV) :")
    print(f"  lignes (courses)   : {n_courses:,}")
    print(f"  tours de service   : {n_tours:,}")
    print(f"  couverture         : {dim['date'].min().date()} → {dim['date'].max().date()}")
    print(f"\n  Par annee horaire :")
    for ah, grp in dim.groupby("annee_horaire"):
        n_t = grp["id_tour_service"].nunique()
        print(
            f"    {ah} : {len(grp):>7,} courses / {n_t:>4,} tours"
            f"  ({grp['date'].min().date()} → {grp['date'].max().date()})"
        )
    print(f"\n  Sens :")
    for sens, n in dim["base_sens"].value_counts().items():
        print(f"    {sens:<12} : {n:,}")
    ch = dim["point_changement_possible"].sum()
    print(f"\n  Points de changement possibles (arrivée VV ou BLON) : {ch:,} / {n_courses:,}")
    print(f"\n  Note : cal_heure_depart absent de la source.")


def main() -> None:
    dim = build_dim()
    validate(dim)

    DIMENSION.mkdir(parents=True, exist_ok=True)
    dim.to_parquet(OUTPUT, index=False)
    dim.to_csv(OUTPUT.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    print(f"  parquet : {OUTPUT}  ({len(dim):,} lignes)")

    print_summary(dim)


if __name__ == "__main__":
    main()
