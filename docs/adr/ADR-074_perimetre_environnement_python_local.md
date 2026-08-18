---
id: ADR-074
ancien_id: aucun
date_decision: 2026-07-09
statut: actif
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-07-09
gel_registre: 2026-08-16
---

# ADR-074 - Périmètre d'environnement : artefact intégralement en Python local, déploiement Dataiku écarté du travail de master

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (2026-07-09) |
| **Date** | 2026-07-09 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-003, ADR-016, ADR-017, ADR-027, ADR-030, ADR-031 (expérimentations conduites dans Dataiku, jalons historiques) ; ADR-052 (modèle final couche 1) ; ADR-073 (POC couche 2) |

## Contexte

En début de projet, l'exploration de modélisation était conduite dans l'environnement Dataiku (DSS), et le déploiement opérationnel alors envisagé y était rattaché (voir `CONTEXT.md` et l'ADR-003, « pipeline de prédiction et d'interprétabilité SHAP à déployer dans Dataiku »). Plusieurs ADR datent de cette phase et s'appuient sur des runs Dataiku : les variantes de modèle (ADR-016), l'ablation de `horaire_numero_train` (ADR-017), le split temporel (ADR-027), la révision de stratégie (ADR-030) et le verdict de segmentation (ADR-031), avec des valeurs de référence issues de ces runs (dont un R² de 0.613).

## Décision

**Volet (a) : migration complète du cycle vers Python local.** La lignée canonique du projet (dataset `ml_dataset.parquet` = `416bb90b`, modèle Enrichi_Seg v1.9, couche 2 de décision, résultats canoniques) est intégralement née et vit dans l'environnement **Python local versionné** : pipeline médaillon orchestré par le `Makefile`, code sous `src/` et `scripts/`, suite de tests `tests/`. Les **expérimentations** initiales conduites dans Dataiku (les runs d'entraînement, de comparaison et d'évaluation, et les valeurs qui en sont issues, dont le R² de référence de 0.613) sont des **jalons historiques non reproductibles depuis le présent dépôt**. En revanche, les **décisions** actées par les ADR de cette phase (ADR-016, ADR-017, ADR-027, ADR-030, ADR-031) demeurent régies par leur propre chaîne de statut dans `docs/adr/INDEX.md` ; les plus structurantes (segmentation BAS/HAUT, principe du split temporel) ont été confirmées par la re-fondation en Python. **Le présent ADR ne supersède aucun des ADR cités.**

**Volet (b) : déploiement opérationnel hors périmètre du travail de master.** Le déploiement opérationnel de l'artefact (mise en production, intégration au système d'information de l'exploitant, exploitation en continu) est **hors du périmètre du travail de master**. Il relèverait d'une **décision d'entreprise ultérieure**. L'artefact livré est un POC d'aide à la décision (voir ADR-073).

## Justification

- Le travail de master porte sur la **conception et l'évaluation** de l'artefact (démarche Design Science Research), et non sur son industrialisation.
- Un pipeline **versionné, reproductible et testé** en Python local sert mieux les exigences de traçabilité et de reproductibilité de la thèse (empreinte de dataset byte-exacte, ADR, tests de non-régression) qu'un environnement où le versionnement au même grain n'est pas garanti.
- La consolidation a re-fondé la lignée canonique en Python, rendant l'environnement Dataiku initial redondant pour le périmètre finalement retenu.

## Conséquences

- Les scripts liés à Dataiku (`scripts/dataiku/recipe_force_dtypes.py`, recette de forçage des types pour le chargement dans Dataiku, non référencée par la chaîne active) sont archivés sous `archive/deprecated/scripts_dataiku/`.
- Les documents vivants (`CONTEXT.md`, docstrings du code actif) sont corrigés : la notion de « déploiement cible Dataiku » est remplacée par le périmètre effectif (artefact Python local ; déploiement hors périmètre du travail de master).
- Les ADR datés mentionnant Dataiku restent **intacts** (contrats préenregistrés) ; `docs/adr/INDEX.md` porte une note générale renvoyant au présent ADR, sans superséder aucun ADR.
- Passes ultérieures : les notebooks livrables et le manuscrit seront mis à jour ; en particulier, le R² de référence Dataiku (0.613) du notebook 05 (`R2_DATAIKU_REF`) est à étiqueter comme jalon historique non reproductible avec renvoi au présent ADR, ou à retirer.
