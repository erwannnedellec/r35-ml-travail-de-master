#!/usr/bin/env python3
"""
Section 4.5 — compléments à `verif_45_configuration.py`.

LECTURE SEULE. Aucun réentraînement, aucune réoptimisation, aucune écriture hors
de docs/memoire/verifs/section_4_5/. Le parquet canonique n'est que haché ; les
modèles gelés ne sont ouverts qu'en lecture.

Compléments
-----------
C1. Confrontation H25 du candidat best-R² de la campagne (b) contre la
    configuration retenue : R², MAE, MAE>63, biais>63, PR-AUC par segment et en
    global, pour les DEUX configurations. Détermination de l'état de données sur
    lequel la lecture a porté (`416bb90b` ou `ba493568`), par comparaison des
    valeurs de référence aux deux fichiers de métadonnées présents dans le dépôt.
    Contrôle chiffré de deux affirmations du manuscrit.
    -> verif_45c_c1_h25_best_r2.csv
C2. Résultat de la campagne (a) : combinaison gagnante des 27 par cellule, score,
    et rang de la combinaison (6 / 1 / 300 / 0,1) avec son écart au premier.
    Classement recalculé depuis le CSV brut des 162 lignes walk-forward.
    -> verif_45c_c2_campagne_a.csv
C3. Quatrième campagne d'`exp_hpo` (`tuning_optuna_h24_prauc_troncon.py`) :
    objectif, espace, budget, graine, validation, empreinte, gagnante, et
    recherche d'une trace de confrontation à H25. Comparaison paramètre par
    paramètre avec l'espace de la campagne (b).
    -> verif_45c_c3_campagne_prauc.csv
C4. Désambiguïsation de l'empreinte tronquée `416bb90b` : objet désigné, recensement
    exhaustif des occurrences (constante de garde, suffixe de nom de fichier, champ
    de métadonnées, prose), et hachage de TOUS les fichiers du dépôt pour établir
    si un artefact porte cette empreinte comme empreinte propre.
    -> verif_45c_c4_empreinte_416bb90b.csv

Plus une synthèse machine : verif_45_complements_synthese.json.
Sorties déterministes : aucun horodatage embarqué, aucune date de système de
fichiers (les dates rapportées viennent de l'historique git, reproductible).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import ast
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
HASH_DATASET_8 = "ba493568"
MODEL_DIR = ROOT / "models/enrichi_seg"
MODELS = {"bas": ("enrichi_seg_bas_ba493568.json", "e4ddfccd"),
          "haut": ("enrichi_seg_haut_ba493568.json", "df6a11c5")}

DIR_B = ROOT / "archive/explorations/consolidation_finale/exp_hpo"
SRC_B = DIR_B / "tuning_optuna_h24.py"
C1_PY = DIR_B / "test_h25_best_r2_vs_cf09.py"
C1_JSON = DIR_B / "test_h25_best_r2_vs_cf09.json"
C1_MD = DIR_B / "RAPPORT_TEST_H25_best_r2.md"

DIR_A = ROOT / "archive/explorations/consolidation_finale"
A_NB = DIR_A / "notebooks/etape_03_robustesse_hyperparams.ipynb"
A_BEST = DIR_A / "outputs/etape_03_best_params.json"
A_WF = DIR_A / "outputs/etape_03_wf_tuning_results.csv"

C3_PY = DIR_B / "tuning_optuna_h24_prauc_troncon.py"
C3_JSON = DIR_B / "tuning_prauc_troncon_h24_resultats.json"
C3_TRIALS = DIR_B / "tuning_prauc_troncon_h24_trials.csv"
C3_MD = DIR_B / "RAPPORT_TUNING_PRAUC_TRONCON_H24.md"
C3_TEST_PY = DIR_B / "test_h25_prauc_troncon_vs_cf09.py"
C3_TEST_JSON = DIR_B / "test_h25_prauc_troncon_vs_cf09.json"
C3_TEST_MD = DIR_B / "RAPPORT_TEST_H25_prauc_troncon.md"

META_COURANT = MODEL_DIR / "enrichi_seg_metadata.json"          # génération ba493568
META_V19 = MODEL_DIR / "enrichi_seg_metadata_416bb90b.json"     # génération 416bb90b

EMPREINTE = "416bb90b"
INTROUVABLE = "INTROUVABLE dans le dépôt"

# Racines balayées pour le hachage exhaustif du complément 4 (tout le dépôt suivi
# ou produit, hors environnement virtuel et caches).
RACINES_HACHAGE = ["models", "outputs", "docs", "src", "scripts", "archive", "tests",
                   "notebooks", "consolidation_finale", "reports", "figures", "logs",
                   "analysis", "anonymisation", "catboost_info", "data/processed"]
EXCLUS_HACHAGE = ["venv", "__pycache__", ".git", "node_modules", ".ipynb_checkpoints"]


# ════════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ════════════════════════════════════════════════════════════════════════════════
def sha256_full(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha8(path: Path) -> str:
    return sha256_full(path)[:8]


def rel(path: Path) -> str:
    return str(Path(path).relative_to(ROOT))


def src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def git(*args) -> str:
    """Sortie git dépouillée ; chaîne vide si git indisponible ou sans réponse."""
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def date_premier_commit(path: Path) -> str:
    """Date du commit qui ajoute le fichier (ancrage temporel reproductible)."""
    d = git("log", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel(path))
    return d.splitlines()[-1] if d else INTROUVABLE


def module_literals(tree: ast.AST) -> dict:
    env = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    try:
                        env[t.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError):
                        pass
                elif isinstance(t, ast.Tuple):
                    try:
                        vals = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    for el, v in zip(t.elts, vals if isinstance(vals, tuple) else ()):
                        if isinstance(el, ast.Name):
                            env[el.id] = v
    return env


def scalaire(source: str, nom: str):
    tree = ast.parse(source)
    return module_literals(tree).get(nom)


def espace_suggest(source: str, nom_fonction: str) -> dict:
    """Espace de recherche Optuna d'une fonction, lu dans ses appels `suggest_*`."""
    tree = ast.parse(source)
    cible = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == nom_fonction:
            cible = node
    if cible is None:
        raise LookupError(f"fonction {nom_fonction} absente")
    out = {}
    for node in ast.walk(cible):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if not node.func.attr.startswith("suggest_"):
            continue
        args = [ast.literal_eval(a) for a in node.args]
        kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
        out[args[0]] = {"appel": node.func.attr,
                        "type": "entier" if node.func.attr == "suggest_int" else "réel",
                        "borne_min": args[1], "borne_max": args[2],
                        "loi": "log-uniforme" if kw.get("log") else "uniforme"}
    return out


