"""
Ajoute les indicateurs STATPOP autour des gares à stage_04 (→ stage_06_statpop).

Pour chaque tronçon, on joint les indicateurs de fact_statpop_gare :
  - côté gare de départ  (préfixe ``spatial_gare_depart_``)
  - côté gare d'arrivée  (préfixe ``spatial_gare_arrivee_``)

Le millésime STATPOP utilisé est résolu via STATPOP_MAPPING indexé par
l'année calendaire de base_date (cf. ADR-039 v2). Cette indexation évite
la fuite temporelle d'une indexation par horaire_annee_horaire et garantit
qu'un voyageur compté en décembre N reçoive le millésime N (et non N+1).
Les indicateurs consolidés de fact_statpop_gare sont calculés dans un rayon
de 500 m autour de chaque gare par scripts/build_fact_statpop_gare.py.

La jointure est réalisée par chunks (100 000 lignes) pour limiter
l'empreinte mémoire, et le parquet est écrit en streaming via PyArrow.

Sources
-------
- data/processed/stage_04b_meteo_j.parquet        (produit par add_meteo_journaliere_to_raw_stacked.py)
- data/processed/sources/statpop_clean_causal.parquet  (produit par build_fact_statpop_gare.py, forward-fill causal ADR-076)

Sortie
------
- data/processed/stage_06_statpop.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py``
"""

import os
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import STAGE_04B_METEO_J as STAGE_04_METEO, STAGE_06_STATPOP, STATPOP_CLEAN as FACT_STATPOP  # noqa: E402
from pipeline.io import read_stage  # noqa: E402

WRITE_CSV = os.environ.get("WRITE_CSV", "").strip().lower() in {"1", "true", "yes"}
CHUNK_SIZE = 100_000

STATPOP_KEY_COLUMNS = ["annee_enquete_statpop", "gare_abreviation"]
RAW_STATION_COLUMNS = {
    "depart": "id_gare_depart",
    "arrivee": "id_gare_arrivee",
}

FACT_METADATA_RENAMES = {
    "annee_publication_statpop": "annee_publication_statpop",
    "gare_commune": "commune",
    "statpop_hectares_count": "hectares_count",
}
FACT_IDENTITY_COLUMNS = {
    "annee_enquete_statpop",
    "gare_abreviation",
    "gare_bpuic",
    "gare_nom",
    "gare_km",
}
SUMMARY_POPULATION_VALUE_COLUMNS = [
    "population_500m_total",
    "population_residante_permanente_total",
]

# -----------------------------------------------------------------------------
# Sélection de features STATPOP — retrait des redondances arithmétiques
# -----------------------------------------------------------------------------
# Trois features ont été retirées de STATPOP_KEEP_SUFFIXES suite à un
# diagnostic de multicolinéarité (cf. ADR-024) :
#   - densite_population_500m_km2  : r=1.00 avec population_500m_total
#     (le buffer étant à rayon fixe, surface = constante → densité = total / 0.785)
#   - densite_menages_500m_km2     : r=1.00 avec menages_500m_total (même raison)
#   - taille_menage_moyenne_estimee : r=0.96 avec part_grands_menages_4p_plus
#     (taille moyenne mécaniquement tirée par la proportion de grands ménages)
# Les valeurs restent calculées et stockées dans statpop_clean.parquet pour
# permettre une réintroduction sans recalcul du fait STATPOP (coûteux).
# -----------------------------------------------------------------------------

# Suffixes des colonnes statpop conservees dans la sortie (24 features × 2 côtés = 48 colonnes).
STATPOP_KEEP_SUFFIXES = {
    # Topologie (ordre ordinal dans dim_gare — feature XGBoost pour la séquence des tronçons)
    "ordre",
    # Population
    "population_500m_total",
    "part_population_0_14_ans",
    "part_population_15_24_ans",
    "part_population_25_64_ans",
    "part_population_65_plus",
    "part_population_80_plus",
    "indice_stabilite_residentielle",
    "indice_mobilite_residentielle",
    "part_nouveaux_arrivants_1_an",
    "part_population_etrangere",
    "part_population_nee_etranger",
    # Menages (disponibles 2015-2020, 2022, 2024 ; forward-fill causal pour 2021 et 2023 — ADR-063)
    # densite_menages_500m_km2 retiree : r=1.00 avec menages_500m_total (cf. ADR-024)
    # taille_menage_moyenne_estimee retiree : r=0.96 avec part_grands_menages_4p_plus (cf. ADR-024)
    "menages_500m_total",
    "population_par_menage_500m",
    "part_menages_1_personne",
    "part_grands_menages_4p_plus",
    # Qualite HPI (disponible 2015-2020, 2022, 2024 ; forward-fill causal pour 2021 et 2023 — ADR-063)
    "hpi_classe_max_500m",
    "hpi_hectares_classe_1_count",
    "hpi_hectares_classe_2_count",
    "hpi_hectares_classe_manquante_count",
    "hpi_hectares_autre_classe_count",
    "part_hectares_hpi_non_plausible",
    "flag_qualite_statpop_faible",
}

