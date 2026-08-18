---
id: ADR-035
ancien_id: ADR-37
date_decision: 2026-06-03
statut: amendé
amende_par: [ADR-036]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-035 — Intégration des réservations de groupes ResSys en couche 1 du pipeline ML

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-036.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acté |
| **Date** | 2026-06-03 |
| **Décideur** | Erwann Nedellec (data analyste MOB, futur data lead) |
| **Notebooks de référence** | `notebooks/02_data_understanding_ressys.ipynb` (sections 1–10), `notebooks/02_data_understanding_apc.ipynb` (§3.1 TCE, §3.3 AFZ weekend) |
| **Révoque** | — |
| **Lié à** | ADR-027 (split H22+H23 / H24), ADR-033 (architecture deux couches, augmentation métier), ADR-034 (base_offre diagnostique) |

---

## 1. Contexte

### 1.1 — Le problème opérationnel : limite informationnelle sur le segment haut

L'ADR-033 (2026-05-29) a formalisé le pivot architectural du projet R35 ML vers un système à deux couches : modèle XGBoost de régression en couche 1 (prédiction de `target_voyageurs_2eme_classe` au grain tronçon × course × date), et système de décision UM augmenté en couche 2. Ce pivot a été motivé empiriquement par le constat qu'aucune des architectures testées (régression pondérée, classification binaire) ne parvenait à dépasser un PR-AUC de 0.25 sur la classe surcharge, et par le diagnostic que cette limite est **informationnelle et non algorithmique** : les features automatiques actuelles ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles, particulièrement sur le segment haut.

Ce diagnostic est rendu quantitatif par le notebook 07 (segmentation bas/haut) : le modèle de référence atteint R² = 0.6123 global (scénario D, 160 features), mais seulement R² = 0.3279 sur le segment haut, et un **rappel de 0.000 sur les 104 surcharges test du segment haut H24** (aucune prédite). L'analyse des erreurs extrêmes (notebook 07, §5) révèle une concentration en juin (33 % du top 1 % des erreurs vs 8 % en global) et les dimanches/fériés (31 % vs 15 % en global) — pattern cohérent avec une dynamique touristique non capturée par les features existantes.

### 1.2 — La nouvelle source : réservations de groupes ResSys

À la suite des entretiens avec le Responsable de production, MOB, une base de données de réservations de groupes s'avère disponible : les fichiers d'export ResSys pour la ligne R35, archivés de H16 à H25, au format `data/external/reservations/export_r35_h{16-25}.xlsx`. Ces fichiers contiennent exclusivement des **réservations de groupes** (colonne `Reiseart = Gruppe`), avec deux statuts possibles : `50 Abgeschlossen` (confirmée) et `90 Storniert` (annulée). Le schéma est stable sur l'ensemble de la période : 19 colonnes identiques, vérifiées dans le notebook 02_ressys §1 (Quality Gate 1 : PASS).

L'inventaire global (02_ressys §1) porte sur **11 556 lignes brutes H16-H25**, dont **9 129 Abgeschlossen** représentant **338 580 passagers 2ème classe cumulés**. Rapporté au volume APC H24 (6 702 978 voyageurs-tronçon), le poids des réservations au niveau du voyage logique est de **0.48 %** — faible en termes volumétriques. La valeur de cette source réside non pas dans son volume mais dans la nature de l'information qu'elle porte : la présence planifiée de groupes importants sur des trains et dates spécifiques, précisément la catégorie d'événements que le modèle ne capte pas.

### 1.3 — L'hypothèse empirique et sa confirmation

L'hypothèse formulée par Erwann avant l'investigation : les réservations de groupes expliqueraient une part significative des surcharges segment haut non détectées par le modèle.

Le notebook 02_ressys valide cette hypothèse empiriquement. Sur les **104 surcharges segment haut H24** (cellules avec `target_voyageurs_2eme_classe ≥ 94`) :

