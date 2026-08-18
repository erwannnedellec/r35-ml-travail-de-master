#!/usr/bin/env python3
"""figures_style.py - charte graphique unique des figures du chantier 1bis.

Une seule source de verite pour l'apparence des figures produites par les notebooks
canoniques : palette Okabe-Ito sure daltonisme, 300 DPI, libelles d'axes francais avec
unite, couleurs BAS/HAUT et trait du seuil UM figes, et un controle de conformite
bloquant a l'enregistrement.

Regles appliquees (spec validee au GATE volet 1) :
  - aucun titre dans l'image (ni ax.set_title, ni fig.suptitle) : le titre vit dans la
    legende du manuscrit ;
  - libelles d'axes et legendes en francais, jamais de nom de variable brut ;
  - pas de notation scientifique sur les axes : l'ordre de grandeur passe dans l'unite
    du libelle (ex. « Charge (milliers de voyageurs) »), jamais en multiplicateur d'axe ;
  - dates en francais (« 12 juin 2025 »), jamais au format ISO ;
  - multi-panneaux reperes par des lettres (a), (b), sans sous-titre descriptif ;
  - couleurs BAS/HAUT et trait du seuil UM definis une seule fois ici (memes teintes
    partout) ;
  - PNG reproductible : horodatage fige par SOURCE_DATE_EPOCH.

Les libelles proviennent du codebook canonique (colonnes libelle_fr + unite) : source
unique, pas de double maintenance. Voir docs/gabarit_notebooks.md et docs/glossaire.md.

Usage type dans un notebook canonique :

    import figures_style as fs
    fs.apply_style()
    fig, ax = plt.subplots()
    ax.hist(df["target_voyageurs_2eme_classe"], color=fs.COULEUR_BAS)
    fs.seuil_um_line(ax, orientation="v")
    fs.finalize(ax, x_col="target_voyageurs_2eme_classe", ylabel="Nombre de courses")
    ax.legend()
    fs.save(fig, "docs/figures/xxx.png")

Executer `python3 scripts/figures_style.py` lance un auto-test (figure conforme vs
non conforme).
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"

# --- Palette Okabe-Ito (sure daltonisme) ---
OKABE_ITO = [
    "#000000",  # noir
    "#E69F00",  # orange
    "#56B4E9",  # bleu ciel
    "#009E73",  # vert
    "#F0E442",  # jaune
    "#0072B2",  # bleu
    "#D55E00",  # vermillon
    "#CC79A7",  # mauve
]

# --- Constantes metier figees (memes teintes partout) ---
COULEUR_BAS = "#0072B2"   # segment BAS (pendulaire, plaine)
COULEUR_HAUT = "#D55E00"  # segment HAUT (touristique, cremaillere)
COULEURS_SEGMENT = {"BAS": COULEUR_BAS, "HAUT": COULEUR_HAUT}

SEUIL_UM = 63
SEUIL_UM_LIBELLE = "Seuil UM : 63 places assises 2e classe"
SEUIL_UM_KW = dict(color="#000000", linestyle="--", linewidth=1.2, zorder=1)

# Prefixes de familles de colonnes : detecte une fuite de nom brut dans un libelle.
_RAW_PREFIX = re.compile(
    r"(?:^|_)(?:target|base|histo|meteo|ist|vmcv|spatial|resa|simba|horaire|event|cal|id)_"
)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Mois francais (independant de la locale du systeme).
_MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


# ---------------------------------------------------------------------------
# Reproductibilite
# ---------------------------------------------------------------------------

def source_date_epoch() -> int:
    """Horodatage de gel (repli sur le gel v1.9, 2026-06-21 UTC)."""
    return int(os.environ.get("SOURCE_DATE_EPOCH", "1782000000"))


# ---------------------------------------------------------------------------
# Style global
# ---------------------------------------------------------------------------

def apply_style() -> None:
    """Applique les rcParams de la charte (idempotent).

    Raffinements charte v2 (2026-07) : police Helvetica Neue (repli Arial puis
    DejaVu Sans), cadre despine (spines haut et droite masquees), grille legere
    posee sous les traces, mise en page « constrained » par defaut (evite les
    chevauchements et les elements hors cadre sans recours a bbox=tight). La
    palette Okabe-Ito, l'interdiction de titre embarque et l'interdiction de
    notation scientifique sont inchangees.

    Reproductibilite : la police doit etre presente sur la machine de
    regeneration ; a defaut le repli DejaVu Sans s'applique (meme structure,
    glyphes differents). Les PNG restent byte-reproductibles a police constante.
    """
    mpl.rcParams.update({
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 11,
        "axes.labelsize": 11.5,
        "axes.titlesize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.frameon": True,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "#cccccc",
        "axes.grid": True,
        "grid.color": "#b0b0b0",
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        # Cadre allege : despine haut/droite, axes gris fonce fins.
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#444444",
        "axes.linewidth": 0.8,
        "axes.labelcolor": "#222222",
        "text.color": "#222222",
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        # Mise en page automatique (remplace savefig.bbox=tight, qui rognait).
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.06,
        "figure.constrained_layout.w_pad": 0.06,
        "axes.prop_cycle": mpl.cycler(color=OKABE_ITO),
        # Jamais de notation scientifique ni d'offset commun.
        "axes.formatter.useoffset": False,
        "axes.formatter.use_mathtext": False,
        "axes.formatter.limits": (-9, 9),
    })


# ---------------------------------------------------------------------------
# Libelles : source unique = codebook canonique (libelle_fr + unite)
# ---------------------------------------------------------------------------

_LABELS_CACHE = None


def _labels() -> dict:
    global _LABELS_CACHE
    if _LABELS_CACHE is None:
        cb = pd.read_csv(CODEBOOK)
        d = {}
        for _, r in cb.iterrows():
            lib = str(r["libelle_fr"]).strip()
            uni = "" if pd.isna(r["unite"]) else str(r["unite"]).strip()
            d[str(r["colonne"])] = f"{lib} ({uni})" if uni else lib
        _LABELS_CACHE = d
    return _LABELS_CACHE


def label_for(col: str) -> str:
    """Libelle francais complet « Libelle (unite) » d'une colonne du dataset."""
    lab = _labels().get(col)
    if lab is None:
        raise KeyError(
            f"Colonne absente du codebook : {col!r}. Ajouter une exception dans "
            f"scripts/build_codebook_canonique.py (LIBELLE_EXCEPTIONS) puis regenerer."
        )
    return lab


