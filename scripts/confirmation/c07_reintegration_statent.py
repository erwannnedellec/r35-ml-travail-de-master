#!/usr/bin/env python3
"""
c07_reintegration_statent.py — test de REINTEGRATION STATENT (emploi), pas un retrait.

CHECKPOINT (rapporte avant execution) : il n'existe AUCUNE colonne prefixee `statent_`
dans ml_dataset.parquet. Les donnees d'emploi STATENT y figurent sous le prefixe spatial_,
en 4 colonnes, TOUTES absentes des 158 features (retrait STATENT, ADR-064) :
  - spatial_gare_depart_emplois_500m_total
  - spatial_gare_depart_emplois_500m_services
  - spatial_gare_arrivee_emplois_500m_total
  - spatial_gare_arrivee_emplois_500m_services

Design (reintegration, symetrique de c06) : 158f (canonique) vs 162f (158 + 4 colonnes emploi).
Deux bras reentraines (Split C, HP canoniques, seed 42, threads=1) :
  - 158f segmente = canonique -> DOIT reproduire e4ddfccd/df6a11c5 (invariance). Divergence = STOP.
  - 162f segmente = 158 + les 4 colonnes emploi STATENT reintegrees.
Delta R2 par segment = 162f - 158f (effet de la REINTEGRATION). Chiffres seuls.

Sortie : outputs/confirmation/c07_reintegration_statent.json.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as H  # noqa: E402

STATENT_COLS = [
    "spatial_gare_depart_emplois_500m_total",
    "spatial_gare_depart_emplois_500m_services",
    "spatial_gare_arrivee_emplois_500m_total",
    "spatial_gare_arrivee_emplois_500m_services",
]
SEGMENTS = ("bas", "haut", "global")


def main() -> int:
    print("=== c07 — reintegration STATENT (158f vs 162f), Split C, ba493568 ===")
    H.assert_dataset()
    feats_158 = H.load_features_158()
    df = H.load_dataset()
    present = [c for c in STATENT_COLS if c in df.columns]
    absent = [c for c in STATENT_COLS if c not in df.columns]
    print(f"  colonnes emploi STATENT presentes : {len(present)}/{len(STATENT_COLS)} {present}")
    assert not absent, f"colonnes emploi STATENT manquantes : {absent}"
    # aucune ne doit deja etre dans les 158
    overlap = [c for c in STATENT_COLS if c in feats_158]
    assert not overlap, f"colonnes STATENT deja dans les 158f : {overlap}"

    feats_162 = feats_158 + STATENT_COLS
    train, test = H.split_c(df)
    print(f"  Split C : train={len(train)} | test H25={len(test)}")

    # -- bras 158f (canonique) : reproduction d'empreinte (GARDE) --
    t0 = time.time()
    pred_158, models_158 = H.train_segmented(train, test, feats_158)
    repro = H.reproduce_and_hash_segmented(models_158)
    dt_158 = time.time() - t0
    print(f"  158f : reproduction empreintes = {repro['all_identical']} ({dt_158:.0f}s)")
    if not repro["all_identical"]:
        payload = {"script": "c07_reintegration_statent.py", "STOP": True,
                   "raison": "le reentrainement 158f segmente NE reproduit PAS e4ddfccd/df6a11c5",
                   "model_reproduction": repro,
                   "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)))}
        H.write_json("c07_reintegration_statent.json", payload)
        print("!" * 72 + "\nSTOP c07 : empreinte 158f non reproduite. Rapport ecrit, arret.\n" + "!" * 72)
        return 1
    metrics_158 = H.metrics_by_segment(test, pred_158)

    # -- bras 162f (158 + 4 colonnes emploi STATENT) --
    t1 = time.time()
    pred_162, _ = H.train_segmented(train, test, feats_162)
    dt_162 = time.time() - t1
    metrics_162 = H.metrics_by_segment(test, pred_162)

    delta_r2_162_moins_158 = {s: metrics_162[s]["r2"] - metrics_158[s]["r2"] for s in SEGMENTS}
    for s in SEGMENTS:
        print(f"  [{s:6}] R2 158f={metrics_158[s]['r2']:.6f} | 162f={metrics_162[s]['r2']:.6f} "
              f"| delta(162-158)={delta_r2_162_moins_158[s]:+.6f}")

    payload = {
        "script": "c07_reintegration_statent.py",
        "role": "reintegration STATENT (emploi) : 158f vs 162f (+4 colonnes emploi), delta R2 H25",
        "checkpoint_statent": {
            "colonnes_prefixe_statent_dans_parquet": 0,
            "colonnes_emploi_statent_reintegrees": STATENT_COLS,
            "toutes_absentes_des_158f": True,
            "note": "STATENT sous prefixe spatial_ (emplois_500m) ; retrait des 158f (ADR-064)",
        },
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)),
                             extra={"n_features_158": 158, "n_features_162": 162,
                                    "hyperparams": "ADR-052 (300/6/0.1/0.8/0.8, seed=42)",
                                    "durees_s": {"train_158f": round(dt_158, 1), "train_162f": round(dt_162, 1)}}),
        "metriques_h25_158f": metrics_158,
        "metriques_h25_162f": metrics_162,
        "delta_r2_162f_moins_158f": delta_r2_162_moins_158,
        "model_reproduction": {
            "bras_158f": repro,
            "bras_162f": {"archived": None, "retrained": None, "identical": None,
                          "note": "sans objet : pas d'artefact 162f ba493568 archive"},
        },
    }
    out = H.write_json("c07_reintegration_statent.json", payload)
    print(f"[OK] {out.relative_to(H.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
