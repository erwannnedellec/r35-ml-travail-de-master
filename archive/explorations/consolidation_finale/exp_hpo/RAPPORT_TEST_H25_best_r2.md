# CHANTIER HYPERPARAMÈTRES — test H25 : best-R² (Optuna) vs CF09

**Statut : test H25 décisif réalisé. VERDICT = NON-ADOPTION. ARRÊT — pas de re-figement.**
Hors canonique (`consolidation_finale/exp_hpo/test_h25_best_r2_vs_cf09.py`). Hash
`416bb90b` intact (lecture seule, contrôlé), pipeline non touché, aucun modèle sauvegardé.
H25 touché une seule fois pour ce test.

## Critère d'adoption (posé AVANT de voir les chiffres)
best-R² remplace CF09 **seulement s'il ne dégrade matériellement AUCUNE** métrique clé sur
H25 : R² global, biais>63, **PR-AUC tronçon ET tour par segment**. Jeu égal ou mieux partout
→ adoption. Dégradation matérielle d'une métrique → non-adoption, conservation CF09.
Seuils : R²g Δ < −0.005 ; biais>63 plus négatif de > 0.5 ; PR-AUC (par segment) Δ < −0.005.

## Protocole
Train tri-annuel H22 (hors Gilamont) + H23 + H24 (801 282) → test H25 (309 252), Split C.
158 features, seed=42, segmentation BAS/HAUT, `reg:squarederror`, seuil 63. **Iso-tout sauf
les HP.** best-R² = HP **différenciés par segment** (issus de `tuning_optuna_h24_resultats.json`,
Pareto best-R²) ; CF09 = HP **partagés**.

| | BAS | HAUT |
|---|---|---|
| **CF09** | depth6 lr0.10 n300 sub0.80 col0.80 mcw1 γ0 λ1 α0 | *(identiques)* |
| **best-R²** | depth8 lr0.029 n360 sub0.82 col0.67 mcw10 γ4.47 λ3.88 α1.88 | depth5 lr0.077 n349 sub0.63 col0.63 mcw2 γ3.37 λ3.44 α0.82 |

**Garde-fou — PARFAIT.** CF09 reproduit les `metrics_h25` canoniques à **Δ = 0.0000**
(R² et PR-AUC, BAS/HAUT/global). Comparaison propre.

## Résultats H25 — CF09 vs best-R² (Δ = best − CF09)

| segment | métrique | CF09 | best-R² | Δ | matériel ? |
|---|---|---|---|---|---|
| global | R² | 0.6013 | 0.6054 | **+0.0040** | mieux |
| global | MAE glob | 7.712 | 7.638 | −0.074 | mieux |
| global | **biais>63** | −28.47 | −29.57 | **−1.11** | ⚠ pire |
| global | MAE>63 | 29.09 | 29.92 | +0.83 | pire |
| bas | R² | 0.5868 | 0.5911 | +0.0042 | mieux |
| bas | **biais>63** | −26.51 | −27.48 | **−0.97** | ⚠ pire |
| bas | MAE>63 | 27.20 | 27.85 | +0.65 | pire |
| bas | PR-AUC tronçon | 0.4687 | 0.4717 | +0.0030 | ≈ (bruit) |
| bas | PR-AUC tour | 0.5531 | 0.5564 | +0.0034 | ≈ (bruit) |
| **haut** | R² | 0.4334 | 0.4388 | +0.0054 | mieux |
| **haut** | **biais>63** | −42.27 | −44.30 | **−2.04** | ⚠ pire |
| **haut** | MAE>63 | 42.40 | 44.54 | +2.14 | pire |
| **haut** | **PR-AUC tronçon** | 0.3452 | 0.3384 | **−0.0068** | ⚠ en baisse |
| **haut** | **PR-AUC tour** | 0.3459 | 0.3369 | **−0.0090** | ⚠ en baisse |

## Verdict (selon le critère pré-posé)

**NON-ADOPTION — conserver CF09.** best-R² **dégrade matériellement** plusieurs métriques
clés sur H25 :
- **biais>63 plus négatif sur TOUS les segments** (BAS −0.97, HAUT **−2.04**, global −1.11) :
  sous-prédiction de la zone de surcharge **aggravée**, avec MAE>63 dégradée partout.
- **PR-AUC HAUT en baisse, tronçon (−0.0068) ET tour (−0.0090)** : sur l'objectif même
  (séparabilité HAUT), best-R² fait **pire** que CF09.

Le seul gain est un **+0.004 de R² global** — réel et qui généralise (contrairement à k=2),
mais obtenu en ajustant mieux la **masse** au détriment de la **zone >63** (biais, MAE>63) et
de la **séparabilité HAUT**. Tension R²/classe rare déjà documentée (ADR-31/32). Le critère
n'est pas rempli.

## Le mirage H24→H25 (anti-k=2)

| segment | ΔR² H24 → H25 | ΔPR-AUC tronçon H24 → H25 |
|---|---|---|
| bas | +0.0201 → +0.0042 | +0.0191 → +0.0030 |
| **haut** | +0.0166 → +0.0054 | **+0.0426 → −0.0068** |

Le saut **PR-AUC HAUT +0.043** de validation **s'inverse sur H25 (−0.007)** — exactement le
schéma redouté (cf. k=2). C'était du **bruit de segment** (HAUT ≈ 600 / 1 200 surcharges,
instable), pas un gain réel. Les gains de R² s'atténuent (≈ ⅕–⅓ retenu) mais restent positifs.

## Conclusion

CF09 (HP partagés) **conservé** comme référence canonique. Le passage à des HP différenciés
par segment « best-R² » n'apporte qu'un micro-gain de R² global, **au prix d'une dégradation
de la zone >63 et de la PR-AUC HAUT** — non conforme au critère d'adoption. Cohérent avec la
conclusion triangulée (perte, features, HP) : le plafond HAUT est intrinsèque au signal, et
optimiser le R² global se fait contre l'objectif classe-rare.

**ARRÊT** : table H25 + verdict produits. **Pas de re-figement** (le canonique `416bb90b`
reste la référence) — toute adoption serait une étape séparée et explicite. Décision conjointe.