# Raccourcissement des noms pour les colonnes spatial_.
STATPOP_SUFFIX_SHORT = {
    # Population
    "population_500m_total":            "pop_500m_total",
    "densite_population_500m_km2":      "densite_pop_500m_km2",
    "part_population_0_14_ans":         "part_pop_0_14_ans",
    "part_population_15_24_ans":        "part_pop_15_24_ans",
    "part_population_25_64_ans":        "part_pop_25_64_ans",
    "part_population_65_plus":          "part_pop_65_plus",
    "part_population_80_plus":          "part_pop_80_plus",
    "indice_stabilite_residentielle":   "indice_stabilite_resid",
    "indice_mobilite_residentielle":    "indice_mobilite_resid",
    "part_nouveaux_arrivants_1_an":     "part_nouveaux_arrivants_1an",
    "part_population_etrangere":        "part_pop_etrangere",
    "part_population_nee_etranger":     "part_pop_nee_etranger",
    # Menages
    "menages_500m_total":               "menages_500m_total",
    "densite_menages_500m_km2":         "densite_menages_500m_km2",
    "population_par_menage_500m":       "pop_par_menage_500m",
    "part_menages_1_personne":          "part_menages_1p",
    "part_grands_menages_4p_plus":      "part_grands_menages_4p",
    "taille_menage_moyenne_estimee":    "taille_menage_moy",
    # Qualite HPI
    "hpi_classe_max_500m":              "hpi_classe_max",
    "hpi_hectares_classe_1_count":      "hpi_ha_classe_1",
    "hpi_hectares_classe_2_count":      "hpi_ha_classe_2",
    "hpi_hectares_classe_manquante_count": "hpi_ha_manquante",
    "hpi_hectares_autre_classe_count":  "hpi_ha_autre",
    "part_hectares_hpi_non_plausible":  "part_hpi_non_plausible",
    "flag_qualite_statpop_faible":      "flag_qualite_faible",
}

# Mapping année calendaire → millésime STATPOP et type de source (ADR-063 : causalité Z-2).
# - "exact"        : millésime OFS publié correspondant à l'année civile Z-2
# - "forward_fill" : HP*/HPI absents pour ce millésime → forward-fill causal depuis millésime N-1 (ADR-063)
# - "carry_forward": Z-2 non disponible → proxy sur le plus ancien millesime disponible
#
# Convention : indexation par année calendaire de base_date (pas horaire_annee_horaire).
# Justification causalité : STATPOP millesime Y est publié vers Y+2 ; utiliser millesime Y
# pour observer l'année Y introduit une fuite de disponibilité. Mapping conservateur Z-2 :
# observation année civile Z → millesime Z-2. (cf. ADR-063)
#
# VVVI : gare Vevey-Vignerons active depuis H23 (déc. 2022). Les millesimes 2020 et 2021
# (nécessaires pour les observations H23/H24 avec Z-2) sont absents de statpop_clean.
# Correction inline via _patch_vvvi_statpop() : forward-fill depuis VVVI-2022.
STATPOP_MAPPING: dict[int, dict] = {
    2015: {"millesime": 2015, "source": "exact"},          # Z-2=2013 absent → proxy 2015
    2016: {"millesime": 2015, "source": "carry_forward"},  # Z-2=2014 absent → proxy 2015
    2017: {"millesime": 2015, "source": "exact"},          # Z-2=2015 ✓
    2018: {"millesime": 2016, "source": "exact"},          # Z-2=2016 ✓
    2019: {"millesime": 2017, "source": "exact"},          # Z-2=2017 ✓
    2020: {"millesime": 2018, "source": "exact"},          # Z-2=2018 ✓
    2021: {"millesime": 2019, "source": "exact"},          # Z-2=2019 ✓ (ADR-063)
    2022: {"millesime": 2020, "source": "exact"},          # Z-2=2020 ✓ (ADR-063)
    2023: {"millesime": 2021, "source": "forward_fill"},    # Z-2=2021 ✓ HP*/HPI forward-fill ←2020 (ADR-063)
    2024: {"millesime": 2022, "source": "exact"},          # Z-2=2022 ✓ (ADR-063)
    2025: {"millesime": 2023, "source": "forward_fill"},   # Z-2=2023 ✓ HP*/HPI forward-fill ←2022 (ADR-063)
}

