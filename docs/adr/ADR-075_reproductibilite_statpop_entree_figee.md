---
id: ADR-075
ancien_id: aucun
date_decision: 2026-07-10
statut: amendé
amende_par: [ADR-076]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-07-10
gel_registre: 2026-08-16
---

# ADR-075 - Reproductibilité de la branche STATPOP : entrée figée rematérialisée depuis le dataset gelé, invariant clean-all redéfini

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-076.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (2026-07-10) |
| **Date** | 2026-07-10 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-074 (périmètre Python local) ; ADR-063 (mapping STATPOP Z-2, causalité) ; ADR-025 (millésime contemporain) ; ADR-073 (POC) |

## Contexte

Le premier `make clean-all && make` depuis les sources brutes n'avait **jamais été exécuté de bout en bout** avant le 2026-07-09. Sa première exécution a révélé **trois ruptures** de la chaîne de reconstruction :

1. PDF `data/external/vacances_scolaires/` (Vaud) : source publique purgée de HEAD (commit `ec28f4a`) sans règle `.gitignore` ni documentation.
2. `data/processed/sources/statpop_clean_causal.parquet` : rupture de nommage (la recette Makefile écrit `statpop_clean.parquet`) **et** de contenu (le code committé ne reproduit pas les valeurs canoniques).
3. `data/processed/sources/statent_clean_causal.parquet` : prérequis de `stage_06b` sans règle make (produit par un script archivé).

Le message du commit `aa230a8` (2026-07-07 ; « pipeline canonique reproduisant le dataset gelé 416bb90b », mention « STATPOP causal carry_forward ») était un **overclaim** : cette reproduction n'avait jamais été vérifiée de bout en bout, et elle est **fausse pour la branche STATPOP** telle que produite par le code committé. Ce constat confirme rétrospectivement la réserve émise dans le rapport d'audit (§1.1.4) sur la valeur probante limitée de l'historique git.

## Verdict d'investigation (étape 2b)

