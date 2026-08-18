---
id: ADR-039
ancien_id: ADR-41
date_decision: 2026-06-04
statut: remplacé
remplace_par: [ADR-063]
modifie: [ADR-006, ADR-025]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-039 — Mapping STATPOP par année calendaire et carry-forward 2024 pour 2025

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Décisions antérieures que ce document modifie : ADR-006, ADR-025.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (v3, 2026-06-16) — mapping Z-2 et imputation forward-fill révisés par ADR-063 |
| **Date** | 2026-06-04 (v2) / 2026-06-16 (v3) |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-006 (stratégie millésime), ADR-008 (lag opérationnel J-2), ADR-011 (interpolation STATPOP 2021 et 2023 — révisé), ADR-024 (géométrie Voronoi clippée), ADR-037 (grain enrichi histo_*), ADR-038 (extension périmètre H25), **ADR-063** (causalité disponibilité STATPOP — révision v3) |
| **Historique** | v1 (initial) : mapping par `horaire_annee_horaire` — révoqué pour fuite temporelle. v2 (2026-06-04) : mapping par année calendaire stricte, interpolation 2021/2023. **v3 (2026-06-16) : mapping Z-2 conservateur (borne Jan 1 Y+2) + forward-fill causal (remplace interpolation).** |

## Contexte

L'extension du périmètre temporel à l'année horaire H25 (décembre 2024 – décembre 2025, à acter par ADR-038) confronte le pipeline à un problème de disponibilité de la source STATPOP. L'Office fédéral de la statistique publie les millésimes STATPOP avec une latence de 12 à 18 mois sur l'année de référence. Au moment du gel du dataset (juin 2026), le millésime 2024 est le dernier exact disponible ; le millésime 2025 n'est pas publié.

Cet ADR articule deux décisions liées :

1. **Refactorisation du mapping millésime** : remplacement de la jointure naïve `dates.dt.year` (stratégie "exploratoire" per ADR-006) et de la première version de l'ADR-039 par un mapping explicite indexé sur l'année calendaire, garantissant la pureté temporelle stricte.

2. **Stratégie de gestion de 2025** : utilisation du millésime 2024 comme proxy pour les dates de l'année calendaire 2025, avec traçabilité explicite via une colonne de source.

## Pourquoi année calendaire et non année horaire

Les années horaires CFF/MOB s'étendent de mi-décembre à mi-décembre (par exemple H22 = 12/12/2021 → 10/12/2022). La première version de cet ADR utilisait un mapping `STATPOP_MAPPING` indexé sur `horaire_annee_horaire`, ce qui attribuait à H22 le millésime STATPOP 2022. Conséquence : les voyageurs comptés en décembre 2021 (qui appartiennent à H22) recevaient une donnée STATPOP datée du **31 décembre 2022** — soit une fuite temporelle de jusqu'à 12 mois.

Cette fuite est incohérente avec le principe de pureté temporelle stricte qui sous-tend le reste du projet :
- L'ADR-008 impose un lag opérationnel J-2 pour les comptages APC (jamais utiliser une donnée non-consolidée au moment de la décision).
- L'ADR-037 implémente un shift dynamique respectant strictement cette contrainte.

Indexer le mapping sur l'année calendaire de `base_date` supprime cette fuite : les 18-21 jours de décembre de chaque année calendaire qui appartiennent à l'année horaire suivante reçoivent le millésime STATPOP cohérent avec leur date réelle, et non avec leur année horaire.

L'amplitude empirique de la correction est faible (variation interannuelle STATPOP ≈ 1 %, et seulement ~5 % des observations sont en décembre). Mais l'amélioration de la défensibilité méthodologique est significative pour le mémoire.

## Options considérées (pour la gestion de 2025)

| Option | Description | Forces | Faiblesses |
|---|---|---|---|
| A. Carry-forward depuis 2024 | Utiliser STATPOP 2024 comme proxy pour les dates de l'année calendaire 2025 | Simple, transparent, sans extrapolation hasardeuse ; réversible | Assume une variation démographique 2024→2025 négligeable (en réalité ≈ 0.5–1 %) |
| B. Extrapolation linéaire | Projeter la tendance 2022→2023→2024 à 2025 | Plus sophistiqué en apparence | Amplifie le bruit sur fenêtre courte ; sensible aux phénomènes ponctuels (nouvelles constructions) |
| C. Valeurs manquantes (NaN) | Ne pas attribuer STATPOP aux dates 2025 | Théoriquement le plus pur | XGBoost gère mal les NaN systématiques sur ~25 % du test set ; biais d'apprentissage difficile à diagnostiquer |

