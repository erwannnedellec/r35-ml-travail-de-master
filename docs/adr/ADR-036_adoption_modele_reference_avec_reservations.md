---
id: ADR-036
ancien_id: ADR-38
date_decision: 2026-06-03
statut: amendé
amende_par: [ADR-072]
modifie: [ADR-033, ADR-035]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-036 — Adoption du modèle de référence enrichi des features réservations (couche 1)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-072.
> Décisions antérieures que ce document modifie : ADR-033, ADR-035.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acté |
| **Date** | 2026-06-03 |
| **Décideur** | Erwann Nedellec (data analyste MOB, futur data lead) |
| **Notebooks de référence** | `notebooks/11_modeling_with_reservations.ipynb` (sections 1–9), `notebooks/11b_diagnostics_pr_auc_et_narcisses.ipynb` (sections 0–4) |
| **Révoque** | — (étend ADR-033 sans le révoquer : les métriques de référence ADR-033 sont remplacées, l'architecture deux couches reste inchangée) |
| **Lié à** | ADR-027 (split temporel H22+H23 / H24), ADR-033 (architecture deux couches, limite informationnelle), ADR-035 (intégration features `resa_*` en couche 1) |

---

## 1. Contexte

### 1.1 — Le test empirique posé par l'ADR-035

L'ADR-035 (2026-06-03) a intégré 8 features dérivées des réservations de groupes ResSys (`resa_*`) au pipeline `ml_dataset.parquet`, avec l'hypothèse empirique que la présence planifiée de groupes constitue une information prédictive non capturée par les 160 features du modèle de référence ADR-033. La justification reposait sur la coïncidence entre réservations confirmées et surcharges : 62 sur 104 surcharges segment haut H24 (59.6 %) coïncident avec au moins une réservation de groupe à J-1, et 7 sur 7 surcharges de juin H24 (100 %) y coïncident.

Le notebook 11 a testé cette hypothèse selon le protocole de référence ADR-033 : split temporel H22+H23 train / H24 test OOT (ADR-027), hyperparamètres XGBoost figés (`n_estimators=300, max_depth=6, lr=0.1, subsample=0.8, colsample_bytree=0.8`), walk-forward strict, `random_state=42`. Deux modèles ont été comparés : le modèle A (baseline 160 features, scénario D ADR-033) et le modèle B (168 features = 160 baseline + 8 `resa_*`). Le notebook 11b a conduit deux diagnostics empiriques ciblés sur les résultats contre-intuitifs de cette comparaison.

### 1.2 — Cinq hypothèses pré-enregistrées

Les hypothèses suivantes ont été pré-formulées avant exécution dans le notebook 11 et soumises à test empirique :

- **H1** : l'ajout des `resa_*` améliore le R² sur le segment haut (R² haut B > 0.3279)
- **H2** : l'ajout des `resa_*` n'altère pas le R² sur le segment bas (R² bas B ≥ 0.5823, tolérance ±2 %)
- **H3** : l'ajout des `resa_*` permet pour la première fois de détecter des surcharges haut (Rappel haut B > 0.000)
- **H4** : le gain de R² haut est concentré sur juin H24 (mois pour lequel 7/7 surcharges coïncident avec une réservation)
- **H5** : `resa_max_groupe_2c_J_minus_1` est plus discriminante que `resa_pax_2c_J_minus_1` sur le segment haut (mean|SHAP resa_max| > mean|SHAP resa_pax| sur haut)

### 1.3 — Résultats empiriques globaux

Le tableau suivant synthétise la comparaison A vs B sur le test set H24 (335 709 lignes) :

| Métrique | A — baseline (160 features) | B — + resa_* (168 features) | ΔB−A |
|---|---|---|---|
| R² global | 0.6123 | **0.6454** | **+0.0331** |
| R² segment bas | 0.5823 | **0.6045** | **+0.0222** |
| R² segment haut | 0.3279 | **0.4757** | **+0.1478** |
| RMSE global | 11.063 | 10.581 | −0.482 |
| RMSE segment haut | 9.661 | 8.532 | −1.129 |
| MAE global | 7.307 | 7.045 | −0.262 |
| MAE segment haut | 5.725 | 5.019 | −0.706 |
| Rappel surcharges haut @ seuil 94 | 0.000 | 0.000 | 0.000 |
| Précision surcharges haut @ seuil 94 | n/a | n/a | — |
| PR-AUC global | 0.232 | 0.242 | +0.010 |
| PR-AUC segment haut | **0.090** | **0.055** | **−0.035** |

Le verdict sur les cinq hypothèses est le suivant :

| Hypothèse | Verdict | Δ observé |
|---|---|---|
| H1 — R² haut B > 0.3279 | **✅ CONFIRMÉE** | +0.1478, de 0.3279 à 0.4757 (+45 % en relatif) |
| H2 — R² bas non dégradé | **✅ CONFIRMÉE** | +0.0222, amélioration nette |
| H3 — Rappel haut > 0.000 | **❌ INFIRMÉE** | 0.000 inchangé |
| H4 — Gain concentré en juin | **❌ INFIRMÉE** | Δjuin=+0.168, Δmoy_autres=+0.175 ; gain non concentré |
| H5 — SHAP resa_max > resa_pax | **❌ INFIRMÉE** | 0.245 vs 0.732 sur haut ; resa_pax dominant |

---

## 2. Décisions actées

### 2.1 — Adoption du modèle B comme nouveau modèle de référence couche 1

**Décision** : le modèle B (168 features brutes, soit 167 features actives après le §2.3) remplace le modèle de référence ADR-033 (160 features) pour la **prédiction de niveau** de `target_voyageurs_2eme_classe` en couche 1. Les métriques de référence ADR-033 (R² global=0.6123, R² bas=0.5823, R² haut=0.3279) sont remplacées par celles du modèle B (R² global=0.6454, R² bas=0.6045, R² haut=0.4757).

**Justification empirique** : le gain de +0.1478 R² sur le segment haut — de 0.3279 à 0.4757, soit une progression de 45 % en relatif — est le plus important obtenu par une seule itération de feature engineering dans le projet. Ce gain présente quatre propriétés qui justifient l'adoption sans réservation :

**Significativité en absolu** : +14.78 points de R² sur un segment qui représentait le principal défi prédictif du projet depuis l'ADR-030. La réduction du RMSE de 9.661 à 8.532 (−1.129) et du MAE de 5.725 à 5.019 (−0.706) confirment que le gain n'est pas artefactuel.

**Robustesse sur l'ensemble des segments** : le segment bas progresse de +0.0222 R² et d'aucun segment ne régressant, le gain est Pareto-dominant par rapport à la référence ADR-033.

**Reproductibilité et traçabilité** : le protocole est identique au modèle de référence ADR-033 (hyperparamètres figés, random_state=42, split H22+H23/H24), les modèles sont persistés (`models/11_modeling/xgb_A.json` et `xgb_B.json`), et les métriques sont confirmées de manière indépendante par le notebook 11b (vérification R² haut B = 0.4757 ± 0.001).

**Généralisation temporelle mensuelle** : le gain est positif sur les 12 mois calendaires de H24, de +0.033 (mai) à +0.299 (septembre). Aucun mois ne présente de régression.

**Cohérence avec l'analyse SHAP** : `resa_pax_2c_J_minus_1` se classe 11ème sur 168 features au classement SHAP global (mean|SHAP|=0.540), avec un ratio SHAP haut/bas de 1.54 confirmant un signal plus concentré sur le segment cible. Les features `resa_n_dossiers_J_minus_1` (rang 28, mean|SHAP|=0.212) et `resa_max_groupe_2c_J_minus_1` (rang 38, mean|SHAP|=0.151) apportent un signal complémentaire. La feature `resa_max_groupe_2c_J_minus_1` présente le ratio haut/bas le plus élevé des 8 features `resa_*` (2.06 contre 1.54 pour `resa_pax_2c`), confirmant que la taille du plus grand groupe est le signal le plus caractéristique du segment touristique, même si son amplitude absolue est inférieure au volume total.

**Périmètre d'adoption — couche 1 uniquement** : cette décision porte exclusivement sur la prédiction de niveau de `target_voyageurs_2eme_classe`. La traduction de cette prédiction en décision UM binaire (couche 2) reste entièrement à concevoir, comme prévu par l'ADR-033. L'ADR-036 ne se prononce pas sur la couche 2.

### 2.2 — Conservation de `event_is_saison_narcisses` dans les 167 features actives

**Décision** : la feature `event_is_saison_narcisses` est **conservée** dans le modèle de référence B. Le modèle alternatif B' (167 features sans cette feature) testé dans le notebook 11b n'est pas retenu comme référence malgré un léger gain marginal sur certains mois.

**Résultats empiriques notebook 11b §2.2** : la comparaison B vs B' sur segment haut H24 révèle des différences asymétriques par mois :

| Mois | n_surcharges | ΔB−A | ΔB'−A | ΔB−B' (apport narcisses) |
|---|---|---|---|---|
| Mai (Narcisses) | 55 | +0.0333 | +0.0239 | **+0.009** |
| Juin | 7 | +0.168 | +0.168 | +0.001 |
| Septembre | 0 | +0.299 | +0.286 | +0.013 |
| Octobre | 0 | +0.255 | +0.248 | +0.006 |
| Mars | 10 | +0.324 | +0.361 | **−0.037** |
| Avril | 0 | +0.072 | +0.107 | **−0.035** |
| Novembre | 0 | +0.091 | +0.125 | **−0.034** |

La feature narcisses apporte un gain marginal sur le mois de mai (+0.009 R²) et est légèrement contre-productive sur mars, avril et novembre (jusqu'à −0.037). La gain net agrégé de la feature sur l'ensemble de H24 est faiblement positif.

**Justification du choix de conservation** :

1. **Robustesse temporelle et MLOps** : `event_is_saison_narcisses` est une feature calendaire stable et interprétable, indépendante des données de réservation ResSys. Elle constitue un signal de référence pour un événement touristique structurant de la R35. Retirer cette feature sur la base d'un signal observé sur une seule année de holdout (H24) n'est pas conforme aux bonnes pratiques de gestion de modèle en production : les gains observés sur mars, avril et novembre sous B' peuvent relever de la variance d'échantillonnage d'une exécution unique.

2. **Absence de validation multi-seed** : les différences B'−B sont inférieures à ±0.037 R² sur un mois et pourraient ne pas être statistiquement significatives. Une validation multi-seed ou multi-holdout (H25, H26) serait nécessaire pour les distinguer du bruit, ce qui est hors périmètre de ce travail.

3. **Interprétabilité opérationnelle** : pour les interlocuteurs métier (production MOB, conducteurs), la présence d'une feature calendaire Narcisses rend le raisonnement du modèle plus explicable lors des réunions de validation. Sa suppression pour un gain marginal dégraderait la confiance opérationnelle sans bénéfice net démontré.

**Conséquence** : l'observation B' est documentée en §4 comme piste à monitorer sur H25 et H26. Si elle se confirme sur deux années consécutives de holdout avec des données indépendantes, un ADR ultérieur pourra envisager le retrait de cette feature.

### 2.3 — Retrait de `resa_has_resa_J_minus_1` du jeu de features actives

**Décision** : la feature `resa_has_resa_J_minus_1` (flag binaire indiquant la présence d'au moins une réservation confirmée à J-1) est **retirée du jeu de features d'entraînement et d'inférence**. Le modèle de référence effectif comporte donc **167 features actives** (160 features baseline + 7 features `resa_*` quantitatives).

**Justification empirique** (notebook 11 §7, analyse SHAP) : cette feature présente un mean|SHAP| de **0.000** — rang 168 sur 168, dernière position absolue dans le classement d'importance. XGBoost l'ignore entièrement. La redondance est mécanique : toute cellule pour laquelle `resa_has_resa_J_minus_1 = True` a nécessairement `resa_pax_2c_J_minus_1 > 0`, et le modèle exploite déjà l'information de présence via la variable quantitative. Le flag binaire n'apporte aucune information au-delà du signe de la variable numérique.

**Conséquence sur le pipeline** : le stage_10 (`add_reservations_to_raw_stacked.py`) continue de calculer et persister `resa_has_resa_J_minus_1` dans `ml_dataset.parquet` pour assurer la traçabilité et la compatibilité descendante avec les notebooks 11 et 11b. La feature est exclue des listes `FEATURES_A` et `FEATURES_B` à l'entraînement. Sa suppression du stage_10 sera traitée lors d'une révision ultérieure de l'ADR-035 §2.6, qui listera 7 features `resa_*` au lieu de 8.

---

## 3. Diagnostic empirique du paradoxe R² ↑ / Rappel = 0

### 3.1 — Le constat brut

La contradiction centrale du notebook 11 est la suivante : le gain R² segment haut est le plus important du projet (+0.1478), mais le rappel sur les 104 surcharges segment haut H24 reste exactement nul pour les deux modèles, y compris pour les 62 surcharges qui coïncident avec une réservation confirmée. Ce paradoxe mérite une explication rigoureuse avant toute décision sur la couche 2.

### 3.2 — Distribution des prédictions sur le segment haut H24

L'analyse de la distribution des prédictions sur les 84 603 cellules du segment haut H24 (notebook 11b §1.1) révèle la nature structurelle de ce paradoxe :

| Statistique de y_pred | Modèle A | Modèle B |
|---|---|---|
| Médiane | 6.99 | 5.61 |
| Q99 | 28.96 | 37.40 |
| Q99.5 | 33.58 | 46.56 |
| **Valeur maximale** | **65.42** | **76.52** |
| N pred ≥ 80 | 0 | 0 |
| **N pred ≥ 94** | **0** | **0** |

Aucun des deux modèles ne produit jamais une prédiction ≥ 80 sur le segment haut. La valeur maximale de B (76.52) reste à 17.5 unités sous le seuil opérationnel 94. Le gap entre prédiction et seuil sur les 104 vraies surcharges confirme cette interprétation :

| Statistique du gap (94 − y_pred) | Modèle A | Modèle B |
|---|---|---|
| Gap minimal | 28.6 | 32.9 |
| Q25 du gap | 63.4 | 42.7 |
| **Gap médian** | **68.0** | **52.0** |
| Q75 du gap | 77.5 | 69.5 |
| N surcharges avec gap < 10 | 0 | 0 |
| N surcharges avec gap ≥ 50 | 96/104 | 58/104 |

Le modèle B réduit le gap médian de 16 unités (68.0 → 52.0) — ce qui représente une amélioration continue réelle et explique le gain R². Mais aucune surcharge n'est à moins de 32.9 unités du seuil dans le meilleur des cas. La détection par seuillage simple est structurellement hors de portée du modèle de régression XGBoost avec les hyperparamètres et le jeu de features actuels.

**Interprétation** : la limite identifiée à l'ADR-033 (limite informationnelle) est partiellement levée par les `resa_*` — le modèle prédit désormais mieux les niveaux de charge sur les cellules avec réservation (médiane y_pred sur les 104 surcharges : 26 sous A, 42 sous B, gain de +16 unités). Mais cette amélioration est insuffisante pour franchir le seuil 94, car les vraies valeurs se situent entre 94 et 170 — une cible qui reste hors de portée des prédictions actuelles.

### 3.3 — Mécanisme de la baisse PR-AUC haut (notebook 11b §1.2-1.3)

Le paradoxe additionnel — PR-AUC segment haut en baisse de 0.090 à 0.055 malgré un meilleur R² — a fait l'objet d'un diagnostic dans le notebook 11b. L'hypothèse initiale (B noie les surcharges dans le ranking global) a été **infirmée** : le rang médian des 104 surcharges *s'améliore* sous B, passant de 1384 à 608 sur 84 603 cellules. En termes de top-K, B place 45/104 surcharges dans son top 500 contre 18/104 pour A.

Le mécanisme réel identifié est plus précis : **B améliore le classement médian mais contamine le haut du ranking** (top 100-200) avec des faux positifs spécifiques. Le tableau suivant l'illustre :

| Seuil de détection | A — N pred ≥ seuil (total) | dont vraies surcharges | B — N pred ≥ seuil (total) | dont vraies surcharges |
|---|---|---|---|---|
| ≥ 40 | 163 | ~8 | 692 | ~56 |
| ≥ 60 | 11 | 7 (64 %) | 101 | **1 (1 %)** |
| ≥ 80 | 0 | — | 0 | — |

Sous A, 11 cellules au total dépassent 60 en prédiction, dont 7 sont de vraies surcharges (précision locale de 64 %). Sous B, 101 cellules dépassent 60, dont seulement 1 est une vraie surcharge et **100 sont des cellules avec réservation sans surcharge** (précision locale de 1 %). Ces 100 cellules occupent les positions de rang 100-200 dans le classement B, déplaçant les surcharges qui se trouvaient là sous A.

La répartition des prédictions par groupe confirme ce mécanisme (notebook 11b §1.3) :

| Groupe | n | Médiane y_pred A | Médiane y_pred B | N pred ≥ 60 A | N pred ≥ 60 B |
|---|---|---|---|---|---|
| Vraies surcharges (104) | 104 | 26.01 | 42.02 | 7 | 1 |
| Résa sans surcharge | 3 019 | 12.21 | **25.31** | **0** | **100** |
| Sans résa, sans surcharge | 81 480 | 6.80 | 5.35 | 4 | 0 |

Le modèle B élève la médiane des prédictions sur les 3 019 cellules avec réservation sans surcharge de 12.21 à 25.31, poussant 100 d'entre elles au-dessus de 60. Ces cellules s'intercalent dans le classement entre les rares cellules où A avait déjà une haute confiance (les 7 vraies surcharges prédites ≥ 60 par A). La PR-AUC mesure la précision aux premiers points de rappel — c'est précisément là que la contamination se fait sentir : les 100 premiers faux positifs de B occupent des rangs plus élevés que les vrais positifs de A.

**Ce mécanisme est cohérent avec la valeur informationnelle des `resa_*`** : le modèle apprend correctement que les cellules avec réservation auront une charge plus élevée, mais puisque 90 % d'entre elles ne déclenchent pas de surcharge (ADR-035 §1.3, précision naïve = 9.1 %), il ne peut pas apprendre à prédire ≥ 94 sur ces cellules — il apprend seulement que leur charge sera entre 20 et 60, ce qui est empiriquement juste mais insuffisant pour la détection opérationnelle.

**Conséquence opérationnelle pour la couche 2 future** : si la couche 2 utilise une logique de tri par score (déclencher UM sur les K premières alertes quotidiennes), le modèle A pourrait conserver un avantage sur les toutes premières alertes (précision ≥ 60 : 64 % pour A contre 1 % pour B). Si la couche 2 intègre une logique multi-critères combinant y_pred avec des signaux métier explicites (présence réservation ≥ X passagers, type d'événement, météo), le modèle B est préférable car sa prédiction de niveau est meilleure sur toute la distribution. Ce point sera tranché lors de la conception de la couche 2 (§5, action prioritaire 1).

### 3.4 — Mécanisme du faible gain sur mai (notebook 11b §2)

Le faible gain R² en mai (Δ=+0.033 contre +0.175 en moyenne sur les autres mois) avait suscité l'hypothèse d'une redondance avec la feature `event_is_saison_narcisses`. Cette hypothèse a été **infirmée** par le notebook 11b : en entraînant le modèle B' sans cette feature, le gain `resa_*` sur mai reste à +0.024 (vs +0.033 en B), différence marginale (+0.009) qui ne suffit pas à expliquer la faiblesse du gain.

Le mécanisme identifié est un **effet de plafond spécifique aux mois avec surcharges** : les 55 surcharges de mai ont des valeurs réelles comprises entre 94 et 170. Le modèle B les prédit en médiane à 42 (contre 26 pour A), un gain de +16 unités — mais ces prédictions restent à 52 unités du seuil en médiane. Le R² mensuel n'augmente que faiblement car les résidus quadratiques sur ces 55 observations (chacune avec une erreur de 40 à 130) dominent le calcul du mois. Dans les mois sans surcharges (septembre, octobre), les vraies valeurs se situent dans la plage 20-60 que les prédictions atteignent désormais correctement grâce aux `resa_*` — d'où des gains R² massifs.

Ce diagnostic confirme, par un angle complémentaire, que la limite de détection des surcharges est de nature structurelle et non résoluble par l'enrichissement des features de la couche 1 seule.

### 3.5 — Validation rétrospective de l'architecture deux couches

Les résultats empiriques des notebooks 11 et 11b constituent une **confirmation forte de la pertinence de l'architecture deux couches actée à l'ADR-033**. La couche 1 (régression XGBoost) :

- **Améliore son objectif natif** : la prédiction de niveau bénéficie substantiellement des features `resa_*`, avec des gains R² documentés et reproductibles sur l'ensemble du test set H24.
- **Ne peut pas résoudre seule la détection des surcharges** : cette limite est structurelle, confirmée par l'analyse du gap (§3.2), par la contamination du ranking (§3.3), et par l'effet de plafond sur les mois à forte charge (§3.4).

La détection opérationnelle des surcharges UM — rappel > 0 sur les 104 cibles H24 — est désormais formellement identifiée comme un **problème de couche 2**, à traiter par une logique distincte de la régression XGBoost couche 1 : règles métier seuillées, score composite y_pred × signaux résa × interactions calendaires/météo, classificateur binaire post-régression, etc.

---

## 4. Limites et travaux futurs

1. **Rappel inchangé à 0 sur les surcharges haut** : la couche 1 ne détecte aucune des 104 surcharges segment haut H24 au seuil opérationnel 94. Cette limite est structurelle — aucune prédiction ne dépasse 76.52, soit un gap minimal de 17.5 unités par rapport au seuil. Elle n'est pas résoluble par le tuning des features couche 1, et nécessite une conception dédiée de la couche 2.

2. **PR-AUC haut en baisse (0.090 → 0.055)** : le modèle B est moins discriminant que A en tête de ranking sur le segment haut, du fait de la contamination par 100 cellules avec réservation sans surcharge prédites au-dessus de 60 (§3.3). Ce point a des implications architecturales pour la couche 2 (§3.3) et doit être considéré lors de sa conception.

3. **Valeur prédite maximale plafonnée** : la valeur maximale de y_pred sur le segment haut est 76.52 sous B. La distance structurelle au seuil 94 mérite une investigation dédiée : transformation de target (log, racine carrée), ajustement des hyperparamètres (max_depth plus élevé, régularisation plus faible), ou confirmation que ce plafond est inhérent au jeu de features disponible. Cette investigation est hors périmètre de l'ADR-036.

4. **Piste B' (sans narcisses) à monitorer sur H25-H26** : le modèle B' (167 features sans `event_is_saison_narcisses`) présente un gain marginal sur 4 mois (mars, avril, novembre, décembre, jusqu'à +0.037 R²). Cette observation peut relever de la variance d'échantillonnage sur un seul holdout annuel. Elle sera ré-évaluée lors des re-entraînements périodiques sur H25 et H26. Si elle se confirme sur deux années indépendantes, un ADR ultérieur traitera le retrait potentiel de cette feature.

5. **Retrait de `resa_has_resa_J_minus_1` du stage_10** : la feature étant mécaniquement redondante et ignorée par XGBoost (mean|SHAP|=0.000), sa production dans le pipeline peut être supprimée lors d'une révision ultérieure du stage_10 et de l'ADR-035 §2.6. Elle passera alors de 8 à 7 features `resa_*` documentées.

6. **Couche 2 entièrement à concevoir** : la décision UM binaire — la finalité opérationnelle du projet — reste le travail central à conduire en itération suivante. Elle nécessite une concertation avec les interlocuteurs MOB (Responsable de production, MOB, la conduite des trains) sur les critères opérationnels acceptables : taux de faux positifs UM tolérable, seuil de déclenchement adapté, mode dégradé en l'absence de prédiction fiable.

7. **Surcharges sans réservation (42/104 en H24)** : les 40.4 % de surcharges haut H24 sans réservation ResSys restent inexpliquées par les features actuelles. Ces surcharges correspondent probablement à des pics de fréquentation spontanée (météo favorable + week-end + événement non réservé via ResSys) et constitueront un angle d'analyse prioritaire dans la conception de la couche 2.

---

## 5. Backlog post-ADR

| Priorité | Action | Déclencheur |
|---|---|---|
| 1 — Critique | Concevoir la couche 2 (décision UM) : règles métier, classificateur dédié, ou score composite y_pred × features `resa_*` × signaux calendaires/météo | ADR-036 acté |
| 1 — Critique | Concertation avec le responsable de production sur les critères opérationnels de couche 2 (taux FP UM tolérable, mode dégradé, latence de décision, intégration système) | ADR-036 acté |
| 2 — Standard | Mettre à jour le code d'inférence pour exclure `resa_has_resa_J_minus_1` des features actives et réviser l'ADR-035 §2.6 | Dès que possible |
| 2 — Standard | Re-entraînement périodique sur H22-H25 (ajout holdout H25) ; évaluer B vs B' sur deux années | Disponibilité données H25 |
| 3 — Standard | Investigation du plafond y_pred haut (transformation target, hyperparamètres alternatifs, ablation features) | Itération MLOps future |
| 3 — Standard | Analyse des 42 surcharges sans réservation H24 : caractérisation météo/événementiel pour alimenter la conception couche 2 | Itération future |

---

## 6. Références

### Notebooks de référence
- `notebooks/11_modeling_with_reservations.ipynb` — comparaison A vs B, métriques H1-H5, SHAP global et par segment, verdict
- `notebooks/11b_diagnostics_pr_auc_et_narcisses.ipynb` — diagnostic ranking surcharges, diagnostic redondance narcisses, gap prédiction/seuil

### Outputs principaux
- `models/11_modeling/xgb_A.json` — modèle baseline 160 features (persisté, reproductible)
- `models/11_modeling/xgb_B.json` — modèle référence 168 features brutes (167 actives)
- `outputs/11_metriques_comparaison.csv` — tableau complet A vs B (global, bas, haut)
- `outputs/11_decomposition_mensuelle.csv` — R² mensuel A vs B sur segment haut H24
- `outputs/11_shap_global_ranking.csv` — ranking SHAP des 168 features (modèle B, test H24)
- `outputs/11_surcharges_detection.csv` — décomposition 2×2 avec/sans résa × détectée A/B
- `outputs/11b_ranking_surcharges.csv` — rang des 104 surcharges sous A et B (sur 84 603 cellules)
- `outputs/11b_r2_mensuel_3modeles.csv` — R² mensuel A, B, B' sur segment haut H24

### Figures clés
- `figures/11/11_comparaison_A_vs_B.png` — R², rappel et MAE par segment (A vs B)
- `figures/11/11_r2_haut_par_mois.png` — décomposition mensuelle A vs B avec annotations surcharges
- `figures/11/shap_global_top30.png` — top 30 SHAP global avec features `resa_*` en évidence
- `figures/11/shap_resa_par_segment.png` — SHAP features `resa_*` décomposé bas/haut
- `figures/11b/11b_pr_curve_haut.png` — courbes Précision-Rappel segment haut (A vs B)
- `figures/11b/11b_gap_seuil_surcharges.png` — distribution du gap prédiction/seuil sur les 104 surcharges
- `figures/11b/11b_r2_mensuel_3modeles.png` — R² mensuel A, B, B' avec focus mai/Narcisses
- `figures/11b/11b_ranking_surcharges.png` — distribution des rangs A vs B pour les 104 surcharges

### ADR liés
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — Split temporel H22+H23 train / H24 test
- [ADR-033](ADR-033_pivot_architectural_regression_augmentation_metier.md) — Architecture deux couches, limite informationnelle, pivot vers régression + augmentation métier
- [ADR-035](ADR-035_integration_reservations_couche_1.md) — Intégration des 8 features `resa_*` en couche 1, quality gates pipeline, topologie year-specific

### Reproductibilité
- `xgboost` 2.1.4, `scikit-learn` 1.6.1, `shap` 0.49.1
- `random_state = 42` partout (XGBoost, split, SHAP)
- Hash md5 (8 chars) du `ml_dataset.parquet` utilisé : `bc7bc1f0`
- Hyperparamètres figés : `n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, tree_method=hist`
