---
id: ADR-005
ancien_id: ADR-04 (seuil_um_94_2c)
date_decision: 2026-05
statut: amendé
amende_par: [ADR-060]
modifie: [ADR-004]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-005 — Seuil UM : `SEUIL_UM_2C = 63` (places assises 2ème classe SURF 7500)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-004.
> **Précision au gel.** Le nom du fichier et le titre portent la valeur d'époque (`SEUIL_UM_2C = 94`) ; la valeur en vigueur au gel est **63** (ADR-060).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée — mis à jour 2026-06-09 (ADR-060) |
| **Date** | 2026-05, corrigé 2026-06-09 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |
| **Remplace** | ADR-004_seuil_um_86.md (valeur incorrecte, version archivée) |

## Contexte

La couche de décision (Section 2.3 du notebook `01`) exige un seuil de capacité pour traduire la prédiction de charge en recommandation UM binaire. Ce seuil doit être défini sur la même variable que la cible ML (cf. ADR-001).

Le matériel roulant de la R35 est le SURF 7500 (MVR/MOB). Ses capacités selon la spec officielle MOB (ABeh 7501-7508) :

| Classe | Places assises (rame simple) | Offre APC (rame simple) |
|---|---|---|
| 1ère classe | 12 places | 12 places |
| **2ème classe** | **63 places assises** | **94 places (63 assises + 31 strapontins)** |
| **Total** | **75 places assises** | **106 (offre APC totale)** |

**Distinction capacité assise / offre APC** : le SI comptage APC enregistre `offre_2eme_classe = 94` pour une rame SURF 7500. Cette valeur de 94 inclut **31 strapontins** (zones multi-usages : vélos, skis, bagages), non mobilisables comme sièges selon la spec matériel MOB active (ref. P01) et le schéma véhicule officiel. Les **63 places assises** sont les places fixes, réservables, utilisables sans restriction.

**Sources (triple traçabilité — ADR-060, 2026-06-09)** :
- Spécification du matériel roulant voyageurs MOB (document interne), champ « Places assises 2ème » : **63** ✓
- Schéma véhicule `vehicules_portes_7500.png` : 63 assises + 31 strapontins (coquille Excel col. "Strap." : 32 affiché, 31 réel confirmé par APC)
- Réconciliation APC empirique : `offre(94) − voyageurs(63) = 31` ✓
- Validation : Responsable des Actifs Voyageurs, MOB, 2026-06-09

**UM (Unité Multiple) = 2 rames couplées** → 126 places assises en 2ème classe (63×2), offre APC 188 (94×2).

Le seuil opérationnel UM est donc ancré sur les **places assises 2ème classe** = 63.

## Décision

**`SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500 = 63`**

Ce seuil matérialise la limite à partir de laquelle la rame simple ne permet plus de garantir une place assise en 2ème classe à l'ensemble des voyageurs : dès la 64ème personne, au moins un voyageur est sans siège.

Constantes associées à utiliser dans le code (cf. `src/r35/constants.py`) :

```python
CAPACITE_ASSISE_2C_SURF7500 = 63    # places assises 2ème classe, rame simple
OFFRE_TOTALE_2C_APC_SURF7500 = 94   # offre APC 2C (63 assises + 31 strapontins)
CAPACITE_ASSISE_1C_SURF7500 = 12    # places assises 1ère classe, rame simple
CAPACITE_ASSISE_TOTAL_SURF7500 = 75 # total places assises rame simple (63+12)
SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500  # seuil déclencheur UM = 63

# Indicateur surcharge (strictement supérieur = au moins un voyageur sans siège)
is_surcharge_2c = target_voyageurs_2eme_classe > SEUIL_UM_2C   # > 63
recommandation_um = prediction_voyageurs_2eme_classe > SEUIL_UM_2C
```

## Justification

**Ancrage capacitaire :** le seuil de 63 correspond aux places assises 2ème classe officielles du SURF 7500. Les 31 strapontins supplémentaires (offre APC = 94) ne constituent pas des places assises mobilisables sans restriction et ne constituent pas une capacité d'assise garantie.

**Ancrage qualitatif :**
- **5/6 participants** aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent explicitement la saturation sur les **places assises 2ème classe**, pas sur la capacité totale.
- La 1ère classe n'est jamais le facteur limitant (moy = 1 voyageur, P99 = 7, capacité = 12 places).
- Les entretiens confirment la pertinence métier du seuil d'occupation des **sièges** — ce qui confirme 63 (pas 94).

**Ancrage data :** H25 (test OOT, modèle Enrichi_Seg 158f v1.1, dataset daf936c8, ADR-061) :
- Surcharges `> 63` : BAS=8392, HAUT=1192, GLOBAL=9584 (3.28% des observations)
- Surcharges `> 94` à titre comparatif : BAS=1166, HAUT=280, GLOBAL=1446 (0.47%)

**Note historique — référence à +56% (seuil précédent) :** l'ancienne version de cet ADR mentionnait "+56% de surcharges supplémentaires vs `target_voyageurs_total > 106`" pour justifier 94 vs 106. Cette comparaison portait sur l'ancien seuil de 94 (offre APC) et n'a plus d'objet. La justification du seuil 63 repose entièrement sur la définition des places assises (spec MOB, ADR-060) — pas sur une comparaison relative.

## Convention sur >

- `is_surcharge_2c` : `> 63` — la capacité assise est **dépassée** (au moins un voyageur sans siège).
- Pipeline feature `histo_voyageurs_2eme_classe_win7_n_surcharges` : utilise `> SEUIL_UM_2EME` (strict) — identique.
- Pour la recommandation UM opérationnelle : `prediction > 63`.

## Conséquences

- **Couche de décision** : `recommandation_um = prediction_voyageurs_2eme_classe > 63`.
- **Métriques métier** : Rappel et Précision calculées avec ce seuil. Déséquilibre classes mesuré ~0.47% à l'ancien seuil 94, ~3.28% au seuil 63 (H25).
- **Feature win7_n_surcharges** : recalculée avec seuil 63 (ADR-060), dataset hash daf936c8.
- **Analyse de sensibilité** : une plage [63–94] pourrait être explorée en couche 2 pour quantifier la sensibilité des métriques au seuil — mais la valeur 63 est la valeur physique de référence.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `SEUIL_UM = 94` (offre APC, ancienne valeur) | Incorrect — 94 = offre APC incluant 31 strapontins non mobilisables comme sièges (spec MOB P01). Confusion entre offre totale et places assises. ADR-060. |
| `SEUIL_UM = 106` (offre APC totale 1C+2C) | Écarté — mélange 2C et 1C ; n'est pas le périmètre de décision UM 2ème classe |
| `SEUIL_UM = 86` (ancienne estimation) | Incorrect — archivé dans ADR-004_seuil_um_86.md |
| Seuil dynamique par groupe de tronçons | Possible en phase d'évaluation — reporté après premiers résultats de modélisation couche 2 |
| Régression quantile (p90) comme proxy du seuil | Complémentaire à l'analyse de sensibilité — pas un substitut au seuil de capacité physique |

## Fichiers impactés

- `src/r35/constants.py` — constantes `CAPACITE_ASSISE_2C_SURF7500 = 63`, `OFFRE_TOTALE_2C_APC_SURF7500 = 94`, `SEUIL_UM_2C = 63`
- `scripts/pipeline/add_features_to_raw_stacked.py` — `SEUIL_UM_2EME = 63` (ADR-060)
- `data/processed/ml_dataset.parquet` — hash `daf936c8` (ADR-060)
- `notebooks/02_data_understanding_apc.ipynb` §2.1.1 (analyse surcharges)
