---
id: ADR-051
ancien_id: ADR-CF08
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-069]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-051 — Pertes alternatives : quantile regression et Tweedie

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-069.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». Les pertes alternatives instruites ici (quantile, Tweedie) sont **écartées** : ADR-069 conserve `reg:squarederror`.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-050 (weighting), ADR-049 (cadrage bas/haut), ADR-036 (modèle référence)

---

## Contexte et motivation

ADR-050 a montré que le **sample weighting MSE** (w=20 optimal) réduit le biais≥80 haut de
seulement 15 % (-50.4 → -42.6), sans l'éliminer. La sous-prédiction structurelle des surcharges
est une propriété de l'objectif MSE : en minimisant l'erreur quadratique sur une distribution
fortement asymétrique (0.4 % de surcharges), XGBoost converge vers la **moyenne conditionnelle**,
qui est massivement tirée vers le bas par la masse des observations normales.

La Phase 3 explore deux familles de pertes qui modifient cet objectif :

1. **Quantile regression** (`reg:quantileerror`, α ∈ {0.85, 0.90, 0.95}) : minimise la perte
   de vérification pinball. Le modèle prédit le **α-quantile** de la distribution conditionnelle,
   pas la moyenne. Pour α > 0.5, le modèle est entraîné à prédire haut.

2. **Tweedie regression** (`reg:tweedie`) : perte multiplicative adaptée aux données de comptage
   positives et sur-dispersées. Objectif `log(y_pred)` → invariant d'échelle, adapté aux
   distributions Power-loi.

**Candidats testés** : Enrichi_Seg (179 features, architecture segmentée) et APC_Seg (38 features),
identifiés comme meilleurs dans leurs familles respectives en Phase 1. Hyperparams ADR-036 figés.
Walk-forward H22→H24 (train), H25 lecture seule.

---

## ⚠️ Avertissement d'interprétation (à lire avant le tableau)

**Le quantile loss change la signification de la prédiction.**

- MSE → le modèle prédit la **charge attendue** (moyenne conditionnelle). Un biais négatif signifie
  sous-estimation.
- Quantile α → le modèle prédit un **majorant prudent de la charge** au niveau α. Un "meilleur
  biais≥80" à α élevé ne signifie pas que le modèle prédit mieux — il signifie que le modèle
  prédit plus haut sur l'ensemble des observations, y compris les charges basses et moyennes
  (sur-prédiction de 34 à 82 % sur le MAE global, cf. tableau).

**Ne pas comparer directement le biais≥80 entre MSE et quantile comme si c'était la même métrique.**
Le biais≥80 d'un modèle quantile α=0.95 signifie "le 95e quantile prédit est encore inférieur à la
charge réelle pour les surcharges" — et non "le modèle sous-prédit de X voyageurs en espérance".

---

## Phase 3 — Résultats par perte et segment

### Segment HAUT (77 262 obs, 297 surcharges ≥80)

| Configuration | R² | MAE | MAE≥80 | Biais≥80 [IC95%] | Δbiais vs MSE |
|---------------|-----|-----|--------|------------------|---------------|
| **Enrichi_Seg MSE** (baseline) | **0.480** | 6.19 | 50.4 | −50.4 [−50.4; −49.0] | — |
| Enrichi_Seg tweedie | 0.374 | **6.05** | 64.5 | −64.5 [−66.6; −62.3] | −14.1 (pire) |
| Enrichi_Seg q=0.85 | 0.347 | 8.29 | 39.6 | −39.2 [−41.5; −37.1] | **+11.2 (−22%)** |
| Enrichi_Seg q=0.90 | 0.198 | 9.67 | 35.7 | −34.2 [−36.7; −31.9] | +16.2 (−32%) |
| Enrichi_Seg q=0.95 | 0.024 | 11.03 | 34.0 | −31.8 [−34.1; −29.4] | +18.6 (−37%) |
| **APC_Seg MSE** (baseline) | **0.306** | 5.73 | 60.5 | −59.5 | — |
| APC_Seg tweedie | 0.314 | 6.62 | 65.6 | −64.1 [−66.5; −61.8] | −4.6 (pire) |
| APC_Seg q=0.85 | 0.164 | 9.40 | 48.0 | −46.3 [−48.6; −44.0] | +13.2 (−22%) |
| APC_Seg q=0.90 | −0.033 | 10.97 | 45.4 | −43.8 [−46.0; −41.3] | +15.7 (−26%) |
| APC_Seg q=0.95 | −0.463 | 13.63 | 39.3 | −36.9 [−39.2; −34.5] | +22.6 (−38%) |

