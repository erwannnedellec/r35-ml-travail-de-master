---
id: ADR-013
ancien_id: ADR-13
date_decision: 2026-05-15
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-013 — Convention de ponctualité par valeur absolue

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

La fonction de calcul du pourcentage de ponctualité comparait `retard <= seuil`,
ce qui considérait comme ponctuel un train parti en avance (retard négatif).

Cette convention est incorrecte dans le contexte ferroviaire : un départ en avance
est aussi pénalisant qu'un retard pour les voyageurs en correspondance, qui ratent
leur train. L'OFT mesure également la ponctualité en valeur absolue.

## Décision (révisée 2026-05-21)

Deux conventions coexistent selon le contexte :

### Ponctualité au DÉPART — convention symétrique `|retard| <= seuil`

Un départ en avance est aussi pénalisant qu'un retard pour les voyageurs en
correspondance, qui ratent leur train. Convention OFT.

```python
def _pct_ponctuel_symetrique(serie: pd.Series, seuil: int) -> float:
    valid = serie.dropna()
    return float((valid.abs() <= seuil).mean()) if len(valid) > 0 else float("nan")
```

S'applique à :
- `build_istdaten_ponctualite.py` — `ist_r35_pct_dep_ponctuel_*_j`
- `build_dim_profil_train.py` — `is_en_retard_dep` (retard >= seuil, sans valeur absolue,
  car l'avance au départ d'un tronçon intermédiaire n'est pas un problème)

### Ponctualité à l'ARRIVÉE — convention retard seul `retard <= seuil`

Un train CFF arrivant en avance à Vevey ne fait pas rater la correspondance R35.
Pénaliser l'avance gonflerait artificiellement la non-ponctualité.

```python
def _pct_ponctuel_retard_seul(serie: pd.Series, seuil: int) -> float:
    valid = serie.dropna()
    return float((valid <= seuil).mean()) if len(valid) > 0 else float("nan")
```

S'applique à :
- `build_istdaten_ponctualite.py` — `ist_vevey_pct_arr_ponctuel_180s_j`
- `build_dim_profil_train.py` — `is_en_retard_arr` (retard >= seuil, cohérent)

## Conséquences

- `ist_r35_pct_dep_ponctuel_*_j` : inchangé (déjà symétrique).
- `ist_vevey_pct_arr_ponctuel_180s_j` : légère hausse attendue (les avances
  ne sont plus pénalisées).
- `is_en_retard_dep` et `is_en_retard_arr` dans `build_dim_profil_train.py` :
  inchangés — les deux utilisaient déjà `retard >= seuil`.

## Alternatives écartées

- **Convention symétrique pour les arrivées** : surestimait la non-ponctualité
  des feeders Vevey. Supprimé le 2026-05-21.
- **Seuils asymétriques** (ex. `-30s ≤ retard ≤ 180s`) : introduit un paramètre
  supplémentaire sans justification opérationnelle claire.
