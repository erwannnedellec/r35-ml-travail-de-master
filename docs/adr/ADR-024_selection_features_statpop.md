---
id: ADR-024
ancien_id: ADR-25
date_decision: 2026-05-21
statut: actif
amende_par: [ADR-025]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-024 — Sélection de features STATPOP : retrait des redondances arithmétiques

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été amendée par ADR-025.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

## Statut
Accepté — 2026-05-21

## Contexte

Le dataset `ml_dataset` contient un sous-espace de features `spatial_*` composé de :
- 4 features de topologie (`spatial_distance_km`, `spatial_segment`, `spatial_gare_depart_ordre`, `spatial_gare_arrivee_ordre`)
- 50 features STATPOP (25 indicateurs × 2 côtés : départ et arrivée)

Un diagnostic de corrélations a été conduit sur le sous-espace STATPOP pour identifier les multicolinéarités susceptibles de dégrader l'interprétabilité SHAP du modèle XGBoost et d'introduire une instabilité dans les importances de features.

## Diagnostic

Deux clusters de redondance ont été identifiés :

### Cluster 1 — Redondance arithmétique exacte (r = 1.00)

Le buffer STATPOP est calculé avec un rayon fixe `RADIUS_M = 500` (m) pour toutes les gares. La surface de capture est donc constante : `BUFFER_AREA_KM2 = π × 0.25 ≈ 0.785 km²`.

Par construction dans `build_fact_statpop_gare.py` :
```
densite_population_500m_km2 = population_500m_total / 0.785
densite_menages_500m_km2    = menages_500m_total    / 0.785
```

Ces densités sont des transformations affines des totaux. La corrélation est exactement 1.00 pour toutes les gares et tous les millésimes.

### Cluster 2 — Redondance quasi-parfaite (r = 0.96)

`taille_menage_moyenne_estimee` est calculée dans `build_fact_statpop_gare.py` comme la moyenne pondérée :

```
taille_moy = (HP01 + 2·HP02 + 3·HP03 + 4·HP04 + 5·HP05 + 6·HP06) / HPTOT
```

`part_grands_menages_4p_plus` est `(HP04 + HP05 + HP06) / HPTOT`.

Les grands ménages (≥ 4 personnes) dominent arithmétiquement le numérateur de la taille moyenne. Les deux variables mesurent essentiellement la même dimension de la structure des ménages.

## Décision

Retrait de 3 features (× 2 côtés = 6 colonnes au total) du set `STATPOP_KEEP_SUFFIXES` dans `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` :

| Feature retirée | Feature conservée | Raison |
|---|---|---|
| `densite_population_500m_km2` | `population_500m_total` | r = 1.00 par construction |
| `densite_menages_500m_km2` | `menages_500m_total` | r = 1.00 par construction |
| `taille_menage_moyenne_estimee` | `part_grands_menages_4p_plus` | r = 0.96, redondance quasi-parfaite |

**Principe de conservation** : on garde les valeurs absolues (totaux) et les parts bornées `[0, 1]`, qui sont plus interprétables et dont le sens ne dépend pas d'un paramètre de rayon de buffer (à comparer avec les densités, qui deviendraient fausses si le rayon change).

## Implémentation

Retrait localisé uniquement dans `STATPOP_KEEP_SUFFIXES` du script pipeline. La table source `statpop_clean.parquet` conserve l'intégralité des 27 features d'origine. La réversibilité est totale : réintroduire les variables retirées nécessite uniquement la réinsertion de leur suffixe dans le set et le recalcul du `stage_06`.

**Fichier modifié** : `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py`

## Conséquences

- **Avant** : 54 features `spatial_*` (4 topologie + 50 STATPOP)
- **Après** : 52 features `spatial_*` (4 topologie + 48 STATPOP)
- Élimination de toutes les paires avec r > 0.95 dans le sous-espace STATPOP
- Amélioration attendue de la stabilité et de l'interprétabilité des valeurs SHAP

## Réversibilité

Les variables retirées sont recalculables arithmétiquement depuis les features conservées :
- `densite_pop_500m_km2 = population_500m_total / 0.785`
- `densite_menages_500m_km2 = menages_500m_total / 0.785`
- `taille_menage_moy` : relation empirique non-linéaire avec `part_grands_menages_4p` (r = 0.96)

La table `statpop_clean.parquet` préserve les 27 features d'origine sans modification.

## Références

- [ADR-011](ADR-011_imputation_millesimes_statpop_manquants.md) — Imputation des millésimes 2021 et 2023
- [ADR-006](ADR-006_statpop_dernier_millesime_disponible.md) — Choix du millésime de référence
- `scripts/sources/build_fact_statpop_gare.py` — Construction des features STATPOP
