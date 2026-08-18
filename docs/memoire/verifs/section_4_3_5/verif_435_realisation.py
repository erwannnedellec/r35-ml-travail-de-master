#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verif_435_realisation.py
========================
Vérifications en LECTURE SEULE pour la section 4.3.5 (réalisation de l'offre / ISTDATEN).
Aucune écriture dans scripts/, data/, ni dans les parquets sources. Ce script ne fait que
lire les tables canoniques du dépôt, recalculer quatre grandeurs, et écrire ses propres
sorties `verif_435_*.csv` + un récapitulatif console.

Empreinte attendue du dataset canonique : ml_dataset.parquet SHA256[:8] = ba493568 (gel v2, ADR-076).

Tâches
------
  T1  Refonte H24→H25 : nombre de trains renumérotés (attendu 52) et part des observations
      H25 portant un numéro nouveau. Deux mesures : (A) roster strict numero_train ;
      (B) mesure opérationnelle « match SIMBA 2024 » (simba_source_depart, ADR-041).
  T2  Inventaire de la famille régularité/correspondances (préfixe ist_) dans les 158 features :
      liste, mesure, source exacte (docstrings des build_dim_*).
  T3  Rappel de l'exploration committée liant retard/correspondances à la charge
      (notebook 02 §5, Spearman ist_* vs target) — résumé des chiffres.
  T4  Latence d'horodatage ISTDATEN par année horaire H18→H25 (part des enregistrements
      avec horodatage réel), reproduisant la définition de la matrice de couverture 4.4.1.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
PROC = ROOT / "data" / "processed"
DIM = ROOT / "data" / "dimension"
OUT = Path(__file__).resolve().parent

ML = PROC / "ml_dataset.parquet"
IST_CLEAN = PROC / "sources" / "istdaten_clean.parquet"   # source canonique (2018→2025), PAS l'orphelin fact_istdaten_r35
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
SPEARMAN = ROOT / "notebooks" / "figures" / "02_data_understanding_istdaten_qualite" / "05_spearman_utilite_predictive.csv"
ANNEES = DIM / "annees_horaires.csv"

YEARS = [f"H{n}" for n in range(18, 26)]


def check_hash() -> str:
    h = hashlib.sha256(ML.read_bytes()).hexdigest()[:8]
    print(f"[hash] ml_dataset.parquet SHA256[:8] = {h}  (attendu ba493568)"
          f"  -> {'OK' if h == 'ba493568' else 'DIVERGENCE'}")
    return h


def bornes_horaires():
    dim = pd.read_csv(ANNEES, sep=";")
    dim["Debut"] = pd.to_datetime(dim["Debut"], format="%d.%m.%Y", errors="coerce")
    dim["Fin"] = pd.to_datetime(dim["Fin"], format="%d.%m.%Y", errors="coerce")
    return [(r.Annee, r.Debut, r.Fin) for _, r in dim.iterrows()
            if pd.notna(r.Debut) and pd.notna(r.Fin)]


def to_hnn(dates, bornes):
    s = pd.to_datetime(dates, errors="coerce")
    out = pd.Series(pd.NA, index=s.index, dtype="object")
    for annee, deb, fin in bornes:
        out[(s >= deb) & (s <= fin)] = annee
    return out


