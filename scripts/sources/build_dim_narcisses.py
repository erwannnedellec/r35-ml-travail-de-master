"""
Construit la dimension de la saison des narcisses aux Pléiades.

La saison des narcisses est un phénomène touristique saisonnier majeur
concentrant une affluence spécifique sur le tronçon Blonay–Les Pléiades
(cité spontanément dans les entretiens qualitatifs, notamment P05).

Règle calendaire (mécanisme corrigé — ADR-076)
----------------------------------------------
La saison est une floraison naturelle, pas un événement à dates officielles.
Une fenêtre annuelle fixe est utilisée :
  date_debut : 15 avril
  date_fin   : 25 mai

Cette fenêtre est un choix a priori, posé comme valeur de repli en l'absence
de calendrier de floraison. Elle n'a fait l'objet d'aucune calibration
empirique (correction du 2026-07-30, addendum ADR-076).

AUCUNE source de dates officielles de floraison n'existe (Coopérative des
Pléiades / Montreux-Vevey Tourisme jamais obtenues ; vérification négative
exhaustive du 2026-07-11 : `find data/`, grep `narciss`/`OFFICIAL_DATES`,
consignée dans l'ADR-076). La règle est donc PUREMENT CALENDAIRE.

Mécanisme sans borne figée au passé (ADR-076)
---------------------------------------------
Le producteur couvre les années de COVERAGE_START_YEAR à COVERAGE_END_YEAR,
cette dernière étant un HORIZON FUTUR volontairement en avance sur les données
(pas une année passée figée sans rappel — c'est le défaut de la génération précédente (corrigé, ADR-076)). Le
rappel manquant est une GARDE DE COUVERTURE au point où la dim rencontre les
données (scripts/pipeline/coverage_guard.py, câblée dans
add_narcisses_to_raw_stacked.py) : le build échoue bruyamment si la dim ne
couvre pas la fin de la dernière période de données. Maintenance : reculer
COVERAGE_END_YEAR quand l'horizon est atteint (rare).

Sortie
------
data/dimension/dim_narcisses.parquet   grain : 1 ligne par jour dans la fenêtre
  Colonnes :
    date                  datetime64[ns]
    is_saison_narcisses   bool    — True si la date est dans la fenêtre
    narcisses_source      string  — "regle_calendaire" (valeur unique)

CSV : toujours écrit à côté du parquet (petite table).

Anti-leakage J-1
-----------------
La fenêtre est calendaire fixe, connue à J-1 sans observation du jour J.

Usage
-----
    python3 scripts/sources/build_dim_narcisses.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIM_DIR = PROJECT_ROOT / "data" / "dimension"
OUTPUT  = DIM_DIR / "dim_narcisses.parquet"

# Couverture temporelle. Début = premier millésime APC (H16). Fin = horizon futur
# paramétré, volontairement en avance sur les données ; la garde de couverture au
# join (coverage_guard) est le rappel qui échoue si les données dépassent la dim.
# ADR-076 : plus de borne figée à une année passée sans garde.
COVERAGE_START_YEAR = 2015
COVERAGE_END_YEAR   = 2030

# ---------------------------------------------------------------------------
# Règle calendaire (fenêtre de floraison fixe)
# Choix a priori, jamais calibré empiriquement (addendum ADR-076 du 2026-07-30).
# Une calibration sur les seules années d'entraînement reste une perspective ouverte.
# Règle purement calendaire : aucune source de dates officielles n'existe (ADR-076).
# ---------------------------------------------------------------------------
REGLE_CALENDAIRE_DEBUT_MOIS = 4   # avril
REGLE_CALENDAIRE_DEBUT_JOUR = 15
REGLE_CALENDAIRE_FIN_MOIS   = 5   # mai
REGLE_CALENDAIRE_FIN_JOUR   = 25

NARCISSES_SOURCE = "regle_calendaire"


def _window_for_year(annee: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Retourne (debut, fin) de la fenêtre calendaire pour une année donnée."""
    return (
        pd.Timestamp(annee, REGLE_CALENDAIRE_DEBUT_MOIS, REGLE_CALENDAIRE_DEBUT_JOUR),
        pd.Timestamp(annee, REGLE_CALENDAIRE_FIN_MOIS,   REGLE_CALENDAIRE_FIN_JOUR),
    )


def build_dim() -> pd.DataFrame:
    rows: list[dict] = []
    for annee in range(COVERAGE_START_YEAR, COVERAGE_END_YEAR + 1):
        debut, fin = _window_for_year(annee)
        for d in pd.date_range(debut, fin, freq="D"):
            rows.append({
                "date":                d,
                "is_saison_narcisses": True,
                "narcisses_source":    NARCISSES_SOURCE,
            })

    if not rows:
        return pd.DataFrame(
            columns=["date", "is_saison_narcisses", "narcisses_source"]
        )

    dim = pd.DataFrame(rows)
    dim["date"]                = pd.to_datetime(dim["date"]).dt.normalize()
    dim["is_saison_narcisses"] = dim["is_saison_narcisses"].astype(bool)
    dim["narcisses_source"]    = dim["narcisses_source"].astype("string")
    return dim.sort_values("date").reset_index(drop=True)


def validate(dim: pd.DataFrame) -> None:
    dup = dim.loc[dim["date"].duplicated(keep=False)]
    if not dup.empty:
        raise ValueError(
            f"Dates dupliquées dans dim_narcisses ({len(dup)} lignes) : "
            f"{dup['date'].head(5).tolist()}"
        )


def print_summary(dim: pd.DataFrame) -> None:
    print(f"\nDimension saison des narcisses :")
    print(f"  jours positifs     : {len(dim):,}")
    print(f"  couverture         : {COVERAGE_START_YEAR} → {COVERAGE_END_YEAR} "
          f"(règle purement calendaire {REGLE_CALENDAIRE_DEBUT_JOUR:02d}.{REGLE_CALENDAIRE_DEBUT_MOIS:02d}"
          f" → {REGLE_CALENDAIRE_FIN_JOUR:02d}.{REGLE_CALENDAIRE_FIN_MOIS:02d})")
    print(f"\n  Fenêtre par année :")
    for annee, grp in dim.groupby(dim["date"].dt.year):
        debut  = grp["date"].min().date()
        fin    = grp["date"].max().date()
        print(f"    {annee} : {debut} → {fin}  ({len(grp)} jours)")


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
