# INDEX canonique des ADR (Architecture Decision Records)

Document **canonique** de traçabilité des décisions du projet R35. Registre **gelé au 2026-08-16**
par [ADR-078](ADR-078_cloture_du_registre.md).

**78 ADR** : ADR-001 à ADR-077, plus l'ADR-078 de clôture.

## Comment lire ce registre

Un ADR consigne une décision **telle qu'elle a été prise à un instant donné**. Il n'est pas
retravaillé rétroactivement (mémoire, §3.3) : le registre documente le cheminement, y compris
les pistes abandonnées, et non une position finale continûment révisée.

Conséquence pratique : **un ADR au statut `remplacé` ou `révoqué` décrit une décision qui n'est
plus en vigueur.** Chaque fichier porte, sous son titre, un bandeau d'état qui donne son statut
au gel et le renvoi vers l'ADR qui l'a modifié. Deux colonnes de la table ci-dessous signalent
en outre les documents dont les **chiffres** sont périmés, sans que la décision le soit :

- *seuil 94* — les décomptes de surcharge précèdent ADR-060 (seuil en vigueur : **63**) ;
- *génération < `ba493568`* — les métriques précèdent la migration de gel ADR-076
  (`416bb90b` → `ba493568`) et ne sont pas réalignées.

## Règle d'ordonnancement

Ordre strictement chronologique par **date de décision**. À date égale, départage par dépendance
logique (un ADR qui en cite un autre vient après), puis par ordre alphabétique du nom de fichier
d'origine. L'ancien identifiant reste tracé en front-matter (`ancien_id`).

## Table de correspondance

