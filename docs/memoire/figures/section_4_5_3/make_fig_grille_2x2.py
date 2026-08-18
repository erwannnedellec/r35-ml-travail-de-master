#!/usr/bin/env python3
"""Section 4.5.3 — fig_grille_2x2.png.

Decomposition enrichissement x segmentation : R2 du segment HAUT dans les 4 cellules
{M0, 158 var.} x {global, segmente}, avec les deltas annotes sur les aretes
(horizontales = enrichissement 158-M0 ; verticales = segmentation seg-global).
Schema, charte maison figstyle. Largeur 8 cm (DEMI).

Source (outputs/confirmation/ uniquement, gel ba493568) : c04_delta_segmentation.json.
LECTURE SEULE. Aucune annotation de conclusion (seuls les R2 et deltas chiffres).
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
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402


def _rogner_marges(path, pad_px: int = 12) -> None:
    """Rogne le PNG au contenu utile (pixels non blancs) + une marge fixe `pad_px`, pour que
    le fichier du dépôt corresponde au cadrage inséré au manuscrit. Byte-reproductible : pixels
    déterministes (rendu matplotlib pinné) + rognage/ré-encodage PIL déterministes, sans
    horodatage embarqué."""
    from PIL import Image, ImageChops, PngImagePlugin
    im = Image.open(path).convert("RGB")
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    box = (max(0, bbox[0] - pad_px), max(0, bbox[1] - pad_px),
           min(im.width, bbox[2] + pad_px), min(im.height, bbox[3] + pad_px))
    info = PngImagePlugin.PngInfo()
    info.add_text("Software", "figstyle + rognage marges (charte mémoire R35)")
    im.crop(box).save(path, "PNG", pnginfo=info)


def main() -> int:
    c04 = json.loads((CONF / "c04_delta_segmentation.json").read_text())
    cells = c04["cellules_metriques_h25"]
    dec = c04["decomposition_r2"]
    r2h = {k: float(cells[k]["haut"]["r2"]) for k in
           ("M0_global", "158_global", "M0_seg", "158_seg_gel")}
    d_enr_glob = dec["delta_enrichissement_158_moins_M0"]["a_global_fixe"]["haut"]
    d_enr_seg = dec["delta_enrichissement_158_moins_M0"]["a_segmente_fixe"]["haut"]
    d_seg_m0 = dec["delta_segmentation_seg_moins_global"]["a_M0_fixe"]["haut"]
    d_seg_158 = dec["delta_segmentation_seg_moins_global"]["a_158_fixe"]["haut"]

    fs.apply_style()
    L12 = 12 * fs.CM   # 12 cm : lisibilité des arêtes (police agrandie), 300 DPI natif
    fig, ax = fs.new_fig(L12, hauteur=L12)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    cx_g, cx_d = 0.24, 0.76                       # colonnes gauche / droite
    cy_h, cy_b = 0.70, 0.26                       # lignes haut / bas
    w, h = 0.24, 0.18
    pos = {"M0_global": (cx_g, cy_h), "158_global": (cx_d, cy_h),
           "M0_seg": (cx_g, cy_b), "158_seg_gel": (cx_d, cy_b)}
    bras_lib = {"M0_global": "M0 · global", "158_global": "158f · global",
                "M0_seg": "M0 · segmenté", "158_seg_gel": "158f · segmenté"}
    fill = {"M0_global": fs.OKABE_ITO["bleu_ciel"], "158_global": fs.OKABE_ITO["orange"],
            "M0_seg": fs.OKABE_ITO["bleu_ciel"], "158_seg_gel": fs.COULEUR_HAUT}
    for k, (cx, cy) in pos.items():
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                     boxstyle="round,pad=0.004,rounding_size=0.02",
                     linewidth=0.8, edgecolor="#333333", facecolor=fill[k], alpha=0.30))
        ax.text(cx, cy + 0.032, bras_lib[k], ha="center", va="center", fontsize=8.5, color="#222222")
        ax.text(cx, cy - 0.034, f"R² = {r2h[k]:.3f}", ha="center", va="center",
                fontsize=10.5, fontweight="bold", color="#222222")

    def arrow(a, b):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=8,
                     linewidth=0.9, color="#666666", shrinkA=1, shrinkB=1))

    arrow((cx_g + w / 2, cy_h), (cx_d - w / 2, cy_h))   # enrichissement · global
    arrow((cx_g + w / 2, cy_b), (cx_d - w / 2, cy_b))   # enrichissement · segmenté
    arrow((cx_g, cy_h - h / 2), (cx_g, cy_b + h / 2))   # segmentation · M0
    arrow((cx_d, cy_h - h / 2), (cx_d, cy_b + h / 2))   # segmentation · 158
    wbox = dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.12)
    ann = dict(fontsize=8, color="#7a3b00", ha="center", va="center", bbox=wbox)
    ax.text(0.50, cy_h, f"enrichissement\nΔR² {d_enr_glob:+.3f}", **ann)
    ax.text(0.50, cy_b, f"enrichissement\nΔR² {d_enr_seg:+.3f}", **ann)
    ann2 = dict(fontsize=8, color="#004b39", ha="center", va="center", rotation=90, bbox=wbox)
    ax.text(cx_g, 0.48, f"segmentation\nΔR² {d_seg_m0:+.3f}", **ann2)
    ax.text(cx_d, 0.48, f"segmentation\nΔR² {d_seg_158:+.3f}", **ann2)
    # Pas de titre embarqué : le titre APA (R² du segment haut, H25) va dans le document.

    p = fs.save_fig(fig, "fig_grille_2x2", DOSSIER, largeur=L12)
    plt.close(fig)
    # bbox_inches='tight' rogne au cadre des axes (0-1), pas au contenu, pour un schéma
    # axis('off') : on rogne donc explicitement au contenu utile + ~12 px (cadrage manuscrit).
    _rogner_marges(p, pad_px=12)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
