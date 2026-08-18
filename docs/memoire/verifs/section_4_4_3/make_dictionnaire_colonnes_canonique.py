#!/usr/bin/env python3
"""Annexe §4.4.3 — dictionnaire de données de la table canonique + réconciliation
209 / 179 / 158.

Objet
-----
Produire, en LECTURE SEULE sur les artefacts gelés, deux livrables :

  1. Le squelette machine du dictionnaire de données : une ligne par colonne de
     `data/processed/ml_dataset.parquet` (empreinte SHA256[:8] = `ba493568`,
     gel v2 ADR-076), avec famille, types, cardinalité, taux de valeurs
     manquantes par période, grain de variation et statut de sélection.
     La colonne `definition` est laissée VIDE : elle est remplie à la main.

  2. Le rapport de réconciliation `reconciliation_209_179_158.md` : assertions
     bloquantes sur les décomptes (209 colonnes, 158 features, tableau 9 des
     familles), reconstruction colonne par colonne du tableau 13 (répartition
     des 51 colonnes hors modèle) et contrôle croisé des taux de manquants
     cités en §4.4.2 (`histo_*`) et §4.5.4 (`simba_*`).

Provenance de la liste des 158 features
---------------------------------------
Elle est lue dans l'ARTEFACT DU MODÈLE GELÉ lui-même — `learner.feature_names`
du booster `models/enrichi_seg/enrichi_seg_bas_ba493568.json`, relu via
`xgboost.Booster.load_model` — et NON par réexécution des règles de sélection.
Le booster HAUT et la liste sérialisée au gel
(`outputs/couche2/features_158f_sans_simba.json`) servent de contre-épreuves :
le script assère l'identité des trois listes, ordre compris.

Réconciliation historique
-------------------------
La chaîne 179 -> 171 -> 172 -> 170 -> 158 est rejouée nominalement depuis les
listes persistées sous `archive/explorations/consolidation_finale/outputs/`
(ADR-048, ADR-054, ADR-057, ADR-061) ; aucune règle n'est réexécutée.

Exécution (une commande, déterministe — aucun horodatage dans les sorties) :

    venv/bin/python docs/memoire/verifs/section_4_4_3/make_dictionnaire_colonnes_canonique.py

LECTURE SEULE : aucune donnée ni aucun artefact de modèle n'est modifié.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import xgboost as xgb

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
TABLEAUX = ROOT / "docs" / "memoire" / "tableaux" / "section_4_4_3"

CANON = ROOT / "data" / "processed" / "ml_dataset.parquet"
MODEL_BAS = ROOT / "models" / "enrichi_seg" / "enrichi_seg_bas_ba493568.json"
MODEL_HAUT = ROOT / "models" / "enrichi_seg" / "enrichi_seg_haut_ba493568.json"
MODEL_META = ROOT / "models" / "enrichi_seg" / "enrichi_seg_metadata.json"
FEATURES_JSON = ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"

ARCH = ROOT / "archive" / "explorations" / "consolidation_finale" / "outputs"
LISTE_179 = ARCH / "etape_04_shap_importance_bas.csv"          # ADR-048 / ADR-053
LISTE_171 = ARCH / "etape_04bis_features_171.json"             # ADR-054 §1
LISTE_170 = ARCH / "etape_04bis_v2_features_170f.json"         # ADR-054 §2 + ADR-057
RETIREES_8 = ARCH / "etape_04bis_features_retirees_8.csv"      # ADR-054 §1 (les 8)

OUT_CSV = TABLEAUX / "dictionnaire_colonnes_canonique.csv"
OUT_XLSX = TABLEAUX / "dictionnaire_colonnes_canonique.xlsx"
OUT_MD = DOSSIER / "reconciliation_209_179_158.md"

HASH_ATTENDU = "ba493568"

# --------------------------------------------------------------------------- #
# Contrats du mémoire (valeurs à reproduire, jamais à recalculer par ajustement)
# --------------------------------------------------------------------------- #
N_COLONNES_ATTENDU = 209
N_FEATURES_ATTENDU = 158

# Tableau 9 du mémoire — comptes par famille
TABLEAU_9 = {
    "spatial_": 55, "ist_": 28, "meteo_": 27, "event_": 20, "histo_": 16,
    "cal_": 15, "simba_": 14, "base_": 8, "resa_": 8, "id_": 6, "vmcv_": 6,
    "horaire_": 3, "target_": 3,
}

# Tableau 13 du mémoire — répartition annoncée des colonnes hors modèle
TABLEAU_13 = {
    "retrait structurel": 30,
    "contribution nulle": 8,
    "gain nul": 2,
    "famille SIMBA": 12,
}

# ADR-054 §2 — les 2 features à gain XGBoost nul retirées de 172f
GAIN_NUL_2 = [
    "spatial_gare_arrivee_hpi_ha_classe_2",
    "spatial_gare_arrivee_hpi_ha_autre",
]

# Sous-catégories nominales du « retrait structurel » (ADR-064 amendement pour
# les emplois ; identifiants / cibles / offre / drapeaux de provenance sont des
# colonnes de traçabilité jamais soumises au modèle).
STRUCTUREL_SOUS_CAT = {
    "identifiants et clés": [
        "id_source_file", "id_gare_depart", "id_gare_arrivee",
        "id_gare_depart_bpuic", "id_gare_arrivee_bpuic",
        "id_statpop_reference_year", "horaire_annee_horaire",
        "horaire_numero_train", "horaire_service_id_complet",
        "base_date", "base_depart_datetime", "base_arrivee_datetime",
    ],
    "colonnes techniques (sens, offre)": [
        "base_sens", "base_offre_1ere_classe", "base_offre_2eme_classe",
        "base_offre_total",
    ],
    "cibles": [
        "target_voyageurs_1ere_classe", "target_voyageurs_2eme_classe",
        "target_voyageurs_total",
    ],
    "drapeaux de provenance": [
        "spatial_statpop_source_depart", "spatial_statpop_source_arrivee",
        "vmcv_source_depart", "vmcv_source_arrivee",
        "simba_source_depart", "simba_source_arrivee",
    ],
    "emplois (STATENT, ADR-064 amendement)": [
        "spatial_gare_depart_emplois_500m_total",
        "spatial_gare_depart_emplois_500m_services",
        "spatial_gare_arrivee_emplois_500m_total",
        "spatial_gare_arrivee_emplois_500m_services",
    ],
}

# Fourchettes annoncées dans le manuscrit (contrôle croisé, section C)
HISTO_H25_BORNE_BASSE_PCT = 0.64   # §4.4.2
HISTO_H25_BORNE_HAUTE_PCT = 0.90   # §4.4.2

ANNEES_TRAIN = ["H22", "H23", "H24"]
ANNEE_TEST = "H25"
MAX_MODALITES_LISTEES = 12


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def sha256_8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def stop(msg: str) -> None:
    print(f"\n*** STOP — {msg}", file=sys.stderr)
    sys.exit(1)


def famille(nom: str) -> str:
    """Préfixe avant le premier underscore, underscore inclus."""
    return nom.split("_", 1)[0] + "_" if "_" in nom else nom


def codes_cle(df: pd.DataFrame, colonnes: list[str]) -> np.ndarray:
    """Code entier dense (0..G-1) du n-uplet de colonnes de groupement."""
    combine = np.zeros(len(df), dtype=np.int64)
    for col in colonnes:
        c, u = pd.factorize(df[col], use_na_sentinel=False)
        combine = combine * np.int64(len(u)) + c.astype(np.int64)
    return pd.factorize(combine, use_na_sentinel=False)[0].astype(np.int64)


def est_constante(ordre: np.ndarray, g_trie: np.ndarray, v: np.ndarray) -> bool:
    """La colonne (codes `v`) est-elle constante dans chaque groupe ?

    NaN compte comme une modalité à part entière : un groupe mêlant NaN et une
    valeur observée n'est PAS constant.
    """
    v_trie = v[ordre]
    meme_groupe = g_trie[1:] == g_trie[:-1]
    valeur_change = v_trie[1:] != v_trie[:-1]
    return not bool(np.any(meme_groupe & valeur_change))


def formate_modalites(valeurs: list) -> str:
    out = []
    for v in valeurs:
        if isinstance(v, pd.Timestamp):
            out.append(v.isoformat())
        elif isinstance(v, (np.floating, float)):
            out.append(f"{float(v):g}")
        else:
            out.append(str(v))
    return " | ".join(out)


def pct(n: int, d: int) -> float:
    return float("nan") if d == 0 else round(100.0 * n / d, 4)


# Époque fixe pour le classeur : un .xlsx est une archive zip, dont les
# horodatages d'entrées et les propriétés `created`/`modified` briseraient la
# reproductibilité à l'octet. On les gèle.
EPOQUE_FIXE = dt.datetime(1980, 1, 1, 0, 0, 0)


def ecrit_xlsx_deterministe(df: pd.DataFrame, chemin: Path, feuille: str) -> None:
    """Écrit un .xlsx byte-reproductible (aucun horodatage d'exécution)."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=feuille, index=False)
        props = xl.book.properties
        props.created = EPOQUE_FIXE
        props.modified = EPOQUE_FIXE
        props.creator = "make_dictionnaire_colonnes_canonique.py"
        props.lastModifiedBy = "make_dictionnaire_colonnes_canonique.py"

    # openpyxl réécrit `dcterms:modified` à l'heure courante au moment du save :
    # on le regèle après coup, en même temps que les horodatages du zip.
    horodatage_fige = EPOQUE_FIXE.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    source = zipfile.ZipFile(io.BytesIO(tampon.getvalue()))
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for info in source.infolist():
            contenu = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                contenu = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)",
                    rb"\g<1>" + horodatage_fige + rb"\g<2>", contenu)
            fige = zipfile.ZipInfo(info.filename, date_time=EPOQUE_FIXE.timetuple()[:6])
            fige.compress_type = info.compress_type
            fige.external_attr = info.external_attr
            z.writestr(fige, contenu)
    chemin.write_bytes(sortie.getvalue())


