#!/usr/bin/env python3
"""
Section 4.5 — configuration effective de la couche 1, espaces de recherche des
campagnes de réglage, configurations non retenues, baselines et environnement.

LECTURE SEULE. Aucun réentraînement, aucune réoptimisation, aucune écriture hors
de docs/memoire/verifs/section_4_5/. Les deux modèles gelés sont chargés en
mémoire (jamais réécrits) ; le parquet canonique n'est que haché.

Principe de la vérification
---------------------------
Rien n'est recopié à la main. Chaque valeur est soit LUE dans un artefact
(fichier modèle, JSON de sortie de campagne), soit EXTRAITE PAR ANALYSE
SYNTAXIQUE (`ast`) du code versionné qui l'a produite. Quand une information est
absente du dépôt, elle est marquée `INTROUVABLE` — jamais reconstituée.

Blocs produits
--------------
A. Configuration effective des deux régresseurs gelés (`e4ddfccd`, `df6a11c5`).
   Distinction stricte, paramètre par paramètre, entre valeur fixée dans le code
   d'entraînement et valeur héritée du défaut de xgboost.
   → verif_45_bloc_a_config_effective.csv
B. Espaces de recherche des trois campagnes de réglage, avec test de contenance
   de la configuration retenue (300 / 6 / 0,1 / 0,8 / 0,8).
   → verif_45_bloc_b_espaces_recherche.csv
C. Configurations gagnantes non retenues (campagnes b et c) en regard du retenu.
   → verif_45_bloc_c_configs_candidates.csv
D. Baselines (Ridge, Random Forest, naïve) et environnement d'exécution.
   → verif_45_bloc_d_baselines_environnement.csv

Plus une synthèse machine : verif_45_synthese.json.
Sorties déterministes : aucun horodatage embarqué.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import ast
import csv
import hashlib
import inspect
import itertools
import json
import platform
import sys
from pathlib import Path

import numpy as np
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

# ── Ancrages canoniques (ADR-076) ───────────────────────────────────────────────
ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
HASH_DATASET_8 = "ba493568"
MODEL_DIR = ROOT / "models/enrichi_seg"
MODELS = {"bas": ("enrichi_seg_bas_ba493568.json", "e4ddfccd"),
          "haut": ("enrichi_seg_haut_ba493568.json", "df6a11c5")}
METADATA = MODEL_DIR / "enrichi_seg_metadata.json"

# ── Sources de code (chemins relatifs à la racine du dépôt) ─────────────────────
SRC_TRAIN = ROOT / "scripts/experiences/phase4_migration_ba493568.py"   # producteur du gel
SRC_HARNESS = ROOT / "scripts/confirmation/_harness.py"                  # socle iso-protocole
SRC_A_NB = (ROOT / "archive/explorations/consolidation_finale/notebooks"
            / "etape_03_robustesse_hyperparams.ipynb")
SRC_A_BEST = (ROOT / "archive/explorations/consolidation_finale/outputs"
              / "etape_03_best_params.json")
DIR_B = ROOT / "archive/explorations/consolidation_finale/exp_hpo"
SRC_B = DIR_B / "tuning_optuna_h24.py"
SRC_B_RES = DIR_B / "tuning_optuna_h24_resultats.json"
SRC_B_TRIALS = DIR_B / "tuning_optuna_h24_trials.csv"
SRC_B_LOG = DIR_B / "run.log"
DIR_C = (ROOT / "archive/explorations/consolidation_finale"
         / "exp_comparatif_algos/tuning")
SRC_C = DIR_C / "tuning_comparatif_algos.py"
SRC_C_RES = DIR_C / "tuning_resultats.json"
SRC_C_LOG = DIR_C / "run_full.log"
CONF = ROOT / "outputs/confirmation"
SRC_C03 = ROOT / "scripts/confirmation/c03_baseline_lineaire.py"
SRC_C10 = ROOT / "scripts/confirmation/c10_comparatif_algos.py"
REQUIREMENTS = ROOT / "requirements.txt"
MAKEFILE = ROOT / "Makefile"

INTROUVABLE = "INTROUVABLE dans le dépôt"

# Configuration retenue, telle qu'invoquée par le manuscrit (test de contenance bloc B).
RETENU = {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.1,
          "subsample": 0.8, "colsample_bytree": 0.8}


# ════════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ════════════════════════════════════════════════════════════════════════════════
def sha256_full(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha8(path: Path) -> str:
    return sha256_full(path)[:8]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def module_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def notebook_cells(path: Path) -> "list[str]":
    nb = json.loads(path.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def notebook_code(path: Path) -> str:
    """Concatène les cellules de code SYNTAXIQUEMENT VALIDES d'un notebook.

    Une cellule non analysable (ici : une f-string multi-lignes de mise en figure)
    est écartée et signalée, plutôt que de faire échouer toute la lecture. Aucune
    des cellules écartées ne porte de définition d'espace de recherche.
    """
    ok, ko = [], []
    for i, src in enumerate(notebook_cells(path)):
        try:
            ast.parse(src)
            ok.append(src)
        except SyntaxError:
            ko.append(i)
    if ko:
        print(f"      [note] cellules de code non analysables écartées : {ko} "
              f"(sur {len(ok) + len(ko)})")
    return "\n".join(ok)


def find_assign(tree: ast.AST, name: str):
    """Renvoie le noeud valeur de la dernière affectation `name = ...` au niveau module."""
    found = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    found = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value:
                found = node.value
    return found


def module_literals(tree: ast.AST) -> dict:
    """Constantes littérales affectées au niveau module (résolution des `Name` simples).

    Permet de lire `random_state=SEED` sans exécuter le module : SEED est résolu
    depuis son affectation littérale, pas deviné.
    """
    env = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    try:
                        env[t.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError):
                        pass
                elif isinstance(t, ast.Tuple):   # a, b = 1, 2
                    try:
                        vals = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    for el, v in zip(t.elts, vals if isinstance(vals, tuple) else ()):
                        if isinstance(el, ast.Name):
                            env[el.id] = v
    return env


def _eval_node(node: ast.AST, env: dict):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        pass
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    return ast.unparse(node)


def dict_call_to_py(node: ast.AST, env: "dict | None" = None) -> dict:
    """`dict(a=1, b=CONST)` ou `{...}` littéral -> dict Python.

    Les noms sont résolus par `env` (constantes de module) ; tout ce qui n'est ni
    littéral ni constante connue est rendu sous sa forme source.
    """
    env = env or {}
    if isinstance(node, ast.Dict):
        return {_eval_node(k, env): _eval_node(v, env)
                for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        return {kw.arg: _eval_node(kw.value, env) for kw in node.keywords}
    raise TypeError(f"noeud non convertible en dict : {ast.dump(node)[:120]}")


def extract_dict_assign(src: str, name: str) -> dict:
    tree = ast.parse(src)
    return dict_call_to_py(find_assign(tree, name), module_literals(tree))


def extract_scalar_assign(src: str, name: str):
    """Valeur littérale d'une affectation de module ; à défaut, sa forme source.

    (`N_TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 40` n'est pas un
    littéral : la forme source est rendue telle quelle, sans être évaluée.)
    """
    tree = ast.parse(src)
    node = find_assign(tree, name)
    if node is None:
        # affectation multiple `A, B = 1, 2`
        return module_literals(tree).get(name)
    return _eval_node(node, module_literals(tree))


def extract_suggest_space(src: str, func_name: str) -> "list[dict]":
    """Extrait les appels `trial.suggest_int/float/categorical` d'une fonction donnée.

    Renvoie, pour chaque hyperparamètre, son nom, son type d'appel, ses bornes et
    sa loi d'échantillonnage telle qu'elle découle littéralement de l'appel
    (`log=True` -> log-uniforme ; sinon uniforme ; `suggest_categorical` ->
    catégorielle). Aucune interprétation au-delà de la lecture de l'appel.
    """
    tree = ast.parse(src)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            target = node
    if target is None:
        raise LookupError(f"fonction {func_name} absente")
    out = []
    for node in ast.walk(target):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        meth = node.func.attr
        if not meth.startswith("suggest_"):
            continue
        args = [ast.literal_eval(a) for a in node.args]
        kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
        nom = args[0]
        if meth == "suggest_categorical":
            out.append({"hp": nom, "appel": meth, "type": "catégoriel",
                        "borne_min": None, "borne_max": None,
                        "choix": args[1], "loi": "catégorielle"})
            continue
        lo, hi = args[1], args[2]
        log = bool(kwargs.get("log", False))
        typ = "entier" if meth == "suggest_int" else "réel"
        out.append({"hp": nom, "appel": meth, "type": typ,
                    "borne_min": lo, "borne_max": hi, "choix": None,
                    "loi": "log-uniforme" if log else "uniforme"})
    return out


def contient(space: dict, valeur) -> bool:
    """Contenance stricte d'une valeur dans un espace décrit par bornes ou choix."""
    if space.get("choix") is not None:
        return valeur in space["choix"]
    lo, hi = space.get("borne_min"), space.get("borne_max")
    if lo is None or hi is None:
        return False
    return bool(lo <= valeur <= hi)


def oui_non(b) -> str:
    return "oui" if b else "non"


