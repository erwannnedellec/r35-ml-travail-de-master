"""
CHANTIER HYPERPARAMÈTRES — tuning Optuna documenté (validation H24)
===================================================================
EXPÉRIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI au modèle
canonique. Aucun modèle sauvegardé. H25 JAMAIS chargé. Rien dans le rapport.

Objectif double
---------------
(1) Documenter une procédure d'optimisation HP défendable (réponse au point
    soulevé par le directeur du travail de master : HP actuels ADR-CF09 non
    justifiés méthodologiquement).
(2) Vérifier si de meilleurs HP améliorent quelque chose. Attendu : reg:squarederror
    vise toujours la moyenne → biais>63 et PR-AUC ne devraient PAS bouger
    significativement. Le tuning confirme/documente. Constat rapporté honnêtement.

Méthode
-------
Optuna, sampler TPE (bayésien), multi-objectif (front de Pareto).
  directions = [maximize R²_global_H24, minimize |biais>63_H24|]
  (pas de combinaison pondérée arbitraire → pas de λ injustifiable)
PAS de cross-validation aléatoire (violerait la causalité temporelle).

Protocole (identique aux phases perte)
--------------------------------------
  train      = H22 (Gilamont 8501260 exclu) + H23
  validation = H24   ;   H25 jamais chargé pour le choix
  Par segment BAS/HAUT séparément (HP optimaux peuvent différer).
  Perte = reg:squarederror (canonique). Seed=42. ~50 essais.

Observables loggés par essai (pas objectifs) : PR-AUC tronçon, PR-AUC tour,
MAE>63, MAE globale — pour surveiller si la séparabilité bouge (probablement non).
"""

import json, hashlib, time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb
import optuna
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

optuna.logging.set_verbosity(optuna.logging.WARNING)

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_hpo"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
N_TRIALS       = 50
TARGET         = "target_voyageurs_2eme_classe"

# HP actuels canoniques (ADR-CF09) — point de référence
HP_ACTUELS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    min_child_weight=1, reg_lambda=1.0, reg_alpha=0.0, gamma=0.0,
)
FIXED = dict(objective="reg:squarederror", tree_method="hist",
             random_state=SEED, enable_categorical=True, verbosity=0, n_jobs=-1)

print("=" * 80)
print("CHANTIER HYPERPARAMÈTRES — tuning Optuna multi-objectif (VALIDATION H24)")
print("=" * 80)

# ── 0. Dataset ──────────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Dataset ──  Hash {file_hash} ✓ (lecture seule)")
df = pd.read_parquet(PARQUET)
with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158

