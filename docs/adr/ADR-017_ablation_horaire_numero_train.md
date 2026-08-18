---
id: ADR-017
ancien_id: ADR-18
date_decision: 2026-05-15
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-017 — Ablation empirique de la feature horaire_numero_train

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-15

## Contexte

La feature `horaire_numero_train` est encodée en dummy avec environ 108 modalités
dans le modèle XGBoost. Son apport prédictif est questionné car les autres
features (`base_depart_datetime` cyclique, `base_sens`, `cal_type_jour`, `horaire_annee_horaire`)
caractérisent déjà intrinsèquement le service ferroviaire.

Théoriquement, deux hypothèses concurrentes :
- **Hypothèse de redondance** : les caractéristiques du service capturent
  l'essentiel du signal, `horaire_numero_train` n'apporte rien.
- **Hypothèse de signal résiduel** : `horaire_numero_train` capture des comportements
  voyageurs spécifiques au train (habitudes scolaires, navettes d'entreprise,
  effets de groupe) non réductibles aux caractéristiques opérationnelles.

## Décision

Trancher par ablation empirique : produire deux variantes du dataset `ml_dataset`
(avec et sans la feature) et comparer les performances test sur H24.

Le script `build_ml_dataset.py` expose un argument `--exclure-horaire-numero-train`
qui contrôle l'inclusion de la feature. La variante sans la feature est écrite
dans `ml_dataset_sans_train_id.parquet`.

## Critère de décision

- Si Δ R² test > 0.02 en faveur de la version **avec** : feature conservée,
  signal résiduel justifié.
- Si Δ R² test < 0.02 (incluant le cas où la version **sans** gagne) : feature
  retirée, simplification du modèle.

## Conséquences

- Deux datasets distincts produits dans `data/processed/` pour les tests d'ablation.
- La décision finale sera tranchée après les entraînements Dataiku.