def notebook_code(path: Path) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    ok = []
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        s = "".join(c["source"])
        try:
            ast.parse(s)
            ok.append(s)
        except SyntaxError:
            pass
    return "\n".join(ok)


def write_csv(name: str, header: list, rows: list) -> Path:
    p = OUT / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  -> {rel(p)} ({len(rows)} lignes)")
    return p


def f6(x):
    return "" if x is None else f"{x:.6f}" if isinstance(x, float) else str(x)


# ════════════════════════════════════════════════════════════════════════════════
# Préambule
# ════════════════════════════════════════════════════════════════════════════════
def preambule() -> dict:
    print("=" * 88)
    print("VERIF §4.5 — compléments C1 à C4 (lecture seule)")
    print("=" * 88)
    prov = {}
    if ML_DATASET.exists():
        full = sha256_full(ML_DATASET)
        if full[:8] != HASH_DATASET_8:
            raise RuntimeError(f"STOP provenance : dataset {full[:8]} != {HASH_DATASET_8}")
        prov["dataset"] = {"fichier": rel(ML_DATASET), "sha256": full, "sha256_8": full[:8]}
        print(f"  dataset {rel(ML_DATASET)} : SHA256[:8] = {full[:8]} OK")
    else:
        prov["dataset"] = {"fichier": rel(ML_DATASET), "sha256": INTROUVABLE}
        print(f"  dataset {rel(ML_DATASET)} ABSENT")
    prov["modeles"] = {}
    for seg, (fn, att) in MODELS.items():
        h = sha8(MODEL_DIR / fn)
        if h != att:
            raise RuntimeError(f"STOP provenance : modèle {seg} {h} != {att}")
        prov["modeles"][seg] = {"fichier": rel(MODEL_DIR / fn), "sha256_8": h}
        print(f"  modèle {seg:<4} : SHA256[:8] = {h} OK")
    manquants = [rel(p) for p in (C1_PY, C1_JSON, A_BEST, A_WF, C3_PY, C3_JSON,
                                  C3_TEST_PY, C3_TEST_JSON, META_COURANT, META_V19)
                 if not p.exists()]
    prov["fichiers_sources_manquants"] = manquants
    print(f"  fichiers sources attendus manquants : {manquants if manquants else 'aucun'}")
    return prov


