# Architecture des données — Projet R35 ML

Ce répertoire implémente une architecture en couches calquée sur le modèle médaillon
(bronze / silver / gold) standard en data engineering, adaptée au cadre CRISP-ML(Q).

Chaque couche a une responsabilité stricte. Franchir une couche sans passer par
la précédente est interdit — cela brise la reproductibilité et la traçabilité.

---

## Vue d'ensemble des couches

```
raw/                 Données APC brutes (immuables)
external/            Sources externes brutes (immuables)
    │
    ▼ scripts/sources/
intermediate/        Artefacts de structuration brute (bronze — cas horaires uniquement)
    │
    ▼ scripts/sources/
processed/sources/   Tables propres par source (silver)
dimension/           Référentiels métier (silver — lookup statiques)
    │
    ▼ scripts/pipeline/ (Makefile)
processed/stage_NN   Pipeline d'enrichissement séquentiel (gold en construction)
processed/ml_dataset Dataset ML final (gold)
```

---

## `raw/` — Données APC brutes

Fichiers CSV exports directs du système de comptage automatique de passagers (APC),
un fichier par période horaire. Aucune transformation. Immuables.

---

## `external/` — Sources externes brutes

Données tierces organisées par source. Immuables.

```
external/
├── horaires_r35/      PDF des horaires officiels R35 (MVR/MOB) par année horaire
├── meteosuisse/       Exports historiques MeteoSuisse (stations VEV et CHD, 10 min)
├── istdaten/          Données de ponctualité opentransportdata.swiss (CSV mensuels)
├── evenements/        PDF des manifestations Riviera (2015–2024)
├── statpop/           Registres de population OFS (STATPOP, annuel par commune)
├── ski/               PDFs officiels Coopérative des Pléiades — périodes d'exploitation RM (H20–H25)
├── rotations/         Données de planification MOB — tours de service R35, année horaire H24 (à intégrer)
└── vacances_scolaires/ PDF calendriers scolaires vaudois
```

### Récupération des sources publiques non versionnées (requises par `make clean-all`)

Certaines sources publiques ne sont pas versionnées dans le dépôt mais sont requises par la
reconstruction. Les récupérer avant `make check-sources` puis `make clean-all && make`.

**Calendriers scolaires vaudois** (`vacances_scolaires/`), requis par
`build_dim_vacances_feries_vaud.py` (donc par `make clean-all`, qui reconstruit
`dim_vacances_feries_vaud`). Sources publiques stables de l'État de Vaud, empreintes
vérifiées identiques aux versions d'origine le 2026-07-10 :

```bash
mkdir -p data/external/vacances_scolaires
curl -sSL -o data/external/vacances_scolaires/Vacances_scolaires_vaudoises.pdf \
  https://www.vd.ch/fileadmin/user_upload/organisation/dfj/dgeo/fichiers_pdf/Vacances_scolaires_vaudoises.pdf
curl -sSL -o data/external/vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf \
  https://www.vd.ch/fileadmin/user_upload/themes/formation/Vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf
```

| Fichier | SHA256 attendu |
|---|---|
| `Vacances_scolaires_vaudoises.pdf` | `8a3494690a08d744cd857d23d8fadc9b4982bd933e4f70a8024dad1c94cd313f` |
| `def_calendrier_vacances_scolaires_2023_2031.pdf` | `ba8fed55ae2237e6fc5fc909843029238c36b9ec38e5cd5e8a191c25413e5a73` |

Provenance : État de Vaud, calendriers des vacances scolaires vaudoises (données publiques).
Ces PDF ont été purgés de HEAD sans documentation (voir ADR-075) ; ils restent hors HEAD
puisque récupérables à une URL stable vérifiée.

### Branche refabricable : `statpop_clean_causal.parquet` (ADR-076, ex-entrée figée ADR-075)

Depuis la migration de gel **ADR-076** (gel v2 `ba493568`), la branche STATPOP est **refabriquée
depuis les bruts** : la recette d'origine (forward-fill causal versionné) est promue au pipeline.
`statpop_clean_causal.parquet` est produit par `scripts/sources/build_fact_statpop_gare.py`
(reconstruction VVVI topologie H23 + forward-fill causal LOCF sur les millésimes 2021/2023) et
dépend de STAGE_06 dans le Makefile. Ce n'est **plus une entrée figée** : elle est retirée de la
liste des empreintes SHA de `check-sources`, et **effacée par `make clean-all`** (donc reconstruite
au run vierge).

- **Reproductibilité** : vérifiée par le run vierge (double `make clean-all && make` pinné →
  `ba493568` identique), plus par un SHA épinglé.
- **Périmètre produit** : 88 lignes (topologie complète, comme l'a toujours produit
  `statpop_clean.parquet` d'origine) dont **86 consommées** par la jointure Z-2 (= le périmètre du
  bocal historique `40ae0fe0`) ; 2 lignes inertes `(2021, GIL)` / `(2022, GIL)` (Gilamont disparaît
  en H23, ces millésimes ne sont jamais mappés). La ligne inerte `VVVI-2019` est ajoutée à la lecture
  par `add_statpop` (patch inline, jamais recherchée par la jointure).
