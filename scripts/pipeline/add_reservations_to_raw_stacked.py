"""
add_reservations_to_raw_stacked.py
===================================
Ajoute les 8 features réservations de groupes ResSys à stage_09_simba (→ stage_10_reservations).

Décision architecturale
------------------------
Les réservations de groupes sont intégrées en couche 1 du modèle XGBoost (features),
et non comme règle OR en couche 2 (ADR-035 §2.1). Cette décision est motivée par
la précision du prédicteur naïf (0.091 — 90 % de faux positifs si utilisé seul)
et le double-comptage sémantique qu'une OR-rule introduirait avec la target APC.

Périmètre
---------
Seules les réservations ``50 Abgeschlossen`` avec ``lead_days ≥ 1`` (connues à J-1)
sont utilisées. Les ``90 Storniert`` sont exclues (ADR-035 §2.5).
Années traitées : H22-H25 (cohérence ADR-027). H16-H21 hors ml_dataset utilisent
la topologie H22 comme proxy (ADR-035 §2.3).

Topologie year-specific (ADR-035 §2.3)
--------------------------------------
La LINE_ORDER est déduite des tronçons réellement présents dans le ml_dataset pour
chaque année horaire, via ``build_line_order_from_ml()``. Corrige le bug GIL
(notebook 02_ressys §9.4) : GIL était desservi en H22 uniquement ; la LINE_ORDER v1
statique créait des tronçons GIL inexistants en H23/H24 (3 688 orphelins, 38.2 %).

Features calculées (ADR-035 §2.6)
----------------------------------
  resa_pax_2c_J_minus_1           somme pax_2c des réservations confirmées à J-1
  resa_n_dossiers_J_minus_1       nombre de dossiers distincts
  resa_max_groupe_2c_J_minus_1    taille du plus gros groupe individuel
  resa_part_scolaire_J_minus_1    part pax_2c groupes scolaires (heuristique)
  resa_part_tour_operator_J_minus_1  part pax_2c tour-opérateurs (heuristique)
  resa_n_pays_distincts_J_minus_1 nombre de pays distincts
  resa_n_langues_distinctes_J_minus_1  nombre de langues distinctes
  resa_has_resa_J_minus_1         True si au moins une réservation connue à J-1

Imputation
----------
Cellules ml_dataset sans réservation : les 7 features numériques valent 0,
``resa_has_resa_J_minus_1`` vaut False (0 est sémantiquement correct).

Quality Gates logés
-------------------
  QG1 : schéma identique sur les 10 fichiers d'export ResSys
  QG2 : taux d'orphelins éclatement < 1 %
  QG3 : taux d'orphelins jointure H23 et H24 < 5 % ; H22 ~58 % (couverture
         partielle documentée — causes F+E, ADR-035 §2.7)

Sources
-------
- data/processed/stage_09_simba.parquet
- data/external/reservations/export_r35_h{16-25}.xlsx
- data/dimension/dim_gare.parquet

Sortie
------
- data/processed/stage_10_reservations.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_reservations_to_raw_stacked.py``
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (  # noqa: E402
    DIM_GARE,
    RESA_DIR,
    STAGE_09_SIMBA,
    STAGE_10_RESERVATIONS,
)
from pipeline.io import read_stage, write_stage  # noqa: E402
from pipeline.reservations_utils import (  # noqa: E402
    COL_RENAME,
    GARE_MAP,
    KEYWORDS_SCOLAIRE,
    KEYWORDS_TOUR_OPERATOR,
    LEAD_DAYS_MIN,
    STATUT_ABGESCHLOSSEN,
    build_line_order_from_ml,
    eclate_reservation,
    is_scolaire,
    is_tour_operator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WRITE_CSV = os.environ.get("WRITE_CSV", "").strip().lower() in {"1", "true", "yes"}

# Années traitées — cohérence ml_dataset ADR-027
ANNEES_HORAIRES: list[str] = [f"H{h:02d}" for h in range(16, 26)]
ANNEES_PIPELINE: list[str] = ["H22", "H23", "H24", "H25"]

# Colonnes de jointure
ML_DATE_COL     = "base_date"
ML_TRAIN_COL    = "horaire_numero_train"
ML_DEP_COL      = "id_gare_depart"
ML_ARR_COL      = "id_gare_arrivee"
ML_AH_COL       = "horaire_annee_horaire"

# Seuils Quality Gates
QG2_SEUIL_ORPHELINS_ECLATE = 0.01   # < 1 %
QG3_SEUIL_ORPHELINS_JOINT  = 0.05   # < 5 % (H23/H24 seulement)


# ---------------------------------------------------------------------------
# Étape 1 — Chargement et filtrage des réservations
# ---------------------------------------------------------------------------

def _charger_reservations() -> pd.DataFrame:
    """Charge les 10 fichiers d'export ResSys et retourne le DataFrame combiné filtré."""
    dfs: list[pd.DataFrame] = []
    schemas: list[list[str]] = []

    for ah in ANNEES_HORAIRES:
        h_num = int(ah[1:])
        fname = RESA_DIR / f"export_r35_h{h_num:02d}.xlsx"
        df = pd.read_excel(fname, sheet_name="Export")
        schemas.append(df.columns.tolist())
        df = df.rename(columns=COL_RENAME)
        df["annee_horaire"] = ah
        log.info(
            "  %s : %d lignes chargées (%d Abg, %d Sto)",
            fname.name, len(df),
            (df.statut == STATUT_ABGESCHLOSSEN).sum(),
            (df.statut != STATUT_ABGESCHLOSSEN).sum(),
        )
        dfs.append(df)

    # QG1 — schéma identique
    ref = schemas[0]
    for i, s in enumerate(schemas[1:], 1):
        if s != ref:
            log.warning(
                "QG1 WARN : schéma %s diffère de H16 (diff=%s)",
                ANNEES_HORAIRES[i], set(s) ^ set(ref),
            )
    log.info("QG1 : schéma vérifié sur %d fichiers", len(ANNEES_HORAIRES))

    df_all = pd.concat(dfs, ignore_index=True)

    # Filtrage : Abgeschlossen uniquement
    df_abg = df_all[df_all.statut == STATUT_ABGESCHLOSSEN].copy()

    # lead_days
    df_abg["date_voyage_d"]   = pd.to_datetime(df_abg["date_voyage"]).dt.normalize()
    df_abg["date_commande_d"] = pd.to_datetime(df_abg["date_commande"]).dt.normalize()
    df_abg["lead_days"] = (df_abg["date_voyage_d"] - df_abg["date_commande_d"]).dt.days
    df_abg = df_abg[df_abg["lead_days"] >= LEAD_DAYS_MIN]

    log.info(
        "Après filtre Abgeschlossen + lead_days ≥ %d : %d réservations",
        LEAD_DAYS_MIN, len(df_abg),
    )
    return df_abg


