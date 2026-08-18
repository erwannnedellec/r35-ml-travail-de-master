#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_distribution_charge.py — Figure §4.3.4 : distribution de la charge de 2e classe.

Histogramme (ordonnée logarithmique) de la charge de 2e classe au grain tronçon,
périmètre H22-H25 (data/processed/ml_dataset.parquet, gel v2 ba493568, ADR-076 ;
1 141 984 tronçons). Trois repères verticaux — 63 (assises, ADR-060), 94 (saturation
nominale), 166 (projection de la limite massique) — et queue conservée jusqu'à 206.

Charte : figures_style (16 cm, 300 DPI, aucun titre embarqué, SOURCE_DATE_EPOCH figé,
PNG byte-reproductible). Bin unitaire (1 voyageur) : chaque barre = un niveau de charge.
"""
from __future__ import annotations
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402

CM = 1 / 2.54
SEUIL_ASSISES, SEUIL_SATURATION, SEUIL_MASSIQUE = 63, 94, 166
ANNEES = ["H22", "H23", "H24", "H25"]
OUT = ROOT / "docs/memoire/figures/section_4_3_4/fig_distribution_charge.png"

# ── Données (grain tronçon, H22-H25) ────────────────────────────────────────
df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet",
                     columns=["horaire_annee_horaire", "target_voyageurs_2eme_classe"])
charge = df.loc[df["horaire_annee_horaire"].isin(ANNEES),
                "target_voyageurs_2eme_classe"].astype("float64")
n_obs = int(len(charge))
c_max = int(charge.max())
n_extreme = int((charge >= SEUIL_MASSIQUE).sum())
print(f"n_obs={n_obs} | charge_max={c_max} | obs>=166={n_extreme}")

# ── Figure ──────────────────────────────────────────────────────────────────
fs.apply_style()
fig, ax = plt.subplots(figsize=(16 * CM, 10 * CM))

bins = np.arange(0, c_max + 2)                       # bornes unitaires 0..206
ax.hist(charge, bins=bins, color=fs.COULEUR_BAS, edgecolor="none")
ax.set_yscale("log")
ax.set_xlim(0, 210)
ax.set_ylim(0.7, None)

# repères verticaux sobres (libellés courts, verticaux le long du trait)
for x, lab in [(SEUIL_ASSISES, "assises · 63"),
               (SEUIL_SATURATION, "saturation · 94"),
               (SEUIL_MASSIQUE, "limite technique · 166")]:
    ax.axvline(x, color="#444444", linestyle="--", linewidth=1.0, zorder=3)
    ax.annotate(lab, xy=(x, 1.0), xycoords=("data", "axes fraction"),
                xytext=(3, -5), textcoords="offset points", rotation=90,
                va="top", ha="left", fontsize=8, color="#555555")

fs.finalize(ax, xlabel="Charge de 2e classe (voyageurs par tronçon)",
            ylabel="Nombre de tronçons (échelle logarithmique)", periode="H22-H25")
fs.save(fig, OUT)
plt.close(fig)
print(f"[OK] {OUT.relative_to(ROOT)}")
