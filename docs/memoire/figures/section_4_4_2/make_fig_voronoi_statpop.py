#!/usr/bin/env python3
"""Section 4.4.2 — Rattachement spatial STATPOP : zones tampons vs cellules de Voronoï.

Reprise en registre académique de l'ancienne figure `s3_voronoi_statpop` :
  - aucun titre embarqué, aucun identifiant (ni « ADR-25 », ni « Feature engineering ») ;
  - titres de panneaux sobres et noirs, en français, avec tréma partout (« Voronoï ») ;
  - couleurs de segment = palette maison (bas = bleu, haut = vermillon Okabe-Ito),
    identiques dans les deux panneaux, aucune couleur sémaphore ;
  - 17 gares (topologie courante : sans Gilamont ni Clies, fermées) et leurs codes,
    tracé pointillé de la ligne, chevauchement du panneau des tampons rendu par la transparence ;
  - distances de contrôle (VV-VVVI, bascule bas→haut) VÉRIFIÉES depuis les coordonnées et
    imprimées en sortie, mais NON annotées sur la figure (registre sobre) ;
  - le datage de la topologie en légende relève du manuscrit (hors figure).

Géométrie exacte en coordonnées MN95 (LV95, mètres) : les tampons sont des disques de
500 m ; les cellules de Voronoï sont bornées à 500 m par intersection avec le disque
(demi-plans des médiatrices ∩ disque). Affichage en kilomètres, aspect métrique conservé.

Charte `src/memoire/figstyle.py` : Okabe-Ito, 16 cm, 300 DPI, bbox tight, sans titre
embarqué. Reproductibilité byte-à-byte : SOURCE_DATE_EPOCH=1782000000 en tête.
LECTURE SEULE (lit `data/dimension/dim_gare.parquet`), écrit un PNG.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")  # byte-repro, avant matplotlib

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
from matplotlib.patches import Circle, Polygon as MplPoly, Patch  # noqa: E402

GARES = ROOT / "data" / "dimension" / "dim_gare.parquet"
RAYON_M = 500.0
# Topologie courante : Gilamont (fermée fin H22) et Clies (fermée fin H18) exclues.
HORS_TOPOLOGIE = {"GIL", "CLIE"}
# Segment réseau au grain gare : bas (plaine, Vevey → Château-de-Blonay),
# haut (crémaillère, Blonay → Les Pléiades). Blonay ouvre la section haute.
SEG_BAS = {"VV", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL"}
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]


def charger():
    g = pd.read_parquet(GARES, columns=["abreviation", "ordre", "lv95East", "lv95North"])
    g = g[~g["abreviation"].isin(HORS_TOPOLOGIE)].copy()
    g = g.sort_values("ordre").reset_index(drop=True)
    g["segment"] = np.where(g["abreviation"].isin(SEG_BAS), "bas", "haut")
    assert len(g) == 17, f"topologie courante attendue = 17 gares, obtenu {len(g)}"
    return g


def dist_m(g, a, b):
    ra = g.loc[g.abreviation == a].iloc[0]
    rb = g.loc[g.abreviation == b].iloc[0]
    return float(np.hypot(ra.lv95East - rb.lv95East, ra.lv95North - rb.lv95North))


def cellule_voronoi_bornee(i, pts, r=RAYON_M):
    """Cellule de Voronoï du site i, bornée à un disque de rayon r (mètres).

    Intersection du disque de 500 m avec les demi-plans « plus proche de i que de j »
    (médiatrices), pour tous les autres sites j. Robuste, sans reconstruction des
    régions non bornées de scipy.
    """
    xi, yi = pts[i]
    cell = Point(xi, yi).buffer(r, quad_segs=96)
    T = 8000.0
    for j, (xj, yj) in enumerate(pts):
        if j == i:
            continue
        mx, my = (xi + xj) / 2.0, (yi + yj) / 2.0
        ux, uy = xj - xi, yj - yi
        n = np.hypot(ux, uy)
        ux, uy = ux / n, uy / n            # i -> j (normale sortante)
        px, py = -uy, ux                   # direction de la médiatrice
        tix, tiy = -ux, -uy                # vers i (demi-plan conservé)
        demi_plan = Polygon([
            (mx + T * px, my + T * py),
            (mx - T * px, my - T * py),
            (mx - T * px + T * tix, my - T * py + T * tiy),
            (mx + T * px + T * tix, my + T * py + T * tiy),
        ])
        cell = cell.intersection(demi_plan)
        if cell.is_empty:
            break
    return cell


def _poly_xy_km(geom):
    """Anneaux extérieurs (en km) d'un Polygon ou MultiPolygon shapely."""
    parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [np.asarray(p.exterior.coords) / 1000.0 for p in parts if not p.is_empty]


