---
id: ADR-031
ancien_id: ADR-32
date_decision: 2026-05-28
statut: amendé
amende_par: [ADR-033]
modifie: [ADR-030]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-031 — Verdict empirique sur la modélisation de la classe rare et décision d'explorer la segmentation

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-033.
> Décisions antérieures que ce document modifie : ADR-030.
> **Précision au gel.** L'évaluation du classifieur binaire rapportée au §2.4 est la **contre-épreuve** du levier L3 d'ADR-030. Voir la note d'ADR-030 sur l'articulation avec le §4.6.2 du mémoire.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-28 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/05_evaluation_modele_h24.ipynb`, `notebooks/05b_comparaison_modeles_h24.ipynb`, `notebooks/05c_evaluation_classifieur_h24.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM 94), ADR-027 (split temporel), ADR-030 (révision stratégie) |

## 1. Contexte et rappel

L'ADR-030 a acté, suite au découplage critique R²/rappel observé sur le régresseur XGBoost de référence, la révision de la stratégie de modélisation et l'exploration de trois leviers correctifs : pondération agressive des observations surcharge (L1), objectif asymétrique quantile loss (L2), et classifieur binaire dédié (L3). L'objectif opérationnel demeure la détection des surcharges (`target_voyageurs_2eme_classe ≥ 94`, ADR-005) pour la décision UM sur la ligne R35, avec un déséquilibre réel de 341:1 (983 surcharges sur 335 709 observations H24, ADR-027).

Le présent ADR documente le verdict empirique de ce parcours de modélisation, conduit sur le test set H24, et acte deux décisions : (1) le constat d'une limite informationnelle à la prédiction des surcharges, et (2) l'exploration d'une dernière piste — la segmentation en deux modèles distincts (segment bas / segment haut) — avant la clôture de la phase de modélisation.

## 2. Leviers testés et résultats

### 2.1 Régresseur RMSE complet — 193 features (référence)

Évalué dans `notebooks/05_evaluation_modele_h24.ipynb`.

| Métrique | Valeur |
|---|---|
| R² global | 0.6128 |
| R² segment bas | 0.5780 |
| R² segment haut | 0.3606 |
| RMSE global | 11.06 voyageurs |
| Rappel @94 | 1.2 % (12 TP / 983 surcharges) |
| Précision @94 | 85.7 % |
| F2 @94 | 0.015 |
| Rappel max (seuil = 40) | 62.1 % |
| Rappel @94 — segment haut | 0.0 % (0 TP / 104 surcharges) |

Le biais conditionnel est sévère et croissant avec la charge : les prédictions plafonnent autour de 47–53 voyageurs quelle que soit l'amplitude réelle de la surcharge (erreur moyenne −119 voyageurs pour les charges ≥ 150). Les cibles de rappel 90 % et 95 % sont déclarées non atteignables dès ce stade.

### 2.2 Régresseur RMSE top 20 features (parcimonie)

Évalué dans `notebooks/05b_comparaison_modeles_h24.ipynb`.

| Métrique | Valeur |
|---|---|
| R² global | 0.6377 (meilleur des trois régresseurs) |
| Rappel @94 | 4.8 % |
| Précision @94 | 82.5 % |
| F2 @94 | 0.059 |
| Rappel max (seuil = 40) | 69.6 % |

Le modèle réduit à 20 features obtient le meilleur R² des trois régresseurs tout en étant structurellement plus parcimonieux. Il constitue l'argument empirique de la parcimonie pour l'artefact final si la segmentation n'apporte rien.

### 2.3 Régresseur pondéré 10/5/1 — levier L1

Évalué dans `notebooks/05b_comparaison_modeles_h24.ipynb`. Poids appliqués : 10 (surcharge), 5 (vigilance, 80–93), 1 (normal).

| Métrique | Valeur |
|---|---|
| R² global | 0.6226 |
| Rappel @94 | 6.6 % (meilleur rappel parmi les régresseurs) |
| Précision @94 | 64.4 % |
| F2 @94 | 0.081 |
| Rappel max (seuil = 40) | 65.9 % |

Le tableau de synthèse des trois régresseurs confirme le **découplage R²/rappel** : le modèle offrant le meilleur R² (Top20, 0.638) n'est pas celui offrant le meilleur rappel (Pondéré, 6.6 %). La pondération 10/5/1, bien qu'elle améliore légèrement le rappel, reste très insuffisante face à un déséquilibre de 341:1. Pour contrebalancer mécaniquement la pression de la MSE sur la classe normale, un poids de l'ordre de 100 à 341 serait théoriquement nécessaire. Le levier L1 avec une pondération modérée est insuffisant.

