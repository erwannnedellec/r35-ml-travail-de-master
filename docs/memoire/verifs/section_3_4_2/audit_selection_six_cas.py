#!/usr/bin/env python3
"""Vérif §3.4.2 — trace d'audit de la sélection des six cas d'entretien (annexe).

Objet
-----
Reconstituer de manière déterministe, depuis les sources du dépôt et sans aucune valeur
saisie à la main, la trace d'audit de la sélection des six cas présentés en séances
décideurs D01/D02 (14.07.2026), puis vérifier qu'elle reproduit exactement les cas
effectivement présentés.

Quatre étapes, dans l'ordre demandé par le protocole de vérification :

  E1. RÈGLES — restitution VERBATIM des règles préenregistrées (aucune reformulation),
      extraites par découpage automatique de leurs fichiers porteurs :
        * `scripts/experiences/selection_cas_entretien_deploiement_ba493568.py`
          (docstring de tête = protocole 2.3 tel qu'implémenté et figé),
        * `docs/adr/ADR-077_configuration_deploiement_c_plancher.md`.
      Date de consignation de chaque bloc = date du plus ancien commit dont le contenu
      versionné contient déjà le bloc mot pour mot (recherche sur `git log --reverse`).
      Les règles ambiguës ou absentes sont SIGNALÉES, jamais inférées ni complétées.

  E2. VIVIER — vérification des empreintes (dataset canonique + modèles couche 1 figés),
      reconstruction de la matrice de confusion H25 au grain course à la configuration de
      déploiement `c ∪ plancher`, puis construction des viviers ordonnés par cellule selon
      la règle de sévérité applicable. Profondeur N par vivier documentée et calculée
      (cf. `profondeur_N`).

  E3. AUDIT — application des règles dans leur ordre préenregistré, avec journalisation
      d'une ligne par candidat examiné (strate, rang, course, date, valeur du critère de
      sévérité, statut, règle d'exclusion citée dans les termes exacts du protocole).

  E4. VÉRIFICATION — confrontation des six cas re-dérivés aux six cas effectivement
      présentés (ordre verrouillé lu dans `docs/entretiens/supports/fiche_intervieweur.md`
      et artefact figé `outputs/entretiens/cas_entretien_deploiement_ba493568.json`),
      plus trois analyses de sensibilité sur les degrés de liberté résiduels identifiés
      en E1. Toute divergence est documentée telle quelle ; aucune règle n'est ajustée
      pour retrouver le résultat attendu.

Discipline
----------
Lecture seule sur toutes les entrées (dataset, modèles, ADR, scripts, artefacts figés).
Le script n'écrit que ses trois livrables. Threads = 1 (déterminisme XGBoost).

Sorties
-------
  docs/memoire/verifs/section_3_4_2/rapport_audit_selection_six_cas.md
  docs/memoire/tableaux/section_3_4_2/table_3_4_2_audit_selection_cas.csv
  docs/memoire/tableaux/section_3_4_2/table_3_4_2_audit_selection_cas.md
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import ast
import hashlib
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision, blocs  # noqa: E402

# ── Sources (lecture seule) ────────────────────────────────────────────────────
SEL_PY = ROOT / "scripts/experiences/selection_cas_entretien_deploiement_ba493568.py"
ADR_077 = ROOT / "docs/adr/ADR-077_configuration_deploiement_c_plancher.md"
FICHE = ROOT / "docs/entretiens/supports/fiche_intervieweur.md"
ARTEFACT = ROOT / "outputs/entretiens/cas_entretien_deploiement_ba493568.json"
CALIB = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"
ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"

# ── Livrables ──────────────────────────────────────────────────────────────────
DIR_VERIF = ROOT / "docs/memoire/verifs/section_3_4_2"
DIR_TAB = ROOT / "docs/memoire/tableaux/section_3_4_2"
RAPPORT = DIR_VERIF / "rapport_audit_selection_six_cas.md"
CSV = DIR_TAB / "table_3_4_2_audit_selection_cas.csv"
TAB_MD = DIR_TAB / "table_3_4_2_audit_selection_cas.md"

SEUIL = decision.SEUIL          # 63 places assises 2e classe (ADR-060), importé
MARGE_RANGS = 2                 # marge de profondeur exigée par le protocole de vérification


# ═══════════════════════════════════════════════════════════════════════════════
# Outils : empreintes, git, extraction verbatim
# ═══════════════════════════════════════════════════════════════════════════════
def sha8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout


_CACHE_SHOW = {}


def git_show(sha: str, rel: str) -> str:
    if (sha, rel) not in _CACHE_SHOW:
        try:
            _CACHE_SHOW[(sha, rel)] = git("show", f"{sha}:{rel}")
        except subprocess.CalledProcessError:
            _CACHE_SHOW[(sha, rel)] = ""
    return _CACHE_SHOW[(sha, rel)]


def commits_de(path: Path):
    """(sha, date) des commits touchant `path`, du plus ancien au plus récent."""
    rel = str(path.relative_to(ROOT))
    out = git("log", "--reverse", "--format=%H %ad", "--date=short", "--", rel).strip()
    return [tuple(l.split(" ", 1)) for l in out.split("\n") if l]


def modifie_non_valide(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    return bool(git("status", "--porcelain", "--", rel).strip())


def date_consignation(path: Path, bloc: str):
    """Date du plus ancien commit dont le contenu versionné contient DÉJÀ `bloc` mot pour
    mot. Renvoie (date, sha) ou (None, None) si le bloc n'existe que dans l'arbre de travail."""
    rel = str(path.relative_to(ROOT))
    norm = "\n".join(l.rstrip() for l in bloc.strip("\n").split("\n"))
    for sha, date in commits_de(path):
        contenu = "\n".join(l.rstrip() for l in git_show(sha, rel).split("\n"))
        if norm in contenu:
            return date, sha[:7]
    return None, None


def _slice(lignes, debut: str, fin, label: str) -> str:
    """Découpe verbatim de `lignes` : de la 1re ligne commençant par `debut` (après strip)
    jusqu'à la ligne précédant la 1re ligne commençant par `fin` (None = fin de liste)."""
    i = next((k for k, l in enumerate(lignes) if l.strip().startswith(debut)), None)
    if i is None:
        raise RuntimeError(f"[E1] ancre introuvable ({label}) : « {debut} »")
    if fin is None:
        j = len(lignes)
    else:
        j = next((k for k in range(i + 1, len(lignes)) if lignes[k].strip().startswith(fin)), None)
        if j is None:
            raise RuntimeError(f"[E1] ancre de fin introuvable ({label}) : « {fin} »")
    return "\n".join(lignes[i:j]).rstrip()


def lignes_source(path: Path, bloc: str):
    """(première, dernière) ligne 1-indexée de `bloc` dans `path` (référence file:lignes)."""
    src = path.read_text().split("\n")
    prem = bloc.split("\n")[0]
    i = next((k for k, l in enumerate(src) if l == prem), None)
    if i is None:
        raise RuntimeError(f"[E1] bloc non localisé dans {path.name} : « {prem[:60]} »")
    return i + 1, i + len(bloc.split("\n"))