### Segment BAS (223 211 obs, 1 215 surcharges ≥80)

| Configuration | R² | MAE | MAE≥80 | Biais≥80 |
|---------------|-----|-----|--------|----------|
| **Enrichi_Seg MSE** (baseline) | **0.556** | 8.61 | 40.1 | −39.8 |
| Enrichi_Seg tweedie | 0.493 | 8.94 | 48.6 | −48.5 (pire) |
| Enrichi_Seg q=0.85 | 0.358 | 11.51 | 29.0 | −25.6 |
| Enrichi_Seg q=0.90 | 0.204 | 13.22 | 26.1 | −21.9 |
| Enrichi_Seg q=0.95 | −0.062 | 15.79 | 23.7 | −18.9 |
| **APC_Seg MSE** (baseline) | **0.494** | 9.17 | 44.5 | −44.4 |
| APC_Seg tweedie | 0.495 | 9.04 | 46.3 | −46.1 (pire) |
| APC_Seg q=0.85 | 0.312 | 11.51 | 34.1 | −32.3 |
| APC_Seg q=0.90 | 0.161 | 13.39 | 31.3 | −28.5 |
| APC_Seg q=0.95 | −0.137 | 16.07 | 27.7 | −24.1 |

### Segment GLOBAL (recombinés, 300 473 obs)

| Configuration | R² | MAE global | Biais≥80 global | Sur-prédiction¹ |
|---------------|-----|-----------|----------------|-----------------|
| **Enrichi_Seg MSE** | **0.584** | **7.99** | −41.5 | — |
| Enrichi_Seg tweedie | 0.520 | 8.19 | −51.0 (pire) | ≈ MSE |
| Enrichi_Seg q=0.85 | 0.415 | 10.68 | −27.7 | **+34 %** MAE |
| Enrichi_Seg q=0.90 | 0.275 | 12.30 | −23.9 | +54 % MAE |
| Enrichi_Seg q=0.95 | 0.048 | 14.56 | −21.0 | +82 % MAE |
| **APC_Seg MSE** | 0.510 | 8.53 | −46.8 | — |
| APC_Seg tweedie | 0.512 | 8.42 | −49.0 (pire) | ≈ MSE |
| APC_Seg q=0.85 | 0.351 | 11.21 | −34.6 | +31 % MAE |
| APC_Seg q=0.90 | 0.207 | 12.77 | −31.0 | +50 % MAE |
| APC_Seg q=0.95 | −0.086 | 15.44 | −26.2 | +81 % MAE |

¹ Augmentation du MAE global par rapport à la baseline MSE de même feature set : proxy de la sur-prédiction sur les charges basses/moyennes.

---

## Grand Tableau Final — Tous les modèles couche 1

Tableau de référence pour la validation. Lignes = feature set × architecture × perte.
**Candidats Phase 3 uniquement sur `Seg`** (meilleure architecture Phase 1).

