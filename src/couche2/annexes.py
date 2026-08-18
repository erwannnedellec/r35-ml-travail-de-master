"""
src/couche2/annexes.py — Couche 2 phase 2 : annexes descriptives X1-X9 (lecture seule).

Consolide toutes les vérifications pré-rédaction en un JSON à n bruts, chaque bloc
portant son STATUT (headline préenregistré / robustesse / descriptif / addendum
post-lecture). N'entraîne rien, ne change aucune politique. Le headline (top-k
protocolaire k=418, ADR-073 R6) reste défini dans decision.py et n'est pas rejoué ici.

NB terminologie : la règle candidate résa (X6) s'appelle « PLANCHER DE DEMANDE
ANNONCÉE » (réalisation 64-70 %, no-show 30-36 % — un plancher, pas une garantie).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np  # noqa: F401
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from couche2 import decision, blocs  # noqa: E402

ML = decision.ROOT / "data/processed/ml_dataset.parquet"
OUT = decision.ROOT / "outputs/couche2/q_couche2_annexes_ba493568.json"
RESA_COL = "resa_pax_2c_J_minus_1"
HISTO_COL = "histo_voyageurs_2eme_classe_win7_mean"


def compute_annexes() -> dict:
    ds = decision.build_decision_set()
    h = ds[ds["annee"] == "H25"].copy()
    y = h["label"].values.astype(bool)
    seg = h["segment"].values
    top = decision._topn_mask(h, decision.BUDGET_HUMAIN_H25)
    um = h["is_UM"].values.astype(bool)
    is1508 = (h["numero_train"] == "1508").values

    # ── X1 — recoupement (complémentarité) — statut headline préenregistré ──
    cell = lambda mr, hu: {"n": int(((top == mr) & (um == hu)).sum()),
                           "justifiees": int(((top == mr) & (um == hu) & y).sum())}
    X1 = {"statut": "headline préenregistré (grain course, iso-budget)",
          "matrice_modele_x_humain": {"reco_UM": cell(True, True), "reco_simple": cell(True, False),
                                       "non_UM": cell(False, True), "non_simple": cell(False, False)},
          "VP_modele": int((top & y).sum()), "VP_humain": int((um & y).sum()),
          "surcharges_captees_par_au_moins_un": int(((top | um) & y).sum()), "total_positives": int(y.sum())}

    # ── X2 — concentration du top-418 — descriptif ──
    t = h[top]
    X2 = {"statut": "descriptif",
          "jours_distincts": int(t["date"].nunique()), "jours_total": int(h["date"].nunique()),
          "reco_par_jour_med": int(t["date"].value_counts().median()), "reco_par_jour_max": int(t["date"].value_counts().max()),
          "top10_services": {str(k): int(v) for k, v in t["numero_train"].value_counts().head(10).items()},
          "par_mois": {str(k): int(v) for k, v in t["date"].dt.to_period("M").value_counts().sort_index().items()}}

    # ── X3 — profil des faux positifs — descriptif ──
    fp = t[~t["label"]]
    X3 = {"statut": "descriptif", "n_FP": int(len(fp)),
          "charge_55_63": int(((fp["charge_max"] >= 55) & (fp["charge_max"] <= 63)).sum()),
          "charge_40_55": int(((fp["charge_max"] >= 40) & (fp["charge_max"] < 55)).sum()),
          "charge_sous_40": int((fp["charge_max"] < 40).sum()),
          "charge_min_med_moy_max": [float(fp["charge_max"].min()), float(fp["charge_max"].median()),
                                     float(fp["charge_max"].mean()), float(fp["charge_max"].max())]}

    # ── X4 — top-20 nominatif — descriptif ──
    t20 = h.sort_values(["score", "date", "numero_train"], ascending=[False, True, True]).head(20)
    X4 = {"statut": "descriptif",
          "top20": [{"date": str(r.date.date()), "train": r.numero_train, "segment": r.segment,
                     "score": round(float(r.score), 1), "charge_observee": int(round(r.charge_max)),
                     "UM_humaine": bool(r.is_UM)} for r in t20.itertuples()]}

    # ── X7 — sensibilité 1508 — robustesse (hors headline) ──
    h_ex = h[~is1508]
    idx_ex = set(h_ex.sort_values(["score", "date", "numero_train"], ascending=[False, True, True]).index[:418])
    mask_ex = h.index.isin(idx_ex)
    X7 = {"statut": "robustesse (hors protocole headline)",
          "avec_1508": decision._eval_full(top, y, seg),
          "sans_1508_reclasse": decision._eval_full(mask_ex, y, seg),
          "contribution_1508_dans_top418": {"n": int((top & is1508).sum()), "VP": int((top & is1508 & y).sum()),
                                            "FP": int((top & is1508 & ~y).sum())},
          "humain_UM_sur_1508_H25": int((um & is1508).sum())}

    # ── X8 + X9 — données & trajectoire 1508 (+ famille) — descriptif ──
    ml = pd.read_parquet(ML, columns=["base_date", "horaire_numero_train", "horaire_annee_horaire",
                                      "target_voyageurs_2eme_classe", HISTO_COL, RESA_COL,
                                      "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre"])
    ml["nt"] = ml["horaire_numero_train"].astype("Int64").astype(str)
    ml["mth"] = pd.to_datetime(ml["base_date"]).dt.to_period("M").astype(str)
    comp = blocs.load_composition()

    def profil_service(svc):
        m = ml[ml["nt"] == svc]
        annees = sorted(m["horaire_annee_horaire"].unique())
        cc = m.groupby([pd.to_datetime(m["base_date"]).dt.normalize()]).target_voyageurs_2eme_classe.max()
        rot = comp[comp["numero_train"] == svc]
        return {"annees_presentes": annees, "n_courses": int(len(cc)),
                "charge_course_med": float(cc.median()), "charge_course_q90": float(cc.quantile(.9)),
                "pct_gt63": float((cc > 63).mean()), "pct_gt94": float((cc > 94).mean()),
                "rotations_UM": int(rot["is_UM"].sum()), "rotations_courses": int(len(rot))}

    # trajectoire mensuelle (rang percentile) pour 1508/1308/1306
    h["mth"] = h["date"].dt.to_period("M").astype(str)
    h["pct"] = h.groupby("mth")["score"].rank(pct=True)
    budget_frac = decision.BUDGET_HUMAIN_H25 / decision.ISO_PERIMETRE_H25
    def trajectoire(svc):
        s = h[h["numero_train"] == svc]
        out = {}
        for mth, g in s.groupby("mth"):
            thr = h[h["mth"] == mth]["score"].quantile(1 - budget_frac)
            hist = ml[(ml["nt"] == svc) & (ml["mth"] == mth)][HISTO_COL]
            out[mth] = {"n": int(len(g)), "score_med": round(float(g["score"].median()), 1),
                        "pct_rang_med": round(float(g["pct"].median()), 2),
                        "dans_top_budget_mois": int((g["score"] >= thr).sum()),
                        "histo_pct_nonnull": round(float(hist.notna().mean()), 2) if len(hist) else None}
        return out

    X8 = {"statut": "descriptif — source APC EN COURS DE VÉRIFICATION MÉTIER (pas de tx_equipement dans ml_dataset)",
          "profils": {svc: profil_service(svc) for svc in ("1508", "1308", "1306", "1447")}}
    X9 = {"statut": "descriptif (hors headline)",
          "conclusion": "1508 top-rangé À PARTIR de janvier 2025 (histo dispo), milieu de peloton en déc-2024 : "
                        "rattrapage histo-piloté ~1 mois (cutoff mensuel ADR-062), pas un prior structurel.",
          "trajectoire_rang_percentile": {svc: trajectoire(svc) for svc in ("1508", "1308", "1306")}}

    # ── X6 — PLANCHER DE DEMANDE ANNONCÉE (résa>63) — addendum post-lecture ──
    resa = ml.groupby([pd.to_datetime(ml["base_date"]).dt.normalize(), "nt", "horaire_annee_horaire"])[RESA_COL].max().reset_index()
    resa.columns = ["date", "numero_train", "annee", "resa2c"]
    # ds porte deja une colonne resa2c (build_decision_set, D3) : la retirer avant le merge
    # pour eviter la collision de colonnes (resa2c_x/_y) qui faisait echouer d2["resa2c"].
    # La version ml-derivee (resa, ci-dessus) fait foi. Defaut pre-existant revele par la
    # regeneration ba493568 (bug de code, non couvert par l'engagement ADR-076 qui vise les re-gels).
    d2 = ds.drop(columns=["resa2c"], errors="ignore").merge(
        resa, on=["date", "numero_train", "annee"], how="left")
    plancher = {"statut": "addendum post-lecture H25 (« plancher de demande annoncée » — plancher, pas garantie)",
                "regle": f"{RESA_COL} > 63 (course-level, J-1)"}
    for a in ("H24", "H25"):
        sub = d2[d2["annee"] == a]; rr = sub[sub["resa2c"] > 63]
        plancher[a] = {"n": int(len(rr)), "HAUT": int((rr["segment"] == "haut").sum()),
                       "BAS": int((rr["segment"] == "bas").sum()),
                       "surcharge_realisee": int(rr["label"].sum()),
                       "taux_realisation": round(float(rr["label"].mean()), 3)}
    h25d = d2[d2["annee"] == "H25"].copy()
    h25d["top418"] = decision._topn_mask(ds[ds["annee"] == "H25"], 418)
    rr = h25d[h25d["resa2c"] > 63]
    plancher["croisement_top418_H25"] = {
        "total": int(len(rr)), "deja_dans_top418_redondance": int(rr["top418"].sum()),
        "apport_propre_hors_top418": int((~rr["top418"]).sum()),
        "apport_propre_surcharge_realisee": int(rr[~rr["top418"]]["label"].sum())}

    return {"meta": {"hash": "ba493568", "n_courses_H25": int(len(h)), "n_positives_H25": int(y.sum())},
            "X1_recoupement": X1, "X2_concentration": X2, "X3_faux_positifs": X3, "X4_top20": X4,
            "X7_robustesse_1508": X7, "X8_donnees_services": X8, "X9_trajectoire": X9,
            "X6_plancher_demande_annoncee": plancher}


if __name__ == "__main__":
    res = compute_annexes()
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    x1 = res["X1_recoupement"]; x7 = res["X7_robustesse_1508"]; pl = res["X6_plancher_demande_annoncee"]
    print(f"[X1] union captée={x1['surcharges_captees_par_au_moins_un']}/{x1['total_positives']} "
          f"(modèle {x1['VP_modele']}, humain {x1['VP_humain']})")
    print(f"[X7] top418 sans 1508 P={x7['sans_1508_reclasse']['global']['precision']*100:.1f}% (avec={x7['avec_1508']['global']['precision']*100:.1f}%)")
    print(f"[X6 plancher] H25 apport propre={pl['croisement_top418_H25']['apport_propre_hors_top418']} "
          f"(réalisées={pl['croisement_top418_H25']['apport_propre_surcharge_realisee']})")
    print(f"[OK] {OUT.name}")
