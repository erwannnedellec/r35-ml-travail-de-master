"""
verif_434_cible.py — Vérifications sur la cible « surcharge » (section 4.3.4).

Source unique : data/processed/ml_dataset.parquet (gel v2, SHA256[:8] = ba493568,
ADR-076) pour Q1/Q2/Q4/Q5 ; data/external/reservations/export_r35_h*.xlsx (source
brute ResSys/CAPRE) pour Q3. Aucune valeur en dur : tout est recalculé.

Définitions canoniques (rappelées) :
  - Surcharge 2e classe = target_voyageurs_2eme_classe > 63 (ADR-060, seuil assises).
  - Grain TRONÇON : une ligne = un tronçon élémentaire d'une course ; segment =
    spatial_segment (bas = plaine, gare ordre <=10 ; haut = crémaillère, ordre >10).
  - Grain COURSE : (base_date, horaire_numero_train) ; label surcharge = au moins un
    tronçon observé > 63 (D2, decision.py) ; segment de course = any_haut =
    la course touche la crémaillère (>=1 tronçon avec gare ordre >10) -> "haut",
    sinon "bas" (règle P2, blocs.load_charge). ATTENTION : le segment de course
    N'EST PAS spatial_segment agrégé ; une course pleine-ligne dont la surcharge
    est en plaine est comptée "haut" (elle atteint la montagne).
  - Pointe : fenêtres opérationnalisées dans le pipeline istdaten
    (build_istdaten_ponctualite.py) : matin 05h-08h, soir 16h-19h (heure de départ) ;
    jour ouvrable = lundi-vendredi (jour_semaine_iso 1..5).
"""
from __future__ import annotations
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
ML = ROOT / "data/processed/ml_dataset.parquet"
RESA_DIR = ROOT / "data/external/reservations"
SEUIL = 63
ORDRE_PLAINE_MAX = 10
POINTE_MATIN = {5, 6, 7, 8}          # 05h-08h inclus (range(5,9))
POINTE_SOIR = {16, 17, 18, 19}       # 16h-19h inclus (range(16,20))
ANNEES = ["H22", "H23", "H24", "H25"]
STATUT_CONFIRME = "50 Abgeschlossen"

def _hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]

def pc(n, d):
    return f"{100*n/d:.1f}%" if d else "n/d"

# ════════════════════════════════════════════════════════════════════════════
print("="*78)
print(f"ml_dataset SHA256[:8] = {_hash(ML)} (attendu ba493568)")
print("="*78)

df = pd.read_parquet(ML, columns=[
    "horaire_annee_horaire", "base_date", "horaire_numero_train", "spatial_segment",
    "target_voyageurs_2eme_classe", "cal_heure_depart", "cal_jour_semaine_iso",
    "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre",
    "resa_has_resa_J_minus_1", "resa_pax_2c_J_minus_1"])
df["charge"] = df["target_voyageurs_2eme_classe"].astype("float64")
df["surch"] = df["charge"] > SEUIL
df["ouvrable"] = df["cal_jour_semaine_iso"].astype("Int64").isin([1, 2, 3, 4, 5])
df["pointe"] = df["cal_heure_depart"].astype("Int64").isin(POINTE_MATIN | POINTE_SOIR)
df["touche_haut"] = ((df["spatial_gare_depart_ordre"] > ORDRE_PLAINE_MAX) |
                     (df["spatial_gare_arrivee_ordre"] > ORDRE_PLAINE_MAX)).fillna(False)
df["resa_has"] = df["resa_has_resa_J_minus_1"].astype("float64").fillna(0) > 0
df["resa_pax_pos"] = df["resa_pax_2c_J_minus_1"].astype("float64").fillna(0) > 0

# ─── Q1 : pointe & ouvrable, par segment (grain tronçon) ────────────────────
print("\n" + "#"*78 + "\n# Q1 — surcharges en pointe / jours ouvrables, par segment (grain tronçon)\n" + "#"*78)
print("Pointe = départ 05-08h ou 16-19h ; ouvrable = lun-ven.")
for seg in ["bas", "haut", "TOTAL"]:
    sub = df[df["surch"]] if seg == "TOTAL" else df[df["surch"] & (df["spatial_segment"] == seg)]
    print(f"\n[{seg}] surcharges H22-H25 = {len(sub)}")
    print(f"  {'annee':7} {'n_surch':>8} {'pointe':>16} {'ouvrable':>16} {'pointe&ouvr':>16}")
    for a in ANNEES + ["H22-H25"]:
        s = sub if a == "H22-H25" else sub[sub["horaire_annee_horaire"] == a]
        n = len(s)
        if n == 0:
            print(f"  {a:7} {0:>8}"); continue
        npo, nou, nbo = int(s["pointe"].sum()), int(s["ouvrable"].sum()), int((s["pointe"] & s["ouvrable"]).sum())
        print(f"  {a:7} {n:>8} {f'{npo} ({pc(npo,n)})':>16} {f'{nou} ({pc(nou,n)})':>16} {f'{nbo} ({pc(nbo,n)})':>16}")

# ─── Q2 : répartition surcharges par segment, DEUX grains ───────────────────
print("\n" + "#"*78 + "\n# Q2 — répartition des surcharges par segment (grain tronçon & grain course)\n" + "#"*78)
print("\n-- GRAIN TRONÇON (segment = spatial_segment) --")
tr = df[df["surch"]].groupby(["horaire_annee_horaire", "spatial_segment"]).size().unstack(fill_value=0)
tr["total"] = tr.sum(axis=1)
tr.loc["H22-H24"] = tr.loc[["H22", "H23", "H24"]].sum()
tr.loc["H22-H25"] = tr.loc[["H22", "H23", "H24", "H25"]].sum()
print(tr.to_string())