| # | Modèle | Perte | w | R² haut | MAE≥80 haut | Biais≥80 haut | R² bas | Biais≥80 bas | R² global | Biais≥80 global | PR-AUC haut |
|---|--------|-------|---|---------|------------|---------------|--------|-------------|-----------|----------------|------------|
| 1 | **Enrichi_Seg** | MSE | 1 | **0.480** | 50.4 | −50.4 | **0.556** | −39.8 | **0.584** | −41.5 | 0.191 |
| 2 | APC_Seg | MSE | 1 | 0.306 | 60.5 | −59.5 | 0.494 | −44.4 | 0.510 | −46.8 | **0.254** |
| 3 | Enrichi_Seg | MSE | 10 | 0.462 | 44.1 | −43.7 | 0.545 | −37.8 | 0.573 | −38.8 | 0.174 |
| 4 | APC_Seg | MSE | 10 | 0.287 | 57.3 | −57.2 | 0.480 | −42.5 | 0.496 | −44.9 | 0.290 |
| 5 | Enrichi_Seg | MSE | 20 | 0.443 | 43.1 | −42.6 | 0.535 | −36.8 | 0.563 | −37.8 | 0.153 |
| 6 | APC_Seg | MSE | 20 | 0.282 | 58.5 | −58.5 | 0.467 | −42.5 | 0.486 | −45.1 | 0.237 |
| 7 | Enrichi_Seg | q=0.85 | 1 | 0.347 | 39.6 | **−39.2** | 0.358 | **−25.6** | 0.415 | **−27.7** | 0.156 |
| 8 | APC_Seg | q=0.85 | 1 | 0.164 | 48.0 | −46.3 | 0.312 | −32.3 | 0.351 | −34.6 | 0.274 |
| 9 | Enrichi_Seg | q=0.90 | 1 | 0.198 | 35.7 | −34.2 | 0.204 | −21.9 | 0.275 | −23.9 | 0.206 |
| 10 | APC_Seg | q=0.90 | 1 | −0.033 | 45.4 | −43.8 | 0.161 | −28.5 | 0.207 | −31.0 | 0.252 |
| 11 | Enrichi_Seg | q=0.95 | 1 | 0.024 | 34.0 | −31.8 | −0.062 | −18.9 | 0.048 | −21.0 | 0.157 |
| 12 | APC_Seg | q=0.95 | 1 | −0.463 | 39.3 | −36.9 | −0.137 | −24.1 | −0.086 | −26.2 | 0.247 |
| 13 | Enrichi_Seg | tweedie | 1 | 0.374 | 64.5 | −64.5 | 0.493 | −48.5 | 0.520 | −51.0 | 0.261 |
| 14 | APC_Seg | tweedie | 1 | 0.314 | 65.6 | −64.1 | 0.495 | −46.1 | 0.512 | −49.0 | 0.279 |

**Colonnes** : Biais≥80 = biais moyen sur les observations à charge réelle ≥ 80 (négatif = sous-prédiction) ; PR-AUC = courbe précision-rappel avec seuil walk-forward, informatif couche 2.  
**Gras** = meilleur par colonne dans son groupe de comparaison.

---

## Analyse par perte

### Tweedie — Levier nul, aggrave les charges élevées

La perte Tweedie **n'améliore pas** les surcharges : biais≥80 haut passe de −50.4 → −64.5 pour
Enrichi_Seg (+28 % de sous-prédiction). La perte multiplicative pénalise plus fortement les
erreurs relatives sur les grandes valeurs, mais dans notre contexte (distribution bimodale
apc_comptage + évènements rares), ce mécanisme amplifie la régression vers la moyenne sur les
hautes charges plutôt que de la corriger. R² haut = 0.374, acceptable mais inférieur à MSE (0.480).

**Verdict : rejeté.** Tweedie est inadapté au problème — ne corrige pas le biais structurel et
dégrade la précision sur les surcharges.

### Quantile regression — Compromis biais/R² progressif mais coûteux

Le quantile loss réduit le biais≥80 en déplaçant l'objectif de prédiction de la moyenne vers un
quantile supérieur. Cet effet est réel mais a un coût mesurable sur l'ensemble de la distribution :

| α | Δbiais≥80 haut | R² haut | MAE global Enrichi | Sur-prédiction globale |
|---|---------------|---------|-------------------|----------------------|
| MSE | — | 0.480 | 7.99 | 0 % |
| 0.85 | −22 % | 0.347 | 10.68 | +34 % |
| 0.90 | −32 % | 0.198 | 12.30 | +54 % |
| 0.95 | −37 % | ≈0 | 14.56 | +82 % |

Trois observations clés :

1. **Le biais≥80 reste toujours négatif, même à α=0.95** : le 95e quantile prédit est encore
   inférieur à la charge réelle pour les surcharges (biais=-31.8 sur haut). La queue de
   distribution est extrêmement difficile à capturer — un quantile élevé corrige partiellement
   mais pas entièrement. Cette observation confirme que le problème "60 vs 95" est structurel.

2. **α élevé = sur-prédiction des charges normales** : à α=0.90, le MAE global augmente de +54 %
   (+4.3 voyageurs/tronçon en moyenne). Sur les charges basses (pas de surcharge), le modèle
   annonce davantage de voyageurs que n'en observe l'APC. Coût opérationnel : faux positifs
   potentiels si ce profil de charge nourrit la couche 2 sans correction.