# ═══════════════════════════════════════════════════════════════════════════════
# E1 — Restitution VERBATIM des règles préenregistrées
# ═══════════════════════════════════════════════════════════════════════════════
def etape1_regles():
    src_sel = SEL_PY.read_text()
    doc = ast.get_docstring(ast.parse(src_sel), clean=False)
    dl = doc.split("\n")
    sl = src_sel.split("\n")
    adr = ADR_077.read_text().split("\n")

    blocs_ = []

    def ajoute(theme, path, bloc, note=""):
        d, sha = date_consignation(path, bloc)
        a, b = lignes_source(path, bloc)
        blocs_.append({"theme": theme, "source": f"{path.relative_to(ROOT)}:{a}-{b}",
                       "verbatim": bloc, "date_consignation": d, "commit": sha, "note": note})

    # -- protocole 2.3 : docstring de tête du script de sélection (figé) --
    ajoute("Règle évaluée et composition des strates de la matrice de confusion",
           SEL_PY, _slice(dl, "Selection des 6 cas d'entretien", "Tout est RE-DERIVE", "en-tête"))
    ajoute("Chapeau des règles préenregistrées",
           SEL_PY, _slice(dl, "Regles preenregistrees", "- critere primaire", "chapeau"))
    ajoute("Critère primaire de sévérité",
           SEL_PY, _slice(dl, "- critere primaire", "- FN (2)", "critère primaire"))
    ajoute("Règle de sévérité — cellule FN (2 cas) et sous-règle fermée de strate 166+",
           SEL_PY, _slice(dl, "- FN (2)", "- VP (2)", "FN"))
    ajoute("Règle de sévérité — cellule VP (2 cas), sous-règle fermée de strate 166+, "
           "diversité de mécanisme et dérogation de la paire 166+",
           SEL_PY, _slice(dl, "- VP (2)", "- FP (1)", "VP"))
    ajoute("Règle de sévérité — cellule FP (1 cas) et durcissement du départage (b)",
           SEL_PY, _slice(dl, "- FP (1)", "- VN (1)", "FP"))
    ajoute("Règle de sévérité — cellule VN (1 cas)",
           SEL_PY, _slice(dl, "- VN (1)", "- diversite d'ensemble", "VN"))
    ajoute("Diversité d'ensemble",
           SEL_PY, _slice(dl, "- diversite d'ensemble", "- departages", "diversité"))
    ajoute("Règles de départage",
           SEL_PY, _slice(dl, "- departages", "- hierarchie", "départages"))
    ajoute("Hiérarchie des règles",
           SEL_PY, _slice(dl, "- hierarchie", None, "hiérarchie"))
    ajoute("Strate des affluences extrêmes : constante et statut de la limite de 166 voyageurs",
           SEL_PY, _slice(sl, "CAP_RAME = 166", "MD = ROOT", "CAP_RAME"))
    ajoute("Opérationnalisation du cas FP (texte publié dans les pièces d'entretien)",
           SEL_PY, _slice(sl, "OPERATIONNALISATION_FP = (", "ZONE_ORDRE", "opérationnalisation FP"))
    ajoute("Traitement de la paire dédiée à la strate des affluences extrêmes",
           SEL_PY, _slice(sl, '"paire_166plus": {', '"diversite_ensemble"', "paire 166+"))

    # -- ADR-077 : décision de configuration et statut de la limite 166 --
    ajoute("Configuration de déploiement (point de fonctionnement de la matrice de tirage)",
           ADR_077, _slice(adr, "## Décision", "## Chiffres H25", "décision ADR-077"))
    ajoute("Statut de la limite d'exploitabilité de 166 voyageurs",
           ADR_077, _slice(adr, "## Addendum de formulation (2026-07-12",
                           "## Addendum (2026-07-16)", "addendum 166"))
    ajoute("Antériorité des chiffres de la configuration sur la sélection des cas",
           ADR_077, _slice(adr, "- Chiffres H25 de l'union", "## Addendum (2026-07-24)", "antériorité"),
           note="dernière ligne de la section « Conséquences »")

    return blocs_


# ═══════════════════════════════════════════════════════════════════════════════
# E1 (suite) — Formules d'exclusion, citées dans les TERMES EXACTS du protocole
# ═══════════════════════════════════════════════════════════════════════════════
EXCL_DATE = "(a) pas deux memes dates"
EXCL_OCC = "max 2 occurrences d'une course"
EXCL_CELL = "jamais meme cellule"
EXCL_DURCI = "departage (b) DURCI en preference de non-reutilisation de course"
EXCL_SEV = "severite inferieure au retenu"


def controle_verbatim_exclusions():
    """Garantit mécaniquement que chaque motif d'exclusion écrit dans le tableau d'audit
    est un fragment TEXTUEL du protocole préenregistré (aucune reformulation)."""
    src = SEL_PY.read_text()
    doc = ast.get_docstring(ast.parse(src), clean=False)
    ctrl = []
    for motif, ou, texte in [(EXCL_DATE, "docstring", doc), (EXCL_OCC, "docstring", doc),
                             (EXCL_CELL, "docstring", doc), (EXCL_DURCI, "docstring", doc),
                             (EXCL_SEV, "corps du script", src)]:
        if motif not in texte:
            raise RuntimeError(f"[E1] motif non verbatim dans {ou} : « {motif} »")
        ctrl.append({"motif": motif, "present_dans": ou})
    return ctrl


# ═══════════════════════════════════════════════════════════════════════════════
# E2 — Empreintes de la configuration figée
# ═══════════════════════════════════════════════════════════════════════════════
def etape2_empreintes():
    emp = {"dataset": {}, "modeles": [], "generation_416bb90b": {}}

    h_ds = sha8(ML_DATASET)
    emp["dataset"] = {"fichier": str(ML_DATASET.relative_to(ROOT)), "empreinte": h_ds,
                      "attendue": blocs.HASH_CANONIQUE,
                      "conforme": h_ds == blocs.HASH_CANONIQUE,
                      "origine_attendue": "src/couche2/blocs.py::HASH_CANONIQUE (gel v2, ADR-076)"}

    for p, att, seg in [(decision.MODEL_BAS, decision.HASH_MODEL_BAS, "bas"),
                        (decision.MODEL_HAUT, decision.HASH_MODEL_HAUT, "haut")]:
        h = sha8(p)
        emp["modeles"].append({"segment": seg, "fichier": str(p.relative_to(ROOT)),
                               "empreinte": h, "attendue": att, "conforme": h == att})

    # génération 416bb90b : mêmes poids ou non ? (contrôle d'identité binaire)
    md = ROOT / "models/enrichi_seg"
    for seg in ("bas", "haut"):
        v19 = md / f"enrichi_seg_{seg}_416bb90b.json"
        v2 = md / f"enrichi_seg_{seg}_ba493568.json"
        emp["generation_416bb90b"][seg] = {
            "fichier_v19": str(v19.relative_to(ROOT)) if v19.exists() else None,
            "empreinte_v19": sha8(v19) if v19.exists() else None,
            "empreinte_v2": sha8(v2),
            "identiques": (v19.exists() and sha8(v19) == sha8(v2)),
        }
    emp["artefacts_nommes_416bb90b"] = sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / "outputs/couche2").glob("*416bb90b*"))
    return emp


# ═══════════════════════════════════════════════════════════════════════════════
# E2 (suite) — Matrice de confusion H25 et viviers ordonnés
# ═══════════════════════════════════════════════════════════════════════════════
def etape2_matrice():
    """Reconstruit exactement la matrice de tirage : jeu de décision canonique (decision.py),
    seuil c re-calibré sur H24 et confronté à l'artefact de calibration, masque
    `c ∪ plancher`, affectation des quadrants."""
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)          # gardes P3 : 29 222 / 2 072

    calib_re = decision.calibrate(ds)
    tau_re = calib_re["regles_deployables"]["c_haute_precision"]["seuil"]
    tau_js = json.loads(CALIB.read_text())["regles_deployables"]["c_haute_precision"]["seuil"]
    tau_c = tau_js                                            # le script figé lit l'artefact

    h = ds[ds["annee"] == "H25"].copy()
    resa = h["resa2c"].fillna(0)
    h["reco_c"] = h["score"] >= tau_c
    h["reco_pl"] = resa > SEUIL
    h["reco"] = h["reco_c"] | h["reco_pl"]
    h["voie"] = np.where(h["reco_c"] & h["reco_pl"], "les_deux",
                np.where(h["reco_c"], "score", np.where(h["reco_pl"], "plancher", "aucune")))
    h["cell"] = "VN"
    h.loc[h["reco"] & h["label"], "cell"] = "VP"
    h.loc[h["reco"] & ~h["label"], "cell"] = "FP"
    h.loc[~h["reco"] & h["label"], "cell"] = "FN"
    h["marge"] = h["charge_max"] - SEUIL
    h["date_s"] = pd.to_datetime(h["date"]).dt.strftime("%Y-%m-%d")

    vc = h["cell"].value_counts().to_dict()
    matrice = {c: int(vc.get(c, 0)) for c in ("VP", "FP", "FN", "VN")}
    matrice["volume_recommande"] = int(h["cell"].isin(["VP", "FP"]).sum())

    art = json.loads(ARTEFACT.read_text())["preambule"]["matrice_config_H25"]
    return h, tau_c, {
        "gardes": info, "matrice": matrice, "matrice_artefact_fige": art,
        "matrice_conforme": all(matrice[k] == art[k] for k in art),
        "tau_c_artefact": tau_js, "tau_c_recalibre": tau_re,
        "tau_c_ecart": abs(tau_js - tau_re),
    }


# CAP_RAME : lu dans le script figé (jamais ressaisi)
def cap_rame() -> int:
    m = re.search(r"^CAP_RAME = (\d+)", SEL_PY.read_text(), re.M)
    return int(m.group(1))


def _viv(cle, strate, cell, critere, pool, cles, sens):
    return {"cle": cle, "strate": strate, "cellule": cell, "critere": critere,
            "pool": pool.sort_values(cles, ascending=sens), "cles_tri": cles, "sens_tri": sens}


