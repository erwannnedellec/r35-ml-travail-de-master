---
id: ADR-076
ancien_id: aucun
date_decision: 2026-07-11
statut: actif
modifie: [ADR-052, ADR-066, ADR-075]
corroboration_date: dépôt de travail, commit du 2026-07-11
gel_registre: 2026-08-16
---

# ADR-076 - Migration de gel : dataset v2 (correction du producteur narcisses + promotion de la recette STATPOP au pipeline)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-052, ADR-066, ADR-075.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Adopté le 2026-07-11 (migration exécutée : gel v2 `ba493568` produit, double run pinné byte-reproductible) |
| **Date** | 2026-07-11 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-075 (STATPOP entrée figée, amendé par le présent) ; ADR-063 (mapping STATPOP Z-2, forward-fill causal) ; ADR-066 (gouvernance des empreintes de hash) ; ADR-055 (correction Voronoï VVVI) ; ADR-011 (imputation millésimes STATPOP) ; ADR-039 (mapping STATPOP par année, carry-forward H25) |
| **Ancien gel** | `416bb90b` (v1.9, gelé le 2026-06-21) |
| **Nouveau gel** | **`ba493568`** (H2, double run vierge pinné byte-identique, GATE 3 le 2026-07-11) |
| **Environnement** | pyarrow 21.0.0, pandas 2.3.3 (ADR-066, ADR-074) |

---

## Contexte

Le gel canonique courant `416bb90b` (v1.9) porte deux défauts de pipeline documentés, tous deux de nature « procédé », non « valeur » :

1. **Producteur dim_narcisses non maintenu sur H25.** `scripts/sources/build_dim_narcisses.py` code une fenêtre calendaire (15 avril - 25 mai) bornée par une constante figée à une année passée (`WINDOW_END = 2024-12-31`). La boucle de construction itère de 2015 à 2024 inclus : la saison de floraison du printemps 2025, qui tombe dans la saison horaire H25, est absente du parquet (date max observée : 2024-05-25). La dim ne couvre donc pas la fin de la période de données.

2. **Branche STATPOP non refabricable par le code committé.** ADR-075 a établi que `statpop_clean_causal.parquet` (empreinte `40ae0fe0`) n'est pas reproductible depuis le code du dépôt : elle a été produite par un procédé manuel non versionné, puis rematérialisée depuis le dataset gelé lui-même (Piste B, rétro-déduction Float32) et figée par empreinte. Le code committé, appliqué aux bruts, produit des valeurs divergentes à cause d'une garde trop stricte (`notna().all()`, `build_fact_statpop_gare.py:980-981`) qui neutralise la surcharge d'imputation et laisse un fallback `bfill().ffill()` non causal. ADR-075 a explicitement classé cette garde « point connu, hors périmètre, non corrigé ».

L'archéologie de refabrication (rapport `docs/rapports/archeologie_statpop_phase2_refabrication.md`) a depuis produit une recette d'origine versionnée (`scripts/experiences/rebuild_statpop_origine.py`) qui reproduit les valeurs du bocal figé : zéro divergence sur les colonnes discrètes (dont le résidu discriminant `hpi_classe_max` des gares du haut CHBL/HTV/STLE), égalité à rtol 1e-4 sur les continues. La refabrication par le forward-fill causal depuis les bruts est donc prouvée.

**Précision du diagnostic d'ADR-075 (interception dans notre propre analyse).** ADR-075 attribuait la divergence STATPOP à la garde `notna().all()` (« trop stricte »). L'analyse d'implémentation de la présente migration montre que la garde n'était que le **symptôme** : le geste canonique reproduit par le gel `416bb90b` est le **forward-fill intégral** (report du millésime précédent sur toutes les colonnes imputées, continues comme catégorielles), et non un « max des voisins » corrigé — ce dernier donnerait 2021=2 là où le canonique et le forward-fill donnent 2021=1. C'est la troisième interception d'une erreur par le mécanisme de vérification, cette fois dans notre propre diagnostic ; la traçabilité doit le montrer, pas le lisser (l'addendum d'ADR-075, phase 5, portera la même précision).

Un contrôle d'ampleur préalable sur l'effet du défaut narcisses (commit `14f25fe`, rapport `docs/rapports/check_narcisses_temps1.md`) concluait à un effet vraisemblablement marginal sur les métriques.

## Motif de la migration : qualité d'artefact, pas résultats

