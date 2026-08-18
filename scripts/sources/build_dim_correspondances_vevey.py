"""
build_dim_correspondances_vevey.py
====================================
Calcule les correspondances Vevey CFF ↔ R35 par train, dans les deux sens.

Deux familles de features sont produites :
  - ``_in_``  : feeders CFF arrivant à Vevey AVANT le départ d'un R35 montant
                (train R35 partant de Vevey vers Les Pléiades)
  - ``_out_`` : CFF partant de Vevey APRÈS l'arrivée d'un R35 descendant
                (train R35 arrivant à Vevey depuis Les Pléiades)

Grain de sortie : date × numero_train
Les features sont NaN pour les trains qui ne passent pas par Vevey dans
le sens concerné. La propagation sur tous les tronçons du train est faite
lors de la jointure dans add_istdaten_to_raw_stacked.py.

Définitions théorique / garantie
----------------------------------
Correspondance **théorique** : les horaires officiels permettent physiquement
la correspondance (fenêtre basée sur ANKUNFTSZEIT/ABFAHRTSZEIT).

Correspondance **garantie** : les heures réelles confirment que la
correspondance a eu lieu (fenêtre basée sur AN_PROGNOSE/AB_PROGNOSE).
Fallback sur l'horaire si la donnée réelle est manquante.

Fenêtres de correspondance (validées)
----------------------------------------
  Sens _in_  : CFF arrive dans [départ_R35 - 5 min, départ_R35 - 1 min]
  Sens _out_ : CFF part   dans [arrivée_R35 + 1 min, arrivée_R35 + 5 min]

Garantie _in_  : arrivée effective CFF dans la fenêtre effective R35 (aucun seuil retard)
Garantie _out_ : départ effectif CFF dans la fenêtre effective R35

Logique J-2
-----------
Les rolling windows sont calculées avec lag=0 (aucun décalage dans le
rolling). La responsabilité du décalage J-2 est portée exclusivement par la
jointure dans add_istdaten_to_raw_stacked.py, qui lit la ligne ISTDATEN de
date=J-2 pour alimenter la prédiction du jour J. Le rolling à date=J-2
couvre donc les N occurrences du même type de jour se terminant à J-2 inclus.

Features produites (12 au total : 6 _in_ + 6 _out_)
-------------------------------------------------------
Pour sens ∈ {in, out} et fenêtre ∈ {5occ, 20occ} :
  ist_corresp_{sens}_n_theoriques_moy_{fenetre}
  ist_corresp_{sens}_n_garanties_moy_{fenetre}
  ist_corresp_{sens}_pct_garanties_{fenetre}

Inputs
------
  data/external/istdaten/istdaten_*.csv
  data/processed/sources/istdaten_clean.parquet
  data/dimension/dim_vacances_feries_vaud.parquet

Output
------
  data/processed/sources/dim_correspondances_vevey.parquet
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    DIM_CORRESPONDANCES_VEVEY,
    DIM_VACANCES_FERIES,
    ISTDATEN_CLEAN,
    ISTDATEN_DIR,
)
from _rolling_par_type_jour import rolling_par_type_jour

# Fenêtres de correspondance
FENETRE_IN_AMONT_MIN: int = 5    # CFF arrive au plus 5 min avant départ R35
FENETRE_IN_AVAL_MIN: int = 1     # CFF arrive au moins 1 min avant départ R35
FENETRE_OUT_AMONT_MIN: int = 1   # CFF part au moins 1 min après arrivée R35
FENETRE_OUT_AVAL_MIN: int = 5    # CFF part au plus 5 min après arrivée R35
SEUIL_RETARD_FEEDER_SEC: int = 300  # 5 min

BPUIC_VEVEY: int = 8501200
LINIEN_FEEDERS: frozenset[str] = frozenset(
    {"S3", "S4", "S7", "RE", "R3", "R4", "R7", "RE33", "IR90", "IR"}
)
STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

# Paramètres rolling (n_occurrences, min_periods, suffixe)
FENETRES: list[tuple[int, int, str]] = [
    (5,  2, "5occ"),
    (20, 5, "20occ"),
]
# lag=0 : la fenêtre inclut l'observation courante (date=J-2).
# Le décalage J-2 est géré exclusivement par la jointure dans
# add_istdaten_to_raw_stacked.py (base_date = date + 2 jours).
LAG_OPERATIONNEL: int = 0
TYPE_JOUR_COL: str = "cal_type_jour_3classes"
SERVICE_ID_COL: str = "ist_service_id"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilitaires communs
# ---------------------------------------------------------------------------


def _lire_kwargs() -> dict:
    # usecols : à partir d'oct. 2025, le format ISTDATEN a un 22ème champ SLOID.
    # On sélectionne explicitement les 21 colonnes du schéma historique.
    return dict(
        sep=";",
        low_memory=False,
        usecols=[
            "BETRIEBSTAG", "FAHRT_BEZEICHNER", "BETREIBER_ID", "BETREIBER_ABK",
            "BETREIBER_NAME", "PRODUKT_ID", "LINIEN_ID", "LINIEN_TEXT", "UMLAUF_ID",
            "VERKEHRSMITTEL_TEXT", "ZUSATZFAHRT_TF", "FAELLT_AUS_TF", "BPUIC",
            "HALTESTELLEN_NAME", "ANKUNFTSZEIT", "AN_PROGNOSE", "AN_PROGNOSE_STATUS",
            "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS", "DURCHFAHRT_TF",
        ],
        dtype={
            "LINIEN_TEXT": "category",
            "AN_PROGNOSE_STATUS": "category",
            "AB_PROGNOSE_STATUS": "category",
            "FAELLT_AUS_TF": str,
            "DURCHFAHRT_TF": str,
        },
    )


def _ajouter_service_id(df: pd.DataFrame) -> pd.DataFrame:
    """Construit ist_service_id depuis le premier départ théorique de chaque (date, train)."""
    premier_dep = (
        df.dropna(subset=["horaire_depart"])
        .groupby(["date", "numero_train"], as_index=False)["horaire_depart"]
        .min()
        .rename(columns={"horaire_depart": "_heure_origine"})
    )
    heure_str = premier_dep["_heure_origine"].dt.strftime("%Hh%M").fillna("NA")
    premier_dep[SERVICE_ID_COL] = (
        premier_dep["numero_train"].astype(str) + "_" + heure_str
    )
    return df.merge(
        premier_dep[["date", "numero_train", SERVICE_ID_COL]],
        on=["date", "numero_train"],
        how="left",
    )


def _ajouter_type_jour(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Joint dim_vacances_feries_vaud pour obtenir cal_type_jour_3classes."""
    feries = pd.read_parquet(
        DIM_VACANCES_FERIES, columns=["date", "is_ferie_vaud", "jour_semaine_iso"]
    )
    feries["date"] = pd.to_datetime(feries["date"])
    feries[TYPE_JOUR_COL] = np.where(
        feries["is_ferie_vaud"] | (feries["jour_semaine_iso"] == 7),
        "dimanche_ferie",
        np.where(feries["jour_semaine_iso"] == 6, "samedi", "ouvrable"),
    )
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    return df.merge(feries[["date", TYPE_JOUR_COL]], on=date_col, how="left")


