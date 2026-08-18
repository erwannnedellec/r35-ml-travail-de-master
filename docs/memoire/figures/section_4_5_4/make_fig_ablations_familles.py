#!/usr/bin/env python3
"""Section 4.5.4 — fig_ablations_familles.png.

Ecart de R2 H25 par segment (bas / haut / global) pour deux familles de variables :
  - SIMBA   : retrait (158 contre 170 variables)        source c06_ablation_simba.json
  - STATENT : réintégration (162 contre 158 variables)  source c07_reintegration_statent.json
Barres horizontales divergentes autour de zero. Charte maison figstyle. Largeur 16 cm.

Sources : outputs/confirmation/ uniquement (gel ba493568). LECTURE SEULE.
Aucune annotation de conclusion (seuls les deltas chiffres).
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
from matplotlib.patches import Patch  # noqa: E402

SEGS = ["bas", "haut", "global"]
SEG_LBL = {"bas": "Segment bas", "haut": "Segment haut", "global": "Global"}


def main() -> int:
    c06 = json.loads((CONF / "c06_ablation_simba.json").read_text())
    c07 = json.loads((CONF / "c07_reintegration_statent.json").read_text())
    fam = [("SIMBA : retrait (158 contre 170 variables)", c06["delta_r2_158f_moins_170f"]),
           ("STATENT : réintégration (162 contre 158 variables)", c07["delta_r2_162f_moins_158f"])]
    seg_col = {"bas": fs.COULEUR_BAS, "haut": fs.COULEUR_HAUT, "global": fs.OKABE_ITO["noir"]}

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.42)
    yt, ytl, gap = [], [], 1
    y = 0
    for fname, deltas in fam:
        y0 = y
        for s in SEGS:
            v = float(deltas[s])
            ax.barh(y, v, height=0.7, color=seg_col[s], edgecolor="#333333", linewidth=0.5, zorder=2)
            ax.annotate(f"{v:+.4f}", xy=(v, y), xytext=(4 if v >= 0 else -4, 0),
                        textcoords="offset points", ha="left" if v >= 0 else "right",
                        va="center", fontsize=7, color="#444444")
            yt.append(y); ytl.append(SEG_LBL[s]); y += 1
        # ligne de référence x=0 PROPRE au groupe (n'atteint pas l'étiquette de famille)
        ax.plot([0, 0], [y0 - 0.45, y0 + 2 + 0.45], color="#000000", linewidth=1.0, zorder=1)
        # étiquette de famille au-dessus du groupe, hors de la ligne de référence
        ax.annotate(fname, xy=(0, y0 - 0.45), xytext=(0, 5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#333333",
                    annotation_clip=False)
        y += gap
    ax.set_yticks(yt); ax.set_yticklabels(ytl, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Écart de R² sur H25 (sans unité)")
    ax.grid(True, axis="x"); ax.grid(False, axis="y")
    xabs = max(abs(float(d[s])) for _, d in fam for s in SEGS)
    ax.set_xlim(-xabs * 1.6, xabs * 1.6)
    ax.legend(handles=[Patch(facecolor=seg_col[s], edgecolor="#333333", label=SEG_LBL[s]) for s in SEGS],
              loc="upper left", fontsize=8, ncol=1, handlelength=1.3)
    p = fs.save_fig(fig, "fig_ablations_familles", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
