"""
CHANTIER HYPERPARAMÈTRES — re-tuning Optuna sur la BONNE cible couche 1
======================================================================
Cible = PR-AUC TRONÇON GLOBALE (grain natif du prédicteur, réunion BAS+HAUT au
tronçon — PAS la moyenne des PR-AUC de segment, PAS le tour qui relève couche 2).
EXPERIMENTAL — HORS canonique (`exp_hpo/`). Ne touche NI au hash 416bb90b, NI au
pipeline, NI aux modèles canoniques. Aucun modèle sauvegardé. H25 JAMAIS chargé
(ni tuning ni choix). ARRÊT après validation H24.

Méthode
-------
Optuna TPE, **objectif unique = MAXIMIZE PR-AUC tronçon globale (H24)**.
HP **PARTAGÉS** BAS/HAUT (comme CF09) : à chaque essai, mêmes HP pour les deux
modèles, entraîner les deux, réunir les prédictions au tronçon, calculer la PR-AUC
tronçon globale. Pas de CV aléatoire (causalité temporelle).
  train = H22(Gilamont exclu)+H23  →  validation H24.  ~50 essais. seed=42.
Observables loggés (NON optimisés) : PR-AUC tour globale, R² global, biais>63 global,
PR-AUC tronçon par segment — pour surveiller les contreparties.

Garde-fou
---------
La fonction PR-AUC tronçon globale est IDENTIQUE à celle validée en Phase C (a
reproduit la PR-AUC tronçon canonique globale H25 = 0,4490 à Δ=0). Ici, contrôle
in-protocole : CF09 (HP partagés) sur H24 doit reproduire la référence Phase B
(PR-AUC tronçon globale H24 = 0,4759).
"""
import json, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, average_precision_score
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

HASH_ATTENDU, GILAMONT_BPUIC, SEUIL, SEED, N_TRIALS = "416bb90b", 8501260, 63, 42, 50
TARGET = "target_voyageurs_2eme_classe"
REF_H24_PRAUC_TRONCON_GLOBAL = 0.4759  # Phase B, CF09, H24 (garde-fou in-protocole)

HP_ACTUELS = dict(n_estimators=300, max_depth=6, learning_rate=0.1,
                  subsample=0.8, colsample_bytree=0.8,
                  min_child_weight=1, reg_lambda=1.0, reg_alpha=0.0, gamma=0.0)
FIXED = dict(objective="reg:squarederror", tree_method="hist",
             random_state=SEED, enable_categorical=True, verbosity=0, n_jobs=-1)

print("=" * 80)
print("CHANTIER HP — re-tuning Optuna sur PR-AUC TRONÇON GLOBALE (validation H24)")
print("=" * 80)

# ── 0. Dataset ──────────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Hash {file_hash} ✓ (lecture seule)")
df = pd.read_parquet(PARQUET)
FEATS = json.load(open(FEAT_JSON))["features"]; assert len(FEATS) == 158