# ════════════════════════════════════════════════════════════════════════════════
# COMPLÉMENT 1 — confrontation H25 du candidat best-R²
# ════════════════════════════════════════════════════════════════════════════════
def complement_1() -> dict:
    print("\n" + "-" * 88)
    print("C1 — confrontation H25 : candidat best-R² (campagne b) vs configuration retenue")
    print("-" * 88)
    d = json.loads(C1_JSON.read_text(encoding="utf-8"))
    code = src(C1_PY)
    hash_asserte = scalaire(code, "HASH_ATTENDU")
    seed = scalaire(code, "SEED")
    seuil = scalaire(code, "SEUIL")

    # -- état de données : déterminé par confrontation aux DEUX métadonnées du dépôt --
    meta_cour = json.loads(META_COURANT.read_text(encoding="utf-8"))["metrics_h25"]
    meta_v19 = json.loads(META_V19.read_text(encoding="utf-8"))["metrics_h25"]
    ref = d["cf09_h25"]
    concordance = {}
    for etiq, meta, gen in (("metadata courant", meta_cour, "ba493568"),
                            ("metadata v1.9", meta_v19, "416bb90b")):
        ecarts = {s: abs(ref[s]["r2_global"] - meta[s]["r2"]) for s in ("bas", "haut", "global")}
        concordance[gen] = {"source": etiq, "ecart_max_r2": max(ecarts.values()),
                            "ecarts": ecarts,
                            "identique_a_1e_12": max(ecarts.values()) < 1e-12}
    etat = [g for g, v in concordance.items() if v["identique_a_1e_12"]]
    etat_retenu = etat[0] if len(etat) == 1 else "AMBIGU"
    print(f"  empreinte assertée dans le script : {hash_asserte} ; seed {seed} ; seuil {seuil}")
    for g, v in concordance.items():
        print(f"    concordance des R² de référence avec la génération {g} "
              f"({v['source']}) : écart max = {v['ecart_max_r2']:.3e} "
              f"-> {'IDENTIQUE' if v['identique_a_1e_12'] else 'différent'}")
    print(f"  => évaluation portée sur l'état : {etat_retenu}")

    date_ajout = date_premier_commit(C1_JSON)
    created_at_embarque = d.get("created_at", None)
    print(f"  date d'exécution embarquée dans la sortie : "
          f"{created_at_embarque if created_at_embarque else INTROUVABLE}")
    print(f"  date du commit d'ajout du JSON (ancrage git) : {date_ajout}")

    # -- table des métriques --
    rows = []
    hdr = ["segment", "metrique", "configuration_retenue", "candidat_best_r2", "delta",
           "n_obs", "n_gt63", "source"]
    METRIQUES = [("r2_global", "R²"), ("mae_global", "MAE"), ("mae_gt63", "MAE>63"),
                 ("bias_gt63", "biais>63"), ("pr_auc_troncon", "PR-AUC tronçon"),
                 ("pr_auc_tour", "PR-AUC tour")]
    valeurs = {}
    for seg in ("bas", "haut", "global"):
        a, b = d["cf09_h25"][seg], d["best_r2_h25"][seg]
        for cle, lib in METRIQUES:
            delta = b[cle] - a[cle]
            valeurs[(seg, cle)] = {"retenue": a[cle], "candidat": b[cle], "delta": delta}
            rows.append([seg, lib, f"{a[cle]:.10f}", f"{b[cle]:.10f}", f"{delta:+.10f}",
                         a["n_obs"], a["n_gt63"], rel(C1_JSON)])
        print(f"  [{seg:6}] R² {a['r2_global']:.4f} -> {b['r2_global']:.4f} "
              f"(Δ{b['r2_global'] - a['r2_global']:+.4f}) | "
              f"biais>63 {a['bias_gt63']:+.2f} -> {b['bias_gt63']:+.2f} "
              f"(Δ{b['bias_gt63'] - a['bias_gt63']:+.2f})")

    # -- contrôle chiffré des deux affirmations du manuscrit --
    d_r2g = valeurs[("global", "r2_global")]["delta"]
    d_bh = valeurs[("haut", "bias_gt63")]["delta"]
    controles = [
        {"affirmation": "gain d'environ quatre millièmes de R² global",
         "grandeur_mesuree": "Δ R² global (candidat − retenue)",
         "valeur": d_r2g, "valeur_arrondie": round(d_r2g, 4),
         "libelle_manuscrit": "+0,004", "source": rel(C1_JSON)},
        {"affirmation": "aggravation d'environ deux voyageurs du biais sur les "
                        "surcharges du segment haut",
         "grandeur_mesuree": "Δ biais>63 segment haut (candidat − retenue)",
         "valeur": d_bh, "valeur_arrondie": round(d_bh, 2),
         "libelle_manuscrit": "−2,04 (biais plus négatif)", "source": rel(C1_JSON)},
    ]
    for c in controles:
        rows.append(["[contrôle]", c["grandeur_mesuree"], "", "", f"{c['valeur']:+.10f}",
                     "", "", c["source"]])
    print(f"  contrôle 1 — Δ R² global = {d_r2g:+.10f} (arrondi {round(d_r2g, 4):+})")
    print(f"  contrôle 2 — Δ biais>63 haut = {d_bh:+.10f} (arrondi {round(d_bh, 2):+})")

    # -- contexte du test --
    for cle, val in [
        ("empreinte assertée par le script", hash_asserte),
        ("état de données de l'évaluation", etat_retenu),
        ("graine", seed), ("seuil de surcharge", seuil),
        ("date d'exécution embarquée", created_at_embarque or INTROUVABLE),
        ("date du commit d'ajout (git)", date_ajout),
        ("garde-fou : la config retenue reproduit les métriques canoniques",
         d.get("garde_fou_cf09_reproduit_canon")),
        ("critère d'adoption", d.get("critere_adoption")),
        ("verdict", d.get("verdict")),
    ]:
        rows.append(["[contexte]", cle, str(val), "", "", "", "", rel(C1_JSON)])

    write_csv("verif_45c_c1_h25_best_r2.csv", hdr, rows)
    return {"empreinte_assertee": hash_asserte, "etat_de_donnees": etat_retenu,
            "concordance_metadata": concordance, "seed": seed, "seuil": seuil,
            "date_execution_embarquee": created_at_embarque or INTROUVABLE,
            "date_commit_ajout": date_ajout,
            "garde_fou_reproduction_canon": d.get("garde_fou_cf09_reproduit_canon"),
            "critere_adoption": d.get("critere_adoption"),
            "degradations_materielles": d.get("degradations_materielles"),
            "verdict": d.get("verdict"),
            "metriques": {f"{s}/{c}": v for (s, c), v in valeurs.items()},
            "controles_manuscrit": controles,
            "sources": {"script": rel(C1_PY), "json": rel(C1_JSON),
                        "rapport": rel(C1_MD) if C1_MD.exists() else INTROUVABLE}}


