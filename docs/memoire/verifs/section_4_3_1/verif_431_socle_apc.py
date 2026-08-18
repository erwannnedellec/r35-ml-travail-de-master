#!/usr/bin/env python3
"""Vérif §4.3.1 (socle APC) — recalcul depuis les données du dataset canonique
`ba493568` (périmètre H22-H25) et des tables APC / ISTDATEN sources.

LECTURE SEULE. Aucune valeur n'est recopiée d'un rapport antérieur : tout est
recalculé ici. Écrit trois CSV récapitulatifs à côté de ce script.

Tâche 1 — Part de la charge de 2e classe dans la charge totale
-------------------------------------------------------------
Source : data/processed/ml_dataset.parquet (dataset canonique ba493568, H22-H25).
Colonnes : target_voyageurs_2eme_classe (cible), target_voyageurs_1ere_classe,
target_voyageurs_total, spatial_segment (bas/haut), horaire_annee_horaire.
Définition : part = Σ charge 2e classe / Σ charge totale (pondérée par les
voyageurs, = agrégat de charge). Déclinée en global, par segment, par année
horaire, et par segment × année.

Tâche 2 — Couverture de mesure APC vs réalisation de l'offre (ISTDATEN)
----------------------------------------------------------------------
Référence des courses circulées CANONIQUE :
data/processed/sources/istdaten_clean.parquet (= ISTDATEN_CLEAN, écrite par
scripts/sources/build_fact_istdaten_r35.py, LUE par le pipeline, 2018→2025 ;
cf. archive/explorations/analysis/chantier_roulement/TRACAGE_DEPENDANCES_ISTDATEN.md
qui fait foi). data/processed/fact_istdaten_r35.parquet est un ORPHELIN périmé
(2021→2024-12, écrit/lu par personne) : recalculé ici uniquement pour la
réconciliation (addendum 2026-07-18). Côté mesuré : APC
data/processed/stage_01_annee_horaire.parquet (base APC, grain
course × tronçon × sens × date, colonne horaire_numero_train / base_date).

Règle d'appariement (documentée dans build_fact_istdaten_r35.py) :
croisement APC × ISTDATEN sur (date, numero_train).

Grain de la couverture : la COURSE (date, numero_train). Une course est dite
« circulée » si (numero_train non nul) et ≥1 arrêt non annulé (is_annule==False)
dans ISTDATEN. Elle est « mesurée » si (date, numero_train) est présent dans
l'APC avec une charge 2e classe non nulle. Couverture = circulées ∩ mesurées /
circulées, par année horaire.

Mapping date → année horaire : data/dimension/annees_horaires.csv (intervalles
Debut/Fin), identique au mapping du pipeline.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent

ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
STAGE_01 = ROOT / "data" / "processed" / "stage_01_annee_horaire.parquet"
# Table de réalisation ISTDATEN. CANONIQUE = istdaten_clean.parquet (ISTDATEN_CLEAN,
# écrite par build_fact_istdaten_r35.py, 2018→2025, LUE par le pipeline) ; cf.
# archive/explorations/analysis/chantier_roulement/TRACAGE_DEPENDANCES_ISTDATEN.md.
# fact_istdaten_r35.parquet est un ORPHELIN périmé (2021→2024-12, écrit/lu par personne),
# conservé ici pour la réconciliation de l'addendum 2026-07-18.
IST_CLEAN = ROOT / "data" / "processed" / "sources" / "istdaten_clean.parquet"
FACT_IST_ORPHELIN = ROOT / "data" / "processed" / "fact_istdaten_r35.parquet"
ANNEES_HORAIRES = ROOT / "data" / "dimension" / "annees_horaires.csv"

ANNEES_ML = ["H22", "H23", "H24", "H25"]


# ---------------------------------------------------------------------------
# Mapping année horaire
# ---------------------------------------------------------------------------
def charger_intervalles_ah() -> pd.DataFrame:
    ah = pd.read_csv(ANNEES_HORAIRES, sep=";", parse_dates=["Debut", "Fin"],
                     dayfirst=True)
    return ah.dropna(subset=["Debut", "Fin"]).sort_values("Debut").reset_index(drop=True)


def mapper_annee_horaire(dates: pd.Series, ah: pd.DataFrame) -> pd.Series:
    """Assigne l'année horaire par intervalle Debut<=date<=Fin (borne incluse)."""
    d = pd.to_datetime(dates)
    out = pd.Series(pd.NA, index=d.index, dtype="object")
    for _, row in ah.iterrows():
        m = (d >= row["Debut"]) & (d <= row["Fin"])
        out[m] = row["Annee"]
    return out


