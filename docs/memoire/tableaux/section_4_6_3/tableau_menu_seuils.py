#!/usr/bin/env python3
"""
tableau_menu_seuils.py — TÂCHE 4, mémoire §4.6.

Tableau récapitulatif du menu décisionnel de la couche 2 : une ligne par seuil de score
(a′ / b / c) + une ligne pour le plancher de réservation. Métriques EN CALIBRATION sur H24.

Réutilise le code canonique `src/couche2/decision.py` (build_decision_set + calibrate) — les
seuils a′/b/c et leurs métriques H24 en sortent tels quels ; le plancher (règle déterministe
résa>63, sans paramètre appris) est évalué sur la même tranche H24 (il ne dépend ni du modèle
ni d'aucune calibration).

LECTURE SEULE : n'écrit que ses .csv/.md dans docs/memoire/tableaux/section_4_6/. Rien dans
outputs/. Reproductibilité : threads=1 (ADR-076).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
SEUIL = 63

# Métadonnées éditoriales (postures + critères courts) — texte du tableau de 4.6.
POSTURE = {
    "a_prime":  "Parcimonie (volume aligné sur la pratique)",
    "b":        "Rappel renforcé (couverture maximale)",
    "c":        "Haute précision (fausses alarmes maîtrisées)",
    "plancher": "Garantie inconditionnelle (engagement commercial)",
}
CRITERE = {
    "a_prime":  "Rang au budget d'engagements humain H24 (381 UM sur 32 102 courses)",
    "b":        "Maximisation de F₂ (β=2, pondère rappel) sur H24",
    "c":        "Maximisation de F₀‚₅ (β=0,5, pondère précision) sur H24",
    "plancher": "Aucun paramètre appris — règle déterministe (résa 2ᵉ cl. J-1 > 63)",
}
DESIGNATION = {
    "a_prime":  "a′ — iso-volume",
    "b":        "b — rappel renforcé",
    "c":        "c — haute précision",
    "plancher": "Plancher de demande annoncée",
}


def pct(x):
    return None if x is None else round(x * 100, 1)


def main():
    ds = decision.build_decision_set()
    decision.assert_perimetre_et_ancrage(ds)                 # gardes P3
    calib = decision.calibrate(ds)
    reg = calib["regles_deployables"]
    n_pos_H24 = calib["n_positives_H24"]                     # 2380

    rows = {}
    for key, rk in [("a_prime", "a_iso_volume"), ("b", "b_rappel_renforce"), ("c", "c_haute_precision")]:
        d = reg[rk]
        rows[key] = {"seuil": f"{d['seuil']:.2f}", "volume": d["volume"], "VP": d["VP"],
                     "FP": d["FP"], "precision": pct(d["precision"]), "rappel": pct(d["rappel"])}

    # -- plancher sur H24 : règle resa2c>63 (sans modèle, sans calibration) --
    h24 = ds[ds["annee"] == "H24"]
    m_pl = h24["resa2c"].values > SEUIL
    y24 = h24["label"].values.astype(bool)
    vol = int(m_pl.sum()); vp = int((m_pl & y24).sum()); fp = vol - vp
    rows["plancher"] = {"seuil": "sans parametre appris", "volume": vol, "VP": vp, "FP": fp,
                        "precision": pct(vp / vol) if vol else None,
                        "rappel": pct(vp / n_pos_H24) if n_pos_H24 else None}

    order = ["a_prime", "b", "c", "plancher"]
    headers = ["designation", "posture", "critere_calibration", "valeur_seuil_voyageurs_predits",
               "volume_H24", "VP_H24", "FP_H24", "precision_H24_pct", "rappel_H24_pct"]

    # ── CSV ──
    csv_path = OUT_DIR / "tableau_menu_seuils.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for k in order:
            r = rows[k]
            w.writerow([DESIGNATION[k], POSTURE[k], CRITERE[k], r["seuil"],
                        r["volume"], r["VP"], r["FP"], r["precision"], r["rappel"]])

    # ── Markdown ──
    md = []
    md.append("# Menu de seuils décisionnels — couche 2 (§4.6)\n")
    md.append("Métriques **en calibration sur H24** (population 32 102 courses / 2 380 surcharges). "
              "Génération `ba493568` ; seuils a′/b/c inchangés vs gel décisionnel `416bb90b`. "
              "Score de course = max des prédictions couche 1 sur les tronçons (D3).\n")
    md.append("⚠️ Les précisions/rappels H24 sont **in-sample** (H24 ∈ train Split C) et ne se "
              "transfèrent pas tels quels ; performances H25 dans `reconciliation_menu_H25.md`.\n")
    md.append("| Désignation | Posture | Critère de calibration | Valeur du seuil (voy. prédits) "
              "| Volume H24 | Précision H24 | Rappel H24 |")
    md.append("|---|---|---|---|---:|---:|---:|")
    for k in order:
        r = rows[k]
        seuil = r["seuil"] if k == "plancher" else f"{r['seuil']}"
        prec = "—" if r["precision"] is None else f"{r['precision']:.1f} %"
        rapp = "—" if r["rappel"] is None else f"{r['rappel']:.1f} %"
        md.append(f"| {DESIGNATION[k]} | {POSTURE[k]} | {CRITERE[k]} | {seuil} "
                  f"| {r['volume']} | {prec} | {rapp} |")
    md.append("\n*Détail VP/FP H24* : "
              + " ; ".join(f"{DESIGNATION[k].split(' —')[0]} "
                           f"{rows[k]['VP']}/{rows[k]['FP']}" for k in order)
              + " (VP/FP).")
    md.append("\nSources : `src/couche2/decision.py:172-181,258` ; "
              "`outputs/couche2/q_couche2_calibration_H24_ba493568.json`. "
              "Généré par `tableau_menu_seuils.py` (threads=1).")
    (OUT_DIR / "tableau_menu_seuils.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ── écho ──
    print("[a'/b/c/plancher — calibration H24]")
    for k in order:
        r = rows[k]
        print(f"  {DESIGNATION[k]:32} seuil={r['seuil']:>22} vol={r['volume']:>5} "
              f"VP={r['VP']:>4} FP={r['FP']:>4} P={r['precision']} R={r['rappel']}")
    print(f"[OK] {csv_path.name} + tableau_menu_seuils.md")


if __name__ == "__main__":
    main()