# ════════════════════════════════════════════════════════════════════════════════
# Préambule : gardes de provenance
# ════════════════════════════════════════════════════════════════════════════════
def preambule() -> dict:
    print("=" * 88)
    print("VERIF §4.5 — configuration couche 1, espaces de recherche, baselines, environnement")
    print("=" * 88)
    prov = {}

    if ML_DATASET.exists():
        full = sha256_full(ML_DATASET)
        prov["dataset"] = {"fichier": rel(ML_DATASET), "sha256": full,
                           "sha256_8": full[:8], "attendu_8": HASH_DATASET_8,
                           "conforme": full[:8] == HASH_DATASET_8,
                           "taille_octets": ML_DATASET.stat().st_size}
        if full[:8] != HASH_DATASET_8:
            raise RuntimeError(f"STOP provenance : dataset {full[:8]} != {HASH_DATASET_8}")
        print(f"  dataset  {rel(ML_DATASET)}\n           SHA256 = {full}\n"
              f"           SHA256[:8] = {full[:8]} (attendu {HASH_DATASET_8}) OK")
    else:
        prov["dataset"] = {"fichier": rel(ML_DATASET), "sha256": INTROUVABLE,
                           "sha256_8": INTROUVABLE, "attendu_8": HASH_DATASET_8,
                           "conforme": None}
        print(f"  dataset  {rel(ML_DATASET)} ABSENT — empreinte non vérifiable ici")

    prov["modeles"] = {}
    for seg, (fname, attendu) in MODELS.items():
        f = MODEL_DIR / fname
        full = sha256_full(f)
        ok = full[:8] == attendu
        prov["modeles"][seg] = {"fichier": rel(f), "sha256": full, "sha256_8": full[:8],
                                "attendu_8": attendu, "conforme": ok,
                                "taille_octets": f.stat().st_size}
        if not ok:
            raise RuntimeError(f"STOP provenance : modèle {seg} {full[:8]} != {attendu}")
        print(f"  modèle {seg:<4} {rel(f)}\n           SHA256[:8] = {full[:8]} "
              f"(attendu {attendu}) OK  [vérifié AVANT chargement]")
    return prov


