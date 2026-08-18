---
id: ADR-022
ancien_id: ADR-05
date_decision: 2026-05-21
statut: actif
amende_par: [ADR-028]
modifie: [ADR-003]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-022 — Disponibilité J-1 des features et stratégie météo horaire

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été amendée par ADR-028.
> Décisions antérieures que ce document modifie : ADR-003.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Révisé |
| **Date initiale** | 2026-05 |
| **Révision** | 2026-05-21 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `01_business_understanding.ipynb` §5, `02_data_understanding_meteosuisse.ipynb` |

---

## 1. Contexte — Logique J-1 et train/serve skew

Le modèle doit fonctionner dans une logique J-1 : toute prédiction est produite la veille du jour de circulation (communication au mécanicien le soir J-1). Toute variable utilisée en prédiction doit donc être disponible ou approximable à ce moment.

Ce principe s'applique aussi bien au prototype historique qu'au déploiement opérationnel. Les contraintes de disponibilité influencent :
- La sélection finale des features (interdiction d'utiliser des données du jour J)
- La logique de jointure dans la pipeline (décalage temporel nécessaire)
- La valeur des backtests (réalisme de la simulation opérationnelle)

---

## 2. Décision sur la granularité météo

**Les features météo passent d'une agrégation journalière à une résolution horaire.**

Cette décision est motivée par trois arguments :

**Alignement train/serve.** En exploitation J-1, le modèle sera servi par les prévisions horaires MétéoSuisse (« Local forecast data », point forecasts pour ~6 000 localités suisses, mis à jour toutes les heures, horizon jusqu'à J+7). La granularité journalière introduisait une asymétrie structurelle entre entraînement (moyennes journalières) et inférence (prévisions horaires). Le passage à l'horaire réduit cet écart.

**Exploitation comportementale fine.** Une moyenne journalière écrase les signaux comportementaux distincts : commuter du matin, excursionniste de l'après-midi, sortie opportuniste conditionnée à la météo du moment. La résolution horaire permet d'attribuer à chaque train sa météo à l'heure de départ.

**Cohérence avec CRISP-ML(Q).** Le choix de granularité est une décision de conception, documentée ici comme telle, et non un détail d'implémentation.

**Approche MVP.** Cette refonte se limite délibérément à six features de premier niveau (température, précipitations, ensoleillement, vent, hauteur de neige et flag neige binaire), toutes à l'heure du départ et mappées selon le segment du tronçon. Des features dérivées plus sophistiquées (différentiels VEV/CHD, fenêtres temporelles matinale et d'usage, tendances multi-jours, lag de hauteur de neige) pourront être ajoutées dans une itération ultérieure, sur la base des résultats de feature importance (SHAP) et de la triangulation avec le corpus qualitatif. Le principe MVP — démontrer la valeur de la granularité horaire et du mapping spatial avant d'enrichir — guide ce choix méthodologique et s'inscrit dans la logique itérative de CRISP-ML(Q).

**Itération 2 — features destination.** Suite à l'analyse SHAP du modèle initial (faible importance des features météo locales au tronçon), une seconde itération MVP introduit quatre features supplémentaires capturant le comportement d'anticipation de l'usager : température, précipitations, ensoleillement et vent à la destination du train (CHD pour les trains montants, VEV pour les descendants). Ces ajouts visent à tester l'hypothèse comportementale selon laquelle la décision de prendre le train dépend davantage des conditions anticipées à destination que des conditions vécues au tronçon courant. Les features locales au tronçon ne sont pas remplacées : XGBoost et l'analyse SHAP arbitreront entre les deux logiques. Les features liées à la hauteur de neige initialement envisagées (locale, destination, praticabilité ski) ont été retirées suite à un diagnostic d'instrumentation détaillé en section 6.

---

## 3. Décision sur les stations d'observation

Deux stations MétéoSuisse sont utilisées comme sources d'entraînement :

| Station | Altitude | Segment servi | Rôle |
|---|---|---|---|
| **VEV** Vevey/Corseaux | ~380 m | bas (ordre ≤ 10) | Proxy régional bas de ligne |
| **CHD** Château-d'Oex | ~1 000 m | haut (ordre > 10) | Proxy altitude Les Pléiades (~1 350 m) |

**Mapping spatial bas/haut.** Le segment d'un tronçon est déterminé par la position ordinale de ses deux gares dans `dim_gare` :
- **bas** : les deux gares ont `ordre ≤ 10` — tronçon entièrement en plaine, Blonay incluse comme terminus bas
- **haut** : au moins une des deux gares a `ordre > 10` — le tronçon touche la crémaillère

Le cas **mixte** disparaît par construction de cette règle : dès qu'un tronçon touche la crémaillère (une des deux gares au-delà de Blonay), il est classé **haut**. Blonay (ordre 10) est donc **bas** quand elle est associée à une gare de plaine, et **haut** quand elle est associée à une gare d'altitude (Prélaz-sur-Blonay et au-delà).

La résolution VEV/CHD est transparente dans le dataset final : les 6 colonnes `meteo_*_h` reçoivent la valeur de la station appropriée selon le segment, sans préfixe station visible.

---

## 4. Train/serve skew — Reconnaissance et protocole de calibration

**En entraînement**, les features météo sont construites à partir d'**observations horaires MétéoSuisse** aux stations VEV et CHD. Ces observations correspondent à la météo réalisée le jour J.

**En exploitation J-1**, ces variables seraient alimentées par les **prévisions horaires point MétéoSuisse** disponibles jusqu'à J+7.

**Impossibilité matérielle d'utiliser des prévisions archivées.** MétéoSuisse n'archive pas les prévisions historiques dans ses canaux OGD : le catalogue STAC ne propose que les prévisions courantes (rétention 24–48 h selon le dataset). Il est donc impossible de reconstituer rétrospectivement les prévisions qui auraient été disponibles à J-1 pour les années H22–H24.

**Conséquence acceptée.** Le prototype utilise les observations comme proxy des prévisions. Cette hypothèse est moins problématique à la granularité horaire qu'à la granularité journalière : les prévisions horaires à J-1 ont une précision suffisante pour que l'écart observation/prévision reste faible sur les variables utilisées (température, précipitations, ensoleillement).

**Protocole de calibration shadow.** Pour constituer l'archive nécessaire à l'évaluation future du gap observation/prévision, un snapshot quotidien des prévisions MétéoSuisse locales pour les localités R35 (Vevey, Blonay, Les Pléiades) devrait être initié dès maintenant. Ce protocole — non implémenté dans le prototype — est un principe de conception pour le déploiement opérationnel.

---

## 5. Matrice de disponibilité J-1

Toute feature est classée dans l'une des cinq catégories suivantes :

| Catégorie | Définition | Features concernées | Traitement dans la pipeline |
|---|---|---|---|
| **1 — Certaine** | Disponible à J-1 de manière certaine, sans hypothèse | `cal_*`, `horaire_*`, `event_*`, `spatial_*`, `histo_*` (lags) | Jointure directe |
| **2 — Prévisionnelle** | Disponible à J-1 via prévision horaire (incertitude résiduelle) | `meteo_*_h` (5 features locales : temp., préc., ensoleillement, vent, neige binaire), `meteo_destination_*_h` (4 features destination : temp., préc., ensoleillement, vent) | Observations horaires VEV/CHD comme proxy des prévisions MétéoSuisse horaires disponibles à J-1. Mapping VEV/CHD selon `spatial_segment` (local) ou `base_sens` (destination). Les features hauteur de neige (`meteo_neige_cm_h`, `meteo_destination_neige_cm_h`, `event_ski_neige_si_ouvert_h`) ont été retirées (cf. §6). |
| **3 — Dernier état connu** | Disponible à J-1 via le dernier enregistrement disponible | `spatial_*` (STATPOP) | Dernier millésime disponible à la date de prédiction (cf. ADR-006) |
| **4 — Décalée** | Disponible à J-1 uniquement sur observations passées | `ist_*` (ponctualité, réalisation, headway) | Calcul sur fenêtres J-2, J-8→J-2, jamais sur J (cf. ADR-008, ADR-015, ADR-018) |
| **5 — Interdite** | Contient des informations du jour J — data leakage | `base_tx_occupation_*`, `base_passagers_*`, `base_places_disponibles_*` | Supprimées dans `build_ml_dataset.py` |

---

## Règles d'application

1. **Catégorie 5 (interdite)** : exclues dans `build_ml_dataset.py`. Ne doivent jamais figurer parmi les inputs du modèle.

2. **Catégorie 4 (décalée)** : les features `ist_*` sont calculées sur des observations antérieures à la date prédite. Aucune information de réalisation du jour J n'est utilisée.

3. **Catégorie 2 (prévisionnelle — météo)** : voir sections 2, 3, 4 ci-dessus. La pipeline opérationnelle devra alimenter les features météo depuis les prévisions MétéoSuisse horaires, et non depuis les observations a posteriori.

---

## Conséquences

- Les analyses de feature importance (SHAP) distingueront les features certaines (catégorie 1) des features prévisionnelles (catégorie 2).
- La pipeline opérationnelle devra intégrer les prévisions MétéoSuisse horaires pour les localités R35.
- L'initiation du protocole de calibration shadow est recommandée avant tout déploiement en production.

## 6. Retrait des features de hauteur de neige — shift d'instrumentation

### Constat empirique

L'inspection des fichiers MétéoSuisse propres (parquets `meteo_vev_clean` et `meteo_chd_clean`) a révélé que le paramètre `htoauths` (hauteur de neige automatique, valeur instantanée horaire) n'a été instrumenté ni à VEV ni à CHD avant 2023 :

| Station | Avant 2023 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| VEV | 100 % NaN | 36 % couvert | 98 % couvert | 100 % couvert |
| CHD | 100 % NaN | 56 % couvert | 99 % couvert | 100 % couvert |

Les valeurs 0 cm existent par ailleurs (22.4 % VEV, 9.1 % CHD globalement) et confirment que les capteurs retournent bien 0 en absence de neige. Les NaN avant 2023 sont donc structurellement attribuables à l'absence d'installation du capteur, pas à un encodage de « pas de neige ».

### Conséquence sur la configuration train/test

La configuration prototype utilise H22-H23 comme données d'entraînement et H24 comme données de test. Cette configuration crée un **shift d'instrumentation** sur trois features dépendantes de `htoauths` :

- `meteo_neige_cm_h` (locale au tronçon)
- `meteo_destination_neige_cm_h` (destination)
- `event_ski_neige_si_ouvert_h` (praticabilité ski)

Ces trois features sont quasi-100 % NaN en train (H22-H23) et quasi-100 % renseignées en test (H24). XGBoost gère techniquement les NaN, mais ne peut pas apprendre la structure du signal à partir d'un train où la feature ne varie pratiquement pas. Toute analyse SHAP sur ces trois features refléterait un artefact d'instrumentation et non un signal métier exploitable.

### Décision

Les trois features sont **retirées du dataset** au stade du prototype. La feature `meteo_neige_binaire_h` (flag binaire neige) est conservée car sa construction ne dépend pas exclusivement de `htoauths` : côté VEV elle repose uniquement sur la pluie froide (précipitations > 0 ET T < 2°C), et côté CHD la logique OR retombe proprement sur la pluie froide quand `htoauths` est NaN (`NaN > 0` est évalué à `False` par pandas).

### Réversibilité

Les features retirées pourront être réintroduites dans une itération future lorsque les données d'entraînement incluront 2024 ou ultérieures (à partir de l'année horaire H25 par exemple), période sur laquelle l'instrumentation `htoauths` est complète sur les deux stations.

### Inscription méthodologique

Cette décision illustre un principe central de CRISP-ML(Q) : la phase Data Understanding doit identifier les défauts structurels d'instrumentation avant qu'ils ne contaminent silencieusement les phases ultérieures. Le retrait préventif est préférable à la conservation d'une feature techniquement disponible mais méthodologiquement inexploitable, parce qu'elle introduirait un biais d'interprétation dans les résultats SHAP sans gain prédictif réel.

---

## Fichiers impactés

- `scripts/pipeline/add_spatial_to_raw_stacked.py` (nouveau stage_03e — correction frontière Blonay)
- `scripts/pipeline/add_meteo_to_raw_stacked.py` (nouveau stage_04 — fusion VEV+CHD, horaire, 9 features)
- `scripts/pipeline/add_features_to_raw_stacked.py` (retrait calcul spatial, passthrough)
- `scripts/pipeline/build_ml_dataset.py` (préfixe `meteo_` conservé, colonnes `_j` disparaissent)
- `notebooks/02_data_understanding_meteosuisse.ipynb`
