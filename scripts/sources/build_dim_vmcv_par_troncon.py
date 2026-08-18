"""
build_dim_vmcv_par_troncon.py
================================
Calcule 3 features de concurrence modale VMCV au grain tronçon × train × jour.

Contexte et motivation
-----------------------
La concurrence VMCV est mesurée via trois dimensions comparables à la
décision modale du voyageur au moment t :

  vmcv_delta_attente_min   : (attente avant R35) - (attente avant prochain VMCV)
                             Positif si VMCV arrive avant le R35 → VMCV avantageux
  vmcv_delta_trajet_min    : (trajet R35 sur tronçon) - (trajet VMCV équivalent)
                             Positif si VMCV est plus rapide → VMCV avantageux
  vmcv_delta_frequence_h   : (fréquence VMCV) - (fréquence R35) dans la fenêtre ±30min
                             Positif si VMCV est plus fréquent → VMCV avantageux

NB : la convention de signe de delta_frequence est inversée par rapport à la
définition littérale de la spec (freq_VMCV - freq_R35 au lieu de freq_R35 -
freq_VMCV) afin d'être cohérente avec la convention globale "delta > 0 = VMCV
meilleur" (ADR-020).

Couverture attendue
--------------------
Les données VMCV dans ISTDATEN débutent en octobre 2018. Avant cette date,
toutes les features sont NaN (XGBoost gère nativement).

Seuls les tronçons dont les DEUX gares ont un arrêt VMCV dans le rayon de
RAYON_PROXIMITE_M mètres auront des features non-NaN. En pratique :
  - VV↔GIL (lignes 202 et 215 actives)
  - Éventuellement GIL↔VVVI si ligne 202 dessert aussi VVVI
  - Tous les tronçons hauts (Blonay-Pléiades) : 100% NaN, aucune alternative bus

Logique J-2
-----------
Ce script produit les features à la date RÉELLE du service R35 (pas J+2).
Le décalage J-2 est appliqué lors de la jointure dans
add_istdaten_to_raw_stacked.py (même logique que dim_profil_train).

Inputs
------
  data/processed/sources/istdaten_clean.parquet
  data/external/istdaten/istdaten_*.csv
  data/dimension/dim_gare.parquet
  data/dimension/full-world-traffic-point.csv
  data/dimension/dim_vmcv_lignes_concurrentes.parquet

Output
------
  data/processed/sources/dim_vmcv_par_troncon.parquet

Grain : (date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)
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
    DIM_VMCV_PAR_TRONCON,
    FULL_WORLD_TRAFFIC_POINT,
    ISTDATEN_CLEAN,
    ISTDATEN_DIR,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAYON_PROXIMITE_M: int = 200
FENETRE_ATTENTE_AMONT_MIN: int = 5    # R35 departure: traveler arrives 5min before
FENETRE_ATTENTE_AVAL_MIN: int = 30    # Next VMCV searched up to 30min after R35
FENETRE_FREQUENCE_MIN: int = 30       # Frequency window: ±30min around R35 dep

DEBUT_VMCV_ISTDATEN: pd.Timestamp = pd.Timestamp("2018-10-01")
STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Haversine vectorisé (repris de build_vmcv_lignes_concurrentes.py)
# ---------------------------------------------------------------------------


def _haversine_vec(
    lon1: float, lat1: float,
    lons2: pd.Series, lats2: pd.Series,
) -> pd.Series:
    R = 6_371_000
    phi1, phi2 = np.radians(lat1), np.radians(lats2.values)
    dphi = np.radians(lats2.values - lat1)
    dl = np.radians(lons2.values - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dl / 2) ** 2
    return pd.Series(2 * R * np.arcsin(np.sqrt(a)), index=lons2.index)


# ---------------------------------------------------------------------------
# Étape 1 — Mapping statique : tronçon R35 → paires d'arrêts VMCV alternatives
# ---------------------------------------------------------------------------


def _geocoder_arrets_vmcv(
    stops_vmcv: pd.DataFrame,   # (linien_text, bpuic)
    full_world: Path,
) -> pd.DataFrame:
    """Ajoute lon/lat à chaque arrêt VMCV via full-world-traffic-point.csv."""
    ref = pd.read_csv(
        full_world,
        sep=";",
        encoding="utf-8-sig",
        low_memory=False,
        usecols=["number", "wgs84East", "wgs84North", "trafficPointElementType", "status"],
        dtype={"number": "Int64"},
    )
    ref_clean = ref[
        (ref["trafficPointElementType"] == "BOARDING_PLATFORM")
        & (ref["status"] == "VALIDATED")
        & ref["wgs84East"].notna()
    ]
    centroides = (
        ref_clean.groupby("number")[["wgs84East", "wgs84North"]]
        .mean()
        .reset_index()
        .rename(columns={"number": "bpuic", "wgs84East": "lon", "wgs84North": "lat"})
    )
    return stops_vmcv.merge(centroides, on="bpuic", how="left")


def _identifier_arrets_vmcv_proches(
    gares_r35: pd.DataFrame,
    arrets_vmcv_geo: pd.DataFrame,   # (linien_text, bpuic, lon, lat)
    lignes_actives: frozenset[str],
    rayon_m: int,
) -> pd.DataFrame:
    """Retourne (gare_r35_bpuic, bpuic_vmcv, linien_text) pour les stops dans rayon_m."""
    valides = arrets_vmcv_geo.dropna(subset=["lon", "lat"])
    valides = valides[valides["linien_text"].isin(lignes_actives)]

    results: list[pd.DataFrame] = []
    for _, gare in gares_r35.iterrows():
        dists = _haversine_vec(
            gare["wgs84East"], gare["wgs84North"], valides["lon"], valides["lat"]
        )
        proches = valides.loc[dists <= rayon_m, ["linien_text", "bpuic"]].copy()
        proches["gare_r35_bpuic"] = gare["bpuic"]
        results.append(proches)

    if not results:
        return pd.DataFrame(columns=["gare_r35_bpuic", "bpuic_vmcv", "linien_text"])

    return (
        pd.concat(results, ignore_index=True)
        .rename(columns={"bpuic": "bpuic_vmcv"})
        .drop_duplicates()
    )


def _construire_mapping_troncons(
    gares_r35: pd.DataFrame,
    arrets_proches: pd.DataFrame,   # (gare_r35_bpuic, bpuic_vmcv, linien_text)
) -> pd.DataFrame:
    """Construit la table (gare_depart_bpuic, gare_arrivee_bpuic, sens, bpuic_vmcv_dep, bpuic_vmcv_arr, linien_text).

    Pour chaque tronçon R35 adjacent (en km order), identifie les lignes VMCV
    qui ont des arrêts proches des DEUX extrémités.
    """
    gares_sorted = gares_r35.sort_values("km").reset_index(drop=True)

    # Adjacent pairs — both ascending and descending directions
    pairs: list[dict] = []
    for i in range(len(gares_sorted) - 1):
        g_a = gares_sorted.iloc[i]   # lower km
        g_b = gares_sorted.iloc[i + 1]  # higher km
        pairs.append({"gare_depart_bpuic": g_a["bpuic"], "gare_arrivee_bpuic": g_b["bpuic"], "sens": "VV -> PLEI"})
        pairs.append({"gare_depart_bpuic": g_b["bpuic"], "gare_arrivee_bpuic": g_a["bpuic"], "sens": "PLEI -> VV"})

    troncons_r35 = pd.DataFrame(pairs)

    dep_stops = arrets_proches.rename(columns={
        "gare_r35_bpuic": "gare_depart_bpuic",
        "bpuic_vmcv": "bpuic_vmcv_dep",
    })
    arr_stops = arrets_proches.rename(columns={
        "gare_r35_bpuic": "gare_arrivee_bpuic",
        "bpuic_vmcv": "bpuic_vmcv_arr",
    })

    mapping = (
        troncons_r35
        .merge(dep_stops, on="gare_depart_bpuic")
        .merge(arr_stops, on=["gare_arrivee_bpuic", "linien_text"])
    )
    # Drop degenerate pairs (same VMCV stop on both ends)
    mapping = mapping[mapping["bpuic_vmcv_dep"] != mapping["bpuic_vmcv_arr"]]

    return mapping[
        ["gare_depart_bpuic", "gare_arrivee_bpuic", "sens", "bpuic_vmcv_dep", "bpuic_vmcv_arr", "linien_text"]
    ].drop_duplicates().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Étape 2 — Extraction des passages VMCV depuis les CSV bruts ISTDATEN
# ---------------------------------------------------------------------------


def _lire_passages_vmcv(bpuics_pertinents: frozenset[int]) -> pd.DataFrame:
    """Lit tous les fichiers ISTDATEN, extrait les passages VMCV aux BPUICs pertinents.

    Retourne un DataFrame avec l'heure effective (réelle si REAL/GESCHAETZT,
    sinon théorique) de départ et d'arrivée par (date, fahrt, bpuic).
    """
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")

    cols_utiles = [
        "BETRIEBSTAG", "BETREIBER_ABK", "LINIEN_TEXT", "FAHRT_BEZEICHNER",
        "BPUIC", "HALTESTELLEN_NAME",
        "ANKUNFTSZEIT", "ABFAHRTSZEIT",
        "AN_PROGNOSE", "AB_PROGNOSE",
        "AN_PROGNOSE_STATUS", "AB_PROGNOSE_STATUS",
        "FAELLT_AUS_TF", "DURCHFAHRT_TF",
    ]
    dtype_map = {
        "BETREIBER_ABK": str, "LINIEN_TEXT": str, "FAHRT_BEZEICHNER": str,
        "BPUIC": "Int64", "AN_PROGNOSE_STATUS": str, "AB_PROGNOSE_STATUS": str,
        "FAELLT_AUS_TF": str, "DURCHFAHRT_TF": str,
    }

    fragments: list[pd.DataFrame] = []
    n_total = len(fichiers)

    for i, fich in enumerate(fichiers, 1):
        _kw = dict(sep=";", usecols=cols_utiles, dtype=dtype_map, low_memory=False)
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **_kw)
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **_kw)
            log.warning("Encodage latin-1 pour %s", fich.name)

        # Filter: VMCV only, not cancelled, not through service, BPUIC pertinent
        masque = (
            (df["BETREIBER_ABK"] == "VMCV")
            & (df["FAELLT_AUS_TF"].str.lower() != "true")
            & (df["DURCHFAHRT_TF"].str.lower() != "true")
            & df["BPUIC"].isin(bpuics_pertinents)
        )
        df_v = df.loc[masque].copy()
        if df_v.empty:
            log.info("[%02d/%02d] %s : 0 passages VMCV pertinents", i, n_total, fich.name)
            continue

        df_v["date"] = pd.to_datetime(df_v["BETRIEBSTAG"], format="%d.%m.%Y", errors="coerce")
        df_v["horaire_dep"] = pd.to_datetime(df_v["ABFAHRTSZEIT"], format="%d.%m.%Y %H:%M", errors="coerce")
        df_v["horaire_arr"] = pd.to_datetime(df_v["ANKUNFTSZEIT"], format="%d.%m.%Y %H:%M", errors="coerce")
        df_v["reel_dep"] = pd.to_datetime(df_v["AB_PROGNOSE"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
        df_v["reel_arr"] = pd.to_datetime(df_v["AN_PROGNOSE"], format="%d.%m.%Y %H:%M:%S", errors="coerce")

        statut_dep_ok = df_v["AB_PROGNOSE_STATUS"].isin(STATUTS_REELS)
        statut_arr_ok = df_v["AN_PROGNOSE_STATUS"].isin(STATUTS_REELS)
        df_v["h_dep_eff"] = df_v["reel_dep"].where(statut_dep_ok, df_v["horaire_dep"])
        df_v["h_arr_eff"] = df_v["reel_arr"].where(statut_arr_ok, df_v["horaire_arr"])

        fragments.append(df_v[[
            "date", "LINIEN_TEXT", "FAHRT_BEZEICHNER", "BPUIC",
            "h_dep_eff", "h_arr_eff",
        ]].rename(columns={"LINIEN_TEXT": "linien_text", "FAHRT_BEZEICHNER": "fahrt", "BPUIC": "bpuic"}))
        log.info("[%02d/%02d] %s : %d passages VMCV pertinents", i, n_total, fich.name, len(df_v))

    if not fragments:
        log.warning("Aucun passage VMCV trouvé pour les BPUICs pertinents.")
        return pd.DataFrame(columns=["date", "linien_text", "fahrt", "bpuic", "h_dep_eff", "h_arr_eff"])

    return pd.concat(fragments, ignore_index=True)


# ---------------------------------------------------------------------------
# Étape 3 — Reconstruction des tronçons VMCV
# ---------------------------------------------------------------------------


def _reconstruire_troncons_vmcv(
    passages: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Reconstruit les paires (dep, arr) VMCV à partir des passages par arrêt.

    Pour chaque fahrt, joint les passages aux stops de départ avec les passages
    aux stops d'arrivée et filtre pour ne garder que les paires dans le mapping.
    La condition h_dep < h_arr assure le bon sens de circulation.

    Retourne: (date, linien_text, fahrt, bpuic_vmcv_dep, bpuic_vmcv_arr,
               h_dep_vmcv, h_arr_vmcv, trajet_vmcv_min)
    """
    bpuics_dep = frozenset(mapping["bpuic_vmcv_dep"])
    bpuics_arr = frozenset(mapping["bpuic_vmcv_arr"])

    dep_rows = passages[passages["bpuic"].isin(bpuics_dep)].rename(columns={
        "bpuic": "bpuic_vmcv_dep", "h_dep_eff": "h_dep_vmcv",
    })[["date", "linien_text", "fahrt", "bpuic_vmcv_dep", "h_dep_vmcv"]]

    arr_rows = passages[passages["bpuic"].isin(bpuics_arr)].rename(columns={
        "bpuic": "bpuic_vmcv_arr", "h_arr_eff": "h_arr_vmcv",
    })[["date", "linien_text", "fahrt", "bpuic_vmcv_arr", "h_arr_vmcv"]]

    # Cross-join within each fahrt (bounded by small number of relevant stops/fahrt)
    joined = dep_rows.merge(arr_rows, on=["date", "linien_text", "fahrt"])

    # Keep only chronologically ordered pairs that are in our mapping
    paires_valides = mapping[["bpuic_vmcv_dep", "bpuic_vmcv_arr"]].drop_duplicates()
    troncons = joined.merge(paires_valides, on=["bpuic_vmcv_dep", "bpuic_vmcv_arr"])
    troncons = troncons[
        troncons["h_dep_vmcv"].notna()
        & troncons["h_arr_vmcv"].notna()
        & (troncons["h_dep_vmcv"] < troncons["h_arr_vmcv"])
    ].copy()

    troncons["trajet_vmcv_min"] = (
        (troncons["h_arr_vmcv"] - troncons["h_dep_vmcv"]).dt.total_seconds() / 60
    )

    # Sanity: reject implausible travel times (> 60 min or ≤ 0)
    troncons = troncons[troncons["trajet_vmcv_min"].between(0.5, 60, inclusive="right")]

    return troncons[["date", "linien_text", "fahrt", "bpuic_vmcv_dep", "bpuic_vmcv_arr",
                      "h_dep_vmcv", "h_arr_vmcv", "trajet_vmcv_min"]]


