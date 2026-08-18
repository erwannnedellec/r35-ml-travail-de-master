#!/usr/bin/env python3
"""
Phase 4 migration de gel (416bb90b -> ba493568) : reentrainement iso-protocole,
recalibration couche 2 (H24), evaluation H25 comparative. ADR-076.

Threads numeriques = 1 (contrat de reproductibilite ADR-076) : pinning AVANT tout
import numerique. Le module couche2 (decision/blocs) est MONKEYPATCHE vers les
artefacts ba493568 (code source non modifie ; propagation du hash = phase 5).

Sorties : models/enrichi_seg/enrichi_seg_{bas,haut}_ba493568.json, metadata,
outputs/couche2/q_couche2_{calibration_H24,eval}_ba493568.json, et un JSON de
resultats consolides pour le tableau comparatif du GATE 4.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import r2_score, mean_absolute_error, average_precision_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

HASH = "ba493568"
SEED = 42
SEUIL = 63
GILAMONT_BPUIC = 8501260
MODEL_DIR = ROOT / "models/enrichi_seg"
OUT_C2 = ROOT / "outputs/couche2"
TARE_T = 54.2
TARIF_TBKM = 0.06444

XGB_PARAMS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    objective="reg:squarederror", tree_method="hist",
    random_state=SEED, enable_categorical=True, verbosity=0,
)


def sha8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def prep_X(d: pd.DataFrame, feats: list) -> pd.DataFrame:
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X


def r2_ci(y, p, n_boot=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[i] = r2_score(y[idx], p[idx])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def seg_metrics(y, p):
    gt = y > SEUIL
    lo, hi = r2_ci(y, p)
    return {
        "n_obs": int(len(y)), "r2": float(r2_score(y, p)),
        "r2_ci_lo": lo, "r2_ci_hi": hi,
        "mae": float(mean_absolute_error(y, p)),
        "mae_gt63": float(np.mean(np.abs(p[gt] - y[gt]))) if gt.any() else None,
        "bias_gt63": float(np.mean(p[gt] - y[gt])) if gt.any() else None,
        "pr_auc": float(average_precision_score(gt.astype(int), p)) if gt.any() else None,
        "prevalence": float(gt.mean()), "n_gt63": int(gt.sum()),
    }


def main():
    t0 = time.time()
    print(f"=== PHASE 4 — reentrainement + recalibration + evaluation ({HASH}) ===")
    print(f"threads: OMP={os.environ['OMP_NUM_THREADS']} VECLIB={os.environ['VECLIB_MAXIMUM_THREADS']}")

    # ---- 0. dataset + features ----
    dsfile = ROOT / "data/processed/ml_dataset.parquet"
    h = sha8(dsfile)
    print(f"dataset hash = {h} (attendu {HASH})")
    assert h == HASH, f"hash dataset {h} != {HASH}"
    feats = json.loads((OUT_C2 / "features_158f_sans_simba.json").read_text())["features"]
    assert len(feats) == 158, f"{len(feats)} features != 158"

    df = pd.read_parquet(dsfile)
    for c in ("horaire_annee_horaire", "spatial_segment", "target_voyageurs_2eme_classe",
              "id_gare_depart_bpuic", "id_gare_arrivee_bpuic"):
        assert c in df.columns, f"colonne manquante {c}"

    # ---- 4a. Split C + segmentation + reentrainement ----
    t_train0 = time.time()
    h22 = df[df["horaire_annee_horaire"] == "H22"]
    gil = ((h22["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
           (h22["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC))
    train = pd.concat([h22[~gil], df[df["horaire_annee_horaire"].isin(["H23", "H24"])]],
                      ignore_index=True)
    test = df[df["horaire_annee_horaire"] == "H25"].copy()
    print(f"Split C : train={len(train)} (attendu 801282) | test H25={len(test)} (attendu 309252)")

    models, metrics, y_all, p_all = {}, {}, [], []
    for seg in ("bas", "haut"):
        mtr = train[train["spatial_segment"] == seg]
        mte = test[test["spatial_segment"] == seg]
        Xtr, ytr = prep_X(mtr, feats), mtr["target_voyageurs_2eme_classe"].values.astype("float64")
        Xte, yte = prep_X(mte, feats), mte["target_voyageurs_2eme_classe"].values.astype("float64")
        m = xgb.XGBRegressor(**XGB_PARAMS)
        m.fit(Xtr, ytr)
        pte = m.predict(Xte).astype("float64")
        out = MODEL_DIR / f"enrichi_seg_{seg}_{HASH}.json"
        m.save_model(str(out))
        models[seg] = {"file": str(out.relative_to(ROOT)), "hash_sha256_8": sha8(out)}
        metrics[seg] = seg_metrics(yte, pte)
        y_all.append(yte); p_all.append(pte)
        print(f"  {seg}: R2={metrics[seg]['r2']:.4f} PR-AUC={metrics[seg]['pr_auc']:.4f} "
              f"n={metrics[seg]['n_obs']} model_hash={models[seg]['hash_sha256_8']}")
    y_all, p_all = np.concatenate(y_all), np.concatenate(p_all)
    metrics["global"] = seg_metrics(y_all, p_all)
    print(f"  global: R2={metrics['global']['r2']:.4f} PR-AUC={metrics['global']['pr_auc']:.4f}")
    t_train = time.time() - t_train0

    meta = {
        "model_id": "enrichi_seg_couche1", "version": "2.0", "generation": HASH,
        "split": {"rule": "Split C", "n_train": int(len(train)), "n_test": int(len(test))},
        "dataset": {"file": "data/processed/ml_dataset.parquet", "hash_sha256_8": HASH,
                    "n_features": 158, "reproductible": "double clean-all && make pinne -> ba493568 (ADR-076)"},
        "models": models,
        "hyperparams": "ADR-052 (XGBoost MSE, 300/6/0.1/0.8/0.8, seed=42) ; threads=1 ADR-076",
        "seuil_surcharge": 63, "metrics_h25": metrics,
        "supersedes": {"v1.9": "416bb90b"},
    }
    (MODEL_DIR / "enrichi_seg_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # ---- 4b/4c. couche 2 : monkeypatch vers ba493568, recalibration + evaluation ----
    from couche2 import blocs, decision
    blocs.HASH_CANONIQUE = HASH
    # assert_canonical_dataset lie sa valeur par defaut `expected` a la DEFINITION :
    # patcher HASH_CANONIQUE ne suffit pas, on remplace la fonction (gotcha default arg).
    _orig_assert = blocs.assert_canonical_dataset
    blocs.assert_canonical_dataset = lambda path=blocs.ML_DATASET, expected=HASH: _orig_assert(path, expected)
    decision.MODEL_BAS = MODEL_DIR / f"enrichi_seg_bas_{HASH}.json"
    decision.MODEL_HAUT = MODEL_DIR / f"enrichi_seg_haut_{HASH}.json"
    decision.HASH_MODEL_BAS = models["bas"]["hash_sha256_8"]
    decision.HASH_MODEL_HAUT = models["haut"]["hash_sha256_8"]

    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)     # GARDES BLOQUANTES 29222 / 2072
    print(f"[GARDES] {info}")

    t_cal0 = time.time()
    calib = decision.calibrate(ds)
    (OUT_C2 / f"q_couche2_calibration_H24_{HASH}.json").write_text(
        json.dumps(calib, indent=2, ensure_ascii=False))
    ev = decision.evaluate_h25(ds, calib)
    ev["meta"]["hash"] = HASH
    ev_nocurve = {k: v for k, v in ev.items() if k != "_pr_curve"}
    (OUT_C2 / f"q_couche2_eval_{HASH}.json").write_text(
        json.dumps(ev_nocurve, indent=2, ensure_ascii=False))
    t_cal = time.time() - t_cal0

    # ---- 4d extras : baseline invariance, strates, 166+, couts FP ----
    h25 = ds[ds["annee"] == "H25"].copy()
    y = h25["label"].values.astype(bool)
    seg = h25["segment"].values
    taus = {rk: calib["regles_deployables"][rk]["seuil"]
            for rk in ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")}

    # distance par course (H25) pour les couts FP
    dh25 = df[df["horaire_annee_horaire"] == "H25"].copy()
    distcol = "spatial_distance_km"
    have_dist = distcol in dh25.columns
    if have_dist:
        dh25["date"] = pd.to_datetime(dh25["base_date"]).dt.normalize()
        dh25["numero_train"] = dh25["horaire_numero_train"].astype("Int64").astype(str)
        cdist = dh25.groupby(["date", "numero_train"])[distcol].sum().rename("dist_km").reset_index()
        h25 = h25.merge(cdist, on=["date", "numero_train"], how="left")
    else:
        h25["dist_km"] = np.nan

    def capt(rk_or_human):
        if rk_or_human == "humaine":
            return h25["is_UM"].values.astype(bool)
        return h25["score"].values >= taus[rk_or_human]

    rules = ["a_iso_volume", "b_rappel_renforce", "c_haute_precision", "humaine"]

    # strates de charge (courses surcharge)
    charge = h25["charge_max"].values
    strata = {"63-93": (charge > 63) & (charge < 94),
              "94-165": (charge >= 94) & (charge < 166),
              "166+": (charge >= 166)}
    strata_recall = {}
    for sname, smask in strata.items():
        tot = int((y & smask).sum())
        strata_recall[sname] = {"n_surcharges": tot}
        for rk in rules:
            cap = capt(rk)
            strata_recall[sname][rk] = (int((cap & y & smask).sum()) / tot) if tot else None

    # 166+ (les cas extremes), capture par regle
    top166 = h25[charge >= 166].sort_values("charge_max", ascending=False)
    cas166 = []
    for row in top166.itertuples(index=False):
        d = {"date": str(pd.Timestamp(row.date).date()), "numero_train": row.numero_train,
             "segment": row.segment, "charge": float(row.charge_max), "score": round(float(row.score), 1)}
        for rk in rules:
            if rk == "humaine":
                d["humaine"] = bool(row.is_UM)
            else:
                d[rk] = bool(row.score >= taus[rk])
        cas166.append(d)
    capture_166 = {rk: sum(1 for c in cas166 if c[rk]) for rk in rules}
    capture_166["_n"] = len(cas166)

    # couts FP (volet B)
    couts_fp = {}
    for rk in rules:
        cap = capt(rk)
        fp = cap & ~y
        if have_dist:
            cout = float((TARE_T * h25.loc[fp, "dist_km"].fillna(0).values * TARIF_TBKM).sum())
        else:
            cout = None
        couts_fp[rk] = {"n_FP": int(fp.sum()), "cout_CHF": round(cout, 0) if cout is not None else None}

    # rappel HAUT mai-juin 2025 (par regle, au point de reference et global)
    dts = pd.to_datetime(h25["date"])
    mj_haut = (seg == "haut") & dts.dt.month.isin([5, 6]).values
    mj_haut_surch = mj_haut & y
    narc_focus = {"n_surcharges_haut_mai_juin": int(mj_haut_surch.sum())}
    for rk in rules:
        cap = capt(rk)
        tot = int(mj_haut_surch.sum())
        narc_focus[rk] = {
            "rappel": (int((cap & mj_haut_surch).sum()) / tot) if tot else None,
            "FN": int((~cap & mj_haut_surch).sum()),
        }

    # baseline humaine invariance (via blocs canonique)
    try:
        base = blocs.compute_baseline()
        ref = base["reference_phase2_course_H25"]
        baseline_check = {"budget_UM_H25": ref["budget_UM_H25"],
                          "n_surcharges_H25": ref["n_surcharges_H25"],
                          "VP": ref["global"]["VP"], "precision": ref["global"]["precision"],
                          "rappel": ref["global"]["rappel"]}
    except Exception as e:
        baseline_check = {"erreur": str(e)}

    results = {
        "generation": HASH, "gardes": info, "metrics_h25": metrics,
        "seuils": {rk: round(t, 4) for rk, t in taus.items()},
        "points_operation": {rk: decision._eval_full((h25["score"].values >= taus[rk]), y, seg)
                             if rk != "humaine" else decision._eval_full(h25["is_UM"].values.astype(bool), y, seg)
                             for rk in rules},
        "artefact_complet": ev["artefact_complet_reference"],
        "strata_recall": strata_recall, "capture_166": capture_166, "cas166": cas166,
        "couts_fp": couts_fp, "baseline_humaine_H25": baseline_check,
        "narcisses_mai_juin_haut": narc_focus,
        "durees_s": {"reentrainement": round(t_train, 1), "recalibration_eval": round(t_cal, 1),
                     "total": round(time.time() - t0, 1)},
        "distance_disponible": have_dist,
    }
    (OUT_C2 / f"phase4_resultats_{HASH}.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n[OK] resultats -> outputs/couche2/phase4_resultats_{HASH}.json")
    print(f"seuils a'/b/c = {taus['a_iso_volume']:.2f} / {taus['b_rappel_renforce']:.2f} / {taus['c_haute_precision']:.2f}")
    print(f"baseline H25 (invariante attendue) : {baseline_check}")
    print(f"durees: train={t_train:.0f}s calib/eval={t_cal:.0f}s total={time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