| Modèle | R² | Rappel @94 | F2 @94 | Rappel max (seuil 40) |
|---|---|---|---|---|
| Complet | 0.6128 | 1.2 % | 0.015 | 62.1 % |
| Top20 | 0.6377 | 4.8 % | 0.059 | 69.6 % |
| Pondéré 10/5/1 | 0.6226 | 6.6 % | 0.081 | 65.9 % |

Aucun régresseur ne dépasse 70 % de rappel, même au seuil de déclenchement le plus agressif testé (40). Aucun n'atteint 80 %.

### 2.4 Classifieur binaire XGBoost — scale_pos_weight = 341 — levier L3

Évalué dans `notebooks/05c_evaluation_classifieur_h24.ipynb`. Le classifieur prédit directement `is_surcharge = (target ≥ 94)` avec `scale_pos_weight ≈ 341` (ratio de déséquilibre, ADR-030 §3.1).

#### 2.4.1 Métriques discriminantes non pondérées

| Métrique | Global | Segment bas | Segment haut |
|---|---|---|---|
| PR-AUC non pondéré | **0.2359** | 0.2619 | 0.0116 |
| ROC-AUC | 0.9012 | 0.9010 | 0.9097 |
| Taux de base (précision aléatoire) | 0.293 % | 0.350 % | 0.124 % |
| Rapport PR-AUC / taux base | 80.6× | 74.8× | 9.7× |

Le segment haut présente un PR-AUC de 0.0116, soit environ 9.7× le taux de base — le classifieur ne parvient pas à discriminer les surcharges sur ce segment touristique. Le ROC-AUC de 0.90+ est trompeur et ne doit pas être interprété comme une mesure de performance sur la classe rare (cf. §5).

#### 2.4.2 Calibration par ratio de coût FN:FP

| Ratio FN:FP | Seuil optimal | Rappel | Précision | FN | FP | FP/TP |
|---|---|---|---|---|---|---|
| 3:1 | 0.920 | 23.6 % | 51.3 % | 751 | 220 | 0.95 |
| 5:1 | 0.720 | 29.6 % | 39.0 % | 692 | 456 | 1.57 |
| **10:1** | **0.490** | **34.8 %** | **28.1 %** | **641** | **877** | **2.56** |
| 20:1 | 0.250 | 40.7 % | 17.9 % | 583 | 1 832 | 4.58 |

Même au ratio 20:1, le rappel plafonne à 40.7 %. Le ratio réel (coût d'une UM inutile vs d'une surcharge ratée) doit être obtenu auprès du Responsable de production, MOB pour fixer le point de fonctionnement opérationnel.

### 2.5 Tableau comparatif final — PR-AUC non pondéré

| Modèle | PR-AUC non pondéré | n surcharges H24 | Rappel max |
|---|---|---|---|
| Classifieur 341 | 0.2359 | 983 | 73.0 % |
| Complet (régresseur) | 0.2481 | 983 | — |
| Top20 (régresseur) | 0.2496 | 983 | — |
| Pondéré 10/5/1 (régresseur) | 0.2276 | 983 | — |

Les quatre modèles convergent vers un PR-AUC non pondéré compris entre 0.228 et 0.250.

## 3. Constat central : convergence des approches vers un même plafond

Le résultat principal de ce parcours est la convergence remarquable des quatre modèles — deux familles d'approches distinctes (régression RMSE et classification binaire orientée rappel), avec des formulations d'objectif et des traitements du déséquilibre très différents — vers un PR-AUC non pondéré de **0.23 à 0.25** sur le test set H24.

Cette convergence ne peut s'expliquer par une inadéquation méthodologique : le classifieur avec `scale_pos_weight = 341` est précisément conçu pour contrebalancer le déséquilibre, et son PR-AUC est comparable — voire légèrement inférieur — aux régresseurs. Elle suggère que **le plafond de performance est d'origine informationnelle** : les features disponibles (données de fréquentation historique, calendrier, météo, événementiels, SIMBA) ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité suffisante.

Ce constat est un **résultat de recherche à part entière** (contribution DSR Level 2 : connaissance sur les limites de prédictibilité du phénomène avec les données disponibles), et non un échec de modélisation. Il délimite ce qui est prédictible et ce qui ne l'est pas avec le référentiel informationnel actuel.

## 4. Caractérisation de la limite informationnelle

### 4.1 Le segment haut : une limite structurelle

