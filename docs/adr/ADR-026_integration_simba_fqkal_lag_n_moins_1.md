---
id: ADR-026
ancien_id: ADR-27
date_decision: 2026-05-21
statut: révoqué
revoque_par: [ADR-061]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-026 — Intégration SIMBA FQkal avec lag N-1 systématique

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-061.
> **Précision au gel.** Les variables `simba_*` intégrées ici sont **retirées du modèle** par ADR-061 ; elles restent présentes dans la table canonique au titre de la réversibilité.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

## Statut
Accepté — 2026-05-21

## Contexte

### Source SIMBA FQkal

SIMBA FQkal (Fahrgast-Qualität kalibré) est le modèle de demande de la planification de l'offre des CFF.
Il combine deux sources primaires :
- **FQ (Fahrgast-Qualität)** : enquêtes Origine-Destination réalisées dans les trains (questionnaires papier/numérique auprès des voyageurs)
- **HOP (Hochrechnung Personenverkehr)** : comptages officiels de voyageurs, dérivés des AFZ (automatische Fahrgastzählung, comptage automatique de passagers)

La calibration FQ → FQkal utilise HOP comme référence de niveau. Les données sont mises à disposition par SBB aux KTU (Kleine Transportunternehmen, dont MOB/MVR) au format CSV annuel (`zuginout_MOB_YYYY.csv`), au grain voyage individuel (`zug_in` → `zug_out`) avec volume estimé DWV/DNWV/DTV.

### Intérêt pour le projet R35

SIMBA apporte deux types de signal non couverts par les sources actuelles (APC, STATPOP, ISTDATEN, météo, calendrier) :

1. **Profil tarifaire** — composition du trafic par type de titre (GA, Mobilis Riviera, billets HTA, Spar/promotionnel, jeunes, abonnements, militaires). Un train dominé GA est structurellement plus prévisible (navetteurs réguliers) qu'un train dominé billets (excursionnistes sensibles à la météo).

2. **Correspondances intermodales** — part de voyageurs provenant d'un zubringer (train amont, `zubringer_tucode/vmnummer`) ou dirigés vers un anschluss (train aval). Encode le couplage au réseau national non capturé par ISTDATEN.

3. **OD étendue** — répartition des origines/destinations réelles au-delà du périmètre R35 (origine Lausanne, Genève, etc.), permettant une caractérisation de la demande longue distance vs locale.

### Synthèse des 5 questions méthodologiques (notebook `02_data_understanding_simba.ipynb`)

| Question | Résultat chiffré |
|---|---|
| Q1 — Granularité et couverture | Annuelle (Fahrplanjahr), 25 colonnes, ~13 000 lignes/an pour R35 (TU=42), 4 millésimes disponibles (H22–H25) |
| Q2 — Risque de leakage | r = **0.97** entre SIMBA(N) et APC(N) sur le périmètre R35 (expansion OD → tronçon) — circularité confirmée |
| Q3 — Disponibilité temporelle | Latence de publication 4–5 mois ; SIMBA(N-1) toujours disponible avant déploiement H(N) |
| Q4 — Algorithme d'expansion | Facteur de multiplication ~3× (chaque OD couvre en moyenne 3 tronçons R35), exécution < 5s/millésime |
| Q5 — Identification périmètre R35 | TU=42 (SBB), trains 1300–1399, debicode 9190, offertcode 7730, 17 gares |

### Identification empirique du risque

La corrélation r = 0.97 entre l'occupation SIMBA (expandue OD → tronçon, DWV) et les comptages APC 2e classe (jours ouvrables, H24) a été mesurée par :

```python
# Expansion OD → tronçons traversés (cf. simba_to_troncon_occupancy dans le notebook)
# puis jointure sur (numero_train, gare_depart, gare_arrivee) avec apc_stacked
```

Ce niveau de corrélation est attendu et s'explique par la chaîne de calibration
`AFZ (APC) → FRASY → HOP → calibration FQkal`.

## Décision

**Intégration partielle de SIMBA dans la pipeline avec lag N-1 systématique.**

### Règle de mapping millésime → année horaire

Pour une prédiction sur l'année horaire `H(Y)`, utiliser le millésime SIMBA `Y-1` :

```python
simba_millesime = int(horaire_annee_horaire[1:]) + 2000 - 1
# H24 → 2023, H23 → 2022, H22 → 2021
```

Ce mapping est symétrique à `STATPOP_YEAR_TO_HORAIRE` d'ADR-025, avec la même logique :
le millésime N-1 est structurellement stable et représentatif de l'année N.

### Features retenues

