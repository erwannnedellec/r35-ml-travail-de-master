---
id: ADR-078
ancien_id: aucun
date_decision: 2026-08-16
statut: actif
modifie: []
corroboration_date: gel de remise
gel_registre: 2026-08-16
---

# ADR-078 — Clôture du registre à la remise du travail de master

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Ce document est le dernier ADR du registre. Il ne rouvre aucune décision de conception :
> il arrête l'état du registre, consigne les décisions prises au fil du projet qui n'ont pas
> fait l'objet d'un ADR propre, et énumère les écarts subsistants entre le registre et le
> manuscrit. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — clôture |
| **Date** | 2026-08-16 |
| **Décideur** | Erwann Nedellec |
| **Portée** | Registre ADR-001 à ADR-077 |

---

## 1. Objet

Le mémoire (§3.3) engage un « registre versionné d'Architecture Decision Records, gelé à la
remise du travail », dont chaque entrée « consigne une décision telle qu'elle a été prise à un
instant donné du cycle, sans être systématiquement retravaillé lorsqu'une découverte ultérieure
aurait pu en infléchir le contenu ».

Ce principe a une conséquence que le présent document assume et traite : lu dans l'ordre, le
registre expose des décisions qui ne sont plus en vigueur, sans que l'ADR d'origine le signale.
La clôture procède donc en trois temps, tous **formels** :

1. **normalisation d'en-tête** — chaque ADR reçoit un front-matter uniforme (`statut`,
   `remplace_par`, `amende_par`, `revoque_par`, `modifie`, `chiffres_perimes`) et un bandeau
   d'état placé sous son titre ;
2. **clôture des statuts d'époque** — dix ADR portaient un statut non terminal (« Proposé — en
   attente de validation », « Résultats — en attente de… »). Le libellé d'époque est **conservé**,
   annoté d'un commentaire, et l'état au gel figure au bandeau ;
3. **consignation des lacunes** — section 3 ci-dessous.

Aucun corps d'ADR n'a été réécrit. Les seules phrases ajoutées le sont au bandeau, sous
l'intitulé « Précision au gel », et se bornent à signaler qu'un titre ou qu'une décision de fond
ne reflète plus l'état retenu.

## 2. État final du registre

| Statut au gel | Nombre | Lecture |
|---|---|---|
| `actif` | 29 | décision en vigueur au gel `ba493568` |
| `amendé` | 20 | en vigueur, modifiée par un ADR ultérieur |
| `remplacé` | 19 | décision supplantée par un ADR ultérieur |
| `révoqué` | 9 | décision annulée, ou dont l'objet a disparu |
| **Total** | **77** | + le présent ADR-078 |

Les cas dont la lecture naïve induirait le plus en erreur, tous désormais porteurs d'un bandeau :

- **ADR-048** décide « modèle final couche 1 = APC-only, 38 variables ». Ce n'est pas le modèle
  retenu (Enrichi_Seg, ADR-052, 158 variables). Aucun marqueur n'existait, ni dans l'ADR, ni à l'index.
- **ADR-052** et **ADR-054** portent « 170 features » dans leur titre, périmètre ramené à 158 par ADR-061.
- **ADR-046** ne prend aucune décision (« Décision requise ») ; le critère F2 qu'il instruit est
  ensuite mobilisé comme acquis par ADR-047 et ADR-048. La trace de cette décision manque : voir §3.
- **ADR-064** s'auto-révoque par son propre amendement (STATENT intégré puis retiré).
- **Quinze ADR** au seuil 94 et **dix-huit** portant des chiffres antérieurs au gel `ba493568`
  sont désormais signalés comme tels, individuellement (ADR-052 porte les deux marques).

## 3. Décisions du mémoire non couvertes par un ADR propre

Les décisions ci-dessous ont été prises et sont exposées dans le manuscrit ; aucune ne fait
l'objet d'un ADR dédié. Elles sont **consignées ici a posteriori**, à la date de clôture et non à
la date où elles ont été prises — la distinction est explicite et suit le précédent d'ADR-068
(traçabilité a posteriori). Aucune n'est rétrodatée.

### 3.1 Préparation des données