class _Labels:
    """Acces dict-like aux libelles (fs.LABELS[col])."""

    def __getitem__(self, col: str) -> str:
        return label_for(col)

    def get(self, col: str, default=None):
        try:
            return label_for(col)
        except KeyError:
            return default

    def __contains__(self, col: str) -> bool:
        return col in _labels()


LABELS = _Labels()


# ---------------------------------------------------------------------------
# Finalisation d'un axe
# ---------------------------------------------------------------------------

def _check_libelle(txt: str, axe: str) -> None:
    if "_" in txt or _RAW_PREFIX.search(txt):
        raise ValueError(f"Libelle d'axe {axe} brut (nom de variable) : {txt!r}")


def finalize(ax, *, xlabel=None, ylabel=None, x_col=None, y_col=None, periode=None):
    """Pose les libelles d'axes francais, desactive la notation scientifique.

    xlabel/ylabel : chaine explicite. x_col/y_col : nom de colonne, resolu via le
    codebook. periode : note de perimetre affichee en bas a droite (ex. « H25 »).
    """
    xl = xlabel if xlabel is not None else (label_for(x_col) if x_col else None)
    yl = ylabel if ylabel is not None else (label_for(y_col) if y_col else None)
    if xl is not None:
        _check_libelle(xl, "x")
        ax.set_xlabel(xl)
    if yl is not None:
        _check_libelle(yl, "y")
        ax.set_ylabel(yl)
    try:
        ax.ticklabel_format(style="plain", axis="both", useOffset=False)
    except (AttributeError, ValueError):
        # axe categoriel ou de dates : pas de formatter numerique.
        pass
    if periode:
        ax.annotate(
            periode, xy=(1.0, -0.14), xycoords="axes fraction",
            ha="right", va="top", fontsize=8, color="#555555",
        )
    return ax


