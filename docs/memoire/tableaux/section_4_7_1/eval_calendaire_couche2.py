#!/usr/bin/env python3
"""
eval_calendaire_couche2.py — LOT C, section 4.7.1 : évaluation calendaire de la couche 2.

Ventilation temporelle des points d'opération de la couche 2 sur H25, au grain COURSE,
avec les **seuils calibrés sur H24 INCHANGÉS** (ADR-073). Analyse descriptive post-hoc :
LECTURE SEULE, aucun réentraînement, aucune re-calibration, aucune re-sélection.

Configurations évaluées :
  - pratique de référence (rotations)  — décision humaine d'unité multiple observée ;
  - a′ ∪ plancher                      — point de RÉFÉRENCE d'évaluation (iso-volume, ADR-073) ;
  - c ∪ plancher                       — configuration de DÉPLOIEMENT (ADR-077) ;
  - b (rappel renforcé)                — colonne de CONTEXTE (borne haute de rappel).
Plancher = demande annoncée à J−1 supérieure au seuil de places assises (résa 2e classe > 63).

Découpages :
  1. par mois horaire — 13 mois, les deux décembres distingués (déc. 2024 et déc. 2025) ;
  2. par type de jour (typologie 3 classes du dataset) × segment ;
  3. charge d'alerte quotidienne de la configuration de déploiement.

GARDE-FOUS (STOP si divergence) : empreinte ml_dataset `ba493568` ; périmètre course H25
= 29 222 dont 2 072 surcharges (1 224 haut / 848 bas) ; seuils H24 a′/b/c = 78,99/51,31/64,12 ;
volumes H25 publiés reproduits (418 / 352 / 866 / 2 563).

Sorties :
  docs/memoire/tableaux/section_4_7_1/table_471_couche2_mensuel.csv
  docs/memoire/tableaux/section_4_7_1/table_471_couche2_type_jour_segment.csv
  docs/memoire/tableaux/section_4_7_1/table_471_couche2_charge_alerte.csv
  docs/memoire/tableaux/section_4_7_1/table_471_couche2_charge_alerte_par_jour.csv
  docs/memoire/tableaux/section_4_7_1/eval_calendaire_couche2.md
  docs/memoire/figures/section_4_7_1/fig_couche2_precision_rappel_mensuels.png

Exécution : python3 docs/memoire/tableaux/section_4_7_1/eval_calendaire_couche2.py
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")   # PNG byte-reproductible

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FIG_DIR = ROOT / "docs/memoire/figures/section_4_7_1"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from couche2 import blocs, decision    # noqa: E402

ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
HASH_CANONIQUE = "ba493568"
CALIB_JSON = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"
SEUIL = 63

# Ordre d'affichage figé des configurations.
CONF_REFERENCE = "pratique de référence (rotations)"
CONF_A_PLANCHER = "a′ ∪ plancher"
CONF_C_PLANCHER = "c ∪ plancher"
CONF_B = "b (rappel renforcé)"
ORDRE_CONF = [CONF_REFERENCE, CONF_A_PLANCHER, CONF_C_PLANCHER, CONF_B]

# Volumes H25 publiés (ADR-073 / ADR-077) — garde-fous de reproduction.
ANCRAGES_VOLUME = {CONF_REFERENCE: 418, CONF_A_PLANCHER: 352,
                   CONF_C_PLANCHER: 866, CONF_B: 2563}

SEUILS_H24_ATTENDUS = {"a_iso_volume": 78.99, "b_rappel_renforce": 51.31,
                       "c_haute_precision": 64.12}

ORDRE_TYPE_JOUR = ["ouvrable", "samedi", "dimanche_ferie"]
LIB_TYPE_JOUR = {"ouvrable": "jour ouvrable", "samedi": "samedi",
                 "dimanche_ferie": "dimanche ou jour férié"}

MOIS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc."]

# Couleurs (Okabe-Ito + neutre achromatique pour le repère de prévalence).
COL_DEPLOIEMENT = "#E69F00"     # orange — règle c (identique à la figure PR couche 2)
COL_REFERENCE = "#000000"       # noir — pratique humaine
COL_PREVALENCE = "#999999"      # gris neutre — repère discret


# ══════════════════════════════════════════════════════════════════════════════
# 0. Garde-fous et chargement
# ══════════════════════════════════════════════════════════════════════════════
def charger_taus() -> dict:
    calib = json.loads(CALIB_JSON.read_text())
    r = calib["regles_deployables"]
    taus = {k: float(r[k]["seuil"]) for k in SEUILS_H24_ATTENDUS}
    for k, v in SEUILS_H24_ATTENDUS.items():
        if abs(taus[k] - v) > 0.01:
            raise RuntimeError(f"STOP : seuil H24 {k} = {taus[k]:.4f} != {v} attendu.")
    return taus


def calendrier_h25() -> pd.DataFrame:
    """Table jour → (mois horaire, libellé de mois, type de jour). Un seul enregistrement
    par date : le script échoue si une date porte deux valeurs calendaires."""
    cols = ["horaire_annee_horaire", "base_date", "cal_mois_horaire",
            "cal_annee_civile", "cal_mois", "cal_type_jour_3classes"]
    df = pd.read_parquet(ML_DATASET, columns=cols)
    h = df[df["horaire_annee_horaire"] == "H25"].copy()
    h["date"] = pd.to_datetime(h["base_date"]).dt.normalize()
    cal = h.groupby("date").agg(
        mois_horaire=("cal_mois_horaire", "unique"),
        annee_civile=("cal_annee_civile", "unique"),
        mois_civil=("cal_mois", "unique"),
        type_jour=("cal_type_jour_3classes", "unique")).reset_index()
    for c in ("mois_horaire", "annee_civile", "mois_civil", "type_jour"):
        multi = cal[c].map(len) > 1
        if multi.any():
            raise RuntimeError(f"STOP : {int(multi.sum())} date(s) avec plusieurs valeurs de {c}.")
        cal[c] = cal[c].map(lambda v: v[0])
    cal["mois_horaire"] = cal["mois_horaire"].astype(int)
    cal["mois_libelle"] = [f"{MOIS_FR[int(m) - 1]} {int(a)}"
                           for m, a in zip(cal["mois_civil"], cal["annee_civile"])]
    n_mois = cal["mois_horaire"].nunique()
    if n_mois != 13:
        raise RuntimeError(f"STOP : {n_mois} mois horaires H25 != 13 attendus.")
    # les deux décembres doivent être distingués par le mois horaire
    dec = cal[cal["mois_civil"] == 12]["mois_horaire"].unique()
    if sorted(dec.tolist()) != [1, 13]:
        raise RuntimeError(f"STOP : les deux décembres H25 devraient porter les mois "
                           f"horaires 1 et 13, obtenu {sorted(dec.tolist())}.")
    tj = set(cal["type_jour"].unique()) - set(ORDRE_TYPE_JOUR)
    if tj:
        raise RuntimeError(f"STOP : types de jour inattendus -> {sorted(tj)}")
    return cal[["date", "mois_horaire", "mois_libelle", "type_jour"]]


def jeu_de_decision(taus: dict) -> tuple[pd.DataFrame, dict]:
    """Jeu de décision H25 au grain course, augmenté du calendrier et des masques de
    recommandation. Les seuils H24 ne sont PAS recalculés."""
    blocs.assert_canonical_dataset(ML_DATASET, HASH_CANONIQUE)
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)
    h25 = ds[ds["annee"] == "H25"].copy()
    h25["date"] = pd.to_datetime(h25["date"]).dt.normalize()

    cal = calendrier_h25()
    n_avant = len(h25)
    h25 = h25.merge(cal, on="date", how="left")
    if len(h25) != n_avant or h25["mois_horaire"].isna().any():
        raise RuntimeError("STOP : jointure calendaire incomplète sur les courses H25.")

    score, resa = h25["score"].values, h25["resa2c"].values
    plancher = resa > SEUIL
    h25[CONF_REFERENCE] = h25["is_UM"].values.astype(bool)
    h25[CONF_A_PLANCHER] = (score >= taus["a_iso_volume"]) | plancher
    h25[CONF_C_PLANCHER] = (score >= taus["c_haute_precision"]) | plancher
    h25[CONF_B] = score >= taus["b_rappel_renforce"]

    for nom, attendu in ANCRAGES_VOLUME.items():
        obtenu = int(h25[nom].sum())
        if obtenu != attendu:
            raise RuntimeError(f"STOP : volume H25 « {nom} » = {obtenu} != {attendu} publié.")
    return h25, info


# ══════════════════════════════════════════════════════════════════════════════
# 1. Métriques
# ══════════════════════════════════════════════════════════════════════════════
def metriques(sub: pd.DataFrame, conf: str) -> dict:
    reco = sub[conf].values.astype(bool)
    y = sub["label"].values.astype(bool)
    vol = int(reco.sum()); vp = int((reco & y).sum()); pos = int(y.sum()); n = len(sub)
    return {"n_courses": n, "n_surcharges": pos,
            "prevalence": (pos / n) if n else None,
            "volume": vol, "VP": vp, "FP": vol - vp,
            "precision": (vp / vol) if vol else None,
            "rappel": (vp / pos) if pos else None}


def table_mensuelle(h25: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for (mh, lib), sub in h25.groupby(["mois_horaire", "mois_libelle"], sort=True):
        for conf in ORDRE_CONF:
            lignes.append({"mois_horaire": int(mh), "mois": lib, "configuration": conf,
                           "n_jours": int(sub["date"].nunique()), **metriques(sub, conf)})
    df = pd.DataFrame(lignes)
    df["_ordre"] = df["configuration"].map({c: i for i, c in enumerate(ORDRE_CONF)})
    df = df.sort_values(["mois_horaire", "_ordre"]).drop(columns="_ordre")
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(6)
    return df.reset_index(drop=True)


def table_type_jour_segment(h25: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for tj in ORDRE_TYPE_JOUR:
        for seg in ("global", "bas", "haut"):
            sub = h25[h25["type_jour"] == tj]
            if seg != "global":
                sub = sub[sub["segment"] == seg]
            for conf in ORDRE_CONF:
                lignes.append({"type_jour": tj, "type_jour_libelle": LIB_TYPE_JOUR[tj],
                               "segment": seg, "configuration": conf,
                               "n_jours": int(sub["date"].nunique()), **metriques(sub, conf)})
    df = pd.DataFrame(lignes)
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(6)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 2. Charge d'alerte quotidienne (configuration de déploiement)
# ══════════════════════════════════════════════════════════════════════════════
def charge_alerte(h25: pd.DataFrame, conf: str = CONF_C_PLANCHER
                  ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nombre de recommandations par jour de service. Le dénominateur est l'ensemble des
    jours PRÉSENTS dans le périmètre iso (une journée sans course appariée n'existe pas)."""
    g = h25.assign(
        _reco=h25[conf].values.astype(bool),
        _lab=h25["label"].values.astype(bool),
        _vp=(h25[conf].values.astype(bool) & h25["label"].values.astype(bool)))
    par_jour = g.groupby(["date", "type_jour"], as_index=False).agg(
        n_courses=("_lab", "size"), n_recommandations=("_reco", "sum"),
        n_surcharges=("_lab", "sum"), VP=("_vp", "sum"))
    for c in ("n_courses", "n_recommandations", "n_surcharges", "VP"):
        par_jour[c] = par_jour[c].astype(int)

    def stats(sub: pd.DataFrame, libelle: str) -> dict:
        v = sub["n_recommandations"].values
        return {"perimetre": libelle, "n_jours": int(len(sub)),
                "total_recommandations": int(v.sum()),
                "moyenne": float(np.mean(v)) if len(v) else None,
                "mediane": float(np.median(v)) if len(v) else None,
                "p95": float(np.percentile(v, 95)) if len(v) else None,
                "max": int(v.max()) if len(v) else None,
                "min": int(v.min()) if len(v) else None,
                "n_jours_a_zero": int((v == 0).sum()),
                "part_jours_a_zero": float((v == 0).mean()) if len(v) else None}

    lignes = [stats(par_jour, "H25 (tous les jours de service)")]
    for tj in ORDRE_TYPE_JOUR:
        lignes.append(stats(par_jour[par_jour["type_jour"] == tj], LIB_TYPE_JOUR[tj]))
    resume = pd.DataFrame(lignes)
    num = [c for c in resume.columns if resume[c].dtype.kind == "f"]
    resume[num] = resume[num].round(4)
    par_jour = par_jour.sort_values("date").reset_index(drop=True)
    return resume, par_jour


