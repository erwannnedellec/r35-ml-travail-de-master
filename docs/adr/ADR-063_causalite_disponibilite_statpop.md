---
id: ADR-063
ancien_id: ADR-CF19
date_decision: 2026-06-16
statut: actif
modifie: [ADR-006, ADR-011, ADR-025, ADR-039, ADR-055]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-063 — Causalité de disponibilité STATPOP : mapping Z-2 conservateur, forward-fill causal, correction géographique VVVI

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-006, ADR-011, ADR-025, ADR-039, ADR-055.
> **Précision au gel.** Ce document porte **deux auto-corrections datées** (18.06 et 19.06.2026) qui invalident une partie de ses propres mesures. Les lire avant les tableaux qu'elles corrigent.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (2026-06-16) — corrigé 2026-06-18 (Z-2 pipeline) — **corrigé 2026-06-19** (forward-fill pipeline, voir §Correction 2026-06-19) |
| **Date** | 2026-06-16 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-006 (stratégie millésime), ADR-011 (imputation 2021/2023 — révisé), ADR-024 (géométrie Voronoï), ADR-039 (mapping calendaire — révisé) |
| **Version modèle** | Enrichi_Seg v1.3 (hash 961a0bd5) — v1.2 (fe9d6b4d) archivée dans archive_v1.2/ |

## Contexte

La Philosophie A (mapping STATPOP initial, implémentée dans ADR-039 v2) présentait deux problèmes de causalité temporelle :

### Problème 1 — Fuite de disponibilité (mapping contemporain)

Le millésime STATPOP Y est produit par l'OFS sur l'état de la population au 31 décembre de l'année Y. Il est publié généralement vers août de l'année Y+1, mais **cette date n'est pas garantie** et peut glisser au-delà. La Philosophie A attribuait aux observations de l'année civile Z le millésime Z (mapping Z→Z) pour les années exactes, et Z→Z-1 carry-forward pour 2025.

Conséquence : une observation du 15 mars 2023 recevait le millésime STATPOP 2023 — publié au plus tôt fin 2024. Cette donnée n'était pas disponible à la date de la décision opérationnelle modélisée. Il s'agit d'une fuite temporelle de disponibilité, distincte d'une fuite de cible mais méthodologiquement inacceptable dans un mémoire MSc défendant la rigueur causale.

### Problème 2 — Interpolation avec borne future (millesimes 2021 et 2023)

L'ADR-011 avait adopté une interpolation linéaire pour les millésimes manquants :
- 2021 = moyenne(2020, 2022) — utilise STATPOP 2022, publié courant 2023
- 2023 = moyenne(2022, 2024) — utilise STATPOP 2024, publié courant 2025

L'interpolation mobilise une borne future non disponible à la date de l'observation, renforçant la fuite de disponibilité.

### Problème 3 — NaN VVVI (gare du segment BAS)

La gare VVVI n'était pas présente dans les topologies H19-H22 et était donc absente des zones Voronoï correspondantes dans `statpop_clean`. Conséquence : 33 327 observations VVVI (segment BAS, H23+H24+H25) recevaient des valeurs NaN pour toutes les features `spatial_gare_*_pop_500m_*`. Ces NaN n'encodaient pas une absence démographique réelle — VVVI est en zone urbaine dense de Vevey — mais un artefact d'attribution géographique.

## Décision

### 1. Mapping Z-2 conservateur (borne Jan 1 Y+2)

Le millésime Y est considéré sûrement disponible **à partir du 1er janvier Y+2**, ce qui garantit une marge suffisante même en cas de retard de publication. Une observation de l'année civile Z utilise donc le millésime Z-2 :

```python
MAPPING_BC_MILLESIME = {
    2021: 2019,
    2022: 2020,
    2023: 2021,
    2024: 2022,
    2025: 2023,
}
```

Ce décalage est **uniforme** par année civile (clé = `base_date.dt.year`, pas de bascule intra-année). Il n'y a pas de bascule août/septembre parce que la date de publication n'est pas garantie.

### 2. Forward-fill causal pour les millesimes sans HP*/HPI

Les données HP (effectifs de ménages privés) et HPI (indicateur de plausibilité des ménages
privés), au sens de la nomenclature STATPOP, ne sont disponibles dans la source OFS que pour certains millésimes. Forward-fill appliqué :
- 2021 ← 2020 (HP*/HPI de 2020 utilisés pour le millésime 2021)
- 2023 ← 2022 (HP*/HPI de 2022 utilisés pour le millésime 2023)

