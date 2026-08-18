#!/usr/bin/env python3
"""§4.6.3 — Charge PRÉDITE de 2e classe, par tronçon, du même cas illustratif.

Figure B du couple 4.6.2 / 4.6.3 (même course, mêmes axes, même échelle Y que la fig. A).
Barres de la charge 2e classe PRÉDITE par tronçon (modèles figés), couleurs par segment.
Le tronçon portant le SCORE de course (= max des prédictions) est mis en évidence
(bordure renforcée + hachures), annoté « score de course » avec sa valeur. Trois traits
horizontaux de styles distincts marquent le menu de décision — b (51,31), c (64,12),
a′ (78,99) : le lecteur voit que le score franchit b et c mais PAS a′. Aucun trait à 63.

Données : `cas_4_6_troncons.csv` (+ `cas_4_6_meta.json`), produits par
`docs/memoire/verifs/section_4_6/selection_cas_4_6.py`. LECTURE SEULE ; PNG 300 DPI
reproductible (SOURCE_DATE_EPOCH). Charte : `scripts/figures_style.py`.
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
OUT = ROOT / "docs/memoire/figures/section_4_6_3/fig_charge_predite_cas.png"
YMAX = 112                      # échelle Y COMMUNE aux figures A et B (comparabilité)

# seuils du menu (mêmes couleurs Okabe-Ito que la figure PR de la couche 2, decision.py)
MENU = [
    ("a_prime", "Seuil a′ (iso-volume) : 78,99", "#009E73", (0, (5, 1))),        # tirets longs
    ("c",       "Seuil c (haute précision) : 64,12", "#E69F00", (0, (4, 1, 1, 1))),  # tiret-point
    ("b",       "Seuil b (rappel renforcé) : 51,31", "#CC79A7", (0, (1, 1.4))),   # pointillés
]

def vfr(x, dec=2):
    return f"{x:.{dec}f}".replace(".", ",")

# ---- données du cas (support commun aux deux figures) ----------------------------
t = pd.read_csv(VERIF / "cas_4_6_troncons.csv")
meta = json.loads((VERIF / "cas_4_6_meta.json").read_text())
s = meta["statut_menu"]
TAU = {"a_prime": s["a_prime_iso_volume"]["seuil"], "c": s["c_haute_precision"]["seuil"],
       "b": s["b_rappel_renforce"]["seuil"]}
x = range(len(t))
pred = t["charge_predite"].to_numpy()
colors = [fs.COULEUR_BAS if seg == "bas" else fs.COULEUR_HAUT for seg in t["segment"]]
i_score = int(t.index[t["porteur_score"]][0])
score = float(pred[i_score])

# ============================================================== figure
fs.apply_style()
fig, ax = plt.subplots(figsize=(7.4, 4.4))

bars = ax.bar(x, pred, color=colors, edgecolor="white", linewidth=0.6, zorder=3, width=0.82)
d = bars[i_score]
d.set_edgecolor("#000000"); d.set_linewidth(2.2); d.set_hatch("////"); d.set_zorder(4)

# trois seuils du menu (styles + couleurs distincts) DEVANT les barres — PAS de trait à 63
menu_handles = []
for key, lib, col, dash in MENU:
    ax.axhline(TAU[key], color=col, linestyle=dash, linewidth=1.7, zorder=5)
    menu_handles.append(Line2D([], [], color=col, linestyle=dash, linewidth=1.7, label=lib))

# score de course : valeur + annotation
ax.text(i_score, score + 1.5, vfr(score, 1), ha="center", va="bottom",
        fontsize=9, fontweight="bold", zorder=5)
ax.annotate("score de course", xy=(i_score, score), xytext=(i_score - 3.6, score + 20),
            ha="center", va="bottom", fontsize=8.5, color="#222222",
            arrowprops=dict(arrowstyle="-", color="#444444", lw=0.9,
                            connectionstyle="arc3,rad=-0.2"))

# axes / graduations (IDENTIQUES à la figure A)
ax.set_xticks(list(x))
ax.set_xticklabels(t["gare_depart"], rotation=45, ha="right", fontsize=8)
ax.set_xlim(-0.7, len(t) - 0.3)
ax.set_ylim(0, YMAX)
ax.grid(axis="x", visible=False)
fs.finalize(ax, xlabel="Gare de départ du tronçon (ordre de la marche)",
            ylabel="Charge prédite de 2e classe (voyageurs)", periode="H25")

seg_handles = [
    Patch(facecolor=fs.COULEUR_BAS, label="Segment bas (plaine)"),
    Patch(facecolor=fs.COULEUR_HAUT, label="Segment haut (crémaillère)"),
    Patch(facecolor="white", edgecolor="#000000", linewidth=1.6, hatch="////",
          label="Tronçon portant le score"),
]
ax.legend(handles=seg_handles + menu_handles, loc="upper left", fontsize=7.6,
          framealpha=0.92, borderpad=0.6, ncol=1)

fs.save(fig, OUT)
plt.close(fig)
print("FIGURE:", OUT)
print(f"cas {meta['cas_retenu']['numero_train']} | score={vfr(score)} sur "
      f"{meta['cas_retenu']['troncon_determinant']} | franchit b,c pas a′")
