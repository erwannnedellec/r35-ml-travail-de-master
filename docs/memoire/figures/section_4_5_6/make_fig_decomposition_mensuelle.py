#!/usr/bin/env python3
"""Section 4.5.6 (extension) — BROUILLON f_decomposition_mensuelle.

Courbes SHAP signées mensuelles par famille fonctionnelle, un panneau par segment
(bas / haut), sur les 13 mois horaires de H25 (deux décembres distingués). Ligne zéro.
Les familles d'amplitude < 0,3 voyageur (max |moyenne mensuelle| sur segments×mois) sont
regroupées en « Autres » (note en légende). Source : t_famille_mois_signe.csv (s05).
Charte figstyle (Okabe-Ito, 300 DPI, sans titre embarqué). Aucune interprétation.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CSV = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6" / "t_famille_mois_signe.csv"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SEUIL_AMP = 0.3
OI = None  # rempli après apply_style
XLAB = ["déc. 24", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
        "août", "sept.", "oct.", "nov.", "déc. 25"]


def main() -> int:
    d = pd.read_csv(CSV)
    amp = d.groupby("famille")["mean_shap_signe"].agg(lambda s: s.abs().max())
    gros = amp[amp >= SEUIL_AMP].sort_values(ascending=False).index.tolist()
    petits = amp[amp < SEUIL_AMP].sort_values(ascending=False).index.tolist()

    fs.apply_style()
    oi = fs.OKABE_ITO
    couleurs = {
        "Calendrier": oi["orange"], "Historique de charge": oi["bleu"],
        "Météo": oi["bleu_ciel"], "Événement": oi["vert"],
        "Réservation de groupe": oi["mauve"], "Régularité et correspondances": oi["vermillon"],
    }
    autres_col = "#999999"
    DEC = [1, 13]                                     # décembres partiels -> marqueurs creux

    def courbe(ax, x, y, color, lw, ls, label):
        ax.plot(x, y, ls=ls, lw=lw, color=color, label=label, zorder=2)   # ligne seule
        full = ~np.isin(x, DEC); dec = np.isin(x, DEC)
        ax.plot(x[full], y[full], ls="none", marker="o", ms=3, mfc=color, mec=color, zorder=3)
        ax.plot(x[dec], y[dec], ls="none", marker="o", ms=4.5, mfc="white", mec=color,
                mew=1.0, zorder=4)

    fig, axes = plt.subplots(2, 1, figsize=(fs.LARGE, fs.LARGE * 0.88), sharex=True, sharey=True)
    for ax, seg, titre in ((axes[0], "bas", "BAS (plaine)"), (axes[1], "haut", "HAUT (crémaillère)")):
        sub = d[d.segment == seg]
        piv = sub.pivot_table(index="mois", columns="famille", values="mean_shap_signe").sort_index()
        x = piv.index.values
        for fa in gros:
            courbe(ax, x, piv[fa].values, couleurs.get(fa, "#333333"), 1.3, "-", fa)
        autres = piv[petits].sum(axis=1).values
        courbe(ax, x, autres, autres_col, 0.7, "--", "Autres (" + ", ".join(petits) + ")")
        ax.axhline(0, color="#555555", lw=0.6, zorder=0)
        ax.set_ylabel("SHAP signé moyen\n(voyageurs)", fontsize=8)
        ax.annotate(titre, xy=(0.01, 0.94), xycoords="axes fraction", ha="left", va="top",
                    fontsize=9, fontweight="bold")
        ax.grid(True, axis="y", lw=0.3); ax.tick_params(labelsize=7)
    axes[1].set_xticks(range(1, 14))
    axes[1].set_xticklabels(XLAB, rotation=45, ha="right", fontsize=7)
    axes[1].set_xlabel("Mois de l'année horaire H25 (deux décembres distingués)", fontsize=8, labelpad=4)
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, 1.32), ncol=3, fontsize=7,
                   handlelength=1.6, columnspacing=1.2)
    fig.subplots_adjust(left=0.12, right=0.99, top=0.85, bottom=0.12, hspace=0.10)
    p = fs.save_fig(fig, "f_decomposition_mensuelle", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