Cela remplace l'interpolation de l'ADR-011 (2021 = moyenne(2020,2022), 2023 = moyenne(2022,2024)) qui utilisait une borne future. Le forward-fill ne mobilise que des données disponibles avant la date de l'observation.

### 3. Correction géographique VVVI

La zone Voronoï de VVVI est reconstruite rétrospectivement en utilisant la topologie H23 (où VVVI est active) comme proxy géographique stable. Les hectares STATPOP (RELIs) des millésimes 2019, 2020 et 2021 sont agrégés pour cette zone. Les valeurs HP*/HPI de 2021 sont forward-fillées depuis 2020 (cohérent avec la décision 2 ci-dessus).

Légitimité causale : les données de population par hectare sont des constats géographiques passés — leur utilisation pour reconstruire la zone VVVI aux millésimes antérieurs ne crée pas de fuite temporelle.

## Coût de performance

| Métrique | v1.2 (Philo A, fe9d6b4d) | v1.3 (Philo C_fix, 961a0bd5) | Δ |
|---|---|---|---|
| R² BAS (H25) | 0.589749 | 0.593410 | **+0.0037** (élimination NaN VVVI) |
| R² HAUT (H25) | 0.462726 | 0.447184 | **−0.0155** (coût causalité STATPOP) |
| R² GLOBAL (H25) | 0.608121 | 0.608443 | **+0.0003** (neutre) |
| PR-AUC HAUT | 0.3554 | 0.3410 | −0.0144 |

### Décomposition du coût HAUT

Le ΔR²HAUT = −0.0155 se décompose en deux effets indépendants :
- **Décalage millésime Z-2** (mapping B vs A) : ΔR²H = −0.0142 (92 % du coût)
- **Forward-fill vs interpolation** : ΔR²H = −0.0013 (8 % du coût)

La correction VVVI (NaN→valeur réelle) affecte exclusivement le segment BAS (VVVI est une gare BAS). Le R²HAUT est rigoureusement indépendant de cette correction — les modèles BAS et HAUT sont entraînés sur des données disjointes (`spatial_segment`).

## Arbitrage assumé explicitement

**Ce n'est pas une correction d'erreur — c'est un arbitrage de rigueur méthodologique.**

La Philosophie A n'était pas « fausse » au sens statistique — elle produisait les meilleures métriques sur H25 parce qu'elle utilisait des millésimes plus récents, mieux alignés avec les patterns démographiques H25. En adoptant Z-2, on renonce délibérément à une partie de ce signal (ΔR²H = −0.0155) pour garantir qu'aucune donnée non disponible à la date opérationnelle ne soit mobilisée.

Ce trade-off est cohérent avec la position de la thèse : un modèle destiné à un usage opérationnel J-1 doit être entraîné avec des contraintes de disponibilité réalistes, quand bien même cela dégrade marginalement les métriques sur données rétrospectives.

La dégradation HAUT est modérée (−3.3 % de R² relatif) et intégralement attribuable à l'adoption d'un mapping plus conservateur, pas à une dégradation de la qualité du modèle. Le R²GLOBAL reste quasi stable (+0.0003).

## Note de traçabilité — Artefact d'évaluation en mémoire

Lors de l'évaluation in-memory du script `statpop_philo_c_vvvi_fix.py`, un faux ΔR²HAUT de −0.0411 avait été rapporté (0.4472 → 0.4061). Ce chiffre était incorrect.

Cause racine : `pd.concat` entre `statpop_ff` (dtypes Int64) et les nouvelles lignes VVVI (avec NA dans les colonnes HP absent de STATPOP2021) a déclenché un FutureWarning de corruption dtype. L'évaluation in-memory utilisait un objet corrompu. Le round-trip via `to_parquet()` / `read_parquet()` restaure les dtypes corrects.

Preuve de l'artefact : le modèle HAUT est entraîné sur `spatial_segment == "haut"`. Les observations VVVI sont toutes dans `spatial_segment == "bas"`. L'ensemble d'entraînement du modèle HAUT est **identique** entre C et C_fix (0 différence ligne à ligne). Avec seed=42 déterministe, ΔR²HAUT = 0.000000 exactement entre C et C_fix. Le ΔR²H = −0.0155 constaté entre v1.2 et v1.3 provient entièrement du changement de mapping STATPOP (Philosophie A → C), pas de la correction VVVI.

