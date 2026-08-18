---
id: ADR-069
ancien_id: ADR-CF25
date_decision: 2026-06-28
statut: actif
modifie: [ADR-050, ADR-051]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-069 — Conservation de la perte MSE (`reg:squarederror`) : leviers de perte testés et écartés

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-050, ADR-051.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-28 |
| **Date** | 2026-06-28 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-052 (hyperparamètres XGBoost), ADR-060 (seuil surcharge 63), ADR-065 (Split C), ADR-030 / ADR-031 (découplage R²/rappel classe rare), ADR-033 (pivot régression + augmentation couche 2) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset ou de hash.** |

---

## Contexte

Le directeur du travail de master et un audit externe ont relevé que la perte
`reg:squarederror` (MSE) minimise son risque sur la **masse des faibles charges** (≤63,
~97 % des tronçons) et **sous-prédit structurellement la zone de surcharge >63** : le biais
canonique global sur H25 est de **−28,5** (le modèle prédit en moyenne 28,5 voyageurs de
moins que l'observé sur les tronçons réellement >63 ; HAUT : −42,3).

Question posée : **un autre traitement de la perte peut-il faire mieux sur la zone >63 —
réduire le biais ET/OU relever la séparabilité (PR-AUC) ?** La distinction est essentielle :
réduire le biais déplace le *point de fonctionnement* ; relever la PR-AUC relève le *plafond*
de pouvoir discriminant (capacité à ordonner surcharges et non-surcharges, indépendamment du
seuil de décision).

## Décision

**La perte `reg:squarederror` est CONSERVÉE comme perte canonique de la couche 1.**
**Aucun levier de perte** (pondération des observations ou perte asymétrique) **n'est adopté.**
Le modèle canonique `416bb90b` reste inchangé (hash vérifié intact).

## Rationnel empirique

Deux leviers de perte ont été testés sous protocole strict, **hors canonique**
(`consolidation_finale/exp_perte/`, aucun modèle expérimental sauvegardé) :

- **Protocole de choix** : train = H22 (hors Gilamont, ADR-065) + H23 → **validation H24**.
  Balayage du paramètre sur H24. **H25 jamais utilisé pour le choix.**
- **Confirmation de généralisation** : réentraînement tri-annuel H22+H23+H24 (Split C
  canonique, 801 282 obs) → **test H25** (309 252 obs), uniquement pour rapporter si le gain
  de validation généralise — **pas pour sélectionner**.
- **Iso-tout sauf le levier** : mêmes 158 features, hyperparamètres ADR-052 (n_est=300,
  depth=6, lr=0.1, subsample/colsample=0.8), seed=42, segmentation BAS/HAUT.

**Leviers testés**
1. **`sample_weight` binaire** : poids `W` si charge >63, sinon 1, sur le label réel.
   Balayage `W ∈ {1, 2, 3, 5, 10, 20}` (W=1 = contrôle MSE non pondéré).
2. **MSE asymétrique** : sous-prédiction pénalisée `k×`. Gradient `g = r` si `r ≥ 0`,
   `g = k·r` si `r < 0` ; hessien `h = 1` si `r ≥ 0`, `h = k` si `r < 0` (avec `r = pred − obs`).
   Optimum visé = quantile conditionnel `τ = k/(k+1)`. Balayage `k ∈ {1, 2, 3, 5, 9, 19}`
   (τ ≈ 0.5, 0.67, 0.75, 0.83, 0.9, 0.95).
   **Garde-fou validé** : k=1 reproduit `reg:squarederror` **bit-exact** (`max|Δpred| = 0`,
   BAS et HAUT, sur validation H24 comme sur le réentraînement tri-annuel).

### Verdict en trois points

**(a) Le biais >63 se réduit mécaniquement avec le paramètre, et généralise partiellement
sur H25 — effet réel mais modeste.** Sur H24, le biais global >63 passe de −29,1 (baseline)
à −24,3 (k=2) / −26,1 (W=2). Sur H25, l'amélioration retenue est d'environ **−2 à −2,5 sur le
biais global >63** (canonique −28,5 → k=2 −26,2 / W=2 −26,0), soit ~la moitié de l'amplitude
observée en validation.

**(b) La PR-AUC NE bouge PAS.** En validation, un saut initial modeste (W=2 / k=2) **sature
immédiatement** puis plateau ; pousser le paramètre plus haut (W=20, k=19, τ=0.95) réduit
encore le biais **sans** relever la PR-AUC. Sur le holdout H25, le saut **s'évapore** :
ΔPR-AUC tronçon et tour ≈ **±0,003** pour les deux leviers (k=2 : tronçon −0,003 / tour +0,001 ;
W=2 : tronçon +0,006 / tour −0,001). **Les deux leviers recalent le POINT DE FONCTIONNEMENT
(biais ↓) sans relever le PLAFOND de séparabilité.** Constat confirmé sur validation H24 ET
sur le test H25.

**(c) Le gain de R² de k=2 sur H24 (+0,034) était un sur-ajustement de validation.** Il
**s'inverse sur H25** (−0,015 : k=2 R² global 0,586 vs canonique 0,601). Sur le segment
**HAUT** (peu de surcharges, ~600 en H24 / ~1 200 en H25, statistiquement instable), k=2 est
**contre-productif sur le test** : PR-AUC tronçon **0,345 → 0,298** et biais >63 inchangé voire
dégradé. Observation comparative : **W=2 généralise plus proprement que k=2** (R² global
préservé 0,601→0,601, masse quasi intacte : MAE globale 7,71→7,77, sur-prédiction induite
biais ≤63 +1,4→+1,8) — **mais sans gain de séparabilité non plus**, donc **non adopté**.

### Synthèse chiffrée (H25, GLOBAL, n>63 = 9 584)

| Modèle | R² glob | MAE glob | biais >63 | MAE >63 | biais ≤63 | PR-AUC tronçon | PR-AUC tour |
|---|---:|---:|---:|---:|---:|---:|---:|
| Canonique (`reg:squarederror`) | 0,6013 | 7,712 | −28,47 | 29,09 | +1,37 | 0,4490 | 0,5635 |
| k=2 (MSE asym, τ=0,67) | 0,5863 | 8,108 | −26,23 | 27,05 | +3,11 | 0,4456 | 0,5643 |
| W=2 (`sample_weight`) | 0,6008 | 7,770 | −26,02 | 26,92 | +1,83 | 0,4549 | 0,5628 |

## Conséquence architecturale

**Le plafond de séparabilité de la couche 1 est une propriété du SIGNAL (features), non de la
fonction de perte ni du point de fonctionnement.** Ce chantier constitue une **validation
empirique de la distinction biais / pouvoir discriminant** :

1. **Couche 2 (recalibration / décision)** : ne peut que **choisir un point de fonctionnement
   sur une courbe PR fixe**. Recalibrer = se déplacer le long de la courbe (arbitrer
   précision/rappel), **pas** relever la courbe. La sous-prédiction structurelle de la zone >63
   relève donc d'un **réglage de seuil opérationnel** en couche 2, pas d'un changement de perte
   en couche 1.
2. **Seul levier capable de relever le plafond : l'enrichissement du SIGNAL** (nouvelles
   features porteuses d'information discriminante sur la zone >63). C'est la **piste suivante**.

## Traçabilité

- Balayages et confirmation H25 (scripts + sorties JSON/CSV) : `consolidation_finale/exp_perte/`
  - `balayage_sample_weight_h24.py` / `.csv` / `.json` — Phase 1 (sample_weight, validation H24).
  - `balayage_mse_asym_h24.py` / `.csv` / `.json` — Phase 2 (MSE asymétrique, validation H24 ;
    garde-fou k=1 ≡ `reg:squarederror`).
  - `confirmation_h25_k2_w2.py` / `confirmation_h25_k2_w2.json` — Phase 3 (test H25, 3 modèles ;
    garde-fou : modèles canoniques chargés reproduisent les métriques H25 publiées à Δ=0, et
    k=1 custom tri-annuel reproduit le canonique à `max|Δpred| = 0`).
- **Modèles expérimentaux non sauvegardés.** **Hash canonique `416bb90b` intact, vérifié**
  (lecture seule du dataset à chaque exécution).
- Aucune écriture dans le rapport de synthèse ni dans les autres ADR.
