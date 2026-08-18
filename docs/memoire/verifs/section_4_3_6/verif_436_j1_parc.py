#!/usr/bin/env python3
"""Vérif §4.3.6 (chiffre destiné au chapitre 1) — Parc SURF série 7500 au registre
des rotations CEV/R35.

Objet
-----
Établir, à partir du SEUL registre de planification des rotations (source brute
`data/external/rotations/rotations_23_25.csv`), les deux chiffres destinés au
chapitre 1 :

  (1) Le nombre de RAMES DISTINCTES de la série 7500 (SURF ABeh 2/6, MVR)
      observées sur l'ensemble de la période couverte, avec pour chacune son
      identifiant et sa première / dernière apparition dans le registre.

  (2) Les périodes de couverture exactes du registre : première et dernière date,
      et trous éventuels dans le calendrier d'observation.

Définition « série 7500 »
-------------------------
Identifiant de rame = colonne `CompositionLoc`. Une rame SURF est désignée par son
numéro d'unité à quatre chiffres 75xx (ex. « 7508 »). On retient donc les valeurs
de `CompositionLoc` correspondant au motif ^75\\d\\d$.

Périmètre de comptage
---------------------
Le registre mélange plusieurs régimes (voyageurs réguliers, trains spéciaux,
formations, courses techniques/infra, bus de remplacement, matériel patrimonial
Blonay–Chamby « BC xx »). Le parc SURF est un fait matériel indépendant du régime
de la course : une rame 75xx observée UNE fois dans le registre existe dans le parc.
On compte donc les 75xx sur TOUT le registre (tous TrainType / TrainProprietaire),
puis on reporte séparément le sous-ensemble « voyageurs réguliers » (voy × Régulier),
qui est le périmètre effectivement mobilisé par le pipeline ML
(`scripts/sources/build_dim_rotations_r35.py`).

LECTURE SEULE. Écrit un CSV récapitulatif à côté de ce script.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "external" / "rotations" / "rotations_23_25.csv"

SERIE_7500 = re.compile(r"^75\d\d$")


def charger() -> pd.DataFrame:
    raw = pd.read_csv(SOURCE, sep=";", encoding="utf-8-sig")
    raw["TrainDate"] = pd.to_datetime(raw["TrainDate"])
    return raw


def registre_couverture(raw: pd.DataFrame) -> dict:
    """(2) Couverture calendaire du registre : min/max, jours présents, trous."""
    jours = pd.Index(sorted(raw["TrainDate"].dt.normalize().unique()))
    d0, d1 = jours.min(), jours.max()
    calendrier = pd.date_range(d0, d1, freq="D")
    manquants = calendrier.difference(jours)
    # Regrouper les jours manquants en plages contiguës
    plages = []
    if len(manquants):
        s = manquants[0]
        prev = manquants[0]
        for d in manquants[1:]:
            if (d - prev).days == 1:
                prev = d
                continue
            plages.append((s, prev))
            s = prev = d
        plages.append((s, prev))
    return {
        "debut": d0,
        "fin": d1,
        "jours_calendaires": len(calendrier),
        "jours_observes": len(jours),
        "jours_manquants": len(manquants),
        "plages_manquantes": plages,
    }


def registre_7500(raw: pd.DataFrame) -> pd.DataFrame:
    """(1) Une ligne par rame 75xx : première / dernière apparition, jours, lignes."""
    loc = raw["CompositionLoc"].astype("string").str.strip()
    m = loc.str.match(SERIE_7500, na=False)
    sub = raw[m].copy()
    sub["rame"] = loc[m].values
    g = sub.groupby("rame")
    reg = pd.DataFrame({
        "premiere_apparition": g["TrainDate"].min(),
        "derniere_apparition": g["TrainDate"].max(),
        "jours_actifs": g["TrainDate"].apply(lambda s: s.dt.normalize().nunique()),
        "lignes_registre": g.size(),
    }).sort_index()
    return reg


def autres_series(raw: pd.DataFrame) -> pd.Series:
    """Contexte : autres identifiants numériques de rame (hors 75xx)."""
    loc = raw["CompositionLoc"].astype("string").str.strip()
    num = loc[loc.str.match(r"^\d+$", na=False)]
    autres = num[~num.str.match(SERIE_7500, na=False)]
    return autres.value_counts()


def main() -> None:
    raw = charger()
    reg_voy = raw[(raw["TrainProprietaire"] == "voy") & (raw["TrainType"] == "Régulier")]

    print("=" * 78)
    print("REGISTRE DES ROTATIONS CEV / R35 — source :", SOURCE.name)
    print("=" * 78)
    print(f"Lignes brutes                : {len(raw):,}")
    print(f"  dont voyageurs réguliers   : {len(reg_voy):,}")

    # ---- (2) Couverture -----------------------------------------------------
    cov = registre_couverture(raw)
    print("\n--- (2) COUVERTURE DU REGISTRE (tous régimes) ---")
    print(f"Première date : {cov['debut'].date()}")
    print(f"Dernière date : {cov['fin'].date()}")
    print(f"Jours calendaires sur la plage : {cov['jours_calendaires']}")
    print(f"Jours effectivement observés   : {cov['jours_observes']}")
    print(f"Jours manquants (trous)        : {cov['jours_manquants']}")
    if cov["plages_manquantes"]:
        print("Plages manquantes :")
        for a, b in cov["plages_manquantes"]:
            n = (b - a).days + 1
            if n == 1:
                print(f"    {a.date()} (1 jour)")
            else:
                print(f"    {a.date()} → {b.date()} ({n} jours)")
    else:
        print("Aucun trou : registre continu jour par jour.")

    # ---- (1) Parc série 7500 ------------------------------------------------
    reg = registre_7500(raw)
    print("\n--- (1) PARC SÉRIE 7500 (SURF ABeh 2/6) — tous régimes ---")
    print(f"Nombre de rames distinctes 75xx : {len(reg)}")
    print(f"Identifiants : {', '.join(reg.index.tolist())}")
    print()
    aff = reg.copy()
    aff["premiere_apparition"] = aff["premiere_apparition"].dt.date
    aff["derniere_apparition"] = aff["derniere_apparition"].dt.date
    print(aff.to_string())

    # Sous-ensemble voyageurs réguliers (périmètre pipeline ML)
    reg_v = registre_7500(reg_voy)
    print("\n--- (1bis) même parc restreint aux voyageurs réguliers (voy × Régulier) ---")
    print(f"Rames distinctes 75xx : {len(reg_v)} — {', '.join(reg_v.index.tolist())}")

    # ---- Contexte : autres séries -------------------------------------------
    autres = autres_series(raw)
    print("\n--- Contexte : autres identifiants numériques de rame (hors 75xx) ---")
    print(autres.to_string())

    # ---- Export -------------------------------------------------------------
    out = DOSSIER / "verif_436_j1_parc.csv"
    reg.assign(
        premiere_apparition=reg["premiere_apparition"].dt.date,
        derniere_apparition=reg["derniere_apparition"].dt.date,
    ).to_csv(out, encoding="utf-8-sig")
    print(f"\nCSV écrit : {out}")


if __name__ == "__main__":
    main()
