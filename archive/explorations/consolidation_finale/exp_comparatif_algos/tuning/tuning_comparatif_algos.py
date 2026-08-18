"""
Tuning comparatif XGBoost / LightGBM / CatBoost par Optuna — architecture segmentée
====================================================================================
HORS CANONIQUE. Ne touche NI au hash 416bb90b, NI au ml_dataset, NI au pipeline,
NI aux modèles canoniques (lecture seule stricte).

OBJECTIF
  Comparer XGBoost, LightGBM et CatBoost, chacun optimisé par Optuna au MÊME budget,
  dans l'architecture SEGMENTÉE de l'artefact (un modèle BAS + un modèle HAUT, aiguillage
  par spatial_segment — exactement comme CF09), pour déterminer le meilleur régresseur de
  charge. Aucune promotion de modèle : la décision reste ouverte, prise au vu des résultats.

VERROU MÉTHODOLOGIQUE (absolu)
  - Le tuning Optuna se fait EXCLUSIVEMENT sur le train (H22 hors Gilamont + H23 + H24, Split C).
  - H25 n'est JAMAIS vu pendant l'optimisation, sous aucune forme.
  - H25 n'est révélé qu'UNE SEULE FOIS, tout à la fin, sur les modèles déjà figés,
    + CF09 comme repère + baseline naïve comme plancher.

VALIDATION OPTUNA
  - Walk-forward temporel à 3 plis, construit UNIQUEMENT à l'intérieur du train, par DATE
    (expanding window, ordre chronologique strict, aucune fuite futur -> passé).
  - Métrique optimisée : RMSE de validation, moyenné sur les 3 plis, calculé sur les deux
    segments RÉUNIS (critère unique par essai). RMSE = juge principal (cohérent ADR-CF09).

BUDGET & ÉCHANTILLONNAGE
  - 40 essais Optuna par algorithme, échantillonneur TPE, seed 42.
  - Early stopping (40 rounds) pendant chaque essai ; plafond d'arbres = 600.
  - HP PARTAGÉS entre BAS et HAUT dans un essai (comme CF09) ; n_arbres déterminé par
    early stopping (moyenne des best_iteration des 3 plis, par segment) pour le refit final.

ARCHITECTURE : segmentée pour les 3 algos. JAMAIS de modèle global monolithique.

Usage : python tuning_comparatif_algos.py [n_trials]   (défaut 40 ; utiliser 2 pour smoke test)
Arrêt après la table de résultats. Aucune décision de promotion.
"""

import sys, json, hashlib, time, warnings, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score, mean_squared_error

import optuna

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

ROOT      = Path(__file__).resolve().parents[3]
OUT_CANON = ROOT / "consolidation_finale" / "outputs"
HERE      = Path(__file__).resolve().parent
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = OUT_CANON / "features_158f_sans_simba.json"
CANON_Q6  = OUT_CANON / "q6_resultats_416bb90b.json"
CANON_PRED = OUT_CANON / "q6_predictions_h25_158f_416bb90b.parquet"   # prédictions CF09 figées (lecture seule)

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
N_TRIALS       = int(sys.argv[1]) if len(sys.argv) > 1 else 40
MAX_TREES      = 600
EARLY_STOP     = 40
TARGET         = "target_voyageurs_2eme_classe"

# Colonnes clés baseline naïve (plancher H1) — identiques au comparatif défaut
BL_TRONCON = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]
BL_COURSE  = "horaire_numero_train"
BL_TYPEJ   = "cal_is_weekend"

print("=" * 82)
print(f"TUNING COMPARATIF Optuna — XGB/LGBM/CatBoost segmentés — {N_TRIALS} essais/algo — seed {SEED}")
print("=" * 82)

# ══════════════════════════════════════════════════════════════════════════════
# 0. DATASET (lecture seule) + garde-fou hash
# ══════════════════════════════════════════════════════════════════════════════
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash attendu {HASH_ATTENDU}, obtenu {file_hash} — ARRÊT"
print(f"\n── 0. Dataset ──\n  Hash SHA256[:8] = {file_hash} ✓ (canonique intact, lecture seule)")

