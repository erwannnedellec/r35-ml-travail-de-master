"""
Construit la table de dimension des gares de la ligne R35.

Sources :
  - data/dimension/gare_abreviation.csv        → BPUIC, abréviation, nom, commune, ordre, km
  - data/dimension/full-world-traffic-point.csv → coordonnées GPS (lv95 + wgs84 + altitude)
  - data/dimension/gare_GIL_CLIE.csv            → coordonnées de secours pour GIL et CLIE

Sortie :
  - data/dimension/dim_gare.csv
  - data/dimension/dim_gare.parquet
"""

from pathlib import Path

import pandas as pd


STATION_PATH = Path("data/dimension/gare_abreviation.csv")
TRAFFIC_POINT_PATH = Path("data/dimension/full-world-traffic-point.csv")
FALLBACK_PATH = Path("data/dimension/gare_GIL_CLIE.csv")
RAW_DIR = Path("data/raw")
OUTPUT_CSV = Path("data/dimension/dim_gare.csv")
OUTPUT_PARQUET = Path("data/dimension/dim_gare.parquet")

COORDINATE_COLUMNS = ["lv95East", "lv95North", "wgs84East", "wgs84North", "height"]


def load_stations() -> pd.DataFrame:
    df = pd.read_csv(STATION_PATH, encoding="utf-8-sig")
    df = df.rename(columns={
        "Gare_BPUIC": "bpuic",
        "Gare_abreviation": "abreviation",
        "Gare_nom": "nom",
        "Gare_Gare_localityName": "commune",
        "Gare_Ordre": "ordre",
        "Gare_Gare_km": "km",
    })

    for col in ["abreviation", "nom", "commune"]:
        df[col] = df[col].astype("string").str.strip()
        df.loc[df[col].eq(""), col] = pd.NA

    df = df.dropna(subset=["abreviation"]).copy()
    df["bpuic"] = pd.to_numeric(df["bpuic"], errors="coerce").astype("Int64")
    df["ordre"] = pd.to_numeric(df["ordre"], errors="coerce").astype("Int64")
    df["km"] = pd.to_numeric(df["km"], errors="coerce").astype("Float64")

    return df[["abreviation", "bpuic", "nom", "commune", "ordre", "km"]]


def load_coordinates() -> pd.DataFrame:
    """Charge full-world-traffic-point et retourne une ligne par BPUIC.

    Stratégie : pour chaque BPUIC, on retient les entrées avec la validité la
    plus récente (validTo le plus tardif, puis validFrom le plus tardif), puis
    on moyenne les coordonnées de toutes les voies/quais de cette tranche.
    """
    required = ["number", "validFrom", "validTo", *COORDINATE_COLUMNS]
    tp = pd.read_csv(
        TRAFFIC_POINT_PATH,
        sep=";",
        encoding="utf-8-sig",
        usecols=required,
        dtype="string",
        low_memory=False,
    )

    tp["number"] = pd.to_numeric(tp["number"], errors="coerce").astype("Int64")
    tp = tp.dropna(subset=["number"])

    for col in COORDINATE_COLUMNS:
        tp[col] = pd.to_numeric(tp[col], errors="coerce").astype("Float64")

    # Garder uniquement les lignes avec au moins une coordonnée renseignée
    tp = tp.loc[tp[COORDINATE_COLUMNS].notna().any(axis=1)].copy()

    # Sélection de la tranche de validité la plus récente par BPUIC
    for date_col in ["validTo", "validFrom"]:
        tp[f"_{date_col}"] = tp[date_col].fillna("")

    latest_to = tp.groupby("number")["_validTo"].transform("max")
    tp = tp.loc[tp["_validTo"].eq(latest_to)].copy()

    latest_from = tp.groupby("number")["_validFrom"].transform("max")
    tp = tp.loc[tp["_validFrom"].eq(latest_from)].copy()

    # Moyenne des coordonnées (plusieurs quais par gare)
    coords = (
        tp.groupby("number", dropna=False)[COORDINATE_COLUMNS]
        .mean()
        .reset_index()
        .rename(columns={"number": "bpuic"})
    )

    for col in COORDINATE_COLUMNS:
        coords[col] = coords[col].astype("Float64")

    return coords


