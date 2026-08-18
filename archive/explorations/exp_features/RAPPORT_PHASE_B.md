# CHANTIER FEATURES — Phase B : test d'impact des 8 features cantonales

**Statut : test d'impact sur VALIDATION H24 terminé. ARRÊT — rien intégré.**
Hors canonique (`exp_features/phaseB_impact_h24.py`). Hash `416bb90b` intact (lecture
seule, contrôlé en tête de script), aucun stage créé, `build_ml_dataset.py` non touché,
aucun modèle sauvegardé, **H25 jamais chargé** dans train/valid.

## Protocole (iso-tout sauf l'ajout des 8 features)
- **train** = H22 (tronçons Gilamont 8501260 exclus) + H23 → **validation = H24**.
- Perte `reg:squarederror` (ADR-CF25), HP ADR-CF09 (n_est=300, depth=6, lr=0.1,
  subsample/colsample=0.8), **seed=42**, segmentation **BAS/HAUT**, seuil **63**,
  `base_score` = moyenne train du segment.
- **BASELINE 158f** recalculé sur ce protocole bi-annuel (PAS les chiffres canoniques
  tri-annuels H25). **CANDIDAT 166f** = 158 + 8 cantonales, jointes **par date**
  (`base_date`) depuis `features_vacances_feries_cantonales.parquet` en mémoire.
- Jointure : **0 NaN** train/valid (la plage cantonale couvre H22-H24).

**Validation iso-protocole :** le baseline 158f reproduit **à l'identique** le k=1
(reg:squarederror) du chantier perte (`balayage_mse_asym_h24`) — R²glob 0.6586,
PR-AUC HAUT 0.3077/0.3126, biais>63 −43.86. La comparaison est donc propre.

Validation H24 : BAS 251 106 / HAUT 84 603 obs ; surcharges >63 : BAS 8 917, **HAUT 620**.

## Résultats — 158f vs 166f (validation H24)

| segment | métrique | 158f | 166f | Δ |
|---|---|---|---|---|
| **haut** | **PR-AUC tronçon** | 0.3077 | 0.3055 | **−0.0022** |
| **haut** | **PR-AUC tour** | 0.3126 | 0.3141 | **+0.0015** |
| haut | R² | 0.5101 | 0.4983 | −0.0119 |
| haut | MAE>63 | 44.40 | 45.59 | +1.19 |
| haut | biais>63 | −43.86 | −45.27 | −1.41 |
| bas | PR-AUC tronçon | 0.4919 | 0.5110 | +0.0191 |
| bas | PR-AUC tour | 0.5881 | 0.6003 | +0.0122 |
| bas | R² | 0.6170 | 0.6233 | +0.0063 |
| bas | MAE>63 | 28.37 | 27.47 | −0.90 |
| global | PR-AUC tronçon | 0.4759 | 0.4964 | +0.0204 |
| global | PR-AUC tour | 0.5903 | 0.6026 | +0.0124 |
| global | R² | 0.6586 | 0.6620 | +0.0034 |

## SHAP des 8 features (rang /166, % du SHAP total)

| feature | BAS rang | BAS %tot | HAUT rang | HAUT %tot |
|---|---|---|---|---|
| **event_is_vacances_valais** | **7** | **2.35 %** | 40 | 0.66 % |
| event_is_vacances_neuchatel | 28 | 0.86 % | 135 | 0.02 % |
| event_is_vacances_geneve | 75 | 0.25 % | 127 | 0.03 % |
| event_is_vacances_fribourg | 108 | 0.08 % | 81 | 0.26 % |
| event_is_ferie_valais | 116 | 0.05 % | 120 | 0.05 % |
| event_is_ferie_neuchatel | 121 | 0.03 % | 124 | 0.04 % |
| event_is_ferie_geneve | 138 | 0.01 % | 110 | 0.09 % |
| event_is_ferie_fribourg | 132 | 0.02 % | 139 | 0.01 % |

## Lecture (sans optimisme)

**POINT CLÉ — la PR-AUC HAUT ne se relève PAS.** Δ = −0.0022 (tronçon) / +0.0015 (tour),
soit **profondément dans la zone de bruit** (< 0.03 ; HAUT n'a que **620 surcharges** en
validation, très instable — cf. précédent k=2 qui montait puis s'effondrait sur H25). Le
plafond HAUT (~0.31 ici) **n'est pas franchi**. Pire, le R² HAUT **baisse** (−0.012) et la
MAE>63 HAUT se **dégrade** (+1.19) : sur le segment cible, les 8 features sont
**neutres à légèrement négatives** (léger sur-apprentissage de features corrélées).

**Le seul signal réel est `event_is_vacances_valais`** (rang 7/166, 2.35 % du SHAP en
BAS), accessoirement `event_is_vacances_neuchatel`. Il porte une amélioration **modeste
mais crédible sur le segment BAS** (PR-AUC tronçon +0.019, tour +0.012, MAE>63 −0.90 ;
BAS = 8 917 surcharges, bien plus stable que HAUT). Hypothèse confirmée : signal
touristique alpin (vacances VS), **mais sur le mauvais segment** — BAS n'était pas le
goulot.

**Les 4 features `event_is_ferie_*` sont quasi mortes** (rangs 110-139, < 0.1 %) dans les
deux segments. La redondance férié **VS≈FR (r=0.97)** se traduit comme prévu par un SHAP
**partagé et nul** : l'information fériés est déjà captée par `event_is_ferie_vaud` (présent
dans les 158) et les features calendaires. GE/FR vacances : négligeables aussi.

## Verdict & recommandation

**Sur l'objectif (relever la PR-AUC HAUT, plafond ~0.345) : ÉCHEC.** Comme la perte et les
HP avant elles, les features cantonales ne relèvent pas le plafond HAUT. **Ne pas
industrialiser le bloc des 8 features.**

Si un suivi est jugé utile, il se limiterait à **`event_is_vacances_valais` seule** (±NE),
pour le segment BAS — mais c'est hors objectif et le gain PR-AUC reste sous le seuil de
bruit de 0.03. Les 4 `event_is_ferie_*` et les vacances GE/FR/(NE sur HAUT) sont à écarter.

**ARRÊT** : pas de test H25, pas d'intégration, pas de stage. Décision conjointe ensuite
(le seul candidat éventuel à confirmer une fois sur H25 serait `event_is_vacances_valais`
pour le BAS, si l'on juge le micro-gain BAS digne d'intérêt).
