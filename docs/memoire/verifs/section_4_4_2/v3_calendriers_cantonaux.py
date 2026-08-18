#!/usr/bin/env python3
"""
V3 — Calendriers des cantons limitrophes (VS, FR, NE, GE) : trace de l'evaluation.

Verifie (a) qu'une evaluation a bien eu lieu, (b) selon quel protocole, (c) quels
chiffres ont ete mesures, (d) s'il existe une trace d'un motif alternatif
(redondance avec le calendrier vaudois) qui aurait pu motiver l'abandon.

Lecture seule. Aucun reentrainement : les chiffres sont RELUS des artefacts
JSON du chantier `exp_features/`, et la correlation avec le calendrier vaudois est
RECALCULEE depuis les features cantonales construites et le jeu canonique.

Sorties : docs/memoire/verifs/complements/v3_*.csv
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _garde import ROOT, garde  # noqa: E402

OUT = Path(__file__).resolve().parent
EXP = ROOT / "archive" / "explorations" / "exp_features"
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"

TRACES = [
    ("docs/adr/ADR-070_features_vacances_feries_cantonales.md", "ADR — decision de ne pas integrer"),
    ("archive/explorations/exp_features/RAPPORT_PHASE_A.md", "rapport — construction et controle qualite"),
    ("archive/explorations/exp_features/RAPPORT_PHASE_B.md", "rapport — impact en validation interne H24"),
    ("archive/explorations/exp_features/RAPPORT_PHASE_C.md", "rapport — confirmation hors temps H25"),
    ("archive/explorations/exp_features/build_cantonal_features.py", "script — construction des 8 variables"),
    ("archive/explorations/exp_features/parse_valais.py", "script — parseur des PDF valaisans"),
    ("archive/explorations/exp_features/qc_report.py", "script — controle qualite et correlations"),
    ("archive/explorations/exp_features/phaseB_impact_h24.py", "script — test d'impact H24"),
    ("archive/explorations/exp_features/phaseC_confirm_h25.py", "script — confirmation H25"),
    ("archive/explorations/exp_features/outputs/phaseB_impact_h24.json", "artefact de resultat H24"),
    ("archive/explorations/exp_features/outputs/phaseC_confirm_h25.json", "artefact de resultat H25"),
    ("archive/explorations/exp_features/outputs/features_vacances_feries_cantonales.parquet",
     "artefact — 8 variables construites"),
    ("archive/explorations/exp_features/outputs/audit_periodes_vacances.csv", "audit — periodes de vacances"),
    ("archive/explorations/exp_features/outputs/audit_feries.csv", "audit — jours feries"),
]

CANTONS = ["valais", "fribourg", "neuchatel", "geneve"]


def date_git(rel: str) -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%ad", "--date=short", "--", rel],
                           cwd=ROOT, capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or "n/d"
    except Exception:
        return "n/d"


def main() -> None:
    garde()
    print("=" * 78)
    print("V3 — CALENDRIERS DES CANTONS LIMITROPHES : TRACE DE L'EVALUATION")
    print("=" * 78)

    # ── 1. Inventaire des traces ──────────────────────────────────────────────
    print("\n[1] Traces presentes dans le depot")
    inv = []
    for rel, objet in TRACES:
        p = ROOT / rel
        inv.append({"chemin": rel, "existe": p.exists(), "objet": objet,
                    "derniere_date_git": date_git(rel) if p.exists() else ""})
        print(f"    {'OK ' if p.exists() else 'ABS'} {rel}")
    pd.DataFrame(inv).to_csv(OUT / "v3_inventaire_traces.csv", index=False)

    # ── 2. Chiffres mesures, relus des artefacts ──────────────────────────────
    print("\n[2] Chiffres relus des artefacts de resultat")
    b = json.loads((EXP / "outputs" / "phaseB_impact_h24.json").read_text())
    c = json.loads((EXP / "outputs" / "phaseC_confirm_h25.json").read_text())
    print(f"    phaseB statut : {b.get('statut', 'n/d')}")
    print(f"    phaseC statut : {c.get('statut', 'n/d')}")
    (OUT / "v3_cles_artefacts.txt").write_text(
        "phaseB_impact_h24.json : " + json.dumps(list(b.keys()), ensure_ascii=False) + "\n"
        "phaseC_confirm_h25.json : " + json.dumps(list(c.keys()), ensure_ascii=False) + "\n")

    def plonge(d, chemin=""):
        """Aplatit un JSON imbrique en (chemin, valeur scalaire)."""
        out = {}
        if isinstance(d, dict):
            for k, v in d.items():
                out.update(plonge(v, f"{chemin}.{k}" if chemin else k))
        elif isinstance(d, (int, float, str, bool)) or d is None:
            out[chemin] = d
        return out

    pb, pc = plonge(b), plonge(c)
    pd.DataFrame([{"artefact": "phaseB_impact_h24.json", "cle": k, "valeur": v}
                  for k, v in pb.items()] +
                 [{"artefact": "phaseC_confirm_h25.json", "cle": k, "valeur": v}
                  for k, v in pc.items()]).to_csv(OUT / "v3_mesures_brutes.csv", index=False)

    # Deltas PR-AUC clefs (recherche par motif, pas de cle devinee)
    def cherche(plat, *motifs):
        return {k: v for k, v in plat.items()
                if all(m in k for m in motifs) and isinstance(v, (int, float))}

    print("\n    Deltas PR-AUC releves (phase B, validation interne H24) :")
    for k, v in sorted(cherche(pb, "delta").items()):
        print(f"      {k:60} {v}")
    print("\n    Deltas PR-AUC releves (phase C, confirmation hors temps H25) :")
    for k, v in sorted(cherche(pc, "delta").items()):
        print(f"      {k:60} {v}")

    # ── 3. Taux de generalisation du gain BAS ─────────────────────────────────
    print("\n[3] Taux de generalisation du gain BAS (H24 -> H25)")
    # valeurs telles que publiees dans RAPPORT_PHASE_B / C et ADR-070
    gener = []
    for lbl, d24, d25 in [("PR-AUC BAS grain troncon", 0.0191, 0.0055),
                          ("PR-AUC BAS grain tour", 0.0122, 0.0047)]:
        r = d25 / d24
        gener.append({"metrique": lbl, "delta_validation_H24": d24,
                      "delta_confirmation_H25": d25,
                      "part_retenue_pct": round(100 * r, 1),
                      "inferieur_au_tiers": bool(r < 1 / 3)})
        print(f"    {lbl:28} {d24:+.4f} -> {d25:+.4f} = {100*r:.1f} % retenus "
              f"({'< 1/3' if r < 1/3 else '>= 1/3'})")
    pd.DataFrame(gener).to_csv(OUT / "v3_generalisation_gain_bas.csv", index=False)

    # ── 4. Motif alternatif : redondance avec le calendrier vaudois ───────────
    print("\n[4] Motif alternatif teste : correlation avec le calendrier vaudois")
    cant = pd.read_parquet(EXP / "outputs" / "features_vacances_feries_cantonales.parquet")
    cant["date"] = pd.to_datetime(cant["date"]).dt.normalize()
    vaud = pd.read_parquet(ML_DATASET, columns=["base_date", "event_is_vacances_vaud",
                                                "event_is_ferie_vaud"])
    vaud["date"] = pd.to_datetime(vaud["base_date"]).dt.normalize()
    vaud = vaud.drop_duplicates("date")[["date", "event_is_vacances_vaud", "event_is_ferie_vaud"]]
    m = cant.merge(vaud, on="date", how="inner")
    print(f"    jours communs au perimetre du jeu canonique : {len(m)}")

    def jaccard(a, b):
        a, b = a.astype(bool), b.astype(bool)
        u = (a | b).sum()
        return float((a & b).sum() / u) if u else np.nan

    # Deux perimetres, tous deux defendables, rapportes cote a cote :
    #  - « tous jours »       : tous les jours du perimetre du jeu canonique ;
    #  - « jours ouvrables »  : lundi-vendredi, perimetre du controle qualite d'origine
    #                           (archive/explorations/exp_features/qc_report.py:26,64-95).
    m["is_weekday"] = m["date"].dt.weekday < 5
    perimetres = {"tous_jours": m, "jours_ouvrables": m[m["is_weekday"]]}

    corr = []
    for pnom, sub in perimetres.items():
        for fam, ref in [("vacances", "event_is_vacances_vaud"), ("ferie", "event_is_ferie_vaud")]:
            for k in CANTONS:
                col = f"event_is_{fam}_{k}"
                a = sub[col].astype(float)
                bb = sub[ref].astype(float)
                r = float(np.corrcoef(a, bb)[0, 1])
                corr.append({"perimetre": pnom, "famille": fam, "canton": k, "reference": ref,
                             "n_jours": len(sub),
                             "pearson_r": round(r, 4),
                             "jaccard": round(jaccard(sub[col], sub[ref]), 4),
                             "quasi_identique_r_sup_095": bool(r > 0.95)})
    cdf = pd.DataFrame(corr)
    cdf.to_csv(OUT / "v3_correlation_avec_vaud.csv", index=False)
    print("\n" + cdf.to_string(index=False))

    # correlations internes entre cantons (redondance VS-FR annoncee a 0,97)
    inter = []
    for pnom, sub in perimetres.items():
        for fam in ("vacances", "ferie"):
            cols = [f"event_is_{fam}_{k}" for k in CANTONS]
            cm = sub[cols].astype(float).corr().round(4)
            cm.to_csv(OUT / f"v3_correlation_interne_{fam}_{pnom}.csv")
            for i, a in enumerate(CANTONS):
                for bcanton in CANTONS[i + 1:]:
                    inter.append({"perimetre": pnom, "famille": fam,
                                  "canton_a": a, "canton_b": bcanton,
                                  "n_jours": len(sub),
                                  "pearson_r": float(cm.loc[f"event_is_{fam}_{a}",
                                                            f"event_is_{fam}_{bcanton}"])})
    idf = pd.DataFrame(inter)
    idf.to_csv(OUT / "v3_correlation_inter_cantonale.csv", index=False)
    print("\n    Correlations inter-cantonales :")
    print(idf.to_string(index=False))

    print("\n[5] Verdict sur le motif alternatif")
    for pnom in perimetres:
        s = cdf[cdf["perimetre"] == pnom]
        maxi = s.loc[s["pearson_r"].idxmax()]
        print(f"    [{pnom}] correlation maximale avec le vaudois : "
              f"{maxi['famille']} {maxi['canton']} r = {maxi['pearson_r']} "
              f"(n = {maxi['n_jours']} jours) ; quasi identiques (r > 0,95) : "
              f"{int(s['quasi_identique_r_sup_095'].sum())} / {len(s)}")
    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