# ══════════════════════════════════════════════════════════════════════════════
# 3. Figure — précision et rappel mensuels
# ══════════════════════════════════════════════════════════════════════════════
MOIS_HORAIRES_PARTIELS = (1, 13)   # les deux décembres : H25 court du 15 déc. au 13 déc.


def bornes_mois_partiels(h25: pd.DataFrame) -> str:
    """Libellé des plages couvertes par les deux mois horaires partiels, DÉRIVÉ des
    dates réellement présentes (jamais écrit en dur) : « 15-31 déc. 2024, 1-13 déc. 2025 »."""
    morceaux = []
    for mh in MOIS_HORAIRES_PARTIELS:
        d = h25.loc[h25["mois_horaire"] == mh, "date"]
        if d.empty:
            raise RuntimeError(f"STOP : aucun jour pour le mois horaire partiel {mh}.")
        d0, d1 = pd.Timestamp(d.min()), pd.Timestamp(d.max())
        if (d0.month, d0.year) != (d1.month, d1.year):
            raise RuntimeError(f"STOP : le mois horaire {mh} chevauche deux mois civils.")
        morceaux.append(f"{d0.day}-{d1.day} {MOIS_FR[d0.month - 1]} {d0.year}")
    return ", ".join(morceaux)


def figure_mensuelle(mens: pd.DataFrame, note_partiels: str) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import figures_style as fs

    fs.apply_style()
    ordre = (mens[["mois_horaire", "mois"]].drop_duplicates()
             .sort_values("mois_horaire").reset_index(drop=True))
    x = np.arange(len(ordre))

    def serie(conf: str, col: str) -> np.ndarray:
        d = (mens[mens["configuration"] == conf]
             .set_index("mois_horaire").loc[ordre["mois_horaire"], col])
        return 100.0 * d.values.astype("float64")

    prev = serie(CONF_C_PLANCHER, "prevalence")     # identique pour toute configuration

    fig, axes = plt.subplots(2, 1, figsize=(8.4, 7.4), sharex=True)
    for ax, col, ylab, lettre in [(axes[0], "precision", "Précision (%)", "a"),
                                  (axes[1], "rappel", "Rappel (%)", "b")]:
        ax.plot(x, serie(CONF_C_PLANCHER, col), color=COL_DEPLOIEMENT, marker="o",
                markersize=5, lw=1.8,
                label="Configuration de déploiement (règle c et plancher de réservations)")
        ax.plot(x, serie(CONF_REFERENCE, col), color=COL_REFERENCE, marker="D",
                markersize=4.5, lw=1.4, linestyle="--",
                label="Pratique de référence (unités multiples décidées)")
        ax.plot(x, prev, color=COL_PREVALENCE, marker=".", markersize=5, lw=1.0,
                linestyle=":", label="Prévalence de surcharge (repère)")
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 20))
        fs.lettre_panneau(ax, lettre)
        fs.finalize(ax, ylabel=ylab)

    fs.finalize(axes[1], xlabel="Mois horaire", periode="H25")
    axes[1].set_xticks(x)
    # Les deux décembres sont des mois horaires partiels : repérés par un astérisque,
    # explicité par la note de bas de figure.
    etiquettes = [f"{lib}*" if mh in MOIS_HORAIRES_PARTIELS else lib
                  for mh, lib in zip(ordre["mois_horaire"], ordre["mois"])]
    axes[1].set_xticklabels(etiquettes, rotation=45, ha="right")
    # Légende hors des panneaux : les deux courbes occupent toute la hauteur utile.
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=1, frameon=True)
    fig.text(0.012, 0.008, f"* mois horaires partiels ({note_partiels})",
             ha="left", va="bottom", fontsize=7.5, color="#555555")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_couche2_precision_rappel_mensuels.png"
    fs.save(fig, out)
    plt.close(fig)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 4. Rapport