df = pd.read_parquet(PARQUET)
FEATS = json.load(open(FEAT_JSON))["features"]
assert len(FEATS) == 158
CAT_FEATS = [c for c in FEATS if str(df[c].dtype) in ("object", "string", "category")]
print(f"  {len(df):,} lignes · {len(FEATS)} features · {len(CAT_FEATS)} catégorielles")

# ══════════════════════════════════════════════════════════════════════════════
# 1. SPLIT C + segments
# ══════════════════════════════════════════════════════════════════════════════
h22_all  = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = ((h22_all["id_gare_depart_bpuic"].astype(int) == GILAMONT_BPUIC) |
            (h22_all["id_gare_arrivee_bpuic"].astype(int) == GILAMONT_BPUIC))
train = pd.concat([h22_all[~mask_gil], df[df["horaire_annee_horaire"].isin(["H23", "H24"])]],
                  ignore_index=True)
h25   = df[df["horaire_annee_horaire"] == "H25"].copy().reset_index(drop=True)
assert len(train) == 801282 and len(h25) == 309252
print(f"\n── 1. Split C ──\n  Train={len(train):,}  H25={len(h25):,} (révélé une seule fois, à la fin)")


def prep_X(d):
    X = d[[c for c in FEATS if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X


def cb_prep(X):
    """CatBoost : catégorielles en str, aucune NaN (vérifié)."""
    Xc = X.copy()
    for c in CAT_FEATS:
        Xc[c] = Xc[c].astype("string").fillna("NA").astype(str)
    return Xc


# ── Matrices train globales (préparation canonique) ──
X_train = prep_X(train)
y_train = train[TARGET].values.astype("float64")
seg_train = train["spatial_segment"].values
dates_train = train["base_date"].values

# ── H25 (préparé mais NON utilisé avant la section finale) ──
X_h25 = prep_X(h25)
y_h25 = h25[TARGET].values.astype("float64")
mask_b_h25 = (h25["spatial_segment"] == "bas").values
mask_h_h25 = (h25["spatial_segment"] == "haut").values

# ══════════════════════════════════════════════════════════════════════════════
# 2. PLIS WALK-FORWARD (date-based, expanding window, DANS le train uniquement)
# ══════════════════════════════════════════════════════════════════════════════
udates = np.sort(pd.unique(dates_train))
chunks = np.array_split(udates, 4)   # 4 blocs chronologiques -> 3 plis expanding
FOLDS = []   # (train_pos, val_pos)
for k in range(3):
    tr_dates  = np.concatenate(chunks[:k + 1])
    val_dates = chunks[k + 1]
    tr_pos  = np.where(np.isin(dates_train, tr_dates))[0]
    val_pos = np.where(np.isin(dates_train, val_dates))[0]
    FOLDS.append((tr_pos, val_pos))
print("\n── 2. Plis walk-forward (expanding, par date, train-only) ──")
for k, (tp, vp) in enumerate(FOLDS):
    print(f"  Pli {k+1} : train={len(tp):>7,} (<= {pd.Timestamp(chunks[k].max()).date()})"
          f"  val={len(vp):>7,} ({pd.Timestamp(chunks[k+1].min()).date()} -> {pd.Timestamp(chunks[k+1].max()).date()})")


# ══════════════════════════════════════════════════════════════════════════════
# 3. ESPACES DE RECHERCHE (générosité comparable, adaptés par bibliothèque)
#    Chacun : learning_rate (log) · complexité (depth/leaves) · subsample lignes ·
#    subsample colonnes · 2-3 termes de régularisation. n_arbres via early stopping (<=600).
# ══════════════════════════════════════════════════════════════════════════════
def space_xgb(t):
    return dict(
        learning_rate    = t.suggest_float("learning_rate", 0.01, 0.3, log=True),
        max_depth        = t.suggest_int("max_depth", 3, 10),
        subsample        = t.suggest_float("subsample", 0.6, 1.0),
        colsample_bytree = t.suggest_float("colsample_bytree", 0.6, 1.0),
        min_child_weight = t.suggest_int("min_child_weight", 1, 10),
        reg_lambda       = t.suggest_float("reg_lambda", 1e-2, 10.0, log=True),
        reg_alpha        = t.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
    )

def space_lgbm(t):
    return dict(
        learning_rate     = t.suggest_float("learning_rate", 0.01, 0.3, log=True),
        num_leaves        = t.suggest_int("num_leaves", 15, 255),
        max_depth         = t.suggest_int("max_depth", 3, 12),
        subsample         = t.suggest_float("subsample", 0.6, 1.0),
        colsample_bytree  = t.suggest_float("colsample_bytree", 0.6, 1.0),
        min_child_samples = t.suggest_int("min_child_samples", 5, 100),
        reg_lambda        = t.suggest_float("reg_lambda", 1e-2, 10.0, log=True),
        reg_alpha         = t.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
    )

def space_catboost(t):
    return dict(
        learning_rate    = t.suggest_float("learning_rate", 0.01, 0.3, log=True),
        depth            = t.suggest_int("depth", 4, 10),
        subsample        = t.suggest_float("subsample", 0.6, 1.0),
        rsm              = t.suggest_float("rsm", 0.6, 1.0),
        min_data_in_leaf = t.suggest_int("min_data_in_leaf", 1, 100),
        l2_leaf_reg      = t.suggest_float("l2_leaf_reg", 1.0, 30.0, log=True),
        random_strength  = t.suggest_float("random_strength", 1e-3, 10.0, log=True),
    )

SPACES_DOC = {
    "xgboost": {
        "learning_rate": "loguniform[0.01,0.3]", "max_depth": "int[3,10]",
        "subsample": "unif[0.6,1.0]", "colsample_bytree": "unif[0.6,1.0]",
        "min_child_weight": "int[1,10]", "reg_lambda": "loguniform[1e-2,10]",
        "reg_alpha": "loguniform[1e-3,10]", "n_estimators": f"<= {MAX_TREES} via early stopping ({EARLY_STOP})",
    },
    "lightgbm": {
        "learning_rate": "loguniform[0.01,0.3]", "num_leaves": "int[15,255]", "max_depth": "int[3,12]",
        "subsample": "unif[0.6,1.0] (bagging_freq=1)", "colsample_bytree": "unif[0.6,1.0]",
        "min_child_samples": "int[5,100]", "reg_lambda": "loguniform[1e-2,10]",
        "reg_alpha": "loguniform[1e-3,10]", "n_estimators": f"<= {MAX_TREES} via early stopping ({EARLY_STOP})",
    },
    "catboost": {
        "learning_rate": "loguniform[0.01,0.3]", "depth": "int[4,10]",
        "subsample": "unif[0.6,1.0] (bootstrap Bernoulli)", "rsm": "unif[0.6,1.0]",
        "min_data_in_leaf": "int[1,100]", "l2_leaf_reg": "loguniform[1,30]",
        "random_strength": "loguniform[1e-3,10]", "iterations": f"<= {MAX_TREES} via early stopping ({EARLY_STOP})",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# 4. ENTRAÎNEMENT D'UN SEGMENT (avec early stopping) — par bibliothèque
#    Retourne (predictions_val, best_iteration). Utilisé en CV et pour le refit.
# ══════════════════════════════════════════════════════════════════════════════
def fit_predict_seg(algo, params, Xtr, ytr, Xva, yva, n_final=None):
    """Si n_final is None -> early stopping (CV). Sinon -> refit figé à n_final arbres, prédit Xva."""
    if algo == "xgboost":
        import xgboost as xgb
        if n_final is None:
            m = xgb.XGBRegressor(n_estimators=MAX_TREES, early_stopping_rounds=EARLY_STOP,
                                 objective="reg:squarederror", tree_method="hist",
                                 enable_categorical=True, random_state=SEED, verbosity=0, **params)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
            bi = int(m.best_iteration)
            pred = m.predict(Xva, iteration_range=(0, bi + 1)).astype("float64")
            return pred, bi
        m = xgb.XGBRegressor(n_estimators=n_final, objective="reg:squarederror", tree_method="hist",
                             enable_categorical=True, random_state=SEED, verbosity=0, **params)
        m.fit(Xtr, ytr, verbose=False)
        return m.predict(Xva).astype("float64"), n_final

    if algo == "lightgbm":
        import lightgbm as lgb
        p = dict(params); p["subsample_freq"] = 1   # active le bagging de lignes
        if n_final is None:
            m = lgb.LGBMRegressor(n_estimators=MAX_TREES, random_state=SEED, n_jobs=-1, verbose=-1, **p)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)],
                  categorical_feature=CAT_FEATS,
                  callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False), lgb.log_evaluation(0)])
            bi = int(m.best_iteration_)
            return m.predict(Xva, num_iteration=bi).astype("float64"), bi
        m = lgb.LGBMRegressor(n_estimators=n_final, random_state=SEED, n_jobs=-1, verbose=-1, **p)
        m.fit(Xtr, ytr, categorical_feature=CAT_FEATS)
        return m.predict(Xva).astype("float64"), n_final

    if algo == "catboost":
        from catboost import CatBoostRegressor
        Xtr_c, Xva_c = cb_prep(Xtr), cb_prep(Xva)
        if n_final is None:
            m = CatBoostRegressor(iterations=MAX_TREES, od_type="Iter", od_wait=EARLY_STOP,
                                  bootstrap_type="Bernoulli", loss_function="RMSE",
                                  random_seed=SEED, thread_count=-1, verbose=0, **params)
            m.fit(Xtr_c, ytr, eval_set=(Xva_c, yva), cat_features=CAT_FEATS, use_best_model=True)
            bi = int(m.get_best_iteration())
            return m.predict(Xva_c).astype("float64"), bi
        m = CatBoostRegressor(iterations=n_final, bootstrap_type="Bernoulli", loss_function="RMSE",
                              random_seed=SEED, thread_count=-1, verbose=0, **params)
        m.fit(Xtr_c, ytr, cat_features=CAT_FEATS)
        return m.predict(Xva_c).astype("float64"), n_final

    raise ValueError(algo)