| Id | Ancien id | Date | Titre | Statut au gel | Relations | Chiffres périmés | Corrob. git |
|---|---|---|---|---|---|---|---|
| [ADR-001](ADR-001_cible_2eme_classe.md) | ADR-01 | 2026-05 | Changement de cible : `charge_totale` → `target_voyageurs_2eme_classe` | **amendé** | amendé par ADR-060 | seuil 94 | dépôt de travail, commit du 2026-05-12 |
| [ADR-002](ADR-002_split_temporel.md) | ADR-02 | 2026-05 | Stratégie de split temporel : scénario candidat H17–H22 / H23 / H24 | ~~remplacé~~ | remplacé par ADR-027 | — | dépôt de travail, commit du 2026-05-12 |
| [ADR-003](ADR-003_modele_unique_vs_separes.md) | ADR-03 | 2026-05 | Architecture modèle : unique + feature `base_segment` vs deux modèles séparés | ~~remplacé~~ | remplacé par ADR-052 ; révoqué par ADR-022 | — | dépôt de travail, commit du 2026-05-12 |
| [ADR-004](ADR-004_seuil_um_86.md) | ADR-04 (seuil_um_86) | 2026-05 | ~~Ancrage du seuil UM : `SEUIL_UM = 86`~~ — ARCHIVÉ | ~~remplacé~~ | remplacé par ADR-005 | — | dépôt de travail, commit du 2026-05-12 |
| [ADR-005](ADR-005_seuil_um_94_2c.md) | ADR-04 (seuil_um_94_2c) | 2026-05 | Seuil UM : `SEUIL_UM_2C = 63` (places assises 2ème classe SURF 7500) | **amendé** | amendé par ADR-060 | seuil 94 | dépôt de travail, commit du 2026-06-04 |
| [ADR-006](ADR-006_statpop_dernier_millesime_disponible.md) | ADR-06 | 2026-05 | STATPOP : stratégie du dernier millésime disponible | ~~remplacé~~ | remplacé par ADR-039, ADR-063 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-007](ADR-007_rotations_tours_service.md) | ADR-07 | 2026-05 | Tours de service : table de rotations externe nécessaire pour la couche de décision | **amendé** | amendé par ADR-073 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-008](ADR-008_lag_operationnel_J-2.md) | ADR-08 | 2026-05 | Décalage opérationnel J-2 pour les features historiques APC | ~~remplacé~~ | remplacé par ADR-062 ; précisé par ADR-015 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-009](ADR-009_grain_lag_avec_annee_horaire.md) | ADR-09 | 2026-05 | Grain de groupement des features historiques : inclusion de l'année horaire | ~~remplacé~~ | remplacé par ADR-037, ADR-042, ADR-044, ADR-062 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-010](ADR-010_famille_features_historiques.md) | ADR-10 | 2026-05 | Famille des features historiques APC : 6 statistiques par variable | **amendé** | amendé par ADR-019, ADR-037, ADR-060 | seuil 94 | dépôt de travail, commit du 2026-06-04 |
| [ADR-011](ADR-011_imputation_millesimes_statpop_manquants.md) | ADR-11 | 2026-05 | Imputation des millésimes STATPOP manquants (2021, 2023) | ~~remplacé~~ | remplacé par ADR-063 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-012](ADR-012_grain_train_istdaten.md) | ADR-12 | 2026-05-15 | Refonte ISTDATEN au grain date × numero_train | ~~remplacé~~ | remplacé par ADR-019 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-013](ADR-013_ponctualite_valeur_absolue.md) | ADR-13 | 2026-05-15 | Convention de ponctualité par valeur absolue | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-014](ADR-014_fenetre_correspondance_vevey.md) | ADR-14 | 2026-05-15 | Fenêtre de correspondance Vevey [-20, -2] minutes | ~~remplacé~~ | remplacé par ADR-019 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-015](ADR-015_logique_operationnelle_j_moins_2.md) | ADR-15 | 2026-05-15 | Logique opérationnelle J-2 pour les features ISTDATEN | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-016](ADR-016_stabilite_numeros_train_r35.md) | ADR-16 | 2026-05-15 | Stabilité des numéros de train R35 sur la période modélisable | ~~révoqué~~ | révoqué par ADR-019, ADR-038 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-017](ADR-017_ablation_horaire_numero_train.md) | ADR-18 | 2026-05-15 | Ablation empirique de la feature horaire_numero_train | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-018](ADR-018_feature_horaire_headway_emergente.md) | ADR-19 | 2026-05-15 | Features ist_headway_* depuis ISTDATEN exclusivement | **amendé** | amendé par ADR-067 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-019](ADR-019_refonte_features_ist_grain_troncon_rolling_type_jour.md) | ADR-21 | 2026-05-17 | Refonte des features ISTDATEN : grain tronçon + rolling par type de jour | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-020](ADR-020_refonte_features_vmcv_concurrence_modale.md) | ADR-22 | 2026-05-18 | Refonte des features VMCV : concurrence modale au grain tronçon | ~~remplacé~~ | remplacé par ADR-021 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-021](ADR-021_refonte_vmcv_decision_embarquement.md) | ADR-23 | 2026-05-18 | Refonte VMCV : décision à l'embarquement, grain train × jour × sens | actif | précisé par ADR-040 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-022](ADR-022_disponibilite_j_moins_1.md) | ADR-05 | 2026-05-21 | Disponibilité J-1 des features et stratégie météo horaire | actif | amendé par ADR-028 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-023](ADR-023_feeders_vevey_ir90_ir.md) | ADR-24 | 2026-05-21 | Inclusion de IR90 et IR dans les feeders Vevey | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-024](ADR-024_selection_features_statpop.md) | ADR-25 | 2026-05-21 | Sélection de features STATPOP : retrait des redondances arithmétiques | actif | amendé par ADR-025 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-025](ADR-025_buffer_voronoi_par_annee_horaire.md) | ADR-26 | 2026-05-21 | Refonte du buffer STATPOP : Voronoi clippé par année horaire | **amendé** | amendé par ADR-039, ADR-063 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-026](ADR-026_integration_simba_fqkal_lag_n_moins_1.md) | ADR-27 | 2026-05-21 | Intégration SIMBA FQkal avec lag N-1 systématique | ~~révoqué~~ | révoqué par ADR-061 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) | ADR-28 | 2026-05-22 | Split temporel : H22+H23 entraînement / H24 test | ~~révoqué~~ | amendé par ADR-065 ; révoqué par ADR-038 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-028](ADR-028_enrichissement_features_meteo_journalieres.md) | ADR-29 | 2026-05-23 | Enrichissement des features météo : agrégats journaliers J, J-1, J+1 | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-029](ADR-029_reclassification_zonale_et_decomposition_par_localite_r35.md) | ADR-30 | 2026-05-23 | Reclassification zonale Montreux et décomposition événementielle par localité R35 | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) | ADR-31 | 2026-05-28 | Révision de la stratégie de modélisation suite au découplage R²/rappel sur la classe surcharge | **amendé** | amendé par ADR-031 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-031](ADR-031_verdict_modelisation_classe_rare_et_segmentation.md) | ADR-32 | 2026-05-28 | Verdict empirique sur la modélisation de la classe rare et décision d'explorer la segmentation | **amendé** | amendé par ADR-033 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-032](ADR-032_perimetre_materiel_et_coherence_temporelle.md) | ADR-33 | 2026-05-29 | Périmètre matériel et cohérence temporelle : H16 exclu, H17–H22 écartés de l'entraînement, H23–H24 retenus comme périmètre SURF cohérent | ~~révoqué~~ | révoqué par ADR-034 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-033](ADR-033_pivot_architectural_regression_augmentation_metier.md) | ADR-34 | 2026-05-29 | Pivot architectural : régression continue + augmentation métier en couche 2 | ~~remplacé~~ | remplacé par ADR-036, ADR-052 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-034](ADR-034_perimetre_base_offre_qualite_diagnostique.md) | ADR-36 | 2026-05-29 | Périmètre `base_offre_2eme_classe` : qualité diagnostique sans impact sur l'entraînement ML | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-035](ADR-035_integration_reservations_couche_1.md) | ADR-37 | 2026-06-03 | Intégration des réservations de groupes ResSys en couche 1 du pipeline ML | **amendé** | amendé par ADR-036 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-036](ADR-036_adoption_modele_reference_avec_reservations.md) | ADR-38 | 2026-06-03 | Adoption du modèle de référence enrichi des features réservations (couche 1) | **amendé** | amendé par ADR-072 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-037](ADR-037_grain_histo_type_jour_service.md) | ADR-39 | 2026-06-04 | Grain enrichi des features histo_* : conditionnement par type de jour et identification par service | ~~remplacé~~ | remplacé par ADR-042, ADR-044 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-038](ADR-038_extension_perimetre_h25.md) | ADR-40 | 2026-06-04 | Extension du périmètre temporel à H25 | **amendé** | amendé par ADR-065 | génération < `ba493568` | dépôt de travail, commit du 2026-06-04 |
| [ADR-039](ADR-039_carry_forward_statpop_h25.md) | ADR-41 | 2026-06-04 | Mapping STATPOP par année calendaire et carry-forward 2024 pour 2025 | ~~remplacé~~ | remplacé par ADR-063 | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-040](ADR-040_gestion_interruption_vmcv_istdaten_h25.md) | ADR-42 | 2026-06-04 | Gestion de l'interruption VMCV ISTDATEN H25 (01.09 – 13.10.2025) | actif | — | — | dépôt de travail, commit du 2026-06-04 |
| [ADR-041](ADR-041_simba_refonte_horaire_h25.md) | ADR-43 | 2026-06-05 | Gestion de la refonte d'horaire H24→H25 sur les features SIMBA | ~~remplacé~~ | remplacé par ADR-056 ; révoqué par ADR-061 | génération < `ba493568` | dépôt de travail, commit du 2026-06-05 |
| [ADR-042](ADR-042_creneau_histo_30min.md) | ADR-CF01 | 2026-06-05 | Clé de groupement créneau ±30 min pour les features histo_* | **amendé** | amendé par ADR-044, ADR-062 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-043](ADR-043_creneau_simulation_RF1.md) | ADR-CF01b | 2026-06-05 | Simulation de refonte d'horaire : test de validation de RF-1 | actif | — | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-044](ADR-044_creneau_avec_sens.md) | ADR-CF01c | 2026-06-05 | Ajout de `base_sens` à la clé de groupement créneau | **amendé** | amendé par ADR-062 | — | déclaratif (aucun commit d'époque) |
| [ADR-045](ADR-045_grille_factorielle_etape2.md) | ADR-CF02 | 2026-06-05 | Grille factorielle 2×3 sur H25 : résultats étape 2 | ~~révoqué~~ | révoqué par ADR-046, ADR-052 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-046](ADR-046_critere_calibration_seuil_wf.md) | ADR-CF03 | 2026-06-05 | Critère de calibration du seuil Walk-Forward | ~~révoqué~~ | révoqué par ADR-052 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-047](ADR-047_robustesse_hyperparametres.md) | ADR-CF04 | 2026-06-05 | Robustesse hyperparamètres et sélection du candidat final (couche 1) | ~~remplacé~~ | remplacé par ADR-052 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-048](ADR-048_feature_selection_externe.md) | ADR-CF05 | 2026-06-06 | Feature selection contrôlée des sources externes | ~~remplacé~~ | remplacé par ADR-050, ADR-052 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-049](ADR-049_cadrage_bas_haut.md) | ADR-CF06 | 2026-06-06 | Cadrage bas/haut : angle mort et stratégie de seuil | ~~révoqué~~ | révoqué par ADR-052, ADR-073 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-050](ADR-050_regression_weighting.md) | ADR-CF07 | 2026-06-06 | Grille régression features × architecture et sample weighting | ~~remplacé~~ | remplacé par ADR-069 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-051](ADR-051_pertes_alternatives_quantile_tweedie.md) | ADR-CF08 | 2026-06-06 | Pertes alternatives : quantile regression et Tweedie | ~~remplacé~~ | remplacé par ADR-069 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-052](ADR-052_modele_final_couche1_enrichi_seg.md) | ADR-CF09 | 2026-06-06 | Modèle final couche 1 : Enrichi_Seg (MSE, 170 features, architecture segmentée) | **amendé** | amendé par ADR-061, ADR-076 | seuil 94, génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-053](ADR-053_shap_explicabilite.md) | ADR-CF10 | 2026-06-06 | SHAP Enrichi_Seg : explicabilité des modèles BAS et HAUT | **amendé** | amendé par ADR-054 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-054](ADR-054_nettoyage_parcimonie.md) | ADR-CF11 | 2026-06-06 | Nettoyage de parcimonie : 179 → 171 → 172 → 170 features | **amendé** | amendé par ADR-061 | seuil 94 | déclaratif (aucun commit d'époque) |
| [ADR-055](ADR-055_correction_voronoi_vvvi_statpop_2022.md) | ADR-CF12 | 2026-06-07 | Correction du Voronoï STATPOP manquant pour VVVI (millésimes 2022 et 2023) | ~~remplacé~~ | remplacé par ADR-063 | — | déclaratif (aucun commit d'époque) |
| [ADR-056](ADR-056_simba_jointure_nan_confirme.md) | ADR-CF13 | 2026-06-07 | Jointure SIMBA : NaN tracé confirmé après investigation exhaustive | ~~révoqué~~ | révoqué par ADR-061 | — | déclaratif (aucun commit d'époque) |
| [ADR-057](ADR-057_denivele_troncon_spatial.md) | ADR-CF14 | 2026-06-07 | Feature topologique : dénivelé signé du tronçon (`spatial_denivele_troncon_m`) | actif | — | — | déclaratif (aucun commit d'époque) |
| [ADR-058](ADR-058_dim_ski_regeneree_saison_25_26_partielle.md) | ADR-CF15 (dim_ski) | 2026-06-07 | Régénération dim_ski_pleiades + intégration partielle saison 2025-2026 | **amendé** | amendé par ADR-059 | — | déclaratif (aucun commit d'époque) |
| [ADR-059](ADR-059_garde_defensive_cible_coerce.md) | ADR-CF15 (garde_defensive) | 2026-06-07 | Garde défensive sur le calcul de la cible (coerce silencieux) | actif | — | — | déclaratif (aucun commit d'époque) |
| [ADR-060](ADR-060_seuil_surcharge_63_seats.md) | ADR-CF16 | 2026-06-09 | Correction du seuil de surcharge 2ème classe : 94 → 63 | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-061](ADR-061_retrait_simba_features.md) | ADR-CF17 | 2026-06-11 | Retrait définitif des 12 features SIMBA du modèle de couche 1 | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-062](ADR-062_virage_leakage_histo_apc.md) | ADR-CF18 | 2026-06-16 | Virage leakage temporel APC : cutoff mensuel, tronçon dans la clé histo_*, fenêtre win7 | actif | — | génération < `ba493568` | dépôt de travail, commit du 2026-06-21 |
| [ADR-063](ADR-063_causalite_disponibilite_statpop.md) | ADR-CF19 | 2026-06-16 | Causalité de disponibilité STATPOP : mapping Z-2 conservateur, forward-fill causal, correction géographique VVVI | actif | — | génération < `ba493568` | dépôt de travail, commit du 2026-06-21 |
| [ADR-064](ADR-064_integration_statent_emploi_500m.md) | ADR-CF20 | 2026-06-18 | Intégration STATENT emploi 500m (couche 1, v1.4) | ~~révoqué~~ | révoqué par ADR-064 | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-065](ADR-065_split_c_exclusion_gilamont_h22.md) | ADR-CF21 | 2026-06-18 | Split C : exclusion des tronçons Gilamont H22, conservation du reste de H22 | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-066](ADR-066_gouvernance_empreintes_hash_dataset.md) | ADR-CF22 | 2026-06-20 | Gouvernance des empreintes de hash des datasets (SHA256[:8], rupture MD5→SHA256) | **amendé** | amendé par ADR-076 | génération < `ba493568` | dépôt de travail, commit du 2026-06-21 |
| [ADR-067](ADR-067_headway_grille_planifiee.md) | ADR-CF23 | 2026-06-20 | Headway calculé sur la grille horaire planifiée connue à J-1 (annulés et suppléments inclus) | actif | — | génération < `ba493568` | dépôt de travail, commit du 2026-06-21 |
| [ADR-068](ADR-068_retrait_id_gare_features.md) | ADR-CF24 | 2026-06-22 | Traçabilité a posteriori du retrait des identifiants de gare (`id_gare_*`) de la liste de features | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-069](ADR-069_conservation_perte_mse.md) | ADR-CF25 | 2026-06-28 | Conservation de la perte MSE (`reg:squarederror`) : leviers de perte testés et écartés | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-070](ADR-070_features_vacances_feries_cantonales.md) | ADR-CF26 | 2026-06-28 | Features vacances/fériés cantonaux (VS/FR/NE/GE) : testées et écartées | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-071](ADR-071_tuning_hyperparametres_optuna.md) | ADR-CF27 | 2026-06-28 | Conservation des hyperparamètres ADR-052 : optimisation Optuna conduite, CF09 confirmé robuste out-of-time | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-072](ADR-072_comparaison_algorithmes_confirmation_xgboost.md) | ADR-CF28 | 2026-07-03 | Comparaison d'algorithmes et confirmation de XGBoost pour la couche 1 | actif | — | génération < `ba493568` | déclaratif (aucun commit d'époque) |
| [ADR-073](ADR-073_probleme_decision_couche2.md) | ADR-44 | 2026-07-04 | Problème de décision de la couche 2 : seuillage calibré des prédictions couche 1 au grain course (POC d'aide à la décision) | **amendé** | amendé par ADR-077 | génération < `ba493568` | dépôt de travail, commit du 2026-07-04 |
| [ADR-074](ADR-074_perimetre_environnement_python_local.md) | aucun | 2026-07-09 | Périmètre d'environnement : artefact intégralement en Python local, déploiement Dataiku écarté du travail de master | actif | — | génération < `ba493568` | dépôt de travail, commit du 2026-07-09 |
| [ADR-075](ADR-075_reproductibilite_statpop_entree_figee.md) | aucun | 2026-07-10 | Reproductibilité de la branche STATPOP : entrée figée rematérialisée depuis le dataset gelé, invariant clean-all redéfini | **amendé** | amendé par ADR-076 | génération < `ba493568` | dépôt de travail, commit du 2026-07-10 |
| [ADR-076](ADR-076_migration_gel_dataset_v2.md) | aucun | 2026-07-11 | Migration de gel : dataset v2 (correction du producteur narcisses + promotion de la recette STATPOP au pipeline) | actif | — | — | dépôt de travail, commit du 2026-07-11 |
| [ADR-077](ADR-077_configuration_deploiement_c_plancher.md) | aucun | 2026-07-12 | Configuration de déploiement recommandée : règle c + plancher réservations | actif | — | — | en attente |
| [ADR-078](ADR-078_cloture_du_registre.md) | aucun | 2026-08-16 | Clôture du registre à la remise du travail de master | actif | — | — | gel de remise |

## Chaînes de supersession

Toutes les relations ci-dessous sont désormais **explicites** dans le front-matter des deux ADR
concernés et dans leur bandeau. Elles ne l'étaient pas toutes au fil du projet : l'établissement
de cette table fait partie de la clôture du registre (ADR-078 §1).

| Décision d'origine | Nature | Portée par | Objet de la décision d'origine |
|---|---|---|---|
| ADR-001 | amendement | **ADR-060** | Changement de cible : `charge_totale` → `target_voyageurs_2eme_classe` |
| ADR-002 | remplacement | **ADR-027** | Stratégie de split temporel : scénario candidat H17–H22 / H23 / H24 |
| ADR-003 | remplacement | **ADR-052** | Architecture modèle : unique + feature `base_segment` vs deux modèles séparés |
| ADR-003 | révocation | **ADR-022** | Architecture modèle : unique + feature `base_segment` vs deux modèles séparés |
| ADR-004 | remplacement | **ADR-005** | ~~Ancrage du seuil UM : `SEUIL_UM = 86`~~ — ARCHIVÉ |
| ADR-005 | amendement | **ADR-060** | Seuil UM : `SEUIL_UM_2C = 63` (places assises 2ème classe SURF 7500) |
| ADR-006 | remplacement | **ADR-039** | STATPOP : stratégie du dernier millésime disponible |
| ADR-006 | remplacement | **ADR-063** | STATPOP : stratégie du dernier millésime disponible |
| ADR-007 | amendement | **ADR-073** | Tours de service : table de rotations externe nécessaire pour la couche de décision |
| ADR-008 | précision | **ADR-015** | Décalage opérationnel J-2 pour les features historiques APC |
| ADR-008 | remplacement | **ADR-062** | Décalage opérationnel J-2 pour les features historiques APC |
| ADR-009 | remplacement | **ADR-037** | Grain de groupement des features historiques : inclusion de l'année horaire |
| ADR-009 | remplacement | **ADR-042** | Grain de groupement des features historiques : inclusion de l'année horaire |
| ADR-009 | remplacement | **ADR-044** | Grain de groupement des features historiques : inclusion de l'année horaire |
| ADR-009 | remplacement | **ADR-062** | Grain de groupement des features historiques : inclusion de l'année horaire |
| ADR-010 | amendement | **ADR-019** | Famille des features historiques APC : 6 statistiques par variable |
| ADR-010 | amendement | **ADR-037** | Famille des features historiques APC : 6 statistiques par variable |
| ADR-010 | amendement | **ADR-060** | Famille des features historiques APC : 6 statistiques par variable |
| ADR-011 | remplacement | **ADR-063** | Imputation des millésimes STATPOP manquants (2021, 2023) |
| ADR-012 | remplacement | **ADR-019** | Refonte ISTDATEN au grain date × numero_train |
| ADR-014 | remplacement | **ADR-019** | Fenêtre de correspondance Vevey [-20, -2] minutes |
| ADR-016 | révocation | **ADR-019** | Stabilité des numéros de train R35 sur la période modélisable |
| ADR-016 | révocation | **ADR-038** | Stabilité des numéros de train R35 sur la période modélisable |
| ADR-018 | amendement | **ADR-067** | Features ist_headway_* depuis ISTDATEN exclusivement |
| ADR-020 | remplacement | **ADR-021** | Refonte des features VMCV : concurrence modale au grain tronçon |
| ADR-021 | précision | **ADR-040** | Refonte VMCV : décision à l'embarquement, grain train × jour × sens |
| ADR-022 | amendement | **ADR-028** | Disponibilité J-1 des features et stratégie météo horaire |
| ADR-024 | amendement | **ADR-025** | Sélection de features STATPOP : retrait des redondances arithmétiques |
| ADR-025 | amendement | **ADR-039** | Refonte du buffer STATPOP : Voronoi clippé par année horaire |
| ADR-025 | amendement | **ADR-063** | Refonte du buffer STATPOP : Voronoi clippé par année horaire |
| ADR-026 | révocation | **ADR-061** | Intégration SIMBA FQkal avec lag N-1 systématique |
| ADR-027 | amendement | **ADR-065** | Split temporel : H22+H23 entraînement / H24 test |
| ADR-027 | révocation | **ADR-038** | Split temporel : H22+H23 entraînement / H24 test |
| ADR-030 | amendement | **ADR-031** | Révision de la stratégie de modélisation suite au découplage R²/rappel sur la classe surcharge |
| ADR-031 | amendement | **ADR-033** | Verdict empirique sur la modélisation de la classe rare et décision d'explorer la segmentation |
| ADR-032 | révocation | **ADR-034** | Périmètre matériel et cohérence temporelle : H16 exclu, H17–H22 écartés de l'entraînement, H23–H24 retenus comme périmètre SURF cohérent |
| ADR-033 | remplacement | **ADR-036** | Pivot architectural : régression continue + augmentation métier en couche 2 |
| ADR-033 | remplacement | **ADR-052** | Pivot architectural : régression continue + augmentation métier en couche 2 |
| ADR-035 | amendement | **ADR-036** | Intégration des réservations de groupes ResSys en couche 1 du pipeline ML |
| ADR-036 | amendement | **ADR-072** | Adoption du modèle de référence enrichi des features réservations (couche 1) |
| ADR-037 | remplacement | **ADR-042** | Grain enrichi des features histo_* : conditionnement par type de jour et identification par service |
| ADR-037 | remplacement | **ADR-044** | Grain enrichi des features histo_* : conditionnement par type de jour et identification par service |
| ADR-038 | amendement | **ADR-065** | Extension du périmètre temporel à H25 |
| ADR-039 | remplacement | **ADR-063** | Mapping STATPOP par année calendaire et carry-forward 2024 pour 2025 |
| ADR-041 | remplacement | **ADR-056** | Gestion de la refonte d'horaire H24→H25 sur les features SIMBA |
| ADR-041 | révocation | **ADR-061** | Gestion de la refonte d'horaire H24→H25 sur les features SIMBA |
| ADR-042 | amendement | **ADR-044** | Clé de groupement créneau ±30 min pour les features histo_* |
| ADR-042 | amendement | **ADR-062** | Clé de groupement créneau ±30 min pour les features histo_* |
| ADR-044 | amendement | **ADR-062** | Ajout de `base_sens` à la clé de groupement créneau |
| ADR-045 | révocation | **ADR-046** | Grille factorielle 2×3 sur H25 : résultats étape 2 |
| ADR-045 | révocation | **ADR-052** | Grille factorielle 2×3 sur H25 : résultats étape 2 |
| ADR-046 | révocation | **ADR-052** | Critère de calibration du seuil Walk-Forward |
| ADR-047 | remplacement | **ADR-052** | Robustesse hyperparamètres et sélection du candidat final (couche 1) |
| ADR-048 | remplacement | **ADR-050** | Feature selection contrôlée des sources externes |
| ADR-048 | remplacement | **ADR-052** | Feature selection contrôlée des sources externes |
| ADR-049 | révocation | **ADR-052** | Cadrage bas/haut : angle mort et stratégie de seuil |
| ADR-049 | révocation | **ADR-073** | Cadrage bas/haut : angle mort et stratégie de seuil |
| ADR-050 | remplacement | **ADR-069** | Grille régression features × architecture et sample weighting |
| ADR-051 | remplacement | **ADR-069** | Pertes alternatives : quantile regression et Tweedie |
| ADR-052 | amendement | **ADR-061** | Modèle final couche 1 : Enrichi_Seg (MSE, 170 features, architecture segmentée) |
| ADR-052 | amendement | **ADR-076** | Modèle final couche 1 : Enrichi_Seg (MSE, 170 features, architecture segmentée) |
| ADR-053 | amendement | **ADR-054** | SHAP Enrichi_Seg : explicabilité des modèles BAS et HAUT |
| ADR-054 | amendement | **ADR-061** | Nettoyage de parcimonie : 179 → 171 → 172 → 170 features |
| ADR-055 | remplacement | **ADR-063** | Correction du Voronoï STATPOP manquant pour VVVI (millésimes 2022 et 2023) |
| ADR-056 | révocation | **ADR-061** | Jointure SIMBA : NaN tracé confirmé après investigation exhaustive |
| ADR-058 | amendement | **ADR-059** | Régénération dim_ski_pleiades + intégration partielle saison 2025-2026 |
| ADR-064 | révocation | **ADR-064** | Intégration STATENT emploi 500m (couche 1, v1.4) |
| ADR-066 | amendement | **ADR-076** | Gouvernance des empreintes de hash des datasets (SHA256[:8], rupture MD5→SHA256) |
| ADR-073 | amendement | **ADR-077** | Problème de décision de la couche 2 : seuillage calibré des prédictions couche 1 au grain course (POC d'aide à la décision) |
| ADR-075 | amendement | **ADR-076** | Reproductibilité de la branche STATPOP : entrée figée rematérialisée depuis le dataset gelé, invariant clean-all redéfini |

## Numéros absents de l'ancienne série simple

- **ADR-17, ADR-20** : réservés, jamais créés, objet non reconstitué.
- **ADR-35** : numéro réservé de façon prospective pour la « décision finale sur l'architecture »
  (modèle unique vs deux modèles spécialisés), référencé par le générateur du notebook 07. La
  décision a été prise sous ADR-CF09, devenu **ADR-052** ; le numéro 35 n'a jamais été consommé.
- **ADR-39bis** : identifiant conditionnel cité dans ADR-037 et ADR-038 (« si une régression
  majeure du PR-AUC survient sur H25 »). La condition ne s'est pas réalisée : cet ADR n'a jamais
  été créé. Les mentions sont conservées au titre de la trace des contrats.

## Mentions Dataiku

Environnement d'expérimentation de la phase initiale et cible de déploiement alors envisagée.
Les runs et valeurs Dataiku (dont le R² 0,613) sont des jalons historiques non reproductibles ;
la lignée canonique a été refondée en Python (ADR-074). Le déploiement opérationnel est hors
périmètre du travail de master.

## Migration de gel ADR-076

La migration **ADR-076** remplace le hash canonique `416bb90b` par **`ba493568`** (producteur
narcisses corrigé sur H25, branche STATPOP refabriquée depuis les bruts, threads fixés à 1).
Les ADR portant des chiffres d'une génération antérieure sont signalés colonne « Chiffres
périmés » et dans leur bandeau — cette liste corrige et complète celle de l'index d'époque, qui
en omettait plusieurs. `416bb90b` reste la trace historique ; aucun résultat n'est effacé.

## Décisions du mémoire sans ADR propre

Le registre est dense sur la fabrique du modèle et plus lacunaire sur les protocoles d'évaluation
et d'inférence. Ces décisions sont énumérées et consignées a posteriori à
[ADR-078 §3](ADR-078_cloture_du_registre.md), à la date de clôture et sans rétrodatage.