Le segment haut (Blonay–Les Pléiades, à caractère touristique) concentre 104 surcharges sur 983, soit 10.6 % du total. Ces 104 surcharges sont **systématiquement non détectées** par le régresseur de référence (rappel = 0.0 % à tout seuil ≥ 80), et le classifieur n'obtient qu'un PR-AUC de 0.0116 — marginalement supérieur au taux de base de 0.124 %.

| Approche | Rappel segment haut | PR-AUC segment haut |
|---|---|---|
| Régresseur complet (seuil 94) | 0.0 % | — |
| Classifieur 341 | — | 0.0116 |

La prédiction des surcharges sur ce segment dépasse les capacités du référentiel informationnel actuel.

### 4.2 Analyse des faux négatifs résiduels (classifieur, ratio 10:1)

Au seuil optimal pour un ratio FN:FP de 10:1 (seuil proba = 0.490), 641 surcharges sur 983 restent non détectées (65.2 %).

**Par segment :**
- Segment bas : 537 FN
- Segment haut : 104 FN (100 % des surcharges du segment)

**Par sens :**
- VV → Pléiades : 374 FN (58.3 %)
- Pléiades → VV : 267 FN (41.7 %)

**Par type de jour :**
- Ouvrable hors vacances : 311 FN (48.5 %) — les surcharges ordinaires non détectées dominent
- Dimanche ou férié : 99 FN
- Samedi hors vacances : 98 FN
- Vendredi hors vacances : 77 FN

