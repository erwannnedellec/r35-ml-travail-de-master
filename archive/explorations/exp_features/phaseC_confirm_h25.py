"""
CHANTIER FEATURES — Phase C : confirmation H25 du seul candidat
================================================================
event_is_vacances_valais (gain BAS observe en validation H24). EXPERIMENTAL, HORS
canonique. Hash 416bb90b intact (lecture seule), aucun stage, build_ml_dataset.py
non touche, aucun modele sauvegarde. H25 touche UNE FOIS pour rapport de
generalisation. RAPPORT seulement — PAS de selection, PAS d'industrialisation.

Question : le micro-gain BAS de validation (PR-AUC troncon +0.019, tour +0.012) se
retrouve-t-il sur H25, ou s'evapore-t-il ?

Protocole (iso-canonique sauf l'ajout d'1 feature)
--------------------------------------------------
  train = H22 (Gilamont 8501260 exclu) + H23 + H24   ;   test = H25   (Split C canonique)
  CANONIQUE 158f vs 159f (158 + event_is_vacances_valais SEULE).
  Iso ADR-CF09, seed=42, segmentation BAS/HAUT, seuil 63, reg:squarederror.
Garde-fou : 158f doit reproduire les chiffres canoniques (metrics_h25 metadata).
"""
import json, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score
import xgboost as xgb

ROOT      = Path(__file__).resolve().parents[1]
OUT       = ROOT / "exp_features" / "outputs"
PARQUET   = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "consolidation_finale" / "outputs" / "features_158f_sans_simba.json"
CANTON_PARQUET = ROOT / "exp_features" / "outputs" / "features_vacances_feries_cantonales.parquet"
META_JSON = ROOT / "models" / "enrichi_seg" / "enrichi_seg_metadata.json"

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
TARGET         = "target_voyageurs_2eme_classe"
NEW_FEAT       = "event_is_vacances_valais"

BASE_PARAMS = dict(
    objective="reg:squarederror",
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", random_state=SEED,
    enable_categorical=True, verbosity=0,
)

print("=" * 80)
print("CHANTIER FEATURES — Phase C : confirmation H25 de event_is_vacances_valais")
print("=" * 80)

# ── 0. Datasets ─────────────────────────────────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash {file_hash} != {HASH_ATTENDU}"
print(f"\n── 0. Dataset ── Hash {file_hash} ✓ (lecture seule)")
with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158 and NEW_FEAT not in FEATS
FEATS_159 = FEATS + [NEW_FEAT]

df = pd.read_parquet(PARQUET)
cant = pd.read_parquet(CANTON_PARQUET)
cant["base_date"] = pd.to_datetime(cant["date"])
cant = cant[["base_date", NEW_FEAT]]

