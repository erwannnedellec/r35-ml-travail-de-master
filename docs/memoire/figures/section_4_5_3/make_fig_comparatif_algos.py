#!/usr/bin/env python3
"""Section 4.5.3 — fig_comparatif_algos.png.

R2 global et PR-AUC globale (seuil 63) par algorithme sur H25 : canonique CF09 (gel),
Random Forest defaut, XGBoost / LightGBM / CatBoost aux best_params. La baseline naive
est exclue de l'axe (elle ecraserait l'echelle) et signalee en note factuelle.
Barres groupees, charte maison figstyle. Largeur 16 cm.

Source (outputs/confirmation/ uniquement, gel ba493568) : c10_comparatif_algos.json (ADR-072).
LECTURE SEULE. Aucune annotation de conclusion.
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

ALGOS = [("canonique_cf09_gel", "Modèle retenu"),
         ("randomforest_defaut", "Random Forest\n(défaut)"),
         ("xgboost_bestparams", "XGBoost\n(réglage Optuna)"),
         ("lightgbm_bestparams", "LightGBM\n(réglage Optuna)"),
         ("catboost_bestparams", "CatBoost\n(réglage Optuna)")]


def main() -> int:
    c10 = json.loads((CONF / "c10_comparatif_algos.json").read_text())
    m = c10["metriques_h25"]
    r2 = [float(m[k]["global"]["r2"]) for k, _ in ALGOS]
    prauc = [float(m[k]["global"]["pr_auc"]) for k, _ in ALGOS]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.52)
    x = np.arange(len(ALGOS)); w = 0.38
    b1 = ax.bar(x - w / 2, r2, w, label="R² global (sans unité)", color=fs.OKABE_ITO["bleu"],
                edgecolor="#333333", linewidth=0.5)
    b2 = ax.bar(x + w / 2, prauc, w, label="PR-AUC globale, seuil 63 (sans unité)",
                color=fs.OKABE_ITO["vert"], edgecolor="#333333", linewidth=0.5)
    for bars, vals in ((b1, r2), (b2, prauc)):
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.3f}", xy=(b.get_x() + b.get_width() / 2, v), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=6.8, color="#444444")
    ax.set_xticks(x); ax.set_xticklabels([lbl for _, lbl in ALGOS], fontsize=8)
    ax.set_xlabel("Algorithme (architecture segmentée, évaluation H25)")
    ax.set_ylabel("Score (sans unité)")
    ax.set_ylim(0, 0.72)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=2, fontsize=8, handlelength=1.6)
    # Baseline naïve exclue de l'échelle : note APA (chiffres) placée dans le document.
    p = fs.save_fig(fig, "fig_comparatif_algos", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