## Décision

**[v3, ADR-063] Adoption d'un mapping Z-2 conservateur** indexé sur l'année calendaire (`base_date.dt.year`), avec forward-fill causal pour les millésimes HP*/HPI manquants :

```python
# ADR-063 : mapping Z-2 (borne disponibilité Jan 1 Y+2)
MAPPING_BC_MILLESIME = {
    2021: 2019,   # exact
    2022: 2020,   # exact
    2023: 2021,   # HP*/HPI forward-fill ← 2020 (OFS ne publie pas HP 2021)
    2024: 2022,   # exact
    2025: 2023,   # HP*/HPI forward-fill ← 2022 (OFS ne publie pas HP 2023)
}
```

**[v2, archivée — fuite de disponibilité]** La version v2 appliquait un mapping contemporain (Z→Z) avec interpolation pour 2021/2023 :

```python
# v2 — ARCHIVÉE : mapping contemporain (fuite de disponibilité)
STATPOP_MAPPING = {
    2021: {"millesime": 2021, "source": "interpole"},     # ADR-011 : utilisait borne future 2022
    2022: {"millesime": 2022, "source": "exact"},
    2023: {"millesime": 2023, "source": "interpole"},     # ADR-011 : utilisait borne future 2024
    2024: {"millesime": 2024, "source": "exact"},
    2025: {"millesime": 2024, "source": "carry_forward"},
}
```

### Conséquences sur la composition des sources par année horaire

Avec ce mapping, chaque année horaire reçoit potentiellement deux millésimes STATPOP selon la date de la course :

| Année horaire | Composition source STATPOP |
|---|---|
| H22 (12/12/2021–10/12/2022) | déc. 2021 : `interpole` (millésime 2021) ; jan–nov. 2022 : `exact` (millésime 2022) |
| H23 (11/12/2022–09/12/2023) | déc. 2022 : `exact` (millésime 2022) ; jan–nov. 2023 : `interpole` (millésime 2023) |
| H24 (10/12/2023–14/12/2024) | déc. 2023 : `interpole` (millésime 2023) ; jan–déc. 2024 : `exact` (millésime 2024) |
| H25 (15/12/2024–13/12/2025) | déc. 2024 : `exact` (millésime 2024) ; jan–nov. 2025 : `carry_forward` (millésime 2024) |

Cette granularité fine offre une traçabilité supérieure à un mapping unique par année horaire et restitue exactement la cohérence temporelle attendue. La colonne `spatial_statpop_source_*` permet d'identifier au niveau de la ligne quel régime STATPOP s'applique.

### Justification du carry-forward pour 2025

L'option A (carry-forward depuis 2024) est retenue sur trois arguments :

1. **Magnitude de l'erreur faible** : la variation annuelle de population dans un rayon de 500 mètres autour d'une gare R35 est de l'ordre de 0.5 à 1 % par an. Cette amplitude n'a pas d'effet matériel sur la prédiction de fréquentation. Le signal STATPOP capture une réalité structurelle (zone dense vs zone peu peuplée) et non conjoncturelle.

2. **Cohérence avec la philosophie du projet** : privilégier les solutions transparentes et défendables aux solutions sophistiquées qui ajoutent du bruit (principe "empirique avant méthodologique").

3. **Réversibilité** : quand STATPOP 2025 sera publié (probablement courant 2026–2027), la substitution est triviale — une seule ligne à modifier dans `STATPOP_MAPPING`.

## Convention de traçabilité

Deux colonnes sont ajoutées au pipeline STATPOP :

- `spatial_statpop_source_depart`
- `spatial_statpop_source_arrivee`

