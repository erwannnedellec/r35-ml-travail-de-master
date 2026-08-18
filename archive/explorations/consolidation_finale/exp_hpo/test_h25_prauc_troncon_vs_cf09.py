"""
CHANTIER HP — test H25 DÉCISIF : candidat best-PR-AUC-tronçon (HP partagés, Optuna
cible PR-AUC tronçon globale) vs CF09. EXPERIMENTAL — HORS canonique (`exp_hpo/`).
Ne touche NI au hash 416bb90b, NI au pipeline, NI aux modèles canoniques. Aucun
modèle sauvegardé. H25 touché UNE FOIS pour ce test. PAS de re-figement ici.

Critère d'adoption (posé AVANT les chiffres, strict)
----------------------------------------------------
(1) le gain de PR-AUC tronçon globale SURVIT à ≥ +0,014 sur H25 (moitié du +0,028 H24) ;
(2) AUCUNE dégradation matérielle : R² global, biais>63 (tous segments), PR-AUC tour
    globale, et pas d'effondrement PR-AUC HAUT.
Les DEUX → éligible adoption (re-figement décidé ensuite). Sinon → CF09 conservé.

Protocole (iso-canonique sauf les HP)
-------------------------------------
  train H22(Gilamont 8501260 exclu)+H23+H24 (Split C) → test H25 ; 158 features,
  seed=42, segmentation BAS/HAUT, reg:squarederror, seuil 63, base_score=moy train seg.
  CF09 = HP partagés actuels. CANDIDAT = HP partagés best essai 45 (chargés du JSON).
Garde-fou : CF09 reproduit les metrics_h25 canoniques (R² 0,6013 ; PR-AUC tronçon globale
  0,4490 ; BAS 0,4687 ; HAUT 0,3452 ; tour 0,5635) à Δ≈0.
"""
import json, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "consolidation_finale" / "exp_hpo"
PARQUET = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"
TUNING_JSON = OUT / "tuning_prauc_troncon_h24_resultats.json"
META_JSON = ROOT / "models" / "enrichi_seg" / "enrichi_seg_metadata.json"

HASH_ATTENDU, GILAMONT_BPUIC, SEUIL, SEED = "416bb90b", 8501260, 63, 42
TARGET = "target_voyageurs_2eme_classe"
COMMON = dict(objective="reg:squarederror", tree_method="hist",
              random_state=SEED, enable_categorical=True, verbosity=0, n_jobs=-1)
# garde-fou metrics_h25 canoniques (metadata) — tour ajouté manuellement (cf. Phase B/C)
CANON_H25 = {"r2_global": 0.6013, "pr_auc_troncon_global": 0.4490,
             "pr_auc_troncon_bas": 0.4687, "pr_auc_troncon_haut": 0.3452,
             "pr_auc_tour_global": 0.5635}
GAIN_MIN = 0.014  # condition (1)

print("=" * 80)
print("CHANTIER HP — test H25 DÉCISIF : best-PR-AUC-tronçon vs CF09")
print("=" * 80)

file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Hash {file_hash} ✓ (lecture seule)")
FEATS = json.load(open(FEAT_JSON))["features"]; assert len(FEATS) == 158
CF09 = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=1, reg_lambda=1.0, reg_alpha=0.0, gamma=0.0)
CAND = json.load(open(TUNING_JSON))["best"]["hp"]
print("  CF09     :", CF09)
print("  candidat :", {k: round(v, 4) if isinstance(v, float) else v for k, v in CAND.items()})

