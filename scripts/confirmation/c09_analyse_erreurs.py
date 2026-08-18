#!/usr/bin/env python3
"""
c09_analyse_erreurs.py — analyse d'erreurs sur les predictions des modeles GELES.

Consolide trois fragments existants, depuis les predictions figees (grain troncon, H25).
Aucun reentrainement (LECTURE SEULE des modeles).

(a) Residus par segment et par tranche de charge (autour de 63) :
    <= 63 / 64-93 / 94-165 / > 165. Les bornes suivent le seuil de surcharge applique en
    STRICTEMENT SUPERIEUR (y > SEUIL) : une charge de 63 places assises n'est pas une
    surcharge, elle appartient donc a la tranche basse et non a la tranche 64-93.
(b) Metriques par mois horaire H25 (cal_mois_horaire 1..13 ; les deux decembres = 12 et 13).
(c) Stratification connus vs renumerotes (mecanisme sids_train, etape_03bis).
    DEUX cles rapportees telles quelles (chiffres seuls) :
      - horaire_service_id_complet (mecanisme litteral nomme) : composite numero_train+heure.
      - horaire_numero_train (course seule) : stable a l'heure de depart pres.
    Fait consigne : sur ba493568, l'inter H24<->H25 de service_id_complet est VIDE (les
    horaires de depart ont bouge), la strate 'connu' est donc vide pour cette cle ; la cle
    numero_train donne une strate connu non vide.

Sortie : outputs/confirmation/c09_analyse_erreurs.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

# Bornes alignees sur H.SEUIL applique en strictement superieur (cf. strat_metrics :
# gt = y > H.SEUIL). La borne basse de la tranche surchargee est donc SEUIL + 1 = 64.
TRANCHES = [("<= 63", -np.inf, H.SEUIL + 1), ("64-93", H.SEUIL + 1, 94),
            ("94-165", 94, 166), ("> 165", 166, np.inf)]


def residus_tranche(y, p):
    r = p - y
    return {"n": int(len(y)),
            "charge_moyenne": float(y.mean()) if len(y) else None,
            "pred_moyenne": float(p.mean()) if len(y) else None,
            "biais_moyen": float(r.mean()) if len(y) else None,
            "mae": float(np.abs(r).mean()) if len(y) else None}


def strat_metrics(y, p):
    gt = y > H.SEUIL
    n_pos = int(gt.sum())
    return {"n_obs": int(len(y)), "n_gt63": n_pos,
            "prevalence": float(gt.mean()) if len(y) else None,
            "pr_auc": float(average_precision_score(gt.astype(int), p)) if n_pos > 0 else None,
            "rappel_pred_gt63": float(((p > H.SEUIL) & gt).sum() / n_pos) if n_pos > 0 else None}


def par_segment(fn, y, p, seg):
    out = {"global": fn(y, p)}
    for s in ("bas", "haut"):
        m = seg == s
        out[s] = fn(y[m], p[m])
    return out


def main() -> int:
    print("=== c09 — analyse d'erreurs (predictions figees, H25) ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    h25 = df[df["horaire_annee_horaire"] == "H25"].copy()
    if len(h25) != H.N_TEST_H25:
        raise RuntimeError(f"STOP : n_test H25={len(h25)} != {H.N_TEST_H25}")

    pred = H.frozen_predict(h25, feats)                    # empreintes verifiees dans le helper
    y = H.y_of(h25)
    seg = h25["spatial_segment"].values

    # (a) residus par tranche de charge
    a = {}
    n_couvert = 0
    for name, lo, hi in TRANCHES:
        m = (y >= lo) & (y < hi)
        a[name] = par_segment(residus_tranche, y[m], pred[m], seg[m])
        n_couvert += int(m.sum())
    # Partition close : tranches disjointes et exhaustives sur H25 (STOP si trou ou recouvrement).
    if n_couvert != len(h25):
        raise RuntimeError(f"STOP : partition des tranches non close ({n_couvert} != {len(h25)}).")
    for s in ("global", "bas", "haut"):
        n_s = sum(a[t][s]["n"] for t in a)
        n_att = len(h25) if s == "global" else int((seg == s).sum())
        if n_s != n_att:
            raise RuntimeError(f"STOP : effectifs {s} = {n_s} != {n_att}.")
    print(f"  (a) residus par tranche : {[t[0] for t in TRANCHES]} "
          f"(partition close, {n_couvert} troncons)")

    # (b) metriques par mois horaire (les deux decembres separes : 12 et 13)
    mh = h25["cal_mois_horaire"].astype("Int64")
    mois_cal = h25["cal_mois"].astype("Int64")
    b = {}
    for mval in sorted(mh.dropna().unique().tolist()):
        m = (mh == mval).values
        modal = int(mois_cal[m].mode().iloc[0]) if m.any() else None
        b[str(int(mval))] = {
            "cal_mois_calendaire_modal": modal,
            "note": "2e décembre du même exercice horaire" if int(mval) == 13 else None,
            "global": H.seg_metrics(y[m], pred[m], with_ci=True),
            "bas": H.seg_metrics(y[m & (seg == "bas")], pred[m & (seg == "bas")], with_ci=False),
            "haut": H.seg_metrics(y[m & (seg == "haut")], pred[m & (seg == "haut")], with_ci=False),
        }
    print(f"  (b) metriques par mois horaire : {len(b)} mois (1..13)")

    # (c) stratification connus vs renumerotes — deux cles
    tr_mask = df["horaire_annee_horaire"].isin(["H22", "H23", "H24"])
    sids_sid = set(df.loc[tr_mask, "horaire_service_id_complet"].dropna().unique())
    sids_num = set(df.loc[tr_mask, "horaire_numero_train"].dropna().unique())
    c = {}
    for cle, col, seen in [("horaire_service_id_complet", "horaire_service_id_complet", sids_sid),
                           ("horaire_numero_train", "horaire_numero_train", sids_num)]:
        strat = h25[col].apply(lambda v: "connu" if v in seen else "renumero").values
        n_con = int((strat == "connu").sum()); n_ren = int((strat == "renumero").sum())
        bloc = {"n_service_id_train": len(seen),
                "n_connu": n_con, "n_renumero": n_ren,
                "part_renumero": (n_ren / len(h25))}
        for lbl in ("connu", "renumero"):
            sm = strat == lbl
            bloc[lbl] = par_segment(strat_metrics, y[sm], pred[sm], seg[sm])
        c[cle] = bloc
        print(f"  (c) cle={cle} : connu={n_con} renumero={n_ren} (troncons)")

    payload = {
        "script": "c09_analyse_erreurs.py",
        "role": "analyse d'erreurs (residus/tranche, mois horaire, connus vs renumerotes) — modeles geles",
        "meta": H.meta_block(models_loaded=True, n_test=int(len(h25)),
                             extra={"grain": "troncon", "seuil_surcharge": H.SEUIL,
                                    "fait_service_id": "inter H24<->H25 de horaire_service_id_complet "
                                    "VIDE sur ba493568 (horaires de depart decales) -> strate 'connu' "
                                    "vide pour cette cle ; cle numero_train non degeneree"}),
        "a_residus_par_tranche_charge": a,
        "b_metriques_par_mois_horaire": b,
        "c_connus_vs_renumerotes": c,
    }
    out = H.write_json("c09_analyse_erreurs.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
