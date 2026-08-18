---
id: ADR-027
ancien_id: ADR-28
date_decision: 2026-05-22
statut: révoqué
revoque_par: [ADR-038]
amende_par: [ADR-065]
modifie: [ADR-002]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-027 — Split temporel : H22+H23 entraînement / H24 test

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-038 ; amendée par ADR-065.
> Décisions antérieures que ce document modifie : ADR-002.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-05-22 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `notebooks/04_model_engineering_split.ipynb` |
| **Remplace** | ADR-002 (proposition initiale H17-H22 / H23 / H24, obsolète) |

## Contexte

Le dataset ML (`ml_dataset.parquet`) couvre la période H16–H24 (2 051 510 observations dans stage_09, grain tronçon × course × date). Plusieurs configurations de split temporel sont techniquement réalisables. La présente ADR fixe le périmètre définitif du modèle de référence du mémoire.

Trois facteurs rendent cette décision non triviale :

1. **Hétérogénéité des régimes opérationnels** : la période H16-H24 couvre un régime pré-COVID (H16-H19), une perturbation COVID (H20-H21) et un retour à la normale post-COVID (H22-H24). Ces trois régimes produisent des distributions de voyageurs statistiquement distinctes (mesurées par le test KS bilatéral).

2. **Couverture temporelle hétérogène des features externes** : les sources ISTDATEN (`ist_*`), VMCV (`vmcv_*`) et SIMBA FQkal (`simba_*`, cf. ADR-026) ne sont pas disponibles sur toute la période. Leur absence sur H16-H22 réduit la richesse informative du jeu d'entraînement si ces années sont incluses.

3. **Cohérence entraînement ↔ déploiement** : le modèle est destiné à être exploité dans le contexte H25 et au-delà. Le jeu d'entraînement doit être représentatif de ce contexte, pas d'un régime structurellement différent (COVID, topologie différente, numérotation différente).

## Décision

**Périmètre d'entraînement et validation** : **H22 + H23** (497 023 observations)

**Périmètre de test out-of-time (OOT)** : **H24** (335 709 observations)

**Exclusions** :
- H16-H21 : exclus du périmètre du modèle de référence (régimes non-représentatifs et/ou features critiques absentes)
- H25 : disponible dans le dataset source mais non utilisé pour le modèle de référence (cf. section "Position de H25")

Cette décision est implémentée dans `scripts/pipeline/build_ml_dataset.py` :
```python
ANNEE_HORAIRE_MIN = "H22"  # ADR-027
ANNEE_HORAIRE_MAX = "H24"  # ADR-027
```

## Justification : les 5 arguments

### 1. Stationnarité statistique (KS)

La matrice KS bilatérale sur `target_voyageurs_total` (calculée sur stage_09, 2 051 510 observations) révèle trois clusters temporels :

| Cluster | Années | KS interne max | KS vs H24 |
|---|---|---|---|
| Pré-COVID | H16-H19 | 0.090 | 0.025–0.113 |
| **COVID** | H20-H21 | **0.004** | 0.144–0.147 |
| **Post-COVID** | H22-H24 | **0.123** | — |

Paires clés pour le split retenu (Config B) :
- **KS(H22, H23) = 0.0722** — cohérence interne du jeu d'entraînement ✅
- **KS(H23, H24) = 0.1231** — stationnarité train/test (< seuil 0.15) ✅
- **KS(H22, H24) = 0.0775** — H22 statistiquement compatible avec le test ✅

Pour comparaison, les KS COVID vs test sont élevés : KS(H20, H24) = 0.1441 et KS(H21, H24) = 0.1469. Inclure H20-H21 dans l'entraînement introduirait un biais de régime non représentatif des conditions de déploiement.

H22 est statistiquement plus proche du cluster post-COVID (distance moyenne vs H23-H24 = 0.075) que du cluster COVID (distance moyenne vs H20-H21 = 0.075). Sa classification dans le périmètre d'entraînement post-COVID est statistiquement justifiée.

### 2. Couverture des features externes

La heatmap de couverture (% non-NaN) par préfixe et année horaire montre des lacunes structurelles sur H16-H22 :

| Feature | H16-H17 | H18-H21 | H22 | H23 | H24 |
|---|---|---|---|---|---|
| ISTDATEN (`ist_*`) | 0% | 28-47% | 28% | 47% | 66% |
| VMCV (`vmcv_*`) | 0% | 19-29% | 46% | 68% | 65% |
| SIMBA (`simba_*`) | 0% | 0% | 0% | 95% | 96% |
| Météo, calendrier, événements | ~100% | ~100% | ~100% | ~100% | ~100% |

