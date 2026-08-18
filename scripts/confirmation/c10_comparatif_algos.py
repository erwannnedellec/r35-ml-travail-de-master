#!/usr/bin/env python3
"""
c10_comparatif_algos.py — confirmation post-gel du comparatif d'algorithmes (ADR-072).

Rejoue sur ba493568 le PERIMETRE COMPLET de la comparaison historique (ADR-072), en
LECTURE SEULE. La selection est FIGEE : le verdict d'ADR-072 (indiscernabilite des
boostings tunes, conservation de XGBoost aux HP CF09/ADR-052) n'est PAS rouvert ; ce run
confirme les chiffres sur le H25 corrige narcisses, il ne re-decide rien.

Bras (Split C, seed 42, threads numeriques = 1) :
  0. Canonique CF09 (gel, e4ddfccd/df6a11c5) : reference, LECTURE SEULE (non reentraine).
  1. Baseline naive moyenne historique : cle (troncon dep×arr, numero de course, type de jour
     ouvre/weekend), repli en cascade (course->troncon->global) ; AUCUNE donnee H25 dans la
     construction ; couverture des replis rapportee sur le H25 corrige.
  2. RandomForest sklearn defaut (seed 42, segmente) : comme le premier temps historique
     (n_jobs=-1 = vitesse seule, RF deterministe a random_state fixe ; encodage ordinal +
     imputation mediane du train, imposes par la bibliotheque).
  3-5. XGBoost / LightGBM / CatBoost aux best_params_*.json geles, SANS re-tuning (inchange).

Chaque bras : metriques preenregistrees completes bas/haut/global (R2 + IC bootstrap,
MAE, MAE>63, biais>63, PR-AUC seuil 63, prevalence, n_gt63) — l'arbitrage se joue sur la
zone >63 (ADR-072), donc >63 est rapporte pour TOUS les bras.

Sortie : outputs/confirmation/c10_comparatif_algos.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

TUNING = H.ROOT / "archive/explorations/consolidation_finale/exp_comparatif_algos/tuning"
CAT_FEATS = ["cal_jour_semaine", "cal_type_jour", "cal_type_jour_3classes",
             "event_ski_source", "event_covid_phase", "event_narcisses_source"]
TARGET = "target_voyageurs_2eme_classe"
BL_DEP, BL_ARR = "id_gare_depart_bpuic", "id_gare_arrivee_bpuic"
BL_CSE, BL_TJR = "horaire_numero_train", "cal_is_weekend"


def _seg_predict(train, test, feats, make_bas, make_haut, fit_fn, pred_fn):
    pred = np.empty(len(test), dtype="float64")
    for seg, make in (("bas", make_bas), ("haut", make_haut)):
        mtr = train[train["spatial_segment"] == seg]
        mte = test[test["spatial_segment"] == seg]
        m = make()
        fit_fn(m, H.prep_X(mtr, feats), H.y_of(mtr))
        pred[(test["spatial_segment"] == seg).values] = pred_fn(m, H.prep_X(mte, feats)).astype("float64")
    return pred


def _keys(d):
    return (d[BL_DEP].astype("int64").values, d[BL_ARR].astype("int64").values,
            d[BL_CSE].astype("int64").values, d[BL_TJR].astype("int64").values)


def baseline_naive(train, test):
    dep, arr, cse, tjr = _keys(train)
    tr = pd.DataFrame({"dep": dep, "arr": arr, "cse": cse, "tjr": tjr, TARGET: H.y_of(train)})
    L1 = tr.groupby(["dep", "arr", "cse", "tjr"])[TARGET].mean()
    L2 = tr.groupby(["dep", "arr", "cse"])[TARGET].mean()
    L3 = tr.groupby(["dep", "arr", "tjr"])[TARGET].mean()
    L4 = tr.groupby(["dep", "arr"])[TARGET].mean()
    L5 = float(tr[TARGET].mean())

    dep, arr, cse, tjr = _keys(test)

    def rdx(L, arrays):
        return L.reindex(pd.MultiIndex.from_arrays(arrays)).to_numpy(dtype="float64", na_value=np.nan)
    vs = [(1, rdx(L1, [dep, arr, cse, tjr])), (2, rdx(L2, [dep, arr, cse])),
          (3, rdx(L3, [dep, arr, tjr])), (4, rdx(L4, [dep, arr]))]
    pred = np.full(len(test), np.nan); level = np.zeros(len(test), int)
    for lv, v in vs:
        m = np.isnan(pred) & ~np.isnan(v)
        pred[m] = v[m]; level[m] = lv
    m = np.isnan(pred); pred[m] = L5; level[m] = 5
    cover = {int(l): int((level == l).sum()) for l in range(1, 6)}
    cover_pct = {l: round(100 * n / len(test), 2) for l, n in cover.items()}
    regle = {
        "cle_complete": "(troncon dep×arr bpuic, numero de course=horaire_numero_train, type_jour=cal_is_weekend)",
        "source": "moyenne target_voyageurs_2eme_classe sur TRAIN Split C (H22 hors Gilamont+H23+H24 ; aucune donnee H25)",
        "repli_cascade": ["1:(troncon,course,type_jour)", "2:(troncon,course)",
                          "3:(troncon,type_jour)", "4:(troncon)", "5:moyenne globale train"],
        "moyenne_globale_train": L5,
    }
    return pred, {"couverture_n": cover, "couverture_pct": cover_pct, "regle": regle}


def rf_predict(train, test, feats):
    from sklearn.ensemble import RandomForestRegressor
    num = [f for f in feats if f not in CAT_FEATS]
    cat_maps = {c: {v: i for i, v in enumerate(pd.Index(train[c].astype("string").dropna().unique()))}
                for c in CAT_FEATS}
    medians = {c: float(pd.to_numeric(train[c], errors="coerce").median()) for c in num}

    def tr_(d):
        out = pd.DataFrame(index=d.index)
        for c in num:
            out[c] = pd.to_numeric(d[c], errors="coerce").fillna(medians[c]).astype("float64")
        for c in CAT_FEATS:
            out[c] = d[c].astype("string").map(cat_maps[c]).fillna(-1).astype("float64")
        return out[feats].values

    pred = np.empty(len(test), dtype="float64")
    for seg in ("bas", "haut"):
        mtr = train[train["spatial_segment"] == seg]
        mte = test[test["spatial_segment"] == seg]
        rf = RandomForestRegressor(random_state=H.SEED, n_jobs=-1)   # defaut ; n_jobs = vitesse seule
        rf.fit(tr_(mtr), H.y_of(mtr))
        pred[(test["spatial_segment"] == seg).values] = rf.predict(tr_(mte)).astype("float64")
    return pred


def main() -> int:
    import xgboost as xgb
    import lightgbm as lgb
    import catboost
    from catboost import CatBoostRegressor
    import sklearn

    print("=== c10 — confirmation comparatif algos (ADR-072), Split C, ba493568 ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    train, test = H.split_c(df)
    print(f"  Split C : train={len(train)} | test H25={len(test)}")
    bp = {a: json.loads((TUNING / f"best_params_{a}.json").read_text())
          for a in ("xgboost", "lightgbm", "catboost")}

    def _cb_prep(X):
        Xc = X.copy()
        for c in CAT_FEATS:
            Xc[c] = Xc[c].astype("string").fillna("NA").astype(str)
        return Xc

    results, durees, extras = {}, {}, {}

    # 0. Canonique CF09 (gel, lecture seule)
    t0 = time.time()
    results["canonique_cf09_gel"] = H.metrics_by_segment(test, H.frozen_predict(test, feats))
    durees["canonique_cf09_gel"] = round(time.time() - t0, 1)
    print(f"  [canonique_cf09_gel] R2 global={results['canonique_cf09_gel']['global']['r2']:.6f} (lecture seule)")

    # 1. Baseline naive (moyenne historique)
    t0 = time.time()
    pred, extras["baseline_naive"] = baseline_naive(train, test)
    results["baseline_naive_moyenne_historique"] = H.metrics_by_segment(test, pred)
    durees["baseline_naive_moyenne_historique"] = round(time.time() - t0, 1)
    cov = extras["baseline_naive"]["couverture_pct"]
    print(f"  [baseline_naive] R2 global={results['baseline_naive_moyenne_historique']['global']['r2']:.6f} "
          f"| couverture N1={cov[1]}% N3={cov[3]}%")

    # 2. RandomForest defaut segmente
    t0 = time.time()
    results["randomforest_defaut"] = H.metrics_by_segment(test, rf_predict(train, test, feats))
    durees["randomforest_defaut"] = round(time.time() - t0, 1)
    print(f"  [randomforest_defaut] R2 global={results['randomforest_defaut']['global']['r2']:.6f} ({durees['randomforest_defaut']}s)")

    # 3. XGBoost best_params
    px = bp["xgboost"]["best_params"]; t0 = time.time()
    pred = _seg_predict(train, test, feats,
        lambda: xgb.XGBRegressor(**px, n_estimators=bp["xgboost"]["n_arbres_bas"], objective="reg:squarederror",
                                 tree_method="hist", enable_categorical=True, random_state=H.SEED, verbosity=0),
        lambda: xgb.XGBRegressor(**px, n_estimators=bp["xgboost"]["n_arbres_haut"], objective="reg:squarederror",
                                 tree_method="hist", enable_categorical=True, random_state=H.SEED, verbosity=0),
        lambda m, X, y: m.fit(X, y), lambda m, X: m.predict(X))
    results["xgboost_bestparams"] = H.metrics_by_segment(test, pred)
    durees["xgboost_bestparams"] = round(time.time() - t0, 1)
    print(f"  [xgboost_bestparams] R2 global={results['xgboost_bestparams']['global']['r2']:.6f} ({durees['xgboost_bestparams']}s)")

    # 4. LightGBM best_params
    pl = dict(bp["lightgbm"]["best_params"]); pl["subsample_freq"] = 1; t0 = time.time()
    pred = _seg_predict(train, test, feats,
        lambda: lgb.LGBMRegressor(**pl, n_estimators=bp["lightgbm"]["n_arbres_bas"], random_state=H.SEED, n_jobs=1, verbose=-1),
        lambda: lgb.LGBMRegressor(**pl, n_estimators=bp["lightgbm"]["n_arbres_haut"], random_state=H.SEED, n_jobs=1, verbose=-1),
        lambda m, X, y: m.fit(X, y, categorical_feature=CAT_FEATS), lambda m, X: m.predict(X))
    results["lightgbm_bestparams"] = H.metrics_by_segment(test, pred)
    durees["lightgbm_bestparams"] = round(time.time() - t0, 1)
    print(f"  [lightgbm_bestparams] R2 global={results['lightgbm_bestparams']['global']['r2']:.6f} ({durees['lightgbm_bestparams']}s)")

    # 5. CatBoost best_params
    pc = dict(bp["catboost"]["best_params"]); pc["bootstrap_type"] = "Bernoulli"; t0 = time.time()
    pred = _seg_predict(train, test, feats,
        lambda: CatBoostRegressor(**pc, iterations=bp["catboost"]["n_arbres_bas"], random_seed=H.SEED, verbose=0, thread_count=1),
        lambda: CatBoostRegressor(**pc, iterations=bp["catboost"]["n_arbres_haut"], random_seed=H.SEED, verbose=0, thread_count=1),
        lambda m, X, y: m.fit(_cb_prep(X), y, cat_features=CAT_FEATS), lambda m, X: m.predict(_cb_prep(X)))
    results["catboost_bestparams"] = H.metrics_by_segment(test, pred)
    durees["catboost_bestparams"] = round(time.time() - t0, 1)
    print(f"  [catboost_bestparams] R2 global={results['catboost_bestparams']['global']['r2']:.6f} ({durees['catboost_bestparams']}s)")

    valid_hist = {a: {"best_cv_rmse_mean": bp[a].get("best_cv_rmse_mean"),
                      "cv_rmse_folds": bp[a].get("cv_rmse_folds"), "cv_rmse_std": bp[a].get("cv_rmse_std"),
                      "n_arbres_bas": bp[a].get("n_arbres_bas"), "n_arbres_haut": bp[a].get("n_arbres_haut"),
                      "best_params": bp[a].get("best_params"),
                      "source": f"archive/explorations/consolidation_finale/exp_comparatif_algos/tuning/best_params_{a}.json"}
                  for a in ("xgboost", "lightgbm", "catboost")}

    payload = {
        "script": "c10_comparatif_algos.py",
        "role": "confirmation post-gel du comparatif d'algorithmes (ADR-072) sur ba493568, lecture seule",
        "adr_reference": "ADR-072",
        "h25_version": "corrigée narcisses (ba493568)",
        "selection_figee": ("Selection FIGEE (ADR-072) : verdict d'indiscernabilite des boostings tunes, "
                            "conservation de XGBoost et des HP CF09/ADR-052. Ce run CONFIRME les chiffres "
                            "post-gel en lecture seule ; il ne rouvre ni la selection d'algorithme ni les HP."),
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)),
                             extra={"perimetre": "canonique CF09 (gel) + baseline naive + RandomForest defaut + "
                                    "XGB/LGBM/CatBoost best_params (inchanges)",
                                    "architecture": "segmentee BAS/HAUT ; boostings n_estimators = n_arbres_{bas,haut} archives",
                                    "re_tuning": False, "cat_features": CAT_FEATS,
                                    "note_threads": "threads numeriques=1 (ADR-076) ; RandomForest n_jobs=-1 = vitesse seule "
                                    "(deterministe a random_state fixe), comme le premier temps historique",
                                    "manip_categorielles": "XGB category ; LGBM categorical_feature+subsample_freq=1 ; "
                                    "CatBoost cat_features str+bootstrap_type=Bernoulli ; RF encodage ordinal+imputation mediane",
                                    "durees_s": durees,
                                    "versions_bibliotheques": {"xgboost": xgb.__version__, "lightgbm": lgb.__version__,
                                        "catboost": catboost.__version__, "sklearn": sklearn.__version__, "numpy": np.__version__}}),
        "metriques_h25": results,
        "baseline_naive_details": extras["baseline_naive"],
        "h24_validation_historique": {
            "note": "validation walk-forward 3 plis expanding par date DANS le train (H22-H24), RMSE combine, "
                    "tuning d'epoque 416bb90b ; reportee telle quelle, non recalculee (boostings seulement)",
            "par_algo": valid_hist,
        },
        "model_reproduction": {
            "canonique_cf09_gel": {"archived": {"bas": H.HASH_MODEL_BAS, "haut": H.HASH_MODEL_HAUT},
                                   "retrained": None, "identical": True, "note": "gel reutilise en lecture seule"},
            "comparateurs": {"archived": None, "retrained": None, "identical": None,
                             "note": "sans objet : aucun artefact ba493568 archive pour naive/RF/boostings tunes"},
        },
    }
    out = H.write_json("c10_comparatif_algos.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