# ---------------------------------------------------------------------------
# Étape 2 — Éclatement multi-tronçons
# ---------------------------------------------------------------------------

def _eclater(df_abg: pd.DataFrame, df_ml: pd.DataFrame) -> pd.DataFrame:
    """Éclate les voyages logiques en tronçons élémentaires (year-specific)."""
    dim_gare = pd.read_parquet(DIM_GARE, columns=["abreviation", "nom", "ordre"])

    # LINE_ORDER par année horaire (topologie year-specific, ADR-035 §2.3)
    line_orders: dict[str, list[str]] = {}
    for ah in ANNEES_PIPELINE:
        sub_ml = df_ml[df_ml[ML_AH_COL] == ah]
        if len(sub_ml) > 0:
            line_orders[ah] = build_line_order_from_ml(sub_ml, dim_gare)
        else:
            line_orders[ah] = line_orders.get("H22", [])
        log.info("  %s LINE_ORDER : %s", ah, line_orders[ah])

    # H16-H21 utilisent H22 comme proxy
    lo_proxy = line_orders.get("H22", [])
    for ah in ANNEES_HORAIRES:
        if ah not in line_orders:
            line_orders[ah] = lo_proxy

    all_eclate: list[dict] = []
    all_orphelins: list[dict] = []
    total = len(df_abg)

    for _, row in df_abg.iterrows():
        ah = row["annee_horaire"]
        results = eclate_reservation(row, line_orders[ah], GARE_MAP)
        for r in results:
            if r.get("orphelin", False):
                all_orphelins.append(r)
            else:
                all_eclate.append(r)

    df_eclate = pd.DataFrame(all_eclate)
    pct_orph = len(all_orphelins) / total * 100 if total > 0 else 0.0

    log.info(
        "Éclatement : %d → %d lignes (×%.1f), %d orphelins (%.1f %%)",
        total, len(df_eclate),
        len(df_eclate) / total if total else 0,
        len(all_orphelins), pct_orph,
    )

    if pct_orph >= QG2_SEUIL_ORPHELINS_ECLATE * 100:
        log.warning(
            "QG2 WARN : taux d'orphelins éclatement %.1f %% ≥ seuil %.0f %%",
            pct_orph, QG2_SEUIL_ORPHELINS_ECLATE * 100,
        )
    else:
        log.info("QG2 PASS : orphelins éclatement %.2f %%", pct_orph)

    # Restreindre aux années pipeline et nettoyage dtypes
    df_eclate = df_eclate[df_eclate["annee_horaire"].isin(ANNEES_PIPELINE)].copy()
    for col in ["num_dossier", "numero_train", "pax_1c", "pax_2c"]:
        if col in df_eclate.columns:
            df_eclate[col] = pd.to_numeric(df_eclate[col], errors="coerce").astype("Int64")
    if "orphelin" in df_eclate.columns:
        df_eclate = df_eclate.drop(columns=["orphelin"])

    return df_eclate


