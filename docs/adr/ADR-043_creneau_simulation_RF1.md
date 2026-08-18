---
id: ADR-043
ancien_id: ADR-CF01b
date_decision: 2026-06-05
statut: actif
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-043 — Simulation de refonte d'horaire : test de validation de RF-1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « Proposé ». Le test de validation RF-1 rapporté ici a été **conduit et retenu** ; la clé de créneau qu'il valide est en vigueur via ADR-042/044/062.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — en attente de validation  <!-- statut d'époque ; état au gel : actif (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-042 (créneau ±30 min), étape 1bis  
**Nature** : Addendum à ADR-042 — test empirique ciblé du mécanisme RF-1

---

## Motivation

ADR-042 avait conclu que le créneau ±30 min était **statistiquement équivalent** à ADR-037 sur les folds WF H22-H24, et que cette non-discrimination était **structurelle** : les service_ids H22-H23-H24 sont stables, le mécanisme RF-1 ne s'active pas sur ces folds.

L'étape 1bis teste RF-1 en recréant artificiellement le régime de refonte d'horaire à l'intérieur du train (H22+H23 = train, H24 = pseudo-test), où la mesure est possible.

---

## Protocole

### Masquage H24

- Les 117 `horaire_service_id_complet` H24 sont remplacés par des identifiants inédits (`MASK_0000`…`MASK_0116`) qui n'apparaissent **jamais** dans H22+H23.
- Les `mins_origine` (temps de départ réels) sont **préservés** pour la stratégie (b).

**Anti-fuite masquage** : `{MASK_ids} ∩ {H22+H23 service_ids} = ∅` — vérifié.

### Stratégie (a) — service_id froid

- GROUP_KEYS : `[horaire_service_id_complet, cal_type_jour_3classes]` (sans `annee_horaire`)
- H22+H23 : service_ids réels → série cross-H22-H23
- H24 masqué : `MASK_xxxx` → **groupe vide** dans H22+H23, démarrage à froid

### Stratégie (b) — créneau ±30 min