def french_date_axis(ax, which: str = "x"):
    """Formate un axe temporel en francais (« 12 juin 2025 »), jamais en ISO."""
    def _fmt(x, pos=None):
        d = mpl.dates.num2date(x)
        return f"{d.day} {_MOIS_FR[d.month]} {d.year}"

    axis = ax.xaxis if which == "x" else ax.yaxis
    axis.set_major_formatter(mpl.ticker.FuncFormatter(_fmt))
    return ax


def echelle_milliers(ax, which: str = "y"):
    """Divise les graduations par 1000 (l'unite « (milliers ...) » va dans le libelle,
    jamais de multiplicateur d'axe)."""
    axis = ax.yaxis if which == "y" else ax.xaxis
    axis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, p: f"{v / 1000:g}"))
    return ax


def seuil_um_line(ax, orientation: str = "h", annotate: bool = True):
    """Trace le seuil UM (63) avec le style et le libelle uniques de la charte."""
    if orientation == "h":
        ax.axhline(SEUIL_UM, **SEUIL_UM_KW)
    else:
        ax.axvline(SEUIL_UM, **SEUIL_UM_KW)
    if annotate:
        trait = {k: v for k, v in SEUIL_UM_KW.items()
                 if k in ("color", "linestyle", "linewidth")}
        ax.plot([], [], label=SEUIL_UM_LIBELLE, **trait)
    return ax


def lettre_panneau(ax, lettre: str, x: float = -0.08, y: float = 1.02):
    """Repere un panneau par une lettre (a), (b) sans sous-titre descriptif."""
    ax.text(x, y, f"({lettre})", transform=ax.transAxes, fontweight="bold",
            fontsize=11, ha="right", va="bottom")
    return ax


# ---------------------------------------------------------------------------
# Controle de conformite (bloquant a l'enregistrement)
# ---------------------------------------------------------------------------

def _a_un_voisin_libelle(ax, which: str) -> bool:
    """Vrai si l'axe partage son axe x (ou y) avec un panneau deja libelle.

    Tolere un libelle vide sur un panneau d'axes PARTAGES (sharex/sharey) des lors
    qu'un panneau frere porte le libelle : evite la redondance sur les figures
    multi-panneaux a axe commun, sans relacher l'exigence sur les axes autonomes.
    """
    try:
        grouper = ax.get_shared_x_axes() if which == "x" else ax.get_shared_y_axes()
        siblings = list(grouper.get_siblings(ax))
    except Exception:
        return False
    for s in siblings:
        if s is ax:
            continue
        lab = s.get_xlabel() if which == "x" else s.get_ylabel()
        if lab.strip():
            return True
    return False


