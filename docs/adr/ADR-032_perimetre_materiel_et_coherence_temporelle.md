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
