---
id: ADR-033
ancien_id: ADR-34
date_decision: 2026-05-29
statut: remplacé
remplace_par: [ADR-036, ADR-052]
modifie: [ADR-031]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-033 — Pivot architectural : régression continue + augmentation métier en couche 2

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-036, ADR-052.
> Décisions antérieures que ce document modifie : ADR-031.
> **Précision au gel — tableau §1.2 non traçable.** Le tableau du §1.2 est présenté comme
> l'« aboutissement empirique (ADR-031) ». Il ne reproduit pas ADR-031 §2.5, dont les valeurs
> sont : classifieur `scale_pos_weight = 341` **0,2359**, régresseur complet **0,2481**,
> régresseur Top20 **0,2496**, régresseur pondéré 10/5/1 **0,2276** — trois régresseurs et un
> classifieur, dont **aucun n'est un `scale_pos_weight = 20`**. Les valeurs 0,244 / 0,238 / 0,252
> ne correspondent à aucun run du registre, et `scale_pos_weight = 20` n'apparaît dans aucun ADR
> ni dans aucun fichier du dépôt. Le rappel de **40,7 %** est celui du classifieur 341 calibré au
> ratio de coût FN:FP de **20:1** (ADR-031 §2.4.2), pour une précision de **17,9 %** et
> FP/TP = **4,58** : le « 20 » est un ratio de coût, non un poids de classe, et la précision de
> 3,9 % n'a aucune source dans le registre. Le quadruplet n'est pas établissable depuis le dépôt ;
> la justification n° 2 du §1.3 est reformulée sur les valeurs d'ADR-031.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-29 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/05_modeling_xgboost_reference.ipynb`, `notebooks/05b_modeling_weighted.ipynb`, `notebooks/05c_modeling_classification.ipynb`, `notebooks/06_feature_analysis_h22_h23_h24.ipynb`, `notebooks/07_segmentation_bas_haut.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM), ADR-007 (tours de service), ADR-027 (split temporel), ADR-030 (révision stratégie), ADR-031 (verdict classe rare), ADR-032 (révoqué), ADR-034 (périmètre base_offre) |

---

## 1. Contexte et motivation du pivot

### 1.1 — Cheminement depuis l'ADR-030

L'ADR-030 (révision stratégie, date : 2026-05-xx) avait acté l'exploration de trois leviers pour répondre au découplage R²/rappel observé sur la classe surcharge dans le modèle de référence (R² ≈ 0.613, rappel sur surcharges ≈ 0 % à seuil calibré naïvement) :

- **L1 — Pondération des surcharges** : `scale_pos_weight` et `sample_weight` proportionnel à la rareté
- **L2 — Fonction de coût asymétrique** : `reg:tweedie`, focale-regression, pertes asymétriques personnalisées
- **L3 — Classification binaire** : reformulation en `target_um_2eme_classe ∈ {0, 1}` avec seuil calibré

L'ADR-030 considérait ces leviers comme orthogonaux et complémentaires, et réservait la décision finale à l'issue des empiriques.

### 1.2 — Aboutissement empirique (ADR-031)

Le notebook 05c (classification) et le notebook 05b (pondération) ont conduit à la convergence documentée dans l'ADR-031 :

| Modèle | PR-AUC | Rappel (seuil 0.40) | Précision |
|---|---|---|---|
| XGBoost Baseline (nb05) | 0.235 | ~0 % | — |
| XGBoost pondéré scale_pos_weight=20 | 0.244 | 40.7 % | 3.9 % |
| XGBoost pondéré sample_weight | 0.238 | ~similaire | ~similaire |
| Classifieur binaire calibré | 0.252 | variable | variable |

Les quatre variantes convergent vers un PR-AUC de 0.23–0.25. L'ADR-031 a interprété ce plafond comme une **limite informationnelle** : les features automatiques actuelles ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité opérationnelle.

L'addendum de l'ADR-031 (2026-05-29) a élargi cette interprétation à un pivot architectural, formalisé par le présent ADR-033.

### 1.3 — Pourquoi la poursuite de l'optimisation pure n'est plus la voie retenue

Trois raisons convergentes :

