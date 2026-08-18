#!/usr/bin/env python3
"""
A5 — Génération des deux annexes manquantes du §4.5.

Annexe A (§4.5.4, tableau 13) — détail NOMINAL des retraits de variables à chaque étape
de la chaîne de sélection 209 → 179 → 171 → 172 → 170 → 158.

Annexe B (§4.5.6) — détail des contributions par variable, avec rattachement à la variable
candidate qualitative, reproduisant les couvertures de 98,6 % (bas) et 98,9 % (haut).

LECTURE SEULE sur tous les artefacts canoniques. Sorties déterministes (aucun horodatage),
écrites uniquement sous docs/memoire/tableaux/section_4_5_4/ et docs/memoire/verifs/section_4_5/.

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/a5_annexes.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[4]
OUT_VERIF = Path(__file__).resolve().parent
OUT_TAB = ROOT / "docs/memoire/tableaux/section_4_5_4"

ML = ROOT / "data/processed/ml_dataset.parquet"
HASH_ATTENDU = "ba493568"
CONSO = ROOT / "archive/explorations/consolidation_finale/outputs"
VIVIER_179 = CONSO / "etape_04_shap_importance_bas.csv"
F171 = CONSO / "etape_04bis_features_171.json"
F170 = CONSO / "etape_04bis_v2_features_170f.json"
RETIREES_8 = CONSO / "etape_04bis_features_retirees_8.csv"
F158 = ROOT / "outputs/couche2/features_158f_sans_simba.json"
SHAP = {s: ROOT / f"outputs/confirmation/c08_shap_ranks_{s}.csv" for s in ("bas", "haut")}
CODEBOOK = ROOT / "outputs/codebook_canonique_ba493568.csv"
DICO = ROOT / "docs/memoire/tableaux/section_4_4_3/dictionnaire_colonnes_canonique.csv"
MAPPING = ROOT / "docs/memoire/tableaux/annexe_22/mapping_candidates_colonnes_v2.csv"

DENIVELE = "spatial_denivele_troncon_m"

# Sous-catégories du bloc « retrait structurel » (reconciliation_209_179_158.md §3.2)
SOUS_CAT_STRUCTUREL = {
    "identifiants et clés": [
        "id_source_file", "id_gare_depart", "id_gare_arrivee", "id_gare_depart_bpuic",
        "id_gare_arrivee_bpuic", "id_statpop_reference_year", "horaire_annee_horaire",
        "horaire_numero_train", "horaire_service_id_complet", "base_date",
        "base_depart_datetime", "base_arrivee_datetime"],
    "colonnes techniques (sens, offre)": [
        "base_sens", "base_offre_1ere_classe", "base_offre_2eme_classe", "base_offre_total"],
    "cibles": [
        "target_voyageurs_1ere_classe", "target_voyageurs_2eme_classe",
        "target_voyageurs_total"],
    "drapeaux de provenance": [
        "spatial_statpop_source_depart", "spatial_statpop_source_arrivee",
        "vmcv_source_depart", "vmcv_source_arrivee", "simba_source_depart",
        "simba_source_arrivee"],
    "emplois (STATENT, ADR-064 amendement)": [
        "spatial_gare_depart_emplois_500m_total", "spatial_gare_depart_emplois_500m_services",
        "spatial_gare_arrivee_emplois_500m_total",
        "spatial_gare_arrivee_emplois_500m_services"],
    "réintroduite ensuite dans le modèle": [DENIVELE],
}

ETAPES = [
    ("E1", "Retrait structurel", "ADR-048", 209, 179,
     "Complément du vivier soumis à la sélection : identifiants, clés, cibles, drapeaux "
     "de provenance, capacités d'offre (fuite anti-causale ADR-034), emplois STATENT "
     "(ADR-064 amendement)."),
    ("E2", "Nettoyage §1 — contribution nulle", "ADR-054 §1", 179, 171,
     "mean|SHAP| = 0,000 exact dans les DEUX segments."),
    ("E3", "Ajout du dénivelé", "ADR-057", 171, 172,
     "Variable créée après la constitution du vivier ; seule marche positive de la chaîne."),
    ("E4", "Nettoyage §2 — gain nul", "ADR-054 §2", 172, 170,
     "Gain XGBoost = 0 dans les DEUX segments."),
    ("E5", "Retrait de la famille SIMBA", "ADR-061", 170, 158,
     "Fiabilité et déployabilité de la source (instabilité inter-millésimes, fuite de "
     "disponibilité, manquants structurels) — non le R²."),
]


def sha8(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


# ── Annexe A ────────────────────────────────────────────────────────────────────
def annexe_a(cols209, cb, dico):
    v179 = pd.read_csv(VIVIER_179)["feature"].tolist()
    f171 = json.loads(F171.read_text())["features"]
    f170 = json.loads(F170.read_text())["features"]
    f158 = json.loads(F158.read_text())["features"]
    ret8 = pd.read_csv(RETIREES_8)["feature"].tolist()
    ret2 = json.loads(F170.read_text())["removed_from_172"]
    simba12 = json.loads(F158.read_text())["simba_features_removed"]

    # Assertions bloquantes de volumétrie (chaîne rejouée nominalement)
    assert len(cols209) == 209, len(cols209)
    assert len(v179) == 179 and len(f171) == 171 and len(f170) == 170 and len(f158) == 158
    assert len(ret8) == 8 and len(ret2) == 2 and len(simba12) == 12
    struct30 = [c for c in cols209 if c not in v179]
    assert len(struct30) == 30, len(struct30)
    assert set(v179) - set(f171) == set(ret8)
    assert set(f171) | {DENIVELE} == set(f170) | set(ret2)
    assert set(f170) - set(f158) == set(simba12)

    inv_sous_cat = {c: k for k, v in SOUS_CAT_STRUCTUREL.items() for c in v}
    lignes = []
    for c in sorted(struct30):
        lignes.append({"etape": "E1", "operation": "retrait", "sous_categorie":
                       inv_sous_cat.get(c, "(non classée)"), "variable": c})
    for c in sorted(ret8):
        lignes.append({"etape": "E2", "operation": "retrait",
                       "sous_categorie": "mean|SHAP| = 0,000 exact (bas ET haut)",
                       "variable": c})
    lignes.append({"etape": "E3", "operation": "ajout",
                   "sous_categorie": "variable créée après le vivier (ADR-057)",
                   "variable": DENIVELE})
    for c in sorted(ret2):
        lignes.append({"etape": "E4", "operation": "retrait",
                       "sous_categorie": "gain XGBoost = 0 (bas ET haut)", "variable": c})
    for c in sorted(simba12):
        lignes.append({"etape": "E5", "operation": "retrait",
                       "sous_categorie": "famille SIMBA (12 simba_part_*)", "variable": c})

    d = pd.DataFrame(lignes)
    meta = {e[0]: e for e in ETAPES}
    d["libelle_etape"] = d["etape"].map(lambda e: meta[e][1])
    d["adr"] = d["etape"].map(lambda e: meta[e][2])
    d["n_avant"] = d["etape"].map(lambda e: meta[e][3])
    d["n_apres"] = d["etape"].map(lambda e: meta[e][4])
    d["motif_etape"] = d["etape"].map(lambda e: meta[e][5])
    d["famille"] = d["variable"].map(cb.set_index("colonne")["famille"])
    d["libelle_fr"] = d["variable"].map(cb.set_index("colonne")["libelle_fr"])
    d["dans_le_modele_gele_158"] = d["variable"].isin(f158)
    if "statut" in dico.columns:
        d["statut_dictionnaire"] = d["variable"].map(dico.set_index(dico.columns[0])["statut"])
    d = d[["etape", "libelle_etape", "adr", "n_avant", "n_apres", "operation",
           "sous_categorie", "variable", "famille", "libelle_fr",
           "dans_le_modele_gele_158", "motif_etape"]]
    d = d.sort_values(["etape", "sous_categorie", "variable"]).reset_index(drop=True)

    recap = pd.DataFrame([{"etape": e[0], "libelle": e[1], "adr": e[2],
                           "n_avant": e[3], "n_apres": e[4], "delta": e[4] - e[3],
                           "n_variables_listees": int((d["etape"] == e[0]).sum())}
                          for e in ETAPES])
    assert recap["delta"].abs().sum() == len(d), (recap["delta"].abs().sum(), len(d))
    return d, recap, f158


# ── Annexe B ────────────────────────────────────────────────────────────────────
def annexe_b(f158, cb):
    shap = {}
    for s, p in SHAP.items():
        x = pd.read_csv(p).rename(columns={
            "mean_abs_shap": f"mean_abs_shap_{s}", "rang": f"rang_{s}",
            "pct_du_total": f"pct_du_total_{s}"})
        shap[s] = x
    d = shap["bas"].merge(shap["haut"], on="feature", how="outer")
    assert len(d) == 158, len(d)

    m = pd.read_csv(MAPPING)
    lien = []
    for _, r in m.iterrows():
        for col in str(r["colonnes_cibles"]).split(";"):
            col = col.strip()
            if col:
                lien.append({"feature": col, "candidate": r["candidate"],
                             "code_thematique": r["code_thematique"],
                             "statut_triangulation": r["statut_triangulation"],
                             "section_de_reference": r["section_de_reference"]})
    lien = pd.DataFrame(lien)
    agg = (lien[lien["feature"].isin(d["feature"])]
           .groupby("feature")
           .agg(candidates=("candidate", lambda s: " ; ".join(sorted(set(s)))),
                n_candidates=("candidate", lambda s: len(set(s))),
                codes_thematiques=("code_thematique", lambda s: " ; ".join(sorted(set(s)))),
                sections_de_reference=("section_de_reference",
                                       lambda s: " ; ".join(sorted(set(map(str, s))))))
           .reset_index())
    d = d.merge(agg, on="feature", how="left")
    d["citee_par_une_candidate"] = d["candidates"].notna()
    d["famille"] = d["feature"].map(cb.set_index("colonne")["famille"])
    d["libelle_fr"] = d["feature"].map(cb.set_index("colonne")["libelle_fr"])
    d = d[["feature", "famille", "libelle_fr", "rang_bas", "mean_abs_shap_bas",
           "pct_du_total_bas", "rang_haut", "mean_abs_shap_haut", "pct_du_total_haut",
           "citee_par_une_candidate", "n_candidates", "candidates",
           "codes_thematiques", "sections_de_reference"]]
    d = d.sort_values("rang_bas").reset_index(drop=True)

    couv = []
    for s in ("bas", "haut"):
        tot = d[f"mean_abs_shap_{s}"].sum()
        cit = d.loc[d["citee_par_une_candidate"], f"mean_abs_shap_{s}"].sum()
        orp = tot - cit
        couv.append({"segment": s.upper(), "masse_totale": round(tot, 6),
                     "n_citees": int(d["citee_par_une_candidate"].sum()),
                     "masse_citee": round(cit, 6),
                     "part_citee_pct": round(100 * cit / tot, 2),
                     "n_orphelines": int((~d["citee_par_une_candidate"]).sum()),
                     "masse_orpheline": round(orp, 6),
                     "part_orpheline_pct": round(100 * orp / tot, 2)})
    return d, pd.DataFrame(couv)


def main() -> int:
    print("=== A5 — génération des deux annexes du §4.5 (lecture seule) ===")
    h = sha8(ML)
    if h != HASH_ATTENDU:
        raise RuntimeError(f"STOP : hash ml_dataset {h} != {HASH_ATTENDU}")
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    cols209 = list(pq.ParquetFile(ML).schema_arrow.names)
    cb = pd.read_csv(CODEBOOK)
    dico = pd.read_csv(DICO)

    a, recap_a, f158 = annexe_a(cols209, cb, dico)
    a.to_csv(OUT_TAB / "annexe_4_5_4_retraits_nominatifs.csv", index=False)
    recap_a.to_csv(OUT_TAB / "annexe_4_5_4_retraits_recapitulatif.csv", index=False)
    print(f"  Annexe A : {len(a)} variables listées sur 5 étapes "
          f"(assertions de chaîne : OK)")
    print(recap_a.to_string(index=False))

    b, couv = annexe_b(f158, cb)
    b.to_csv(OUT_TAB / "annexe_4_5_6_contributions_par_variable.csv", index=False)
    couv.to_csv(OUT_TAB / "annexe_4_5_6_couverture.csv", index=False)
    print(f"  Annexe B : {len(b)} variables")
    print(couv.to_string(index=False))

    # ── Rendus Markdown prêts à insérer ────────────────────────────────────────
    src = {"ml_dataset.parquet": HASH_ATTENDU,
           "c08_shap_ranks_bas.csv": sha8(SHAP["bas"]),
           "c08_shap_ranks_haut.csv": sha8(SHAP["haut"]),
           "features_158f_sans_simba.json": sha8(F158),
           "etape_04bis_v2_features_170f.json": sha8(F170),
           "etape_04bis_features_171.json": sha8(F171),
           "etape_04_shap_importance_bas.csv": sha8(VIVIER_179),
           "etape_04bis_features_retirees_8.csv": sha8(RETIREES_8),
           "mapping_candidates_colonnes_v2.csv": sha8(MAPPING)}
    entete = ("\n".join(f"| `{k}` | `{v}` |" for k, v in src.items()))

    ma = [
        "# Annexe — détail nominal des retraits de variables (§4.5.4, tableau 13)",
        "",
        "Table générée en lecture seule par "
        "`docs/memoire/verifs/section_4_5/a5_annexes.py`. Chaîne de sélection rejouée "
        "nominalement depuis les listes sérialisées, avec assertions bloquantes ; aucune "
        "recopie manuelle.",
        "", "## Empreintes des sources", "", "| Fichier | SHA256[:8] |", "|---|---|",
        entete, "",
        "## Récapitulatif de la chaîne", "", md_table(recap_a), "",
        "Identité comptable : `209 − 30 = 179`, puis `179 − 8 + 1 − 2 − 12 = 158`.",
        "", "## Détail nominal", "",
        md_table(a.drop(columns=["motif_etape"])), "",
        "## Motif par étape", "",
        md_table(recap_a[["etape", "libelle", "adr"]].assign(
            motif=[e[5] for e in ETAPES])),
    ]
    (OUT_TAB / "annexe_4_5_4_retraits_nominatifs.md").write_text("\n".join(ma))

    mb = [
        "# Annexe — contributions par variable et rattachement aux variables candidates (§4.5.6)",
        "",
        "Table générée en lecture seule par "
        "`docs/memoire/verifs/section_4_5/a5_annexes.py`. Contributions = `mean|SHAP|` "
        "publiées par `scripts/confirmation/c08_shap_segments.py` sur les modèles gelés "
        "`e4ddfccd` / `df6a11c5`, périmètre H25. Rattachement = mapping de jugement "
        "`mapping_candidates_colonnes_v2.csv` (31 candidates), lu tel quel.",
        "", "## Empreintes des sources", "", "| Fichier | SHA256[:8] |", "|---|---|",
        entete, "",
        "## Couverture — reproduction des 98,6 % et 98,9 % du manuscrit", "",
        md_table(couv), "",
        "## Détail par variable (158 lignes, tri par rang du segment bas)", "",
        md_table(b),
    ]
    (OUT_TAB / "annexe_4_5_6_contributions_par_variable.md").write_text("\n".join(mb))

    (OUT_VERIF / "a5_annexes.json").write_text(json.dumps({
        "empreintes_sources": src,
        "annexe_A": {"n_lignes": int(len(a)),
                     "recapitulatif": recap_a.to_dict(orient="records"),
                     "sorties": ["docs/memoire/tableaux/section_4_5_4/annexe_4_5_4_retraits_nominatifs.csv",
                                 "docs/memoire/tableaux/section_4_5_4/annexe_4_5_4_retraits_nominatifs.md",
                                 "docs/memoire/tableaux/section_4_5_4/annexe_4_5_4_retraits_recapitulatif.csv"]},
        "annexe_B": {"n_lignes": int(len(b)),
                     "couverture": couv.to_dict(orient="records"),
                     "sorties": ["docs/memoire/tableaux/section_4_5_4/annexe_4_5_6_contributions_par_variable.csv",
                                 "docs/memoire/tableaux/section_4_5_4/annexe_4_5_6_contributions_par_variable.md",
                                 "docs/memoire/tableaux/section_4_5_4/annexe_4_5_6_couverture.csv"]},
    }, indent=2, ensure_ascii=False))
    print(f"[OK] annexes dans {OUT_TAB.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
