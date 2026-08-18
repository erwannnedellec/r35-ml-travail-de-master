---
id: ADR-072
ancien_id: ADR-CF28
date_decision: 2026-07-03
statut: actif
modifie: [ADR-036]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-072 : Comparaison d'algorithmes et confirmation de XGBoost pour la couche 1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-036.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Décision figée |
| **Date** | 2026-07-03 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-052 (hyperparamètres et architecture, confirmés ici), ADR-060 (seuil de surcharge 63), ADR-061 (retrait SIMBA), ADR-064 (retrait STATENT), ADR-065 (Split C), ADR-049 (segmentation BAS et HAUT), ADR-071 (optimisation Optuna des hyperparamètres, complémentaire), ADR-036 (structure de raisonnement conservée, chiffres périmés, voir section dédiée) |
| **Version modèle** | Enrichi_Seg v1.9 (158 features, Split C, hash dataset `416bb90b`), inchangée |
| **Nature** | Décision méthodologique et point de référence à jour de l'état canonique. Aucun changement de modèle, de dataset, de hash, de pipeline. |

---

## 1. Contexte et déclencheur

Le directeur du travail de master a relevé, lors de la revue du travail de modélisation, qu'un seul algorithme (XGBoost) avait été mis en oeuvre pour la couche 1, sans comparaison à d'autres familles d'apprentissage, et a demandé une justification du choix. Cette justification, honnêtement, n'existait pas au moment du commentaire. Le choix initial de XGBoost reposait sur la pratique courante et la maîtrise de l'outil, pas sur une démonstration empirique documentée que cet algorithme était le mieux adapté au problème.

Plutôt que de construire a posteriori un argumentaire théorique, qui aurait été fragile et peu convaincant, la démarche retenue a été de produire la justification manquante par une comparaison empirique rigoureuse, menée à protocole strictement contrôlé. Le présent ADR acte cette comparaison, en tire la décision sur les algorithmes, et sert simultanément de point de référence à jour de l'état du modèle canonique.

---

## 2. Description exacte et vérifiée du modèle canonique

Le bloc ci-dessous est repris de `models/enrichi_seg/enrichi_seg_metadata.json` (version 1.9, créée le 2026-06-20). Il fait de cet ADR la référence à jour de l'état canonique.

| Élément | Valeur |
|---|---|
| Architecture | Deux régresseurs XGBoost segmentés, un modèle BAS et un modèle HAUT, aiguillage par `spatial_segment` |
| Objectif | `reg:squarederror` (MSE) |
| Hyperparamètres | n_estimators 300, max_depth 6, learning_rate 0.1, subsample 0.8, colsample_bytree 0.8, seed 42 (ADR-052) |
| Features | 158, sans SIMBA (ADR-061), sans STATENT (ADR-064) |
| Cible | `target_voyageurs_2eme_classe` |
| Seuil de surcharge | 63 (ADR-060) |
| Dataset | `data/processed/ml_dataset.parquet`, hash SHA256 tronqué `416bb90b` |
| Split | Split C (ADR-065), entraînement H22 hors tronçons Gilamont (BPUIC 8501260) plus H23 plus H24, test H25 |
| Tailles | 801 282 observations d'entraînement, 309 252 observations de test H25 |
| Empreintes modèles | BAS `e4ddfccd`, HAUT `df6a11c5` |
| Version | 1.9 |

Métriques H25 du canonique (source `enrichi_seg_metadata.json`, clé `metrics_h25`), pour mémoire et comme repère de la comparaison :

| Segment | R² | MAE | PR-AUC tronçon | n surcharges (>63) |
|---|---:|---:|---:|---:|
| BAS | 0.5868 | 8.169 | 0.4687 | 8 392 |
| HAUT | 0.4334 | 6.389 | 0.3452 | 1 192 |
| GLOBAL | 0.6013 | 7.712 | 0.4490 | 9 584 |

---

## 3. Méthode de comparaison, en deux temps

### 3.1 Premier temps, comparaison à paramètres par défaut

Cinq approches ont été comparées aux paramètres par défaut de leur bibliothèque, sans aucun réglage, sur le protocole iso-canonique (mêmes 158 features, dataset `416bb90b`, Split C, architecture segmentée, seed 42) :

1. une baseline naïve par moyenne historique, qui prédit pour chaque ligne H25 la charge 2e classe moyenne observée dans le train (H22 à H24, aucune donnée H25) pour la même combinaison de tronçon, de numéro de course et de type de jour (ouvré ou week-end), avec un repli en cascade documenté vers des moyennes moins conditionnées lorsque la combinaison est absente du train,
2. Random Forest (scikit-learn),
3. XGBoost par défaut,
4. LightGBM par défaut,
5. CatBoost par défaut.

