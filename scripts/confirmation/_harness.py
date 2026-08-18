#!/usr/bin/env python3
"""
_harness.py — socle commun de la suite de confirmation (scripts/confirmation/).

Discipline (feu vert 2026-07-16, modele + dataset GELES, ADR-076) :
  - le dataset (`ba493568`) et les modeles (`e4ddfccd`/`df6a11c5`) sont FIGES ;
    la suite EVALUE, elle ne selectionne rien, ne modifie aucun ADR, dataset ou
    modele canonique ;
  - assert sha256[:8](ml_dataset) == "ba493568" (via blocs.assert_canonical_dataset) ;
  - seed 42 ; threads numeriques epingles a 1 (contrat ADR-076, AVANT tout import
    numerique : chaque script cNN pose le pinning en tete, ce module le repose) ;
  - Split C standard : train = H22 (hors Gilamont, BPUIC 8501260) + H23 + H24 ;
    test = H25 via `horaire_annee_horaire` ;
  - metriques au format preenregistre (protocole phase 4) : R2 (+ IC bootstrap
    1000 iterations seed 42), MAE, MAE>63, biais>63, PR-AUC seuil 63, prevalence,
    effectifs ; ventilation bas/haut/global quand pertinent ;
  - une sortie JSON par script sous outputs/confirmation/, prefixee cNN_ ;
  - chaque JSON porte un bloc `meta` (created_at, hash dataset, hashes modeles si
    charges, n_train, n_test, h25_contact, h25_version).

Invariance inter-generations (416bb90b -> ba493568) : seules les donnees H25 ont
change (features narcisses, nulles par erreur sur H25 ; train H22-H24 identique,
modeles canoniques byte-identiques). Consequence outillee ici : tout reentrainement
158f segmente sur Split C DOIT reproduire l'empreinte archivee e4ddfccd/df6a11c5
(cf. reproduce_and_hash_segmented) ; une divergence = STOP.

LECTURE SEULE sur les artefacts canoniques : n'ecrit que sous outputs/confirmation/.
"""
from __future__ import annotations
import os

# Pinning des threads numeriques AVANT tout import numerique (defensif : les scripts
# cNN le posent aussi en tete). Contrat de reproductibilite ADR-076.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import datetime
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (average_precision_score, mean_absolute_error,
                             r2_score)

# ── Chemins canoniques ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import blocs  # noqa: E402  (assert_canonical_dataset canonique)

ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
FEAT_JSON = ROOT / "outputs/couche2/features_158f_sans_simba.json"
MODEL_DIR = ROOT / "models/enrichi_seg"
METADATA = MODEL_DIR / "enrichi_seg_metadata.json"
OUT_DIR = ROOT / "outputs/confirmation"

# ── Constantes gelees ───────────────────────────────────────────────────────────
HASH = "ba493568"                        # sha256[:8] ml_dataset (gel v2, ADR-076)
SEED = 42
SEUIL = 63                               # places assises 2C (ADR-060)
GILAMONT_BPUIC = 8501260                 # troncons exclus de H22 (Split C, ADR-065)
N_BOOT = 1000                            # IC bootstrap (protocole phase 4)

# Empreintes des modeles canoniques figes (couche 1, ADR-076)
HASH_MODEL_BAS, HASH_MODEL_HAUT = "e4ddfccd", "df6a11c5"

# Ancrages de volumetrie (STOP si un ecart apparait)
N_TRAIN_SPLIT_C = 801282
N_TEST_H25 = 309252
N_H25_BAS = 229747
N_H25_HAUT = 79505

# Hyperparametres canoniques couche 1 (ADR-052, robustesse ADR-071 ; iso-protocole)
XGB_PARAMS = dict(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    objective="reg:squarederror", tree_method="hist",
    random_state=SEED, enable_categorical=True, verbosity=0,
)


