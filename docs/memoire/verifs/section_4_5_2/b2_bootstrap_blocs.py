#!/usr/bin/env python3
"""
B2 — Sensibilité du bootstrap à la dépendance intra-course et intra-date.

CADRAGE. Analyse de SENSIBILITÉ : elle ne remplace pas l'intervalle préenregistré du
manuscrit (R² global [0,598 ; 0,605], bootstrap i.i.d. 1000 itérations au grain de
l'observation). N'écrit que sous docs/memoire/verifs/section_4_5/. Aucun réentraînement du
modèle retenu : les prédictions viennent des modèles GELÉS e4ddfccd / df6a11c5.

Les deux baselines de comparaison (M0 et naïve) sont, elles, reconstruites — ce sont des
baselines, pas le modèle retenu, et leurs prédictions ne sont archivées nulle part. M0 est
réentraîné à l'identique de scripts/confirmation/c02_baseline_m0.py ; la baseline naïve
réutilise la fonction de scripts/confirmation/c10_comparatif_algos.py.

VARIANTES DE BLOC (1000 itérations, graine 42, comme le préenregistré) :
  iid          — grain de l'observation (reproduction du préenregistré)
  date         — bloc = journée d'exploitation (base_date)
  date_course  — bloc = (base_date, numéro de train, sens) = la course
  course       — bloc = (numéro de train, sens), toutes dates : comparaison croisée

Sorties :
  - b2_intervalles.csv          IC par (modèle, segment, variante) + facteur d'élargissement
  - b2_ecarts_apparies.csv      IC de ΔR² (modèle retenu − M0) et (− naïve), par variante
  - b2_bootstrap_blocs.json     synthèse machine

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/b2_bootstrap_blocs.py
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
from sklearn.metrics import r2_score

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402
from c10_comparatif_algos import baseline_naive  # noqa: E402

OUT = Path(__file__).resolve().parent
N_BOOT = H.N_BOOT      # 1000, protocole phase 4
SEED = H.SEED          # 42
VARIANTES = ["iid", "date", "date_course", "course"]


def cles_blocs(test: pd.DataFrame) -> dict:
    """Code entier de bloc par variante, aligné sur l'ordre de `test`."""
    d = test["base_date"].values.astype("datetime64[D]").astype("int64")
    t = test["horaire_numero_train"].astype("float64").fillna(-1).astype("int64").values
    s = pd.factorize(test["base_sens"].astype(str))[0].astype("int64")
    return {
        "date": d,
        "date_course": (d.astype("int64") * 1_000_000 + t * 10 + s),
        "course": (t * 10 + s),
    }


def ic_bootstrap(y, p, blocs=None, n_boot=N_BOOT, seed=SEED):
    """IC95 du R². blocs=None -> rééchantillonnage i.i.d. des observations (préenregistré).
    Sinon rééchantillonnage AVEC REMISE des blocs, indices concaténés."""
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = np.empty(n_boot)
    if blocs is None:
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            vals[i] = r2_score(y[idx], p[idx])
        return vals, n
    ordre = np.argsort(blocs, kind="stable")
    b_tri = blocs[ordre]
    debuts = np.flatnonzero(np.r_[True, b_tri[1:] != b_tri[:-1]])
    fins = np.r_[debuts[1:], len(b_tri)]
    membres = [ordre[a:b] for a, b in zip(debuts, fins)]
    nb = len(membres)
    tailles = np.empty(n_boot, dtype="int64")
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        idx = np.concatenate([membres[j] for j in pick])
        tailles[i] = len(idx)
        vals[i] = r2_score(y[idx], p[idx])
    return vals, (nb, float(tailles.mean()))