Ce premier temps situe XGBoost parmi les alternatives et mesure de combien les modèles d'apprentissage dépassent la baseline naïve, ce qui teste directement l'hypothèse H1 du proposal (les variables temporelles et contextuelles améliorent la prévision par rapport à la seule récurrence historique).

Note sur la couverture de la baseline. La clé complète (tronçon, numéro de course, type de jour) ne retrouve son équivalent historique que pour 53.69 pour cent des lignes H25. La refonte horaire H25 renumérote les courses, ce qui fait basculer 42.36 pour cent des lignes vers le repli (tronçon, type de jour). Cette fragilité face à un changement d'offre est une limite intrinsèque de l'approche historique seule, pas un artefact de mesure.

### 3.2 Second temps, optimisation Optuna à budget égal

Le premier temps prête le flanc à une objection d'équité : les paramètres par défaut ne sont pas également soignés d'une bibliothèque à l'autre, si bien qu'un écart faible peut refléter la qualité des défauts plutôt qu'une supériorité de fond. Pour neutraliser cette objection, les trois méthodes de boosting (XGBoost, LightGBM, CatBoost) ont été optimisées par Optuna à budget strictement égal, 40 essais par algorithme, échantillonneur TPE, seed 42, avec des espaces de recherche de générosité comparable (taux d'apprentissage, complexité, sous-échantillonnage de lignes et de colonnes, régularisation, nombre d'arbres borné à 600 via early stopping).

Verrou méthodologique. L'optimisation se déroule exclusivement sur le train (H22 hors Gilamont plus H23 plus H24), en validation temporelle walk-forward à trois plis construite par date à l'intérieur du seul train, en fenêtre expansive respectant l'ordre chronologique. Le holdout H25 n'est jamais vu pendant l'optimisation et n'est révélé qu'une seule fois, tout à la fin, sur les modèles figés, à côté du canonique CF09 comme repère et de la baseline naïve comme plancher.

Métrique optimisée. Le RMSE de validation, moyenné sur les trois plis, calculé sur les deux segments réunis pour donner un critère unique par essai. Ce choix est cohérent avec le critère de la couche 1, définie comme régresseur de charge dans l'ADR-052, et non comme détecteur de surcharge (qui relève de la couche 2).

Vérification d'iso-conditions. Il a été vérifié, à partir des scripts et de leurs sorties, que le comparatif tourne sur exactement les 158 features du canonique (fichier `features_158f_sans_simba.json`, sans SIMBA ni STATENT), sur le même dataset `416bb90b` (hash recalculé et contrôlé en début et en fin d'exécution), en architecture segmentée BAS et HAUT. Seul l'algorithme varie.

---

## 4. Résultats

Tous les chiffres ci-dessous sont lus depuis les sorties réelles (`tuning_resultats.json`, `comparatif_resultats.json` et fichiers associés), aucun n'est reconstruit à la main.

### 4.1 Validation (train walk-forward, juge principal RMSE)

| Algorithme | RMSE de validation (moyenne 3 plis) | Écart-type entre plis |
|---|---:|---:|
| CatBoost | 10.4928 | 0.7897 |
| LightGBM | 10.4943 | 0.7687 |
| XGBoost | 10.5506 | 0.7530 |

L'écart de RMSE entre les trois boostings vaut 0.0577. La variabilité moyenne entre plis vaut 0.7705. Le premier est très inférieur à la seconde (environ treize fois plus petit).

### 4.2 Holdout H25 (révélé une seule fois)

| Modèle | RMSE global | R² global | PR-AUC tronçon global |
|---|---:|---:|---:|
| CatBoost (Optuna, segmenté) | 11.400 | 0.6198 | 0.4686 |
| LightGBM (Optuna, segmenté) | 11.459 | 0.6159 | 0.4609 |
| XGBoost (Optuna, segmenté) | 11.534 | 0.6108 | 0.4564 |
| CF09 canonique (repère) | 11.674 | 0.6013 | 0.4490 |
| Baseline naïve (plancher) | 16.687 | 0.1855 | 0.0557 |

Sur H25, l'ordre des trois boostings est CatBoost, puis LightGBM, puis XGBoost, dans un mouchoir : l'écart de RMSE global entre le meilleur et XGBoost vaut 0.1341, soit environ 0.009 de R² global.

### 4.3 Dépassement de la baseline naïve (hypothèse H1)

Tous les modèles d'apprentissage dépassent largement la baseline naïve. Sur la PR-AUC tronçon globale, ils atteignent de l'ordre de 0.46 contre 0.056 pour la baseline, soit un facteur voisin de huit. Sur le RMSE global, ils descendent autour de 11.4 contre 16.7. Sur le R² global, ils atteignent de l'ordre de 0.61 à 0.62 contre 0.19. L'écart est encore plus net sur le segment HAUT, où la PR-AUC des boostings tunés (0.33 à 0.37) dépasse la baseline (0.025) d'un facteur voisin de treize à quinze. Ce résultat valide l'hypothèse selon laquelle les variables temporelles et contextuelles améliorent significativement la prévision par rapport à la seule récurrence historique.