# ════════════════════════════════════════════════════════════════════════════════
# COMPLÉMENT 2 — résultat de la campagne (a)
# ════════════════════════════════════════════════════════════════════════════════
def complement_2() -> dict:
    print("\n" + "-" * 88)
    print("C2 — campagne (a) : gagnante des 27 par cellule et rang de (6 / 1 / 300 / 0,1)")
    print("-" * 88)
    CLES = ["max_depth", "min_child_weight", "n_estimators", "learning_rate"]
    REFERENCE = {"max_depth": 6, "min_child_weight": 1, "n_estimators": 300,
                 "learning_rate": 0.1}

    code_nb = notebook_code(A_NB)
    seuil_a = scalaire(code_nb, "SEUIL_UM")
    embargo_a = scalaire(code_nb, "EMBARGO")
    beta_a = scalaire(code_nb, "CRITERE_BETA")
    print(f"  seuil de surcharge en vigueur dans la campagne : SEUIL_UM = {seuil_a} "
          f"(embargo {embargo_a} j, critère F-bêta bêta={beta_a})")

    wf = pd.read_csv(A_WF)
    best_json = json.loads(A_BEST.read_text(encoding="utf-8"))
    moy = (wf.groupby(["cellule"] + CLES)["wf_pr_auc_haut"]
             .agg(score_moyen="mean", n_plis="count").reset_index())

    rows = []
    hdr = ["cellule", "role", "rang", "n_combinaisons", "max_depth", "min_child_weight",
           "n_estimators", "learning_rate", "score_moyen_pr_auc_haut", "n_plis",
           "ecart_au_premier", "source"]
    res = {}
    for cell in sorted(moy["cellule"].unique()):
        s = (moy[moy["cellule"] == cell].sort_values("score_moyen", ascending=False)
             .reset_index(drop=True))
        s["rang"] = s.index + 1
        top = s.iloc[0]
        m = ((s["max_depth"] == REFERENCE["max_depth"])
             & (s["min_child_weight"] == REFERENCE["min_child_weight"])
             & (s["n_estimators"] == REFERENCE["n_estimators"])
             & (s["learning_rate"] == REFERENCE["learning_rate"]))
        r = s[m].iloc[0]
        dernier = s.iloc[-1]
        ecart = float(r["score_moyen"] - top["score_moyen"])

        # concordance avec le JSON archivé de la campagne
        j = best_json.get(cell, {})
        concorde = (int(j.get("max_depth", -1)) == int(top["max_depth"])
                    and int(j.get("min_child_weight", -1)) == int(top["min_child_weight"])
                    and int(j.get("n_estimators", -1)) == int(top["n_estimators"])
                    and abs(float(j.get("learning_rate", -1)) - float(top["learning_rate"])) < 1e-12
                    and abs(float(j.get("mean_wf_pr_auc", -1)) - float(top["score_moyen"])) < 1e-9)

        for role, ligne in (("gagnante", top), ("configuration retenue", r),
                            ("dernière", dernier)):
            rows.append([cell, role, int(ligne["rang"]), len(s),
                         int(ligne["max_depth"]), int(ligne["min_child_weight"]),
                         int(ligne["n_estimators"]), float(ligne["learning_rate"]),
                         f"{float(ligne['score_moyen']):.10f}", int(ligne["n_plis"]),
                         f"{float(ligne['score_moyen'] - top['score_moyen']):+.10f}",
                         rel(A_WF)])
        rows.append([cell, "[contrôle] gagnante recalculée = etape_03_best_params.json",
                     "", "", "", "", "", "", "", "", "oui" if concorde else "NON",
                     rel(A_BEST)])

        res[cell] = {
            "n_combinaisons": int(len(s)),
            "gagnante": {k: (int(top[k]) if k != "learning_rate" else float(top[k]))
                         for k in CLES} | {"score_moyen": float(top["score_moyen"])},
            "configuration_retenue": {"rang": int(r["rang"]),
                                      "score_moyen": float(r["score_moyen"]),
                                      "ecart_au_premier": ecart,
                                      "ecart_relatif": ecart / float(top["score_moyen"])},
            "derniere": {k: (int(dernier[k]) if k != "learning_rate" else float(dernier[k]))
                         for k in CLES} | {"score_moyen": float(dernier["score_moyen"]),
                                           "rang": int(dernier["rang"])},
            "concordance_avec_etape_03_best_params": concorde,
        }
        print(f"  {cell:<17} gagnante d={int(top['max_depth'])} "
              f"mcw={int(top['min_child_weight'])} n={int(top['n_estimators'])} "
              f"lr={float(top['learning_rate'])} -> {float(top['score_moyen']):.6f} "
              f"| retenue rang {int(r['rang'])}/{len(s)} score "
              f"{float(r['score_moyen']):.6f} (écart {ecart:+.6f}) "
              f"| concordance JSON : {'oui' if concorde else 'NON'}")

    rows.append(["[protocole]", "seuil de surcharge (SEUIL_UM)", "", "", "", "", "", "",
                 str(seuil_a), "", "", rel(A_NB)])
    rows.append(["[protocole]", "embargo (jours)", "", "", "", "", "", "",
                 str(embargo_a), "", "", rel(A_NB)])
    rows.append(["[protocole]", "critère de calibration du seuil (bêta)", "", "", "", "",
                 "", "", str(beta_a), "", "", rel(A_NB)])
    rows.append(["[protocole]", "lignes du CSV walk-forward", "", "", "", "", "", "",
                 str(len(wf)), "", "", rel(A_WF)])

    write_csv("verif_45c_c2_campagne_a.csv", hdr, rows)
    return {"seuil_surcharge": seuil_a, "embargo_jours": embargo_a, "beta": beta_a,
            "n_lignes_wf": int(len(wf)), "cellules": res,
            "sources": {"csv_walk_forward": rel(A_WF), "json_gagnantes": rel(A_BEST),
                        "notebook": rel(A_NB)}}


