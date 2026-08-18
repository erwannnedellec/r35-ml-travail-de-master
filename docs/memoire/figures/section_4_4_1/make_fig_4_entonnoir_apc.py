#!/usr/bin/env python3
"""Section 4.4.1 — fig_4_entonnoir_apc.png (version sobre, registre mémoire).

Cascade/entonnoir HORIZONTAL de construction du jeu de données APC, en écho exact de
fig_entonnoir_variables (§4.5.4). Registre académique sobre : une SEULE couleur de bloc
(bleu Okabe-Ito), la progression portée par les effectifs et la LARGEUR des blocs. Les
trois premiers blocs ont une largeur STRICTEMENT identique — l'invariance de cardinalité
EST le message (le dédoublonnage retire 1 252 lignes sur 2,36 M, l'enrichissement n'en
retire aucune) ; le dernier bloc est réduit proportionnellement (filtre temporel H22-H25).
Aucun titre embarqué, tous les accents, aucun franglais. Charte maison figstyle : 300 DPI,
bbox tight, SOURCE_DATE_EPOCH. Largeur 16 cm.

Chaîne : 2 362 014 → 2 360 762 → 2 360 762 → 1 141 984 lignes. Étiquette sobre sous chaque
connecteur (opération + delta typographique, sans numérotation ni gras) ; sous le bloc
final, une ligne grise discrète donne la répartition par année horaire.

Effectifs LUS du pipeline (aucun chiffre codé en dur) :
  - brut          = apc_stacked + doublons nets (dérivés de raw_duplicates)
  - dédoublonnage = apc_stacked.parquet
  - enrichissement= stage_01 = stage_10 (invariance vérifiée par assert)
  - filtre        = ml_dataset.parquet, répartition lue de horaire_annee_horaire
Chaîne réconciliée par assert ; garde de provenance sur l'empreinte canonique. Aucune
interprétation.
"""
import os
os.environ["SOURCE_DATE_EPOCH"] = "1782000000"
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

HASH = "ba493568"
PROC = ROOT / "data" / "processed"
APC = PROC / "sources" / "apc_stacked.parquet"
STAGE_01 = PROC / "stage_01_annee_horaire.parquet"
STAGE_10 = PROC / "stage_10_reservations.parquet"
RAW_DUP = PROC / "raw_duplicates.parquet"
ML = PROC / "ml_dataset.parquet"

# Clé de dédoublonnage : les 31 colonnes du schéma brut (stack_raw_csv.py:71-103).
RAW_SCHEMA_COLUMNS = [
    "date", "numero_train", "code_et", "code_debiteur", "gare_depart", "gare_arrivee",
    "code_offre", "troncon_tgl", "tx_equipement_afz_1ere_classe",
    "tx_equipement_afz_2eme_classe", "offre_1ere_classe", "offre_2eme_classe",
    "voyageurs_1ere_classe", "voyageurs_2eme_classe", "groupes_1ere_classe",
    "groupes_2eme_classe", "places_disponibles_1ere_classe",
    "places_disponibles_2eme_classe", "passagers_montant_1ere_classe",
    "passagers_montant_2eme_classe", "passagers_descendants_1ere_classe",
    "passagers_descendants_2eme_classe", "code_justification", "depart_datetime",
    "arrivee_datetime", "divergence_horaire", "mode_comptage", "source", "distance_km",
    "tx_occupation_1ere_classe", "tx_occupation_2eme_classe",
]


def effectifs() -> dict:
    """Effectifs et répartition lus du pipeline (aucun chiffre codé en dur).

    Provenance vérifiée sur l'empreinte canonique de ml_dataset ; chaîne réconciliée par
    assert (les valeurs des assert sont des GARDES, pas la source d'affichage).
    """
    import pandas as pd
    import pyarrow.parquet as pq

    assert hashlib.sha256(ML.read_bytes()).hexdigest()[:8] == HASH, "ml_dataset non canonique"

    n_dedup = pq.read_metadata(APC).num_rows            # apc_stacked (après dédoublonnage)
    n_s1 = pq.read_metadata(STAGE_01).num_rows
    n_s10 = pq.read_metadata(STAGE_10).num_rows
    n_ml = pq.read_metadata(ML).num_rows

    # Doublons nets = lignes retirées par keep="first" parmi les membres tracés (keep=False).
    dup = pd.read_parquet(RAW_DUP, columns=RAW_SCHEMA_COLUMNS)
    net = int(dup.duplicated(subset=RAW_SCHEMA_COLUMNS, keep="first").sum())
    n_brut = n_dedup + net

    # Répartition du dernier niveau par année horaire (lue de la colonne).
    col = pq.read_table(ML, columns=["horaire_annee_horaire"]).to_pandas()["horaire_annee_horaire"]
    vc = col.value_counts()
    annees = ["H22", "H23", "H24", "H25"]
    parts = {a: int(vc[a]) for a in annees}

    # Réconciliation stricte de la chaîne (gardes contre une dérive silencieuse des données).
    assert net == 1252, "doublons nets non réconciliés"
    assert n_brut == 2362014, "brut non réconcilié"
    assert n_dedup == 2360762 and n_s1 == n_dedup == n_s10, "invariance de cardinalité rompue"
    assert n_ml == 1141984 and sum(parts.values()) == n_ml, "filtre temporel non réconcilié"

    return dict(brut=n_brut, dedup=n_dedup, s1=n_s1, s10=n_s10, ml=n_ml,
                net=net, delta_enrich=n_s10 - n_s1, annees=annees, parts=parts)