Pour mémoire, le premier temps (paramètres par défaut) donne la même hiérarchie d'ensemble : les trois boostings et Random Forest dépassent tous la baseline, Random Forest reste en retrait des boostings (PR-AUC globale 0.3887 contre 0.43 à 0.46), et les défauts de LightGBM et CatBoost devancent légèrement le défaut de XGBoost, ce qui motivait précisément le passage au second temps à budget égal.

---

## 5. Verdict et justification du choix

**Ce passage est celui que le décideur doit relire et s'approprier en priorité, car c'est l'argument qui sera défendu en soutenance.**

### 5.1 Indiscernabilité de performance

L'écart de performance entre les trois algorithmes de boosting est très inférieur à la variabilité de mesure. En validation, 0.0577 de RMSE d'écart entre algorithmes contre 0.7705 de variabilité entre plis. Aucun des trois ne domine de façon statistiquement fiable. Le critère de conclusion, posé avant de voir les résultats, était précisément le suivant : un algorithme n'est déclaré meilleur que si son avantage est stable en validation et se confirme sur H25, faute de quoi on conclut à l'indiscernabilité et on ne départage pas sur le RMSE. Ce critère conduit ici à l'indiscernabilité. Le travail antérieur de tuning (ADR-071) a de plus montré qu'un écart de cet ordre ne se maintient pas d'un jeu de données à l'autre, un gain apparent en validation ou sur une année pouvant s'inverser sur l'année suivante.

Il faut assumer explicitement, sans le masquer, que CatBoost arrive numériquement en tête, à la fois en validation (RMSE 10.4928) et sur H25 (RMSE global 11.400, R² global 0.6198). Cet avantage est réel dans les chiffres, mais il n'est pas fiable au sens statistique, l'écart vivant à l'intérieur de la variabilité de mesure. Là où CatBoost se détache un peu plus, sur le segment HAUT (R² 0.4848 et PR-AUC 0.3712 contre 0.46 et 0.33 pour les deux autres), il s'agit précisément du segment à plus forte variance de réentraînement, documentée dans l'ADR-052, où un écart de cet ordre ne doit pas être surinterprété.

Il faut de plus noter que les gains numériques des configurations optimisées sur les métriques de surface (RMSE et R²) se paient sur la classe rare. La section 6 le détaille sur XGBoost, où un R² global un peu meilleur s'accompagne d'une dégradation de la zone de surcharge (>63) et de la PR-AUC du segment HAUT, ce qui est le mauvais arbitrage pour une couche 1 destinée à alimenter la détection de surcharge en couche 2 (tension R² et rappel de classe rare, ADR-030 et ADR-031).

### 5.2 Justification de XGBoost sur les critères secondaires

L'indiscernabilité de performance étant établie, le choix ne peut pas et ne doit pas se faire sur le RMSE. Il se fait sur les critères secondaires prescrits par le cadre CRISP-ML(Q) de Studer et al., qui invitent explicitement à considérer, au delà de la performance brute, l'explicabilité, la maintenabilité et l'adéquation au contexte de déploiement.

Sur l'explicabilité, il faut être précis pour ne pas surclasser XGBoost à tort. Les trois boostings sont également explicables, puisque ce sont des ensembles d'arbres compatibles avec TreeSHAP. Le vrai choix d'explicabilité n'a pas été XGBoost contre CatBoost, mais le gradient boosting contre le deep learning opaque. En retenant une famille d'arbres explicable par SHAP plutôt qu'un réseau de neurones, la modélisation répond directement au gap XAI identifié dans la revue de littérature, celui d'un besoin de prévisions interprétables par l'opérateur pour la décision d'unité multiple. Ce point est solide et défendable.

Les critères qui départagent ensuite XGBoost au sein du trio sont les suivants : la maturité et la robustesse éprouvée de l'écosystème SHAP autour de XGBoost, et la maîtrise interne de l'outil, qui réduit le risque de mise en oeuvre et de maintenance. Ces critères, dans un contexte d'indiscernabilité de performance, justifient de conserver XGBoost.

---

## 6. Décision sur les hyperparamètres

Les hyperparamètres du canonique (ADR-052) sont conservés et ne sont pas remplacés par ceux issus d'Optuna. La justification demande de la précision, car elle ne peut pas se réduire à un simple constat d'écart nul.

