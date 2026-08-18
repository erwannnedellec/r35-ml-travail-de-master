#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification 2 — Décompte des renumérotations de la refonte d'horaire de
décembre 2024 (passage H24 -> H25). Sections 4.3.5 et 4.5.1 du mémoire.

LECTURE SEULE. Aucune donnée n'est écrite hors de docs/memoire/verifs/section_4_3_7/.
Aucun réentraînement, aucun modèle chargé.

Commande de rejeu (environnement vierge, depuis la racine du dépôt) :

    python3 docs/memoire/verifs/section_4_3_5/verif_renumerotation_h25.py

Prérequis : pandas, numpy, pyarrow.

Objet : le mémoire donne deux comptes contradictoires pour la même refonte
(52 sur ~103 en §4.3.5 ; 48 sur 104 en §4.5.1). Ce script ne tranche pas : il
énumère les opérationnalisations défendables et donne le compte exact sous
chacune, avec sa source et son filtre.

Trois sources, trois définitions :
  D1  grille théorique     : data/processed/horaires_r35_troncons_jour.parquet
                             (offre planifiée reconstruite des PDF horaires,
                             grain tronçon x jour, colonnes annee_horaire /
                             numero_train)
  D2  circulations réalisées : data/processed/fact_istdaten_r35.parquet
                             (ISTDATEN déjà filtré en amont par
                             build_fact_istdaten_r35.py :
                             BETREIBER_ABK == "MVR-cev" et
                             LINIEN_TEXT in {"R","R35"} ; grain date x train x arrêt)
  D3  jeu de modélisation  : data/processed/ml_dataset.parquet
                             (empreinte ba493568, grain tronçon observé)

