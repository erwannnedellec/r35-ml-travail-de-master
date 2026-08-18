"""
build_vmcv_lignes_concurrentes.py
==================================
Identifie les lignes VMCV qui concurrencent la R35 par analyse de proximité
géographique entre leurs arrêts et les gares de la R35.

Logique de compétition (double critère géographique)
-----------------------------------------------------
Une ligne VMCV est déclarée concurrente si elle satisfait simultanément :
  1. Elle dessert au moins un arrêt dans un rayon RAYON_COMPETITION_METRES
     de la gare de Vevey (BPUIC 8501200), nœud de départ de la R35.
  2. Elle dessert au moins un autre arrêt dans un rayon RAYON_COMPETITION_METRES
     d'une gare R35 hors Vevey (corridor Gilamont → Blonay).

Justification : un bus qui passe par Vevey vers Villeneuve ou Châtel-St-Denis
traverse le nœud principal sans concurrencer la montée. Le critère 2 cible les
lignes qui se superposent effectivement au corridor d'adhérence Vevey–Blonay.

Inputs
------
  data/external/istdaten/istdaten_*.csv     : CSV filtrés (VMCV pré-sélectionné)
  data/dimension/full-world-traffic-point.csv : référentiel géo des arrêts (OFT)
  data/dimension/dim_gare.parquet           : gares R35 avec coordonnées WGS84

Output
------
  data/dimension/dim_vmcv_lignes_concurrentes.parquet

    Grain : une ligne par LINIEN_TEXT VMCV
    Colonnes clés (enrichies) :
      linien_text               — identifiant de ligne (ex. "215")
      nb_stops_proches_vevey    — arrêts VMCV dans le rayon de Vevey
      nb_stops_proches_corridor — arrêts VMCV dans le rayon des autres gares R35
      stops_proches_list        — noms des arrêts proches (audit)
      dist_min_r35_m            — distance minimale à une gare R35 (mètres)
      is_concurrent             — satisfait les deux critères
      rayon_metres              — constante de rayon utilisée (reproductibilité)

Usage
-----
    python scripts/build_vmcv_lignes_concurrentes.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    DIM_GARE,
    DIM_VMCV_CONCURRENTES,
    DIM_VMCV_LIGNES_PAR_GARE,
    FULL_WORLD_TRAFFIC_POINT,
    ISTDATEN_DIR,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Rayon de proximité : un arrêt bus est "proche" d'une gare R35 s'il se trouve
# dans ce rayon. 400 m correspond à ~5 min de marche, seuil standard en
# analyse d'accessibilité TP (Hansson et al., 2019 ; pratique OFT).
RAYON_COMPETITION_METRES: int = 400

# BPUIC de la gare de Vevey — nœud de départ/terminus de la R35
BPUIC_VEVEY: int = 8501200

# Fréquence minimale (courses/jour) en dessous de laquelle une ligne concurrente
# est considérée comme opérationnellement négligeable (flag is_concurrent_actif).
# La ligne 291 (~1,5 courses/jour) tombe sous ce seuil.
SEUIL_FREQUENCE_MIN_J: float = 5.0

# Paramètres du calcul de temps de marche estimé (vol d'oiseau × facteur de détour)
VITESSE_MARCHE_M_MIN: float = 83.3   # 5 km/h en m/min
FACTEUR_DETOUR: float = 1.4          # facteur standard vol d'oiseau → distance réelle piéton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------


def haversine_metres(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """Calcule la distance Haversine entre deux points GPS en mètres.

    Args:
        lon1: Longitude du point 1 (degrés décimaux WGS84).
        lat1: Latitude du point 1 (degrés décimaux WGS84).
        lon2: Longitude du point 2.
        lat2: Latitude du point 2.

    Returns:
        Distance en mètres.
    """
    rayon_terre_m = 6_371_000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return float(2 * rayon_terre_m * np.arcsin(np.sqrt(a)))


def haversine_vectorise(
    lon1: float,
    lat1: float,
    lons2: "pd.Series[float]",
    lats2: "pd.Series[float]",
) -> "pd.Series[float]":
    """Version vectorisée de haversine_metres pour un point contre plusieurs.

    Args:
        lon1: Longitude du point de référence.
        lat1: Latitude du point de référence.
        lons2: Longitudes des points cibles.
        lats2: Latitudes des points cibles.

    Returns:
        Série de distances en mètres (même index que lons2).
    """
    rayon_terre_m = 6_371_000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lats2.values)
    dphi = np.radians(lats2.values - lat1)
    dlambda = np.radians(lons2.values - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    distances = 2 * rayon_terre_m * np.arcsin(np.sqrt(a))
    return pd.Series(distances, index=lons2.index)


# ---------------------------------------------------------------------------
# Étape 1 — Extraction des arrêts VMCV depuis les fichiers ISTDATEN filtrés
# ---------------------------------------------------------------------------


def extraire_stops_vmcv(istdaten_dir: Path) -> pd.DataFrame:
    """Extrait les combinaisons uniques (LINIEN_TEXT, BPUIC) pour les lignes VMCV.

    Lit tous les fichiers istdaten_*.csv du répertoire, filtre les lignes VMCV
    et retourne les paires arrêt–ligne uniques, avec le nom de l'arrêt.

    Args:
        istdaten_dir: Répertoire contenant les CSV istdaten filtrés mensuels.

    Returns:
        DataFrame avec colonnes ['linien_text', 'bpuic', 'nom_arret'],
        sans doublons, trié par linien_text puis bpuic.

    Raises:
        FileNotFoundError: Si aucun fichier CSV n'est trouvé dans le répertoire.
    """
    fichiers = sorted(istdaten_dir.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {istdaten_dir}")

    log.info("Lecture de %d fichiers ISTDATEN pour extraire les stops VMCV…", len(fichiers))

    cols_utiles = ["BETREIBER_ABK", "LINIEN_TEXT", "BPUIC", "HALTESTELLEN_NAME"]

    morceaux: list[pd.DataFrame] = []
    for fich in fichiers:
        _kwargs = dict(sep=";", usecols=cols_utiles,
                       dtype={"BPUIC": "Int64", "LINIEN_TEXT": str}, low_memory=False)
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **_kwargs)
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **_kwargs)
            log.warning("Encodage latin-1 pour %s", fich.name)
        vmcv = df[df["BETREIBER_ABK"] == "VMCV"][
            ["LINIEN_TEXT", "BPUIC", "HALTESTELLEN_NAME"]
        ].drop_duplicates()
        morceaux.append(vmcv)

    resultat = (
        pd.concat(morceaux, ignore_index=True)
        .drop_duplicates(subset=["LINIEN_TEXT", "BPUIC"])
        .rename(columns={
            "LINIEN_TEXT": "linien_text",
            "BPUIC": "bpuic",
            "HALTESTELLEN_NAME": "nom_arret",
        })
        .sort_values(["linien_text", "bpuic"])
        .reset_index(drop=True)
    )

    # Normalisation : certains LINIEN_TEXT sont vides ou NaN → filtre
    resultat = resultat[resultat["linien_text"].notna() & (resultat["linien_text"] != "")]

    log.info(
        "  → %d combinaisons (ligne, arrêt) uniques, %d lignes VMCV distinctes, %d BPUICs uniques",
        len(resultat),
        resultat["linien_text"].nunique(),
        resultat["bpuic"].nunique(),
    )
    return resultat


# ---------------------------------------------------------------------------
# Étape 1b — Fréquence journalière par ligne VMCV
# ---------------------------------------------------------------------------


def calculer_frequence_vmcv(istdaten_dir: Path) -> pd.DataFrame:
    """Calcule la fréquence journalière moyenne de chaque ligne VMCV.

    Pour chaque fichier mensuel, compte les courses uniques par (date, ligne)
    puis agrège en moyenne sur l'ensemble de la période disponible.
    Une « course unique » = un FAHRT_BEZEICHNER distinct sur une journée donnée.

    Args:
        istdaten_dir: Répertoire contenant les CSV istdaten filtrés mensuels.

    Returns:
        DataFrame avec colonnes ['linien_text', 'frequence_moy_j'],
        indexé sur l'ensemble des lignes VMCV présentes dans les données.
    """
    fichiers = sorted(istdaten_dir.glob("istdaten_*.csv"))
    cols = ["BETRIEBSTAG", "BETREIBER_ABK", "LINIEN_TEXT", "FAHRT_BEZEICHNER"]

    morceaux: list[pd.DataFrame] = []
    for fich in fichiers:
        _kwargs = dict(sep=";", usecols=cols,
                       dtype={"LINIEN_TEXT": str, "FAHRT_BEZEICHNER": str}, low_memory=False)
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **_kwargs)
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **_kwargs)
        df = df[df["BETREIBER_ABK"] == "VMCV"][
            ["BETRIEBSTAG", "LINIEN_TEXT", "FAHRT_BEZEICHNER"]
        ].drop_duplicates()
        morceaux.append(df)

    df_all = pd.concat(morceaux, ignore_index=True).drop_duplicates()

    # Nombre de courses uniques par (date, ligne)
    courses_par_j = (
        df_all.groupby(["BETRIEBSTAG", "LINIEN_TEXT"])["FAHRT_BEZEICHNER"]
        .nunique()
        .reset_index(name="nb_courses")
    )

    frequences = (
        courses_par_j.groupby("LINIEN_TEXT")["nb_courses"]
        .mean()
        .round(1)
        .reset_index()
        .rename(columns={"nb_courses": "frequence_moy_j", "LINIEN_TEXT": "linien_text"})
    )
    log.info(
        "Fréquences calculées sur %d jours-lignes distincts",
        len(courses_par_j),
    )
    return frequences


# ---------------------------------------------------------------------------
# Étape 2 — Géocodage des arrêts VMCV via le référentiel OFT
# ---------------------------------------------------------------------------


def geocoder_stops_vmcv(
    stops_vmcv: pd.DataFrame,
    chemin_ref: Path,
) -> pd.DataFrame:
    """Ajoute les coordonnées WGS84 à chaque arrêt VMCV via le référentiel OFT.

    Agrège les bordures d'arrêt (BOARDING_PLATFORM) par BPUIC en prenant
    le centroïde (moyenne des coordonnées non nulles), ce qui donne une
    position représentative de l'arrêt même quand plusieurs quais existent.

    Args:
        stops_vmcv: DataFrame avec au moins une colonne 'bpuic' (Int64).
        chemin_ref: Chemin vers full-world-traffic-point.csv.

    Returns:
        stops_vmcv enrichi des colonnes ['lon', 'lat', 'nb_quais'].
        Les arrêts sans correspondance géo reçoivent NaN et un log d'alerte.
    """
    log.info("Chargement du référentiel géo OFT (%s)…", chemin_ref.name)
    ref = pd.read_csv(
        chemin_ref,
        sep=";",
        encoding="utf-8-sig",
        low_memory=False,
        usecols=["number", "wgs84East", "wgs84North", "trafficPointElementType", "status"],
        dtype={"number": "Int64"},
    )

    # Filtre : bordures d'arrêt valides avec coordonnées
    ref_clean = ref[
        (ref["trafficPointElementType"] == "BOARDING_PLATFORM")
        & (ref["status"] == "VALIDATED")
        & (ref["wgs84East"].notna())
        & (ref["wgs84North"].notna())
    ].copy()

    # Centroïde par BPUIC
    centroides = (
        ref_clean.groupby("number")[["wgs84East", "wgs84North"]]
        .agg(lon=("wgs84East", "mean"), lat=("wgs84North", "mean"), nb_quais=("wgs84East", "count"))
        .reset_index()
        .rename(columns={"number": "bpuic"})
    )

    enrichi = stops_vmcv.merge(centroides, on="bpuic", how="left")

    nb_sans_geo = enrichi["lon"].isna().sum()
    if nb_sans_geo > 0:
        manquants = enrichi.loc[enrichi["lon"].isna(), "bpuic"].unique()
        log.warning(
            "%d arrêts VMCV sans coordonnées dans le référentiel : %s",
            nb_sans_geo,
            manquants.tolist(),
        )

    log.info(
        "  → %d/%d arrêts géocodés (%.1f%%)",
        len(enrichi) - nb_sans_geo,
        len(enrichi),
        100 * (len(enrichi) - nb_sans_geo) / len(enrichi),
    )
    return enrichi


# ---------------------------------------------------------------------------
# Étape 3 — Calcul des distances aux gares R35
# ---------------------------------------------------------------------------


def calculer_proximite_r35(
    stops_geocodes: pd.DataFrame,
    gares_r35: pd.DataFrame,
    rayon_m: int,
) -> pd.DataFrame:
    """Calcule la distance minimale de chaque arrêt VMCV aux gares R35.

    Pour chaque arrêt VMCV géocodé, calcule la distance Haversine à chacune
    des 19 gares R35 et conserve la distance minimale et la gare la plus proche.
    Marque ensuite si l'arrêt est "proche" de Vevey spécifiquement, et s'il
    est proche d'une autre gare R35 (corridor hors Vevey).

    Args:
        stops_geocodes: DataFrame avec ['bpuic', 'linien_text', 'lon', 'lat'].
        gares_r35: DataFrame dim_gare avec ['bpuic', 'wgs84East', 'wgs84North', 'nom'].
        rayon_m: Rayon de proximité en mètres.

    Returns:
        stops_geocodes enrichi de ['dist_min_r35_m', 'gare_r35_proche',
        'proche_vevey', 'proche_corridor'].
    """
    # Filtre les arrêts sans coordonnées
    valides = stops_geocodes.dropna(subset=["lon", "lat"]).copy()

    distances_min: list[float] = []
    gares_proches: list[str] = []
    proche_vevey_flags: list[bool] = []
    proche_corridor_flags: list[bool] = []

    gares_non_vevey = gares_r35[gares_r35["bpuic"] != BPUIC_VEVEY]
    gare_vevey = gares_r35[gares_r35["bpuic"] == BPUIC_VEVEY].iloc[0]

    for _, arret in valides.iterrows():
        # Distance à toutes les gares R35
        dists = haversine_vectorise(
            arret["lon"], arret["lat"],
            gares_r35["wgs84East"], gares_r35["wgs84North"],
        )
        idx_min = dists.idxmin()
        dist_min = dists.min()
        distances_min.append(dist_min)
        gares_proches.append(gares_r35.loc[idx_min, "nom"])

        # Critère 1 : proche de Vevey ?
        dist_vevey = haversine_metres(
            arret["lon"], arret["lat"],
            gare_vevey["wgs84East"], gare_vevey["wgs84North"],
        )
        proche_vevey_flags.append(dist_vevey <= rayon_m)

        # Critère 2 : proche d'une gare du corridor (hors Vevey) ?
        if len(gares_non_vevey) > 0:
            dists_corridor = haversine_vectorise(
                arret["lon"], arret["lat"],
                gares_non_vevey["wgs84East"], gares_non_vevey["wgs84North"],
            )
            proche_corridor_flags.append(dists_corridor.min() <= rayon_m)
        else:
            proche_corridor_flags.append(False)

    valides = valides.copy()
    valides["dist_min_r35_m"] = distances_min
    valides["gare_r35_proche"] = gares_proches
    valides["proche_vevey"] = proche_vevey_flags
    valides["proche_corridor"] = proche_corridor_flags

    # Réintègre les lignes sans coordonnées avec NaN
    resultat = stops_geocodes.merge(
        valides[["bpuic", "linien_text", "dist_min_r35_m", "gare_r35_proche",
                 "proche_vevey", "proche_corridor"]],
        on=["bpuic", "linien_text"],
        how="left",
    )
    return resultat


# ---------------------------------------------------------------------------
# Étape 3b — Attribution directe (linien_text, gare_abreviation)
# ---------------------------------------------------------------------------


def calculer_lignes_par_gare_r35(
    stops_geocodes: pd.DataFrame,
    gares_r35: pd.DataFrame,
    rayon_m: int,
) -> pd.DataFrame:
    """Construit la table (linien_text, gare_abreviation) par proximite reelle.

    Pour chaque gare R35, identifie les lignes VMCV ayant au moins un stop
    dans le rayon de competition. Produit toutes les paires valides sans proxy.

    Args:
        stops_geocodes: DataFrame avec ['linien_text', 'bpuic', 'lon', 'lat'].
        gares_r35: DataFrame dim_gare avec ['abreviation', 'wgs84East', 'wgs84North'].
        rayon_m: Rayon de proximite en metres.

    Returns:
        DataFrame avec colonnes ['linien_text', 'gare_abreviation'],
        une ligne par paire (ligne VMCV, gare R35) effective.
    """
    valides = stops_geocodes.dropna(subset=["lon", "lat"]).copy()

    pairs: list[dict] = []
    for _, gare in gares_r35.iterrows():
        dists = haversine_vectorise(
            gare["wgs84East"], gare["wgs84North"],
            valides["lon"], valides["lat"],
        )
        lignes_proches = valides.loc[dists <= rayon_m, "linien_text"].unique()
        for lt in lignes_proches:
            pairs.append({
                "linien_text": lt,
                "gare_abreviation": gare["abreviation"],
            })

    if not pairs:
        log.warning("Aucune paire (ligne VMCV, gare R35) trouvee dans le rayon %dm", rayon_m)
        return pd.DataFrame(columns=["linien_text", "gare_abreviation"])

    result = (
        pd.DataFrame(pairs)
        .drop_duplicates()
        .sort_values(["gare_abreviation", "linien_text"])
        .reset_index(drop=True)
    )
    log.info(
        "Attribution par gare : %d paires (ligne, gare) | %d gares avec au moins 1 ligne",
        len(result),
        result["gare_abreviation"].nunique(),
    )
    return result


# ---------------------------------------------------------------------------
# Étape 4 — Agrégation par ligne et application du double critère
# ---------------------------------------------------------------------------


def identifier_lignes_concurrentes(
    stops_avec_distances: pd.DataFrame,
    frequences: pd.DataFrame,
    rayon_m: int,
) -> pd.DataFrame:
    """Agrège par ligne VMCV et applique le double critère de concurrence.

    Enrichit le résultat avec la fréquence journalière, le temps de marche
    estimé et le flag is_concurrent_actif (fréquence ≥ SEUIL_FREQUENCE_MIN_J).

    Args:
        stops_avec_distances: DataFrame avec ['linien_text', 'bpuic', 'nom_arret',
            'dist_min_r35_m', 'proche_vevey', 'proche_corridor'].
        frequences: DataFrame ['linien_text', 'frequence_moy_j'] issu de
            calculer_frequence_vmcv().
        rayon_m: Rayon utilisé (conservé dans l'output pour reproductibilité).

    Returns:
        DataFrame grain LINIEN_TEXT avec les colonnes de résultat.
    """
    # Calcul de stops_proches_list séparément pour éviter le problème du
    # closure sur s.name dans un lambda groupby (s.name = nom de colonne,
    # pas la clé de groupe).
    proches_par_ligne = (
        stops_avec_distances[
            stops_avec_distances["proche_vevey"] | stops_avec_distances["proche_corridor"]
        ]
        .groupby("linien_text")["nom_arret"]
        .apply(lambda s: ", ".join(sorted(s.dropna().unique())))
        .rename("stops_proches_list")
        .reset_index()
    )

    agregat = (
        stops_avec_distances.groupby("linien_text")
        .agg(
            nb_stops_proches_vevey=("proche_vevey", "sum"),
            nb_stops_proches_corridor=("proche_corridor", "sum"),
            dist_min_r35_m=("dist_min_r35_m", "min"),
        )
        .reset_index()
        .merge(proches_par_ligne, on="linien_text", how="left")
        .assign(stops_proches_list=lambda df: df["stops_proches_list"].fillna(""))
    )

    # Double critère de concurrence géographique
    agregat["is_concurrent"] = (
        (agregat["nb_stops_proches_vevey"] >= 1)
        & (agregat["nb_stops_proches_corridor"] >= 1)
    )
    agregat["rayon_metres"] = rayon_m

    # Temps de marche estimé vers la gare R35 la plus proche
    # Formule : distance vol d'oiseau × facteur détour / vitesse piéton
    agregat["temps_marche_min_estime"] = (
        agregat["dist_min_r35_m"] * FACTEUR_DETOUR / VITESSE_MARCHE_M_MIN
    ).round(1)

    # Fréquence journalière moyenne (depuis données historiques complètes)
    agregat = agregat.merge(frequences, on="linien_text", how="left")
    agregat["frequence_moy_j"] = agregat["frequence_moy_j"].fillna(0.0)

    # Concurrent actif = concurrent géographique ET fréquence suffisante
    agregat["is_concurrent_actif"] = (
        agregat["is_concurrent"]
        & (agregat["frequence_moy_j"] >= SEUIL_FREQUENCE_MIN_J)
    )

    return agregat.sort_values("dist_min_r35_m").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def construire_dim_vmcv_concurrentes() -> pd.DataFrame:
    """Orchestre les quatre étapes et écrit le parquet de sortie.

    Returns:
        DataFrame final dim_vmcv_lignes_concurrentes.
    """
    # Étape 1a : stops VMCV depuis ISTDATEN
    stops_vmcv = extraire_stops_vmcv(ISTDATEN_DIR)

    # Étape 1b : fréquences journalières (second passage sur les mêmes fichiers)
    log.info("Calcul des fréquences journalières VMCV…")
    frequences = calculer_frequence_vmcv(ISTDATEN_DIR)

    # Étape 2 : géocodage
    stops_geocodes = geocoder_stops_vmcv(stops_vmcv, FULL_WORLD_TRAFFIC_POINT)

    # Étape 3 : chargement dim_gare et calcul distances
    log.info("Chargement dim_gare R35…")
    gares_r35 = pd.read_parquet(
        DIM_GARE,
        columns=["bpuic", "nom", "abreviation", "wgs84East", "wgs84North"],
    )
    assert gares_r35["wgs84East"].notna().all(), "Coordonnées manquantes dans dim_gare"
    assert BPUIC_VEVEY in gares_r35["bpuic"].values, (
        f"BPUIC Vevey ({BPUIC_VEVEY}) absent de dim_gare — vérifier le fichier"
    )
    log.info("  → %d gares R35 chargées", len(gares_r35))

    log.info(
        "Calcul des distances Haversine (rayon = %d m)…", RAYON_COMPETITION_METRES
    )
    stops_avec_distances = calculer_proximite_r35(
        stops_geocodes, gares_r35, RAYON_COMPETITION_METRES
    )

    # Étape 3b : attribution directe par gare (sans proxy)
    log.info("Calcul de l'attribution (linien_text, gare_abreviation) par gare R35…")
    lignes_par_gare = calculer_lignes_par_gare_r35(
        stops_geocodes, gares_r35, RAYON_COMPETITION_METRES
    )

    # Étape 4 : agrégation, critère de concurrence et enrichissement
    dim = identifier_lignes_concurrentes(
        stops_avec_distances, frequences, RAYON_COMPETITION_METRES
    )

    # Écriture atomique — table principale
    DIM_VMCV_CONCURRENTES.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_VMCV_CONCURRENTES.with_suffix(".tmp.parquet")
    try:
        dim.to_parquet(tmp, index=False)
        tmp.rename(DIM_VMCV_CONCURRENTES)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    log.info("Écrit : %s (%d lignes)", DIM_VMCV_CONCURRENTES, len(dim))

    # Écriture atomique — table per-gare
    tmp2 = DIM_VMCV_LIGNES_PAR_GARE.with_suffix(".tmp.parquet")
    try:
        lignes_par_gare.to_parquet(tmp2, index=False)
        tmp2.rename(DIM_VMCV_LIGNES_PAR_GARE)
    except Exception:
        tmp2.unlink(missing_ok=True)
        raise
    log.info("Écrit : %s (%d paires ligne-gare)", DIM_VMCV_LIGNES_PAR_GARE, len(lignes_par_gare))

    return dim


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    dim = construire_dim_vmcv_concurrentes()

    actives = dim[dim["is_concurrent_actif"]]
    geo_seul = dim[dim["is_concurrent"] & ~dim["is_concurrent_actif"]]
    non_concurrentes = dim[~dim["is_concurrent"]]

    print("\n" + "=" * 70)
    print(f"Rayon : {RAYON_COMPETITION_METRES} m  |  "
          f"Seuil fréquence : {SEUIL_FREQUENCE_MIN_J} courses/j")
    print(f"Total lignes VMCV analysées        : {len(dim)}")
    print(f"Concurrentes actives (géo + freq)  : {len(actives)}")
    print(f"Concurrentes géo uniquement (exclues par fréquence) : {len(geo_seul)}")
    print(f"Non concurrentes                   : {len(non_concurrentes)}")

    print("\n--- Lignes CONCURRENTES ACTIVES (retenues pour les features ML) ---")
    print(
        actives[
            ["linien_text", "frequence_moy_j", "temps_marche_min_estime",
             "nb_stops_proches_vevey", "nb_stops_proches_corridor", "stops_proches_list"]
        ].to_string(index=False)
    )

    if len(geo_seul) > 0:
        print("\n--- Lignes géographiquement concurrentes mais fréquence trop faible ---")
        print(
            geo_seul[["linien_text", "frequence_moy_j", "dist_min_r35_m"]
                     ].to_string(index=False)
        )

    print("\n--- Top 5 non concurrentes (les plus proches géographiquement) ---")
    print(
        non_concurrentes.head(5)[
            ["linien_text", "frequence_moy_j", "dist_min_r35_m",
             "nb_stops_proches_vevey", "nb_stops_proches_corridor"]
        ].to_string(index=False)
    )
