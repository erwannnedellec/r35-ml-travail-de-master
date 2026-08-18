#!/usr/bin/env python3
"""figstyle.py — référence unique des figures du mémoire (couche mémoire au-dessus de la charte maison).

Consolidation (2026-07-12) : ce module n'a plus SA PROPRE palette ni SES PROPRES rcParams.
Il IMPORTE `scripts/figures_style.py` — source unique de la palette Okabe-Ito et des
rcParams — et n'ajoute que la couche spécifique au manuscrit : largeurs normalisées
(LARGE=16 cm, DEMI=8 cm) et un enregistrement `save_fig` sans titre embarqué.

Arbitrage de mise en page : figstyle enregistre en `bbox_inches='tight'` (figures insérées
à taille fixe dans le document) et désactive donc `constrained_layout` (mécanisme de la
charte notebooks) — les deux ne se combinent pas ; ici tight prime, partout.

Consommateurs de l'ancienne charte (`figures_style` direct), non migrés, hors périmètre :
notebooks 02_apc/02_evenements/02_ressys/03c/03h/08, scripts build_codebook_canonique.py,
experiences/render_supports_ba493568.py, docs/memoire/synthese_surcharges/*.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))
import figures_style as _house  # charte maison : source unique palette + rcParams  # noqa: E402

# ---------------------------------------------------------------------------
# Palette Okabe-Ito — RÉFÉRENCÉE depuis la charte maison (valeurs non redéfinies)
# ---------------------------------------------------------------------------
_HEX = _house.OKABE_ITO  # liste ordonnée [noir, orange, bleu_ciel, vert, jaune, bleu, vermillon, mauve]
OKABE_ITO: dict[str, str] = {
    "noir": _HEX[0], "orange": _HEX[1], "bleu_ciel": _HEX[2], "vert": _HEX[3],
    "jaune": _HEX[4], "bleu": _HEX[5], "vermillon": _HEX[6], "mauve": _HEX[7],
}
OKABE_ITO_CYCLE: list[str] = [
    OKABE_ITO["bleu"], OKABE_ITO["vermillon"], OKABE_ITO["vert"],
    OKABE_ITO["orange"], OKABE_ITO["bleu_ciel"], OKABE_ITO["mauve"], OKABE_ITO["jaune"],
]
COULEUR_BAS = _house.COULEUR_BAS      # segment BAS (source unique)
COULEUR_HAUT = _house.COULEUR_HAUT    # segment HAUT (source unique)

# ---------------------------------------------------------------------------
# Largeurs standard (cm -> pouces)
# ---------------------------------------------------------------------------
CM = 1.0 / 2.54
LARGE = 16.0 * CM   # ~6.30 in — pleine largeur de colonne
DEMI = 8.0 * CM     # ~3.15 in — demi-largeur

# ---------------------------------------------------------------------------
# Style global : délègue à la charte maison, puis applique le seul delta mémoire
# ---------------------------------------------------------------------------

def apply_style() -> None:
    """Applique les rcParams de la charte maison (source unique), puis le delta mémoire.

    Delta unique : `constrained_layout` désactivé (figstyle enregistre en bbox=tight).
    Aucune autre redéfinition de rcParams ni de palette ici.
    """
    _house.apply_style()
    mpl.rcParams.update({
        "figure.constrained_layout.use": False,
        "figure.autolayout": False,
    })


def new_fig(largeur: float = LARGE, hauteur: float | None = None):
    """Crée (fig, ax) à la largeur standard. hauteur par défaut = largeur / 1.6."""
    if hauteur is None:
        hauteur = largeur / 1.6
    return plt.subplots(figsize=(largeur, hauteur))


def sequential_cmap(vers: str = "bleu"):
    """Rampe séquentielle blanc -> teinte Okabe-Ito (compatible daltonisme, lisible en gris)."""
    return LinearSegmentedColormap.from_list(
        f"okabe_seq_{vers}", ["#ffffff", OKABE_ITO[vers]], N=256
    )


# ---------------------------------------------------------------------------
# Enregistrement mémoire : PNG 300 DPI, bbox_inches='tight', sans titre embarqué
# ---------------------------------------------------------------------------

def _assert_sans_titre(fig) -> None:
    sup = getattr(fig, "_suptitle", None)
    if sup is not None and sup.get_text().strip():
        raise ValueError(f"Titre embarqué interdit (suptitle) : {sup.get_text()!r}")
    for i, ax in enumerate(fig.get_axes()):
        if ax.get_title().strip():
            raise ValueError(f"Titre embarqué interdit (axe {i}) : {ax.get_title()!r}")


def save_fig(fig, nom: str, dossier, largeur: float = LARGE):
    """Enregistre `fig` en PNG 300 DPI, bbox_inches='tight', sans titre embarqué.

    Écrit `dossier/nom`. La largeur standard est imposée à l'enregistrement (ratio conservé).
    Renvoie le chemin écrit.
    """
    _assert_sans_titre(fig)
    if not nom.lower().endswith(".png"):
        nom = f"{nom}.png"
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    l0, h0 = fig.get_size_inches()
    fig.set_size_inches(largeur, h0 * (largeur / l0) if l0 else largeur / 1.6)
    fig.savefig(chemin, dpi=300, bbox_inches="tight",
                metadata={"Software": "src/memoire/figstyle.py (charte mémoire R35)"})
    return chemin