SPACE_FN = {"xgboost": space_xgb, "lightgbm": space_lgbm, "catboost": space_catboost}


# ══════════════════════════════════════════════════════════════════════════════
# 5. OBJECTIF OPTUNA — CV walk-forward, RMSE combiné (BAS+HAUT réunis), moyenné 3 plis
# ══════════════════════════════════════════════════════════════════════════════
def make_objective(algo):
    def objective(trial):
        params = SPACE_FN[algo](trial)
        fold_rmses, bi_bas, bi_haut = [], [], []
        for (tr_pos, val_pos) in FOLDS:
            seg_tr, seg_va = seg_train[tr_pos], seg_train[val_pos]
            Xtr, ytr = X_train.iloc[tr_pos], y_train[tr_pos]
            Xva, yva = X_train.iloc[val_pos], y_train[val_pos]
            pred_va = np.empty(len(val_pos), "float64")
            for seg, bi_list in (("bas", bi_bas), ("haut", bi_haut)):
                m_tr, m_va = (seg_tr == seg), (seg_va == seg)
                p, bi = fit_predict_seg(algo, params,
                                        Xtr[m_tr], ytr[m_tr], Xva[m_va], yva[m_va])
                pred_va[m_va] = p
                bi_list.append(bi)
            rmse = float(np.sqrt(mean_squared_error(yva, pred_va)))  # combiné, deux segments réunis
            fold_rmses.append(rmse)
        trial.set_user_attr("fold_rmses", fold_rmses)
        trial.set_user_attr("n_bas",  int(round(np.mean(bi_bas)  + 1)))
        trial.set_user_attr("n_haut", int(round(np.mean(bi_haut) + 1)))
        return float(np.mean(fold_rmses))
    return objective


