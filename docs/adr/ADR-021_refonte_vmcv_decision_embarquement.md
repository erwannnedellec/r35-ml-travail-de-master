---
id: ADR-021
ancien_id: ADR-23
date_decision: 2026-05-18
statut: actif
precise_par: [ADR-040]
modifie: [ADR-020]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-021 — Refonte VMCV : décision à l'embarquement, grain train × jour × sens

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été précisée par ADR-040.
> Décisions antérieures que ce document modifie : ADR-020.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Implémenté et validé  
**Date** : 2026-05-18  
**Auteur** : E. Nédellec  
**Remplace** : ADR-020

---

## Contexte

ADR-020 (grain tronçon) a produit une couverture de 0,08 % (1 720 / 2 245 594 lignes),
très en-dessous du seuil d'inclusion de 0,5 %. L'analyse de la cause racine a révélé
un défaut structurel :

- L'arrêt GIL (Gilamont, bpuic 8501260, km=1,21) a été remplacé par VVVI (Vevey-Vignerons,
  bpuic 8502476, km=1,45) en décembre 2022.
- La ligne VMCV 202 n'est dense dans ISTDATEN qu'à partir de novembre 2022.
- Le critère ADR-020 exigeait qu'une même ligne VMCV soit présente aux deux extrémités d'un
  tronçon R35. Avec seulement 2 mois de chevauchement GIL/VMCV avant la transition, très
  peu de tronçons satisfaisaient ce critère.

Le retour qualitatif du panel passager (P03, 07:21 : *« il y a eu des lignes de bus qui ont
été ajoutées à Saint-Légier, qui m'ont permis des fois de pas prendre le train et de plutôt
prendre le bus »*) confirme un défaut conceptuel plus profond : **la décision
modale est prise à la gare d'embarquement, pas à chaque tronçon**. Un passager embarquant
à Vevey décide de prendre le R35 ou le bus 202 en fonction de l'offre à Vevey ; il ne
réévalue pas cette décision à chaque arrêt du trajet.

---

## Décisions

### D1 — Nouveau grain : (date, numero_train, sens)

La table `dim_vmcv_par_train_jour.parquet` est construite au grain
**(date, numero_train, sens)**, soit une ligne par départ de train dans une direction
donnée. Les features sont ensuite **propagées** à tous les tronçons du même train
lors de la jointure dans `add_istdaten_to_raw_stacked.py`.

### D2 — Test directionnel basé sur les seuils kilométriques empiriques

La pertinence d'une ligne VMCV pour un sens de circulation donné est déterminée
par sa présence près d'une gare R35 aux extrémités de la ligne :

| Sens         | Condition de pertinence                                          |
|:-------------|:-----------------------------------------------------------------|
| VV → PLEI    | La ligne VMCV a au moins un arrêt à ≤ 200 m d'une gare km ≥ 5,5 |
| PLEI → VV    | La ligne VMCV a au moins un arrêt à ≤ 200 m d'une gare km ≤ 4,0 |

**Justification empirique des seuils :**

L'analyse des charges moyennes de 2ème classe au départ (jours ouvrés, toutes
années horaires) révèle une bipolarité fonctionnelle nette :

| Gare              | km    | Montants/obs | Ratio vs seuil |
|:------------------|------:|-------------:|:---------------|
| Vevey             |  0,00 |        29,56 | — (pôle bas)   |
| Blonay            |  5,72 |        11,07 | 5,3× vs CDBL   |
| Château-de-Blonay |  5,35 |         2,08 | — (rupture)    |
| Les Pléiades      | 14,28 |         5,80 | — (pôle haut)  |

La rupture Blonay / Château-de-Blonay (ratio 5,3×) se situe entre km=5,35 et km=5,72.
Le seuil km ≥ 5,5 capture Blonay et au-delà, le seuil km ≤ 4,0 isole la zone
basse-vallée (Vevey, Vevey-Vignerons, La Tour-de-Peilz).

La zone intermédiaire (St-Légier-Village km=4,72 ; La Chiésaz km=5,10 ;
Château-de-Blonay km=5,35) reste délibérément hors du test directionnel :
une ligne VMCV ne desservant que ces gares ne constitue pas une alternative
crédible ni pour un voyageur montant vers Les Pléiades ni pour un voyageur
descendant vers Vevey.

### D3 — 4 features produites (vmcv_delta_trajet_min retiré)