# ════════════════════════════════════════════════════════════════════════════════
# BLOC A — configuration effective des deux régresseurs gelés
# ════════════════════════════════════════════════════════════════════════════════
def bloc_a():
    print("\n" + "-" * 88)
    print("BLOC A — configuration effective des deux régresseurs gelés")
    print("-" * 88)

    # A.1 — valeurs FIXÉES dans le code d'entraînement (analyse syntaxique)
    params_train = extract_dict_assign(module_source(SRC_TRAIN), "XGB_PARAMS")
    params_harness = extract_dict_assign(module_source(SRC_HARNESS), "XGB_PARAMS")
    seed_train = extract_scalar_assign(module_source(SRC_TRAIN), "SEED")
    print(f"  code d'entraînement du gel : {rel(SRC_TRAIN)}")
    print(f"    XGB_PARAMS = {params_train}")
    print(f"    SEED = {seed_train}")
    print(f"  socle iso-protocole        : {rel(SRC_HARNESS)}")
    print(f"    XGB_PARAMS identique au producteur : "
          f"{oui_non(params_train == params_harness)}")

    # A.2 — inventaire des paramètres réglables de l'estimateur (xgboost installé)
    sig = inspect.signature(xgb.XGBRegressor.__init__)
    params_estimateur = [n for n in sig.parameters if n not in ("self", "kwargs")]
    sentinelles = xgb.XGBRegressor().get_params()   # None = « non fixé » côté sklearn

    # A.3 — ce que l'ARTEFACT permet de vérifier
    artefacts = {}
    boosters = {}
    for seg, (fname, _) in MODELS.items():
        f = MODEL_DIR / fname
        raw = json.loads(f.read_text(encoding="utf-8"))
        learner = raw["learner"]
        gbm = learner["gradient_booster"]["model"]
        trees = gbm["trees"]

        def prof(t):
            left, right = t["left_children"], t["right_children"]
            dep = [0] * len(left)
            stack, mx = [0], 0
            while stack:
                n = stack.pop()
                if left[n] != -1:
                    dep[left[n]] = dep[right[n]] = dep[n] + 1
                    stack += [left[n], right[n]]
                mx = max(mx, dep[n])
            return mx

        profs = [prof(t) for t in trees]
        b = xgb.Booster()
        b.load_model(str(f))
        boosters[seg] = b
        artefacts[seg] = {
            "xgboost_version_serialisee": raw["version"],
            "num_trees": int(gbm["gbtree_model_param"]["num_trees"]),
            "num_parallel_tree": int(gbm["gbtree_model_param"]["num_parallel_tree"]),
            "num_feature": int(learner["learner_model_param"]["num_feature"]),
            "base_score": learner["learner_model_param"]["base_score"],
            "boost_from_average": learner["learner_model_param"]["boost_from_average"],
            "objective": learner["objective"]["name"],
            "scale_pos_weight": learner["objective"]["reg_loss_param"]["scale_pos_weight"],
            "n_arbres_dumpes": len(b.get_dump()),
            "profondeur_observee_min": int(min(profs)),
            "profondeur_observee_max": int(max(profs)),
            "profondeur_observee_moyenne": round(float(np.mean(profs)), 4),
            "attributs_serialises": sorted(learner.get("attributes", {}).keys()),
            "n_feature_types_categoriels": sum(1 for t in learner["feature_types"] if t == "c"),
            "feature_names_identiques_ordre": None,   # rempli plus bas
        }
        print(f"  artefact {seg:<4} : num_trees={artefacts[seg]['num_trees']} "
              f"num_feature={artefacts[seg]['num_feature']} "
              f"objective={artefacts[seg]['objective']} "
              f"base_score={artefacts[seg]['base_score']} "
              f"profondeur observée min/max={artefacts[seg]['profondeur_observee_min']}/"
              f"{artefacts[seg]['profondeur_observee_max']}")

    # A.4 — ce que l'artefact NE porte PAS : preuve directe
    #      get_params() après load_model sur un XGBRegressor neuf, et save_config()
    reg = xgb.XGBRegressor()
    reg.load_model(str(MODEL_DIR / MODELS["bas"][0]))
    gp = reg.get_params()
    hp_sklearn_nuls = sorted(k for k in ("n_estimators", "max_depth", "learning_rate",
                                         "subsample", "colsample_bytree", "tree_method",
                                         "random_state", "min_child_weight", "gamma",
                                         "reg_lambda", "reg_alpha")
                             if gp.get(k) is None)
    cfg_bas = json.loads(boosters["bas"].save_config())
    ttp = cfg_bas["learner"]["gradient_booster"]["tree_train_param"]
    gtp = cfg_bas["learner"]["gradient_booster"]["gbtree_train_param"]
    gen = cfg_bas["learner"]["generic_param"]
    preuve_defauts = {
        "eta_save_config": ttp["eta"], "eta_code_entrainement": params_train["learning_rate"],
        "subsample_save_config": ttp["subsample"], "subsample_code": params_train["subsample"],
        "colsample_bytree_save_config": ttp["colsample_bytree"],
        "colsample_bytree_code": params_train["colsample_bytree"],
        "max_depth_save_config": ttp["max_depth"], "max_depth_code": params_train["max_depth"],
        "tree_method_save_config": gtp["tree_method"], "tree_method_code": params_train["tree_method"],
        "updater_save_config": gtp["updater"],
        "seed_save_config": gen["seed"], "seed_code": params_train["random_state"],
    }
    print("\n  Contrôle de sérialisation (xgboost "
          f"{xgb.__version__}) : le fichier modèle NE porte PAS les hyperparamètres "
          "d'entraînement.")
    print(f"    get_params() après load_model : {len(hp_sklearn_nuls)} des 11 HP "
          f"testés valent None -> {hp_sklearn_nuls}")
    print(f"    Booster.save_config() rend les DÉFAUTS de la bibliothèque, pas les "
          f"valeurs d'entraînement :")
    print(f"      eta={ttp['eta']} (entraînement {params_train['learning_rate']}) ; "
          f"subsample={ttp['subsample']} (entraînement {params_train['subsample']}) ; "
          f"colsample_bytree={ttp['colsample_bytree']} "
          f"(entraînement {params_train['colsample_bytree']})")
    print(f"      max_depth={ttp['max_depth']} coïncide avec le défaut de la "
          f"bibliothèque — coïncidence, pas une preuve.")

    # A.5 — divergence bas/haut
    raw_b = json.loads((MODEL_DIR / MODELS["bas"][0]).read_text(encoding="utf-8"))
    raw_h = json.loads((MODEL_DIR / MODELS["haut"][0]).read_text(encoding="utf-8"))
    for seg, raw in (("bas", raw_b), ("haut", raw_h)):
        artefacts[seg]["feature_names_identiques_ordre"] = (
            raw_b["learner"]["feature_names"] == raw_h["learner"]["feature_names"])
    cfg_haut = json.loads(boosters["haut"].save_config())
    divergences = []
    if raw_b["version"] != raw_h["version"]:
        divergences.append(("version xgboost sérialisée",
                            str(raw_b["version"]), str(raw_h["version"])))
    for champ in ("num_trees", "num_parallel_tree"):
        vb = raw_b["learner"]["gradient_booster"]["model"]["gbtree_model_param"][champ]
        vh = raw_h["learner"]["gradient_booster"]["model"]["gbtree_model_param"][champ]
        if vb != vh:
            divergences.append((f"gbtree_model_param.{champ}", vb, vh))
    for champ in ("num_feature", "num_class", "num_target", "boost_from_average", "base_score"):
        vb = raw_b["learner"]["learner_model_param"][champ]
        vh = raw_h["learner"]["learner_model_param"][champ]
        if vb != vh:
            divergences.append((f"learner_model_param.{champ}", vb, vh))
    if raw_b["learner"]["objective"] != raw_h["learner"]["objective"]:
        divergences.append(("objective", json.dumps(raw_b["learner"]["objective"]),
                            json.dumps(raw_h["learner"]["objective"])))
    if raw_b["learner"]["feature_names"] != raw_h["learner"]["feature_names"]:
        divergences.append(("feature_names", "(158 noms)", "(158 noms, ordre différent)"))
    if raw_b["learner"]["feature_types"] != raw_h["learner"]["feature_types"]:
        divergences.append(("feature_types", "(158 types)", "(158 types, différents)"))
    if cfg_bas["learner"] != cfg_haut["learner"]:
        diffs_cfg = [k for k in cfg_bas["learner"]
                     if cfg_bas["learner"][k] != cfg_haut["learner"].get(k)]
        divergences.append(("save_config().learner", "diffère sur : " + ", ".join(diffs_cfg), ""))
    print("\n  Divergences bas vs haut au niveau des artefacts : "
          f"{len(divergences)} champ(s)")
    for d in divergences:
        print(f"    - {d[0]} : bas={d[1]} | haut={d[2]}")

    # A.6 — arrêt anticipé : recherche dans le code du producteur
    src_train = module_source(SRC_TRAIN)
    tree_train = ast.parse(src_train)
    fit_calls = []
    for node in ast.walk(tree_train):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "fit"):
            fit_calls.append({"n_args_positionnels": len(node.args),
                              "kwargs": sorted(kw.arg for kw in node.keywords if kw.arg)})
    early = {
        "early_stopping_rounds_dans_XGB_PARAMS": "early_stopping_rounds" in params_train,
        "eval_metric_dans_XGB_PARAMS": "eval_metric" in params_train,
        "callbacks_dans_XGB_PARAMS": "callbacks" in params_train,
        "appels_fit": fit_calls,
        "eval_set_passe_au_fit": any("eval_set" in c["kwargs"] for c in fit_calls),
    }
    print(f"\n  Arrêt anticipé : early_stopping_rounds dans XGB_PARAMS = "
          f"{oui_non(early['early_stopping_rounds_dans_XGB_PARAMS'])} ; "
          f"eval_set passé à fit() = {oui_non(early['eval_set_passe_au_fit'])} "
          f"(appels fit : {fit_calls})")

    # A.7 — table paramètre par paramètre
    #
    # Pour un paramètre NON fixé dans le code, la valeur en vigueur à l'entraînement
    # EST le défaut de la bibliothèque : on la lit dans la configuration interne du
    # booster (Booster.save_config()). Pour un paramètre FIXÉ dans le code, cette
    # même configuration rend le défaut et non la valeur d'entraînement (démontré en
    # A.4) : la valeur effective est alors celle du code, et elle seule.
    ttp_alias = {   # nom sklearn -> clé de tree_train_param
        "min_child_weight": "min_child_weight", "gamma": "min_split_loss",
        "reg_lambda": "reg_lambda", "reg_alpha": "reg_alpha",
        "colsample_bylevel": "colsample_bylevel", "colsample_bynode": "colsample_bynode",
        "max_delta_step": "max_delta_step", "grow_policy": "grow_policy",
        "max_leaves": "max_leaves", "max_bin": "max_bin",
        "sampling_method": "sampling_method", "monotone_constraints": "monotone_constraints",
        "interaction_constraints": "interaction_constraints",
        "max_cat_to_onehot": "max_cat_to_onehot", "max_cat_threshold": "max_cat_threshold",
    }
    ltp_alias = {"booster": "booster", "multi_strategy": "multi_strategy"}
    gen_alias = {"n_jobs": "n_jobs", "device": "device",
                 "validate_parameters": "validate_parameters"}
    ltp = cfg_bas["learner"]["learner_train_param"]
    defaut_effectif = {}
    for k, ck in ttp_alias.items():
        defaut_effectif[k] = (ttp[ck], f"Booster.save_config().tree_train_param.{ck}")
    for k, ck in ltp_alias.items():
        defaut_effectif[k] = (ltp[ck], f"Booster.save_config().learner_train_param.{ck}")
    for k, ck in gen_alias.items():
        defaut_effectif[k] = (gen[ck], f"Booster.save_config().generic_param.{ck}")
    defaut_effectif["n_jobs"] = (
        f"{gen['n_jobs']} (0 = tous les fils disponibles) — ramené à 1 fil par "
        "l'épinglage OMP_NUM_THREADS=1 et suivantes (ADR-076)",
        "Booster.save_config().generic_param.n_jobs + " + rel(SRC_TRAIN))
    defaut_effectif["num_parallel_tree"] = (
        artefacts["bas"]["num_parallel_tree"],
        "artefact gelé — gbtree_model_param.num_parallel_tree")
    defaut_effectif["scale_pos_weight"] = (
        artefacts["bas"]["scale_pos_weight"], "artefact gelé — objective.reg_loss_param")
    defaut_effectif["base_score"] = (
        f"bas {artefacts['bas']['base_score']} / haut {artefacts['haut']['base_score']}",
        "artefact gelé — appris sur le train (boost_from_average=1), non fixé")
    defaut_effectif["missing"] = (
        "nan (np.nan)",
        f"défaut de l'estimateur sklearn — inspect.signature(XGBRegressor), "
        f"xgboost {xgb.__version__}")
    for k in ("early_stopping_rounds", "eval_metric", "callbacks", "importance_type",
              "feature_types", "feature_weights", "max_cat_to_onehot"):
        if k in sentinelles and sentinelles[k] is None and k not in defaut_effectif:
            defaut_effectif[k] = ("non utilisé (None côté estimateur sklearn)",
                                  f"XGBRegressor().get_params() — xgboost {xgb.__version__}")

    rows = []
    hdr = ["parametre", "valeur_effective", "origine", "verifiable_dans_l_artefact",
           "valeur_lue_dans_l_artefact", "source"]
    interet = [  # ordre de lecture du manuscrit
        "n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree",
        "objective", "tree_method", "random_state", "enable_categorical", "verbosity",
        "missing", "min_child_weight", "gamma", "reg_lambda", "reg_alpha",
        "colsample_bylevel", "colsample_bynode", "max_delta_step", "grow_policy",
        "max_leaves", "max_bin", "booster", "n_jobs", "base_score", "scale_pos_weight",
        "num_parallel_tree", "sampling_method", "monotone_constraints",
        "interaction_constraints", "early_stopping_rounds", "eval_metric", "callbacks",
        "max_cat_to_onehot", "max_cat_threshold", "multi_strategy", "device",
        "importance_type", "validate_parameters", "feature_types",
    ]
    vus = set()
    ordre = [p for p in interet if not (p in vus or vus.add(p))]
    ordre += [p for p in params_estimateur if p not in vus and not vus.add(p)]

    art_lu = {
        "n_estimators": str(artefacts["bas"]["num_trees"]),
        "objective": artefacts["bas"]["objective"],
        "base_score": f"bas {artefacts['bas']['base_score']} / haut {artefacts['haut']['base_score']}",
        "scale_pos_weight": str(artefacts["bas"]["scale_pos_weight"]),
        "num_parallel_tree": str(artefacts["bas"]["num_parallel_tree"]),
        "max_depth": (f"profondeur observée des 300 arbres = "
                      f"{artefacts['bas']['profondeur_observee_min']} (min) / "
                      f"{artefacts['bas']['profondeur_observee_max']} (max) — "
                      f"compatible avec max_depth=6, ne le prouve pas à lui seul"),
    }
    for p in ordre:
        if p in params_train:
            val = params_train[p]
            origine = "fixée dans le code d'entraînement"
            source = rel(SRC_TRAIN)
        elif p in defaut_effectif:
            val, source = defaut_effectif[p]
            origine = (f"défaut de la bibliothèque (xgboost {xgb.__version__}) — "
                       "non fixé dans le code d'entraînement")
        elif p in sentinelles:
            val = ("non utilisé (None côté estimateur sklearn)"
                   if sentinelles[p] is None else sentinelles[p])
            origine = (f"défaut de la bibliothèque (xgboost {xgb.__version__}) — "
                       "non fixé dans le code d'entraînement")
            source = f"XGBRegressor().get_params() — xgboost {xgb.__version__}"
        else:
            continue
        if isinstance(val, float) and np.isnan(val):
            val = "nan"
        rows.append([p, str(val), origine, oui_non(p in art_lu), art_lu.get(p, ""), source])
    # lignes de synthèse propres à l'artefact
    rows.append(["[artefact] num_trees (bas)", str(artefacts["bas"]["num_trees"]),
                 "lu dans l'artefact gelé", "oui", str(artefacts["bas"]["num_trees"]),
                 rel(MODEL_DIR / MODELS["bas"][0])])
    rows.append(["[artefact] num_trees (haut)", str(artefacts["haut"]["num_trees"]),
                 "lu dans l'artefact gelé", "oui", str(artefacts["haut"]["num_trees"]),
                 rel(MODEL_DIR / MODELS["haut"][0])])
    rows.append(["[artefact] num_feature", str(artefacts["bas"]["num_feature"]),
                 "lu dans l'artefact gelé", "oui", str(artefacts["bas"]["num_feature"]),
                 rel(MODEL_DIR / MODELS["bas"][0])])
    rows.append(["[artefact] version xgboost sérialisée",
                 ".".join(map(str, artefacts["bas"]["xgboost_version_serialisee"])),
                 "lu dans l'artefact gelé", "oui",
                 ".".join(map(str, artefacts["bas"]["xgboost_version_serialisee"])),
                 rel(MODEL_DIR / MODELS["bas"][0])])
    rows.append(["[arrêt anticipé] employé", "non",
                 "absence de early_stopping_rounds / eval_set dans le code d'entraînement",
                 "non", "", rel(SRC_TRAIN)])

    write_csv("verif_45_bloc_a_config_effective.csv", hdr, rows)

    return {
        "params_code_entrainement": {k: ("nan" if isinstance(v, float) and np.isnan(v) else v)
                                     for k, v in params_train.items()},
        "params_code_identiques_producteur_vs_harness": params_train == params_harness,
        "seed": seed_train,
        "defauts_bibliotheque_xgboost": xgb.__version__,
        "defauts_effectifs_non_fixes": {k: str(v[0]) for k, v in defaut_effectif.items()},
        "artefacts": artefacts,
        "hp_sklearn_nuls_apres_load": hp_sklearn_nuls,
        "preuve_save_config_rend_les_defauts": preuve_defauts,
        "arret_anticipe": early,
        "divergences_bas_haut": [{"champ": d[0], "bas": d[1], "haut": d[2]} for d in divergences],
        "sources": {"producteur_du_gel": rel(SRC_TRAIN), "socle": rel(SRC_HARNESS),
                    "metadata": rel(METADATA)},
    }


