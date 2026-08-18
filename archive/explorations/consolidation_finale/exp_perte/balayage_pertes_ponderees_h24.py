"""
CHANTIER PERTE — Phase 4 : deux pertes pondérées centrées sur la zone de surcharge
==================================================================================
EXPERIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI aux modèles
canoniques. Aucun modèle sauvegardé. H25 JAMAIS chargé. Rien dans le rapport.

Forme commune : perte = w(obs)·½·a·r²,  r = pred − obs,  a = k si r<0 sinon 1.
  gradient g = w(obs)·a·r ;  hessien h = w(obs)·a  (>0 partout).
  FORME A (cloche centrée 63)  : w_A(obs) = exp(−(obs−63)²/(2σ²)).   σ∈{5,10,20}, k∈{1,2,3,5}
  FORME B (rampe à paliers)    : w_B(obs) = 1 si obs<63 ; W1 si 63≤obs≤94 ; W2 si obs>94.
                                 (W1,W2)∈{(2,4),(3,6),(5,10),(10,20)}, k∈{1,2,3,5}

Garde-fous (EN PREMIER) :
  - IMPL (machinerie partagée A/B) : w≡1, k=1 reproduit reg:squarederror bit-exact (allclose).
  - FORME A limite : σ=1000, k=1 ≈ MSE (w_A→~plat ; Δpred rapporté, ARRÊT si > 0,1).
  - FORME B contrôle : W1=W2=1, k=1 reproduit reg:squarederror bit-exact (allclose).

Protocole (identique Phases 1-3) : train H22(Gilamont 8501260 exclu)+H23 → validation H24.
Iso-tout sauf la perte : 158 features, ADR-CF09, seed=42, segmentation BAS/HAUT.
"""
import json, hashlib, time, itertools
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_perte"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"

HASH_ATTENDU, GILAMONT_BPUIC, SEUIL, SEED = "416bb90b", 8501260, 63, 42
TARGET = "target_voyageurs_2eme_classe"
SIGMAS = [5, 10, 20]
WPAIRS = [(2, 4), (3, 6), (5, 10), (10, 20)]
KS = [1, 2, 3, 5]

BASE_PARAMS = dict(n_estimators=300, max_depth=6, learning_rate=0.1,
                   subsample=0.8, colsample_bytree=0.8,
                   tree_method="hist", random_state=SEED,
                   enable_categorical=True, verbosity=0, n_jobs=-1)

def make_obj(weight_fn, k):
    kf = float(k)
    def obj(y_true, y_pred):
        r = y_pred - y_true
        a = np.where(r < 0, kf, 1.0)
        w = weight_fn(y_true)
        return w * a * r, w * a
    return obj

def w_flat(obs):  return np.ones_like(obs, dtype="float64")
def w_A(sigma):   return lambda obs: np.exp(-((obs - 63.0) ** 2) / (2.0 * sigma ** 2))
def w_B(W1, W2):  return lambda obs: np.where(obs < SEUIL, 1.0, np.where(obs > 94, float(W2), float(W1)))

print("=" * 80)
print("CHANTIER PERTE — Phase 4 : pertes pondérées A (cloche) vs B (rampe) — VALIDATION H24")
print("=" * 80)

# ── 0. Dataset ──────────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Hash {file_hash} ✓ (lecture seule)")
df = pd.read_parquet(PARQUET)
FEATS = json.load(open(FEAT_JSON))["features"]; assert len(FEATS) == 158

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