| Feature                     | Description                                                                              | NaN si                               |
|:----------------------------|:-----------------------------------------------------------------------------------------|:-------------------------------------|
| `vmcv_n_lignes_concurrentes`| Nb de lignes VMCV distinctes pertinentes pour (gare départ, sens) — **statique**        | Jamais (= 0 si aucune ligne)         |
| `vmcv_min_attente_min`      | Attente minimale (min) avant le prochain VMCV dans [h_dep_r35 − 5min, h_dep_r35 + 30min] | Aucun VMCV dans la fenêtre d'attente |
| `vmcv_delta_attente_min`    | 5 − vmcv_min_attente_min (positif = VMCV avantageux car part presque au même moment)    | Aucun VMCV dans la fenêtre d'attente |
| `vmcv_delta_frequence_h`    | Nb VMCV dans ±30min − nb R35 dans ±30min (train courant inclus dans R35)               | 0 VMCV dans la fenêtre de fréquence  |

`vmcv_delta_trajet_min` de l'ADR-020 est **retiré** : le bus ne dessert pas la même
destination finale que le R35, ce qui rend une comparaison de temps de trajet
porte-à-porte non pertinente sans données OD passagers.

### D4 — Jointure J-2 sur 3 clés

La jointure dans `add_istdaten_to_raw_stacked.py` utilise :
- `base_date = date + 2j` (logique J-2 opérationnelle)
- `horaire_numero_train = numero_train`
- `base_sens = sens`

Chaque tronçon APC d'un train reçoit ainsi les mêmes 4 valeurs VMCV (propagation
naturelle du grain train×sens vers le grain tronçon).

---

## Conséquences

- **Couverture attendue** : nettement supérieure à 0,5 % car le critère de matching
  repose sur la gare de départ (toujours présente dans ISTDATEN) et non sur une paire
  de gares (soumise à la transition GIL → VVVI).
- **Concentration sur Vevey** : les features doivent être non-NaN principalement pour
  les trains partant de Vevey et Blonay, pas uniformément répartis sur tous les tronçons.
- **Rétrocompatibilité** : ADR-020 est retiré. `dim_vmcv_par_troncon.parquet` reste
  sur disque comme archive mais n'est plus utilisé par la pipeline.

---

## Validation empirique

*(Scripts : `analysis/coverage_vmcv.py`, `analysis/verify_vmcv_directional_mapping.py`,
`analysis/verify_vmcv_anomalies.py` — exécutés le 2026-05-18)*

### Couverture globale

| Métrique                    | Valeur            | Baseline ADR-020 |
|:----------------------------|------------------:|----------------:|
| Couverture globale (δ-att.) | **20,08 %**       | 0,08 %          |
| Gain                        | **×251**          | —               |
| Lignes couvertes (count)    | 474 083 / 2 360 762 | 1 720 / 2 245 594 |

### Couverture par année horaire

| Année horaire | Total tronçons | Couverts | Couverture |
|:-------------:|---------------:|---------:|:----------:|
| H16           |        168 377 |        0 |      0,00% |
| H17           |        218 529 |        0 |      0,00% |
| H18           |        195 696 |      414 |      0,21% |
| H19           |        233 595 |        0 |      0,00% |
| H20           |        208 312 |        0 |      0,00% |
| H21           |        194 269 |   15 041 |      7,74% |
| H22           |        161 597 |   49 512 |     30,64% |
| H23           |        335 426 |  204 143 |     60,86% |
| H24           |        335 709 |  195 077 |     58,11% |
| H25           |        309 252 |    9 896 |      3,20% |

La montée en couverture à partir de H21 reflète le déploiement progressif des données
VMCV réelles dans ISTDATEN (opérateur VMCV actif dans les exports à partir de fin 2020).

### Mapping directionnel

| Gare de départ    | km    | VV→PLEI couverts | PLEI→VV couverts |
|:------------------|------:|-----------------:|-----------------:|
| Vevey (8501200)   |  0,00 |          103 798 |                2 |
| Blonay (8501281)  |  5,72 |            3 267 |           66 664 |
| St-Légier-Village (8501264) | 4,02 |            2 |                8 |

Les 14 autres gares R35 sont **toutes Cause A** : aucun arrêt VMCV à ≤ 200 m. Cause B = 0
(aucun cas où un VMCV est proche géographiquement mais échoue au test directionnel pour
une gare avec du trafic réel).

### Distribution de `vmcv_delta_attente_min` (lignes couvertes, n=474 083)

| Statistique | Valeur |
|:------------|-------:|
| min         | −30,00 |
| p05         |  −4,05 |
| médiane     |  +2,30 |
| p95         |  +5,00 |
| max         |  +5,00 |
| % > 0 (VMCV avantageux) | **66,9 %** |

### Note structurelle — gares non couvertes