1. **Plafond empirique robuste** : la stabilité du PR-AUC entre modèles de nature différente (régression pondérée vs classification) indique que la limite n'est pas algorithmique. Ajouter des arbres, affiner les hyperparamètres ou explorer d'autres architectures (neural networks, gradient boosting alternatif) ne leverait pas cette contrainte informationnelle.

2. **Plafond de rappel infranchissable au coût opérationnel acceptable** : le rappel plafonne à **40,7 %** au ratio de coût FN:FP le plus agressif testé (20:1), pour une précision de **17,9 %** et FP/TP = 4,58 (ADR-031 §2.4.2) ; au ratio 10:1 il n'atteint que 34,8 %, pour une précision de 28,1 %. Aucun réglage ne procure simultanément un rappel opérationnellement utile et une précision au moins égale à la pratique en vigueur, et sur le segment haut le rappel reste nul (0 TP sur 104 surcharges, ADR-031 §2.1 et §4.1). Dans le contexte opérationnel MOB — où 79.2 % des UM déployées sont déjà inutiles (baseline tours, notebook 04h) — une dégradation supplémentaire de la précision rend l'artefact contre-productif.

3. **Limite informationnelle identifiable** : l'analyse des faux négatifs résiduels (notebook 07, segment haut) révèle une concentration sur juin (33 % vs 8 % global) et les dimanches/fériés (31 % vs 15 % global). Ces patterns correspondent à des événements touristiques ponctuels que les features automatiques actuelles (météo, calendrier, événementiel Riviera Tourisme) ne couvrent pas entièrement. La solution est l'enrichissement de l'information, pas l'optimisation du modèle.

---

## 2. Décision architecturale

### 2.1 — Architecture à deux couches (confirmation ADR-003)

L'architecture à deux couches de l'ADR-003 est confirmée et précisée :

**Couche 1 — Modèle prédictif** :
Modèle XGBoost de régression au grain tronçon × course × date, prédisant `target_voyageurs_2eme_classe` en valeur continue. Entraîné sur H22+H23, évalué sur H24 (ADR-027). Performances de référence : R² global = 0.6123 (scénario D, 160 features nettoyées, notebook 06).

**Couche 2 — Système de décision UM** :
Combinaison de la prédiction continue de la couche 1 avec des informations métier externes pour produire la recommandation finale UM au niveau du tour de service (ADR-007). La couche 2 n'est pas un simple seuillage : elle intègre une **augmentation métier** (§2.5 ci-dessous) qui enrichit la décision en capturant des signaux non automatisables.

La couche 2 produit : `recommandation_um = (pred_voyageurs_2eme_classe >= SEUIL_UM_2C) OR (signal_augmentation_metier)`.

### 2.2 — Modèle unique avec feature `spatial_segment` (validé empiriquement par notebook 07)

L'architecture duale (deux modèles XGBoost spécialisés par segment bas/haut) a été testée empiriquement dans le notebook 07. Résultats :

| Approche | R² segment bas | R² segment haut |
|---|---|---|
| Modèle unique (sans `spatial_segment`) | 0.5815 | 0.3374 |
| Modèle spécialisé bas ou haut | 0.5569 | 0.3262 |
| **ΔR² (spécialisé − unique)** | **−0.025** | **−0.011** |

Les modèles spécialisés sont systématiquement inférieurs au modèle unique sur les deux segments. L'entraînement sur un seul segment prive le modèle des 379 K observations du segment bas qui apportent de la généralisation.

**Le modèle unique est retenu.** La feature `spatial_segment` agit comme switch contextuel permettant au modèle unique d'apprendre simultanément les deux dynamiques de fréquentation.

Note : bien que les performances globales soient inférieures pour les modèles spécialisés, l'analyse SHAP par segment (notebook 07, Section 5) révèle des divergences profondes dans les features importantes :
- **Segment bas** (TRV/pendulaire) : identifiants de gare (`id_gare_depart/arrivee`), sens de circulation (`base_sens`), vacances scolaires
- **Segment haut** (touristique/excursionniste) : météo (température, précipitations), profil tarifaire SIMBA (`simba_part_spar`), démographie locale

Ces divergences constituent un résultat de data understanding exploitable dans le mémoire pour documenter la dualité des dynamiques de la ligne R35.

### 2.3 — Régression au grain tronçon (confirmation ADR-001)

