"""
build_dim_headway.py
=====================
Calcule deux features de headway depuis ISTDATEN au niveau tronçon × sens,
en utilisant uniquement l'horaire théorique.

Feature émergente des entretiens qualitatifs (P02, P05, P06).
La formulation symétrique capture l'isolement temporel sans préjuger
de la direction de l'effet.

Grain de sortie : date × numero_train × gare_depart × gare_arrivee × sens

Features
--------
- ist_headway_avant_min         : minutes depuis le départ théorique du train
                                  précédent sur le même tronçon × sens.
                                  NaN si premier train de la journée.
- ist_headway_apres_min         : minutes jusqu'au départ théorique du train
                                  suivant sur le même tronçon × sens.
                                  NaN si dernier train de la journée.
- ist_headway_avant_is_first_of_day : 1 si pas de prédécesseur ce jour-là,
                                      0 sinon (int8).
- ist_headway_apres_is_last_of_day  : 1 si pas de successeur ce jour-là,
                                      0 sinon (int8).

Définition de l'heure de départ théorique
------------------------------------------
Seul horaire_depart est utilisé (ISTDATEN théorique, pas le PDF).
Aucun fallback sur reel_depart : utiliser les heures réelles crée un
distribution shift entraînement/inférence car MOB n'a que l'horaire
théorique à J-1 au moment de la décision.

Périmètre : grille PLANIFIÉE connue à J-1 (ADR-066). Le critère unique est
« le train était-il dans la grille planifiée connue à J-1 ? ». Aucun filtre de
statut réalisé n'est appliqué :
- is_annule = True → INCLUS. Le train est planifié ; l'annulation n'est pas
  connue à J-1 au moment de la décision. Filtrer les annulés injecterait de
  l'information réalisée non disponible à l'inférence.
- is_supplementaire = True → INCLUS. Les suppléments sont planifiés en amont
  (le processus de planification MOB n'autorise pas d'ajout le jour J, confirmé
  par E. Nédellec) ; ils font donc partie de la grille connue à J-1.
Le headway est ainsi purement planifié (réguliers + annulés + suppléments).

Reconstruction des tronçons
-----------------------------
Le grain de fact_istdaten_r35 est (date, numero_train, bpuic) au niveau arrêt.
Pour chaque (date, numero_train), les arrêts sont triés par horaire_depart
(théorique) et des paires successives (bpuic_n, bpuic_n+1) forment les tronçons.
Le sens est déduit de l'ordre kilométrique dans dim_gare.

Clé de jointure avec stage_07_istdaten (via add_features_to_raw_stacked.py)
----------------------------------------------------------------------------
  (date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)
    ↔ (base_date, horaire_numero_train, id_gare_depart_bpuic, id_gare_arrivee_bpuic, base_sens)

Inputs
------
  data/processed/sources/istdaten_clean.parquet
  data/dimension/dim_gare.parquet  (colonne km pour déduire le sens)

Output
------
  data/processed/sources/dim_headway.parquet
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import DIM_GARE, DIM_HEADWAY, ISTDATEN_CLEAN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _construire_topologie_r35() -> dict[int, float]:
    """Retourne un mapping bpuic → km depuis dim_gare."""
    gares = pd.read_parquet(DIM_GARE, columns=["bpuic", "km"])
    gares = gares.dropna(subset=["bpuic", "km"])
    return dict(zip(gares["bpuic"].astype(int), gares["km"].astype(float)))


def _reconstruire_troncons(
    df_istdaten: pd.DataFrame,
    km_par_bpuic: dict[int, float],
) -> pd.DataFrame:
    """Transforme le grain (date, train, arrêt) en grain (date, train, tronçon, sens).

    Utilise uniquement horaire_depart pour le tri des arrêts, éliminant le
    distribution shift entraînement/inférence présent avec reel_depart.

    ADR-066 : aucun filtre de statut réalisé. Tous les trains de la grille
    planifiée connue à J-1 sont inclus (réguliers + annulés + suppléments) :
    l'annulation et le statut réalisé ne sont pas connus au moment de la décision.
    """
    df = df_istdaten.copy()

    df["depart_theorique"] = df["horaire_depart"]

    df = df.sort_values(
        ["date", "numero_train", "depart_theorique"]
    ).reset_index(drop=True)

    df["bpuic_arr"] = df.groupby(["date", "numero_train"])["bpuic"].shift(-1)
    df["nom_arr"] = df.groupby(["date", "numero_train"])["haltestellen_name"].shift(-1)

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
        "haltestellen_name": "gare_depart",
        "nom_arr": "gare_arrivee",
        "bpuic_arr": "gare_arrivee_bpuic",
    })[[
        "date", "numero_train",
        "gare_depart_bpuic", "gare_depart",
        "gare_arrivee_bpuic", "gare_arrivee",
        "sens", "depart_theorique", "is_supplementaire",
    ]].copy()


def _calculer_headway(troncons: pd.DataFrame) -> pd.DataFrame:
    """Calcule ist_headway_avant_min, ist_headway_apres_min et les flags binaires.

    NaN quand pas de prédécesseur/successeur (premier/dernier train de la journée).
    Les flags ist_headway_*_is_first/last_of_day valent 1 exactement quand NaN.
    """
    df = troncons.sort_values(
        ["date", "gare_depart_bpuic", "gare_arrivee_bpuic", "sens", "depart_theorique"]
    ).reset_index(drop=True)

    cle = ["date", "gare_depart_bpuic", "gare_arrivee_bpuic", "sens"]

    df["depart_prec"] = df.groupby(cle)["depart_theorique"].shift(1)
    df["depart_suiv"] = df.groupby(cle)["depart_theorique"].shift(-1)

    df["ist_headway_avant_min"] = (
        (df["depart_theorique"] - df["depart_prec"]).dt.total_seconds() / 60
    )
    df["ist_headway_apres_min"] = (
        (df["depart_suiv"] - df["depart_theorique"]).dt.total_seconds() / 60
    )

    df["ist_headway_avant_is_first_of_day"] = (
        df["ist_headway_avant_min"].isna().astype("int8")
    )
    df["ist_headway_apres_is_last_of_day"] = (
        df["ist_headway_apres_min"].isna().astype("int8")
    )

    return df[[
        "date", "numero_train",
        "gare_depart_bpuic", "gare_depart",
        "gare_arrivee_bpuic", "gare_arrivee",
        "sens",
        "ist_headway_avant_min", "ist_headway_apres_min",
        "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day",
    ]].copy()


def _validation_plausibilite(df: pd.DataFrame) -> None:
    for col, flag_col in [
        ("ist_headway_avant_min", "ist_headway_avant_is_first_of_day"),
        ("ist_headway_apres_min", "ist_headway_apres_is_last_of_day"),
    ]:
        # Cohérence NaN ↔ flag=1
        nan_mask = df[col].isna()
        flag_mask = df[flag_col] == 1
        incohérents = (nan_mask != flag_mask).sum()
        assert incohérents == 0, (
            f"{col} : {incohérents} lignes où NaN ≠ flag ({flag_col})"
        )

        valid = df.loc[~nan_mask, col]
        assert (valid >= 0).all(), f"{col} : valeur négative détectée"
        assert (valid < 24 * 60).all(), f"{col} : valeur > 24h détectée"

        n_nan = nan_mask.sum()
        log.info(
            "%s : min=%.1f  med=%.1f  P90=%.1f  P99=%.1f min  "
            "NaN (premier/dernier)=%d (%.1f%%)",
            col, valid.min(), valid.median(),
            valid.quantile(0.90), valid.quantile(0.99),
            n_nan, 100 * n_nan / len(df),
        )


def main() -> None:
    log.info("Lecture de fact_istdaten_r35 (%s) ...", ISTDATEN_CLEAN.name)
    df_ist = pd.read_parquet(ISTDATEN_CLEAN, columns=[
        "date", "numero_train", "bpuic", "haltestellen_name",
        "horaire_depart",
        "is_annule", "is_supplementaire",
    ])
    log.info("  %d lignes (date × train × arrêt)", len(df_ist))

    log.info("Construction de la topologie R35 ...")
    km_par_bpuic = _construire_topologie_r35()
    log.info("  %d gares mappées", len(km_par_bpuic))

    log.info("Reconstruction des tronçons (horaire théorique uniquement) ...")
    troncons = _reconstruire_troncons(df_ist, km_par_bpuic)
    log.info("  %d lignes (date × train × tronçon)", len(troncons))

    log.info("Calcul des headway avant/après ...")
    headway_df = _calculer_headway(troncons)

    _validation_plausibilite(headway_df)

    DIM_HEADWAY.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIM_HEADWAY.with_suffix(".tmp.parquet")
    try:
        headway_df.to_parquet(tmp, index=False)
        tmp.rename(DIM_HEADWAY)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", DIM_HEADWAY)
    log.info("  %d lignes × %d colonnes", headway_df.shape[0], headway_df.shape[1])
    log.info(
        "  Période : %s → %s",
        str(headway_df["date"].min())[:10],
        str(headway_df["date"].max())[:10],
    )
    log.info(
        "  Tronçons uniques : %d",
        headway_df.groupby(["gare_depart_bpuic", "gare_arrivee_bpuic"]).ngroups,
    )
    n_first = headway_df["ist_headway_avant_is_first_of_day"].sum()
    n_last = headway_df["ist_headway_apres_is_last_of_day"].sum()
    log.info(
        "  Premiers de journée : %d (%.1f%%)  |  Derniers : %d (%.1f%%)",
        n_first, 100 * n_first / len(headway_df),
        n_last, 100 * n_last / len(headway_df),
    )


if __name__ == "__main__":
    main()
