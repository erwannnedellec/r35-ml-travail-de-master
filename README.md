# R35 ML — code de l'artefact

Code de l'artefact du travail de master (MSc HES-SO en Business Administration, orientation
Management des Systèmes d'Information) portant sur la ligne ferroviaire régionale
**R35 Vevey – Blonay – Les Pléiades**, exploitée par MVR (groupe MOB).

L'artefact estime la charge voyageurs de 2ᵉ classe par tronçon et par course, puis convertit
cette estimation en recommandation d'engagement d'une seconde automotrice, à l'horizon de la
veille pour le lendemain (J-1).

> **Le mémoire fait foi.** Ce dépôt contient tout le code nécessaire à la reproduction de
> l'état scientifique final : chaîne de construction du jeu de données, entraînement des deux
> modèles finaux, couche décisionnelle, suite de confirmation, suite de tests, et registre des
> décisions de conception — ainsi que les générateurs des figures, des tableaux et des
> vérifications du manuscrit lui-même. Muni de l'archive de données, `make reproduce` rejoue la
> chaîne de bout en bout, et `make reproduce-memoire` régénère ensuite les figures et les
> tableaux du mémoire. Le dépôt ne porte en revanche ni les notebooks d'exploration, ni les
> expériences abandonnées.

> Mis à disposition **à des fins d'évaluation académique** uniquement. Voir [LICENSE](LICENSE).

---

## Contenu

| Emplacement | Contenu |
|---|---|
| `Makefile` | Chaîne de reproduction du jeu de données canonique (architecture médaillon) |
| `scripts/sources/` | Construction des tables propres, une par source |
| `scripts/pipeline/` | Chaîne d'enrichissement séquentielle, invoquée par le Makefile |
| `src/couche2/` | Couche décisionnelle : score de course, seuils, plancher de réservation, restitution |
| `src/r35/constants.py` | Constantes du domaine : capacités, seuils, topologie de la ligne |
| `scripts/experiences/` | Entraînement des deux modèles finaux, configuration de déploiement (ADR-077), compléments de la section 4.5.7, dérivation des cas d'entretien |
| `scripts/confirmation/` | Suite de confirmation post-gel — résultats du chapitre 4.5 ([README dédié](scripts/confirmation/README.md)) |
| `tests/` | Suite de non-régression complète (223 fonctions), exécutable sans les données |
| `docs/memoire/` | Générateurs des figures, tableaux et vérifications du manuscrit — **92 scripts** (89 générateurs et 3 modules partagés), rangés en trois familles (`figures/`, `tableaux/`, `verifs/`) puis par **sous-section du mémoire**, à l'endroit où leur produit est cité pour la première fois |
| `archive/explorations/` | Artefacts des campagnes lues par ces générateurs : optimisation d'hyperparamètres (ADR-071), comparatif d'algorithmes (ADR-072), pertes alternatives (ADR-051), variables calendaires cantonales (ADR-070) |
| `docs/adr/` | Registre des décisions de conception — 78 ADR + `INDEX.md` |
| `models/enrichi_seg/` | Modèles gelés de la couche 1 |
| `data/` | **Vide de données.** Arborescence attendue documentée dans [`data/README.md`](data/README.md) |

## Architecture

**Couche 1 — prédiction.** Deux régresseurs XGBoost segmentés par position du tronçon
(BAS pendulaire Vevey–Blonay, HAUT touristique Blonay–Les Pléiades), aiguillés à l'inférence.
158 variables, dont 6 catégorielles en prise en charge native. Perte quadratique, 300 arbres,
profondeur 6, pas d'arrêt anticipé, graine 42, hyperparamètres identiques pour les deux segments.
Entraînement sur H22–H24 (hors tronçons Gilamont de H22), évaluation hors temps sur H25.

**Couche 2 — décision.** Le score de course est le **maximum** des charges prédites sur ses
tronçons. Un menu de trois seuils calibrés sur H24 (a′ iso-volume, b rappel renforcé, c haute
précision) produit la recommandation, complétée d'un **plancher de réservation** déterministe et
sans paramètre appris : recommandation dès que les voyageurs de 2ᵉ classe réservés en groupe
excèdent strictement 63.

## Données

