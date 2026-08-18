#!/usr/bin/env python3
"""Section 4.5.6 (extension) — f_part_famille_dotplot (version MANUSCRIT, finale).

Dot plot de la composition |SHAP| par famille × strate (type de jour), deux panneaux
(bas, haut). Familles en ordonnée dans l'ordre du GLOBAL BAS ; quatre strates en points
par famille (teintes ET marqueurs Okabe-Ito distincts, dodge vertical). Famille « Desserte »
omise (part < 0,05 %), signalée en note. Titre d'axe x commun. Aucun tableau intégré :
les masses par strate et les effectifs sont dans tableaux/section_4_5_6/t_masse_par_strate.csv.

La version « petits multiples » est conservée dans verifs/section_4_5_6/ comme artefact.
Source : tableaux/section_4_5_6/t_famille_strate.csv (s02). Graduations x jusqu'à 40 %.
Charte figstyle (300 DPI, sans titre embarqué, daltonisme-compatible). Aucune interprétation.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CSV = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6" / "t_famille_strate.csv"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

NBSP = " "
# Strate -> (libellé, couleur Okabe-Ito, marqueur, dodge vertical) — INCHANGÉ
STRATA = [
    ("pointe_ouvrable", "Pointe ouvrable", "vermillon", "o", -0.24),
    ("horspointe_ouvrable", "Hors-pointe ouvrable", "bleu", "s", -0.08),
    ("samedi", "Samedi", "vert", "^", 0.08),
    ("dimanche_ferie", "Dimanche / férié", "orange", "D", 0.24),
]
OMISE = "Desserte"


def main() -> int:
    d = pd.read_csv(CSV)
    fs.apply_style()
    oi = fs.OKABE_ITO

    order = (d[(d.segment == "bas") & (d.stratification == "global")]
             .sort_values("part", ascending=False)["famille"].tolist())
    order = [f for f in order if f != OMISE]
    ypos = {f: i for i, f in enumerate(order)}

    fig, (ax_b, ax_h) = plt.subplots(1, 2, figsize=(fs.LARGE, fs.LARGE * 0.52), sharey=True)
    for ax, seg, titre in ((ax_b, "bas", "BAS (plaine)"), (ax_h, "haut", "HAUT (crémaillère)")):
        sub = d[(d.segment == seg) & (d.stratification == "type_jour")]
        for key, lab, col, mk, dy in STRATA:
            s = sub[sub.strate == key].set_index("famille").reindex(order)
            y = [ypos[f] + dy for f in order]
            ax.scatter(s["part"].values * 100, y, s=26, marker=mk, color=oi[col],
                       edgecolors="#333333", linewidths=0.4, zorder=3, label=lab)
        if seg == "bas":
            ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=7.5)
        else:
            ax.tick_params(labelleft=False)
        ax.set_xlim(0, 40); ax.set_xticks(range(0, 41, 10))
        ax.grid(True, axis="x", lw=0.3); ax.grid(False, axis="y")
        ax.tick_params(labelsize=7)
        ax.annotate(titre, xy=(0.97, 0.03), xycoords="axes fraction", ha="right", va="bottom",
                    fontsize=9, fontweight="bold",
                    color=fs.COULEUR_BAS if seg == "bas" else fs.COULEUR_HAUT)
    ax_b.set_ylim(-0.6, len(order) - 0.4)
    ax_b.invert_yaxis()
    ax_b.annotate(f"Famille «{NBSP}{OMISE}{NBSP}» omise (part <{NBSP}0,05{NBSP}%).",
                  xy=(0.03, 0.97), xycoords="axes fraction", ha="left", va="top",
                  fontsize=6.5, style="italic", color="#555555")

    handles, labels = ax_b.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.04),
               ncol=4, fontsize=7.5, handletextpad=0.3, columnspacing=1.4)
    fig.supxlabel(f"Part de la masse |SHAP| de la famille (%)", fontsize=8.5)
    fig.subplots_adjust(left=0.19, right=0.99, top=0.90, bottom=0.13, wspace=0.08)
    p = fs.save_fig(fig, "f_part_famille_dotplot", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