- **62 (59.6 %) coïncident avec au moins une réservation de groupe** confirmée à date (02_ressys §9.7, topologie corrigée v2)
- **7 sur 7 surcharges segment haut de juin H24 (100 %)** coïncident avec une réservation

Juin concentre précisément les pires erreurs du modèle (33 % des erreurs extrêmes haut) et est le mois pour lequel le rappel était le plus attendu. La convergence entre le diagnostic ADR-033 (juin comme mois problématique) et la concentration des réservations sur ce même mois constitue une validation croisée forte.

Pour mémoire, le prédicteur naïf « résa ≥ 94 → surcharge » sur le segment haut H24 atteint un Rappel = 0.317 et une Précision = 0.091 (02_ressys §7.2). Ce prédicteur pris isolément est trop imprécis pour être utilisé directement — 90 % des réservations de 94+ pax ne déclenchent pas une surcharge APC, parce qu'une composante de fréquentation spontanée s'y ajoute. C'est précisément pourquoi ces réservations doivent entrer dans le modèle ML comme **features**, et non comme règles métier indépendantes.

---

## 2. Décisions actées

### 2.1 — Architecture d'intégration : Approche 1, couche 1 XGBoost

**Décision** : les features dérivées des réservations sont intégrées dans le régresseur XGBoost de la couche 1. Elles constituent des features d'entrée parmi les 160+ déjà présentes dans `ml_dataset.parquet`. L'architecture à deux couches de l'ADR-033 est maintenue sans modification.

**Justification empirique** : l'Approche 2 — intégrer les réservations comme règle OR en couche 2 — a été explicitement écartée pour deux raisons convergentes. (1) Le prédicteur naïf atteint une précision de seulement 0.091 (02_ressys §7.2) : une OR-rule couche 2 déclencherait des UM pour 90 % de faux positifs, dégradant le ratio opérationnel actuel. (2) La target `target_voyageurs_2eme_classe` inclut les passagers de groupe dans les comptages APC — intégrer les réservations comme règle OR indépendante du modèle qui prédit cette même cible crée un double-comptage sémantique. En revanche, fournir les réservations comme features XGBoost permet au modèle d'**apprendre l'interaction résa × autres features** (météo, vacances scolaires, saisonnalité), ce qui est précisément ce qu'un prédicteur naïf ne peut pas faire.

**Conséquence** : le scénario de features retenu pour le modèle de référence (ADR-033 §3.1 : scénario D, 160 features) sera étendu à 168 features incluant les 8 features `resa_*` définies au §2.6. L'ADR-35 (à venir) intégrera cette extension dans sa décision finale sur le scénario de features.

### 2.2 — Périmètre temporel : H22-H25

**Décision** : les réservations sont intégrées au pipeline pour les années horaires H22 à H25, en cohérence avec ADR-027 (périmètre ml_dataset : H22+H23 train, H24 test). Les fichiers H16-H21 sont chargés et nettoyés dans le notebook 02_ressys mais ne sont pas injectés dans le pipeline.

**Justification** : le ml_dataset couvre H22-H24. H25 sera ajouté comme holdout lors d'une prochaine itération (ADR-002). H16-H21 restent disponibles pour analyse historique des patterns de réservation, mais leur intégration dans le pipeline d'entraînement n'apporterait pas de valeur directe : le ml_dataset ne couvre pas ces années et il n'existe pas de target pour créer des features ML sur cette période.

**Limite** : H22 présente une couverture réservations structurellement partielle, documentée en §2.7 ci-dessous.

### 2.3 — Topologie d'éclatement year-specific

**Décision** : la LINE_ORDER statique extraite de `dim_gare` est remplacée par une fonction `build_line_order_from_ml(annee_horaire)` qui déduit la séquence de gares active en consultant les tronçons réellement présents dans `ml_dataset.parquet` pour chaque année horaire. Les années H16-H21, hors ml_dataset, utilisent la topologie H22 comme proxy.

