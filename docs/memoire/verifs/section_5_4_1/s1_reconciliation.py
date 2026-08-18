#!/usr/bin/env python3
"""
s1_reconciliation.py — VÉRIF 4, section 4.1 : réconciliation préalable.

PORTE BLOQUANTE. Confronte la table d'autorité de l'annexe 22 (fournie par la consigne,
transcrite dans `_table_autorite_annexe22.py`) à la liste gelée des 158 variables et à
la table canonique, puis recalcule les agrégats du tableau A19.2 depuis le modèle gelé.

Si les quatre lignes de l'A19.2 ne sont pas reproduites, le script S'ARRÊTE et rapporte
l'écart. Aucune ablation n'est lancée tant que cette porte n'est pas franchie.

Sortie : docs/memoire/verifs/section_5_1/_reconciliation.json (consommé par s2/s3),
         et le bloc Markdown de tête du rapport final.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI.parent))
import _socle_chap5 as S            # noqa: E402
import _table_autorite_annexe22 as A  # noqa: E402

FEAT_JSON = S.ROOT / "outputs/couche2/features_158f_sans_simba.json"
SHAP = {s: S.ROOT / f"outputs/confirmation/c08_shap_ranks_{s}.csv" for s in ("bas", "haut")}
OUT_JSON = ICI / "_reconciliation.json"
OUT_CSV = S.ROOT / "docs/memoire/tableaux/section_5_4_1"
STATUTS = [A.CONFIRMEE, A.LITTERATURE, A.EMERGENTE]


def main() -> int:
    emp = S.empreintes()
    feats = json.loads(FEAT_JSON.read_text())["features"]
    assert len(feats) == 158, f"attendu 158 variables, obtenu {len(feats)}"
    feats_set = set(feats)
    cols_table = set(pq.read_schema(S.ROOT / "data/processed/ml_dataset.parquet").names)

    # ── Index candidate -> colonnes, colonne -> candidates ─────────────────────
    par_cand = {c: cols for c, _, _, cols in A.TABLE_A19_1}
    stat_cand = {c: st for c, st, _, _ in A.TABLE_A19_1}
    couv_cand = {c: cv for c, _, cv, _ in A.TABLE_A19_1}
    col2cand = {}
    for cand, cols in par_cand.items():
        for c in cols:
            col2cand.setdefault(c, []).append(cand)

    # ── 4.1.2 Anomalies de correspondance ──────────────────────────────────────
    citees = set(col2cand)
    citees_absentes_table = sorted(citees - cols_table)
    citees_hors_modele = sorted((citees & cols_table) - feats_set)
    modele_non_citees = sorted(feats_set - citees)
    multi_citees = {c: v for c, v in sorted(col2cand.items()) if len(v) > 1}

    anomalies = pd.DataFrame(
        [{"type": "citée mais absente de la table canonique", "colonne": c,
          "candidates": ";".join(col2cand[c]),
          "statuts": ";".join(sorted({stat_cand[x] for x in col2cand[c]}))}
         for c in citees_absentes_table] +
        [{"type": "citée et présente dans la table, mais hors des 158", "colonne": c,
          "candidates": ";".join(col2cand[c]),
          "statuts": ";".join(sorted({stat_cand[x] for x in col2cand[c]}))}
         for c in citees_hors_modele] +
        [{"type": "dans les 158 mais citée par aucune candidate", "colonne": c,
          "candidates": "", "statuts": ""} for c in modele_non_citees] +
        [{"type": "citée par plusieurs candidates", "colonne": c,
          "candidates": ";".join(v),
          "statuts": ";".join(sorted({stat_cand[x] for x in v}))}
         for c, v in multi_citees.items()])
    anomalies.to_csv(OUT_CSV / "t54_reconciliation_anomalies.csv", index=False)

    # ── 4.1.4 Reproduction des agrégats A19.2 (colonnes DÉDOUBLONNÉES) ─────────
    masse = {}
    for seg, p in SHAP.items():
        d = pd.read_csv(p)
        if set(d["feature"]) != feats_set:
            raise RuntimeError(f"STOP : c08_shap_ranks_{seg}.csv ne couvre pas les 158 variables.")
        masse[seg] = dict(zip(d["feature"], d["pct_du_total"]))

    obtenu, ecarts = {}, []
    cols_par_statut = {}
    for st in STATUTS:
        cands = [c for c, s2, _, _ in A.TABLE_A19_1 if s2 == st]
        cols = sorted({c for cd in cands for c in par_cand[cd]})       # dédoublonnage
        cols_par_statut[st] = cols
        dans_modele = [c for c in cols if c in feats_set]
        obtenu[st] = {
            "candidates": len(cands), "colonnes": len(cols),
            "colonnes_dans_modele": len(dans_modele),
            "bas": round(sum(masse["bas"][c] for c in dans_modele), 2),
            "haut": round(sum(masse["haut"][c] for c in dans_modele), 2)}
    toutes = sorted({c for cols in cols_par_statut.values() for c in cols})
    toutes_modele = [c for c in toutes if c in feats_set]
    obtenu["Total"] = {
        "candidates": len(A.TABLE_A19_1), "colonnes": len(toutes),
        "colonnes_dans_modele": len(toutes_modele),
        "bas": round(sum(masse["bas"][c] for c in toutes_modele), 2),
        "haut": round(sum(masse["haut"][c] for c in toutes_modele), 2)}

    for cle, att in A.A19_2_ATTENDU.items():
        for champ in ("candidates", "colonnes", "bas", "haut"):
            if obtenu[cle][champ] != att[champ]:
                ecarts.append({"ligne": cle, "champ": champ,
                               "attendu_memoire": att[champ], "obtenu": obtenu[cle][champ]})

    # contrôle complémentaire : colonnes non rattachées
    non_ratt = sorted(cols_table - citees)
    non_ratt_modele = sorted(feats_set - citees)
    nr = {"colonnes": len(non_ratt), "dans_le_modele": len(non_ratt_modele),
          "bas": round(sum(masse["bas"][c] for c in non_ratt_modele), 2),
          "haut": round(sum(masse["haut"][c] for c in non_ratt_modele), 2)}
    for champ, att in A.NON_RATTACHEES_ATTENDU.items():
        if nr[champ] != att:
            ecarts.append({"ligne": "non rattachées", "champ": champ,
                           "attendu_memoire": att, "obtenu": nr[champ]})

    a19 = pd.DataFrame([{"ligne": k, **v} for k, v in obtenu.items()])
    a19.to_csv(OUT_CSV / "t54_reproduction_a19_2.csv", index=False)

    # ── 4.1.3 Confrontation aux fichiers du dépôt ──────────────────────────────
    depot = []
    mat = S.ROOT / "docs/memoire/tableaux/annexe_22/matrice_correspondance_annexe_19.csv"
    if mat.exists():
        m = pd.read_csv(mat)
        for cand in sorted(set(par_cand) | set(m["candidate"])):
            ligne = m[m["candidate"] == cand]
            if ligne.empty:
                depot.append({"fichier": mat.name, "candidate": cand, "ecart":
                              "présente dans la table du mémoire, absente du fichier du dépôt"})
                continue
            if cand not in par_cand:
                depot.append({"fichier": mat.name, "candidate": cand, "ecart":
                              "présente dans le fichier du dépôt, absente de la table du mémoire"})
                continue
            r = ligne.iloc[0]
            if r["statut_triangulation"] != stat_cand[cand]:
                depot.append({"fichier": mat.name, "candidate": cand, "ecart":
                              f"statut « {r['statut_triangulation']} » au dépôt contre "
                              f"« {stat_cand[cand]} » au mémoire"})
            cd = set() if pd.isna(r["colonnes_cibles"]) else \
                {x.strip() for x in str(r["colonnes_cibles"]).split(";") if x.strip()}
            cm = set(par_cand[cand])
            if cd != cm:
                depot.append({"fichier": mat.name, "candidate": cand, "ecart":
                              f"colonnes : au dépôt seulement {sorted(cd - cm)} ; "
                              f"au mémoire seulement {sorted(cm - cd)}"})
        # agrégat par statut du fichier du dépôt (somme par candidate, non dédoublonnée)
        agg = m.groupby("statut_triangulation")[
            ["contribution_bas_pct_masse_segment", "contribution_haut_pct_masse_segment"]].sum()
        for st in STATUTS:
            if st in agg.index:
                for champ, col in (("bas", "contribution_bas_pct_masse_segment"),
                                   ("haut", "contribution_haut_pct_masse_segment")):
                    v = round(float(agg.loc[st, col]), 2)
                    if v != obtenu[st][champ]:
                        depot.append({"fichier": mat.name, "candidate": f"(agrégat {st})",
                                      "ecart": f"contribution {champ} : {v} au dépôt contre "
                                               f"{obtenu[st][champ]} au mémoire"})
    autres = sorted(set(S.ROOT.glob("outputs/codebook_canonique_*.csv")) |
                    set(S.ROOT.glob("notebooks/outputs/06_codebook_features.csv")))
    vocab = {A.CONFIRMEE, A.LITTERATURE, A.EMERGENTE,
             "Confirmee", "Litterature", "Emergente"}
    for f in autres:
        d = pd.read_csv(f)
        # une colonne ne porte le statut de triangulation que si ses modalités
        # appartiennent au vocabulaire confirmée / littérature / émergente
        porteuses = [c for c in d.columns
                     if d[c].dropna().astype(str).isin(vocab).any()]
        if porteuses:
            note = f"porte un statut de triangulation dans {porteuses}"
        else:
            cands = [c for c in d.columns if "statut" in c.lower()]
            note = ("ne porte AUCUN statut de triangulation ; "
                    + (f"la colonne `{cands[0]}` est un statut technique "
                       f"({sorted(set(d[cands[0]].dropna().astype(str)))[:3]}…)"
                       if cands else "aucune colonne de statut"))
        depot.append({"fichier": str(f.relative_to(S.ROOT)), "candidate": "(fichier entier)",
                      "ecart": f"{len(d)} lignes ; {note}"})
    depot_df = pd.DataFrame(depot)
    depot_df.to_csv(OUT_CSV / "t54_ecarts_depot_vs_memoire.csv", index=False)

    # ── 4.1 point E : colonnes de traçabilité ──────────────────────────────────
    tracabilite = {c: (c in feats_set) for c in ("event_narcisses_source", "event_ski_source")}

    # ── Périmètres d'ablation ──────────────────────────────────────────────────
    def cols_de(cands):
        return sorted({c for cd in cands for c in par_cand[cd] if c in feats_set})

    perimetres = {
        "A1": cols_de(A.CANDIDATES_A1),
        "vmcv": cols_de(A.CANDIDATES_STRATE_VMCV),
        "A3": [c for c in cols_par_statut[A.LITTERATURE] if c in feats_set],
        "A4": [c for c in cols_par_statut[A.CONFIRMEE] if c in feats_set],
        "exclues_du_perimetre": cols_de(A.EXCLUES_DU_PERIMETRE),
    }
    perimetres["A2"] = sorted(set(perimetres["A1"]) | set(perimetres["vmcv"]))

    res = {"empreintes": emp, "n_features": len(feats),
           "anomalies": {"citees_absentes_table": citees_absentes_table,
                         "citees_hors_modele": citees_hors_modele,
                         "modele_non_citees": modele_non_citees,
                         "multi_citees": multi_citees},
           "a19_2_obtenu": obtenu, "a19_2_attendu": A.A19_2_ATTENDU,
           "non_rattachees": nr, "non_rattachees_attendu": A.NON_RATTACHEES_ATTENDU,
           "ecarts_a19_2": ecarts, "ecarts_depot": depot,
           "tracabilite": tracabilite, "perimetres": perimetres,
           "masse_pct": {s: {c: masse[s][c] for c in feats} for s in ("bas", "haut")}}
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    # ── Restitution ────────────────────────────────────────────────────────────
    print("=" * 78)
    print("VÉRIF 4 — SECTION 4.1 : RÉCONCILIATION (porte bloquante)")
    print("=" * 78)
    print(f"\nempreintes : dataset {emp['dataset']} | modèles {emp['modele_bas']}/{emp['modele_haut']} "
          f"| menu {emp['calibration_H24']}")
    print(f"commit {emp['commit']}")
    print(f"\n[4.1.2] anomalies de correspondance")
    print(f"  citées mais absentes de la table canonique : {len(citees_absentes_table)} {citees_absentes_table}")
    print(f"  citées, dans la table, hors des 158        : {len(citees_hors_modele)} {citees_hors_modele}")
    print(f"  dans les 158, citées par aucune candidate  : {len(modele_non_citees)}")
    for c in modele_non_citees:
        print(f"      {c}")
    print(f"  citées par plusieurs candidates            : {len(multi_citees)}")
    for c, v in multi_citees.items():
        print(f"      {c} <- {v} (statuts : {sorted({stat_cand[x] for x in v})})")
    print(f"\n[4.1 point E] colonnes de traçabilité présentes dans les 158 : {tracabilite}")

    print(f"\n[4.1.4] reproduction du tableau A19.2")
    print(f"{'ligne':<14}{'cand.':>7}{'col.':>7}{'/modèle':>9}{'bas':>9}{'haut':>9}   contrôle")
    for cle in [A.CONFIRMEE, A.LITTERATURE, A.EMERGENTE, "Total"]:
        o, att = obtenu[cle], A.A19_2_ATTENDU[cle]
        ok = all(o[k] == att[k] for k in ("candidates", "colonnes", "bas", "haut"))
        print(f"{cle:<14}{o['candidates']:>7}{o['colonnes']:>7}{o['colonnes_dans_modele']:>9}"
              f"{o['bas']:>9}{o['haut']:>9}   {'OK' if ok else 'ÉCART'}"
              f"{'' if ok else f'  (mémoire : {att})'}")
    print(f"{'non rattachées':<14}{'':>7}{nr['colonnes']:>7}{nr['dans_le_modele']:>9}"
          f"{nr['bas']:>9}{nr['haut']:>9}   "
          f"{'OK' if all(nr[k] == v for k, v in A.NON_RATTACHEES_ATTENDU.items()) else 'ÉCART'}")

    print(f"\n[4.1.3] écarts entre le dépôt et la table du mémoire : {len(depot)}")
    for e in depot:
        print(f"  [{e['fichier']}] {e['candidate']} : {e['ecart']}")

    print(f"\n[périmètres d'ablation]")
    for k in ("A1", "vmcv", "A2", "A3", "A4", "exclues_du_perimetre"):
        print(f"  {k:22} {len(perimetres[k]):>3} colonnes")
    print(f"  A1 : {perimetres['A1']}")
    print(f"  exclues (grain) : {perimetres['exclues_du_perimetre']}")

    if ecarts:
        print("\n" + "!" * 78)
        print("STOP — le tableau A19.2 n'est pas reproduit. Écarts :")
        for e in ecarts:
            print(f"  {e}")
        print("Aucune ablation n'est lancée. Rapport d'écart écrit dans _reconciliation.json.")
        print("!" * 78)
        return 1

    print(f"\n[OK] porte franchie — A19.2 reproduit sur les quatre lignes. {OUT_JSON.name} écrit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