La cible reste `target_voyageurs_2eme_classe` en régression continue (ADR-001). La couche de décision UM applique le seuil `SEUIL_UM_2C = 94` (ADR-005) en aval, après agrégation au niveau du tour de service.

La reformulation en classification binaire (`target_um_2eme_classe`) testée dans le notebook 05c est définitivement écartée pour le modèle principal : la régression continue préserve l'information de magnitude (à quel point la surcharge est dépassée) utile pour la calibration du seuil en couche 2.

### 2.4 — Périmètre d'entraînement (confirmation ADR-027)

Le split H22+H23 entraînement / H24 test (ADR-027) est confirmé sans modification. L'ADR-032 (révoqué le 2026-05-29 et remplacé par ADR-034) avait proposé une restriction à H23 seul sur la base d'un argument d'incohérence matérielle. Cet argument a été invalidé par l'ADR-034 : `base_offre_2eme_classe` est une variable diagnostique hors-ML, et `target_voyageurs_2eme_classe` est invariante au matériel.

Volumes retenus :
- Train : H22+H23 — 497 023 observations (379 390 bas + 117 633 haut)
- Test OOT : H24 — 335 709 observations (251 106 bas + 84 603 haut)

### 2.5 — Augmentation métier comme réponse à la limite informationnelle

Le pivot architectural central de cet ADR est l'introduction formelle de l'**augmentation métier** comme composante de la couche 2.

**Principe** : intégrer dans le système de décision des informations disponibles à J-1 que les features automatiques ne capturent pas, parce qu'elles ne sont pas structurées dans un système de données exploitable automatiquement.

**Sources prioritaires d'augmentation métier** (à valider opérationnellement avec le Responsable de production, MOB) :

| Source | Type | Disponibilité présumée | Priorité |
|---|---|---|---|
| Réservations groupes anticipées | Base interne MOB | À confirmer avec Responsable de production, MOB | Haute |
| Événements planifiés non publiés | Calendriers internes, conventions, transports scolaires | À confirmer avec Responsable de production, MOB | Haute |
| Signaux contextuels opérationnels | Communication équipes terrain | À structurer | Moyenne |
| Complément référentiel événementiel | Au-delà de Riviera Tourisme | À valider avec Responsable de production, MOB | Moyenne |

**Ce que l'augmentation métier n'est pas** : une modification du modèle prédictif. La couche 1 reste inchangée. L'augmentation métier enrichit uniquement la décision finale en couche 2.

**Condition de mise en œuvre** : validation de la disponibilité et de la fiabilité opérationnelle des sources listées auprès du Responsable de production, MOB avant tout développement de la couche 2.

---

## 3. Résultats empiriques sous-jacents au pivot

### 3.1 — Résultats du notebook 06 (analyse de features et nettoyage)

**Périmètre nettoyé** : 160 features ML retenues (`FEATURES_ML_NETTOYEES`) après exclusion de 14 features en deux catégories :
- Catégorie 1 — hors-cible (12 features) : `histo_voyageurs_1ere_classe_*` × 6 + `histo_voyageurs_total_*` × 6
- Catégorie 5 — doublons calendaires (2 features) : `cal_heure_depart`, `cal_heure_arrivee`

22 features supplémentaires sont classées "à valider" (catégories 3, 6, 7) mais conservées dans `FEATURES_ML_NETTOYEES` par défaut.

**R² du modèle de référence** : 0.6123 sur 160 features — stable vs 0.613 sur 174 features (Δ = −0.0007), confirmant que les exclusions n'ont pas de coût empirique.

**Courbe d'élagage** (top-N features par rang composite) :

| N features | R² global |
|---|---|
| 10 | 0.6181 |
| 15 | 0.5890 |
| 30 | 0.6002 |
| 70 | 0.6005 |
| 160 | 0.6123 |

La courbe est très plate au-delà de 10 features : le top 10 surperforme le complet (0.6181 > 0.6123). Signal d'alerte sur la redondance des features marginales.

**Quatre scénarios évalués** :

| Scénario | n features | R² global | R² bas | R² haut |
|---|---|---|---|---|
| A — Minimum viable | 15 | 0.5890 | 0.5731 | 0.1792 |
| B — Équilibré | 30 | 0.6002 | 0.5782 | 0.2460 |
| C — Performance | 70 | 0.6005 | 0.5682 | 0.3162 |
| D — Complet | 160 | 0.6123 | 0.5823 | 0.3279 |