# Grain course construit depuis ml_dataset (indépendant de l'intersection rotations)
course = df.groupby(["base_date", "horaire_numero_train", "horaire_annee_horaire"], sort=True).agg(
    charge_max=("charge", "max"),
    any_haut=("touche_haut", "max"),
    resa_has=("resa_has", "max"),
    resa_pax_pos=("resa_pax_pos", "max")).reset_index()
course["label"] = course["charge_max"] > SEUIL
course["segment"] = np.where(course["any_haut"], "haut", "bas")
print(f"\n-- GRAIN COURSE (course = date x numero_train ; segment = any_haut ; label = >=1 tronçon >63) --")
print(f"   courses totales H22-H25 = {len(course)}")
co = course[course["label"]].groupby(["horaire_annee_horaire", "segment"]).size().unstack(fill_value=0)
for c in ["bas", "haut"]:
    if c not in co.columns:
        co[c] = 0
co = co[["bas", "haut"]]
co["total"] = co.sum(axis=1)
co.loc["H22-H24"] = co.loc[["H22", "H23", "H24"]].sum()
co.loc["H22-H25"] = co.loc[["H22", "H23", "H24", "H25"]].sum()
print(co.to_string())
h25 = co.loc["H25"]
print(f"\n   >>> CONTRÔLE H25 course : bas={h25['bas']} (attendu 848) / haut={h25['haut']} (attendu 1224) "
      f"-> {'OK' if (h25['bas'], h25['haut']) == (848, 1224) else 'ECART'}")

# ─── Q4 : coïncidence réservation-surcharge, segment haut, grain course ──────
print("\n" + "#"*78 + "\n# Q4 — courses en surcharge (segment haut) portant une réservation de groupe\n" + "#"*78)
print("Lien : course (grain) surchargée (>=1 tronçon >63) ET segment haut (touche crémaillère),")
print("       portant une résa de groupe = resa_has_resa_J_minus_1 (confirmée, connue à J-1).")
haut_surch = course[course["label"] & (course["segment"] == "haut")]
print(f"\n  {'annee':9} {'n_courses_haut_surch':>20} {'porte_resa (has)':>22} {'porte_resa (pax2c>0)':>22}")
for a in ANNEES + ["H22-H25"]:
    s = haut_surch if a == "H22-H25" else haut_surch[haut_surch["horaire_annee_horaire"] == a]
    n = len(s)
    if n == 0:
        print(f"  {a:9} {0:>20}"); continue
    nh, npx = int(s["resa_has"].sum()), int(s["resa_pax_pos"].sum())
    print(f"  {a:9} {n:>20} {f'{nh} ({pc(nh,n)})':>22} {f'{npx} ({pc(npx,n)})':>22}")

# ─── Q5 : distribution complète de la charge (grain tronçon) ────────────────
print("\n" + "#"*78 + "\n# Q5 — distribution de la charge 2e classe (grain tronçon, H22-H25)\n" + "#"*78)
bins = [-np.inf, 62, 93, 165, np.inf]
labels = ["<63 (0-62)", "63-93", "94-165", ">=166"]
df["tranche"] = pd.cut(df["charge"], bins=bins, labels=labels)
print(f"\n  charge max observée = {int(df['charge'].max())} ; n tronçons = {len(df)}")
print(f"\n  {'tranche':14} {'H22':>10} {'H23':>10} {'H24':>10} {'H25':>10} {'H22-H25':>12} {'part':>8}")
dist = df.groupby(["tranche", "horaire_annee_horaire"], observed=True).size().unstack(fill_value=0)
for lab in labels:
    row = dist.loc[lab] if lab in dist.index else pd.Series(0, index=ANNEES)
    tot = int(row.reindex(ANNEES).fillna(0).sum())
    cells = " ".join(f"{int(row.get(a,0)):>10}" for a in ANNEES)
    print(f"  {lab:14} {cells} {tot:>12} {pc(tot,len(df)):>8}")
tot_all = " ".join(f"{int((df['horaire_annee_horaire']==a).sum()):>10}" for a in ANNEES)
print(f"  {'TOTAL':14} {tot_all} {len(df):>12} {'100.0%':>8}")
# réconciliation avec le seuil de surcharge (>63 strict)
n63 = int((df["charge"] == 63).sum())
n6493 = int(((df["charge"] > 63) & (df["charge"] <= 93)).sum())
print(f"\n  Réconciliation seuil >63 : tronçons à charge==63 (limite assises, NON surcharge) = {n63}")
print(f"    cellule 63-93 = {n63} (==63) + {n6493} (64-93, surchargés) = {n63+n6493}")
print(f"    surcharges >63 total = {n6493} + 3629 (94-165) + 45 (>=166) = {n6493+3629+45}")
# cas extrêmes détaillés
extr = df[df["charge"] >= 166].sort_values("charge", ascending=False)
print(f"\n  Cas extrêmes (charge >=166) : n = {len(extr)} "
      f"(dont ==166 exact : {int((df['charge']==166).sum())} ; strict >166 : {int((df['charge']>166).sum())})")
print(f"    top charges : {sorted(extr['charge'].astype(int).tolist(), reverse=True)[:15]}")
print(f"    par année : {extr.groupby('horaire_annee_horaire').size().to_dict()}")
print(f"    par segment : {extr.groupby('spatial_segment').size().to_dict()}")

print("\n[FIN Q1/Q2/Q4/Q5]")