**Par tranche de charge réelle :**
- [94–110[ : 464 FN sur 735 surcharges (taux FN 63.1 %)
- [110–130[ : 138 FN sur 205 (67.3 %)
- [130–150[ : 30 FN sur 32 (93.8 %)
- [150+[ : 9 FN sur 11 (81.8 %)

Les surcharges extrêmes (charges ≥ 130) présentent des taux de faux négatifs supérieurs à 80 %, précisément celles où l'enjeu opérationnel est le plus critique. Les déterminants de ces pics — événements locaux non répertoriés dans les référentiels disponibles, groupes organisés sans réservation SIMBA enregistrée, affluences ponctuelles — ne figurent pas dans les sources mobilisées.

## 5. Note sur la métrique pondérée trompeuse

Le classifieur entraîné avec `scale_pos_weight = 341` est évalué par Dataiku avec une métrique Average Precision **calculée sur les données pondérées par les poids d'entraînement**, ce qui gonfle artificiellement la contribution de la classe surcharge dans le calcul. Dataiku affiche ainsi un PR-AUC ≈ 0.913.

L'évaluation non pondérée conduite dans le notebook 05c (chaque observation compte pour 1, conformément aux conditions opérationnelles réelles) donne :

| Métrique | Valeur Dataiku | Valeur non pondérée (opérationnelle) |
|---|---|---|
| PR-AUC | 0.913 | **0.2359** |
| ROC-AUC | — | 0.9012 |

L'écart entre 0.913 et 0.236 est un **artefact de pondération**, non un indicateur de performance réelle. Cette confusion méthodologique — présenter comme métrique de performance une grandeur calculée sur données pondérées — peut conduire à des conclusions erronées sur la capacité opérationnelle du modèle. Le même biais affecte le ROC-AUC, qui présente un score de 0.90+ sur une classe rare à 0.29 % : cette valeur reflète la discrimination sur la classe normale (très bien séparée) et non sur la classe rare.

**Règle de validation** : pour tout modèle entraîné avec des poids de classe, les métriques d'évaluation opérationnelle doivent être calculées sur données non pondérées. Les métriques pondérées restent utiles pour le suivi d'entraînement, pas pour l'évaluation décisionnelle.

## 6. Décision

### 6.1 Acte de la limite informationnelle

La convergence de quatre modèles de deux familles distinctes vers un PR-AUC non pondéré de 0.23–0.25 est interprétée comme **la limite informationnelle du référentiel de données actuel** pour la prédiction des surcharges individuelles sur la ligne R35. Cette limite est actée comme résultat de recherche.

La phase de modélisation ne sera pas prolongée par de nouveaux entraînements sur les features existantes sans enrichissement substantiel du référentiel (cf. §8).

### 6.2 Exploration de la segmentation avant clôture

Une dernière piste est retenue avant la clôture : la **segmentation en deux modèles distincts**, un pour le segment bas (urbain/pendulaire, 251 106 observations, 879 surcharges, déséquilibre 286:1) et un pour le segment haut (touristique, 84 603 observations, 104 surcharges, déséquilibre 814:1).

**Rationale** : les résultats montrent que le segment haut est systématiquement non détecté et présente des dynamiques fondamentalement différentes (saisonnalité touristique, événements ponctuels). Des modèles spécialisés par segment pourraient capturer des patterns que le modèle global écrase. Cette piste rejoint la question restée ouverte dans l'ADR-003 (modèle unique vs modèles segmentés).

Si la segmentation n'apporte pas d'amélioration significative du PR-AUC non pondéré ou du rappel sur le segment haut, la limite informationnelle est considérée comme confirmée et la phase de modélisation est close.

La cible (ADR-001) et le seuil 94 (ADR-005) sont inchangés.

## 7. Modèle de référence provisoire pour l'artefact

En l'absence de résultat probant de la segmentation, le modèle de référence provisoire pour l'artefact final est le **régresseur Top20**. Ce choix est justifié par :

1. **Meilleur R² global** (0.6377 vs 0.6128 pour le Complet, 0.6226 pour le Pondéré) : meilleure capacité prédictive globale.
2. **Parcimonie** : 20 features vs 193, plus aisément maintenable et interprétable pour MOB/MVR.
3. **Sortie continue** : une prédiction en nombre de voyageurs est plus riche informationnellement qu'une probabilité binaire — elle permet de calibrer le seuil de déclenchement UM en couche de décision (ADR-003) et d'estimer l'ampleur de la surcharge.
4. **PR-AUC comparable au classifieur** : 0.2496 (Top20) vs 0.2359 (classifieur), ce dernier n'apportant pas d'avantage décisionnel malgré une formulation explicitement orientée rappel.

Ce choix est provisoire et conditionnel au résultat de l'exploration de la segmentation.

## 8. Points ouverts et pistes futures

### 8.1 Test de segmentation (immédiat)

L'exploration immédiate est le test de deux modèles distincts entraînés sur chaque segment. Le critère de succès est une amélioration significative du PR-AUC non pondéré sur le segment haut (seuil indicatif : PR-AUC > 0.05, contre 0.0116 actuellement).

### 8.2 Arbitrage coût FP/FN (MOB)

Le niveau acceptable de faux positifs (UM inutiles) conditionne le point de fonctionnement opérationnel du modèle, même imparfait. Cet arbitrage doit être obtenu auprès du Responsable de production, MOB avant tout déploiement. Sans cet ancrage, la calibration du seuil de décision (ADR-003) reste théorique.

### 8.3 Valeur opérationnelle partielle

Le modèle démontre une capacité de détection partielle sur le segment bas (PR-AUC = 0.26, rappel max 73.0 % pour le classifieur). La question de la valeur opérationnelle d'un rappel limité — typiquement 35–40 % sur le segment bas au ratio 10:1 — mérite une discussion avec MOB. Un outil détectant correctement un tiers des surcharges sur le segment pendulaire peut déjà réduire significativement les incidents si le biais de faux positifs reste acceptable.

### 8.4 Pistes d'enrichissement du référentiel

Les faux négatifs résiduels pointent vers des déterminants structurellement absents des données actuelles :

- **Données de réservation de groupes** : groupes organisés sans trace dans SIMBA, dont l'affluence génère des pics non anticipés.
- **Référentiel événementiel local exhaustif** : les manifestations Riviera et Vaud couvrent les événements connus ; les événements privés, scolaires ou associatifs ponctuels ne sont pas répertoriés.
- **Features de pic enrichies** : historique de surcharges par combinaison jour-type × train × sens à granularité annuelle, saisonnalité interannuelle explicite.
- **Données météo haute résolution** : influence des conditions météorologiques estivales sur la fréquentation touristique du segment haut.

Ces pistes constituent des axes de travaux futurs hors périmètre du présent mémoire.

## 9. Références

- `notebooks/05_evaluation_modele_h24.ipynb` — évaluation régresseur de référence (193 features), 7 figures dans `notebooks/figures/05/`
- `notebooks/05b_comparaison_modeles_h24.ipynb` — comparaison trois régresseurs, 6 figures dans `notebooks/figures/05b/`
- `notebooks/05c_evaluation_classifieur_h24.ipynb` — évaluation classifieur binaire scale_pos_weight=341, 6 figures dans `notebooks/figures/05c/`
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — architecture à deux couches (prédictive + décision) ; question modèle unique vs segmentés
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM = 94 (capacité assise 2ème classe SURF 7500)
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22-H23 / H24
- [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) — révision de la stratégie de modélisation, leviers L1–L3

---

## Addendum — 2026-05-29 : pivot architectural vers régression + augmentation métier

Cet addendum est ajouté postérieurement à la rédaction initiale de l'ADR-031. Il documente un pivot stratégique acté lors d'un examen de la trajectoire du projet, sans modifier le corps original ni invalider les résultats empiriques rapportés.

### A.1 Pivot acté

Le corps de l'ADR-031 documente un parcours de quatre modèles (trois régresseurs et un classifieur binaire) ayant convergé vers un plafond PR-AUC non pondéré de 0.23–0.25 sur le test set H24. Il acte l'exploration de la segmentation comme dernière piste avant clôture de la phase de modélisation, et retient à titre provisoire le régresseur Top20 comme modèle de référence.

Après examen de cette trajectoire, un **pivot architectural** est acté : l'optimisation du modèle de prédiction au sens strict (recherche d'un rappel maximal sur la classe surcharge par pondération, objective asymétrique ou classification binaire) est abandonnée. L'artefact est désormais conçu comme un **système d'aide à la décision à deux couches** combinant :

1. **Un modèle de régression au grain tronçon** prédisant `target_voyageurs_2eme_classe` en valeur continue, sur le périmètre H22+H23 / H24 défini par l'ADR-027.
2. **Une couche d'augmentation métier** intégrant les informations connues à J-1 que les features actuelles ne capturent pas : réservations de groupes, événements planifiés par l'équipe planification MOB, signaux contextuels documentés par les entretiens qualitatifs (P01–P06).

La décision UM finale résulte de la combinaison de la prédiction de charge et de ces inputs métier, dans la couche de décision aval (ADR-003). Cette architecture respecte la nature DSR de l'artefact : elle améliore la décision réelle par rapport au baseline opérationnel (79.2 % de tours UM injustifiés, notebook 04h) plutôt que de chercher une performance prédictive brute hors d'atteinte au regard de la limite informationnelle des features automatiques.

### A.2 Statut révisé des décisions de l'ADR-031

| Décision originale | Statut révisé |
|---|---|
| §6.1 — Acte de la limite informationnelle | **Conservée et reformulée.** La limite informationnelle reste un résultat de recherche valide (contribution DSR Level 2). La réponse à cette limite n'est plus l'enrichissement du référentiel par segmentation seule, mais l'augmentation métier de l'artefact (sources externes au modèle). |
| §6.2 — Exploration de la segmentation comme dernière piste avant clôture | **Redirigée.** La piste segmentation reste pertinente comme axe d'analyse complémentaire (Travail 3 à venir, conditionnel aux résultats du Travail 1 sur les features), non comme dernière tentative d'optimisation avant clôture. |
| §7 — Modèle de référence provisoire = régresseur Top20 | **Conservé à titre indicatif.** Le choix final du modèle de référence sera tranché par l'ADR-35 après le Travail 1 (analyse approfondie des features sur le périmètre H22+H23 / H24). |
| §5 — Note méthodologique sur les métriques pondérées trompeuses | **Conservée intégralement.** |
| §8.4 — Pistes d'enrichissement du référentiel | **Conservée et renforcée.** Les pistes (réservations groupes, événements locaux exhaustifs) constituent désormais le pilier "augmentation métier" du pivot architectural acté ici. |

### A.3 Articulation avec les ADR suivants

- L'**ADR-032** (révoqué le jour de sa rédaction, remplacé par l'ADR-034) ne modifie pas le périmètre d'entraînement. Le split ADR-027 (H22+H23 / H24) reste applicable.
- L'**ADR-033** (à rédiger après le Travail 1) formalisera complètement le pivot architectural acté ici, avec le détail de l'architecture à deux couches et les conditions de faisabilité opérationnelle de l'augmentation métier validées avec le Responsable de production, MOB.
- L'**ADR-35** (à rédiger après les Travaux 2 et 3) actera les décisions finales sur le modèle de référence, le sous-ensemble de features retenu et la question de la segmentation.

## Amendement 2026-07-09 — Correction d'attribution d'interlocuteur

Les mentions d'origine de cet ADR attribuaient l'arbitrage du coût faux positifs / faux négatifs et les validations opérationnelles associées à une autre personne (le référent superviseur du projet côté MOB). L'interlocuteur réel de cet arbitrage et de ces validations était le **Responsable de production, MOB**. La correction porte uniquement sur l'**identité de l'interlocuteur** : le contenu de l'arbitrage, les valeurs et les décisions retenues demeurent inchangés. Correction découverte lors de la passe d'anonymisation et tracée ici.
