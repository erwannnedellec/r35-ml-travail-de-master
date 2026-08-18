"""
CHANTIER HYPERPARAMÈTRES — test H25 décisif : best-R² (Optuna, HP différenciés par
segment) vs CF09 (HP partagés). EXPERIMENTAL — HORS canonique (exp_hpo/). Ne touche
NI au hash 416bb90b, NI au pipeline, NI aux modeles canoniques. Aucun modele sauvegarde.
H25 touche UNE FOIS pour ce test. Le re-figement eventuel sera une etape SEPAREE.

Critere d'adoption (pose AVANT de voir les chiffres)
----------------------------------------------------
best-R² remplace CF09 SEULEMENT s'il ne degrade MATERIELLEMENT AUCUNE metrique cle
sur H25 : R² global (pas de baisse nette type k=2), biais>63 (pas pire), PR-AUC troncon
ET tour PAR SEGMENT (pas en baisse). Jeu egal ou mieux partout -> adoption. Degradation
materielle d'une metrique -> non-adoption, conservation CF09.

Seuils de materialite (transparents) :
  R² global        : baisse materielle si Δ < -0.005   (k=2 etait -0.015)
  PR-AUC (par seg) : baisse materielle si Δ < -0.005   (au-dela du bruit ~0.003)
  biais>63 (par seg): pire si plus negatif de > 0.5    (sous-prediction aggravee)

Protocole (iso-canonique sauf les HP)
-------------------------------------
  train H22(Gilamont 8501260 exclu)+H23+H24 (Split C) -> test H25 ; 158 features,
  seed=42, segmentation BAS/HAUT, reg:squarederror, seuil 63, base_score=moyenne train seg.
Garde-fou : CF09 doit reproduire les metrics_h25 canoniques (metadata enrichi_seg), Δ≈0.
"""
import json, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT      = Path(__file__).resolve().parents[2]
OUT       = ROOT / "consolidation_finale" / "exp_hpo"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"
TUNING_JSON = ROOT / "consolidation_finale" / "exp_hpo" / "tuning_optuna_h24_resultats.json"
META_JSON = ROOT / "models" / "enrichi_seg" / "enrichi_seg_metadata.json"

HASH_ATTENDU, GILAMONT_BPUIC, SEUIL, SEED = "416bb90b", 8501260, 63, 42
TARGET = "target_voyageurs_2eme_classe"
COMMON = dict(objective="reg:squarederror", tree_method="hist",
              random_state=SEED, enable_categorical=True, verbosity=0)

print("=" * 80)
print("CHANTIER HP — test H25 : best-R² (Optuna, par segment) vs CF09 (partagé)")
print("=" * 80)

# ── 0. Données + HP ─────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Hash {file_hash} ✓ (lecture seule)")
FEATS = json.load(open(FEAT_JSON))["features"]; assert len(FEATS) == 158
tun = json.load(open(TUNING_JSON))
CF09 = tun["hp_actuels_adr_cf09"]               # HP partagés bas=haut
BESTR2 = {s: tun["pareto"][s]["best_R2"]["params"] for s in ("bas", "haut")}  # HP par segment
print("  CF09 (partagé) :", CF09)
print("  best-R² BAS  :", BESTR2["bas"])
print("  best-R² HAUT :", BESTR2["haut"])

