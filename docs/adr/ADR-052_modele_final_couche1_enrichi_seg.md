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