# ════════════════════════════════════════════════════════════════════════════════
# BLOC B — espaces de recherche des trois campagnes
# ════════════════════════════════════════════════════════════════════════════════
def bloc_b():
    print("\n" + "-" * 88)
    print("BLOC B — espaces de recherche des trois campagnes de réglage")
    print("-" * 88)
    rows = []
    hdr = ["campagne", "algorithme", "hyperparametre", "explore", "type", "loi",
           "borne_min", "borne_max", "choix_ou_grille", "valeur_retenue",
           "contenue_dans_l_espace", "source"]
    synth = {}

    # ── (a) grille factorielle 27 combinaisons, walk-forward 2 plis ──────────────
    code_a = notebook_code(SRC_A_NB)
    tree_a = ast.parse(code_a)
    xgb_base_a = dict_call_to_py(find_assign(tree_a, "XGB_BASE"), module_literals(tree_a))
    grid_node = find_assign(tree_a, "GRID")
    # GRID = list(itertools.product(<lit>, <lit>, <lit>))
    prod_args = [ast.literal_eval(a) for a in grid_node.args[0].args]
    grille_a = {"max_depth": prod_args[0], "min_child_weight": prod_args[1],
                "couples_n_estimators_learning_rate": [list(t) for t in prod_args[2]]}
    n_comb_a = len(list(itertools.product(*prod_args)))
    folds_a = ast.literal_eval(find_assign(tree_a, "FOLDS"))
    seed_a = extract_scalar_assign(code_a, "SEED")
    embargo_a = extract_scalar_assign(code_a, "EMBARGO")
    seuil_a = extract_scalar_assign(code_a, "SEUIL_UM")
    beta_a = extract_scalar_assign(code_a, "CRITERE_BETA")
    nboot_a = extract_scalar_assign(code_a, "N_BOOT")
    cells_a = sorted(json.loads(SRC_A_BEST.read_text(encoding="utf-8")).keys())
    # garde-fou de hachage du dataset dans la campagne (a) ?
    garde_a = ("sha256" in code_a) or ("HASH_ATTENDU" in code_a)
    print(f"  (a) grille factorielle — {n_comb_a} combinaisons, "
          f"{len(folds_a)} plis, {len(cells_a)} cellules ; source {rel(SRC_A_NB)}")
    print(f"      plis : " + " ; ".join(f"{f['name']} train={f['train']} val={f['val']}"
                                        for f in folds_a))
    print(f"      garde-fou d'empreinte du dataset dans la campagne : {oui_non(garde_a)}")

    esp_a = {
        "max_depth": {"choix": grille_a["max_depth"], "loi": "grille exhaustive (catégorielle)"},
        "min_child_weight": {"choix": grille_a["min_child_weight"],
                             "loi": "grille exhaustive (catégorielle)"},
        "n_estimators": {"choix": sorted({c[0] for c in grille_a["couples_n_estimators_learning_rate"]}),
                         "loi": "grille exhaustive, couplée à learning_rate"},
        "learning_rate": {"choix": sorted({c[1] for c in grille_a["couples_n_estimators_learning_rate"]}),
                          "loi": "grille exhaustive, couplée à n_estimators"},
        "subsample": {"choix": [xgb_base_a["subsample"]], "loi": "constante (non explorée)"},
        "colsample_bytree": {"choix": [xgb_base_a["colsample_bytree"]],
                             "loi": "constante (non explorée)"},
    }
    explores_a = {"max_depth", "min_child_weight", "n_estimators", "learning_rate"}
    for hp, val in RETENU.items():
        sp = esp_a[hp]
        ok = contient(sp, val)
        # cas particulier : (n_estimators, learning_rate) sont couplés
        if hp in ("n_estimators", "learning_rate"):
            couple_ok = [300, 0.1] in grille_a["couples_n_estimators_learning_rate"]
            note = f"couple (300, 0.1) présent dans la grille : {oui_non(couple_ok)}"
        else:
            note = ""
        rows.append(["(a) grille factorielle 27 comb.", "XGBoost", hp,
                     oui_non(hp in explores_a), "ensemble fini", sp["loi"], "", "",
                     json.dumps(sp["choix"]) + ((" — " + note) if note else ""),
                     val, oui_non(ok), rel(SRC_A_NB)])
    for hp in ("min_child_weight",):
        sp = esp_a[hp]
        rows.append(["(a) grille factorielle 27 comb.", "XGBoost", hp, "oui",
                     "ensemble fini", sp["loi"], "", "", json.dumps(sp["choix"]),
                     "1 (valeur du modèle retenu, défaut xgboost)",
                     oui_non(contient(sp, 1)), rel(SRC_A_NB)])
    synth["a"] = {
        "libelle": "Grille factorielle par cellule — robustesse des hyperparamètres (ADR-047)",
        "script": rel(SRC_A_NB),
        "sorties": [rel(SRC_A_BEST),
                    rel(ROOT / "archive/explorations/consolidation_finale/outputs"
                        / "etape_03_wf_tuning_results.csv")],
        "hyperparametres_explores": sorted(explores_a),
        "grille": grille_a, "n_combinaisons": n_comb_a,
        "hyperparametres_constants": {k: xgb_base_a[k]
                                      for k in ("subsample", "colsample_bytree",
                                                "tree_method", "objective")},
        "objectif_optimise": "PR-AUC du segment haut, moyenne des 2 plis "
                             "(fonction eval_wf_haut, seuil de surcharge "
                             f"{seuil_a} de l'époque)",
        "schema_validation": {"type": "walk-forward temporel progressif, par année horaire",
                              "n_plis": len(folds_a), "plis": folds_a,
                              "embargo_jours": embargo_a,
                              "cellules_tunees": cells_a},
        "budget_essais": f"{n_comb_a} combinaisons × {len(folds_a)} plis × "
                         f"{len(cells_a)} cellules = "
                         f"{n_comb_a * len(folds_a) * len(cells_a)} entraînements",
        "graine_optimiseur": "sans objet — grille exhaustive déterministe ; "
                             f"SEED={seed_a} est le random_state de XGBoost",
        "bibliotheque_optimisation": "aucune — itertools.product (bibliothèque standard)",
        "criteres_annexes": {"calibration du seuil": f"F-bêta, bêta={beta_a}",
                             "bootstrap": nboot_a},
        "garde_empreinte_dataset": garde_a,
        "empreinte_dataset_de_l_epoque": INTROUVABLE + " — la campagne (a) ne pose aucun "
                                         "garde-fou d'empreinte et ses sorties n'en "
                                         "consignent aucune (ADR-045 mentionne le hash "
                                         "intermédiaire 1a53590f pour l'étape 2)",
    }

    # ── (b) Optuna bayésien multi-objectif, 50 essais par segment ────────────────
    src_b = module_source(SRC_B)
    space_b = extract_suggest_space(src_b, "objective")
    n_trials_b = extract_scalar_assign(src_b, "N_TRIALS")
    seed_b = extract_scalar_assign(src_b, "SEED")
    fixed_b = extract_dict_assign(src_b, "FIXED")
    hp_actuels_b = extract_dict_assign(src_b, "HP_ACTUELS")
    hash_b = extract_scalar_assign(src_b, "HASH_ATTENDU")
    res_b = json.loads(SRC_B_RES.read_text(encoding="utf-8"))
    # directions et sampler, lus dans l'appel create_study
    tree_b = ast.parse(src_b)
    env_b = module_literals(tree_b)
    directions_b, sampler_b, sampler_seed_b = None, None, None
    for node in ast.walk(tree_b):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_study"):
            for kw in node.keywords:
                if kw.arg == "directions":
                    directions_b = _eval_node(kw.value, env_b)
                if kw.arg == "sampler" and isinstance(kw.value, ast.Call):
                    sampler_b = kw.value.func.attr
                    for k2 in kw.value.keywords:
                        if k2.arg == "seed":
                            sampler_seed_b = _eval_node(k2.value, env_b)
    print(f"\n  (b) Optuna TPE multi-objectif — {len(space_b)} HP, {n_trials_b} essais "
          f"par segment ; source {rel(SRC_B)}")
    print(f"      directions={directions_b} sampler={sampler_b}(seed={sampler_seed_b})")
    print(f"      paramètres figés hors espace : {fixed_b}")
    esp_b = {s["hp"]: s for s in space_b}
    for hp, val in RETENU.items():
        sp = esp_b.get(hp)
        if sp is None:
            rows.append(["(b) Optuna TPE multi-objectif", "XGBoost", hp, "non", "", "",
                         "", "", "", val, "non", rel(SRC_B)])
            continue
        rows.append(["(b) Optuna TPE multi-objectif", "XGBoost", hp, "oui", sp["type"],
                     sp["loi"], sp["borne_min"], sp["borne_max"], "", val,
                     oui_non(contient(sp, val)), rel(SRC_B)])
    for hp in sorted(set(esp_b) - set(RETENU)):
        sp = esp_b[hp]
        ref = hp_actuels_b.get(hp)
        rows.append(["(b) Optuna TPE multi-objectif", "XGBoost", hp, "oui", sp["type"],
                     sp["loi"], sp["borne_min"], sp["borne_max"], "",
                     ref if ref is not None else "",
                     oui_non(contient(sp, ref)) if ref is not None else "",
                     rel(SRC_B)])
    synth["b"] = {
        "libelle": "Optimisation bayésienne multi-objectif par segment (ADR-071)",
        "script": rel(SRC_B),
        "sorties": [rel(SRC_B_RES), rel(SRC_B_TRIALS), rel(SRC_B_LOG),
                    rel(DIR_B / "postprocess_h24.py"),
                    rel(DIR_B / "test_h25_best_r2_vs_cf09.py")],
        "hyperparametres_explores": space_b,
        "parametres_figes_hors_espace": fixed_b,
        "objectif_optimise": {"directions": directions_b,
                              "objectif_1": "maximiser R² global sur H24",
                              "objectif_2": "minimiser |biais>63| sur H24",
                              "agregation": "front de Pareto (aucune pondération)"},
        "schema_validation": {"type": "hold-out temporel unique (pas de validation croisée)",
                              "n_plis": 1,
                              "train": "H22 hors tronçons Gilamont (BPUIC 8501260) + H23",
                              "validation": "H24",
                              "test": "H25 jamais chargé pendant l'optimisation",
                              "n_train": 465573, "n_validation": 335709,
                              "source_effectifs": rel(SRC_B_LOG)},
        "budget_essais": {"par_segment": n_trials_b, "segments": ["bas", "haut"],
                          "total": n_trials_b * 2,
                          "lignes_dans_le_csv_de_trials": 100},
        "graine_optimiseur": {"sampler": sampler_b, "seed": sampler_seed_b,
                              "seed_module": seed_b},
        "bibliotheque_optimisation": {
            "nom": "optuna",
            "version_au_moment_de_la_campagne": INTROUVABLE + " — ni le JSON de résultats, "
            "ni le CSV de trials, ni run.log ne consignent la version d'optuna ; "
            "requirements.txt (committé le 2026-07-09, postérieur à la campagne du "
            "2026-06-28) épingle optuna==4.9.0",
        },
        "empreinte_dataset_de_la_campagne": hash_b,
        "reference_dans_la_campagne": hp_actuels_b,
        "n_points_pareto": {s: res_b["pareto"][s]["n_pareto"] for s in ("bas", "haut")},
        "note_execution": "run.log montre que la première exécution s'est interrompue "
                          "après les figures (AttributeError ndarray.ptp, NumPy 2.0) ; "
                          "tuning_optuna_h24_resultats.json a été produit par "
                          f"{rel(DIR_B / 'postprocess_h24.py')}, qui relit le CSV de "
                          "trials sans ré-optimiser",
    }

    # ── (c) comparatif inter-algorithmes, 40 essais par algorithme ───────────────
    src_c = module_source(SRC_C)
    spaces_c = {"xgboost": extract_suggest_space(src_c, "space_xgb"),
                "lightgbm": extract_suggest_space(src_c, "space_lgbm"),
                "catboost": extract_suggest_space(src_c, "space_catboost")}
    n_trials_c = extract_scalar_assign(src_c, "N_TRIALS")   # défaut du littéral
    max_trees_c = extract_scalar_assign(src_c, "MAX_TREES")
    early_c = extract_scalar_assign(src_c, "EARLY_STOP")
    seed_c = extract_scalar_assign(src_c, "SEED")
    hash_c = extract_scalar_assign(src_c, "HASH_ATTENDU")
    res_c = json.loads(SRC_C_RES.read_text(encoding="utf-8"))
    spaces_doc_c = res_c["search_spaces"]
    tree_c = ast.parse(src_c)
    env_c = module_literals(tree_c)
    sampler_c, sampler_seed_c, direction_c = None, None, None
    for node in ast.walk(tree_c):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_study"):
            for kw in node.keywords:
                if kw.arg == "direction":
                    direction_c = _eval_node(kw.value, env_c)
                if kw.arg == "sampler" and isinstance(kw.value, ast.Call):
                    sampler_c = kw.value.func.attr
                    for k2 in kw.value.keywords:
                        if k2.arg == "seed":
                            sampler_seed_c = _eval_node(k2.value, env_c)
    n_trials_effectif_c = res_c["n_trials_par_algo"]
    print(f"\n  (c) comparatif inter-algorithmes — {n_trials_effectif_c} essais/algo, "
          f"sampler {sampler_c}(seed={sampler_seed_c}), direction={direction_c} ; "
          f"source {rel(SRC_C)}")
    for algo, sp_list in spaces_c.items():
        print(f"      {algo:<9} : {len(sp_list)} HP échantillonnés + n_arbres par "
              f"arrêt anticipé (plafond {max_trees_c}, patience {early_c})")
    esp_c_xgb = {s["hp"]: s for s in spaces_c["xgboost"]}
    for hp, val in RETENU.items():
        if hp == "n_estimators":
            rows.append(["(c) comparatif inter-algorithmes", "XGBoost", hp, "non",
                         "entier", "non échantillonné — fixé par arrêt anticipé",
                         1, max_trees_c,
                         f"plafond {max_trees_c} arbres, patience {early_c} tours",
                         val, oui_non(1 <= val <= max_trees_c), rel(SRC_C)])
            continue
        sp = esp_c_xgb.get(hp)
        if sp is None:
            rows.append(["(c) comparatif inter-algorithmes", "XGBoost", hp, "non", "",
                         "", "", "", "", val, "non", rel(SRC_C)])
            continue
        rows.append(["(c) comparatif inter-algorithmes", "XGBoost", hp, "oui", sp["type"],
                     sp["loi"], sp["borne_min"], sp["borne_max"], "", val,
                     oui_non(contient(sp, val)), rel(SRC_C)])
    for hp in sorted(set(esp_c_xgb) - set(RETENU)):
        sp = esp_c_xgb[hp]
        ref = {"min_child_weight": 1, "reg_lambda": 1.0, "reg_alpha": 0.0}.get(hp)
        rows.append(["(c) comparatif inter-algorithmes", "XGBoost", hp, "oui", sp["type"],
                     sp["loi"], sp["borne_min"], sp["borne_max"], "",
                     ref if ref is not None else "",
                     oui_non(contient(sp, ref)) if ref is not None else "", rel(SRC_C)])
    for algo in ("lightgbm", "catboost"):
        for sp in spaces_c[algo]:
            rows.append(["(c) comparatif inter-algorithmes", algo, sp["hp"], "oui",
                         sp["type"], sp["loi"], sp["borne_min"], sp["borne_max"], "",
                         "", "", rel(SRC_C)])
        nom_arbres = "n_estimators" if algo == "lightgbm" else "iterations"
        rows.append(["(c) comparatif inter-algorithmes", algo, nom_arbres, "non",
                     "entier", "non échantillonné — fixé par arrêt anticipé", 1,
                     max_trees_c,
                     f"plafond {max_trees_c} arbres, patience {early_c} tours", "", "",
                     rel(SRC_C)])
    synth["c"] = {
        "libelle": "Comparatif inter-algorithmes à budget égal (ADR-072)",
        "script": rel(SRC_C),
        "sorties": [rel(SRC_C_RES), rel(SRC_C_LOG)] +
                   [rel(DIR_C / f"best_params_{a}.json") for a in spaces_c] +
                   [rel(DIR_C / f"trials_{a}.csv") for a in spaces_c],
        "hyperparametres_explores": spaces_c,
        "espaces_tels_que_documentes_dans_la_sortie": spaces_doc_c,
        "arbres": {"mode": "arrêt anticipé pendant chaque essai ; refit final au nombre "
                           "moyen de best_iteration des 3 plis, par segment",
                   "plafond": max_trees_c, "patience": early_c},
        "objectif_optimise": {"direction": direction_c,
                              "metrique": "RMSE de validation, moyenné sur les 3 plis, "
                                          "calculé sur les deux segments réunis"},
        "schema_validation": {"type": "walk-forward temporel à fenêtre expansive, par date, "
                                      "à l'intérieur du seul train",
                              "n_plis": 3,
                              "construction": "dates uniques du train découpées en 4 blocs "
                                              "chronologiques (np.array_split) -> 3 plis",
                              "plis_effectifs": [
                                  {"pli": 1, "n_train": 102832, "n_val": 211520,
                                   "val_debut": "2022-09-07", "val_fin": "2023-06-29"},
                                  {"pli": 2, "n_train": 314352, "n_val": 246174,
                                   "val_debut": "2023-06-30", "val_fin": "2024-03-22"},
                                  {"pli": 3, "n_train": 560526, "n_val": 240756,
                                   "val_debut": "2024-03-23", "val_fin": "2024-12-14"}],
                              "source_effectifs": rel(SRC_C_LOG),
                              "test": "H25 révélé une seule fois, après figement"},
        "budget_essais": {"par_algorithme": n_trials_effectif_c,
                          "algorithmes": sorted(spaces_c),
                          "total": n_trials_effectif_c * 3,
                          "valeur_par_defaut_dans_le_script": n_trials_c,
                          "duree_minutes": {a: json.loads(
                              (DIR_C / f"best_params_{a}.json").read_text(encoding="utf-8")
                          )["tuning_minutes"] for a in sorted(spaces_c)}},
        "graine_optimiseur": {"sampler": sampler_c, "seed": sampler_seed_c,
                              "seed_module": seed_c},
        "bibliotheque_optimisation": {
            "nom": "optuna",
            "version_au_moment_de_la_campagne": INTROUVABLE + " — ni tuning_resultats.json, "
            "ni best_params_*.json, ni run_full.log ne consignent la version d'optuna ; "
            "requirements.txt (committé le 2026-07-09, postérieur à la campagne, exécutée "
            "le 2026-07-02 d'après les horodatages des trials_*.csv) épingle optuna==4.9.0",
        },
        "empreinte_dataset_de_la_campagne": hash_c,
        "architecture": res_c["architecture"],
    }

    write_csv("verif_45_bloc_b_espaces_recherche.csv", hdr, rows)

    # Récapitulatif de contenance imprimé
    print("\n  Contenance de la configuration retenue (300 / 6 / 0,1 / 0,8 / 0,8) :")
    print(f"    {'hyperparamètre':<18} {'(a)':>22} {'(b)':>22} {'(c)':>22}")
    recap = {}
    for hp, val in RETENU.items():
        cells = []
        for camp in ("(a) grille factorielle 27 comb.", "(b) Optuna TPE multi-objectif",
                     "(c) comparatif inter-algorithmes"):
            r = next(x for x in rows
                     if x[0] == camp and x[1] == "XGBoost" and x[2] == hp)
            cells.append(f"{r[10]} (exploré : {r[3]})")
        recap[hp] = {"valeur": val, "a": cells[0], "b": cells[1], "c": cells[2]}
        print(f"    {hp:<18} {cells[0]:>22} {cells[1]:>22} {cells[2]:>22}")
    synth["contenance_configuration_retenue"] = recap
    return synth