# ══════════════════════════════════════════════════════════════════════════════
def fr(x, nd=1, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    v = 100 * x if pct else x
    s = f"{v:.{nd}f}".replace(".", ",")
    return s + (" %" if pct else "")


def mil(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    return f"{int(n):,}".replace(",", " ")


def md_mensuel(mens: pd.DataFrame, confs: list) -> list:
    ordre = (mens[["mois_horaire", "mois"]].drop_duplicates()
             .sort_values("mois_horaire"))
    entete = ["Mois", "Courses", "Surcharges", "Prévalence"]
    for c in confs:
        entete += [f"{c} — vol.", f"{c} — VP", f"{c} — préc.", f"{c} — rappel"]
    L = ["| " + " | ".join(entete) + " |",
         "|" + "---|" * len(entete)]
    for _, o in ordre.iterrows():
        bloc = mens[mens["mois_horaire"] == o["mois_horaire"]]
        ref = bloc.iloc[0]
        cells = [o["mois"], mil(ref["n_courses"]), mil(ref["n_surcharges"]),
                 fr(ref["prevalence"], 1, pct=True)]
        for c in confs:
            r = bloc[bloc["configuration"] == c].iloc[0]
            cells += [mil(r["volume"]), mil(r["VP"]),
                      fr(r["precision"], 1, pct=True), fr(r["rappel"], 1, pct=True)]
        L.append("| " + " | ".join(cells) + " |")
    return L


def ecrire_rapport(h25: pd.DataFrame, info: dict, taus: dict, mens: pd.DataFrame,
                   tjs: pd.DataFrame, alerte: pd.DataFrame, fig: Path) -> Path:
    L = []
    A = L.append
    A("# Évaluation calendaire de la couche 2 — H25 (section 4.7.1)")
    A("")
    A("**Lot C — analyse descriptive post-hoc, lecture seule.** Grain course, périmètre iso H25,")
    A("**seuils calibrés sur H24 inchangés** (ADR-073). Aucun réentraînement, aucune")
    A("re-calibration, aucune re-sélection.")
    A("")
    A("| Garde-fou | Valeur |")
    A("|---|---|")
    A(f"| Empreinte `ml_dataset.parquet` | `{HASH_CANONIQUE}` |")
    A(f"| Périmètre H25 (courses) | {mil(info['n_h25'])} |")
    A(f"| Surcharges (au moins un tronçon > 63) | {mil(info['positives_h25'])} "
      f"({mil(info['positives_haut'])} haut / {mil(info['positives_bas'])} bas) |")
    A(f"| Seuils H24 figés a′ / b / c | {fr(taus['a_iso_volume'], 2)} / "
      f"{fr(taus['b_rappel_renforce'], 2)} / {fr(taus['c_haute_precision'], 2)} |")
    A("| Volumes H25 reproduits | 418 (référence) / 352 (a′∪plancher) / 866 (c∪plancher) / 2 563 (b) |")
    A(f"| Jours de service couverts | {h25['date'].nunique()} |")
    A("")
    A("Configurations : **pratique de référence** (unités multiples effectivement décidées),")
    A("**a′ ∪ plancher** (point de référence d'évaluation, iso-volume), **c ∪ plancher**")
    A("(configuration de déploiement, ADR-077) et **b** (rappel renforcé, colonne de contexte).")
    A("Plancher = réservation 2e classe annoncée à J−1 supérieure à 63.")
    A("")

    A("## 1. Ventilation par mois horaire (13 mois, deux décembres distingués)")
    A("")
    A("Les deux décembres sont des mois horaires **partiels** : le mois horaire 1 court du")
    A("15 au 31 décembre 2024, le mois horaire 13 du 1er au 13 décembre 2025. Leurs volumes")
    A("ne sont donc pas comparables aux onze mois pleins.")
    A("")
    A("### Tableau principal")
    A("")
    L.extend(md_mensuel(mens, [CONF_REFERENCE, CONF_A_PLANCHER, CONF_C_PLANCHER]))
    A("")
    A("### Colonne de contexte — règle b (rappel renforcé)")
    A("")
    L.extend(md_mensuel(mens, [CONF_B]))
    A("")

    A("## 2. Ventilation par type de jour × segment")
    A("")
    A("Typologie 3 classes du dataset. Le segment de course suit la règle canonique (une course")
    A("qui atteint la crémaillère est « haut »).")
    A("")
    for seg in ("global", "bas", "haut"):
        A(f"### Segment {seg}")
        A("")
        A("| Type de jour | Configuration | Jours | Courses | Surcharges | Prévalence | "
          "Volume | VP | Précision | Rappel |")
        A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for tj in ORDRE_TYPE_JOUR:
            for conf in ORDRE_CONF:
                r = tjs[(tjs["type_jour"] == tj) & (tjs["segment"] == seg) &
                        (tjs["configuration"] == conf)].iloc[0]
                A(f"| {LIB_TYPE_JOUR[tj]} | {conf} | {int(r['n_jours'])} | "
                  f"{mil(r['n_courses'])} | {mil(r['n_surcharges'])} | "
                  f"{fr(r['prevalence'], 1, pct=True)} | {mil(r['volume'])} | {mil(r['VP'])} | "
                  f"{fr(r['precision'], 1, pct=True)} | {fr(r['rappel'], 1, pct=True)} |")
        A("")

    A("## 3. Charge d'alerte quotidienne — configuration de déploiement (c ∪ plancher)")
    A("")
    A("Nombre de recommandations émises par jour de service.")
    A("")
    A("| Périmètre | Jours | Total | Moyenne | Médiane | p95 | Max | Jours à 0 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in alerte.iterrows():
        A(f"| {r['perimetre']} | {int(r['n_jours'])} | {mil(r['total_recommandations'])} | "
          f"{fr(r['moyenne'], 2)} | {fr(r['mediane'], 1)} | {fr(r['p95'], 1)} | "
          f"{int(r['max'])} | {int(r['n_jours_a_zero'])} "
          f"({fr(r['part_jours_a_zero'], 1, pct=True)}) |")
    A("")

    A("## 4. Figure")
    A("")
    A(f"`{fig.relative_to(ROOT)}` — précision (a) et rappel (b) mensuels de la configuration")
    A("de déploiement et de la pratique de référence, prévalence mensuelle en repère discret.")
    A("Style maison (Okabe-Ito, 300 DPI, sans titre embarqué), horodatage figé.")
    A("")

    A("## 5. Constats factuels")
    A("")
    L.extend(constats(h25, mens, tjs, alerte))
    A("")
    out = HERE / "eval_calendaire_couche2.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def constats(h25: pd.DataFrame, mens: pd.DataFrame, tjs: pd.DataFrame,
             alerte: pd.DataFrame) -> list:
    """5 à 10 lignes de constats factuels, sans interprétation. Tous les nombres sont
    recalculés depuis les tables produites."""
    C = []
    dep = mens[mens["configuration"] == CONF_C_PLANCHER].set_index("mois_horaire")
    ref = mens[mens["configuration"] == CONF_REFERENCE].set_index("mois_horaire")

    p_min, p_max = dep["precision"].min(), dep["precision"].max()
    m_min = dep["precision"].idxmin(); m_max = dep["precision"].idxmax()
    C.append(f"1. Sur les 13 mois horaires, la précision mensuelle de `c ∪ plancher` varie de "
             f"{fr(p_min, 1, pct=True)} ({dep.loc[m_min, 'mois']}) à {fr(p_max, 1, pct=True)} "
             f"({dep.loc[m_max, 'mois']}).")

    r_min, r_max = dep["rappel"].min(), dep["rappel"].max()
    rm_min, rm_max = dep["rappel"].idxmin(), dep["rappel"].idxmax()
    C.append(f"2. Le rappel mensuel de `c ∪ plancher` varie de {fr(r_min, 1, pct=True)} "
             f"({dep.loc[rm_min, 'mois']}) à {fr(r_max, 1, pct=True)} ({dep.loc[rm_max, 'mois']}).")

    pd_dep = pd.to_numeric(dep["precision"], errors="coerce")
    pd_ref = pd.to_numeric(ref["precision"], errors="coerce")
    defini = pd_dep.notna() & pd_ref.notna()
    n_dep_sup = int((pd_dep[defini] > pd_ref[defini]).sum())
    n_comp = int(defini.sum())
    C.append(f"3. La précision de `c ∪ plancher` dépasse celle de la pratique de référence sur "
             f"{n_dep_sup} des {n_comp} mois où les deux sont définies ; "
             f"sur l'année, {fr(mens_total(mens, CONF_C_PLANCHER, 'precision'), 1, pct=True)} "
             f"contre {fr(mens_total(mens, CONF_REFERENCE, 'precision'), 1, pct=True)}.")

    prev = dep["prevalence"]
    C.append(f"4. La prévalence mensuelle de surcharge au grain course va de "
             f"{fr(prev.min(), 1, pct=True)} ({dep.loc[prev.idxmin(), 'mois']}) à "
             f"{fr(prev.max(), 1, pct=True)} ({dep.loc[prev.idxmax(), 'mois']}).")

    lignes_tj = []
    for tj in ORDRE_TYPE_JOUR:
        r = tjs[(tjs["type_jour"] == tj) & (tjs["segment"] == "global") &
                (tjs["configuration"] == CONF_C_PLANCHER)].iloc[0]
        lignes_tj.append(f"{LIB_TYPE_JOUR[tj]} {fr(r['precision'], 1, pct=True)} / "
                         f"{fr(r['rappel'], 1, pct=True)}")
    C.append(f"5. Par type de jour, `c ∪ plancher` affiche en précision / rappel : "
             + " ; ".join(lignes_tj) + ".")

    lignes_ref = []
    for tj in ORDRE_TYPE_JOUR:
        r = tjs[(tjs["type_jour"] == tj) & (tjs["segment"] == "global") &
                (tjs["configuration"] == CONF_REFERENCE)].iloc[0]
        lignes_ref.append(f"{LIB_TYPE_JOUR[tj]} {fr(r['precision'], 1, pct=True)} / "
                          f"{fr(r['rappel'], 1, pct=True)}")
    C.append(f"6. Sur les mêmes découpages, la pratique de référence affiche : "
             + " ; ".join(lignes_ref) + ".")

    hb = []
    for seg in ("bas", "haut"):
        r = tjs[(tjs["type_jour"] == "dimanche_ferie") & (tjs["segment"] == seg) &
                (tjs["configuration"] == CONF_C_PLANCHER)].iloc[0]
        hb.append(f"{seg} {fr(r['precision'], 1, pct=True)} / {fr(r['rappel'], 1, pct=True)}")
    C.append(f"7. Les dimanches et jours fériés, `c ∪ plancher` sépare ainsi les segments "
             f"(précision / rappel) : " + " ; ".join(hb) + ".")

    we = []
    for tj in ("samedi", "dimanche_ferie"):
        r = tjs[(tjs["type_jour"] == tj) & (tjs["segment"] == "global") &
                (tjs["configuration"] == CONF_A_PLANCHER)].iloc[0]
        we.append(f"{LIB_TYPE_JOUR[tj]} {int(r['volume'])} recommandation(s) sur "
                  f"{int(r['n_jours'])} jours (rappel {fr(r['rappel'], 1, pct=True)})")
    C.append(f"8. Le point de référence `a′ ∪ plancher` n'émet presque rien hors semaine : "
             + " ; ".join(we) + ".")

    a = alerte.iloc[0]
    C.append(f"9. La charge d'alerte de `c ∪ plancher` est de {fr(a['moyenne'], 2)} "
             f"recommandations par jour en moyenne (médiane {fr(a['mediane'], 1)}, "
             f"p95 {fr(a['p95'], 1)}, maximum {int(a['max'])}), sur "
             f"{int(a['n_jours'])} jours de service ; {int(a['n_jours_a_zero'])} jours "
             f"({fr(a['part_jours_a_zero'], 1, pct=True)}) sans aucune recommandation.")

    b = mens[mens["configuration"] == CONF_B]
    C.append(f"10. En colonne de contexte, la règle b émet {mil(b['volume'].sum())} "
             f"recommandations sur l'année, pour une précision de "
             f"{fr(mens_total(mens, CONF_B, 'precision'), 1, pct=True)} et un rappel de "
             f"{fr(mens_total(mens, CONF_B, 'rappel'), 1, pct=True)}.")
    return C


def mens_total(mens: pd.DataFrame, conf: str, quoi: str):
    """Métrique agrégée sur l'année, recalculée depuis les effectifs (pas une moyenne
    de taux mensuels)."""
    d = mens[mens["configuration"] == conf]
    vp, vol, pos = int(d["VP"].sum()), int(d["volume"].sum()), int(d["n_surcharges"].sum())
    if quoi == "precision":
        return (vp / vol) if vol else None
    if quoi == "rappel":
        return (vp / pos) if pos else None
    raise ValueError(quoi)


# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 78)
    print("LOT C — évaluation calendaire de la couche 2 (H25, grain course)")
    print("=" * 78)
    taus = charger_taus()
    print(f"seuils H24 figés : a′={taus['a_iso_volume']:.2f} "
          f"b={taus['b_rappel_renforce']:.2f} c={taus['c_haute_precision']:.2f} — OK")
    h25, info = jeu_de_decision(taus)
    print(f"périmètre H25 : {info['n_h25']:,} courses, {info['positives_h25']:,} surcharges "
          f"({info['positives_haut']} haut / {info['positives_bas']} bas) — ancrages OK")
    print(f"volumes reproduits : " +
          " ".join(f"{k.split(' ')[0]}={int(h25[k].sum())}" for k in ORDRE_CONF))

    mens = table_mensuelle(h25)
    tjs = table_type_jour_segment(h25)
    alerte, par_jour = charge_alerte(h25)
    fig = figure_mensuelle(mens, bornes_mois_partiels(h25))

    HERE.mkdir(parents=True, exist_ok=True)
    fichiers = []
    for df, nom in [(mens, "table_471_couche2_mensuel.csv"),
                    (tjs, "table_471_couche2_type_jour_segment.csv"),
                    (alerte, "table_471_couche2_charge_alerte.csv"),
                    (par_jour, "table_471_couche2_charge_alerte_par_jour.csv")]:
        p = HERE / nom
        df.to_csv(p, index=False)
        fichiers.append(p)
    fichiers.append(ecrire_rapport(h25, info, taus, mens, tjs, alerte, fig))
    fichiers.append(fig)

    print("\n── Mensuel, configuration de déploiement (c ∪ plancher) ──")
    for _, r in mens[mens["configuration"] == CONF_C_PLANCHER].iterrows():
        print(f"  {r['mois']:>11} courses={int(r['n_courses']):>5} surch={int(r['n_surcharges']):>4} "
              f"prev={fr(r['prevalence'],1,pct=True):>7} vol={int(r['volume']):>4} "
              f"VP={int(r['VP']):>4} P={fr(r['precision'],1,pct=True):>7} "
              f"R={fr(r['rappel'],1,pct=True):>7}")
    print("\n── Type de jour × segment (global), c ∪ plancher ──")
    for _, r in tjs[(tjs["segment"] == "global") &
                    (tjs["configuration"] == CONF_C_PLANCHER)].iterrows():
        print(f"  {LIB_TYPE_JOUR[r['type_jour']]:>22} vol={int(r['volume']):>4} "
              f"P={fr(r['precision'],1,pct=True):>7} R={fr(r['rappel'],1,pct=True):>7}")
    print("\n── Charge d'alerte quotidienne (c ∪ plancher) ──")
    for _, r in alerte.iterrows():
        print(f"  {r['perimetre']:>34} jours={int(r['n_jours']):>3} moy={fr(r['moyenne'],2):>6} "
              f"med={fr(r['mediane'],1):>5} p95={fr(r['p95'],1):>5} max={int(r['max']):>3} "
              f"zéro={int(r['n_jours_a_zero']):>3}")
    print()
    for f in fichiers:
        print(f"  [OK] {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
