---
id: ADR-050
ancien_id: ADR-CF07
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-069]
modifie: [ADR-048]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-050 — Grille régression features × architecture et sample weighting

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-069.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-048.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». La pondération des surcharges instruite ici est **écartée** : ADR-069 conserve la perte quadratique non pondérée.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045→CF06

---

## Contexte

Recentrage couche 1 sur la **régression** : qualité de prédiction de la charge, indépendamment
du seuil (décision couche 2). Métriques : R², MAE, MAE≥60, MAE≥80, Biais≥80.
H25 lecture seule, hyperparams figés ADR-036.

---

## Phase 1 — Grille 8 modèles

### Résultats segment HAUT (touristique, 297 surcharges)

| Modèle | R² haut | IC 95% | MAE haut | MAE ≥80 | Biais ≥80 | PR-AUC |
|--------|---------|--------|----------|---------|-----------|--------|
| APC_Global | 0.283 | — | — | 61.9 | **-61.7** | 0.301 |
| APC_Haut | 0.306 | — | — | 60.5 | -59.5 | — |
| APC_Seg | 0.306 | — | — | 60.5 | -59.5 | — |
| Enrichi_Global | 0.457 | — | — | 53.2 | -53.2 | 0.132 |
| Enrichi_Haut | **0.480** | — | — | **50.4** | **-50.4** | — |
| **Enrichi_Seg** | **0.480** | — | — | **50.4** | **-50.4** | 0.193 |

### Résultats segment GLOBAL (recombinés pour les segmentés)

| Modèle | R² global | R² bas | R² haut |
|--------|-----------|--------|---------|
| APC_Global | 0.503 | 0.489 | 0.283 |
| APC_Seg | 0.510 | 0.494 | 0.306 |
| Enrichi_Global | 0.574 | 0.547 | 0.457 |
| **Enrichi_Seg** | **0.584** | **0.556** | **0.480** |

---

## Finding clé — Sous-prédiction systématique (biais ≥80)

**Tous les modèles sous-prédisent les charges élevées de -50 à -62 voyageurs.**

Pour une charge réelle de 90+ voyageurs (surcharge), le modèle prédit en moyenne ~35-45 voyageurs.
Ce n'est pas un problème de seuil — c'est la **régression vers la moyenne** : XGBoost optimise
l'erreur quadratique sur l'ensemble des observations, et les surcharges (rares, 0.4 %) sont
écrasées par la masse des observations normales.

Ce biais est documenté en Chapitre 4 comme limite de l'artefact : le profil de charge montré à
l'opérateur (SHAP + valeur prédite) sera systématiquement optimiste sur les cas qui comptent pour l'UM.

### Gagnants Phase 1

- **Régression générale** : Enrichi_Seg (R²=0.584 global, 0.480 haut)
- **Précision charges élevées** : Enrichi_Haut = Enrichi_Seg sur haut (MAE≥80=50.4, biais=-50.4)
- **Détection UM** (PR-AUC, de l'étape 3bis) : APC_Global (0.301)

**Candidat Phase 2** : Enrichi_Haut (arch spécialisée haut, 179 features)

---

## Phase 2 — Sample weighting sur Enrichi_Haut

Poids w pour les observations surcharge (charge_réelle ≥ 94) dans le TRAIN H22-H24 uniquement.

| w_ratio | R² haut | MAE ≥80 haut | Biais ≥80 haut | ΔBiais vs baseline |
|---------|---------|-------------|----------------|-------------------|
| 1 (baseline) | 0.480 | 50.4 | -50.4 | — |
| 5 | 0.460 | 46.1 | -45.7 | +4.7 (+9.3 %) |
| **10** | **0.462** | **44.1** | **-43.7** | **+6.7 (+13.3 %)** |
| **20** | 0.443 | **43.1** | **-42.6** | **+7.8 (+15.5 %)** |
| 50 | 0.412 | 44.7 | -43.4 | +7.0 (+13.9 %) |

### Interprétation

- **Le weighting réduit le biais de ~15-16 %** (de -50.4 à -42.6 avec w=20) mais ne l'élimine pas.
  Le biais structurel de régression MSE sur distribution asymétrique ne peut pas être corrigé
  entièrement par le weighting.
- **Optimal w=20** : MAE≥80 minimal (43.1), biais le plus proche de 0 (-42.6). R² haut passe
  de 0.480 → 0.443 (perte ~8 % acceptable).
- **w=50 dégrade** : MAE≥80 remonte légèrement (44.7) — régularisation excessive, le modèle
  commence à sur-optimiser les rares surcharges au détriment de la cohérence générale.
- **Le biais reste négatif même à w=50** (-43.4) : propriété fondamentale, pas corrigeable
  sans changer l'objectif (ex. quantile regression).

---

## Décision

### Modèle couche 1 recommandé

**Enrichi_Seg, hyperparams ADR-036, sans weighting** (R²=0.584 global, MAE≥80=50.4 haut).

Rationale :
- Meilleur R² global et bas (couverture complète du réseau)
- Même qualité haut que Enrichi_Haut
- Le sample weighting améliore modérément MAE≥80 (-15 %) mais le biais reste fort

**Si priorité maximale sur justesse charges élevées** → Enrichi_Haut w=20
(MAE≥80=43.1, biais=-42.6, R²haut=0.443).

### Le biais ≥80 est un facteur à documenter dans la thèse

La valeur prédite par le modèle pour une surcharge est systématiquement sous-estimée de ~42-50
voyageurs. Ceci renforce la nécessité de la couche de décision (couche 2) : le décideur ne voit
pas la valeur prédite comme une prédiction fiable de la charge absolue, mais comme un signal
relatif (la valeur prédite classe correctement les jours à risque même si elle sous-estime
l'amplitude). La SHAP explanation expose les drivers, pas l'amplitude prédite.

### Arbitrage APC vs Enrichi (couche 1 finale)

| Critère | APC-only | Enrichi_Seg |
|---------|----------|-------------|
| PR-AUC haut (détection UM) | **0.301** | 0.193 |
| R² global | 0.503 | **0.584** |
| R² haut | 0.283 | **0.480** |
| MAE ≥80 haut | 61.9 | **50.4** |
| Biais ≥80 haut | -61.7 | **-50.4** |
| N features | **38** | 179 |

Pour la **décision UM J-1** (détection = PR-AUC) : APC-only gagne.  
Pour la **qualité du profil de charge** (R², MAE) : Enrichi_Seg gagne.

Ce sont deux usages différents. Si la couche 1 sert à produire un profil de charge SHAP
lisible par l'opérateur → Enrichi_Seg. Si elle sert uniquement à détecter le risque de
surcharge → APC-only.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03quat_regression_weighting.ipynb` | Notebook réexécutable |
| `consolidation_finale/outputs/etape_03quat_phase1_results.csv` | Phase 1 — 8 modèles × segments |
| `consolidation_finale/outputs/etape_03quat_phase2_results.csv` | Phase 2 — weighting × ratios |
| `consolidation_finale/figures/etape_03quat_phase1_grille.png` | Grille régression (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase1_biais.png` | Biais ≥80 (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase2_weighting.png` | Courbes weighting (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase2_predit_vs_reel.png` | Prédit vs réel (300 DPI) |
