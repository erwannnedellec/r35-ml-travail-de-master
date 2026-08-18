---
id: ADR-009
ancien_id: ADR-09
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-037, ADR-042, ADR-044, ADR-062]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-009 — Grain de groupement des features historiques : inclusion de l'année horaire

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-037, ADR-042, ADR-044, ADR-062.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Constante** | `GROUP_KEYS = ["horaire_annee_horaire", "horaire_troncon_tgl", "horaire_numero_train"]` |
| **Remplace** | `GROUP_KEYS = ["horaire_troncon_tgl", "horaire_numero_train"]` |

## Contexte

Les features historiques APC (`histo_*`) sont construites par groupe `(troncon, numero_train)` : pour un tronçon et un numéro de train donnés, on calcule des statistiques glissantes sur les dates précédentes.

Le problème est que les **numéros de train ne sont pas stables d'une année horaire à l'autre**. Lors du changement d'horaire annuel CFF (mi-décembre), les numéros de train peuvent être :

- **Réattribués** : le numéro 6301 peut désigner un service Vevey–Les Pléiades en H23 et un service avec un créneau ou un parcours différent en H24.
- **Abandonnés ou créés** : certains services disparaissent ou apparaissent au changement d'horaire.

Avec `GROUP_KEYS = ["horaire_troncon_tgl", "horaire_numero_train"]`, la fenêtre glissante du premier jour de la nouvelle année horaire hérite de l'historique de l'année précédente — potentiellement celui d'un **service fonctionnellement différent**. Cela crée un mélange de séries non comparables dans les features.

## Décision

**Option 1 retenue — stratégie conservatrice :**

`GROUP_KEYS = ["horaire_annee_horaire", "horaire_troncon_tgl", "horaire_numero_train"]`

Les fenêtres glissantes ne traversent jamais une frontière d'année horaire. Chaque combinaison `(année, troncon, numero_train)` est traitée comme une série indépendante.

## Justification

**Correction du biais de mélange :** sans l'année horaire dans la clé, les premières semaines de chaque nouvelle année horaire pourraient hériter d'un historique non représentatif (service différent, créneau décalé). Cela fausserait les features de lag pour une période critique (nouvelles compositions d'offre).

**Simplicité d'implémentation :** l'option 1 est triviale à implémenter (ajout d'une clé dans le groupby) et facile à valider (contrôle dans `main()` : première obs de chaque groupe → `lag2 = NaN`).

**Coût accepté :** les `LAG_OPERATIONNEL_JOURS` (=2) premières observations de chaque groupe ont `lag2 = NaN`, et les fenêtres win7 démarrent avec `min_periods=1` sur les premières semaines. La perte est de **~7-14 jours de features valides à chaque mi-décembre** (durée du warm-up de la fenêtre 7j), soit une fraction marginale du dataset total.

**XGBoost est robuste aux NaN :** le modèle de la phase suivante gère nativement les NaN en features, donc les premières observations du nouvel horaire ne sont pas perdues — elles sont simplement moins renseignées.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| **Option 1 (retenue)** — interruption aux frontières d'année | Simple, sans risque de contamination inter-années |
| **Option 2** — service_id reconstruit par clustering temporel | Plus complexe ; nécessite une analyse des discontinuités d'horaire ; reportée en analyse de sensibilité éventuelle |
| **Option 3** — conserver `shift` sans clé année, supprimer J-1 à J+1 du changement | Fragile, ne couvre pas les réattributions subtiles de numéros |

## Conséquences

- Les features `histo_*` sont maintenant correctement isolées par année horaire.
- Le merge final ajoute `horaire_annee_horaire` aux clés de jointure entre `daily` et `result` : cohérence garantie si `result` contient bien cette colonne (produite dès stage_01).
- Le contrôle de cohérence dans `main()` valide que la première observation de chaque `(année, troncon, train)` a bien `lag2 = NaN`.

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constante `GROUP_KEYS`
- `notebooks/04_data_preparation.ipynb` — documentation de la stratégie de groupement à mettre à jour