# ---------------------------------------------------------------------------
# Sens ENTRANT (_in_) : CFF → R35 partant de Vevey
# ---------------------------------------------------------------------------


def _lire_arrivees_feeders_vevey() -> pd.DataFrame:
    """Lit toutes les arrivées de feeders CFF à Vevey (ANKUNFTSZEIT)."""
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")

    fragments: list[pd.DataFrame] = []
    for i, fich in enumerate(fichiers, 1):
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **_lire_kwargs())
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **_lire_kwargs())
            log.warning("Encodage latin-1 pour %s", fich.name)

        masque = (
            (df["BPUIC"] == BPUIC_VEVEY)
            & (df["LINIEN_TEXT"].isin(LINIEN_FEEDERS))
            & (df["DURCHFAHRT_TF"].str.lower() != "true")
            & (df["FAELLT_AUS_TF"].str.lower() != "true")
            & df["ANKUNFTSZEIT"].notna()
        )
        df_v = df.loc[masque, [
            "BETRIEBSTAG", "ANKUNFTSZEIT", "AN_PROGNOSE", "AN_PROGNOSE_STATUS",
        ]].copy()

        if df_v.empty:
            continue

        df_v["date"] = pd.to_datetime(df_v["BETRIEBSTAG"], format="%d.%m.%Y")
        df_v["horaire_arrivee_feeder"] = pd.to_datetime(
            df_v["ANKUNFTSZEIT"], format="%d.%m.%Y %H:%M", errors="coerce"
        )
        df_v["reel_arrivee_feeder"] = pd.to_datetime(
            df_v["AN_PROGNOSE"], format="%d.%m.%Y %H:%M:%S", errors="coerce"
        )
        statut_ok = df_v["AN_PROGNOSE_STATUS"].isin(STATUTS_REELS)
        df_v["retard_feeder_sec"] = (
            (df_v["reel_arrivee_feeder"] - df_v["horaire_arrivee_feeder"])
            .dt.total_seconds()
            .where(statut_ok)
        )
        fragments.append(df_v[["date", "horaire_arrivee_feeder", "reel_arrivee_feeder", "retard_feeder_sec"]])
        log.info("[%02d/%02d] %s : %d arrivées feeders", i, len(fichiers), fich.name, len(df_v))

    if not fragments:
        return pd.DataFrame(columns=["date", "horaire_arrivee_feeder", "reel_arrivee_feeder", "retard_feeder_sec"])
    return pd.concat(fragments, ignore_index=True)


