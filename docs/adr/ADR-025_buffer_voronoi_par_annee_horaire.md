---
id: ADR-025
ancien_id: ADR-26
date_decision: 2026-05-21
statut: amendé
amende_par: [ADR-039, ADR-063]
modifie: [ADR-024]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-025 — Refonte du buffer STATPOP : Voronoi clippé par année horaire

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-039, ADR-063.
> Décisions antérieures que ce document modifie : ADR-024.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

## Statut
Accepté — 2026-05-21

## Contexte

Le diagnostic `docs/diagnostic_buffers_statpop.md` (2026-05-21) a établi que le buffer disque uniforme de 500 m crée des chevauchements sévères entre gares voisines :
- **79 % des gares** ont un taux de captation propre < 50 %
- La gare la plus touchée (VVVI) ne dispose que de **11 % de zone exclusive**
- 8 paires présentent plus de 50 % du buffer en commun (pire cas : VVVI ↔ CLIE à 226 m, 71.5 % en commun)

De plus, la topologie R35 évolue dans le temps :
- **CLIE** (Clies) : active H16–H18, fermée fin H18
- **GIL** (Gilamont) : actif H16–H22, fermé fin H22
- **VVVI** (Vevey Vignerons) : actif depuis H23, remplace GIL

Un buffer disque ignorant ces évolutions topologiques attribue les mêmes hectares à GIL et VVVI simultanément, même pour les années où l'une ou l'autre est fermée.

## Décision

Remplacer le buffer disque uniforme par un **diagramme de Voronoi clippé à 500 m, recalculé pour chaque topologie active**.

Pour chaque combinaison (année horaire HY, gare g active en HY) :

```
Z(g, HY) = (polygone de Voronoi de g sur les gares actives en HY) ∩ (disque 500 m centré sur g)
```

Propriétés garanties :
1. **Aucun chevauchement** entre zones de gares actives la même année (partition de Voronoi)
2. **Zone maximale de 500 m** depuis chaque gare (clippage disque)
3. **Cohérence topologique** : les zones reflètent les gares effectivement actives

## Mapping millésime STATPOP → topologie

Convention : le millésime STATPOP année civile Y utilise la topologie de l'année horaire HY (même numéro), qui couvre la majorité des jours de l'année civile Y. Pour STATPOP 2015 (antérieur à H16), la topologie H16 est utilisée par défaut car H15 est hors périmètre des données APC.

| Millésime STATPOP | Année horaire | Gares actives (résumé) |
|---|---|---|
| 2015 | H16 | 18 gares (GIL + CLIE actifs ; VVVI absent) |
| 2016 | H16 | 18 gares |
| 2017 | H17 | 18 gares (GIL + CLIE actifs) |
| 2018 | H18 | 18 gares (GIL + CLIE actifs) |
| 2019 | H19 | 17 gares (CLIE fermée) |
| 2020 | H20 | 17 gares |
| 2021 | H21 | 17 gares |
| 2022 | H22 | 17 gares (GIL encore actif) |
| 2023 | H23 | 17 gares (GIL fermé, VVVI actif) |
| 2024 | H24 | 17 gares |

Source des gares actives : `data/processed/horaires_r35_arrets_officiels.parquet` (PDFs H16–H25 officiel MVR).

## Implémentation

**Fichier modifié** : `scripts/sources/build_fact_statpop_gare.py`

Nouvelles fonctions :
- `load_active_gares_by_horaire()` — charge les gares actives depuis les horaires officiels
- `compute_voronoi_zones()` — calcule les polygones Voronoi clippés (shapely 2.0)
- `get_voronoi_zones_for_year()` — cache par topologie pour éviter les recalculs

Modifications :
- `aggregate_raw_values_for_station()` — utilise `shapely.within()` (vectorisé) au lieu de distance euclidienne
- `build_features_from_raw_aggregates()` — accepte `zone_area_km2` réelle pour les densités
- `aggregate_for_station()` — accepte un polygone Voronoi
- `build_fact()` — itère uniquement sur les gares actives par millésime

**Comportement de la sortie** :
- Avant : 19 gares × 10 millésimes = 190 lignes
- Après : 174 lignes (GIL 8 ans, CLIE 4 ans, VVVI 2 ans, 16 autres × 10 ans)

Aucune modification de schéma (27 features, mêmes noms, mêmes types).

## Conséquences

- Les features `densite_population_500m_km2` et `densite_menages_500m_km2` dans `statpop_clean.parquet` utilisent désormais l'aire réelle de la zone Voronoi comme dénominateur (plus correct qu'une constante). Ces features sont exclues du ML dataset (ADR-024) mais leur valeur en source est améliorée.
- La colonne `statpop_hectares_count` reflète les hectares dans la zone Voronoi, pas dans le disque.
- Aucun changement de schéma dans `stage_06_statpop.parquet` ni `ml_dataset.parquet`.
- Les gares inactives pour un millésime donné n'ont plus d'entrée dans `statpop_clean.parquet` (comportement correct : pas de jointure APC possible sur ces lignes).

## Gestion des transitions topologiques

Entre H22 et H23 (GIL → VVVI) :
- STATPOP 2022 : GIL reçoit sa zone Voronoi habituelle ; VVVI absent
- STATPOP 2023 : VVVI reçoit une zone Voronoi incluant les hectares autrefois attribués à GIL ; GIL absent

Ce saut de zone est intentionnel et reflète la réalité du réseau. Le modèle XGBoost gère cette discontinuité via la feature `horaire_annee_horaire` déjà présente dans le dataset.

## Trade-offs et limites

1. **Nom des features légèrement trompeur** : `population_500m_total` désigne la population dans la zone Voronoi ≤ 500 m, pas un disque de 500 m. Renommage (`pop_zone_total`) envisageable dans une itération future mais non prioritaire.
2. **Dépendance à shapely** : ajouté comme dépendance Python du projet (`pip install shapely`).
3. **Performance** : le calcul Voronoi est mis en cache par topologie (3 topologies distinctes = 3 calculs) — négligeable à l'exécution.
4. **Couverture < 500 m pour les gares en cluster** : par construction, les zones Voronoi des gares très proches sont plus petites que le disque de 500 m. La population capturée est donc plus faible mais correspond mieux à la zone d'influence réelle.

## Réversibilité

Pour revenir au buffer disque, remplacer le filtrage `shapely.within(points_arr, zone)` par `dist <= RADIUS_M` dans `aggregate_raw_values_for_station()` et restaurer `build_fact()` sans les zones Voronoi. La sauvegarde de l'ancien fichier est disponible : `statpop_clean_disque500.parquet`.

## Références

- `docs/diagnostic_buffers_statpop.md` — diagnostic ayant motivé la décision
- [ADR-024](ADR-024_selection_features_statpop.md) — retrait des redondances arithmétiques (préservé)
- [ADR-011](ADR-011_imputation_millesimes_statpop_manquants.md) — imputation 2021/2023 (inchangée)
- [ADR-006](ADR-006_statpop_dernier_millesime_disponible.md) — choix du millésime de référence