def load_fallback_coordinates() -> pd.DataFrame:
    if not FALLBACK_PATH.exists():
        return pd.DataFrame(columns=["bpuic", *COORDINATE_COLUMNS])

    fb = pd.read_csv(FALLBACK_PATH, encoding="utf-8-sig")
    fb = fb.rename(columns={
        "Gare_Gare_BPUIC": "bpuic",
        "Gare_lv95East": "lv95East",
        "Gare_lv95North": "lv95North",
        "Gare_wgs84East": "wgs84East",
        "Gare__wgs84North": "wgs84North",
    })
    fb["bpuic"] = pd.to_numeric(fb["bpuic"], errors="coerce").astype("Int64")
    fb["height"] = pd.Series(pd.NA, index=fb.index, dtype="Float64")

    for col in ["lv95East", "lv95North", "wgs84East", "wgs84North"]:
        fb[col] = pd.to_numeric(fb[col], errors="coerce").astype("Float64")

    return fb[["bpuic", *COORDINATE_COLUMNS]]


def load_active_stations(raw_dir: Path = RAW_DIR) -> set[str]:
    """Retourne l'ensemble des abréviations présentes dans les fichiers bruts."""
    gares: set[str] = set()
    for path in sorted(raw_dir.glob("*.csv")):
        df = pd.read_csv(path, usecols=["gare_depart", "gare_arrivee"])
        gares.update(df["gare_depart"].dropna().unique())
        gares.update(df["gare_arrivee"].dropna().unique())
    return gares


def build_dim_gare() -> pd.DataFrame:
    print("Détection des gares actives dans les fichiers bruts...")
    active = load_active_stations()
    print(f"  {len(active)} gares trouvées : {sorted(active)}")

    print("Chargement des gares...")
    stations = load_stations()
    stations = stations[stations["abreviation"].isin(active)].copy()
    print(f"  {len(stations)} gares conservées après filtre")

    print("Chargement des coordonnées GPS (full-world-traffic-point)...")
    coords = load_coordinates()
    print(f"  {coords['bpuic'].nunique()} BPUICs avec coordonnées")

    print("Chargement des coordonnées de secours (GIL / CLIE)...")
    fallback = load_fallback_coordinates()
    fallback_only = fallback.loc[~fallback["bpuic"].isin(coords["bpuic"])].copy()
    if not fallback_only.empty:
        coords = pd.concat([coords, fallback_only], ignore_index=True)
        print(f"  {len(fallback_only)} BPUIC(s) ajouté(s) depuis le fallback")

    print("Jointure...")
    dim = stations.merge(coords, on="bpuic", how="left")

    # Rapport de couverture GPS
    missing_gps = dim[dim["wgs84East"].isna()]["abreviation"].tolist()
    if missing_gps:
        print(f"  Attention : {len(missing_gps)} gare(s) sans coordonnées GPS : {missing_gps}")
    else:
        print("  Toutes les gares ont des coordonnées GPS.")

    return dim


def main() -> None:
    dim = build_dim_gare()

    print(f"\nTable finale : {len(dim)} gares × {len(dim.columns)} colonnes")
    print("Colonnes :", dim.columns.tolist())
    print()
    print(dim.to_string(index=False))

    print(f"\nÉcriture CSV  → {OUTPUT_CSV}")
    dim.to_csv(OUTPUT_CSV, index=False)

    print(f"Écriture Parquet → {OUTPUT_PARQUET}")
    dim.to_parquet(OUTPUT_PARQUET, index=False)

    print("Terminé.")


if __name__ == "__main__":
    main()