# Noms des colonnes de traçabilité source (métadonnées, pas des features ML).
# Convention cohérente avec event_ski_source, event_narcisses_source, event_covid_phase.
STATPOP_SOURCE_COL_DEPART  = "spatial_statpop_source_depart"
STATPOP_SOURCE_COL_ARRIVEE = "spatial_statpop_source_arrivee"


# ---------------------------------------------------------------------------
# Garde de provenance de la table STATPOP consommee (ADR-063, ADR-076)
# ---------------------------------------------------------------------------
# Correctif pre-publication (ADR-078 section 5.2). La garde d'epoque testait une
# etiquette de source derivee de STATPOP_MAPPING, c'est-a-dire une constante de ce
# module, et jamais la table effectivement lue : elle ne pouvait pas se declencher.
# La presente garde inspecte le CONTENU de l'artefact consomme.
#
# Propriete discriminante. La recette causale retenue (ADR-076) impute les millesimes
# manquants par report du dernier millesime publie AVANT la cible (LOCF) : les valeurs
# de 2021 sont donc EXACTEMENT celles de 2020, et celles de 2023 celles de 2022, sur
# toutes les colonnes imputees. La recette d'epoque combinait interpolation lineaire
# (colonnes continues) et maximum des millesimes adjacents (colonnes ordinales et
# binaires) : elle viole cette egalite des que la valeur croit d'un millesime a l'autre.
#
# Verifie empiriquement sur les deux tables du projet : la table causale ne presente
# aucun ecart sur 429 valeurs ; la table d'epoque en presente six, tous sur
# hpi_classe_max_500m, aux gares CHBL, HTV et STLE — ce sont exactement les valeurs
# d'ancrage dont ADR-075 etablit qu'elles distinguent les deux recettes (2021 = 1 et
# 2023 = 2 en causal, l'inverse par maximum adjacent).
#
# La garde est en lecture seule : elle ne modifie ni la table ni le pipeline.

#: Millesimes imputes -> millesime source du report causal (ADR-076).
STATPOP_MILLESIMES_IMPUTES: dict[int, int] = {2021: 2020, 2023: 2022}

#: Colonnes imputees, en miroir de INTERPOLATION_COLUMNS + IMPUTATION_MAX_COLUMNS du
#: producteur (scripts/sources/build_fact_statpop_gare.py). Ce sont les seules colonnes
#: reellement imputees : la source OFS ne publie les effectifs de menages et l'indicateur
#: HPI que pour certains millesimes, alors que les effectifs de population le sont chaque
#: annee. Les colonnes ordinales et binaires (hpi_classe_max_500m,
#: flag_qualite_statpop_faible) portent le pouvoir discriminant, les continues
#: constituant un controle de coherence supplementaire.
STATPOP_COLONNES_IMPUTEES = [
    "menages_500m_total",
    "densite_menages_500m_km2",
    "population_par_menage_500m",
    "part_menages_1_personne",
    "part_grands_menages_4p_plus",
    "taille_menage_moyenne_estimee",
    "hpi_hectares_classe_1_count",
    "hpi_hectares_classe_2_count",
    "hpi_hectares_classe_manquante_count",
    "hpi_hectares_autre_classe_count",
    "part_hectares_hpi_non_plausible",
    "hpi_classe_max_500m",
    "flag_qualite_statpop_faible",
]

#: VVVI (Vevey-Vignerons) est reconstruite depuis les hectares reels pour 2020-2022
#: (build_vvvi_rows_h23, ADR-076) : ses millesimes imputes ne sont pas des reports.
#: Elle est donc hors du test d'egalite.
STATPOP_GARES_RECONSTRUITES = {"VVVI"}


