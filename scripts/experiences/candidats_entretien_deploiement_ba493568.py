#!/usr/bin/env python3
"""
Candidats pour la matrice de confusion a la CONFIGURATION DE DEPLOIEMENT c UNION plancher
(ADR-077, gel ba493568). Substitution de restitution.py::candidats_entretien (qui reste a
a'+plancher, config d'evaluation iso-volume, INCHANGEE). Meme structure de candidats
(cible 2 VP / 1 VN / 1 FP / 2 FN ; sous-groupes diversite/severite) au point d'operation
c UNION plancher. Ne selectionne PAS les 6 (choix humain par le protocole 2.3). Lecture seule.
Threads=1.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision, restitution  # noqa: E402

OUT = ROOT / "outputs/couche2/q_couche2_cas_entretien_candidats_deploiement_ba493568.json"


def _reco_par(score, r2c, tau_c):
    c = score >= tau_c
    p = (r2c or 0) > decision.SEUIL
    return "c+plancher" if (c and p) else ("c" if c else ("plancher" if p else "—"))


def to_rows(sub, tau_c):
    return [{"date": str(r.date.date()), "train": r.numero_train, "segment": r.segment,
             "score": round(float(r.score), 1), "charge_observee": int(round(r.charge_max)),
             "UM_humaine": bool(r.is_UM),
             "resa_pax_2c": int(r.resa_pax_2c) if pd.notna(r.resa_pax_2c) else 0,
             "reco_par": _reco_par(r.score, r.resa_pax_2c, tau_c),
             "histo_win7": round(float(r.histo_win7), 1) if pd.notna(r.histo_win7) else None}
            for r in sub.itertuples()]


def main():
    ds, h, tr, taus = restitution._load_ctx()
    tau_c = taus["c_haute_precision"]
    resa = h["resa_pax_2c"].fillna(0)
    h["reco"] = (h["score"] >= tau_c) | (resa > decision.SEUIL)   # config deploiement : c ∪ plancher
    h["cell"] = "VN"
    h.loc[h["reco"] & h["label"], "cell"] = "VP"
    h.loc[h["reco"] & ~h["label"], "cell"] = "FP"
    h.loc[~h["reco"] & h["label"], "cell"] = "FN"

    counts = h["cell"].value_counts().to_dict()
    out = {"statut": "candidats — supports d'entretien (aucune decision) ; matrice a la CONFIGURATION DE DEPLOIEMENT (score c ∪ plancher de demande annoncee) — ADR-077",
           "point_operation": f"deploiement = c (F0.5, seuil H24 fige = {tau_c:.1f}) UNION plancher (resa>63) ; volume H25 = {int(h['reco'].sum())}",
           "cible_guide_2_3": "2 VP / 1 VN / 1 FP / 2 FN (choix humain parmi les candidats, protocole 2.3)",
           "matrice_H25": {"VP": int(counts.get("VP", 0)), "FP": int(counts.get("FP", 0)),
                           "FN": int(counts.get("FN", 0)), "VN": int(counts.get("VN", 0))}}

    vp = h[h.cell == "VP"]
    out["VP_candidats"] = {
        "1508_non_UM_humain": to_rows(vp[(vp.numero_train == "1508") & ~vp.is_UM].sort_values("score", ascending=False).head(4), tau_c),
        "famille_1308": to_rows(vp[vp.numero_train == "1308"].sort_values("score", ascending=False).head(3), tau_c),
        "HAUT_touristique": to_rows(vp[vp.segment == "haut"].sort_values("score", ascending=False).head(4), tau_c),
        "avec_reservation": to_rows(vp[vp.resa_pax_2c > 63].sort_values("score", ascending=False).head(3), tau_c)}
    fp = h[h.cell == "FP"]
    out["FP_candidats"] = {
        "quasi_seuil_55_63": to_rows(fp[(fp.charge_max >= 55) & (fp.charge_max <= 63)].sort_values("score", ascending=False).head(5), tau_c),
        "franchement_bas_sous40": to_rows(fp[fp.charge_max < 40].sort_values("score", ascending=False).head(5), tau_c)}
    fn = h[h.cell == "FN"]
    out["FN_candidats"] = {
        "charge_la_plus_lourde": to_rows(fn.sort_values("charge_max", ascending=False).head(6), tau_c),
        "avec_reservation": to_rows(fn[fn.resa_pax_2c > 63].sort_values("charge_max", ascending=False).head(4), tau_c),
        "HAUT": to_rows(fn[fn.segment == "haut"].sort_values("charge_max", ascending=False).head(3), tau_c)}
    vn = h[h.cell == "VN"]
    out["VN_candidats"] = to_rows(vn.sort_values("score").head(8), tau_c)

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[deploiement c∪plancher] matrice H25 : {out['matrice_H25']}")
    print(f"  volume reco = {int(h['reco'].sum())} ; tau_c = {tau_c:.2f}")
    print("  FN candidats — charge la plus lourde (dont les 166+ non captes) :")
    for r in out["FN_candidats"]["charge_la_plus_lourde"]:
        print(f"    {r['date']} {r['train']} {r['segment']:4} charge={r['charge_observee']} "
              f"score={r['score']} resa={r['resa_pax_2c']} reco_par={r['reco_par']}")
    print(f"[OK] {OUT.name}")


if __name__ == "__main__":
    main()
