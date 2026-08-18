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