Cette migration est décidée pour **corriger deux défauts de procédé du pipeline**, afin que le gel soit intégralement refabricable byte-exact depuis les bruts et les entrées figées documentées restantes (statent, dim_rotations : non refabricables par nature, ADR-075), sans étape manuelle et sans entrée figée qui SERAIT refabricable en principe. La distinction est : STATPOP était figée par accident de procédé (corrigeable, donc corrigée) ; statent et dim_rotations sont figées par indisponibilité de source (non corrigeable). Ce n'est **pas** une optimisation de résultats :

- Le check préalable `14f25fe` concluait à un effet marginal du défaut narcisses ; la migration n'est pas engagée dans l'attente d'un gain.
- La correction STATPOP ne change **pas** la sémantique des valeurs : le gel `416bb90b` avait déjà, par le procédé ad hoc, appliqué le forward-fill causal (valeurs causalement correctes, cf. ADR-075). Promouvoir la recette d'origine ne fait que rendre ce geste **refabricable par le code**, sans en modifier le résultat sémantique.

En clair : le seul changement de **valeur** attendu porte sur les features narcisses en 2025 (mai-juin H25). Le changement de **hash** est, lui, inévitable (voir Justification, point 1).

## Périmètre fermé

Deux corrections, rien d'autre. L'audit de périmètre (GATE 0) a confirmé que rien d'autre n'y entre :

1. **dim_narcisses** : producteur versionné corrigeant le **mécanisme** (pas seulement la constante), couvrant H16-H25 (2025 inclus) et paramétrable pour les années futures.
2. **Branche STATPOP** : promotion de la recette d'origine (forward-fill causal) au pipeline ; l'entrée figée `40ae0fe0` se dissout au profit d'une cible refabriquée par la chaîne.

**Hors périmètre, confirmé par l'audit 0a :**

| Dimension | Mécanisme | Couverture H25 | Décision |
|---|---|---|---|
| dim_manifestations_riviera | Parse dynamique de PDFs annuels (source externe maintenue) | COUVRE (max 2025-12-31) | inchangée |
| dim_ski_pleiades | `OFFICIAL_PERIODS` maintenu jusqu'à H25/H26 + PDFs | COUVRE (max 2025-12-13) | inchangée |
| covid | Zéro 2025 factuel | sans objet | inchangée |

Aucune dim à grain ligne n'est modifiée : la volumétrie du gel v2 est attendue identique (voir Invariants GATE 3).

## Décision

1. **Producteur dim_narcisses versionné (correction du mécanisme).** La fenêtre courante n'est plus bornée par une constante figée à une année passée : la couverture est dérivée de la dernière période de données présente (ou paramétrée), de sorte que le producteur ne « s'oublie » plus d'une année sur l'autre. La règle calendaire (15 avril - 25 mai) est conservée ; les features narcisses restent dans les 158, seules leurs valeurs changent sur 2025.

2. **Garde de couverture, mutualisable.** Une fonction commune (pas trois copies) fait échouer bruyamment le build si une dim événementielle ne couvre pas la fin de la dernière période de données, avec un message renvoyant au présent ADR. Dans ce gel, la garde s'applique à **narcisses** uniquement. Son extension à ski et manifestations est **recommandée mais non appliquée** ici : l'appliquer changerait leurs parquets, ce qui sortirait du périmètre fermé (voir Justification, point 2).

3. **Suppression du fossile `OFFICIAL_DATES`.** Le dictionnaire `OFFICIAL_DATES` (vide), la branche `_get_window_for_year` qui le teste et les avertissements associés sont supprimés ; la section « approche v2 - calendrier officiel » du docstring est taillée. Un commentaire indique que la règle est purement calendaire (15 avril - 25 mai), calibrée empiriquement, et qu'aucune source officielle n'existe (voir Justification, point 3).

4. **Promotion de la recette STATPOP d'origine au pipeline.** Le forward-fill causal (LOCF, report du millésime précédent) devient l'imputation du producteur, appliqué à **toutes** les colonnes imputées (continues et catégorielles `hpi_classe_max`/`flag`), via `impute_forward_fill_causal`. L'imputation non-causale d'époque (interpolation linéaire par index + max des millésimes adjacents avec fallback backward-fill gardé par `notna().all()`) est **substituée, pas corrigée** : la garde `notna().all()`, symptôme et non cause, disparaît avec le bloc qu'elle gardait (une garde « corrigée » donnerait le max des voisins, soit 2021=2, divergent du canonique 2021=1). Le fix VVVI H23 est **intégré** au producteur (`build_vvvi_rows_h23`, millésimes 2020-2022). Une règle Make produit `statpop_clean_causal.parquet` depuis les bruts ; STAGE_06 en dépend.

   **Répartition VVVI (producteur / consommateur).** Le producteur reconstruit les millésimes VVVI **actifs pour la consommation** (2020-2022, topologie H23) — le périmètre exact du bocal (86 lignes). La ligne **inerte VVVI-2019** reste ajoutée à la **consommation** (`_patch_vvvi_statpop`), jamais mobilisée par la jointure Z-2 : le consommateur est laissé inchangé (risque nul, sémantique consommée préservée). Cette répartition est documentée ici pour qu'un lecteur découvrant l'ajout côté consommation en comprenne la raison sans archéologie.

