#!/usr/bin/env python3
"""Tableaux des sections 4.5.x du mémoire — extraction depuis outputs/confirmation/.

Même discipline de provenance que les figures (docs/memoire/figures/) : source EXCLUSIVE
= outputs/confirmation/ (gel `ba493568`, modèle figé, LECTURE SEULE), garde de provenance
sur le hash de chaque JSON source, AUCUNE ré-exécution de modèle, sorties déterministes
(byte-reproductibles : pas d'horodatage embarqué). Nommage mémoire (Modèle retenu /
réglage Optuna ; aucun identifiant ADR / CF09 / hash dans les libellés).

Produit sous ce dossier :
  - table_4_5_2_baselines.csv           (naïve / M0 / Ridge ; sources c02, c03, c10)
  - table_4_5_3_comparatif_5bras.csv    (5 bras ; source c10)
  - table_4_5_7_renumerotation.csv      (connu/renuméroté × segment ; source c09)
  - table_4_5_7_prevalence_mensuelle.csv (mois horaire H25 ; source c09)
  - tableaux_4_5.md                     (les 4 tables rendues + provenance : source citable)

Les CSV portent les valeurs BRUTES (prévalence en fraction) ; le MD les rend (%).
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONF = ROOT / "outputs" / "confirmation"
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
OUT = Path(__file__).resolve().parent
HASH = "ba493568"
SEG = ("bas", "haut", "global")
SEG_FR = {"bas": "bas", "haut": "haut", "global": "global"}
# Noms de mois indexés par le mois CALENDAIRE standard (1 = janvier … 12 = décembre) ;
# point uniquement sur les mois réellement abrégés (identique à fig_metriques_mensuelles).
MOIS_ABBR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
             "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def date_mapping() -> dict:
    """cal_mois_horaire -> (libellé mois+année, date_min, date_max, n) DÉRIVÉ des dates
    RÉELLES du parquet gelé ba493568 (aucun offset codé en dur). Le test définitif montre
    qu'un indice cal_mois_horaire couvre exactement UN mois calendaire ; le libellé est donc
    le mois-année dominant des dates observées. Provenance vérifiée par empreinte."""
    import pandas as pd
    hp = hashlib.sha256(ML.read_bytes()).hexdigest()[:8]
    assert hp == HASH, f"provenance parquet {hp} != {HASH}"
    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "cal_mois_horaire", "base_date"])
    df = df[df["horaire_annee_horaire"] == "H25"].copy()
    df["base_date"] = pd.to_datetime(df["base_date"])
    out = {}
    for idx, sub in df.groupby("cal_mois_horaire", observed=True):
        ym = sub["base_date"].dt.to_period("M").mode().iloc[0]  # année-mois dominant
        out[int(idx)] = (f"{MOIS_ABBR[ym.month]} {ym.year}",
                         str(sub["base_date"].min().date()),
                         str(sub["base_date"].max().date()), int(len(sub)))
    return out


def load(fname: str) -> dict:
    d = json.loads((CONF / fname).read_text())
    h = d.get("meta", {}).get("dataset_hash_sha256_8")
    assert h == HASH, f"provenance {fname} : hash {h} != {HASH} (source non canonique)"
    return d


def metric_rows(bras: str, m: dict) -> list:
    out = []
    for s in SEG:
        d = m[s]
        out.append([bras, SEG_FR[s], round(d["r2"], 4), round(d["mae"], 2),
                    round(d["mae_gt63"], 2), round(d["bias_gt63"], 2),
                    round(d["pr_auc"], 4), int(d["n_gt63"])])
    return out


def write_csv(name: str, header: list, rows: list) -> Path:
    p = OUT / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


def md_table(header: list, rows: list, fmt=None) -> str:
    fmt = fmt or (lambda v: str(v))
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(fmt(v) for v in r) + " |")
    return "\n".join(lines)


def main() -> int:
    c02, c03, c09, c10 = load("c02_baseline_m0.json"), load("c03_baseline_lineaire.json"), \
        load("c09_analyse_erreurs.json"), load("c10_comparatif_algos.json")
    OUT.mkdir(parents=True, exist_ok=True)

    METRIC_H = ["bras", "segment", "r2", "mae", "mae_gt63", "biais_gt63", "pr_auc", "n_gt63"]

    # -- Table 4.5.2 : baselines (naïve / M0 / Ridge) --
    t1 = []
    t1 += metric_rows("Baseline naïve", c10["metriques_h25"]["baseline_naive_moyenne_historique"])
    t1 += metric_rows("M0 (APC + calendrier)", c02["metriques_h25"])
    t1 += metric_rows("Ridge (158 var.)", c03["metriques_h25"])
    write_csv("table_4_5_2_baselines.csv", METRIC_H, t1)

    # -- Table 4.5.3 : comparatif 5 bras (c10) --
    ARMS = [("Modèle retenu", "canonique_cf09_gel"),
            ("Random Forest (défaut)", "randomforest_defaut"),
            ("XGBoost (réglage Optuna)", "xgboost_bestparams"),
            ("LightGBM (réglage Optuna)", "lightgbm_bestparams"),
            ("CatBoost (réglage Optuna)", "catboost_bestparams")]
    t2 = []
    for name, k in ARMS:
        t2 += metric_rows(name, c10["metriques_h25"][k])
    write_csv("table_4_5_3_comparatif_5bras.csv", METRIC_H, t2)

    # -- Table 4.5.7a : renumérotation (clé numero_train) --
    RENUM_H = ["strate", "segment", "n_obs", "n_gt63", "prevalence_gt63", "pr_auc"]
    c = c09["c_connus_vs_renumerotes"]["horaire_numero_train"]
    t3a = []
    for strat, lbl in [("connu", "Course connue"), ("renumero", "Course renumérotée")]:
        for s in SEG:
            d = c[strat][s]
            t3a.append([lbl, SEG_FR[s], int(d["n_obs"]), int(d["n_gt63"]),
                        round(d["prevalence"], 6), round(d["pr_auc"], 4)])
    write_csv("table_4_5_7_renumerotation.csv", RENUM_H, t3a)

    # -- Table 4.5.7b : prévalence >63 par mois horaire H25 (libellé dérivé des dates réelles) --
    dm = date_mapping()
    MENS_H = ["mois_horaire", "mois_calendaire", "date_min", "date_max", "n_obs", "n_gt63",
              "prevalence_gt63_global", "prevalence_gt63_bas", "prevalence_gt63_haut"]
    b = c09["b_metriques_par_mois_horaire"]
    t3b = []
    for mk in sorted(b, key=int):
        d = b[mk]
        idx = int(mk)
        lab, dmin, dmax, n_par = dm[idx]
        assert n_par == int(d["global"]["n_obs"]), \
            f"désaccord n_obs mois {idx} : parquet {n_par} vs c09 {d['global']['n_obs']}"
        t3b.append([idx, lab, dmin, dmax, int(d["global"]["n_obs"]), int(d["global"]["n_gt63"]),
                    round(d["global"]["prevalence"], 6), round(d["bas"]["prevalence"], 6),
                    round(d["haut"]["prevalence"], 6)])
    write_csv("table_4_5_7_prevalence_mensuelle.csv", MENS_H, t3b)

    # -- MD combiné (source citable) : décimales fixes (R²/PR-AUC 4 ; MAE/biais 2 ; n entier) --
    def pct(v):
        return f"{v * 100:.3f} %"

    def fmt_metric(r):
        return [r[0], r[1], f"{r[2]:.4f}", f"{r[3]:.2f}", f"{r[4]:.2f}",
                f"{r[5]:.2f}", f"{r[6]:.4f}", str(r[7])]

    MH = ["Bras", "Segment", "R²", "MAE", "MAE>63", "biais>63", "PR-AUC", "n>63"]
    md = []
    md.append("# Tableaux des sections 4.5.x (suite de confirmation, gel `ba493568`)\n")
    md.append("Tables extraites **exclusivement** de `outputs/confirmation/` (hash `ba493568`, "
              "modèle figé, lecture seule), générées par `make_tableaux_4_5.py`. **Aucune "
              "ré-exécution de modèle** ; garde de provenance sur le hash de chaque JSON source ; "
              "sorties déterministes (byte-reproductibles). Nommage mémoire : « Modèle retenu », "
              "« <Algo> (réglage Optuna) », « Random Forest (défaut) » ; les identifiants "
              "(CF09, best_params, hash) restent dans les JSON de traçabilité, pas dans ces libellés.\n")
    md.append("Convention : `n>63` (positifs observés) est invariant entre bras par segment "
              "(bas 8392 / haut 1192 / global 9584 = iso-périmètre). CSV associés dans ce dossier "
              "(valeurs brutes, prévalence en fraction).\n")

    md.append("## Table 4.5.2 — Baselines (naïve / M0 / Ridge), H25 par segment\n")
    md.append("Sources : `c10_comparatif_algos.json` (bras naïve), `c02_baseline_m0.json`, "
              "`c03_baseline_lineaire.json`.\n")
    md.append(md_table(MH, [fmt_metric(r) for r in t1]) + "\n")

    md.append("## Table 4.5.3 — Comparatif d'algorithmes (5 bras), H25 par segment\n")
    md.append("Source : `c10_comparatif_algos.json` (ADR-072, sélection figée). Baseline naïve : "
              "voir Table 4.5.2.\n")
    md.append(md_table(MH, [fmt_metric(r) for r in t2]) + "\n")

    md.append("## Table 4.5.7a — Renumérotation des courses (clé numéro de train), H25\n")
    md.append("Source : `c09_analyse_erreurs.json`. Clé `horaire_service_id_complet` dégénérée "
              "sur `ba493568` (voir c09) ; clé `numéro de train` non dégénérée, rapportée ici.\n")
    RH = ["Strate", "Segment", "n obs", "n>63", "prévalence>63", "PR-AUC"]
    t3a_md = [[r[0], r[1], str(r[2]), str(r[3]), pct(r[4]), f"{r[5]:.4f}"] for r in t3a]
    md.append(md_table(RH, t3a_md) + "\n")

    md.append("## Table 4.5.7b — Prévalence >63 par mois horaire H25\n")
    md.append("Prévalence : `c09_analyse_erreurs.json`. Libellé de mois **dérivé des dates réelles** "
              "du parquet gelé `ba493568` (`cal_mois_horaire` → période observée), sans offset codé "
              "en dur : l'année horaire H25 va de décembre 2024 (indice 1) à décembre 2025 (indice 13).\n")
    MMH = ["Mois horaire", "Mois cal.", "Période (dates)", "n obs", "n>63",
           "prév. global", "prév. bas", "prév. haut"]
    t3b_md = [[str(r[0]), r[1], f"{r[2]} → {r[3]}", str(r[4]), str(r[5]),
               pct(r[6]), pct(r[7]), pct(r[8])] for r in t3b]
    md.append(md_table(MMH, t3b_md) + "\n")

    (OUT / "tableaux_4_5.md").write_text("\n".join(md), encoding="utf-8")

    print("[écrit]")
    for p in sorted(OUT.glob("*.csv")):
        print("  ", p.relative_to(ROOT))
    print("  ", (OUT / "tableaux_4_5.md").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
