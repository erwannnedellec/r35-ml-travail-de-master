"""
src/couche2/restitution.py — Couche 2 phase 3 : restitution POC (lecture seule).

3.1 Table de restitution J-1 pour un jour type de H25 (aide à la décision, aucune
    logique de décision automatique : drapeaux seulement).
3.3 Liste CANDIDATE de cas pour la matrice de confusion au top-k protocolaire
    (guide d'entretien §2.3, section D) — 8-10 candidats par case pour choix humain.

N'entraîne rien, ne change aucune politique. Importe decision.py (scores figés).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from couche2 import decision, blocs  # noqa: E402

OUT = decision.ROOT / "outputs/couche2"
JOUR_TYPE = "2025-01-23"                        # ouvrable hors vacances, contient le top-1 du 1508
ML_COLS = ["base_date", "horaire_numero_train", "target_voyageurs_2eme_classe",
           "resa_pax_2c_J_minus_1", "histo_voyageurs_2eme_classe_win7_mean", "cal_type_jour"]


def _load_ctx():
    """ds H25 + prédictions tronçon + résa + histo + calibration (seuils figés)."""
    ds = decision.build_decision_set()
    h = ds[ds["annee"] == "H25"].copy()
    h["top418"] = decision._topn_mask(h, decision.BUDGET_HUMAIN_H25)
    tr = decision.load_troncon_predictions()
    tr = tr[tr["annee"] == "H25"]
    ml = pd.read_parquet(decision.ROOT / "data/processed/ml_dataset.parquet", columns=ML_COLS)
    ml["date"] = pd.to_datetime(ml["base_date"]).dt.normalize()
    ml["numero_train"] = ml["horaire_numero_train"].astype("Int64").astype(str)
    ctx = ml.groupby(["date", "numero_train"]).agg(
        resa_pax_2c=("resa_pax_2c_J_minus_1", "max"),
        histo_win7=("histo_voyageurs_2eme_classe_win7_mean", "max"),
        cal_type_jour=("cal_type_jour", "first")).reset_index()
    h = h.merge(ctx, on=["date", "numero_train"], how="left")
    calib = json.loads((OUT / "q_couche2_calibration_H24_ba493568.json").read_text())
    taus = {k: v["seuil"] for k, v in calib["regles_deployables"].items()}
    return ds, h, tr, taus


def restitution_jour(jour: str = JOUR_TYPE) -> pd.DataFrame:
    """3.1 — table J-1 du jour : score, tronçons>seuil, drapeaux 3 points déployables
    (seuil figé), drapeau plancher de demande annoncée (résa), courses chaînées (contexte)."""
    ds, h, tr, taus = _load_ctx()
    d = pd.Timestamp(jour)
    day = h[h["date"] == d].copy()

    # tronçons prédits > 63 par course (pour la lisibilité opérationnelle)
    trd = tr[tr["date"] == d]
    ntr = trd[trd["pred"] > decision.SEUIL].groupby("numero_train").size().rename("troncons_pred_gt63")
    day = day.merge(ntr, on="numero_train", how="left")
    day["troncons_pred_gt63"] = day["troncons_pred_gt63"].fillna(0).astype(int)

    # courses chaînées du même véhicule ce jour (contexte rotations, SANS logique de décision)
    comp = blocs.load_composition()
    comp["date"] = pd.to_datetime(comp["date"]).dt.normalize()
    cday = comp[comp["date"] == d]
    veh2courses = {}
    for _, r in cday.iterrows():
        for v in r["vehicles"]:
            veh2courses.setdefault(v, set()).add(r["numero_train"])
    def chainees(nt):
        vehs = cday[cday["numero_train"] == nt]["vehicles"]
        s = set()
        for vv in vehs:
            for v in vv:
                s |= veh2courses.get(v, set())
        s.discard(nt)
        return ",".join(sorted(s)) if s else ""
    day["courses_chainees_meme_vehicule"] = day["numero_train"].map(chainees)

    day["drapeau_a_iso_volume"] = day["score"] >= taus["a_iso_volume"]
    day["drapeau_b_rappel_renforce"] = day["score"] >= taus["b_rappel_renforce"]
    day["drapeau_c_haute_precision"] = day["score"] >= taus["c_haute_precision"]
    day["drapeau_plancher_demande_annoncee"] = day["resa_pax_2c"] > decision.SEUIL
    # mode d'échec du plancher (X6, réalisation 64-70 %) : résa annoncée > 63 non réalisée = no-show
    day["plancher_statut"] = np.where(
        day["drapeau_plancher_demande_annoncee"] & (day["charge_max"] <= decision.SEUIL),
        "no-show/annulation groupe",
        np.where(day["drapeau_plancher_demande_annoncee"], "réalisée", ""))
    # cas limite : demande annoncée > capacité UM (2 x 63 = 126) -> hors périmètre couche 2, à signaler
    day["resa_gt_capacite_UM_126"] = day["resa_pax_2c"] > 126

    cols = ["numero_train", "segment", "score", "troncons_pred_gt63",
            "drapeau_a_iso_volume", "drapeau_b_rappel_renforce", "drapeau_c_haute_precision",
            "drapeau_plancher_demande_annoncee", "plancher_statut", "resa_gt_capacite_UM_126",
            "resa_pax_2c", "histo_win7", "charge_max", "is_UM", "courses_chainees_meme_vehicule"]
    day = day.sort_values("score", ascending=False)[cols]
    day["score"] = day["score"].round(1)
    return day


def candidats_entretien() -> dict:
    """3.3 — candidats par case de la matrice de confusion au POINT D'OPÉRATION a'
    (iso-volume, seuil figé — ADR-073 addendum 2026-07-05 ; remplace le top-k protocolaire).
    Guide §2.3 : cible 2 VP / 1 VN / 1 FP / 2 FN. 8-10 candidats/case pour choix humain."""
    ds, h, tr, taus = _load_ctx()
    tau_a = taus["a_iso_volume"]
    resa = h["resa_pax_2c"].fillna(0)
    h["reco"] = (h["score"] >= tau_a) | (resa > decision.SEUIL)   # artefact complet : a' (score) ∪ plancher (résa)
    h["cell"] = "VN"
    h.loc[h["reco"] & h["label"], "cell"] = "VP"
    h.loc[h["reco"] & ~h["label"], "cell"] = "FP"
    h.loc[~h["reco"] & h["label"], "cell"] = "FN"

    def _reco_par(score, r2c):
        a = score >= tau_a; p = (r2c or 0) > decision.SEUIL
        return "a'+plancher" if (a and p) else ("a'" if a else ("plancher" if p else "—"))

    def to_rows(sub):
        return [{"date": str(r.date.date()), "train": r.numero_train, "segment": r.segment,
                 "score": round(float(r.score), 1), "charge_observee": int(round(r.charge_max)),
                 "UM_humaine": bool(r.is_UM), "resa_pax_2c": int(r.resa_pax_2c) if pd.notna(r.resa_pax_2c) else 0,
                 "reco_par": _reco_par(r.score, r.resa_pax_2c),
                 "histo_win7": round(float(r.histo_win7), 1) if pd.notna(r.histo_win7) else None}
                for r in sub.itertuples()]

    out = {"statut": "candidats — supports d'entretien (aucune décision) ; matrice à l'ARTEFACT COMPLET au point de référence (score a' ∪ plancher de demande annoncée) — ADR-073 addendum 2026-07-05",
           "point_operation": f"artefact complet = a' iso-volume (seuil H24 figé = {tau_a:.1f}) UNION plancher (résa>63) ; volume H25 = 353",
           "mention_supports": "recommandations à l'artefact complet au point de référence (score a' + plancher, ADR-073)",
           "cible_guide_2_3": "2 VP / 1 VN / 1 FP / 2 FN (choix humain parmi les candidats)"}
    # VP : diversité — inclure explicitement 1508 (VP modèle / non-UM humain) + famille 1308
    vp = h[h.cell == "VP"]
    out["VP_candidats"] = {
        "1508_non_UM_humain": to_rows(vp[(vp.numero_train == "1508") & ~vp.is_UM].sort_values("score", ascending=False).head(4)),
        "famille_1308": to_rows(vp[vp.numero_train == "1308"].sort_values("score", ascending=False).head(3)),
        "HAUT_touristique": to_rows(vp[vp.segment == "haut"].sort_values("score", ascending=False).head(4)),
        "avec_reservation": to_rows(vp[vp.resa_pax_2c > 63].sort_values("score", ascending=False).head(3))}
    # FP : sévérité — quasi-seuil (55-63) vs franchement bas (<40)
    fp = h[h.cell == "FP"]
    out["FP_candidats"] = {
        "quasi_seuil_55_63": to_rows(fp[(fp.charge_max >= 55) & (fp.charge_max <= 63)].sort_values("score", ascending=False).head(5)),
        "franchement_bas_sous40": to_rows(fp[fp.charge_max < 40].sort_values("score", ascending=False).head(5))}
    # FN : sévérité — surcharges manquées les plus lourdes / avec résa / HAUT
    fn = h[h.cell == "FN"]
    out["FN_candidats"] = {
        "charge_la_plus_lourde": to_rows(fn.sort_values("charge_max", ascending=False).head(5)),
        "avec_reservation": to_rows(fn[fn.resa_pax_2c > 63].sort_values("charge_max", ascending=False).head(4)),
        "HAUT": to_rows(fn[fn.segment == "haut"].sort_values("charge_max", ascending=False).head(3))}
    # VN : contrôle — vrais négatifs nets (score bas, charge basse)
    vn = h[h.cell == "VN"]
    out["VN_candidats"] = to_rows(vn.sort_values("score").head(8))
    return out


if __name__ == "__main__":
    rj = restitution_jour()
    csv = OUT / f"restitution_j1_{JOUR_TYPE}.csv"
    rj.to_csv(csv, index=False)
    print(f"[3.1] restitution {JOUR_TYPE} : {len(rj)} courses | recommandées(top-418)="
          f"{int(rj['drapeau_a_iso_volume'].sum())}(a')/{int(rj['drapeau_c_haute_precision'].sum())}(c)/"
          f"{int(rj['drapeau_b_rappel_renforce'].sum())}(b) | plancher résa="
          f"{int(rj['drapeau_plancher_demande_annoncee'].sum())}")
    print(rj.head(8).to_string(index=False))
    cand = candidats_entretien()
    (OUT / "q_couche2_cas_entretien_candidats.json").write_text(json.dumps(cand, indent=2, ensure_ascii=False))
    print(f"\n[3.3] candidats : VP {sum(len(v) for v in cand['VP_candidats'].values())} | "
          f"FP {sum(len(v) for v in cand['FP_candidats'].values())} | "
          f"FN {sum(len(v) for v in cand['FN_candidats'].values())} | VN {len(cand['VN_candidats'])}")
    print(f"[OK] {csv.name} + q_couche2_cas_entretien_candidats.json")
