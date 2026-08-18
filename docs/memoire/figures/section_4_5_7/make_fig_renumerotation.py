#!/usr/bin/env python3
"""Section 4.5.7 — fig_renumerotation.png.

PR-AUC (seuil 63) par strate de renumérotation (course connue / renumérotée) et par segment
(bas / haut / global) sur H25. Une course est « connue » si son numéro de train figure aux
années d'entraînement, « renumérotée » sinon (définition détaillée dans la légende APA du
document). Prévalences >63 par strate en note. Charte maison figstyle. Largeur 16 cm.

Strate dérivée du numéro de train (clé non dégénérée ; la clé composée numéro+heure est
dégénérée sur le gel, cf. c09). Source (outputs/confirmation/ uniquement, gel ba493568) :
c09_analyse_erreurs.json (c_connus_vs_renumerotes). LECTURE SEULE. Aucune annotation de conclusion.
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

SEGS = ["bas", "haut", "global"]
SEG_LBL = {"bas": "Segment bas", "haut": "Segment haut", "global": "Global"}
STRATES = [("connu", "Course connue", fs.OKABE_ITO["bleu"]),
           ("renumero", "Course renumérotée", fs.OKABE_ITO["orange"])]
CLE = "horaire_numero_train"


def pct(v):
    return f"{v * 100:.2f} %".replace(".", ",")


def main() -> int:
    c09 = json.loads((CONF / "c09_analyse_erreurs.json").read_text())
    c = c09["c_connus_vs_renumerotes"][CLE]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.5)
    x = np.arange(len(SEGS)); w = 0.38
    for i, (skey, slbl, col) in enumerate(STRATES):
        off = (i - 0.5) * w
        vals = [float(c[skey][s]["pr_auc"]) for s in SEGS]
        bars = ax.bar(x + off, vals, w, label=slbl, color=col, edgecolor="#333333", linewidth=0.5)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.3f}", xy=(b.get_x() + b.get_width() / 2, v), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=7, color="#444444")
    ax.set_xticks(x); ax.set_xticklabels([SEG_LBL[s] for s in SEGS])
    ax.set_xlabel("Périmètre d'évaluation (H25)")
    ax.set_ylabel("PR-AUC, seuil 63 (sans unité)")
    ax.set_ylim(0, max(float(c[k][s]["pr_auc"]) for k, _, _ in STRATES for s in SEGS) * 1.18)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=2, fontsize=8, handlelength=1.6)

    # Note factuelle : prévalence >63 par strate × segment (lue de c09, non codée en dur)
    def strate_note(skey, lbl):
        return (f"{lbl} : bas {pct(c[skey]['bas']['prevalence'])} · haut {pct(c[skey]['haut']['prevalence'])} "
                f"· global {pct(c[skey]['global']['prevalence'])}")
    note = ("Prévalence >63 par strate. " + strate_note("connu", "Course connue")
            + ". " + strate_note("renumero", "Renumérotée") + ".")
    ax.annotate(note, xy=(0.5, -0.30), xycoords="axes fraction", ha="center", va="top",
                fontsize=7, color="#555555")

    p = fs.save_fig(fig, "fig_renumerotation", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
