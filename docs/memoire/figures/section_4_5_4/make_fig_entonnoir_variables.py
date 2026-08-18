#!/usr/bin/env python3
"""Section 4.5.4 — fig_entonnoir_variables.png (version sobre, registre mémoire).

Cascade/entonnoir HORIZONTAL de la sélection des variables, en écho à fig_4_entonnoir_apc
(§4.4). Registre académique sobre : une SEULE couleur de bloc (bleu Okabe-Ito), la
progression portée par les effectifs et la LARGEUR des blocs (strictement décroissante,
sauf la marche +1 où 172 est très légèrement plus large que 171). Aucun identifiant interne
dans les libellés. Charte maison figstyle : pas de titre embarqué, 300 DPI, bbox tight,
SOURCE_DATE_EPOCH. Largeur 16 cm.

Chemin : 209 → 179 → 171 → 172 → 170 → 158. Critère court + delta (noir) sous chaque marche.
Branche rejetée : trait pointillé fin depuis 179 vers un bloc 157 gris hachuré (impasse),
annotation sobre « rejeté : ΔR² haut −0,026 ».

Effectifs LUS des fichiers de listes (set-diff) + parquet ba493568, aucun chiffre codé en
dur : deltas recalculés et chaîne vérifiée par assert ; garde de provenance sur l'empreinte.
Aucune interprétation.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch  # noqa: E402

HASH = "ba493568"
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
ARCH = ROOT / "archive/explorations/consolidation_finale/outputs"
LISTES = {
    179: ROOT / "models/11_modeling/xgb_B_prime_final_features.json",
    171: ARCH / "etape_04bis_features_171.json",
    172: ARCH / "controle_enrichi_seg_172f.json",
    170: ARCH / "etape_04bis_v2_features_170f.json",
    158: ROOT / "outputs/couche2/features_158f_sans_simba.json",
    157: ARCH / "etape_04bis_features_157.json",
}


def n_features(p: Path) -> int:
    d = json.loads(p.read_text())
    f = d["features"] if isinstance(d.get("features"), list) else d["features"]["features"]
    return len(f)


def effectifs() -> dict:
    """Effectifs lus des fichiers (aucun chiffre codé en dur). Provenance parquet vérifiée."""
    import pyarrow.parquet as pq
    assert hashlib.sha256(ML.read_bytes()).hexdigest()[:8] == HASH, "parquet non canonique"
    n = {209: len(pq.read_schema(ML).names)}
    n.update({k: n_features(v) for k, v in LISTES.items()})
    assert [n[179] - n[209], n[171] - n[179], n[172] - n[171], n[170] - n[172], n[158] - n[170]] \
        == [-30, -8, 1, -2, -12], "chaîne principale non réconciliée"
    assert n[157] - n[179] == -22, "branche rejetée non réconciliée"
    return n


def dfmt(d: int) -> str:
    return f"+{d}" if d > 0 else f"−{abs(d)}"          # signe moins typographique (U+2212)


def main() -> int:
    n = effectifs()
    BLEU = fs.OKABE_ITO["bleu"]
    order = [209, 179, 171, 172, 170, 158]
    tags = {209: "Table canonique", 158: "Modèle retenu"}
    ops = [("retrait\nstructurel", n[179] - n[209]), ("contribution\nnulle", n[171] - n[179]),
           ("dénivelé\nréintroduit", n[172] - n[171]), ("gain\nnul", n[170] - n[172]),
           ("retrait\nSIMBA", n[158] - n[170])]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.56)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    yc, H = 0.66, 0.30
    xs = [0.075 + i * 0.17 for i in range(6)]
    W_MIN, W_MAX = 0.082, 0.140

    def wf(N):                                          # largeur ∝ effectif (échelle étirée 158–209)
        return W_MIN + (W_MAX - W_MIN) * (N - 158) / (209 - 158)
    widths = {k: wf(k) for k in (209, 179, 171, 170, 158, 157)}
    widths[172] = widths[171] + 0.004                   # +1 : 172 très légèrement plus large que 171 (< 179)
    y_lib = yc - H / 2 - 0.05
    y_delta = y_lib - 0.072

    def bloc(x, k, y=yc, rejected=False):
        ww = widths[k]
        ax.add_patch(FancyBboxPatch((x - ww / 2, y - H / 2), ww, H,
                     boxstyle="round,pad=0.004,rounding_size=0.018", linewidth=1.0,
                     edgecolor="#777777" if rejected else "#1a1a1a",
                     linestyle="--" if rejected else "-",
                     facecolor="#c9c9c9" if rejected else BLEU, alpha=0.6 if rejected else 1.0,
                     hatch="///" if rejected else None, zorder=3))
        tcol = "#333333" if rejected else "white"
        ax.text(x, y + 0.012, f"{k}", ha="center", va="center", fontsize=13.5,
                fontweight="bold", color=tcol, zorder=4)
        ax.text(x, y - 0.036, "variables", ha="center", va="center", fontsize=7.5, color=tcol, zorder=4)

    # connecteurs gris + étiquettes de critère (deltas en noir, y compris le +1)
    for i in range(5):
        x0 = xs[i] + widths[order[i]] / 2
        x1 = xs[i + 1] - widths[order[i + 1]] / 2
        ax.add_patch(Rectangle((x0, yc - H * 0.36), x1 - x0, H * 0.72,
                     facecolor="#dcdcdc", edgecolor="none", zorder=1))
        lib, delta = ops[i]
        xm = (xs[i] + xs[i + 1]) / 2
        ax.text(xm, y_lib, lib, ha="center", va="top", fontsize=7.4, color="#333333")
        ax.text(xm, y_delta, dfmt(delta), ha="center", va="top", fontsize=10,
                fontweight="bold", color="#222222")

    for k in order:
        bloc(xs[order.index(k)], k)
        if k in tags:
            ax.text(xs[order.index(k)], yc + H / 2 + 0.03, tags[k], ha="center", va="bottom",
                    fontsize=8.2, color="#222222")

    # branche rejetée (sobre) : 179 --(pointillés fins)--> 157 gris hachuré
    x179 = xs[1]; y157 = 0.205; x157 = x179 + 0.01
    ax.add_patch(FancyArrowPatch((x179, yc - H / 2), (x157, y157 + H / 2),
                 connectionstyle="arc3,rad=0.02", arrowstyle="-|>", mutation_scale=9,
                 linewidth=0.9, linestyle=(0, (3, 3)), color="#9a9a9a", zorder=2))
    bloc(x157, 157, y=y157, rejected=True)
    ax.text(x157 - widths[157] / 2 - 0.014, y157 + 0.05, dfmt(n[157] - n[179]),
            ha="right", va="center", fontsize=9, color="#888888")
    ax.text(x157 + widths[157] / 2 + 0.02, y157, "rejeté : ΔR² haut −0,026",
            ha="left", va="center", fontsize=8.5, color="#444444")

    p = fs.save_fig(fig, "fig_entonnoir_variables", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
