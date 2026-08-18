# =============================================================================
# Pipeline R35 — Makefile
#
# Usage courant
# -------------
#   make               → construit ml_dataset.parquet (cible par défaut)
#   make dims          → construit toutes les tables sources et de dimension
#   make stage_01      → rejoue uniquement le stage 01
#   make clean         → supprime tous les stages intermédiaires
#   make clean-all     → supprime stages + sources + ml_dataset
#
# Rejouer depuis une étape spécifique
# ------------------------------------
#   touch data/processed/stage_03_manifestations.parquet
#   make               → make détecte que stage_04+ sont plus anciens et les rejoue
#
# Variables d'environnement
# -------------------------
#   WRITE_CSV=1 make   → produit aussi les CSV à chaque étape
# =============================================================================

PYTHON  := python3
SRC     := scripts/sources
PIPE    := scripts/pipeline

# ---------------------------------------------------------------------------
# Reproductibilite : threads numeriques fixes a 1 (ADR-076)
# ---------------------------------------------------------------------------
# Le double run vierge de confirmation (ADR-076) a revele un non-determinisme
# ENVIRONNEMENTAL pre-existant : le BLAS multi-thread (Apple Accelerate / OpenBLAS)
# produit des reductions flottantes non-associatives, dependantes de l'ordonnancement
# des threads (differences a l'ULP, ~1 run sur 3). Fixer les threads a 1 rend l'ordre
# de sommation deterministe. Le contrat de reproductibilite couvre desormais
# code + donnees + environnement (pinning pyarrow 21.0.0 ADR-066, threads ADR-076).
export OMP_NUM_THREADS        := 1
export OPENBLAS_NUM_THREADS   := 1
export MKL_NUM_THREADS        := 1
export NUMEXPR_NUM_THREADS    := 1
export VECLIB_MAXIMUM_THREADS := 1

# ---------------------------------------------------------------------------
# Chemins — synchronisés avec scripts/pipeline/paths.py
# ---------------------------------------------------------------------------

# Tables propres par source (silver — processed/sources/)
APC_STACKED      := data/processed/sources/apc_stacked.parquet
METEO_VEV_CLEAN  := data/processed/sources/meteo_vev_clean.parquet
METEO_CHD_CLEAN  := data/processed/sources/meteo_chd_clean.parquet
HORAIRES_CLEAN   := data/processed/sources/horaires_clean.parquet
ISTDATEN_CLEAN   := data/processed/sources/istdaten_clean.parquet
ISTDATEN_PONCT   := data/processed/sources/istdaten_ponctualite.parquet
STATPOP_CLEAN    := data/processed/sources/statpop_clean_causal.parquet

# Référentiels métier (dimension/)
DIM_GARE                := data/dimension/dim_gare.parquet
DIM_VACANCES            := data/dimension/dim_vacances_feries_vaud.parquet
DIM_MANIFESTATIONS      := data/dimension/dim_manifestations_riviera.parquet
DIM_SKI                 := data/dimension/dim_ski_pleiades.parquet
DIM_ROTATIONS           := data/dimension/dim_rotations_r35.parquet
DIM_COVID               := data/dimension/dim_covid.parquet
DIM_NARCISSES           := data/dimension/dim_narcisses.parquet
DIM_VMCV_CONCURRENTES   := data/dimension/dim_vmcv_lignes_concurrentes.parquet
DIM_VMCV_LIGNES_PAR_GARE := data/dimension/dim_vmcv_lignes_par_gare_r35.parquet

