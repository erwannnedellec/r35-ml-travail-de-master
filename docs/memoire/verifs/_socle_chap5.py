#!/usr/bin/env python3
"""
_socle_chap5.py — socle commun des vérifications du chapitre 5 (§5.1, §5.2, §5.4).

Rôle : reconstruire, depuis les SOURCES CANONIQUES et sous garde-fous, le jeu de
décision au grain de la course enrichi des attributs nécessaires aux lectures du
chapitre 5 (type de jour en trois classes, distance de course, strate de charge).

Discipline : LECTURE SEULE stricte.
  - le dataset (`ba493568`), les modèles (`e4ddfccd` / `df6a11c5`) et le menu de
    seuils calibré sur H24 (a′, b, c) sont FIGÉS et seulement relus ;
  - aucun seuil n'est recalculé, réajusté ni sélectionné ici ;
  - les garde-fous d'ancrage de `couche2.decision` (29 222 courses H25, 2 072
    surcharges dont 1 224 HAUT / 848 BAS) sont exécutés à chaque construction.

Le type de jour provient de `cal_type_jour_3classes`, la typologie en trois classes
comportementales du projet (`ouvrable` / `samedi` / `dimanche_ferie`), construite par
`scripts/pipeline/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py`. Elle est
un attribut de la DATE : le socle vérifie qu'elle est bien unique par date avant de la
projeter au grain de la course.
"""
from __future__ import annotations

import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
CALIB_JSON = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"
HASH_DATASET = "ba493568"
HASH_MODEL_BAS, HASH_MODEL_HAUT = "e4ddfccd", "df6a11c5"

SEUIL = 63                       # places assises 2e classe (ADR-060)
TARE_T = 54.2                    # tare d'une unité multiple supplémentaire, tonnes
TARIF_TBKM = 0.06444             # redevance d'utilisation du réseau, CHF par tonne-km
COUT_PAR_KM = TARE_T * TARIF_TBKM        # 3,4926 CHF/km — facteur constant du volet B

TYPES_JOUR = ["ouvrable", "samedi", "dimanche_ferie"]
LIB_TYPE_JOUR = {"ouvrable": "Jour ouvrable", "samedi": "Samedi",
                 "dimanche_ferie": "Dimanche ou jour férié"}
STRATES = {"63-93": (63, 94), "94-165": (94, 166), "166+": (166, np.inf)}


# ── Empreintes et provenance ───────────────────────────────────────────────────
def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def git_commit() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def empreintes() -> dict:
    return {
        "commit": git_commit(),
        "branche": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
                                  capture_output=True, text=True).stdout.strip(),
        "dataset": sha8(ML_DATASET),
        "modele_bas": sha8(ROOT / "models/enrichi_seg/enrichi_seg_bas_ba493568.json"),
        "modele_haut": sha8(ROOT / "models/enrichi_seg/enrichi_seg_haut_ba493568.json"),
        "calibration_H24": sha8(CALIB_JSON),
    }


def seuils() -> dict:
    """Menu de seuils calibré sur H24, RELU tel quel. Aucune recalibration."""
    reg = json.loads(CALIB_JSON.read_text())["regles_deployables"]
    return {"a": reg["a_iso_volume"]["seuil"],
            "b": reg["b_rappel_renforce"]["seuil"],
            "c": reg["c_haute_precision"]["seuil"]}


def fr(n) -> str:
    """Séparateur de milliers par espace (convention typographique du mémoire)."""
    return f"{int(n):,}".replace(",", " ")