def _r35_partant_vevey(df_fact: pd.DataFrame) -> pd.DataFrame:
    """Trains R35 partant de Vevey avec leur horaire et heure réelle de départ."""
    df = df_fact[
        (df_fact["bpuic"] == BPUIC_VEVEY) & df_fact["horaire_depart"].notna()
    ].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "numero_train", SERVICE_ID_COL, "horaire_depart", "reel_depart", "statut_depart"]].drop_duplicates()


def _calculer_correspondances_in(
    trains_vevey: pd.DataFrame,
    feeders: pd.DataFrame,
) -> pd.DataFrame:
    """Indicateurs de correspondance _in_ par (date, numero_train)."""
    cols_base = [
        "ist_corresp_in_n_theoriques_j",
        "ist_corresp_in_n_garanties_j",
        "ist_corresp_in_pct_garanties_j",
        "ist_corresp_in_retard_moy_j",
    ]

    full = trains_vevey[["date", "numero_train", SERVICE_ID_COL]].drop_duplicates().copy()
    if feeders.empty:
        for c in cols_base:
            full[c] = np.nan
        full["ist_corresp_in_n_theoriques_j"] = 0
        full["ist_corresp_in_n_garanties_j"] = 0
        return full

    merged = trains_vevey.merge(feeders, on="date", how="left")
    merged = merged[merged["horaire_arrivee_feeder"].notna()].copy()

    # Délai théorique (horaires officiels)
    merged["delai_theorique_min"] = (
        (merged["horaire_depart"] - merged["horaire_arrivee_feeder"])
        .dt.total_seconds() / 60
    )
    masque_theorique = (
        (merged["delai_theorique_min"] >= FENETRE_IN_AVAL_MIN)
        & (merged["delai_theorique_min"] <= FENETRE_IN_AMONT_MIN)
    )
    fenetre = merged[masque_theorique].copy()

    # Heure réelle de départ R35 (pour test effectif)
    statut_dep_reel = fenetre["statut_depart"].isin(STATUTS_REELS)
    fenetre["dep_effectif_r35"] = fenetre["reel_depart"].where(
        statut_dep_reel, fenetre["horaire_depart"]
    )
    # Arrivée effective du feeder
    fenetre["arr_effective_feeder"] = fenetre["reel_arrivee_feeder"].fillna(
        fenetre["horaire_arrivee_feeder"]
    )

    # Garantie : arrivée effective du feeder dans la fenêtre effective du R35
    fenetre["correspondance_garantie"] = (
        (fenetre["arr_effective_feeder"] <= fenetre["dep_effectif_r35"] - pd.Timedelta(minutes=FENETRE_IN_AVAL_MIN))
        & (fenetre["arr_effective_feeder"] >= fenetre["dep_effectif_r35"] - pd.Timedelta(minutes=FENETRE_IN_AMONT_MIN))
    )

    agg = fenetre.groupby(["date", "numero_train", SERVICE_ID_COL], as_index=False).agg(
        ist_corresp_in_n_theoriques_j=("delai_theorique_min", "count"),
        ist_corresp_in_n_garanties_j=("correspondance_garantie", "sum"),
        ist_corresp_in_retard_moy_j=("retard_feeder_sec", "mean"),
    )
    agg["ist_corresp_in_pct_garanties_j"] = (
        agg["ist_corresp_in_n_garanties_j"] / agg["ist_corresp_in_n_theoriques_j"]
    ).where(agg["ist_corresp_in_n_theoriques_j"] > 0)

    result = full.merge(agg, on=["date", "numero_train", SERVICE_ID_COL], how="left")
    result["ist_corresp_in_n_theoriques_j"] = result["ist_corresp_in_n_theoriques_j"].fillna(0).astype(int)
    result["ist_corresp_in_n_garanties_j"] = result["ist_corresp_in_n_garanties_j"].fillna(0).astype(int)
    return result