def mil(n: int) -> str:
    """Entier avec espace fine comme séparateur de milliers."""
    return f"{n:,}".replace(",", " ")


# --------------------------------------------------------------------------- #
# 0. Gardes d'entrée
# --------------------------------------------------------------------------- #
def main() -> None:
    lignes_rapport: list[str] = []

    def emit(s: str = "") -> None:
        print(s)
        lignes_rapport.append(s)

    for p in (CANON, MODEL_BAS, MODEL_HAUT, MODEL_META, FEATURES_JSON,
              LISTE_179, LISTE_171, LISTE_170, RETIREES_8):
        if not p.exists():
            stop(f"fichier source absent : {p}")

    h_canon = sha256_8(CANON)
    if h_canon != HASH_ATTENDU:
        stop(
            f"empreinte du dataset non conforme : lue {h_canon!r}, "
            f"attendue {HASH_ATTENDU!r}. Le dictionnaire n'est pas produit."
        )

    h_bas, h_haut = sha256_8(MODEL_BAS), sha256_8(MODEL_HAUT)

    # ----------------------------------------------------------------------- #
    # 1. Liste des features DEPUIS L'ARTEFACT DU MODÈLE
    # ----------------------------------------------------------------------- #
    booster_bas = xgb.Booster()
    booster_bas.load_model(str(MODEL_BAS))
    features = list(booster_bas.feature_names or [])

    booster_haut = xgb.Booster()
    booster_haut.load_model(str(MODEL_HAUT))
    features_haut = list(booster_haut.feature_names or [])

    meta_gel = json.loads(FEATURES_JSON.read_text())
    features_json = list(meta_gel["features"])
    simba_retirees = list(meta_gel["simba_features_removed"])

    if features != features_haut:
        stop("les listes de features des boosters BAS et HAUT diffèrent")
    if features != features_json:
        stop("la liste du booster diffère de la liste sérialisée au gel")
    if len(features) != N_FEATURES_ATTENDU:
        stop(f"le booster déclare {len(features)} features, attendu {N_FEATURES_ATTENDU}")

    set_features = set(features)

    # ----------------------------------------------------------------------- #
    # 2. Schéma parquet
    # ----------------------------------------------------------------------- #
    pf = pq.ParquetFile(CANON)
    schema_arrow = pf.schema_arrow
    schema_parquet = pf.schema
    colonnes = list(schema_arrow.names)
    n_lignes = pf.metadata.num_rows

    if len(colonnes) != N_COLONNES_ATTENDU:
        stop(f"{len(colonnes)} colonnes lues, attendu {N_COLONNES_ATTENDU}")

    type_arrow = {n: str(schema_arrow.field(n).type) for n in colonnes}
    type_physique = {schema_parquet.column(i).name: schema_parquet.column(i).physical_type
                     for i in range(len(schema_parquet.names))}

    # ----------------------------------------------------------------------- #
    # 3. Clés de groupement (adaptées aux colonnes réelles de la table)
    # ----------------------------------------------------------------------- #
    cols_cles = ["horaire_annee_horaire", "id_gare_depart", "id_gare_arrivee",
                 "base_date", "cal_heure_depart", "horaire_numero_train",
                 "id_statpop_reference_year"]
    df_cles = pd.read_parquet(CANON, columns=cols_cles)

    # Échelle demandée -> colonnes réelles. `troncon` n'existe pas comme colonne :
    # il est porté par le couple (gare de départ, gare d'arrivée), qui encode
    # aussi le sens. `millesime` = millésime STATPOP porté par
    # `id_statpop_reference_year`. `heure` = heure de départ.
    ECHELLES = [
        ("troncon",           ["id_gare_depart", "id_gare_arrivee"]),
        ("arret_millesime_depart",  ["id_gare_depart", "id_statpop_reference_year"]),
        ("arret_millesime_arrivee", ["id_gare_arrivee", "id_statpop_reference_year"]),
        ("date",              ["base_date"]),
        ("date_heure",        ["base_date", "cal_heure_depart"]),
        ("troncon_date",      ["id_gare_depart", "id_gare_arrivee", "base_date"]),
        ("numero_train_date", ["horaire_numero_train", "base_date"]),
    ]
    # Libellé restitué dans le dictionnaire (les deux variantes « arrêt x millésime »
    # sont testées à la même marche de l'échelle, dans cet ordre).
    LIBELLE_ECHELLE = {
        "troncon": "(troncon)",
        "arret_millesime_depart": "(arret, millesime)",
        "arret_millesime_arrivee": "(arret, millesime)",
        "date": "(date)",
        "date_heure": "(date, heure)",
        "troncon_date": "(troncon, date)",
        "numero_train_date": "(numero_train, date)",
    }
    CLE_REELLE = {nom: "(" + ", ".join(c) + ")" for nom, c in ECHELLES}

    prepare: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for nom, cols in ECHELLES:
        g = codes_cle(df_cles, cols)
        ordre = np.argsort(g, kind="stable")
        prepare[nom] = (ordre, g[ordre])

    n_groupes = {nom: int(prepare[nom][1][-1] + 1) for nom, _ in ECHELLES}

    # Masques de période
    annee = df_cles["horaire_annee_horaire"].astype("string")
    masque_train = annee.isin(ANNEES_TRAIN).to_numpy(dtype=bool, na_value=False)
    masque_test = (annee == ANNEE_TEST).to_numpy(dtype=bool, na_value=False)
    n_train, n_test = int(masque_train.sum()), int(masque_test.sum())
    if n_train + n_test != n_lignes:
        stop(f"partition H22-H24 / H25 incomplète : {n_train} + {n_test} != {n_lignes}")

    # Clé de DIAGNOSTIC, hors échelle demandée : sert uniquement à expliquer, en
    # §5.1, les colonnes topologiques qui retombent sur `(troncon, date)` faute
    # d'une marche `(troncon, annee_horaire)` dans l'échelle.
    g_diag = codes_cle(df_cles, ["id_gare_depart", "id_gare_arrivee",
                                 "horaire_annee_horaire"])
    ordre_diag = np.argsort(g_diag, kind="stable")
    diag_troncon_annee = (ordre_diag, g_diag[ordre_diag])
    n_groupes_diag = int(diag_troncon_annee[1][-1] + 1)

    # ----------------------------------------------------------------------- #
    # 4. Parcours colonne par colonne
    # ----------------------------------------------------------------------- #
    enregistrements = []
    nan_par_colonne: dict[str, dict[str, float]] = {}
    constantes_troncon_annee: list[str] = []

    for i, nom in enumerate(colonnes):
        s = pd.read_parquet(CANON, columns=[nom])[nom]
        isna = s.isna().to_numpy(dtype=bool)

        n_nan_tot = int(isna.sum())
        n_nan_train = int(isna[masque_train].sum())
        n_nan_test = int(isna[masque_test].sum())
        taux = {
            "h22_h24": pct(n_nan_train, n_train),
            "h25": pct(n_nan_test, n_test),
            "total": pct(n_nan_tot, n_lignes),
        }
        nan_par_colonne[nom] = taux

        nunique = int(s.nunique(dropna=True))
        if nunique <= MAX_MODALITES_LISTEES:
            modalites = formate_modalites(sorted(s.dropna().unique().tolist()))
        else:
            modalites = ""

        codes_v = pd.factorize(s, use_na_sentinel=False)[0].astype(np.int64)
        grain, cle_utilisee = "par observation", ""
        for echelle, _ in ECHELLES:
            ordre, g_trie = prepare[echelle]
            if est_constante(ordre, g_trie, codes_v):
                grain = LIBELLE_ECHELLE[echelle]
                cle_utilisee = CLE_REELLE[echelle]
                break
        if est_constante(*diag_troncon_annee, codes_v):
            constantes_troncon_annee.append(nom)

        enregistrements.append({
            "ordre_parquet": i,
            "nom": nom,
            "famille": famille(nom),
            "definition": "",
            "dtype_parquet_physique": type_physique.get(nom, ""),
            "dtype_parquet_logique": type_arrow[nom],
            "dtype_pandas": str(s.dtype),
            "nunique": nunique,
            "valeurs_distinctes_si_nunique_le_12": modalites,
            "taux_nan_h22_h24_pct": taux["h22_h24"],
            "taux_nan_h25_pct": taux["h25"],
            "taux_nan_total_pct": taux["total"],
            "n_nan_total": n_nan_tot,
            "grain_variation": grain,
            "grain_cle_reelle": cle_utilisee,
            "statut_selection": "retenue" if nom in set_features else "hors modèle",
        })
        del s, codes_v, isna

    dico = pd.DataFrame(enregistrements)

    # ----------------------------------------------------------------------- #
    # 5. Réconciliation
    # ----------------------------------------------------------------------- #
    hors_modele = [c for c in colonnes if c not in set_features]
    n_hors = len(hors_modele)

    comptes_familles = dico["famille"].value_counts().to_dict()

    # Chaîne historique, rejouée nominalement
    with open(LISTE_179, newline="") as fh:
        f179 = [r["feature"] for r in csv.DictReader(fh)]
    f171 = json.loads(LISTE_171.read_text())["features"]
    f170 = json.loads(LISTE_170.read_text())["features"]
    with open(RETIREES_8, newline="") as fh:
        contribution_nulle_8 = [r["feature"] for r in csv.DictReader(fh)]

    # Le bloc « retrait structurel » du tableau 13 = complément du vivier 179
    structurel_30 = [c for c in colonnes if c not in set(f179)]
    structurel_hors_modele = [c for c in structurel_30 if c not in set_features]
    structurel_retenues = [c for c in structurel_30 if c in set_features]

    categorie = {}
    for c in structurel_30:
        categorie[c] = "retrait structurel"
    for c in contribution_nulle_8:
        categorie[c] = "contribution nulle"
    for c in GAIN_NUL_2:
        categorie[c] = "gain nul"
    for c in simba_retirees:
        categorie[c] = "famille SIMBA"

    sous_cat = {}
    for lib, membres in STRUCTUREL_SOUS_CAT.items():
        for c in membres:
            sous_cat[c] = lib

    dico["categorie_tableau_13"] = dico["nom"].map(categorie).fillna("")
    dico["sous_categorie_structurelle"] = dico["nom"].map(sous_cat).fillna("")
    dico["reference_adr"] = dico["nom"].map(
        {**{c: "ADR-048 (vivier 179)" for c in structurel_30},
         **{c: "ADR-054 §1" for c in contribution_nulle_8},
         **{c: "ADR-054 §2" for c in GAIN_NUL_2},
         **{c: "ADR-061" for c in simba_retirees},
         "spatial_denivele_troncon_m": "ADR-057 (réintroduite)"}
    ).fillna("")
    for c in STRUCTUREL_SOUS_CAT["emplois (STATENT, ADR-064 amendement)"]:
        dico.loc[dico["nom"] == c, "reference_adr"] = "ADR-064 (amendement)"

    # --- Assertions bloquantes ------------------------------------------------
    echecs: list[str] = []

    if len(colonnes) != N_COLONNES_ATTENDU:
        echecs.append(f"nombre de colonnes = {len(colonnes)} != {N_COLONNES_ATTENDU}")
    if len(features) != N_FEATURES_ATTENDU:
        echecs.append(f"nombre de features = {len(features)} != {N_FEATURES_ATTENDU}")
    if n_hors != N_COLONNES_ATTENDU - N_FEATURES_ATTENDU:
        echecs.append(f"colonnes hors modèle = {n_hors} != "
                      f"{N_COLONNES_ATTENDU - N_FEATURES_ATTENDU}")

    if comptes_familles != TABLEAU_9:
        for f in sorted(set(comptes_familles) | set(TABLEAU_9)):
            lu, att = comptes_familles.get(f, 0), TABLEAU_9.get(f, 0)
            if lu != att:
                echecs.append(f"famille {f} : lue {lu}, tableau 9 annonce {att}")

    if set(f179) - set(colonnes):
        echecs.append("le vivier 179 contient des noms absents des 209 colonnes")
    if set(f179) - set(contribution_nulle_8) != set(f171):
        echecs.append("chaîne ADR-054 §1 : 179 − 8 != 171")
    if set(f170) - set(f171) != {"spatial_denivele_troncon_m"}:
        echecs.append("chaîne ADR-057 : 171 + dénivelé != 172 − 2")
    if set(f171) - set(f170) != set(GAIN_NUL_2):
        echecs.append("chaîne ADR-054 §2 : les 2 features à gain nul ne se retrouvent pas")
    if set(f170) - set(simba_retirees) != set_features:
        echecs.append("chaîne ADR-061 : 170 − 12 SIMBA != les 158 du booster")

    if len(structurel_30) != TABLEAU_13["retrait structurel"]:
        echecs.append(f"retrait structurel = {len(structurel_30)} != "
                      f"{TABLEAU_13['retrait structurel']}")
    if len(contribution_nulle_8) != TABLEAU_13["contribution nulle"]:
        echecs.append("bloc « contribution nulle » != 8")
    if len(GAIN_NUL_2) != TABLEAU_13["gain nul"]:
        echecs.append("bloc « gain nul » != 2")
    if len(simba_retirees) != TABLEAU_13["famille SIMBA"]:
        echecs.append("bloc « famille SIMBA » != 12")

    blocs = [structurel_30, contribution_nulle_8, GAIN_NUL_2, simba_retirees]
    union = set().union(*blocs)
    somme = sum(len(b) for b in blocs)
    if union != set(hors_modele) | set(structurel_retenues):
        echecs.append("l'union des 4 blocs du tableau 13 ne couvre pas les colonnes visées")
    if somme - len(union) != 0:
        echecs.append("les 4 blocs du tableau 13 se recouvrent")
    if structurel_retenues != ["spatial_denivele_troncon_m"]:
        echecs.append(f"colonnes du bloc structurel présentes dans le modèle : "
                      f"{structurel_retenues} (attendu le seul dénivelé)")

    membres_sous_cat = [c for m in STRUCTUREL_SOUS_CAT.values() for c in m]
    if set(membres_sous_cat) != set(structurel_hors_modele):
        manquants = sorted(set(structurel_hors_modele) - set(membres_sous_cat))
        surplus = sorted(set(membres_sous_cat) - set(structurel_hors_modele))
        echecs.append(f"sous-catégories structurelles incomplètes — "
                      f"non classées : {manquants} ; hors périmètre : {surplus}")

    # ----------------------------------------------------------------------- #
    # 6. Contrôle croisé des valeurs du manuscrit
    # ----------------------------------------------------------------------- #
    histo = sorted(c for c in colonnes if c.startswith("histo_"))
    simba_part = sorted(c for c in colonnes if c.startswith("simba_part_"))
    simba_source = sorted(c for c in colonnes if c.startswith("simba_source_"))

    histo_h25 = {c: nan_par_colonne[c]["h25"] for c in histo}
    simba_part_h25 = {c: nan_par_colonne[c]["h25"] for c in simba_part}
    simba_source_h25 = {c: nan_par_colonne[c]["h25"] for c in simba_source}

    # H22 seul (le taux « total » ne suffit pas : il agrège H22-H24)
    df_h22 = pd.read_parquet(CANON, columns=["horaire_annee_horaire"])
    masque_h22 = (df_h22["horaire_annee_horaire"].astype("string") == "H22").to_numpy(
        dtype=bool, na_value=False)
    n_h22 = int(masque_h22.sum())
    simba_h22 = {}
    for c in simba_part + simba_source:
        s = pd.read_parquet(CANON, columns=[c])[c]
        simba_h22[c] = pct(int(s.isna().to_numpy(dtype=bool)[masque_h22].sum()), n_h22)
    del df_h22

    # --- Éléments de la note §5.1 --------------------------------------------
    DENIV = "spatial_denivele_troncon_m"
    n_train_modele = int(json.loads(MODEL_META.read_text())["split"]["n_train"])

    cible_diag = [c for c in constantes_troncon_annee
                  if dico.loc[dico["nom"] == c, "grain_variation"].iloc[0]
                  == "(troncon, date)"]
    df_diag = pd.read_parquet(
        CANON, columns=["horaire_annee_horaire", "id_gare_depart",
                        "id_gare_arrivee", DENIV] + cible_diag)

    # Pour chaque colonne visée, on ne restitue que les tronçons dont la valeur
    # change d'une année horaire à l'autre : ce sont eux qui interdisent la
    # marche `(troncon)` de l'échelle.
    revisions_diag: dict[str, list[str]] = {}
    for c in cible_diag:
        par_troncon_annee = (
            df_diag.groupby(["id_gare_depart", "id_gare_arrivee",
                             "horaire_annee_horaire"], observed=True)[c]
            .first().unstack("horaire_annee_horaire"))
        varie = par_troncon_annee.nunique(axis=1, dropna=True) > 1
        lignes = []
        for (dep, arr), row in par_troncon_annee[varie].iterrows():
            detail = ", ".join(f"{a} = {float(v):g}" for a, v in row.items()
                               if pd.notna(v))
            lignes.append(f"`{dep}→{arr}` ({detail})")
        revisions_diag[c] = lignes

    na_deniv = df_diag[DENIV].isna()
    n_nan_deniv = int(na_deniv.sum())
    troncons_deniv_nan = sorted(
        set(zip(df_diag.loc[na_deniv, "id_gare_depart"],
                df_diag.loc[na_deniv, "id_gare_arrivee"])))
    annees_deniv_nan = sorted(
        set(df_diag.loc[na_deniv, "horaire_annee_horaire"].dropna()))
    del df_diag

    histo_min, histo_max = min(histo_h25.values()), max(histo_h25.values())
    simba_part_min = min(simba_part_h25.values())
    simba_part_max = max(simba_part_h25.values())
    simba_h22_part_min = min(simba_h22[c] for c in simba_part)
    simba_h22_part_max = max(simba_h22[c] for c in simba_part)

    ok_histo = (round(histo_min, 2) >= HISTO_H25_BORNE_BASSE_PCT
                and round(histo_max, 2) <= HISTO_H25_BORNE_HAUTE_PCT)
    ok_simba_moitie = 40.0 <= simba_part_min and simba_part_max <= 60.0
    ok_simba_h22 = simba_h22_part_min == 100.0 and simba_h22_part_max == 100.0

    # ----------------------------------------------------------------------- #
    # 7. Écriture des livrables
    # ----------------------------------------------------------------------- #
    TABLEAUX.mkdir(parents=True, exist_ok=True)
    ordre_colonnes = [
        "ordre_parquet", "nom", "famille", "definition",
        "dtype_parquet_physique", "dtype_parquet_logique", "dtype_pandas",
        "nunique", "valeurs_distinctes_si_nunique_le_12",
        "taux_nan_h22_h24_pct", "taux_nan_h25_pct", "taux_nan_total_pct",
        "n_nan_total", "grain_variation", "grain_cle_reelle",
        "statut_selection", "categorie_tableau_13",
        "sous_categorie_structurelle", "reference_adr",
    ]
    dico = dico[ordre_colonnes]
    dico.to_csv(OUT_CSV, index=False, encoding="utf-8")
    ecrit_xlsx_deterministe(dico, OUT_XLSX, "dictionnaire")

    # ----------------------------------------------------------------------- #
    # 8. Rapport
    # ----------------------------------------------------------------------- #
    def tick(b: bool) -> str:
        return "OK" if b else "ÉCART"

    emit("# Réconciliation 209 / 179 / 158 — table canonique `ml_dataset.parquet`")
    emit()
    emit("Annexe §4.4.3 — dictionnaire de données. Rapport produit en lecture seule par")
    emit("`docs/memoire/verifs/section_4_4_3/make_dictionnaire_colonnes_canonique.py`.")
    emit()
    emit("## 1. Fichiers sources et empreintes")
    emit()
    emit("| Rôle | Chemin | Empreinte SHA256[:8] |")
    emit("|---|---|---|")
    emit(f"| Table canonique | `data/processed/ml_dataset.parquet` | `{h_canon}` |")
    emit(f"| Modèle gelé BAS (source des 158 noms) | `models/enrichi_seg/enrichi_seg_bas_ba493568.json` | `{h_bas}` |")
    emit(f"| Modèle gelé HAUT (contre-épreuve) | `models/enrichi_seg/enrichi_seg_haut_ba493568.json` | `{h_haut}` |")
    emit(f"| Liste sérialisée au gel (contre-épreuve) | `outputs/couche2/features_158f_sans_simba.json` | `{sha256_8(FEATURES_JSON)}` |")
    emit(f"| Vivier 179 (ADR-048/053) | `{LISTE_179.relative_to(ROOT)}` | `{sha256_8(LISTE_179)}` |")
    emit(f"| Liste 171 (ADR-054 §1) | `{LISTE_171.relative_to(ROOT)}` | `{sha256_8(LISTE_171)}` |")
    emit(f"| Liste 170 (ADR-054 §2 + ADR-057) | `{LISTE_170.relative_to(ROOT)}` | `{sha256_8(LISTE_170)}` |")
    emit(f"| Les 8 à contribution nulle (ADR-054 §1) | `{RETIREES_8.relative_to(ROOT)}` | `{sha256_8(RETIREES_8)}` |")
    emit()
    emit(f"Volumétrie : **{mil(n_lignes)}** lignes × **{len(colonnes)}** colonnes "
         f"(H22-H24 : {mil(n_train)} ; H25 : {mil(n_test)}).")
    emit()
    emit("**Provenance de la liste du modèle gelé.** Les 158 noms sont lus dans")
    emit("`learner.feature_names` du booster BAS relu par `xgboost.Booster.load_model`,")
    emit("et non par réexécution des règles de sélection. Le booster HAUT et")
    emit("`features_158f_sans_simba.json` donnent la **même liste, ordre compris**")
    emit("(assertion bloquante du script).")
    emit()

    emit("## 2. Assertions bloquantes")
    emit()
    emit("| Assertion | Attendu | Lu | Verdict |")
    emit("|---|---|---|---|")
    emit(f"| Empreinte de la table canonique | `{HASH_ATTENDU}` | `{h_canon}` | {tick(h_canon == HASH_ATTENDU)} |")
    emit(f"| Nombre total de colonnes | {N_COLONNES_ATTENDU} | {len(colonnes)} | {tick(len(colonnes) == N_COLONNES_ATTENDU)} |")
    emit(f"| Colonnes retenues (features du booster) | {N_FEATURES_ATTENDU} | {len(features)} | {tick(len(features) == N_FEATURES_ATTENDU)} |")
    emit(f"| Colonnes hors modèle | {N_COLONNES_ATTENDU - N_FEATURES_ATTENDU} | {n_hors} | {tick(n_hors == N_COLONNES_ATTENDU - N_FEATURES_ATTENDU)} |")
    emit(f"| Listes BAS / HAUT / gel identiques (ordre compris) | oui | {'oui' if features == features_haut == features_json else 'non'} | {tick(features == features_haut == features_json)} |")
    emit()

    emit("### 2.1 Comptes par famille — tableau 9 du mémoire")
    emit()
    emit("| Famille | Tableau 9 | Lu | Verdict | dont retenues | dont hors modèle |")
    emit("|---|---|---|---|---|---|")
    for f in sorted(TABLEAU_9, key=lambda x: (-TABLEAU_9[x], x)):
        lu = comptes_familles.get(f, 0)
        sous = dico[dico["famille"] == f]
        nret = int((sous["statut_selection"] == "retenue").sum())
        emit(f"| `{f}` | {TABLEAU_9[f]} | {lu} | {tick(lu == TABLEAU_9[f])} | {nret} | {lu - nret} |")
    emit(f"| **Total** | **{sum(TABLEAU_9.values())}** | **{sum(comptes_familles.values())}** | "
         f"**{tick(comptes_familles == TABLEAU_9)}** | **{len(features)}** | **{n_hors}** |")
    emit()
    familles_hors_tableau = sorted(set(comptes_familles) - set(TABLEAU_9))
    if familles_hors_tableau:
        emit(f"Familles présentes dans la table mais absentes du tableau 9 : "
             f"{', '.join('`' + f + '`' for f in familles_hors_tableau)}.")
    else:
        emit("Aucune famille en dehors des 13 du tableau 9 ; le tableau 9 est reproduit exactement.")
    emit()

    emit("## 3. Tableau 13 — répartition des colonnes hors modèle, colonne par colonne")
    emit()
    emit("| Bloc | Tableau 13 | Reconstruit | dont hors modèle | dont retenues | Verdict |")
    emit("|---|---|---|---|---|---|")
    for lib, membres in (("retrait structurel", structurel_30),
                         ("contribution nulle", contribution_nulle_8),
                         ("gain nul", GAIN_NUL_2),
                         ("famille SIMBA", simba_retirees)):
        nret = sum(1 for c in membres if c in set_features)
        emit(f"| {lib} | {TABLEAU_13[lib]} | {len(membres)} | {len(membres) - nret} | {nret} | "
             f"{tick(len(membres) == TABLEAU_13[lib])} |")
    emit(f"| **Somme des blocs** | **{sum(TABLEAU_13.values())}** | **{somme}** | **{n_hors}** | "
         f"**{somme - n_hors}** | — |")
    emit()
    emit(f"Somme annoncée {sum(TABLEAU_13.values())} ; colonnes hors modèle {n_hors} ; "
         f"écart **+{somme - n_hors}**.")
    emit()
    emit("**Origine de l'écart d'une unité — confirmée.** Le bloc « retrait structurel »")
    emit("est le complément exact du vivier de 179 variables soumis à la sélection")
    emit(f"(ADR-048) : {len(colonnes)} − {len(f179)} = {len(structurel_30)}, décompte du")
    emit("tableau 13 reproduit sans ajustement. Les 4 blocs sont deux à deux disjoints")
    emit(f"(vérifié : {somme} membres pour {len(union)} noms distincts) et couvrent")
    emit(f"{len(union)} colonnes, dont {n_hors} hors modèle et {somme - n_hors} retenue.")
    emit("Cette unique colonne à la fois « retirée » et présente dans le modèle gelé est")
    emit(f"**{', '.join('`' + c + '`' for c in structurel_retenues)}** (ADR-057) : créée")
    emit("**après** la constitution du vivier 179, elle en est absente pour une raison de")
    emit("chronologie et non de nature, puis réintroduite dans la chaîne 171 → 172. C'est")
    emit("exactement le dénivelé réintroduit annoncé par le manuscrit.")
    emit()
    emit(f"La répartition effective des {n_hors} colonnes hors modèle est donc")
    emit(f"**{len(structurel_hors_modele)} + {len(contribution_nulle_8)} + {len(GAIN_NUL_2)} + "
         f"{len(simba_retirees)} = {n_hors}**, et l'identité comptable s'écrit")
    emit(f"`{len(colonnes)} − {len(structurel_30)} = {len(f179)}` puis")
    emit(f"`{len(f179)} − {len(contribution_nulle_8)} + 1 − {len(GAIN_NUL_2)} − "
         f"{len(simba_retirees)} = {len(features)}`.")
    emit()

    emit("### 3.1 Chaîne de sélection rejouée nominalement")
    emit()
    emit("| Étape | ADR | Opération | N | Vérifié |")
    emit("|---|---|---|---|---|")
    emit(f"| Vivier soumis à sélection | ADR-048 | 209 − {len(structurel_30)} structurelles | {len(f179)} | "
         f"{tick(len(colonnes) - len(structurel_30) == len(f179))} |")
    emit(f"| Nettoyage §1 | ADR-054 §1 | − {len(contribution_nulle_8)} à contribution nulle (SHAP = 0,000 exact) | {len(f171)} | "
         f"{tick(set(f179) - set(contribution_nulle_8) == set(f171))} |")
    emit(f"| Ajout dénivelé | ADR-057 | + 1 `spatial_denivele_troncon_m` | 172 | "
         f"{tick(set(f170) - set(f171) == {'spatial_denivele_troncon_m'})} |")
    emit(f"| Nettoyage §2 | ADR-054 §2 | − {len(GAIN_NUL_2)} à gain XGBoost nul | {len(f170)} | "
         f"{tick(set(f171) - set(f170) == set(GAIN_NUL_2))} |")
    emit(f"| Retrait SIMBA | ADR-061 | − {len(simba_retirees)} `simba_part_*` | {len(features)} | "
         f"{tick(set(f170) - set(simba_retirees) == set_features)} |")
    emit()

    emit("### 3.2 Détail nominal des blocs")
    emit()
    emit(f"**Retrait structurel — {len(structurel_30)} colonnes** (complément du vivier 179) :")
    emit()
    emit("| Sous-catégorie | N | Colonnes |")
    emit("|---|---|---|")
    for lib, membres in STRUCTUREL_SOUS_CAT.items():
        emit(f"| {lib} | {len(membres)} | {', '.join('`' + c + '`' for c in membres)} |")
    emit(f"| réintroduite dans le modèle (hors nature structurelle) | {len(structurel_retenues)} | "
         f"{', '.join('`' + c + '`' for c in structurel_retenues)} |")
    emit(f"| **Total** | **{len(structurel_30)}** | — |")
    emit()
    emit(f"**Contribution nulle — {len(contribution_nulle_8)} colonnes** "
         f"(ADR-054 §1, `mean|SHAP|` = 0,000 exact dans BAS et HAUT) :")
    emit()
    for c in contribution_nulle_8:
        emit(f"- `{c}`")
    emit()
    emit(f"**Gain nul — {len(GAIN_NUL_2)} colonnes** (ADR-054 §2, gain XGBoost = 0 dans BAS et HAUT) :")
    emit()
    for c in GAIN_NUL_2:
        emit(f"- `{c}`")
    emit()
    emit(f"**Famille SIMBA — {len(simba_retirees)} colonnes** (ADR-061) :")
    emit()
    emit(", ".join("`" + c + "`" for c in simba_retirees))
    emit()
    emit("Note : la famille `simba_` compte 14 colonnes dans la table ; les 2 drapeaux de")
    emit("provenance `simba_source_depart` / `simba_source_arrivee` relèvent du bloc")
    emit("« retrait structurel », pas du bloc « famille SIMBA » (12 `simba_part_*`).")
    emit()

    emit("## 4. Contrôle croisé des valeurs citées dans le manuscrit")
    emit()
    emit(f"### 4.1 `histo_*` sur H25 — fourchette annoncée en §4.4.2 : "
         f"{HISTO_H25_BORNE_BASSE_PCT:.2f} % à {HISTO_H25_BORNE_HAUTE_PCT:.2f} %")
    emit()
    emit("| Variable | Taux de manquants H25 (%) | Effectif manquant |")
    emit("|---|---|---|")
    for c in histo:
        n = int(round(histo_h25[c] * n_test / 100))
        emit(f"| `{c}` | {histo_h25[c]:.4f} | {mil(n)} |")
    emit(f"| **Étendue** | **{histo_min:.4f} – {histo_max:.4f}** | — |")
    emit()
    emit(f"Verdict : **{tick(ok_histo)}** — la fourchette observée "
         f"[{histo_min:.2f} % ; {histo_max:.2f} %] est celle annoncée "
         f"[{HISTO_H25_BORNE_BASSE_PCT:.2f} % ; {HISTO_H25_BORNE_HAUTE_PCT:.2f} %] "
         f"(arrondi au centième).")
    emit()
    emit("### 4.2 `simba_*` sur H25 — « près de la moitié de valeurs structurellement manquantes » (§4.5.4)")
    emit()
    emit("| Variable | Taux de manquants H25 (%) |")
    emit("|---|---|")
    for c in simba_part:
        emit(f"| `{c}` | {simba_part_h25[c]:.4f} |")
    for c in simba_source:
        emit(f"| `{c}` (drapeau de provenance) | {simba_source_h25[c]:.4f} |")
    emit()
    emit(f"Verdict : **{tick(ok_simba_moitie)}** — les 12 `simba_part_*` sont à "
         f"{simba_part_min:.2f} % de manquants sur H25 "
         + ("(valeur unique)" if simba_part_min == simba_part_max
            else f"à {simba_part_max:.2f} %")
         + ", ce qui soutient la formulation « près de la moitié ».")
    emit()
    emit(f"### 4.3 `simba_*` sur H22 — manquants attendus en totalité ({mil(n_h22)} observations)")
    emit()
    emit("| Variable | Taux de manquants H22 (%) |")
    emit("|---|---|")
    for c in simba_part:
        emit(f"| `{c}` | {simba_h22[c]:.4f} |")
    for c in simba_source:
        emit(f"| `{c}` (drapeau de provenance) | {simba_h22[c]:.4f} |")
    emit()
    emit(f"Verdict : **{tick(ok_simba_h22)}** — les 12 `simba_part_*` sont à "
         f"{simba_h22_part_min:.2f} % de manquants sur H22.")
    emit()

    emit("## 5. Grain de variation — clés réellement employées")
    emit()
    emit("La table ne porte pas de colonne `troncon` ni `arret` : l'échelle demandée est")
    emit("traduite dans les colonnes réelles ci-dessous, testées dans cet ordre, la")
    emit("première donnant `nunique` = 1 dans tous les groupes étant retenue. Un NaN")
    emit("compte comme une modalité à part entière (un groupe mêlant NaN et valeur")
    emit("observée n'est pas constant).")
    emit()
    emit("| Rang | Échelle demandée | Colonnes réelles de la table | Nombre de groupes | Colonnes classées |")
    emit("|---|---|---|---|---|")
    for rang, (nom, _cols) in enumerate(ECHELLES, start=1):
        n_cls = int((dico["grain_cle_reelle"] == CLE_REELLE[nom]).sum())
        emit(f"| {rang} | {LIBELLE_ECHELLE[nom]} | `{CLE_REELLE[nom]}` | "
             f"{mil(n_groupes[nom])} | {n_cls} |")
    n_obs = int((dico["grain_variation"] == "par observation").sum())
    emit(f"| — | par observation (repli) | — | {mil(n_lignes)} | {n_obs} |")
    emit()
    emit("`(arret, millesime)` est testée en deux variantes successives — gare de départ")
    emit("puis gare d'arrivée, chacune croisée avec `id_statpop_reference_year` — pour")
    emit("couvrir les deux moitiés symétriques du bloc `spatial_gare_*`. La variante")
    emit("effectivement retenue est reportée colonne par colonne dans `grain_cle_reelle`.")
    emit()

    emit("### 5.1 Deux observations issues du calcul du grain")
    emit()
    emit("**(a) Colonnes topologiques classées `(troncon, date)`.** L'échelle demandée ne")
    emit("comporte pas de marche `(troncon, annee_horaire)`. Une clé de diagnostic")
    emit(f"`(id_gare_depart, id_gare_arrivee, horaire_annee_horaire)` ({mil(n_groupes_diag)} "
         "groupes),")
    emit("hors échelle, montre que les colonnes suivantes, classées `(troncon, date)`, sont")
    emit("en réalité constantes par tronçon **et par année horaire** — leur grain effectif")
    emit("est donc annuel, pas journalier :")
    emit()
    for c in cible_diag:
        emit(f"- `{c}` — tronçons dont la valeur est révisée d'une année à l'autre : "
             + " ; ".join(revisions_diag[c]))
    if not cible_diag:
        emit("- aucune")
    emit()
    emit("**(b) `spatial_denivele_troncon_m` — valeurs manquantes sur H22.** ADR-057")
    emit("documentait « 0 NaN » sur la génération de l'époque (205 colonnes). Sous")
    emit(f"`{HASH_ATTENDU}`, la colonne compte {mil(n_nan_deniv)} manquants, tous sur")
    emit(f"{'/'.join(annees_deniv_nan)} ({nan_par_colonne[DENIV]['h22_h24']:.4f} % de "
         f"H22-H24, {nan_par_colonne[DENIV]['h25']:.4f} % de H25), et tous portés par les")
    emit(f"tronçons {', '.join('`' + a + '→' + b + '`' for a, b in troncons_deniv_nan)} —")
    emit("c'est-à-dire les tronçons de Gilamont, gare fermée après H22.")
    emit()
    emit("Ce décompte est exactement celui des observations écartées de l'entraînement par")
    emit(f"le Split C (ADR-065) : {mil(n_train)} − {mil(n_train_modele)} = "
         f"{mil(n_train - n_train_modele)}, à comparer à {mil(n_nan_deniv)} manquants "
         f"→ **{tick(n_train - n_train_modele == n_nan_deniv)}**")
    emit("(`n_train` lu dans `models/enrichi_seg/enrichi_seg_metadata.json`). Aucune des")
    emit("lignes concernées n'entre donc dans le modèle gelé ; l'écart avec ADR-057 est un")
    emit("écart de génération de dataset, sans effet sur l'entraînement.")
    emit()

    emit("## 6. Livrables")
    emit()
    emit("| Fichier | Contenu |")
    emit("|---|---|")
    emit(f"| `{OUT_CSV.relative_to(ROOT)}` | Dictionnaire, {len(dico)} lignes × {len(dico.columns)} colonnes, `definition` vide |")
    emit(f"| `{OUT_XLSX.relative_to(ROOT)}` | Même contenu au format tableur |")
    emit(f"| `{OUT_MD.relative_to(ROOT)}` | Le présent rapport |")
    emit(f"| `{Path(__file__).relative_to(ROOT)}` | Script de génération, réexécutable en une commande |")
    emit()

    if echecs:
        emit("## 7. ÉCARTS DÉTECTÉS")
        emit()
        for e in echecs:
            emit(f"- {e}")
        emit()
    else:
        emit("## 7. Écarts détectés")
        emit()
        emit("Aucun. Toutes les assertions bloquantes passent ; les tableaux 9 et 13 sont")
        emit("reproduits colonne par colonne depuis les artefacts gelés.")
        emit()

    OUT_MD.write_text("\n".join(lignes_rapport) + "\n", encoding="utf-8")

    if echecs:
        stop(f"{len(echecs)} assertion(s) en échec — voir {OUT_MD}")


if __name__ == "__main__":
    main()