# ── Utilitaires de hash / IO ────────────────────────────────────────────────────
def sha8(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def assert_dataset() -> str:
    """Garde-fou dur (reutilise blocs.assert_canonical_dataset) : le monde de donnees
    est bien le canonique gel v2 ba493568. RuntimeError sinon."""
    return blocs.assert_canonical_dataset(ML_DATASET, HASH)


def load_features_158() -> list:
    feats = json.loads(FEAT_JSON.read_text())["features"]
    assert len(feats) == 158, f"attendu 158 features, obtenu {len(feats)}"
    return feats


def load_dataset() -> pd.DataFrame:
    return pd.read_parquet(ML_DATASET)


def write_json(name: str, payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


# ── Split C + preparation des features ──────────────────────────────────────────
def split_c(df: pd.DataFrame):
    """Split C standard (ADR-065) : train = H22 hors Gilamont + H23 + H24 ; test = H25.
    Verifie les ancrages de volumetrie (STOP si ecart)."""
    h22 = df[df["horaire_annee_horaire"] == "H22"]
    gil = ((h22["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
           (h22["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC))
    train = pd.concat([h22[~gil], df[df["horaire_annee_horaire"].isin(["H23", "H24"])]],
                      ignore_index=True)
    test = df[df["horaire_annee_horaire"] == "H25"].copy()
    if len(train) != N_TRAIN_SPLIT_C:
        raise RuntimeError(f"STOP Split C : n_train={len(train)} != {N_TRAIN_SPLIT_C} attendu.")
    if len(test) != N_TEST_H25:
        raise RuntimeError(f"STOP Split C : n_test H25={len(test)} != {N_TEST_H25} attendu.")
    return train, test


def prep_X(d: pd.DataFrame, feats: list) -> pd.DataFrame:
    """Prep canonique (identique q_all_v18 / phase4) : object|string -> category ;
    Int|UInt -> float64. Preserve l'ordre `feats`."""
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X


def y_of(d: pd.DataFrame) -> np.ndarray:
    return d["target_voyageurs_2eme_classe"].values.astype("float64")


# ── Metriques preenregistrees ───────────────────────────────────────────────────
def r2_ci(y: np.ndarray, p: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED):
    """IC95 bootstrap du R2 (protocole phase 4 : 1000 iterations, seed 42)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[i] = r2_score(y[idx], p[idx])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def seg_metrics(y: np.ndarray, p: np.ndarray, with_ci: bool = True) -> dict:
    """Metriques regression au format preenregistre (identique phase4.seg_metrics)."""
    y = np.asarray(y, dtype="float64"); p = np.asarray(p, dtype="float64")
    gt = y > SEUIL
    if with_ci:
        lo, hi = r2_ci(y, p)
    else:
        lo = hi = None
    return {
        "n_obs": int(len(y)), "r2": float(r2_score(y, p)),
        "r2_ci_lo": lo, "r2_ci_hi": hi,
        "mae": float(mean_absolute_error(y, p)),
        "mae_gt63": float(np.mean(np.abs(p[gt] - y[gt]))) if gt.any() else None,
        "bias_gt63": float(np.mean(p[gt] - y[gt])) if gt.any() else None,
        "pr_auc": float(average_precision_score(gt.astype(int), p)) if gt.any() else None,
        "prevalence": float(gt.mean()), "n_gt63": int(gt.sum()),
    }


def metrics_by_segment(test: pd.DataFrame, pred: np.ndarray, with_ci: bool = True) -> dict:
    """Ventilation bas/haut/global sur H25 (test), pred alignee sur l'ordre de `test`."""
    y = y_of(test)
    seg = test["spatial_segment"].values
    out = {}
    for s in ("bas", "haut"):
        m = seg == s
        out[s] = seg_metrics(y[m], pred[m], with_ci)
    out["global"] = seg_metrics(y, pred, with_ci)
    return out


# ── Entrainement (iso-protocole) ────────────────────────────────────────────────
def _fit(params: dict, Xtr, ytr):
    m = xgb.XGBRegressor(**params)
    m.fit(Xtr, ytr)
    return m


def train_global(train, test, feats, params=XGB_PARAMS):
    """Un XGBoost GLOBAL (non segmente). Retourne (pred_h25 alignee test, model)."""
    m = _fit(params, prep_X(train, feats), y_of(train))
    pred = m.predict(prep_X(test, feats)).astype("float64")
    return pred, m


def train_segmented(train, test, feats, params=XGB_PARAMS):
    """Deux XGBoost segmentes (bas, haut). Retourne (pred_h25 alignee test, {seg: model})."""
    pred = np.empty(len(test), dtype="float64")
    models = {}
    for seg in ("bas", "haut"):
        mtr = train[train["spatial_segment"] == seg]
        mte = test[test["spatial_segment"] == seg]
        m = _fit(params, prep_X(mtr, feats), y_of(mtr))
        pred[(test["spatial_segment"] == seg).values] = m.predict(prep_X(mte, feats)).astype("float64")
        models[seg] = m
    return pred, models


def load_frozen_models() -> dict:
    """Charge les deux modeles couche 1 GELES, en verifiant leur empreinte canonique."""
    models = {}
    for seg, exp in (("bas", HASH_MODEL_BAS), ("haut", HASH_MODEL_HAUT)):
        f = MODEL_DIR / f"enrichi_seg_{seg}_ba493568.json"
        h = sha8(f)
        if h != exp:
            raise RuntimeError(f"STOP : empreinte modele {seg} {h} != {exp} (couche 1 non figee).")
        m = xgb.XGBRegressor(); m.load_model(str(f))
        models[seg] = m
    return models


def frozen_predict(test: pd.DataFrame, feats: list, models: dict | None = None) -> np.ndarray:
    """Predictions des modeles GELES sur `test`, alignees sur son ordre (grain troncon)."""
    if models is None:
        models = load_frozen_models()
    pred = np.empty(len(test), dtype="float64")
    for seg in ("bas", "haut"):
        mask = (test["spatial_segment"] == seg).values
        pred[mask] = models[seg].predict(prep_X(test[mask], feats)).astype("float64")
    return pred


def reproduce_and_hash_segmented(models: dict) -> dict:
    """Sauve chaque modele segmente dans un fichier temporaire, calcule son sha256[:8]
    et le compare a l'empreinte canonique (e4ddfccd / df6a11c5). Ne persiste rien sous
    models/ (canoniques intacts). Format : bloc `model_reproduction` du protocole."""
    expected = {"bas": HASH_MODEL_BAS, "haut": HASH_MODEL_HAUT}
    out = {}
    for seg, m in models.items():
        with tempfile.NamedTemporaryFile(suffix=".json", delete=True) as tf:
            m.save_model(tf.name)
            h = sha8(Path(tf.name))
        out[seg] = {"archived": expected[seg], "retrained": h, "identical": (h == expected[seg])}
    out["all_identical"] = all(v["identical"] for v in out.values())
    return out


# ── Bloc meta commun ────────────────────────────────────────────────────────────
def meta_block(models_loaded: bool = False, n_train: int | None = None,
               n_test: int | None = None, extra: dict | None = None) -> dict:
    m = {
        "created_at": now_iso(),
        "dataset": "data/processed/ml_dataset.parquet",
        "dataset_hash_sha256_8": HASH,
        "h25_contact": "post-gel, lecture seule",
        "h25_version": "corrigée narcisses (ba493568)",
        "seed": SEED,
        "threads": os.environ.get("OMP_NUM_THREADS", "?"),
        "split": "C (train = H22 hors Gilamont BPUIC 8501260 + H23 + H24 ; test = H25)",
        "n_train": n_train, "n_test": n_test,
    }
    if models_loaded:
        m["models"] = {
            "bas": {"file": "models/enrichi_seg/enrichi_seg_bas_ba493568.json",
                    "hash_sha256_8_attendu": HASH_MODEL_BAS},
            "haut": {"file": "models/enrichi_seg/enrichi_seg_haut_ba493568.json",
                     "hash_sha256_8_attendu": HASH_MODEL_HAUT},
        }
    if extra:
        m.update(extra)
    return m
