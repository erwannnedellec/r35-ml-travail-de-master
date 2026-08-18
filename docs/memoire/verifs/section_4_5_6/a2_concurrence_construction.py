#!/usr/bin/env python3
"""
A2 — Construction des variables de concurrence modale (VMCV) et vérification des
corrélations citées en §4.5.6.

Audit en LECTURE SEULE : aucun réentraînement, aucune écriture hors
docs/memoire/verifs/section_4_5/.

Produit :
  - a2_colonnes_vmcv.csv        inventaire des colonnes de la famille `vmcv_`
  - a2_mapping_geometrique.csv  mapping statique (gare R35, sens) -> lignes VMCV, rayon 200 m
  - a2_correlations.csv         rang + Spearman(SHAP signé, valeur) sur H25, modèles gelés
  - a2_resultats.json           synthèse machine

Protocole SHAP : reprise exacte de scripts/confirmation/c08_shap_segments.py
(mêmes modèles gelés, même périmètre H25, même prep_X, booster.predict(pred_contribs=True)).
Contrôle de conformité bloquant contre outputs/confirmation/c08_shap_ranks_{bas,haut}.csv.

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/a2_concurrence_construction.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402

OUT = Path(__file__).resolve().parent
DIM_LIGNES = ROOT / "data/dimension/dim_vmcv_lignes_concurrentes.parquet"
DIM_GARE = ROOT / "data/dimension/dim_gare.parquet"
DIM_TRAIN_JOUR = ROOT / "data/processed/sources/dim_vmcv_par_train_jour.parquet"
CODEBOOK = ROOT / "outputs/codebook_canonique_ba493568.csv"

VMCV_COLS = ["vmcv_n_lignes_concurrentes", "vmcv_min_attente_min",
             "vmcv_delta_attente_min", "vmcv_delta_frequence_h",
             "vmcv_source_depart", "vmcv_source_arrivee"]
HEADWAY_COLS = ["ist_headway_avant_min", "ist_headway_apres_min",
                "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day"]

# Constantes de construction lues dans le code producteur (pour la traçabilité)
RAYON_LIGNES_M = 400        # build_vmcv_lignes_concurrentes.py:69  (RAYON_COMPETITION_METRES)
RAYON_MAPPING_M = 200       # build_dim_vmcv_par_train_jour.py:71   (RAYON_PROXIMITE_M)
KM_SEUIL_BAS = 4.0          # build_dim_vmcv_par_train_jour.py:69
KM_SEUIL_HAUT = 5.5         # build_dim_vmcv_par_train_jour.py:70


# ── SHAP (protocole c08) ────────────────────────────────────────────────────────
def shap_h25(test, feats, models):
    """SHAP signés par segment sur H25 (TreeSHAP exact, pred_contribs, tree_path_dependent)."""
    out = {}
    for seg in ("bas", "haut"):
        sub = test[test["spatial_segment"] == seg]
        X = H.prep_X(sub, feats)
        booster = models[seg].get_booster()
        dm = xgb.DMatrix(X, enable_categorical=True)
        contribs = booster.predict(dm, pred_contribs=True)      # (n, 159) : +biais
        out[seg] = {"shap": contribs[:, :-1], "meta": sub.reset_index(drop=True),
                    "idx": {f: i for i, f in enumerate(feats)}}
    return out


def ranks(shap, feats):
    mabs = np.abs(shap).mean(axis=0)
    d = pd.DataFrame({"feature": feats, "mean_abs_shap": mabs})
    d = d.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    d["rang"] = d.index + 1
    d["pct_du_total"] = 100.0 * d["mean_abs_shap"] / d["mean_abs_shap"].sum()
    return d.set_index("feature")


def conformite_c08(rk):
    """Contrôle bloquant : les mean|SHAP| recalculés reproduisent c08 en float32."""
    verdicts = {}
    for seg in ("bas", "haut"):
        ref = pd.read_csv(ROOT / f"outputs/confirmation/c08_shap_ranks_{seg}.csv")
        m = ref.merge(rk[seg].reset_index(), on="feature", suffixes=("_ref", "_new"))
        if len(m) != 158:
            raise RuntimeError(f"STOP conformité c08 {seg} : {len(m)} features appariées != 158")
        eq32 = np.array_equal(m["mean_abs_shap_ref"].values.astype("float32"),
                              m["mean_abs_shap_new"].values.astype("float32"))
        ecart = float(np.max(np.abs(m["mean_abs_shap_ref"].values
                                    - m["mean_abs_shap_new"].values)))
        rang_ok = bool((m["rang_ref"] == m["rang_new"]).all())
        if not (eq32 and rang_ok):
            raise RuntimeError(f"STOP conformité c08 {seg} : eq32={eq32} rangs={rang_ok} "
                               f"ecart_max={ecart:.3e}")
        verdicts[seg] = {"egalite_float32": eq32, "rangs_identiques": rang_ok,
                         "ecart_max_float64": ecart}
    return verdicts


def spearman_signed(d, feat, mask=None):
    """Spearman(valeur, SHAP signé) sur les lignes non-NaN — convention s02_analyses.py:110."""
    col = d["shap"][:, d["idx"][feat]].astype("float64")
    val = d["meta"][feat].astype("float64").values
    if mask is not None:
        col, val = col[mask], val[mask]
    ok = ~np.isnan(val)
    rho = np.nan
    if ok.sum() > 10 and np.unique(val[ok]).size > 1 and np.unique(col[ok]).size > 1:
        rho = float(spearmanr(val[ok], col[ok]).statistic)
    return rho, float(np.mean(col)), int(len(col)), int(ok.sum())


def main() -> int:
    print("=== A2 — concurrence modale : construction + corrélations (lecture seule) ===")
    H.assert_dataset()
    feats = H.load_features_158()
    df = H.load_dataset()
    train, test = H.split_c(df)
    res = {"dataset_hash": H.HASH,
           "modeles": {"bas": H.HASH_MODEL_BAS, "haut": H.HASH_MODEL_HAUT},
           "n_h25": int(len(test))}

    # ── 1. Inventaire des colonnes de la famille vmcv_ ──────────────────────────
    cb = pd.read_csv(CODEBOOK).set_index("colonne")
    rows = []
    for c in VMCV_COLS:
        s_all, s_h25 = df[c], test[c]
        rows.append({
            "colonne": c,
            "dtype": str(df[c].dtype),
            "dans_158_features": c in feats,
            "famille_codebook": cb.loc[c, "famille"] if c in cb.index else None,
            "libelle_fr": cb.loc[c, "libelle_fr"] if c in cb.index else None,
            "nan_pct_h22_h25": round(100.0 * s_all.isna().mean(), 4),
            "nan_pct_h25": round(100.0 * s_h25.isna().mean(), 4),
            "n_nan_h25": int(s_h25.isna().sum()),
            "n_modalites_h25": int(s_h25.nunique(dropna=True)),
            "min_h25": (float(s_h25.min()) if s_h25.dtype.kind in "fiu" else None),
            "max_h25": (float(s_h25.max()) if s_h25.dtype.kind in "fiu" else None),
        })
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "a2_colonnes_vmcv.csv", index=False)
    print(inv[["colonne", "dtype", "dans_158_features", "nan_pct_h25"]].to_string(index=False))
    res["colonnes"] = rows

    # ── 2. Géométrie : mapping statique (gare, sens) reconstruit depuis les dims ─
    lig = pd.read_parquet(DIM_LIGNES)
    res["lignes_vmcv"] = {
        "n_lignes_table": int(len(lig)),
        "rayon_selection_lignes_m": RAYON_LIGNES_M,
        "n_is_concurrent": int(lig["is_concurrent"].sum()),
        "n_is_concurrent_actif": int(lig["is_concurrent_actif"].sum()),
        "lignes_is_concurrent_actif": sorted(lig.loc[lig["is_concurrent_actif"],
                                                     "linien_text"].astype(str)),
        "lignes_passees_au_builder": sorted(lig["linien_text"].dropna().astype(str).unique()),
        "note": "build_dim_vmcv_par_train_jour.py:456 passe TOUTES les lignes de la table "
                "(pas seulement is_concurrent_actif) au filtre de proximité 200 m.",
    }

    # Le mapping effectif est relu depuis la table produite (grain train x jour x sens),
    # croisée avec la gare de départ : on rapporte la distribution effective.
    tj = pd.read_parquet(DIM_TRAIN_JOUR)
    distrib = (tj.groupby(["sens", "vmcv_n_lignes_concurrentes"], dropna=False)
                 .size().rename("n_combinaisons_date_train_sens").reset_index())
    distrib.to_csv(OUT / "a2_mapping_geometrique.csv", index=False)
    res["mapping_effectif"] = {
        "grain_table_source": "(date, numero_train, sens)",
        "n_lignes_table_source": int(len(tj)),
        "rayon_mapping_m": RAYON_MAPPING_M,
        "seuil_km_bas": KM_SEUIL_BAS, "seuil_km_haut": KM_SEUIL_HAUT,
        "distribution": distrib.astype(object).where(pd.notna(distrib), None)
                               .to_dict(orient="records"),
    }

    # Sur H25 : quelle est la gare de départ effective des tronçons couverts ?
    gare = pd.read_parquet(DIM_GARE)
    km = dict(zip(gare["bpuic"], gare["km"]))
    cov = test[test["vmcv_n_lignes_concurrentes"].notna()].copy()
    par_sens = (cov.groupby("base_sens")["vmcv_n_lignes_concurrentes"]
                   .agg(["size", "mean", "max"]).reset_index())
    res["h25_couverture_par_sens"] = par_sens.to_dict(orient="records")
    res["h25_km_gare_depart_troncon"] = {
        "note": "km de la gare de DEPART DU TRONCON (pas de la course) pour les tronçons "
                "à vmcv_n_lignes_concurrentes non nul, par sens",
        "par_sens": {
            s: {"km_min": float(np.nanmin(g["id_gare_depart_bpuic"].map(km))),
                "km_max": float(np.nanmax(g["id_gare_depart_bpuic"].map(km))),
                "n": int(len(g))}
            for s, g in cov[cov["vmcv_n_lignes_concurrentes"] > 0].groupby("base_sens")
        },
    }

    # ── 3. SHAP sur H25, modèles gelés ──────────────────────────────────────────
    print("  chargement des modèles gelés + calcul SHAP H25 (peut prendre 1-3 min) …")
    models = H.load_frozen_models()
    data = shap_h25(test, feats, models)
    rk = {seg: ranks(data[seg]["shap"], feats) for seg in ("bas", "haut")}
    res["conformite_c08"] = conformite_c08(rk)
    print("  conformité c08 : OK (float32 + rangs identiques sur 158 features, 2 segments)")

    # ── 4. Corrélations citées au manuscrit ─────────────────────────────────────
    lignes = []
    for feat in VMCV_COLS[:4] + HEADWAY_COLS:
        for seg in ("bas", "haut"):
            rho, signed, n, n_ok = spearman_signed(data[seg], feat)
            lignes.append({
                "variable": feat, "segment": seg,
                "rang_sur_158": int(rk[seg].loc[feat, "rang"]),
                "mean_abs_shap": float(rk[seg].loc[feat, "mean_abs_shap"]),
                "pct_du_total": float(rk[seg].loc[feat, "pct_du_total"]),
                "mean_shap_signe": signed,
                "spearman_valeur_vs_shap": rho,
                "n_obs": n, "n_obs_non_nan": n_ok,
            })
    corr = pd.DataFrame(lignes)
    corr.to_csv(OUT / "a2_correlations.csv", index=False)
    print(corr.to_string(index=False))
    res["correlations"] = lignes

    # Vérification directe des trois valeurs du manuscrit
    def get(v, s, k):
        r = corr[(corr.variable == v) & (corr.segment == s)].iloc[0]
        return float(r[k]) if k != "rang_sur_158" else int(r[k])

    res["verdicts_manuscrit"] = {
        "vmcv_n_lignes_concurrentes_bas_spearman": {
            "annonce": -0.66,
            "recalcule": round(get("vmcv_n_lignes_concurrentes", "bas",
                                   "spearman_valeur_vs_shap"), 4),
            "rang_bas": get("vmcv_n_lignes_concurrentes", "bas", "rang_sur_158"),
        },
        "ist_headway_apres_min_bas": {
            "annonce_spearman": -0.80, "annonce_rang": 11,
            "recalcule_spearman": round(get("ist_headway_apres_min", "bas",
                                            "spearman_valeur_vs_shap"), 4),
            "recalcule_rang": get("ist_headway_apres_min", "bas", "rang_sur_158"),
        },
    }

    (OUT / "a2_resultats.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