# ════════════════════════════════════════════════════════════════════════════════
# COMPLÉMENT 3 — quatrième campagne d'exp_hpo
# ════════════════════════════════════════════════════════════════════════════════
def complement_3() -> dict:
    print("\n" + "-" * 88)
    print("C3 — quatrième campagne d'exp_hpo (cible PR-AUC tronçon globale H24)")
    print("-" * 88)
    code = src(C3_PY)
    tree = ast.parse(code)
    env = module_literals(tree)
    espace_4 = espace_suggest(code, "objective")
    espace_b = espace_suggest(src(SRC_B), "objective")
    res = json.loads(C3_JSON.read_text(encoding="utf-8"))

    direction, sampler, sampler_seed = None, None, None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_study"):
            for kw in node.keywords:
                if kw.arg == "direction":
                    direction = ast.literal_eval(kw.value)
                if kw.arg == "sampler" and isinstance(kw.value, ast.Call):
                    sampler = kw.value.func.attr
                    for k2 in kw.value.keywords:
                        if k2.arg == "seed":
                            sampler_seed = (ast.literal_eval(k2.value)
                                            if isinstance(k2.value, ast.Constant)
                                            else env.get(k2.value.id))
    fixed = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "FIXED" and isinstance(node.value, ast.Call):
                    fixed = {k.arg: (ast.literal_eval(k.value)
                                     if isinstance(k.value, ast.Constant)
                                     else env.get(getattr(k.value, "id", None),
                                                  ast.unparse(k.value)))
                             for k in node.value.keywords}
    trials = pd.read_csv(C3_TRIALS)

    print(f"  objectif : direction={direction} sur « {res.get('cible')} »")
    print(f"  budget : {env.get('N_TRIALS')} essais ; sampler {sampler}(seed={sampler_seed})")
    print(f"  empreinte assertée : {env.get('HASH_ATTENDU')} ; seuil {env.get('SEUIL')}")
    print(f"  lignes du CSV de trials : {len(trials)}")

    # -- confrontation H25 : existe-t-elle ? --
    traces = []
    for p in (C3_TEST_PY, C3_TEST_JSON, C3_TEST_MD):
        traces.append({"fichier": rel(p), "present": p.exists(),
                       "date_commit_ajout": date_premier_commit(p) if p.exists() else None})
    confrontation_existe = all(t["present"] for t in traces[:2])
    print(f"  trace d'une confrontation à H25 : "
          f"{'OUI' if confrontation_existe else 'NON'} -> "
          + ", ".join(t["fichier"].split('/')[-1] for t in traces if t["present"]))

    test = json.loads(C3_TEST_JSON.read_text(encoding="utf-8")) if C3_TEST_JSON.exists() else None

    rows = []
    hdr = ["rubrique", "element", "valeur", "campagne_b_correspondante", "identique",
           "source"]

    # protocole
    for cle, val in [
        ("objectif", f"direction={direction} sur PR-AUC tronçon globale H24 "
                     "(réunion BAS+HAUT au grain tronçon)"),
        ("hyperparamètres partagés BAS/HAUT", "oui (comme la configuration retenue)"),
        ("budget d'essais", f"{env.get('N_TRIALS')} essais, une seule étude "
                            "(pas de dédoublement par segment)"),
        ("graine de l'optimiseur", f"{sampler}(seed={sampler_seed})"),
        ("schéma de validation", "hold-out temporel unique : train = H22 hors Gilamont "
                                 "(BPUIC 8501260) + H23 → validation = H24 ; "
                                 "pas de validation croisée ; H25 non chargé au tuning"),
        ("empreinte du jeu de données", str(env.get("HASH_ATTENDU"))),
        ("seuil de surcharge", str(env.get("SEUIL"))),
        ("paramètres figés hors espace", json.dumps(fixed, ensure_ascii=False)),
        ("garde-fou in-protocole", json.dumps(res.get("garde_fou"), ensure_ascii=False)),
        ("date d'exécution embarquée", res.get("created_at") or INTROUVABLE),
        ("date du commit d'ajout du JSON (git)", date_premier_commit(C3_JSON)),
        ("lignes du CSV de trials", str(len(trials))),
    ]:
        rows.append(["protocole", cle, val, "", "", rel(C3_PY)])

    # espace, paramètre par paramètre vs campagne (b)
    tous = sorted(set(espace_4) | set(espace_b))
    identiques, differents = [], []
    for hp in tous:
        a4, ab = espace_4.get(hp), espace_b.get(hp)
        d4 = ("absent" if a4 is None
              else f"{a4['type']}, {a4['loi']}, [{a4['borne_min']} ; {a4['borne_max']}]")
        db = ("absent" if ab is None
              else f"{ab['type']}, {ab['loi']}, [{ab['borne_min']} ; {ab['borne_max']}]")
        ident = (a4 == ab)
        (identiques if ident else differents).append(hp)
        rows.append(["espace de recherche", hp, d4, db, "oui" if ident else "non",
                     f"{rel(C3_PY)} vs {rel(SRC_B)}"])
    print(f"  espace vs campagne (b) : {len(identiques)}/{len(tous)} paramètres "
          f"identiques ; différents : {differents if differents else 'aucun'}")

    # configuration gagnante
    best = res["best"]
    for hp, v in best["hp"].items():
        rows.append(["configuration gagnante", hp, f"{v}", "", "", rel(C3_JSON)])
    rows.append(["configuration gagnante", "numéro d'essai", str(best["trial"]), "", "",
                 rel(C3_JSON)])
    for cle in ("pr_auc_troncon_global", "pr_auc_tour_global", "r2_global",
                "bias_gt63_global", "pr_auc_troncon_bas", "pr_auc_troncon_haut"):
        rows.append(["validation H24 — gagnante", cle, f"{best[cle]:.10f}",
                     f"{res['cf09'][cle]:.10f}",
                     f"{best[cle] - res['cf09'][cle]:+.10f}", rel(C3_JSON)])
    rows.append(["validation H24 — gagnante", "gain sur l'objectif vs config retenue",
                 f"{res['gain_vs_cf09']:.10f}", "", "", rel(C3_JSON)])
    print(f"  gagnante : essai {best['trial']} ; PR-AUC tronçon globale H24 "
          f"{best['pr_auc_troncon_global']:.4f} vs {res['cf09']['pr_auc_troncon_global']:.4f} "
          f"(gain {res['gain_vs_cf09']:+.4f})")

    # confrontation H25
    for t in traces:
        rows.append(["confrontation H25", f"fichier {t['fichier'].split('/')[-1]}",
                     "présent" if t["present"] else INTROUVABLE, "",
                     t["date_commit_ajout"] or "", t["fichier"]])
    if test:
        for seg in ("bas", "haut", "global"):
            a, b = test["cf09_h25"][seg], test["candidat_h25"][seg]
            for cle in ("r2", "mae_global", "mae_gt63", "bias_gt63", "pr_auc_troncon",
                        "pr_auc_tour"):
                rows.append([f"confrontation H25 — {seg}", cle, f"{b[cle]:.10f}",
                             f"{a[cle]:.10f}", f"{b[cle] - a[cle]:+.10f}",
                             rel(C3_TEST_JSON)])
        for cle in ("critere", "verdict"):
            rows.append(["confrontation H25", cle,
                         json.dumps(test.get(cle), ensure_ascii=False), "", "",
                         rel(C3_TEST_JSON)])
        code_test = src(C3_TEST_PY)
        rows.append(["confrontation H25", "empreinte assertée par le script de test",
                     str(scalaire(code_test, "HASH_ATTENDU")), "", "", rel(C3_TEST_PY)])
        rows.append(["confrontation H25", "date d'exécution embarquée",
                     test.get("created_at") or INTROUVABLE, "", "", rel(C3_TEST_JSON)])
        print(f"  confrontation H25 : verdict « {test.get('verdict')} »")

    write_csv("verif_45c_c3_campagne_prauc.csv", hdr, rows)
    return {"objectif": {"direction": direction, "cible": res.get("cible")},
            "budget": env.get("N_TRIALS"), "sampler": sampler, "seed": sampler_seed,
            "empreinte_assertee": env.get("HASH_ATTENDU"), "seuil": env.get("SEUIL"),
            "parametres_figes": fixed, "garde_fou": res.get("garde_fou"),
            "date_execution_embarquee": res.get("created_at") or INTROUVABLE,
            "date_commit_ajout": date_premier_commit(C3_JSON),
            "espace": espace_4,
            "comparaison_espace_campagne_b": {"identiques": identiques,
                                              "differents": differents,
                                              "n_total": len(tous)},
            "gagnante": best, "reference_h24": res["cf09"],
            "gain_objectif": res["gain_vs_cf09"],
            "confrontation_h25": {"existe": confrontation_existe, "traces": traces,
                                  "verdict": test.get("verdict") if test else None,
                                  "critere": test.get("critere") if test else None,
                                  "empreinte_assertee": scalaire(src(C3_TEST_PY),
                                                                 "HASH_ATTENDU")
                                  if C3_TEST_PY.exists() else INTROUVABLE,
                                  "resultats": {s: {"retenue": test["cf09_h25"][s],
                                                    "candidat": test["candidat_h25"][s]}
                                                for s in ("bas", "haut", "global")}
                                  if test else None}}


