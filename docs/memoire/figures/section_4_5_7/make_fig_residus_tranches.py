#!/usr/bin/env python3
"""Section 4.5.7 — fig_residus_tranches.png.

Biais moyen de prediction (pred − charge observee) par tranche de charge
(<= 63 / 64-93 / 94-165 / > 165) et par segment (bas / haut / global) sur H25. Les
bornes suivent le seuil de surcharge applique en strictement superieur (y > 63) :
une charge de 63 places assises n'est pas une surcharge et releve de la tranche
basse. La tranche > 165 (queue de distribution) est mise en evidence. Barres
groupees, charte maison figstyle. Largeur 16 cm.

Source (outputs/confirmation/ uniquement, gel ba493568) : c09_analyse_erreurs.json
(a_residus_par_tranche_charge). LECTURE SEULE. Aucune annotation de conclusion.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CONF = ROOT / "outputs" / "confirmation"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

TRANCHES = ["<= 63", "64-93", "94-165", "> 165"]      # clés JSON (c09)
TRANCHES_LBL = {"<= 63": "≤ 63", "64-93": "64-93",     # libellés d'axe (typographie mémoire)
                "94-165": "94-165", "> 165": "> 165"}
SEGS = ["bas", "haut", "global"]
SEG_LBL = {"bas": "Segment bas", "haut": "Segment haut", "global": "Global"}


def main() -> int:
    c09 = json.loads((CONF / "c09_analyse_erreurs.json").read_text())
    a = c09["a_residus_par_tranche_charge"]
    seg_col = {"bas": fs.COULEUR_BAS, "haut": fs.COULEUR_HAUT, "global": fs.OKABE_ITO["noir"]}

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.52)
    x = np.arange(len(TRANCHES)); w = 0.26
    # mise en evidence de la tranche 166+ (bande de fond)
    ax.axvspan(x[-1] - 0.5, x[-1] + 0.5, color="#f0e442", alpha=0.20, zorder=0)
    for i, s in enumerate(SEGS):
        off = (i - 1) * w
        vals = [float(a[t][s]["biais_moyen"]) for t in TRANCHES]
        ax.bar(x + off, vals, w, label=SEG_LBL[s], color=seg_col[s],
               edgecolor="#333333", linewidth=0.5)
    ax.axhline(0, color="#000000", linewidth=0.9)
    n166 = a[TRANCHES[-1]]["global"]["n"]
    # Annotation hors de la zone des barres : au-dessus du cadre de surbrillance.
    ax.annotate(f"Tranche > 165 ({n166} observations)", xy=(x[-1], ax.get_ylim()[1]),
                xytext=(0, 5), textcoords="offset points", ha="center", va="bottom",
                fontsize=7.5, color="#7a6a00", annotation_clip=False)
    ax.set_xticks(x); ax.set_xticklabels([f"{TRANCHES_LBL[t]} voy." for t in TRANCHES])
    ax.set_xlabel("Tranche de charge observée de 2e classe (voyageurs)")
    ax.set_ylabel("Biais moyen de prédiction (voyageurs)")
    ax.legend(loc="lower left", fontsize=8, ncol=3, handlelength=1.3, columnspacing=1.0)
    p = fs.save_fig(fig, "fig_residus_tranches", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