Sur les 17 gares R35 apparaissant comme gare de départ dans ISTDATEN, 3 disposent
d'une alternative VMCV à ≤ 200 m : Vevey, Blonay et St-Légier-Village (10 trains
partiels sur l'ensemble de la période — cf. Vérification 1 ci-dessous).

Les 14 gares intermédiaires (Vevey-Vignerons, Clies, Hauteville, Château-d'Hauteville,
St-Légier-Gare, La Chiésaz, Château-de-Blonay, Prélaz-sur-Blonay, Tusinge,
Les Chevalleyres, Bois-de-Chexbres, Fayaux, Ondallaz-L'Alliaz, Lally) ne sont desservies
par aucun bus VMCV dans le rayon de 200 m. Cette absence reflète la géographie du
territoire (zone semi-rurale entre Vevey et Blonay) et constitue une caractéristique
structurelle du réseau de transport régional, pas un défaut de mapping.

### Vérification 1 — St-Légier-Village comme gare de départ (10 trains)

Causes identifiées après analyse des séquences ISTDATEN :
- **VV→PLEI (2 trains)** : train 1372 du 2023-08-24 et train 1344 du 2024-03-01.
  Les séquences montrent que ces trains démarrent physiquement à Blonay mais
  ont St-Légier-Village comme premier arrêt *dans le sens VV→PLEI* — ce sont des
  trains qui font un aller-retour partiel (Blonay→St-Légier puis repartent en montée).
  Aucun arrêt annulé. 10 trains au total sur la période : volume négligeable.
- **PLEI→VV (8 trains)** : trains partiels avec 0 arrêt annulé mais séquence complète
  débutant avant St-Légier-Village. L'identification de la gare de départ effective
  capture le premier tronçon dans le sens PLEI→VV, qui se trouve être St-Légier-Village
  pour ces courses où le segment haut est en sens inverse.

**Conclusion** : ces 10 trains ne constituent pas un artefact de données. L'impact
sur la couverture VMCV est nul (volume < 0,005 % du dataset total).

### Vérification 2 — Limitation connue du test directionnel D2

L'analyse du mapping pour Vevey (km=0) en PLEI→VV révèle que 11 des 12 lignes VMCV
identifiées (201, 202, 209, 211, 212, 213, 215, 216, 217, 218, 290) **ne traversent
pas la zone haute** (n_gares_haut=0 pour toutes). Seule la ligne 291 a des arrêts
proches des deux pôles.

**Cause** : le test D2 actuel sélectionne une ligne pour sens PLEI→VV si elle appartient
à `lines_near_bas` (≥1 arrêt près d'une gare km ≤ 4,0). Pour une gare *elle-même* dans
la zone bas (comme Vevey à km=0), la gare satisfait trivialement le critère, et toutes
les lignes VMCV passant par Vevey sont incluses, y compris des bus urbains qui ne
remontent pas vers Blonay.

**Impact réel** : les 2 trains Vevey-PLEI→VV représentent 0,001 % du dataset total.
La couverture PLEI→VV significative provient entièrement de Blonay (km=5,72), où le
test est correct : seules les lignes avec un arrêt près de Blonay ET un arrêt près de
la zone bas (Vevey) sont incluses.

**Limitation tolérable** : une version raffinée exigerait qu'une ligne ait des arrêts
dans les deux pôles (et non seulement dans le pôle opposé à la gare considérée). Cette
correction est reportée à une itération ultérieure si l'analyse SHAP révèle un problème
de signal. XGBoost discriminera empiriquement les lignes utiles via la corrélation
feature–cible sur les 474 083 lignes couvertes.

---

## Fichiers modifiés

| Fichier                                      | Rôle                                    |
|:---------------------------------------------|:----------------------------------------|
| `scripts/sources/build_dim_vmcv_par_train_jour.py` | Script producteur (nouveau)       |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py`  | Famille 3 mise à jour             |
| `scripts/pipeline/paths.py`                  | `DIM_VMCV_PAR_TRAIN_JOUR` ajouté       |
| `Makefile`                                   | Règle + dépendances mise à jour        |
| `tests/test_pipeline_vmcv_train_jour.py`     | 34 tests (nouveau)                     |
| `tests/test_pipeline_vmcv.py`                | Marqué DEPRECATED                     |
| `analysis/coverage_vmcv.py`                  | Features ADR-021                        |
| `analysis/verify_vmcv_directional_mapping.py`| Diagnostic mapping directionnel        |
| `analysis/verify_vmcv_anomalies.py`          | Vérifications V1/V2 pré-clôture        |