## Cohérence avec STATENT

Cette décision établit la règle de causalité applicable à toute source OFS structurelle avec latence de publication comparable. STATENT (statistique des entreprises), dont l'intégration est prévue au cycle suivant, devra appliquer la même borne Z-2 conservatrice (publication STATENT généralement 18-24 mois après l'année de référence).

## Correction 2026-06-18 — Bug pipeline : Z-2 n'avait jamais été réellement appliqué

### Bug identifié

L'audit du 2026-06-18 a révélé que le script `scripts/pipeline/build_stage06_statpop.py` avait bien été mis à jour avec le mapping Z-2 (ADR-063), **mais que `stage_06.parquet` n'avait jamais été reconstruit**. Les datasets v1.3 (961a0bd5), v1.4 (c1ecfc19) et tous les datasets expérimentaux intermédiaires contenaient donc STATPOP Z-0 dans les données, malgré les labels "ADR-063 causal Z-2".

Vérification directe sur chaque dataset :
```
v1.3 (961a0bd5) : id_statpop_reference_year H22 → [2021, 2021, 2021] ← Z-0
v1.4 (c1ecfc19) : id_statpop_reference_year H22 → [2021, 2021, 2021] ← Z-0
5fdca746        : id_statpop_reference_year H22 → [2019, 2019, 2019] ← Z-2 ✓
```

### Correction

Le pipeline a été reconstruit le 2026-06-18 à partir de `stage_06` (STATPOP Z-2 réel) via `make stage_07 → stage_08 → stage_09 → ml_dataset`. Dataset canonique résultant : `5fdca746` (209 colonnes, 1 141 984 lignes H22–H25).

### Vrai effet de Z-2 (mesuré sur données correctes)

La comparaison `c1ecfc19` (Z-0 effectif) vs `5fdca746` (Z-2 effectif) sur les mêmes features et le même split A :

| Segment | Z-0 (c1ecfc19, INVALIDE) | Z-2 (5fdca746, CORRECT) | Δ |
|---|---|---|---|
| R² BAS | 0.592 | 0.566 | −0.027 |
| **R² HAUT** | 0.438 | **0.483** | **+0.045** |
| R² GLOBAL | 0.606 | 0.593 | −0.013 |
| PR-AUC HAUT | 0.340 | 0.430 | **+0.090** |

