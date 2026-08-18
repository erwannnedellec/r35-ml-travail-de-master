#!/usr/bin/env python3
"""
V5 — Espace de variables du chapitre 5 : recalcul des trois valeurs avancees.

Sur les 158 variables du modele gele et sur l'annee d'evaluation H25 :
  - combien varient AU SEIN d'un couple (troncon, date) ;
  - parmi elles, combien sont renseignees a plus de 95 % sur H25 ;
  - le complement, c'est-a-dire les variables constantes a ce grain.

La definition de « varier » est explicitee et DEUX lectures defendables sont
produites cote a cote, sans arbitrage :
  - lecture A (NaN = modalite)  : un couple (troncon, date) est variant si les
    valeurs observees, valeur manquante comprise, ne sont pas toutes egales ;
  - lecture B (NaN ignore)      : un couple est variant s'il porte au moins deux
    valeurs NON MANQUANTES distinctes.
Une troisieme lecture, purement documentaire, relit le grain declare colonne par
colonne dans le dictionnaire de la section 4.4.3.

Cle de troncon retenue : (id_gare_depart_bpuic, id_gare_arrivee_bpuic), cle
canonique orientee d'ADR-062. Une lecture non orientee est produite en controle.

Sorties : docs/memoire/verifs/complements/v5_*.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _garde import ROOT, garde  # noqa: E402

OUT = Path(__file__).resolve().parent
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEATS = ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
DICO = ROOT / "docs" / "memoire" / "tableaux" / "section_4_4_3" / "dictionnaire_colonnes_canonique.csv"

ANNEE_EVAL = "H25"
CLE_TRONCON = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]
SEUIL_RENSEIGNEMENT = 0.95


def main() -> None:
    garde()
    print("=" * 78)
    print("V5 — ESPACE DE VARIABLES : VARIATION AU GRAIN (TRONCON, DATE) SUR H25")
    print("=" * 78)

    feats = json.load(open(FEATS))["features"]
    print(f"\n[1] Liste des variables du modele : {FEATS.relative_to(ROOT)}")
    print(f"    {len(feats)} variables declarees")

    besoin = sorted(set(feats + CLE_TRONCON + ["base_date", "horaire_annee_horaire"]))
    df = pd.read_parquet(ML_DATASET, columns=besoin)
    absentes = [f for f in feats if f not in df.columns]
    if absentes:
        raise SystemExit(f"[ARRET] variables absentes du jeu canonique : {absentes}")

    h25 = df[df["horaire_annee_horaire"] == ANNEE_EVAL].copy()
    h25["_date"] = pd.to_datetime(h25["base_date"]).dt.normalize()
    print(f"\n[2] Annee d'evaluation {ANNEE_EVAL} : {len(h25)} observations")

    cles = CLE_TRONCON + ["_date"]
    g = h25.groupby(cles, sort=False, dropna=False)
    taille = g.size()
    testables = taille >= 2
    print(f"    couples (troncon, date)                : {len(taille)}")
    print(f"    couples a >= 2 observations (testables): {int(testables.sum())}")
    print(f"    observations dans les couples testables: {int(taille[testables].sum())}")

    # ── Comptage par variable, deux lectures ──────────────────────────────────
    print("\n[3] Comptage par variable")
    lignes = []
    for c in feats:
        nun_a = g[c].nunique(dropna=False)      # lecture A : NaN = modalite
        nun_b = g[c].nunique(dropna=True)       # lecture B : NaN ignore
        var_a = int((nun_a[testables] > 1).sum())
        var_b = int((nun_b[testables] > 1).sum())
        nn = float(h25[c].notna().mean())
        lignes.append({
            "variable": c,
            "prefixe": c.split("_", 1)[0] + "_",
            "dtype": str(h25[c].dtype),
            "taux_renseignement_H25_pct": round(100 * nn, 4),
            "renseignee_plus_de_95_pct": bool(nn > SEUIL_RENSEIGNEMENT),
            "couples_testables": int(testables.sum()),
            "couples_variants_lectureA": var_a,
            "part_couples_variants_lectureA_pct": round(100 * var_a / max(1, int(testables.sum())), 4),
            "varie_lectureA": bool(var_a > 0),
            "couples_variants_lectureB": var_b,
            "part_couples_variants_lectureB_pct": round(100 * var_b / max(1, int(testables.sum())), 4),
            "varie_lectureB": bool(var_b > 0),
        })
    res = pd.DataFrame(lignes)

    # ── Grain declare au dictionnaire (troisieme lecture, documentaire) ───────
    dico = pd.read_csv(DICO)[["nom", "grain_variation", "grain_cle_reelle", "famille"]]
    res = res.merge(dico.rename(columns={"nom": "variable"}), on="variable", how="left")
    # Un grain declare (troncon, date), (date), (troncon) ou (arret, millesime) est
    # CONSTANT au sein d'un couple (troncon, date) ; « par observation »,
    # (numero_train, date) et (date, heure) y VARIENT.
    GRAINS_VARIANTS = {"par observation", "(numero_train, date)", "(date, heure)"}
    res["varie_grain_declare"] = res["grain_variation"].isin(GRAINS_VARIANTS)

    res.to_csv(OUT / "v5_variables_158_detail.csv", index=False)

    for lect, col in [("A (NaN = modalite)", "varie_lectureA"),
                      ("B (NaN ignore)", "varie_lectureB"),
                      ("grain declare au dictionnaire", "varie_grain_declare")]:
        nv = int(res[col].sum())
        nc = len(res) - nv
        nv95 = int((res[col] & res["renseignee_plus_de_95_pct"]).sum())
        print(f"\n    Lecture {lect}")
        print(f"      variables variant au sein d'un (troncon, date) : {nv} / {len(res)}")
        print(f"      dont renseignees a plus de 95 % sur H25        : {nv95}")
        print(f"      variables constantes a ce grain                : {nc}")

    # ── Listes nominales ──────────────────────────────────────────────────────
    for col, nom in [("varie_lectureA", "lectureA"), ("varie_lectureB", "lectureB"),
                     ("varie_grain_declare", "grain_declare")]:
        res[res[col]][["variable", "prefixe", "famille", "grain_variation",
                       "taux_renseignement_H25_pct", "renseignee_plus_de_95_pct",
                       "part_couples_variants_lectureA_pct",
                       "part_couples_variants_lectureB_pct"]].to_csv(
            OUT / f"v5_variables_variantes_{nom}.csv", index=False)
        res[~res[col]][["variable", "prefixe", "famille", "grain_variation",
                        "taux_renseignement_H25_pct"]].to_csv(
            OUT / f"v5_variables_constantes_{nom}.csv", index=False)

    # ── Ventilation par famille de prefixe ────────────────────────────────────
    print("\n[4] Ventilation par famille de prefixe")
    vent = []
    for pref, sub in res.groupby("prefixe"):
        vent.append({
            "prefixe": pref, "n_variables": len(sub),
            "variantes_lectureA": int(sub["varie_lectureA"].sum()),
            "constantes_lectureA": int((~sub["varie_lectureA"]).sum()),
            "variantes_lectureB": int(sub["varie_lectureB"].sum()),
            "constantes_lectureB": int((~sub["varie_lectureB"]).sum()),
            "variantes_et_renseignees_95_lectureA":
                int((sub["varie_lectureA"] & sub["renseignee_plus_de_95_pct"]).sum()),
            "variantes_et_renseignees_95_lectureB":
                int((sub["varie_lectureB"] & sub["renseignee_plus_de_95_pct"]).sum()),
            "renseignees_95": int(sub["renseignee_plus_de_95_pct"].sum()),
        })
    vdf = pd.DataFrame(vent).sort_values("n_variables", ascending=False)
    vdf.to_csv(OUT / "v5_ventilation_par_prefixe.csv", index=False)
    print(vdf.to_string(index=False))

    # ventilation par famille du codebook (libelles sanctionnes)
    cb = pd.read_csv(CODEBOOK)[["colonne", "famille"]].rename(columns={"colonne": "variable"})
    res2 = res.drop(columns=["famille"]).merge(cb, on="variable", how="left")
    fam = []
    for f, sub in res2.groupby("famille"):
        fam.append({"famille_codebook": f, "n_variables": len(sub),
                    "variantes_lectureA": int(sub["varie_lectureA"].sum()),
                    "constantes_lectureA": int((~sub["varie_lectureA"]).sum()),
                    "variantes_lectureB": int(sub["varie_lectureB"].sum()),
                    "constantes_lectureB": int((~sub["varie_lectureB"]).sum()),
                    "variantes_et_renseignees_95_lectureA":
                        int((sub["varie_lectureA"] & sub["renseignee_plus_de_95_pct"]).sum())})
    fdf = pd.DataFrame(fam).sort_values("n_variables", ascending=False)
    fdf.to_csv(OUT / "v5_ventilation_par_famille_codebook.csv", index=False)
    print("\n" + fdf.to_string(index=False))

    # ── Controle : cle de troncon non orientee ────────────────────────────────
    print("\n[5] Controle de sensibilite : cle de troncon NON orientee")
    h25["_paire"] = [tuple(sorted((a, b))) for a, b in
                     zip(h25["id_gare_depart_bpuic"], h25["id_gare_arrivee_bpuic"])]
    g2 = h25.groupby(["_paire", "_date"], sort=False, dropna=False)
    t2 = g2.size() >= 2
    v2 = {c: int((g2[c].nunique(dropna=False)[t2] > 1).sum()) for c in feats}
    n_var2 = sum(1 for c in feats if v2[c] > 0)
    print(f"    couples (paire de gares non orientee, date) testables : {int(t2.sum())}")
    print(f"    variables variant a ce grain (lecture A)              : {n_var2} / {len(feats)}")
    pd.DataFrame([{"variable": c, "couples_variants": v2[c], "varie": v2[c] > 0}
                  for c in feats]).to_csv(OUT / "v5_controle_troncon_non_oriente.csv", index=False)

    # ── Confrontation aux valeurs du squelette du chapitre 5 ──────────────────
    print("\n[6] Confrontation aux valeurs avancees par le squelette du chapitre 5")
    avances = {"varient": 72, "variantes_et_renseignees_95": 44, "constantes": 86}
    conf = []
    for lect, col in [("A", "varie_lectureA"), ("B", "varie_lectureB"),
                      ("grain_declare", "varie_grain_declare")]:
        nv = int(res[col].sum())
        conf.append({"lecture": lect,
                     "varient_recalcule": nv, "varient_avance": avances["varient"],
                     "variantes_et_renseignees_95_recalcule":
                         int((res[col] & res["renseignee_plus_de_95_pct"]).sum()),
                     "variantes_et_renseignees_95_avance": avances["variantes_et_renseignees_95"],
                     "constantes_recalcule": len(res) - nv,
                     "constantes_avance": avances["constantes"]})
    cdf = pd.DataFrame(conf)
    cdf.to_csv(OUT / "v5_confrontation_chapitre5.csv", index=False)
    print(cdf.to_string(index=False))

    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
