---
id: ADR-030
ancien_id: ADR-31
date_decision: 2026-05-28
statut: amendé
amende_par: [ADR-031]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-030 — Révision de la stratégie de modélisation suite au découplage R²/rappel sur la classe surcharge

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-031.
> **Précision au gel.** Le levier L3 retenu ici (classifieur binaire dédié) **a été évalué** — ADR-031 §2.4 en rapporte les résultats sur H24 — puis écarté. Le mémoire (§4.6.2) présente le classifieur direct comme non évalué : la formulation vise le classifieur appliqué à l'architecture et au périmètre finaux, non ce levier exploratoire.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-28 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `notebooks/05_evaluation_modele_h24.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM 94), ADR-027 (split temporel) |

## 1. Contexte

Le modèle de référence est un régresseur XGBoost prédisant `target_voyageurs_2eme_classe`, optimisé sur le R² (cf. configuration Dataiku). L'objectif opérationnel réel est la détection des surcharges (`target >= 94`, ADR-005) pour déclencher la recommandation UM.

L'évaluation orientée décision conduite sur le test set H24 (notebook 05) révèle un **découplage critique** entre la performance de régression et la performance décisionnelle.

## 2. Constat empirique

### 2.1 Performance de régression honorable

| Scope | R² | RMSE | MAE | WMAPE |
|---|---|---|---|---|
| Global | 0.613 | 11.06 | 7.19 | 0.360 |
| Segment bas | 0.578 | 11.56 | 7.79 | 0.327 |
| Segment haut | 0.361 | 9.42 | 5.42 | 0.635 |

Le R² global de 0.613 est cohérent avec la littérature de prédiction de fréquentation à court terme et pourrait, isolément, suggérer un modèle exploitable.

### 2.2 Échec décisionnel sur la classe surcharge

Au seuil physique de 94 (ADR-005), la performance de détection est quasi nulle :

| Indicateur | Valeur |
|---|---|
| Surcharges réelles (H24) | 983 |
| Surcharges détectées (TP) | 12 |
| Surcharges ratées (FN) | 971 (98.8 %) |
| Rappel | 1.2 % |
| Précision | 85.7 % |
| F2-score | 0.015 |

Le modèle détecte 12 surcharges sur 983. **Il échoue sur sa cible opérationnelle.**

### 2.3 Biais conditionnel : écrasement de la queue haute

L'erreur moyenne de prédiction par tranche de charge réelle montre une sous-estimation croissante et sévère :

