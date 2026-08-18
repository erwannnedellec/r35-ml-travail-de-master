"""
build_istdaten_ponctualite.py
===================================
Agrège les données ISTDATEN en indicateurs journaliers de ponctualité R35
et de connexions ferroviaires à Vevey.

Grain sortie : date (une ligne par date de service)

Sections
--------
  1. R35 ponctualité   — depuis fact_istdaten_r35.parquet
  2. Horaires théoriques — depuis horaires_r35_troncons_jour.parquet
  3. Connexions Vevey  — re-lecture des CSV mensuels ISTDATEN,
                         filtre BPUIC=8501200, LINIEN_TEXT ∈ {S3,S4,S7,RE}

Inputs
------
  data/processed/fact_istdaten_r35.parquet
  data/processed/horaires_r35_troncons_jour.parquet
  data/external/istdaten/istdaten_*.csv

Output
------
  data/processed/dim_ponctualite_istdaten.parquet

    Grain   : date
    Colonnes:
      date
      ist_r35_n_courses_theoriques_j
      ist_r35_n_courses_realisees_j
      ist_r35_n_courses_annulees_j
      ist_r35_taux_realisation_horaire_j
      ist_r35_n_courses_supplementaires_j
      ist_r35_part_courses_supplementaires_j
      ist_r35_pct_dep_ponctuel_60s_j
      ist_r35_pct_dep_ponctuel_180s_j
      ist_r35_pct_dep_ponctuel_300s_j
      ist_r35_retard_dep_moy_sec_j
      ist_vevey_n_arrivees_j
      ist_vevey_n_arrivees_pointe_j
      ist_vevey_n_arrivees_creux_j
      ist_vevey_retard_arr_moy_sec_j
      ist_vevey_pct_arr_ponctuel_180s_j

Usage
-----
    python scripts/sources/build_istdaten_ponctualite.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    ISTDATEN_PONCTUALITE,
    ISTDATEN_CLEAN,
    HORAIRES_CLEAN,
    ISTDATEN_DIR,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATUTS_REELS: frozenset[str] = frozenset({"REAL", "GESCHAETZT"})

# Lignes ferrées servant de correspondance à Vevey (BPUIC 8501200).
# S3/S4/S7 → renommées R3/R4/R7 par SBB dès mi-2022 (transition parallèle).
# RE33 = Regional Express 33 Lausanne–Brig arrêtant à Vevey.
# IR90  = InterRegio 90 Genève-Aéroport–Brig (22 975 passages/an, ≈ RE33).
#         Inclus suite à révision superviseur 2026-05-21 (cf. ADR-023).
# IR    = Désignation générique SBB pour les premiers/derniers trains du jour
#         sur l'axe Genève–Brig (3 236 passages/an), avant renommage en IR90.
#         Concentration 5h-7h et 22h-23h, LINIEN_IDs distincts d'IR90.
# IR95, SN, EC, EXT exclus : < 600 passages/an ou services internationaux
#         sans pertinence pour la correspondance R35 régionale.
LINIEN_FEEDERS_VEVEY: frozenset[str] = frozenset(
    {"S3", "S4", "S7", "RE", "R3", "R4", "R7", "RE33", "IR90", "IR"}
)

# Tranches horaires pointe (heures pleines, début d'heure)
HEURES_POINTE_MATIN: range = range(5, 9)   # 5h–8h inclus
HEURES_POINTE_SOIR: range = range(16, 20)  # 16h–19h inclus
HEURES_CREUX: range = range(9, 16)         # 9h–15h inclus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section 1 — R35 ponctualité (depuis fact_istdaten_r35)
# ---------------------------------------------------------------------------


def _agreger_r35(df_fact: pd.DataFrame) -> pd.DataFrame:
    """Calcule les indicateurs R35 journaliers depuis la table de fait.

    Niveau train : un train est « annulé » si TOUS ses arrêts sont annulés.
    Niveau arrêt : retards calculés sur les seuls statuts REAL/GESCHAETZT.

    Returns:
        DataFrame indexé sur date (Python datetime.date).
    """
    # --- Niveau train ---
    train_flags = (
        df_fact.groupby(["date", "numero_train"])[["is_annule", "is_supplementaire"]]
        .agg(
            train_annule=("is_annule", "all"),
            train_suppl=("is_supplementaire", "any"),
        )
        .reset_index()
    )

    r35_trains = train_flags.groupby("date").agg(
        ist_r35_n_courses_realisees_j=("train_annule", lambda x: (~x).sum()),
        ist_r35_n_courses_annulees_j=("train_annule", "sum"),
        ist_r35_n_courses_supplementaires_j=("train_suppl", "sum"),
    )

    # --- Niveau arrêt (retards) ---
    df_reel = df_fact[df_fact["statut_depart"].isin(STATUTS_REELS)].copy()

    def _pct_ponctuel_symetrique(serie: pd.Series, seuil: int) -> float:
        """Part des observations ponctuelles au seuil (convention symétrique).

        Ponctuel si |retard| <= seuil. Un départ en avance est non-ponctuel :
        les voyageurs en correspondance ratent le train.
        Utilisé pour la ponctualité au DÉPART.
        """
        valid = serie.dropna()
        return float((valid.abs() <= seuil).mean()) if len(valid) > 0 else float("nan")

    r35_stops = df_reel.groupby("date")["retard_depart_sec"].agg(
        ist_r35_pct_dep_ponctuel_60s_j=lambda x: _pct_ponctuel_symetrique(x, 60),
        ist_r35_pct_dep_ponctuel_180s_j=lambda x: _pct_ponctuel_symetrique(x, 180),
        ist_r35_pct_dep_ponctuel_300s_j=lambda x: _pct_ponctuel_symetrique(x, 300),
        ist_r35_retard_dep_moy_sec_j="mean",
    )

    return r35_trains.join(r35_stops, how="outer")


# ---------------------------------------------------------------------------
# Section 2 — Horaires théoriques (depuis horaires_r35_troncons_jour)
# ---------------------------------------------------------------------------


def _charger_n_theoriques() -> pd.Series:
    """Compte les courses théoriques R35 par date depuis les horaires PDF.

    Returns:
        Series[int] indexée sur date (Python datetime.date).
    """
    df = pd.read_parquet(HORAIRES_CLEAN, columns=["date", "numero_train"])
    # Conversion datetime64 → date pour aligner avec fact_istdaten_r35
    df["date"] = df["date"].dt.date
    n_theoriques = (
        df.groupby("date")["numero_train"]
        .nunique()
        .rename("ist_r35_n_courses_theoriques_j")
    )
    return n_theoriques


# ---------------------------------------------------------------------------
# Section 3 — Connexions Vevey (re-lecture des CSV mensuels)
# ---------------------------------------------------------------------------


def _lire_vevey_depuis_csv(csv_path: Path) -> pd.DataFrame:
    """Filtre un CSV mensuel et retourne les arrivées de feeders à Vevey.

    Garde uniquement :
      - BPUIC == 8501200 (Vevey)
      - LINIEN_TEXT ∈ {S3, S4, S7, RE}
      - DURCHFAHRT_TF != true (arrêt effectif, pas transit)
      - FAELLT_AUS_TF != true (service réalisé)
      - ANKUNFTSZEIT non vide (= arrivée enregistrée)

    Returns:
        DataFrame avec colonnes [date, horaire_arrivee, retard_arr_sec,
        statut_arrivee, is_pointe, is_creux].
    """
    # Sélection explicite des 21 colonnes du schéma historique. À partir
    # d'oct. 2025, un 22ème champ SLOID a été ajouté par l'OFT ; usecols
    # garantit la robustesse aux deux formats sans modification du schéma.
    _COLS_VEVEY = [
        "BETRIEBSTAG", "FAHRT_BEZEICHNER", "BETREIBER_ID", "BETREIBER_ABK",
        "BETREIBER_NAME", "PRODUKT_ID", "LINIEN_ID", "LINIEN_TEXT", "UMLAUF_ID",
        "VERKEHRSMITTEL_TEXT", "ZUSATZFAHRT_TF", "FAELLT_AUS_TF", "BPUIC",
        "HALTESTELLEN_NAME", "ANKUNFTSZEIT", "AN_PROGNOSE", "AN_PROGNOSE_STATUS",
        "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS", "DURCHFAHRT_TF",
    ]
    _read_kwargs = dict(
        sep=";",
        low_memory=False,
        usecols=_COLS_VEVEY,
        dtype={
            "LINIEN_TEXT": "category",
            "AN_PROGNOSE_STATUS": "category",
            "FAELLT_AUS_TF": str,
            "DURCHFAHRT_TF": str,
        },
    )
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", **_read_kwargs)
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin-1", **_read_kwargs)
        log.warning("Encodage latin-1 utilisé pour %s", csv_path.name)

    masque = (
        (df["BPUIC"] == 8501200)
        & (df["LINIEN_TEXT"].isin(LINIEN_FEEDERS_VEVEY))
        & (df["DURCHFAHRT_TF"].str.lower() != "true")
        & (df["FAELLT_AUS_TF"].str.lower() != "true")
        & df["ANKUNFTSZEIT"].notna()
    )
    df_v = df[masque].copy()

    if df_v.empty:
        return pd.DataFrame(
            columns=["date", "horaire_arrivee", "retard_arr_sec",
                     "statut_arrivee", "is_pointe", "is_creux"]
        )

    df_v["date"] = pd.to_datetime(
        df_v["BETRIEBSTAG"], format="%d.%m.%Y"
    ).dt.date

    df_v["horaire_arrivee"] = pd.to_datetime(
        df_v["ANKUNFTSZEIT"], format="%d.%m.%Y %H:%M", errors="coerce"
    )
    df_v["reel_arrivee"] = pd.to_datetime(
        df_v["AN_PROGNOSE"], format="%d.%m.%Y %H:%M:%S", errors="coerce"
    )

    statut_ok = df_v["AN_PROGNOSE_STATUS"].isin(STATUTS_REELS)
    df_v["retard_arr_sec"] = (
        (df_v["reel_arrivee"] - df_v["horaire_arrivee"])
        .dt.total_seconds()
        .where(statut_ok)
    )

    heure = df_v["horaire_arrivee"].dt.hour
    is_weekday = df_v["horaire_arrivee"].dt.weekday < 5  # lundi–vendredi

    df_v["is_pointe"] = is_weekday & (
        heure.isin(HEURES_POINTE_MATIN) | heure.isin(HEURES_POINTE_SOIR)
    )
    df_v["is_creux"] = heure.isin(HEURES_CREUX)

    return df_v[
        ["date", "horaire_arrivee", "retard_arr_sec", "is_pointe", "is_creux"]
    ]


def _agreger_vevey(fichiers: list[Path]) -> pd.DataFrame:
    """Consolide les arrivées de feeders à Vevey et les agrège par date.

    Returns:
        DataFrame indexé sur date avec indicateurs ist_vevey_*.
    """
    fragments: list[pd.DataFrame] = []
    for i, fich in enumerate(fichiers, 1):
        df_v = _lire_vevey_depuis_csv(fich)
        if not df_v.empty:
            fragments.append(df_v)
        log.info("[%02d/%02d] Vevey — %s : %d arrivées feeders",
                 i, len(fichiers), fich.name, len(df_v))

    if not fragments:
        log.warning("Aucune arrivée de feeders trouvée à Vevey")
        return pd.DataFrame()

    df = pd.concat(fragments, ignore_index=True)

    def _pct_ponctuel_retard_seul(serie: pd.Series, seuil: int) -> float:
        """Part des observations ponctuelles au seuil (convention retard seul).

        Ponctuel si retard <= seuil. Une arrivée en avance n'est pas pénalisée :
        un train CFF arrivant tôt à Vevey ne fait pas rater la correspondance R35.
        Utilisé pour la ponctualité à l'ARRIVÉE des feeders.
        """
        valid = serie.dropna()
        return float((valid <= seuil).mean()) if len(valid) > 0 else float("nan")

    agg = df.groupby("date").agg(
        ist_vevey_n_arrivees_j=("horaire_arrivee", "count"),
        ist_vevey_n_arrivees_pointe_j=("is_pointe", "sum"),
        ist_vevey_n_arrivees_creux_j=("is_creux", "sum"),
        ist_vevey_retard_arr_moy_sec_j=("retard_arr_sec", "mean"),
        ist_vevey_pct_arr_ponctuel_180s_j=(
            "retard_arr_sec", lambda x: _pct_ponctuel_retard_seul(x, 180)
        ),
    )

    agg["ist_vevey_n_arrivees_pointe_j"] = agg["ist_vevey_n_arrivees_pointe_j"].astype(int)
    agg["ist_vevey_n_arrivees_creux_j"] = agg["ist_vevey_n_arrivees_creux_j"].astype(int)

    return agg


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def construire_dim_ponctualite() -> None:
    """Orchestre les trois sections et écrit le parquet final."""
    fichiers = sorted(ISTDATEN_DIR.glob("istdaten_*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier istdaten_*.csv dans {ISTDATEN_DIR}")

    # --- Section 1 : R35 ponctualité ---
    log.info("Section 1 : chargement fact_istdaten_r35 …")
    df_fact = pd.read_parquet(ISTDATEN_CLEAN)
    r35 = _agreger_r35(df_fact)
    log.info("  R35 : %d dates", len(r35))

    # --- Section 2 : horaires théoriques ---
    log.info("Section 2 : chargement horaires théoriques …")
    n_theoriques = _charger_n_theoriques()
    log.info("  Horaires : %d dates (couverture %s → %s)",
             len(n_theoriques),
             min(n_theoriques.index),
             max(n_theoriques.index))

    # --- Assemblage R35 + horaires ---
    df = r35.join(n_theoriques, how="left")
    df["ist_r35_taux_realisation_horaire_j"] = (
        df["ist_r35_n_courses_realisees_j"] / df["ist_r35_n_courses_theoriques_j"]
    )
    df["ist_r35_part_courses_supplementaires_j"] = (
        df["ist_r35_n_courses_supplementaires_j"] / df["ist_r35_n_courses_realisees_j"]
    ).where(df["ist_r35_n_courses_realisees_j"] > 0)

    # --- Section 3 : connexions Vevey ---
    log.info("Section 3 : extraction connexions Vevey depuis %d CSV …", len(fichiers))
    vevey = _agreger_vevey(fichiers)

    if not vevey.empty:
        df = df.join(vevey, how="left")
    else:
        for col in ["ist_vevey_n_arrivees_j", "ist_vevey_n_arrivees_pointe_j",
                    "ist_vevey_n_arrivees_creux_j", "ist_vevey_retard_arr_moy_sec_j",
                    "ist_vevey_pct_arr_ponctuel_180s_j"]:
            df[col] = float("nan")

    df = df.reset_index().rename(columns={"index": "date"})

    # --- Réordonnancement des colonnes ---
    colonnes_finales = [
        "date",
        "ist_r35_n_courses_theoriques_j",
        "ist_r35_n_courses_realisees_j",
        "ist_r35_n_courses_annulees_j",
        "ist_r35_taux_realisation_horaire_j",
        "ist_r35_n_courses_supplementaires_j",
        "ist_r35_part_courses_supplementaires_j",
        "ist_r35_pct_dep_ponctuel_60s_j",
        "ist_r35_pct_dep_ponctuel_180s_j",
        "ist_r35_pct_dep_ponctuel_300s_j",
        "ist_r35_retard_dep_moy_sec_j",
        "ist_vevey_n_arrivees_j",
        "ist_vevey_n_arrivees_pointe_j",
        "ist_vevey_n_arrivees_creux_j",
        "ist_vevey_retard_arr_moy_sec_j",
        "ist_vevey_pct_arr_ponctuel_180s_j",
    ]
    df = df[colonnes_finales]

    # --- Logging des stats ---
    log.info("Dimensions finales : %d lignes × %d colonnes", df.shape[0], df.shape[1])
    log.info("Période : %s → %s", df["date"].min(), df["date"].max())
    log.info(
        "Taux réalisation moyen : %.1f%%",
        df["ist_r35_taux_realisation_horaire_j"].mean() * 100,
    )
    log.info(
        "Ponctualité ≤180s moyenne : %.1f%%",
        df["ist_r35_pct_dep_ponctuel_180s_j"].mean() * 100,
    )
    log.info(
        "Arrivées Vevey feeders/jour : %.1f moy",
        df["ist_vevey_n_arrivees_j"].mean(),
    )

    # --- Écriture atomique ---
    ISTDATEN_PONCTUALITE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ISTDATEN_PONCTUALITE.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False)
        tmp.rename(ISTDATEN_PONCTUALITE)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info("Écrit : %s", ISTDATEN_PONCTUALITE)


if __name__ == "__main__":
    construire_dim_ponctualite()
