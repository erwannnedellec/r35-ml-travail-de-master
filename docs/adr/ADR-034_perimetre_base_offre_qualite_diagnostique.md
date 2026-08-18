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