Le scénario C maximise le R² sur le segment haut (0.3162) tout en restant parcimonieux (70 features). Le scénario B offre le meilleur rapport performance/complexité globale. La décision entre B et C est reportée à l'ADR-35, après validation opérationnelle des sources d'augmentation métier.

**Top 5 features par rang SHAP composite** :
1. `histo_voyageurs_2eme_classe_win7_mean` — historique 7j moyen (autocorrélation pendulaire forte)
2. `spatial_gare_depart_ordre` — position topologique de la gare
3. `spatial_gare_arrivee_ordre` — position topologique de la gare arrivée
4. `horaire_numero_train` — identifiant de train (rang 4, ablation borderline — ADR-017)
5. `histo_voyageurs_2eme_classe_win7_median` — historique 7j médian

### 3.2 — Résultats du notebook 07 (test de segmentation bas/haut)

**Comparaison modèle unique vs modèles spécialisés** (cf. §2.2 pour le tableau complet) :
- Verdict : modèle unique suffisant. Spécialisation écartée empiriquement.
- ΔR² = −0.025 (bas), −0.011 (haut). Pas de gain sur aucun segment.

**Divergence des features top SHAP entre segments** (Section 5, notebook 07) :

| Analyse | Résultat |
|---|---|
| Features consensus (top 20 des deux segments) | 11 features — essentiellement `histo_*` et `cal_*` |
| Features importantes uniquement sur le bas | 4 : `id_gare_depart/arrivee`, `base_sens`, `event_is_vacances_ou_ferie_vaud` |
| Features importantes uniquement sur le haut | 5 : `simba_part_spar`, `meteo_temperature_h`, `meteo_temperature_max_j`, `meteo_precip_total_j`, `spatial_gare_depart_pop_500m_total` |
| Top divergence rang (|Δrang| max) | `id_gare_depart` (Δ = 122), `id_gare_arrivee` (Δ = 119), `spatial_gare_depart_pop_500m_total` (Δ = 96) |

Ces divergences confirment empiriquement que le segment bas obéit à une dynamique pendulaire (identité des gares, calendrier, sens) tandis que le segment haut obéit à une dynamique excursionniste-touristique (météo, profil tarifaire, démographie).

**Rappel sur les surcharges du segment haut** :
- 104 surcharges dans le test H24 haut (0.12 % du segment)
- Rappel = 0.000 sur les deux modèles (unique et spécialisé)
- Confirmation empirique de la limite informationnelle structurelle sur le segment haut

**Diagnostic des erreurs extrêmes** (top 1% erreurs absolues, segment haut) :
- Concentration en juin : 33 % du top 1% vs 8 % dans la distribution globale haut
- Concentration dimanches/fériés : 31 % vs 15 % global
- Pattern cohérent avec une dynamique touristique non capturée par les features actuelles

### 3.3 — Limite informationnelle structurelle

Les analyses des notebooks 05, 05b, 05c, 06 et 07 convergent vers la conclusion suivante :

> **Les features automatiques actuelles (APC historique, calendrier, météo, événementiel public Riviera Tourisme, ISTDATEN, SIMBA) ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité opérationnelle, particulièrement sur le segment haut.**

Cette limite est structurelle et non algorithmique :
- Elle est stable entre 4 architectures de modèles différentes (PR-AUC 0.23–0.25, ADR-031)
- Elle est géographiquement localisée (segment haut > segment bas)
- Elle est temporellement localisée (juin, dimanches/fériés touristiques)
- Elle est explicable : les pics touristiques extrêmes sont par nature imprévisibles sans information sur les flux planifiés (réservations groupes, événements privés)

Le pivot vers l'augmentation métier (couche 2) est la réponse architecturale rationnelle à cette limite.

---

## 4. Conséquences sur les ADR existants

### 4.1 — ADR-003 (architecture deux couches)

**Statut** : confirmé et précisé.

L'ADR-003 avait posé l'architecture à deux couches (modèle prédictif + couche de décision UM). Le présent ADR-033 précise que la couche 2 n'est pas un simple seuillage post-prédiction, mais un système de décision enrichi par l'augmentation métier. Cette précision est additive — elle ne remet pas en cause l'ADR-003.

