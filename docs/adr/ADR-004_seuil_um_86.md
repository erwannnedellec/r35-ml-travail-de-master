---
id: ADR-004
ancien_id: ADR-04 (seuil_um_86)
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-005]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-004 — ~~Ancrage du seuil UM : `SEUIL_UM = 86`~~ — ARCHIVÉ

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-005.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

> **⚠️ Ce fichier est archivé.** La valeur 86 était incorrecte.
> La capacité assise 2ème classe du SURF 7500 est **94 places**.
> **Voir : [ADR-005_seuil_um_94_2c.md](ADR-005_seuil_um_94_2c.md)**

| Champ | Valeur |
|---|---|
| **Statut** | ~~Acceptée sous condition~~ — **REMPLACÉE par ADR-005_seuil_um_94_2c.md** |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |

## Contexte

La couche de décision (Section 2.3 du notebook `01`) exige un seuil de capacité pour traduire la prédiction de charge en recommandation UM binaire. Deux candidats naturels :

| Candidat | Valeur | Signification |
|---|---|---|
| `CAPACITE_ASSISE_TOTALE` | ~98 places | Rame simple, toutes classes |
| `CAPACITE_ASSISE_2EME` | **86 places** | Rame simple, 2ème classe uniquement |

Le choix est couplé à la décision de cible (ADR-001) : retenir `target_voyageurs_2eme_classe` impose un seuil défini sur la 2ème classe.

## Décision

**`SEUIL_UM = CAPACITE_ASSISE_2EME = 86`** (capacité assise 2ème classe).

Ancrage qualitatif :
- **5/6 participants** aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent explicitement la saturation sur les places assises 2ème classe, pas sur la capacité totale.
- La 1ère classe n'est jamais le facteur limitant (moy = 1 voyageur, P99 = 7, capacité = 12 places).

Ancrage data :
- Mode observé dans `base_places_disponibles_2eme_classe` ≈ 86 places en rame simple.
- La valeur est dérivée du mode observé et à confirmer avec MOB.

## Conséquences

- **Couche de décision** : `recommandation(T) = 1 si voyageurs_2eme_classe_max(T) + marge > 86`.
- **Métriques métier** : Rappel et Précision calculées avec ce seuil. Déséquilibre classes mesuré à ~50:1.
- **Analyse de sensibilité** : une plage [80–110] sera testée en `05_feature_analysis` pour quantifier la sensibilité des métriques au seuil.
- **Validation pendante** : confirmation de la valeur exacte auprès du domaine Voyageurs (sémantique : places assises vs capacité totale homologuée, différenciation adhérence vs crémaillère).
- **Granularité** : un seuil par groupe de tronçons (adhérence Vevey–Blonay vs crémaillère Blonay–Pléiades) reste envisageable — calibrage MOB requis.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `SEUIL_UM = 98` (capacité totale) | Écarté — manque 56 % des surcharges réelles (ADR-001) |
| Seuil dynamique par groupe de tronçons | Possible — reporté après validation du domaine Voyageurs (marge de sécurité et granularité) |
| Régression quantile (p90) comme proxy du seuil | Complémentaire à la marge de sécurité — pas un substitut au seuil de capacité |
