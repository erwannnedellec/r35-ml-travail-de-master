---
id: ADR-007
ancien_id: ADR-07
date_decision: 2026-05
statut: amendé
amende_par: [ADR-073]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-007 — Tours de service : table de rotations externe nécessaire pour la couche de décision

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-073.
> **Précision au gel.** La table de rotations a bien été produite (`scripts/sources/build_dim_rotations_r35.py`), mais employée **exclusivement comme référence de vérité de l'évaluation** (mémoire §4.3.6 et §4.7.2), jamais comme variable ni comme grain de décision. Le grain de la décision est la **course** (ADR-073) ; la couche de décision au grain du tour de service décrite ci-dessous n'a pas été réalisée et relève des perspectives.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `01_business_understanding.ipynb` §2.3, future `06_decision_layer.ipynb` |

## Contexte

La décision opérationnelle UM se prend au niveau du **tour de service**, pas au niveau de la course ou du tronçon individuel. La composition matérielle (rame simple vs UM) est héritée sur l'ensemble d'un tour et ne peut être modifiée librement entre chaque course.

Points de changement de composition sur la R35 : **Vevey** et **Blonay** uniquement.

Le modèle ML prédit la charge au grain **tronçon × course × date** — le grain disponible dans les données APC. Pour traduire ces prédictions en recommandation UM exploitable, il est nécessaire de relier les courses à leur tour de service.

**Problème :** les tours de service ne peuvent pas être reconstruits de manière fiable à partir des seules données APC. L'information de rotation provient de la planification, pas des mesures de comptage.

## Décision

**Les tours de service ne seront pas reconstruits depuis les APC seul. Une table de rotations issue de la planification sera intégrée à la couche de décision.**

Un dataset de rotations pour l'année 2024 existe déjà. Il sera la première source intégrée.

## Architecture recommandée

```
data/external/rotations/          ← source brute (Excel/CSV planification)
scripts/sources/build_rotations_r35_2024.py  ← script de structuration
data/dimension/dim_rotations_r35.parquet     ← table propre (référentiel)
```

## Grain et schéma cible de `dim_rotations_r35`

| Colonne | Type | Description |
|---|---|---|
| `annee_horaire` | str | Année horaire (ex. : H24) |
| `id_tour_service` | str | Identifiant du tour de service |
| `horaire_numero_train` | str | Numéro de train / course |
| `base_sens` | str | Sens de circulation |
| `cal_heure_depart` | time | Heure de départ prévue |
| `id_gare_depart` | str | Abréviation gare de départ |
| `id_gare_arrivee` | str | Abréviation gare d'arrivée |
| `ordre_dans_tour` | int | Position ordinale de la course dans le tour |
| `point_changement_possible` | bool | La course se termine/commence à un point de changement (VV ou BLON) |
| `source_version` | str | Version / date du plan de rotation |

## Rôle dans l'artefact final

L'architecture de décision est la suivante :

1. Le modèle prédit `prediction_voyageurs_2eme_classe` au niveau **tronçon × course × date**.
2. Les prédictions sont agrégées par course (charge maximale sur les tronçons d'une course).
3. Les courses sont rattachées à un tour de service via `dim_rotations_r35`.
4. La couche de décision recommande ou non une UM au niveau du **tour**, en fonction du risque maximal observé/prédit sur les courses et tronçons du tour.
5. L'utilisateur métier reçoit une recommandation explicable (SHAP), qu'il peut accepter, modifier ou rejeter.

## Formulation recommandée pour la documentation

"La prédiction est produite au niveau tronçon × course × date, car il s'agit du grain disponible dans les données APC. La décision opérationnelle UM ne se prend toutefois pas à ce niveau : elle concerne un tour de service, dont la composition est héritée sur plusieurs courses. Les tours ne pouvant pas être reconstruits de manière fiable à partir des seules données APC, une table de rotations issue de la planification sera intégrée à la couche de décision, dans un premier temps pour l'année 2024."

## Limites

- La table de rotations est disponible pour 2024 uniquement à ce stade. Les années antérieures nécessiteront des données de planification supplémentaires ou une hypothèse de stabilité inter-annuelle.
- La logique de rotation peut varier selon le type de jour (semaine / weekend / fériés) et selon la saison. Le schéma cible devra accommoder ces variations.
- Les changements de composition en cours de service (panne, renfort) ne sont pas couverts par la table de rotations — ils restent une décision opérationnelle non modélisée.

## Conséquences

- La pipeline actuelle (stages 01–08 + ml_dataset) produit les prédictions au grain tronçon. Elle reste inchangée.
- La couche de décision est une étape distincte, post-prédiction, qui consomme `ml_dataset.parquet` + `dim_rotations_r35.parquet`.
- L'ajout de `dim_rotations_r35` dans le Makefile est prévu comme cible indépendante (comme les autres tables `dim_*`).

## Fichiers à créer

- `data/external/rotations/` (répertoire)
- `scripts/sources/build_rotations_r35_2024.py`
- `data/dimension/dim_rotations_r35.parquet`
- Future : `notebooks/06_decision_layer.ipynb`
