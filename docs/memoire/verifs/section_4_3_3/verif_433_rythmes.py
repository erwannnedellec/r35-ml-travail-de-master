#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification section 4.3.3 — Rythmes saisonniers de la ligne R35.

ADDENDUM PÉRIMÈTRE (compréhension des données avant gel) : la matrice mois × année
couvre **H16-H25** (dix années horaires, décembres distingués), calculée sur la **table
enrichie AMONT du filtre temporel** — `stage_10_reservations.parquet`
(cardinalité 2 360 762) — et NON sur le parquet gelé `ba493568` (H22-H25). Contrôle :
`stage_10` filtré à H22-H25 reproduit exactement les moyennes/surcharges de `ml_dataset`.

Produit :
  1. deux matrices mois horaire (1..13) x année horaire (H16..H25) :
       A. charge moyenne de deuxième classe (tronçon)
       B. taux de surcharge 2e classe (> 63 voy., tronçon)
  2. corrélations des profils mensuels année contre année :
       - au sein du bloc moderne H22-H25 (6 paires)
       - chaque année pandémique (H20, H21) contre les 9 autres
       - matrice 10x10 complète (CSV)
  3. saisonnalité des modulateurs (calendrier complet) : jours-manifestation,
     nombre de manifestations, jours d'ouverture ski, réservations de groupes — H16-H25.

Sources :
  - data/processed/stage_10_reservations.parquet   (amont, H16-H25, 2 360 762 lignes)
  - data/dimension/annees_horaires.csv             (bornes des années horaires)
  - data/dimension/dim_manifestations_riviera.parquet
  - data/dimension/dim_ski_pleiades.parquet
  - data/external/reservations/export_r35_h{16..25}.xlsx