- **Ancrages** : forward-fill causal reproduit les valeurs d'origine (CHBL/HTV/STLE `hpi_classe_max`
  2021=1, 2023=2). L'ancien bocal figé `40ae0fe0` (rétro-déduit Float32) et le script de
  rematérialisation sont archivés sous `scripts/archive/` (voir ADR-076, décision 6).

### Entrée figée : `statent_clean_causal.parquet` (ADR-075)

`statent_clean_causal.parquet` (emploi STATENT, grain `(annee_enquete_statent,
gare_abreviation)`, 91 lignes) est une **entrée figée sans producteur canonique**.

- **SHA256 attendu** : `cede91b9e9dd69329a5b081ae7dd7591700ddb7b95889595b19269d2c2155efe`.
- **Preuve d'absence de producteur** : le seul script existant,
  `archive/explorations/scripts_exp/statent_integration_exp.py` (marqué HORS CANONIQUE),
  est lié au dataset expérimental v1.3 (`ml_dataset_v1.3.parquet`, absent), écrit un autre
  fichier (`statent_clean_exp.parquet`) dont le contenu **diffère** du survivant (empreinte
  `ca31fe27`, 86 lignes contre 91). Aucun script committé ou archivé ne reproduit
  `statent_clean_causal.parquet`.
- **Portée** : les colonnes emploi alimentent le dataset gelé (`stage_06b`) mais sont
  **exclues des 158 features** du modèle. L'entrée reste néanmoins requise pour reproduire
  `ba493568` byte-exact.
- `make clean-all` **n'efface pas** cette entrée figée (déjà hors de sa liste de suppression).

---

## `intermediate/` — Structuration brute (bronze)

Artefacts produits par le parsing de sources non-tabulaires, **avant** nettoyage
et sélection finale.