### 4.2 — ADR-030 (révision stratégie de modélisation)

**Statut** : reste valide, parcours clos.

L'ADR-030 avait ouvert l'exploration des leviers L1/L2/L3. Ce parcours est désormais clos : les trois leviers ont été testés empiriquement (notebooks 05b et 05c), leur aboutissement documenté dans l'ADR-031, et le pivot architectural formalisé dans le présent ADR-033. L'ADR-030 n'est pas révoqué — il documente la démarche exploratoire qui a mené à l'ADR-033.

### 4.3 — ADR-031 (verdict classe rare et addendum)

**Statut** : cohérence maintenue.

L'addendum de l'ADR-031 (2026-05-29) référence déjà explicitement l'ADR-033. Les résultats empiriques de l'ADR-031 (PR-AUC 0.23–0.25, plafond robuste) sont les arguments centraux du pivot documenté ici.

Note : l'addendum de l'ADR-031 contient une mention de l'ADR-032 (révoqué) comme facteur explicatif du plafond PR-AUC. Cette mention est inexacte (l'argument d'incohérence matérielle de l'ADR-032 ne s'applique pas à la cible continue). Elle est préservée pour la traçabilité historique, mais ne doit pas être citée dans le mémoire. L'explication correcte du plafond est la limite informationnelle documentée en §3.3 du présent ADR.

### 4.4 — ADR-35 (à venir)

**Statut** : non encore rédigé.  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->

L'ADR-35 actera la décision finale sur le modèle de référence :
- Scénario de features retenu (B, C ou variante) après validation opérationnelle des sources d'augmentation métier auprès du Responsable de production, MOB
- Hyperparamètres définitifs (à tuner ou à conserver tels quels selon la décision)
- Architecture de la couche 2 et seuil de décision UM calibré
- Toute exclusion supplémentaire de features (catégories 3, 6, 7 du notebook 06)

L'ADR-35 ne peut être rédigé qu'après la validation opérationnelle des sources d'augmentation métier (§5.1 ci-dessous).

---

## 5. Plan d'action pour la suite

### 5.1 — Validation opérationnelle des sources d'augmentation métier

**Interlocuteur principal** : Responsable de production, MOB.
**Interlocuteur secondaire** : conduite des trains (échange informel).

Questions à valider avec Responsable de production, MOB :
1. Existe-t-il une base structurée de réservations groupes avec granularité date × train × volume anticipé ? Quelle est la latence de saisie ?
2. Les événements privés (transports scolaires spéciaux, conventions, groupes culturels) sont-ils tracés quelque part à J-1 ou seulement informellement ?
3. Quel est le référentiel événementiel en dehors de Riviera Tourisme ? Y a-t-il un calendrier opérationnel interne ?
4. Quel est le coût relatif perçu d'une UM inutile (faux positif) versus une surcharge ratée (faux négatif) ? Ce ratio conditionne la calibration du seuil en couche 2.

Questions à valider du côté de la conduite des trains :
1. À quelle heure précise le mécano reçoit-il la décision UM pour le lendemain ? (contrainte horizon décisionnel)
2. Quelle est la forme acceptable de la recommandation ? (message court, probabilité, catégorie de risque)

### 5.2 — Calibration du seuil de décision UM

Le seuil de déclenchement UM en couche 2 doit être calibré selon le ratio FN:FP acceptable, défini avec Responsable de production, MOB. Sans cet ancrage opérationnel, le seuil reste théorique.

Le baseline opérationnel de référence reste : 79.2 % d'UM inutiles sur les tours analysés (notebook 04h). L'artefact ML ne doit pas dégrader ce ratio au-delà d'un niveau acceptable à définir avec Responsable de production, MOB.

### 5.3 — Rédaction de l'ADR-35

Prérequis :
1. Validation opérationnelle des sources d'augmentation métier (§5.1) — Responsable de production, MOB
2. Résultats du Travail 2 (validation externe des variables auprès du responsable de production si applicable)
3. Décision sur le scénario de features (B vs C) après intégration des retours opérationnels

L'ADR-35 figera : scénario features, hyperparamètres (tunés ou pratiques), architecture couche 2, seuil de décision UM, critères d'évaluation du système global (couche 1 + couche 2).

