#!/usr/bin/env python3
"""
PROTOCOLE PREENREGISTRE (ecrit AVANT execution) - Configuration de deploiement : regle c + plancher reservations.

Provenance : exigences elicitees (responsable de production : ratio de tolerance idealement ~66 % de
precision, limite ~50 % ; notes juillet 2026, hypotheses A16-A18 du guide v2.11) + contrainte de conception
(toute demande annoncee depassant le seuil de places doit etre garantie : une reservation est un engagement
commercial). Ces exigences designent une INSTANCIATION de deploiement de l'artefact (famille de points
d'exploitation + plancher), pas une re-conception ni une re-calibration.

Definition : recommandation = (score >= tau_c au grain course via MAX troncon) OU (resa2c > 63 sur la course).
  tau_c = seuil F0.5 calibre sur H24 (64.12, generation ba493568). Memes conventions que l'artefact
  d'evaluation : seuil 63, grain course, iso-perimetre H25 (29 222 courses, 2 072 positives), gardes en tete.

Discipline : aucun chiffre attendu n'est devine. L'union ne s'extrapole PAS des lignes existantes (le
recouvrement plancher/score CHANGE quand le seuil descend de a' a c : c capture deja par le score une partie
de ce que le plancher apportait a a'). Sortie H24 d'abord (coherence de calibration : c reste-t-il dans la
bande de precision cible une fois le plancher uni ? CONSTAT, pas re-calibration), puis H25 (chiffres canoniques).

Ne remplace RIEN : la config d'evaluation a'+plancher (352/77.8/13.2) reste la comparaison iso-volume a la
pratique humaine. On AJOUTE une configuration ; les deux coexistent avec leurs fonctions distinctes.

Sortie : outputs/couche2/q_couche2_deploiement_ba493568.json (memes gardes et meta que q_couche2_eval).
Threads = 1 (reproductibilite, ADR-076).
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

SEUIL = 63
TARE_T = 54.2
TARIF_TBKM = 0.06444
OUT = ROOT / "outputs/couche2/q_couche2_deploiement_ba493568.json"


def recouvrement(reco_score, reco_pl):
    reco = reco_score | reco_pl
    return {"score_seul": int((reco_score & ~reco_pl).sum()),
            "plancher_seul": int((reco_pl & ~reco_score).sum()),
            "intersection": int((reco_score & reco_pl).sum()),
            "union": int(reco.sum())}


def main():
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)          # gardes 29 222 / 2 072
    calib = json.loads((ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json").read_text())
    taus = {rk: calib["regles_deployables"][rk]["seuil"] for rk in
            ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")}
    tau_c, tau_a = taus["c_haute_precision"], taus["a_iso_volume"]

    # distance par course (couts FP volet B)
    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    d = df[df["horaire_annee_horaire"].isin(["H24", "H25"])].copy()
    d["date"] = pd.to_datetime(d["base_date"]).dt.normalize()
    d["numero_train"] = d["horaire_numero_train"].astype("Int64").astype(str)
    have_dist = "spatial_distance_km" in d.columns
    cdist = (d.groupby(["date", "numero_train"])["spatial_distance_km"].sum().rename("dist_km").reset_index()
             if have_dist else None)

    def slice_annee(a):
        s = ds[ds["annee"] == a].copy()
        if cdist is not None:
            s = s.merge(cdist, on=["date", "numero_train"], how="left")
        else:
            s["dist_km"] = np.nan
        return s

    def masque(sub, kind):
        if kind == "c":       return sub["score"].values >= tau_c
        if kind == "a":       return sub["score"].values >= tau_a
        if kind == "b":       return sub["score"].values >= taus["b_rappel_renforce"]
        if kind == "plancher": return sub["resa2c"].values > SEUIL
        if kind == "union_c":  return (sub["score"].values >= tau_c) | (sub["resa2c"].values > SEUIL)
        if kind == "union_a":  return (sub["score"].values >= tau_a) | (sub["resa2c"].values > SEUIL)
        if kind == "humaine":  return sub["is_UM"].values.astype(bool)
        raise ValueError(kind)

    def evalue(sub, mask):
        y = sub["label"].values.astype(bool)
        return decision._eval_full(mask, y, sub["segment"].values)

    def cout_fp(sub, mask):
        y = sub["label"].values.astype(bool)
        fp = mask & ~y
        cout = float((TARE_T * sub.loc[fp, "dist_km"].fillna(0).values * TARIF_TBKM).sum()) if have_dist else None
        return {"n_FP": int(fp.sum()), "cout_CHF": round(cout, 0) if cout is not None else None}

    # ---- H24 : coherence de calibration (constat) ----
    h24 = slice_annee("H24")
    m_union_h24, m_c_h24 = masque(h24, "union_c"), masque(h24, "c")
    coherence_H24 = {
        "definition": "constat de coherence : c seul et c UNION plancher sur H24 (annee de calibration). "
                      "Pas de re-calibration.",
        "c_seul": evalue(h24, m_c_h24)["global"],
        "c_union_plancher": {**evalue(h24, m_union_h24)["global"],
                             "recouvrement": recouvrement(pd.Series(m_c_h24), pd.Series(masque(h24, "plancher")))},
        "bande_precision_cible": {"ideal": 0.66, "limite": 0.50},
    }

    # ---- H25 : chiffres canoniques ----
    h25 = slice_annee("H25")
    y25 = h25["label"].values.astype(bool)
    seg25 = h25["segment"].values
    m_union = masque(h25, "union_c")
    m_c = masque(h25, "c")
    m_pl = masque(h25, "plancher")

    deploiement_H25 = {
        **evalue(h25, m_union),
        "recouvrement": recouvrement(pd.Series(m_c), pd.Series(m_pl)),
    }

    # comparaison en colonnes (memes conventions), recalcule depuis ds pour coherence
    comparaison = {
        "deploiement_c_plancher": evalue(h25, m_union)["global"],
        "c_seul": evalue(h25, m_c)["global"],
        "a_plancher": evalue(h25, masque(h25, "union_a"))["global"],
        "b": evalue(h25, masque(h25, "b"))["global"],
        "humaine": evalue(h25, masque(h25, "humaine"))["global"],
    }

    # capture des 166+ (6 cas, detail par cas)
    charge = h25["charge_max"].values
    top166 = h25[charge >= 166].sort_values("charge_max", ascending=False)
    cas166 = []
    for r in top166.itertuples(index=False):
        sc, pl = bool(r.score >= tau_c), bool(r.resa2c > SEUIL)
        cas166.append({"date": str(pd.Timestamp(r.date).date()), "numero_train": r.numero_train,
                       "segment": r.segment, "charge": float(r.charge_max),
                       "score": round(float(r.score), 1), "resa2c": round(float(r.resa2c), 1),
                       "capte_par_score": sc, "capte_par_plancher": pl,
                       "capte": sc or pl,
                       "voie": ("les_deux" if sc and pl else "score" if sc else "plancher" if pl else "aucune")})
    capture_166 = {"n": len(cas166), "captes_union": sum(c["capte"] for c in cas166), "cas": cas166}

    # rappels par strate (surcharges)
    strata = {"63-93": (charge > 63) & (charge < 94),
              "94-165": (charge >= 94) & (charge < 166),
              "166+": (charge >= 166)}
    strata_recall = {}
    for sn, sm in strata.items():
        tot = int((y25 & sm).sum())
        strata_recall[sn] = {"n_surcharges": tot,
                             "deploiement_c_plancher": (int((m_union & y25 & sm).sum()) / tot) if tot else None,
                             "c_seul": (int((m_c & y25 & sm).sum()) / tot) if tot else None,
                             "a_plancher": (int((masque(h25, "union_a") & y25 & sm).sum()) / tot) if tot else None}

    # couts FP volet B (union)
    couts = {"deploiement_c_plancher": cout_fp(h25, m_union),
             "c_seul": cout_fp(h25, m_c),
             "a_plancher": cout_fp(h25, masque(h25, "union_a")),
             "humaine": cout_fp(h25, masque(h25, "humaine"))}

    res = {
        "meta": {"hash": "ba493568", "configuration": "deploiement : regle c (F0.5, seuil H24) UNION plancher (resa2c>63)",
                 "tau_c": tau_c, "n_courses_H25": info["n_h25"], "n_positives_H25": info["positives_h25"],
                 "n_positives_haut": info["positives_haut"], "n_positives_bas": info["positives_bas"],
                 "note": "AJOUT d'une configuration de deploiement ; la config d'evaluation a'+plancher (iso-volume) est inchangee."},
        "coherence_H24": coherence_H24,
        "deploiement_H25": deploiement_H25,
        "comparaison_H25": comparaison,
        "capture_166plus": capture_166,
        "rappels_par_strate_H25": strata_recall,
        "couts_fp_volet_B_H25": couts,
    }
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    # ---- impression (chiffres bruts) ----
    _p = lambda x: "n/d" if x is None else f"{x*100:.1f}%"
    print("=" * 78)
    print(f"CONFIG DEPLOIEMENT : c (tau={tau_c:.2f}) UNION plancher (resa2c>63) - ba493568")
    print(f"gardes : {info['n_h25']} courses / {info['positives_h25']} surcharges "
          f"({info['positives_haut']} HAUT / {info['positives_bas']} BAS)")
    print("=" * 78)
    print("\n[H24 coherence] c seul vs c+plancher (annee de calibration, constat)")
    cs, cu = coherence_H24["c_seul"], coherence_H24["c_union_plancher"]
    print(f"  c seul        : vol={cs['volume']} P={_p(cs['precision'])} R={_p(cs['recall'])}")
    print(f"  c+plancher    : vol={cu['volume']} P={_p(cu['precision'])} R={_p(cu['recall'])} "
          f"| recouvrement {cu['recouvrement']}")
    print(f"  bande cible   : ideal 66% / limite 50%")
    print("\n[H25 deploiement c+plancher]")
    g = deploiement_H25["global"]
    print(f"  GLOBAL : vol={g['volume']} VP={g['VP']} FP={g['FP']} P={_p(g['precision'])} R={_p(g['recall'])}")
    for s in ("haut", "bas"):
        d_ = deploiement_H25[s]
        print(f"    {s.upper():4} vol={d_['volume']} VP={d_['VP']} P={_p(d_['precision'])} R={_p(d_['recall'])}")
    print(f"  recouvrement : {deploiement_H25['recouvrement']}")
    print("\n[Comparaison H25, global : vol / P / R]")
    for k, v in comparaison.items():
        print(f"  {k:24} vol={v['volume']:5} P={_p(v['precision'])} R={_p(v['recall'])}")
    print("\n[Capture 166+ (6 cas)]")
    print(f"  union capte {capture_166['captes_union']}/{capture_166['n']}")
    for c in cas166:
        print(f"    {c['date']} {c['numero_train']} {c['segment']:4} charge={c['charge']:.0f} "
              f"score={c['score']} resa={c['resa2c']} -> {c['voie']}")
    print("\n[Rappels par strate H25 (deploiement / c_seul / a+plancher)]")
    for sn, v in strata_recall.items():
        print(f"  {sn:7} (n={v['n_surcharges']:4}) : {_p(v['deploiement_c_plancher'])} / "
              f"{_p(v['c_seul'])} / {_p(v['a_plancher'])}")
    print("\n[Couts FP volet B H25]")
    for k, v in couts.items():
        print(f"  {k:24} n_FP={v['n_FP']:5} cout={v['cout_CHF']} CHF")
    print(f"\n[OK] {OUT.name}")


if __name__ == "__main__":
    main()