# ── 1. Split (H25 jeté) ─────────────────────────────────────────────────────
h22 = df[df["horaire_annee_horaire"] == "H22"]
mgil = ((h22["id_gare_depart_bpuic"].astype("int64") == GILAMONT_BPUIC) |
        (h22["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC))
train = pd.concat([h22[~mgil].copy(), df[df["horaire_annee_horaire"] == "H23"].copy()], ignore_index=True)
valid = df[df["horaire_annee_horaire"] == "H24"].copy()
del df

def prep_X(d):
    X = d[[c for c in FEATS if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"): X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"): X[c] = X[c].astype("float64")
    return X

mb_tr = (train["spatial_segment"] == "bas").values; mh_tr = (train["spatial_segment"] == "haut").values
mb_va = (valid["spatial_segment"] == "bas").values; mh_va = (valid["spatial_segment"] == "haut").values
X_tr = {"bas": prep_X(train[mb_tr]), "haut": prep_X(train[mh_tr])}
X_va = {"bas": prep_X(valid[mb_va]), "haut": prep_X(valid[mh_va])}
y_tr = {"bas": train.loc[mb_tr, TARGET].values.astype("float64"), "haut": train.loc[mh_tr, TARGET].values.astype("float64")}
y_va_g = valid[TARGET].values.astype("float64")
yb_va_g = (y_va_g > SEUIL).astype(int)
base_score = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tkey_g = list(zip(valid["base_date"], valid["horaire_numero_train"]))
print(f"── 1. train={len(train):,} valid(H24)={len(valid):,} | >63 global={int(yb_va_g.sum())}")

# ── 2. Cible : PR-AUC tronçon GLOBALE (réunion BAS+HAUT) ────────────────────
def fit_predict_global(params):
    """Entraîne BAS et HAUT avec les MÊMES HP, réunit les prédictions au tronçon."""
    yp_g = np.empty(len(valid))
    seg_tr = {}
    for s in ("bas", "haut"):
        m = xgb.XGBRegressor(base_score=base_score[s], **params, **FIXED)
        m.fit(X_tr[s], y_tr[s])
        p = m.predict(X_va[s]).astype("float64")
        yp_g[mb_va if s == "bas" else mh_va] = p
        seg_tr[s] = float(average_precision_score((y_va_g[mb_va if s == "bas" else mh_va] > SEUIL).astype(int), p))
    return yp_g, seg_tr

def pr_auc_troncon_global(yp_g):
    return float(average_precision_score(yb_va_g, yp_g))

def pr_auc_tour_global(yp_g):
    g = pd.DataFrame({"k": tkey_g, "obs": y_va_g, "pred": yp_g}).groupby("k").agg(mo=("obs","max"), mp=("pred","max"))
    return float(average_precision_score((g["mo"].values > SEUIL).astype(int), g["mp"].values))

def observables(yp_g):
    z = yb_va_g.astype(bool); res = yp_g - y_va_g
    return {"pr_auc_troncon_global": pr_auc_troncon_global(yp_g),
            "pr_auc_tour_global": pr_auc_tour_global(yp_g),
            "r2_global": float(r2_score(y_va_g, yp_g)),
            "bias_gt63_global": float(res[z].mean())}

# ── 3. Garde-fou : CF09 reproduit la référence H24 (0,4759) ─────────────────
print("\n── 2. GARDE-FOU CF09 (HP partagés) sur H24 ──")
t0 = time.time()
yp_cf09, seg_cf09 = fit_predict_global(HP_ACTUELS)
obs_cf09 = observables(yp_cf09)
d_ref = abs(obs_cf09["pr_auc_troncon_global"] - REF_H24_PRAUC_TRONCON_GLOBAL)
print(f"  PR-AUC tronçon globale CF09 = {obs_cf09['pr_auc_troncon_global']:.4f} "
      f"(réf Phase B {REF_H24_PRAUC_TRONCON_GLOBAL}, Δ={d_ref:.4f}) "
      + ("✓" if d_ref < 1e-3 else "✗"))
print(f"  observables CF09 : PR-AUC_tour={obs_cf09['pr_auc_tour_global']:.4f} "
      f"R²={obs_cf09['r2_global']:.4f} biais>63={obs_cf09['bias_gt63_global']:+.2f} "
      f"| PR-AUC_tr BAS={seg_cf09['bas']:.4f} HAUT={seg_cf09['haut']:.4f}  ({time.time()-t0:.0f}s)")
assert d_ref < 1e-3, "Garde-fou échoué : CF09 ne reproduit pas la PR-AUC tronçon globale H24."

# ── 4. Optuna mono-objectif : MAXIMIZE PR-AUC tronçon globale ───────────────
print(f"\n── 3. Optuna TPE — MAXIMIZE PR-AUC tronçon globale ({N_TRIALS} essais) ──")
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
    yp_g, seg_tr = fit_predict_global(params)
    obs = observables(yp_g)
    for k, v in obs.items(): trial.set_user_attr(k, v)
    trial.set_user_attr("pr_auc_troncon_bas", seg_tr["bas"])
    trial.set_user_attr("pr_auc_troncon_haut", seg_tr["haut"])
    return obs["pr_auc_troncon_global"]

study = optuna.create_study(direction="maximize",
                            sampler=optuna.samplers.TPESampler(seed=SEED),
                            study_name="hpo_prauc_troncon_global_h24")
# injecter CF09 comme essai 0 (référence dans l'étude)
study.enqueue_trial(HP_ACTUELS)
t0 = time.time()
study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)
print(f"  Terminé en {time.time()-t0:.0f}s | best PR-AUC tronçon globale = {study.best_value:.4f}")

# ── 5. Export trials ────────────────────────────────────────────────────────
OUT.mkdir(parents=True, exist_ok=True)
rows = []
for t in study.trials:
    if t.values is None: continue
    rows.append({"trial": t.number, "pr_auc_troncon_global": t.value,
                 "pr_auc_tour_global": t.user_attrs.get("pr_auc_tour_global"),
                 "r2_global": t.user_attrs.get("r2_global"),
                 "bias_gt63_global": t.user_attrs.get("bias_gt63_global"),
                 "pr_auc_troncon_bas": t.user_attrs.get("pr_auc_troncon_bas"),
                 "pr_auc_troncon_haut": t.user_attrs.get("pr_auc_troncon_haut"),
                 **{f"hp_{k}": v for k, v in t.params.items()}})
dft = pd.DataFrame(rows).sort_values("pr_auc_troncon_global", ascending=False).reset_index(drop=True)
dft.to_csv(OUT / "tuning_prauc_troncon_h24_trials.csv", index=False)

# ── 6. Lecture : best vs CF09, stabilité, observables ───────────────────────
best = study.best_trial
HP_KEYS = ["max_depth","learning_rate","n_estimators","subsample","colsample_bytree",
           "min_child_weight","reg_lambda","reg_alpha","gamma"]
print("\n" + "=" * 80)
print("RÉSULTAT — best-PR-AUC-tronçon vs CF09 (validation H24)")
print("=" * 80)
gain = best.value - obs_cf09["pr_auc_troncon_global"]
print(f"  CF09  PR-AUC tronçon globale = {obs_cf09['pr_auc_troncon_global']:.4f}")
print(f"  BEST  PR-AUC tronçon globale = {best.value:.4f}   (Δ = {gain:+.4f})")
print(f"  best HP : " + "  ".join(f"{k}={best.params[k]:.4g}" if isinstance(best.params[k], float) else f"{k}={best.params[k]}" for k in HP_KEYS))
print(f"\n  Observables du best (contreparties) :")
print(f"    PR-AUC tour globale : {best.user_attrs['pr_auc_tour_global']:.4f}  (CF09 {obs_cf09['pr_auc_tour_global']:.4f}, Δ {best.user_attrs['pr_auc_tour_global']-obs_cf09['pr_auc_tour_global']:+.4f})")
print(f"    R² global           : {best.user_attrs['r2_global']:.4f}  (CF09 {obs_cf09['r2_global']:.4f}, Δ {best.user_attrs['r2_global']-obs_cf09['r2_global']:+.4f})")
print(f"    biais>63 global     : {best.user_attrs['bias_gt63_global']:+.2f}  (CF09 {obs_cf09['bias_gt63_global']:+.2f}, Δ {best.user_attrs['bias_gt63_global']-obs_cf09['bias_gt63_global']:+.2f})")
print(f"    PR-AUC tr BAS/HAUT  : {best.user_attrs['pr_auc_troncon_bas']:.4f} / {best.user_attrs['pr_auc_troncon_haut']:.4f}")

# stabilité : top-K essais
K = 8
top = dft.head(K)
print(f"\n  STABILITÉ — top-{K} essais (objectif PR-AUC tronçon globale) :")
print(f"    objectif : max={top['pr_auc_troncon_global'].max():.4f} min={top['pr_auc_troncon_global'].min():.4f} "
      f"écart={top['pr_auc_troncon_global'].max()-top['pr_auc_troncon_global'].min():.4f}")
print(f"    écart #1 vs #2 : {dft['pr_auc_troncon_global'].iloc[0]-dft['pr_auc_troncon_global'].iloc[1]:.4f} "
      f"(isolé si grand vs la dispersion du top)")
print(f"    {'HP':>18} {'CF09':>8} {'top-min':>9} {'top-med':>9} {'top-max':>9}")
for k in HP_KEYS:
    col = f"hp_{k}"; cf = HP_ACTUELS[k]
    print(f"    {k:>18} {cf:>8.4g} {top[col].min():>9.4g} {top[col].median():>9.4g} {top[col].max():>9.4g}")

# ── 7. Figures : historique + importance ────────────────────────────────────
def fig_history():
    fig, ax = plt.subplots(figsize=(10, 5))
    vals = [t.value for t in study.trials if t.value is not None]
    nums = [t.number for t in study.trials if t.value is not None]
    running = np.maximum.accumulate(vals)
    ax.plot(nums, vals, "o", ms=4, color="#888", label="essais")
    ax.plot(nums, running, "-", color="#1a9850", lw=2, label="meilleur courant")
    ax.axhline(obs_cf09["pr_auc_troncon_global"], ls="--", color="#2166ac", label="CF09")
    ax.set_xlabel("essai"); ax.set_ylabel("PR-AUC tronçon globale (H24)")
    ax.set_title(f"HPO PR-AUC tronçon globale — historique ({N_TRIALS} essais TPE)")
    ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
    fig.savefig(OUT / "history_prauc_troncon_h24.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    print("  Figure → history_prauc_troncon_h24.png")

def fig_importance():
    try:
        imp = optuna.importance.get_param_importances(study)
        fig, ax = plt.subplots(figsize=(8, 5))
        names = list(imp.keys())[::-1]; vals = list(imp.values())[::-1]
        ax.barh(names, vals, color="#4393c3"); ax.set_xlabel("importance (fANOVA)")
        ax.set_title("Importance HP — cible PR-AUC tronçon globale (H24)"); plt.tight_layout()
        fig.savefig(OUT / "param_importance_prauc_troncon_h24.png", dpi=200, bbox_inches="tight"); plt.close(fig)
        print("  Figure → param_importance_prauc_troncon_h24.png")
    except Exception as e:
        print(f"  (importance indisponible : {e})")

print("\n── 4. Figures ──")
fig_history(); fig_importance()

# ── 8. JSON résumé ──────────────────────────────────────────────────────────
(OUT / "tuning_prauc_troncon_h24_resultats.json").write_text(json.dumps({
    "experiment": "re-tuning Optuna cible PR-AUC tronçon globale (couche 1), validation H24",
    "statut": "EXPERIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact, H25 jamais touché",
    "cible": "MAXIMIZE PR-AUC tronçon globale H24 (réunion BAS+HAUT au tronçon, HP partagés)",
    "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; pas de CV aléatoire ; seed 42 ; 50 essais TPE",
    "garde_fou": {"cf09_pr_auc_troncon_global_h24": obs_cf09["pr_auc_troncon_global"],
                  "reference_phase_b": REF_H24_PRAUC_TRONCON_GLOBAL, "delta": d_ref,
                  "note": "fonction identique à Phase C qui reproduisait 0.4490 canonique H25 à Δ=0"},
    "cf09": {"hp": HP_ACTUELS, **obs_cf09, "pr_auc_troncon_bas": seg_cf09["bas"], "pr_auc_troncon_haut": seg_cf09["haut"]},
    "best": {"trial": best.number, "hp": best.params, "pr_auc_troncon_global": best.value,
             **{k: best.user_attrs.get(k) for k in ["pr_auc_tour_global","r2_global","bias_gt63_global","pr_auc_troncon_bas","pr_auc_troncon_haut"]}},
    "gain_vs_cf09": gain,
    "top_trials": dft.head(K).to_dict(orient="records"),
}, indent=2, ensure_ascii=False))

# ── 9. Verdict de lecture (H24 seulement) ───────────────────────────────────
print("\n" + "=" * 80)
NOISE = 0.01
ecart_top = top['pr_auc_troncon_global'].max() - top['pr_auc_troncon_global'].min()
if gain < NOISE:
    lecture = f"Gain {gain:+.4f} DANS LE BRUIT (<{NOISE}) → CF09 confirmé sur la PR-AUC tronçon globale."
elif ecart_top > gain:
    lecture = f"Gain {gain:+.4f} > bruit MAIS top-{K} dispersé (écart {ecart_top:.4f} ≥ gain) → robustesse douteuse."
else:
    lecture = f"Gain {gain:+.4f} FRANC et top-{K} resserré (écart {ecart_top:.4f}) → candidat à confirmer sur H25 (étape séparée)."
print("LECTURE (validation H24) :", lecture)
print("ARRÊT — H24 seulement. PAS de test H25, PAS d'adoption ici.")
print("=" * 80)