# ---------------------------------------------------------------------------
# Étape 3 — Agrégation au grain ML
# ---------------------------------------------------------------------------

def _aggreger(df_eclate: pd.DataFrame) -> pd.DataFrame:
    """Agrège les tronçons éclatés au grain ML et calcule les 8 features resa_*."""
    df = df_eclate.copy()
    df["flag_scolaire"]      = df.apply(lambda r: is_scolaire(r.get("nom_groupe"), r.get("partenaire")), axis=1)
    df["flag_tour_operator"] = df["partenaire"].apply(is_tour_operator)
    df["pax_2c_num"]         = pd.to_numeric(df["pax_2c"], errors="coerce").fillna(0)

    grain_key = ["date_voyage_d", "numero_train", "troncon_depart", "troncon_arrivee", "annee_horaire"]

    # Agrégations de base
    base = df.groupby(grain_key).agg(
        resa_pax_2c_J_minus_1            =("pax_2c_num", "sum"),
        resa_n_dossiers_J_minus_1        =("num_dossier", "nunique"),
        resa_max_groupe_2c_J_minus_1     =("pax_2c_num", "max"),
        resa_n_pays_distincts_J_minus_1  =("pays", "nunique"),
        resa_n_langues_distinctes_J_minus_1=("langue", "nunique"),
    ).reset_index()

    # Parts scolaire et tour-opérateur (join séparé pour lisibilité)
    sco = (
        df[df.flag_scolaire]
        .groupby(grain_key)["pax_2c_num"].sum()
        .reset_index(name="pax_scolaire")
    )
    top = (
        df[df.flag_tour_operator]
        .groupby(grain_key)["pax_2c_num"].sum()
        .reset_index(name="pax_tour_op")
    )

    grain = base.merge(sco, on=grain_key, how="left").merge(top, on=grain_key, how="left")
    grain["pax_scolaire"]  = grain["pax_scolaire"].fillna(0)
    grain["pax_tour_op"]   = grain["pax_tour_op"].fillna(0)

    total = grain["resa_pax_2c_J_minus_1"]
    grain["resa_part_scolaire_J_minus_1"]      = (grain["pax_scolaire"] / total.replace(0, pd.NA)).fillna(0)
    grain["resa_part_tour_operator_J_minus_1"] = (grain["pax_tour_op"]  / total.replace(0, pd.NA)).fillna(0)
    grain["resa_has_resa_J_minus_1"]           = True  # sera False après imputation

    grain = grain.drop(columns=["pax_scolaire", "pax_tour_op"])

    log.info("Grain ML agrégé : %d cellules (date × train × tronçon)", len(grain))
    return grain


# ---------------------------------------------------------------------------
# Étape 4 — Jointure et imputation
# ---------------------------------------------------------------------------

