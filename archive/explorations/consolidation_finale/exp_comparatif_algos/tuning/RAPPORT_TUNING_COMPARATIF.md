# Tuning comparatif XGBoost / LightGBM / CatBoost par Optuna — architecture segmentée

**Statut** : hors canonique. Hash `416bb90b`, `ml_dataset.parquet`, pipeline et **modèles canoniques intacts** (lecture seule ; hash revérifié en fin de run).
**Emplacement** : `consolidation_finale/exp_comparatif_algos/tuning/`
**Script** : `tuning_comparatif_algos.py` (réexécutable : `python tuning_comparatif_algos.py [n_trials]`).
**Sorties** : `best_params_{xgboost,lightgbm,catboost}.json`, `trials_{algo}.csv`, `tuning_resultats.json`.

## 1. Objectif

Comparer XGBoost, LightGBM et CatBoost, **chacun optimisé par Optuna au même budget**, dans l'**architecture
segmentée** de l'artefact (un modèle BAS + un modèle HAUT, aiguillage par `spatial_segment`, exactement comme
CF09), pour déterminer le meilleur régresseur de charge. Test de robustesse du choix d'algorithme ; **la décision
de modèle final reste ouverte**, prise au vu des résultats. Aucune promotion de modèle ici.

## 2. Verrou méthodologique (absolu)