def _placer_codes(ax, xk, yk, codes, off=0.30):
    """Codes gares déportés perpendiculairement à la ligne, côté alterné, avec conducteur.

    Décale chaque étiquette du côté opposé à sa voisine (réduit les recouvrements dans
    la grappe dense du haut) ; un fin trait conducteur relie le point à son libellé."""
    n = len(xk)
    for i in range(n):
        i0, i1 = max(0, i - 1), min(n - 1, i + 1)
        tx, ty = xk[i1] - xk[i0], yk[i1] - yk[i0]
        tl = np.hypot(tx, ty) or 1.0
        px, py = -ty / tl, tx / tl                 # perpendiculaire à la ligne
        side = 1.0 if i % 2 == 0 else -1.0
        lx, ly = xk[i] + px * side * off, yk[i] + py * side * off
        ax.plot([xk[i], lx], [yk[i], ly], color="#b0b0b0", linewidth=0.5, zorder=4)
        ax.annotate(codes[i], (lx, ly), fontsize=6.6, color="#111111", ha="center",
                    va="center", zorder=6, path_effects=HALO)


def dessiner_panneau(ax, g, mode):
    """mode = 'tampon' (disques 500 m) ou 'voronoi' (cellules bornées à 500 m)."""
    coul = {"bas": fs.COULEUR_BAS, "haut": fs.COULEUR_HAUT}
    pts_m = list(zip(g.lv95East.to_numpy(), g.lv95North.to_numpy()))
    xk = g.lv95East.to_numpy() / 1000.0
    yk = g.lv95North.to_numpy() / 1000.0
    seg = g.segment.to_numpy()

    if mode == "tampon":
        for x, y, s in zip(xk, yk, seg):
            ax.add_patch(Circle((x, y), RAYON_M / 1000.0, facecolor=coul[s], alpha=0.30,
                                edgecolor=coul[s], linewidth=0.8, zorder=2))
    else:
        for i in range(len(g)):
            cell = cellule_voronoi_bornee(i, pts_m)
            for ring in _poly_xy_km(cell):
                ax.add_patch(MplPoly(ring, closed=True, facecolor=coul[seg[i]], alpha=0.55,
                                     edgecolor="white", linewidth=1.0, zorder=2))

    # tracé pointillé de la ligne (ordre des gares) + points + codes déportés
    ax.plot(xk, yk, ls=(0, (2, 2)), color="#6a6a6a", linewidth=1.0, zorder=3)
    ax.scatter(xk, yk, s=11, color="#000000", zorder=5)
    _placer_codes(ax, xk, yk, g.abreviation.tolist())
    ax.set_aspect("equal")
    ax.grid(False)


def main():
    g = charger()
    d_vvvi = dist_m(g, "VV", "VVVI")
    d_basc = dist_m(g, "CHBL", "BLON")
    print("Section 4.4.2 — reprise s3_voronoi_statpop")
    print(f"[topologie] {len(g)} gares : {g.abreviation.tolist()}")
    print(f"[distance vérifiée] VV–VVVI = {d_vvvi:.1f} m")
    print(f"[distance vérifiée] bascule CHBL–BLON (bas→haut) = {d_basc:.1f} m")

    fs.apply_style()
    # Panneaux empilés (pleine largeur) : la ligne diagonale reste lisible et l'aspect
    # métrique (disques circulaires) est conservé sans écraser la grappe dense du haut.
    fig, axes = plt.subplots(2, 1, figsize=(fs.LARGE, fs.LARGE * 1.05), sharex=True, sharey=True)
    titres = ["Zones tampons de 500 m", "Cellules de Voronoï bornées à 500 m"]
    modes = ["tampon", "voronoi"]
    for ax, titre, mode in zip(axes, titres, modes):
        dessiner_panneau(ax, g, mode)
        ax.set_ylabel("Coordonnée nord (km, MN95)")
        ax.text(0.5, 1.02, titre, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=10.5, color="#000000")
    axes[1].set_xlabel("Coordonnée est (km, MN95)")

    # marges homogènes autour du même cadre géographique dans les deux panneaux
    xk = g.lv95East.to_numpy() / 1000.0
    yk = g.lv95North.to_numpy() / 1000.0
    mx0, mx1, my0, my1 = xk.min(), xk.max(), yk.min(), yk.max()
    padx, pady = 0.75, 1.05
    for ax in axes:
        ax.set_xlim(mx0 - padx, mx1 + padx)
        ax.set_ylim(my0 - pady, my1 + pady)

    leg = [Patch(facecolor=fs.COULEUR_BAS, edgecolor="none", label="Segment bas"),
           Patch(facecolor=fs.COULEUR_HAUT, edgecolor="none", label="Segment haut")]
    axes[0].legend(handles=leg, loc="upper left", fontsize=8, frameon=True,
                   borderaxespad=0.4)

    p = fs.save_fig(fig, "s3_voronoi_statpop", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print(f"[écrit] {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
