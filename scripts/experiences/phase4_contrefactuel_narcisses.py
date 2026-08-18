#!/usr/bin/env python3
"""
Phase 4e — contrefactuel narcisses mai-juin HAUT (ADR-076).

Les modeles ba493568 sont byte-identiques a 416bb90b (train inchange). Le SEUL
changement H25 est narcisses 2025. On isole donc l'effet en re-predisant H25 avec
les features narcisses 2025 REMISES A ZERO (= etat 416bb90b) et en comparant le
rappel HAUT mai-juin (au meme perimetre/segment/label, aux memes seuils H24).
Threads=1 (ADR-076).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
HASH = "ba493568"
MODEL_DIR = ROOT / "models/enrichi_seg"


def main():
    from couche2 import blocs, decision
    blocs.HASH_CANONIQUE = HASH
    _oa = blocs.assert_canonical_dataset
    blocs.assert_canonical_dataset = lambda path=blocs.ML_DATASET, expected=HASH: _oa(path, expected)
    decision.MODEL_BAS = MODEL_DIR / f"enrichi_seg_bas_{HASH}.json"
    decision.MODEL_HAUT = MODEL_DIR / f"enrichi_seg_haut_{HASH}.json"
    import hashlib
    decision.HASH_MODEL_BAS = hashlib.sha256(decision.MODEL_BAS.read_bytes()).hexdigest()[:8]
    decision.HASH_MODEL_HAUT = hashlib.sha256(decision.MODEL_HAUT.read_bytes()).hexdigest()[:8]

    # ds NEW (narcisses ON) : perimetre / segment / label / score(new)
    ds = decision.build_decision_set()
    calib = decision.calibrate(ds)
    taus = {rk: calib["regles_deployables"][rk]["seuil"] for rk in
            ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")}

    # score OLD-equiv : re-predire H25 avec narcisses 2025 OFF
    feats = json.loads((ROOT / "outputs/couche2/features_158f_sans_simba.json").read_text())["features"]
    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    d = df[df["horaire_annee_horaire"] == "H25"].copy()
    m2025 = pd.to_datetime(d["base_date"]).dt.year.values == 2025
    n_flip = int(((d["event_is_saison_narcisses"].fillna(False).astype(bool)) & m2025).sum())
    d.loc[m2025, "event_is_saison_narcisses"] = False
    if "event_narcisses_source" in d.columns:
        d.loc[m2025, "event_narcisses_source"] = "hors_saison"
    d["event_narcisses_source"] = d["event_narcisses_source"].astype("string")

    mb = xgb.XGBRegressor(); mb.load_model(str(decision.MODEL_BAS))
    mh = xgb.XGBRegressor(); mh.load_model(str(decision.MODEL_HAUT))
    pred = np.empty(len(d), dtype="float64")
    mbmask = (d["spatial_segment"] == "bas").values
    mhmask = (d["spatial_segment"] == "haut").values
    pred[mbmask] = mb.predict(decision._prep_X(d[mbmask], feats)).astype("float64")
    pred[mhmask] = mh.predict(decision._prep_X(d[mhmask], feats)).astype("float64")
    tr_old = pd.DataFrame({
        "date": pd.to_datetime(d["base_date"]).dt.normalize().values,
        "numero_train": d["horaire_numero_train"].astype("Int64").astype(str).values,
        "pred_old": pred})
    course_old = tr_old.groupby(["date", "numero_train"], sort=True)["pred_old"].max().reset_index()

    h25 = ds[ds["annee"] == "H25"].merge(course_old, on=["date", "numero_train"], how="left")
    y = h25["label"].values.astype(bool)
    seg = h25["segment"].values
    dts = pd.to_datetime(h25["date"])
    mj = (seg == "haut") & dts.dt.month.isin([5, 6]).values & y
    tot = int(mj.sum())

    def recall(scorecol, tau):
        cap = h25[scorecol].values >= tau
        return int((cap & mj).sum()) / tot, int((~cap & mj).sum())

    out = {"n_flip_narcisses_2025_H25_troncons": n_flip,
           "n_surcharges_haut_mai_juin": tot, "seuils": taus, "par_regle": {}}
    for rk, tau in taus.items():
        r_new, fn_new = recall("score", tau)
        r_old, fn_old = recall("pred_old", tau)
        out["par_regle"][rk] = {"ancien_equiv": {"rappel": r_old, "FN": fn_old},
                                "nouveau": {"rappel": r_new, "FN": fn_new}}
    # humaine (inchangee)
    hum = h25["is_UM"].values.astype(bool)
    out["humaine"] = {"rappel": int((hum & mj).sum()) / tot, "FN": int((~hum & mj).sum())}
    (ROOT / f"outputs/couche2/phase4_contrefactuel_narcisses_{HASH}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False))

    print(f"=== Contrefactuel narcisses mai-juin HAUT (n_surcharges={tot}) ===")
    print(f"troncons H25 dont narcisses 2025 remis OFF : {n_flip}")
    for rk, tau in taus.items():
        p = out["par_regle"][rk]
        print(f"  {rk:20} (tau={tau:.1f}) : rappel ancien-equiv={p['ancien_equiv']['rappel']:.3f} "
              f"(FN {p['ancien_equiv']['FN']}) -> nouveau={p['nouveau']['rappel']:.3f} (FN {p['nouveau']['FN']})")
    print(f"  humaine (inchangee)  : rappel={out['humaine']['rappel']:.3f} (FN {out['humaine']['FN']})")


if __name__ == "__main__":
    main()
