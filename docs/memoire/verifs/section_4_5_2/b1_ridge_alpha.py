#!/usr/bin/env python3
"""
B1 — Sensibilité de la référence linéaire (Ridge) au réglage de alpha.

CADRAGE. Analyse de SENSIBILITÉ : elle ne remplace aucune valeur préenregistrée du
manuscrit. Ne modifie ni outputs/confirmation/, ni les tableaux du manuscrit, ni aucun
ADR. N'écrit que sous docs/memoire/verifs/section_4_5/.

PROTOCOLE
  1. Balayage de alpha sur 6 valeurs (0,01 / 0,1 / 1 / 10 / 100 / 1000), EXCLUSIVEMENT en
     validation interne sur H24, par validation temporelle progressive à 3 plis
     (fenêtre d'entraînement croissante, plis de validation = 3 tiers chronologiques de
     H24) — régime de séparation de la §4.5.1 : H25 n'est jamais touché à ce stade.
  2. Sélection du meilleur alpha au R² global moyen sur les 3 plis.
  3. UNE SEULE lecture sur H25 avec la configuration retenue : mêmes 158 variables, même
     imputation médiane du train, même partition (Split C), même graine (42).

Tout le reste est iso-c03 : ColumnTransformer identique (médiane + StandardScaler sur les
152 numériques ; most_frequent + one-hot sur les 6 catégorielles), modèle GLOBAL, métriques
au format préenregistré (bootstrap 1000, seed 42).

Sorties :
  - b1_ridge_balayage.csv     R² par (alpha, pli) et moyenne
  - b1_ridge_h25.csv          tableau au format du tableau 11, alpha retenu vs alpha=1,0
  - b1_ridge_alpha.json       synthèse machine

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/b1_ridge_alpha.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402

OUT = Path(__file__).resolve().parent
ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]   # 7 valeurs : la 7e borne le
# balayage par le haut, un optimum retenu au bord de la grille n'étant pas un optimum
ALPHA_MANUSCRIT = 1.0        # valeur par défaut rapportée au manuscrit (c03)
N_PLIS = 3


def build_design(d, feats, cat_cols, num_cols):
    """Identique à c03_baseline_lineaire.build_design."""
    X = d[feats].copy()
    for c in cat_cols:
        X[c] = X[c].astype("string").astype("object")
    for c in num_cols:
        X[c] = X[c].astype("float64")
    return X


def make_pipeline(cat_cols, num_cols, alpha):
    """Identique à c03_baseline_lineaire.make_pipeline."""
    num = Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())])
    cat = Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                    ("oh", OneHotEncoder(handle_unknown="ignore"))])
    pre = ColumnTransformer([("num", num, num_cols), ("cat", cat, cat_cols)])
    return Pipeline([("pre", pre), ("ridge", Ridge(alpha=alpha, random_state=H.SEED))])


def plis_progressifs(train):
    """3 plis à fenêtre d'entraînement croissante, validation confinée à H24.

    H24 est découpé en 3 blocs chronologiques contigus d'effectifs aussi proches que
    possible (frontières posées sur les dates, jamais au milieu d'une journée).
      pli 1 : fit H22+H23                       -> valid bloc 1 de H24
      pli 2 : fit H22+H23 + bloc 1              -> valid bloc 2 de H24
      pli 3 : fit H22+H23 + blocs 1-2           -> valid bloc 3 de H24
    """
    est_h24 = (train["horaire_annee_horaire"] == "H24").values
    base = ~est_h24                                    # H22 (hors Gilamont) + H23
    dates = np.sort(train.loc[est_h24, "base_date"].unique())
    # frontières par quantiles d'observations, arrondies à la journée
    d24 = train.loc[est_h24, "base_date"].values
    q1, q2 = np.quantile(d24.astype("datetime64[ns]").astype("int64"), [1 / 3, 2 / 3])
    b1 = np.datetime64(int(q1), "ns")
    b2 = np.datetime64(int(q2), "ns")
    bd = train["base_date"].values.astype("datetime64[ns]")
    blocs = [est_h24 & (bd <= b1),
             est_h24 & (bd > b1) & (bd <= b2),
             est_h24 & (bd > b2)]
    plis = []
    cumul = base.copy()
    for k, bl in enumerate(blocs, start=1):
        plis.append({"pli": k, "fit": cumul.copy(), "valid": bl.copy(),
                     "n_fit": int(cumul.sum()), "n_valid": int(bl.sum()),
                     "valid_debut": str(pd.Timestamp(train.loc[bl, "base_date"].min()).date()),
                     "valid_fin": str(pd.Timestamp(train.loc[bl, "base_date"].max()).date())})
        cumul = cumul | bl
    assert sum(p["n_valid"] for p in plis) == int(est_h24.sum())
    _ = dates
    return plis


def main() -> int:
    print("=== B1 — sensibilité de la Ridge au réglage de alpha (analyse de sensibilité) ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    cat_cols = [c for c in feats if str(df[c].dtype) in ("object", "string", "category")]
    num_cols = [c for c in feats if c not in cat_cols]
    train, test = H.split_c(df)
    print(f"  {len(num_cols)} numériques + {len(cat_cols)} catégorielles | "
          f"train={len(train)} test H25={len(test)}")

    Xtr = build_design(train, feats, cat_cols, num_cols)
    ytr = H.y_of(train)
    Xte = build_design(test, feats, cat_cols, num_cols)

    # ── 1. Balayage en validation interne H24, 3 plis progressifs ───────────────
    plis = plis_progressifs(train)
    for p in plis:
        print(f"  pli {p['pli']} : fit n={p['n_fit']:>7} | valid n={p['n_valid']:>7} "
              f"({p['valid_debut']} → {p['valid_fin']})")

    lignes = []
    for a in ALPHAS:
        for p in plis:
            t0 = time.time()
            pipe = make_pipeline(cat_cols, num_cols, a).fit(Xtr[p["fit"]], ytr[p["fit"]])
            pv = pipe.predict(Xtr[p["valid"]])
            yv = ytr[p["valid"]]
            seg = train.loc[p["valid"], "spatial_segment"].values
            lignes.append({
                "alpha": a, "pli": p["pli"], "n_fit": p["n_fit"], "n_valid": p["n_valid"],
                "valid_debut": p["valid_debut"], "valid_fin": p["valid_fin"],
                "r2_global": float(r2_score(yv, pv)),
                "r2_bas": float(r2_score(yv[seg == "bas"], pv[seg == "bas"])),
                "r2_haut": float(r2_score(yv[seg == "haut"], pv[seg == "haut"])),
                "duree_s": round(time.time() - t0, 1),
            })
            print(f"    alpha={a:<8} pli {p['pli']} R2_global={lignes[-1]['r2_global']:.6f} "
                  f"({lignes[-1]['duree_s']}s)")
    bal = pd.DataFrame(lignes)
    moy = (bal.groupby("alpha")[["r2_global", "r2_bas", "r2_haut"]]
              .mean().reset_index().rename(columns=lambda c: c + "_moy" if c != "alpha" else c))
    bal.to_csv(OUT / "b1_ridge_balayage.csv", index=False)
    print("\n  R² global moyen sur les 3 plis :")
    for _, r in moy.iterrows():
        print(f"    alpha={r['alpha']:<8} R2_moy={r['r2_global_moy']:.6f}")
    best = float(moy.loc[moy["r2_global_moy"].idxmax(), "alpha"])
    print(f"  ==> alpha retenu (R² global moyen max) : {best}")

    # ── 2. Lecture UNIQUE sur H25 ──────────────────────────────────────────────
    h25 = {}
    for a, lbl in ((best, "alpha_retenu"), (ALPHA_MANUSCRIT, "alpha_defaut_manuscrit")):
        if lbl == "alpha_defaut_manuscrit" and a == best:
            h25[lbl] = h25["alpha_retenu"]
            continue
        t0 = time.time()
        pipe = make_pipeline(cat_cols, num_cols, a).fit(Xtr, ytr)
        pred = pipe.predict(Xte).astype("float64")
        m = H.metrics_by_segment(test, pred)
        m["_alpha"] = a
        m["_duree_entrainement_s"] = round(time.time() - t0, 1)
        h25[lbl] = m
        print(f"  H25 [alpha={a}] R2 bas={m['bas']['r2']:.4f} haut={m['haut']['r2']:.4f} "
              f"global={m['global']['r2']:.4f}")

    # ── 3. Tableau au format du tableau 11 + écarts ────────────────────────────
    rows = []
    for lbl, m in h25.items():
        for s in ("bas", "haut", "global"):
            rows.append({"bras": f"Ridge (158 var.) — {lbl} = {m['_alpha']}",
                         "alpha": m["_alpha"], "segment": s,
                         "r2": m[s]["r2"], "r2_ci_lo": m[s]["r2_ci_lo"],
                         "r2_ci_hi": m[s]["r2_ci_hi"], "mae": m[s]["mae"],
                         "mae_gt63": m[s]["mae_gt63"], "biais_gt63": m[s]["bias_gt63"],
                         "pr_auc": m[s]["pr_auc"], "n_gt63": m[s]["n_gt63"]})
    tab = pd.DataFrame(rows)
    ref = h25["alpha_defaut_manuscrit"]
    ecarts = [{"segment": s,
               "delta_r2": h25["alpha_retenu"][s]["r2"] - ref[s]["r2"],
               "delta_mae": h25["alpha_retenu"][s]["mae"] - ref[s]["mae"],
               "delta_mae_gt63": h25["alpha_retenu"][s]["mae_gt63"] - ref[s]["mae_gt63"],
               "delta_biais_gt63": h25["alpha_retenu"][s]["bias_gt63"] - ref[s]["bias_gt63"],
               "delta_pr_auc": h25["alpha_retenu"][s]["pr_auc"] - ref[s]["pr_auc"]}
              for s in ("bas", "haut", "global")]
    tab.to_csv(OUT / "b1_ridge_h25.csv", index=False)

    payload = {
        "script": "b1_ridge_alpha.py",
        "cadrage": "ANALYSE DE SENSIBILITÉ — ne remplace aucune valeur préenregistrée ; "
                   "destinée à une note de bas de page ou une annexe.",
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)), extra={
            "modele": "Ridge (sklearn.linear_model), GLOBAL — iso c03_baseline_lineaire.py",
            "grille_alpha": ALPHAS, "n_plis": N_PLIS,
            "protocole_validation": "validation temporelle progressive à 3 plis, "
                                    "validation confinée à H24, H25 jamais touché au "
                                    "stade du réglage",
            "imputation": "numériques = médiane du train ; catégorielles = most_frequent "
                          "+ one-hot (handle_unknown=ignore)",
            "n_numeriques": len(num_cols), "n_categorielles": len(cat_cols),
        }),
        "plis": [{k: v for k, v in p.items() if k not in ("fit", "valid")} for p in plis],
        "balayage_h24": lignes,
        "balayage_h24_moyennes": moy.to_dict(orient="records"),
        "alpha_retenu": best,
        "alpha_defaut_manuscrit": ALPHA_MANUSCRIT,
        "metriques_h25": {k: {s: v[s] for s in ("bas", "haut", "global")}
                          | {"alpha": v["_alpha"]} for k, v in h25.items()},
        "ecarts_h25_retenu_moins_defaut": ecarts,
        "reference_manuscrit_c03": json.loads(
            (ROOT / "outputs/confirmation/c03_baseline_lineaire.json").read_text()
        )["metriques_h25"],
    }
    (OUT / "b1_ridge_alpha.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
