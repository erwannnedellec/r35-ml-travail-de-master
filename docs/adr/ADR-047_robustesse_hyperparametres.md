---
id: ADR-047
ancien_id: ADR-CF04
date_decision: 2026-06-05
statut: remplacé
remplace_par: [ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-047 — Robustesse hyperparamètres et sélection du candidat final (couche 1)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». L'alternative laissée ouverte ici (APC_Global tunée / Enrichi_Seg figée) est **tranchée par ADR-052** en faveur d'Enrichi_Seg.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (critère F2), ADR-036 (hyperparams référence)

---

## Contexte

Étape 3 : tester la robustesse du classement de l'étape 2 (APC_Global > Enrichi_Seg sur PR-AUC haut)
quand les hyperparamètres sont tunés par cellule.

---

## Protocole

**Grille** : max_depth ∈ {4,6,8} × min_child_weight ∈ {1,5,10} × (n_estimators, lr) ∈ {(300,0.1),(500,0.05),(800,0.05)} = **27 combinaisons**  
**Sélection** : max WF PR-AUC haut moyen (Fold1+Fold2, H22-H24)  
**Seuil** : F2 recalibré sur train pour chaque config (ADR-046)  
**Évaluation** : H25 lecture seule, IC bootstrap 95 %

---

## Meilleurs hyperparamètres par cellule (sélectionnés sur WF H22-H24)

| Cellule | max_depth | min_child_weight | n_estimators | learning_rate | WF PR-AUC (tunée) | WF PR-AUC (figée ADR-036) |
|---------|-----------|-----------------|--------------|---------------|-------------------|-----------------------------|
| APC_Global | **8** | **10** | **800** | **0.05** | 0.042 | 0.022 (estimé) |
| APC_Haut | **4** | **10** | **500** | **0.05** | 0.054 | 0.030 (estimé) |
| Enrichi_Seg | **4** | **10** | **300** | **0.1** | 0.111 | 0.103 (estimé) |

> Note : les WF PR-AUC sur H22-H24 sont très faibles (0.04–0.11) car les service_ids y sont tous connus.
> Le bénéfice réel du créneau ne se matérialise que sur H25 (trains renumérotés).
> La sélection WF est donc peu fiable pour prédire la performance H25 — finding clé pour la thèse.

---

## Évaluation H25 — Tunée vs Figée (seuil F2)

| Cellule | Version | Seuil F2 | PR-AUC haut | IC 95 % | Rappel@WF | Précision | R² global |
|---------|---------|----------|-------------|---------|-----------|-----------|-----------|
| **APC_Global** | Figée (ADR-036) | 32.22 | 0.301 | [0.244–0.356] | 62.6 % | 13.1 % | 0.503 |
| **APC_Global** | **Tunée** | 37.46 | **0.336** | [0.280–0.392] | **63.3 %** | **18.5 %** | 0.510 |
| APC_Haut | Figée (ADR-036) | 32.71 | 0.254 | [0.204–0.305] | 64.3 % | 12.6 % | 0.033 |
| APC_Haut | Tunée | 39.74 | 0.303 | [0.249–0.358] | 57.6 % | 21.0 % | 0.021 |
| **Enrichi_Seg** | **Figée (ADR-036)** | 45.01 | **0.191** | [0.160–0.234] | **65.3 %** | **15.0 %** | **0.584** |
| Enrichi_Seg | Tunée | 48.09 | 0.135 | [0.115–0.162] | 54.9 % | 16.8 % | 0.573 |

---

## Findings clés

### 1. Classement PR-AUC haut : STABLE et amplifié

| Classement | Figée | Tunée |
|------------|-------|-------|
| APC_Global | 0.301 | **0.336** |
| Enrichi_Seg | 0.191 | 0.135 |

APC_Global > Enrichi_Seg sur PR-AUC haut dans les deux versions. L'écart s'amplifie avec le tuning.

### 2. Le tuning aide APC_Global, nuit à Enrichi_Seg

- **APC_Global** : +0.035 PR-AUC (+11.6 % relatif), IC tunée [0.280–0.392] vs figée [0.244–0.356] — chevauchants → tendance favorable non significative
- **Enrichi_Seg** : −0.056 PR-AUC (−29 % relatif), IC figée [0.160–0.234] et tunée [0.115–0.162] **ne se chevauchent pas** → la figée est significativement meilleure que la tunée pour Enrichi_Seg

> *Note au gel : les deux intervalles se recouvrent en réalité sur [0,160 ; 0,162]. Le critère
> de recouvrement, correctement appliqué à l'observation précédente, ne permet donc pas de
> conclure à une différence significative ici. La décision de conserver la configuration figée
> tient au protocole (ADR-052), non à ce test.*

### 3. Enrichi_Seg figée reste meilleure pour la régression

R² global : Enrichi_Seg figée (0.584) >> APC_Global tunée (0.510)

### 4. WF PR-AUC non prédictif de H25 (finding thèse)

Sur H22-H24, tous les service_ids sont connus → le créneau n'apporte pas d'avantage mesurable
sur les folds WF. Sur H25, 50 % des service_ids sont renumérotés → le créneau démontre son apport (RF-1).
Le tuning WF optimise pour la mauvaise distribution → sélection moins fiable que sur données réelles.

---

## Décision

**Selon l'objectif :**

| Objectif | Candidat retenu | Hyperparams | PR-AUC H25 | R² global |
|----------|----------------|-------------|-----------|-----------|
| Détection surcharges (opérationnel) | **APC_Global tunée** | d=8, mcw=10, n=800, lr=0.05 | **0.336** | 0.510 |
| Régression générale (recherche) | **Enrichi_Seg figée** | d=6, mcw=1, n=300, lr=0.1 | 0.191 | **0.584** |

Le candidat final pour la sélection (étape 4) sera celui qu'Erwann retient selon la priorité
opérationnelle ou académique.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03_robustesse_hyperparams.ipynb` | Notebook (réexécutable Restart & Run All) |
| `consolidation_finale/outputs/etape_03_wf_tuning_results.csv` | 162 lignes WF × grid × fold |
| `consolidation_finale/outputs/etape_03_best_params.json` | Meilleurs hyperparamètres par cellule |
| `consolidation_finale/outputs/etape_03_tuned_vs_fixed.csv` | 6 lignes H25 tunée + figée |
| `consolidation_finale/figures/etape_03_tuned_vs_fixed.png` | Figure comparaison (300 DPI) |
| `consolidation_finale/figures/etape_03_hyperparams_sensitivity.png` | Sensibilité WF (300 DPI) |
