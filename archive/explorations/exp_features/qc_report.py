"""
CHANTIER FEATURES — Phase A, ETAPE 5 : controle qualite des 8 features.
Couverture / plausibilite / correlations inter-cantonales et avec le vaudois.
N'integre rien : lecture seule des sorties de build_cantonal_features.py.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "outputs"
CANTONS = ["valais", "fribourg", "neuchatel", "geneve"]

# dataset canonique
DS0, DS1 = pd.Timestamp("2021-12-12"), pd.Timestamp("2025-12-13")
# split temporel (ADR-28/40) : train H22-H24, test H25
SPLIT = pd.Timestamp("2024-12-15")  # frontiere indicative H24/H25


def main():
    f = pd.read_parquet(OUT / "features_vacances_feries_cantonales.parquet")
    f["date"] = pd.to_datetime(f["date"])
    f = f[(f.date >= DS0) & (f.date <= DS1)].reset_index(drop=True)
    f["annee"] = f.date.dt.year
    f["is_weekday"] = f.date.dt.weekday < 5

    vac_cols = [f"event_is_vacances_{c}" for c in CANTONS]
    fer_cols = [f"event_is_ferie_{c}" for c in CANTONS]

    print("=" * 78)
    print(f"PERIMETRE QC : {f.date.min().date()} -> {f.date.max().date()}  ({len(f)} jours)")
    print("=" * 78)

    # 1) COUVERTURE / NaN
    print("\n[1] COUVERTURE (taux NaN par feature)")
    na = f[vac_cols + fer_cols].isna().mean()
    print("  NaN max:", float(na.max()), "-> aucune NaN (features binaires construites)" if na.max() == 0 else "")

    # 1b) couverture par annee : une periode de vacances detectee chaque annee/canton ?
    print("\n[1b] VACANCES : nb jours par annee/canton (detecte une asymetrie source)")
    piv = f.groupby("annee")[vac_cols].sum()
    print(piv.to_string())
    print("\n[1c] FERIES : nb jours par annee/canton")
    pivf = f.groupby("annee")[fer_cols].sum()
    print(pivf.to_string())

    # 2) PLAUSIBILITE : % de jours en vacances (~25-27% attendu, 13-14 semaines)
    print("\n[2] PLAUSIBILITE : % jours calendaires en vacances par canton (attendu ~25-27%)")
    full_years = [2022, 2023, 2024]  # annees civiles completes dans le perimetre
    fy = f[f.annee.isin(full_years)]
    for c in CANTONS:
        col = f"event_is_vacances_{c}"
        by = fy.groupby("annee")[col].mean() * 100
        print(f"  {c:10s}: " + "  ".join(f"{y}={by[y]:.1f}%" for y in full_years)
              + f"   moy={by.mean():.1f}%")
    print("\n[2b] FERIES : nb jours feries / an (attendu ~10-14 selon canton)")
    for c in CANTONS:
        col = f"event_is_ferie_{c}"
        by = fy.groupby("annee")[col].sum()
        print(f"  {c:10s}: " + "  ".join(f"{y}={int(by[y])}" for y in full_years))

    # 3) CORRELATION INTER-CANTONALE (vacances) — attendu fort (calendriers romands)
    print("\n[3] CORRELATION INTER-CANTONALE — event_is_vacances_* (Pearson, jours ouvrables)")
    wk = f[f.is_weekday]
    cm = wk[vac_cols].corr()
    cm.columns = [c.replace("event_is_vacances_", "") for c in cm.columns]
    cm.index = cm.columns
    print(cm.round(3).to_string())
    print("\n[3b] CORRELATION INTER-CANTONALE — event_is_ferie_* (jours ouvrables)")
    cmf = wk[fer_cols].corr()
    cmf.columns = [c.replace("event_is_ferie_", "") for c in cmf.columns]
    cmf.index = cmf.columns
    print(cmf.round(3).to_string())

    # 4) CORRELATION AVEC LE VAUDOIS EXISTANT (crucial : redondance ?)
    print("\n[4] CORRELATION AVEC LE VAUDOIS EXISTANT (event_is_vacances_vaud / event_is_ferie_vaud)")
    v = pd.read_parquet(ROOT / "data" / "dimension" / "dim_vacances_feries_vaud.parquet")
    v["date"] = pd.to_datetime(v["date"])
    v = v[["date", "is_vacances_scolaires_vaud", "is_ferie_vaud"]].copy()
    v["vacances_vaud"] = v["is_vacances_scolaires_vaud"].astype(int)
    v["ferie_vaud"] = v["is_ferie_vaud"].astype(int)
    m = f.merge(v[["date", "vacances_vaud", "ferie_vaud"]], on="date", how="left")
    mwk = m[m.is_weekday]
    print("  vacances : corr(event_is_vacances_<canton>, vacances_vaud)  [jours ouvrables]")
    for c in CANTONS:
        r = mwk[f"event_is_vacances_{c}"].corr(mwk["vacances_vaud"])
        # taux de coincidence (jaccard sur jours ouvrables)
        a = mwk[f"event_is_vacances_{c}"].astype(bool); b = mwk["vacances_vaud"].astype(bool)
        jac = (a & b).sum() / (a | b).sum()
        flag = "  <<< QUASI-IDENTIQUE (>0.95)" if r > 0.95 else ""
        print(f"    {c:10s}: r={r:.3f}  jaccard={jac:.3f}{flag}")
    print("  feries : corr(event_is_ferie_<canton>, ferie_vaud)  [jours ouvrables]")
    for c in CANTONS:
        r = mwk[f"event_is_ferie_{c}"].corr(mwk["ferie_vaud"])
        a = mwk[f"event_is_ferie_{c}"].astype(bool); b = mwk["ferie_vaud"].astype(bool)
        jac = (a & b).sum() / (a | b).sum()
        flag = "  <<< QUASI-IDENTIQUE (>0.95)" if r > 0.95 else ""
        print(f"    {c:10s}: r={r:.3f}  jaccard={jac:.3f}{flag}")

    # 5) asymetrie train/test : presence de vacances des 2 cotes du split
    print("\n[5] ASYMETRIE TRAIN/TEST (split H24/H25 ~2024-12-15) : jours vacances de chaque cote")
    for c in CANTONS:
        col = f"event_is_vacances_{c}"
        tr = f[f.date < SPLIT][col].sum(); te = f[f.date >= SPLIT][col].sum()
        print(f"  {c:10s}: train={int(tr)}  test={int(te)}  "
              + ("OK" if tr > 0 and te > 0 else "<<< ASYMETRIE"))


if __name__ == "__main__":
    main()