# ---------------------------------------------------------------------------
# Tâche 1
# ---------------------------------------------------------------------------
def tache1() -> pd.DataFrame:
    df = pd.read_parquet(ML_DATASET, columns=[
        "target_voyageurs_1ere_classe", "target_voyageurs_2eme_classe",
        "target_voyageurs_total", "spatial_segment", "horaire_annee_horaire"])
    for c in ["target_voyageurs_1ere_classe", "target_voyageurs_2eme_classe",
              "target_voyageurs_total"]:
        df[c] = df[c].astype("float64")

    print("=" * 78)
    print("TÂCHE 1 — Part de la charge 2e classe dans la charge totale")
    print("Source :", ML_DATASET.relative_to(ROOT))
    print("=" * 78)
    print(f"Lignes (tronçons) : {len(df):,}")
    nan_2c = int(df["target_voyageurs_2eme_classe"].isna().sum())
    nan_tot = int(df["target_voyageurs_total"].isna().sum())
    print(f"NaN charge 2e classe : {nan_2c} | NaN charge totale : {nan_tot}")
    # Contrôle identité total == 1ere + 2eme
    recompose = df["target_voyageurs_1ere_classe"] + df["target_voyageurs_2eme_classe"]
    ecart_max = float((df["target_voyageurs_total"] - recompose).abs().max())
    print(f"Contrôle total == 1re+2e : écart max = {ecart_max:g}")

    def part(sub: pd.DataFrame) -> pd.Series:
        s2 = sub["target_voyageurs_2eme_classe"].sum()
        s1 = sub["target_voyageurs_1ere_classe"].sum()
        st = sub["target_voyageurs_total"].sum()
        return pd.Series({
            "n_troncons": len(sub),
            "somme_charge_1re": s1,
            "somme_charge_2e": s2,
            "somme_charge_totale": st,
            "part_2e_pct": 100.0 * s2 / st if st else float("nan"),
        })

    lignes = []
    g = part(df); g.name = ("global", "global"); lignes.append(g)
    for seg in ["bas", "haut"]:
        r = part(df[df["spatial_segment"] == seg]); r.name = ("segment", seg)
        lignes.append(r)
    for ah_ in ANNEES_ML:
        r = part(df[df["horaire_annee_horaire"] == ah_]); r.name = ("annee", ah_)
        lignes.append(r)
    for seg in ["bas", "haut"]:
        for ah_ in ANNEES_ML:
            sub = df[(df["spatial_segment"] == seg) & (df["horaire_annee_horaire"] == ah_)]
            r = part(sub); r.name = ("segment_x_annee", f"{seg}_{ah_}")
            lignes.append(r)

    res = pd.DataFrame(lignes)
    res.index = pd.MultiIndex.from_tuples(res.index, names=["decoupage", "modalite"])
    res = res.reset_index()
    for c in ["somme_charge_1re", "somme_charge_2e", "somme_charge_totale"]:
        res[c] = res[c].astype("int64")
    res["part_2e_pct"] = res["part_2e_pct"].round(3)
    print()
    print(res.to_string(index=False))
    return res


