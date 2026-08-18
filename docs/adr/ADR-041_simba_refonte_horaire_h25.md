---
id: ADR-041
ancien_id: ADR-43
date_decision: 2026-06-05
statut: remplacé
remplace_par: [ADR-056]
revoque_par: [ADR-061]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-05
gel_registre: 2026-08-16
---

# ADR-041 — Gestion de la refonte d'horaire H24→H25 sur les features SIMBA

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-056 ; révoquée par ADR-061.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** Les variables `simba_*` dont ce document règle la valeur manquante sont **retirées du modèle** par ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-04 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-026 (intégration SIMBA FQkal, mapping N-1), ADR-038 (extension périmètre H25), ADR-039 v2 (convention `_source` STATPOP), ADR-040 (convention `_source` VMCV) |

## Contexte

L'extension du périmètre temporel à H25 (ADR-038) confronte la pipeline SIMBA à un phénomène nouveau, non rencontré sur H22-H24 : la refonte d'horaire CFF/MOB de décembre 2024 a renuméroté une partie substantielle des trains R35.

L'ADR-026 a établi le mapping `simba_millesime = horaire_annee_horaire − 1` (donc H25 → SIMBA 2024), avec une jointure clé sur le numéro de train. Cette jointure produit désormais une couverture partielle sur H25 :

- 51 trains conservés depuis H24 (49 % des trains) : match SIMBA 2024 complet (160 147 obs, 51.8 % de H25)
- 52 trains renumérotés (50 %) : aucun match avec SIMBA 2024 (143 867 obs, 46.5 % de H25)
- 1 train à couverture partielle — train 1416, 6.2 % NaN, probable restructuration en cours d'année

En volume d'observations, **46.6 % des lignes H25 sont sans valeur SIMBA**. La distribution est stable temporellement (~46 % sur tous les mois de janvier à décembre 2025) et concentrée sur certaines sous-populations :

| Sens | Segment | NaN SIMBA H25 |
|---|---|---|
| PLEI → VV | bas | 35.9 % |
| PLEI → VV | haut | 43.4 % |
| VV → PLEI | bas | 53.9 % |
| VV → PLEI | haut | 63.9 % |

Par type de jour : ouvrable 50.8 %, dimanche/férié 35.7 %, samedi 34.8 %.

SIMBA 2025 est disponible dans `dim_simba_r35` (millésimes disponibles : 2022, 2023, 2024, 2025) et permettrait techniquement une jointure secondaire récupérant 99.8 % des observations actuellement NaN (les 52 trains renumérotés sont tous présents dans SIMBA 2025). Cette option est rejetée pour raison méthodologique (cf. décision ci-dessous).

## Options considérées

| Option | Description | Forces | Faiblesses |
|---|---|---|---|
| A. NaN tracé (état actuel) | Conserver le NaN produit par la jointure N-1, ajouter une colonne de traçabilité `simba_source_*` | Cohérence stricte avec règle N-1 d'ADR-026 ; pas de leakage ; transparence | 46.6 % du test set H25 sans valeur SIMBA |
| B. Jointure secondaire SIMBA 2025 | Compléter par SIMBA 2025 pour les 52 trains renumérotés | Récupère 99.8 % de couverture | Leakage circulaire : SIMBA(N) corrélé avec APC(N) selon ADR-026 — invalide pour une évaluation OOT rigoureuse |
| C. Substitution carry-forward SIMBA 2024 par mapping ad-hoc | Mapper les numéros H25 renumérotés vers leurs équivalents fonctionnels H24 | Tentative de récupération sans leakage | Mapping ad-hoc impossible à valider rigoureusement ; aucune garantie de correspondance fonctionnelle entre numéros |

## Décision

**Option A retenue pour l'évaluation principale du mémoire** : conserver le NaN produit par la jointure SIMBA 2024 sur H25, avec ajout de deux colonnes de traçabilité `simba_source_depart` / `simba_source_arrivee`.

Justifications :

1. **Cohérence avec le principe méthodologique d'ADR-026** : l'ADR-026 a établi le lag N-1 systématique pour éviter le leakage circulaire SIMBA(N) ↔ APC(N) (r=0.97 documenté). Utiliser SIMBA 2025 pour H25 réintroduirait ce leakage que la pipeline est précisément conçue pour éviter. Le principe d'ADR-026 prime sur la maximisation de couverture.

2. **Précision sur ce que "cohérence N-1" signifie** : appliquer N-1 strictement ne garantit pas la disponibilité uniforme du signal SIMBA. Pour les 46.6 % de lignes H25 dont le train n'existe pas dans SIMBA 2024, l'application du principe N-1 produit du NaN — pas du signal. La cohérence méthodologique est dans l'application uniforme du principe (pas de SIMBA N), pas dans la disponibilité uniforme du signal.

3. **Importance secondaire de SIMBA au classement SHAP** : les features `simba_*` apparaissent dans la moitié inférieure du classement SHAP du modèle B référence (ADR-036). L'impact attendu du NaN sur 46.6 % de H25 est mesurable mais limité, particulièrement sur le segment bas où d'autres features (cal_*, histo_*, resa_*) portent l'essentiel du signal.

4. **Gestion native XGBoost** : XGBoost apprend une direction par défaut pour les NaN via la pression du gradient. Sur les features SIMBA, le routage est appris sur les 100 % NaN de H22 (SIMBA 2021 indisponible, ADR-026) et les NaN naturels de H23-H24 (5.1 % et 4.4 %). Ce routage est donc déjà calibré pour des NaN SIMBA substantiels, contrairement aux features rares en NaN sur le training set.

