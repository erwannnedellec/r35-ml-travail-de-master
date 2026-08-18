#!/usr/bin/env python3
"""§4.6.2 — Charge OBSERVÉE de 2e classe, par tronçon, du cas illustratif.

Figure A du couple 4.6.2 / 4.6.3 (même course, mêmes axes). Barres de la charge 2e
classe MESURÉE (APC) par tronçon, dans l'ordre de la marche, couleurs par segment
(bleu bas / vermillon haut, frontière à Blonay). Trait horizontal en tirets au seuil de
mesure (63 places assises). Le tronçon déterminant (charge maximale, qui porte aussi le
score du modèle en fig. 4.6.3) est mis en évidence (bordure renforcée + hachures).

Données : `cas_4_6_troncons.csv` (+ `cas_4_6_meta.json`), produits par
`docs/memoire/verifs/section_4_6/selection_cas_4_6.py` (sélection déterministe, prédictions
canoniques). LECTURE SEULE ; écrit un PNG 300 DPI reproductible (SOURCE_DATE_EPOCH).
Charte : `scripts/figures_style.py` (palette Okabe-Ito, aucun titre embarqué).
"""
import os, sys, json
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

VERIF = ROOT / "docs/memoire/verifs/section_4_6_2"
OUT = ROOT / "docs/memoire/figures/section_4_6_2/fig_charge_observee_cas.png"
YMAX = 112                      # échelle Y COMMUNE aux figures A et B (comparabilité)
SEUIL_MESURE = 63

# ---- données du cas (support commun aux deux figures) ----------------------------
t = pd.read_csv(VERIF / "cas_4_6_troncons.csv")
meta = json.loads((VERIF / "cas_4_6_meta.json").read_text())
x = range(len(t))
obs = t["charge_observee_2c"].to_numpy()
colors = [fs.COULEUR_BAS if s == "bas" else fs.COULEUR_HAUT for s in t["segment"]]
i_det = int(t.index[t["porteur_score"]][0])                 # tronçon déterminant (= porteur du score)
obs_max = int(obs.max())

# ============================================================== figure
fs.apply_style()
fig, ax = plt.subplots(figsize=(7.4, 4.4))

bars = ax.bar(x, obs, color=colors, edgecolor="white", linewidth=0.6, zorder=3, width=0.82)

# tronçon déterminant : bordure renforcée + hachures
d = bars[i_det]
d.set_edgecolor("#000000"); d.set_linewidth(2.2); d.set_hatch("////"); d.set_zorder(4)

# seuil de mesure (63) — trait en tirets DEVANT les barres, libellé demandé
ax.axhline(SEUIL_MESURE, color="#000000", linestyle="--", linewidth=1.2, zorder=5)

# valeur du max + annotation « tronçon déterminant »
ax.text(i_det, obs_max + 1.5, str(obs_max), ha="center", va="bottom",
        fontsize=9, fontweight="bold", zorder=5)
ax.annotate("tronçon déterminant", xy=(i_det, obs_max), xytext=(i_det - 3.4, obs_max + 12),
            ha="center", va="bottom", fontsize=8.5, color="#222222",
            arrowprops=dict(arrowstyle="-", color="#444444", lw=0.9,
                            connectionstyle="arc3,rad=-0.2"))

# axes / graduations
ax.set_xticks(list(x))
ax.set_xticklabels(t["gare_depart"], rotation=45, ha="right", fontsize=8)
ax.set_xlim(-0.7, len(t) - 0.3)
ax.set_ylim(0, YMAX)
ax.grid(axis="x", visible=False)
fs.finalize(ax, xlabel="Gare de départ du tronçon (ordre de la marche)",
            ylabel="Charge observée de 2e classe (voyageurs)", periode="H25")

legende = [
    Patch(facecolor=fs.COULEUR_BAS, label="Segment bas (plaine)"),
    Patch(facecolor=fs.COULEUR_HAUT, label="Segment haut (crémaillère)"),
    Patch(facecolor="white", edgecolor="#000000", linewidth=1.6, hatch="////",
          label="Tronçon déterminant"),
    Line2D([], [], color="#000000", linestyle="--", linewidth=1.2,
           label="Seuil de mesure (63 places assises)"),
]
ax.legend(handles=legende, loc="upper left", fontsize=8, framealpha=0.92, borderpad=0.6)

fs.save(fig, OUT)
plt.close(fig)
print("FIGURE:", OUT)
print(f"cas {meta['cas_retenu']['numero_train']} du {meta['cas_retenu']['date']} | "
      f"max observé={obs_max} sur {meta['cas_retenu']['troncon_determinant']}")