| Décision | Valeur retenue | Section du mémoire |
|---|---|---|
| Dédoublonnage strict à l'empilement | 1 252 lignes nettes retirées, 3 journées de recouvrement | §4.4.1 |
| Agrégat mensuel APC écarté | motifs : granularité et circularité (valeurs modélisées) | §4.3.1 |
| Neutralisation des bascules de jour (ISTDATEN) | avant calcul des retards | §4.4.2 |
| Conversion stricte en UTC avant jointure horaire | décalage 1-2 h selon saison | §4.4.2 |
| Lissage VMCV sur 5 et 20 occurrences, conditionné au type de jour | — | §4.4.2 |
| Manifestations : exclusion des annulés et reportés ; 8 journées sans lieu comptées hors zonage | — | §4.4.2 |
| Aucune normalisation d'échelle | arbres invariants aux transformations monotones ; lisibilité en unités natives | §4.4.2 |
| Encodage catégoriel natif XGBoost | 6 variables catégorielles | annexe 23 |
| Jointures gauches m:1 validées en cardinalité | invariant de 2 360 762 observations, contrôlé de bout en bout | §4.4.3 |
| Table canonique = sur-ensemble délibéré | 209 colonnes ; SIMBA et STATENT conservés au titre de la réversibilité | §4.4.3 |

### 3.2 Protocole d'évaluation de la couche 1

| Décision | Valeur retenue | Section du mémoire |
|---|---|---|
| Critères de succès CRISP-ML(Q) | critère ML : **> 33,5 % de précision**, arrêté avant lecture du test | §4.1.6 |
| Discipline de séparation graduée | décisions structurelles arbitrées sur H25 en lecture seule, critère **ΔR² < 0,02 avec IC recouvrants** | §3.4.1, §4.5.1 |
| Périmètre du préenregistrement | borné à l'évaluation finale ; arbitrages structurels à valeur déclarative | §4.5.1 |
| Baseline Ridge | mêmes 158 variables, architecture globale, **α = 1,0**, imputation par la médiane du jeu d'entraînement | §4.5.2 |
| Baseline M0 | même algorithme, architecture globale, **31 variables** de calendrier et d'historique | §4.5.2 |
| Rejet des familles d'algorithmes | séries temporelles ; méthodes à distance et à noyau | §4.5.3 |
| Métriques rapportées | R², MAE, MAE > 63, biais > 63, PR-AUC ; par segment et global ; rapportées à la prévalence | §3.4.1 |
| Intervalles de confiance | bootstrap **1 000 répliques par observation** ; sensibilité par grappes (course, puis journée) | §4.5.5 |
| Épreuve d'erreur du cycle mensuel | 13 mois horaires, deux décembres distingués | §4.5.7 |
| Seconde ablation STATENT sur le modèle gelé | −0,039 sur le haut, −0,008 global | §4.5.4 |

### 3.3 Couche décisionnelle

| Décision | Valeur retenue | Section du mémoire |
|---|---|---|
| Critère F2 pour le seuil de rappel renforcé | acté nulle part au registre ; instruit par ADR-046, mobilisé par ADR-047 et ADR-048 | §4.6.3 |
| **Seuil b = 51,31** | maximise F2 (rappel pesé 4× la précision) | §4.6.3 |
| Effectifs du jeu de calibration | H24 seul : **32 102 courses, 2 380 en surcharge**, prédictions in-sample | §4.6.3 |
| Nature des critères de calibration | **exclusivement statistiques** ; coûts et tolérance du RPROD interviennent en aval | §4.6.3 |
| Valorisation économique | facteur agrégé **3,49 CHF/km de course** = tare 54,2 t (Stadler, plan BZ 2004242 ind. c) × prix du sillon TRV 2025 **0,06444 CHF/tbkm** (Transports Montreux-Vevey-Riviera SA, document interne, juillet 2024) ; provenance versée à ADR-077 par addendum du 2026-08-18 | §4.7.2 |
| Inférence de la comparaison à la pratique | IC bootstrap sur les précisions ; **test exact de McNemar** sur le rappel ; rééchantillonnage par journées entières (dispersion 6,96 / 2,81) | §5.1 |
| Politique de seuil différenciée par type de jour | c ∪ plancher les jours ouvrables et samedis, posture b les dimanches et fériés ; **analyse post-hoc, non préenregistrée** | §5.2.1 |

## 4. Écarts entre registre et manuscrit, à trancher dans le manuscrit

