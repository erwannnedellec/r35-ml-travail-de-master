---
id: ADR-016
ancien_id: ADR-16
date_decision: 2026-05-15
statut: révoqué
revoque_par: [ADR-019, ADR-038]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-016 — Stabilité des numéros de train R35 sur la période modélisable

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-019, ADR-038.
> **Précision au gel.** La stabilité des numéros de train constatée ici ne vaut plus après la refonte d'horaire H25 : ADR-038 relève que 100 % des heures de départ à l'origine ont changé.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-15

## Contexte

Les numéros de train CFF/MVR sont réutilisés d'horaire en horaire et peuvent
correspondre à des services différents (heure, sens) après les changements
d'horaire annuels de mi-décembre. Le pipeline `build_dim_profil_train.py`
groupe les rolling windows 7j et 28j par `numero_train` sans tenir compte
de ces transitions, ce qui pourrait théoriquement mélanger les statistiques
de deux services distincts.

Le risque a été investigué avant validation du pipeline.

## Diagnostic quantitatif

Analyse des transitions d'horaire entre 2018 et 2024 :

| Transition  | Δ < 5 min | Δ 5-30 min | Δ ≥ 30 min | Sens changé | REAL avant/après |
|-------------|-----------|------------|------------|-------------|-------------------|
| H18→H19     | 35%       | 16%        | 49%        | 3%          | 0% / 0%           |
| H19→H20     | 89%       | 8%         | 2%         | 1%          | 0% / 0%           |
| H20→H21     | 96%       | 4%         | 0%         | 0%          | 0% / 0%           |
| H21→H22     | 100%      | 0%         | 0%         | 0%          | 0% / 0%           |
| H22→H23     | 96%       | 4%         | 0%         | 3%          | 0% / 0%           |
| H23→H24     | 100%      | 0%         | 0%         | 0%          | ~88% / ~88%       |

## Constat

La seule transition d'horaire incluse dans la fenêtre de données ISTDATEN
exploitables (REAL/GESCHAETZT à partir de juillet 2023) est H23→H24,
qui présente 100% de stabilité (108/108 trains).

Les transitions plus anciennes affichent des taux de changement significatifs
(notamment H18→H19 lors de la réforme du cadencement MVR-cev), mais elles
se situent intégralement dans une période sans données réelles. Les rolling
windows par numero_train ne calculent donc rien sur ces périodes, et aucune
contamination des statistiques n'est possible.

## Décision

Conserver le groupement par `numero_train` simple dans `build_dim_profil_train.py`,
sans introduire de `service_id` composite. La modification ne serait pas
neutre (perte d'historique au début de chaque horaire, complexification du
pipeline) et n'apporterait aucun bénéfice empirique.

## Conséquences

- Pipeline préservé en l'état, pas de modification de scripts.
- Documentation explicite du raisonnement quantitatif dans cet ADR.
- Si une future année de données introduit une transition instable (par
  exemple H24→H25 avec un changement majeur), cette décision devra être
  revue. À surveiller au moment de l'extension du pipeline en production.

---

## Annexe — Exploration empirique : encodage composite numéro × heure d'origine

**Date** : 2026-05-16

### Motivation

Même si les rolling windows se groupent par `numero_train` sans risque
(décision ci-dessus), la question se pose pour la feature identité de train
donnée en entrée du modèle XGBoost. Si deux services distincts partagent
un `numero_train` sur des années horaires différentes, le modèle pourrait
apprendre une association erronée.

Pour trancher empiriquement, une troisième variante d'encodage est introduite :
`horaire_service_id_complet = f"{numero_train}_{heure_origine:%Hh%M}"`.
L'heure d'origine est l'heure de départ théorique (ISTDATEN) du **premier
arrêt** du train ce jour-là, commune à tous les tronçons du même service.

### Trois variantes comparées dans Dataiku

| Modèle | Dataset | Feature identité de service |
|--------|---------|------------------------------|
| A | ml_dataset.parquet | `horaire_numero_train` |
| B | ml_dataset_service_id.parquet | `horaire_service_id_complet` |
| C | ml_dataset_sans_train_id.parquet | aucune |

Les trois datasets sont produits par `build_ml_dataset.py` via l'argument
`--variante-encodage-service {numero_seul,service_id_seul,aucun}`.

### Critères de décision

- Si R²(A) ≈ R²(C) → la feature identité n'apporte pas de signal ; utiliser C.
- Si R²(A) > R²(C) → signal réel ; comparer A vs B :
  - R²(A) ≈ R²(B) → encodage numéro seul suffit (A retenu, plus simple).
  - R²(B) > R²(A) → l'identifiant composite apporte un gain ; retenir B.

### Validité de l'identifiant composite sur H23→H24

La transition H23→H24 est 100% stable (108/108 trains, cf. tableau ci-dessus).
L'identifiant composite est donc cohérent entre train (H22-H23) et test (H24) :
les modalités vues à l'entraînement correspondent aux mêmes services en production.