Les données d'exploitation sont **confidentielles et ne figurent pas dans ce dépôt** : comptages
automatiques de voyageurs (APC), registre des rotations, réservations de groupes, données SIMBA.
Les sources externes mobilisées sont publiques ou institutionnelles (ISTDATEN
d'opentransportdata.swiss, MétéoSuisse, STATPOP et STATENT de l'OFS, calendriers scolaires
vaudois, programmes de manifestations) mais ne sont pas redistribuées ici.

**Mise en place.** Une archive est transmise séparément au directeur de thèse. Elle contient
l'arborescence `data/` complète, telle que décrite dans [`data/README.md`](data/README.md).
Décompresser l'archive et **copier ses dossiers dans `data/`** à la racine du dépôt :

```
data/
├── raw/            comptages APC bruts
├── external/       sources externes, un dossier par source
├── dimension/      référentiels métier
└── processed/      produit par `make` — ne rien y déposer
```

Le `.gitignore` ignore l'ensemble : déposer les données ne risque pas de les versionner.

## Reproduction

```bash
python3.9 -m venv venv
venv/bin/pip install -r requirements.txt
```

Une fois les données en place, **une seule commande rejoue toute la chaîne scientifique** :

```bash
make reproduce
```

Elle enchaîne, en s'arrêtant au premier écart :

| Étape | Cible | Produit | Durée indicative |
|---|---|---|---|
| 1. Jeu canonique | `reproduce-dataset` | `data/processed/ml_dataset.parquet` → **`ba493568`** | ~25 min |
| 2. Couche 1 | `reproduce-couche1` | baseline humaine, **modèles `e4ddfccd` / `df6a11c5`**, métadonnées, calibration H24, évaluation H25 | ~10 min |
| 3. Couche 2 | `reproduce-couche2` | configuration de déploiement (ADR-077), annexes quantitatives | ~2 min |
| 4. Confirmation | `reproduce-confirmation` | `outputs/confirmation/c01…c10.json` — résultats du chapitre 4.5 | ~40 min |
| 5. Compléments | `reproduce-complements` | contrefactuel et SHAP narcisses, cas d'entretien, dictionnaire des colonnes | ~5 min |
| 6. Manuscrit | `reproduce-memoire` | figures, tableaux et vérifications du mémoire — **90 scripts rejoués, 2 SKIP documentés** | ~20 min |

**Le contrôle décisif est l'étape 2.** Le réentraînement iso-protocole des deux modèles doit
rendre exactement les empreintes archivées — `make check-models` est appelé automatiquement et
interrompt la chaîne en cas d'écart. Les modèles livrés sont copiés dans `models/_reference/`
avant d'être réécrits.

### Ce qui a été vérifié, et comment

La chaîne a été rejouée en **deux temps, sur deux bancs distincts**. Les deux preuves sont
complémentaires : ni l'une ni l'autre ne couvre seule la chaîne entière.

| | Ce qui a été rejoué | Résultat obtenu |
|---|---|---|
| **16 août 2026** | étape 1 seule : sources figées → `data/processed/ml_dataset.parquet` | empreinte **`ba493568`**, **à l'octet près** |
| **18 août 2026** | étapes 2 à 6 : `ba493568` → tout l'aval, depuis un clone vierge et un environnement neuf monté depuis `requirements.txt` | réentraînement **`e4ddfccd` / `df6a11c5`** conforme ; **9 artefacts sur 9** identiques au dépôt de travail ; suite de tests 203 passés, 35 ignorés, 0 échec |

Le run du 18 août n'a **pas** reconstruit le jeu de données. Il l'a lié depuis le dépôt de travail,
a contrôlé son empreinte avant tout calcul, puis a passé `-o data/processed/ml_dataset.parquet` à
`make` pour le déclarer à jour. La reconstruction depuis les sources avait été validée deux jours
plus tôt, et la seule modification intervenue entre les deux dates porte sur `docs/memoire/`,
c'est-à-dire en aval du jeu.

Mises bout à bout, les deux vérifications couvrent la chaîne complète — **sources → `ba493568` →
modèles gelés → couche décisionnelle → figures, tableaux et chiffres du manuscrit**. C'est
exactement ce que `make reproduce` enchaîne, en une commande, pour un tiers partant des seules
sources.

Chaque étape est aussi exécutable seule. Pour rejouer uniquement le jeu de données :

```bash
make check-sources          # présence et empreintes des entrées figées
make clean-all && make      # reconstruit data/processed/ml_dataset.parquet
```

