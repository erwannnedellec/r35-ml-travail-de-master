#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fig_heatmap_surcharge_mensuelle (§4.3.3) — heatmap mois horaire × année horaire du
taux de surcharge de 2ᵉ classe (> 63 voy., grain tronçon), H16-H25.

Source de données : docs/memoire/verifs/section_4_3_3/verif_433_matriceB_surcharge.csv (version étendue
H16-H25, produite par verif_433_rythmes.py sur la table amont stage_10, cardinalité
2 360 762). 13 lignes (mois horaires, décembres distingués) × 10 colonnes (H16..H25).

Charte : src/memoire/figstyle.py — largeur 16 cm, 300 DPI, bbox tight, sans titre embarqué.
Rampe séquentielle chaude jaune → orange → rouge (YlOrRd), PAS divergente.
Valeurs en cellule (un chiffre après la virgule), texte en contraste automatique. Cellule H22×Sep
hachurée (n = 2 960 vs ~27 000 en mois plein, trou de comptage de sept. 2022), seule cellule non
représentative des 130. Pas d'encadré de périmètre : la figure vit en §4.3, avant la décision
de périmètre.

Reproductibilité byte-à-byte : SOURCE_DATE_EPOCH=1782000000 posé en tête (avant matplotlib) ;
backend Agg ; deux exécutions → même empreinte.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")  # byte-repro, avant matplotlib

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

SRC = ROOT / "docs/memoire/verifs/section_4_3_3/verif_433_matriceB_surcharge.csv"
DOSSIER = ROOT / "docs/memoire/figures/section_4_3_3"

# Libellés de mois horaire, français accentué, décembres distingués (ordre poste 1..13).
MOIS_FR = ["déc. (ouv.)", "janv.", "févr.", "mars", "avr.", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc. (clôt.)"]
ANNEES = [f"H{n}" for n in range(16, 26)]
# Cellule non représentative (trou de comptage APC, sept. 2022).
CELL_HACHUREE = ("H22", "sept.")   # (année, libellé mois)


def _text_color(rgba):
    """Gris auto-contrasté : sombre sur cellule claire, clair sur cellule foncée."""
    r, g, b = rgba[:3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b   # luminance relative sRGB approx.
    return "#222222" if lum > 0.55 else "#ececec"


def main():
    # ------------------------------------------------------------------ données
    df = pd.read_csv(SRC, index_col=0)
    df = df[ANNEES]                       # ordre colonnes H16..H25
    M = df.to_numpy(dtype=float)          # 13 x 10, ligne 0 = déc. (ouv.)
    nrow, ncol = M.shape
    vmax = float(np.ceil(np.nanmax(M) * 2) / 2)   # 9.29 -> 9.5

    fs.apply_style()
    cmap = plt.get_cmap("YlOrRd")         # rampe chaude séquentielle jaune -> orange -> rouge
    norm = plt.Normalize(vmin=0.0, vmax=vmax)

    fig, ax = fs.new_fig(largeur=fs.LARGE, hauteur=12.0 * fs.CM)
    ax.imshow(M, cmap=cmap, norm=norm, aspect="auto", interpolation="nearest",
              origin="upper")

    # séparateurs de cellules (blancs, discrets) ; pas de grille de fond.
    ax.grid(False)
    ax.set_xticks(np.arange(-0.5, ncol, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, nrow, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", length=0)
    for s in ax.spines.values():
        s.set_visible(False)

    # ------------------------------------------------------------- axes / ticks
    ax.set_xticks(range(ncol))
    ax.set_xticklabels(ANNEES)
    ax.set_yticks(range(nrow))
    ax.set_yticklabels(MOIS_FR)
    ax.tick_params(length=0)
    ax.set_xlabel("Année horaire")
    ax.set_ylabel("Mois horaire")

    # ------------------------------------------------------- valeurs en cellule
    j_hach = ANNEES.index(CELL_HACHUREE[0])
    i_hach = MOIS_FR.index(CELL_HACHUREE[1])
    for i in range(nrow):
        for j in range(ncol):
            v = M[i, j]
            if np.isnan(v):
                continue
            txt = f"{v:.1f}".replace(".", ",")
            ax.text(j, i, txt, ha="center", va="center", fontsize=6.6,
                    color=_text_color(cmap(norm(v))))

    # ------------------------------------------- cellule hachurée non représentative
    ax.add_patch(Rectangle((j_hach - 0.5, i_hach - 0.5), 1, 1, fill=False,
                           hatch="////", edgecolor="#3d3d3d", linewidth=0.0, zorder=3))

    # --------------------------------------------------------------- colorbar
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                        fraction=0.045, pad=0.03)
    cbar.set_label("Part des tronçons en surcharge (2ᵉ classe > 63 voy.), en %")
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(length=0)

    # ----------------------------------------------------- note grise discrète
    ax.annotate(
        "Cellule hachurée : H22 × sept., n = 2 960 tronçons contre ~27 000 en mois plein\n"
        "(trou de comptage de sept. 2022) ; seule cellule non représentative des 130.",
        xy=(0.0, -0.14), xycoords="axes fraction", ha="left", va="top",
        fontsize=6.8, color="#777777")

    p = fs.save_fig(fig, "fig_heatmap_surcharge_mensuelle", DOSSIER, largeur=fs.LARGE)
    print("[OK]", p)
    return p


if __name__ == "__main__":
    main()
