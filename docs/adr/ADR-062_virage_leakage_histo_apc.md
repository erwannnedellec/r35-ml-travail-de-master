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
