#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_profils_horaires.py — Figure §4.3.2 : profils horaires de la charge, bas vs haut.

Part de la charge journalière de 2e classe par heure de départ, normalisée par cellule
segment × type de jour (dénominateur = charge totale de la cellule sur les 24 h), en %.
Grain tronçon, ml_dataset H22-H25 (gel v2 ba493568, ADR-076). Deux panneaux à ordonnée
partagée : (a) jours ouvrables, (b) week-ends et fériés. Segment = spatial_segment ;
type de jour = « ouvrable » si cal_type_jour_3classes == "ouvrable", sinon « week-end »
(samedi ∪ dimanche/férié) — convention canonique compute_enrichissement_ba493568.py.

Repères : bandes de pointe 6-8 h et 16-18 h (définition rapport 432/B1b). Contrôle de
cohérence bloquant : part en pointe ouvrable bas=51,9 % / haut=30,5 % (verif_432 Q3).

Charte : figures_style (16 cm, 300 DPI, aucun titre embarqué, français accentué,
SOURCE_DATE_EPOCH figé, PNG byte-reproductible).
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
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402

CM = 1 / 2.54
ANNEES = ["H22", "H23", "H24", "H25"]
POINTE = [6, 7, 8, 16, 17, 18]
BANDES = [(6, 8), (16, 18)]
HEURES = list(range(5, 24))              # 5-23 affichées
BANDE_KW = dict(facecolor="#808080", alpha=0.10, edgecolor="none", zorder=0)
OUT = ROOT / "docs/memoire/figures/section_4_3_2/fig_profils_horaires.png"

# ── Données (grain tronçon, H22-H25) ────────────────────────────────────────
ml = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet", columns=[
    "horaire_annee_horaire", "spatial_segment", "cal_heure_depart",
    "cal_type_jour_3classes", "target_voyageurs_2eme_classe"])
ml = ml[ml["horaire_annee_horaire"].isin(ANNEES)].copy()
ml["t"] = ml["target_voyageurs_2eme_classe"].astype("float64")
ml["seg"] = ml["spatial_segment"].astype(str)
ml["h"] = ml["cal_heure_depart"].astype("Int64").astype(float)
ml["we"] = np.where(ml["cal_type_jour_3classes"].astype(str) == "ouvrable",
                    "ouvrable", "week-end")

profils, part_pointe = {}, {}
for seg in ("bas", "haut"):
    for grp in ("ouvrable", "week-end"):
        s = ml[(ml.seg == seg) & (ml.we == grp)].groupby("h").t.sum()
        s = s.reindex(range(24), fill_value=0.0)
        p = s / s.sum()
        profils[(seg, grp)] = p
        part_pointe[(seg, grp)] = float(p.loc[POINTE].sum() * 100)

# ── Contrôle de cohérence avec verif_432 Q3 (bloquant avant sortie) ─────────
ATTENDU = {("bas", "ouvrable"): 51.9, ("haut", "ouvrable"): 30.5,
           ("bas", "week-end"): 33.0, ("haut", "week-end"): 23.7}
print("Part de la charge journalière en pointe (6-8 h + 16-18 h) :")
for k, att in ATTENDU.items():
    got = part_pointe[k]
    ok = abs(round(got, 1) - att) <= 0.1
    print(f"  {k[0]:4} {k[1]:9} = {got:5.1f} %  (attendu {att} %)  {'OK' if ok else 'ÉCART'}")
    assert ok, f"Incohérence verif_432 Q3 pour {k}: {got:.1f} != {att}"
print("[cohérence verif_432 Q3 vérifiée]")

# ── Figure : deux panneaux à ordonnée partagée ──────────────────────────────
fs.apply_style()
fig, axes = plt.subplots(1, 2, figsize=(16 * CM, 8.5 * CM), sharey=True)

for ax, (grp, lettre) in zip(axes, [("ouvrable", "a"), ("week-end", "b")]):
    for (x0, x1) in BANDES:
        ax.axvspan(x0, x1, **BANDE_KW)
    for seg, col in [("bas", fs.COULEUR_BAS), ("haut", fs.COULEUR_HAUT)]:
        p = profils[(seg, grp)]
        ax.plot(HEURES, [p.loc[h] * 100 for h in HEURES], color=col, lw=1.6,
                marker="o", markersize=3.2, markeredgecolor="none",
                label=f"Segment {seg}")
    ax.set_xlim(5, 23)
    ax.set_xticks(list(range(5, 24, 2)))
    fs.lettre_panneau(ax, lettre)
    fs.finalize(ax, xlabel="Heure de départ (h)",
                ylabel="Part de la charge journalière (%)" if lettre == "a" else " ")

axes[0].set_ylim(0, None)
handles = [
    plt.Line2D([], [], color=fs.COULEUR_BAS, marker="o", markersize=3.2, lw=1.6,
               label="Segment bas (plaine)"),
    plt.Line2D([], [], color=fs.COULEUR_HAUT, marker="o", markersize=3.2, lw=1.6,
               label="Segment haut (crémaillère)"),
    Patch(facecolor="#808080", alpha=0.10, edgecolor="none",
          label="Fenêtres de pointe (6-8 h, 16-18 h)"),
]
fig.legend(handles=handles, loc="outside upper center", ncol=3, fontsize=8)

fs.save(fig, OUT)
plt.close(fig)
print(f"[OK] {OUT.relative_to(ROOT)}")