3. **R² haut à α=0.95 ≈ 0** pour Enrichi_Seg (0.024) et négatif pour APC_Seg (−0.463) : le
   modèle quantile sur-prédit systématiquement sur l'ensemble haut — il ne classe plus les jours
   correctement à l'intérieur du segment. Ce n'est plus un modèle de régression : c'est un
   majorant quasi-constant.

### Meilleur compromis Phase 3 : Enrichi_Seg q=0.85

- Biais haut : −39.2 (vs −50.4 MSE, **−22 %**)
- R² haut : 0.347 (vs 0.480 MSE, **−28 %**)
- MAE global : 10.68 (vs 7.99 MSE, **+34 %**)
- Biais global : −27.7 (vs −41.5 MSE, **−33 %**)

Gain biais = 22 % haut. Coût : R² haut perd 28 %, MAE global augmente de 34 %.

---

## Comparaison synthétique — Candidats résiduels

Quatre candidats méritent d'être mis en regard pour la décision finale :

| Candidat | R² haut | Biais≥80 haut | R² global | Biais≥80 global | MAE global | Signification |
|----------|---------|-------------|-----------|----------------|-----------|---------------|
| Enrichi_Seg MSE | **0.480** | −50.4 | **0.584** | −41.5 | **7.99** | charge attendue (moyenne) |
| Enrichi_Seg MSE w=20 | 0.443 | −42.6 | 0.563 | −37.8 | ~8.5* | charge attendue, pondérée |
| Enrichi_Seg q=0.85 | 0.347 | **−39.2** | 0.415 | **−27.7** | 10.68 | majorant 85e quantile |
| Enrichi_Seg q=0.90 | 0.198 | −34.2 | 0.275 | −23.9 | 12.30 | majorant 90e quantile |

*MAE w=20 non disponible directement dans le grand tableau (vient d'ADR-050).

**La décision de fond** : veut-on un modèle couche 1 qui prédit la **charge probable** (MSE,
meilleur R², sous-prédit les surcharges) ou un **majorant prudent de la charge** (quantile, moins
de sous-prédiction sur les surcharges mais sur-prédit les cas normaux et qualité globale dégradée) ?

Ce sont deux usages différents pour l'artefact UM :
- MSE → le praticien voit "probabilité que 65 voyageurs soient attendus" → il doit interpréter que
  les vraies surcharges peuvent dépasser de 50 voyageurs
- q=0.85 → le praticien voit "je m'attends à au moins X voyageurs dans 85 % des cas" → biais
  réduit sur les surcharges mais les jours "normaux" semblent plus chargés qu'ils ne le sont

---

## Ce qui n'est PAS décidé ici

**Le modèle final couche 1 n'est pas figé dans cet ADR.**

Ce tableau est présenté pour validation avant décision. La question centrale est l'arbitrage
R²/biais dans le contexte opérationnel :
- Si la couche 2 (seuil, détection) absorbe complètement le biais (signal relatif suffit) →
  Enrichi_Seg MSE est optimal (R² maximal).
- Si le profil de charge absolu est montré à l'opérateur et que la sous-prédiction de 50
  voyageurs est jugée problématique → Enrichi_Seg q=0.85 est un compromis documenté (−22 %
  biais, −28 % R²).
- Enrichi_Seg q=0.90+ et Tweedie : non recommandés.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_3q5_phase3.csv` | Phase 3 — 8 configs × 3 segments (24 lignes) |
| `consolidation_finale/outputs/etape_3q5_grand_tableau.csv` | Grand tableau — 14 modèles × métriques |
| `consolidation_finale/figures/etape_3q5_biais_par_config.png` | Biais≥80 par modèle/segment/perte (300 DPI) |
| `consolidation_finale/figures/etape_3q5_biais_vs_r2.png` | Trade-off biais/R² (300 DPI) |
| `consolidation_finale/figures/etape_3q5_predit_vs_reel.png` | Prédit vs réel avant/après (300 DPI) |
| `consolidation_finale/figures/etape_3q5_quantile_effect.png` | Effet de α sur la distribution (300 DPI) |

> ⚠️ **Note technique** : le notebook `etape_03quinquies_pertes_alternatives.ipynb` n'a pas été
> sauvegardé (session interrompue). Les outputs CSV et figures ont été persistés avant interruption.
> Les résultats sont reproductibles depuis `etape_03quat_regression_weighting.ipynb` (Phase 1-2)
> en ajoutant la boucle Phase 3 sur `reg:quantileerror` et `reg:tweedie`.
