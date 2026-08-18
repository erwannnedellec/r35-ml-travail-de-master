#!/usr/bin/env python3
"""Annexe 19 — matrice de correspondance candidates qualitatives × colonnes canoniques.

Objet
-----
Vérifier et enrichir le mapping de JUGEMENT fourni en entrée
(`mapping_candidates_colonnes.csv`, version v2 à 31 candidates), qui relie les
variables candidates issues de la phase qualitative (annexe 9 du mémoire) aux
colonnes de la table canonique `ml_dataset.parquet` (empreinte `ba493568`).

Le mapping n'est PAS produit ni corrigé par ce script : il est lu tel quel.
  A. contrôle d'intégrité (noms existants, volumétrie, répartitions),
  B. enrichissement par des grandeurs lues dans les artefacts gelés,
  C. lecture inverse des colonnes non citées, classées en quatre catégories,
  D. parts de masse de contribution, par somme directe sur colonnes dédoublonnées.

Tout écart aux répartitions et aux contrôles attendus est RAPPORTÉ, jamais corrigé.

Évolutions de la version v2 du mapping
--------------------------------------
- 31 candidates au lieu de 30 : `F_OPS.groupes` (thème `08_SOCIAL.Groupe`) porte
  désormais les 8 colonnes `resa_*`, auparavant orphelines.
- Six statuts de triangulation révisés par application de la règle du codebook
  au niveau du construit.
- Colonne `code_thematique` ajoutée en entrée.
- La notion de « colonne écartée par la définition de sa candidate » est
  SUPPRIMÉE : les mentions « Exclure » du codebook sont des intentions de
  conception révisées en préparation, non des règles opposables. Ni la constante
  d'exclusions, ni la colonne correspondante, ni la catégorie « résidu » de la
  version précédente ne sont reprises.

Sources lues (toutes en lecture seule)
--------------------------------------
  data/processed/ml_dataset.parquet                     schéma seul (209 noms)
  models/enrichi_seg/enrichi_seg_bas_ba493568.json       les 158 feature_names
  outputs/confirmation/c08_shap_ranks_{bas,haut}.csv     mean|SHAP| et rangs
  docs/memoire/tableaux/section_4_4_3/
      dictionnaire_colonnes_canonique.csv                taux de manquants, statut

Sorties
-------
  docs/memoire/tableaux/annexe_22/matrice_correspondance_annexe_19.csv
  docs/memoire/tableaux/annexe_22/matrice_correspondance_annexe_19.xlsx
  docs/memoire/verifs/annexe_22/verif_matrice_correspondance.md

Exécution (une commande, déterministe — aucun horodatage dans les sorties) :

    venv/bin/python docs/memoire/verifs/annexe_22/make_matrice_correspondance.py
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
TABLEAUX = ROOT / "docs" / "memoire" / "tableaux" / "annexe_22"

CANON = ROOT / "data" / "processed" / "ml_dataset.parquet"
MODEL_BAS = ROOT / "models" / "enrichi_seg" / "enrichi_seg_bas_ba493568.json"
SHAP_BAS = ROOT / "outputs" / "confirmation" / "c08_shap_ranks_bas.csv"
SHAP_HAUT = ROOT / "outputs" / "confirmation" / "c08_shap_ranks_haut.csv"
DICO = (ROOT / "docs" / "memoire" / "tableaux" / "section_4_4_3"
        / "dictionnaire_colonnes_canonique.csv")

MAPPING = TABLEAUX / "mapping_candidates_colonnes.csv"
OUT_CSV = TABLEAUX / "matrice_correspondance_annexe_19.csv"
OUT_XLSX = TABLEAUX / "matrice_correspondance_annexe_19.xlsx"
OUT_MD = DOSSIER / "verif_matrice_correspondance.md"

HASH_ATTENDU = "ba493568"
N_COLONNES_CANON = 209
N_FEATURES = 158
N_CANDIDATES_ATTENDU = 31
N_ORPHELINES_ATTENDU = 57

COLONNES_ENTREE = ["candidate", "code_thematique", "statut_triangulation",
                   "statut_couverture", "colonnes_cibles", "justification",
                   "section_de_reference"]

# Répartitions annoncées par le manuscrit (contrôle, jamais appliqué en correction).
REPARTITION_COUVERTURE = {
    "Couverte directement": 20,
    "Couverte avec transformation": 5,
    "Couverte par le grain": 2,
    "Exclue par conception": 2,
    "Non couverte": 2,
}
REPARTITION_TRIANGULATION = {
    "Confirmée": 15,
    "Émergente": 9,
    "Littérature": 7,
}

# Contrôle attendu de la lecture inverse : 57 orphelines, dont 8 seulement
# retenues dans les 158. Jamais appliqué en correction, tout écart est rapporté.
ORPHELINES_RETENUES_ATTENDUES = [
    "spatial_gare_depart_hpi_ha_classe_1",
    "spatial_gare_depart_hpi_ha_classe_2",
    "spatial_gare_depart_part_hpi_non_plausible",
    "spatial_gare_arrivee_hpi_ha_classe_1",
    "spatial_gare_arrivee_part_hpi_non_plausible",
    "event_is_covid_restrictions",
    "event_covid_phase",
    "base_duree_troncon_minutes",
]

# --------------------------------------------------------------------------- #
# Classement des colonnes orphelines — règles ordonnées, première touche gagne
# --------------------------------------------------------------------------- #
# Les quatre catégories sont celles fixées par la section 4.4.5. La quatrième est
# le reliquat, c'est-à-dire ce qu'aucune des trois premières ne capte. Chaque
# orpheline mémorise la règle qui l'a captée, pour audit.

# Suffixes des indicateurs de qualité de la source STATPOP, énumérés plutôt que
# décrits par motif. `part_hpi_non_plausible` y figure : son suffixe ne commence
# pas par `hpi_` mais il s'agit bien d'un indicateur de qualité HPI, et le
# contrôle attendu de la section 4.4.5 le compte parmi eux. Ce point de lecture
# est signalé dans le rapport.
SUFFIXES_QUALITE_STATPOP = (
    "hpi_classe_max", "hpi_ha_classe_1", "hpi_ha_classe_2", "hpi_ha_manquante",
    "hpi_ha_autre", "part_hpi_non_plausible", "flag_qualite_faible",
)

_TECHNIQUES_NOMMEES = {
    "base_date", "base_sens", "base_depart_datetime", "base_arrivee_datetime",
    "base_offre_1ere_classe", "base_offre_2eme_classe", "base_offre_total",
    "spatial_segment",
}


def _suffixe_gare(nom: str) -> str:
    """Segment du nom situé après `spatial_gare_{depart|arrivee}_`, sinon vide."""
    if not nom.startswith(("spatial_gare_depart_", "spatial_gare_arrivee_")):
        return ""
    return nom.split("_", 3)[3] if nom.count("_") >= 3 else ""


def _est_technique(nom: str) -> bool:
    return (
        nom.startswith(("id_", "target_", "horaire_"))
        or nom in _TECHNIQUES_NOMMEES
        or nom.endswith(("_source_depart", "_source_arrivee"))
    )


CATEGORIES: list[tuple[int, str, callable]] = [
    (1, "proportions tarifaires et variables d'emplois",
     lambda c: c.startswith("simba_part_") or (
         c.startswith("spatial_gare_") and "_emplois_500m_" in c)),
    (2, "indicateurs de qualité de la source STATPOP",
     lambda c: _suffixe_gare(c) in SUFFIXES_QUALITE_STATPOP),
    (3, "identifiants, cibles et colonnes techniques", _est_technique),
    (4, "reliquat", lambda c: True),
]

EPOQUE_FIXE = dt.datetime(1980, 1, 1, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def sha256_8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def stop(msg: str) -> None:
    print(f"\n*** STOP — {msg}", file=sys.stderr)
    sys.exit(1)


def mil(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def decoupe(cellule: str) -> list[str]:
    """Découpe un champ colonnes_cibles en noms distincts, ordre d'apparition."""
    vus: list[str] = []
    for brut in str(cellule).split(";"):
        nom = brut.strip()
        if nom and nom not in vus:
            vus.append(nom)
    return vus


