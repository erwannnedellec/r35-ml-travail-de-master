#!/usr/bin/env python3
"""
A3 — Recalculs à l'appui de la chronologie du retrait SIMBA.

LECTURE SEULE : recalcule sur `ba493568` les trois valeurs chiffrées de fiabilité qui
sont recalculables (fuite de disponibilité, manquants structurels, rangs SHAP archivés),
et rassemble les horodatages machine des artefacts de la frise.

Ce qui n'est PAS recalculable est signalé comme tel dans la sortie (corrélation
inter-millésimes r = 0,056 : aucun script producteur dans le dépôt).

Sorties :
  - a3_simba_verifs.json     synthèse machine
  - a3_simba_shap_rangs.csv  rangs des 12 simba_part_* dans chaque artefact SHAP archivé

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/a3_simba_verifs.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ML = ROOT / "data/processed/ml_dataset.parquet"
HASH_ATTENDU = "ba493568"

SIMBA_PART = [
    "simba_part_ga", "simba_part_mobilis", "simba_part_billet_hta", "simba_part_spar",
    "simba_part_jeunes", "simba_part_abonnement", "simba_part_militaire",
    "simba_part_autre", "simba_part_corresp_amont", "simba_part_corresp_aval",
    "simba_part_premiere_classe", "simba_part_intra_r35",
]

# Fenêtres de latence de publication SIMBA (ADR-061 §2)
FENETRES = [("déc. 2024 – mars 2025", "2025-03-31", 16.6),
            ("déc. 2024 – avr. 2025 (latence 5 mois)", "2025-04-30", 21.6),
            ("déc. 2024 – mai 2025 (latence 6 mois)", "2025-05-31", 26.2)]

# Artefacts SHAP archivés portant les 12 simba_part_*
SHAP_ARTEFACTS = {
    "bas_170f": "archive/explorations/consolidation_finale/outputs/q6_shap_ranks_bas_170f_archive.csv",
    "haut_170f": "archive/explorations/consolidation_finale/outputs/q6_shap_ranks_haut_170f_archive.csv",
    "bas_vivier_179": "archive/explorations/consolidation_finale/outputs/etape_04_shap_importance_bas.csv",
    "modele_B_168f": "outputs/11_shap_global_ranking.csv",
}

# Artefacts horodatés de la frise (champ JSON portant le timestamp)
FRISE = {
    "outputs/experiences/contreverif_h24_simba.json": "created_at",
    "outputs/confirmation/c06_ablation_simba.json": "meta.created_at",
    "archive/explorations/consolidation_finale/outputs/retrait_simba_158f_resultats.json": "created_at",
    "archive/explorations/consolidation_finale/outputs/backup_51e459ff/retrait_simba_158f_resultats.json": "created_at",
}


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def dig(d, path):
    for k in path.split("."):
        d = d.get(k, {}) if isinstance(d, dict) else None
        if d is None:
            return None
    return d


def main() -> int:
    print("=== A3 — recalculs SIMBA (lecture seule) ===")
    h = sha8(ML)
    if h != HASH_ATTENDU:
        raise RuntimeError(f"STOP : hash ml_dataset {h} != {HASH_ATTENDU}")
    res = {"dataset_hash": h}

    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "base_date"] + SIMBA_PART)
    h25 = df[df["horaire_annee_horaire"] == "H25"]
    n25 = len(h25)
    print(f"  H25 : {n25} observations, {h25.base_date.min().date()} → {h25.base_date.max().date()}")

    # ── Constat 3 : manquants structurels sur H25 ───────────────────────────────
    nan25 = {c: round(100.0 * h25[c].isna().mean(), 4) for c in SIMBA_PART}
    res["constat_3_manquants_h25"] = {
        "annonce_adr_061": 46.6,
        "taux_par_variable_pct": nan25,
        "valeur_unique": len(set(nan25.values())) == 1,
        "valeur": list(nan25.values())[0],
    }
    print(f"  manquants H25 : {list(nan25.values())[0]} % (identique sur les 12 variables : "
          f"{len(set(nan25.values())) == 1})")

    # ── Constat 2 : fuite de disponibilité ──────────────────────────────────────
    match = h25["simba_part_ga"].notna()
    fen = []
    for lab, fin, annonce in FENETRES:
        w = match & (h25["base_date"] <= fin)
        fen.append({"fenetre": lab, "n_obs_avec_match_simba": int(w.sum()),
                    "pct_de_h25": round(100.0 * w.sum() / n25, 4),
                    "annonce_adr_061_pct": annonce})
        print(f"  {lab}: {int(w.sum())} obs = {100.0 * w.sum() / n25:.2f} % "
              f"(ADR-061 : {annonce} %)")
    res["constat_2_fuite_disponibilite"] = fen

    # ── Constat 1 : corrélation inter-millésimes — non reproductible ────────────
    res["constat_1_correlation_inter_millesimes"] = {
        "valeur_annoncee": 0.056,
        "variable": "simba_part_ga",
        "source": "docs/adr/ADR-061_retrait_simba_features.md §1 (tableau des 9 corrélations)",
        "reproductible": False,
        "note": "non déterminable sur pièces : aucun script du dépôt ne produit ces "
                "corrélations inter-millésimes ; seuls existent les producteurs de "
                "pipeline SIMBA et les scripts d'ablation de 2026-07-16.",
        "incoherence_signalee": "ADR-061 §1 « 52 trains conservés » vs ADR-041:24-25 "
                                "« 51 trains conservés / 52 renumérotés » — non tranchable.",
    }

    # ── Constat 4 : rangs SHAP des 12 simba_part_* ──────────────────────────────
    lignes, synth = [], {}
    for nom, rel in SHAP_ARTEFACTS.items():
        p = ROOT / rel
        if not p.exists():
            synth[nom] = {"absent": rel}
            continue
        d = pd.read_csv(p)
        fc = [c for c in d.columns if "feat" in c.lower()][0]
        rc = [c for c in d.columns if c in ("rang", "rank")][0]
        vc = [c for c in d.columns if "shap" in c.lower()][0]
        n = len(d)
        s = d[d[fc].astype(str).str.startswith("simba_part")]
        for _, r in s.iterrows():
            lignes.append({"artefact": nom, "fichier": rel, "n_variables": n,
                           "variable": r[fc], "rang": int(r[rc]),
                           "mean_abs_shap": float(r[vc])})
        synth[nom] = {
            "fichier": rel, "n_variables": int(n), "n_simba": int(len(s)),
            "rang_min": int(s[rc].min()), "rang_median": float(s[rc].median()),
            "rang_max": int(s[rc].max()),
            "n_dans_moitie_inferieure": int((s[rc] > n / 2).sum()),
            "part_masse_shap_pct": round(100.0 * s[vc].sum() / d[vc].sum(), 3),
        }
        print(f"  SHAP {nom:15} n={n:4} rangs {s[rc].min()}-{s[rc].max()} "
              f"médiane {s[rc].median():.0f} ; moitié inf. {int((s[rc] > n / 2).sum())}/12")
    pd.DataFrame(lignes).to_csv(OUT / "a3_simba_shap_rangs.csv", index=False)
    res["constat_4_rangs_shap"] = {
        "annonce_adr_061": "systématiquement dans la moitié inférieure du classement SHAP",
        "par_artefact": synth,
        "verdict": "contredit au grain de la variable ; vrai seulement au grain de la "
                   "famille (ADR-053 : 5,3 % bas / 4,7 % haut, 7e sur 9 familles)",
    }

    # ── Frise : horodatages machine ─────────────────────────────────────────────
    frise = {}
    for rel, champ in FRISE.items():
        p = ROOT / rel
        frise[rel] = dig(json.loads(p.read_text()), champ) if p.exists() else None
    res["frise_horodatages_machine"] = frise
    res["dates_declaratives_adr"] = {
        "ADR-061 date_decision": "2026-06-11",
        "ADR-061 corroboration_git": "déclaratif (2026-07-07) — docs/adr/INDEX.md:101",
        "ADR-041 date_decision": "2026-06-05",
        "ADR-026 date_decision": "2026-05-21",
        "ADR-076 date_decision": "2026-07-11",
    }
    for k, v in frise.items():
        print(f"  {v}  {k}")

    (OUT / "a3_simba_verifs.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
