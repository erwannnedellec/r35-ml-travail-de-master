#!/usr/bin/env python3
"""Figures de la section 4.5.1 — justification du protocole temporel par stationnarité.

Produit (dans ce dossier) :
  - fig_4_ks_matrice_annees.png : matrice KS bilatérale de la cible entre années horaires ;
  - fig_4_kde_cible_annees.png  : densités (KDE) de la cible par année horaire.

Variable analysée : la cible = voyageurs de 2e classe (`target_voyageurs_2eme_classe`),
au grain natif tronçon × course × date.

Données. Le gel canonique `ml_dataset.parquet` (empreinte ba493568, ADR-066/076) ne
couvre que H22-H25. L'analyse KS d'origine (ADR-027) portait sur H16-H25 et déclare
2 051 510 observations « dans stage_09 ». On retrouve cette source amont pré-filtre :
`data/processed/stage_09_simba.parquet`. Son décompte H16-H24 reproduit exactement le
2 051 510 d'ADR-027, et son sous-ensemble H22-H25 est vérifié identique au canonique
avant usage. Son empreinte est épinglée mais N'EST PAS gouvernée par ADR (seul
ba493568 l'est) : caveat signalé dans le rapport et dans ce fichier.

LECTURE SEULE sur les données : lit deux parquet, écrit deux PNG dans ce dossier.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.stats import ks_2samp, gaussian_kde

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

CANONIQUE = "ba493568"
FROZEN_STAGE09 = "954135f9"   # source figée H16-H25 (ADR-066, addendum 2026-07-12)
CIBLE = "target_voyageurs_2eme_classe"
TOTAL = "target_voyageurs_total"      # variable d'ADR-027 (pour le contrôle)
ANNEE = "horaire_annee_horaire"
ML = ROOT / "data/processed/ml_dataset.parquet"
STAGE09 = ROOT / "data/processed/stage_09_simba.parquet"
SEED = 42


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def ordre(annees):
    return sorted(annees, key=lambda a: int(a[1:]))


def main() -> int:
    print("=" * 74)
    print("Figures section 4.5.1 — stationnarité du protocole temporel")
    print("=" * 74)

    # ---- ÉTAPE 1a : vérification d'empreinte du canonique (abort sinon) ----
    h_ml = sha8(ML)
    print(f"[hash] ml_dataset.parquet = {h_ml} (attendu {CANONIQUE})")
    assert h_ml == CANONIQUE, f"ABORT : empreinte {h_ml} != {CANONIQUE}"

    # ---- ÉTAPE 1b : source amont H16-H25 + cross-check H22-H25 vs canonique ----
    h_st = sha8(STAGE09)
    concord = "== figée" if h_st == FROZEN_STAGE09 else f"!= figée {FROZEN_STAGE09}"
    print(f"[hash] stage_09_simba.parquet = {h_st} ({concord} ; source figée ADR-066, "
          f"NON gouvernée comme canonique)")

    dfc = pd.read_parquet(ML, columns=[ANNEE, CIBLE])
    dfs = pd.read_parquet(STAGE09, columns=[ANNEE, CIBLE, TOTAL])

    # cross-check : la cible H22-H25 de stage_09 doit égaler celle du canonique
    ok_cross = True
    for a in ["H22", "H23", "H24", "H25"]:
        cc = dfc.loc[dfc[ANNEE] == a, CIBLE].sort_values().to_numpy()
        ss = dfs.loc[dfs[ANNEE] == a, CIBLE].sort_values().to_numpy()
        same = (len(cc) == len(ss)) and np.array_equal(
            np.nan_to_num(cc, nan=-1.0), np.nan_to_num(ss, nan=-1.0))
        ok_cross = ok_cross and same
        print(f"   cross-check {a}: n_canon={len(cc)} n_stage={len(ss)} identique={same}")
    if ok_cross:
        source, df = "stage_09 (H16-H25)", dfs
        print("[source] cross-check OK -> figures sur H16-H25 (stage_09), caveat empreinte.")
    else:
        source, df = "ml_dataset canonique (H22-H25 seul)", dfc.assign(**{TOTAL: np.nan})
        print("[source] cross-check ÉCHOUÉ -> repli H22-H25 canonique, RESTRICTION signalée.")

    # ---- population exacte : effectifs et NaN par année ----
    annees = ordre(df[ANNEE].unique())
    print("\n[population] grain tronçon × course × date — cible = voyageurs 2e classe")
    print(f"{'année':>6} {'n_lignes':>10} {'n_NaN_cible':>12} {'n_utilisé':>10} "
          f"{'médiane':>8} {'p95':>6} {'max':>6}")
    data = {}
    for a in annees:
        v = df.loc[df[ANNEE] == a, CIBLE].to_numpy()
        vv = v[~np.isnan(v)]
        data[a] = vv
        print(f"{a:>6} {len(v):>10} {int(np.isnan(v).sum()):>12} {len(vv):>10} "
              f"{np.median(vv):>8.1f} {np.percentile(vv,95):>6.0f} {vv.max():>6.0f}")

    # ---- ÉTAPE 2 : matrice KS bilatérale (cible 2e classe) ----
    n = len(annees)
    M = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = ks_2samp(data[annees[i]], data[annees[j]], method="asymp").statistic
            M[i, j] = M[j, i] = d

    print("\n[KS] matrice D (cible 2e classe) — paires clés :")
    def ksval(a, b):
        return M[annees.index(a), annees.index(b)] if a in annees and b in annees else float("nan")
    for a, b in [("H22", "H23"), ("H23", "H24"), ("H22", "H24"),
                 ("H24", "H25"), ("H22", "H25"), ("H23", "H25"),
                 ("H20", "H24"), ("H21", "H24")]:
        print(f"   KS({a},{b}) = {ksval(a,b):.4f}")

    # ---- CONTRÔLE : KS sur target_voyageurs_total (variable d'ADR-027) ----
    if df[TOTAL].notna().any():
        print("\n[CONTRÔLE vs ADR-027 l.48-66] — ADR-027 = KS sur voyageurs TOTAL ;"
              " nos figures = KS sur 2e classe (divergence par construction).")
        tot = {a: df.loc[(df[ANNEE] == a), TOTAL].dropna().to_numpy() for a in annees}
        for a, b, ref027 in [("H22", "H23", 0.0722), ("H23", "H24", 0.1231),
                             ("H22", "H24", 0.0775)]:
            if len(tot[a]) and len(tot[b]):
                d_tot = ks_2samp(tot[a], tot[b], method="asymp").statistic
                print(f"   KS_total({a},{b}) = {d_tot:.4f}  | ADR-027 = {ref027:.4f}"
                      f"  | KS_2e_classe = {ksval(a,b):.4f}")

    # ---- Figure 1 : heatmap KS ----
    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.82)
    cmap = fs.sequential_cmap("bleu")
    im = ax.imshow(M, cmap=cmap, vmin=0.0, vmax=max(0.15, M.max()))
    ax.set_xticks(range(n)); ax.set_xticklabels(annees)
    ax.set_yticks(range(n)); ax.set_yticklabels(annees)
    ax.set_xlabel("Année horaire"); ax.set_ylabel("Année horaire")
    ax.grid(False)
    seuil_txt = 0.5 * max(0.15, M.max())
    for i in range(n):
        for j in range(n):
            if i == j:
                ax.text(j, i, "—", ha="center", va="center", color="#999999", fontsize=8)
            else:
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                        color=("white" if M[i, j] > seuil_txt else "#222222"))
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Statistique de Kolmogorov-Smirnov D (sans unité)")
    p1 = fs.save_fig(fig, "fig_4_ks_matrice_annees", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print(f"\n[écrit] {p1.relative_to(ROOT)}")

    # ---- Figure 2 : KDE de la cible par année horaire ----
    # ÉTAPE 3 (consigne tronquée) : interprétation = densités KDE superposées de la
    # cible par année, compagnon visuel de la matrice KS. Deux groupes de légende,
    # sans mention d'entraînement ni de test : « Périmètre retenu (H22-H25) » en
    # traits pleins couleur, « Années exclues (H16-H21) » en pointillés gris.
    xmax = float(np.percentile(np.concatenate([data[a] for a in annees]), 99))
    grid = np.linspace(0, xmax, 400)
    rng = np.random.default_rng(SEED)
    retenues = [a for a in annees if int(a[1:]) >= 22]
    couleurs = [fs.OKABE_ITO["bleu"], fs.OKABE_ITO["vert"],
                fs.OKABE_ITO["orange"], fs.OKABE_ITO["vermillon"]]

    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.62)
    for a in annees:
        vv = data[a]
        ech = vv if len(vv) <= 40000 else rng.choice(vv, 40000, replace=False)
        dens = gaussian_kde(ech)(grid)
        if a in retenues:
            ax.plot(grid, dens, lw=1.8, color=couleurs[retenues.index(a) % len(couleurs)],
                    zorder=3)
        else:
            ax.plot(grid, dens, lw=0.9, ls="--", color="#9a9a9a", alpha=0.85, zorder=1)
    ax.axvline(63, color="#000000", ls=":", lw=1.0, zorder=2)
    ax.set_xlim(0, xmax)
    ymax = ax.get_ylim()[1]
    ax.annotate("Seuil de surcharge : 63", xy=(64, 0.13 * ymax), fontsize=8,
                color="#555555", ha="left")
    ax.set_xlabel("Charge de 2e classe (voyageurs par tronçon-course)")
    ax.set_ylabel("Densité estimée (sans unité)")
    # Deux légendes groupées (intitulés = périmètres ; aucune mention entraînement/test).
    h_ret = [Line2D([0], [0], color=couleurs[i], lw=1.8) for i in range(len(retenues))]
    leg1 = ax.legend(h_ret, list(retenues), title="Périmètre retenu (H22-H25)",
                     loc="upper right", bbox_to_anchor=(0.995, 0.995),
                     fontsize=8, title_fontsize=8.5, handlelength=1.8, borderaxespad=0.4)
    leg1.get_title().set_fontweight("bold")
    ax.add_artist(leg1)
    h_exc = [Line2D([0], [0], color="#9a9a9a", lw=1.0, ls="--")]
    leg2 = ax.legend(h_exc, ["H16 à H21"], title="Années exclues (H16-H21)",
                     loc="upper right", bbox_to_anchor=(0.995, 0.58),
                     fontsize=8, title_fontsize=8.5, handlelength=1.8, borderaxespad=0.4)
    leg2.get_title().set_fontweight("bold")
    p2 = fs.save_fig(fig, "fig_4_kde_cible_annees", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print(f"[écrit] {p2.relative_to(ROOT)}")

    print("\n[source retenue]", source, f"| stage_09 sha256[:8]={h_st}")
    print(f"[KDE] x tronqué à p99 global = {xmax:.0f} voy. ; sous-échantillon 40k/année (seed {SEED}).")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
