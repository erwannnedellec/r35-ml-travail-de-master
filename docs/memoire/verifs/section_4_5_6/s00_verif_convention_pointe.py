#!/usr/bin/env python3
"""Section 4.5.6 (extension) — verification reproductible de la convention de pointe.

Reproduit, depuis ml_dataset.parquet (ba493568, grain tronçon), les statistiques de
pointe de §4.3.4 sous les trois conventions candidates, pour SANCTIONNER le choix B :

  A  = {6,7,8,16,17,18}   (fenêtre 3 h, bornes incluses ; fig. 7 §4.3.2, compute_enrichissement)
  B  = {6,7,16,17}        (fenêtre réf. 2 h, demi-ouverte [6,8)∪[16,18) ; test T5 §4.3.4)  ← RETENUE
  C  = {5,6,7,8,16,17,18,19} (fenêtre large 5-8/16-19 ; ist ponctualité, verif_434)

Critère : la convention retenue doit reproduire EXACTEMENT le test T5 (bas ouvrable) et
les chiffres têtes de §4.3.4 (57,1 % / 85,4 % bas ; 11,4 % / 44,2 % haut). Jour ouvrable
= cal_type_jour_3classes == "ouvrable" (fériés exclus). LECTURE SEULE.

Sortie : tableaux/section_4_5_6/t_verif_convention_pointe.csv.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
TAB = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6"
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402

CONV = {"A_incl_678_161718": {6, 7, 8, 16, 17, 18},
        "B_demiouv_67_1617": {6, 7, 16, 17},
        "C_large_5678_16171819": {5, 6, 7, 8, 16, 17, 18, 19}}


def main() -> int:
    print("dataset:", H.assert_dataset())
    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet",
                         columns=["spatial_segment", "cal_type_jour_3classes",
                                  "cal_heure_depart", "target_voyageurs_2eme_classe"])
    df["surch"] = df["target_voyageurs_2eme_classe"].astype("float64") > H.SEUIL
    h = df["cal_heure_depart"].astype("int64")
    ouv = df["cal_type_jour_3classes"] == "ouvrable"
    rows = []
    for name, hs in CONV.items():
        peak = h.isin(hs)
        # T5 bas ouvrable (2x2 pointe × surcharge)
        b = df["spatial_segment"] == "bas"
        bo = b & ouv
        a = int((bo & peak & df.surch).sum()); bb = int((bo & peak & ~df.surch).sum())
        c = int((bo & ~peak & df.surch).sum()); d = int((bo & ~peak & ~df.surch).sum())
        expo = 100 * (a + bb) / int(bo.sum())
        occ = 100 * a / int((bo & df.surch).sum())
        tp = 100 * a / (a + bb); th = 100 * c / (c + d)
        OR = (a * d) / (bb * c)
        # haut : part surcharges en pointe (tous jours) et en ouvrable
        hs_seg = df["spatial_segment"] == "haut"
        hsu = hs_seg & df.surch
        haut_pointe = 100 * (hsu & peak).sum() / int(hsu.sum())
        haut_ouv = 100 * (hsu & ouv).sum() / int(hsu.sum())
        bas_ouv_part = 100 * (b & df.surch & ouv).sum() / int((b & df.surch).sum())
        rows.append(dict(convention=name,
                         bas_exposition_pointe_pct=round(expo, 2),
                         bas_occurrence_pointe_pct=round(occ, 2),
                         bas_taux_pointe_pct=round(tp, 3), bas_taux_hors_pct=round(th, 3),
                         bas_odds_ratio=round(OR, 3),
                         haut_pointe_tous_jours_pct=round(haut_pointe, 2),
                         haut_ouvrable_pct=round(haut_ouv, 2),
                         bas_ouvrable_pct=round(bas_ouv_part, 2),
                         a=a, b=bb, c=c, d=d))
    out = pd.DataFrame(rows)
    TAB.mkdir(parents=True, exist_ok=True)
    out.to_csv(TAB / "t_verif_convention_pointe.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(out.to_string(index=False))
    ref = out[out.convention == "B_demiouv_67_1617"].iloc[0]
    print("\nAttendus §4.3.4 : bas expo 31.21 / occ 57.11 / OR 3.058 ; haut pointe 11.4 / ouvr 44.2 ; bas ouvr 85.4")
    ok = (abs(ref.bas_exposition_pointe_pct - 31.21) < 0.05 and abs(ref.bas_occurrence_pointe_pct - 57.11) < 0.05
          and abs(ref.bas_odds_ratio - 3.058) < 0.01 and abs(ref.haut_pointe_tous_jours_pct - 11.43) < 0.05
          and abs(ref.haut_ouvrable_pct - 44.18) < 0.05 and abs(ref.bas_ouvrable_pct - 85.38) < 0.05)
    print("CONVENTION B reproduit §4.3.4 :", "OK" if ok else "ÉCART")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