# ---------------------------------------------------------------------------
# Sens SORTANT (_out_) : R35 arrivant à Vevey → CFF partant
# ---------------------------------------------------------------------------


def _lire_departs_cff_vevey() -> pd.DataFrame:
    """Lit toutes les départs de CFF à Vevey (ABFAHRTSZEIT)."""
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    fragments: list[pd.DataFrame] = []

    for i, fich in enumerate(fichiers, 1):
        try:
            df = pd.read_csv(fich, encoding="utf-8-sig", **_lire_kwargs())
        except UnicodeDecodeError:
            df = pd.read_csv(fich, encoding="latin-1", **_lire_kwargs())
            log.warning("Encodage latin-1 pour %s", fich.name)

        masque = (
            (df["BPUIC"] == BPUIC_VEVEY)
            & (df["LINIEN_TEXT"].isin(LINIEN_FEEDERS))
            & (df["DURCHFAHRT_TF"].str.lower() != "true")
            & (df["FAELLT_AUS_TF"].str.lower() != "true")
            & df["ABFAHRTSZEIT"].notna()
        )
        df_v = df.loc[masque, [
            "BETRIEBSTAG", "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS",
        ]].copy()

        if df_v.empty:
            continue

        df_v["date"] = pd.to_datetime(df_v["BETRIEBSTAG"], format="%d.%m.%Y")
        df_v["horaire_depart_cff"] = pd.to_datetime(
            df_v["ABFAHRTSZEIT"], format="%d.%m.%Y %H:%M", errors="coerce"
        )
        df_v["reel_depart_cff"] = pd.to_datetime(
            df_v["AB_PROGNOSE"], format="%d.%m.%Y %H:%M:%S", errors="coerce"
        )
        statut_ok = df_v["AB_PROGNOSE_STATUS"].isin(STATUTS_REELS)
        df_v["retard_cff_sec"] = (
            (df_v["reel_depart_cff"] - df_v["horaire_depart_cff"])
            .dt.total_seconds()
            .where(statut_ok)
        )
        fragments.append(df_v[["date", "horaire_depart_cff", "reel_depart_cff", "retard_cff_sec"]])
        log.info("[%02d/%02d] %s : %d départs CFF", i, len(fichiers), fich.name, len(df_v))

    if not fragments:
        return pd.DataFrame(columns=["date", "horaire_depart_cff", "reel_depart_cff", "retard_cff_sec"])
    return pd.concat(fragments, ignore_index=True)


