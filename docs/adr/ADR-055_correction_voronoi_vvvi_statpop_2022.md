---
id: ADR-055
ancien_id: ADR-CF12
date_decision: 2026-06-07
statut: remplacé
remplace_par: [ADR-063]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-055 — Correction du Voronoï STATPOP manquant pour VVVI (millésimes 2022 et 2023)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté — appliqué  
**Auteur** : Erwann Nedellec  

---

## Contexte

Un audit NaN systématique des features `spatial_` dans `ml_dataset.parquet` a révélé un trou de référentiel ciblé : la gare **VVVI (Vevey Vignerons)** présentait 100 % de NaN sur les 18 features HPI/ménages en H23 (31 452 lignes × 2 côtés = 62 904 occurrences) et 6 % en H24 (1 875 lignes × 2), sans NaN en H22 ni en H25.

**Cause identifiée** : VVVI a remplacé GIL (Gilamont) à partir de H23 (décembre 2022). Le pipeline `build_fact_statpop_gare.py` utilise le mapping `STATPOP_YEAR_TO_HORAIRE[2022] = "H22"`, ce qui produit un Voronoï H22 avec GIL comme station active — VVVI est donc absent du millésime 2022. Conséquences en cascade :

1. **1 702 lignes H23 (calendaire déc 2022)** → millésime 2022 → VVVI absent → toutes features `spatial_` NaN.
2. **29 750 lignes H23 (calendaire 2023)** → millésime 2023 → VVVI présent (population calculée) mais ménages/HPI NaN. En effet, STATPOP 2023 (OFS) ne contient pas les colonnes HP\*/HPI ; elles sont normalement interpolées entre 2022 et 2024, mais l'ancre 2022 est absente pour VVVI → l'interpolation échoue silencieusement.
3. **1 875 lignes H24 (calendaire 2023)** → millésime 2023 → même problème ménages/HPI.

**Vérification de symétrie préalable** : GIL présente 0 % de NaN sur tous ses millésimes actifs (H16–H22). Aucune autre gare n'est affectée. Le trou est strictement isolé à VVVI.

---

## Décision

Recalculer le Voronoï VVVI avec les données STATPOP **millésime 2022** et injecter la ligne résultante dans `statpop_clean.parquet`. L'interpolation existante de `impute_missing_millesimes()` prend ensuite en charge le millésime 2023 (ancre 2022 disponible → (1636+1679)/2 = 1658).

**Méthode de calcul** : topologie H23 (VVVI active, GIL absent) × données STATPOP2022.csv. Justification : les 1 702 lignes calendaire-2022 sont toutes des observations H23 (VVVI est la gare active pour ces dates) ; utiliser la topologie H23 donne à VVVI son territoire réel pour ces observations.

**Ce qui n'a pas été fait** : propager les valeurs du millésime 2024 vers H23/H24. Ce serait une violation du principe year-specific (ADR-025) créant une asymétrie où VVVI aurait une démographie d'une autre année que les autres gares la même période.

---

## Résultats de calcul

| Millésime | Population 500m | Ménages 500m | Hectares | HPI classe max | Source |
|-----------|----------------|--------------|----------|----------------|--------|
| 2022 (calculé) | 3 417 | 1 636 | 59 | 2 | STATPOP2022.csv × topologie H23 |
| 2023 (interpolé) | 3 496 | 1 658 | 59 | 2 | interpolation linéaire 2022/2024 |
| 2024 (existait) | 3 522 | 1 679 | 59 | 1 | calculé originellement |

La valeur interpolée 2023 (1658) est la moyenne arithmétique exacte de 2022 (1636) et 2024 (1679), cohérente avec la stratégie `interpolate` du pipeline.

---

## Non-régression

Vérification explicite avant sauvegarde dans `fix_vvvi_statpop_2022.py` : comparaison numérique (arrondi 8 décimales) de toutes les lignes non-VVVI entre l'ancien et le nouveau `statpop_clean.parquet` → **0 différence**. Seules les lignes VVVI ont changé.

Après régénération complète de la pipeline (stages 06 → 10 → ml_dataset) :

| Vérification | Avant | Après |
|---|---|---|
| NaN `spatial_gare_*_menages_500m_total` VVVI H23 | 31 452 (100 %) | **0 (0 %)** |
| NaN `spatial_gare_*_menages_500m_total` VVVI H24 | 1 875 (6 %) | **0 (0 %)** |
| NaN `spatial_` total dans ml_dataset | 62 904 + 3 750 = 66 654 | **0** |
| Shape ml_dataset | (1 141 984, 204) | (1 141 984, 204) inchangé |
| Autres gares, autres features | — | inchangés (non-régression OK) |

**Nouveau hash ml_dataset** : SHA256 partiel `d3000f48074a496b`  
(ancien hash audit NaN : `cd29a5f2` — remplacé)

---

## Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `data/processed/sources/statpop_clean.parquet` | +1 ligne (VVVI-2022) + interpolation VVVI-2023 mise à jour |
| `data/processed/sources/statpop_clean.csv` | synchronisé |
| `data/processed/stage_06_statpop.parquet` | régénéré |
| `data/processed/stage_07_istdaten.parquet` | régénéré |
| `data/processed/stage_08_features.parquet` | régénéré |
| `data/processed/stage_09_simba.parquet` | régénéré |
| `data/processed/stage_10_reservations.parquet` | régénéré |
| `data/processed/ml_dataset.parquet` | régénéré |
| `scripts/sources/fix_vvvi_statpop_2022.py` | script correctif (idempotent) |

---

## Impact modèle

Le modèle figé (`etape_04bis_v2_nettoyage_171f.ipynb`) entraîné sur H22–H24 recevait des NaN pour 18 features spatial_ sur toutes les observations VVVI en H23 (18,8 % des observations H23). XGBoost routait ces lignes via sa branche "missing" pour ces 18 features, sans signal socio-démographique sur VVVI. Le correctif fournit les valeurs correctes ; le modèle **devra être ré-entraîné** pour bénéficier de ce signal.