# ══════════════════════════════════════════════════════════════════════════════
# 6. MÉTRIQUES H25 (identiques au comparatif défaut, + RMSE juge principal)
# ══════════════════════════════════════════════════════════════════════════════
def metrics(y_true, y_pred, seuil=SEUIL):
    y_true = np.asarray(y_true, "float64"); y_pred = np.asarray(y_pred, "float64")
    m_z = y_true > seuil; n_surch = int(m_z.sum())
    res = y_pred[m_z] - y_true[m_z] if n_surch else None
    y_bin = (y_true > seuil).astype(int)
    return {
        "n_obs": int(len(y_true)), "n_surch": n_surch,
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "mae_gt63": float(np.abs(res).mean()) if n_surch else None,
        "bias_gt63": float(res.mean()) if n_surch else None,
        "pr_auc_troncon": float(average_precision_score(y_bin, y_pred)) if y_bin.sum() else None,
    }

def seg_metrics(yp):
    return {"global": metrics(y_h25, yp),
            "bas":    metrics(y_h25[mask_b_h25], yp[mask_b_h25]),
            "haut":   metrics(y_h25[mask_h_h25], yp[mask_h_h25])}


# ══════════════════════════════════════════════════════════════════════════════
# 7. BOUCLE PRINCIPALE : tuning -> refit figé -> (H25 gardé pour la fin)
# ══════════════════════════════════════════════════════════════════════════════
seg_tr_full = seg_train
STUDIES, BEST = {}, {}
FROZEN_PRED_H25 = {}