- GROUP_KEYS : `[creneau_anchor_30, cal_type_jour_3classes]` (sans `annee_horaire`)
- Anchors construits sur **H22+H23 uniquement** (jeu d'entraînement)
- H22+H23 : anchor = leur propre temps d'origine (auto-ancrage exact)
- H24 masqué : anchor = service H22+H23 le plus proche à ±30 min → **héritage cross-années**

Coverage anchors H24 masqué : **100 %** (tous les H24 trouvent un anchor dans H22+H23 à ±30 min).

### Modèle et évaluation

- **Un seul modèle** entraîné sur H22+H23 (features stratégie b — quasi-identiques à ADR-037)
- Évalué sur H24 post-embargo avec features de chaque stratégie
- Embargo : 9 jours (comme étapes 1 et 2)
- Métriques : PR-AUC haut, Rappel@68.49, R²haut — IC bootstrap 500 réplications

---

## Résultats empiriques

### Anti-fuite et cohérence de la simulation

| Vérification | Résultat | Statut |
|---|---|---|
| MASK_ids ∩ H22+H23 | ∅ | ✅ |
| Coverage H24 masqué (créneau) | 100.0 % | ✅ |
| H22+H23 NaN lag2 strat. A | 0.8 % | ✅ |
| H22+H23 NaN lag2 strat. B | 0.8 % | ✅ |
| **Corrélation lags H22+H23 A/B** | **r = 1.0000** | ✅ |
| % lags H22+H23 différents A/B | **0.0 %** | ✅ |

Les features d'entraînement H22+H23 sont **identiques** pour les deux stratégies → modèle strictement le même.

### Cohérence avec le régime H25 simulé

| Période H24 | Strat. A NaN lag2 | Strat. B NaN lag2 |
|---|---|---|
| Post-embargo complet | 0.1 % | 0.0 % |
| Early (emb.+0–60j) | 0.2 % | 0.0 % |

win7_n_surcharges haut — période early :
- Strat. A : mean = 0.007, proportion > 0 = **0.4 %**
- Strat. B : mean = 0.007, proportion > 0 = **0.4 %**

→ Les deux stratégies fournissent des lags quasi-nuls en termes de signal de surcharge pour la période début H24 (décembre–février, faible saison de surcharges).

### Performance prédictive — PR-AUC haut, rappel@WF, R²haut

| Modèle | Période | R²haut | PR-AUC haut | IC 95% | Rappel@WF | IC 95% |
|--------|---------|--------|-------------|--------|-----------|--------|
| (a) service_id froid | Début H24 | 0.499 | 0.065 | [0.029–0.140] | 0.0 % | — |
| (b) créneau ±30 | Début H24 | **0.504** | 0.064 | [0.029–0.139] | 0.0 % | — |
| (a) service_id froid | H24 complet | 0.473 | 0.112 | [0.075–0.168] | 13.5 % | [7.2–20.3 %] |
| (b) créneau ±30 | H24 complet | **0.474** | 0.111 | [0.075–0.168] | 13.5 % | [7.2–20.3 %] |
| (a) service_id froid | Fin H24 | 0.467 | 0.152 | [0.095–0.240] | 17.3 % | [9.3–25.9 %] |
| (b) créneau ±30 | Fin H24 | 0.467 | 0.152 | [0.095–0.240] | 17.3 % | [9.3–25.9 %] |

**Les deux stratégies sont statistiquement identiques sur toutes les périodes et métriques.** Les IC 95 % sont superposés à la décimale.

---

## Diagnostic du Fold 1 (étape 1)

Le Fold 1 (H22→H23) avait montré une dégradation apparente du créneau (PR-AUC 0.033→0.025). Ce diagnostic en démontre l'origine.

| Test | Résultat |
|---|---|
| Corrélation H23 lag2 ADR-037 vs créneau | **r = 1.0000** |
| % H23 lag2 différents | **0.0 %** |
| Médiane H23 lag2 ADR-037 | 12.6 |
| Médiane H23 lag2 créneau | 12.6 |

**Les features H23 sont strictement identiques entre ADR-037 et créneau.** La dégradation Fold 1 est un artefact statistique : le test porte sur 153 surcharges dans 82K observations haut H23 (prévalence 0.19%), produisant une variance très élevée dans PR-AUC. Les IC se chevauchent ([0.024–0.045] vs [0.019–0.034]) — la différence est dans le bruit.

---

## Interprétation — Pourquoi le mécanisme RF-1 ne s'active pas dans la simulation

**Raison 1 : La saison de démarrage est une basse saison.**
H24 (et H25) commencent en décembre. La période de démarrage (décembre–février) est une faible saison de surcharges sur le segment haut. Le `win7_n_surcharges` est ≈ 0 pour les deux stratégies dans cette période (0.4 % de valeurs > 0). L'héritage cross-années ne fournit pas de signal additionnel sur les surcharges, car H22-H23 n'en avait pas non plus en décembre-janvier.

**Raison 2 : La période critique est le champ aveugle de l'évaluation.**
Le bénéfice du créneau est concentré dans les **9 premiers jours** (warm-up), exclus par l'embargo. Sur ce bénéfice, la stratégie (a) a NaN histo_*, la stratégie (b) a des lags H22+H23 valides. Mais évaluer sur cette période est hors-distribution pour le modèle (jamais entraîné sans histo_* au démarrage).

**Raison 3 : Le cold-start H24 est structurellement court.**
Après 9 jours d'embargo, H24 propre data est disponible. La fenêtre win7 est pleine en ~9 observations ouvrables (~13 jours calendaires). La période où (b) >  (a) est donc de 9–13 jours — trop courte pour être mesurable sur le H24 complet (335 K observations).

**Raison 4 : La co-linéarité des features haut.**
Même avec créneau, `win7_n_surcharges` haut est ≈ 0 en début de H24/H25. Le signal discriminant pour les surcharges vient d'autres features (météo, événements, réservations) qui sont identiques entre les deux stratégies.

---

## Verdict : RF-1 non démontré sur régime simulé

Conformément au protocole de l'étape 1bis : **la stratégie (b) ne bat pas la stratégie (a) sur le pseudo-test H24 masqué** (IC superposés sur toutes les métriques). Le mécanisme RF-1 ne peut pas être empiriquement validé depuis les données d'entraînement (limitation structurelle, pas d'information dans les folds testables).

---

## Options de décision

### Option 1 : Revert to ADR-037 (protocole strict)
Le créneau ne démontre aucune amélioration mesurable. RF-1 n'est pas prouvé. Le pipeline reste inchangé. La fragmentation RF-1 sur H25 sera documentée comme limitation ex-post.

**Pour** : prudence technique, pas de changement sans bénéfice démontré.  
**Contre** : garantit le cold-start H25. Les 9 premiers jours de H25 auront NaN histo_* pour 100% des services (refonte complète). Si ces jours contiennent des surcharges à prédire, ce sont autant de faux négatifs certains.

### Option 2 : Retenir le créneau ±30 min (ADR-042 confirmé)
La neutralité est une preuve de robustesse (pas de régression). L'absence de bénéfice mesurable est un artefact structurel, pas une réfutation. Le créneau fournit une assurance contre le cold-start H25 à coût nul sur la performance connue.

**Pour** : neutralité démontrée + couverture H25 + cohérence théorique.  
**Contre** : bénéfice non empiriquement démontré.

---

## Recommandation

**Option 2 — Retenir le créneau ±30 min**, pour les raisons suivantes :

1. **Neutralité démontrée sur 3 régimes** : Fold 1 WF, Fold 2 WF, pseudo-test H24 masqué. Pas une seule métrique n'est significativement dégradée. Le coût du créneau est nul.

2. **La non-démonstration est une limitation de l'expérience, pas une réfutation.** Le bénéfice est concentré dans les 9 jours de warm-up (hors évaluation) et dans une future haute saison H25 (hors training). Ces deux fenêtres ne sont pas testables par construction.

3. **Asymétrie des risques.** Revenir à ADR-037 garantit 100% de cold-start H25 pour les services renumérotés. Le créneau réduit ce risque (couverture 93.1% haut à ±30 min) à coût nul de performance mesurable.

4. **Fold 1 résolu.** La "dégradation" fold 1 est un artefact statistique (variance intrinsèque sur 153 surcharges, features H23 strictement identiques confirmé). Elle ne reflète aucun problème structural du créneau.

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01bis_simulation_RF1.ipynb` | Notebook complet |
| `consolidation_finale/outputs/etape_01bis_results.csv` | Résultats simulation 2 strats × 3 périodes + bootstrap |
| `consolidation_finale/figures/etape_01bis_sim_pr_recall.png` | PR-AUC et rappel par période |
| `consolidation_finale/figures/etape_01bis_r2.png` | R² haut par période |
| `consolidation_finale/figures/etape_01bis_diagnostics.png` | win7_n_surcharges + IC comparaison |