def ic_apparie(y, pa, pb, blocs=None, n_boot=N_BOOT, seed=SEED):
    """IC95 de ΔR² = R²(pa) − R²(pb), rééchantillonnage APPARIÉ (mêmes indices)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = np.empty(n_boot)
    if blocs is None:
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            vals[i] = r2_score(y[idx], pa[idx]) - r2_score(y[idx], pb[idx])
        return vals
    ordre = np.argsort(blocs, kind="stable")
    b_tri = blocs[ordre]
    debuts = np.flatnonzero(np.r_[True, b_tri[1:] != b_tri[:-1]])
    fins = np.r_[debuts[1:], len(b_tri)]
    membres = [ordre[a:b] for a, b in zip(debuts, fins)]
    nb = len(membres)
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        idx = np.concatenate([membres[j] for j in pick])
        vals[i] = r2_score(y[idx], pa[idx]) - r2_score(y[idx], pb[idx])
    return vals


def pct(v):
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def main() -> int:
    print("=== B2 — bootstrap par blocs (analyse de sensibilité) ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    train, test = H.split_c(df)
    y = H.y_of(test)
    seg = test["spatial_segment"].values
    masques = {"bas": seg == "bas", "haut": seg == "haut",
               "global": np.ones(len(test), dtype=bool)}

    # ── Prédictions ─────────────────────────────────────────────────────────────
    print("  modèle retenu : prédictions des modèles GELÉS (aucun réentraînement) …")
    pred = {"modele_retenu": H.frozen_predict(test, feats)}
    print("  baseline M0 (cal_ + histo_, global) : réentraînement iso-c02 …")
    feats_m0 = [f for f in feats if f.startswith("cal_") or f.startswith("histo_")]
    assert len(feats_m0) == 31, f"M0 attendu 31 features, obtenu {len(feats_m0)}"
    t0 = time.time()
    pred["m0"], _ = H.train_global(train, test, feats_m0)
    print(f"    ({time.time() - t0:.0f}s)")
    print("  baseline naïve (moyenne historique, iso-c10) …")
    pred["naive"], extras_naive = baseline_naive(train, test)

    # Contrôle : le bras « modèle retenu » doit reproduire les R² publiés (c01)
    c01 = json.loads((ROOT / "outputs/confirmation/c01_metriques_finales.json").read_text())
    for s in ("bas", "haut", "global"):
        r2 = r2_score(y[masques[s]], pred["modele_retenu"][masques[s]])
        ref = c01["metriques_h25"][s]["r2"]
        if abs(r2 - ref) > 1e-9:
            raise RuntimeError(f"STOP : R² {s} recalculé {r2} != c01 {ref}")
    print("  contrôle : R² du modèle gelé identiques à c01 (bas/haut/global) — OK")

    blocs_tous = cles_blocs(test)

    # ── 1. IC du R² par modèle × segment × variante ────────────────────────────
    lignes, brut = [], {}
    for nom_modele, p in pred.items():
        for s, m in masques.items():
            largeur_iid = None
            for var in VARIANTES:
                b = None if var == "iid" else blocs_tous[var][m]
                t0 = time.time()
                vals, info = ic_bootstrap(y[m], p[m], b)
                lo, hi = pct(vals)
                if var == "iid":
                    largeur_iid = hi - lo
                lignes.append({
                    "modele": nom_modele, "segment": s, "variante_bloc": var,
                    "r2_point": float(r2_score(y[m], p[m])),
                    "ic_lo": lo, "ic_hi": hi, "largeur": hi - lo,
                    "facteur_elargissement": (hi - lo) / largeur_iid,
                    "n_obs": int(m.sum()),
                    "n_blocs": (None if var == "iid" else int(info[0])),
                    "taille_moy_reechantillon": (int(m.sum()) if var == "iid"
                                                 else round(info[1], 1)),
                    "duree_s": round(time.time() - t0, 1),
                })
                brut.setdefault(nom_modele, {}).setdefault(s, {})[var] = vals.tolist()
                print(f"  [{nom_modele:14} {s:6} {var:11}] R2={lignes[-1]['r2_point']:.4f} "
                      f"IC=[{lo:.4f};{hi:.4f}] largeur={hi - lo:.4f} "
                      f"×{lignes[-1]['facteur_elargissement']:.2f} ({lignes[-1]['duree_s']}s)")
    tab = pd.DataFrame(lignes)
    tab.to_csv(OUT / "b2_intervalles.csv", index=False)

    # ── 2. IC apparié des écarts (modèle retenu − baseline) ────────────────────
    ecarts = []
    for base in ("m0", "naive"):
        for s, m in masques.items():
            largeur_iid = None
            for var in VARIANTES:
                b = None if var == "iid" else blocs_tous[var][m]
                vals = ic_apparie(y[m], pred["modele_retenu"][m], pred[base][m], b)
                lo, hi = pct(vals)
                if var == "iid":
                    largeur_iid = hi - lo
                ecarts.append({
                    "comparaison": f"modele_retenu_moins_{base}", "segment": s,
                    "variante_bloc": var,
                    "delta_r2_point": float(r2_score(y[m], pred["modele_retenu"][m])
                                            - r2_score(y[m], pred[base][m])),
                    "ic_lo": lo, "ic_hi": hi, "largeur": hi - lo,
                    "facteur_elargissement": (hi - lo) / largeur_iid,
                    "ic_exclut_zero": bool(lo > 0 or hi < 0),
                })
                print(f"  [Δ vs {base:6} {s:6} {var:11}] Δ={ecarts[-1]['delta_r2_point']:.4f} "
                      f"IC=[{lo:.4f};{hi:.4f}] exclut 0 : {ecarts[-1]['ic_exclut_zero']}")
    eca = pd.DataFrame(ecarts)
    eca.to_csv(OUT / "b2_ecarts_apparies.csv", index=False)

    payload = {
        "script": "b2_bootstrap_blocs.py",
        "cadrage": "ANALYSE DE SENSIBILITÉ — ne remplace pas l'IC préenregistré du "
                   "manuscrit ; destinée à une note de bas de page ou une annexe.",
        "meta": H.meta_block(models_loaded=True, n_train=int(len(train)),
                             n_test=int(len(test)), extra={
                                 "n_boot": N_BOOT, "seed": SEED, "variantes": VARIANTES,
                                 "definition_course": "(base_date, horaire_numero_train, "
                                                      "base_sens)",
                                 "couverture_baseline_naive": extras_naive.get("couverture_pct"),
                             }),
        "ic_preenregistre_c01": {s: {"r2": c01["metriques_h25"][s]["r2"],
                                     "ic_lo": c01["metriques_h25"][s]["r2_ci_lo"],
                                     "ic_hi": c01["metriques_h25"][s]["r2_ci_hi"]}
                                 for s in ("bas", "haut", "global")},
        "intervalles": lignes,
        "ecarts_apparies": ecarts,
    }
    (OUT / "b2_bootstrap_blocs.json").write_text(json.dumps(payload, indent=2,
                                                           ensure_ascii=False))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