# ---------------------------------------------------------------------------
# Tâche 2
# ---------------------------------------------------------------------------
def charger_apc() -> tuple[set, set]:
    """Côté APC (mesuré) : jours couverts et ensemble des courses mesurées."""
    apc = pd.read_parquet(STAGE_01, columns=[
        "base_date", "horaire_numero_train", "target_voyageurs_2eme_classe"])
    apc["date"] = pd.to_datetime(apc["base_date"]).dt.normalize()
    apc["train"] = pd.to_numeric(apc["horaire_numero_train"], errors="coerce").astype("Int64")
    apc_dates = set(apc["date"].unique())  # jours avec ≥1 mesure APC
    apc_meas = apc[apc["target_voyageurs_2eme_classe"].notna() & apc["train"].notna()]
    apc_meas_set = set(map(tuple, apc_meas[["date", "train"]].drop_duplicates().to_numpy()))
    return apc_dates, apc_meas_set


def couverture(ist_path: Path, label: str, apc_dates: set, apc_meas_set: set
               ) -> tuple[pd.DataFrame, pd.DataFrame]:
    ah = charger_intervalles_ah()

    # --- Côté ISTDATEN (circulé) ---
    ist = pd.read_parquet(ist_path, columns=["date", "numero_train", "is_annule",
                                             "is_supplementaire"])
    ist["date"] = pd.to_datetime(ist["date"]).dt.normalize()
    ist["train"] = pd.to_numeric(ist["numero_train"], errors="coerce").astype("Int64")
    ist["annee_horaire"] = mapper_annee_horaire(ist["date"], ah)

    print("\n" + "=" * 78)
    print(f"TÂCHE 2 [{label}] — Couverture de mesure APC vs réalisation ISTDATEN")
    print("Référence circulées :", ist_path.relative_to(ROOT))
    print("APC (mesuré)        :", STAGE_01.relative_to(ROOT))
    print("Règle d'appariement : (date, numero_train)")
    print("=" * 78)
    print(f"ISTDATEN lignes (date×train×arrêt) : {len(ist):,}")
    print(f"ISTDATEN date min/max : {ist['date'].min().date()} → {ist['date'].max().date()}")
    n_nan_train = int(ist["train"].isna().sum())
    print(f"Lignes numero_train NaN (non appariables) : {n_nan_train} "
          f"({100*n_nan_train/len(ist):.3f} %)")

    # Agrégat au grain course (date, train)
    ist_notna = ist[ist["train"].notna()].copy()
    grp = ist_notna.groupby(["date", "train"], observed=True)
    course = pd.DataFrame({
        "n_arrets": grp.size(),
        "n_non_annules": grp["is_annule"].apply(lambda s: int((~s).sum())),
        "is_suppl": grp["is_supplementaire"].max(),
    }).reset_index()
    course["annee_horaire"] = mapper_annee_horaire(course["date"], ah)
    course["circule"] = course["n_non_annules"] > 0
    course["mesure"] = [
        (d, t) in apc_meas_set for d, t in zip(course["date"], course["train"])
    ]
    course["jour_apc_present"] = course["date"].isin(apc_dates)

    # ---- Couverture par année horaire ----
    rows = []
    for ah_ in ANNEES_ML:
        sub = course[course["annee_horaire"] == ah_]
        circ = sub[sub["circule"]]
        n_circ = len(circ)
        n_meas = int(circ["mesure"].sum())
        # bornes de couverture ISTDATEN pour cette année
        deb = ah.loc[ah["Annee"] == ah_, "Debut"].iloc[0]
        fin = ah.loc[ah["Annee"] == ah_, "Fin"].iloc[0]
        jours_ah = (fin - deb).days + 1
        jours_ist = sub["date"].nunique()
        rows.append({
            "annee_horaire": ah_,
            "ist_debut": deb.date(), "ist_fin": fin.date(),
            "jours_annee_horaire": jours_ah,
            "jours_ist_presents": jours_ist,
            "courses_circulees": n_circ,
            "courses_mesurees_apc": n_meas,
            "couverture_pct": round(100.0 * n_meas / n_circ, 2) if n_circ else float("nan"),
        })
    cov = pd.DataFrame(rows)
    print("\n--- Couverture par année horaire ---")
    print(cov.to_string(index=False))

    # ---- Typologie des non-appariements (courses circulées non mesurées) ----
    typo_rows = []
    for ah_ in ANNEES_ML:
        sub = course[course["annee_horaire"] == ah_]
        circ = sub[sub["circule"]]
        non_mes = circ[~circ["mesure"]]
        b_gap = int((~non_mes["jour_apc_present"]).sum())   # jour sans aucune mesure APC
        c_train = int(non_mes["jour_apc_present"].sum())     # jour couvert, train non mesuré
        n_annulees = int((~sub["circule"]).sum())            # courses entièrement annulées
        n_suppl = int(circ["is_suppl"].sum())
        typo_rows.append({
            "annee_horaire": ah_,
            "circulees": int(circ.shape[0]),
            "non_mesurees_total": int(non_mes.shape[0]),
            "cause_jour_sans_apc": b_gap,
            "cause_train_non_mesure_jour_couvert": c_train,
            "ref_courses_entierement_annulees": n_annulees,
            "ref_courses_supplementaires": n_suppl,
        })
    typo = pd.DataFrame(typo_rows)
    print("\n--- Typologie des causes de non-appariement (courses circulées non mesurées) ---")
    print(typo.to_string(index=False))
    # Représentativité : une année n'est vérifiable que si la référence ISTDATEN couvre
    # ~toute la période de l'année horaire (seuil 95 % des jours calendaires).
    cov["representatif"] = cov["jours_ist_presents"] >= 0.95 * cov["jours_annee_horaire"]
    ref_fin = ist["date"].max().date()
    for _, r in cov.iterrows():
        if not r["representatif"]:
            print(f"\nNote {r['annee_horaire']} : réf. ISTDATEN ({ist_path.name}) s'arrête au "
                  f"{ref_fin} ; seuls {r['jours_ist_presents']}/{r['jours_annee_horaire']} jours "
                  f"présents → couverture NON REPRÉSENTATIVE (référence tronquée).")
    return cov, typo