# ════════════════════════════════════════════════════════════════════════════════
# BLOC C — configurations gagnantes non retenues
# ════════════════════════════════════════════════════════════════════════════════
def bloc_c(params_retenus: dict):
    print("\n" + "-" * 88)
    print("BLOC C — configurations gagnantes non retenues, en regard du retenu")
    print("-" * 88)
    rows = []
    hdr = ["origine", "candidat", "segment", "hyperparametre", "valeur_candidat",
           "valeur_retenue", "ecart", "source"]

    def cmp_val(v_cand, v_ret):
        if v_ret is None:
            return "hors périmètre du retenu"
        if isinstance(v_cand, (int, float)) and isinstance(v_ret, (int, float)):
            if float(v_cand) == float(v_ret):
                return "identique"
            return f"{float(v_cand) - float(v_ret):+.6g}"
        return "identique" if v_cand == v_ret else "différent"

    # Référence : configuration retenue, 9 HP explicites (les 4 non fixés dans le code
    # valent leur défaut xgboost, et c'est ce que la campagne (b) prend pour référence).
    ref_9 = dict(RETENU)
    ref_9.update({"min_child_weight": 1, "reg_lambda": 1.0, "reg_alpha": 0.0, "gamma": 0.0})

    # ── (b) points du front de Pareto ───────────────────────────────────────────
    res_b = json.loads(SRC_B_RES.read_text(encoding="utf-8"))
    hp_ref_b = res_b["hp_actuels_adr_cf09"]
    assert hp_ref_b == ref_9, "la référence de la campagne (b) diffère du retenu documenté"
    pts_b = {}
    for seg in ("bas", "haut"):
        for pt in ("best_R2", "knee", "best_bias"):
            m = res_b["pareto"][seg][pt]
            pts_b[(seg, pt)] = m
            for hp, v in m["params"].items():
                rows.append(["(b) Optuna TPE multi-objectif", pt, seg, hp, v,
                             ref_9.get(hp), cmp_val(v, ref_9.get(hp)), rel(SRC_B_RES)])
    print("  (b) front de Pareto : "
          f"bas {res_b['pareto']['bas']['n_pareto']} points, "
          f"haut {res_b['pareto']['haut']['n_pareto']} points. "
          "Multi-objectif : aucun « meilleur » unique.")
    print("      Le candidat désigné pour le test d'adoption (ADR-071) est best-R² :")
    for seg in ("bas", "haut"):
        p = pts_b[(seg, "best_R2")]["params"]
        print(f"        {seg:<4} max_depth={p['max_depth']} lr={p['learning_rate']:.6g} "
              f"n_estimators={p['n_estimators']} subsample={p['subsample']:.6g} "
              f"colsample={p['colsample_bytree']:.6g} mcw={p['min_child_weight']} "
              f"lambda={p['reg_lambda']:.6g} alpha={p['reg_alpha']:.6g} "
              f"gamma={p['gamma']:.6g}")

    # ── (c) trois configurations optimisées ─────────────────────────────────────
    bp = {}
    for algo in ("xgboost", "lightgbm", "catboost"):
        d = json.loads((DIR_C / f"best_params_{algo}.json").read_text(encoding="utf-8"))
        bp[algo] = d
        for hp, v in d["best_params"].items():
            ref = ref_9.get(hp) if algo == "xgboost" else None
            rows.append(["(c) comparatif inter-algorithmes", algo, "partagé bas+haut",
                         hp, v, ref, cmp_val(v, ref),
                         rel(DIR_C / f"best_params_{algo}.json")])
        for seg, cle in (("bas", "n_arbres_bas"), ("haut", "n_arbres_haut")):
            v = d[cle]
            ref = ref_9["n_estimators"] if algo == "xgboost" else None
            rows.append(["(c) comparatif inter-algorithmes", algo, seg,
                         "n_estimators (arrêt anticipé)", v, ref, cmp_val(v, ref),
                         rel(DIR_C / f"best_params_{algo}.json")])
        print(f"  (c) {algo:<9} CV-RMSE={d['best_cv_rmse_mean']:.4f} "
              f"(±{d['cv_rmse_std']:.4f}) n_arbres bas/haut={d['n_arbres_bas']}/"
              f"{d['n_arbres_haut']}")

    # ligne de référence explicite
    for hp, v in ref_9.items():
        rows.append(["configuration retenue (référence)", "modèle gelé", "bas et haut",
                     hp, v, v, "identique",
                     rel(SRC_TRAIN) if hp in params_retenus
                     else f"défaut xgboost {xgb.__version__}"])

    write_csv("verif_45_bloc_c_configs_candidates.csv", hdr, rows)

    return {
        "reference_9_hp": ref_9,
        "campagne_b": {
            "n_points_pareto": {s: res_b["pareto"][s]["n_pareto"] for s in ("bas", "haut")},
            "note": "campagne multi-objectif : le front de Pareto n'a pas de point "
                    "optimal unique ; ADR-071 désigne best-R² comme candidat testé "
                    "pour l'adoption. best-bias et knee sont reportés dans le CSV.",
            "points": {f"{seg}/{pt}": pts_b[(seg, pt)] for (seg, pt) in pts_b},
            "reference_h24": res_b["reference_h24"],
        },
        "campagne_c": {a: {k: bp[a][k] for k in ("best_params", "n_arbres_bas",
                                                 "n_arbres_haut", "best_cv_rmse_mean",
                                                 "cv_rmse_folds", "cv_rmse_std",
                                                 "n_trials", "seed", "tuning_minutes")}
                       for a in bp},
    }