# Tables silver ISTDATEN refondues (processed/sources/)
DIM_SIMBA_R35       := data/dimension/dim_simba_r35.parquet
DIM_PROFIL_TRAIN    := data/processed/sources/dim_profil_train.parquet
DIM_CORRESPONDANCES := data/processed/sources/dim_correspondances_vevey.parquet
DIM_VMCV_PAR_GARE      := data/processed/sources/dim_vmcv_par_gare.parquet    # DEPRECATED
DIM_VMCV_PAR_TRONCON   := data/processed/sources/dim_vmcv_par_troncon.parquet   # DEPRECATED — ADR-020 remplacé par ADR-021
DIM_VMCV_PAR_TRAIN_JOUR := data/processed/sources/dim_vmcv_par_train_jour.parquet
DIM_HEADWAY         := data/processed/sources/dim_headway.parquet

# Pipeline séquentielle (gold — processed/)
STAGE_01          := data/processed/stage_01_annee_horaire.parquet
STAGE_02          := data/processed/stage_02_calendrier.parquet
STAGE_03          := data/processed/stage_03_manifestations.parquet
STAGE_03B         := data/processed/stage_03b_ski.parquet
STAGE_03C         := data/processed/stage_03c_covid.parquet
STAGE_03D         := data/processed/stage_03d_narcisses.parquet
STAGE_03E         := data/processed/stage_03e_spatial.parquet
STAGE_04          := data/processed/stage_04_meteo.parquet
STAGE_04B         := data/processed/stage_04b_meteo_j.parquet
STAGE_06          := data/processed/stage_06_statpop.parquet
STAGE_07_ISTDATEN := data/processed/stage_07_istdaten.parquet
STAGE_08          := data/processed/stage_08_features.parquet
STAGE_09          := data/processed/stage_09_simba.parquet
STAGE_10          := data/processed/stage_10_reservations.parquet
STAGE_06B         := data/processed/stage_06b_statent.parquet
STATENT_CLEAN     := data/processed/sources/statent_clean_causal.parquet
ML_DS             := data/processed/ml_dataset.parquet
RESA_XLSX         := $(wildcard data/external/reservations/*.xlsx)

RAW_CSV     := $(wildcard data/raw/*.csv)
RAW_METEO   := $(wildcard data/external/meteosuisse/*.csv)
RAW_STATPOP := $(wildcard data/external/statpop/*.csv)

# ---------------------------------------------------------------------------
# Cibles phony
# ---------------------------------------------------------------------------
.PHONY: all dims sources stage_01 stage_02 stage_03 stage_03b stage_03c stage_03d \
        stage_03e stage_04 stage_04b stage_06 stage_06b stage_07 stage_08 stage_09 stage_10 clean clean-all help \
        check-sources check-models check-guards check-tests \
        reproduce reproduce-dataset reproduce-couche1 reproduce-couche2 \
        reproduce-confirmation reproduce-complements reproduce-memoire

all: $(ML_DS)

# Verification des empreintes des deux modeles geles de la couche 1 (ADR-076).
# Seule verification d'integrite executable SANS les donnees confidentielles :
# elle constitue le point de controle offert au jury (cf. README section 1).
check-models:
	@echo "Empreintes SHA256[:8] des modeles geles du gel ba493568 :"
	@for f in models/enrichi_seg/enrichi_seg_bas_ba493568.json \
	          models/enrichi_seg/enrichi_seg_haut_ba493568.json ; do \
	    h=$$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()[:8])" $$f) ; \
	    printf "  %-52s %s\n" "$$f" "$$h" ; \
	  done
	@python3 -c "import hashlib; \
	    b=hashlib.sha256(open('models/enrichi_seg/enrichi_seg_bas_ba493568.json','rb').read()).hexdigest()[:8]; \
	    h=hashlib.sha256(open('models/enrichi_seg/enrichi_seg_haut_ba493568.json','rb').read()).hexdigest()[:8]; \
	    ok = (b=='e4ddfccd' and h=='df6a11c5'); \
	    print('  -> attendu : e4ddfccd (bas) / df6a11c5 (haut) -- ' + ('CONFORME' if ok else 'ECART')); \
	    raise SystemExit(0 if ok else 1)"

# Tests des gardes du pipeline executables SANS les donnees confidentielles. Couvre la
# garde de provenance de la table STATPOP (ADR-063, ADR-076) et son test negatif : une
# table interpolee doit faire echouer la garde.
check-guards:
	@python3 -m pytest tests/test_statpop_provenance_causale.py -q

# Verification bloquante des entrees figees (empreintes SHA256) et sources requises
# (presence). Prealable a `make clean-all && make` (invariant de reproductibilite, ADR-075).
check-sources:
	@bash scripts/check_sources.sh

# Suite de tests complete (perimetre canonique de pytest.ini). Ne demande pas les
# donnees : les tests qui en dependent se declarent ignores.
check-tests:
	@$(PYTHON) -m pytest -q

# ===========================================================================
# CHAINE SCIENTIFIQUE COMPLETE  —  `make reproduce`
# ---------------------------------------------------------------------------
# Rejoue l'integralite de l'etat scientifique final rapporte au memoire :
#   donnees sources -> ml_dataset.parquet (ba493568) -> baseline humaine
#   -> entrainement des deux modeles finaux -> calibration H24 et evaluation H25
#   de la couche 2 -> suite de confirmation (chapitre 4.5 du memoire).
#
# Prerequis : archive de donnees en place (README, section Donnees) et
#             environnement installe depuis requirements.txt.
# Duree indicative : ~25 min (jeu) + ~10 min (couche 1 et 2) + ~40 min
#                    (confirmation, dont ~29 min pour c10 seul).
#
# Point de controle decisif : `make check-models` apres reproduce-couche1.
# Un reentrainement iso-protocole DOIT rendre e4ddfccd (bas) et df6a11c5 (haut).
# ===========================================================================
PY_REPRO := OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
            NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 $(PYTHON)

reproduce: reproduce-dataset reproduce-couche1 reproduce-couche2 reproduce-confirmation
	@echo ""
	@echo "==================================================================="
	@echo "  CHAINE SCIENTIFIQUE REJOUEE DE BOUT EN BOUT."
	@echo "  Artefacts : models/enrichi_seg/, outputs/couche2/, outputs/confirmation/"
	@echo "  Controle decisif : make check-models  ->  attendu CONFORME"
	@echo "==================================================================="

# 1 — Jeu de donnees canonique, et verification de son empreinte.
reproduce-dataset: check-sources $(ML_DS)
	@$(PYTHON) -c "import hashlib; \
	    h=hashlib.sha256(open('$(ML_DS)','rb').read()).hexdigest()[:8]; \
	    print('  ml_dataset.parquet -> ' + h + ' (attendu ba493568)'); \
	    raise SystemExit(0 if h=='ba493568' else 1)"

# 2 — Couche 1. `blocs.py` produit d'abord la baseline humaine canonique, que
#     `decision.py` consomme ensuite. Les modeles livres sont mis de cote dans
#     models/_reference/ (ignore par git) avant d'etre reecrits.
reproduce-couche1: reproduce-dataset
	@mkdir -p models/_reference
	@cp -f models/enrichi_seg/enrichi_seg_bas_ba493568.json  models/_reference/ 2>/dev/null || true
	@cp -f models/enrichi_seg/enrichi_seg_haut_ba493568.json models/_reference/ 2>/dev/null || true
	$(PY_REPRO) src/couche2/blocs.py
	$(PY_REPRO) scripts/experiences/phase4_migration_ba493568.py
	@$(MAKE) --no-print-directory check-models

# 3 — Couche 2 : configuration de deploiement (ADR-077) et annexes quantitatives.
reproduce-couche2: reproduce-couche1
	$(PY_REPRO) scripts/experiences/deploiement_c_plancher_ba493568.py
	$(PY_REPRO) src/couche2/annexes.py
	$(PY_REPRO) scripts/experiences/export_pr_courbe_ba493568.py

# 4 — Suite de confirmation. c01 est la porte : si la concordance echoue, arret.
#     Ordre d'execution documente par scripts/confirmation/README.md.
reproduce-confirmation: reproduce-couche2
	$(PY_REPRO) scripts/confirmation/c01_metriques_finales.py
	$(PY_REPRO) scripts/confirmation/c08_shap_segments.py
	$(PY_REPRO) scripts/confirmation/c09_analyse_erreurs.py
	$(PY_REPRO) scripts/confirmation/c02_baseline_m0.py
	$(PY_REPRO) scripts/confirmation/c03_baseline_lineaire.py
	$(PY_REPRO) scripts/confirmation/c04_delta_segmentation.py
	$(PY_REPRO) scripts/confirmation/c06_ablation_simba.py
	$(PY_REPRO) scripts/confirmation/c07_reintegration_statent.py
	$(PY_REPRO) scripts/confirmation/c10_comparatif_algos.py

# 5 — Complements : contrefactuel et SHAP narcisses (section 4.5.7), derivation
#     des cas d'entretien (section 3.4.2), dictionnaire canonique des colonnes.
#     Hors chaine principale.
reproduce-complements: reproduce-couche2
	$(PY_REPRO) scripts/experiences/phase4_contrefactuel_narcisses.py
	$(PY_REPRO) scripts/experiences/phase4_shap_narcisses.py
	$(PY_REPRO) scripts/experiences/candidats_entretien_deploiement_ba493568.py
	$(PY_REPRO) scripts/experiences/selection_cas_entretien_deploiement_ba493568.py
	$(PY_REPRO) scripts/build_codebook_canonique.py

# 6 — Generateurs des figures, tableaux et verifications du manuscrit.
#     Scripts autonomes sous docs/memoire/, chacun executable seul. Passes
#     successives : l'ordre alphabetique ne garantit pas qu'un producteur passe
#     avant son consommateur, la boucle recommence tant qu'elle progresse.
#
#     SKIP_MEMOIRE : deux generateurs sont STRUCTURELLEMENT non reproductibles
#     depuis le depot remis. Ils n'auditent pas l'artefact mais des materiaux que
#     le depot ne porte pas :
#       - audit_selection_six_cas.py atteste par `git log` l'anteriorite du
#         protocole de selection des six cas ; le depot remis est un export a la
#         date de gel, sans historique (memoire, annexe 16.1) ;
#       - verif_v2_prerequis.py audite les notebooks d'exploration, hors perimetre
#         publie (README, section Perimetre).
#     Ils sont declares SKIP et non FAIL : leur non-execution est documentee, pas
#     un defaut. La cible ne sort en erreur que s'il y a un FAIL.
SKIP_MEMOIRE := docs/memoire/verifs/section_3_4_2/audit_selection_six_cas.py \
                docs/memoire/verifs/section_4_3_1/verif_v2_prerequis.py

reproduce-memoire: reproduce-confirmation reproduce-complements
	@tous="$$(find docs/memoire -name '*.py' -not -path '*__pycache__*' | sort)" ; \
	reste="" ; nb_skip=0 ; \
	for f in $$tous ; do \
	  saute=0 ; \
	  for s in $(SKIP_MEMOIRE) ; do [ "$$f" = "$$s" ] && saute=1 ; done ; \
	  if [ $$saute -eq 1 ] ; then \
	    printf '  %-74s SKIP\n' "$$f" ; nb_skip=$$((nb_skip+1)) ; \
	  else reste="$$reste $$f" ; fi ; \
	done ; \
	total=$$(echo $$reste | wc -w | tr -d ' ') ; \
	for passe in 1 2 3 ; do \
	  echec="" ; nb_ok=0 ; \
	  echo "" ; echo "  --- passe $$passe ---" ; \
	  for f in $$reste ; do \
	    if OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
	       NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MPLBACKEND=Agg \
	       $(PYTHON) "$$f" >/dev/null 2>&1 ; \
	    then nb_ok=$$((nb_ok+1)) ; printf '  %-74s OK\n' "$$f" ; \
	    else echec="$$echec $$f" ; fi ; \
	  done ; \
	  echo "  passe $$passe : $$nb_ok reussite(s)" ; \
	  if [ -z "$$echec" ] || [ "$$nb_ok" -eq 0 ] ; then reste="$$echec" ; break ; fi ; \
	  reste="$$echec" ; \
	done ; \
	ko=$$(echo $$reste | wc -w | tr -d ' ') ; \
	echo "" ; \
	echo "  BILAN : $$((total-ko)) OK / $$nb_skip SKIP / $$ko FAIL" ; \
	if [ "$$ko" -gt 0 ] ; then \
	  echo "  En echec :" ; for f in $$reste ; do echo "    $$f" ; done ; \
	  exit 1 ; \
	fi ; \
	echo "  Generateurs du manuscrit : tous rejoues (hors $$nb_skip SKIP documentes)."

# Raccourcis nommés
stage_01:  $(STAGE_01)
stage_02:  $(STAGE_02)
stage_03:  $(STAGE_03)
stage_03b: $(STAGE_03B)
stage_03c: $(STAGE_03C)
stage_03d: $(STAGE_03D)
stage_03e: $(STAGE_03E)
stage_04:  $(STAGE_04)
stage_04b: $(STAGE_04B)
stage_06:  $(STAGE_06)
stage_06b: $(STAGE_06B)
stage_07:  $(STAGE_07_ISTDATEN)
stage_08:  $(STAGE_08)
stage_09:  $(STAGE_09)
stage_10:  $(STAGE_10)

# Tables sources (silver) + référentiels (dimension)
sources: $(APC_STACKED) $(METEO_VEV_CLEAN) $(METEO_CHD_CLEAN) $(HORAIRES_CLEAN)

dims: sources \
      $(DIM_GARE) $(DIM_VACANCES) $(DIM_MANIFESTATIONS) $(DIM_SKI) $(DIM_ROTATIONS) \
      $(DIM_COVID) $(DIM_NARCISSES) \
      $(DIM_VMCV_CONCURRENTES) \
      $(DIM_PROFIL_TRAIN) $(DIM_CORRESPONDANCES) $(DIM_VMCV_PAR_TRAIN_JOUR) $(DIM_HEADWAY) \
      $(DIM_SIMBA_R35)

# ---------------------------------------------------------------------------
# Tables propres par source — scripts/sources/
# ---------------------------------------------------------------------------

$(APC_STACKED): $(RAW_CSV) $(SRC)/stack_raw_csv.py
	$(PYTHON) $(SRC)/stack_raw_csv.py

$(METEO_VEV_CLEAN): $(RAW_METEO) $(SRC)/build_meteosuisse_vev_clean.py
	$(PYTHON) $(SRC)/build_meteosuisse_vev_clean.py

$(METEO_CHD_CLEAN): $(RAW_METEO) $(SRC)/build_meteosuisse_chd_clean.py
	$(PYTHON) $(SRC)/build_meteosuisse_chd_clean.py

$(HORAIRES_CLEAN): $(wildcard data/external/horaires_r35/*.pdf) \
                   $(SRC)/build_horaires_r35_from_pdfs.py $(DIM_GARE)
	$(PYTHON) $(SRC)/build_horaires_r35_from_pdfs.py

# statpop_clean_causal.parquet : branche STATPOP REFABRIQUEE depuis les bruts par le
# forward-fill causal versionne (ADR-076, promotion de la recette d'origine). N'est plus
# une entree figee : sa reproductibilite se verifie par le run vierge (double make), pas
# par un SHA epingle. VVVI (topologie H23) reconstruit dans le producteur ; la ligne inerte
# VVVI-2019 est ajoutee au consommateur (add_statpop..., jamais mobilisee par la jointure Z-2).
$(STATPOP_CLEAN): $(RAW_STATPOP) $(DIM_GARE) $(HORAIRES_CLEAN) \
                  $(SRC)/build_fact_statpop_gare.py
	$(PYTHON) $(SRC)/build_fact_statpop_gare.py

# ISTDATEN : dépend des CSV filtrés (filter_istdaten.sh doit être exécuté manuellement)
$(ISTDATEN_CLEAN): $(DIM_GARE) $(SRC)/build_fact_istdaten_r35.py
	$(PYTHON) $(SRC)/build_fact_istdaten_r35.py

$(ISTDATEN_PONCT): $(ISTDATEN_CLEAN) $(HORAIRES_CLEAN) $(SRC)/build_istdaten_ponctualite.py
	$(PYTHON) $(SRC)/build_istdaten_ponctualite.py

# ---------------------------------------------------------------------------
# Référentiels métier — scripts/sources/
# ---------------------------------------------------------------------------

$(DIM_GARE): data/dimension/gare_abreviation.csv \
             data/dimension/full-world-traffic-point.csv \
             $(SRC)/build_dim_gare.py
	$(PYTHON) $(SRC)/build_dim_gare.py

$(DIM_VACANCES): $(SRC)/build_dim_vacances_feries_vaud.py
	$(PYTHON) $(SRC)/build_dim_vacances_feries_vaud.py

$(DIM_MANIFESTATIONS): $(SRC)/build_dim_manifestations_riviera.py
	$(PYTHON) $(SRC)/build_dim_manifestations_riviera.py

$(DIM_SKI): $(wildcard data/external/ski/ski_*.pdf) \
            $(SRC)/build_dim_ski_pleiades_avec_reconstruction.py
	$(PYTHON) $(SRC)/build_dim_ski_pleiades_avec_reconstruction.py

# dim_rotations_r35 : ENTREE FIGEE DOCUMENTEE (addendum ADR-075). Regeneration
# DESACTIVEE par garde bloquante : la table fait foi par son empreinte
# (688e943b5ea9...), provenance rotations_22_24.csv (brut absent du depot) ; une
# regeneration depuis le brut present (rotations_23_25.csv) produirait une table
# DIFFERENTE et changerait silencieusement la baseline humaine (couche 2).
# Empreinte verifiee par `make check-sources`. Prerequis retires a dessein (la
# cible n'est jamais consideree perimee par un changement de brut).
$(DIM_ROTATIONS):
	@echo "ARRET : dim_rotations_r35 est une entree figee documentee (addendum ADR-075)."
	@echo "  Regeneration desactivee. La table fait foi par empreinte (688e943b5ea9)."
	@echo "  Provenance rotations_22_24.csv (brut absent) ; rotations_23_25.csv donnerait"
	@echo "  une table differente et changerait la baseline humaine (couche 2)."
	@echo "  Voir docs/adr/ADR-075_reproductibilite_statpop_entree_figee.md (addendum) et"
	@echo "  scripts/check_sources.sh."
	@exit 1

$(DIM_COVID): $(SRC)/build_dim_covid.py
	$(PYTHON) $(SRC)/build_dim_covid.py

$(DIM_NARCISSES): $(SRC)/build_dim_narcisses.py
	$(PYTHON) $(SRC)/build_dim_narcisses.py

# build_vmcv_lignes_concurrentes.py produit deux fichiers simultanément
$(DIM_VMCV_CONCURRENTES) $(DIM_VMCV_LIGNES_PAR_GARE): $(SRC)/build_vmcv_lignes_concurrentes.py
	$(PYTHON) $(SRC)/build_vmcv_lignes_concurrentes.py

$(DIM_SIMBA_R35): $(wildcard data/external/simba/*.csv) \
                  $(SRC)/build_fact_simba_r35.py \
                  $(SRC)/build_dim_simba_r35.py
	$(PYTHON) $(SRC)/build_fact_simba_r35.py
	$(PYTHON) $(SRC)/build_dim_simba_r35.py

$(DIM_PROFIL_TRAIN): $(ISTDATEN_CLEAN) $(SRC)/build_dim_profil_train.py
	$(PYTHON) $(SRC)/build_dim_profil_train.py

$(DIM_CORRESPONDANCES): $(ISTDATEN_CLEAN) $(SRC)/build_dim_correspondances_vevey.py
	$(PYTHON) $(SRC)/build_dim_correspondances_vevey.py

$(DIM_VMCV_PAR_TRONCON): $(ISTDATEN_CLEAN) $(DIM_GARE) $(DIM_VMCV_CONCURRENTES) \
                          $(SRC)/build_dim_vmcv_par_troncon.py
	$(PYTHON) $(SRC)/build_dim_vmcv_par_troncon.py

$(DIM_VMCV_PAR_TRAIN_JOUR): $(ISTDATEN_CLEAN) $(DIM_GARE) $(DIM_VMCV_CONCURRENTES) \
                              $(SRC)/build_dim_vmcv_par_train_jour.py
	$(PYTHON) $(SRC)/build_dim_vmcv_par_train_jour.py

$(DIM_HEADWAY): $(ISTDATEN_CLEAN) $(DIM_GARE) $(SRC)/build_dim_headway.py
	$(PYTHON) $(SRC)/build_dim_headway.py

# ---------------------------------------------------------------------------
# Pipeline séquentielle — scripts/pipeline/
# ---------------------------------------------------------------------------

$(STAGE_01): $(APC_STACKED) $(PIPE)/add_annee_horaire_to_raw_stacked.py \
             data/dimension/annees_horaires.csv
	$(PYTHON) $(PIPE)/add_annee_horaire_to_raw_stacked.py

$(STAGE_02): $(STAGE_01) $(DIM_VACANCES) \
             $(PIPE)/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py
	$(PYTHON) $(PIPE)/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py

$(STAGE_03): $(STAGE_02) $(DIM_MANIFESTATIONS) \
             $(PIPE)/add_manifestations_riviera_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_manifestations_riviera_to_raw_stacked.py

$(STAGE_03B): $(STAGE_03) $(DIM_SKI) \
              $(PIPE)/add_ski_pleiades_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_ski_pleiades_to_raw_stacked.py

$(STAGE_03C): $(STAGE_03B) $(DIM_COVID) \
              $(PIPE)/add_covid_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_covid_to_raw_stacked.py

$(STAGE_03D): $(STAGE_03C) $(DIM_NARCISSES) \
              $(PIPE)/add_narcisses_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_narcisses_to_raw_stacked.py

$(STAGE_03E): $(STAGE_03D) \
              $(PIPE)/add_spatial_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_spatial_to_raw_stacked.py

$(STAGE_04): $(STAGE_03E) $(METEO_VEV_CLEAN) $(METEO_CHD_CLEAN) \
             $(PIPE)/add_meteo_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_meteo_to_raw_stacked.py

$(STAGE_04B): $(STAGE_04) $(METEO_VEV_CLEAN) $(METEO_CHD_CLEAN) $(DIM_GARE) \
              $(PIPE)/add_meteo_journaliere_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_meteo_journaliere_to_raw_stacked.py

$(STAGE_06): $(STAGE_04B) $(STATPOP_CLEAN) \
             $(PIPE)/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py
	$(PYTHON) $(PIPE)/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py

# $(STATENT_CLEAN) (statent_clean_causal.parquet) est une ENTREE FIGEE (ADR-075), non
# reconstruite par la chaine et sans producteur canonique : le seul script (archive,
# statent_integration_exp.py, HORS CANONIQUE) est lie au dataset v1.3 (absent), ecrit un
# autre fichier (statent_clean_exp.parquet, contenu different : 86 lignes vs 91). Empreinte
# cede91b9, verifiee par `make check-sources`, epargnee par clean-all. Les colonnes emplois
# alimentent le dataset gele mais sont hors des 158 features du modele.
$(STAGE_06B): $(STAGE_06) $(STATENT_CLEAN) \
              $(PIPE)/add_statent_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_statent_to_raw_stacked.py

$(STAGE_07_ISTDATEN): $(STAGE_06B) $(DIM_PROFIL_TRAIN) $(DIM_CORRESPONDANCES) \
                       $(DIM_VMCV_PAR_TRAIN_JOUR) \
                       $(PIPE)/add_istdaten_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_istdaten_to_raw_stacked.py

$(STAGE_08): $(STAGE_07_ISTDATEN) $(DIM_HEADWAY) \
             $(PIPE)/add_features_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_features_to_raw_stacked.py

$(STAGE_09): $(STAGE_08) $(DIM_SIMBA_R35) \
             $(PIPE)/add_simba_to_raw_stacked.py
	$(PYTHON) $(PIPE)/add_simba_to_raw_stacked.py

$(STAGE_10): $(STAGE_09) $(RESA_XLSX) $(DIM_GARE) \
             $(PIPE)/add_reservations_to_raw_stacked.py \
             $(PIPE)/reservations_utils.py
	$(PYTHON) $(PIPE)/add_reservations_to_raw_stacked.py

$(ML_DS): $(STAGE_10) \
          $(PIPE)/build_ml_dataset.py
	$(PYTHON) $(PIPE)/build_ml_dataset.py

# ---------------------------------------------------------------------------
# Nettoyage
# ---------------------------------------------------------------------------

clean:
	rm -f data/processed/stage_0*.parquet \
	      data/processed/stage_0*.csv \
	      data/processed/stage_0*.tmp.parquet \
	      data/processed/stage_1*.parquet \
	      data/processed/stage_1*.csv \
	      data/processed/stage_1*.tmp.parquet \
	      data/processed/sources/simba_clean.parquet \
	      data/processed/sources/simba_expansion_troncons.parquet

clean-all: clean
	rm -f $(ML_DS) $(ML_DS:.parquet=.csv) \
	      $(APC_STACKED) $(METEO_VEV_CLEAN) $(METEO_CHD_CLEAN) \
	      $(HORAIRES_CLEAN) \
	      $(STATPOP_CLEAN) $(STATPOP_CLEAN:.parquet=.csv) \
	      $(ISTDATEN_CLEAN) $(ISTDATEN_PONCT) \
	      $(DIM_GARE) $(DIM_VACANCES) $(DIM_MANIFESTATIONS) \
	      $(DIM_MANIFESTATIONS:.parquet=.csv) \
	      data/dimension/dim_manifestations_riviera_evenements.parquet \
	      data/dimension/dim_manifestations_riviera_evenements.csv \
	      $(DIM_SKI) $(DIM_SKI:.parquet=.csv)

# ---------------------------------------------------------------------------
# Aide
# ---------------------------------------------------------------------------

help:
	@echo ""
	@echo "  make              Construit ml_dataset.parquet (pipeline complète)"
	@echo "  make dims         Construit tables sources + référentiels"
	@echo "  make sources      Construit uniquement les tables sources (silver)"
	@echo "  make stage_NN     Construit jusqu'au stage NN (01, 02, 03, 03b–03e, 04, 06–10)"
	@echo "  make clean        Supprime les stages intermédiaires"
	@echo "  make clean-all    Supprime stages + sources + ml_dataset"
	@echo ""
	@echo "  WRITE_CSV=1 make  Produit aussi les CSV à chaque étape"
	@echo ""
	@echo "  Note: filter_istdaten.sh doit être exécuté manuellement avant"
	@echo "        make dims (pré-requis des données ISTDATEN filtrées)."
	@echo "        Le script est idempotent : il saute les mois déjà présents."
	@echo "        Couvre 2018-01 → 2024-12 (toutes conventions de nommage LaCie)."
	@echo ""
