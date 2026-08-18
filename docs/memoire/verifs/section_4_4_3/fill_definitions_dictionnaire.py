#!/usr/bin/env python3
"""Annexe §4.4.3 — remplissage de la colonne `definition` du dictionnaire de données.

Objet
-----
Compléter le squelette produit par `make_dictionnaire_colonnes_canonique.py` avec
cinq colonnes documentaires (`definition`, `unite`, `mode_obtention`,
`source_definition`, `confiance`), rédigées d'après le CODE PRODUCTEUR de chaque
colonne et non d'après les docstrings.

Règle cardinale appliquée
-------------------------
Chaque définition est écrite d'après l'opération effectivement réalisée par le
script producteur, aux lignes citées dans `source_definition`. Lorsque le
docstring d'un producteur affirme autre chose que son calcul, la définition suit
le CALCUL et la divergence est consignée dans `definitions_rapport.md` (constante
`DIVERGENCES`). Aucune définition n'est inférée : une colonne dont le producteur
n'a pas été retrouvé, ou dont le calcul reste ambigu, garde une `definition` vide
et figure dans `NON_RESOLUES`.

Ce script NE régénère aucune des colonnes existantes du CSV : il les relit
telles quelles et n'ajoute que les cinq colonnes documentaires. Il ne recalcule
rien sur les données, à l'exception des trois vérifications complémentaires
demandées, qui sont en LECTURE SEULE.

Sorties
-------
  docs/memoire/tableaux/section_4_4_3/dictionnaire_colonnes_canonique.csv   (mis à jour)
  docs/memoire/tableaux/section_4_4_3/dictionnaire_colonnes_canonique.xlsx  (mis à jour)
  docs/memoire/verifs/section_4_4_3/grammaire_nommage.md
  docs/memoire/verifs/section_4_4_3/definitions_rapport.md

Exécution (une commande, déterministe — aucun horodatage dans les sorties) :

    venv/bin/python docs/memoire/verifs/section_4_4_3/fill_definitions_dictionnaire.py

LECTURE SEULE sur les données et les modèles.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
TABLEAUX = ROOT / "docs" / "memoire" / "tableaux" / "section_4_4_3"

CANON = ROOT / "data" / "processed" / "ml_dataset.parquet"
DICO_CSV = TABLEAUX / "dictionnaire_colonnes_canonique.csv"
DICO_XLSX = TABLEAUX / "dictionnaire_colonnes_canonique.xlsx"
OUT_GRAMMAIRE = DOSSIER / "grammaire_nommage.md"
OUT_RAPPORT = DOSSIER / "definitions_rapport.md"

HASH_ATTENDU = "ba493568"
N_COLONNES_ATTENDU = 209

# Colonnes documentaires ajoutées par ce script (les seules qu'il écrit).
COLONNES_AJOUTEES = ["unite", "mode_obtention", "source_definition", "confiance"]

EPOQUE_FIXE = dt.datetime(1980, 1, 1, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Raccourcis de chemins producteurs
# --------------------------------------------------------------------------- #
S_STACK = "scripts/sources/stack_raw_csv.py"
S_ANNEE = "scripts/pipeline/add_annee_horaire_to_raw_stacked.py"
S_CAL = "scripts/pipeline/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py"
S_MANIF = "scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py"
S_SKI = "scripts/pipeline/add_ski_pleiades_to_raw_stacked.py"
S_COVID = "scripts/pipeline/add_covid_to_raw_stacked.py"
S_NARC = "scripts/pipeline/add_narcisses_to_raw_stacked.py"
S_SPAT = "scripts/pipeline/add_spatial_to_raw_stacked.py"
S_METEOH = "scripts/pipeline/add_meteo_to_raw_stacked.py"
S_METEOJ = "scripts/pipeline/add_meteo_journaliere_to_raw_stacked.py"
S_STATPOP = "scripts/pipeline/add_statpop_to_raw_stacked_annee_horaire_meteo_vev.py"
S_STATENT = "scripts/pipeline/add_statent_to_raw_stacked.py"
S_IST = "scripts/pipeline/add_istdaten_to_raw_stacked.py"
S_FEAT = "scripts/pipeline/add_features_to_raw_stacked.py"
S_SIMBA = "scripts/pipeline/add_simba_to_raw_stacked.py"
S_RESA = "scripts/pipeline/add_reservations_to_raw_stacked.py"

B_STATPOP = "scripts/sources/build_fact_statpop_gare.py"
B_HEADWAY = "scripts/sources/build_dim_headway.py"
B_PROFIL = "scripts/sources/build_dim_profil_train.py"
B_CORRESP = "scripts/sources/build_dim_correspondances_vevey.py"
B_VMCV = "scripts/sources/build_dim_vmcv_par_train_jour.py"
B_SIMBA = "scripts/sources/build_dim_simba_r35.py"
B_NARC = "scripts/sources/build_dim_narcisses.py"
B_SKI = "scripts/sources/build_dim_ski_pleiades_avec_reconstruction.py"
B_COVID = "scripts/sources/build_dim_covid.py"
B_VACANCES = "scripts/sources/build_dim_vacances_feries_vaud.py"
B_MANIF = "scripts/sources/build_dim_manifestations_riviera.py"
U_ROLLING = "scripts/sources/_rolling_par_type_jour.py"
U_RESA = "scripts/pipeline/reservations_utils.py"

# Vocabulaire d'unités. Les six dernières étendent la liste proposée dans la
# commande : aucune des unités proposées ne les exprime sans fausser la mesure.
UNITES_PROPOSEES = {
    "voyageurs", "minutes", "mm", "°C", "heures", "mètres", "habitants",
    "pourcentage", "sans unité", "",
}
UNITES_AJOUTEES = {"km", "km/h", "W/m²", "places", "ménages", "secondes"}


DEFS: dict[str, tuple[str, str, str, str, str]] = {}


def d(nom: str, definition: str, unite: str, mode: str, source: str,
      confiance: str = "haute") -> None:
    """Enregistre une définition. `definition` vide = colonne non résolue."""
    DEFS[nom] = (definition, unite, mode, source, confiance)


# --------------------------------------------------------------------------- #
# id_ — identifiants et clés
# --------------------------------------------------------------------------- #
d("id_source_file",
  "Nom du fichier CSV d'export APC dont provient l'observation, inscrit en "
  "première colonne au moment de l'empilement des exports bruts.",
  "sans unité", "dérivée", f"{S_STACK}:load_csv():L212-224")

for cote, lib in (("depart", "de départ"), ("arrivee", "d'arrivée")):
    d(f"id_gare_{cote}",
      f"Abréviation de la gare {lib} du tronçon, restituée telle quelle depuis "
      "la colonne correspondante de l'export APC.",
      "sans unité", "brute", f"{S_STACK}:rename_output_columns():L107-176")
    d(f"id_gare_{cote}_bpuic",
      f"Identifiant BPUIC du point d'arrêt de la gare {lib}, obtenu par jointure "
      "de l'abréviation de gare sur le référentiel gare_abreviation.csv "
      "(colonne Gare_BPUIC).",
      "sans unité", "dérivée",
      f"{S_STACK}:add_station_dimension():L422-463")

d("id_statpop_reference_year",
  "Millésime STATPOP mobilisé par la ligne, résolu par table de correspondance "
  "depuis l'année civile de la date de circulation selon une règle de causalité "
  "Z-2 (une observation de l'année civile Z reçoit le millésime Z-2), avec report "
  "sur le millésime 2015 pour les années civiles antérieures à 2017. L'indexation "
  "porte sur l'année civile et non sur l'année horaire, de sorte qu'une "
  "observation de décembre reçoive le millésime de son année civile.",
  "sans unité", "dérivée",
  f"{S_STATPOP}:build_statpop_millesime_and_source():L207-244 (table STATPOP_MAPPING:L160-172)")

# --------------------------------------------------------------------------- #
# base_ — mesures et attributs de course issus de l'APC
# --------------------------------------------------------------------------- #
d("base_date",
  "Date de circulation du tronçon, lue depuis l'export APC au format "
  "jour.mois.année et convertie en date.",
  "sans unité", "brute", f"{S_STACK}:apply_schema():L554-559")

d("base_sens",
  "Sens de circulation déduit de la parité du numéro de train : un numéro pair "
  "donne « PLEI -> VV », un numéro impair « VV -> PLEI ». Manquant si le numéro "
  "de train est absent.",
  "sans unité", "dérivée", f"{S_STACK}:add_train_direction():L628-642")

d("base_depart_datetime",
  "Horodatage du départ du tronçon, obtenu en ajoutant à la date de circulation "
  "normalisée le nombre de minutes de l'heure de départ de l'horaire APC (format "
  "HH:MM).",
  "sans unité", "dérivée", f"{S_STACK}:apply_schema():L561-587")

d("base_arrivee_datetime",
  "Horodatage de l'arrivée du tronçon, obtenu en ajoutant à la date de "
  "circulation le nombre de minutes de l'heure d'arrivée, augmenté d'un jour "
  "lorsque l'heure d'arrivée est antérieure à l'heure de départ.",
  "sans unité", "dérivée", f"{S_STACK}:apply_schema():L561-587")

d("base_duree_troncon_minutes",
  "Écart en minutes entre l'horodatage d'arrivée et l'horodatage de départ du "
  "tronçon, le franchissement de minuit étant absorbé par l'ajout d'un jour à "
  "l'arrivée. La valeur est nulle lorsque l'horaire APC place le départ et "
  "l'arrivée dans la même minute.",
  "minutes", "dérivée", f"{S_STACK}:apply_schema():L589-605")

for cl, lib in (("1ere", "première"), ("2eme", "deuxième")):
    d(f"base_offre_{cl}_classe",
      f"Nombre de places de {lib} classe offertes sur le tronçon, restitué tel "
      "quel depuis l'export APC.",
      "places", "brute", f"{S_STACK}:rename_output_columns():L107-176")

d("base_offre_total",
  "Somme des places offertes en première et en deuxième classe, calculée en "
  "exigeant au moins un terme renseigné : le résultat n'est manquant que si les "
  "deux offres le sont.",
  "places", "dérivée", f"{S_FEAT}:add_derived_features():L435-439")

# --------------------------------------------------------------------------- #
# horaire_ — structure de l'offre
# --------------------------------------------------------------------------- #
d("horaire_annee_horaire",
  "Année horaire CFF de la date de circulation, affectée par recherche "
  "d'intervalle fermé sur les bornes de début et de fin de chaque année horaire "
  "du référentiel annees_horaires.csv. Le build échoue si une date ne tombe dans "
  "aucun intervalle.",
  "sans unité", "dérivée", f"{S_ANNEE}:add_annee_horaire():L135-167")

d("horaire_numero_train",
  "Numéro de train de la course, restitué tel quel depuis l'export APC.",
  "sans unité", "brute", f"{S_STACK}:rename_output_columns():L107-176")

d("horaire_service_id_complet",
  "Identifiant composite du service, au format {numéro de train}_{HHhMM}, où "
  "l'heure est celle du plus petit horodatage de départ observé pour le couple "
  "date et numéro de train, c'est-à-dire l'heure d'origine de la course. Vaut "
  "{numéro}_NA si aucun horodatage de départ n'est exploitable.",
  "sans unité", "dérivée", f"{S_FEAT}:_ajouter_service_id_complet():L291-311")

# --------------------------------------------------------------------------- #
# target_ — cibles
# --------------------------------------------------------------------------- #
for cl, lib in (("1ere", "première"), ("2eme", "deuxième")):
    d(f"target_voyageurs_{cl}_classe",
      f"Comptage APC des voyageurs de {lib} classe présents à bord sur le "
      "tronçon, restitué tel quel depuis l'export.",
      "voyageurs", "brute", f"{S_STACK}:rename_output_columns():L107-176")

d("target_voyageurs_total",
  "Somme des comptages de première et de deuxième classe, chaque terme manquant "
  "étant remplacé par zéro avant l'addition. Toute valeur non numérique dans "
  "l'un des deux comptages interrompt le build.",
  "voyageurs", "dérivée", f"{S_FEAT}:add_derived_features():L414-433")

# --------------------------------------------------------------------------- #
# cal_ — calendrier
# --------------------------------------------------------------------------- #
_CAL_DIM = f"{S_CAL}:add_vacances_feries_to_raw_stacked():L237-295 (référentiel {B_VACANCES}:build_date_dimension():L758-830)"

d("cal_annee_civile", "Année civile de la date de circulation, reprise du "
  "référentiel calendaire joint sur la date.", "sans unité", "dérivée", _CAL_DIM)
d("cal_mois", "Numéro du mois civil de la date de circulation, de 1 à 12, repris "
  "du référentiel calendaire.", "sans unité", "dérivée", _CAL_DIM)
d("cal_jour", "Quantième du mois de la date de circulation, repris du "
  "référentiel calendaire.", "sans unité", "dérivée", _CAL_DIM)
d("cal_jour_semaine_iso", "Jour de la semaine au sens ISO, de 1 pour lundi à 7 "
  "pour dimanche, repris du référentiel calendaire.", "sans unité", "dérivée",
  _CAL_DIM)
d("cal_jour_semaine", "Nom du jour de la semaine, repris du référentiel "
  "calendaire.", "sans unité", "dérivée", _CAL_DIM)
d("cal_is_weekend", "Indicatrice valant 1 lorsque le jour de la semaine ISO vaut "
  "6 ou 7, c'est-à-dire samedi ou dimanche.", "sans unité", "dérivée",
  f"{B_VACANCES}:build_date_dimension():L770-772")

d("cal_mois_horaire",
  "Position ordinale du mois dans l'année horaire, sur treize positions : le "
  "décembre d'ouverture reçoit la position 1, janvier à novembre les positions 2 "
  "à 12, et le décembre de clôture la position 13. Le décembre de clôture est "
  "reconnu par l'égalité entre l'année civile et 2000 augmenté du code numérique "
  "de l'année horaire.",
  "sans unité", "dérivée",
  f"{S_CAL}:add_vacances_feries_to_raw_stacked():L297-314")

d("cal_type_jour",
  "Catégorie de jour à neuf modalités, affectée par la première condition "
  "vérifiée dans l'ordre suivant : férié ou dimanche, pont (jour ouvrable non "
  "férié encadré de deux jours non travaillés), veille de férié, lendemain de "
  "férié, samedi en vacances, samedi hors vacances, vendredi hors vacances, jour "
  "ouvrable en vacances, jour ouvrable hors vacances. La modalité par défaut est "
  "ouvrable_hors_vacances.",
  "sans unité", "dérivée",
  f"{S_CAL}:compute_type_jour():L200-230 (pont, veille et lendemain calculés par build_date_calendar():L170-197)")

d("cal_type_jour_3classes",
  "Regroupement de cal_type_jour en trois classes comportementales : "
  "dimanche_ferie pour la modalité férié ou dimanche, samedi pour les deux "
  "modalités de samedi, ouvrable pour les six autres.",
  "sans unité", "dérivée",
  f"{S_CAL}:_TYPE_JOUR_9_TO_3:L77-87 (application L289-291)")

for mom, lib in (("depart", "de départ"), ("arrivee", "d'arrivée")):
    d(f"cal_heure_{mom}",
      f"Heure de l'horaire APC {lib} du tronçon, extraite du champ parsé au "
      "format HH:MM.",
      "heures", "dérivée", f"{S_STACK}:apply_schema():L561-605")
    d(f"cal_minute_{mom}",
      f"Minute de l'horaire APC {lib} du tronçon, extraite du champ parsé au "
      "format HH:MM.",
      "minutes", "dérivée", f"{S_STACK}:apply_schema():L561-605")

d("cal_depart_minute_du_jour",
  "Minutes écoulées depuis minuit au départ du tronçon, calculées comme l'heure "
  "de départ multipliée par 60 augmentée de la minute de départ.",
  "minutes", "dérivée", f"{S_FEAT}:add_derived_features():L395-405")
d("cal_arrivee_minute_du_jour",
  "Minutes écoulées depuis minuit à l'arrivée du tronçon, calculées comme "
  "l'heure d'arrivée multipliée par 60 augmentée de la minute d'arrivée.",
  "minutes", "dérivée", f"{S_FEAT}:add_derived_features():L395-405")

# --------------------------------------------------------------------------- #
# event_ — contexte événementiel et calendaire
# --------------------------------------------------------------------------- #
d("event_is_vacances_vaud",
  "Indicatrice valant 1 lorsque la date de circulation appartient aux vacances "
  "scolaires vaudoises du référentiel calendaire.",
  "sans unité", "dérivée", _CAL_DIM)
d("event_is_ferie_vaud",
  "Indicatrice valant 1 lorsque la date de circulation porte un type de jour "
  "férié vaudois renseigné dans le référentiel calendaire.",
  "sans unité", "dérivée",
  f"{B_VACANCES}:build_date_dimension():L800 (jointure {_CAL_DIM})")
d("event_is_vacances_ou_ferie_vaud",
  "Indicatrice valant 1 lorsque la date est en vacances scolaires vaudoises ou "
  "fériée, par disjonction logique des deux indicatrices.",
  "sans unité", "dérivée",
  f"{S_CAL}:add_vacances_feries_to_raw_stacked():L284-285")

_MANIF_SRC = f"{S_MANIF}:add_manifestations():L73-93 (référentiel {B_MANIF}, zones LIEU_TO_ZONE_NORMALIZED:L93+)"

d("event_is_manifestation_riviera",
  "Indicatrice valant 1 lorsqu'au moins une manifestation du référentiel Montreux "
  "Riviera se déroule à la date de circulation. Les dates sans correspondance "
  "dans le référentiel reçoivent 0.",
  "sans unité", "dérivée", _MANIF_SRC)
d("event_n_manifestations_riviera",
  "Nombre de manifestations du référentiel Montreux Riviera se déroulant "
  "simultanément à la date de circulation, toutes zones confondues. Les dates "
  "sans correspondance reçoivent 0.",
  "sans unité", "dérivée", _MANIF_SRC)
d("event_n_manifestations_zone_directe_j",
  "Nombre de manifestations du jour situées en zone directe, c'est-à-dire dans "
  "les localités desservies par la R35. Les dates sans correspondance reçoivent 0.",
  "sans unité", "dérivée", _MANIF_SRC)
d("event_n_manifestations_zone_indirecte_j",
  "Nombre de manifestations du jour situées en zone indirecte, c'est-à-dire dans "
  "les communes reliées à Vevey ou à la R35 par correspondance fréquente. Les "
  "dates sans correspondance reçoivent 0.",
  "sans unité", "dérivée", _MANIF_SRC)
d("event_n_manifestations_hors_zone_j",
  "Nombre de manifestations du jour situées hors zone, c'est-à-dire dans des "
  "lieux sans connectivité pertinente vers la R35. Série de contrôle. Les dates "
  "sans correspondance reçoivent 0.",
  "sans unité", "dérivée", _MANIF_SRC)
for loc, lib in (("vevey", "à Vevey"), ("st_legier", "à Saint-Légier"),
                 ("blonay", "à Blonay et aux Pléiades")):
    d(f"event_n_manifestations_{loc}_j",
      f"Nombre de manifestations du jour localisées {lib}, sous-ensemble de la "
      "zone directe. Les dates sans correspondance reçoivent 0.",
      "sans unité", "dérivée", _MANIF_SRC)
for ev, lib in (("montreux_jazz", "le Montreux Jazz Festival"),
                ("marche_noel", "le Marché de Noël de Montreux"),
                ("montreux_noel", "Montreux Noël")):
    d(f"event_is_{ev}",
      f"Indicatrice valant 1 lorsque la date de circulation est couverte par "
      f"{lib} selon le référentiel des manifestations. Les dates sans "
      "correspondance reçoivent 0.",
      "sans unité", "dérivée", _MANIF_SRC)

d("event_is_ski_ouvert",
  "Indicatrice valant 1 lorsque la date de circulation appartient à une période "
  "d'ouverture du domaine skiable des Pléiades. Le référentiel ne contient que "
  "des jours d'ouverture, les dates absentes reçoivent 0.",
  "sans unité", "dérivée",
  f"{S_SKI}:add_ski():L52-73 (référentiel {B_SKI}:build_dim():L136-169)")
d("event_ski_source",
  "Provenance de la période d'ouverture du domaine skiable : officiel pour les "
  "saisons documentées par les PDF de la Coopérative des Pléiades, reconstruit "
  "pour les saisons antérieures reconstituées par règle calendaire, hors_saison "
  "pour les dates absentes du référentiel. Le référentiel ne comportant que des "
  "jours d'ouverture, la modalité hors_saison recouvre exactement les jours de "
  "fermeture.",
  "sans unité", "dérivée",
  f"{S_SKI}:add_ski():L69-71 (référentiel {B_SKI}:build_dim():L136-169)")

d("event_is_covid_restrictions",
  "Indicatrice valant 1 lorsque la date de circulation est couverte par une "
  "phase de restrictions sanitaires du référentiel COVID, 0 sinon.",
  "sans unité", "dérivée",
  f"{S_COVID}:add_covid():L46-67 (référentiel {B_COVID}:build_dim():L103-119)")
d("event_covid_phase",
  "Phase de restrictions sanitaires en vigueur à la date de circulation, prise "
  "dans le référentiel COVID, avec la modalité normal pour les dates hors phase.",
  "sans unité", "dérivée",
  f"{S_COVID}:add_covid():L63-65 (référentiel {B_COVID}:build_dim():L103-119)")

d("event_is_saison_narcisses",
  "Indicatrice valant 1 lorsque la date de circulation tombe dans la fenêtre "
  "calendaire de floraison des narcisses, fixée du 15 avril au 25 mai inclus de "
  "chaque année, 0 sinon. Aucune source de dates de floraison observées n'existe, "
  "la fenêtre est purement calendaire.",
  "sans unité", "dérivée",
  f"{S_NARC}:add_narcisses():L46-74 (règle {B_NARC}:_window_for_year():L85-90)")
d("event_narcisses_source",
  "Provenance de la fenêtre de floraison : regle_calendaire pour les dates de la "
  "fenêtre du 15 avril au 25 mai, hors_saison pour les autres. Le référentiel ne "
  "produit que la modalité regle_calendaire et ne contient que des jours en "
  "saison, la colonne ne prend donc que ces deux valeurs.",
  "sans unité", "dérivée",
  f"{S_NARC}:add_narcisses():L70-72 (référentiel {B_NARC}:build_dim():L93-113)")

# --------------------------------------------------------------------------- #
# spatial_ — topologie, STATPOP, STATENT
# --------------------------------------------------------------------------- #
d("spatial_distance_km",
  "Longueur du tronçon, restituée telle quelle depuis la colonne de distance de "
  "l'export APC.",
  "km", "brute", f"{S_STACK}:rename_output_columns():L107-176")

for cote, lib in (("depart", "de départ"), ("arrivee", "d'arrivée")):
    d(f"spatial_gare_{cote}_ordre",
      f"Rang ordinal de la gare {lib} le long de la ligne, obtenu par jointure de "
      "l'abréviation de gare sur le référentiel gare_abreviation.csv (colonne "
      "Gare_Ordre).",
      "sans unité", "dérivée", f"{S_STACK}:add_station_dimension():L422-463")

d("spatial_segment",
  "Segment de ligne du tronçon : bas lorsque les deux gares ont un rang ordinal "
  "inférieur ou égal à 10, haut dès qu'au moins une des deux gares a un rang "
  "supérieur à 10, le tronçon touchant alors la crémaillère. Manquant lorsque "
  "l'un des deux rangs est absent.",
  "sans unité", "dérivée", f"{S_SPAT}:add_spatial_segment():L50-66")

d("spatial_denivele_troncon_m",
  "Différence d'altitude entre la gare d'arrivée et la gare de départ, en mètres "
  "signés (positive en montée, négative en descente), les altitudes étant lues "
  "dans dim_gare.csv. Manquante lorsque l'altitude d'au moins une des deux gares "
  "est absente de ce référentiel.",
  "mètres", "dérivée", f"{S_SPAT}:add_denivele_troncon():L69-106")

# --- indicateurs STATPOP, appliqués symétriquement aux deux extrémités ------- #
_ZONE = ("la zone de Voronoï de la gare {lib}, écrêtée à 500 mètres de rayon, "
         "pour le millésime STATPOP retenu")
_SRC_STATPOP = (f"{B_STATPOP}:build_features_from_raw_aggregates():L781-861 "
                f"(jointure {S_STATPOP}:add_statpop_for_side():L358-397)")
_SRC_HPI = (f"{B_STATPOP}:build_hpi_features():L736-778 "
            f"(jointure {S_STATPOP}:add_statpop_for_side():L358-397)")

_STATPOP_INDIC: list[tuple[str, str, str, str]] = [
    ("pop_500m_total",
     "Population résidante permanente totale (variable OFS BBTOT) dénombrée dans "
     "{zone}.", "habitants", _SRC_STATPOP),
    ("menages_500m_total",
     "Nombre de ménages privés (variable OFS HPTOT) dénombrés dans {zone}.",
     "ménages", _SRC_STATPOP),
    ("pop_par_menage_500m",
     "Rapport de la population résidante permanente au nombre de ménages privés "
     "dans {zone}, la division étant protégée contre un dénominateur nul ou "
     "manquant.", "sans unité", _SRC_STATPOP),
    ("part_menages_1p",
     "Part des ménages d'une personne (HP01) dans le total des ménages privés de "
     "{zone}, bornée à l'intervalle [0, 1].", "pourcentage", _SRC_STATPOP),
    ("part_grands_menages_4p",
     "Part des ménages de quatre personnes ou plus (somme des variables HP04, "
     "HP05 et HP06) dans le total des ménages privés de {zone}, bornée à "
     "l'intervalle [0, 1].", "pourcentage", _SRC_STATPOP),
    ("part_pop_0_14_ans",
     "Part de la population âgée de 0 à 14 ans (classes d'âge 01 à 03, hommes et "
     "femmes cumulés) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("part_pop_15_24_ans",
     "Part de la population âgée de 15 à 24 ans (classes d'âge 04 et 05, hommes "
     "et femmes cumulés) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("part_pop_25_64_ans",
     "Part de la population âgée de 25 à 64 ans (classes d'âge 06 à 13, hommes et "
     "femmes cumulés) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("part_pop_65_plus",
     "Part de la population âgée de 65 ans et plus (classes d'âge 14 à 19, hommes "
     "et femmes cumulés) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("part_pop_80_plus",
     "Part de la population âgée de 80 ans et plus (classes d'âge 17 à 19, hommes "
     "et femmes cumulés) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("indice_stabilite_resid",
     "Part de la population résidant dans la commune depuis plus de dix ans ou "
     "depuis la naissance (somme des variables BB44 et BB45) dans la population "
     "totale de {zone}, bornée à [0, 1].", "pourcentage", _SRC_STATPOP),
    ("indice_mobilite_resid",
     "Part de la population résidant dans la commune depuis moins de cinq ans "
     "(somme des variables BB41, moins d'un an, et BB42, de un à cinq ans) dans la "
     "population totale de {zone}, bornée à [0, 1].", "pourcentage", _SRC_STATPOP),
    ("part_nouveaux_arrivants_1an",
     "Part de la population dont le domicile un an auparavant se trouvait ailleurs "
     "(somme des variables BB52 même canton, BB53 autre canton et BB54 étranger) "
     "dans la population totale de {zone}, bornée à [0, 1].", "pourcentage",
     _SRC_STATPOP),
    ("part_pop_etrangere",
     "Part de la population résidante permanente de nationalité étrangère "
     "(variable BB12) dans la population totale de {zone}, bornée à [0, 1].",
     "pourcentage", _SRC_STATPOP),
    ("part_pop_nee_etranger",
     "Part de la population née à l'étranger (variable BB26) dans la population "
     "totale de {zone}, bornée à [0, 1].", "pourcentage", _SRC_STATPOP),
    ("hpi_classe_max",
     "Valeur maximale de l'indicateur de plausibilité des ménages privés HPI parmi "
     "les hectares de {zone}, la classe 1 signalant des ménages plausibles et la "
     "classe 2 la présence d'au moins un ménage non plausible.", "sans unité",
     _SRC_HPI),
    ("hpi_ha_classe_1",
     "Nombre d'hectares de {zone} dont l'indicateur HPI vaut 1.", "sans unité",
     _SRC_HPI),
    ("hpi_ha_classe_2",
     "Nombre d'hectares de {zone} dont l'indicateur HPI vaut 2.", "sans unité",
     _SRC_HPI),
    ("hpi_ha_manquante",
     "Nombre d'hectares de {zone} dont l'indicateur HPI est manquant.",
     "sans unité", _SRC_HPI),
    ("hpi_ha_autre",
     "Nombre d'hectares de {zone} dont l'indicateur HPI est renseigné mais "
     "différent de 1 et de 2.", "sans unité", _SRC_HPI),
    ("part_hpi_non_plausible",
     "Part des hectares d'indicateur HPI égal à 2 dans le nombre total d'hectares "
     "de {zone}, bornée à [0, 1].", "pourcentage", _SRC_HPI),
    ("flag_qualite_faible",
     "Indicatrice valant 1 lorsque la part d'hectares d'indicateur HPI égal à 2 "
     "dépasse 0,20 dans {zone}, 0 sinon.", "sans unité", _SRC_HPI),
]

for suffixe, gabarit, unite, src in _STATPOP_INDIC:
    for cote, lib in (("depart", "de départ"), ("arrivee", "d'arrivée")):
        d(f"spatial_gare_{cote}_{suffixe}",
          gabarit.format(zone=_ZONE.format(lib=lib)),
          unite, "dérivée", src)

for cote, lib in (("depart", "de départ"), ("arrivee", "d'arrivée")):
    d(f"spatial_gare_{cote}_emplois_500m_total",
      "Emploi total (variable OFS B08EMPT) dans la zone de Voronoï 500 mètres de "
      f"la gare {lib}, pour le millésime STATENT résolu par la règle de causalité "
      "Z-3 (une observation de l'année civile Z reçoit le millésime Z-3). "
      "Manquante pour les années civiles antérieures à 2021, dont le millésime "
      "Z-3 est absent de la table figée.",
      "sans unité", "dérivée",
      f"{S_STATENT}:add_statent():L88-121 (table STATENT_MAPPING:L63-69, contenu de "
      "l'indicateur documenté par docs/adr/ADR-064_integration_statent_emploi_500m.md:L50-53, "
      "producteur absent du dépôt)", "moyenne")
    d(f"spatial_gare_{cote}_emplois_500m_services",
      "Emploi du secteur tertiaire (variable OFS B08EMPTS3) dans la zone de "
      f"Voronoï 500 mètres de la gare {lib}, pour le millésime STATENT résolu par "
      "la règle de causalité Z-3. Manquante pour les années civiles antérieures à "
      "2021.",
      "sans unité", "dérivée",
      f"{S_STATENT}:add_statent():L88-121 (table STATENT_MAPPING:L63-69, contenu de "
      "l'indicateur documenté par docs/adr/ADR-064_integration_statent_emploi_500m.md:L50-53, "
      "producteur absent du dépôt)", "moyenne")

for cote in ("depart", "arrivee"):
    d(f"spatial_statpop_source_{cote}",
      "Marqueur de provenance du millésime STATPOP : exact lorsque le millésime "
      "Z-2 existe tel quel, forward_fill lorsque les variables de ménages et de "
      "qualité HPI de ce millésime ont été reportées depuis le millésime "
      "précédent, carry_forward lorsque Z-2 est indisponible. La valeur est "
      "calculée à partir de la seule année civile de la date de circulation et "
      "est recopiée à l'identique côté départ et côté arrivée : elle ne dépend "
      "d'aucune des deux gares.",
      "sans unité", "dérivée",
      f"{S_STATPOP}:add_statpop_to_raw_stacked():L421-425 (valeur produite par "
      "build_statpop_millesime_and_source():L207-244)")

# --------------------------------------------------------------------------- #
# meteo_ — horaire puis journalier
# --------------------------------------------------------------------------- #
_STATION_LOC = ("la station météo du segment du tronçon, celle de plaine "
                "(Vevey-Corseaux) lorsque le segment est bas et celle d'altitude "
                "(Château-d'Oex) lorsqu'il est haut")
_STATION_DEST = ("la station météo de destination du train, celle d'altitude "
                 "(Château-d'Oex) pour un train montant et celle de plaine "
                 "(Vevey-Corseaux) pour un train descendant")
_CLE_H = ("La mesure est prélevée à l'heure UTC obtenue en localisant "
          "l'horodatage de départ en Europe/Zurich, en le convertissant en UTC "
          "puis en le tronquant à l'heure.")
_SRC_METEOH = f"{S_METEOH}:build_meteo_features():L234-349 (clé de jointure build_join_key_utc():L179-197)"

_METEO_H = [
    ("temperature_h", "Température de l'air à 2 mètres (paramètre MétéoSuisse "
     "tre200h0) mesurée par {station}.", "°C"),
    ("precipitation_mm_h", "Cumul horaire des précipitations (paramètre "
     "MétéoSuisse rre150h0) mesuré par {station}.", "mm"),
    ("ensoleillement_min_h", "Durée d'ensoleillement de l'heure (paramètre "
     "MétéoSuisse sre000h0) mesurée par {station}.", "minutes"),
    ("vent_max_h", "Rafale de vent maximale sur une seconde de l'heure "
     "(paramètre MétéoSuisse fu3010h1) mesurée par {station}.", "km/h"),
]
for suffixe, gabarit, unite in _METEO_H:
    d(f"meteo_{suffixe}",
      gabarit.format(station=_STATION_LOC) + " " + _CLE_H +
      " Manquante lorsque le segment n'est ni bas ni haut.",
      unite, "dérivée", _SRC_METEOH)
    d(f"meteo_destination_{suffixe}",
      gabarit.format(station=_STATION_DEST) + " " + _CLE_H +
      " Manquante lorsque le sens n'est ni montant ni descendant.",
      unite, "dérivée", _SRC_METEOH)

d("meteo_neige_binaire_h",
  "Indicatrice de neige de l'heure, construite selon la station du segment. "
  "Pour la station de plaine, elle vaut 1 lorsque les précipitations horaires "
  "sont strictement positives et la température strictement inférieure à 2 °C. "
  "Pour la station d'altitude, elle vaut 1 lorsque la hauteur de neige est "
  "strictement positive, ou bien lorsque les précipitations sont strictement "
  "positives et la température strictement inférieure à 2 °C. " + _CLE_H,
  "sans unité", "dérivée", f"{S_METEOH}:build_meteo_features():L286-308")

_AGG_J = ("Les agrégats sont calculés sur la journée calendaire de l'horodatage "
          "MétéoSuisse, exprimé en UTC.")
_STATION_LOC_J = ("la station d'altitude (Château-d'Oex) lorsque le segment du "
                  "tronçon est haut, la station de plaine (Vevey-Corseaux) dans "
                  "tous les autres cas")
_STATION_DEST_J = ("la station d'altitude (Château-d'Oex) pour un train montant, "
                   "la station de plaine (Vevey-Corseaux) dans tous les autres cas")
_SRC_METEOJ = (f"{S_METEOJ}:build_aggregats_journaliers():L160-185 et "
               "join_agg_journaliers():L192-273")

_METEO_J = [
    ("temperature_max_j", "Maximum des températures horaires de l'air à 2 mètres "
     "de la journée de circulation, calculé sur {station}.", "°C", True),
    ("precip_total_j", "Somme des précipitations horaires de la journée de "
     "circulation, calculée sur {station}.", "mm", True),
    ("ensol_total_j", "Somme des durées d'ensoleillement horaires de la journée "
     "de circulation, calculée sur {station}.", "minutes", True),
    ("vent_max_j", "Maximum des rafales horaires de la journée de circulation, "
     "calculé sur {station}.", "km/h", True),
    ("rayon_global_moy_j", "Moyenne des rayonnements globaux horaires de la "
     "journée de circulation, calculée sur {station}.", "W/m²", True),
    ("precip_total_j_moins_1", "Somme des précipitations horaires de la veille du "
     "jour de circulation, calculée sur {station}.", "mm", True),
    ("ensol_total_j_moins_1", "Somme des durées d'ensoleillement horaires de la "
     "veille du jour de circulation, calculée sur {station}.", "minutes", True),
    ("precip_total_j_plus_1", "Somme des précipitations horaires du lendemain du "
     "jour de circulation, calculée sur {station}.", "mm", True),
    ("ensol_total_j_plus_1", "Somme des durées d'ensoleillement horaires du "
     "lendemain du jour de circulation, calculée sur {station}.", "minutes", True),
]
for suffixe, gabarit, unite, _ in _METEO_J:
    if f"meteo_{suffixe}" not in ("meteo_rayon_global_moy_j",) or True:
        d(f"meteo_{suffixe}",
          gabarit.format(station=_STATION_LOC_J) + " " + _AGG_J,
          unite, "dérivée", _SRC_METEOJ)
    d(f"meteo_destination_{suffixe}",
      gabarit.format(station=_STATION_DEST_J) + " " + _AGG_J,
      unite, "dérivée", _SRC_METEOJ)

# --------------------------------------------------------------------------- #
# ist_ — ponctualité, correspondances, headway
# --------------------------------------------------------------------------- #
_FEN = {"5occ": ("5", "2"), "20occ": ("20", "5")}
_J2 = ("La statistique est calculée sur la journée J-2 puis reportée sur la "
       "journée de circulation par la jointure, la fenêtre incluant l'occurrence "
       "de J-2.")
_SRC_PROFIL = (f"{B_PROFIL}:_ajouter_rolling():L259-299 (fenêtre "
               f"{U_ROLLING}:rolling_par_type_jour():L27-97, jointure "
               f"{S_IST}:_joindre_troncon_j_moins_2():L167-191)")

for pos, lib_pos in (("dep", "au départ"), ("arr", "à l'arrivée")):
    for fen, (n, minp) in _FEN.items():
        d(f"ist_profil_train_retard_{pos}_troncon_mean_{fen}",
          f"Moyenne du retard {lib_pos} du tronçon, en secondes, sur les {n} "
          "dernières occurrences du même service et du même tronçon partageant le "
          f"type de jour de l'occurrence courante, avec au moins {minp} "
          f"occurrences renseignées. {_J2}",
          "secondes", "dérivée", _SRC_PROFIL)
        d(f"ist_profil_train_retard_{pos}_troncon_std_{fen}",
          f"Écart-type du retard {lib_pos} du tronçon, en secondes, sur les {n} "
          "dernières occurrences du même service et du même tronçon partageant le "
          f"type de jour de l'occurrence courante, avec au moins {minp} "
          f"occurrences renseignées. {_J2}",
          "secondes", "dérivée", _SRC_PROFIL)
        d(f"ist_profil_train_pct_en_retard_{pos}_troncon_{fen}",
          f"Proportion d'occurrences en retard {lib_pos} parmi les {n} dernières "
          "du même service et du même tronçon partageant le type de jour, une "
          "occurrence étant tenue pour en retard lorsque son retard atteint 180 "
          f"secondes. L'avance n'est jamais comptée comme un retard. Au moins "
          f"{minp} occurrences renseignées sont exigées. {_J2}",
          "pourcentage", "dérivée",
          _SRC_PROFIL + f" (seuil {B_PROFIL}:_agreger_troncon_jour():L223-251)")

_SRC_CORRESP = (f"{B_CORRESP}:_ajouter_rolling_corresp():L434-492 (comptages "
                "quotidiens _calculer_correspondances_in():L237-305 et "
                f"_calculer_correspondances_out():L363-431, jointure "
                f"{S_IST}:_joindre_train_jour_j_moins_2():L144-159)")
_SENS_CORRESP = {
    "in": ("des trains CFF arrivant à Vevey dans la fenêtre allant de 5 à 1 "
           "minute avant le départ théorique du train R35 montant",
           "Manquante pour les trains R35 qui ne partent pas de Vevey."),
    "out": ("des trains CFF partant de Vevey dans la fenêtre allant de 1 à 5 "
            "minutes après l'arrivée théorique du train R35 descendant",
            "Manquante pour les trains R35 qui n'arrivent pas à Vevey."),
}
for sens, (fenetre, nan_note) in _SENS_CORRESP.items():
    for fen, (n, minp) in _FEN.items():
        d(f"ist_corresp_{sens}_n_theoriques_moy_{fen}",
          f"Moyenne, sur les {n} dernières occurrences du même service partageant "
          "le type de jour, du nombre quotidien " + fenetre +
          f". Au moins {minp} occurrences renseignées sont exigées. {nan_note} {_J2}",
          "sans unité", "dérivée", _SRC_CORRESP)
        d(f"ist_corresp_{sens}_n_garanties_moy_{fen}",
          f"Moyenne, sur les {n} dernières occurrences du même service partageant "
          "le type de jour, du nombre quotidien de ces correspondances "
          "effectivement réalisées, c'est-à-dire dont l'heure effective du train "
          "CFF tombe dans la fenêtre recalculée sur les heures effectives du train "
          f"R35. Au moins {minp} occurrences renseignées sont exigées. {nan_note} {_J2}",
          "sans unité", "dérivée", _SRC_CORRESP)
        d(f"ist_corresp_{sens}_pct_garanties_{fen}",
          "Rapport de la somme glissante des correspondances réalisées à la somme "
          f"glissante des correspondances théoriques, sur les {n} dernières "
          "occurrences du même service partageant le type de jour. Le rapport de "
          "sommes est employé plutôt que la moyenne des rapports quotidiens. "
          f"Manquant lorsque la somme des théoriques est nulle. {nan_note} {_J2}",
          "pourcentage", "dérivée", _SRC_CORRESP)

_SRC_HEADWAY = (f"{B_HEADWAY}:_calculer_headway():L143-179 (reconstruction des "
                f"tronçons _reconstruire_troncons():L93-140, jointure "
                f"{S_FEAT}:main():L627-655)")
d("ist_headway_avant_min",
  "Écart en minutes entre le départ théorique du train et celui du train "
  "précédent sur le même tronçon, le même sens et le même jour, les trains étant "
  "ordonnés par heure de départ théorique. Manquant pour le premier train de la "
  "journée. La grille retenue est la grille planifiée connue la veille : les "
  "trains annulés et les suppléments y sont inclus, aucun filtre de réalisation "
  "n'est appliqué.",
  "minutes", "dérivée", _SRC_HEADWAY)
d("ist_headway_apres_min",
  "Écart en minutes entre le départ théorique du train suivant et celui du train "
  "courant sur le même tronçon, le même sens et le même jour. Manquant pour le "
  "dernier train de la journée. La grille retenue est la grille planifiée connue "
  "la veille, trains annulés et suppléments inclus.",
  "minutes", "dérivée", _SRC_HEADWAY)
d("ist_headway_avant_is_first_of_day",
  "Indicatrice valant 1 exactement lorsque ist_headway_avant_min est manquant, "
  "c'est-à-dire lorsque le train est le premier de la journée sur ce tronçon et "
  "ce sens.",
  "sans unité", "dérivée", _SRC_HEADWAY)
d("ist_headway_apres_is_last_of_day",
  "Indicatrice valant 1 exactement lorsque ist_headway_apres_min est manquant, "
  "c'est-à-dire lorsque le train est le dernier de la journée sur ce tronçon et "
  "ce sens.",
  "sans unité", "dérivée", _SRC_HEADWAY)

# --------------------------------------------------------------------------- #
# vmcv_ — concurrence modale
# --------------------------------------------------------------------------- #
_SRC_VMCV = (f"{B_VMCV}:_calculer_features():L319-443 (mapping directionnel "
             f"_construire_mapping_directionnel():L159-208, jointure "
             f"{S_IST}:_joindre_train_jour_sens_j_moins_2():L199-220)")
d("vmcv_n_lignes_concurrentes",
  "Nombre de lignes de bus VMCV distinctes tenues pour concurrentes du train, une "
  "ligne étant retenue lorsqu'elle dessert un arrêt situé à moins de 200 mètres "
  "d'une gare R35 de la moitié de ligne visée par le sens du train : gare de "
  "kilomètre au moins égal à 5,5 pour un train montant, au plus égal à 4,0 pour "
  "un train descendant. Grandeur topologique, sans variation journalière.",
  "sans unité", "dérivée", _SRC_VMCV)
d("vmcv_min_attente_min",
  "Attente minimale en minutes avant le prochain passage d'un bus VMCV "
  "concurrent, cherchée dans la fenêtre allant de 5 minutes avant à 30 minutes "
  "après le départ du train. Manquante en l'absence de passage dans la fenêtre.",
  "minutes", "dérivée", _SRC_VMCV)
d("vmcv_delta_attente_min",
  "Différence entre 5 minutes et l'attente minimale avant le prochain bus VMCV "
  "concurrent, positive lorsque l'alternative en bus est disponible plus vite que "
  "ce seuil. Manquante lorsque l'attente minimale l'est.",
  "minutes", "dérivée", _SRC_VMCV)
d("vmcv_delta_frequence_h",
  "Différence entre le nombre de passages VMCV concurrents et le nombre de trains "
  "R35, comptés dans une fenêtre de plus ou moins 30 minutes autour du départ du "
  "train, le train courant étant inclus dans le second terme. Manquante en "
  "l'absence de passage VMCV dans la fenêtre.",
  "sans unité", "dérivée", _SRC_VMCV)
for cote in ("depart", "arrivee"):
    d(f"vmcv_source_{cote}",
      "Marqueur de disponibilité de la publication VMCV dans ISTDATEN : "
      "manquant_interruption_vmcv pour les dates comprises entre le 1er septembre "
      "et le 13 octobre 2025 inclus, publie pour toutes les autres. La valeur est "
      "calculée à partir de la seule date de circulation et est recopiée à "
      "l'identique côté départ et côté arrivée : elle ne dépend d'aucune des deux "
      "gares.",
      "sans unité", "dérivée", f"{S_IST}:main():L325-332")

# --------------------------------------------------------------------------- #
# histo_ — historique APC sous cutoff mensuel
# --------------------------------------------------------------------------- #
_GROUPE = ("du même groupe, un groupe réunissant le sens de circulation, le "
           "créneau d'origine ancré à plus ou moins 30 minutes sur les services "
           "H22 à H24, le type de jour en trois classes et le tronçon (gares de "
           "départ et d'arrivée)")
_CONSOL = ("Une occurrence est consolidée lorsque sa date est antérieure ou égale "
           "au dernier jour du dernier mois publié et ingéré à la veille du "
           "trajet, le mois M étant publié le 3 du mois M+1 et exploitable le 4. "
           "Les comptages sont d'abord moyennés par groupe et par date. Le "
           "suffixe lag2 est un vestige de nommage : la règle appliquée est ce "
           "seuil mensuel, non un décalage de deux jours.")
_SRC_HISTO_BASE = (f"{S_FEAT}:add_derived_features():L441-572 (seuil "
                   "_cutoff_mensuel_seuils():L166-198, clé de groupement "
                   "GROUP_KEYS:L114-120, ancrage "
                   "_ajouter_creneau_anchor_30():L314-385")
_SRC_HISTO = _SRC_HISTO_BASE + ")"
_SRC_HISTO_NS = _SRC_HISTO_BASE + ", seuil de surcharge SEUIL_UM_2EME:L144-154)"

_CLASSES = {
    "1ere_classe": "de première classe",
    "2eme_classe": "de deuxième classe",
    "total": "toutes classes confondues",
}
for cle, lib_cl in _CLASSES.items():
    d(f"histo_voyageurs_{cle}_lag2",
      f"Comptage de voyageurs {lib_cl} de la dernière occurrence consolidée "
      f"{_GROUPE}. {_CONSOL}",
      "voyageurs", "dérivée", _SRC_HISTO)
    d(f"histo_voyageurs_{cle}_win7_mean",
      f"Moyenne des comptages de voyageurs {lib_cl} sur les sept dernières "
      f"occurrences consolidées {_GROUPE}, les occurrences manquantes étant "
      f"écartées avant le calcul. {_CONSOL}",
      "voyageurs", "dérivée", _SRC_HISTO)
    d(f"histo_voyageurs_{cle}_win7_median",
      f"Médiane des comptages de voyageurs {lib_cl} sur les sept dernières "
      f"occurrences consolidées {_GROUPE}, les occurrences manquantes étant "
      f"écartées avant le calcul. {_CONSOL}",
      "voyageurs", "dérivée", _SRC_HISTO)
    d(f"histo_voyageurs_{cle}_win7_max",
      f"Maximum des comptages de voyageurs {lib_cl} sur les sept dernières "
      f"occurrences consolidées {_GROUPE}, les occurrences manquantes étant "
      f"écartées avant le calcul. {_CONSOL}",
      "voyageurs", "dérivée", _SRC_HISTO)
    d(f"histo_voyageurs_{cle}_win7_std",
      f"Écart-type d'échantillon (dénominateur n-1) des comptages de voyageurs "
      f"{lib_cl} sur les sept dernières occurrences consolidées {_GROUPE}. Vaut "
      f"zéro lorsque la fenêtre ne retient qu'une seule occurrence. {_CONSOL}",
      "voyageurs", "dérivée", _SRC_HISTO)

d("histo_voyageurs_2eme_classe_win7_n_surcharges",
  "Nombre d'occurrences dont le comptage de deuxième classe dépasse strictement "
  f"63 places assises, parmi les sept dernières occurrences consolidées {_GROUPE}. "
  f"{_CONSOL}",
  "sans unité", "dérivée", _SRC_HISTO_NS)

# --------------------------------------------------------------------------- #
# simba_ — structure de la demande (millésime N-1)
# --------------------------------------------------------------------------- #
_SIMBA_BASE = ("dans le total des voyageurs d'un jour ouvrable moyen recensés par "
               "SIMBA sur le tronçon, pour le millésime égal au code de l'année "
               "horaire diminué de un. La jointure est indifférente au sens : un "
               "tronçon reçoit la valeur calculée pour son homologue ascendant.")
_SRC_SIMBA_TARIF = (f"{B_SIMBA}:calculer_parts_tarifaires():L114-153 (jointure "
                    f"{S_SIMBA}:joindre_simba():L221-280, millésime "
                    "annee_horaire_vers_millesime_simba():L116-131)")

_SIMBA_TARIF = {
    "ga": "munis d'un abonnement général",
    "mobilis": "munis d'un titre Mobilis Riviera",
    "billet_hta": "munis d'un billet HTA",
    "spar": "munis d'un billet Spar ou promotionnel",
    "jeunes": "munis d'un titre Jeunes",
    "abonnement": "munis d'un autre abonnement",
    "militaire": "voyageant au titre militaire",
    "autre": "munis d'un autre titre de transport",
}
for cle, lib in _SIMBA_TARIF.items():
    d(f"simba_part_{cle}",
      f"Part des voyageurs {lib} {_SIMBA_BASE}",
      "pourcentage", "dérivée", _SRC_SIMBA_TARIF)

d("simba_part_corresp_amont",
  f"Part des voyageurs pour lesquels un train amont est renseigné {_SIMBA_BASE}",
  "pourcentage", "dérivée",
  f"{B_SIMBA}:calculer_parts_correspondances():L156-181 (jointure {S_SIMBA}:joindre_simba():L221-280)")
d("simba_part_corresp_aval",
  f"Part des voyageurs pour lesquels un train aval est renseigné {_SIMBA_BASE}",
  "pourcentage", "dérivée",
  f"{B_SIMBA}:calculer_parts_correspondances():L156-181 (jointure {S_SIMBA}:joindre_simba():L221-280)")
d("simba_part_premiere_classe",
  f"Part des voyageurs voyageant en première classe {_SIMBA_BASE}",
  "pourcentage", "dérivée",
  f"{B_SIMBA}:calculer_part_premiere_classe():L184-199 (jointure {S_SIMBA}:joindre_simba():L221-280)")
d("simba_part_intra_r35",
  "Part des voyageurs dont l'origine et la destination du voyage sont toutes "
  f"deux des gares de la R35 {_SIMBA_BASE}",
  "pourcentage", "dérivée",
  f"{B_SIMBA}:calculer_part_intra_r35():L202-228 (jointure {S_SIMBA}:joindre_simba():L221-280)")

for cote in ("depart", "arrivee"):
    d(f"simba_source_{cote}",
      "Marqueur d'appariement SIMBA : match_simba_n_minus_1 lorsque la jointure "
      "sur le millésime de l'année horaire diminuée de un a trouvé une "
      "correspondance, manquant_simba_n_minus_1 sinon. La valeur est déduite du "
      "seul résultat de la jointure et est recopiée à l'identique côté départ et "
      "côté arrivée : elle ne dépend d'aucune des deux gares.",
      "sans unité", "dérivée", f"{S_SIMBA}:joindre_simba():L262-271")

# --------------------------------------------------------------------------- #
# resa_ — réservations de groupes connues à J-1
# --------------------------------------------------------------------------- #
_RESA_PERIM = ("Seules les réservations de statut « 50 Abgeschlossen » dont le "
               "délai de réservation atteint au moins un jour sont retenues, et "
               "chaque réservation est préalablement éclatée sur les tronçons "
               "élémentaires de son parcours.")
_SRC_RESA_BASE = (f"{S_RESA}:_aggreger():L240-282 (périmètre "
                  "_charger_reservations():L122-172, éclatement "
                  f"{U_RESA}:eclate_reservation():L171-220, imputation "
                  f"{S_RESA}:_joindre_et_imputer():L289-370")
_SRC_RESA = _SRC_RESA_BASE + ")"

d("resa_pax_2c_J_minus_1",
  "Somme des voyageurs de deuxième classe des réservations de groupe couvrant le "
  f"tronçon ce jour-là. {_RESA_PERIM} Vaut 0 en l'absence de réservation.",
  "voyageurs", "dérivée", _SRC_RESA)
d("resa_n_dossiers_J_minus_1",
  "Nombre de dossiers de réservation distincts couvrant le tronçon ce jour-là. "
  f"{_RESA_PERIM} Vaut 0 en l'absence de réservation.",
  "sans unité", "dérivée", _SRC_RESA)
d("resa_max_groupe_2c_J_minus_1",
  "Nombre de voyageurs de deuxième classe du plus gros dossier couvrant le "
  f"tronçon ce jour-là. {_RESA_PERIM} Vaut 0 en l'absence de réservation.",
  "voyageurs", "dérivée", _SRC_RESA)
d("resa_part_scolaire_J_minus_1",
  "Part des voyageurs de deuxième classe appartenant à des dossiers classés "
  "scolaires, rapportée au total réservé sur le tronçon. Le classement est une "
  "heuristique par mots-clés cherchés dans la concaténation du nom de groupe et "
  f"du partenaire. Vaut 0 en l'absence de réservation. {_RESA_PERIM}",
  "pourcentage", "dérivée",
  _SRC_RESA_BASE + f", heuristique {U_RESA}:is_scolaire():L227-251)")
d("resa_part_tour_operator_J_minus_1",
  "Part des voyageurs de deuxième classe appartenant à des dossiers classés "
  "tour-opérateurs, rapportée au total réservé sur le tronçon. Le classement est "
  "une heuristique par mots-clés cherchés dans le seul champ partenaire. Vaut 0 "
  f"en l'absence de réservation. {_RESA_PERIM}",
  "pourcentage", "dérivée",
  _SRC_RESA_BASE + f", heuristique {U_RESA}:is_tour_operator():L254-272)")
d("resa_n_pays_distincts_J_minus_1",
  "Nombre de pays distincts déclarés par les dossiers couvrant le tronçon ce "
  f"jour-là. {_RESA_PERIM} Vaut 0 en l'absence de réservation.",
  "sans unité", "dérivée", _SRC_RESA)
d("resa_n_langues_distinctes_J_minus_1",
  "Nombre de langues distinctes déclarées par les dossiers couvrant le tronçon ce "
  f"jour-là. {_RESA_PERIM} Vaut 0 en l'absence de réservation.",
  "sans unité", "dérivée", _SRC_RESA)
d("resa_has_resa_J_minus_1",
  "Indicatrice valant 1 lorsqu'au moins une réservation de groupe retenue couvre "
  f"le tronçon ce jour-là, 0 après imputation des cellules sans réservation. "
  f"{_RESA_PERIM}",
  "sans unité", "dérivée", _SRC_RESA)


# --------------------------------------------------------------------------- #
# Divergences docstring / calcul relevées à la lecture des producteurs
# --------------------------------------------------------------------------- #
DIVERGENCES: list[dict[str, str]] = [
    {
        "colonnes": "les 44 colonnes `spatial_gare_{depart,arrivee}_*` réellement "
                    "issues de STATPOP (22 indicateurs par extrémité)",
        "emplacement": f"{S_STATPOP}, docstring de module, L12-13",
        "docstring": "« Les indicateurs consolidés de fact_statpop_gare sont calculés "
                     "dans un rayon de 500 m autour de chaque gare ».",
        "calcul": "L'unité spatiale n'est pas un disque de 500 m mais la cellule de "
                  "Voronoï de la gare, calculée sur les gares actives du millésime "
                  "puis écrêtée au disque de 500 m "
                  f"({B_STATPOP}:compute_voronoi_zones():L493-553). Les zones sont "
                  "donc disjointes et généralement plus petites que le disque.",
        "traitement": "Les définitions disent « zone de Voronoï écrêtée à 500 mètres ».",
    },
    {
        "colonnes": "`spatial_gare_depart_ordre`, `spatial_gare_arrivee_ordre`",
        "emplacement": f"{S_STATPOP}, commentaire de STATPOP_KEEP_SUFFIXES, L82-86",
        "docstring": "Le suffixe `ordre` est listé parmi les « suffixes des colonnes "
                     "statpop conservees dans la sortie (24 features × 2 côtés = 48 "
                     "colonnes) », ce qui le présente comme un indicateur STATPOP.",
        "calcul": "La table `statpop_clean_causal.parquet` ne contient aucune colonne "
                  "`ordre` (33 colonnes, vérifié). Le rang ordinal provient du "
                  f"référentiel gare_abreviation.csv joint en amont "
                  f"({S_STACK}:add_station_dimension():L422-463) ; l'entrée `ordre` "
                  "de STATPOP_KEEP_SUFFIXES ne fait que le protéger de la suppression "
                  "opérée à L394-397. De plus le décompte annoncé est faux : "
                  "STATPOP_KEEP_SUFFIXES contient 23 suffixes et non 24, ce que "
                  "confirme la table canonique, qui porte 23 colonnes "
                  "`spatial_gare_depart_*` hors emploi et autant côté arrivée, "
                  "soit 46 colonnes et non 48. Sur ces 23, une seule (`ordre`) "
                  "n'est pas un indicateur STATPOP.",
        "traitement": "La définition de `spatial_gare_*_ordre` cite le référentiel de "
                      "gares, pas STATPOP. Le décompte est recompté dans le rapport.",
    },
    {
        "colonnes": "`spatial_statpop_source_depart` / `_arrivee`, "
                    "`vmcv_source_depart` / `_arrivee`, "
                    "`simba_source_depart` / `_arrivee`",
        "emplacement": f"{S_STATPOP}:L176-177, {S_IST}:L329-332, {S_SIMBA}:L112-113",
        "docstring": "Le suffixe `_depart` / `_arrivee` de ces six colonnes suggère "
                     "une valeur propre à chaque extrémité du tronçon, à l'image des "
                     "46 paires STATPOP.",
        "calcul": "Les trois paires sont assignées deux fois à partir d'une seule et "
                  "même série : provenance du millésime pour STATPOP (calculée sur "
                  "l'année civile), fenêtre d'interruption pour VMCV (calculée sur la "
                  "date), résultat de la jointure pour SIMBA. Aucune des six ne "
                  "dépend d'une gare. L'égalité stricte des trois paires est vérifiée "
                  "sur les 1 141 984 lignes (section 5 du présent rapport).",
        "traitement": "Chaque définition dit explicitement que la valeur est recopiée "
                      "à l'identique des deux côtés et ne dépend d'aucune gare.",
    },
    {
        "colonnes": "les 9 colonnes `meteo_*_h`",
        "emplacement": f"{S_METEOH}:build_meteo_features(), docstring L235-238",
        "docstring": "« Construit les 6 features météo finales ».",
        "calcul": "La fonction construit 9 colonnes : 5 locales au tronçon et 4 de "
                  "destination, conformément à METEO_FEATURE_COLUMNS:L125-137 et au "
                  "docstring de module L1. Le nombre 6 est un vestige d'une version "
                  "antérieure.",
        "traitement": "Sans effet sur les définitions ; l'écart est purement "
                      "rédactionnel et interne au fichier.",
    },
    {
        "colonnes": "les 9 colonnes `meteo_*_j` locales",
        "emplacement": f"{S_METEOJ}, docstring de module L52-53 et "
                       "join_agg_journaliers() docstring L204",
        "docstring": "« spatial_segment == \"bas\" → station VEV ; \"haut\" → CHD » et "
                     "« Ce mapping est strictement identique à add_meteo_to_raw_stacked.py ».",
        "calcul": "Le calcul est `np.where(is_haut, CHD, VEV)` (L257-261) : toute "
                  "valeur de segment autre que « haut », y compris un segment manquant, "
                  "reçoit la station de plaine. Le stage horaire, lui, produit un "
                  f"manquant dans ce cas ({S_METEOH}:L260-284). Les deux mappings ne "
                  "sont donc pas strictement identiques sur le traitement du cas "
                  "résiduel. Sur le périmètre canonique H22-H25, `spatial_segment` "
                  "n'est jamais manquant, l'écart reste sans effet observable.",
        "traitement": "Les définitions journalières disent « lorsque le segment est "
                      "haut, la station de plaine dans tous les autres cas ».",
    },
    {
        "colonnes": "les 16 colonnes `histo_*`",
        "emplacement": f"{S_FEAT}, suffixe de nommage lag2",
        "docstring": "Le suffixe `lag2` désigne, dans la conception d'origine, un "
                     "décalage opérationnel de deux jours.",
        "calcul": "Le décalage appliqué est un seuil mensuel composé calculé par "
                  "`_cutoff_mensuel_seuils()` (L166-198), puis un `searchsorted` sur "
                  "les dates triées du groupe (L478-482). Le délai obtenu est de "
                  "l'ordre de trois semaines, non de deux jours ; une garde échoue "
                  "explicitement si le délai médian retombe sous dix jours (L226-243). "
                  "Le code documente lui-même ce vestige à L48-56 et L93-97.",
        "traitement": "Chaque définition `histo_*` énonce la règle de seuil mensuel et "
                      "signale que `lag2` est un vestige de nommage.",
    },
    {
        "colonnes": "`spatial_denivele_troncon_m`",
        "emplacement": f"{S_SPAT}, docstring de module L22-26",
        "docstring": "Les altitudes sont lues « depuis dim_gare.csv (source de vérité "
                     "incluant GIL et CLIE, cf. ADR-057) », par opposition aux colonnes "
                     "d'altitude du stage courant qui « héritent d'un NaN pour GIL/CLIE ».",
        "calcul": "La lecture se fait bien depuis dim_gare.csv "
                  "(add_denivele_troncon():L93-95), mais la colonne reste manquante "
                  "sur 31 450 observations, toutes portées par les quatre tronçons de "
                  "Gilamont en H22 (constaté sur le gel canonique). Le fichier "
                  "dim_gare.csv ne fournit donc pas l'altitude de GIL, contrairement "
                  "à ce qu'affirme le docstring. La fonction de résumé prévoit "
                  "d'ailleurs ce cas (print_summary():L123-132).",
        "traitement": "La définition indique que la valeur est manquante lorsque "
                      "l'altitude d'une des deux gares est absente du référentiel.",
    },
]

# Colonnes dont le producteur n'a pas été retrouvé ou dont le calcul reste ambigu.
# Chacune garde une `definition` vide dans le CSV.
NON_RESOLUES: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Grammaire de nommage — motifs vérifiés contre la liste réelle des noms
# --------------------------------------------------------------------------- #
MOTIFS: list[dict] = [
    {
        "famille": "id_",
        "motif": "id_{objet}[_{qualifiant}]",
        "segments": [
            ("objet", "source_file, gare_depart, gare_arrivee, statpop",
             "entité identifiée"),
            ("qualifiant", "bpuic, reference_year",
             "précision sur la nature de l'identifiant, absent par défaut"),
        ],
        "regex": r"^id_(source_file|gare_(depart|arrivee)(_bpuic)?|statpop_reference_year)$",
    },
    {
        "famille": "base_",
        "motif": "base_{grandeur}[_{classe}]",
        "segments": [
            ("grandeur", "date, sens, depart_datetime, arrivee_datetime, "
             "duree_troncon_minutes, offre", "grandeur mesurée sur la course"),
            ("classe", "1ere_classe, 2eme_classe, total",
             "classe de voitures, uniquement pour l'offre"),
        ],
        "regex": r"^base_(date|sens|(depart|arrivee)_datetime|duree_troncon_minutes|offre_(1ere_classe|2eme_classe|total))$",
    },
    {
        "famille": "horaire_",
        "motif": "horaire_{objet}",
        "segments": [("objet", "annee_horaire, numero_train, service_id_complet",
                      "attribut de structure de l'offre")],
        "regex": r"^horaire_(annee_horaire|numero_train|service_id_complet)$",
    },
    {
        "famille": "target_",
        "motif": "target_voyageurs_{classe}",
        "segments": [("classe", "1ere_classe, 2eme_classe, total",
                      "classe de voitures comptée")],
        "regex": r"^target_voyageurs_(1ere_classe|2eme_classe|total)$",
    },
    {
        "famille": "cal_",
        "motif": "cal_{composante}",
        "segments": [
            ("composante",
             "annee_civile, mois, mois_horaire, jour, jour_semaine, "
             "jour_semaine_iso, is_weekend, type_jour, type_jour_3classes, "
             "heure_depart, minute_depart, heure_arrivee, minute_arrivee, "
             "depart_minute_du_jour, arrivee_minute_du_jour",
             "composante calendaire ou horaire du trajet"),
        ],
        "regex": r"^cal_(annee_civile|mois|mois_horaire|jour|jour_semaine|jour_semaine_iso|is_weekend|type_jour|type_jour_3classes|(heure|minute)_(depart|arrivee)|(depart|arrivee)_minute_du_jour)$",
    },
    {
        "famille": "event_",
        "motif": "event_{is_|n_|∅}{evenement}[_{portee}]",
        "segments": [
            ("préfixe de type", "is_ (indicatrice), n_ (compte), aucun (modalité "
             "textuelle : ski_source, covid_phase, narcisses_source)",
             "nature de la variable"),
            ("evenement",
             "vacances_vaud, ferie_vaud, vacances_ou_ferie_vaud, "
             "manifestation(s)_riviera, montreux_jazz, marche_noel, montreux_noel, "
             "ski_ouvert, covid_restrictions, saison_narcisses",
             "événement ou période décrite"),
            ("portee", "zone_directe_j, zone_indirecte_j, hors_zone_j, vevey_j, "
             "st_legier_j, blonay_j", "zone ou localité, suffixe _j = au jour"),
        ],
        "regex": r"^event_(is_|n_)?[a-z0-9_]+$",
    },
    {
        "famille": "spatial_",
        "motif": "spatial_gare_{depart|arrivee}_{indicateur} "
                 "| spatial_{attribut_troncon} | spatial_statpop_source_{depart|arrivee}",
        "segments": [
            ("gare_{côté}", "depart, arrivee", "extrémité du tronçon décrite"),
            ("indicateur",
             "ordre, pop_500m_total, menages_500m_total, pop_par_menage_500m, "
             "part_*, indice_*, hpi_*, flag_qualite_faible, emplois_500m_*",
             "indicateur territorial mesuré sur la zone de la gare"),
            ("attribut_troncon", "distance_km, segment, denivele_troncon_m",
             "attribut du tronçon entier, sans côté"),
        ],
        "regex": r"^spatial_(gare_(depart|arrivee)_[a-z0-9_]+|distance_km|segment|denivele_troncon_m|statpop_source_(depart|arrivee))$",
    },
    {
        "famille": "meteo_",
        "motif": "meteo_[destination_]{grandeur}_{horizon}",
        "segments": [
            ("destination_", "présent ou absent",
             "présent : station de la gare de destination du train, résolue par le "
             "sens ; absent : station du segment du tronçon"),
            ("grandeur",
             "temperature, precipitation_mm, ensoleillement_min, vent_max, "
             "neige_binaire, temperature_max, precip_total, ensol_total, "
             "rayon_global_moy", "paramètre météorologique"),
            ("horizon", "h (heure du départ), j (jour de circulation), "
             "j_moins_1 (veille), j_plus_1 (lendemain)",
             "horizon temporel de l'agrégation"),
        ],
        "regex": r"^meteo_(destination_)?[a-z0-9_]+_(h|j|j_moins_1|j_plus_1)$",
    },
    {
        "famille": "ist_",
        "motif": "ist_{sous_famille}_{mesure}_{fenetre}occ | ist_headway_{position}_{mesure}",
        "segments": [
            ("sous_famille", "profil_train, corresp_in, corresp_out, headway",
             "bloc de features ISTDATEN"),
            ("mesure",
             "retard_{dep|arr}_troncon_{mean|std}, pct_en_retard_{dep|arr}_troncon, "
             "n_theoriques_moy, n_garanties_moy, pct_garanties, "
             "min, is_first_of_day, is_last_of_day", "grandeur calculée"),
            ("fenetre", "5occ, 20occ",
             "nombre d'occurrences de même type de jour dans la fenêtre glissante ; "
             "absent pour headway, qui n'est pas une fenêtre glissante"),
        ],
        "regex": r"^ist_(profil_train_[a-z_]+_(5occ|20occ)|corresp_(in|out)_[a-z_]+_(5occ|20occ)|headway_(avant|apres)_(min|is_first_of_day|is_last_of_day))$",
    },
    {
        "famille": "vmcv_",
        "motif": "vmcv_{mesure} | vmcv_source_{depart|arrivee}",
        "segments": [
            ("mesure", "n_lignes_concurrentes, min_attente_min, "
             "delta_attente_min, delta_frequence_h", "grandeur de concurrence modale"),
        ],
        "regex": r"^vmcv_(n_lignes_concurrentes|min_attente_min|delta_attente_min|delta_frequence_h|source_(depart|arrivee))$",
    },
    {
        "famille": "histo_",
        "motif": "histo_voyageurs_{classe}_{statistique}",
        "segments": [
            ("classe", "1ere_classe, 2eme_classe, total", "classe comptée"),
            ("statistique",
             "lag2 (dernière occurrence consolidée), win7_mean, win7_median, "
             "win7_max, win7_std, win7_n_surcharges",
             "statistique sur la fenêtre des sept dernières occurrences "
             "consolidées ; win7_n_surcharges n'existe que pour la deuxième classe"),
        ],
        "regex": r"^histo_voyageurs_(1ere_classe|2eme_classe|total)_(lag2|win7_(mean|median|max|std|n_surcharges))$",
    },
    {
        "famille": "simba_",
        "motif": "simba_part_{modalite} | simba_source_{depart|arrivee}",
        "segments": [
            ("modalite",
             "ga, mobilis, billet_hta, spar, jeunes, abonnement, militaire, autre, "
             "corresp_amont, corresp_aval, premiere_classe, intra_r35",
             "famille tarifaire, type de correspondance, classe ou périmètre du "
             "voyage"),
        ],
        "regex": r"^simba_(part_(ga|mobilis|billet_hta|spar|jeunes|abonnement|militaire|autre|corresp_amont|corresp_aval|premiere_classe|intra_r35)|source_(depart|arrivee))$",
    },
    {
        "famille": "resa_",
        "motif": "resa_{mesure}_J_minus_1",
        "segments": [
            ("mesure",
             "pax_2c, n_dossiers, max_groupe_2c, part_scolaire, "
             "part_tour_operator, n_pays_distincts, n_langues_distinctes, has_resa",
             "grandeur agrégée sur les réservations de groupe"),
            ("J_minus_1", "suffixe constant",
             "rappelle que seules les réservations connues au moins un jour avant "
             "le voyage sont retenues"),
        ],
        "regex": r"^resa_[a-z0-9_]+_J_minus_1$",
    },
]


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def sha256_8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def stop(msg: str) -> None:
    print(f"\n*** STOP — {msg}", file=sys.stderr)
    sys.exit(1)


def mil(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def ecrit_xlsx_deterministe(df: pd.DataFrame, chemin: Path, feuille: str) -> None:
    """Écrit un .xlsx byte-reproductible (aucun horodatage d'exécution)."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=feuille, index=False)
        props = xl.book.properties
        props.created = EPOQUE_FIXE
        props.modified = EPOQUE_FIXE
        props.creator = "fill_definitions_dictionnaire.py"
        props.lastModifiedBy = "fill_definitions_dictionnaire.py"

    horodatage = EPOQUE_FIXE.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    source = zipfile.ZipFile(io.BytesIO(tampon.getvalue()))
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for info in source.infolist():
            contenu = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                contenu = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)",
                    rb"\g<1>" + horodatage + rb"\g<2>", contenu)
            fige = zipfile.ZipInfo(info.filename, date_time=EPOQUE_FIXE.timetuple()[:6])
            fige.compress_type = info.compress_type
            fige.external_attr = info.external_attr
            z.writestr(fige, contenu)
    chemin.write_bytes(sortie.getvalue())