def viviers(h, cap):
    """Viviers ordonnés par cellule selon la règle de sévérité applicable, listés dans l'ordre
    d'application du corps du script figé."""
    fpp = h[(h.cell == "FP") & (h.voie == "score") & (h.charge_max < 40)].copy()
    fpp["over_pred"] = fpp["score"] - fpp["charge_max"]
    v = [
        _viv("VP_166", "VP — strate 166+ captée", "VP",
             "marge = charge réalisée − 63 (décroissante)",
             h[(h.cell == "VP") & (h.charge_max >= cap)], ["marge"], [False]),
        _viv("FN_166", "FN — strate 166+ manquée", "FN", "charge réalisée (décroissante)",
             h[(h.cell == "FN") & (h.charge_max >= cap)], ["charge_max"], [False]),
        _viv("VP_MECA", "VP — diversité de mécanisme (plancher joué)", "VP",
             "marge = charge réalisée − 63 (décroissante)",
             h[(h.cell == "VP") & (~h.reco_c) & (h.reco_pl) & (h.charge_max < cap)],
             ["marge"], [False]),
        _viv("FN_HORS", "FN — hors 166+ (forte intensité)", "FN", "charge réalisée (décroissante)",
             h[(h.cell == "FN") & (h.charge_max < cap)], ["charge_max"], [False]),
        _viv("FP", "FP — écart prédit-réalisé le plus net", "FP",
             "écart prédit-réalisé = score − charge réalisée (décroissant)",
             fpp, ["over_pred"], [False]),
        _viv("VN", "VN — proche seuil sans franchir", "VN",
             "charge réalisée (décroissante) puis score (croissant)",
             h[(h.cell == "VN") & (h.charge_max >= 56) & (h.charge_max <= 63)],
             ["charge_max", "score"], [False, True]),
    ]
    # vivier de repli du VP « diversité de mécanisme » (branche non empruntée si le 1er suffit)
    repli = _viv("VP_REPLI", "VP — diversité de mécanisme (repli : divergence outil-humain)", "VP",
                 "marge = charge réalisée − 63 (décroissante)",
                 h[(h.cell == "VP") & (~h.is_UM) & (h.charge_max < cap)], ["marge"], [False])
    return v, repli


# ═══════════════════════════════════════════════════════════════════════════════
# E3 — Application des règles, journalisée
# ═══════════════════════════════════════════════════════════════════════════════
class Etat:
    """État des départages, réplique stricte du script figé (pris_dates / pris_courses /
    pris_cellules et la double passe de préférence de non-réutilisation)."""

    def __init__(self):
        self.dates, self.courses, self.cellules = set(), {}, set()

    def motif_indispo(self, cand, cell):
        if cand.date in self.dates:
            return EXCL_DATE
        if (cand.numero_train, cell) in self.cellules:
            return EXCL_CELL
        if self.courses.get(cand.numero_train, 0) >= 2:
            return EXCL_OCC
        return None

    def prendre(self, cand, cell):
        self.dates.add(cand.date)
        self.courses[cand.numero_train] = self.courses.get(cand.numero_train, 0) + 1
        self.cellules.add((cand.numero_train, cell))


def choisir(pool, cell, etat, journal=None):
    """Réplique de `choisir` du script figé, instrumentée. `journal` reçoit (rang, cand,
    statut, motif, passe) pour chaque candidat effectivement examiné par l'algorithme."""
    for prefer_unused in (True, False):
        for rang, cand in enumerate(pool.itertuples(), 1):
            if prefer_unused and cand.numero_train in etat.courses:
                if journal is not None:
                    journal.append((rang, cand, "écarté", EXCL_DURCI, 1))
                continue
            motif = etat.motif_indispo(cand, cell)
            if motif is None:
                etat.prendre(cand, cell)
                if journal is not None:
                    journal.append((rang, cand, "retenu", "", 1 if prefer_unused else 2))
                return cand
            if journal is not None:
                journal.append((rang, cand, "écarté", motif, 1 if prefer_unused else 2))
    return None


def profondeur_N(journal, taille_pool):
    """N = (rang le plus profond touché par une règle de départage ou par la sélection)
    + MARGE_RANGS, borné par la taille du vivier. Par construction de la double passe,
    toute exclusion de départage est de rang inférieur ou égal au rang du retenu ; N couvre
    donc tous les candidats écartés par un départage, plus deux rangs de marge."""
    if not journal:
        return min(MARGE_RANGS, taille_pool)
    return min(max(r for r, *_ in journal) + MARGE_RANGS, taille_pool)


def bloc_ex_aequo(viv, rang_pick):
    """Rangs (1-indexés) des candidats partageant EXACTEMENT la clé de tri du candidat retenu.
    Un bloc de taille > 1 signale que l'ordre interne du vivier n'est pas déterminé par le
    critère de sévérité : degré de liberté à instruire."""
    cles = viv["pool"][viv["cles_tri"]].round(6)
    ref = cles.iloc[rang_pick - 1]
    egal = (cles == ref).all(axis=1).values
    return [i + 1 for i, e in enumerate(egal) if e]


def etape3_audit(h, cap):
    """Applique les six règles dans l'ordre préenregistré et produit le tableau d'audit."""
    vivs, repli = viviers(h, cap)
    etat = Etat()
    lignes, picks, meta_N = [], [], []

    for ordre, viv in enumerate(vivs, 1):
        journal = []
        avant = (set(etat.dates), dict(etat.courses), set(etat.cellules))   # état d'entrée
        cell, cle = viv["cellule"], viv["cle"]
        cand = choisir(viv["pool"], cell, etat, journal)
        if cand is None and cle == "VP_MECA":          # branche de repli préenregistrée
            journal = []
            viv = repli
            cand = choisir(viv["pool"], cell, etat, journal)
        if cand is None:
            raise RuntimeError(f"[E3] vivier {cle} épuisé sans sélection possible")
        picks.append((cell, cand, viv["strate"], cle))

        pool, strate, critere, col = viv["pool"], viv["strate"], viv["critere"], viv["cles_tri"][0]
        N = profondeur_N(journal, len(pool))
        rang_pick = next(r for r, c, s, m, p in journal if s == "retenu")

        # ex æquo : le retenu partage-t-il sa clé de tri avec d'autres candidats, et si oui,
        # est-il le seul de son bloc à passer les départages dans l'état d'entrée du vivier ?
        bloc = bloc_ex_aequo(viv, rang_pick)
        etat_entree = Etat()
        etat_entree.dates, etat_entree.courses, etat_entree.cellules = avant
        rows = list(pool.itertuples())
        eligibles = [r for r in bloc
                     if rows[r - 1].numero_train not in etat_entree.courses
                     and etat_entree.motif_indispo(rows[r - 1], cell) is None]
        meta_N.append({"vivier": cle, "strate": strate, "taille_vivier": len(pool),
                       "rang_du_retenu": rang_pick,
                       "rang_le_plus_profond_examine": max(r for r, *_ in journal),
                       "N_retenu": N, "marge_rangs": MARGE_RANGS,
                       "taille_bloc_ex_aequo": len(bloc),
                       "n_eligibles_dans_le_bloc": len(eligibles),
                       "selection_invariante_au_bloc": len(eligibles) == 1,
                       "n_exclusions_effectives": sum(1 for r, c, s, m, p in journal if s == "écarté"),
                       "course_retenue": cand.numero_train, "date_retenue": cand.date_s})

        vus = set()
        for rang, c, statut, motif, passe in journal:
            vus.add(rang)
            lignes.append(_ligne(ordre, strate, cell, rang, c, critere, col,
                                 statut, motif, "oui", passe, ""))
        # marge de profondeur : rangs au-delà de l'arrêt de l'algorithme (non examinés). On y
        # consigne, à titre indicatif, le départage qui les aurait également écartés.
        for rang, c in enumerate(pool.itertuples(), 1):
            if rang in vus or rang > N:
                continue
            aussi = (EXCL_DURCI if c.numero_train in etat.courses
                     else (etat.motif_indispo(c, cell) or ""))
            lignes.append(_ligne(ordre, strate, cell, rang, c, critere, col,
                                 "écarté", EXCL_SEV, "non", 0, aussi))

    tab = pd.DataFrame(lignes).sort_values(["ordre_application", "rang", "passe"],
                                           kind="mergesort").reset_index(drop=True)
    return tab, picks, meta_N


def _ligne(ordre, strate, cell, rang, c, critere, col, statut, motif, examine, passe, aussi=""):
    return {
        "strate": strate,
        "rang": rang,
        "numero_course": c.numero_train,
        "date": c.date_s,
        "critere_severite": critere,
        "valeur_critere": round(float(getattr(c, col)), 2),
        "statut": statut,
        "regle_exclusion": motif,
        "departage_aussi_applicable": aussi,
        "cellule": cell,
        "segment": c.segment,
        "charge_realisee": int(round(c.charge_max)),
        "score": round(float(c.score), 1),
        "resa2c": int(c.resa2c) if pd.notna(c.resa2c) else 0,
        "voie_de_capture": c.voie,
        "examine_par_l_algorithme": examine,
        "passe": passe,
        "ordre_application": ordre,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# E4 — Vérification et sensibilité
# ═══════════════════════════════════════════════════════════════════════════════
CAS_MD = ROOT / "docs/entretiens/cas_entretien_deploiement_ba493568.md"
RE_ECARTE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}) course (\d+) \((\w+)\) :.*?-> ecarte : (.+)$", re.M)


