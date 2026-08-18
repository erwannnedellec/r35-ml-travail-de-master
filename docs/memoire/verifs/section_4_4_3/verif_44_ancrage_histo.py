#!/usr/bin/env python3
"""Vérif §4.4 (préparation des données) — ancrage des variables historiques
`histo_*` à travers la refonte d'horaire H24 -> H25.

Objet
-----
Établir, en lecture seule sur le dataset canonique figé `ml_dataset.parquet`
(empreinte SHA256[:8] = `ba493568`, gel v2 ADR-076), les chiffres du contrefactuel
d'ancrage des features `histo_*` :

  T1. Contrefactuel « sans le mécanisme » : part des observations H25 qui seraient
      PRIVÉES d'antécédent H22-H24 selon la clé d'identification employée
      (numéro de train seul, ou service_id complet = numéro + heure d'origine).
  T2. Roster de renumérotation : numéros distincts H24 / H25, disparus, nouveaux.
  T3. Contrefactuel clé complète (tronçon x numéro x type_jour) et repli
      (tronçon x type_jour), à la manière d'ADR-072.
  T4. Payoff réel « avec le mécanisme » : couverture effective de
      `histo_voyageurs_2eme_classe_lag2` sur H25 (globale et par type de jour).

Mécanisme vérifié (rappel, non recalculé ici — cf. code producteur)
-------------------------------------------------------------------
La clé de groupement des `histo_*` est, dans
`scripts/pipeline/add_features_to_raw_stacked.py:114-120` :

    GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes",
                  "id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]

L'appariement se fait donc par sens x créneau horaire ancré (±30 min) x type de
jour x tronçon — PAS par identifiant de service. `creneau_anchor_30` affecte à
chaque ligne l'heure d'origine (minutes depuis minuit) du service H22-H24 le plus
proche, la tolérance ±30 min étant appliquée à
`add_features_to_raw_stacked.py:372` (`best_dist <= CRENEAU_LARGEUR_MIN`, avec
`CRENEAU_LARGEUR_MIN = 30`, ligne 104). Le service_id complet
(`{numéro}_{HHhMM}`) n'existe que comme métadonnée hors clé.

Registre : ADR-042 (créneau ±30, cœur), ADR-043 (test RF-1), ADR-044 (ajout
`base_sens`), ADR-062 (clé 5-termes + cutoff mensuel) ; prédécesseur fragile
ADR-037 (`annee_horaire x service_id x type_jour`). Toutes datées 2026-06-04 ->
06-16, antérieures au gel `ba493568` (ADR-076, 2026-07-11).

LECTURE SEULE. Écrit trois CSV récapitulatifs à côté de ce script.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
CANON = ROOT / "data" / "processed" / "ml_dataset.parquet"
STAGE08 = ROOT / "data" / "processed" / "stage_08_features.parquet"

HASH_ATTENDU = "ba493568"
ANNEES_ANCRES = ["H22", "H23", "H24"]  # cf. add_features_to_raw_stacked.py:101
LAG2 = "histo_voyageurs_2eme_classe_lag2"

COLS = [
    "horaire_annee_horaire",
    "horaire_numero_train",
    "horaire_service_id_complet",
    "cal_type_jour_3classes",
    "id_gare_depart_bpuic",
    "id_gare_arrivee_bpuic",
    LAG2,
]


def _empreinte(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def _clef(d: pd.DataFrame, cols: list[str]) -> pd.Series:
    return d[cols].astype(str).agg("|".join, axis=1)


def main() -> None:
    print("=" * 78)
    print("VÉRIF §4.4 — ANCRAGE DES VARIABLES HISTORIQUES (refonte H24 -> H25)")
    print("=" * 78)

    emp = _empreinte(CANON)
    print(f"Source canonique : {CANON.name}  SHA256[:8] = {emp}")
    if emp != HASH_ATTENDU:
        print(f"  ATTENTION : empreinte attendue {HASH_ATTENDU} — écart, chiffres à revalider.")
    else:
        print(f"  Empreinte conforme au gel v2 (ADR-076).")

    df = pd.read_parquet(CANON, columns=COLS)
    ah = df["horaire_annee_horaire"].astype(str)
    h25 = df[ah == "H25"].copy()
    past = df[ah.isin(ANNEES_ANCRES)].copy()
    N = len(h25)
    print(f"\nObservations H25 : {N:,}   |   antécédents H22-H24 : {len(past):,}")

    # ---- T1 : contrefactuel « identifiant de service » ----------------------
    print("\n--- T1. CONTREFACTUEL SANS MÉCANISME (privation d'historique H25) ---")
    t1_rows = []
    for col, libelle in [
        ("horaire_service_id_complet", "service_id complet (numéro + heure d'origine) — clé ADR-037"),
        ("horaire_numero_train", "numéro de train seul (identifiant de service naturel)"),
    ]:
        past_set = set(past[col].dropna().unique())
        in_past = h25[col].isin(past_set)
        match = float(in_past.mean() * 100)
        orphan = 100.0 - match
        t1_rows.append({
            "cle_identification": libelle,
            "colonne": col,
            "cles_distinctes_H22_H24": len(past_set),
            "H25_apparie_pct": round(match, 2),
            "H25_prive_historique_pct": round(orphan, 2),
            "H25_prive_historique_n": int((~in_past).sum()),
        })
        print(f"  [{col}] apparié {match:6.2f}%  | PRIVÉ {orphan:6.2f}%  "
              f"(clés distinctes H22-H24 = {len(past_set)})")
    t1 = pd.DataFrame(t1_rows)

    # ---- T2 : roster de renumérotation --------------------------------------
    print("\n--- T2. ROSTER DE RENUMÉROTATION (numero_train) ---")
    h24_nums = set(df.loc[ah == "H24", "horaire_numero_train"].dropna().unique())
    h25_nums = set(h25["horaire_numero_train"].dropna().unique())
    maintenus = h24_nums & h25_nums
    disparus = h24_nums - h25_nums
    nouveaux = h25_nums - h24_nums
    t2 = pd.DataFrame([{
        "numeros_distincts_H24": len(h24_nums),
        "numeros_distincts_H25": len(h25_nums),
        "maintenus_H24_et_H25": len(maintenus),
        "disparus_de_H24": len(disparus),
        "nouveaux_en_H25": len(nouveaux),
    }])
    print(t2.to_string(index=False))
    print(f"  -> 52 attendu (ADR-038/041) : {'OK' if len(disparus) == 52 else 'ÉCART'}")

    # ---- T3 : contrefactuel clé complète vs repli (ADR-072) -----------------
    print("\n--- T3. CONTREFACTUEL CLÉ COMPLÈTE vs REPLI (ADR-072) ---")
    full_keys = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic",
                 "horaire_numero_train", "cal_type_jour_3classes"]
    repli_keys = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic", "cal_type_jour_3classes"]
    past_full = set(_clef(past, full_keys))
    past_repli = set(_clef(past, repli_keys))
    h25_full = _clef(h25, full_keys)
    h25_repli = _clef(h25, repli_keys)
    m_full = h25_full.isin(past_full)
    m_repli_only = (~m_full) & (h25_repli.isin(past_repli))
    m_none = (~m_full) & (~h25_repli.isin(past_repli))
    num_orphan = ~h25["horaire_numero_train"].isin(h24_nums)  # numéro absent de H24
    t3 = pd.DataFrame([{
        "cle_complete_troncon_numero_typejour_pct": round(float(m_full.mean() * 100), 2),
        "numero_orphelin_renumerote_pct": round(float(num_orphan.mean() * 100), 2),
        "repli_troncon_typejour_seul_pct": round(float(m_repli_only.mean() * 100), 2),
        "sans_aucun_repli_pct": round(float(m_none.mean() * 100), 2),
    }])
    print(t3.to_string(index=False))
    print("  (ADR-072 : 53.69 % clé complète, ~42.36 % basculent vers le repli)")

    # ---- T4 : payoff réel « avec le mécanisme » -----------------------------
    print("\n--- T4. AVEC LE MÉCANISME (frozen) : couverture histo_*_lag2 sur H25 ---")
    lag = h25[LAG2]
    cov_glob = float(lag.notna().mean() * 100)
    print(f"  Global : apparié {cov_glob:.2f}%  | NaN résiduel {100 - cov_glob:.2f}% "
          f"(n = {int(lag.isna().sum()):,})")
    t4_rows = [{
        "perimetre": "global", "n": int(len(h25)),
        "couverture_histo_pct": round(cov_glob, 2),
        "nan_residuel_pct": round(100 - cov_glob, 2),
    }]
    for tj, g in h25.groupby("cal_type_jour_3classes", observed=True):
        c = float(g[LAG2].notna().mean() * 100)
        t4_rows.append({
            "perimetre": str(tj), "n": int(len(g)),
            "couverture_histo_pct": round(c, 2),
            "nan_residuel_pct": round(100 - c, 2),
        })
        print(f"    {str(tj):16s} n={len(g):7,d}  couverture={c:.2f}%")
    t4 = pd.DataFrame(t4_rows)

    # Corroboration facultative : couverture de l'ancre elle-même (stage_08)
    if STAGE08.exists():
        s = pd.read_parquet(
            STAGE08, columns=["horaire_annee_horaire", "creneau_anchor_30"])
        s25 = s[s["horaire_annee_horaire"].astype(str) == "H25"]
        anc_cov = float(s25["creneau_anchor_30"].notna().mean() * 100)
        print(f"\n  [stage_08] couverture de l'ancre créneau ±30 min sur H25 : {anc_cov:.2f}%")

    # ---- Export -------------------------------------------------------------
    t1.to_csv(DOSSIER / "verif_44_ancrage_histo_task1_contrefactuel.csv",
              index=False, encoding="utf-8-sig")
    t2.to_csv(DOSSIER / "verif_44_ancrage_histo_task2_roster.csv",
              index=False, encoding="utf-8-sig")
    t3.to_csv(DOSSIER / "verif_44_ancrage_histo_task3_cle_complete.csv",
              index=False, encoding="utf-8-sig")
    t4.to_csv(DOSSIER / "verif_44_ancrage_histo_task4_couverture.csv",
              index=False, encoding="utf-8-sig")
    print(f"\nCSV écrits dans : {DOSSIER}")


if __name__ == "__main__":
    main()
