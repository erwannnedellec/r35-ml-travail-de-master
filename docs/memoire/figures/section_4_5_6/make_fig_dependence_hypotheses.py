#!/usr/bin/env python3
"""Section 4.5.6 (extension) — BROUILLON f_dependence_hypotheses (item 4 appliqué).

Grille 2×2 de dependence plots (SHAP signé vs valeur), ordre : (1) température,
(2) neige, (3) headway BAS, (4) VMCV BAS. Libellés français du codebook (mêmes que les
figures top-15). Item 4 : panneau VMCV en teinte unie (la fenêtre d'indisponibilité rend
la catégorie vide — cf. note_vmcv_neige.md §3) ; panneau headway fixé au segment BAS par
hypothèse (dit en légende), léger jitter horizontal sur les intervalles discrets.
Source : cache SHAP signé de s01 (R356_CACHE). Échantillon 20 000 points/panneau (graine 42).
Charte figstyle (sans titre embarqué, Okabe-Ito, 300 DPI).
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CACHE = Path(os.environ["R356_CACHE"]) if "R356_CACHE" in os.environ else \
    ROOT / "docs" / "memoire" / "verifs" / "section_4_5_6" / "_cache"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

PEAK = {6, 7, 16, 17}
N_SAMPLE = 20000


def libelles():
    lib = {}
    with open(CODEBOOK) as f:
        for r in csv.DictReader(f):
            lib[r["colonne"]] = r["libelle_fr"]
    return lib


def load():
    info = json.loads((CACHE / "feats_order.json").read_text())
    feats = info["feats"]; idx = {f: i for i, f in enumerate(feats)}
    d = {}
    for seg in ("bas", "haut"):
        d[seg] = {"shap": np.load(CACHE / f"shap_signed_{seg}.npy"),
                  "meta": pd.read_parquet(CACHE / f"meta_{seg}.parquet").reset_index(drop=True),
                  "idx": idx}
    return d


def samp(mask, seed=42):
    ii = np.where(mask)[0]
    if len(ii) > N_SAMPLE:
        ii = np.random.default_rng(seed).choice(ii, N_SAMPLE, replace=False)
    return ii


def scatter_hue(ax, x, y, cats, labels, colors, xlabel, ylabel=True):
    for lab, col in zip(labels, colors):
        m = cats == lab
        ax.scatter(x[m], y[m], s=3, alpha=0.25, color=col, edgecolors="none",
                   label=lab, rasterized=True)
    ax.axhline(0, color="#888888", linewidth=0.5, zorder=0)
    ax.set_xlabel(xlabel, fontsize=7.5)
    if ylabel:
        ax.set_ylabel("SHAP signé (voyageurs)", fontsize=7.5)
    ax.tick_params(labelsize=6.5)
    ax.legend(fontsize=6, markerscale=2, handletextpad=0.2, framealpha=0.85, loc="best")


def main() -> int:
    lib = libelles()
    d = load()
    OI = fs.OKABE_ITO
    fs.apply_style()
    fig, axes = plt.subplots(2, 2, figsize=(fs.LARGE, fs.LARGE * 0.80))

    # (1) TEMPÉRATURE — HAUT, couleur = été / hiver
    seg = "haut"; f = "meteo_temperature_h"
    meta = d[seg]["meta"]; sh = d[seg]["shap"][:, d[seg]["idx"][f]]
    val = meta[f].astype("float64").values; mois = meta["cal_mois"].astype("int64").values
    sais = np.where(np.isin(mois, [6, 7, 8]), "été", np.where(np.isin(mois, [12, 1, 2]), "hiver", "autre"))
    m = ~np.isnan(val) & (sais != "autre"); ii = samp(m)
    scatter_hue(axes[0, 0], val[ii], sh[ii].astype(float), sais[ii], ["été", "hiver"],
                [OI["orange"], OI["bleu"]], f"{lib[f]} (°C) — HAUT")

    # (2) NEIGE — saison ski ∩ ouvrable, couleur = segment, x jitteré
    rng = np.random.default_rng(42)
    ax = axes[0, 1]
    for seg, col, nm in (("bas", fs.COULEUR_BAS, "bas"), ("haut", fs.COULEUR_HAUT, "haut")):
        meta = d[seg]["meta"]; sh = d[seg]["shap"][:, d[seg]["idx"]["meteo_neige_binaire_h"]]
        ski = (meta["event_is_ski_ouvert"] == 1).values
        ouv = (meta["cal_type_jour_3classes"] == "ouvrable").values
        val = meta["meteo_neige_binaire_h"].astype("float64").values
        ii = samp(ski & ouv & ~np.isnan(val))
        x = val[ii] + rng.uniform(-0.12, 0.12, len(ii))
        ax.scatter(x, sh[ii].astype(float), s=3, alpha=0.3, color=col, edgecolors="none",
                   label=nm, rasterized=True)
    ax.axhline(0, color="#888888", linewidth=0.5); ax.set_xticks([0, 1])
    ax.set_xticklabels(["pas de neige", "neige"], fontsize=7)
    ax.set_xlabel(f"{lib['meteo_neige_binaire_h']}\nsaison ski, jours ouvrables", fontsize=7.5)
    ax.tick_params(labelsize=6.5); ax.legend(fontsize=6, markerscale=2, loc="best")

    # (3) HEADWAY — BAS (par hypothèse), ouvrable ; couleur = pointe/hors-pointe/soirée ; jitter
    seg = "bas"; f = "ist_headway_avant_min"
    meta = d[seg]["meta"]; sh = d[seg]["shap"][:, d[seg]["idx"][f]]
    val = meta[f].astype("float64").values; h = meta["cal_heure_depart"].astype("int64").values
    ouv = (meta["cal_type_jour_3classes"] == "ouvrable").values
    reg = np.where(np.isin(h, list(PEAK)), "pointe", np.where(h >= 19, "soirée (≥19 h)", "hors-pointe"))
    ii = samp((~np.isnan(val)) & ouv)
    xj = val[ii] + np.random.default_rng(42).uniform(-0.4, 0.4, len(ii))    # jitter intervalles discrets
    scatter_hue(axes[1, 0], xj, sh[ii].astype(float), reg[ii],
                ["pointe", "hors-pointe", "soirée (≥19 h)"],
                [OI["vermillon"], OI["bleu_ciel"], OI["mauve"]],
                f"{lib[f]} (min) — BAS (par hypothèse), ouvrable")

    # (4) VMCV — BAS, teinte UNIE (fenêtre d'indisponibilité écartée : catégorie vide)
    seg = "bas"; f = "vmcv_min_attente_min"
    meta = d[seg]["meta"]; sh = d[seg]["shap"][:, d[seg]["idx"][f]]
    val = meta[f].astype("float64").values
    ii = samp(~np.isnan(val))
    ax = axes[1, 1]
    ax.scatter(val[ii], sh[ii].astype(float), s=3, alpha=0.25, color=OI["bleu"],
               edgecolors="none", rasterized=True)
    ax.axhline(0, color="#888888", linewidth=0.5, zorder=0)
    ax.set_xlabel(f"{lib[f]} — BAS", fontsize=7.5)
    ax.set_ylabel("SHAP signé (voyageurs)", fontsize=7.5); ax.tick_params(labelsize=6.5)

    fig.subplots_adjust(left=0.09, right=0.985, top=0.99, bottom=0.10, wspace=0.24, hspace=0.34)
    p = fs.save_fig(fig, "f_dependence_hypotheses", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    print("[écrit]", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