for algo in ["xgboost", "lightgbm", "catboost"]:
    print(f"\n{'='*82}\n  OPTUNA — {algo.upper()}  ({N_TRIALS} essais, TPE seed {SEED})\n{'='*82}")
    t0 = time.time()
    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(make_objective(algo), n_trials=N_TRIALS, show_progress_bar=False)
    dt = time.time() - t0
    bt = study.best_trial
    folds = bt.user_attrs["fold_rmses"]
    print(f"  [{dt/60:.1f} min] best CV-RMSE = {bt.value:.4f}  "
          f"(plis={['%.4f'%f for f in folds]}, std={np.std(folds):.4f})")
    print(f"  best params : {bt.params}")
    print(f"  n_arbres refit : BAS={bt.user_attrs['n_bas']}  HAUT={bt.user_attrs['n_haut']}")

    # Sauvegarde HP + trials
    (HERE / f"best_params_{algo}.json").write_text(json.dumps({
        "algo": algo, "n_trials": N_TRIALS, "seed": SEED,
        "best_cv_rmse_mean": bt.value, "cv_rmse_folds": folds, "cv_rmse_std": float(np.std(folds)),
        "best_params": bt.params, "n_arbres_bas": bt.user_attrs["n_bas"],
        "n_arbres_haut": bt.user_attrs["n_haut"],
        "search_space": SPACES_DOC[algo],
        "tuning_minutes": round(dt / 60, 2),
    }, indent=2, ensure_ascii=False))
    study.trials_dataframe().to_csv(HERE / f"trials_{algo}.csv", index=False)

    # ── Refit figé sur le TRAIN COMPLET (H25 toujours non vu) ──
    print(f"  Refit figé sur train complet ({algo}) …")
    m_b_tr, m_h_tr = (seg_tr_full == "bas"), (seg_tr_full == "haut")
    m_b_te, m_h_te = mask_b_h25, mask_h_h25
    yp = np.empty(len(h25), "float64")
    pb, _ = fit_predict_seg(algo, bt.params, X_train[m_b_tr], y_train[m_b_tr],
                            X_h25[m_b_te], y_h25[m_b_te], n_final=bt.user_attrs["n_bas"])
    ph, _ = fit_predict_seg(algo, bt.params, X_train[m_h_tr], y_train[m_h_tr],
                            X_h25[m_h_te], y_h25[m_h_te], n_final=bt.user_attrs["n_haut"])
    yp[m_b_te] = pb; yp[m_h_te] = ph
    FROZEN_PRED_H25[algo] = yp
    STUDIES[algo] = {"best_cv_rmse": bt.value, "cv_folds": folds, "cv_std": float(np.std(folds)),
                     "n_bas": bt.user_attrs["n_bas"], "n_haut": bt.user_attrs["n_haut"]}
    BEST[algo] = bt.params


