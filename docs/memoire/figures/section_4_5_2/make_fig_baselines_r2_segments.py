#!/usr/bin/env python3
"""Section 4.5.2 — fig_baselines_r2_segments.png.

Barres groupees du R2 H25 par segment (bas / haut / global) et par bras :
baseline naive (moyenne historique), modele M0 (APC + calendrier), Ridge (158 var.),
modele final (reference). Charte maison figstyle. Largeur 16 cm.

Sources (outputs/confirmation/ uniquement, gel ba493568) :
  - c01_metriques_finales.json          : modele final (reference)
  - c02_baseline_m0.json                : M0
  - c03_baseline_lineaire.json          : Ridge
  - c10_comparatif_algos.json           : baseline naive
LECTURE SEULE. Aucune annotation de conclusion.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"   # reproductibilite byte-a-byte (charte)
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

SEG = ["bas", "haut", "global"]
SEG_LABELS = ["Segment bas", "Segment haut", "Global"]


def load(name):
    return json.loads((CONF / name).read_text())


def main() -> int:
    c01, c02, c03, c10 = load("c01_metriques_finales.json"), load("c02_baseline_m0.json"), \
        load("c03_baseline_lineaire.json"), load("c10_comparatif_algos.json")
    r2 = lambda d, seg: float(d[seg]["r2"])
    naive = c10["metriques_h25"]["baseline_naive_moyenne_historique"]
    bras = [
        ("Baseline naïve (moyenne historique)", {s: r2(naive, s) for s in SEG}, fs.OKABE_ITO["jaune"], None),
        ("Modèle M0 (APC + calendrier)", {s: r2(c02["metriques_h25"], s) for s in SEG}, fs.OKABE_ITO["bleu_ciel"], None),
        ("Régression Ridge (158 variables)", {s: r2(c03["metriques_h25"], s) for s in SEG}, fs.OKABE_ITO["orange"], None),
        ("Modèle retenu (référence)", {s: r2(c01["metriques_h25"], s) for s in SEG}, fs.OKABE_ITO["noir"], "//"),
    ]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.55)
    x = np.arange(len(SEG)); w = 0.2
    for i, (nom, vals, col, hatch) in enumerate(bras):
        off = (i - (len(bras) - 1) / 2) * w
        bars = ax.bar(x + off, [vals[s] for s in SEG], w, label=nom, color=col,
                      edgecolor="#333333", linewidth=0.5, hatch=hatch)
        for b, s in zip(bars, SEG):
            ax.annotate(f"{vals[s]:.3f}", xy=(b.get_x() + b.get_width() / 2, vals[s]),
                        xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                        fontsize=6.5, color="#444444", rotation=90)
    ax.set_xticks(x); ax.set_xticklabels(SEG_LABELS)
    ax.set_xlabel("Périmètre d'évaluation (H25)")
    ax.set_ylabel("Coefficient de détermination R² (sans unité)")
    ax.set_ylim(0, max(0.68, max(v[s] for _, v, _, _ in bras for s in SEG) * 1.10))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=2, fontsize=8,
              handlelength=1.6, columnspacing=1.4)
    p = fs.save_fig(fig, "fig_baselines_r2_segments", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
