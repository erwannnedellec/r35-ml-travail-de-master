#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification 1 — Définition de la surcharge : deuxième classe seule (D2) contre
total des deux classes (DT). Section 4.1.5 / 4.3 du mémoire.

LECTURE SEULE. Aucune donnée n'est écrite hors de docs/memoire/verifs/section_4_3_7/.
Aucun réentraînement, aucun modèle chargé, aucune modification du pipeline.

Commande de rejeu (environnement vierge, depuis la racine du dépôt) :

    python3 docs/memoire/verifs/section_4_3_4/verif_definitions_surcharge.py

Prérequis : pandas, numpy, pyarrow. Dataset canonique
data/processed/ml_dataset.parquet d'empreinte SHA256[:8] == ba493568 (gel v2,
ADR-076). Contrôle dur en préambule, STOP sinon.

Colonnes retenues (relevées dans le schéma, non devinées) :
  - charge 1re classe   : target_voyageurs_1ere_classe   (Int16)
  - charge 2e classe    : target_voyageurs_2eme_classe   (Int16)
  - charge totale       : target_voyageurs_total         (float64)
  - segment bas/haut    : spatial_segment                (string)
  - année horaire       : horaire_annee_horaire          (string)
  - numéro de train     : horaire_numero_train           (int64)
  - date d'exploitation : base_date                      (timestamp[ns])

Définitions comparées :
  D2 : target_voyageurs_2eme_classe > 63   (63 sièges fixes de 2e classe, rame simple)
  DT : target_voyageurs_total       > 75   (63 sièges 2e classe + 12 places 1re classe)

Grain course (convention §4.6, reprise de src/couche2/decision.py:105) :
  clé (base_date, horaire_numero_train, horaire_annee_horaire) ; une course est en
  surcharge dès qu'AU MOINS UN de ses tronçons observés dépasse le seuil (max > seuil).

Segment d'une course (convention canonique, reprise de src/couche2/blocs.py:189) :
  « haut » si au moins un tronçon de la course est haut, « bas » sinon.

Seuls les tronçons effectivement mesurés sont présents dans le jeu : aucune
imputation n'est faite, aucun tronçon manquant n'est reconstruit.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Chemins & constantes
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[4]
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
OUT = ROOT / "docs" / "memoire" / "verifs" / "section_4_3_7"
# Les sorties sont deposees en section_4_3_7 : elles alimentent la synthese
# gen_synthese_verifs_4_3.py, qui les lit dans son propre repertoire, et les
# tableaux 7 et 8 du memoire les citent a la section 4.3.7.
OUT.mkdir(parents=True, exist_ok=True)

HASH_ATTENDU = "ba493568"
SEUIL_D2 = 63          # sièges fixes de 2e classe d'une rame simple
SEUIL_DT = 75          # 63 (2e classe) + 12 (1re classe)
PLACES_1C = 12         # places de 1re classe d'une rame simple

COL_1C = "target_voyageurs_1ere_classe"
COL_2C = "target_voyageurs_2eme_classe"
COL_TOT = "target_voyageurs_total"
COL_SEG = "spatial_segment"
COL_ANNEE = "horaire_annee_horaire"
COL_NUM = "horaire_numero_train"
COL_DATE = "base_date"

CMD = "python3 docs/memoire/verifs/section_4_3_4/verif_definitions_surcharge.py"

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


# --- formatage manuscrit : virgule décimale, espace insécable (U+00A0) ------- #
NBSP = " "


def fmt_n(n) -> str:
    """Entier avec espace insécable comme séparateur de milliers."""
    return f"{int(n):,}".replace(",", NBSP)


