#!/usr/bin/env python3
"""
V1 — Le codebook de 209 entrees : la phrase de la section 4.3.1 decrit-elle la
source APC ou la table canonique de modelisation ?

Lecture seule. Denombre :
  (1) les colonnes de l'export APC brut (data/raw/*.csv), avant tout enrichissement ;
  (2) les colonnes de la table gold mono-source APC (apc_stacked.parquet) ;
  (3) les colonnes de ml_dataset.parquet (jeu canonique gele) ;
  (4) l'inventaire des codebooks / dictionnaires du depot avec leur nombre d'entrees
      et l'etape de la chaine a laquelle chacun se rapporte.

Sorties : docs/memoire/verifs/complements/v1_codebook_*.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _garde import ROOT, garde  # noqa: E402

OUT = Path(__file__).resolve().parent

RAW_DIR = ROOT / "data" / "raw"
APC_STACKED = ROOT / "data" / "processed" / "sources" / "apc_stacked.parquet"
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"

# Inventaire des artefacts documentaires candidats au titre de « codebook ».
# (chemin, objet documente, etape de la chaine)
CANDIDATS = [
    ("outputs/codebook_canonique_ba493568.csv",
     "colonnes du jeu canonique gele ba493568 (dtype, statut, appartenance aux 158 features, "
     "taux de NaN, plage ou modalites, libelle FR, unite)",
     "table de modelisation (gold, apres toutes les jointures)"),
    ("outputs/codebook_canonique_416bb90b.csv",
     "idem, generation precedente v1.9",
     "table de modelisation (generation superseedee)"),
    ("docs/memoire/tableaux/section_4_4_3/dictionnaire_colonnes_canonique.csv",
     "dictionnaire etendu des colonnes du jeu canonique (definition, mode d'obtention, "
     "source de definition avec ligne de code, grain de variation, taux de NaN par periode)",
     "table de modelisation (gold)"),
    ("notebooks/outputs/06_codebook_features.csv",
     "features du notebook 06 (prefixe, type, description, source, formule)",
     "analyse de features, generation anterieure au gel"),
    ("docs/memoire/verifs/section_4_3_1/annexe_X_catalogue_sources.md",
     "catalogue des sources amont (fournisseur, acquisition, perimetre)",
     "sources brutes"),
    ("docs/glossaire.md",
     "glossaire des termes et des champs",
     "transversal"),
]


def compte_entrees(path: Path) -> int | None:
    """Nombre d'entrees d'un artefact documentaire (lignes hors en-tete pour un CSV)."""
    if not path.exists():
        return None
    if path.suffix == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return max(0, sum(1 for _ in csv.reader(fh)) - 1)
    return None


def main() -> None:
    garde()
    print("=" * 78)
    print("V1 — CODEBOOK DE 209 ENTREES : SOURCE APC OU TABLE CANONIQUE ?")
    print("=" * 78)

    # ── (1) export APC brut ────────────────────────────────────────────────────
    print("\n[1] Export APC brut (data/raw/, immuable, avant tout enrichissement)")
    lignes_raw = []
    entetes = {}
    for f in sorted(RAW_DIR.glob("*.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            header = fh.readline().rstrip("\n").rstrip("\r")
        cols = header.split(",")
        entetes[f.name] = cols
        lignes_raw.append({"fichier": str(f.relative_to(ROOT)), "n_colonnes": len(cols)})
        print(f"    {f.relative_to(ROOT)} : {len(cols)} colonnes")
    schemas = {tuple(v) for v in entetes.values()}
    print(f"    schemas distincts entre les {len(entetes)} exports : {len(schemas)}")
    n_raw = len(next(iter(schemas)))

    pd.DataFrame(lignes_raw).to_csv(OUT / "v1_colonnes_export_apc_brut.csv", index=False)
    pd.DataFrame({"ordre": range(1, n_raw + 1), "colonne": list(next(iter(schemas)))}).to_csv(
        OUT / "v1_schema_export_apc_brut.csv", index=False)

    # ── (2) table gold mono-source APC ─────────────────────────────────────────
    fa = pq.ParquetFile(APC_STACKED)
    n_apc_stacked = len(fa.schema_arrow.names)
    print(f"\n[2] Table gold mono-source APC : {APC_STACKED.relative_to(ROOT)}")
    print(f"    {n_apc_stacked} colonnes, {fa.metadata.num_rows} lignes")

    # ── (3) jeu canonique ──────────────────────────────────────────────────────
    fm = pq.ParquetFile(ML_DATASET)
    n_ml = len(fm.schema_arrow.names)
    print(f"\n[3] Jeu canonique : {ML_DATASET.relative_to(ROOT)}")
    print(f"    {n_ml} colonnes, {fm.metadata.num_rows} lignes")

    # ── (4) inventaire des codebooks ───────────────────────────────────────────
    print("\n[4] Inventaire des codebooks et dictionnaires")
    inv = []
    for rel, objet, etape in CANDIDATS:
        p = ROOT / rel
        n = compte_entrees(p)
        inv.append({"chemin": rel, "existe": p.exists(),
                    "n_entrees": n if n is not None else "",
                    "objet_documente": objet, "etape_chaine": etape})
        print(f"    {rel:70} entrees={n if n is not None else 'n/a (markdown)'}")
    pd.DataFrame(inv).to_csv(OUT / "v1_inventaire_codebooks.csv", index=False)

    # ── (5) confrontation ──────────────────────────────────────────────────────
    cb = pd.read_csv(ROOT / "outputs/codebook_canonique_ba493568.csv")
    cols_cb = set(cb["colonne"])
    cols_raw = set(next(iter(schemas)))
    cols_apc_stacked = set(fa.schema_arrow.names)
    cols_ml = set(fm.schema_arrow.names)

    print("\n[5] Confrontation des perimetres")
    print(f"    entrees du codebook canonique                      : {len(cols_cb)}")
    print(f"    == colonnes de ml_dataset.parquet ?                : {cols_cb == cols_ml}")
    print(f"    colonnes de l'export APC brut couvertes par le nom : "
          f"{len(cols_cb & cols_raw)}/{len(cols_raw)} (les noms bruts sont renommes en amont)")

    # Devenir de chaque colonne brute : renommage semantique canonique de
    # scripts/sources/stack_raw_csv.py (FINAL_COLUMN_RENAMES), puis presence dans
    # ml_dataset.parquet. Mesure la contribution reelle de la source APC aux 209.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stack_raw_csv", ROOT / "scripts" / "sources" / "stack_raw_csv.py")
    srp = importlib.util.module_from_spec(spec)
    sys.modules["stack_raw_csv"] = srp
    spec.loader.exec_module(srp)
    ren = srp.FINAL_COLUMN_RENAMES
    # `depart` / `arrivee` (heures brutes) sont converties en horodatages nommes
    # `depart_datetime` / `arrivee_datetime` dans apply_schema (stack_raw_csv.py:581-597)
    # AVANT l'application de FINAL_COLUMN_RENAMES : on chaine les deux renommages.
    pre_ren = {"depart": "depart_datetime", "arrivee": "arrivee_datetime"}
    devenir = []
    for c in next(iter(schemas)):
        cible = ren.get(pre_ren.get(c, c), pre_ren.get(c, c))
        devenir.append({"colonne_brute": c, "nom_canonique": cible,
                        "present_dans_apc_stacked": cible in cols_apc_stacked,
                        "present_dans_ml_dataset": cible in cols_ml})
    dev = pd.DataFrame(devenir)
    dev.to_csv(OUT / "v1_devenir_colonnes_brutes.csv", index=False)
    n_survivantes = int(dev["present_dans_ml_dataset"].sum())
    print(f"    colonnes brutes survivant dans ml_dataset          : "
          f"{n_survivantes}/{len(dev)} (apres renommage semantique)")
    print(f"    colonnes brutes survivant dans apc_stacked         : "
          f"{int(dev['present_dans_apc_stacked'].sum())}/{len(dev)}")

    resume = pd.DataFrame([
        {"perimetre": "export APC brut (data/raw/*.csv)", "n_colonnes": n_raw,
         "etape": "raw — immuable, avant tout enrichissement"},
        {"perimetre": "schema normalise de dedoublonnage (RAW_SCHEMA_COLUMNS)", "n_colonnes": 31,
         "etape": "raw — apres retrait de type_jour"},
        {"perimetre": "apc_stacked.parquet (gold mono-source APC)", "n_colonnes": n_apc_stacked,
         "etape": "silver/gold mono-source — empilement + dimension gare"},
        {"perimetre": "ml_dataset.parquet (jeu canonique gele ba493568)", "n_colonnes": n_ml,
         "etape": "gold — table de modelisation, apres toutes les jointures"},
        {"perimetre": "codebook_canonique_ba493568.csv", "n_colonnes": len(cols_cb),
         "etape": "documentation de la table de modelisation"},
    ])
    resume.to_csv(OUT / "v1_resume_perimetres.csv", index=False)
    print("\n" + resume.to_string(index=False))

    print("\n[6] Verdict")
    if len(cols_cb) == n_ml and n_raw != len(cols_cb):
        print(f"    Le codebook de {len(cols_cb)} entrees documente ml_dataset.parquet "
              f"({n_ml} colonnes), PAS l'export APC brut ({n_raw} colonnes).")
    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