| Feature | Formule | Type |
|---|---|---|
| `simba_part_ga` | Σ DWV(GA) / Σ DWV(total) | proportion [0,1] |
| `simba_part_mobilis` | Σ DWV(Mobilis Riviera) / Σ DWV(total) | proportion [0,1] |
| `simba_part_billet_hta` | Σ DWV(Billet HTA) / Σ DWV(total) | proportion [0,1] |
| `simba_part_jeunes` | Σ DWV(Jeunes) / Σ DWV(total) | proportion [0,1] |
| `simba_part_abonnement` | Σ DWV(Abonnement) / Σ DWV(total) | proportion [0,1] |
| `simba_part_spar` | Σ DWV(Spar/promotionnel) / Σ DWV(total) | proportion [0,1] |
| `simba_part_autre` | Σ DWV(Autre) / Σ DWV(total) | proportion [0,1] |
| `simba_part_corresp_amont` | Σ DWV(zubringer non-nul) / Σ DWV(total) | proportion [0,1] |
| `simba_part_corresp_aval` | Σ DWV(anschluss non-nul) / Σ DWV(total) | proportion [0,1] |
| `simba_part_intra_r35` | Σ DWV(quell+ziel ∈ gares R35) / Σ DWV(total) | proportion [0,1] |
| `simba_part_premiere_classe` | Σ DWV(abteil_klasse=1) / Σ DWV(total) | proportion [0,1] |

### Feature explicitement exclue

`simba_voyageurs_dwv_total` (volume brut) : conservé dans `dim_simba_r35.parquet` pour
traçabilité et audit, mais **exclu du `ml_dataset.parquet`**.

Motif : même avec lag N-1, la corrélation inter-millésimes reste ~0.95 — rapport
signal/risque défavorable comparé aux lags APC (`histo_*`) qui portent le même signal
avec une résolution temporelle bien supérieure (jour à jour vs annuelle).

## Justification méthodologique

### Distinction sources exogènes vs sources auto-référentielles

La règle de cohérence temporelle suit un critère conditionnel sur la nature causale :

| Type | Définition | Règle |
|---|---|---|
| **Exogène** | Phénomène causalement indépendant des comptages APC | Cohérence 1-pour-1 acceptable ; décalage millésime uniquement si latence opérationnelle |
| **Auto-référentielle** | Dérive empiriquement des comptages APC (directement ou via chaîne) | Lag temporel obligatoire |

STATPOP, météo, calendrier et événements sont **exogènes** : leur valeur est indépendante
du fait qu'un train soit plein ou vide. SIMBA et les lags APC (`histo_*`) sont
**auto-référentiels** : leur valeur encode, directement ou indirectement, le niveau de
trafic passé qui est corrélé à la cible future.

### Argument opérationnel (cohérence entraînement ↔ exploitation)

En exploitation J-1, le modèle dispose de SIMBA(N-1) (disponible depuis avril/mai N)
mais jamais de SIMBA(N) (non encore publié). Entraîner avec SIMBA(N) et déployer avec
SIMBA(N-1) créerait un **distribution shift** entre les conditions de validation
et les conditions de production, rendant les performances mesurées non représentatives.

### Argument anti-circularité

Utiliser SIMBA(N) pour prédire APC(N) crée un raccourci tautologique : le modèle apprendrait
à reproduire la cible via un intermédiaire qui la contient déjà. Ce schéma produit des
métriques d'entraînement artificiellement élevées et des modèles fragiles hors distribution.

Référence : Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012).
*Leakage in Data Mining: Formulation, Detection, and Avoidance*.
ACM Transactions on Knowledge Discovery from Data, 6(4), 1–21.

## Périmètre TU et filtre R35

- **Filtre primaire** : `ho_tucode == 42` (SBB, exploitant contractuel R35)
- **Identifiants secondaires de confirmation** :
  - `ckv_liste == '42'`
  - `debicode_liste == '9190'`
  - `offertcode_liste ∈ {'7730', '7730,7731'}`
- **Mapping trains** : `ho_vmnummer` ↔ `horaire_numero_train` direct (plage observée 1300–1553)
- **17 gares R35** : VV, VVVI, HTV, CHTV, STLE, STLV, CHIZ, CHBL, BLON, PRLZ, TUS, CHEV, BCHX, FAY, OND, LAL, PLEI

## Conséquences

### Nouveaux artefacts

| Artefact | Script producteur | Chemin |
|---|---|---|
| `simba_clean.parquet` | `scripts/sources/build_fact_simba_r35.py` | `data/processed/sources/` |
| `simba_expansion_troncons.parquet` | `scripts/sources/build_fact_simba_r35.py` | `data/processed/sources/` |
| `dim_simba_r35.parquet` | `scripts/sources/build_dim_simba_r35.py` | `data/dimension/` |
| `stage_09_simba.parquet` | `scripts/pipeline/add_simba_to_raw_stacked.py` | `data/processed/` |

### Modifications de la pipeline