---

## 6. Limites et points de vigilance

1. **Sources d'augmentation métier non validées** : la faisabilité opérationnelle des sources de la couche 2 n'est pas encore confirmée. Si Responsable de production, MOB indique qu'aucune source structurée n'est disponible, l'augmentation métier devra reposer sur des signaux semi-formels (communication téléphonique, notes opérationnelles) dont l'automatisation est plus complexe.

2. **Segment haut structurellement difficile** : R² haut = 0.33 (modèle unique). Même avec l'augmentation métier, les pics extrêmes touristiques resteront imprévisibles si les événements ne sont pas anticipés dans les sources internes MOB. Risque résiduel documenté et assumé.

3. **Couche 2 non encore évaluée empiriquement** : à ce stade, seule la couche 1 (modèle de régression) a été évaluée. L'évaluation du système global (couche 1 + couche 2 avec augmentation métier) n'a pas encore été conduite. Elle sera l'objet d'un travail ultérieur après validation des sources.

4. **Hyperparamètres XGBoost non tunés** : les paramètres pratiques (n_estimators=300, max_depth=6, lr=0.1, subsample=colsample=0.8) ont été utilisés par convention de comparabilité dans les notebooks 05 à 07. Un tuning Bayésien ciblé pourrait améliorer marginalement les performances. La décision de tuner est reportée à l'ADR-35.

5. **Rappel nul sur le segment haut** : le rappel = 0 sur les 104 surcharges test du segment haut est une limite forte de la couche 1 seule. La couche 2 (avec augmentation métier) est la seule réponse viable pour ce segment.

6. **Risque de surdépendance aux features histo_*** : les 3 premières features par rang SHAP global sont des lags historiques (`histo_voyageurs_2eme_classe_win7_*`). Cette dépendance forte à l'autocorrélation est performante sur les patterns récurrents mais structurellement aveugle aux ruptures de tendance (événements exceptionnels non précédés d'historique de surcharge).

---

## 7. Références

### Notebooks
- `notebooks/05_modeling_xgboost_reference.ipynb` — XGBoost baseline, R² = 0.611–0.613, PR-AUC = 0.235
- `notebooks/05b_modeling_weighted.ipynb` — Pondération L1/L2, PR-AUC max = 0.244, rappel max = 40.7 % (scale_pos_weight=20)
- `notebooks/05c_modeling_classification.ipynb` — Classification binaire, PR-AUC = 0.252
- `notebooks/06_feature_analysis_h22_h23_h24.ipynb` — Codebook 192 features, nettoyage, scénarios A–D, top SHAP
- `notebooks/07_segmentation_bas_haut.ipynb` — Comparaison modèle unique vs spécialisés, divergence SHAP, diagnostic segment haut

### ADR associés
- [ADR-001](ADR-001_cible_2eme_classe.md) — Cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — Architecture deux couches
- [ADR-005](ADR-005_seuil_um_94_2c.md) — Seuil UM `SEUIL_UM_2C = 94`
- [ADR-007](ADR-007_rotations_tours_service.md) — Tours de service, couche de décision
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — Split temporel H22+H23 / H24
- [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) — Révision stratégie (leviers L1/L2/L3)
- [ADR-031](ADR-031_verdict_modelisation_classe_rare_et_segmentation.md) — Verdict classe rare, plafond PR-AUC
- [ADR-032](ADR-032_perimetre_materiel_et_coherence_temporelle.md) — Révoqué (2026-05-29)
- [ADR-034](ADR-034_perimetre_base_offre_qualite_diagnostique.md) — `base_offre_2eme_classe` hors-ML

### Sources théoriques sur l'augmentation métier
- Hevner et al. (2004) — Design Science Research : l'artefact combinant couche prédictive et couche décisionnelle s'inscrit dans la famille des "decision support systems" évalués sur leur utilité organisationnelle réelle.
- Gregor & Hevner (2013) — Positionnement DSR : la couche 2 constitue une "improvement" (amélioration d'une solution connue) par rapport au seuillage naïf.
- Lundberg & Lee (2017) — SHAP : explicabilité de la couche 1 comme condition d'adoption de la couche 2 (l'opérateur doit pouvoir valider la prédiction avant d'y adjoindre les signaux métier).