Quatre points ont été instruits. Un seul appelle une reprise du texte du mémoire ; les trois
autres ont été tranchés par la source exécutable ou par un artefact d'évaluation conservé, et
n'appellent aucune correction.

1. **Classifieur binaire direct.** Le §4.6.2 le déclare « non évalué dans ce travail (limite
   déclarée) ». ADR-030 le retient comme levier L3, et **ADR-031 §2.4 en rapporte l'évaluation
   complète sur H24** (PR-AUC non pondéré 0,2359, ROC-AUC 0,9012, calibration par ratio de coût
   de 3:1 à 20:1). La formulation du mémoire doit distinguer le levier exploratoire, évalué et
   écarté, du classifieur appliqué à l'architecture et au périmètre finaux, qui ne l'a pas été.
2. **Nombre de répliques bootstrap — résolu, sans écart.** Le mémoire annonce 1 000 répliques
   (§4.5.5) ; plusieurs ADR consignent 500 (ADR-042, ADR-052). La source exécutable tranche :
   `scripts/confirmation/_harness.py` fixe `N_BOOT = 1000` et sa fonction `r2_ci()` documente
   « protocole phase 4 : 1000 iterations, seed 42 ». Ce sont ces scripts qui produisent le
   tableau 16 du mémoire. Les 500 des ADR relèvent des campagnes exploratoires antérieures, sur
   une autre génération du jeu. **Le mémoire est exact ; aucune correction n'est requise.**

