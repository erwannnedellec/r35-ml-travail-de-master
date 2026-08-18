#!/usr/bin/env python3
"""Section 4.5.6 (extension) — Phase 2D (OPTIONNEL) : interactions SHAP sur le HAUT.

Interactions TreeSHAP entre {température, neige} et les variables de CALENDRIER (famille
cal_), segment HAUT.

COÛT (calibré sur ce modèle) : `pred_interactions=True` = **~2,15 s/observation**
(matrice complète 159×159 par ligne). L'échantillon NOMINAL de 20 000 obs (repli prévu
par la mission) coûterait ~12 h ; 3 000 obs ~1,8 h. On échantillonne donc
**R356_NSAMPLE (défaut 600) observations HAUT, graine 42** — réduction assumée et
documentée, dictée par le coût, non par un choix statistique. Résultat INDICATIF
(classement des paires), pas une estimation de précision.

Convention de symétrie : XGBoost renvoie Phi_ij symétrique ; on rapporte |Phi_ij| tel
quel (hors diagonale, l'effet de paire complet vaut 2·Phi_ij). On n'extrait que les
lignes {température, neige} de la matrice. Mesure : moyenne de |Phi_ij| (voyageurs).
LECTURE SEULE. Sortie : tableaux/section_4_5_6/t_interactions_haut.csv.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[4]
TAB = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402

N_SAMPLE = int(os.environ.get("R356_NSAMPLE", "600"))   # réduit par coût (2,15 s/obs) ; documenté
SEED = 42
ROW_FEATS = ["meteo_temperature_h", "meteo_neige_binaire_h"]
CHUNK = 200


def main() -> int:
    t0 = time.time()
    print("=== s03 — interactions SHAP {température, neige} × calendrier (HAUT, échantillon 20k) ===")
    print("dataset:", H.assert_dataset())
    feats = H.load_features_158()
    idx = {f: i for i, f in enumerate(feats)}
    cb = pd.read_csv(CODEBOOK)
    fam = dict(zip(cb["colonne"], cb["famille"]))
    cal_feats = [f for f in feats if fam.get(f) == "cal_"]

    need = list(dict.fromkeys(feats + ["horaire_annee_horaire", "spatial_segment"]))
    h25 = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet", columns=need,
                          filters=[("horaire_annee_horaire", "==", "H25")])
    haut = h25[h25["spatial_segment"] == "haut"].reset_index(drop=True)
    if len(haut) > N_SAMPLE:
        take = np.random.default_rng(SEED).choice(len(haut), N_SAMPLE, replace=False)
        haut = haut.iloc[np.sort(take)].reset_index(drop=True)
    print(f"HAUT échantillon : {len(haut)} obs (graine {SEED})")

    mf = H.MODEL_DIR / "enrichi_seg_haut_ba493568.json"
    assert H.sha8(mf) == H.HASH_MODEL_HAUT, "empreinte modèle haut non canonique"
    m = xgb.XGBRegressor(); m.load_model(str(mf))
    booster = m.get_booster()
    X = H.prep_X(haut, feats)[feats]

    ri = [idx[f] for f in ROW_FEATS]
    acc = np.zeros((len(ROW_FEATS), len(feats) + 1))    # somme |interaction| (col biais incluse)
    n = 0
    for s in range(0, len(X), CHUNK):
        dm = xgb.DMatrix(X.iloc[s:s + CHUNK], enable_categorical=True)
        M = booster.predict(dm, pred_interactions=True)   # (c, F+1, F+1)
        acc += np.abs(M[:, ri, :]).sum(axis=0)
        n += M.shape[0]
        print(f"  ... {n}/{len(X)}  ({time.time()-t0:.0f}s)", flush=True)
    mean_abs = acc / n                                    # (len(ROW_FEATS), F+1)

    rows = []
    for k, rf in enumerate(ROW_FEATS):
        for cf in cal_feats:
            rows.append(dict(row_var=rf, cal_var=cf,
                             mean_abs_interaction=float(mean_abs[k, idx[cf]]), n_echantillon=n))
        rows.append(dict(row_var=rf, cal_var="_effet_principal_diagonal",
                         mean_abs_interaction=float(mean_abs[k, idx[rf]]), n_echantillon=n))
    out = pd.DataFrame(rows).sort_values(["row_var", "mean_abs_interaction"], ascending=[True, False])
    TAB.mkdir(parents=True, exist_ok=True)
    out.to_csv(TAB / "t_interactions_haut.csv", index=False)
    print(out.to_string(index=False))
    print(f"[OK] t_interactions_haut.csv | total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
