# Glossaire

Termes métier et techniques du projet R35 ML. Registre : ferroviaire suisse (MVR / MOB),
comptage automatique de voyageurs, apprentissage automatique.

## Contexte et exploitation

- **R35** : ligne ferroviaire régionale Vevey-Les Pléiades (canton de Vaud).
- **MVR** : Transports Montreux-Vevey-Riviera, entreprise ferroviaire exploitant la ligne R35,
  du groupe **MOB** (Compagnie du Chemin de fer Montreux Oberland bernois SA).
- **UM (unité multiple)** : composition de deux rames couplées, offrant environ le double de
  la capacité assise d'une rame simple. Le **doublage en UM** est la décision opérationnelle
  que le système aide à prendre.
- **SURF 7500** (ABeh 7501-7508) : matériel roulant de référence de la ligne. Sa capacité de
  2ème classe fixe le seuil de décision : **63 places assises de 2ème classe** par rame simple,
  hors strapontins des zones mixtes (porte-skis / vélos). Validé par la Responsable des Actifs
  Voyageurs, MOB. L'offre APC enregistre 94 (63 assises + 31 strapontins) ; seule la capacité
  assise (63) sert de seuil de surcharge.
- **Course** : un trajet identifié par son numéro de train (`numero_train`). **Grain de
  décision de l'artefact**.
- **Tour de service (rotation)** : enchaînement de courses assurées par une même rame sur une
  journée. Utilisé pour l'**évaluation rétrospective**, pas comme grain de décision.
- **Tronçon** : segment de ligne entre deux gares consécutives. Grain fin de la charge.
- **Créneau** : fenêtre horaire de regroupement (ancrage 30 minutes) pour stabiliser les
  features historiques.
- **Segment BAS / HAUT** : partition des tronçons selon la topologie. Un tronçon est **BAS**
  quand ses deux gares ont un ordre topologique inférieur ou égal à 10 (plaine, jusqu'à Blonay
  incluse) ; il est **HAUT** dès qu'il touche la crémaillère (au moins une gare au-delà de
  Blonay, ordre supérieur à 10). Blonay (ordre 10) est donc classée BAS ou HAUT selon l'autre
  gare du tronçon. Chaque segment est traité par un modèle spécialisé.
- **J-1 / J-2** : horizons temporels. Recommandation produite à **J-1** ; certaines features
  ne sont disponibles qu'à **J-2** (latence de publication).
- **iso-périmètre** : périmètre commun (intersection planification / réalisation) garantissant
  que la couche 2 et la baseline humaine sont évaluées sur le **même ensemble de courses**
  (sur H25 : 29 222 courses). Condition d'une comparaison équitable modèle / pratique actuelle.

## Sources de données

- **APC** (Automatic Passenger Counting) : comptage automatique montées/descentes. Source de
  la cible (`target_voyageurs_2eme_classe`).
- **ISTDATEN** : données de réalisation horaire (ponctualité, retards), opentransportdata.swiss.
- **VMCV** : indicateurs de concurrence modale dérivés d'ISTDATEN, grain train x jour x sens.
- **SIMBA (FQkal)** : données structurelles de fréquentation et de tarification MOB. Lag N-1.
- **ResSys / CAPRE** : système de réservation de groupes (même source, nommage variable).
  Features `resa_*`.
- **STATPOP** : statistique de la population (OFS), agrégée par gare via un diagramme de
  Voronoi clippé à 500 m.
- **STATENT** : statistique des entreprises et de l'emploi (OFS). Colonnes emploi 500 m
  présentes dans le dataset mais retirées des features du modèle.

## Modélisation et pipeline

- **DSR** (Design Science Research) : cadre méthodologique de conception d'artefact évalué.
- **CRISP-ML(Q)** : cycle de vie de projet d'apprentissage automatique.
- **Architecture médaillon** : préparation des données en étapes numérotées (`stage_01` à
  `stage_10`, avec des sous-étages `03b` à `03e`, `04b`, `06b`), chaque étape enrichissant une
  table parquet à partir de la précédente.
- **Enrichi_Seg v1.9** : modèle canonique de couche 1. Deux régresseurs XGBoost (BAS, HAUT),
  158 features. Empreinte de dataset `ba493568`.
- **Décompte des colonnes et des features (convention)** : pour lever toute ambiguïté (dette
  documentaire soldée, voir ADR-072), on distingue quatre notions :
  - **colonnes du dataset** : les **209** colonnes de `ml_dataset.parquet` (`ba493568`) ;
    dictionnaire complet dans `outputs/codebook_canonique_ba493568.csv` ;
  - **features du modèle** : les **158** features effectivement utilisées par Enrichi_Seg v1.9
    (`outputs/couche2/features_158f_sans_simba.json` ; SIMBA retiré par ADR-061, STATENT par
    ADR-064) ;
  - **colonnes hors matrice** : colonnes présentes dans le dataset mais hors du modèle,
    conservées pour la traçabilité (identifiants, clés) ou retirées par décision tracée ;
  - **features analysées à l'étape X** : les décomptes intermédiaires datés (160 au scénario D
    ADR-033, 167/168 avec réservations ADR-036, 170, 179 pour l'Enrichi), jalons de la démarche
    à ne pas confondre avec les 158 features canoniques.
- **Split C** : périmètre d'entraînement H22 (hors tronçons Gilamont) + H23 + H24 ;
  test out-of-time sur H25.
- **Surcharge** : charge de 2ème classe strictement supérieure au **seuil UM** de 63 places
  assises (au moins un voyageur sans siège). Cible opérationnelle de la détection.
- **bloc (identité-composition)** : regroupement de courses consécutives partageant la même
  identité de composition physique (rame et couplage). Unité d'agrégation utilisée pour mesurer
  la précision de la baseline UM humaine dans les rapports de couche 2.
- **histo_\* / win7** : features historiques APC (statistiques sur fenêtre glissante de 7
  occurrences), calculées avec un décalage (cutoff) préservant la causalité temporelle.
- **headway** : intervalle entre trains successifs, calculé sur la grille planifiée connue à
  J-1.
- **Empreinte de contenu (hash) `ba493568`** : SHA256 tronqué du fichier `ml_dataset.parquet`,
  identifiant de version reproductible du dataset (à pyarrow 21.0.0 constant). À ne pas
  confondre avec un identifiant de commit git.
- **ADR** (Architecture Decision Record) : décision de conception préenregistrée. Voir
  `docs/adr/INDEX.md`.
