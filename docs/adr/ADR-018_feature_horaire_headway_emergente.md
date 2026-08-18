---
id: ADR-018
ancien_id: ADR-19
date_decision: 2026-05-15
statut: amendé
amende_par: [ADR-067]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-018 — Features ist_headway_* depuis ISTDATEN exclusivement

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-067.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Révisé
**Date initiale** : 2026-05-15 | **Révision** : 2026-05-21

## Contexte

La phase qualitative exploratoire (6 entretiens semi-directifs, codage
thématique) a identifié la cadence horaire (headway) comme critère
structurant de la décision d'usage de la R35, mentionné par 3/6 participants
(P02, P05, P06).

P05 formule explicitement un contre-argument à l'ajout d'unités multiples :
la solution opérationnelle perçue est l'augmentation de fréquence, pas de
capacité par train. Cette feature était absente du pipeline ML initial dérivé
de la littérature ML appliquée au transport ferroviaire (Ding et al. 2016,
Yusuf et al. 2025).

La première implémentation utilisait les horaires PDF (horaires théoriques
publiés). Cette approche a été abandonnée : la qualité de l'extraction PDF
est insuffisamment maîtrisée (grain des tronçons incohérent entre annéess
horaires, couverture H16–H19 ~76%), et elle introduit une dépendance à une
source fragile alors qu'ISTDATEN fournit les mêmes informations avec une
couverture et une traçabilité supérieures.

## Décision

Ajouter deux features symétriques au pipeline ML, construites exclusivement
depuis `fact_istdaten_r35.parquet` :

- `ist_headway_avant_min` : minutes depuis le départ du train précédent
  sur le même tronçon dans le même sens
- `ist_headway_apres_min` : minutes jusqu'au départ du train suivant
  sur le même tronçon dans le même sens

Le préfixe `ist_` est cohérent avec les autres features dérivées d'ISTDATEN.

### Définition technique (révisée 2026-05-21)

**Heure de départ** : uniquement `horaire_depart` (ISTDATEN théorique, pas le PDF).
La version initiale utilisait `reel_depart` avec fallback sur `horaire_depart`.
Ce fallback a été supprimé : en déploiement, MOB n'a que l'horaire théorique à J-1.
Utiliser les heures réelles en entraînement créait un distribution shift documenté
mais évitable. La perte est la granularité « retard induit par un train précédent » ;
elle est assumée car la cohérence opérationnelle prime.

- `is_annule = True` → exclu (ne compte pas comme prédécesseur ni successeur)
- `is_supplementaire = True`, `is_annule = False` → inclus normalement

**Reconstruction des tronçons** : pour chaque `(date, numero_train)`, les
arrêts sont triés par `horaire_depart` et des paires successives
`(bpuic_n, bpuic_n+1)` forment les tronçons. Le sens est déduit de l'ordre
kilométrique dans `dim_gare`.

**Valeurs manquantes** : premier train de la journée → `ist_headway_avant_min = NaN` ;
dernier train → `ist_headway_apres_min = NaN`. La sentinelle 999.0 a été supprimée :
XGBoost gère nativement les NaN, et 999 créait une discontinuité artificielle.

**Flags binaires ajoutés** :
- `ist_headway_avant_is_first_of_day` (int8) : 1 ↔ `ist_headway_avant_min` est NaN
- `ist_headway_apres_is_last_of_day` (int8) : 1 ↔ `ist_headway_apres_min` est NaN

### Clé de jointure dans le pipeline

```
dim_headway (date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)
  ↔ stage_07_istdaten (base_date, horaire_numero_train,
                        id_gare_depart_bpuic, id_gare_arrivee_bpuic, base_sens)
```

Pas de décalage J-2 : en entraînement, `dim_headway` contient des
observations passées connues au moment de la prédiction.

## Justification de la formulation symétrique

La formulation avant/après capture l'isolement temporel sans préjuger de la
direction de l'effet : un train très espacé du précédent absorbe davantage de
demande accumulée ; un train très rapproché du suivant peut inciter les usagers
à attendre. Les deux directions sont empiriquement distinctes et permettent une
analyse SHAP différenciée.

## Cohérence opérationnelle (entraînement vs déploiement)

En **entraînement** comme en **déploiement**, la source est l'horaire théorique
ISTDATEN. La révision 2026-05-21 a aligné entraînement et déploiement en
supprimant le fallback sur `reel_depart`. MOB substituera par son horaire
tabulaire interne sans distribution shift.

## Conséquences

- Source unique et robuste : ISTDATEN, déjà dans le pipeline.
- Couverture H24 (test set) : >95%.
- Pipeline simple : deux features, grain identique à stage_07.
- Feature défendable scientifiquement : émergente du qualitatif, complémentaire
  au contre-argument P05 sur la fréquence vs la capacité.
- Permet une analyse SHAP directe : quantifie l'effet marginal d'une réduction
  de headway sur la fréquentation prédite, documentant empiriquement
  la validité du contre-argument P05.

## Critère de validation

Si l'ablation de ces features dégrade significativement la performance
(Δ R² > 0.01), l'apport quantitatif justifie leur inclusion. Si la dégradation
est marginale (< 0.01), les features sont conservées pour leur valeur
explicative et le matériau qu'elles apportent au Chapitre 4 du mémoire.

## Articulation avec la couche de décision (Chapitre 5)

Les features alimentent directement la discussion opérationnelle : faut-il
dimensionner par capacité (UM) ou par fréquence (headway réduit) ?
L'analyse SHAP sur les courses en surcharge permettra de quantifier l'effet
marginal d'une réduction de headway sur la fréquentation prédite.
