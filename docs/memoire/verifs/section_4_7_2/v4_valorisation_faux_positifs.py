#!/usr/bin/env python3
"""
V4 — Valorisation des faux positifs (section 4.7.2).

Etablit la methode de valorisation telle qu'elle est CODEE, puis recalcule le cout
unitaire moyen par faux positif et la distance moyenne parcourue dans chacun des
deux ensembles compares par le manuscrit :
  - la pratique humaine  (418 UM engagees sur H25, dont 278 faux positifs) ;
  - la configuration de deploiement c UNION plancher (866 recommandations, 244 FP).

Lecture seule stricte : aucun reentrainement, les modeles de couche 1 sont lus figes
par src/couche2/decision.py.

Sorties : docs/memoire/verifs/section_4_7/v4_*.csv
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
from _garde import ROOT, garde  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

OUT = _HERE
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
CALIB = ROOT / "outputs" / "couche2" / "q_couche2_calibration_H24_ba493568.json"

# Constantes de valorisation — reprises a l'identique de la source unique :
# scripts/experiences/deploiement_c_plancher_ba493568.py:40-42
TARE_T = 54.2          # tare du materiel, en tonnes
TARIF_TBKM = 0.06444   # CHF par tonne-brute-kilometre
SEUIL = 63             # places assises 2e classe (ADR-060)


def main() -> None:
    garde()
    print("=" * 78)
    print("V4 — VALORISATION DES FAUX POSITIFS")
    print("=" * 78)

    print("\n[1] Methode telle qu'elle est codee")
    print("    source unique : scripts/experiences/deploiement_c_plancher_ba493568.py")
    print("      L40  SEUIL       = 63")
    print(f"      L41  TARE_T     = {TARE_T}   (tonnes)")
    print(f"      L42  TARIF_TBKM = {TARIF_TBKM} (CHF par tonne-brute-kilometre)")
    print("      L63-70  dist_km  = somme de `spatial_distance_km` sur les troncons de la course")
    print("      L94-99  cout     = somme, sur les FP, de TARE_T * dist_km * TARIF_TBKM")
    print("                         (`dist_km` manquante remplacee par 0 : .fillna(0))")
    print("    ADR fixant la convention : docs/adr/ADR-077_configuration_deploiement_c_plancher.md:54")

    # ── Jeu de decision fige ──────────────────────────────────────────────────
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)
    print(f"\n[2] Gardes du perimetre : {info['n_h25']} courses H25 / "
          f"{info['positives_h25']} surcharges "
          f"({info['positives_haut']} HAUT / {info['positives_bas']} BAS)")

    calib = json.loads(CALIB.read_text())
    tau = {k: calib["regles_deployables"][k]["seuil"] for k in
           ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")}
    print(f"    seuils calibres H24 : a' {tau['a_iso_volume']:.2f} | "
          f"b {tau['b_rappel_renforce']:.2f} | c {tau['c_haute_precision']:.2f}")

    # ── Distance par course ───────────────────────────────────────────────────
    df = pd.read_parquet(ML_DATASET, columns=["horaire_annee_horaire", "base_date",
                                              "horaire_numero_train", "spatial_distance_km"])
    d = df[df["horaire_annee_horaire"] == "H25"].copy()
    d["date"] = pd.to_datetime(d["base_date"]).dt.normalize()
    d["numero_train"] = d["horaire_numero_train"].astype("Int64").astype(str)
    cdist = (d.groupby(["date", "numero_train"])["spatial_distance_km"]
               .sum().rename("dist_km").reset_index())

    h25 = ds[ds["annee"] == "H25"].merge(cdist, on=["date", "numero_train"], how="left")
    n_sans_dist = int(h25["dist_km"].isna().sum())
    print(f"\n[3] Distance par course (somme des troncons) sur les {len(h25)} courses H25")
    print(f"    courses sans distance renseignee : {n_sans_dist}")
    print(f"    min {h25['dist_km'].min():.2f} km | mediane {h25['dist_km'].median():.2f} km | "
          f"max {h25['dist_km'].max():.2f} km")

    # ── Ensembles compares ────────────────────────────────────────────────────
    def masque(sub, kind):
        s, r = sub["score"].values, sub["resa2c"].values
        if kind == "humaine":            return sub["is_UM"].values.astype(bool)
        if kind == "deploiement_c_plancher": return (s >= tau["c_haute_precision"]) | (r > SEUIL)
        if kind == "c_seul":             return s >= tau["c_haute_precision"]
        if kind == "a_plancher":         return (s >= tau["a_iso_volume"]) | (r > SEUIL)
        if kind == "b":                  return s >= tau["b_rappel_renforce"]
        raise ValueError(kind)

    ENSEMBLES = ["humaine", "deploiement_c_plancher", "c_seul", "a_plancher", "b"]

    def valorise(sub, m):
        y = sub["label"].values.astype(bool)
        fp = m & ~y
        vp = m & y
        dfp = sub.loc[fp, "dist_km"]
        cout_ligne = TARE_T * dfp.fillna(0).values * TARIF_TBKM
        return {
            "volume": int(m.sum()), "VP": int(vp.sum()), "n_FP": int(fp.sum()),
            "precision_pct": round(100 * int(vp.sum()) / max(1, int(m.sum())), 2),
            "cout_total_CHF": round(float(cout_ligne.sum()), 1),
            "cout_moyen_par_FP_CHF": round(float(cout_ligne.mean()), 3) if fp.sum() else None,
            "cout_median_par_FP_CHF": round(float(np.median(cout_ligne)), 3) if fp.sum() else None,
            "distance_moyenne_FP_km": round(float(dfp.fillna(0).mean()), 4) if fp.sum() else None,
            "distance_mediane_FP_km": round(float(dfp.fillna(0).median()), 4) if fp.sum() else None,
            "distance_min_FP_km": round(float(dfp.min()), 3) if fp.sum() else None,
            "distance_max_FP_km": round(float(dfp.max()), 3) if fp.sum() else None,
            "FP_sans_distance": int(dfp.isna().sum()),
        }

    print("\n[4] Valorisation par ensemble (global)")
    glob = []
    for k in ENSEMBLES:
        r = valorise(h25, masque(h25, k))
        r["ensemble"] = k
        glob.append(r)
    gdf = pd.DataFrame(glob).set_index("ensemble")
    gdf.to_csv(OUT / "v4_valorisation_global.csv")
    print(gdf[["volume", "VP", "n_FP", "cout_total_CHF", "cout_moyen_par_FP_CHF",
               "distance_moyenne_FP_km"]].to_string())

    # ── Controle de reproduction des chiffres publies ─────────────────────────
    print("\n[5] Controle : reproduction des chiffres d'ADR-077 ligne 54")
    attendu = {"humaine": (278, 8719.0), "deploiement_c_plancher": (244, 6922.0),
               "c_seul": (235, 6592.0), "a_plancher": (78, 2495.0)}
    ctrl = []
    for k, (nfp, cout) in attendu.items():
        obs_n = int(gdf.loc[k, "n_FP"])
        obs_c = float(gdf.loc[k, "cout_total_CHF"])
        ctrl.append({"ensemble": k, "n_FP_publie": nfp, "n_FP_recalcule": obs_n,
                     "cout_publie_CHF": cout, "cout_recalcule_CHF": round(obs_c, 1),
                     "ecart_CHF": round(obs_c - cout, 1),
                     "conforme_a_l_unite": bool(abs(obs_c - cout) < 1.0 and obs_n == nfp)})
        print(f"    {k:24} FP {obs_n} (publie {nfp}) | "
              f"cout {obs_c:.1f} CHF (publie {cout:.0f}) | ecart {obs_c - cout:+.1f}")
    pd.DataFrame(ctrl).to_csv(OUT / "v4_controle_reproduction.csv", index=False)

    # ── Ventilation par segment ───────────────────────────────────────────────
    print("\n[6] Ventilation par segment")
    seg_rows = []
    for k in ENSEMBLES:
        m = masque(h25, k)
        for s in ("bas", "haut"):
            sub = h25[h25["segment"] == s]
            r = valorise(sub, masque(sub, k))
            r.update({"ensemble": k, "segment": s})
            seg_rows.append(r)
    sdf = pd.DataFrame(seg_rows)
    sdf = sdf[["ensemble", "segment", "volume", "VP", "n_FP", "cout_total_CHF",
               "cout_moyen_par_FP_CHF", "distance_moyenne_FP_km", "distance_mediane_FP_km"]]
    sdf.to_csv(OUT / "v4_valorisation_par_segment.csv", index=False)
    print(sdf.to_string(index=False))

    # ── Decomposition de l'ecart de cout unitaire ─────────────────────────────
    print("\n[7] Decomposition de l'ecart de cout unitaire humaine vs deploiement")
    cu_h = float(gdf.loc["humaine", "cout_moyen_par_FP_CHF"])
    cu_d = float(gdf.loc["deploiement_c_plancher", "cout_moyen_par_FP_CHF"])
    dm_h = float(gdf.loc["humaine", "distance_moyenne_FP_km"])
    dm_d = float(gdf.loc["deploiement_c_plancher", "distance_moyenne_FP_km"])
    facteur = TARE_T * TARIF_TBKM
    print(f"    facteur unitaire TARE_T x TARIF_TBKM = {facteur:.6f} CHF/km")
    print(f"    humaine     : {cu_h:.4f} CHF/FP pour {dm_h:.4f} km/FP "
          f"-> {cu_h / dm_h:.6f} CHF/km")
    print(f"    deploiement : {cu_d:.4f} CHF/FP pour {dm_d:.4f} km/FP "
          f"-> {cu_d / dm_d:.6f} CHF/km")
    residu = (cu_h - cu_d) - facteur * (dm_h - dm_d)
    print(f"    ecart de cout unitaire observe        : {cu_h - cu_d:+.4f} CHF/FP")
    print(f"    ecart explique par la distance seule  : {facteur * (dm_h - dm_d):+.4f} CHF/FP")
    print(f"    residu                                : {residu:+.6f} CHF/FP")
    pd.DataFrame([{
        "facteur_CHF_par_km": round(facteur, 6),
        "cout_unitaire_humaine_CHF": round(cu_h, 4),
        "cout_unitaire_deploiement_CHF": round(cu_d, 4),
        "distance_moyenne_humaine_km": round(dm_h, 4),
        "distance_moyenne_deploiement_km": round(dm_d, 4),
        "ecart_cout_unitaire_CHF": round(cu_h - cu_d, 4),
        "ecart_explique_par_distance_CHF": round(facteur * (dm_h - dm_d), 4),
        "residu_CHF": round(residu, 6),
    }]).to_csv(OUT / "v4_decomposition_ecart.csv", index=False)

    # ── Distribution des distances de course des FP ───────────────────────────
    print("\n[8] Distribution du nombre de troncons des courses en faux positif")
    ntr = []
    for k in ("humaine", "deploiement_c_plancher"):
        m = masque(h25, k)
        fp = h25[m & ~h25["label"].values.astype(bool)]
        ntr.append({"ensemble": k, "n_FP": len(fp),
                    "troncons_moyen": round(float(fp["n_troncons"].mean()), 3),
                    "troncons_median": float(fp["n_troncons"].median()),
                    "part_segment_haut_pct": round(100 * float((fp["segment"] == "haut").mean()), 2),
                    "part_segment_bas_pct": round(100 * float((fp["segment"] == "bas").mean()), 2)})
    ndf = pd.DataFrame(ntr)
    ndf.to_csv(OUT / "v4_composition_fp.csv", index=False)
    print(ndf.to_string(index=False))

    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
