"""
build_dim_vmcv_par_train_jour.py
=================================
Construit dim_vmcv_par_train_jour.parquet — features de concurrence modale VMCV
au grain (date, numero_train, sens), selon la logique « décision à l'embarquement »
(ADR-021).

Design
------
Pour chaque train R35 qui part d'une gare donnée un jour donné, on évalue si un
passager souhaitant aller dans la même direction générale dispose d'une alternative
VMCV pertinente à moins de 200 m.

Test directionnel (D2 de l'ADR-021) :
  sens "VV -> PLEI" : la ligne VMCV doit avoir au moins un arrêt à ≤ 200 m d'une
                      gare R35 du haut (km ≥ 5.5).
  sens "PLEI -> VV" : idem avec gare R35 du bas (km ≤ 4.0).

4 features produites :
  vmcv_n_lignes_concurrentes  — nb de lignes VMCV distinctes pertinentes (statique)
  vmcv_min_attente_min        — attente minimale (min) avant le prochain VMCV dans
                                [h_dep_r35 − 5min, h_dep_r35 + 30min], NaN si aucun
  vmcv_delta_attente_min      — 5 − vmcv_min_attente_min (positif = VMCV avantageux)
  vmcv_delta_frequence_h      — nb VMCV dans ±30min − nb R35 dans ±30min (train
                                courant inclus), NaN si 0 VMCV dans la fenêtre

Inputs
------
  data/processed/sources/istdaten_clean.parquet
  data/dimension/dim_gare.parquet
  data/dimension/dim_vmcv_lignes_concurrentes.parquet
  data/dimension/full-world-traffic-point.csv
  data/external/istdaten/istdaten_*.csv  (les 84 fichiers bruts)

Output
------
  data/processed/sources/dim_vmcv_par_train_jour.parquet
"""

from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    DIM_GARE,
    DIM_VMCV_CONCURRENTES,
    DIM_VMCV_PAR_TRAIN_JOUR,
    ISTDATEN_CLEAN,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes — exposées pour les tests
# ---------------------------------------------------------------------------

KM_SEUIL_BAS: float = 4.0   # km ≤ 4.0 → gare « bas de ligne »
KM_SEUIL_HAUT: float = 5.5  # km ≥ 5.5 → gare « haut de ligne »
RAYON_PROXIMITE_M: int = 200
FENETRE_ATTENTE_AMONT_MIN: int = 5
FENETRE_ATTENTE_AVAL_MIN: int = 30
FENETRE_FREQUENCE_MIN: int = 30

GRAIN = ["date", "numero_train", "sens"]

STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

ISTDATEN_DIR = Path("data/external/istdaten")
FULL_WORLD_TRAFFIC_POINT = Path("data/dimension/full-world-traffic-point.csv")


# ---------------------------------------------------------------------------
# Étape 1a — Géocodage et proximité géographique
# ---------------------------------------------------------------------------


def _haversine_vec(
    lon_ref: float,
    lat_ref: float,
    lons: pd.Series,
    lats: pd.Series,
) -> pd.Series:
    """Distance haversine (mètres) entre un point de référence et un vecteur de points."""
    R = 6_371_000
    φ1 = math.radians(lat_ref)
    φ2 = np.radians(lats.values)
    Δφ = φ2 - φ1
    Δλ = np.radians(lons.values - lon_ref)
    a = np.sin(Δφ / 2) ** 2 + math.cos(φ1) * np.cos(φ2) * np.sin(Δλ / 2) ** 2
    return pd.Series(R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)), index=lons.index)


def _geocoder_arrets_vmcv(
    stops_vmcv: pd.DataFrame,
    fwtp_path: Path = FULL_WORLD_TRAFFIC_POINT,
) -> pd.DataFrame:
    """Ajoute les coordonnées WGS84 aux arrêts VMCV depuis le référentiel FWTP."""
    fwtp = pd.read_csv(fwtp_path, sep=";", dtype=str,
                       usecols=["number", "wgs84East", "wgs84North"])
    fwtp["bpuic"] = pd.to_numeric(fwtp["number"], errors="coerce")
    fwtp["lon"] = pd.to_numeric(fwtp["wgs84East"], errors="coerce")
    fwtp["lat"] = pd.to_numeric(fwtp["wgs84North"], errors="coerce")
    fwtp = fwtp[["bpuic", "lon", "lat"]].dropna(subset=["bpuic"]).drop_duplicates("bpuic")
    return stops_vmcv.merge(fwtp, on="bpuic", how="left")


