# CHANTIER HP — test H25 décisif : best-PR-AUC-tronçon vs CF09

**Statut : test H25 réalisé. VERDICT = NON-ADOPTION (les 2 conditions échouent). ARRÊT — pas
de re-figement.** Hors canonique (`exp_hpo/`), hash `416bb90b` intact (lecture seule), pipeline
non touché, aucun modèle sauvegardé. H25 touché une seule fois.

## Critère d'adoption (posé AVANT les chiffres, strict)
(1) gain PR-AUC tronçon globale **≥ +0,014** sur H25 (moitié du +0,028 H24) ; ET
(2) **aucune dégradation matérielle** (R² global, biais>63 tous segments, PR-AUC tour globale,
pas d'effondrement PR-AUC HAUT). Les **deux** → éligible adoption. Sinon → CF09 conservé.

## Protocole & garde-fou
Train tri-annuel H22 (hors Gilamont) + H23 + H24 (801 282) → test H25 (309 252), Split C.
HP **partagés** ; candidat = best essai 45 (depth8 / lr0,0255 / n597 / sub0,68 / col0,62 /
mcw2 / λ3,42 / α0,18 / γ4,0). 158f, seed42, seg BAS/HAUT, `reg:squarederror`.

**Garde-fou PARFAIT** : CF09 reproduit les `metrics_h25` canoniques à **Δ = 0,0000** sur les
**cinq** repères (R² 0,6013 ; PR-AUC tronçon globale 0,4490 ; BAS 0,4687 ; HAUT 0,3452 ; tour
0,5635). Comparaison propre.

## Résultats H25 — CF09 vs candidat

| segment | métrique | CF09 | candidat | Δ H25 | (Δ H24) |
|---|---|---:|---:|---:|---:|
| **global** | **PR-AUC tronçon** (cible) | 0,4490 | 0,4593 | **+0,0103** | +0,0278 |
| global | PR-AUC tour | 0,5635 | 0,5685 | +0,0050 | +0,0116 |
| global | R² | 0,6013 | 0,6120 | +0,0106 | +0,0178 |
| global | MAE globale | 7,712 | 7,605 | −0,107 | |
| global | **biais>63** | −28,47 | −29,22 | **−0,75** ⚠ | +0,71 |
| bas | PR-AUC tronçon | 0,4687 | 0,4822 | +0,0135 | +0,0273 |
| bas | PR-AUC tour | 0,5531 | 0,5633 | +0,0102 | |
| bas | R² | 0,5868 | 0,5940 | +0,0071 | |
| bas | biais>63 | −26,51 | −26,95 | −0,44 | |
| haut | R² | 0,4334 | 0,4671 | +0,0338 | |
| haut | **biais>63** | −42,27 | −45,20 | **−2,94** ⚠ | |
| haut | MAE>63 | 42,40 | 45,20 | +2,80 ⚠ | |
| **haut** | **PR-AUC tronçon** | 0,3452 | 0,3374 | **−0,0078** ⚠ | +0,0215 |
| **haut** | **PR-AUC tour** | 0,3459 | 0,3402 | **−0,0058** ⚠ | |

## Verdict mécanique (selon le critère pré-posé)

**(1) Gain insuffisant.** PR-AUC tronçon globale H25 = **+0,0103 < +0,014** → **ÉCHEC**. Le gain
H24 (+0,0278) **s'atténue à 37 %** hors échantillon — même schéma que tous les leviers
précédents (k=2, best-R², features Phase C).

**(2) Dégradation matérielle.** → **ÉCHEC** sur :
- **biais>63 HAUT −2,94** (et global −0,75) : sous-prédiction de la zone de surcharge **aggravée** ;
  MAE>63 HAUT +2,80.
- **PR-AUC HAUT en baisse** (tronçon −0,0078, tour −0,0058) : le gain HAUT de validation
  (+0,0215) **s'inverse** — **3ᵉ confirmation** que les mouvements PR-AUC HAUT en validation sont
  du bruit de petit échantillon (HAUT ≈ 620 / 1 192 surcharges).

**VERDICT : NON-ADOPTION — CF09 conservé** (gain sous le seuil **ET** dégradation matérielle).

## Lecture honnête (sans optimisme ni pessimisme)

C'était le candidat le **plus sérieux** du projet : gain H24 franc (+0,028) et robuste (40/50
essais, HP convergents, cible correcte). Et il **généralise partiellement** — contrairement à
k=2/best-R² qui s'effondraient, ici R² (+0,011), MAE globale (−0,11), **PR-AUC tronçon globale
(+0,010)** et **BAS (+0,0135)** restent **positifs** sur H25. Le régime régularisé apporte un
**vrai petit mieux sur le segment stable**.

**Mais** : (a) ce mieux est **sous le seuil strict** (+0,010 < +0,014), et (b) il s'**accompagne**
d'une dégradation de la **zone >63** (biais HAUT −2,94, le régime profond/régularisé prédit
encore plus bas sur les rares très fortes charges) et d'un **recul PR-AUC HAUT** (mirage de
validation inversé, 3ᵉ fois). Le critère, posé pour éviter d'adopter un candidat sous-seuil ET
dégradant, **fait son travail**.

## Conséquence
CF09 **conservé**. Même en optimisant la **bonne métrique** (PR-AUC tronçon globale) et avec un
signal de validation franc et robuste, le tuning d'HP ne livre qu'un gain OOT **sous le seuil
d'intérêt**, **au prix** d'une dégradation de la zone de surcharge. Cela **renforce** la
conclusion triangulée (perte ADR-CF25, features ADR-CF26, HP ADR-CF27) : le **plafond HAUT et le
biais de la zone >63 sont intrinsèques au signal J-1** ; les gains de régularisation sur le R²/la
masse **se paient sur la classe rare** (tension ADR-31/32). 

*Note pour la suite :* ADR-CF27 (conservation CF09) pourra être **amendé** pour intégrer ce
re-tuning sur la cible correcte — argument plus fort encore (méthode défendable, cible native,
gain OOT sous-seuil + dégradant). À décider ensemble.

**ARRÊT** : table H25 + verdict produits. Aucun re-figement, canonique `416bb90b` intact.

## Traçabilité
`consolidation_finale/exp_hpo/test_h25_prauc_troncon_vs_cf09.py` / `.json`. Garde-fou : CF09
reproduit les 5 `metrics_h25` canoniques à Δ=0. Hash `416bb90b` intact. Aucune écriture
pipeline/rapport/dataset.