La reconstruction doit rendre l'empreinte **`ba493568`** (SHA256 tronqué) à l'octet près. Le
contrat de reproductibilité couvre **code + données + environnement** : sans l'épinglage de
`pyarrow==21.0.0` et sans la fixation des bibliothèques de calcul à un seul fil d'exécution
— imposée par le Makefile (`OMP/OPENBLAS/MKL/NUMEXPR/VECLIB_MAXIMUM_THREADS=1`) — le BLAS
multi-thread introduit un non-déterminisme flottant rare.

Deux entrées restent figées, non refabricables par indisponibilité de source :
`statent_clean_causal` et `dim_rotations_r35` (ADR-075). Le hash `416bb90b` est la trace
historique du gel antérieur à la migration ADR-076.

Trois contrôles ne demandent pas les données :

```bash
make check-models           # empreintes des deux modèles gelés
make check-guards           # garde de provenance STATPOP et son test négatif
make check-tests            # suite de non-régression complète
make help                   # cibles de la chaîne
```

`make check-models` recalcule les empreintes des modèles de couche 1 et les compare aux valeurs
du mémoire : **`e4ddfccd`** pour le segment bas, **`df6a11c5`** pour le haut. `make check-tests`
exécute la suite entière ; les tests qui demandent les données se déclarent ignorés.

## Le registre ADR

`docs/adr/` contient **78 Architecture Decision Records**, gelés à la remise par
[`ADR-078`](docs/adr/ADR-078_cloture_du_registre.md).

**Clé de lecture.** Un ADR consigne une décision *telle qu'elle a été prise à un instant donné*
et n'est pas retravaillé rétroactivement. Le registre documente donc aussi les pistes abandonnées.
**Un ADR au statut `remplacé` ou `révoqué` décrit une décision qui n'est plus en vigueur.**

Chaque fichier porte, sous son titre, un **bandeau d'état** donnant son statut au gel, l'ADR qui
l'a modifié, et le cas échéant le fait que ses chiffres relèvent d'une génération antérieure du
jeu de données, ou du seuil de surcharge d'époque (94, porté à 63 par ADR-060).
[`INDEX.md`](docs/adr/INDEX.md) donne la table complète et les 70 relations de supersession.

| Statut au gel | Nombre |
|---|---|
| `actif` | 29 |
| `amendé` | 20 |
| `remplacé` | 19 |
| `révoqué` | 9 |
| clôture (ADR-078) | 1 |

**Renvois hors dépôt.** Les ADR citent, au titre de leur traçabilité d'époque, des notebooks
d'exploration, des rapports d'expérience et des sorties intermédiaires qui appartiennent au dépôt
de travail et ne sont pas repris ici. Ces renvois documentent le chemin parcouru ; ils ne
conditionnent pas la lecture du registre, dont l'`INDEX.md` et les bandeaux suffisent à la
navigation.

## Ce que le dépôt corrobore, et ce qu'il ne corrobore pas

Les affirmations d'implémentation du registre ont été vérifiées **en partant du code** : 218
affirmations, dont 120 corroborées par un fichier et une fonction identifiés. Le détail, les
nuances et les trois divergences ADR ↔ code relevées figurent à
[`ADR-078 §5`](docs/adr/ADR-078_cloture_du_registre.md).

Ce qui **se vérifie ici** : la chaîne de construction du jeu de données et ses gardes, la clé de
groupement des variables historiques, la géométrie du rattachement spatial, les conventions de
ponctualité, la logique de la couche décisionnelle (score de course, seuils, plancher), la
gouvernance des empreintes, l'environnement épinglé, la composition des 158 variables
(`outputs/couche2/features_158f_sans_simba.json`), et — depuis l'ouverture du périmètre de
reproduction — les **hyperparamètres**, la **perte**, le **protocole de partition** (Split C),
les **valeurs** des trois seuils du menu, l'**analyse SHAP**, les **baselines et ablations**, et
la **comparaison d'algorithmes** d'ADR-072.

S'y vérifient également les **figures et les tableaux du manuscrit**, dont les générateurs
figurent sous `docs/memoire/`, et les **campagnes d'optimisation** d'ADR-051, ADR-070, ADR-071 et
ADR-072, dont les artefacts lus par ces générateurs sont versés sous `archive/explorations/`.

Ce qui **ne s'y vérifie pas** : les **notebooks d'exploration** des phases de compréhension
métier et des données, les **expériences abandonnées** en cours de route, et l'**antériorité**
des protocoles préenregistrés — celle-ci est attestée par l'historique du dépôt de travail, dont
le présent dépôt est un export à la date de gel et qu'il ne porte donc pas. Sur ces points, le
mémoire fait foi.

