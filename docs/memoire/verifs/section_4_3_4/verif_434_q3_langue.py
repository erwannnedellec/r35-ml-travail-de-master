"""
verif_434_q3_langue.py — Q3 : champ de langue dans ResSys ? part des résa en français.

Source brute : data/external/reservations/export_r35_h{16..25}.xlsx (CAPRE/MOB).
Champ de langue = colonne « Sprache » (COL_RENAME -> 'langue', reservations_utils.py).
Statut confirmé = « 50 Abgeschlossen » (STATUT_ABGESCHLOSSEN, ADR-035 §2.5).
Grain rapporté : le dossier de réservation (une ligne = un dossier CAPRE).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
RESA_DIR = ROOT / "data/external/reservations"
STATUT_CONFIRME = "50 Abgeschlossen"
ANNEES = ["h22", "h23", "h24", "h25"]

frames = []
for f in sorted(RESA_DIR.glob("export_r35_h*.xlsx")):
    d = pd.read_excel(f)
    d["_annee"] = f.stem.split("_")[-1]  # h22...
    frames.append(d)
raw = pd.concat(frames, ignore_index=True)

print("Colonnes brutes :", list(raw.columns))
LANG = "Sprache"
STAT = "Statut de la réservation"
assert LANG in raw.columns, "champ de langue absent"
print(f"\nChamp de langue présent : « {LANG} »  ->  OUI")
print(f"n lignes (dossiers) toutes années = {len(raw)}")

print("\n-- Valeurs du champ langue (toutes années, tous statuts) --")
print(raw[LANG].fillna("(vide)").value_counts(dropna=False).to_string())

print("\n-- Statuts présents --")
print(raw[STAT].fillna("(vide)").value_counts().to_string())

def frac_fr(sub):
    n = len(sub)
    lang = sub[LANG].astype("string").str.strip().str.lower()
    nfr = int((lang == "français").sum())
    nvide = int(sub[LANG].isna().sum())
    return n, nfr, nvide

print("\n" + "="*70)
print("PART DES RÉSERVATIONS EN FRANÇAIS")
print("="*70)
for base_lbl, base in [("TOUTES réservations", raw),
                       (f"CONFIRMÉES ({STATUT_CONFIRME})", raw[raw[STAT] == STATUT_CONFIRME])]:
    print(f"\n[{base_lbl}]")
    print(f"  {'périmètre':12} {'n_dossiers':>11} {'n_français':>11} {'part_fr':>9} {'n_vide':>8}")
    for a in ANNEES:
        s = base[base["_annee"] == a]
        n, nfr, nv = frac_fr(s)
        if n:
            print(f"  {a.upper():12} {n:>11} {nfr:>11} {f'{100*nfr/n:.1f}%':>9} {nv:>8}")
    s = base[base["_annee"].isin(ANNEES)]
    n, nfr, nv = frac_fr(s)
    print(f"  {'H22-H25':12} {n:>11} {nfr:>11} {f'{100*nfr/n:.1f}%':>9} {nv:>8}")
    n, nfr, nv = frac_fr(base)
    print(f"  {'H16-H25 (tt)':12} {n:>11} {nfr:>11} {f'{100*nfr/n:.1f}%':>9} {nv:>8}")

# doublons de dossier ?
if "Numéro de dossier" in raw.columns:
    nd = raw["Numéro de dossier"].nunique()
    print(f"\nNuméros de dossier distincts = {nd} / {len(raw)} lignes "
          f"(doublons = {len(raw)-nd})")
