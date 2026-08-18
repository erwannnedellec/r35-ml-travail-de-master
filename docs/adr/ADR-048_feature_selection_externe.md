---
id: ADR-048
ancien_id: ADR-CF05
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-050, ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-048 — Feature selection contrôlée des sources externes

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-050, ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** **La décision de fond de ce document n'est pas celle retenue.** Le modèle final de couche 1 n'est pas APC-only (38 variables) mais Enrichi_Seg (ADR-052), à 158 variables après ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (F2), ADR-047 (robustesse hyperparams)

---

## Question

L'Enrichi-brut (179 features) fait moins bien qu'APC-only (38 features) sur PR-AUC haut H25.
Est-ce que l'information externe est structurellement inutile, ou est-ce que le signal est noyé
sous 141 features brutes ?

---

## Protocole

- **Importance** : XGBoost gain normalisé sur TRAIN H22-H24 complet (jamais H25)
- **Modèles** : APC-only (38) + top-K externes, K ∈ {5, 10, 20, 40} + Enrichi-brut (179)
- **Seuil** : F2 recalibré sur train (ADR-046) | **Hyperparams** : figés ADR-036 (comparabilité ADR-047)
- **Évaluation** : H25 lecture seule, embargo 9j, IC bootstrap 95 %
- **Règle** : sélection des features figée depuis le classement TRAIN, jamais H25

---

## Partie A — Importance des features externes (TRAIN uniquement)

### Importance par source (gain XGBoost normalisé, H22-H24)

| Source | Gain total | N features |
|--------|-----------|-----------|
| STATPOP (`spatial_*`) | **0.145** | 45 |
| ISTDATEN (`ist_*`) | 0.066 | 28 |
| Météo (`meteo_*`) | 0.065 | 27 |
| Réservations (`resa_*`) | 0.060 | 8 |
| Événements (`event_*`) | 0.042 | 17 |
| SIMBA (`simba_*`) | 0.041 | 12 |
| VMCV (`vmcv_*`) | 0.031 | 4 |

**9/141 features externes à importance=0** (jamais utilisées comme split sur le train).

### Top features externes retenues par K

| K | Composition | Features dominantes |
|---|-------------|---------------------|
| **K=5** | spatial(2), resa(2), vmcv(1) | menages_500m, resa_n_dossiers, vmcv_n_lignes |
| **K=10** | spatial(6), resa(3), vmcv(1) | + pop_nee_etranger, pax_2c_J-1, max_groupe |
| **K=20** | spatial(8), resa(3), ist(3), event(3), meteo(2), vmcv(1) | + headway, neige_binaire, manifestations |
| **K=40** | spatial(11), ist(7), simba(7), meteo(5), event(5), resa(4), vmcv(1) | + IST ponctualité, SIMBA parts tarifaires |

### Ce que la sélection écarte (non retenu avant K=40)

| Source | Retenues K=40 | Total | Éliminées | Raison probable |
|--------|--------------|-------|-----------|----------------|
| IST ponctualité (famille A) | 7/28 | 28 | 21 | NaN H22=89 %, H23=62 % → signal partiel |
| SIMBA | 7/12 | 12 | 5 | Corrélation r=0.97 APC, signal marginal |
| histo_total_* | *(APC-only)* | — | — | Redondant avec histo_2eme |
| histo_1ere_* | *(APC-only)* | — | — | Idem, volume < 2ème classe |

---

## Partie B — Évaluation H25 (lecture seule)

### Résultats par modèle

| Modèle | N feats | Seuil F2 | PR-AUC haut | IC 95 % | Rappel@WF | Précision | R² global |
|--------|---------|----------|-------------|---------|-----------|-----------|-----------|
| **APC-only** | **38** | 32.22 | **0.301** | **[0.244–0.356]** | **62.6 %** | 13.1 % | 0.503 |
| Enrichi-K5 | 43 | 45.50 | 0.175 | [0.138–0.220] | 53.5 % | 12.4 % | 0.572 |
| Enrichi-K10 | 48 | 41.79 | 0.225 | [0.179–0.277] | 57.2 % | 12.2 % | 0.573 |
| Enrichi-K20 | 58 | 43.46 | 0.224 | [0.183–0.276] | 63.3 % | 12.0 % | 0.578 |
| Enrichi-K40 | 78 | 42.94 | 0.145 | [0.117–0.179] | 57.2 % | 11.4 % | 0.578 |
| Enrichi-brut | 179 | 48.46 | 0.132 | [0.109–0.164] | 52.5 % | 14.8 % | 0.574 |

