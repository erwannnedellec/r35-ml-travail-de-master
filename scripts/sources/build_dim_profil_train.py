"""
build_dim_profil_train.py
==========================
Construit le profil historique de ponctualité par tronçon × train R35.

Grain de sortie : date × numero_train × gare_depart_bpuic × gare_arrivee_bpuic × sens

Évolution par rapport à la version précédente
----------------------------------------------
- Grain affiné : tronçon (paires d'arrêts successifs) au lieu de train-jour.
  Cela capture la dégradation de ponctualité le long du parcours.
- Rolling conditionnel par type de jour : les fenêtres ne comparent que des
  occurrences du même type de jour (ouvrable, samedi, dimanche_ferie).
  Cf. ADR-019_refonte_features_ist_grain_troncon_rolling_type_jour.
- Groupement par service_id (numero_train + heure d'origine) au lieu de
  numero_train seul. Évite le mélange de services renumérotés entre horaires.
- Deux fenêtres : 5 occurrences (court) et 20 occurrences (long).

Logique J-2
-----------
Les fenêtres glissantes sont calculées avec lag=0 (aucun décalage dans le
rolling). La responsabilité du décalage J-2 est portée exclusivement par la
jointure dans add_istdaten_to_raw_stacked.py, qui lit la ligne ISTDATEN de
date=J-2 pour alimenter la prédiction du jour J. Le rolling à date=J-2
couvre donc les N occurrences du même type de jour se terminant à J-2 inclus,
ce qui est le comportement correct pour une décision à J-1.

Convention de ponctualité
--------------------------
Un départ/arrivée est en retard si retard_sec >= SEUIL_PONCTUALITE_SEC (180s).
Les départs en avance ne sont pas comptabilisés comme retards (pas de risque
de rater une correspondance à l'origine).

Features produites (12 par tronçon-train-jour)
-----------------------------------------------
Pour position ∈ {dep, arr} et fenêtre ∈ {5occ, 20occ} :
  ist_profil_train_retard_{position}_troncon_mean_{fenetre}
  ist_profil_train_retard_{position}_troncon_std_{fenetre}
  ist_profil_train_pct_en_retard_{position}_troncon_{fenetre}

Inputs
------
  data/processed/sources/istdaten_clean.parquet
  data/dimension/dim_gare.parquet       (km pour déduire le sens)
  data/dimension/dim_vacances_feries_vaud.parquet  (cal_type_jour_3classes)

Output
------
  data/processed/sources/dim_profil_train.parquet

    Grain : date × numero_train × gare_depart_bpuic × gare_arrivee_bpuic × sens
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import DIM_GARE, DIM_PROFIL_TRAIN, DIM_VACANCES_FERIES, ISTDATEN_CLEAN
from _rolling_par_type_jour import rolling_par_type_jour

SEUIL_PONCTUALITE_SEC: int = 180
STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

# Fenêtres de rolling : (n_occurrences, min_periods, suffixe_colonne)
FENETRES: list[tuple[int, int, str]] = [
    (5,  2, "5occ"),
    (20, 5, "20occ"),
]

# lag=0 : la fenêtre inclut l'observation courante (date=J-2).
# Le décalage J-2 est géré exclusivement par la jointure dans
# add_istdaten_to_raw_stacked.py (base_date = date + 2 jours).
LAG_OPERATIONNEL: int = 0
TYPE_JOUR_COL: str = "cal_type_jour_3classes"
DATE_COL: str = "date"
SERVICE_ID_COL: str = "ist_service_id"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topologie R35 et déduction du sens
# ---------------------------------------------------------------------------


def _charger_km_par_bpuic() -> dict[int, float]:
    """Retourne un mapping bpuic → km depuis dim_gare."""
    gares = pd.read_parquet(DIM_GARE, columns=["bpuic", "km"])
    return dict(zip(gares["bpuic"].dropna().astype(int), gares["km"].astype(float)))


# ---------------------------------------------------------------------------
# Construction du service_id depuis les données ISTDATEN
# ---------------------------------------------------------------------------


def _ajouter_service_id(df_fact: pd.DataFrame) -> pd.DataFrame:
    """Construit ist_service_id = numero_train + heure du premier arrêt théorique.

    Remplace le groupement par numero_train seul pour éviter le mélange de
    services renumérotés entre deux horaires annuels.
    Cohérent avec horaire_service_id_complet dans add_features_to_raw_stacked.py.
    """
    df = df_fact.copy()
    df["_date_dt"] = pd.to_datetime(df[DATE_COL], errors="coerce")

    premier_dep = (
        df.dropna(subset=["horaire_depart"])
        .groupby(["_date_dt", "numero_train"], as_index=False)["horaire_depart"]
        .min()
        .rename(columns={"horaire_depart": "_heure_origine"})
    )
    heure_str = premier_dep["_heure_origine"].dt.strftime("%Hh%M").fillna("NA")
    premier_dep[SERVICE_ID_COL] = (
        premier_dep["numero_train"].astype(str) + "_" + heure_str
    )

    df = df.merge(
        premier_dep[["_date_dt", "numero_train", SERVICE_ID_COL]],
        on=["_date_dt", "numero_train"],
        how="left",
    )
    return df.drop(columns=["_date_dt"])


# ---------------------------------------------------------------------------
# Reconstruction des tronçons (logique partagée avec build_dim_headway.py)
# ---------------------------------------------------------------------------


def _reconstruire_troncons(
    df_fact: pd.DataFrame,
    km_par_bpuic: dict[int, float],
) -> pd.DataFrame:
    """Transforme le grain (date, train, arrêt) en grain (date, train, tronçon, sens).

    Même logique que dans build_dim_headway.py :
    - Filtre les trains annulés.
    - Trie par heure de départ effective (réelle si REAL/GESCHAETZT, théorique sinon).
    - Construit des paires successives d'arrêts (bpuic_n, bpuic_n+1).
    - Déduit le sens depuis l'ordre kilométrique.
    - Conserve les retards de départ (gare amont) et d'arrivée (gare aval) du tronçon.
    """
    df = df_fact[~df_fact["is_annule"]].copy()

    df["depart_effectif"] = df["reel_depart"].where(
        df["statut_depart"].isin(STATUTS_REELS),
        df["horaire_depart"],
    )

    df = df.sort_values([DATE_COL, "numero_train", "depart_effectif"]).reset_index(drop=True)

    grp = df.groupby([DATE_COL, "numero_train"])
    df["bpuic_arr"] = grp["bpuic"].shift(-1)
    df["retard_arr_sec"] = grp["retard_arrivee_sec"].shift(-1)

    troncons = df.dropna(subset=["bpuic_arr"]).copy()
    troncons["bpuic_arr"] = troncons["bpuic_arr"].astype(int)

    troncons["km_dep"] = troncons["bpuic"].map(km_par_bpuic)
    troncons["km_arr"] = troncons["bpuic_arr"].map(km_par_bpuic)
    troncons = troncons.dropna(subset=["km_dep", "km_arr"])

    troncons["sens"] = np.where(
        troncons["km_dep"] < troncons["km_arr"],
        "VV -> PLEI",
        "PLEI -> VV",
    )

    return troncons.rename(columns={
        "bpuic": "gare_depart_bpuic",
        "bpuic_arr": "gare_arrivee_bpuic",
        "retard_depart_sec": "retard_dep_troncon_sec",
        "retard_arr_sec": "retard_arr_troncon_sec",
    })[[
        DATE_COL, "numero_train", SERVICE_ID_COL,
        "gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
        "retard_dep_troncon_sec", "retard_arr_troncon_sec",
    ]].copy()


# ---------------------------------------------------------------------------
# Ajout du type de jour
# ---------------------------------------------------------------------------


def _ajouter_type_jour(df: pd.DataFrame) -> pd.DataFrame:
    """Joint dim_vacances_feries_vaud pour obtenir cal_type_jour_3classes."""
    feries = pd.read_parquet(
        DIM_VACANCES_FERIES,
        columns=["date", "is_ferie_vaud", "jour_semaine_iso"],
    )
    feries["date"] = pd.to_datetime(feries["date"])

    # Calcul de cal_type_jour_3classes directement depuis les colonnes sources
    feries[TYPE_JOUR_COL] = np.where(
        feries["is_ferie_vaud"] | (feries["jour_semaine_iso"] == 7),
        "dimanche_ferie",
        np.where(feries["jour_semaine_iso"] == 6, "samedi", "ouvrable"),
    )

    df = df.copy()
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    return df.merge(feries[["date", TYPE_JOUR_COL]], on=DATE_COL, how="left")


# ---------------------------------------------------------------------------
# Agrégation au grain (date, service_id, tronçon)
# ---------------------------------------------------------------------------


def _agreger_troncon_jour(troncons: pd.DataFrame) -> pd.DataFrame:
    """Agrège au grain (date × service_id × tronçon) = unicité requise pour rolling."""
    GRAIN = [DATE_COL, SERVICE_ID_COL, "numero_train",
              "gare_depart_bpuic", "gare_arrivee_bpuic", "sens"]

    agg = troncons.groupby(GRAIN, as_index=False).agg(
        retard_dep_troncon_sec=("retard_dep_troncon_sec", "mean"),
        retard_arr_troncon_sec=("retard_arr_troncon_sec", "mean"),
    )

    # Booléens de retard (>= seuil)
    # Départ : retard >= seuil (pas de valeur absolue — l'avance n'est pas un problème
    # pour les correspondances à l'origine d'un tronçon).
    agg["is_en_retard_dep"] = (
        agg["retard_dep_troncon_sec"].notna()
        & (agg["retard_dep_troncon_sec"] >= SEUIL_PONCTUALITE_SEC)
    ).astype("float64")
    # Arrivée : retard >= seuil (convention retard seul, cohérente avec
    # ist_vevey_pct_arr_ponctuel_180s_j dans build_istdaten_ponctualite.py).
    agg["is_en_retard_arr"] = (
        agg["retard_arr_troncon_sec"].notna()
        & (agg["retard_arr_troncon_sec"] >= SEUIL_PONCTUALITE_SEC)
    ).astype("float64")

    # NaN si le retard source est NaN
    agg.loc[agg["retard_dep_troncon_sec"].isna(), "is_en_retard_dep"] = np.nan
    agg.loc[agg["retard_arr_troncon_sec"].isna(), "is_en_retard_arr"] = np.nan

    return agg


# ---------------------------------------------------------------------------
# Rolling windows par type de jour
# ---------------------------------------------------------------------------


def _ajouter_rolling(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les 12 features de ponctualité par tronçon-train-jour.

    Pour position ∈ {dep, arr} et fenêtre ∈ {5occ, 20occ} :
      ist_profil_train_retard_{position}_troncon_mean_{fenetre}
      ist_profil_train_retard_{position}_troncon_std_{fenetre}
      ist_profil_train_pct_en_retard_{position}_troncon_{fenetre}
    """
    df = df.copy().sort_values([DATE_COL, SERVICE_ID_COL,
                                "gare_depart_bpuic", "gare_arrivee_bpuic", "sens"])

    # Clé composite : service_id × tronçon (sens inclus dans les clés de tronçon)
    df["_gk"] = (
        df[SERVICE_ID_COL].astype(str) + "_"
        + df["gare_depart_bpuic"].astype(str) + "_"
        + df["gare_arrivee_bpuic"].astype(str) + "_"
        + df["sens"]
    )

    for position, col_retard, col_bool in [
        ("dep", "retard_dep_troncon_sec", "is_en_retard_dep"),
        ("arr", "retard_arr_troncon_sec", "is_en_retard_arr"),
    ]:
        for n_occ, min_per, suffix in FENETRES:
            df[f"ist_profil_train_retard_{position}_troncon_mean_{suffix}"] = rolling_par_type_jour(
                df, group_key="_gk", date_col=DATE_COL, type_jour_col=TYPE_JOUR_COL,
                value_col=col_retard, n_occurrences=n_occ, min_periods=min_per,
                lag=LAG_OPERATIONNEL, stat="mean",
            )
            df[f"ist_profil_train_retard_{position}_troncon_std_{suffix}"] = rolling_par_type_jour(
                df, group_key="_gk", date_col=DATE_COL, type_jour_col=TYPE_JOUR_COL,
                value_col=col_retard, n_occurrences=n_occ, min_periods=min_per,
                lag=LAG_OPERATIONNEL, stat="std",
            )
            df[f"ist_profil_train_pct_en_retard_{position}_troncon_{suffix}"] = rolling_par_type_jour(
                df, group_key="_gk", date_col=DATE_COL, type_jour_col=TYPE_JOUR_COL,
                value_col=col_bool, n_occurrences=n_occ, min_periods=min_per,
                lag=LAG_OPERATIONNEL, stat="mean",
            )

    return df.drop(columns=["_gk"])


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