def assert_statpop_provenance_causale(fact, chemin=None) -> dict:
    """Echoue si la table STATPOP consommee n'est pas la table causale (LOCF).

    Le report causal etant une copie exacte, la tolerance est nulle : un seul ecart
    suffit a etablir que la table n'a pas ete produite par la recette d'ADR-076.

    Args:
        fact: la table STATPOP telle qu'elle vient d'etre lue.
        chemin: chemin resolu de l'artefact, pour le message d'erreur (facultatif).

    Returns:
        Un dictionnaire de comptes, pour journalisation.

    Raises:
        RuntimeError: si aucune colonne imputee n'est presente, si un millesime source
            manque, si aucune gare n'est comparable, ou si un seul ecart au report
            causal est constate — signature de la recette d'epoque.
    """
    import numpy as np

    ou = f" ({chemin})" if chemin else ""
    colonnes = [c for c in STATPOP_COLONNES_IMPUTEES if c in fact.columns]
    if not colonnes:
        raise RuntimeError(
            f"PROVENANCE STATPOP : aucune colonne imputee dans la table consommee{ou}. "
            f"Attendu au moins une de {STATPOP_COLONNES_IMPUTEES}."
        )

    annees = set(fact["annee_enquete_statpop"].dropna().astype(int).unique())
    comptes = {"colonnes_testees": len(colonnes), "paires": {}, "ecarts": 0, "total": 0}
    ecarts_detail: list[str] = []

    for cible, source in STATPOP_MILLESIMES_IMPUTES.items():
        if cible not in annees:
            continue  # millesime hors du perimetre conserve : rien a verifier
        if source not in annees:
            raise RuntimeError(
                f"PROVENANCE STATPOP : le millesime impute {cible} est present{ou} mais son "
                f"millesime source {source} est absent. Le report causal (ADR-076) est "
                f"inverifiable sur cette table."
            )

        a = (fact[fact["annee_enquete_statpop"] == cible]
             .drop_duplicates("gare_abreviation").set_index("gare_abreviation")[colonnes])
        b = (fact[fact["annee_enquete_statpop"] == source]
             .drop_duplicates("gare_abreviation").set_index("gare_abreviation")[colonnes])
        gares = a.index.intersection(b.index).difference(STATPOP_GARES_RECONSTRUITES)
        if len(gares) == 0:
            raise RuntimeError(
                f"PROVENANCE STATPOP : aucune gare eligible pour comparer {cible} a {source}{ou}."
            )

        av = a.loc[gares].to_numpy(dtype=float)
        bv = b.loc[gares].to_numpy(dtype=float)
        differe = ~((np.isnan(av) & np.isnan(bv))
                    | np.isclose(av, bv, rtol=0.0, atol=1e-9, equal_nan=False))
        for ig, ic in zip(*np.nonzero(differe)):
            if len(ecarts_detail) < 8:
                ecarts_detail.append(
                    f"{gares[ig]}/{colonnes[ic]} : {cible}={av[ig, ic]:g} "
                    f"mais {source}={bv[ig, ic]:g}"
                )
        comptes["paires"][f"{cible}<-{source}"] = {
            "gares": int(len(gares)),
            "ecarts": int(differe.sum()),
            "total": int(differe.size),
        }
        comptes["ecarts"] += int(differe.sum())
        comptes["total"] += int(differe.size)

    if comptes["total"] == 0:
        raise RuntimeError(
            f"PROVENANCE STATPOP : aucun millesime impute present dans la table{ou}. "
            f"Attendu au moins un de {sorted(STATPOP_MILLESIMES_IMPUTES)}."
        )

    if comptes["ecarts"]:
        raise RuntimeError(
            f"PROVENANCE STATPOP ECHOUEE{ou} : {comptes['ecarts']} valeur(s) sur "
            f"{comptes['total']} des millesimes imputes ne reproduisent pas exactement leur "
            f"millesime source, alors que le report causal (LOCF, ADR-076) est une copie "
            f"exacte. Exemples — {' ; '.join(ecarts_detail)}. C'est la signature de la recette "
            f"d'epoque (interpolation lineaire et maximum des millesimes adjacents). Verifier "
            f"que STATPOP_CLEAN pointe bien vers statpop_clean_causal.parquet, produit par "
            f"scripts/sources/build_fact_statpop_gare.py, et non vers statpop_clean.parquet."
        )
    return comptes