Ces colonnes prennent les valeurs suivantes (par ligne, selon l'année calendaire de `base_date`) :

| Valeur | Signification | Années calendaires concernées (Z-2 mapping) |
|---|---|---|
| `exact` | Millésime OFS publié exact, pas d'imputation HP* | 2021→2019, 2022→2020, 2024→2022 |
| `forward_fill` | Millésime exact population, HP*/HPI forward-fillés depuis millésime précédent | 2023→2021 (HP←2020), 2025→2023 (HP←2022) |

Convention cohérente avec les colonnes de métadonnées existantes : `event_ski_source`, `event_narcisses_source`, `event_covid_phase`.

**Important** : `spatial_statpop_source_depart` et `spatial_statpop_source_arrivee` sont des métadonnées de traçabilité. Elles doivent être ajoutées à la liste `COLS_EXCLUES` du notebook de modélisation lors du run final coordonné (à faire avec ADR-037 et ADR-038).

## Conséquences

### Positives

- **Cohérence temporelle stricte** : suppression de la fuite temporelle de jusqu'à 12 mois qui affectait les courses de décembre dans la v1 de l'ADR. Alignement avec ADR-008 et ADR-037.
- **Traçabilité granulaire** : chaque observation reçoit une source STATPOP cohérente avec sa date calendaire ; la colonne `spatial_statpop_source_*` peut varier au sein d'une même année horaire (décembre vs reste), reflétant fidèlement la réalité.
- **Extensibilité** : la constante `STATPOP_MAPPING` permet l'ajout du millésime 2025 publié en une ligne.
- **Auditabilité** : la validation post-construction affiche une distribution croisée année horaire × année calendaire permettant de vérifier explicitement que les cours de décembre N reçoivent bien le millésime N (et non N+1).

### Limitations à documenter dans le mémoire

- **Sous-estimation potentielle dans les zones à forte croissance démographique** : un nouveau quartier construit entre 2024 et 2025 ne sera pas reflété dans STATPOP. L'effet est probablement marginal sur R35 (zone géographique stabilisée).
- **Le modèle apprend l'effet STATPOP sur 2022–2024 (millésimes exacts et interpolés) et l'applique à 2025 (carry-forward)** : si une transition démographique structurelle a lieu en 2025, elle ne sera pas captée.

### Comparaison avec la v1 de l'ADR (révoquée)

| Aspect | v1 (révoquée) | v2 (présente) |
|---|---|---|
| Clé de mapping | `horaire_annee_horaire` (H15–H25) | Année calendaire (2015–2025) |
| Fuite temporelle décembre | Jusqu'à 12 mois | Aucune |
| Composition source par AH | Source unique par AH | Source potentiellement mixte (déc. vs reste) |
| Traçabilité | Deux colonnes `_source` | Deux colonnes `_source` (inchangé) |

## Validation post-déploiement

Quand le millésime STATPOP 2025 sera publié (probablement Q2–Q3 2027) :

1. Remplacer `{"millesime": 2024, "source": "carry_forward"}` par `{"millesime": 2025, "source": "exact"}` dans `STATPOP_MAPPING`
2. Rejouer le pipeline depuis stage_06 et reconstruire `ml_dataset.parquet`
3. Réentraîner le modèle de référence et comparer les métriques

**Critère de validation** : si Δ R² < 0.005 sur le segment haut H25, l'hypothèse de carry-forward acceptable est confirmée empiriquement. Si Δ R² > 0.005, documenter la magnitude de l'erreur introduite.

## Fichiers impactés

- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` : `STATPOP_MAPPING` ré-indexé par année calendaire (`int`), `build_statpop_millesime_and_source` lit `base_date.dt.year`, summary enrichi avec distribution croisée AH × année calendaire.
- `data/processed/stage_06_statpop.parquet` : `spatial_statpop_source_*` peut désormais varier au sein d'une même année horaire (décembre vs reste).
- `data/processed/ml_dataset.parquet` : propagation des deux colonnes jusqu'au dataset final.
- À faire lors du run final : ajouter `spatial_statpop_source_depart` et `spatial_statpop_source_arrivee` à `COLS_EXCLUES` dans `notebooks/SYNTHESE_modele_R35_evaluation_complete.ipynb` (sections 4.2 et 5).

## Note méthodologique sur la révision

La révision de cet ADR illustre une pratique méthodologique attendue dans le projet : la révocation et la réécriture explicite d'un ADR lorsqu'une faiblesse méthodologique est identifiée *avant* la production de résultats définitifs. Cette pratique est cohérente avec le principe CRISP-ML(Q) (Studer et al., 2021) de documentation systématique des décisions, y compris quand elles évoluent. La v1 de l'ADR-039 reste mentionnée dans l'historique pour préserver la traçabilité du raisonnement, sans risque de confusion sur la décision actuelle.
