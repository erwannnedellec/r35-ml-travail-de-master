"""
Construit la dimension des périodes de restrictions COVID en Suisse/Vaud.

Sources officielles
-------------------
Toutes les phases sont sourcées auprès des textes officiels suivants :
  - RS 818.101.24  Ordonnance 2 COVID-19 (Federal, 13.03.2020)
  - RS 818.101.26  Ordonnance COVID-19 mesures spéciales (Federal, 28.10.2020)
  - admin.ch       Communiqués du Conseil fédéral (identifiés par msg-id)
  - Conseil d'État VD, arrêtés sur l'état de nécessité (archives vd.ch)

Phases retenues
---------------
  normal                — pas de restriction fédérale/cantonale significative
  semi_confinement      — situation extraordinaire CH (16.03.2020 → 11.05.2020)
  mesures_renforcees    — restrictions automne 2020 → printemps 2021 (VD)
  certificat_obligatoire — certificat COVID obligatoire (13.09.2021 → 16.02.2022)

Sortie
------
data/dimension/dim_covid.parquet   grain : 1 ligne par jour dans la fenêtre APC
  Colonnes :
    date                      datetime64[ns]
    is_covid_restrictions     bool    — True si restrictions actives
    covid_phase               string  — nom de la phase

CSV : toujours écrit à côté du parquet (petite table).

Usage
-----
    python3 scripts/sources/build_dim_covid.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIM_DIR = PROJECT_ROOT / "data" / "dimension"
OUTPUT  = DIM_DIR / "dim_covid.parquet"

# Fenêtre de couverture alignée sur les données APC H16–H24
WINDOW_START = pd.Timestamp("2015-01-01")
WINDOW_END   = pd.Timestamp("2024-12-31")

# ---------------------------------------------------------------------------
# Définition des phases COVID — dates confirmées, sources officielles citées
# ---------------------------------------------------------------------------

COVID_PHASES: list[dict] = [
    {
        "phase":           "semi_confinement",
        "date_debut":      "2020-03-16",
        "date_fin":        "2020-05-11",
        "source_confirmee": True,
        "reference": (
            "Conseil fédéral, communiqué du 16.03.2020 (admin.ch, msg-id-78454), "
            "déclaration de situation extraordinaire art. 7 LEp ; "
            "communiqué du 29.04.2020 (msg-id-78948), réouverture commerces/restaurants ; "
            "base légale RS 818.101.24 (Ordonnance 2 COVID-19). "
            "Début : 16.03.2020 = entrée en vigueur situation extraordinaire et fermeture "
            "commerces non essentiels. "
            "Fin : 11.05.2020 = réouverture magasins, marchés, restaurants, musées, "
            "bibliothèques et écoles primaires/secondaires."
        ),
    },
    {
        "phase":           "mesures_renforcees",
        "date_debut":      "2020-11-04",
        "date_fin":        "2021-05-30",
        "source_confirmee": True,
        "reference": (
            "Arrêté du Conseil d'État VD du 03.11.2020 sur l'état de nécessité "
            "(fermeture restaurants/bars/lieux de loisirs dès 04.11.2020 17h00) ; "
            "Conseil fédéral, modification de RS 818.101.26 du 28.10.2020 (RO 2020 4503) ; "
            "communiqué CF 11.12.2020 (msg-id-81745), durcissement national à partir du 22.12.2020 ; "
            "levée progressive avril-mai 2021 (terrasses 19.04.2021, intérieur restaurants ~31.05.2021). "
            "Début : 04.11.2020 = état de nécessité vaudois (date cantonale retenue car R35 en VD). "
            "Fin : 30.05.2021 = retour fonctionnement normal restaurants intérieurs en VD. "
            "Fenêtre unique conservée malgré oscillations internes (réouverture brève 10-22 déc. 2020)."
        ),
    },
    {
        "phase":           "certificat_obligatoire",
        "date_debut":      "2021-09-13",
        "date_fin":        "2022-02-16",
        "source_confirmee": True,
        "reference": (
            "Conseil fédéral, communiqué du 08.09.2021 (admin.ch, msg-id-85035), "
            "extension du certificat COVID à restaurants intérieurs/loisirs/manifestations "
            "dès 13.09.2021 ; "
            "communiqué du 16.02.2022 (msg-id-87216), levée des règles 3G/2G/2G+ effective "
            "le 17.02.2022 ; base légale RS 818.101.26 modifiée. "
            "Début : 13.09.2021 = entrée en vigueur obligation de certificat. "
            "Fin : 16.02.2022 = dernier jour d'application (levée décidée le 16, effective le 17)."
        ),
    },
]


def build_dim() -> pd.DataFrame:
    all_dates = pd.date_range(WINDOW_START, WINDOW_END, freq="D")
    dim = pd.DataFrame({"date": all_dates})
    dim["is_covid_restrictions"] = False
    dim["covid_phase"]           = "normal"

    for phase_def in COVID_PHASES:
        phase = phase_def["phase"]
        debut = phase_def["date_debut"]
        fin   = phase_def["date_fin"]
        mask  = (dim["date"] >= pd.Timestamp(debut)) & (dim["date"] <= pd.Timestamp(fin))
        dim.loc[mask, "is_covid_restrictions"] = True
        dim.loc[mask, "covid_phase"]           = phase

    dim["is_covid_restrictions"] = dim["is_covid_restrictions"].astype(bool)
    dim["covid_phase"]           = dim["covid_phase"].astype("string")
    return dim.sort_values("date").reset_index(drop=True)


def validate(dim: pd.DataFrame) -> None:
    dup = dim.loc[dim["date"].duplicated(keep=False)]
    if not dup.empty:
        raise ValueError(f"Dates dupliquées dans dim_covid ({len(dup)} lignes)")
    if dim.empty:
        raise ValueError("dim_covid est vide")
    na_phase = dim["covid_phase"].isna().sum()
    if na_phase:
        raise ValueError(f"{na_phase} lignes avec covid_phase = NA")


def print_summary(dim: pd.DataFrame) -> None:
    print(f"\nDimension COVID :")
    print(f"  jours total        : {len(dim):,}")
    print(f"  couverture         : {dim['date'].min().date()} → {dim['date'].max().date()}")
    print(f"\n  Distribution par phase :")
    for phase, grp in dim.groupby("covid_phase", observed=True):
        n    = len(grp)
        pct  = n / len(dim) * 100
        dates = f"{grp['date'].min().date()} → {grp['date'].max().date()}" if n > 0 else "—"
        print(f"    {phase:<30}: {n:>5} jours ({pct:.1f}%)  {dates}")
    n_restrictions = int(dim["is_covid_restrictions"].sum())
    print(f"\n  Jours avec restrictions : {n_restrictions:,} / {len(dim):,}")

    print(f"\n  Sources officielles :")
    for p in COVID_PHASES:
        print(f"    [{p['phase']}]  {p['date_debut']} → {p['date_fin']}")
        # Afficher la première phrase de la référence
        ref_short = p["reference"].split(";")[0].strip()
        print(f"      {ref_short}")


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