- **Entrées STATPOP stables** : empreintes SHA256 et dates de publication OFS (STATPOP2021.csv 2022-07-20, STATPOP2023.csv 2024-08-20) antérieures au gel v1.9 (2026-06-21). Il n'y a **pas de dérive d'entrée**.
- **Le code actuel appliqué aux données actuelles reproduit le dataset DIVERGENT**, pas le canonique (établi par le run `clean-all` et par un test d'imputation isolé). L'écart est confiné à la branche STATPOP, et pour `hpi_classe_max` aux trois gares du haut CHBL, HTV, STLE (valeurs identiques).
- Millésimes d'ancrage (données brutes, non imputées) de ces trois gares : **2020 = 1, 2022 = 2, 2024 = 1**. Les millésimes 2021 et 2023 sont imputés (les CSV OFS de ces millésimes ne portent pas de données HPI).
- **Ce que fait le code committé** : pour les indicateurs catégoriels (`hpi_classe_max`), la surcharge « maximum des millésimes adjacents » **ne se déclenche jamais**, sa garde `notna().all()` exigeant que TOUTES les gares soient non-NA au millésime voisin, condition jamais satisfaite du fait des gares historiquement inactives (CLIE fermée après H18, GIL après H22, VVVI active seulement à partir de H23). L'imputation retombe sur son défaut `bfill().ffill()`, soit un **backward-fill** (valeur du millésime **suivant**) : 2023 ← 2024 = **1**. C'est un **look-ahead**, contraire au principe de causalité Z-2 (ADR-063).
- **Ce que faisait l'imputation ad hoc canonique** : un **forward-fill (carry_forward, LOCF)**, valeur du millésime **précédent** : 2023 ← 2022 = **2**. Causalement correct.
- La valeur canonique (2) est donc **plus sensée** que celle du code (1) : le procédé manuel a appliqué la règle causale (report du passé), tandis que le fallback du code emprunte au futur. La garde `notna().all()`, qui rend la surcharge inopérante et laisse s'appliquer ce fallback non causal, est **identifiée comme trop stricte** (défaut latent, présent au code depuis `02b88e8`, antérieur au gel). Elle **n'est PAS corrigée** ici : la corriger changerait le comportement de reconstruction et sortirait du périmètre. **Point connu, documenté, hors périmètre.**

Conclusion : la branche STATPOP du dataset gelé **n'est pas reproductible depuis le code committé**. Elle a été produite par un procédé manuel non versionné (`build_fact_statpop_gare.py` + `fix_vvvi_statpop_2022.py` + renommage manuel + imputation hpi ad hoc par forward-fill).

## Décision

1. `statpop_clean_causal.parquet` devient une **entrée figée documentée**, **rematérialisée depuis le dataset gelé lui-même** (Piste B) par le script versionné `scripts/rematerialise_statpop_clean_causal.py`. Ce n'est pas une copie de confiance mais une **reconstruction vérifiée** : inversion prouvée **exacte en valeur sur les 209 colonnes** du dataset (zéro divergence au replay diagnostique), **unicité par couple** vérifiée (assertion départ == arrivée sur les couples partagés), cas limites **documentés individuellement** (CLIE seule gare absente de la couverture ; HTV-2023 seul couple d'aire incohérent, aire interpolée ; VVVI-2019 ligne inerte ajoutée par le patch inline à la lecture). Empreinte contractuelle : **`40ae0fe0`** (86 lignes ; grain `(annee_enquete_statpop, gare_abreviation)`).
2. Le **schéma** de l'entrée figée est **dérivé du gelé par rétro-déduction** des dtypes (inversion de `_optimize_dtypes`, `stage_07`), pas déclaré : gelé Float32 implique amont Float64 ; gelé Int16/Int32 implique amont Int64. `menages_500m_total` est en Float64, cicatrice de l'`interpolate` de `fix_vvvi`.
3. Le **replay complet** de la chaîne aval avec cette entrée figée **reproduit `416bb90b` byte-exact** (vérifié 2026-07-10 ; suite de tests à la baseline d'alors, 195 passés / 35 skippés / 0 échec ; le test de stabilité ajouté en conséquence du présent ADR porte le décompte au-delà, voir Conséquences).
4. L'**invariant de reproductibilité** est redéfini : `make check-sources` (présence et empreintes des entrées figées et sources requises), **puis** `make clean-all && make`. Il remplace l'ancien invariant `make clean && make`.
5. Le **contrat reste `416bb90b`** : aucun re-gel, aucune modification de contenu du dataset, aucun réentraînement. Le code actif (`add_statpop`, patch inline `_patch_vvvi_statpop`, garde `notna().all()`) reste **inchangé**.

## Justification : leçon de gouvernance

Un hash de sortie ne vaut contrat de reproductibilité que si le **procédé qui le produit est intégralement sous contrôle de version, sans étape manuelle**. Le cas STATPOP en montre le coût : trois interventions manuelles non tracées (fix_vvvi non câblé, renommage, imputation hpi ad hoc) invisibles au dépôt, qui ont rendu le canonique irreproductible et fait passer un overclaim (`aa230a8`) pour un fait.

**Règle** : toute intervention manuelle sur une donnée intermédiaire, **même manifestement juste** (comme l'imputation hpi ad hoc, causalement plus correcte que le fallback du code), doit être **scriptée ou tracée par un ADR au moment où elle est faite**. À défaut, elle devient une dette de reproductibilité.

## Conséquences

- Quatre commits de plomberie, un par rupture : fetch documenté des PDF vacances (Rupture 1) ; script de rematérialisation + recette Makefile corrigée + entrée figée documentée (Rupture 2) ; règle make ou entrée figée pour statent (Rupture 3) ; cible `make check-sources` (invariant).
- Un **test pytest de stabilité du patch inline** : `_patch_vvvi_statpop` appliqué à l'entrée figée ne modifie aucune ligne existante (différence purement additive sur une ligne non référencée, VVVI-2019). Le décompte de la suite passe au-delà de 230, à réconcilier avec le manuscrit.
- `make clean-all` **épargne désormais les entrées figées** (ne les supprime plus).
- Mise à jour du §5 du rapport de clôture, de la section Reproduction du README racine, et des reprises manuscrit.
- La garde `notna().all()` reste un **point connu, hors périmètre** (non corrigée).

## Addendum (2026-07-10) - `dim_rotations_r35` sous protection d'entrée figée documentée

Constat postérieur (chantier 1bis, compréhension des données des rotations). La table `data/dimension/dim_rotations_r35.parquet` n'est **pas régénérable à l'identique** par la chaîne actuelle :

- elle **fait foi par son empreinte** SHA256 `688e943b5ea9...` (vérifiée par `make check-sources`) ;
- sa **provenance** est `rotations_22_24.csv` (colonne `source_version` sur toutes les lignes), **brut d'exploitation absent du dépôt** ;
- le brut présent au dépôt est `rotations_23_25.csv` ; une **régénération depuis ce brut produirait une table différente**, ce qui **changerait silencieusement la baseline UM humaine** dont cette table est la **source de vérité** (couche 2, comparatif central) ;
- la table est **hors du hash `416bb90b`** (elle ne participe pas au dataset gelé) et **déjà épargnée par `clean-all`** ; l'enjeu est plus étroit que la branche STATPOP, d'où la **magnitude addendum** (pas de nouvel ADR).

**Décision.** `dim_rotations_r35` est qualifiée d'**entrée figée documentée**, même famille de gouvernance que la branche STATPOP, magnitude moindre. Protections :

1. **Recette `make dims` neutralisée** : la cible `$(DIM_ROTATIONS)` est remplacée par une **garde bloquante** (échec explicite renvoyant à cet addendum), prérequis retirés pour qu'aucun changement de brut ne rende la cible périmée. Le geste destructeur est désarmé **en amont**.
2. **Empreinte vérifiée par `check-sources`** (présence + SHA256 complet), au même standard que `statpop_clean_causal` et `statent_clean_causal` ; filet **complémentaire** en aval.

La protection est assurée par le **couple garde `make` + `check-sources`** ; **pas de test pytest dédié**, la table ne subissant **aucune transformation à la lecture** (contrairement au patch inline STATPOP, qui a son test de stabilité).

La provenance divergente est **documentée, non corrigée** (le brut d'origine n'est pas réintroduit) : la table gelée fait foi.

## Addendum (2026-07-11) - Migration ADR-076 : dissolution de l'entrée figée STATPOP, précision du diagnostic

La migration de gel **ADR-076** (dataset v2, hash `ba493568`) révise trois points du présent ADR :

1. **Dissolution du statut d'entrée figée de `statpop_clean_causal`.** La branche STATPOP est promue au pipeline : `statpop_clean_causal.parquet` est désormais **refabriquée depuis les bruts** par le forward-fill causal versionné (`build_fact_statpop_gare.py`), et **retirée** de la liste des empreintes figées de `check-sources`. Sa reproductibilité se vérifie par le run vierge (double `make clean-all && make` pinné), plus par un SHA épinglé. Le présent ADR **reste actif** pour `statent_clean_causal` et `dim_rotations_r35`, entrées figées par indisponibilité de source (non corrigeables).

2. **Précision du diagnostic (garde = symptôme, forward-fill = geste canonique).** Le présent ADR attribuait la divergence STATPOP à la garde `notna().all()` (« trop stricte »). L'analyse d'implémentation d'ADR-076 montre que la garde n'était que le **symptôme** : le geste canonique reproduit par `416bb90b` est le **forward-fill intégral** (report du millésime précédent, colonnes continues comme catégorielles), non un « max des voisins » corrigé — ce dernier donnerait 2021=2 là où le canonique donne 2021=1. La garde disparaît avec le bloc d'imputation non-causal qu'elle gardait, substitué par le forward-fill (ADR-076, décision 4).

3. **Reproductibilité systématique.** L'assertion de reproductibilité de `416bb90b` (décision, point 3) reste exacte (un replay `clean-all && make` a reproduit l'empreinte), mais la reproductibilité **systématique run-à-run** n'avait jamais été éprouvée par double run indépendant ; l'environnement multi-thread (Apple Accelerate) ne la garantissait pas (non-déterminisme flottant rare). Le gel v2 fixe les threads numériques à 1 (Makefile) et naît avec la preuve du double run pinné byte-identique.

Voir **ADR-076** pour le détail complet de la migration.
