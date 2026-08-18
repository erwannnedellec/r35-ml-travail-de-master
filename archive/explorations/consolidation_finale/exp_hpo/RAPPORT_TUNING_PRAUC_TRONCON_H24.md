# CHANTIER HP — re-tuning Optuna sur la PR-AUC tronçon globale (validation H24)

**Statut : tuning H24 réalisé. Candidat bat CF09 franchement ET stablement. ARRÊT — pas de
test H25 ici (étape séparée).** Hors canonique (`consolidation_finale/exp_hpo/`), hash
`416bb90b` intact (lecture seule), pipeline non touché, aucun modèle sauvegardé, **H25 jamais
chargé**.

## Pourquoi ce re-tuning
Le tuning précédent (ADR-CF27) optimisait un **proxy** (R² / biais, **par segment**). La cible
correcte de la couche 1 est la **PR-AUC tronçon globale** : séparabilité au **grain natif du
prédicteur**, sur **toute la ligne** (l'enjeu surcharge concerne tout le parcours, pas
seulement le HAUT). L'agrégation au tour et la décision relèvent de la **couche 2** → on reste
au **tronçon**.

## Protocole
Optuna TPE, **objectif unique = MAXIMIZE PR-AUC tronçon globale (H24)**, **HP partagés**
BAS/HAUT (à chaque essai : mêmes HP, entraîner les deux modèles, **réunir** les prédictions au
tronçon, calculer la PR-AUC tronçon globale). Pas de CV aléatoire. Train H22 (hors Gilamont) +
H23 → validation H24. 50 essais, seed=42. Observables loggés sans être optimisés.

**Garde-fou — PARFAIT.** CF09 (HP partagés) sur H24 : PR-AUC tronçon globale = **0,4759**,
**Δ = 0,0000** vs référence Phase B. (Fonction identique à celle validée en Phase C, qui
reproduisait la PR-AUC tronçon canonique H25 = 0,4490 à Δ=0.)

## Résultat — best vs CF09 (validation H24)

| | CF09 | best (essai 45) | Δ |
|---|---:|---:|---:|
| **PR-AUC tronçon globale** (cible) | 0,4759 | **0,5037** | **+0,0278** |
| PR-AUC tour globale | 0,5903 | 0,6019 | +0,0117 |
| R² global | 0,6586 | 0,6764 | +0,0178 |
| biais>63 global | −29,13 | −28,42 | **+0,71** (moins de sous-prédiction) |
| PR-AUC tronçon BAS | 0,4919 | 0,5192 | +0,0273 |
| PR-AUC tronçon HAUT | 0,3077 | 0,3292 | +0,0215 |

**HP du best** (≠ CF09) : depth=8, lr=0,0255, n_est=597, subsample=0,68, colsample=0,62,
min_child_weight=2, λ=3,42, α=0,18, γ=4,0. → régime **profond + lent + régularisé + sous-
échantillonné**.

**Sur H24, AUCUN arbitrage** : la PR-AUC tronçon (globale, BAS, HAUT), la PR-AUC tour, le R²
**et** le biais>63 s'améliorent **tous** — contrairement au candidat best-R² (ADR-CF27) qui
dégradait biais>63 et PR-AUC HAUT.

## Robustesse (le point décisif vs un coup de chance)

- **40 / 50 essais battent CF09** (0,4759) ; 9 essais > 0,50. Le gain n'est pas un point isolé.
- **Top-8 resserré** : objectif ∈ [0,5001 ; 0,5037] (écart **0,0036**), #1 vs #2 = 0,0014 —
  bien **inférieur au gain (+0,0278)** : signal franc, pas du bruit.
- **Les HP du top-8 convergent** et s'écartent **systématiquement** de CF09, dans le même sens :

| HP | CF09 | top-8 (min → méd → max) |
|---|---:|---|
| max_depth | 6 | 8 → 9 → 10 |
| learning_rate | 0,10 | 0,020 → 0,029 → 0,037 |
| n_estimators | 300 | 545 → 562 → 597 |
| subsample | 0,80 | 0,63 → 0,67 → 0,72 |
| colsample_bytree | 0,80 | 0,60 → 0,63 → 0,66 |
| min_child_weight | 1 | 2 → 5,5 → 9 |
| reg_lambda | 1,0 | 3,0 → 3,4 → 4,1 |
| reg_alpha | 0,0 | 0,18 → 0,49 → 0,91 |
| gamma | 0,0 | 0,22 → 1,9 → 4,7 |

C'est un **régime de régularisation cohérent et classique** (lr bas + plus d'arbres + L1/L2 +
sous-échantillonnage lignes/colonnes), pas un optimum exotique. Les observables du top-8 sont
homogènes (R² 0,673-0,678 ; biais>63 −28,2 à −28,5 ; tour 0,601-0,606 ; BAS 0,517-0,520).

## Lecture (validation H24, sans optimisme)

**C'est le premier levier à franchir la barre H24 franchement (+0,0278 ≫ bruit ~0,01) ET
stablement (top resserré + HP convergents) sur la BONNE métrique.** Le gain est **porté par le
BAS** (8 917 surcharges, segment stable) — donc sur la partie **fiable** de la métrique,
contrairement aux mirages HAUT précédents.

**MAIS H24 reste la validation.** Le précédent constant de ce projet est que les gains de
validation **s'atténuent ou s'inversent** sur H25 (k=2 : R² +0,034→−0,015 ; best-R² : PR-AUC
HAUT +0,043→−0,007 ; features Phase C : BAS +0,019→+0,0055). Le best-R² avait déjà montré une
atténuation BAS au ⅕–¼ hors échantillon. Donc même un gain franc et robuste **en validation**
ne garantit pas la généralisation. Ce qui distingue ce candidat : (1) cible native correcte,
(2) régime de régularisation **défendable et convergent** (mécanisme = meilleur ordonnancement,
pas sur-ajustement de la masse), (3) gain sur le **segment stable**. Cela le rend **plus
crédible** que les candidats précédents — sans le démontrer.

## Suite (décision conjointe)
Selon le critère pré-posé (« bat CF09 franchement et stablement sur H24 → test H25 séparé,
critère strict »), **ce candidat est éligible au test H25**. Recommandation : **un test H25
unique et strict** (mêmes garde-fous : CF09 reproduit `metrics_h25` à Δ=0 ; critère
d'adoption = aucune dégradation matérielle, et gain PR-AUC tronçon globale qui survit franchement
hors échantillon). À décider ensemble.

**ARRÊT** : validation H24 seule. Pas de test H25, pas d'adoption, pas de re-figement ici.

## Traçabilité
`consolidation_finale/exp_hpo/tuning_optuna_h24_prauc_troncon.py`, sorties
`tuning_prauc_troncon_h24_resultats.json` / `_trials.csv`, figures
`history_prauc_troncon_h24.png`, `param_importance_prauc_troncon_h24.png`. Garde-fou CF09 =
0,4759 (Δ=0). Hash `416bb90b` intact. Aucune écriture pipeline/rapport/dataset.
