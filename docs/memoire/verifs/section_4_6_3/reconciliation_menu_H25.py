#!/usr/bin/env python3
"""
reconciliation_menu_H25.py  —  TÂCHE 2, mémoire §4.6.

Recalcul INDÉPENDANT des 7 points de fonctionnement H25 du menu décisionnel de la
couche 2, directement depuis le parquet canonique (`data/processed/ml_dataset.parquet`,
SHA256[:8] = ba493568, gel v2 ADR-076) et les modèles Enrichi_Seg figés
(`enrichi_seg_{bas,haut}_ba493568.json`, hashes e4ddfccd / df6a11c5 — byte-identiques
à la couche 1 v1.9, gel décisionnel 416bb90b : la migration gel v2 n'a corrigé que des
features H25, cf. ADR-076 + rapport_audit_calibration_couche2.md).

Méthode : on RÉUTILISE le code canonique `src/couche2/decision.py` (build_decision_set,
assert_perimetre_et_ancrage, calibrate, evaluate_h25) — aucun réentraînement, aucune règle
locale. Le point de déploiement c ∪ plancher est reconstruit à l'identique du protocole
préenregistré `scripts/experiences/deploiement_c_plancher_ba493568.py`.

Chaque point est comparé aux valeurs du manuscrit v3_55 et reçoit un verdict par ligne.

LECTURE SEULE. Le script N'ÉCRIT QUE dans docs/memoire/verifs/section_4_6/ (son .md).
Il n'écrit RIEN dans outputs/couche2/. Reproductibilité : threads=1 (ADR-076).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

SEUIL = 63
OUT_MD = Path(__file__).resolve().parent / "reconciliation_menu_H25.md"

# ── Valeurs du manuscrit v3_55 (à réconcilier) : vol, VP, FP, précision %, rappel % ──
MANUSCRIT = {
    "pratique_418_UM":      (418, 140, 278, 33.5, 6.8),
    "budget_egal_418":      (418, 343,  75, 82.1, 16.6),
    "a_prime":              (252, 215,  37, 85.3, 10.4),
    "b":                    (2563, 1292, 1271, 50.4, 62.4),
    "c":                    (840, 605, 235, 72.0, 29.2),
    "a_prime_union_planch": (352, 274,  78, 77.8, 13.2),
    "c_union_planch":       (866, 622, 244, 71.8, 30.0),
}
LIB = {
    "pratique_418_UM":      "Pratique de référence (418 UM humaines)",
    "budget_egal_418":      "Lecture à budget égal (418 premiers scores)",
    "a_prime":              "a′ (iso-volume, seuil figé)",
    "b":                    "b (rappel renforcé, F2)",
    "c":                    "c (haute précision, F0.5)",
    "a_prime_union_planch": "a′ ∪ plancher (point de référence)",
    "c_union_planch":       "c ∪ plancher (déploiement)",
}
# Décompositions d'union attendues (score_seul, plancher_seul, intersection)
MANUSCRIT_UNION = {
    "a_prime_union_planch": (198, 100, 54),
    "c_union_planch":       (712,  26, 128),
}


def pct(x):
    return None if x is None else round(x * 100, 1)


def recompute():
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)          # gardes 29 222 / 2 072 / 1 224 / 848
    calib = decision.calibrate(ds)
    ev = decision.evaluate_h25(ds, calib)

    reg = calib["regles_deployables"]
    tau_a = reg["a_iso_volume"]["seuil"]
    tau_c = reg["c_haute_precision"]["seuil"]

    def row(g):
        return (g["volume"], g["VP"], g["FP"], pct(g["precision"]), pct(g["recall"]))

    out = {}
    out["pratique_418_UM"] = row(ev["humain_H25"]["global"])
    out["budget_egal_418"] = row(ev["headline_top_k_protocolaire"]["global"])
    out["a_prime"] = row(ev["deployable_menu"]["a_iso_volume"]["seuil_fige"]["global"])
    out["b"] = row(ev["deployable_menu"]["b_rappel_renforce"]["seuil_fige"]["global"])
    out["c"] = row(ev["deployable_menu"]["c_haute_precision"]["seuil_fige"]["global"])

    art = ev["artefact_complet_reference"]
    out["a_prime_union_planch"] = row(art["global"])

    # -- c ∪ plancher reconstruit à l'identique du protocole préenregistré (ADR-077) --
    h25 = ds[ds["annee"] == "H25"].copy()
    y = h25["label"].values.astype(bool)
    reco_c = h25["score"].values >= tau_c
    reco_pl = h25["resa2c"].values > SEUIL
    reco_u = reco_c | reco_pl
    vol = int(reco_u.sum()); vp = int((reco_u & y).sum()); fp = vol - vp
    out["c_union_planch"] = (vol, vp, fp, pct(vp / vol), pct(vp / int(y.sum())))

    # décompositions d'union
    union_dec = {}
    ra = art["recouvrement"]
    union_dec["a_prime_union_planch"] = (ra["a_seul"], ra["plancher_seul"], ra["intersection"])
    union_dec["c_union_planch"] = (int((reco_c & ~reco_pl).sum()),
                                   int((reco_pl & ~reco_c).sum()),
                                   int((reco_c & reco_pl).sum()))

    # métadonnées de contrôle
    meta = {
        "hash_dataset": decision.blocs.assert_canonical_dataset(),
        "n_h25": info["n_h25"], "pos": info["positives_h25"],
        "pos_haut": info["positives_haut"], "pos_bas": info["positives_bas"],
        "tau_a": tau_a, "tau_b": reg["b_rappel_renforce"]["seuil"], "tau_c": tau_c,
        "n_courses_H24": calib["n_courses_H24"], "n_pos_H24": calib["n_positives_H24"],
        "budget_H24": calib["budget_humain_H24"], "budget_H25": calib["budget_humain_H25"],
        "n_resa_sup63_H25": int(reco_pl.sum()),
    }
    return out, union_dec, meta


def verdict(recomp, manu):
    """Verdict par ligne : OK si vol/VP/FP identiques ET %prec/%rappel identiques (1 déc.)."""
    diffs = []
    for i, name in enumerate(["vol", "VP", "FP", "prec%", "rappel%"]):
        if recomp[i] != manu[i]:
            diffs.append(f"{name} {recomp[i]}≠{manu[i]}")
    return ("OK — identique" if not diffs else "ÉCART : " + ", ".join(diffs))


def main():
    recomp, union_dec, meta = recompute()

    L = []
    L.append("# Réconciliation des métriques H25 du menu décisionnel (couche 2) — §4.6\n")
    L.append("Recalcul indépendant depuis le parquet canonique **ba493568** et les modèles figés "
             "**e4ddfccd / df6a11c5** (byte-identiques à la couche 1 v1.9, gel décisionnel "
             "**416bb90b** ; la migration gel v2 ADR-076 n'a corrigé que des features H25). "
             "Code réutilisé : `src/couche2/decision.py` (aucun réentraînement). "
             "Point c ∪ plancher : protocole `scripts/experiences/deploiement_c_plancher_ba493568.py`.\n")
    L.append(f"Généré par `reconciliation_menu_H25.py` (threads=1). Hash dataset vérifié = "
             f"**{meta['hash_dataset']}**.\n")

    L.append("## Garde-fous de périmètre (P3, recalculés)\n")
    L.append(f"- Courses H25 iso-périmètre : **{meta['n_h25']}** (attendu 29 222) — "
             f"{'OK' if meta['n_h25']==29222 else 'ÉCART'}")
    L.append(f"- Surcharges (label D2) : **{meta['pos']}** (attendu 2 072) — "
             f"{'OK' if meta['pos']==2072 else 'ÉCART'}")
    L.append(f"- dont segment HAUT : **{meta['pos_haut']}** (attendu 1 224) — "
             f"{'OK' if meta['pos_haut']==1224 else 'ÉCART'}")
    L.append(f"- dont segment BAS : **{meta['pos_bas']}** (attendu 848) — "
             f"{'OK' if meta['pos_bas']==848 else 'ÉCART'}")
    L.append(f"- Calibration H24 : {meta['n_courses_H24']} courses / {meta['n_pos_H24']} surcharges ; "
             f"budget humain H24 = {meta['budget_H24']} ; budget humain H25 = {meta['budget_H25']}.")
    L.append(f"- Seuils recalculés : τ(a′) = **{meta['tau_a']:.5f}**, τ(b) = **{meta['tau_b']:.5f}**, "
             f"τ(c) = **{meta['tau_c']:.5f}**.")
    L.append(f"- Courses résa 2ᵉ cl. J-1 > 63 en H25 (plancher) : **{meta['n_resa_sup63_H25']}**.\n")

    L.append("## Tableau manuscrit v3_55 vs recalcul (grain course, H25, global)\n")
    L.append("| Point de fonctionnement | source | volume | VP | FP | précision | rappel | verdict |")
    L.append("|---|---|---:|---:|---:|---:|---:|---|")
    all_ok = True
    for key in MANUSCRIT:
        m = MANUSCRIT[key]; r = recomp[key]
        v = verdict(r, m)
        if not v.startswith("OK"):
            all_ok = False
        L.append(f"| {LIB[key]} | manuscrit | {m[0]} | {m[1]} | {m[2]} | {m[3]:.1f} % | {m[4]:.1f} % | |")
        L.append(f"| {LIB[key]} | **recalcul** | {r[0]} | {r[1]} | {r[2]} | {r[3]:.1f} % | {r[4]:.1f} % | **{v}** |")

    L.append("\n## Décompositions d'union\n")
    L.append("| Union | source | score seul | plancher seul | intersection | (somme) | verdict |")
    L.append("|---|---|---:|---:|---:|---:|---|")
    for key in MANUSCRIT_UNION:
        m = MANUSCRIT_UNION[key]; r = union_dec[key]
        vok = (r == m)
        if not vok:
            all_ok = False
        L.append(f"| {LIB[key]} | manuscrit | {m[0]} | {m[1]} | {m[2]} | {sum(m)} | |")
        L.append(f"| {LIB[key]} | **recalcul** | {r[0]} | {r[1]} | {r[2]} | {sum(r)} | "
                 f"**{'OK — identique' if vok else 'ÉCART'}** |")

    L.append("\n## Verdict global\n")
    L.append(f"**{'TOUTES LES LIGNES CONCORDENT (aucun écart, pas même d’une unité).' if all_ok else 'DES ÉCARTS SUBSISTENT — voir lignes ci-dessus.'}**")
    L.append("\nLes valeurs du manuscrit v3_55 correspondent donc au **gel courant ba493568**. "
             "(Les valeurs de l’ancien gel 416bb90b — a′ 253/216/37/85,4/10,4, etc. — sont "
             "supersédées ; cf. `valeurs_ancien_gel_a_chercher.md`.)")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n[OK] écrit → {OUT_MD}")
    print(f"[GLOBAL] {'TOUT CONCORDE' if all_ok else 'ÉCARTS'}")


if __name__ == "__main__":
    main()
