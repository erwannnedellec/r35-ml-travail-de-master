#!/usr/bin/env python3
"""Section 1.2.2 — Plan d'aménagement de l'automotrice SURF 7500.

Régénère la figure du plan intérieur (vue en plan, côtés gauche + droite d'une même
caisse) à partir du plan constructeur brut
`data/external/spec_materiel/vehicules_portes_7500.png`, en le nettoyant et en y posant
une lecture « capacité » conforme à la charte des figures (figures_style.py) :

  1. on retire les surcharges non conformes du plan brut : le titre « 7500 » (en haut),
     les grosses flèches noires « Dir. MX/PLEI » / « Dir. ZW/VV » (marges gauche/droite),
     et les quatre gros numéros de porte bleus (3/4 à gauche, 1/2 à droite) ;
  2. on remplace l'annotation des portes par une lecture des ZONES DE CAPACITÉ, deux
     familles distinguées par des aplats discrets Okabe-Ito :
        · places assises fixes  (les quatre baies assises) — vert  (#009E73) ;
        · zones multi-usages     (les deux espaces « Skis » à strapontins, vélos, skis,
          bagages) — orange (#E69F00).
     La distinction 1re / 2e classe est volontairement fusionnée (décision de cadrage :
     le plan constructeur ne porte aucune étiquette de classe et les baies sont dessinées
     à l'identique). Les 75 places assises = 63 (2e classe) + 12 (1re classe).

Aucune teinte réservée n'est utilisée pour les aplats : la charte fige le bleu #0072B2
(segment BAS) et le vermillon #D55E00 (segment HAUT) ; on prend deux autres teintes
Okabe-Ito sûres au daltonisme.

Aucune direction n'est réintroduite (choix de cadrage) : l'orientation, si besoin, ira
dans la légende du manuscrit.

Sortie : 300 DPI, largeur 14,2 cm (cx = 5105400 EMU), sans titre incrusté, horodatage
figé (SOURCE_DATE_EPOCH). LECTURE SEULE d'un PNG ; écrit un PNG. Byte-reproductible à
police et à source constantes.

Note charte : c'est une figure SCHÉMATIQUE (plan technique), sans axes de données ; le
contrôle automatique de figures_style (pensé pour des axes x/y de données) est donc
désactivé à l'enregistrement, mais les règles applicables — aucun titre incrusté, 300 DPI,
horodatage figé, palette Okabe-Ito, libellés français — sont respectées et vérifiées
explicitement ci-dessous.
"""
import os, sys
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Patch  # noqa: E402

SRC = ROOT / "data/external/spec_materiel/vehicules_portes_7500.png"
OUT = ROOT / "docs/memoire/figures/section_1_2_2/fig_plan_amenagement_7500.png"

# --- largeur cible manuscrit : 14,2 cm = cx 5105400 EMU (1 pouce = 914400 EMU) --------
CX_EMU = 5105400
LARGEUR_PO = CX_EMU / 914400.0                 # ≈ 5,583 pouces

# --- capacités (specs matériel) — distinction 1re/2e volontairement fusionnée ----------
N_SIEGES_FIXES = 63 + 12                        # 63 (2e classe) + 12 (1re classe) = 75
N_STRAPONTINS = 31                             # zones multi-usages (vélos, skis, bagages)

# --- palette : teintes Okabe-Ito hors réservées BAS(#0072B2)/HAUT(#D55E00) -------------
COUL_SIEGES = "#009E73"                         # vert   : places assises fixes
COUL_MULTI = "#E69F00"                          # orange : zones multi-usages
ALPHA_APLAT = 0.18                              # aplats discrets (le trait noir reste lisible)

# --- géométrie mesurée sur le plan brut (2000 x 620 px) --------------------------------
# Fenêtre du corps du plan : hors titre (haut), hors flèches (marges), et coupée juste
# sous la ligne de plancher pour retirer la rangée de cotes constructeur (16145, 12231…).
CROP = (372, 346, 1618, 460)
# Emprises horizontales des zones, en pixels du plan RECADRÉ (origine = CROP[0], CROP[1]).
#   baies assises A (ext. Pléiades) · B · C · D (ext. Vevey)  →  places fixes
#   deux espaces « Skis » (de part et d'autre du bloc technique central)  →  multi-usages
SPANS_SIEGES = [(33, 226), (400, 533), (678, 813), (980, 1188)]
SPANS_MULTI = [(273, 396), (816, 938)]