**La correction Z-2 AMÉLIORE le HAUT** (+4.5 pts R², +9 pts PR-AUC). Elle dégrade légèrement BAS et GLOBAL, mais le segment critique (HAUT, saisonnier-touristique) en bénéficie significativement. Ceci est cohérent : les gares CHTV/HTV (Château-d'Hauteville / Hauteville) ont une population résidente plus représentative en 2019 (Z-2 pour H22) qu'en 2021 (Z-0 pour H22), car 2019 précède les mouvements migratoires COVID.

### Invalidation des métriques antérieures

Le "coût de causalité −0.0155 HAUT (v1.2→v1.3)" comparait **deux datasets Z-0** (fe9d6b4d et 961a0bd5). Ce chiffre n'est pas attribuable au passage Z-0→Z-2 ; il reflète un effet secondaire non identifié (probablement la correction NaN VVVI qui influe sur le BAS mais pas le HAUT — à ré-investiguer si nécessaire). Ce chiffre **ne doit pas être cité dans la thèse** comme "coût causalité STATPOP".

Le vrai coût/bénéfice de la rigueur causale Z-2 est documenté dans le tableau ci-dessus : la rigueur ne coûte pas de performance, elle **améliore le HAUT** (le segment le plus important pour la détection des surcharges).

### Fichiers impactés (correction)

- `data/processed/ml_dataset.parquet` — hash `5fdca746` (pipeline rebuild 2026-06-18, premier vrai Z-2)
- Métriques finales : voir Enrichi_Seg v1.6 (158f, Split C, `5fdca746`)
- `models/enrichi_seg/enrichi_seg_metadata.json` — version 1.6
- Archives invalides : c1ecfc19 (v1.4), 961a0bd5 (v1.3), fe9d6b4d (v1.2) — toutes Z-0 effectif

## Correction 2026-06-19 — Bug pipeline : forward-fill n'était pas réellement appliqué

### Bug identifié

Audit du 2026-06-19 : `paths.py` pointait vers `statpop_clean.parquet` (DEFAULT_STRATEGY="interpolate") au lieu de `statpop_clean_causal.parquet` (carry_forward). Le dataset `5fdca746` avait le bon mapping Z-2 mais **les valeurs HP*/HPI utilisaient encore l'interpolation** (ex. VV menages 2021 = 4694 = mean(4660,4728) au lieu de 4660 = forward-fill←2020).

Troisième occurrence du même patron de bug (ADR décidé, pipeline non conforme) → assertion dure ajoutée.

### Correction

- `scripts/pipeline/paths.py` ligne 82 : `STATPOP_CLEAN = SOURCES / "statpop_clean_causal.parquet"` ✓
- `Makefile` ligne 37 : cible et commande `--strategy carry_forward` ✓
- `STATPOP_MAPPING` : labels `interpole` → `forward_fill` pour millesimes 2021 et 2023 ✓
- **Assertion dure** dans `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` : `RuntimeError` si "interpole" détecté dans le résumé de labels ✓

### Vrai effet Z-2-interpolé → Z-2-forward_fill (d39d0bd8, Split C, 158f, modèles réentraînés)

| Segment | 5fdca746 (Z-2-interp) | d39d0bd8 (Z-2-ff) | Δ |
|---|---|---|---|
| R² BAS | 0.5655 | 0.5666 | +0.001 |
| **R² HAUT** | 0.4982 | **0.4896** | **−0.009** (dans le bruit std=0.018) |
| R² GLOBAL | 0.5955 | 0.5949 | −0.001 |
| PR-AUC HAUT | 0.4322 | 0.4079 | −0.024 |

**Interprétation** : l'impact est non significatif (ΔR²HAUT dans 0.5×std multi-seed). L'interpolation avait une légère fuite causale (vue la borne future 2022 pour estimer 2021), mais son impact mesurable sur le modèle est nul. Le forward-fill est retenu pour la rigueur méthodologique.

Observations affectées : **630 413 / 1 141 984 (55.2%)** — H23 (millesime 2021, 337 329 obs) + H25 (millesime 2023, 293 084 obs).

### Décomposition complète de la causalité STATPOP (tableau synthèse)

| Étape | Hash | Source | R²HAUT | ΔR²HAUT |
|---|---|---|---|---|
| Z-0 effectif (invalide) | c1ecfc19 | interp (Z-0 caché) | 0.438 | — |
| Z-2 interpolé | 5fdca746 | interp (Z-2) | 0.4982 | **+0.060** vs Z-0 |
| Z-2 forward-fill (**retenu** — STATPOP du canonique) | d39d0bd8 | ff (Z-2) | 0.4896 | −0.009 vs interp |

Bénéfice total Z-0→Z-2-ff : **+0.052 R²HAUT** (+5.2 pts).

### Fichiers impactés (correction 2026-06-19)

- `data/processed/ml_dataset.parquet` — hash canonique `51e459ff` (v1.8 ; forward-fill causal CF19 + histo_* cutoff mensuel/tronçon CF18). `d39d0bd8` (forward-fill causal seul, 2026-06-19) supersédé — voir ADR-062 amendement.
- `models/enrichi_seg/enrichi_seg_bas.json` — modèle BAS v1.7 (hash 07c32993)
- `models/enrichi_seg/enrichi_seg_haut.json` — modèle HAUT v1.7 (hash 9c6b25ba)
- `models/enrichi_seg/enrichi_seg_metadata.json` — version 1.7
- `scripts/pipeline/paths.py` — STATPOP_CLEAN corrigé
- `Makefile` — cible STATPOP_CLEAN corrigée
- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` — assertion dure + labels forward_fill

## Fichiers impactés (original)

- `data/processed/ml_dataset_v1.3.parquet` — dataset de référence v1.3 (hash 961a0bd5)
- `data/processed/sources/statpop_clean_causal.parquet` — statpop avec forward-fill + VVVI fix (hash fe6b0b1c)
- `models/enrichi_seg/archive_v1.2/` — archive modèles v1.2 (fe9d6b4d)
- `scripts/exp/statpop_philo_c_vvvi_fix.py` — script de construction du dataset v1.3 (exp → référence)
- `docs/adr/ADR-039_carry_forward_statpop_h25.md` — révisé (mapping et imputation corrigés)