def _identifier_arrets_vmcv_proches(
    gares_r35: pd.DataFrame,
    stops_vmcv_geo: pd.DataFrame,
    lignes_actives: frozenset[str],
    rayon_m: int = RAYON_PROXIMITE_M,
) -> pd.DataFrame:
    """
    Identifie les arrêts VMCV à ≤ rayon_m de chaque gare R35.

    Retourne: (gare_r35_bpuic, gare_r35_km, bpuic_vmcv, linien_text)
    """
    valides = stops_vmcv_geo.dropna(subset=["lon", "lat"])
    valides = valides[valides["linien_text"].isin(lignes_actives)]

    rows: list[dict] = []
    for _, gare in gares_r35.iterrows():
        dist = _haversine_vec(
            gare["wgs84East"], gare["wgs84North"],
            valides["lon"], valides["lat"],
        )
        proches = valides[dist <= rayon_m]
        for _, stop in proches.iterrows():
            rows.append({
                "gare_r35_bpuic": int(gare["bpuic"]),
                "gare_r35_km":    float(gare["km"]),
                "bpuic_vmcv":     int(stop["bpuic"]),
                "linien_text":    str(stop["linien_text"]),
            })

    if not rows:
        return pd.DataFrame(columns=["gare_r35_bpuic", "gare_r35_km",
                                     "bpuic_vmcv", "linien_text"])
    return pd.DataFrame(rows).drop_duplicates()


# ---------------------------------------------------------------------------
# Étape 1b — Mapping directionnel statique
# ---------------------------------------------------------------------------


