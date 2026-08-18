---
id: ADR-010
ancien_id: ADR-10
date_decision: 2026-05
statut: amendé
amende_par: [ADR-019, ADR-037, ADR-060]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-010 — Famille des features historiques APC : 6 statistiques par variable

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-019, ADR-037, ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Suffixes** | `lag2`, `win7_mean`, `win7_median`, `win7_max`, `win7_std`, `win7_n_surcharges` |
| **Remplace** | 2 features par variable : `lag_1j_moy`, `lag_7j_moy` |

## Contexte

La version initiale du script calculait uniquement deux features par variable source (`lag_1j_moy` et `lag_7j_moy`), soit 6 features au total. Ces deux features capturent uniquement la **tendance centrale** (moyenne) sur des fenêtres temporelles différentes.

La cible ML (`target_voyageurs_2eme_classe`) et la règle de décision UM (`>= 94 voyageurs`) orientent le problème vers la **détection de pics de fréquentation** (queue de distribution), pas vers la prédiction de la fréquentation moyenne. Des modèles de tendance centrale seuls sont insuffisants pour capturer la variance intra-groupe et l'historique de saturation.

## Décision

**6 features dérivées par variable source** (3 variables × 6 statistiques = 18 features historiques) :

| Suffixe | Type | Fenêtre effective | Signal capté |
|---|---|---|---|
| `lag2` | ponctuel | J-2 | Continuité immédiate (avant-hier) |
| `win7_mean` | tendance centrale | J-8 à J-2 | Niveau moyen de la semaine écoulée |
| `win7_median` | tendance centrale robuste | J-8 à J-2 | Niveau médian, insensible aux outliers |
| `win7_max` | extrême | J-8 à J-2 | Pic maximal observé dans la semaine |
| `win7_std` | dispersion | J-8 à J-2 | Variabilité hebdomadaire de la fréquentation |
| `win7_n_surcharges` | compteur métier | J-8 à J-2 | Nombre de jours > 94 voyageurs (2ème classe uniquement) |

`win7_n_surcharges` est calculée **uniquement pour `target_voyageurs_2eme_classe`** (la cible ML, cf. ADR-001 et ADR-004). Pour les autres variables sources (1ère classe, total), cette feature est mise à NaN.

## Justification

**Détection de pics :** `win7_max` et `win7_n_surcharges` capturent directement l'historique de saturation récente — l'information la plus pertinente pour anticiper un nouveau pic.

**Robustesse aux outliers :** `win7_median` est préférée à `win7_mean` pour les groupes avec des jours atypiques isolés (annulations, événements exceptionnels). Offrir les deux laisse le modèle arbitrer.

**Dispersion comme signal :** `win7_std` encode la variabilité du tronçon/train. Un tronçon à forte std est plus difficile à prédire ; le modèle peut l'apprendre comme facteur d'incertitude.

**Tri empirique via SHAP :** l'objectif n'est pas de pré-sélectionner les features utiles mais d'en offrir un ensemble riche pour que l'analyse SHAP (phase modélisation) effectue le tri empirique. Des features redondantes ou non informatives seront identifiées et éliminées à cette étape.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| 2 features (mean 1j + mean 7j) — ancienne version | Insuffisant pour capter la queue de distribution — tendance centrale seule |
| Percentiles (p75, p90) à la place de max | Plus stables que max mais nécessitent plus d'historique pour être significatifs ; max est plus interprétable opérationnellement |
| Features sur fenêtre 28j | Reportées : fenêtre 7j déjà couvre les patterns hebdomadaires ; la valeur marginale d'une fenêtre 28j sera évaluée en phase SHAP si les features 7j s'avèrent insuffisantes |
| win7_n_surcharges pour toutes les variables sources | Non pertinent pour 1ère classe (saturation quasi-inexistante, cf. ADR-001) et total (seuil différent, cf. ADR-004) |

## Conséquences

- Passage de 6 à 18 features historiques dans `stage_08_features.parquet`.
- Noms de colonnes mis à jour (préfixe `histo_`, suffixes descriptifs) — incompatibles avec l'ancienne version de stage_08 : recalcul nécessaire.
- `build_ml_dataset.py` doit être vérifié pour s'assurer qu'il n'exclut pas les nouvelles colonnes `histo_*`.
- Les analyses SHAP en phase modélisation fourniront le tri empirique définitif des 18 features.

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constantes `HISTO_SUFFIXES`, `SEUIL_UM_2EME`, fonction `_feature_col`, bloc de calcul des lags
- `notebooks/04_data_preparation.ipynb` — inventaire des features à mettre à jour
- `notebooks/05_feature_analysis.ipynb` (futur) — analyse SHAP des 18 features historiques
