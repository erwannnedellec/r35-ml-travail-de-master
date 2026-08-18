#!/usr/bin/env python3
"""
V2 — Concurrence modale VMCV : construction reelle et grain de portage.

Question directe : la valeur d'une variable `vmcv_` varie-t-elle d'un troncon a
l'autre au sein d'une meme course, ou est-elle constante sur la course ?

Lecture seule sur le jeu canonique ba493568. Aucune reconstruction de dimension.

Sorties : docs/memoire/verifs/complements/v2_vmcv_*.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _garde import ROOT, garde  # noqa: E402

OUT = Path(__file__).resolve().parent
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
DIM_TRAIN_JOUR = ROOT / "data" / "processed" / "sources" / "dim_vmcv_par_train_jour.parquet"

# Cle de course telle qu'utilisee par la jointure VMCV
# (scripts/pipeline/add_istdaten_to_raw_stacked.py:217-219).
CLE_COURSE = ["base_date", "horaire_numero_train", "base_sens"]
# Cle de troncon canonique (ADR-062 : troncon dans la cle des histo_*).
CLE_TRONCON = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]


def main() -> None:
    garde()
    print("=" * 78)
    print("V2 — VARIABLES vmcv_ : GRAIN DE CALCUL ET GRAIN DE PORTAGE")
    print("=" * 78)

    schema = pq.ParquetFile(ML_DATASET).schema_arrow
    cols_vmcv = [c for c in schema.names if c.startswith("vmcv_")]
    print(f"\n[1] Colonnes prefixees vmcv_ dans ml_dataset.parquet : {len(cols_vmcv)}")
    for c in cols_vmcv:
        print(f"    {c}")

    # Dimension amont : grain de calcul declare
    dim = pd.read_parquet(DIM_TRAIN_JOUR)
    print(f"\n[2] Dimension amont : {DIM_TRAIN_JOUR.relative_to(ROOT)}")
    print(f"    {len(dim)} lignes, colonnes : {list(dim.columns)}")
    grain_dim = ["date", "numero_train", "sens"]
    n_uniq = len(dim.drop_duplicates(grain_dim))
    print(f"    unicite sur (date, numero_train, sens) : {n_uniq}/{len(dim)} "
          f"-> {'CLE' if n_uniq == len(dim) else 'NON UNIQUE'}")

    # Chargement du jeu canonique, colonnes utiles seulement
    besoin = CLE_COURSE + CLE_TRONCON + cols_vmcv + ["horaire_annee_horaire"]
    df = pd.read_parquet(ML_DATASET, columns=besoin)
    print(f"\n[3] Jeu canonique : {len(df)} observations (grain course x troncon x date)")

    # ── Test central : variation intra-course ─────────────────────────────────
    print("\n[4] Variation des vmcv_ AU SEIN d'une meme course")
    print("    (une course = (base_date, horaire_numero_train, base_sens))")
    g = df.groupby(CLE_COURSE, sort=False, dropna=False)
    n_courses = g.ngroups
    n_multi = int((g.size() >= 2).sum())
    print(f"    courses totales                        : {n_courses}")
    print(f"    courses a >= 2 troncons (testables)    : {n_multi}")

    lignes = []
    for c in cols_vmcv:
        if not pd.api.types.is_numeric_dtype(df[c]):
            # colonnes de provenance (vmcv_source_*) : test sur les modalites
            nun = g[c].nunique(dropna=False)
        else:
            nun = g[c].nunique(dropna=False)
        testables = g.size() >= 2
        n_var = int((nun[testables] > 1).sum())
        n_cst = int((nun[testables] <= 1).sum())
        lignes.append({
            "colonne": c,
            "dtype": str(df[c].dtype),
            "courses_testables": int(testables.sum()),
            "courses_ou_la_valeur_varie": n_var,
            "courses_ou_la_valeur_est_constante": n_cst,
            "part_courses_variantes_pct": round(100 * n_var / max(1, int(testables.sum())), 6),
            "taux_nan_pct": round(100 * float(df[c].isna().mean()), 4),
        })
    res = pd.DataFrame(lignes)
    res.to_csv(OUT / "v2_vmcv_variation_intra_course.csv", index=False)
    print("\n" + res[["colonne", "courses_testables", "courses_ou_la_valeur_varie",
                      "part_courses_variantes_pct", "taux_nan_pct"]].to_string(index=False))

    # ── Contre-epreuve : variation intra-(troncon, date) ──────────────────────
    print("\n[5] Contre-epreuve : les vmcv_ varient-elles au sein d'un (troncon, date) ?")
    print("    (si oui, elles portent bien une information de course, pas de troncon)")
    g2 = df.groupby(CLE_TRONCON + ["base_date"], sort=False, dropna=False)
    lignes2 = []
    for c in cols_vmcv:
        nun = g2[c].nunique(dropna=False)
        testables = g2.size() >= 2
        n_var = int((nun[testables] > 1).sum())
        lignes2.append({
            "colonne": c,
            "couples_troncon_date_testables": int(testables.sum()),
            "couples_ou_la_valeur_varie": n_var,
            "part_couples_variants_pct": round(100 * n_var / max(1, int(testables.sum())), 4),
        })
    res2 = pd.DataFrame(lignes2)
    res2.to_csv(OUT / "v2_vmcv_variation_intra_troncon_date.csv", index=False)
    print("\n" + res2.to_string(index=False))

    # ── Effectifs par annee horaire (couverture) ──────────────────────────────
    print("\n[6] Couverture par annee horaire (taux de NaN)")
    cols_num = [c for c in cols_vmcv if pd.api.types.is_numeric_dtype(df[c])]
    cov = (df.groupby("horaire_annee_horaire")[cols_num]
             .apply(lambda s: 100 * s.isna().mean()).round(3))
    cov["n_observations"] = df.groupby("horaire_annee_horaire").size()
    cov.to_csv(OUT / "v2_vmcv_couverture_par_annee.csv")
    print(cov.to_string())

    # ── Decalage J-2 de la jointure ───────────────────────────────────────────
    print("\n[7] Decalage temporel de la jointure (add_istdaten_to_raw_stacked.py:211)")
    print("    La dimension calculee au jour d est rattachee aux observations du jour d+2.")
    dim2 = dim.copy()
    dim2["base_date"] = pd.to_datetime(dim2["date"]) + pd.Timedelta(days=2)
    dim2 = dim2.rename(columns={"numero_train": "horaire_numero_train", "sens": "base_sens"})
    cle_num = [c for c in cols_vmcv if pd.api.types.is_numeric_dtype(df[c])]
    obs = (df.drop_duplicates(CLE_COURSE)[CLE_COURSE + cle_num]
             .assign(base_date=lambda t: pd.to_datetime(t["base_date"])))
    dim2["horaire_numero_train"] = dim2["horaire_numero_train"].astype(str)
    obs["horaire_numero_train"] = obs["horaire_numero_train"].astype("Int64").astype(str)
    j = obs.merge(dim2[["base_date", "horaire_numero_train", "base_sens"] + cle_num],
                  on=["base_date", "horaire_numero_train", "base_sens"],
                  how="inner", suffixes=("_obs", "_dim"))
    print(f"    courses appariees a la dimension decalee de +2 j : {len(j)} / {len(obs)}")
    ident = []
    for c in cle_num:
        a, b = j[f"{c}_obs"], j[f"{c}_dim"]
        eg = int(((a == b) | (a.isna() & b.isna())).sum())
        ident.append({"colonne": c, "courses_comparees": len(j), "valeurs_identiques": eg,
                      "part_identique_pct": round(100 * eg / max(1, len(j)), 4)})
    idf = pd.DataFrame(ident)
    idf.to_csv(OUT / "v2_vmcv_controle_decalage_j2.csv", index=False)
    print(idf.to_string(index=False))

    # ── Verdict ───────────────────────────────────────────────────────────────
    print("\n[8] Verdict")
    varie_qqpart = res[res["courses_ou_la_valeur_varie"] > 0]
    if varie_qqpart.empty:
        print("    AUCUNE variable vmcv_ ne varie d'un troncon a l'autre au sein d'une course :")
        print("    la valeur est CONSTANTE sur toute la course, sur les "
              f"{n_multi} courses a plusieurs troncons.")
    else:
        print("    Variables variant au sein d'une course :")
        print(varie_qqpart.to_string(index=False))
    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