def groupe(n: int) -> str:
    """Séparateur de milliers = espace fine insécable (U+202F), norme française."""
    return f"{n:,}".replace(",", " ")


def dfmt(d: int) -> str:
    if d == 0:
        return "±0"
    return f"+{groupe(d)}" if d > 0 else f"−{groupe(abs(d))}"   # signe moins typographique (U+2212)


def main() -> int:
    n = effectifs()
    BLEU = fs.OKABE_ITO["bleu"]

    # Blocs de la cascade : effectif + libellé « lignes ».
    order = ["brut", "dedup", "s10", "ml"]
    effectif = {"brut": n["brut"], "dedup": n["dedup"], "s10": n["s10"], "ml": n["ml"]}
    tags = {"brut": "Extraction brute", "ml": "Périmètre de modélisation"}

    # Étiquettes sobres sous les connecteurs (opération puis delta, sans numéro ni gras).
    ops = [f"dédoublonnage strict\n{dfmt(-n['net'])}",
           f"enrichissement (dix étapes)\n{dfmt(n['delta_enrich'])}",
           "filtre temporel H22-H25"]

    # Répartition du dernier niveau (une seule ligne grise, sans couleur par année).
    ligne_annees = "   ·   ".join(f"{a} {groupe(n['parts'][a])}" for a in n["annees"])

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.50)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    yc, H = 0.60, 0.30
    W_FULL = 0.200                                       # largeur des blocs 1-3 (invariance)
    ratio = n["ml"] / n["dedup"]                         # ≈ 0,484 : réduction proportionnelle
    widths = {"brut": W_FULL, "dedup": W_FULL, "s10": W_FULL, "ml": W_FULL * ratio}

    # Centres à espacement égal entre les 4 blocs, cascade centrée dans le cadre.
    gap = 0.065
    span = sum(widths[k] for k in order) + 3 * gap
    x_left = (1 - span) / 2
    xs = {}
    x = x_left
    for k in order:
        xs[k] = x + widths[k] / 2
        x += widths[k] + gap

    y_lib = yc - H / 2 - 0.05
    y_annees = 0.135

    def bloc(k):
        x, ww = xs[k], widths[k]
        ax.add_patch(FancyBboxPatch((x - ww / 2, yc - H / 2), ww, H,
                     boxstyle="round,pad=0.004,rounding_size=0.018", linewidth=1.0,
                     edgecolor="#1a1a1a", facecolor=BLEU, zorder=3))
        ax.text(x, yc + 0.020, groupe(effectif[k]), ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=4)
        ax.text(x, yc - 0.052, "lignes", ha="center", va="center", fontsize=7.5,
                color="white", zorder=4)

    # Connecteurs gris + étiquettes de critère (sobres, une ligne, sans gras).
    for i in range(3):
        k0, k1 = order[i], order[i + 1]
        x0 = xs[k0] + widths[k0] / 2
        x1 = xs[k1] - widths[k1] / 2
        ax.add_patch(Rectangle((x0, yc - H * 0.36), x1 - x0, H * 0.72,
                     facecolor="#dcdcdc", edgecolor="none", zorder=1))
        xm = (xs[k0] + xs[k1]) / 2
        ax.text(xm, y_lib, ops[i], ha="center", va="top", fontsize=6.8,
                color="#333333", linespacing=1.5)

    for k in order:
        bloc(k)
        if k in tags:
            ax.text(xs[k], yc + H / 2 + 0.035, tags[k], ha="center", va="bottom",
                    fontsize=8.4, color="#222222")

    # Répartition par année horaire, sous le bloc final (grise, discrète, sans couleur).
    x_annees = (xs["s10"] + xs["ml"]) / 2               # centrée sous le dernier segment du flux
    ax.text(x_annees, y_annees, ligne_annees, ha="center", va="center",
            fontsize=7.2, color="#7a7a7a")

    p = fs.save_fig(fig, "fig_4_entonnoir_apc", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