def fmt_pct(x, dec: int = 1) -> str:
    """Pourcentage, virgule décimale, `dec` décimale(s)."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n. d."
    return f"{x:.{dec}f}".replace(".", ",")


def fmt_f(x, dec: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n. d."
    return f"{x:,.{dec}f}".replace(",", "\x00").replace(".", ",").replace("\x00", NBSP)


# --------------------------------------------------------------------------- #
# 0. Contrôle d'empreinte (STOP si non conforme)
# --------------------------------------------------------------------------- #
emit("=" * 78)
emit("VÉRIFICATION 1 — D2 (2e classe > 63) contre DT (total > 75)")
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
# Chargement (lecture seule)
# --------------------------------------------------------------------------- #
df = pd.read_parquet(ML, columns=[COL_DATE, COL_ANNEE, COL_NUM, COL_SEG, COL_1C, COL_2C, COL_TOT])
df[COL_1C] = df[COL_1C].astype("int64")
df[COL_2C] = df[COL_2C].astype("int64")
df[COL_TOT] = df[COL_TOT].astype("float64")
df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.normalize()

emit(f"Lignes chargées (tronçons observés, H22-H25) : {len(df):,}")
emit(f"Répartition par année horaire : "
     f"{df[COL_ANNEE].value_counts().sort_index().to_dict()}")
emit(f"Répartition par segment : {df[COL_SEG].value_counts().to_dict()}")
emit("")

# Indicateurs de surcharge au grain tronçon
df["D2"] = df[COL_2C] > SEUIL_D2
df["DT"] = df[COL_TOT] > SEUIL_DT

POPULATIONS = {
    "H22-H25 (régime actuel)": df[COL_ANNEE].isin(["H22", "H23", "H24", "H25"]),
    "H25 seule": df[COL_ANNEE].eq("H25"),
}


# --------------------------------------------------------------------------- #
# Outils : contingence, accord
# --------------------------------------------------------------------------- #
def contingence(d2: pd.Series, dt: pd.Series) -> dict:
    """Table 2x2 D2 x DT + taux de discordance, kappa de Cohen, Jaccard."""
    d2 = d2.astype(bool).values
    dt = dt.astype(bool).values
    n = len(d2)
    n11 = int((d2 & dt).sum())        # concordance positive
    n10 = int((d2 & ~dt).sum())       # D2 seule
    n01 = int((~d2 & dt).sum())       # DT seule
    n00 = int((~d2 & ~dt).sum())      # concordance négative
    union = n11 + n10 + n01

    # kappa de Cohen
    po = (n11 + n00) / n if n else np.nan
    p_d2, p_dt = (n11 + n10) / n, (n11 + n01) / n
    pe = p_d2 * p_dt + (1 - p_d2) * (1 - p_dt)
    kappa = (po - pe) / (1 - pe) if n and (1 - pe) > 0 else np.nan

    jaccard = n11 / union if union else np.nan
    tot_d2, tot_dt = n11 + n10, n11 + n01
    ecart_rel = (tot_dt - tot_d2) / tot_d2 * 100 if tot_d2 else np.nan

    return {
        "n_total": n,
        "concordance_negative_n": n00, "concordance_negative_pct": 100 * n00 / n if n else np.nan,
        "D2_seule_n": n10, "D2_seule_pct": 100 * n10 / n if n else np.nan,
        "DT_seule_n": n01, "DT_seule_pct": 100 * n01 / n if n else np.nan,
        "concordance_positive_n": n11, "concordance_positive_pct": 100 * n11 / n if n else np.nan,
        "union_n": union,
        "discordants_n": n10 + n01,
        "taux_discordance_sur_union_pct": 100 * (n10 + n01) / union if union else np.nan,
        "total_D2_n": tot_d2, "total_D2_pct": 100 * tot_d2 / n if n else np.nan,
        "total_DT_n": tot_dt, "total_DT_pct": 100 * tot_dt / n if n else np.nan,
        "ecart_relatif_DT_vs_D2_pct": ecart_rel,
        "kappa_cohen": kappa,
        "jaccard": jaccard,
    }


def to_course(sub: pd.DataFrame) -> pd.DataFrame:
    """Grain course (§4.6) : clé (date, numéro, année) ; surcharge = au moins un
    tronçon observé au-dessus du seuil. Segment canonique : haut si au moins un
    tronçon haut (src/couche2/blocs.py:189)."""
    g = sub.groupby([COL_DATE, COL_NUM, COL_ANNEE], sort=True)
    c = g.agg(
        charge_2c_max=(COL_2C, "max"),
        charge_tot_max=(COL_TOT, "max"),
        charge_1c_max=(COL_1C, "max"),
        n_troncons=(COL_2C, "size"),
        any_haut=(COL_SEG, lambda s: (s == "haut").any()),
        all_haut=(COL_SEG, lambda s: (s == "haut").all()),
    ).reset_index()
    c["D2"] = c["charge_2c_max"] > SEUIL_D2
    c["DT"] = c["charge_tot_max"] > SEUIL_DT
    c["segment"] = np.where(c["any_haut"], "haut", "bas")
    c["mixte"] = c["any_haut"] & ~c["all_haut"]
    return c


# --------------------------------------------------------------------------- #
# Q1-Q3 : contingence, effectifs, accord — par population et par grain
# --------------------------------------------------------------------------- #
emit("-" * 78)
emit("Q1-Q3 — Table de contingence D2 x DT, effectifs, accord")
emit("-" * 78)

rows = []
courses_cache: dict[str, pd.DataFrame] = {}

for pop_nom, mask in POPULATIONS.items():
    sub = df[mask]
    # grain tronçon
    r = contingence(sub["D2"], sub["DT"])
    r.update({"population": pop_nom, "grain": "tronçon"})
    rows.append(r)
    # grain course
    cs = to_course(sub)
    courses_cache[pop_nom] = cs
    r = contingence(cs["D2"], cs["DT"])
    r.update({"population": pop_nom, "grain": "course"})
    rows.append(r)

cont = pd.DataFrame(rows)
cols_order = ["population", "grain", "n_total",
              "concordance_negative_n", "concordance_negative_pct",
              "D2_seule_n", "D2_seule_pct",
              "DT_seule_n", "DT_seule_pct",
              "concordance_positive_n", "concordance_positive_pct",
              "union_n", "discordants_n", "taux_discordance_sur_union_pct",
              "total_D2_n", "total_D2_pct", "total_DT_n", "total_DT_pct",
              "ecart_relatif_DT_vs_D2_pct", "kappa_cohen", "jaccard"]
cont = cont[cols_order]
cont.to_csv(OUT / "verif_definitions_surcharge.csv", index=False, encoding="utf-8")

for _, r in cont.iterrows():
    emit(f"\n[{r.population} | grain {r.grain}]  n = {r.n_total:,}")
    emit(f"  ni D2 ni DT      : {r.concordance_negative_n:>8,}  ({r.concordance_negative_pct:6.2f} %)")
    emit(f"  D2 seule         : {r.D2_seule_n:>8,}  ({r.D2_seule_pct:6.2f} %)")
    emit(f"  DT seule         : {r.DT_seule_n:>8,}  ({r.DT_seule_pct:6.2f} %)")
    emit(f"  D2 et DT         : {r.concordance_positive_n:>8,}  ({r.concordance_positive_pct:6.2f} %)")
    emit(f"  union            : {r.union_n:>8,}   discordants : {r.discordants_n:,} "
         f"({r.taux_discordance_sur_union_pct:.2f} % de l'union)")
    emit(f"  total D2 = {r.total_D2_n:,} | total DT = {r.total_DT_n:,} | "
         f"écart relatif DT/D2 = {r.ecart_relatif_DT_vs_D2_pct:+.2f} %")
    emit(f"  kappa de Cohen = {r.kappa_cohen:.4f} | Jaccard = {r.jaccard:.4f}")

# --------------------------------------------------------------------------- #
# Q4 : affirmation A — la 1re classe est-elle jamais le facteur limitant ?
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Q4 — Affirmation A : la 1re classe (12 places) comme facteur limitant")
emit("-" * 78)

dist_rows, lim_rows = [], []
for pop_nom, mask in POPULATIONS.items():
    sub = df[mask]
    for seg_nom, seg_mask in [("global", pd.Series(True, index=sub.index)),
                              ("bas", sub[COL_SEG].eq("bas")),
                              ("haut", sub[COL_SEG].eq("haut"))]:
        s = sub[seg_mask]
        v = s[COL_1C].values
        n = len(v)
        depasse = int((v > PLACES_1C).sum())
        limitant = int(((v > PLACES_1C) & (s[COL_2C].values <= SEUIL_D2)).sum())
        dist_rows.append({
            "population": pop_nom, "segment": seg_nom, "n_troncons": n,
            "min": int(v.min()) if n else np.nan,
            "q1": float(np.percentile(v, 25)) if n else np.nan,
            "mediane": float(np.percentile(v, 50)) if n else np.nan,
            "q3": float(np.percentile(v, 75)) if n else np.nan,
            "p90": float(np.percentile(v, 90)) if n else np.nan,
            "p95": float(np.percentile(v, 95)) if n else np.nan,
            "p99": float(np.percentile(v, 99)) if n else np.nan,
            "max": int(v.max()) if n else np.nan,
            "moyenne": float(v.mean()) if n else np.nan,
        })
        lim_rows.append({
            "population": pop_nom, "segment": seg_nom, "n_troncons": n,
            "n_1c_sup_12": depasse, "pct_1c_sup_12": 100 * depasse / n if n else np.nan,
            "n_1c_facteur_limitant": limitant,
            "pct_1c_facteur_limitant": 100 * limitant / n if n else np.nan,
        })

dist = pd.DataFrame(dist_rows)
lim = pd.DataFrame(lim_rows)
dist.to_csv(OUT / "verif_surcharge_distribution_1ere_classe.csv", index=False, encoding="utf-8")
lim.to_csv(OUT / "verif_surcharge_facteur_limitant_1ere_classe.csv", index=False, encoding="utf-8")

emit("\nDistribution de la charge de 1re classe (grain tronçon) :")
emit(dist.to_string(index=False))
emit("\nDépassement des 12 places et facteur limitant (grain tronçon) :")
emit(lim.to_string(index=False))

# --------------------------------------------------------------------------- #
# Q5 : ventilation par segment de la contingence — H25, grain course
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Q5 — Ventilation par segment, H25, grain course")
emit("-" * 78)

cs25 = courses_cache["H25 seule"]
seg_rows = []
for seg in ["bas", "haut"]:
    s = cs25[cs25["segment"] == seg]
    r = contingence(s["D2"], s["DT"])
    r.update({"population": "H25 seule", "grain": "course",
              "segment": seg, "regle_segment": "canonique blocs.py:189 (haut si au moins un tronçon haut)"})
    seg_rows.append(r)

# Variante d'opérationnalisation : course x segment (une course mixte compte dans les deux)
sub25 = df[POPULATIONS["H25 seule"]]
for seg in ["bas", "haut"]:
    s = sub25[sub25[COL_SEG] == seg]
    g = s.groupby([COL_DATE, COL_NUM, COL_ANNEE], sort=True).agg(
        c2=(COL_2C, "max"), ct=(COL_TOT, "max")).reset_index()
    r = contingence(g["c2"] > SEUIL_D2, g["ct"] > SEUIL_DT)
    r.update({"population": "H25 seule", "grain": "course",
              "segment": seg,
              "regle_segment": "variante course x segment (course mixte comptée dans les deux)"})
    seg_rows.append(r)

seg_df = pd.DataFrame(seg_rows)[["population", "grain", "segment", "regle_segment"] + cols_order[2:]]
seg_df.to_csv(OUT / "verif_definitions_surcharge_par_segment.csv", index=False, encoding="utf-8")
emit(seg_df.to_string(index=False))

n_mixte = int(cs25["mixte"].sum())
emit(f"\nCourses H25 traversant les deux segments (mixtes) : {n_mixte:,} "
     f"sur {len(cs25):,} ({100*n_mixte/len(cs25):.2f} %) — d'où les deux règles rapportées.")

# --------------------------------------------------------------------------- #
# Sensibilité au seuil de la définition « total » — l'énoncé admet deux lectures
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Sensibilité — deux lectures défendables de « définition fondée sur le total »")
emit("-" * 78)
emit("DT75 : total > 75 = 63 sièges de 2e classe + 12 places de 1re classe.")
emit("       Lecture de l'énoncé : les 12 places de 1re classe comptent comme capacité.")
emit("DT63 : total > 63 = charge totale rapportée aux seuls sièges de 2e classe.")
emit("       Lecture concurrente : les places de 1re classe ne sont pas offertes aux")
emit("       voyageurs de 2e classe, la capacité de référence reste 63.")
emit("Aucune des deux n'est tranchée ici ; les deux sont rapportées.")

sens_rows = []
for pop_nom, mask in POPULATIONS.items():
    sub = df[mask]
    cs = courses_cache[pop_nom]
    for seuil in (63, 75):
        # grain tronçon
        r = contingence(sub["D2"], sub[COL_TOT] > seuil)
        r.update({"population": pop_nom, "grain": "tronçon",
                  "definition_total": f"DT{seuil} (total > {seuil})"})
        sens_rows.append(r)
        # grain course
        r = contingence(cs["D2"], cs["charge_tot_max"] > seuil)
        r.update({"population": pop_nom, "grain": "course",
                  "definition_total": f"DT{seuil} (total > {seuil})"})
        sens_rows.append(r)

sens = pd.DataFrame(sens_rows)[["population", "grain", "definition_total"] + cols_order[2:]]
sens.to_csv(OUT / "verif_definitions_surcharge_sensibilite_seuil.csv",
            index=False, encoding="utf-8")
emit("")
emit(sens[["population", "grain", "definition_total", "n_total", "total_D2_n", "total_DT_n",
           "ecart_relatif_DT_vs_D2_pct", "taux_discordance_sur_union_pct",
           "kappa_cohen", "jaccard"]].to_string(index=False))

# --------------------------------------------------------------------------- #
# Contrôle de cohérence : identité comptable et part de la 2e classe
# --------------------------------------------------------------------------- #
emit("")
emit("-" * 78)
emit("Contrôle de cohérence — identité comptable et part de la 2e classe")
emit("-" * 78)

ecart = df[COL_TOT] - (df[COL_1C] + df[COL_2C])
n_viol = int((ecart.abs() > 1e-9).sum())
emit(f"\nIdentité total = 1re + 2e, sur l'intégralité du jeu ({len(df):,} lignes) :")
emit(f"  lignes en écart (|écart| > 1e-9) : {n_viol}")
emit(f"  écart absolu maximal             : {float(ecart.abs().max()):.10g}")
emit(f"  somme des écarts                 : {float(ecart.sum()):.10g}")
emit(f"  => identité {'VÉRIFIÉE sans écart' if n_viol == 0 else 'INFIRMÉE'}")

part_rows = [{
    "controle": "identite_total_egale_1ere_plus_2eme",
    "perimetre": "ml_dataset intégral (H22-H25)",
    "n_lignes": len(df), "n_lignes_en_ecart": n_viol,
    "ecart_abs_max": float(ecart.abs().max()), "somme_ecarts": float(ecart.sum()),
    "verdict": "vérifiée sans écart" if n_viol == 0 else "infirmée",
}]

emit("\nPart de la 2e classe dans la charge totale (régime actuel H22-H25) :")
sub = df[POPULATIONS["H22-H25 (régime actuel)"]]
ATTENDU = {"global": 94.7, "bas": 94.9, "haut": 92.7}
for seg_nom, seg_mask in [("global", pd.Series(True, index=sub.index)),
                          ("bas", sub[COL_SEG].eq("bas")),
                          ("haut", sub[COL_SEG].eq("haut"))]:
    s = sub[seg_mask]
    som2, somt = float(s[COL_2C].sum()), float(s[COL_TOT].sum())
    pct = 100 * som2 / somt if somt else np.nan
    att = ATTENDU[seg_nom]
    emit(f"  {seg_nom:<7} : somme 2e = {som2:>14,.0f} | somme totale = {somt:>14,.0f} | "
         f"part = {pct:6.3f} %  (publié §4.3.1 : {att} % ; écart {pct-att:+.3f} pt)")
    part_rows.append({
        "controle": "part_2eme_classe_dans_total",
        "perimetre": f"H22-H25 régime actuel — {seg_nom}",
        "somme_2eme_classe": som2, "somme_totale": somt,
        "part_2eme_pct_calculee": pct, "part_2eme_pct_publiee_4_3_1": att,
        "ecart_points": pct - att,
        "verdict": "concordant à 0,05 pt" if abs(pct - att) < 0.05 else "écart à signaler",
    })

# Faits de cadrage repris par la synthèse (aucune valeur n'y est saisie à la main)
part_rows.append({
    "controle": "courses_mixtes_H25",
    "perimetre": "H25, grain course",
    "n_lignes": len(cs25), "n_courses_mixtes": n_mixte,
    "pct_courses_mixtes": 100 * n_mixte / len(cs25) if len(cs25) else np.nan,
    "verdict": "deux règles de segment rapportées",
})
for an in ["H22", "H23", "H24", "H25"]:
    part_rows.append({
        "controle": "volumetrie_par_annee_horaire",
        "perimetre": an, "n_lignes": int((df[COL_ANNEE] == an).sum()),
        "verdict": "tronçons observés présents dans le jeu",
    })

pd.DataFrame(part_rows).to_csv(OUT / "verif_surcharge_controle_coherence.csv",
                               index=False, encoding="utf-8")

# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #
emit("")
emit("=" * 78)
emit(f"Exécuté le {DATE_EXEC} | {VERSIONS}")
emit(f"Commande : {CMD}")
emit("Sorties écrites dans docs/memoire/verifs/section_4_3_7/ :")
for f in ["verif_definitions_surcharge.csv",
          "verif_definitions_surcharge_sensibilite_seuil.csv",
          "verif_definitions_surcharge_par_segment.csv",
          "verif_surcharge_distribution_1ere_classe.csv",
          "verif_surcharge_facteur_limitant_1ere_classe.csv",
          "verif_surcharge_controle_coherence.csv"]:
    emit(f"  - {f}")
emit("=" * 78)

(OUT / "verif_definitions_surcharge_journal.txt").write_text("\n".join(LOG), encoding="utf-8")