L'année horaire d'ISTDATEN (qui ne porte qu'une date) est reconstruite par les
bornes debut_annee_horaire / fin_annee_horaire de la grille théorique.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
OFFRE = ROOT / "data" / "processed" / "horaires_r35_troncons_jour.parquet"
IST = ROOT / "data" / "processed" / "fact_istdaten_r35.parquet"
OUT = ROOT / "docs" / "memoire" / "verifs" / "section_4_3_7"
# Les sorties sont deposees en section_4_3_7 : elles alimentent la synthese
# gen_synthese_verifs_4_3.py, qui les lit dans son propre repertoire, et les
# tableaux 7 et 8 du memoire les citent a la section 4.3.7.
OUT.mkdir(parents=True, exist_ok=True)

HASH_ATTENDU = "ba493568"
GILAMONT_BPUIC = 8501260          # exclu du train H22 par le Split C
TRANSITIONS = [("H22", "H23"), ("H23", "H24"), ("H24", "H25")]

CMD = "python3 docs/memoire/verifs/section_4_3_5/verif_renumerotation_h25.py"

LOG: list[str] = []


def emit(s: str = "") -> None:
    print(s)
    LOG.append(s)


def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


# --------------------------------------------------------------------------- #
# 0. Contrôle d'empreinte
# --------------------------------------------------------------------------- #
emit("=" * 78)
emit("VÉRIFICATION 2 — Renumérotation de décembre 2024 (H24 -> H25)")
emit("=" * 78)
h = sha8(ML)
emit(f"ml_dataset.parquet SHA256[:8] = {h} (attendu {HASH_ATTENDU})")
if h != HASH_ATTENDU:
    emit("STOP — empreinte non conforme : le dataset n'est pas le gel canonique ba493568.")
    sys.exit(1)
emit("Empreinte conforme — poursuite des calculs.")
emit("")

DATE_EXEC = _dt.date.today().isoformat()
VERSIONS = f"python {sys.version.split()[0]} | pandas {pd.__version__} | numpy {np.__version__}"

# --------------------------------------------------------------------------- #
# Chargement des trois sources (lecture seule)
# --------------------------------------------------------------------------- #
offre = pd.read_parquet(OFFRE, columns=["annee_horaire", "numero_train", "date",
                                        "debut_annee_horaire", "fin_annee_horaire"])
mld = pd.read_parquet(ML, columns=["horaire_annee_horaire", "horaire_numero_train", "base_date"])
ist = pd.read_parquet(IST, columns=["date", "numero_train", "is_annule", "is_supplementaire"])
ist["date"] = pd.to_datetime(ist["date"])

bornes = (offre.groupby("annee_horaire")
          .agg(debut=("debut_annee_horaire", "min"), fin=("fin_annee_horaire", "max"))
          .reset_index())
ist["annee_horaire"] = pd.NA
for _, r in bornes.iterrows():
    ist.loc[(ist["date"] >= r.debut) & (ist["date"] <= r.fin), "annee_horaire"] = r.annee_horaire

emit("Sources chargées :")
emit(f"  D1 grille théorique  : {len(offre):,} lignes tronçon x jour, "
     f"années {sorted(offre['annee_horaire'].unique())}")
emit(f"  D2 ISTDATEN MVR-cev  : {len(ist):,} lignes date x train x arrêt, "
     f"dates {ist['date'].min().date()} -> {ist['date'].max().date()}")
emit(f"  D3 ml_dataset        : {len(mld):,} tronçons observés, "
     f"années {sorted(mld['horaire_annee_horaire'].unique())}")
emit("")

# --------------------------------------------------------------------------- #
# Couverture temporelle d'ISTDATEN — limite majeure à documenter
# --------------------------------------------------------------------------- #
emit("-" * 78)
emit("Couverture temporelle d'ISTDATEN par année horaire (limite de D2)")
emit("-" * 78)
cov_rows = []
for _, r in bornes.iterrows():
    if r.annee_horaire not in set(ist["annee_horaire"].dropna()):
        continue
    s = ist[ist["annee_horaire"] == r.annee_horaire]
    etendue = (r.fin - r.debut).days + 1
    n_j = s["date"].nunique()
    cov_rows.append({
        "annee_horaire": r.annee_horaire,
        "debut_annee_horaire": r.debut.date(), "fin_annee_horaire": r.fin.date(),
        "jours_etendue_theorique": etendue,
        "jours_presents_istdaten": n_j,
        "couverture_pct": 100 * n_j / etendue,
        "date_min_istdaten": s["date"].min().date(), "date_max_istdaten": s["date"].max().date(),
        "n_lignes": len(s), "n_numeros_distincts": s["numero_train"].nunique(),
    })
cov = pd.DataFrame(cov_rows)
cov.to_csv(OUT / "verif_renumerotation_couverture_istdaten.csv", index=False, encoding="utf-8")
emit(cov.to_string(index=False))
emit("")
h25cov = cov[cov["annee_horaire"] == "H25"]
if len(h25cov):
    r = h25cov.iloc[0]
    emit(f"AVERTISSEMENT — ISTDATEN ne couvre que {r.jours_presents_istdaten} jours de H25 "
         f"({r.couverture_pct:.1f} % de l'année horaire), du {r.date_min_istdaten} au "
         f"{r.date_max_istdaten}. La définition D2 sur H25 porte donc sur un fragment "
         f"d'année et n'est PAS comparable telle quelle à D1 et D3. Aucune extrapolation "
         f"n'est faite ; une variante à fenêtre appariée est calculée plus bas.")
emit("")


# --------------------------------------------------------------------------- #
# Fonction de comparaison d'un couple d'années
# --------------------------------------------------------------------------- #
def compare(nums_a: set, nums_b: set, obs_b: pd.Series, an_a: str, an_b: str,
            definition: str, source: str, filtre: str) -> dict:
    """nums_a/nums_b : numéros distincts. obs_b : série des numéros de chaque
    observation de l'année b (pour la part d'observations sans antécédent)."""
    sans_ant = nums_b - nums_a
    disparus = nums_a - nums_b
    maintenus = nums_a & nums_b
    n_obs = len(obs_b)
    obs_sans_ant = int(obs_b.isin(sans_ant).sum()) if n_obs else 0
    return {
        "definition": definition, "source": source, "filtre": filtre,
        "transition": f"{an_a} -> {an_b}",
        "n_numeros_annee_A": len(nums_a),
        "n_numeros_annee_B": len(nums_b),
        "n_maintenus": len(maintenus),
        "n_sans_antecedent_B": len(sans_ant),
        "pct_sans_antecedent_B": 100 * len(sans_ant) / len(nums_b) if nums_b else np.nan,
        "n_disparus_A": len(disparus),
        "pct_disparus_A": 100 * len(disparus) / len(nums_a) if nums_a else np.nan,
        "n_obs_annee_B": n_obs,
        "n_obs_B_sans_antecedent": obs_sans_ant,
        "pct_obs_B_sans_antecedent": 100 * obs_sans_ant / n_obs if n_obs else np.nan,
    }


def nums_and_obs(df: pd.DataFrame, col_annee: str, col_num: str, annee: str):
    s = df[df[col_annee] == annee]
    return set(s[col_num].dropna().astype("int64")), s[col_num].dropna().astype("int64")


# --------------------------------------------------------------------------- #
# D1, D2, D3 sur les trois transitions
# --------------------------------------------------------------------------- #
emit("-" * 78)
emit("Comptes par définition et par transition")
emit("-" * 78)

res = []

# --- D1 : grille théorique ------------------------------------------------- #
for a, b in TRANSITIONS:
    na, _ = nums_and_obs(offre, "annee_horaire", "numero_train", a)
    nb, ob = nums_and_obs(offre, "annee_horaire", "numero_train", b)
    res.append(compare(na, nb, ob, a, b, "D1 grille théorique",
                       "horaires_r35_troncons_jour.parquet",
                       "offre planifiée R35, aucun filtre supplémentaire ; "
                       "observations = tronçons x jours planifiés"))

# --- D2 : circulations réalisées (3 variantes de filtre) ------------------- #
VARIANTES_IST = {
    "toutes lignes ISTDATEN (annulées et supplémentaires incluses)":
        pd.Series(True, index=ist.index),
    "hors circulations annulées (is_annule == False)":
        ~ist["is_annule"].astype(bool),
    "hors annulées et hors supplémentaires":
        (~ist["is_annule"].astype(bool)) & (~ist["is_supplementaire"].astype(bool)),
}
for lib, m in VARIANTES_IST.items():
    sub = ist[m]
    for a, b in TRANSITIONS:
        na, _ = nums_and_obs(sub, "annee_horaire", "numero_train", a)
        nb, ob = nums_and_obs(sub, "annee_horaire", "numero_train", b)
        res.append(compare(na, nb, ob, a, b, "D2 circulations réalisées",
                           "fact_istdaten_r35.parquet (BETREIBER_ABK == MVR-cev, "
                           "LINIEN_TEXT in {R, R35})",
                           lib + " ; observations = lignes date x train x arrêt"))

# --- D3 : jeu de modélisation ---------------------------------------------- #
for a, b in TRANSITIONS:
    na, _ = nums_and_obs(mld, "horaire_annee_horaire", "horaire_numero_train", a)
    nb, ob = nums_and_obs(mld, "horaire_annee_horaire", "horaire_numero_train", b)
    res.append(compare(na, nb, ob, a, b, "D3 jeu de modélisation",
                       "ml_dataset.parquet (ba493568)",
                       "tronçons effectivement observés (comptage APC présent) ; "
                       "observations = tronçons observés"))

# --- D2' : fenêtre appariée (mêmes jours calendaires de début d'année horaire) --- #
# H25 n'est couvert par ISTDATEN que sur ses N premiers jours. Pour rendre la
# comparaison D2 défendable, on restreint CHAQUE année horaire à sa fenêtre
# d'ouverture de même longueur.
if len(h25cov):
    n_jours_h25 = int(h25cov.iloc[0]["jours_presents_istdaten"])
    ist_app = ist.copy()
    keep = pd.Series(False, index=ist_app.index)
    for _, r in bornes.iterrows():
        fin_fenetre = r.debut + pd.Timedelta(days=n_jours_h25 - 1)
        keep |= (ist_app["date"] >= r.debut) & (ist_app["date"] <= fin_fenetre)
    ist_app = ist_app[keep & (~ist_app["is_annule"].astype(bool))]
    for a, b in TRANSITIONS:
        na, _ = nums_and_obs(ist_app, "annee_horaire", "numero_train", a)
        nb, ob = nums_and_obs(ist_app, "annee_horaire", "numero_train", b)
        res.append(compare(na, nb, ob, a, b, "D2' circulations réalisées, fenêtre appariée",
                           "fact_istdaten_r35.parquet (BETREIBER_ABK == MVR-cev)",
                           f"hors annulées ; {n_jours_h25} premiers jours de chaque année "
                           f"horaire (longueur imposée par la couverture H25)"))

    # Même restriction appliquée à D1 et D3, pour comparer à périmètre égal
    for src_nom, dfx, ca, cn, cd, lbl in [
        ("D1' grille théorique, fenêtre appariée", offre, "annee_horaire", "numero_train", "date",
         "horaires_r35_troncons_jour.parquet"),
        ("D3' jeu de modélisation, fenêtre appariée", mld, "horaire_annee_horaire",
         "horaire_numero_train", "base_date", "ml_dataset.parquet (ba493568)"),
    ]:
        d = dfx.copy()
        d[cd] = pd.to_datetime(d[cd])
        keep = pd.Series(False, index=d.index)
        for _, r in bornes.iterrows():
            fin_fenetre = r.debut + pd.Timedelta(days=n_jours_h25 - 1)
            keep |= (d[cd] >= r.debut) & (d[cd] <= fin_fenetre)
        d = d[keep]
        for a, b in TRANSITIONS:
            na, _ = nums_and_obs(d, ca, cn, a)
            nb, ob = nums_and_obs(d, ca, cn, b)
            res.append(compare(na, nb, ob, a, b, src_nom, lbl,
                               f"{n_jours_h25} premiers jours de chaque année horaire"))

recap = pd.DataFrame(res)
recap.to_csv(OUT / "verif_renumerotation_h25.csv", index=False, encoding="utf-8")

for d in recap["definition"].unique():
    emit(f"\n### {d}")
    sub = recap[recap["definition"] == d]
    for filt in sub["filtre"].unique():
        s2 = sub[sub["filtre"] == filt]
        emit(f"  filtre : {filt}")
        emit("  " + s2[["transition", "n_numeros_annee_A", "n_numeros_annee_B", "n_maintenus",
                        "n_sans_antecedent_B", "pct_sans_antecedent_B", "n_disparus_A",
                        "pct_disparus_A", "n_obs_annee_B", "n_obs_B_sans_antecedent",
                        "pct_obs_B_sans_antecedent"]].to_string(index=False).replace("\n", "\n  "))

# --------------------------------------------------------------------------- #
# Contrôle : les deux changements d'horaire précédents
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Contrôle — « les deux changements précédents n'avaient modifié aucun numéro »")
emit("-" * 78)
ctrl = recap[recap["transition"].isin(["H22 -> H23", "H23 -> H24"])][
    ["definition", "filtre", "transition", "n_numeros_annee_A", "n_numeros_annee_B",
     "n_sans_antecedent_B", "n_disparus_A", "pct_obs_B_sans_antecedent"]]
ctrl.to_csv(OUT / "verif_renumerotation_transitions_anterieures.csv", index=False, encoding="utf-8")
emit(ctrl.to_string(index=False))

aucun = ctrl[(ctrl["n_sans_antecedent_B"] == 0) & (ctrl["n_disparus_A"] == 0)]
emit(f"\nLignes où l'affirmation « aucun numéro modifié » tient exactement : "
     f"{len(aucun)} sur {len(ctrl)}.")

# --------------------------------------------------------------------------- #
# Contrôle complémentaire : cascade de repli de la baseline naïve (§4.5.2)
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Contrôle complémentaire — cascade de repli de la baseline naïve (§4.5.2)")
emit("-" * 78)
emit("Reproduction de la règle archivée (comparatif_algos.py) : clé complète")
emit("(tronçon dép x arr bpuic, numéro de course, type de jour cal_is_weekend),")
emit("train = H22 (Gilamont 8501260 exclu) + H23 + H24, test = H25.")

bl = pd.read_parquet(ML, columns=["horaire_annee_horaire", "id_gare_depart_bpuic",
                                  "id_gare_arrivee_bpuic", "horaire_numero_train",
                                  "cal_is_weekend"])
bl["dep"] = bl["id_gare_depart_bpuic"].astype("int64")
bl["arr"] = bl["id_gare_arrivee_bpuic"].astype("int64")
bl["cse"] = bl["horaire_numero_train"].astype("int64")
bl["tjr"] = bl["cal_is_weekend"].astype("int64")

h22 = bl[bl["horaire_annee_horaire"] == "H22"]
h22_sc = h22[(h22["dep"] != GILAMONT_BPUIC) & (h22["arr"] != GILAMONT_BPUIC)]
h23_24 = bl[bl["horaire_annee_horaire"].isin(["H23", "H24"])]
h25 = bl[bl["horaire_annee_horaire"] == "H25"]

cascade_rows = []
for lbl, train in [("Split C — H22 hors Gilamont + H23 + H24", pd.concat([h22_sc, h23_24])),
                   ("variante — H22 intégral + H23 + H24", pd.concat([h22, h23_24]))]:
    L1 = set(map(tuple, train[["dep", "arr", "cse", "tjr"]].drop_duplicates().values))
    L2 = set(map(tuple, train[["dep", "arr", "cse"]].drop_duplicates().values))
    L3 = set(map(tuple, train[["dep", "arr", "tjr"]].drop_duplicates().values))
    L4 = set(map(tuple, train[["dep", "arr"]].drop_duplicates().values))

    k1 = list(map(tuple, h25[["dep", "arr", "cse", "tjr"]].values))
    k2 = list(map(tuple, h25[["dep", "arr", "cse"]].values))
    k3 = list(map(tuple, h25[["dep", "arr", "tjr"]].values))
    k4 = list(map(tuple, h25[["dep", "arr"]].values))

    level = np.zeros(len(h25), dtype=int)
    for i in range(len(h25)):
        if k1[i] in L1:   level[i] = 1
        elif k2[i] in L2: level[i] = 2
        elif k3[i] in L3: level[i] = 3
        elif k4[i] in L4: level[i] = 4
        else:             level[i] = 5

    n = len(h25)
    libelle = {1: "(tronçon, course, type_jour) — clé complète",
               2: "(tronçon, course)", 3: "(tronçon, type_jour)",
               4: "(tronçon)", 5: "moyenne globale du train"}
    emit(f"\n  [{lbl}]  train = {len(train):,} lignes | test H25 = {n:,} lignes")
    for l in range(1, 6):
        c = int((level == l).sum())
        emit(f"    niveau {l} {libelle[l]:<42} : {c:>7,}  ({100*c/n:5.2f} %)")
        cascade_rows.append({
            "perimetre_train": lbl, "niveau": l, "cle": libelle[l],
            "n_lignes_H25": c, "pct_lignes_H25": 100 * c / n, "n_total_H25": n,
        })

casc = pd.DataFrame(cascade_rows)
casc.to_csv(OUT / "verif_renumerotation_cascade_baseline.csv", index=False, encoding="utf-8")

emit("\n  Valeurs à confronter au manuscrit §4.5.1 / §4.5.2 : clé complète 53,7 % ; "
     "repli le moins conditionné (niveau 3) 42,4 %.")

# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #
emit("")
emit("=" * 78)
emit(f"Exécuté le {DATE_EXEC} | {VERSIONS}")
emit(f"Commande : {CMD}")
emit("Sorties écrites dans docs/memoire/verifs/section_4_3_7/ :")
for f in ["verif_renumerotation_h25.csv",
          "verif_renumerotation_couverture_istdaten.csv",
          "verif_renumerotation_transitions_anterieures.csv",
          "verif_renumerotation_cascade_baseline.csv"]:
    emit(f"  - {f}")
emit("=" * 78)

(OUT / "verif_renumerotation_h25_journal.txt").write_text("\n".join(LOG), encoding="utf-8")
