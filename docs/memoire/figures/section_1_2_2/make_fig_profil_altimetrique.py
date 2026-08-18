#!/usr/bin/env python3
"""Section 1.2 — Profil altimétrique de la ligne R35 (Vevey → Les Pléiades).

Figure d'ouverture du chapitre 1 : elle illustre, pour un lecteur qui n'a lu que le
paragraphe « Gares desservies », les faits que ce paragraphe affirme :
  1. la partition bas / haut, tranchée à Blonay (bascule de couleur bleu → vermillon) ;
  2. la rupture de pente qui la fonde (bas ≤ 5,3 %, puis ~9 % dès Blonay) ;
  3. la section à crémaillère au-delà de Blonay (segment haut épaissi), qui conduit aux
     Pléiades avec une rampe qui culmine vers 23 % avant Lally.

Altitudes et kilométrages proviennent EXCLUSIVEMENT de dim_gare (colonnes height, km) ;
aucune valeur n'est saisie de mémoire. Les 17 gares actives sont retenues (GIL et CLIE
fermées, sans altitude, exclues — topologie courante, cohérente avec §4.3.2). Les pentes
sont recalculées et vérifiées par assertion (provenance), sans être annotées sur la figure.

Palette maison : segment bas bleu (adhérence, plaine), segment haut vermillon
(crémaillère). LECTURE SEULE ; écrit un PNG. Byte-repro : SOURCE_DATE_EPOCH.
"""
import os, sys
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DIMGARE = ROOT / "data/dimension/dim_gare.parquet"
OUT = ROOT / "docs/memoire/figures/section_1_2_2/fig_profil_altimetrique.png"
ORDRE_MAX_BAS = 10          # BLON (Blonay) = dernière gare de plaine, incluse dans le bas
HORS = {"GIL", "CLIE"}      # gares fermées, sans altitude renseignée

# ---- données : 17 gares actives, ordonnées le long de la ligne -------------------
g = pd.read_parquet(DIMGARE, columns=["abreviation", "nom", "ordre", "km", "height"])
topo = g[~g.abreviation.isin(HORS)].sort_values("ordre").reset_index(drop=True)
assert len(topo) == 17, f"topologie courante = 17 gares attendues, obtenu {len(topo)}"
assert topo.height.notna().all(), "altitude manquante sur une gare active"

km = topo.km.astype(float).to_numpy()
alt = topo.height.astype(float).to_numpy()
nom = topo.nom.tolist()
est_bas = (topo.ordre <= ORDRE_MAX_BAS).to_numpy()

# ---- pentes maximales, recalculées depuis les données (provenance, pas annotées) --
pente = np.diff(alt) / (np.diff(km) * 1000.0) * 100.0            # % par tronçon adjacent
abbr = topo.abreviation.tolist()
i_bp = abbr.index("PRLZ") - 1        # tronçon BLON->PRLZ (juste après Blonay)
i_ol = abbr.index("LAL") - 1         # tronçon OND->LAL (juste avant Lally)
p_apres_blonay = pente[i_bp]
p_avant_lally = pente[i_ol]
assert abs(p_apres_blonay - 9.2) < 0.15, f"pente après Blonay = {p_apres_blonay:.2f} % (attendu ~9,2)"
assert abs(p_avant_lally - 23.0) < 0.3, f"pente avant Lally = {p_avant_lally:.2f} % (attendu ~23)"
assert abs(pente.max() - p_avant_lally) < 1e-9, "OND->LAL doit être la pente maximale de la ligne"

# ============================================================== figure
fs.apply_style()
fig, ax = plt.subplots(figsize=(6.30, 4.35))   # 16 cm de large
YMIN = 300

# --- remplissage du terrain, par segment (bleu bas / vermillon haut) --------------
mb = est_bas
mh = topo.ordre.to_numpy() >= ORDRE_MAX_BAS     # haut : de Blonay (inclus, jonction) aux Pléiades
ax.fill_between(km[mb], alt[mb], YMIN, color=fs.COULEUR_BAS, alpha=0.14, linewidth=0, zorder=1)
ax.fill_between(km[mh], alt[mh], YMIN, color=fs.COULEUR_HAUT, alpha=0.13, linewidth=0, zorder=1)

# --- profil : trait bleu (bas) puis trait vermillon épaissi (haut / crémaillère) ---
ax.plot(km[mb], alt[mb], color=fs.COULEUR_BAS, linewidth=1.9, zorder=4,
        solid_capstyle="round")
ax.plot(km[mh], alt[mh], color=fs.COULEUR_HAUT, linewidth=2.9, zorder=4,
        solid_capstyle="round")

# --- gares : marqueurs colorés par segment ----------------------------------------
ax.scatter(km[mb], alt[mb], s=20, color=fs.COULEUR_BAS, zorder=5,
           edgecolor="white", linewidth=0.6)
ax.scatter(km[~mb], alt[~mb], s=20, color=fs.COULEUR_HAUT, zorder=5,
           edgecolor="white", linewidth=0.6)

# --- noms des 17 gares : posés NETTEMENT au-dessus des points, jamais dessus -------
# Chaque nom est écrit à la verticale, son PREMIER caractère à un même écart en points
# écran au-dessus du marqueur — donc strictement identique d'une gare à l'autre, quelle
# que soit la longueur du nom. va="bottom" + rotation_mode="default" ancrent le bas du
# texte tourné (et non son milieu) : sans quoi les noms longs retomberaient sur le point.
GAP_PT = 6                                         # écart point → début du nom (points écran)
bbox = dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6)
for x, y, n, bas in zip(km, alt, nom, est_bas):
    coul = fs.COULEUR_BAS if bas else fs.COULEUR_HAUT
    ax.annotate(n, (x, y), xytext=(0, GAP_PT), textcoords="offset points",
                rotation=90, rotation_mode="default", ha="center", va="bottom",
                fontsize=6.8, color=coul, zorder=6, bbox=bbox)

# --- cadre, échelles, légende -----------------------------------------------------
ax.set_xlim(-0.35, 11.0)
ax.set_ylim(YMIN, 1780)
ax.set_xticks(np.arange(0, 11, 2))
ax.grid(axis="x", visible=False)
fs.finalize(ax, xlabel="Distance cumulée depuis Vevey (km)", ylabel="Altitude (m)")

legende = [
    Line2D([], [], color=fs.COULEUR_BAS, linewidth=1.9,
           label="Segment bas (adhérence)"),
    Line2D([], [], color=fs.COULEUR_HAUT, linewidth=2.9,
           label="Segment haut (crémaillère)"),
]
ax.legend(handles=legende, loc="upper left", fontsize=8, framealpha=0.92,
          borderpad=0.6, handlelength=1.8)

fs.save(fig, OUT)
plt.close(fig)
print("FIGURE:", OUT)
print(f"gares={len(topo)}  km {km[0]:.2f}->{km[-1]:.2f}  alt {alt[0]:.0f}->{alt[-1]:.0f} m")
print(f"pente après Blonay (BLON->PRLZ) = {p_apres_blonay:.2f} %")
print(f"pente avant Lally  (OND->LAL)   = {p_avant_lally:.2f} %  (max ligne)")