# ══════════════════════════════════════════════════════════════════════════════
# 8. RÉVÉLATION H25 — UNE SEULE FOIS. Modèles figés + CF09 (repère) + baseline (plancher)
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*82}\n  RÉVÉLATION H25 (une seule fois) — modèles figés + CF09 + baseline\n{'='*82}")
RESULTS = {}
for algo in ["xgboost", "lightgbm", "catboost"]:
    RESULTS[f"{algo} (Optuna seg)"] = seg_metrics(FROZEN_PRED_H25[algo])

# ── CF09 : prédictions figées lues depuis l'artefact canonique (lecture seule) ──
cf_pred = pd.read_parquet(CANON_PRED)
assert (cf_pred[TARGET].values == y_h25).all(), "Ordre H25 CF09 non aligné"
RESULTS["CF09 canonique (repère)"] = seg_metrics(cf_pred["pred_enrichi_seg"].values.astype("float64"))

# ── Baseline naïve historique (plancher H1) — même règle que le comparatif défaut ──
def baseline_naive():
    tr = train[BL_TRONCON + [BL_COURSE, BL_TYPEJ, TARGET]].copy()
    tr["dep"] = tr[BL_TRONCON[0]].astype("int64"); tr["arr"] = tr[BL_TRONCON[1]].astype("int64")
    tr["cse"] = tr[BL_COURSE].astype("int64");     tr["tjr"] = tr[BL_TYPEJ].astype("int64")
    L = [tr.groupby(g)[TARGET].mean().to_dict() for g in
         (["dep", "arr", "cse", "tjr"], ["dep", "arr", "cse"], ["dep", "arr", "tjr"], ["dep", "arr"])]
    Lg = float(tr[TARGET].mean())
    hk = h25.copy()
    hk["dep"] = hk[BL_TRONCON[0]].astype("int64"); hk["arr"] = hk[BL_TRONCON[1]].astype("int64")
    hk["cse"] = hk[BL_COURSE].astype("int64");     hk["tjr"] = hk[BL_TYPEJ].astype("int64")
    dep, arr, cse, tjr = hk["dep"].values, hk["arr"].values, hk["cse"].values, hk["tjr"].values
    yp = np.full(len(hk), np.nan)
    for i in range(len(hk)):
        for lvl, key in enumerate([(dep[i], arr[i], cse[i], tjr[i]), (dep[i], arr[i], cse[i]),
                                    (dep[i], arr[i], tjr[i]), (dep[i], arr[i])]):
            if key in L[lvl]:
                yp[i] = L[lvl][key]; break
        else:
            yp[i] = Lg
    return yp
RESULTS["Baseline naïve (plancher)"] = seg_metrics(baseline_naive())

# ══════════════════════════════════════════════════════════════════════════════
# 9. TABLE DE RÉSULTATS + JSON
# ══════════════════════════════════════════════════════════════════════════════
ORDER = ["xgboost (Optuna seg)", "lightgbm (Optuna seg)", "catboost (Optuna seg)",
         "CF09 canonique (repère)", "Baseline naïve (plancher)"]

def f(v, nd=4):
    return "    —" if v is None else f"{v:.{nd}f}"

print("\n" + "=" * 100)
print("TABLE DE RÉSULTATS — H25 (une seule fois), Split C, 158f, seed 42  |  RMSE = juge principal")
print("=" * 100)
for seg in ("global", "bas", "haut"):
    print(f"\n### Segment {seg.upper()}")
    print(f"{'Modèle':<28} {'RMSE':>8} {'R²':>8} {'PR-AUC':>8} {'MAE':>8} {'MAE>63':>8} {'biais>63':>9}")
    print("-" * 82)
    for name in ORDER:
        m = RESULTS[name][seg]
        print(f"{name:<28} {f(m['rmse'],3):>8} {f(m['r2']):>8} {f(m['pr_auc_troncon']):>8} "
              f"{f(m['mae'],3):>8} {f(m['mae_gt63'],2):>8} {f(m['bias_gt63'],2):>9}")

