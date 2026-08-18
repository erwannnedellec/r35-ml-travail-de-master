# CHANTIER FEATURES — Phase C : confirmation H25 de `event_is_vacances_valais`

**Statut : table de généralisation H25 produite. ARRÊT — rien adopté, rien industrialisé.**
Hors canonique (`exp_features/phaseC_confirm_h25.py`). Hash `416bb90b` intact (lecture
seule, contrôlé), aucun stage, `build_ml_dataset.py` non touché, aucun modèle sauvegardé.
**H25 touché une seule fois** pour ce rapport. Rapport de **généralisation seulement** —
pas de sélection, pas d'industrialisation (décision pré-actée, indépendante du résultat).

## Protocole (iso-canonique sauf l'ajout d'1 feature)
- Train **tri-annuel** H22 (Gilamont 8501260 exclu) + H23 + H24 → **test H25** (Split C).
- **CANONIQUE 158f** vs **159f** (158 + `event_is_vacances_valais` **seule**).
- Iso ADR-CF09, seed=42, segmentation BAS/HAUT, seuil 63, `reg:squarederror`.
- n_train = 801 282, n_test H25 = 309 252. Jointure : 0 NaN.

**Garde-fou — PARFAIT.** Le 158f reproduit les `metrics_h25` canoniques (metadata
enrichi_seg) **à la 4ᵉ décimale, Δ = 0.0000** sur R² *et* PR-AUC pour BAS/HAUT/global
(R²g 0.6013, PR-AUC BAS 0.4687/0.5531, HAUT 0.3452/0.3459). Protocole tri-annuel
strictement iso → comparaison propre.

Surcharges >63 en test H25 : BAS 8 392, **HAUT 1 192**, global 9 584.

## Résultats H25 — 158f vs 159f

| segment | métrique | 158f | 159f | Δ H25 | (rappel Δ valid H24) |
|---|---|---|---|---|---|
| **bas** | **PR-AUC tronçon** | 0.4687 | 0.4741 | **+0.0055** | +0.0191 |
| **bas** | **PR-AUC tour** | 0.5531 | 0.5577 | **+0.0047** | +0.0122 |
| bas | R² | 0.5868 | 0.5876 | +0.0007 | |
| bas | MAE>63 | 27.20 | 27.06 | −0.14 | |
| **haut** | **PR-AUC tronçon** | 0.3452 | 0.3646 | **+0.0194** | −0.0022 |
| **haut** | **PR-AUC tour** | 0.3459 | 0.3559 | **+0.0100** | +0.0015 |
| haut | R² | 0.4334 | 0.4428 | +0.0095 | (−0.0119 en H24) |
| haut | MAE>63 | 42.40 | 41.54 | −0.87 | (+1.19 en H24) |
| haut | biais>63 | −42.27 | −41.22 | +1.05 | |
| global | PR-AUC tronçon | 0.4490 | 0.4560 | +0.0070 | |
| global | PR-AUC tour | 0.5635 | 0.5640 | +0.0005 | |
| global | R² | 0.6013 | 0.6034 | +0.0020 | |

**SHAP `event_is_vacances_valais` sur H25** : rang **9/159** en BAS (2.73 %), rang 52/159
en HAUT (0.61 %) — *usage stable* vs H24 (rang 7 BAS / 40 HAUT). La feature est
**utilisée de façon cohérente** par le modèle, surtout en BAS.

## Lecture factuelle

**1. Le gain BAS de validation ne se confirme PAS pleinement — il s'atténue.**
PR-AUC BAS tronçon **+0.0191 (H24) → +0.0055 (H25)** ; tour **+0.0122 → +0.0047**.
Soit ~¼ du gain de validation retenu sur H25. Le gain BAS reste **positif mais sous le
seuil de bruit (0.03)** des deux côtés, et **largement réduit** hors échantillon.

**2. Instabilité de segment — le gain change de segment entre H24 et H25.**
Là où H24 ne montrait rien sur HAUT (PR-AUC −0.002, R² −0.012), **H25 montre un mouvement
HAUT favorable et cohérent** (PR-AUC +0.019/+0.010, R² +0.009, MAE>63 −0.87, biais>63
+1.05). Mais ce signe **contredit la validation H24**. HAUT n'a que 620 (H24) / 1 192
(H25) surcharges → PR-AUC HAUT instable. **Ce retournement est le symptôme de cette
instabilité, pas un gain HAUT démontré** : on ne peut pas conclure à un gain HAUT à partir
d'un unique run H25 qui contredit la validation.

**3. SHAP cohérent, effet métrique petit.** La feature est constamment utilisée (rang ~9
BAS sur H24 et H25), mais son effet sur la PR-AUC reste **< 0.02 partout** et **non stable
dans le segment où il apparaît**.

## Verdict

**Réponse à la question posée :** le micro-gain BAS de validation **ne généralise que
partiellement** (s'atténue à +0.0055 tronçon). L'apparent gain HAUT sur H25 **contredit**
la validation H24 → attribuable à l'instabilité petit-échantillon du HAUT, pas à un effet
robuste. **Aucun gain reproductible ne franchit le seuil d'intérêt (0.03)** ni ne se
stabilise sur un segment.

Conclusion d'ensemble du chantier (A→C) : les features cantonales — y compris le seul
candidat survivant `event_is_vacances_valais` — **ne relèvent pas le plafond HAUT**
(objectif) et n'apportent qu'un effet BAS petit, atténué hors échantillon et instable en
segment. **Rien à adopter.** Conforme à la consigne : pas de sélection, pas
d'industrialisation, pas de stage. Chiffres disponibles pour l'ADR features.

**ARRÊT.**
