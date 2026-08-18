---
id: ADR-012
ancien_id: ADR-12
date_decision: 2026-05-15
statut: remplacé
remplace_par: [ADR-019]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-012 — Refonte ISTDATEN au grain date × numero_train

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-019.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Le pipeline ISTDATEN initial (stage_07 via `add_ponctualite_to_raw_stacked.py`) agrégeait
tous les indicateurs de ponctualité au grain journalier (une ligne par date). Cette
agrégation détruisait le signal le plus informatif pour la prédiction de fréquentation :
la spécificité par train.

Deux trains du même jour peuvent avoir des profils de ponctualité très différents
(le 8h20 est régulièrement en retard, le 9h05 ne l'est jamais). En agrégeant, on
perd cette information et on contraint le modèle à utiliser des moyennes journalières
peu discriminantes.

## Décision

Passer le grain des features ISTDATEN de `date` à `date × numero_train` via trois
nouvelles tables :

| Table | Script producteur | Grain |
|---|---|---|
| `dim_profil_train` | `build_dim_profil_train.py` | date × numero_train |
| `dim_correspondances_vevey` | `build_dim_correspondances_vevey.py` | date × numero_train |
| `dim_vmcv_par_gare` | `build_dim_vmcv_par_gare.py` | gare (statique) |

Le nouveau script d'intégration `add_istdaten_to_raw_stacked.py` remplace
`add_ponctualite_to_raw_stacked.py` et produit `stage_07_istdaten.parquet`.

## Conséquences

**Positives :**
- Le modèle dispose d'un signal par train, permettant de capturer les habitudes
  de ponctualité structurelles de chaque course.
- Les fenêtres 7j et 28j par train reflètent l'historique spécifique du train,
  pas la moyenne du réseau.
- Les correspondances Vevey deviennent précises : on sait exactement quels feeders
  arrivent avant chaque départ R35.

**Négatives / risques :**
- Couverture partielle attendue : les trains sans historique 28j (début de période,
  nouveaux numéros) auront NaN. XGBoost gère nativement les NaN.
- Les correspondances Vevey ne couvrent que les trains depuis Vevey (les autres
  trains auront NaN pour cette famille, ce qui est correct).
- Volume de données accru : `dim_profil_train` a un grain plus fin qu'une simple
  table journalière.

## Alternatives écartées

- **Conserver le grain journalier** : perd le signal par train, acceptable pour un
  baseline mais insuffisant pour un modèle performant.
- **Grain arrêt** : trop fin pour la jointure APC (le modèle prédit par tronçon,
  pas par arrêt). Le grain train est le bon niveau d'agrégation.

## Tests d'ablation

Voir `add_istdaten_to_raw_stacked.py --familles` pour les variantes d'ablation
permettant d'isoler la contribution de chaque famille (Chapitre 4 du mémoire).
