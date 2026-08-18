#!/usr/bin/env python3
"""
_table_autorite_annexe22.py — table d'autorité candidate ↔ statut ↔ colonnes.

TRANSCRIPTION du tableau A19.1 de l'annexe 22 du mémoire (`TM_Format_final_v3_89.docx`),
fournie par la consigne de la VÉRIF 4. **C'est la seule source d'autorité.**

Le dépôt ne consigne PAS le lien variable ↔ littérature ↔ entretiens : le mémoire l'écrit
explicitement en tête de son annexe 22 (« le rattachement d'une candidate à une colonne
est un jugement, non un calcul »). Toute table de correspondance trouvée dans le dépôt
est donc traitée comme potentiellement périmée et réconciliée contre celle-ci ; les écarts
sont rapportés, jamais arbitrés.

Ce module ne contient que des données. Il n'exécute aucun calcul.
"""

CONFIRMEE, LITTERATURE, EMERGENTE = "Confirmée", "Littérature", "Émergente"

# (candidate, triangulation, statut de couverture, colonnes de la table)
TABLE_A19_1 = [
    ("F_TEMP.heure", CONFIRMEE, "Couverte directement", [
        "cal_heure_depart", "cal_minute_depart", "cal_depart_minute_du_jour",
        "cal_heure_arrivee", "cal_minute_arrivee", "cal_arrivee_minute_du_jour"]),
    ("F_TEMP.jour_semaine", CONFIRMEE, "Couverte directement", [
        "cal_jour_semaine", "cal_jour_semaine_iso", "cal_is_weekend",
        "cal_type_jour_3classes"]),
    ("F_TEMP.mois", CONFIRMEE, "Couverte directement", [
        "cal_mois", "cal_mois_horaire", "cal_jour", "cal_annee_civile"]),
    ("F_TEMP.vacances", CONFIRMEE, "Couverte directement", [
        "event_is_vacances_vaud", "event_is_vacances_ou_ferie_vaud"]),
    ("F_TEMP.ferie", LITTERATURE, "Couverte directement", [
        "event_is_ferie_vaud", "cal_type_jour"]),
    ("F_TEMP.lag_J-1", LITTERATURE, "Couverte avec transformation", [
        "histo_voyageurs_1ere_classe_lag2", "histo_voyageurs_2eme_classe_lag2",
        "histo_voyageurs_total_lag2"]),
    ("F_TEMP.lag_S-1", LITTERATURE, "Couverte avec transformation", [
        "histo_voyageurs_1ere_classe_win7_max", "histo_voyageurs_1ere_classe_win7_mean",
        "histo_voyageurs_1ere_classe_win7_median", "histo_voyageurs_1ere_classe_win7_std",
        "histo_voyageurs_2eme_classe_win7_max", "histo_voyageurs_2eme_classe_win7_mean",
        "histo_voyageurs_2eme_classe_win7_median",
        "histo_voyageurs_2eme_classe_win7_n_surcharges",
        "histo_voyageurs_2eme_classe_win7_std", "histo_voyageurs_total_win7_max",
        "histo_voyageurs_total_win7_mean", "histo_voyageurs_total_win7_median",
        "histo_voyageurs_total_win7_std"]),
    ("F_TEMP.ponctualite", CONFIRMEE, "Couverte directement", [
        "ist_profil_train_pct_en_retard_arr_troncon_20occ",
        "ist_profil_train_pct_en_retard_arr_troncon_5occ",
        "ist_profil_train_pct_en_retard_dep_troncon_20occ",
        "ist_profil_train_pct_en_retard_dep_troncon_5occ",
        "ist_profil_train_retard_arr_troncon_mean_20occ",
        "ist_profil_train_retard_arr_troncon_mean_5occ",
        "ist_profil_train_retard_arr_troncon_std_20occ",
        "ist_profil_train_retard_arr_troncon_std_5occ",
        "ist_profil_train_retard_dep_troncon_mean_20occ",
        "ist_profil_train_retard_dep_troncon_mean_5occ",
        "ist_profil_train_retard_dep_troncon_std_20occ",
        "ist_profil_train_retard_dep_troncon_std_5occ"]),
    ("F_METEO.temperature", CONFIRMEE, "Couverte directement", [
        "meteo_temperature_h", "meteo_destination_temperature_h",
        "meteo_temperature_max_j", "meteo_destination_temperature_max_j"]),
    ("F_METEO.precipitation", CONFIRMEE, "Couverte directement", [
        "meteo_destination_precip_total_j", "meteo_destination_precip_total_j_moins_1",
        "meteo_destination_precip_total_j_plus_1",
        "meteo_destination_precipitation_mm_h", "meteo_precip_total_j",
        "meteo_precip_total_j_moins_1", "meteo_precip_total_j_plus_1",
        "meteo_precipitation_mm_h"]),
    ("F_METEO.neige", CONFIRMEE, "Couverte directement", ["meteo_neige_binaire_h"]),
    ("F_METEO.ensoleillement", CONFIRMEE, "Couverte directement", [
        "meteo_destination_ensol_total_j", "meteo_destination_ensol_total_j_moins_1",
        "meteo_destination_ensol_total_j_plus_1",
        "meteo_destination_ensoleillement_min_h",
        "meteo_destination_rayon_global_moy_j", "meteo_ensol_total_j",
        "meteo_ensol_total_j_moins_1", "meteo_ensol_total_j_plus_1",
        "meteo_ensoleillement_min_h", "meteo_rayon_global_moy_j"]),
    ("F_METEO.vent", LITTERATURE, "Couverte directement", [
        "meteo_destination_vent_max_h", "meteo_destination_vent_max_j",
        "meteo_vent_max_h", "meteo_vent_max_j"]),
    ("F_SOL.pop_residente", LITTERATURE, "Couverte directement", [
        "spatial_gare_depart_pop_500m_total", "spatial_gare_arrivee_pop_500m_total",
        "spatial_gare_depart_menages_500m_total", "spatial_gare_arrivee_menages_500m_total",
        "spatial_gare_depart_pop_par_menage_500m", "spatial_gare_arrivee_pop_par_menage_500m",
        "spatial_gare_depart_part_menages_1p", "spatial_gare_arrivee_part_menages_1p",
        "spatial_gare_depart_part_grands_menages_4p",
        "spatial_gare_arrivee_part_grands_menages_4p",
        "spatial_gare_depart_part_pop_0_14_ans", "spatial_gare_arrivee_part_pop_0_14_ans",
        "spatial_gare_depart_part_pop_15_24_ans", "spatial_gare_arrivee_part_pop_15_24_ans",
        "spatial_gare_depart_part_pop_25_64_ans", "spatial_gare_arrivee_part_pop_25_64_ans",
        "spatial_gare_depart_part_pop_65_plus", "spatial_gare_arrivee_part_pop_65_plus",
        "spatial_gare_depart_part_pop_80_plus", "spatial_gare_arrivee_part_pop_80_plus",
        "spatial_gare_depart_indice_stabilite_resid",
        "spatial_gare_arrivee_indice_stabilite_resid",
        "spatial_gare_depart_indice_mobilite_resid",
        "spatial_gare_arrivee_indice_mobilite_resid",
        "spatial_gare_depart_part_nouveaux_arrivants_1an",
        "spatial_gare_arrivee_part_nouveaux_arrivants_1an",
        "spatial_gare_depart_part_pop_etrangere", "spatial_gare_arrivee_part_pop_etrangere",
        "spatial_gare_depart_part_pop_nee_etranger",
        "spatial_gare_arrivee_part_pop_nee_etranger"]),
    ("F_SOL.densite_res", LITTERATURE, "Couverte avec transformation", [
        "spatial_gare_depart_pop_500m_total", "spatial_gare_arrivee_pop_500m_total"]),
    ("F_RESEAU.bus_215", CONFIRMEE, "Couverte avec transformation", [
        "vmcv_delta_attente_min", "vmcv_delta_frequence_h", "vmcv_min_attente_min",
        "vmcv_n_lignes_concurrentes"]),
    ("F_RESEAU.correspondance", CONFIRMEE, "Couverte directement", [
        "ist_corresp_in_n_garanties_moy_20occ", "ist_corresp_in_n_garanties_moy_5occ",
        "ist_corresp_in_n_theoriques_moy_20occ", "ist_corresp_in_n_theoriques_moy_5occ",
        "ist_corresp_in_pct_garanties_20occ", "ist_corresp_in_pct_garanties_5occ",
        "ist_corresp_out_n_garanties_moy_20occ", "ist_corresp_out_n_garanties_moy_5occ",
        "ist_corresp_out_n_theoriques_moy_20occ", "ist_corresp_out_n_theoriques_moy_5occ",
        "ist_corresp_out_pct_garanties_20occ", "ist_corresp_out_pct_garanties_5occ"]),
    ("F_TERRAIN.altitude", LITTERATURE, "Couverte avec transformation", [
        "spatial_denivele_troncon_m"]),
    ("F_TERRAIN.troncon", EMERGENTE, "Couverte par le grain", [
        "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre", "spatial_segment",
        "spatial_distance_km"]),
    ("F_EVT.jazz", CONFIRMEE, "Couverte directement", ["event_is_montreux_jazz"]),
    ("F_EVT.marche_noel", CONFIRMEE, "Couverte directement", [
        "event_is_marche_noel", "event_is_montreux_noel"]),
    ("F_EVT.narcisses", EMERGENTE, "Couverte directement", [
        "event_is_saison_narcisses", "event_narcisses_source"]),
    ("F_EVT.calendrier_local", CONFIRMEE, "Couverte directement", [
        "event_is_manifestation_riviera", "event_n_manifestations_blonay_j",
        "event_n_manifestations_hors_zone_j", "event_n_manifestations_riviera",
        "event_n_manifestations_st_legier_j", "event_n_manifestations_vevey_j",
        "event_n_manifestations_zone_directe_j", "event_n_manifestations_zone_indirecte_j"]),
    ("F_EVT.ski", EMERGENTE, "Couverte directement", [
        "event_is_ski_ouvert", "event_ski_source"]),
    ("F_OPS.travaux", EMERGENTE, "Non couverte", []),
    ("F_OPS.composition", EMERGENTE, "Exclue par conception", []),
    ("F_OPS.direction", EMERGENTE, "Couverte par le grain", ["base_sens"]),
    ("F_OPS.headway", CONFIRMEE, "Couverte directement", [
        "ist_headway_apres_is_last_of_day", "ist_headway_apres_min",
        "ist_headway_avant_is_first_of_day", "ist_headway_avant_min"]),
    ("F_OPS.groupes", EMERGENTE, "Couverte directement", [
        "resa_has_resa_J_minus_1", "resa_max_groupe_2c_J_minus_1",
        "resa_n_dossiers_J_minus_1", "resa_n_langues_distinctes_J_minus_1",
        "resa_n_pays_distincts_J_minus_1", "resa_part_scolaire_J_minus_1",
        "resa_part_tour_operator_J_minus_1", "resa_pax_2c_J_minus_1"]),
    ("F_EMERG.migros", EMERGENTE, "Non couverte", []),
    ("F_EMERG.1ere_classe", EMERGENTE, "Exclue par conception", []),
]

