#!/usr/bin/env python3
"""
s2_entrainement_variantes.py — VÉRIF 4, section 4.2 : entraînement des variantes.

Cinq variantes, à hyperparamètres, architecture segmentée et partition STRICTEMENT
identiques au modèle gelé. Seule la liste de variables change.

  C  — modèle gelé, référence                        158 variables
  A1 — sans les candidates émergentes substantielles 146  (narcisses, ski, groupes)
  A2 — A1 étendue à la concurrence modale            142  (A1 + les 4 colonnes vmcv_)
  A3 — sans les candidates « Littérature »           105
  A4 — sans les candidates « Confirmée »              76

A3 et A4 sont des CONTRÔLES DE CALIBRAGE : ils disent de combien dégrade le retrait d'un
bloc de taille comparable ou supérieure, sans quoi un écart de deux centièmes en A1 n'est
pas interprétable.

Dix graines d'initialisation, fixées ici une fois pour toutes et jamais rouvertes. La
graine 42 est celle du modèle gelé : la variante C entraînée à la graine 42 DOIT
reproduire les empreintes e4ddfccd / df6a11c5. Toute divergence est un STOP.

Discipline : écrit UNIQUEMENT sous docs/memoire/verifs/section_5_1/_experimentation/.
Ne touche ni au modèle gelé, ni à la recette de référence, ni à la table canonique.

Sortie : _experimentation/s2_variantes.json  + prédictions H25 de C, A1, A2 (graine 42).
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

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[3]
sys.path.insert(0, str(ROOT / "scripts/confirmation"))
import _harness as H  # noqa: E402

EXP = ICI / "_experimentation"
EXP.mkdir(exist_ok=True)
RECON = ICI / "_reconciliation.json"

# Graines d'initialisation — FIXÉES avant exécution, jamais rouvertes (section 5).
GRAINES = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
GRAINE_REF = 42

VARIANTES = ["C", "A1", "A2", "A3", "A4"]
DESCRIPTION = {
    "C": "modèle gelé, référence",
    "A1": "sans les candidates émergentes substantielles (narcisses, ski, groupes)",
    "A2": "A1 étendue à la concurrence modale (+ vmcv_)",
    "A3": "sans les candidates issues de la seule littérature",
    "A4": "sans les candidates confirmées",
}


def main() -> int:
    if not RECON.exists():
        raise RuntimeError("STOP : _reconciliation.json absent — lancer s1_reconciliation.py d'abord.")
    recon = json.loads(RECON.read_text())
    per = recon["perimetres"]

    H.assert_dataset()
    feats158 = H.load_features_158()
    df = H.load_dataset()
    train, test = H.split_c(df)
    print(f"Split C : train={len(train)} | test H25={len(test)}", flush=True)

    retraits = {"C": [], "A1": per["A1"], "A2": per["A2"], "A3": per["A3"], "A4": per["A4"]}
    listes = {}
    for v in VARIANTES:
        r = set(retraits[v])
        manquantes = r - set(feats158)
        if manquantes:
            raise RuntimeError(f"STOP : colonnes à retirer absentes des 158 pour {v} : {manquantes}")
        listes[v] = [c for c in feats158 if c not in r]        # ordre canonique préservé
        print(f"  {v:3} {len(listes[v]):>3} variables (retrait de {len(r)})", flush=True)

    resultats, durees = {}, {}
    for v in VARIANTES:
        resultats[v] = {}
        for g in GRAINES:
            t0 = time.time()
            params = dict(H.XGB_PARAMS, random_state=g)
            pred, models = H.train_segmented(train, test, listes[v], params)
            dt = time.time() - t0

            # garde-fou d'ancrage : C à la graine de référence doit reproduire le gel
            if v == "C" and g == GRAINE_REF:
                repro = H.reproduce_and_hash_segmented(models)
                print(f"  [C/{g}] reproduction du gel : {repro['all_identical']} "
                      f"(bas {repro['bas']['retrained']} / haut {repro['haut']['retrained']})",
                      flush=True)
                if not repro["all_identical"]:
                    (EXP / "s2_STOP.json").write_text(json.dumps(
                        {"STOP": True, "raison": "la variante C à la graine 42 ne reproduit "
                                                 "pas e4ddfccd / df6a11c5",
                         "model_reproduction": repro}, indent=2, ensure_ascii=False))
                    print("!" * 78 + "\nSTOP : ancrage du gel non reproduit.\n" + "!" * 78)
                    return 1
                resultats[v]["_reproduction_gel"] = repro

            # IC bootstrap du R2 seulement à la graine de référence (coût maîtrisé) ;
            # la dispersion inter-graines est chiffrée séparément, section 4.3.2.
            met = H.metrics_by_segment(test, pred, with_ci=(g == GRAINE_REF))
            resultats[v][str(g)] = met
            durees[f"{v}/{g}"] = round(dt, 1)
            print(f"  [{v}/{g}] R2 global={met['global']['r2']:.6f} "
                  f"MAE>63={met['global']['mae_gt63']:.4f} "
                  f"PR-AUC={met['global']['pr_auc']:.6f}  ({dt:.0f}s)", flush=True)

            # prédictions H25 conservées pour la propagation à la couche décisionnelle
            if g == GRAINE_REF and v in ("C", "A1", "A2"):
                pd.DataFrame({
                    "date": pd.to_datetime(test["base_date"]).dt.normalize().values,
                    "numero_train": test["horaire_numero_train"].astype("Int64").astype(str).values,
                    "spatial_segment": test["spatial_segment"].values,
                    "target": H.y_of(test),
                    "resa2c": test["resa_pax_2c_J_minus_1"].astype("Float64").astype(float).values,
                    "pred": pred,
                }).to_parquet(EXP / f"pred_h25_{v}_g{g}.parquet", index=False)

    payload = {
        "script": "s2_entrainement_variantes.py",
        "role": "VÉRIF 4 §4.2 — entraînement des variantes d'ablation (post-hoc, hors gel)",
        "meta": H.meta_block(n_train=int(len(train)), n_test=int(len(test)), extra={
            "graines": GRAINES, "graine_reference": GRAINE_REF,
            "variantes": {v: {"description": DESCRIPTION[v], "n_variables": len(listes[v]),
                              "n_retirees": len(retraits[v]),
                              "colonnes_retirees": sorted(retraits[v])} for v in VARIANTES},
            "durees_s": durees,
            "empreintes_reconciliation": recon["empreintes"]}),
        "resultats": resultats,
    }
    (EXP / "s2_variantes.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\n[OK] s2_variantes.json — {len(VARIANTES)} variantes × {len(GRAINES)} graines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
