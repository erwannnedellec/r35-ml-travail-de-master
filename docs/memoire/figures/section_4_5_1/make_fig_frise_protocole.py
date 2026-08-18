#!/usr/bin/env python3
"""Frise du protocole temporel — section 4.5.1.

Produit fig_4_frise_protocole.png : blocs H22, H23, H24 (entraînement) et H25 (test)
CONTIGUS — l'absence de bande d'embargo est traduite par la contiguïté, la distinction
entraînement/test passe par la couleur et l'étiquette, jamais par un blanc.

La portion Gilamont de H22 (exclue du train, ADR-065) est figurée par une bande hachurée
occupant la fraction correspondante de la HAUTEUR du bloc H22 : les tronçons Gilamont sont
répartis sur toute l'année H22, ce n'est pas une tranche calendaire. Représenter cette
exclusion comme un segment de temps serait faux.

Dates de frontière et part Gilamont sont DÉRIVÉES du parquet canonique (empreinte
ba493568 vérifiée), non codées en dur. Aucune métrique de performance n'apparaît.

LECTURE SEULE sur les données : lit un parquet, écrit un PNG dans ce dossier.
"""
import hashlib
import sys
from pathlib import Path

import pandas as pd
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

CANONIQUE = "ba493568"
ML = ROOT / "data/processed/ml_dataset.parquet"
GILAMONT_BPUIC = 8501260
TRAIN = ["H22", "H23", "H24"]
TEST = "H25"

_MOIS = ["", "janv.", "févr.", "mars", "avril", "mai", "juin",
         "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def date_fr(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {_MOIS[d.month]} {d.year}"


def main() -> int:
    h = hashlib.sha256(ML.read_bytes()).hexdigest()[:8]
    print(f"[hash] ml_dataset.parquet = {h} (attendu {CANONIQUE})")
    assert h == CANONIQUE, f"ABORT : empreinte {h} != {CANONIQUE}"

    df = pd.read_parquet(ML, columns=["horaire_annee_horaire", "base_date",
                                      "id_gare_depart_bpuic", "id_gare_arrivee_bpuic"])
    df["base_date"] = pd.to_datetime(df["base_date"])
    bornes = df.groupby("horaire_annee_horaire")["base_date"].agg(["min", "max"])
    n_h22 = int((df["horaire_annee_horaire"] == "H22").sum())
    gil = ((df["horaire_annee_horaire"] == "H22") &
           ((df["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
            (df["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC)))
    part_gil = int(gil.sum()) / n_h22
    print(f"[frise] part Gilamont dans H22 = {int(gil.sum())}/{n_h22} = {part_gil:.3%}")

    annees = TRAIN + [TEST]
    # Blocs CONTIGUS : chaque bloc court du début d'une année horaire au début de la
    # suivante (le dernier s'arrête à sa date max). Aucun blanc entre H24 et H25.
    debuts = {a: bornes.loc[a, "min"] for a in annees}
    fin_h25 = bornes.loc[TEST, "max"]
    spans = {}
    for i, a in enumerate(annees):
        x0 = debuts[a]
        x1 = debuts[annees[i + 1]] if i + 1 < len(annees) else fin_h25
        spans[a] = (x0, x1)
        print(f"[frise] {a} : {date_fr(x0)} -> {date_fr(x1)}")

    C_TRAIN = fs.OKABE_ITO["bleu"]
    C_TEST = fs.OKABE_ITO["vermillon"]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.34)

    # Blocs jointifs : aucun liseré, aucun espace (edgecolor="none").
    for a in annees:
        x0, x1 = spans[a]
        larg = x1 - x0
        couleur = C_TEST if a == TEST else C_TRAIN
        ax.add_patch(Rectangle((x0, 0), larg, 1.0, facecolor=couleur,
                               edgecolor="none", linewidth=0.0, zorder=2))
        ax.text(x0 + larg / 2, 0.58, a, ha="center", va="center", color="white",
                fontsize=12, fontweight="bold", zorder=4)
    # Séparateurs d'années INTERNES au bloc d'entraînement : simples repères, pas des vides.
    for a in ("H23", "H24"):
        ax.axvline(spans[a][0], color="white", lw=0.9, zorder=4)

    # Portion Gilamont : fraction de la HAUTEUR du bloc H22 (part des observations,
    # réparties sur toute l'année) — surtout pas une tranche de temps.
    x0, x1 = spans["H22"]
    ax.add_patch(Rectangle((x0, 0), x1 - x0, part_gil, facecolor="white", alpha=0.35,
                           edgecolor="white", hatch="////", linewidth=0.0, zorder=3))

    # Accolades de périmètre (couleur + étiquette, jamais un blanc).
    x_tr0, x_tr1 = spans["H22"][0], spans["H24"][1]
    x_te0, x_te1 = spans[TEST]
    for (xa, xb, lab, col) in [(x_tr0, x_tr1, "Entraînement", C_TRAIN),
                               (x_te0, x_te1, "Test", C_TEST)]:
        ax.plot([xa, xb], [1.16, 1.16], color=col, lw=1.4, zorder=2,
                solid_capstyle="butt")
        ax.text(xa + (xb - xa) / 2, 1.24, lab, ha="center", va="bottom",
                color=col, fontsize=10, fontweight="bold")

    # Frontière entraînement / test : trait net, AUCUN espace.
    ax.axvline(x_te0, color="#222222", lw=1.2, zorder=5)

    ax.set_xlim(spans["H22"][0], fin_h25)
    ax.set_ylim(0, 1.42)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    bornes_x = [spans[a][0] for a in annees] + [fin_h25]
    ax.set_xticks(bornes_x)
    ax.set_xticklabels([date_fr(d) for d in bornes_x], fontsize=8, rotation=30, ha="right")
    ax.set_xlabel("Frontières d'année horaire (changement d'horaire de mi-décembre)",
                  labelpad=6)

    # Teinte de la bande Gilamont telle qu'elle apparaît (bleu + voile blanc 35 %).
    leg = [
        Patch(facecolor=C_TRAIN, label="Années d'entraînement"),
        Patch(facecolor=C_TEST, label="Année de test"),
        Patch(facecolor="#59A3CD", hatch="////", edgecolor="white",
              label=f"Tronçons Gilamont exclus du train ({part_gil:.1%} des observations H22)"),
    ]
    ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.60),
              ncol=1, fontsize=8, frameon=True)

    p = fs.save_fig(fig, "fig_4_frise_protocole", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print(f"[écrit] {p.relative_to(ROOT)}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