def ecartes_deja_publies():
    """Trace d'écartés déjà publiée dans les pièces d'entretien (bloc « Ecartes (auditabilite
    de la non-selection) » du document figé), pour confrontation."""
    txt = CAS_MD.read_text()
    bloc = txt[txt.index("## Ecartes"):]
    return [{"date": d, "numero_course": t, "segment": s, "motif_publie": m.strip()}
            for d, t, s, m in RE_ECARTE.findall(bloc)]


def confronter_ecartes(tab):
    """Compare la trace publiée et le tableau d'audit : ce que la trace publiée omet, ce
    qu'elle contient au-delà de la profondeur N, et l'accord des motifs."""
    publies = ecartes_deja_publies()
    cle_pub = {(e["numero_course"], e["date"]) for e in publies}
    aud = tab[tab.statut == "écarté"]
    cle_aud = {(r.numero_course, r.date) for r in aud.itertuples()}

    # candidats effectivement opposés par un départage mais absents de la trace publiée
    opposes = aud[aud.examine_par_l_algorithme == "oui"]
    omis = [{"numero_course": r.numero_course, "date": r.date, "strate": r.strate,
             "rang": r.rang, "charge": r.charge_realisee, "regle": r.regle_exclusion}
            for r in opposes.itertuples() if (r.numero_course, r.date) not in cle_pub]
    # entrées publiées situées au-delà de la profondeur N du tableau d'audit
    au_dela = [e for e in publies if (e["numero_course"], e["date"]) not in cle_aud]
    return {"n_publies": len(publies), "omis_de_la_trace_publiee": omis,
            "publies_au_dela_de_N": au_dela}


def cas_attendus():
    """Six cas effectivement présentés : ordre verrouillé + date + cellule, LUS dans la
    fiche intervieweur (aucune saisie manuelle)."""
    txt = FICHE.read_text()
    ordre = re.search(r"Ordre de presentation verrouille\s*:\s*(.+)", txt).group(1)
    seq = [m for m in re.findall(r"Cas (\d+) \((\d+)\)", ordre)]
    entetes = {t: (d, c) for t, d, c in
               re.findall(r"^## Cas \d+ - course (\d+) \((\d{4}-\d{2}-\d{2})\) - cellule (\w+)",
                          txt, re.M)}
    return [{"ordre_presentation": int(n), "numero_course": t,
             "date": entetes[t][0], "cellule": entetes[t][1]} for n, t in seq]


def cas_artefact():
    """Six cas dans l'ordre de DÉRIVATION, lus dans l'artefact figé du 2026-07-12."""
    art = json.loads(ARTEFACT.read_text())
    return [{"ordre_derivation": i, "numero_course": f["bloc_J1"]["identifiant"]["numero_train"],
             "date": f["bloc_J1"]["identifiant"]["date"], "cellule": f["cellule"],
             "raison_selection": f["notes_intervieweur"]["raison_selection"]}
            for i, f in enumerate(art["fiches"], 1)]


def rejouer(ordre, par_cle, repli):
    """Rejoue la sélection en permutant l'ordre d'application des six règles ; renvoie
    l'ensemble {(course, date)} obtenu (ou None si un vivier s'épuise)."""
    etat, out = Etat(), []
    for cle in ordre:
        viv = par_cle[cle]
        cand = choisir(viv["pool"], viv["cellule"], etat)
        if cand is None and cle == "VP_MECA":
            cand = choisir(repli["pool"], repli["cellule"], etat)
        if cand is None:
            return None
        out.append((cand.numero_train, cand.date_s))
    return frozenset(out)