def main() -> None:
    res1 = tache1()
    apc_dates, apc_meas_set = charger_apc()

    # Table CANONIQUE de réalisation (istdaten_clean, 2018→2025) : source de vérité.
    cov, typo = couverture(IST_CLEAN, "CANONIQUE istdaten_clean", apc_dates, apc_meas_set)
    # Table ORPHELINE périmée (fact_istdaten_r35, 2021→2024-12) : pour réconciliation.
    cov_o, _ = couverture(FACT_IST_ORPHELIN, "ORPHELIN fact_istdaten_r35", apc_dates, apc_meas_set)

    # ---- Réconciliation canonique vs orphelin ----
    recon = cov[["annee_horaire", "courses_circulees", "courses_mesurees_apc",
                 "couverture_pct"]].merge(
        cov_o[["annee_horaire", "courses_circulees", "courses_mesurees_apc",
               "couverture_pct"]],
        on="annee_horaire", suffixes=("_canonique", "_orphelin"))
    recon["delta_couverture_pts"] = (recon["couverture_pct_canonique"]
                                     - recon["couverture_pct_orphelin"]).round(2)
    print("\n" + "=" * 78)
    print("RÉCONCILIATION — canonique (istdaten_clean) vs orphelin (fact_istdaten_r35)")
    print("=" * 78)
    print(recon.to_string(index=False))

    res1.to_csv(DOSSIER / "verif_431_task1_charge_2c.csv", index=False, encoding="utf-8-sig")
    cov.to_csv(DOSSIER / "verif_431_task2_couverture.csv", index=False, encoding="utf-8-sig")
    typo.to_csv(DOSSIER / "verif_431_task2_typologie.csv", index=False, encoding="utf-8-sig")
    recon.to_csv(DOSSIER / "verif_431_task2_reconciliation.csv", index=False, encoding="utf-8-sig")
    print("\nCSV écrits dans", DOSSIER.relative_to(ROOT))


if __name__ == "__main__":
    main()
