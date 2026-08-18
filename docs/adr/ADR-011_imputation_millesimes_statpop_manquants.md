---
id: ADR-011
ancien_id: ADR-11
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-063]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-011 — Imputation des millésimes STATPOP manquants (2021, 2023)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée — sous réserve de validation empirique (test de sensibilité) |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **ADR liés** | ADR-002 (split temporel), ADR-022 (disponibilité J-1), ADR-006 (dernier millésime disponible) |

## Contexte

Les fichiers STATPOP 2021 et 2023 publiés par l'OFS ne contiennent pas les données
sur les ménages (HP\*) ni les indicateurs de qualité HPI. Sur la période d'étude
(2015–2024), ces deux millésimes sont structurellement incomplets pour 13 variables.

Compte tenu de la stratégie de split (ADR-002), seul le millésime 2023 affecte
directement le train set (H22–H23). Le millésime 2021 tombe dans la période COVID
(traitée séparément) mais est conservé dans le pipeline pour préserver la cohérence
historique de la table `statpop_clean`.

## Décision

**Stratégie retenue : interpolation linéaire entre millésimes adjacents.**

Pour les variables continues (`INTERPOLATION_COLUMNS`) :
- 2021 = moyenne arithmétique de 2020 et 2022 (2021 équidistant → interpolation exacte)
- 2023 = moyenne arithmétique de 2022 et 2024 (même logique)

Pour les indicateurs catégoriels (`IMPUTATION_MAX_COLUMNS` : `hpi_classe_max_500m`,
`flag_qualite_statpop_faible`) : imputation par le **maximum** des deux millésimes
adjacents, quelle que soit la stratégie principale. Justification : ces variables sont
ordinales/binaires ; une interpolation linéaire produirait une valeur intermédiaire sans
sens sémantique (ex. flag = 0.5). Le principe de précaution s'impose : si l'une des
années voisines signale une qualité dégradée, l'année interpolée hérite de ce signal.

## Justification

- Les variables STATPOP retenues sont **structurellement lentes** : la population totale
  dans les buffers 500 m n'a progressé que de +9,5 % sur 10 ans. L'hypothèse de
  linéarité sur deux ans est raisonnable.
- Le millésime concerné (2023) se situe dans un régime post-COVID stabilisé, sans
  choc démographique conjoncturel identifié.
- L'interpolation est réalisée **entre deux valeurs observées**, sans extrapolation.
  `pandas.interpolate(method='index')` garantit cette propriété.
- Pratique standard en analyse spatiale pour les données de registres administratifs
  à publication annuelle (Cromley & McLafferty, 2011 ; Fotheringham et al., 2000).

## Stratégies alternatives exposées

Le script `build_fact_statpop_gare.py` expose trois variantes via `--strategy` :

| Stratégie | Description | Usage |
|---|---|---|
| `interpolate` | Interpolation linéaire (défaut) | Configuration retenue en production |
| `carry_forward` | LOCF — dernière valeur observée reportée | Référence causale stricte (impute avec données disponibles *avant* la période) |
| `none` | Pas d'imputation — NA conservés | Baseline pour quantifier l'impact de l'imputation |

## Test de sensibilité

Un test empirique est réalisé en phase de modélisation (section 4.x du mémoire) :
trois entraînements du modèle de référence sont comparés avec les trois variantes.

**Critère de validation** : l'écart de R² entre les variantes reste < 0.01 sur le
test set H24. Si tel est le cas, la stratégie retenue est confirmée. Si l'écart est
significatif, la stratégie `carry_forward` est privilégiée pour sa rigueur causale.

## Conséquences

- `build_fact_statpop_gare.py` implémente `impute_missing_millesimes()` avec le
  paramètre `strategy`. La stratégie par défaut est `"interpolate"`.
- La table `statpop_clean.parquet` ne contient plus aucun NA sur les colonnes cibles
  (sauf pour les millésimes hors de la plage d'interpolation).
- Les variables ménages et HPI sont intégrées dans le `ml_dataset` via
  `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (`STATPOP_KEEP_SUFFIXES`).
- Pour les tests de sensibilité, renommer la sortie :
  `statpop_clean_{strategy}.parquet` avant de rejouer la pipeline.
