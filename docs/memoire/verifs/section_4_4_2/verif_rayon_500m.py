#!/usr/bin/env python3
"""Section 4.4.2 — Justification du rayon 500 m : part de la cellule de Voronoï
contrainte par le voisinage vs par le rayon.

Pour chaque cellule de Voronoï bornée (disque de 500 m ∩ médiatrices des voisines,
construction IDENTIQUE à `make_fig_voronoi_statpop.py`), on calcule :

  1) ratio_aire = aire(cellule) / aire(disque complet 500 m).
     part_aire_voisinage = 1 − ratio_aire  = fraction du disque « rognée ».
     ATTENTION à l'interprétation : la cellule = disque ∩ demi-plans, elle est donc
     TOUJOURS ⊆ disque. Toute réduction d'AIRE sous le disque est causée par les
     médiatrices des voisines — le rayon, lui, ne rogne jamais l'aire sous le disque
     (le disque EST le rayon). L'aire seule ne distingue donc pas les deux causes.

  2) La distinction des deux causes se lit sur le PÉRIMÈTRE de la cellule :
       - L_bis : longueur de bord portée par une médiatrice  → contrainte de VOISINAGE
       - L_arc : longueur de bord portée par le cercle 500 m → contrainte de RAYON
     frac_arc = L_arc / périmètre  = part du contour où le cap 500 m est l'unique
     contrainte active (aucune voisine assez proche pour mordre ici). C'est là que le
     rayon « décide ». Nuance importante : la ligne étant quasi-1D, le rayon décide
     LATÉRALEMENT (perpendiculaire à la voie) pour presque tous les arrêts, et pas
     seulement aux deux extrémités de ligne (VV en bas, PLEI en haut).

Sorties : tableau brut par arrêt, moyennes par segment (bas/haut), moyennes globales,
et un CSV. LECTURE SEULE (`data/dimension/dim_gare.parquet`), écrit un CSV à côté.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent

GARES = ROOT / "data" / "dimension" / "dim_gare.parquet"
RAYON_M = 500.0
AIRE_DISQUE = np.pi * RAYON_M**2                       # 785 398.16 m²
QUAD_SEGS = 512                                        # finesse du cercle (précision aire/arc)
TOL_ARC = 0.5                                          # m : bord classé « arc » si mi-arête à |·|≤tol de r

# Topologie courante (identique à la figure) : GIL (fermée fin H22) et CLIE (fin H18) exclues.
HORS_TOPOLOGIE = {"GIL", "CLIE"}
SEG_BAS = {"VV", "VVVI", "HTV", "CHTV", "STLE", "STLV", "CHIZ", "CHBL"}


def charger():
    g = pd.read_parquet(GARES, columns=["abreviation", "nom", "ordre", "lv95East", "lv95North"])
    g = g[~g["abreviation"].isin(HORS_TOPOLOGIE)].copy()
    g = g.sort_values("ordre").reset_index(drop=True)
    g["segment"] = np.where(g["abreviation"].isin(SEG_BAS), "bas", "haut")
    assert len(g) == 17, f"topologie courante attendue = 17 gares, obtenu {len(g)}"
    return g


def cellule_voronoi_bornee(i, pts, r=RAYON_M):
    """Cellule de Voronoï du site i, bornée au disque de rayon r. Construction identique
    à make_fig_voronoi_statpop.py : disque ∩ demi-plans « plus proche de i que de j »."""
    xi, yi = pts[i]
    cell = Point(xi, yi).buffer(r, quad_segs=QUAD_SEGS)
    T = 8000.0
    for j, (xj, yj) in enumerate(pts):
        if j == i:
            continue
        mx, my = (xi + xj) / 2.0, (yi + yj) / 2.0
        ux, uy = xj - xi, yj - yi
        n = np.hypot(ux, uy)
        ux, uy = ux / n, uy / n
        px, py = -uy, ux
        tix, tiy = -ux, -uy
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


def _rings(geom):
    parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [np.asarray(p.exterior.coords) for p in parts if not p.is_empty]


def decompose_bord(cell, site, r=RAYON_M, tol=TOL_ARC):
    """Répartit le périmètre de la cellule en longueur d'ARC (bord sur le cercle r)
    et longueur de MÉDIATRICE (bord droit intérieur). Classification par le rayon du
    MILIEU de chaque arête : une corde d'arc a son milieu ~sur le cercle (flèche
    ~6e-4 m à quad_segs=512), une corde de médiatrice a son milieu nettement en deçà."""
    xi, yi = site
    l_arc = l_bis = 0.0
    for ring in _rings(cell):
        for a, b in zip(ring[:-1], ring[1:]):
            mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            seg = float(np.hypot(b[0] - a[0], b[1] - a[1]))
            rmid = float(np.hypot(mx - xi, my - yi))
            if abs(rmid - r) <= tol:
                l_arc += seg
            else:
                l_bis += seg
    return l_arc, l_bis


def main():
    g = charger()
    pts = list(zip(g.lv95East.to_numpy(float), g.lv95North.to_numpy(float)))
    P = np.array(pts)

    rows = []
    for i in range(len(g)):
        cell = cellule_voronoi_bornee(i, pts)
        aire = float(cell.area)
        ratio = aire / AIRE_DISQUE
        l_arc, l_bis = decompose_bord(cell, pts[i])
        perim = l_arc + l_bis
        frac_arc = l_arc / perim if perim else np.nan
        # contexte de voisinage
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        d[i] = np.inf
        d_nn = float(d.min())
        n_1000 = int((d < 2 * RAYON_M).sum())          # voisines dont la médiatrice entre dans le disque
        rows.append(dict(
            ordre=int(g.ordre[i]), abrev=g.abreviation[i], nom=g.nom[i], seg=g.segment[i],
            aire_m2=aire, ratio_aire=ratio, part_aire_vois=1 - ratio,
            perim_m=perim, L_arc_m=l_arc, L_bis_m=l_bis,
            frac_arc=frac_arc, frac_bis=1 - frac_arc,
            d_nn_m=d_nn, n_vois_1000m=n_1000,
        ))
    df = pd.DataFrame(rows)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    print("=" * 108)
    print(f"Section 4.4.2 — justification rayon {RAYON_M:.0f} m  |  aire disque complet = "
          f"π·r² = {AIRE_DISQUE:,.1f} m²  |  17 gares (topologie courante)")
    print("=" * 108)
    aff = df.copy()
    aff["aire_m2"] = aff["aire_m2"].round(0).astype(int)
    aff["ratio_aire"] = aff["ratio_aire"].round(3)
    aff["part_aire_vois"] = aff["part_aire_vois"].round(3)
    aff["perim_m"] = aff["perim_m"].round(0).astype(int)
    aff["L_arc_m"] = aff["L_arc_m"].round(0).astype(int)
    aff["L_bis_m"] = aff["L_bis_m"].round(0).astype(int)
    aff["frac_arc"] = aff["frac_arc"].round(3)
    aff["frac_bis"] = aff["frac_bis"].round(3)
    aff["d_nn_m"] = aff["d_nn_m"].round(0).astype(int)
    print(aff.to_string(index=False))

    print("\n" + "-" * 108)
    print("MOYENNES PAR SEGMENT  (bas = plaine VV→CHBL, 8 gares ; haut = crémaillère BLON→PLEI, 9 gares)")
    print("-" * 108)
    gseg = df.groupby("seg").agg(
        n=("abrev", "size"),
        ratio_aire_moy=("ratio_aire", "mean"),
        part_aire_vois_moy=("part_aire_vois", "mean"),
        frac_arc_moy=("frac_arc", "mean"),
        frac_bis_moy=("frac_bis", "mean"),
        d_nn_moy=("d_nn_m", "mean"),
    ).reindex(["bas", "haut"])
    print(gseg.round(3).to_string())

    print("\n" + "-" * 108)
    print("MOYENNES GLOBALES (17 gares)")
    print("-" * 108)
    print(f"  ratio_aire (cellule/disque)                 moyenne = {df.ratio_aire.mean():.3f}   "
          f"médiane = {df.ratio_aire.median():.3f}")
    print(f"  part d'aire « rognée par le voisinage » 1−r moyenne = {df.part_aire_vois.mean():.3f}   "
          f"médiane = {df.part_aire_vois.median():.3f}")
    print(f"  frac_arc  (contour porté par le RAYON 500m) moyenne = {df.frac_arc.mean():.3f}   "
          f"médiane = {df.frac_arc.median():.3f}")
    print(f"  frac_bis  (contour porté par le VOISINAGE)  moyenne = {df.frac_bis.mean():.3f}   "
          f"médiane = {df.frac_bis.median():.3f}")

    print("\n  Distinction des deux causes par arrêt (aire rognée = 100% voisinage par construction ;")
    print("  le RAYON n'agit que sur le contour) — arrêts où le rayon domine le contour (frac_arc≥0.5) :")
    dom_rayon = df[df.frac_arc >= 0.5].sort_values("frac_arc", ascending=False)
    for _, r in dom_rayon.iterrows():
        print(f"    {r.abrev:5s} (ordre {int(r.ordre):2d}, {r.seg:4s}) : frac_arc={r.frac_arc:.3f}  "
              f"ratio_aire={r.ratio_aire:.3f}  d_nn={r.d_nn_m:.0f} m")
    print("  arrêts où le voisinage domine le contour (frac_arc<0.5) :",
          ", ".join(df[df.frac_arc < 0.5].sort_values("ordre").abrev.tolist()))

    out = DOSSIER / "verif_rayon_500m.csv"
    df.to_csv(out, index=False)
    print(f"\n[écrit] {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
