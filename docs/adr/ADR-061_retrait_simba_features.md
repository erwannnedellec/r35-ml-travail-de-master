---
id: ADR-061
ancien_id: ADR-CF17
date_decision: 2026-06-11
statut: actif
modifie: [ADR-026, ADR-041, ADR-052, ADR-054, ADR-056]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-061 — Retrait définitif des 12 features SIMBA du modèle de couche 1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-026, ADR-041, ADR-052, ADR-054, ADR-056.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-11 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-026 (intégration SIMBA, lag N-1), ADR-041 (refonte horaire H24→H25), ADR-052 (modèle final Enrichi_Seg), ADR-060 (seuil surcharge 63) |

## Contexte

L'investigation de la cohérence temporelle SIMBA (2026-06-11) a mis en évidence une convergence de quatre problèmes structurels indépendants sur les 12 features `simba_part_*` :

### 1. Instabilité inter-annuelle quasi-nulle

Sur les 52 trains conservés entre H24 et H25 (même numéro de train, comparaison propre sans contamination des trains renumérotés), la corrélation entre les profils SIMBA 2023 et SIMBA 2024 est :

| Feature | r (2023 vs 2024) | MAE |
|---|---|---|
| `simba_part_ga` | **0.056** | 0.127 |
| `simba_part_billet_hta` | 0.138 | 0.089 |
| `simba_part_spar` | 0.124 | 0.030 |
| `simba_part_jeunes` | 0.023 | 0.053 |
| `simba_part_intra_r35` | 0.331 | 0.236 |
| `simba_part_premiere_classe` | 0.537 | 0.038 |
| `simba_part_corresp_amont` | 0.658 | 0.112 |
| `simba_part_corresp_aval` | 0.724 | 0.137 |
| `simba_part_mobilis` | 0.752 | 0.138 |

La corrélation r = 0.056 pour `simba_part_ga` (feature la plus interprétable, dominante en volume) invalide l'hypothèse de "profil structurel stable" qui justifiait le lag N-1. Ces écarts reflètent une volatilité réelle de la composition de la demande en post-COVID, potentiellement amplifiée par la réforme tarifaire CFF 2023.

### 2. Leakage de disponibilité sur 21.6% de H25

