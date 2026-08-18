---
id: ADR-058
ancien_id: ADR-CF15 (dim_ski)
date_decision: 2026-06-07
statut: amendé
amende_par: [ADR-059]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-058 — Régénération dim_ski_pleiades + intégration partielle saison 2025-2026

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-059.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté  
**Impact hash** : `0c0b7807` → `96225c25`

---

## Contexte

Deux défauts coexistaient dans la dimension ski avant ce correctif :

1. **Bug latent (ski_source manquante)** : `dim_ski_pleiades.parquet` avait été régénéré avec l'ancien script `build_dim_ski_pleiades.py`, perdant la colonne `ski_source`. Or `add_ski_pleiades_to_raw_stacked.py` lit explicitement `dim["ski_source"]` → KeyError garanti au prochain relancement de stage_03b.

2. **Couverture incomplète** : le PDF `ski_25_26.pdf` (saison 2025-2026 officielle) était présent dans `data/external/ski/` mais non parsé ni intégré.

## Décision

### A — Correction du bug latent

Régénérer `dim_ski_pleiades.parquet` avec `build_dim_ski_pleiades_avec_reconstruction.py` (le bon script), qui :
- Produit la colonne `ski_source` (`"officiel"` / `"reconstruit"`)
- Ajoute les saisons H16–H19 reconstruites empiriquement (règle : 1er samedi ≥ 12 déc. + dernier dimanche ≤ 15 mars)

### B — Intégration partielle saison 2025-2026

**PDF source** : `ski_25_26.pdf` — "Exploitation: du samedi 13 décembre 2025 au dimanche 8 mars 2026"

**Analyse périmètre** :
- Convention APC : H25 = 2024-12-15 → 2025-12-13 ; H26 démarre 2025-12-14
- 2025-12-13 (samedi, ouverture officielle de la saison 2025-2026) = **dernier jour de H25**
- 2025-12-14 → 2026-03-08 = **H26, hors périmètre du dataset**

**Décision** : intégrer uniquement 2025-12-13. Les 84 jours restants (H26) ne sont pas intégrés — aucune donnée APC H26 n'existe dans le dataset.

**Entrée ajoutée dans `OFFICIAL_PERIODS`** :
```python
("H26", "2025-12-13", "2025-12-13"),  # 1 seul jour dans H25
```

## Vérification d'écart (pre-run)

Comparaison nouvelle dim vs ancien `stage_03b_ski.parquet` sur le périmètre H22-H25 APC :

| Saison | Dates ski=True ancien | Dates ski=True nouveau | Diff |
|---|---|---|---|
| H22 | 86 | 86 | IDENTIQUE ✓ |
| H23 | 86 | 86 | IDENTIQUE ✓ |
| H24 | 86 | 86 | IDENTIQUE ✓ |
| H25 | 86 | 86 | IDENTIQUE ✓ (avant ajout) |

Seul ajout contrôlé : **2025-12-13** (1 date).

## Non-régression (post-run)

Vérification sur `ml_dataset.parquet` final :

| Horaire | Dates ski=True | Première | Dernière |
|---|---|---|---|
| H22 | 86 | 2021-12-18 | 2022-03-13 |
| H23 | 86 | 2022-12-17 | 2023-03-12 |
| H24 | 87 | 2023-12-16 | 2024-12-14 |
| H25 | 86 | 2024-12-15 | **2025-12-13** ← nouveau |

H24 = 87 dates car 2024-12-14 (ouverture ski H25, dernier jour H24 APC) était déjà True avant ce correctif.

**Tronçons impactés** : 676 tronçons sur base_date=2025-12-13 (samedi, segment haut), tous passent à `event_is_ski_ouvert=True`, `event_ski_source='officiel'`.

## Anti-fuite

`event_is_ski_ouvert` est un flag calendaire publié avant l'ouverture de la saison. Disponible à J-1. Aucune donnée de fréquentation observée ingérée. Pas de fuite temporelle.

## Impact

- `dim_ski_pleiades.parquet` : 530 lignes (H20–H25) → 882 lignes (H16–H26 partiel, `ski_source` présente)
- `stage_03b` → `ml_dataset` : pipeline complète relancée depuis stage_03b
- Hash ml_dataset : `0c0b7807` → **`96225c25`** (205 colonnes, 1 141 984 lignes inchangées)
- Script producteur : `build_dim_ski_pleiades_avec_reconstruction.py` (remplace `build_dim_ski_pleiades.py`)

## Non-intégré (H26)

La saison 2025-2026 au-delà du 2025-12-13 (2025-12-14 → 2026-03-08) relève de H26 et n'est pas intégrée. L'intégrer nécessiterait d'étendre le dataset à H26 — décision de périmètre de thèse indépendante de ce correctif.