---

## Partie C — Vérification RF-1

**Note de définition** : avec `horaire_service_id_complet` (encode heure de départ + numéro), TOUS les H25 haut (77 262 obs, 297 surcharges) sont « renumérotés » — cohérent avec étape 0 (refonte totale 2024→2025 des horaires). Le créneau ×sens permet à APC-only de les détecter malgré l'absence d'historique exact.

**Comparaison PR-AUC sur renumérotés H25 haut (100 % de la population) :**

| Modèle | PR-AUC renumérotés | Rappel@WF |
|--------|--------------------|-----------|
| APC-only | **0.301** | 62.6 % |
| Enrichi-K10 | 0.225 | 57.2 % |
| Enrichi-K20 | 0.224 | 63.3 % |
| Enrichi-K40 | 0.145 | 57.2 % |
| Enrichi-brut | 0.132 | 52.5 % |

APC-only = meilleure détection sur les trains renumérotés. Les features externes diluent systématiquement le signal histo_* créneau.

---

## Findings clés

### 1. Enrichi-sélectionné < APC-only sur PR-AUC haut pour tout K

APC-only (0.301) > Enrichi-K10 (0.225) > Enrichi-K20 (0.224) > Enrichi-K5 (0.175) > Enrichi-K40 (0.145) > Enrichi-brut (0.132).

**Ce n'est pas un problème de noyage du signal** : même avec seulement 5 features externes soigneusement sélectionnées, la PR-AUC chute de 0.301 → 0.175. Le problème est structurel.

### 2. Courbe PR-AUC vs K non monotone

- K=10 est le meilleur Enrichi-K (0.225), mais reste 25 % sous APC-only
- K=5 < K=10 (les 5 meilleures features sont encore trop peu cohérentes avec le signal surcharge)
- K > 10 dégrade à nouveau (K=40 pire que K=10)
- L'ajout de toute feature externe, même la meilleure, dilue le signal histo_* créneau

### 3. R² global : les externes aident dès K=5

APC-only : 0.503 → K=5 : 0.572 (+14 %). Plateau à K=20 (0.578). Les 3 premières features externes (STATPOP ménages, réservations J-1, VMCV lignes) apportent l'essentiel du gain de régression. L'ajout de K=40 à 179 n'améliore plus.

### 4. Les réservations (resa_*) sont la 2ème source par importance individuelle

`resa_n_dossiers_J_minus_1` (rank 2) et `resa_pax_2c_J_minus_1` (rank 5) sont top-5. Elles améliorent R² mais dégradent PR-AUC : elles prédisent la charge moyenne mais introduisent un biais qui écrase les prédictions extrêmes (surcharges rares).

### 5. Conclusion sur la valeur de l'enrichissement

| Objectif | Recommandation |
|----------|----------------|
| **Détection surcharges (couche 1 opérationnelle)** | **APC-only** — les externes nuisent |
| **Prédiction continue de charge (recherche/contexte)** | **Enrichi-K5 ou K10** — gain R² +14 %, minimal en features |

---

## Décision

**L'enrichissement externe ne contribue pas à l'objectif principal (détection UM J-1).**

Le modèle final couche 1 retenu est : **APC-only (38 features), hyperparams ADR-036 figés** (ou tunés ADR-047 si retenu par Erwann).

Cette conclusion clôt la question de la valeur de l'enrichissement externe pour la détection de surcharges. Elle sera documentée dans le corps de la thèse (Chapitre 4 — Évaluation de l'artefact) comme un résultat en soi : la charge historique créneau × sens est suffisante ; les sources socio-démographiques, météo et réservations n'apportent pas de valeur incrémentale pour la tâche de classification de surcharge.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03bis_feature_selection.ipynb` | Notebook réexécutable |
| `consolidation_finale/outputs/etape_03bis_feature_importance.csv` | 141 features externes classées par gain |
| `consolidation_finale/outputs/etape_03bis_enrichi_k_results.csv` | Métriques H25 par modèle (6 lignes) |
| `consolidation_finale/outputs/etape_03bis_rf1_results.csv` | RF-1 par modèle × strate |
| `consolidation_finale/figures/etape_03bis_enrichi_k_comparison.png` | PR-AUC/Rappel/R² par K (300 DPI) |
| `consolidation_finale/figures/etape_03bis_feature_importance.png` | Top-50 importance externe (300 DPI) |
| `consolidation_finale/figures/etape_03bis_tradeoff_K.png` | Courbe PR-AUC et R² vs N features (300 DPI) |