# ════════════════════════════════════════════════════════════════════════════════
# COMPLÉMENT 4 — désambiguïsation de l'empreinte 416bb90b
# ════════════════════════════════════════════════════════════════════════════════
def complement_4() -> dict:
    print("\n" + "-" * 88)
    print(f"C4 — désambiguïsation de l'empreinte tronquée {EMPREINTE}")
    print("-" * 88)
    rows = []
    hdr = ["categorie", "chemin_ou_reference", "ce_que_l_empreinte_designe",
           "empreinte_propre_du_fichier", "adr_de_rattachement", "detail"]

    # -- 4.1 hachage exhaustif : un artefact porte-t-il cette empreinte ? --
    porteurs, n_fichiers = [], 0
    empreintes_connues = {EMPREINTE, "ba493568", "e4ddfccd", "df6a11c5"}
    par_empreinte = {}
    for racine in RACINES_HACHAGE:
        p = ROOT / racine
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if not f.is_file() or any(x in f.parts for x in EXCLUS_HACHAGE):
                continue
            if f.parent == OUT:      # les sorties de cette vérification sont hors balayage
                continue
            try:
                h = sha256_full(f)[:8]
            except OSError:
                continue
            n_fichiers += 1
            if h in empreintes_connues:
                par_empreinte.setdefault(h, []).append(rel(f))
            if h == EMPREINTE:
                porteurs.append(rel(f))
    print(f"  hachage exhaustif : {n_fichiers} fichiers balayés")
    print(f"  fichiers dont SHA256[:8] == {EMPREINTE} : "
          f"{porteurs if porteurs else 'AUCUN'}")
    rows.append(["empreinte propre",
                 f"balayage de {n_fichiers} fichiers ({', '.join(RACINES_HACHAGE)})",
                 f"aucun fichier du dépôt ne porte {EMPREINTE} comme empreinte propre"
                 if not porteurs else "; ".join(porteurs),
                 "", "ADR-066",
                 "le parquet v1.9 lui-même est absent du poste : data/processed ne "
                 "contient que l'état courant"])
    for h in sorted(par_empreinte):
        for f in par_empreinte[h]:
            rows.append(["empreinte propre observée", f, f"SHA256[:8] = {h}", h,
                         "ADR-076" if h != EMPREINTE else "ADR-066", ""])

    # -- 4.2 objet désigné, d'après les métadonnées versionnées --
    m19 = json.loads(META_V19.read_text(encoding="utf-8"))
    mcur = json.loads(META_COURANT.read_text(encoding="utf-8"))
    rows.append(["objet désigné", rel(META_V19),
                 f"{EMPREINTE} = SHA256[:8] de {m19['dataset']['file']} dans son état "
                 f"v{m19['version']} (créé le {m19.get('created_at')})",
                 "", "ADR-066 (convention), ADR-076 (supersession)",
                 f"n_features={m19['dataset']['n_features']} ; "
                 f"reproductible : {m19['dataset']['reproductible']}"])
    rows.append(["objet désigné", rel(META_COURANT),
                 f"génération courante = {mcur['dataset']['hash_sha256_8']} "
                 f"(v{mcur['version']}), supersède v1.9 = "
                 f"{mcur.get('supersedes', {}).get('v1.9')}",
                 "", "ADR-076", "le parquet v1.9 n'existe plus sur disque"])
    print(f"  objet désigné : SHA256[:8] du parquet ml_dataset dans son état v1.9 "
          f"(métadonnées créées le {m19.get('created_at')}), supersédé par "
          f"{mcur['dataset']['hash_sha256_8']}")

    # -- 4.3 les deux modèles v1.9 et courants sont-ils le même octet ? --
    for seg in ("bas", "haut"):
        f19 = MODEL_DIR / f"enrichi_seg_{seg}_{EMPREINTE}.json"
        fcur = MODEL_DIR / f"enrichi_seg_{seg}_{HASH_DATASET_8}.json"
        if f19.exists() and fcur.exists():
            h19, hcur = sha8(f19), sha8(fcur)
            rows.append(["artefact suffixé", rel(f19),
                         f"le suffixe {EMPREINTE} nomme la GÉNÉRATION de données, "
                         f"pas l'empreinte du fichier",
                         h19, "ADR-076",
                         f"byte-identique à {rel(fcur)} : "
                         f"{'oui' if h19 == hcur else 'NON'} (empreinte propre {h19})"])
            print(f"  modèle {seg:<4} : {rel(f19)} et {rel(fcur)} — "
                  f"byte-identiques : {'oui' if h19 == hcur else 'NON'} "
                  f"(empreinte propre {h19})")

    # -- 4.4 recensement des occurrences dans le dépôt --
    occurrences = {"suffixe_nom_de_fichier": [], "constante_de_garde": [],
                   "champ_de_metadonnees": [], "prose_ou_commentaire": []}
    for racine in RACINES_HACHAGE + ["."]:
        p = ROOT / racine
        if not p.exists():
            continue
        for f in sorted(p.rglob("*") if racine != "." else p.glob("*")):
            if not f.is_file() or any(x in f.parts for x in EXCLUS_HACHAGE):
                continue
            if f.parent == OUT:      # les sorties de cette vérification sont hors recensement
                continue
            if EMPREINTE in f.name:
                occurrences["suffixe_nom_de_fichier"].append(rel(f))
    occurrences["suffixe_nom_de_fichier"] = sorted(set(occurrences["suffixe_nom_de_fichier"]))

    grep = git("grep", "-l", EMPREINTE, "--", ":!docs/memoire/verifs")
    fichiers_texte = sorted(set(grep.splitlines())) if grep else []
    for rf in fichiers_texte:
        f = ROOT / rf
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf'HASH_ATTENDU\s*[,=][^\n]*{EMPREINTE}', texte) or \
           re.search(rf'HASH_ATTENDU[^\n]*=\s*"{EMPREINTE}"', texte):
            occurrences["constante_de_garde"].append(rf)
        if re.search(rf'"(hash|dataset_hash|hash_sha256_8)"\s*:\s*"{EMPREINTE}"', texte):
            occurrences["champ_de_metadonnees"].append(rf)
        if rf.endswith(".md") or rf.endswith("CONTEXT.md") or rf.endswith("README.md"):
            occurrences["prose_ou_commentaire"].append(rf)
    for k in occurrences:
        occurrences[k] = sorted(set(occurrences[k]))
        for rf in occurrences[k]:
            f = ROOT / rf
            prop = sha8(f) if f.exists() and f.is_file() else ""
            rows.append([k, rf,
                         f"génération de données v1.9 du parquet ml_dataset "
                         f"(SHA256[:8] = {EMPREINTE})", prop,
                         "ADR-066 / ADR-076", ""])
        print(f"  occurrences [{k}] : {len(occurrences[k])}")

    # -- 4.5 côté couche décisionnelle : que déclarent les sorties suffixées ? --
    couche2 = sorted((ROOT / "outputs/couche2").glob(f"*{EMPREINTE}*")) \
        if (ROOT / "outputs/couche2").exists() else []
    c2_detail = []
    for f in couche2:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            d = {}
        declare = (d.get("meta") or {}).get("hash") if isinstance(d.get("meta"), dict) else None
        c2_detail.append({"fichier": rel(f), "meta_hash_declare": declare or INTROUVABLE,
                          "empreinte_propre": sha8(f)})
        rows.append(["couche décisionnelle", rel(f),
                     f"suffixe = génération de données ; champ meta.hash déclaré = "
                     f"{declare or 'absent'}", sha8(f), "ADR-073 / ADR-077",
                     "artefact distinct du parquet ; l'empreinte y nomme la génération "
                     "dont il est issu, pas le fichier lui-même"])
        print(f"  couche 2 : {rel(f)} — meta.hash déclaré = {declare or 'absent'} ; "
              f"empreinte propre {sha8(f)}")

    write_csv("verif_45c_c4_empreinte_416bb90b.csv", hdr, rows)
    return {"empreinte": EMPREINTE,
            "objet_designe": {
                "nature": "SHA256[:8] du fichier data/processed/ml_dataset.parquet",
                "etat": f"version v{m19['version']} du dataset, métadonnées créées le "
                        f"{m19.get('created_at')}",
                "supersede_par": mcur["dataset"]["hash_sha256_8"],
                "adr": ["ADR-066 (convention de hachage)", "ADR-076 (gel v2, supersession)"],
                "present_sur_disque": bool(porteurs)},
            "hachage_exhaustif": {"n_fichiers": n_fichiers,
                                  "porteurs_de_l_empreinte": porteurs,
                                  "par_empreinte_connue": par_empreinte},
            "occurrences": occurrences,
            "couche_decisionnelle": c2_detail,
            "artefact_distinct_portant_la_meme_empreinte":
                porteurs if porteurs else "aucun"}


