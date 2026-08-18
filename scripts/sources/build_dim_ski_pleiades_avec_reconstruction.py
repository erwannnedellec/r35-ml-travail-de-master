"""
Construit la dimension des périodes d'exploitation du domaine skiable des
Pléiades, avec reconstruction empirique pour les saisons H16–H19.

Sources officielles (H20–H25 complets + H26 partiel)
------------------------------------------------------
PDFs Coopérative des Pléiades (data/external/ski/) — dates d'exploitation :
  ski_19_20.pdf → H20 : 14.12.2019 – 15.03.2020
  ski_20_21.pdf → H21 : 12.12.2020 – 14.03.2021
  ski_21_22.pdf → H22 : 18.12.2021 – 13.03.2022
  ski_22_23.pdf → H23 : 17.12.2022 – 12.03.2023
  ski_23_24.pdf → H24 : 16.12.2023 – 10.03.2024
  ski_24_25.pdf → H25 : 14.12.2024 – 09.03.2025
  ski_25_26.pdf → saison 2025-2026 officielle : 13.12.2025 – 08.03.2026
                  → seul 2025-12-13 tombe dans H25 (fin de H25 = 2025-12-13,
                    convention APC H25 = 2024-12-15 → 2025-12-13).
                  → 2025-12-14 → 2026-03-08 = H26, hors périmètre dataset.

Règle de reconstruction pour H16–H19
--------------------------------------
Dérivée des 6 saisons officielles H20–H25 :

  Observation 1 — Ouverture :
    Toutes les saisons ouvrent un SAMEDI entre le 12 et le 18 décembre.
    Règle : premier samedi sur ou après le 12 décembre de l'année N-1.
    Reproduction exacte : H20 (14/12), H21 (12/12), H22 (18/12),
                         H23 (17/12), H24 (16/12), H25 (14/12).

  Observation 2 — Fermeture :
    Toutes les saisons ferment un DIMANCHE entre le 9 et le 15 mars.
    Règle : dernier dimanche sur ou avant le 15 mars de l'année N.
    Reproduction exacte : H20 (15/03), H21 (14/03), H22 (13/03),
                         H23 (12/03), H24 (10/03), H25 (09/03).

  Observation 3 — Ouverture quotidienne :
    Sur H20–H25, chaque jour dans la période est ouvert (pas de modèle
    week-end uniquement). La même convention est appliquée aux saisons
    reconstruites.

Limites documentées
-------------------
  - Pas de prise en compte des conditions d'enneigement (fermetures
    techniques, mauvaises saisons).
  - Pas de distinction des ouvertures partielles (certains jours de la
    semaine uniquement) si ce modèle existait avant H20.
  - Les saisons H16–H19 sont marquées ski_source='reconstruit' pour
    permettre une pondération ou une exclusion lors de la modélisation.
  - Recommandation : compléter par contact avec la Coopérative des Pléiades
    pour obtenir les archives H16–H19.

Sortie
------
data/dimension/dim_ski_pleiades.parquet   grain : 1 ligne par jour d'exploitation
  Colonnes :
    date           datetime64[ns]
    is_ski_ouvert  bool
    saison_ski     string  — ex. "H20"
    ski_source     string  — "officiel" (H20–H25) ou "reconstruit" (H16–H19)

CSV : toujours écrit à côté du parquet (petite table).

Usage
-----
    python3 scripts/sources/build_dim_ski_pleiades_avec_reconstruction.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIM_DIR = PROJECT_ROOT / "data" / "dimension"
OUTPUT  = DIM_DIR / "dim_ski_pleiades.parquet"

# ---------------------------------------------------------------------------
# Périodes officielles H20–H25 (source : PDFs Coopérative des Pléiades)
# ---------------------------------------------------------------------------
OFFICIAL_PERIODS: list[tuple[str, str, str]] = [
    ("H20", "2019-12-14", "2020-03-15"),
    ("H21", "2020-12-12", "2021-03-14"),
    ("H22", "2021-12-18", "2022-03-13"),
    ("H23", "2022-12-17", "2023-03-12"),
    ("H24", "2023-12-16", "2024-03-10"),
    ("H25", "2024-12-14", "2025-03-09"),
    # Saison 2025-2026 (source : ski_25_26.pdf) : 2025-12-13 → 2026-03-08.
    # Seul 2025-12-13 tombe dans H25 (fin H25 = 2025-12-13, convention APC).
    # Le reste (2025-12-14 → 2026-03-08) est H26, hors périmètre du dataset.
    ("H26", "2025-12-13", "2025-12-13"),
]

# ---------------------------------------------------------------------------
# Saisons à reconstruire
# Pour HXX : décembre de l'année (2000 + XX - 1) → mars de l'année (2000 + XX)
# ---------------------------------------------------------------------------
SEASONS_TO_RECONSTRUCT = ["H16", "H17", "H18", "H19"]


# ---------------------------------------------------------------------------
# Fonctions de dérivation de la règle
# ---------------------------------------------------------------------------

def first_saturday_on_or_after(year: int, month: int, day: int) -> pd.Timestamp:
    """Premier samedi sur ou après la date (year, month, day)."""
    dt = pd.Timestamp(year, month, day)
    days_to_sat = (5 - dt.weekday()) % 7  # weekday 5 = samedi
    return dt + pd.Timedelta(days=int(days_to_sat))


def last_sunday_on_or_before(year: int, month: int, day: int) -> pd.Timestamp:
    """Dernier dimanche sur ou avant la date (year, month, day)."""
    dt = pd.Timestamp(year, month, day)
    days_back = (dt.weekday() - 6) % 7   # weekday 6 = dimanche
    return dt - pd.Timedelta(days=int(days_back))


def reconstruct_season(saison: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Calcule les dates de début et de fin d'une saison reconstruite HXX.
    Règle : ouverture = 1er samedi ≥ 12 décembre (année N-1),
            fermeture = dernier dimanche ≤ 15 mars (année N).
    """
    xx     = int(saison[1:])
    yr_dec = 2000 + xx - 1
    yr_mar = 2000 + xx
    debut  = first_saturday_on_or_after(yr_dec, 12, 12)
    fin    = last_sunday_on_or_before(yr_mar, 3, 15)
    return debut, fin