**Justification empirique** : la LINE_ORDER v1 (statique, extraite de `dim_gare`) incluait GIL (Gilamont) pour toutes les années. Or GIL était desservi en H22 uniquement — il a été retiré du graphique commercial à partir de H23 (confirmépar l'absence de GIL dans ml_dataset H23 et H24). L'éclatement v1 créait systématiquement les tronçons `VV→GIL`, `GIL→VVVI`, `VVVI→GIL`, `GIL→VV` pour toutes les réservations H23-H24 passant par Vevey, tronçons inexistants dans le ml_dataset de ces années. Cela produisait 3 688 orphelins (38.2 % du total) classés Cause E dans la décomposition de la Section 10.

**Impact correction** : l'éclatement v2 (topologie year-specific) ramène le taux d'orphelins de 16.8 % à 2.2 % sur H24, et de 8.9 % à 3.1 % sur H23 (02_ressys §9.6). Le grain ML v2 (`02_ressys_resa_au_grain_ml_h22_h25_v2.parquet`) est l'output de référence : **35 697 cellules** (date × train × tronçon × année horaire) pour H22-H25.

**Implémentation** : le stage pipeline `add_reservations` doit appeler `build_line_order_from_ml(annee_horaire)` au début de chaque traitement annuel, avant de passer la liste ordonnée à `eclate_reservation()`.

### 2.4 — Temporal cutoff : lead_days ≥ 1 (connu à J-1)

**Décision** : une réservation est incluse dans le calcul des features J-1 si et seulement si `lead_days = (date_voyage − date_commande).days ≥ 1`.

**Justification empirique** : le notebook 02_ressys §3.2 documente que la quasi-totalité du volume est connu très en avance :

| Horizon | % réservations | % pax_2c |
|---|---|---|
| À J-1 | 100.0 % | 99.9 % |
| À J-2 | 97.8 % | 98.6 % |
| À J-7 | 83.4 % | 87.4 % |
| À J-30 | 52.1 % | 61.4 % |
| À J-60 | 24.0 % | 29.7 % |

La médiane de la latence d'achat est de **32 jours** (mean 40.5 jours, §3.1). La latence est stable sur H16-H25 (médiane 29–47 jours selon les années, §3.3), sans rupture significative post-COVID sur la tendance centrale.

**Cohérence opérationnelle** : le cutoff J-1 garantit que la feature serait calculable dans un pipeline de prédiction opérationnel à J-1. Le choix J-7 maximiserait la couverture en volume mais exclurait 16.6 % des réservations qui arrivent entre J-7 et J-1 — non retenu car les 99.9 % de pax_2c disponibles à J-1 rendent l'exclusion inutile.

**Limite** : 4 réservations Abgeschlossen sur 9 129 (0.04 %) ont `lead_days = 0` (commande le jour même). Elles sont exclues. Impact ML négligeable.

### 2.5 — Traitement des Storniert : exclusion stricte

**Décision** : seules les réservations de statut `50 Abgeschlossen` sont utilisées dans le calcul des features. Les `90 Storniert` sont exclues.

**Justification** : une réservation annulée ne génère aucune charge réelle. Son inclusion introduirait du bruit, particulièrement pour le mois de mars-avril en H20 (31.4 % d'annulation, impact COVID) et H22 (27.6 %).

**Limite documentée** (02_ressys §8.3, Limite 2) : le fichier d'export ResSys ne contient pas de date d'annulation. Une réservation annulée après J-1 mais avant le voyage apparaît dans le fichier comme `90 Storniert` sans qu'il soit possible de déterminer si elle était encore Abgeschlossen à J-1. Cette troncature crée une légère surestimation des features `resa_*` (des annulations tardives sont traitées comme si elles n'avaient jamais existé, alors qu'elles étaient connues à J-1). L'impact est estimé faible si le taux d'annulation post-J-1 est bas. À monitorer empiriquement post-déploiement.

### 2.6 — Features candidates retenues : 8 features `resa_*`

**Décision** : les 8 features suivantes sont calculées au grain ML (date × train × tronçon) à partir des réservations Abgeschlossen avec `lead_days ≥ 1`. Leur imputation par défaut est `0` (pour les 7 numériques) et `False` (pour le flag binaire) lorsqu'aucune réservation n'est connue pour la cellule — 0 est sémantiquement correct (aucune réservation connue = absence de groupe planifié).

Les 7 features quantitatives valent **0 sur 97.59 % des cellules H22-H24** (cellules sans réservation, imputation explicite) et prennent des valeurs strictement positives sur **2.41 % des cellules** (**20 097 cellules sur 832 732 totales** H22-H24). Le flag `resa_has_resa_J_minus_1` vaut `False` sur les mêmes 97.59 % par construction et `True` sur les 2.41 % restantes. XGBoost apprend le signal réservation principalement sur ces 20 097 cellules — mais c'est précisément sur cette fraction que la valeur informative est forte (62/104 surcharges haut H24 y figurent, cf. §1.3).

**Couverture détaillée par année horaire** (mesure post-jointure sur `ml_dataset.parquet` après stage_10) :

| Année | Lignes ml_dataset | Avec résa | Taux |
|---|---|---|---|
| H22 | 161 597 | 4 007 | 2.48 % |
| H23 | 335 426 | 8 145 | 2.43 % |
| H24 | 335 709 | 7 945 | 2.37 % |
| **H22-H24** | **832 732** | **20 097** | **2.41 %** |

La cohérence inter-années (~2.4 % sur les trois années) valide que la couverture partielle H22 documentée en §2.7 n'introduit pas de déséquilibre majeur dans la fraction de cellules enrichies disponibles pour l'apprentissage. Ces chiffres remplacent l'estimation pré-jointure ~12 000 cellules / 3.4 % du notebook 02_ressys §8.1, qui sous-estimait la couverture réelle du grain ML après éclatement multi-tronçons.

| Feature | Définition | Hypothèse de signal |
|---|---|---|
| `resa_pax_2c_J_minus_1` | Somme `pax_2c` des réservations Abg. avec `lead_days ≥ 1` | Proxy volume groupe — corrélé avec les pics de fréquentation |
| `resa_n_dossiers_J_minus_1` | Nombre de dossiers distincts | Différencie 1 grand groupe de plusieurs petits groupes indépendants |
| `resa_max_groupe_2c_J_minus_1` | Taille du plus gros groupe individuel | Un groupe unique de 80+ pax est quasi-certain de provoquer une surcharge |
| `resa_part_scolaire_J_minus_1` | Part `pax_2c` de groupes scolaires (heuristique keywords) | Saisonnalité scolaire spécifique : narcisses (mai), automne, classes de neige |
| `resa_part_tour_operator_J_minus_1` | Part `pax_2c` tour-opérateurs (heuristique keywords) | Voyageurs internationaux, pics décalés vs locaux |
| `resa_n_pays_distincts_J_minus_1` | Nombre de pays distincts | Signal de tourisme international groupé |
| `resa_n_langues_distinctes_J_minus_1` | Nombre de langues distinctes | Signal complémentaire de diversité (confirme internationalité) |
| `resa_has_resa_J_minus_1` | Flag binaire : au moins une réservation connue à J-1 | Feature robuste aux valeurs nulles — signal de présence groupe quelle que soit la taille |

**Heuristiques de classification** (02_ressys §6.1) :
- *Scolaire* — keywords sur `nom_groupe` + `partenaire` : `ecole`, `école`, `scolaire`, `classe`, `school`, `schule`, `uape`, `gym`, `college`, `enfant`
- *Tour-opérateur* — keywords sur `partenaire` : `kuoni`, `ake`, `eisenbahn`, `globus`, `hotelplan`, `tui`, `tourisme`, `tourism`, `reise`

Ces heuristiques sont approximatives. Leur validation sur un échantillon de 50 réservations avec l'équipe MOB constitue une action de suivi (§5, priorité 2).

### 2.7 — Couverture H22 : partielle structurelle documentée

**Décision** : H22 est conservé dans le périmètre d'entraînement avec ses features réservations, malgré un taux d'orphelins de jointure élevé (58.5 %).

**Diagnostic empirique** (02_ressys §9-10) : sur 9 651 cellules ResSys H22 au grain ML v2, 5 644 (58.5 %) sont orphelines de la jointure avec ml_dataset. La décomposition complète des causes, conduite en Section 10 du notebook 02_ressys par rapprochement avec le NB02, attribue la totalité de ces orphelins à des causes documentées indépendamment :

| Cause | N orphelins H22 | % H22 | Source |
|---|---|---|---|
| E — Bug topologie GIL (corrigé v2) | 1 072 | 16.2 % | Section 9 du 02_ressys |
| F — Artefact format APC H22 | 5 547 | 83.7 % | NB02 §3.1 (TCE instable 9-83 %) |
| G — Trains sans AFZ weekend | 12 | 0.2 % | NB02 §3.3 (TCE = 0 % weekend) |
| **Total** | **6 631** | **100.0 %** | |

La Cause E correspond aux tronçons GIL qui, contrairement à H23/H24, **existent bien dans ml_dataset H22** (31 450 lignes) : les réservations éclatées via GIL auraient dû joindre. La non-jointure restante après correction v2 (58.5 % au lieu de 0 %) est due à la Cause F et G, structurelles.

La Cause F est mécanique et documentée dans NB02 §3.1 : la couverture APC (TCE = nb courses APC / nb courses théoriques) est instable en H22, variant de 9 % à 83 % selon les périodes de l'année. Cela signifie que de nombreuses courses réelles — dont certaines avec des groupes — ne figurent pas dans ml_dataset H22 pour des raisons de format de fichier. Cette cause est mécanique — un artefact du format d'export APC, non un phénomène métier. Il n'y a pas de raison structurelle de penser qu'elle est corrélée au niveau de charge des courses absentes, l'export ne sélectionnant pas les courses sur leur niveau de remplissage. Une vérification empirique formelle de cette absence de biais nécessiterait un dataset APC alternatif sur H22 non disponible à ce jour. À défaut, cette hypothèse est documentée comme limite résiduelle (cf. §4, Limite 7) et non comme démonstration.

**Conséquence ML** : les 5 644 cellules orphelines H22 sont absentes de `ml_dataset.parquet`. Elles n'ont pas de `target_voyageurs_2eme_classe` et ne participent à aucun calcul de loss ou de gradient. L'impact sur la qualité du modèle est **nul** : le modèle ignore ces cellules, il ne se trompe pas sur elles. Les features `resa_*` des cellules H22 *effectivement dans* ml_dataset (9 651 − 5 644 = 4 007 cellules) sont calculées correctement.

**Quality Gate 3 (v2)** :

| Année | Orphelins jointure | Taux | Statut |
|---|---|---|---|
| H22 | 5 644 / 9 651 | 58.5 % | ✓ PASS — couverture partielle documentée (F+E, NB02) |
| H23 | 263 / 8 440 | 3.1 % | ✓ PASS |
| H24 | 180 / 8 125 | 2.2 % | ✓ PASS |

**Quality Gate 5** (cause inconnue < 5 %) : 338 orphelins H23/H24 non attribuables à E/F/G/A, soit 3.5 % — **✓ PASS**. Ces orphelins (train régulier, tronçon existant, mais date spécifique absente du ml_dataset) sont probablement des gaps APC ponctuels — capteurs en maintenance sur un trajet isolé. Leur impact est nul pour les mêmes raisons que la Cause F.

---

## 3. Conséquences sur le pipeline et le workflow de modélisation

### 3.1 — Implémentation du stage `add_reservations`

Le nouveau stage `scripts/pipeline/add_reservations_to_raw_stacked.py` (ou équivalent dans la numérotation Makefile) doit implémenter la séquence suivante :

1. Charger les 10 fichiers `data/external/reservations/export_r35_h{16-25}.xlsx`, renommer les colonnes selon la convention `COL_RENAME` du 02_ressys §1, ajouter la colonne `annee_horaire`.
2. Filtrer `statut == '50 Abgeschlossen'` et `lead_days = (date_voyage − date_commande).days ≥ 1`.
3. Pour chaque `annee_horaire`, appeler `build_line_order_from_ml(ah)` pour obtenir la LINE_ORDER active.
4. Appliquer `eclate_reservation(row, line_order, GARE_MAP)` sur chaque ligne pour éclater les voyages logiques en tronçons élémentaires.
5. Agréger au grain ML `(date_voyage, horaire_numero_train, troncon_depart, troncon_arrivee)` avec les 8 features candidates (cf. §2.6).
6. Joindre au ml_dataset via la clé `(base_date, horaire_numero_train, id_gare_depart, id_gare_arrivee)`.
7. Imputer 0 / False sur les cellules ml_dataset sans réservation.
8. Persister `data/processed/ml_dataset_with_reservations.parquet`.

Les fonctions `build_line_order_from_ml()`, `eclate_reservation()`, `is_scolaire()` et `is_tour_operator()` sont à factoriser depuis le notebook 02_ressys (§5.1, §5.2, §6.1) vers un module partagé `scripts/pipeline/reservations_utils.py`.

Le fichier de référence intermédiaire `outputs/02_ressys_resa_au_grain_ml_h22_h25_v2.parquet` (35 697 cellules) peut être utilisé directement pour le re-entraînement avant l'implémentation complète du stage, afin de valider le gain ML en parallèle du développement.

### 3.2 — Re-entraînement et métriques de comparaison

Un notebook dédié (numérotation à définir dans la phase Modeling CRISP-ML(Q) — provisoirement `11_modeling_with_reservations.ipynb`) doit reproduire le protocole du modèle de référence ADR-033 (scénario D, split H22+H23 / H24, walk-forward strict, random_state=42) en ajoutant les 8 features `resa_*` au jeu de features ML nettoyées.

Métriques à comparer systématiquement vs modèle de référence ADR-033 :

| Métrique | Référence (ADR-033) | Cible avec réservations |
|---|---|---|
| R² global | 0.6123 | ≥ 0.6123 |
| R² segment bas | 0.5823 | ≥ 0.5823 |
| R² segment haut | 0.3279 | > 0.3279 (objectif principal) |
| Rappel surcharges haut H24 | 0.000 | > 0.000 (condition nécessaire) |
| Précision surcharges haut H24 | — | à documenter |
| PR-AUC global | ~0.24 | à documenter |

**Hypothèse principale à tester** : l'ajout des features `resa_*` améliore le R² et le rappel sur le segment haut sans dégrader le segment bas. Étant donné que les réservations couvrent 2.41 % des cellules (cf. §2.6, concentration sur le segment haut en proportion), l'effet sur le segment bas est attendu faible.

### 3.3 — Analyse SHAP post-entraînement

Les features `resa_*` doivent être analysées en SHAP global et par segment :

- **Question 1** : quelle feature `resa_*` porte le plus de signal sur le segment haut ? Hypothèse : `resa_max_groupe_2c_J_minus_1` > `resa_pax_2c_J_minus_1` car la taille du plus gros groupe capture mieux la saturation instantanée d'un train.
- **Question 2** : existe-t-il une interaction `resa_pax_2c × meteo_temperature_max_j` (les groupes touristiques + beau temps amplifient la surcharge) ou `resa_pax_2c × event_is_vacances_vaud` ?
- **Question 3** : les features `resa_part_scolaire` et `resa_part_tour_operator` portent-elles un signal indépendant de `resa_pax_2c` sur les deux segments ?

### 3.4 — Positionnement dans le mémoire de thèse

L'intégration des réservations après le pivot architectural constitue un retour amont contrôlé vers la phase Data Understanding du cadre CRISP-ML(Q) — exactement le type d'itération que ce cadre méthodologique prescrit (CRISP-ML(Q) §3, itérativité des phases). Ce cycle est à mentionner explicitement dans la section Méthode du mémoire (Chapitre 3.5 — Design de l'artefact) : la détection de la limite informationnelle (ADR-033) a déclenché l'investigation d'une nouvelle source (notebook 02_ressys), dont le résultat empirique (59.6 % des surcharges haut couvertes) justifie l'extension du jeu de features. Ce mouvement illustre concrètement comment le CRISP-ML(Q) permet de diagnostiquer et corriger des limitations informationnelles en cours de projet.

---

## 4. Limites et travaux futurs

1. **Surcharges segment haut sans réservation** (42/104 en H24, 40.4 %) : ces surcharges restent inexpliquées par la source réservations. Hypothèses : coïncidences météo favorables + voyageurs spontanés, événements touristiques non réservés via ResSys (randonnées, excursions individuelles en famille), ou groupes réservés via d'autres canaux non couverts par cet export. Les features `event_*` et `meteo_*` déjà présentes dans ml_dataset constituent la piste d'exploration prioritaire.

2. **Surcharges segment bas avec réservation** (256/1757 en H24, 14.6 %) : le signal réservation est structurellement plus faible sur le bas de ligne (navettes VV-Blonay, trafic pendulaire). Les 1 501 surcharges bas sans réservation ont d'autres déterminants (événements Riviera, vacances scolaires, fréquentation de pointe journalière).

3. **Annulations tardives non traçables** : le fichier d'export ResSys ne contient pas de date d'annulation pour les `90 Storniert`. Les réservations annulées après J-1 sont comptées comme absentes plutôt que comme présentes-puis-annulées. Impact ML estimé faible mais non mesuré. À monitorer post-déploiement.

4. **Hypothèse de trajet direct dans l'éclatement** : chaque ligne ResSys (voyage logique) est éclatée en tronçons élémentaires en supposant un trajet direct de `gare_depart` à `gare_arrivee` selon la topologie R35. Si un groupe fait une correspondance intermédiaire non déclarée dans le fichier, le tronçon intermédiaire sera surcompté. 21 dossiers avec pax_2c incohérent entre tronçons détectés au §5.3 — cas marginaux documentés.

5. **Couverture volumétrique** : les réservations représentent 0.48 % des voyageurs-tronçon APC au niveau du voyage logique (H24). Le modèle doit capter l'essentiel de la fréquentation via les autres 160 features. L'intégration des réservations ne remplace pas les features historiques et météo — elle les complète sur les 2.41 % de cellules avec réservation (cf. §2.6).

6. **H16-H21 hors training** : 5 années de réservations (4 891 Abgeschlossen, 155 047 pax_2c) sont disponibles mais non injectées en cohérence avec ADR-027. Elles peuvent servir à une analyse historique des patterns de réservation (saisonnalité, profil des partenaires) sans impacter l'entraînement.

7. **Biais de sélection résiduel sur H22** : l'hypothèse selon laquelle l'artefact format APC H22 (Cause F, NB02 §3.1) est non corrélé au niveau de charge n'a pas été démontrée empiriquement faute de dataset APC alternatif sur H22. L'hypothèse reste défendable mécaniquement (l'export ne filtre pas par niveau de remplissage) mais constitue une limite résiduelle à monitorer si un dataset alternatif devient disponible (rapprochement avec rotations, données de billetterie individuelle).

---

## 5. Backlog post-ADR

| Priorité | Action | Déclencheur |
|---|---|---|
| 1 — Critique | Implémenter `scripts/pipeline/add_reservations_to_raw_stacked.py` | ADR-035 acté |
| 1 — Critique | Re-entraîner XGBoost avec 8 features `resa_*`, documenter ΔR² par segment | Outputs 02_ressys v2 disponibles |
| 2 — Standard | Analyse SHAP comparative vs modèle référence ADR-033 | Notebook re-entraînement disponible |
| 2 — Standard | Valider heuristiques scolaire/tour-opérateur avec MOB sur 50 réservations | Coordonner avec Erwann + MOB |
| 2 — Standard | Documenter les résultats dans notebook dédié (11_modeling_*) et créer ADR-036 si l'architecture évolue | Résultats re-entraînement disponibles |

---

## 6. Quality Gates — Récapitulatif

| Gate | Résultat | Détail |
|---|---|---|
| QG1 — Schéma identique H16-H25 | ✓ PASS | 19 colonnes identiques sur les 10 fichiers |
| QG2 — Tronçons orphelins éclatement v2 | ✓ PASS | 0 orphelins — GARE_MAP complet et topologie year-specific |
| QG3 — Réservations orphelines H22 v2 | ✓ PASS couverture partielle | 58.5 %, causes F+E documentées NB02 — impact ML nul |
| QG3 — Réservations orphelines H23 v2 | ✓ PASS | 3.1 % |
| QG3 — Réservations orphelines H24 v2 | ✓ PASS | 2.2 % |
| QG5 — Cause inconnue < 5 % | ✓ PASS | 3.5 % (338 cellules H23-H24) |

---

## 7. Références

### Notebook source
- `notebooks/02_data_understanding_ressys.ipynb` — Data Understanding réservations, 88 cellules (sections 1–10)

### Outputs principaux
- `outputs/02_ressys_resa_eclate_h22_h25_v2.parquet` — 55 465 lignes éclatées H22-H25 (topologie v2)
- `outputs/02_ressys_resa_au_grain_ml_h22_h25_v2.parquet` — **35 697 cellules au grain ML** (référence pour le pipeline)
- `outputs/02_ressys_decomposition_orphelins_v2.csv` — décomposition empirique des 9 658 orphelins H22-H24
- `outputs/02_ressys_orphelins_caracterises_v2.csv` — orphelins avec cause attribuée (E/F/G/A/Z)
- `outputs/02_ressys_features_candidates.csv` — 8 features avec définitions et hypothèses

### Figures clés
- `notebooks/figures/02_ressys/02_ressys_focus_segment_haut.png` — 62/104 surcharges haut H24 avec réservation
- `notebooks/figures/02_ressys/02_ressys_matrice_confusion_seuil_94.png` — prédicteur naïf vs APC (Rappel=0.317, Précision=0.091)
- `notebooks/figures/02_ressys/02_ressys_decomposition_causes_v2.png` — répartition empirique des 9 658 orphelins
- `notebooks/figures/02_ressys/02_ressys_latence_par_annee.png` — stabilité lead_days H16-H25

### ADR liés
- [ADR-001](ADR-001_cible_2eme_classe.md) — Cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — Architecture deux couches
- [ADR-005](ADR-005_seuil_um_94_2c.md) — Seuil UM `SEUIL_UM_2C = 94`
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — Split temporel H22+H23 / H24
- [ADR-033](ADR-033_pivot_architectural_regression_augmentation_metier.md) — Pivot architectural, limite informationnelle, augmentation métier
- [ADR-034](ADR-034_perimetre_base_offre_qualite_diagnostique.md) — `base_offre` hors-ML

### Sources méthodologiques
- CRISP-ML(Q) §3 — Itérativité des phases (retour Data Understanding en cours de Modeling)
- Notebook 02 §3.1 — TCE instable H22 (artefact format APC)
- Notebook 02 §3.3 — Trains sans AFZ weekend, liste de 34 trains (TCE = 0 %)