"""
import warnings
warnings.filterwarnings("ignore")
import glob
import pandas as pd
from pathlib import Path

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/memoire/verifs/section_4_3_3"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = [f"H{n}" for n in range(16, 26)]          # H16 .. H25
PANDEMIC = ["H20", "H21"]
MODERN = ["H22", "H23", "H24", "H25"]
MH = list(range(1, 14))
MH_LABEL = {1: "Déc.(ouv.)", 2: "Jan", 3: "Fév", 4: "Mar", 5: "Avr", 6: "Mai",
            7: "Jun", 8: "Jul", 9: "Aoû", 10: "Sep", 11: "Oct", 12: "Nov",
            13: "Déc.(clôt.)"}
SEUIL = 63  # SEUIL_ASSISES (ADR-060 / ADR-CF16)

# --------------------------------------------------------------------------- #
# 0. Table enrichie amont du filtre temporel
# --------------------------------------------------------------------------- #
cols = ["base_date", "horaire_annee_horaire", "cal_mois", "cal_mois_horaire",
        "target_voyageurs_2eme_classe",
        "event_is_manifestation_riviera", "event_n_manifestations_riviera",
        "event_is_ski_ouvert", "event_covid_phase"]
df = pd.read_parquet(ROOT / "data/processed/stage_10_reservations.parquet", columns=cols)
df["cal_mois_horaire"] = df["cal_mois_horaire"].astype("int64")
df = df[df["horaire_annee_horaire"].isin(YEARS)].copy()
print(f"[stage_10 amont] {len(df):,} lignes tronçon (attendu 2 360 762), "
      f"années {sorted(df.horaire_annee_horaire.unique())}")


def as_matrix(series, years=YEARS):
    m = series.unstack().reindex(index=MH, columns=years)
    m.index = [MH_LABEL[i] for i in MH]
    return m


def _int(m):
    return m.fillna(0).round().astype("Int64")


def _fr(x, dec=2):
    if pd.isna(x):
        return "—"
    s = f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


# --------------------------------------------------------------------------- #
# 1. Matrices charge & surcharge (grain tronçon), H16-H25
# --------------------------------------------------------------------------- #
sub = df[df["target_voyageurs_2eme_classe"].notna()].copy()
sub["surch"] = (sub["target_voyageurs_2eme_classe"] > SEUIL).astype(float)
g = sub.groupby(["cal_mois_horaire", "horaire_annee_horaire"])
mean_load = as_matrix(g["target_voyageurs_2eme_classe"].mean())
surch_rate = as_matrix(g["surch"].mean() * 100.0)
n_obs = as_matrix(g["surch"].size())

print("\n===== MATRICE A — CHARGE MOYENNE 2e CLASSE (voy./tronçon) — H16-H25 =====")
print(mean_load.round(2).to_string())
print("\n===== MATRICE B — TAUX DE SURCHARGE 2e cl. > 63 (%) — H16-H25 =====")
print(surch_rate.round(2).to_string())
print("\n---- couverture (n tronçons observés non nuls) ----")
print(_int(n_obs).to_string())

ann = sub.groupby("horaire_annee_horaire").agg(
    charge_moy=("target_voyageurs_2eme_classe", "mean"),
    tx_surcharge_pct=("surch", lambda s: 100 * s.mean()),
    n=("surch", "size"))
print("\n---- repères annuels (pondérés) ----")
print(ann.round(3).reindex(YEARS).to_string())

# part pandémique par année (contexte)
covid = (df[df.target_voyageurs_2eme_classe.notna()]
         .assign(anormal=lambda d: d.event_covid_phase.ne("normal"))
         .groupby("horaire_annee_horaire")["anormal"].mean() * 100)
print("\n---- part de tronçons sous phase COVID non normale (%) ----")
print(covid.reindex(YEARS).round(1).to_string())

# --------------------------------------------------------------------------- #
# 2. Corrélations inter-années
# --------------------------------------------------------------------------- #
def pair(mat, a, b, method):
    s = mat[[a, b]].dropna()
    return round(s[a].corr(s[b], method=method), 3)


def block_corr(mat, years, method):
    rows = []
    for i in range(len(years)):
        for j in range(i + 1, len(years)):
            rows.append((f"{years[i]}~{years[j]}", pair(mat, years[i], years[j], method)))
    return rows


def vs_others(mat, y, method):
    return [(o, pair(mat, y, o, method)) for o in YEARS if o != y]


for name, mat in [("A charge moyenne", mean_load), ("B taux surcharge", surch_rate)]:
    print(f"\n======== RÉCURRENCE — {name} ========")
    # bloc moderne H22-H25
    bm = block_corr(mat, MODERN, "pearson")
    print("  [bloc moderne H22-H25] pearson :",
          ", ".join(f"{p}={v}" for p, v in bm),
          f"| moyenne {sum(v for _, v in bm)/len(bm):.3f}")
    # années pandémiques contre les autres
    for py in PANDEMIC:
        vo = vs_others(mat, py, "pearson")
        print(f"  [{py} vs autres] pearson :",
              ", ".join(f"{o}={v}" for o, v in vo),
              f"| moyenne {sum(v for _, v in vo)/len(vo):.3f}")
    # matrice complète 10x10 -> CSV
    cm = mat.corr(method="pearson").reindex(index=YEARS, columns=YEARS)
    cm.round(3).to_csv(OUT / f"verif_433_corr_{'A' if name.startswith('A') else 'B'}_10x10.csv")

# --------------------------------------------------------------------------- #
# 3. Saisonnalité des modulateurs (calendrier complet H16-H25)
# --------------------------------------------------------------------------- #
dim_ah = pd.read_csv(ROOT / "data/dimension/annees_horaires.csv", sep=";")
dim_ah["Debut"] = pd.to_datetime(dim_ah["Debut"], format="%d.%m.%Y", errors="coerce")
dim_ah["Fin"] = pd.to_datetime(dim_ah["Fin"], format="%d.%m.%Y", errors="coerce")
BORNES = {r.Annee: (r.Debut, r.Fin) for _, r in dim_ah.iterrows()
          if r.Annee in YEARS and pd.notna(r.Debut) and pd.notna(r.Fin)}
DEBYEAR = {y: deb.year for y, (deb, _f) in BORNES.items()}


def to_hnn_mh(dates):
    dts = pd.to_datetime(dates, errors="coerce").reset_index(drop=True)
    ah = pd.Series(pd.NA, index=dts.index, dtype="object")
    for y, (deb, fin) in BORNES.items():
        ah[(dts >= deb) & (dts <= fin)] = y
    m, yr = dts.dt.month, dts.dt.year
    mh = pd.Series(pd.NA, index=dts.index, dtype="Int64")
    nd = m.between(1, 11)
    mh[nd] = (m[nd] + 1).astype("Int64")
    dec = (m == 12)
    debyear = ah.map(DEBYEAR)
    mh[dec & (yr == debyear)] = 1
    mh[dec & (yr != debyear) & ah.notna()] = 13
    return ah.values, mh.values


def count_matrix(dates, weights=None):
    ah, mh = to_hnn_mh(dates)
    d = pd.DataFrame({"ah": ah, "mh": mh})
    d = d[d["ah"].isin(YEARS)]
    if weights is not None:
        d["w"] = pd.Series(weights).reset_index(drop=True)[d.index]
        s = d.groupby(["mh", "ah"])["w"].sum()
    else:
        s = d.groupby(["mh", "ah"]).size()
    return as_matrix(s)


# manifestations
mani = pd.read_parquet(ROOT / "data/dimension/dim_manifestations_riviera.parquet",
                       columns=["date", "is_manifestation_riviera", "n_manifestations_riviera"])
mani = mani[mani["is_manifestation_riviera"] == True].copy()
jours_manif = count_matrix(mani["date"])
n_manif = count_matrix(mani["date"], weights=mani["n_manifestations_riviera"].values)

# ski
ski = pd.read_parquet(ROOT / "data/dimension/dim_ski_pleiades.parquet",
                      columns=["date", "is_ski_ouvert"])
ski = ski[ski["is_ski_ouvert"] == True]
jours_ski = count_matrix(ski["date"])

print("\n===== MODULATEUR 1a — JOURS-MANIFESTATION — H16-H25 =====")
print(_int(jours_manif).to_string())
print("  total/an :", {y: int(jours_manif[y].fillna(0).sum()) for y in YEARS})
print("  (réf. S06 : H16 225, H17 210, H18 244, H19 310, H20 64, H21 200, H22 210, H23 211, H24 229, H25 220)")
print("\n===== MODULATEUR 1b — NOMBRE TOTAL DE MANIFESTATIONS — H16-H25 =====")
print(_int(n_manif).to_string())
print("  total/an :", {y: int(n_manif[y].fillna(0).sum()) for y in YEARS})
print("\n===== MODULATEUR 2 — JOURS D'OUVERTURE DU SKI — H16-H25 =====")
print(_int(jours_ski).to_string())
print("  total/an :", {y: int(jours_ski[y].fillna(0).sum()) for y in YEARS})
print("  (réf. S10 : H16 92, H17 86, H18 86, H19 86, H20 93, H21 92, H22 86, H23 86, H24 87, H25 86)")

# réservations (toutes les années, tous les exports)
frames = []
for f in sorted(glob.glob(str(ROOT / "data/external/reservations/export_r35_h*.xlsx"))):
    frames.append(pd.read_excel(f))
resa = pd.concat(frames, ignore_index=True)
resa["travel"] = pd.to_datetime(resa["Date de voyage"], errors="coerce")
resa["is_conf"] = resa["Statut de la réservation"].astype(str).str.contains("Abgeschlossen", na=False)
ah, mh = to_hnn_mh(resa["travel"])
resa["ah"], resa["mh"] = ah, mh
resa_m = resa[pd.Series(ah).isin(YEARS)].copy()
resa_all = as_matrix(resa_m.groupby(["mh", "ah"]).size())
resa_ab = as_matrix(resa_m[resa_m["is_conf"]].groupby(["mh", "ah"]).size())
print("\n===== MODULATEUR 3 — RÉSERVATIONS (lignes-dossiers) — H16-H25 =====")
print("--- toutes ---")
print(_int(resa_all).to_string())
print("  total/an :", {y: int(resa_all[y].fillna(0).sum()) for y in YEARS})
print("--- confirmées ---")
print(_int(resa_ab).to_string())
print("  total/an :", {y: int(resa_ab[y].fillna(0).sum()) for y in YEARS})
print("  (réf. S07 : H16 978, H17 908, H18 837, H19 956, H20 571, H21 762, H22 1036, H23 981, H24 991, H25 1105)")

# récurrence des modulateurs (bloc moderne vs années pandémiques)
print("\n======== RÉCURRENCE — modulateurs ========")
for nm, mat in [("jours-manif", jours_manif), ("jours-ski", jours_ski),
                ("résa lignes", resa_all)]:
    bm = block_corr(mat, MODERN, "pearson")
    mbm = sum(v for _, v in bm) / len(bm)
    p20 = [v for _, v in vs_others(mat, "H20", "pearson")]
    p21 = [v for _, v in vs_others(mat, "H21", "pearson")]
    print(f"  {nm:14s} H22-H25 moy={mbm:.3f} | H20 vs autres moy={sum(p20)/len(p20):.3f} "
          f"| H21 vs autres moy={sum(p21)/len(p21):.3f}")

# --------------------------------------------------------------------------- #
# Sauvegarde CSV
# --------------------------------------------------------------------------- #
mean_load.round(3).to_csv(OUT / "verif_433_matriceA_charge.csv")
surch_rate.round(3).to_csv(OUT / "verif_433_matriceB_surcharge.csv")
_int(n_obs).to_csv(OUT / "verif_433_couverture_n.csv")
_int(jours_manif).to_csv(OUT / "verif_433_mod_manif_jours.csv")
_int(n_manif).to_csv(OUT / "verif_433_mod_manif_total.csv")
_int(jours_ski).to_csv(OUT / "verif_433_mod_ski.csv")
_int(resa_all).to_csv(OUT / "verif_433_mod_resa_tous.csv")
_int(resa_ab).to_csv(OUT / "verif_433_mod_resa_abouties.csv")
print("\n[OK] CSV (H16-H25) écrits dans", OUT)