## Périmètre

Ce dépôt porte **tout le code de l'état scientifique final** : chaîne de données, entraînement,
couche décisionnelle, suite de confirmation, suite de tests. Le critère retenu est simple — est
publié ici tout ce qui **calcule un nombre ou un modèle rapporté au mémoire**.

Restent hors dépôt, comme relevant du chemin parcouru et non de l'état final :

- les **notebooks d'exploration** (phases CRISP-DM de compréhension métier et des données) ;
- les **expériences abandonnées** et les contre-vérifications d'époque sur H24, supersédées par
  la suite de confirmation ;
- le **gros de l'archive d'exploration** : seuls en sont versés les artefacts que les générateurs
  du manuscrit lisent nommément ;
- les **sorties** elles-mêmes — `outputs/`, figures et tableaux —, régénérables par
  `make reproduce` puis `make reproduce-memoire`, et dont certaines portent des données
  d'exploitation ;
- l'**historique Git du dépôt de travail** : le présent dépôt en est un export à la date de gel.

Deux vérifications portent ainsi sur des matériaux que le dépôt ne contient pas. Elles sont
conservées pour ce qu'elles documentent, et `make reproduce-memoire` les déclare **SKIP** — leur
non-exécution est attendue et documentée, ce n'est pas un défaut de reproductibilité :

| Vérification | Ce qu'elle audite |
|---|---|
| `verifs/section_3_4_2/audit_selection_six_cas.py` | atteste par `git log` l'antériorité du protocole de sélection des six cas ; le dépôt est un export sans historique (annexe 16.1 du mémoire) |
| `verifs/section_4_3_1/verif_v2_prerequis.py` | audite les notebooks d'exploration, non publiés |

**Le décompte, sans ambiguïté.** `docs/memoire/` contient **92 fichiers `.py`** : **89 générateurs**
et **3 modules partagés** — `verifs/_garde.py`, `verifs/_socle_chap5.py` et
`verifs/_table_autorite_annexe22.py` —, importés par les autres, sans effet de bord lorsqu'ils sont
exécutés seuls. `make reproduce-memoire` énumère les 92 fichiers, en écarte 2 par nom, et exécute
les 90 restants. D'où le bilan attendu :

```
BILAN : 90 OK / 2 SKIP / 0 FAIL
```

où les **90 OK** se lisent **87 générateurs + 3 modules partagés**. Les deux formulations —
« 87 des 89 générateurs » et « 90 des 92 fichiers » — décrivent le même état ; elles diffèrent
seulement par ce qu'elles comptent.

Ces matériaux relèvent du dépôt de travail ; les résultats qu'ils établissent sont rapportés dans
le mémoire, qui fait foi.

Le déploiement opérationnel — mise en production et intégration au système d'information de
l'exploitant — est hors du périmètre du travail (ADR-074).

## Licence

Ce dépôt est publié sous **deux licences complémentaires**.

| Ce qui est couvert | Licence |
|---|---|
| **Code** — `src/`, `scripts/`, `tests/`, les générateurs de `docs/memoire/`, le `Makefile` | [MIT](LICENSE) |
| **Modèles gelés** — `models/enrichi_seg/*.json` | [MIT](LICENSE), comme le code dont ils sont la sortie |
| **Documentation** — `README.md`, `data/README.md`, le registre des 78 ADR (`docs/adr/`) et les notes `.md` | [CC BY 4.0](LICENSE-DOCS) |

Les deux modèles sont des ensembles d'arbres sérialisés : ils encodent des relations agrégées
apprises sur le jeu canonique, non des enregistrements. Les interroger suppose de disposer des
158 variables d'entrée, donc des données d'exploitation, qui ne sont pas publiées.

**Les données ne sont couvertes par aucune des deux licences.** Comptages APC, données internes
MOB, réservations, rotations et paramètres du système de comptage appartiennent à la Compagnie
du Chemin de fer Montreux Oberland bernois SA. Ils ne figurent pas dans ce dépôt et sont transmis
séparément aux membres du jury pour les besoins de l'évaluation — voir la section
[Données](#données).

Le travail a été conduit en contexte d'entreprise, dans le cadre d'un travail de master
MSc HES-SO en Business Administration, orientation Management des Systèmes d'Information.
Le mémoire fait foi.