def _joindre_et_imputer(df_ml: pd.DataFrame, grain: pd.DataFrame) -> pd.DataFrame:
    """Left-join ml_dataset ← grain réservations, puis impute les cellules sans résa."""
    resa_cols = [
        "resa_pax_2c_J_minus_1",
        "resa_n_dossiers_J_minus_1",
        "resa_max_groupe_2c_J_minus_1",
        "resa_part_scolaire_J_minus_1",
        "resa_part_tour_operator_J_minus_1",
        "resa_n_pays_distincts_J_minus_1",
        "resa_n_langues_distinctes_J_minus_1",
        "resa_has_resa_J_minus_1",
    ]
    join_key = [ML_DATE_COL, ML_TRAIN_COL, ML_DEP_COL, ML_ARR_COL]

    # Aligner les clés de jointure (renommage côté grain uniquement)
    grain_join = grain.rename(columns={
        "date_voyage_d":   ML_DATE_COL,
        "numero_train":    ML_TRAIN_COL,
        "troncon_depart":  ML_DEP_COL,
        "troncon_arrivee": ML_ARR_COL,
    })

    # Normalisation in-place (df_ml non réutilisé après cet appel — pas de copy nécessaire)
    df_ml[ML_DATE_COL] = pd.to_datetime(df_ml[ML_DATE_COL]).dt.normalize()

    # Extraction légère pour QG3 (5 colonnes vs 218) avant libération de df_ml
    df_ml_qg3 = df_ml[[ML_AH_COL] + join_key].copy() if ML_AH_COL in df_ml.columns else None

    # Sélectionner uniquement les colonnes nécessaires côté grain pour le merge
    grain_for_merge = grain_join[[c for c in join_key + resa_cols if c in grain_join.columns]]
    enrichi = df_ml.merge(grain_for_merge, on=join_key, how="left")
    del df_ml  # libère le dataframe 218-cols avant QG3 et imputation

    # QG3 — taux d'orphelins jointure par année horaire (si les colonnes sont disponibles)
    if df_ml_qg3 is not None and "annee_horaire" in grain_join.columns:
        for ah in ["H22", "H23", "H24"]:
            grain_ah = grain_join[grain_join["annee_horaire"] == ah]
            if len(grain_ah) == 0:
                continue
            ml_ah = df_ml_qg3[df_ml_qg3[ML_AH_COL] == ah]
            m = grain_ah[join_key].merge(ml_ah[join_key], on=join_key, how="left", indicator=True)
            n_orph = (m["_merge"] == "left_only").sum()
            pct = n_orph / len(grain_ah) * 100
            if ah == "H22":
                log.info(
                    "QG3 %s : %.1f %% orphelins (couverture partielle F+E — ADR-035 §2.7)", ah, pct
                )
            elif pct >= QG3_SEUIL_ORPHELINS_JOINT * 100:
                log.warning(
                    "QG3 WARN %s : %.1f %% orphelins ≥ seuil %.0f %%",
                    ah, pct, QG3_SEUIL_ORPHELINS_JOINT * 100,
                )
            else:
                log.info("QG3 PASS %s : %.1f %% orphelins", ah, pct)

    # Imputation 0 / False — cast explicite avant fillna pour éviter le FutureWarning pandas 2.x
    numeric_resa = [c for c in resa_cols if c != "resa_has_resa_J_minus_1"]
    for col in numeric_resa:
        enrichi[col] = pd.to_numeric(enrichi[col], errors="coerce").fillna(0)
    enrichi["resa_has_resa_J_minus_1"] = enrichi["resa_has_resa_J_minus_1"].astype(object).where(
        enrichi["resa_has_resa_J_minus_1"].notna(), other=False
    ).astype(bool)

    # Types finaux
    for col in ["resa_pax_2c_J_minus_1", "resa_n_dossiers_J_minus_1",
                "resa_max_groupe_2c_J_minus_1", "resa_n_pays_distincts_J_minus_1",
                "resa_n_langues_distinctes_J_minus_1"]:
        enrichi[col] = enrichi[col].astype("int32")
    for col in ["resa_part_scolaire_J_minus_1", "resa_part_tour_operator_J_minus_1"]:
        enrichi[col] = enrichi[col].astype("float32")
    enrichi["resa_has_resa_J_minus_1"] = enrichi["resa_has_resa_J_minus_1"].astype(bool)

    n_avec_resa = enrichi["resa_has_resa_J_minus_1"].sum()
    log.info(
        "Cellules ml_dataset enrichies avec résa : %d / %d (%.2f %%)",
        n_avec_resa, len(enrichi), n_avec_resa / len(enrichi) * 100,
    )
    return enrichi


# ---------------------------------------------------------------------------
# API publique — réutilisée par build_ml_dataset.py (inline)
# ---------------------------------------------------------------------------

def enrich_with_reservations(df_ml: pd.DataFrame) -> pd.DataFrame:
    """Applique les 4 étapes ResSys et retourne le df enrichi avec les 8 features resa_*.

    Utilisé en inline par build_ml_dataset.py pour éviter un stage intermédiaire.
    Les resa_* sont ajoutées en fin de DataFrame ; l'ordre canonique est géré par
    l'appelant (insertion après simba_source_arrivee).
    """
    log.info("=== enrich_with_reservations (inline) ===")
    log.info("Chargement réservations de groupes ResSys …")
    df_abg = _charger_reservations()
    log.info("Éclatement multi-tronçons …")
    df_eclate = _eclater(df_abg, df_ml)
    log.info("Agrégation au grain ML …")
    grain = _aggreger(df_eclate)
    log.info("Jointure et imputation …")
    return _joindre_et_imputer(df_ml, grain)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== stage_10 : add_reservations_to_raw_stacked ===")

    log.info("Chargement stage_09_simba …")
    df_ml = read_stage(STAGE_09_SIMBA)
    log.info("  %d lignes, %d colonnes", len(df_ml), df_ml.shape[1])

    log.info("Chargement réservations de groupes ResSys …")
    df_abg = _charger_reservations()

    log.info("Éclatement multi-tronçons (topologie year-specific) …")
    df_eclate = _eclater(df_abg, df_ml)

    log.info("Agrégation au grain ML …")
    grain = _aggreger(df_eclate)

    log.info("Jointure et imputation …")
    enrichi = _joindre_et_imputer(df_ml, grain)

    log.info("Persistance → stage_10_reservations …")
    write_stage(enrichi, STAGE_10_RESERVATIONS, write_csv=WRITE_CSV)
    log.info("=== stage_10 terminé ===")


if __name__ == "__main__":
    main()