- `scripts/pipeline/paths.py` : ajout `STAGE_09_SIMBA`, `SIMBA_CLEAN`, `SIMBA_EXPANSION`, `DIM_SIMBA_R35`
- `Makefile` : ajout cible `stage_09` après `stage_08`, avant `build_ml_dataset.py`
- `scripts/pipeline/build_ml_dataset.py` : lecture depuis `stage_09_simba.parquet` au lieu de `stage_08_features.parquet`

### Schéma `ml_dataset.parquet`

Nouvelles colonnes avec préfixe `simba_` (11 features) :
`simba_part_ga`, `simba_part_mobilis`, `simba_part_billet_hta`, `simba_part_jeunes`,
`simba_part_abonnement`, `simba_part_spar`, `simba_part_autre`,
`simba_part_corresp_amont`, `simba_part_corresp_aval`,
`simba_part_intra_r35`, `simba_part_premiere_classe`.

Aucun changement de schéma sur les stages 01–08.

### Valeurs NaN attendues

| Année horaire | Millésime SIMBA utilisé | Disponible | Lignes NaN |
|---|---|---|---|
| H22 | SIMBA 2021 | ❌ non disponible | 100 % des lignes H22 |
| H23 | SIMBA 2022 | ✅ | 0 % |
| H24 | SIMBA 2023 | ✅ | 0 % |
| H25 (test OOT) | SIMBA 2024 | ✅ | 0 % |

XGBoost gère nativement les NaN dans les features — aucune imputation requise.
H22 avec features SIMBA = NaN est acceptable : le modèle disposera d'autres features
pour les observations H22.

## Trade-offs et limites

1. **Granularité annuelle** : SIMBA ne fournit pas de signal quotidien. Les features SIMBA
   sont des profils structurels constants pour un train donné sur toute l'année. Leur apport
   est dans la caractérisation du type de demande, pas dans sa dynamique.

2. **Latence de publication** : SIMBA(N-1) est disponible en avril-mai de N. Pour les
   prédictions de janvier-avril N, si H(N) démarre en décembre N-1, un fallback sur
   SIMBA(N-2) est théoriquement requis. En pratique, le déploiement prototype ne couvre
   pas ce cas limite ; il est documenté pour une itération future.

3. **Circularité indirecte résiduelle** : même avec lag N-1, la chaîne
   `AFZ → HOP → FQkal` implique que les profils SIMBA(N-1) sont partiellement influencés
   par le trafic APC(N-1) (corrélation inter-millésimes ~0.95). Cette circularité
   résiduelle est **acceptée comme limite documentée**, atténuée par la nature proportionnelle
   des features retenues (les proportions sont structurellement plus stables que les volumes).

4. **Hypothèse de traversée complète** : l'expansion OD → tronçon suppose que chaque
   voyageur (quell → ziel) traverse tous les tronçons intermédiaires entre sa montée et
   sa descente. C'est exact par construction (définition d'un tronçon dans le réseau R35).

## Réversibilité

Les scripts de construction SIMBA sont indépendants des stages 01–08. Pour désactiver
l'intégration SIMBA :
1. Retirer `stage_09` de la chaîne Makefile
2. Lire `stage_08_features.parquet` dans `build_ml_dataset.py` (fallback trivial)
3. Aucune transformation destructive sur les données existantes

## Addendum — ADR-061 (2026-06-11) : retrait des features simba_* du modèle

L'investigation de cohérence temporelle (2026-06-11) a établi que les 12 features `simba_*` présentent trois problèmes structurels : instabilité inter-annuelle quasi-nulle (r = 0.056 pour `simba_part_ga` entre SIMBA 2023 et 2024 sur les trains conservés), leakage de disponibilité sur 21.6 % des observations H25 (SIMBA 2024 non publié pour déc 2024 – avr 2025), et 46.6 % de NaN structurels sur H25 (refonte d'horaire ADR-041).

**Décision ADR-061** : les features `simba_*` sont retirées du modèle de couche 1 Enrichi_Seg. Le modèle v1.1 opère sur 158 features (ΔR² global = +0.007, ΔR² HAUT = +0.042 vs 170f).

SIMBA reste intégrée dans le pipeline (`stage_09_simba.parquet`) et constitue une source du Business Understanding. Elle n'est plus une feature prédictive.

## Références

- Notebook `notebooks/02_data_understanding_simba.ipynb` — investigation Data Understanding complète
- [ADR-022](ADR-022_disponibilite_j_moins_1.md) — disponibilité J-1, principe du dernier état connu
- [ADR-025](ADR-025_buffer_voronoi_par_annee_horaire.md) — mapping millésime/horaire STATPOP (précédent méthodologique)
- [ADR-002](ADR-002_split_temporel.md) — split temporel, H25 réservé comme jeu de test OOT
- [ADR-061](../docs/adr/ADR-061_retrait_simba_features.md) — retrait features simba_*, modèle v1.1 158f
- Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). *Leakage in Data Mining: Formulation, Detection, and Avoidance*. ACM TKDD, 6(4), 1–21.