Inclure H16-H21 dans le train apporterait des observations sans les features ISTDATEN, VMCV et SIMBA — des features qui portent des signaux structurels non capturables autrement. Bien que XGBoost gère nativement les NaN, un jeu d'entraînement avec 70-100% de NaN sur ces features ne permettrait pas au modèle d'apprendre leur signal de manière robuste.

### 3. Qualité des comptages APC

Le taux de couverture APC (courses observées / courses théoriques d'après les PDFs horaires) connaît une rupture structurelle :

| Année | Taux APC | Nb. courses observées |
|---|---|---|
| H20 | 54.3% | 21 136 |
| H21 | 62.6% | 19 719 |
| **H22** | **43.1%** | **16 948** |
| **H23** | **94.4%** | **32 052** |
| **H24** | **82.4%** | **32 107** |

La transition H22→H23 représente +90% en nombre absolu de courses observées. H22 contribue à la diversité saisonnière (deux décembres dans la période d'entraînement) malgré sa couverture plus faible.

**Note de méthode** : le taux de couverture mesure le volume d'observations disponibles, pas la qualité unitaire de chaque comptage. Une couverture plus faible signifie moins de courses observées par jour, pas des comptages individuels plus bruités.

### 4. Alignement opérationnel (DSR)

Le modèle est conçu pour être déployé dans le contexte H25+ (ligne R35 en régime post-COVID normalisé). L'alignement entre les conditions d'entraînement et les conditions de déploiement est une exigence méthodologique du Design Science Research (Hevner et al., 2004).

Éléments de continuité opérationnelle H22-H24 :
- **Topologie** : Vevey Vignerons (VVVI) actif depuis H23 (H22 encore sur Gilamont)
- **Numérotation** : 102-108 numéros de train distincts, structure stable
- **Service** : R35 normalisé, plus de restrictions COVID-19
- **Régime APC** : couverture quasi-complète à partir de H23

### 5. Volume d'entraînement

| Configuration | Années train | Volume train | Saisons |
|---|---|---|---|
| Config B (retenue) | H22+H23 | **497 023** | 2 années complètes |
| Config C | H23 seul | 335 426 | 1 année |
| Config A | H16-H23 | 1 851 904 | 8 années (hétérogènes) |

H22+H23 offre deux années horaires complètes, garantissant la présence de tous les profils saisonniers (été touristique, hiver ski, transitions automne/printemps) dans l'entraînement.

## Alternatives considérées et rejetées

| Config | Train | Test | Raison du rejet |
|---|---|---|---|
| **A** | H16-H23 | H24 | Feature shift majeur : ISTDATEN et SIMBA absents sur H16-H22. Régime opérationnel incohérent (COVID et pré-COVID mélangés). KS moyen train/test = 0.1086 mais porté par des distributions non-représentatives. |
| **C** | H23 | H24 | Volume insuffisant (335k lignes, une seule saison). Manque de diversité saisonnière. KS(H23, H24) = 0.123 le plus élevé de toutes les configurations train/test candidats. |
| **D** | H19+H23 | H24 | Incohérence opérationnelle (pré-COVID + post-COVID non contiguë). ISTDATEN et SIMBA absents sur H19. Le saut temporel H19→H23 introduit un biais de sélection non justifiable opérationnellement. |
| **E** | H23+H24 | H25 | Configuration testée empiriquement : performances dégradées en raison de l'absence d'ISTDATEN 2025 et des événements Riviera 2025 dans le pipeline. À reconsidérer pour une itération future si ces sources deviennent disponibles. |

## Conséquences sur la pipeline

### `scripts/pipeline/build_ml_dataset.py`

Les constantes sont déjà correctement configurées :

```python
# Filtre temporel — ADR-027 : H22-H24 périmètre modèle de référence.
# H25 accessible via modification ponctuelle de ANNEE_HORAIRE_MAX pour expérimentations.
ANNEE_HORAIRE_MIN = "H22"
ANNEE_HORAIRE_MAX = "H24"
```

Résultat du filtrage : **832 732 lignes** (H22 : 161 597, H23 : 335 426, H24 : 335 709).

### Configuration Dataiku

Split explicite à implémenter dans Dataiku :
- **Entraînement + validation** : lignes où `horaire_annee_horaire ∈ {H22, H23}`
- **Test OOT** : lignes où `horaire_annee_horaire = H24`

## Trade-offs et limites

1. **H22 avec NaN systématiques sur SIMBA** : le millésime SIMBA 2021 n'est pas disponible, les 11 features `simba_*` sont à NaN sur toutes les observations H22 (~161k lignes, ≈ 32% du train). XGBoost gère nativement ces NaN en effectuant des splits uniquement sur les valeurs disponibles. L'impact sur les performances est attendu limité car les autres features couvrent ces observations.

2. **Diagnostic train/test mismatch (Dataiku)** : la croissance post-COVID continue entre H23 et H24 produit un léger décalage de distribution (KS = 0.123) signalé par le monitoring Dataiku. Cette limite est acceptée comme contrepartie de la cohérence opérationnelle — utiliser des données COVID pour réduire ce KS serait méthodologiquement incorrect.

3. **Topologie mixte H22** : VVVI (Vevey Vignerons) est absent en H22 (remplacé par GIL, Gilamont). Les tronçons impliquant VVVI ne sont présents qu'en H23-H24. Ce changement topologique est géré nativement par le modèle (variables `spatial_*` encodent la position dans la topologie active).

## Position de H25

H25 est disponible dans stage_09 (32 303 courses théoriques dans les horaires) mais non inclus dans `ml_dataset.parquet` par défaut. Raisons :

1. ISTDATEN 2025 (`ist_*`) est absent du pipeline → 100% de NaN sur les 28 features ist_.
2. Les événements Riviera 2025 (`event_*`) ne sont pas encore intégrés.
3. La configuration H23+H24 train / H25 test (Config E) a été testée empiriquement et produit des performances dégradées.

H25 reste accessible pour des expérimentations futures en modifiant ponctuellement `ANNEE_HORAIRE_MAX = "H25"` dans `build_ml_dataset.py`, après intégration des sources manquantes.

## Investigation complémentaire écartée — Extension du train set via statut PROGNOSE ISTDATEN

### Hypothèse testée

Il a été envisagé d'étendre le périmètre d'entraînement vers H16-H22 en s'appuyant sur les entrées ISTDATEN de statut `PROGNOSE` (temps estimé) comme proxy des entrées `REAL` (temps mesuré), afin de compenser partiellement l'absence de délais observés sur cette période.

### Diagnostic empirique

L'analyse de `fact_istdaten_r35.parquet` (`statut_depart`, `retard_depart_sec`) révèle :

| Année | PROGNOSE | REAL | UNBEKANNT | Lignes |
|---|---|---|---|---|
| 2021 | 0% | 0% | **100%** | 30 164 |
| 2022 | 0% | 0% | **100%** | 344 626 |
| 2023 | 0.5% | 50% | 49.5% | 350 694 |
| 2024 | 0.8% | 95% | 4.2% | 352 360 |

Deux constats disqualifient l'hypothèse :

1. **Absence de PROGNOSE sur H22** : 2021-2022 est à 100% UNBEKANNT — aucune entrée PROGNOSE sur laquelle s'appuyer.

2. **PROGNOSE ne contient pas de mesure de délai** : sur 2023-2024 (seule période avec PROGNOSE), `retard_depart_sec` est à NaN sur 100% des lignes PROGNOSE. PROGNOSE encode une heure estimée future, pas un écart mesuré post-réalisation. Il ne peut pas servir de proxy de REAL.

### Conclusion

Le 72% de NaN sur les features `ist_*` en H22 est **intrinsèque à la source ISTDATEN** (régime UNBEKANNT en 2021-2022), pas un artefact de pipeline corrigeable. Il n'existe pas de levier pour étendre le train set vers H16-H22 via cette source. La limite est acceptée et documentée dans la section Trade-offs.

**Note complémentaire** : l'écart de retard moyen H23 (−102 s) vs H24 (+69 s) reflète une variation de ponctualité réelle entre les deux années horaires, pas un artefact de mesure. Ce signal est capturé par `ist_r35_retard_dep_moy_sec_j` dans `dim_ponctualite_istdaten.parquet`.

## Décomposition ISTDATEN par famille de features (addendum 2026-05-23)

### Contexte

Le diagnostic initial indique un taux global de NaN ISTDATEN sur H22 de 72.4%. Cette mesure agrège des features de natures fondamentalement différentes. Le notebook `02_data_understanding_istdaten_qualite` précise ce diagnostic en classifiant les 28 features `ist_*` en deux familles selon leur dépendance au statut REAL.

### Classification des 28 features `ist_*`

| Famille | Description | Nb features | Source technique | Dépend de REAL ? |
|---|---|---|---|---|
| **A** | Ponctualité mesurée | 20 | `retard_dep/arr_sec` filtré sur `STATUTS_REELS = {REAL, GESCHAETZT}` | **Oui** |
| **B** | Structure de l'horaire | 8 | `horaire_depart` théorique uniquement (`build_dim_headway.py`) ou `horaire_arrivee` feeders | **Non** |

**Famille A (20 features)** :
- 12 `ist_profil_train_*` : moyennes, écarts-types et % de retard départ/arrivée sur fenêtres glissantes 5occ/20occ — calcul conditionnel à `statut REAL`
- 8 `ist_corresp_*_garanties_*` / `*_pct_garanties_*` : correspondances effectivement maintenues — requièrent le retard réel des feeders (REAL)

**Famille B (8 features)** :
- 4 `ist_headway_*` : intervalles entre trains consécutifs, déduits de `horaire_depart` théorique uniquement — aucun recours à `reel_depart` (cf. `build_dim_headway.py` commentaire ligne 31)
- 4 `ist_corresp_*_theoriques_*` : comptage des feeders dont l'heure d'arrivée planifiée est dans la fenêtre de correspondance — statut-indépendant

### Constats empiriques (NaN % par famille, source : `ml_dataset.parquet`)

| Famille | Sous-groupe | NaN H22 | NaN H23 | NaN H24 | Nature du NaN |
|---|---|---|---|---|---|
| A | `ist_profil_train_*` (12) | **100%** | 61-63% | 16% | Temporel : UNBEKANNT 2021-2022 |
| A | `ist_corresp_*_garanties_*` (8) | 54-92% | 55-77% | 57-81% | Mixte : temporel + structurel |
| **B** | **`ist_headway_*` (4)** | **2-5%** | **0-4%** | **4-7%** | **Quasi-nul — indépendant du statut** |
| B | `ist_corresp_*_theoriques_*` (4) | 55-59% | 55-57% | 57-59% | **Structurel uniquement** (trains Vevey) |

Taux agrégés : Famille A → H22=**89.3%**, H23=61.9%, H24=35.1% ; Famille B → H22=**30.1%**, H23=29.0%, H24=31.8%.

### Reformulation nuancée

Le « 72.4% NaN global sur `ist_*` en H22 » masque deux situations radicalement différentes :

1. **Famille A indisponible sur H22** (89.3% NaN) : l'UNBEKANNT 2021-2022 bloque toutes les mesures de retard. Limite intrinsèque à la source, non corrigeable par PROGNOSE.

2. **Famille B disponible sur H22** (30.1% NaN) : les 4 features headway sont quasi-complètes sur H22 (2-5% NaN, identique à H23-H24). Les 4 features de correspondances théoriques ont ~57% NaN constant sur **toutes** les années — NaN structurel lié à la topologie (seuls les trains passant par Vevey sont couverts), pas au statut REAL.

**En pratique** : le modèle dispose sur H22 des features de structure d'horaire (headway) avec la même qualité que sur H23-H24. XGBoost apprend ces signaux indépendamment de la disponibilité des features de ponctualité.

### Référence

- Notebook `notebooks/02_data_understanding_istdaten_qualite.ipynb`
- Tableaux : `notebooks/figures/02_data_understanding_istdaten_qualite/02_nan_par_feature_par_annee.csv`, `notebooks/figures/02_data_understanding_istdaten_qualite/03_classification_features_familles.csv`

## Références

- Notebook `notebooks/04_model_engineering_split.ipynb` — justification empirique chiffrée (5 figures, 5 tableaux)
- [ADR-002](ADR-002_split_temporel.md) — proposition initiale de split (remplacée par la présente ADR)
- [ADR-022](ADR-022_disponibilite_j_moins_1.md) — disponibilité J-1 et principe du dernier état connu
- [ADR-026](ADR-026_integration_simba_fqkal_lag_n_moins_1.md) — lag N-1 SIMBA (NaN H22 attendus)
- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design Science in Information Systems Research. *MIS Quarterly*, 28(1), 75–105.
- Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in Data Mining: Formulation, Detection, and Avoidance. *ACM TKDD*, 6(4), 1–21.