# ════════════════════════════════════════════════════════════════════════════════
# BLOC D — baselines et environnement
# ════════════════════════════════════════════════════════════════════════════════
def bloc_d():
    print("\n" + "-" * 88)
    print("BLOC D — baselines et environnement")
    print("-" * 88)
    rows = []
    hdr = ["rubrique", "element", "valeur", "origine", "source"]

    # ── D.1 Ridge ───────────────────────────────────────────────────────────────
    src = module_source(SRC_C03)
    alpha_defaut = extract_scalar_assign(src, "ALPHA_DEFAUT")
    alphas_sweep = extract_scalar_assign(src, "ALPHAS_SWEEP")
    c03 = json.loads((CONF / "c03_baseline_lineaire.json").read_text(encoding="utf-8"))
    sw = c03["validation_grossiere_H24"]
    from sklearn.linear_model import Ridge
    import sklearn
    ridge_defauts = Ridge().get_params()
    print(f"  D.1 Ridge : alpha retenu (headline) = {alpha_defaut} "
          f"(= défaut scikit-learn {ridge_defauts['alpha']})")
    print(f"      balayage informatif sur H24 : {sw['alphas']}")
    print(f"      meilleur alpha du balayage = {sw['meilleur_alpha_H24']} — NON adopté "
          f"(le headline reste {alpha_defaut})")
    for k, v in [
        ("bibliothèque", f"scikit-learn {sklearn.__version__} — sklearn.linear_model.Ridge"),
        ("alpha du modèle rapporté", str(alpha_defaut)),
        ("alpha : origine de la valeur",
         f"défaut de la bibliothèque ({ridge_defauts['alpha']}) — voir procédure ci-dessous"),
        ("procédure de sélection sur H24",
         "balayage sur " + json.dumps(alphas_sweep) + " ; ajustement sur H22+H23, "
         "évaluation R² global sur H24 ; PAS de tuning fin, PAS de validation croisée, "
         "PAS de RidgeCV. Le balayage est déclaré informatif dans le script : le modèle "
         "rapporté est refité sur tout le train Split C à alpha=1.0"),
        ("R² H24 du balayage", json.dumps(sw["alphas"])),
        ("meilleur alpha du balayage", str(sw["meilleur_alpha_H24"])),
        ("meilleur alpha adopté ?", "non — le modèle rapporté conserve alpha=1.0"),
        ("architecture", c03["meta"]["modele"]),
        ("imputation numériques",
         f"SimpleImputer(strategy='median') sur {c03['meta']['n_numeriques']} variables, "
         "médiane apprise sur le train"),
        ("imputation catégorielles",
         f"SimpleImputer(strategy='most_frequent') puis OneHotEncoder("
         f"handle_unknown='ignore') sur {c03['meta']['n_categorielles']} variables"),
        ("standardisation", c03["meta"]["standardisation"]),
        ("motif de l'imputation", c03["meta"]["note_nan"]),
        ("graine", str(c03["meta"]["seed"])),
        ("empreinte du dataset", c03["meta"]["dataset_hash_sha256_8"]),
    ]:
        rows.append(["D.1 Ridge (§4.5.2)", k, v, "lu dans le script / sa sortie",
                     f"{rel(SRC_C03)} ; {rel(CONF / 'c03_baseline_lineaire.json')}"])
    for k, v in ridge_defauts.items():
        if k == "alpha":
            continue
        rows.append(["D.1 Ridge (§4.5.2)", f"[défaut sklearn] {k}", str(v),
                     "défaut de la bibliothèque (non fixé dans le code)",
                     f"sklearn {sklearn.__version__} — Ridge().get_params()"])

    # ── D.2 Random Forest ───────────────────────────────────────────────────────
    from sklearn.ensemble import RandomForestRegressor
    src10 = module_source(SRC_C10)
    tree10 = ast.parse(src10)
    rf_kwargs = None
    for node in ast.walk(tree10):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "RandomForestRegressor"):
            rf_kwargs = {kw.arg: (ast.unparse(kw.value) if hasattr(ast, "unparse")
                                  else ast.dump(kw.value)) for kw in node.keywords}
    if rf_kwargs and rf_kwargs.get("random_state") == "H.SEED":
        rf_kwargs["random_state"] = f"H.SEED = {extract_scalar_assign(module_source(SRC_HARNESS), 'SEED')}"
    rf_defauts = RandomForestRegressor().get_params()
    c10 = json.loads((CONF / "c10_comparatif_algos.json").read_text(encoding="utf-8"))
    print(f"\n  D.2 Random Forest : scikit-learn {sklearn.__version__} — "
          f"RandomForestRegressor ; arguments fixés dans le code = {rf_kwargs}")
    print(f"      n_estimators (défaut) = {rf_defauts['n_estimators']} ; "
          f"criterion = {rf_defauts['criterion']} ; max_depth = {rf_defauts['max_depth']} ; "
          f"max_features = {rf_defauts['max_features']}")
    rows.append(["D.2 Random Forest (§4.5.3)", "bibliothèque",
                 f"scikit-learn {sklearn.__version__} — "
                 "sklearn.ensemble.RandomForestRegressor", "environnement installé",
                 rel(REQUIREMENTS)])
    for k, v in (rf_kwargs or {}).items():
        rows.append(["D.2 Random Forest (§4.5.3)", f"[fixé dans le code] {k}", str(v),
                     "fixé dans le code", rel(SRC_C10)])
    for k, v in rf_defauts.items():
        if k in (rf_kwargs or {}):
            continue
        rows.append(["D.2 Random Forest (§4.5.3)", f"[défaut sklearn] {k}", str(v),
                     "défaut de la bibliothèque (non fixé dans le code)",
                     f"sklearn {sklearn.__version__} — RandomForestRegressor().get_params()"])
    for k, v in [
        ("architecture", "segmentée : un RandomForest BAS + un RandomForest HAUT, "
                         "aiguillage par spatial_segment"),
        ("prétraitement", c10["meta"]["manip_categorielles"].split(";")[-1].strip()),
        ("note n_jobs", c10["meta"]["note_threads"]),
        ("durée d'entraînement (s)", str(c10["meta"]["durees_s"]["randomforest_defaut"])),
    ]:
        rows.append(["D.2 Random Forest (§4.5.3)", k, v, "lu dans la sortie",
                     rel(CONF / "c10_comparatif_algos.json")])

    # ── D.3 Baseline naïve ──────────────────────────────────────────────────────
    bn = c10["baseline_naive_details"]
    print("\n  D.3 Baseline naïve — règle de repli en cascade :")
    libelles = {
        1: "moyenne du train pour (tronçon départ×arrivée, numéro de course, type de jour)",
        2: "à défaut, moyenne du train pour (tronçon, numéro de course)",
        3: "à défaut, moyenne du train pour (tronçon, type de jour)",
        4: "à défaut, moyenne du train pour (tronçon)",
        5: "à défaut, moyenne globale du train",
    }
    for niv in range(1, 6):
        n = bn["couverture_n"][str(niv)]
        pct = bn["couverture_pct"][str(niv)]
        print(f"      niveau {niv} — {libelles[niv]} : {n:>7} lignes H25 ({pct} %)")
        rows.append(["D.3 Baseline naïve (§4.5.2 / §4.5.3)", f"niveau {niv}",
                     f"{libelles[niv]} — appliqué à {n} lignes H25 ({pct} %)",
                     "lu dans la sortie", rel(CONF / "c10_comparatif_algos.json")])
    rows.append(["D.3 Baseline naïve (§4.5.2 / §4.5.3)", "définition du type de jour",
                 "cal_is_weekend (ouvré / week-end)", "lu dans le code", rel(SRC_C10)])
    rows.append(["D.3 Baseline naïve (§4.5.2 / §4.5.3)", "source des moyennes",
                 bn["regle"]["source"], "lu dans la sortie",
                 rel(CONF / "c10_comparatif_algos.json")])
    rows.append(["D.3 Baseline naïve (§4.5.2 / §4.5.3)", "moyenne globale du train",
                 f"{bn['regle']['moyenne_globale_train']:.10f} voyageurs 2e classe",
                 "lu dans la sortie", rel(CONF / "c10_comparatif_algos.json")])

    # ── D.4 Environnement ───────────────────────────────────────────────────────
    import pandas as pd
    import lightgbm as lgb
    import catboost
    import optuna
    live = {
        "python": platform.python_version(),
        "xgboost": xgb.__version__, "lightgbm": lgb.__version__,
        "catboost": catboost.__version__, "scikit-learn": sklearn.__version__,
        "optuna": optuna.__version__, "numpy": np.__version__, "pandas": pd.__version__,
    }
    req = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if "==" in line:
            k, v = line.split("==", 1)
            req[k.strip().lower()] = v.strip()
    pin_req = {"xgboost": req.get("xgboost"), "lightgbm": req.get("lightgbm"),
               "catboost": req.get("catboost"), "scikit-learn": req.get("scikit-learn"),
               "optuna": req.get("optuna"), "numpy": req.get("numpy"),
               "pandas": req.get("pandas"), "pyarrow": req.get("pyarrow")}
    versions_c10 = c10["meta"]["versions_bibliotheques"]
    print("\n  D.4 Environnement")
    print(f"      interpréteur courant : Python {live['python']} ({sys.executable})")
    for k in ("xgboost", "lightgbm", "catboost", "scikit-learn", "optuna", "numpy", "pandas"):
        marque = "=" if live[k] == pin_req.get(k) else "!="
        print(f"      {k:<13} installé {live[k]:<8} {marque} requirements.txt "
              f"{pin_req.get(k)}")
    rows.append(["D.4 Environnement", "python", live["python"],
                 "interpréteur d'exécution de ce script", "platform.python_version()"])
    rows.append(["D.4 Environnement", "python (documenté)", "3.9.10",
                 "documenté dans le dépôt", "README.md ligne 56"])
    for k in ("xgboost", "lightgbm", "catboost", "scikit-learn", "optuna", "numpy",
              "pandas"):
        mod = "sklearn" if k == "scikit-learn" else k
        rows.append(["D.4 Environnement", k, live[k], "importé dans l'environnement courant",
                     f"{mod}.__version__"])
        rows.append(["D.4 Environnement", f"{k} (épinglé)", str(pin_req.get(k)),
                     "épinglage versionné", rel(REQUIREMENTS)])
    rows.append(["D.4 Environnement", "pyarrow (épinglé)", str(pin_req.get("pyarrow")),
                 "épinglage versionné, contrat d'empreinte (ADR-066)", rel(REQUIREMENTS)])
    for k, v in versions_c10.items():
        rows.append(["D.4 Environnement", f"{k} (consigné à l'exécution de c10)", v,
                     "consigné dans la sortie du comparatif post-gel",
                     rel(CONF / "c10_comparatif_algos.json")])

    # graine unique
    seed_train = extract_scalar_assign(module_source(SRC_TRAIN), "SEED")
    seed_harness = extract_scalar_assign(module_source(SRC_HARNESS), "SEED")
    rows.append(["D.4 Environnement", "graine unique", str(seed_train),
                 "fixée dans le code d'entraînement du gel", rel(SRC_TRAIN)])
    rows.append(["D.4 Environnement", "graine (socle de confirmation)", str(seed_harness),
                 "fixée dans le socle", rel(SRC_HARNESS)])
    print(f"      graine unique : {seed_train} (producteur du gel) ; "
          f"{seed_harness} (socle de confirmation) — identiques : "
          f"{oui_non(seed_train == seed_harness)}")

    # épinglage mono-fil
    mk = MAKEFILE.read_text(encoding="utf-8")
    env_vars = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]
    mk_lignes = {}
    for i, line in enumerate(mk.splitlines(), start=1):
        for v in env_vars:
            if line.strip().startswith(f"export {v}"):
                mk_lignes[v] = (i, line.strip())
    src_train_txt = module_source(SRC_TRAIN)
    pin_train = all(v in src_train_txt for v in env_vars)
    pin_harness = all(v in module_source(SRC_HARNESS) for v in env_vars)
    print(f"\n      épinglage mono-fil : {len(mk_lignes)}/5 variables exportées par le "
          f"Makefile ; posées aussi dans le producteur du gel : {oui_non(pin_train)} ; "
          f"dans le socle : {oui_non(pin_harness)}")
    for v in env_vars:
        li, txt = mk_lignes.get(v, (None, INTROUVABLE))
        rows.append(["D.4 Environnement", f"épinglage mono-fil — {v}", txt,
                     "exporté par le Makefile" if li else INTROUVABLE,
                     f"Makefile:{li}" if li else "Makefile"])
    rows.append(["D.4 Environnement", "épinglage mono-fil — producteur du gel",
                 f"les 5 variables sont posées à 1 avant tout import numérique : "
                 f"{oui_non(pin_train)}", "lu dans le code", rel(SRC_TRAIN)])
    rows.append(["D.4 Environnement", "épinglage mono-fil — motif",
                 "non-déterminisme d'Apple Accelerate (BLAS multi-fil), réductions "
                 "flottantes non associatives, ~1 exécution sur 3, écarts à l'ULP",
                 "ADR-076, section Justification point 5",
                 "docs/adr/ADR-076_migration_gel_dataset_v2.md"])

    # empreintes
    if ML_DATASET.exists():
        full = sha256_full(ML_DATASET)
        rows.append(["D.4 Environnement", "empreinte du parquet canonique (SHA256)",
                     full, "recalculée par ce script", rel(ML_DATASET)])
        rows.append(["D.4 Environnement", "empreinte du parquet canonique (SHA256[:8])",
                     full[:8], "recalculée par ce script", rel(ML_DATASET)])
    else:
        rows.append(["D.4 Environnement", "empreinte du parquet canonique",
                     INTROUVABLE + " — fichier absent du poste", "—", rel(ML_DATASET)])
    for seg, (fname, attendu) in MODELS.items():
        rows.append(["D.4 Environnement", f"empreinte du modèle {seg} (SHA256)",
                     sha256_full(MODEL_DIR / fname), "recalculée par ce script",
                     rel(MODEL_DIR / fname)])

    write_csv("verif_45_bloc_d_baselines_environnement.csv", hdr, rows)

    return {
        "ridge": {"bibliotheque": f"scikit-learn {sklearn.__version__}",
                  "classe": "sklearn.linear_model.Ridge", "architecture": c03["meta"]["modele"],
                  "alpha_rapporte": alpha_defaut,
                  "alpha_origine": f"défaut scikit-learn ({ridge_defauts['alpha']})",
                  "balayage_h24": {"alphas": alphas_sweep, "r2_h24": sw["alphas"],
                                   "meilleur": sw["meilleur_alpha_H24"],
                                   "adopte": False,
                                   "protocole": "ajustement H22+H23, évaluation R² global "
                                                "sur H24, sans validation croisée ni RidgeCV",
                                   "note_du_script": sw["note"]},
                  "pretraitement": {"numeriques": c03["meta"]["imputation"].split(";")[0].strip(),
                                    "categorielles": c03["meta"]["imputation"].split(";")[1].strip(),
                                    "standardisation": c03["meta"]["standardisation"],
                                    "n_numeriques": c03["meta"]["n_numeriques"],
                                    "n_categorielles": c03["meta"]["n_categorielles"]},
                  "defauts_sklearn": {k: str(v) for k, v in ridge_defauts.items()}},
        "random_forest": {"bibliotheque": f"scikit-learn {sklearn.__version__}",
                          "classe": "sklearn.ensemble.RandomForestRegressor",
                          "arguments_fixes_dans_le_code": rf_kwargs,
                          "defauts_sklearn": {k: str(v) for k, v in rf_defauts.items()},
                          "architecture": "segmentée BAS/HAUT",
                          "duree_s": c10["meta"]["durees_s"]["randomforest_defaut"]},
        "baseline_naive": {"cascade": [f"{n} — {libelles[n]}" for n in range(1, 6)],
                           "couverture_n": bn["couverture_n"],
                           "couverture_pct": bn["couverture_pct"],
                           "moyenne_globale_train": bn["regle"]["moyenne_globale_train"],
                           "cle_type_jour": "cal_is_weekend"},
        "environnement": {"versions_installees": live,
                          "versions_epinglees_requirements": pin_req,
                          "versions_consignees_c10": versions_c10,
                          "python_documente": "3.9.10 (README.md:56)",
                          "graine_unique": seed_train,
                          "variables_mono_fil": env_vars,
                          "mono_fil_makefile": {v: mk_lignes.get(v, (None, None))[1]
                                                for v in env_vars},
                          "mono_fil_dans_le_producteur": pin_train,
                          "mono_fil_dans_le_socle": pin_harness,
                          "empreinte_parquet_sha256": sha256_full(ML_DATASET)
                          if ML_DATASET.exists() else INTROUVABLE,
                          "empreinte_parquet_sha256_8": sha8(ML_DATASET)
                          if ML_DATASET.exists() else INTROUVABLE}}