# Tableau A19.2 du mémoire — agrégats de contrôle à reproduire EXACTEMENT (porte bloquante).
A19_2_ATTENDU = {
    CONFIRMEE:   {"candidates": 15, "colonnes": 82, "bas": 46.63, "haut": 52.89},
    LITTERATURE: {"candidates": 7,  "colonnes": 53, "bas": 43.23, "haut": 35.67},
    EMERGENTE:   {"candidates": 9,  "colonnes": 17, "bas": 8.73,  "haut": 10.34},
    "Total":     {"candidates": 31, "colonnes": 152, "bas": 98.59, "haut": 98.90},
}

# Colonnes de la table non rattachées à une candidate (contrôle du mémoire).
NON_RATTACHEES_ATTENDU = {"colonnes": 57, "bas": 1.41, "haut": 1.10, "dans_le_modele": 8}

# ── Périmètre d'ablation, fixé par la consigne (section 3, points A et B) ───────
# Les candidates « Couverte par le grain » encodent la structure de la table et non un
# construit comportemental : elles sont EXCLUES du périmètre d'ablation par convention.
EXCLUES_DU_PERIMETRE = ["F_TERRAIN.troncon", "F_OPS.direction"]

# Périmètre substantiel de l'ablation émergente (12 colonnes).
CANDIDATES_A1 = ["F_EVT.narcisses", "F_EVT.ski", "F_OPS.groupes"]
# Strate séparée : statut contradictoire entre l'annexe 22 et les sections 4.2.1 / 4.2.2.
CANDIDATES_STRATE_VMCV = ["F_RESEAU.bus_215"]
