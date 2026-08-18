#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests statistiques — Section 4.3 du mémoire (compréhension des données, ligne R35).

LECTURE SEULE. Aucune donnée n'est modifiée. Le dataset canonique
`data/processed/ml_dataset.parquet` doit avoir l'empreinte SHA256[:8] == ba493568
(gel v2, ADR-076) : contrôle dur en préambule, STOP sinon.

Périmètre : H22-H25 (iso-périmètre contemporain, aligné §4.4.1), grain tronçon,
deuxième classe uniquement (target_voyageurs_2eme_classe).

Conventions (établies dans le repo, non redéfinies ici) :
  - Segment : colonne `spatial_segment` (bas = deux gares d'ordre <= 10, Vevey→Blonay
    incluse ; haut = tronçon touchant une gare d'ordre > 10, crémaillère). Vérifié
    identique à la règle d'ordre sur la totalité du dataset (0 écart).
  - Jour ouvrable / week-end-férié : `cal_type_jour_3classes`
    (ouvrable ; week-end/férié = samedi ∪ dimanche_ferie).
  - Surcharge : target_voyageurs_2eme_classe > 63 (ADR-060 / ADR-CF16, seuil assises).
  - Fenêtres de pointe de RÉFÉRENCE (heure de passage = heure de DÉPART du tronçon,
    minute-du-jour) : matin [6h00, 8h00), soir [16h00, 18h00). Intervalles demi-ouverts
    de 2 h chacun (cohérent avec la variante « 5h30-7h30 » de l'énoncé, elle-même de 2 h).
    Variantes de sensibilité :
      -30/+30 min : matin [5h30, 7h30), soir [16h30, 18h30)
      -1h/+1h     : matin [5h00, 7h00), soir [17h00, 19h00)
  - Agrégats journaliers : toujours sur les tronçons OBSERVÉS du jour (dénominateur
    variable), jamais un dénominateur fixe. Lorsqu'un test partitionne la journée en
    fenêtres (T5 : pointe / hors pointe), le dénominateur est celui des tronçons
    observés du jour DANS LA FENÊTRE considérée — un sous-ensemble des tronçons
    observés du jour, donc toujours variable et jamais fixe.

Sortie : docs/memoire/tests_section_4_3/ (rapport md + un CSV par tableau).
Ce script est conservé dans analysis/ (sans commit).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

# --------------------------------------------------------------------------- #
# Chemins & constantes
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[4]
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
OFFER = ROOT / "data" / "processed" / "horaires_r35_troncons_jour.parquet"
OUT = Path(__file__).resolve().parent / "tests_section_4_3"
OUT.mkdir(parents=True, exist_ok=True)

HASH_ATTENDU = "ba493568"
SEUIL = 63
ANNEES = ["H22", "H23", "H24", "H25"]
OUVR = "ouvrable"
WE = ["samedi", "dimanche_ferie"]

# Fenêtres de pointe (minutes du jour, intervalles demi-ouverts [start, end))
WIN = {
    "reference (6h-8h / 16h-18h)":       ((360, 480), (960, 1080)),
    "-30/+30 min (5h30-7h30 / 16h30-18h30)": ((330, 450), (990, 1110)),
    "-1h/+1h (5h-7h / 17h-19h)":         ((300, 420), (1020, 1140)),
}
WIN_REF = WIN["reference (6h-8h / 16h-18h)"]
# Fenêtre « large » de la publication §4.3.4 (verif_434), heures pleines {5,6,7,8}∪{16,17,18,19}
POINTE_LARGE_HEURES = {5, 6, 7, 8, 16, 17, 18, 19}


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def fmt_p(p: float) -> str:
    """p arrondi à 3 chiffres significatifs, '< 0.001' le cas échéant."""
    if p < 0.001:
        return "< 0.001"
    return f"{p:.3g}"


def in_window(minutes: np.ndarray, cfg) -> np.ndarray:
    (ms, me), (es, ee) = cfg
    return ((minutes >= ms) & (minutes < me)) | ((minutes >= es) & (minutes < ee))


def cliff_delta_from_U(U1: float, n1: int, n2: int) -> float:
    """Delta de Cliff = 2*U1/(n1*n2) - 1, U1 = statistique MWU du 1er groupe."""
    return 2.0 * U1 / (n1 * n2) - 1.0


def rank_biserial_apparie(diff: np.ndarray) -> tuple[float, int, float, float]:
    """Rank-biserial apparié (Kerby 2014) sur diff = bas - haut (zéros exclus)."""
    d = diff[diff != 0]
    if len(d) == 0:
        return float("nan"), 0, 0.0, 0.0
    ranks = stats.rankdata(np.abs(d))
    t_plus = ranks[d > 0].sum()
    t_minus = ranks[d < 0].sum()
    r = (t_plus - t_minus) / (t_plus + t_minus)
    return r, len(d), float(t_plus), float(t_minus)


LOG: list[str] = []


def emit(s: str = "") -> None:
    print(s)
    LOG.append(s)


# --------------------------------------------------------------------------- #
# 0. Contrôle d'empreinte (STOP si non conforme)
# --------------------------------------------------------------------------- #
h = sha8(ML)
emit("=" * 80)
emit(f"ml_dataset.parquet SHA256[:8] = {h} (attendu {HASH_ATTENDU})")
if h != HASH_ATTENDU:
    emit("STOP — empreinte non conforme : le dataset n'est pas le gel canonique ba493568.")
    sys.exit(1)
emit("Empreinte conforme — poursuite des calculs.")
emit("=" * 80)

VERSIONS = (f"python {sys.version.split()[0]} | pandas {pd.__version__} | "
            f"numpy {np.__version__} | scipy {scipy.__version__}")
DATE_EXEC = _dt.date.today().isoformat()

# --------------------------------------------------------------------------- #
# Chargement (lecture seule)
# --------------------------------------------------------------------------- #
df = pd.read_parquet(ML, columns=[
    "base_date", "horaire_annee_horaire", "horaire_numero_train",
    "id_gare_depart_bpuic", "id_gare_arrivee_bpuic",
    "spatial_segment", "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre",
    "cal_type_jour_3classes", "cal_jour_semaine_iso", "cal_mois", "cal_heure_depart",
    "cal_depart_minute_du_jour", "target_voyageurs_2eme_classe"])
df["base_date"] = pd.to_datetime(df["base_date"])
df["charge"] = df["target_voyageurs_2eme_classe"].astype("float64")
df["minute"] = df["cal_depart_minute_du_jour"].astype("int64").to_numpy()
df["heure"] = df["cal_heure_depart"].astype("int64")
df["surch"] = df["charge"] > SEUIL
df["ouvrable"] = df["cal_type_jour_3classes"] == OUVR
df["we_ferie"] = df["cal_type_jour_3classes"].isin(WE)
df["iso_lun_ven"] = df["cal_jour_semaine_iso"].astype("Int64").isin([1, 2, 3, 4, 5])
df["samedi"] = df["cal_type_jour_3classes"] == "samedi"
df["in_pointe_ref"] = in_window(df["minute"].to_numpy(), WIN_REF)
df["seg"] = df["spatial_segment"].astype(str)

# Contrôle : spatial_segment == règle d'ordre (les deux gares <= 10 => bas)
seg_rule = np.where((df["spatial_gare_depart_ordre"] <= 10) &
                    (df["spatial_gare_arrivee_ordre"] <= 10), "bas", "haut")
assert (df["seg"].to_numpy() == seg_rule).all(), "spatial_segment != règle d'ordre"
emit(f"\nLignes (tronçons) H22-H25 : {len(df):,} | "
     f"bas {int((df['seg']=='bas').sum()):,} / haut {int((df['seg']=='haut').sum()):,}")
emit("Contrôle segment : spatial_segment == règle d'ordre (0 écart) OK")


# =========================================================================== #
# C0 — Couverture APC par segment × année horaire
# =========================================================================== #
emit("\n" + "#" * 80)
emit("# C0 — Couverture APC (part des tronçons OFFERTS effectivement mesurés)")
emit("#" * 80)

off = pd.read_parquet(OFFER, columns=[
    "date", "annee_horaire", "numero_train",
    "gare_depart_bpuic", "gare_arrivee_bpuic",
    "gare_depart_ordre", "gare_arrivee_ordre"])
off["date"] = pd.to_datetime(off["date"])
off = off[off["annee_horaire"].isin(ANNEES)].copy()
KEY = ["date", "numero_train", "gare_depart_bpuic", "gare_arrivee_bpuic"]
n_dup = int(off.duplicated(KEY).sum())
off = off.drop_duplicates(KEY).copy()
off["seg"] = np.where((off["gare_depart_ordre"] <= 10) &
                      (off["gare_arrivee_ordre"] <= 10), "bas", "haut")
mlkeys = set(zip(df["base_date"], df["horaire_numero_train"],
                 df["id_gare_depart_bpuic"], df["id_gare_arrivee_bpuic"]))
off["measured"] = [k in mlkeys for k in zip(
    off["date"], off["numero_train"], off["gare_depart_bpuic"], off["gare_arrivee_bpuic"])]

emit(f"Dénominateur = tronçons offerts (grille planifiée horaires_r35_troncons_jour, "
     f"dédupliquée sur {KEY}, {n_dup:,} doublons retirés).")
emit(f"Numérateur   = tronçons offerts appariés à une mesure APC dans ml_dataset "
     f"(clé date × n° train × bpuic dep × bpuic arr).")

c0_rows = []
for an in ANNEES + ["H22-H25"]:
    sub = off if an == "H22-H25" else off[off["annee_horaire"] == an]
    row = {"annee_horaire": an}
    covs = {}
    for seg in ["bas", "haut"]:
        s = sub[sub["seg"] == seg]
        offered = len(s)
        measured = int(s["measured"].sum())
        cov = 100.0 * measured / offered if offered else float("nan")
        covs[seg] = cov
        row[f"offert_{seg}"] = offered
        row[f"mesure_{seg}"] = measured
        row[f"couverture_{seg}_pct"] = round(cov, 1)
    row["ecart_bas_moins_haut_pts"] = round(covs["bas"] - covs["haut"], 1)
    c0_rows.append(row)
c0 = pd.DataFrame(c0_rows)
emit("\n" + c0.to_string(index=False))
ecart_max = c0["ecart_bas_moins_haut_pts"].abs().max()
C0_FLAG = ecart_max > 10
emit(f"\nÉcart |bas - haut| maximal sur les années/total : {ecart_max:.1f} pts "
     f"→ {'⚠ DÉPASSE 10 pts' if C0_FLAG else 'sous le seuil de 10 pts (pas d’alerte)'}")

# Caveat : mesures APC absentes de la grille reconstruite (alignement imparfait)
offkeys = set(zip(off["date"], off["numero_train"],
                  off["gare_depart_bpuic"], off["gare_arrivee_bpuic"]))
ml_in_off = np.fromiter(
    (k in offkeys for k in zip(df["base_date"], df["horaire_numero_train"],
                               df["id_gare_depart_bpuic"], df["id_gare_arrivee_bpuic"])),
    dtype=bool, count=len(df))
pct_ml_hors_offre = 100.0 * (~ml_in_off).mean()
emit(f"Note d'alignement : {int((~ml_in_off).sum()):,} tronçons mesurés ({pct_ml_hors_offre:.1f} %) "
     f"absents de la grille reconstruite (surtout H23/H25) — la grille sous-décrit l'offre "
     f"réelle ces années-là ; la couverture absolue est donc à lire avec prudence, la "
     f"COMPARAISON bas/haut restant l'objet du contrôle.")
c0.to_csv(OUT / "c0_couverture_apc.csv", index=False, encoding="utf-8-sig")

# Couverture H22 tous segments confondus — calculée, jamais arrondie à la main.
_r_h22 = c0[c0["annee_horaire"] == "H22"].iloc[0]
_num_h22 = int(_r_h22["mesure_bas"]) + int(_r_h22["mesure_haut"])
_den_h22 = int(_r_h22["offert_bas"]) + int(_r_h22["offert_haut"])
_cov_h22 = 100.0 * _num_h22 / _den_h22
emit(f"Couverture H22 tous segments : {_cov_h22:.2f} % ({_num_h22:,}/{_den_h22:,})")


# =========================================================================== #
# Construction des agrégats journaliers × segment
# =========================================================================== #
# charge moyenne par tronçon observé, nb tronçons observés, par (jour, segment)
day_seg = df.groupby(["base_date", "seg"], observed=True).agg(
    charge_moy=("charge", "mean"),
    n_obs=("charge", "size"),
    type3=("cal_type_jour_3classes", "first"),
).reset_index()
piv_moy = day_seg.pivot(index="base_date", columns="seg", values="charge_moy")
piv_n = day_seg.pivot(index="base_date", columns="seg", values="n_obs")
type_par_jour = day_seg.drop_duplicates("base_date").set_index("base_date")["type3"]


# =========================================================================== #
# T1 — Dualité d'intensité (Wilcoxon apparié bas vs haut)
# =========================================================================== #
emit("\n" + "#" * 80)
emit("# T1 — Dualité d'intensité : charge moyenne/tronçon, bas vs haut (Wilcoxon apparié)")
emit("#" * 80)


def t1_bloc(nom: str, jours_mask: pd.Series) -> dict:
    """jours_mask : index = base_date, bool. Filtre >=10 tronçons observés sur LES DEUX segments."""
    jours = type_par_jour.index[jours_mask.reindex(type_par_jour.index, fill_value=False)]
    both = piv_n.reindex(jours)
    ok = both["bas"].notna() & both["haut"].notna() & (both["bas"] >= 10) & (both["haut"] >= 10)
    jours_ret = both.index[ok]
    n_candidats = len(jours)
    n_exclus = n_candidats - len(jours_ret)
    bas = piv_moy.loc[jours_ret, "bas"].to_numpy(dtype=float)
    haut = piv_moy.loc[jours_ret, "haut"].to_numpy(dtype=float)
    diff = bas - haut
    W, p = stats.wilcoxon(bas, haut, alternative="two-sided", zero_method="wilcox")
    r_rb, n_nonzero, _tp, _tm = rank_biserial_apparie(diff)
    n_bas_sup = int((bas > haut).sum())
    res = {
        "sous_groupe": nom,
        "n_jours_candidats": n_candidats,
        "n_jours_exclus_<10tr": n_exclus,
        "n_paires": len(jours_ret),
        "n_paires_non_nulles": n_nonzero,
        "wilcoxon_W": round(float(W), 3),
        "p": p,
        "rank_biserial_apparie": round(float(r_rb), 4),
        "mediane_bas": round(float(np.median(bas)), 3),
        "mediane_haut": round(float(np.median(haut)), 3),
        "mediane_diff_bas_moins_haut": round(float(np.median(diff)), 3),
        "n_jours_bas_sup_haut": n_bas_sup,
        "part_jours_bas_sup_haut_pct": round(100.0 * n_bas_sup / len(jours_ret), 1),
    }
    emit(f"\n[{nom}] paires retenues = {len(jours_ret)} "
         f"(candidats {n_candidats}, exclus <10 tr {n_exclus})")
    emit(f"  W={res['wilcoxon_W']}  p={fmt_p(p)}  rank-biserial={res['rank_biserial_apparie']}")
    emit(f"  médiane bas={res['mediane_bas']} / haut={res['mediane_haut']} "
         f"(diff méd. {res['mediane_diff_bas_moins_haut']})")
    emit(f"  jours bas>haut : {n_bas_sup}/{len(jours_ret)} "
         f"({res['part_jours_bas_sup_haut_pct']} %)")
    return res


tous_mask = pd.Series(True, index=type_par_jour.index)
ouvr_mask = type_par_jour == OUVR
we_mask = type_par_jour.isin(WE)
t1_rows = [
    t1_bloc("tous jours", tous_mask),
    t1_bloc("jours ouvrables", ouvr_mask),
    t1_bloc("week-ends & fériés", we_mask),
]
t1 = pd.DataFrame(t1_rows)
t1_out = t1.copy()
t1_out["p"] = t1_out["p"].map(lambda x: f"{x:.3g}")
t1_out.to_csv(OUT / "t1_wilcoxon.csv", index=False, encoding="utf-8-sig")


# =========================================================================== #
# T2 — Structures horaires
# =========================================================================== #
emit("\n" + "#" * 80)
emit("# T2 — Structures horaires : part de charge en pointe (Mann-Whitney bas vs haut)")
emit("#" * 80)

# Table (jour ouvrable, segment) -> part de charge en pointe.
# Filtre "même que T1" : jours ouvrables où LES DEUX segments ont >=10 tronçons observés.
ouvr_jours = type_par_jour.index[ouvr_mask]
both_o = piv_n.reindex(ouvr_jours)
ok_o = (both_o["bas"] >= 10) & (both_o["haut"] >= 10) & both_o["bas"].notna() & both_o["haut"].notna()
jours_t2 = both_o.index[ok_o]
emit(f"Jours ouvrables retenus (>=10 tronçons sur les deux segments) : {len(jours_t2)} "
     f"(candidats {len(ouvr_jours)}, exclus {len(ouvr_jours) - len(jours_t2)})")

dfo = df[df["ouvrable"] & df["base_date"].isin(jours_t2)].copy()


def parts_pointe(seg: str, cfg) -> np.ndarray:
    s = dfo[dfo["seg"] == seg]
    inw = in_window(s["minute"].to_numpy(), cfg)
    tot = s.groupby("base_date")["charge"].sum()
    pnt = s.assign(w=inw).groupby("base_date").apply(
        lambda g: g.loc[g["w"], "charge"].sum(), include_groups=False)
    part = (pnt / tot).reindex(tot.index)
    return part.to_numpy(dtype=float)


def mwu_bloc(nom_cfg: str, cfg_haut, cfg_bas=WIN_REF) -> dict:
    bas = parts_pointe("bas", cfg_bas)
    haut = parts_pointe("haut", cfg_haut)
    bas = bas[~np.isnan(bas)]
    haut = haut[~np.isnan(haut)]
    U, p = stats.mannwhitneyu(bas, haut, alternative="two-sided")
    delta = cliff_delta_from_U(U, len(bas), len(haut))
    res = {
        "config": nom_cfg,
        "fenetre_bas": "reference",
        "n_bas": len(bas),
        "n_haut": len(haut),
        "mannwhitney_U": round(float(U), 1),
        "p": p,
        "cliff_delta": round(float(delta), 4),
        "mediane_part_bas_pct": round(100 * float(np.median(bas)), 2),
        "mediane_part_haut_pct": round(100 * float(np.median(haut)), 2),
    }
    return res


# Résultat principal (référence des deux côtés)
mwu_ref = mwu_bloc("reference (6h-8h / 16h-18h)", WIN_REF)
emit(f"\n[Référence] n bas={mwu_ref['n_bas']} / haut={mwu_ref['n_haut']}  "
     f"U={mwu_ref['mannwhitney_U']}  p={fmt_p(mwu_ref['p'])}  "
     f"delta Cliff={mwu_ref['cliff_delta']}")
emit(f"  médiane part en pointe : bas={mwu_ref['mediane_part_bas_pct']} % / "
     f"haut={mwu_ref['mediane_part_haut_pct']} %")
t2_mwu = pd.DataFrame([mwu_ref])
t2_mwu_out = t2_mwu.copy()
t2_mwu_out["p"] = t2_mwu_out["p"].map(lambda x: f"{x:.3g}")
t2_mwu_out.to_csv(OUT / "t2_mann_whitney.csv", index=False, encoding="utf-8-sig")

# Sensibilité : fenêtre du HAUT décalée, bas en référence
emit("\n-- Sensibilité (fenêtre du HAUT décalée, bas en référence) --")
sens_rows = []
for nom, cfg in WIN.items():
    r = mwu_bloc(nom, cfg_haut=cfg, cfg_bas=WIN_REF)
    r["fenetre_haut"] = nom
    sens_rows.append(r)
    emit(f"  {nom:42s} U={r['mannwhitney_U']:>10}  p={fmt_p(r['p']):>8}  "
         f"delta={r['cliff_delta']:+.4f}  méd. haut={r['mediane_part_haut_pct']} %")
t2_sens = pd.DataFrame(sens_rows)[
    ["config", "fenetre_bas", "fenetre_haut", "n_bas", "n_haut",
     "mannwhitney_U", "p", "cliff_delta", "mediane_part_bas_pct", "mediane_part_haut_pct"]]
t2_sens_out = t2_sens.copy()
t2_sens_out["p"] = t2_sens_out["p"].map(lambda x: f"{x:.3g}")
t2_sens_out.to_csv(OUT / "t2_sensibilite_fenetres.csv", index=False, encoding="utf-8-sig")

# Chi² d'homogénéité sur les distributions horaires (24 bins, charge totale), jours ouvrables
emit("\n-- Chi² d'homogénéité des profils horaires (24 h, charge totale, jours ouvrables) --")
dfo_all = df[df["ouvrable"] & df["base_date"].isin(jours_t2)]
tab = dfo_all.groupby(["seg", "heure"])["charge"].sum().unstack("heure").reindex(
    index=["bas", "haut"], columns=range(24)).fillna(0.0)
# retirer les heures sans aucune desserte (charge totale nulle -> fréquence attendue nulle)
heures_servies = tab.columns[tab.sum(axis=0) > 0]
n_heures_hors = 24 - len(heures_servies)
tab = tab[heures_servies]
chi2, pchi, ddl, _exp = stats.chi2_contingency(tab.to_numpy())
N = float(tab.to_numpy().sum())
cramer_v = float(np.sqrt(chi2 / (N * (min(tab.shape) - 1))))
emit(f"  Heures desservies (charge>0) : {len(heures_servies)}/24 "
     f"({n_heures_hors} heures nocturnes sans desserte retirées : "
     f"{[int(x) for x in range(24) if x not in list(heures_servies)]})")
emit(f"  chi2={chi2:,.1f}  ddl={ddl}  p={fmt_p(pchi)}  V de Cramér={cramer_v:.4f}  "
     f"(N charge={int(N):,})")
emit("  NB : la charge agrégée est traitée comme des effectifs (choix de l'énoncé) ; le chi²"
     " est donc mécaniquement énorme, le V de Cramér est l'indicateur d'effet interprétable.")

# Maxima locaux du profil horaire moyen (jours ouvrables)
emit("\n-- Maxima locaux du profil horaire moyen (jours ouvrables) --")
maxima_rows = []
prof_ouvr = df[df["ouvrable"] & df["base_date"].isin(jours_t2)]
for seg in ["bas", "haut"]:
    s = prof_ouvr[prof_ouvr["seg"] == seg]
    prof = s.groupby("heure")["charge"].mean().reindex(range(24)).fillna(0.0)
    vals = prof.to_numpy()
    pic = vals.max()
    h_pic = int(np.argmax(vals))
    emit(f"\n  [{seg}] pic principal = {h_pic}h ({pic:.2f} voy./tronçon)")
    for hh in range(24):
        left = vals[hh - 1] if hh > 0 else -np.inf
        right = vals[hh + 1] if hh < 23 else -np.inf
        if vals[hh] > left and vals[hh] >= right and vals[hh] > 0:
            rel = vals[hh] / pic
            is_pic = (hh == h_pic)
            maxima_rows.append({
                "segment": seg, "heure": hh,
                "charge_moy_troncon": round(float(vals[hh]), 3),
                "valeur_relative_au_pic": round(float(rel), 3),
                "pic_principal": is_pic,
            })
            emit(f"    maximum local {hh}h : {vals[hh]:.2f} "
                 f"({100*rel:.1f} % du pic){' [PIC]' if is_pic else ''}")
t2_maxima = pd.DataFrame(maxima_rows)
t2_maxima.to_csv(OUT / "t2_maxima_locaux.csv", index=False, encoding="utf-8-sig")

# Part AGRÉGÉE (pondérée par la charge) de la charge en pointe de référence 2 h,
# par segment × type de jour. Estimateur pooled (Σ charge en pointe / Σ charge totale),
# distinct de la médiane des parts journalières de T2 ci-dessus. Même fenêtre 2 h pour
# les deux segments (aucun décalage), afin de comparer l'effacement de la pointe.
emit("\n-- Part AGRÉGÉE de charge en pointe (réf. 2 h), par segment × type de jour --")
agg_rows = []
for typ_label, mask in [("jours ouvrables", df["ouvrable"]),
                        ("week-ends & fériés", df["we_ferie"])]:
    for seg in ["bas", "haut"]:
        s = df[mask & (df["seg"] == seg)]
        tot = float(s["charge"].sum())
        pnt = float(s.loc[s["in_pointe_ref"], "charge"].sum())
        part = 100.0 * pnt / tot if tot else float("nan")
        agg_rows.append({
            "type_jour": typ_label,
            "segment": seg,
            "n_jours": int(s["base_date"].nunique()),
            "n_troncons": int(len(s)),
            "charge_totale": int(round(tot)),
            "charge_en_pointe": int(round(pnt)),
            "part_pointe_agregee_pct": round(part, 2),
        })
        emit(f"  {typ_label:20s} {seg:4s} : part pointe = {part:5.2f} %  "
             f"({int(round(pnt)):,}/{int(round(tot)):,} voy. ; "
             f"{len(s):,} tronçons, {int(s['base_date'].nunique())} jours)")
t2_agg = pd.DataFrame(agg_rows)
t2_agg.to_csv(OUT / "t2_parts_agregees.csv", index=False, encoding="utf-8-sig")
# Effacement de la pointe au bas le week-end (même fenêtre)
_bo = t2_agg[(t2_agg.type_jour == "jours ouvrables") & (t2_agg.segment == "bas")].iloc[0]
_bw = t2_agg[(t2_agg.type_jour == "week-ends & fériés") & (t2_agg.segment == "bas")].iloc[0]
_ho = t2_agg[(t2_agg.type_jour == "jours ouvrables") & (t2_agg.segment == "haut")].iloc[0]
_hw = t2_agg[(t2_agg.type_jour == "week-ends & fériés") & (t2_agg.segment == "haut")].iloc[0]
emit(f"  → Effacement pointe BAS (ouvrable→week-end, même fenêtre) : "
     f"{_bo['part_pointe_agregee_pct']:.2f} % → {_bw['part_pointe_agregee_pct']:.2f} % "
     f"({_bw['part_pointe_agregee_pct'] - _bo['part_pointe_agregee_pct']:+.2f} pts) ; "
     f"HAUT : {_ho['part_pointe_agregee_pct']:.2f} % → {_hw['part_pointe_agregee_pct']:.2f} %")


# =========================================================================== #
# T4 — Saisonnalité de la surcharge (Kruskal-Wallis par mois calendaire)
# =========================================================================== #
emit("\n" + "#" * 80)
emit("# T4 — Saisonnalité de la surcharge : taux journalier par mois (Kruskal-Wallis)")
emit("#" * 80)

day = df.groupby("base_date", observed=True).agg(
    n_obs=("charge", "size"),
    n_surch=("surch", "sum"),
    mois=("cal_mois", "first"),
).reset_index()
n_jours_tot = len(day)
day_ok = day[day["n_obs"] >= 30].copy()
n_exclus_t4 = n_jours_tot - len(day_ok)
day_ok["taux"] = 100.0 * day_ok["n_surch"] / day_ok["n_obs"]
emit(f"Jours totaux : {n_jours_tot} | retenus (>=30 tronçons) : {len(day_ok)} | "
     f"exclus (<30) : {n_exclus_t4}")

MOIS_NOM = {1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
            7: "juillet", 8: "août", 9: "septembre", 10: "octobre",
            11: "novembre", 12: "décembre"}
groupes = [day_ok.loc[day_ok["mois"] == m, "taux"].to_numpy() for m in range(1, 13)]
H, pkw = stats.kruskal(*groupes)
k = 12
n_kw = int(sum(len(g) for g in groupes))
ddl_kw = k - 1
epsilon2 = float(H / (n_kw - 1))
emit(f"\nKruskal-Wallis : H={H:.3f}  ddl={ddl_kw}  p={fmt_p(pkw)}  epsilon²={epsilon2:.4f}  "
     f"(n={n_kw})")

t4_rows = []
for m in range(1, 13):
    g = day_ok.loc[day_ok["mois"] == m, "taux"]
    t4_rows.append({
        "mois": m, "mois_nom": MOIS_NOM[m],
        "n_jours": int(len(g)),
        "mediane_taux_surcharge_pct": round(float(np.median(g)), 3) if len(g) else float("nan"),
        "moyenne_taux_surcharge_pct": round(float(g.mean()), 3) if len(g) else float("nan"),
    })
t4 = pd.DataFrame(t4_rows).sort_values("mediane_taux_surcharge_pct", ascending=False)
t4["rang"] = range(1, len(t4) + 1)
t4 = t4.sort_values("mois")
emit("\n" + t4.to_string(index=False))
emit("\nClassement des mois (médiane décroissante du taux de surcharge) :")
for _, r in t4.sort_values("rang").iterrows():
    emit(f"  {int(r['rang']):>2}. {r['mois_nom']:<10} "
         f"médiane {r['mediane_taux_surcharge_pct']:.3f} % (n={int(r['n_jours'])} j)")
# stats globales dans le CSV (colonnes répétées + entête)
t4_csv = t4.copy()
t4_csv["kruskal_H"] = round(float(H), 3)
t4_csv["ddl"] = ddl_kw
t4_csv["p"] = f"{pkw:.3g}"
t4_csv["epsilon2"] = round(epsilon2, 4)
t4_csv["n_total"] = n_kw
t4_csv.to_csv(OUT / "t4_kruskal_wallis.csv", index=False, encoding="utf-8-sig")


# =========================================================================== #
# T5 — Concentration de la surcharge en pointe (test journalier apparié)
# =========================================================================== #
# Unité d'analyse = LE JOUR, comme T1 et T2. Chaque jour ouvrable fournit une paire
# (taux de surcharge en pointe, taux de surcharge hors pointe) sur le segment bas ;
# le test est un Wilcoxon apparié sur ces 990 paires, avec la corrélation bisériale
# de rang de Kerby (2014) comme taille d'effet — mêmes conventions que T1.
# Le tableau de contingence au grain du tronçon suit, en COMPLÉMENT DESCRIPTIF.
emit("\n" + "#" * 80)
emit("# T5 — Concentration de la surcharge en pointe (segment BAS, jours ouvrables)")
emit("#      Test principal : Wilcoxon apparié au grain JOURNALIER")
emit("#" * 80)

bas_ouvr = df[(df["seg"] == "bas") & df["ouvrable"]].copy()
n_bo = len(bas_ouvr)
minutes_bo = bas_ouvr["minute"].to_numpy()
surch_bo = bas_ouvr["surch"].to_numpy()

MIN_TR_T5 = 10   # tronçons minimum DE PART ET D'AUTRE (filtre homologue de T1/T2)

# Agrégats journaliers : toujours sur les tronçons OBSERVÉS du jour, dans chaque
# fenêtre (dénominateurs variables, jamais fixes) — convention commune de la section.
_g5 = (bas_ouvr.assign(inw=bas_ouvr["in_pointe_ref"])
       .groupby(["base_date", "inw"], observed=True)
       .agg(n_tr=("surch", "size"), n_su=("surch", "sum")).reset_index())
_n5 = _g5.pivot(index="base_date", columns="inw", values="n_tr")
_s5 = _g5.pivot(index="base_date", columns="inw", values="n_su")
_cand5 = len(_n5)
_ok5 = (_n5[True].notna() & _n5[False].notna()
        & (_n5[True] >= MIN_TR_T5) & (_n5[False] >= MIN_TR_T5))
_jours5 = _n5.index[_ok5]
_excl5 = _cand5 - len(_jours5)

taux_pnt_j = (_s5.loc[_jours5, True] / _n5.loc[_jours5, True]).to_numpy(dtype=float)
taux_hrs_j = (_s5.loc[_jours5, False] / _n5.loc[_jours5, False]).to_numpy(dtype=float)
diff5 = taux_pnt_j - taux_hrs_j

W5, p5_j = stats.wilcoxon(taux_pnt_j, taux_hrs_j, alternative="two-sided",
                          zero_method="wilcox")
r_rb5, n_nz5, _tp5, _tm5 = rank_biserial_apparie(diff5)
n_jours_pnt_sup = int((diff5 > 0).sum())

emit(f"\nUnité d'analyse : le JOUR (agrégat journalier), segment bas, jours ouvrables.")
emit(f"Paires retenues : {len(_jours5)} (candidats {_cand5}, exclus <{MIN_TR_T5} tronçons "
     f"d'un côté ou de l'autre : {_excl5})")
emit(f"  Wilcoxon apparié : W={W5:,.1f}  p={fmt_p(p5_j)}  (p exact = {p5_j:.4g})")
emit(f"  Corrélation bisériale de rang (Kerby) = {r_rb5:.4f} "
     f"(paires non nulles : {n_nz5}/{len(_jours5)})")
emit(f"  Taux de surcharge médian : pointe {100*float(np.median(taux_pnt_j)):.3f} % / "
     f"hors pointe {100*float(np.median(taux_hrs_j)):.3f} %")
emit(f"  Différence médiane (pointe − hors pointe) = "
     f"{100*float(np.median(diff5)):+.3f} pts")
emit(f"  Jours où le taux en pointe dépasse le taux hors pointe : "
     f"{n_jours_pnt_sup}/{len(_jours5)} ({100.0*n_jours_pnt_sup/len(_jours5):.1f} %)")

t5_journalier = {
    "sous_groupe": "segment bas, jours ouvrables",
    "unite_analyse": "jour (agrégat journalier)",
    "n_jours_candidats": _cand5,
    f"n_jours_exclus_<{MIN_TR_T5}tr": _excl5,
    "n_paires": len(_jours5),
    "n_paires_non_nulles": n_nz5,
    "wilcoxon_W": round(float(W5), 3),
    "p": p5_j,
    "rank_biserial_apparie": round(float(r_rb5), 4),
    "mediane_taux_pointe_pct": round(100 * float(np.median(taux_pnt_j)), 3),
    "mediane_taux_hors_pointe_pct": round(100 * float(np.median(taux_hrs_j)), 3),
    "mediane_diff_pts": round(100 * float(np.median(diff5)), 3),
    "n_jours_pointe_sup_hors": n_jours_pnt_sup,
    "part_jours_pointe_sup_hors_pct": round(100.0 * n_jours_pnt_sup / len(_jours5), 1),
}
pd.DataFrame([{**t5_journalier, "p": f"{p5_j:.3g}"}]).to_csv(
    OUT / "t5_wilcoxon_journalier.csv", index=False, encoding="utf-8-sig")


# --------------------------------------------------------------------------- #
# T5 — COMPLÉMENT DESCRIPTIF (grain tronçon, SANS test inférentiel principal)
# --------------------------------------------------------------------------- #
# Le tableau 2x2 ci-dessous décrit l'exposition et l'occurrence au grain du TRONÇON
# (648 088 observations bas × ouvrable). Il est conservé pour la lecture descriptive
# et la comparabilité avec les chiffres publiés (71,7 % / 86,6 %), mais son chi carré
# et son OR NE SONT PAS le test de la section : les tronçons d'une même course ne sont
# pas indépendants (dépendance intra-course), ce qui gonfle le chi carré et resserre
# artificiellement l'IC de l'OR. Le test inférentiel est le Wilcoxon journalier ci-dessus.
emit("\n" + "-" * 80)
emit("# T5 — COMPLÉMENT DESCRIPTIF au grain du TRONÇON (non inférentiel)")
emit("#   chi carré et OR reportés à titre DESCRIPTIF uniquement : les tronçons d'une")
emit("#   même course ne sont pas indépendants (dépendance intra-course).")
emit("-" * 80)


def deux_par_deux(minutes, surch, cfg):
    inw = in_window(minutes, cfg)
    a = int((inw & surch).sum())      # pointe & surchargé
    b = int((inw & ~surch).sum())     # pointe & non
    c = int((~inw & surch).sum())     # hors-pointe & surchargé
    d = int((~inw & ~surch).sum())    # hors-pointe & non
    return a, b, c, d


a, b, cc, d = deux_par_deux(minutes_bo, surch_bo, WIN_REF)
n_expo_pointe = a + b
expo = 100.0 * n_expo_pointe / n_bo
n_surch_bo = a + cc
occ_ouvr = 100.0 * a / n_surch_bo
# 2x2 stats
tab5 = np.array([[a, b], [cc, d]], dtype=float)
chi2_5, p5, ddl5, _ = stats.chi2_contingency(tab5, correction=False)
# phi = sqrt(chi2/n) : taille d'effet du tableau 2x2 au grain du tronçon. À comparer
# à la bisériale de rang journalière — l'écart entre les deux mesure ce que le grain
# tronçon dilue (chaque tronçon pèse autant qu'un jour, et ils sont corrélés).
phi_5 = float(np.sqrt(chi2_5 / n_bo))
OR = (a * d) / (b * cc)
se = np.sqrt(1/a + 1/b + 1/cc + 1/d)
or_lo, or_hi = np.exp(np.log(OR) - 1.96 * se), np.exp(np.log(OR) + 1.96 * se)
taux_pointe = a / (a + b)
taux_hors = cc / (cc + d)
ratio = taux_pointe / taux_hors

emit(f"\nTronçons bas × jours ouvrables observés : {n_bo:,}")
emit(f"Exposition (part en pointe, fenêtre réf.) : {expo:.1f} % "
     f"({n_expo_pointe:,}/{n_bo:,})")
emit(f"Occurrence (part des surchargés en pointe, réf.) : {occ_ouvr:.1f} % "
     f"({a:,}/{n_surch_bo:,})")
emit(f"\nTableau 2x2 (fenêtre réf.) :")
emit(f"                surchargé   non-surchargé   total")
emit(f"  pointe        {a:>9,}   {b:>13,}   {a+b:>7,}")
emit(f"  hors-pointe   {cc:>9,}   {d:>13,}   {cc+d:>7,}")
emit(f"  total         {a+cc:>9,}   {b+d:>13,}   {n_bo:>7,}")
emit(f"  chi2={chi2_5:,.1f}  ddl={ddl5}  p={fmt_p(p5)}   [DESCRIPTIF]")
emit(f"  phi={phi_5:.4f}  (taille d'effet du 2x2 ; bisériale de rang journalière = "
     f"{r_rb5:.4f})")
emit(f"  OR={OR:.3f}  IC95%=[{or_lo:.3f}, {or_hi:.3f}]   [IC non corrigé de la "
     f"dépendance intra-course]")
emit(f"  taux surcharge pointe={100*taux_pointe:.3f} % / hors-pointe={100*taux_hors:.3f} % "
     f"→ ratio simple = {ratio:.2f}")

# --- Raccord avec le 71,7 % publié (toutes courses = tous jours, segment bas) ---
bas_all = df[df["seg"] == "bas"]
# (i) référence 2h, tous jours
a2, b2, c2, d2 = deux_par_deux(bas_all["minute"].to_numpy(), bas_all["surch"].to_numpy(), WIN_REF)
occ_ref_tous = 100.0 * a2 / (a2 + c2)
# (ii) reproduction exacte du 71,7 % : fenêtre large heures pleines, tous jours
surch_bas_all = bas_all[bas_all["surch"]]
n_sba = len(surch_bas_all)
n_pointe_large = int(surch_bas_all["heure"].isin(POINTE_LARGE_HEURES).sum())
occ_large_tous = 100.0 * n_pointe_large / n_sba
emit(f"\n-- Raccord avec le 71,7 % publié (§4.3.4) --")
emit(f"  Publié (bas, TOUS jours, fenêtre LARGE {{5,6,7,8}}∪{{16,17,18,19}}) : "
     f"{occ_large_tous:.1f} % ({n_pointe_large:,}/{n_sba:,})  [reproduit le 71,7 %]")
emit(f"  Lecture réf. (bas, TOUS jours, fenêtre 2h) : "
     f"{occ_ref_tous:.1f} % ({a2:,}/{a2+c2:,})")
emit(f"  Lecture T5 (bas, jours OUVRABLES, fenêtre 2h) : "
     f"{occ_ouvr:.1f} % ({a:,}/{n_surch_bo:,})")
emit(f"  Écart des deux lectures = fenêtre (large 8h → réf 2h : "
     f"{occ_large_tous - occ_ref_tous:+.1f} pts) + filtre jour "
     f"(tous → ouvrables : {occ_ouvr - occ_ref_tous:+.1f} pts).")

t5_rows = [
    # ---- Bloc TEST : Wilcoxon apparié au grain journalier (test de la section) ----
    {"bloc": "test_journalier", "metrique": "n_paires_jours", "valeur": len(_jours5),
     "numerateur": len(_jours5), "denominateur": _cand5,
     "detail": f"jours ouvrables retenus / candidats ; filtre >={MIN_TR_T5} tronçons "
               f"de part et d'autre (exclus : {_excl5})"},
    {"bloc": "test_journalier", "metrique": "wilcoxon_W", "valeur": round(float(W5), 1),
     "numerateur": np.nan, "denominateur": len(_jours5),
     "detail": f"apparié bilatéral, zero_method=wilcox ; paires non nulles "
               f"{n_nz5}/{len(_jours5)} ; p={p5_j:.4g}"},
    {"bloc": "test_journalier", "metrique": "p_value", "valeur": p5_j,
     "numerateur": np.nan, "denominateur": np.nan, "detail": f"{fmt_p(p5_j)}"},
    {"bloc": "test_journalier", "metrique": "rank_biserial_kerby", "valeur": round(float(r_rb5), 4),
     "numerateur": np.nan, "denominateur": n_nz5,
     "detail": "taille d'effet appariée (Kerby 2014), sur les paires non nulles"},
    {"bloc": "test_journalier", "metrique": "mediane_taux_pointe_pct",
     "valeur": round(100 * float(np.median(taux_pnt_j)), 3),
     "numerateur": np.nan, "denominateur": np.nan, "detail": "médiane sur les jours retenus"},
    {"bloc": "test_journalier", "metrique": "mediane_taux_hors_pointe_pct",
     "valeur": round(100 * float(np.median(taux_hrs_j)), 3),
     "numerateur": np.nan, "denominateur": np.nan, "detail": "médiane sur les jours retenus"},
    {"bloc": "test_journalier", "metrique": "n_jours_pointe_sup_hors", "valeur": n_jours_pnt_sup,
     "numerateur": n_jours_pnt_sup, "denominateur": len(_jours5),
     "detail": "jours où le taux en pointe dépasse le taux hors pointe"},
    # ---- Bloc DESCRIPTIF : grain tronçon (non inférentiel) ----
    {"bloc": "descriptif_troncon", "metrique": "exposition_pointe_pct", "valeur": round(expo, 2),
     "numerateur": n_expo_pointe, "denominateur": n_bo,
     "detail": "bas ouvrable, fenêtre réf. 2h"},
    {"bloc": "descriptif_troncon", "metrique": "occurrence_surcharge_pointe_pct",
     "valeur": round(occ_ouvr, 2), "numerateur": a, "denominateur": n_surch_bo,
     "detail": "bas ouvrable, fenêtre réf. 2h"},
    {"bloc": "descriptif_troncon", "metrique": "occurrence_tous_jours_ref_pct",
     "valeur": round(occ_ref_tous, 2), "numerateur": a2, "denominateur": a2 + c2,
     "detail": "bas TOUS jours, fenêtre réf. 2h"},
    {"bloc": "descriptif_troncon", "metrique": "occurrence_tous_jours_large_pct_(=71.7 publie)",
     "valeur": round(occ_large_tous, 2), "numerateur": n_pointe_large, "denominateur": n_sba,
     "detail": "bas TOUS jours, fenêtre large {5-8,16-19} heures pleines"},
    {"bloc": "descriptif_troncon", "metrique": "2x2_pointe_surcharge", "valeur": a,
     "numerateur": a, "denominateur": a + b, "detail": "a = pointe & surchargé"},
    {"bloc": "descriptif_troncon", "metrique": "2x2_pointe_non", "valeur": b,
     "numerateur": b, "denominateur": a + b, "detail": "b = pointe & non-surchargé"},
    {"bloc": "descriptif_troncon", "metrique": "2x2_horspointe_surcharge", "valeur": cc,
     "numerateur": cc, "denominateur": cc + d, "detail": "c = hors-pointe & surchargé"},
    {"bloc": "descriptif_troncon", "metrique": "2x2_horspointe_non", "valeur": d,
     "numerateur": d, "denominateur": cc + d, "detail": "d = hors-pointe & non-surchargé"},
    {"bloc": "descriptif_troncon", "metrique": "chi2_DESCRIPTIF", "valeur": round(float(chi2_5), 1),
     "numerateur": np.nan, "denominateur": n_bo,
     "detail": f"ddl={ddl5}, p={fmt_p(p5)} — DESCRIPTIF : dépendance intra-course, "
               f"n'est pas le test de la section"},
    {"bloc": "descriptif_troncon", "metrique": "phi_DESCRIPTIF", "valeur": round(phi_5, 4),
     "numerateur": np.nan, "denominateur": n_bo,
     "detail": "phi = racine(chi2/n) ; à comparer à la bisériale de rang journalière "
               f"({r_rb5:.4f})"},
    {"bloc": "descriptif_troncon", "metrique": "odds_ratio", "valeur": round(float(OR), 3),
     "numerateur": np.nan, "denominateur": np.nan,
     "detail": f"IC95% [{or_lo:.3f}, {or_hi:.3f}] — IC non corrigé de la dépendance intra-course"},
    {"bloc": "descriptif_troncon", "metrique": "ratio_simple_taux_pointe_sur_hors",
     "valeur": round(float(ratio), 3), "numerateur": np.nan, "denominateur": np.nan,
     "detail": f"taux pointe {100*taux_pointe:.3f}% / hors {100*taux_hors:.3f}%"},
]
t5 = pd.DataFrame(t5_rows)
t5.to_csv(OUT / "t5_exposition_surcharge.csv", index=False, encoding="utf-8-sig")

# --- Sensibilité T5 (ratio & OR uniquement ; fenêtre du bas décalée) ---
emit("\n-- Sensibilité T5 (ratio simple & OR ; fenêtre du BAS décalée) --")
t5s_rows = []
for nom, cfg in WIN.items():
    aa, bb, ccc, dd = deux_par_deux(minutes_bo, surch_bo, cfg)
    OR_ = (aa * dd) / (bb * ccc)
    se_ = np.sqrt(1/aa + 1/bb + 1/ccc + 1/dd)
    lo_, hi_ = np.exp(np.log(OR_) - 1.96 * se_), np.exp(np.log(OR_) + 1.96 * se_)
    ratio_ = (aa / (aa + bb)) / (ccc / (ccc + dd))
    t5s_rows.append({
        "config": nom, "a_pointe_surch": aa, "b_pointe_non": bb,
        "c_hors_surch": ccc, "d_hors_non": dd,
        "ratio_simple": round(float(ratio_), 3),
        "odds_ratio": round(float(OR_), 3),
        "OR_ic95_bas": round(float(lo_), 3), "OR_ic95_haut": round(float(hi_), 3),
    })
    emit(f"  {nom:42s} ratio={ratio_:5.2f}  OR={OR_:6.3f}  IC95%=[{lo_:.3f}, {hi_:.3f}]")
t5_sens = pd.DataFrame(t5s_rows)
t5_sens.to_csv(OUT / "t5_sensibilite_fenetres.csv", index=False, encoding="utf-8-sig")


# =========================================================================== #
# T5b — HAUT (surcharges) + raccords du 86,6 % publié (BAS, jours ouvrables)
# =========================================================================== #
emit("\n" + "#" * 80)
emit("# T5b — Surcharges HAUT & raccords du 86,6 % publié (BAS)")
emit("#" * 80)

t5b_rows = []

# ---- HAUT : distribution des surcharges de tronçon (fenêtre réf. 2 h), H22-H25 ----
haut_s = df[(df["seg"] == "haut") & df["surch"]]
n_h = len(haut_s)
h_pointe_tous = int(haut_s["in_pointe_ref"].sum())
h_ouvr = int(haut_s["ouvrable"].sum())
haut_s_ouvr = haut_s[haut_s["ouvrable"]]
h_pointe_ouvr = int(haut_s_ouvr["in_pointe_ref"].sum())
h_pointe_et_ouvr = int((haut_s["in_pointe_ref"] & haut_s["ouvrable"]).sum())
emit(f"\n[HAUT] surcharges tronçon H22-H25 = {n_h:,}")
emit(f"  en pointe (réf. 2 h), tous jours       : {h_pointe_tous:,}/{n_h:,} "
     f"({100*h_pointe_tous/n_h:.1f} %)")
emit(f"  en jours ouvrables                      : {h_ouvr:,}/{n_h:,} "
     f"({100*h_ouvr/n_h:.1f} %)")
emit(f"  en pointe PARMI les surcharges ouvrables : {h_pointe_ouvr:,}/{h_ouvr:,} "
     f"({100*h_pointe_ouvr/h_ouvr:.1f} %)")
emit(f"  en pointe ET ouvrable / total           : {h_pointe_et_ouvr:,}/{n_h:,} "
     f"({100*h_pointe_et_ouvr/n_h:.1f} %)")
t5b_rows += [
    {"bloc": "haut", "metrique": "surcharges_troncon_total", "periode": "H22-H25",
     "valeur_pct": np.nan, "numerateur": n_h, "denominateur": n_h,
     "detail": "toutes surcharges haut H22-H25"},
    {"bloc": "haut", "metrique": "part_en_pointe_ref_tous_jours", "periode": "H22-H25",
     "valeur_pct": round(100*h_pointe_tous/n_h, 2), "numerateur": h_pointe_tous, "denominateur": n_h,
     "detail": "fenêtre réf. 2 h ; dénominateur = toutes surcharges haut"},
    {"bloc": "haut", "metrique": "part_en_jours_ouvrables", "periode": "H22-H25",
     "valeur_pct": round(100*h_ouvr/n_h, 2), "numerateur": h_ouvr, "denominateur": n_h,
     "detail": "cal_type_jour_3classes == ouvrable"},
    {"bloc": "haut", "metrique": "part_en_pointe_ref_parmi_ouvrables", "periode": "H22-H25",
     "valeur_pct": round(100*h_pointe_ouvr/h_ouvr, 2), "numerateur": h_pointe_ouvr, "denominateur": h_ouvr,
     "detail": "dénominateur = surcharges haut en jours ouvrables"},
    {"bloc": "haut", "metrique": "part_pointe_ET_ouvrable_sur_total", "periode": "H22-H25",
     "valeur_pct": round(100*h_pointe_et_ouvr/n_h, 2), "numerateur": h_pointe_et_ouvr, "denominateur": n_h,
     "detail": "pointe réf. 2 h ET ouvrable / toutes surcharges haut"},
]

# ---- BAS : raccord du 86,6 % publié (part des surcharges en jours ouvrables) ----
emit("\n[BAS] part des surcharges de tronçon en jours ouvrables — 3 conventions de jour")
emit("  (le 86,6 % publié en §4.3.4 utilise le calendrier lundi-vendredi, fériés inclus)")
for per in ["H22-H25", "H25"]:
    bas_s = df[(df["seg"] == "bas") & df["surch"]]
    if per != "H22-H25":
        bas_s = bas_s[bas_s["horaire_annee_horaire"] == per]
    n_b = len(bas_s)
    n_ouvr3 = int(bas_s["ouvrable"].sum())                       # type_jour 3classes
    n_iso = int(bas_s["iso_lun_ven"].sum())                      # calendrier lun-ven (= publié)
    n_ouvr_sam = int((bas_s["ouvrable"] | bas_s["samedi"]).sum())  # variante + samedi
    emit(f"\n  --- {per} (n surcharges bas = {n_b:,}) ---")
    emit(f"    type_jour 'ouvrable' (fériés exclus)   : {n_ouvr3:,}/{n_b:,} "
         f"({100*n_ouvr3/n_b:.1f} %)   [convention de ce rapport]")
    emit(f"    calendrier lundi-vendredi (fériés incl.): {n_iso:,}/{n_b:,} "
         f"({100*n_iso/n_b:.1f} %)   [= 86,6 % publié]")
    emit(f"    'ouvrable' + samedi (variante)          : {n_ouvr_sam:,}/{n_b:,} "
         f"({100*n_ouvr_sam/n_b:.1f} %)")
    for lab, nn, det in [
        ("part_ouvrable_typejour", n_ouvr3, "cal_type_jour_3classes==ouvrable (fériés exclus) — convention du rapport"),
        ("part_calendrier_lun_ven", n_iso, "cal_jour_semaine_iso in 1..5 (fériés inclus) — reproduit le 86,6 % publié"),
        ("part_ouvrable_plus_samedi", n_ouvr_sam, "variante ouvrable + samedi"),
    ]:
        t5b_rows.append({
            "bloc": "bas_raccord", "metrique": lab, "periode": per,
            "valeur_pct": round(100*nn/n_b, 2), "numerateur": nn, "denominateur": n_b,
            "detail": det})

t5b = pd.DataFrame(t5b_rows)
t5b.to_csv(OUT / "t5b_haut_et_raccords.csv", index=False, encoding="utf-8-sig")
# valeurs pour le md
_hp = 100*h_pointe_tous/n_h
_ho2 = 100*h_ouvr/n_h
_hpo = 100*h_pointe_ouvr/h_ouvr
bas_all_s = df[(df["seg"] == "bas") & df["surch"]]
_b_ouvr = 100*int(bas_all_s["ouvrable"].sum())/len(bas_all_s)
_b_iso = 100*int(bas_all_s["iso_lun_ven"].sum())/len(bas_all_s)
_b_sam = 100*int((bas_all_s["ouvrable"] | bas_all_s["samedi"]).sum())/len(bas_all_s)
bas_h25_s = bas_all_s[bas_all_s["horaire_annee_horaire"] == "H25"]
_b25_ouvr = 100*int(bas_h25_s["ouvrable"].sum())/len(bas_h25_s)
_b25_iso = 100*int(bas_h25_s["iso_lun_ven"].sum())/len(bas_h25_s)


# =========================================================================== #
# Écriture du rapport Markdown
# =========================================================================== #
def num(x, n=0):
    return f"{x:,.{n}f}".replace(",", " ")


md = []
md.append("# Tests statistiques — Section 4.3 (compréhension des données, ligne R35)\n")
md.append("**Projet R35 ML — Travail de master (Erwann Nedellec).** Vérifications en "
          "lecture seule ; aucune donnée modifiée.\n")
md.append(f"- Dataset canonique : `ml_dataset.parquet` SHA256[:8] = **`{h}`** "
          f"(attendu `{HASH_ATTENDU}`) — **vérifié au lancement**.\n"
          f"- Périmètre : **H22-H25**, grain **tronçon**, **2ᵉ classe** "
          f"(`target_voyageurs_2eme_classe`), {num(len(df))} tronçons.\n"
          f"- Segment : `spatial_segment` (bas = deux gares d'ordre ≤ 10 ; haut = "
          f"tronçon touchant une gare d'ordre > 10). Identique à la règle d'ordre (0 écart).\n"
          f"- Jour ouvrable / week-end-férié : `cal_type_jour_3classes`.\n"
          f"- Surcharge : `target_voyageurs_2eme_classe` > {SEUIL}.\n"
          f"- Fenêtres de pointe (heure de **départ** du tronçon) — référence : matin "
          f"**[6h00, 8h00)**, soir **[16h00, 18h00)** (intervalles demi-ouverts de 2 h).\n"
          f"- **Agrégats journaliers** : toujours calculés sur les **tronçons observés "
          f"du jour** (dénominateur variable), jamais sur un dénominateur fixe. Lorsqu'un "
          f"test partitionne la journée en fenêtres (T5 : pointe / hors pointe), le "
          f"dénominateur est celui des tronçons observés du jour **dans la fenêtre** "
          f"considérée — sous-ensemble des tronçons observés du jour, donc lui aussi "
          f"variable.\n")

# Alerte C0 en tête si dépassement
if C0_FLAG:
    md.append(f"\n> ⚠ **ALERTE C0** — l'écart de couverture APC bas/haut atteint "
              f"**{ecart_max:.1f} pts**, au-delà du seuil de 10 pts.\n")
else:
    md.append(f"\n> **C0 — pas d'alerte.** Écart de couverture APC bas/haut maximal = "
              f"**{ecart_max:.1f} pts** (< 10 pts) sur toutes les années et le total.\n")

md.append("\n---\n\n## C0 — Couverture APC par segment × année horaire\n")
md.append("Part des **tronçons offerts** (grille planifiée `horaires_r35_troncons_jour`, "
          f"dédupliquée, {num(n_dup)} doublons retirés) **effectivement mesurés** par l'APC "
          "(appariement date × n° train × BPUIC départ × BPUIC arrivée).\n")
md.append("\n| Année | Offert bas | Mesuré bas | **Couv. bas** | Offert haut | Mesuré haut | "
          "**Couv. haut** | Écart (bas−haut) |\n|---|---:|---:|---:|---:|---:|---:|---:|\n")
for _, r in c0.iterrows():
    md.append(f"| {r['annee_horaire']} | {num(r['offert_bas'])} | {num(r['mesure_bas'])} | "
              f"**{r['couverture_bas_pct']:.1f} %** | {num(r['offert_haut'])} | "
              f"{num(r['mesure_haut'])} | **{r['couverture_haut_pct']:.1f} %** | "
              f"{r['ecart_bas_moins_haut_pts']:+.1f} pts |\n")
md.append(f"\n**Lecture.** Écart |bas−haut| maximal = **{ecart_max:.1f} pts** (H24), "
          f"sous le seuil de 10 pts → pas d'alerte. **H22 est atypiquement bas** "
          f"(couverture tous segments = **{_cov_h22:.2f} %**, soit {num(_num_h22)} tronçons "
          f"mesurés sur {num(_den_h22)} offerts) : déploiement APC partiel — l'appariement "
          f"inverse confirme que 100 % des tronçons H22 mesurés figurent dans l'offre, la "
          f"faible couverture est donc réelle (l'APC n'a mesuré qu'un peu plus de deux "
          f"tronçons offerts sur cinq), avec le trou de septembre 2022. "
          f"En H23-H24 le **haut** est même mieux couvert "
          f"(+7,6 / +8,2 pts). *Caveat d'alignement : {num((~ml_in_off).sum())} tronçons "
          f"mesurés ({pct_ml_hors_offre:.1f} %) sont absents de la grille reconstruite "
          f"(surtout H23/H25) ; la couverture absolue est donc à lire avec prudence, la "
          f"comparaison bas/haut restant robuste.*\n")

md.append("\n---\n\n## T1 — Dualité d'intensité (Wilcoxon apparié bas vs haut)\n")
md.append("Par jour et par segment : charge moyenne par tronçon observé "
          "(`mean(target_voyageurs_2eme_classe)`). Ne sont retenus que les jours où **les "
          "deux segments** comptent ≥ 10 tronçons observés. Wilcoxon signed-rank apparié, "
          "bilatéral.\n")
md.append("\n| Sous-groupe | n paires | jours exclus (<10 tr) | W | p | rank-biserial | "
          "méd. bas | méd. haut | méd. diff | jours bas>haut |\n"
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
for r in t1_rows:
    md.append(f"| {r['sous_groupe']} | {num(r['n_paires'])} | {num(r['n_jours_exclus_<10tr'])} | "
              f"{r['wilcoxon_W']:.0f} | {fmt_p(r['p'])} | {r['rank_biserial_apparie']:.4f} | "
              f"{r['mediane_bas']:.2f} | {r['mediane_haut']:.2f} | "
              f"{r['mediane_diff_bas_moins_haut']:.2f} | "
              f"{num(r['n_jours_bas_sup_haut'])}/{num(r['n_paires'])} "
              f"({r['part_jours_bas_sup_haut_pct']:.1f} %) |\n")
md.append("\n**Lecture.** La charge moyenne par tronçon du **bas** dépasse systématiquement "
          "celle du **haut** : différence médiane fortement positive, rank-biserial ≈ +1, "
          "et la quasi-totalité des jours ont bas > haut. Effet massif et homogène entre "
          "jours ouvrables et week-ends/fériés.\n")

md.append("\n---\n\n## T2 — Structures horaires\n")
md.append(f"Par jour ouvrable et par segment : part de la charge du jour tombant dans les "
          f"fenêtres de pointe de référence (matin [6h,8h) + soir [16h,18h)). Même filtre "
          f"≥ 10 tronçons sur les deux segments → **{len(jours_t2)} jours ouvrables** retenus.\n")
md.append("\n### Mann-Whitney U (part en pointe, bas vs haut) — référence\n")
md.append("\n| n bas | n haut | U | p | delta de Cliff | méd. part bas | méd. part haut |\n"
          "|---:|---:|---:|---:|---:|---:|---:|\n")
md.append(f"| {mwu_ref['n_bas']} | {mwu_ref['n_haut']} | {mwu_ref['mannwhitney_U']:.0f} | "
          f"{fmt_p(mwu_ref['p'])} | {mwu_ref['cliff_delta']:.4f} | "
          f"{mwu_ref['mediane_part_bas_pct']:.2f} % | {mwu_ref['mediane_part_haut_pct']:.2f} % |\n")
md.append(f"\n**Lecture.** La part de charge en pointe est nettement plus élevée dans le bas "
          f"(médiane {mwu_ref['mediane_part_bas_pct']:.1f} %) que dans le haut "
          f"(médiane {mwu_ref['mediane_part_haut_pct']:.1f} %) ; delta de Cliff "
          f"= {mwu_ref['cliff_delta']:.2f} (grand effet). *(Niveaux non directement comparables "
          f"au 51,9 % / 30,5 % publié en §4.3.2 : celui-ci agrège la charge sur tous les jours "
          f"(part pondérée) avec une fenêtre 3 h {{6,7,8}}∪{{16,17,18}}, ici on prend la MÉDIANE "
          f"des parts journalières sur une fenêtre 2 h — deux estimateurs et deux fenêtres "
          f"différents. Le contraste bas > haut est identique dans les deux lectures.)*\n")

md.append("\n### Chi² d'homogénéité des profils horaires (24 h, charge totale, jours ouvrables)\n")
md.append(f"chi² = **{num(chi2, 0)}**, ddl = **{ddl}**, p = **{fmt_p(pchi)}**, "
          f"**V de Cramér = {cramer_v:.3f}** (N charge = {num(N)}). La charge agrégée est "
          f"traitée comme des effectifs (choix de l'énoncé) → le chi² est mécaniquement très "
          f"grand ; **le V de Cramér est l'indicateur d'effet interprétable** (profils "
          f"horaires bas et haut fortement hétérogènes).\n")

md.append("\n### Sensibilité (fenêtre du HAUT décalée ; bas en référence)\n")
md.append("\n| Fenêtre haut | n bas | n haut | U | p | delta de Cliff | méd. part haut |\n"
          "|---|---:|---:|---:|---:|---:|---:|\n")
for r in sens_rows:
    md.append(f"| {r['fenetre_haut']} | {r['n_bas']} | {r['n_haut']} | "
              f"{r['mannwhitney_U']:.0f} | {fmt_p(r['p'])} | {r['cliff_delta']:.4f} | "
              f"{r['mediane_part_haut_pct']:.2f} % |\n")
md.append("\n**Lecture.** Décaler la fenêtre du haut (jusqu'à ±1 h) ne renverse pas le "
          "contraste : delta de Cliff et p restent stables → la dualité horaire est robuste "
          "au calage exact de la fenêtre.\n")

md.append("\n### Maxima locaux du profil horaire moyen (jours ouvrables)\n")
md.append("\n| Segment | Heure | Charge moy./tronçon | % du pic principal | Pic |\n"
          "|---|---:|---:|---:|:--:|\n")
for _, r in t2_maxima.iterrows():
    md.append(f"| {r['segment']} | {int(r['heure'])}h | {r['charge_moy_troncon']:.2f} | "
              f"{100*r['valeur_relative_au_pic']:.1f} % | {'●' if r['pic_principal'] else ''} |\n")
md.append("\n**Lecture.** Le **bas** culmine le matin (pic 7 h) puis reste élevé l'après-midi "
          "(maxima secondaires à 12 h, 15 h et 17 h, tous > 82 % du pic) : la double pointe "
          "pendulaire matin/soir se double d'un plateau d'après-midi. Le **haut** a un profil "
          "unimodal de milieu de journée (pic 15 h), signature touristique/loisir. *(Les "
          "micro-maxima nocturnes 0 h / 22-23 h sont des artefacts de bord, aux heures "
          "quasi sans desserte.)*\n")

md.append("\n### Part agrégée de la charge en pointe (réf. 2 h), par segment × type de jour\n")
md.append("Estimateur **pondéré par la charge** (Σ voyageurs en pointe / Σ voyageurs du "
          "type de jour), fenêtre de référence 2 h ([6h,8h)+[16h,18h)), **même fenêtre pour "
          "les deux segments**. Complète la médiane des parts journalières ci-dessus ; c'est "
          "l'estimateur homologue à celui de §4.3.2 (mais sur fenêtre 2 h, pas 3 h).\n")
md.append("\n| Type de jour | Segment | Part agrégée en pointe | Voyageurs en pointe / total | n tronçons | n jours |\n"
          "|---|---|---:|---:|---:|---:|\n")
for _, r in t2_agg.iterrows():
    md.append(f"| {r['type_jour']} | {r['segment']} | **{r['part_pointe_agregee_pct']:.1f} %** | "
              f"{num(r['charge_en_pointe'])} / {num(r['charge_totale'])} | "
              f"{num(r['n_troncons'])} | {num(r['n_jours'])} |\n")
md.append(f"\n**Lecture.** Avec la **même** fenêtre 2 h, la pointe du **bas s'efface le "
          f"week-end/férié** : {_bo['part_pointe_agregee_pct']:.1f} % en jours ouvrables → "
          f"{_bw['part_pointe_agregee_pct']:.1f} % le week-end "
          f"({_bw['part_pointe_agregee_pct'] - _bo['part_pointe_agregee_pct']:+.1f} pts), "
          f"signature pendulaire (navetteurs absents le week-end). Le **haut**, lui, reste "
          f"quasi stable ({_ho['part_pointe_agregee_pct']:.1f} % → "
          f"{_hw['part_pointe_agregee_pct']:.1f} %) : sa charge ne dépend pas des heures de "
          f"bureau. Le contraste bas/haut en pointe (ouvrable) est confirmé par cet "
          f"estimateur pondéré ({_bo['part_pointe_agregee_pct']:.1f} % vs "
          f"{_ho['part_pointe_agregee_pct']:.1f} %).\n")

md.append("\n---\n\n## T4 — Saisonnalité de la surcharge (Kruskal-Wallis par mois)\n")
md.append(f"Par jour : taux de surcharge = tronçons surchargés / tronçons observés (tous "
          f"segments), jours à ≥ 30 tronçons observés. Jours retenus : **{len(day_ok)}** "
          f"(exclus < 30 tr : {n_exclus_t4}). Groupes = 12 mois calendaires.\n")
md.append(f"\n**Kruskal-Wallis : H = {H:.2f}, ddl = {ddl_kw}, p = {fmt_p(pkw)}, "
          f"epsilon² = {epsilon2:.4f}** (n = {num(n_kw)}).\n")
md.append("\n| Rang | Mois | n jours | Médiane taux surcharge | Moyenne taux |\n"
          "|---:|---|---:|---:|---:|\n")
for _, r in t4.sort_values("rang").iterrows():
    md.append(f"| {int(r['rang'])} | {r['mois_nom']} | {int(r['n_jours'])} | "
              f"{r['mediane_taux_surcharge_pct']:.3f} % | {r['moyenne_taux_surcharge_pct']:.3f} % |\n")
rang_top = t4.sort_values("rang").head(3)
rang_last = t4.sort_values("rang").tail(1).iloc[0]
top_txt = ", ".join(f"{r['mois_nom']} ({r['mediane_taux_surcharge_pct']:.2f} %)"
                    for _, r in rang_top.iterrows())
md.append("\n**Lecture.** Le taux de surcharge varie significativement selon le mois "
          f"(p {fmt_p(pkw)}, epsilon² = {epsilon2:.3f}, effet modéré). En tête : {top_txt} ; "
          f"en queue **{rang_last['mois_nom']}** (médiane {rang_last['mediane_taux_surcharge_pct']:.2f} %, "
          f"creux estival). Les pics de printemps (narcisses/beau temps) et de fin/début "
          "d'année scolaire ressortent nettement.\n")

md.append("\n---\n\n## T5 — Concentration de la surcharge en pointe (segment bas, jours ouvrables)\n")
md.append("**Unité d'analyse : le jour**, comme T1, T2 et T4. Chaque jour ouvrable fournit "
          "une paire (taux de surcharge en pointe, taux de surcharge hors pointe) sur le "
          "segment bas ; les deux taux sont calculés sur les **tronçons observés du jour** "
          "dans chaque fenêtre. Test apparié de Wilcoxon, taille d'effet = corrélation "
          "bisériale de rang appariée (Kerby, 2014). Filtre homologue de T1/T2 : au moins "
          f"**{MIN_TR_T5} tronçons observés de part et d'autre**.\n")
md.append("\n| n paires (jours) | jours exclus | W | p | bisériale de rang | méd. taux pointe | "
          "méd. taux hors pointe |\n|---:|---:|---:|---|---:|---:|---:|\n"
          f"| {num(len(_jours5))} | {_excl5} | {W5:,.1f} | {fmt_p(p5_j)} | "
          f"{r_rb5:.4f} | {100*float(np.median(taux_pnt_j)):.3f} % | "
          f"{100*float(np.median(taux_hrs_j)):.3f} % |\n")
md.append(f"\n**Lecture.** Sur **{num(len(_jours5))}** jours ouvrables appariés, le taux de "
          f"surcharge en pointe dépasse le taux hors pointe **{n_jours_pnt_sup} jours sur "
          f"{len(_jours5)}** ({100.0*n_jours_pnt_sup/len(_jours5):.1f} %). "
          f"W = {W5:,.1f}, p = {fmt_p(p5_j)} (p exact = {p5_j:.3g}), bisériale de rang "
          f"= **{r_rb5:.4f}** — effet fort. La concentration de la surcharge du bas dans les "
          f"fenêtres de pointe est établie **au grain journalier**, où l'unité d'observation "
          f"est indépendante.\n")

md.append("\n### Complément descriptif au grain du tronçon (non inférentiel)\n")
md.append(f"Sur les **{num(n_bo)}** tronçons du bas en jours ouvrables (dont "
          f"**{num(n_surch_bo)}** surchargés), fenêtre de référence 2 h. Ce bloc est "
          f"**descriptif** : les tronçons d'une même course ne sont pas indépendants, le "
          f"chi² et l'IC de l'OR ci-dessous ne valent donc pas comme test — ils sont "
          f"reportés pour la lecture des effectifs et la comparabilité avec les chiffres "
          f"publiés.\n")
md.append(f"\n- **Exposition** (part des tronçons observés en pointe) : "
          f"**{expo:.1f} %** ({num(n_expo_pointe)}/{num(n_bo)}).\n"
          f"- **Occurrence** (part des surchargés survenant en pointe) : "
          f"**{occ_ouvr:.1f} %** ({num(a)}/{num(n_surch_bo)}).\n")
md.append("\n**Tableau 2×2 (fenêtre réf.) :**\n\n"
          "| | surchargé | non-surchargé | total |\n|---|---:|---:|---:|\n"
          f"| **pointe** | {num(a)} | {num(b)} | {num(a+b)} |\n"
          f"| **hors-pointe** | {num(cc)} | {num(d)} | {num(cc+d)} |\n"
          f"| **total** | {num(a+cc)} | {num(b+d)} | {num(n_bo)} |\n")
md.append(f"\n- chi² = **{num(chi2_5,0)}**, ddl = {ddl5}, p = **{fmt_p(p5)}** "
          f"— *descriptif, dépendance intra-course non corrigée*.\n"
          f"- **phi = {phi_5:.4f}** (taille d'effet du 2×2) — à comparer à la bisériale de "
          f"rang journalière **{r_rb5:.4f}**.\n"
          f"- **Odds ratio = {OR:.2f}** — IC 95 % [{or_lo:.2f}, {or_hi:.2f}] "
          f"*(IC non corrigé de la dépendance intra-course)*.\n"
          f"- Taux de surcharge en pointe = {100*taux_pointe:.3f} % vs hors-pointe = "
          f"{100*taux_hors:.3f} % → **ratio simple = {ratio:.1f}**.\n")
md.append("\n### Raccord avec le 71,7 % publié (§4.3.4)\n")
md.append("\n| Lecture | Fenêtre | Jours | Occurrence | Effectif |\n|---|---|---|---:|---|\n"
          f"| **Publié §4.3.4** | large {{5-8, 16-19}} h | tous | **{occ_large_tous:.1f} %** | "
          f"{num(n_pointe_large)}/{num(n_sba)} |\n"
          f"| Référence 2 h, tous jours | [6,8)+[16,18) | tous | {occ_ref_tous:.1f} % | "
          f"{num(a2)}/{num(a2+c2)} |\n"
          f"| **T5** (réf. 2 h, ouvrables) | [6,8)+[16,18) | ouvrables | {occ_ouvr:.1f} % | "
          f"{num(a)}/{num(n_surch_bo)} |\n")
md.append(f"\n**Lecture.** La lecture de référence reproduit **{occ_large_tous:.1f} %** avec "
          f"la fenêtre large publiée (= le 71,7 % de §4.3.4). L'écart avec la lecture T5 tient "
          f"à **deux** choix : (1) fenêtre plus étroite (large 8 h → réf 2 h : "
          f"{occ_large_tous - occ_ref_tous:+.1f} pts) ; (2) restriction aux jours ouvrables "
          f"(tous → ouvrables : {occ_ouvr - occ_ref_tous:+.1f} pts). Les deux lectures sont "
          f"cohérentes une fois ces conventions explicitées.\n")

md.append("\n### Sensibilité T5 (ratio simple & OR ; fenêtre du bas décalée)\n")
md.append("\n| Config | ratio simple | Odds ratio | IC 95 % |\n|---|---:|---:|---|\n")
for r in t5s_rows:
    md.append(f"| {r['config']} | {r['ratio_simple']:.1f} | {r['odds_ratio']:.2f} | "
              f"[{r['OR_ic95_bas']:.2f}, {r['OR_ic95_haut']:.2f}] |\n")
md.append("\n**Lecture.** Ratio et OR restent du même ordre sur les trois calages de fenêtre "
          "→ la concentration des surcharges du bas en pointe est robuste au choix de fenêtre.\n")

md.append("\n---\n\n## T5b — Surcharges du HAUT & raccords du 86,6 % publié\n")
md.append("### Segment HAUT — distribution des surcharges de tronçon (H22-H25, fenêtre réf. 2 h)\n")
md.append(f"Sur les **{num(n_h)}** surcharges de tronçon du haut (2ᵉ classe > 63) sur H22-H25 :\n")
md.append("\n| Lecture | Valeur | Effectif |\n|---|---:|---|\n"
          f"| En pointe (réf. 2 h), **tous jours** | **{_hp:.1f} %** | {num(h_pointe_tous)}/{num(n_h)} |\n"
          f"| En **jours ouvrables** | **{_ho2:.1f} %** | {num(h_ouvr)}/{num(n_h)} |\n"
          f"| En pointe **parmi** les surcharges ouvrables | {_hpo:.1f} % | {num(h_pointe_ouvr)}/{num(h_ouvr)} |\n"
          f"| En pointe **ET** ouvrable / total | {100*h_pointe_et_ouvr/n_h:.1f} % | {num(h_pointe_et_ouvr)}/{num(n_h)} |\n")
md.append(f"\n**Lecture.** À l'opposé du bas, les surcharges du **haut sont très peu concentrées "
          f"en pointe pendulaire** ({_hp:.1f} % en fenêtre réf. 2 h) et à peine la moitié tombent "
          f"en jours ouvrables ({_ho2:.1f} %) : le reste survient le week-end/férié (ski, "
          f"narcisses, loisir). La combinaison pointe × ouvrable ne capte que "
          f"{100*h_pointe_et_ouvr/n_h:.1f} % des surcharges du haut — signature touristique, "
          f"non pendulaire. *(Fenêtre 2 h plus étroite que le {{5-8,16-19}} de §4.3.4, qui donnait "
          f"13,0 % en pointe ; l'ordre de grandeur — très faible — est le même.)*\n")

md.append("\n### Segment BAS — origine du 86,6 % publié (part des surcharges en jours ouvrables)\n")
md.append("Le **86,6 %** publié en §4.3.4 compte les surcharges du bas tombant un jour de "
          "semaine au sens **calendaire (lundi-vendredi, fériés inclus)**. La convention de ce "
          "rapport (`cal_type_jour_3classes == ouvrable`) **exclut les fériés en semaine** "
          "(reclassés en dimanche/férié), d'où une valeur légèrement plus basse.\n")
md.append("\n| Période | Convention de jour | Part ouvrable | Effectif |\n|---|---|---:|---|\n"
          f"| **H22-H25** | `ouvrable` (fériés exclus) — *ce rapport* | **{_b_ouvr:.1f} %** | "
          f"{num(int(bas_all_s['ouvrable'].sum()))}/{num(len(bas_all_s))} |\n"
          f"| **H22-H25** | calendrier lun-ven (fériés inclus) — *= publié* | **{_b_iso:.1f} %** | "
          f"{num(int(bas_all_s['iso_lun_ven'].sum()))}/{num(len(bas_all_s))} |\n"
          f"| **H22-H25** | `ouvrable` + samedi (variante) | {_b_sam:.1f} % | "
          f"{num(int((bas_all_s['ouvrable']|bas_all_s['samedi']).sum()))}/{num(len(bas_all_s))} |\n"
          f"| H25 | `ouvrable` (fériés exclus) | {_b25_ouvr:.1f} % | "
          f"{num(int(bas_h25_s['ouvrable'].sum()))}/{num(len(bas_h25_s))} |\n"
          f"| H25 | calendrier lun-ven (fériés inclus) | {_b25_iso:.1f} % | "
          f"{num(int(bas_h25_s['iso_lun_ven'].sum()))}/{num(len(bas_h25_s))} |\n")
md.append(f"\n**Lecture — origine du 86,6 %.** Le **{_b_iso:.1f} %** (calendrier lun-ven, "
          f"fériés inclus) **reproduit le 86,6 % publié** ; la convention `ouvrable` de ce "
          f"rapport donne **{_b_ouvr:.1f} %**, soit **{_b_iso - _b_ouvr:+.1f} pt** — l'écart "
          f"correspond exactement aux surcharges du bas survenant sur un **jour férié en "
          f"semaine** (comptées « semaine » par le calendrier, « férié » par le type de jour). "
          f"Ce n'est donc pas un artefact d'année : H25 seul suit la même logique "
          f"({_b25_iso:.1f} % calendrier vs {_b25_ouvr:.1f} % type_jour). Ajouter le samedi "
          f"(**{_b_sam:.1f} %**) *dépasse* le 86,6 % : la variante samedi n'explique pas l'écart, "
          f"qui vient bien des fériés. Aucune correction requise — deux définitions cohérentes, "
          f"à citer explicitement.\n")

md.append("\n---\n\n## Métadonnées de reproduction\n")
md.append(f"- Environnement : {VERSIONS}.\n")
md.append(f"- Empreinte parquet vérifiée : `ml_dataset.parquet` SHA256[:8] = **`{h}`** "
          f"(= attendu `{HASH_ATTENDU}`).\n")
md.append(f"- Dossier de sortie : `{OUT}`\n")
md.append(f"- Script : `analysis/tests_section_4_3.py` (lecture seule, sans commit).\n")
md.append(f"- Date d'exécution : {DATE_EXEC}.\n")
md.append("- CSV produits : `c0_couverture_apc.csv`, `t1_wilcoxon.csv`, "
          "`t2_mann_whitney.csv`, `t2_sensibilite_fenetres.csv`, `t2_maxima_locaux.csv`, "
          "`t2_parts_agregees.csv`, `t4_kruskal_wallis.csv`, `t5_wilcoxon_journalier.csv`, "
          "`t5_exposition_surcharge.csv`, "
          "`t5_sensibilite_fenetres.csv`, `t5b_haut_et_raccords.csv`.\n")

(OUT / "resultats_tests_4_3.md").write_text("".join(md), encoding="utf-8")

emit("\n" + "=" * 80)
emit(f"Rapport et CSV écrits dans : {OUT}")
emit(f"Dossier mémoire confirmé : {OUT.parent}")
emit("=" * 80)