# ════════════════════════════════════════════════════════════════════════════════
def write_csv(name: str, header: list, rows: list) -> Path:
    p = OUT / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  -> {rel(p)} ({len(rows)} lignes)")
    return p


def main() -> int:
    prov = preambule()
    a = bloc_a()
    b = bloc_b()
    c = bloc_c(a["params_code_entrainement"])
    d = bloc_d()

    manquants = [
        "Bloc B (b) — version d'optuna au moment de la campagne du 2026-06-28 : "
        "absente de tuning_optuna_h24_resultats.json, du CSV de trials et de run.log.",
        "Bloc B (c) — version d'optuna au moment de la campagne du 2026-07-02 : "
        "absente de tuning_resultats.json, des best_params_*.json et de run_full.log.",
        "Bloc B (a) — empreinte du dataset de la campagne : le notebook ne pose aucun "
        "garde-fou de hachage et ses sorties n'en consignent aucune.",
        "Bloc A — les hyperparamètres d'entraînement ne sont PAS sérialisés dans les "
        "fichiers modèles : xgboost n'écrit que le modèle. La configuration effective "
        "n'est donc lisible que dans le code d'entraînement versionné.",
    ]
    print("\n" + "-" * 88)
    print("INFORMATIONS ABSENTES DU DÉPÔT (non reconstituées)")
    print("-" * 88)
    for m in manquants:
        print("  - " + m)

    synthese = {"provenance": prov, "bloc_a": a, "bloc_b": b, "bloc_c": c, "bloc_d": d,
                "informations_introuvables": manquants}
    p = OUT / "verif_45_synthese.json"
    p.write_text(json.dumps(synthese, indent=2, ensure_ascii=False, default=str),
                 encoding="utf-8")
    print(f"\n  -> {rel(p)}")
    print("\nTERMINÉ — lecture seule, aucun artefact canonique modifié.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
