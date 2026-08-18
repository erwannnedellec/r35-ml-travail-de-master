---
id: ADR-054
ancien_id: ADR-CF11
date_decision: 2026-06-06
statut: amendé
amende_par: [ADR-061]
modifie: [ADR-053]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-054 — Nettoyage de parcimonie : 179 → 171 → 172 → 170 features

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-061.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-053.
> **Précision au gel.** Le décompte final de cette chaîne de parcimonie (170) est ramené à **158** par ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06 — mis à jour 2026-06-07  
**Statut** : **DÉCISION FIGÉE** — validée par Erwann Nédellec  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-052 (modèle couche 1), ADR-053 (SHAP explicabilité), ADR-048 (feature selection), ADR-057 (dénivelé tronçon)

## Chaîne de nettoyage

| Étape | N features | Opération |
|-------|-----------|-----------|
| Point de départ | 179 | Modèle exploratoire (ADR-048) |
| ADR-054 §1 | **171** | −8 HPI structurellement nulles (SHAP = 0.000 exact dans BAS ET HAUT) |
| ADR-057 | **172** | +1 `spatial_denivele_troncon_m` (dénivelé signé par tronçon) |
| ADR-054 §2 | **170** | −2 HPI nulles découvertes sur 172f ; dénivelé conservé (retrait dégrade HAUT −0.022) |

**Périmètre final : 170 features** (fichier `etape_04bis_v2_features_170f.json`).

---

## §1 — Premier nettoyage : 179 → 171 (2026-06-06)

**Retrait de 8 features de topologie HPI à SHAP = 0.000 exact dans les deux modèles (BAS et HAUT).**

