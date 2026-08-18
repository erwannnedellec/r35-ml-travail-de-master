---
id: ADR-045
ancien_id: ADR-CF02
date_decision: 2026-06-05
statut: révoqué
revoque_par: [ADR-046, ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-045 — Grille factorielle 2×3 sur H25 : résultats étape 2

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-046, ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Les seuils Walk-Forward publiés ici sont **invalidés** par ADR-046, et l'appareil de seuil de couche 1 qu'ils servent est **sans objet** depuis ADR-052 : le modèle final est un régresseur pur, aucun seuil Walk-Forward n'est produit.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Résultats — en attente de sélection du modèle (étape 3 robustesse hyperparamètres)  <!-- statut d'époque ; état au gel : révoqué (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-044 (clé créneau), ADR-038 (périmètre H22-H24/H25)

---

## Contexte

Pipeline modifié (ADR-044) : `add_features_to_raw_stacked.py` régénère les histo_* avec `GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]`. Dataset régénéré à cette étape — hash intermédiaire `1a53590f` (vs `cd29a5f2` ADR-037) ; hash canonique final après ADR-057/CF15 : **`11b58391`**.

---

## PARTIE A — Vérifications pipeline

| Contrôle | Résultat | Statut |
|----------|----------|--------|
| NaN structurels créneau | 6 549 / 2 360 762 = 0.3 % | ✅ Services nuit attendus |
| Couverture H25 creneau_anchor_30 | **100.0 %** | ✅ |
| Première obs/groupe avec lag NaN | 333/333 | ✅ |
| win7_max ≥ win7_mean | 0 violations | ✅ |
| base_sens : 2 sens distincts | VV→PLEI / PLEI→VV | ✅ |

### Taux NaN histo_2c_lag2 — avant/après

| Année | Segment | ADR-037 | Créneau CF01c |
|-------|---------|--------|--------------|
| H22 | bas/haut | 2.4 % | 0.2 % / 0.1 % |
| H23 | bas/haut | 1.1 % | 0.0 % |
| H24 | bas/haut | 1.1 % | 0.0 % |
| **H25** | **bas/haut** | **1.3 %** | **0.0 %** |

---

## PARTIE B — Grille factorielle

### Définition des feature sets

**APC-only** (38 features) :
- Calendaire : `cal_*` (15) + `event_is_vacances/ferie/ou_ferie_vaud` (3)
- Topologie : `spatial_gare_depart/arrivee_ordre`, `spatial_segment`, `base_duree_troncon_minutes` (4)
- Histo : 16 features `histo_*` (créneau ADR-044)

**Enrichi** (179 features) : APC-only + météo (27) + STATPOP (44) + événements (8) + ISTDATEN (14+) + VMCV (6) + SIMBA (12) + réservations ResSys (8)

### Seuils walk-forward calibrés (train H22-H24 uniquement)

| Feature set | Seuil WF gelé | Fold1 | Fold2 |
|-------------|--------------|-------|-------|
| Enrichi | **72.83** | 74.95 | 70.71 |
| APC-only | **76.46** | 79.85 | 73.08 |

### Résultats des 6 cellules sur H25

| Cellule | R²glob | PR-AUC haut | IC 95% | Rappel@WF haut |
|---------|--------|-------------|--------|----------------|
| **APC_Global** | 0.504 | **0.301** | [0.248–0.357] | **13.8 %** |
| APC_Haut | 0.302 | 0.253 | [0.202–0.304] | 13.8 % |
| APC_Seg (recomb.) | 0.512 | 0.253 | [0.202–0.304] | 13.8 % |
| Enrichi_Global | **0.575** | 0.132 | [0.107–0.165] | 7.1 % |
| Enrichi_Haut | 0.477 | 0.193 | [0.160–0.235] | 12.1 % |
| Enrichi_Seg (recomb.) | **0.585** | 0.193 | [0.160–0.235] | 12.1 % |

---

## Vérification RF-1 — trains renumérotés H25 (RÉSULTAT CLEF)

**Périmètre haut H25 :** 79 505 observations, 297 surcharges (prévalence 0.37 %)  
**Renumérotés :** 49.6 % (nouveaux numéros de train, absents de H22-H24)  
**Connus :** 50.4 % (mêmes numéros que H22-H24)

| Modèle | Connus | Renumérotés | Verdict RF-1 |
|--------|--------|-------------|-------------|
| ADR-037 (audit, référence) | 0.204 / 15.9 % | **0.055 / 0.0 %** | — |
| Enrichi_Global | 0.271 / 13.4 % | 0.072 / **0.0 %** | RF-1 partiel (ΔPR-AUC +0.017, rappel encore 0) |
| Enrichi_Haut | 0.416 / 22.9 % | 0.116 / **0.0 %** | RF-1 partiel (ΔPR-AUC +0.061, rappel encore 0) |
| **APC_Global** | **0.398 / 12.7 %** | **0.230 / 15.0 %** | **RF-1 DÉMONTRÉ** |
| **APC_Haut** | **0.309 / 15.3 %** | **0.213 / 12.1 %** | **RF-1 DÉMONTRÉ** |

**RF-1 est démontré sur les modèles APC-only.** Le créneau × sens récupère du signal sur les trains renumérotés : PR-AUC 0.055→0.230 (×4.2) et Rappel 0%→15%.

**Sur les modèles Enrichi :** amélioration PR-AUC (+0.017 à +0.061) mais rappel encore 0%. Les features externes semblent diluer le signal histo_* créneau sur ce sous-ensemble.

---

## Observations clés

### 1. APC_Global > Enrichi_Global sur PR-AUC haut (0.301 vs 0.132)

Sur le segment haut (touristique, surcharges rares), les features externes (météo, STATPOP, SIMBA…) dégradent la détection de surcharges par rapport au modèle APC-only. Hypothèse : le signal histo_* créneau est dilué par les features moins discriminantes pour les cas rares. Enrichi compense par un R²glob supérieur (0.575 vs 0.504) — meilleure régression générale, moins bonne détection de surcharges.

### 2. Segmenté ≥ Global pour PR-AUC haut (au sein de chaque feature set)

Enrichi_Seg (0.193) > Enrichi_Global (0.132) et APC_Seg (0.253) légèrement < APC_Global (0.301). La spécialisation haut améliore la détection dans le cas Enrichi, mais APC_Global reste supérieur à APC_Haut (0.301 vs 0.253) — probablement parce que les données bas fournissent un signal de calibration utile pour le modèle APC.

### 3. Rappel@WF identique pour toutes les variantes APC (13.8%)

Indépendamment du périmètre d'entraînement (global vs haut), les modèles APC appliqués au haut H25 produisent le même rappel. Cela suggère que le seuil WF calibré est bien adapté et que la puissance discriminante est saturée par les features APC.

---

## Ce qui reste à faire (étape 3)

Ce tableau est produit avec hyperparamètres figés (ADR-036 : 300 arbres, max_depth=6, lr=0.1). L'étape 3 teste la robustesse : variantes de n_estimators, max_depth, subsample. Le modèle final sera sélectionné après étape 3.

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_02_grille_results.csv` | 8 cellules (6 + 2 segmentés recombinés) × métriques + CI |
| `consolidation_finale/outputs/etape_02_rf1_verification.csv` | RF-1 connus vs renumérotés × 4 modèles |
| `consolidation_finale/figures/etape_02_grille_resultats.png` | PR-AUC / rappel / R² de la grille |
| `consolidation_finale/figures/etape_02_rf1_verification.png` | RF-1 avant/après créneau |
| `consolidation_finale/figures/etape_02_nan_comparison.png` | NaN histo_* avant/après |
