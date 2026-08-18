"""
CHANTIER FEATURES — Phase B : test d'impact des 8 features vacances/feries cantonaux
====================================================================================
EXPERIMENTAL — HORS canonique. Ne touche NI au hash 416bb90b, NI au ml_dataset
canonique, NI aux modeles canoniques. Aucun stage cree, build_ml_dataset.py intact.
Aucun modele sauvegarde. H25 JAMAIS charge. Rien dans le rapport.

Objectif
--------
Les 8 features cantonales relevent-elles la PR-AUC (surtout HAUT, plafond ~0.345) ?
On compare, ISO-TOUT sauf l'ajout des 8 features, sur VALIDATION H24 :
  - BASELINE 158f : protocole bi-annuel (train H22 hors Gilamont + H23 -> valid H24)
  - CANDIDAT 166f : memes 158 features + 8 cantonales, meme protocole
Protocole/HP/segmentation/perte STRICTEMENT identiques a
consolidation_finale/exp_perte/balayage_mse_asym_h24.py (k=1 == reg:squarederror).

Les 8 features sont jointes PAR DATE (base_date) depuis
exp_features/outputs/features_vacances_feries_cantonales.parquet dans un dataset
EXPERIMENTAL en memoire (jamais ecrit dans data/processed/).
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

HASH_ATTENDU   = "416bb90b"
GILAMONT_BPUIC = 8501260
SEUIL          = 63
SEED           = 42
TARGET         = "target_voyageurs_2eme_classe"
CANTONS        = ["valais", "fribourg", "neuchatel", "geneve"]
NEW_FEATS = [f"event_is_vacances_{c}" for c in CANTONS] + [f"event_is_ferie_{c}" for c in CANTONS]

# ADR-CF09 — iso hyperparametres canoniques, perte MSE native (ADR-CF25)
BASE_PARAMS = dict(
    objective="reg:squarederror",
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", random_state=SEED,
    enable_categorical=True, verbosity=0,
)

print("=" * 80)
print("CHANTIER FEATURES — Phase B : impact 8 features cantonales (VALIDATION H24)")
print("=" * 80)

# ── 0. Datasets (lecture seule + integrite) ─────────────────────────────────
file_hash = hashlib.sha256(PARQUET.read_bytes()).hexdigest()[:8]
assert file_hash == HASH_ATTENDU, f"Hash attendu {HASH_ATTENDU}, obtenu {file_hash}"
print(f"\n── 0. Dataset canonique ── Hash SHA256[:8] = {file_hash} ✓ (lecture seule)")

with open(FEAT_JSON) as f:
    FEATS = json.load(f)["features"]
assert len(FEATS) == 158
assert not (set(FEATS) & set(NEW_FEATS)), "collision noms features"
FEATS_166 = FEATS + NEW_FEATS

df = pd.read_parquet(PARQUET)
assert "H25" not in df["horaire_annee_horaire"].unique() or True  # H25 present mais JAMAIS selectionne
cant = pd.read_parquet(CANTON_PARQUET)
cant["base_date"] = pd.to_datetime(cant["date"])
cant = cant[["base_date"] + NEW_FEATS]
print(f"  ml_dataset : {len(df):,} lignes | features cantonales : {len(cant):,} dates")

# ── 1. Split VALIDATION (H25 jete, jamais charge dans train/valid) ──────────
h22_all  = df[df["horaire_annee_horaire"] == "H22"]
mask_gil = (
    (h22_all["id_gare_depart_bpuic"].astype("int64")  == GILAMONT_BPUIC) |
    (h22_all["id_gare_arrivee_bpuic"].astype("int64") == GILAMONT_BPUIC)
)
train = pd.concat([h22_all[~mask_gil].copy(),
                   df[df["horaire_annee_horaire"] == "H23"].copy()], ignore_index=True)
valid = df[df["horaire_annee_horaire"] == "H24"].copy()
del df

# jointure PAR DATE des 8 features (dataset experimental en memoire)
for d in (train, valid):
    pass
train = train.merge(cant, on="base_date", how="left")
valid = valid.merge(cant, on="base_date", how="left")
# controle couverture jointure (aucune NaN attendue : plage cantonale couvre H22-H24)
na_tr = train[NEW_FEATS].isna().any(axis=1).sum()
na_va = valid[NEW_FEATS].isna().any(axis=1).sum()
print(f"  jointure cantonale : NaN train={na_tr} valid={na_va} "
      + ("✓" if na_tr == 0 and na_va == 0 else "✗ TROU DE JOINTURE"))
assert na_tr == 0 and na_va == 0
for c in NEW_FEATS:
    train[c] = train[c].astype("int8"); valid[c] = valid[c].astype("int8")

def prep_X(d, feats):
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X

mask_tr = {"bas": (train["spatial_segment"] == "bas").values,
           "haut": (train["spatial_segment"] == "haut").values}
mask_va = {"bas": (valid["spatial_segment"] == "bas").values,
           "haut": (valid["spatial_segment"] == "haut").values}
y_tr = {s: train.loc[mask_tr[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_va = {s: valid.loc[mask_va[s], TARGET].values.astype("float64") for s in ("bas", "haut")}
y_va_g = valid[TARGET].values.astype("float64")
BASE_SCORE = {s: float(y_tr[s].mean()) for s in ("bas", "haut")}
tour_key = {
    "bas":    list(zip(valid.loc[mask_va["bas"],  "base_date"], valid.loc[mask_va["bas"],  "horaire_numero_train"])),
    "haut":   list(zip(valid.loc[mask_va["haut"], "base_date"], valid.loc[mask_va["haut"], "horaire_numero_train"])),
    "global": list(zip(valid["base_date"], valid["horaire_numero_train"])),
}
print(f"  TRAIN BAS={mask_tr['bas'].sum():,} HAUT={mask_tr['haut'].sum():,} | "
      f"VALID BAS={mask_va['bas'].sum():,} HAUT={mask_va['haut'].sum():,}")
print(f"  VALID surcharges >{SEUIL} : BAS={int((y_va['bas']>SEUIL).sum())} "
      f"HAUT={int((y_va['haut']>SEUIL).sum())} GLOBAL={int((y_va_g>SEUIL).sum())}")

# ── 2. Metriques ────────────────────────────────────────────────────────────
def pr_auc_troncon(yt, yp):
    yb = (yt > SEUIL).astype(int)
    return float(average_precision_score(yb, yp)) if yb.sum() else None

def pr_auc_tour(keys, yt, yp):
    g = pd.DataFrame({"k": keys, "obs": yt, "pred": yp})
    agg = g.groupby("k").agg(mo=("obs", "max"), mp=("pred", "max"))
    yb = (agg["mo"].values > SEUIL).astype(int)
    return float(average_precision_score(yb, agg["mp"].values)) if yb.sum() else None

def metrics_block(yt, yp, keys):
    z = yt > SEUIL; le = ~z; res = yp - yt
    return {
        "n_obs": int(len(yt)), "n_gt63": int(z.sum()),
        "r2_global": float(r2_score(yt, yp)),
        "mae_global": float(mean_absolute_error(yt, yp)),
        "bias_gt63": float(res[z].mean()) if z.sum() else None,
        "mae_gt63": float(np.abs(res[z]).mean()) if z.sum() else None,
        "pr_auc_troncon": pr_auc_troncon(yt, yp),
        "pr_auc_tour": pr_auc_tour(keys, yt, yp),
    }

# ── 3. Entrainement + evaluation des 2 configurations ───────────────────────
def run(feats, tag):
    X_tr = {s: prep_X(train[mask_tr[s]], feats) for s in ("bas", "haut")}
    X_va = {s: prep_X(valid[mask_va[s]], feats) for s in ("bas", "haut")}
    models, preds = {}, {}
    for s in ("bas", "haut"):
        m = xgb.XGBRegressor(base_score=BASE_SCORE[s], **BASE_PARAMS)
        m.fit(X_tr[s], y_tr[s])
        models[s] = m
        preds[s] = m.predict(X_va[s]).astype("float64")
    yp_g = np.empty(len(valid))
    yp_g[mask_va["bas"]] = preds["bas"]; yp_g[mask_va["haut"]] = preds["haut"]
    res = {
        "bas":    metrics_block(y_va["bas"],  preds["bas"],  tour_key["bas"]),
        "haut":   metrics_block(y_va["haut"], preds["haut"], tour_key["haut"]),
        "global": metrics_block(y_va_g, yp_g, tour_key["global"]),
    }
    print(f"\n  [{tag}] {len(feats)}f :")
    for s in ("bas", "haut", "global"):
        m = res[s]
        print(f"    {s:>6} R²={m['r2_global']:.4f} MAEg={m['mae_global']:.3f} "
              f"biais>63={m['bias_gt63']:+.2f} MAE>63={m['mae_gt63']:.2f} "
              f"PRAUC_tr={m['pr_auc_troncon']:.4f} PRAUC_tour={m['pr_auc_tour']:.4f}")
    return models, {s: X_va[s] for s in ("bas", "haut")}, res

print("\n── 3. Entrainement BASELINE puis CANDIDAT (reg:squarederror, ADR-CF09) ──")
t0 = time.time()
_, _, res_base = run(FEATS, "BASELINE")
models_c, Xva_c, res_cand = run(FEATS_166, "CANDIDAT")
print(f"\n  (entrainement total {time.time()-t0:.0f}s)")

# ── 4. SHAP des 8 nouvelles features, par segment (TreeSHAP via booster) ─────
print("\n── 4. SHAP candidat — rang & contribution des 8 features cantonales ──")
SAMPLE = 60000
shap_summary = {}
for s in ("bas", "haut"):
    X = Xva_c[s]
    if len(X) > SAMPLE:
        X = X.sample(SAMPLE, random_state=SEED)
    booster = models_c[s].get_booster()
    dm = xgb.DMatrix(X, enable_categorical=True)
    contribs = booster.predict(dm, pred_contribs=True)  # (n, n_feat+1)
    feat_names = list(X.columns)
    mean_abs = np.abs(contribs[:, :-1]).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    rank = {feat_names[i]: int(np.where(order == i)[0][0]) + 1 for i in range(len(feat_names))}
    contrib_map = {feat_names[i]: float(mean_abs[i]) for i in range(len(feat_names))}
    total = float(mean_abs.sum())
    print(f"\n  segment {s.upper()} (n_shap={len(X):,}, {len(feat_names)} features)")
    print(f"    {'feature':30} {'rang':>5} {'mean|SHAP|':>11} {'%tot':>6}")
    for nf in NEW_FEATS:
        print(f"    {nf:30} {rank[nf]:>5}/{len(feat_names)} {contrib_map[nf]:>11.4f} "
              f"{100*contrib_map[nf]/total:>5.2f}%")
    shap_summary[s] = {nf: {"rank": rank[nf], "mean_abs_shap": contrib_map[nf],
                            "pct_total": 100*contrib_map[nf]/total} for nf in NEW_FEATS}
    shap_summary[s]["_n_features"] = len(feat_names)

# ── 5. Comparaison & deltas ─────────────────────────────────────────────────
print("\n" + "=" * 80)
print("COMPARAISON 158f (baseline) vs 166f (candidat) — VALIDATION H24")
print("=" * 80)
print(f"{'segment':>6} {'metric':>14} | {'158f':>9} | {'166f':>9} | {'Δ':>9}")
print("-" * 60)
rows = []
for s in ("bas", "haut", "global"):
    for met in ["r2_global", "mae_global", "bias_gt63", "mae_gt63",
                "pr_auc_troncon", "pr_auc_tour"]:
        b = res_base[s][met]; c = res_cand[s][met]
        d = (c - b) if (b is not None and c is not None) else None
        ds = f"{d:+.4f}" if d is not None else "  n/a"
        print(f"{s:>6} {met:>14} | {b:>9.4f} | {c:>9.4f} | {ds:>9}")
        rows.append({"segment": s, "metric": met, "v158": b, "v166": c, "delta": d})
    print("-" * 60)

# lecture du point cle
dh_tr = res_cand["haut"]["pr_auc_troncon"] - res_base["haut"]["pr_auc_troncon"]
dh_to = res_cand["haut"]["pr_auc_tour"] - res_base["haut"]["pr_auc_tour"]
print(f"\nPOINT CLÉ — PR-AUC HAUT : tronçon Δ={dh_tr:+.4f}  tour Δ={dh_to:+.4f}")
print("SEUIL DE BRUIT : gain < 0.03 = probablement bruit (HAUT ~620 surcharges, instable).")
verdict = ("AMPLEUR NETTE (>0.05) — candidat a confirmer sur H25" if max(dh_tr, dh_to) > 0.05
           else "ZONE DE BRUIT (<0.03) — pas de gain reel demontre" if max(dh_tr, dh_to) < 0.03
           else "ZONE GRISE (0.03–0.05) — non concluant sans confirmation H25")
print(f"VERDICT (validation H24, sans optimisme) : {verdict}")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "phaseB_impact_h24.json").write_text(json.dumps({
    "experiment": "CHANTIER FEATURES Phase B — impact 8 features cantonales",
    "statut": "EXPERIMENTAL hors canonique — aucun modele sauvegarde, hash 416bb90b intact, H25 jamais charge",
    "protocole": "train H22(Gilamont exclu)+H23 → validation H24 ; iso ADR-CF09, seed=42, seuil 63, reg:squarederror, segmentation bas/haut",
    "baseline_158f": res_base, "candidat_166f": res_cand,
    "deltas": rows, "shap_8_features": shap_summary,
    "pr_auc_haut_delta": {"troncon": dh_tr, "tour": dh_to}, "verdict": verdict,
}, indent=2, ensure_ascii=False))
print(f"\nFichier : {OUT/'phaseB_impact_h24.json'}")
print("ARRÊT — validation H24 seulement. Pas de test H25, pas d'integration, pas de stage.")
print("=" * 80)