- Le tuning Optuna se fait **exclusivement** sur le train (H22 hors Gilamont + H23 + H24, Split C).
- **H25 n'est jamais vu pendant l'optimisation**, sous aucune forme (ni tuning, ni early stopping, ni choix du n° d'arbres).
- H25 n'est révélé **qu'une seule fois**, tout à la fin, sur les modèles déjà **figés**, avec CF09 comme repère
  et la baseline naïve comme plancher.
- Garde-fou : le hash `416bb90b` est vérifié en début **et** en fin de script.

## 3. Protocole — iso-canonique sauf l'algorithme

| Élément | Valeur |
|---|---|
| Dataset | `ml_dataset.parquet`, hash `416bb90b` (lecture seule) |
| Features | 158f (`features_158f_sans_simba.json`), identiques au canonique |
| Cible | `target_voyageurs_2eme_classe` |
| Architecture | **Segmentée** BAS+HAUT pour les 3 algos ; HP **partagés** BAS/HAUT dans un essai (comme CF09) ; aiguillage `spatial_segment`. **Jamais de modèle global monolithique.** |
| Train | H22 (Gilamont 8501260 exclu) + H23 + H24 = 801 282 |
| Test H25 | 309 252 — révélé une seule fois |
| Seed | 42 (TPE + modèles) |

## 4. Validation Optuna — walk-forward temporel dans le train

3 plis **expanding window**, construits **uniquement dans le train**, par **date** (`base_date`), en ordre
chronologique strict (aucune fuite futur → passé). Les dates uniques du train (1 069 dates, 2021-12 → 2024-12)
sont découpées en 4 blocs chronologiques ; les plis sont :

| Pli | Train (dates) | Validation (dates) |
|---|---|---|
| 1 | bloc 0 | bloc 1 |
| 2 | blocs 0–1 | bloc 2 |
| 3 | blocs 0–2 | bloc 3 |

Le découpage par **date** (et non par ligne) évite qu'une même journée soit à cheval train/val.
**Métrique optimisée** : RMSE de validation, **moyenné sur les 3 plis**, calculé sur les **deux segments réunis**
(critère unique par essai). Le **RMSE est le juge principal**, cohérent avec ADR-CF09 qui définit la couche 1
comme un régresseur de charge.

## 5. Budget & échantillonnage

- **40 essais Optuna par algorithme**, échantillonneur **TPE**, seed 42.
- **Early stopping (40 rounds)** pendant chaque essai, sur le pli de validation ; plafond d'arbres **600**
  (l'early stopping coupe avant si la validation stagne).
- Le n° d'arbres du modèle figé = moyenne des `best_iteration` des 3 plis, **par segment** (BAS et HAUT séparément),
  puis refit sur le train complet à ce nombre fixe (sans early stopping, donc **sans jamais regarder H25**).

## 6. Espaces de recherche (générosité comparable, adaptés par bibliothèque)

Chaque algorithme explore : taux d'apprentissage (log), complexité (profondeur / nombre de feuilles), n° d'arbres
(via early stopping ≤ 600), sous-échantillonnage de lignes, sous-échantillonnage de colonnes, et 2–3 termes de
régularisation. Aucun n'est avantagé.

| Dimension | XGBoost | LightGBM | CatBoost |
|---|---|---|---|
| learning_rate | loguniform[0.01, 0.3] | loguniform[0.01, 0.3] | loguniform[0.01, 0.3] |
| complexité | max_depth int[3, 10] | num_leaves int[15, 255] + max_depth int[3, 12] | depth int[4, 10] |
| lignes | subsample[0.6, 1.0] | subsample[0.6, 1.0] (bagging_freq=1) | subsample[0.6, 1.0] (bootstrap Bernoulli) |
| colonnes | colsample_bytree[0.6, 1.0] | colsample_bytree[0.6, 1.0] | rsm[0.6, 1.0] |
| feuille min | min_child_weight int[1, 10] | min_child_samples int[5, 100] | min_data_in_leaf int[1, 100] |
| régularisation | reg_lambda log[1e-2,10], reg_alpha log[1e-3,10] | reg_lambda log[1e-2,10], reg_alpha log[1e-3,10] | l2_leaf_reg log[1,30], random_strength log[1e-3,10] |
| n_arbres | ≤ 600, early stopping (40) | ≤ 600, early stopping (40) | ≤ 600, early stopping (40) |

Les paramétrisations diffèrent (LightGBM est *leaf-wise* → `num_leaves` ; XGBoost/CatBoost *depth-wise*), mais le
nombre de degrés de liberté et l'amplitude des plages sont équivalents. La régularisation de CatBoost est
paramétrée différemment (`l2_leaf_reg` + `random_strength`) mais de cardinalité comparable.

## 7. Critère de conclusion (posé AVANT de voir les résultats)

Un algorithme n'est déclaré **meilleur** que si son avantage en RMSE sur les autres est **stable sur les 3 plis
de validation** *et* **se confirme sur H25**. Si les trois se tiennent dans un écart **inférieur à la variabilité
inter-plis** observée, on conclut à l'**indiscernabilité** : on ne départage pas sur le RMSE, et le choix relève
alors des **critères secondaires** (explicabilité, intégration Dataiku, maturité, maîtrise interne).
La métrique d'arbitrage (RMSE) n'est **jamais** modifiée a posteriori.

## 8. Table de résultats — H25 (révélé une seule fois)

*(40 essais/algo. Source : `tuning_resultats.json`, valeurs calculées, jamais retapées. RMSE = juge principal.)*

### GLOBAL
| Modèle | RMSE | R² | PR-AUC | MAE | MAE>63 | biais>63 |
|---|---:|---:|---:|---:|---:|---:|
| **catboost (Optuna seg)** | **11,400** | 0,6198 | 0,4686 | 7,470 | 29,40 | −29,06 |
| lightgbm (Optuna seg) | 11,459 | 0,6159 | 0,4609 | 7,491 | 28,87 | −28,40 |
| xgboost (Optuna seg) | 11,534 | 0,6108 | 0,4564 | 7,578 | 30,17 | −29,83 |
| CF09 canonique (repère) | 11,674 | 0,6013 | 0,4490 | 7,712 | 29,09 | −28,47 |
| Baseline naïve (plancher) | 16,687 | 0,1855 | 0,0557 | 11,388 | 56,02 | −56,02 |

### BAS
| Modèle | RMSE | R² | PR-AUC | MAE | MAE>63 | biais>63 |
|---|---:|---:|---:|---:|---:|---:|
| catboost (Optuna seg) | 11,744 | 0,6007 | 0,4883 | 8,035 | 27,11 | −26,72 |
| lightgbm (Optuna seg) | 11,747 | 0,6005 | 0,4853 | 8,039 | 26,53 | −25,99 |
| xgboost (Optuna seg) | 11,856 | 0,5931 | 0,4788 | 8,117 | 27,85 | −27,46 |
| CF09 canonique (repère) | 11,947 | 0,5868 | 0,4687 | 8,169 | 27,20 | −26,51 |
| Baseline naïve (plancher) | 17,500 | 0,1135 | 0,0581 | 12,522 | 53,43 | −53,43 |

### HAUT
| Modèle | RMSE | R² | PR-AUC | MAE | MAE>63 | biais>63 |
|---|---:|---:|---:|---:|---:|---:|
| catboost (Optuna seg) | 10,343 | 0,4848 | 0,3712 | 5,838 | 45,55 | −45,54 |
| xgboost (Optuna seg) | 10,550 | 0,4639 | 0,3368 | 6,019 | 46,45 | −46,45 |
| lightgbm (Optuna seg) | 10,581 | 0,4608 | 0,3330 | 5,909 | 45,35 | −45,35 |
| CF09 canonique (repère) | 10,847 | 0,4334 | 0,3452 | 6,389 | 42,40 | −42,27 |
| Baseline naïve (plancher) | 14,075 | 0,0459 | 0,0251 | 8,110 | 74,21 | −74,21 |

### Validation Optuna — train walk-forward 3 plis (juge principal)
| Algo | CV-RMSE moyen | std inter-plis | plis (1 / 2 / 3) | n_arbres BAS/HAUT | tuning |
|---|---:|---:|---|---:|---:|
| catboost | 10,4928 | 0,7897 | 11,508 / 10,387 / 9,583 | 440 / 276 | 128 min |
| lightgbm | 10,4943 | 0,7687 | 11,480 / 10,400 / 9,604 | 453 / 175 | 37 min |
| xgboost | 10,5506 | 0,7530 | 11,511 / 10,468 / 9,672 | 536 / 313 | 94 min |

**Écart inter-algos CV-RMSE = 0,058** · **variabilité inter-plis moyenne = 0,771** · écart inter-algos H25 = 0,134.

### Meilleurs hyperparamètres (sauvegardés en JSON)
- **xgboost** : lr 0,021 · max_depth 8 · subsample 0,84 · colsample 0,62 · min_child_weight 9 · λ 6,03 · α 0,030
- **lightgbm** : lr 0,034 · num_leaves 71 · max_depth 11 · subsample 0,63 · colsample 0,60 · min_child_samples 49 · λ 0,041 · α 3,82
- **catboost** : lr 0,071 · depth 9 · subsample 0,93 · rsm 0,82 · min_data_in_leaf 8 · l2 2,68 · random_strength 0,005

## 9. Synthèse & verdict

**Verdict (critère §7, non modifié a posteriori) : INDISCERNABILITÉ sur le RMSE.**

Les trois algorithmes de boosting, optimisés au même budget, se tiennent en **0,058 de CV-RMSE** — soit **≈ 13×
moins que la variabilité inter-plis** (0,771). L'ordre CatBoost ≳ LightGBM ≳ XGBoost se retrouve sur H25 mais dans
un mouchoir (**0,134 de RMSE global**, ΔR² ≈ 0,009 entre le meilleur et XGBoost). L'avantage de CatBoost n'est
**pas stable au regard de la variabilité de validation** : le critère pré-posé conclut donc à l'indiscernabilité, et
**on ne départage pas sur le RMSE**. Le choix relève des **critères secondaires** : explicabilité (SHAP par segment),
intégration Dataiku, maturité de la bibliothèque, maîtrise interne.

Observations factuelles complémentaires :
- **Tous les modèles ML battent largement la baseline naïve** : RMSE global ~11,4–11,5 vs **16,7** ; PR-AUC ~0,46
  vs **0,056** ; R² ~0,61–0,62 vs **0,19**. Confirme H1 sur une base tunée.
- **Le tuning n'apporte qu'un gain marginal** sur le canonique : vs CF09, le meilleur (CatBoost) gagne **−0,27 de
  RMSE global** et **+0,019 de R²** — cohérent avec le constat Optuna antérieur (le réglage change peu sur ce
  problème). Le peloton tuné se place juste au-dessus de CF09.
- **Segment HAUT** : CatBoost s'y détache un peu plus nettement (R² 0,485 vs 0,46/0,46 pour xgb/lgbm ; PR-AUC 0,371
  vs ~0,33), mais ce segment porte une variance de réentraînement structurelle connue (ADR-CF09), à ne pas
  surinterpréter sur un écart de cet ordre.
- **Coût** : CatBoost et XGBoost sont ~3× plus lents que LightGBM à budget égal (128 / 94 / 37 min) — un critère
  secondaire d'exploitation, pas de performance.

**Aucune décision de promotion de modèle. Le canonique 416bb90b/CF09 est intact. Arrêt après la table — on interprète
et on décide ensemble.**
