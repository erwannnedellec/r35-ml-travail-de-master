"""
build_fact_simba_r35.py
=======================
Produit deux tables propres à partir des CSV bruts SIMBA FQkal :

  1. ``simba_clean.parquet``
     Grain fin : (millésime × train × OD × titre × classe).
     Résultat de la sélection R35 (TU=42), normalisation des colonnes,
     catégorisation des titres tarifaires et validation des invariants.

  2. ``simba_expansion_troncons.parquet``
     Grain étendu : (millésime × train × tronçon × titre × classe).
     Chaque paire OD est développée en N lignes, une par tronçon R35
     traversé (montée en A → descente en B traverse tous les tronçons A-B).

Règle anti-leakage (ADR-026)
---------------------------
Ce script produit des tables au grain millésime, sans jointure avec les
données APC. Le mapping millésime → année horaire (lag N-1) est appliqué
dans le stage pipeline (``add_simba_to_raw_stacked.py``).

Gestion de la transition topologique GIL → VVVI
-----------------------------------------------
La gare Gilamont (GIL) est active jusqu'au millésime SIMBA 2022 inclus.
Elle est remplacée par Vevey Vignerons (VVVI) à partir de 2023.
Ce script normalise GIL → VVVI dans les colonnes gare_montee/gare_descente
afin que les tronçons produits utilisent les codes de gare courants du
pipeline APC (VVVI), facilitant la jointure aval.

Inputs
------
  data/external/simba/zuginout_MOB_2022.csv
  data/external/simba/zuginout_MOB_2023.csv
  data/external/simba/zuginout_MOB_2024.csv
  data/external/simba/zuginout_MOB_2025.csv

Outputs
-------
  data/processed/sources/simba_clean.parquet
  data/processed/sources/simba_expansion_troncons.parquet

Usage
-----
    python scripts/sources/build_fact_simba_r35.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import SIMBA_DIR, SIMBA_CLEAN, SIMBA_EXPANSION  # noqa: E402
from pipeline.io import write_stage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de filtrage R35
# ---------------------------------------------------------------------------

HO_TUCODE_R35: int = 42
DEBICODE_R35: int = 9190
CKV_R35: str = "42"   # normalisé en string (float en 2022, string en 2023+)
OFFERTCODES_R35: frozenset[str] = frozenset({"7730", "7730,7731"})
MILLESIMES: list[int] = [2022, 2023, 2024, 2025]

# ---------------------------------------------------------------------------
# Topologie R35 — ordre ordinal des gares (bas → haut)
# ---------------------------------------------------------------------------

# GIL (Gilamont, actif jusqu'à 2022) et VVVI (Vevey Vignerons, actif depuis 2023)
# occupent la même position physique. GIL est normalisé en VVVI avant l'expansion.
STATION_ORDER: dict[str, int] = {
    "VV":   0,
    "VVVI": 2,   # Vevey Vignerons (ex-GIL jusqu'à 2022, normalisé ici)
    "HTV":  4,
    "CHTV": 5,
    "STLE": 6,
    "STLV": 7,
    "CHIZ": 8,
    "CHBL": 9,
    "BLON": 10,
    "PRLZ": 11,
    "TUS":  12,
    "CHEV": 13,
    "BCHX": 14,
    "FAY":  15,
    "OND":  16,
    "LAL":  17,
    "PLEI": 18,
}

# GIL normalisé en VVVI dans les colonnes gare
GARE_NORMALISATION: dict[str, str] = {"GIL": "VVVI"}

STATIONS_SORTED: list[str] = sorted(STATION_ORDER, key=STATION_ORDER.__getitem__)
TRONCONS: list[tuple[str, str]] = [
    (STATIONS_SORTED[i], STATIONS_SORTED[i + 1])
    for i in range(len(STATIONS_SORTED) - 1)
]

# ---------------------------------------------------------------------------
# Mapping colonnes brutes → noms normalisés
# ---------------------------------------------------------------------------

COLONNES_RENOMMAGE: dict[str, str] = {
    "ho_vmnummer":                   "simba_numero_train",
    "zug_in_haltestelle_kuerzel":    "simba_gare_montee",
    "zug_in_haltestelle_name":       "simba_gare_montee_nom",
    "zug_out_haltestelle_kuerzel":   "simba_gare_descente",
    "zug_out_haltestelle_name":      "simba_gare_descente_nom",
    "quell_kuerzel":                 "simba_origine_voyage",
    "quell_name":                    "simba_origine_voyage_nom",
    "ziel_kuerzel":                  "simba_destination_voyage",
    "ziel_name":                     "simba_destination_voyage_nom",
    "faw_art":                       "simba_titre_code",
    "faw_bezeichnung":               "simba_titre_nom",
    "faw_klasse":                    "simba_titre_classe_faw",
    "abteil_klasse":                 "simba_classe",
    "zubringer_tucode":              "simba_corresp_amont_tu",
    "zubringer_vmnummer":            "simba_corresp_amont_train",
    "anschluss_tucode":              "simba_corresp_aval_tu",
    "anschluss_vmnummer":            "simba_corresp_aval_train",
    "reisende_dwv":                  "simba_voyageurs_dwv",
    "reisende_dnwv":                 "simba_voyageurs_dnwv",
    "reisende_dtv":                  "simba_voyageurs_dtv",
}

# Colonnes à conserver (les colonnes techniques de filtre sont supprimées après validation)
COLONNES_SUPPRIMER: list[str] = [
    "ho_tucode",
    "meta_lauf_liste",
    "debicode_liste",
    "ckv_liste",
    "offertcode_liste",
]

# ---------------------------------------------------------------------------
# Familles tarifaires
# ---------------------------------------------------------------------------

def classifier_titre_famille(titre_nom: pd.Series) -> pd.Series:
    """Regroupe les codes faw_bezeichnung en familles tarifaires métier.

    Args:
        titre_nom: Série pandas contenant les libellés de titre (faw_bezeichnung).

    Returns:
        Série pandas avec les familles tarifaires ('GA', 'Mobilis Riviera', etc.).
    """
    b = titre_nom.str.lower().fillna("")
    famille = pd.Series("Autre", index=titre_nom.index, dtype="string")
    famille = famille.where(~b.str.contains("mobilis"), "Mobilis Riviera")
    famille = famille.where(
        ~(b.str.startswith("ga") | b.str.contains(r"\bga\b") | b.str.contains("ga\+")),
        "GA",
    )
    famille = famille.where(~(b.str.contains("ht") & b.str.contains("ef")), "Billet HTA")
    famille = famille.where(~b.str.contains("spar"), "Spar / promotionnel")
    famille = famille.where(
        ~(b.str.contains("kind") | b.str.contains("jugend")), "Jeunes"
    )
    famille = famille.where(
        ~(b.str.contains("abo") | b.str.contains("abonn")), "Abonnement"
    )
    famille = famille.where(
        ~(b.str.contains("militär") | b.str.contains("milit")), "Militaire"
    )
    # Mobilis a la priorité sur GA (certains libellés contiennent les deux)
    famille = famille.where(~b.str.contains("mobilis"), "Mobilis Riviera")
    return famille


# ---------------------------------------------------------------------------
# Chargement et filtrage
# ---------------------------------------------------------------------------

def charger_millesime(millesime: int) -> pd.DataFrame:
    """Charge un fichier CSV SIMBA et filtre les lignes R35 (TU=42).

    Args:
        millesime: Année du fichier SIMBA (ex. 2022).

    Returns:
        DataFrame filtré sur TU=42 avec colonne simba_millesime ajoutée.

    Raises:
        FileNotFoundError: Si le fichier CSV est absent.
        AssertionError: Si aucune ligne R35 n'est trouvée dans le fichier.
    """
    chemin = SIMBA_DIR / f"zuginout_MOB_{millesime}.csv"
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier SIMBA introuvable : {chemin}")

    df = pd.read_csv(chemin, sep=";", low_memory=False)
    log.info("Millésime %d : %d lignes brutes chargées", millesime, len(df))

    df_r35 = df[df["ho_tucode"] == HO_TUCODE_R35].copy()
    assert len(df_r35) > 0, f"Aucune ligne R35 (TU=42) dans le fichier {millesime}"

    df_r35["simba_millesime"] = millesime
    log.info("Millésime %d : %d lignes R35 (TU=42)", millesime, len(df_r35))
    return df_r35


def valider_filtres_secondaires(df: pd.DataFrame) -> None:
    """Vérifie que les identifiants secondaires R35 sont cohérents avec TU=42.

    Args:
        df: DataFrame filtré sur TU=42, avant normalisation.

    Raises:
        AssertionError: Si un identifiant secondaire est incohérent.
    """
    offertcodes_obs = set(df["offertcode_liste"].dropna().astype(str).unique())
    inattendus = offertcodes_obs - OFFERTCODES_R35 - {""}
    assert not inattendus, (
        f"Offertcodes inattendus pour TU=42 : {inattendus}. "
        "Vérifier que le périmètre R35 n'a pas changé."
    )

    # Normalisation en string pour comparer malgré le changement de type (float 2022 / str 2023+)
    ckv_obs = {str(v).rstrip(".0") if str(v).endswith(".0") else str(v)
               for v in df["ckv_liste"].dropna().unique()}
    ckv_inattendus = ckv_obs - {CKV_R35, ""}
    assert not ckv_inattendus, f"CKV inattendus pour TU=42 : {ckv_inattendus}"

    log.info("Identifiants secondaires R35 validés (offertcode, ckv).")


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes brutes vers les conventions du projet.

    Args:
        df: DataFrame brut filtré TU=42.

    Returns:
        DataFrame avec colonnes renommées, tri de colonnes propre.
    """
    n_avant = len(df)
    df = df.rename(columns=COLONNES_RENOMMAGE)
    df = df.drop(columns=COLONNES_SUPPRIMER, errors="ignore")

    assert len(df) == n_avant, "Perte de lignes lors du renommage — anomalie inattendue"
    return df