def _r35_arrivant_vevey(df_fact: pd.DataFrame) -> pd.DataFrame:
    """Trains R35 arrivant à Vevey avec leur horaire et heure réelle d'arrivée."""
    df = df_fact[
        (df_fact["bpuic"] == BPUIC_VEVEY) & df_fact["horaire_arrivee"].notna()
    ].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "numero_train", SERVICE_ID_COL, "horaire_arrivee", "reel_arrivee", "statut_arrivee"]].drop_duplicates()


def _calculer_correspondances_out(
    trains_vevey: pd.DataFrame,
    cff_departs: pd.DataFrame,
) -> pd.DataFrame:
    """Indicateurs de correspondance _out_ par (date, numero_train)."""
    cols_base = [
        "ist_corresp_out_n_theoriques_j",
        "ist_corresp_out_n_garanties_j",
        "ist_corresp_out_pct_garanties_j",
        "ist_corresp_out_retard_moy_j",
    ]

    full = trains_vevey[["date", "numero_train", SERVICE_ID_COL]].drop_duplicates().copy()
    if cff_departs.empty:
        for c in cols_base:
            full[c] = np.nan
        full["ist_corresp_out_n_theoriques_j"] = 0
        full["ist_corresp_out_n_garanties_j"] = 0
        return full

    merged = trains_vevey.merge(cff_departs, on="date", how="left")
    merged = merged[merged["horaire_depart_cff"].notna()].copy()

    # Délai théorique : CFF part dans [arrivée_R35 + 1min, arrivée_R35 + 5min]
    merged["delai_theorique_min"] = (
        (merged["horaire_depart_cff"] - merged["horaire_arrivee"])
        .dt.total_seconds() / 60
    )
    masque_theorique = (
        (merged["delai_theorique_min"] >= FENETRE_OUT_AMONT_MIN)
        & (merged["delai_theorique_min"] <= FENETRE_OUT_AVAL_MIN)
    )
    fenetre = merged[masque_theorique].copy()

    # Arrivée effective du R35 (réelle si disponible)
    statut_arr_reel = fenetre["statut_arrivee"].isin(STATUTS_REELS)
    fenetre["arr_effective_r35"] = fenetre["reel_arrivee"].where(
        statut_arr_reel, fenetre["horaire_arrivee"]
    )
    # Départ effectif du CFF
    fenetre["dep_effectif_cff"] = fenetre["reel_depart_cff"].fillna(fenetre["horaire_depart_cff"])

    # Garantie : CFF part dans la fenêtre effective (après arrivée réelle du R35)
    fenetre["correspondance_garantie"] = (
        (fenetre["dep_effectif_cff"] - fenetre["arr_effective_r35"]).dt.total_seconds() / 60
        >= FENETRE_OUT_AMONT_MIN
    ) & (
        (fenetre["dep_effectif_cff"] - fenetre["arr_effective_r35"]).dt.total_seconds() / 60
        <= FENETRE_OUT_AVAL_MIN
    )

    agg = fenetre.groupby(["date", "numero_train", SERVICE_ID_COL], as_index=False).agg(
        ist_corresp_out_n_theoriques_j=("delai_theorique_min", "count"),
        ist_corresp_out_n_garanties_j=("correspondance_garantie", "sum"),
        ist_corresp_out_retard_moy_j=("retard_cff_sec", "mean"),
    )
    agg["ist_corresp_out_pct_garanties_j"] = (
        agg["ist_corresp_out_n_garanties_j"] / agg["ist_corresp_out_n_theoriques_j"]
    ).where(agg["ist_corresp_out_n_theoriques_j"] > 0)

    result = full.merge(agg, on=["date", "numero_train", SERVICE_ID_COL], how="left")
    result["ist_corresp_out_n_theoriques_j"] = result["ist_corresp_out_n_theoriques_j"].fillna(0).astype(int)
    result["ist_corresp_out_n_garanties_j"] = result["ist_corresp_out_n_garanties_j"].fillna(0).astype(int)
    return result


