"""
Produit la table ML-ready à partir de stage_10_reservations (→ ml_dataset).

Cette étape supprime les colonnes qui ne doivent pas entrer dans le modèle :

  Colonnes vides dans les fichiers APC source
    base_groupes_1ere_classe, base_groupes_2eme_classe
    id_code_justification, base_divergence_horaire

  Data leakage ou valeurs peu fiables
    id_code_et, id_code_debiteur, id_code_offre, id_mode_comptage, id_source
    horaire_troncon_tgl         (clé technique des lags, déjà calculés)
    base_tx_equipement_afz_*    (taux dérivés de l'offre, pas disponibles à J-2)
    base_places_disponibles_*   (idem)
    base_passagers_montant/descendants_*  (mesures temps-réel non disponibles à J-2)
    base_tx_occupation_*        (dérivé des targets — leakage direct)

  Colonnes ISTDATEN (ist_*)
    Aucune suppression nécessaire : toutes les ist_* sont construites sur
    des données J-2 (logique opérationnelle, voir ADR-015).
    Elles sont conservées telles quelles.

  Colonnes SIMBA (simba_*)
    simba_voyageurs_dwv_total exclue (cf. ADR-026 — redondance avec lags APC).
    Les 12 proportions simba_part_* sont conservées.

Le stage_10 reste intact pour les analyses ponctuelles et l'audit.

Les deux colonnes d'identifiant de service (horaire_numero_train et
horaire_service_id_complet) sont conservées ensemble dans ml_dataset à des
fins de traçabilité et d'audit. Elles sont exclues des 158 features
canoniques du modèle. horaire_numero_train identifie la course, grain de la
décision de couche 2.

Sources
-------
- data/processed/stage_10_reservations.parquet  (produit par add_reservations_to_raw_stacked.py)
  ↳ les 8 features resa_* (ADR-035) y sont déjà enrichies (stage dédié, en fin de chaîne) ;
    le réordonnancement canonique (resa_* après simba_source_arrivee) est appliqué ici.

Sortie
------
- data/processed/ml_dataset.parquet
- data/processed/ml_dataset.csv
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_10_RESERVATIONS, ML_DATASET  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Périmètre temporel — modèle de référence du mémoire (ADR-027).
# Train + validation : H22+H23. Test OOT : H24.
# H16-H21 exclus : régimes COVID/pré-COVID non représentatifs du contexte de déploiement.
# H25 inclus : ISTDATEN 2025 et événements Riviera 2025 ingérés (cf. ADR-038).
ANNEE_HORAIRE_MIN = "H22"
ANNEE_HORAIRE_MAX = "H25"

# Colonnes a supprimer de la table ML (noms prefixes tels que produits par la pipeline).
# Le parquet source complet reste intact pour les analyses ponctuelles.
COLUMNS_TO_DROP = [
    # Colonnes vides dans les fichiers APC source
    "base_groupes_1ere_classe",
    "base_groupes_2eme_classe",
    "id_code_justification",
    "base_divergence_horaire",
    # Identifiants techniques inutiles pour le modele
    "id_code_et",
    "id_code_debiteur",
    "id_code_offre",
    "id_mode_comptage",
    "id_source",
    # Cles de groupement utilisees pour le calcul des lags (lags deja dans la table)
    "horaire_troncon_tgl",
    "creneau_anchor_30",         # ancrage créneau interne (ADR-044) — non modèle
    # Colonnes APC operationnelles peu fiables ou redondantes
    "base_tx_equipement_afz_1ere_classe",
    "base_tx_equipement_afz_2eme_classe",
    "base_places_disponibles_1ere_classe",
    "base_places_disponibles_2eme_classe",
    "base_passagers_montant_1ere_classe",
    "base_passagers_montant_2eme_classe",
    "base_passagers_descendants_1ere_classe",
    "base_passagers_descendants_2eme_classe",
    # Taux d'occupation fournis par la source : data leakage potentiel (derives des targets)
    "base_tx_occupation_1ere_classe",
    "base_tx_occupation_2eme_classe",
    # Volume SIMBA brut — redondance avec lags APC, corrélation résiduelle inter-millésimes ~0.95 (cf. ADR-026)
    "simba_voyageurs_dwv_total",
]

# Colonne-ancre pour l'insertion des resa_* dans l'ordre canonique.
# Les resa_* sont insérées immédiatement après cette colonne (dernière de stage_09).
_RESA_ANCHOR = "simba_source_arrivee"


def build_ml_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = df[(df["horaire_annee_horaire"] >= ANNEE_HORAIRE_MIN) & (df["horaire_annee_horaire"] <= ANNEE_HORAIRE_MAX)].copy()
    present = [c for c in COLUMNS_TO_DROP if c in df.columns]
    absent = [c for c in COLUMNS_TO_DROP if c not in df.columns]
    ml_df = df.drop(columns=present)
    bool_cols = [c for c in ml_df.columns if ml_df[c].dtype == bool]
    ml_df[bool_cols] = ml_df[bool_cols].astype("int8")
    return ml_df, present, absent


def print_summary(df_in: pd.DataFrame, df_out: pd.DataFrame, dropped: list[str], absent: list[str]) -> None:
    print(f"\nTable source   : {len(df_in):,} lignes, {df_in.shape[1]} colonnes")
    print(f"Filtre {ANNEE_HORAIRE_MIN}–{ANNEE_HORAIRE_MAX} : {len(df_out):,} lignes conservées ({len(df_in)-len(df_out):,} supprimées)")
    print(f"Table ML-ready : {len(df_out):,} lignes, {df_out.shape[1]} colonnes")
    print(f"\n{len(dropped)} colonne(s) supprimees :")
    for col in dropped:
        print(f"  - {col}")
    if absent:
        print(f"\n{len(absent)} colonne(s) absentes de la source (ignorees) :")
        for col in absent:
            print(f"  ? {col}")
    print(f"\nColonnes conservees ({df_out.shape[1]}) :")
    for prefix in ["id_", "target_", "base_", "horaire_", "cal_", "spatial_", "meteo_", "event_", "histo_", "ist_", "vmcv_", "simba_", "resa_"]:
        cols = [c for c in df_out.columns if c.startswith(prefix)]
        if cols:
            print(f"  {prefix:<12} {len(cols):>3} colonne(s)")


def main() -> None:
    df = read_stage(STAGE_10_RESERVATIONS)
    log.info("stage_10 chargé : %d lignes, %d colonnes", len(df), df.shape[1])

    # Réordonnancement canonique : resa_* insérées après _RESA_ANCHOR
    cols = df.columns.tolist()
    resa_cols = [c for c in cols if c.startswith("resa_")]
    non_resa = [c for c in cols if not c.startswith("resa_")]
    if _RESA_ANCHOR in non_resa:
        anchor_idx = non_resa.index(_RESA_ANCHOR)
        cols_ordered = non_resa[: anchor_idx + 1] + resa_cols + non_resa[anchor_idx + 1 :]
        df = df[cols_ordered]
    else:
        log.warning("Colonne-ancre '%s' absente — resa_* conservées en fin de table", _RESA_ANCHOR)

    ml_df, dropped, absent = build_ml_dataset(df)

    write_stage(ml_df, ML_DATASET, write_csv=True)
    print_summary(df, ml_df, dropped, absent)


if __name__ == "__main__":
    main()