# ---------------------------------------------------------------------------
# Étape 4 — Horaires R35 au grain tronçon
# ---------------------------------------------------------------------------


def _charger_horaires_r35_troncons(gares_r35: pd.DataFrame) -> pd.DataFrame:
    """Construit les horaires R35 au grain (date, train, gare_dep, gare_arr, sens).

    Utilise les heures effectives (réelles si REAL/GESCHAETZT, sinon théoriques).
    Exclut les trains annulés.
    """
    df = pd.read_parquet(ISTDATEN_CLEAN)
    df["date"] = pd.to_datetime(df["date"])
    km_map = dict(zip(gares_r35["bpuic"], gares_r35["km"]))

    df = df[df["bpuic"].isin(km_map) & ~df["is_annule"]].copy()
    df["km"] = df["bpuic"].map(km_map)

    # Effective departure and arrival times
    dep_ok = df["statut_depart"].isin(STATUTS_REELS)
    arr_ok = df["statut_arrivee"].isin(STATUTS_REELS)
    df["h_dep_eff"] = df["reel_depart"].where(dep_ok, df["horaire_depart"])
    df["h_arr_eff"] = df["reel_arrivee"].where(arr_ok, df["horaire_arrivee"])
    df["h_dep_eff"] = pd.to_datetime(df["h_dep_eff"])

    # Sort to reconstruct tronçons (consecutive stops by effective departure time)
    df = df.sort_values(["date", "numero_train", "h_dep_eff"]).reset_index(drop=True)

    # Shift to get next stop within each (date, train)
    next_cols = df.groupby(["date", "numero_train"], sort=False)[
        ["bpuic", "km", "h_arr_eff"]
    ].shift(-1)
    next_cols.columns = ["bpuic_arr", "km_arr", "h_arr_troncon"]

    df = pd.concat([df[["date", "numero_train", "bpuic", "km", "h_dep_eff", "h_arr_eff"]],
                    next_cols], axis=1)
    df = df.dropna(subset=["bpuic_arr"])
    df["bpuic_arr"] = df["bpuic_arr"].astype(int)

    df["sens"] = np.where(df["km"] < df["km_arr"], "VV -> PLEI", "PLEI -> VV")
    df["trajet_r35_min"] = (
        (df["h_arr_troncon"] - df["h_dep_eff"]).dt.total_seconds() / 60
    )
    # Reject implausible R35 travel times
    df = df[df["trajet_r35_min"].between(0, 60, inclusive="right")]

    return df.rename(columns={
        "bpuic": "gare_depart_bpuic",
        "bpuic_arr": "gare_arrivee_bpuic",
        "h_dep_eff": "h_dep_r35",
        "h_arr_troncon": "h_arr_r35",
    })[["date", "numero_train", "gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
        "h_dep_r35", "h_arr_r35", "trajet_r35_min"]]