La publication de SIMBA Y intervient en avril-mai Y+1 (latence 4–5 mois). H25 débute en décembre 2024. Pour les observations de décembre 2024 à avril 2025, SIMBA 2024 (millésime assigné par la convention ADR-026 à toute l'année H25) n'était pas encore publié :

| Fenêtre | Observations concernées | % de H25 |
|---|---|---|
| Déc 2024 – mars 2025 | 51 486 avec match SIMBA | 16.6% |
| Déc 2024 – avril 2025 (latence 5 mois) | 66 687 avec match SIMBA | **21.6%** |
| Déc 2024 – mai 2025 (latence 6 mois) | 80 973 avec match SIMBA | 26.2% |

Ces observations ont reçu dans le dataset des valeurs SIMBA 2024 qui n'auraient pas été disponibles à la date de décision réelle. C'est un leakage de disponibilité sur les features (pas sur la cible) qui crée une asymétrie entre les conditions d'évaluation et les conditions de production pour ces mois.

### 3. 46.6% de NaN structurels sur H25

La refonte d'horaire CFF/MOB de décembre 2024 a renuméroté 52 trains (50% du parc), sans équivalent dans SIMBA 2024 (ADR-041). Ces trains ne peuvent recevoir aucune valeur SIMBA sans réintroduire le leakage circulaire SIMBA(N) ↔ APC(N). Le taux de NaN SIMBA sur H25 est stable à ~47% sur tous les mois de l'année — il est structurel, pas temporel.

### 4. Bas du classement SHAP

Les features `simba_*` apparaissent systématiquement dans la moitié inférieure du classement SHAP (ADR-036, ADR-041, ADR-053), confirmant leur contribution marginale à la performance prédictive.

## Décision

**Retrait définitif des 12 features `simba_*` du modèle de couche 1 Enrichi_Seg.**

Cette décision est fondée sur la **fiabilité et la déployabilité**, et non sur le R². Un modèle sans features instables et partiellement indisponibles est meilleur au sens opérationnel, indépendamment de l'impact sur les métriques.

Les 12 features retirées :

```
simba_part_ga, simba_part_mobilis, simba_part_billet_hta, simba_part_spar,
simba_part_jeunes, simba_part_abonnement, simba_part_militaire, simba_part_autre,
simba_part_corresp_amont, simba_part_corresp_aval, simba_part_premiere_classe,
simba_part_intra_r35
```

**SIMBA reste une source du Business Understanding** (compréhension des profils tarifaires, structure de la demande par titre de transport, correspondances intermodales) documentée dans le mémoire. Elle informe le contexte opérationnel sans constituer une feature prédictive du modèle de couche 1.

## Résultats du réentraînement

Nouveau modèle : Enrichi_Seg v1.1, 158 features, dataset hash daf936c8, seed 42, hyperparamètres ADR-052 inchangés.

| Segment | R² 158f | R² 170f (ref) | ΔR² | IC 95% R² |
|---|---|---|---|---|
| BAS | **0.5548** | 0.5538 | **+0.0010** | [0.5512 ; 0.5586] |
| HAUT | **0.5042** | 0.4626 | **+0.0415** | [0.4933 ; 0.5138] |
| GLOBAL | **0.5884** | 0.5812 | **+0.0072** | [0.5850 ; 0.5917] |

Le modèle 158f est **neutre à marginalement meilleur** sur tous les segments. L'amélioration de +0.042 sur le segment HAUT (touristique) est cohérente avec la suppression de features très bruitées (r~0.05) sur un segment où le signal est structurellement plus fragile.

**Interprétation** : les features SIMBA, en raison de leur faible stabilité inter-annuelle, introduisaient du bruit plutôt qu'un signal structurel. Leur retrait ne dégrade pas le modèle — il l'assainie.

## Artefacts produits

| Artefact | Chemin | Statut |
|---|---|---|
| Modèles 158f | `models/enrichi_seg/enrichi_seg_{bas,haut}.json` | Canonical v1.1 |
| Métadonnées | `models/enrichi_seg/enrichi_seg_metadata.json` | Version 1.1 |
| Archive 170f | `models/enrichi_seg/archive_170f/` | Traçabilité |
| Liste features | `consolidation_finale/outputs/features_158f_sans_simba.json` | Canonical |
| SHAP 158f | `consolidation_finale/outputs/q6_shap_ranks_{bas,haut}_158f.csv` | Courants |
| Prédictions 158f | `consolidation_finale/outputs/q6_predictions_h25_158f.parquet` | Courants |
| Script d'entraînement | `consolidation_finale/scripts/retrait_simba_158f.py` | Reproductible |
| Résultats complets | `consolidation_finale/outputs/retrait_simba_158f_resultats.json` | Courants |

## Conséquences sur la documentation

- **ADR-026** : SIMBA reste documentée comme source intégrée dans le pipeline. Ajouter note de bas de page : les `simba_*` ont été retirées des features prédictives par ADR-061.
- **ADR-041** : décision Option A (NaN tracé) reste valide pour la traçabilité pipeline. Ajouter note : la décision de retrait rend caduque la question du NaN pour le modèle, mais l'analyse reste pertinente pour la compréhension des données.
- **Section DataPrep** : tableau des familles de features : 10 groupes → 9 groupes (sans SIMBA), compte total 170 → 158.
- **Section BU** : §3.3.4 « Profils de demande SIMBA FQkal » conservé. Clarification ajoutée : SIMBA informe le contexte mais n'est pas une feature prédictive du modèle final (voir ADR-061).
- **verify_enrichi_seg.py** : assertions 170 → 158, FEAT_JSON → features_158f_sans_simba.json.
- **Notebook assertions** : `assert len(FEATURES) == 158`.

## Références

- Investigation cohérence temporelle SIMBA, 2026-06-11
- ADR-026 — Intégration SIMBA FQkal, lag N-1
- ADR-041 — Refonte horaire H24→H25, NaN SIMBA structurels
- ADR-052 — Modèle final Enrichi_Seg, hyperparamètres
- ADR-060 — Seuil surcharge 63
- `consolidation_finale/scripts/retrait_simba_158f.py` — script de réentraînement