def check_conformite(fig) -> list:
    """Retourne la liste des non-conformites d'une figure vivante (vide = conforme)."""
    problems = []
    try:
        fig.canvas.draw()  # realise les ticklabels et l'offset text
    except Exception:
        pass

    sup = getattr(fig, "_suptitle", None)
    if sup is not None and sup.get_text().strip():
        problems.append(f"suptitle present : {sup.get_text()!r} (le titre va dans la legende)")

    for i, ax in enumerate(fig.get_axes()):
        if ax.get_label() == "<colorbar>":
            continue
        if ax.get_title().strip():
            problems.append(f"axe {i}: titre dans l'image ({ax.get_title()!r})")
        for nom, lab in (("x", ax.get_xlabel()), ("y", ax.get_ylabel())):
            if not lab.strip():
                if ax.has_data() and not _a_un_voisin_libelle(ax, nom):
                    problems.append(f"axe {i}: libelle {nom} manquant")
            elif "_" in lab or _RAW_PREFIX.search(lab):
                problems.append(f"axe {i}: libelle {nom} brut ({lab!r})")
        off = (ax.yaxis.get_offset_text().get_text()
               + ax.xaxis.get_offset_text().get_text())
        if off.strip():
            problems.append(f"axe {i}: notation scientifique/offset ({off!r})")
        leg = ax.get_legend()
        if leg is not None:
            for t in leg.get_texts():
                s = t.get_text()
                if "_" in s or _RAW_PREFIX.search(s):
                    problems.append(f"axe {i}: entree de legende brute ({s!r})")
        for nom, axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            for tl in axis.get_ticklabels():
                if _ISO_DATE.search(tl.get_text()):
                    problems.append(f"axe {i}: graduation {nom} au format ISO ({tl.get_text()!r})")
                    break
    return problems


def save(fig, path, check: bool = True):
    """Enregistre en PNG 300 DPI, horodatage fige (SOURCE_DATE_EPOCH). Leve si non conforme."""
    path = Path(path)
    if check:
        problems = check_conformite(fig)
        if problems:
            raise ValueError(
                "Figure non conforme a la charte :\n  - " + "\n  - ".join(problems)
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.utcfromtimestamp(source_date_epoch())
    metadata = {
        "Creation Time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Software": "figures_style.py (charte R35, chantier 1bis)",
    }
    # Pas de bbox_inches="tight" : la mise en page « constrained » (apply_style)
    # gere l'espacement et evite le rognage des legendes/annotations hors axes.
    fig.savefig(path, dpi=300, metadata=metadata)
    return path


# ---------------------------------------------------------------------------
# Inventaire de conformite des figures deja exportees (docs/memoire/figures)
# ---------------------------------------------------------------------------

def inventaire_figures_memoire(dossier="docs/memoire/figures") -> pd.DataFrame:
    """Inventorie les PNG deja exportes (nom, taille, producteur au depot si trouve).

    Limite honnete : un PNG n'expose pas ses axes ; check_conformite ne s'applique
    qu'aux figures VIVANTES (in-notebook). Cette fonction ne modifie rien : elle
    produit un inventaire a joindre au rapport pour revue manuelle.
    """
    base = ROOT / dossier
    rows = []
    if base.exists():
        for png in sorted(base.rglob("*.png")):
            rows.append({
                "figure": str(png.relative_to(ROOT)),
                "taille_ko": round(png.stat().st_size / 1024, 1),
                "producteur_au_depot": "a rechercher (grep du nom dans notebooks/ scripts/)",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Auto-test
# ---------------------------------------------------------------------------

def _autotest() -> int:
    apply_style()
    ok = True

    # (1) Figure conforme.
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [10, 40, 70], color=COULEUR_BAS)
    seuil_um_line(ax, orientation="h")
    finalize(ax, xlabel="Rang du tronçon", ylabel="Charge de 2e classe (voyageurs)")
    ax.legend()
    prob = check_conformite(fig)
    print("conforme -> non-conformites:", prob)
    ok = ok and (prob == [])
    plt.close(fig)

    # (2) Figure non conforme (titre + label brut + suptitle).
    fig, ax = plt.subplots()
    fig.suptitle("Titre interdit")
    ax.plot([0, 1], [1, 2])
    ax.set_title("titre dans l'image")
    ax.set_xlabel("target_voyageurs_2eme_classe")
    prob = check_conformite(fig)
    print("non conforme -> non-conformites detectees:", len(prob))
    for p in prob:
        print("   -", p)
    ok = ok and (len(prob) >= 3)
    plt.close(fig)

    # (3) Libelle depuis le codebook.
    print("label_for(cible) =", label_for("target_voyageurs_2eme_classe"))
    print("COULEURS_SEGMENT =", COULEURS_SEGMENT)

    print("\nAUTO-TEST:", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(_autotest())