# ---------------------------------------------------------------------------
# Étape 5 — Calcul des trois features delta
# ---------------------------------------------------------------------------

GRAIN = ["date", "numero_train", "gare_depart_bpuic", "gare_arrivee_bpuic", "sens"]


def _calculer_deltas(
    r35_troncons: pd.DataFrame,
    vmcv_troncons: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Calcule les trois features delta pour chaque tronçon R35.

    delta_attente_min  : h_dep_r35 - h_dep_vmcv (en minutes), max sur les VMCV
                         dans [h_dep_r35 − AMONT, h_dep_r35 + AVAL].
                         NaN si aucun VMCV dans la fenêtre attente.
    delta_trajet_min   : trajet_r35 − trajet_vmcv_moyen_journalier (en minutes).
                         La moyenne est calculée sur TOUS les services VMCV du jour
                         (pas seulement ceux dans la fenêtre attente), ce qui reflète
                         la vitesse commerciale structurelle de la ligne.
                         NaN si aucun VMCV ce jour-là sur le tronçon alternatif.
    delta_frequence_h  : (nb VMCV dans ±30min) − (nb R35 dans ±30min, train courant inclus).
                         L'inclusion du train courant reflète la perception du voyageur
                         de la densité de service totale sur le tronçon.
                         NaN si aucun VMCV dans la fenêtre de fréquence.
    """
    # Merge R35 with mapping to get VMCV alternatives
    r35_with_map = r35_troncons.merge(
        mapping[["gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
                 "bpuic_vmcv_dep", "bpuic_vmcv_arr"]].drop_duplicates(),
        on=["gare_depart_bpuic", "gare_arrivee_bpuic", "sens"],
        how="left",
    )

    # Rows with no VMCV alternative: bpuic_vmcv_dep is NaN → handled by left join
    r35_has_vmcv = r35_with_map.dropna(subset=["bpuic_vmcv_dep"])
    r35_has_vmcv = r35_has_vmcv.copy()
    r35_has_vmcv["bpuic_vmcv_dep"] = r35_has_vmcv["bpuic_vmcv_dep"].astype(int)
    r35_has_vmcv["bpuic_vmcv_arr"] = r35_has_vmcv["bpuic_vmcv_arr"].astype(int)

    # Join with VMCV tronçons
    r35_vmcv = r35_has_vmcv.merge(
        vmcv_troncons[["date", "bpuic_vmcv_dep", "bpuic_vmcv_arr",
                       "h_dep_vmcv", "trajet_vmcv_min"]],
        on=["date", "bpuic_vmcv_dep", "bpuic_vmcv_arr"],
        how="left",
    )

    # --- delta_attente : window [h_dep_r35 - AMONT, h_dep_r35 + AVAL] ---
    r35_vmcv["h_window_start"] = r35_vmcv["h_dep_r35"] - pd.Timedelta(minutes=FENETRE_ATTENTE_AMONT_MIN)
    r35_vmcv["h_window_end"] = r35_vmcv["h_dep_r35"] + pd.Timedelta(minutes=FENETRE_ATTENTE_AVAL_MIN)
    in_attente_window = (
        r35_vmcv["h_dep_vmcv"].notna()
        & (r35_vmcv["h_dep_vmcv"] >= r35_vmcv["h_window_start"])
        & (r35_vmcv["h_dep_vmcv"] <= r35_vmcv["h_window_end"])
    )
    vmcv_att = r35_vmcv[in_attente_window].copy()
    # delta_attente = h_dep_r35 - h_dep_vmcv (positive → VMCV comes before R35)
    vmcv_att["_delta_att"] = (
        (vmcv_att["h_dep_r35"] - vmcv_att["h_dep_vmcv"]).dt.total_seconds() / 60
    )
    # Take best VMCV (maximum delta = minimum wait)
    agg_att = vmcv_att.groupby(GRAIN, as_index=False).agg(
        vmcv_delta_attente_min=("_delta_att", "max"),
    )

    # --- delta_trajet : daily average VMCV travel time (structural, not window-dependent) ---
    # Using all VMCV services of the day captures the structural speed of the line
    # (commercial speed, road constraints), which does not vary within a 30-minute
    # window around a specific R35 train.
    trajet_vmcv_jour = (
        vmcv_troncons
        .groupby(["date", "bpuic_vmcv_dep", "bpuic_vmcv_arr"], as_index=False)
        .agg(_trajet_vmcv_moy_jour=("trajet_vmcv_min", "mean"))
    )
    r35_traj = r35_has_vmcv.merge(
        trajet_vmcv_jour,
        on=["date", "bpuic_vmcv_dep", "bpuic_vmcv_arr"],
        how="left",
    )
    agg_traj = r35_traj.groupby(GRAIN, as_index=False).agg(
        _trajet_vmcv_moy=("_trajet_vmcv_moy_jour", "mean"),
    )

    # --- delta_frequence : ±30min window ---
    r35_vmcv["h_freq_start"] = r35_vmcv["h_dep_r35"] - pd.Timedelta(minutes=FENETRE_FREQUENCE_MIN)
    r35_vmcv["h_freq_end"] = r35_vmcv["h_dep_r35"] + pd.Timedelta(minutes=FENETRE_FREQUENCE_MIN)
    in_freq_window = (
        r35_vmcv["h_dep_vmcv"].notna()
        & (r35_vmcv["h_dep_vmcv"] >= r35_vmcv["h_freq_start"])
        & (r35_vmcv["h_dep_vmcv"] <= r35_vmcv["h_freq_end"])
    )
    agg_vmcv_freq = r35_vmcv[in_freq_window].groupby(GRAIN, as_index=False).agg(
        _vmcv_freq_count=("h_dep_vmcv", "count"),
    )

    # R35 frequency: the current train is included in its own count (self-join) because
    # the passenger perceives the overall density of R35 service on the tronçon, not
    # just the "other" trains. For a solo train with 1 VMCV, delta_freq = 1 − 1 = 0.
    r35_freq_self = r35_troncons.merge(
        r35_troncons[GRAIN + ["h_dep_r35"]].rename(columns={
            "numero_train": "_train_other",
            "h_dep_r35": "_h_dep_other",
        }),
        on=["date", "gare_depart_bpuic", "gare_arrivee_bpuic", "sens"],
    )
    r35_freq_self = r35_freq_self[
        (r35_freq_self["h_dep_r35"] - r35_freq_self["_h_dep_other"]).dt.total_seconds().abs() / 60
        <= FENETRE_FREQUENCE_MIN
    ]
    agg_r35_freq = r35_freq_self.groupby(GRAIN, as_index=False).agg(
        _r35_freq_count=("_train_other", "nunique"),
    )

    # --- Assemble results ---
    result = r35_troncons[GRAIN + ["trajet_r35_min"]].copy()

    result = result.merge(agg_att, on=GRAIN, how="left")
    result = result.merge(agg_traj, on=GRAIN, how="left")
    result = result.merge(agg_vmcv_freq, on=GRAIN, how="left")
    result = result.merge(agg_r35_freq, on=GRAIN, how="left")

    # delta_trajet
    result["vmcv_delta_trajet_min"] = (
        result["trajet_r35_min"] - result["_trajet_vmcv_moy"]
    )

    # delta_frequence: freq_VMCV - freq_R35 (per hour, window = 60min)
    # NaN if no VMCV in the frequency window
    result["vmcv_delta_frequence_h"] = np.where(
        result["_vmcv_freq_count"].notna() & (result["_vmcv_freq_count"] > 0),
        result["_vmcv_freq_count"] - result["_r35_freq_count"],
        np.nan,
    )

    cols_finales = GRAIN + [
        "vmcv_delta_attente_min",
        "vmcv_delta_trajet_min",
        "vmcv_delta_frequence_h",
    ]
    return result[cols_finales].copy()


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def main() -> None:
    # -------------------------------------------------------------------------
    # Étape 1 : Mapping statique tronçon R35 → arrêts VMCV alternatifs
    # -------------------------------------------------------------------------
    log.info("Chargement des gares R35 ...")
    gares_r35 = pd.read_parquet(
        DIM_GARE,
        columns=["bpuic", "abreviation", "nom", "km", "wgs84East", "wgs84North"],
    )
    log.info("  %d gares R35", len(gares_r35))

    log.info("Chargement des lignes VMCV actives ...")
    lignes_actives_df = pd.read_parquet(DIM_VMCV_CONCURRENTES)
    lignes_actives: frozenset[str] = frozenset(
        lignes_actives_df.loc[lignes_actives_df["is_concurrent_actif"], "linien_text"]
    )
    log.info("  %d lignes VMCV actives : %s", len(lignes_actives), sorted(lignes_actives))

    log.info("Extraction des arrêts VMCV actifs depuis un fichier ISTDATEN récent ...")
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    stops_vmcv_raw: list[pd.DataFrame] = []
    for fich in fichiers[-3:]:   # 3 derniers mois suffisent pour le mapping statique
        _kw = dict(sep=";", usecols=["BETREIBER_ABK", "LINIEN_TEXT", "BPUIC"],
                   dtype={"BETREIBER_ABK": str, "LINIEN_TEXT": str, "BPUIC": "Int64"},
                   low_memory=False)
        try:
            df_s = pd.read_csv(fich, encoding="utf-8-sig", **_kw)
        except UnicodeDecodeError:
            df_s = pd.read_csv(fich, encoding="latin-1", **_kw)
        vmcv_s = df_s[
            (df_s["BETREIBER_ABK"] == "VMCV")
            & df_s["LINIEN_TEXT"].isin(lignes_actives)
        ][["LINIEN_TEXT", "BPUIC"]].drop_duplicates()
        stops_vmcv_raw.append(vmcv_s)

    stops_vmcv = (
        pd.concat(stops_vmcv_raw, ignore_index=True)
        .drop_duplicates()
        .rename(columns={"LINIEN_TEXT": "linien_text", "BPUIC": "bpuic"})
    )
    log.info("  %d arrêts VMCV uniques (lignes actives)", len(stops_vmcv))

    log.info("Géocodage des arrêts VMCV ...")
    stops_vmcv_geo = _geocoder_arrets_vmcv(stops_vmcv, FULL_WORLD_TRAFFIC_POINT)
    n_sans_geo = stops_vmcv_geo["lon"].isna().sum()
    if n_sans_geo > 0:
        log.warning("%d arrêts VMCV sans coordonnées dans le référentiel.", n_sans_geo)

    log.info("Identification des arrêts VMCV proches des gares R35 (rayon = %dm) ...", RAYON_PROXIMITE_M)
    arrets_proches = _identifier_arrets_vmcv_proches(
        gares_r35, stops_vmcv_geo, lignes_actives, RAYON_PROXIMITE_M
    )
    log.info("  %d paires (gare_r35, arrêt_vmcv, ligne) dans le rayon", len(arrets_proches))

    mapping = _construire_mapping_troncons(gares_r35, arrets_proches)
    log.info("  %d combinaisons tronçon-R35 → alternative-VMCV", len(mapping))

    if mapping.empty:
        log.warning("Aucune alternative VMCV trouvée. Output = 0 features non-NaN.")

    bpuics_dep = frozenset(mapping["bpuic_vmcv_dep"].dropna().astype(int))
    bpuics_arr = frozenset(mapping["bpuic_vmcv_arr"].dropna().astype(int))
    bpuics_pertinents = bpuics_dep | bpuics_arr
    log.info("  %d BPUICs VMCV pertinents à extraire", len(bpuics_pertinents))

    # -------------------------------------------------------------------------
    # Étape 2 : Lecture des passages VMCV (tous les CSV ISTDATEN)
    # -------------------------------------------------------------------------
    log.info("Lecture des passages VMCV sur les BPUICs pertinents (tous les CSV ISTDATEN) ...")
    passages_vmcv = _lire_passages_vmcv(bpuics_pertinents)
    log.info("  %d passages VMCV pertinents extraits", len(passages_vmcv))

    # -------------------------------------------------------------------------
    # Étape 3 : Reconstruction des tronçons VMCV
    # -------------------------------------------------------------------------
    log.info("Reconstruction des tronçons VMCV ...")
    vmcv_troncons = _reconstruire_troncons_vmcv(passages_vmcv, mapping)
    log.info("  %d tronçons VMCV reconstruits (date × ligne × fahrt × dep → arr)", len(vmcv_troncons))

    # -------------------------------------------------------------------------
    # Étape 4 : Horaires R35 au grain tronçon
    # -------------------------------------------------------------------------
    log.info("Construction des horaires R35 au grain tronçon ...")
    r35_troncons = _charger_horaires_r35_troncons(gares_r35)
    log.info("  %d tronçons R35 (date × train × gare_dep × gare_arr)", len(r35_troncons))

    # -------------------------------------------------------------------------
    # Étape 5 : Calcul des deltas
    # -------------------------------------------------------------------------
    log.info("Calcul des trois features delta VMCV ...")
    df_out = _calculer_deltas(r35_troncons, vmcv_troncons, mapping)
    log.info("  Output : %d lignes × %d colonnes", df_out.shape[0], df_out.shape[1])

    for col in ["vmcv_delta_attente_min", "vmcv_delta_trajet_min", "vmcv_delta_frequence_h"]:
        n_non_nan = df_out[col].notna().sum()
        log.info("  Couverture %s : %d / %d (%.1f%%)", col, n_non_nan, len(df_out),
                 100 * n_non_nan / len(df_out) if len(df_out) > 0 else 0)

    # Validation des bornes
    att = df_out["vmcv_delta_attente_min"].dropna()
    if not att.empty:
        hors_bornes = att[~att.between(-FENETRE_ATTENTE_AVAL_MIN, FENETRE_ATTENTE_AMONT_MIN + 1)]
        assert hors_bornes.empty, (
            f"delta_attente hors bornes [{-FENETRE_ATTENTE_AVAL_MIN}, {FENETRE_ATTENTE_AMONT_MIN + 1}] : "
            f"{len(hors_bornes)} valeurs problématiques, "
            f"exemples : {hors_bornes.head().tolist()}"
        )

    # -------------------------------------------------------------------------
    # Écriture atomique
    # -------------------------------------------------------------------------
    DIM_VMCV_PAR_TRONCON.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_VMCV_PAR_TRONCON.with_suffix(".tmp.parquet")
    try:
        df_out.to_parquet(tmp, index=False)
        tmp.rename(DIM_VMCV_PAR_TRONCON)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", DIM_VMCV_PAR_TRONCON)
    log.info("  Période : %s → %s",
             str(df_out["date"].min())[:10], str(df_out["date"].max())[:10])


if __name__ == "__main__":
    main()
