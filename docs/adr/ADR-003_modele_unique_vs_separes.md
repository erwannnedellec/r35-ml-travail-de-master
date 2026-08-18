---
id: ADR-003
ancien_id: ADR-03
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-052]
revoque_par: [ADR-022]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-003 — Architecture modèle : unique + feature `base_segment` vs deux modèles séparés

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-052 ; révoquée par ADR-022.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §4.3 |

## Contexte

La ligne R35 présente deux segments géographiques aux dynamiques très différentes :

| Segment | Tronçons | Profil | TJM moyen |
|---|---|---|---|
| **Bas de ligne** | VV → Blonay | Urbain / pendulaire / scolaire | ~100–160 voy |
| **Haut de ligne** | Blonay → Pléiades | Montagne / touristique / loisirs | ~20–60 voy |

Le test de Kolmogorov-Smirnov entre les distributions de charge des deux segments (§4.3) donne **KS(bas, haut) = 0.456**, valeur très supérieure au seuil de stationnarité (0.15). Deux architectures sont envisageables :

| Architecture | Avantages | Inconvénients |
|---|---|---|
| **Modèle unique + feature `base_segment`** | Partage des paramètres entre segments ; plus simple à maintenir | Risque de sous-performance si les dynamiques sont trop différentes |
| **Deux modèles séparés** (bas / haut) | Spécialisation complète | Double complexité de maintenance ; moins de données par modèle |

## Décision

**Modèle unique + feature `base_segment` (bas / haut / mixte) retenu en V1.**

Justification :
- Approche standard en prévision de transport pour des lignes à profil mixte
- La feature `base_segment` permet au modèle d'apprendre les effets d'interaction différenciés
- Réduit le risque de sur-apprentissage sur le segment haut (moins d'observations)
- Un seul pipeline de prédiction et d'interprétabilité SHAP à déployer dans Dataiku

## Conséquences

- **Feature** : `base_segment` (bas / haut / mixte) ajoutée au dataset — déjà présente dans le pipeline.
- **Ablation study** : comparaison modèle unique vs deux modèles séparés planifiée en `05_feature_analysis`.
- **SHAP** : l'interprétation SHAP devra être ventilée par segment pour être opérationnellement utile.
- **Seuil UM** : la granularité du seuil par groupe (adhérence vs crémaillère) reste calibrable indépendamment dans la couche de décision (ADR-004).

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| Deux modèles séparés (bas/haut) | Reporté comme ablation study — pas exclu définitivement |
| Feature d'interaction segment × saison | Complémentaire, pas exclusif — peut être ajoutée en `05_feature_analysis` |

## Addendum (2026-07-24)

L'architecture à modèle unique avec base_segment est supersédée par la campagne comparative ultérieure : architecture segmentée à deux régresseurs bas et haut (ADR-031, confirmée ADR-052). La définition du découpage de ligne reste active.
