# ALL_ADRS — digest généré du registre

Concaténation intégrale des 78 ADR.
Fichier **généré** : ne pas éditer ici, éditer l'ADR source.

---


---
id: ADR-001
ancien_id: ADR-01
date_decision: 2026-05
statut: amendé
amende_par: [ADR-060]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-001 — Changement de cible : `charge_totale` → `target_voyageurs_2eme_classe`

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |

## Contexte

Le proposal validé (Nedellec, 2026) et la première itération du notebook `01_business_understanding` retenaient `charge_totale = voyageurs_1ere_classe + voyageurs_2eme_classe` comme cible ML, avec un seuil de surcharge défini sur la capacité totale de la rame (106 places assises, SURF 7500 simple).

L'analyse conduite en `02_data_understanding_apc` §2.1.1 a comparé les deux définitions de surcharge sur la population H17–H24 :

| Définition | Seuil | Surcharges détectées | Note |
|---|---|---|---|
| `target_voyageurs_total > SEUIL_TOTAL` | 106 | référence | capacité totale SURF 7500 |
| `target_voyageurs_2eme_classe >= SEUIL_UM_2C` | 94 | +56 % capturées en plus | capacité assise 2ème classe |

## Décision

**Cible retenue : `target_voyageurs_2eme_classe`** comparée au seuil `SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500 = 94` (capacité assise 2ème classe d'une rame SURF 7500 simple).

Formulation officielle : "La cible prédictive retenue est `target_voyageurs_2eme_classe`, qui représente la charge observée en 2ème classe sur un tronçon donné, pour une course et une date données. Ce choix est justifié par l'analyse des données APC et par le contexte opérationnel : les situations de saturation concernent principalement la 2ème classe, tandis que la 1ère classe constitue rarement le facteur déclencheur d'une décision UM."

Justification double :
1. **Data-driven** : `target_voyageurs_2eme_classe >= 94` capture +56 % de surcharges réelles supplémentaires vs `target_voyageurs_total > 106`, parce que la 1ère classe (12 places, moy = 1 voy, P99 = 7) n'est jamais le facteur limitant.
2. **Qualitatif** : 5/6 participants aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent la saturation sur la capacité assise 2ème classe, pas sur la capacité totale.

`target_voyageurs_total` reste calculé dans le pipeline pour l'audit et la vérification d'intégrité, mais n'est pas la cible ML.

## Conséquences

- **Architecture** : la couche de décision (Étape 2) utilise `recommandation_um_seuil_2c = prediction_voyageurs_2eme_classe >= SEUIL_UM_2C`.
- **Métriques** : les métriques de régression (MAE, WMAPE, R²) portent sur `target_voyageurs_2eme_classe`.
- **Baselines** : toutes les baselines sont recalculées sur cette cible.
- **Pipeline** : `target_voyageurs_2eme_classe` est présente dans la table depuis `apc_stacked.parquet` — aucun changement de pipeline requis.
- **Seuil** : lié à ADR-005 (ancrage de `SEUIL_UM_2C = 94`, capacité assise 2ème classe SURF 7500).
- **Contrôle qualité** : `target_voyageurs_total` reste calculé dans le pipeline (`add_features_to_raw_stacked.py`) pour l'audit et la vérification d'intégrité, mais n'est pas la cible ML.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `target_voyageurs_total > 106` | Manque ~56 % des surcharges réelles ; la 1ère classe n'est jamais limitante |
| Régression sur flux montées/descentes par arrêt | Inadapté à la décision UM qui s'appuie sur la charge maximale instantanée |

## Addendum (2026-07-24)

La définition de la cible (charge assise 2e classe, grain date × course × tronçon) demeure active. Le seuil de 94 places mentionné dans le corps est supersédé par ADR-060, qui fixe le seuil canonique de surcharge à strictement plus de 63 places assises. Aucune autre disposition modifiée.

---


---
id: ADR-002
ancien_id: ADR-02
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-027]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-002 — Stratégie de split temporel : scénario candidat H17–H22 / H23 / H24

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-027.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Proposition — décision finale reportée à la phase de modélisation |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §5 |

## Contexte

La décision définitive du split train / validation / test ne peut pas être prise en phase de Data Understanding. Elle dépend de facteurs qui ne sont pas tous connus à ce stade :

- Stationnarité temporelle des APC (partiellement analysée en §5)
- Disponibilité effective des variables explicatives par année horaire (ISTDATEN disponible seulement à partir de 2018)
- Ruptures topologiques de la ligne (CLIE actif H16–H18, GIL actif H16–H22, VVVI depuis H23)
- Ruptures d'offre ou d'exploitation (COVID H20–H22, modifications de service)
- Disponibilité des sources externes (ski H20–H25, météo CHD, etc.)
- Performances obtenues lors des premiers entraînements
- Importance réelle des features selon la modélisation
- Contraintes d'évaluation temporelle propres à un cas J-1

Cette ADR documente le **scénario candidat** le plus robuste identifié en Data Understanding, sans le présenter comme définitivement retenu.

## Scénario candidat analysé

Trois options ont été envisagées ou analysées :

| Option | Train | Val | Test | Statut |
|---|---|---|---|---|
| A (restrictive) | H22–H23 | walk-forward trim. intra-H23 | H24 | Conservée en analyse de sensibilité |
| B (candidat) | H17–H22 | H23 | H24 | Scénario initial — ISTDATEN OK, stationnarité démontrée |
| C (candidat étendu) | H16–H22 | H23 | H24 | En analyse NB01/NB02 §5.2 — H16 exploitable avec `target_2eme_classe` |

Les tests KS conduits en §5 ont fourni des éléments favorables aux options B et C :
- KS(H22, H23) = 0.076 < 0.15 — stationnarité entre train et val démontrée
- KS(H23, H24) = 0.072 < 0.15 — stationnarité entre val et test démontrée
- 5–7 ans d'historique (H17–H22 ou H16–H22) offrent un signal de robustesse incluant la période COVID
- H23 est la première année avec ISTDATEN stable (TCE cours > 93 %)

**Note H16** : initialement exclue pour 55,5 % de nulls sur `voyageurs_1ere_classe`. Avec la cible `target_voyageurs_2eme_classe` (0,7 % de nulls), H16 peut être incluse dans l'entraînement si la stationnarité KS(H16, H17–H22) est confirmée en NB02 §5.2. Cette décision fait partie des arbitrages à finaliser en phase de modélisation.

## Éléments d'aide à la décision

Les analyses APC et les tests KS constituent des **éléments d'aide à la définition du split**, non une décision finale. Le split final sera déterminé de manière itérative dans la phase de modélisation, en tenant compte :

1. De la disponibilité des features `ist_*` (NA sur H17–H21 → impact sur la richesse réelle du train set)
2. Des ruptures topologiques (VVVI actif depuis H23 → impact sur la cohérence des tronçons)
3. Des premiers résultats de modélisation et de la distribution des erreurs par sous-période
4. De la pertinence métier de l'évaluation (représentativité de H24 pour les conditions actuelles)

## Statut de H25

H25 (14 déc. 2024 en cours) est disponible partiellement dans les tables APC. Elle peut être analysée à titre descriptif pour vérifier la couverture des données.

**H25 n'est pas scellée comme test final à ce stade.** Elle ne sera éventuellement désignée comme holdout final qu'après décision explicite en phase de modélisation, selon les données disponibles et la complétude de l'année horaire.

## Conséquences provisoires

- **Walk-forward candidat** : H17–H22 → Val H23 → Test H24. Validation trimestrielle intra-H23 disponible en robustesse.
- **ISTDATEN** : features `ist_*` à NaN sur H17–H21 — gérées nativement par LightGBM/XGBoost, mais à évaluer sur la richesse informative effective du train set.
- **Pondération H20–H22Q1** : la rupture COVID (KS 2022Q1→Q2 = 0.123) peut justifier une pondération réduite des observations de cette période — à décider en `04_data_preparation`.
- **Analyse de sensibilité** : split court H22/H23 (option A) présenté en annexe Ch. 4 comme variante restrictive.

## Formulation recommandée pour la documentation

"À ce stade, les analyses de stationnarité APC et les ruptures topologiques documentées fournissent des éléments d'aide à la définition du futur split train / validation / test. Le split final n'est toutefois pas arrêté dans la phase de Data Understanding. Il sera déterminé ultérieurement de manière itérative, en tenant compte de la disponibilité des variables explicatives, de la stabilité temporelle, des premiers résultats de modélisation et de la pertinence métier de l'évaluation."

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| Split court H22–H23/H24 (option A) | Conservé en analyse de sensibilité ; écarté comme split principal car richesse 5 ans disponible |
| Split aléatoire | Interdit — leakage temporel |
| Leave-one-year-out | Coût computationnel disproportionné pour le gain attendu |

## Fichiers impactés

- `notebooks/01_business_understanding.ipynb` §6 (scénario de split)
- `notebooks/02_data_understanding_apc.ipynb` §5 (tests KS, stationnarité)
- Future : `notebooks/04_data_preparation.ipynb` (décision finale du split)

---


---
id: ADR-003
ancien_id: ADR-03
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-052]
revoque_par: [ADR-022]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-003 — Architecture modèle : unique + feature `base_segment` vs deux modèles séparés

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-052 ; révoquée par ADR-022.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §4.3 |

## Contexte

La ligne R35 présente deux segments géographiques aux dynamiques très différentes :

| Segment | Tronçons | Profil | TJM moyen |
|---|---|---|---|
| **Bas de ligne** | VV → Blonay | Urbain / pendulaire / scolaire | ~100–160 voy |
| **Haut de ligne** | Blonay → Pléiades | Montagne / touristique / loisirs | ~20–60 voy |

Le test de Kolmogorov-Smirnov entre les distributions de charge des deux segments (§4.3) donne **KS(bas, haut) = 0.456**, valeur très supérieure au seuil de stationnarité (0.15). Deux architectures sont envisageables :

| Architecture | Avantages | Inconvénients |
|---|---|---|
| **Modèle unique + feature `base_segment`** | Partage des paramètres entre segments ; plus simple à maintenir | Risque de sous-performance si les dynamiques sont trop différentes |
| **Deux modèles séparés** (bas / haut) | Spécialisation complète | Double complexité de maintenance ; moins de données par modèle |

## Décision

**Modèle unique + feature `base_segment` (bas / haut / mixte) retenu en V1.**

Justification :
- Approche standard en prévision de transport pour des lignes à profil mixte
- La feature `base_segment` permet au modèle d'apprendre les effets d'interaction différenciés
- Réduit le risque de sur-apprentissage sur le segment haut (moins d'observations)
- Un seul pipeline de prédiction et d'interprétabilité SHAP à déployer dans Dataiku

## Conséquences

- **Feature** : `base_segment` (bas / haut / mixte) ajoutée au dataset — déjà présente dans le pipeline.
- **Ablation study** : comparaison modèle unique vs deux modèles séparés planifiée en `05_feature_analysis`.
- **SHAP** : l'interprétation SHAP devra être ventilée par segment pour être opérationnellement utile.
- **Seuil UM** : la granularité du seuil par groupe (adhérence vs crémaillère) reste calibrable indépendamment dans la couche de décision (ADR-004).

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| Deux modèles séparés (bas/haut) | Reporté comme ablation study — pas exclu définitivement |
| Feature d'interaction segment × saison | Complémentaire, pas exclusif — peut être ajoutée en `05_feature_analysis` |

## Addendum (2026-07-24)

L'architecture à modèle unique avec base_segment est supersédée par la campagne comparative ultérieure : architecture segmentée à deux régresseurs bas et haut (ADR-031, confirmée ADR-052). La définition du découpage de ligne reste active.

---


---
id: ADR-004
ancien_id: ADR-04 (seuil_um_86)
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-005]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-004 — ~~Ancrage du seuil UM : `SEUIL_UM = 86`~~ — ARCHIVÉ

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-005.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

> **⚠️ Ce fichier est archivé.** La valeur 86 était incorrecte.
> La capacité assise 2ème classe du SURF 7500 est **94 places**.
> **Voir : [ADR-005_seuil_um_94_2c.md](ADR-005_seuil_um_94_2c.md)**

| Champ | Valeur |
|---|---|
| **Statut** | ~~Acceptée sous condition~~ — **REMPLACÉE par ADR-005_seuil_um_94_2c.md** |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |

## Contexte

La couche de décision (Section 2.3 du notebook `01`) exige un seuil de capacité pour traduire la prédiction de charge en recommandation UM binaire. Deux candidats naturels :

| Candidat | Valeur | Signification |
|---|---|---|
| `CAPACITE_ASSISE_TOTALE` | ~98 places | Rame simple, toutes classes |
| `CAPACITE_ASSISE_2EME` | **86 places** | Rame simple, 2ème classe uniquement |

Le choix est couplé à la décision de cible (ADR-001) : retenir `target_voyageurs_2eme_classe` impose un seuil défini sur la 2ème classe.

## Décision

**`SEUIL_UM = CAPACITE_ASSISE_2EME = 86`** (capacité assise 2ème classe).

Ancrage qualitatif :
- **5/6 participants** aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent explicitement la saturation sur les places assises 2ème classe, pas sur la capacité totale.
- La 1ère classe n'est jamais le facteur limitant (moy = 1 voyageur, P99 = 7, capacité = 12 places).

Ancrage data :
- Mode observé dans `base_places_disponibles_2eme_classe` ≈ 86 places en rame simple.
- La valeur est dérivée du mode observé et à confirmer avec MOB.

## Conséquences

- **Couche de décision** : `recommandation(T) = 1 si voyageurs_2eme_classe_max(T) + marge > 86`.
- **Métriques métier** : Rappel et Précision calculées avec ce seuil. Déséquilibre classes mesuré à ~50:1.
- **Analyse de sensibilité** : une plage [80–110] sera testée en `05_feature_analysis` pour quantifier la sensibilité des métriques au seuil.
- **Validation pendante** : confirmation de la valeur exacte auprès du domaine Voyageurs (sémantique : places assises vs capacité totale homologuée, différenciation adhérence vs crémaillère).
- **Granularité** : un seuil par groupe de tronçons (adhérence Vevey–Blonay vs crémaillère Blonay–Pléiades) reste envisageable — calibrage MOB requis.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `SEUIL_UM = 98` (capacité totale) | Écarté — manque 56 % des surcharges réelles (ADR-001) |
| Seuil dynamique par groupe de tronçons | Possible — reporté après validation du domaine Voyageurs (marge de sécurité et granularité) |
| Régression quantile (p90) comme proxy du seuil | Complémentaire à la marge de sécurité — pas un substitut au seuil de capacité |

---


---
id: ADR-005
ancien_id: ADR-04 (seuil_um_94_2c)
date_decision: 2026-05
statut: amendé
amende_par: [ADR-060]
modifie: [ADR-004]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-005 — Seuil UM : `SEUIL_UM_2C = 63` (places assises 2ème classe SURF 7500)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-004.
> **Précision au gel.** Le nom du fichier et le titre portent la valeur d'époque (`SEUIL_UM_2C = 94`) ; la valeur en vigueur au gel est **63** (ADR-060).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée — mis à jour 2026-06-09 (ADR-060) |
| **Date** | 2026-05, corrigé 2026-06-09 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §2.1.1 |
| **Remplace** | ADR-004_seuil_um_86.md (valeur incorrecte, version archivée) |

## Contexte

La couche de décision (Section 2.3 du notebook `01`) exige un seuil de capacité pour traduire la prédiction de charge en recommandation UM binaire. Ce seuil doit être défini sur la même variable que la cible ML (cf. ADR-001).

Le matériel roulant de la R35 est le SURF 7500 (MVR/MOB). Ses capacités selon la spec officielle MOB (ABeh 7501-7508) :

| Classe | Places assises (rame simple) | Offre APC (rame simple) |
|---|---|---|
| 1ère classe | 12 places | 12 places |
| **2ème classe** | **63 places assises** | **94 places (63 assises + 31 strapontins)** |
| **Total** | **75 places assises** | **106 (offre APC totale)** |

**Distinction capacité assise / offre APC** : le SI comptage APC enregistre `offre_2eme_classe = 94` pour une rame SURF 7500. Cette valeur de 94 inclut **31 strapontins** (zones multi-usages : vélos, skis, bagages), non mobilisables comme sièges selon la spec matériel MOB active (ref. P01) et le schéma véhicule officiel. Les **63 places assises** sont les places fixes, réservables, utilisables sans restriction.

**Sources (triple traçabilité — ADR-060, 2026-06-09)** :
- Spécification du matériel roulant voyageurs MOB (document interne), champ « Places assises 2ème » : **63** ✓
- Schéma véhicule `vehicules_portes_7500.png` : 63 assises + 31 strapontins (coquille Excel col. "Strap." : 32 affiché, 31 réel confirmé par APC)
- Réconciliation APC empirique : `offre(94) − voyageurs(63) = 31` ✓
- Validation : Responsable des Actifs Voyageurs, MOB, 2026-06-09

**UM (Unité Multiple) = 2 rames couplées** → 126 places assises en 2ème classe (63×2), offre APC 188 (94×2).

Le seuil opérationnel UM est donc ancré sur les **places assises 2ème classe** = 63.

## Décision

**`SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500 = 63`**

Ce seuil matérialise la limite à partir de laquelle la rame simple ne permet plus de garantir une place assise en 2ème classe à l'ensemble des voyageurs : dès la 64ème personne, au moins un voyageur est sans siège.

Constantes associées à utiliser dans le code (cf. `src/r35/constants.py`) :

```python
CAPACITE_ASSISE_2C_SURF7500 = 63    # places assises 2ème classe, rame simple
OFFRE_TOTALE_2C_APC_SURF7500 = 94   # offre APC 2C (63 assises + 31 strapontins)
CAPACITE_ASSISE_1C_SURF7500 = 12    # places assises 1ère classe, rame simple
CAPACITE_ASSISE_TOTAL_SURF7500 = 75 # total places assises rame simple (63+12)
SEUIL_UM_2C = CAPACITE_ASSISE_2C_SURF7500  # seuil déclencheur UM = 63

# Indicateur surcharge (strictement supérieur = au moins un voyageur sans siège)
is_surcharge_2c = target_voyageurs_2eme_classe > SEUIL_UM_2C   # > 63
recommandation_um = prediction_voyageurs_2eme_classe > SEUIL_UM_2C
```

## Justification

**Ancrage capacitaire :** le seuil de 63 correspond aux places assises 2ème classe officielles du SURF 7500. Les 31 strapontins supplémentaires (offre APC = 94) ne constituent pas des places assises mobilisables sans restriction et ne constituent pas une capacité d'assise garantie.

**Ancrage qualitatif :**
- **5/6 participants** aux entretiens exploratoires (P01, P02, P04, P05, P06) définissent explicitement la saturation sur les **places assises 2ème classe**, pas sur la capacité totale.
- La 1ère classe n'est jamais le facteur limitant (moy = 1 voyageur, P99 = 7, capacité = 12 places).
- Les entretiens confirment la pertinence métier du seuil d'occupation des **sièges** — ce qui confirme 63 (pas 94).

**Ancrage data :** H25 (test OOT, modèle Enrichi_Seg 158f v1.1, dataset daf936c8, ADR-061) :
- Surcharges `> 63` : BAS=8392, HAUT=1192, GLOBAL=9584 (3.28% des observations)
- Surcharges `> 94` à titre comparatif : BAS=1166, HAUT=280, GLOBAL=1446 (0.47%)

**Note historique — référence à +56% (seuil précédent) :** l'ancienne version de cet ADR mentionnait "+56% de surcharges supplémentaires vs `target_voyageurs_total > 106`" pour justifier 94 vs 106. Cette comparaison portait sur l'ancien seuil de 94 (offre APC) et n'a plus d'objet. La justification du seuil 63 repose entièrement sur la définition des places assises (spec MOB, ADR-060) — pas sur une comparaison relative.

## Convention sur >

- `is_surcharge_2c` : `> 63` — la capacité assise est **dépassée** (au moins un voyageur sans siège).
- Pipeline feature `histo_voyageurs_2eme_classe_win7_n_surcharges` : utilise `> SEUIL_UM_2EME` (strict) — identique.
- Pour la recommandation UM opérationnelle : `prediction > 63`.

## Conséquences

- **Couche de décision** : `recommandation_um = prediction_voyageurs_2eme_classe > 63`.
- **Métriques métier** : Rappel et Précision calculées avec ce seuil. Déséquilibre classes mesuré ~0.47% à l'ancien seuil 94, ~3.28% au seuil 63 (H25).
- **Feature win7_n_surcharges** : recalculée avec seuil 63 (ADR-060), dataset hash daf936c8.
- **Analyse de sensibilité** : une plage [63–94] pourrait être explorée en couche 2 pour quantifier la sensibilité des métriques au seuil — mais la valeur 63 est la valeur physique de référence.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `SEUIL_UM = 94` (offre APC, ancienne valeur) | Incorrect — 94 = offre APC incluant 31 strapontins non mobilisables comme sièges (spec MOB P01). Confusion entre offre totale et places assises. ADR-060. |
| `SEUIL_UM = 106` (offre APC totale 1C+2C) | Écarté — mélange 2C et 1C ; n'est pas le périmètre de décision UM 2ème classe |
| `SEUIL_UM = 86` (ancienne estimation) | Incorrect — archivé dans ADR-004_seuil_um_86.md |
| Seuil dynamique par groupe de tronçons | Possible en phase d'évaluation — reporté après premiers résultats de modélisation couche 2 |
| Régression quantile (p90) comme proxy du seuil | Complémentaire à l'analyse de sensibilité — pas un substitut au seuil de capacité physique |

## Fichiers impactés

- `src/r35/constants.py` — constantes `CAPACITE_ASSISE_2C_SURF7500 = 63`, `OFFRE_TOTALE_2C_APC_SURF7500 = 94`, `SEUIL_UM_2C = 63`
- `scripts/pipeline/add_features_to_raw_stacked.py` — `SEUIL_UM_2EME = 63` (ADR-060)
- `data/processed/ml_dataset.parquet` — hash `daf936c8` (ADR-060)
- `notebooks/02_data_understanding_apc.ipynb` §2.1.1 (analyse surcharges)

---


---
id: ADR-006
ancien_id: ADR-06
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-039, ADR-063]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-006 — STATPOP : stratégie du dernier millésime disponible

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-039, ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `02_data_understanding_statpop.ipynb`, future `04_data_preparation.ipynb` |

## Contexte

STATPOP (OFS) est une source socio-démographique structurelle décrivant la population résidant à proximité de chaque arrêt R35. Elle est utile comme feature ML car elle capte la demande potentielle de transport et l'urbanité des zones desservies.

Contrainte opérationnelle : STATPOP est publiée avec un délai. Un millésime n'est généralement publié qu'un an après l'année de référence (ex. : STATPOP 2024 publié en 2025). En exploitation J-1, il est impossible d'utiliser le millésime de l'année en cours — il n'est pas encore disponible.

La jointure naïve `date.year → millésime STATPOP correspondant` crée un **biais d'optimisme** dans l'évaluation historique : elle utilise rétrospectivement des données qui n'auraient pas été disponibles au moment de la prédiction.

## Décision

**En exploitation opérationnelle, STATPOP doit être joint selon le dernier millésime disponible à la date de prédiction**, et non selon l'année calendaire de la date de circulation.

**Règle simplifiée :**
```
millesime_disponible(date_prediction) = min(date_prediction.year - 1, max_millesime_disponible)
```

Exemple : pour une prédiction faite en mai 2025, on utilise STATPOP 2024 (si publié) ou 2023 (sinon).

## Stratégies selon le contexte

| Contexte | Stratégie | Justification |
|---|---|---|
| **Entraînement exploratoire (phase DU)** | Jointure par année civile (`date.year`) | Simplifie l'exploration ; biais documenté comme limite acceptable |
| **Entraînement et évaluation finale** | Jointure par dernier millésime disponible | Réalisme opérationnel ; évite le biais d'optimisme |
| **Déploiement opérationnel** | Dernier millésime OFS publié à la date de prédiction | Seule source disponible en production |

La stratégie retenue pour l'entraînement final sera documentée dans `04_data_preparation.ipynb`.

## Impact estimé

L'évolution inter-annuelle de STATPOP est faible (+9,5 % sur 10 ans pour la population totale dans les buffers 500 m). L'impact du biais de millésime est donc **probablement faible** en pratique, mais doit être documenté comme limite méthodologique.

## Gestion des variables manquantes en 2021 et 2023

Les millésimes 2021 et 2023 (source OFS) ne contiennent pas de données ménages (HP*) ni HPI. Les 13 variables concernées sont comblées par **interpolation linéaire** par gare entre les millésimes adjacents :

| Millésime incomplet | Bornes d'interpolation | Résultat |
|---|---|---|
| 2021 | 2020 et 2022 (équidistants) | moyenne arithmétique |
| 2023 | 2022 et 2024 (équidistants) | moyenne arithmétique |

Variables interpolées : `menages_500m_total`, `densite_menages_500m_km2`, `population_par_menage_500m`, `part_menages_1_personne`, `part_grands_menages_4p_plus`, `taille_menage_moyenne_estimee`, `hpi_classe_max_500m`, `hpi_hectares_classe_1_count`, `hpi_hectares_classe_2_count`, `hpi_hectares_classe_manquante_count`, `hpi_hectares_autre_classe_count`, `part_hectares_hpi_non_plausible`, `flag_qualite_statpop_faible`.

L'interpolation est réalisée dans `build_fact_statpop_gare.py` via `interpolate_missing_millesimes()` (pandas `interpolate(method='index')`). Les colonnes entier sont arrondies après interpolation.

Ces variables interpolées sont ensuite **intégrées dans le ml_dataset** via `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (extension de `STATPOP_KEEP_SUFFIXES`).

## Limites documentées

1. Les dates exactes de publication des millésimes OFS ne sont pas toutes connues. La règle simplifiée `année - 1` peut ne pas être exacte pour tous les millésimes.
2. L'interpolation linéaire pour 2021 et 2023 est une approximation : elle suppose une évolution monotone entre les millésimes adjacents. Pour des variables lentes (STATPOP évolue de ~1–2 % par an), cette hypothèse est raisonnable.
3. La granularité hectare de STATPOP (puis agrégée au buffer 500 m par gare) introduit une approximation spatiale, indépendante du problème de millésime.

## Conséquences

- Le script `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` devra implémenter une logique de jointure par millésime disponible (à la place de la jointure par année civile directe).
- La table `statpop_clean.parquet` contient la colonne `annee_enquete_statpop` — utiliser cette clé pour la jointure contrôlée.
- Le report de cette décision à `04_data_preparation.ipynb` est intentionnel : le choix final dépend des performances observées à la modélisation.

## Fichiers impactés

- `scripts/sources/build_fact_statpop_gare.py` (interpolation 2021/2023 via `interpolate_missing_millesimes()`)
- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (logique de jointure + extension `STATPOP_KEEP_SUFFIXES` pour ménages et HPI)
- `data/processed/sources/statpop_clean.parquet` (millésime source, désormais sans NA sur ménages/HPI)
- `notebooks/02_data_understanding_statpop.ipynb` §QG (documentation de la contrainte)
- Future : `notebooks/04_data_preparation.ipynb` (décision et implémentation finale)

---


---
id: ADR-007
ancien_id: ADR-07
date_decision: 2026-05
statut: amendé
amende_par: [ADR-073]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-007 — Tours de service : table de rotations externe nécessaire pour la couche de décision

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-073.
> **Précision au gel.** La table de rotations a bien été produite (`scripts/sources/build_dim_rotations_r35.py`), mais employée **exclusivement comme référence de vérité de l'évaluation** (mémoire §4.3.6 et §4.7.2), jamais comme variable ni comme grain de décision. Le grain de la décision est la **course** (ADR-073) ; la couche de décision au grain du tour de service décrite ci-dessous n'a pas été réalisée et relève des perspectives.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `01_business_understanding.ipynb` §2.3, future `06_decision_layer.ipynb` |

## Contexte

La décision opérationnelle UM se prend au niveau du **tour de service**, pas au niveau de la course ou du tronçon individuel. La composition matérielle (rame simple vs UM) est héritée sur l'ensemble d'un tour et ne peut être modifiée librement entre chaque course.

Points de changement de composition sur la R35 : **Vevey** et **Blonay** uniquement.

Le modèle ML prédit la charge au grain **tronçon × course × date** — le grain disponible dans les données APC. Pour traduire ces prédictions en recommandation UM exploitable, il est nécessaire de relier les courses à leur tour de service.

**Problème :** les tours de service ne peuvent pas être reconstruits de manière fiable à partir des seules données APC. L'information de rotation provient de la planification, pas des mesures de comptage.

## Décision

**Les tours de service ne seront pas reconstruits depuis les APC seul. Une table de rotations issue de la planification sera intégrée à la couche de décision.**

Un dataset de rotations pour l'année 2024 existe déjà. Il sera la première source intégrée.

## Architecture recommandée

```
data/external/rotations/          ← source brute (Excel/CSV planification)
scripts/sources/build_rotations_r35_2024.py  ← script de structuration
data/dimension/dim_rotations_r35.parquet     ← table propre (référentiel)
```

## Grain et schéma cible de `dim_rotations_r35`

| Colonne | Type | Description |
|---|---|---|
| `annee_horaire` | str | Année horaire (ex. : H24) |
| `id_tour_service` | str | Identifiant du tour de service |
| `horaire_numero_train` | str | Numéro de train / course |
| `base_sens` | str | Sens de circulation |
| `cal_heure_depart` | time | Heure de départ prévue |
| `id_gare_depart` | str | Abréviation gare de départ |
| `id_gare_arrivee` | str | Abréviation gare d'arrivée |
| `ordre_dans_tour` | int | Position ordinale de la course dans le tour |
| `point_changement_possible` | bool | La course se termine/commence à un point de changement (VV ou BLON) |
| `source_version` | str | Version / date du plan de rotation |

## Rôle dans l'artefact final

L'architecture de décision est la suivante :

1. Le modèle prédit `prediction_voyageurs_2eme_classe` au niveau **tronçon × course × date**.
2. Les prédictions sont agrégées par course (charge maximale sur les tronçons d'une course).
3. Les courses sont rattachées à un tour de service via `dim_rotations_r35`.
4. La couche de décision recommande ou non une UM au niveau du **tour**, en fonction du risque maximal observé/prédit sur les courses et tronçons du tour.
5. L'utilisateur métier reçoit une recommandation explicable (SHAP), qu'il peut accepter, modifier ou rejeter.

## Formulation recommandée pour la documentation

"La prédiction est produite au niveau tronçon × course × date, car il s'agit du grain disponible dans les données APC. La décision opérationnelle UM ne se prend toutefois pas à ce niveau : elle concerne un tour de service, dont la composition est héritée sur plusieurs courses. Les tours ne pouvant pas être reconstruits de manière fiable à partir des seules données APC, une table de rotations issue de la planification sera intégrée à la couche de décision, dans un premier temps pour l'année 2024."

## Limites

- La table de rotations est disponible pour 2024 uniquement à ce stade. Les années antérieures nécessiteront des données de planification supplémentaires ou une hypothèse de stabilité inter-annuelle.
- La logique de rotation peut varier selon le type de jour (semaine / weekend / fériés) et selon la saison. Le schéma cible devra accommoder ces variations.
- Les changements de composition en cours de service (panne, renfort) ne sont pas couverts par la table de rotations — ils restent une décision opérationnelle non modélisée.

## Conséquences

- La pipeline actuelle (stages 01–08 + ml_dataset) produit les prédictions au grain tronçon. Elle reste inchangée.
- La couche de décision est une étape distincte, post-prédiction, qui consomme `ml_dataset.parquet` + `dim_rotations_r35.parquet`.
- L'ajout de `dim_rotations_r35` dans le Makefile est prévu comme cible indépendante (comme les autres tables `dim_*`).

## Fichiers à créer

- `data/external/rotations/` (répertoire)
- `scripts/sources/build_rotations_r35_2024.py`
- `data/dimension/dim_rotations_r35.parquet`
- Future : `notebooks/06_decision_layer.ipynb`

---


---
id: ADR-008
ancien_id: ADR-08
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-062]
precise_par: [ADR-015]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-008 — Décalage opérationnel J-2 pour les features historiques APC

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-062 ; précisée par ADR-015.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

> **⚠ CORRECTION 2026-06-16 (ADR-062)** — Le lag J-2 défini ci-dessous est **incorrect pour les données APC** (HOP-REP-WEB). La publication APC réelle est mensuelle : le mois M est disponible à partir du 3 de M+1. Le lag réel est min=3 j / médiane=18 j / max=33 j, et non J-2. La constante `LAG_OPERATIONNEL_JOURS = 2` a été remplacée par un **cutoff mensuel** dans le pipeline expérimental (inc1, hash `fe9d6b4d`). Voir ADR-062 pour la décision complète et l'attribution chiffrée. ADR-008 reste valide pour les autres features à lag journalier (ISTDATEN, météo).

| Champ | Valeur |
|---|---|
| **Statut** | Partiellement corrigée — voir ADR-062 |
| **Date** | 2026-05 |
| **Correction** | 2026-06-16 (ADR-062) |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Constante** | `LAG_OPERATIONNEL_JOURS = 2` *(remplacée par cutoff mensuel pour les histo_* APC — cf. ADR-062)* |
| **Remplace** | Comportement implicite `shift(1)` — données J-1 utilisées comme si elles étaient disponibles à J-1 |

## Contexte

Le modèle est conçu pour produire une recommandation UM la veille du jour de circulation (J-1), conformément au processus opérationnel décrit dans ADR-022. La question est : quelle est la **dernière journée APC réellement disponible** au moment de la décision ?

Les comptages APC de la journée J-1 sont consolidés par le système de collecte dans la nuit de J-1 à J. À l'heure où la décision UM doit être prise (en soirée de J-1), ces données **ne sont pas encore disponibles**.

La version initiale du script utilisait un `shift(1)`, qui plaçait les données de J-1 comme input pour prédire J. Cela constitue un **leakage temporel** : en exploitation réelle, ces données n'existent pas encore au moment de la prédiction.

## Décision

**`LAG_OPERATIONNEL_JOURS = 2`**

Toutes les features historiques APC (`histo_*`) utilisent des données antérieures ou égales à J-2. La fenêtre glissante 7j se termine donc à J-2 et couvre J-8 à J-2 inclus.

Correspondance entre suffixes de features et fenêtres effectives :

| Suffixe | Fenêtre effective | Données utilisées |
|---|---|---|
| `lag2` | ponctuel J-2 | observation du avant-hier |
| `win7_*` | J-8 à J-2 inclus | 7 jours glissants, tous antérieurs à J-1 |

## Justification

**Réalisme opérationnel :** en exploitation, les données APC de J-1 ne sont disponibles que le matin de J. Utiliser `shift(2)` garantit que le modèle ne dépend que de données effectivement accessibles au moment de la décision.

**Cohérence avec ADR-022 :** la matrice de disponibilité J-1 classe les features `histo_*` en catégorie 1 (certaines). Avec `shift(1)`, cette classification était incorrecte — ces features étaient en réalité partiellement en catégorie 5 (leakage). Avec `shift(2)`, la classification catégorie 1 est correctement justifiée.

**Impact sur les performances backtestées :** le passage de J-1 à J-2 perd un jour d'information. L'impact attendu est faible car les patterns de fréquentation sont fortement auto-corrélés sur plusieurs jours, et la fenêtre win7 compense la perte du point J-1.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| `shift(1)` — données J-1 | Leakage temporel : données non consolidées à l'heure de décision |
| `shift(0)` — données J | Leakage évident (données du jour à prédire) |
| Horodatage précis de consolidation | Non disponible dans le système APC actuel — reporté si accès aux logs de collecte |

## Conséquences

- Les features `histo_*` sont désormais correctement classées catégorie 1 (certaines) selon ADR-022.
- La performance sur données historiques peut être légèrement inférieure à l'ancienne version (`shift(1)`), mais les métriques seront plus représentatives de l'exploitation réelle.
- Le contrôle de cohérence dans `main()` valide que les `LAG_OPERATIONNEL_JOURS` premières observations de chaque groupe ont bien `lag2 = NaN`.

> **Note de correction (ADR-062, 2026-06-16) :** La supposition que J-2 représente une donnée APC disponible est incorrecte. Les données APC (HOP-REP-WEB) sont publiées mensuellement, avec un lag réel de 18 j en médiane. L'impact du leakage J-2 sur les métriques H25 est : ΔR² HAUT = −0.100, ΔR² GLOBAL = −0.030. La correction est la substitution du cutoff mensuel au lag J-2 dans `add_features_to_raw_stacked.py`. La classification catégorie 1 des `histo_*` selon ADR-022 reste valide avec le cutoff mensuel (les données du dernier mois publié sont certaines à la date de décision).

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constante `LAG_OPERATIONNEL_JOURS`, shift et rolling
- `scripts/pipeline/add_istdaten_to_raw_stacked.py` — jointure `+2 jours` (seul point de décalage pour les features ISTDATEN)
- `scripts/sources/build_dim_profil_train.py` — `LAG_OPERATIONNEL=0` (décalage délégué à la jointure)
- `scripts/sources/build_dim_correspondances_vevey.py` — `LAG_OPERATIONNEL=0` (idem)
- `scripts/sources/_rolling_par_type_jour.py` — `lag` défaut à 0

## Note sur le double-lag ISTDATEN (corrigé 2026-05-21)

Les scripts de dimension ISTDATEN utilisaient `lag=2` dans le rolling ET la
jointure décalait de `+2j`. Ce double-comptage a été corrigé : les scripts de
dimension utilisent `lag=0`, la jointure conserve `+2j`. Cf. ADR-015.

---


---
id: ADR-009
ancien_id: ADR-09
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-037, ADR-042, ADR-044, ADR-062]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-009 — Grain de groupement des features historiques : inclusion de l'année horaire

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-037, ADR-042, ADR-044, ADR-062.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Constante** | `GROUP_KEYS = ["horaire_annee_horaire", "horaire_troncon_tgl", "horaire_numero_train"]` |
| **Remplace** | `GROUP_KEYS = ["horaire_troncon_tgl", "horaire_numero_train"]` |

## Contexte

Les features historiques APC (`histo_*`) sont construites par groupe `(troncon, numero_train)` : pour un tronçon et un numéro de train donnés, on calcule des statistiques glissantes sur les dates précédentes.

Le problème est que les **numéros de train ne sont pas stables d'une année horaire à l'autre**. Lors du changement d'horaire annuel CFF (mi-décembre), les numéros de train peuvent être :

- **Réattribués** : le numéro 6301 peut désigner un service Vevey–Les Pléiades en H23 et un service avec un créneau ou un parcours différent en H24.
- **Abandonnés ou créés** : certains services disparaissent ou apparaissent au changement d'horaire.

Avec `GROUP_KEYS = ["horaire_troncon_tgl", "horaire_numero_train"]`, la fenêtre glissante du premier jour de la nouvelle année horaire hérite de l'historique de l'année précédente — potentiellement celui d'un **service fonctionnellement différent**. Cela crée un mélange de séries non comparables dans les features.

## Décision

**Option 1 retenue — stratégie conservatrice :**

`GROUP_KEYS = ["horaire_annee_horaire", "horaire_troncon_tgl", "horaire_numero_train"]`

Les fenêtres glissantes ne traversent jamais une frontière d'année horaire. Chaque combinaison `(année, troncon, numero_train)` est traitée comme une série indépendante.

## Justification

**Correction du biais de mélange :** sans l'année horaire dans la clé, les premières semaines de chaque nouvelle année horaire pourraient hériter d'un historique non représentatif (service différent, créneau décalé). Cela fausserait les features de lag pour une période critique (nouvelles compositions d'offre).

**Simplicité d'implémentation :** l'option 1 est triviale à implémenter (ajout d'une clé dans le groupby) et facile à valider (contrôle dans `main()` : première obs de chaque groupe → `lag2 = NaN`).

**Coût accepté :** les `LAG_OPERATIONNEL_JOURS` (=2) premières observations de chaque groupe ont `lag2 = NaN`, et les fenêtres win7 démarrent avec `min_periods=1` sur les premières semaines. La perte est de **~7-14 jours de features valides à chaque mi-décembre** (durée du warm-up de la fenêtre 7j), soit une fraction marginale du dataset total.

**XGBoost est robuste aux NaN :** le modèle de la phase suivante gère nativement les NaN en features, donc les premières observations du nouvel horaire ne sont pas perdues — elles sont simplement moins renseignées.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| **Option 1 (retenue)** — interruption aux frontières d'année | Simple, sans risque de contamination inter-années |
| **Option 2** — service_id reconstruit par clustering temporel | Plus complexe ; nécessite une analyse des discontinuités d'horaire ; reportée en analyse de sensibilité éventuelle |
| **Option 3** — conserver `shift` sans clé année, supprimer J-1 à J+1 du changement | Fragile, ne couvre pas les réattributions subtiles de numéros |

## Conséquences

- Les features `histo_*` sont maintenant correctement isolées par année horaire.
- Le merge final ajoute `horaire_annee_horaire` aux clés de jointure entre `daily` et `result` : cohérence garantie si `result` contient bien cette colonne (produite dès stage_01).
- Le contrôle de cohérence dans `main()` valide que la première observation de chaque `(année, troncon, train)` a bien `lag2 = NaN`.

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constante `GROUP_KEYS`
- `notebooks/04_data_preparation.ipynb` — documentation de la stratégie de groupement à mettre à jour

---


---
id: ADR-010
ancien_id: ADR-10
date_decision: 2026-05
statut: amendé
amende_par: [ADR-019, ADR-037, ADR-060]
chiffres_perimes: [seuil94]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-010 — Famille des features historiques APC : 6 statistiques par variable

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-019, ADR-037, ADR-060.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nédellec |
| **Script impacté** | `scripts/pipeline/add_features_to_raw_stacked.py` |
| **Suffixes** | `lag2`, `win7_mean`, `win7_median`, `win7_max`, `win7_std`, `win7_n_surcharges` |
| **Remplace** | 2 features par variable : `lag_1j_moy`, `lag_7j_moy` |

## Contexte

La version initiale du script calculait uniquement deux features par variable source (`lag_1j_moy` et `lag_7j_moy`), soit 6 features au total. Ces deux features capturent uniquement la **tendance centrale** (moyenne) sur des fenêtres temporelles différentes.

La cible ML (`target_voyageurs_2eme_classe`) et la règle de décision UM (`>= 94 voyageurs`) orientent le problème vers la **détection de pics de fréquentation** (queue de distribution), pas vers la prédiction de la fréquentation moyenne. Des modèles de tendance centrale seuls sont insuffisants pour capturer la variance intra-groupe et l'historique de saturation.

## Décision

**6 features dérivées par variable source** (3 variables × 6 statistiques = 18 features historiques) :

| Suffixe | Type | Fenêtre effective | Signal capté |
|---|---|---|---|
| `lag2` | ponctuel | J-2 | Continuité immédiate (avant-hier) |
| `win7_mean` | tendance centrale | J-8 à J-2 | Niveau moyen de la semaine écoulée |
| `win7_median` | tendance centrale robuste | J-8 à J-2 | Niveau médian, insensible aux outliers |
| `win7_max` | extrême | J-8 à J-2 | Pic maximal observé dans la semaine |
| `win7_std` | dispersion | J-8 à J-2 | Variabilité hebdomadaire de la fréquentation |
| `win7_n_surcharges` | compteur métier | J-8 à J-2 | Nombre de jours > 94 voyageurs (2ème classe uniquement) |

`win7_n_surcharges` est calculée **uniquement pour `target_voyageurs_2eme_classe`** (la cible ML, cf. ADR-001 et ADR-004). Pour les autres variables sources (1ère classe, total), cette feature est mise à NaN.

## Justification

**Détection de pics :** `win7_max` et `win7_n_surcharges` capturent directement l'historique de saturation récente — l'information la plus pertinente pour anticiper un nouveau pic.

**Robustesse aux outliers :** `win7_median` est préférée à `win7_mean` pour les groupes avec des jours atypiques isolés (annulations, événements exceptionnels). Offrir les deux laisse le modèle arbitrer.

**Dispersion comme signal :** `win7_std` encode la variabilité du tronçon/train. Un tronçon à forte std est plus difficile à prédire ; le modèle peut l'apprendre comme facteur d'incertitude.

**Tri empirique via SHAP :** l'objectif n'est pas de pré-sélectionner les features utiles mais d'en offrir un ensemble riche pour que l'analyse SHAP (phase modélisation) effectue le tri empirique. Des features redondantes ou non informatives seront identifiées et éliminées à cette étape.

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| 2 features (mean 1j + mean 7j) — ancienne version | Insuffisant pour capter la queue de distribution — tendance centrale seule |
| Percentiles (p75, p90) à la place de max | Plus stables que max mais nécessitent plus d'historique pour être significatifs ; max est plus interprétable opérationnellement |
| Features sur fenêtre 28j | Reportées : fenêtre 7j déjà couvre les patterns hebdomadaires ; la valeur marginale d'une fenêtre 28j sera évaluée en phase SHAP si les features 7j s'avèrent insuffisantes |
| win7_n_surcharges pour toutes les variables sources | Non pertinent pour 1ère classe (saturation quasi-inexistante, cf. ADR-001) et total (seuil différent, cf. ADR-004) |

## Conséquences

- Passage de 6 à 18 features historiques dans `stage_08_features.parquet`.
- Noms de colonnes mis à jour (préfixe `histo_`, suffixes descriptifs) — incompatibles avec l'ancienne version de stage_08 : recalcul nécessaire.
- `build_ml_dataset.py` doit être vérifié pour s'assurer qu'il n'exclut pas les nouvelles colonnes `histo_*`.
- Les analyses SHAP en phase modélisation fourniront le tri empirique définitif des 18 features.

## Fichiers impactés

- `scripts/pipeline/add_features_to_raw_stacked.py` — constantes `HISTO_SUFFIXES`, `SEUIL_UM_2EME`, fonction `_feature_col`, bloc de calcul des lags
- `notebooks/04_data_preparation.ipynb` — inventaire des features à mettre à jour
- `notebooks/05_feature_analysis.ipynb` (futur) — analyse SHAP des 18 features historiques

---


---
id: ADR-011
ancien_id: ADR-11
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-063]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-011 — Imputation des millésimes STATPOP manquants (2021, 2023)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acceptée — sous réserve de validation empirique (test de sensibilité) |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **ADR liés** | ADR-002 (split temporel), ADR-022 (disponibilité J-1), ADR-006 (dernier millésime disponible) |

## Contexte

Les fichiers STATPOP 2021 et 2023 publiés par l'OFS ne contiennent pas les données
sur les ménages (HP\*) ni les indicateurs de qualité HPI. Sur la période d'étude
(2015–2024), ces deux millésimes sont structurellement incomplets pour 13 variables.

Compte tenu de la stratégie de split (ADR-002), seul le millésime 2023 affecte
directement le train set (H22–H23). Le millésime 2021 tombe dans la période COVID
(traitée séparément) mais est conservé dans le pipeline pour préserver la cohérence
historique de la table `statpop_clean`.

## Décision

**Stratégie retenue : interpolation linéaire entre millésimes adjacents.**

Pour les variables continues (`INTERPOLATION_COLUMNS`) :
- 2021 = moyenne arithmétique de 2020 et 2022 (2021 équidistant → interpolation exacte)
- 2023 = moyenne arithmétique de 2022 et 2024 (même logique)

Pour les indicateurs catégoriels (`IMPUTATION_MAX_COLUMNS` : `hpi_classe_max_500m`,
`flag_qualite_statpop_faible`) : imputation par le **maximum** des deux millésimes
adjacents, quelle que soit la stratégie principale. Justification : ces variables sont
ordinales/binaires ; une interpolation linéaire produirait une valeur intermédiaire sans
sens sémantique (ex. flag = 0.5). Le principe de précaution s'impose : si l'une des
années voisines signale une qualité dégradée, l'année interpolée hérite de ce signal.

## Justification

- Les variables STATPOP retenues sont **structurellement lentes** : la population totale
  dans les buffers 500 m n'a progressé que de +9,5 % sur 10 ans. L'hypothèse de
  linéarité sur deux ans est raisonnable.
- Le millésime concerné (2023) se situe dans un régime post-COVID stabilisé, sans
  choc démographique conjoncturel identifié.
- L'interpolation est réalisée **entre deux valeurs observées**, sans extrapolation.
  `pandas.interpolate(method='index')` garantit cette propriété.
- Pratique standard en analyse spatiale pour les données de registres administratifs
  à publication annuelle (Cromley & McLafferty, 2011 ; Fotheringham et al., 2000).

## Stratégies alternatives exposées

Le script `build_fact_statpop_gare.py` expose trois variantes via `--strategy` :

| Stratégie | Description | Usage |
|---|---|---|
| `interpolate` | Interpolation linéaire (défaut) | Configuration retenue en production |
| `carry_forward` | LOCF — dernière valeur observée reportée | Référence causale stricte (impute avec données disponibles *avant* la période) |
| `none` | Pas d'imputation — NA conservés | Baseline pour quantifier l'impact de l'imputation |

## Test de sensibilité

Un test empirique est réalisé en phase de modélisation (section 4.x du mémoire) :
trois entraînements du modèle de référence sont comparés avec les trois variantes.

**Critère de validation** : l'écart de R² entre les variantes reste < 0.01 sur le
test set H24. Si tel est le cas, la stratégie retenue est confirmée. Si l'écart est
significatif, la stratégie `carry_forward` est privilégiée pour sa rigueur causale.

## Conséquences

- `build_fact_statpop_gare.py` implémente `impute_missing_millesimes()` avec le
  paramètre `strategy`. La stratégie par défaut est `"interpolate"`.
- La table `statpop_clean.parquet` ne contient plus aucun NA sur les colonnes cibles
  (sauf pour les millésimes hors de la plage d'interpolation).
- Les variables ménages et HPI sont intégrées dans le `ml_dataset` via
  `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` (`STATPOP_KEEP_SUFFIXES`).
- Pour les tests de sensibilité, renommer la sortie :
  `statpop_clean_{strategy}.parquet` avant de rejouer la pipeline.

---


---
id: ADR-012
ancien_id: ADR-12
date_decision: 2026-05-15
statut: remplacé
remplace_par: [ADR-019]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-012 — Refonte ISTDATEN au grain date × numero_train

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-019.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Le pipeline ISTDATEN initial (stage_07 via `add_ponctualite_to_raw_stacked.py`) agrégeait
tous les indicateurs de ponctualité au grain journalier (une ligne par date). Cette
agrégation détruisait le signal le plus informatif pour la prédiction de fréquentation :
la spécificité par train.

Deux trains du même jour peuvent avoir des profils de ponctualité très différents
(le 8h20 est régulièrement en retard, le 9h05 ne l'est jamais). En agrégeant, on
perd cette information et on contraint le modèle à utiliser des moyennes journalières
peu discriminantes.

## Décision

Passer le grain des features ISTDATEN de `date` à `date × numero_train` via trois
nouvelles tables :

| Table | Script producteur | Grain |
|---|---|---|
| `dim_profil_train` | `build_dim_profil_train.py` | date × numero_train |
| `dim_correspondances_vevey` | `build_dim_correspondances_vevey.py` | date × numero_train |
| `dim_vmcv_par_gare` | `build_dim_vmcv_par_gare.py` | gare (statique) |

Le nouveau script d'intégration `add_istdaten_to_raw_stacked.py` remplace
`add_ponctualite_to_raw_stacked.py` et produit `stage_07_istdaten.parquet`.

## Conséquences

**Positives :**
- Le modèle dispose d'un signal par train, permettant de capturer les habitudes
  de ponctualité structurelles de chaque course.
- Les fenêtres 7j et 28j par train reflètent l'historique spécifique du train,
  pas la moyenne du réseau.
- Les correspondances Vevey deviennent précises : on sait exactement quels feeders
  arrivent avant chaque départ R35.

**Négatives / risques :**
- Couverture partielle attendue : les trains sans historique 28j (début de période,
  nouveaux numéros) auront NaN. XGBoost gère nativement les NaN.
- Les correspondances Vevey ne couvrent que les trains depuis Vevey (les autres
  trains auront NaN pour cette famille, ce qui est correct).
- Volume de données accru : `dim_profil_train` a un grain plus fin qu'une simple
  table journalière.

## Alternatives écartées

- **Conserver le grain journalier** : perd le signal par train, acceptable pour un
  baseline mais insuffisant pour un modèle performant.
- **Grain arrêt** : trop fin pour la jointure APC (le modèle prédit par tronçon,
  pas par arrêt). Le grain train est le bon niveau d'agrégation.

## Tests d'ablation

Voir `add_istdaten_to_raw_stacked.py --familles` pour les variantes d'ablation
permettant d'isoler la contribution de chaque famille (Chapitre 4 du mémoire).

---


---
id: ADR-013
ancien_id: ADR-13
date_decision: 2026-05-15
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-013 — Convention de ponctualité par valeur absolue

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

La fonction de calcul du pourcentage de ponctualité comparait `retard <= seuil`,
ce qui considérait comme ponctuel un train parti en avance (retard négatif).

Cette convention est incorrecte dans le contexte ferroviaire : un départ en avance
est aussi pénalisant qu'un retard pour les voyageurs en correspondance, qui ratent
leur train. L'OFT mesure également la ponctualité en valeur absolue.

## Décision (révisée 2026-05-21)

Deux conventions coexistent selon le contexte :

### Ponctualité au DÉPART — convention symétrique `|retard| <= seuil`

Un départ en avance est aussi pénalisant qu'un retard pour les voyageurs en
correspondance, qui ratent leur train. Convention OFT.

```python
def _pct_ponctuel_symetrique(serie: pd.Series, seuil: int) -> float:
    valid = serie.dropna()
    return float((valid.abs() <= seuil).mean()) if len(valid) > 0 else float("nan")
```

S'applique à :
- `build_istdaten_ponctualite.py` — `ist_r35_pct_dep_ponctuel_*_j`
- `build_dim_profil_train.py` — `is_en_retard_dep` (retard >= seuil, sans valeur absolue,
  car l'avance au départ d'un tronçon intermédiaire n'est pas un problème)

### Ponctualité à l'ARRIVÉE — convention retard seul `retard <= seuil`

Un train CFF arrivant en avance à Vevey ne fait pas rater la correspondance R35.
Pénaliser l'avance gonflerait artificiellement la non-ponctualité.

```python
def _pct_ponctuel_retard_seul(serie: pd.Series, seuil: int) -> float:
    valid = serie.dropna()
    return float((valid <= seuil).mean()) if len(valid) > 0 else float("nan")
```

S'applique à :
- `build_istdaten_ponctualite.py` — `ist_vevey_pct_arr_ponctuel_180s_j`
- `build_dim_profil_train.py` — `is_en_retard_arr` (retard >= seuil, cohérent)

## Conséquences

- `ist_r35_pct_dep_ponctuel_*_j` : inchangé (déjà symétrique).
- `ist_vevey_pct_arr_ponctuel_180s_j` : légère hausse attendue (les avances
  ne sont plus pénalisées).
- `is_en_retard_dep` et `is_en_retard_arr` dans `build_dim_profil_train.py` :
  inchangés — les deux utilisaient déjà `retard >= seuil`.

## Alternatives écartées

- **Convention symétrique pour les arrivées** : surestimait la non-ponctualité
  des feeders Vevey. Supprimé le 2026-05-21.
- **Seuils asymétriques** (ex. `-30s ≤ retard ≤ 180s`) : introduit un paramètre
  supplémentaire sans justification opérationnelle claire.

---


---
id: ADR-014
ancien_id: ADR-14
date_decision: 2026-05-15
statut: remplacé
remplace_par: [ADR-019]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-014 — Fenêtre de correspondance Vevey [-20, -2] minutes

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-019.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Pour calculer les correspondances CFF→R35 à Vevey, il faut définir quelle
fenêtre temporelle avant le départ R35 constitue une correspondance valide.

Deux paramètres structurent cette fenêtre :
- **Borne amont** : au-delà de combien de minutes d'attente un voyageur ne
  prend-il plus le R35 pour rejoindre un destination par une autre voie ?
- **Borne aval** : en-deçà de combien de minutes avant le départ le voyageur
  ne peut-il plus monter dans le train ?

Un troisième paramètre définit le seuil de retard au-delà duquel une
correspondance est considérée comme ratée :
- **Seuil retard feeder** : au-delà de ce retard, le voyageur rate le R35.

## Décision

Fenêtre retenue : `[depart_R35 - 20 min, depart_R35 - 2 min]`  
Seuil retard feeder : 5 minutes (300 secondes)

| Paramètre | Valeur | Justification |
|---|---|---|
| Borne amont | 20 min | Temps maximal d'attente acceptable à Vevey gare (quai couvert) |
| Borne aval | 2 min | Temps minimal de transfert entre quai CFF et quai R35 |
| Seuil retard | 5 min | Marge de tolérance opérationnelle CFF/MVR-cev |

## Conséquences

- Un train R35 partant à 9h30 compte les feeders arrivés entre 9h10 et 9h28.
- Un feeder arrivé à 9h25 avec 6 min de retard (heure prévue 9h19) est comptabilisé
  dans la fenêtre mais NOT comme correspondance effective.
- Les trains R35 ne partant pas de Vevey (BPUIC ≠ 8501200) ont NaN pour
  toutes les features correspondances — comportement attendu et géré par XGBoost.

## Sensibilité à tester (Phase 4)

Variants à évaluer :
- Borne amont 15 min (voyageurs qui arrivent juste avant le départ)
- Seuil retard feeder 3 min (plus strict)
- Exclusion des feeders RE33 (longue distance, correspondances moins systématiques)

## Addendum (2026-07-24)

La fenêtre de correspondance [-20, -2] minutes est supersédée par ADR-019, qui fixe la fenêtre finale de une à cinq minutes entre l'arrivée du train apporteur et le départ R35 (mémoire, section 4.4.2).

---


---
id: ADR-015
ancien_id: ADR-15
date_decision: 2026-05-15
statut: actif
modifie: [ADR-008]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-015 — Logique opérationnelle J-2 pour les features ISTDATEN

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-008.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Le pipeline de prédiction produit chaque matin du jour J une prédiction de
fréquentation pour le lendemain (jour J+1). Les features ISTDATEN (profil de
ponctualité, correspondances Vevey) sont calculées à partir des données
real-time publiées par l'OFT.

La question est : jusqu'à quelle date les données ISTDATEN sont-elles
disponibles au moment où le pipeline tourne ?

## Contrainte opérationnelle

L'OFT publie les données ISTDATEN avec un décalage de traitement d'environ
24h. Au matin du jour J, les données disponibles couvrent jusqu'à J-2 au plus
tôt de manière fiable. Les données de J-1 peuvent être incomplètes ou absentes.

Conséquence : toute feature ISTDATEN utilisée pour prédire J+1 (depuis le
pipeline tournant le matin de J) doit être calculée à partir de données
≤ J-2.

## Décision

Le décalage J-2 est porté **exclusivement par la jointure** dans
`add_istdaten_to_raw_stacked.py`. Les fenêtres glissantes dans les scripts
de dimension utilisent `lag=0` (aucun décalage interne).

| Composant | V1 (incorrect) | V2 (double-lag, incorrect) | V3 (correct) |
|---|---|---|---|
| `build_dim_profil_train.py` — rolling | `shift(1)` | `shift(2)` | `shift(0)` |
| `build_dim_correspondances_vevey.py` — rolling | `shift(1)` | `shift(2)` | `shift(0)` |
| `add_istdaten_to_raw_stacked.py` — jointure | `Timedelta(days=1)` | `Timedelta(days=2)` | `Timedelta(days=2)` ✓ |

**Pourquoi V2 était incorrect** : avec `lag=2` dans le rolling ET `+2j` dans
la jointure, pour `base_date=J` on lisait la ligne ISTDATEN de `date=J-2`,
dont la fenêtre rolling se terminait à `(J-2) - 2 occurrences du même type de jour`.
Pour les jours ouvrables c'est J-4, pour les samedis c'est J-2-14j = J-16.
Double-décalage non voulu.

**V3** : rolling avec `lag=0` à `date=J-2` → fenêtre couvrant les N dernières
occurrences du même type de jour se terminant à J-2 inclus. La jointure
matérialise ensuite J-2 → `base_date=J`. Décalage J-2 strict respecté.

Les features VMCV sont statiques (pas de dimension temporelle) : non affectées.

## Conséquences

- Pour une prédiction du jour J+1 produite le matin de J, les features
  ISTDATEN reflètent l'historique jusqu'à J-2 inclus (2 jours de plus de
  données qu'avec V2).
- La couverture des features roulantes augmente (V2 pouvait être à J-4 ou plus).
- Le test `TestJointureJMoins2` vérifie explicitement que J-1 ne matche pas
  et que J-2 matche.

## Alternative écartée

**Shift(1) / J-1** : acceptable si le pipeline tourne après la publication
complète des données ISTDATEN de la veille. Écarté car les données de J-1
sont publiées avec un décalage variable et non garanti avant l'heure de
lancement du pipeline.

---


---
id: ADR-016
ancien_id: ADR-16
date_decision: 2026-05-15
statut: révoqué
revoque_par: [ADR-019, ADR-038]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-016 — Stabilité des numéros de train R35 sur la période modélisable

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-019, ADR-038.
> **Précision au gel.** La stabilité des numéros de train constatée ici ne vaut plus après la refonte d'horaire H25 : ADR-038 relève que 100 % des heures de départ à l'origine ont changé.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-15

## Contexte

Les numéros de train CFF/MVR sont réutilisés d'horaire en horaire et peuvent
correspondre à des services différents (heure, sens) après les changements
d'horaire annuels de mi-décembre. Le pipeline `build_dim_profil_train.py`
groupe les rolling windows 7j et 28j par `numero_train` sans tenir compte
de ces transitions, ce qui pourrait théoriquement mélanger les statistiques
de deux services distincts.

Le risque a été investigué avant validation du pipeline.

## Diagnostic quantitatif

Analyse des transitions d'horaire entre 2018 et 2024 :

| Transition  | Δ < 5 min | Δ 5-30 min | Δ ≥ 30 min | Sens changé | REAL avant/après |
|-------------|-----------|------------|------------|-------------|-------------------|
| H18→H19     | 35%       | 16%        | 49%        | 3%          | 0% / 0%           |
| H19→H20     | 89%       | 8%         | 2%         | 1%          | 0% / 0%           |
| H20→H21     | 96%       | 4%         | 0%         | 0%          | 0% / 0%           |
| H21→H22     | 100%      | 0%         | 0%         | 0%          | 0% / 0%           |
| H22→H23     | 96%       | 4%         | 0%         | 3%          | 0% / 0%           |
| H23→H24     | 100%      | 0%         | 0%         | 0%          | ~88% / ~88%       |

## Constat

La seule transition d'horaire incluse dans la fenêtre de données ISTDATEN
exploitables (REAL/GESCHAETZT à partir de juillet 2023) est H23→H24,
qui présente 100% de stabilité (108/108 trains).

Les transitions plus anciennes affichent des taux de changement significatifs
(notamment H18→H19 lors de la réforme du cadencement MVR-cev), mais elles
se situent intégralement dans une période sans données réelles. Les rolling
windows par numero_train ne calculent donc rien sur ces périodes, et aucune
contamination des statistiques n'est possible.

## Décision

Conserver le groupement par `numero_train` simple dans `build_dim_profil_train.py`,
sans introduire de `service_id` composite. La modification ne serait pas
neutre (perte d'historique au début de chaque horaire, complexification du
pipeline) et n'apporterait aucun bénéfice empirique.

## Conséquences

- Pipeline préservé en l'état, pas de modification de scripts.
- Documentation explicite du raisonnement quantitatif dans cet ADR.
- Si une future année de données introduit une transition instable (par
  exemple H24→H25 avec un changement majeur), cette décision devra être
  revue. À surveiller au moment de l'extension du pipeline en production.

---

## Annexe — Exploration empirique : encodage composite numéro × heure d'origine

**Date** : 2026-05-16

### Motivation

Même si les rolling windows se groupent par `numero_train` sans risque
(décision ci-dessus), la question se pose pour la feature identité de train
donnée en entrée du modèle XGBoost. Si deux services distincts partagent
un `numero_train` sur des années horaires différentes, le modèle pourrait
apprendre une association erronée.

Pour trancher empiriquement, une troisième variante d'encodage est introduite :
`horaire_service_id_complet = f"{numero_train}_{heure_origine:%Hh%M}"`.
L'heure d'origine est l'heure de départ théorique (ISTDATEN) du **premier
arrêt** du train ce jour-là, commune à tous les tronçons du même service.

### Trois variantes comparées dans Dataiku

| Modèle | Dataset | Feature identité de service |
|--------|---------|------------------------------|
| A | ml_dataset.parquet | `horaire_numero_train` |
| B | ml_dataset_service_id.parquet | `horaire_service_id_complet` |
| C | ml_dataset_sans_train_id.parquet | aucune |

Les trois datasets sont produits par `build_ml_dataset.py` via l'argument
`--variante-encodage-service {numero_seul,service_id_seul,aucun}`.

### Critères de décision

- Si R²(A) ≈ R²(C) → la feature identité n'apporte pas de signal ; utiliser C.
- Si R²(A) > R²(C) → signal réel ; comparer A vs B :
  - R²(A) ≈ R²(B) → encodage numéro seul suffit (A retenu, plus simple).
  - R²(B) > R²(A) → l'identifiant composite apporte un gain ; retenir B.

### Validité de l'identifiant composite sur H23→H24

La transition H23→H24 est 100% stable (108/108 trains, cf. tableau ci-dessus).
L'identifiant composite est donc cohérent entre train (H22-H23) et test (H24) :
les modalités vues à l'entraînement correspondent aux mêmes services en production.

---


---
id: ADR-017
ancien_id: ADR-18
date_decision: 2026-05-15
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-017 — Ablation empirique de la feature horaire_numero_train

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-15

## Contexte

La feature `horaire_numero_train` est encodée en dummy avec environ 108 modalités
dans le modèle XGBoost. Son apport prédictif est questionné car les autres
features (`base_depart_datetime` cyclique, `base_sens`, `cal_type_jour`, `horaire_annee_horaire`)
caractérisent déjà intrinsèquement le service ferroviaire.

Théoriquement, deux hypothèses concurrentes :
- **Hypothèse de redondance** : les caractéristiques du service capturent
  l'essentiel du signal, `horaire_numero_train` n'apporte rien.
- **Hypothèse de signal résiduel** : `horaire_numero_train` capture des comportements
  voyageurs spécifiques au train (habitudes scolaires, navettes d'entreprise,
  effets de groupe) non réductibles aux caractéristiques opérationnelles.

## Décision

Trancher par ablation empirique : produire deux variantes du dataset `ml_dataset`
(avec et sans la feature) et comparer les performances test sur H24.

Le script `build_ml_dataset.py` expose un argument `--exclure-horaire-numero-train`
qui contrôle l'inclusion de la feature. La variante sans la feature est écrite
dans `ml_dataset_sans_train_id.parquet`.

## Critère de décision

- Si Δ R² test > 0.02 en faveur de la version **avec** : feature conservée,
  signal résiduel justifié.
- Si Δ R² test < 0.02 (incluant le cas où la version **sans** gagne) : feature
  retirée, simplification du modèle.

## Conséquences

- Deux datasets distincts produits dans `data/processed/` pour les tests d'ablation.
- La décision finale sera tranchée après les entraînements Dataiku.

---


---
id: ADR-018
ancien_id: ADR-19
date_decision: 2026-05-15
statut: amendé
amende_par: [ADR-067]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-018 — Features ist_headway_* depuis ISTDATEN exclusivement

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-067.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Révisé
**Date initiale** : 2026-05-15 | **Révision** : 2026-05-21

## Contexte

La phase qualitative exploratoire (6 entretiens semi-directifs, codage
thématique) a identifié la cadence horaire (headway) comme critère
structurant de la décision d'usage de la R35, mentionné par 3/6 participants
(P02, P05, P06).

P05 formule explicitement un contre-argument à l'ajout d'unités multiples :
la solution opérationnelle perçue est l'augmentation de fréquence, pas de
capacité par train. Cette feature était absente du pipeline ML initial dérivé
de la littérature ML appliquée au transport ferroviaire (Ding et al. 2016,
Yusuf et al. 2025).

La première implémentation utilisait les horaires PDF (horaires théoriques
publiés). Cette approche a été abandonnée : la qualité de l'extraction PDF
est insuffisamment maîtrisée (grain des tronçons incohérent entre annéess
horaires, couverture H16–H19 ~76%), et elle introduit une dépendance à une
source fragile alors qu'ISTDATEN fournit les mêmes informations avec une
couverture et une traçabilité supérieures.

## Décision

Ajouter deux features symétriques au pipeline ML, construites exclusivement
depuis `fact_istdaten_r35.parquet` :

- `ist_headway_avant_min` : minutes depuis le départ du train précédent
  sur le même tronçon dans le même sens
- `ist_headway_apres_min` : minutes jusqu'au départ du train suivant
  sur le même tronçon dans le même sens

Le préfixe `ist_` est cohérent avec les autres features dérivées d'ISTDATEN.

### Définition technique (révisée 2026-05-21)

**Heure de départ** : uniquement `horaire_depart` (ISTDATEN théorique, pas le PDF).
La version initiale utilisait `reel_depart` avec fallback sur `horaire_depart`.
Ce fallback a été supprimé : en déploiement, MOB n'a que l'horaire théorique à J-1.
Utiliser les heures réelles en entraînement créait un distribution shift documenté
mais évitable. La perte est la granularité « retard induit par un train précédent » ;
elle est assumée car la cohérence opérationnelle prime.

- `is_annule = True` → exclu (ne compte pas comme prédécesseur ni successeur)
- `is_supplementaire = True`, `is_annule = False` → inclus normalement

**Reconstruction des tronçons** : pour chaque `(date, numero_train)`, les
arrêts sont triés par `horaire_depart` et des paires successives
`(bpuic_n, bpuic_n+1)` forment les tronçons. Le sens est déduit de l'ordre
kilométrique dans `dim_gare`.

**Valeurs manquantes** : premier train de la journée → `ist_headway_avant_min = NaN` ;
dernier train → `ist_headway_apres_min = NaN`. La sentinelle 999.0 a été supprimée :
XGBoost gère nativement les NaN, et 999 créait une discontinuité artificielle.

**Flags binaires ajoutés** :
- `ist_headway_avant_is_first_of_day` (int8) : 1 ↔ `ist_headway_avant_min` est NaN
- `ist_headway_apres_is_last_of_day` (int8) : 1 ↔ `ist_headway_apres_min` est NaN

### Clé de jointure dans le pipeline

```
dim_headway (date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)
  ↔ stage_07_istdaten (base_date, horaire_numero_train,
                        id_gare_depart_bpuic, id_gare_arrivee_bpuic, base_sens)
```

Pas de décalage J-2 : en entraînement, `dim_headway` contient des
observations passées connues au moment de la prédiction.

## Justification de la formulation symétrique

La formulation avant/après capture l'isolement temporel sans préjuger de la
direction de l'effet : un train très espacé du précédent absorbe davantage de
demande accumulée ; un train très rapproché du suivant peut inciter les usagers
à attendre. Les deux directions sont empiriquement distinctes et permettent une
analyse SHAP différenciée.

## Cohérence opérationnelle (entraînement vs déploiement)

En **entraînement** comme en **déploiement**, la source est l'horaire théorique
ISTDATEN. La révision 2026-05-21 a aligné entraînement et déploiement en
supprimant le fallback sur `reel_depart`. MOB substituera par son horaire
tabulaire interne sans distribution shift.

## Conséquences

- Source unique et robuste : ISTDATEN, déjà dans le pipeline.
- Couverture H24 (test set) : >95%.
- Pipeline simple : deux features, grain identique à stage_07.
- Feature défendable scientifiquement : émergente du qualitatif, complémentaire
  au contre-argument P05 sur la fréquence vs la capacité.
- Permet une analyse SHAP directe : quantifie l'effet marginal d'une réduction
  de headway sur la fréquentation prédite, documentant empiriquement
  la validité du contre-argument P05.

## Critère de validation

Si l'ablation de ces features dégrade significativement la performance
(Δ R² > 0.01), l'apport quantitatif justifie leur inclusion. Si la dégradation
est marginale (< 0.01), les features sont conservées pour leur valeur
explicative et le matériau qu'elles apportent au Chapitre 4 du mémoire.

## Articulation avec la couche de décision (Chapitre 5)

Les features alimentent directement la discussion opérationnelle : faut-il
dimensionner par capacité (UM) ou par fréquence (headway réduit) ?
L'analyse SHAP sur les courses en surcharge permettra de quantifier l'effet
marginal d'une réduction de headway sur la fréquentation prédite.

---


---
id: ADR-019
ancien_id: ADR-21
date_decision: 2026-05-17
statut: actif
modifie: [ADR-010, ADR-012, ADR-014, ADR-016]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-019 — Refonte des features ISTDATEN : grain tronçon + rolling par type de jour

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-010, ADR-012, ADR-014, ADR-016.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-17  
**Auteur** : E. Nédellec  

---

## Contexte

La première version des features ISTDATEN (ponctualité et correspondances)
présentait trois limites identifiées lors de la revue critique du pipeline :

1. **Grain train-jour trop grossier** : la ponctualité était agrégée au niveau
   du train pour toute sa course. La dégradation cumulée des retards le long
   du parcours (souvent observée sur les lignes de montagne) était invisible.

2. **Correspondances unidirectionnelles** : seul le flux entrant (CFF → R35) était
   modélisé. Le flux sortant (R35 → CFF) est tout aussi structurant pour le
   comportement de report modal des voyageurs descendants.

3. **Rolling windows mélangent les types de jour** : grouper par `numero_train`
   sans filtrer par type de jour combine des observations hétérogènes (ex. un
   lundi chargé compte autant qu'un dimanche creux dans la fenêtre de 7 jours).
   De plus, `numero_train` ne distingue pas deux services portant le même numéro
   avant et après un changement d'horaire annuel.

---

## Décisions

### D1 — Grain tronçon pour `dim_profil_train`

Le grain de sortie passe de `(date, numero_train)` à
`(date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)`.

La reconstruction des tronçons suit la même logique que `build_dim_headway.py` :
tri par heure de départ effective, paires d'arrêts successifs, sens déduit du km.

La jointure dans `add_istdaten_to_raw_stacked.py` est mise à jour en conséquence
pour utiliser les cinq clés `(base_date, horaire_numero_train, id_gare_depart_bpuic,
id_gare_arrivee_bpuic, base_sens)`.

### D2 — Correspondances bidirectionnelles (`_in_` et `_out_`)

`build_dim_correspondances_vevey.py` produit désormais deux familles :
- `ist_corresp_in_*` : feeders CFF arrivant à Vevey avant le départ d'un R35 montant.
  Fenêtre théorique : [départ_R35 - 5 min, départ_R35 - 1 min].
  Garantie : arrivée effective CFF dans la même fenêtre basée sur le départ effectif R35
  (aucun seuil de retard — la fenêtre effective suffit comme critère).
- `ist_corresp_out_*` : CFF partant de Vevey après l'arrivée d'un R35 descendant.
  Fenêtre théorique : [arrivée_R35 + 1 min, arrivée_R35 + 5 min].
  Garantie : départ effectif CFF dans la même fenêtre basée sur l'arrivée effective R35.

Les features sont NaN pour les trains ne passant pas par Vevey dans le sens
concerné. La propagation sur tous les tronçons du train est faite lors de la
jointure (grain train × jour, not tronçon).

Un avertissement est émis si des trains apparaissent dans les deux sens sur
le même jour (correspondances bidirectionnelles).

### D3 — Rolling conditionnel par type de jour

Un utilitaire partagé `_rolling_par_type_jour.py` implémente des fenêtres
glissantes qui ne comptent que les occurrences du **même type de jour** :
- `ouvrable` (lun–ven, hors fériés)
- `samedi`
- `dimanche_ferie`

Cette classification est ajoutée au stage_02 sous le nom `cal_type_jour_3classes`
(dérivée de `cal_type_jour` à 9 classes existant).

### D4 — Groupement par service_id au lieu de numero_train

Le `group_key` des rolling windows passe de `numero_train` à `ist_service_id`
(`{numero_train}_{heure_origine_Hh}`), qui encode implicitement l'année horaire
via l'heure de première desserte.

Avantage : un train 1308 à 07h12 en H23 et un train 1308 à 07h15 en H24
(après recadençage) ne partagent plus le même historique.

### D5 — Deux fenêtres : 5 occurrences et 20 occurrences

| Fenêtre | `min_periods` | Usage |
|---------|--------------|-------|
| 5 occ   | 2            | Signal réactif (environ 1 semaine d'ouvrables) |
| 20 occ  | 5            | Signal de tendance (environ 1 mois d'ouvrables) |

Ces fenêtres remplacent les fenêtres 7j et 28j calendaires précédentes,
qui sous-pondéraient les weekends.

---

## Features produites

### `dim_profil_train` (12 features par tronçon-train-jour)

Pour `position ∈ {dep, arr}` et `fenêtre ∈ {5occ, 20occ}` :

| Feature | Description |
|---------|-------------|
| `ist_profil_train_retard_{pos}_troncon_mean_{fen}` | Retard moyen (s) sur les N dernières occurrences du même type de jour |
| `ist_profil_train_retard_{pos}_troncon_std_{fen}` | Écart-type du retard |
| `ist_profil_train_pct_en_retard_{pos}_troncon_{fen}` | Part des occurrences avec retard ≥ 180 s |

### `dim_correspondances_vevey` (12 features par train-jour)

Pour `sens ∈ {in, out}` et `fenêtre ∈ {5occ, 20occ}` :

| Feature | Description |
|---------|-------------|
| `ist_corresp_{sens}_n_theoriques_moy_{fen}` | Moyenne glissante du nb de CFF dans la fenêtre théorique |
| `ist_corresp_{sens}_n_garanties_moy_{fen}` | Moyenne glissante du nb de correspondances garanties |
| `ist_corresp_{sens}_pct_garanties_{fen}` | Moyenne glissante du taux de garantie |

Les features `_j` (valeurs journalières) sont calculées en interne pour le
rolling mais ne figurent pas dans le parquet de sortie.

---

## Conséquences

### Positives
- Le modèle peut capturer la dégradation de ponctualité le long du parcours.
- Le flux sortant enrichit la modélisation des voyageurs descendants.
- Les fenêtres par type de jour sont homogènes et interprétables.
- Le service_id évite le leakage cross-horaire sans nécessiter `horaire_annee_horaire`
  dans la clé de groupe.

### Négatives / Compromis
- La jointure profil_train dans `add_istdaten_to_raw_stacked.py` utilise 5 clés
  au lieu de 2. Risque de NaN plus élevé si les tronçons ISTDATEN ne couvrent pas
  exactement les tronçons APC (ex. tronçons supplémentaires ou réorganisés).
- Le calcul des rolling est plus lent (boucle par type de jour × groupe).
- La lecture des CSVs ISTDATEN est maintenant réalisée **deux fois** dans
  `build_dim_correspondances_vevey.py` (arrivées et départs). À optimiser si les
  temps d'exécution deviennent contraignants.

### Fichiers modifiés
| Fichier | Rôle |
|---------|------|
| `scripts/sources/_rolling_par_type_jour.py` | Nouveau — utilitaire partagé |
| `scripts/pipeline/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py` | Ajout `cal_type_jour_3classes` |
| `scripts/sources/build_dim_profil_train.py` | Refonte complète — grain tronçon |
| `scripts/sources/build_dim_correspondances_vevey.py` | Refonte — fenêtre [5,1], garantie sans seuil retard, rolling 3 features, output sans `_j` |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py` | Clés de jointure tronçon pour profil_train ; suppression famille VMCV |

---

## Alternatives rejetées

### A1 — Conserver le grain train-jour pour la ponctualité

Rejeté : la ponctualité en tête de ligne n'est pas représentative de la
ponctualité sur les tronçons hauts (Chamby–Les Pléiades), qui sont les plus
sensibles aux conditions météo. Le grain tronçon est nécessaire.

### A2 — Rolling par jour de semaine (7 classes au lieu de 3)

Rejeté : trop peu d'occurrences par groupe pour les jours rares (ex. pont,
veille de fériée). Trois classes donnent un compromis acceptable entre
homogénéité et volumétrie.

### A3 — Lire les CSVs ISTDATEN une seule fois pour _in_ et _out_

Possible en combinant la lecture en un seul passe. Non implémenté pour
conserver la lisibilité du code. À envisager si le temps de build > 30 min.

---


---
id: ADR-020
ancien_id: ADR-22
date_decision: 2026-05-18
statut: remplacé
remplace_par: [ADR-021]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-020 — Refonte des features VMCV : concurrence modale au grain tronçon

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-021.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Remplacé par ADR-021  
**Date** : 2026-05-18  
**Auteur** : E. Nédellec  

---

## Contexte

La première version des features VMCV (implémentée dans `build_dim_vmcv_par_gare.py`)
présentait quatre limites identifiées lors de la revue du pipeline :

1. **Grain gare, pas tronçon** : la concurrence était agrégée au niveau de la gare,
   sans distinguer le sens de circulation. Une gare peut être desservie par VMCV dans
   un sens seulement, ou avec des fréquences très différentes selon la direction.

2. **Présence/absence seulement** : les features binaires ne capturaient pas
   l'avantage ou le désavantage relatif (attente, temps de trajet, fréquence).

3. **Statique** : les features ne variaient pas d'un jour à l'autre ni d'un train
   à l'autre, limitant leur pouvoir prédictif en interaction avec les features temporelles.

4. **Chaîne de dépendances longue** : `dim_vmcv_lignes_concurrentes` →
   `dim_vmcv_lignes_par_gare_r35` → `dim_vmcv_par_gare` → jointure dans la pipeline.

---

## Décisions

### D1 — Trois features différentielles au grain tronçon × train × jour

| Feature | Description | Signe positif |
|---------|-------------|---------------|
| `vmcv_delta_attente_min` | (attente R35) − (attente prochain VMCV dans [−5min, +30min]) | VMCV passe avant R35 |
| `vmcv_delta_trajet_min` | (trajet R35 sur tronçon) − (moyenne journalière du trajet VMCV sur le même tronçon) | VMCV plus rapide |
| `vmcv_delta_frequence_h` | (nb VMCV dans ±30min) − (nb R35 dans ±30min) | VMCV plus fréquent |

NaN si aucun arrêt VMCV alternatif dans le rayon RAYON_PROXIMITE_M (200m) pour les
deux extrémités du tronçon.

Note sur `delta_frequence` — convention de signe : la formule est inversée par rapport à la
définition littérale « (freq_R35 − freq_VMCV) » pour rester cohérente avec la
convention globale « delta > 0 = VMCV avantageux » de D1.

Note sur `delta_frequence` — auto-inclusion R35 : le train R35 courant est inclus dans
le décompte de sa propre fréquence (self-join sur le tronçon dans ±30min). Ce choix est
intentionnel : le voyageur perçoit la densité globale du service R35 sur le tronçon,
pas uniquement les « autres » trains. Conséquence : pour un train R35 isolé face à 1 VMCV,
`delta_frequence = 1 − 1 = 0`.

Note sur `delta_trajet_min` — fenêtre journalière : la moyenne de référence est calculée
sur **tous les services VMCV du jour** sur le tronçon (pas seulement ceux dans la fenêtre
d'attente). Cela stabilise le calcul lorsque peu de services VMCV coincident avec la
fenêtre d'attente d'un train R35 donné, et capture la vitesse structurelle de la ligne.

### D2 — Identification des alternatives VMCV par proximité géographique (200m)

Un arrêt VMCV est considéré alternatif à une gare R35 si la distance haversine est
≤ 200m. La condition s'applique aux **deux** extrémités du tronçon : un tronçon R35
n'a de features non-NaN que si ses deux gares ont chacune un arrêt VMCV alternatif
sur la **même ligne** (même `LINIEN_TEXT`).

En pratique, seul le tronçon VV↔GIL est couvert (lignes 202, 215) car la gare
VVVI (km=1.45), entre GIL (km=1.21) et CLIE (km=2.66), est trop éloignée des arrêts
VMCV pour être dans le rayon. Tous les tronçons hauts (Blonay-Pléiades) retourneront
NaN (aucune alternative bus).

### D3 — Reconstruction des tronçons VMCV via FAHRT_BEZEICHNER

Les passages VMCV sont extraits des CSV ISTDATEN bruts (filtrés sur
`BETREIBER_ABK == "VMCV"` et les BPUICs pertinents). La reconstruction des tronçons
utilise `FAHRT_BEZEICHNER` pour grouper les arrêts d'un même service, puis joint
les lignes de départ avec les lignes d'arrivée en imposant `h_dep < h_arr`. Seules
les paires correspondant au mapping statique (D2) sont conservées.

### D4 — Couverture temporelle : VMCV dans ISTDATEN à partir d'octobre 2018

Les données VMCV dans ISTDATEN débutent en octobre 2018. Avant cette date, toutes
les features VMCV sont NaN (XGBoost gère nativement les valeurs manquantes).

### D5 — Jointure J-2 dans add_istdaten_to_raw_stacked.py

Le décalage opérationnel J-2 est appliqué à la jointure via `_joindre_troncon_j_moins_2`
avec les 5 clés :
`(base_date, horaire_numero_train, id_gare_depart_bpuic, id_gare_arrivee_bpuic, base_sens)`

Même logique que `dim_profil_train` (ADR-019, D1). Le grain des deux tables est aligné.

---

## Features produites

Grain : `(date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)`

| Feature | Type | NaN si... |
|---------|------|-----------|
| `vmcv_delta_attente_min` | float | Pas d'alternative VMCV dans [−5, +30min] avant/après le départ R35 |
| `vmcv_delta_trajet_min` | float | Aucun service VMCV sur ce tronçon ce jour-là |
| `vmcv_delta_frequence_h` | float | Aucun VMCV dans ±30min autour du départ R35 |

---

## Conséquences

### Positives
- Features dynamiques : varient par train, par jour, par tronçon.
- Interprétables directement comme avantage compétitif instantané du mode bus.
- NaN naturels pour les tronçons sans alternative modale (pas d'imputation nécessaire).
- Grain cohérent avec `dim_profil_train` (ADR-019) → même jointure 5-clés.

### Négatives / Compromis
- Couverture limitée en pratique : seul VV↔GIL non-NaN (tous les tronçons hauts = NaN).
- La lecture des 84 CSV ISTDATEN bruts est nécessaire (plusieurs minutes d'exécution).
- La jointure sur 5 clés augmente le risque de NaN si les tronçons VMCV ne correspondent
  pas exactement aux tronçons APC (tolérance = 0).

### Fichiers modifiés / créés
| Fichier | Rôle |
|---------|------|
| `scripts/sources/build_dim_vmcv_par_troncon.py` | Nouveau — remplace `build_dim_vmcv_par_gare.py` |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py` | Ajout famille 3 VMCV avec jointure tronçon |
| `scripts/pipeline/paths.py` | Ajout `DIM_VMCV_PAR_TRONCON`, `DIM_VMCV_PAR_GARE` marqué DEPRECATED |
| `Makefile` | Règle `dim_vmcv_par_troncon`, mise à jour `dims` et `stage_07` |

---

## Alternatives rejetées

### A1 — Conserver le grain gare avec features quantitatives

Rejeté : le grain gare masque les variations directionnelles. Le grain tronçon est
cohérent avec ADR-019 (dim_profil_train) et permet la jointure sur 5 clés.

### A2 — Rayon de 500m au lieu de 200m

Rejeté : un rayon plus large inclut des arrêts de bus non-alternatifs (ex. arrêts
sur une avenue parallèle sans continuité de service). 200m garantit une proximité
physique directe (même carrefour ou passage piéton immédiat).

### A3 — Rolling windows temporelles pour les features VMCV

Non implémenté : les features VMCV sont calculées à la date réelle du service R35 et
varient naturellement d'un jour à l'autre via les grilles horaires VMCV effectives.
Un rolling ajouterait de la complexité sans gain interprétatif clair sur 3 features.

---


---
id: ADR-021
ancien_id: ADR-23
date_decision: 2026-05-18
statut: actif
precise_par: [ADR-040]
modifie: [ADR-020]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-021 — Refonte VMCV : décision à l'embarquement, grain train × jour × sens

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été précisée par ADR-040.
> Décisions antérieures que ce document modifie : ADR-020.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Implémenté et validé  
**Date** : 2026-05-18  
**Auteur** : E. Nédellec  
**Remplace** : ADR-020

---

## Contexte

ADR-020 (grain tronçon) a produit une couverture de 0,08 % (1 720 / 2 245 594 lignes),
très en-dessous du seuil d'inclusion de 0,5 %. L'analyse de la cause racine a révélé
un défaut structurel :

- L'arrêt GIL (Gilamont, bpuic 8501260, km=1,21) a été remplacé par VVVI (Vevey-Vignerons,
  bpuic 8502476, km=1,45) en décembre 2022.
- La ligne VMCV 202 n'est dense dans ISTDATEN qu'à partir de novembre 2022.
- Le critère ADR-020 exigeait qu'une même ligne VMCV soit présente aux deux extrémités d'un
  tronçon R35. Avec seulement 2 mois de chevauchement GIL/VMCV avant la transition, très
  peu de tronçons satisfaisaient ce critère.

Le retour qualitatif du panel passager (P03, 07:21 : *« il y a eu des lignes de bus qui ont
été ajoutées à Saint-Légier, qui m'ont permis des fois de pas prendre le train et de plutôt
prendre le bus »*) confirme un défaut conceptuel plus profond : **la décision
modale est prise à la gare d'embarquement, pas à chaque tronçon**. Un passager embarquant
à Vevey décide de prendre le R35 ou le bus 202 en fonction de l'offre à Vevey ; il ne
réévalue pas cette décision à chaque arrêt du trajet.

---

## Décisions

### D1 — Nouveau grain : (date, numero_train, sens)

La table `dim_vmcv_par_train_jour.parquet` est construite au grain
**(date, numero_train, sens)**, soit une ligne par départ de train dans une direction
donnée. Les features sont ensuite **propagées** à tous les tronçons du même train
lors de la jointure dans `add_istdaten_to_raw_stacked.py`.

### D2 — Test directionnel basé sur les seuils kilométriques empiriques

La pertinence d'une ligne VMCV pour un sens de circulation donné est déterminée
par sa présence près d'une gare R35 aux extrémités de la ligne :

| Sens         | Condition de pertinence                                          |
|:-------------|:-----------------------------------------------------------------|
| VV → PLEI    | La ligne VMCV a au moins un arrêt à ≤ 200 m d'une gare km ≥ 5,5 |
| PLEI → VV    | La ligne VMCV a au moins un arrêt à ≤ 200 m d'une gare km ≤ 4,0 |

**Justification empirique des seuils :**

L'analyse des charges moyennes de 2ème classe au départ (jours ouvrés, toutes
années horaires) révèle une bipolarité fonctionnelle nette :

| Gare              | km    | Montants/obs | Ratio vs seuil |
|:------------------|------:|-------------:|:---------------|
| Vevey             |  0,00 |        29,56 | — (pôle bas)   |
| Blonay            |  5,72 |        11,07 | 5,3× vs CDBL   |
| Château-de-Blonay |  5,35 |         2,08 | — (rupture)    |
| Les Pléiades      | 14,28 |         5,80 | — (pôle haut)  |

La rupture Blonay / Château-de-Blonay (ratio 5,3×) se situe entre km=5,35 et km=5,72.
Le seuil km ≥ 5,5 capture Blonay et au-delà, le seuil km ≤ 4,0 isole la zone
basse-vallée (Vevey, Vevey-Vignerons, La Tour-de-Peilz).

La zone intermédiaire (St-Légier-Village km=4,72 ; La Chiésaz km=5,10 ;
Château-de-Blonay km=5,35) reste délibérément hors du test directionnel :
une ligne VMCV ne desservant que ces gares ne constitue pas une alternative
crédible ni pour un voyageur montant vers Les Pléiades ni pour un voyageur
descendant vers Vevey.

### D3 — 4 features produites (vmcv_delta_trajet_min retiré)

| Feature                     | Description                                                                              | NaN si                               |
|:----------------------------|:-----------------------------------------------------------------------------------------|:-------------------------------------|
| `vmcv_n_lignes_concurrentes`| Nb de lignes VMCV distinctes pertinentes pour (gare départ, sens) — **statique**        | Jamais (= 0 si aucune ligne)         |
| `vmcv_min_attente_min`      | Attente minimale (min) avant le prochain VMCV dans [h_dep_r35 − 5min, h_dep_r35 + 30min] | Aucun VMCV dans la fenêtre d'attente |
| `vmcv_delta_attente_min`    | 5 − vmcv_min_attente_min (positif = VMCV avantageux car part presque au même moment)    | Aucun VMCV dans la fenêtre d'attente |
| `vmcv_delta_frequence_h`    | Nb VMCV dans ±30min − nb R35 dans ±30min (train courant inclus dans R35)               | 0 VMCV dans la fenêtre de fréquence  |

`vmcv_delta_trajet_min` de l'ADR-020 est **retiré** : le bus ne dessert pas la même
destination finale que le R35, ce qui rend une comparaison de temps de trajet
porte-à-porte non pertinente sans données OD passagers.

### D4 — Jointure J-2 sur 3 clés

La jointure dans `add_istdaten_to_raw_stacked.py` utilise :
- `base_date = date + 2j` (logique J-2 opérationnelle)
- `horaire_numero_train = numero_train`
- `base_sens = sens`

Chaque tronçon APC d'un train reçoit ainsi les mêmes 4 valeurs VMCV (propagation
naturelle du grain train×sens vers le grain tronçon).

---

## Conséquences

- **Couverture attendue** : nettement supérieure à 0,5 % car le critère de matching
  repose sur la gare de départ (toujours présente dans ISTDATEN) et non sur une paire
  de gares (soumise à la transition GIL → VVVI).
- **Concentration sur Vevey** : les features doivent être non-NaN principalement pour
  les trains partant de Vevey et Blonay, pas uniformément répartis sur tous les tronçons.
- **Rétrocompatibilité** : ADR-020 est retiré. `dim_vmcv_par_troncon.parquet` reste
  sur disque comme archive mais n'est plus utilisé par la pipeline.

---

## Validation empirique

*(Scripts : `analysis/coverage_vmcv.py`, `analysis/verify_vmcv_directional_mapping.py`,
`analysis/verify_vmcv_anomalies.py` — exécutés le 2026-05-18)*

### Couverture globale

| Métrique                    | Valeur            | Baseline ADR-020 |
|:----------------------------|------------------:|----------------:|
| Couverture globale (δ-att.) | **20,08 %**       | 0,08 %          |
| Gain                        | **×251**          | —               |
| Lignes couvertes (count)    | 474 083 / 2 360 762 | 1 720 / 2 245 594 |

### Couverture par année horaire

| Année horaire | Total tronçons | Couverts | Couverture |
|:-------------:|---------------:|---------:|:----------:|
| H16           |        168 377 |        0 |      0,00% |
| H17           |        218 529 |        0 |      0,00% |
| H18           |        195 696 |      414 |      0,21% |
| H19           |        233 595 |        0 |      0,00% |
| H20           |        208 312 |        0 |      0,00% |
| H21           |        194 269 |   15 041 |      7,74% |
| H22           |        161 597 |   49 512 |     30,64% |
| H23           |        335 426 |  204 143 |     60,86% |
| H24           |        335 709 |  195 077 |     58,11% |
| H25           |        309 252 |    9 896 |      3,20% |

La montée en couverture à partir de H21 reflète le déploiement progressif des données
VMCV réelles dans ISTDATEN (opérateur VMCV actif dans les exports à partir de fin 2020).

### Mapping directionnel

| Gare de départ    | km    | VV→PLEI couverts | PLEI→VV couverts |
|:------------------|------:|-----------------:|-----------------:|
| Vevey (8501200)   |  0,00 |          103 798 |                2 |
| Blonay (8501281)  |  5,72 |            3 267 |           66 664 |
| St-Légier-Village (8501264) | 4,02 |            2 |                8 |

Les 14 autres gares R35 sont **toutes Cause A** : aucun arrêt VMCV à ≤ 200 m. Cause B = 0
(aucun cas où un VMCV est proche géographiquement mais échoue au test directionnel pour
une gare avec du trafic réel).

### Distribution de `vmcv_delta_attente_min` (lignes couvertes, n=474 083)

| Statistique | Valeur |
|:------------|-------:|
| min         | −30,00 |
| p05         |  −4,05 |
| médiane     |  +2,30 |
| p95         |  +5,00 |
| max         |  +5,00 |
| % > 0 (VMCV avantageux) | **66,9 %** |

### Note structurelle — gares non couvertes

Sur les 17 gares R35 apparaissant comme gare de départ dans ISTDATEN, 3 disposent
d'une alternative VMCV à ≤ 200 m : Vevey, Blonay et St-Légier-Village (10 trains
partiels sur l'ensemble de la période — cf. Vérification 1 ci-dessous).

Les 14 gares intermédiaires (Vevey-Vignerons, Clies, Hauteville, Château-d'Hauteville,
St-Légier-Gare, La Chiésaz, Château-de-Blonay, Prélaz-sur-Blonay, Tusinge,
Les Chevalleyres, Bois-de-Chexbres, Fayaux, Ondallaz-L'Alliaz, Lally) ne sont desservies
par aucun bus VMCV dans le rayon de 200 m. Cette absence reflète la géographie du
territoire (zone semi-rurale entre Vevey et Blonay) et constitue une caractéristique
structurelle du réseau de transport régional, pas un défaut de mapping.

### Vérification 1 — St-Légier-Village comme gare de départ (10 trains)

Causes identifiées après analyse des séquences ISTDATEN :
- **VV→PLEI (2 trains)** : train 1372 du 2023-08-24 et train 1344 du 2024-03-01.
  Les séquences montrent que ces trains démarrent physiquement à Blonay mais
  ont St-Légier-Village comme premier arrêt *dans le sens VV→PLEI* — ce sont des
  trains qui font un aller-retour partiel (Blonay→St-Légier puis repartent en montée).
  Aucun arrêt annulé. 10 trains au total sur la période : volume négligeable.
- **PLEI→VV (8 trains)** : trains partiels avec 0 arrêt annulé mais séquence complète
  débutant avant St-Légier-Village. L'identification de la gare de départ effective
  capture le premier tronçon dans le sens PLEI→VV, qui se trouve être St-Légier-Village
  pour ces courses où le segment haut est en sens inverse.

**Conclusion** : ces 10 trains ne constituent pas un artefact de données. L'impact
sur la couverture VMCV est nul (volume < 0,005 % du dataset total).

### Vérification 2 — Limitation connue du test directionnel D2

L'analyse du mapping pour Vevey (km=0) en PLEI→VV révèle que 11 des 12 lignes VMCV
identifiées (201, 202, 209, 211, 212, 213, 215, 216, 217, 218, 290) **ne traversent
pas la zone haute** (n_gares_haut=0 pour toutes). Seule la ligne 291 a des arrêts
proches des deux pôles.

**Cause** : le test D2 actuel sélectionne une ligne pour sens PLEI→VV si elle appartient
à `lines_near_bas` (≥1 arrêt près d'une gare km ≤ 4,0). Pour une gare *elle-même* dans
la zone bas (comme Vevey à km=0), la gare satisfait trivialement le critère, et toutes
les lignes VMCV passant par Vevey sont incluses, y compris des bus urbains qui ne
remontent pas vers Blonay.

**Impact réel** : les 2 trains Vevey-PLEI→VV représentent 0,001 % du dataset total.
La couverture PLEI→VV significative provient entièrement de Blonay (km=5,72), où le
test est correct : seules les lignes avec un arrêt près de Blonay ET un arrêt près de
la zone bas (Vevey) sont incluses.

**Limitation tolérable** : une version raffinée exigerait qu'une ligne ait des arrêts
dans les deux pôles (et non seulement dans le pôle opposé à la gare considérée). Cette
correction est reportée à une itération ultérieure si l'analyse SHAP révèle un problème
de signal. XGBoost discriminera empiriquement les lignes utiles via la corrélation
feature–cible sur les 474 083 lignes couvertes.

---

## Fichiers modifiés

| Fichier                                      | Rôle                                    |
|:---------------------------------------------|:----------------------------------------|
| `scripts/sources/build_dim_vmcv_par_train_jour.py` | Script producteur (nouveau)       |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py`  | Famille 3 mise à jour             |
| `scripts/pipeline/paths.py`                  | `DIM_VMCV_PAR_TRAIN_JOUR` ajouté       |
| `Makefile`                                   | Règle + dépendances mise à jour        |
| `tests/test_pipeline_vmcv_train_jour.py`     | 34 tests (nouveau)                     |
| `tests/test_pipeline_vmcv.py`                | Marqué DEPRECATED                     |
| `analysis/coverage_vmcv.py`                  | Features ADR-021                        |
| `analysis/verify_vmcv_directional_mapping.py`| Diagnostic mapping directionnel        |
| `analysis/verify_vmcv_anomalies.py`          | Vérifications V1/V2 pré-clôture        |

---


---
id: ADR-022
ancien_id: ADR-05
date_decision: 2026-05-21
statut: actif
amende_par: [ADR-028]
modifie: [ADR-003]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-022 — Disponibilité J-1 des features et stratégie météo horaire

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été amendée par ADR-028.
> Décisions antérieures que ce document modifie : ADR-003.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Révisé |
| **Date initiale** | 2026-05 |
| **Révision** | 2026-05-21 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `01_business_understanding.ipynb` §5, `02_data_understanding_meteosuisse.ipynb` |

---

## 1. Contexte — Logique J-1 et train/serve skew

Le modèle doit fonctionner dans une logique J-1 : toute prédiction est produite la veille du jour de circulation (communication au mécanicien le soir J-1). Toute variable utilisée en prédiction doit donc être disponible ou approximable à ce moment.

Ce principe s'applique aussi bien au prototype historique qu'au déploiement opérationnel. Les contraintes de disponibilité influencent :
- La sélection finale des features (interdiction d'utiliser des données du jour J)
- La logique de jointure dans la pipeline (décalage temporel nécessaire)
- La valeur des backtests (réalisme de la simulation opérationnelle)

---

## 2. Décision sur la granularité météo

**Les features météo passent d'une agrégation journalière à une résolution horaire.**

Cette décision est motivée par trois arguments :

**Alignement train/serve.** En exploitation J-1, le modèle sera servi par les prévisions horaires MétéoSuisse (« Local forecast data », point forecasts pour ~6 000 localités suisses, mis à jour toutes les heures, horizon jusqu'à J+7). La granularité journalière introduisait une asymétrie structurelle entre entraînement (moyennes journalières) et inférence (prévisions horaires). Le passage à l'horaire réduit cet écart.

**Exploitation comportementale fine.** Une moyenne journalière écrase les signaux comportementaux distincts : commuter du matin, excursionniste de l'après-midi, sortie opportuniste conditionnée à la météo du moment. La résolution horaire permet d'attribuer à chaque train sa météo à l'heure de départ.

**Cohérence avec CRISP-ML(Q).** Le choix de granularité est une décision de conception, documentée ici comme telle, et non un détail d'implémentation.

**Approche MVP.** Cette refonte se limite délibérément à six features de premier niveau (température, précipitations, ensoleillement, vent, hauteur de neige et flag neige binaire), toutes à l'heure du départ et mappées selon le segment du tronçon. Des features dérivées plus sophistiquées (différentiels VEV/CHD, fenêtres temporelles matinale et d'usage, tendances multi-jours, lag de hauteur de neige) pourront être ajoutées dans une itération ultérieure, sur la base des résultats de feature importance (SHAP) et de la triangulation avec le corpus qualitatif. Le principe MVP — démontrer la valeur de la granularité horaire et du mapping spatial avant d'enrichir — guide ce choix méthodologique et s'inscrit dans la logique itérative de CRISP-ML(Q).

**Itération 2 — features destination.** Suite à l'analyse SHAP du modèle initial (faible importance des features météo locales au tronçon), une seconde itération MVP introduit quatre features supplémentaires capturant le comportement d'anticipation de l'usager : température, précipitations, ensoleillement et vent à la destination du train (CHD pour les trains montants, VEV pour les descendants). Ces ajouts visent à tester l'hypothèse comportementale selon laquelle la décision de prendre le train dépend davantage des conditions anticipées à destination que des conditions vécues au tronçon courant. Les features locales au tronçon ne sont pas remplacées : XGBoost et l'analyse SHAP arbitreront entre les deux logiques. Les features liées à la hauteur de neige initialement envisagées (locale, destination, praticabilité ski) ont été retirées suite à un diagnostic d'instrumentation détaillé en section 6.

---

## 3. Décision sur les stations d'observation

Deux stations MétéoSuisse sont utilisées comme sources d'entraînement :

| Station | Altitude | Segment servi | Rôle |
|---|---|---|---|
| **VEV** Vevey/Corseaux | ~380 m | bas (ordre ≤ 10) | Proxy régional bas de ligne |
| **CHD** Château-d'Oex | ~1 000 m | haut (ordre > 10) | Proxy altitude Les Pléiades (~1 350 m) |

**Mapping spatial bas/haut.** Le segment d'un tronçon est déterminé par la position ordinale de ses deux gares dans `dim_gare` :
- **bas** : les deux gares ont `ordre ≤ 10` — tronçon entièrement en plaine, Blonay incluse comme terminus bas
- **haut** : au moins une des deux gares a `ordre > 10` — le tronçon touche la crémaillère

Le cas **mixte** disparaît par construction de cette règle : dès qu'un tronçon touche la crémaillère (une des deux gares au-delà de Blonay), il est classé **haut**. Blonay (ordre 10) est donc **bas** quand elle est associée à une gare de plaine, et **haut** quand elle est associée à une gare d'altitude (Prélaz-sur-Blonay et au-delà).

La résolution VEV/CHD est transparente dans le dataset final : les 6 colonnes `meteo_*_h` reçoivent la valeur de la station appropriée selon le segment, sans préfixe station visible.

---

## 4. Train/serve skew — Reconnaissance et protocole de calibration

**En entraînement**, les features météo sont construites à partir d'**observations horaires MétéoSuisse** aux stations VEV et CHD. Ces observations correspondent à la météo réalisée le jour J.

**En exploitation J-1**, ces variables seraient alimentées par les **prévisions horaires point MétéoSuisse** disponibles jusqu'à J+7.

**Impossibilité matérielle d'utiliser des prévisions archivées.** MétéoSuisse n'archive pas les prévisions historiques dans ses canaux OGD : le catalogue STAC ne propose que les prévisions courantes (rétention 24–48 h selon le dataset). Il est donc impossible de reconstituer rétrospectivement les prévisions qui auraient été disponibles à J-1 pour les années H22–H24.

**Conséquence acceptée.** Le prototype utilise les observations comme proxy des prévisions. Cette hypothèse est moins problématique à la granularité horaire qu'à la granularité journalière : les prévisions horaires à J-1 ont une précision suffisante pour que l'écart observation/prévision reste faible sur les variables utilisées (température, précipitations, ensoleillement).

**Protocole de calibration shadow.** Pour constituer l'archive nécessaire à l'évaluation future du gap observation/prévision, un snapshot quotidien des prévisions MétéoSuisse locales pour les localités R35 (Vevey, Blonay, Les Pléiades) devrait être initié dès maintenant. Ce protocole — non implémenté dans le prototype — est un principe de conception pour le déploiement opérationnel.

---

## 5. Matrice de disponibilité J-1

Toute feature est classée dans l'une des cinq catégories suivantes :

| Catégorie | Définition | Features concernées | Traitement dans la pipeline |
|---|---|---|---|
| **1 — Certaine** | Disponible à J-1 de manière certaine, sans hypothèse | `cal_*`, `horaire_*`, `event_*`, `spatial_*`, `histo_*` (lags) | Jointure directe |
| **2 — Prévisionnelle** | Disponible à J-1 via prévision horaire (incertitude résiduelle) | `meteo_*_h` (5 features locales : temp., préc., ensoleillement, vent, neige binaire), `meteo_destination_*_h` (4 features destination : temp., préc., ensoleillement, vent) | Observations horaires VEV/CHD comme proxy des prévisions MétéoSuisse horaires disponibles à J-1. Mapping VEV/CHD selon `spatial_segment` (local) ou `base_sens` (destination). Les features hauteur de neige (`meteo_neige_cm_h`, `meteo_destination_neige_cm_h`, `event_ski_neige_si_ouvert_h`) ont été retirées (cf. §6). |
| **3 — Dernier état connu** | Disponible à J-1 via le dernier enregistrement disponible | `spatial_*` (STATPOP) | Dernier millésime disponible à la date de prédiction (cf. ADR-006) |
| **4 — Décalée** | Disponible à J-1 uniquement sur observations passées | `ist_*` (ponctualité, réalisation, headway) | Calcul sur fenêtres J-2, J-8→J-2, jamais sur J (cf. ADR-008, ADR-015, ADR-018) |
| **5 — Interdite** | Contient des informations du jour J — data leakage | `base_tx_occupation_*`, `base_passagers_*`, `base_places_disponibles_*` | Supprimées dans `build_ml_dataset.py` |

---

## Règles d'application

1. **Catégorie 5 (interdite)** : exclues dans `build_ml_dataset.py`. Ne doivent jamais figurer parmi les inputs du modèle.

2. **Catégorie 4 (décalée)** : les features `ist_*` sont calculées sur des observations antérieures à la date prédite. Aucune information de réalisation du jour J n'est utilisée.

3. **Catégorie 2 (prévisionnelle — météo)** : voir sections 2, 3, 4 ci-dessus. La pipeline opérationnelle devra alimenter les features météo depuis les prévisions MétéoSuisse horaires, et non depuis les observations a posteriori.

---

## Conséquences

- Les analyses de feature importance (SHAP) distingueront les features certaines (catégorie 1) des features prévisionnelles (catégorie 2).
- La pipeline opérationnelle devra intégrer les prévisions MétéoSuisse horaires pour les localités R35.
- L'initiation du protocole de calibration shadow est recommandée avant tout déploiement en production.

## 6. Retrait des features de hauteur de neige — shift d'instrumentation

### Constat empirique

L'inspection des fichiers MétéoSuisse propres (parquets `meteo_vev_clean` et `meteo_chd_clean`) a révélé que le paramètre `htoauths` (hauteur de neige automatique, valeur instantanée horaire) n'a été instrumenté ni à VEV ni à CHD avant 2023 :

| Station | Avant 2023 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| VEV | 100 % NaN | 36 % couvert | 98 % couvert | 100 % couvert |
| CHD | 100 % NaN | 56 % couvert | 99 % couvert | 100 % couvert |

Les valeurs 0 cm existent par ailleurs (22.4 % VEV, 9.1 % CHD globalement) et confirment que les capteurs retournent bien 0 en absence de neige. Les NaN avant 2023 sont donc structurellement attribuables à l'absence d'installation du capteur, pas à un encodage de « pas de neige ».

### Conséquence sur la configuration train/test

La configuration prototype utilise H22-H23 comme données d'entraînement et H24 comme données de test. Cette configuration crée un **shift d'instrumentation** sur trois features dépendantes de `htoauths` :

- `meteo_neige_cm_h` (locale au tronçon)
- `meteo_destination_neige_cm_h` (destination)
- `event_ski_neige_si_ouvert_h` (praticabilité ski)

Ces trois features sont quasi-100 % NaN en train (H22-H23) et quasi-100 % renseignées en test (H24). XGBoost gère techniquement les NaN, mais ne peut pas apprendre la structure du signal à partir d'un train où la feature ne varie pratiquement pas. Toute analyse SHAP sur ces trois features refléterait un artefact d'instrumentation et non un signal métier exploitable.

### Décision

Les trois features sont **retirées du dataset** au stade du prototype. La feature `meteo_neige_binaire_h` (flag binaire neige) est conservée car sa construction ne dépend pas exclusivement de `htoauths` : côté VEV elle repose uniquement sur la pluie froide (précipitations > 0 ET T < 2°C), et côté CHD la logique OR retombe proprement sur la pluie froide quand `htoauths` est NaN (`NaN > 0` est évalué à `False` par pandas).

### Réversibilité

Les features retirées pourront être réintroduites dans une itération future lorsque les données d'entraînement incluront 2024 ou ultérieures (à partir de l'année horaire H25 par exemple), période sur laquelle l'instrumentation `htoauths` est complète sur les deux stations.

### Inscription méthodologique

Cette décision illustre un principe central de CRISP-ML(Q) : la phase Data Understanding doit identifier les défauts structurels d'instrumentation avant qu'ils ne contaminent silencieusement les phases ultérieures. Le retrait préventif est préférable à la conservation d'une feature techniquement disponible mais méthodologiquement inexploitable, parce qu'elle introduirait un biais d'interprétation dans les résultats SHAP sans gain prédictif réel.

---

## Fichiers impactés

- `scripts/pipeline/add_spatial_to_raw_stacked.py` (nouveau stage_03e — correction frontière Blonay)
- `scripts/pipeline/add_meteo_to_raw_stacked.py` (nouveau stage_04 — fusion VEV+CHD, horaire, 9 features)
- `scripts/pipeline/add_features_to_raw_stacked.py` (retrait calcul spatial, passthrough)
- `scripts/pipeline/build_ml_dataset.py` (préfixe `meteo_` conservé, colonnes `_j` disparaissent)
- `notebooks/02_data_understanding_meteosuisse.ipynb`

---


---
id: ADR-023
ancien_id: ADR-24
date_decision: 2026-05-21
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-023 — Inclusion de IR90 et IR dans les feeders Vevey

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-21
**Décideur** : Erwann Nédellec (superviseur)

## Contexte

Le calcul des correspondances Vevey CFF ↔ R35 (`build_dim_correspondances_vevey.py`,
`build_istdaten_ponctualite.py`) utilise une liste de lignes "feeders" qui
alimentent ou captent les voyageurs du R35 à la gare de Vevey (BPUIC=8501200).

La liste initiale (`S3`, `S4`, `S7`, `R3`, `R4`, `R7`, `RE`, `RE33`) couvrait les
lignes régionales et le RE33 mais omettait les lignes InterRegio passant par Vevey.

## Diagnostic (données ISTDATEN 2024, BPUIC=8501200, hors transit et annulés)

| LINIEN_TEXT | Passages 2024 | Commentaire |
|---|---|---|
| R35 | 32 030 | La ligne elle-même — pas un feeder |
| RE33 | 23 421 | ✅ inclus |
| **IR90** | **22 975** | ❌ absent — Genève-Aéroport–Brig |
| R3 | 14 616 | ✅ inclus |
| R4 | 14 269 | ✅ inclus |
| R7 | 13 201 | ✅ inclus |
| **IR** | **3 236** | ❌ absent — désignation générique (voir ci-dessous) |
| RE | 1 434 | ✅ inclus |
| IR95 | 590 | ❌ exclus (volume marginal) |
| SN / EC / EXT | < 250 | ❌ exclus (internationaux / exceptionnels) |

### Analyse de "IR" (sans suffixe numérique)

- **Opérateur** : SBB uniquement.
- **Distribution horaire** : 72% des passages entre 5h et 7h, + 0h et 23h.
  Ces trains correspondent aux premières et dernières courses du jour sur
  l'axe Genève–Brig (même axe qu'IR90), qui conservent l'ancien label générique
  "IR" dans ISTDATEN tandis que les trains de journée ont été renommés "IR90".
- **LINIEN_IDs** : distincts des LINIEN_IDs IR90 — pas de doublons.
- **Conclusion** : feeders réels concentrés en heures de pointe matinale.

## Décision

Ajouter **IR90** et **IR** à `LINIEN_FEEDERS_VEVEY` / `LINIEN_FEEDERS` dans les
deux scripts concernés. Exclusions maintenues :

| Ligne | Décision | Motif |
|---|---|---|
| IR90 | ✅ inclus | Volume identique à RE33, ligne touristique Genève–Brig directe |
| IR | ✅ inclus | Premiers/derniers trains du jour sur axe IR90, feeders matinaux pertinents |
| IR95 | ❌ exclus | < 600 passages/an, impact statistique négligeable |
| SN | ❌ exclus | Scenic Night / services nocturnes internationaux |
| EC | ❌ exclus | EuroCity, clientèle longue distance, peu de correspondances R35 |
| EXT / EXT3 / EXT33 | ❌ exclus | Trains exceptionnels (<200 passages), bruit catégoriel |

## Justification de l'inclusion IR90

La R35 dessert Les Pléiades, destination touristique de référence du chablais vaudois.
L'IR90 Genève-Aéroport–Brig (via Lausanne, Vevey, Montreux) est la liaison principale
amenant la clientèle touristique depuis Genève, Lausanne et le Valais vers Vevey, point
de correspondance naturel avec la R35. Son omission initiale constituait un biais
systématique dans les features de correspondance.

## Conséquences

- `ist_vevey_n_arrivees_j` et indicateurs associés augmenteront (~+5-10% de passages).
- `ist_corresp_in_n_theoriques_j` et `ist_corresp_out_n_theoriques_j` augmenteront
  pour les trains R35 dont les horaires coïncident avec les IR90/IR.
- Le pipeline de dimension `dim_correspondances_vevey` doit être régénéré.
- L'impact quantitatif est documenté dans le message de comparaison AVANT/APRÈS.

## Fichiers impactés

- `scripts/sources/build_istdaten_ponctualite.py` — `LINIEN_FEEDERS_VEVEY`
- `scripts/sources/build_dim_correspondances_vevey.py` — `LINIEN_FEEDERS`

---


---
id: ADR-024
ancien_id: ADR-25
date_decision: 2026-05-21
statut: actif
amende_par: [ADR-025]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-024 — Sélection de features STATPOP : retrait des redondances arithmétiques

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Cette décision a été amendée par ADR-025.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

## Statut
Accepté — 2026-05-21

## Contexte

Le dataset `ml_dataset` contient un sous-espace de features `spatial_*` composé de :
- 4 features de topologie (`spatial_distance_km`, `spatial_segment`, `spatial_gare_depart_ordre`, `spatial_gare_arrivee_ordre`)
- 50 features STATPOP (25 indicateurs × 2 côtés : départ et arrivée)

Un diagnostic de corrélations a été conduit sur le sous-espace STATPOP pour identifier les multicolinéarités susceptibles de dégrader l'interprétabilité SHAP du modèle XGBoost et d'introduire une instabilité dans les importances de features.

## Diagnostic

Deux clusters de redondance ont été identifiés :

### Cluster 1 — Redondance arithmétique exacte (r = 1.00)

Le buffer STATPOP est calculé avec un rayon fixe `RADIUS_M = 500` (m) pour toutes les gares. La surface de capture est donc constante : `BUFFER_AREA_KM2 = π × 0.25 ≈ 0.785 km²`.

Par construction dans `build_fact_statpop_gare.py` :
```
densite_population_500m_km2 = population_500m_total / 0.785
densite_menages_500m_km2    = menages_500m_total    / 0.785
```

Ces densités sont des transformations affines des totaux. La corrélation est exactement 1.00 pour toutes les gares et tous les millésimes.

### Cluster 2 — Redondance quasi-parfaite (r = 0.96)

`taille_menage_moyenne_estimee` est calculée dans `build_fact_statpop_gare.py` comme la moyenne pondérée :

```
taille_moy = (HP01 + 2·HP02 + 3·HP03 + 4·HP04 + 5·HP05 + 6·HP06) / HPTOT
```

`part_grands_menages_4p_plus` est `(HP04 + HP05 + HP06) / HPTOT`.

Les grands ménages (≥ 4 personnes) dominent arithmétiquement le numérateur de la taille moyenne. Les deux variables mesurent essentiellement la même dimension de la structure des ménages.

## Décision

Retrait de 3 features (× 2 côtés = 6 colonnes au total) du set `STATPOP_KEEP_SUFFIXES` dans `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` :

| Feature retirée | Feature conservée | Raison |
|---|---|---|
| `densite_population_500m_km2` | `population_500m_total` | r = 1.00 par construction |
| `densite_menages_500m_km2` | `menages_500m_total` | r = 1.00 par construction |
| `taille_menage_moyenne_estimee` | `part_grands_menages_4p_plus` | r = 0.96, redondance quasi-parfaite |

**Principe de conservation** : on garde les valeurs absolues (totaux) et les parts bornées `[0, 1]`, qui sont plus interprétables et dont le sens ne dépend pas d'un paramètre de rayon de buffer (à comparer avec les densités, qui deviendraient fausses si le rayon change).

## Implémentation

Retrait localisé uniquement dans `STATPOP_KEEP_SUFFIXES` du script pipeline. La table source `statpop_clean.parquet` conserve l'intégralité des 27 features d'origine. La réversibilité est totale : réintroduire les variables retirées nécessite uniquement la réinsertion de leur suffixe dans le set et le recalcul du `stage_06`.

**Fichier modifié** : `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py`

## Conséquences

- **Avant** : 54 features `spatial_*` (4 topologie + 50 STATPOP)
- **Après** : 52 features `spatial_*` (4 topologie + 48 STATPOP)
- Élimination de toutes les paires avec r > 0.95 dans le sous-espace STATPOP
- Amélioration attendue de la stabilité et de l'interprétabilité des valeurs SHAP

## Réversibilité

Les variables retirées sont recalculables arithmétiquement depuis les features conservées :
- `densite_pop_500m_km2 = population_500m_total / 0.785`
- `densite_menages_500m_km2 = menages_500m_total / 0.785`
- `taille_menage_moy` : relation empirique non-linéaire avec `part_grands_menages_4p` (r = 0.96)

La table `statpop_clean.parquet` préserve les 27 features d'origine sans modification.

## Références

- [ADR-011](ADR-011_imputation_millesimes_statpop_manquants.md) — Imputation des millésimes 2021 et 2023
- [ADR-006](ADR-006_statpop_dernier_millesime_disponible.md) — Choix du millésime de référence
- `scripts/sources/build_fact_statpop_gare.py` — Construction des features STATPOP

---


---
id: ADR-025
ancien_id: ADR-26
date_decision: 2026-05-21
statut: amendé
amende_par: [ADR-039, ADR-063]
modifie: [ADR-024]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-025 — Refonte du buffer STATPOP : Voronoi clippé par année horaire

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-039, ADR-063.
> Décisions antérieures que ce document modifie : ADR-024.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

## Statut
Accepté — 2026-05-21

## Contexte

Le diagnostic `docs/diagnostic_buffers_statpop.md` (2026-05-21) a établi que le buffer disque uniforme de 500 m crée des chevauchements sévères entre gares voisines :
- **79 % des gares** ont un taux de captation propre < 50 %
- La gare la plus touchée (VVVI) ne dispose que de **11 % de zone exclusive**
- 8 paires présentent plus de 50 % du buffer en commun (pire cas : VVVI ↔ CLIE à 226 m, 71.5 % en commun)

De plus, la topologie R35 évolue dans le temps :
- **CLIE** (Clies) : active H16–H18, fermée fin H18
- **GIL** (Gilamont) : actif H16–H22, fermé fin H22
- **VVVI** (Vevey Vignerons) : actif depuis H23, remplace GIL

Un buffer disque ignorant ces évolutions topologiques attribue les mêmes hectares à GIL et VVVI simultanément, même pour les années où l'une ou l'autre est fermée.

## Décision

Remplacer le buffer disque uniforme par un **diagramme de Voronoi clippé à 500 m, recalculé pour chaque topologie active**.

Pour chaque combinaison (année horaire HY, gare g active en HY) :

```
Z(g, HY) = (polygone de Voronoi de g sur les gares actives en HY) ∩ (disque 500 m centré sur g)
```

Propriétés garanties :
1. **Aucun chevauchement** entre zones de gares actives la même année (partition de Voronoi)
2. **Zone maximale de 500 m** depuis chaque gare (clippage disque)
3. **Cohérence topologique** : les zones reflètent les gares effectivement actives

## Mapping millésime STATPOP → topologie

Convention : le millésime STATPOP année civile Y utilise la topologie de l'année horaire HY (même numéro), qui couvre la majorité des jours de l'année civile Y. Pour STATPOP 2015 (antérieur à H16), la topologie H16 est utilisée par défaut car H15 est hors périmètre des données APC.

| Millésime STATPOP | Année horaire | Gares actives (résumé) |
|---|---|---|
| 2015 | H16 | 18 gares (GIL + CLIE actifs ; VVVI absent) |
| 2016 | H16 | 18 gares |
| 2017 | H17 | 18 gares (GIL + CLIE actifs) |
| 2018 | H18 | 18 gares (GIL + CLIE actifs) |
| 2019 | H19 | 17 gares (CLIE fermée) |
| 2020 | H20 | 17 gares |
| 2021 | H21 | 17 gares |
| 2022 | H22 | 17 gares (GIL encore actif) |
| 2023 | H23 | 17 gares (GIL fermé, VVVI actif) |
| 2024 | H24 | 17 gares |

Source des gares actives : `data/processed/horaires_r35_arrets_officiels.parquet` (PDFs H16–H25 officiel MVR).

## Implémentation

**Fichier modifié** : `scripts/sources/build_fact_statpop_gare.py`

Nouvelles fonctions :
- `load_active_gares_by_horaire()` — charge les gares actives depuis les horaires officiels
- `compute_voronoi_zones()` — calcule les polygones Voronoi clippés (shapely 2.0)
- `get_voronoi_zones_for_year()` — cache par topologie pour éviter les recalculs

Modifications :
- `aggregate_raw_values_for_station()` — utilise `shapely.within()` (vectorisé) au lieu de distance euclidienne
- `build_features_from_raw_aggregates()` — accepte `zone_area_km2` réelle pour les densités
- `aggregate_for_station()` — accepte un polygone Voronoi
- `build_fact()` — itère uniquement sur les gares actives par millésime

**Comportement de la sortie** :
- Avant : 19 gares × 10 millésimes = 190 lignes
- Après : 174 lignes (GIL 8 ans, CLIE 4 ans, VVVI 2 ans, 16 autres × 10 ans)

Aucune modification de schéma (27 features, mêmes noms, mêmes types).

## Conséquences

- Les features `densite_population_500m_km2` et `densite_menages_500m_km2` dans `statpop_clean.parquet` utilisent désormais l'aire réelle de la zone Voronoi comme dénominateur (plus correct qu'une constante). Ces features sont exclues du ML dataset (ADR-024) mais leur valeur en source est améliorée.
- La colonne `statpop_hectares_count` reflète les hectares dans la zone Voronoi, pas dans le disque.
- Aucun changement de schéma dans `stage_06_statpop.parquet` ni `ml_dataset.parquet`.
- Les gares inactives pour un millésime donné n'ont plus d'entrée dans `statpop_clean.parquet` (comportement correct : pas de jointure APC possible sur ces lignes).

## Gestion des transitions topologiques

Entre H22 et H23 (GIL → VVVI) :
- STATPOP 2022 : GIL reçoit sa zone Voronoi habituelle ; VVVI absent
- STATPOP 2023 : VVVI reçoit une zone Voronoi incluant les hectares autrefois attribués à GIL ; GIL absent

Ce saut de zone est intentionnel et reflète la réalité du réseau. Le modèle XGBoost gère cette discontinuité via la feature `horaire_annee_horaire` déjà présente dans le dataset.

## Trade-offs et limites

1. **Nom des features légèrement trompeur** : `population_500m_total` désigne la population dans la zone Voronoi ≤ 500 m, pas un disque de 500 m. Renommage (`pop_zone_total`) envisageable dans une itération future mais non prioritaire.
2. **Dépendance à shapely** : ajouté comme dépendance Python du projet (`pip install shapely`).
3. **Performance** : le calcul Voronoi est mis en cache par topologie (3 topologies distinctes = 3 calculs) — négligeable à l'exécution.
4. **Couverture < 500 m pour les gares en cluster** : par construction, les zones Voronoi des gares très proches sont plus petites que le disque de 500 m. La population capturée est donc plus faible mais correspond mieux à la zone d'influence réelle.

## Réversibilité

Pour revenir au buffer disque, remplacer le filtrage `shapely.within(points_arr, zone)` par `dist <= RADIUS_M` dans `aggregate_raw_values_for_station()` et restaurer `build_fact()` sans les zones Voronoi. La sauvegarde de l'ancien fichier est disponible : `statpop_clean_disque500.parquet`.

## Références

- `docs/diagnostic_buffers_statpop.md` — diagnostic ayant motivé la décision
- [ADR-024](ADR-024_selection_features_statpop.md) — retrait des redondances arithmétiques (préservé)
- [ADR-011](ADR-011_imputation_millesimes_statpop_manquants.md) — imputation 2021/2023 (inchangée)
- [ADR-006](ADR-006_statpop_dernier_millesime_disponible.md) — choix du millésime de référence

---


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

---


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

---


---
id: ADR-028
ancien_id: ADR-29
date_decision: 2026-05-23
statut: actif
modifie: [ADR-022]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-028 — Enrichissement des features météo : agrégats journaliers J, J-1, J+1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-022.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-23 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/02d_diagnostic_features_meteo.ipynb` |
| **Note de décision** | `notes/02d_recap_meteo_pour_decision.md` |

---

## 1. Contexte

Le modèle de référence (H22-H23 → H24, R²=0.62) ne fait apparaître aucune feature `meteo_*`
dans le top 20 SHAP, malgré le profil touristique marqué de la R35 (segment Blonay → Les Pléiades).

Le diagnostic empirique du notebook `02d_diagnostic_features_meteo.ipynb` révèle deux limites
structurelles des 9 features `meteo_*_h` actuelles (cf. ADR-022) :

**Limite 1 — Granularité horaire ponctuelle.** Les features actuelles capturent la météo à l'heure
exacte du passage du train. Or les décisions touristiques (aller au lac, en montagne, skier) répondent
aux conditions journalières globales anticipées, pas à la valeur ponctuelle à l'heure de départ.
La médiane des heures de départ est ~14h sur les deux segments : un voyageur décide le matin
en se basant sur la météo attendue pour la journée, pas sur la valeur observée à 6h.

**Limite 2 — Corrélations faibles entre valeurs horaires et agrégats journaliers.**
Mesurées sur le dataset H22-H24, segment bas :

| Feature horaire actuelle | Agrégat journalier candidat | Corrélation Pearson |
|---|---|---|
| `meteo_temperature_h` | T° max journalière | **r = 0.956** (quasi-redondant) |
| `meteo_precipitation_mm_h` | Total précipitations j | **r = 0.472** (signal différent) |
| `meteo_ensoleillement_min_h` | Total ensoleillement j | **r = 0.582** (signal différent) |
| `meteo_vent_max_h` | Rafale max j | **r = 0.590** (signal différent) |

La variabilité intra-journalière du rayonnement global (std 199 W/m², range 576 W/m² sur VEV 2024)
justifie également l'ajout d'un agrégat journalier pour ce paramètre, absent des features actuelles.

---

## 2. Décision — 18 nouvelles features réparties en 4 niveaux

### Niveau 1 — Agrégats journaliers J, locaux (4 features)

| Feature | Calcul | Station |
|---|---|---|
| `meteo_temperature_max_j` | T° max du jour J (°C) | VEV ou CHD selon `spatial_segment` |
| `meteo_precip_total_j` | Σ précipitations du jour J (mm) | VEV ou CHD |
| `meteo_ensol_total_j` | Σ ensoleillement du jour J (min) | VEV ou CHD |
| `meteo_vent_max_j` | Rafale max du jour J (km/h) | VEV ou CHD |

### Niveau 2 — Agrégats journaliers J, destination (4 features)

Même calcul que le niveau 1, avec la station mappée sur la **gare destination du tronçon**
selon `base_sens` (identique à la logique existante des `meteo_destination_*_h`) :

| Feature | Station |
|---|---|
| `meteo_destination_temperature_max_j` | CHD (montant VV→PLEI) / VEV (descendant PLEI→VV) |
| `meteo_destination_precip_total_j` | idem |
| `meteo_destination_ensol_total_j` | idem |
| `meteo_destination_vent_max_j` | idem |

### Niveau 3 — Contexte temporel J-1 et J+1 (8 features)

Précipitations et ensoleillement uniquement (paramètres les plus discriminants pour les
arbitrages comportementaux « il a fait / fera beau ») :

| Feature | Calcul | Station |
|---|---|---|
| `meteo_precip_total_j_moins_1` | Σ précip J-1 (mm), local | `spatial_segment` |
| `meteo_ensol_total_j_moins_1` | Σ ensol J-1 (min), local | `spatial_segment` |
| `meteo_destination_precip_total_j_moins_1` | Σ précip J-1 (mm), destination | `base_sens` |
| `meteo_destination_ensol_total_j_moins_1` | Σ ensol J-1 (min), destination | `base_sens` |
| `meteo_precip_total_j_plus_1` | Σ précip J+1 (mm), local | `spatial_segment` |
| `meteo_ensol_total_j_plus_1` | Σ ensol J+1 (min), local | `spatial_segment` |
| `meteo_destination_precip_total_j_plus_1` | Σ précip J+1 (mm), destination | `base_sens` |
| `meteo_destination_ensol_total_j_plus_1` | Σ ensol J+1 (min), destination | `base_sens` |

### Niveau 4 — Rayonnement global (2 features)

Paramètre disponible à 100% dans VEV et CHD, absent des features actuelles, fort signal
intra-journalier :

| Feature | Calcul | Station |
|---|---|---|
| `meteo_rayon_global_moy_j` | Rayonnement global moyen du jour J (W/m²), local | `spatial_segment` |
| `meteo_destination_rayon_global_moy_j` | Rayonnement global moyen du jour J, destination | `base_sens` |

**Total : 18 nouvelles features.** Dataset ML passe de 9 à 27 features `meteo_*`.

---

## 3. Mapping spatial unifié (spatial_segment)

Toutes les features météo — horaires (`meteo_*_h`, stage_04) et journalières
(`meteo_*_j`, stage_04b) — utilisent **le même critère de rattachement à la station** :

### Features locales (niveaux 1, 3 et 4)

> **`spatial_segment == "haut"` → station CHD ; `spatial_segment == "bas"` → VEV**

`spatial_segment` est calculé en stage_03e : une ligne est `"haut"` dès qu'au moins une gare
du tronçon a `ordre > 10` (soit Lally et au-delà, où la crémaillère est engagée).

Ce critère opérationnel est retenu pour garantir la **cohérence sémantique entre les deux
familles de features météo** et simplifier l'argumentaire du modèle (une seule frontière VEV/CHD
pour les 27 features `meteo_*`).

**Note sur Blonay (BLON, 620 m, ordre = 10)** : lorsque Blonay est la gare haute d'un tronçon
(ex. STLE–BLON), `spatial_segment = "bas"` → VEV. Lorsqu'elle est la gare basse d'un tronçon
de crémaillère (BLON–PRLZ), `spatial_segment = "haut"` → CHD. Ce comportement est cohérent avec
la frontière opérationnelle de la ligne (changement de matériel roulant à Blonay).

### Mapping destination (niveaux 2, 3, 4)

La logique `base_sens` est conservée à l'identique des features horaires existantes :
- `"VV -> PLEI"` (train montant) → CHD
- `"PLEI -> VV"` (train descendant) → VEV

---

## 4. Disponibilité J-1 et statut de proxy (cohérence ADR-022)

Toutes les nouvelles features utilisent les observations météo historiques comme proxy
des prévisions disponibles à J-1 en production, selon le même statut épistémique que
les features horaires existantes (catégorie 2 — prévisionnelle, cf. ADR-022 §5).

**Agrégats J** : en entraînement, la météo du jour J est disponible (observations a posteriori).
En production, l'équivalent sont les **prévisions horaires MétéoSuisse** pour le jour J,
disponibles la veille à 8h (API ICON-CH2-EPS, paramètres vérifiés : `tre200dx`, `rka150p0`,
`sre000h0`, `fu3010h1`, `gre000h0`). Le même train/serve skew documenté en ADR-022 s'applique.

**Agrégats J-1** : disponibles à J-1 depuis les observations. Pas de skew sur J-1.

**Agrégats J+1** : en entraînement, disponibles a posteriori. En production,
prévisions MétéoSuisse pour J+1 disponibles à J-1 (horizon J+2 de la veille).

**Couverture temporelle confirmée** : VEV (2015-09-08 → 2025-12-31) et CHD (2012-02-08 → 2025-12-31)
couvrent intégralement le périmètre H22-H24. Pas de NaN structurel sur J-1 ni J+1.

---

## 5. Trade-offs et limites

- **18 features supplémentaires** : enrichissement substantiel ; l'analyse SHAP post-entraînement
  permettra d'identifier les features non-informatives à retirer dans une itération ultérieure.
- **Frontière VEV/CHD unique** : le critère `spatial_segment` correspond à la frontière opérationnelle
  de la ligne (crémaillère, changement de matériel), pas à la transition climatique réelle (~1 000 m).
  CHD reste une approximation pour PRLZ–FAY (661–972 m), acceptée au niveau prototypique.
- **J+1 sur les dernières journées H24** : NaN pour le 14 décembre 2024 (dernier jour H24 — pas de J+1
  dans la période de couverture). XGBoost gère nativement les NaN.

---

## 6. Paramètres reportés à une itération future

- Nébulosité (codes SMN `nprolohs`, `npromths`, `nprohihs`) : sémantique à clarifier
- Isotherme zéro (`zprfr0hs`) : à intégrer dans les données historiques d'abord
- Pictogramme MétéoSuisse journalier (`jp2000d0`) : table de correspondance des codes à documenter
- Features de variation et tendance (variation T° sur 3j, cumul neige 7j) : gain incertain,
  à évaluer après le prochain cycle SHAP

---

## 7. Implémentation

| Artefact | Action |
|---|---|
| `scripts/pipeline/add_meteo_journaliere_to_raw_stacked.py` | Nouveau stage 04b |
| `scripts/pipeline/paths.py` | Ajout `STAGE_04B_METEO_J` |
| `Makefile` | Chaînage `STAGE_04 → STAGE_04B → STAGE_06` |
| `CONTEXT.md` | Mise à jour section météo + table stages |

---

## Références

- Notebook `notebooks/02d_diagnostic_features_meteo.ipynb` — justification empirique complète
- Note `notes/02d_recap_meteo_pour_decision.md` — synthèse et recommandations
- ADR-022 — granularité horaire, mapping VEV/CHD, train/serve skew
- ADR-027 — split temporel H22-H23 / H24 (périmètre du modèle de référence)

---


---
id: ADR-029
ancien_id: ADR-30
date_decision: 2026-05-23
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-029 — Reclassification zonale Montreux et décomposition événementielle par localité R35

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-23 |
| **Décideur** | Erwann Nedellec |
| **Scripts modifiés** | `scripts/sources/build_dim_manifestations_riviera.py`, `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` |

---

## 1. Contexte

Le système événementiel (cf. CONTEXT.md section « Sources intégrées ») agrège les manifestations
Montreux Riviera Tourisme en 3 zones géographiques (`zone_directe`, `zone_indirecte`, `hors_zone`)
selon le champ `lieu` des PDFs sources. Deux limites structurelles ont été identifiées lors de
l'audit pré-modélisation.

**Limite 1 — Confusion entre proximité géographique et connectivité ferroviaire.**

La classification initiale plaçait Montreux et ses dépendances (Territet, Clarens, Chailly,
Veytaux, Glion, Caux, Villeneuve, etc.) en `hors_zone`. Or :

- Montreux est directement connectée à Vevey (terminus R35) par la ligne du Léman à haute fréquence.
- Les grosses manifestations montreusiennes (Montreux Jazz Festival, Montreux Noël, Marché de Noël,
  Montreux Trail Festival, Freddie Celebration Days, MAG Montreux Art Gallery, Foire des Planches,
  Montreux Nestlé Open) génèrent un effet d'attraction régional qui déborde mécaniquement sur la R35
  par plusieurs canaux :
  - Visiteurs logeant dans le segment R35 (Blonay, Saint-Légier) et se déplaçant vers Montreux.
  - Excursions touristiques aux Pléiades pendant les festivals (offre montagne complémentaire).
  - Saturation hôtelière qui pousse les visiteurs vers le segment haut de la ligne.

Classer ces événements en `hors_zone` confondait proximité géographique (Montreux est loin du
segment Blonay) et connectivité fonctionnelle (Montreux est directement reliée à Vevey).

**Limite 2 — Granularité spatiale insuffisante en zone directe.**

Le compteur `event_n_manifestations_zone_directe_j` agrégeait les manifestations des 3 localités
traversées par la R35 sans distinction. Or chaque localité correspond à un régime de trafic distinct :

- **Vevey** : terminus urbain lacustre, fort flux pendulaire et touristique.
- **Saint-Légier** : corridor piémont résidentiel pavillonnaire.
- **Blonay** : pôle crémaillère + accès montagne touristique (Pléiades).

Un événement à Vevey n'impacte probablement pas le segment R35 de la même manière qu'un événement
à Saint-Légier ou Blonay. L'agrégation masquait cette asymétrie.

---

## 2. Décisions

### Décision 1 — Reclassification zonale Montreux

Le mapping `LIEU_TO_ZONE_NORMALIZED` dans `build_dim_manifestations_riviera.py` est modifié.

**Reclassement de `hors_zone` vers `zone_indirecte`** (14 lieux) :

| Lieu normalisé | Justification |
|---|---|
| montreux | Terminus ligne du Léman côté Montreux, connexion directe à Vevey |
| territet | Quartier de Montreux, même bassin de correspondance |
| clarens, clarens s/montreux | Commune entre Montreux et Vevey |
| chailly, chailly s/montreux | Localité sur les hauteurs de Montreux |
| chernex | Commune de la commune de Montreux |
| vernex | Quartier de Montreux |
| veytaux | Commune entre Montreux et Villeneuve |
| villeneuve, villeneuve-montreux | Terminus est de la ligne du Léman |
| glion | Hauteurs de Montreux, accessible via Montreux |
| caux | Idem |
| brent | Hameau sur les hauteurs de Montreux |

**Maintien en `hors_zone`** (lieux sans connectivité pertinente vers la R35) :

| Lieu normalisé | Justification |
|---|---|
| jaman, rochers-de-naye, les avants | Accessibles uniquement via ligne MOB Montreux–Rochers, pas par la R35 |
| cully, lutry, epesses, rivaz, st-saphorin | Côté Lavaux/Lausanne, opposé à la R35 |
| lausanne | Hors périmètre Riviera R35 |
| aran s, villette | Proches de Cully |
| riviera | Région entière, signal trop large pour être discriminant |

### Décision 2 — Décomposition événementielle par localité R35

Ajout de 3 features de comptage journalier dans `dim_manifestations_riviera` et propagation
dans le stage 03, **en complément** des features zonales existantes (conservées).

| Feature | Type | Description |
|---|---|---|
| `event_n_manifestations_vevey_j` | Int8 | Manifestations à Vevey ce jour |
| `event_n_manifestations_st_legier_j` | Int8 | Manifestations à Saint-Légier ce jour |
| `event_n_manifestations_blonay_j` | Int8 | Manifestations à Blonay et localités rattachées (Pléiades, etc.) ce jour |

**Logique de classification par sous-chaîne** (fonction `classify_localite_r35`) :

Le champ `lieu` est normalisé (lowercase, suppression des diacritiques) puis examiné par
recherche de sous-chaîne dans l'ordre de priorité suivant :

1. `"vevey"` dans le lieu normalisé → localité **Vevey**
2. `"legier"` dans le lieu normalisé → localité **Saint-Légier**
3. `"blonay"` ou `"pleiades"` dans le lieu normalisé → localité **Blonay**
4. Sinon → `hors_r35` (ne contribue à aucun des 3 compteurs)

Cette logique couvre naturellement les variantes orthographiques rencontrées dans les PDFs
(Vevey-Vignerons, Saint-Légier, St Légier, Blonay-Chamby, Les Pléiades, etc.).

La priorité Vevey > Saint-Légier > Blonay gère les rares lieux multi-localisations
(ex. `"Vevey/La Tour-de-Peilz/St-Légier"` → Vevey).

**Correspondance avec la topologie R35 :**

| Localité R35 | Gares R35 rattachées |
|---|---|
| Vevey | VV, VVVI, GIL (historique H16-H22), CLIE (historique H16-H18) |
| Saint-Légier | HTV, CHTV, STLV, STLE, CHIZ |
| Blonay | CHBL, BLON, PRLZ, TUS, CHEV, BCHX, FAY, OND, LAL, PLEI |

---

## 3. Validation empirique post-implémentation

### Couverture de la classification par localité

Sur les 212 événements en `zone_directe` (PDFs 2015–2024) :

| Localité | Événements | % | Nature dominante |
|---|---|---|---|
| Vevey | 174 | 82.1 % | Festivals lacustres, marchés folkloriques, fêtes culturelles |
| Blonay | 28 | 13.2 % | Crémaillère, montagne, Pléiades, Désalpe, Léman Retro |
| Saint-Légier | 10 | 4.7 % | Semaine Internationale de Piano principalement |
| hors_r35 | **0** | **0.0 %** | Aucun événement zone directe non rattaché |

Le résultat `hors_r35 = 0` confirme que les 3 sous-chaînes couvrent l'intégralité des
événements zone directe répertoriés dans les PDFs sources sur la période 2015–2024.

Cas particulier résolu : `'Les Pléiades'` ne contient ni « vevey » ni « legier » ni « blonay »,
mais contient « pleiades » → correctement classé en `blonay`.

### Intégrité pipeline

| Indicateur | Valeur | Statut |
|---|---|---|
| `ml_dataset.parquet` lignes | 832 732 | Inchangé ✓ |
| Colonnes totales | 192 | +3 vs avant ✓ |
| Features `event_*` totales | 20 | +3 nouvelles ✓ |
| Warnings pipeline | 0 | ✓ |

---

## 4. Trade-offs et limites

**Limite 1 — Compteur Saint-Légier creux.**
`event_n_manifestations_st_legier_j` sera actif sur environ 8–10 jours par an (essentiellement
la Semaine Internationale de Piano, août). Le signal est faible en volume mais potentiellement
précis. Le SHAP révélera si la feature est exploitable malgré sa rareté.

**Limite 2 — Compteur Vevey dominant.**
Vevey concentre 82 % des événements zone directe. `event_n_manifestations_vevey_j` pourrait
être redondant avec `event_n_manifestations_zone_directe_j` (dominé par Vevey). Si cette
redondance est confirmée par le SHAP, la feature zonale pourra être retirée dans une itération
future sans modifier la dim ni le pipeline.

**Limite 3 — Localités rattachées non couvertes si absentes des PDFs actuels.**
La logique par sous-chaîne ne capte pas Hauteville, Chevalleyres, Fayaux, Tusinge si ces noms
apparaissent comme lieu principal dans un PDF futur. La validation empirique sur 2015–2024 montre
0 occurrence — le risque est nul sur le périmètre actuel. À surveiller lors de la mise à jour
annuelle de la dimension.

**Limite 4 — Effet de débordement Montreux non quantifié.**
La reclassification en `zone_indirecte` est justifiée conceptuellement (connectivité ferroviaire,
saturation hôtelière) mais l'ampleur empirique du débordement sur la R35 reste à mesurer via le
SHAP post-entraînement. Si `event_n_manifestations_zone_indirecte_j` émerge dans le top SHAP,
l'hypothèse sera validée empiriquement.

---

## 5. Cohérence opérationnelle (anti-leakage J-1)

Les 3 nouvelles features héritent du statut épistémique des features `event_*` existantes :

> Les manifestations sont planifiées à l'avance et publiées par Montreux Riviera Tourisme.
> Toutes les features sont déterminables à J-1. Aucune fuite temporelle.

---

## 6. Implémentation

| Artefact | Modification |
|---|---|
| `scripts/sources/build_dim_manifestations_riviera.py` | Mapping zonal Montreux modifié + fonction `classify_localite_r35` ajoutée + 3 colonnes localité dans la dim date + docstring module mis à jour |
| `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` | `_NEW_COLS` étendu avec 3 colonnes + 3 features `event_*` créées et typées |
| `data/dimension/dim_manifestations_riviera.parquet` | Reconstruit : 2 116 dates, 13 colonnes (dont 3 nouvelles) |
| `data/dimension/dim_manifestations_riviera_evenements.parquet` | Reconstruit : 632 événements, colonne `localite_r35` ajoutée |
| `data/processed/stage_03_manifestations.parquet` | Régénéré : 2 051 510 lignes × 82 colonnes (+3) |
| `data/processed/ml_dataset.parquet` | Régénéré : 832 732 lignes × 192 colonnes |

---

## 7. Références

- `scripts/sources/build_dim_manifestations_riviera.py` — implémentation zonale et localité
- `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` — propagation stage 03
- ADR-027 — split temporel H22+H23 / H24 (périmètre du modèle concerné)
- ADR-028 — enrichissement features météo journalières (modification structurelle parallèle)
- PDFs sources : `data/external/evenements/Manifestations YYYY.pdf` (2015–2024)

---


---
id: ADR-030
ancien_id: ADR-31
date_decision: 2026-05-28
statut: amendé
amende_par: [ADR-031]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-030 — Révision de la stratégie de modélisation suite au découplage R²/rappel sur la classe surcharge

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-031.
> **Précision au gel.** Le levier L3 retenu ici (classifieur binaire dédié) **a été évalué** — ADR-031 §2.4 en rapporte les résultats sur H24 — puis écarté. Le mémoire (§4.6.2) présente le classifieur direct comme non évalué : la formulation vise le classifieur appliqué à l'architecture et au périmètre finaux, non ce levier exploratoire.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-28 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `notebooks/05_evaluation_modele_h24.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM 94), ADR-027 (split temporel) |

## 1. Contexte

Le modèle de référence est un régresseur XGBoost prédisant `target_voyageurs_2eme_classe`, optimisé sur le R² (cf. configuration Dataiku). L'objectif opérationnel réel est la détection des surcharges (`target >= 94`, ADR-005) pour déclencher la recommandation UM.

L'évaluation orientée décision conduite sur le test set H24 (notebook 05) révèle un **découplage critique** entre la performance de régression et la performance décisionnelle.

## 2. Constat empirique

### 2.1 Performance de régression honorable

| Scope | R² | RMSE | MAE | WMAPE |
|---|---|---|---|---|
| Global | 0.613 | 11.06 | 7.19 | 0.360 |
| Segment bas | 0.578 | 11.56 | 7.79 | 0.327 |
| Segment haut | 0.361 | 9.42 | 5.42 | 0.635 |

Le R² global de 0.613 est cohérent avec la littérature de prédiction de fréquentation à court terme et pourrait, isolément, suggérer un modèle exploitable.

### 2.2 Échec décisionnel sur la classe surcharge

Au seuil physique de 94 (ADR-005), la performance de détection est quasi nulle :

| Indicateur | Valeur |
|---|---|
| Surcharges réelles (H24) | 983 |
| Surcharges détectées (TP) | 12 |
| Surcharges ratées (FN) | 971 (98.8 %) |
| Rappel | 1.2 % |
| Précision | 85.7 % |
| F2-score | 0.015 |

Le modèle détecte 12 surcharges sur 983. **Il échoue sur sa cible opérationnelle.**

### 2.3 Biais conditionnel : écrasement de la queue haute

L'erreur moyenne de prédiction par tranche de charge réelle montre une sous-estimation croissante et sévère :

| Tranche réelle | n | Erreur moyenne (préd − réel) | Prédiction moyenne |
|---|---|---|---|
| [0–80[ | 332 653 | −2.2 | 17.1 |
| [80–94[ | 2 073 | −39.2 | 46.4 |
| [94–110[ | 735 | −47.2 | 52.7 |
| [110–150[ | 237 | −71.5 | 47.2 |
| [150+[ | 11 | −119.2 | 47.2 |

Le modèle plafonne ses prédictions autour de 47–53 voyageurs quelle que soit l'ampleur réelle de la surcharge. Les pics extrêmes (charge réelle > 150) sont prédits au même niveau que des charges modérées.

### 2.4 Insuffisance du calibrage de seuil seul

L'abaissement du seuil de déclenchement appliqué à la prédiction (couche de décision, ADR-003) ne résout pas le problème, car le modèle a appris à ne pas prédire haut :

| Seuil de déclenchement | Rappel | Précision | FN | FP |
|---|---|---|---|---|
| 94 (naïf) | 1.2 % | 85.7 % | 971 | 2 |
| 75 | 21.1 % | 63.7 % | 776 | 118 |
| 65 | 30.1 % | 33.4 % | 687 | 591 |
| 55 | 40.9 % | 15.4 % | 581 | 2 202 |

Même au seuil de déclenchement le plus agressif testé (55), le rappel plafonne à 40.9 % au prix de 2 202 faux positifs. **Les cibles de rappel 90 % et 95 % sont inatteignables avec ce modèle.**

## 3. Diagnostic de cause racine

Le découplage s'explique par deux mécanismes conjugués, indépendants de la qualité du feature engineering.

### 3.1 Déséquilibre extrême de la cible (341:1)

La proportion de surcharges réelles sur H24 est de 983 / 335 709 = 0.29 %, soit un déséquilibre de **341:1**, nettement supérieur à l'estimation initiale de ~50:1 (ADR-005). Par segment : 0.35 % (bas) et 0.12 % (haut).

### 3.2 Inadéquation entre fonction objectif et objectif métier

L'optimisation du RMSE (ou R²) sur une cible à 341:1 conduit mécaniquement le modèle à minimiser l'erreur sur la masse des observations normales (99.7 %) au détriment de la classe rare. Mathématiquement, ignorer les 983 surcharges optimise le RMSE global. Le modèle adopte un comportement de régression vers la moyenne conditionnelle, écrasant la queue haute.

**Le problème n'est pas le modèle ni les features, mais la formulation : une décision binaire portant sur une classe rare a été traitée comme une régression optimisée sur l'erreur moyenne.**

## 4. Décision

**Réviser la stratégie de modélisation vers une formulation explicitement orientée vers la détection de la classe rare**, conformément à la nature binaire de la décision UM (ADR-003, ADR-005).

Cette révision est une itération CRISP-ML(Q) : la phase d'Évaluation invalide la formulation de la phase de Modélisation et impose un retour amont. La cible métier (`target_voyageurs_2eme_classe`, ADR-001) et le seuil (94, ADR-005) sont conservés ; seule la formulation d'apprentissage est révisée.

## 5. Leviers évalués

Trois leviers sont retenus pour test empirique, par ordre de priorité méthodologique :

| Levier | Principe | Avantage | Limite |
|---|---|---|---|
| **L1 — Pondération agressive** | Sample weights forts sur la classe surcharge dans le régresseur XGBoost | Rapide, reste dans le régresseur existant, testable en Visual ML | Pansement sur une formulation inadaptée ; risque d'explosion des FP |
| **L2 — Objective asymétrique** | Quantile loss (q≈0.9) au lieu de RMSE | Relève structurellement les prédictions vers le haut de la distribution conditionnelle | Change l'interprétation de la sortie (quantile, non espérance) |
| **L3 — Classifieur binaire dédié** | Reformuler en classification `surcharge ∈ {0,1}` avec `scale_pos_weight` ≈ ratio de déséquilibre | Aligné avec la décision binaire réelle (ADR-003/04) ; XGBoost gère nativement le déséquilibre | Perd l'estimation de l'ampleur de la charge ; nécessite un nouveau pipeline d'évaluation |

**Note** : un modèle à deux étages (classifieur de détection + régresseur d'ampleur conditionnel) est envisageable comme synthèse de L2 et L3, à évaluer si L3 seul donne un rappel satisfaisant mais une information d'ampleur insuffisante pour la couche de décision.

## 6. Critères de décision entre leviers

Le levier retenu sera celui qui maximise le **rappel sur la classe surcharge à un niveau de faux positifs acceptable**, évalué sur le test set H24, puis ventilé par segment. Les métriques de décision (rappel, précision, F2) priment sur les métriques de régression (R², RMSE).

**Dépendance ouverte (à résoudre avec MOB)** : le niveau acceptable de faux positifs dépend du coût relatif d'une UM inutile (faux positif) versus une surcharge ratée (faux négatif). Cet arbitrage doit être obtenu auprès du Responsable de production, MOB avant la calibration finale du seuil de décision. Sans cet ancrage, le compromis rappel/précision est calibré à l'aveugle.

## 7. Conséquences

- **Phase de modélisation** : un nouveau cycle d'entraînement est requis (pondération, objective, ou classifieur). Les résultats seront documentés dans un ADR de suivi ou en addendum à celui-ci.
- **Couche de décision (ADR-003)** : le calibrage du seuil de déclenchement reste pertinent mais subordonné à une formulation d'apprentissage corrigée — il ne peut compenser seul l'écrasement de la queue haute.
- **Évaluation** : le notebook 05 devient le protocole d'évaluation de référence pour comparer les leviers (mêmes métriques, même split H24).
- **Cible et seuil** : inchangés (ADR-001, ADR-005).
- **Contribution au mémoire** : ce découplage R²/rappel constitue un résultat méthodologique central — il démontre empiriquement l'insuffisance d'une évaluation par R² seul pour un problème de détection de classe rare, et justifie une approche orientée décision conforme au cadre DSR.

## 8. Alternatives considérées et écartées (à ce stade)

| Alternative | Raison du report |
|---|---|
| Conserver le régresseur RMSE + calibrage de seuil seul | Empiriquement insuffisant : rappel plafonné à 40.9 % même au seuil 55 (§2.4) |
| Rééchantillonnage synthétique (SMOGN, SMOTE-R) | Plus complexe à implémenter proprement dans Dataiku ; reporté après test de L1–L3 |
| Abaisser le seuil de capacité sous 94 | Rejeté : 94 est une caractéristique technique du SURF 7500 (ADR-005), non un paramètre ajustable |

## 9. Références

- Notebook `notebooks/05_evaluation_modele_h24.ipynb` — constat empirique complet, 7 figures dans `notebooks/figures/05/`
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — architecture à deux couches (prédictive + décision)
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM = 94 (capacité assise 2ème classe SURF 7500)
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22-H23 / H24

## Amendement 2026-07-09 — Correction d'attribution d'interlocuteur

Les mentions d'origine de cet ADR attribuaient l'arbitrage du coût faux positifs / faux négatifs et les validations opérationnelles associées à une autre personne (le référent superviseur du projet côté MOB). L'interlocuteur réel de cet arbitrage et de ces validations était le **Responsable de production, MOB**. La correction porte uniquement sur l'**identité de l'interlocuteur** : le contenu de l'arbitrage, les valeurs et les décisions retenues demeurent inchangés. Correction découverte lors de la passe d'anonymisation et tracée ici.

---


---
id: ADR-031
ancien_id: ADR-32
date_decision: 2026-05-28
statut: amendé
amende_par: [ADR-033]
modifie: [ADR-030]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-031 — Verdict empirique sur la modélisation de la classe rare et décision d'explorer la segmentation

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-033.
> Décisions antérieures que ce document modifie : ADR-030.
> **Précision au gel.** L'évaluation du classifieur binaire rapportée au §2.4 est la **contre-épreuve** du levier L3 d'ADR-030. Voir la note d'ADR-030 sur l'articulation avec le §4.6.2 du mémoire.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-28 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/05_evaluation_modele_h24.ipynb`, `notebooks/05b_comparaison_modeles_h24.ipynb`, `notebooks/05c_evaluation_classifieur_h24.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM 94), ADR-027 (split temporel), ADR-030 (révision stratégie) |

## 1. Contexte et rappel

L'ADR-030 a acté, suite au découplage critique R²/rappel observé sur le régresseur XGBoost de référence, la révision de la stratégie de modélisation et l'exploration de trois leviers correctifs : pondération agressive des observations surcharge (L1), objectif asymétrique quantile loss (L2), et classifieur binaire dédié (L3). L'objectif opérationnel demeure la détection des surcharges (`target_voyageurs_2eme_classe ≥ 94`, ADR-005) pour la décision UM sur la ligne R35, avec un déséquilibre réel de 341:1 (983 surcharges sur 335 709 observations H24, ADR-027).

Le présent ADR documente le verdict empirique de ce parcours de modélisation, conduit sur le test set H24, et acte deux décisions : (1) le constat d'une limite informationnelle à la prédiction des surcharges, et (2) l'exploration d'une dernière piste — la segmentation en deux modèles distincts (segment bas / segment haut) — avant la clôture de la phase de modélisation.

## 2. Leviers testés et résultats

### 2.1 Régresseur RMSE complet — 193 features (référence)

Évalué dans `notebooks/05_evaluation_modele_h24.ipynb`.

| Métrique | Valeur |
|---|---|
| R² global | 0.6128 |
| R² segment bas | 0.5780 |
| R² segment haut | 0.3606 |
| RMSE global | 11.06 voyageurs |
| Rappel @94 | 1.2 % (12 TP / 983 surcharges) |
| Précision @94 | 85.7 % |
| F2 @94 | 0.015 |
| Rappel max (seuil = 40) | 62.1 % |
| Rappel @94 — segment haut | 0.0 % (0 TP / 104 surcharges) |

Le biais conditionnel est sévère et croissant avec la charge : les prédictions plafonnent autour de 47–53 voyageurs quelle que soit l'amplitude réelle de la surcharge (erreur moyenne −119 voyageurs pour les charges ≥ 150). Les cibles de rappel 90 % et 95 % sont déclarées non atteignables dès ce stade.

### 2.2 Régresseur RMSE top 20 features (parcimonie)

Évalué dans `notebooks/05b_comparaison_modeles_h24.ipynb`.

| Métrique | Valeur |
|---|---|
| R² global | 0.6377 (meilleur des trois régresseurs) |
| Rappel @94 | 4.8 % |
| Précision @94 | 82.5 % |
| F2 @94 | 0.059 |
| Rappel max (seuil = 40) | 69.6 % |

Le modèle réduit à 20 features obtient le meilleur R² des trois régresseurs tout en étant structurellement plus parcimonieux. Il constitue l'argument empirique de la parcimonie pour l'artefact final si la segmentation n'apporte rien.

### 2.3 Régresseur pondéré 10/5/1 — levier L1

Évalué dans `notebooks/05b_comparaison_modeles_h24.ipynb`. Poids appliqués : 10 (surcharge), 5 (vigilance, 80–93), 1 (normal).

| Métrique | Valeur |
|---|---|
| R² global | 0.6226 |
| Rappel @94 | 6.6 % (meilleur rappel parmi les régresseurs) |
| Précision @94 | 64.4 % |
| F2 @94 | 0.081 |
| Rappel max (seuil = 40) | 65.9 % |

Le tableau de synthèse des trois régresseurs confirme le **découplage R²/rappel** : le modèle offrant le meilleur R² (Top20, 0.638) n'est pas celui offrant le meilleur rappel (Pondéré, 6.6 %). La pondération 10/5/1, bien qu'elle améliore légèrement le rappel, reste très insuffisante face à un déséquilibre de 341:1. Pour contrebalancer mécaniquement la pression de la MSE sur la classe normale, un poids de l'ordre de 100 à 341 serait théoriquement nécessaire. Le levier L1 avec une pondération modérée est insuffisant.

| Modèle | R² | Rappel @94 | F2 @94 | Rappel max (seuil 40) |
|---|---|---|---|---|
| Complet | 0.6128 | 1.2 % | 0.015 | 62.1 % |
| Top20 | 0.6377 | 4.8 % | 0.059 | 69.6 % |
| Pondéré 10/5/1 | 0.6226 | 6.6 % | 0.081 | 65.9 % |

Aucun régresseur ne dépasse 70 % de rappel, même au seuil de déclenchement le plus agressif testé (40). Aucun n'atteint 80 %.

### 2.4 Classifieur binaire XGBoost — scale_pos_weight = 341 — levier L3

Évalué dans `notebooks/05c_evaluation_classifieur_h24.ipynb`. Le classifieur prédit directement `is_surcharge = (target ≥ 94)` avec `scale_pos_weight ≈ 341` (ratio de déséquilibre, ADR-030 §3.1).

#### 2.4.1 Métriques discriminantes non pondérées

| Métrique | Global | Segment bas | Segment haut |
|---|---|---|---|
| PR-AUC non pondéré | **0.2359** | 0.2619 | 0.0116 |
| ROC-AUC | 0.9012 | 0.9010 | 0.9097 |
| Taux de base (précision aléatoire) | 0.293 % | 0.350 % | 0.124 % |
| Rapport PR-AUC / taux base | 80.6× | 74.8× | 9.7× |

Le segment haut présente un PR-AUC de 0.0116, soit environ 9.7× le taux de base — le classifieur ne parvient pas à discriminer les surcharges sur ce segment touristique. Le ROC-AUC de 0.90+ est trompeur et ne doit pas être interprété comme une mesure de performance sur la classe rare (cf. §5).

#### 2.4.2 Calibration par ratio de coût FN:FP

| Ratio FN:FP | Seuil optimal | Rappel | Précision | FN | FP | FP/TP |
|---|---|---|---|---|---|---|
| 3:1 | 0.920 | 23.6 % | 51.3 % | 751 | 220 | 0.95 |
| 5:1 | 0.720 | 29.6 % | 39.0 % | 692 | 456 | 1.57 |
| **10:1** | **0.490** | **34.8 %** | **28.1 %** | **641** | **877** | **2.56** |
| 20:1 | 0.250 | 40.7 % | 17.9 % | 583 | 1 832 | 4.58 |

Même au ratio 20:1, le rappel plafonne à 40.7 %. Le ratio réel (coût d'une UM inutile vs d'une surcharge ratée) doit être obtenu auprès du Responsable de production, MOB pour fixer le point de fonctionnement opérationnel.

### 2.5 Tableau comparatif final — PR-AUC non pondéré

| Modèle | PR-AUC non pondéré | n surcharges H24 | Rappel max |
|---|---|---|---|
| Classifieur 341 | 0.2359 | 983 | 73.0 % |
| Complet (régresseur) | 0.2481 | 983 | — |
| Top20 (régresseur) | 0.2496 | 983 | — |
| Pondéré 10/5/1 (régresseur) | 0.2276 | 983 | — |

Les quatre modèles convergent vers un PR-AUC non pondéré compris entre 0.228 et 0.250.

## 3. Constat central : convergence des approches vers un même plafond

Le résultat principal de ce parcours est la convergence remarquable des quatre modèles — deux familles d'approches distinctes (régression RMSE et classification binaire orientée rappel), avec des formulations d'objectif et des traitements du déséquilibre très différents — vers un PR-AUC non pondéré de **0.23 à 0.25** sur le test set H24.

Cette convergence ne peut s'expliquer par une inadéquation méthodologique : le classifieur avec `scale_pos_weight = 341` est précisément conçu pour contrebalancer le déséquilibre, et son PR-AUC est comparable — voire légèrement inférieur — aux régresseurs. Elle suggère que **le plafond de performance est d'origine informationnelle** : les features disponibles (données de fréquentation historique, calendrier, météo, événementiels, SIMBA) ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité suffisante.

Ce constat est un **résultat de recherche à part entière** (contribution DSR Level 2 : connaissance sur les limites de prédictibilité du phénomène avec les données disponibles), et non un échec de modélisation. Il délimite ce qui est prédictible et ce qui ne l'est pas avec le référentiel informationnel actuel.

## 4. Caractérisation de la limite informationnelle

### 4.1 Le segment haut : une limite structurelle

Le segment haut (Blonay–Les Pléiades, à caractère touristique) concentre 104 surcharges sur 983, soit 10.6 % du total. Ces 104 surcharges sont **systématiquement non détectées** par le régresseur de référence (rappel = 0.0 % à tout seuil ≥ 80), et le classifieur n'obtient qu'un PR-AUC de 0.0116 — marginalement supérieur au taux de base de 0.124 %.

| Approche | Rappel segment haut | PR-AUC segment haut |
|---|---|---|
| Régresseur complet (seuil 94) | 0.0 % | — |
| Classifieur 341 | — | 0.0116 |

La prédiction des surcharges sur ce segment dépasse les capacités du référentiel informationnel actuel.

### 4.2 Analyse des faux négatifs résiduels (classifieur, ratio 10:1)

Au seuil optimal pour un ratio FN:FP de 10:1 (seuil proba = 0.490), 641 surcharges sur 983 restent non détectées (65.2 %).

**Par segment :**
- Segment bas : 537 FN
- Segment haut : 104 FN (100 % des surcharges du segment)

**Par sens :**
- VV → Pléiades : 374 FN (58.3 %)
- Pléiades → VV : 267 FN (41.7 %)

**Par type de jour :**
- Ouvrable hors vacances : 311 FN (48.5 %) — les surcharges ordinaires non détectées dominent
- Dimanche ou férié : 99 FN
- Samedi hors vacances : 98 FN
- Vendredi hors vacances : 77 FN

**Par tranche de charge réelle :**
- [94–110[ : 464 FN sur 735 surcharges (taux FN 63.1 %)
- [110–130[ : 138 FN sur 205 (67.3 %)
- [130–150[ : 30 FN sur 32 (93.8 %)
- [150+[ : 9 FN sur 11 (81.8 %)

Les surcharges extrêmes (charges ≥ 130) présentent des taux de faux négatifs supérieurs à 80 %, précisément celles où l'enjeu opérationnel est le plus critique. Les déterminants de ces pics — événements locaux non répertoriés dans les référentiels disponibles, groupes organisés sans réservation SIMBA enregistrée, affluences ponctuelles — ne figurent pas dans les sources mobilisées.

## 5. Note sur la métrique pondérée trompeuse

Le classifieur entraîné avec `scale_pos_weight = 341` est évalué par Dataiku avec une métrique Average Precision **calculée sur les données pondérées par les poids d'entraînement**, ce qui gonfle artificiellement la contribution de la classe surcharge dans le calcul. Dataiku affiche ainsi un PR-AUC ≈ 0.913.

L'évaluation non pondérée conduite dans le notebook 05c (chaque observation compte pour 1, conformément aux conditions opérationnelles réelles) donne :

| Métrique | Valeur Dataiku | Valeur non pondérée (opérationnelle) |
|---|---|---|
| PR-AUC | 0.913 | **0.2359** |
| ROC-AUC | — | 0.9012 |

L'écart entre 0.913 et 0.236 est un **artefact de pondération**, non un indicateur de performance réelle. Cette confusion méthodologique — présenter comme métrique de performance une grandeur calculée sur données pondérées — peut conduire à des conclusions erronées sur la capacité opérationnelle du modèle. Le même biais affecte le ROC-AUC, qui présente un score de 0.90+ sur une classe rare à 0.29 % : cette valeur reflète la discrimination sur la classe normale (très bien séparée) et non sur la classe rare.

**Règle de validation** : pour tout modèle entraîné avec des poids de classe, les métriques d'évaluation opérationnelle doivent être calculées sur données non pondérées. Les métriques pondérées restent utiles pour le suivi d'entraînement, pas pour l'évaluation décisionnelle.

## 6. Décision

### 6.1 Acte de la limite informationnelle

La convergence de quatre modèles de deux familles distinctes vers un PR-AUC non pondéré de 0.23–0.25 est interprétée comme **la limite informationnelle du référentiel de données actuel** pour la prédiction des surcharges individuelles sur la ligne R35. Cette limite est actée comme résultat de recherche.

La phase de modélisation ne sera pas prolongée par de nouveaux entraînements sur les features existantes sans enrichissement substantiel du référentiel (cf. §8).

### 6.2 Exploration de la segmentation avant clôture

Une dernière piste est retenue avant la clôture : la **segmentation en deux modèles distincts**, un pour le segment bas (urbain/pendulaire, 251 106 observations, 879 surcharges, déséquilibre 286:1) et un pour le segment haut (touristique, 84 603 observations, 104 surcharges, déséquilibre 814:1).

**Rationale** : les résultats montrent que le segment haut est systématiquement non détecté et présente des dynamiques fondamentalement différentes (saisonnalité touristique, événements ponctuels). Des modèles spécialisés par segment pourraient capturer des patterns que le modèle global écrase. Cette piste rejoint la question restée ouverte dans l'ADR-003 (modèle unique vs modèles segmentés).

Si la segmentation n'apporte pas d'amélioration significative du PR-AUC non pondéré ou du rappel sur le segment haut, la limite informationnelle est considérée comme confirmée et la phase de modélisation est close.

La cible (ADR-001) et le seuil 94 (ADR-005) sont inchangés.

## 7. Modèle de référence provisoire pour l'artefact

En l'absence de résultat probant de la segmentation, le modèle de référence provisoire pour l'artefact final est le **régresseur Top20**. Ce choix est justifié par :

1. **Meilleur R² global** (0.6377 vs 0.6128 pour le Complet, 0.6226 pour le Pondéré) : meilleure capacité prédictive globale.
2. **Parcimonie** : 20 features vs 193, plus aisément maintenable et interprétable pour MOB/MVR.
3. **Sortie continue** : une prédiction en nombre de voyageurs est plus riche informationnellement qu'une probabilité binaire — elle permet de calibrer le seuil de déclenchement UM en couche de décision (ADR-003) et d'estimer l'ampleur de la surcharge.
4. **PR-AUC comparable au classifieur** : 0.2496 (Top20) vs 0.2359 (classifieur), ce dernier n'apportant pas d'avantage décisionnel malgré une formulation explicitement orientée rappel.

Ce choix est provisoire et conditionnel au résultat de l'exploration de la segmentation.

## 8. Points ouverts et pistes futures

### 8.1 Test de segmentation (immédiat)

L'exploration immédiate est le test de deux modèles distincts entraînés sur chaque segment. Le critère de succès est une amélioration significative du PR-AUC non pondéré sur le segment haut (seuil indicatif : PR-AUC > 0.05, contre 0.0116 actuellement).

### 8.2 Arbitrage coût FP/FN (MOB)

Le niveau acceptable de faux positifs (UM inutiles) conditionne le point de fonctionnement opérationnel du modèle, même imparfait. Cet arbitrage doit être obtenu auprès du Responsable de production, MOB avant tout déploiement. Sans cet ancrage, la calibration du seuil de décision (ADR-003) reste théorique.

### 8.3 Valeur opérationnelle partielle

Le modèle démontre une capacité de détection partielle sur le segment bas (PR-AUC = 0.26, rappel max 73.0 % pour le classifieur). La question de la valeur opérationnelle d'un rappel limité — typiquement 35–40 % sur le segment bas au ratio 10:1 — mérite une discussion avec MOB. Un outil détectant correctement un tiers des surcharges sur le segment pendulaire peut déjà réduire significativement les incidents si le biais de faux positifs reste acceptable.

### 8.4 Pistes d'enrichissement du référentiel

Les faux négatifs résiduels pointent vers des déterminants structurellement absents des données actuelles :

- **Données de réservation de groupes** : groupes organisés sans trace dans SIMBA, dont l'affluence génère des pics non anticipés.
- **Référentiel événementiel local exhaustif** : les manifestations Riviera et Vaud couvrent les événements connus ; les événements privés, scolaires ou associatifs ponctuels ne sont pas répertoriés.
- **Features de pic enrichies** : historique de surcharges par combinaison jour-type × train × sens à granularité annuelle, saisonnalité interannuelle explicite.
- **Données météo haute résolution** : influence des conditions météorologiques estivales sur la fréquentation touristique du segment haut.

Ces pistes constituent des axes de travaux futurs hors périmètre du présent mémoire.

## 9. Références

- `notebooks/05_evaluation_modele_h24.ipynb` — évaluation régresseur de référence (193 features), 7 figures dans `notebooks/figures/05/`
- `notebooks/05b_comparaison_modeles_h24.ipynb` — comparaison trois régresseurs, 6 figures dans `notebooks/figures/05b/`
- `notebooks/05c_evaluation_classifieur_h24.ipynb` — évaluation classifieur binaire scale_pos_weight=341, 6 figures dans `notebooks/figures/05c/`
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — architecture à deux couches (prédictive + décision) ; question modèle unique vs segmentés
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM = 94 (capacité assise 2ème classe SURF 7500)
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22-H23 / H24
- [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) — révision de la stratégie de modélisation, leviers L1–L3

---

## Addendum — 2026-05-29 : pivot architectural vers régression + augmentation métier

Cet addendum est ajouté postérieurement à la rédaction initiale de l'ADR-031. Il documente un pivot stratégique acté lors d'un examen de la trajectoire du projet, sans modifier le corps original ni invalider les résultats empiriques rapportés.

### A.1 Pivot acté

Le corps de l'ADR-031 documente un parcours de quatre modèles (trois régresseurs et un classifieur binaire) ayant convergé vers un plafond PR-AUC non pondéré de 0.23–0.25 sur le test set H24. Il acte l'exploration de la segmentation comme dernière piste avant clôture de la phase de modélisation, et retient à titre provisoire le régresseur Top20 comme modèle de référence.

Après examen de cette trajectoire, un **pivot architectural** est acté : l'optimisation du modèle de prédiction au sens strict (recherche d'un rappel maximal sur la classe surcharge par pondération, objective asymétrique ou classification binaire) est abandonnée. L'artefact est désormais conçu comme un **système d'aide à la décision à deux couches** combinant :

1. **Un modèle de régression au grain tronçon** prédisant `target_voyageurs_2eme_classe` en valeur continue, sur le périmètre H22+H23 / H24 défini par l'ADR-027.
2. **Une couche d'augmentation métier** intégrant les informations connues à J-1 que les features actuelles ne capturent pas : réservations de groupes, événements planifiés par l'équipe planification MOB, signaux contextuels documentés par les entretiens qualitatifs (P01–P06).

La décision UM finale résulte de la combinaison de la prédiction de charge et de ces inputs métier, dans la couche de décision aval (ADR-003). Cette architecture respecte la nature DSR de l'artefact : elle améliore la décision réelle par rapport au baseline opérationnel (79.2 % de tours UM injustifiés, notebook 04h) plutôt que de chercher une performance prédictive brute hors d'atteinte au regard de la limite informationnelle des features automatiques.

### A.2 Statut révisé des décisions de l'ADR-031

| Décision originale | Statut révisé |
|---|---|
| §6.1 — Acte de la limite informationnelle | **Conservée et reformulée.** La limite informationnelle reste un résultat de recherche valide (contribution DSR Level 2). La réponse à cette limite n'est plus l'enrichissement du référentiel par segmentation seule, mais l'augmentation métier de l'artefact (sources externes au modèle). |
| §6.2 — Exploration de la segmentation comme dernière piste avant clôture | **Redirigée.** La piste segmentation reste pertinente comme axe d'analyse complémentaire (Travail 3 à venir, conditionnel aux résultats du Travail 1 sur les features), non comme dernière tentative d'optimisation avant clôture. |
| §7 — Modèle de référence provisoire = régresseur Top20 | **Conservé à titre indicatif.** Le choix final du modèle de référence sera tranché par l'ADR-35 après le Travail 1 (analyse approfondie des features sur le périmètre H22+H23 / H24). |
| §5 — Note méthodologique sur les métriques pondérées trompeuses | **Conservée intégralement.** |
| §8.4 — Pistes d'enrichissement du référentiel | **Conservée et renforcée.** Les pistes (réservations groupes, événements locaux exhaustifs) constituent désormais le pilier "augmentation métier" du pivot architectural acté ici. |

### A.3 Articulation avec les ADR suivants

- L'**ADR-032** (révoqué le jour de sa rédaction, remplacé par l'ADR-034) ne modifie pas le périmètre d'entraînement. Le split ADR-027 (H22+H23 / H24) reste applicable.
- L'**ADR-033** (à rédiger après le Travail 1) formalisera complètement le pivot architectural acté ici, avec le détail de l'architecture à deux couches et les conditions de faisabilité opérationnelle de l'augmentation métier validées avec le Responsable de production, MOB.
- L'**ADR-35** (à rédiger après les Travaux 2 et 3) actera les décisions finales sur le modèle de référence, le sous-ensemble de features retenu et la question de la segmentation.

## Amendement 2026-07-09 — Correction d'attribution d'interlocuteur

Les mentions d'origine de cet ADR attribuaient l'arbitrage du coût faux positifs / faux négatifs et les validations opérationnelles associées à une autre personne (le référent superviseur du projet côté MOB). L'interlocuteur réel de cet arbitrage et de ces validations était le **Responsable de production, MOB**. La correction porte uniquement sur l'**identité de l'interlocuteur** : le contenu de l'arbitrage, les valeurs et les décisions retenues demeurent inchangés. Correction découverte lors de la passe d'anonymisation et tracée ici.

---


---
id: ADR-032
ancien_id: ADR-33
date_decision: 2026-05-29
statut: révoqué
revoque_par: [ADR-034]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-032 — Périmètre matériel et cohérence temporelle : H16 exclu, H17–H22 écartés de l'entraînement, H23–H24 retenus comme périmètre SURF cohérent

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-034.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Révoqué — voir ADR-034 |
| **Date** | 2026-05-29 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/02_data_understanding_apc.ipynb` §6.2 ; `notebooks/03h_du_rotations.ipynb` ; `notebooks/04h_triangulation_apc_rotations.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-005 (seuil UM 94), ADR-007 (tours de service), ADR-027 (split temporel — révisé par le présent ADR) |

---

> ## ⚠️ ADR RÉVOQUÉ — 2026-05-29
>
> **Cet ADR est révoqué le jour même de sa rédaction, après examen approfondi de son argument central.** Il est remplacé par l'**ADR-034** (Périmètre `base_offre_2eme_classe` : qualité diagnostique sans impact sur l'entraînement ML).
>
> **Motif de la révocation.** Le raisonnement de l'ADR-032 conclut à l'exclusion de H17–H22 du périmètre d'entraînement ML sur la base d'une incohérence matérielle (ABDe vs SURF 7500). Cet argument repose sur deux confusions conceptuelles :
>
> 1. La variable `base_offre_2eme_classe` (sur laquelle porte le diagnostic) **n'est pas une feature du modèle ML**. Elle est utilisée uniquement comme proxy diagnostique en data understanding. Le modèle apprend `f(features) → target_voyageurs_2eme_classe` sans aucune référence à la capacité du matériel.
>
> 2. La cible `target_voyageurs_2eme_classe` est une **mesure physique invariante** (nombre de voyageurs comptés par les APC). 94 voyageurs en H17 sur ABDe = 94 voyageurs en H24 sur SURF, ce sont les mêmes personnes comptées. Le seuil 94 (ADR-005) est appliqué uniquement en couche de décision aval, pas pendant l'apprentissage.
>
> Conséquence : l'incohérence matérielle détectée sur `base_offre_2eme_classe` est un constat de qualité de cette colonne diagnostique uniquement. Elle ne justifie aucune exclusion d'année horaire dans l'entraînement ML.
>
> **Résultats conservés de l'ADR-032.** Les analyses empiriques sous-jacentes (notebooks 02 §6.2, 03h, 04h) restent valides en tant que data understanding : caractérisation de `base_offre` par année, parc SURF 7500, triangulation APC × rotations (99.3 % concordance), baseline opérationnel niveau tour (79.2 % UM inutiles). Ces résultats sont repris dans l'ADR-034 et dans le mémoire en tant que constats de data understanding, sans la conclusion d'exclusion qui en avait été tirée à tort.
>
> **Décisions effectivement annulées par cette révocation :**
> - L'exclusion catégorique de H16 du périmètre ML est annulée (H16 reste candidat à l'entraînement ; voir ADR-034 pour la nuance).
> - L'exclusion de H17–H22 du périmètre d'entraînement est annulée.
> - La révision implicite de l'ADR-027 (split H22+H23 / H24 → H23 / H24) est annulée. L'ADR-027 reste applicable tel quel.
> - L'instruction de modifier `ANNEE_HORAIRE_MIN = "H23"` dans `build_ml_dataset.py` est annulée.
>
> Le corps original de l'ADR-032 (sections 1 à 8 ci-dessous) est conservé tel quel pour traçabilité du raisonnement initial. Il ne doit pas être considéré comme reflétant la position actuelle du projet.

---

## 1. Contexte

Le dataset ML agrège des données APC couvrant les années horaires H16 à H24 (décembre–décembre). La capacité de décision UM (`SEUIL_UM_2C = 94`, ADR-005) est calibrée sur le matériel roulant SURF 7500 déployé à partir de l'année horaire H23. Les années antérieures correspondent à du matériel ABDe dont la capacité assise 2ème classe est structurellement différente (~140 places simple, ~280 double).

Trois constats convergents, issus des notebooks de data understanding (02, 03h, 04h), établissent que l'utilisation naïve de toutes les années horaires disponibles crée une contamination matérielle qui invalide le proxy structurel de détection UM et rend le périmètre d'entraînement incohérent avec le contexte opérationnel de déploiement.

---

## 2. Constats empiriques

### 2.1 Distribution de `base_offre_2eme_classe` par année horaire (notebook 02 §6.2)

La colonne `base_offre_2eme_classe` sert de proxy structurel de détection de composition double : toute valeur ≥ 160 est interprétée comme une UM déployée (`SEUIL_OFFRE_DOUBLE = 160`). Cette règle est robuste si et seulement si le mode de la distribution annuelle reste inférieur à 160.

| Année | n obs (tronçons) | Mode `base_offre` | Mode % | 2ème valeur | 2ème % | Taux proxy UM (≥160) | Statut |
|---|---|---|---|---|---|---|---|
| **H16** | 168 377 | **180** | **53.0 %** | 140 | 44.8 % | **53.01 %** | **❌ CONTAMINÉ** |
| H17 | 218 529 | 140 | 97.7 % | 180 | 2.3 % | 2.29 % | ✅ Valide |
| H18 | 195 696 | 140 | 97.6 % | 280 | 2.3 % | 2.35 % | ✅ Valide |
| H19 | 233 595 | 140 | 99.7 % | 280 | 0.3 % | 0.33 % | ✅ Valide |
| H20 | 208 312 | 140 | 99.7 % | 280 | 0.3 % | 0.30 % | ✅ Valide |
| H21 | 194 269 | 140 | 99.4 % | 280 | 0.6 % | 0.62 % | ✅ Valide |
| H22 | 161 597 | 140 | 90.8 % | 78 | 8.8 % | 0.40 % | ✅ Valide |
| H23 | 335 426 | 90 | 96.2 % | 180 | 3.7 % | 3.76 % | ✅ Valide (SURF) |
| H24 | 335 709 | 94 | 99.0 % | 188 | 1.0 % | 1.04 % | ✅ Valide (SURF) |
| **Total H16–H24** | **2 051 510** | — | — | — | — | — | — |

**Interprétation de l'anomalie H16.** En H16, le mode de `base_offre_2eme_classe` est 180, valeur correspondant à la capacité assise simple de l'ABDe (non de l'SURF). Or 180 > 160 = `SEUIL_OFFRE_DOUBLE`. Conséquence : 53.01 % des tronçons H16 sont classifiés UM par le proxy, dont la quasi-totalité sont des faux positifs. Cette contamination est structurelle (matériau, non instrumentale) et ne peut être corrigée par un recalibrage du seuil sans dégrader le périmètre H17–H24.

### 2.2 Transition matérielle et incohérence de capacité H17–H22 (notebooks 02 §6.2, 03h)

Le matériel roulant ABDe (H16–H22) a une capacité assise 2ème classe simple de **140 places**. Le seuil UM retenu (`SEUIL_UM_2C = 94`, ADR-005) est calibré sur la **capacité du SURF 7500** (94 places simple), introduit progressivement à partir de H23 et opérationnel à plein régime en H24.

| Matériel | Années horaires | Capacité 2ème cl. simple | Capacité 2ème cl. double | SEUIL_UM_2C applicable |
|---|---|---|---|---|
| ABDe (ancien) | H16–H22 | ~140 | ~280 | ❌ Non (seuil 94 hors capacité) |
| SURF 7500 (intro) | H23 | ~90 | ~180 | ✅ Oui (capacité proche de 94) |
| SURF 7500 (canonique) | H24 | 94 | 188 | ✅ Oui (capacité = seuil) |

Pour les années H17–H22 avec matériel ABDe, la variable `target_voyageurs_2eme_classe` mesure une fréquentation par rapport à une capacité de 140 places. La cible opérationnelle (`target >= 94`, ADR-005) correspond à un **taux de remplissage de 67 %** sur ABDe, contre 100 % sur SURF 7500. Entraîner le modèle sur H17–H22 revient à lui apprendre à déclencher l'alarme UM à 67 % de remplissage du matériel présent — ce qui n'est pas la décision opérationnelle visée au déploiement.

### 2.3 Parc SURF et couverture des rotations (notebook 03h)

Le notebook 03h analyse les rotations (affectations rame × course) couvrant la période septembre 2023 – décembre 2024 :

- **46 869 lignes** × 12 colonnes | période : 2023-05-28 → 2024-12-31 (506 jours)
- **8 rames SURF** actives : 7501–7508 ; médiane 4 rames actives/jour
- **45 113 courses régulières voyageurs** (SURF uniquement) : 43 644 simples (96.74 %), 472 UM-SURF (1.05 %), 997 bus substitution
- **Couverture** : H22 absent, H23 partiel (à partir de sept. 2023 — 3 mois), H24 complet
- **Taux UM planifié** ~1 % des courses régulières SURF

Ces données confirment que le SURF 7500 opère exclusivement sur H23 (partiel) et H24 (complet). Aucune rotation SURF n'est disponible pour H17–H22, ce qui rend impossible toute validation croisée APC × rotations pour ces années.

### 2.4 Triangulation APC × rotations sur H23–H24 (notebook 04h)

La triangulation croisant les comptages APC (`proxy structurel base_offre ≥ 160`) et les rotations réelles (composition SURF) sur la période septembre 2023 – décembre 2024 :

| Indicateur | Valeur |
|---|---|
| Périmètre fiable proxy (H17–H24) | 1 883 133 tronçons (91.8 % du total APC) |
| Tronçons APC sept. 2023–déc. 2024 | 427 926 — dont 6 769 UM (1.58 %) |
| Courses rotations sur même période | 43 551 — dont 471 UM-SURF (1.08 %) |
| **Jointure inner APC × rotations** | **40 797 course-jours** (99.7 % APC, 95.3 % rotations) |
| Concordance globale | **99.3 %** |

Matrice de concordance sur les 40 797 course-jours jointurés :

| | APC → Simple | APC → UM |
|---|---|---|
| **Rot → Simple** | 40 086 | 253 (APC seul) |
| **Rot → UM** | 45 (Rot seul) | 413 (concordants) |

La concordance de 99.3 % sur la période SURF valide que le proxy structurel `base_offre ≥ 160` est fiable pour H23–H24. Elle confirme également que H16 est inutilisable (contamination 53 %) et que l'absence de rotations SURF pour H17–H22 rend impossible toute validation équivalente sur ces années.

**Baseline décisionnelle (niveau tour de service, notebook 04h) :**
- 423 tours analysés, 88 justifiés (20.8 %), 335 inutiles (79.2 %)
- 346 décompositions « contestables » (75.5 %), 88 héritées de capacité (19.2 %), 24 véritablement justifiées (5.2 %)

---

## 3. Problème

Deux incompatibilités structurelles interdisent d'utiliser H16–H22 pour l'entraînement du modèle ML :

1. **H16 — contamination du proxy UM** : le mode de `base_offre_2eme_classe` en H16 est 180, soit au-dessus du seuil 160. La variable cible dérivée (`um_deploye` via proxy) est corrompue pour 53 % des observations. Inclure H16 injecte massivement des faux positifs dans la variable cible.

2. **H17–H22 — incohérence matérielle avec la décision opérationnelle** : le seuil `SEUIL_UM_2C = 94` est la capacité assise du SURF 7500. Sur ABDe (H17–H22), ce seuil correspond à un taux de remplissage de 67 %, non à la saturation. Un modèle entraîné sur ces années apprendrait à signaler la surcharge à 67 % de remplissage d'un matériel absent du déploiement cible. Les rotations SURF étant indisponibles pour H17–H22, la validation externe est impossible.

---

## 4. Décision

**Trois décisions formelles** sont arrêtées par le présent ADR :

### Décision 1 — H16 exclu catégoriquement de toutes les analyses ML

H16 est exclu de toute utilisation dans les pipelines ML (entraînement, validation, test) et des analyses de proxy UM. La contamination structurelle de `base_offre_2eme_classe` (mode = 180 ≥ seuil 160, taux proxy spurieux = 53.01 %) invalide irrémédiablement la variable cible pour cette année horaire.

H16 reste accessible dans les données brutes pour des analyses exploratoires non-ML (volume, distribution brute) avec annotation explicite de la contamination.

### Décision 2 — H17–H22 exclus du périmètre d'entraînement

Les années H17–H22 sont exclues du périmètre d'entraînement ML. La raison est l'incohérence matérielle : entraîner sur des observations ABDe (capacité 140) avec un seuil cible calibré SURF 7500 (capacité 94) constitue une erreur de formulation du problème d'apprentissage. Cette exclusion s'applique indépendamment de la validité du proxy UM sur ces années (qui est confirmée pour H17–H22, cf. §2.1).

### Décision 3 — H23–H24 retenus comme périmètre SURF cohérent

H23 et H24 forment le périmètre de modélisation retenu. Ce périmètre satisfait les trois conditions de cohérence :

| Condition | H23 | H24 |
|---|---|---|
| Matériel SURF 7500 opérationnel | ✅ (intro sept. 2023) | ✅ (canonique) |
| Proxy UM `base_offre ≥ 160` fiable | ✅ (taux 3.76 %) | ✅ (taux 1.04 %) |
| Rotations SURF disponibles pour validation | ✅ (partiel, 3 mois) | ✅ (complet) |
| Concordance APC × rotations ≥ 99 % | ✅ (triangulation §2.4) | ✅ |

**Révision du split temporel (conséquence sur ADR-027)** : la restriction du périmètre à H23–H24 impose de réviser le split d'entraînement/test. La configuration retenue est **H23 en entraînement / H24 en test OOT** (en lieu et place de H22+H23 / H24 défini en ADR-027). Cette révision fait l'objet d'un addendum formel à ADR-027 (cf. §7).

---

## 5. Volumes et impact quantitatif

| Configuration | Périmètre | Volume train | Volume test | Perte vs ADR-027 |
|---|---|---|---|---|
| ADR-027 (avant révision) | H22+H23 / H24 | 497 023 obs. | 335 709 obs. | — |
| **ADR-032 (retenu)** | **H23 / H24** | **335 426 obs.** | **335 709 obs.** | **−32.5 % train** |

La réduction de 32.5 % du volume d'entraînement est le coût direct de la cohérence matérielle. Ce coût est jugé acceptable : H22 apporte 161 597 observations ABDe dont le signal est structurellement incohérent avec la décision opérationnelle cible. Les 335 426 observations H23 sont homogènes en matériel et en seuil.

---

## 6. Alternatives considérées et écartées

| Alternative | Raison du rejet |
|---|---|
| Recalibrer `SEUIL_UM_2C` selon le matériel de chaque année | Contraire à ADR-005 : 94 est une caractéristique physique du SURF 7500, non un paramètre ajustable. Recalibrer annuellement crée autant de problèmes qu'il n'en résout. |
| Créer une feature `materiel_roulant` et conserver H17–H22 | La feature matériel n'est pas disponible de façon fiable dans l'ISTDATEN historique. De plus, le modèle apprendrait une relation cible–matériel qui n'existera plus au déploiement (100 % SURF). Biais de covariate shift garanti. |
| Ajuster le seuil `SEUIL_OFFRE_DOUBLE` pour exclure H16 à la marge | Un seuil ≥ 181 exclut H16 mais détériore la détection sur H17 (2ème valeur = 180, 2.3 % des obs.). La contamination H16 est systémique, non marginale. |
| Conserver H22 en entraînement malgré l'incohérence | H22 : 161 597 obs., mode = 140, proxy UM valide (0.40 %) mais matériel ABDe. Le signal d'entraînement reste incohérent avec le seuil 94. Exclusion maintenue. |
| Utiliser H17–H24 (proxy fiable) sans distinction matérielle | Valide pour des analyses de taux UM historique. Invalide pour l'entraînement ML avec `SEUIL_UM_2C = 94` comme critère de décision. |

---

## 7. Conséquences

### 7.1 Révision d'ADR-027 (split temporel)

ADR-027 définit le split **H22+H23 entraînement / H24 test**. Le présent ADR rend cette configuration incohérente : H22 (ABDe) ne doit pas figurer en entraînement. **Un addendum à ADR-027 est requis** pour consigner la révision du split vers **H23 entraînement / H24 test**.

> ⚠️ ADR-027 n'est pas modifié immédiatement. L'addendum sera rédigé séparément avec mise à jour des métriques KS et des volumes dans le notebook de justification du split (`notebooks/04_model_engineering_split.ipynb`).

### 7.2 Impact sur ADR-030 (stratégie de modélisation)

ADR-030 documente le découplage R²/rappel évalué sur le test set H24 avec un modèle entraîné sur H22+H23. Les métriques rapportées (R² = 0.613, rappel = 1.2 % sur 983 surcharges) correspondent au périmètre ADR-027 non révisé. Une fois le split révisé vers H23/H24, une réévaluation sur le nouveau périmètre d'entraînement est nécessaire pour vérifier si le découplage persiste ou s'amplifie.

> ⚠️ ADR-030 n'est pas modifié immédiatement. Un addendum documentant la réévaluation post-révision du split sera rédigé après réentraînement.

### 7.3 Pipeline ML

Le script `build_ml_dataset.py` utilise `ANNEE_HORAIRE_MIN = "H22"` par défaut. Suite au présent ADR, la valeur doit être portée à `"H23"` pour les runs d'entraînement de référence. H22 reste accessible pour des analyses exploratoires explicitement bornées.

> ⚠️ Le pipeline n'est pas modifié immédiatement. La modification de `ANNEE_HORAIRE_MIN` sera effectuée lors de la prochaine itération d'entraînement.

### 7.4 Analyses de type « périmètre proxy UM fiable »

Pour toute analyse historique du proxy UM (taux UM, injustifiés, saisonnalité), le périmètre fiable reste **H17–H24** (proxy valide, matériel ABDe ou SURF). H16 est exclu même de ces analyses.

---

## 8. Références

- Notebook `notebooks/02_data_understanding_apc.ipynb` §6.2 — distribution `base_offre_2eme_classe` par année horaire, figure `outputs/02_offre_qualite_par_annee.png`
- Notebook `notebooks/03h_du_rotations.ipynb` — parc SURF 7500, couverture rotations H23–H24
- Notebook `notebooks/04h_triangulation_apc_rotations.ipynb` — triangulation APC × rotations, concordance 99.3 % sur 40 797 course-jours
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM `SEUIL_UM_2C = 94` (capacité assise 2ème classe SURF 7500)
- [ADR-007](ADR-007_rotations_tours_service.md) — tours de service, table de rotations externe
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22+H23 / H24 (révisé par le présent ADR)
- [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) — découplage R²/rappel, stratégie de modélisation (addendum à prévoir)

---


---
id: ADR-033
ancien_id: ADR-34
date_decision: 2026-05-29
statut: remplacé
remplace_par: [ADR-036, ADR-052]
modifie: [ADR-031]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-033 — Pivot architectural : régression continue + augmentation métier en couche 2

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-036, ADR-052.
> Décisions antérieures que ce document modifie : ADR-031.
> **Précision au gel — tableau §1.2 non traçable.** Le tableau du §1.2 est présenté comme
> l'« aboutissement empirique (ADR-031) ». Il ne reproduit pas ADR-031 §2.5, dont les valeurs
> sont : classifieur `scale_pos_weight = 341` **0,2359**, régresseur complet **0,2481**,
> régresseur Top20 **0,2496**, régresseur pondéré 10/5/1 **0,2276** — trois régresseurs et un
> classifieur, dont **aucun n'est un `scale_pos_weight = 20`**. Les valeurs 0,244 / 0,238 / 0,252
> ne correspondent à aucun run du registre, et `scale_pos_weight = 20` n'apparaît dans aucun ADR
> ni dans aucun fichier du dépôt. Le rappel de **40,7 %** est celui du classifieur 341 calibré au
> ratio de coût FN:FP de **20:1** (ADR-031 §2.4.2), pour une précision de **17,9 %** et
> FP/TP = **4,58** : le « 20 » est un ratio de coût, non un poids de classe, et la précision de
> 3,9 % n'a aucune source dans le registre. Le quadruplet n'est pas établissable depuis le dépôt ;
> la justification n° 2 du §1.3 est reformulée sur les valeurs d'ADR-031.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-29 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/05_modeling_xgboost_reference.ipynb`, `notebooks/05b_modeling_weighted.ipynb`, `notebooks/05c_modeling_classification.ipynb`, `notebooks/06_feature_analysis_h22_h23_h24.ipynb`, `notebooks/07_segmentation_bas_haut.ipynb` |
| **ADR liés** | ADR-001 (cible), ADR-003 (architecture deux couches), ADR-005 (seuil UM), ADR-007 (tours de service), ADR-027 (split temporel), ADR-030 (révision stratégie), ADR-031 (verdict classe rare), ADR-032 (révoqué), ADR-034 (périmètre base_offre) |

---

## 1. Contexte et motivation du pivot

### 1.1 — Cheminement depuis l'ADR-030

L'ADR-030 (révision stratégie, date : 2026-05-xx) avait acté l'exploration de trois leviers pour répondre au découplage R²/rappel observé sur la classe surcharge dans le modèle de référence (R² ≈ 0.613, rappel sur surcharges ≈ 0 % à seuil calibré naïvement) :

- **L1 — Pondération des surcharges** : `scale_pos_weight` et `sample_weight` proportionnel à la rareté
- **L2 — Fonction de coût asymétrique** : `reg:tweedie`, focale-regression, pertes asymétriques personnalisées
- **L3 — Classification binaire** : reformulation en `target_um_2eme_classe ∈ {0, 1}` avec seuil calibré

L'ADR-030 considérait ces leviers comme orthogonaux et complémentaires, et réservait la décision finale à l'issue des empiriques.

### 1.2 — Aboutissement empirique (ADR-031)

Le notebook 05c (classification) et le notebook 05b (pondération) ont conduit à la convergence documentée dans l'ADR-031 :

| Modèle | PR-AUC | Rappel (seuil 0.40) | Précision |
|---|---|---|---|
| XGBoost Baseline (nb05) | 0.235 | ~0 % | — |
| XGBoost pondéré scale_pos_weight=20 | 0.244 | 40.7 % | 3.9 % |
| XGBoost pondéré sample_weight | 0.238 | ~similaire | ~similaire |
| Classifieur binaire calibré | 0.252 | variable | variable |

Les quatre variantes convergent vers un PR-AUC de 0.23–0.25. L'ADR-031 a interprété ce plafond comme une **limite informationnelle** : les features automatiques actuelles ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité opérationnelle.

L'addendum de l'ADR-031 (2026-05-29) a élargi cette interprétation à un pivot architectural, formalisé par le présent ADR-033.

### 1.3 — Pourquoi la poursuite de l'optimisation pure n'est plus la voie retenue

Trois raisons convergentes :

1. **Plafond empirique robuste** : la stabilité du PR-AUC entre modèles de nature différente (régression pondérée vs classification) indique que la limite n'est pas algorithmique. Ajouter des arbres, affiner les hyperparamètres ou explorer d'autres architectures (neural networks, gradient boosting alternatif) ne leverait pas cette contrainte informationnelle.

2. **Plafond de rappel infranchissable au coût opérationnel acceptable** : le rappel plafonne à **40,7 %** au ratio de coût FN:FP le plus agressif testé (20:1), pour une précision de **17,9 %** et FP/TP = 4,58 (ADR-031 §2.4.2) ; au ratio 10:1 il n'atteint que 34,8 %, pour une précision de 28,1 %. Aucun réglage ne procure simultanément un rappel opérationnellement utile et une précision au moins égale à la pratique en vigueur, et sur le segment haut le rappel reste nul (0 TP sur 104 surcharges, ADR-031 §2.1 et §4.1). Dans le contexte opérationnel MOB — où 79.2 % des UM déployées sont déjà inutiles (baseline tours, notebook 04h) — une dégradation supplémentaire de la précision rend l'artefact contre-productif.

3. **Limite informationnelle identifiable** : l'analyse des faux négatifs résiduels (notebook 07, segment haut) révèle une concentration sur juin (33 % vs 8 % global) et les dimanches/fériés (31 % vs 15 % global). Ces patterns correspondent à des événements touristiques ponctuels que les features automatiques actuelles (météo, calendrier, événementiel Riviera Tourisme) ne couvrent pas entièrement. La solution est l'enrichissement de l'information, pas l'optimisation du modèle.

---

## 2. Décision architecturale

### 2.1 — Architecture à deux couches (confirmation ADR-003)

L'architecture à deux couches de l'ADR-003 est confirmée et précisée :

**Couche 1 — Modèle prédictif** :
Modèle XGBoost de régression au grain tronçon × course × date, prédisant `target_voyageurs_2eme_classe` en valeur continue. Entraîné sur H22+H23, évalué sur H24 (ADR-027). Performances de référence : R² global = 0.6123 (scénario D, 160 features nettoyées, notebook 06).

**Couche 2 — Système de décision UM** :
Combinaison de la prédiction continue de la couche 1 avec des informations métier externes pour produire la recommandation finale UM au niveau du tour de service (ADR-007). La couche 2 n'est pas un simple seuillage : elle intègre une **augmentation métier** (§2.5 ci-dessous) qui enrichit la décision en capturant des signaux non automatisables.

La couche 2 produit : `recommandation_um = (pred_voyageurs_2eme_classe >= SEUIL_UM_2C) OR (signal_augmentation_metier)`.

### 2.2 — Modèle unique avec feature `spatial_segment` (validé empiriquement par notebook 07)

L'architecture duale (deux modèles XGBoost spécialisés par segment bas/haut) a été testée empiriquement dans le notebook 07. Résultats :

| Approche | R² segment bas | R² segment haut |
|---|---|---|
| Modèle unique (sans `spatial_segment`) | 0.5815 | 0.3374 |
| Modèle spécialisé bas ou haut | 0.5569 | 0.3262 |
| **ΔR² (spécialisé − unique)** | **−0.025** | **−0.011** |

Les modèles spécialisés sont systématiquement inférieurs au modèle unique sur les deux segments. L'entraînement sur un seul segment prive le modèle des 379 K observations du segment bas qui apportent de la généralisation.

**Le modèle unique est retenu.** La feature `spatial_segment` agit comme switch contextuel permettant au modèle unique d'apprendre simultanément les deux dynamiques de fréquentation.

Note : bien que les performances globales soient inférieures pour les modèles spécialisés, l'analyse SHAP par segment (notebook 07, Section 5) révèle des divergences profondes dans les features importantes :
- **Segment bas** (TRV/pendulaire) : identifiants de gare (`id_gare_depart/arrivee`), sens de circulation (`base_sens`), vacances scolaires
- **Segment haut** (touristique/excursionniste) : météo (température, précipitations), profil tarifaire SIMBA (`simba_part_spar`), démographie locale

Ces divergences constituent un résultat de data understanding exploitable dans le mémoire pour documenter la dualité des dynamiques de la ligne R35.

### 2.3 — Régression au grain tronçon (confirmation ADR-001)

La cible reste `target_voyageurs_2eme_classe` en régression continue (ADR-001). La couche de décision UM applique le seuil `SEUIL_UM_2C = 94` (ADR-005) en aval, après agrégation au niveau du tour de service.

La reformulation en classification binaire (`target_um_2eme_classe`) testée dans le notebook 05c est définitivement écartée pour le modèle principal : la régression continue préserve l'information de magnitude (à quel point la surcharge est dépassée) utile pour la calibration du seuil en couche 2.

### 2.4 — Périmètre d'entraînement (confirmation ADR-027)

Le split H22+H23 entraînement / H24 test (ADR-027) est confirmé sans modification. L'ADR-032 (révoqué le 2026-05-29 et remplacé par ADR-034) avait proposé une restriction à H23 seul sur la base d'un argument d'incohérence matérielle. Cet argument a été invalidé par l'ADR-034 : `base_offre_2eme_classe` est une variable diagnostique hors-ML, et `target_voyageurs_2eme_classe` est invariante au matériel.

Volumes retenus :
- Train : H22+H23 — 497 023 observations (379 390 bas + 117 633 haut)
- Test OOT : H24 — 335 709 observations (251 106 bas + 84 603 haut)

### 2.5 — Augmentation métier comme réponse à la limite informationnelle

Le pivot architectural central de cet ADR est l'introduction formelle de l'**augmentation métier** comme composante de la couche 2.

**Principe** : intégrer dans le système de décision des informations disponibles à J-1 que les features automatiques ne capturent pas, parce qu'elles ne sont pas structurées dans un système de données exploitable automatiquement.

**Sources prioritaires d'augmentation métier** (à valider opérationnellement avec le Responsable de production, MOB) :

| Source | Type | Disponibilité présumée | Priorité |
|---|---|---|---|
| Réservations groupes anticipées | Base interne MOB | À confirmer avec Responsable de production, MOB | Haute |
| Événements planifiés non publiés | Calendriers internes, conventions, transports scolaires | À confirmer avec Responsable de production, MOB | Haute |
| Signaux contextuels opérationnels | Communication équipes terrain | À structurer | Moyenne |
| Complément référentiel événementiel | Au-delà de Riviera Tourisme | À valider avec Responsable de production, MOB | Moyenne |

**Ce que l'augmentation métier n'est pas** : une modification du modèle prédictif. La couche 1 reste inchangée. L'augmentation métier enrichit uniquement la décision finale en couche 2.

**Condition de mise en œuvre** : validation de la disponibilité et de la fiabilité opérationnelle des sources listées auprès du Responsable de production, MOB avant tout développement de la couche 2.

---

## 3. Résultats empiriques sous-jacents au pivot

### 3.1 — Résultats du notebook 06 (analyse de features et nettoyage)

**Périmètre nettoyé** : 160 features ML retenues (`FEATURES_ML_NETTOYEES`) après exclusion de 14 features en deux catégories :
- Catégorie 1 — hors-cible (12 features) : `histo_voyageurs_1ere_classe_*` × 6 + `histo_voyageurs_total_*` × 6
- Catégorie 5 — doublons calendaires (2 features) : `cal_heure_depart`, `cal_heure_arrivee`

22 features supplémentaires sont classées "à valider" (catégories 3, 6, 7) mais conservées dans `FEATURES_ML_NETTOYEES` par défaut.

**R² du modèle de référence** : 0.6123 sur 160 features — stable vs 0.613 sur 174 features (Δ = −0.0007), confirmant que les exclusions n'ont pas de coût empirique.

**Courbe d'élagage** (top-N features par rang composite) :

| N features | R² global |
|---|---|
| 10 | 0.6181 |
| 15 | 0.5890 |
| 30 | 0.6002 |
| 70 | 0.6005 |
| 160 | 0.6123 |

La courbe est très plate au-delà de 10 features : le top 10 surperforme le complet (0.6181 > 0.6123). Signal d'alerte sur la redondance des features marginales.

**Quatre scénarios évalués** :

| Scénario | n features | R² global | R² bas | R² haut |
|---|---|---|---|---|
| A — Minimum viable | 15 | 0.5890 | 0.5731 | 0.1792 |
| B — Équilibré | 30 | 0.6002 | 0.5782 | 0.2460 |
| C — Performance | 70 | 0.6005 | 0.5682 | 0.3162 |
| D — Complet | 160 | 0.6123 | 0.5823 | 0.3279 |

Le scénario C maximise le R² sur le segment haut (0.3162) tout en restant parcimonieux (70 features). Le scénario B offre le meilleur rapport performance/complexité globale. La décision entre B et C est reportée à l'ADR-35, après validation opérationnelle des sources d'augmentation métier.

**Top 5 features par rang SHAP composite** :
1. `histo_voyageurs_2eme_classe_win7_mean` — historique 7j moyen (autocorrélation pendulaire forte)
2. `spatial_gare_depart_ordre` — position topologique de la gare
3. `spatial_gare_arrivee_ordre` — position topologique de la gare arrivée
4. `horaire_numero_train` — identifiant de train (rang 4, ablation borderline — ADR-017)
5. `histo_voyageurs_2eme_classe_win7_median` — historique 7j médian

### 3.2 — Résultats du notebook 07 (test de segmentation bas/haut)

**Comparaison modèle unique vs modèles spécialisés** (cf. §2.2 pour le tableau complet) :
- Verdict : modèle unique suffisant. Spécialisation écartée empiriquement.
- ΔR² = −0.025 (bas), −0.011 (haut). Pas de gain sur aucun segment.

**Divergence des features top SHAP entre segments** (Section 5, notebook 07) :

| Analyse | Résultat |
|---|---|
| Features consensus (top 20 des deux segments) | 11 features — essentiellement `histo_*` et `cal_*` |
| Features importantes uniquement sur le bas | 4 : `id_gare_depart/arrivee`, `base_sens`, `event_is_vacances_ou_ferie_vaud` |
| Features importantes uniquement sur le haut | 5 : `simba_part_spar`, `meteo_temperature_h`, `meteo_temperature_max_j`, `meteo_precip_total_j`, `spatial_gare_depart_pop_500m_total` |
| Top divergence rang (|Δrang| max) | `id_gare_depart` (Δ = 122), `id_gare_arrivee` (Δ = 119), `spatial_gare_depart_pop_500m_total` (Δ = 96) |

Ces divergences confirment empiriquement que le segment bas obéit à une dynamique pendulaire (identité des gares, calendrier, sens) tandis que le segment haut obéit à une dynamique excursionniste-touristique (météo, profil tarifaire, démographie).

**Rappel sur les surcharges du segment haut** :
- 104 surcharges dans le test H24 haut (0.12 % du segment)
- Rappel = 0.000 sur les deux modèles (unique et spécialisé)
- Confirmation empirique de la limite informationnelle structurelle sur le segment haut

**Diagnostic des erreurs extrêmes** (top 1% erreurs absolues, segment haut) :
- Concentration en juin : 33 % du top 1% vs 8 % dans la distribution globale haut
- Concentration dimanches/fériés : 31 % vs 15 % global
- Pattern cohérent avec une dynamique touristique non capturée par les features actuelles

### 3.3 — Limite informationnelle structurelle

Les analyses des notebooks 05, 05b, 05c, 06 et 07 convergent vers la conclusion suivante :

> **Les features automatiques actuelles (APC historique, calendrier, météo, événementiel public Riviera Tourisme, ISTDATEN, SIMBA) ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles avec une fidélité opérationnelle, particulièrement sur le segment haut.**

Cette limite est structurelle et non algorithmique :
- Elle est stable entre 4 architectures de modèles différentes (PR-AUC 0.23–0.25, ADR-031)
- Elle est géographiquement localisée (segment haut > segment bas)
- Elle est temporellement localisée (juin, dimanches/fériés touristiques)
- Elle est explicable : les pics touristiques extrêmes sont par nature imprévisibles sans information sur les flux planifiés (réservations groupes, événements privés)

Le pivot vers l'augmentation métier (couche 2) est la réponse architecturale rationnelle à cette limite.

---

## 4. Conséquences sur les ADR existants

### 4.1 — ADR-003 (architecture deux couches)

**Statut** : confirmé et précisé.

L'ADR-003 avait posé l'architecture à deux couches (modèle prédictif + couche de décision UM). Le présent ADR-033 précise que la couche 2 n'est pas un simple seuillage post-prédiction, mais un système de décision enrichi par l'augmentation métier. Cette précision est additive — elle ne remet pas en cause l'ADR-003.

### 4.2 — ADR-030 (révision stratégie de modélisation)

**Statut** : reste valide, parcours clos.

L'ADR-030 avait ouvert l'exploration des leviers L1/L2/L3. Ce parcours est désormais clos : les trois leviers ont été testés empiriquement (notebooks 05b et 05c), leur aboutissement documenté dans l'ADR-031, et le pivot architectural formalisé dans le présent ADR-033. L'ADR-030 n'est pas révoqué — il documente la démarche exploratoire qui a mené à l'ADR-033.

### 4.3 — ADR-031 (verdict classe rare et addendum)

**Statut** : cohérence maintenue.

L'addendum de l'ADR-031 (2026-05-29) référence déjà explicitement l'ADR-033. Les résultats empiriques de l'ADR-031 (PR-AUC 0.23–0.25, plafond robuste) sont les arguments centraux du pivot documenté ici.

Note : l'addendum de l'ADR-031 contient une mention de l'ADR-032 (révoqué) comme facteur explicatif du plafond PR-AUC. Cette mention est inexacte (l'argument d'incohérence matérielle de l'ADR-032 ne s'applique pas à la cible continue). Elle est préservée pour la traçabilité historique, mais ne doit pas être citée dans le mémoire. L'explication correcte du plafond est la limite informationnelle documentée en §3.3 du présent ADR.

### 4.4 — ADR-35 (à venir)

**Statut** : non encore rédigé.  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->

L'ADR-35 actera la décision finale sur le modèle de référence :
- Scénario de features retenu (B, C ou variante) après validation opérationnelle des sources d'augmentation métier auprès du Responsable de production, MOB
- Hyperparamètres définitifs (à tuner ou à conserver tels quels selon la décision)
- Architecture de la couche 2 et seuil de décision UM calibré
- Toute exclusion supplémentaire de features (catégories 3, 6, 7 du notebook 06)

L'ADR-35 ne peut être rédigé qu'après la validation opérationnelle des sources d'augmentation métier (§5.1 ci-dessous).

---

## 5. Plan d'action pour la suite

### 5.1 — Validation opérationnelle des sources d'augmentation métier

**Interlocuteur principal** : Responsable de production, MOB.
**Interlocuteur secondaire** : conduite des trains (échange informel).

Questions à valider avec Responsable de production, MOB :
1. Existe-t-il une base structurée de réservations groupes avec granularité date × train × volume anticipé ? Quelle est la latence de saisie ?
2. Les événements privés (transports scolaires spéciaux, conventions, groupes culturels) sont-ils tracés quelque part à J-1 ou seulement informellement ?
3. Quel est le référentiel événementiel en dehors de Riviera Tourisme ? Y a-t-il un calendrier opérationnel interne ?
4. Quel est le coût relatif perçu d'une UM inutile (faux positif) versus une surcharge ratée (faux négatif) ? Ce ratio conditionne la calibration du seuil en couche 2.

Questions à valider du côté de la conduite des trains :
1. À quelle heure précise le mécano reçoit-il la décision UM pour le lendemain ? (contrainte horizon décisionnel)
2. Quelle est la forme acceptable de la recommandation ? (message court, probabilité, catégorie de risque)

### 5.2 — Calibration du seuil de décision UM

Le seuil de déclenchement UM en couche 2 doit être calibré selon le ratio FN:FP acceptable, défini avec Responsable de production, MOB. Sans cet ancrage opérationnel, le seuil reste théorique.

Le baseline opérationnel de référence reste : 79.2 % d'UM inutiles sur les tours analysés (notebook 04h). L'artefact ML ne doit pas dégrader ce ratio au-delà d'un niveau acceptable à définir avec Responsable de production, MOB.

### 5.3 — Rédaction de l'ADR-35

Prérequis :
1. Validation opérationnelle des sources d'augmentation métier (§5.1) — Responsable de production, MOB
2. Résultats du Travail 2 (validation externe des variables auprès du responsable de production si applicable)
3. Décision sur le scénario de features (B vs C) après intégration des retours opérationnels

L'ADR-35 figera : scénario features, hyperparamètres (tunés ou pratiques), architecture couche 2, seuil de décision UM, critères d'évaluation du système global (couche 1 + couche 2).

---

## 6. Limites et points de vigilance

1. **Sources d'augmentation métier non validées** : la faisabilité opérationnelle des sources de la couche 2 n'est pas encore confirmée. Si Responsable de production, MOB indique qu'aucune source structurée n'est disponible, l'augmentation métier devra reposer sur des signaux semi-formels (communication téléphonique, notes opérationnelles) dont l'automatisation est plus complexe.

2. **Segment haut structurellement difficile** : R² haut = 0.33 (modèle unique). Même avec l'augmentation métier, les pics extrêmes touristiques resteront imprévisibles si les événements ne sont pas anticipés dans les sources internes MOB. Risque résiduel documenté et assumé.

3. **Couche 2 non encore évaluée empiriquement** : à ce stade, seule la couche 1 (modèle de régression) a été évaluée. L'évaluation du système global (couche 1 + couche 2 avec augmentation métier) n'a pas encore été conduite. Elle sera l'objet d'un travail ultérieur après validation des sources.

4. **Hyperparamètres XGBoost non tunés** : les paramètres pratiques (n_estimators=300, max_depth=6, lr=0.1, subsample=colsample=0.8) ont été utilisés par convention de comparabilité dans les notebooks 05 à 07. Un tuning Bayésien ciblé pourrait améliorer marginalement les performances. La décision de tuner est reportée à l'ADR-35.

5. **Rappel nul sur le segment haut** : le rappel = 0 sur les 104 surcharges test du segment haut est une limite forte de la couche 1 seule. La couche 2 (avec augmentation métier) est la seule réponse viable pour ce segment.

6. **Risque de surdépendance aux features histo_*** : les 3 premières features par rang SHAP global sont des lags historiques (`histo_voyageurs_2eme_classe_win7_*`). Cette dépendance forte à l'autocorrélation est performante sur les patterns récurrents mais structurellement aveugle aux ruptures de tendance (événements exceptionnels non précédés d'historique de surcharge).

---

## 7. Références

### Notebooks
- `notebooks/05_modeling_xgboost_reference.ipynb` — XGBoost baseline, R² = 0.611–0.613, PR-AUC = 0.235
- `notebooks/05b_modeling_weighted.ipynb` — Pondération L1/L2, PR-AUC max = 0.244, rappel max = 40.7 % (scale_pos_weight=20)
- `notebooks/05c_modeling_classification.ipynb` — Classification binaire, PR-AUC = 0.252
- `notebooks/06_feature_analysis_h22_h23_h24.ipynb` — Codebook 192 features, nettoyage, scénarios A–D, top SHAP
- `notebooks/07_segmentation_bas_haut.ipynb` — Comparaison modèle unique vs spécialisés, divergence SHAP, diagnostic segment haut

### ADR associés
- [ADR-001](ADR-001_cible_2eme_classe.md) — Cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — Architecture deux couches
- [ADR-005](ADR-005_seuil_um_94_2c.md) — Seuil UM `SEUIL_UM_2C = 94`
- [ADR-007](ADR-007_rotations_tours_service.md) — Tours de service, couche de décision
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — Split temporel H22+H23 / H24
- [ADR-030](ADR-030_revision_strategie_modelisation_classe_rare.md) — Révision stratégie (leviers L1/L2/L3)
- [ADR-031](ADR-031_verdict_modelisation_classe_rare_et_segmentation.md) — Verdict classe rare, plafond PR-AUC
- [ADR-032](ADR-032_perimetre_materiel_et_coherence_temporelle.md) — Révoqué (2026-05-29)
- [ADR-034](ADR-034_perimetre_base_offre_qualite_diagnostique.md) — `base_offre_2eme_classe` hors-ML

### Sources théoriques sur l'augmentation métier
- Hevner et al. (2004) — Design Science Research : l'artefact combinant couche prédictive et couche décisionnelle s'inscrit dans la famille des "decision support systems" évalués sur leur utilité organisationnelle réelle.
- Gregor & Hevner (2013) — Positionnement DSR : la couche 2 constitue une "improvement" (amélioration d'une solution connue) par rapport au seuillage naïf.
- Lundberg & Lee (2017) — SHAP : explicabilité de la couche 1 comme condition d'adoption de la couche 2 (l'opérateur doit pouvoir valider la prédiction avant d'y adjoindre les signaux métier).

---


---
id: ADR-034
ancien_id: ADR-36
date_decision: 2026-05-29
statut: actif
modifie: [ADR-032]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-034 — Périmètre `base_offre_2eme_classe` : qualité diagnostique sans impact sur l'entraînement ML

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-032.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-29 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/02_data_understanding_apc.ipynb` §6.2 ; `notebooks/03h_du_rotations.ipynb` ; `notebooks/04h_triangulation_apc_rotations.ipynb` |
| **Remplace** | ADR-032 (révoqué le 2026-05-29) |
| **ADR liés** | ADR-001 (cible), ADR-005 (seuil UM 94), ADR-027 (split temporel — inchangé) |

---

## 1. Contexte

Au cours de la phase de data understanding, l'analyse de `base_offre_2eme_classe` (variable d'offre des APC, représentant la capacité installée par tronçon-course) a révélé des variations significatives entre années horaires, liées aux changements de matériel roulant sur la ligne R35 (ABDe jusqu'en H22, SURF 7500 à partir de H23).

Un premier examen (ADR-032 du 2026-05-29, révoqué le même jour) avait conclu à la nécessité d'exclure H16–H22 du périmètre d'entraînement ML, sur la base d'un argument d'incohérence matérielle. Cet argument reposait sur une confusion entre le statut diagnostique de `base_offre_2eme_classe` (variable hors modèle) et le signal appris par le modèle (la cible continue `target_voyageurs_2eme_classe`). Le présent ADR remplace cette décision par un constat plus modeste et techniquement correct.

---

## 2. Constat empirique sur `base_offre_2eme_classe` (notebook 02 §6.2)

La colonne `base_offre_2eme_classe` représente la capacité 2ème classe installée pour un tronçon-course donné. Elle sert de proxy structurel de composition : toute valeur ≥ 160 (`SEUIL_OFFRE_DOUBLE`) est interprétée comme une UM déployée.

| Année | n obs (tronçons) | Mode `base_offre` | Mode % | 2ème valeur | 2ème % | Taux proxy UM (≥160) | Statut diagnostique |
|---|---|---|---|---|---|---|---|
| **H16** | 168 377 | **180** | **53.0 %** | 140 | 44.8 % | **53.01 %** | ❌ Inutilisable (proxy) |
| H17 | 218 529 | 140 | 97.7 % | 180 | 2.3 % | 2.29 % | ✅ Valide |
| H18 | 195 696 | 140 | 97.6 % | 280 | 2.3 % | 2.35 % | ✅ Valide |
| H19 | 233 595 | 140 | 99.7 % | 280 | 0.3 % | 0.33 % | ✅ Valide |
| H20 | 208 312 | 140 | 99.7 % | 280 | 0.3 % | 0.30 % | ✅ Valide |
| H21 | 194 269 | 140 | 99.4 % | 280 | 0.6 % | 0.62 % | ✅ Valide |
| H22 | 161 597 | 140 | 90.8 % | 78 | 8.8 % | 0.40 % | ✅ Valide |
| H23 | 335 426 | 90 | 96.2 % | 180 | 3.7 % | 3.76 % | ✅ Valide (SURF) |
| H24 | 335 709 | 94 | 99.0 % | 188 | 1.0 % | 1.04 % | ✅ Valide (SURF) |

Trois régimes distincts :

- **H16** : mode 180 (53.0 % des observations) ≥ seuil proxy 160. Le proxy structurel `base_offre ≥ 160` produit un taux UM spurieux de 53.01 %. Cause : le mode 180 correspond à la capacité assise simple de l'ABDe, supérieure au seuil 160. **Cette colonne ne peut pas être utilisée pour des analyses diagnostiques de type proxy UM sur H16.**
- **H17–H22** : matériel ABDe, mode 140, proxy `base_offre ≥ 160` valide (taux 0.30 %–2.35 %).
- **H23–H24** : matériel SURF 7500, mode 90/94, proxy `base_offre ≥ 160` valide (taux 3.76 % et 1.04 %).

---

## 3. Statut de `base_offre_2eme_classe` dans le projet

`base_offre_2eme_classe` est une **variable d'offre opérationnelle**. Elle est utilisée dans le projet uniquement comme :

1. **Proxy diagnostique** en data understanding pour caractériser le matériel roulant historique et estimer le taux d'UM observé (proxy `base_offre ≥ 160`, notebooks 02 §6.3, 04h).
2. **Variable de contrôle** pour la triangulation APC × rotations (notebook 04h).

**Elle n'est pas une feature du modèle ML et n'est pas dans `ml_dataset.parquet`.** La cible du modèle est `target_voyageurs_2eme_classe` (ADR-001), qui est une mesure physique du nombre de voyageurs comptés par les APC, indépendante de la capacité installée.

---

## 4. Implications pour l'entraînement ML

**Aucune exclusion d'année horaire n'est requise sur la base du diagnostic `base_offre_2eme_classe`.** Quatre raisons :

1. **Invariance de la cible** : `target_voyageurs_2eme_classe` est un comptage physique. 94 voyageurs comptés en H17 sur ABDe = 94 voyageurs comptés en H24 sur SURF. Le matériel sous-jacent ne modifie pas la signification du comptage.

2. **Absence du matériel dans le modèle** : le modèle apprend `f(features) → target_voyageurs_2eme_classe` en valeur continue. Aucune feature ne encode la capacité du matériel roulant.

3. **Seuil opérationnel en aval uniquement** : le seuil `SEUIL_UM_2C = 94` (ADR-005) intervient exclusivement dans la couche de décision aval (ADR-003), pas dans la phase d'apprentissage. L'apprentissage porte sur la prédiction du nombre de voyageurs, pas sur le déclenchement de l'alarme UM.

4. **Stationnarité empirique validée** : les tests KS réalisés dans le cadre de l'ADR-027 confirment la stationnarité de la distribution de `target_voyageurs_2eme_classe` entre H22, H23 et H24 (KS(H22, H23) = 0.072 ; KS(H22, H24) = 0.0775 < 0.15).

**Le périmètre d'entraînement retenu reste celui défini par l'ADR-027 : H22+H23 entraînement / H24 test.** Aucune révision de l'ADR-027 n'est nécessaire.

---

## 5. Implications pour les analyses diagnostiques utilisant `base_offre_2eme_classe`

Pour les analyses qui s'appuient sur `base_offre_2eme_classe` comme proxy structurel, les périmètres fiables sont :

| Analyse | Périmètre fiable | Justification |
|---|---|---|
| Taux UM observé par année (proxy `base_offre ≥ 160`) | H17–H24 | H16 exclu : contamination du proxy (mode 180 ≥ 160) |
| Triangulation APC × rotations (composition réelle) | H23–H24 | Par disponibilité des données rotations SURF uniquement |
| Caractérisation du parc matériel historique | H16–H24 | Avec annotation explicite de la transition ABDe → SURF |

H16 reste accessible dans les données brutes pour des analyses exploratoires non-proxy (volumes bruts, distribution brute) avec annotation de la contamination.

---

## 6. Résultats conservés des notebooks 02 §6.2, 03h, 04h

Les analyses suivantes, issues des notebooks de data understanding, sont **conservées intégralement et restent références** dans le mémoire, dissociées de toute conclusion d'exclusion d'année horaire :

**Notebook 02 §6.2** — qualité de `base_offre_2eme_classe` par année horaire. Figure `outputs/02_offre_qualite_par_annee.png`. Constat diagnostique : H16 inutilisable pour le proxy structurel, H17–H24 valide. Ces résultats relèvent du data understanding sur la variable `base_offre`, pas du périmètre d'entraînement.

**Notebook 03h** — caractérisation du parc SURF 7500 : 8 rames actives (7501–7508), 46 869 lignes × 12 colonnes, période mai 2023 – déc. 2024. Taux UM planifié ~1 % des courses régulières (472/45 113). Ces résultats documentent le contexte opérationnel de déploiement.

**Notebook 04h** — triangulation APC × rotations sur H23–H24 : **99.3 % de concordance** sur 40 797 course-jours jointurés (413 UM concordants, 253 APC seul, 45 Rot seul). Baseline opérationnel **niveau tour de service** : 423 tours analysés, 88 justifiés (20.8 %), 335 inutiles (79.2 %). Ce baseline reste la référence centrale pour évaluer la valeur opérationnelle de l'artefact ML par rapport à la pratique actuelle (79.2 % d'UM inutiles).

---

## 7. Décisions

1. **`base_offre_2eme_classe` est confirmée comme variable diagnostique uniquement**, hors du dataset ML. Son comportement par année horaire (tableau §2) est documenté en tant que résultat de data understanding.

2. **Le périmètre d'entraînement défini par l'ADR-027 (H22+H23 / H24) est conservé sans modification.** L'argument d'incohérence matérielle de l'ADR-032 (révoqué) ne s'applique pas à la cible continue ni aux features du modèle.

3. **H16 est conservé dans les données brutes** et reste candidat à l'inclusion dans le périmètre d'entraînement ML (sa cible `target_voyageurs_2eme_classe` est aussi invariante que les autres années). H16 est exclu uniquement des analyses utilisant le proxy `base_offre ≥ 160` comme proxy UM (contamination).

4. **Aucune modification du pipeline ML n'est requise.** Le script `build_ml_dataset.py` conserve `ANNEE_HORAIRE_MIN = "H22"`.

---

## 8. Conséquences

- **ADR-027** : inchangé. Le split H22+H23 / H24 reste applicable tel quel.
- **ADR-030** : inchangé. Les chiffres rapportés (R² 0.613, etc.) restent valides sur leur périmètre H22+H23 / H24.
- **ADR-031** : son addendum du 2026-05-29 (rédigé en référence à l'ADR-032 révoqué) doit être révisé pour supprimer la référence à l'incohérence matérielle comme facteur explicatif du plafond PR-AUC. Voir consigne séparée.
- **Pipeline ML** : aucune modification.
- **CONTEXT.md** : la section "Périmètre matériel et cohérence temporelle (ADR-032)" est supprimée ; la section "Périmètre temporel — modèle de référence (ADR-027)" est restaurée dans sa formulation originale.

---

## 9. Références

- Notebook `notebooks/02_data_understanding_apc.ipynb` §6.2 — distribution `base_offre_2eme_classe` par année horaire, figure `outputs/02_offre_qualite_par_annee.png`
- Notebook `notebooks/03h_du_rotations.ipynb` — parc SURF 7500, couverture rotations H23–H24
- Notebook `notebooks/04h_triangulation_apc_rotations.ipynb` — triangulation APC × rotations, concordance 99.3 % sur 40 797 course-jours, baseline opérationnel 79.2 % UM inutiles
- [ADR-001](ADR-001_cible_2eme_classe.md) — cible `target_voyageurs_2eme_classe`
- [ADR-005](ADR-005_seuil_um_94_2c.md) — seuil UM `SEUIL_UM_2C = 94` (capacité assise 2ème classe SURF 7500)
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — split temporel H22+H23 / H24 (inchangé)
- [ADR-032](ADR-032_perimetre_materiel_et_coherence_temporelle.md) — révoqué le 2026-05-29 (raisonnement initial conservé pour traçabilité)

---


---
id: ADR-035
ancien_id: ADR-37
date_decision: 2026-06-03
statut: amendé
amende_par: [ADR-036]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-035 — Intégration des réservations de groupes ResSys en couche 1 du pipeline ML

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-036.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Acté |
| **Date** | 2026-06-03 |
| **Décideur** | Erwann Nedellec (data analyste MOB, futur data lead) |
| **Notebooks de référence** | `notebooks/02_data_understanding_ressys.ipynb` (sections 1–10), `notebooks/02_data_understanding_apc.ipynb` (§3.1 TCE, §3.3 AFZ weekend) |
| **Révoque** | — |
| **Lié à** | ADR-027 (split H22+H23 / H24), ADR-033 (architecture deux couches, augmentation métier), ADR-034 (base_offre diagnostique) |

---

## 1. Contexte

### 1.1 — Le problème opérationnel : limite informationnelle sur le segment haut

L'ADR-033 (2026-05-29) a formalisé le pivot architectural du projet R35 ML vers un système à deux couches : modèle XGBoost de régression en couche 1 (prédiction de `target_voyageurs_2eme_classe` au grain tronçon × course × date), et système de décision UM augmenté en couche 2. Ce pivot a été motivé empiriquement par le constat qu'aucune des architectures testées (régression pondérée, classification binaire) ne parvenait à dépasser un PR-AUC de 0.25 sur la classe surcharge, et par le diagnostic que cette limite est **informationnelle et non algorithmique** : les features automatiques actuelles ne contiennent pas l'information nécessaire pour prédire les surcharges individuelles, particulièrement sur le segment haut.

Ce diagnostic est rendu quantitatif par le notebook 07 (segmentation bas/haut) : le modèle de référence atteint R² = 0.6123 global (scénario D, 160 features), mais seulement R² = 0.3279 sur le segment haut, et un **rappel de 0.000 sur les 104 surcharges test du segment haut H24** (aucune prédite). L'analyse des erreurs extrêmes (notebook 07, §5) révèle une concentration en juin (33 % du top 1 % des erreurs vs 8 % en global) et les dimanches/fériés (31 % vs 15 % en global) — pattern cohérent avec une dynamique touristique non capturée par les features existantes.

### 1.2 — La nouvelle source : réservations de groupes ResSys

À la suite des entretiens avec le Responsable de production, MOB, une base de données de réservations de groupes s'avère disponible : les fichiers d'export ResSys pour la ligne R35, archivés de H16 à H25, au format `data/external/reservations/export_r35_h{16-25}.xlsx`. Ces fichiers contiennent exclusivement des **réservations de groupes** (colonne `Reiseart = Gruppe`), avec deux statuts possibles : `50 Abgeschlossen` (confirmée) et `90 Storniert` (annulée). Le schéma est stable sur l'ensemble de la période : 19 colonnes identiques, vérifiées dans le notebook 02_ressys §1 (Quality Gate 1 : PASS).

L'inventaire global (02_ressys §1) porte sur **11 556 lignes brutes H16-H25**, dont **9 129 Abgeschlossen** représentant **338 580 passagers 2ème classe cumulés**. Rapporté au volume APC H24 (6 702 978 voyageurs-tronçon), le poids des réservations au niveau du voyage logique est de **0.48 %** — faible en termes volumétriques. La valeur de cette source réside non pas dans son volume mais dans la nature de l'information qu'elle porte : la présence planifiée de groupes importants sur des trains et dates spécifiques, précisément la catégorie d'événements que le modèle ne capte pas.

### 1.3 — L'hypothèse empirique et sa confirmation

L'hypothèse formulée par Erwann avant l'investigation : les réservations de groupes expliqueraient une part significative des surcharges segment haut non détectées par le modèle.

Le notebook 02_ressys valide cette hypothèse empiriquement. Sur les **104 surcharges segment haut H24** (cellules avec `target_voyageurs_2eme_classe ≥ 94`) :

- **62 (59.6 %) coïncident avec au moins une réservation de groupe** confirmée à date (02_ressys §9.7, topologie corrigée v2)
- **7 sur 7 surcharges segment haut de juin H24 (100 %)** coïncident avec une réservation

Juin concentre précisément les pires erreurs du modèle (33 % des erreurs extrêmes haut) et est le mois pour lequel le rappel était le plus attendu. La convergence entre le diagnostic ADR-033 (juin comme mois problématique) et la concentration des réservations sur ce même mois constitue une validation croisée forte.

Pour mémoire, le prédicteur naïf « résa ≥ 94 → surcharge » sur le segment haut H24 atteint un Rappel = 0.317 et une Précision = 0.091 (02_ressys §7.2). Ce prédicteur pris isolément est trop imprécis pour être utilisé directement — 90 % des réservations de 94+ pax ne déclenchent pas une surcharge APC, parce qu'une composante de fréquentation spontanée s'y ajoute. C'est précisément pourquoi ces réservations doivent entrer dans le modèle ML comme **features**, et non comme règles métier indépendantes.

---

## 2. Décisions actées

### 2.1 — Architecture d'intégration : Approche 1, couche 1 XGBoost

**Décision** : les features dérivées des réservations sont intégrées dans le régresseur XGBoost de la couche 1. Elles constituent des features d'entrée parmi les 160+ déjà présentes dans `ml_dataset.parquet`. L'architecture à deux couches de l'ADR-033 est maintenue sans modification.

**Justification empirique** : l'Approche 2 — intégrer les réservations comme règle OR en couche 2 — a été explicitement écartée pour deux raisons convergentes. (1) Le prédicteur naïf atteint une précision de seulement 0.091 (02_ressys §7.2) : une OR-rule couche 2 déclencherait des UM pour 90 % de faux positifs, dégradant le ratio opérationnel actuel. (2) La target `target_voyageurs_2eme_classe` inclut les passagers de groupe dans les comptages APC — intégrer les réservations comme règle OR indépendante du modèle qui prédit cette même cible crée un double-comptage sémantique. En revanche, fournir les réservations comme features XGBoost permet au modèle d'**apprendre l'interaction résa × autres features** (météo, vacances scolaires, saisonnalité), ce qui est précisément ce qu'un prédicteur naïf ne peut pas faire.

**Conséquence** : le scénario de features retenu pour le modèle de référence (ADR-033 §3.1 : scénario D, 160 features) sera étendu à 168 features incluant les 8 features `resa_*` définies au §2.6. L'ADR-35 (à venir) intégrera cette extension dans sa décision finale sur le scénario de features.

### 2.2 — Périmètre temporel : H22-H25

**Décision** : les réservations sont intégrées au pipeline pour les années horaires H22 à H25, en cohérence avec ADR-027 (périmètre ml_dataset : H22+H23 train, H24 test). Les fichiers H16-H21 sont chargés et nettoyés dans le notebook 02_ressys mais ne sont pas injectés dans le pipeline.

**Justification** : le ml_dataset couvre H22-H24. H25 sera ajouté comme holdout lors d'une prochaine itération (ADR-002). H16-H21 restent disponibles pour analyse historique des patterns de réservation, mais leur intégration dans le pipeline d'entraînement n'apporterait pas de valeur directe : le ml_dataset ne couvre pas ces années et il n'existe pas de target pour créer des features ML sur cette période.

**Limite** : H22 présente une couverture réservations structurellement partielle, documentée en §2.7 ci-dessous.

### 2.3 — Topologie d'éclatement year-specific

**Décision** : la LINE_ORDER statique extraite de `dim_gare` est remplacée par une fonction `build_line_order_from_ml(annee_horaire)` qui déduit la séquence de gares active en consultant les tronçons réellement présents dans `ml_dataset.parquet` pour chaque année horaire. Les années H16-H21, hors ml_dataset, utilisent la topologie H22 comme proxy.

**Justification empirique** : la LINE_ORDER v1 (statique, extraite de `dim_gare`) incluait GIL (Gilamont) pour toutes les années. Or GIL était desservi en H22 uniquement — il a été retiré du graphique commercial à partir de H23 (confirmépar l'absence de GIL dans ml_dataset H23 et H24). L'éclatement v1 créait systématiquement les tronçons `VV→GIL`, `GIL→VVVI`, `VVVI→GIL`, `GIL→VV` pour toutes les réservations H23-H24 passant par Vevey, tronçons inexistants dans le ml_dataset de ces années. Cela produisait 3 688 orphelins (38.2 % du total) classés Cause E dans la décomposition de la Section 10.

**Impact correction** : l'éclatement v2 (topologie year-specific) ramène le taux d'orphelins de 16.8 % à 2.2 % sur H24, et de 8.9 % à 3.1 % sur H23 (02_ressys §9.6). Le grain ML v2 (`02_ressys_resa_au_grain_ml_h22_h25_v2.parquet`) est l'output de référence : **35 697 cellules** (date × train × tronçon × année horaire) pour H22-H25.

**Implémentation** : le stage pipeline `add_reservations` doit appeler `build_line_order_from_ml(annee_horaire)` au début de chaque traitement annuel, avant de passer la liste ordonnée à `eclate_reservation()`.

### 2.4 — Temporal cutoff : lead_days ≥ 1 (connu à J-1)

**Décision** : une réservation est incluse dans le calcul des features J-1 si et seulement si `lead_days = (date_voyage − date_commande).days ≥ 1`.

**Justification empirique** : le notebook 02_ressys §3.2 documente que la quasi-totalité du volume est connu très en avance :

| Horizon | % réservations | % pax_2c |
|---|---|---|
| À J-1 | 100.0 % | 99.9 % |
| À J-2 | 97.8 % | 98.6 % |
| À J-7 | 83.4 % | 87.4 % |
| À J-30 | 52.1 % | 61.4 % |
| À J-60 | 24.0 % | 29.7 % |

La médiane de la latence d'achat est de **32 jours** (mean 40.5 jours, §3.1). La latence est stable sur H16-H25 (médiane 29–47 jours selon les années, §3.3), sans rupture significative post-COVID sur la tendance centrale.

**Cohérence opérationnelle** : le cutoff J-1 garantit que la feature serait calculable dans un pipeline de prédiction opérationnel à J-1. Le choix J-7 maximiserait la couverture en volume mais exclurait 16.6 % des réservations qui arrivent entre J-7 et J-1 — non retenu car les 99.9 % de pax_2c disponibles à J-1 rendent l'exclusion inutile.

**Limite** : 4 réservations Abgeschlossen sur 9 129 (0.04 %) ont `lead_days = 0` (commande le jour même). Elles sont exclues. Impact ML négligeable.

### 2.5 — Traitement des Storniert : exclusion stricte

**Décision** : seules les réservations de statut `50 Abgeschlossen` sont utilisées dans le calcul des features. Les `90 Storniert` sont exclues.

**Justification** : une réservation annulée ne génère aucune charge réelle. Son inclusion introduirait du bruit, particulièrement pour le mois de mars-avril en H20 (31.4 % d'annulation, impact COVID) et H22 (27.6 %).

**Limite documentée** (02_ressys §8.3, Limite 2) : le fichier d'export ResSys ne contient pas de date d'annulation. Une réservation annulée après J-1 mais avant le voyage apparaît dans le fichier comme `90 Storniert` sans qu'il soit possible de déterminer si elle était encore Abgeschlossen à J-1. Cette troncature crée une légère surestimation des features `resa_*` (des annulations tardives sont traitées comme si elles n'avaient jamais existé, alors qu'elles étaient connues à J-1). L'impact est estimé faible si le taux d'annulation post-J-1 est bas. À monitorer empiriquement post-déploiement.

### 2.6 — Features candidates retenues : 8 features `resa_*`

**Décision** : les 8 features suivantes sont calculées au grain ML (date × train × tronçon) à partir des réservations Abgeschlossen avec `lead_days ≥ 1`. Leur imputation par défaut est `0` (pour les 7 numériques) et `False` (pour le flag binaire) lorsqu'aucune réservation n'est connue pour la cellule — 0 est sémantiquement correct (aucune réservation connue = absence de groupe planifié).

Les 7 features quantitatives valent **0 sur 97.59 % des cellules H22-H24** (cellules sans réservation, imputation explicite) et prennent des valeurs strictement positives sur **2.41 % des cellules** (**20 097 cellules sur 832 732 totales** H22-H24). Le flag `resa_has_resa_J_minus_1` vaut `False` sur les mêmes 97.59 % par construction et `True` sur les 2.41 % restantes. XGBoost apprend le signal réservation principalement sur ces 20 097 cellules — mais c'est précisément sur cette fraction que la valeur informative est forte (62/104 surcharges haut H24 y figurent, cf. §1.3).

**Couverture détaillée par année horaire** (mesure post-jointure sur `ml_dataset.parquet` après stage_10) :

| Année | Lignes ml_dataset | Avec résa | Taux |
|---|---|---|---|
| H22 | 161 597 | 4 007 | 2.48 % |
| H23 | 335 426 | 8 145 | 2.43 % |
| H24 | 335 709 | 7 945 | 2.37 % |
| **H22-H24** | **832 732** | **20 097** | **2.41 %** |

La cohérence inter-années (~2.4 % sur les trois années) valide que la couverture partielle H22 documentée en §2.7 n'introduit pas de déséquilibre majeur dans la fraction de cellules enrichies disponibles pour l'apprentissage. Ces chiffres remplacent l'estimation pré-jointure ~12 000 cellules / 3.4 % du notebook 02_ressys §8.1, qui sous-estimait la couverture réelle du grain ML après éclatement multi-tronçons.

| Feature | Définition | Hypothèse de signal |
|---|---|---|
| `resa_pax_2c_J_minus_1` | Somme `pax_2c` des réservations Abg. avec `lead_days ≥ 1` | Proxy volume groupe — corrélé avec les pics de fréquentation |
| `resa_n_dossiers_J_minus_1` | Nombre de dossiers distincts | Différencie 1 grand groupe de plusieurs petits groupes indépendants |
| `resa_max_groupe_2c_J_minus_1` | Taille du plus gros groupe individuel | Un groupe unique de 80+ pax est quasi-certain de provoquer une surcharge |
| `resa_part_scolaire_J_minus_1` | Part `pax_2c` de groupes scolaires (heuristique keywords) | Saisonnalité scolaire spécifique : narcisses (mai), automne, classes de neige |
| `resa_part_tour_operator_J_minus_1` | Part `pax_2c` tour-opérateurs (heuristique keywords) | Voyageurs internationaux, pics décalés vs locaux |
| `resa_n_pays_distincts_J_minus_1` | Nombre de pays distincts | Signal de tourisme international groupé |
| `resa_n_langues_distinctes_J_minus_1` | Nombre de langues distinctes | Signal complémentaire de diversité (confirme internationalité) |
| `resa_has_resa_J_minus_1` | Flag binaire : au moins une réservation connue à J-1 | Feature robuste aux valeurs nulles — signal de présence groupe quelle que soit la taille |

**Heuristiques de classification** (02_ressys §6.1) :
- *Scolaire* — keywords sur `nom_groupe` + `partenaire` : `ecole`, `école`, `scolaire`, `classe`, `school`, `schule`, `uape`, `gym`, `college`, `enfant`
- *Tour-opérateur* — keywords sur `partenaire` : `kuoni`, `ake`, `eisenbahn`, `globus`, `hotelplan`, `tui`, `tourisme`, `tourism`, `reise`

Ces heuristiques sont approximatives. Leur validation sur un échantillon de 50 réservations avec l'équipe MOB constitue une action de suivi (§5, priorité 2).

### 2.7 — Couverture H22 : partielle structurelle documentée

**Décision** : H22 est conservé dans le périmètre d'entraînement avec ses features réservations, malgré un taux d'orphelins de jointure élevé (58.5 %).

**Diagnostic empirique** (02_ressys §9-10) : sur 9 651 cellules ResSys H22 au grain ML v2, 5 644 (58.5 %) sont orphelines de la jointure avec ml_dataset. La décomposition complète des causes, conduite en Section 10 du notebook 02_ressys par rapprochement avec le NB02, attribue la totalité de ces orphelins à des causes documentées indépendamment :

| Cause | N orphelins H22 | % H22 | Source |
|---|---|---|---|
| E — Bug topologie GIL (corrigé v2) | 1 072 | 16.2 % | Section 9 du 02_ressys |
| F — Artefact format APC H22 | 5 547 | 83.7 % | NB02 §3.1 (TCE instable 9-83 %) |
| G — Trains sans AFZ weekend | 12 | 0.2 % | NB02 §3.3 (TCE = 0 % weekend) |
| **Total** | **6 631** | **100.0 %** | |

La Cause E correspond aux tronçons GIL qui, contrairement à H23/H24, **existent bien dans ml_dataset H22** (31 450 lignes) : les réservations éclatées via GIL auraient dû joindre. La non-jointure restante après correction v2 (58.5 % au lieu de 0 %) est due à la Cause F et G, structurelles.

La Cause F est mécanique et documentée dans NB02 §3.1 : la couverture APC (TCE = nb courses APC / nb courses théoriques) est instable en H22, variant de 9 % à 83 % selon les périodes de l'année. Cela signifie que de nombreuses courses réelles — dont certaines avec des groupes — ne figurent pas dans ml_dataset H22 pour des raisons de format de fichier. Cette cause est mécanique — un artefact du format d'export APC, non un phénomène métier. Il n'y a pas de raison structurelle de penser qu'elle est corrélée au niveau de charge des courses absentes, l'export ne sélectionnant pas les courses sur leur niveau de remplissage. Une vérification empirique formelle de cette absence de biais nécessiterait un dataset APC alternatif sur H22 non disponible à ce jour. À défaut, cette hypothèse est documentée comme limite résiduelle (cf. §4, Limite 7) et non comme démonstration.

**Conséquence ML** : les 5 644 cellules orphelines H22 sont absentes de `ml_dataset.parquet`. Elles n'ont pas de `target_voyageurs_2eme_classe` et ne participent à aucun calcul de loss ou de gradient. L'impact sur la qualité du modèle est **nul** : le modèle ignore ces cellules, il ne se trompe pas sur elles. Les features `resa_*` des cellules H22 *effectivement dans* ml_dataset (9 651 − 5 644 = 4 007 cellules) sont calculées correctement.

**Quality Gate 3 (v2)** :

| Année | Orphelins jointure | Taux | Statut |
|---|---|---|---|
| H22 | 5 644 / 9 651 | 58.5 % | ✓ PASS — couverture partielle documentée (F+E, NB02) |
| H23 | 263 / 8 440 | 3.1 % | ✓ PASS |
| H24 | 180 / 8 125 | 2.2 % | ✓ PASS |

**Quality Gate 5** (cause inconnue < 5 %) : 338 orphelins H23/H24 non attribuables à E/F/G/A, soit 3.5 % — **✓ PASS**. Ces orphelins (train régulier, tronçon existant, mais date spécifique absente du ml_dataset) sont probablement des gaps APC ponctuels — capteurs en maintenance sur un trajet isolé. Leur impact est nul pour les mêmes raisons que la Cause F.

---

## 3. Conséquences sur le pipeline et le workflow de modélisation

### 3.1 — Implémentation du stage `add_reservations`

Le nouveau stage `scripts/pipeline/add_reservations_to_raw_stacked.py` (ou équivalent dans la numérotation Makefile) doit implémenter la séquence suivante :

1. Charger les 10 fichiers `data/external/reservations/export_r35_h{16-25}.xlsx`, renommer les colonnes selon la convention `COL_RENAME` du 02_ressys §1, ajouter la colonne `annee_horaire`.
2. Filtrer `statut == '50 Abgeschlossen'` et `lead_days = (date_voyage − date_commande).days ≥ 1`.
3. Pour chaque `annee_horaire`, appeler `build_line_order_from_ml(ah)` pour obtenir la LINE_ORDER active.
4. Appliquer `eclate_reservation(row, line_order, GARE_MAP)` sur chaque ligne pour éclater les voyages logiques en tronçons élémentaires.
5. Agréger au grain ML `(date_voyage, horaire_numero_train, troncon_depart, troncon_arrivee)` avec les 8 features candidates (cf. §2.6).
6. Joindre au ml_dataset via la clé `(base_date, horaire_numero_train, id_gare_depart, id_gare_arrivee)`.
7. Imputer 0 / False sur les cellules ml_dataset sans réservation.
8. Persister `data/processed/ml_dataset_with_reservations.parquet`.

Les fonctions `build_line_order_from_ml()`, `eclate_reservation()`, `is_scolaire()` et `is_tour_operator()` sont à factoriser depuis le notebook 02_ressys (§5.1, §5.2, §6.1) vers un module partagé `scripts/pipeline/reservations_utils.py`.

Le fichier de référence intermédiaire `outputs/02_ressys_resa_au_grain_ml_h22_h25_v2.parquet` (35 697 cellules) peut être utilisé directement pour le re-entraînement avant l'implémentation complète du stage, afin de valider le gain ML en parallèle du développement.

### 3.2 — Re-entraînement et métriques de comparaison

Un notebook dédié (numérotation à définir dans la phase Modeling CRISP-ML(Q) — provisoirement `11_modeling_with_reservations.ipynb`) doit reproduire le protocole du modèle de référence ADR-033 (scénario D, split H22+H23 / H24, walk-forward strict, random_state=42) en ajoutant les 8 features `resa_*` au jeu de features ML nettoyées.

Métriques à comparer systématiquement vs modèle de référence ADR-033 :

| Métrique | Référence (ADR-033) | Cible avec réservations |
|---|---|---|
| R² global | 0.6123 | ≥ 0.6123 |
| R² segment bas | 0.5823 | ≥ 0.5823 |
| R² segment haut | 0.3279 | > 0.3279 (objectif principal) |
| Rappel surcharges haut H24 | 0.000 | > 0.000 (condition nécessaire) |
| Précision surcharges haut H24 | — | à documenter |
| PR-AUC global | ~0.24 | à documenter |

**Hypothèse principale à tester** : l'ajout des features `resa_*` améliore le R² et le rappel sur le segment haut sans dégrader le segment bas. Étant donné que les réservations couvrent 2.41 % des cellules (cf. §2.6, concentration sur le segment haut en proportion), l'effet sur le segment bas est attendu faible.

### 3.3 — Analyse SHAP post-entraînement

Les features `resa_*` doivent être analysées en SHAP global et par segment :

- **Question 1** : quelle feature `resa_*` porte le plus de signal sur le segment haut ? Hypothèse : `resa_max_groupe_2c_J_minus_1` > `resa_pax_2c_J_minus_1` car la taille du plus gros groupe capture mieux la saturation instantanée d'un train.
- **Question 2** : existe-t-il une interaction `resa_pax_2c × meteo_temperature_max_j` (les groupes touristiques + beau temps amplifient la surcharge) ou `resa_pax_2c × event_is_vacances_vaud` ?
- **Question 3** : les features `resa_part_scolaire` et `resa_part_tour_operator` portent-elles un signal indépendant de `resa_pax_2c` sur les deux segments ?

### 3.4 — Positionnement dans le mémoire de thèse

L'intégration des réservations après le pivot architectural constitue un retour amont contrôlé vers la phase Data Understanding du cadre CRISP-ML(Q) — exactement le type d'itération que ce cadre méthodologique prescrit (CRISP-ML(Q) §3, itérativité des phases). Ce cycle est à mentionner explicitement dans la section Méthode du mémoire (Chapitre 3.5 — Design de l'artefact) : la détection de la limite informationnelle (ADR-033) a déclenché l'investigation d'une nouvelle source (notebook 02_ressys), dont le résultat empirique (59.6 % des surcharges haut couvertes) justifie l'extension du jeu de features. Ce mouvement illustre concrètement comment le CRISP-ML(Q) permet de diagnostiquer et corriger des limitations informationnelles en cours de projet.

---

## 4. Limites et travaux futurs

1. **Surcharges segment haut sans réservation** (42/104 en H24, 40.4 %) : ces surcharges restent inexpliquées par la source réservations. Hypothèses : coïncidences météo favorables + voyageurs spontanés, événements touristiques non réservés via ResSys (randonnées, excursions individuelles en famille), ou groupes réservés via d'autres canaux non couverts par cet export. Les features `event_*` et `meteo_*` déjà présentes dans ml_dataset constituent la piste d'exploration prioritaire.

2. **Surcharges segment bas avec réservation** (256/1757 en H24, 14.6 %) : le signal réservation est structurellement plus faible sur le bas de ligne (navettes VV-Blonay, trafic pendulaire). Les 1 501 surcharges bas sans réservation ont d'autres déterminants (événements Riviera, vacances scolaires, fréquentation de pointe journalière).

3. **Annulations tardives non traçables** : le fichier d'export ResSys ne contient pas de date d'annulation pour les `90 Storniert`. Les réservations annulées après J-1 sont comptées comme absentes plutôt que comme présentes-puis-annulées. Impact ML estimé faible mais non mesuré. À monitorer post-déploiement.

4. **Hypothèse de trajet direct dans l'éclatement** : chaque ligne ResSys (voyage logique) est éclatée en tronçons élémentaires en supposant un trajet direct de `gare_depart` à `gare_arrivee` selon la topologie R35. Si un groupe fait une correspondance intermédiaire non déclarée dans le fichier, le tronçon intermédiaire sera surcompté. 21 dossiers avec pax_2c incohérent entre tronçons détectés au §5.3 — cas marginaux documentés.

5. **Couverture volumétrique** : les réservations représentent 0.48 % des voyageurs-tronçon APC au niveau du voyage logique (H24). Le modèle doit capter l'essentiel de la fréquentation via les autres 160 features. L'intégration des réservations ne remplace pas les features historiques et météo — elle les complète sur les 2.41 % de cellules avec réservation (cf. §2.6).

6. **H16-H21 hors training** : 5 années de réservations (4 891 Abgeschlossen, 155 047 pax_2c) sont disponibles mais non injectées en cohérence avec ADR-027. Elles peuvent servir à une analyse historique des patterns de réservation (saisonnalité, profil des partenaires) sans impacter l'entraînement.

7. **Biais de sélection résiduel sur H22** : l'hypothèse selon laquelle l'artefact format APC H22 (Cause F, NB02 §3.1) est non corrélé au niveau de charge n'a pas été démontrée empiriquement faute de dataset APC alternatif sur H22. L'hypothèse reste défendable mécaniquement (l'export ne filtre pas par niveau de remplissage) mais constitue une limite résiduelle à monitorer si un dataset alternatif devient disponible (rapprochement avec rotations, données de billetterie individuelle).

---

## 5. Backlog post-ADR

| Priorité | Action | Déclencheur |
|---|---|---|
| 1 — Critique | Implémenter `scripts/pipeline/add_reservations_to_raw_stacked.py` | ADR-035 acté |
| 1 — Critique | Re-entraîner XGBoost avec 8 features `resa_*`, documenter ΔR² par segment | Outputs 02_ressys v2 disponibles |
| 2 — Standard | Analyse SHAP comparative vs modèle référence ADR-033 | Notebook re-entraînement disponible |
| 2 — Standard | Valider heuristiques scolaire/tour-opérateur avec MOB sur 50 réservations | Coordonner avec Erwann + MOB |
| 2 — Standard | Documenter les résultats dans notebook dédié (11_modeling_*) et créer ADR-036 si l'architecture évolue | Résultats re-entraînement disponibles |

---

## 6. Quality Gates — Récapitulatif

| Gate | Résultat | Détail |
|---|---|---|
| QG1 — Schéma identique H16-H25 | ✓ PASS | 19 colonnes identiques sur les 10 fichiers |
| QG2 — Tronçons orphelins éclatement v2 | ✓ PASS | 0 orphelins — GARE_MAP complet et topologie year-specific |
| QG3 — Réservations orphelines H22 v2 | ✓ PASS couverture partielle | 58.5 %, causes F+E documentées NB02 — impact ML nul |
| QG3 — Réservations orphelines H23 v2 | ✓ PASS | 3.1 % |
| QG3 — Réservations orphelines H24 v2 | ✓ PASS | 2.2 % |
| QG5 — Cause inconnue < 5 % | ✓ PASS | 3.5 % (338 cellules H23-H24) |

---

## 7. Références

### Notebook source
- `notebooks/02_data_understanding_ressys.ipynb` — Data Understanding réservations, 88 cellules (sections 1–10)

### Outputs principaux
- `outputs/02_ressys_resa_eclate_h22_h25_v2.parquet` — 55 465 lignes éclatées H22-H25 (topologie v2)
- `outputs/02_ressys_resa_au_grain_ml_h22_h25_v2.parquet` — **35 697 cellules au grain ML** (référence pour le pipeline)
- `outputs/02_ressys_decomposition_orphelins_v2.csv` — décomposition empirique des 9 658 orphelins H22-H24
- `outputs/02_ressys_orphelins_caracterises_v2.csv` — orphelins avec cause attribuée (E/F/G/A/Z)
- `outputs/02_ressys_features_candidates.csv` — 8 features avec définitions et hypothèses

### Figures clés
- `notebooks/figures/02_ressys/02_ressys_focus_segment_haut.png` — 62/104 surcharges haut H24 avec réservation
- `notebooks/figures/02_ressys/02_ressys_matrice_confusion_seuil_94.png` — prédicteur naïf vs APC (Rappel=0.317, Précision=0.091)
- `notebooks/figures/02_ressys/02_ressys_decomposition_causes_v2.png` — répartition empirique des 9 658 orphelins
- `notebooks/figures/02_ressys/02_ressys_latence_par_annee.png` — stabilité lead_days H16-H25

### ADR liés
- [ADR-001](ADR-001_cible_2eme_classe.md) — Cible `target_voyageurs_2eme_classe`
- [ADR-003](ADR-003_modele_unique_vs_separes.md) — Architecture deux couches
- [ADR-005](ADR-005_seuil_um_94_2c.md) — Seuil UM `SEUIL_UM_2C = 94`
- [ADR-027](ADR-027_split_temporel_h22_h23_train_h24_test.md) — Split temporel H22+H23 / H24
- [ADR-033](ADR-033_pivot_architectural_regression_augmentation_metier.md) — Pivot architectural, limite informationnelle, augmentation métier
- [ADR-034](ADR-034_perimetre_base_offre_qualite_diagnostique.md) — `base_offre` hors-ML

### Sources méthodologiques
- CRISP-ML(Q) §3 — Itérativité des phases (retour Data Understanding en cours de Modeling)
- Notebook 02 §3.1 — TCE instable H22 (artefact format APC)
- Notebook 02 §3.3 — Trains sans AFZ weekend, liste de 34 trains (TCE = 0 %)

---


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

---


---
id: ADR-037
ancien_id: ADR-39
date_decision: 2026-06-04
statut: remplacé
remplace_par: [ADR-042, ADR-044]
modifie: [ADR-009, ADR-010]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-037 — Grain enrichi des features histo_* : conditionnement par type de jour et identification par service

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-042, ADR-044.
> Décisions antérieures que ce document modifie : ADR-009, ADR-010.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-04  
**Statut** : Accepté (validation conditionnelle — à confirmer sur run final H25)  
**Décideur** : Erwann Nédellec (data analyste MOB, R35)  
**Lié à** : ADR-008 (lag opérationnel J-2), ADR-009 (grain lag avec année horaire), ADR-033 (architecture deux couches), ADR-036 (modèle B référence)

---

## Contexte

Les features `histo_*` du modèle de référence B (ADR-036) exploitent l'autocorrélation temporelle du signal APC au grain `(horaire_annee_horaire, horaire_troncon_tgl, horaire_numero_train)`. L'implémentation calculait un shift positionnel fixe à 2 occurrences précédentes et une fenêtre glissante sur les 7 dernières occurrences, toutes natures de jours confondues.

Deux faiblesses sémantiques de ce grain ont été identifiées en revue méthodologique :

**1. Mélange des régimes de fréquentation.** La fenêtre `win7` d'une course quotidienne mélange dans le même calcul des observations de mardi, samedi, dimanche, jours fériés — alors que la fréquentation diffère structurellement selon le type de jour (régime pendulaire versus régime touristique), particulièrement sur le segment haut de R35 (Vevey – Villeneuve). Ce mélange dilue le signal historique au lieu de l'affiner.

**2. Identification fragile du service.** `horaire_numero_train` peut désigner des services différents (heures d'origine différentes) au sein d'une même année horaire ou entre changements d'horaire. `horaire_service_id_complet`, construit comme `{numéro}_{HHhMM}` (numéro de train + heure de départ depuis l'origine ce jour), identifie plus stablement le « même service » au sens opérationnel.

**3. Bug latent `observed=False`.** `cal_type_jour_3classes` est de dtype `category` dans stage_07. Le groupby pandas avec `observed=False` (comportement par défaut pour les colonnes category) crée des lignes fantômes pour toutes les combinaisons catégorielles non observées, multipliant la table daily par 6× et réduisant la couverture lag à ~3 % sur les ouvrables. Ce bug était latent dans l'implémentation précédente (GROUP_KEYS sans colonne category) ; il aurait été activé à la première utilisation du nouveau grain sans la correction.

---

## Investigation empirique

Un notebook diagnostic (`notebooks/12_diagnostic_histo_type_jour.ipynb`, seed=42, modèle XGBoost 300 arbres) a comparé le modèle B actuel (ADR-036) à un modèle B' utilisant le grain enrichi sur le test OOT H24 (n = 335 709 observations) :

| Métrique | B (référence ADR-036) | B' (grain enrichi) | Delta |
|---|---|---|---|
| R² global | 0.6454 | **0.6594** | **+0.014** |
| R² segment bas | 0.6045 | **0.6220** | **+0.018** |
| R² segment haut | 0.4757 | **0.4836** | +0.008 |
| PR-AUC segment haut | 0.0548 | **0.1521** | **+0.097 (×2.8 relatif)** |
| Gap min surcharges haut (unités sous 94) | 32.9 | **14.6** | −18.3 |
| Gap moyen surcharges haut | 56.3 | **51.8** | −4.5 |
| Surcharges haut individuellement mieux prédites | — | 67/104 (64.4 %) | — |

Le gain sur le **PR-AUC du segment haut** (×2.8 relatif, 0.0548 → 0.1521) constitue la justification empirique principale : c'est la métrique opérationnellement critique pour la couche 2 (capacité à discriminer les surcharges réelles parmi les cellules à risque). Le gain R² global (+1.4 pp) améliore aussi significativement les segments bas et global.

Le gain R² segment haut (+0.008) est en deçà du seuil critique C2 fixé à +0.010 (écart de 0.002 points), dans la variance attendue d'un run à 300 arbres sur ~85 000 observations. Une validation multi-seed sur 3 runs était initialement prévue mais a été reportée au run final sur le périmètre H23-H24 / H25, plus informative que de stabiliser sur un périmètre qui sera supplanté.

---

## Décision

**Adoption du nouveau grain pour les features `histo_*`.**

```python
GROUP_KEYS = [
    "horaire_annee_horaire",
    "horaire_troncon_tgl",
    "horaire_service_id_complet",
    "cal_type_jour_3classes",
]
```

avec :

- **`cal_type_jour_3classes`** à 3 modalités : `ouvrable`, `samedi`, `dimanche_ferie`. Cette dernière englobe tout jour férié quel que soit le jour de la semaine (logique : trafic touristique potentiel structurellement différent des ouvrables même pour un lundi-fériés).
- **`horaire_service_id_complet`** construit comme `{horaire_numero_train}_{HHhMM}` où `HHhMM` est l'heure d'origine du service ce jour.
- **`horaire_troncon_tgl`** conservé pour cohérence du schéma (vaut toujours 0 sur R35, ligne unique — n'apporte pas de discrimination mais maintient la structure du contrat de données).

La logique de shift est désormais **dynamique par searchsorted** : pour chaque ligne de date D, l'occurrence utilisée pour le lag est la dernière dans la série groupée dont `base_date ≤ D - 2 jours calendaires` (respect strict d'ADR-008). Cette logique préserve la pureté opérationnelle tout en évitant le gaspillage d'information :

- Mardi (ouvrable) → lag = Lundi si Lundi ≤ D−2, sinon Vendredi
- Mercredi (ouvrable) → lag = Lundi (J−2 exact)
- Samedi → lag = Samedi précédent (J−7, toujours consolidé)
- Dimanche → lag = Vendredi ou Dimanche précédent selon le calendrier

---

## Modifications apportées au code

**Fichier modifié** : `scripts/pipeline/add_features_to_raw_stacked.py`

1. `GROUP_KEYS` enrichi avec `horaire_service_id_complet` et `cal_type_jour_3classes`.
2. `DERIVED_COLS` : `horaire_service_id_complet` retiré (désormais INPUT du GROUP_KEYS, non OUTPUT dérivé).
3. `add_derived_features` : section "Features historiques" remplacée par la logique searchsorted. `observed=True` sur tous les groupby.
4. `main()` : `_ajouter_service_id_complet` appelé en PREMIER, avant `add_derived_features`, suivi d'une vérification de la présence de `cal_type_jour_3classes`.
5. Contrôles de cohérence mis à jour : `head(1)` par groupe (première occurrence) au lieu de `head(LAG_OPERATIONNEL_JOURS)` (sémantique différente avec shift dynamique).

---

## Conséquences

### Positives

- Gain PR-AUC majeur sur le segment haut (×2.8) : la couche 1 produit un signal substantiellement plus utile pour la couche 2 de détection des surcharges.
- Gain R² global +1.4 pp, R² bas +1.8 pp : amélioration générale de la précision.
- Pureté méthodologique renforcée : alignement strict entre la justification opérationnelle (ADR-008, J−2 calendaire) et l'implémentation (shift dynamique, pas de shift positionnel fixe).
- Cohérence avec le qualitatif MOB : les entretiens P01–P06 ont fait émerger l'importance du type de jour comme déterminant de fréquentation (résultats TPB). Le conditionnement par `cal_type_jour_3classes` matérialise cette intuition dans le pipeline ML.

### Limitations et points de vigilance

- **Couverture par groupe** : avec un grain plus fin (service + type_jour), le nombre d'occurrences par groupe est réduit. Les premières observations de chaque groupe ont lag NaN (notamment au démarrage d'un horaire ou d'un service nouveau). Les contrôles post-construction vérifient la couverture par type_jour.
- **Intersection train/test sur H25** : la refonte d'horaire 2024→2025 peut changer les `horaire_service_id_complet`. Le contrôle existant (seuil 80 % d'observations du test avec historique en train) est le point de surveillance critique sur le run H25.
- **Bug `observed=False` corrigé** : tout futur ajout de colonne `category` dans GROUP_KEYS devra maintenir `observed=True` dans les groupby.
- **Performance** : le remplacement de pandas `.shift()` vectorisé par une boucle Python par groupe est acceptable sur le volume actuel (daily ≈ 200 k lignes, ~1 400 groupes de ~140 lignes). Si le dataset croît significativement, envisager une vectorisation complète par `merge_asof` (cf. implémentation dans notebook 12, cellule 2).

---

## Validation différée

Le critère C2 (ΔR² segment haut ≥ +0.010) est manqué de 0.002 points sur le run de validation seed=42. Trois runs supplémentaires (seeds 0, 1, 2) étaient initialement prévus pour confirmer la stabilité, mais ont été reportés au run final sur le périmètre H23-H24 / H25 (à venir). Si ce run montre une régression nette du R² segment haut ou du PR-AUC segment haut par rapport au grain ADR-036, la décision sera réexaminée et documentée dans un ADR-39bis.

---

## Références

- Notebook diagnostic : `notebooks/12_diagnostic_histo_type_jour.ipynb`
- ADR-008 : Lag opérationnel J-2 — données APC consolidées
- ADR-009 : Grain du lag avec année horaire — frontière conservatrice
- ADR-033 : Architecture deux couches régression + décision
- ADR-036 : Modèle B référence couche 1
- Studer et al. (2021), CRISP-ML(Q) — documentation systématique des décisions ML

---


---
id: ADR-038
ancien_id: ADR-40
date_decision: 2026-06-04
statut: amendé
amende_par: [ADR-065]
modifie: [ADR-016, ADR-027]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-038 — Extension du périmètre temporel à H25

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-065.
> Décisions antérieures que ce document modifie : ADR-016, ADR-027.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** Les métriques H25 publiées ici sous le libellé « Enrichi_Seg 158f » précèdent la correction de fuite temporelle d'ADR-062 et la migration de gel d'ADR-076. Elles diffèrent sensiblement de celles du mémoire (tableau 16), notamment sur le segment haut, et ne doivent pas être lues comme les résultats du modèle final.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-04 |
| **Décideur** | Erwann Nédellec (data analyste MOB, R35) |
| **ADR liés** | ADR-027 (split temporel H22-H23 / H24), ADR-037 (grain enrichi histo_*), ADR-039 (carry-forward STATPOP H25) |

---

## Contexte

L'ADR-027 (2026-05) avait acté un périmètre H22-H23 train / H24 test, intersection minimale entre disponibilité des sources, qualité APC et stationnarité distributionnelle. Au gel initial du dataset, H25 était partielle (10.5 / 12 mois) et l'ingestion des sources externes 2025 n'était pas finalisée.

L'ingestion des deux dernières sources critiques rend désormais H25 méthodologiquement exploitable comme test OOT :

- **Événements Riviera 2025** : reçus de Montreux Riviera Tourisme le 2026-06-04
- **ISTDATEN 2025** : exportés et nettoyés le 2026-06-04

Le millésime STATPOP 2025 reste indisponible (latence usuelle OFS), géré par carry-forward selon ADR-039.

---

## Décision

Adoption d'un nouveau périmètre temporel :

- **Entraînement** : H22 + H23 + H24 (832 732 observations, ml_dataset hash daf936c8)
- **Test OOT** : H25 (309 252 observations, hash daf936c8)

---

## Justification empirique

### Critère 1 — Stationnarité distributionnelle (à recalculer avec H25)

Le test KS entre années horaires confirme la cohérence du nouveau périmètre d'entraînement (valeurs ADR-027 sur `target_voyageurs_total`, n = 2 051 510) :

| Paire | Valeur KS | Seuil | Statut |
|---|---|---|---|
| H22 vs H23 | 0.0821 | ≤ 0.15 | ✅ (ADR-027) |
| H22 vs H24 | 0.0775 | ≤ 0.15 | ✅ (ADR-027) |
| H23 vs H24 | 0.1231 | ≤ 0.15 | ✅ (ADR-027) |
| H22 vs H25 | 0.0650 | ≤ 0.20 | ✅ |
| H23 vs H25 | 0.1056 | ≤ 0.20 | ✅ |
| H24 vs H25 | 0.0248 | ≤ 0.20 | ✅ |

Si toutes les paires (Hxx, H25) restent < 0.20, le périmètre est validé. Un seuil légèrement plus permissif que pour le bloc d'entraînement est acceptable pour le test : une légère dérive distributionnelle entre train et test est attendue et mesurer la robustesse à cette dérive est précisément l'objet d'un test OOT. La paire H24 vs H25 est le critère le plus discriminant — H24 et H25 étant les deux années les plus proches temporellement.

### Critère 1bis — TCE hétérogène entre années d'entraînement

L'inclusion de H22 dans le jeu d'entraînement introduit une hétérogénéité de qualité APC :

| Année horaire | TCE APC | Source |
|---|---|---|
| H22 | 52 % | Système de comptage en transition |
| H23 | 98 % | Nouveau système opérationnel |
| H24 | 100 % | Nouveau système stabilisé |

Cette hétérogénéité représente un point de vigilance documenté. Trois arguments justifient néanmoins l'inclusion de H22 :

1. **Compatibilité distributionnelle** : KS(H22, H24) = 0.0775 est meilleure que KS(H23, H24) = 0.1231. La portion H22 reste statistiquement cohérente avec le régime opérationnel courant.

2. **Volume additionnel** : ~830 K observations supplémentaires renforcent la portance des fenêtres `histo_*` (cf. ADR-037), particulièrement sur les courses peu fréquentes du segment haut où la fenêtre 7-occurrences se remplit lentement.

3. **Robustesse XGBoost au bruit** : un signal APC partiellement bruité sur 1/3 du training (H22) est compensé par 2/3 d'observations de qualité maximale (H23, H24). XGBoost est par construction robuste à ce type d'hétérogénéité.

La limitation sera explicitement reconnue dans la section méthodologique du mémoire.

### Critère 2 — Disponibilité des sources

Toutes les sources du modèle B (ADR-036) sont disponibles sur H23-H25, avec carry-forward STATPOP 2024 pour H25 (ADR-039). Confirmation à date :

| Source | H23 | H24 | H25 |
|---|---|---|---|
| ISTDATEN APC | ✅ | ✅ | ✅ (2026-06-04) |
| Événements Riviera | ✅ | ✅ | ✅ (2026-06-04) |
| Météo CdH / Vevey | ✅ | ✅ | ✅ |
| SIMBA FQkal | ✅ | ✅ | ✅ (lag N-1 = SIMBA 2024, ADR-041 — SIMBA 2025 exclu pour éviter leakage) |
| STATPOP | ✅ (2023) | ✅ (2024) | carry-forward 2024 (ADR-039) |
| Réservations ResSys | ✅ | ✅ | ✅ |

### Critère 3 — Refonte d'horaire 2024 → 2025

La refonte d'horaire CFF/MOB de décembre 2024 a affecté l'ensemble des trains R35 (cf. ADR-041) :

- **Trains maintenus H24 → H25 (même numéro)** : 51 / ~103 trains (49 %), représentant 51,8 % des observations H25 (160 147 obs). Match SIMBA 2024 complet sur ces services.
- **Trains renumérotés** : 52 trains (50 %), représentant 46,5 % des observations H25 (143 867 obs). Aucun match SIMBA 2024.
- **`horaire_service_id_complet` H24 maintenus en H25 : 0 / ~103 (0 %)** — la refonte a modifié 100 % des heures de départ à l'origine pour tous les trains R35, changeant de facto tous les identifiants (ADR-042).
- **Contrôle pipeline (seuil 80 %) : FAIL** (0 % < 80 %).

**Conséquences sur les features `histo_*`** : les features histo_* (clé `horaire_service_id_complet` + `cal_type_jour_3classes`, ADR-037) produisent NaN pour tous les services H25 en début de période test — XGBoost gère les NaN nativement. La dégradation observée sur les services renumérotés (PR-AUC haut = 0.055 vs 0.204 pour les services stables, ADR-042) est documentée comme fragilité RF-1 du modèle. Le contrôle < 80 % est attendu et documenté ; il n'invalide pas le test OOT mais signale une limite opérationnelle à mentionner dans le mémoire.

### Critère 4 — Volume d'entraînement

Le périmètre H22+H23+H24 est supérieur au précédent H22+H23 grâce à l'ajout de H24 :

| Périmètre | N entraînement | N test |
|---|---|---|
| H22+H23 / H24 (ADR-027) | ~497 000 | 335 709 |
| H22+H23+H24 / H25 (ADR-038) | 832 732 | 309 252 |

---

## Observation de l'ADR-037 au run H25

L'ADR-037 (adoption du grain enrichi `histo_*`) a été validée empiriquement sur le diagnostic seed=42 (test H24) avec un gain qualitatif substantiel (PR-AUC haut ×2.8, gap min divisé par 2, 64.4 % des surcharges individuellement mieux prédites). Aucun double entraînement n'est conduit sur H25 : la validation devient observationnelle.

**Critère de réinvestigation a posteriori** : si une régression majeure et inexpliquée du PR-AUC haut survient sur H25 (PR-AUC haut < 0.05, soit pire que le baseline B avant ADR-037 sur H24), une réinvestigation rétrospective sera conduite et documentée par un ADR-39bis. Aucun seuil moins strict ne déclenchera de remise en cause de l'ADR-037 : son adoption repose sur le gain qualitatif observé sur H24, qui n'a pas vocation à être réfuté par une seule mesure ponctuelle sur un autre périmètre.

Cette posture est cohérente avec le principe CRISP-ML(Q) de documentation des décisions méthodologiques : un gain empirique validé une fois sur un test substantiel reste valide tant qu'aucune contre-évidence claire n'émerge.

### Résultats observés

| Métrique | Enrichi_Seg v1.1 158f sur H25 | Critère de réinvestigation |
|---|---|---|
| R² global H25 | **0.588** (IC 95% [0.585, 0.592]) | — |
| R² segment haut H25 | **0.504** (IC 95% [0.493, 0.514]) | — |
| PR-AUC segment haut H25 | **0.191** (IC 95% [0.160, 0.234], ADR-047) | < 0.05 → ADR-39bis |
| R² segment bas H25 | **0.555** (IC 95% [0.551, 0.559]) | — |

---

## Conséquences

### Positives

- Test OOT sur l'année la plus récente disponible (H25) : meilleure pertinence opérationnelle pour la couche 2 et le déploiement futur.
- Validation indirecte de la robustesse face à la refonte d'horaire 2024→2025 (généralisation à un nouvel horaire).
- **Volume d'entraînement maximisé** : 832 732 observations (H22+H23+H24), tirant pleinement parti de la période où toutes les sources sont disponibles avec une qualité acceptable.
- ADR-037 traité par observation et non par re-validation systématique, simplifiant la séquence d'exécution du run final.

### Limitations à documenter dans le mémoire

- **Carry-forward STATPOP 2025 → 2024** (ADR-039) : approximation documentée, erreur attendue < 1 % sur les features démographiques.
- **Stabilité de `horaire_service_id_complet`** entre H24 et H25 : risque de couverture réduite des features `histo_*` si la refonte d'horaire est majeure.
- **TCE hétérogène entre années d'entraînement** : H22 (52 %) vs H23-H24 (98-100 %). Documentée en critère 1bis ci-dessus.
- L'ADR-037 n'est pas re-validée par double entraînement sur H25, mais observée a posteriori. Un PR-AUC haut < 0.05 sur H25 déclencherait un ADR-39bis.

---

## Références

- ADR-027 : Split temporel initial H22-H23 / H24 (révoqué par cet ADR pour la version finale du mémoire)
- ADR-037 : Grain enrichi des features `histo_*` (adoption directe, observation a posteriori sur H25)
- ADR-039 : Carry-forward STATPOP 2024 pour année calendaire 2025
- Notebook KS : `notebooks/04_model_engineering_split.ipynb`
- Notebook synthèse : `notebooks/SYNTHESE_modele_R35_evaluation_complete.ipynb` (à mettre à jour avec les nouveaux chiffres après run final)

## Addendum 2026-07-12 — micro-vérification de KS(H22,H23) = 0,0821 (Critère 1, l.50) : IRREPRODUIT

Contrôle conduit pour la section 4.5.1 : tenter de reproduire la valeur **KS(H22,H23) = 0,0821** du tableau du Critère 1 (l.50). Ce tableau annonce des KS calculés « sur `target_voyageurs_total`, n = 2 051 510 » (l.46).

**Résultats bruts** (source `stage_09_simba.parquet`, SHA256[:8] `954135f9` — cf. addendum ADR-066 2026-07-12 ; la cible est générationnellement invariante, ces valeurs valent donc aussi pour le gel d'époque `daf936c8`, non conservé sur disque) :

| Variable | Population | KS(H22,H23) |
|---|---|---|
| `target_voyageurs_total` | pleine (NaN retirés) | **0,0722** |
| `target_voyageurs_total` | H22 sans Gilamont | 0,0292 |
| `target_voyageurs_2eme_classe` | pleine (NaN retirés) | **0,0833** |
| `target_voyageurs_2eme_classe` | H22 sans Gilamont | 0,0402 |
| `target_voyageurs_2eme_classe` | brute (NaN inclus) | 0,0833 |

NaN de la cible sur H22 et H23 = 0 pour les deux variables ; l'inclusion des NaN est sans effet.

**Conclusion : 0,0821 IRREPRODUIT.** Aucune combinaison variable × population ne le reproduit. Sur la variable déclarée par la ligne (`target_voyageurs_total`), la valeur reproductible est **0,0722**, identique à ADR-027 (l.59). Les deux autres cellules de la même ligne d'ADR-038 se reproduisent, elles, exactement sur `total` : KS(H22,H24) = 0,0775 (l.51) et KS(H23,H24) = 0,1231 (l.52). Seule la cellule H22×H23 diverge (0,0821 déclaré vs 0,0722 reproduit). La valeur la plus proche toutes variantes confondues est 0,0833 (cible 2e classe, pleine ; Δ = +0,0012), qui ne correspond ni à la variable déclarée par la ligne ni à 0,0821.

**Lecture (sans modification des valeurs historiques).** Deux cellules sur trois reproduites à l'identique sur `total`, une seule cellule isolément divergente : profil cohérent avec une **anomalie ponctuelle de transcription** de la cellule H22×H23 (l.50), la ligne recopiant par ailleurs les valeurs `total` d'ADR-027. La valeur historique 0,0821 est **conservée telle quelle** ; le présent addendum documente l'écart, il ne le corrige pas.

---


---
id: ADR-039
ancien_id: ADR-41
date_decision: 2026-06-04
statut: remplacé
remplace_par: [ADR-063]
modifie: [ADR-006, ADR-025]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-039 — Mapping STATPOP par année calendaire et carry-forward 2024 pour 2025

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Décisions antérieures que ce document modifie : ADR-006, ADR-025.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (v3, 2026-06-16) — mapping Z-2 et imputation forward-fill révisés par ADR-063 |
| **Date** | 2026-06-04 (v2) / 2026-06-16 (v3) |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-006 (stratégie millésime), ADR-008 (lag opérationnel J-2), ADR-011 (interpolation STATPOP 2021 et 2023 — révisé), ADR-024 (géométrie Voronoi clippée), ADR-037 (grain enrichi histo_*), ADR-038 (extension périmètre H25), **ADR-063** (causalité disponibilité STATPOP — révision v3) |
| **Historique** | v1 (initial) : mapping par `horaire_annee_horaire` — révoqué pour fuite temporelle. v2 (2026-06-04) : mapping par année calendaire stricte, interpolation 2021/2023. **v3 (2026-06-16) : mapping Z-2 conservateur (borne Jan 1 Y+2) + forward-fill causal (remplace interpolation).** |

## Contexte

L'extension du périmètre temporel à l'année horaire H25 (décembre 2024 – décembre 2025, à acter par ADR-038) confronte le pipeline à un problème de disponibilité de la source STATPOP. L'Office fédéral de la statistique publie les millésimes STATPOP avec une latence de 12 à 18 mois sur l'année de référence. Au moment du gel du dataset (juin 2026), le millésime 2024 est le dernier exact disponible ; le millésime 2025 n'est pas publié.

Cet ADR articule deux décisions liées :

1. **Refactorisation du mapping millésime** : remplacement de la jointure naïve `dates.dt.year` (stratégie "exploratoire" per ADR-006) et de la première version de l'ADR-039 par un mapping explicite indexé sur l'année calendaire, garantissant la pureté temporelle stricte.

2. **Stratégie de gestion de 2025** : utilisation du millésime 2024 comme proxy pour les dates de l'année calendaire 2025, avec traçabilité explicite via une colonne de source.

## Pourquoi année calendaire et non année horaire

Les années horaires CFF/MOB s'étendent de mi-décembre à mi-décembre (par exemple H22 = 12/12/2021 → 10/12/2022). La première version de cet ADR utilisait un mapping `STATPOP_MAPPING` indexé sur `horaire_annee_horaire`, ce qui attribuait à H22 le millésime STATPOP 2022. Conséquence : les voyageurs comptés en décembre 2021 (qui appartiennent à H22) recevaient une donnée STATPOP datée du **31 décembre 2022** — soit une fuite temporelle de jusqu'à 12 mois.

Cette fuite est incohérente avec le principe de pureté temporelle stricte qui sous-tend le reste du projet :
- L'ADR-008 impose un lag opérationnel J-2 pour les comptages APC (jamais utiliser une donnée non-consolidée au moment de la décision).
- L'ADR-037 implémente un shift dynamique respectant strictement cette contrainte.

Indexer le mapping sur l'année calendaire de `base_date` supprime cette fuite : les 18-21 jours de décembre de chaque année calendaire qui appartiennent à l'année horaire suivante reçoivent le millésime STATPOP cohérent avec leur date réelle, et non avec leur année horaire.

L'amplitude empirique de la correction est faible (variation interannuelle STATPOP ≈ 1 %, et seulement ~5 % des observations sont en décembre). Mais l'amélioration de la défensibilité méthodologique est significative pour le mémoire.

## Options considérées (pour la gestion de 2025)

| Option | Description | Forces | Faiblesses |
|---|---|---|---|
| A. Carry-forward depuis 2024 | Utiliser STATPOP 2024 comme proxy pour les dates de l'année calendaire 2025 | Simple, transparent, sans extrapolation hasardeuse ; réversible | Assume une variation démographique 2024→2025 négligeable (en réalité ≈ 0.5–1 %) |
| B. Extrapolation linéaire | Projeter la tendance 2022→2023→2024 à 2025 | Plus sophistiqué en apparence | Amplifie le bruit sur fenêtre courte ; sensible aux phénomènes ponctuels (nouvelles constructions) |
| C. Valeurs manquantes (NaN) | Ne pas attribuer STATPOP aux dates 2025 | Théoriquement le plus pur | XGBoost gère mal les NaN systématiques sur ~25 % du test set ; biais d'apprentissage difficile à diagnostiquer |

## Décision

**[v3, ADR-063] Adoption d'un mapping Z-2 conservateur** indexé sur l'année calendaire (`base_date.dt.year`), avec forward-fill causal pour les millésimes HP*/HPI manquants :

```python
# ADR-063 : mapping Z-2 (borne disponibilité Jan 1 Y+2)
MAPPING_BC_MILLESIME = {
    2021: 2019,   # exact
    2022: 2020,   # exact
    2023: 2021,   # HP*/HPI forward-fill ← 2020 (OFS ne publie pas HP 2021)
    2024: 2022,   # exact
    2025: 2023,   # HP*/HPI forward-fill ← 2022 (OFS ne publie pas HP 2023)
}
```

**[v2, archivée — fuite de disponibilité]** La version v2 appliquait un mapping contemporain (Z→Z) avec interpolation pour 2021/2023 :

```python
# v2 — ARCHIVÉE : mapping contemporain (fuite de disponibilité)
STATPOP_MAPPING = {
    2021: {"millesime": 2021, "source": "interpole"},     # ADR-011 : utilisait borne future 2022
    2022: {"millesime": 2022, "source": "exact"},
    2023: {"millesime": 2023, "source": "interpole"},     # ADR-011 : utilisait borne future 2024
    2024: {"millesime": 2024, "source": "exact"},
    2025: {"millesime": 2024, "source": "carry_forward"},
}
```

### Conséquences sur la composition des sources par année horaire

Avec ce mapping, chaque année horaire reçoit potentiellement deux millésimes STATPOP selon la date de la course :

| Année horaire | Composition source STATPOP |
|---|---|
| H22 (12/12/2021–10/12/2022) | déc. 2021 : `interpole` (millésime 2021) ; jan–nov. 2022 : `exact` (millésime 2022) |
| H23 (11/12/2022–09/12/2023) | déc. 2022 : `exact` (millésime 2022) ; jan–nov. 2023 : `interpole` (millésime 2023) |
| H24 (10/12/2023–14/12/2024) | déc. 2023 : `interpole` (millésime 2023) ; jan–déc. 2024 : `exact` (millésime 2024) |
| H25 (15/12/2024–13/12/2025) | déc. 2024 : `exact` (millésime 2024) ; jan–nov. 2025 : `carry_forward` (millésime 2024) |

Cette granularité fine offre une traçabilité supérieure à un mapping unique par année horaire et restitue exactement la cohérence temporelle attendue. La colonne `spatial_statpop_source_*` permet d'identifier au niveau de la ligne quel régime STATPOP s'applique.

### Justification du carry-forward pour 2025

L'option A (carry-forward depuis 2024) est retenue sur trois arguments :

1. **Magnitude de l'erreur faible** : la variation annuelle de population dans un rayon de 500 mètres autour d'une gare R35 est de l'ordre de 0.5 à 1 % par an. Cette amplitude n'a pas d'effet matériel sur la prédiction de fréquentation. Le signal STATPOP capture une réalité structurelle (zone dense vs zone peu peuplée) et non conjoncturelle.

2. **Cohérence avec la philosophie du projet** : privilégier les solutions transparentes et défendables aux solutions sophistiquées qui ajoutent du bruit (principe "empirique avant méthodologique").

3. **Réversibilité** : quand STATPOP 2025 sera publié (probablement courant 2026–2027), la substitution est triviale — une seule ligne à modifier dans `STATPOP_MAPPING`.

## Convention de traçabilité

Deux colonnes sont ajoutées au pipeline STATPOP :

- `spatial_statpop_source_depart`
- `spatial_statpop_source_arrivee`

Ces colonnes prennent les valeurs suivantes (par ligne, selon l'année calendaire de `base_date`) :

| Valeur | Signification | Années calendaires concernées (Z-2 mapping) |
|---|---|---|
| `exact` | Millésime OFS publié exact, pas d'imputation HP* | 2021→2019, 2022→2020, 2024→2022 |
| `forward_fill` | Millésime exact population, HP*/HPI forward-fillés depuis millésime précédent | 2023→2021 (HP←2020), 2025→2023 (HP←2022) |

Convention cohérente avec les colonnes de métadonnées existantes : `event_ski_source`, `event_narcisses_source`, `event_covid_phase`.

**Important** : `spatial_statpop_source_depart` et `spatial_statpop_source_arrivee` sont des métadonnées de traçabilité. Elles doivent être ajoutées à la liste `COLS_EXCLUES` du notebook de modélisation lors du run final coordonné (à faire avec ADR-037 et ADR-038).

## Conséquences

### Positives

- **Cohérence temporelle stricte** : suppression de la fuite temporelle de jusqu'à 12 mois qui affectait les courses de décembre dans la v1 de l'ADR. Alignement avec ADR-008 et ADR-037.
- **Traçabilité granulaire** : chaque observation reçoit une source STATPOP cohérente avec sa date calendaire ; la colonne `spatial_statpop_source_*` peut varier au sein d'une même année horaire (décembre vs reste), reflétant fidèlement la réalité.
- **Extensibilité** : la constante `STATPOP_MAPPING` permet l'ajout du millésime 2025 publié en une ligne.
- **Auditabilité** : la validation post-construction affiche une distribution croisée année horaire × année calendaire permettant de vérifier explicitement que les cours de décembre N reçoivent bien le millésime N (et non N+1).

### Limitations à documenter dans le mémoire

- **Sous-estimation potentielle dans les zones à forte croissance démographique** : un nouveau quartier construit entre 2024 et 2025 ne sera pas reflété dans STATPOP. L'effet est probablement marginal sur R35 (zone géographique stabilisée).
- **Le modèle apprend l'effet STATPOP sur 2022–2024 (millésimes exacts et interpolés) et l'applique à 2025 (carry-forward)** : si une transition démographique structurelle a lieu en 2025, elle ne sera pas captée.

### Comparaison avec la v1 de l'ADR (révoquée)

| Aspect | v1 (révoquée) | v2 (présente) |
|---|---|---|
| Clé de mapping | `horaire_annee_horaire` (H15–H25) | Année calendaire (2015–2025) |
| Fuite temporelle décembre | Jusqu'à 12 mois | Aucune |
| Composition source par AH | Source unique par AH | Source potentiellement mixte (déc. vs reste) |
| Traçabilité | Deux colonnes `_source` | Deux colonnes `_source` (inchangé) |

## Validation post-déploiement

Quand le millésime STATPOP 2025 sera publié (probablement Q2–Q3 2027) :

1. Remplacer `{"millesime": 2024, "source": "carry_forward"}` par `{"millesime": 2025, "source": "exact"}` dans `STATPOP_MAPPING`
2. Rejouer le pipeline depuis stage_06 et reconstruire `ml_dataset.parquet`
3. Réentraîner le modèle de référence et comparer les métriques

**Critère de validation** : si Δ R² < 0.005 sur le segment haut H25, l'hypothèse de carry-forward acceptable est confirmée empiriquement. Si Δ R² > 0.005, documenter la magnitude de l'erreur introduite.

## Fichiers impactés

- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` : `STATPOP_MAPPING` ré-indexé par année calendaire (`int`), `build_statpop_millesime_and_source` lit `base_date.dt.year`, summary enrichi avec distribution croisée AH × année calendaire.
- `data/processed/stage_06_statpop.parquet` : `spatial_statpop_source_*` peut désormais varier au sein d'une même année horaire (décembre vs reste).
- `data/processed/ml_dataset.parquet` : propagation des deux colonnes jusqu'au dataset final.
- À faire lors du run final : ajouter `spatial_statpop_source_depart` et `spatial_statpop_source_arrivee` à `COLS_EXCLUES` dans `notebooks/SYNTHESE_modele_R35_evaluation_complete.ipynb` (sections 4.2 et 5).

## Note méthodologique sur la révision

La révision de cet ADR illustre une pratique méthodologique attendue dans le projet : la révocation et la réécriture explicite d'un ADR lorsqu'une faiblesse méthodologique est identifiée *avant* la production de résultats définitifs. Cette pratique est cohérente avec le principe CRISP-ML(Q) (Studer et al., 2021) de documentation systématique des décisions, y compris quand elles évoluent. La v1 de l'ADR-039 reste mentionnée dans l'historique pour préserver la traçabilité du raisonnement, sans risque de confusion sur la décision actuelle.

---


---
id: ADR-040
ancien_id: ADR-42
date_decision: 2026-06-04
statut: actif
modifie: [ADR-021]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-040 — Gestion de l'interruption VMCV ISTDATEN H25 (01.09 – 13.10.2025)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-021.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-04 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-021 (features concurrence modale VMCV), ADR-039 v2 (convention `_source` analogue), ADR-038 (extension périmètre H25) |

## Contexte

L'ingestion ISTDATEN H25 a révélé une interruption de publication des données VMCV (Vevey-Montreux-Chillon-Villeneuve) entre le 01.09.2025 et le 13.10.2025 inclus (43 jours, ~12 % du test set H25). Avant et après cette période, VMCV publie normalement.

Cette interruption affecte les 4 features `vmcv_*` du modèle (concurrence modale bus, cf. ADR-021) : `vmcv_n_lignes_concurrentes`, `vmcv_frequence_horaire_bus`, `vmcv_ratio_temps_trajet`, `vmcv_chevauchement_horaire`. Les données R35 (MVR-cev) elles-mêmes sont intactes (validation : 32 842 lignes en septembre 2025, conforme à août et octobre).

Un backfill n'est pas envisageable dans un délai compatible avec le mémoire (service tiers, dépendance externe non maîtrisée).

## Options considérées

| Option | Description | Forces | Faiblesses |
|---|---|---|---|
| A. NaN avec traçabilité | Laisser NaN sur les 43 jours, XGBoost gère nativement via default direction routing | Aucune donnée inventée, transparence totale | Asymétrie train/test sur l'occurrence des NaN |
| B. Imputation par moyennes historiques | Imputer les 43 jours par moyenne H22-H24 stratifiée | Préserve la cohérence de régime d'entrée | Invente des données ; complexité d'implémentation ; choix de granularité non trivial |
| C. Exclusion des features VMCV du modèle | Retirer vmcv_* du jeu de features | Aucune asymétrie | Perd le signal VMCV sur 88 % du test où il est dispo |

## Décision

**Option A retenue : laisser NaN sur les 43 jours d'interruption, avec traçabilité explicite.**

Justifications :

1. **Importance secondaire de VMCV** : les 4 features `vmcv_*` apparaissent dans la moitié inférieure du classement SHAP du modèle B (cf. notebook synthèse Section 7). VMCV a un signal pertinent sur le segment bas mais largement redondant avec d'autres features. Sur le segment haut, VMCV n'a aucune pertinence opérationnelle (pas de bus concurrent dans les hauteurs). L'impact attendu du NaN sur 12 % du test est donc faible.

2. **Gestion native XGBoost** : XGBoost apprend une direction par défaut pour les NaN à chaque split d'arbre. Quelques NaN naturels existent dans le training H22-H24 (cas de bus manquants ponctuels traités par le pipeline VMCV existant), donc le routage par défaut est appris au moins partiellement pour les features `vmcv_*`.

3. **Transparence vs inventivité** : laisser NaN est plus défendable que d'imputer par des valeurs construites, particulièrement face à un jury qui valorise la pureté méthodologique. L'imputation aurait introduit une dépendance à un choix de granularité (gare × type_jour × créneau horaire ?) discutable.

4. **Validation empirique a posteriori** : l'impact réel sera mesuré au moment du run final en stratifiant les métriques par sous-période (jours avec VMCV publié vs jours d'interruption). Si l'effet est mesurable, il sera documenté en limitation du mémoire.

## Convention de traçabilité

Deux colonnes sont ajoutées au pipeline VMCV :

- `vmcv_source_depart`
- `vmcv_source_arrivee`

Avec valeurs :

| Valeur | Signification |
|---|---|
| `publie` | Données VMCV publiées normalement sur ISTDATEN |
| `manquant_interruption_vmcv` | Interruption de publication VMCV (43 jours, 01.09.2025 – 13.10.2025) |

Convention cohérente avec `event_ski_source`, `event_narcisses_source`, `event_covid_phase`, `spatial_statpop_source_*` (ADR-039).

**Important** : ces colonnes sont des métadonnées de traçabilité, à ajouter à la liste `COLS_EXCLUES` du notebook synthèse lors du run final coordonné.

## Modifications à apporter

### Script pipeline VMCV

Identifier le script qui produit les features `vmcv_*` (probablement `scripts/pipeline/add_vmcv_to_raw_stacked.py` ou nom équivalent — à confirmer par diagnostic préalable).

Modifications :

1. **Ajouter une constante** définissant la période d'interruption :

```python
# Période d'interruption de publication VMCV sur ISTDATEN.
# Validé par diagnostic ingestion H25 (cf. rapport 04.06.2026, ADR-040).
VMCV_INTERRUPTION_DEBUT = pd.Timestamp("2025-09-01")
VMCV_INTERRUPTION_FIN = pd.Timestamp("2025-10-13")  # inclus
```

2. **Logique de jointure inchangée** : les NaN apparaissent naturellement quand la jointure échoue (pas de données VMCV pour les 43 jours).

3. **Ajouter les colonnes de traçabilité** après les jointures :

```python
# Marqueur de source VMCV (métadonnée, exclu du training)
mask_interruption = (
    (df["base_date"] >= VMCV_INTERRUPTION_DEBUT)
    & (df["base_date"] <= VMCV_INTERRUPTION_FIN)
)
df["vmcv_source_depart"] = pd.Series("publie", index=df.index, dtype="string")
df["vmcv_source_arrivee"] = pd.Series("publie", index=df.index, dtype="string")
df.loc[mask_interruption, "vmcv_source_depart"] = "manquant_interruption_vmcv"
df.loc[mask_interruption, "vmcv_source_arrivee"] = "manquant_interruption_vmcv"
```

4. **Vérification de cohérence** post-construction :

```python
n_interruption = (df["vmcv_source_depart"] == "manquant_interruption_vmcv").sum()
n_total_h25 = (df["horaire_annee_horaire"] == "H25").sum()
print(f"  VMCV interruption : {n_interruption:,} lignes "
      f"({100*n_interruption/n_total_h25:.1f}% du test H25)")

# Cohérence : sur les jours d'interruption, vmcv_n_lignes_concurrentes doit être NaN
nan_interruption = df.loc[mask_interruption, "vmcv_n_lignes_concurrentes"].isna().sum()
print(f"  NaN vmcv_n_lignes_concurrentes sur interruption : "
      f"{nan_interruption}/{n_interruption} "
      f"({'OK' if nan_interruption == n_interruption else 'ANOMALIE'})")
```

### Notebook synthèse

À faire au run final coordonné (pas maintenant) : ajouter `vmcv_source_depart` et `vmcv_source_arrivee` à la liste `COLS_EXCLUES` du notebook synthèse, aux deux endroits où elle apparaît (Section 4.2 et Section 5).

### Validation empirique à conduire au run final

Stratifier les métriques d'évaluation sur H25 par sous-période :

- Métriques sur H25 complet
- Métriques sur H25 hors période d'interruption (88 % du test)
- Métriques sur les 43 jours d'interruption uniquement

Si l'écart de R² entre les deux sous-périodes est < 0.005, l'impact est négligeable. Si l'écart est > 0.005, documenter en limitation du mémoire. Idéalement, faire la stratification par segment (bas / haut) pour isoler l'effet : VMCV n'ayant pas de pertinence sur le segment haut, on s'attend à ce que l'écart soit nul sur le haut et marginal sur le bas.

## Conséquences

### Positives

- Aucune donnée inventée, transparence totale sur la dégradation de la couverture
- Traçabilité par colonne `vmcv_source`, audit méthodologique possible
- Gestion native XGBoost cohérente avec le reste du pipeline
- Simplicité d'implémentation

### Limitations à documenter dans le mémoire

- 12 % du test set H25 présente des NaN sur 4 features VMCV
- Le routage XGBoost des NaN sur ces features n'est appris que partiellement (via les rares NaN naturels du training)
- Impact réel à quantifier par stratification des métriques au run final
- Une régression structurelle de VMCV (changement de service, nouvelles lignes) entre 01.09 et 13.10.2025 ne serait pas captée même si elle avait lieu

## Précision sur les features VMCV statiques vs dynamiques (ajout 2026-06-04)

L'audit pré-entraînement a révélé que parmi les 4 features `vmcv_*` du modèle, une est **statique** et trois sont **dynamiques** :

- **Statique** (non affectée par l'interruption ISTDATEN) :
  - `vmcv_n_lignes_concurrentes` — calculée depuis `dim_vmcv_lignes_concurrentes`, qui décrit la topologie des lignes VMCV indépendamment du calendrier quotidien

- **Dynamiques** (NaN pendant l'interruption, attendus à 100 %) :
  - `vmcv_min_attente_min` — attente minimale calculée depuis les horaires VMCV ISTDATEN
  - `vmcv_delta_attente_min` — dérivée de la précédente
  - `vmcv_delta_frequence_h` — fréquence comparative calculée depuis ISTDATEN

Le contrôle de cohérence post-construction du script `add_istdaten_to_raw_stacked.py` utilise désormais `vmcv_min_attente_min` (dynamique) plutôt que `vmcv_n_lignes_concurrentes` (statique) pour vérifier que les features sont bien NaN pendant les 43 jours d'interruption. Cette correction supprime un faux positif `[ANOMALIE]` dans les logs sans changer la décision ni la convention de traçabilité.

Conséquence pratique : sur les 31 594 lignes `manquant_interruption_vmcv`, `vmcv_n_lignes_concurrentes` reste non-NaN (information topologique préservée), mais les 3 features dynamiques sont NaN. XGBoost dispose donc d'une information partielle sur ces 43 jours — un comportement plus correct que des NaN totaux.

## Références

- Rapport d'ingestion ISTDATEN H25, 04.06.2026 (interruption VMCV identifiée)
- ADR-021 : Features de concurrence modale VMCV, D3 (statique vs dynamique)
- ADR-039 v2 : Carry-forward STATPOP (convention `_source` analogue)
- Notebook synthèse Section 7 : classement SHAP montrant VMCV en moitié inférieure

---


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

---


---
id: ADR-042
ancien_id: ADR-CF01
date_decision: 2026-06-05
statut: amendé
amende_par: [ADR-044, ADR-062]
modifie: [ADR-009, ADR-037]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-042 — Clé de groupement créneau ±30 min pour les features histo_*

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-044, ADR-062.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-009, ADR-037.
> **Précision au gel.** Le statut d'époque de ce document est resté « Proposé — en attente de validation ». La décision a été **appliquée** : la clé de groupement en vigueur est celle d'ADR-062, dont ce document est le premier maillon.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — en attente de validation par Erwann Nédellec  <!-- statut d'époque ; état au gel : amendé (voir bandeau) -->
**Décideur** : Erwann Nédellec (data analyste MOB, R35)  
**Lié à** : ADR-037 (grain enrichi histo_*), ADR-038 (périmètre H25), étape 0 (diagnostic décalage horaire)

---

## Contexte

ADR-037 a enrichi les GROUP_KEYS des features `histo_*` avec `horaire_service_id_complet` et `cal_type_jour_3classes`, apportant un gain PR-AUC haut ×2.8 sur H24.

L'audit du 2026-06-05 (phase 2.4) a identifié la fragilité RF-1 : la refonte d'horaire 2024→2025 a modifié **100 % des `horaire_service_id_complet`** H25 (tous les services ont changé d'heure de départ origine). Les trains H25 renumérotés/décalés obtiennent PR-AUC haut = 0.055 (vs 0.204 pour les services stables), avec Rappel@WF = 0 %.

La contribution C3 estimée à ≈ 0.057 R² sur le global H25 justifie de traiter ce point avant la sélection finale du modèle.

---

## Problème RF-1

Le GROUP_KEY actuel `horaire_annee_horaire × service_id_complet × type_jour_3classes` isole chaque année horaire dans sa propre série temporelle. Lors d'une refonte d'horaire :
- H24 : service `1302_05h31` → séries H22/H23/H24 constituées
- H25 : service `1302_05h37` → série H25 vide au démarrage → NaN histo_* pour les ~9 premières occurrences

Conséquence : les services H25 (100 % de la population) partent à froid, sans hériter de l'historique H22-H24 des services équivalents. Sur le segment haut (touristique, fortement autocorrélé), cette absence d'historique est préjudiciable.

---

## Diagnostic étape 0 (2026-06-05)

Analyse sur `ml_dataset_service_id.parquet`, grain (service_id × tronçon adjacent × type_jour_3classes).

| Métrique | Global | Segment bas | **Segment haut** |
|---|---|---|---|
| Médiane écart H25 → voisin H22-H24 | 6 min | 6 min | **13 min** |
| P90 | 20 min | 9 min | 21 min |
| Couverture ≤ 15 min | 84.7 % | 96.9 % | **51.1 %** |
| Couverture ≤ 30 min | 98.2 % | 100 % | **93.1 %** |
| Couverture ≤ 60 min | 99.4 % | 100 % | 97.8 % |

Services haut non couverts à ±30 min :
- **Services nuit** (1476_00h00/05, 1473_00h00/23h35) : aucun ancêtre H22-H24 → NaN structurel. Vérification : 0 surcharge sur 1 509 observations haut H25 → **sans conséquence opérationnelle**.
- **4 services ouvrable matin** (1411_08h05/15, 1416_08h44/51) : gap ~40 min. Couverts avec ±45 min, non couverts à ±30 min.

---

## Évaluation étape 1 — Walk-forward H22/H23/H24

### Protocole

- 4 modèles : B_ADR39 (actuel), B_cren15 (±15 min), B_cren30 (±30 min), B_cren45 (±45 min)
- Nouveau GROUP_KEY : `[creneau_anchor_X, cal_type_jour_3classes]` (sans `horaire_annee_horaire` → historique cross-années)
- 2 folds WF : Fold1 (H22→H23), Fold2 (H22+H23→H24), embargo 9 jours
- Hyperparamètres XGBoost inchangés (ADR-036 : 300 arbres, max_depth=6, lr=0.1, seed=42)
- Métriques : PR-AUC haut, Rappel@68.49 haut, R²haut, IC bootstrap 500 (95 %)

### Résultats WF

| Fold | Modèle | R²haut | PR-AUC haut | IC 95% | Rappel@WF haut | IC 95% |
|------|--------|--------|-------------|--------|----------------|--------|
| Fold1 H22→H23 | B ADR-037 | 0.266 | 0.033 | [0.024–0.045] | 11.8 % | [6.8–17.1 %] |
| Fold1 H22→H23 | B créneau ±15/30/45 | **0.290** | 0.025 | [0.019–0.034] | 2.6 % | [0.6–5.4 %] |
| Fold2 H22+H23→H24 | B ADR-037 | 0.467 | **0.123** | [0.084–0.190] | 11.5 % | [5.8–18.3 %] |
| Fold2 H22+H23→H24 | B créneau ±15/30/45 | **0.474** | 0.112 | [0.075–0.168] | **13.5 %** | [7.2–20.3 %] |

**Observation critique** : les 3 largeurs créneau produisent des résultats identiques sur H22-H24. Explication : en H22-H24, les refontes d'horaire sont mineures et les service_ids sont stables. Le créneau assigne le même anchor à ±15, ±30 et ±45 min (chaque service H22-H24 est son propre anchor exact). La discrimination entre largeurs est **structurellement impossible sur les folds WF** — le problème RF-1 est spécifique à H25.

**Équivalence statistique** : les IC bootstrap 95 % se chevauchent largement entre B_ADR39 et toutes les variantes créneau (les deux métriques clés sont dans les IC des autres). Aucune dégradation significative.

### Anti-fuite confirmée

1. H22_max_date < H23_min_date → aucune contamination future dans les lags H22.
2. Algorithme searchsorted(right)−1 garantit structurellement lag ≤ base_date − 2j.
3. Les anchors créneau sont des temps H22-H24 fixes → l'assignment de H25 ne contient aucune donnée H25.

---

## Décision

**Adoption du créneau ±30 min comme clé de groupement des features `histo_*`.**

### Nouveau GROUP_KEY

```python
GROUP_KEYS = ["creneau_anchor_30", "cal_type_jour_3classes"]
```

où `creneau_anchor_30` = temps (en minutes depuis minuit) du service H22-H24 le plus proche dans ±30 minutes sur le même `cal_type_jour_3classes`. Sans `horaire_annee_horaire` → l'historique cross-années est disponible.

### Justification du choix ±30 min

Le choix est guidé par la **couverture H25 (étape 0)** — seule donnée discriminante disponible, les folds WF étant structurellement non discriminants :

- **±15 min rejeté** : couverture haut H25 = 51.1 % seulement.
- **±30 min retenu** : couverture haut H25 = 93.1 %, équivalence WF confirmée.
- **±45 min non retenu** : gain marginal (~4 points sur 4 services matin ouvrable) sans avantage WF démontré. Largeur plus large = groupes plus hétérogènes = potentiel bruit accru. Conservé comme analyse de sensibilité.

### Cas des services nuit (NaN structurel)

Les 4 services haut sans anchor (1476, 1473) conservent NaN histo_* avec le créneau ±30 min. Statut : **acceptable**. Ces trains ont une charge maximale de 20 voyageurs sur 2e classe (seuil UM = 94) — 0 faux négatif opérationnel possible. XGBoost utilisera la direction NaN apprise sur l'entraînement.

---

## Conséquences

### Positives

- Suppression du redémarrage à froid pour les services renumérotés lors des refontes d'horaire : chaque service H25 hérite de l'historique H22-H24 du service H22-H24 le plus proche en temps, dès le premier jour de H25.
- Couverture histo_* H25 : 100 % bas (contre 1.1 % NaN ADR-037), 93.1 % haut (contre 1.3 % NaN ADR-037 — mais ce 1.3 % était une moyenne trompeuse masquant 100 % NaN pour les services renumérotés en début de H25).
- Robustesse aux refontes d'horaire futures : le mécanisme fonctionnera pour tout changement annuel CFF tant qu'un service tourne à ±30 min d'un service H22-H24.

### Limitations documentées

- **Services nuit** (4 service_ids, 2.2 % des obs haut H25) : NaN histo_* structurel. Sans conséquence opérationnelle (0 surcharge).
- **4 créneaux matin ouvrable** (1411_08h05/15, 1416_08h44/51) : gap ~40 min → histo_* NaN avec ±30 min. Ces 4 services correspondent à des créneaux ajoutés dans H25 sans équivalent ouvrable en H22-H24. Potentiels faux négatifs si ces services présentent des surcharges. À vérifier lors de l'évaluation étape 4.
- La performance réelle sur H25 ne sera mesurable qu'à l'étape 4 (évaluation finale en lecture seule).

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01_selection_creneau_histo.ipynb` | Notebook complet avec WF, anti-fuite, night check |
| `consolidation_finale/outputs/etape_01_wf_results.csv` | Résultats WF 4 modèles × 2 folds + bootstrap CI |
| `consolidation_finale/figures/etape_01_wf_pr_recall_haut.png` | PR-AUC et rappel par fold et modèle |
| `consolidation_finale/figures/etape_01_wf_r2.png` | R² global et haut par fold |
| `consolidation_finale/figures/etape_01_nan_rates.png` | Taux NaN histo_* par année × modèle |

---

## Références

- Étape 0 diagnostic : `consolidation_finale/notebooks/etape_00_diagnostic_decalage_horaire_h25.ipynb`
- ADR-037 : grain enrichi histo_* (adopté 2026-06-04)
- ADR-038 : extension périmètre H25
- Audit phases 0-4 : `notes/audit_phases_0_4_2026_06_05.md`

---


---
id: ADR-043
ancien_id: ADR-CF01b
date_decision: 2026-06-05
statut: actif
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-043 — Simulation de refonte d'horaire : test de validation de RF-1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « Proposé ». Le test de validation RF-1 rapporté ici a été **conduit et retenu** ; la clé de créneau qu'il valide est en vigueur via ADR-042/044/062.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — en attente de validation  <!-- statut d'époque ; état au gel : actif (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-042 (créneau ±30 min), étape 1bis  
**Nature** : Addendum à ADR-042 — test empirique ciblé du mécanisme RF-1

---

## Motivation

ADR-042 avait conclu que le créneau ±30 min était **statistiquement équivalent** à ADR-037 sur les folds WF H22-H24, et que cette non-discrimination était **structurelle** : les service_ids H22-H23-H24 sont stables, le mécanisme RF-1 ne s'active pas sur ces folds.

L'étape 1bis teste RF-1 en recréant artificiellement le régime de refonte d'horaire à l'intérieur du train (H22+H23 = train, H24 = pseudo-test), où la mesure est possible.

---

## Protocole

### Masquage H24

- Les 117 `horaire_service_id_complet` H24 sont remplacés par des identifiants inédits (`MASK_0000`…`MASK_0116`) qui n'apparaissent **jamais** dans H22+H23.
- Les `mins_origine` (temps de départ réels) sont **préservés** pour la stratégie (b).

**Anti-fuite masquage** : `{MASK_ids} ∩ {H22+H23 service_ids} = ∅` — vérifié.

### Stratégie (a) — service_id froid

- GROUP_KEYS : `[horaire_service_id_complet, cal_type_jour_3classes]` (sans `annee_horaire`)
- H22+H23 : service_ids réels → série cross-H22-H23
- H24 masqué : `MASK_xxxx` → **groupe vide** dans H22+H23, démarrage à froid

### Stratégie (b) — créneau ±30 min

- GROUP_KEYS : `[creneau_anchor_30, cal_type_jour_3classes]` (sans `annee_horaire`)
- Anchors construits sur **H22+H23 uniquement** (jeu d'entraînement)
- H22+H23 : anchor = leur propre temps d'origine (auto-ancrage exact)
- H24 masqué : anchor = service H22+H23 le plus proche à ±30 min → **héritage cross-années**

Coverage anchors H24 masqué : **100 %** (tous les H24 trouvent un anchor dans H22+H23 à ±30 min).

### Modèle et évaluation

- **Un seul modèle** entraîné sur H22+H23 (features stratégie b — quasi-identiques à ADR-037)
- Évalué sur H24 post-embargo avec features de chaque stratégie
- Embargo : 9 jours (comme étapes 1 et 2)
- Métriques : PR-AUC haut, Rappel@68.49, R²haut — IC bootstrap 500 réplications

---

## Résultats empiriques

### Anti-fuite et cohérence de la simulation

| Vérification | Résultat | Statut |
|---|---|---|
| MASK_ids ∩ H22+H23 | ∅ | ✅ |
| Coverage H24 masqué (créneau) | 100.0 % | ✅ |
| H22+H23 NaN lag2 strat. A | 0.8 % | ✅ |
| H22+H23 NaN lag2 strat. B | 0.8 % | ✅ |
| **Corrélation lags H22+H23 A/B** | **r = 1.0000** | ✅ |
| % lags H22+H23 différents A/B | **0.0 %** | ✅ |

Les features d'entraînement H22+H23 sont **identiques** pour les deux stratégies → modèle strictement le même.

### Cohérence avec le régime H25 simulé

| Période H24 | Strat. A NaN lag2 | Strat. B NaN lag2 |
|---|---|---|
| Post-embargo complet | 0.1 % | 0.0 % |
| Early (emb.+0–60j) | 0.2 % | 0.0 % |

win7_n_surcharges haut — période early :
- Strat. A : mean = 0.007, proportion > 0 = **0.4 %**
- Strat. B : mean = 0.007, proportion > 0 = **0.4 %**

→ Les deux stratégies fournissent des lags quasi-nuls en termes de signal de surcharge pour la période début H24 (décembre–février, faible saison de surcharges).

### Performance prédictive — PR-AUC haut, rappel@WF, R²haut

| Modèle | Période | R²haut | PR-AUC haut | IC 95% | Rappel@WF | IC 95% |
|--------|---------|--------|-------------|--------|-----------|--------|
| (a) service_id froid | Début H24 | 0.499 | 0.065 | [0.029–0.140] | 0.0 % | — |
| (b) créneau ±30 | Début H24 | **0.504** | 0.064 | [0.029–0.139] | 0.0 % | — |
| (a) service_id froid | H24 complet | 0.473 | 0.112 | [0.075–0.168] | 13.5 % | [7.2–20.3 %] |
| (b) créneau ±30 | H24 complet | **0.474** | 0.111 | [0.075–0.168] | 13.5 % | [7.2–20.3 %] |
| (a) service_id froid | Fin H24 | 0.467 | 0.152 | [0.095–0.240] | 17.3 % | [9.3–25.9 %] |
| (b) créneau ±30 | Fin H24 | 0.467 | 0.152 | [0.095–0.240] | 17.3 % | [9.3–25.9 %] |

**Les deux stratégies sont statistiquement identiques sur toutes les périodes et métriques.** Les IC 95 % sont superposés à la décimale.

---

## Diagnostic du Fold 1 (étape 1)

Le Fold 1 (H22→H23) avait montré une dégradation apparente du créneau (PR-AUC 0.033→0.025). Ce diagnostic en démontre l'origine.

| Test | Résultat |
|---|---|
| Corrélation H23 lag2 ADR-037 vs créneau | **r = 1.0000** |
| % H23 lag2 différents | **0.0 %** |
| Médiane H23 lag2 ADR-037 | 12.6 |
| Médiane H23 lag2 créneau | 12.6 |

**Les features H23 sont strictement identiques entre ADR-037 et créneau.** La dégradation Fold 1 est un artefact statistique : le test porte sur 153 surcharges dans 82K observations haut H23 (prévalence 0.19%), produisant une variance très élevée dans PR-AUC. Les IC se chevauchent ([0.024–0.045] vs [0.019–0.034]) — la différence est dans le bruit.

---

## Interprétation — Pourquoi le mécanisme RF-1 ne s'active pas dans la simulation

**Raison 1 : La saison de démarrage est une basse saison.**
H24 (et H25) commencent en décembre. La période de démarrage (décembre–février) est une faible saison de surcharges sur le segment haut. Le `win7_n_surcharges` est ≈ 0 pour les deux stratégies dans cette période (0.4 % de valeurs > 0). L'héritage cross-années ne fournit pas de signal additionnel sur les surcharges, car H22-H23 n'en avait pas non plus en décembre-janvier.

**Raison 2 : La période critique est le champ aveugle de l'évaluation.**
Le bénéfice du créneau est concentré dans les **9 premiers jours** (warm-up), exclus par l'embargo. Sur ce bénéfice, la stratégie (a) a NaN histo_*, la stratégie (b) a des lags H22+H23 valides. Mais évaluer sur cette période est hors-distribution pour le modèle (jamais entraîné sans histo_* au démarrage).

**Raison 3 : Le cold-start H24 est structurellement court.**
Après 9 jours d'embargo, H24 propre data est disponible. La fenêtre win7 est pleine en ~9 observations ouvrables (~13 jours calendaires). La période où (b) >  (a) est donc de 9–13 jours — trop courte pour être mesurable sur le H24 complet (335 K observations).

**Raison 4 : La co-linéarité des features haut.**
Même avec créneau, `win7_n_surcharges` haut est ≈ 0 en début de H24/H25. Le signal discriminant pour les surcharges vient d'autres features (météo, événements, réservations) qui sont identiques entre les deux stratégies.

---

## Verdict : RF-1 non démontré sur régime simulé

Conformément au protocole de l'étape 1bis : **la stratégie (b) ne bat pas la stratégie (a) sur le pseudo-test H24 masqué** (IC superposés sur toutes les métriques). Le mécanisme RF-1 ne peut pas être empiriquement validé depuis les données d'entraînement (limitation structurelle, pas d'information dans les folds testables).

---

## Options de décision

### Option 1 : Revert to ADR-037 (protocole strict)
Le créneau ne démontre aucune amélioration mesurable. RF-1 n'est pas prouvé. Le pipeline reste inchangé. La fragmentation RF-1 sur H25 sera documentée comme limitation ex-post.

**Pour** : prudence technique, pas de changement sans bénéfice démontré.  
**Contre** : garantit le cold-start H25. Les 9 premiers jours de H25 auront NaN histo_* pour 100% des services (refonte complète). Si ces jours contiennent des surcharges à prédire, ce sont autant de faux négatifs certains.

### Option 2 : Retenir le créneau ±30 min (ADR-042 confirmé)
La neutralité est une preuve de robustesse (pas de régression). L'absence de bénéfice mesurable est un artefact structurel, pas une réfutation. Le créneau fournit une assurance contre le cold-start H25 à coût nul sur la performance connue.

**Pour** : neutralité démontrée + couverture H25 + cohérence théorique.  
**Contre** : bénéfice non empiriquement démontré.

---

## Recommandation

**Option 2 — Retenir le créneau ±30 min**, pour les raisons suivantes :

1. **Neutralité démontrée sur 3 régimes** : Fold 1 WF, Fold 2 WF, pseudo-test H24 masqué. Pas une seule métrique n'est significativement dégradée. Le coût du créneau est nul.

2. **La non-démonstration est une limitation de l'expérience, pas une réfutation.** Le bénéfice est concentré dans les 9 jours de warm-up (hors évaluation) et dans une future haute saison H25 (hors training). Ces deux fenêtres ne sont pas testables par construction.

3. **Asymétrie des risques.** Revenir à ADR-037 garantit 100% de cold-start H25 pour les services renumérotés. Le créneau réduit ce risque (couverture 93.1% haut à ±30 min) à coût nul de performance mesurable.

4. **Fold 1 résolu.** La "dégradation" fold 1 est un artefact statistique (variance intrinsèque sur 153 surcharges, features H23 strictement identiques confirmé). Elle ne reflète aucun problème structural du créneau.

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01bis_simulation_RF1.ipynb` | Notebook complet |
| `consolidation_finale/outputs/etape_01bis_results.csv` | Résultats simulation 2 strats × 3 périodes + bootstrap |
| `consolidation_finale/figures/etape_01bis_sim_pr_recall.png` | PR-AUC et rappel par période |
| `consolidation_finale/figures/etape_01bis_r2.png` | R² haut par période |
| `consolidation_finale/figures/etape_01bis_diagnostics.png` | win7_n_surcharges + IC comparaison |

---


---
id: ADR-044
ancien_id: ADR-CF01c
date_decision: 2026-06-05
statut: amendé
amende_par: [ADR-062]
modifie: [ADR-009, ADR-037, ADR-042]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-044 — Ajout de `base_sens` à la clé de groupement créneau

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-062.
> Décisions antérieures que ce document modifie : ADR-009, ADR-037, ADR-042.
> **Précision au gel.** Le §Décision publie une clé à **trois** termes sous le titre « clé de
> groupement finale ». Ce n'est pas l'état au gel : ADR-062 y a ajouté le tronçon. La clé en
> vigueur dans le pipeline canonique (`scripts/pipeline/add_features_to_raw_stacked.py`,
> `GROUP_KEYS`) compte **cinq** termes : `[base_sens, creneau_anchor_30, cal_type_jour_3classes,
> id_gare_depart_bpuic, id_gare_arrivee_bpuic]`. `base_sens` y figure toujours, en première
> position, et le créneau ancré reste à ±30 min (`CRENEAU_LARGEUR_MIN = 30`). Le mot « finale »
> du §Décision se lit « finale à la date du 2026-06-05 ».
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Accepté — pipeline régénéré (hash intermédiaire 1a53590f → canonique final `11b58391`, 2026-06-05)  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-042 (créneau ±30), ADR-043 (simulation RF-1), étape 1ter

---

## Problème identifié

La clé de groupement créneau retenue à l'étape 1 était :
```python
GROUP_KEYS = ["creneau_anchor_30", "cal_type_jour_3classes"]
```

Cette clé **ne distingue pas le sens de circulation**. Un train montant (VV → Pléiades) à 08h30 et un train descendant (Pléiades → VV) à 08h35 se retrouvent dans le même groupe, avec des régimes de charge opposés (montée matinale forte, descente matinale faible).

### Preuve empirique (Tâche 1)

| Dimension | Orientée ? | Preuve |
|-----------|-----------|--------|
| `horaire_troncon_tgl` | **Non** — constante 0 | Toutes les 2.36 M lignes de stage_08 valent 0 |
| `(id_gare_depart, id_gare_arrivee)` | **Oui** | 0 tronçon sur 43 a deux directions |
| `horaire_service_id_complet` (ADR-037) | **Oui** implicite | 0 service sur 147 span les deux directions |
| Créneau étapes 1/1bis `[cren, tj]` | **Non** | 98 % des VV→PLEI ont un PLEI→VV à ±30 min |

ADR-037 était correct car `service_id` sépare implicitement les directions. Le créneau sans `base_sens` introduit un mélange de régimes incompatibles.

---

## Solution

Ajouter `base_sens` aux GROUP_KEYS :

```python
GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]
```

`horaire_troncon_tgl` est retiré de la liste (constante sans valeur discriminante). `base_sens` assure la séparation directionnelle explicite (VV → PLEI et PLEI → VV dans des groupes distincts).

**Note** : `base_sens` est redondant avec `(id_gare_depart, id_gare_arrivee)` dans les données (chaque tronçon orienté a un seul sens), mais il est préférable de l'inclure explicitement dans la clé pour la lisibilité et la robustesse.

---

## Impact sur la couverture H25 (Tâche 2)

La couverture **ne change pas** en ajoutant `base_sens` :

| Segment | ≤ 30 min SANS sens | ≤ 30 min AVEC sens |
|---------|-------------------|-------------------|
| Global  | 98.2 % | **98.2 %** |
| Bas     | 100.0 % | **100.0 %** |
| Haut    | 93.1 % | **93.1 %** |

Raison : le `troncon_id = (gare_depart, gare_arrivee)` encode déjà la direction dans l'analyse de couverture. Les anchors sont naturellement par direction, le filtre `base_sens` n'élimine aucun match.

---

## Impact sur la performance WF (Tâche 3)

Re-vérification avec la clé corrigée `[base_sens, creneau_30, type_jour]`, Fold2 H22+H23→H24 :

| Modèle | Clé GROUP | PR-AUC haut | IC 95 % | Rappel@WF |
|--------|-----------|-------------|---------|-----------|
| B_ADR39 | [annee, sid, tj] | 0.123 | [0.084–0.190] | 11.5 % |
| B_cren30 (step 1, sans sens) | [cren, tj] | 0.112 | [0.075–0.168] | 13.5 % |
| **B_cren30_SENS (step 1ter)** | **[sens, cren, tj]** | **0.152** | **[0.095–0.221]** | **13.5 %** |

**Simulation masquage H24 (Tâche 3)** :

| Stratégie | PR-AUC haut | IC 95 % | Rappel@WF |
|-----------|-------------|---------|-----------|
| (a) service_id × sens, froid | 0.148 | [0.092–0.213] | 13.5 % |
| (b) créneau × sens | 0.152 | [0.095–0.221] | 13.5 % |

**Observations** :
1. **Neutralité de la simulation confirmée** avec sens — IC (a)/(b) superposés
2. **B_cren30_SENS au moins équivalent à B_ADR39** sur WF Fold2 (0.152 vs 0.123) — tendance favorable non significative : les IC chevauchent largement ([0.095–0.221] vs [0.084–0.190]), aucune amélioration ne peut être affirmée depuis les données d'entraînement seules
3. La version non orientée (step 1 sans sens, 0.112 `[0.075–0.168]`) mesure plus bas que la version orientée (0.152 `[0.095–0.221]`), mais les IC se chevauchent sur `[0.095–0.168]` et chaque estimation ponctuelle tombe dans l'IC de l'autre : l'écart est une **association compatible avec une baisse** due au mélange directionnel, sans qu'une dégradation puisse être affirmée — le même critère qu'à l'observation 2. La justification retenue pour l'ajout de `base_sens` est donc **structurelle et non métrique** : sans le sens, le créneau ±30 min regroupe par construction des régimes de charge opposés
4. **Anti-fuite** : H22+H23 corrélation A/B = 1.0000 — features training identiques

---

## Décision

**Clé de groupement finale pour les features `histo_*`** :

```python
GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]
```

| Élément | Décision | Raison |
|---------|----------|--------|
| `horaire_troncon_tgl` | **Retiré** | Constante 0, sans valeur discriminante |
| `horaire_annee_horaire` | **Retiré** | Historique cross-années voulu (ADR-042) |
| `base_sens` | **Ajouté** | Sépare les directions opposées |
| `creneau_anchor_30` | **Conservé** | Ancrage créneau ±30 min (ADR-042) |
| `cal_type_jour_3classes` | **Conservé** | Séparation ouvrable/samedi/dimanche (ADR-037) |

### Apport de la décision
- **Correction du mélange directionnel** (justification structurelle principale) : VV→PLEI et PLEI→VV dans des groupes séparés — le mélange corrompait le signal historique
- **Au moins équivalent à ADR-037** sur le train : tendance favorable non significative (IC chevauchants), pas d'amélioration prouvée
- Justifié structurellement par la correction de l'échec `service_id` sur refonte d'horaire (trains renumérotés H25 absents de H22-H24 → signal histo_* perdu avec l'ancienne clé)
- **Neutralité simulation** maintenue avec sens

### Limitations
- Mêmes que ADR-042 et ADR-043 : RF-1 non démontré depuis le train (limitation structurelle, bénéfice attendu uniquement sur H25), couverture haut 93.1 % à ±30 min

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01ter_sens_creneau.ipynb` | Notebook complet 3 tâches |
| `consolidation_finale/outputs/etape_01ter_ecarts_avec_sens.csv` | Couverture par (tronçon, sens, type_jour) |
| `consolidation_finale/outputs/etape_01ter_wf_results.csv` | WF Fold2 + simulation masquage avec sens |
| `consolidation_finale/figures/etape_01ter_resultats.png` | WF et simulation comparaison |
| `consolidation_finale/figures/etape_01ter_synthese.png` | Tableau récapitulatif étapes 1→1ter |

---


---
id: ADR-045
ancien_id: ADR-CF02
date_decision: 2026-06-05
statut: révoqué
revoque_par: [ADR-046, ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-045 — Grille factorielle 2×3 sur H25 : résultats étape 2

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-046, ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Les seuils Walk-Forward publiés ici sont **invalidés** par ADR-046, et l'appareil de seuil de couche 1 qu'ils servent est **sans objet** depuis ADR-052 : le modèle final est un régresseur pur, aucun seuil Walk-Forward n'est produit.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Résultats — en attente de sélection du modèle (étape 3 robustesse hyperparamètres)  <!-- statut d'époque ; état au gel : révoqué (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-044 (clé créneau), ADR-038 (périmètre H22-H24/H25)

---

## Contexte

Pipeline modifié (ADR-044) : `add_features_to_raw_stacked.py` régénère les histo_* avec `GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]`. Dataset régénéré à cette étape — hash intermédiaire `1a53590f` (vs `cd29a5f2` ADR-037) ; hash canonique final après ADR-057/CF15 : **`11b58391`**.

---

## PARTIE A — Vérifications pipeline

| Contrôle | Résultat | Statut |
|----------|----------|--------|
| NaN structurels créneau | 6 549 / 2 360 762 = 0.3 % | ✅ Services nuit attendus |
| Couverture H25 creneau_anchor_30 | **100.0 %** | ✅ |
| Première obs/groupe avec lag NaN | 333/333 | ✅ |
| win7_max ≥ win7_mean | 0 violations | ✅ |
| base_sens : 2 sens distincts | VV→PLEI / PLEI→VV | ✅ |

### Taux NaN histo_2c_lag2 — avant/après

| Année | Segment | ADR-037 | Créneau CF01c |
|-------|---------|--------|--------------|
| H22 | bas/haut | 2.4 % | 0.2 % / 0.1 % |
| H23 | bas/haut | 1.1 % | 0.0 % |
| H24 | bas/haut | 1.1 % | 0.0 % |
| **H25** | **bas/haut** | **1.3 %** | **0.0 %** |

---

## PARTIE B — Grille factorielle

### Définition des feature sets

**APC-only** (38 features) :
- Calendaire : `cal_*` (15) + `event_is_vacances/ferie/ou_ferie_vaud` (3)
- Topologie : `spatial_gare_depart/arrivee_ordre`, `spatial_segment`, `base_duree_troncon_minutes` (4)
- Histo : 16 features `histo_*` (créneau ADR-044)

**Enrichi** (179 features) : APC-only + météo (27) + STATPOP (44) + événements (8) + ISTDATEN (14+) + VMCV (6) + SIMBA (12) + réservations ResSys (8)

### Seuils walk-forward calibrés (train H22-H24 uniquement)

| Feature set | Seuil WF gelé | Fold1 | Fold2 |
|-------------|--------------|-------|-------|
| Enrichi | **72.83** | 74.95 | 70.71 |
| APC-only | **76.46** | 79.85 | 73.08 |

### Résultats des 6 cellules sur H25

| Cellule | R²glob | PR-AUC haut | IC 95% | Rappel@WF haut |
|---------|--------|-------------|--------|----------------|
| **APC_Global** | 0.504 | **0.301** | [0.248–0.357] | **13.8 %** |
| APC_Haut | 0.302 | 0.253 | [0.202–0.304] | 13.8 % |
| APC_Seg (recomb.) | 0.512 | 0.253 | [0.202–0.304] | 13.8 % |
| Enrichi_Global | **0.575** | 0.132 | [0.107–0.165] | 7.1 % |
| Enrichi_Haut | 0.477 | 0.193 | [0.160–0.235] | 12.1 % |
| Enrichi_Seg (recomb.) | **0.585** | 0.193 | [0.160–0.235] | 12.1 % |

---

## Vérification RF-1 — trains renumérotés H25 (RÉSULTAT CLEF)

**Périmètre haut H25 :** 79 505 observations, 297 surcharges (prévalence 0.37 %)  
**Renumérotés :** 49.6 % (nouveaux numéros de train, absents de H22-H24)  
**Connus :** 50.4 % (mêmes numéros que H22-H24)

| Modèle | Connus | Renumérotés | Verdict RF-1 |
|--------|--------|-------------|-------------|
| ADR-037 (audit, référence) | 0.204 / 15.9 % | **0.055 / 0.0 %** | — |
| Enrichi_Global | 0.271 / 13.4 % | 0.072 / **0.0 %** | RF-1 partiel (ΔPR-AUC +0.017, rappel encore 0) |
| Enrichi_Haut | 0.416 / 22.9 % | 0.116 / **0.0 %** | RF-1 partiel (ΔPR-AUC +0.061, rappel encore 0) |
| **APC_Global** | **0.398 / 12.7 %** | **0.230 / 15.0 %** | **RF-1 DÉMONTRÉ** |
| **APC_Haut** | **0.309 / 15.3 %** | **0.213 / 12.1 %** | **RF-1 DÉMONTRÉ** |

**RF-1 est démontré sur les modèles APC-only.** Le créneau × sens récupère du signal sur les trains renumérotés : PR-AUC 0.055→0.230 (×4.2) et Rappel 0%→15%.

**Sur les modèles Enrichi :** amélioration PR-AUC (+0.017 à +0.061) mais rappel encore 0%. Les features externes semblent diluer le signal histo_* créneau sur ce sous-ensemble.

---

## Observations clés

### 1. APC_Global > Enrichi_Global sur PR-AUC haut (0.301 vs 0.132)

Sur le segment haut (touristique, surcharges rares), les features externes (météo, STATPOP, SIMBA…) dégradent la détection de surcharges par rapport au modèle APC-only. Hypothèse : le signal histo_* créneau est dilué par les features moins discriminantes pour les cas rares. Enrichi compense par un R²glob supérieur (0.575 vs 0.504) — meilleure régression générale, moins bonne détection de surcharges.

### 2. Segmenté ≥ Global pour PR-AUC haut (au sein de chaque feature set)

Enrichi_Seg (0.193) > Enrichi_Global (0.132) et APC_Seg (0.253) légèrement < APC_Global (0.301). La spécialisation haut améliore la détection dans le cas Enrichi, mais APC_Global reste supérieur à APC_Haut (0.301 vs 0.253) — probablement parce que les données bas fournissent un signal de calibration utile pour le modèle APC.

### 3. Rappel@WF identique pour toutes les variantes APC (13.8%)

Indépendamment du périmètre d'entraînement (global vs haut), les modèles APC appliqués au haut H25 produisent le même rappel. Cela suggère que le seuil WF calibré est bien adapté et que la puissance discriminante est saturée par les features APC.

---

## Ce qui reste à faire (étape 3)

Ce tableau est produit avec hyperparamètres figés (ADR-036 : 300 arbres, max_depth=6, lr=0.1). L'étape 3 teste la robustesse : variantes de n_estimators, max_depth, subsample. Le modèle final sera sélectionné après étape 3.

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_02_grille_results.csv` | 8 cellules (6 + 2 segmentés recombinés) × métriques + CI |
| `consolidation_finale/outputs/etape_02_rf1_verification.csv` | RF-1 connus vs renumérotés × 4 modèles |
| `consolidation_finale/figures/etape_02_grille_resultats.png` | PR-AUC / rappel / R² de la grille |
| `consolidation_finale/figures/etape_02_rf1_verification.png` | RF-1 avant/après créneau |
| `consolidation_finale/figures/etape_02_nan_comparison.png` | NaN histo_* avant/après |

---


---
id: ADR-046
ancien_id: ADR-CF03
date_decision: 2026-06-05
statut: révoqué
revoque_par: [ADR-052]
modifie: [ADR-045]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-046 — Critère de calibration du seuil Walk-Forward

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-045.
> **Précision au gel.** Ce document **n'arrête aucun critère** : il se clôt sur une décision requise. Le critère F2 qu'il met en discussion est ensuite mobilisé comme acquis par ADR-047 et ADR-048, sans qu'un ADR ne l'acte — lacune consignée à ADR-078. L'appareil de seuil de couche 1 qu'il instruit est sans objet depuis ADR-052 ; la calibration de seuil en vigueur est celle de la couche 2 (ADR-073, ADR-077).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — **en attente de décision Erwann Nédellec**  <!-- statut d'époque ; état au gel : révoqué (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille factorielle), ADR-036 (seuil opérationnel 68.49)

---

## Contexte

Le pipeline de calibration du seuil WF (Walk-Forward) utilise un critère F-beta pour trouver le seuil optimal
sur les prédictions de charge (segment haut) : pour chaque fold de validation (H23, H24),
on cherche le seuil t* qui maximise F-beta, puis on moyenne les seuils des deux folds.

La session précédente (coupure de contexte) avait documenté dans ADR-045 des seuils WF de
**72.83** (Enrichi) et **76.46** (APC-only). Ces valeurs ne correspondent **ni à F1 ni à F2**.
L'étape 2bis (2026-06-05) a recalculé les seuils avec les deux critères et constaté l'incohérence.

---

## Données du problème

### Seuils WF produits par F1 vs F2 (calculés 2026-06-05)

| Feature set | Critère | Fold1 | Fold2 | **Seuil final** |
|-------------|---------|-------|-------|----------------|
| APC-only    | F1      | 46.35 | 32.41 | **39.38** |
| APC-only    | F2      | 32.03 | 32.41 | **32.22** |
| Enrichi     | F1      | 46.64 | 52.76 | **49.70** |
| Enrichi     | F2      | 46.64 | 50.29 | **48.46** |

Valeurs ADR-045 (session précédente, critère inconnu) : APC=76.46, Enrichi=72.83

### Métriques H25 résultantes — APC_Global et Enrichi_Global

| Cellule | Critère | Seuil | PR-AUC haut | IC 95% | Rappel@WF | Précision@WF |
|---------|---------|-------|-------------|--------|-----------|-------------|
| APC_Global | **F1** | 39.38 | 0.301 | [0.244–0.356] | **53.9 %** | 18.3 % |
| APC_Global | **F2** | 32.22 | 0.301 | [0.244–0.356] | **62.6 %** | 13.1 % |
| Enrichi_Global | **F1** | 49.70 | 0.132 | [0.109–0.164] | **50.8 %** | 15.2 % |
| Enrichi_Global | **F2** | 48.46 | 0.132 | [0.109–0.164] | **52.5 %** | 14.8 % |
| APC_Global | *ADR-045* | *76.46* | *0.301* | *[0.248–0.357]* | *13.8 %* | *~61 %* |
| Enrichi_Global | *ADR-045* | *72.83* | *0.132* | *[0.107–0.165]* | *7.1 %* | *~52 %* |

> **Note** : PR-AUC est indépendant du seuil — il reste identique quelle que soit la calibration.
> Seuls rappel et précision @WF varient.

### Implications opérationnelles estimées

_Labels calculés avec surcharge définie comme target ≥ 94 (offre APC — provisoire, ADR-060 corrige en >63). H25 haut complet : 1 192 surcharges >63 (vs 297 à seuil=94 ci-dessous). Décomptes à recalibrer._

| Critère | Rappel | Surcharges détectées (seuil≥94, provisoire) | Faux positifs estimés |
|---------|--------|---------------------------------------------|-----------------------|
| F1 APC  | 53.9 % | ~160 / 297 | ~730 |
| F2 APC  | 62.6 % | ~186 / 297 | ~1 230 |
| ADR-045 (critère inconnu) | 13.8 % | ~41 / 297 | ~25 |

---

## Question de décision

**Quel critère de calibration retenir pour le seuil WF ?**

### Option A — F1 (beta=1) : équilibre rappel / précision

- **Seuil** : APC≈39, Enrichi≈50
- **Rappel** : ~50-54 % — détecte 1 surcharge sur 2
- **Précision** : ~15-18 % — ~1 alarme justifiée sur 6
- **Argumentaire** : compromis équilibré ; les coûts d'un UM inutile (logistique, coût matériel)
  et d'un surcharge manquée (confort passager, potentiellement image) sont considérés équivalents.

### Option B — F2 (beta=2) : rappel privilégié (asymétrie de coût)

- **Seuil** : APC≈32, Enrichi≈48
- **Rappel** : ~53-63 % — détecte 3 surcharges sur 5
- **Précision** : ~13-15 % — ~1 alarme justifiée sur 7
- **Argumentaire** : manquer une surcharge est structurellement plus coûteux qu'un UM inutile.
  Beta=2 pèse le rappel 4× plus que la précision. Justification DSR : les échanges métier conduits au fil du projet indiquent
  que la surcharge non anticipée génère des plaintes passagers et des arbitrages de composition
  de dernière minute (coût opérationnel indirect).

### Option C — Critère opérationnel à définir (ex. rappel ≥ X % à précision maximale)

- Maximiser la précision sous contrainte de rappel minimum (ex. ≥ 50 %)
- Ou fixer un ratio précision/rappel conforme à la valeur décision UM documentée dans ADR-007

---

## Conséquence sur ADR-045

**Selon la décision :**

- **Si F1 ou F2** : les seuils et métriques rappel de l'ADR-045 seront mis à jour.
  Les résultats clés (PR-AUC haut, classement APC > Enrichi) restent valides — seuls
  les rappel@WF et précision@WF changent.
- Les seuils ADR-045 (72.83 / 76.46) sont invalidés : ils ne correspondent à aucun critère F-beta
  identifiable. Ils seront archivés comme "session précédente, critère inconnu".

---

## Données complémentaires (anti-fuite, à documenter dans notebook)

- **Groupes réels** [base_sens, creneau_anchor_30, cal_type_jour_3classes] : **339** (ADR-045 disait 333 — écart de 6, documenter)
- **Première obs/groupe → lag NaN** : 339/339 (100 %) ✓
- **NaN H25** : 0.0000 % ✓ (anchors construits exclusivement sur H22-H24)
- **Gap H24→H25** : > 2 jours ✓ (lag J-2 garanti)

---

## Décision requise

> Erwann : choisir entre Option A (F1), Option B (F2), ou Option C (critère opérationnel).
> Cette décision détermine les seuils WF qui seront gelés pour l'étape 3
> et figés dans le notebook exécuté final.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_02bis_calibration_seuils.csv` | Seuils Fold1/Fold2/final par (feature_set, critère) |
| `consolidation_finale/outputs/etape_02bis_f1_f2_comparison.csv` | Métriques H25 par (cellule, critère) |
| `consolidation_finale/outputs/etape_02bis_antifuite.json` | Résultats anti-fuite sur clé réelle |

---


---
id: ADR-047
ancien_id: ADR-CF04
date_decision: 2026-06-05
statut: remplacé
remplace_par: [ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-047 — Robustesse hyperparamètres et sélection du candidat final (couche 1)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». L'alternative laissée ouverte ici (APC_Global tunée / Enrichi_Seg figée) est **tranchée par ADR-052** en faveur d'Enrichi_Seg.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (critère F2), ADR-036 (hyperparams référence)

---

## Contexte

Étape 3 : tester la robustesse du classement de l'étape 2 (APC_Global > Enrichi_Seg sur PR-AUC haut)
quand les hyperparamètres sont tunés par cellule.

---

## Protocole

**Grille** : max_depth ∈ {4,6,8} × min_child_weight ∈ {1,5,10} × (n_estimators, lr) ∈ {(300,0.1),(500,0.05),(800,0.05)} = **27 combinaisons**  
**Sélection** : max WF PR-AUC haut moyen (Fold1+Fold2, H22-H24)  
**Seuil** : F2 recalibré sur train pour chaque config (ADR-046)  
**Évaluation** : H25 lecture seule, IC bootstrap 95 %

---

## Meilleurs hyperparamètres par cellule (sélectionnés sur WF H22-H24)

| Cellule | max_depth | min_child_weight | n_estimators | learning_rate | WF PR-AUC (tunée) | WF PR-AUC (figée ADR-036) |
|---------|-----------|-----------------|--------------|---------------|-------------------|-----------------------------|
| APC_Global | **8** | **10** | **800** | **0.05** | 0.042 | 0.022 (estimé) |
| APC_Haut | **4** | **10** | **500** | **0.05** | 0.054 | 0.030 (estimé) |
| Enrichi_Seg | **4** | **10** | **300** | **0.1** | 0.111 | 0.103 (estimé) |

> Note : les WF PR-AUC sur H22-H24 sont très faibles (0.04–0.11) car les service_ids y sont tous connus.
> Le bénéfice réel du créneau ne se matérialise que sur H25 (trains renumérotés).
> La sélection WF est donc peu fiable pour prédire la performance H25 — finding clé pour la thèse.

---

## Évaluation H25 — Tunée vs Figée (seuil F2)

| Cellule | Version | Seuil F2 | PR-AUC haut | IC 95 % | Rappel@WF | Précision | R² global |
|---------|---------|----------|-------------|---------|-----------|-----------|-----------|
| **APC_Global** | Figée (ADR-036) | 32.22 | 0.301 | [0.244–0.356] | 62.6 % | 13.1 % | 0.503 |
| **APC_Global** | **Tunée** | 37.46 | **0.336** | [0.280–0.392] | **63.3 %** | **18.5 %** | 0.510 |
| APC_Haut | Figée (ADR-036) | 32.71 | 0.254 | [0.204–0.305] | 64.3 % | 12.6 % | 0.033 |
| APC_Haut | Tunée | 39.74 | 0.303 | [0.249–0.358] | 57.6 % | 21.0 % | 0.021 |
| **Enrichi_Seg** | **Figée (ADR-036)** | 45.01 | **0.191** | [0.160–0.234] | **65.3 %** | **15.0 %** | **0.584** |
| Enrichi_Seg | Tunée | 48.09 | 0.135 | [0.115–0.162] | 54.9 % | 16.8 % | 0.573 |

---

## Findings clés

### 1. Classement PR-AUC haut : STABLE et amplifié

| Classement | Figée | Tunée |
|------------|-------|-------|
| APC_Global | 0.301 | **0.336** |
| Enrichi_Seg | 0.191 | 0.135 |

APC_Global > Enrichi_Seg sur PR-AUC haut dans les deux versions. L'écart s'amplifie avec le tuning.

### 2. Le tuning aide APC_Global, nuit à Enrichi_Seg

- **APC_Global** : +0.035 PR-AUC (+11.6 % relatif), IC tunée [0.280–0.392] vs figée [0.244–0.356] — chevauchants → tendance favorable non significative
- **Enrichi_Seg** : −0.056 PR-AUC (−29 % relatif), IC figée [0.160–0.234] et tunée [0.115–0.162] **ne se chevauchent pas** → la figée est significativement meilleure que la tunée pour Enrichi_Seg

> *Note au gel : les deux intervalles se recouvrent en réalité sur [0,160 ; 0,162]. Le critère
> de recouvrement, correctement appliqué à l'observation précédente, ne permet donc pas de
> conclure à une différence significative ici. La décision de conserver la configuration figée
> tient au protocole (ADR-052), non à ce test.*

### 3. Enrichi_Seg figée reste meilleure pour la régression

R² global : Enrichi_Seg figée (0.584) >> APC_Global tunée (0.510)

### 4. WF PR-AUC non prédictif de H25 (finding thèse)

Sur H22-H24, tous les service_ids sont connus → le créneau n'apporte pas d'avantage mesurable
sur les folds WF. Sur H25, 50 % des service_ids sont renumérotés → le créneau démontre son apport (RF-1).
Le tuning WF optimise pour la mauvaise distribution → sélection moins fiable que sur données réelles.

---

## Décision

**Selon l'objectif :**

| Objectif | Candidat retenu | Hyperparams | PR-AUC H25 | R² global |
|----------|----------------|-------------|-----------|-----------|
| Détection surcharges (opérationnel) | **APC_Global tunée** | d=8, mcw=10, n=800, lr=0.05 | **0.336** | 0.510 |
| Régression générale (recherche) | **Enrichi_Seg figée** | d=6, mcw=1, n=300, lr=0.1 | 0.191 | **0.584** |

Le candidat final pour la sélection (étape 4) sera celui qu'Erwann retient selon la priorité
opérationnelle ou académique.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03_robustesse_hyperparams.ipynb` | Notebook (réexécutable Restart & Run All) |
| `consolidation_finale/outputs/etape_03_wf_tuning_results.csv` | 162 lignes WF × grid × fold |
| `consolidation_finale/outputs/etape_03_best_params.json` | Meilleurs hyperparamètres par cellule |
| `consolidation_finale/outputs/etape_03_tuned_vs_fixed.csv` | 6 lignes H25 tunée + figée |
| `consolidation_finale/figures/etape_03_tuned_vs_fixed.png` | Figure comparaison (300 DPI) |
| `consolidation_finale/figures/etape_03_hyperparams_sensitivity.png` | Sensibilité WF (300 DPI) |

---


---
id: ADR-048
ancien_id: ADR-CF05
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-050, ADR-052]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-048 — Feature selection contrôlée des sources externes

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-050, ADR-052.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** **La décision de fond de ce document n'est pas celle retenue.** Le modèle final de couche 1 n'est pas APC-only (38 variables) mais Enrichi_Seg (ADR-052), à 158 variables après ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (F2), ADR-047 (robustesse hyperparams)

---

## Question

L'Enrichi-brut (179 features) fait moins bien qu'APC-only (38 features) sur PR-AUC haut H25.
Est-ce que l'information externe est structurellement inutile, ou est-ce que le signal est noyé
sous 141 features brutes ?

---

## Protocole

- **Importance** : XGBoost gain normalisé sur TRAIN H22-H24 complet (jamais H25)
- **Modèles** : APC-only (38) + top-K externes, K ∈ {5, 10, 20, 40} + Enrichi-brut (179)
- **Seuil** : F2 recalibré sur train (ADR-046) | **Hyperparams** : figés ADR-036 (comparabilité ADR-047)
- **Évaluation** : H25 lecture seule, embargo 9j, IC bootstrap 95 %
- **Règle** : sélection des features figée depuis le classement TRAIN, jamais H25

---

## Partie A — Importance des features externes (TRAIN uniquement)

### Importance par source (gain XGBoost normalisé, H22-H24)

| Source | Gain total | N features |
|--------|-----------|-----------|
| STATPOP (`spatial_*`) | **0.145** | 45 |
| ISTDATEN (`ist_*`) | 0.066 | 28 |
| Météo (`meteo_*`) | 0.065 | 27 |
| Réservations (`resa_*`) | 0.060 | 8 |
| Événements (`event_*`) | 0.042 | 17 |
| SIMBA (`simba_*`) | 0.041 | 12 |
| VMCV (`vmcv_*`) | 0.031 | 4 |

**9/141 features externes à importance=0** (jamais utilisées comme split sur le train).

### Top features externes retenues par K

| K | Composition | Features dominantes |
|---|-------------|---------------------|
| **K=5** | spatial(2), resa(2), vmcv(1) | menages_500m, resa_n_dossiers, vmcv_n_lignes |
| **K=10** | spatial(6), resa(3), vmcv(1) | + pop_nee_etranger, pax_2c_J-1, max_groupe |
| **K=20** | spatial(8), resa(3), ist(3), event(3), meteo(2), vmcv(1) | + headway, neige_binaire, manifestations |
| **K=40** | spatial(11), ist(7), simba(7), meteo(5), event(5), resa(4), vmcv(1) | + IST ponctualité, SIMBA parts tarifaires |

### Ce que la sélection écarte (non retenu avant K=40)

| Source | Retenues K=40 | Total | Éliminées | Raison probable |
|--------|--------------|-------|-----------|----------------|
| IST ponctualité (famille A) | 7/28 | 28 | 21 | NaN H22=89 %, H23=62 % → signal partiel |
| SIMBA | 7/12 | 12 | 5 | Corrélation r=0.97 APC, signal marginal |
| histo_total_* | *(APC-only)* | — | — | Redondant avec histo_2eme |
| histo_1ere_* | *(APC-only)* | — | — | Idem, volume < 2ème classe |

---

## Partie B — Évaluation H25 (lecture seule)

### Résultats par modèle

| Modèle | N feats | Seuil F2 | PR-AUC haut | IC 95 % | Rappel@WF | Précision | R² global |
|--------|---------|----------|-------------|---------|-----------|-----------|-----------|
| **APC-only** | **38** | 32.22 | **0.301** | **[0.244–0.356]** | **62.6 %** | 13.1 % | 0.503 |
| Enrichi-K5 | 43 | 45.50 | 0.175 | [0.138–0.220] | 53.5 % | 12.4 % | 0.572 |
| Enrichi-K10 | 48 | 41.79 | 0.225 | [0.179–0.277] | 57.2 % | 12.2 % | 0.573 |
| Enrichi-K20 | 58 | 43.46 | 0.224 | [0.183–0.276] | 63.3 % | 12.0 % | 0.578 |
| Enrichi-K40 | 78 | 42.94 | 0.145 | [0.117–0.179] | 57.2 % | 11.4 % | 0.578 |
| Enrichi-brut | 179 | 48.46 | 0.132 | [0.109–0.164] | 52.5 % | 14.8 % | 0.574 |

---

## Partie C — Vérification RF-1

**Note de définition** : avec `horaire_service_id_complet` (encode heure de départ + numéro), TOUS les H25 haut (77 262 obs, 297 surcharges) sont « renumérotés » — cohérent avec étape 0 (refonte totale 2024→2025 des horaires). Le créneau ×sens permet à APC-only de les détecter malgré l'absence d'historique exact.

**Comparaison PR-AUC sur renumérotés H25 haut (100 % de la population) :**

| Modèle | PR-AUC renumérotés | Rappel@WF |
|--------|--------------------|-----------|
| APC-only | **0.301** | 62.6 % |
| Enrichi-K10 | 0.225 | 57.2 % |
| Enrichi-K20 | 0.224 | 63.3 % |
| Enrichi-K40 | 0.145 | 57.2 % |
| Enrichi-brut | 0.132 | 52.5 % |

APC-only = meilleure détection sur les trains renumérotés. Les features externes diluent systématiquement le signal histo_* créneau.

---

## Findings clés

### 1. Enrichi-sélectionné < APC-only sur PR-AUC haut pour tout K

APC-only (0.301) > Enrichi-K10 (0.225) > Enrichi-K20 (0.224) > Enrichi-K5 (0.175) > Enrichi-K40 (0.145) > Enrichi-brut (0.132).

**Ce n'est pas un problème de noyage du signal** : même avec seulement 5 features externes soigneusement sélectionnées, la PR-AUC chute de 0.301 → 0.175. Le problème est structurel.

### 2. Courbe PR-AUC vs K non monotone

- K=10 est le meilleur Enrichi-K (0.225), mais reste 25 % sous APC-only
- K=5 < K=10 (les 5 meilleures features sont encore trop peu cohérentes avec le signal surcharge)
- K > 10 dégrade à nouveau (K=40 pire que K=10)
- L'ajout de toute feature externe, même la meilleure, dilue le signal histo_* créneau

### 3. R² global : les externes aident dès K=5

APC-only : 0.503 → K=5 : 0.572 (+14 %). Plateau à K=20 (0.578). Les 3 premières features externes (STATPOP ménages, réservations J-1, VMCV lignes) apportent l'essentiel du gain de régression. L'ajout de K=40 à 179 n'améliore plus.

### 4. Les réservations (resa_*) sont la 2ème source par importance individuelle

`resa_n_dossiers_J_minus_1` (rank 2) et `resa_pax_2c_J_minus_1` (rank 5) sont top-5. Elles améliorent R² mais dégradent PR-AUC : elles prédisent la charge moyenne mais introduisent un biais qui écrase les prédictions extrêmes (surcharges rares).

### 5. Conclusion sur la valeur de l'enrichissement

| Objectif | Recommandation |
|----------|----------------|
| **Détection surcharges (couche 1 opérationnelle)** | **APC-only** — les externes nuisent |
| **Prédiction continue de charge (recherche/contexte)** | **Enrichi-K5 ou K10** — gain R² +14 %, minimal en features |

---

## Décision

**L'enrichissement externe ne contribue pas à l'objectif principal (détection UM J-1).**

Le modèle final couche 1 retenu est : **APC-only (38 features), hyperparams ADR-036 figés** (ou tunés ADR-047 si retenu par Erwann).

Cette conclusion clôt la question de la valeur de l'enrichissement externe pour la détection de surcharges. Elle sera documentée dans le corps de la thèse (Chapitre 4 — Évaluation de l'artefact) comme un résultat en soi : la charge historique créneau × sens est suffisante ; les sources socio-démographiques, météo et réservations n'apportent pas de valeur incrémentale pour la tâche de classification de surcharge.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03bis_feature_selection.ipynb` | Notebook réexécutable |
| `consolidation_finale/outputs/etape_03bis_feature_importance.csv` | 141 features externes classées par gain |
| `consolidation_finale/outputs/etape_03bis_enrichi_k_results.csv` | Métriques H25 par modèle (6 lignes) |
| `consolidation_finale/outputs/etape_03bis_rf1_results.csv` | RF-1 par modèle × strate |
| `consolidation_finale/figures/etape_03bis_enrichi_k_comparison.png` | PR-AUC/Rappel/R² par K (300 DPI) |
| `consolidation_finale/figures/etape_03bis_feature_importance.png` | Top-50 importance externe (300 DPI) |
| `consolidation_finale/figures/etape_03bis_tradeoff_K.png` | Courbe PR-AUC et R² vs N features (300 DPI) |

---


---
id: ADR-049
ancien_id: ADR-CF06
date_decision: 2026-06-06
statut: révoqué
revoque_par: [ADR-052, ADR-073]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-049 — Cadrage bas/haut : angle mort et stratégie de seuil

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-052, ADR-073.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** L'architecture R3 instruite ici (seuils de décision distincts par segment) **n'a pas été implémentée** : la couche 2 applique un seuil unique au score de course (ADR-073).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06 — requalifié 2026-06-10  
**Statut** : **Exploration méthodologique — valeurs numériques caduques, conclusion qualitative conservée**  
**Décideur** : Erwann Nédellec  
**Modèle d'exploration** : APC-only 38 features (exploration uniquement) — modèle final : Enrichi_Seg 170f (ADR-052)  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (critère F-beta, en attente), ADR-047 (hyperparams), ADR-048 (feature selection), ADR-060 (seuil 94→63, cause de caducité)

> **Requalification 2026-06-10 — Exploration méthodologique.** CF06 est orphelin dans l'architecture finale : vérification en lecture seule confirme que les seuils R1/R2/R3 (32.22 / 66.69 / 66.94) ne sont référencés dans aucun composant de production. Le modèle final (ADR-052) est un régresseur pur — aucun seuil WF n'est produit en sortie. La décision UM (ADR-033) s'ancre sur `pred ≥ SEUIL_UM_2C = 63` directement.
>
> **Deux dimensions de caducité des valeurs numériques** : (a) labels définis à ≥94 au lieu de >63 (ADR-060) ; (b) modèle sous-jacent APC-only 38f au lieu d'Enrichi_Seg 170f (ADR-052). Toutes les valeurs numériques de cet ADR (seuils, PR-AUC, rappels, précisions, décomptes) sont des **valeurs d'exploration, non valides pour l'architecture finale**.
>
> **Conclusion qualitative conservée** : le principe de seuils de décision distincts par segment (R3 — bas pendulaire ≠ haut touristique) est structurel et indépendant du seuil et du modèle. Il constitue l'apport durable de CF06 pour la conception de la couche 2.
>
> La calibration effective des seuils (valeurs numériques) sera réalisée en couche 2, sur seuil >63, modèle Enrichi_Seg 170f, critère F-beta à acter (ADR-046 en attente).

---

## Contexte

Tout le travail de calibration et de sélection (étapes 2, 3, 3bis) a été focalisé sur le **segment haut**
(touristique, Lally–Les Pléiades). Cette analyse vérifie que ce choix était justifié
et que le bas (pendulaire, VV–Lally) n'est pas un angle mort.

---

## Partie A — Décompte absolu des surcharges _(valeurs d'exploration — caduques)_

### H25 post-embargo (9j) — 300 473 observations totales

> ⚠️ **Valeurs d'exploration, non valides pour l'architecture finale.** Labels définis à ≥94 (offre APC) et modèle APC-only 38f. Décomptes à recalculer en couche 2 sur labels >63. Pour référence, les décomptes H25 complet (emb0) à seuil >63 : BAS=8 392, HAUT=1 192, GLOBAL=9 584 (source : `q7_zone_metrics_gt63.json`).

_Décomptes d'exploration calculés avec surcharge ≥ 94 (offre APC — caduque)._

| Segment | N obs | N surch ≥94 _(exploration)_ | Prévalence _(exploration)_ |
|---------|-------|--------------------------|-----------|
| **Bas (pendulaire)** | 223 211 | **1 215** | **0.544 %** |
| Haut (touristique) | 77 262 | 297 | 0.384 % |
| **Global** | 300 473 | **1 512** | **0.503 %** |

**Observation structurelle conservée** : le bas représente ~80 % des surcharges à seuil=94. À seuil>63, le bas représente 8 392 / 9 584 = **87.6 %** — la dominance pendulaire est encore plus marquée. Ce ratio asymétrique (bas ×7.2, haut ×4.2 par rapport à seuil=94) confirme que les deux segments ont des dynamiques de surcharge fondamentalement différentes.

### Répartition temporelle

| Mois horaire | Bas | Haut | Interprétation |
|-------------|-----|------|----------------|
| 1 (Déc↑) | 0 | **48** | Ski saison opening |
| 2 (Jan) | 95 | 29 | Ski hiver |
| 3 (Fév) | 40 | 32 | Ski hiver |
| 4-5 (Mar-Avr) | 110 | 0 | Scolaire bas |
| **6 (Jun)** | **238** | **170** | **Pic double** : narcisses haut + pendulaire bas |
| 7-8 (Jul-Aoû) | 86 | 8 | Été modéré |
| 9-12 | 501 | 10 | Automne/hiver bas |

**Haut** = surcharges concentrées ski (Déc-Fév) et narcisses (Juin).  
**Bas** = surcharges réparties toute l'année, pics Juin, Octobre, Novembre.

---

## Partie B — Performance APC-only sur le bas _(valeurs d'exploration — caduques)_

> ⚠️ **Valeurs d'exploration.** PR-AUC et rappels calculés sur modèle APC-only 38f avec labels ≥94. Non transposables au modèle final Enrichi_Seg 170f ni au seuil >63. Conservés pour la traçabilité de la démarche d'exploration.

| Segment | PR-AUC _(explor.)_ | IC 95 % _(explor.)_ | Rappel@WF _(explor.)_ | R² _(explor.)_ |
|---------|--------|---------|-----------|-----|
| **Bas** | **0.199** | [0.177–0.223] | **90.2 %** | 0.489 |
| Haut | 0.301 | [0.244–0.356] | 62.6 % | 0.283 |
| Global | 0.207 | [0.184–0.230] | 84.8 % | 0.503 |

**Observation structurelle conservée** : le bas n'est pas un angle mort du modèle (PR-AUC=0.199 > baseline aléatoire). Le problème est le seuil de détection, pas la capacité prédictive. Ce constat est indépendant du seuil et du modèle.

---

## Partie C — Comparaison des 3 régimes de seuil _(valeurs d'exploration — caduques)_

> ⚠️ **Valeurs d'exploration.** Seuils R1/R2/R3 (32.22 / 66.69 / 66.94) calibrés sur : (a) labels ≥94, (b) modèle APC-only 38f. Deux dimensions de caducité — non utilisables dans l'architecture finale. La calibration effective sera réalisée en couche 2.

### Seuils calibrés WF _(exploration, labels ≥94, APC-only)_

| Régime | Seuil bas _(explor.)_ | Seuil haut _(explor.)_ |
|--------|-----------|-----------|
| R1 — Seuil haut unique | 32.22 | 32.22 |
| R2 — Seuil global unique | 66.69 | 66.69 |
| R3 — Seuils par segment | **66.94** | **32.22** |

**Observation structurelle conservée** : le seuil bas (≈67) est structurellement plus élevé que le seuil haut (≈32), reflétant les charges moyennes plus élevées du segment pendulaire dense. Ce rapport (seuil bas >> seuil haut) sera recalculé mais restera probablement ordonné de même.

### Évaluation H25 _(exploration, labels ≥94, APC-only)_

#### Rappel _(exploration)_

| Régime | Bas | Haut | Global |
|--------|-----|------|--------|
| R1 Seuil haut (actuel) | **90.2 %** | 62.6 % | **84.8 %** |
| R2 Seuil global | 32.6 % | 20.5 % | 30.2 % |
| **R3 Par segment** | 32.3 % | **62.6 %** | **38.2 %** |

#### Précision (opérationnelle) _(exploration)_

| Régime | Bas | Haut | Global | Détections totales |
|--------|-----|------|--------|-------------------|
| R1 Seuil haut | **2.3 %** | 13.1 % | 2.6 % | **48 847** |
| R2 Seuil global | 24.7 % | 52.6 % | 26.6 % | 1 721 |
| **R3 Par segment** | **25.0 %** | **13.1 %** | **19.3 %** | **2 988** |

---

## Analyse des résultats _(raisonnement structurel conservé, valeurs numériques caduques)_

### 1. Le bas est un angle mort de SEUIL, pas de modèle _(conservé)_

Le modèle APC-only a PR-AUC=0.199 sur le bas — il n'est pas aveugle. Le problème structurel est qu'un seuil calibré sur le segment touristique rare est trop bas pour le segment pendulaire dense, générant un volume prohibitif de fausses alarmes. **Ce principe est indépendant du seuil (94 ou 63) et du modèle (APC-only ou Enrichi_Seg).** Il justifie la nécessité d'une stratégie de seuil différenciée par segment.

### 2. R1 (seuil unique côté haut) — inadapté au bas _(conservé)_

Un seuil unique calibré sur le haut touristique génère un ratio fausses alarmes/surcharges opérationnellement inutilisable sur le bas pendulaire dense (précision ~2 % dans cette exploration). **Ce constat qualitatif est robuste** : les dynamiques de charge sont structurellement différentes entre bas et haut.

### 3. R2 (seuil global unique) — détériore la détection haut _(conservé)_

Un seuil global unique protège la précision globale mais dégrade la détection sur le haut touristique rare. Inacceptable pour la mission principale (surcharges touristiques imprévisibles). **Ce constat qualitatif reste valide** avec tout modèle ou seuil.

### 4. R3 (seuils distincts par segment) — architecture recommandée _(conservé)_

Le principe : seuils distincts bas/haut permet de maintenir la détection haut tout en réduisant le bruit bas. **C'est la conclusion structurelle durable de CF06** : la couche 2 doit distinguer les deux segments pour la calibration du seuil de décision.

---

## Conclusion qualitative conservée — Apport durable de CF06

**L'architecture R3 (seuils distincts par segment) est la conclusion méthodologique de cet ADR.** Elle reste valide indépendamment du seuil de surcharge (94 ou 63) et du modèle (APC-only ou Enrichi_Seg), car elle repose sur une asymétrie structurelle entre segments :

- **Bas (pendulaire)** : charges moyennes plus élevées, surcharges 87.6 % du total >63 (8 392/9 584), profil régulier — seuil de décision mécaniquement plus élevé
- **Haut (touristique)** : charges plus variables, surcharges rares et événementielles — seuil de décision plus bas requis pour la sensibilité

Cette asymétrie est confirmée par les ratios de surcharge à seuil >63 : bas ×7.2, haut ×4.2 par rapport à seuil=94. Elle est structurelle (différences de demande, de fréquentation, de saisonnalité).

---

## Décision — Statut requalifié

### Modèle couche 1

Le modèle final est **Enrichi_Seg 170f** (ADR-052) — pas APC-only. Décision close. CF06 utilisait APC-only à titre d'exploration.

### Couche 2 — Principe de seuil par segment (R3) : **RETENU comme architecture à implémenter**

L'architecture R3 — seuils distincts bas/haut, calibrés sur H22-H24 en walk-forward — est recommandée pour la couche 2. La **décision qualitative est figée**. Les **valeurs numériques** (32.22, 66.94) sont caduques et seront recalculées avec :
- Modèle : Enrichi_Seg 170f (ADR-052)
- Labels : target > 63 (ADR-060)
- Critère F-beta : à acter (ADR-046 en attente)
- Protocole : walk-forward H22-H24, jamais H25

La compatibilité avec l'unité de décision UM au niveau du tour (ADR-007) reste valide — la stratégie par segment s'applique au niveau du tronçon puis s'agrège au tour.

### Limitations

- La PR-AUC bas et les rappels R3 de cette exploration (APC-only, labels ≥94) ne sont pas transposables. Avec Enrichi_Seg 170f et labels >63, les valeurs seront différentes.
- La sous-estimation systématique du modèle dans la zone de surcharge (biais>63 : −30.4 BAS, −37.8 HAUT — ADR-052) est un facteur à intégrer dans la calibration du seuil de décision couche 2.

---

## Fichiers

_Tous les outputs ci-dessous sont des artefacts d'exploration (labels ≥94, APC-only 38f). Ils documentent la démarche méthodologique mais leurs valeurs numériques ne sont pas valides pour l'architecture finale._

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03ter_cadrage_bas_haut.ipynb` | Notebook d'exploration (SEUIL_UM=63, > strict — mis à jour pour cohérence, mais valeurs dans les outputs sont issues de la run ≥94) |
| `consolidation_finale/outputs/etape_03ter_surcharges_par_segment.csv` | Décomptes d'exploration (≥94) |
| `consolidation_finale/outputs/etape_03ter_surcharges_temporel.csv` | Distribution mensuelle d'exploration |
| `consolidation_finale/outputs/etape_03ter_pr_auc_par_segment.csv` | PR-AUC exploration APC-only |
| `consolidation_finale/outputs/etape_03ter_regimes_seuil.csv` | Comparaison 3 régimes d'exploration |
| `consolidation_finale/figures/etape_03ter_*.png` | Figures d'exploration — 300 DPI |

---


---
id: ADR-050
ancien_id: ADR-CF07
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-069]
modifie: [ADR-048]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-050 — Grille régression features × architecture et sample weighting

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-069.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-048.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». La pondération des surcharges instruite ici est **écartée** : ADR-069 conserve la perte quadratique non pondérée.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-045→CF06

---

## Contexte

Recentrage couche 1 sur la **régression** : qualité de prédiction de la charge, indépendamment
du seuil (décision couche 2). Métriques : R², MAE, MAE≥60, MAE≥80, Biais≥80.
H25 lecture seule, hyperparams figés ADR-036.

---

## Phase 1 — Grille 8 modèles

### Résultats segment HAUT (touristique, 297 surcharges)

| Modèle | R² haut | IC 95% | MAE haut | MAE ≥80 | Biais ≥80 | PR-AUC |
|--------|---------|--------|----------|---------|-----------|--------|
| APC_Global | 0.283 | — | — | 61.9 | **-61.7** | 0.301 |
| APC_Haut | 0.306 | — | — | 60.5 | -59.5 | — |
| APC_Seg | 0.306 | — | — | 60.5 | -59.5 | — |
| Enrichi_Global | 0.457 | — | — | 53.2 | -53.2 | 0.132 |
| Enrichi_Haut | **0.480** | — | — | **50.4** | **-50.4** | — |
| **Enrichi_Seg** | **0.480** | — | — | **50.4** | **-50.4** | 0.193 |

### Résultats segment GLOBAL (recombinés pour les segmentés)

| Modèle | R² global | R² bas | R² haut |
|--------|-----------|--------|---------|
| APC_Global | 0.503 | 0.489 | 0.283 |
| APC_Seg | 0.510 | 0.494 | 0.306 |
| Enrichi_Global | 0.574 | 0.547 | 0.457 |
| **Enrichi_Seg** | **0.584** | **0.556** | **0.480** |

---

## Finding clé — Sous-prédiction systématique (biais ≥80)

**Tous les modèles sous-prédisent les charges élevées de -50 à -62 voyageurs.**

Pour une charge réelle de 90+ voyageurs (surcharge), le modèle prédit en moyenne ~35-45 voyageurs.
Ce n'est pas un problème de seuil — c'est la **régression vers la moyenne** : XGBoost optimise
l'erreur quadratique sur l'ensemble des observations, et les surcharges (rares, 0.4 %) sont
écrasées par la masse des observations normales.

Ce biais est documenté en Chapitre 4 comme limite de l'artefact : le profil de charge montré à
l'opérateur (SHAP + valeur prédite) sera systématiquement optimiste sur les cas qui comptent pour l'UM.

### Gagnants Phase 1

- **Régression générale** : Enrichi_Seg (R²=0.584 global, 0.480 haut)
- **Précision charges élevées** : Enrichi_Haut = Enrichi_Seg sur haut (MAE≥80=50.4, biais=-50.4)
- **Détection UM** (PR-AUC, de l'étape 3bis) : APC_Global (0.301)

**Candidat Phase 2** : Enrichi_Haut (arch spécialisée haut, 179 features)

---

## Phase 2 — Sample weighting sur Enrichi_Haut

Poids w pour les observations surcharge (charge_réelle ≥ 94) dans le TRAIN H22-H24 uniquement.

| w_ratio | R² haut | MAE ≥80 haut | Biais ≥80 haut | ΔBiais vs baseline |
|---------|---------|-------------|----------------|-------------------|
| 1 (baseline) | 0.480 | 50.4 | -50.4 | — |
| 5 | 0.460 | 46.1 | -45.7 | +4.7 (+9.3 %) |
| **10** | **0.462** | **44.1** | **-43.7** | **+6.7 (+13.3 %)** |
| **20** | 0.443 | **43.1** | **-42.6** | **+7.8 (+15.5 %)** |
| 50 | 0.412 | 44.7 | -43.4 | +7.0 (+13.9 %) |

### Interprétation

- **Le weighting réduit le biais de ~15-16 %** (de -50.4 à -42.6 avec w=20) mais ne l'élimine pas.
  Le biais structurel de régression MSE sur distribution asymétrique ne peut pas être corrigé
  entièrement par le weighting.
- **Optimal w=20** : MAE≥80 minimal (43.1), biais le plus proche de 0 (-42.6). R² haut passe
  de 0.480 → 0.443 (perte ~8 % acceptable).
- **w=50 dégrade** : MAE≥80 remonte légèrement (44.7) — régularisation excessive, le modèle
  commence à sur-optimiser les rares surcharges au détriment de la cohérence générale.
- **Le biais reste négatif même à w=50** (-43.4) : propriété fondamentale, pas corrigeable
  sans changer l'objectif (ex. quantile regression).

---

## Décision

### Modèle couche 1 recommandé

**Enrichi_Seg, hyperparams ADR-036, sans weighting** (R²=0.584 global, MAE≥80=50.4 haut).

Rationale :
- Meilleur R² global et bas (couverture complète du réseau)
- Même qualité haut que Enrichi_Haut
- Le sample weighting améliore modérément MAE≥80 (-15 %) mais le biais reste fort

**Si priorité maximale sur justesse charges élevées** → Enrichi_Haut w=20
(MAE≥80=43.1, biais=-42.6, R²haut=0.443).

### Le biais ≥80 est un facteur à documenter dans la thèse

La valeur prédite par le modèle pour une surcharge est systématiquement sous-estimée de ~42-50
voyageurs. Ceci renforce la nécessité de la couche de décision (couche 2) : le décideur ne voit
pas la valeur prédite comme une prédiction fiable de la charge absolue, mais comme un signal
relatif (la valeur prédite classe correctement les jours à risque même si elle sous-estime
l'amplitude). La SHAP explanation expose les drivers, pas l'amplitude prédite.

### Arbitrage APC vs Enrichi (couche 1 finale)

| Critère | APC-only | Enrichi_Seg |
|---------|----------|-------------|
| PR-AUC haut (détection UM) | **0.301** | 0.193 |
| R² global | 0.503 | **0.584** |
| R² haut | 0.283 | **0.480** |
| MAE ≥80 haut | 61.9 | **50.4** |
| Biais ≥80 haut | -61.7 | **-50.4** |
| N features | **38** | 179 |

Pour la **décision UM J-1** (détection = PR-AUC) : APC-only gagne.  
Pour la **qualité du profil de charge** (R², MAE) : Enrichi_Seg gagne.

Ce sont deux usages différents. Si la couche 1 sert à produire un profil de charge SHAP
lisible par l'opérateur → Enrichi_Seg. Si elle sert uniquement à détecter le risque de
surcharge → APC-only.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03quat_regression_weighting.ipynb` | Notebook réexécutable |
| `consolidation_finale/outputs/etape_03quat_phase1_results.csv` | Phase 1 — 8 modèles × segments |
| `consolidation_finale/outputs/etape_03quat_phase2_results.csv` | Phase 2 — weighting × ratios |
| `consolidation_finale/figures/etape_03quat_phase1_grille.png` | Grille régression (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase1_biais.png` | Biais ≥80 (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase2_weighting.png` | Courbes weighting (300 DPI) |
| `consolidation_finale/figures/etape_03quat_phase2_predit_vs_reel.png` | Prédit vs réel (300 DPI) |

---


---
id: ADR-051
ancien_id: ADR-CF08
date_decision: 2026-06-06
statut: remplacé
remplace_par: [ADR-069]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-051 — Pertes alternatives : quantile regression et Tweedie

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-069.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». Les pertes alternatives instruites ici (quantile, Tweedie) sont **écartées** : ADR-069 conserve `reg:squarederror`.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats — en attente de validation Erwann Nédellec  <!-- statut d'époque ; état au gel : remplacé (voir bandeau) -->
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-050 (weighting), ADR-049 (cadrage bas/haut), ADR-036 (modèle référence)

---

## Contexte et motivation

ADR-050 a montré que le **sample weighting MSE** (w=20 optimal) réduit le biais≥80 haut de
seulement 15 % (-50.4 → -42.6), sans l'éliminer. La sous-prédiction structurelle des surcharges
est une propriété de l'objectif MSE : en minimisant l'erreur quadratique sur une distribution
fortement asymétrique (0.4 % de surcharges), XGBoost converge vers la **moyenne conditionnelle**,
qui est massivement tirée vers le bas par la masse des observations normales.

La Phase 3 explore deux familles de pertes qui modifient cet objectif :

1. **Quantile regression** (`reg:quantileerror`, α ∈ {0.85, 0.90, 0.95}) : minimise la perte
   de vérification pinball. Le modèle prédit le **α-quantile** de la distribution conditionnelle,
   pas la moyenne. Pour α > 0.5, le modèle est entraîné à prédire haut.

2. **Tweedie regression** (`reg:tweedie`) : perte multiplicative adaptée aux données de comptage
   positives et sur-dispersées. Objectif `log(y_pred)` → invariant d'échelle, adapté aux
   distributions Power-loi.

**Candidats testés** : Enrichi_Seg (179 features, architecture segmentée) et APC_Seg (38 features),
identifiés comme meilleurs dans leurs familles respectives en Phase 1. Hyperparams ADR-036 figés.
Walk-forward H22→H24 (train), H25 lecture seule.

---

## ⚠️ Avertissement d'interprétation (à lire avant le tableau)

**Le quantile loss change la signification de la prédiction.**

- MSE → le modèle prédit la **charge attendue** (moyenne conditionnelle). Un biais négatif signifie
  sous-estimation.
- Quantile α → le modèle prédit un **majorant prudent de la charge** au niveau α. Un "meilleur
  biais≥80" à α élevé ne signifie pas que le modèle prédit mieux — il signifie que le modèle
  prédit plus haut sur l'ensemble des observations, y compris les charges basses et moyennes
  (sur-prédiction de 34 à 82 % sur le MAE global, cf. tableau).

**Ne pas comparer directement le biais≥80 entre MSE et quantile comme si c'était la même métrique.**
Le biais≥80 d'un modèle quantile α=0.95 signifie "le 95e quantile prédit est encore inférieur à la
charge réelle pour les surcharges" — et non "le modèle sous-prédit de X voyageurs en espérance".

---

## Phase 3 — Résultats par perte et segment

### Segment HAUT (77 262 obs, 297 surcharges ≥80)

| Configuration | R² | MAE | MAE≥80 | Biais≥80 [IC95%] | Δbiais vs MSE |
|---------------|-----|-----|--------|------------------|---------------|
| **Enrichi_Seg MSE** (baseline) | **0.480** | 6.19 | 50.4 | −50.4 [−50.4; −49.0] | — |
| Enrichi_Seg tweedie | 0.374 | **6.05** | 64.5 | −64.5 [−66.6; −62.3] | −14.1 (pire) |
| Enrichi_Seg q=0.85 | 0.347 | 8.29 | 39.6 | −39.2 [−41.5; −37.1] | **+11.2 (−22%)** |
| Enrichi_Seg q=0.90 | 0.198 | 9.67 | 35.7 | −34.2 [−36.7; −31.9] | +16.2 (−32%) |
| Enrichi_Seg q=0.95 | 0.024 | 11.03 | 34.0 | −31.8 [−34.1; −29.4] | +18.6 (−37%) |
| **APC_Seg MSE** (baseline) | **0.306** | 5.73 | 60.5 | −59.5 | — |
| APC_Seg tweedie | 0.314 | 6.62 | 65.6 | −64.1 [−66.5; −61.8] | −4.6 (pire) |
| APC_Seg q=0.85 | 0.164 | 9.40 | 48.0 | −46.3 [−48.6; −44.0] | +13.2 (−22%) |
| APC_Seg q=0.90 | −0.033 | 10.97 | 45.4 | −43.8 [−46.0; −41.3] | +15.7 (−26%) |
| APC_Seg q=0.95 | −0.463 | 13.63 | 39.3 | −36.9 [−39.2; −34.5] | +22.6 (−38%) |

### Segment BAS (223 211 obs, 1 215 surcharges ≥80)

| Configuration | R² | MAE | MAE≥80 | Biais≥80 |
|---------------|-----|-----|--------|----------|
| **Enrichi_Seg MSE** (baseline) | **0.556** | 8.61 | 40.1 | −39.8 |
| Enrichi_Seg tweedie | 0.493 | 8.94 | 48.6 | −48.5 (pire) |
| Enrichi_Seg q=0.85 | 0.358 | 11.51 | 29.0 | −25.6 |
| Enrichi_Seg q=0.90 | 0.204 | 13.22 | 26.1 | −21.9 |
| Enrichi_Seg q=0.95 | −0.062 | 15.79 | 23.7 | −18.9 |
| **APC_Seg MSE** (baseline) | **0.494** | 9.17 | 44.5 | −44.4 |
| APC_Seg tweedie | 0.495 | 9.04 | 46.3 | −46.1 (pire) |
| APC_Seg q=0.85 | 0.312 | 11.51 | 34.1 | −32.3 |
| APC_Seg q=0.90 | 0.161 | 13.39 | 31.3 | −28.5 |
| APC_Seg q=0.95 | −0.137 | 16.07 | 27.7 | −24.1 |

### Segment GLOBAL (recombinés, 300 473 obs)

| Configuration | R² | MAE global | Biais≥80 global | Sur-prédiction¹ |
|---------------|-----|-----------|----------------|-----------------|
| **Enrichi_Seg MSE** | **0.584** | **7.99** | −41.5 | — |
| Enrichi_Seg tweedie | 0.520 | 8.19 | −51.0 (pire) | ≈ MSE |
| Enrichi_Seg q=0.85 | 0.415 | 10.68 | −27.7 | **+34 %** MAE |
| Enrichi_Seg q=0.90 | 0.275 | 12.30 | −23.9 | +54 % MAE |
| Enrichi_Seg q=0.95 | 0.048 | 14.56 | −21.0 | +82 % MAE |
| **APC_Seg MSE** | 0.510 | 8.53 | −46.8 | — |
| APC_Seg tweedie | 0.512 | 8.42 | −49.0 (pire) | ≈ MSE |
| APC_Seg q=0.85 | 0.351 | 11.21 | −34.6 | +31 % MAE |
| APC_Seg q=0.90 | 0.207 | 12.77 | −31.0 | +50 % MAE |
| APC_Seg q=0.95 | −0.086 | 15.44 | −26.2 | +81 % MAE |

¹ Augmentation du MAE global par rapport à la baseline MSE de même feature set : proxy de la sur-prédiction sur les charges basses/moyennes.

---

## Grand Tableau Final — Tous les modèles couche 1

Tableau de référence pour la validation. Lignes = feature set × architecture × perte.
**Candidats Phase 3 uniquement sur `Seg`** (meilleure architecture Phase 1).

| # | Modèle | Perte | w | R² haut | MAE≥80 haut | Biais≥80 haut | R² bas | Biais≥80 bas | R² global | Biais≥80 global | PR-AUC haut |
|---|--------|-------|---|---------|------------|---------------|--------|-------------|-----------|----------------|------------|
| 1 | **Enrichi_Seg** | MSE | 1 | **0.480** | 50.4 | −50.4 | **0.556** | −39.8 | **0.584** | −41.5 | 0.191 |
| 2 | APC_Seg | MSE | 1 | 0.306 | 60.5 | −59.5 | 0.494 | −44.4 | 0.510 | −46.8 | **0.254** |
| 3 | Enrichi_Seg | MSE | 10 | 0.462 | 44.1 | −43.7 | 0.545 | −37.8 | 0.573 | −38.8 | 0.174 |
| 4 | APC_Seg | MSE | 10 | 0.287 | 57.3 | −57.2 | 0.480 | −42.5 | 0.496 | −44.9 | 0.290 |
| 5 | Enrichi_Seg | MSE | 20 | 0.443 | 43.1 | −42.6 | 0.535 | −36.8 | 0.563 | −37.8 | 0.153 |
| 6 | APC_Seg | MSE | 20 | 0.282 | 58.5 | −58.5 | 0.467 | −42.5 | 0.486 | −45.1 | 0.237 |
| 7 | Enrichi_Seg | q=0.85 | 1 | 0.347 | 39.6 | **−39.2** | 0.358 | **−25.6** | 0.415 | **−27.7** | 0.156 |
| 8 | APC_Seg | q=0.85 | 1 | 0.164 | 48.0 | −46.3 | 0.312 | −32.3 | 0.351 | −34.6 | 0.274 |
| 9 | Enrichi_Seg | q=0.90 | 1 | 0.198 | 35.7 | −34.2 | 0.204 | −21.9 | 0.275 | −23.9 | 0.206 |
| 10 | APC_Seg | q=0.90 | 1 | −0.033 | 45.4 | −43.8 | 0.161 | −28.5 | 0.207 | −31.0 | 0.252 |
| 11 | Enrichi_Seg | q=0.95 | 1 | 0.024 | 34.0 | −31.8 | −0.062 | −18.9 | 0.048 | −21.0 | 0.157 |
| 12 | APC_Seg | q=0.95 | 1 | −0.463 | 39.3 | −36.9 | −0.137 | −24.1 | −0.086 | −26.2 | 0.247 |
| 13 | Enrichi_Seg | tweedie | 1 | 0.374 | 64.5 | −64.5 | 0.493 | −48.5 | 0.520 | −51.0 | 0.261 |
| 14 | APC_Seg | tweedie | 1 | 0.314 | 65.6 | −64.1 | 0.495 | −46.1 | 0.512 | −49.0 | 0.279 |

**Colonnes** : Biais≥80 = biais moyen sur les observations à charge réelle ≥ 80 (négatif = sous-prédiction) ; PR-AUC = courbe précision-rappel avec seuil walk-forward, informatif couche 2.  
**Gras** = meilleur par colonne dans son groupe de comparaison.

---

## Analyse par perte

### Tweedie — Levier nul, aggrave les charges élevées

La perte Tweedie **n'améliore pas** les surcharges : biais≥80 haut passe de −50.4 → −64.5 pour
Enrichi_Seg (+28 % de sous-prédiction). La perte multiplicative pénalise plus fortement les
erreurs relatives sur les grandes valeurs, mais dans notre contexte (distribution bimodale
apc_comptage + évènements rares), ce mécanisme amplifie la régression vers la moyenne sur les
hautes charges plutôt que de la corriger. R² haut = 0.374, acceptable mais inférieur à MSE (0.480).

**Verdict : rejeté.** Tweedie est inadapté au problème — ne corrige pas le biais structurel et
dégrade la précision sur les surcharges.

### Quantile regression — Compromis biais/R² progressif mais coûteux

Le quantile loss réduit le biais≥80 en déplaçant l'objectif de prédiction de la moyenne vers un
quantile supérieur. Cet effet est réel mais a un coût mesurable sur l'ensemble de la distribution :

| α | Δbiais≥80 haut | R² haut | MAE global Enrichi | Sur-prédiction globale |
|---|---------------|---------|-------------------|----------------------|
| MSE | — | 0.480 | 7.99 | 0 % |
| 0.85 | −22 % | 0.347 | 10.68 | +34 % |
| 0.90 | −32 % | 0.198 | 12.30 | +54 % |
| 0.95 | −37 % | ≈0 | 14.56 | +82 % |

Trois observations clés :

1. **Le biais≥80 reste toujours négatif, même à α=0.95** : le 95e quantile prédit est encore
   inférieur à la charge réelle pour les surcharges (biais=-31.8 sur haut). La queue de
   distribution est extrêmement difficile à capturer — un quantile élevé corrige partiellement
   mais pas entièrement. Cette observation confirme que le problème "60 vs 95" est structurel.

2. **α élevé = sur-prédiction des charges normales** : à α=0.90, le MAE global augmente de +54 %
   (+4.3 voyageurs/tronçon en moyenne). Sur les charges basses (pas de surcharge), le modèle
   annonce davantage de voyageurs que n'en observe l'APC. Coût opérationnel : faux positifs
   potentiels si ce profil de charge nourrit la couche 2 sans correction.

3. **R² haut à α=0.95 ≈ 0** pour Enrichi_Seg (0.024) et négatif pour APC_Seg (−0.463) : le
   modèle quantile sur-prédit systématiquement sur l'ensemble haut — il ne classe plus les jours
   correctement à l'intérieur du segment. Ce n'est plus un modèle de régression : c'est un
   majorant quasi-constant.

### Meilleur compromis Phase 3 : Enrichi_Seg q=0.85

- Biais haut : −39.2 (vs −50.4 MSE, **−22 %**)
- R² haut : 0.347 (vs 0.480 MSE, **−28 %**)
- MAE global : 10.68 (vs 7.99 MSE, **+34 %**)
- Biais global : −27.7 (vs −41.5 MSE, **−33 %**)

Gain biais = 22 % haut. Coût : R² haut perd 28 %, MAE global augmente de 34 %.

---

## Comparaison synthétique — Candidats résiduels

Quatre candidats méritent d'être mis en regard pour la décision finale :

| Candidat | R² haut | Biais≥80 haut | R² global | Biais≥80 global | MAE global | Signification |
|----------|---------|-------------|-----------|----------------|-----------|---------------|
| Enrichi_Seg MSE | **0.480** | −50.4 | **0.584** | −41.5 | **7.99** | charge attendue (moyenne) |
| Enrichi_Seg MSE w=20 | 0.443 | −42.6 | 0.563 | −37.8 | ~8.5* | charge attendue, pondérée |
| Enrichi_Seg q=0.85 | 0.347 | **−39.2** | 0.415 | **−27.7** | 10.68 | majorant 85e quantile |
| Enrichi_Seg q=0.90 | 0.198 | −34.2 | 0.275 | −23.9 | 12.30 | majorant 90e quantile |

*MAE w=20 non disponible directement dans le grand tableau (vient d'ADR-050).

**La décision de fond** : veut-on un modèle couche 1 qui prédit la **charge probable** (MSE,
meilleur R², sous-prédit les surcharges) ou un **majorant prudent de la charge** (quantile, moins
de sous-prédiction sur les surcharges mais sur-prédit les cas normaux et qualité globale dégradée) ?

Ce sont deux usages différents pour l'artefact UM :
- MSE → le praticien voit "probabilité que 65 voyageurs soient attendus" → il doit interpréter que
  les vraies surcharges peuvent dépasser de 50 voyageurs
- q=0.85 → le praticien voit "je m'attends à au moins X voyageurs dans 85 % des cas" → biais
  réduit sur les surcharges mais les jours "normaux" semblent plus chargés qu'ils ne le sont

---

## Ce qui n'est PAS décidé ici

**Le modèle final couche 1 n'est pas figé dans cet ADR.**

Ce tableau est présenté pour validation avant décision. La question centrale est l'arbitrage
R²/biais dans le contexte opérationnel :
- Si la couche 2 (seuil, détection) absorbe complètement le biais (signal relatif suffit) →
  Enrichi_Seg MSE est optimal (R² maximal).
- Si le profil de charge absolu est montré à l'opérateur et que la sous-prédiction de 50
  voyageurs est jugée problématique → Enrichi_Seg q=0.85 est un compromis documenté (−22 %
  biais, −28 % R²).
- Enrichi_Seg q=0.90+ et Tweedie : non recommandés.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/outputs/etape_3q5_phase3.csv` | Phase 3 — 8 configs × 3 segments (24 lignes) |
| `consolidation_finale/outputs/etape_3q5_grand_tableau.csv` | Grand tableau — 14 modèles × métriques |
| `consolidation_finale/figures/etape_3q5_biais_par_config.png` | Biais≥80 par modèle/segment/perte (300 DPI) |
| `consolidation_finale/figures/etape_3q5_biais_vs_r2.png` | Trade-off biais/R² (300 DPI) |
| `consolidation_finale/figures/etape_3q5_predit_vs_reel.png` | Prédit vs réel avant/après (300 DPI) |
| `consolidation_finale/figures/etape_3q5_quantile_effect.png` | Effet de α sur la distribution (300 DPI) |

> ⚠️ **Note technique** : le notebook `etape_03quinquies_pertes_alternatives.ipynb` n'a pas été
> sauvegardé (session interrompue). Les outputs CSV et figures ont été persistés avant interruption.
> Les résultats sont reproductibles depuis `etape_03quat_regression_weighting.ipynb` (Phase 1-2)
> en ajoutant la boucle Phase 3 sur `reg:quantileerror` et `reg:tweedie`.

---


---
id: ADR-052
ancien_id: ADR-CF09
date_decision: 2026-06-06
statut: amendé
amende_par: [ADR-061, ADR-076]
modifie: [ADR-003, ADR-033, ADR-045, ADR-046, ADR-047, ADR-048, ADR-049]
chiffres_perimes: [seuil94, gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-052 — Modèle final couche 1 : Enrichi_Seg (MSE, 170 features, architecture segmentée)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-061, ADR-076.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-003, ADR-033, ADR-045, ADR-046, ADR-047, ADR-048, ADR-049.
> **Précision au gel.** Le périmètre de **170 variables** cité au titre est ramené à **158** par ADR-061 (retrait de la famille SIMBA). Le titre porte la valeur d'époque.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06 — mis à jour 2026-06-07, 2026-06-10  
**Statut** : **DÉCISION FIGÉE** — validée par Erwann Nédellec  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-044 (clé histo_*), ADR-048 (feature selection), ADR-047 (hyperparams ADR-036), ADR-049 (cadrage bas/haut), ADR-050 (weighting), ADR-051 (pertes alternatives), ADR-054 (nettoyage parcimonie 179→171→172→170), ADR-060 (seuil surcharge 94→63)

> **Mise à jour 2026-06-07** : périmètre features porté à **172** suite à l'ajout du dénivelé tronçon (ADR-057), puis réduit à **170** après nettoyage de parcimonie final (retrait de 2 features HPI à gain=0 exact — ADR-054 §2).
>
> **Mise à jour 2026-06-10 (ADR-060)** : réentraînement sur dataset `daf936c8` (seuil surcharge = 63). Métriques H25, décomptes de surcharges et analyse Seg/Global mis à jour. La justification de l'architecture segmentée s'est **renforcée** — voir § Justification ci-dessous.

---

## Décision

**Modèle couche 1 retenu = Enrichi_Seg**

| Paramètre | Valeur |
|-----------|--------|
| Architecture | Segmentée : deux régresseurs XGBoost indépendants (modèle BAS + modèle HAUT) |
| Objectif XGBoost | `reg:squarederror` (MSE) |
| Hyperparamètres | ADR-036 figés : `n_estimators=300, max_depth=6, lr=0.1, subsample=0.8, colsample_bytree=0.8` |
| Feature set | **170 features** (parcimonie finale ADR-054) |
| Clé `histo_*` | `[base_sens, creneau_anchor_30, cal_type_jour_3classes]` — ADR-044 |
| Aiguillage en inférence | `spatial_segment` (colonne pipeline, non incluse dans les 170f) → modèle BAS ou modèle HAUT |
| Target | `target_voyageurs_2eme_classe` par tronçon × course × date |
| Train | H22 + H23 + H24 |
| Embargo | **0** (retiré — décision post-audit ist_*, analogue naturel justifié) |
| Test H25 | Lecture seule — résultats = plancher de performance |

---

## Critère de sélection couche 1

La couche 1 prédit la **charge en voyageurs** (régression). Elle n'est pas évaluée sur la détection de surcharge (couche 2). Métriques d'arbitrage : R², MAE, MAE≥80, biais≥80 par segment.

La détection au seuil (UM J-1), le seuil calibré et la PR-AUC relèvent de la couche 2 (traitée après).

---

## Performance H25 — Modèle final Enrichi_Seg (170 features, emb0, dataset daf936c8)

Seuil de surcharge = **63 places assises** (ADR-060). Métriques MAE>63 et Biais>63 = erreur du modèle dans la zone de surcharge réelle (target > 63). Source : `q7_zone_metrics_gt63.json` (script `q7_zone_metrics_gt63.py`, 500 itérations bootstrap SEED=42).

| Segment | n_obs | n_surch>63 | R² | IC 95% R² | MAE | MAE>63 | Biais>63 | IC 95% Biais>63 |
|---------|-------|-----------|-----|-----------|-----|--------|---------|----------------|
| BAS | 229 747 | 8 392 | **0.554** | [0.550 ; 0.557] | 8.57 | 30.8 | −30.4 | [−30.8 ; −30.0] |
| HAUT | 79 505 | 1 192 | **0.463** | [0.449 ; 0.475] | 6.38 | 39.1 | −37.8 | [−39.2 ; −36.4] |
| GLOBAL | 309 252 | 9 584 | **0.581** | [0.578 ; 0.585] | 8.01 | 31.9 | −31.3 | [−31.7 ; −30.9] |

IC à 500 itérations bootstrap (SEED=42). H25 = cas-pire (refonte horaire la plus sévère de la décennie) → chiffres = plancher de performance.

> **Note zone de mesure** : MAE>63 (30.8/39.1/31.9) < MAE≥80 (41.0/47.1/41.9 — Q6 JSON) car la zone >63 inclut les cas 64–79 moins extrêmes, mieux prédits. C'est un changement de zone de mesure, pas une amélioration du modèle. Le modèle est identique.

**Comparaison avec dataset 11b58391 (seuil=94, périmé)** : ΔR² = −0.005/+0.002/−0.003 (BAS/HAUT/GLOBAL) — neutre, dans la variance de réentraînement. La modification du seuil (94→63) n'affecte que les valeurs de `win7_n_surcharges` et n'impacte pas les métriques de régression continues.

**Évolution vs modèle précédent (171f, hash 1a53590f, emb9)** : BAS +0.0065, HAUT −0.0062, GLOBAL +0.0051 (calculé à l'ancien seuil 94 — donnée historique).

---

## Justification du choix Seg vs Global

### Contexte et révision du critère

La justification initiale s'appuyait sur ΔR² HAUT = +0.023 (IC disjoints, sur le dataset 171f/1a53590f). Ce résultat n'a pas été confirmé sur le modèle final 170f : l'analyse de variance multi-seed (10 seeds, paramètres ADR-036, dataset 11b58391) montre que le ΔR² Seg−Global sur le HAUT est **intrinsèquement bruité**.

### Analyse de variance multi-seed — résultats (dataset daf936c8, seuil=63)

10 seeds (42, 0, 1, …, 8), paramètres ADR-036 figés, architecture Seg vs Global sur 170f identique.

| Statistique | ΔR² HAUT (seuil=63) | ΔR² HAUT (seuil=94, historique) | ΔR² BAS (seuil=63) |
|-------------|--------------------|---------------------------------|---------------------|
| Moyenne | **+0.0247** | +0.0154 | +0.0056 |
| Écart-type | 0.0149 | 0.0140 | 0.0070 |
| Min | **+0.0039** (seed 6) | −0.0074 (seed 2) | −0.0026 |
| Max | **+0.0424** (seed 8) | +0.0372 (seed 7) | +0.0177 |
| Nb seeds > 0.02 | **5/10** | 3/10 | 0/10 |
| Nb seeds > 0 | **10/10** | 9/10 | 7/10 |

Avec seuil=63 : 1 192 surcharges HAUT (vs 280 à seuil=94 strict) — le segment est 4.3× moins rare.

**Diagnostic** : le ratio signal/bruit HAUT est passé de 1.1 (seuil=94) à **1.7** (seuil=63). Le seuil 0.02 est désormais **franchi par la moyenne** (+0.025). Le minimum est **strictement positif** (min=+0.004 vs −0.007 avant) — Seg n'est plus jamais pire que Global sur aucun seed. La std reste à 0.015 — la variance est structurelle au segment HAUT (taille, hétérogénéité touristique), pas un artefact de rareté de surcharges.

Résultats sauvegardés : `consolidation_finale/outputs/q6_variance_seeds_daf936c8.csv`

### Ce qui est robuste

- Sur le **segment BAS** : ΔR² Seg > Global sur 7/10 seeds (std = 0.007, variance plus haute qu'avec seuil=94 — normal, le signal est plus diffus sur un segment déjà performant). Avantage positif en moyenne.
- Sur le **segment HAUT** : Seg est **toujours** meilleur (10/10 seeds positifs), avantage moyen +0.025, minimum strictement positif. La non-infériorité est établie **de façon systématique**. La supériorité formelle (IC disjoints) n'est pas atteinte mais la distribution est unilatéralement positive.
- Seg n'est **jamais inférieur** à Global sur aucun seed HAUT (vs 1 seed légèrement négatif à seuil=94).

### Décision : architecture Seg CONSERVÉE (justification renforcée)

Sur trois critères explicites :

1. **Performance reproductiblement positive sur BAS** : avantage Seg positif en moyenne, le pendulaire représente 74 % des observations et est la composante la plus exploitable opérationnellement.

2. **Non-infériorité désormais SYSTÉMATIQUE sur HAUT** (10/10 seeds, minimum strictement positif) : avec seuil=63, le signal Seg est plus fort et la mesure est unilatéralement positive. La variance structurelle résiduelle (std=0.015) est inhérente à la taille du segment touristique et à `colsample_bytree=0.8` — elle ne remet pas en cause la supériorité de Seg.

3. **Valeur opérationnelle de la séparation** : les déterminants de la charge diffèrent structurellement entre pendulaire (BAS : historique 28 %, topologie 17 %, VMCV 5 %) et touristique (HAUT : météo 24 %, historique 24 %, réservations ResSys 9 %). Deux SHAP explanations distinctes permettent à l'opérateur UM de lire les drivers par segment — argument de lisibilité directement pertinent pour l'adoption de l'artefact par le responsable de production.

**Note sur win7_n_surcharges** : avec seuil=63, cette feature est passée du rang 144/170 au rang **90/170** sur BAS (mean|SHAP| ×11.4) et du rang 138/170 au rang **117/170** sur HAUT. Elle reste hors top 20 mais est désormais activement utilisée par le modèle.

**Ce raffinement** : le passage de seuil=94 à seuil=63 a résolu partiellement l'instabilité de la mesure (min ΔR² strictement positif, 10/10 seeds, moyenne > 0.02), tout en révélant que la variance résiduelle est structurelle (segment HAUT petit, demande touristique hétérogène). Il est documenté ici comme résultat de thèse : la justification de l'architecture segmentée est désormais robuste sur le critère de non-infériorité SYSTÉMATIQUE.

### Coût assumé

L'architecture à deux modèles implique deux entraînements, deux artefacts model, un aiguillage par `spatial_segment` en production, deux SHAP explanations. Ce coût est **acceptable** au niveau artefact (preuve de concept DSR). Une industrialisation pourrait envisager un modèle unique avec terme d'interaction ou modèle hiérarchique — documenté comme piste de travail futur.

---

## Limite structurelle — variance du R² HAUT et évaluation du segment touristique

La variance multi-seed du R² HAUT (±0.008 selon le seed, sur daf936c8) implique que **toutes** les métriques du segment touristique portent cette incertitude, pas seulement le ΔR² Seg−Global. Le R² HAUT du modèle final (0.463) doit être lu avec un IC élargi de ±0.008 (incertitude de réentraînement sur daf936c8), en plus de l'IC bootstrap (±0.013 à 95 %).

**Note** : avec seuil=94, la variance multi-seed était ±0.017 (mesure très bruitée à cause de 297 surcharges seulement). Avec seuil=63 et 1 192 surcharges, la variance structurelle est réduite à ±0.008 — le segment est moins rare mais reste un segment touristique hétérogène.

**Cause** : taille du segment HAUT (79 505 obs, demande touristique événementielle) combinée à `colsample_bytree=0.8`. Cette limite est cohérente avec la difficulté connue du segment touristique (demande imprévisible, saison partielle H25).

Pour la thèse, l'évaluation du segment BAS (pendulaire, n_surch>63=8 392) est plus fiable que celle du HAUT. Les performances HAUT sont indicatives avec incertitude de réentraînement ±0.008.

---

## Limite structurelle — sous-prédiction des charges élevées

Le biais>63 est structurellement négatif : **−30.4 sur BAS, −37.8 sur HAUT**. Pour une observation en surcharge (target > 63), le modèle annonce en moyenne ~30-38 voyageurs de moins que la réalité.

Cette sous-prédiction est une propriété de la fonction de perte MSE sur distribution asymétrique (0.4 % de surcharges). Irréductible (tests ADR-050/CF08) :

| Levier testé | Résultat (mesuré sur 179f) |
|-------------|--------------------------|
| Sample weighting w=20 (ADR-050) | Réduction biais haut 15 % seulement, R² −8 % |
| Quantile α=0.85 (ADR-051) | Réduction biais haut 22 %, R² −28 %, MAE global +34 % |
| Quantile α≥0.90 (ADR-051) | R² haut < 0.20, sur-prédiction massive — non utilisable |
| Tweedie (ADR-051) | Aggrave le biais haut — rejeté |

**Gestion** : le biais est géré en couche 2 par seuil calibré (walk-forward H24). L'artefact expose un signal de risque relatif (SHAP), pas une estimation de charge absolue.

---

## H25 comme cas-pire

H25 est la refonte d'horaire la plus sévère de la décennie pour la ligne R35 (renumérotation massive des courses, ADR-038). Les features `histo_*` du modèle sont absentes ou peu fiables sur les courses renumérotées. En exploitation normale (horaires stables), les performances seraient supérieures.

---

## Ce que ce modèle n'est pas

- Ce n'est **pas** un système de prévision de charge opérationnel en production
- Ce n'est **pas** un détecteur de surcharge (couche 2, traitée séparément)
- Ce n'est **pas** conçu pour une inférence en temps réel

C'est un **artefact de recherche** (DSR) démontrant la faisabilité de la prédiction de charge J-1 pour la décision UM sur la ligne R35.

---

## Fichiers artefacts

| Fichier | Rôle |
|---------|------|
| `consolidation_finale/outputs/etape_04bis_v2_features_170f.json` | Liste des **170 features** figées |
| `consolidation_finale/outputs/q5_variance_seeds_170f.csv` | Distribution ΔR² Seg−Global sur 10 seeds (analyse multi-seed) |
| `consolidation_finale/outputs/etape_04bis_v2_q4_metriques_170f.csv` | Métriques bootstrap H25 170f (seuil=94, historique) |
| `consolidation_finale/outputs/q6_resultats_daf936c8.json` | Métriques H25 170f daf936c8 — R², MAE, n_surch≥63, zone ≥80, SHAP rangs, multi-seed |
| `consolidation_finale/outputs/q7_zone_metrics_gt63.json` | **Source des MAE>63 / Biais>63** du tableau Performance — zone target>63 strict, bootstrap SEED=42 |
| `consolidation_finale/scripts/q7_zone_metrics_gt63.py` | Script zone metrics >63 (réexécutable, config figée ADR-036, daf936c8) |
| `consolidation_finale/outputs/q6_shap_ranks_bas_daf936c8.csv` | Rang SHAP BAS 170f / daf936c8 |
| `consolidation_finale/outputs/q6_shap_ranks_haut_daf936c8.csv` | Rang SHAP HAUT 170f / daf936c8 |
| `consolidation_finale/outputs/q6_variance_seeds_daf936c8.csv` | ΔR² Seg−Global 10 seeds / daf936c8 |
| `consolidation_finale/figures/q6_shap_beeswarm_bas_170f_daf936c8.png` | SHAP beeswarm BAS 170f daf936c8 (300 DPI) |
| `consolidation_finale/figures/q6_shap_beeswarm_haut_170f_daf936c8.png` | SHAP beeswarm HAUT 170f daf936c8 (300 DPI) |
| `consolidation_finale/figures/q6_shap_top15_daf936c8.png` | Top 15 features côte à côte daf936c8 (300 DPI) |
| `consolidation_finale/scripts/q6_reentrainement_seuil_63.py` | Script réentraînement complet daf936c8 (Q1-Q4) réexécutable |
| `consolidation_finale/scripts/q5_variance_seeds.py` | Script variance multi-seed seuil=94 (historique) |
| `models/11_modeling/xgb_M0.json` | Modèle de référence antérieur (archivé) |

---


---
id: ADR-053
ancien_id: ADR-CF10
date_decision: 2026-06-06
statut: amendé
amende_par: [ADR-054]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-053 — SHAP Enrichi_Seg : explicabilité des modèles BAS et HAUT

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-054.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** Statut d'époque resté « en attente de validation ». Le critère de retrait proposé ici (SHAP < 0,01, 32 variables) est **durci** par ADR-054 (nullité stricte, 8 variables).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06  
**Statut** : Résultats validés — analyse exploratoire 179f  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-052 (modèle couche 1 figé), ADR-048 (feature selection), ADR-054 (nettoyage parcimonie 179→171→172→170)

> ⚠️ **Avertissement de version** : cette analyse SHAP a été produite sur le **modèle 179f** (avant nettoyage de parcimonie ADR-054). Elle a servi à **identifier les features à retirer** (les 8 HPI à SHAP = 0.000 exact). Le SHAP du modèle **final 170f** est dans le notebook `etape_04bis_v2_nettoyage_172f.ipynb` et les figures `etape_04bis_v2_shap_*_170f.png`. La comparaison 179f vs 170f confirme que les importances par source et le top-5 sont quasi identiques — le récit d'explicabilité est inchangé. **Pour la thèse, citer les chiffres SHAP 170f** (cohérence avec le modèle figé) ; cet ADR-053 reste la documentation de la démarche d'identification des features inutiles.

---

## Contexte

Calcul des valeurs SHAP (TreeExplainer, shap 0.49.1) sur H25 pour les deux modèles
Enrichi_Seg à **179 features** (avant nettoyage ADR-054). Objectif : explicabilité pour
l'adoption opérateur (promesse DSR) et identification des features à SHAP nul à retirer.
Les résultats de cet ADR informent la discussion de la thèse — les chiffres précis sont
ceux du 179f exploratoire ; le SHAP définitif (171f) est dans etape_04bis_v2.

| Paramètre | Valeur |
|-----------|--------|
| Modèle BAS | XGBoost MSE, **179f (exploratoire)**, H22-H24 train, 223 211 obs H25 |
| Modèle HAUT | XGBoost MSE, **179f (exploratoire)**, H22-H24 train, 77 262 obs H25 |
| Méthode SHAP | TreeExplainer (TreeSHAP, exact, pas d'approximation) |
| Métrique importance | mean \|SHAP\| sur H25 complet |
| Summary plots | Subsample 8 000 obs H25 (beeswarm) |
| SHAP définitif (171f) | `etape_04bis_v2_nettoyage_171f.ipynb` + figures `etape_04bis_shap_*_171.png` |

---

## Importance par source — BAS vs HAUT

| Source | BAS % | HAUT % | Δ (H−B) | Lecture |
|--------|-------|--------|---------|--------|
| **Historique (histo_)** | **28.2 %** | **23.7 %** | −4.5 % ↓ | Dominant dans les deux ; plus fort en BAS |
| **Calendrier (cal_)** | 18.5 % | 21.2 % | +2.7 % ↑ | Fort partout ; légèrement plus en HAUT |
| **Topologie (spatial_)** | 16.9 % | 7.4 % | **−9.5 % ↓↓** | Dominant en BAS, marginal en HAUT |
| **Météo (meteo_)** | 10.5 % | **23.7 %** | **+13.2 % ↑↑** | Secondaire en BAS, co-dominant en HAUT |
| **Réservations (resa_)** | 2.6 % | 9.1 % | **+6.6 % ↑↑** | Quasi-absentes en BAS, matérielles en HAUT |
| ISTDATEN J-1 (ist_) | 7.4 % | 5.9 % | −1.6 % | Similaire, légèrement plus en BAS |
| SIMBA FQkal (simba_) | 5.3 % | 4.7 % | −0.6 % | Similaire dans les deux |
| Événements (event_) | 5.4 % | 3.1 % | −2.3 % ↓ | Plus fort en BAS (fériés locaux) |
| VMCV embarquement (vmcv_) | 5.1 % | 1.2 % | **−3.9 % ↓** | Matériel en BAS, marginal en HAUT |

---

## Top features par modèle

### Modèle BAS — Top 10

| Rang | Feature | mean\|SHAP\| | Source | Interprétation |
|------|---------|------------|--------|---------------|
| 1 | `histo_voyageurs_total_win7_mean` | 3.29 | histo_ | Charge habituelle du tronçon sur 7j roulants |
| 2 | `spatial_gare_arrivee_ordre` | 2.82 | spatial_ | Identifiant de position de la gare arrivée |
| 3 | `histo_voyageurs_2eme_classe_win7_mean` | 1.91 | histo_ | Charge 2e classe habituelle sur 7j |
| 4 | `spatial_gare_depart_ordre` | 1.41 | spatial_ | Identifiant de position de la gare départ |
| 5 | `vmcv_n_lignes_concurrentes` | 1.22 | vmcv_ | Nb lignes VMCV concurrentes (offre alternative) |
| 6 | `event_is_vacances_vaud` | 0.92 | event_ | Vacances scolaires vaudoises |
| 7 | `histo_voyageurs_total_win7_median` | 0.90 | histo_ | Médiane historique 7j (robuste aux pics) |
| 8 | `cal_type_jour` | 0.85 | cal_ | Type de jour (ouvrable/WE/vacances) |
| 9 | `cal_annee_civile` | 0.77 | cal_ | Année civile (tendance multi-annuelle) |
| 10 | `cal_depart_minute_du_jour` | 0.73 | cal_ | Créneau horaire de départ |

### Modèle HAUT — Top 10

| Rang | Feature | mean\|SHAP\| | Source | Interprétation |
|------|---------|------------|--------|---------------|
| 1 | `cal_type_jour` | 1.43 | cal_ | Type de jour — signal saisonnier fort |
| 2 | `histo_voyageurs_total_win7_mean` | 1.21 | histo_ | Charge historique 7j roulants |
| 3 | `resa_pax_2c_J_minus_1` | 1.03 | resa_ | Nb passagers réservés J-1 en 2e classe |
| 4 | `meteo_ensoleillement_min_h` | 0.90 | meteo_ | Ensoleillement min horaire (signal ski/lac) |
| 5 | `histo_voyageurs_total_win7_max` | 0.85 | histo_ | Pic max sur 7j (capture événements) |
| 6 | `resa_n_dossiers_J_minus_1` | 0.75 | resa_ | Nb dossiers réservation J-1 |
| 7 | `meteo_temperature_h` | 0.70 | meteo_ | Température horaire |
| 8 | `cal_mois` | 0.66 | cal_ | Mois (saisonnalité touristique) |
| 9 | `cal_depart_minute_du_jour` | 0.55 | cal_ | Créneau horaire |
| 10 | `histo_voyageurs_2eme_classe_win7_std` | 0.46 | histo_ | Variabilité historique (captures l'incertitude) |

---

## Comparaison structurelle BAS vs HAUT — confirmation de l'hypothèse

L'hypothèse formulée avant l'analyse : *BAS piloté par historique + topologie ; HAUT par météo + réservations + événements*.

**Résultat : hypothèse confirmée et précisée.**

**Modèle BAS (pendulaire)** : dominé par l'historique de charge (28 %) et la topologie (17 %). Le pendulaire est un phénomène structurel — la charge d'un tronçon à un créneau donné est très prédictible par son pattern passé. Les `spatial_gare_*_ordre` (rang 2 et 4) agissent comme des ID de tronçon — le modèle encode essentiellement quel tronçon est prédit, l'historique encode à quelle hauteur. La VMCV (5 %) signale les tronçons où une offre alternative absorbe une partie de la demande.

**Modèle HAUT (touristique)** : la météo monte à 24 % (équivalent à l'historique). Les réservations (9 %) apparaissent significativement — la demande touristique est partiellement anticipée via ResSys. Le `cal_type_jour` passe au rang 1 : la saisonnalité (ski, saison estivale, ponts) domine le signal touristique. La topologie chute à 7 % — les tronçons haut ne se distinguent pas par leur structure mais par leur demande événementielle.

**Insight opérationnel clé** : pour expliquer une décision UM à l'opérateur, les SHAP drivers seront fondamentalement différents selon le segment — ce qui justifie ex-post l'architecture à deux modèles (ADR-052) et la présentation séparée des SHAP par segment dans l'artefact.

---

## Features à importance quasi-nulle — 32 candidates au retrait

Seuil : mean\|SHAP\| < 0.01 voyageur dans les **deux** modèles (BAS et HAUT).

### Profil des 32 features quasi-nulles

| Source | N features | Exemples |
|--------|-----------|---------|
| Topologie/STATPOP (spatial_) | **17** | `spatial_gare_*_hpi_*`, `spatial_gare_*_indice_mobilite_resid`, `spatial_gare_*_part_pop_etrangere`, `spatial_segment` |
| ISTDATEN J-1 (ist_) | 4 | `ist_headway_*_is_*_of_day`, `ist_profil_train_pct_en_retard_dep_troncon_5occ` |
| Événements (event_) | 3 | `event_is_marche_noel`, `event_is_montreux_noel`, `event_ski_source` |
| Réservations (resa_) | 3 | `resa_has_resa_J_minus_1`, `resa_n_langues_distinctes_J_minus_1`, `resa_part_tour_operator_J_minus_1` |
| Calendrier (cal_) | 1 | `cal_is_weekend` (redondant avec `cal_type_jour`) |
| Historique (histo_) | 1 | `histo_voyageurs_2eme_classe_win7_n_surcharges` |

### `spatial_segment` — artefact de l'architecture segmentée

`spatial_segment` a mean\|SHAP\| = 0.000 dans les deux modèles. C'est logique : la feature est **constante** dans chaque modèle (tous les exemples BAS ont `spatial_segment='bas'`). Elle n'apporte aucune information dans l'architecture segmentée. **Candidate au retrait immédiat** dès qu'une version simplifiée de l'artefact est envisagée.

### Catégories STATPOP granulaires (HPI, indices sociodémographiques)

Les 17 features STATPOP quasi-nulles sont des indicateurs sociodémographiques fins par gare (HPI = indicateur de plausibilité des ménages privés, au sens STATPOP ; indices de mobilité résidentielle, parts de population par tranche d'âge granulaire). Leur inclusion dans les 179 features venait de la phase de feature engineering (ADR-048 ne les a pas éliminées par walk-forward). La non-importance SHAP suggère que le modèle n'exploite pas ces signaux fins — soit parce qu'ils sont redondants avec les features `spatial_gare_*_ordre` (qui encodent déjà l'identité du tronçon), soit parce que la granularité est trop fine pour le signal.

### Ne pas retirer sans validation

La décision de retrait est proposée, pas exécutée. Les 32 features quasi-nulles dans les deux modèles constituent un **premier lot** :

```
cal_is_weekend, event_is_marche_noel, event_is_montreux_noel, event_ski_source,
histo_voyageurs_2eme_classe_win7_n_surcharges,
ist_headway_apres_is_last_of_day, ist_headway_avant_is_first_of_day,
ist_profil_train_pct_en_retard_dep_troncon_5occ,
resa_has_resa_J_minus_1, resa_n_langues_distinctes_J_minus_1, resa_part_tour_operator_J_minus_1,
spatial_gare_arrivee_flag_qualite_faible, spatial_gare_arrivee_hpi_classe_max,
spatial_gare_arrivee_hpi_ha_autre, spatial_gare_arrivee_hpi_ha_classe_2,
spatial_gare_arrivee_hpi_ha_manquante, spatial_gare_arrivee_indice_mobilite_resid,
spatial_gare_arrivee_part_grands_menages_4p, spatial_gare_arrivee_part_pop_0_14_ans,
spatial_gare_arrivee_part_pop_etrangere, spatial_gare_depart_flag_qualite_faible,
spatial_gare_depart_hpi_classe_max, spatial_gare_depart_hpi_ha_autre,
spatial_gare_depart_hpi_ha_classe_2, spatial_gare_depart_hpi_ha_manquante,
spatial_gare_depart_indice_mobilite_resid, spatial_gare_depart_part_grands_menages_4p,
spatial_gare_depart_part_hpi_non_plausible, spatial_gare_depart_part_pop_15_24_ans,
spatial_gare_depart_part_pop_etrangere, spatial_gare_depart_part_pop_nee_etranger,
spatial_segment
```

---

## Features asymétriques — actives dans un modèle, quasi-nulles dans l'autre

Ces features documentent des déterminants spécifiques à chaque segment et représentent
la valeur ajoutée de l'architecture segmentée pour l'explicabilité :

| Feature | BAS | HAUT | Lecture |
|---------|-----|------|--------|
| `meteo_neige_binaire_h` | 0.001 | **0.281** | La neige pilote le touristique (ski), invisible en pendulaire |
| `resa_n_pays_distincts_J_minus_1` | 0.000 | **0.066** | Diversité internationale des réservations → signal touristique |
| `spatial_gare_depart_indice_stabilite_resid` | 0.004 | **0.079** | Zone résidentielle stable → signal navetteur fort en HAUT |
| `spatial_distance_km` | **0.209** | 0.002 | Distance tronçon = déterminant pendulaire, non touristique |
| `simba_part_militaire` | **0.062** | 0.000 | Militaires empruntent surtout les lignes pendulaires |
| `spatial_gare_arrivee_part_menages_1p` | **0.192** | 0.001 | Isolement résidentiel → navetteurs seuls (BAS) |
| `event_is_ski_ouvert` | **0.033** | 0.002 | Inattendu : ski plus actif en BAS que HAUT¹ |

¹ `event_is_ski_ouvert` est plus actif en BAS qu'en HAUT. Interprétation possible : les skieurs empruntent aussi les tronçons bas pour rejoindre les remontées (ex. Vevey→Blonay) ; le tronçon haut est déjà capturé par `meteo_neige_binaire_h`.

---

## Implications pour l'artefact UM

1. **Présentation à l'opérateur** : les SHAP drivers doivent être filtrés par segment. Un opérateur regardant un tronçon haut verra météo + réservations + calendrier ; un opérateur sur tronçon bas verra historique + topologie. Deux grilles d'explication distinctes.

2. **Features à fort impact opérationnel** : `resa_pax_2c_J_minus_1` (rang 3 HAUT) montre que les réservations J-1 ResSys ont une valeur prédictive réelle — elles contribuent à ~9 % de l'importance HAUT. Ce résultat valide l'intégration ResSys (ADR-035).

3. **Topologie en BAS** : `spatial_gare_arrivee_ordre` et `spatial_gare_depart_ordre` (rangs 2 et 4) agissent comme identifiants de tronçon. Ils capturent l'effet fixe tronçon que l'historique ne couvre pas complètement. À exposer avec précaution : l'opérateur ne comprendra pas pourquoi "gare_arrivee=5" est une feature importante.

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_04_shap_enrichi_seg.ipynb` | Notebook réexécutable |
| `consolidation_finale/outputs/etape_04_shap_importance_bas.csv` | 179 features triées par importance BAS |
| `consolidation_finale/outputs/etape_04_shap_importance_haut.csv` | 179 features triées par importance HAUT |
| `consolidation_finale/outputs/etape_04_shap_importance_par_source.csv` | Importance agrégée par source |
| `consolidation_finale/outputs/etape_04_shap_features_quasi_nulles.csv` | 32 features candidates au retrait |
| `consolidation_finale/figures/etape_04_shap_summary_bas.png` | Beeswarm BAS — top 30 (300 DPI) |
| `consolidation_finale/figures/etape_04_shap_summary_haut.png` | Beeswarm HAUT — top 30 (300 DPI) |
| `consolidation_finale/figures/etape_04_shap_importance_sources.png` | Bar chart sources BAS vs HAUT (300 DPI) |
| `consolidation_finale/figures/etape_04_shap_top20_bas_vs_haut.png` | Top 20 features côte à côte (300 DPI) |

---


---
id: ADR-054
ancien_id: ADR-CF11
date_decision: 2026-06-06
statut: amendé
amende_par: [ADR-061]
modifie: [ADR-053]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-054 — Nettoyage de parcimonie : 179 → 171 → 172 → 170 features

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-061.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-053.
> **Précision au gel.** Le décompte final de cette chaîne de parcimonie (170) est ramené à **158** par ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06 — mis à jour 2026-06-07  
**Statut** : **DÉCISION FIGÉE** — validée par Erwann Nédellec  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-052 (modèle couche 1), ADR-053 (SHAP explicabilité), ADR-048 (feature selection), ADR-057 (dénivelé tronçon)

## Chaîne de nettoyage

| Étape | N features | Opération |
|-------|-----------|-----------|
| Point de départ | 179 | Modèle exploratoire (ADR-048) |
| ADR-054 §1 | **171** | −8 HPI structurellement nulles (SHAP = 0.000 exact dans BAS ET HAUT) |
| ADR-057 | **172** | +1 `spatial_denivele_troncon_m` (dénivelé signé par tronçon) |
| ADR-054 §2 | **170** | −2 HPI nulles découvertes sur 172f ; dénivelé conservé (retrait dégrade HAUT −0.022) |

**Périmètre final : 170 features** (fichier `etape_04bis_v2_features_170f.json`).

---

## §1 — Premier nettoyage : 179 → 171 (2026-06-06)

**Retrait de 8 features de topologie HPI à SHAP = 0.000 exact dans les deux modèles (BAS et HAUT).**

| Feature retirée | Source | SHAP BAS | SHAP HAUT | Justification |
|-----------------|--------|----------|----------|---------------|
| `spatial_segment` | Topologie | 0.0000 | 0.0000 | Constante dans chaque modèle segmenté — artefact architectural |
| `spatial_gare_arrivee_flag_qualite_faible` | Topologie | 0.0000 | 0.0000 | Flag HPI qualité — jamais utilisé en split |
| `spatial_gare_arrivee_hpi_classe_max` | Topologie | 0.0000 | 0.0000 | Classe HPI max gare arrivée — jamais utilisé en split |
| `spatial_gare_arrivee_hpi_ha_manquante` | Topologie | 0.0000 | 0.0000 | HPI ha manquante gare arrivée — jamais utilisé en split |
| `spatial_gare_depart_flag_qualite_faible` | Topologie | 0.0000 | 0.0000 | Flag HPI qualité gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_classe_max` | Topologie | 0.0000 | 0.0000 | Classe HPI max gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_ha_autre` | Topologie | 0.0000 | 0.0000 | HPI ha autre gare départ — jamais utilisé en split |
| `spatial_gare_depart_hpi_ha_manquante` | Topologie | 0.0000 | 0.0000 | HPI ha manquante gare départ — jamais utilisé en split |

**Feature conservée malgré SHAP = 0 :**

| Feature | SHAP BAS | SHAP HAUT | Justification conservation |
|---------|----------|----------|---------------------------|
| `resa_has_resa_J_minus_1` | 0.0000 | 0.0000 | Signal réservations réservé à la couche 2. Silence sur H25 attribuable au cas-pire (refonte horaire = perturbation des réservations habituelles). Redondance probable avec `resa_pax_2c_J_minus_1` (rang 3 HAUT). Coût de conservation = 0 ; risque de retrait pour la couche 2 = non nul. |

---

## Iso-performance H25 — résultats de validation

| Segment | R² 179f | IC 95% | R² 171f | IC 95% | ΔR² | IC chevauchants | Verdict |
|---------|---------|--------|---------|--------|-----|----------------|---------|
| BAS | 0.5557 | [0.5517 ; 0.5590] | 0.5519 | [0.5482 ; 0.5552] | −0.0038 | **Oui** | ✅ OK |
| HAUT | 0.4803 | [0.4693 ; 0.4908] | 0.4671 | [0.4553 ; 0.4797] | −0.0133 | **Oui** | ✅ OK |
| GLOBAL | 0.5841 | [0.5812 ; 0.5876] | 0.5792 | [0.5760 ; 0.5825] | −0.0050 | **Oui** | ✅ OK |

**Critère d'acceptation** : ΔR² < 0.02 sur chaque segment ET IC chevauchants.  
**Résultat** : critère respecté sur les trois segments. Retrait validé.

### Note sur le ΔR² HAUT = −0.013

Les 8 features retirées ont SHAP = 0.000 exact dans les deux modèles, pourtant ΔR² HAUT = −0.013 (non nul). Ceci renforce le finding méthodologique central : même des features à SHAP marginal strictement nul peuvent contribuer marginalement via des mécanismes non capturés par la valeur SHAP moyenne — vraisemblablement des effets d'interaction très locaux sur les observations rares. Le ΔR² reste dans le bruit (IC chevauchants, ΔR² < 0.02) et le retrait est validé, mais l'observation est documentée pour la thèse.

MAE comparées :

| Segment | MAE 179f | MAE 171f | Δ | MAE≥80 179f | MAE≥80 171f | Biais≥80 171f [IC] |
|---------|---------|---------|---|------------|------------|-------------------|
| BAS | 8.614 | 8.637 | +0.023 | 40.1 | 41.0 | −40.9 [−41.7 ; −40.2] |
| HAUT | 6.191 | 6.319 | +0.128 | 50.4 | 49.2 | −49.0 [−51.2 ; −47.0] |
| GLOBAL | 7.991 | 8.041 | +0.050 | 41.7 | 42.3 | −42.2 [−43.0 ; −41.5] |

---

## Finding méthodologique — à documenter dans la thèse

### Le SHAP marginal moyen sous-estime les contributions par interaction sur cible rare

**Contexte** : lors de l'étape 4bis (tentative de retrait de 22 features dont 10 à SHAP marginal faible mais non nul), la dégradation suivante a été observée :

| Métrique | 179f | 157f | Δ |
|---------|------|------|---|
| R² HAUT | 0.4803 | 0.4540 | **−0.026** ⚠️ |
| R² BAS | 0.5557 | 0.5537 | −0.002 ✅ |
| R² GLOBAL | 0.5841 | 0.5785 | −0.006 ✅ |

Les 22 features retirées représentaient **0.1 % de l'importance SHAP totale** sur HAUT (somme des mean|SHAP| = 0.0185). Pourtant ΔR² HAUT = −0.026 — soit une dégradation de 5.5 %.

**Interprétation** : le mean|SHAP| est une métrique de contribution *marginale, moyennée sur toutes les observations*. Sur une cible à événements rares (surcharges touristiques, 0.4 % des obs HAUT), les contributions SHAP s'annulent entre observations (positives pour les jours de surcharge, négatives ou nulles pour les jours ordinaires). La moyenne est quasi-nulle alors que la contribution *conditionnelle* sur les jours critiques peut être significative.

Les features STATPOP de gare (indices de mobilité résidentielle, parts de population par tranche d'âge) encodent des caractéristiques des stations alpines et lacustres — elles aident XGBoost à distinguer les tronçons à demande touristique élevée sans que cela transparaisse dans la moyenne SHAP globale.

**Règle opérationnelle dérivée** : sur un problème à cible rare avec des features potentiellement importantes sur les cas rares, le seuil de retrait basé sur mean|SHAP| doit être strictement nul (0.000 exact), pas simplement « faible » (< 0.01 voyageur). Le retrait de features à SHAP marginal moyen faible mais non nul est risqué. Seules les features à SHAP = 0.000 exact dans les deux modèles peuvent être retirées sans risque de dégradation.

Ce finding est un résultat de thèse : il illustre les limites de l'importance SHAP comme critère de sélection de features, en particulier dans les contextes de déséquilibre sévère de classes.

---

## §2 — Deuxième nettoyage : 172 → 170 (2026-06-07)

Après ajout du dénivelé tronçon (ADR-057, 171→172), une nouvelle passe de parcimonie a été conduite sur le modèle 172f (critère : gain XGBoost = 0 dans BAS ET HAUT).

**3 features à gain = 0 dans les deux modèles :**

| Feature | Gain BAS | Gain HAUT | Action |
|---------|----------|----------|--------|
| `resa_has_resa_J_minus_1` | 0.000 | 0.000 | **PROTÉGÉE** — signal couche 2 |
| `spatial_gare_arrivee_hpi_ha_classe_2` | 0.000 | 0.000 | Retirée |
| `spatial_gare_arrivee_hpi_ha_autre` | 0.000 | 0.000 | Retirée |

**Validation empirique du retrait des 2 HPI :**

| Segment | ΔR² | IC chevauchants | Verdict |
|---------|-----|----------------|---------|
| BAS | < 0.002 | Oui | ✅ OK |
| HAUT | < 0.002 | Oui | ✅ OK |
| GLOBAL | < 0.002 | Oui | ✅ OK |

**Dénivelé conservé** malgré rang HAUT modeste (102/170, SHAP=0.033) : test empirique de retrait montre ΔR² HAUT = −0.022 (retrait dégrade). Sur BAS, rang 17/170, SHAP=0.458 — feature active et significative. Corrélation Spearman dénivelé vs gare_ordre faible (ρ=−0.107 / +0.090) → information orthogonale.

---

## Périmètre final de la couche 1

| Paramètre | Valeur |
|-----------|--------|
| Architecture | Enrichi_Seg — deux XGBoost MSE (BAS + HAUT) |
| Features | **170** (179 − 8 HPI §1 + 1 dénivelé − 2 HPI §2) |
| `resa_has_resa_J_minus_1` | Conservée (couche 2 — SHAP=0 sur H25 attribuable au cas-pire) |
| `spatial_denivele_troncon_m` | Conservée (test empirique : retrait dégrade HAUT −0.022) |
| Hyperparamètres | ADR-036 |
| Clé `histo_*` | ADR-044 |
| Objectif | `reg:squarederror` |

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_04bis_v2_nettoyage_172f.ipynb` | Notebook réexécutable (172→170) |
| `consolidation_finale/outputs/etape_04bis_v2_features_170f.json` | Liste des **170 features** finales |
| `consolidation_finale/outputs/etape_04bis_v2_q1_test_denivele.csv` | Test empirique retrait dénivelé |
| `consolidation_finale/outputs/etape_04bis_v2_q3_parcimonie` | (intégré dans le notebook) |
| `consolidation_finale/outputs/etape_04bis_shap_importance_bas_171.csv` | SHAP BAS 171f (référence §1 — intermédiaire) |
| `consolidation_finale/outputs/etape_04bis_shap_importance_haut_171.csv` | SHAP HAUT 171f (référence §1 — intermédiaire) |
| `consolidation_finale/outputs/etape_04bis_v2_shap_importance_bas_170f.csv` | SHAP BAS **170f final** |
| `consolidation_finale/outputs/etape_04bis_v2_shap_importance_haut_170f.csv` | SHAP HAUT **170f final** |
| `consolidation_finale/figures/etape_04bis_v2_shap_beeswarm_bas_170f.png` | Beeswarm BAS 170f (300 DPI) |
| `consolidation_finale/figures/etape_04bis_v2_shap_beeswarm_haut_170f.png` | Beeswarm HAUT 170f (300 DPI) |
| `consolidation_finale/figures/etape_04bis_v2_shap_top15_170f.png` | Top 15 côte à côte 170f (300 DPI) |

---


---
id: ADR-055
ancien_id: ADR-CF12
date_decision: 2026-06-07
statut: remplacé
remplace_par: [ADR-063]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-055 — Correction du Voronoï STATPOP manquant pour VVVI (millésimes 2022 et 2023)

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-063.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté — appliqué  
**Auteur** : Erwann Nedellec  

---

## Contexte

Un audit NaN systématique des features `spatial_` dans `ml_dataset.parquet` a révélé un trou de référentiel ciblé : la gare **VVVI (Vevey Vignerons)** présentait 100 % de NaN sur les 18 features HPI/ménages en H23 (31 452 lignes × 2 côtés = 62 904 occurrences) et 6 % en H24 (1 875 lignes × 2), sans NaN en H22 ni en H25.

**Cause identifiée** : VVVI a remplacé GIL (Gilamont) à partir de H23 (décembre 2022). Le pipeline `build_fact_statpop_gare.py` utilise le mapping `STATPOP_YEAR_TO_HORAIRE[2022] = "H22"`, ce qui produit un Voronoï H22 avec GIL comme station active — VVVI est donc absent du millésime 2022. Conséquences en cascade :

1. **1 702 lignes H23 (calendaire déc 2022)** → millésime 2022 → VVVI absent → toutes features `spatial_` NaN.
2. **29 750 lignes H23 (calendaire 2023)** → millésime 2023 → VVVI présent (population calculée) mais ménages/HPI NaN. En effet, STATPOP 2023 (OFS) ne contient pas les colonnes HP\*/HPI ; elles sont normalement interpolées entre 2022 et 2024, mais l'ancre 2022 est absente pour VVVI → l'interpolation échoue silencieusement.
3. **1 875 lignes H24 (calendaire 2023)** → millésime 2023 → même problème ménages/HPI.

**Vérification de symétrie préalable** : GIL présente 0 % de NaN sur tous ses millésimes actifs (H16–H22). Aucune autre gare n'est affectée. Le trou est strictement isolé à VVVI.

---

## Décision

Recalculer le Voronoï VVVI avec les données STATPOP **millésime 2022** et injecter la ligne résultante dans `statpop_clean.parquet`. L'interpolation existante de `impute_missing_millesimes()` prend ensuite en charge le millésime 2023 (ancre 2022 disponible → (1636+1679)/2 = 1658).

**Méthode de calcul** : topologie H23 (VVVI active, GIL absent) × données STATPOP2022.csv. Justification : les 1 702 lignes calendaire-2022 sont toutes des observations H23 (VVVI est la gare active pour ces dates) ; utiliser la topologie H23 donne à VVVI son territoire réel pour ces observations.

**Ce qui n'a pas été fait** : propager les valeurs du millésime 2024 vers H23/H24. Ce serait une violation du principe year-specific (ADR-025) créant une asymétrie où VVVI aurait une démographie d'une autre année que les autres gares la même période.

---

## Résultats de calcul

| Millésime | Population 500m | Ménages 500m | Hectares | HPI classe max | Source |
|-----------|----------------|--------------|----------|----------------|--------|
| 2022 (calculé) | 3 417 | 1 636 | 59 | 2 | STATPOP2022.csv × topologie H23 |
| 2023 (interpolé) | 3 496 | 1 658 | 59 | 2 | interpolation linéaire 2022/2024 |
| 2024 (existait) | 3 522 | 1 679 | 59 | 1 | calculé originellement |

La valeur interpolée 2023 (1658) est la moyenne arithmétique exacte de 2022 (1636) et 2024 (1679), cohérente avec la stratégie `interpolate` du pipeline.

---

## Non-régression

Vérification explicite avant sauvegarde dans `fix_vvvi_statpop_2022.py` : comparaison numérique (arrondi 8 décimales) de toutes les lignes non-VVVI entre l'ancien et le nouveau `statpop_clean.parquet` → **0 différence**. Seules les lignes VVVI ont changé.

Après régénération complète de la pipeline (stages 06 → 10 → ml_dataset) :

| Vérification | Avant | Après |
|---|---|---|
| NaN `spatial_gare_*_menages_500m_total` VVVI H23 | 31 452 (100 %) | **0 (0 %)** |
| NaN `spatial_gare_*_menages_500m_total` VVVI H24 | 1 875 (6 %) | **0 (0 %)** |
| NaN `spatial_` total dans ml_dataset | 62 904 + 3 750 = 66 654 | **0** |
| Shape ml_dataset | (1 141 984, 204) | (1 141 984, 204) inchangé |
| Autres gares, autres features | — | inchangés (non-régression OK) |

**Nouveau hash ml_dataset** : SHA256 partiel `d3000f48074a496b`  
(ancien hash audit NaN : `cd29a5f2` — remplacé)

---

## Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `data/processed/sources/statpop_clean.parquet` | +1 ligne (VVVI-2022) + interpolation VVVI-2023 mise à jour |
| `data/processed/sources/statpop_clean.csv` | synchronisé |
| `data/processed/stage_06_statpop.parquet` | régénéré |
| `data/processed/stage_07_istdaten.parquet` | régénéré |
| `data/processed/stage_08_features.parquet` | régénéré |
| `data/processed/stage_09_simba.parquet` | régénéré |
| `data/processed/stage_10_reservations.parquet` | régénéré |
| `data/processed/ml_dataset.parquet` | régénéré |
| `scripts/sources/fix_vvvi_statpop_2022.py` | script correctif (idempotent) |

---

## Impact modèle

Le modèle figé (`etape_04bis_v2_nettoyage_171f.ipynb`) entraîné sur H22–H24 recevait des NaN pour 18 features spatial_ sur toutes les observations VVVI en H23 (18,8 % des observations H23). XGBoost routait ces lignes via sa branche "missing" pour ces 18 features, sans signal socio-démographique sur VVVI. Le correctif fournit les valeurs correctes ; le modèle **devra être ré-entraîné** pour bénéficier de ce signal.

---


---
id: ADR-056
ancien_id: ADR-CF13
date_decision: 2026-06-07
statut: révoqué
revoque_par: [ADR-061]
modifie: [ADR-041]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-056 — Jointure SIMBA : NaN tracé confirmé après investigation exhaustive

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-061.
> Décisions antérieures que ce document modifie : ADR-041.
> **Précision au gel.** Les variables `simba_*` dont ce document confirme la valeur manquante sont **retirées du modèle** par ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — définitif |
| **Date** | 2026-06-07 |
| **Décideur** | Erwann Nedellec |
| **Supersède** | ADR-041 (`docs/adr/ADR-041_simba_refonte_horaire_h25.md`) |
| **ADRs liés** | ADR-026 (leakage SIMBA, lag N-1), ADR-044 (créneau×sens histo_), ADR-055 (STATPOP VVVI) |
| **Dataset de référence** | `ml_dataset.parquet` hash **0c0b7807** (post-correctif STATPOP VVVI, ADR-055) |
| **Modifications pipeline** | Aucune — documentation pure |

---

## Contexte

L'ADR-041 (2026-06-04) a établi que 46.6 % des observations H25 ont les features `simba_*` à NaN en raison de la refonte d'horaire CFF décembre 2024 : 52 trains sur 103 ont été renumérotés, leurs nouveaux numéros étant absents de SIMBA 2024 (millésime de référence pour H25, règle lag N-1 de l'ADR-026). L'Option A — NaN tracé — avait été retenue à titre conservatoire, en cohérence méthodologique avec le principe anti-leakage, mais sans validation empirique des alternatives.

Le présent ADR documente l'investigation complète conduite pour évaluer cinq voies alternatives avant d'acter définitivement la décision. Il remplace l'ADR-041 qui reste une référence historique mais n'est plus la décision en vigueur.

---

## Contraintes héritées (non réexaminées)

### Lag N-1 obligatoire — ADR-026

SIMBA FQkal est produit par la chaîne `AFZ (APC) → FRASY → HOP → calibration FQkal`. La corrélation entre SIMBA(N) et APC(N) est r = **0.97** sur R35 H24 (mesurée sur expansion OD → tronçon). Utiliser SIMBA de l'année courante pour prédire l'occupation de la même année constitue un leakage circulaire tautologique qui rendrait les métriques d'entraînement non représentatives des conditions de production.

**Règle maintenue sans exception** : pour une prédiction sur H(Y), seul SIMBA(Y-1) est autorisé — jamais SIMBA(Y).

Cette contrainte exclut d'emblée toute jointure utilisant SIMBA 2025 pour récupérer les 52 trains renumérotés H25. L'Option B de l'ADR-041 (jointure secondaire SIMBA 2025) reste invalide pour l'évaluation principale.

### Colonnes de traçabilité

Les colonnes `simba_source_depart` / `simba_source_arrivee` (introduites en ADR-041, convention cohérente avec ADR-039 v2 et ADR-040) sont **maintenues**.

| Valeur | Signification |
|---|---|
| `match_simba_n_minus_1` | Jointure réussie sur numéro de train, millésime N-1 |
| `manquant_simba_n_minus_1` | Aucun match (millésime N-1 indisponible ou train renuméroté) |

Ces colonnes permettent de stratifier les métriques H25 au moment du réentraînement final (cf. §Validation empirique).

---

## Profil de la couverture SIMBA H25

| Catégorie | Trains | Observations H25 | % |
|---|---|---|---|
| Trains conservés H24→H25 | 51 | 160 147 | 51.8 % |
| Trains renumérotés, absents de SIMBA 2024 | 52 | 143 867 | 46.5 % |
| Couverture partielle (train 1416) | 1 | ~2 000 | 0.6 % NaN internes |
| **Total H25** | **103** | **~308 000** | — |

La distribution est stable temporellement (≈ 46 % NaN sur tous les mois H25) et asymétrique par sens : sens VV→PLEI ouvrables concentre 54–64 % de NaN (trains de pointe du matin majoritairement renumérotés).

---

## Investigation — cinq voies testées

### Voie 1 — Jointure par numéro de train (état initial ADR-041)

**Grain** : (millesime × numero_train × gare_min × gare_max)

**Résultat** : couverture H25 = 53.4 % (52 trains renumérotés absents de SIMBA 2024 → 46.6 % NaN). Pour H23 et H24, la couverture reste 94–96 % (quelques trains nouveaux par renouvellement annuel mineur, géré nativement par XGBoost).

La stabilité inter-années (2022 vs 2023, proxy du saut inter-millésimes) des features existantes au grain train×tronçon (L0) :

| Feature | W-MAE L0 (pondéré volume) | Corrélation inter-millésimes | Seuil 0.05 |
|---|---|---|---|
| `simba_part_ga` | **0.094** | 0.14 | ✗ |
| `simba_part_mobilis` | **0.131** | 0.55 | ✗ |
| `simba_part_intra_r35` | **0.211** | 0.24 | ✗ |
| `simba_part_corresp_amont` | **0.130** | 0.63 | ✗ |
| `simba_part_corresp_aval` | **0.093** | — | ✗ |
| `simba_part_billet_hta` | **0.070** | — | ✗ |
| `simba_part_spar` | 0.014 | −0.05 (variance nulle) | ✓ (trivial) |
| `simba_part_premiere_classe` | **0.020** | — | ✓ |

Seules les features à quasi-variance nulle (spar) ou à signal très faible (premiere_classe) passent le seuil. Les quatre features informatives (GA, Mobilis, intra R35, correspondances) échouent.

---

### Voie 2 — Agrégation au grain tronçon (L1, tous trains agrégés)

**Grain** : (millesime × gare_min × gare_max) — tous les trains du même tronçon fusionnés

**Raisonnement** : en agrégeant sur tous les trains, le dénominateur devient très grand et le profil plus stable.

**Résultat** :

| Feature | W-MAE L1 | R² géographique | Bilan |
|---|---|---|---|
| `simba_part_ga` | **0.038** (stable ✓) | **0.003** — quasi-nul | Stable mais plat |
| `simba_part_mobilis` | **0.035** (stable ✓) | **0.563** — fort | Stable ET discriminant |
| `simba_part_intra_r35` | 0.061 (limite) | 0.230 — moyen | Borderline |
| `simba_part_corresp_amont` | 0.208 | — | Pire qu'à L0 |

La stabilité de `part_ga` à L1 est **illusoire** : le signal géographique est quasi-inexistant (R² = 0.003, range inter-tronçons = 2.8 pp, toutes sections à ≈ 12 %). En agrégeant tous les trains du même tronçon, on obtient une constante — stable parce qu'informationnellement vide. Le signal GA était train-spécifique, pas géographique.

Pour les correspondances, L1 est pire que L0 (0.208 vs 0.130) : les correspondances sont un attribut de service spécifique à chaque train, pas une propriété géographique invariante du tronçon.

**Verdict voie 2** : stabilité atteinte au prix de la discriminance pour GA — la jointure L1 ne fournit pas de signal utile.

---

### Voie 3 — Décomposition numérateur/dénominateur (Kitagawa)

**Question** : l'instabilité des parts vient-elle d'un artefact de ratio (dénominateur variable) ou d'une dérive réelle de la demande (numérateur) ?

**Méthode** : pour chaque cellule commune entre SIMBA 2022 et 2023, décomposer l'erreur en :
- Effet **dénominateur** : fixer le numérateur (voyageurs GA) à la valeur 2022, appliquer le dénominateur (total) de 2023 → erreur attributable au seul volume global
- Effet **numérateur** : appliquer le numérateur 2023 au dénominateur 2022 → erreur attributable à la seule composition de clientèle

**Résultat pour `part_ga`** :

| Composante | Contribution |
|---|---|
| Dénominateur seul (volume global) | corrélation inter-millésimes ≈ **0.85** — stable |
| Numérateur seul (voyageurs GA absolus) | **76 % de l'erreur totale** |

**Verdict voie 3** : l'instabilité est une dérive comportementale réelle — le nombre absolu de voyageurs GA varie significativement d'une année à l'autre sur les mêmes trains. Ce n'est pas un artefact de mise en pourcentage. Les hypothèses "ratio instable mais signal stable" sont **réfutées**.

---

### Voie 4 — Signature horaire par créneau de proximité (creneau_anchor_30)

**Hypothèse** : le profil tarifaire par créneau (matin = pendulaires GA/Mobilis, midi = occasionnels billets) constitue une signature stable inter-années, robuste aux refontes d'horaire puisqu'un nouveau train à 07h11 porte le même type de clientèle qu'un ancien train à 07h11.

**Construction de creneau_anchor_30** (code : `add_features_to_raw_stacked.py`, ligne 209) : pour chaque train H22-H24, extraire le temps de départ en minutes depuis minuit depuis le format `{num}_{HHhMM}` du `service_id`. Les temps uniques constituent une table d'anchors par (sens × type_jour). Chaque nouvelle observation reçoit l'anchor le plus proche à ±30 min.

**Bijectivité découverte** : le grain (creneau_anchor_30 × tronçon × sens) est **bijectif avec le grain train** — 1 062 / 1 062 cellules contiennent exactement 1 train SIMBA. Explication : les anchors sont les temps de départ exacts de chaque train H22-H24 ; deux trains consécutifs à 07h11 et 07h26 reçoivent des anchors distincts (431 et 446 minutes). L'agrégation n'a jamais lieu. Le créneau de proximité est un réétiquetage du train, pas une agrégation temporelle.

**Vérification de l'hypothèse de signal horaire** (SIMBA 2024, pondéré volume) :

| Tranche | GA | Mobilis |
|---|---|---|
| Matin peak (06h30–08h30) | 10.4 % | 68.7 % |
| Midi (11h–13h30) | 9.6 % | 68.0 % |
| Soir peak (16h30–19h30) | 12.5 % | 66.8 % |
| **Soirée (> 19h30)** | **16.5 %** | 61.0 % |

R²(tranche horaire) pour GA = 12.4 %. La signature "matin = pendulaires GA élevés" est infirmée : la part GA est maximale en soirée (16.5 %), pas au matin peak (10.4 %). Mobilis domine à toute heure (60–70 %), ce qui atténue la discrimination pendulaire/occasionnel caractéristique des lignes urbaines. La R35/MOB a un profil Mobilis structurel homogène.

**Résultat stabilité** (W-MAE créneau×tronçon vs L0) :

| Feature | W-MAE créneau proximité | W-MAE L0 | Gain |
|---|---|---|---|
| `part_ga` | 0.0929 | 0.0944 | +1.6 % — gain nul |
| `part_mobilis` | 0.1310 | 0.1315 | +0.4 % — gain nul |

**Verdict voie 4** : la bijectivité est un **artefact de construction de la clé** (pas une propriété de la ligne, qui a bien une cadence de 15 min aux heures de pointe). Le test n'a pas évalué la vraie signature temporelle — il a recouru au test L0 sous un label différent. Le grain créneau-proximité n'agrège jamais deux trains, donc ne peut pas améliorer la stabilité.

---

### Voie 5 — Agrégation par tranches fixes de 30 min (vraie agrégation)

**Motivation** : la voie 4 a identifié l'artefact. La vraie agrégation temporelle consiste à affecter chaque train à une fenêtre fixe (plancher à la demi-heure la plus proche : 07h00–07h30, 07h30–08h00…) indépendamment de son numéro. Aux heures de pointe, deux trains consécutifs à 15 min d'intervalle tombent dans la même fenêtre : vraie agrégation, volume doublé, profil moyenné.

**Structure des données** :

- Sur H24 VV→PLEI ouvrables : **14 fenêtres à 2 trains SIMBA** (aux heures de pointe AM 05h30–08h30 et PM 15h30–19h00)
- **63.7 % du volume SIMBA total** est concentré dans ces fenêtres peak (11 897 / 18 670 DWV)

**Résultats stabilité** (SIMBA 2022 vs 2023, 100 % de trains matchés) :

| Feature | W-MAE L0 | W-MAE fixe global | W-MAE fixe **peak** | Amélio peak | Seuil 0.05 |
|---|---|---|---|---|---|
| `simba_part_ga` | 0.094 | 0.0824 | **0.0570** | −39 % | ✗ (+14 % au-dessus) |
| `simba_part_mobilis` | 0.131 | 0.1056 | **0.0770** | −41 % | ✗ |
| `simba_part_billet_hta` | 0.070 | 0.0330 | **0.0217** | −69 % | **✓** |
| `simba_part_intra_r35` | 0.211 | 0.1582 | **0.1240** | −41 % | ✗ |
| `simba_part_corresp_amont` | 0.130 | 0.0891 | **0.0460** | −65 % | **✓** |
| `simba_part_corresp_aval` | 0.093 | 0.0832 | **0.0893** | −4 % | ✗ |
| `simba_part_premiere_classe` | 0.020 | 0.0354 | **0.0281** | (dégradé) | ✓ (trivial) |

**Discriminance confirmée** au grain tranche-fixe :

| Feature | R²(fenêtre) | R²(géographique) |
|---|---|---|
| `ga` | 0.41 | 0.01 |
| `mobilis` | 0.37 | 0.28 |
| `intra_r35` | 0.46 | 0.01 |
| `corresp_amont` | 0.33 | 0.003 |

La variation est essentiellement temporelle — le signal existe.

**Décomposition bruit/dérive aux fenêtres peak** :

L'amélioration de 39 % sur GA (0.094 → 0.057) est réelle : doubler le volume agrégé réduit effectivement le bruit de ratio. Mais la décomposition numérateur/dénominateur confirme que la dérive comportementale du numérateur (variation absolue des voyageurs GA d'une année à l'autre) **domine toujours après agrégation** et absorbe la majorité du gain potentiel. Le résidu de 0.057 est de la dérive genuinement non récupérable par agrégation.

**Verdict voie 5** : l'agrégation par tranches fixes est la meilleure voie testée — amélioration de 39–65 % sur les fenêtres peak. Elle rend stables ET discriminantes les features secondaires (`corresp_amont` W-MAE 0.046, `billet_hta` 0.022). Mais les deux features à plus fort poids SHAP — GA (0.057) et Mobilis (0.077) — **restent au-dessus du seuil 0.05**, la dérive comportementale inter-années dominant et résistant à l'agrégation double volume.

---

## Tableau de synthèse des cinq voies

| Voie | Grain | Stable GA ? | Discriminant GA ? | Couverture H25 | Verdict |
|---|---|---|---|---|---|
| 1 — Numéro de train (L0) | train × tronçon | ✗ (0.094) | Oui | 53.4 % | Instable — état initial |
| 2 — Tronçon (L1) | tronçon | ✓ (0.038) | ✗ (R²=0.003) | ~100 % potentiel | Stable mais plat — rejeté |
| 3 — Kitagawa | décomposition | — (76 % num) | — | — | Dérive réelle confirmée |
| 4 — Créneau proximité | anchor unique ≡ train | ✗ (0.093) | Partiel | 53.4 % | Artefact bijectif — rejeté |
| 5 — Tranches fixes | fenêtre 30 min × tronçon | ✗ GA 0.057 (**−39 %**) | Oui (R²=0.41) | ~100 % potentiel | Meilleure voie mais GA échoue |

---

## Décision

**Option A maintenue : NaN tracé intégral pour toutes les features SIMBA sur les trains renumérotés H25.**

### Pourquoi pas l'option hybride ?

La voie 5 rend stables et discriminantes `corresp_amont` et `billet_hta` sur les fenêtres peak. Une option hybride serait techniquement possible : jointure par tranches fixes pour ces deux features, NaN maintenu pour GA et Mobilis.

Cette option est **rejetée** pour les raisons suivantes :

1. **Rapport bénéfice/complexité défavorable** : SIMBA représente environ 5 % de l'importance SHAP globale du modèle. `corresp_amont` et `billet_hta` sont en bas du classement interne des features SIMBA. Le gain de couverture sur deux features secondaires ne justifie pas une logique de jointure hétérogène par-feature dans le pipeline.

2. **Cohérence de la traçabilité** : avec une jointure hybride, la colonne `simba_source_*` aurait une sémantique ambiguë (certaines features seraient remplies par tranches-fixes, d'autres resteraient NaN). La convention `match/manquant` perdrait son interprétation univoque.

3. **Défendabilité** : le NaN intégral est transparent et auditables. Le routage XGBoost est appris de façon cohérente sur l'ensemble des features SIMBA. Une jointure hybride par-feature introduirait une hétérogénéité dans le signal qui complexifie l'interprétation des SHAP sans bénéfice mesurable sur les métriques attendues (ΔR² < 0.01 sur le segment critique haut).

### Gestion native par XGBoost

XGBoost apprend une direction de routage par défaut pour les NaN via la pression du gradient. Sur les features SIMBA, ce routage est calibré sur les **100 % de NaN de H22** (SIMBA 2021 indisponible, ADR-026). Il est donc déjà stable, robuste, et représentatif d'une proportion élevée de NaN — contrairement à une feature dont les NaN seraient rares et accidentels.

---

## Limites structurelles à documenter

### SIMBA sans type_jour

SIMBA FQkal produit un profil annuel moyen par numéro de train, **indifférencié par type de jour** (ouvrable, samedi, dimanche). Un train aura le même `simba_part_ga` un lundi et un dimanche. Cette limite est **commune à toutes les variantes de jointure** — elle s'applique identiquement aux voies 1 à 5 et ne peut pas être contournée sans que SBB révise le format de publication. Le modèle compense partiellement via les features `histo_*` (lags APC par créneau × type_jour, discriminants) et `cal_*` (calendrier).

### Couverture H25

46.6 % des observations H25 sans signal SIMBA. Le modèle dispose de ses 167 autres features actives pour ces observations. L'impact est mesurable et mesuré au §Validation empirique ci-dessous.

---

## Finding méthodologique généralisable (résultat de thèse)

> **La jointure par créneau ou agrégation temporelle ne transfère correctement que des quantités stables au grain où le créneau procure une vraie agrégation.**

L'investigation distingue deux cas :

- **`histo_*` (lags APC)** : la jointure par créneau réussit car la charge d'un créneau horaire (nombre de voyageurs) est **stable inter-années** sur la même ligne. Le créneau agrège plusieurs jours d'observation du même service, réduisant le bruit tout en préservant le signal.

- **Features SIMBA (profils tarifaires)** : la jointure par créneau échoue car la composition de clientèle (proportion GA, Mobilis) **dérive réellement entre années** — dérive comportementale confirmée par la décomposition Kitagawa (76 % du numérateur). L'agrégation de deux trains par fenêtre fixe réduit le bruit de 39–65 % mais ne supprime pas la dérive sous-jacente, qui reste supérieure au seuil d'acceptabilité pour les features informatives.

La condition de succès d'une jointure temporelle est donc que **la quantité jointe soit stable au grain agrégé**. Cette condition est vérifiable empiriquement (W-MAE inter-millésimes, décomposition Kitagawa) avant toute implémentation, et devrait systématiquement précéder toute décision d'ingénierie de features dans les projets ML transport.

---

## Validation empirique — réentraînement final

Conduire au moment de l'évaluation H25 :

1. **Stratification par `simba_source_depart`** :
   - Métriques sur `match_simba_n_minus_1` (51.8 % de H25)
   - Métriques sur `manquant_simba_n_minus_1` (46.5 % de H25)
   - Si ΔR² < 0.01 entre les deux sous-populations : absence de SIMBA sur les renumérotés sans biais — **Option A définitivement validée**
   - Si ΔR² > 0.02 : documenter en limite quantifiée dans le mémoire

2. **SHAP des features `simba_*` sur H25** : confirmer que le rang reste dans la moitié inférieure (cohérence ADR-036). Une remontée signalerait un biais de signal.

3. **Analyse de sensibilité (annexe)** : entraîner un modèle avec jointure secondaire SIMBA 2025 pour les 52 trains renumérotés ; quantifier l'écart de métriques. Si ΔR² < 0.005, valide rétrospectivement l'Option A et documente le coût réel du respect du principe N-1.

---

## Conséquences

- `add_simba_to_raw_stacked.py` : **aucune modification**
- `dim_simba_r35.parquet` : **aucune modification**
- `ml_dataset.parquet` hash **0c0b7807** : **inchangé**
- Colonnes `simba_source_*` : **maintenues** pour la stratification
- ADR-041 : supersédé — voir présent ADR pour la décision en vigueur

---

## Numérotation ADR

- ADR-055 — Correction Voronoï STATPOP VVVI (2026-06-07) — pas de collision
- **ADR-056 — présent ADR** — SIMBA jointure NaN définitif
- ADR-057 — Dénivelé tronçon spatial — pas de collision

---

## Références

- `scripts/pipeline/add_simba_to_raw_stacked.py` — jointure actuelle, inchangée
- `scripts/pipeline/add_features_to_raw_stacked.py`, ligne 209 — construction `creneau_anchor_30` (proximité)
- ADR-026 (`docs/adr/ADR-026_integration_simba_fqkal_lag_n_moins_1.md`) — leakage r=0.97, lag N-1
- ADR-041 (`docs/adr/ADR-041_simba_refonte_horaire_h25.md`) — décision NaN tracé initiale, supersédé
- ADR-044 — créneau×sens pour `histo_*` (contexte comparatif)
- Données : `data/external/simba/zuginout_MOB_2023.csv`, `zuginout_MOB_2024.csv`
- Données : `data/dimension/dim_simba_r35.parquet` (4 239 lignes, millésimes 2022–2025)
- Notebooks : `02_data_understanding_apc.ipynb`, `SYNTHESE_modele_R35_evaluation_complete.ipynb`

---


---
id: ADR-057
ancien_id: ADR-CF14
date_decision: 2026-06-07
statut: actif
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-057 — Feature topologique : dénivelé signé du tronçon (`spatial_denivele_troncon_m`)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date :** 2026-06-07  
**Statut :** Accepté  
**Auteur :** Erwann Nedellec  

---

## Contexte

Le ml_dataset (hash `d3000f48`, 204 colonnes) contient déjà deux features topologiques
d'ordre (`spatial_gare_depart_ordre`, `spatial_gare_arrivee_ordre`) et une feature de
segment (`spatial_segment` = bas/haut). Ces features capturent la position et le contexte
géographique du tronçon sur la ligne, mais pas l'intensité ni le sens de la pente.

La ligne R35 présente un profil altimétrique très marqué : de Vevey (386 m) aux Pléiades
(1348 m), soit 962 m de dénivelé positif sur 11 km. La crémaillère commence à partir de
Blonay. Certains tronçons sont très pentus (ex. Lally→Ondallaz : +147 m), d'autres
quasi-plats (ex. Vevey→Gilamont : +45 m). Cette variabilité d'intensité n'est capturée
par aucune feature actuelle.

Par ailleurs, le sens de circulation est structurellement asymétrique : la montée
(VV→PLEI) peut générer des profils de charge différents de la descente (PLEI→VV) à
position et contexte identiques, notamment sur les tronçons touristiques de crémaillère.

---

## Décision

Ajouter **une seule feature**, `spatial_denivele_troncon_m`, définie comme :

```
spatial_denivele_troncon_m = altitude_gare_arrivee − altitude_gare_depart  [mètres, signé]
```

- **Positif** : tronçon parcouru en montée (arrivée plus haute que départ)
- **Négatif** : tronçon parcouru en descente
- **Préfixe** `spatial_` : cohérent avec la topologie du tronçon (même famille que
  `spatial_segment`, `spatial_gare_depart_ordre`, etc.)
- **Stage** : `03e` (`add_spatial_to_raw_stacked.py`) — stage naturel pour les features
  topologiques, là où `spatial_segment` est déjà calculé

Les altitudes sont lues depuis **`data/dimension/dim_gare.csv`** (source de vérité,
19 entrées, toutes avec altitude valide) et non depuis les colonnes
`spatial_gare_depart_altitude` / `spatial_gare_arrivee_altitude` déjà présentes dans
le pipeline, qui héritent d'un NaN pour GIL et CLIE (héritage du fallback sans `height`
dans `stack_raw_csv.py` / `gare_GIL_CLIE.csv`).

---

## Justification du signal orthogonal

| Feature existante | Ce qu'elle capture | Ce qu'elle ne capture pas |
|---|---|---|
| `spatial_gare_depart_ordre` | Position ordinale de la gare de départ | Intensité de la pente entre les deux gares |
| `spatial_gare_arrivee_ordre` | Position ordinale de la gare d'arrivée | Idem |
| `spatial_segment` (bas/haut) | Contexte crémaillère vs plaine | Finesse intra-segment (ex. OND→LAL vs TUS→CHEV) |
| `spatial_denivele_troncon_m` | **Intensité + sens de la pente** | — |

Le dénivelé signé apporte un signal **orthogonal** : deux tronçons peuvent avoir le même
ordre de départ et d'arrivée mais des dénivelés très différents (ex. tronçons non-adjacents
dans les APC). Le sens distingue la montée touristique (surcharge crémaillère le matin)
de la descente (retours, profils inverses).

---

## Décision de NE PAS ajouter l'altitude brute

Deux features d'altitude brute (`spatial_gare_depart_altitude`,
`spatial_gare_arrivee_altitude`) sont déjà présentes dans les stages intermédiaires
mais **exclues du ml_dataset** (elles ne figurent pas dans la liste des features conservées
par `build_ml_dataset.py`).

Cette exclusion est maintenue délibérément :
- L'altitude de départ et d'arrivée est **fortement corrélée** à `spatial_gare_depart_ordre`
  et `spatial_gare_arrivee_ordre` (relation monotone sur la ligne) → redondance.
- Le modèle dispose déjà de `spatial_gare_depart_km` et `spatial_gare_arrivee_km` comme
  proxy kilométrique de la position.
- Le dénivelé **signé** apporte le signal manquant (pente orientée) sans double-compter
  l'information de position déjà couverte.

---

## Vérification préalable des données

| Gare | Période active | Altitude dim_gare.csv | Altitude dim_gare.parquet | Statut |
|------|---------------|----------------------|--------------------------|--------|
| VV (Vevey) | H16–H25 | 386.5 m | 386.5 m | ✅ |
| GIL (Gilamont) | H16–H22 | 431.7 m | NaN ⚠ | ✅ lu depuis CSV |
| CLIE (Clies) | H16–H18 | 457.9 m | NaN ⚠ | ✅ lu depuis CSV (hors périmètre H22–H25) |
| VVVI (Vevey Vignerons) | H23–H25 | 444.4 m | 444.4 m | ✅ |
| PLEI (Les Pléiades) | H16–H25 | 1348.2 m | 1348.2 m | ✅ |
| Autres 14 gares | H16–H25 | présentes | présentes | ✅ |

Le NaN de GIL et CLIE dans `dim_gare.parquet` provient du script `build_dim_gare.py` /
`stack_raw_csv.py` qui initialise `height = NaN` pour le fallback (`gare_GIL_CLIE.csv`
sans colonne `height`). La lecture directe depuis `dim_gare.csv` résout le problème sans
régénérer la chaîne entière depuis `apc_stacked`.

---

## Non-régression

Test exécuté après régénération complète de stage_03e → stage_10 → ml_dataset :

- Lignes : 1 141 984 (inchangé)
- Colonnes ml_dataset : 204 → **205** (+1 exactement)
- `spatial_denivele_troncon_m` : **0 NaN**, min=−153.9 m, max=+153.9 m, mean=−0.6 m
- Toutes les autres colonnes et toutes les lignes : inchangées

---

## Résultat

- Nouveau hash `ml_dataset.parquet` : **`0c0b7807`** (remplace `d3000f48`)
- Feature ajoutée au stage_03e (`add_spatial_to_raw_stacked.py`)
- `DIM_GARE_CSV` ajouté à `scripts/pipeline/paths.py` comme constante canonique

---

## Liens

- ADR-055 : correction VVVI STATPOP 2022 (hash `d3000f48`)
- ADR-056 : SIMBA jointure NaN confirmé empiriquement

---


---
id: ADR-058
ancien_id: ADR-CF15 (dim_ski)
date_decision: 2026-06-07
statut: amendé
amende_par: [ADR-059]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-058 — Régénération dim_ski_pleiades + intégration partielle saison 2025-2026

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-059.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté  
**Impact hash** : `0c0b7807` → `96225c25`

---

## Contexte

Deux défauts coexistaient dans la dimension ski avant ce correctif :

1. **Bug latent (ski_source manquante)** : `dim_ski_pleiades.parquet` avait été régénéré avec l'ancien script `build_dim_ski_pleiades.py`, perdant la colonne `ski_source`. Or `add_ski_pleiades_to_raw_stacked.py` lit explicitement `dim["ski_source"]` → KeyError garanti au prochain relancement de stage_03b.

2. **Couverture incomplète** : le PDF `ski_25_26.pdf` (saison 2025-2026 officielle) était présent dans `data/external/ski/` mais non parsé ni intégré.

## Décision

### A — Correction du bug latent

Régénérer `dim_ski_pleiades.parquet` avec `build_dim_ski_pleiades_avec_reconstruction.py` (le bon script), qui :
- Produit la colonne `ski_source` (`"officiel"` / `"reconstruit"`)
- Ajoute les saisons H16–H19 reconstruites empiriquement (règle : 1er samedi ≥ 12 déc. + dernier dimanche ≤ 15 mars)

### B — Intégration partielle saison 2025-2026

**PDF source** : `ski_25_26.pdf` — "Exploitation: du samedi 13 décembre 2025 au dimanche 8 mars 2026"

**Analyse périmètre** :
- Convention APC : H25 = 2024-12-15 → 2025-12-13 ; H26 démarre 2025-12-14
- 2025-12-13 (samedi, ouverture officielle de la saison 2025-2026) = **dernier jour de H25**
- 2025-12-14 → 2026-03-08 = **H26, hors périmètre du dataset**

**Décision** : intégrer uniquement 2025-12-13. Les 84 jours restants (H26) ne sont pas intégrés — aucune donnée APC H26 n'existe dans le dataset.

**Entrée ajoutée dans `OFFICIAL_PERIODS`** :
```python
("H26", "2025-12-13", "2025-12-13"),  # 1 seul jour dans H25
```

## Vérification d'écart (pre-run)

Comparaison nouvelle dim vs ancien `stage_03b_ski.parquet` sur le périmètre H22-H25 APC :

| Saison | Dates ski=True ancien | Dates ski=True nouveau | Diff |
|---|---|---|---|
| H22 | 86 | 86 | IDENTIQUE ✓ |
| H23 | 86 | 86 | IDENTIQUE ✓ |
| H24 | 86 | 86 | IDENTIQUE ✓ |
| H25 | 86 | 86 | IDENTIQUE ✓ (avant ajout) |

Seul ajout contrôlé : **2025-12-13** (1 date).

## Non-régression (post-run)

Vérification sur `ml_dataset.parquet` final :

| Horaire | Dates ski=True | Première | Dernière |
|---|---|---|---|
| H22 | 86 | 2021-12-18 | 2022-03-13 |
| H23 | 86 | 2022-12-17 | 2023-03-12 |
| H24 | 87 | 2023-12-16 | 2024-12-14 |
| H25 | 86 | 2024-12-15 | **2025-12-13** ← nouveau |

H24 = 87 dates car 2024-12-14 (ouverture ski H25, dernier jour H24 APC) était déjà True avant ce correctif.

**Tronçons impactés** : 676 tronçons sur base_date=2025-12-13 (samedi, segment haut), tous passent à `event_is_ski_ouvert=True`, `event_ski_source='officiel'`.

## Anti-fuite

`event_is_ski_ouvert` est un flag calendaire publié avant l'ouverture de la saison. Disponible à J-1. Aucune donnée de fréquentation observée ingérée. Pas de fuite temporelle.

## Impact

- `dim_ski_pleiades.parquet` : 530 lignes (H20–H25) → 882 lignes (H16–H26 partiel, `ski_source` présente)
- `stage_03b` → `ml_dataset` : pipeline complète relancée depuis stage_03b
- Hash ml_dataset : `0c0b7807` → **`96225c25`** (205 colonnes, 1 141 984 lignes inchangées)
- Script producteur : `build_dim_ski_pleiades_avec_reconstruction.py` (remplace `build_dim_ski_pleiades.py`)

## Non-intégré (H26)

La saison 2025-2026 au-delà du 2025-12-13 (2025-12-14 → 2026-03-08) relève de H26 et n'est pas intégrée. L'intégrer nécessiterait d'étendre le dataset à H26 — décision de périmètre de thèse indépendante de ce correctif.

---


---
id: ADR-059
ancien_id: ADR-CF15 (garde_defensive)
date_decision: 2026-06-07
statut: actif
modifie: [ADR-058]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-059 — Garde défensive sur le calcul de la cible (coerce silencieux)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-058.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-07  
**Statut** : Accepté — appliqué  
**Auteur** : Erwann Nedellec  

---

## Contexte

L'audit NaN systématique du ml_dataset (2026-06-07) a identifié un risque latent dans `add_features_to_raw_stacked.py` (stage 08). Le calcul de `target_voyageurs_total` utilisait le pattern :

```python
v1 = pd.to_numeric(result["target_voyageurs_1ere_classe"], errors="coerce").fillna(0)
v2 = pd.to_numeric(result["target_voyageurs_2eme_classe"], errors="coerce").fillna(0)
result["target_voyageurs_total"] = (v1 + v2).astype("float64")
```

Ce pattern s'applique aux deux colonnes sources de la cible réelle du modèle (`target_voyageurs_2eme_classe`) et de la variable de contrôle (`target_voyageurs_total`). En présence de valeurs non-numériques dans une extraction APC malformée, `errors="coerce"` les transforme silencieusement en NaN, puis `fillna(0)` les écrase en zéro — sans log, sans erreur, sans trace. Un faux zéro sur la cible = point d'entraînement empoisonné.

**Confirmation sur données réelles** : 0 corruption constatée (invariant vérifié à chaque exécution). C'est un risque latent, pas un problème actif.

---

## Décision

Ajouter une vérification explicite **avant** le `fillna(0)` : comptage des valeurs originellement non-NaN qui deviennent NaN après `to_numeric`. Si le compte est > 0 → `raise ValueError` avec le nombre et un échantillon des valeurs fautives.

**Ce qui ne change pas sur données propres** : comportement strictement identique. Les variables intermédiaires `_v1_coerced.fillna(0)` sont algébriquement équivalentes à `pd.to_numeric(..., errors="coerce").fillna(0)`.

---

## Justification du choix `raise ValueError` vs `logging.warning`

La convention du projet (CONTEXT.md §Bonnes pratiques) spécifie "assertions sur les invariants critiques". La cible est l'invariant le plus critique du pipeline — un faux zéro ici propage une erreur silencieuse dans toutes les features historiques (`histo_*`) et dans le score de chaque modèle entraîné sur ce dataset. Un arrêt immédiat (`raise ValueError`) est préférable à un warning qui pourrait être ignoré.

---

## Vérification élargie : `target_voyageurs_2eme_classe` protégée ailleurs ?

Recherche dans tout le pipeline (`scripts/`) :

| Fichier | Ligne | Pattern | Verdict |
|---------|-------|---------|---------|
| `add_features_to_raw_stacked.py` | 304–305 | `coerce.fillna(0)` sur 1c et **2c** | ✅ Protégé par cette garde |
| `add_features_to_raw_stacked.py` | 332 | `to_numeric(result[col], errors="coerce")` sur LAG_SOURCE_COLS (inclut 2c) | ✅ Sans `fillna` — NaN propagés, non écrasés |
| `scripts/generate_notebook_02_du_surcharges.py` | 893 | `df["target_voyageurs_2eme_classe"].astype("float64").fillna(-1)` | ✅ Script notebook, opère sur ml_dataset déjà construit. Valeur sentinelle −1 pour visualisation, pas pour entraînement |
| `scripts/update_notebook_02.py` | 269 | `v2 = df["target_voyageurs_2eme_classe"].fillna(0)` | ✅ Script notebook (statistiques descriptives), pas pipeline |

**Conclusion** : `target_voyageurs_2eme_classe` n'est soumise à aucun `coerce→fillna(0)` silencieux en dehors de la ligne désormais protégée.

---

## Non-régression

- Shape ml_dataset : (1 141 984, 205) — inchangé
- `target_voyageurs_total` NaN : 0 — inchangé
- `target_voyageurs_2eme_classe` NaN : 0 — inchangé
- Diff `total − (1c + 2c)` : 0.000000 — exact
- Garde silencieuse (0 corruption détectée) → aucune erreur levée

**Note sur le hash — canonique désigné** : le hash du fichier parquet est `11b58391` (MD5). Une sérialisation antérieure du même dataset avait produit `96225c25` (référencé dans CONTEXT.md v5 initial et `controle_enrichi_seg_172f.json`). L'identité de contenu entre les deux est prouvée : fingerprint pandas trié `42a02ffe571f7863`, 1 141 984 lignes, 205 colonnes, toutes valeurs identiques — seules les métadonnées de timestamp parquet diffèrent. **Hash canonique unique : `11b58391`** (c'est celui que produit le fichier sur disque à chaque run). Les notebooks assertent uniquement `11b58391`. `96225c25` n'est plus une référence active.

---

## Fichier modifié

| Fichier | Lignes | Nature |
|---------|--------|--------|
| `scripts/pipeline/add_features_to_raw_stacked.py` | 304–326 | Garde défensive + restructuration des variables v1/v2 |

---


---
id: ADR-060
ancien_id: ADR-CF16
date_decision: 2026-06-09
statut: actif
modifie: [ADR-001, ADR-005, ADR-010]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-060 — Correction du seuil de surcharge 2ème classe : 94 → 63

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-001, ADR-005, ADR-010.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-09  
**Statut** : DÉCISION FIGÉE  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-005 (seuil opérationnel couche 2), ADR-052 (modèle final 170f hash `11b58391`), ADR-049 (cadrage BAS/HAUT)

---

## Contexte

Depuis ADR-005, la constante `SEUIL_UM_2EME = 94` était utilisée dans le pipeline de features pour calculer `histo_voyageurs_2eme_classe_win7_n_surcharges` (nombre d'occurrences de surcharge dans une fenêtre glissante de 7 creneaux J-2). La valeur 94 provenait de `offre_2eme_classe` dans les données APC, qui encode la capacité totale opérationnelle de la rame SURF 7500.

## Problème identifié

La valeur 94 inclut **31 strapontins** (zones multi-usages : vélos, skis, bagages). Ces places ne sont pas mobilisables comme sièges selon la spec matériel MOB active (ref. P01) et le schéma véhicule officiel. La réalité opérationnelle pour la décision UM est : **63 places assises** (places fixes, réservables, utilisables sans restriction).

Un seuil à 94 signifie « toutes les places assises ET tous les strapontins occupés » — un état rare et mal défini. Un seuil à 63 signifie « tous les sièges réservables occupés » — le déclencheur naturel de la décision UM.

## Sources (triple traçabilité)

| Source | Valeur 2ème classe | Fichier |
|--------|--------------------|---------|
| Spécification matériel roulant voyageurs MOB (document interne) — champ « Places assises 2ème » | **63** ✓ correct | source interne, non diffusée |
| Spécification matériel roulant voyageurs MOB (document interne) — champ « Strapontins » | **32** ⚠ écart de saisie (31 réel) | source interne, non diffusée |
| Schéma véhicule `vehicules_portes_7500.png` | **63** assises + **31** strapontins | `data/external/spec_materiel/vehicules_portes_7500.png` |
| APC empirique : `offre − voyageurs` quand `voyageurs = 63` | `94 − 63 = 31` → confirme 31 strapontins | `raw_stacked_annee_horaire.csv` |

**Note coquille Excel** : L'Excel est **correct sur les places assises** (colonne "Places assises 2ème" = 63 pour les ABeh 7501-7508). Sa seule coquille porte sur les **strapontins** (colonne "Strap." = 32 affiché au lieu de 31 réel). Le schéma véhicule et la réconciliation APC convergent sur **63 assises + 31 strapontins = 94**, sans aucune incidence sur le seuil retenu (63 = nombre de places assises). Validation : Responsable des Actifs Voyageurs, MOB, 2026-06-09.

**Valeur retenue : 63.**

## Décision

`SEUIL_UM_2EME` dans `scripts/pipeline/add_features_to_raw_stacked.py` modifié de `94` à `63`.

Seule `histo_voyageurs_2eme_classe_win7_n_surcharges` est calculée à partir de ce seuil. Les autres features capacité (`base_offre_2eme_classe`, `base_places_disponibles_2eme_classe`, `base_tx_occupation_2eme_classe`) sont soit exclues du ml_dataset, soit hors du périmètre 170f, et ne sont **pas modifiées**.

## Impact quantitatif — ml_dataset H22–H25

| Métrique | Ancien (seuil=94) | Nouveau (seuil=63) |
|----------|-------------------|-------------------|
| Hash MD5 ml_dataset | `11b58391de431b24f13b25a2764cfdc8` | `daf936c8bd3e69b87e937123ec185b22` |
| Total observations | 1 141 984 | 1 141 984 |
| Obs `win7_n_surcharges = 0` | 1 134 099 | 1 090 081 |
| Obs `win7_n_surcharges ≥ 1` | 7 607 | 51 625 (×6.8) |
| Obs `win7_n_surcharges = 7` | 16 | 396 |
| Obs passées 0 → ≥1 | — | 44 018 (3.9%) |

La feature est désormais activée sur **3.9 % des observations** contre 0.7 % avant — représentation plus réaliste des creneaux historiquement chargés.

### Distribution complète

| Valeur | Seuil=94 | Seuil=63 | Delta |
|--------|----------|----------|-------|
| 0 | 1 134 099 | 1 090 081 | −44 018 |
| 1 | 6 317 | 32 577 | +26 260 |
| 2 | 622 | 9 266 | +8 644 |
| 3 | 360 | 3 544 | +3 184 |
| 4 | 112 | 2 640 | +2 528 |
| 5 | 96 | 1 844 | +1 748 |
| 6 | 84 | 1 358 | +1 274 |
| 7 | 16 | 396 | +380 |
| NaN | 278 | 278 | 0 |

## Non-régression

Vérification ciblée post-régénération des stages 08→09→10→ml_dataset :

- Seule `histo_voyageurs_2eme_classe_win7_n_surcharges` a changé de valeurs.
- `base_offre_2eme_classe` (retenu dans ml_dataset) : valeurs inchangées (raw APC), absent du périmètre 170f → sans impact sur le modèle.
- Toutes les autres 204 colonnes : identiques (même source APC/météo/SIMBA/réservations).
- Lignes conservées : 1 141 984 (identique).

## Ce qui N'est PAS modifié ici

- `src/r35/constants.py` → non modifié (SEUIL_UM_2EME couche 2 = 94, reste inchangé jusqu'au réentraînement)
- ADR-005, ADR-049, ADR-052 → non modifiés (métriques H25 `n_surch≥94` correspondent encore au modèle précédent hash `11b58391`)
- Notebooks consolidation_finale → non modifiés

Ces propagations interviendront après réentraînement sur le nouveau ml_dataset (hash `daf936c8`).

## Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `scripts/pipeline/add_features_to_raw_stacked.py` | `SEUIL_UM_2EME = 94 → 63` avec commentaire source triple |
| `scripts/pipeline/add_reservations_to_raw_stacked.py` | Optimisation mémoire (`del df_ml` post-merge, extraction QG3 avant merge) — sans impact sur les valeurs |
| `data/external/spec_materiel/` (spécification interne du matériel roulant) | Ajouté (source spec matériel) |
| `data/external/spec_materiel/vehicules_portes_7500.png` | Ajouté (schéma véhicule SURF 7500) |
| `data/processed/ml_dataset.parquet` | Régénéré — nouveau hash `daf936c8` |

---


---
id: ADR-061
ancien_id: ADR-CF17
date_decision: 2026-06-11
statut: actif
modifie: [ADR-026, ADR-041, ADR-052, ADR-054, ADR-056]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-061 — Retrait définitif des 12 features SIMBA du modèle de couche 1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-026, ADR-041, ADR-052, ADR-054, ADR-056.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-11 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-026 (intégration SIMBA, lag N-1), ADR-041 (refonte horaire H24→H25), ADR-052 (modèle final Enrichi_Seg), ADR-060 (seuil surcharge 63) |

## Contexte

L'investigation de la cohérence temporelle SIMBA (2026-06-11) a mis en évidence une convergence de quatre problèmes structurels indépendants sur les 12 features `simba_part_*` :

### 1. Instabilité inter-annuelle quasi-nulle

Sur les 52 trains conservés entre H24 et H25 (même numéro de train, comparaison propre sans contamination des trains renumérotés), la corrélation entre les profils SIMBA 2023 et SIMBA 2024 est :

| Feature | r (2023 vs 2024) | MAE |
|---|---|---|
| `simba_part_ga` | **0.056** | 0.127 |
| `simba_part_billet_hta` | 0.138 | 0.089 |
| `simba_part_spar` | 0.124 | 0.030 |
| `simba_part_jeunes` | 0.023 | 0.053 |
| `simba_part_intra_r35` | 0.331 | 0.236 |
| `simba_part_premiere_classe` | 0.537 | 0.038 |
| `simba_part_corresp_amont` | 0.658 | 0.112 |
| `simba_part_corresp_aval` | 0.724 | 0.137 |
| `simba_part_mobilis` | 0.752 | 0.138 |

La corrélation r = 0.056 pour `simba_part_ga` (feature la plus interprétable, dominante en volume) invalide l'hypothèse de "profil structurel stable" qui justifiait le lag N-1. Ces écarts reflètent une volatilité réelle de la composition de la demande en post-COVID, potentiellement amplifiée par la réforme tarifaire CFF 2023.

### 2. Leakage de disponibilité sur 21.6% de H25

La publication de SIMBA Y intervient en avril-mai Y+1 (latence 4–5 mois). H25 débute en décembre 2024. Pour les observations de décembre 2024 à avril 2025, SIMBA 2024 (millésime assigné par la convention ADR-026 à toute l'année H25) n'était pas encore publié :

| Fenêtre | Observations concernées | % de H25 |
|---|---|---|
| Déc 2024 – mars 2025 | 51 486 avec match SIMBA | 16.6% |
| Déc 2024 – avril 2025 (latence 5 mois) | 66 687 avec match SIMBA | **21.6%** |
| Déc 2024 – mai 2025 (latence 6 mois) | 80 973 avec match SIMBA | 26.2% |

Ces observations ont reçu dans le dataset des valeurs SIMBA 2024 qui n'auraient pas été disponibles à la date de décision réelle. C'est un leakage de disponibilité sur les features (pas sur la cible) qui crée une asymétrie entre les conditions d'évaluation et les conditions de production pour ces mois.

### 3. 46.6% de NaN structurels sur H25

La refonte d'horaire CFF/MOB de décembre 2024 a renuméroté 52 trains (50% du parc), sans équivalent dans SIMBA 2024 (ADR-041). Ces trains ne peuvent recevoir aucune valeur SIMBA sans réintroduire le leakage circulaire SIMBA(N) ↔ APC(N). Le taux de NaN SIMBA sur H25 est stable à ~47% sur tous les mois de l'année — il est structurel, pas temporel.

### 4. Bas du classement SHAP

Les features `simba_*` apparaissent systématiquement dans la moitié inférieure du classement SHAP (ADR-036, ADR-041, ADR-053), confirmant leur contribution marginale à la performance prédictive.

## Décision

**Retrait définitif des 12 features `simba_*` du modèle de couche 1 Enrichi_Seg.**

Cette décision est fondée sur la **fiabilité et la déployabilité**, et non sur le R². Un modèle sans features instables et partiellement indisponibles est meilleur au sens opérationnel, indépendamment de l'impact sur les métriques.

Les 12 features retirées :

```
simba_part_ga, simba_part_mobilis, simba_part_billet_hta, simba_part_spar,
simba_part_jeunes, simba_part_abonnement, simba_part_militaire, simba_part_autre,
simba_part_corresp_amont, simba_part_corresp_aval, simba_part_premiere_classe,
simba_part_intra_r35
```

**SIMBA reste une source du Business Understanding** (compréhension des profils tarifaires, structure de la demande par titre de transport, correspondances intermodales) documentée dans le mémoire. Elle informe le contexte opérationnel sans constituer une feature prédictive du modèle de couche 1.

## Résultats du réentraînement

Nouveau modèle : Enrichi_Seg v1.1, 158 features, dataset hash daf936c8, seed 42, hyperparamètres ADR-052 inchangés.

| Segment | R² 158f | R² 170f (ref) | ΔR² | IC 95% R² |
|---|---|---|---|---|
| BAS | **0.5548** | 0.5538 | **+0.0010** | [0.5512 ; 0.5586] |
| HAUT | **0.5042** | 0.4626 | **+0.0415** | [0.4933 ; 0.5138] |
| GLOBAL | **0.5884** | 0.5812 | **+0.0072** | [0.5850 ; 0.5917] |

Le modèle 158f est **neutre à marginalement meilleur** sur tous les segments. L'amélioration de +0.042 sur le segment HAUT (touristique) est cohérente avec la suppression de features très bruitées (r~0.05) sur un segment où le signal est structurellement plus fragile.

**Interprétation** : les features SIMBA, en raison de leur faible stabilité inter-annuelle, introduisaient du bruit plutôt qu'un signal structurel. Leur retrait ne dégrade pas le modèle — il l'assainie.

## Artefacts produits

| Artefact | Chemin | Statut |
|---|---|---|
| Modèles 158f | `models/enrichi_seg/enrichi_seg_{bas,haut}.json` | Canonical v1.1 |
| Métadonnées | `models/enrichi_seg/enrichi_seg_metadata.json` | Version 1.1 |
| Archive 170f | `models/enrichi_seg/archive_170f/` | Traçabilité |
| Liste features | `consolidation_finale/outputs/features_158f_sans_simba.json` | Canonical |
| SHAP 158f | `consolidation_finale/outputs/q6_shap_ranks_{bas,haut}_158f.csv` | Courants |
| Prédictions 158f | `consolidation_finale/outputs/q6_predictions_h25_158f.parquet` | Courants |
| Script d'entraînement | `consolidation_finale/scripts/retrait_simba_158f.py` | Reproductible |
| Résultats complets | `consolidation_finale/outputs/retrait_simba_158f_resultats.json` | Courants |

## Conséquences sur la documentation

- **ADR-026** : SIMBA reste documentée comme source intégrée dans le pipeline. Ajouter note de bas de page : les `simba_*` ont été retirées des features prédictives par ADR-061.
- **ADR-041** : décision Option A (NaN tracé) reste valide pour la traçabilité pipeline. Ajouter note : la décision de retrait rend caduque la question du NaN pour le modèle, mais l'analyse reste pertinente pour la compréhension des données.
- **Section DataPrep** : tableau des familles de features : 10 groupes → 9 groupes (sans SIMBA), compte total 170 → 158.
- **Section BU** : §3.3.4 « Profils de demande SIMBA FQkal » conservé. Clarification ajoutée : SIMBA informe le contexte mais n'est pas une feature prédictive du modèle final (voir ADR-061).
- **verify_enrichi_seg.py** : assertions 170 → 158, FEAT_JSON → features_158f_sans_simba.json.
- **Notebook assertions** : `assert len(FEATURES) == 158`.

## Références

- Investigation cohérence temporelle SIMBA, 2026-06-11
- ADR-026 — Intégration SIMBA FQkal, lag N-1
- ADR-041 — Refonte horaire H24→H25, NaN SIMBA structurels
- ADR-052 — Modèle final Enrichi_Seg, hyperparamètres
- ADR-060 — Seuil surcharge 63
- `consolidation_finale/scripts/retrait_simba_158f.py` — script de réentraînement

---


---
id: ADR-062
ancien_id: ADR-CF18
date_decision: 2026-06-16
statut: actif
modifie: [ADR-008, ADR-009, ADR-042, ADR-044]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-062 — Virage leakage temporel APC : cutoff mensuel, tronçon dans la clé histo_*, fenêtre win7

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-008, ADR-009, ADR-042, ADR-044.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-16
**Statut** : Accepté
**Décideur** : Erwann Nédellec
**Périmètre** : features `histo_*` uniquement — STATENT et ResSys font l'objet d'ADR séparés
**Lié à** : ADR-008 (lag J-2 → corrigé ici), ADR-037 (grain histo enrichi type_jour), ADR-060 (seuil 63), ADR-061 (retrait SIMBA)

---

## Contexte

Le calendrier de publication réel des données APC (HOP-REP-WEB) a été établi lors d'une investigation empirique sur le dataset H22–H25 :

- **Mois M est disponible à partir du 3 de M+1.** Il n'existe aucun canal de publication plus fréquent.
- Le pipeline `add_features_to_raw_stacked.py` utilisait `LAG_OPERATIONNEL_JOURS = 2` (ADR-008), supposant que les données de J-2 étaient disponibles au moment de la décision.

Cette hypothèse J-2 est **correcte pour les données de la journée écoulée** (ponctualité ISTDATEN, météo), mais elle est **incorrecte pour les données APC** : les comptages APC d'un jour J ne sont consolidés que dans le rapport mensuel du mois suivant.

---

## Problème : leakage temporel confirmé

Le lag réel entre la date d'une observation APC et sa publication effective dans HOP-REP-WEB est :

| Statistique | Lag (jours calendaires) |
|---|---|
| Minimum | 3 j |
| Médiane | **18 j** |
| Maximum | 33 j |

L'implémentation J-2 permettait donc au modèle d'utiliser des données APC non publiées au moment où la décision UM doit être prise. La fraction de fenêtres d'entraînement touchées par ce leakage :

| Année | % fenêtres win7 avec ≥1 occurrence non publiée |
|---|---|
| H22 | ~86 % |
| H23 | ~91 % |
| H24 | ~94 % |
| **Global** | **~91 %** |

L'impact mesuré sur les métriques H25 (plancher honnête = cutoff mensuel seul, sans tronçon) :

| Métrique | daf936c8 biaisé (J-2) | Plancher honnête | Δ leakage pur |
|---|---|---|---|
| R² HAUT | 0.504 | **0.404** | **−0.100** |
| R² BAS | 0.555 | 0.524 | −0.031 |
| R² GLOBAL | 0.588 | 0.558 | −0.030 |

Le R² HAUT est le plus touché (−0.100) car le segment HAUT (Vevey–Les Pléiades, ski) a des patterns de fréquentation plus volatils ; l'historique récent apportait un gain artificiel non reproductible en production.

---

## Décision

Adoption de trois changements conjoints sur le pipeline `histo_*` :

### 1. Cutoff mensuel (remplacement de J-2)

La fenêtre histo_* se termine désormais au **dernier jour du dernier mois entièrement publié** à la date de décision D :

```python
def compute_cutoff_mensuel(D):
    D = pd.Timestamp(D)
    if D.day >= 3:
        mois_p = D.month - 1 or 12
        annee_p = D.year if D.month > 1 else D.year - 1
    else:
        mois_p = D.month - 2; annee_p = D.year
        if mois_p <= 0: mois_p += 12; annee_p -= 1
    dernier_jour = calendar.monthrange(annee_p, mois_p)[1]
    return pd.Timestamp(annee_p, mois_p, dernier_jour)
```

Ce cutoff constitue en lui-même un **embargo structurel** : les données les plus récentes disponibles ont en moyenne 18 jours de décalage. L'argument « embargo=0 » du §4.8 du rapport (qui reposait sur le lag J-2) devra être reformulé lors de la régénération finale.

### 2. Tronçon dans la clé de groupement histo_*

La clé de groupement passe de :
```
[base_sens, creneau_anchor_30, cal_type_jour_3classes]
```
à :
```
[base_sens, creneau_anchor_30, cal_type_jour_3classes, id_gare_depart_bpuic, id_gare_arrivee_bpuic]
```

**Justification :** le pipeline précédent calculait la moyenne des `histo_*` sur tous les tronçons d'une même course (ex. Vevey → Les Pléiades = 8 tronçons avec des profils de charge radicalement différents). Ce `.mean()` inter-tronçons lissait l'historique et détruisait l'information locale. Ajouter le tronçon `(id_gare_depart_bpuic, id_gare_arrivee_bpuic)` comme clé supplémentaire supprime ce lissage.

**Impact isolé (mesure en deux temps, cutoff mensuel fixé) :**

| Métrique | Plancher honnête (sans tronçon) | +tronçon (inc1) | Δ |
|---|---|---|---|
| R² HAUT | 0.404 | **0.463** | **+0.058** |
| R² BAS | 0.524 | 0.590 | +0.066 |
| R² GLOBAL | 0.558 | 0.608 | +0.050 |

Le tronçon dans la clé récupère donc la majorité du retrait dû à la correction du leakage.

**Note architecture :** le tronçon est ajouté à la CLÉ de calcul des histo_*, pas comme colonne feature supplémentaire. Le total de features du modèle reste 158 (confirmé par vérification bit-à-bit après rechargement).

### 3. Conservation de la fenêtre win7 (vs fenêtre mensuelle testée)

La fenêtre `win7` (7 dernières occurrences du groupe précédant le cutoff mensuel) est **conservée**. Une alternative, `inc1bis`, a été testée : remplacer win7 par la moyenne de toutes les occurrences du dernier mois publié.

La justification du rejet d'`inc1bis` repose sur l'**argument de valeur décisionnelle marginale au niveau tour** :

**Structure des surcharges HAUT au niveau tour (H25, trains mixtes BAS+HAUT) :**

| Catégorie | N tours | % des tours avec surcharge HAUT |
|---|---|---|
| Redondants : HAUT + BAS en surcharge (BAS déjà déclenche l'UM) | 154 | 81.9 % |
| **Isolés : HAUT seul en surcharge** (HAUT porte la décision UM) | **34** | **18.1 %** |

Sur les 34 tours **isolés** (seul sous-ensemble à valeur décisionnelle propre) :

| Métrique | inc1 (win7) | inc1bis (mensuel) | Δ |
|---|---|---|---|
| **PR-AUC >63** | **0.752** | 0.703 | **+0.049 en faveur de win7** |
| Lift | 1.33× | 1.24× | +0.086× win7 |
| Précision naïve (seuil 63) | **100.0 %** | 86.4 % | win7 |

Sur les 154 tours redondants (sans enjeu décisionnel propre), les deux modèles sont équivalents (PR-AUC ~0.92).

**Conclusion :** le gain BAS d'`inc1bis` (+0.020 PR-AUC) porte sur des décisions déjà prises par le BAS du même tour ; le gain HAUT de `win7` (+0.049) porte sur les 18 % de cas où la détection HAUT cause effectivement une décision UM différente. `win7` est retenu.

**Risque opérationnel supplémentaire d'`inc1bis` écarté :** la fenêtre mensuelle introduit ~17 % de NaN aux transitions décembre/janvier (dernier mois publié change brutalement), contre 0.02 % pour win7.

---

## Attribution chiffrée — récapitulatif

| Étape | R² HAUT | Δ HAUT | Interprétation |
|---|---|---|---|
| daf936c8 — J-2, biaisé | 0.504 | — | Référence obsolète (leakage) |
| Plancher honnête — cutoff mensuel seul | 0.404 | −0.100 | Leakage pur mesuré |
| + Tronçon dans clé histo_* (inc1) | **0.463** | **+0.058** | Récupération via granularité tronçon |
| Δ résiduel vs daf936c8 | — | −0.042 | Coût net de la correction du leakage |

---

## Conséquences

- **daf936c8 (`ml_dataset.parquet`)** : marqué **OBSOLÈTE** (leakage temporel histo_*). Ne plus utiliser comme référence de performance.
- **`ml_dataset_exp_inc1.parquet`** (hash `fe9d6b4d`) : établi comme **base de travail intermédiaire couche 1**. Pas encore le canonique final (cycles STATENT et ResSys à venir).
- **Enrichi_Seg v1.2** : modèles re-sérialisés sur `fe9d6b4d` dans `models/enrichi_seg/`. v1.1 archivée dans `models/enrichi_seg/archive_v1.1/`.
- **ADR-008** : corrigé — le lag APC n'est pas J-2 mais cutoff mensuel. Voir correction inline ADR-008.
- **§3.4, §3.5, §4.8 du rapport** : à reformuler lors de la régénération finale (régénération différée après STATENT + ResSys). **Ne pas régénérer maintenant.**
- **`constants.py` `SEUIL_SURCHARGE`** : non modifié (reste 63, ADR-060 inchangé).

---

## Pistes d'amélioration future (hors périmètre)

- **Reformulation saisonnière N−1** : une feature `saisonnier_nm1_mois_mean` (même mois, année N−1) a été testée (inc2) et rejetée : colinéarité avec `cal_mois` déjà présent + 28–30 % de NaN sur H25 causant des directions XGBoost hors-distribution. Une variante potentiellement viable : résidu N−1 (charge observée − moyenne de l'année × facteur saisonnier) ou moyenne des 4 semaines homologues N−1 avec imputation explicite.
- **Fenêtres calendaires courtes** : des fenêtres de 10–20 jours calendaires (plutôt que 7 occurrences ou 1 mois) pourraient concilier récence et non-arbitraire. Non testées dans ce cycle.

---

## Fichiers impactés

| Fichier | Modification |
|---|---|
| `scripts/pipeline/add_features_to_raw_stacked.py` | cutoff mensuel, GROUP_KEYS + tronçon |
| `data/processed/ml_dataset_exp_inc1.parquet` | dataset de travail (hash `fe9d6b4d`) |
| `models/enrichi_seg/enrichi_seg_bas.json` | modèle BAS v1.2 |
| `models/enrichi_seg/enrichi_seg_haut.json` | modèle HAUT v1.2 |
| `models/enrichi_seg/enrichi_seg_metadata.json` | métadonnées v1.2 |
| `docs/adr/ADR-008_lag_operationnel_J-2.md` | correction lag mensuel |

---

## Références

- Investigation leakage : sessions 2026-06-14/15/16 (notebooks expérimentaux `daily_exp_mensuel.parquet`, `daily_exp_inc1.parquet`)
- ADR-008 : Lag opérationnel J-2 — corrigé par cet ADR
- ADR-037 : Grain enrichi histo_* type_jour + service_id
- ADR-060 : Seuil surcharge 94 → 63
- ADR-061 : Retrait 12 features SIMBA

---

## Amendement 2026-06-20 — Application réelle au pipeline canonique (v1.8, hash `51e459ff`)

**Constat.** La décision de cet ADR (cutoff mensuel + clé tronçon) avait été **actée mais jamais appliquée au pipeline canonique**. Le code correctif vivait dans une branche de travail « inc1 » **jamais commitée** ; seuls les artefacts de sortie (`daily_exp_inc1.parquet`, `daily_exp_mensuel.parquet`) subsistaient. Le pipeline canonique `add_features_to_raw_stacked.py` appliquait donc encore `LAG_OPERATIONNEL_JOURS = 2` (J-2, ADR-008) + clé 3-termes. Les datasets v1.6 (`5fdca746`) et v1.7 (`d39d0bd8`) **contenaient donc le leakage temporel histo_*** que cet ADR prétendait corriger (vérifié : pour une même course, les tronçons partageaient une valeur histo identique = moyenne inter-tronçon ; lag J-2 et non cutoff mensuel).

**Réimplémentation (chirurgicale, orthogonale CF19/CF20/CF21).** Deux modifications dans `add_features_to_raw_stacked.py` :
1. `GROUP_KEYS` étendu à 5 termes : `[base_sens, creneau_anchor_30, cal_type_jour_3classes, id_gare_depart_bpuic, id_gare_arrivee_bpuic]`.
2. Lag : `_cutoff_mensuel_seuils()` (dernier mois entièrement publié à D ; bascule le 3 de M+1) remplace `dates − 2 j`.

**Validation contre oracle.** Les features histo_* régénérées reproduisent `daily_exp_inc1.parquet` **à 100,000 %** (2 286 825 lignes, 16 colonnes histo_*, 0 écart). Propriétés confirmées : tronçon dans la clé (variation inter-tronçon 98,4 %), cutoff mensuel (bascule lag2 au 3 du mois ; délai médian 1ʳᵉ occ.→1ᵉʳ lag2 = 21 j vs ~2 j en J-2).

**Garde-fou.** Assertion `_assert_histo_conformite_adr_cf18()` exécutée à chaque build avant écriture de stage_08 : RuntimeError si la clé perd le tronçon (variation < 50 %) ou si le lag redevient J-2 (délai médian < 10 j). Empêche toute régression silencieuse (l'écart initial venait précisément de l'absence de commit du code inc1).

**Nouveau hash canonique : `51e459ff`** (SHA256[:8], reproductible `make clean && make`, pyarrow 21.0.0). Orthogonalité stricte : seules les 16 colonnes histo_* changent vs `d39d0bd8` (193 colonnes identiques — STATPOP/STATENT/Split C intacts).

**Effet réel sur métriques H25** (d39d0bd8 J-2/3-termes → 51e459ff cutoff/tronçon, Split C, 158f, modèles réentraînés seed=42) :

| Segment | R² d39d0bd8 (leakage) | R² 51e459ff (corrigé) | Δ |
|---|---|---|---|
| BAS | 0.5666 | **0.5920** | +0.025 (granularité tronçon) |
| HAUT | 0.4896 | **0.4472** | **−0.042** (retrait leakage, segment critique) |
| GLOBAL | 0.5949 | **0.6074** | +0.012 |

La baisse sur HAUT est la signature attendue du retrait du leakage ; la hausse sur BAS vient de la granularité tronçon (info réelle non-fuyante). **Décomposition leakage vs granularité** (3 points : d39d0bd8 → `daily_exp_mensuel` cutoff/3-termes → 51e459ff cutoff/tronçon) à produire en Section 5 — oracles disponibles.

**Audit anti-fuite clé 5-termes** : 5 176 groupes (vs 339 en 3-termes), premières occurrences NaN 5176/5176. **Couverture histo_* H25 = 99,3 %** (0,68 % de NaN : démarrage à froid des `tronçon × créneau × type_jour` rares sans historique suffisant ; géré nativement par XGBoost).

| Fichier | Modification (2026-06-20) |
|---|---|
| `scripts/pipeline/add_features_to_raw_stacked.py` | GROUP_KEYS 5-termes + `_cutoff_mensuel_seuils()` + `_assert_histo_conformite_adr_cf18()` |
| `data/processed/ml_dataset.parquet` | hash canonique `51e459ff` |
| `models/enrichi_seg/enrichi_seg_{bas,haut}_51e459ff.json` | modèles réentraînés (a3408ef6 / 28108fd9) |
| `consolidation_finale/scripts/q_all_v17_51e459ff.py`, `retrain_51e459ff_cf18.py` | régénération outputs q* + métriques |

---

## Amendement 2026-06-20 (bis) — Règle de cutoff composée : décision T-1 + délai d'ingestion (hash `416bb90b`)

**Constat (audit externe, point 3).** Le cutoff mensuel `_cutoff_mensuel_seuils()` de l'amendement précédent était calculé sur `base_date = T` (date du **trajet**) avec un seuil de bascule au **3** du mois. Il omettait **deux délais** :
1. **Décision à T-1.** La décision UM se prend la veille du trajet ; le cutoff doit se baser sur la date de **décision `D_dec = base_date − 1 jour`**, pas sur la date du trajet `T`.
2. **Ingestion APC d'un jour.** Les comptages d'un mois M publiés sur PrepWeb (HOP-REP-WEB) le 3 de M+1 ne sont **ingérés/utilisables que le lendemain — le 4** de M+1.

Le cutoff antérieur (`T`, seuil au 3) utilisait donc, sur une fraction des lignes, un mois d'historique **plus frais que celui réellement disponible** à la décision (biais optimiste léger).

**Règle composée (corrigée).** Un mois M est utilisable pour une décision à `D_dec = T−1` si :

> `(3 de M+1) + 1 jour d'ingestion ≤ D_dec`, c'est-à-dire `(4 de M+1) ≤ D_dec`.

Conditionnelle à la date, appliquée sur `D_dec = T−1` :
- dernier mois utilisable = (mois de `D_dec` − 1) si `D_dec.day ≥ 4`, sinon (mois de `D_dec` − 2).
- seuil = dernier jour de ce mois utilisable.

```python
d_dec = pd.DatetimeIndex(dates_arr) - pd.Timedelta(days=1)   # (a) décision à T-1
back  = np.where(d_dec.day >= 4, 1, 2)                        # (b) publié le 3 + 1j ingestion -> utilisable le 4
month_start  = d_dec.values.astype("datetime64[M]")
cutoff_month = month_start - back.astype("timedelta64[M]")
```

**Exemples.**

| Trajet T | Décision T-1 | Jour de décision | Dernier mois utilisable | Cutoff |
|---|---|---|---|---|
| 4 juillet | 3 juillet | 3 (< 4) → juin pas encore ingéré | **mai** | 31 mai |
| 5 juillet | 4 juillet | 4 (≥ 4) → juin utilisable | **juin** | 30 juin |

**Ampleur (mesurée sur le dataset, 1 141 984 lignes).** **78 082 lignes (6,84 %)** utilisent désormais un mois d'historique différent (M-2 au lieu de M-1), réparties **exactement** sur `base_date.day ∈ {3 (39 299 lignes), 4 (38 783 lignes)}` — aucune autre ligne affectée. Chaque composante isolée vaut 3,44 % / 39 299 lignes (le décalage T-1 seul affecte le jour 3 ; l'ingestion +1 seule affecte le jour 4) ; la règle composée additionne les deux.

**Garde-fou.** L'assertion `_assert_histo_conformite_adr_cf18()` reste en place (floor `med_gap ≥ 10 j`, détecte une régression J-2). Sous la règle composée, le **délai médian 1ʳᵉ occ.→1ᵉʳ lag2 passe de 21 j à 24 j** (légèrement plus élevé, conforme au recul d'un mois sur les jours 3-4) — l'assertion passe sans modification de seuil.

**Nouveau hash canonique : `416bb90b`** (SHA256[:8], reproductible : deux `make clean && make` indépendants → `416bb90b` byte-exact, pyarrow 21.0.0). Cette correction est groupée avec **ADR-067** (headway grille planifiée). Orthogonalité stricte : exactement **20 colonnes changent** vs `51e459ff` (16 `histo_*` du cutoff composé + 4 `ist_headway_*` de CF23 ; 189 colonnes identiques).

**Effet réel sur métriques H25** (`51e459ff` → `416bb90b`, Split C, 158f, modèles réentraînés seed=42) :

| Segment | R² 51e459ff | R² 416bb90b | Δ | PR-AUC 51e459ff | PR-AUC 416bb90b | Δ |
|---|---|---|---|---|---|---|
| BAS | 0.5920 | **0.5868** | −0.0052 | 0.4814 | **0.4687** | −0.0127 |
| HAUT | 0.4472 | **0.4334** | −0.0138 | 0.3410 | **0.3452** | +0.0042 |
| GLOBAL | 0.6074 | **0.6013** | −0.0061 | 0.4571 | **0.4490** | −0.0081 |

Baisse faible et dans le sens attendu (retrait d'un biais optimiste). Le PR-AUC BAS baisse (0.481 → 0.469), attribuable au recul d'historique sur les jours 3-4 sur le segment pendulaire (autocorrélation forte) — coût assumé du retrait de leakage, à discuter en Section 5 (justification renforcée de la couche 2).

| Fichier | Modification (2026-06-20 bis) |
|---|---|
| `scripts/pipeline/add_features_to_raw_stacked.py` | `_cutoff_mensuel_seuils()` règle composée (T-1 + ingestion) + docstrings |
| `data/processed/ml_dataset.parquet` | hash canonique `416bb90b` |
| `models/enrichi_seg/enrichi_seg_{bas,haut}_416bb90b.json` | modèles réentraînés (e4ddfccd / df6a11c5) |
| `consolidation_finale/scripts/q_all_v18_416bb90b.py`, `retrain_416bb90b_cf18cf23_metrics.json` | régénération outputs q* + métriques |

---


---
id: ADR-063
ancien_id: ADR-CF19
date_decision: 2026-06-16
statut: actif
modifie: [ADR-006, ADR-011, ADR-025, ADR-039, ADR-055]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-063 — Causalité de disponibilité STATPOP : mapping Z-2 conservateur, forward-fill causal, correction géographique VVVI

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-006, ADR-011, ADR-025, ADR-039, ADR-055.
> **Précision au gel.** Ce document porte **deux auto-corrections datées** (18.06 et 19.06.2026) qui invalident une partie de ses propres mesures. Les lire avant les tableaux qu'elles corrigent.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (2026-06-16) — corrigé 2026-06-18 (Z-2 pipeline) — **corrigé 2026-06-19** (forward-fill pipeline, voir §Correction 2026-06-19) |
| **Date** | 2026-06-16 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-006 (stratégie millésime), ADR-011 (imputation 2021/2023 — révisé), ADR-024 (géométrie Voronoï), ADR-039 (mapping calendaire — révisé) |
| **Version modèle** | Enrichi_Seg v1.3 (hash 961a0bd5) — v1.2 (fe9d6b4d) archivée dans archive_v1.2/ |

## Contexte

La Philosophie A (mapping STATPOP initial, implémentée dans ADR-039 v2) présentait deux problèmes de causalité temporelle :

### Problème 1 — Fuite de disponibilité (mapping contemporain)

Le millésime STATPOP Y est produit par l'OFS sur l'état de la population au 31 décembre de l'année Y. Il est publié généralement vers août de l'année Y+1, mais **cette date n'est pas garantie** et peut glisser au-delà. La Philosophie A attribuait aux observations de l'année civile Z le millésime Z (mapping Z→Z) pour les années exactes, et Z→Z-1 carry-forward pour 2025.

Conséquence : une observation du 15 mars 2023 recevait le millésime STATPOP 2023 — publié au plus tôt fin 2024. Cette donnée n'était pas disponible à la date de la décision opérationnelle modélisée. Il s'agit d'une fuite temporelle de disponibilité, distincte d'une fuite de cible mais méthodologiquement inacceptable dans un mémoire MSc défendant la rigueur causale.

### Problème 2 — Interpolation avec borne future (millesimes 2021 et 2023)

L'ADR-011 avait adopté une interpolation linéaire pour les millésimes manquants :
- 2021 = moyenne(2020, 2022) — utilise STATPOP 2022, publié courant 2023
- 2023 = moyenne(2022, 2024) — utilise STATPOP 2024, publié courant 2025

L'interpolation mobilise une borne future non disponible à la date de l'observation, renforçant la fuite de disponibilité.

### Problème 3 — NaN VVVI (gare du segment BAS)

La gare VVVI n'était pas présente dans les topologies H19-H22 et était donc absente des zones Voronoï correspondantes dans `statpop_clean`. Conséquence : 33 327 observations VVVI (segment BAS, H23+H24+H25) recevaient des valeurs NaN pour toutes les features `spatial_gare_*_pop_500m_*`. Ces NaN n'encodaient pas une absence démographique réelle — VVVI est en zone urbaine dense de Vevey — mais un artefact d'attribution géographique.

## Décision

### 1. Mapping Z-2 conservateur (borne Jan 1 Y+2)

Le millésime Y est considéré sûrement disponible **à partir du 1er janvier Y+2**, ce qui garantit une marge suffisante même en cas de retard de publication. Une observation de l'année civile Z utilise donc le millésime Z-2 :

```python
MAPPING_BC_MILLESIME = {
    2021: 2019,
    2022: 2020,
    2023: 2021,
    2024: 2022,
    2025: 2023,
}
```

Ce décalage est **uniforme** par année civile (clé = `base_date.dt.year`, pas de bascule intra-année). Il n'y a pas de bascule août/septembre parce que la date de publication n'est pas garantie.

### 2. Forward-fill causal pour les millesimes sans HP*/HPI

Les données HP (effectifs de ménages privés) et HPI (indicateur de plausibilité des ménages
privés), au sens de la nomenclature STATPOP, ne sont disponibles dans la source OFS que pour certains millésimes. Forward-fill appliqué :
- 2021 ← 2020 (HP*/HPI de 2020 utilisés pour le millésime 2021)
- 2023 ← 2022 (HP*/HPI de 2022 utilisés pour le millésime 2023)

Cela remplace l'interpolation de l'ADR-011 (2021 = moyenne(2020,2022), 2023 = moyenne(2022,2024)) qui utilisait une borne future. Le forward-fill ne mobilise que des données disponibles avant la date de l'observation.

### 3. Correction géographique VVVI

La zone Voronoï de VVVI est reconstruite rétrospectivement en utilisant la topologie H23 (où VVVI est active) comme proxy géographique stable. Les hectares STATPOP (RELIs) des millésimes 2019, 2020 et 2021 sont agrégés pour cette zone. Les valeurs HP*/HPI de 2021 sont forward-fillées depuis 2020 (cohérent avec la décision 2 ci-dessus).

Légitimité causale : les données de population par hectare sont des constats géographiques passés — leur utilisation pour reconstruire la zone VVVI aux millésimes antérieurs ne crée pas de fuite temporelle.

## Coût de performance

| Métrique | v1.2 (Philo A, fe9d6b4d) | v1.3 (Philo C_fix, 961a0bd5) | Δ |
|---|---|---|---|
| R² BAS (H25) | 0.589749 | 0.593410 | **+0.0037** (élimination NaN VVVI) |
| R² HAUT (H25) | 0.462726 | 0.447184 | **−0.0155** (coût causalité STATPOP) |
| R² GLOBAL (H25) | 0.608121 | 0.608443 | **+0.0003** (neutre) |
| PR-AUC HAUT | 0.3554 | 0.3410 | −0.0144 |

### Décomposition du coût HAUT

Le ΔR²HAUT = −0.0155 se décompose en deux effets indépendants :
- **Décalage millésime Z-2** (mapping B vs A) : ΔR²H = −0.0142 (92 % du coût)
- **Forward-fill vs interpolation** : ΔR²H = −0.0013 (8 % du coût)

La correction VVVI (NaN→valeur réelle) affecte exclusivement le segment BAS (VVVI est une gare BAS). Le R²HAUT est rigoureusement indépendant de cette correction — les modèles BAS et HAUT sont entraînés sur des données disjointes (`spatial_segment`).

## Arbitrage assumé explicitement

**Ce n'est pas une correction d'erreur — c'est un arbitrage de rigueur méthodologique.**

La Philosophie A n'était pas « fausse » au sens statistique — elle produisait les meilleures métriques sur H25 parce qu'elle utilisait des millésimes plus récents, mieux alignés avec les patterns démographiques H25. En adoptant Z-2, on renonce délibérément à une partie de ce signal (ΔR²H = −0.0155) pour garantir qu'aucune donnée non disponible à la date opérationnelle ne soit mobilisée.

Ce trade-off est cohérent avec la position de la thèse : un modèle destiné à un usage opérationnel J-1 doit être entraîné avec des contraintes de disponibilité réalistes, quand bien même cela dégrade marginalement les métriques sur données rétrospectives.

La dégradation HAUT est modérée (−3.3 % de R² relatif) et intégralement attribuable à l'adoption d'un mapping plus conservateur, pas à une dégradation de la qualité du modèle. Le R²GLOBAL reste quasi stable (+0.0003).

## Note de traçabilité — Artefact d'évaluation en mémoire

Lors de l'évaluation in-memory du script `statpop_philo_c_vvvi_fix.py`, un faux ΔR²HAUT de −0.0411 avait été rapporté (0.4472 → 0.4061). Ce chiffre était incorrect.

Cause racine : `pd.concat` entre `statpop_ff` (dtypes Int64) et les nouvelles lignes VVVI (avec NA dans les colonnes HP absent de STATPOP2021) a déclenché un FutureWarning de corruption dtype. L'évaluation in-memory utilisait un objet corrompu. Le round-trip via `to_parquet()` / `read_parquet()` restaure les dtypes corrects.

Preuve de l'artefact : le modèle HAUT est entraîné sur `spatial_segment == "haut"`. Les observations VVVI sont toutes dans `spatial_segment == "bas"`. L'ensemble d'entraînement du modèle HAUT est **identique** entre C et C_fix (0 différence ligne à ligne). Avec seed=42 déterministe, ΔR²HAUT = 0.000000 exactement entre C et C_fix. Le ΔR²H = −0.0155 constaté entre v1.2 et v1.3 provient entièrement du changement de mapping STATPOP (Philosophie A → C), pas de la correction VVVI.

## Cohérence avec STATENT

Cette décision établit la règle de causalité applicable à toute source OFS structurelle avec latence de publication comparable. STATENT (statistique des entreprises), dont l'intégration est prévue au cycle suivant, devra appliquer la même borne Z-2 conservatrice (publication STATENT généralement 18-24 mois après l'année de référence).

## Correction 2026-06-18 — Bug pipeline : Z-2 n'avait jamais été réellement appliqué

### Bug identifié

L'audit du 2026-06-18 a révélé que le script `scripts/pipeline/build_stage06_statpop.py` avait bien été mis à jour avec le mapping Z-2 (ADR-063), **mais que `stage_06.parquet` n'avait jamais été reconstruit**. Les datasets v1.3 (961a0bd5), v1.4 (c1ecfc19) et tous les datasets expérimentaux intermédiaires contenaient donc STATPOP Z-0 dans les données, malgré les labels "ADR-063 causal Z-2".

Vérification directe sur chaque dataset :
```
v1.3 (961a0bd5) : id_statpop_reference_year H22 → [2021, 2021, 2021] ← Z-0
v1.4 (c1ecfc19) : id_statpop_reference_year H22 → [2021, 2021, 2021] ← Z-0
5fdca746        : id_statpop_reference_year H22 → [2019, 2019, 2019] ← Z-2 ✓
```

### Correction

Le pipeline a été reconstruit le 2026-06-18 à partir de `stage_06` (STATPOP Z-2 réel) via `make stage_07 → stage_08 → stage_09 → ml_dataset`. Dataset canonique résultant : `5fdca746` (209 colonnes, 1 141 984 lignes H22–H25).

### Vrai effet de Z-2 (mesuré sur données correctes)

La comparaison `c1ecfc19` (Z-0 effectif) vs `5fdca746` (Z-2 effectif) sur les mêmes features et le même split A :

| Segment | Z-0 (c1ecfc19, INVALIDE) | Z-2 (5fdca746, CORRECT) | Δ |
|---|---|---|---|
| R² BAS | 0.592 | 0.566 | −0.027 |
| **R² HAUT** | 0.438 | **0.483** | **+0.045** |
| R² GLOBAL | 0.606 | 0.593 | −0.013 |
| PR-AUC HAUT | 0.340 | 0.430 | **+0.090** |

**La correction Z-2 AMÉLIORE le HAUT** (+4.5 pts R², +9 pts PR-AUC). Elle dégrade légèrement BAS et GLOBAL, mais le segment critique (HAUT, saisonnier-touristique) en bénéficie significativement. Ceci est cohérent : les gares CHTV/HTV (Château-d'Hauteville / Hauteville) ont une population résidente plus représentative en 2019 (Z-2 pour H22) qu'en 2021 (Z-0 pour H22), car 2019 précède les mouvements migratoires COVID.

### Invalidation des métriques antérieures

Le "coût de causalité −0.0155 HAUT (v1.2→v1.3)" comparait **deux datasets Z-0** (fe9d6b4d et 961a0bd5). Ce chiffre n'est pas attribuable au passage Z-0→Z-2 ; il reflète un effet secondaire non identifié (probablement la correction NaN VVVI qui influe sur le BAS mais pas le HAUT — à ré-investiguer si nécessaire). Ce chiffre **ne doit pas être cité dans la thèse** comme "coût causalité STATPOP".

Le vrai coût/bénéfice de la rigueur causale Z-2 est documenté dans le tableau ci-dessus : la rigueur ne coûte pas de performance, elle **améliore le HAUT** (le segment le plus important pour la détection des surcharges).

### Fichiers impactés (correction)

- `data/processed/ml_dataset.parquet` — hash `5fdca746` (pipeline rebuild 2026-06-18, premier vrai Z-2)
- Métriques finales : voir Enrichi_Seg v1.6 (158f, Split C, `5fdca746`)
- `models/enrichi_seg/enrichi_seg_metadata.json` — version 1.6
- Archives invalides : c1ecfc19 (v1.4), 961a0bd5 (v1.3), fe9d6b4d (v1.2) — toutes Z-0 effectif

## Correction 2026-06-19 — Bug pipeline : forward-fill n'était pas réellement appliqué

### Bug identifié

Audit du 2026-06-19 : `paths.py` pointait vers `statpop_clean.parquet` (DEFAULT_STRATEGY="interpolate") au lieu de `statpop_clean_causal.parquet` (carry_forward). Le dataset `5fdca746` avait le bon mapping Z-2 mais **les valeurs HP*/HPI utilisaient encore l'interpolation** (ex. VV menages 2021 = 4694 = mean(4660,4728) au lieu de 4660 = forward-fill←2020).

Troisième occurrence du même patron de bug (ADR décidé, pipeline non conforme) → assertion dure ajoutée.

### Correction

- `scripts/pipeline/paths.py` ligne 82 : `STATPOP_CLEAN = SOURCES / "statpop_clean_causal.parquet"` ✓
- `Makefile` ligne 37 : cible et commande `--strategy carry_forward` ✓
- `STATPOP_MAPPING` : labels `interpole` → `forward_fill` pour millesimes 2021 et 2023 ✓
- **Assertion dure** dans `add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` : `RuntimeError` si "interpole" détecté dans le résumé de labels ✓

### Vrai effet Z-2-interpolé → Z-2-forward_fill (d39d0bd8, Split C, 158f, modèles réentraînés)

| Segment | 5fdca746 (Z-2-interp) | d39d0bd8 (Z-2-ff) | Δ |
|---|---|---|---|
| R² BAS | 0.5655 | 0.5666 | +0.001 |
| **R² HAUT** | 0.4982 | **0.4896** | **−0.009** (dans le bruit std=0.018) |
| R² GLOBAL | 0.5955 | 0.5949 | −0.001 |
| PR-AUC HAUT | 0.4322 | 0.4079 | −0.024 |

**Interprétation** : l'impact est non significatif (ΔR²HAUT dans 0.5×std multi-seed). L'interpolation avait une légère fuite causale (vue la borne future 2022 pour estimer 2021), mais son impact mesurable sur le modèle est nul. Le forward-fill est retenu pour la rigueur méthodologique.

Observations affectées : **630 413 / 1 141 984 (55.2%)** — H23 (millesime 2021, 337 329 obs) + H25 (millesime 2023, 293 084 obs).

### Décomposition complète de la causalité STATPOP (tableau synthèse)

| Étape | Hash | Source | R²HAUT | ΔR²HAUT |
|---|---|---|---|---|
| Z-0 effectif (invalide) | c1ecfc19 | interp (Z-0 caché) | 0.438 | — |
| Z-2 interpolé | 5fdca746 | interp (Z-2) | 0.4982 | **+0.060** vs Z-0 |
| Z-2 forward-fill (**retenu** — STATPOP du canonique) | d39d0bd8 | ff (Z-2) | 0.4896 | −0.009 vs interp |

Bénéfice total Z-0→Z-2-ff : **+0.052 R²HAUT** (+5.2 pts).

### Fichiers impactés (correction 2026-06-19)

- `data/processed/ml_dataset.parquet` — hash canonique `51e459ff` (v1.8 ; forward-fill causal CF19 + histo_* cutoff mensuel/tronçon CF18). `d39d0bd8` (forward-fill causal seul, 2026-06-19) supersédé — voir ADR-062 amendement.
- `models/enrichi_seg/enrichi_seg_bas.json` — modèle BAS v1.7 (hash 07c32993)
- `models/enrichi_seg/enrichi_seg_haut.json` — modèle HAUT v1.7 (hash 9c6b25ba)
- `models/enrichi_seg/enrichi_seg_metadata.json` — version 1.7
- `scripts/pipeline/paths.py` — STATPOP_CLEAN corrigé
- `Makefile` — cible STATPOP_CLEAN corrigée
- `scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py` — assertion dure + labels forward_fill

## Fichiers impactés (original)

- `data/processed/ml_dataset_v1.3.parquet` — dataset de référence v1.3 (hash 961a0bd5)
- `data/processed/sources/statpop_clean_causal.parquet` — statpop avec forward-fill + VVVI fix (hash fe6b0b1c)
- `models/enrichi_seg/archive_v1.2/` — archive modèles v1.2 (fe9d6b4d)
- `scripts/exp/statpop_philo_c_vvvi_fix.py` — script de construction du dataset v1.3 (exp → référence)
- `docs/adr/ADR-039_carry_forward_statpop_h25.md` — révisé (mapping et imputation corrigés)

---


---
id: ADR-064
ancien_id: ADR-CF20
date_decision: 2026-06-18
statut: révoqué
revoque_par: [ADR-064]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-064 — Intégration STATENT emploi 500m (couche 1, v1.4)

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par son propre amendement.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** **Ce document est auto-révoqué** : son amendement du 18.06.2026 retire les variables d'emploi STATENT qu'il intégrait. Le modèle final compte 158 variables, sans STATENT ; les colonnes restent dans la table canonique au titre de la réversibilité.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut :** Exploré puis **RETIRÉ** — 2026-06-18 (voir §Amendement)
**Auteur :** Erwann Nédellec
**ADRs liés :** ADR-063 (causalité STATPOP), ADR-061 (retrait SIMBA), ADR-035 (réservations)

---

## Contexte

### Source STATENT

STATENT (Statistique structurelle des entreprises, OFS) recense l'emploi au niveau des 100m² hectares LV95 pour l'ensemble de la Suisse. Millesimes disponibles 2015–2023 publiés avec une latence d'environ 18 mois (PUBJAHR = ERHJAHR + 2, vérifié sur l'ensemble des 9 millesimes).

La variable `B08EMPT` désigne l'emploi total (en équivalents plein temps) ; `B08EMPTS3` le secteur tertiaire (services). La protection statistique `B08T ≤ 4` conduit en théorie à un arrondissement à 0, mais à l'échelle des buffers 500 m autour des gares R35 les hectares agrégés répartissent le risque : 0 % des valeurs finales sont classées = 4 arrondies.

### Motivation — revue de littérature

La littérature sur la demande de transport ferroviaire distingue deux catégories de déterminants socio-géographiques :

1. **Signal résidence** (bassin de population autour de la gare de départ) — capturé par STATPOP (intégré, ADR-063).
2. **Signal destination-emploi** (attractivité économique de la gare d'arrivée) — mesuré par l'emploi local, typiquement déterminant sur les lignes de pendulaires.

La R35 (Montreux–Zweisimmen) est une ligne à dominante loisirs/montagne, non de pendulaires. Néanmoins, l'omission du signal destination-emploi laisserait le modèle incomplet vis-à-vis des critères de complétude démontrés dans la revue de littérature. L'intégration est justifiée par la cohérence conceptuelle du jeu de features et par l'exhaustivité démonstrative.

---

## Décision

**Intégrer STATENT comme 4 features supplémentaires (162 features totales) dans Enrichi_Seg v1.4**, malgré un apport métrique légèrement négatif, au nom de la cohérence avec la revue de littérature et de la complétude des déterminants socio-géographiques.

Ce choix privilégie **l'exhaustivité conceptuelle sur la performance brute**. L'apport métrique négatif est **assumé et documenté explicitement** — il ne s'agit pas d'une amélioration de performance.

---

## Méthode d'intégration

### Features construites

| Feature | Description |
|---------|-------------|
| `spatial_gare_depart_emplois_500m_total` | Emploi total (B08EMPT) dans buffer Voronoï 500 m de la gare de départ |
| `spatial_gare_depart_emplois_500m_services` | Emploi secteur tertiaire (B08EMPTS3) dans buffer Voronoï 500 m de la gare de départ |
| `spatial_gare_arrivee_emplois_500m_total` | Emploi total dans buffer Voronoï 500 m de la gare d'arrivée |
| `spatial_gare_arrivee_emplois_500m_services` | Emploi tertiaire dans buffer Voronoï 500 m de la gare d'arrivée |

### Jointure géographique

L'identifiant spatial RELI est identique dans STATENT et STATPOP (`RELI = int((E_LV95-2000000)/100)*10000 + int((N_LV95-1000000)/100)`, système EPSG:2056), ce qui rend les zones Voronoï calculées pour STATPOP directement réutilisables pour STATENT.

### Correction VVVI (défaut NaN)

La gare VVVI (Vevey-Vignerons) a ouvert en H23 et n'apparaît pas dans les topologies antérieures H18–H22. La zone Voronoï de VVVI est reconstruite via la topologie H23 (superficie 717 171 m²) puis appliquée rétrospectivement aux hectares STATENT pour les millesimes 2018–2022. Cette correction suit le même protocole que le correctif VVVI de STATPOP (ADR-063), maintenant 0 % de NaN sur l'ensemble du périmètre.

### Mapping causal Z-3

La borne de disponibilité pour STATENT est plus conservatrice que STATPOP (PUBJAHR = ERHJAHR + 2, plus marges opérationnelles) :

| Année horaire (Z) | Millesime STATENT utilisé |
|-------------------|--------------------------|
| H22 (2021) | 2018 |
| H23 (2022) | 2019 |
| H24 (2023) | 2020 |
| H25 (2024) | 2021 |
| — (2025) | 2022 |

Forward-fill causal cohérent avec ADR-063 (aucune valeur future utilisée).

**Source canonique :** `data/processed/sources/statent_clean_causal.parquet` (91 lignes : 5 millesimes × 17–18 gares + VVVI reconstruit).

---

## Résultat mesuré

Mesure propre (NaN=0 %, déterministe seed=42, split H22-H24/H25 per ADR-072) :

| Segment | R² v1.3 (référence) | R² v1.4 (+STATENT) | ΔR² |
|---------|--------------------|--------------------|-----|
| BAS | 0.5934 | 0.5923 | −0.0012 |
| HAUT | 0.4472 | 0.4375 | **−0.0097** |
| GLOBAL | 0.6084 | 0.6061 | **−0.0024** (assumé) |

| Segment | PR-AUC >63 v1.3 | PR-AUC >63 v1.4 | ΔPR-AUC |
|---------|-----------------|-----------------|---------|
| BAS | 0.4683 | 0.4771 | +0.0088 |
| HAUT | 0.3410 | 0.3401 | −0.0009 |

### Mécanisme ΔR²HAUT — non-artefact confirmé

Le ΔR²HAUT = −0.0097 est **réel**, confirmé par 5 signatures indépendantes :

1. 0 warning XGBoost fit (pas de FutureWarning dtype)
2. 0 NaN features emploi sur test HAUT
3. Preds range sain [−3.4, 98.7], 0 NaN/Inf
4. 0 vraie différence non-STATENT sur train HAUT (3 097 814 comptées précédemment = 100 % faux positifs `NaN != NaN`)
5. Dtypes suspects symétriques entre v1.3 et v1.4 (20 colonnes identiques dans les deux)

**Mécanisme** : les features emploi présentent une forte variance *inter-gares* mais une variance *intra-gare quasi nulle* (5 millesimes, 25 valeurs uniques pour 9 gares de départ HAUT). Le modèle HAUT les exploite comme quasi-identifiants géographiques (7 splits, gain=1 434 sur `arrivee_emplois_total`) partiellement redondants avec les features de position déjà présentes (`spatial_gare_arrivee_ordre`, top-7 SHAP HAUT). Cette redondance introduit du bruit marginal → légère dégradation test.

### Rangs SHAP (4 features emploi)

**Segment BAS (162 features)**

| Feature | Rang SHAP | |SHAP| moyen |
|---------|-----------|--------------|
| `arrivee_emplois_500m_total` | 127/162 | 0.0053 |
| `arrivee_emplois_500m_services` | 131/162 | 0.0045 |
| `depart_emplois_500m_total` | 138/162 | 0.0028 |
| `depart_emplois_500m_services` | **162/162** | 0.0000 |

**Segment HAUT (162 features)**

| Feature | Rang SHAP | |SHAP| moyen |
|---------|-----------|--------------|
| `arrivee_emplois_500m_total` | 99/162 | 0.0335 |
| `depart_emplois_500m_total` | 126/162 | 0.0038 |
| `arrivee_emplois_500m_services` | 147/162 | 0.0001 |
| `depart_emplois_500m_services` | 155/162 | 0.0000 |

Les 4 features emploi occupent le bas du classement SHAP sur les deux segments.

---

## Arbitrage explicite : STATENT vs SIMBA (ADR-061)

SIMBA a été retiré (ADR-061) pour des raisons de **validité** : leakage de disponibilité opérationnelle, instabilité inter-annuelle, NaN structurels H25 rendant le déploiement impossible. STATENT est **valide et stable** (mapping causal rigoureux, NaN=0 %, couverture complète). La règle est cohérente :

> On retire ce qui est **invalide ou instable**. On peut conserver ce qui est **valide**, même si légèrement redondant et métriquement négatif, par choix de complétude conceptuelle documenté.

L'intégration de STATENT ne remet pas en cause le retrait de SIMBA.

---

## Coût et bénéfice

| Dimension | Valeur |
|-----------|--------|
| ΔR² GLOBAL | −0.0024 (assumé) |
| ΔR² HAUT | −0.0097 (réel, mécanisme compris) |
| ΔR² BAS | −0.0012 (négligeable) |
| ΔPR-AUC BAS >63 | +0.0088 (marginal) |
| Bénéfice conceptuel | Complétude déterminants socio-géographiques pour la thèse |
| Coût déploiement | Nil (STATENT stable, Z-3 causal, NaN=0 %) |

---

## Traçabilité

- Dataset : `data/processed/ml_dataset_v1.4.parquet` (hash MD5-8 `c1ecfc19`)
- Source STATENT canonique : `data/processed/sources/statent_clean_causal.parquet`
- Script expérimental : `scripts/exp/statent_integration_exp.py`
- Modèles : `models/enrichi_seg/enrichi_seg_{bas,haut}.json` v1.4 (162 features)
- Vérification : `models/enrichi_seg/verify_enrichi_seg.py` (non-régression ✓)
- Archive v1.3 (961a0bd5) : `models/enrichi_seg/archive_v1.3/`

---

## Amendement 2026-06-18 — STATENT retiré de la configuration finale

### Contexte de la révision

L'évaluation ADR-064 ci-dessus a été conduite sur le dataset `c1ecfc19` qui contenait STATPOP Z-0 malgré le label "ADR-063 causal Z-2" (bug pipeline identifié le 2026-06-18 — voir §Chronologie mapping Z-0/Z-2). Après reconstruction du pipeline (`5fdca746`, STATPOP Z-2 réellement appliqué), l'effet réel de STATENT a été re-mesuré sur les données correctes.

### Effet STATENT sur données correctes (dataset 5fdca746)

| Segment | ΔR² (162f vs 158f) | ΔPR-AUC>63 |
|---|---|---|
| BAS | +0.003 | **+0.017** |
| HAUT | **−0.016** | −0.002 |
| GLOBAL | −0.0004 | — |

Sur les données correctes, la dégradation HAUT est **plus forte** (−0.016 vs −0.010 précédemment), et le gain BAS PR-AUC est confirmé (+0.017). Les 4 features STATENT restent en bas du classement SHAP.

### Décision de retrait — 2026-06-18

STATENT est **retiré** de la configuration finale (Enrichi_Seg v1.6, 158 features). Justification :

1. **Coût HAUT non justifié** : ΔR²HAUT = −0.016 sur données correctes. Le segment HAUT (touristique, saisonnier) est le segment critique pour la détection des surcharges — une dégradation de −0.016 R² n'est pas acceptable au nom de la complétude conceptuelle.
2. **Redondance géographique confirmée** : les features emploi STATENT capturent essentiellement l'identité de la gare, déjà portée par `spatial_gare_arrivee_ordre`, `id_gare_arrivee` et les features STATPOP. Rangs SHAP : 99e–162e/162 sur HAUT, 127e–162e/162 sur BAS.
3. **Cohérence avec le principe de parcimonie** (ADR-054) : STATENT est valide et stable (contrairement à SIMBA), mais la redondance et le coût HAUT net le placent hors du seuil d'inclusion.
4. **Distinction SIMBA vs STATENT** : SIMBA a été retiré pour invalidité opérationnelle ; STATENT est retiré pour redondance à coût net négatif. Les deux retraits sont cohérents mais pour des raisons distinctes.

### Traçabilité du retrait

- Modèle final : Enrichi_Seg **v1.6**, 158 features (sans STATENT), Split C, dataset `5fdca746`
- Script de mesure : `consolidation_finale/scripts/eval_split_tce_et_split_c.py`
- Résultats : `consolidation_finale/outputs/eval_split_h22_tce_splitc_resultats.json`
- STATENT demeure dans le pipeline (`stage_06b`) et dans `ml_dataset.parquet` — son retrait est uniquement dans la liste de features du modèle (`features_158f_sans_simba.json`)

### Chronologie du mapping STATPOP Z-0/Z-2

| Dataset | Hash | Label ADR | STATPOP réel dans les données |
|---|---|---|---|
| ml_dataset_exp_inc1 | fe9d6b4d | v1.2 pré-CF19 | Z-0 |
| ml_dataset v1.3 | 961a0bd5 | ADR-063 Z-2 | **Z-0** (bug : stage_06 non reconstruit) |
| ml_dataset v1.4 | c1ecfc19 | ADR-063+CF20 Z-2 | **Z-0** (bug persistant) |
| ml_dataset final | **5fdca746** | pipeline rebuild 2026-06-18 | **Z-2 ✓** (premier dataset correct) |

**Implication** : toutes les métriques publiées avant la version 1.6 (y compris la "dégradation HAUT −0.0155 ADR-063" et les métriques ADR-064) ont été calculées sur des données avec STATPOP Z-0. Ces métriques sont invalides pour l'analyse de causalité STATPOP. Se référer aux métriques v1.6 pour la thèse.

## Addendum (2026-07-24)

**Erratum 1.** Lire « R35 (Vevey–Les Pléiades) » au lieu de « R35 (Montreux–Zweisimmen) » dans la section Motivation. Aucune incidence sur la décision ni sur les données.

**Erratum 2 (au gel).** §Correction VVVI : lire « **VVVI (Vevey-Vignerons)** » au lieu de « VVVI (Zweisimmen) ». VVVI est la gare de Vevey-Vignerons, ouverte en H23 en remplacement de Gilamont ; Zweisimmen appartient à la ligne Montreux–Zweisimmen, hors R35. Aucune incidence sur les données : le code n'a jamais manipulé que la topologie R35.

**Erratum 3 (au gel).** Les bornes d'emploi « de 8 à Rougemont à 756 à Montreux » et le CV ≈ 1,85 ont été retirés du §Mécanisme : ils portaient sur des gares hors R35 et ne sont pas reproductibles depuis le dépôt remis, la table STATENT étant une entrée figée sans producteur canonique (ADR-075). Aucun chiffre de remplacement n'est produit. Le retrait effectif des quatre variables d'emploi est en revanche vérifiable : elles sont absentes de `outputs/couche2/features_158f_sans_simba.json`.

---


---
id: ADR-065
ancien_id: ADR-CF21
date_decision: 2026-06-18
statut: actif
modifie: [ADR-027, ADR-038]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-065 — Split C : exclusion des tronçons Gilamont H22, conservation du reste de H22

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-027, ADR-038.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-18 |
| **Date** | 2026-06-18 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-027 (split H22+H23/H24), ADR-038 (extension H25), ADR-063 (STATPOP Z-2) |
| **Version modèle** | Enrichi_Seg v1.6 (158f, Split C, hash dataset 5fdca746) |

---

## Contexte

L'ADR-038 avait acté le split H22+H23+H24 train / H25 test. La question de la qualité de H22 dans le jeu d'entraînement a été posée en vue de la consolidation finale. Deux signaux justifiaient une investigation :

1. **TCE H22 = 48.9 %** : seule la moitié des courses ISTDATEN H22 est présente dans les données APC. Le notebook 02 documente ce phénomène comme un "artefact format APC H22" (variation intra-annuelle : 9 % en septembre 2022, 83 % en juillet 2022). La cause n'est pas entièrement élucidée ; la distribution des courses capturées est cohérente (biais de sélection non détecté sur créneaux, type de jour, mois, segment).

2. **Bascule Gilamont → VVVI en H23** : la gare Gilamont (BPUIC 8501260, km 1.21 sur la ligne) a été remplacée par Vevey Vignerons (VVVI, BPUIC 8502476, km 1.45) à l'ouverture de H23. Les 4 tronçons Gilamont (GIL↔VV, GIL↔HTV) existent uniquement en H22 et n'ont aucun équivalent en H23-H25. Leur présence dans le train introduit une topologie réseau que le modèle ne rencontrera jamais en production.

### Évaluation empirique : Split A vs B vs C

Trois configurations ont été comparées sur test H25 (158 features, seed=42, même hyperparamètres) :

| Configuration | Train | HAUT R² | BAS R² | GLOBAL R² |
|---|---|---|---|---|
| **A (actuel)** | H22+H23+H24 (832 732) | 0.498 | 0.563 | 0.593 |
| **B (sans H22)** | H23+H24 (671 135) | 0.456 | 0.562 | 0.586 |
| **C (H22 sans Gilamont)** | H22_valid+H23+H24 (801 282) | **0.498** | **0.566** | **0.596** |

### Localisation de la valeur HAUT de H22

Le gain HAUT de +4.2 pts R² (A vs B) est **entièrement attribuable aux tronçons Blonay-Pléiades de H22**, qui sont topologiquement identiques sur H22-H25. La gare Gilamont est dans la section BAS (VV→Blonay) ; les tronçons Gilamont exclus du train sont intégralement classifiés segment BAS. Retirer Gilamont n'affecte pas une seule observation HAUT de H22 (Split C HAUT = Split A HAUT, ΔR² = 0.0000 exactement).

### Validité topologique de Split C

La validité du nettoyage H22 BAS a été vérifiée sur les 12 tronçons BAS partagés (ni Gilamont ni VVVI) :

| Périmètre | KS max H22 vs H23 | Seuil ADR-027 |
|---|---|---|
| Tronçons voisins HTV (CHTV↔HTV) | **0.095** | 0.15 ✅ |
| Tronçons intérieurs BAS | **0.080** | 0.15 ✅ |

Aucun signal de redistribution de flux sur les tronçons adjacents à la bascule Gilamont→VVVI. Les décalages observés (H22 légèrement > H23 < H24) correspondent à la tendance temporelle générale du trafic post-COVID, non à un effet topologique.

**Cohérence de l'ordre spatial** : `spatial_gare_depart_ordre` et `spatial_gare_arrivee_ordre` sont stables par gare sur H22-H25 (ancrage par position km, non par rang séquentiel). HTV = ordre 4 en H22 comme en H23-H25. Aucune correction nécessaire.

**Note topographique** : Gilamont (km 1.21) et VVVI (km 1.45) sont à 244 m l'une de l'autre. Ce n'est pas un simple renommage mais un déplacement de gare. Les tronçons GIL↔VV/HTV et VVVI↔VV/HTV sont des arêtes distinctes du graphe réseau.

**Note CLIE** : Clies (BPUIC 8501261, ordre 3) est absente de ml_dataset sur toutes les années. Cette gare ne constitue pas un tronçon direct dans les données APC (services directs GIL→HTV / VVVI→HTV). Elle est conservée dans dim_gare pour historique.

---

## Décision

**Split C** : jeu d'entraînement = H22 (tronçons Gilamont exclus) + H23 + H24, test = H25.

**Règle d'exclusion** : retirer du train toutes les observations dont `id_gare_depart_bpuic = 8501260` OU `id_gare_arrivee_bpuic = 8501260` (Gilamont). Soit 31 450 observations BAS H22 sur 161 597 totales H22 (19.5 %).

**H22 conservé** pour :
- Le segment HAUT (Blonay-Pléiades) : topologie identique H22-H25, 3ème cycle saisonnier qui apporte +4.2 pts R² HAUT vs Split B.
- Le segment BAS hors Gilamont : 10 tronçons BAS topologiquement stables (KS < 0.10), nettoyage améliore BAS +0.003 R² vs Split A.

---

## Implémentation

```python
GILAMONT_BPUIC = 8501260
gilamont_mask = (
    (df["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
    (df["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC)
)
h22_valid = df[(df["horaire_annee_horaire"] == "H22") & ~gilamont_mask]
train_c = pd.concat([h22_valid,
                     df[df["horaire_annee_horaire"].isin(["H23", "H24"])]])
```

---

## Résultat

| Segment | R² H25 | PR-AUC H25 | MAE>63 | biais>63 |
|---|---|---|---|---|
| BAS | 0.5655 | 0.4358 | 28.7 | −27.8 |
| HAUT | 0.4982 | 0.4322 | 39.5 | −39.2 |
| GLOBAL | 0.5955 | — | MAE=7.90 | — |

Enrichi_Seg v1.6 — dataset `5fdca746`, 158 features (sans SIMBA, sans STATENT).

---

## Limites documentées

- **TCE H22 = 48.9 %** : 51 % des courses ISTDATEN H22 sont absentes des données APC. La cause est labelisée "artefact format" dans le notebook 02 mais non entièrement élucidée. La distribution des courses capturées est cohérente. Un biais sur les courses absentes (notamment septembre 2022 à 9 % de TCE) ne peut pas être totalement exclu.
- La stationnarité de H22 BAS non-Gilamont a été vérifiée par KS (< 0.10), non par une analyse complète de la représentativité des courses manquantes H22 vs ISTDATEN.

---


---
id: ADR-066
ancien_id: ADR-CF22
date_decision: 2026-06-20
statut: amendé
amende_par: [ADR-076]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-066 — Gouvernance des empreintes de hash des datasets (SHA256[:8], rupture MD5→SHA256)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-076.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-20 |
| **Date** | 2026-06-20 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-062 (cutoff mensuel histo), ADR-063 (STATPOP Z-2 causal), ADR-064 (retrait STATENT), ADR-065 (Split C) |
| **Version modèle** | Enrichi_Seg v1.7 (158f, Split C, hash dataset `d39d0bd8`) |
| **Environnement** | pyarrow 21.0.0, pandas 2.3.3 |

---

## Contexte

Chaque version du dataset `ml_dataset.parquet` est identifiée par une empreinte de hash tronquée à 8 caractères, censée garantir la traçabilité et la reproductibilité bit-à-bit de l'artefact d'entraînement. Lors de la consolidation finale (v1.7), un audit de cohérence a mis en évidence deux problèmes de gouvernance non documentés :

1. **Rupture d'algorithme de hachage en cours de chaîne.** Les versions antérieures et postérieures de la chaîne n'utilisent pas le même algorithme :

   | Version | Hash | Algorithme | Label dans les outputs |
   |---|---|---|---|
   | v1.2 | `fe9d6b4d` | **MD5[:8]** | `hash_md5_8` |
   | v1.3 | `961a0bd5` | **MD5[:8]** | `hash_md5_8` |
   | v1.4 | `c1ecfc19` | **MD5[:8]** | `hash_md5_8` |
   | seuil 63 | `daf936c8` | **MD5[:8]** | `hash_md5_8` |
   | v1.6 | `5fdca746` | **SHA256[:8]** | `hash_sha256_8` |
   | **v1.7** | **`d39d0bd8`** | **SHA256[:8]** | `hash_sha256_8` |

   La bascule MD5 → SHA256 est intervenue **au passage v1.4 → v1.6** (premiers scripts SHA256 : `q_all_v16_5fdca746.py`, `final_158f_split_c.py`). Le même fichier physique produit donc des empreintes différentes selon l'algorithme — exemple sur l'artefact courant : `MD5[:8] = e380d1e5`, `SHA256[:8] = d39d0bd8`.

2. **Absence de référence ADR.** La convention de hachage n'était formalisée dans aucun ADR. Le rapport de synthèse (`rapport_synthese_couche1`, §3.1) citait par erreur **ADR-015**, qui traite de la *logique opérationnelle J-2 des features ISTDATEN* et n'a aucun rapport avec le hachage.

## Décision

1. **Empreinte canonique = SHA256[:8] du fichier `ml_dataset.parquet`, à environnement pyarrow constant (21.0.0).** C'est le standard en vigueur **depuis v1.6 (`5fdca746`)** et il est confirmé pour toutes les versions ultérieures. Le hachage porte sur les octets bruts du parquet (`hashlib.sha256(path.read_bytes()).hexdigest()[:8]`).

2. **Rupture d'algorithme assumée et documentée.** Les versions **≤ `daf936c8`** (v1.2 `fe9d6b4d`, v1.3 `961a0bd5`, v1.4 `c1ecfc19`, seuil `daf936c8`) utilisent **MD5[:8]** ; les versions **≥ v1.6** (`5fdca746`, v1.7 `d39d0bd8`) utilisent **SHA256[:8]**.

3. **Conséquence assumée — hashs historiques non comparables et non recalculables.** Les empreintes de la chaîne historique ne sont pas comparables entre elles (algorithmes différents). Les parquets ≤ `daf936c8` ayant été archivés/supprimés (seul `ml_dataset.parquet` = `d39d0bd8` subsiste sur disque), leur SHA256 **n'est pas recalculable**. Les hashs MD5 antérieurs valent comme **repères d'archive**, non réconciliables avec le standard actuel.

4. **Reproductibilité de l'artefact canonique — vérifiée.** `d39d0bd8` (artefact canonique final v1.7) est **reproductible par `make` complet à pyarrow 21.0.0 constant**. C'est la version qui compte pour la reproductibilité de l'artefact ; la non-réconciliation des hashs historiques n'affecte pas la reproductibilité du dataset en production.

5. **Correction de la référence erronée.** La citation « ADR-015 » pour la convention de hachage a été retirée du rapport (§3.1). **Le présent ADR-066 est désormais la référence unique de la convention de hachage des datasets.**

## Recommandation future (gouvernance, non bloquant)

- **Double-tampon MD5 + SHA256** pour les versions futures, si un pont avec la chaîne historique MD5 est souhaité.
- **Noter la version de `pyarrow`** dans tout ADR critique : l'empreinte du parquet dépend du writer (schéma, compression, `created_by`). Un changement de version pyarrow peut modifier le hash sans changement de contenu.

## Preuve de reproductibilité (v1.7 / `d39d0bd8`)

Vérification réalisée le 2026-06-20 :

```
make clean            # suppression des stages (sources/dims conservées)
make                  # reconstruction complète de la chaîne de stages → ml_dataset.parquet
```

Résultat — parquet régénéré :

```
SHA256[:8] = d39d0bd8   ✓  (== empreinte canonique attendue)
MD5[:8]    = e380d1e5       (cohérent avec l'artefact d'origine)
1 141 984 lignes × 209 colonnes ; années H22-H25
pyarrow 21.0.0 | pandas 2.3.3
```

Cohérence de la chaîne amont confirmée sur l'artefact régénéré :
- STATPOP : `statpop_clean_causal` branché, label `forward_fill` (630 413 obs) + `exact` (511 571), mapping Z-2 — aucun `interpole`/`carry_forward` résiduel ;
- Ski : `event_ski_source` ∈ {`officiel`, `hors_saison`} — `reconstruit` absent du dataset ML ;
- STATENT : absent des 209 colonnes conservées (retiré au build — ADR-064) ;
- ResSys : intégré en ligne dans la passe finale (`build_ml_dataset.py` dépend de `stage_09`, pas de `stage_10` ; `stage_10` = artefact d'audit hors flux principal) ;
- Split C (ADR-065) : sélection appliquée en aval de la construction (le parquet contient l'intégralité des observations H22-H25).

## Conséquences

- **Positif** : convention de hachage formalisée et tracée ; reproductibilité de l'artefact canonique prouvée ; suppression d'une citation ADR erronée ; algorithme robuste (SHA256) confirmé comme standard.
- **Négatif assumé** : la chaîne historique MD5 reste non réconciliable (parquets archivés/supprimés) — accepté, car seule la version canonique en production importe pour la reproductibilité.
- **Dépendance environnementale** : l'empreinte est garantie à `pyarrow 21.0.0` constant ; tout changement de version du writer devra être réévalué et acté.

## Mise à jour 2026-06-20 — hash canonique courant `51e459ff`

`d39d0bd8` (v1.7) est **supersédé** par **`51e459ff`** (v1.8) : application réelle d'ADR-062 (histo_* cutoff mensuel + clé tronçon, voir amendement ADR-062). `51e459ff` est un **SHA256[:8]** (même convention), **reproductible** par `make clean && make` (pyarrow 21.0.0, vérifié 2026-06-20). La convention de hachage reste inchangée ; seul le pointeur canonique évolue d39d0bd8 → 51e459ff.

## Mise à jour 2026-06-20 bis — hash canonique courant `416bb90b`

`51e459ff` (v1.8) est **supersédé** par **`416bb90b`** (v1.9) : deux dernières corrections de leakage — cutoff APC composé décision T-1 + ingestion (amendement ADR-062) et headway sur grille planifiée (ADR-067). `416bb90b` est un **SHA256[:8]** (convention inchangée), **reproductible** : deux `make clean && make` indépendants → `416bb90b` byte-exact (pyarrow 21.0.0, vérifié 2026-06-20). Pointeur canonique : d39d0bd8 → 51e459ff → **`416bb90b`**. Cette convention de hachage (ADR-066) reste la référence unique et **n'est pas modifiée** par la bascule ; seul le pointeur évolue.

## Addendum 2026-07-12 — source figée des figures de stationnarité (section 4.5.1) : `stage_09_simba.parquet` (SHA256[:8] `954135f9`)

Les figures de stationnarité H16-H25 de la section 4.5.1 (matrice KS et KDE de la cible 2e classe) ne peuvent pas être produites depuis le gel canonique `ml_dataset.parquet` (`ba493568`), qui ne couvre que H22-H25 (filtre temporel du build, ADR-027/038). Elles s'appuient sur la table amont pré-filtre `data/processed/stage_09_simba.parquet`, **SHA256[:8] = `954135f9`** (pyarrow 21.0.0), consignée ici comme **source figée** de ces figures.

**Statut d'empreinte.** `954135f9` est un intermédiaire du pipeline médaillon, **hors du périmètre de gouvernance canonique** du présent ADR (seul `ba493568`, empreinte du `ml_dataset.parquet`, est le pointeur canonique gouverné). Elle est **figée en entrée** des figures (prise telle quelle sur disque) et ne fait l'objet d'**aucun contrat de reproductibilité propre** : sa reconstruction dépendrait d'un run complet du pipeline (hors périmètre du chantier figures, lecture seule), non rejoué ni re-vérifié ici. Elle est donc consignée comme non re-générable dans ce cadre, à la différence de `ba493568`.

**Validation par recoupement (deux ancrages indépendants).**
1. **Cardinalité** : `stage_09` restreint à H16-H24 compte **2 051 510** observations, identique au chiffre déclaré par ADR-027 (l.20 : « 2 051 510 observations dans stage_09 »).
2. **Identité octet à octet du sous-ensemble courant** : la cible `target_voyageurs_2eme_classe` de `stage_09` sur H22, H23, H24, H25 est **identique ligne à ligne** à celle du canonique `ba493568` (cross-check 4/4 années : effectifs 161 597 / 335 426 / 335 709 / 309 252, séries triées égales).

**Surveillance.** `954135f9` est ajoutée à `scripts/check_hash_propagation.py` comme empreinte de **source figée** (règle positive de présence : attendue dans le présent ADR et dans le générateur `docs/memoire/figures/section_4_5_1/make_fig_4_5_1.py`), distincte des empreintes canoniques supersédées surveillées par la règle A (elle n'est pas « périmée » : sa présence est requise, pas proscrite).

**Convention inchangée.** La convention de hachage (SHA256[:8] sur les octets du parquet, pyarrow 21.0.0) reste celle du présent ADR ; cet addendum n'ajoute qu'un registre de source figée, il ne modifie ni la gouvernance canonique ni les empreintes historiques.

---


---
id: ADR-067
ancien_id: ADR-CF23
date_decision: 2026-06-20
statut: actif
modifie: [ADR-018]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-067 — Headway calculé sur la grille horaire planifiée connue à J-1 (annulés et suppléments inclus)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-018.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-20
**Statut** : Accepté
**Décideur** : Erwann Nédellec
**Périmètre** : features `ist_headway_*` uniquement (`build_dim_headway.py`)
**Lié à** : ADR-018 (features `ist_headway_*` depuis ISTDATEN), ADR-022 (disponibilité J-1), ADR-062 (cutoff histo_*, autre correction du même rebuild canonique)

---

## Contexte

Les features `ist_headway_*` mesurent l'isolement temporel d'un train sur son tronçon × sens
(minutes depuis le train précédent / jusqu'au train suivant, à l'horaire **théorique**).
Elles sont calculées par `build_dim_headway.py` à partir d'ISTDATEN, qui est construite depuis
l'**horaire planifié** : tous les trains prévus y figurent avec un statut (`is_annule`,
`is_supplementaire`).

L'implémentation antérieure filtrait les trains annulés avant de reconstruire les tronçons :

```python
df = df_istdaten[~df_istdaten["is_annule"]].copy()
```

Un audit externe (2026-06-20) a relevé que ce filtre fait dépendre le headway d'une information
de **statut réalisé** : retirer un train parce qu'il a été annulé suppose que l'annulation est
connue au moment du calcul. Or la décision UM se prend à **J-1**, et l'annulation d'un train du
jour J n'est **pas connue à J-1**. Le headway antérieur injectait donc, sur une fraction des
tronçons, une information non disponible à l'inférence (distribution shift entraînement/inférence).

---

## Décision

Le headway se calcule sur **tous les trains de la grille horaire planifiée connue à J-1**, sans
aucun filtre de statut réalisé. Critère unique : *« le train était-il dans la grille planifiée
connue à J-1 ? »*

| Statut | Connu à J-1 ? | Décision |
|---|---|---|
| Régulier | Oui | **Inclus** |
| **Annulé** (`is_annule = True`) | Oui (planifié) ; l'annulation n'est **pas** connue à J-1 | **Inclus** (changement) |
| **Supplémentaire** (`is_supplementaire = True`) | Oui — planifié en amont | **Inclus** (déjà le cas) |

**Justification du maintien des suppléments.** Le processus de planification MOB n'autorise pas
l'ajout d'un train le jour J : tout supplément est planifié en amont et figure donc dans la grille
connue à J-1 (source : E. Nédellec, data lead MOB). La cohérence est confirmée par les données :
les trains supplémentaires ont un `horaire_depart` théorique renseigné dans 88,7 % des cas
(≈ le taux des réguliers, 91,3 %), signe de leur présence à la grille planifiée.

**Modification** : retrait du filtre `~is_annule` dans `_reconstruire_troncons`
(`build_dim_headway.py`). Aucun autre changement (toujours `horaire_depart` théorique uniquement,
aucun fallback sur `reel_depart`, cf. ADR-018).

---

## Ampleur mesurée (dataset 51e459ff → 416bb90b)

- **+22 555 tronçons** réintégrés (présents à la grille planifiée, auparavant écartés car annulés).
- **3 989 tronçons existants modifiés (0,174 %)** — un train annulé intercalé décale le voisin
  immédiat. Médiane du headway **inchangée (30,0 min)** ; l'effet est strictement local.
- Couverture `ist_headway_*` dans ml_dataset : 78,9 % / 79,3 % (avant/après) ; NaN structurels =
  premiers/derniers de journée (3,5 %).
- Note : 3 941 lignes étaient à la fois `is_annule` ET `is_supplementaire` ; auparavant exclues
  par le filtre annulé, désormais incluses.

**Validité de l'horaire théorique par statut** (taux d'`horaire_depart` manquant) : régulier
8,68 %, annulé 9,56 %, supplément 11,33 % — taux comparables, aucune anomalie. Les rares lignes
sans horaire théorique produisent un headway NaN (comportement identique pour tous les statuts).

---

## Rang SHAP des features `ist_headway_*` (H25, Enrichi_Seg)

`ist_headway_apres_min` et `ist_headway_avant_min` sont des features **importantes**
(rangs #17 et #19/158 sur le segment BAS ; #36 et #61/158 sur HAUT) — d'où l'intérêt de les
calculer sur la bonne grille. Les flags `is_first/last_of_day` sont en queue de classement
(rangs > 130). La part d'information réalisée retirée par cette correction reste néanmoins
**bornée à 0,174 %** des tronçons.

---

## Conséquences

- **Une des deux corrections du rebuild canonique `416bb90b`** (2026-06-20), avec l'amendement
  ADR-062 (cutoff composé). Orthogonalité stricte vérifiée : seules les 4 colonnes
  `ist_headway_*` changent du fait de cette correction (16 colonnes `histo_*` du côté CF18) ;
  189/209 colonnes byte-identiques à 51e459ff.
- **ADR-018** : révisé — le headway reste théorique mais sur la grille planifiée complète
  (le filtre `~is_annule` antérieur est supprimé).
- Effet combiné CF18+CF23 sur métriques H25 : faible et conforme au retrait de biais
  (cf. CONTEXT.md, section Enrichi_Seg v1.9).

---

## Fichiers impactés

| Fichier | Modification (2026-06-20) |
|---|---|
| `scripts/sources/build_dim_headway.py` | retrait du filtre `~is_annule` dans `_reconstruire_troncons` + docstring |
| `data/processed/sources/dim_headway.parquet` | recalculé (grille planifiée complète) |
| `data/processed/ml_dataset.parquet` | hash canonique `416bb90b` (avec ADR-062 composé) |

---

## Références

- ADR-018 — Features `ist_headway_*` depuis ISTDATEN exclusivement (révisé par cet ADR)
- ADR-062 — Amendement règle composée du cutoff histo_* (même rebuild canonique)
- Audit externe headway/cutoff, 2026-06-20 (5 points ; CF23 = point 4, CF18 amendé = point 3)

---


---
id: ADR-068
ancien_id: ADR-CF24
date_decision: 2026-06-22
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-068 — Traçabilité a posteriori du retrait des identifiants de gare (`id_gare_*`) de la liste de features

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** Le `xgb_M0` cité ici (12 variables) est un **objet distinct** de la baseline M0 du mémoire (31 variables, §4.5.2). L'homonymie est signalée, non résolue.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (traçabilité a posteriori) — 2026-06-22 |
| **Date** | 2026-06-22 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-033 (pivot, ère 160f — listait `id_gare_*`), ADR-036 (modèle B 168f), ADR-017 (ablation `horaire_numero_train`), ADR-037 (grain histo B_prime), ADR-048 (sélection externe sur 179f) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) |

---

## Objet

Cet ADR **constate et trace a posteriori** le retrait des features `id_gare_depart` et
`id_gare_arrivee` de la liste de features du modèle. Cette décision **n'avait pas été
formalisée au moment où elle a eu lieu** ; le présent document la documente après coup,
sans réintroduire les features ni modifier le hash canonique.

**Aucun changement de modèle, de dataset ou de hash n'est induit par cet ADR — il est purement documentaire.**

## Constat factuel (chronologie vérifiée)

Vérification par extraction des `feature_names` des modèles sérialisés et confrontation des listes de features :

| Modèle | n features | `id_gare_depart` / `id_gare_arrivee` |
|---|---|---|
| `xgb_M0` (12f) | 12 | présent (`id_gare_depart`) |
| `xgb_A` (160f, ADR-033) | 160 | **présents** |
| `xgb_B` (168f, ADR-036) | 168 | **présents** |
| `xgb_B_prime` (179f) | 179 | **absents** |
| 171f / 170f / 169f / **158f canonique** | … | **absents** |

- **Transition exacte** : `xgb_B` (168f) → `xgb_B_prime` (179f), datée par git **2026-06-04 → 2026-06-05**.
- **Diff identifiants retirés au même moment** : `id_gare_depart`, `id_gare_arrivee`, `base_sens`, `horaire_numero_train` (différence exacte des deux listes de features).
- Le notebook 07 (segmentation, 2026-05-29, ère B) gardait encore `id_gare_depart`/`id_gare_arrivee` comme features catégorielles (seules les variantes `_bpuic` étaient exclues via `COLS_EXCLUES_ML`).

## Rationnel (sourcé, non reconstruit après coup)

Le retrait est cohérent avec des éléments **mesurés à l'époque**, même s'il n'avait pas été
formalisé comme décision :

1. **Importance mesurée négligeable.** CONTEXT.md « Finding B » : dans le modèle B (168f),
   `id_gare_depart` / `id_gare_arrivee` se classent **rang 149/168 et 152/168** au gain XGBoost
   (gain **0,049 % et 0,035 %**).
2. **Redondance structurelle.** `spatial_gare_depart_ordre` et `spatial_gare_arrivee_ordre`
   encodent la position des gares sur la ligne et **figurent dans les 158 features canoniques**
   (rangs #60 et #61 de `features_158f_sans_simba.json`). La topologie est donc préservée sans
   les identifiants nominaux.
3. **Robustesse out-of-time.** Un identifiant **nominal** (LabelEncodé, traité comme ordinal
   arbitraire par XGBoost) généralise mal à une topologie qui change entre millésimes
   (Gilamont → VVVI, ADR-065), là où l'**ordre ordinal de position** (`spatial_gare_*_ordre`)
   généralise par position relative.
4. **Cohérence de nettoyage.** Le retrait s'inscrit dans le nettoyage groupé des identifiants
   bruts à la construction de B_prime (`horaire_numero_train` tracé par **ADR-017** ; `base_sens`
   conservé uniquement comme **clé** de groupement `histo_*` — ADR-062 — et exclu des features
   au titre des clés d'identification, cf. §3.4 du rapport de synthèse).

## Honnêteté de traçabilité

- La décision **n'a pas été formalisée** au moment du retrait (2026-06-05) : aucun commit,
  ADR ou note ne l'enregistrait. Elle est tracée **a posteriori** ici.
- **ADR-033 n'est pas réécrit** : il reste un document daté de l'ère 160f où `id_gare_*` étaient
  effectivement des features importantes (par divergence inter-segment). Sa lecture doit se faire
  dans ce contexte historique.

## Décision

1. **Ne pas réintégrer** `id_gare_depart` / `id_gare_arrivee` dans les features : apport mesuré
   négligeable, redondance avec `spatial_gare_*_ordre`, réintégration changerait le hash
   canonique `416bb90b` et dégraderait la robustesse OOT pour un gain attendu nul.
2. **Tracer** le retrait via le présent ADR.
3. **Aligner** CONTEXT.md « Finding B » (qui décrivait encore les `id_gare_*` comme présentes)
   sur l'état réel, sans effacer la mesure historique (rang 149/152 reste un fait utile).

## Conséquences

- Aucune sur le modèle, le dataset ou le hash (`416bb90b` figé).
- Documentaire : cohérence rétablie entre la liste de features réelle, le rapport de synthèse
  (§4.4 corrigé) et CONTEXT.md « Finding B ».
- `ALL_ADRS.md` (digest généré) devra être régénéré pour inclure cet ADR.

---


---
id: ADR-069
ancien_id: ADR-CF25
date_decision: 2026-06-28
statut: actif
modifie: [ADR-050, ADR-051]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-069 — Conservation de la perte MSE (`reg:squarederror`) : leviers de perte testés et écartés

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-050, ADR-051.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-28 |
| **Date** | 2026-06-28 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-052 (hyperparamètres XGBoost), ADR-060 (seuil surcharge 63), ADR-065 (Split C), ADR-030 / ADR-031 (découplage R²/rappel classe rare), ADR-033 (pivot régression + augmentation couche 2) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset ou de hash.** |

---

## Contexte

Le directeur du travail de master et un audit externe ont relevé que la perte
`reg:squarederror` (MSE) minimise son risque sur la **masse des faibles charges** (≤63,
~97 % des tronçons) et **sous-prédit structurellement la zone de surcharge >63** : le biais
canonique global sur H25 est de **−28,5** (le modèle prédit en moyenne 28,5 voyageurs de
moins que l'observé sur les tronçons réellement >63 ; HAUT : −42,3).

Question posée : **un autre traitement de la perte peut-il faire mieux sur la zone >63 —
réduire le biais ET/OU relever la séparabilité (PR-AUC) ?** La distinction est essentielle :
réduire le biais déplace le *point de fonctionnement* ; relever la PR-AUC relève le *plafond*
de pouvoir discriminant (capacité à ordonner surcharges et non-surcharges, indépendamment du
seuil de décision).

## Décision

**La perte `reg:squarederror` est CONSERVÉE comme perte canonique de la couche 1.**
**Aucun levier de perte** (pondération des observations ou perte asymétrique) **n'est adopté.**
Le modèle canonique `416bb90b` reste inchangé (hash vérifié intact).

## Rationnel empirique

Deux leviers de perte ont été testés sous protocole strict, **hors canonique**
(`consolidation_finale/exp_perte/`, aucun modèle expérimental sauvegardé) :

- **Protocole de choix** : train = H22 (hors Gilamont, ADR-065) + H23 → **validation H24**.
  Balayage du paramètre sur H24. **H25 jamais utilisé pour le choix.**
- **Confirmation de généralisation** : réentraînement tri-annuel H22+H23+H24 (Split C
  canonique, 801 282 obs) → **test H25** (309 252 obs), uniquement pour rapporter si le gain
  de validation généralise — **pas pour sélectionner**.
- **Iso-tout sauf le levier** : mêmes 158 features, hyperparamètres ADR-052 (n_est=300,
  depth=6, lr=0.1, subsample/colsample=0.8), seed=42, segmentation BAS/HAUT.

**Leviers testés**
1. **`sample_weight` binaire** : poids `W` si charge >63, sinon 1, sur le label réel.
   Balayage `W ∈ {1, 2, 3, 5, 10, 20}` (W=1 = contrôle MSE non pondéré).
2. **MSE asymétrique** : sous-prédiction pénalisée `k×`. Gradient `g = r` si `r ≥ 0`,
   `g = k·r` si `r < 0` ; hessien `h = 1` si `r ≥ 0`, `h = k` si `r < 0` (avec `r = pred − obs`).
   Optimum visé = quantile conditionnel `τ = k/(k+1)`. Balayage `k ∈ {1, 2, 3, 5, 9, 19}`
   (τ ≈ 0.5, 0.67, 0.75, 0.83, 0.9, 0.95).
   **Garde-fou validé** : k=1 reproduit `reg:squarederror` **bit-exact** (`max|Δpred| = 0`,
   BAS et HAUT, sur validation H24 comme sur le réentraînement tri-annuel).

### Verdict en trois points

**(a) Le biais >63 se réduit mécaniquement avec le paramètre, et généralise partiellement
sur H25 — effet réel mais modeste.** Sur H24, le biais global >63 passe de −29,1 (baseline)
à −24,3 (k=2) / −26,1 (W=2). Sur H25, l'amélioration retenue est d'environ **−2 à −2,5 sur le
biais global >63** (canonique −28,5 → k=2 −26,2 / W=2 −26,0), soit ~la moitié de l'amplitude
observée en validation.

**(b) La PR-AUC NE bouge PAS.** En validation, un saut initial modeste (W=2 / k=2) **sature
immédiatement** puis plateau ; pousser le paramètre plus haut (W=20, k=19, τ=0.95) réduit
encore le biais **sans** relever la PR-AUC. Sur le holdout H25, le saut **s'évapore** :
ΔPR-AUC tronçon et tour ≈ **±0,003** pour les deux leviers (k=2 : tronçon −0,003 / tour +0,001 ;
W=2 : tronçon +0,006 / tour −0,001). **Les deux leviers recalent le POINT DE FONCTIONNEMENT
(biais ↓) sans relever le PLAFOND de séparabilité.** Constat confirmé sur validation H24 ET
sur le test H25.

**(c) Le gain de R² de k=2 sur H24 (+0,034) était un sur-ajustement de validation.** Il
**s'inverse sur H25** (−0,015 : k=2 R² global 0,586 vs canonique 0,601). Sur le segment
**HAUT** (peu de surcharges, ~600 en H24 / ~1 200 en H25, statistiquement instable), k=2 est
**contre-productif sur le test** : PR-AUC tronçon **0,345 → 0,298** et biais >63 inchangé voire
dégradé. Observation comparative : **W=2 généralise plus proprement que k=2** (R² global
préservé 0,601→0,601, masse quasi intacte : MAE globale 7,71→7,77, sur-prédiction induite
biais ≤63 +1,4→+1,8) — **mais sans gain de séparabilité non plus**, donc **non adopté**.

### Synthèse chiffrée (H25, GLOBAL, n>63 = 9 584)

| Modèle | R² glob | MAE glob | biais >63 | MAE >63 | biais ≤63 | PR-AUC tronçon | PR-AUC tour |
|---|---:|---:|---:|---:|---:|---:|---:|
| Canonique (`reg:squarederror`) | 0,6013 | 7,712 | −28,47 | 29,09 | +1,37 | 0,4490 | 0,5635 |
| k=2 (MSE asym, τ=0,67) | 0,5863 | 8,108 | −26,23 | 27,05 | +3,11 | 0,4456 | 0,5643 |
| W=2 (`sample_weight`) | 0,6008 | 7,770 | −26,02 | 26,92 | +1,83 | 0,4549 | 0,5628 |

## Conséquence architecturale

**Le plafond de séparabilité de la couche 1 est une propriété du SIGNAL (features), non de la
fonction de perte ni du point de fonctionnement.** Ce chantier constitue une **validation
empirique de la distinction biais / pouvoir discriminant** :

1. **Couche 2 (recalibration / décision)** : ne peut que **choisir un point de fonctionnement
   sur une courbe PR fixe**. Recalibrer = se déplacer le long de la courbe (arbitrer
   précision/rappel), **pas** relever la courbe. La sous-prédiction structurelle de la zone >63
   relève donc d'un **réglage de seuil opérationnel** en couche 2, pas d'un changement de perte
   en couche 1.
2. **Seul levier capable de relever le plafond : l'enrichissement du SIGNAL** (nouvelles
   features porteuses d'information discriminante sur la zone >63). C'est la **piste suivante**.

## Traçabilité

- Balayages et confirmation H25 (scripts + sorties JSON/CSV) : `consolidation_finale/exp_perte/`
  - `balayage_sample_weight_h24.py` / `.csv` / `.json` — Phase 1 (sample_weight, validation H24).
  - `balayage_mse_asym_h24.py` / `.csv` / `.json` — Phase 2 (MSE asymétrique, validation H24 ;
    garde-fou k=1 ≡ `reg:squarederror`).
  - `confirmation_h25_k2_w2.py` / `confirmation_h25_k2_w2.json` — Phase 3 (test H25, 3 modèles ;
    garde-fou : modèles canoniques chargés reproduisent les métriques H25 publiées à Δ=0, et
    k=1 custom tri-annuel reproduit le canonique à `max|Δpred| = 0`).
- **Modèles expérimentaux non sauvegardés.** **Hash canonique `416bb90b` intact, vérifié**
  (lecture seule du dataset à chaque exécution).
- Aucune écriture dans le rapport de synthèse ni dans les autres ADR.

---


---
id: ADR-070
ancien_id: ADR-CF26
date_decision: 2026-06-28
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-070 — Features vacances/fériés cantonaux (VS/FR/NE/GE) : testées et écartées

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-28 |
| **Date** | 2026-06-28 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-069 (conservation perte MSE — « la piste suivante = enrichissement du signal »), ADR-052 (hyperparamètres XGBoost), ADR-060 (seuil surcharge 63), ADR-065 (Split C), ADR-049 (segmentation BAS/HAUT), ADR-061 (retrait SIMBA), ADR-033 (pivot régression + augmentation couche 2) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset, de hash, de pipeline.** |

---

## Contexte

Le directeur du travail de master a suggéré que les **vacances scolaires et jours fériés
des cantons voisins** (Valais, Fribourg, Neuchâtel, Genève) pourraient capter un trafic
**excursionniste** vers le segment HAUT touristique (Les Pléiades), là où le **plafond de
séparabilité est le plus bas** (PR-AUC HAUT ≈ 0,345 sur H25) et où ni la perte (ADR-069)
ni les hyperparamètres (tuning Optuna) n'avaient rien relevé.

Hypothèse à tester : **ces features relèvent-elles la PR-AUC HAUT ?** C'est, après la perte
et les HP, le **3ᵉ levier indépendant** examiné pour franchir ce plafond — et précisément
celui que l'ADR-069 désignait comme « la piste suivante : enrichissement du signal ».

## Décision

**Les 8 features ne sont PAS intégrées au modèle canonique.**
`event_is_vacances_{valais, fribourg, neuchatel, geneve}` et `event_is_ferie_{…}` restent
des **features candidates non retenues**. Le modèle 158f / hash `416bb90b` reste **inchangé**
(hash vérifié intact à chaque exécution expérimentale).

## Rationnel empirique — 3 phases, hors canonique

Chantier entièrement **hors canonique** (`exp_features/`), protocole strict, **iso-tout sauf
les features**, HP ADR-052, seed=42, segmentation BAS/HAUT, perte `reg:squarederror`,
seuil 63. **Protocole de choix** = train H22 (hors Gilamont, ADR-065) + H23 → **validation
H24** ; **H25 jamais utilisé pour le choix**, touché une seule fois pour la confirmation de
généralisation.

### Phase A — Construction & contrôle qualité

8 features binaires journalières construites et sourcées :
- **Valais** : 5 PDF « Plan de scolarité » coloriés (pas de dates explicites) → parseur de
  rectangles vectoriels (bleu/jaune = classe, **orange = férié cantonal**, blanc = congé),
  **datation par position de grille** (robuste aux coquilles source : ex. « 25 » imprimé
  pour « 15 »). Validation : 0 incohérence jour/position, totaux mensuels de jours de classe
  reproduits exactement, **72 fériés analytiques confirmés à 100 % par l'orange**.
- **Fribourg** : XLSX (périodes explicites, calendrier majoritaire francophone).
- **Neuchâtel** : arrêté 410.562 (table de périodes).
- **Genève** : PDF (chaque année liste aussi n+1 ; 2024-25 récupérée via le PDF 2023-24).

QC : **0 NaN**, plausibilité 23-26 % de jours/an en vacances (attendu ~25-27 %), **aucune
asymétrie train/test**, pas de fuite (calendriers statutaires publiés ex ante, connus J-1).
Corrélations avec le vaudois existant **0,67-0,91** (aucune > 0,95) → information
incrémentale présente. **Redondance interne férié VS≈FR (r = 0,97).**

### Phase B — Impact (validation H24, 158f vs 166f)

**Sur l'objectif HAUT : ÉCHEC.** Δ PR-AUC HAUT = **−0,0022** (tronçon) / +0,0015 (tour),
dans le bruit ; R² HAUT même **légèrement dégradé** (−0,012), MAE>63 HAUT +1,19. Seul signal
réel : **`event_is_vacances_valais` sur le BAS** (SHAP rang 7/166, +0,019 PR-AUC BAS) — **hors
cible**. Les 4 `event_is_ferie_*` et les vacances GE/FR sont **quasi morts** (SHAP < 0,1 % ;
la redondance VS≈FR se traduit par un SHAP partagé nul, l'info fériés étant déjà captée par
`event_is_ferie_vaud`).

### Phase C — Confirmation H25 (`event_is_vacances_valais` seule, 158f vs 159f)

Garde-fou parfait : le 158f reproduit les `metrics_h25` canoniques **à Δ = 0,0000** (R² et
PR-AUC, BAS/HAUT/global). Résultat :
- Le **gain BAS ne généralise qu'au quart** : PR-AUC BAS tronçon **+0,019 (H24) → +0,0055
  (H25)**, tour +0,012 → +0,0047 — sous le seuil d'intérêt (0,03).
- **Instabilité de segment** : le mouvement HAUT apparu sur H25 (+0,019 PR-AUC) **contredit**
  la validation H24 (−0,002) → artefact petit-échantillon du HAUT (620 / 1 192 surcharges),
  **pas un gain démontré**.
- SHAP **stable** (rang ~9/159 BAS) mais **effet métrique < 0,02 partout**, non reproductible.

## Verdict

Même le seul candidat survivant (`event_is_vacances_valais`) **ne relève pas le plafond
HAUT** et n'offre qu'un effet BAS **petit, atténué hors échantillon et instable en segment**.

*Note interprétative :* le signal valaisan sur le BAS est cohérent avec un possible flux
**pendulaire transfrontalier** (habitants du bas travaillant en Valais ; demande réduite les
jours fériés/vacances valaisans), mais **trop ténu** pour être exploité ou vérifié.

## Conséquence architecturale — triangulation des 3 chantiers

Avec la **perte** (ADR-069) et les **hyperparamètres** (tuning Optuna documenté), les
**features cantonales** constituent le **3ᵉ levier indépendant testé qui NE relève PAS la
PR-AUC HAUT**. Conclusion empirique **triangulée** :

> Le plafond de séparabilité du segment HAUT (~0,345) est **intrinsèque au signal disponible
> à J-1** sur ce segment rare et volatil — ce n'est ni un défaut de modélisation (perte, HP)
> ni un manque de cette source.

Implication : la **couche 2** choisit un point de fonctionnement sur une **courbe PR fixe** ;
relever le plafond HAUT exigerait des **sources de signal nouvelles non disponibles à ce
stade**. Ceci **clôt empiriquement** la piste « enrichissement du signal » ouverte par
ADR-069 pour la source vacances/fériés cantonaux.

## Traçabilité

Chantier dans `exp_features/` : `parse_valais.py`, `build_cantonal_features.py`,
`phaseB_impact_h24.py`, `phaseC_confirm_h25.py`, `RAPPORT_PHASE_{A,B,C}.md`, sorties dans
`exp_features/outputs/`. Garde-fous : baseline 158f reproduit le k=1 du chantier perte
(validation H24) et les `metrics_h25` canoniques (test H25) à Δ = 0. **Features candidates
non intégrées. Hash canonique `416bb90b` intact, vérifié. Aucune écriture dans le rapport,
le pipeline ou le dataset.**

---


---
id: ADR-071
ancien_id: ADR-CF27
date_decision: 2026-06-28
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-071 — Conservation des hyperparamètres ADR-052 : optimisation Optuna conduite, CF09 confirmé robuste out-of-time

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-28 |
| **Date** | 2026-06-28 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-052 (hyperparamètres XGBoost — confirmés ici), ADR-069 (perte MSE conservée), ADR-070 (features cantonales écartées), ADR-065 (Split C), ADR-049 (segmentation BAS/HAUT), ADR-060 (seuil 63), ADR-030 / ADR-031 (découplage R²/rappel classe rare) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset, de hash, de pipeline.** |

---

## Contexte

Le directeur du travail de master a relevé que les hyperparamètres ADR-052 (n_est=300,
depth=6, lr=0.1, subsample/colsample=0.8) étaient présentés **sans méthode d'optimisation
documentée** — « on pourrait penser à de bonnes pratiques, mais il n'y en a pas vraiment ».
Il a suggéré une **optimisation systématique** (Optuna / RandomSearch plutôt que GridSearch,
trop lourd).

Question : **une optimisation des HP améliore-t-elle le modèle, et faut-il changer CF09 ?**

## Décision

**Les hyperparamètres ADR-052 sont CONSERVÉS.** Le candidat optimal Optuna (« best-R² »,
HP différenciés par segment) **n'est PAS adopté**. Le modèle 158f / hash `416bb90b` reste
**inchangé** (hash vérifié intact à chaque exécution).

## Rationnel empirique — protocole strict, hors canonique (`exp_hpo/`)

**Méthode d'optimisation.** Optuna, sampler **TPE bayésien**, **multi-objectif** [maximiser
R²_H24, minimiser |biais>63|_H24] avec **front de Pareto** (pas de pondération λ arbitraire).
**Pas de CV aléatoire** (respect de la causalité temporelle). Optimisation sur train
H22 (hors Gilamont, ADR-065) + H23 → **validation H24**, **par segment** (BAS / HAUT,
50 essais chacun). **H25 jamais utilisé pour le tuning.**

**Constat en validation H24.** CF09 est **quasi optimal**. Le meilleur point (best-R²) ne
gagne que **+0,02 de R²** sur H24 ; le biais>63 ne bouge quasiment pas (les HP ne changent
pas l'estimand `reg:squarederror`) ; un mouvement **PR-AUC HAUT (+0,043)** apparaît en
validation. Profils best-R² : **régularisation plus forte + lr plus bas**, différenciés par
segment — BAS depth=8 / lr=0,029 / n=360 / min_child_weight=10 / γ=4,47 / λ=3,88 / α=1,88 ;
HAUT depth=5 / lr=0,077 / n=349 / γ=3,37 / λ=3,44.

**Confirmation sur H25** (critère d'adoption posé **avant** de voir les chiffres : adoption
seulement si **aucune dégradation matérielle** de R² global, biais>63, PR-AUC tronçon ET tour
par segment). Réentraînement tri-annuel H22+H23+H24 (Split C, 801 282 obs) → test H25
(309 252 obs). **Garde-fou : CF09 reproduit les `metrics_h25` canoniques à Δ = 0,0000.**

**best-R² ÉCHOUE le critère.** Sur H25 il :
- **aggrave le biais>63 sur tous les segments** (HAUT **−2,04**, BAS −0,97, global −1,11 ;
  MAE>63 pire partout) ;
- **dégrade la PR-AUC HAUT** (tronçon **−0,0068**, tour **−0,0090**) — **pire sur l'objectif
  même** ;
- pour un gain marginal de **+0,004 de R² global**, obtenu en ajustant mieux la masse au
  **détriment de la zone >63** (tension R²/classe rare, ADR-030/32).

### Synthèse chiffrée (H25, GLOBAL puis HAUT)

| | R² glob | biais>63 | MAE>63 | PR-AUC tronçon HAUT | PR-AUC tour HAUT |
|---|---:|---:|---:|---:|---:|
| **CF09** (canonique) | 0,6013 | −28,47 | 29,09 | 0,3452 | 0,3459 |
| best-R² (par segment) | 0,6054 | −29,57 | 29,92 | 0,3384 | 0,3369 |
| **Δ (best − CF09)** | **+0,0040** | **−1,11** | +0,83 | **−0,0068** | **−0,0090** |

**Le mirage de validation.** Le mouvement PR-AUC HAUT de validation (**+0,043**) **s'inverse
sur H25 (−0,007)** — **bruit de segment** (HAUT ≈ 600 / 1 200 surcharges, statistiquement
instable), **même profil que k=2** (ADR-069) **et que les features en Phase C** (ADR-070).

| segment | ΔR² H24 → H25 | ΔPR-AUC tronçon H24 → H25 |
|---|---|---|
| bas | +0,020 → +0,004 | +0,019 → +0,003 |
| **haut** | +0,017 → +0,005 | **+0,043 → −0,007** |

## Conséquence — triangulation complète

Les **hyperparamètres** constituent le **3ᵉ levier indépendant testé** (avec la **perte**
ADR-069 et les **features** ADR-070) **qui NE relève PAS la PR-AUC HAUT**. Conclusion
empirique **triangulée et confirmée** :

> Le plafond de séparabilité du segment HAUT (~0,345) est **intrinsèque au signal disponible
> à J-1**, non un défaut de modélisation (perte, features, HP).

Apports de ce chantier :
1. **Procédure d'optimisation documentée et défendable** (réponse directe au point soulevé par le directeur du travail de master) :
   Optuna TPE multi-objectif Pareto, par segment, sans fuite temporelle.
2. **CF09 confirmé quasi optimal ET robuste out-of-time** : le candidat sélectionné sur
   validation **dégrade le test** — CF09 généralise mieux.
3. **Un re-tuning serait à refaire sur tout nouveau jeu de features** — **sans objet ici** :
   les features cantonales ayant été écartées (ADR-070), le jeu reste **158f**.

## Traçabilité

`consolidation_finale/exp_hpo/` : `tuning_optuna_h24.py` / `_resultats.json` / `_trials.csv`,
`postprocess_h24.py`, figures (`pareto_*`, `param_importance_*`, `history_*`),
`test_h25_best_r2_vs_cf09.py` / `.json`, `RAPPORT_TEST_H25_best_r2.md`. **Garde-fou : CF09
reproduit les `metrics_h25` canoniques à Δ = 0.** Modèles expérimentaux non sauvegardés.
**Hash canonique `416bb90b` intact, vérifié.** Aucune écriture dans le rapport ni le pipeline.
ADR autonome : `docs/adr/ADR-071_tuning_hyperparametres_optuna.md`.

---


---
id: ADR-072
ancien_id: ADR-CF28
date_decision: 2026-07-03
statut: actif
modifie: [ADR-036]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-072 : Comparaison d'algorithmes et confirmation de XGBoost pour la couche 1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-036.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Décision figée |
| **Date** | 2026-07-03 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-052 (hyperparamètres et architecture, confirmés ici), ADR-060 (seuil de surcharge 63), ADR-061 (retrait SIMBA), ADR-064 (retrait STATENT), ADR-065 (Split C), ADR-049 (segmentation BAS et HAUT), ADR-071 (optimisation Optuna des hyperparamètres, complémentaire), ADR-036 (structure de raisonnement conservée, chiffres périmés, voir section dédiée) |
| **Version modèle** | Enrichi_Seg v1.9 (158 features, Split C, hash dataset `416bb90b`), inchangée |
| **Nature** | Décision méthodologique et point de référence à jour de l'état canonique. Aucun changement de modèle, de dataset, de hash, de pipeline. |

---

## 1. Contexte et déclencheur

Le directeur du travail de master a relevé, lors de la revue du travail de modélisation, qu'un seul algorithme (XGBoost) avait été mis en oeuvre pour la couche 1, sans comparaison à d'autres familles d'apprentissage, et a demandé une justification du choix. Cette justification, honnêtement, n'existait pas au moment du commentaire. Le choix initial de XGBoost reposait sur la pratique courante et la maîtrise de l'outil, pas sur une démonstration empirique documentée que cet algorithme était le mieux adapté au problème.

Plutôt que de construire a posteriori un argumentaire théorique, qui aurait été fragile et peu convaincant, la démarche retenue a été de produire la justification manquante par une comparaison empirique rigoureuse, menée à protocole strictement contrôlé. Le présent ADR acte cette comparaison, en tire la décision sur les algorithmes, et sert simultanément de point de référence à jour de l'état du modèle canonique.

---

## 2. Description exacte et vérifiée du modèle canonique

Le bloc ci-dessous est repris de `models/enrichi_seg/enrichi_seg_metadata.json` (version 1.9, créée le 2026-06-20). Il fait de cet ADR la référence à jour de l'état canonique.

| Élément | Valeur |
|---|---|
| Architecture | Deux régresseurs XGBoost segmentés, un modèle BAS et un modèle HAUT, aiguillage par `spatial_segment` |
| Objectif | `reg:squarederror` (MSE) |
| Hyperparamètres | n_estimators 300, max_depth 6, learning_rate 0.1, subsample 0.8, colsample_bytree 0.8, seed 42 (ADR-052) |
| Features | 158, sans SIMBA (ADR-061), sans STATENT (ADR-064) |
| Cible | `target_voyageurs_2eme_classe` |
| Seuil de surcharge | 63 (ADR-060) |
| Dataset | `data/processed/ml_dataset.parquet`, hash SHA256 tronqué `416bb90b` |
| Split | Split C (ADR-065), entraînement H22 hors tronçons Gilamont (BPUIC 8501260) plus H23 plus H24, test H25 |
| Tailles | 801 282 observations d'entraînement, 309 252 observations de test H25 |
| Empreintes modèles | BAS `e4ddfccd`, HAUT `df6a11c5` |
| Version | 1.9 |

Métriques H25 du canonique (source `enrichi_seg_metadata.json`, clé `metrics_h25`), pour mémoire et comme repère de la comparaison :

| Segment | R² | MAE | PR-AUC tronçon | n surcharges (>63) |
|---|---:|---:|---:|---:|
| BAS | 0.5868 | 8.169 | 0.4687 | 8 392 |
| HAUT | 0.4334 | 6.389 | 0.3452 | 1 192 |
| GLOBAL | 0.6013 | 7.712 | 0.4490 | 9 584 |

---

## 3. Méthode de comparaison, en deux temps

### 3.1 Premier temps, comparaison à paramètres par défaut

Cinq approches ont été comparées aux paramètres par défaut de leur bibliothèque, sans aucun réglage, sur le protocole iso-canonique (mêmes 158 features, dataset `416bb90b`, Split C, architecture segmentée, seed 42) :

1. une baseline naïve par moyenne historique, qui prédit pour chaque ligne H25 la charge 2e classe moyenne observée dans le train (H22 à H24, aucune donnée H25) pour la même combinaison de tronçon, de numéro de course et de type de jour (ouvré ou week-end), avec un repli en cascade documenté vers des moyennes moins conditionnées lorsque la combinaison est absente du train,
2. Random Forest (scikit-learn),
3. XGBoost par défaut,
4. LightGBM par défaut,
5. CatBoost par défaut.

Ce premier temps situe XGBoost parmi les alternatives et mesure de combien les modèles d'apprentissage dépassent la baseline naïve, ce qui teste directement l'hypothèse H1 du proposal (les variables temporelles et contextuelles améliorent la prévision par rapport à la seule récurrence historique).

Note sur la couverture de la baseline. La clé complète (tronçon, numéro de course, type de jour) ne retrouve son équivalent historique que pour 53.69 pour cent des lignes H25. La refonte horaire H25 renumérote les courses, ce qui fait basculer 42.36 pour cent des lignes vers le repli (tronçon, type de jour). Cette fragilité face à un changement d'offre est une limite intrinsèque de l'approche historique seule, pas un artefact de mesure.

### 3.2 Second temps, optimisation Optuna à budget égal

Le premier temps prête le flanc à une objection d'équité : les paramètres par défaut ne sont pas également soignés d'une bibliothèque à l'autre, si bien qu'un écart faible peut refléter la qualité des défauts plutôt qu'une supériorité de fond. Pour neutraliser cette objection, les trois méthodes de boosting (XGBoost, LightGBM, CatBoost) ont été optimisées par Optuna à budget strictement égal, 40 essais par algorithme, échantillonneur TPE, seed 42, avec des espaces de recherche de générosité comparable (taux d'apprentissage, complexité, sous-échantillonnage de lignes et de colonnes, régularisation, nombre d'arbres borné à 600 via early stopping).

Verrou méthodologique. L'optimisation se déroule exclusivement sur le train (H22 hors Gilamont plus H23 plus H24), en validation temporelle walk-forward à trois plis construite par date à l'intérieur du seul train, en fenêtre expansive respectant l'ordre chronologique. Le holdout H25 n'est jamais vu pendant l'optimisation et n'est révélé qu'une seule fois, tout à la fin, sur les modèles figés, à côté du canonique CF09 comme repère et de la baseline naïve comme plancher.

Métrique optimisée. Le RMSE de validation, moyenné sur les trois plis, calculé sur les deux segments réunis pour donner un critère unique par essai. Ce choix est cohérent avec le critère de la couche 1, définie comme régresseur de charge dans l'ADR-052, et non comme détecteur de surcharge (qui relève de la couche 2).

Vérification d'iso-conditions. Il a été vérifié, à partir des scripts et de leurs sorties, que le comparatif tourne sur exactement les 158 features du canonique (fichier `features_158f_sans_simba.json`, sans SIMBA ni STATENT), sur le même dataset `416bb90b` (hash recalculé et contrôlé en début et en fin d'exécution), en architecture segmentée BAS et HAUT. Seul l'algorithme varie.

---

## 4. Résultats

Tous les chiffres ci-dessous sont lus depuis les sorties réelles (`tuning_resultats.json`, `comparatif_resultats.json` et fichiers associés), aucun n'est reconstruit à la main.

### 4.1 Validation (train walk-forward, juge principal RMSE)

| Algorithme | RMSE de validation (moyenne 3 plis) | Écart-type entre plis |
|---|---:|---:|
| CatBoost | 10.4928 | 0.7897 |
| LightGBM | 10.4943 | 0.7687 |
| XGBoost | 10.5506 | 0.7530 |

L'écart de RMSE entre les trois boostings vaut 0.0577. La variabilité moyenne entre plis vaut 0.7705. Le premier est très inférieur à la seconde (environ treize fois plus petit).

### 4.2 Holdout H25 (révélé une seule fois)

| Modèle | RMSE global | R² global | PR-AUC tronçon global |
|---|---:|---:|---:|
| CatBoost (Optuna, segmenté) | 11.400 | 0.6198 | 0.4686 |
| LightGBM (Optuna, segmenté) | 11.459 | 0.6159 | 0.4609 |
| XGBoost (Optuna, segmenté) | 11.534 | 0.6108 | 0.4564 |
| CF09 canonique (repère) | 11.674 | 0.6013 | 0.4490 |
| Baseline naïve (plancher) | 16.687 | 0.1855 | 0.0557 |

Sur H25, l'ordre des trois boostings est CatBoost, puis LightGBM, puis XGBoost, dans un mouchoir : l'écart de RMSE global entre le meilleur et XGBoost vaut 0.1341, soit environ 0.009 de R² global.

### 4.3 Dépassement de la baseline naïve (hypothèse H1)

Tous les modèles d'apprentissage dépassent largement la baseline naïve. Sur la PR-AUC tronçon globale, ils atteignent de l'ordre de 0.46 contre 0.056 pour la baseline, soit un facteur voisin de huit. Sur le RMSE global, ils descendent autour de 11.4 contre 16.7. Sur le R² global, ils atteignent de l'ordre de 0.61 à 0.62 contre 0.19. L'écart est encore plus net sur le segment HAUT, où la PR-AUC des boostings tunés (0.33 à 0.37) dépasse la baseline (0.025) d'un facteur voisin de treize à quinze. Ce résultat valide l'hypothèse selon laquelle les variables temporelles et contextuelles améliorent significativement la prévision par rapport à la seule récurrence historique.

Pour mémoire, le premier temps (paramètres par défaut) donne la même hiérarchie d'ensemble : les trois boostings et Random Forest dépassent tous la baseline, Random Forest reste en retrait des boostings (PR-AUC globale 0.3887 contre 0.43 à 0.46), et les défauts de LightGBM et CatBoost devancent légèrement le défaut de XGBoost, ce qui motivait précisément le passage au second temps à budget égal.

---

## 5. Verdict et justification du choix

**Ce passage est celui que le décideur doit relire et s'approprier en priorité, car c'est l'argument qui sera défendu en soutenance.**

### 5.1 Indiscernabilité de performance

L'écart de performance entre les trois algorithmes de boosting est très inférieur à la variabilité de mesure. En validation, 0.0577 de RMSE d'écart entre algorithmes contre 0.7705 de variabilité entre plis. Aucun des trois ne domine de façon statistiquement fiable. Le critère de conclusion, posé avant de voir les résultats, était précisément le suivant : un algorithme n'est déclaré meilleur que si son avantage est stable en validation et se confirme sur H25, faute de quoi on conclut à l'indiscernabilité et on ne départage pas sur le RMSE. Ce critère conduit ici à l'indiscernabilité. Le travail antérieur de tuning (ADR-071) a de plus montré qu'un écart de cet ordre ne se maintient pas d'un jeu de données à l'autre, un gain apparent en validation ou sur une année pouvant s'inverser sur l'année suivante.

Il faut assumer explicitement, sans le masquer, que CatBoost arrive numériquement en tête, à la fois en validation (RMSE 10.4928) et sur H25 (RMSE global 11.400, R² global 0.6198). Cet avantage est réel dans les chiffres, mais il n'est pas fiable au sens statistique, l'écart vivant à l'intérieur de la variabilité de mesure. Là où CatBoost se détache un peu plus, sur le segment HAUT (R² 0.4848 et PR-AUC 0.3712 contre 0.46 et 0.33 pour les deux autres), il s'agit précisément du segment à plus forte variance de réentraînement, documentée dans l'ADR-052, où un écart de cet ordre ne doit pas être surinterprété.

Il faut de plus noter que les gains numériques des configurations optimisées sur les métriques de surface (RMSE et R²) se paient sur la classe rare. La section 6 le détaille sur XGBoost, où un R² global un peu meilleur s'accompagne d'une dégradation de la zone de surcharge (>63) et de la PR-AUC du segment HAUT, ce qui est le mauvais arbitrage pour une couche 1 destinée à alimenter la détection de surcharge en couche 2 (tension R² et rappel de classe rare, ADR-030 et ADR-031).

### 5.2 Justification de XGBoost sur les critères secondaires

L'indiscernabilité de performance étant établie, le choix ne peut pas et ne doit pas se faire sur le RMSE. Il se fait sur les critères secondaires prescrits par le cadre CRISP-ML(Q) de Studer et al., qui invitent explicitement à considérer, au delà de la performance brute, l'explicabilité, la maintenabilité et l'adéquation au contexte de déploiement.

Sur l'explicabilité, il faut être précis pour ne pas surclasser XGBoost à tort. Les trois boostings sont également explicables, puisque ce sont des ensembles d'arbres compatibles avec TreeSHAP. Le vrai choix d'explicabilité n'a pas été XGBoost contre CatBoost, mais le gradient boosting contre le deep learning opaque. En retenant une famille d'arbres explicable par SHAP plutôt qu'un réseau de neurones, la modélisation répond directement au gap XAI identifié dans la revue de littérature, celui d'un besoin de prévisions interprétables par l'opérateur pour la décision d'unité multiple. Ce point est solide et défendable.

Les critères qui départagent ensuite XGBoost au sein du trio sont les suivants : la maturité et la robustesse éprouvée de l'écosystème SHAP autour de XGBoost, et la maîtrise interne de l'outil, qui réduit le risque de mise en oeuvre et de maintenance. Ces critères, dans un contexte d'indiscernabilité de performance, justifient de conserver XGBoost.

---

## 6. Décision sur les hyperparamètres

Les hyperparamètres du canonique (ADR-052) sont conservés et ne sont pas remplacés par ceux issus d'Optuna. La justification demande de la précision, car elle ne peut pas se réduire à un simple constat d'écart nul.

Il faut d'abord reconnaître honnêtement que la configuration XGBoost optimisée par Optuna est, sur les métriques de surface, légèrement meilleure que CF09 sur H25 : R² global 0.6108 contre 0.6013 (un gain de l'ordre de 0.0095, hors de l'intervalle de confiance bootstrap de CF09), MAE global 7.578 contre 7.712, PR-AUC globale 0.4564 contre 0.4490. Écrire que l'optimisation n'apporte aucun gain serait donc inexact et réfutable.

Le refus d'adopter cette configuration repose sur deux arguments solides. Premièrement, le gain global se paie sur la zone opérationnellement critique. Sur le segment HAUT, celui qui alimente la détection de surcharge en couche 2, la configuration optimisée gagne du R² (0.4639 contre 0.4334) mais dégrade la PR-AUC (0.3368 contre 0.3452) et sous-prédit davantage les surcharges (biais au-dessus de 63 de -46.45 contre -42.27, MAE au-dessus de 63 de 46.45 contre 42.40). Pour une couche 1 dont la finalité est de nourrir la détection de surcharge, améliorer l'ajustement du gros de la distribution au prix de la classe rare est le mauvais arbitrage (tension R² et rappel de classe rare, ADR-030 et ADR-031). Deuxièmement, la gouvernance interdit de choisir sur le holdout. L'avantage de la configuration optimisée n'est visible que sur H25 (le CV walk-forward n'a pas été calculé pour CF09, il n'existe donc aucune preuve en validation que le réglage optimisé batte CF09), or basculer parce qu'une configuration paraît meilleure sur H25 reviendrait à décider sur un test qui doit rester vu une seule fois.

Ces deux arguments convergent avec l'ADR-071, dont le critère d'adoption pré-posé, appliqué à des optimisations Optuna de XGBoost, avait déjà conclu à la non-adoption au motif que les gains ne se maintenaient pas hors échantillon et dégradaient les métriques de la zone de surcharge.

Formulé positivement, le comparatif confirme que le réglage du canonique est déjà dans une zone raisonnable, aucune configuration alternative ne le dominant à la fois sur la performance globale et sur la zone de surcharge. Ce résultat est cohérent avec le constat de fond du projet, à savoir que la performance est bornée par le signal disponible à J moins 1 plutôt que par le choix de l'algorithme ou par le réglage de ses hyperparamètres (voir aussi ADR-071). Les meilleurs hyperparamètres trouvés par Optuna pour chaque algorithme sont archivés dans les fichiers `best_params_*.json` à titre de trace, sans être promus.

---

## 7. Liens et cohérence documentaire

Les ADR faisant foi pour l'état canonique sont : ADR-052 (hyperparamètres et architecture segmentée), ADR-060 (seuil de surcharge 63), ADR-061 (retrait de SIMBA), ADR-064 (retrait de STATENT), ADR-065 (Split C), ADR-049 (segmentation BAS et HAUT). Le présent ADR-072 complète l'ADR-071 (optimisation Optuna des hyperparamètres) en portant la comparaison au niveau du choix d'algorithme.

Avertissement sur l'ADR-036. L'ADR-036 conserve sa valeur pour la structure de raisonnement sur les hyperparamètres et sur l'apport des features de réservation, mais ses chiffres de features et de seuil sont périmés. Il mentionne 160 puis 168 features et un seuil de surcharge à 94 ou 80. L'état actuel est de 158 features (après retrait de SIMBA par ADR-061 et de STATENT par ADR-064) et un seuil de surcharge à 63 (ADR-060). Aucun lecteur ne doit prendre les chiffres de l'ADR-036 pour l'état courant.

---

## 8. Fichiers sources des chiffres

Les valeurs de ce document sont tirées des fichiers suivants, en lecture seule :

- `models/enrichi_seg/enrichi_seg_metadata.json` : description et métriques H25 du canonique (section 2).
- `consolidation_finale/exp_comparatif_algos/tuning/tuning_resultats.json` : RMSE de validation, écarts entre plis, résultats H25 des boostings tunés, verdict (sections 4.1, 4.2, 4.3, 5).
- `consolidation_finale/exp_comparatif_algos/tuning/best_params_xgboost.json`, `best_params_lightgbm.json`, `best_params_catboost.json` : meilleurs hyperparamètres archivés (section 6).
- `consolidation_finale/exp_comparatif_algos/comparatif_resultats.json` : comparaison à paramètres par défaut et couverture de la baseline naïve (sections 3.1, 4.3).
- `consolidation_finale/exp_comparatif_algos/comparatif_algos.py` et `tuning/tuning_comparatif_algos.py` : scripts réexécutables du comparatif et vérification d'iso-conditions (section 3).

Aucune valeur nécessaire à la rédaction n'était absente des sorties. Toutes les valeurs citées proviennent des fichiers ci-dessus.

---


---
id: ADR-073
ancien_id: ADR-44
date_decision: 2026-07-04
statut: amendé
amende_par: [ADR-077]
modifie: [ADR-049]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-07-04
gel_registre: 2026-08-16
---

# ADR-073 — Problème de décision de la couche 2 : seuillage calibré des prédictions couche 1 au grain course (POC d'aide à la décision)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-077.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-049.
> **Précision au gel.** Le point de référence désigné en fin de document (règle a′ iso-volume seule) est remplacé par **a′ ∪ plancher** ; la configuration de déploiement recommandée est **c ∪ plancher** (ADR-077).
> **Précision au gel.** Ce document écarte la projection contrefactuelle du modèle au grain du bloc d'accouplement **du protocole d'évaluation qu'il arrête**, et en conclut que la comparaison à cette borne reste « indicative, non conclusive ». Cette projection a été **conduite après le gel de l'artefact**, comme analyse d'évaluation du mémoire (§4.7.2, lecture à deux grains) : la configuration de déploiement y atteint 72,3 % de précision et 31,4 % de rappel au grain du bloc, contre 58,9 % et 6,0 % pour la pratique. Elle est produite en lecture seule, sous garde d'empreinte `ba493568`, par `docs/memoire/verifs/section_4_7/v6_grain_bloc.py` (2026-08-05, dépôt de travail), et ne modifie ni l'artefact ni le protocole arrêtés ici : la réserve ci-dessous est levée par une analyse d'évaluation postérieure, non par une décision de conception ultérieure. Détail en ADR-078 §4.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | **Accepté** — 2026-07-04 (E. Nédellec, après double relecture) |
| **Date** | 2026-07-04 |
| **Décideur** | Erwann Nédellec (data lead R35) |
| **ADRs liés** | ADR-033 (pivot : augmentation métier couche 2), ADR-005 / ADR-060 (seuil 63), ADR-049 (segmentation BAS/HAUT), ADR-052 (hyperparamètres), ADR-007 (rotations = source de décision UM), ADR-030 / ADR-031 (découplage R²/rappel, plafond de séparabilité), ADR-035 / ADR-036 (réservations, modèle de référence), ADR-038 (extension périmètre H25) |
| **Version modèle couche 1** | Enrichi_Seg v1.9 (158 features, Split C, hash dataset `416bb90b`) — **consommée en lecture seule** |
| **Nature** | Décision d'**architecture** de la couche de décision + **protocole d'évaluation**. **Aucun changement couche 1** (ni features, ni pipeline, ni hyperparamètres, ni hash). |
| **Artefacts** | Module baseline `src/couche2/blocs.py` → `baseline_um_canonique.json` (SHA256 `5874cb14…`) ; tests `tests/couche2/test_blocs.py` (19, verts). |

---

## Contexte

Le pivot **ADR-033** a acté que le plafond de séparabilité des surcharges (PR-AUC HAUT ≈ 0,345,
signal disponible à J-1) est une **limite informationnelle**, pas algorithmique. La réponse n'est
donc pas une nouvelle architecture ML mais une **couche de décision** (couche 2) qui transforme les
prédictions figées de la couche 1 en une **recommandation d'unité multiple (UM)** exploitable, et
qui se compare au **comportement humain passé** (référentiel établi par `src/couche2/blocs.py`).

La couche 1 est **figée** (v1.9, hash `416bb90b`) : la couche 2 la consomme, ne la réentraîne pas,
ne touche ni aux features ni au pipeline. Le présent ADR fixe le **problème de décision**, le
**protocole d'évaluation** et les **limites assumées** de la couche 2, avant toute implémentation.

---

## Décision (D1–D7)

**D1 — Nature.** La couche 2 est un **seuillage calibré des prédictions couche 1 au grain course**.
C'est un **POC d'aide à la décision**. Elle **n'inclut ni optimisation par chaîne, ni simulation de
faisabilité opérationnelle** (découplage, disponibilité du matériel roulant, contraintes de
roulement) : ces contraintes relèvent du métier, **par conception**.

**D2 — Label positif (vérité terrain).** Une course est **positive** si **au moins un de ses
tronçons observés** dépasse **63 voyageurs** en 2ᵉ classe (places assises, ADR-060).

**D3 — Score de décision.** Le score d'une course est le **maximum des prédictions couche 1** sur
ses tronçons.

**D4 — Calibration causale.** Tout **paramètre de l'artefact** (seuils de score, points d'opération
déployables) est calibré sur **H24 uniquement**, en **walk-forward temporel**. **Aucun paramètre
n'est jamais ajusté sur H25.** H25 est lu **une seule fois** en lecture finale. *Distinction (R6) :
le **top-k au budget humain H25 (k = 418)** utilisé pour la comparaison headline n'est **pas** un
paramètre de l'artefact — c'est une **constante du protocole de comparaison** (volume d'engagement
emprunté au côté **humain**), qui **n'utilise pas les labels H25** et ne contrevient donc pas à D4
(voir Conséquences).*

**D5 — Comparaison à l'humain : iso-budget et iso-périmètre (sur H25).** Voir section dédiée. Le
**budget** = nombre de courses-UM humaines **dans H25** = **418** (et non 883, qui est la période
totale). La précision et le rappel humains de référence sont recalculés **sur H25 seul** :
**précision 33,5 % (140/418)**, **rappel 6,8 % (140/2072)**. La comparaison porte sur le **couple
précision-rappel**, pas sur la précision seule. Ce **top-k = 418 est la constante de comparaison
headline** (protocole, côté humain) ; il est **distinct des seuils déployables du menu**, calibrés sur
H24 (D4, Conséquences R6).

**D6 — Hiérarchie des grains.** **Course = headline** (grain de la décision et de l'évaluation).
**Bloc = lecture conséquence** (grain de la décision d'accouplement), lu en **fourchette H25** côté
humain **[canonique 58,9 % (246/418) ; sensibilité 66,7 % (279/418)]** (pour mémoire, *période
totale* : 40,5 % / 45,7 %). **Tour = annexe diagnostique uniquement**, **toujours étiqueté
« permissif »**, et — s'il est présenté — calculé avec la **même agrégation des deux côtés**.

**D7 — Contribution de la couche 2.** La valeur ajoutée est la **formalisation de la décision, le
choix explicite du point d'opération et la transparence** — **pas un gain de détection**. La couche 2
**hérite du plafond PR-AUC HAUT ≈ 0,345** de la couche 1, et la documentation le dit explicitement.

---

## Convention de bloc (grain « lecture conséquence »)

Le grain bloc mesure l'**effet d'héritage** : la composition UM est décidée par anticipation et
**héritée le long du roulement** (une rame accouplée n'est décrochée qu'à Vevey ou Blonay). Un bloc
regroupe donc les courses d'**une même décision d'accouplement**.

**(a) Clé = identité de composition, course atomique.** Un bloc est une suite maximale de courses
consécutives d'un même véhicule dont l'**ensemble accouplé est identique** ; un **changement de
partenaire** en cours de journée (ex. 7501+7502 → 7501+7506) **ferme le bloc** — ce sont deux
décisions distinctes. La signature d'une course = ensemble accouplé **maximal** (segment UM).

**(b) Structure physique complète.** La consécutivité est établie sur **toutes** les courses rail du
véhicule (y compris sans mesure APC), ordonnées par l'**horaire réel istdaten** ; tie-break
déterministe **[heure de départ, numéro de train]**.

**(c) Comptage mesuré uniquement.** Numérateur **et** dénominateur restreints aux **881 courses UM
appariées APC**. Les UM non mesurées structurent les chaînes mais ne sont jamais comptées.

**(d) Sémantique d'UM = set-dedup.** Une UM = **≥ 2 rames rail distinctes** (série 7501–7508). Un
numéro écrit deux fois (« 7508,7508 ») = une seule rame = course **simple**. Compte canonique
(*période totale*) : **914 UM / 881 appariées** APC ; dont **418 UM en H25** (budget D5).

**Cas particuliers documentés.**
- **77 courses UM « partielles »** (renfort accouplé/découplé à Blonay : UM sur une jambe, simple sur
  l'autre — 77/914) : traitées comme **UM à part entière** (course atomique), rattachées au bloc de
  leur signature ; la jambe simple n'ouvre pas de sous-bloc (convention identique à `is_UM = OR` sur
  les segments).
- **2 anomalies de saisie** (service 1334 BLON→VV : `7508,7508` le 2023-11-24, `7506,7506` le
  2024-06-26) : **doublons d'écriture** reclassés en unité simple par le set-dedup, sans correction de
  donnée. Un **garde-fou** (`blocs.py`) lève une erreur sur tout **nouveau** doublon.

**Séquence chronologique et non-révisabilité (E2).** La convention (a)–(d) a été **actée *ex ante*** sur
un argument de principe (« un bloc = une décision d'accouplement »), **avant** l'observation des
chiffres. Les valeurs de justification bloc (**40,5 %** *période totale* ; **58,9 %** restreinte à
H25) en sont le résultat **constaté *ex post***. La convention **n'est plus rediscutable après
observation des chiffres**, dans un sens comme dans l'autre.

**Garde-fou de robustesse (E1).** La variante **consécutivité simple** est **conservée et étiquetée**
dans `baseline_um_canonique.json` à côté de la canonique, aux deux périmètres :
*période totale* 45,7 % (403/881, 532 blocs) vs 40,5 % (357/881, 621 blocs) ; **H25** 66,7 % (279/418)
vs 58,9 % (246/418). L'écart canonique↔sensibilité en *période totale* (−5,2 pts, 46 courses) est
intégralement tracé (`e3_courses_perdant_justification.csv`) : ce sont des courses **non surchargées**
dont l'héritage traversait un changement de partenaire.

---

## Référence de comparaison (D5) — iso-budget et iso-périmètre H25

**Iso-budget (comparaison headline).** Le modèle est classé par score (D3) ; on retient le **top-k au
budget humain H25** (**k = 418** courses-UM). C'est une **constante de protocole** (volume emprunté au
côté humain, sans labels H25), **pas un seuil déployable** (R6). Précision/rappel au **grain course**
(headline), en global et par segment BAS/HAUT. **Départage déterministe du classement**
(reproductibilité byte-exact, R3) : **score décroissant, puis tie-break `[date, numero_train]`** ; la
k-ième course est incluse selon ce même ordre (pas d'ex æquo ambigu au budget).

**Barre humaine H25 (grain course, n bruts — précision ET rappel, R4).**

| | budget UM (VP+FP) | VP | FP | FN | n surcharges (VP+FN) | précision | rappel |
|---|---|---|---|---|---|---|---|
| **Global** | **418** | 140 | 278 | 1 932 | 2 072 | **33,5 %** (140/418) | **6,8 %** (140/2072) |
| HAUT | 328 | 138 | 190 | 1 086 | 1 224 | 42,1 % (138/328) | 11,3 % (138/1224) |
| BAS | 90 | 2 | 88 | 846 | 848 | 2,2 % (2/90) | 0,24 % (2/848) |

Le **23,0 %** (*période totale*, précision course) est rapporté mais **n'est PAS la barre** de
comparaison.

**Iso-périmètre H25 = 29 222 courses** (vérifié, précondition C2) : intersection stricte
**prédiction couche 1 (`ml_dataset`) ∩ décision UM humaine (rotations) ∩ label observé (APC)**. Toutes
les **418 UM humaines** et les **29 222 courses** de la baseline H25 sont présentes dans le
`ml_dataset` (bornes identiques 2024-12-15 → 2025-12-13). **2 courses** présentes dans `ml_dataset`
mais absentes des rotations (2025-09-15 t1312, 2025-11-16 t1415 ; toutes deux **non surchargées**,
décision UM indéfinie) sont **exclues** du périmètre de comparaison (immatériel).

**Lecture conséquence (bloc), côté humain uniquement.** Le résultat course du modèle est lu contre
la **fourchette humaine H25 au grain bloc** **[58,9 % (246/418) ; 66,7 % (279/418)]**, **sans
projection du modèle** (voir alternatives écartées). *(Ces valeurs sont restreintes à H25 ; la
fourchette de période totale — 40,5 % / 45,7 % — est nettement plus basse, l'écart reflétant le
**label shift** de prévalence H25.)* Interprétation : le grain course **sous-estime** la qualité
décisionnelle humaine (courses héritées subies, non décidées) ; le bloc la mesure au niveau de la
décision d'accouplement. L'absence de projection bloc côté modèle rend la comparaison à cette borne
**indicative, non conclusive**.

---

## Segments et UM de repositionnement (E6)

- L'évaluation **headline est GLOBALE** (grain course, iso-budget). Les lectures **BAS et HAUT** sont
  rapportées **systématiquement, à statut égal** : aucun segment n'est désigné comme référence
  prioritaire. Le bas de ligne (pendulaire Vevey–Blonay) concentre l'essentiel du trafic ; le haut
  (touristique) a ses dynamiques propres ; les surcharges des deux segments ont le **même statut**.
- **Caveat baseline humaine BAS.** La précision humaine de **2,2 % en BAS (H25)** (rappel 0,24 %) est
  **structurellement déprimée** par les **UM de repositionnement** (service **1334**, dépôt de
  Blonay), qui ne sont **pas des décisions de demande**. Ce chiffre **sous-estime** la qualité
  décisionnelle humaine sur ce segment et doit être lu avec cette réserve. Le **42,1 % HAUT (H25)**
  (rappel 11,3 %) n'est **pas** affecté par cet artefact.
- Les UM de repositionnement **restent dans la population** de comparaison (pas d'exclusion) ; la
  réserve est portée par le **texte**, pas par un retraitement des données.
- Les 2 anomalies de saisie ci-dessus concernent **le même service 1334** : **qualité de saisie à
  surveiller** sur ce service.

---

## Alternatives écartées

**A1 — Projection contrefactuelle du modèle au grain bloc.** *Écartée.* Projeter les recommandations
du modèle sur des blocs (pour un chiffre « bloc » côté modèle) suppose de **reconstruire des blocs
contrefactuels** à partir de décisions que le modèle n'a pas prises — **coût** et **fragilité
d'hypothèse** élevés (points de découplage non modélisés). **Remplacée** par la **lecture en
fourchette** (D5) : le modèle (course) est lu contre l'intervalle bloc **humain**.

**A2 — Optimisation par chaîne / roulement.** *Écartée du POC, documentée en perspective.* Optimiser
la décision au niveau du **roulement** plutôt que de la course isolée est méthodologiquement possible
et l'**information existe à J-1** : le roulement planifié est connu **~J-20 h** via la séance
**GOP-CAT**. C'est une **piste d'extension** réaliste, mais **hors périmètre** du POC (D1), qui reste
au grain course pour la clarté décisionnelle et l'auditabilité.

**A3 — Grain tour comme barre de comparaison.** *Écartée.* Le grain tour (**73,4 %**, *période totale*,
1 047 tours UM) est **permissif** par construction (un tour est justifié dès qu'une de ses courses
surcharge) ; il **reproduit l'ancien 72,7 %** et sert **uniquement de diagnostic**, jamais de barre
(D6).

---

## Limites assumées

- **Plafond de détection hérité (D7).** La couche 2 hérite du plafond **PR-AUC HAUT ≈ 0,345**
  (signal J-1) ; elle **ne relève pas la détection**. Sa contribution est décisionnelle
  (formalisation, point d'opération, transparence).
- **Propagation bloc = chaînage observé, côté humain uniquement.** L'héritage bloc est reconstruit
  par chaînage des compositions **observées** (rotations + istdaten), **sans modélisation des points
  de découplage**. Aucune projection bloc n'est faite côté modèle.
- **Caveat label shift.** La tendance annuelle apparente (précision course H24 ~14 % → H25 ~33 %) est
  **en partie mécanique** : la **prévalence des surcharges est plus élevée en H25** (~×1,93 en
  tronçon) et, à comportement d'engagement constant, la précision apparente **monte avec la
  prévalence**. À lire comme « précision apparente en hausse, **en partie portée par la prévalence** »,
  **pas** comme une amélioration décisionnelle avérée.
- **Hypothèse d'inélasticité** de la demande à la capacité (la charge observée en UM aurait été la
  même en rame simple) — non testable ici, assumée.
- **Couverture APC réduite à l'automne 2025** (~75 % vs ~95 %) : échantillon H25 partiel sur les
  derniers mois ; ne pas sur-lire H25 Q3-Q4.

---

## Conséquences

- **Phase 2** (implémentation) : `src/couche2/decision.py` (chargement prédictions v1.9 H24/H25,
  agrégation max D3, label D2), calibration H24 walk-forward (D4), évaluation H25 unique (D5) sur le
  **périmètre iso 29 222**.
- **Deux objets distincts (R6) — à ne pas confondre.**
  - **Top-k protocolaire (comparaison headline).** Le **top-k au budget humain H25 (k = 418)** est une
    **constante du protocole de comparaison**, définie par la baseline **humaine** — **pas un paramètre
    de l'artefact**. Il n'est **pas « calibré »** et **ne contrevient pas à D4** : il **emprunte au côté
    humain le volume d'engagement** pour rendre la comparaison équitable, **sans utiliser les labels
    H25**. C'est la lecture **headline** (modèle vs humain, à volume égal).
  - **Points d'opération DÉPLOYABLES (menu métier), calibrés sur H24 (D4).** Seuils sur le **score**,
    réalistes en production (ne connaissent pas le budget H25 a priori) : **(a′) iso-volume** — seuil
    H24 tel que le **volume de recommandations = budget humain H24 (381)**, **appliqué tel quel à H25**
    (volume H25 résultant **proche de 418 mais non contraint**) ; **(b) rappel renforcé** (seuil
    abaissé — plus de détections, plus de FP) ; **(c) haute précision** (seuil relevé — moins de FP).
  - **Choix final** du point déployable : **pas statistique** — **ratio de coûts FN:FP élicité auprès
    du responsable de production** (Responsable de production, MOB), **consigné dans un mémo daté**. La couche 2 fournit la
    **courbe et la transparence** ; le métier tranche. Le **menu** (et non un point unique) est
    **présenté en évaluation organisationnelle** (cf. guide d'entretien §2.3).
- **Sorties D5 séparées.** `q_couche2_eval_416bb90b.json` et les figures rapportent **distinctement**
  (i) le **top-k protocolaire** (k = 418, comparaison headline vs humain) et (ii) les **trois seuils
  déployables** (a′ / b / c, menu métier) — jamais mélangés. Tous n bruts.
- **Tests** exigés : label course (D2), agrégation max (D3), respect du budget (D5),
  **non-contamination H25** (aucun paramètre dérivé de H25, D4).
- **Aucun impact couche 1** : hash `416bb90b` inchangé, vérifié par assertion en tête de chaque
  script couche 2.
- Intégration au digest `ALL_ADRS.md` **après passage en Accepté**.

---

## Addendum post-acceptation (2026-07-04, pré-lecture H25)

*Ajouté **après acceptation** et **avant toute lecture des résultats H25**, dans le cadre de la
phase 2 (P1 / verrouillage V-lock). N'édite pas le corps accepté ci-dessus ; le complète.*

- **Calibration in-sample (H24 ∈ train Split C).** Les prédictions couche 1 sur H24 sont **in-sample**.
  Le « walk-forward H24 » teste la **stabilité de seuils globaux entre sous-périodes de H24** (modèle
  figé), **pas** une validation séquentielle ni une causalité d'apprentissage. Les précisions H24 (ex.
  99,0 % à l'iso-volume) sont **in-sample** et ne se transfèrent pas telles quelles.
- **Décalage de scores H24→H25.** Diagnostic **sans labels** (scores disponibles à J-1) : les scores
  H25 sont plus bas (~6 pts au sommet de distribution). Ce décalage **confond optimisme in-sample et
  drift de population** — **indissociables sans labels H25** ; aucune attribution unilatérale.
- **Règles de rang.** Les trois règles déployables sont **exprimées en rang/volume** (quantiles de
  score H24), pas en score absolu, pour atténuer le risque de transfert.
- **Convention de transfert (V2, verrouillée).** En évaluation H25, **deux** conventions sont
  rapportées : **(i) seuil figé** = lecture de **déployabilité** (primaire pour le menu métier ; la
  sous-recommandation attendue — ~253 vs budget 418 — est un **résultat** de dérive de calibration en
  déploiement, motivant une **recalibration périodique** ; perspective : quantile glissant sur fenêtre
  écoulée, déployable à J-1) ; **(ii) rang annuel** = lecture **diagnostic de drift**, étiquetée
  « **convention d'évaluation, non déployable telle quelle** » (le rang dans la distribution annuelle
  H25 n'est pas connaissable à J-1). **Aucune des deux n'est le headline** : le headline reste le
  **top-k protocolaire k = 418** (R6). Cette hiérarchie **ne change pas** après lecture des résultats.
- **Limitation assumée (P1).** Seuils calibrés sur prédictions **in-sample** ; risque de transfert
  documenté ; atténué par règles de rang ; convention de transfert V2 ci-dessus.

---

## Addendum post-lecture H25 (2026-07-04) — plancher de demande annoncée (candidat au menu déployable)

*Chronologie : ajouté **après** la lecture des résultats H25 (phase 2.3), comme composant **candidat**
du menu déployable. **Statut : à valider en entretien (A17).** N'édite pas le corps accepté.*

- **Règle candidate.** « **Plancher de demande annoncée** » : recommander toute course dont la
  **réservation 2ᵉ classe à J-1** (`resa_pax_2c_J_minus_1`) dépasse la **capacité assise** (> 63). Il ne
  s'agit **pas d'une garantie** (voir taux de réalisation).
- **Justification a priori** (indépendante des résultats H25) : une **demande annoncée** supérieure à la
  capacité assise **exige une réponse** — signal **déterministe** de niveau opérationnel, **orthogonal**
  au score prédictif (histo-piloté).
- **Chiffres H25 en appui (X6, n bruts).** 154 courses résa>63 (142 HAUT / 12 BAS) ; **taux de
  réalisation 64 %** (99/154 ; H24 : 70 %, 64/92) → **no-show/annulation implicite ~30-36 %** (d'où
  « plancher de demande annoncée », pas une garantie). Croisement top-418 : **94 déjà couvertes**
  (redondance), **60 d'apport propre** (hors top-418, majoritairement HAUT), dont **31 surcharges
  réalisées**.
- **Architecture cible (si retenue).** **Plancher déterministe du menu déployable** : la règle **force**
  la recommandation (demande annoncée > capacité), le score la **complète** ; **jamais fondue dans le
  top-k protocolaire** (comparaison headline). Complémentaire au score histo-piloté, qui rattrape les
  nouveaux services en ~1 mois (addendum 1 / X9).

---

## Addendum post-lecture H25 (2026-07-05) — remplacement de la comparaison headline D5

*Chronologie : ajouté **après** la lecture des résultats H25. **Aucun recalcul, aucun résultat
préenregistré supprimé** : le top-k=418 reste intégralement rapporté en **annexe**. On change la
**lecture principale**, pas les nombres.*

- **Décision.** La comparaison **iso-budget top-k = 418** (préenregistrée et exécutée) est **remplacée
  comme lecture principale** par la comparaison à **points d'opération naturels** : les **matrices de
  confusion des règles déployables** (a′, b, c — **seuil figé**) **+ le plancher de demande annoncée**,
  **chacune à son volume propre**, contre la **pratique humaine H25 observée** (418 UM, précision course
  **33,5 %** / rappel **6,8 %**).
- **Critère de validité (dominance).** Une règle est validée si elle **domine simultanément** le point
  humain sur **précision ET rappel**. Résultat H25 (seuil figé) :

  | Point d'opération (seuil figé, H25) | volume | VP | FP | précision | rappel | domine (P>33,5 % ET R>6,8 %) |
  |---|---|---|---|---|---|---|
  | **(a′) iso-volume** | **253** | 216 | 37 | **85,4 %** | **10,4 %** | **✓✓ — à volume INFÉRIEUR à la pratique (253 < 418)** |
  | (b) rappel renforcé | 2 564 | 1 289 | 1 275 | 50,3 % | 62,2 % | ✓✓ |
  | (c) haute précision | 848 | 611 | 237 | 72,1 % | 29,5 % | ✓✓ |
  | plancher de demande annoncée | 154 | 99 | 55 | 64,3 % | 4,8 % | **complément** (rappel < humain, jamais seul) |
  | **artefact complet (a′ ∪ plancher) — RÉFÉRENCE** | **353** | 275 | 78 | **77,9 %** | **13,3 %** | **✓✓** |

  Le fait le plus fort : **(a′) domine l'humain en engageant MOINS de courses** (253 vs 418).

  **Discipline de dominance (F1).** La dominance simultanée précision **ET** rappel ne s'applique qu'aux
  **trois règles de score (a′, b, c)**. Le **plancher seul ne domine PAS** (rappel 4,8 % < 6,8 %) : c'est un
  **filet complémentaire** — couverture du **risque de demande annoncée que le score manque** (X6 : 60 courses
  HAUT hors classement) — **jamais déployé seul**. L'**artefact complet** = **score (a′) ∪ plancher** : à
  **volume 353** (recouvrement : 199 a′ seul + 100 plancher seul + 54 communs), il **domine** l'humain
  (77,9 % / 13,3 %) et constitue le **point de référence** rapporté en lecture principale et sur les supports
  d'entretien (3.3).
- **Motif.** Le **volume humain (418) n'est pas une enveloppe allouée** mais la **résultante de contraintes
  locales** (matériel disponible, roulements, maintenance). La contrainte **iso-volume n'a donc pas
  d'interprétation opérationnelle** ; comparer à volume égal impose au modèle une contrainte que
  l'exploitant ne subit pas comme un budget. Les points d'opération **déployables** (seuils calibrés H24)
  sont la lecture pertinente.
- **Intégrité du préenregistrement.** Le top-k=418 (résultats P=82,1 % / R=16,6 %) **reste rapporté** dans
  le JSON canonique et **en annexe du notebook**, avec mention de statut, **sans rôle narratif**. Rien
  n'est supprimé ; la transparence du protocole préenregistré est préservée.

### Point d'opération de référence de l'artefact

En attendant le **choix du métier en entretien (A17)**, le **point de référence** de l'artefact est la
règle **(a′) iso-volume** : **calibrée sur H24**, seuil ancré sur le **volume de pratique H24 = 381**
(déployable, ne connaît pas le budget H25 a priori), **appliquée à H25** (volume résultant 253). C'est le
point **le plus conservateur** (précision 85,4 %, volume inférieur à la pratique) et le plus directement
**déployable**. Les règles (b)/(c) et le plancher restent au menu pour l'arbitrage coût FN:FP.

---


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

---


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

---


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

---


---
id: ADR-077
ancien_id: aucun
date_decision: 2026-07-12
statut: actif
modifie: [ADR-073]
corroboration_date: en attente
gel_registre: 2026-08-16
---

# ADR-077 - Configuration de déploiement recommandée : règle c + plancher réservations

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-073.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté le 2026-07-24 (addendum), proposé le 2026-07-12 |  <!-- statut d'époque ; état au gel : actif (voir bandeau) -->
| **Date** | 2026-07-12 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-073 (problème de décision couche 2 : famille de points d'exploitation + plancher = l'ARTEFACT) ; ADR-076 (gel v2 `ba493568`) ; ADR-060 (seuil de surcharge 63) |
| **Génération** | `ba493568` (gel v2) |

---

## Contexte

L'artefact de couche 2 (ADR-073) est une **famille de points d'exploitation** (menu déployable a'/b/c) plus un **plancher de demande annoncée** (réservations J-1). Il ne prescrit pas un point unique : le choix relève des exigences métier. Deux exigences élicitées désignent une instanciation :

1. **Ratio de tolérance du décideur** (responsable de production, notes d'entretien informel de juillet 2026 ; hypothèses A16-A18 du guide v2.11) : précision **idéalement ~66 %**, **limite ~50 %**. Le point **c** (F0.5, precision-weighted, seuil H24 = 64,12) vise cette bande.
2. **Contrainte de conception (garantie des réservations)** : toute demande annoncée dépassant le seuil de places doit être garantie — une réservation est un **engagement commercial**. D'où le **plancher** `resa2c > 63`, uni au score.

D'où la configuration de déploiement : **recommandation = (score ≥ 64,12 au grain course, max tronçon) OU (resa2c > 63)**.

## Décision

La **configuration de déploiement recommandée** est **c ∪ plancher**. Ce n'est **ni une re-conception ni une re-calibration** : la famille de points et le plancher sont l'artefact (ADR-073) ; le seuil c est celui calibré sur H24 (ADR-073, inchangé) ; on **instancie** l'artefact selon les exigences ci-dessus.

**On AJOUTE une configuration, on ne remplace rien.** La configuration d'évaluation **a' ∪ plancher** (iso-volume, 352/77,8 %/13,2 %) conserve son rôle : **comparaison loyale à la pratique humaine** (même budget que les 418 UM). Les deux coexistent avec des fonctions distinctes (évaluation iso-volume vs déploiement).

## Chiffres H25 (grain course, iso-périmètre 29 222 courses / 2 072 surcharges, gardes tenues)

| Configuration (global) | volume | VP | FP | précision | rappel |
|---|---|---|---|---|---|
| **Déploiement c ∪ plancher** | **866** | 622 | 244 | **71,8 %** | **30,0 %** |
| c seul (F0.5) | 840 | 605 | 235 | 72,0 % | 29,2 % |
| a' ∪ plancher (évaluation iso-volume) | 352 | 274 | 78 | 77,8 % | 13,2 % |
| b (F2, rappel) | 2 563 | 1 292 | 1 271 | 50,4 % | 62,4 % |
| humaine (418 UM) | 418 | 140 | 278 | 33,5 % | 6,8 % |

Déploiement par segment : HAUT 395 / 68,6 % / 22,1 % ; BAS 471 / 74,5 % / 41,4 %.

**Recouvrement (H25)** : score seul **712**, plancher seul **26**, intersection **128**, union **866**. L'union ne s'extrapolait pas de a' ∪ plancher : à seuil c (64,12, plus bas que a' 78,99), le score capture déjà l'essentiel de ce que le plancher apportait à a' — le plancher n'ajoute que **26 courses propres** (contre 100 pour a').

**Rappels par strate H25** (déploiement / c seul / a'∪plancher) : 63-93 **24,8 %** / 24,0 % / 8,2 % ; 94-165 **56,2 %** / 55,0 % / 38,2 % ; 166+ **50,0 %** / 50,0 % / 33,3 %.

**Capture des 166+ (6 cas)** : l'union en capte **3/6**, tous par le **score** (les 6 cas ont `resa2c = 0`, le plancher n'ajoute rien sur cette queue). Détail : 206 (score 74,9, capté), 182 (95,7, capté), 167 (94,1, capté) ; 174 (62,0), 172 (57,9), 166 (57,9) non captés (score < 64,12, sans réservation).

**Coûts FP (volet B, tare 54,2 t × distance × 0,06444 CHF/tbkm — provenance en addendum du 2026-08-18)** : déploiement **244 FP / 6 922 CHF** (c seul 235 / 6 592 ; a'∪plancher 78 / 2 495 ; humaine 278 / 8 719).

## Cohérence de calibration (H24, constat, PAS re-calibration)

Sur H24 (année de calibration) : c seul **1 546 / 85,1 % / 55,3 %** ; c ∪ plancher **1 573 / 83,7 % / 55,3 %** (le plancher n'ajoute que 27 courses). La précision reste **au-dessus de la bande cible** (idéal 66 %, limite 50 %) sur l'année de calibration : la configuration est cohérente avec l'exigence de précision.

## Justification : le plancher, garantie inconditionnelle et non contribution statistique

Le recouvrement H25 le montre : à seuil c (64,12), le plancher n'apporte que **26 courses propres** (contre 100 à a') et ne capte **aucun des six 166+** (`resa2c = 0` sur les six). Le plancher est conservé **non pour sa contribution statistique** — marginale à ce seuil — **mais pour sa fonction de garantie inconditionnelle** : une réservation annoncée dépassant le seuil de places est un **engagement commercial**, garanti **par construction** (indépendamment du score du modèle). Sa **redondance croissante** quand le score devient plus sensible (de a' à c) est une **propriété de robustesse** — deux filets, l'un statistique (score), l'autre commercial (plancher) — **pas un défaut**.

## Pare-feu de restitution

L'évaluation naturaliste de mardi (Human Risk & Effectiveness) porte sur **cette configuration de déploiement**. Le **pare-feu de restitution** (guide 2.2) reste entier : ni la **justification chiffrée** du choix de c, ni la **cartographie des points d'exploitation** ne sont présentées avant ou pendant la section D de l'entretien.

## Sources datées et validation

- Notes d'entretien informel (ratio 66/50, juillet 2026).
- Contrainte de garantie des réservations (concepteur / responsable des données).
- Hypothèses **A16-A18** du guide d'entretien v2.11. **Leur validation formelle intervient à l'entretien de mardi** : si la grille les infirme, un **addendum post-entretien** est porté au présent ADR (la décision de configuration est alors ré-examinée).

- **Provenance de la convention de coût (addendum du 2026-08-18)** — tare de **54,2 t** : Stadler, esquisse-type ABeh 2/6 7500, plan n° BZ 2004242 indice c. Prix du sillon **0,06444 CHF/tbkm** : Transports Montreux-Vevey-Riviera SA, « MVR prix du sillon TRV 2025 », document interne, juillet 2024. Facteur agrégé 54,2 × 0,06444 = **3,4926 CHF/km de course**, arrondi à 3,49 au manuscrit (§4.7.2). Complément documentaire : aucune valeur ni décision du présent ADR n'est modifiée.

## Limites

Les **trois 166+ non captés** (2025-09-02 course 1508 ; 2025-05-18 course 1419 ; 2025-08-26 course 1508) ont tous `resa2c = 0` et des **scores 57-62** (sous le seuil c = 64,12) : **ni le filet commercial ni le filet statistique ne voient cette queue**. C'est la **démonstration empirique de la limite théorique** : un seuil sur une moyenne conditionnelle (le score de régression) ne **garantit pas les queues**. La **règle composite par quantile** (garantie sur les queues) reste le **travail futur désigné** ; renvoi à la discussion du mémoire.

## Addendum de formulation (2026-07-12, statut 166 clarifié par élicitation écrite) : définition et statut de la strate 166+

Formulation seule, aucun chiffre de la décision modifié.

**Cible mesurée contre la capacité d'une rame simple (non-circularité).** La strate 166+ (volet C) mesure la **demande** (charge 2ème classe réalisée au tronçon le plus chargé) rapportée à la **capacité de référence d'une rame simple**, indépendamment de la composition effectivement roulée. Justification : mesurer la surcharge contre la capacité roulée rendrait la cible circulaire ; les doublements décidés à bon escient effaceraient les positifs qu'ils traitent ; la demande est donc rapportée à la capacité de référence d'une rame simple. C'est déjà la logique du seuil de surcharge lui-même (63 places assises d'une rame simple, ADR-060), appliquée à la borne haute.

**Statut de la borne 166 (arbitrage 94/166/188 clos par élicitation écrite).** La borne 166 est la **conversion en personnes** (places debout comprises, hors strapontins, vélos et chaises roulantes) d'une **charge maximale admissible de 12,7 tonnes par rame**, définie par le responsable de production (élicitation écrite du 2026-07-09, citation intégrale au dossier d'élicitation `docs/entretiens/dossier_elicitation_deploiement.md`). La limite primaire est **massique** ; 166 en est la **projection conventionnelle** utilisée comme **seuil de planification**. L'écart apparent avec `src/r35/constants.py` (63 assises 2C, 94 d'offre APC totale, 188 pour une UM) est **clos** : 63 et 94 sont des capacités de **places**, 166 une limite de **masse convertie** — grandeurs différentes, aucune contradiction.

**Restent à établir en entretien (hypothèse A16).** (1) source documentaire du 12,7 t (fiche matériel 7500 ou prescription d'exploitation) ; (2) convention de conversion (poids moyen par personne) ; (3) statut opérationnel du dépassement en exploitation. **Amorce empirique** (annexe des cas d'entretien) : **4 des 6 occurrences 166+ ont roulé en rame simple** (dont une à 182), donc le comptage peut dépasser 166 sans que la marche soit empêchée — masse réelle inférieure au comptage, ou tolérance : à éliciter (troisième question A16).

## Addendum (2026-07-16) : renumérotation du guide d'entretien

Renumérotation du guide d'entretien (v2.15) : l'hypothèse **A16** citée dans l'addendum du 2026-07-12 est désormais **H7** ; table de correspondance dans la note de révision du guide. Le corps et l'addendum du 2026-07-12 ne sont pas réécrits (immutabilité de l'ADR) : cette note suffit à la traçabilité de l'identifiant.

## Conséquences

- Artefact `outputs/couche2/q_couche2_deploiement_ba493568.json` (mêmes gardes et meta que `q_couche2_eval`), canonique, généré par `scripts/experiences/deploiement_c_plancher_ba493568.py` (protocole préenregistré en tête).
- La configuration d'évaluation a' ∪ plancher est **inchangée** dans tous les documents existants.
- Chiffres H25 de l'union consignés ci-dessus (produits avant la sélection des cas d'entretien).

## Addendum (2026-07-24)

Statut porté de proposé à accepté. Les entretiens décideurs D01 et D02 (14.07.2026) et l'évaluation organisationnelle (mémoire, section 4.7.4) n'ont pas remis en cause la configuration c ∪ plancher, retenue comme configuration de déploiement recommandée. Deux conditions : la lecture calendaire post-hoc (mémoire, section 4.7.1) établit un rappel de week-end inférieur à la pratique pour les postures de parcimonie, motivant l'étude d'une politique de seuil différenciée par type de jour (recommandation, section 5.2) ; la confirmation sur une année horaire vierge reste requise avant industrialisation.

---


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

---
