#!/usr/bin/env python3
"""Section 4.5.6 (extension) — Phase 1 : valeurs TreeSHAP signées sur H25.

LECTURE SEULE sur les artefacts gelés (dataset ba493568, modèles e4ddfccd/df6a11c5).
Réutilise STRICTEMENT la configuration TreeSHAP de scripts/confirmation/c08_shap_segments.py :
  booster.predict(DMatrix(X, enable_categorical=True), pred_contribs=True)
  → TreeSHAP EXACT (feature_perturbation = tree_path_dependent, AUCUN background).
Différence avec c08 : on conserve les valeurs SIGNÉES par observation (c08 n'agrège
que mean|SHAP|). On revérifie que mean|SHAP| reproduit c08 au flottant près (garde-fou).

Sorties (CACHE, hors dépôt — écrites dans le scratchpad de session) :
  shap_cache/shap_signed_{bas,haut}.npy   : (n, 158) float32, SHAP signés, ordre `feats`
  shap_cache/meta_{bas,haut}.parquet      : strates + valeurs de variables + biais + pred + cible
  shap_cache/feats_order.json             : ordre canonique des 158 features + empreintes

Déterminisme : threads épinglés à 1 (contrat ADR-076) ; pred_contribs est de toute
façon invariant au nombre de threads (vérifié : max|Δ|=0, identité bit-à-bit 1 vs 8 threads).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402  (socle gelé : hashes, prep_X, load_features_158)

CACHE = Path(os.environ["R356_CACHE"]) if "R356_CACHE" in os.environ else \
    ROOT / "docs" / "memoire" / "verifs" / "section_4_5_6" / "_cache"

# Colonnes de stratification (Phase 2B) + variables des vérifications C1-C8, conservées
# en clair à côté des SHAP pour les lectures conditionnelles et les dependence plots.
STRATA_COLS = [
    "cal_heure_depart", "cal_type_jour_3classes", "cal_mois", "base_date",
    "event_is_ski_ouvert", "event_is_saison_narcisses", "event_is_montreux_jazz",
    "event_is_marche_noel", "event_is_montreux_noel", "event_is_manifestation_riviera",
    "event_n_manifestations_riviera", "event_is_ferie_vaud",
]
VALUE_COLS = [  # valeurs de variables pour SHAP signé vs valeur (C1-C7)
    "vmcv_n_lignes_concurrentes", "vmcv_min_attente_min", "vmcv_delta_attente_min",
    "vmcv_delta_frequence_h",
    "ist_headway_avant_min", "ist_headway_apres_min",
    "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day",
    "meteo_neige_binaire_h",
    "meteo_temperature_h", "meteo_destination_temperature_h",
    "meteo_temperature_max_j", "meteo_destination_temperature_max_j",
    "meteo_ensoleillement_min_h", "meteo_destination_ensoleillement_min_h",
    "meteo_ensol_total_j", "meteo_destination_ensol_total_j",
    "spatial_denivele_troncon_m",
    "spatial_gare_depart_pop_500m_total", "spatial_gare_arrivee_pop_500m_total",
    "spatial_gare_depart_menages_500m_total", "spatial_gare_arrivee_menages_500m_total",
]


def main() -> int:
    t0 = time.time()
    print("=== s01 — SHAP signées H25 (modèles gelés, config c08) ===", flush=True)
    print("dataset:", H.assert_dataset(), flush=True)
    feats = H.load_features_158()

    need = list(dict.fromkeys(feats + ["horaire_annee_horaire", "spatial_segment",
                                       "target_voyageurs_2eme_classe"] + STRATA_COLS + VALUE_COLS))
    h25 = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet", columns=need,
                          filters=[("horaire_annee_horaire", "==", "H25")])
    if len(h25) != H.N_TEST_H25:
        raise RuntimeError(f"STOP : n_test H25 = {len(h25)} != {H.N_TEST_H25}")
    print(f"H25 chargé : {len(h25)} obs | load {time.time()-t0:.1f}s", flush=True)

    CACHE.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for seg, exp in (("bas", H.HASH_MODEL_BAS), ("haut", H.HASH_MODEL_HAUT)):
        mf = H.MODEL_DIR / f"enrichi_seg_{seg}_ba493568.json"
        got = H.sha8(mf)
        if got != exp:
            raise RuntimeError(f"STOP : empreinte modèle {seg} {got} != {exp}")
        hashes[seg] = got
        m = xgb.XGBRegressor(); m.load_model(str(mf))

        sub = h25[h25["spatial_segment"] == seg].reset_index(drop=True)
        X = H.prep_X(sub, feats)[feats]                       # ordre canonique des 158
        dm = xgb.DMatrix(X, enable_categorical=True)
        ts = time.time()
        contribs = m.get_booster().predict(dm, pred_contribs=True)   # (n, 159), col -1 = biais
        pred = m.predict(X).astype("float64")
        shap = contribs[:, :-1]                               # SHAP signés par feature
        bias = contribs[:, -1]
        print(f"[{seg}] n={len(sub)} sha8={got} | SHAP {time.time()-ts:.1f}s", flush=True)

        # Garde-fou : mean|SHAP| doit reproduire c08 au flottant près.
        mabs = np.abs(shap).mean(axis=0)
        frozen = pd.read_csv(ROOT / "outputs/confirmation" / f"c08_shap_ranks_{seg}.csv")
        fz = frozen.set_index("feature")["mean_abs_shap"]
        rc = pd.Series(mabs, index=feats)
        dmax = float((rc - fz.reindex(feats)).abs().max())
        assert dmax < 1e-6, f"reproduction c08 échouée ({seg}) : max|Δ mean|SHAP|| = {dmax:.3e}"
        print(f"  reproduction c08 : max|Δ mean|SHAP|| = {dmax:.3e} (< 1e-6 OK)", flush=True)

        np.save(CACHE / f"shap_signed_{seg}.npy", shap.astype("float32"))
        meta = sub[STRATA_COLS + [c for c in VALUE_COLS if c in sub.columns]].copy()
        meta["_bias"] = bias
        meta["_pred"] = pred
        meta["_target"] = sub["target_voyageurs_2eme_classe"].astype("float64").values
        meta["_segment"] = seg
        meta.to_parquet(CACHE / f"meta_{seg}.parquet", index=False)

    (CACHE / "feats_order.json").write_text(json.dumps({
        "feats": feats, "n_features": len(feats),
        "dataset_hash": H.HASH, "model_hash": hashes,
        "shap_config": "xgboost booster.predict(pred_contribs=True) — TreeSHAP exact, "
                       "feature_perturbation=tree_path_dependent, no background (config c08)",
        "peak_convention": "B — demi-ouverte {6,7,16,17} (repro exacte T5 §4.3.4)",
    }, indent=2, ensure_ascii=False))
    print(f"[OK] cache écrit dans {CACHE} | total {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
