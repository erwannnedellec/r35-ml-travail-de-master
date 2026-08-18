#!/usr/bin/env python3
"""Section 4.3.2 — Profil composite le long de la ligne R35 (dualité bas / haut).

Trois bandes empilées partageant l'axe des gares (topologie courante, 17 gares) :
  (a) charge moyenne de 2e classe portée par tronçon (H22-H25, ml_dataset) ;
  (b) population par gare (cellules de Voronoï bornées 500 m, statpop_clean_causal) ;
  (c) emplois par gare (idem, statent_clean_causal).

Échelles indépendantes par bande ; frontière bas/haut à Blonay (trait vertical
traversant les trois bandes). Palette maison (bleu bas / vermillon haut), cohérente
avec fig_shap. LECTURE SEULE ; écrit un PNG. Byte-repro : SOURCE_DATE_EPOCH.
"""
import os, sys, hashlib
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ML = ROOT / "data/processed/ml_dataset.parquet"
STATPOP = ROOT / "data/processed/sources/statpop_clean_causal.parquet"
STATENT = ROOT / "data/processed/sources/statent_clean_causal.parquet"
DIMGARE = ROOT / "data/dimension/dim_gare.parquet"
OUT = ROOT / "docs/memoire/figures/section_4_3_2/fig_profil_ligne.png"
ORDRE_MAX_BAS = 10

assert hashlib.sha256(ML.read_bytes()).hexdigest()[:8] == "ba493568", "hash != ba493568 — STOP"

# ---- topologie courante : 17 gares actives (GIL et CLIE fermées, exclues)
gare = pd.read_parquet(DIMGARE, columns=["abreviation", "bpuic", "ordre", "nom"])
HORS = {"GIL", "CLIE"}
topo = gare[~gare.abreviation.isin(HORS)].sort_values("ordre").reset_index(drop=True)
assert len(topo) == 17, f"topologie courante = 17 gares attendues, obtenu {len(topo)}"
CODES = topo.abreviation.tolist()                          # ordre le long de la ligne
ABBR2ORD = dict(zip(gare.abreviation, gare.ordre.astype(int)))
BPUIC2ABBR = dict(zip(gare.bpuic.astype(int), gare.abreviation))
seg_gare = ["bas" if o <= ORDRE_MAX_BAS else "haut" for o in topo.ordre]
IDX_BLON = CODES.index("BLON")                             # dernière gare de plaine
FRONTIERE = IDX_BLON + 0.5                                 # trait juste au-delà de Blonay

# ---- (a) charge moyenne de 2e classe par tronçon élémentaire (ml_dataset H22-H25)
ml = pd.read_parquet(ML, columns=["id_gare_depart_bpuic", "id_gare_arrivee_bpuic",
                                   "target_voyageurs_2eme_classe"])
ml["t"] = ml.target_voyageurs_2eme_classe.astype("float64")
ml["dep"] = ml.id_gare_depart_bpuic.astype(int).map(BPUIC2ABBR)
ml["arr"] = ml.id_gare_arrivee_bpuic.astype(int).map(BPUIC2ABBR)
ml["tp"] = ml.apply(lambda r: f"{min(r.dep, r.arr, key=lambda a: ABBR2ORD[a])}-"
                              f"{max(r.dep, r.arr, key=lambda a: ABBR2ORD[a])}", axis=1)
charge_moy = ml.groupby("tp").t.mean()
tr_names = [f"{CODES[k]}-{CODES[k+1]}" for k in range(16)]  # 16 tronçons adjacents
charge = [float(charge_moy.get(n, np.nan)) for n in tr_names]
seg_tr = ["bas" if (k + 1) <= IDX_BLON else "haut" for k in range(16)]