def etape4(h, cap, picks):
    obtenu = [{"numero_course": c.numero_train, "date": c.date_s, "cellule": cell}
              for cell, c, _, _ in picks]
    attendu = cas_attendus()
    artefact = cas_artefact()

    set_obtenu = {(d["numero_course"], d["date"]) for d in obtenu}
    set_attendu = {(d["numero_course"], d["date"]) for d in attendu}
    set_artefact = {(d["numero_course"], d["date"]) for d in artefact}

    # ordre de dérivation vs artefact figé (même chaîne de règles)
    ordre_derivation_ok = ([(d["numero_course"], d["date"], d["cellule"]) for d in obtenu] ==
                           [(d["numero_course"], d["date"], d["cellule"]) for d in artefact])
    # ordre de présentation verrouillé vs ordre de dérivation
    ordre_presentation_identique = ([d["numero_course"] for d in obtenu] ==
                                    [d["numero_course"] for d in attendu])
    cellules_ok = ({(d["numero_course"], d["cellule"]) for d in obtenu} ==
                   {(d["numero_course"], d["cellule"]) for d in attendu})

    # -- sensibilité 1 : ordre d'application des six règles (720 permutations) --
    ref = frozenset(set_obtenu)
    vivs, repli = viviers(h, cap)
    par_cle = {v["cle"]: v for v in vivs}
    cles = [v["cle"] for v in vivs]
    perms = list(itertools.permutations(cles))
    resultats = {p: rejouer(list(p), par_cle, repli) for p in perms}
    conformes = [p for p in perms if resultats[p] == ref]
    epuises = sum(1 for p in perms if resultats[p] is None)
    # ordre d'énumération de la docstring : FN(2) puis VP(2) puis FP puis VN
    ordre_docstring = ["FN_166", "FN_HORS", "VP_166", "VP_MECA", "FP", "VN"]
    sens_docstring = rejouer(ordre_docstring, par_cle, repli) == ref

    # caractérisation dérivée : contraintes de précédence vraies sur TOUS les ordres conformes
    # et violées par au moins un ordre non conforme ; on vérifie qu'elles suffisent à décrire
    # exactement l'ensemble conforme (sinon la caractérisation est signalée comme incomplète).
    contraintes = [(a, b) for a in cles for b in cles if a != b
                   and all(p.index(a) < p.index(b) for p in conformes)
                   and any(p.index(a) > p.index(b) for p in perms if resultats[p] != ref)]
    satisfont = [p for p in perms if all(p.index(a) < p.index(b) for a, b in contraintes)]
    caracterisation_exacte = set(satisfont) == set(conformes)

    # -- sensibilité 2 : borne basse non préenregistrée du vivier VN (56) --
    vn_ref = next(c for cell, c, _, cle in picks if cle == "VN")
    etat2 = Etat()
    for cell, c, _, cle in picks:
        if cle != "VN":
            etat2.prendre(c, cell)
    pool_vn_sans_borne = (h[(h.cell == "VN") & (h.charge_max <= SEUIL)]
                          .sort_values(["charge_max", "score"], ascending=[False, True]))
    vn_sans_borne = choisir(pool_vn_sans_borne, "VN", etat2)
    sens_vn = (vn_sans_borne is not None
               and (vn_sans_borne.numero_train, vn_sans_borne.date_s) == (vn_ref.numero_train, vn_ref.date_s))

    # -- contrôle de la dérogation « strate 166+ PRIME » (résa nulle sur toute la strate) --
    s166 = h[h.charge_max >= cap]
    derog = {"n_occurrences_166plus": int(len(s166)),
             "resa2c_toutes_nulles": bool((s166["resa2c"].fillna(0) == 0).all()),
             "n_captees": int((s166["cell"] == "VP").sum())}

    return {
        "obtenu": obtenu, "attendu": attendu, "artefact": artefact,
        "ensemble_identique_a_l_attendu": set_obtenu == set_attendu,
        "ensemble_identique_a_l_artefact": set_obtenu == set_artefact,
        "cellules_identiques": cellules_ok,
        "ordre_derivation_identique_a_l_artefact": ordre_derivation_ok,
        "ordre_presentation_identique_a_l_ordre_de_derivation": ordre_presentation_identique,
        "sensibilite_ordre": {"n_permutations": len(perms), "n_identiques": len(conformes),
                              "n_viviers_epuises": epuises,
                              "ordre_enumere_docstring_donne_le_meme_resultat": bool(sens_docstring),
                              "contraintes_de_precedence": contraintes,
                              "caracterisation_exacte": bool(caracterisation_exacte),
                              "libelles": {v["cle"]: v["strate"] for v in vivs}},
        "sensibilite_borne_VN": {"borne_preenregistree": False, "pool_sans_borne": int(len(pool_vn_sans_borne)),
                                 "meme_cas_retenu": bool(sens_vn)},
        "controle_derogation_166": derog,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rendu
# ═══════════════════════════════════════════════════════════════════════════════
def fr(x, n=1):
    return f"{x:,.{n}f}".replace(",", " ").replace(".", ",")


def ecrire_tableaux(tab: pd.DataFrame):
    cols = ["strate", "rang", "numero_course", "date", "critere_severite", "valeur_critere",
            "statut", "regle_exclusion", "departage_aussi_applicable", "cellule", "segment",
            "charge_realisee", "score", "resa2c", "voie_de_capture", "examine_par_l_algorithme"]
    t = tab[cols].copy()
    DIR_TAB.mkdir(parents=True, exist_ok=True)
    t.to_csv(CSV, index=False, encoding="utf-8")

    md = ["# Tableau §3.4.2 — trace d'audit de la sélection des six cas d'entretien", "",
          "Une ligne par candidat examiné, par strate et par rang de sévérité. Les règles "
          "d'exclusion sont citées dans les termes exacts du protocole préenregistré "
          "(`scripts/experiences/selection_cas_entretien_deploiement_ba493568.py`, consigné le "
          "2026-07-12).", "",
          "| Strate | Rang | Course | Date | Critère de sévérité | Valeur | Statut | "
          "Règle d'exclusion appliquée | Départage également applicable | Segment | Charge | "
          "Score | Résa 2C | Voie |",
          "|---|---:|---:|---|---|---:|---|---|---|:--:|---:|---:|---:|---|"]
    for r in t.itertuples():
        md.append(f"| {r.strate} | {r.rang} | {r.numero_course} | {r.date} | {r.critere_severite} "
                  f"| {fr(r.valeur_critere)} | **{r.statut}** | {r.regle_exclusion or '—'} "
                  f"| {r.departage_aussi_applicable or '—'} "
                  f"| {r.segment} | {r.charge_realisee} | {fr(r.score)} | {r.resa2c} "
                  f"| {r.voie_de_capture} |")
    md += ["", f"Lignes : {len(t)} ; candidats retenus : {int((t.statut == 'retenu').sum())}.",
           "",
           "Lecture des colonnes. `Règle d'exclusion appliquée` est la règle que le protocole a "
           "effectivement opposée au candidat. Les lignes marquées « non » en colonne "
           "`examine_par_l_algorithme` (CSV) sont les rangs de marge : la règle s'est arrêtée avant "
           "de les atteindre, leur exclusion tient donc à leur sévérité inférieure ; ils sont "
           "publiés pour la profondeur d'audit exigée. `Départage également applicable` indique, "
           "pour ces rangs de marge, le départage qui les aurait de toute façon écartés."]
    TAB_MD.write_text("\n".join(md) + "\n")


def ecrire_rapport(regles, ctrl, emp, mat, tau_c, cap, meta_N, tab, v4):
    L = []
    A = L.append
    A("# Vérif §3.4.2 — trace d'audit de la sélection des six cas d'entretien")
    A("")
    A("Reconstitution déterministe, depuis les sources du dépôt, de la sélection des six cas "
      "présentés en séances décideurs D01/D02 (14.07.2026). Régénéré intégralement par "
      "`docs/memoire/verifs/section_3_4_2/audit_selection_six_cas.py` ; aucune valeur n'est "
      "saisie à la main.")
    A("")

    # ── Étape 1 ──
    A("## Étape 1 — Règles préenregistrées, restituées verbatim")
    A("")
    A("Chaque bloc est découpé automatiquement dans son fichier porteur et reproduit sans "
      "reformulation. La date de consignation est celle du plus ancien commit dont le contenu "
      "versionné contient déjà le bloc mot pour mot.")
    A("")
    for b in regles:
        A(f"### {b['theme']}")
        A("")
        d = (f"consigné le **{b['date_consignation']}** (commit `{b['commit']}`)"
             if b["date_consignation"] else
             "**non consigné dans l'historique git** : présent seulement dans l'arbre de travail")
        A(f"Source : `{b['source']}` — {d}." + (f" {b['note']}." if b["note"] else ""))
        A("")
        A("```")
        A(b["verbatim"])
        A("```")
        A("")
    A("### Contrôle de littéralité des motifs d'exclusion")
    A("")
    A("Les libellés d'exclusion employés dans le tableau d'audit sont vérifiés à l'exécution "
      "comme fragments textuels du protocole (le script échoue sinon) :")
    A("")
    for c in ctrl:
        A(f"- « {c['motif']} » — présent dans le {c['present_dans']}.")
    A("")

    A("### Règles ambiguës, absentes ou non préenregistrées — signalées, non inférées")
    A("")
    A("1. **Le guide d'entretien lui-même (v2.11, renuméroté v2.15) n'est pas un fichier du "
      "dépôt.** Le « protocole 2.3 » n'y est donc pas consultable : dans le dépôt, la seule trace "
      "textuelle des règles préenregistrées est la docstring du script de sélection, consignée le "
      "2026-07-12. Le présent audit ne peut certifier l'antériorité des règles à leur "
      "implémentation, seulement leur immutabilité depuis cette date.")
    A("2. **La borne basse du vivier VN n'est pas préenregistrée.** La règle dit « proche seuil "
      "sans franchir, silence correct (pas un cas trivialement vide) » ; l'implémentation "
      "l'opérationnalise en `charge ∈ [56 ; 63]`. La valeur 56 n'apparaît dans aucun document. "
      "Effet testé en étape 4 (sensibilité 2). À l'inverse, la borne du vivier FP "
      "(« franchement bas (charge < 40) ») est, elle, préenregistrée verbatim.")
    A("3. **L'ordre d'application des six règles n'est pas préenregistré.** La docstring énumère "
      "FN, puis VP, puis FP, puis VN ; le corps du script applique VP(166+), FN(166+), VP(mécanisme), "
      "FN(hors 166+), FP, VN. La hiérarchie consignée (« repartition > diversite d'ensemble > "
      "sous-regles de strate > severite > departages ») est une hiérarchie de priorité entre "
      "critères, pas un ordre d'exécution entre cellules. Or le départage (a) dépend de l'ordre. "
      "Effet testé en étape 4 (sensibilité 1).")
    A("4. **La « diversité d'ensemble » est vérifiée, jamais imposée.** La hiérarchie la place "
      "au-dessus des sous-règles de strate, mais l'implémentation la contrôle *a posteriori* sans "
      "jamais revenir sur une sélection ; aucun mécanisme de retour arrière n'existe. Si une "
      "condition de diversité avait échoué, le script l'aurait signalée sans corriger la sélection.")
    A("5. **La dérogation de la paire 166+ est une annotation fixe, non un test.** Le motif "
      "« diversite de mecanisme non satisfaite (vivier 166+ a resa2c=0, voie score seule) ; la "
      "strate 166+ PRIME » est attaché inconditionnellement au premier VP. Sa prémisse est "
      "néanmoins vérifiée ici par le calcul (étape 4, contrôle de dérogation).")
    A("6. **L'ordre de présentation des six cas ne dérive d'aucune règle du protocole.** Il est "
      "verrouillé dans `docs/entretiens/supports/fiche_intervieweur.md:6` sans justification "
      "consignée. Voir étape 4.")
    if modifie_non_valide(ADR_077):
        A("7. **ADR-077 porte des modifications non validées dans git** (arbre de travail) : "
          "l'addendum daté du 2026-07-24 qui porte le statut de « proposé » à « accepté » n'est pas "
          "encore versionné. La configuration de tirage, elle, est consignée depuis le 2026-07-12.")
    A("")

    # ── Étape 2 ──
    A("## Étape 2 — Empreintes vérifiées et reconstitution du vivier")
    A("")
    A("### Empreintes")
    A("")
    d = emp["dataset"]
    A("| Élément | Fichier | Empreinte SHA256[:8] | Attendue | Conforme |")
    A("|---|---|---|---|:--:|")
    A(f"| Jeu d'évaluation H25 (dataset canonique) | `{d['fichier']}` | `{d['empreinte']}` "
      f"| `{d['attendue']}` | {'✓' if d['conforme'] else '✗'} |")
    for m in emp["modeles"]:
        A(f"| Modèle couche 1 figé, segment {m['segment']} | `{m['fichier']}` | `{m['empreinte']}` "
          f"| `{m['attendue']}` | {'✓' if m['conforme'] else '✗'} |")
    A("")
    A("**Sur la référence « couche décisionnelle figée `416bb90b` ».** `416bb90b` est l'empreinte "
      "de l'**ancien gel** du dataset (v1.9, gelé le 2026-06-21), remplacé par le gel v2 "
      "`ba493568` (ADR-076, 2026-07-11) ; ce n'est pas une empreinte de couche décisionnelle. "
      "La sélection des six cas s'est faite sur le gel v2. Contrôle d'identité binaire des poids :")
    A("")
    A("| Segment | Fichier étiqueté `416bb90b` | Empreinte | Fichier étiqueté `ba493568` | Identiques |")
    A("|---|---|---|---|:--:|")
    for seg, g in emp["generation_416bb90b"].items():
        A(f"| {seg} | `{g['fichier_v19']}` | `{g['empreinte_v19']}` | `{g['empreinte_v2']}` "
          f"| {'✓' if g['identiques'] else '✗'} |")
    A("")
    if all(g["identiques"] for g in emp["generation_416bb90b"].values()):
        A("Les modèles des deux générations sont **byte-identiques** : la couche décisionnelle "
          "employée est bien la même sous les deux étiquettes, et la formulation « couche "
          "décisionnelle figée `416bb90b` » ne désigne pas d'autres poids. L'étiquette de "
          "génération courante reste néanmoins `ba493568` : c'est elle que portent le dataset, "
          "les gardes et les artefacts de la sélection.")
    else:
        A("Les modèles des deux générations **diffèrent** : la formulation « couche décisionnelle "
          "figée `416bb90b` » désignerait alors d'autres poids que ceux employés.")
    A("")
    A("Artefacts couche 2 de la génération `416bb90b` conservés côte à côte (trace historique, "
      "ADR-076) : " + ", ".join(f"`{Path(p).name}`" for p in emp["artefacts_nommes_416bb90b"]) + ".")
    A("")
    A("### Point de fonctionnement et matrice de tirage")
    A("")
    A(f"Configuration : recommandation = (score de course ≥ τ(c) = {fr(tau_c, 2)}) OU (résa 2C J-1 > "
      f"{SEUIL}). Seuil τ(c) lu dans `{CALIB.relative_to(ROOT)}` et **re-calibré indépendamment** "
      f"sur H24 par `decision.calibrate` : écart {mat['tau_c_ecart']:.2e}.")
    A("")
    g = mat["gardes"]
    A(f"Gardes P3 tenues : {fr(g['n_h25'], 0)} courses H25, {fr(g['positives_h25'], 0)} surcharges "
      f"({fr(g['positives_haut'], 0)} haut / {fr(g['positives_bas'], 0)} bas).")
    A("")
    m, a = mat["matrice"], mat["matrice_artefact_fige"]
    A("| Quadrant | Re-dérivé | Artefact figé du 2026-07-12 | Conforme |")
    A("|---|---:|---:|:--:|")
    for k in ("VP", "FP", "FN", "VN", "volume_recommande"):
        A(f"| {k} | {fr(m[k], 0)} | {fr(a[k], 0)} | {'✓' if m[k] == a[k] else '✗'} |")
    A("")
    A(f"Strate des affluences extrêmes : `CAP_RAME = {cap}` (lu dans le script figé).")
    A("")
    A("### Profondeur N des viviers")
    A("")
    A("N = (rang le plus profond atteint par l'algorithme, retenu ou écarté) + 2 rangs de marge, "
      "borné par la taille du vivier. La règle balaie chaque vivier du rang 1 jusqu'à l'arrêt : "
      "tout candidat écarté par un départage est donc de rang inférieur ou égal à ce maximum, et N "
      "les couvre tous avec la marge exigée."
      + (" Sur les six viviers, ce maximum coïncide avec le rang du candidat retenu."
         if all(x["rang_du_retenu"] == x["rang_le_plus_profond_examine"] for x in meta_N) else ""))
    A("")
    A("| Vivier | Taille | Rang du retenu | Rang le plus profond examiné | N publié |")
    A("|---|---:|---:|---:|---:|")
    for x in meta_N:
        A(f"| {x['strate']} | {fr(x['taille_vivier'], 0)} | {x['rang_du_retenu']} "
          f"| {x['rang_le_plus_profond_examine']} | {x['N_retenu']} |")
    A("")
    A("### Ex æquo sur le critère de sévérité")
    A("")
    A("Un vivier peut contenir plusieurs candidats de valeur de critère strictement identique : "
      "leur ordre interne ne vient alors pas du protocole mais de l'ordre des lignes en entrée. "
      "Pour chaque vivier, on isole le bloc d'ex æquo contenant le candidat retenu et on compte, "
      "dans l'état des départages à l'entrée du vivier, combien de ses membres étaient éligibles. "
      "Un seul éligible ⇒ la sélection ne dépend pas de l'ordre interne du bloc.")
    A("")
    A("| Vivier | Taille du bloc d'ex æquo du retenu | Éligibles dans le bloc | Sélection invariante |")
    A("|---|---:|---:|:--:|")
    for x in meta_N:
        A(f"| {x['strate']} | {x['taille_bloc_ex_aequo']} | {x['n_eligibles_dans_le_bloc']} "
          f"| {'✓' if x['selection_invariante_au_bloc'] else '✗'} |")
    A("")
    if all(x["selection_invariante_au_bloc"] for x in meta_N):
        A("Les six sélections sont **invariantes** à l'ordre interne des blocs d'ex æquo : là où "
          "des ex æquo existent, les règles de départage n'en laissent qu'un seul éligible. Aucun "
          "départage implicite par l'ordre des lignes n'intervient.")
    else:
        A("**Au moins un bloc d'ex æquo compte plusieurs candidats éligibles** : la sélection y "
          "dépend de l'ordre des lignes en entrée, degré de liberté résiduel à signaler.")
    A("")

    # ── Étape 3 ──
    A("## Étape 3 — Application des règles et tableau d'audit")
    A("")
    A(f"Le tableau complet ({len(tab)} lignes, une par candidat examiné) est publié dans "
      f"`{CSV.relative_to(ROOT)}` et `{TAB_MD.relative_to(ROOT)}`. Synthèse des six sélections, "
      f"dans l'ordre d'application des règles :")
    A("")
    A("| # | Strate | Course | Date | Cellule | Critère | Valeur | Rang |")
    A("|---:|---|---:|---|:--:|---|---:|---:|")
    ret = tab[tab.statut == "retenu"]
    for i, r in enumerate(ret.itertuples(), 1):
        A(f"| {i} | {r.strate} | {r.numero_course} | {r.date} | {r.cellule} | {r.critere_severite} "
          f"| {fr(r.valeur_critere)} | {r.rang} |")
    A("")
    ecartes = tab[tab.statut == "écarté"]
    A(f"Candidats écartés consignés : {len(ecartes)}, dont "
      f"{int((ecartes.examine_par_l_algorithme == 'oui').sum())} effectivement examinés par une "
      f"règle de départage et {int((ecartes.examine_par_l_algorithme == 'non').sum())} publiés au "
      f"titre de la marge de profondeur.")
    A("")
    par_regle = ecartes[ecartes.examine_par_l_algorithme == "oui"]["regle_exclusion"].value_counts()
    if len(par_regle):
        A("Répartition des exclusions effectives par règle :")
        A("")
        for k, v in par_regle.items():
            A(f"- « {k} » : {v}")
        A("")

    # -- confrontation à la trace d'écartés déjà publiée --
    conf = confronter_ecartes(tab)
    A("### Confrontation à la trace d'écartés déjà publiée")
    A("")
    A(f"Le document figé `{CAS_MD.relative_to(ROOT)}` porte un bloc « Ecartes (auditabilite de la "
      f"non-selection) » de {conf['n_publies']} entrées. Il n'est pas équivalent au tableau d'audit :")
    A("")
    if conf["omis_de_la_trace_publiee"]:
        A(f"**{len(conf['omis_de_la_trace_publiee'])} candidats effectivement opposés par une règle "
          f"de départage n'y figurent pas.** La fonction qui produit ce bloc écarte de sa liste tout "
          f"candidat dont la course a été retenue ailleurs ; or c'est précisément la préférence de "
          f"non-réutilisation qui les a exclus. Les candidats les plus sévères de leur vivier "
          f"disparaissent ainsi de la trace publiée :")
        A("")
        A("| Course | Date | Strate | Rang | Charge | Règle qui l'écarte |")
        A("|---:|---|---|---:|---:|---|")
        for o in conf["omis_de_la_trace_publiee"]:
            A(f"| {o['numero_course']} | {o['date']} | {o['strate']} | {o['rang']} | {o['charge']} "
              f"| {o['regle']} |")
        A("")
        A("Le tableau d'audit publié ici les rétablit : c'est la condition pour que l'affirmation "
          "« chaque cas candidat non retenu a été consigné avec la règle qui l'écarte » soit "
          "littéralement vraie.")
    else:
        A("Aucun candidat opposé par un départage ne manque à la trace publiée.")
    A("")
    if conf["publies_au_dela_de_N"]:
        A(f"À l'inverse, {len(conf['publies_au_dela_de_N'])} entrée(s) de la trace publiée se "
          f"situent au-delà de la profondeur N retenue ici (rangs de sévérité plus faibles, jamais "
          f"atteints par la règle) : "
          + " ; ".join(f"course {e['numero_course']} du {e['date']}" for e in conf["publies_au_dela_de_N"])
          + ". Elles ne sont pas contredites, seulement hors du périmètre de profondeur documenté "
            "en étape 2.")
        A("")
    A("Enfin, les motifs de la trace publiée sont calculés *a posteriori*, sur l'état final des "
      "départages : un candidat que la règle n'a jamais atteint peut y recevoir le motif « meme "
      "date qu'un cas retenu ». Le tableau d'audit distingue les deux situations (colonnes "
      "`regle_exclusion` et `departage_aussi_applicable`).")
    A("")

    # -- contrôle des motifs publiés dans les pièces d'entretien --
    A("### Contrôle des motifs de sélection publiés")
    A("")
    A("Les « raisons de sélection » imprimées sur les fiches d'entretien sont des libellés fixes du "
      "script, non des traces calculées. Confrontation au déroulé effectif :")
    A("")
    A("| Course | Motif publié (artefact figé) | Exclusions effectivement opposées avant le retenu | Cohérent |")
    A("|---:|---|---:|:--:|")
    raisons = {(c["numero_course"], c["date"]): c["raison_selection"] for c in v4["artefact"]}
    incoherents = []
    for x in meta_N:
        motif = raisons.get((x["course_retenue"], x["date_retenue"]), "—")
        court = motif.split(" | ")[0]
        annonce_departage = "departage" in court.lower()
        coherent = (x["n_exclusions_effectives"] > 0) or not annonce_departage
        if not coherent:
            incoherents.append((x, court))
        A(f"| {x['course_retenue']} | {court} | {x['n_exclusions_effectives']} "
          f"| {'✓' if coherent else '✗'} |")
    A("")
    for x, court in incoherents:
        A(f"**Écart de libellé.** Le motif publié pour la course {x['course_retenue']} "
          f"({x['date_retenue']}) annonce un départage, alors que le candidat a été retenu au rang "
          f"{x['rang_du_retenu']} de son vivier sans qu'aucune règle de départage n'ait eu à être "
          f"opposée à un candidat mieux classé. Le libellé est une chaîne fixe du script, écrite "
          f"avant l'exécution : il décrit la règle disponible, pas l'événement survenu. Le "
          f"départage de date aurait bien joué au rang suivant (voir le tableau d'audit), mais "
          f"il n'a pas été atteint. Aucune conséquence sur le cas retenu ; incidence sur la "
          f"lecture de la trace publiée.")
        A("")

    # ── Étape 4 ──
    A("## Étape 4 — Vérification")
    A("")
    A("### Les six cas re-dérivés")
    A("")
    A("| Ordre de dérivation | Course | Date | Cellule | Ordre de présentation verrouillé |")
    A("|---:|---:|---|:--:|---:|")
    pres = {c["numero_course"]: c["ordre_presentation"] for c in v4["attendu"]}
    for i, c in enumerate(v4["obtenu"], 1):
        A(f"| {i} | {c['numero_course']} | {c['date']} | {c['cellule']} "
          f"| {pres.get(c['numero_course'], '—')} |")
    A("")
    ok_set = v4["ensemble_identique_a_l_attendu"]
    A(f"- Ensemble des six cas (course + date) identique aux cas effectivement présentés : "
      f"**{'OUI' if ok_set else 'NON'}**.")
    A(f"- Affectation de cellule identique pour les six : "
      f"**{'OUI' if v4['cellules_identiques'] else 'NON'}**.")
    A(f"- Ordre de dérivation identique à l'artefact figé du 2026-07-12 "
      f"(`{ARTEFACT.relative_to(ROOT)}`) : "
      f"**{'OUI' if v4['ordre_derivation_identique_a_l_artefact'] else 'NON'}**.")
    A(f"- Ordre de dérivation identique à l'ordre de présentation verrouillé : "
      f"**{'OUI' if v4['ordre_presentation_identique_a_l_ordre_de_derivation'] else 'NON'}**.")
    A("")
    A("Confrontation à la liste attendue (cas 1 course 1423 du 18.05.2025 ; cas 2 course 1326 du "
      "19.12.2024 ; cas 3 course 1448 du 29.05.2025 ; cas 4 course 1435 du 23.12.2024 ; cas 5 "
      "course 1416 du 04.09.2025 ; cas 6 course 1508 du 02.09.2025), lue dans la fiche "
      "intervieweur :")
    A("")
    A("| Cas | Course | Date | Cellule | Reproduit par les règles |")
    A("|---:|---:|---|:--:|:--:|")
    obt = {(c["numero_course"], c["date"]): c["cellule"] for c in v4["obtenu"]}
    for c in v4["attendu"]:
        k = (c["numero_course"], c["date"])
        A(f"| {c['ordre_presentation']} | {c['numero_course']} | {c['date']} | {c['cellule']} "
          f"| {'✓' if k in obt and obt[k] == c['cellule'] else '✗'} |")
    A("")

    A("### Divergence constatée")
    A("")
    if ok_set and v4["cellules_identiques"] and not v4["ordre_presentation_identique_a_l_ordre_de_derivation"]:
        A("**Une seule divergence, portant sur l'ordre et non sur le contenu.** Les six cas sont "
          "reproduits exactement — mêmes courses, mêmes dates, mêmes cellules — mais l'ordre "
          "demandé (cas 1 à 6) est l'**ordre de présentation verrouillé**, qui n'est produit par "
          "aucune règle du protocole préenregistré.")
        A("")
        A("*Origine probable.* Les règles de sélection produisent un ordre de **dérivation** "
          "(les strates fermées 166+ d'abord, puis les cellules restantes), reproduit ici à "
          "l'identique et confirmé par l'artefact figé du 2026-07-12. L'ordre de **présentation** "
          "est fixé séparément dans `docs/entretiens/supports/fiche_intervieweur.md:6` ; il relève "
          "de la conduite d'entretien, pas de la sélection. Aucune règle générant cette permutation "
          "n'existe dans le dépôt, et le guide d'entretien qui pourrait la porter n'y est pas "
          "versionné.")
        A("")
        A("*Degré de liberté résiduel.* La permutation entre les deux ordres n'est ni dérivable "
          "ni auditable en l'état : c'est, parmi les points relevés ici, le seul qui porte sur ce "
          "que le répondant voit sans être adossé à une règle consignée. Deux régularités "
          "s'observent *a posteriori* sur "
          "l'ordre retenu — les quatre cellules apparaissent une fois avant toute répétition, et "
          "les deux occurrences de la strate 166+ occupent les positions extrêmes (1 et 6), ce qui "
          "va dans le sens du pare-feu d'étanchéité de la paire 166+ (guide 2.2). Ce sont des "
          "**observations**, pas des règles reconstituées : rien dans le dépôt ne les consigne "
          "comme critère de tri.")
    elif ok_set and v4["cellules_identiques"]:
        A("Aucune divergence : contenu, cellules et ordre sont reproduits à l'identique.")
    else:
        A("**Divergence sur le contenu de la sélection** — détail :")
        A("")
        att = {(c["numero_course"], c["date"]) for c in v4["attendu"]}
        got = {(c["numero_course"], c["date"]) for c in v4["obtenu"]}
        for k in sorted(att - got):
            A(f"- attendu et non re-dérivé : course {k[0]} du {k[1]}")
        for k in sorted(got - att):
            A(f"- re-dérivé et non attendu : course {k[0]} du {k[1]}")
    A("")

    A("### Sensibilité aux degrés de liberté identifiés en étape 1")
    A("")
    s = v4["sensibilite_ordre"]
    A(f"**1. Ordre d'application des six règles** (non préenregistré). Les "
      f"{s['n_permutations']} permutations possibles ont été rejouées : **{s['n_identiques']} / "
      f"{s['n_permutations']}** produisent exactement les six mêmes cas, et {s['n_viviers_epuises']} "
      f"conduisent à un vivier épuisé (sélection impossible). L'ordre d'énumération de la docstring "
      f"(FN, puis VP, puis FP, puis VN), distinct de l'ordre d'exécution du script, donne "
      f"{'**le même résultat**' if s['ordre_enumere_docstring_donne_le_meme_resultat'] else '**un résultat DIFFÉRENT**'}.")
    A("")
    if s["n_identiques"] == s["n_permutations"]:
        A("La sélection est donc invariante à ce degré de liberté.")
    else:
        A(f"La sélection **dépend** de ce degré de liberté : "
          f"{s['n_permutations'] - s['n_identiques']} ordres d'application auraient donné autre "
          f"chose. L'ensemble des ordres conformes est exactement caractérisé par "
          f"{len(s['contraintes_de_precedence'])} contrainte(s) de précédence, dérivée(s) du calcul :"
          if s["caracterisation_exacte"] else
          f"La sélection **dépend** de ce degré de liberté : "
          f"{s['n_permutations'] - s['n_identiques']} ordres d'application auraient donné autre "
          f"chose. Les contraintes de précédence suivantes sont nécessaires, mais ne suffisent pas "
          f"à décrire l'ensemble des ordres conformes :")
        A("")
        lib = s["libelles"]
        for a, b in s["contraintes_de_precedence"]:
            A(f"- « {lib[a]} » doit être appliquée avant « {lib[b]} ».")
        A("")
        if set(map(tuple, s["contraintes_de_precedence"])) == {("FN_166", "FN_HORS"), ("FN_166", "FP")}:
            A("Autrement dit : la règle de la strate 166+ manquée doit passer avant les deux autres "
              "viviers qui se disputent la même course, faute de quoi la préférence de "
              "non-réutilisation la lui retire. L'ordre effectivement employé — celui du corps du "
              "script figé — satisfait ces contraintes, et l'ordre d'énumération de la docstring "
              "aussi : les deux lectures possibles du préenregistrement mènent au même résultat, "
              "mais l'ordre n'est pas libre pour autant.")
        else:
            A("L'ordre effectivement employé est celui du corps du script figé.")
    A("")
    b = v4["sensibilite_borne_VN"]
    A(f"**2. Borne basse du vivier VN** (valeur 56, non préenregistrée). En supprimant la borne "
      f"(vivier étendu à toutes les charges ≤ {SEUIL}, soit {fr(b['pool_sans_borne'], 0)} candidats), "
      f"le cas retenu est "
      f"{'inchangé' if b['meme_cas_retenu'] else '**différent**'}. "
      + ("La valeur 56 est donc sans effet sur la sélection : le tri par charge décroissante place "
         "de toute façon les charges les plus proches du seuil en tête."
         if b["meme_cas_retenu"] else
         "La valeur 56 est donc déterminante et constitue un degré de liberté effectif."))
    A("")
    dg = v4["controle_derogation_166"]
    A(f"**3. Prémisse de la dérogation de la paire 166+.** La strate compte "
      f"{dg['n_occurrences_166plus']} occurrences H25, dont {dg['n_captees']} captée(s) par la "
      f"configuration. Prémisse « vivier 166+ à resa2c = 0 » : "
      f"**{'vérifiée' if dg['resa2c_toutes_nulles'] else 'FAUSSE'}** — la dérogation « la strate "
      f"166+ PRIME » sur la diversité de mécanisme "
      f"{'repose bien sur un fait établi' if dg['resa2c_toutes_nulles'] else 'ne repose pas sur le fait invoqué'}.")
    A("")

    A("## Conclusion")
    A("")
    verdict = ("reproduit exactement les six cas présentés" if ok_set and v4["cellules_identiques"]
               else "NE reproduit PAS les six cas présentés")
    A(f"L'application des règles préenregistrées aux viviers reconstruits sur le gel `ba493568` "
      f"{verdict} : mêmes courses, mêmes dates, mêmes cellules, et même ordre de dérivation que "
      f"l'artefact figé du 2026-07-12. La reconstitution n'a été ajustée à aucun moment pour "
      f"retrouver ce résultat : les règles sont celles du protocole, appliquées telles quelles.")
    A("")
    reserves = []
    if not v4["ordre_presentation_identique_a_l_ordre_de_derivation"]:
        reserves.append(
            "**L'ordre de présentation des six cas n'est pas produit par le protocole** ; il est "
            "verrouillé séparément dans la fiche intervieweur, sans règle génératrice consignée. "
            "C'est la seule divergence entre la reconstitution et la liste attendue telle "
            "qu'ordonnée.")
    omis = conf["omis_de_la_trace_publiee"]
    if omis:
        strates = sorted({o["strate"] for o in omis})
        reserves.append(
            f"**La trace d'écartés déjà publiée est incomplète** : {len(omis)} candidats "
            f"({'le vivier' if len(strates) == 1 else 'les viviers'} « "
            + " » et « ".join(strates) +
            " »), écartés par la préférence de non-réutilisation de course, n'y figurent pas — ce "
            "sont pourtant les mieux classés de leur vivier. Le tableau d'audit publié ici les "
            "rétablit ; c'est ce qui rend l'affirmation du manuscrit « chaque cas candidat non "
            "retenu a été consigné avec la règle qui l'écarte » littéralement vraie, ce qu'elle "
            "n'était pas avant.")
    for x, _court in incoherents:
        reserves.append(
            f"**Un motif de sélection publié annonce un départage qui n'a pas eu lieu** (course "
            f"{x['course_retenue']} du {x['date_retenue']}, retenue au rang {x['rang_du_retenu']}). "
            f"Les libellés des fiches sont des chaînes fixes du script, non des traces "
            f"d'exécution. Sans effet sur la sélection.")
    if s["n_identiques"] < s["n_permutations"]:
        reserves.append(
            f"**L'ordre d'application des règles, non préenregistré, n'est pas indifférent** : "
            f"{s['n_identiques']} des {s['n_permutations']} ordres possibles reproduisent la "
            f"sélection. Les deux lectures que le préenregistrement autorise — énumération de la "
            f"docstring et exécution du script — en font partie, mais la propriété tient au fait "
            f"empirique, pas à la règle.")
    NOMS = {1: "Une réserve", 2: "Deux réserves", 3: "Trois réserves", 4: "Quatre réserves",
            5: "Cinq réserves"}
    A(f"{NOMS.get(len(reserves), f'{len(reserves)} réserves')}, "
      f"{'documentée' if len(reserves) == 1 else 'toutes documentées'} ci-dessus, "
      f"{'encadre' if len(reserves) == 1 else 'encadrent'} cette conclusion :")
    A("")
    for i, r in enumerate(reserves, 1):
        A(f"{i}. {r}")
    A("")
    DIR_VERIF.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text("\n".join(L) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("[E1] extraction verbatim des règles préenregistrées…")
    regles = etape1_regles()
    ctrl = controle_verbatim_exclusions()
    print(f"     {len(regles)} blocs extraits, {len(ctrl)} motifs d'exclusion contrôlés verbatim")

    print("[E2] empreintes…")
    emp = etape2_empreintes()
    print(f"     dataset {emp['dataset']['empreinte']} "
          f"({'conforme' if emp['dataset']['conforme'] else 'NON CONFORME'}) ; "
          f"modèles " + " / ".join(f"{m['segment']}={m['empreinte']}" for m in emp["modeles"]))

    print("[E2] reconstruction de la matrice de tirage…")
    h, tau_c, mat = etape2_matrice()
    print(f"     tau_c = {tau_c:.5f} (écart au re-calibrage : {mat['tau_c_ecart']:.2e})")
    print(f"     matrice {mat['matrice']} — conforme à l'artefact : {mat['matrice_conforme']}")

    cap = cap_rame()
    print(f"[E3] application des règles (CAP_RAME = {cap})…")
    tab, picks, meta_N = etape3_audit(h, cap)
    for cell, c, strate, cle in picks:
        print(f"     {cell:3} {c.date_s} course {c.numero_train} "
              f"charge={int(round(c.charge_max)):3} score={c.score:6.1f} "
              f"resa={int(c.resa2c) if pd.notna(c.resa2c) else 0:3} voie={c.voie}")

    print("[E4] vérification et sensibilité…")
    v4 = etape4(h, cap, picks)
    print(f"     ensemble identique aux cas présentés : {v4['ensemble_identique_a_l_attendu']}")
    print(f"     cellules identiques                  : {v4['cellules_identiques']}")
    print(f"     ordre de dérivation = artefact figé  : {v4['ordre_derivation_identique_a_l_artefact']}")
    print(f"     ordre de dérivation = ordre présenté : "
          f"{v4['ordre_presentation_identique_a_l_ordre_de_derivation']}")
    s = v4["sensibilite_ordre"]
    print(f"     sensibilité ordre : {s['n_identiques']}/{s['n_permutations']} permutations "
          f"donnent la même sélection")
    print(f"     sensibilité borne VN : même cas retenu = {v4['sensibilite_borne_VN']['meme_cas_retenu']}")

    ecrire_tableaux(tab)
    ecrire_rapport(regles, ctrl, emp, mat, tau_c, cap, meta_N, tab, v4)
    print(f"[OK] {RAPPORT.relative_to(ROOT)}")
    print(f"[OK] {CSV.relative_to(ROOT)}")
    print(f"[OK] {TAB_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