mtr = {s: (train["spatial_segment"] == s).values for s in ("bas", "haut")}
mva = {s: (valid["spatial_segment"] == s).values for s in ("bas", "haut")}
X_tr = {s: prep_X(train[mtr[s]]) for s in ("bas", "haut")}
X_va = {s: prep_X(valid[mva[s]]) for s in ("bas", "haut")}
y_tr = {s: train.loc[mtr[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_va_g = valid[TARGET].values.astype("float64")
base_score = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tkey = {"bas":  list(zip(valid.loc[mva["bas"],  "base_date"], valid.loc[mva["bas"],  "horaire_numero_train"])),
        "haut": list(zip(valid.loc[mva["haut"], "base_date"], valid.loc[mva["haut"], "horaire_numero_train"])),
        "global": list(zip(valid["base_date"], valid["horaire_numero_train"]))}
print(f"── 1. train={len(train):,} valid(H24)={len(valid):,} | >63 global={int((y_va_g>SEUIL).sum())} "
      f">94={int((y_va_g>94).sum())}")

# ── 2. Garde-fous ───────────────────────────────────────────────────────────
print("\n── 2. GARDE-FOUS ──")
def fit_seg(seg, obj):
    m = xgb.XGBRegressor(objective=obj, base_score=base_score[seg], **BASE_PARAMS)
    m.fit(X_tr[seg], y_tr[seg]); return m.predict(X_va[seg]).astype("float64")

# Garde-fou RIGOUREUX d'implémentation = poids strictement plat (w≡1, k=1) → MSE bit-exact,
# pour Forme A (w_A) ET Forme B (w_B(1,1)). Note : w_A(σ=1000) n'est PAS strictement plat
# (downweight ~3% du tail surcharge → décale les préds extrêmes) ; on le rapporte en
# INFORMATIF, et on vérifie la limite plate de w_A via σ=1e7 (w_A→1 à ~1e-9).
ok_impl = True; ok_A_limit = True
for seg in ("bas", "haut"):
    p_nat = xgb.XGBRegressor(objective="reg:squarederror", base_score=base_score[seg], **BASE_PARAMS).fit(X_tr[seg], y_tr[seg]).predict(X_va[seg]).astype("float64")
    p_flat = fit_seg(seg, make_obj(w_flat, 1))               # IMPL bit-exact : w≡1,k=1
    c_flat = np.allclose(p_nat, p_flat, rtol=1e-5, atol=1e-4); ok_impl = ok_impl and c_flat
    p_b11 = fit_seg(seg, make_obj(w_B(1, 1), 1))             # B W1=W2=1 (≡ w≡1) bit-exact
    c_b11 = np.allclose(p_nat, p_b11, rtol=1e-5, atol=1e-4); ok_impl = ok_impl and c_b11
    p_aLim = fit_seg(seg, make_obj(w_A(1e7), 1))             # A limite plate σ=1e7 → MSE
    d_aLim = float(np.abs(p_nat - p_aLim).max()); ok_A_limit = ok_A_limit and (d_aLim < 0.1)
    d_a1000 = float(np.abs(p_nat - fit_seg(seg, make_obj(w_A(1000), 1))).max())  # informatif
    print(f"  {seg.upper():>4}: IMPL w≡1,k=1 bit-exact={c_flat} | B W1=W2=1 bit-exact={c_b11} | "
          f"A σ=1e7,k=1 max|Δ|={d_aLim:.2e} (limite plate ✓) | [info] A σ=1000 max|Δ|={d_a1000:.1f} (downweight tail)")
ok_A = ok_A_limit
if not ok_impl:
    print("\n  ✗ GARDE-FOU IMPL ÉCHOUÉ — dérivation/implémentation fausse. ARRÊT."); raise SystemExit(1)
if not ok_A:
    print("\n  ✗ GARDE-FOU A limite (σ=1e7) Δ>0,1 — w_A ne tend pas vers MSE. ARRÊT."); raise SystemExit(1)
print("  ✓ Garde-fous validés (impl bit-exact w≡1 & B(1,1) ; limite plate w_A(σ→∞)≈MSE). Balayage autorisé.")

# ── 3. Métriques ────────────────────────────────────────────────────────────
def pr(yb, yp): return float(average_precision_score(yb, yp)) if yb.sum() else None
def pr_tour(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp}).groupby("k").agg(mo=("obs","max"), mp=("pred","max"))
    return pr((g["mo"].values > SEUIL).astype(int), g["mp"].values)
def mblock(yt, yp, keys):
    z = yt > SEUIL; band = (yt >= 56) & (yt <= 70); sev = yt > 94; le = yt <= SEUIL; res = yp - yt
    return {"n_gt63": int(z.sum()), "bias_gt63": float(res[z].mean()) if z.sum() else None,
            "mae_gt63": float(np.abs(res[z]).mean()) if z.sum() else None,
            "bias_band_56_70": float(res[band].mean()) if band.sum() else None,
            "bias_gt94": float(res[sev].mean()) if sev.sum() else None,
            "bias_le63": float(res[le].mean()) if le.sum() else None,
            "mae_global": float(mean_absolute_error(yt, yp)), "r2_global": float(r2_score(yt, yp)),
            "pr_auc_troncon": pr((yt > SEUIL).astype(int), yp), "pr_auc_tour": pr_tour(keys, yt, yp)}

def run_config(weight_fn, k):
    preds = {s: fit_seg(s, make_obj(weight_fn, k)) for s in ("bas", "haut")}
    yp_g = np.empty(len(valid)); yp_g[mva["bas"]] = preds["bas"]; yp_g[mva["haut"]] = preds["haut"]
    return {"bas": mblock(y_va_g[mva["bas"]], preds["bas"], tkey["bas"]),
            "haut": mblock(y_va_g[mva["haut"]], preds["haut"], tkey["haut"]),
            "global": mblock(y_va_g, yp_g, tkey["global"])}, yp_g

# ── 4. Baseline MSE + balayages A et B ──────────────────────────────────────
print("\n── 3. Baseline MSE + balayages ──")
rows = []; preds_keep = {}
t0 = time.time()
res_base, yp_base = run_config(w_flat, 1)
preds_keep["baseline_MSE"] = yp_base
g = res_base["global"]
print(f"  baseline MSE        : biais>63={g['bias_gt63']:+.2f} band={g['bias_band_56_70']:+.2f} "
      f">94={g['bias_gt94']:+.2f} biais≤63={g['bias_le63']:+.2f} MAEg={g['mae_global']:.3f} "
      f"R²={g['r2_global']:.4f} PRtr={g['pr_auc_troncon']:.4f} PRto={g['pr_auc_tour']:.4f}")
rows.append({"forme": "MSE", "config": "baseline", "k": 1, **{f"{s}.{m}": res_base[s][m] for s in ("bas","haut","global") for m in res_base[s]}})

for sigma, k in itertools.product(SIGMAS, KS):
    res, ypg = run_config(w_A(sigma), k)
    rows.append({"forme": "A", "config": f"sigma{sigma}", "sigma": sigma, "k": k,
                 **{f"{s}.{m}": res[s][m] for s in ("bas","haut","global") for m in res[s]}})
    preds_keep[f"A_s{sigma}_k{k}"] = ypg
    g = res["global"]
    print(f"  A σ={sigma:>2} k={k} : biais>63={g['bias_gt63']:+.2f} band={g['bias_band_56_70']:+.2f} "
          f">94={g['bias_gt94']:+.2f} biais≤63={g['bias_le63']:+.2f} MAEg={g['mae_global']:.3f} "
          f"R²={g['r2_global']:.4f} PRtr={g['pr_auc_troncon']:.4f}")
for (W1, W2), k in itertools.product(WPAIRS, KS):
    res, ypg = run_config(w_B(W1, W2), k)
    rows.append({"forme": "B", "config": f"W{W1}-{W2}", "W1": W1, "W2": W2, "k": k,
                 **{f"{s}.{m}": res[s][m] for s in ("bas","haut","global") for m in res[s]}})
    preds_keep[f"B_W{W1}-{W2}_k{k}"] = ypg
    g = res["global"]
    print(f"  B ({W1:>2},{W2:>2}) k={k} : biais>63={g['bias_gt63']:+.2f} band={g['bias_band_56_70']:+.2f} "
          f">94={g['bias_gt94']:+.2f} biais≤63={g['bias_le63']:+.2f} MAEg={g['mae_global']:.3f} "
          f"R²={g['r2_global']:.4f} PRtr={g['pr_auc_troncon']:.4f}")
print(f"  (balayage total {time.time()-t0:.0f}s, {len(rows)} configs)")

res_df = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
res_df.to_csv(OUT / "balayage_pertes_ponderees_h24.csv", index=False)

# ── 5. Sélection best-A / best-B (min |biais>63 global|) + comparaison ──────
def best_of(forme):
    sub = res_df[res_df.forme == forme].copy()
    sub["abs_bias"] = sub["global.bias_gt63"].abs()
    return sub.sort_values("abs_bias").iloc[0]
bA, bB = best_of("A"), best_of("B")
base = res_df[res_df.forme == "MSE"].iloc[0]

def load_prev_best():
    out = {}
    for f, key in [("balayage_sample_weight_h24.json", "P1_sample_weight"),
                   ("balayage_mse_asym_h24.json", "P2_mse_asym")]:
        p = OUT / f
        if not p.exists(): continue
        d = json.load(open(p))["resultats"]
        gl = [r for r in d if r["segment"] == "global"]
        bb = min(gl, key=lambda r: abs(r["bias_gt63"]))
        out[key] = bb
    return out
prev = load_prev_best()

print("\n" + "=" * 80)
print("COMPARAISON — meilleur de chaque forme (min |biais>63 global|), validation H24")
print("=" * 80)
hdr = f"{'config':>22} | {'biais>63':>9} | {'band56-70':>9} | {'biais>94':>9} | {'biais≤63':>9} | {'MAEg':>6} | {'R²':>7} | {'PRtr':>7} | {'PRto':>7}"
print(hdr); print("-" * len(hdr))
def prow(lab, bias63, band, sev, le63, maeg, r2, prtr, prto):
    f = lambda x: f"{x:+.2f}" if x is not None else "   n/a"
    print(f"{lab:>22} | {f(bias63):>9} | {f(band):>9} | {f(sev):>9} | {f(le63):>9} | "
          f"{(maeg if maeg else 0):>6.3f} | {(r2 if r2 else 0):>7.4f} | {(prtr or 0):>7.4f} | {(prto or 0):>7.4f}")
prow("baseline MSE", base["global.bias_gt63"], base["global.bias_band_56_70"], base["global.bias_gt94"], base["global.bias_le63"], base["global.mae_global"], base["global.r2_global"], base["global.pr_auc_troncon"], base["global.pr_auc_tour"])
prow(f"A best ({bA['config']} k{int(bA['k'])})", bA["global.bias_gt63"], bA["global.bias_band_56_70"], bA["global.bias_gt94"], bA["global.bias_le63"], bA["global.mae_global"], bA["global.r2_global"], bA["global.pr_auc_troncon"], bA["global.pr_auc_tour"])
prow(f"B best ({bB['config']} k{int(bB['k'])})", bB["global.bias_gt63"], bB["global.bias_band_56_70"], bB["global.bias_gt94"], bB["global.bias_le63"], bB["global.mae_global"], bB["global.r2_global"], bB["global.pr_auc_troncon"], bB["global.pr_auc_tour"])
for key, r in prev.items():
    prow(key, r["bias_gt63"], None, None, r.get("bias_le63"), r["mae_global"], r["r2_global"], r["pr_auc_troncon"], r["pr_auc_tour"])

# ── 6. Histogrammes : "trou au seuil" autour de 63 ──────────────────────────
print("\n── 4. Distribution des prédictions autour de 63 (détection trou au seuil) ──")
def near63(yp, lo=54, hi=72):
    m = (yp >= lo) & (yp <= hi); return yp[m]
fig, ax = plt.subplots(figsize=(10, 5))
bins = np.arange(40, 100, 2)
for lab, key in [("baseline MSE", "baseline_MSE"),
                 (f"A best {bA['config']} k{int(bA['k'])}", f"A_{bA['config'].replace('sigma','s')}_k{int(bA['k'])}"),
                 (f"B best {bB['config']} k{int(bB['k'])}", f"B_{bB['config']}_k{int(bB['k'])}")]:
    yp = preds_keep.get(key)
    if yp is None: continue
    ax.hist(yp, bins=bins, histtype="step", linewidth=1.8, label=lab)
    c = lambda lo, hi: int(((yp >= lo) & (yp < hi)).sum())
    print(f"  {lab:>26} : préds [60,63)={c(60,63)}  [63,66)={c(63,66)}  [66,69)={c(66,69)}  (trou si creux à 63)")
ax.axvline(63, color="k", ls="--", lw=1, label="seuil 63")
ax.set_xlabel("prédiction"); ax.set_ylabel("nb tronçons"); ax.set_xlim(40, 98)
ax.set_title("Distribution des prédictions autour du seuil 63 (validation H24)")
ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
fig.savefig(OUT / "distribution_seuil63_h24.png", dpi=200, bbox_inches="tight"); plt.close(fig)
print("  Figure → distribution_seuil63_h24.png")

# ── 7. JSON résumé + lectures ───────────────────────────────────────────────
def rec(r):
    return {k: (float(r[k]) if isinstance(r[k], (int, float, np.floating)) and not pd.isna(r[k]) else r[k])
            for k in r.index if k.startswith(("global.", "bas.", "haut.")) or k in ("forme","config","k","sigma","W1","W2")}
(OUT / "balayage_pertes_ponderees_h24.json").write_text(json.dumps({
    "experiment": "Phase 4 — pertes pondérées A (cloche σ) vs B (rampe W1/W2), validation H24",
    "statut": "EXPERIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact, H25 jamais touché",
    "forme_commune": "g=w(obs)·a·r, h=w(obs)·a, a=k si r<0 sinon 1",
    "garde_fous": {"impl_w1_k1_bitexact": bool(ok_impl), "A_limite_sigma1e7_mse": bool(ok_A),
                   "note": "w_A(σ=1000) downweight ~3% du tail surcharge → décale les préds extrêmes (~40), donc σ=1000 n'est PAS un contrôle MSE bit-exact ; preuve impl = w≡1 bit-exact + limite σ=1e7"},
    "grille": {"A": {"sigma": SIGMAS, "k": KS}, "B": {"WPAIRS": WPAIRS, "k": KS}},
    "baseline_MSE": rec(base), "best_A": rec(bA), "best_B": rec(bB),
    "phases_1_2_best": prev,
    "tous_configs": res_df.to_dict(orient="records"),
}, indent=2, ensure_ascii=False, default=lambda o: None))
print(f"\nFichiers : {OUT}/balayage_pertes_ponderees_h24.{{csv,json}} + distribution_seuil63_h24.png")
print("ARRÊT — table comparative produite. Aucune config choisie, aucun réentraînement. Décision conjointe.")
print("=" * 80)