# ── Rappel CV (juge principal, sur validation train) ──
print("\n" + "=" * 82)
print("VALIDATION (train walk-forward 3 plis) — CV-RMSE moyen ± std inter-plis")
print("=" * 82)
for algo in ["xgboost", "lightgbm", "catboost"]:
    s = STUDIES[algo]
    print(f"  {algo:<10} CV-RMSE={s['best_cv_rmse']:.4f}  std_inter-plis={s['cv_std']:.4f}  "
          f"plis={['%.4f'%x for x in s['cv_folds']]}")

# ── Verdict factuel (critère pré-posé) ──
cv_vals = {a: STUDIES[a]["best_cv_rmse"] for a in ["xgboost", "lightgbm", "catboost"]}
cv_stds = {a: STUDIES[a]["cv_std"] for a in ["xgboost", "lightgbm", "catboost"]}
spread_cv = max(cv_vals.values()) - min(cv_vals.values())
typ_std   = float(np.mean(list(cv_stds.values())))
h25_vals  = {a: RESULTS[f"{a} (Optuna seg)"]["global"]["rmse"] for a in ["xgboost", "lightgbm", "catboost"]}
spread_h25 = max(h25_vals.values()) - min(h25_vals.values())
best_cv  = min(cv_vals, key=cv_vals.get)
best_h25 = min(h25_vals, key=h25_vals.get)
indiscernable = spread_cv < typ_std
verdict = (f"INDISCERNABLES sur le RMSE (écart inter-algos CV={spread_cv:.4f} < variabilité inter-plis={typ_std:.4f}). "
           "Le choix relève des critères secondaires (explicabilité, intégration Dataiku, maturité, maîtrise).") \
    if indiscernable else \
    (f"GAGNANT CV={best_cv} (écart inter-algos CV={spread_cv:.4f} >= variabilité inter-plis={typ_std:.4f}) ; "
     f"à confirmer sur H25 (meilleur H25={best_h25}).")

print("\n" + "=" * 82)
print("VERDICT (critère pré-posé, métrique d'arbitrage = RMSE, non modifiée a posteriori)")
print("=" * 82)
print(f"  écart inter-algos CV-RMSE = {spread_cv:.4f}  |  variabilité inter-plis moyenne = {typ_std:.4f}")
print(f"  meilleur CV = {best_cv}  |  meilleur H25 = {best_h25}  |  écart inter-algos H25 = {spread_h25:.4f}")
print(f"  => {verdict}")

payload = {
    "script": "tuning_comparatif_algos.py",
    "objet": "Tuning comparatif Optuna XGB/LGBM/CatBoost segmentés — sélection régresseur couche 1",
    "hors_canonique": True, "promotion_modele": False,
    "dataset_hash": HASH_ATTENDU, "n_features": len(FEATS), "seed": SEED,
    "n_trials_par_algo": N_TRIALS, "max_trees": MAX_TREES, "early_stopping_rounds": EARLY_STOP,
    "architecture": "segmentée (BAS+HAUT, HP partagés par essai, aiguillage spatial_segment) — jamais de global",
    "verrou_h25": "H25 jamais vu au tuning ; révélé une seule fois sur modèles figés",
    "validation": "walk-forward 3 plis expanding par date, DANS le train ; RMSE combiné (2 segments réunis), moyenné",
    "search_spaces": SPACES_DOC,
    "cv": STUDIES,
    "resultats_h25": RESULTS,
    "verdict": {
        "metrique_arbitrage": "RMSE (juge principal, non modifiée a posteriori)",
        "spread_cv_rmse": spread_cv, "variabilite_inter_plis_moy": typ_std,
        "spread_h25_rmse": spread_h25, "meilleur_cv": best_cv, "meilleur_h25": best_h25,
        "indiscernable": bool(indiscernable), "texte": verdict,
    },
    "cf09_source": "q6_predictions_h25_158f_416bb90b.parquet (lecture seule, non ré-entraîné)",
    "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
}
(HERE / "tuning_resultats.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
print(f"\n  Sauvegardé → tuning_resultats.json + best_params_*.json + trials_*.csv")

# Garde-fou final : hash intact
assert hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8] == HASH_ATTENDU
print("\n" + "=" * 82)
print(f"TERMINÉ — hash {HASH_ATTENDU} intact. Arrêt après la table. Aucune promotion de modèle.")
print("=" * 82)
