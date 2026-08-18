#!/usr/bin/env python3
"""
s3_analyse.py — VÉRIF 4, section 4.3 : métriques, dispersion, propagation, redistribution.

Consomme _experimentation/s2_variantes.json et produit :
  1. le tableau de métriques par variante, à la graine de référence (IC bootstrap du R2) ;
  2. la dispersion inter-graines, et surtout l'écart APPARIÉ graine à graine C − variante,
     qui neutralise le bruit d'entraînement commun aux deux bras et constitue le test
     décisif : un écart dont le signe n'est pas constant sur les dix graines n'est pas
     un effet ;
  3. la propagation de A1 et A2 à la couche décisionnelle, à seuils du menu INCHANGÉS,
     dans les deux régimes de plancher (actif / désactivé) ;
  4. la redistribution des parts de contribution par origine sur la variante A1.

Discipline : lecture seule sur les artefacts canoniques. Le modèle A1 est réentraîné à
la graine de référence pour le calcul SHAP (déterministe, threads épinglés) et n'est
jamais persisté sous models/.

Sorties : _experimentation/s3_analyse.json + CSV sous docs/memoire/tableaux/section_5_4_1/.
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

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI.parent))
ROOT = ICI.parents[3]
sys.path.insert(0, str(ROOT / "scripts/confirmation"))
import _harness as H              # noqa: E402
import _socle_chap5 as S          # noqa: E402
import _table_autorite_annexe22 as A  # noqa: E402

EXP = ICI / "_experimentation"
OUT_CSV = ROOT / "docs/memoire/tableaux/section_5_4_1"
METRIQUES = ["r2", "mae", "mae_gt63", "bias_gt63", "pr_auc"]
SEGMENTS = ["global", "bas", "haut"]
VARIANTES = ["C", "A1", "A2", "A3", "A4"]
ABLATIONS = ["A1", "A2", "A3", "A4"]


def main() -> int:
    s2 = json.loads((EXP / "s2_variantes.json").read_text())
    recon = json.loads((ICI / "_reconciliation.json").read_text())
    graines = [str(g) for g in s2["meta"]["graines"]]
    gref = str(s2["meta"]["graine_reference"])
    infos = s2["meta"]["variantes"]
    res = s2["resultats"]

    # ── 4.3.1 Métriques à la graine de référence ───────────────────────────────
    lignes = []
    for v in VARIANTES:
        for seg in SEGMENTS:
            m = res[v][gref][seg]
            lignes.append({"variante": v, "n_variables": infos[v]["n_variables"],
                           "segment": seg, "graine": int(gref), **{k: m[k] for k in METRIQUES},
                           "r2_ci_lo": m["r2_ci_lo"], "r2_ci_hi": m["r2_ci_hi"],
                           "n_obs": m["n_obs"], "n_gt63": m["n_gt63"]})
    ref = pd.DataFrame(lignes)
    ref.to_csv(OUT_CSV / "t54_metriques_graine_reference.csv", index=False, float_format="%.17g")

    # ── 4.3.2 Dispersion inter-graines et écart APPARIÉ ────────────────────────
    disp_rows, app_rows = [], []
    for seg in SEGMENTS:
        for met in METRIQUES:
            serie = {v: np.array([res[v][g][seg][met] for g in graines], dtype=float)
                     for v in VARIANTES}
            for v in VARIANTES:
                x = serie[v]
                disp_rows.append({"variante": v, "segment": seg, "metrique": met,
                                  "moyenne": x.mean(), "ecart_type": x.std(ddof=1),
                                  "min": x.min(), "max": x.max(),
                                  "etendue": x.max() - x.min(), "n_graines": len(x)})
            for v in ABLATIONS:
                d = serie["C"] - serie[v]          # écart apparié, graine à graine
                # une dégradation est un R2/PR-AUC plus bas, ou une erreur plus haute
                sens = 1 if met in ("r2", "pr_auc") else -1
                degrade = (d * sens) > 0
                app_rows.append({
                    "variante": v, "segment": seg, "metrique": met,
                    "delta_moyen_C_moins_variante": d.mean(), "delta_ecart_type": d.std(ddof=1),
                    "delta_min": d.min(), "delta_max": d.max(),
                    "dispersion_intra_C": serie["C"].std(ddof=1),
                    "dispersion_intra_variante": serie[v].std(ddof=1),
                    "n_graines_degradees": int(degrade.sum()),
                    "signe_constant": bool(degrade.all() or (~degrade).all()),
                    "ratio_delta_sur_dispersion":
                        abs(d.mean()) / serie["C"].std(ddof=1) if serie["C"].std(ddof=1) > 0 else np.inf,
                })
    disp = pd.DataFrame(disp_rows)
    app = pd.DataFrame(app_rows)
    disp.to_csv(OUT_CSV / "t54_dispersion_inter_graines.csv", index=False, float_format="%.17g")
    app.to_csv(OUT_CSV / "t54_ecarts_apparies.csv", index=False, float_format="%.17g")

    # ── 4.3.3 Propagation à la couche décisionnelle, seuils INCHANGÉS ──────────
    seuils = S.seuils()
    tau_c = seuils["c"]
    canon = S.h25_de(S.build_enrichi())           # périmètre iso 29 222, label, segment, is_UM
    y = canon["label"].values.astype(bool)
    P = int(y.sum())

    dec_rows = []
    for v in ("C", "A1", "A2"):
        f = EXP / f"pred_h25_{v}_g{gref}.parquet"
        tr = pd.read_parquet(f)
        cours = (tr.groupby(["date", "numero_train"], sort=True)
                 .agg(score=("pred", "max"), charge_max=("target", "max"),
                      resa2c=("resa2c", "max")).reset_index())
        j = canon[["date", "numero_train", "label", "segment"]].merge(
            cours, on=["date", "numero_train"], how="left")
        if len(j) != len(canon) or j["score"].isna().any():
            raise RuntimeError(f"STOP : jonction incomplète pour la variante {v}.")
        # contrôle : le label recalculé doit coïncider avec le label canonique
        if not np.array_equal((j["charge_max"].values > S.SEUIL), j["label"].values.astype(bool)):
            raise RuntimeError(f"STOP : label recalculé != label canonique pour {v}.")

        sc = j["score"].values >= tau_c
        pl = j["resa2c"].values > S.SEUIL
        for regime, mask in (("plancher actif (c ∪ plancher)", sc | pl),
                             ("plancher désactivé (c seul)", sc)):
            for seg in SEGMENTS:
                sel = np.ones(len(j), bool) if seg == "global" else (j["segment"].values == seg)
                dec_rows.append({"variante": v, "regime": regime, "segment": seg,
                                 **S.confusion(mask[sel], y[sel])})
    dec = pd.DataFrame(dec_rows)
    dec.to_csv(OUT_CSV / "t54_couche_decisionnelle.csv", index=False, float_format="%.17g")

    # ── 4.3.4 Redistribution des contributions sur A1 ──────────────────────────
    import xgboost as xgb
    H.assert_dataset()
    feats158 = H.load_features_158()
    retire_a1 = set(recon["perimetres"]["A1"])
    feats_a1 = [c for c in feats158 if c not in retire_a1]
    df = H.load_dataset()
    train, test = H.split_c(df)
    contrib = {}
    for seg in ("bas", "haut"):
        mtr = train[train["spatial_segment"] == seg]
        mte = test[test["spatial_segment"] == seg]
        m = xgb.XGBRegressor(**dict(H.XGB_PARAMS, random_state=int(gref)))
        m.fit(H.prep_X(mtr, feats_a1), H.y_of(mtr))
        dm = xgb.DMatrix(H.prep_X(mte, feats_a1), enable_categorical=True)
        sh = m.get_booster().predict(dm, pred_contribs=True)[:, :-1]   # hors terme de biais
        masse = np.abs(sh).mean(axis=0)
        contrib[seg] = dict(zip(feats_a1, (masse / masse.sum() * 100).astype(float)))

    par_cand = {c: cols for c, _, _, cols in A.TABLE_A19_1}
    stat = {c: st for c, st, _, _ in A.TABLE_A19_1}
    masse_c = recon["masse_pct"]          # parts du modèle gelé (c08)
    redis = []
    for st_lib in (A.CONFIRMEE, A.LITTERATURE, A.EMERGENTE):
        cands = [c for c in par_cand if stat[c] == st_lib]
        cols = sorted({x for cd in cands for x in par_cand[cd]})
        for seg in ("bas", "haut"):
            avant = sum(masse_c[seg][c] for c in cols if c in masse_c[seg])
            apres = sum(contrib[seg].get(c, 0.0) for c in cols)
            redis.append({"statut": st_lib, "segment": seg, "part_C_pct": round(avant, 4),
                          "part_A1_pct": round(apres, 4), "delta_pct": round(apres - avant, 4)})
    nr = [c for c in feats158 if c not in {x for cols in par_cand.values() for x in cols}]
    for seg in ("bas", "haut"):
        avant = sum(masse_c[seg][c] for c in nr)
        apres = sum(contrib[seg].get(c, 0.0) for c in nr)
        redis.append({"statut": "non rattachées", "segment": seg, "part_C_pct": round(avant, 4),
                      "part_A1_pct": round(apres, 4), "delta_pct": round(apres - avant, 4)})
    redis = pd.DataFrame(redis)
    redis.to_csv(OUT_CSV / "t54_redistribution_contributions.csv", index=False, float_format="%.17g")

    (EXP / "s3_analyse.json").write_text(json.dumps({
        "metriques_reference": ref.to_dict("records"),
        "dispersion": disp.to_dict("records"),
        "ecarts_apparies": app.to_dict("records"),
        "couche_decisionnelle": dec.to_dict("records"),
        "redistribution": redis.to_dict("records"),
        "tau_c": tau_c, "n_courses": len(canon), "n_surcharges": P,
    }, indent=2, ensure_ascii=False))

    # ── Restitution ────────────────────────────────────────────────────────────
    pd.set_option("display.width", 200)
    print("=== 4.3.1 métriques, graine de référence, global ===")
    print(ref[ref.segment == "global"][["variante", "n_variables", "r2", "r2_ci_lo", "r2_ci_hi",
                                        "mae", "mae_gt63", "bias_gt63", "pr_auc"]].to_string(index=False))
    print("\n=== 4.3.2 écarts appariés C − variante (global) ===")
    print(app[(app.segment == "global")][
        ["variante", "metrique", "delta_moyen_C_moins_variante", "delta_ecart_type",
         "dispersion_intra_C", "n_graines_degradees", "signe_constant",
         "ratio_delta_sur_dispersion"]].to_string(index=False))
    print("\n=== 4.3.3 couche décisionnelle (global) ===")
    print(dec[dec.segment == "global"][
        ["variante", "regime", "volume", "VP", "FP", "precision", "rappel", "F1"]].to_string(index=False))
    print("\n=== 4.3.4 redistribution des contributions ===")
    print(redis.to_string(index=False))
    print("\n[OK] s3_analyse.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
