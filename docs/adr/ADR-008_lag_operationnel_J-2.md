---
id: ADR-008
ancien_id: ADR-08
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-062]
precise_par: [ADR-015]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-008 — Décalage opérationnel J-2 pour les features historiques APC

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-062 ; précisée par ADR-015.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

> **⚠ CORRECTION 2026-06-16 (ADR-062)** — Le lag J-2 défini ci-dessous est **incorrect pour les données APC** (HOP-REP-WEB). La publication APC réelle est mensuelle : le mois M est disponible à partir du 3 de M+1. Le lag réel est min=3 j / médiane=18 j / max=33 j, et non J-2. La constante `LAG_OPERATIONNEL_JOURS = 2` a été remplacée par un **cutoff mensuel** dans le pipeline expérimental (inc1, hash `fe9d6b4d`). Voir ADR-062 pour la décision complète et l'attribution chiffrée. ADR-008 reste valide pour les autres features à lag journalier (ISTDATEN, météo).

| Champ | Valeur |
|---|---|
| **Statut** | Partiellement corrigée — voir ADR-062 |
| **Date** | 2026-05 |
| **Correction** | 2026-06-16 (ADR-062) |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Constante** | `LAG_OPERATIONNEL_JOURS = 2` *(remplacée par cutoff mensuel pour les histo_* APC — cf. ADR-062)* |
| **Remplace** | Comportement implicite `shift(1)` — données J-1 utilisées comme si elles étaient disponibles à J-1 |

## Contexte

Le modèle est conçu pour produire une recommandation UM la veille du jour de circulation (J-1), conformément au processus opérationnel décrit dans ADR-022. La question est : quelle est la **dernière journée APC réellement disponible** au moment de la décision ?

Les comptages APC de la journée J-1 sont consolidés par le système de collecte dans la nuit de J-1 à J. À l'heure où la décision UM doit être prise (en soirée de J-1), ces données **ne sont pas encore disponibles**.

La version initiale du script utilisait un `shift(1)`, qui plaçait les données de J-1 comme input pour prédire J. Cela constitue un **leakage temporel** : en exploitation réelle, ces données n'existent pas encore au moment de la prédiction.

## Décision

**`LAG_OPERATIONNEL_JOURS = 2`**

Toutes les features historiques APC (`histo_*`) utilisent des données antérieures ou égales à J-2. La fenêtre glissante 7j se termine donc à J-2 et couvre J-8 à J-2 inclus.

Correspondance entre suffixes de features et fenêtres effectives :

| Suffixe | Fenêtre effective | Données utilisées |
|---|---|---|
| `lag2` | ponctuel J-2 | observation du avant-hier |
| `win7_*` | J-8 à J-2 inclus | 7 jours glissants, tous antérieurs à J-1 |

## Justification

**Réalisme opérationnel :** en exploitation, les données APC de J-1 ne sont disponibles que le matin de J. Utiliser `shift(2)` garantit que le modèle ne dépend que de données effectivement accessibles au moment de la décision.

**Cohérence avec ADR-022 :** la matrice de disponibilité J-1 classe les features `histo_*` en catégorie 1 (certaines). Avec `shift(1)`, cette classification était incorrecte — ces features étaient en réalité partiellement en catégorie 5 (leakage). Avec `shift(2)`, la classification catégorie 1 est correctement justifiée.

**Impact sur les performances backtestées :** le passage de J-1 à J-2 perd un jour d'information. L'impact attendu est faible car les patterns de fréquentation sont fortement auto-corrélés sur plusieurs jours, et la fenêtre win7 compense la perte du point J-1.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `shift(1)` — données J-1 | Leakage temporel : données non consolidées à l'heure de décision |
| `shift(0)` — données J | Leakage évident (données du jour à prédire) |
| Horodatage précis de consolidation | Non disponible dans le système APC actuel — reporté si accès aux logs de collecte |

## Conséquences

- Les features `histo_*` sont désormais correctement classées catégorie 1 (certaines) selon ADR-022.
- La performance sur données historiques peut être légèrement inférieure à l'ancienne version (`shift(1)`), mais les métriques seront plus représentatives de l'exploitation réelle.
- Le contrôle de cohérence dans `main()` valide que les `LAG_OPERATIONNEL_JOURS` premières observations de chaque groupe ont bien `lag2 = NaN`.

> **Note de correction (ADR-062, 2026-06-16) :** La supposition que J-2 représente une donnée APC disponible est incorrecte. Les données APC (HOP-REP-WEB) sont publiées mensuellement, avec un lag réel de 18 j en médiane. L'impact du leakage J-2 sur les métriques H25 est : ΔR² HAUT = −0.100, ΔR² GLOBAL = −0.030. La correction est la substitution du cutoff mensuel au lag J-2 dans `add_features_to_raw_stacked.py`. La classification catégorie 1 des `histo_*` selon ADR-022 reste valide avec le cutoff mensuel (les données du dernier mois publié sont certaines à la date de décision).

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constante `LAG_OPERATIONNEL_JOURS`, shift et rolling
- `scripts/pipeline/add_istdaten_to_raw_stacked.py` — jointure `+2 jours` (seul point de décalage pour les features ISTDATEN)
- `scripts/sources/build_dim_profil_train.py` — `LAG_OPERATIONNEL=0` (décalage délégué à la jointure)
- `scripts/sources/build_dim_correspondances_vevey.py` — `LAG_OPERATIONNEL=0` (idem)
- `scripts/sources/_rolling_par_type_jour.py` — `lag` défaut à 0

## Note sur le double-lag ISTDATEN (corrigé 2026-05-21)

Les scripts de dimension ISTDATEN utilisaient `lag=2` dans le rolling ET la
jointure décalait de `+2j`. Ce double-comptage a été corrigé : les scripts de
dimension utilisent `lag=0`, la jointure conserve `+2j`. Cf. ADR-015.
