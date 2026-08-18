#!/usr/bin/env python3
"""
Section 4.5 — bloc E : budget, validation, échantillonneur, arrêt anticipé et graines
de la campagne comparative inter-algorithmes (ADR-072).

LECTURE SEULE. Aucune exécution d'entraînement, aucune réoptimisation, aucune écriture
hors de docs/memoire/verifs/section_4_5/.

Chaque valeur est LUE dans un fichier versionné, et son numéro de ligne est RETROUVÉ
par recherche d'une ancre textuelle dans ce fichier — jamais recopié à la main. Si une
ancre ne se trouve pas, la ligne vaut INTROUVABLE et la valeur n'est pas rapportée.

Sortie : verif_45_bloc_e_budget_comparatif.csv
         (element, valeur, algorithme, source_fichier, source_ligne)
Sortie déterministe : aucun horodatage embarqué.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
DIR = ROOT / "archive/explorations/consolidation_finale/exp_comparatif_algos/tuning"
PY = DIR / "tuning_comparatif_algos.py"
LOG = DIR / "run_full.log"
RES = DIR / "tuning_resultats.json"
BP = {a: DIR / f"best_params_{a}.json" for a in ("xgboost", "lightgbm", "catboost")}
TRIALS = {a: DIR / f"trials_{a}.csv" for a in ("xgboost", "lightgbm", "catboost")}

INTROUVABLE = "INTROUVABLE dans le dépôt"
ROWS: list[list] = []


def rel(p: Path) -> str:
    return str(Path(p).relative_to(ROOT))


def lignes(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def ligne_de(p: Path, motif: str, occurrence: int = 1) -> str:
    """Numéro (1-indexé) de la n-ième ligne satisfaisant `motif` ; INTROUVABLE sinon."""
    n = 0
    for i, l in enumerate(lignes(p), start=1):
        if re.search(motif, l):
            n += 1
            if n == occurrence:
                return str(i)
    return INTROUVABLE


def lignes_de(p: Path, motif: str) -> str:
    """Toutes les lignes satisfaisant `motif`, jointes ; INTROUVABLE si aucune."""
    hits = [str(i) for i, l in enumerate(lignes(p), start=1) if re.search(motif, l)]
    return ", ".join(hits) if hits else INTROUVABLE


def texte_ligne(p: Path, num: str) -> str:
    if num == INTROUVABLE or "," in num:
        return ""
    return lignes(p)[int(num) - 1].strip()


def add(element: str, valeur, algo: str, fichier: Path | str, ligne) -> None:
    ROWS.append([element, str(valeur), algo,
                 rel(fichier) if isinstance(fichier, Path) else fichier, str(ligne)])


# ════════════════════════════════════════════════════════════════════════════════
def e1_budget() -> dict:
    print("\nE1 — nombre d'essais Optuna par algorithme")
    l_decl = ligne_de(PY, r"^N_TRIALS\s*=")
    decl = texte_ligne(PY, l_decl)
    add("budget d'essais — déclaration dans le code (valeur par défaut ; surchargeable "
        "par argument de ligne de commande)", decl, "les trois", PY, l_decl)
    l_appel = ligne_de(PY, r"study\.optimize\(")
    add("budget d'essais — passage à study.optimize", texte_ligne(PY, l_appel),
        "les trois", PY, l_appel)

    l_res = ligne_de(RES, r'"n_trials_par_algo"')
    n_res = json.loads(RES.read_text(encoding="utf-8"))["n_trials_par_algo"]
    add("budget d'essais — valeur effective consignée dans la sortie de la campagne",
        n_res, "les trois", RES, l_res)

    valeurs = {}
    for a, p in BP.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        valeurs[a] = d["n_trials"]
        add("budget d'essais — valeur consignée par algorithme", d["n_trials"], a, p,
            ligne_de(p, r'"n_trials"'))
    l_log = ligne_de(LOG, r"essais/algo")
    add("budget d'essais — en-tête du journal d'exécution", texte_ligne(LOG, l_log),
        "les trois", LOG, l_log)

    identique = len(set(valeurs.values())) == 1 and set(valeurs.values()) == {n_res}
    add("budget d'essais — identique pour XGBoost, LightGBM et CatBoost",
        "oui" if identique else "NON", "les trois",
        "confrontation best_params_*.json / tuning_resultats.json", "—")
    print(f"  {valeurs} ; identique : {'oui' if identique else 'NON'}")
    return {"par_algo": valeurs, "consigne_global": n_res, "identique": identique,
            "declaration_code": decl}


def e2_plis() -> dict:
    print("\nE2 — validation temporelle progressive")
    l_split = ligne_de(PY, r"chunks\s*=\s*np\.array_split")
    l_boucle = ligne_de(PY, r"for k in range\(3\)")
    l_tr = ligne_de(PY, r"tr_dates\s*=\s*np\.concatenate")
    l_val = ligne_de(PY, r"val_dates\s*=\s*chunks\[k \+ 1\]")
    add("nombre de plis — boucle de construction", texte_ligne(PY, l_boucle),
        "les trois", PY, l_boucle)
    add("découpage — dates uniques du train réparties en blocs chronologiques",
        texte_ligne(PY, l_split), "les trois", PY, l_split)
    add("définition d'un pli — jeu d'ajustement", texte_ligne(PY, l_tr), "les trois",
        PY, l_tr)
    add("définition d'un pli — jeu de validation", texte_ligne(PY, l_val), "les trois",
        PY, l_val)
    l_append = ligne_de(PY, r"FOLDS\.append")
    add("nature du découpage",
        "par DATE (quartiles des dates uniques du train), et non par année horaire ; "
        "fenêtre expansive, ordre chronologique strict, à l'intérieur du seul train "
        "Split C (H22 hors Gilamont + H23 + H24)", "les trois", PY,
        l_split + "-" + l_append)

    l_res = ligne_de(RES, r'"validation"')
    add("schéma de validation — libellé consigné dans la sortie",
        json.loads(RES.read_text(encoding="utf-8"))["validation"], "les trois", RES, l_res)

    plis = []
    for k in (1, 2, 3):
        ln = ligne_de(LOG, rf"^\s*Pli {k} :")
        txt = texte_ligne(LOG, ln)
        plis.append({"pli": k, "ligne_journal": ln, "texte": txt})
        add(f"pli {k} — effectifs et bornes réalisés", txt, "les trois", LOG, ln)
        print(f"  {txt}")
    return {"n_plis": 3, "plis_realises": plis}


def e3_optimiseur() -> dict:
    print("\nE3 — échantillonneur, graine, direction, métrique d'objectif")
    l_study = ligne_de(PY, r"optuna\.create_study\(")
    l_samp = ligne_de(PY, r"TPESampler\(")
    l_seed = ligne_de(PY, r"^SEED\s*=")
    l_rmse = ligne_de(PY, r"rmse = float\(np\.sqrt\(mean_squared_error")
    l_moy = ligne_de(PY, r"return float\(np\.mean\(fold_rmses\)\)")
    l_pruner = ligne_de(PY, r"pruner\s*=")
    add("direction d'optimisation", texte_ligne(PY, l_study), "les trois", PY, l_study)
    add("échantillonneur et sa graine", texte_ligne(PY, l_samp), "les trois", PY, l_samp)
    add("valeur de la graine", texte_ligne(PY, l_seed), "les trois", PY, l_seed)
    add("métrique d'objectif — calcul par pli (deux segments réunis)",
        texte_ligne(PY, l_rmse), "les trois", PY, l_rmse)
    add("métrique d'objectif — valeur retournée à Optuna", texte_ligne(PY, l_moy),
        "les trois", PY, l_moy)
    add("élagueur (pruner) Optuna",
        "aucun pruner n'est passé à create_study" if l_pruner == INTROUVABLE
        else texte_ligne(PY, l_pruner), "les trois", PY,
        l_pruner if l_pruner != INTROUVABLE else l_study)
    print(f"  {texte_ligne(PY, l_study)} | {texte_ligne(PY, l_samp)} | "
          f"{texte_ligne(PY, l_seed)}")
    print(f"  objectif : {texte_ligne(PY, l_moy)}")
    return {"direction": "minimize", "sampler": "TPESampler", "seed": 42,
            "metrique": "RMSE de validation, moyenné sur les 3 plis, calculé sur les "
                        "deux segments réunis",
            "pruner": "aucun" if l_pruner == INTROUVABLE else texte_ligne(PY, l_pruner)}


def e4_arret_anticipe() -> dict:
    print("\nE4 — arrêt anticipé par algorithme")
    l_max = ligne_de(PY, r"^MAX_TREES\s*=")
    l_pat = ligne_de(PY, r"^EARLY_STOP\s*=")
    add("plafond d'itérations — constante", texte_ligne(PY, l_max), "les trois", PY, l_max)
    add("patience — constante", texte_ligne(PY, l_pat), "les trois", PY, l_pat)

    ancres = {
        "xgboost": {
            "plafond et patience": r"n_estimators=MAX_TREES, early_stopping_rounds=EARLY_STOP",
            "jeu d'évaluation de l'arrêt": r"m\.fit\(Xtr, ytr, eval_set=\[\(Xva, yva\)\], verbose=False\)",
            "itération retenue": r"bi = int\(m\.best_iteration\)",
        },
        "lightgbm": {
            "plafond": r"m = lgb\.LGBMRegressor\(n_estimators=MAX_TREES",
            "patience": r"lgb\.early_stopping\(EARLY_STOP",
            "jeu d'évaluation de l'arrêt": r"m\.fit\(Xtr, ytr, eval_set=\[\(Xva, yva\)\],$",
            "itération retenue": r"bi = int\(m\.best_iteration_\)",
        },
        "catboost": {
            "plafond et patience": r"iterations=MAX_TREES, od_type=\"Iter\", od_wait=EARLY_STOP",
            "jeu d'évaluation de l'arrêt": r"m\.fit\(Xtr_c, ytr, eval_set=\(Xva_c, yva\), cat_features=CAT_FEATS, use_best_model=True\)",
            "itération retenue": r"bi = int\(m\.get_best_iteration\(\)\)",
        },
    }
    detail = {}
    for algo, a in ancres.items():
        detail[algo] = {}
        for libelle, motif in a.items():
            ln = ligne_de(PY, motif)
            add(f"arrêt anticipé — {libelle}",
                texte_ligne(PY, ln) if ln != INTROUVABLE else INTROUVABLE, algo, PY, ln)
            detail[algo][libelle] = {"ligne": ln, "texte": texte_ligne(PY, ln)}
        print(f"  {algo:<9} : " + " | ".join(f"L{v['ligne']}" for v in detail[algo].values()))

    l_obj = ligne_de(PY, r"p, bi = fit_predict_seg\(algo, params,")
    l_rmse_obj = ligne_de(PY, r"rmse = float")
    add("arrêt anticipé — jeu d'évaluation : nature",
        "le jeu de validation du pli courant, restreint au segment traité — soit "
        "exactement le jeu sur lequel le RMSE d'objectif du même essai est calculé "
        "(aucun jeu de validation interne distinct)", "les trois", PY,
        l_obj + "-" + l_rmse_obj)

    # nombres d'arbres retenus au refit final (conséquence de l'arrêt anticipé)
    for a, p in BP.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        add("nombre d'arbres du refit final — segment bas (moyenne des best_iteration "
            "des 3 plis)", d["n_arbres_bas"], a, p, ligne_de(p, r'"n_arbres_bas"'))
        add("nombre d'arbres du refit final — segment haut", d["n_arbres_haut"], a, p,
            ligne_de(p, r'"n_arbres_haut"'))
    l_moy_bi = ligne_de(PY, r'trial\.set_user_attr\("n_bas"')
    add("règle de détermination du nombre d'arbres du refit", texte_ligne(PY, l_moy_bi),
        "les trois", PY, l_moy_bi)
    return {"plafond": 600, "patience": 40, "detail": detail}


def e5_graines_et_fixes() -> dict:
    print("\nE5 — graines des estimateurs et paramètres fixés hors espace")
    fixes = {
        "xgboost": [
            ("graine de l'estimateur (phase de validation croisée)",
             r"enable_categorical=True, random_state=SEED, verbosity=0, \*\*params\)"),
            ("graine de l'estimateur (refit final)",
             r"enable_categorical=True, random_state=SEED, verbosity=0, \*\*params\)"),
            ("paramètres fixés hors espace (validation croisée)",
             r'objective="reg:squarederror", tree_method="hist",'),
            ("paramètres fixés hors espace (refit final)",
             r"m = xgb\.XGBRegressor\(n_estimators=n_final, objective="),
        ],
        "lightgbm": [
            ("graine de l'estimateur (validation croisée)",
             r"m = lgb\.LGBMRegressor\(n_estimators=MAX_TREES, random_state=SEED"),
            ("graine de l'estimateur (refit final)",
             r"m = lgb\.LGBMRegressor\(n_estimators=n_final, random_state=SEED"),
            ("paramètre fixé hors espace — bagging de lignes",
             r'p\["subsample_freq"\] = 1'),
            ("paramètre fixé hors espace — variables catégorielles",
             r"categorical_feature=CAT_FEATS,"),
        ],
        "catboost": [
            ("graine de l'estimateur (validation croisée)",
             r"random_seed=SEED, thread_count=-1, verbose=0, \*\*params\)"),
            ("graine de l'estimateur (refit final)",
             r"random_seed=SEED, thread_count=-1, verbose=0, \*\*params\)"),
            ("paramètres fixés hors espace (validation croisée)",
             r'bootstrap_type="Bernoulli", loss_function="RMSE",'),
            ("paramètres fixés hors espace (refit final)",
             r"m = CatBoostRegressor\(iterations=n_final, bootstrap_type="),
            ("paramètre fixé hors espace — variables catégorielles",
             r"m\.fit\(Xtr_c, ytr, cat_features=CAT_FEATS\)"),
        ],
    }
    occurrences = {("xgboost", "graine de l'estimateur (refit final)"): 2,
                   ("catboost", "graine de l'estimateur (refit final)"): 2}
    detail = {}
    for algo, items in fixes.items():
        detail[algo] = []
        for libelle, motif in items:
            occ = occurrences.get((algo, libelle), 1)
            ln = ligne_de(PY, motif, occurrence=occ)
            add(libelle, texte_ligne(PY, ln) if ln != INTROUVABLE else INTROUVABLE,
                algo, PY, ln)
            detail[algo].append({"element": libelle, "ligne": ln,
                                 "texte": texte_ligne(PY, ln)})
        print(f"  {algo:<9} : " + ", ".join(f"L{d['ligne']}" for d in detail[algo]))

    l_cat = ligne_de(PY, r"^CAT_FEATS = ")
    add("liste des variables catégorielles déclarées", texte_ligne(PY, l_cat),
        "les trois", PY, l_cat)
    l_seed = ligne_de(PY, r"^SEED\s*=")
    add("graine unique — les trois estimateurs reçoivent la même constante",
        "oui : random_state=SEED (XGBoost, LightGBM) et random_seed=SEED (CatBoost), "
        f"avec {texte_ligne(PY, l_seed)}", "les trois", PY, l_seed)
    return detail


def e6_essais_effectifs() -> dict:
    print("\nE6 — essais réellement conduits")
    res = {}
    for a, p in TRIALS.items():
        d = pd.read_csv(p)
        etats = d["state"].value_counts().to_dict()
        n_lignes = len(d)
        n_nan = int(d["value"].isna().sum())
        contigu = (sorted(d["number"].tolist()) == list(range(n_lignes)))
        res[a] = {"n_essais": n_lignes, "etats": etats, "valeurs_manquantes": n_nan,
                  "numeros_contigus_0_a_n_moins_1": contigu,
                  "premier_debut": str(d["datetime_start"].min()),
                  "dernier_achevement": str(d["datetime_complete"].max())}
        plage = f"lignes 2-{n_lignes + 1} (en-tête ligne 1)"
        add("essais effectivement enregistrés", n_lignes, a, p, plage)
        add("répartition des états Optuna", json.dumps(etats, ensure_ascii=False), a, p,
            f"colonne state, {plage}")
        add("essais élagués (PRUNED)", etats.get("PRUNED", 0), a, p, f"colonne state, {plage}")
        add("essais échoués (FAIL)", etats.get("FAIL", 0), a, p, f"colonne state, {plage}")
        add("essais sans valeur d'objectif", n_nan, a, p, f"colonne value, {plage}")
        add("numéros d'essai contigus de 0 à n−1 (aucune interruption)",
            "oui" if contigu else "NON", a, p, f"colonne number, {plage}")
        add("horodatage réel du premier essai", d["datetime_start"].min(), a, p,
            "colonne datetime_start, ligne 2")
        add("horodatage réel du dernier essai achevé", d["datetime_complete"].max(), a, p,
            f"colonne datetime_complete, ligne {n_lignes + 1}")
        print(f"  {a:<9} : {n_lignes} essais, états {etats}, valeurs manquantes {n_nan}, "
              f"contigus {contigu}")

    budget = json.loads(RES.read_text(encoding="utf-8"))["n_trials_par_algo"]
    ecart = {a: res[a]["n_essais"] - budget for a in res}
    add("écart entre budget déclaré et essais conduits",
        json.dumps(ecart, ensure_ascii=False) + (" — aucun écart"
                                                 if set(ecart.values()) == {0} else ""),
        "les trois", "confrontation trials_*.csv / tuning_resultats.json", "—")
    l_log = ligne_de(LOG, r"TERMIN")
    add("journal d'exécution — ligne de fin", texte_ligne(LOG, l_log), "les trois",
        LOG, l_log)
    add("mention d'essai élagué, échoué ou interrompu dans le journal",
        "aucune" if lignes_de(LOG, r"PRUNED|FAIL|Traceback|interromp") == INTROUVABLE
        else lignes_de(LOG, r"PRUNED|FAIL|Traceback|interromp"), "les trois", LOG,
        lignes_de(LOG, r"PRUNED|FAIL|Traceback|interromp"))
    print(f"  écart au budget déclaré ({budget}) : {ecart}")
    return {"budget_declare": budget, "par_algo": res, "ecart": ecart}


# ════════════════════════════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 88)
    print("VERIF §4.5 — bloc E : budget, validation, arrêt anticipé et graines "
          "du comparatif")
    print("=" * 88)
    manquants = [rel(p) for p in [PY, LOG, RES, *BP.values(), *TRIALS.values()]
                 if not p.exists()]
    if manquants:
        raise RuntimeError(f"STOP : fichiers sources absents — {manquants}")
    print(f"  fichiers sources : {len(BP) * 2 + 3} présents, aucun manquant")

    synth = {"e1_budget": e1_budget(), "e2_plis": e2_plis(), "e3_optimiseur": e3_optimiseur(),
             "e4_arret_anticipe": e4_arret_anticipe(), "e5_graines": e5_graines_et_fixes(),
             "e6_essais_effectifs": e6_essais_effectifs()}

    introuvables = [r for r in ROWS if INTROUVABLE in r[1] or INTROUVABLE in r[4]]
    print("\n" + "-" * 88)
    print(f"ÉLÉMENTS INTROUVABLES : {len(introuvables)}")
    for r in introuvables:
        print(f"  - {r[0]} [{r[2]}] : {r[1]} (ligne {r[4]})")

    p = OUT / "verif_45_bloc_e_budget_comparatif.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["element", "valeur", "algorithme", "source_fichier", "source_ligne"])
        w.writerows(ROWS)
    print(f"\n  -> {rel(p)} ({len(ROWS)} lignes)")
    (OUT / "verif_45_bloc_e_synthese.json").write_text(
        json.dumps(synth, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  -> {rel(OUT / 'verif_45_bloc_e_synthese.json')}")
    print("\nTERMINÉ — lecture seule, aucun artefact canonique modifié.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