| Feature retirée | Source | SHAP BAS | SHAP HAUT | Justification |
|-----------------|--------|----------|----------|---------------|
| `spatial_segment` | Topologie | 0.0000 | 0.0000 | Constante dans chaque modèle segmenté — artefact architectural |
| `spatial_gare_arrivee_flag_qualite_faible` | Topologie | 0.0000 | 0.0000 | Flag HPI qualité — jamais utilisé en split |
| `spatial_gare_arrivee_hpi_classe_max` | Topologie | 0.0000 | 0.0000 | Classe HPI max gare arrivée — jamais utilisé en split |
| `spatial_gare_arrivee_hpi_ha_manquante` | Topologie | 0.0000 | 0.0000 | HPI ha manquante gare arrivée — jamais utilisé en split |
| `spatial_gare_depart_flag_qualite_faible` | Topologie | 0.0000 | 0.0000 | Flag HPI qualité gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_classe_max` | Topologie | 0.0000 | 0.0000 | Classe HPI max gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_ha_autre` | Topologie | 0.0000 | 0.0000 | HPI ha autre gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_ha_manquante` | Topologie | 0.0000 | 0.0000 | HPI ha manquante gare départ — jamais utilisé en split |

**Feature conservée malgré SHAP = 0 :**

| Feature | SHAP BAS | SHAP HAUT | Justification conservation |
|---------|----------|----------|---------------------------|
| `resa_has_resa_J_minus_1` | 0.0000 | 0.0000 | Signal réservations réservé à la couche 2. Silence sur H25 attribuable au cas-pire (refonte horaire = perturbation des réservations habituelles). Redondance probable avec `resa_pax_2c_J_minus_1` (rang 3 HAUT). Coût de conservation = 0 ; risque de retrait pour la couche 2 = non nul. |

---

## Iso-performance H25 — résultats de validation

| Segment | R² 179f | IC 95% | R² 171f | IC 95% | ΔR² | IC chevauchants | Verdict |
|---------|---------|--------|---------|--------|-----|----------------|---------|
| BAS | 0.5557 | [0.5517 ; 0.5590] | 0.5519 | [0.5482 ; 0.5552] | −0.0038 | **Oui** | ✅ OK |
| HAUT | 0.4803 | [0.4693 ; 0.4908] | 0.4671 | [0.4553 ; 0.4797] | −0.0133 | **Oui** | ✅ OK |
| GLOBAL | 0.5841 | [0.5812 ; 0.5876] | 0.5792 | [0.5760 ; 0.5825] | −0.0050 | **Oui** | ✅ OK |

**Critère d'acceptation** : ΔR² < 0.02 sur chaque segment ET IC chevauchants.  
**Résultat** : critère respecté sur les trois segments. Retrait validé.

### Note sur le ΔR² HAUT = −0.013

Les 8 features retirées ont SHAP = 0.000 exact dans les deux modèles, pourtant ΔR² HAUT = −0.013 (non nul). Ceci renforce le finding méthodologique central : même des features à SHAP marginal strictement nul peuvent contribuer marginalement via des mécanismes non capturés par la valeur SHAP moyenne — vraisemblablement des effets d'interaction très locaux sur les observations rares. Le ΔR² reste dans le bruit (IC chevauchants, ΔR² < 0.02) et le retrait est validé, mais l'observation est documentée pour la thèse.

MAE comparées :

| Segment | MAE 179f | MAE 171f | Δ | MAE≥80 179f | MAE≥80 171f | Biais≥80 171f [IC] |
|---------|---------|---------|---|------------|------------|-------------------|
| BAS | 8.614 | 8.637 | +0.023 | 40.1 | 41.0 | −40.9 [−41.7 ; −40.2] |
| HAUT | 6.191 | 6.319 | +0.128 | 50.4 | 49.2 | −49.0 [−51.2 ; −47.0] |
| GLOBAL | 7.991 | 8.041 | +0.050 | 41.7 | 42.3 | −42.2 [−43.0 ; −41.5] |

---

## Finding méthodologique — à documenter dans la thèse

### Le SHAP marginal moyen sous-estime les contributions par interaction sur cible rare

**Contexte** : lors de l'étape 4bis (tentative de retrait de 22 features dont 10 à SHAP marginal faible mais non nul), la dégradation suivante a été observée :

| Métrique | 179f | 157f | Δ |
|---------|------|------|---|
| R² HAUT | 0.4803 | 0.4540 | **−0.026** ⚠️ |
| R² BAS | 0.5557 | 0.5537 | −0.002 ✅ |
| R² GLOBAL | 0.5841 | 0.5785 | −0.006 ✅ |

Les 22 features retirées représentaient **0.1 % de l'importance SHAP totale** sur HAUT (somme des mean|SHAP| = 0.0185). Pourtant ΔR² HAUT = −0.026 — soit une dégradation de 5.5 %.

**Interprétation** : le mean|SHAP| est une métrique de contribution *marginale, moyennée sur toutes les observations*. Sur une cible à événements rares (surcharges touristiques, 0.4 % des obs HAUT), les contributions SHAP s'annulent entre observations (positives pour les jours de surcharge, négatives ou nulles pour les jours ordinaires). La moyenne est quasi-nulle alors que la contribution *conditionnelle* sur les jours critiques peut être significative.

Les features STATPOP de gare (indices de mobilité résidentielle, parts de population par tranche d'âge) encodent des caractéristiques des stations alpines et lacustres — elles aident XGBoost à distinguer les tronçons à demande touristique élevée sans que cela transparaisse dans la moyenne SHAP globale.

**Règle opérationnelle dérivée** : sur un problème à cible rare avec des features potentiellement importantes sur les cas rares, le seuil de retrait basé sur mean|SHAP| doit être strictement nul (0.000 exact), pas simplement « faible » (< 0.01 voyageur). Le retrait de features à SHAP marginal moyen faible mais non nul est risqué. Seules les features à SHAP = 0.000 exact dans les deux modèles peuvent être retirées sans risque de dégradation.

Ce finding est un résultat de thèse : il illustre les limites de l'importance SHAP comme critère de sélection de features, en particulier dans les contextes de déséquilibre sévère de classes.

---

## §2 — Deuxième nettoyage : 172 → 170 (2026-06-07)

Après ajout du dénivelé tronçon (ADR-057, 171→172), une nouvelle passe de parcimonie a été conduite sur le modèle 172f (critère : gain XGBoost = 0 dans BAS ET HAUT).

**3 features à gain = 0 dans les deux modèles :**

| Feature | Gain BAS | Gain HAUT | Action |
|---------|----------|----------|--------|
| `resa_has_resa_J_minus_1` | 0.000 | 0.000 | **PROTÉGÉE** — signal couche 2 |
| `spatial_gare_arrivee_hpi_ha_classe_2` | 0.000 | 0.000 | Retirée |
| `spatial_gare_arrivee_hpi_ha_autre` | 0.000 | 0.000 | Retirée |

**Validation empirique du retrait des 2 HPI :**

| Segment | ΔR² | IC chevauchants | Verdict |
|---------|-----|----------------|---------|
| BAS | < 0.002 | Oui | ✅ OK |
| HAUT | < 0.002 | Oui | ✅ OK |
| GLOBAL | < 0.002 | Oui | ✅ OK |

**Dénivelé conservé** malgré rang HAUT modeste (102/170, SHAP=0.033) : test empirique de retrait montre ΔR² HAUT = −0.022 (retrait dégrade). Sur BAS, rang 17/170, SHAP=0.458 — feature active et significative. Corrélation Spearman dénivelé vs gare_ordre faible (ρ=−0.107 / +0.090) → information orthogonale.

---

## Périmètre final de la couche 1

| Paramètre | Valeur |
|-----------|--------|
| Architecture | Enrichi_Seg — deux XGBoost MSE (BAS + HAUT) |
| Features | **170** (179 − 8 HPI §1 + 1 dénivelé − 2 HPI §2) |
| `resa_has_resa_J_minus_1` | Conservée (couche 2 — SHAP=0 sur H25 attribuable au cas-pire) |
| `spatial_denivele_troncon_m` | Conservée (test empirique : retrait dégrade HAUT −0.022) |
| Hyperparamètres | ADR-036 |
| Clé `histo_*` | ADR-044 |
| Objectif | `reg:squarederror` |

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_04bis_v2_nettoyage_172f.ipynb` | Notebook réexécutable (172→170) |
| `consolidation_finale/outputs/etape_04bis_v2_features_170f.json` | Liste des **170 features** finales |
| `consolidation_finale/outputs/etape_04bis_v2_q1_test_denivele.csv` | Test empirique retrait dénivelé |
| `consolidation_finale/outputs/etape_04bis_v2_q3_parcimonie` | (intégré dans le notebook) |
| `consolidation_finale/outputs/etape_04bis_shap_importance_bas_171.csv` | SHAP BAS 171f (référence §1 — intermédiaire) |
| `consolidation_finale/outputs/etape_04bis_shap_importance_haut_171.csv` | SHAP HAUT 171f (référence §1 — intermédiaire) |
| `consolidation_finale/outputs/etape_04bis_v2_shap_importance_bas_170f.csv` | SHAP BAS **170f final** |
| `consolidation_finale/outputs/etape_04bis_v2_shap_importance_haut_170f.csv` | SHAP HAUT **170f final** |
| `consolidation_finale/figures/etape_04bis_v2_shap_beeswarm_bas_170f.png` | Beeswarm BAS 170f (300 DPI) |
| `consolidation_finale/figures/etape_04bis_v2_shap_beeswarm_haut_170f.png` | Beeswarm HAUT 170f (300 DPI) |
| `consolidation_finale/figures/etape_04bis_v2_shap_top15_170f.png` | Top 15 côte à côte 170f (300 DPI) |