# ── 1. Split VALIDATION (H25 jeté) ──────────────────────────────────────────
h22 = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = (
    (h22["id_gare_depart_bpuic"].astype("int64")  == GILAMONT_BPUIC) |
    (h22["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC)
)
train = pd.concat([h22[~mask_gil].copy(),
                   df[df["horaire_annee_horaire"] == "H23"].copy()], ignore_index=True)
valid = df[df["horaire_annee_horaire"] == "H24"].copy()
del df
print(f"── 1. Split ──  train(H22_valid+H23)={len(train):,}  valid(H24)={len(valid):,}")

def prep_X(d, feats=FEATS):
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X

mb_tr = (train["spatial_segment"] == "bas").values
mh_tr = (train["spatial_segment"] == "haut").values
mb_va = (valid["spatial_segment"] == "bas").values
mh_va = (valid["spatial_segment"] == "haut").values
X_tr = {"bas": prep_X(train[mb_tr]), "haut": prep_X(train[mh_tr])}
X_va = {"bas": prep_X(valid[mb_va]), "haut": prep_X(valid[mh_va])}
y_tr = {"bas": train.loc[mb_tr, TARGET].values.astype("float64"),
        "haut": train.loc[mh_tr, TARGET].values.astype("float64")}
y_va = {"bas": valid.loc[mb_va, TARGET].values.astype("float64"),
        "haut": valid.loc[mh_va, TARGET].values.astype("float64")}
tkey = {"bas":  list(zip(valid.loc[mb_va, "base_date"], valid.loc[mb_va, "horaire_numero_train"])),
        "haut": list(zip(valid.loc[mh_va, "base_date"], valid.loc[mh_va, "horaire_numero_train"]))}

def pr_auc_tour(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp})
    agg = g.groupby("k").agg(mo=("obs", "max"), mp=("pred", "max"))
    yb = (agg["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, agg["mp"].values)) if yb.sum() else None

def eval_seg(seg, params):
    m = xgb.XGBRegressor(**params, **FIXED)
    m.fit(X_tr[seg], y_tr[seg])
    yp = m.predict(X_va[seg]).astype("float64")
    yt = y_va[seg]; z = yt > SEUIL; res = yp - yt
    return {
        "r2": float(r2_score(yt, yp)),
        "bias_gt63": float(res[z].mean()),
        "abs_bias_gt63": float(abs(res[z].mean())),
        "mae_gt63": float(np.abs(res[z]).mean()),
        "mae_global": float(mean_absolute_error(yt, yp)),
        "pr_auc_troncon": float(average_precision_score((yt > SEUIL).astype(int), yp)),
        "pr_auc_tour": pr_auc_tour(tkey[seg], yt, yp),
    }

# ── 2. Référence : HP actuels (ADR-CF09) sur H24 ────────────────────────────
print("\n── 2. Référence HP actuels (ADR-CF09) sur H24 ──")
ref = {}
for seg in ("bas", "haut"):
    ref[seg] = eval_seg(seg, HP_ACTUELS)
    r = ref[seg]
    print(f"  {seg:>4}: R²={r['r2']:.4f}  biais>63={r['bias_gt63']:+.2f}  "
          f"PR-AUC_tr={r['pr_auc_troncon']:.4f}  MAE>63={r['mae_gt63']:.2f}  MAEglob={r['mae_global']:.3f}")

# ── 3. Optuna multi-objectif par segment ────────────────────────────────────
def make_objective(seg):
    def objective(trial):
        params = dict(
            max_depth        = trial.suggest_int("max_depth", 3, 10),
            learning_rate    = trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            n_estimators     = trial.suggest_int("n_estimators", 100, 600),
            subsample        = trial.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree = trial.suggest_float("colsample_bytree", 0.6, 1.0),
            min_child_weight = trial.suggest_int("min_child_weight", 1, 10),
            reg_lambda       = trial.suggest_float("reg_lambda", 0.0, 5.0),
            reg_alpha        = trial.suggest_float("reg_alpha", 0.0, 2.0),
            gamma            = trial.suggest_float("gamma", 0.0, 5.0),
        )
        m = eval_seg(seg, params)
        trial.set_user_attr("pr_auc_troncon", m["pr_auc_troncon"])
        trial.set_user_attr("pr_auc_tour", m["pr_auc_tour"])
        trial.set_user_attr("mae_gt63", m["mae_gt63"])
        trial.set_user_attr("mae_global", m["mae_global"])
        trial.set_user_attr("bias_gt63", m["bias_gt63"])
        return m["r2"], m["abs_bias_gt63"]    # maximize R², minimize |biais>63|
    return objective

studies = {}
for seg in ("bas", "haut"):
    print(f"\n── 3.{seg} Optuna TPE multi-objectif — segment {seg.upper()} ({N_TRIALS} essais) ──")
    t0 = time.time()
    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=optuna.samplers.TPESampler(seed=SEED),
        study_name=f"hpo_{seg}_h24",
    )
    study.optimize(make_objective(seg), n_trials=N_TRIALS, show_progress_bar=False)
    studies[seg] = study
    print(f"  Terminé en {time.time()-t0:.0f}s  |  {len(study.best_trials)} points sur le front de Pareto")

# ── 4. Export trials + Pareto ───────────────────────────────────────────────
OUT.mkdir(parents=True, exist_ok=True)
all_rows = []
for seg in ("bas", "haut"):
    for t in studies[seg].trials:
        all_rows.append({
            "segment": seg, "trial": t.number,
            "r2": t.values[0] if t.values else None,
            "abs_bias_gt63": t.values[1] if t.values else None,
            "bias_gt63": t.user_attrs.get("bias_gt63"),
            "pr_auc_troncon": t.user_attrs.get("pr_auc_troncon"),
            "pr_auc_tour": t.user_attrs.get("pr_auc_tour"),
            "mae_gt63": t.user_attrs.get("mae_gt63"),
            "mae_global": t.user_attrs.get("mae_global"),
            "is_pareto": t in studies[seg].best_trials,
            **{f"hp_{k}": v for k, v in t.params.items()},
        })
df_trials = pd.DataFrame(all_rows)
df_trials.to_csv(OUT / "tuning_optuna_h24_trials.csv", index=False)
print(f"\n  Trials → tuning_optuna_h24_trials.csv ({len(df_trials)} lignes)")

# ── 5. Figures : Pareto, importances, historique ────────────────────────────
def fig_pareto(seg):
    s = studies[seg]
    fig, ax = plt.subplots(figsize=(8, 6))
    rs  = [t.values[0] for t in s.trials if t.values]
    bs  = [t.values[1] for t in s.trials if t.values]
    ax.scatter(bs, rs, c="#bbbbbb", s=28, label="essais", zorder=2)
    par = sorted(s.best_trials, key=lambda t: t.values[1])
    ax.plot([t.values[1] for t in par], [t.values[0] for t in par],
            "-o", color="#d6604d", ms=7, label="front de Pareto", zorder=3)
    ax.scatter([ref[seg]["abs_bias_gt63"]], [ref[seg]["r2"]],
               marker="*", s=320, color="#2166ac", edgecolor="k", linewidth=0.8,
               label="HP actuels (ADR-CF09)", zorder=4)
    ax.set_xlabel("|biais >63|  (minimiser →)")
    ax.set_ylabel("R² global H24  (← maximiser)")
    ax.set_title(f"Front de Pareto HPO — segment {seg.upper()} (validation H24)\n"
                 f"reg:squarederror, {N_TRIALS} essais TPE", fontsize=11)
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(OUT / f"pareto_{seg}_h24.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure → pareto_{seg}_h24.png")

def fig_importances(seg):
    s = studies[seg]
    for ti, tname in [(0, "R2"), (1, "abs_bias_gt63")]:
        try:
            imp = optuna.importance.get_param_importances(s, target=lambda t: t.values[ti])
            fig, ax = plt.subplots(figsize=(8, 5))
            names = list(imp.keys())[::-1]; vals = list(imp.values())[::-1]
            ax.barh(names, vals, color="#4393c3")
            ax.set_xlabel("importance (fANOVA)")
            ax.set_title(f"Importance HP — {seg.upper()} / cible {tname} (H24)", fontsize=11)
            plt.tight_layout()
            fig.savefig(OUT / f"param_importance_{seg}_{tname}_h24.png", dpi=200, bbox_inches="tight")
            plt.close(fig)
            print(f"  Figure → param_importance_{seg}_{tname}_h24.png")
        except Exception as e:
            print(f"  (importance {seg}/{tname} indisponible : {e})")

def fig_history(seg):
    s = studies[seg]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    rs = [t.values[0] for t in s.trials if t.values]
    bs = [t.values[1] for t in s.trials if t.values]
    nums = [t.number for t in s.trials if t.values]
    axes[0].plot(nums, rs, "o-", ms=4, color="#1a9850"); axes[0].axhline(ref[seg]["r2"], ls="--", color="#2166ac", label="ADR-CF09")
    axes[0].set_title(f"{seg.upper()} — R² par essai"); axes[0].set_xlabel("essai"); axes[0].set_ylabel("R²"); axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].plot(nums, bs, "o-", ms=4, color="#d73027"); axes[1].axhline(ref[seg]["abs_bias_gt63"], ls="--", color="#2166ac", label="ADR-CF09")
    axes[1].set_title(f"{seg.upper()} — |biais>63| par essai"); axes[1].set_xlabel("essai"); axes[1].set_ylabel("|biais>63|"); axes[1].legend(); axes[1].grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(OUT / f"history_{seg}_h24.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure → history_{seg}_h24.png")

print("\n── 5. Figures ──")
for seg in ("bas", "haut"):
    fig_pareto(seg); fig_importances(seg); fig_history(seg)

# ── 6. Points Pareto saillants + table comparative ──────────────────────────
def pareto_points(seg):
    s = studies[seg]
    bt = s.best_trials
    best_r2   = max(bt, key=lambda t: t.values[0])
    best_bias = min(bt, key=lambda t: t.values[1])
    # knee : normalise R² et |bias| sur le front, point le plus proche de l'idéal
    rs = np.array([t.values[0] for t in bt]); bsv = np.array([t.values[1] for t in bt])
    rn = (rs - rs.min()) / (rs.ptp() + 1e-12)
    bn = (bsv - bsv.min()) / (bsv.ptp() + 1e-12)
    knee = bt[int(np.argmin((1 - rn) ** 2 + bn ** 2))]
    return {"best_R2": best_r2, "best_bias": best_bias, "knee": knee}

def trial_metrics(t):
    return {
        "r2": t.values[0], "bias_gt63": t.user_attrs.get("bias_gt63"),
        "abs_bias_gt63": t.values[1],
        "pr_auc_troncon": t.user_attrs.get("pr_auc_troncon"),
        "pr_auc_tour": t.user_attrs.get("pr_auc_tour"),
        "mae_gt63": t.user_attrs.get("mae_gt63"),
        "mae_global": t.user_attrs.get("mae_global"),
        "params": t.params,
    }

summary = {
    "experiment": "CHANTIER HPO — tuning Optuna multi-objectif, validation H24",
    "statut": "EXPÉRIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact",
    "methode": "Optuna TPE multi-objectif [maximize R²_H24, minimize |biais>63_H24|], pas de CV aléatoire",
    "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; H25 jamais touché",
    "perte": "reg:squarederror (canonique)", "n_trials": N_TRIALS, "seed": SEED,
    "dataset_hash": HASH_ATTENDU, "n_features": len(FEATS), "seuil": SEUIL,
    "hp_actuels_adr_cf09": HP_ACTUELS,
    "reference_h24": ref,
    "pareto": {},
}
for seg in ("bas", "haut"):
    pts = pareto_points(seg)
    summary["pareto"][seg] = {
        "n_pareto": len(studies[seg].best_trials),
        "best_R2":   trial_metrics(pts["best_R2"]),
        "best_bias": trial_metrics(pts["best_bias"]),
        "knee":      trial_metrics(pts["knee"]),
    }
(OUT / "tuning_optuna_h24_resultats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

# ── 7. Tables imprimées ─────────────────────────────────────────────────────
def print_table(seg):
    pts = summary["pareto"][seg]; r = ref[seg]
    print(f"\n{'─'*94}\nTABLE H24 — segment {seg.upper()}  (HP actuels vs points Pareto)\n{'─'*94}")
    print(f"{'config':>22} | {'R²':>7} | {'biais>63':>9} | {'MAE>63':>7} | {'MAEglob':>8} | {'PRAUC_tr':>8} | {'PRAUC_to':>8}")
    print("-" * 94)
    def row(lab, m):
        print(f"{lab:>22} | {m['r2']:>7.4f} | {m['bias_gt63']:>+9.2f} | {m['mae_gt63']:>7.2f} | "
              f"{m['mae_global']:>8.3f} | {m['pr_auc_troncon']:>8.4f} | {(m['pr_auc_tour'] or 0):>8.4f}")
    row("HP actuels (CF09)", r)
    row("Pareto best-R²", pts["best_R2"])
    row("Pareto knee", pts["knee"])
    row("Pareto best-biais", pts["best_bias"])
    # deltas best-R² vs actuels
    b = pts["best_R2"]
    print(f"  Δ best-R² vs actuels : R²={b['r2']-r['r2']:+.4f}  biais>63={b['bias_gt63']-r['bias_gt63']:+.2f}  "
          f"PR-AUC_tr={b['pr_auc_troncon']-r['pr_auc_troncon']:+.4f}  PR-AUC_to={(b['pr_auc_tour'] or 0)-(r['pr_auc_tour'] or 0):+.4f}")

for seg in ("bas", "haut"):
    print_table(seg)

print(f"\n{'='*80}")
print(f"Fichiers : {OUT}")
print("ARRÊT — optimisation H24 seule. NE PAS valider sur H25 ni réentraîner le canonique.")
print("=" * 80)