# --------------------------------------------------------------------------------------
# T1 — Renumérotation H24 → H25
# --------------------------------------------------------------------------------------
def t1_renumerotation():
    print("\n" + "=" * 78)
    print("T1 — Refonte d'horaire H24 → H25 : trains renumérotés")
    print("=" * 78)
    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "horaire_numero_train",
                                      "simba_source_depart"])
    h24 = df[df["horaire_annee_horaire"] == "H24"]
    h25 = df[df["horaire_annee_horaire"] == "H25"]
    t24 = set(h24["horaire_numero_train"].dropna().unique())
    t25 = set(h25["horaire_numero_train"].dropna().unique())
    maintenus = t25 & t24
    nouveaux = t25 - t24            # numéro présent en H25, absent de H24
    disparus = t24 - t25            # numéro présent en H24, absent de H25 = renuméroté / retiré
    n25 = len(h25)
    obs_nouv = int(h25["horaire_numero_train"].isin(nouveaux).sum())

    # Mesure opérationnelle ADR-041 : match SIMBA 2024 (millésime N-1)
    src = h25["simba_source_depart"].astype(str)
    manquant = src.str.contains("manquant", na=False)

    print("(A) Roster strict numero_train (grain course) :")
    print(f"    H24 numéros distincts : {len(t24)}   |   H25 numéros distincts : {len(t25)}")
    print(f"    maintenus (H25 ∩ H24)                    : {len(maintenus)}")
    print(f"    DISPARUS de H24 (renumérotés/retirés)    : {len(disparus)}   [attendu ~52]")
    print(f"    nouveaux en H25 (absents de H24)         : {len(nouveaux)}")
    print(f"    part obs H25 à numéro NOUVEAU            : {obs_nouv}/{n25} = {100*obs_nouv/n25:.1f}%")
    print("(B) Mesure opérationnelle SIMBA 2024 (simba_source_depart, ADR-041) :")
    print(f"    manquant_simba_n_minus_1 (renuméroté)   : {int(manquant.sum())}/{n25} = "
          f"{100*manquant.mean():.1f}%")
    print(f"    match_simba_n_minus_1 (maintenu)        : {int((~manquant).sum())}/{n25} = "
          f"{100*(~manquant).mean():.1f}%")

    rows = [
        {"mesure": "H24_numeros_distincts", "valeur": len(t24), "pct_obs_H25": ""},
        {"mesure": "H25_numeros_distincts", "valeur": len(t25), "pct_obs_H25": ""},
        {"mesure": "maintenus_H25interH24", "valeur": len(maintenus), "pct_obs_H25": ""},
        {"mesure": "disparus_H24_renumerotes", "valeur": len(disparus), "pct_obs_H25": ""},
        {"mesure": "nouveaux_H25", "valeur": len(nouveaux), "pct_obs_H25": ""},
        {"mesure": "obs_H25_numero_nouveau", "valeur": obs_nouv,
         "pct_obs_H25": round(100 * obs_nouv / n25, 1)},
        {"mesure": "obs_H25_manquant_simba2024", "valeur": int(manquant.sum()),
         "pct_obs_H25": round(100 * manquant.mean(), 1)},
        {"mesure": "obs_H25_total", "valeur": n25, "pct_obs_H25": 100.0},
    ]
    pd.DataFrame(rows).to_csv(OUT / "verif_435_task1_renumerotation.csv", index=False)


# --------------------------------------------------------------------------------------
# T2 — Inventaire famille régularité/correspondances (ist_) dans les 158
# --------------------------------------------------------------------------------------
def t2_inventaire_ist():
    print("\n" + "=" * 78)
    print("T2 — Famille régularité/correspondances (ist_) dans les 158 features")
    print("=" * 78)
    cb = pd.read_csv(CODEBOOK)
    ist = cb[(cb["famille"] == "ist_") & (cb["dans_158_features"])].copy()

    def sous_famille(col: str) -> str:
        if col.startswith("ist_profil_train"):
            return "1_retard_profil_train"
        if col.startswith("ist_corresp"):
            return "2_correspondances_vevey"
        if col.startswith("ist_headway"):
            return "3_headway"
        return "autre"

    ist["sous_famille"] = ist["colonne"].map(sous_famille)
    src_map = {
        "1_retard_profil_train": "ISTDATEN (istdaten_clean.parquet) via build_dim_profil_train.py",
        "2_correspondances_vevey": "ISTDATEN (istdaten_clean.parquet) via build_dim_correspondances_vevey.py",
        "3_headway": "ISTDATEN horaire THÉORIQUE (istdaten_clean.parquet) via build_dim_headway.py",
    }
    ist["source_exacte"] = ist["sous_famille"].map(src_map)
    print(f"Total famille ist_ dans les 158 : {len(ist)}")
    print(ist["sous_famille"].value_counts().sort_index().to_string())
    ist[["colonne", "sous_famille", "source", "source_exacte", "taux_nan_pct", "libelle_fr"]] \
        .sort_values(["sous_famille", "colonne"]) \
        .to_csv(OUT / "verif_435_task2_famille_ist.csv", index=False)