# ── 1. Split tri-annuel (Split C) ───────────────────────────────────────────
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
y_te = {s: test.loc[mte[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_te_g = test[TARGET].values.astype("float64")
BASE_SCORE = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tour_key = {
    "bas":    list(zip(test.loc[mte["bas"],  "base_date"], test.loc[mte["bas"],  "horaire_numero_train"])),
    "haut":   list(zip(test.loc[mte["haut"], "base_date"], test.loc[mte["haut"], "horaire_numero_train"])),
    "global": list(zip(test["base_date"], test["horaire_numero_train"])),
}
print(f"  TEST H25 >{SEUIL} : BAS={int((y_te['bas']>SEUIL).sum())} "
      f"HAUT={int((y_te['haut']>SEUIL).sum())} GLOBAL={int((y_te_g>SEUIL).sum())}")

# ── 2. Métriques ────────────────────────────────────────────────────────────
def pr_tr(yt, yp):
    yb = (yt > SEUIL).astype(int)
    return float(average_precision_score(yb, yp)) if yb.sum() else None
def pr_to(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp}).groupby("k").agg(mo=("obs","max"), mp=("pred","max"))
    yb = (g["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, g["mp"].values)) if yb.sum() else None
def mblock(yt, yp, keys):
    z = yt > SEUIL; res = yp - yt
    return {"n_obs": int(len(yt)), "n_gt63": int(z.sum()),
            "r2_global": float(r2_score(yt, yp)), "mae_global": float(mean_absolute_error(yt, yp)),
            "bias_gt63": float(res[z].mean()) if z.sum() else None,
            "mae_gt63": float(np.abs(res[z]).mean()) if z.sum() else None,
            "pr_auc_troncon": pr_tr(yt, yp), "pr_auc_tour": pr_to(keys, yt, yp)}

# ── 3. Entraînement CF09 puis best-R² ───────────────────────────────────────
def run(params_by_seg, tag):
    preds = {}
    for s in ("bas", "haut"):
        p = params_by_seg[s] if s in params_by_seg else params_by_seg
        m = xgb.XGBRegressor(base_score=BASE_SCORE[s], **COMMON, **p)
        m.fit(X_tr[s], y_tr[s])
        preds[s] = m.predict(X_te[s]).astype("float64")
    yp_g = np.empty(len(test)); yp_g[mte["bas"]] = preds["bas"]; yp_g[mte["haut"]] = preds["haut"]
    res = {"bas": mblock(y_te["bas"], preds["bas"], tour_key["bas"]),
           "haut": mblock(y_te["haut"], preds["haut"], tour_key["haut"]),
           "global": mblock(y_te_g, yp_g, tour_key["global"])}
    print(f"\n  [{tag}] (TEST H25) :")
    for s in ("bas", "haut", "global"):
        m = res[s]
        print(f"    {s:>6} R²={m['r2_global']:.4f} MAEg={m['mae_global']:.3f} "
              f"biais>63={m['bias_gt63']:+.2f} MAE>63={m['mae_gt63']:.2f} "
              f"PRAUC_tr={m['pr_auc_troncon']:.4f} PRAUC_tour={m['pr_auc_tour']:.4f}")
    return res

print("\n── 3. Entraînement (Split C, reg:squarederror) ──")
t0 = time.time()
res_cf09 = run({"bas": CF09, "haut": CF09}, "CF09 (partagé)")
res_best = run(BESTR2, "best-R² (par segment)")
print(f"  (total {time.time()-t0:.0f}s)")

# ── 4. Garde-fou CF09 == canonique H25 ──────────────────────────────────────
print("\n── 4. GARDE-FOU CF09 vs metrics_h25 canoniques (metadata) ──")
meta = json.load(open(META_JSON))["metrics_h25"]
gf_ok = True
for s in ("bas", "haut", "global"):
    dr2 = abs(meta[s]["r2"] - res_cf09[s]["r2_global"]); dpr = abs(meta[s]["pr_auc"] - res_cf09[s]["pr_auc_troncon"])
    ok = dr2 < 5e-3 and dpr < 5e-3; gf_ok = gf_ok and ok
    print(f"  {s:>6} R² Δ={dr2:.4f} | PR-AUC(tr) Δ={dpr:.4f} " + ("✓" if ok else "✗"))
print("  → " + ("CF09 reproduit le canonique ✓" if gf_ok else "ÉCART garde-fou ✗"))

# ── 5. Table comparative + verdict selon CRITÈRE D'ADOPTION ─────────────────
print("\n" + "=" * 80)
print("COMPARAISON H25 — CF09 vs best-R² (Δ = best − CF09)")
print("=" * 80)
print(f"{'segment':>6} {'metric':>14} | {'CF09':>9} | {'best-R²':>9} | {'Δ':>9}")
print("-" * 60)
rows = []
for s in ("bas", "haut", "global"):
    for met in ["r2_global", "mae_global", "bias_gt63", "mae_gt63", "pr_auc_troncon", "pr_auc_tour"]:
        b = res_cf09[s][met]; c = res_best[s][met]; d = c - b
        print(f"{s:>6} {met:>14} | {b:>9.4f} | {c:>9.4f} | {d:>+9.4f}")
        rows.append({"segment": s, "metric": met, "cf09": b, "best_r2": c, "delta": d})
    print("-" * 60)

# évaluation automatique du critère
degr = []
# R² global : baisse materielle si < -0.005
dr2g = res_best["global"]["r2_global"] - res_cf09["global"]["r2_global"]
if dr2g < -0.005: degr.append(f"R² global {dr2g:+.4f}")
# biais>63 par segment : pire si plus negatif de >0.5
for s in ("bas", "haut", "global"):
    db = res_best[s]["bias_gt63"] - res_cf09[s]["bias_gt63"]
    if db < -0.5: degr.append(f"biais>63 {s} {db:+.2f} (plus négatif)")
# PR-AUC troncon ET tour par segment : baisse materielle si < -0.005
for s in ("bas", "haut"):
    for met in ("pr_auc_troncon", "pr_auc_tour"):
        dd = res_best[s][met] - res_cf09[s][met]
        if dd < -0.005: degr.append(f"{met} {s} {dd:+.4f}")

print("\nCRITÈRE D'ADOPTION (posé avant les chiffres) :")
if degr:
    print("  → DÉGRADATION MATÉRIELLE détectée sur : " + " ; ".join(degr))
    verdict = "NON-ADOPTION — conserver CF09 (best-R² dégrade au moins une métrique clé sur H25)"
else:
    print("  → aucune dégradation matérielle (R² global, biais>63, PR-AUC tronçon+tour/segment)")
    verdict = "ADOPTION ÉLIGIBLE — best-R² jeu égal ou mieux partout sur H25 (re-figement en étape séparée)"
print(f"  VERDICT : {verdict}")

# rappel généralisation H24→H25 (anti-mirage type k=2)
print("\nGÉNÉRALISATION H24→H25 (best-R² − CF09) :")
ref = tun["reference_h24"]; besth24 = {s: tun["pareto"][s]["best_R2"] for s in ("bas", "haut")}
for s in ("bas", "haut"):
    d24 = besth24[s]["r2"] - ref[s]["r2"]; d25 = res_best[s]["r2_global"] - res_cf09[s]["r2_global"]
    p24 = besth24[s]["pr_auc_troncon"] - ref[s]["pr_auc_troncon"]; p25 = res_best[s]["pr_auc_troncon"] - res_cf09[s]["pr_auc_troncon"]
    print(f"  {s:>4}: ΔR²  H24={d24:+.4f} → H25={d25:+.4f}  |  ΔPR-AUC_tr H24={p24:+.4f} → H25={p25:+.4f}")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "test_h25_best_r2_vs_cf09.json").write_text(json.dumps({
    "experiment": "test H25 best-R² (Optuna, HP par segment) vs CF09",
    "statut": "EXPERIMENTAL hors canonique — aucun modele sauvegarde, hash 416bb90b intact, pas de re-figement",
    "protocole": "train H22(Gil exclu)+H23+H24 → test H25 (Split C) ; iso sauf HP ; seed42 seuil63 reg:squarederror seg bas/haut",
    "hp_cf09": CF09, "hp_best_r2": BESTR2,
    "garde_fou_cf09_reproduit_canon": gf_ok,
    "cf09_h25": res_cf09, "best_r2_h25": res_best, "deltas": rows,
    "critere_adoption": "best-R² adopté ssi aucune dégradation matérielle (R²g Δ<-0.005, biais>63 plus négatif >0.5, PR-AUC tr/tour par segment Δ<-0.005)",
    "degradations_materielles": degr, "verdict": verdict,
}, indent=2, ensure_ascii=False))
print(f"\nFichier : {OUT/'test_h25_best_r2_vs_cf09.json'}")
print("ARRÊT — table H25 + verdict. PAS de re-figement ici (étape séparée, décision conjointe).")
print("=" * 80)