COLS_FEATURES = [
    f"ist_profil_train_retard_{pos}_troncon_{stat}_{fen}"
    for pos in ["dep", "arr"]
    for _, _, fen in FENETRES
    for stat in ["mean", "std"]
] + [
    f"ist_profil_train_pct_en_retard_{pos}_troncon_{fen}"
    for pos in ["dep", "arr"]
    for _, _, fen in FENETRES
]

GRAIN_COLS = [
    DATE_COL, "numero_train",
    "gare_depart_bpuic", "gare_arrivee_bpuic", "sens",
]

COLS_FINALES = GRAIN_COLS + COLS_FEATURES


def main() -> None:
    log.info("Lecture de fact_istdaten_r35 ...")
    df_fact = pd.read_parquet(ISTDATEN_CLEAN)
    log.info("  %d lignes (date × train × arrêt)", len(df_fact))

    log.info("Construction des service_ids depuis ISTDATEN ...")
    df_fact = _ajouter_service_id(df_fact)
    log.info("  %d service_ids distincts", df_fact[SERVICE_ID_COL].nunique())

    log.info("Chargement de la topologie R35 ...")
    km_par_bpuic = _charger_km_par_bpuic()

    log.info("Reconstruction des tronçons ...")
    troncons = _reconstruire_troncons(df_fact, km_par_bpuic)
    log.info("  %d lignes (date × train × tronçon)", len(troncons))

    log.info("Agrégation au grain (date × service_id × tronçon) ...")
    daily = _agreger_troncon_jour(troncons)
    log.info("  %d combinaisons uniques", len(daily))

    log.info("Ajout du type de jour (cal_type_jour_3classes) ...")
    daily = _ajouter_type_jour(daily)
    n_sans_type = daily[TYPE_JOUR_COL].isna().sum()
    if n_sans_type:
        log.warning("  %d lignes sans cal_type_jour_3classes (dates hors dim_vacances_feries)", n_sans_type)

    log.info("Calcul des rolling windows par type de jour (%d fenêtres × 2 positions × 3 stats) ...", len(FENETRES))
    daily = _ajouter_rolling(daily)

    # Rapport de couverture
    n = len(daily)
    log.info("Couverture des features (n=%d) :", n)
    for col in COLS_FEATURES:
        if col in daily.columns:
            pct = 100 * daily[col].notna().sum() / n
            log.info("  %-65s : %5.1f%%", col, pct)

    df_out = daily[COLS_FINALES].copy()

    # Validation de plausibilité : les retards moyens > 2h sont suspects
    for col in [c for c in COLS_FEATURES if "mean" in c]:
        max_val = df_out[col].abs().max()
        if not pd.isna(max_val) and max_val > 7200:
            log.warning("Retard moyen suspect (> 2h) dans %s : %.0fs", col, max_val)

    DIM_PROFIL_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_PROFIL_TRAIN.with_suffix(".tmp.parquet")
    try:
        df_out.to_parquet(tmp, index=False)
        tmp.rename(DIM_PROFIL_TRAIN)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", DIM_PROFIL_TRAIN)
    log.info("  %d lignes × %d colonnes", df_out.shape[0], df_out.shape[1])
    log.info(
        "  Période : %s → %s",
        str(df_out[DATE_COL].min())[:10],
        str(df_out[DATE_COL].max())[:10],
    )
    log.info("  Tronçons uniques : %d", df_out.groupby(["gare_depart_bpuic", "gare_arrivee_bpuic"]).ngroups)
    log.info("  service_ids × tronçons distincts : %d", df_out[[SERVICE_ID_COL if SERVICE_ID_COL in df_out.columns else "numero_train",
                                                                   "gare_depart_bpuic", "gare_arrivee_bpuic"]].drop_duplicates().shape[0]
             if SERVICE_ID_COL not in COLS_FINALES else
             df_out[["gare_depart_bpuic", "gare_arrivee_bpuic"]].drop_duplicates().shape[0])


if __name__ == "__main__":
    main()
