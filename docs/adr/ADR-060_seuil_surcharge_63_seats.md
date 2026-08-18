---
id: ADR-060
ancien_id: ADR-CF16
date_decision: 2026-06-09
statut: actif
modifie: [ADR-001, ADR-005, ADR-010]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-060 — Correction du seuil de surcharge 2ème classe : 94 → 63

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-001, ADR-005, ADR-010.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-09  
**Statut** : DÉCISION FIGÉE  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-005 (seuil opérationnel couche 2), ADR-052 (modèle final 170f hash `11b58391`), ADR-049 (cadrage BAS/HAUT)

---

## Contexte

Depuis ADR-005, la constante `SEUIL_UM_2EME = 94` était utilisée dans le pipeline de features pour calculer `histo_voyageurs_2eme_classe_win7_n_surcharges` (nombre d'occurrences de surcharge dans une fenêtre glissante de 7 creneaux J-2). La valeur 94 provenait de `offre_2eme_classe` dans les données APC, qui encode la capacité totale opérationnelle de la rame SURF 7500.

## Problème identifié

La valeur 94 inclut **31 strapontins** (zones multi-usages : vélos, skis, bagages). Ces places ne sont pas mobilisables comme sièges selon la spec matériel MOB active (ref. P01) et le schéma véhicule officiel. La réalité opérationnelle pour la décision UM est : **63 places assises** (places fixes, réservables, utilisables sans restriction).

Un seuil à 94 signifie « toutes les places assises ET tous les strapontins occupés » — un état rare et mal défini. Un seuil à 63 signifie « tous les sièges réservables occupés » — le déclencheur naturel de la décision UM.

## Sources (triple traçabilité)

| Source | Valeur 2ème classe | Fichier |
|--------|--------------------|---------|
| Spécification matériel roulant voyageurs MOB (document interne) — champ « Places assises 2ème » | **63** ✓ correct | source interne, non diffusée |
| Spécification matériel roulant voyageurs MOB (document interne) — champ « Strapontins » | **32** ⚠ écart de saisie (31 réel) | source interne, non diffusée |
| Schéma véhicule `vehicules_portes_7500.png` | **63** assises + **31** strapontins | `data/external/spec_materiel/vehicules_portes_7500.png` |
| APC empirique : `offre − voyageurs` quand `voyageurs = 63` | `94 − 63 = 31` → confirme 31 strapontins | `raw_stacked_annee_horaire.csv` |

**Note coquille Excel** : L'Excel est **correct sur les places assises** (colonne "Places assises 2ème" = 63 pour les ABeh 7501-7508). Sa seule coquille porte sur les **strapontins** (colonne "Strap." = 32 affiché au lieu de 31 réel). Le schéma véhicule et la réconciliation APC convergent sur **63 assises + 31 strapontins = 94**, sans aucune incidence sur le seuil retenu (63 = nombre de places assises). Validation : Responsable des Actifs Voyageurs, MOB, 2026-06-09.

**Valeur retenue : 63.**

## Décision

`SEUIL_UM_2EME` dans `scripts/pipeline/add_features_to_raw_stacked.py` modifié de `94` à `63`.

Seule `histo_voyageurs_2eme_classe_win7_n_surcharges` est calculée à partir de ce seuil. Les autres features capacité (`base_offre_2eme_classe`, `base_places_disponibles_2eme_classe`, `base_tx_occupation_2eme_classe`) sont soit exclues du ml_dataset, soit hors du périmètre 170f, et ne sont **pas modifiées**.

## Impact quantitatif — ml_dataset H22–H25

| Métrique | Ancien (seuil=94) | Nouveau (seuil=63) |
|----------|-------------------|-------------------|
| Hash MD5 ml_dataset | `11b58391de431b24f13b25a2764cfdc8` | `daf936c8bd3e69b87e937123ec185b22` |
| Total observations | 1 141 984 | 1 141 984 |
| Obs `win7_n_surcharges = 0` | 1 134 099 | 1 090 081 |
| Obs `win7_n_surcharges ≥ 1` | 7 607 | 51 625 (×6.8) |
| Obs `win7_n_surcharges = 7` | 16 | 396 |
| Obs passées 0 → ≥1 | — | 44 018 (3.9%) |

La feature est désormais activée sur **3.9 % des observations** contre 0.7 % avant — représentation plus réaliste des creneaux historiquement chargés.

### Distribution complète

| Valeur | Seuil=94 | Seuil=63 | Delta |
|--------|----------|----------|-------|
| 0 | 1 134 099 | 1 090 081 | −44 018 |
| 1 | 6 317 | 32 577 | +26 260 |
| 2 | 622 | 9 266 | +8 644 |
| 3 | 360 | 3 544 | +3 184 |
| 4 | 112 | 2 640 | +2 528 |
| 5 | 96 | 1 844 | +1 748 |
| 6 | 84 | 1 358 | +1 274 |
| 7 | 16 | 396 | +380 |
| NaN | 278 | 278 | 0 |

## Non-régression

Vérification ciblée post-régénération des stages 08→09→10→ml_dataset :

- Seule `histo_voyageurs_2eme_classe_win7_n_surcharges` a changé de valeurs.
- `base_offre_2eme_classe` (retenu dans ml_dataset) : valeurs inchangées (raw APC), absent du périmètre 170f → sans impact sur le modèle.
- Toutes les autres 204 colonnes : identiques (même source APC/météo/SIMBA/réservations).
- Lignes conservées : 1 141 984 (identique).

## Ce qui N'est PAS modifié ici

- `src/r35/constants.py` → non modifié (SEUIL_UM_2EME couche 2 = 94, reste inchangé jusqu'au réentraînement)
- ADR-005, ADR-049, ADR-052 → non modifiés (métriques H25 `n_surch≥94` correspondent encore au modèle précédent hash `11b58391`)
- Notebooks consolidation_finale → non modifiés

Ces propagations interviendront après réentraînement sur le nouveau ml_dataset (hash `daf936c8`).

## Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `scripts/pipeline/add_features_to_raw_stacked.py` | `SEUIL_UM_2EME = 94 → 63` avec commentaire source triple |
| `scripts/pipeline/add_reservations_to_raw_stacked.py` | Optimisation mémoire (`del df_ml` post-merge, extraction QG3 avant merge) — sans impact sur les valeurs |
| `data/external/spec_materiel/` (spécification interne du matériel roulant) | Ajouté (source spec matériel) |
| `data/external/spec_materiel/vehicules_portes_7500.png` | Ajouté (schéma véhicule SURF 7500) |
| `data/processed/ml_dataset.parquet` | Régénéré — nouveau hash `daf936c8` |