# --------------------------------------------------------------------------------------
# T3 — Exploration committée retard/correspondances ↔ charge
# --------------------------------------------------------------------------------------
def t3_exploration_charge():
    print("\n" + "=" * 78)
    print("T3 — Exploration committée : ist_* (retard/corresp) vs charge (target)")
    print("=" * 78)
    if not SPEARMAN.exists():
        print("  CSV spearman introuvable :", SPEARMAN)
        return
    sp = pd.read_csv(SPEARMAN)
    print(f"  Source : {SPEARMAN.relative_to(ROOT)}  ({len(sp)} lignes, 28 features × 4 années)")
    # extrema par sous-famille sur H24 (année la plus riche en retard réel)
    sp["absr"] = sp["spearman_r"].abs()
    for yr in ["H24", "H25"]:
        sub = sp[sp["annee"] == yr].dropna(subset=["spearman_r"])
        retard = sub[sub["feature"].str.startswith("ist_profil_train_retard")]
        corr = sub[sub["feature"].str.startswith("ist_corresp")]
        head = sub[sub["feature"].str.startswith("ist_headway")]
        def top(g):
            r = g.loc[g["absr"].idxmax()]
            return f'{r["feature"]} r_s={r["spearman_r"]:+.3f}'
        print(f"  [{yr}] max|r_s| retard      : {top(retard) if len(retard) else 'n/a'}")
        print(f"       max|r_s| corresp     : {top(corr) if len(corr) else 'n/a'}")
        print(f"       max|r_s| headway     : {top(head) if len(head) else 'n/a'}")


# --------------------------------------------------------------------------------------
# T4 — Latence d'horodatage ISTDATEN par année horaire H18→H25
# --------------------------------------------------------------------------------------
def t4_latence():
    print("\n" + "=" * 78)
    print("T4 — Latence d'horodatage ISTDATEN H18→H25 (part avec horodatage réel)")
    print("=" * 78)
    bornes = bornes_horaires()
    ist = pd.read_parquet(IST_CLEAN, columns=["date", "numero_train", "reel_depart",
                                              "statut_depart"])
    ist["h"] = to_hnn(ist["date"], bornes)
    ist = ist[ist["h"].isin(YEARS)].copy()
    ist["has_reel"] = ist["reel_depart"].notna()

    # grain enregistrement-arrêt (mesure canonique de la matrice 4.4.1)
    rows = []
    print(f"  {'année':6s} {'n_arrêts':>10s} {'réel(arrêt)':>12s} {'statut=REAL':>12s} "
          f"{'réel(course≥50%)':>18s}")
    g = ist.groupby(["h", "date", "numero_train"])["has_reel"].mean()
    for a in YEARS:
        sub = ist[ist["h"] == a]
        n = len(sub)
        p_arret = float(sub["has_reel"].mean()) if n else float("nan")
        p_real = float((sub["statut_depart"].astype(str).str.upper() == "REAL").mean()) if n else float("nan")
        gc = g.loc[a] if a in g.index.get_level_values(0) else pd.Series(dtype=float)
        p_course = float((gc >= 0.5).mean()) if len(gc) else float("nan")
        rows.append({"annee": a, "n_arrets": n, "pct_reel_arret": round(100 * p_arret, 1),
                     "pct_statut_real": round(100 * p_real, 1),
                     "pct_course_maj_reel": round(100 * p_course, 1)})
        print(f"  {a:6s} {n:>10d} {100*p_arret:>11.1f}% {100*p_real:>11.1f}% {100*p_course:>17.1f}%")
    pd.DataFrame(rows).to_csv(OUT / "verif_435_task4_latence_ist.csv", index=False)


def main():
    print("Vérifications section 4.3.5 — réalisation de l'offre (ISTDATEN)")
    check_hash()
    t1_renumerotation()
    t2_inventaire_ist()
    t3_exploration_charge()
    t4_latence()
    print("\nSorties écrites dans", OUT)


if __name__ == "__main__":
    main()