5. **Cohérence avec ADR-039 v2 et ADR-040** : la convention `_source` est établie pour STATPOP (carry-forward) et VMCV (interruption). L'ajouter pour SIMBA maintient la cohérence narrative du projet : trois sources annuelles, trois ADR documentant trois phénomènes distincts avec une convention de traçabilité unifiée.

## Option B comme analyse de sensibilité (non principale)

L'option B (jointure secondaire SIMBA 2025) est **conservée comme analyse de sensibilité supplémentaire en annexe du mémoire**. L'objectif est de quantifier empiriquement :

- L'impact marginal d'une couverture SIMBA complète vs partielle sur le R² et le PR-AUC H25
- Si l'effet est négligeable (< 0.005 R²), cela valide rétrospectivement la décision Option A
- Si l'effet est substantiel, cela documente quantitativement le coût méthodologique du respect du principe N-1

Cette analyse est explicitement présentée comme sensibilité dans le mémoire, pas comme métrique principale.

## Convention de traçabilité

Deux colonnes ajoutées au stage_09 (script `scripts/pipeline/add_simba_to_raw_stacked.py`, fonction `joindre_simba`) :

- `simba_source_depart`
- `simba_source_arrivee`

| Valeur | Signification | Années horaires concernées |
|---|---|---|
| `match_simba_n_minus_1` | Match réussi avec millésime SIMBA N-1 (règle standard ADR-026) | H23, H24, H25 (trains conservés) |
| `manquant_simba_n_minus_1` | Aucun match (millésime N-1 indisponible ou train absent) | H22 (100 %), H25 (46.6 % — refonte d'horaire) |

Convention cohérente avec `event_ski_source`, `event_narcisses_source`, `event_covid_phase`, `spatial_statpop_source_*` (ADR-039 v2), `vmcv_source_*` (ADR-040).

**Important** : `simba_source_depart` et `simba_source_arrivee` sont des métadonnées de traçabilité. Elles doivent être ajoutées à `COLS_EXCLUES` du notebook synthèse (aux deux endroits où cette liste apparaît) avant l'entraînement du modèle final.

## Conséquences

### Positives

- Cohérence méthodologique stricte avec ADR-026 sur tout le périmètre H22-H25
- Pas de leakage SIMBA(N) ↔ APC(N) sur le test set H25
- Traçabilité complète via colonnes `simba_source_*` — audit post-entraînement possible par stratification
- Documentation d'un phénomène réel (refonte d'horaire 2024-2025) que tout projet ML opérationnel en transport public doit anticiper

### Limitations à documenter dans le mémoire

- **46.6 % du test set H25 sans valeur SIMBA** : le modèle s'appuie sur ses 167 autres features actives pour ces observations. Sous-populations particulièrement touchées : sens VV→PLEI ouvrables (53.9 % NaN bas, 63.9 % NaN haut).
- **Phénomène à anticiper pour le déploiement opérationnel** : toute refonte d'horaire ultérieure (changement annuel CFF mi-décembre) sera potentiellement affectée. Un mécanisme de mapping numéro_train H_N → H_(N-1) par caractéristiques opérationnelles (heure d'origine, sens, tronçons desservis) pourrait être conçu lors d'une itération MLOps future.

## Validation empirique au moment de l'entraînement

Au moment de l'évaluation sur H25, conduire :

1. **Stratifier les métriques H25 par `simba_source_depart`** :
   - Métriques sur lignes `match_simba_n_minus_1` (51.8 %)
   - Métriques sur lignes `manquant_simba_n_minus_1` (46.5 %)
   - Si ΔR² < 0.01 entre les deux sous-populations : impact SIMBA négligeable, Option A validée
   - Si ΔR² > 0.02 : documenter en limite explicite

2. **SHAP des features `simba_*` sur H25** : confirmer que le rang reste dans la moitié inférieure (cohérence ADR-036). Une remontée significative dans le classement signalerait que la couverture partielle crée un biais de signal.

3. **Analyse de sensibilité Option B** (annexe) : entraîner un modèle avec jointure SIMBA 2025 pour les 52 trains renumérotés et mesurer l'écart de métriques.

## Addendum — ADR-061 (2026-06-11) : décision rendue caduque pour le modèle courant

L'ADR-061 (2026-06-11) acte le retrait définitif des 12 features `simba_*` du modèle Enrichi_Seg, pour raisons structurelles (instabilité inter-annuelle, leakage de disponibilité, 46.6 % NaN H25). La décision Option A de cet ADR-041 (NaN tracé, cohérence méthodologique stricte) reste valide pour la **compréhension des données et la traçabilité pipeline** — elle documente un phénomène réel (refonte d'horaire CFF/MOB) que tout projet ML opérationnel en transport public doit anticiper. Mais la question du NaN SIMBA dans le modèle prédictif n'a plus d'objet : les features `simba_*` ont été retirées du modèle.

La validation empirique prévue au §"Validation empirique au moment de l'entraînement" est réalisée à titre documentaire dans ADR-061 (les métriques stratifiées par `simba_source_depart` ont été calculées sur le modèle 170f avant retrait).

## Références

- `scripts/pipeline/add_simba_to_raw_stacked.py` — modification dans `joindre_simba()`, lignes après le `assert`
- ADR-026 — Intégration SIMBA FQkal, mapping N-1, leakage r=0.97
- ADR-038 — Extension périmètre H25
- ADR-039 v2 — Convention `simba_source_*` analogue pour STATPOP
- ADR-040 — Convention `vmcv_source_*` analogue pour VMCV
- ADR-036 — Modèle B référence, classement SHAP de référence
- [ADR-061](ADR-061_retrait_simba_features.md) — retrait features simba_*, modèle v1.1 158f (supersède la décision feature de cet ADR)
- Rapport audit pré-entraînement, 04.06.2026 (Audit C — SIMBA join failure, hash dataset cd29a5f2)
