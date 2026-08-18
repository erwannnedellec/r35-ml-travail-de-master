#!/usr/bin/env python3
"""Section 4.4.3 — fig_architecture_pipeline.png (registre mémoire académique).

Schéma sobre de l'architecture du pipeline de données : flux gauche -> droite des
sources brutes vers la table canonique de modélisation, en écho au vocabulaire visuel
de fig_entonnoir_variables (§4.5.4) et fig_4_entonnoir_apc (§4.4.1) : une SEULE couleur
de bloc (bleu Okabe-Ito), blocs arrondis, connecteurs gris, étiquette d'opération SOUS
chaque connecteur. Remplace le marque-place fig_4_pipeline_medaillon.

Quatre états de la donnée, chacun une couche réelle du dépôt (source : scripts/pipeline/
paths.py, « unique source de vérité pour tous les noms de fichiers ») :

  Sources brutes  --normalisation-->  Tables propres  --enrichissement-->  Table
  (immuables)                         (une par source)   (dix étapes)      enrichie
                                                                              |
                                                        --filtre temporel (H22-H25)-->
                                                                              v
                                                                       Table canonique

Les noms de couches du dépôt sont anglais (médaillon bronze / silver / gold) : ils sont
ici DÉCRITS PAR FONCTION en français, jamais repris tels quels. Aucun identifiant interne
(pas de hash, pas de nom de fichier, pas de « stage_NN »), aucun titre embarqué, tous les
accents.

La multiplicité des sources et des tables propres (fan-in) est portée par un empilement
de blocs ; le passage à un seul flux (épine APC enrichie) marque l'intégration. Les deux
premiers blocs sont donc empilés, les deux derniers uniques.

RIEN N'EST INVENTÉ : verify() importe scripts/pipeline/paths.py et vérifie, contre le
dépôt, que la chaîne va bien de stage_01 à stage_10 puis à la table canonique, que la
couche « tables propres par source » existe, et que les sources brutes (APC + externes)
existent. Le libellé « dix étapes » est adossé à l'amplitude stage_01..stage_10 (écho de
la légende de §4.4.1, « dix stages successifs sans modification de cardinalité »).

Charte src/memoire/figstyle.py : Okabe-Ito, 16 cm, 300 DPI, bbox tight, sans titre
embarqué. Reproductibilité byte-à-byte : SOURCE_DATE_EPOCH=1782000000 en tête.
LECTURE SEULE (vérifie l'existence de chemins), écrit un PNG.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")  # byte-repro, avant matplotlib

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
sys.path.insert(0, str(ROOT / "scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon  # noqa: E402

# Familles de sources RÉELLES mobilisées par la chaîne d'enrichissement de la table
# canonique (annexe catalogue des sources, fiches S01-S12 ; hors S08 rotations, qui
# n'alimente pas ml_dataset mais l'évaluation de la couche 2). APC est l'épine ;
# les dix familles suivantes sont les sources d'enrichissement successives.
SOURCES_FAMILLES = [
    "comptages APC", "horaires publiés", "ponctualité", "météo", "population",
    "emploi", "demande origine-destination", "réservations de groupes",
    "événements", "ski", "vacances et jours fériés",
]


def verify() -> None:
    """Adosse le schéma au dépôt réel (aucune structure inventée).

    Vérifie via scripts/pipeline/paths.py :
      - sources brutes immuables : data/raw et data/external existent ;
      - tables propres par source (silver) : data/processed/sources existe ;
      - chaîne d'enrichissement : la première et la dernière étape sont bien
        stage_01 et stage_10 (amplitude qui fonde le libellé « dix étapes ») ;
      - table canonique : ml_dataset existe.
    """
    from pipeline import paths as P

    assert P.RAW.is_dir(), "sources brutes APC (data/raw) absentes"
    assert P.EXTERNAL.is_dir(), "sources externes (data/external) absentes"
    assert P.SOURCES.is_dir(), "couche des tables propres par source (sources/) absente"
    assert P.STAGE_01_ANNEE.name.startswith("stage_01"), "première étape != stage_01"
    assert P.STAGE_10_RESERVATIONS.name.startswith("stage_10"), "dernière étape != stage_10"
    assert P.STAGE_01_ANNEE.exists(), "stage_01 (début de chaîne) absent du dépôt"
    assert P.STAGE_10_RESERVATIONS.exists(), "stage_10 (fin de chaîne) absent du dépôt"
    assert P.ML_DATASET.exists(), "table canonique (ml_dataset) absente du dépôt"
    # Amplitude stage_01..stage_10 : justifie « dix étapes ».
    principaux = sorted({
        int(p.stem.split("_")[1][:2])
        for p in P.PROCESSED.glob("stage_*.parquet")
    })
    assert principaux and principaux[0] == 1 and principaux[-1] == 10, \
        f"amplitude de la chaîne inattendue : {principaux}"


def main() -> int:
    verify()
    BLEU = fs.OKABE_ITO["bleu"]

    # Quatre états de la donnée (gauche -> droite). empile = fan-in (plusieurs objets).
    blocs = [
        dict(titre="Sources\nbrutes",   sous="immuables",       empile=True),
        dict(titre="Tables\npropres",   sous="une par source",  empile=True),
        dict(titre="Table\nenrichie",   sous="sources jointes",  empile=False),
        dict(titre="Table\ncanonique",  sous="de modélisation",  empile=False),
    ]
    # Opérations (couches de raffinement), étiquette SOUS le connecteur ; phrasé aligné
    # sur la figure sœur fig_4_entonnoir_apc (§4.4.1).
    ops = ["normalisation",
           "enrichissement (dix étapes)\ncardinalité invariante",
           "filtre temporel\nH22-H25"]

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.46)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    yc, H, Wb = 0.60, 0.32, 0.150
    xs = [0.135 + i * 0.2433 for i in range(4)]          # centres à espacement égal
    y_sous = yc - 0.100
    y_op = yc - H / 2 - 0.055
    y_sources = 0.16

    def carte(x, y, ec="#1a1a1a", fc=None, alpha=1.0, z=3):
        ax.add_patch(FancyBboxPatch(
            (x - Wb / 2, y - H / 2), Wb, H,
            boxstyle="round,pad=0.004,rounding_size=0.020",
            linewidth=1.0, edgecolor=ec, facecolor=fc if fc else BLEU,
            alpha=alpha, zorder=z))

    def bloc(x, b):
        # Empilement (fan-in) : deux cartes décalées en arrière-plan haut-droite.
        if b["empile"]:
            for k in (2, 1):
                carte(x + 0.011 * k, yc + 0.016 * k, fc=BLEU, alpha=1.0, z=2)
        carte(x, yc, z=3)
        ax.text(x, yc + 0.035, b["titre"], ha="center", va="center", fontsize=10.5,
                fontweight="bold", color="white", linespacing=1.0, zorder=4)
        ax.text(x, y_sous, b["sous"], ha="center", va="center", fontsize=7.0,
                color="#eaf2f8", zorder=4)

    def connecteur(xa, xb, label):
        x0 = xa + Wb / 2
        x1 = xb - Wb / 2
        bh = 0.050                                        # demi-hauteur du corps (hampe)
        hh = 0.088                                        # demi-hauteur de la tête
        tip = 0.024                                       # longueur de la pointe
        # Hampe + tête triangulaire : flèche grise sobre indiquant le sens du flux.
        ax.add_patch(Polygon(
            [(x0, yc - bh), (x1 - tip, yc - bh), (x1 - tip, yc - hh),
             (x1, yc), (x1 - tip, yc + hh), (x1 - tip, yc + bh)],
            closed=True, facecolor="#dcdcdc", edgecolor="none", zorder=1))
        xm = (x0 + x1) / 2
        ax.text(xm, y_op, label, ha="center", va="top", fontsize=7.2,
                color="#333333", linespacing=1.4, zorder=4)

    for i in range(3):
        connecteur(xs[i], xs[i + 1], ops[i])
    for x, b in zip(xs, blocs):
        bloc(x, b)

    # Énumération des familles de sources, note grise discrète en pied (registre sobre),
    # sur deux lignes centrées pour rester dans la largeur de la bande.
    fam = SOURCES_FAMILLES
    ligne = "Sources : " + ", ".join(fam[:6]) + ",\n" + ", ".join(fam[6:])
    ax.text(0.5, y_sources, ligne, ha="center", va="center", fontsize=6.6,
            color="#7a7a7a", linespacing=1.5, zorder=4)

    p = fs.save_fig(fig, "fig_architecture_pipeline", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