# Colonnes meteo horaires (noms prefixes) — utilisees pour l'ordre des colonnes en sortie.
DAILY_METEO_COLUMNS = {
    "meteo_temperature_h",
    "meteo_precipitation_mm_h",
    "meteo_ensoleillement_min_h",
    "meteo_vent_max_h",
    "meteo_neige_cm_h",
    "meteo_neige_binaire_h",
}


def iter_input_chunks(chunk_size: int = CHUNK_SIZE):
    """Lit stage_04 par batch pour limiter l'empreinte mémoire."""
    if STAGE_04_METEO.exists():
        for batch in pq.ParquetFile(STAGE_04_METEO).iter_batches(batch_size=chunk_size):
            yield batch.to_pandas()
        return
    csv = STAGE_04_METEO.with_suffix(".csv")
    if csv.exists():
        yield from pd.read_csv(csv, encoding="utf-8-sig", low_memory=False, chunksize=chunk_size)
        return
    raise FileNotFoundError(f"Stage 04 introuvable : {STAGE_04_METEO}")


def read_fact_statpop() -> pd.DataFrame:
    return read_stage(FACT_STATPOP, FACT_STATPOP.with_suffix(".csv"))


def build_statpop_millesime_and_source(
    df: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Résout le millésime STATPOP et la source par ligne, via STATPOP_MAPPING.

    Indexation par l'année calendaire de base_date. Cette approche évite la
    fuite temporelle qu'aurait provoquée une indexation par année horaire
    (les 18-21 jours de décembre d'une année N appartiennent à H(N+1) mais
    sont opérationnellement de l'année N).

    Returns
    -------
    millesime : pd.Series[Int64]  — annee_enquete_statpop à utiliser pour la jointure
    source    : pd.Series[string] — 'exact', 'forward_fill' ou 'carry_forward'

    Lève KeyError si une année calendaire n'est pas couverte par STATPOP_MAPPING.
    """
    if "base_date" not in df.columns:
        raise ValueError("Colonne base_date absente de la table input")

    annees_calendaire = pd.to_datetime(df["base_date"], errors="coerce").dt.year

    unknown = set(annees_calendaire.dropna().unique()) - set(STATPOP_MAPPING)
    if unknown:
        raise KeyError(
            f"Années calendaires absentes de STATPOP_MAPPING : {sorted(int(y) for y in unknown)}. "
            "Étendre la constante avant d'exécuter le pipeline."
        )

    millesime = annees_calendaire.map(
        {y: m["millesime"] for y, m in STATPOP_MAPPING.items()}
    ).astype("Int64")

    source = annees_calendaire.map(
        {y: m["source"] for y, m in STATPOP_MAPPING.items()}
    ).astype("string")

    return millesime, source


def _patch_vvvi_statpop(fact: pd.DataFrame) -> pd.DataFrame:
    """Injecte des lignes VVVI pour les millesimes 2019, 2020, 2021 manquants.

    VVVI (Vevey-Vignerons) a ouvert en H23 ; statpop_clean ne couvre VVVI qu'à
    partir de 2022. Avec le mapping causal Z-2, les observations H23/H24 requièrent
    les millesimes 2020/2021. Forward-fill depuis VVVI-2022 (ADR-063).

    Depuis ADR-076, les millesimes actifs (2020-2022) viennent du PRODUCTEUR
    (build_vvvi_rows_h23, topologie H23) : ce patch ne fait plus qu'ajouter la ligne
    INERTE VVVI-2019 (jamais mobilisee par les jointures Z-2, ADR-075/076).
    """
    TARGET_GARE = "VVVI"
    MISSING_MILLESIMES = [2019, 2020, 2021]

    vvvi_ref = fact[
        (fact["gare_abreviation"] == TARGET_GARE) & (fact["annee_enquete_statpop"] == 2022)
    ]
    if len(vvvi_ref) == 0:
        return fact

    rows = []
    for mil in MISSING_MILLESIMES:
        already_present = (
            (fact["gare_abreviation"] == TARGET_GARE) & (fact["annee_enquete_statpop"] == mil)
        ).any()
        if not already_present:
            row = vvvi_ref.iloc[0].copy()
            row["annee_enquete_statpop"] = mil
            if "annee_publication_statpop" in row.index:
                row["annee_publication_statpop"] = pd.NA
            rows.append(row)

    if rows:
        patch = pd.DataFrame(rows)
        fact = pd.concat([fact, patch], ignore_index=True)

    return fact


def prepare_fact_statpop(fact: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(set(STATPOP_KEY_COLUMNS) - set(fact.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans fact_statpop_gare: {missing_columns}")

    if not any(column in fact.columns for column in SUMMARY_POPULATION_VALUE_COLUMNS):
        raise ValueError(
            "Colonne de population manquante dans fact_statpop_gare. "
            f"Colonnes attendues : {SUMMARY_POPULATION_VALUE_COLUMNS}"
        )

    statpop = fact.copy()
    statpop["annee_enquete_statpop"] = statpop["annee_enquete_statpop"].astype("Int64")
    statpop["gare_abreviation"] = statpop["gare_abreviation"].astype("string").str.strip()
    statpop.loc[statpop["gare_abreviation"].eq(""), "gare_abreviation"] = pd.NA

    statpop = _patch_vvvi_statpop(statpop)

    duplicate_mask = statpop.duplicated(STATPOP_KEY_COLUMNS, keep=False)
    if duplicate_mask.any():
        examples = statpop.loc[duplicate_mask, STATPOP_KEY_COLUMNS].head(10)
        raise ValueError(f"Cles STATPOP dupliquees:\n{examples}")

    return statpop


def statpop_value_columns(fact: pd.DataFrame) -> list[str]:
    return [
        column
        for column in fact.columns
        if column not in FACT_IDENTITY_COLUMNS
    ]


def prefixed_summary_column(
    enriched: pd.DataFrame,
    side: str,
    candidate_value_columns: list[str],
) -> str:
    for value_column in candidate_value_columns:
        short = STATPOP_SUFFIX_SHORT.get(value_column, value_column)
        column = f"spatial_gare_{side}_{short}"
        if column in enriched.columns:
            return column

    raise ValueError(
        f"Aucune colonne de synthese STATPOP disponible pour {side}. "
        f"Colonnes candidates : {candidate_value_columns}"
    )


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reordonne les colonnes : base/cal/event/horaire/id -> spatial -> meteo."""
    meteo_cols = [c for c in df.columns if c in DAILY_METEO_COLUMNS]
    spatial_cols = [c for c in df.columns if c.startswith("spatial_")]
    other_cols = [c for c in df.columns if c not in meteo_cols and c not in spatial_cols]
    return df[other_cols + spatial_cols + meteo_cols]


def prefixed_fact_for_side(fact: pd.DataFrame, side: str) -> pd.DataFrame:
    prefix = f"spatial_gare_{side}_"
    value_columns = statpop_value_columns(fact)

    renamed_columns = {}
    for column in value_columns:
        raw_suffix = FACT_METADATA_RENAMES.get(column, column)
        short_suffix = STATPOP_SUFFIX_SHORT.get(raw_suffix, raw_suffix)
        renamed_columns[column] = f"{prefix}{short_suffix}"

    return fact[[*STATPOP_KEY_COLUMNS, *value_columns]].rename(columns=renamed_columns)


def add_statpop_for_side(
    df: pd.DataFrame,
    fact: pd.DataFrame,
    side: str,
    station_column: str,
) -> pd.DataFrame:
    if station_column not in df.columns:
        raise ValueError(f"Colonne {station_column} absente de la table input")

    dimension = prefixed_fact_for_side(fact, side)
    enriched = df.merge(
        dimension,
        how="left",
        left_on=["id_statpop_reference_year", station_column],
        right_on=STATPOP_KEY_COLUMNS,
        validate="many_to_one",
    )

    if len(enriched) != len(df):
        raise ValueError(f"La jointure STATPOP {side} a modifie le nombre de lignes")

    unmatched_mask = enriched[f"spatial_gare_{side}_hectares_count"].isna()
    if unmatched_mask.any():
        missing_years = (
            enriched.loc[unmatched_mask, "id_statpop_reference_year"]
            .dropna()
            .unique()
            .tolist()
        )
        print(
            f"  Avertissement : {int(unmatched_mask.sum()):,} ligne(s) sans STATPOP {side} "
            f"(annees civiles sans millesime : {sorted(missing_years)}) → valeurs nulles"
        )

    # Supprimer les colonnes de jointure et les colonnes hors perimetre population.
    prefix = f"spatial_gare_{side}_"
    keep_prefixed = {f"{prefix}{STATPOP_SUFFIX_SHORT.get(s, s)}" for s in STATPOP_KEEP_SUFFIXES}
    all_prefixed = [c for c in enriched.columns if c.startswith(prefix)]
    drop_cols = [c for c in all_prefixed if c not in keep_prefixed]
    return enriched.drop(columns=[*STATPOP_KEY_COLUMNS, *drop_cols])


def add_statpop_to_raw_stacked(raw_stacked: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    drop_existing = [
        "id_statpop_reference_year",
        STATPOP_SOURCE_COL_DEPART,
        STATPOP_SOURCE_COL_ARRIVEE,
    ]
    enriched = raw_stacked.drop(
        columns=[c for c in drop_existing if c in raw_stacked.columns]
    ).copy()

    millesime, source = build_statpop_millesime_and_source(enriched)
    enriched["id_statpop_reference_year"] = millesime

    for side, station_column in RAW_STATION_COLUMNS.items():
        enriched = add_statpop_for_side(
            enriched,
            fact,
            side=side,
            station_column=station_column,
        )

    # Colonnes de traçabilité source — métadonnées, pas des features ML.
    # Même valeur côté départ et arrivée ; peut varier au sein d'une année horaire
    # (décembre N → millésime N, janvier-novembre N+1 → millésime N+1 ou carry_forward).
    enriched[STATPOP_SOURCE_COL_DEPART]  = source
    enriched[STATPOP_SOURCE_COL_ARRIVEE] = source

    if len(enriched) != len(raw_stacked):
        raise ValueError("La transformation STATPOP a modifie le nombre de lignes")

    return reorder_columns(enriched)


def update_summary_counts(summary: dict, enriched: pd.DataFrame) -> None:
    summary["rows"] += len(enriched)
    year_counts = enriched["id_statpop_reference_year"].value_counts(dropna=False)
    for year, count in year_counts.items():
        summary["years"][year] = summary["years"].get(year, 0) + int(count)
    for side in RAW_STATION_COLUMNS:
        population_column = prefixed_summary_column(enriched, side, SUMMARY_POPULATION_VALUE_COLUMNS)
        summary[f"{side}_population_missing"] += int(enriched[population_column].isna().sum())

    # Distribution des sources par année calendaire (validation post-construction)
    annee_cal = pd.to_datetime(enriched["base_date"], errors="coerce").dt.year
    for year_cal, group_idx in enriched.groupby(annee_cal, dropna=True, sort=False).groups.items():
        year_cal = int(year_cal)
        group = enriched.loc[group_idx]
        src = group[STATPOP_SOURCE_COL_DEPART].iloc[0] if len(group) else None
        if year_cal not in summary["sources_par_annee_cal"]:
            summary["sources_par_annee_cal"][year_cal] = {"source": src, "count": 0}
        summary["sources_par_annee_cal"][year_cal]["count"] += len(group)

    # Distribution croisée année horaire × année calendaire (audit cohérence temporelle)
    tmp = enriched[["horaire_annee_horaire", STATPOP_SOURCE_COL_DEPART]].copy()
    tmp["_annee_cal"] = annee_cal
    for (ah, year_cal), group in tmp.groupby(
        ["horaire_annee_horaire", "_annee_cal"], dropna=True, sort=False
    ):
        key = (str(ah), int(year_cal))
        src = group[STATPOP_SOURCE_COL_DEPART].iloc[0] if len(group) else None
        if key not in summary["sources_par_ah_x_annee_cal"]:
            summary["sources_par_ah_x_annee_cal"][key] = {"source": src, "count": 0}
        summary["sources_par_ah_x_annee_cal"][key]["count"] += len(group)


def print_chunked_summary(summary: dict) -> None:
    print("Millesimes STATPOP utilises:")
    for year, count in sorted(summary["years"].items()):
        print(f"  {year}: {count:,} lignes")
    for side in RAW_STATION_COLUMNS:
        print(f"{side}: population totale manquante={summary[f'{side}_population_missing']:,}")

    print("\n=== Distribution statpop_source par annee calendaire ===")
    for year_cal in sorted(summary["sources_par_annee_cal"]):
        info = summary["sources_par_annee_cal"][year_cal]
        expected = STATPOP_MAPPING.get(year_cal, {}).get("source", "?")
        status = "OK" if info["source"] == expected else f"ANOMALIE (attendu={expected!r})"
        print(f"  {year_cal}: source={info['source']!r}, {info['count']:,} lignes [{status}]")

    print("\n=== Distribution croisee annee horaire x annee calendaire ===")
    print("  (Dec d'annee N appartient a H(N+1) mais recoit millesime N — coherence temporelle stricte.)")
    for (ah, year_cal) in sorted(summary["sources_par_ah_x_annee_cal"]):
        info = summary["sources_par_ah_x_annee_cal"][(ah, year_cal)]
        print(f"  AH={ah}, cal={year_cal}: source={info['source']!r}, {info['count']:,} lignes")

    # La garde de provenance de la table STATPOP est appliquee en amont, sur l'artefact
    # effectivement lu : voir assert_statpop_provenance_causale, appelee dans main().
    # Le bloc d'epoque situe ici testait une etiquette derivee de STATPOP_MAPPING, donc
    # de ce module, et non la table consommee : il ne pouvait pas se declencher
    # (correctif pre-publication, ADR-078 section 5.2).

    # Coherence interne de l'etiquetage : chaque annee calendaire porte l'etiquette que
    # STATPOP_MAPPING lui assigne. Ce controle porte sur l'etiquetage, non sur la
    # provenance de la table (verifiee par assert_statpop_provenance_causale).
    anomalies = [
        year_cal for year_cal, info in summary["sources_par_annee_cal"].items()
        if info["source"] != STATPOP_MAPPING.get(year_cal, {}).get("source")
    ]
    if anomalies:
        raise RuntimeError(
            f"CONFORMITE STATPOP_MAPPING ECHOUEE sur annees calendaires : {anomalies}. "
            "Verifier la coherence entre STATPOP_MAPPING et statpop_clean_causal.parquet."
        )


def main() -> None:
    fact_brut = read_fact_statpop()
    # Garde bloquante de provenance : echoue si la table consommee n'est pas la table
    # causale (ADR-063, ADR-076). Lecture seule, sans effet sur les donnees produites.
    comptes = assert_statpop_provenance_causale(fact_brut, chemin=FACT_STATPOP)
    conformes = comptes["total"] - comptes["ecarts"]
    print(f"  Provenance STATPOP : {conformes}/{comptes['total']} valeurs imputees reproduisent "
          f"exactement leur millesime source — table causale (LOCF) confirmee.")
    fact_statpop = prepare_fact_statpop(fact_brut)
    STAGE_06_STATPOP.parent.mkdir(parents=True, exist_ok=True)

    parquet_writer = None
    csv_path = STAGE_06_STATPOP.with_suffix(".csv")
    csv_header = True
    summary = {
        "rows": 0,
        "years": {},
        "sources_par_annee_cal": {},
        "sources_par_ah_x_annee_cal": {},
        "depart_population_missing": 0,
        "arrivee_population_missing": 0,
    }

    try:
        for chunk_number, raw_chunk in enumerate(iter_input_chunks(), start=1):
            enriched_chunk = add_statpop_to_raw_stacked(raw_chunk, fact_statpop)
            update_summary_counts(summary, enriched_chunk)

            table = pa.Table.from_pandas(enriched_chunk, preserve_index=False)
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(
                    STAGE_06_STATPOP,
                    table.schema,
                    compression="snappy",
                )
            else:
                table = table.cast(parquet_writer.schema)
            parquet_writer.write_table(table)

            if WRITE_CSV:
                enriched_chunk.to_csv(
                    csv_path,
                    mode="w" if csv_header else "a",
                    header=csv_header,
                    index=False,
                    encoding="utf-8-sig" if csv_header else "utf-8",
                )
                csv_header = False

            print(f"Chunk {chunk_number}: {len(enriched_chunk):,} lignes traitees")
    finally:
        if parquet_writer is not None:
            parquet_writer.close()

    print(f"  parquet : {STAGE_06_STATPOP}  ({summary['rows']:,} lignes)")
    if WRITE_CSV:
        print(f"  csv     : {csv_path}")
    print_chunked_summary(summary)


if __name__ == "__main__":
    main()