def ecrit_xlsx_deterministe(df: pd.DataFrame, chemin: Path, feuille: str) -> None:
    """Écrit un .xlsx byte-reproductible (aucun horodatage d'exécution)."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=feuille, index=False)
        props = xl.book.properties
        props.created = EPOQUE_FIXE
        props.modified = EPOQUE_FIXE
        props.creator = "make_matrice_correspondance.py"
        props.lastModifiedBy = "make_matrice_correspondance.py"

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


# --------------------------------------------------------------------------- #
# Programme
# --------------------------------------------------------------------------- #
def main() -> None:
    lignes: list[str] = []

    def emit(s: str = "") -> None:
        lignes.append(s)

    def tick(b: bool) -> str:
        return "OK" if b else "ÉCART"

    # --- Préambule --------------------------------------------------------- #
    for p in (CANON, MODEL_BAS, SHAP_BAS, SHAP_HAUT, DICO, MAPPING):
        if not p.exists():
            stop(f"fichier requis absent : {p}")
    h_canon = sha256_8(CANON)
    if h_canon != HASH_ATTENDU:
        stop(f"empreinte du dataset non conforme : lue {h_canon!r}, "
             f"attendue {HASH_ATTENDU!r}. Aucune sortie n'est produite.")

    # --- Lecture des artefacts --------------------------------------------- #
    import pyarrow.parquet as pq
    import xgboost as xgb

    cols_canon = list(pq.ParquetFile(CANON).schema_arrow.names)
    if len(cols_canon) != N_COLONNES_CANON:
        stop(f"{len(cols_canon)} colonnes lues, attendu {N_COLONNES_CANON}")
    set_canon = set(cols_canon)

    booster = xgb.Booster()
    booster.load_model(str(MODEL_BAS))
    features = list(booster.feature_names or [])
    if len(features) != N_FEATURES:
        stop(f"{len(features)} features dans le booster, attendu {N_FEATURES}")
    set_features = set(features)

    shap, masse = {}, {}
    for seg, chemin in (("bas", SHAP_BAS), ("haut", SHAP_HAUT)):
        t = pd.read_csv(chemin)
        if set(t["feature"]) != set_features:
            stop(f"c08_shap_ranks_{seg}.csv ne couvre pas exactement les 158 features")
        shap[seg] = t.set_index("feature")
        masse[seg] = float(t["mean_abs_shap"].sum())

    dico = pd.read_csv(DICO, keep_default_na=False, dtype=str).set_index("nom")
    if set(dico.index) != set_canon:
        stop("le dictionnaire §4.4.3 ne couvre pas exactement les 209 colonnes")

    mapping = pd.read_csv(MAPPING, keep_default_na=False, dtype=str)
    absentes = [c for c in COLONNES_ENTREE if c not in mapping.columns]
    if absentes:
        stop(f"colonnes absentes du mapping d'entrée : {absentes}")

    # ----------------------------------------------------------------------- #
    # A. Vérifications d'intégrité
    # ----------------------------------------------------------------------- #
    citees_par_candidate = {r["candidate"]: decoupe(r["colonnes_cibles"])
                            for _, r in mapping.iterrows()}

    # A1 — tout nom cité doit exister (BLOQUANT)
    inconnues = [(cand, n) for cand, noms in citees_par_candidate.items()
                 for n in noms if n not in set_canon]
    if inconnues:
        detail = "\n".join(f"      {c} -> {n}" for c, n in inconnues)
        stop(f"{len(inconnues)} nom(s) de colonne inconnu(s) de la table canonique :\n"
             f"{detail}\n    Aucune sortie n'est produite.")

    # A2 — volumétrie et unicité des étiquettes (BLOQUANT)
    if len(mapping) != N_CANDIDATES_ATTENDU:
        stop(f"{len(mapping)} lignes dans le mapping, attendu {N_CANDIDATES_ATTENDU}")
    doublons = [c for c, n in Counter(mapping["candidate"]).items() if n > 1]
    if doublons:
        stop(f"étiquettes de candidate dupliquées : {doublons}")

    # A2 bis — intégrité d'encodage (un CSV UTF-8 relu en Latin-1 laisse des « Ã… »)
    _MOJIBAKE = re.compile(r"Ã.|Â.|�")
    mojibake = [(r["candidate"], col, str(r[col])[:60])
                for _, r in mapping.iterrows() for col in COLONNES_ENTREE
                if _MOJIBAKE.search(str(r[col]))]

    # A3 / A4 — répartitions (RAPPORTÉ, jamais corrigé)
    obs_couv = Counter(mapping["statut_couverture"])
    obs_tri = Counter(mapping["statut_triangulation"])
    ecarts_couv = {k for k in set(REPARTITION_COUVERTURE) | set(obs_couv)
                   if REPARTITION_COUVERTURE.get(k, 0) != obs_couv.get(k, 0)}
    ecarts_tri = {k for k in set(REPARTITION_TRIANGULATION) | set(obs_tri)
                  if REPARTITION_TRIANGULATION.get(k, 0) != obs_tri.get(k, 0)}

    # ----------------------------------------------------------------------- #
    # B. Enrichissement
    # ----------------------------------------------------------------------- #
    enrichi = mapping.copy()
    cols_ajout: dict[str, list] = {k: [] for k in (
        "n_colonnes_table", "n_colonnes_modele", "survie",
        "contribution_bas", "contribution_bas_pct_masse_segment",
        "contribution_haut", "contribution_haut_pct_masse_segment",
        "nan_max_h22_h24", "nan_max_h25")}

    for _, r in mapping.iterrows():
        noms = citees_par_candidate[r["candidate"]]
        dans_modele = [n for n in noms if n in set_features]

        cols_ajout["n_colonnes_table"].append(len(noms))
        cols_ajout["n_colonnes_modele"].append(len(dans_modele))
        if not noms:
            cols_ajout["survie"].append("")
        elif len(dans_modele) == len(noms):
            cols_ajout["survie"].append("entière")
        elif dans_modele:
            cols_ajout["survie"].append("partielle")
        else:
            cols_ajout["survie"].append("nulle")

        for seg in ("bas", "haut"):
            if dans_modele:
                s = float(shap[seg].loc[dans_modele, "mean_abs_shap"].sum())
                cols_ajout[f"contribution_{seg}"].append(round(s, 6))
                cols_ajout[f"contribution_{seg}_pct_masse_segment"].append(
                    round(100.0 * s / masse[seg], 4))
            else:
                cols_ajout[f"contribution_{seg}"].append("")
                cols_ajout[f"contribution_{seg}_pct_masse_segment"].append("")

        if noms:
            cols_ajout["nan_max_h22_h24"].append(round(max(
                float(dico.loc[n, "taux_nan_h22_h24_pct"]) for n in noms), 4))
            cols_ajout["nan_max_h25"].append(round(max(
                float(dico.loc[n, "taux_nan_h25_pct"]) for n in noms), 4))
        else:
            cols_ajout["nan_max_h22_h24"].append("")
            cols_ajout["nan_max_h25"].append("")

    for k, v in cols_ajout.items():
        enrichi[k] = v

    # ----------------------------------------------------------------------- #
    # C. Lecture inverse
    # ----------------------------------------------------------------------- #
    citees = {n for noms in citees_par_candidate.values() for n in noms}
    orphelines = [c for c in cols_canon if c not in citees]

    classement: list[dict] = []
    for c in orphelines:
        for num, libelle, regle in CATEGORIES:
            if regle(c):
                classement.append({
                    "colonne": c, "famille": dico.loc[c, "famille"],
                    "categorie": num, "categorie_libelle": libelle,
                    "statut_selection": dico.loc[c, "statut_selection"],
                    "dans_le_modele": c in set_features})
                break
    classement_df = pd.DataFrame(classement)

    orph_retenues = [d["colonne"] for d in classement if d["dans_le_modele"]]
    controle_retenues = sorted(orph_retenues) == sorted(ORPHELINES_RETENUES_ATTENDUES)
    controle_nombre = len(orphelines) == N_ORPHELINES_ATTENDU

    # ----------------------------------------------------------------------- #
    # D. Parts de masse, somme directe sur colonnes dédoublonnées
    # ----------------------------------------------------------------------- #
    parts: dict[str, dict] = {}
    for seg in ("bas", "haut"):
        col_shap = shap[seg]["mean_abs_shap"]
        c_in = sorted(citees & set_features)
        o_in = sorted(set(orphelines) & set_features)
        s_c = float(col_shap.loc[c_in].sum()) if c_in else 0.0
        s_o = float(col_shap.loc[o_in].sum()) if o_in else 0.0
        par_cat = {}
        for num, libelle, _ in CATEGORIES:
            membres = [d["colonne"] for d in classement
                       if d["categorie"] == num and d["dans_le_modele"]]
            s = float(col_shap.loc[membres].sum()) if membres else 0.0
            par_cat[num] = {"libelle": libelle, "n_total": sum(
                1 for d in classement if d["categorie"] == num),
                "n_dans_modele": len(membres), "somme": s,
                "pct": 100.0 * s / masse[seg]}
        parts[seg] = {
            "masse": masse[seg],
            "n_citees_modele": len(c_in), "somme_citees": s_c,
            "pct_citees": 100.0 * s_c / masse[seg],
            "n_orphelines_modele": len(o_in), "somme_orphelines": s_o,
            "pct_orphelines": 100.0 * s_o / masse[seg],
            "par_categorie": par_cat,
            "boucle": abs((s_c + s_o) / masse[seg] - 1.0) < 1e-9,
        }

    # ----------------------------------------------------------------------- #
    # Écriture des livrables
    # ----------------------------------------------------------------------- #
    TABLEAUX.mkdir(parents=True, exist_ok=True)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    enrichi.to_csv(OUT_CSV, index=False, encoding="utf-8")
    ecrit_xlsx_deterministe(enrichi, OUT_XLSX, "matrice")

    # ----------------------------------------------------------------------- #
    # Rapport
    # ----------------------------------------------------------------------- #
    emit("# Vérification de la matrice de correspondance — annexe 19")
    emit()
    emit("Mapping candidates qualitatives (annexe 9) × colonnes de la table "
         "canonique, version **v2 à 31 candidates**. Rapport produit en lecture "
         "seule par `docs/memoire/verifs/annexe_22/make_matrice_correspondance.py`.")
    emit()
    emit("Le mapping est un jugement fourni en entrée. Ce rapport le contrôle et "
         "l'enrichit. Il ne le produit pas et ne le corrige jamais : tout écart "
         "aux répartitions et aux contrôles annoncés est signalé tel quel.")
    emit()

    emit("## 1. Sources et empreintes")
    emit()
    emit("| Rôle | Chemin | Empreinte SHA256[:8] |")
    emit("|---|---|---|")
    emit(f"| Table canonique (schéma seul) | `data/processed/ml_dataset.parquet` | `{h_canon}` |")
    emit(f"| Mapping de jugement v2 (entrée) | `{MAPPING.relative_to(ROOT)}` | `{sha256_8(MAPPING)}` |")
    emit(f"| Modèle gelé BAS (les 158 features) | `{MODEL_BAS.relative_to(ROOT)}` | `{sha256_8(MODEL_BAS)}` |")
    emit(f"| Rangs SHAP BAS | `{SHAP_BAS.relative_to(ROOT)}` | `{sha256_8(SHAP_BAS)}` |")
    emit(f"| Rangs SHAP HAUT | `{SHAP_HAUT.relative_to(ROOT)}` | `{sha256_8(SHAP_HAUT)}` |")
    emit(f"| Dictionnaire §4.4.3 | `{DICO.relative_to(ROOT)}` | `{sha256_8(DICO)}` |")
    emit(f"| Matrice produite | `{OUT_CSV.relative_to(ROOT)}` | `{sha256_8(OUT_CSV)}` |")
    emit()
    emit(f"Masse totale des contributions : BAS {masse['bas']:.6f}, "
         f"HAUT {masse['haut']:.6f} (somme des mean|SHAP| sur les 158 features).")
    emit()
    emit("**Évolutions de la v2 par rapport à la version précédente.** Une "
         "candidate s'ajoute, `F_OPS.groupes` (thème `08_SOCIAL.Groupe`), qui "
         "porte les 8 colonnes `resa_*` auparavant orphelines. Six statuts de "
         "triangulation sont révisés par application de la règle du codebook au "
         "niveau du construit. La colonne `code_thematique` est ajoutée en "
         "entrée. La notion de colonne écartée par la définition de sa candidate "
         "est supprimée : ni la constante d'exclusions, ni la colonne "
         "correspondante, ni la catégorie « résidu » de la version précédente ne "
         "sont reprises.")
    emit()

    emit("## 2. Vérifications d'intégrité")
    emit()
    emit("| Contrôle | Attendu | Lu | Verdict | Régime |")
    emit("|---|---|---|---|---|")
    emit(f"| Empreinte de la table canonique | `{HASH_ATTENDU}` | `{h_canon}` | "
         f"{tick(True)} | bloquant |")
    emit(f"| Noms de colonnes cités et existants | tous | {len(citees)}/{len(citees)} | "
         f"{tick(True)} | bloquant |")
    emit(f"| Nombre de candidates | {N_CANDIDATES_ATTENDU} | {len(mapping)} | "
         f"{tick(True)} | bloquant |")
    emit(f"| Étiquettes de candidate distinctes | {len(mapping)} | "
         f"{mapping['candidate'].nunique()} | {tick(True)} | bloquant |")
    emit(f"| Répartition par statut_couverture | voir 2.1 | — | "
         f"{tick(not ecarts_couv)} | rapporté |")
    emit(f"| Répartition par statut_triangulation | voir 2.2 | — | "
         f"{tick(not ecarts_tri)} | rapporté |")
    emit(f"| Intégrité d'encodage | aucun champ abîmé | {len(mojibake)} | "
         f"{tick(not mojibake)} | rapporté |")
    emit()

    emit("### 2.1 Répartition par statut_couverture")
    emit()
    emit("| Statut | Annoncé | Lu | Verdict |")
    emit("|---|---|---|---|")
    for k in sorted(set(REPARTITION_COUVERTURE) | set(obs_couv)):
        att, lu = REPARTITION_COUVERTURE.get(k, 0), obs_couv.get(k, 0)
        emit(f"| {k} | {att} | {lu} | {tick(att == lu)} |")
    emit(f"| **Total** | **{sum(REPARTITION_COUVERTURE.values())}** | "
         f"**{sum(obs_couv.values())}** | **{tick(not ecarts_couv)}** |")
    emit()

    emit("### 2.2 Répartition par statut_triangulation")
    emit()
    emit("| Statut | Annoncé | Lu | Verdict |")
    emit("|---|---|---|---|")
    for k in sorted(set(REPARTITION_TRIANGULATION) | set(obs_tri)):
        att, lu = REPARTITION_TRIANGULATION.get(k, 0), obs_tri.get(k, 0)
        emit(f"| {k} | {att} | {lu} | {tick(att == lu)} |")
    emit(f"| **Total** | **{sum(REPARTITION_TRIANGULATION.values())}** | "
         f"**{sum(obs_tri.values())}** | **{tick(not ecarts_tri)}** |")
    emit()
    if mojibake:
        emit("Champs porteurs de séquences d'encodage abîmées :")
        emit()
        emit("| Candidate | Champ | Valeur lue |")
        emit("|---|---|---|")
        for cand, col, val in mojibake:
            emit(f"| `{cand}` | `{col}` | `{val}` |")
        emit()

    emit("### 2.3 Codebook des candidates")
    emit()
    emit("**Aucun codebook de candidates n'est persisté au dépôt.** La colonne "
         "`code_thematique` ajoutée en v2 renvoie aux thèmes du codebook "
         "qualitatif, mais ce codebook n'existe pas sous forme de fichier dans le "
         "dépôt. Les étiquettes de `candidate` comme les codes thématiques sont "
         "donc pris tels quels depuis le mapping, sans confrontation possible à "
         "une source interne, et leur exactitude relève du manuscrit. Aucune "
         "source n'est inventée pour combler cette absence.")
    emit()
    codes = Counter(c for c in mapping["code_thematique"] if c and c != "—")
    sans_code = int(sum(1 for c in mapping["code_thematique"] if not c or c == "—"))
    emit(f"{len(codes)} code(s) thématique(s) distinct(s) sur "
         f"{len(mapping) - sans_code} candidate(s) rattachée(s), "
         f"{sans_code} candidate(s) sans code.")
    emit()
    emit("| Code thématique | Candidates |")
    emit("|---|---|")
    for code, n in sorted(codes.items()):
        membres = sorted(mapping.loc[mapping["code_thematique"] == code, "candidate"])
        emit(f"| `{code}` | {n} — {', '.join('`' + m + '`' for m in membres)} |")
    emit()

    emit("### 2.4 Recouvrement volontaire")
    emit()
    multi: dict[str, list[str]] = {}
    for cand, noms in citees_par_candidate.items():
        for n in noms:
            multi.setdefault(n, []).append(cand)
    partagees = {n: c for n, c in multi.items() if len(c) > 1}
    emit(f"{len(partagees)} colonne(s) citée(s) par plus d'une candidate. Le "
         "recouvrement entre `F_SOL.pop_residente` et `F_SOL.densite_res` est "
         "voulu par le manuscrit, la seconde étant couverte par le construit et "
         "non par la forme. Il n'est donc pas traité comme une anomalie.")
    emit()
    if partagees:
        emit("| Colonne | Candidates |")
        emit("|---|---|")
        for n, c in sorted(partagees.items()):
            emit(f"| `{n}` | {', '.join(sorted(c))} |")
        emit()

    emit("## 3. Enrichissement")
    emit()
    emit("Une colonne par information, toutes lues dans les artefacts gelés sans "
         "recalcul. La consigne nomme `contribution_bas` et `contribution_haut` "
         "en leur demandant la somme et sa part : chaque segment porte donc deux "
         "colonnes, la seconde suffixée `_pct_masse_segment`.")
    emit()
    emit("| Colonne ajoutée | Contenu | Source |")
    emit("|---|---|---|")
    emit("| `n_colonnes_table` | Nombre de colonnes distinctes citées | mapping |")
    emit("| `n_colonnes_modele` | Combien figurent dans les 158 features | "
         "`feature_names` du booster gelé |")
    emit("| `survie` | entière, partielle, nulle, ou vide si aucune colonne citée "
         "| dérivé des deux précédentes |")
    emit("| `contribution_bas` | Somme des mean\\|SHAP\\| des colonnes citées "
         "présentes dans le modèle | `c08_shap_ranks_bas.csv` |")
    emit("| `contribution_bas_pct_masse_segment` | Part de cette somme dans la "
         "masse du segment | idem |")
    emit("| `contribution_haut` | Idem sur HAUT | `c08_shap_ranks_haut.csv` |")
    emit("| `contribution_haut_pct_masse_segment` | Idem | idem |")
    emit("| `nan_max_h22_h24` | Taux de manquants le plus élevé parmi les "
         "colonnes citées | dictionnaire §4.4.3 |")
    emit("| `nan_max_h25` | Idem sur H25 | dictionnaire §4.4.3 |")
    emit()

    emit("### 3.1 Synthèse par statut de couverture")
    emit()
    emit("| Statut de couverture | Candidates | Colonnes citées | dont dans les 158 | "
         "Survie entière / partielle / nulle |")
    emit("|---|---|---|---|---|")
    for statut in sorted(obs_couv):
        sous = enrichi[enrichi["statut_couverture"] == statut]
        sv = Counter(sous["survie"])
        emit(f"| {statut} | {len(sous)} | {int(sous['n_colonnes_table'].sum())} | "
             f"{int(sous['n_colonnes_modele'].sum())} | "
             f"{sv.get('entière', 0)} / {sv.get('partielle', 0)} / {sv.get('nulle', 0)} |")
    emit()
    non_entiere = enrichi[enrichi["survie"].isin(["partielle", "nulle"])]
    if len(non_entiere):
        emit("Candidates dont la survie n'est pas entière :")
        emit()
        emit("| Candidate | Statut de couverture | Survie | Colonnes citées hors des 158 |")
        emit("|---|---|---|---|")
        for _, r in non_entiere.iterrows():
            hors = [n for n in citees_par_candidate[r["candidate"]]
                    if n not in set_features]
            emit(f"| `{r['candidate']}` | {r['statut_couverture']} | {r['survie']} | "
                 + ", ".join("`" + n + "`" for n in hors) + " |")
        emit()

    emit("### 3.2 Synthèse par statut de triangulation")
    emit()
    emit("| Statut de triangulation | Candidates | Colonnes citées | dont dans les 158 | "
         "Contribution BAS | Contribution HAUT |")
    emit("|---|---|---|---|---|---|")
    for statut in sorted(obs_tri):
        sous = enrichi[enrichi["statut_triangulation"] == statut]
        noms = sorted({n for c in sous["candidate"] for n in citees_par_candidate[c]})
        dans = [n for n in noms if n in set_features]
        pb = 100.0 * float(shap["bas"].loc[dans, "mean_abs_shap"].sum()) / masse["bas"] if dans else 0.0
        ph = 100.0 * float(shap["haut"].loc[dans, "mean_abs_shap"].sum()) / masse["haut"] if dans else 0.0
        emit(f"| {statut} | {len(sous)} | {len(noms)} | {len(dans)} | "
             f"{pb:.2f} % | {ph:.2f} % |")
    emit()
    emit("Les colonnes citées sont dédoublonnées à l'intérieur de chaque statut, "
         "de sorte que le recouvrement volontaire ne soit pas compté deux fois. "
         "La somme des parts entre statuts peut en revanche dépasser le total du "
         "point 5 si une même colonne est citée par des candidates de statuts "
         "différents.")
    emit()

    emit("## 4. Lecture inverse — colonnes citées par aucune candidate")
    emit()
    emit(f"Le mapping cite **{len(citees)}** colonnes distinctes sur "
         f"{len(cols_canon)}. Il en laisse **{len(orphelines)}** non citées. Le "
         f"manuscrit en annonce {N_ORPHELINES_ATTENDU} : "
         f"**{tick(controle_nombre)}**.")
    emit()

    emit("### 4.1 Orphelines par famille et statut de sélection")
    emit()
    emit("| Famille | Orphelines | dont retenues dans les 158 | dont hors modèle |")
    emit("|---|---|---|---|")
    for fam in sorted(classement_df["famille"].unique()):
        sous = classement_df[classement_df["famille"] == fam]
        n_ret = int((sous["statut_selection"] == "retenue").sum())
        emit(f"| `{fam}` | {len(sous)} | {n_ret} | {len(sous) - n_ret} |")
    n_ret_tot = int((classement_df["statut_selection"] == "retenue").sum())
    emit(f"| **Total** | **{len(classement_df)}** | **{n_ret_tot}** | "
         f"**{len(classement_df) - n_ret_tot}** |")
    emit()

    emit("### 4.2 Classement en quatre catégories")
    emit()
    emit("Règles ordonnées, première touche gagne. La quatrième catégorie est le "
         "reliquat, c'est-à-dire ce qu'aucune des trois premières ne capte.")
    emit()
    emit("| Catégorie | Libellé | Colonnes | dont retenues dans les 158 |")
    emit("|---|---|---|---|")
    for num, libelle, _ in CATEGORIES:
        sous = classement_df[classement_df["categorie"] == num]
        emit(f"| {num} | {libelle} | {len(sous)} | "
             f"{int(sous['dans_le_modele'].sum())} |")
    emit(f"| **Total** | — | **{len(classement_df)}** | "
         f"**{len(orph_retenues)}** |")
    emit()
    emit("**Point de lecture sur la catégorie 2.** La consigne la décrit par les "
         "« suffixes `hpi_*` et `flag_qualite_faible` ». Le suffixe "
         "`part_hpi_non_plausible` ne commence pas par `hpi_` mais désigne bien "
         "un indicateur de qualité de la source, et le contrôle attendu le compte "
         "parmi les indicateurs HPI présents dans le modèle. Les sept suffixes "
         "retenus sont donc énumérés explicitement dans le script (constante "
         "`SUFFIXES_QUALITE_STATPOP`) plutôt que décrits par motif.")
    emit()

    emit("### 4.3 Contrôle des orphelines retenues dans le modèle")
    emit()
    emit(f"Le manuscrit attend **8** orphelines retenues : les 5 indicateurs de "
         "qualité HPI présents dans le modèle, `event_is_covid_restrictions`, "
         "`event_covid_phase` et `base_duree_troncon_minutes`.")
    emit()
    emit(f"Obtenu : **{len(orph_retenues)}** orpheline(s) retenue(s). Conformité "
         f"au contrôle : **{tick(controle_retenues)}**.")
    emit()
    emit("| Colonne | Catégorie | Famille | Rang SHAP BAS | Rang SHAP HAUT |")
    emit("|---|---|---|---|---|")
    for d_ in classement:
        if not d_["dans_le_modele"]:
            continue
        c = d_["colonne"]
        emit(f"| `{c}` | {d_['categorie']} | `{d_['famille']}` | "
             f"{int(shap['bas'].loc[c, 'rang'])}/{N_FEATURES} | "
             f"{int(shap['haut'].loc[c, 'rang'])}/{N_FEATURES} |")
    emit()
    if not controle_retenues:
        manq = sorted(set(ORPHELINES_RETENUES_ATTENDUES) - set(orph_retenues))
        surp = sorted(set(orph_retenues) - set(ORPHELINES_RETENUES_ATTENDUES))
        emit("**Écart au contrôle attendu, rapporté sans ajustement.**")
        emit()
        if manq:
            emit("Attendues mais absentes : " + ", ".join("`" + c + "`" for c in manq)
                 + ". Cause pour chacune :")
            emit()
            for c in manq:
                if c in citees:
                    emit(f"- `{c}` : citée par le mapping "
                         f"({', '.join(sorted(multi[c]))}), donc pas orpheline.")
                elif c not in set_features:
                    emit(f"- `{c}` : orpheline mais hors des 158 features.")
                else:
                    emit(f"- `{c}` : cause non identifiée automatiquement.")
            emit()
        if surp:
            emit("Présentes mais non attendues : "
                 + ", ".join("`" + c + "`" for c in surp) + ".")
            emit()

    emit("### 4.4 Détail complet des orphelines")
    emit()
    emit("| Colonne | Famille | Catégorie | Statut de sélection |")
    emit("|---|---|---|---|")
    for d_ in classement:
        emit(f"| `{d_['colonne']}` | `{d_['famille']}` | {d_['categorie']} | "
             f"{d_['statut_selection']} |")
    emit()

    emit("## 5. Parts de masse de contribution")
    emit()
    emit("Somme directe des mean|SHAP| sur les colonnes dédoublonnées, sans "
         "passer par les pourcentages par candidate, qui compteraient deux fois "
         "les colonnes du recouvrement volontaire.")
    emit()
    emit("| Segment | Masse totale | Citées | Part citée | Orphelines | Part orpheline |")
    emit("|---|---|---|---|---|---|")
    for seg in ("bas", "haut"):
        p = parts[seg]
        emit(f"| {seg.upper()} | {p['masse']:.6f} | {p['somme_citees']:.6f} "
             f"({p['n_citees_modele']} f.) | **{p['pct_citees']:.2f} %** | "
             f"{p['somme_orphelines']:.6f} ({p['n_orphelines_modele']} f.) | "
             f"**{p['pct_orphelines']:.2f} %** |")
    emit()
    for seg in ("bas", "haut"):
        p = parts[seg]
        emit(f"Segment {seg.upper()} : {p['n_citees_modele']} + "
             f"{p['n_orphelines_modele']} = "
             f"{p['n_citees_modele'] + p['n_orphelines_modele']} features, "
             f"partition à 100 % : **{tick(p['boucle'])}**.")
    emit()

    emit("### 5.1 Détail de la part orpheline par catégorie")
    emit()
    emit("| Catégorie | Libellé | Colonnes | dont dans les 158 | Part BAS | Part HAUT |")
    emit("|---|---|---|---|---|---|")
    for num, libelle, _ in CATEGORIES:
        b = parts["bas"]["par_categorie"][num]
        h = parts["haut"]["par_categorie"][num]
        emit(f"| {num} | {libelle} | {b['n_total']} | {b['n_dans_modele']} | "
             f"{b['pct']:.4f} % | {h['pct']:.4f} % |")
    emit(f"| **Total** | — | **{len(classement_df)}** | "
         f"**{len(orph_retenues)}** | "
         f"**{parts['bas']['pct_orphelines']:.4f} %** | "
         f"**{parts['haut']['pct_orphelines']:.4f} %** |")
    emit()
    emit("Les catégories 1 et 3 ne portent aucune contribution : aucune de leurs "
         "colonnes ne figure dans les 158 features. La masse orpheline se "
         "concentre donc entièrement sur les catégories 2 et 4.")
    emit()

    emit("## 6. Livrables")
    emit()
    emit("| Fichier | Contenu |")
    emit("|---|---|")
    emit(f"| `{OUT_CSV.relative_to(ROOT)}` | Matrice, {len(enrichi)} lignes × "
         f"{len(enrichi.columns)} colonnes |")
    emit(f"| `{OUT_XLSX.relative_to(ROOT)}` | Même contenu au format tableur |")
    emit(f"| `{OUT_MD.relative_to(ROOT)}` | Le présent rapport |")
    emit(f"| `{Path(__file__).relative_to(ROOT)}` | Script, réexécutable en une commande |")
    emit()

    OUT_MD.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(f"Matrice : {len(enrichi)} candidates × {len(enrichi.columns)} colonnes")
    print(f"  colonnes citées         : {len(citees)} / {len(cols_canon)}")
    print(f"  orphelines              : {len(orphelines)} "
          f"(attendu {N_ORPHELINES_ATTENDU}, {tick(controle_nombre)})")
    print(f"  orphelines retenues     : {len(orph_retenues)} "
          f"(attendu 8, {tick(controle_retenues)})")
    print(f"  répartition couverture      : {tick(not ecarts_couv)}")
    print(f"  répartition triangulation   : {tick(not ecarts_tri)}")
    for seg in ("bas", "haut"):
        p = parts[seg]
        print(f"  part citée {seg:<4} : {p['pct_citees']:6.2f} % | "
              f"orpheline : {p['pct_orphelines']:5.2f} %")


if __name__ == "__main__":
    main()
