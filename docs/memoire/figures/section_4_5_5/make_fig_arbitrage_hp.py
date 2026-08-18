#!/usr/bin/env python3
"""Section 4.5.5 — fig_arbitrage_hp.png.

Arbitrage entre gain de R2 global et zone >63, des configurations à réglage Optuna
(XGBoost / LightGBM / CatBoost) relativement au modèle retenu (origine). Deux panneaux :
(a) écart de PR-AUC segment haut ; (b) écart de biais>63 segment haut ; en abscisse,
l'écart de R2 global. Charte maison figstyle. Largeur 16 cm.

Nommage mémoire : modèle final = « Modèle retenu » ; challengers = « <Algo> (réglage
Optuna) ». Les identifiants (CF09, best_params, hash) restent dans les JSON de traçabilité.

Source (outputs/confirmation/ uniquement, gel ba493568) : c10_comparatif_algos.json.
LECTURE SEULE. Aucune annotation de conclusion (points chiffrés seuls).
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

TUNES = [("xgboost_bestparams", "XGBoost", "XGBoost (réglage Optuna)", fs.OKABE_ITO["bleu"]),
         ("lightgbm_bestparams", "LightGBM", "LightGBM (réglage Optuna)", fs.OKABE_ITO["vert"]),
         ("catboost_bestparams", "CatBoost", "CatBoost (réglage Optuna)", fs.OKABE_ITO["mauve"])]
REF = "canonique_cf09_gel"


def main() -> int:
    m = json.loads((CONF / "c10_comparatif_algos.json").read_text())["metriques_h25"]
    dr2 = {k: m[k]["global"]["r2"] - m[REF]["global"]["r2"] for k, *_ in TUNES}
    dprauc_h = {k: m[k]["haut"]["pr_auc"] - m[REF]["haut"]["pr_auc"] for k, *_ in TUNES}
    dbiais_h = {k: m[k]["haut"]["bias_gt63"] - m[REF]["haut"]["bias_gt63"] for k, *_ in TUNES}

    fs.apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(fs.LARGE, fs.LARGE * 0.46))
    fig.subplots_adjust(wspace=0.42)
    panels = [(axes[0], dprauc_h, "Écart de PR-AUC haut (sans unité)", "a"),
              (axes[1], dbiais_h, "Écart de biais>63 haut (voyageurs)", "b")]
    for ax, dy, ylabel, lettre in panels:
        ax.axhline(0, color="#888888", linewidth=0.8, zorder=1)
        ax.axvline(0, color="#888888", linewidth=0.8, zorder=1)
        ax.scatter([0], [0], marker="D", s=55, color=fs.OKABE_ITO["noir"], zorder=3,
                   label="Modèle retenu (référence)")
        for k, court, long, col in TUNES:
            ax.scatter([dr2[k]], [dy[k]], s=60, color=col, zorder=4, label=long)
            ax.annotate(court, xy=(dr2[k], dy[k]), xytext=(4, 5), textcoords="offset points",
                        fontsize=7.5, color="#333333")
        ax.set_xlabel("Écart de R² global (sans unité)")
        ax.set_ylabel(ylabel)
        ax.margins(x=0.18, y=0.22)
        ax.text(0.0, 1.04, f"({lettre})", transform=ax.transAxes, fontweight="bold",
                fontsize=11, ha="left", va="bottom")
    axes[0].legend(loc="upper left", fontsize=7, handlelength=1.2, framealpha=0.9)
    p = fs.save_fig(fig, "fig_arbitrage_hp", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