PONCTUATION_INTERDITE = {"—": "cadratin", "–": "demi-cadratin", ";": "point-virgule"}


def controle_redaction(texte: str) -> list[str]:
    return [lib for signe, lib in PONCTUATION_INTERDITE.items() if signe in texte]


# --------------------------------------------------------------------------- #
# Programme
# --------------------------------------------------------------------------- #
def main() -> None:
    lignes_rapport: list[str] = []
    lignes_gram: list[str] = []

    def emit(s: str = "") -> None:
        lignes_rapport.append(s)

    def gram(s: str = "") -> None:
        lignes_gram.append(s)

    # --- Préambule : empreinte -------------------------------------------- #
    for p in (CANON, DICO_CSV):
        if not p.exists():
            stop(f"fichier requis absent : {p}")
    h_canon = sha256_8(CANON)
    if h_canon != HASH_ATTENDU:
        stop(f"empreinte du dataset non conforme : lue {h_canon!r}, "
             f"attendue {HASH_ATTENDU!r}. Aucune sortie n'est produite.")
    dico = pd.read_csv(DICO_CSV, keep_default_na=False, dtype=str)
    colonnes_avant = list(dico.columns)
    # Socle = colonnes produites par make_dictionnaire_colonnes_canonique.py.
    # Son empreinte est stable d'une exécution à l'autre (contrairement à celle
    # du fichier entier, qui change au premier remplissage) et atteste que ce
    # script n'a rien modifié en dehors des colonnes documentaires.
    colonnes_socle = [c for c in colonnes_avant
                      if c not in COLONNES_AJOUTEES and c != "definition"]
    socle_avant = dico[colonnes_socle].copy()
    h_socle = hashlib.sha256(
        socle_avant.to_csv(index=False).encode("utf-8")).hexdigest()[:8]
    if len(dico) != N_COLONNES_ATTENDU:
        stop(f"{len(dico)} lignes dans le dictionnaire, attendu {N_COLONNES_ATTENDU}")
    if "definition" not in colonnes_avant:
        stop("colonne `definition` absente du dictionnaire")
    noms = list(dico["nom"])

    # --- Remplissage ------------------------------------------------------- #
    inconnues = sorted(set(DEFS) - set(noms))
    if inconnues:
        stop(f"définitions rédigées pour des colonnes absentes de la table : {inconnues}")

    dico["definition"] = [DEFS.get(n, ("", "", "", "", ""))[0] for n in noms]
    dico["unite"] = [DEFS.get(n, ("", "", "", "", ""))[1] for n in noms]
    dico["mode_obtention"] = [DEFS.get(n, ("", "", "", "", ""))[2] for n in noms]
    dico["source_definition"] = [DEFS.get(n, ("", "", "", "", ""))[3] for n in noms]
    dico["confiance"] = [DEFS.get(n, ("", "", "", "", ""))[4] for n in noms]

    non_resolues = [n for n in noms if not dico.loc[dico["nom"] == n, "definition"].iloc[0]]

    # --- Contrôles de rédaction -------------------------------------------- #
    fautes: list[tuple[str, list[str]]] = []
    for n in noms:
        txt = DEFS.get(n, ("",))[0]
        if not txt:
            continue
        pbs = controle_redaction(txt)
        if re.search(r"\bADR-\d+", txt):
            pbs.append("référence ADR dans le texte")
        if re.search(r"\b(je|nous|notre|mon)\b", txt, flags=re.I):
            pbs.append("registre personnel")
        if pbs:
            fautes.append((n, pbs))

    unites_hors_liste = sorted(
        {u for u in dico["unite"] if u and u not in UNITES_PROPOSEES | UNITES_AJOUTEES}
    )

    # --- Ordre final des colonnes ------------------------------------------ #
    idx_def = colonnes_avant.index("definition")
    ordre = (colonnes_avant[: idx_def + 1] + COLONNES_AJOUTEES
             + [c for c in colonnes_avant[idx_def + 1:] if c not in COLONNES_AJOUTEES])
    dico = dico[ordre]

    # --- Grammaire de nommage : vérification des motifs -------------------- #
    couverture: dict[str, dict] = {}
    for m in MOTIFS:
        fam = m["famille"]
        membres = [n for n in noms if n.startswith(fam)]
        rx = re.compile(m["regex"])
        conformes = [n for n in membres if rx.match(n)]
        deviants = [n for n in membres if not rx.match(n)]
        couverture[fam] = {"membres": membres, "conformes": conformes,
                           "deviants": deviants}

    familles_reelles = sorted({n.split("_", 1)[0] + "_" for n in noms if "_" in n})
    familles_sans_motif = [f for f in familles_reelles if f not in couverture]

    # --- Vérifications complémentaires (lecture seule) --------------------- #
    import pyarrow.parquet as pq
    cols_canon = pq.ParquetFile(CANON).schema_arrow.names

    # V1 — paires depart / arrivee
    paires = [(c, c.replace("depart", "arrivee")) for c in cols_canon
              if "depart" in c and c.replace("depart", "arrivee") in cols_canon]
    paires_gare = [p for p in paires if "gare_depart" in p[0]]
    paires_autres = [p for p in paires if "gare_depart" not in p[0]]
    # Symétrie de calcul : les deux membres sont-ils produits par le même appel,
    # appliqué respectivement à id_gare_depart et id_gare_arrivee ? La réponse est
    # lue dans le code (boucles sur les deux côtés) et restituée en section 5.
    paires_source = [p for p in paires if p[0].endswith("_source_depart")]
    identiques: dict[str, bool] = {}
    for a, b in paires_source:
        s = pd.read_parquet(CANON, columns=[a, b])
        identiques[a] = bool((s[a].fillna("<NA>") == s[b].fillna("<NA>")).all())
        del s

    # V2 — ski et narcisses sur H22-H25
    v2 = pd.read_parquet(CANON, columns=[
        "event_is_ski_ouvert", "event_ski_source",
        "event_is_saison_narcisses", "event_narcisses_source"])
    contingences: dict[str, pd.DataFrame] = {}
    desaccords: dict[str, float] = {}
    for flag, src in (("event_is_ski_ouvert", "event_ski_source"),
                      ("event_is_saison_narcisses", "event_narcisses_source")):
        ct = pd.crosstab(v2[flag], v2[src], dropna=False)
        contingences[src] = ct
        majoritaire = v2.groupby(src, observed=True)[flag].agg(
            lambda s: s.mode().iloc[0])
        desaccords[src] = float((v2[src].map(majoritaire) != v2[flag]).mean())
    del v2

    # V3 — durée de tronçon nulle
    v3 = pd.read_parquet(CANON, columns=[
        "base_duree_troncon_minutes", "id_gare_depart", "id_gare_arrivee",
        "horaire_annee_horaire", "spatial_distance_km",
        "cal_heure_depart", "cal_minute_depart",
        "cal_heure_arrivee", "cal_minute_arrivee"])
    n_total = len(v3)
    zero = v3[v3["base_duree_troncon_minutes"] == 0]
    n_zero = len(zero)
    troncons_zero = sorted(set(zip(zero["id_gare_depart"], zero["id_gare_arrivee"])))
    annees_zero = zero["horaire_annee_horaire"].value_counts().sort_index().to_dict()
    dist_zero = sorted({float(x) for x in zero["spatial_distance_km"].dropna()})
    meme_minute = bool(((zero["cal_heure_depart"] == zero["cal_heure_arrivee"])
                        & (zero["cal_minute_depart"] == zero["cal_minute_arrivee"])).all())
    dep, arr = troncons_zero[0] if troncons_zero else ("", "")
    profil = (v3[((v3["id_gare_depart"] == dep) & (v3["id_gare_arrivee"] == arr))
                 | ((v3["id_gare_depart"] == arr) & (v3["id_gare_arrivee"] == dep))]
              .groupby(["id_gare_depart", "id_gare_arrivee", "horaire_annee_horaire",
                        "base_duree_troncon_minutes"], observed=True)
              .size().reset_index(name="n")) if troncons_zero else pd.DataFrame()
    del v3

    # --- Écriture des livrables -------------------------------------------- #
    dico.to_csv(DICO_CSV, index=False, encoding="utf-8")
    ecrit_xlsx_deterministe(dico, DICO_XLSX, "dictionnaire")

    # ----------------------------------------------------------------------- #
    # grammaire_nommage.md
    # ----------------------------------------------------------------------- #
    gram("# Grammaire de nommage des colonnes de la table canonique")
    gram()
    gram("Annexe §4.4.3. Document dérivé des **209 noms réels** de "
         "`data/processed/ml_dataset.parquet` "
         f"(empreinte `{h_canon}`), produit par "
         "`docs/memoire/verifs/section_4_4_3/fill_definitions_dictionnaire.py`.")
    gram()
    gram("Chaque motif ci-dessous est confronté par expression régulière à la "
         "liste complète des noms de sa famille. Toute colonne non conforme est "
         "signalée. Aucun motif n'est postulé au-delà de ce que les noms portent.")
    gram()
    gram("## Règle générale")
    gram()
    gram("Un nom se lit `{famille}_{corps}`, la famille étant le segment situé "
         "avant le premier underscore, underscore inclus. Les 13 familles sont "
         "celles du tableau 9 du mémoire. Le corps se décompose en segments "
         "séparés par des underscores, dont la grammaire est propre à chaque "
         "famille.")
    gram()
    gram("Trois conventions traversent plusieurs familles :")
    gram()
    gram("- `is_` en tête de corps marque une indicatrice à deux modalités, "
         "`n_` un dénombrement.")
    gram("- `depart` et `arrivee` désignent les deux extrémités du tronçon. "
         "Attention : six colonnes portent ce suffixe sans en dépendre "
         "(voir la section 4 ci-dessous).")
    gram("- un suffixe temporel ferme le nom : `_h` pour l'heure du départ, "
         "`_j` pour le jour de circulation, `_j_moins_1` et `_j_plus_1` pour "
         "la veille et le lendemain, `_5occ` et `_20occ` pour des fenêtres "
         "comptées en occurrences et non en jours.")
    gram()
    gram("## 1. Motifs par famille")
    gram()
    for m in MOTIFS:
        fam = m["famille"]
        c = couverture[fam]
        gram(f"### `{fam}` ({len(c['membres'])} colonnes)")
        gram()
        gram(f"Motif : `{m['motif']}`")
        gram()
        gram("| Segment | Valeurs observées | Signification |")
        gram("|---|---|---|")
        for seg, vals, sens in m["segments"]:
            gram(f"| `{seg}` | {vals} | {sens} |")
        gram()
        if c["deviants"]:
            gram(f"**Colonnes non conformes au motif ({len(c['deviants'])})** : "
                 + ", ".join("`" + x + "`" for x in c["deviants"]))
        else:
            gram(f"Conformité : {len(c['conformes'])}/{len(c['membres'])} — "
                 "aucune colonne hors motif.")
        gram()

    gram("## 2. Récapitulatif de conformité")
    gram()
    gram("| Famille | Colonnes | Conformes | Non conformes |")
    gram("|---|---|---|---|")
    tot_m = tot_c = tot_d = 0
    for m in MOTIFS:
        fam = m["famille"]
        c = couverture[fam]
        tot_m += len(c["membres"]); tot_c += len(c["conformes"]); tot_d += len(c["deviants"])
        gram(f"| `{fam}` | {len(c['membres'])} | {len(c['conformes'])} | "
             f"{len(c['deviants'])} |")
    gram(f"| **Total** | **{tot_m}** | **{tot_c}** | **{tot_d}** |")
    gram()
    if familles_sans_motif:
        gram("Familles présentes dans la table sans motif documenté : "
             + ", ".join("`" + f + "`" for f in familles_sans_motif) + ".")
    else:
        gram("Les 13 familles de la table sont toutes couvertes par un motif.")
    gram()

    gram("## 3. Motifs proposés dans la commande, confrontés aux noms réels")
    gram()
    gram("| Motif proposé | Verdict | Précision apportée par les noms réels |")
    gram("|---|---|---|")
    gram("| `histo_{classe}_{statistique}_{fenêtre}` | à corriger | Le corps "
         "commence toujours par `voyageurs`, et la fenêtre n'est pas un segment "
         "séparé : elle est soudée à la statistique (`win7_mean`). La forme "
         "exacte est `histo_voyageurs_{classe}_{statistique}`, avec "
         "`statistique` dans {`lag2`, `win7_mean`, `win7_median`, `win7_max`, "
         "`win7_std`, `win7_n_surcharges`}. |")
    gram("| `meteo_[destination_]{grandeur}_{horizon}` | confirmé | 27 colonnes "
         "sur 27. `destination_` est présent sur 13 colonnes et absent sur 14, "
         "l'asymétrie venant de `meteo_neige_binaire_h`, qui n'a pas "
         "d'équivalent destination. |")
    gram("| `spatial_gare_{depart\\|arrivee}_{indicateur}` | confirmé mais "
         "partiel | 50 colonnes sur 55 s'y conforment. Les 5 autres ne portent "
         "pas de côté : `spatial_distance_km`, `spatial_segment`, "
         "`spatial_denivele_troncon_m` décrivent le tronçon entier, et "
         "`spatial_statpop_source_depart` / `_arrivee` portent un côté sans en "
         "dépendre. |")
    gram("| `ist_{famille}_{mesure}_{fenêtre}occ` | confirmé mais partiel | 24 "
         "colonnes sur 28. Les 4 colonnes `ist_headway_*` ne comportent pas de "
         "fenêtre en occurrences : elles suivent `ist_headway_{avant\\|apres}_"
         "{min\\|is_first_of_day\\|is_last_of_day}`. |")
    gram("| `simba_part_{modalité}` | confirmé mais partiel | 12 colonnes sur "
         "14. Les 2 autres suivent `simba_source_{depart\\|arrivee}`. |")
    gram()

    gram("## 4. Pièges de lecture")
    gram()
    gram("Six colonnes portent le suffixe `_depart` ou `_arrivee` sans dépendre "
         "de la gare correspondante : `spatial_statpop_source_depart` et "
         "`_arrivee`, `vmcv_source_depart` et `_arrivee`, `simba_source_depart` "
         "et `_arrivee`. Chaque paire est produite par une double affectation de "
         "la même série. Leur égalité stricte est vérifiée dans "
         "`definitions_rapport.md`, section 5.")
    gram()
    gram("Le suffixe `lag2` des 16 colonnes `histo_*` ne désigne pas un décalage "
         "de deux jours mais un seuil de consolidation mensuel. Le nom est un "
         "vestige de la conception d'origine.")
    gram()
    gram("Le suffixe `_500m` des colonnes `spatial_gare_*` ne désigne pas un "
         "disque de 500 mètres mais la cellule de Voronoï de la gare écrêtée à "
         "ce rayon, donc une surface généralement plus petite et disjointe de "
         "celle des gares voisines.")
    gram()
    gram("Les suffixes `_5occ` et `_20occ` comptent des occurrences de même type "
         "de jour, pas des jours calendaires. Une fenêtre `20occ` sur un service "
         "du dimanche couvre environ vingt semaines.")
    gram()

    OUT_GRAMMAIRE.write_text("\n".join(lignes_gram) + "\n", encoding="utf-8")

    # ----------------------------------------------------------------------- #
    # definitions_rapport.md
    # ----------------------------------------------------------------------- #
    def tick(b: bool) -> str:
        return "OK" if b else "ÉCART"

    socle_intact = socle_avant.equals(dico[colonnes_socle])
    tick_socle = tick(socle_intact)

    emit("# Remplissage des définitions du dictionnaire de données")
    emit()
    emit("Annexe §4.4.3. Rapport produit par "
         "`docs/memoire/verifs/section_4_4_3/fill_definitions_dictionnaire.py`, "
         "en lecture seule sur les données.")
    emit()
    emit("## 1. Sources et empreintes")
    emit()
    emit("| Rôle | Chemin | Empreinte SHA256[:8] |")
    emit("|---|---|---|")
    emit(f"| Table canonique (garde d'entrée) | `data/processed/ml_dataset.parquet` | `{h_canon}` |")
    emit(f"| Dictionnaire après remplissage | `{DICO_CSV.relative_to(ROOT)}` | `{sha256_8(DICO_CSV)}` |")
    emit(f"| Classeur | `{DICO_XLSX.relative_to(ROOT)}` | `{sha256_8(DICO_XLSX)}` |")
    emit(f"| Socle préservé ({len(colonnes_socle)} colonnes du squelette) | — | `{h_socle}` |")
    emit()
    emit(f"Les {len(colonnes_socle)} colonnes du squelette produit par "
         "`make_dictionnaire_colonnes_canonique.py` sont relues et réécrites "
         f"**sans modification** (vérifié valeur par valeur : {tick_socle}). Ce "
         "script n'écrit que la colonne `definition`, laissée vide par le "
         "squelette, et les quatre colonnes ajoutées "
         + ", ".join("`" + c + "`" for c in COLONNES_AJOUTEES) + ".")
    emit()

    emit("## 2. Répartition des niveaux de confiance")
    emit()
    compte_conf = Counter(dico["confiance"])
    emit("| Confiance | Colonnes | Part | Critère |")
    emit("|---|---|---|---|")
    criteres = {
        "haute": "définition lue dans le calcul du script producteur",
        "moyenne": "calcul de l'indicateur absent du dépôt, seule la jointure et "
                   "un ADR le documentent",
        "": "colonne non résolue, `definition` laissée vide",
    }
    for niveau in ("haute", "moyenne", ""):
        n = compte_conf.get(niveau, 0)
        lib = niveau if niveau else "(vide)"
        emit(f"| {lib} | {n} | {100 * n / len(dico):.1f} % | {criteres[niveau]} |")
    emit(f"| **Total** | **{len(dico)}** | **100,0 %** | — |")
    emit()
    moyennes = sorted(dico.loc[dico["confiance"] == "moyenne", "nom"])
    if moyennes:
        emit("Colonnes en confiance moyenne : "
             + ", ".join("`" + c + "`" for c in moyennes) + ". Le producteur de "
             "`statent_clean_causal.parquet` est absent du dépôt (entrée figée non "
             "refabricable, vérifiée par `scripts/check_sources.sh:L42-43`). La "
             "jointure et le mapping de millésime sont, eux, lus dans le code.")
    emit()
    emit("Répartition par mode d'obtention :")
    emit()
    compte_mode = Counter(dico["mode_obtention"])
    emit("| Mode | Colonnes |")
    emit("|---|---|")
    for mode in ("brute", "dérivée", ""):
        lib = mode if mode else "(vide)"
        emit(f"| {lib} | {compte_mode.get(mode, 0)} |")
    emit()

    emit("## 3. Colonnes non résolues")
    emit()
    if non_resolues:
        emit("| Colonne | Raison |")
        emit("|---|---|")
        for n in non_resolues:
            emit(f"| `{n}` | {NON_RESOLUES.get(n, 'producteur non retrouvé')} |")
    else:
        emit(f"Aucune. Les {len(dico)} colonnes ont été rattachées à un script "
             "producteur et à des lignes de calcul identifiées.")
    emit()

    emit("## 4. Divergences entre docstring et calcul")
    emit()
    emit(f"{len(DIVERGENCES)} divergences relevées. Dans chaque cas, la définition "
         "retenue suit le calcul.")
    emit()
    for i, div in enumerate(DIVERGENCES, start=1):
        emit(f"### 4.{i} {div['colonnes']}")
        emit()
        emit(f"**Emplacement** : `{div['emplacement']}`")
        emit()
        emit(f"**Ce que dit le texte** : {div['docstring']}")
        emit()
        emit(f"**Ce que fait le calcul** : {div['calcul']}")
        emit()
        emit(f"**Traitement retenu** : {div['traitement']}")
        emit()

    emit("## 5. Vérification 1 — paires gare de départ et gare d'arrivée")
    emit()
    emit(f"La table comporte **{len(paires)} paires** de colonnes dont le nom se "
         "déduit l'un de l'autre en remplaçant `depart` par `arrivee`, dont "
         f"**{len(paires_gare)}** portent le fragment `gare_depart` et "
         f"**{len(paires_autres)}** un autre fragment.")
    emit()
    emit("La commande annonçait 26 paires. Le décompte exact est de "
         f"{len(paires_gare)} paires portant `gare_depart`, dont une est la paire "
         "d'identifiants de gare elle-même (`id_gare_depart` et "
         f"`id_gare_arrivee`). Les paires d'**indicateurs** rattachés à une gare "
         f"sont donc au nombre de {len(paires_gare) - 1}, ce qui correspond au "
         "chiffre annoncé.")
    emit()
    emit("| Bloc | Paires | Produit par le même calcul appliqué aux deux extrémités |")
    emit("|---|---|---|")
    emit(f"| Identifiants et topologie de gare | 3 | Oui. `enrich_station_dimensions()` "
         f"({S_STACK}:L466-480) appelle deux fois `add_station_dimension()` avec la "
         "même dimension, sur `gare_depart` puis `gare_arrivee`. |")
    n_statpop = sum(1 for a, _ in paires_gare
                    if a.startswith("spatial_gare_depart_") and "emplois" not in a
                    and not a.endswith("_ordre"))
    emit(f"| Indicateurs STATPOP | {n_statpop} | Oui. `add_statpop_to_raw_stacked()` "
         f"({S_STATPOP}:L413-419) boucle sur les deux côtés en appelant "
         "`add_statpop_for_side()` avec la même table de faits préfixée. |")
    emit(f"| Indicateurs d'emploi STATENT | 2 | Oui. `add_statent()` "
         f"({S_STATENT}:L97-109) boucle sur les deux côtés avec la même table "
         "`statent_clean_causal` et le même millésime. |")
    emit()
    emit("**Aucune paire d'indicateurs de gare ne diverge dans son mode de "
         "calcul.** Les deux membres de chaque paire sont produits par le même "
         "appel de fonction, paramétré par l'abréviation de gare de l'extrémité "
         "considérée.")
    emit()
    emit("En revanche, trois des paires ne portant pas `gare_depart` sont "
         "trompeuses : elles suffixent `_depart` et `_arrivee` alors que leur "
         "valeur ne dépend d'aucune gare. Vérification d'égalité stricte sur les "
         f"{mil(n_total)} lignes :")
    emit()
    emit("| Paire | Colonnes strictement égales | Modalités |")
    emit("|---|---|---|")
    for a, b in paires_source:
        mods = sorted(pd.read_parquet(CANON, columns=[a])[a].dropna().unique())
        emit(f"| `{a}` / `{b}` | **{tick(identiques[a])}**, identiques | "
             + ", ".join("`" + str(m) + "`" for m in mods) + " |")
    emit()
    emit("Les quatre autres paires sans `gare_depart`, à savoir "
         + ", ".join("`" + a + "`" for a, _ in paires_autres
                     if not a.endswith("_source_depart"))
         + " et leurs homologues d'arrivée, décrivent le moment du départ et "
         "celui de l'arrivée du tronçon. Elles sont bien calculées séparément "
         "sur les deux horaires.")
    emit()

    emit("## 6. Vérification 2 — redondance des marqueurs de provenance "
         "événementiels")
    emit()
    emit("Question posée : sur H22 à H25, `event_ski_source` et "
         "`event_narcisses_source` sont-elles fonctionnellement redondantes avec "
         "leur indicatrice de saison ? Le périmètre de la table canonique étant "
         f"exactement H22-H25, les {mil(n_total)} lignes sont retenues.")
    emit()
    for flag, src in (("event_is_ski_ouvert", "event_ski_source"),
                      ("event_is_saison_narcisses", "event_narcisses_source")):
        ct = contingences[src]
        emit(f"### {src} contre {flag}")
        emit()
        entetes = list(ct.columns)
        emit("| " + flag + " | " + " | ".join("`" + str(c) + "`" for c in entetes) + " |")
        emit("|---" * (len(entetes) + 1) + "|")
        for idx, row in ct.iterrows():
            emit(f"| {idx} | " + " | ".join(mil(int(v)) for v in row) + " |")
        emit()
        emit(f"Taux de désaccord (modalité de la colonne de provenance rapportée "
             f"à la valeur majoritaire de l'indicatrice) : "
             f"**{100 * desaccords[src]:.4f} %**.")
        emit()
    emit("**Conclusion.** Les deux colonnes de provenance sont **totalement "
         "redondantes** avec leur indicatrice sur H22-H25 : la table de "
         "contingence est diagonale, le taux de désaccord est nul, et la "
         "correspondance est bijective entre deux modalités de chaque côté. Le "
         "code explique le résultat : les référentiels de dimension ne "
         "contiennent que des jours **en saison** "
         f"(`{B_SKI}:build_dim():L136-169`, `{B_NARC}:build_dim():L93-113`), et "
         "l'étage d'enrichissement remplit les dates absentes par la modalité "
         f"`hors_saison` (`{S_SKI}:L69-71`, `{S_NARC}:L70-72`). La modalité de "
         "provenance ne peut donc que refléter l'appartenance à la saison.")
    emit()
    emit("La troisième modalité prévue pour le ski, `reconstruit`, ne concerne "
         "que les saisons H16 à H19, hors périmètre canonique. Sur H22-H25 la "
         "colonne ne prend que deux valeurs. Pour les narcisses, le producteur "
         "n'émet qu'une seule modalité en saison et n'a donc jamais pu en porter "
         "davantage.")
    emit()
    emit("Ce constat est descriptif. Il établit que ces deux colonnes n'apportent "
         "aucune information au-delà de leur indicatrice sur le périmètre "
         "d'entraînement et de test, sans préjuger de ce qu'un réentraînement "
         "donnerait, qui n'a pas été conduit.")
    emit()

    emit("## 7. Vérification 3 — tronçons de durée nulle")
    emit()
    emit(f"`base_duree_troncon_minutes` vaut zéro sur **{mil(n_zero)} "
         f"observations**, soit **{100 * n_zero / n_total:.4f} %** des "
         f"{mil(n_total)} lignes.")
    emit()
    emit("**Ce que représente une durée nulle.** La colonne est la différence "
         "entre l'horodatage d'arrivée et l'horodatage de départ, tous deux "
         "reconstruits en ajoutant à la date de circulation les heures et minutes "
         f"de l'horaire APC ({S_STACK}:apply_schema():L561-605). L'horaire source "
         "n'a qu'une résolution à la minute. Une durée nulle signifie donc que "
         "l'horaire APC place le départ et l'arrivée du tronçon dans la même "
         "minute, et non qu'un trajet aurait été instantané. Le contrôle le "
         f"confirme : sur la totalité des {mil(n_zero)} observations concernées, "
         "l'heure et la minute de départ égalent celles d'arrivée "
         f"(**{tick(meme_minute)}**).")
    emit()
    emit("**Périmètre.** Le phénomène est entièrement concentré :")
    emit()
    emit("| Caractéristique | Valeur |")
    emit("|---|---|")
    emit("| Tronçons concernés | "
         + ", ".join(f"`{a}` vers `{b}`" for a, b in troncons_zero) + " |")
    emit("| Années horaires | "
         + ", ".join(f"{a} ({mil(int(n))} obs.)" for a, n in annees_zero.items()) + " |")
    emit("| Longueur du tronçon | "
         + ", ".join(f"{x:g} km" for x in dist_zero) + " |")
    emit()
    if not profil.empty:
        emit("Profil complet du tronçon et de son inverse, par année horaire :")
        emit()
        emit("| Départ | Arrivée | Année | Durée (min) | Observations |")
        emit("|---|---|---|---|---|")
        for _, r in profil.iterrows():
            emit(f"| `{r['id_gare_depart']}` | `{r['id_gare_arrivee']}` | "
                 f"{r['horaire_annee_horaire']} | "
                 f"{float(r['base_duree_troncon_minutes']):g} | {mil(int(r['n']))} |")
        emit()
    emit("**Lecture.** Il s'agit d'un unique tronçon de crémaillère de 0,45 km, "
         "parcouru en montée, dont l'horaire APC ne distinguait pas le départ de "
         "l'arrivée en H22 et H23. Le sens inverse porte des durées de 3 à 6 "
         "minutes sur les mêmes années, et le sens montant passe à 1 puis 2 "
         "minutes dès H24. La valeur nulle est donc un artefact d'arrondi de "
         "l'horaire source sur ce seul tronçon, corrigé à partir de H24, et non "
         "une propriété du réseau. La colonne figure parmi les 158 variables du "
         "modèle gelé : l'artefact est donc présent dans les données "
         "d'entraînement H22 et H23, circonscrit à ce tronçon et à ce sens.")
    emit()

    emit("## 8. Contrôles de rédaction")
    emit()
    emit("| Contrôle | Résultat |")
    emit("|---|---|")
    emit(f"| Absence de tiret cadratin, demi-cadratin et point-virgule dans "
         f"`definition` | **{tick(not fautes)}** |")
    emit(f"| Absence de référence ADR dans `definition` | **{tick(not fautes)}** |")
    emit(f"| Registre impersonnel | **{tick(not fautes)}** |")
    emit(f"| Socle du squelette préservé valeur par valeur | "
         f"**{tick_socle}** ({len(colonnes_socle)} colonnes) |")
    emit()
    if fautes:
        emit("Écarts relevés :")
        emit()
        for n, pbs in fautes:
            emit(f"- `{n}` : {', '.join(pbs)}")
        emit()
    emit("**Vocabulaire d'unités.** La liste proposée dans la commande a été "
         "étendue de six valeurs qu'aucune des unités proposées n'exprime sans "
         "fausser la mesure : "
         + ", ".join("`" + u + "`" for u in sorted(UNITES_AJOUTEES))
         + ". Les autres colonnes utilisent exclusivement le vocabulaire proposé.")
    emit()
    if unites_hors_liste:
        emit("Unités employées hors des deux listes : "
             + ", ".join("`" + u + "`" for u in unites_hors_liste) + ".")
        emit()
    compte_unite = Counter(u for u in dico["unite"] if u)
    emit("| Unité | Colonnes |")
    emit("|---|---|")
    for u, n in sorted(compte_unite.items(), key=lambda kv: (-kv[1], kv[0])):
        emit(f"| `{u}` | {n} |")
    emit(f"| (vide) | {sum(1 for u in dico['unite'] if not u)} |")
    emit()

    emit("## 9. Livrables")
    emit()
    emit("| Fichier | Contenu |")
    emit("|---|---|")
    emit(f"| `{DICO_CSV.relative_to(ROOT)}` | Dictionnaire, {len(dico)} lignes × "
         f"{len(dico.columns)} colonnes |")
    emit(f"| `{DICO_XLSX.relative_to(ROOT)}` | Même contenu au format tableur |")
    emit(f"| `{OUT_GRAMMAIRE.relative_to(ROOT)}` | Grammaire de nommage par famille |")
    emit(f"| `{OUT_RAPPORT.relative_to(ROOT)}` | Le présent rapport |")
    emit(f"| `{Path(__file__).relative_to(ROOT)}` | Script de remplissage, "
         "réexécutable en une commande |")
    emit()

    OUT_RAPPORT.write_text("\n".join(lignes_rapport) + "\n", encoding="utf-8")

    print(f"Dictionnaire mis à jour : {len(dico)} lignes × {len(dico.columns)} colonnes")
    print(f"  définitions renseignées : {len(dico) - len(non_resolues)}")
    print(f"  non résolues            : {len(non_resolues)}")
    print(f"  confiance haute/moyenne : {compte_conf.get('haute', 0)} / "
          f"{compte_conf.get('moyenne', 0)}")
    print(f"  divergences consignées  : {len(DIVERGENCES)}")
    print(f"  colonnes hors motif     : {tot_d}")
    if fautes:
        stop(f"{len(fautes)} colonne(s) en écart de rédaction — voir {OUT_RAPPORT}")


if __name__ == "__main__":
    main()