# ── 1. Split tri-annuel ─────────────────────────────────────────────────────
df = pd.read_parquet(PARQUET)
h22 = df[df["horaire_annee_horaire"] == "H22"]
mgil = ((h22["id_gare_depart_bpuic"].astype("int64") == GILAMONT_BPUIC) |
        (h22["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC))
train = pd.concat([h22[~mgil].copy(),
                   df[df["horaire_annee_horaire"] == "H23"].copy(),
                   df[df["horaire_annee_horaire"] == "H24"].copy()], ignore_index=True)
test = df[df["horaire_annee_horaire"] == "H25"].copy()
del df
print(f"  n_train={len(train):,} n_test_H25={len(test):,}")

def prep_X(d):
    X = d[[c for c in FEATS if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"): X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"): X[c] = X[c].astype("float64")
    return X

mtr = {s: (train["spatial_segment"] == s).values for s in ("bas", "haut")}
mte = {s: (test["spatial_segment"] == s).values for s in ("bas", "haut")}
X_tr = {s: prep_X(train[mtr[s]]) for s in ("bas", "haut")}
X_te = {s: prep_X(test[mte[s]]) for s in ("bas", "haut")}
y_tr = {s: train.loc[mtr[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_te_g = test[TARGET].values.astype("float64")
yb_te_g = (y_te_g > SEUIL).astype(int)
base_score = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tkey_g = list(zip(test["base_date"], test["horaire_numero_train"]))
print(f"  TEST H25 >63 : BAS={int((y_te_g[mte['bas']]>SEUIL).sum())} "
      f"HAUT={int((y_te_g[mte['haut']]>SEUIL).sum())} GLOBAL={int(yb_te_g.sum())}")

# ── 2. Métriques ────────────────────────────────────────────────────────────
def pr(yb, yp): return float(average_precision_score(yb, yp)) if yb.sum() else None
def pr_tour(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp}).groupby("k").agg(mo=("obs","max"), mp=("pred","max"))
    return pr((g["mo"].values > SEUIL).astype(int), g["mp"].values)

def evaluate(params, tag):
    yp_g = np.empty(len(test)); seg = {}
    for s in ("bas", "haut"):
        m = xgb.XGBRegressor(base_score=base_score[s], **COMMON, **params)
        m.fit(X_tr[s], y_tr[s])
        p = m.predict(X_te[s]).astype("float64"); yp_g[mte[s]] = p
        yt = y_te_g[mte[s]]; z = yt > SEUIL; res = p - yt
        seg[s] = {"r2": float(r2_score(yt, p)), "mae_global": float(mean_absolute_error(yt, p)),
                  "bias_gt63": float(res[z].mean()), "mae_gt63": float(np.abs(res[z]).mean()),
                  "pr_auc_troncon": pr((yt > SEUIL).astype(int), p),
                  "pr_auc_tour": pr_tour(list(zip(test.loc[mte[s], "base_date"], test.loc[mte[s], "horaire_numero_train"])), yt, p)}
    zg = yb_te_g.astype(bool); resg = yp_g - y_te_g
    glob = {"r2": float(r2_score(y_te_g, yp_g)), "mae_global": float(mean_absolute_error(y_te_g, yp_g)),
            "bias_gt63": float(resg[zg].mean()), "mae_gt63": float(np.abs(resg[zg]).mean()),
            "pr_auc_troncon": pr(yb_te_g, yp_g), "pr_auc_tour": pr_tour(tkey_g, y_te_g, yp_g)}
    res = {"bas": seg["bas"], "haut": seg["haut"], "global": glob}
    print(f"\n  [{tag}] (TEST H25) :")
    for s in ("bas", "haut", "global"):
        m = res[s]
        print(f"    {s:>6} R²={m['r2']:.4f} MAEg={m['mae_global']:.3f} biais>63={m['bias_gt63']:+.2f} "
              f"MAE>63={m['mae_gt63']:.2f} PRAUC_tr={m['pr_auc_troncon']:.4f} PRAUC_tour={m['pr_auc_tour']:.4f}")
    return res

print("\n── 3. Entraînement CF09 puis candidat (Split C) ──")
t0 = time.time()
res_cf09 = evaluate(CF09, "CF09")
res_cand = evaluate(CAND, "candidat best-PR-AUC-tronçon")
print(f"  (total {time.time()-t0:.0f}s)")

# ── 4. Garde-fou CF09 == canonique H25 ──────────────────────────────────────
print("\n── 4. GARDE-FOU CF09 vs metrics_h25 canoniques ──")
gf = {"r2_global": res_cf09["global"]["r2"], "pr_auc_troncon_global": res_cf09["global"]["pr_auc_troncon"],
      "pr_auc_troncon_bas": res_cf09["bas"]["pr_auc_troncon"], "pr_auc_troncon_haut": res_cf09["haut"]["pr_auc_troncon"],
      "pr_auc_tour_global": res_cf09["global"]["pr_auc_tour"]}
gf_ok = True
for k, v in CANON_H25.items():
    d = abs(gf[k] - v); ok = d < 5e-3; gf_ok = gf_ok and ok
    print(f"  {k:>26} canon={v:.4f} obtenu={gf[k]:.4f} Δ={d:.4f} " + ("✓" if ok else "✗"))
assert gf_ok, "GARDE-FOU ÉCHOUÉ — CF09 ne reproduit pas le canonique H25."
print("  → CF09 reproduit le canonique H25 ✓")

# ── 5. Table comparative + Δ H24→H25 ────────────────────────────────────────
H24 = {"pr_auc_troncon_global": (0.4759, 0.5037), "r2_global": (0.6586, 0.6764),
       "bias_gt63_global": (-29.13, -28.42), "pr_auc_tour_global": (0.5903, 0.6019),
       "pr_auc_troncon_bas": (0.4919, 0.5192), "pr_auc_troncon_haut": (0.3077, 0.3292)}
print("\n" + "=" * 80)
print("COMPARAISON H25 — CF09 vs candidat (Δ = candidat − CF09)")
print("=" * 80)
print(f"{'segment':>6} {'metric':>14} | {'CF09':>9} | {'cand':>9} | {'Δ H25':>9} | {'Δ H24':>9}")
print("-" * 70)
rows = []
H24map = {("global","pr_auc_troncon"):"pr_auc_troncon_global", ("global","r2"):"r2_global",
          ("global","bias_gt63"):"bias_gt63_global", ("global","pr_auc_tour"):"pr_auc_tour_global",
          ("bas","pr_auc_troncon"):"pr_auc_troncon_bas", ("haut","pr_auc_troncon"):"pr_auc_troncon_haut"}
for s in ("bas", "haut", "global"):
    for met in ["r2", "mae_global", "bias_gt63", "mae_gt63", "pr_auc_troncon", "pr_auc_tour"]:
        b = res_cf09[s][met]; c = res_cand[s][met]; d = c - b
        h24k = H24map.get((s, met)); dh24 = (H24[h24k][1] - H24[h24k][0]) if h24k else None
        dh = f"{dh24:+.4f}" if dh24 is not None else ""
        print(f"{s:>6} {met:>14} | {b:>9.4f} | {c:>9.4f} | {d:>+9.4f} | {dh:>9}")
        rows.append({"segment": s, "metric": met, "cf09": b, "cand": c, "delta_h25": d, "delta_h24": dh24})
    print("-" * 70)

# ── 6. VERDICT mécanique selon le critère pré-posé ──────────────────────────
gain = res_cand["global"]["pr_auc_troncon"] - res_cf09["global"]["pr_auc_troncon"]
cond1 = gain >= GAIN_MIN
# condition (2) : dégradations matérielles (seuil 0.005 ; biais plus négatif >0.5)
degr = []
if res_cand["global"]["r2"] - res_cf09["global"]["r2"] < -0.005: degr.append(f"R² global {res_cand['global']['r2']-res_cf09['global']['r2']:+.4f}")
for s in ("bas", "haut", "global"):
    db = res_cand[s]["bias_gt63"] - res_cf09[s]["bias_gt63"]
    if db < -0.5: degr.append(f"biais>63 {s} {db:+.2f}")
dtour = res_cand["global"]["pr_auc_tour"] - res_cf09["global"]["pr_auc_tour"]
if dtour < -0.005: degr.append(f"PR-AUC tour globale {dtour:+.4f}")
for met in ("pr_auc_troncon", "pr_auc_tour"):
    dd = res_cand["haut"][met] - res_cf09["haut"][met]
    if dd < -0.005: degr.append(f"HAUT {met} {dd:+.4f}")
cond2 = (len(degr) == 0)

print("\n" + "=" * 80)
print("VERDICT MÉCANIQUE (critère pré-posé)")
print("=" * 80)
print(f"  (1) gain PR-AUC tronçon globale H25 = {gain:+.4f}  (≥ +{GAIN_MIN} ?)  → {'OUI' if cond1 else 'NON'}")
print(f"      rappel H24 = +0.0278  ;  généralisation = {gain/0.0278*100:.0f}% du gain H24")
print(f"  (2) aucune dégradation matérielle ?  → {'OUI' if cond2 else 'NON : ' + ' ; '.join(degr)}")
if cond1 and cond2:
    verdict = "ÉLIGIBLE À L'ADOPTION — les 2 conditions remplies (re-figement = étape séparée)"
else:
    verdict = "NON-ADOPTION — CF09 conservé (" + ("gain insuffisant" if not cond1 else "") + (" + " if not cond1 and not cond2 else "") + ("dégradation matérielle" if not cond2 else "") + ")"
print(f"\n  VERDICT : {verdict}")

(OUT / "test_h25_prauc_troncon_vs_cf09.json").write_text(json.dumps({
    "experiment": "test H25 décisif — candidat best-PR-AUC-tronçon vs CF09",
    "statut": "EXPERIMENTAL hors canonique — aucun modèle sauvegardé, hash 416bb90b intact, H25 touché une fois, pas de re-figement",
    "protocole": "train H22(Gil exclu)+H23+H24 → test H25 (Split C) ; iso sauf HP partagés ; seed42 seuil63 reg:squarederror seg bas/haut",
    "hp_cf09": CF09, "hp_candidat": CAND,
    "garde_fou_cf09_reproduit_canon": gf_ok,
    "cf09_h25": res_cf09, "candidat_h25": res_cand, "deltas": rows,
    "critere": {"cond1_gain_min": GAIN_MIN, "gain_h25": gain, "cond1_ok": bool(cond1),
                "cond2_degradations": degr, "cond2_ok": bool(cond2)},
    "verdict": verdict,
}, indent=2, ensure_ascii=False))
print(f"\nFichier : {OUT/'test_h25_prauc_troncon_vs_cf09.json'}")
print("ARRÊT — table H25 + verdict. PAS de re-figement (étape séparée, décision conjointe).")
print("=" * 80)
