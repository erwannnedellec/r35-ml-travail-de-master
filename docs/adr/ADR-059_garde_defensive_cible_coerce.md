---
id: ADR-059
ancien_id: ADR-CF15 (garde_defensive)
date_decision: 2026-06-07
statut: actif
modifie: [ADR-058]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-059 — Garde défensive sur le calcul de la cible (coerce silencieux)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-058.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté — appliqué  
**Auteur** : Erwann Nedellec  

---

## Contexte

L'audit NaN systématique du ml_dataset (2026-06-07) a identifié un risque latent dans `add_features_to_raw_stacked.py` (stage 08). Le calcul de `target_voyageurs_total` utilisait le pattern :

```python
v1 = pd.to_numeric(result["target_voyageurs_1ere_classe"], errors="coerce").fillna(0)
v2 = pd.to_numeric(result["target_voyageurs_2eme_classe"], errors="coerce").fillna(0)
result["target_voyageurs_total"] = (v1 + v2).astype("float64")
```

Ce pattern s'applique aux deux colonnes sources de la cible réelle du modèle (`target_voyageurs_2eme_classe`) et de la variable de contrôle (`target_voyageurs_total`). En présence de valeurs non-numériques dans une extraction APC malformée, `errors="coerce"` les transforme silencieusement en NaN, puis `fillna(0)` les écrase en zéro — sans log, sans erreur, sans trace. Un faux zéro sur la cible = point d'entraînement empoisonné.

**Confirmation sur données réelles** : 0 corruption constatée (invariant vérifié à chaque exécution). C'est un risque latent, pas un problème actif.

---

## Décision

Ajouter une vérification explicite **avant** le `fillna(0)` : comptage des valeurs originellement non-NaN qui deviennent NaN après `to_numeric`. Si le compte est > 0 → `raise ValueError` avec le nombre et un échantillon des valeurs fautives.

**Ce qui ne change pas sur données propres** : comportement strictement identique. Les variables intermédiaires `_v1_coerced.fillna(0)` sont algébriquement équivalentes à `pd.to_numeric(..., errors="coerce").fillna(0)`.

---

## Justification du choix `raise ValueError` vs `logging.warning`

La convention du projet (CONTEXT.md §Bonnes pratiques) spécifie "assertions sur les invariants critiques". La cible est l'invariant le plus critique du pipeline — un faux zéro ici propage une erreur silencieuse dans toutes les features historiques (`histo_*`) et dans le score de chaque modèle entraîné sur ce dataset. Un arrêt immédiat (`raise ValueError`) est préférable à un warning qui pourrait être ignoré.

---

## Vérification élargie : `target_voyageurs_2eme_classe` protégée ailleurs ?

Recherche dans tout le pipeline (`scripts/`) :

| Fichier | Ligne | Pattern | Verdict |
|---------|-------|---------|---------|
| `add_features_to_raw_stacked.py` | 304–305 | `coerce.fillna(0)` sur 1c et **2c** | ✅ Protégé par cette garde |
| `add_features_to_raw_stacked.py` | 332 | `to_numeric(result[col], errors="coerce")` sur LAG_SOURCE_COLS (inclut 2c) | ✅ Sans `fillna` — NaN propagés, non écrasés |
| `scripts/generate_notebook_02_du_surcharges.py` | 893 | `df["target_voyageurs_2eme_classe"].astype("float64").fillna(-1)` | ✅ Script notebook, opère sur ml_dataset déjà construit. Valeur sentinelle −1 pour visualisation, pas pour entraînement |
| `scripts/update_notebook_02.py` | 269 | `v2 = df["target_voyageurs_2eme_classe"].fillna(0)` | ✅ Script notebook (statistiques descriptives), pas pipeline |

**Conclusion** : `target_voyageurs_2eme_classe` n'est soumise à aucun `coerce→fillna(0)` silencieux en dehors de la ligne désormais protégée.

---

## Non-régression

- Shape ml_dataset : (1 141 984, 205) — inchangé
- `target_voyageurs_total` NaN : 0 — inchangé
- `target_voyageurs_2eme_classe` NaN : 0 — inchangé
- Diff `total − (1c + 2c)` : 0.000000 — exact
- Garde silencieuse (0 corruption détectée) → aucune erreur levée

**Note sur le hash — canonique désigné** : le hash du fichier parquet est `11b58391` (MD5). Une sérialisation antérieure du même dataset avait produit `96225c25` (référencé dans CONTEXT.md v5 initial et `controle_enrichi_seg_172f.json`). L'identité de contenu entre les deux est prouvée : fingerprint pandas trié `42a02ffe571f7863`, 1 141 984 lignes, 205 colonnes, toutes valeurs identiques — seules les métadonnées de timestamp parquet diffèrent. **Hash canonique unique : `11b58391`** (c'est celui que produit le fichier sur disque à chaque run). Les notebooks assertent uniquement `11b58391`. `96225c25` n'est plus une référence active.

---

## Fichier modifié

| Fichier | Lignes | Nature |
|---------|--------|--------|
| `scripts/pipeline/add_features_to_raw_stacked.py` | 304–326 | Garde défensive + restructuration des variables v1/v2 |