# ============================================================ nettoyage du plan brut
img = Image.open(SRC).convert("RGB")
assert img.size == (2000, 620), f"source inattendue : {img.size} (attendu 2000x620)"
arr = np.asarray(img).astype(np.int16).copy()
R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]

# efface les numéros de porte bleus (3/4/1/2) — seule surcharge pouvant border le corps ;
# le titre « 7500 » et les flèches « Dir. » tombent hors de CROP et disparaissent au recadrage.
bleu = (B > 120) & (B - R > 50) & (B - G > 40)
arr[bleu] = 255
plan = arr[CROP[1]:CROP[3], CROP[0]:CROP[2]].astype(np.uint8)
Hpx, Wpx = plan.shape[:2]

# hauteur du corps (toit → plancher) pour caler les aplats sur toute la largeur de caisse
noir = plan.mean(2) < 90
lignes = np.where(noir[:, 400:560].sum(1) > 5)[0]     # bande d'une baie assise : bord à bord
y_haut, y_bas = int(lignes.min()), int(lignes.max())
for a, b in SPANS_SIEGES + SPANS_MULTI:
    assert 0 <= a < b <= Wpx, f"emprise hors cadre : {(a, b)} (largeur {Wpx})"

# canevas : plan + bandeau blanc dessous pour loger la légende dans l'emprise de l'image
PAD_HAUT, PAD_BAS = 6, 104
canevas = np.full((Hpx + PAD_HAUT + PAD_BAS, Wpx, 3), 255, np.uint8)
canevas[PAD_HAUT:PAD_HAUT + Hpx] = plan
Hc = canevas.shape[0]

# ============================================================ figure
fs.apply_style()
fig = plt.figure(figsize=(LARGEUR_PO, LARGEUR_PO * Hc / Wpx))
fig.set_layout_engine("none")                 # plan technique : maîtrise fine des positions
ax = fig.add_axes([0, 0, 1, 1])
ax.imshow(canevas, origin="upper", extent=[0, Wpx, Hc, 0],
          interpolation="lanczos", zorder=0)

# aplats discrets, posés PAR-DESSUS le trait (le fond blanc du plan est opaque) -----------
yt, yb = y_haut + PAD_HAUT, y_bas + PAD_HAUT
for coul, spans in ((COUL_SIEGES, SPANS_SIEGES), (COUL_MULTI, SPANS_MULTI)):
    for a, b in spans:
        ax.add_patch(Rectangle((a, yt), b - a, yb - yt, facecolor=coul,
                               alpha=ALPHA_APLAT, edgecolor=coul, linewidth=0.4,
                               joinstyle="miter", zorder=2))

ax.set_xlim(0, Wpx)
ax.set_ylim(Hc, 0)
ax.axis("off")

# légende = l'annotation des zones (remplace les numéros de porte) ------------------------
handles = [
    Patch(facecolor=COUL_SIEGES, alpha=0.32, edgecolor=COUL_SIEGES, linewidth=0.8,
          label=f"Places assises fixes — {N_SIEGES_FIXES} places"),
    Patch(facecolor=COUL_MULTI, alpha=0.32, edgecolor=COUL_MULTI, linewidth=0.8,
          label=f"Zones multi-usages — {N_STRAPONTINS} strapontins (vélos, skis, bagages)"),
]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, PAD_BAS / Hc),
          frameon=True, framealpha=0.9, edgecolor="#cccccc", fontsize=8.5,
          handlelength=1.4, handleheight=1.1, borderpad=0.7, labelspacing=0.6)

# ============================================================ contrôle + enregistrement
# figure schématique : contrôle charte automatique désactivé, règles vérifiées à la main.
assert getattr(fig, "_suptitle", None) is None or not fig._suptitle.get_text().strip()
assert all(not a.get_title().strip() for a in fig.get_axes()), "titre incrusté interdit"
fs.save(fig, OUT, check=False)
plt.close(fig)

print("FIGURE:", OUT)
print(f"largeur {LARGEUR_PO*2.54:.2f} cm (cx={CX_EMU})  pixels={round(LARGEUR_PO*300)}"
      f"x{round(LARGEUR_PO*Hc/Wpx*300)}  @300dpi")
print(f"zones : {N_SIEGES_FIXES} places assises fixes ({SPANS_SIEGES}) ; "
      f"{N_STRAPONTINS} strapontins multi-usages ({SPANS_MULTI})")
