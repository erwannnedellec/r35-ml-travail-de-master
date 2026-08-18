# Suite de confirmation — `scripts/confirmation/`

Suite d'évaluation **post-gel, en lecture seule**, exécutée sur le dataset et les modèles
**GELÉS** (dataset `ba493568`, gel v2 ADR-076 ; modèles couche 1 `enrichi_seg_{bas,haut}_ba493568.json`,
empreintes `e4ddfccd` / `df6a11c5`, byte-identiques à v1.9). **La suite évalue, elle ne
sélectionne rien** : elle ne modifie aucun ADR, ni le dataset, ni les modèles canoniques.

## Discipline commune (`_harness.py`)

- `assert sha256[:8](ml_dataset) == ba493568` (via `blocs.assert_canonical_dataset`) ;
- `seed = 42` ; threads numériques épinglés à `1` (contrat ADR-076) ;
- **Split C** : train = H22 (hors Gilamont, BPUIC 8501260) + H23 + H24 (801 282) ; test = H25 (309 252) ;
- métriques préenregistrées : R² (+ IC bootstrap 1000 itérations), MAE, MAE>63, biais>63,
  PR-AUC seuil 63, prévalence, effectifs ; ventilées bas / haut / global ;
- une sortie JSON par script sous `outputs/confirmation/`, préfixée `cNN_` ;
- chaque JSON porte un bloc `meta` (`created_at`, hash dataset, empreintes modèles,
  `n_train`, `n_test`, `h25_contact = "post-gel, lecture seule"`, `h25_version = "corrigée narcisses (ba493568)"`).

**Invariance inter-générations** (`416bb90b` → `ba493568`) : seules les données H25 ont
changé (features narcisses ; train H22-H24 strictement identique). Conséquence outillée :
tout réentraînement 158f segmenté sur Split C **doit reproduire** `e4ddfccd` / `df6a11c5`
(champ `model_reproduction`) ; une divergence = STOP.

## Ordre d'exécution

`c01` (GATE) → `c08`, `c09` (lecture seule) → entraînements `c02`, `c03`, `c04`, `c06`, `c07`, `c10`.
Si la concordance de `c01` échoue, la suite s'arrête.

## Tableau récapitulatif

| Script | Rôle | Statut | Durée réelle | Sortie | Reproduction modèle archivé |
|---|---|---|---|---|---|
| `_harness.py` | Socle commun (asserts, Split C, métriques, méta) | — | — | — | — |
| `c01_metriques_finales.py` | Replay lecture seule des modèles gelés, concordance metadata (**GATE**) | OK | ~19 s | `c01_metriques_finales.json` | concordance R² Δ≤1e-16 + empreintes `e4ddfccd`/`df6a11c5` vérifiées |
| `c02_baseline_m0.py` | Baseline M0 (31f cal_+histo_), global | OK | ~33 s | `c02_baseline_m0.json` | sans objet (pas d'artefact M0 archivé) |
| `c03_baseline_lineaire.py` | Baseline linéaire Ridge (158f), imputation médiane du train | OK | ~93 s | `c03_baseline_lineaire.json` | sans objet |
| `c04_delta_segmentation.py` | Décomposition 2×2 {M0,158}×{global,seg} (**subsume c05**) | OK | ~155 s | `c04_delta_segmentation.json` | `158_seg` = gel réutilisé (identique) ; cellules réentraînées sans objet |
| `c06_ablation_simba.py` | Ablation SIMBA : 158f vs 170f (+12 `simba_part_*`) | OK | ~163 s | `c06_ablation_simba.json` | **bras 158f = `e4ddfccd`/`df6a11c5` reproduits (identical=true)** |
| `c07_reintegration_statent.py` | Réintégration STATENT : 158f vs 162f (+4 colonnes emploi) | OK | ~160 s | `c07_reintegration_statent.json` | **bras 158f = `e4ddfccd`/`df6a11c5` reproduits (identical=true)** |
| `c08_shap_segments.py` | SHAP par segment (mean\|SHAP\| complet, top 20 + CSV) | OK | ~542 s | `c08_shap_segments.json` + 3 CSV | gel lecture seule (empreintes vérifiées) |
| `c09_analyse_erreurs.py` | Résidus/tranche, mois horaire, connus vs renumérotés | OK | ~14 s | `c09_analyse_erreurs.json` | gel lecture seule |
| `c10_comparatif_algos.py` | Comparatif ADR-072 (canonique + naïve + RF + 3 boostings) | OK | ~29 min | `c10_comparatif_algos.json` | canonique = gel lecture seule ; comparateurs sans objet |

## Notes de périmètre

- **c05 non produit** : la décomposition 2×2 de `c04` couvre le Δ enrichissement (158−M0) et le
  Δ segmentation (seg−global) d'un bloc.
- **c07 (STATENT)** : aucune colonne préfixée `statent_` dans le parquet ; les données d'emploi
  STATENT sont 4 colonnes `spatial_gare_{depart,arrivee}_emplois_500m_{total,services}` (toutes hors
  des 158f, ADR-064). Le test est une **réintégration** (158 vs 162), pas un retrait.
- **c09 (renumérotation)** : deux clés rapportées telles quelles. `horaire_service_id_complet`
  (composite numéro+heure) est **dégénérée** sur H25 (intersection H24↔H25 vide, horaires décalés →
  0 « connu ») ; `horaire_numero_train` donne une stratification non dégénérée.
- **c10 (ADR-072)** : run de **confirmation post-gel**. Le verdict d'ADR-072 (indiscernabilité des
  boostings tunés, conservation de XGBoost aux HP CF09/ADR-052) est **FIGÉ** et n'est pas rouvert.
  RandomForest `n_jobs=-1` = vitesse seule (déterministe à `random_state` fixé), comme le premier
  temps historique. Métriques H24 de validation reportées telles quelles (`h24_validation_source`).

## Contacts H25

Tous les scripts lisent H25 (test out-of-time) : autorisé (modèle gelé, ADR-076). Chaque contact
est tracé (`meta.h25_contact = "post-gel, lecture seule"`). Aucun script ne réentraîne sur H25 ni ne
modifie un artefact gelé. Les entraînements (c02/c03/c04/c06/c07/c10) s'ajustent sur le **train
Split C** (H22-H24) et n'évaluent H25 qu'en prédiction.
