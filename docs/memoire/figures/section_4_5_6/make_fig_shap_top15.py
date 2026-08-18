#!/usr/bin/env python3
"""Section 4.5.6 — fig_shap_top15_bas.png et fig_shap_top15_haut.png.

Top 15 des variables par importance SHAP moyenne (mean|contribution|) sur H25, par
segment, en barres horizontales. Noms de variables traduits via le codebook canonique
(libelle_fr). Charte maison figstyle. Largeur 16 cm chacune.

Source des donnees (outputs/confirmation/ uniquement, gel ba493568) :
  c08_shap_ranks_{bas,haut}.csv (mean_abs_shap, rang).
Traduction des noms : outputs/codebook_canonique_ba493568.csv (mapping sanctionne, libelles seuls).
LECTURE SEULE. Aucune annotation de conclusion.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CONF = ROOT / "outputs" / "confirmation"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

TOP = 15
SEG_COL = {"bas": fs.COULEUR_BAS, "haut": fs.COULEUR_HAUT}


def libelles():
    cb = pd.read_csv(CODEBOOK).set_index("colonne")["libelle_fr"]
    return cb.to_dict()


def fig_segment(seg, lib):
    df = pd.read_csv(CONF / f"c08_shap_ranks_{seg}.csv").sort_values("rang").head(TOP)
    noms = [str(lib.get(f, f)) for f in df["feature"]]
    vals = df["mean_abs_shap"].to_numpy()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.62)
    y = range(len(noms))
    ax.barh(list(y), vals, color=SEG_COL[seg], edgecolor="#333333", linewidth=0.5)
    ax.set_yticks(list(y)); ax.set_yticklabels(noms, fontsize=8)
    ax.invert_yaxis()   # rang 1 en haut
    for yi, v in zip(y, vals):
        ax.annotate(f"{v:.2f}", xy=(v, yi), xytext=(3, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=7, color="#444444")
    ax.set_xlabel("Importance SHAP moyenne, |contribution| (voyageurs)")
    ax.grid(True, axis="x"); ax.grid(False, axis="y")
    ax.set_xlim(0, vals.max() * 1.15)
    return fig


def main() -> int:
    fs.apply_style()
    lib = libelles()
    for seg in ("bas", "haut"):
        fig = fig_segment(seg, lib)
        p = fs.save_fig(fig, f"fig_shap_top15_{seg}", DOSSIER, largeur=fs.LARGE)
        plt.close(fig)
        print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