def _construire_mapping_directionnel(
    arrets_proches: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construit le mapping (gare_r35_bpuic, sens) → (bpuic_vmcv, linien_text).

    Test directionnel :
      sens "VV -> PLEI" : la ligne VMCV doit avoir un arrêt près d'une gare
                          haut (km ≥ KM_SEUIL_HAUT).
      sens "PLEI -> VV" : idem avec gare bas (km ≤ KM_SEUIL_BAS).

    Une ligne qui atteint à la fois le bas et le haut est valide dans les deux
    sens (cas d'un bus Vevey–Blonay).
    """
    if arrets_proches.empty:
        return pd.DataFrame(
            columns=["gare_r35_bpuic", "sens", "bpuic_vmcv", "linien_text"]
        )

    lines_near_haut: set[str] = set(
        arrets_proches.loc[
            arrets_proches["gare_r35_km"] >= KM_SEUIL_HAUT, "linien_text"
        ]
    )
    lines_near_bas: set[str] = set(
        arrets_proches.loc[
            arrets_proches["gare_r35_km"] <= KM_SEUIL_BAS, "linien_text"
        ]
    )

    rows: list[dict] = []
    for _, row in arrets_proches.iterrows():
        lt = row["linien_text"]
        base = {"gare_r35_bpuic": row["gare_r35_bpuic"], "bpuic_vmcv": row["bpuic_vmcv"],
                "linien_text": lt}
        if lt in lines_near_haut:
            rows.append({**base, "sens": "VV -> PLEI"})
        if lt in lines_near_bas:
            rows.append({**base, "sens": "PLEI -> VV"})

    if not rows:
        return pd.DataFrame(
            columns=["gare_r35_bpuic", "sens", "bpuic_vmcv", "linien_text"]
        )
    return pd.DataFrame(rows).drop_duplicates()


# ---------------------------------------------------------------------------
# Étape 2 — Lecture des passages VMCV (tous les CSV ISTDATEN)
# ---------------------------------------------------------------------------


def _lire_passages_vmcv(bpuics_pertinents: frozenset[int]) -> pd.DataFrame:
    """Lit tous les CSV ISTDATEN et extrait les passages VMCV aux BPUICs pertinents."""
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")

    cols_utiles = [
        "BETRIEBSTAG", "BETREIBER_ABK", "LINIEN_TEXT", "BPUIC",
        "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS",
        "FAELLT_AUS_TF", "DURCHFAHRT_TF",
    ]
    dtype_map = {
        "BETREIBER_ABK": str, "LINIEN_TEXT": str,
        "BPUIC": "Int64", "AB_PROGNOSE_STATUS": str,
        "FAELLT_AUS_TF": str, "DURCHFAHRT_TF": str,
    }

    fragments: list[pd.DataFrame] = []
    n_total = len(fichiers)

    for i, fich in enumerate(fichiers, 1):
        kw = dict(sep=";", usecols=cols_utiles, dtype=dtype_map, low_memory=False)
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **kw)
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **kw)
            log.warning("Encodage latin-1 pour %s", fich.name)

        masque = (
            (df["BETREIBER_ABK"] == "VMCV")
            & (df["FAELLT_AUS_TF"].str.lower() != "true")
            & (df["DURCHFAHRT_TF"].str.lower() != "true")
            & df["BPUIC"].isin(bpuics_pertinents)
        )
        df_v = df.loc[masque].copy()
        if df_v.empty:
            log.info("[%02d/%02d] %s : 0 passages VMCV", i, n_total, fich.name)
            continue

        df_v["date"] = pd.to_datetime(df_v["BETRIEBSTAG"], format="%d.%m.%Y", errors="coerce")
        df_v["horaire_dep"] = pd.to_datetime(df_v["ABFAHRTSZEIT"],
                                              format="%d.%m.%Y %H:%M", errors="coerce")
        df_v["reel_dep"] = pd.to_datetime(df_v["AB_PROGNOSE"],
                                           format="%d.%m.%Y %H:%M:%S", errors="coerce")
        statut_ok = df_v["AB_PROGNOSE_STATUS"].isin(STATUTS_REELS)
        df_v["h_dep_vmcv"] = df_v["reel_dep"].where(statut_ok, df_v["horaire_dep"])

        fragments.append(
            df_v[["date", "LINIEN_TEXT", "BPUIC", "h_dep_vmcv"]]
            .rename(columns={"LINIEN_TEXT": "linien_text", "BPUIC": "bpuic_vmcv"})
        )
        log.info("[%02d/%02d] %s : %d passages VMCV", i, n_total, fich.name, len(df_v))

    if not fragments:
        log.warning("Aucun passage VMCV trouvé pour les BPUICs pertinents.")
        return pd.DataFrame(columns=["date", "linien_text", "bpuic_vmcv", "h_dep_vmcv"])

    return pd.concat(fragments, ignore_index=True)


# ---------------------------------------------------------------------------
# Étape 3 — Horaires R35 au grain (date, numero_train, sens)
# ---------------------------------------------------------------------------


def _charger_departures_r35_train_jour(gares_r35: pd.DataFrame) -> pd.DataFrame:
    """
    Produit un DataFrame (date, numero_train, sens, gare_dep_r35_bpuic, h_dep_r35).

    Pour chaque (date, train, sens), identifie l'arrêt de départ effectif =
    le premier arrêt non annulé dans le sens du voyage.
    """
    df = pd.read_parquet(ISTDATEN_CLEAN)
    df["date"] = pd.to_datetime(df["date"])
    km_map = dict(zip(gares_r35["bpuic"], gares_r35["km"]))

    df = df[df["bpuic"].isin(km_map) & ~df["is_annule"]].copy()
    df["km"] = df["bpuic"].map(km_map)

    dep_ok = df["statut_depart"].isin(STATUTS_REELS)
    df["h_dep_eff"] = df["reel_depart"].where(dep_ok, df["horaire_depart"])
    df["h_dep_eff"] = pd.to_datetime(df["h_dep_eff"])

    # Sort pour obtenir les arrêts consécutifs
    df = df.sort_values(["date", "numero_train", "h_dep_eff"]).reset_index(drop=True)
    df["km_next"] = df.groupby(["date", "numero_train"])["km"].shift(-1)

    # Sens déterminé uniquement pour les arrêts avec successeur
    df_troncon = df.dropna(subset=["km_next"]).copy()
    df_troncon["sens"] = np.where(
        df_troncon["km"] < df_troncon["km_next"], "VV -> PLEI", "PLEI -> VV"
    )

    # Premier arrêt (min h_dep_eff) par (date, train, sens)
    idx_first = df_troncon.groupby(["date", "numero_train", "sens"])["h_dep_eff"].idxmin()
    first_dep = df_troncon.loc[idx_first].copy()

    return first_dep.rename(columns={
        "bpuic":   "gare_dep_r35_bpuic",
        "h_dep_eff": "h_dep_r35",
    })[["date", "numero_train", "sens", "gare_dep_r35_bpuic", "h_dep_r35"]]


# ---------------------------------------------------------------------------
# Étape 4 — Calcul des 4 features
# ---------------------------------------------------------------------------


def _calculer_features(
    r35_trains: pd.DataFrame,
    vmcv_passages: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcule les 4 features de concurrence VMCV au grain (date, numero_train, sens).

    Fenêtres temporelles :
      vmcv_min_attente_min    : [h_dep_r35 − AMONT_MIN, h_dep_r35 + AVAL_MIN]
      vmcv_delta_attente_min  : 5 − min_attente  (positif = VMCV avantageux)
      vmcv_delta_frequence_h  : ±FREQUENCE_MIN autour de h_dep_r35
                                NaN si 0 VMCV dans la fenêtre
      vmcv_n_lignes_concurrentes : statique, depuis le mapping
    """
    # --- Feature statique : nb de lignes VMCV pertinentes par (gare, sens) ---
    n_lignes = (
        mapping
        .groupby(["gare_r35_bpuic", "sens"])["linien_text"]
        .nunique()
        .reset_index()
        .rename(columns={
            "linien_text":   "vmcv_n_lignes_concurrentes",
            "gare_r35_bpuic": "gare_dep_r35_bpuic",
        })
    )

    # --- Jointure R35 × mapping pour obtenir les BPUICs VMCV pertinents ---
    r35_with_map = r35_trains.merge(
        mapping[["gare_r35_bpuic", "sens", "bpuic_vmcv"]].rename(
            columns={"gare_r35_bpuic": "gare_dep_r35_bpuic"}
        ).drop_duplicates(),
        on=["gare_dep_r35_bpuic", "sens"],
        how="left",
    )
    r35_has_vmcv = r35_with_map.dropna(subset=["bpuic_vmcv"]).copy()
    r35_has_vmcv["bpuic_vmcv"] = r35_has_vmcv["bpuic_vmcv"].astype(int)

    # --- Jointure avec les passages VMCV ---
    r35_vmcv = r35_has_vmcv.merge(
        vmcv_passages[["date", "bpuic_vmcv", "h_dep_vmcv"]],
        on=["date", "bpuic_vmcv"],
        how="left",
    )

    # --- delta_attente : fenêtre [h_dep_r35 − AMONT, h_dep_r35 + AVAL] ---
    r35_vmcv["_h_win_start"] = r35_vmcv["h_dep_r35"] - pd.Timedelta(minutes=FENETRE_ATTENTE_AMONT_MIN)
    r35_vmcv["_h_win_end"]   = r35_vmcv["h_dep_r35"] + pd.Timedelta(minutes=FENETRE_ATTENTE_AVAL_MIN)
    in_att = (
        r35_vmcv["h_dep_vmcv"].notna()
        & (r35_vmcv["h_dep_vmcv"] >= r35_vmcv["_h_win_start"])
        & (r35_vmcv["h_dep_vmcv"] <= r35_vmcv["_h_win_end"])
    )
    vmcv_att = r35_vmcv[in_att].copy()
    # min_attente = (h_dep_vmcv − (h_dep_r35 − 5min)) en minutes
    vmcv_att["_attente"] = (
        (vmcv_att["h_dep_vmcv"] - vmcv_att["_h_win_start"]).dt.total_seconds() / 60
    )
    agg_att = vmcv_att.groupby(GRAIN, as_index=False).agg(
        vmcv_min_attente_min=("_attente", "min"),
    )
    agg_att["vmcv_delta_attente_min"] = 5.0 - agg_att["vmcv_min_attente_min"]

    # --- delta_frequence : fenêtre ±FREQUENCE_MIN ---
    r35_vmcv["_h_freq_start"] = r35_vmcv["h_dep_r35"] - pd.Timedelta(minutes=FENETRE_FREQUENCE_MIN)
    r35_vmcv["_h_freq_end"]   = r35_vmcv["h_dep_r35"] + pd.Timedelta(minutes=FENETRE_FREQUENCE_MIN)
    in_freq = (
        r35_vmcv["h_dep_vmcv"].notna()
        & (r35_vmcv["h_dep_vmcv"] >= r35_vmcv["_h_freq_start"])
        & (r35_vmcv["h_dep_vmcv"] <= r35_vmcv["_h_freq_end"])
    )
    agg_vmcv_freq = (
        r35_vmcv[in_freq]
        .groupby(GRAIN, as_index=False)
        .agg(_vmcv_freq=("h_dep_vmcv", "count"))
    )

    # R35 frequency : trains au même (date, gare_dep, sens) dans ±30min (self-join)
    r35_freq_self = r35_trains.merge(
        r35_trains[GRAIN + ["gare_dep_r35_bpuic", "h_dep_r35"]].rename(
            columns={"numero_train": "_other_train", "h_dep_r35": "_other_h_dep"}
        ),
        on=["date", "gare_dep_r35_bpuic", "sens"],
        how="left",
    )
    in_r35_freq = (
        (r35_freq_self["_other_h_dep"] - r35_freq_self["h_dep_r35"])
        .dt.total_seconds().abs() / 60
        <= FENETRE_FREQUENCE_MIN
    )
    agg_r35_freq = (
        r35_freq_self[in_r35_freq]
        .groupby(GRAIN, as_index=False)
        .agg(_r35_freq=("_other_train", "nunique"))
    )

    # --- Assemblage ---
    result = (
        r35_trains
        .merge(n_lignes, on=["gare_dep_r35_bpuic", "sens"], how="left")
        .merge(agg_att[GRAIN + ["vmcv_min_attente_min", "vmcv_delta_attente_min"]],
               on=GRAIN, how="left")
        .merge(agg_vmcv_freq[GRAIN + ["_vmcv_freq"]], on=GRAIN, how="left")
        .merge(agg_r35_freq[GRAIN + ["_r35_freq"]], on=GRAIN, how="left")
    )

    result["vmcv_n_lignes_concurrentes"] = result["vmcv_n_lignes_concurrentes"].fillna(0).astype(int)
    # delta_frequence = NaN si 0 VMCV dans la fenêtre
    result["vmcv_delta_frequence_h"] = np.where(
        result["_vmcv_freq"].notna() & (result["_vmcv_freq"] > 0),
        result["_vmcv_freq"] - result["_r35_freq"],
        np.nan,
    )

    return result[GRAIN + [
        "vmcv_n_lignes_concurrentes",
        "vmcv_min_attente_min",
        "vmcv_delta_attente_min",
        "vmcv_delta_frequence_h",
    ]]


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def main() -> None:
    # -------------------------------------------------------------------------
    # Étape 1 : Mapping statique directionnel
    # -------------------------------------------------------------------------
    log.info("Chargement des gares R35 ...")
    gares_r35 = pd.read_parquet(DIM_GARE)
    log.info("  %d gares R35", len(gares_r35))

    log.info("Chargement des lignes VMCV actives ...")
    lig_conc = pd.read_parquet(DIM_VMCV_CONCURRENTES)
    lignes_actives: frozenset[str] = frozenset(lig_conc["linien_text"].dropna().unique())
    log.info("  %d lignes actives : %s", len(lignes_actives), sorted(lignes_actives))

    log.info("Extraction des arrêts VMCV depuis un fichier ISTDATEN récent ...")
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")
    df_recent = pd.read_csv(
        fichiers[-1], sep=";", usecols=["LINIEN_TEXT", "BPUIC"],
        dtype=str, low_memory=False,
    )
    stops_raw = (
        df_recent[df_recent["LINIEN_TEXT"].isin(lignes_actives)][["LINIEN_TEXT", "BPUIC"]]
        .drop_duplicates()
        .rename(columns={"LINIEN_TEXT": "linien_text", "BPUIC": "bpuic"})
    )
    stops_raw["bpuic"] = pd.to_numeric(stops_raw["bpuic"], errors="coerce").astype("Int64")
    stops_raw = stops_raw.dropna(subset=["bpuic"])
    stops_raw["bpuic"] = stops_raw["bpuic"].astype(int)
    log.info("  %d arrêts VMCV uniques extraits", len(stops_raw))

    log.info("Géocodage des arrêts VMCV ...")
    stops_vmcv_geo = _geocoder_arrets_vmcv(stops_raw, FULL_WORLD_TRAFFIC_POINT)
    n_sans_geo = stops_vmcv_geo["lon"].isna().sum()
    if n_sans_geo > 0:
        log.warning("  %d arrêts VMCV sans coordonnées.", n_sans_geo)

    log.info("Identification des arrêts VMCV proches des gares R35 (rayon = %d m) ...",
             RAYON_PROXIMITE_M)
    arrets_proches = _identifier_arrets_vmcv_proches(
        gares_r35, stops_vmcv_geo, lignes_actives, RAYON_PROXIMITE_M
    )
    log.info("  %d paires (gare_r35, arrêt_vmcv, ligne) dans le rayon", len(arrets_proches))

    log.info("Construction du mapping directionnel ...")
    mapping = _construire_mapping_directionnel(arrets_proches)
    log.info("  %d combinaisons (gare_r35, sens, arrêt_vmcv, ligne)", len(mapping))

    n_gares_couvertes = mapping["gare_r35_bpuic"].nunique()
    log.info("  %d gares R35 avec au moins 1 ligne VMCV concurrente", n_gares_couvertes)

    # Stop condition : < 3 gares couvertes
    if n_gares_couvertes < 3:
        log.error(
            "STOP : seulement %d gare(s) R35 avec concurrence VMCV (< 3). "
            "Vérifier le mapping et les seuils km.",
            n_gares_couvertes,
        )
        sys.exit(1)

    if mapping.empty:
        log.warning("Aucune alternative VMCV trouvée. Output = 0 features non-NaN.")

    bpuics_pertinents: frozenset[int] = frozenset(
        mapping["bpuic_vmcv"].dropna().astype(int)
    )
    log.info("  %d BPUICs VMCV pertinents", len(bpuics_pertinents))

    # -------------------------------------------------------------------------
    # Étape 2 : Passages VMCV
    # -------------------------------------------------------------------------
    log.info("Lecture des passages VMCV (tous les CSV ISTDATEN) ...")
    vmcv_passages = _lire_passages_vmcv(bpuics_pertinents)
    log.info("  %d passages VMCV extraits", len(vmcv_passages))

    # -------------------------------------------------------------------------
    # Étape 3 : Horaires R35 grain train × jour × sens
    # -------------------------------------------------------------------------
    log.info("Construction des horaires R35 au grain (date, train, sens) ...")
    r35_trains = _charger_departures_r35_train_jour(gares_r35)
    log.info("  %d combinaisons (date × train × sens)", len(r35_trains))

    # -------------------------------------------------------------------------
    # Étape 4 : Calcul des features
    # -------------------------------------------------------------------------
    log.info("Calcul des 4 features VMCV ...")
    df_out = _calculer_features(r35_trains, vmcv_passages, mapping)
    log.info("  Output : %d lignes × %d colonnes", df_out.shape[0], df_out.shape[1])

    for col in ["vmcv_n_lignes_concurrentes", "vmcv_min_attente_min",
                "vmcv_delta_attente_min", "vmcv_delta_frequence_h"]:
        n_non_nan = df_out[col].notna().sum() if col != "vmcv_n_lignes_concurrentes" \
            else (df_out[col] > 0).sum()
        label = "> 0" if col == "vmcv_n_lignes_concurrentes" else "non-NaN"
        log.info("  %s (%s) : %d / %d (%.1f%%)",
                 col, label, n_non_nan, len(df_out),
                 100 * n_non_nan / len(df_out) if len(df_out) > 0 else 0)

    # -------------------------------------------------------------------------
    # Étape 5 : Écriture atomique
    # -------------------------------------------------------------------------
    DIM_VMCV_PAR_TRAIN_JOUR.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_VMCV_PAR_TRAIN_JOUR.with_suffix(".tmp.parquet")
    try:
        df_out.to_parquet(tmp, index=False)
        tmp.rename(DIM_VMCV_PAR_TRAIN_JOUR)
        log.info("Écrit : %s", DIM_VMCV_PAR_TRAIN_JOUR)
        log.info("  Période : %s → %s",
                 df_out["date"].min().date(), df_out["date"].max().date())
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
