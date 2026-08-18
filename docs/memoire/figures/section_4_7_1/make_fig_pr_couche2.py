#!/usr/bin/env python3
"""Section 4.7.1 — fig_pr_couche2.png.

Courbe précision-rappel du modèle de couche 1 au grain course (H25), avec les points
d'opération de la couche 2 : top-k protocolaire (k=418), pratique humaine H25 (418 unités
multiples) et les trois règles déployables du menu (a′ iso-volume, b rappel renforcé,
c haute précision — seuils calibrés sur H24). Charte mémoire `figstyle`. Largeur 16 cm.

Source (LECTURE SEULE, gel ba493568) :
  - outputs/couche2/q_couche2_pr_courbe_ba493568.json
    (courbe PR + points d'opération ; produit par src/couche2/decision.py evaluate_h25,
     modèles gelés e4ddfccd/df6a11c5 en lecture seule).
Aucune annotation de conclusion. Le titre vit dans la légende du manuscrit.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"   # reproductibilité byte-à-byte (charte)
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
SRC = ROOT / "outputs" / "couche2" / "q_couche2_pr_courbe_ba493568.json"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs          # charte mémoire (enveloppe la charte maison)  # noqa: E402
import figures_style as house  # couche maison : finalize + contrôle de conformité  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# libellés français (aucun identifiant interne), couleurs Okabe-Ito
LIB = {
    "a_iso_volume": "Règle a′ (iso-volume, seuil figé)",
    "b_rappel_renforce": "Règle b (rappel renforcé, seuil figé)",
    "c_haute_precision": "Règle c (haute précision, seuil figé)",
}
COL = {
    "a_iso_volume": fs.OKABE_ITO["vert"],
    "b_rappel_renforce": fs.OKABE_ITO["mauve"],
    "c_haute_precision": fs.OKABE_ITO["orange"],
}


def main() -> int:
    d = json.loads(SRC.read_text())
    pr, pts = d["pr_curve"], d["points"]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.66)

    ax.plot(pr["recall"], pr["precision"], color=fs.COULEUR_BAS, lw=1.6,
            label="Modèle : courbe précision-rappel (H25, grain course)")

    tk = pts["top_k_protocolaire"]
    ax.scatter(tk["recall"], tk["precision"], color=fs.OKABE_ITO["vermillon"],
               marker="*", s=150, zorder=5, label=f"Top-k protocolaire (k={tk['k']})")
    h = pts["humain"]
    ax.scatter(h["recall"], h["precision"], color=fs.OKABE_ITO["noir"],
               marker="D", s=70, zorder=5, label="Pratique humaine H25 (418 unités multiples)")
    for rk in ("a_iso_volume", "b_rappel_renforce", "c_haute_precision"):
        p = pts[rk]
        ax.scatter(p["recall"], p["precision"], color=COL[rk], marker="o", s=60,
                   zorder=4, label=LIB[rk])

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0.0, 1.03)
    house.finalize(ax, xlabel="Rappel (grain course, H25)",
                   ylabel="Précision (grain course, H25)")
    # légende AU-DESSUS de l'aire de tracé : ne recouvre aucun point d'opération
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=2,
              fontsize=8, handlelength=1.5, columnspacing=1.4)

    problems = house.check_conformite(fig)
    if problems:
        raise SystemExit("Figure non conforme à la charte :\n  - " + "\n  - ".join(problems))

    p = fs.save_fig(fig, "fig_pr_couche2", DOSSIER)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