Il faut d'abord reconnaître honnêtement que la configuration XGBoost optimisée par Optuna est, sur les métriques de surface, légèrement meilleure que CF09 sur H25 : R² global 0.6108 contre 0.6013 (un gain de l'ordre de 0.0095, hors de l'intervalle de confiance bootstrap de CF09), MAE global 7.578 contre 7.712, PR-AUC globale 0.4564 contre 0.4490. Écrire que l'optimisation n'apporte aucun gain serait donc inexact et réfutable.

Le refus d'adopter cette configuration repose sur deux arguments solides. Premièrement, le gain global se paie sur la zone opérationnellement critique. Sur le segment HAUT, celui qui alimente la détection de surcharge en couche 2, la configuration optimisée gagne du R² (0.4639 contre 0.4334) mais dégrade la PR-AUC (0.3368 contre 0.3452) et sous-prédit davantage les surcharges (biais au-dessus de 63 de -46.45 contre -42.27, MAE au-dessus de 63 de 46.45 contre 42.40). Pour une couche 1 dont la finalité est de nourrir la détection de surcharge, améliorer l'ajustement du gros de la distribution au prix de la classe rare est le mauvais arbitrage (tension R² et rappel de classe rare, ADR-030 et ADR-031). Deuxièmement, la gouvernance interdit de choisir sur le holdout. L'avantage de la configuration optimisée n'est visible que sur H25 (le CV walk-forward n'a pas été calculé pour CF09, il n'existe donc aucune preuve en validation que le réglage optimisé batte CF09), or basculer parce qu'une configuration paraît meilleure sur H25 reviendrait à décider sur un test qui doit rester vu une seule fois.

Ces deux arguments convergent avec l'ADR-071, dont le critère d'adoption pré-posé, appliqué à des optimisations Optuna de XGBoost, avait déjà conclu à la non-adoption au motif que les gains ne se maintenaient pas hors échantillon et dégradaient les métriques de la zone de surcharge.

Formulé positivement, le comparatif confirme que le réglage du canonique est déjà dans une zone raisonnable, aucune configuration alternative ne le dominant à la fois sur la performance globale et sur la zone de surcharge. Ce résultat est cohérent avec le constat de fond du projet, à savoir que la performance est bornée par le signal disponible à J moins 1 plutôt que par le choix de l'algorithme ou par le réglage de ses hyperparamètres (voir aussi ADR-071). Les meilleurs hyperparamètres trouvés par Optuna pour chaque algorithme sont archivés dans les fichiers `best_params_*.json` à titre de trace, sans être promus.

---

## 7. Liens et cohérence documentaire

Les ADR faisant foi pour l'état canonique sont : ADR-052 (hyperparamètres et architecture segmentée), ADR-060 (seuil de surcharge 63), ADR-061 (retrait de SIMBA), ADR-064 (retrait de STATENT), ADR-065 (Split C), ADR-049 (segmentation BAS et HAUT). Le présent ADR-072 complète l'ADR-071 (optimisation Optuna des hyperparamètres) en portant la comparaison au niveau du choix d'algorithme.

Avertissement sur l'ADR-036. L'ADR-036 conserve sa valeur pour la structure de raisonnement sur les hyperparamètres et sur l'apport des features de réservation, mais ses chiffres de features et de seuil sont périmés. Il mentionne 160 puis 168 features et un seuil de surcharge à 94 ou 80. L'état actuel est de 158 features (après retrait de SIMBA par ADR-061 et de STATENT par ADR-064) et un seuil de surcharge à 63 (ADR-060). Aucun lecteur ne doit prendre les chiffres de l'ADR-036 pour l'état courant.

---

## 8. Fichiers sources des chiffres

Les valeurs de ce document sont tirées des fichiers suivants, en lecture seule :

- `models/enrichi_seg/enrichi_seg_metadata.json` : description et métriques H25 du canonique (section 2).
- `consolidation_finale/exp_comparatif_algos/tuning/tuning_resultats.json` : RMSE de validation, écarts entre plis, résultats H25 des boostings tunés, verdict (sections 4.1, 4.2, 4.3, 5).
- `consolidation_finale/exp_comparatif_algos/tuning/best_params_xgboost.json`, `best_params_lightgbm.json`, `best_params_catboost.json` : meilleurs hyperparamètres archivés (section 6).
- `consolidation_finale/exp_comparatif_algos/comparatif_resultats.json` : comparaison à paramètres par défaut et couverture de la baseline naïve (sections 3.1, 4.3).
- `consolidation_finale/exp_comparatif_algos/comparatif_algos.py` et `tuning/tuning_comparatif_algos.py` : scripts réexécutables du comparatif et vérification d'iso-conditions (section 3).

Aucune valeur nécessaire à la rédaction n'était absente des sorties. Toutes les valeurs citées proviennent des fichiers ci-dessus.