5. **check-sources : statpop sort des entrées figées.** Une cible refabriquée par la chaîne se vérifie par la reproductibilité du run vierge, pas par un SHA épinglé. `statpop_clean_causal.parquet` est retiré de la liste des empreintes figées de `scripts/check_sources.sh`. **`statent_clean_causal.parquet` et `dim_rotations_r35.parquet` restent des entrées figées** (non refabricables, ADR-075) et conservent leur vérification SHA.

6. **Archivage de la chaîne manuelle retirée (DEUX fichiers).** L'item archive `scripts/rematerialise_statpop_clean_causal.py` (Piste B, rematérialisation depuis le gelé) **et** `scripts/sources/fix_vvvi_statpop_2022.py`, devenu orphelin de l'imputation supprimée (il importait `impute_missing_millesimes`). Les deux relèvent de la même chaîne manuelle qu'ADR-075 nomme ensemble ; déplacés sous `scripts/archive/` (git mv, archivés, pas supprimés). L'archéologie `scripts/experiences/rebuild_statpop_origine.py` reste intacte (pièce probante, n'importe pas la fonction supprimée).

7. **Ce gel est le dernier.** L'engagement de gel unique est réaffirmé : tout défaut découvert après le GATE 3 sera **documenté**, pas corrigé par un re-gel. La leçon de gouvernance d'ADR-075 (aucune étape manuelle hors contrôle de version) est appliquée d'avance : double run vierge de confirmation dès la naissance du gel.

## Justification

### 1. Corriger STATPOP proprement IMPLIQUE le changement de hash (la migration est la condition de la correction)

Le bocal `40ae0fe0` a été rétro-déduit en Float32 depuis le dataset gelé `416bb90b` (Piste B, ADR-075). Un rebuild depuis les bruts (Piste A) est déterministe et byte-reproductible run à run, mais calcule des valeurs Float64 fraîches qui, après optimisation Float32, ne peuvent **pas** coïncider bit-à-bit avec des valeurs elles-mêmes rétro-déduites d'un Float32 (résidu de précision documenté à 1069 cellules, rapport phase 2). La sémantique est identique (discrètes exactes, continues à rtol 1e-4), mais l'empreinte se déplace.

Conclusion : rendre la branche STATPOP refabricable par le code **implique** que le hash change. La migration n'est donc pas seulement un choix de propreté superposé au résultat ; elle est la **condition** de la correction. On ne peut pas à la fois exiger la refabrication byte-exacte depuis les bruts et conserver `416bb90b`.

### 2. Diagnostic mécanistique de l'audit 0a : un défaut de mécanisme, pas de constante

L'audit de couverture (GATE 0a) montre que le défaut n'est pas une constante oubliée mais un **mécanisme sans rappel** : les dims adossées à une source externe re-parsée se maintiennent seules (manifestations : PDFs annuels ; ski : `OFFICIAL_PERIODS` tenu à jour + PDFs), tandis que la seule dim tirée d'une constante figée sans garde s'oublie (narcisses). La correction attaque donc le mécanisme (fenêtre dérivée + garde de couverture bruyante), pas la valeur d'une année.

La garde de couverture est conçue **mutualisable** parce que le besoin est générique : à l'horizon H27, la ligne H26 de ski (`OFFICIAL_PERIODS`, qui s'arrête au jour d'ouverture) présentera le même risque. La garde est proposée pour ski et manifestations mais **non appliquée dans ce gel** : l'activer changerait leurs parquets (donc le hash au-delà du périmètre fermé). C'est une recommandation pour un chantier ultérieur, hors migration.

**Horizon narcisses vs garde.** Le producteur couvre jusqu'à un horizon paramétré (`COVERAGE_END_YEAR = 2030`), volontairement en avance sur les données. Cet horizon reste une **constante future** : ce n'est pas lui qui corrige le mécanisme, c'est la **garde de couverture** (échec bruyant au join). Sans la garde, la constante reproduirait le défaut en 2031 ; avec elle, l'oubli devient impossible silencieusement. L'horizon n'est qu'une borne de confort qui évite un échec prématuré ; la garde est le rappel.

### 3. Vérification négative OFFICIAL_DATES : fermer la question du relecteur

Recherche exhaustive au 2026-07-11 (`find` sur `data/`, grep `OFFICIAL_DATES` et `narciss` sur le dépôt) : **aucune source de dates officielles de floraison n'existe** (Coopérative des Pléiades ou Montreux-Vevey Tourisme jamais obtenues). Le dictionnaire vide était le vestige d'une « approche v2 à privilégier » jamais réalisée : un fossile qui piège le prochain lecteur en suggérant une donnée jamais saisie. Il est supprimé. Cette vérification négative est consignée ici pour fermer d'avance la question « pourquoi pas les dates officielles ? » qu'un relecteur poserait.

### 4. Effet attendu marginal : la migration n'est pas motivée par les résultats

Le check `14f25fe` concluait à un effet vraisemblablement marginal du défaut narcisses. Combiné au point 1 (STATPOP sémantiquement inchangé), l'attente préenregistrée est que les métriques H25 bougent peu, sauf éventuellement dans la seule zone où un effet narcisses est concevable (rappel HAUT mai-juin 2025). La migration est publiée que ces métriques montent, baissent ou stagnent.

### 5. Le double run vierge révèle un non-déterminisme environnemental (4e interception)

Le double run vierge de confirmation (exigence née de la leçon ADR-075 : tester la promesse avant de la faire) a révélé un non-déterminisme environnemental **pré-existant** : Apple Accelerate (BLAS multi-thread), réductions flottantes non-associatives, environ 1 run sur 3, différences à l'ULP. Quatrième interception d'un défaut par le mécanisme de vérification, et la **première portant sur l'environnement d'exécution lui-même**. Remède : threads numériques fixés à 1 dans le Makefile (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS = 1`) ; le contrat de reproductibilité couvre désormais **code + données + environnement** (pinning pyarrow 21.0.0 ADR-066, threads ADR-076).

**Note rétroactive (sans réécriture d'ADR-066/075).** L'assertion de reproductibilité de `416bb90b` (ADR-075) reste exacte : un replay `clean-all && make` a reproduit l'empreinte. Mais la reproductibilité **systématique run-à-run** n'avait jamais été éprouvée par double run indépendant, et l'environnement multi-thread ne la garantissait pas. Le gel v2 est le premier à naître avec cette preuve.

## Protocole : iso-protocole strict

Seules les données changent. Sont tenus rigoureusement identiques :

- **Hyperparamètres** couche 1 (ADR-052/CF09, robustesse ADR-071/CF27).
- **Split** temporel C (ADR-065 : exclusion Gilamont H22, reste de H22 conservé).
- **Segmentation** bas/haut (ADR-049) au seuil de surcharge 63 (ADR-060).
- **Procédure de calibration** couche 2 sur H24 (ADR-073) : la procédure est rejouée à l'identique ; les valeurs des seuils a'/b/c peuvent bouger, la procédure non.
- **Définitions d'évaluation** : iso-périmètre, grain course, points d'opération, conventions de coût (tare, tarif OFT).

Le non-rejeu des décisions de conception (fonction de perte, hyperparamètres, split, segmentation) est délibéré : les données d'entraînement et de validation sont invariantes entre les générations (seul le test H25 est matériellement corrigé, sur les valeurs narcisses) ; rejouer ces choix sur des données identiques n'apporterait que du bruit de graine et romprait le contrôle expérimental qui rend le tableau comparatif interprétable. Seul ce qui dérive mécaniquement des prédictions est rejoué : calibration couche 2 (procédure identique, valeurs de seuils recalculées) et évaluation.

## Évaluation préenregistrée

Le tableau comparatif ancien (`416bb90b`) / nouveau (H2) sera publié **intégralement**, quels que soient les résultats. Colonnes préenregistrées (GATE 4) : R² par segment (bas/haut/global), PR-AUC, les 3 points d'opération (volume/précision/rappel), baseline humaine (attendue inchangée par construction : à vérifier), nombre de surcharges 2 072 (attendu IDENTIQUE si les données APC n'ont pas changé : garde), capture des 166+, coûts FP (volets B/C rejoués), rappels par strate. Focus dédié : rappel HAUT mai-juin 2025 ancien vs nouveau, et SHAP des features narcisses nouvelle génération. Les chiffres de la génération `416bb90b` deviennent la **colonne de comparaison**, pas la garde de conformité.

**Discipline de lecture (GATE 4).** Le tableau comparatif est livré en **chiffres bruts, sans interprétation directionnelle** : la lecture (montée, baisse, stagnation ; attribution des écarts) se fait au GATE, pas dans le livrable. Le contrat porte ainsi sur la discipline de lecture autant que sur la discipline de publication.

## Sort de l'ancien gel

`416bb90b` et l'intégralité de ses résultats restent la **trace historique** : ils ne sont pas effacés. Les ADR à chiffres d'époque (ADR-052, ADR-060, ADR-062, ADR-063, ADR-066, ADR-073, ADR-075, entre autres) reçoivent une **note de génération** listée dans INDEX.md (« chiffres de la génération `416bb90b` »), **pas une réécriture**. La migration est un chapitre supplémentaire, pas un effacement.

**Artefacts nommés au hash (inventaire 0b-A).** Les fichiers de la génération `416bb90b` portant le hash dans leur nom (`codebook_canonique_416bb90b.csv`, `outputs/couche2/q_couche2_*_416bb90b.json`, `models/enrichi_seg/enrichi_seg_{bas,haut}_416bb90b.json`) ne sont **PAS supprimés** : ils sont archivés ou conservés côte à côte avec ceux de la génération H2, selon la convention de chaque dossier. La phase 5 tranchera fichier par fichier. L'ADR pose le **principe** : aucune destruction de la génération précédente.

## Invariants attendus au GATE 3

- **Volumétrie identique** : 1 141 984 lignes, 209 colonnes, mêmes 158 features (les features narcisses restent dans les 158 ; seules leurs valeurs changent sur 2025). Tout écart de volumétrie déclenche un STOP.
- **Gel reproductible dès la naissance** : deux `make check-sources` puis `make clean-all && make` indépendants produisent H2 byte-exact (double run vierge de confirmation).

## Feuille de route de la propagation documentaire (phase 5)

L'inventaire exhaustif des références au hash `416bb90b` (fichiers nommés au hash, contenus citant le hash, artefacts INTACTS de `archive/`) a été dressé au GATE 0b. Il sert de feuille de route à la phase 5 (codebook renommé, README, en-têtes de notebooks canoniques 03c/APC/08, note de génération INDEX, régénération ALL_ADRS, reprises manuscrit). Il n'est pas dupliqué ici : renvoi au rapport d'audit de périmètre GATE 0.

## Conséquences

- **Positif** : le gel v2 devient intégralement refabricable byte-exact depuis les bruts (plus d'entrée figée refabricable en principe pour STATPOP) ; le producteur narcisses ne s'oublie plus ; la garde de couverture rend le défaut de mécanisme détectable à l'avenir.
- **Assumé** : le hash canonique change (`416bb90b` → H2) ; les chiffres publiés des ADR d'époque deviennent « génération `416bb90b` », signalés par note.
- **Entrées figées restantes** : `statent_clean_causal.parquet` et `dim_rotations_r35.parquet` demeurent figées (non refabricables par indisponibilité de source, ADR-075) ; elles ne sont pas touchées par la présente migration.
- **Amende ADR-075** : le point « garde `notna().all()`, hors périmètre, non corrigée » d'ADR-075 est **résolu** par le présent ADR non en corrigeant la garde mais en **retirant le bloc d'imputation non-causal qu'elle gardait** (substitué par le forward-fill causal) ; le statut d'entrée figée de STATPOP y est également révisé (dissolution au profit d'une cible refabriquée). ADR-075 reste actif pour statent et dim_rotations. Un addendum daté du 2026-07-11 est porté dans ADR-075 lui-même (doctrine d'immutabilité : un ADR amendé porte son amendement chez lui), rédigé en phase 5 avec la propagation documentaire, portant aussi la précision du diagnostic (garde = symptôme, forward-fill = geste canonique).
- **Consécration de H2 et sort des candidats** : le canonique **H2 = `ba493568`** est le hash déterministe single-thread, prouvé par deux runs vierges pinnés byte-identiques (GATE 3). Il **coïncide avec la variante multi-thread majoritaire** (runs vierges #2 et #3 avant pinning) : le pinning n'a pas déplacé la valeur, il a garanti sa reproductibilité. `0358f308` (run vierge multi-thread #1) était l'**outlier** de l'aléa Accelerate, consigné ici pour la seule trace. Aucun candidat n'ayant servi à quoi que ce soit, il n'y a pas de propagation à faire.
- **Threads numériques fixés à 1** (Makefile, ADR-076) : condition de reproductibilité, pas une optimisation. Le single-thread peut allonger la durée du run ; la reproductibilité prime sur la vitesse pour un gel (durées relevées au GATE 3).

## Addendum (2026-07-30) - La fenêtre narcisses 15.04 -> 25.05 est un choix a priori, jamais calibré

**Objet.** Correction documentaire du producteur `scripts/sources/build_dim_narcisses.py`. Aucune
donnée, aucune constante, aucune logique n'est modifiée : l'empreinte canonique
`ba493568` est inchangée et `dim_narcisses.parquet` est byte-identique avant et après
(vérification de régénération en mémoire, 656 lignes, SHA256 `1a4f0a1f...ce2f68e`).

**Constat.** Un audit documentaire des sources calendaires et événementielles a établi que la
fenêtre 15 avril -> 25 mai **n'a fait l'objet d'aucune calibration empirique**, contrairement à ce
qu'affirmait le docstring du producteur. Éléments matériels :

- La fenêtre figure **dès le premier commit** du producteur (`02b88e8`, 2026-06-04), sous la
  formulation « Cette fenêtre **est à calibrer** via EDA sur les pics de fréquentation
  Blonay -> Pléiades observés dans les APC (NB05 - Feature Analysis) ». Elle y était explicitement
  qualifiée d'« Approche v1 - règle calendaire (**fallback**) », c'est-à-dire de valeur de repli.
- La phase 2 de la présente migration (`3623693`, 2026-07-11) a réécrit ce passage en « Cette
  fenêtre **est calibrée empiriquement** via EDA [...] », **sans qu'aucune calibration ne soit
  intervenue** entre les deux commits. Le point 3 de la section « Décision » du présent ADR
  (« Un commentaire indique que la règle est purement calendaire (15 avril - 25 mai), calibrée
  empiriquement ») reprend la même assertion : elle est **erronée** et le présent addendum la
  corrige, conformément à la doctrine d'immutabilité du corps (le corps porte la trace de ce qui
  a été écrit, l'addendum porte la correction).
- Aucun code de notebook ne dérive les bornes (recherche des motifs `04-15`, `05-25`,
  `REGLE_CALENDAIRE` dans les sources de cellules de tous les `notebooks/*.ipynb` : aucun
  résultat). Les seules occurrences sont dans les **sorties stockées** de
  `notebooks/02_data_understanding_evenements.ipynb`, qui affichent la couverture d'une dimension
  déjà construite.
- Le renvoi « NB05 - Feature Analysis » est par ailleurs incohérent avec la numérotation du
  dépôt : les notebooks 05 sont des évaluations de modèle, la Feature Analysis est le notebook 06.

**Correction appliquée ce jour.** Le docstring de `scripts/sources/build_dim_narcisses.py`
(section « Règle calendaire ») et le commentaire précédant les constantes `REGLE_CALENDAIRE_*`
énoncent désormais que la fenêtre est un **choix a priori**, posé comme valeur de repli en
l'absence de calendrier de floraison, et qu'elle **n'a fait l'objet d'aucune calibration
empirique**. Les quatre constantes `REGLE_CALENDAIRE_*` sont **inchangées**.

**Ce qui reste vrai et n'est pas remis en cause.** Le point 3 de la « Justification » du présent
ADR (vérification négative `OFFICIAL_DATES` : aucune source de dates officielles de floraison
n'existe) est confirmé par l'audit. La correction de mécanisme portée par cette migration
(`COVERAGE_END_YEAR` + garde de couverture au join) est également confirmée : elle porte sur la
**couverture** de la dimension, non sur la **position** de la fenêtre.

**Versé aux perspectives.** Une calibration de la fenêtre est possible et souhaitable, à une
condition de protocole : elle doit être conduite **sur les seules années d'entraînement**
(H22-H23, et H24 en validation selon le split retenu), à l'exclusion de H25, année de test
out-of-time. Toute calibration mobilisant H25 constituerait une sélection post-lecture du jeu
d'évaluation. Cette perspective n'est **pas** exécutée ici : elle changerait les valeurs de la
dimension et donc l'empreinte du dataset gelé.

**Statut.** Le présent addendum est documentaire. Il ne modifie ni le périmètre, ni le protocole,
ni les résultats de la migration ADR-076, qui restent adoptés en l'état.
