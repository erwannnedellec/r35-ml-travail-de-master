"""
Chemins canoniques de la pipeline R35.

Ce module est l'unique source de vérité pour tous les noms de fichiers.
Toute modification de nommage se fait ici et se propage automatiquement
à l'ensemble des scripts.

Architecture en couches
-----------------------
  raw/                          Données APC brutes (immuables)
  external/                     Sources externes brutes (immuables)
  data/intermediate/            Artefacts de structuration brute (bronze)
  data/processed/sources/       Tables propres par source (silver)
  data/dimension/               Référentiels métier (silver — lookup statiques)
  data/processed/stage_NN_*     Pipeline d'enrichissement (gold)
  data/processed/ml_dataset     Dataset ML final (gold)

Usage
-----
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from pipeline.paths import APC_STACKED, STAGE_01_ANNEE, PROJECT_ROOT
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# Racine du projet
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for candidate in [current, *current.parents]:
        # La racine est le répertoire qui porte à la fois `data/` et `scripts/`.
        # (Le dépôt de travail portait aussi `notebooks/` ; celui-ci n'est pas repris
        # dans le dépôt remis, il ne peut donc plus servir de marqueur de racine.)
        if (candidate / "data").exists() and (candidate / "scripts").exists():
            return candidate
    raise FileNotFoundError(
        "Racine du projet introuvable depuis pipeline/paths.py. "
        "Vérifier que 'data/' et 'scripts/' existent au même niveau."
    )


PROJECT_ROOT = _find_project_root()

RAW          = PROJECT_ROOT / "data" / "raw"
EXTERNAL     = PROJECT_ROOT / "data" / "external"
INTERMEDIATE = PROJECT_ROOT / "data" / "intermediate"
PROCESSED    = PROJECT_ROOT / "data" / "processed"
SOURCES      = PROCESSED / "sources"
DIMENSION    = PROJECT_ROOT / "data" / "dimension"

# ---------------------------------------------------------------------------
# Tables propres par source — processed/sources/ (silver)
#
# Source              → Fichier                Script producteur
# ----------------------------------------------------------------
# APC (4 CSV raw)     → apc_stacked            sources/stack_raw_csv.py
# MeteoSuisse VEV     → meteo_vev_clean        sources/build_meteosuisse_vev_clean.py
# MeteoSuisse CHD     → meteo_chd_clean        sources/build_meteosuisse_chd_clean.py
# Horaires R35 PDF    → horaires_clean         sources/build_horaires_r35_from_pdfs.py
# ISTDATEN            → istdaten_clean         sources/build_fact_istdaten_r35.py
# ISTDATEN agrégé     → istdaten_ponctualite   sources/build_istdaten_ponctualite.py
# ISTDATEN profil     → dim_profil_train       sources/build_dim_profil_train.py
# ISTDATEN corresp.   → dim_correspondances_vevey  sources/build_dim_correspondances_vevey.py
# VMCV par gare       → dim_vmcv_par_gare      sources/build_dim_vmcv_par_gare.py
# STATPOP OFS         → statpop_clean_causal   sources/build_fact_statpop_gare.py (forward-fill causal, ADR-076)
# SIMBA FQkal         → simba_clean            sources/build_fact_simba_r35.py
#                     → simba_expansion_troncons  sources/build_fact_simba_r35.py
# ---------------------------------------------------------------------------
# Note : la dimension ski (dim_ski_pleiades) est dans data/dimension/ car c'est
# un référentiel métier (lookup statique), pas une table de faits source.
# ---------------------------------------------------------------------------

APC_STACKED           = SOURCES / "apc_stacked.parquet"
METEO_VEV_CLEAN       = SOURCES / "meteo_vev_clean.parquet"
METEO_CHD_CLEAN       = SOURCES / "meteo_chd_clean.parquet"
HORAIRES_CLEAN        = SOURCES / "horaires_clean.parquet"
ISTDATEN_CLEAN        = SOURCES / "istdaten_clean.parquet"
ISTDATEN_PONCTUALITE  = SOURCES / "istdaten_ponctualite.parquet"
STATPOP_CLEAN         = SOURCES / "statpop_clean_causal.parquet"
STATENT_CLEAN         = SOURCES / "statent_clean_causal.parquet"
SIMBA_CLEAN           = SOURCES / "simba_clean.parquet"
SIMBA_EXPANSION       = SOURCES / "simba_expansion_troncons.parquet"

# Tables refondues ISTDATEN (grain date × numero_train ou gare statique)
DIM_PROFIL_TRAIN          = SOURCES / "dim_profil_train.parquet"
DIM_CORRESPONDANCES_VEVEY = SOURCES / "dim_correspondances_vevey.parquet"
DIM_VMCV_PAR_GARE         = SOURCES / "dim_vmcv_par_gare.parquet"    # DEPRECATED
DIM_VMCV_PAR_TRONCON      = SOURCES / "dim_vmcv_par_troncon.parquet"  # DEPRECATED — remplacé par DIM_VMCV_PAR_TRAIN_JOUR (ADR-021)
DIM_VMCV_PAR_TRAIN_JOUR   = SOURCES / "dim_vmcv_par_train_jour.parquet"
DIM_HEADWAY               = SOURCES / "dim_headway.parquet"

# Audit des doublons APC (produit par stack_raw_csv.py, non un stage)
RAW_DUPLICATES        = PROCESSED / "raw_duplicates.parquet"

# ---------------------------------------------------------------------------
# Artefacts intermédiaires — data/intermediate/ (bronze)
#
# Produits par build_horaires_r35_from_pdfs.py avant la table propre finale.
# ---------------------------------------------------------------------------

HORAIRES_ARRETS_OFFICIELS   = INTERMEDIATE / "horaires_r35_arrets_officiels.parquet"
HORAIRES_TRONCONS_TEMPLATE  = INTERMEDIATE / "horaires_r35_troncons_template.parquet"
HORAIRES_CALENDRIER         = INTERMEDIATE / "horaires_r35_calendrier_circulation.parquet"
HORAIRES_NOTES              = INTERMEDIATE / "horaires_r35_notes_circulation_pdf.parquet"
HORAIRES_AUDIT              = INTERMEDIATE / "horaires_r35_extraction_audit.csv"

# ---------------------------------------------------------------------------
# Stages de la pipeline principale — processed/ (gold)
#
# Stage  → script producteur (dans scripts/pipeline/)
# -------------------------------------------------------
# stage_01    add_annee_horaire_to_raw_stacked.py
# stage_02    add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py
# stage_03    add_manifestations_riviera_to_raw_stacked.py
# stage_03b   add_ski_pleiades_to_raw_stacked.py          ← ski Les Pléiades
# stage_03c   add_covid_to_raw_stacked.py                 ← flag COVID
# stage_03d   add_narcisses_to_raw_stacked.py             ← saison narcisses
# stage_03e   add_spatial_to_raw_stacked.py               ← spatial_segment (bas/haut/mixte)
# stage_04    add_meteo_to_raw_stacked.py                 ← météo horaire VEV+CHD (9 features)
# stage_04b   add_meteo_journaliere_to_raw_stacked.py     ← météo journalière J/J-1/J+1 (18 features, ADR-028)
# (stage_05 absent : existait comme stage météo CHD séparé, fusionné dans stage_04, numérotation conservée)
# stage_06    add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py
# stage_07    add_istdaten_to_raw_stacked.py  (remplace add_ponctualite_to_raw_stacked.py)
# stage_08    add_features_to_raw_stacked.py
# stage_09    add_simba_to_raw_stacked.py
# stage_10    add_reservations_to_raw_stacked.py  ← réservations de groupes ResSys (ADR-035)
# ml_dataset  build_ml_dataset.py
# ---------------------------------------------------------------------------

STAGE_01_ANNEE          = PROCESSED / "stage_01_annee_horaire.parquet"
STAGE_02_CALENDRIER     = PROCESSED / "stage_02_calendrier.parquet"
STAGE_03_MANIFESTATIONS = PROCESSED / "stage_03_manifestations.parquet"
STAGE_03B_SKI           = PROCESSED / "stage_03b_ski.parquet"
STAGE_03C_COVID         = PROCESSED / "stage_03c_covid.parquet"
STAGE_03D_NARCISSES     = PROCESSED / "stage_03d_narcisses.parquet"
STAGE_03E_SPATIAL       = PROCESSED / "stage_03e_spatial.parquet"
STAGE_04_METEO          = PROCESSED / "stage_04_meteo.parquet"
STAGE_04B_METEO_J       = PROCESSED / "stage_04b_meteo_j.parquet"
STAGE_06_STATPOP        = PROCESSED / "stage_06_statpop.parquet"
STAGE_06B_STATENT       = PROCESSED / "stage_06b_statent.parquet"
STAGE_07_PONCTUALITE    = PROCESSED / "stage_07_ponctualite.parquet"   # DEPRECATED : remplacé par STAGE_07_ISTDATEN
STAGE_07_ISTDATEN       = PROCESSED / "stage_07_istdaten.parquet"
STAGE_08_FEATURES       = PROCESSED / "stage_08_features.parquet"
STAGE_09_SIMBA          = PROCESSED / "stage_09_simba.parquet"
STAGE_10_RESERVATIONS   = PROCESSED / "stage_10_reservations.parquet"
ML_DATASET              = PROCESSED / "ml_dataset.parquet"

# ---------------------------------------------------------------------------
# Référentiels métier — data/dimension/ (silver — lookup statiques)
# ---------------------------------------------------------------------------

DIM_GARE                              = DIMENSION / "dim_gare.parquet"
DIM_GARE_CSV                          = DIMENSION / "dim_gare.csv"
DIM_VACANCES_FERIES                   = DIMENSION / "dim_vacances_feries_vaud.parquet"
DIM_ANNEES_HORAIRES                   = DIMENSION / "annees_horaires.csv"
DIM_MANIFESTATIONS_RIVIERA            = DIMENSION / "dim_manifestations_riviera.parquet"
DIM_MANIFESTATIONS_RIVIERA_EVENEMENTS = DIMENSION / "dim_manifestations_riviera_evenements.parquet"
DIM_VMCV_CONCURRENTES                 = DIMENSION / "dim_vmcv_lignes_concurrentes.parquet"
DIM_VMCV_LIGNES_PAR_GARE             = DIMENSION / "dim_vmcv_lignes_par_gare_r35.parquet"
DIM_SKI_PLEIADES                      = DIMENSION / "dim_ski_pleiades.parquet"
DIM_COVID                             = DIMENSION / "dim_covid.parquet"
DIM_NARCISSES                         = DIMENSION / "dim_narcisses.parquet"
DIM_ROTATIONS_R35                     = DIMENSION / "dim_rotations_r35.parquet"
DIM_SIMBA_R35                         = DIMENSION / "dim_simba_r35.parquet"

# ---------------------------------------------------------------------------
# Sources externes (chemins fréquemment utilisés)
# ---------------------------------------------------------------------------

ISTDATEN_DIR             = EXTERNAL / "istdaten"
SIMBA_DIR                = EXTERNAL / "simba"
RESA_DIR                 = EXTERNAL / "reservations"
FULL_WORLD_TRAFFIC_POINT = DIMENSION / "full-world-traffic-point.csv"