# ---------------------------------------------------------------------------
# Construction de la dimension
# ---------------------------------------------------------------------------

def build_dim() -> pd.DataFrame:
    rows: list[dict] = []

    # Périodes officielles H20–H25
    for saison, debut, fin in OFFICIAL_PERIODS:
        for d in pd.date_range(debut, fin, freq="D"):
            rows.append({
                "date":          d,
                "is_ski_ouvert": True,
                "saison_ski":    saison,
                "ski_source":    "officiel",
            })

    # Périodes reconstruites H16–H19
    for saison in SEASONS_TO_RECONSTRUCT:
        debut, fin = reconstruct_season(saison)
        for d in pd.date_range(debut, fin, freq="D"):
            rows.append({
                "date":          d,
                "is_ski_ouvert": True,
                "saison_ski":    saison,
                "ski_source":    "reconstruit",
            })

    dim = pd.DataFrame(rows)
    dim["date"]          = pd.to_datetime(dim["date"]).dt.normalize()
    dim["is_ski_ouvert"] = dim["is_ski_ouvert"].astype(bool)
    dim["saison_ski"]    = dim["saison_ski"].astype("string")
    dim["ski_source"]    = dim["ski_source"].astype("string")
    return dim.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(dim: pd.DataFrame) -> None:
    dup = dim.loc[dim["date"].duplicated(keep=False)]
    if not dup.empty:
        raise ValueError(
            f"Dates dupliquées dans dim_ski_pleiades ({len(dup)} lignes) : "
            f"{dup['date'].head(5).tolist()}"
        )
    if dim.empty:
        raise ValueError("dim_ski_pleiades est vide")

    # Vérification de la règle sur les officiels
    for saison, debut_ref, fin_ref in OFFICIAL_PERIODS:
        grp = dim.loc[dim["saison_ski"] == saison]
        debut_obs = grp["date"].min().date()
        fin_obs   = grp["date"].max().date()
        debut_exp = pd.Timestamp(debut_ref).date()
        fin_exp   = pd.Timestamp(fin_ref).date()
        if debut_obs != debut_exp or fin_obs != fin_exp:
            raise ValueError(
                f"{saison} : attendu {debut_exp}→{fin_exp}, "
                f"obtenu {debut_obs}→{fin_obs}"
            )


# ---------------------------------------------------------------------------
# Résumé et statistiques de la règle
# ---------------------------------------------------------------------------

def print_summary(dim: pd.DataFrame) -> None:
    print(f"\nDimension ski Les Pléiades (avec reconstruction H16–H19) :")
    print(f"  jours total  : {len(dim):,}")
    print(f"  couverture   : {dim['date'].min().date()} → {dim['date'].max().date()}")
    print(f"\n  Détail par saison :")

    for saison, grp in dim.groupby("saison_ski", observed=False):
        debut   = grp["date"].min().date()
        fin     = grp["date"].max().date()
        source  = grp["ski_source"].iloc[0]
        nb      = len(grp)
        print(f"    {saison} [{source:<11}]: {debut} → {fin}  ({nb} jours)")

    print(f"\n  Statistiques de la règle de reconstruction (dérivées de H20–H25) :")
    print(f"    Ouverture : 1er samedi ≥ 12 décembre  (médiane historique : 15 déc.)")
    print(f"    Fermeture : dernier dimanche ≤ 15 mars (médiane historique : 12 mars)")
    print(f"    Mode d'exploitation : quotidien (identique aux saisons officielles)")
    print(f"\n    Dates reconstruites :")
    for saison in SEASONS_TO_RECONSTRUCT:
        debut, fin = reconstruct_season(saison)
        import calendar
        print(
            f"      {saison}: {debut.date()} ({calendar.day_name[debut.weekday()]}) "
            f"→ {fin.date()} ({calendar.day_name[fin.weekday()]})"
        )
    print()
    print(
        "  [LIMITE] Saisons H16–H19 reconstruites sans données d'enneigement ni "
        "archives officielles. Utiliser ski_source='reconstruit' pour pondérer ou "
        "exclure en sensibilité."
    )


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    dim = build_dim()
    validate(dim)

    DIM_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp.parquet")
    try:
        dim.to_parquet(tmp, index=False)
        tmp.rename(OUTPUT)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    dim.to_csv(OUTPUT.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    print(f"  parquet : {OUTPUT}  ({len(dim):,} lignes)")

    print_summary(dim)


if __name__ == "__main__":
    main()
