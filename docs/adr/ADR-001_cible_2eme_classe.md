---
id: ADR-001
ancien_id: ADR-01
date_decision: 2026-05
statut: amendé
amende_par: [ADR-060]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-001 — Changement de cible : `charge_totale` → `target_voyageurs_2eme_classe`

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |

## Contexte

Le proposal validé (Nedellec, 2026) et la première itération du notebook `01_business_understanding` retenaient `charge_totale = voyageurs_1ere_classe + voyageurs_2eme_classe` comme cible ML, avec un seuil de surcharge défini sur la capacité totale de la rame (106 places assises, SURF 7500 simple).

L'analyse conduite en `02_data_understanding_apc` §2.1.1 a comparé les deux définitions de surcharge sur la population H17–H24 :

| Définition | Seuil | Surcharges détectées | Note |
|---|---|---|---|
| `target_voyageurs_total > SEUIL_TOTAL` | 106 | référence | capacité totale SURF 7500 |
| `target_voyageurs_2eme_classe >= SEUIL_UM_2C` | 94 | +56 % capturées en plus | capacité assise 2ème classe |

## Décision

**Cible retenue : `target_voyageurs_2eme_classe`** comparée au seuil `SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500 = 94` (capacité assise 2ème classe d'une rame SURF 7500 simple).

Formulation officielle : "La cible prédictive retenue est `target_voyageurs_2eme_classe`, qui représente la charge observée en 2ème classe sur un tronçon donné, pour une course et une date données. Ce choix est justifié par l'analyse des données APC et par le contexte opérationnel : les situations de saturation concernent principalement la 2ème classe, tandis que la 1ère classe constitue rarement le facteur déclencheur d'une décision UM."

Justification double :
1. **Data-driven** : `target_voyageurs_2eme_classe >= 94` capture +56 % de surcharges réelles supplémentaires vs `target_voyageurs_total > 106`, parce que la 1ère classe (12 places, moy = 1 voy, P99 = 7) n'est jamais le facteur limitant.
2. **Qualitatif** : 5/6 participants aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent la saturation sur la capacité assise 2ème classe, pas sur la capacité totale.

`target_voyageurs_total` reste calculé dans le pipeline pour l'audit et la vérification d'intégrité, mais n'est pas la cible ML.

## Conséquences

- **Architecture** : la couche de décision (Étape 2) utilise `recommandation_um_seuil_2c = prediction_voyageurs_2eme_classe >= SEUIL_UM_2C`.
- **Métriques** : les métriques de régression (MAE, WMAPE, R²) portent sur `target_voyageurs_2eme_classe`.
- **Baselines** : toutes les baselines sont recalculées sur cette cible.
- **Pipeline** : `target_voyageurs_2eme_classe` est présente dans la table depuis `apc_stacked.parquet` — aucun changement de pipeline requis.
- **Seuil** : lié à ADR-005 (ancrage de `SEUIL_UM_2C = 94`, capacité assise 2ème classe SURF 7500).
- **Contrôle qualité** : `target_voyageurs_total` reste calculé dans le pipeline (`add_features_to_raw_stacked.py`) pour l'audit et la vérification d'intégrité, mais n'est pas la cible ML.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `target_voyageurs_total > 106` | Manque ~56 % des surcharges réelles ; la 1ère classe n'est jamais limitante |
| Régression sur flux montées/descentes par arrêt | Inadapté à la décision UM qui s'appuie sur la charge maximale instantanée |

## Addendum (2026-07-24)

La définition de la cible (charge assise 2e classe, grain date × course × tronçon) demeure active. Le seuil de 94 places mentionné dans le corps est supersédé par ADR-060, qui fixe le seuil canonique de surcharge à strictement plus de 63 places assises. Aucune autre disposition modifiée.