# ── Jeu de décision enrichi ────────────────────────────────────────────────────
def build_enrichi() -> pd.DataFrame:
    """Jeu de décision au grain course (H24 + H25), enrichi du type de jour, de la
    distance de course et de la strate de charge. Garde-fous d'ancrage exécutés."""
    h = sha8(ML_DATASET)
    if h != HASH_DATASET:
        raise RuntimeError(f"STOP empreinte dataset {h} != {HASH_DATASET}.")

    ds = decision.build_decision_set()
    decision.assert_perimetre_et_ancrage(ds)          # 29 222 / 2 072 (1 224 / 848)

    src = pd.read_parquet(ML_DATASET, columns=[
        "base_date", "horaire_annee_horaire", "horaire_numero_train",
        "cal_type_jour_3classes", "spatial_distance_km"])
    src = src[src["horaire_annee_horaire"].isin(["H24", "H25"])].copy()
    src["date"] = pd.to_datetime(src["base_date"]).dt.normalize()
    src["numero_train"] = src["horaire_numero_train"].astype("Int64").astype(str)

    # Le type de jour est un attribut de la DATE : contrôle d'unicité avant projection.
    par_date = src.groupby("date")["cal_type_jour_3classes"].agg(["nunique", "first"])
    if int((par_date["nunique"] > 1).sum()) != 0:
        raise RuntimeError("STOP : cal_type_jour_3classes n'est pas unique par date.")
    tj = par_date["first"].rename("type_jour").reset_index()
    inconnus = set(tj["type_jour"]) - set(TYPES_JOUR)
    if inconnus:
        raise RuntimeError(f"STOP : modalités de type de jour inattendues {inconnus}.")

    dist = (src.groupby(["date", "numero_train"])["spatial_distance_km"]
            .sum().rename("dist_km").reset_index())

    n0 = len(ds)
    ds = ds.merge(tj, on="date", how="left").merge(dist, on=["date", "numero_train"], how="left")
    if len(ds) != n0:
        raise RuntimeError(f"STOP : la jonction a modifié le nombre de lignes ({n0} -> {len(ds)}).")
    if ds["type_jour"].isna().any() or ds["dist_km"].isna().any():
        raise RuntimeError("STOP : type de jour ou distance manquant après jonction.")

    ds["strate"] = pd.cut(ds["charge_max"], bins=[63, 94, 166, np.inf],
                          right=False, labels=list(STRATES)).astype(object)
    ds.loc[ds["charge_max"] <= SEUIL, "strate"] = None
    return ds


def h25_de(ds: pd.DataFrame) -> pd.DataFrame:
    return ds[ds["annee"] == "H25"].reset_index(drop=True)


# ── Masques de politiques (seuils FIGÉS, relus du menu H24) ─────────────────────
def masque_plancher(d: pd.DataFrame) -> np.ndarray:
    """Plancher de réservation : réservations 2e classe agrégées à la course par le
    MAXIMUM sur les tronçons, strictement supérieures à 63."""
    return d["resa2c"].values > SEUIL


def masque_score(d: pd.DataFrame, tau: float) -> np.ndarray:
    return d["score"].values >= tau


def masque_pdiff_score(d: pd.DataFrame, s: dict) -> np.ndarray:
    """Volet SCORE de la politique différenciée : c en jour ouvrable, b le samedi,
    b le dimanche et les jours fériés. Seuils inchangés."""
    tj = d["type_jour"].values
    tau = np.where(tj == "ouvrable", s["c"], s["b"])
    return d["score"].values >= tau


# ── Métriques ──────────────────────────────────────────────────────────────────
def confusion(mask: np.ndarray, y: np.ndarray, n_total: int | None = None) -> dict:
    """Matrice de confusion complète + précision, rappel, F1. Effectifs bruts."""
    mask = np.asarray(mask, dtype=bool)
    y = np.asarray(y, dtype=bool)
    n = len(y) if n_total is None else n_total
    vp = int((mask & y).sum())
    fp = int((mask & ~y).sum())
    fn = int((~mask & y).sum())
    vn = int((~mask & ~y).sum())
    vol, pos = vp + fp, vp + fn
    p = (vp / vol) if vol else None
    r = (vp / pos) if pos else None
    f1 = (2 * p * r / (p + r)) if (p and r) else (0.0 if (p is not None and r is not None) else None)
    return {"n_courses": n, "n_surcharges": pos, "volume": vol, "VP": vp, "FP": fp,
            "FN": fn, "VN": vn, "precision": p, "rappel": r, "F1": f1}


def cout_fp(d: pd.DataFrame, mask: np.ndarray) -> dict:
    """Coût des faux positifs, valorisé au facteur constant COUT_PAR_KM (CHF/km)."""
    y = d["label"].values.astype(bool)
    fp = np.asarray(mask, dtype=bool) & ~y
    km = float(d.loc[fp, "dist_km"].sum())
    return {"n_FP": int(fp.sum()), "km_FP": km, "cout_CHF": km * COUT_PAR_KM}


def charge_alerte(d: pd.DataFrame, mask: np.ndarray, dates_reference=None) -> dict:
    """Distribution du nombre de recommandations par jour. Les jours du périmètre sans
    aucune recommandation comptent pour zéro (ils ne sont pas omis de la distribution)."""
    dates = pd.Index(sorted(d["date"].unique())) if dates_reference is None else pd.Index(dates_reference)
    par_jour = (pd.Series(np.asarray(mask, dtype=int), index=d["date"].values)
                .groupby(level=0).sum().reindex(dates, fill_value=0))
    v = par_jour.values.astype(float)
    return {"n_jours": int(len(v)), "total": int(v.sum()), "moyenne": float(v.mean()),
            "mediane": float(np.median(v)), "d9": float(np.percentile(v, 90)),
            "max": int(v.max()), "jours_sans_recommandation": int((v == 0).sum()),
            "_par_jour": par_jour}
