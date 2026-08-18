# CHANTIER PERTE — Phase 4 : pertes pondérées A (cloche) vs B (rampe à paliers)

**Statut : balayage + comparaison réalisés (validation H24). ARRÊT — aucune config choisie,
aucun réentraînement.** Hors canonique (`exp_perte/`), hash `416bb90b` intact (lecture seule),
aucun modèle sauvegardé, **H25 jamais chargé**, rien dans le rapport.

## Forme commune & grilles
Perte = w(obs)·½·a·r², r = pred−obs, a = k si r<0 sinon 1 (grad g=w·a·r, hess h=w·a).
- **Forme A (cloche)** : w_A = exp(−(obs−63)²/(2σ²)), σ∈{5,10,20}, k∈{1,2,3,5}.
- **Forme B (rampe, suggestion directeur)** : w_B = 1 si obs<63 ; W1 si 63≤obs≤94 ; W2 si obs>94.
  (W1,W2)∈{(2,4),(3,6),(5,10),(10,20)}, k∈{1,2,3,5}.

## Garde-fous (corrigés)
- **Implémentation bit-exact** : `w≡1, k=1` reproduit `reg:squarederror` à **max|Δ|=0,00** (BAS & HAUT),
  idem **B W1=W2=1** → la machinerie custom (poids × asymétrie) est **exacte**.
- **Limite plate Forme A** : σ=1e7 → max|Δ|=0,00 → w_A→MSE quand σ→∞ ✓.
- **Note importante** : σ=1000 n'est **PAS** un contrôle MSE bit-exact — w_A(σ=1000) sous-pondère
  encore le **tail surcharge de ~3 %**, ce qui décale les prédictions extrêmes (max|Δ|≈40). C'est
  attendu (w_A jamais strictement plat), **pas un bug** ; la preuve d'implémentation est `w≡1`.

## Résultats clés (validation H24, global ; >63 = 9 537 tronçons, >94 = 919)

| config | biais>63 | band56-70 | biais>94 | biais≤63 | MAEg | R² | PR-AUC tr | PR-AUC tour |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **baseline MSE** | −29,13 | −19,93 | −49,40 | −1,58 | 6,818 | 0,6586 | 0,4759 | 0,5903 |
| A best (σ5 k5) | −14,38 | **−0,38** | −42,21 | **+38,29** | **37,6** | **−4,11** | 0,3616 | 0,4867 |
| B best (W10-20 k5) | −14,84 | −6,08 | **−36,08** | +4,84 | 8,435 | 0,5523 | 0,4748 | 0,5908 |
| P1 sample_weight (best) | −18,67 | — | — | — | 7,155 | 0,6469 | 0,5009 | 0,6168 |
| P2 MSE asym (best) | −14,62 | — | — | +6,47 | 9,002 | 0,5414 | 0,5022 | 0,6142 |
| **B(2,4) k1** (Pareto doux) | −25,11 | −17,02 | −43,32 | −1,17 | **6,775** | **0,6712** | 0,4958 | — |
| **B(2,4) k2** | −22,14 | −13,85 | −41,54 | +0,71 | **6,742** | **0,6848** | 0,4946 | — |

## Réponses aux 3 questions

**Q1 — Cibler le seuil (A) ou le seuil+au-delà (B) réduit-il le biais>63 MIEUX que l'asymétrie
uniforme (P1/P2) ? → NON, pareil.** À réduction de biais>63 comparable (~−14,6 à −14,8), B(W10-20,k5)
(R²=0,552, PR-AUC tr 0,475) et P2 asym uniforme (R²=0,541, PR-AUC tr 0,502) sont **équivalents**. Le
biais>63 s'achète au **même taux de change** contre le R², **quel que soit l'endroit** où l'on pondère.
Cibler la zone n'apporte pas de meilleur compromis que l'asymétrie uniforme.

**Q2 — A et B diffèrent-elles ? → OUI, radicalement ; B ≫ A.**
- **Forme A est un désastre de calibration** : ses poids ∈[0,1] **annulent la masse** (w≈0 pour obs petit)
  → le modèle **sur-prédit tout** (biais≤63 = **+38** à σ5 !), R² **négatif** (−4,1), MAE globale 37.
  Elle centre bien la bande ambiguë (band56-70≈0) mais **détruit le reste**. Inutilisable.
- **Forme B se comporte bien** : poids≥1, masse préservée, dégradation **monotone et contrôlée**. À
  faible (W,k), B est même un **léger Pareto** sur H24 : B(2,4)k2 → R² 0,685 / MAE 6,74 / PR-AUC tr 0,495
  **mieux que la baseline** tout en réduisant biais>63 de ~7.
- **Le palier W2 (>94) de B aide la zone sévère** : biais>94 passe de **−49,4 → −36,1** (B fort), la
  **meilleure** amélioration de toutes les formes (A reste à −42/−47). **C'est le seul avantage
  distinctif** du design directeur : viser explicitement >94 réduit le mieux la sous-prédiction sévère.

**Q3 — La PR-AUC bouge-t-elle ? → NON, plateau (4ᵉ confirmation).** PR-AUC tronçon reste 0,47-0,53
(baseline 0,476), PR-AUC tour ~0,59 plat — **comme Phases 1-2 et les chantiers HP/features**. La
pondération **déplace le point de fonctionnement (biais↓)** mais **ne relève pas le plafond de
séparabilité**.

## Distribution autour du seuil (« trou au seuil » ?)
**Aucun trou** : baseline et B décroissent normalement autour de 63 (pas de creux ; B pousse un peu de
masse vers le haut, monotone). Forme A crée au contraire un **empilement artificiel** en [60,63)
(52 429 préds) — symptôme de la dé-calibration, pas un évitement du seuil. Figure :
`distribution_seuil63_h24.png`.

## Conclusion (validation H24)
1. **Forme B ≫ Forme A.** Une cloche à poids ∈[0,1] centrée sur 63 **annule la masse** et dé-calibre le
   modèle (R²<0). La rampe à paliers (poids≥1) préserve la calibration et dégrade proprement.
2. **Cibler le seuil n'est pas meilleur que l'asymétrie uniforme** pour réduire le biais>63 : même
   frontière biais/R². L'**unique gain propre** au design B est sur la **zone sévère >94** (palier W2 :
   biais −49→−36).
3. **La PR-AUC ne bouge pas** (4ᵉ levier confirmant le plateau de séparabilité = propriété du signal,
   ADR-CF25/CF26/CF27). Toute réduction de biais reste un **réglage de point de fonctionnement** (couche 2),
   pas un relèvement de plafond (couche 1).

→ **Cohérent avec ADR-CF25 (perte MSE conservée).** Si jamais la réduction du biais sévère >94 devenait
un objectif explicite, le **palier W2 de B** serait l'outil le plus ciblé — mais cela relève d'un réglage
opérationnel de couche 2, pas d'un changement de perte canonique.

**ARRÊT** : table comparative produite. Aucune config choisie, aucun réentraînement. Décision conjointe.

## Traçabilité
`consolidation_finale/exp_perte/balayage_pertes_ponderees_h24.py` / `.csv` / `.json`,
`distribution_seuil63_h24.png`. Garde-fous : impl `w≡1` & `B(1,1)` bit-exact, limite `w_A(σ=1e7)`≈MSE.
Comparaison aux Phases 1-2 (`balayage_sample_weight_h24.json`, `balayage_mse_asym_h24.json`). Hash
`416bb90b` intact. Aucune écriture pipeline/rapport/dataset.
