#!/usr/bin/env python3
"""
V1 — Reconstruction de la corrélation inter-millésimes des proportions SIMBA.

Le manuscrit (§4.5.4) et l'ADR-061 §1 annoncent r = 0,056 sur `simba_part_ga` entre les
millésimes SIMBA 2023 et 2024, « sur les courses comparables ». Aucun script du dépôt ne
produisait cette valeur (constat de l'audit A3). Ce script la reconstruit.

LECTURE SEULE. N'écrit que sous docs/memoire/verifs/section_4_5/.

DÉFINITIONS DE « COURSES COMPARABLES » — cinq variantes, toutes rapportées
  D1  dim / (train, tronçon) / 52 trains conservés  ... grain (numéro de train, tronçon non
        orienté), profils lus dans dim_simba_r35, restreints aux numéros de train qui
        circulent en H25 ET y portent un profil SIMBA 2024
  D2  ml_dataset / (train, tronçon) / 52 trains ... même chose reconstruit depuis
        ml_dataset.parquet (donc limité aux tronçons effectivement observés par l'APC)
  D3  dim / (train, tronçon) / tous trains communs aux deux millésimes (aucune restriction)
  D4  dim / (train) / 52 trains ......... profil moyenné sur les tronçons de la course
  D5  ml_dataset / observation .......... toutes les lignes H24 et H25 appariées par
        (train, tronçon), chaque paire pondérée par son nombre de jours d'observation

Le rattachement millésime → année horaire suit la règle de jointure ADR-026 (lag N-1)
implémentée par scripts/pipeline/add_simba_to_raw_stacked.py :
    H23 → SIMBA 2022 · H24 → SIMBA 2023 · H25 → SIMBA 2024
Le tronçon est normalisé (min, max) des deux gares : la dimension SIMBA ne contient que le
sens ascendant et la jointure du pipeline est direction-agnostique.

Sorties :
  - v1_simba_correlations.csv      une ligne par (définition, paire de millésimes, colonne)
  - v1_simba_agregats.csv          statistique agrégée par (définition, paire)
  - v1_simba_correlation.json      synthèse machine + confrontation à l'ADR-061

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/v1_simba_correlation_millesimes.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ML = ROOT / "data/processed/ml_dataset.parquet"
DIM = ROOT / "data/dimension/dim_simba_r35.parquet"
HASH_ATTENDU = "ba493568"

SIM = ["simba_part_ga", "simba_part_mobilis", "simba_part_billet_hta", "simba_part_spar",
       "simba_part_jeunes", "simba_part_abonnement", "simba_part_militaire",
       "simba_part_autre", "simba_part_corresp_amont", "simba_part_corresp_aval",
       "simba_part_premiere_classe", "simba_part_intra_r35"]

# Année horaire → millésime SIMBA (ADR-026, lag N-1 ; H22 → 2021 absent)
HORAIRE_VERS_MILLESIME = {"H23": 2022, "H24": 2023, "H25": 2024}

# Valeurs annoncées par ADR-061 §1 (9 colonnes sur 12 ; r puis MAE)
ADR_061 = {
    "simba_part_ga": (0.056, 0.127), "simba_part_billet_hta": (0.138, 0.089),
    "simba_part_spar": (0.124, 0.030), "simba_part_jeunes": (0.023, 0.053),
    "simba_part_intra_r35": (0.331, 0.236), "simba_part_premiere_classe": (0.537, 0.038),
    "simba_part_corresp_amont": (0.658, 0.112), "simba_part_corresp_aval": (0.724, 0.137),
    "simba_part_mobilis": (0.752, 0.138),
}
TOL = 0.001   # tolérance de reproduction : les valeurs de l'ADR sont à 3 décimales


def sha8(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]


def troncon_norm(g1, g2):
    """Clé de tronçon NON ORIENTÉE, miroir de _simba_gare_min/_simba_gare_max du pipeline."""
    a, b = g1.astype(str), g2.astype(str)
    return np.where(a < b, a + "|" + b, b + "|" + a)


def profils_dim():
    """Profils (millésime, train, tronçon) lus dans dim_simba_r35."""
    d = pd.read_parquet(DIM)
    d["tr"] = troncon_norm(d["gare_depart"], d["gare_arrivee"])
    d = d.rename(columns={"simba_numero_train": "train", "simba_millesime": "mill"})
    return d[["mill", "train", "tr"] + SIM]


def profils_ml(df):
    """Profils (millésime, train, tronçon) reconstruits depuis ml_dataset, + poids en jours."""
    d = df[df["horaire_annee_horaire"].isin(HORAIRE_VERS_MILLESIME)].copy()
    d["mill"] = d["horaire_annee_horaire"].map(HORAIRE_VERS_MILLESIME)
    d["tr"] = troncon_norm(d["id_gare_depart"], d["id_gare_arrivee"])
    d = d.rename(columns={"horaire_numero_train": "train"})
    d = d.dropna(subset=["simba_part_ga"])
    cle = ["mill", "train", "tr"]
    # garde : un profil est constant sur toutes les lignes d'un (millésime, train, tronçon)
    nu = d.groupby(cle)[SIM].nunique()
    if int((nu > 1).sum().sum()) != 0:
        raise RuntimeError("STOP : profil SIMBA non constant au sein d'un (millésime, train, tronçon)")
    p = d.groupby(cle)[SIM].first().reset_index()
    poids = d.groupby(cle)["base_date"].nunique().rename("n_jours").reset_index()
    return p.merge(poids, on=cle)


def stats_paire(j, poids=None):
    """Pearson, Spearman, MAE, n pour chacune des 12 colonnes, sur un appariement déjà fait."""
    out = []
    for c in SIM:
        x = j[c + "_1"].astype("float64").values
        y = j[c + "_2"].astype("float64").values
        w = None if poids is None else j[poids].astype("float64").values
        ok = ~(np.isnan(x) | np.isnan(y))
        x, y = x[ok], y[ok]
        wo = None if w is None else w[ok]
        n = int(ok.sum())
        r = rho = mae = np.nan
        if n > 2 and np.std(x) > 0 and np.std(y) > 0:
            if wo is None:
                r = float(pearsonr(x, y)[0])
                rho = float(spearmanr(x, y).statistic)
                mae = float(np.mean(np.abs(x - y)))
            else:                                    # variante pondérée (D5)
                mx = np.average(x, weights=wo); my = np.average(y, weights=wo)
                cov = np.average((x - mx) * (y - my), weights=wo)
                sx = np.sqrt(np.average((x - mx) ** 2, weights=wo))
                sy = np.sqrt(np.average((y - my) ** 2, weights=wo))
                r = float(cov / (sx * sy)) if sx > 0 and sy > 0 else np.nan
                rho = float(spearmanr(x, y).statistic)
                mae = float(np.average(np.abs(x - y), weights=wo))
        out.append({"colonne": c, "n_paires": n, "pearson": r, "spearman": rho, "mae": mae})
    return out


def apparier(p, m1, m2, cle, trains=None, poids=False):
    a = p[p["mill"] == m1].set_index(cle)
    b = p[p["mill"] == m2].set_index(cle)
    cols = SIM + (["n_jours"] if poids else [])
    j = a[cols].join(b[SIM], how="inner", lsuffix="_1", rsuffix="_2")
    if trains is not None:
        niv = cle.index("train")
        j = j[j.index.get_level_values(niv).isin(trains)]
    return j


def main() -> int:
    print("=== V1 — corrélation inter-millésimes des proportions SIMBA (lecture seule) ===")
    h = sha8(ML)
    if h != HASH_ATTENDU:
        raise RuntimeError(f"STOP : hash ml_dataset {h} != {HASH_ATTENDU}")

    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "horaire_numero_train",
                                      "id_gare_depart", "id_gare_arrivee", "base_date"] + SIM)
    df["horaire_numero_train"] = df["horaire_numero_train"].astype("float64")

    # Les 52 numéros de train qui circulent en H25 ET y portent un profil SIMBA 2024
    h25 = df[df["horaire_annee_horaire"] == "H25"]
    t52 = set(h25.loc[h25["simba_part_ga"].notna(), "horaire_numero_train"].dropna().astype(int))
    print(f"  trains H25 porteurs d'un profil SIMBA 2024 : {len(t52)}")

    pd_dim = profils_dim()
    pd_dim["train"] = pd_dim["train"].astype("float64")
    pd_ml = profils_ml(df)
    print(f"  profils dim_simba_r35 : {len(pd_dim)} | profils reconstruits ml_dataset : {len(pd_ml)}")
    for m in sorted(pd_dim["mill"].unique()):
        print(f"    millésime {m} : dim {int((pd_dim['mill'] == m).sum()):5} profils, "
              f"{pd_dim.loc[pd_dim['mill'] == m, 'train'].nunique():4} trains"
              + (f" | ml {int((pd_ml['mill'] == m).sum()):5} profils"
                 if (pd_ml["mill"] == m).any() else " | ml —"))

    PAIRES = [(2022, 2023), (2023, 2024), (2024, 2025)]
    DEFS = [
        ("D1", "dim / (train, tronçon) / 52 trains conservés", pd_dim, ["train", "tr"], t52, False),
        ("D2", "ml_dataset / (train, tronçon) / 52 trains conservés", pd_ml, ["train", "tr"], t52, False),
        ("D3", "dim / (train, tronçon) / tous trains communs", pd_dim, ["train", "tr"], None, False),
        ("D4", "dim / (train) / 52 trains conservés", None, ["train"], t52, False),
        ("D5", "ml_dataset / (train, tronçon) pondéré par les jours d'observation",
         pd_ml, ["train", "tr"], t52, True),
    ]
    p_d4 = pd_dim.groupby(["mill", "train"])[SIM].mean().reset_index()

    lignes, agreg = [], []
    for code, libelle, source, cle, trains, poids in DEFS:
        src = p_d4 if code == "D4" else source
        for m1, m2 in PAIRES:
            if not ((src["mill"] == m1).any() and (src["mill"] == m2).any()):
                continue
            j = apparier(src, m1, m2, cle, trains, poids)
            if len(j) == 0:
                continue
            niv = cle.index("train")
            st = stats_paire(j, "n_jours" if poids else None)
            for s in st:
                lignes.append({"definition": code, "libelle": libelle,
                               "millesime_1": m1, "millesime_2": m2,
                               "n_trains": int(j.index.get_level_values(niv).nunique()),
                               **s})
            rs = [s["pearson"] for s in st]
            rhos = [s["spearman"] for s in st]
            agreg.append({"definition": code, "libelle": libelle,
                          "millesime_1": m1, "millesime_2": m2,
                          "n_unites": int(len(j)),
                          "n_trains": int(j.index.get_level_values(niv).nunique()),
                          "pearson_moyen": float(np.nanmean(rs)),
                          "pearson_median": float(np.nanmedian(rs)),
                          "pearson_min": float(np.nanmin(rs)), "pearson_max": float(np.nanmax(rs)),
                          "spearman_moyen": float(np.nanmean(rhos)),
                          "spearman_median": float(np.nanmedian(rhos))})
            print(f"  [{code} {m1}→{m2}] n={len(j):5} unités, "
                  f"{j.index.get_level_values(niv).nunique():3} trains | "
                  f"r moyen={np.nanmean(rs):.3f} médian={np.nanmedian(rs):.3f} | "
                  f"rho moyen={np.nanmean(rhos):.3f}")

    cor = pd.DataFrame(lignes)
    agg = pd.DataFrame(agreg)
    cor.to_csv(OUT / "v1_simba_correlations.csv", index=False)
    agg.to_csv(OUT / "v1_simba_agregats.csv", index=False)

    # ── Confrontation à l'ADR-061 : quelle définition reproduit les 9 valeurs ? ────
    verdicts = {}
    for code, libelle, *_ in DEFS:
        sub = cor[(cor.definition == code) & (cor.millesime_1 == 2023) & (cor.millesime_2 == 2024)]
        if sub.empty:
            continue
        det = {}
        for c, (r_ref, mae_ref) in ADR_061.items():
            row = sub[sub.colonne == c]
            if row.empty:
                continue
            r, mae = float(row.pearson.iloc[0]), float(row.mae.iloc[0])
            det[c] = {"r_adr": r_ref, "r_recalcule": round(r, 4), "ecart_r": round(r - r_ref, 4),
                      "mae_adr": mae_ref, "mae_recalcule": round(mae, 4),
                      "ecart_mae": round(mae - mae_ref, 4),
                      "reproduit": bool(abs(r - r_ref) <= TOL and abs(mae - mae_ref) <= TOL)}
        n_ok = sum(v["reproduit"] for v in det.values())
        verdicts[code] = {"libelle": libelle, "n_colonnes_confrontees": len(det),
                          "n_reproduites": n_ok,
                          "n_unites": int(sub.n_paires.max()) if len(sub) else 0,
                          "detail": det}
        print(f"  confrontation ADR-061 [{code}] : {n_ok}/{len(det)} colonnes reproduites "
              f"à ±{TOL} sur r ET sur MAE")

    gagnante = max(verdicts, key=lambda k: verdicts[k]["n_reproduites"]) if verdicts else None
    payload = {
        "script": "v1_simba_correlation_millesimes.py",
        "sources": {"ml_dataset.parquet": HASH_ATTENDU, "dim_simba_r35.parquet": sha8(DIM)},
        "regle_millesime": "ADR-026 lag N-1 : H23→2022, H24→2023, H25→2024 "
                           "(H22→2021 absent, donc exclu)",
        "cle_troncon": "non orientée (min, max) des deux gares — miroir de "
                       "_simba_gare_min/_simba_gare_max, add_simba_to_raw_stacked.py",
        "trains_conserves_h25_avec_profil_2024": sorted(int(t) for t in t52),
        "n_trains_conserves": len(t52),
        "definitions": {c: l for c, l, *_ in DEFS},
        "agregats": agreg,
        "confrontation_adr_061": verdicts,
        "definition_reproduisant_adr": gagnante,
    }
    (OUT / "v1_simba_correlation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print(f"  ==> définition reproduisant l'ADR-061 : {gagnante}")
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
