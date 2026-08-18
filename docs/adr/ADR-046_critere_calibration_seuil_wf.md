---
id: ADR-046
ancien_id: ADR-CF03
date_decision: 2026-06-05
statut: révoqué
revoque_par: [ADR-052]
modifie: [ADR-045]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-046 — Critère de calibration du seuil Walk-Forward

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-045.
> **Précision au gel.** Ce document **n'arrête aucun critère** : il se clôt sur une décision requise. Le critère F2 qu'il met en discussion est ensuite mobilisé comme acquis par ADR-047 et ADR-048, sans qu'un ADR ne l'acte — lacune consignée à ADR-078. L'appareil de seuil de couche 1 qu'il instruit est sans objet depuis ADR-052 ; la calibration de seuil en vigueur est celle de la couche 2 (ADR-073, ADR-077).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — **en attente de décision Erwann Nédellec**  <!-- statut d'époque ; état au gel : révoqué (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille factorielle), ADR-036 (seuil opérationnel 68.49)

---

## Contexte

Le pipeline de calibration du seuil WF (Walk-Forward) utilise un critère F-beta pour trouver le seuil optimal
sur les prédictions de charge (segment haut) : pour chaque fold de validation (H23, H24),
on cherche le seuil t* qui maximise F-beta, puis on moyenne les seuils des deux folds.

La session précédente (coupure de contexte) avait documenté dans ADR-045 des seuils WF de
**72.83** (Enrichi) et **76.46** (APC-only). Ces valeurs ne correspondent **ni à F1 ni à F2**.
L'étape 2bis (2026-06-05) a recalculé les seuils avec les deux critères et constaté l'incohérence.

---

## Données du problème

### Seuils WF produits par F1 vs F2 (calculés 2026-06-05)

| Feature set | Critère | Fold1 | Fold2 | **Seuil final** |
|-------------|---------|-------|-------|----------------|
| APC-only    | F1      | 46.35 | 32.41 | **39.38** |
| APC-only    | F2      | 32.03 | 32.41 | **32.22** |
| Enrichi     | F1      | 46.64 | 52.76 | **49.70** |
| Enrichi     | F2      | 46.64 | 50.29 | **48.46** |

Valeurs ADR-045 (session précédente, critère inconnu) : APC=76.46, Enrichi=72.83

### Métriques H25 résultantes — APC_Global et Enrichi_Global

| Cellule | Critère | Seuil | PR-AUC haut | IC 95% | Rappel@WF | Précision@WF |
|---------|---------|-------|-------------|--------|-----------|-------------|
| APC_Global | **F1** | 39.38 | 0.301 | [0.244–0.356] | **53.9 %** | 18.3 % |
| APC_Global | **F2** | 32.22 | 0.301 | [0.244–0.356] | **62.6 %** | 13.1 % |
| Enrichi_Global | **F1** | 49.70 | 0.132 | [0.109–0.164] | **50.8 %** | 15.2 % |
| Enrichi_Global | **F2** | 48.46 | 0.132 | [0.109–0.164] | **52.5 %** | 14.8 % |
| APC_Global | *ADR-045* | *76.46* | *0.301* | *[0.248–0.357]* | *13.8 %* | *~61 %* |
| Enrichi_Global | *ADR-045* | *72.83* | *0.132* | *[0.107–0.165]* | *7.1 %* | *~52 %* |

> **Note** : PR-AUC est indépendant du seuil — il reste identique quelle que soit la calibration.
> Seuls rappel et précision @WF varient.

### Implications opérationnelles estimées

_Labels calculés avec surcharge définie comme target ≥ 94 (offre APC — provisoire, ADR-060 corrige en >63). H25 haut complet : 1 192 surcharges >63 (vs 297 à seuil=94 ci-dessous). Décomptes à recalibrer._

| Critère | Rappel | Surcharges détectées (seuil≥94, provisoire) | Faux positifs estimés |
|---------|--------|---------------------------------------------|-----------------------|
| F1 APC  | 53.9 % | ~160 / 297 | ~730 |
| F2 APC  | 62.6 % | ~186 / 297 | ~1 230 |
| ADR-045 (critère inconnu) | 13.8 % | ~41 / 297 | ~25 |

---

## Question de décision

**Quel critère de calibration retenir pour le seuil WF ?**

### Option A — F1 (beta=1) : équilibre rappel / précision

- **Seuil** : APC≈39, Enrichi≈50
- **Rappel** : ~50-54 % — détecte 1 surcharge sur 2
- **Précision** : ~15-18 % — ~1 alarme justifiée sur 6
- **Argumentaire** : compromis équilibré ; les coûts d'un UM inutile (logistique, coût matériel)
  et d'un surcharge manquée (confort passager, potentiellement image) sont considérés équivalents.

### Option B — F2 (beta=2) : rappel privilégié (asymétrie de coût)

- **Seuil** : APC≈32, Enrichi≈48
- **Rappel** : ~53-63 % — détecte 3 surcharges sur 5
- **Précision** : ~13-15 % — ~1 alarme justifiée sur 7
- **Argumentaire** : manquer une surcharge est structurellement plus coûteux qu'un UM inutile.
  Beta=2 pèse le rappel 4× plus que la précision. Justification DSR : les échanges métier conduits au fil du projet indiquent
  que la surcharge non anticipée génère des plaintes passagers et des arbitrages de composition
  de dernière minute (coût opérationnel indirect).

### Option C — Critère opérationnel à définir (ex. rappel ≥ X % à précision maximale)

- Maximiser la précision sous contrainte de rappel minimum (ex. ≥ 50 %)
- Ou fixer un ratio précision/rappel conforme à la valeur décision UM documentée dans ADR-007

---

## Conséquence sur ADR-045

**Selon la décision :**

- **Si F1 ou F2** : les seuils et métriques rappel de l'ADR-045 seront mis à jour.
  Les résultats clés (PR-AUC haut, classement APC > Enrichi) restent valides — seuls
  les rappel@WF et précision@WF changent.
- Les seuils ADR-045 (72.83 / 76.46) sont invalidés : ils ne correspondent à aucun critère F-beta
  identifiable. Ils seront archivés comme "session précédente, critère inconnu".

---

## Données complémentaires (anti-fuite, à documenter dans notebook)

- **Groupes réels** [base_sens, creneau_anchor_30, cal_type_jour_3classes] : **339** (ADR-045 disait 333 — écart de 6, documenter)
- **Première obs/groupe → lag NaN** : 339/339 (100 %) ✓
- **NaN H25** : 0.0000 % ✓ (anchors construits exclusivement sur H22-H24)
- **Gap H24→H25** : > 2 jours ✓ (lag J-2 garanti)

---

## Décision requise

> Erwann : choisir entre Option A (F1), Option B (F2), ou Option C (critère opérationnel).
> Cette décision détermine les seuils WF qui seront gelés pour l'étape 3
> et figés dans le notebook exécuté final.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_02bis_calibration_seuils.csv` | Seuils Fold1/Fold2/final par (feature_set, critère) |
| `consolidation_finale/outputs/etape_02bis_f1_f2_comparison.csv` | Métriques H25 par (cellule, critère) |
| `consolidation_finale/outputs/etape_02bis_antifuite.json` | Résultats anti-fuite sur clé réelle |