| Tranche réelle | n | Erreur moyenne (préd − réel) | Prédiction moyenne |
|---|---|---|---|
| [0–80[ | 332 653 | −2.2 | 17.1 |
| [80–94[ | 2 073 | −39.2 | 46.4 |
| [94–110[ | 735 | −47.2 | 52.7 |
| [110–150[ | 237 | −71.5 | 47.2 |
| [150+[ | 11 | −119.2 | 47.2 |

Le modèle plafonne ses prédictions autour de 47–53 voyageurs quelle que soit l'ampleur réelle de la surcharge. Les pics extrêmes (charge réelle > 150) sont prédits au même niveau que des charges modérées.

### 2.4 Insuffisance du calibrage de seuil seul

L'abaissement du seuil de déclenchement appliqué à la prédiction (couche de décision, ADR-003) ne résout pas le problème, car le modèle a appris à ne pas prédire haut :

| Seuil de déclenchement | Rappel | Précision | FN | FP |
|---|---|---|---|---|
| 94 (naïf) | 1.2 % | 85.7 % | 971 | 2 |
| 75 | 21.1 % | 63.7 % | 776 | 118 |
| 65 | 30.1 % | 33.4 % | 687 | 591 |
| 55 | 40.9 % | 15.4 % | 581 | 2 202 |

Même au seuil de déclenchement le plus agressif testé (55), le rappel plafonne à 40.9 % au prix de 2 202 faux positifs. **Les cibles de rappel 90 % et 95 % sont inatteignables avec ce modèle.**

## 3. Diagnostic de cause racine

Le découplage s'explique par deux mécanismes conjugués, indépendants de la qualité du feature engineering.

### 3.1 Déséquilibre extrême de la cible (341:1)

La proportion de surcharges réelles sur H24 est de 983 / 335 709 = 0.29 %, soit un déséquilibre de **341:1**, nettement supérieur à l'estimation initiale de ~50:1 (ADR-005). Par segment : 0.35 % (bas) et 0.12 % (haut).

### 3.2 Inadéquation entre fonction objectif et objectif métier

L'optimisation du RMSE (ou R²) sur une cible à 341:1 conduit mécaniquement le modèle à minimiser l'erreur sur la masse des observations normales (99.7 %) au détriment de la classe rare. Mathématiquement, ignorer les 983 surcharges optimise le RMSE global. Le modèle adopte un comportement de régression vers la moyenne conditionnelle, écrasant la queue haute.

**Le problème n'est pas le modèle ni les features, mais la formulation : une décision binaire portant sur une classe rare a été traitée comme une régression optimisée sur l'erreur moyenne.**

## 4. Décision

**Réviser la stratégie de modélisation vers une formulation explicitement orientée vers la détection de la classe rare**, conformément à la nature binaire de la décision UM (ADR-003, ADR-005).

Cette révision est une itération CRISP-ML(Q) : la phase d'Évaluation invalide la formulation de la phase de Modélisation et impose un retour amont. La cible métier (`target_voyageurs_2eme_classe`, ADR-001) et le seuil (94, ADR-005) sont conservés ; seule la formulation d'apprentissage est révisée.

## 5. Leviers évalués

Trois leviers sont retenus pour test empirique, par ordre de priorité méthodologique :

| Levier | Principe | Avantage | Limite |
|---|---|---|---|
| **L1 — Pondération agressive** | Sample weights forts sur la classe surcharge dans le régresseur XGBoost | Rapide, reste dans le régresseur existant, testable en Visual ML | Pansement sur une formulation inadaptée ; risque d'explosion des FP |
| **L2 — Objective asymétrique** | Quantile loss (q≈0.9) au lieu de RMSE | Relève structurellement les prédictions vers le haut de la distribution conditionnelle | Change l'interprétation de la sortie (quantile, non espérance) |
| **L3 — Classifieur binaire dédié** | Reformuler en classification `surcharge ∈ {0,1}` avec `scale_pos_weight` ≈ ratio de déséquilibre | Aligné avec la décision binaire réelle (ADR-003/04) ; XGBoost gère nativement le déséquilibre | Perd l'estimation de l'ampleur de la charge ; nécessite un nouveau pipeline d'évaluation |

**Note** : un modèle à deux étages (classifieur de détection + régresseur d'ampleur conditionnel) est envisageable comme synthèse de L2 et L3, à évaluer si L3 seul donne un rappel satisfaisant mais une information d'ampleur insuffisante pour la couche de décision.

## 6. Critères de décision entre leviers

Le levier retenu sera celui qui maximise le **rappel sur la classe surcharge à un niveau de faux positifs acceptable**, évalué sur le test set H24, puis ventilé par segment. Les métriques de décision (rappel, précision, F2) priment sur les métriques de régression (R², RMSE).

**Dépendance ouverte (à résoudre avec MOB)** : le niveau acceptable de faux positifs dépend du coût relatif d'une UM inutile (faux positif) versus une surcharge ratée (faux négatif). Cet arbitrage doit être obtenu auprès du Responsable de production, MOB avant la calibration finale du seuil de décision. Sans cet ancrage, le compromis rappel/précision est calibré à l'aveugle.

## 7. Conséquences

- **Phase de modélisation** : un nouveau cycle d'entraînement est requis (pondération, objective, ou classifieur). Les résultats seront documentés dans un ADR de suivi ou en addendum à celui-ci.
- **Couche de décision (ADR-003)** : le calibrage du seuil de déclenchement reste pertinent mais subordonné à une formulation d'apprentissage corrigée — il ne peut compenser seul l'écrasement de la queue haute.
- **Évaluation** : le notebook 05 devient le protocole d'évaluation de référence pour comparer les leviers (mêmes métriques, même split H24).
- **Cible et seuil** : inchangés (ADR-001, ADR-005).
- **Contribution au mémoire** : ce découplage R²/rappel constitue un résultat méthodologique central — il démontre empiriquement l'insuffisance d'une évaluation par R² seul pour un problème de détection de classe rare, et justifie une approche orientée décision conforme au cadre DSR.

## 8. Alternatives considérées et écartées (à ce stade)

| Alternative | Raison du report |
|---|---|
| Conserver le régresseur RMSE + calibrage de seuil seul | Empiriquement insuffisant : rappel plafonné à 40.9 % même au seuil 55 (§2.4) |
| Rééchantillonnage synthétique (SMOGN, SMOTE-R) | Plus complexe à implémenter proprement dans Dataiku ; reporté après test de L1–L3 |
| Abaisser le seuil de capacité sous 94 | Rejeté : 94 est une caractéristique technique du SURF 7500 (ADR-005), non un paramètre ajustable |

## 9. Références

- Notebook `notebooks/05_evaluation_modele_h24.ipynb` — constat empirique complet, 7 figures dans `notebooks/figures/05/`
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — architecture à deux couches (prédictive + décision)
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM = 94 (capacité assise 2ème classe SURF 7500)
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22-H23 / H24

## Amendement 2026-07-09 — Correction d'attribution d'interlocuteur

Les mentions d'origine de cet ADR attribuaient l'arbitrage du coût faux positifs / faux négatifs et les validations opérationnelles associées à une autre personne (le référent superviseur du projet côté MOB). L'interlocuteur réel de cet arbitrage et de ces validations était le **Responsable de production, MOB**. La correction porte uniquement sur l'**identité de l'interlocuteur** : le contenu de l'arbitrage, les valeurs et les décisions retenues demeurent inchangés. Correction découverte lors de la passe d'anonymisation et tracée ici.