# ── 1. Split TRI-ANNUEL canonique (Split C) ─────────────────────────────────
h22 = df[df["horaire_annee_horaire"] == "H22"]
mgil = ((h22["id_gare_depart_bpuic"].astype("int64") == GILAMONT_BPUIC) |
        (h22["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC))
train = pd.concat([h22[~mgil].copy(),
                   df[df["horaire_annee_horaire"] == "H23"].copy(),
                   df[df["horaire_annee_horaire"] == "H24"].copy()], ignore_index=True)
test = df[df["horaire_annee_horaire"] == "H25"].copy()
del df

train = train.merge(cant, on="base_date", how="left")
test = test.merge(cant, on="base_date", how="left")
na = int(train[NEW_FEAT].isna().sum()) + int(test[NEW_FEAT].isna().sum())
print(f"  n_train={len(train):,} n_test_H25={len(test):,} | jointure NaN={na} "
      + ("✓" if na == 0 else "✗"))
assert na == 0
train[NEW_FEAT] = train[NEW_FEAT].astype("int8"); test[NEW_FEAT] = test[NEW_FEAT].astype("int8")

def prep_X(d, feats):
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X

mtr = {"bas": (train["spatial_segment"] == "bas").values, "haut": (train["spatial_segment"] == "haut").values}
mte = {"bas": (test["spatial_segment"] == "bas").values, "haut": (test["spatial_segment"] == "haut").values}
y_tr = {s: train.loc[mtr[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_te = {s: test.loc[mte[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_te_g = test[TARGET].values.astype("float64")
BASE_SCORE = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tour_key = {
    "bas":    list(zip(test.loc[mte["bas"],  "base_date"], test.loc[mte["bas"],  "horaire_numero_train"])),
    "haut":   list(zip(test.loc[mte["haut"], "base_date"], test.loc[mte["haut"], "horaire_numero_train"])),
    "global": list(zip(test["base_date"], test["horaire_numero_train"])),
}
print(f"  TEST H25 surcharges >{SEUIL} : BAS={int((y_te['bas']>SEUIL).sum())} "
      f"HAUT={int((y_te['haut']>SEUIL).sum())} GLOBAL={int((y_te_g>SEUIL).sum())}")

# ── 2. Metriques ────────────────────────────────────────────────────────────
def pr_tr(yt, yp):
    yb = (yt > SEUIL).astype(int)
    return float(average_precision_score(yb, yp)) if yb.sum() else None
def pr_to(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp})
    agg = g.groupby("k").agg(mo=("obs", "max"), mp=("pred", "max"))
    yb = (agg["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, agg["mp"].values)) if yb.sum() else None
def mblock(yt, yp, keys):
    z = yt > SEUIL; res = yp - yt
    return {"n_obs": int(len(yt)), "n_gt63": int(z.sum()),
            "r2_global": float(r2_score(yt, yp)), "mae_global": float(mean_absolute_error(yt, yp)),
            "bias_gt63": float(res[z].mean()) if z.sum() else None,
            "mae_gt63": float(np.abs(res[z]).mean()) if z.sum() else None,
            "pr_auc_troncon": pr_tr(yt, yp), "pr_auc_tour": pr_to(keys, yt, yp)}

# ── 3. Entrainement 158f puis 159f ──────────────────────────────────────────
def run(feats, tag):
    Xtr = {s: prep_X(train[mtr[s]], feats) for s in ("bas", "haut")}
    Xte = {s: prep_X(test[mte[s]], feats) for s in ("bas", "haut")}
    models, preds = {}, {}
    for s in ("bas", "haut"):
        m = xgb.XGBRegressor(base_score=BASE_SCORE[s], **BASE_PARAMS)
        m.fit(Xtr[s], y_tr[s]); models[s] = m
        preds[s] = m.predict(Xte[s]).astype("float64")
    yp_g = np.empty(len(test)); yp_g[mte["bas"]] = preds["bas"]; yp_g[mte["haut"]] = preds["haut"]
    res = {"bas": mblock(y_te["bas"], preds["bas"], tour_key["bas"]),
           "haut": mblock(y_te["haut"], preds["haut"], tour_key["haut"]),
           "global": mblock(y_te_g, yp_g, tour_key["global"])}
    print(f"\n  [{tag}] {len(feats)}f (TEST H25) :")
    for s in ("bas", "haut", "global"):
        m = res[s]
        print(f"    {s:>6} R²={m['r2_global']:.4f} MAEg={m['mae_global']:.3f} "
              f"biais>63={m['bias_gt63']:+.2f} MAE>63={m['mae_gt63']:.2f} "
              f"PRAUC_tr={m['pr_auc_troncon']:.4f} PRAUC_tour={m['pr_auc_tour']:.4f}")
    return models, Xte, res

print("\n── 3. Entrainement CANONIQUE 158f puis 159f (Split C, reg:squarederror) ──")
t0 = time.time()
_, _, res158 = run(FEATS, "CANONIQUE")
models159, Xte159, res159 = run(FEATS_159, "CANDIDAT")
print(f"  (total {time.time()-t0:.0f}s)")

# ── 4. Garde-fou : 158f reproduit les chiffres canoniques (metadata) ────────
print("\n── 4. GARDE-FOU : 158f vs metrics_h25 canoniques (metadata enrichi_seg) ──")
meta = json.load(open(META_JSON))["metrics_h25"]
gf_ok = True
for s in ("bas", "haut", "global"):
    rc = meta[s]; mine = res158[s]
    dr2 = abs(rc["r2"] - mine["r2_global"]); dpr = abs(rc["pr_auc"] - mine["pr_auc_troncon"])
    ok = dr2 < 5e-3 and dpr < 5e-3; gf_ok = gf_ok and ok
    print(f"  {s:>6} R² canon={rc['r2']:.4f} vs {mine['r2_global']:.4f} (Δ{dr2:.4f}) | "
          f"PR-AUC(tr) canon={rc['pr_auc']:.4f} vs {mine['pr_auc_troncon']:.4f} (Δ{dpr:.4f}) "
          + ("✓" if ok else "✗"))
print("  → " + ("protocole tri-annuel reproduit ✓" if gf_ok else "ÉCART (metadata = modele segmente ; tolerance large)"))

# ── 5. SHAP de event_is_vacances_valais sur H25 ─────────────────────────────
print("\n── 5. SHAP event_is_vacances_valais sur H25 (par segment) ──")
SAMPLE = 60000
shap_sum = {}
for s in ("bas", "haut"):
    X = Xte159[s]
    if len(X) > SAMPLE:
        X = X.sample(SAMPLE, random_state=SEED)
    bst = models159[s].get_booster()
    contribs = bst.predict(xgb.DMatrix(X, enable_categorical=True), pred_contribs=True)
    names = list(X.columns); ma = np.abs(contribs[:, :-1]).mean(axis=0)
    order = np.argsort(ma)[::-1]; idx = names.index(NEW_FEAT)
    rank = int(np.where(order == idx)[0][0]) + 1
    pct = 100 * ma[idx] / ma.sum()
    shap_sum[s] = {"rank": rank, "n_features": len(names), "mean_abs_shap": float(ma[idx]), "pct_total": float(pct)}
    print(f"  {s:>6}: rang {rank}/{len(names)}  mean|SHAP|={ma[idx]:.4f}  {pct:.2f}% du total")

# ── 6. Generalisation : Δ H25 vs Δ validation H24 ───────────────────────────
print("\n" + "=" * 80)
print("GENERALISATION H25 — 158f vs 159f (event_is_vacances_valais seule)")
print("=" * 80)
VALID_DELTA = {"bas": {"pr_auc_troncon": +0.0191, "pr_auc_tour": +0.0122},  # rappel Phase B (H24)
               "haut": {"pr_auc_troncon": -0.0022, "pr_auc_tour": +0.0015}}
print(f"{'segment':>6} {'metric':>14} | {'158f':>9} | {'159f':>9} | {'Δ H25':>9} | {'Δ valid H24':>11}")
print("-" * 74)
rows = []
for s in ("bas", "haut", "global"):
    for met in ["r2_global", "mae_global", "bias_gt63", "mae_gt63", "pr_auc_troncon", "pr_auc_tour"]:
        b = res158[s][met]; c = res159[s][met]; d = (c - b) if (b is not None and c is not None) else None
        vd = VALID_DELTA.get(s, {}).get(met)
        ds = f"{d:+.4f}" if d is not None else "   n/a"
        vs = f"{vd:+.4f}" if vd is not None else ""
        print(f"{s:>6} {met:>14} | {b:>9.4f} | {c:>9.4f} | {ds:>9} | {vs:>11}")
        rows.append({"segment": s, "metric": met, "v158": b, "v159": c, "delta_h25": d, "delta_valid_h24": vd})
    print("-" * 74)

db_tr = res159["bas"]["pr_auc_troncon"] - res158["bas"]["pr_auc_troncon"]
db_to = res159["bas"]["pr_auc_tour"] - res158["bas"]["pr_auc_tour"]
print(f"\nQUESTION CLÉ — gain BAS se confirme-t-il sur H25 ?")
print(f"  PR-AUC BAS tronçon : H24 valid +0.0191  →  H25 test {db_tr:+.4f}")
print(f"  PR-AUC BAS tour    : H24 valid +0.0122  →  H25 test {db_to:+.4f}")
if db_tr >= 0.015 and db_to >= 0.008:
    verdict = "Gain BAS CONFIRMÉ sur H25 (même ordre qu'en validation)"
elif db_tr <= 0.005 and db_to <= 0.005:
    verdict = "Gain BAS ÉVAPORÉ sur H25 (ne généralise pas — comme le R² de k=2)"
else:
    verdict = "Gain BAS PARTIEL / atténué sur H25"
print(f"  VERDICT (factuel) : {verdict}")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "phaseC_confirm_h25.json").write_text(json.dumps({
    "experiment": "Phase C — confirmation H25 event_is_vacances_valais",
    "statut": "EXPERIMENTAL hors canonique — aucun modele sauvegarde, hash 416bb90b intact, H25 touche une fois (rapport)",
    "protocole": "train H22(Gilamont exclu)+H23+H24 → test H25 (Split C) ; iso ADR-CF09 seed42 seuil63 reg:squarederror seg bas/haut",
    "garde_fou_158f_reproduit_canon": gf_ok,
    "canonique_158f": res158, "candidat_159f": res159,
    "shap_vacances_valais_h25": shap_sum, "deltas": rows,
    "gain_bas_h25": {"pr_auc_troncon": db_tr, "pr_auc_tour": db_to},
    "rappel_valid_h24": VALID_DELTA, "verdict": verdict,
}, indent=2, ensure_ascii=False))
print(f"\nFichier : {OUT/'phaseC_confirm_h25.json'}")
print("ARRÊT — table H25 produite. Rien adopte, rien industrialise, aucun stage. ADR a rediger ensuite.")
print("=" * 80)
