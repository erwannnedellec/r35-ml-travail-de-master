#!/usr/bin/env python3
"""Section 4.5.6 (extension) — décomposition SHAP mensuelle SIGNÉE par famille. LECTURE SEULE.

Par segment × mois HORAIRE de H25 (cal_mois_horaire 1..13, DEUX décembres distingués :
1 = déc. 2024, 13 = déc. 2025 ; mêmes bornes que §4.5.7 / figure 25), moyenne des SHAP
SIGNÉS agrégés par famille fonctionnelle (= somme des SHAP signés des variables de la
famille, moyennée sur les observations du mois).

Additivité (TreeSHAP) vérifiée par mois : Σ_familles mean_shap_signe = mean(pred) −
mean(biais), écart exigé < 1e-4 (somme des SHAP float32 effectuée en float64).

Le mois horaire est dérivé de base_date (present au cache s01) : 1 si année 2024, sinon
mois calendaire + 1 — dérivation vérifiée identique à cal_mois_horaire canonique.

Sortie : tableaux/section_4_5_6/t_famille_mois_signe.csv
         (segment, mois, mois_label, famille, mean_shap_signe, n_obs, mean_pred, mean_bias).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
TAB = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
CACHE = Path(os.environ["R356_CACHE"]) if "R356_CACHE" in os.environ else DOSSIER / "_cache"

LIBELLE_FAMILLE = {
    "base_": "Desserte", "cal_": "Calendrier", "event_": "Événement",
    "histo_": "Historique de charge", "horaire_": "Horaire", "id_": "Identifiant",
    "ist_": "Régularité et correspondances", "meteo_": "Météo",
    "resa_": "Réservation de groupe", "simba_": "Structure tarifaire",
    "spatial_": "Contexte spatial", "target_": "Cible", "vmcv_": "Concurrence modale",
}
MOIS_LABEL = {1: "déc. 2024", 2: "janv. 2025", 3: "févr. 2025", 4: "mars 2025",
              5: "avr. 2025", 6: "mai 2025", 7: "juin 2025", 8: "juil. 2025",
              9: "août 2025", 10: "sept. 2025", 11: "oct. 2025", 12: "nov. 2025",
              13: "déc. 2025"}


def mois_horaire(base_date):
    bd = pd.to_datetime(base_date)
    return np.where(bd.dt.year == 2024, 1, bd.dt.month + 1)


def main() -> int:
    feats = json.loads((CACHE / "feats_order.json").read_text())["feats"]
    cb = pd.read_csv(CODEBOOK)
    fam_pref = dict(zip(cb["colonne"], cb["famille"]))
    fam = {f: LIBELLE_FAMILLE[fam_pref[f]] for f in feats}
    familles = sorted(set(fam.values()))
    fam_cols = {fa: [i for i, f in enumerate(feats) if fam[f] == fa] for fa in familles}

    rows = []
    max_ecart = 0.0
    for seg in ("bas", "haut"):
        shap = np.load(CACHE / f"shap_signed_{seg}.npy").astype("float64")   # somme en float64
        meta = pd.read_parquet(CACHE / f"meta_{seg}.parquet").reset_index(drop=True)
        mois = mois_horaire(meta["base_date"])
        # contribution signée agrégée par famille (n, n_familles)
        fam_contrib = {fa: shap[:, cols].sum(axis=1) for fa, cols in fam_cols.items()}
        for mo in range(1, 14):
            mask = mois == mo
            n = int(mask.sum())
            if n == 0:
                continue
            mp = float(meta.loc[mask, "_pred"].mean())
            mb = float(meta.loc[mask, "_bias"].mean())
            somme_fam = 0.0
            for fa in familles:
                mss = float(fam_contrib[fa][mask].mean())
                somme_fam += mss
                rows.append(dict(segment=seg, mois=mo, mois_label=MOIS_LABEL[mo], famille=fa,
                                 mean_shap_signe=mss, n_obs=n, mean_pred=mp, mean_bias=mb))
            ecart = abs(somme_fam - (mp - mb))
            max_ecart = max(max_ecart, ecart)
            assert ecart < 1e-4, f"additivité {seg} mois {mo} : écart {ecart:.2e} >= 1e-4"

    out = pd.DataFrame(rows)
    TAB.mkdir(parents=True, exist_ok=True)
    out.to_csv(TAB / "t_famille_mois_signe.csv", index=False)
    print(f"[OK] t_famille_mois_signe.csv ({len(out)} lignes ; "
          f"{out.segment.nunique()} segments × 13 mois × {len(familles)} familles)")
    print(f"     additivité : écart max Σfamilles vs (mean_pred - mean_bias) = {max_ecart:.2e} (< 1e-4 OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