# ---- (b)/(c) population et emplois par gare (dernier millésime, Voronoï 500 m)
sp = pd.read_parquet(STATPOP).sort_values("annee_enquete_statpop").groupby("gare_abreviation").tail(1)
se = pd.read_parquet(STATENT).sort_values("annee_enquete_statent").groupby("gare_abreviation").tail(1)
pop = pd.Series(dict(zip(sp.gare_abreviation, sp.population_500m_total)))
emp = pd.Series(dict(zip(se.gare_abreviation, se.emplois_500m_total)))
population = [float(pop.get(c, np.nan)) for c in CODES]
emplois = [float(emp.get(c, np.nan)) for c in CODES]

C = {"bas": fs.COULEUR_BAS, "haut": fs.COULEUR_HAUT}

# ============================================================== figure
fs.apply_style()
fig, (axa, axb, axc) = plt.subplots(3, 1, figsize=(7.6, 7.4), sharex=True)

# (a) tronçons : barres centrées entre deux gares (x = k + 0.5)
xtr = np.arange(16) + 0.5
axa.bar(xtr, charge, width=0.82, color=[C[s] for s in seg_tr], edgecolor="white", linewidth=0.4)
fs.finalize(axa, ylabel="Charge 2e classe (voyageurs)")
fs.lettre_panneau(axa, "a")
ymax_a = np.nanmax(charge)
axa.text(IDX_BLON / 2, ymax_a * 1.02, "segment bas", ha="center", va="bottom",
         fontsize=9, color=C["bas"], fontweight="bold")
axa.text((IDX_BLON + 16) / 2, ymax_a * 1.02, "segment haut", ha="center", va="bottom",
         fontsize=9, color=C["haut"], fontweight="bold")

# (b) population par gare
xg = np.arange(17)
axb.bar(xg, population, width=0.82, color=[C[s] for s in seg_gare], edgecolor="white", linewidth=0.4)
fs.finalize(axb, ylabel="Population (habitants)")
fs.lettre_panneau(axb, "b")
for i in ("VV", "VVVI", "BLON"):
    k = CODES.index(i)
    axb.annotate(f"{int(population[k]):,}".replace(",", " "), (k, population[k]),
                 xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                 fontsize=6.6, color="#444444")

# (c) emplois par gare
axc.bar(xg, emplois, width=0.82, color=[C[s] for s in seg_gare], edgecolor="white", linewidth=0.4)
fs.finalize(axc, xlabel="Gare, de Vevey aux Pléiades", ylabel="Emplois (nombre)")
fs.lettre_panneau(axc, "c")
for i in ("VV", "CHTV", "BLON"):
    k = CODES.index(i)
    axc.annotate(f"{int(emplois[k]):,}".replace(",", " "), (k, emplois[k]),
                 xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                 fontsize=6.6, color="#444444")

# frontière bas / haut à Blonay : trait vertical sobre traversant les trois bandes
for ax in (axa, axb, axc):
    ax.axvline(FRONTIERE, color="#333333", linestyle=(0, (4, 3)), linewidth=1.0, zorder=6, alpha=0.85)
    ax.set_xlim(-0.7, 16.7)
axa.text(FRONTIERE - 0.12, ymax_a * 0.98, "Blonay — frontière bas / haut",
         rotation=90, ha="right", va="top", fontsize=7, color="#555555")

# graduations : codes de gare, Vevey et Les Pléiades en toutes lettres
labels = ["Vevey" if c == "VV" else "Les Pléiades" if c == "PLEI" else c for c in CODES]
axc.set_xticks(xg)
axc.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
for ax in (axa, axb, axc):
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.02)

fs.save(fig, OUT)
plt.close(fig)
print("FIGURE:", OUT)
print(f"(a) charge moy/tronçon : {tr_names[0]}={charge[0]:.1f} ... {tr_names[-1]}={charge[-1]:.1f}")
print(f"(b) pop VV={population[0]:.0f} VVVI={population[1]:.0f} BLON={population[IDX_BLON]:.0f} PLEI={population[-1]:.0f}")
print(f"(c) emplois VV={emplois[0]:.0f} CHTV={emplois[CODES.index('CHTV')]:.0f} BLON={emplois[IDX_BLON]:.0f}")