# ════════════════════════════════════════════════════════════════════════════════
def main() -> int:
    prov = preambule()
    c1 = complement_1()
    c2 = complement_2()
    c3 = complement_3()
    c4 = complement_4()

    manquants = []
    if c1["date_execution_embarquee"] == INTROUVABLE:
        manquants.append(
            "C1 — date d'exécution du test H25 best-R² : aucune sortie ne l'embarque "
            "(test_h25_best_r2_vs_cf09.json n'a pas de champ created_at, aucun journal "
            "d'exécution n'accompagne ce test). Seuls ancrages : la date de décision "
            "d'ADR-071 et la date du commit d'ajout des fichiers.")
    if c3["date_execution_embarquee"] == INTROUVABLE:
        manquants.append(
            "C3 — date d'exécution de la quatrième campagne : aucune sortie ne "
            "l'embarque (ni le JSON de résultats, ni le CSV de trials).")
    manquants.append(
        "C2 — empreinte du jeu de données de la campagne (a) : absente (aucun garde-fou "
        "de hachage dans le notebook, aucune trace dans ses sorties).")
    if not c4["hachage_exhaustif"]["porteurs_de_l_empreinte"]:
        manquants.append(
            f"C4 — le parquet portant l'empreinte {EMPREINTE} est absent du poste : "
            "data/processed ne contient que l'état courant. L'empreinte n'est donc pas "
            "revérifiable par recalcul, seulement attestée par les métadonnées "
            "versionnées et les ADR.")

    print("\n" + "-" * 88)
    print("INFORMATIONS ABSENTES DU DÉPÔT (non reconstituées)")
    print("-" * 88)
    for m in manquants:
        print("  - " + m)

    p = OUT / "verif_45_complements_synthese.json"
    p.write_text(json.dumps({"provenance": prov, "c1": c1, "c2": c2, "c3": c3, "c4": c4,
                             "informations_introuvables": manquants},
                            indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  -> {rel(p)}")
    print("\nTERMINÉ — lecture seule, aucun artefact canonique modifié.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
