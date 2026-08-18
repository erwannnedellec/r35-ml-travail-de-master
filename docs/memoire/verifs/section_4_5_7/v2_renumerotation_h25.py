#!/usr/bin/env python3
"""
V2 — Renumérotation des trains au changement d'horaire de décembre 2024.

Le manuscrit annonce « 52 des 103 trains » renumérotés (§4.5.1) et « la moitié de la
grille » (§4.5.7). L'audit A3 signale une incohérence entre ADR-061 (« 52 trains
conservés ») et ADR-041 (« 51 trains conservés / 52 renumérotés »). Ce script calcule les
cardinaux directement depuis les données.

LECTURE SEULE. N'écrit que sous docs/memoire/verifs/section_4_5/.

Deux référentiels sont rapportés côte à côte, car ils ne comptent pas la même chose :
  - `ml_dataset.parquet` : trains effectivement MESURÉS par l'APC (périmètre du modèle) ;
  - `istdaten_clean.parquet` : trains effectivement CIRCULÉS (grille réalisée).
S'y ajoutent les référentiels SIMBA (`dim_simba_r35`), un par millésime, seuls candidats
au cardinal 103.

Les bornes d'année horaire sont DÉRIVÉES des données (min/max de `base_date` par
`horaire_annee_horaire`), jamais codées en dur.

Sorties :
  - v2_ensembles_trains.csv    cardinaux par référentiel et par année horaire
  - v2_strates_h25.csv         partition des numéros H25 et des observations par strate
  - v2_renumerotation.json     synthèse machine

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/v2_renumerotation_h25.py
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
IST = ROOT / "data/processed/sources/istdaten_clean.parquet"
DIM = ROOT / "data/dimension/dim_simba_r35.parquet"
HASH_ATTENDU = "ba493568"


def sha8(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]


def main() -> int:
    print("=== V2 — renumérotation au changement d'horaire de décembre 2024 (lecture seule) ===")
    h = sha8(ML)
    if h != HASH_ATTENDU:
        raise RuntimeError(f"STOP : hash ml_dataset {h} != {HASH_ATTENDU}")

    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "horaire_numero_train",
                                      "base_date", "simba_part_ga"])
    df["train"] = df["horaire_numero_train"].astype("float64")

    # ── Bornes d'année horaire, dérivées des données ────────────────────────────
    bornes = (df.groupby("horaire_annee_horaire")["base_date"]
                .agg(debut="min", fin="max", n_jours="nunique").reset_index())
    print("  bornes dérivées :")
    for _, r in bornes.iterrows():
        print(f"    {r.horaire_annee_horaire} : {r.debut.date()} → {r.fin.date()} "
              f"({r.n_jours} jours)")

    # ── Référentiel 1 : ml_dataset (trains mesurés par l'APC) ──────────────────
    ens_ml = {a: set(g["train"].dropna().astype(int))
              for a, g in df.groupby("horaire_annee_horaire")}

    # ── Référentiel 2 : istdaten_clean (trains circulés) ───────────────────────
    ens_ist = {}
    if IST.exists():
        di = pd.read_parquet(IST, columns=["date", "numero_train"])
        di["date"] = pd.to_datetime(di["date"])
        for _, r in bornes.iterrows():
            s = di[(di["date"] >= r.debut) & (di["date"] <= r.fin)]
            ens_ist[r.horaire_annee_horaire] = set(s["numero_train"].dropna().astype(int))
    else:
        print("  ATTENTION : istdaten_clean.parquet absent — référentiel 2 non calculé")

    # ── Référentiel 3 : dim_simba_r35, un ensemble par millésime ───────────────
    dim = pd.read_parquet(DIM, columns=["simba_millesime", "simba_numero_train"])
    ens_simba = {int(m): set(g["simba_numero_train"].astype(int))
                 for m, g in dim.groupby("simba_millesime")}

    # ── Cardinaux ──────────────────────────────────────────────────────────────
    lignes = []
    for ref, ens in (("ml_dataset (mesuré APC)", ens_ml),
                     ("istdaten_clean (circulé)", ens_ist)):
        for a in sorted(ens):
            lignes.append({"referentiel": ref, "perimetre": a, "n_numeros_train": len(ens[a])})
    for m in sorted(ens_simba):
        lignes.append({"referentiel": "dim_simba_r35 (millésime)", "perimetre": f"SIMBA {m}",
                       "n_numeros_train": len(ens_simba[m])})
    card = pd.DataFrame(lignes)
    card.to_csv(OUT / "v2_ensembles_trains.csv", index=False)
    print("\n  cardinaux :")
    print("   " + card.to_string(index=False).replace("\n", "\n   "))

    # ── Transition H24 → H25, par référentiel ──────────────────────────────────
    transitions = {}
    for ref, ens in (("ml_dataset", ens_ml), ("istdaten", ens_ist)):
        if "H24" not in ens or "H25" not in ens:
            continue
        a, b = ens["H24"], ens["H25"]
        transitions[ref] = {
            "n_H24": len(a), "n_H25": len(b),
            "n_intersection": len(a & b),
            "n_disparus_H24_moins_H25": len(a - b),
            "n_nouveaux_H25_moins_H24": len(b - a),
            "n_union": len(a | b),
            "part_nouveaux_dans_H25_pct": round(100 * len(b - a) / len(b), 2),
            "part_disparus_dans_H24_pct": round(100 * len(a - b) / len(a), 2),
        }
        t = transitions[ref]
        print(f"\n  transition H24 → H25 [{ref}] : |H24|={t['n_H24']} |H25|={t['n_H25']} "
              f"∩={t['n_intersection']} | disparus={t['n_disparus_H24_moins_H25']} "
              f"| nouveaux={t['n_nouveaux_H25_moins_H24']} "
              f"({t['part_nouveaux_dans_H25_pct']} % de H25)")

    # ── Partition des numéros H25 selon la couverture SIMBA 2024 ───────────────
    h25 = df[df["horaire_annee_horaire"] == "H25"]
    avec = set(h25.loc[h25["simba_part_ga"].notna(), "train"].dropna().astype(int))
    sans = ens_ml["H25"] - avec
    nouveaux = ens_ml["H25"] - ens_ml["H24"]
    sans_mais_en_h24 = sorted(sans & ens_ml["H24"])

    strates = []
    for lbl, s in (("H25 avec profil SIMBA 2024", avec),
                   ("H25 sans profil SIMBA 2024", sans),
                   ("  dont numéros nouveaux en H25", sans & nouveaux),
                   ("  dont numéros déjà en H24 mais absents de SIMBA 2024",
                    sans & ens_ml["H24"])):
        m = h25["train"].isin(s)
        # deux comptes distincts : lignes dont le NUMÉRO appartient à la strate, et lignes
        # portant effectivement une valeur (un tronçon peut manquer dans la dimension)
        avec_valeur = int((m & h25["simba_part_ga"].notna()).sum())
        strates.append({"strate": lbl, "n_numeros_train": len(s),
                        "part_des_numeros_h25_pct": round(100 * len(s) / len(ens_ml["H25"]), 2),
                        "n_observations_du_numero": int(m.sum()),
                        "part_des_observations_h25_pct": round(100 * m.mean(), 2),
                        "n_observations_avec_valeur_simba": avec_valeur})
    st = pd.DataFrame(strates)
    st.to_csv(OUT / "v2_strates_h25.csv", index=False)
    print("\n  partition des numéros H25 :")
    print("   " + st.to_string(index=False).replace("\n", "\n   "))
    print(f"\n  numéros présents en H24 ET H25 mais sans profil SIMBA 2024 : {sans_mais_en_h24}")

    # ── Réconciliation de l'écart ADR-041 (51 trains / 160 147 obs) ────────────
    n_avec_valeur = int(h25["simba_part_ga"].notna().sum())
    ecart = n_avec_valeur - 160147
    g = h25[h25["simba_part_ga"].notna()].groupby("train").size()
    coupables = sorted(int(t) for t, n in g.items() if int(n) == ecart)
    recon = {
        "adr_041_conserves": {"n_trains": 51, "n_obs": 160147, "pct": 51.8},
        "adr_041_renumerotes": {"n_trains": 52, "n_obs": 143867, "pct": 46.5},
        "recalcule_avec_valeur_simba": {"n_trains": len(avec), "n_obs": n_avec_valeur,
                                        "pct": round(100 * n_avec_valeur / len(h25), 2)},
        "recalcule_sans_valeur_simba": {"n_obs": int(h25["simba_part_ga"].isna().sum()),
                                        "pct": round(100 * h25["simba_part_ga"].isna().mean(), 2)},
        "ecart_obs_vs_adr_041": ecart,
        "trains_dont_effectif_egale_l_ecart": coupables,
        "lecture": "ADR-041 laisse 5 238 observations non affectées (160 147 + 143 867 = "
                   "304 014 < 309 252). L'écart sur les conservés est expliqué par un seul "
                   "numéro de train omis du décompte.",
    }
    print(f"\n  réconciliation ADR-041 : {n_avec_valeur} obs avec valeur SIMBA "
          f"(ADR-041 : 160 147) — écart {ecart} ; "
          f"train(s) d'effectif exactement égal à l'écart : {coupables}")
    print(f"  observations SANS valeur SIMBA : {int(h25['simba_part_ga'].isna().sum())} "
          f"(ADR-041 : 143 867)")

    # ── Candidats au cardinal 103 ──────────────────────────────────────────────
    candidats = {}
    for ref, ens in (("ml_dataset", ens_ml), ("istdaten", ens_ist)):
        for a in sorted(ens):
            candidats[f"{ref} {a}"] = len(ens[a])
    for m in sorted(ens_simba):
        candidats[f"dim_simba millésime {m}"] = len(ens_simba[m])
    exacts = sorted(k for k, v in candidats.items() if v == 103)
    print(f"\n  référentiels de cardinal EXACTEMENT 103 : {exacts if exacts else 'aucun'}")

    payload = {
        "script": "v2_renumerotation_h25.py",
        "sources": {"ml_dataset.parquet": HASH_ATTENDU,
                    "dim_simba_r35.parquet": sha8(DIM),
                    "istdaten_clean.parquet": (sha8(IST) if IST.exists() else None)},
        "bornes_annees_horaires": [
            {"annee_horaire": r.horaire_annee_horaire, "debut": str(r.debut.date()),
             "fin": str(r.fin.date()), "n_jours": int(r.n_jours)} for _, r in bornes.iterrows()],
        "cardinaux": candidats,
        "referentiels_de_cardinal_103": exacts,
        "transition_h24_h25": transitions,
        "partition_h25_simba": strates,
        "reconciliation_adr_041": recon,
        "numeros_h24_et_h25_sans_profil_simba_2024": sans_mais_en_h24,
        "valeurs_annoncees": {
            "manuscrit_4_5_1": "52 des 103 trains renumérotés",
            "manuscrit_4_5_7": "la moitié de la grille",
            "ADR-041": "51 trains conservés (49 %) / 52 renumérotés (50 %)",
            "ADR-061": "52 trains conservés entre H24 et H25",
        },
    }
    (OUT / "v2_renumerotation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
