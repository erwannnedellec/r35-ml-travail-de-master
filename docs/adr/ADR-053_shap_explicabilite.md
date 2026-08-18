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
