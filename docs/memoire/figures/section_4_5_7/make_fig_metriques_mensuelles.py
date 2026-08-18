#!/usr/bin/env python3
"""Section 4.5.7 — fig_metriques_mensuelles.png.

R2 par mois horaire H25 (cal_mois_horaire 1..13), pour global / bas / haut. L'annee
horaire H25 comporte DEUX decembres (indices 12 et 13), distingues sur l'axe. Lignes
avec marqueurs, charte maison figstyle. Largeur 16 cm.

Source (outputs/confirmation/ uniquement, gel ba493568) : c09_analyse_erreurs.json
(b_metriques_par_mois_horaire). LECTURE SEULE. Aucune annotation de conclusion.
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

MOIS_ABBR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
             "août", "sept.", "oct.", "nov.", "déc."]
SERIES = [("global", "Global", fs.OKABE_ITO["noir"]),
          ("bas", "Segment bas", fs.COULEUR_BAS),
          ("haut", "Segment haut", fs.COULEUR_HAUT)]


def main() -> int:
    c09 = json.loads((CONF / "c09_analyse_erreurs.json").read_text())
    b = c09["b_metriques_par_mois_horaire"]
    months = sorted((int(k) for k in b), key=int)

    # etiquettes d'axe : mois calendaire modal ; 2e occurrence d'un mois -> suffixe (2e)
    labels, seen = [], {}
    for m in months:
        cal = b[str(m)]["cal_mois_calendaire_modal"]
        seen[cal] = seen.get(cal, 0) + 1
        lab = MOIS_ABBR[cal] if cal and 1 <= cal <= 12 else str(m)
        labels.append(lab + (" (2ᵉ)" if seen[cal] > 1 else ""))

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.5)
    for key, lbl, col in SERIES:
        ys = [float(b[str(m)][key]["r2"]) for m in months]
        ax.plot(months, ys, marker="o", markersize=4, linewidth=1.4, color=col, label=lbl)
    # reperage des deux decembres (indices 12 et 13)
    decs = [m for m in months if b[str(m)]["cal_mois_calendaire_modal"] == 12]
    for m in decs:
        ax.axvline(m, color="#888888", linestyle=":", linewidth=0.8, zorder=0)
    ax.set_xticks(months); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("Mois de l'année horaire H25 (deux décembres distingués)")
    ax.set_ylabel("Coefficient de détermination R² (sans unité)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=3, fontsize=8, handlelength=1.6)
    p = fs.save_fig(fig, "fig_metriques_mensuelles", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
