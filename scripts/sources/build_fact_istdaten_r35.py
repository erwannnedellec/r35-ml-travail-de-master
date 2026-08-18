"""
build_fact_istdaten_r35.py
===========================
Construit la table de fait des courses R35 réelles depuis les données ISTDATEN.

Rôle dans le pipeline
---------------------
Table de fait brute, grain fin (date × course × arrêt). Sert à deux usages :
  1. Calcul du taux de comptage effectif APC (notebook 02, section 7) :
     croisement avec stage_01 sur (date, numero_train).
  2. Alimentation de build_istdaten_ponctualite.py pour les agrégats
     journaliers de ponctualité R35.

Filtre opérateur et ligne
-------------------------
  BETREIBER_ABK == "MVR-cev"
  LINIEN_TEXT   ∈ {"R", "R35"}

"R" est utilisé jusqu'en septembre 2023 inclus.
"R35" remplace "R" à partir d'octobre 2023 lors d'un changement de désignation.
Les valeurs "ZUG" et "PE" (désignations internes techniques) sont exclues.

Pattern mémoire
---------------
Pour éviter de charger 19 M lignes en RAM, chaque fichier mensuel est filtré
et sérialisé en parquet intermédiaire dans data/external/istdaten/parquet_tmp/.
L'ensemble est ensuite lu en un seul appel pd.read_parquet(dossier).

Inputs
------
  data/external/istdaten/istdaten_*.csv  (filtrés lors de l'extraction initiale)
  data/dimension/dim_gare.parquet        (assertion BPUICs valides)

Output
------
  data/processed/fact_istdaten_r35.parquet

    Grain     : date × numero_train × bpuic
    Colonnes  : voir schéma ci-dessous

Usage
-----
    python scripts/build_fact_istdaten_r35.py
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    DIM_GARE,
    ISTDATEN_CLEAN,
    ISTDATEN_DIR,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Valeurs LINIEN_TEXT correspondant à la R35 selon la période
LINIEN_TEXT_R35: frozenset[str] = frozenset({"R", "R35"})

# Format attendu pour BETRIEBSTAG (assertion qualité)
REGEX_BETRIEBSTAG: str = r"^\d{2}\.\d{2}\.\d{4}$"

# Seuils pour le filtre des statuts "réels" (calcul des retards)
STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

# Seuil de plausibilité des retards.
# Les retards très négatifs (< -3600s) sont des artefacts day-flip : pour les
# trains circulant après minuit, ABFAHRTSZEIT porte la date J+1 tandis que
# AB_PROGNOSE porte la date J, produisant un retard calculé de ≈ -86400s.
# On nullifie ces valeurs à la source pour protéger tous les consommateurs aval.
# Les retards très positifs (> 7200s, ~2h) sont conservés : ils correspondent
# à de vrais incidents (neige, panne) observés sur le réseau.
RETARD_NEGATIF_ABERRANT_SEC: int = -3600

# Répertoire des parquets intermédiaires (nettoyé après usage)
TMP_DIR: Path = ISTDATEN_DIR / "parquet_tmp_r35"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Étape 1 — Filtrage et parquets intermédiaires par fichier mensuel
# ---------------------------------------------------------------------------


def _extraire_numero_train(fahrt_bezeichner: "pd.Series[str]") -> "pd.Series[object]":
    """Extrait le numéro de train depuis FAHRT_BEZEICHNER.

    Le format est '85:42:NNNN:000'. Le troisième segment (index 2) contient
    le numéro de train, correspondant directement à la colonne `numero_train`
    des données APC.

    Args:
        fahrt_bezeichner: Série de chaînes au format UIC FAHRT_BEZEICHNER.

    Returns:
        Série d'entiers (Int64) avec le numéro de train extrait.
    """
    return (
        fahrt_bezeichner.str.split(":", expand=False)
        .str[2]
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )


def _calculer_retard_sec(
    reel: pd.Series,
    horaire: pd.Series,
    statut: pd.Series,
) -> pd.Series:
    """Calcule le retard en secondes entre l'heure réelle et l'heure théorique.

    Le retard est défini comme (reel - horaire).total_seconds(). Il est mis à
    NaN si le statut n'est pas REAL ou GESCHAETZT, garantissant qu'on ne
    calcule des retards que sur des données réellement observées.

    Args:
        reel: Série datetime des heures réelles (AN/AB_PROGNOSE).
        horaire: Série datetime des heures théoriques (ANKUNFTS/ABFAHRTSZEIT).
        statut: Série catégorielle des statuts de prévision.

    Returns:
        Série float64 du retard en secondes, NaN si non applicable.
    """
    retard = (reel - horaire).dt.total_seconds()
    return retard.where(statut.isin(STATUTS_REELS))


def filtrer_et_sauvegarder_csv(csv_path: Path, tmp_dir: Path) -> int:
    """Filtre un CSV mensuel sur les courses R35 et sauvegarde en parquet.

    Args:
        csv_path: Chemin du fichier CSV mensuel istdaten.
        tmp_dir: Répertoire où écrire le parquet intermédiaire.

    Returns:
        Nombre de lignes R35 trouvées dans ce fichier.
    """
    # Colonnes du schéma historique (21 champs). À partir d'oct. 2025, un 22ème
    # champ SLOID a été ajouté par l'OFT. On sélectionne explicitement les 21
    # colonnes connues pour être robuste aux deux formats.
    COLS_SCHEMA = [
        "BETRIEBSTAG", "FAHRT_BEZEICHNER", "BETREIBER_ID", "BETREIBER_ABK",
        "BETREIBER_NAME", "PRODUKT_ID", "LINIEN_ID", "LINIEN_TEXT", "UMLAUF_ID",
        "VERKEHRSMITTEL_TEXT", "ZUSATZFAHRT_TF", "FAELLT_AUS_TF", "BPUIC",
        "HALTESTELLEN_NAME", "ANKUNFTSZEIT", "AN_PROGNOSE", "AN_PROGNOSE_STATUS",
        "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS", "DURCHFAHRT_TF",
    ]
    _read_kwargs = dict(
        sep=";",
        low_memory=False,
        usecols=COLS_SCHEMA,
        dtype={
            "BETREIBER_ABK": "category",
            "LINIEN_TEXT": "category",
            "AN_PROGNOSE_STATUS": "category",
            "AB_PROGNOSE_STATUS": "category",
            "FAELLT_AUS_TF": str,
            "ZUSATZFAHRT_TF": str,
        },
    )
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", **_read_kwargs)
    except UnicodeDecodeError:
        # Certains fichiers 2018 sont encodés en latin-1 (ex. istdaten_2018-11.csv)
        df = pd.read_csv(csv_path, encoding="latin-1", **_read_kwargs)
        log.warning("Encodage latin-1 utilisé pour %s", csv_path.name)

    # Assertion format de date — détecte les changements de format source
    echantillon = df["BETRIEBSTAG"].dropna().head(100)
    assert echantillon.str.match(REGEX_BETRIEBSTAG).all(), (
        f"Format BETRIEBSTAG inattendu dans {csv_path.name} : "
        f"exemples = {echantillon.unique()[:3].tolist()}"
    )

    # Filtre R35
    masque = (
        (df["BETREIBER_ABK"] == "MVR-cev")
        & (df["LINIEN_TEXT"].isin(LINIEN_TEXT_R35))
    )
    df_r35 = df[masque].copy()

    if df_r35.empty:
        return 0

    # Parsing des dates et heures
    df_r35["date"] = pd.to_datetime(
        df_r35["BETRIEBSTAG"], format="%d.%m.%Y"
    ).dt.date

    for col_dt, col_src, fmt in [
        ("horaire_arrivee", "ANKUNFTSZEIT", "%d.%m.%Y %H:%M"),
        ("horaire_depart", "ABFAHRTSZEIT", "%d.%m.%Y %H:%M"),
        ("reel_arrivee", "AN_PROGNOSE", "%d.%m.%Y %H:%M:%S"),
        ("reel_depart", "AB_PROGNOSE", "%d.%m.%Y %H:%M:%S"),
    ]:
        df_r35[col_dt] = pd.to_datetime(
            df_r35[col_src], format=fmt, errors="coerce"
        )

    # Extraction numéro de train
    df_r35["numero_train"] = _extraire_numero_train(df_r35["FAHRT_BEZEICHNER"])

    # Calcul des retards
    df_r35["retard_arrivee_sec"] = _calculer_retard_sec(
        df_r35["reel_arrivee"],
        df_r35["horaire_arrivee"],
        df_r35["AN_PROGNOSE_STATUS"],
    )
    df_r35["retard_depart_sec"] = _calculer_retard_sec(
        df_r35["reel_depart"],
        df_r35["horaire_depart"],
        df_r35["AB_PROGNOSE_STATUS"],
    )

    # Nullification des artefacts day-flip (retard très négatif ≈ -86400s)
    df_r35.loc[
        df_r35["retard_arrivee_sec"] < RETARD_NEGATIF_ABERRANT_SEC, "retard_arrivee_sec"
    ] = float("nan")
    df_r35.loc[
        df_r35["retard_depart_sec"] < RETARD_NEGATIF_ABERRANT_SEC, "retard_depart_sec"
    ] = float("nan")

    # Booléens (stockés comme strings "true"/"false" dans les CSV)
    df_r35["is_annule"] = df_r35["FAELLT_AUS_TF"].str.lower() == "true"
    df_r35["is_supplementaire"] = df_r35["ZUSATZFAHRT_TF"].str.lower() == "true"

    # Sélection et renommage final
    resultat = df_r35.rename(columns={
        "BPUIC": "bpuic",
        "HALTESTELLEN_NAME": "haltestellen_name",
        "AN_PROGNOSE_STATUS": "statut_arrivee",
        "AB_PROGNOSE_STATUS": "statut_depart",
    })[
        [
            "date", "numero_train", "bpuic", "haltestellen_name",
            "horaire_arrivee", "horaire_depart",
            "reel_arrivee", "reel_depart",
            "statut_arrivee", "statut_depart",
            "retard_arrivee_sec", "retard_depart_sec",
            "is_annule", "is_supplementaire",
        ]
    ]

    # Écriture parquet intermédiaire
    parquet_out = tmp_dir / f"{csv_path.stem}.parquet"
    resultat.to_parquet(parquet_out, index=False)
    return len(resultat)


# ---------------------------------------------------------------------------
# Étape 2 — Consolidation et validation
# ---------------------------------------------------------------------------


def consolider_et_valider(tmp_dir: Path, bpuics_r35: set[int]) -> pd.DataFrame:
    """Lit tous les parquets intermédiaires et valide la cohérence.

    Args:
        tmp_dir: Répertoire contenant les parquets intermédiaires.
        bpuics_r35: Ensemble des BPUICs attendus (depuis dim_gare).

    Returns:
        DataFrame consolidé et validé.

    Raises:
        AssertionError: Si des BPUICs inattendus sont trouvés.
    """
    df = pd.read_parquet(tmp_dir)

    # Assertion : tous les BPUICs R35 ISTDATEN sont dans dim_gare
    bpuics_trouves = set(df["bpuic"].dropna().astype(int).unique())
    inattendus = bpuics_trouves - bpuics_r35
    assert not inattendus, (
        f"{len(inattendus)} BPUICs ISTDATEN hors dim_gare R35 : {sorted(inattendus)[:10]}\n"
        "Vérifier le filtre LINIEN_TEXT ou dim_gare."
    )

    n_total = len(df)
    n_annules = df["is_annule"].sum()
    n_supplementaires = df["is_supplementaire"].sum()
    n_real_depart = (df["statut_depart"].isin({"REAL", "GESCHAETZT"})).sum()

    log.info("Consolidation : %d lignes au total", n_total)
    log.info("  Annulées       : %d (%.1f%%)", n_annules, 100 * n_annules / n_total)
    log.info("  Supplémentaires: %d (%.1f%%)", n_supplementaires, 100 * n_supplementaires / n_total)
    log.info("  Statut départ REAL/GESCHAETZT : %d (%.1f%%)", n_real_depart, 100 * n_real_depart / n_total)

    return df


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def construire_fact_istdaten_r35() -> None:
    """Orchestre le filtrage, la consolidation et l'écriture du parquet final."""
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")

    # Chargement de dim_gare pour l'assertion de BPUICs
    gares_r35 = pd.read_parquet(DIM_GARE, columns=["bpuic"])
    bpuics_r35 = set(gares_r35["bpuic"].astype(int).unique())
    log.info("%d BPUICs R35 attendus depuis dim_gare", len(bpuics_r35))

    # Création et nettoyage du répertoire temporaire
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True)

    # Filtrage fichier par fichier
    total_lignes = 0
    for i, fich in enumerate(fichiers, 1):
        n = filtrer_et_sauvegarder_csv(fich, TMP_DIR)
        total_lignes += n
        log.info("[%02d/%02d] %s → %d lignes R35", i, len(fichiers), fich.name, n)

    log.info("Total lignes R35 extraites : %d", total_lignes)

    # Consolidation et validation
    df = consolider_et_valider(TMP_DIR, bpuics_r35)

    # Écriture atomique
    ISTDATEN_CLEAN.parent.mkdir(parents=True, exist_ok=True)
    tmp = ISTDATEN_CLEAN.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False)
        tmp.rename(ISTDATEN_CLEAN)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", ISTDATEN_CLEAN)
    log.info("  %d lignes × %d colonnes", df.shape[0], df.shape[1])
    log.info("  Période : %s → %s", df["date"].min(), df["date"].max())
    log.info(
        "  Courses uniques : %d  |  Dates uniques : %d",
        df["numero_train"].nunique(),
        df["date"].nunique(),
    )

    # Nettoyage du répertoire temporaire
    shutil.rmtree(TMP_DIR)
    log.info("Répertoire temporaire supprimé : %s", TMP_DIR)


if __name__ == "__main__":
    construire_fact_istdaten_r35()
