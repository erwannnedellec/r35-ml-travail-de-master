---
id: ADR-006
ancien_id: ADR-06
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-039, ADR-063]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-006 — STATPOP : stratégie du dernier millésime disponible

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-039, ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `02_data_understanding_statpop.ipynb`, future `04_data_preparation.ipynb` |

## Contexte

STATPOP (OFS) est une source socio-démographique structurelle décrivant la population résidant à proximité de chaque arrêt R35. Elle est utile comme feature ML car elle capte la demande potentielle de transport et l'urbanité des zones desservies.

Contrainte opérationnelle : STATPOP est publiée avec un délai. Un millésime n'est généralement publié qu'un an après l'année de référence (ex. : STATPOP 2024 publié en 2025). En exploitation J-1, il est impossible d'utiliser le millésime de l'année en cours — il n'est pas encore disponible.

La jointure naïve `date.year → millésime STATPOP correspondant` crée un **biais d'optimisme** dans l'évaluation historique : elle utilise rétrospectivement des données qui n'auraient pas été disponibles au moment de la prédiction.

## Décision

**En exploitation opérationnelle, STATPOP doit être joint selon le dernier millésime disponible à la date de prédiction**, et non selon l'année calendaire de la date de circulation.

**Règle simplifiée :**
```
millesime_disponible(date_prediction) = min(date_prediction.year - 1, max_millesime_disponible)
```

Exemple : pour une prédiction faite en mai 2025, on utilise STATPOP 2024 (si publié) ou 2023 (sinon).

## Stratégies selon le contexte

| Contexte | Stratégie | Justification |
|---|---|---|
| **Entraînement exploratoire (phase DU)** | Jointure par année civile (`date.year`) | Simplifie l'exploration ; biais documenté comme limite acceptable |
| **Entraînement et évaluation finale** | Jointure par dernier millésime disponible | Réalisme opérationnel ; évite le biais d'optimisme |
| **Déploiement opérationnel** | Dernier millésime OFS publié à la date de prédiction | Seule source disponible en production |

La stratégie retenue pour l'entraînement final sera documentée dans `04_data_preparation.ipynb`.

## Impact estimé

L'évolution inter-annuelle de STATPOP est faible (+9,5 % sur 10 ans pour la population totale dans les buffers 500 m). L'impact du biais de millésime est donc **probablement faible** en pratique, mais doit être documenté comme limite méthodologique.

## Gestion des variables manquantes en 2021 et 2023

Les millésimes 2021 et 2023 (source OFS) ne contiennent pas de données ménages (HP*) ni HPI. Les 13 variables concernées sont comblées par **interpolation linéaire** par gare entre les millésimes adjacents :

| Millésime incomplet | Bornes d'interpolation | Résultat |
|---|---|---|
| 2021 | 2020 et 2022 (équidistants) | moyenne arithmétique |
| 2023 | 2022 et 2024 (équidistants) | moyenne arithmétique |

Variables interpolées : `menages_500m_total`, `densite_menages_500m_km2`, `population_par_menage_500m`, `part_menages_1_personne`, `part_grands_menages_4p_plus`, `taille_menage_moyenne_estimee`, `hpi_classe_max_500m`, `hpi_hectares_classe_1_count`, `hpi_hectares_classe_2_count`, `hpi_hectares_classe_manquante_count`, `hpi_hectares_autre_classe_count`, `part_hectares_hpi_non_plausible`, `flag_qualite_statpop_faible`.

L'interpolation est réalisée dans `build_fact_statpop_gare.py` via `interpolate_missing_millesimes()` (pandas `interpolate(method='index')`). Les colonnes entier sont arrondies après interpolation.

Ces variables interpolées sont ensuite **intégrées dans le ml_dataset** via `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (extension de `STATPOP_KEEP_SUFFIXES`).

## Limites documentées

1. Les dates exactes de publication des millésimes OFS ne sont pas toutes connues. La règle simplifiée `année - 1` peut ne pas être exacte pour tous les millésimes.
2. L'interpolation linéaire pour 2021 et 2023 est une approximation : elle suppose une évolution monotone entre les millésimes adjacents. Pour des variables lentes (STATPOP évolue de ~1–2 % par an), cette hypothèse est raisonnable.
3. La granularité hectare de STATPOP (puis agrégée au buffer 500 m par gare) introduit une approximation spatiale, indépendante du problème de millésime.

## Conséquences

- Le script `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` devra implémenter une logique de jointure par millésime disponible (à la place de la jointure par année civile directe).
- La table `statpop_clean.parquet` contient la colonne `annee_enquete_statpop` — utiliser cette clé pour la jointure contrôlée.
- Le report de cette décision à `04_data_preparation.ipynb` est intentionnel : le choix final dépend des performances observées à la modélisation.

## Fichiers impactés

- `scripts/sources/build_fact_statpop_gare.py` (interpolation 2021/2023 via `interpolate_missing_millesimes()`)
- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (logique de jointure + extension `STATPOP_KEEP_SUFFIXES` pour ménages et HPI)
- `data/processed/sources/statpop_clean.parquet` (millésime source, désormais sans NA sur ménages/HPI)
- `notebooks/02_data_understanding_statpop.ipynb` §QG (documentation de la contrainte)
- Future : `notebooks/04_data_preparation.ipynb` (décision et implémentation finale)