def normaliser_gares(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les codes de gare : GIL → VVVI (transition topologique H22 → H23).

    Args:
        df: DataFrame avec colonnes simba_gare_montee et simba_gare_descente.

    Returns:
        DataFrame avec codes de gare normalisés.
    """
    df = df.copy()
    df["simba_gare_montee"] = (
        df["simba_gare_montee"].replace(GARE_NORMALISATION).astype("string")
    )
    df["simba_gare_descente"] = (
        df["simba_gare_descente"].replace(GARE_NORMALISATION).astype("string")
    )
    n_gil = (df["simba_gare_montee"] == "VVVI").sum() + (df["simba_gare_descente"] == "VVVI").sum()
    log.info("Normalisation GIL→VVVI : %d occurrences de VVVI dans le résultat", n_gil)
    return df


def ajouter_famille_tarifaire(df: pd.DataFrame) -> pd.DataFrame:
    """Crée la colonne simba_titre_famille par regroupement des libellés FAW.

    Args:
        df: DataFrame avec colonne simba_titre_nom.

    Returns:
        DataFrame enrichi de la colonne simba_titre_famille.
    """
    df = df.copy()
    df["simba_titre_famille"] = classifier_titre_famille(df["simba_titre_nom"])
    repartition = df["simba_titre_famille"].value_counts()
    log.info("Répartition familles tarifaires :\n%s", repartition.to_string())
    return df


# ---------------------------------------------------------------------------
# Validation finale
# ---------------------------------------------------------------------------

def valider_gares_connues(df: pd.DataFrame) -> None:
    """Vérifie que toutes les gares R35 dans SIMBA sont dans STATION_ORDER.

    Args:
        df: DataFrame normalisé avec simba_gare_montee et simba_gare_descente.

    Raises:
        AssertionError: Si des gares inconnues sont présentes.
    """
    gares_connues = set(STATION_ORDER.keys())
    montee_inconnues = set(df["simba_gare_montee"].dropna().unique()) - gares_connues
    descente_inconnues = set(df["simba_gare_descente"].dropna().unique()) - gares_connues

    assert not montee_inconnues, (
        f"Gares de montée inconnues (hors périmètre R35 ou normalisation manquante) : "
        f"{sorted(montee_inconnues)}"
    )
    assert not descente_inconnues, (
        f"Gares de descente inconnues : {sorted(descente_inconnues)}"
    )
    log.info("Toutes les gares SIMBA appartiennent aux 17 gares R35 ✓")


def valider_trains(df: pd.DataFrame) -> None:
    """Vérifie que tous les numéros de train sont dans la plage R35 (1300–1599).

    La plage réelle observée en APC et SIMBA est 1300–1553. La limite haute
    1599 est conservée avec une marge.

    Args:
        df: DataFrame avec simba_numero_train.
    """
    trains = df["simba_numero_train"].dropna().unique()
    hors_plage = [t for t in trains if not (1300 <= t <= 1599)]
    if hors_plage:
        log.warning(
            "%d train(s) hors plage 1300–1599 : %s — vérifier le périmètre TU=42",
            len(hors_plage),
            sorted(hors_plage)[:10],
        )
    else:
        log.info("Tous les trains dans la plage 1300–1599 ✓")


# ---------------------------------------------------------------------------
# Expansion OD → tronçons (vectorisée)
# ---------------------------------------------------------------------------

def construire_table_troncons() -> pd.DataFrame:
    """Construit le référentiel des tronçons R35 avec leurs positions ordinales.

    Returns:
        DataFrame avec colonnes dep, arr, ord_dep, ord_arr.
    """
    troncon_df = pd.DataFrame(TRONCONS, columns=["dep", "arr"])
    troncon_df["ord_dep"] = troncon_df["dep"].map(STATION_ORDER)
    troncon_df["ord_arr"] = troncon_df["arr"].map(STATION_ORDER)
    return troncon_df


def expandre_od_vers_troncons(df_simba: pd.DataFrame) -> pd.DataFrame:
    """Développe les paires OD en tronçons traversés (vectorisé).

    Pour chaque ligne (train, montée A, descente B, ..., DWV), produit N lignes,
    une par tronçon R35 situé entre A et B inclus.

    Les lignes avec gares hors référentiel (NaN dans ord_in/ord_out) sont
    ignorées avec un avertissement.

    Args:
        df_simba: DataFrame simba_clean avec colonnes simba_gare_montee,
            simba_gare_descente, simba_voyageurs_dwv, etc.

    Returns:
        DataFrame au grain (millesime, train, gare_depart, gare_arrivee, ...)
        avec les attributs SIMBA originaux et les volumes DWV/DTV.
    """
    troncon_ref = construire_table_troncons()

    df = df_simba.copy()
    df["ord_in"] = df["simba_gare_montee"].map(STATION_ORDER)
    df["ord_out"] = df["simba_gare_descente"].map(STATION_ORDER)

    n_avant = len(df)
    df = df.dropna(subset=["ord_in", "ord_out"])
    n_apres = len(df)
    if n_avant != n_apres:
        log.warning(
            "%d lignes ignorées (gares hors référentiel) sur %d total",
            n_avant - n_apres, n_avant,
        )

    # Retirer les OD sans déplacement (même gare montée = descente)
    df = df[df["ord_in"] != df["ord_out"]].copy()

    df["ord_min"] = df[["ord_in", "ord_out"]].min(axis=1).astype(int)
    df["ord_max"] = df[["ord_in", "ord_out"]].max(axis=1).astype(int)

    # Jointure croisée puis filtre : garde les tronçons compris dans l'OD
    expanded = df.merge(troncon_ref, how="cross")
    masque = (
        (expanded["ord_dep"] >= expanded["ord_min"])
        & (expanded["ord_arr"] <= expanded["ord_max"])
    )
    expanded = expanded[masque].copy()

    # Renommer les colonnes tronçon vers la convention pipeline
    expanded = expanded.rename(columns={"dep": "gare_depart", "arr": "gare_arrivee"})

    # Supprimer les colonnes ordinales temporaires
    colonnes_temp = ["ord_in", "ord_out", "ord_min", "ord_max", "ord_dep", "ord_arr"]
    expanded = expanded.drop(columns=colonnes_temp)

    facteur = len(expanded) / max(len(df), 1)
    log.info(
        "Expansion OD→tronçons : %d lignes → %d lignes (facteur ×%.2f)",
        len(df), len(expanded), facteur,
    )
    return expanded.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    """Produit simba_clean.parquet et simba_expansion_troncons.parquet."""
    # 1. Chargement des 4 millésimes
    chunks: list[pd.DataFrame] = []
    for millesime in MILLESIMES:
        try:
            df_mil = charger_millesime(millesime)
            chunks.append(df_mil)
        except FileNotFoundError as exc:
            log.warning("Millésime %d ignoré : %s", millesime, exc)

    assert chunks, "Aucun millésime SIMBA chargé — vérifier data/external/simba/"
    df_brut = pd.concat(chunks, ignore_index=True)
    n_total = len(df_brut)
    log.info("Total R35 toutes années : %d lignes", n_total)

    # 2. Validation des filtres secondaires
    valider_filtres_secondaires(df_brut)

    # 3. Normalisation
    df_norm = normaliser_colonnes(df_brut)
    df_norm = normaliser_gares(df_norm)
    df_norm = ajouter_famille_tarifaire(df_norm)

    assert len(df_norm) == n_total, (
        f"Perte de lignes lors de la normalisation : {n_total} → {len(df_norm)}"
    )

    # 4. Validation post-normalisation
    valider_gares_connues(df_norm)
    valider_trains(df_norm)

    # 5. Écriture simba_clean.parquet
    write_stage(df_norm, SIMBA_CLEAN)

    # 6. Expansion OD → tronçons
    df_exp = expandre_od_vers_troncons(df_norm)

    # 7. Écriture simba_expansion_troncons.parquet
    write_stage(df_exp, SIMBA_EXPANSION)

    # Récapitulatif
    print("\n=== Récapitulatif ===")
    print(f"simba_clean        : {len(df_norm):,} lignes, {df_norm.shape[1]} colonnes")
    print(f"simba_expansion    : {len(df_exp):,} lignes, {df_exp.shape[1]} colonnes")
    print(f"Millésimes couverts : {sorted(df_norm['simba_millesime'].unique())}")
    print(f"Trains couverts    : {df_norm['simba_numero_train'].nunique()} trains uniques")
    print(f"Familles tarifaires :\n{df_norm['simba_titre_famille'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