3. **Projection au grain du bloc d'accouplement — résolue, sans écart.** ADR-073 écarte
   l'opération du protocole d'évaluation qu'il arrête le 2026-07-04, avant implémentation de la
   couche 2 (« Aucune projection bloc n'est faite côté modèle »), et en tire que la comparaison à
   cette borne reste « indicative, non conclusive ». Le mémoire (§4.7.2, §5.1) la conduit et en
   publie le résultat. Ce n'est pas un revirement de conception : la projection est une **analyse
   d'évaluation postérieure au gel de l'artefact**, produite le 2026-08-05 par
   `docs/memoire/verifs/section_4_7/v6_grain_bloc.py` — lecture seule, sous garde d'empreinte
   `ba493568`, sur les artefacts gelés de la couche 2. Le script reproduit d'abord les valeurs
   humaines déjà publiées (418 engagements de H25, 140 justifiés au grain de la course, 246 au
   grain du bloc, soit 58,85 %) avant de produire la projection, et conserve ses sorties en
   `v6_*.csv` :

   | Grandeur publiée (§4.7.2, §5.1) | Sortie du script |
   |---|---|
   | 72,3 % de précision, configuration de déploiement | `precision_bloc_pct = 72.29` |
   | 31,4 % de rappel, configuration de déploiement | `rappel_bloc_pct = 31.39` |
   | 58,9 % de précision, pratique | `precision_bloc_pct = 58.85` |
   | 6,0 % de rappel, pratique | `rappel_bloc_pct = 6.03` |
   | 860 blocs pour 866 recommandations | `n_blocs = 860`, `courses_engagees = 866` |
   | 1,8 course consécutive, bloc humain | `taille_moyenne_bloc = 1.78` |

   Ces vérifications appartiennent au **dépôt de travail** : le présent dépôt publie l'artefact et
   le registre, non les scripts de vérification du manuscrit. L'artefact et le protocole arrêtés
   par ADR-073 sont inchangés ; conformément au principe du registre (mémoire, §3.3), cette
   analyse **n'est pas réinjectée** dans ADR-073, dont le corps reste dans sa rédaction d'origine
   — elle est signalée à son bandeau de gel. **Le mémoire est exact ; aucune correction n'est
   requise.**

4. **Décomposition factorielle — résolue, sans écart.** Les valeurs du mémoire (§4.5.3) sont
   directement produites par `scripts/confirmation/c04_delta_segmentation.py` sur `ba493568`, et
   figurent dans `outputs/confirmation/c04_delta_segmentation.json`, cellule `haut` :

   | Cellule de la grille | R² segment haut | Mémoire |
   |---|---|---|
   | `M0_global` (31 variables, architecture globale) | 0,181440 | 0,181 |
   | `158_global` (enrichissement seul) | 0,379290 | 0,379 |
   | `M0_seg` (segmentation seule) | 0,258550 | 0,259 |
   | `158_seg_gel` (conjonction, modèles gelés) | 0,438636 | 0,439 |

   Le gain propre de la segmentation, 0,059, n'est pas une soustraction faite à la main : c'est
   `decomposition_r2.delta_segmentation_seg_moins_global.a_158_fixe.haut = 0,05934609780606859`,
   calculé et publié par le même script. Les grilles d'ADR-045 et ADR-050 (0,504 / 0,575 / 0,585)
   portent sur une génération antérieure et un périmètre différent ; elles ne sont pas comparables.
   **Le mémoire est exact ; aucune correction n'est requise.**


## 5. Corroboration du registre par le code publié

Une passe de vérification a été conduite **en partant du code**, et non des ADR : pour chaque
affirmation écrite au présent comme une réalité technique, on a cherché le fichier, la fonction ou
la configuration qui la réalise. **218 affirmations** portent un verdict explicite.

| Verdict | Nombre |
|---|---|
| corroboré — le code fait ce que l'ADR dit | 120 |
| corroboré avec nuance — le code le fait autrement, ou partiellement | 25 |
| historique / supersédé — l'ADR décrit un état antérieur, expliqué par un ADR ultérieur | 21 |
| déclaratif seulement — non établissable depuis le dépôt remis | 33 |
| **non corroboré / contradiction** | **19** |

### 5.1 Ce que le dépôt ne permet pas d'établir

Le dépôt remis porte la chaîne de données et l'artefact, non l'entraînement ni l'évaluation.
Restent donc **structurellement déclaratifs**, et le mémoire en est la seule source :

- les hyperparamètres de la couche 1, la perte retenue et le rejet des pertes alternatives
  (ADR-050, ADR-051, ADR-052, ADR-069, ADR-071, ADR-072) — aucun script d'entraînement n'est livré ;
- le protocole de partition et la règle d'exclusion Gilamont (ADR-065) ;
- les campagnes Optuna et le comparatif inter-algorithmes (ADR-071, ADR-072) — seule trace : les
  versions épinglées de `requirements.txt` ;
- l'analyse SHAP et les classements par segment (ADR-053) ;
- les **valeurs** des trois seuils du menu (a′, b, c) : la procédure qui les produit est lisible
  dans `src/couche2/`, les valeurs ne sont re-dérivables qu'avec le jeu gelé et les modèles ;
- l'appareil empirique des ADR d'exploration (ADR-043, ADR-056, ADR-061, ADR-070), dont les
  notebooks et rapports appartiennent au dépôt de travail.

La **liste des 158 variables du modèle final** est en revanche désormais livrée
(`outputs/couche2/features_158f_sans_simba.json`). Elle rend vérifiables par simple lecture les
retraits décidés par ADR-061 (aucune variable `simba_*`), ADR-064 (aucune variable d'emploi) et
ADR-068 (aucun `id_gare_*`).

### 5.2 Divergences ADR ↔ code relevées

Trois écarts méritent d'être connus d'un lecteur du registre.

1. **Une des trois assertions bloquantes annoncées était inopérante — corrigée.** Le mémoire
   (§4.4.3) annonce trois gardes : décalage de deux jours sur l'historique, clé de groupement sans
   le tronçon, millésime STATPOP interpolé. Les deux premières existaient et fonctionnaient
   (`_assert_histo_conformite_adr_cf18` et le contrôle de régression sur `GROUP_KEYS`, dans
   `scripts/pipeline/add_features_to_raw_stacked.py`). La troisième ne pouvait pas se déclencher :
   elle testait une étiquette de source dérivée de la constante `STATPOP_MAPPING`, c'est-à-dire du
   module consommateur lui-même, et jamais la table lue. Elle n'aurait pas détecté la substitution
   de fichier contre laquelle ADR-063 prétend prémunir.

   Elle est remplacée par `assert_statpop_provenance_causale()`, qui inspecte le **contenu de
   l'artefact consommé**. Propriété discriminante : le report causal d'ADR-076 étant une copie
   exacte, les millésimes imputés (2021, 2023) reproduisent à l'identique leur millésime source
   (2020, 2022) sur les treize colonnes imputées ; la recette d'époque, qui combinait interpolation
   linéaire et maximum des millésimes adjacents, viole cette égalité. La tolérance est nulle.
   Mesuré sur les deux tables du projet : **0 écart sur 429 valeurs** pour
   `statpop_clean_causal.parquet`, **6 écarts** pour `statpop_clean.parquet` — tous sur
   `hpi_classe_max_500m`, aux gares CHBL, HTV et STLE, c'est-à-dire exactement les valeurs
   d'ancrage dont ADR-075 établit qu'elles distinguent les deux recettes. Le test négatif est
   explicite et versionné (`tests/test_statpop_provenance_causale.py`, cible `make check-guards`).

2. **Le producteur et le consommateur de la topologie divergeaient de répertoire — corrigé.**
   `build_horaires_r35_from_pdfs.py` écrit `horaires_r35_arrets_officiels.parquet` dans
   `data/intermediate/`, tandis que `build_fact_statpop_gare.py` le lisait dans `data/processed/`.
   Les deux fichiers étaient byte-identiques (SHA-256 `5c79ca5f…`), de sorte que le gel n'était pas
   affecté ; mais `make clean-all` vide `data/processed/` sans régénérer cette copie, et
   l'invariant de reproduction ne tenait pas sur cette branche. Le consommateur pointe désormais
   sur le chemin canonique déclaré par `pipeline.paths.HORAIRES_ARRETS_OFFICIELS`.

3. **Deux dispositifs d'ablation décrits par ADR-016 et ADR-017 n'existent pas dans le code
   livré.** Les arguments de ligne de commande invoqués (`--exclure-horaire-numero-train`,
   `--variante-encodage-service`) ne figurent pas dans `build_ml_dataset.py`, et la sortie
   alternative `ml_dataset_sans_train_id.parquet` n'est produite nulle part. ADR-016 est révoqué,
   ce qui atténue le cas ; ADR-017 est actif et son ablation n'est pas rejouable depuis le dépôt.

### 5.3 Vérification du gel après correctifs

Les deux correctifs ci-dessus ont été appliqués **avant** la remise, sous une contrainte stricte :
ni le jeu canonique ni les modèles ne devaient changer. La chaîne complète a été rejouée depuis
les sources, dans le dépôt de travail disposant des données.

| Contrôle | Résultat |
|---|---|
| Empreinte du jeu reconstruit | `ba493568` → **`ba493568`**, identique |
| Garde de provenance, pendant le build | `429/429 valeurs imputées reproduisent exactement leur millésime source` |
| Modèles gelés | `e4ddfccd` (bas), `df6a11c5` (haut) — conformes |
| `make check-propagation` (dépôt de travail) | règles A, B, C : PASS ; 4 PENDING notebooks, non bloquants |
| Suite de tests | 203 passés, 35 ignorés, 0 échec |
| Durée de la reconstruction | ~25 minutes |

Le jeu `ba493568` avait été produit sous un pipeline dont la troisième garde ne fonctionnait pas ;
sa reconstruction sous le pipeline corrigé rend la **même empreinte à l'octet près**. Les
correctifs portent donc sur les contrôles et sur la chaîne de reproduction, non sur la recette :
**l'artefact scientifique gelé est inchangé**, et les trois assertions bloquantes annoncées au
§4.4.3 du mémoire sont désormais toutes trois effectives.

### 5.4 Ce que corrobore le champ `corroboration_date`

Le champ de front-matter anciennement nommé `corroboration_git` a été renommé
**`corroboration_date`** et sa valeur explicitée. Il n'atteste **pas** que la décision est
implémentée : il atteste que le fichier d'ADR était présent dans un commit du **dépôt de travail**
à la date indiquée, ce qui corrobore sa date de décision. Quarante-neuf ADR sont dans ce cas, dont
quarante-deux avec un commit dans le mois de la date déclarée. Le dépôt remis n'ayant qu'un commit
initial, cette corroboration se vérifie dans le dépôt de travail privé, conservé et non publié.
Les vingt-sept autres ADR portent `déclaratif`.

## 6. Ce que ce document ne fait pas

Il ne réécrit aucune décision, ne rétrodate aucune consignation et ne corrige aucun chiffre
d'époque. Les valeurs périmées restent lisibles dans leur ADR d'origine, signalées au bandeau.
Le registre reste ce que le mémoire annonce : la trace du raisonnement au moment de chaque
décision, augmentée d'une couche de navigation qui en rend l'état final lisible.
