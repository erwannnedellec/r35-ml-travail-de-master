#!/usr/bin/env python3
"""Section 4.5.4 — fig_composition_familles.png.

Composition par famille de l'espace de variables : barres horizontales appariées,
une famille par ligne, deux teintes — espace candidat (gris clair) contre modèle
retenu (bleu maison). Aucun camembert. Effectifs affichés en bout de barre.

Re-dérivation OBLIGATOIRE depuis les listes canoniques sous ba493568 (aucun chiffre
codé en dur, aucune reprise des comptes de l'exploration 416bb90b) :
  - espace candidat (179) : models/11_modeling/xgb_B_prime_final_features.json
  - modèle retenu   (158) : outputs/couche2/features_158f_sans_simba.json
La famille de chaque variable est lue du codebook canonique (colonne `famille`,
outputs/codebook_canonique_ba493568.csv), puis traduite par le libellé français du
tableau des familles de §4.4.4 (miroir de build_codebook_canonique._FAMILLE_BASE).

Tri par effectif RETENU décroissant. La chaîne est vérifiée par assert : somme
candidat = 179, somme retenu = 158, réconciliation set-diff (22 retraits, 1 ajout —
le dénivelé réintroduit) et effondrement SIMBA 12 → 0.

Charte maison figstyle : pas de titre embarqué, aucun identifiant (ADR/hash/«features»),
300 DPI, bbox tight, SOURCE_DATE_EPOCH, largeur 16 cm. Aucune interprétation.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")  # byte-repro, avant matplotlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HASH = "ba493568"
LISTE_CANDIDAT = ROOT / "models" / "11_modeling" / "xgb_B_prime_final_features.json"
LISTE_RETENU = ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"
CODEBOOK = ROOT / "outputs" / f"codebook_canonique_{HASH}.csv"

# Libellés français des familles — tableau des familles de §4.4.4
# (miroir strict de scripts/build_codebook_canonique.py:_FAMILLE_BASE).
LIBELLE_FAMILLE = {
    "base_": "Desserte", "cal_": "Calendrier", "event_": "Événement",
    "histo_": "Historique de charge", "horaire_": "Horaire",
    "id_": "Identifiant", "ist_": "Régularité et correspondances",
    "meteo_": "Météo", "resa_": "Réservation de groupe",
    "simba_": "Structure tarifaire", "spatial_": "Contexte spatial",
    "target_": "Cible", "vmcv_": "Concurrence modale",
}

GRIS_CANDIDAT = "#c9c9c9"   # espace candidat (gris clair)
BLEU_RETENU = fs.COULEUR_BAS  # modèle retenu (bleu maison, #0072B2)


def _liste_features(p: Path) -> list:
    """Lit une liste canonique de variables (schéma {'features': [...]} ou imbriqué)."""
    d = json.loads(p.read_text())
    f = d["features"] if isinstance(d.get("features"), list) else d["features"]["features"]
    return list(f)


def composition() -> pd.DataFrame:
    """Table famille × {candidat, retenu}, re-dérivée et vérifiée par assert."""
    cand = _liste_features(LISTE_CANDIDAT)
    retenu = _liste_features(LISTE_RETENU)
    assert len(cand) == len(set(cand)) == 179, f"liste candidate non canonique : {len(cand)}"
    assert len(retenu) == len(set(retenu)) == 158, f"liste retenue non canonique : {len(retenu)}"

    # Réconciliation set-diff : 22 retraits (12 SIMBA + 10 spatial), 1 ajout (dénivelé).
    retraits = set(cand) - set(retenu)
    ajouts = set(retenu) - set(cand)
    assert len(retraits) == 22, f"retraits attendus 22, obtenus {len(retraits)}"
    assert ajouts == {"spatial_denivele_troncon_m"}, f"ajout inattendu : {sorted(ajouts)}"

    # Famille canonique de chaque variable (codebook ba493568), jamais réinventée.
    cb = pd.read_csv(CODEBOOK)
    fam = dict(zip(cb["colonne"], cb["famille"]))
    manquantes = [f for f in set(cand) | set(retenu) if f not in fam]
    assert not manquantes, f"variables hors codebook : {manquantes}"

    cc, rc = Counter(fam[f] for f in cand), Counter(fam[f] for f in retenu)
    prefixes = set(cc) | set(rc)
    assert all(p in LIBELLE_FAMILLE for p in prefixes), \
        f"famille sans libellé : {[p for p in prefixes if p not in LIBELLE_FAMILLE]}"

    rows = [{"prefixe": p, "famille": LIBELLE_FAMILLE[p],
             "candidat": cc.get(p, 0), "retenu": rc.get(p, 0)} for p in prefixes]
    df = pd.DataFrame(rows)
    df["variation"] = df["retenu"] - df["candidat"]
    # Tri par effectif retenu décroissant (candidat en second rang de départage).
    df = df.sort_values(["retenu", "candidat"], ascending=False).reset_index(drop=True)

    assert df["candidat"].sum() == 179, f"somme candidat = {df['candidat'].sum()} != 179"
    assert df["retenu"].sum() == 158, f"somme retenu = {df['retenu'].sum()} != 158"
    simba = df[df["prefixe"] == "simba_"].iloc[0]
    assert (simba["candidat"], simba["retenu"]) == (12, 0), "effondrement SIMBA 12→0 non retrouvé"
    return df


def ecrire_table(df: pd.DataFrame) -> Path:
    """Table famille × {candidat, retenu} pour la prose (Markdown, effectifs bruts)."""
    def signe(v):
        return "0" if v == 0 else (f"+{v}" if v > 0 else f"−{abs(v)}")
    lignes = ["| Famille | Espace candidat | Modèle retenu | Variation |",
              "|---|---:|---:|---:|"]
    for _, r in df.iterrows():
        lignes.append(f"| {r['famille']} | {r['candidat']} | {r['retenu']} | {signe(r['variation'])} |")
    lignes.append(f"| **Total** | **{df['candidat'].sum()}** | **{df['retenu'].sum()}** "
                  f"| **{signe(df['retenu'].sum() - df['candidat'].sum())}** |")
    p = DOSSIER / "table_composition_familles.md"
    p.write_text("\n".join(lignes) + "\n")
    return p


def main() -> int:
    df = composition()
    p_tab = ecrire_table(df)
    print(df[["famille", "candidat", "retenu", "variation"]].to_string(index=False))
    print("[écrit]", p_tab.relative_to(ROOT))

    n = len(df)
    y = np.arange(n)[::-1]          # index 0 (plus fort effectif retenu) en HAUT
    off, bh = 0.205, 0.38           # décalage vertical du couple + hauteur de barre

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.66)

    ax.barh(y + off, df["candidat"], height=bh, color=GRIS_CANDIDAT,
            edgecolor="#333333", linewidth=0.5, zorder=3)
    ax.barh(y - off, df["retenu"], height=bh, color=BLEU_RETENU,
            edgecolor="#333333", linewidth=0.5, zorder=3)

    xmax = int(df["candidat"].max())
    dx = xmax * 0.012
    for yi, (c, r) in zip(y, zip(df["candidat"], df["retenu"])):
        ax.text(c + dx, yi + off, str(c), va="center", ha="left",
                fontsize=8, color="#555555")
        ax.text(r + dx, yi - off, str(r), va="center", ha="left",
                fontsize=8, fontweight="bold", color=BLEU_RETENU)

    ax.set_yticks(y)
    ax.set_yticklabels(df["famille"], fontsize=9)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xlim(0, xmax + xmax * 0.09)
    ax.set_xlabel("Nombre de variables")
    ax.grid(axis="y", visible=False)

    handles = [Patch(facecolor=GRIS_CANDIDAT, edgecolor="#333333", linewidth=0.5,
                     label=f"Espace candidat ({df['candidat'].sum()})"),
               Patch(facecolor=BLEU_RETENU, edgecolor="#333333", linewidth=0.5,
                     label=f"Modèle retenu ({df['retenu'].sum()})")]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.005),
              ncol=2, fontsize=9, handlelength=1.4)

    p = fs.save_fig(fig, "fig_composition_familles", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