# ---------------------------------------------------------------------------
# Rolling windows par type de jour (commun aux deux sens)
# ---------------------------------------------------------------------------


def _ajouter_rolling_corresp(df: pd.DataFrame, sens: str) -> pd.DataFrame:
    """Ajoute les rolling windows 5occ et 20occ pour les 3 features du sens donné.

    n_theoriques_moy et n_garanties_moy : moyenne glissante (stat="mean").
    pct_garanties : ratio de sommes glissantes (sum garanties / sum théoriques)
      pour éviter la moyenne bruitée des ratios quand n_theoriques_j est faible.
      NaN si sum théoriques == 0 sur la fenêtre.
    """
    df = df.copy()
    col_theoriques = f"ist_corresp_{sens}_n_theoriques_j"
    col_garanties = f"ist_corresp_{sens}_n_garanties_j"

    for n_occ, min_per, suffix_fen in FENETRES:
        # --- n_theoriques_moy et n_garanties_moy (moyenne) ---
        for col_src, suffix_out in [
            (col_theoriques, "n_theoriques_moy"),
            (col_garanties, "n_garanties_moy"),
        ]:
            df[f"ist_corresp_{sens}_{suffix_out}_{suffix_fen}"] = rolling_par_type_jour(
                df,
                group_key=SERVICE_ID_COL,
                date_col="date",
                type_jour_col=TYPE_JOUR_COL,
                value_col=col_src,
                n_occurrences=n_occ,
                min_periods=min_per,
                lag=LAG_OPERATIONNEL,
                stat="mean",
            )

        # --- pct_garanties (ratio de sommes, pas moyenne de ratios) ---
        rolling_sum_garanties = rolling_par_type_jour(
            df,
            group_key=SERVICE_ID_COL,
            date_col="date",
            type_jour_col=TYPE_JOUR_COL,
            value_col=col_garanties,
            n_occurrences=n_occ,
            min_periods=min_per,
            lag=LAG_OPERATIONNEL,
            stat="sum",
        )
        rolling_sum_theoriques = rolling_par_type_jour(
            df,
            group_key=SERVICE_ID_COL,
            date_col="date",
            type_jour_col=TYPE_JOUR_COL,
            value_col=col_theoriques,
            n_occurrences=n_occ,
            min_periods=min_per,
            lag=LAG_OPERATIONNEL,
            stat="sum",
        )
        pct = rolling_sum_garanties / rolling_sum_theoriques
        # NaN quand sum théoriques == 0 (division par zéro → inf → remplacé par NaN)
        pct = pct.where(rolling_sum_theoriques > 0)
        df[f"ist_corresp_{sens}_pct_garanties_{suffix_fen}"] = pct

    return df


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("Lecture de fact_istdaten_r35 ...")
    df_fact = pd.read_parquet(ISTDATEN_CLEAN)
    df_fact["date"] = pd.to_datetime(df_fact["date"])
    log.info("  %d lignes (date × train × arrêt)", len(df_fact))

    log.info("Construction des service_ids ...")
    df_fact = _ajouter_service_id(df_fact)

    # -------------------------------------------------------------------------
    # Sens entrant (_in_)
    # -------------------------------------------------------------------------
    log.info("Lecture des feeders CFF entrants à Vevey ...")
    feeders = _lire_arrivees_feeders_vevey()
    log.info("  %d arrivées feeders", len(feeders))

    trains_partant = _r35_partant_vevey(df_fact)
    log.info("  %d combinaisons (train, jour) R35 partant de Vevey", len(trains_partant))

    log.info("Calcul des correspondances _in_ ...")
    corresp_in = _calculer_correspondances_in(trains_partant, feeders)
    log.info("  Couverture in — n_theoriques : %d / %d",
             corresp_in["ist_corresp_in_n_theoriques_j"].gt(0).sum(), len(corresp_in))

    # -------------------------------------------------------------------------
    # Sens sortant (_out_)
    # -------------------------------------------------------------------------
    log.info("Lecture des CFF sortants de Vevey ...")
    cff_departs = _lire_departs_cff_vevey()
    log.info("  %d départs CFF", len(cff_departs))

    trains_arrivant = _r35_arrivant_vevey(df_fact)
    log.info("  %d combinaisons (train, jour) R35 arrivant à Vevey", len(trains_arrivant))

    doublons = trains_partant[["date", "numero_train"]].merge(
        trains_arrivant[["date", "numero_train"]], on=["date", "numero_train"]
    )
    if not doublons.empty:
        log.warning(
            "%d combinaisons (date, train) présentes dans _in_ ET _out_ "
            "(train passant par Vevey dans les deux sens sur le même jour).",
            len(doublons),
        )

    log.info("Calcul des correspondances _out_ ...")
    corresp_out = _calculer_correspondances_out(trains_arrivant, cff_departs)
    log.info("  Couverture out — n_theoriques : %d / %d",
             corresp_out["ist_corresp_out_n_theoriques_j"].gt(0).sum(), len(corresp_out))

    # -------------------------------------------------------------------------
    # Fusion, type de jour, rolling
    # -------------------------------------------------------------------------
    log.info("Fusion des deux sens ...")
    # Tous les trains R35 passant par Vevey (union des deux jeux)
    all_trains = (
        pd.concat([
            trains_partant[["date", "numero_train", SERVICE_ID_COL]],
            trains_arrivant[["date", "numero_train", SERVICE_ID_COL]],
        ])
        .drop_duplicates()
        .sort_values(["date", "numero_train"])
        .reset_index(drop=True)
    )
    df = all_trains.merge(corresp_in, on=["date", "numero_train", SERVICE_ID_COL], how="left")
    df = df.merge(corresp_out, on=["date", "numero_train", SERVICE_ID_COL], how="left")

    log.info("Ajout du type de jour ...")
    df = _ajouter_type_jour(df, date_col="date")

    log.info("Calcul des rolling windows _in_ ...")
    df = _ajouter_rolling_corresp(df, "in")
    log.info("Calcul des rolling windows _out_ ...")
    df = _ajouter_rolling_corresp(df, "out")

    # Sélection des colonnes finales : rolling uniquement (features _j = internes)
    cols_in_roll = [c for c in df.columns if c.startswith("ist_corresp_in_") and not c.endswith("_j")]
    cols_out_roll = [c for c in df.columns if c.startswith("ist_corresp_out_") and not c.endswith("_j")]

    cols_finales = (
        ["date", "numero_train"]
        + sorted(cols_in_roll)
        + sorted(cols_out_roll)
    )
    df_out = df[[c for c in cols_finales if c in df.columns]].copy()

    n_features = len([c for c in df_out.columns if c.startswith("ist_corresp_")])
    log.info("%d features de correspondance générées", n_features)

    # Validation du taux d'effectivité (toujours dans [0, 1])
    for col in [c for c in df_out.columns if "pct_garanties" in c]:
        valid = df_out[col].dropna()
        if len(valid) > 0:
            assert valid.between(0, 1, inclusive="both").all(), (
                f"Taux hors [0, 1] dans {col}"
            )

    DIM_CORRESPONDANCES_VEVEY.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_CORRESPONDANCES_VEVEY.with_suffix(".tmp.parquet")
    try:
        df_out.to_parquet(tmp, index=False)
        tmp.rename(DIM_CORRESPONDANCES_VEVEY)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", DIM_CORRESPONDANCES_VEVEY)
    log.info("  %d lignes × %d colonnes", df_out.shape[0], df_out.shape[1])
    log.info(
        "  Période : %s → %s",
        str(df_out["date"].min())[:10],
        str(df_out["date"].max())[:10],
    )


if __name__ == "__main__":
    main()