**Règle d'utilisation :** un fichier atterrit ici uniquement quand la transformation
structurelle (parsing PDF, reconstruction de calendrier d'exploitation, etc.) produit
plusieurs tables intermédiaires réutilisables indépendamment de la table propre
finale — et que le script de structuration est distinct du script de nettoyage.

**Pourquoi cette couche n'existe pas pour MeteoSuisse ou STATPOP :** pour les sources
CSV, la structuration (fusion de fichiers, parsing de timestamps) et le nettoyage
(suppression de colonnes vides, déduplication) se font en un seul passage sans
produire d'artefact intermédiaire utile de façon autonome. Les deux couches sont
naturellement collapsées dans un seul script `sources/`.

Contenu actuel : tables horaires R35 extraites des PDF (arrets_officiels,
troncons_template, calendrier_circulation, notes_circulation, extraction_audit).

---

## `processed/sources/` — Tables propres par source (silver)

Une table par source de données. Grain et schéma stabilisés. Prêtes pour
la jointure. Ne contiennent pas encore de features ML construites.

| Fichier | Source brute | Script producteur |
|---------|-------------|-------------------|
| `apc_stacked.parquet` | `raw/*.csv` (4 périodes) | `sources/stack_raw_csv.py` |
| `meteo_vev_clean.parquet` | MeteoSuisse VEV 10 min | `sources/build_meteosuisse_vev_clean.py` |
| `meteo_chd_clean.parquet` | MeteoSuisse CHD 10 min | `sources/build_meteosuisse_chd_clean.py` |
| `horaires_clean.parquet` | PDF horaires R35 | `sources/build_horaires_r35_from_pdfs.py` |
| `istdaten_clean.parquet` | opentransportdata (CSV mensuels) | `sources/build_fact_istdaten_r35.py` |
| `istdaten_ponctualite.parquet` | opentransportdata — agrégat ponctualité J | `sources/build_istdaten_ponctualite.py` |
| `statpop_clean.parquet` | STATPOP OFS (annuel/commune) | `sources/build_fact_statpop_gare.py` |

---

## `dimension/` — Référentiels métier

**Critère :** une table va dans `dimension/` si c'est un référentiel métier stable —
liste de gares, plages d'années horaires, calendrier de vacances scolaires,
liste de manifestations planifiées — qu'on pourrait maintenir manuellement
ou qui provient d'une source externe légère sans transformation volumique.

**Contraste explicite avec `processed/sources/` :** `statpop_clean` est dans
`processed/sources/` car il est produit par agrégation d'un dataset de ~100 000
lignes/an (STATPOP par commune) avec un join géospatial vers les gares R35. Il
n'est pas maintenable manuellement.

`dim_vacances_feries_vaud`, `dim_manifestations_riviera` et `dim_gare` sont dans
`dimension/` car ce sont des listes d'entités ou de périodes construites depuis
des PDF ou des fichiers de référence légers, sans agrégation volumique.

| Fichier | Contenu | Script producteur |
|---------|---------|-------------------|
| `annees_horaires.csv` | Plages début/fin de chaque année horaire CFF | manuel |
| `dim_gare.parquet` | Liste des gares R35 (BPUIC, coordonnées, km) | `sources/build_dim_gare.py` |
| `dim_vacances_feries_vaud.parquet` | Calendrier vacances scolaires et jours fériés vaudois | `sources/build_dim_vacances_feries_vaud.py` |
| `dim_manifestations_riviera.parquet` | Manifestations Riviera agrégées par date | `sources/build_dim_manifestations_riviera.py` |
| `dim_manifestations_riviera_evenements.parquet` | Manifestations grain événement (1 ligne/événement) | `sources/build_dim_manifestations_riviera.py` |
| `dim_vmcv_lignes_concurrentes.parquet` | Lignes VMCV concurrentes à la R35 | `sources/build_vmcv_lignes_concurrentes.py` |
| `dim_ski_pleiades.parquet` | Périodes d'exploitation officielles du ski des Pléiades (H20–H25, 530 jours) | `sources/build_dim_ski_pleiades.py` |
| `dim_rotations_r35.parquet` | Tours de service R35 H24 — rattachement courses → tours pour la couche de décision UM (cf. ADR-007) | `sources/build_rotations_r35_2024.py` (à créer) |

---

## `processed/stage_NN_*.parquet` — Pipeline d'enrichissement (gold)

Enrichissement séquentiel : chaque stage joint une source propre à la table
principale APC. La séquence est strictement linéaire. Le préfixe numérique encode
l'ordre d'exécution ; le suffixe `b` indique un enrichissement secondaire au sein
d'un même groupe thématique (ex. `stage_03b` = deuxième enrichissement événementiel).

La pipeline est divisée en deux sous-phases CRISP-ML(Q) distinctes :

- **Stages 01–07 — Data integration** : jointures de sources externes uniquement.
  Chaque stage ajoute une table `processed/sources/` ou `dimension/` sans dériver
  de features. Le grain et le nombre de lignes restent constants.
- **Stage 08 — Feature construction** : toutes les features dérivées en un seul
  passage (lags sur la cible, composantes calendaires, lag J-1 sur la ponctualité,
  moyennes mobiles). Aucune nouvelle source externe n'est jointe ici.

Cette séparation permet de rejouer le feature engineering (stage 08) sans
retoucher les jointures amont, et inversement.

```
apc_stacked               ← point d'entrée (processed/sources/)

# Data integration — jointures de sources externes
stage_01_annee_horaire    ← + dimension annees_horaires
stage_02_calendrier       ← + dim_vacances_feries_vaud
stage_03_manifestations   ← + dim_manifestations_riviera
stage_03b_ski             ← + dim_ski_pleiades          (event_is_ski_ouvert)
stage_04_meteo_vev        ← + meteo_vev_clean
stage_05_meteo_chd        ← + meteo_chd_clean
stage_06_statpop          ← + statpop_clean
stage_07_ponctualite      ← + istdaten_ponctualite  (jointure J-1)

# Feature construction — features dérivées
stage_08_features         ← lags cible (1j/7j), composantes calendaires,
                             lags ponctualité (7j/28j/même type de jour)

ml_dataset                ← sélection finale des colonnes ML
```

Voir `Makefile` à la racine du projet pour les dépendances complètes et les
commandes de rejeu partiel.

---

## `qualitative/` — Données de la phase qualitative

Transcriptions d'entretiens (P01–P06), grilles de codage, résultats d'analyse
thématique. Séparé du pipeline ML car produit selon un protocole de recherche
qualitative distinct (anonymisation, codage thématique, saturation théorique).

Voir `qualitative/README.md` pour le protocole de collecte et d'analyse.

---

## Invariants à respecter

1. **Sens unique** : les données ne remontent jamais d'une couche vers une couche
   supérieure. Un script `pipeline/` ne modifie jamais `processed/sources/`.

2. **Immuabilité des entrées** : `raw/` et `external/` ne sont jamais écrits
   par un script de pipeline.

3. **Reproductibilité** : `make check-sources` (présence et empreintes des entrées figées
   et sources requises) puis `make clean-all && make` reproduit `processed/` et le dataset
   gelé `ba493568` (gel v2) depuis `raw/`, `external/`, `dimension/` et les entrées figées (ADR-075).
   L'ancien invariant `make clean && make` ne rejouait que les stages, en préservant sources
   et dimensions ; il ne mettait donc pas à l'épreuve la reconstruction complète.

4. **Traçabilité par script** : chaque script `sources/` doit écrire un artefact
   d'audit indiquant au minimum : nombre de lignes lues et écrites, plage de dates
   couverte, taux de valeurs manquantes sur les colonnes critiques.
   Référence : `processed/horaires_r35_extraction_audit.csv`.
