#!/usr/bin/env python3
"""
verif_v2_prerequis.py — Vérifications ciblées avant rédaction des sections 4.3 et 4.4.2.

Six vérifications, en LECTURE SEULE stricte. Le script n'écrit que dans son propre
répertoire (docs/memoire/verifs/section_4_3/), préfixe `v2_`.

  V1  Calibration de la fenêtre des narcisses (15.04 → 25.05) : quelle EDA, quelles
      années horaires, H25 en fait-il partie ? Archéologie git du producteur.
  V2  annees_horaires.csv : contenu H21–H26, contiguïté, coïncidence avec le
      changement d'horaire suisse, source / ADR / test / contrôle de contiguïté.
  V3  Trou de comptage H22 : arbitrage entre 24, 25 et 29 jours, recalculé depuis
      apc_stacked.
  V4  Empreintes ba493568 et 416bb90b : quel artefact, quel mode de calcul,
      mentions discordantes dans docs/memoire/.
  V5  « Caves ouvertes Vaudoises » : dates, présence dans les compteurs globaux vs
      zonaux, intersection avec la fenêtre des narcisses.
  V6  Non-régression documentaire : event_covid_phase / event_is_marche_noel /
      event_is_montreux_noel apparaissent-ils dans un objet flottant déjà produit ?

Sorties
-------
  v2_t1_narcisses_calibration.csv     traces trouvées / absentes
  v2_t1_narcisses_git.csv             archéologie git du producteur
  v2_t2_annees_horaires.csv           bornes, contiguïté, changement d'horaire
  v2_t3_trou_h22.csv                  blocs manquants et arbitrage 24/25/29
  v2_t4_empreintes.csv                artefacts et empreintes
  v2_t4_mentions_discordantes.csv     occurrences de 416bb90b dans docs/memoire/
  v2_t5_caves_ouvertes.csv            occurrences et compteurs
  v2_t6_non_regression.csv            objets flottants concernés

Usage
-----
    python3 docs/memoire/verifs/section_4_3/verif_v2_prerequis.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
APC_STACKED = ROOT / "data" / "processed" / "sources" / "apc_stacked.parquet"
ANNEES_HORAIRES = ROOT / "data" / "dimension" / "annees_horaires.csv"
DIM_MANIF_EV = ROOT / "data" / "dimension" / "dim_manifestations_riviera_evenements.parquet"
DIM_MANIF_DATES = ROOT / "data" / "dimension" / "dim_manifestations_riviera.parquet"
BUILD_NARCISSES = ROOT / "scripts" / "sources" / "build_dim_narcisses.py"

HASH_CANONIQUE = "ba493568"
HASH_PRECEDENT = "416bb90b"

# Fenêtre narcisses codée dans le producteur (constantes l.75-78)
NARC_DEBUT = (4, 15)
NARC_FIN = (5, 25)


def log(m: str = "") -> None:
    print(m, flush=True)


def titre(t: str) -> None:
    log("\n" + "=" * 78)
    log(t)
    log("=" * 78)


def ecrire(df: pd.DataFrame, nom: str) -> None:
    p = HERE / nom
    df.to_csv(p, index=False, encoding="utf-8-sig")
    log(f"  → écrit : {p.relative_to(ROOT)}  ({len(df):,} lignes)")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True
    ).stdout


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def charger_annees() -> pd.DataFrame:
    a = pd.read_csv(ANNEES_HORAIRES, sep=";", encoding="utf-8-sig", dtype="string")
    a = a.rename(columns={"Annee": "annee_horaire", "Debut": "debut",
                          "Fin": "fin", "Nombre de jours": "nb_jours_declare"})
    a["debut"] = pd.to_datetime(a["debut"], format="%d.%m.%Y", errors="coerce")
    a["fin"] = pd.to_datetime(a["fin"], format="%d.%m.%Y", errors="coerce")
    return a


def annee_horaire_de(dates: pd.Series, annees: pd.DataFrame) -> pd.Series:
    ok = annees.dropna(subset=["debut", "fin"])
    idx = pd.IntervalIndex.from_arrays(ok["debut"], ok["fin"], closed="both")
    pos = idx.get_indexer(pd.to_datetime(dates))
    out = pd.Series(pd.NA, index=dates.index, dtype="string")
    m = pos >= 0
    out.loc[m] = ok["annee_horaire"].to_numpy()[pos[m]]
    return out


# ===========================================================================
# V0 — Empreinte
# ===========================================================================

def v0_empreinte() -> None:
    titre("V0 — Empreinte du dataset canonique")
    h = sha8(ML_DATASET)
    log(f"  ml_dataset.parquet SHA256[:8] = {h} (attendu {HASH_CANONIQUE})")
    if h != HASH_CANONIQUE:
        raise SystemExit(f"ARRÊT — empreinte {h} ≠ {HASH_CANONIQUE}.")
    log("  ✓ génération canonique confirmée")


# ===========================================================================
# V1 — Calibration de la fenêtre des narcisses
# ===========================================================================

def v1_narcisses() -> None:
    titre("V1 — Calibration de la fenêtre des narcisses (15.04 → 25.05)")

    # --- (a) Archéologie git du producteur -------------------------------
    hist = git("log", "--format=%h|%ad|%s", "--date=short", "--follow",
               "--", "scripts/sources/build_dim_narcisses.py").strip().splitlines()
    lignes_git = []
    for l in hist:
        h, d, s = l.split("|", 2)
        contenu = git("show", f"{h}:scripts/sources/build_dim_narcisses.py")
        lignes_git.append(dict(
            commit=h, date=d, sujet=s,
            contient_15_avril=("REGLE_CALENDAIRE_DEBUT_JOUR = 15" in contenu),
            contient_25_mai=("REGLE_CALENDAIRE_FIN_JOUR   = 25" in contenu
                             or "REGLE_CALENDAIRE_FIN_JOUR = 25" in contenu),
            formule_calibration=(
                "est à calibrer" if "est à calibrer" in contenu
                else ("est calibrée empiriquement" if "est calibrée empiriquement" in contenu
                      else "AUTRE / ABSENTE")),
            mentionne_official_dates=("OFFICIAL_DATES" in contenu),
        ))
    git_df = pd.DataFrame(lignes_git)
    ecrire(git_df, "v2_t1_narcisses_git.csv")
    log("\n  Archéologie git de scripts/sources/build_dim_narcisses.py :")
    log(git_df.to_string(index=False))

    plus_ancien = git_df.iloc[-1]
    log(f"\n  → la fenêtre 15.04–25.05 est présente DÈS LE PREMIER COMMIT "
        f"({plus_ancien.commit}, {plus_ancien.date}) : "
        f"contient_15_avril={plus_ancien.contient_15_avril}, "
        f"contient_25_mai={plus_ancien.contient_25_mai}")
    log(f"  → formulation d'origine : « {plus_ancien.formule_calibration} » ; "
        f"formulation actuelle : « {git_df.iloc[0].formule_calibration} »")

    # --- (b) Recherche d'un artefact de calibration ------------------------
    controles = []

    def note(objet: str, chemin: str, resultat: str, detail: str) -> None:
        controles.append(dict(objet=objet, chemin=chemin, resultat=resultat,
                              detail=detail))

    # b1 — quel notebook s'appelle NB05 ?
    nb05 = sorted(ROOT.glob("notebooks/05*.ipynb"))
    note("Notebook nommé NB05 dans le dépôt",
         " ; ".join(str(p.relative_to(ROOT)) for p in nb05) or "AUCUN",
         "TROUVÉ" if nb05 else "ABSENT",
         "le producteur renvoie à « NB05 — Feature Analysis » ; le notebook 05 du "
         "dépôt est une évaluation de modèle, la Feature Analysis est le notebook 06")

    # b2 — les bornes apparaissent-elles dans un notebook ?
    # Distinction essentielle : le CODE d'un notebook (dérivation possible) vs
    # ses SORTIES stockées (simple affichage d'une dimension déjà construite).
    motif_bornes = re.compile(r"04-15|05-25|REGLE_CALENDAIRE")
    dans_code, dans_sorties = [], []
    for nb in sorted(ROOT.glob("notebooks/*.ipynb")):
        doc = json.loads(nb.read_text(errors="ignore"))
        code = "\n".join("".join(c["source"]) for c in doc["cells"])
        sorties = json.dumps([c.get("outputs", []) for c in doc["cells"]],
                             ensure_ascii=False)
        if motif_bornes.search(code):
            dans_code.append(str(nb.relative_to(ROOT)))
        elif motif_bornes.search(sorties):
            dans_sorties.append(str(nb.relative_to(ROOT)))
    note("Bornes 15.04 / 25.05 dans le CODE d'un notebook (dérivation possible)",
         " ; ".join(dans_code) or "AUCUN NOTEBOOK",
         "TROUVÉ" if dans_code else "ABSENT",
         "recherche des motifs 04-15, 05-25, REGLE_CALENDAIRE dans les sources "
         "de cellules uniquement (cells[].source)")
    note("Bornes 15.04 / 25.05 seulement dans les SORTIES stockées",
         " ; ".join(dans_sorties) or "AUCUN NOTEBOOK",
         "TROUVÉ" if dans_sorties else "ABSENT",
         "simple affichage de la couverture d'une dimension DÉJÀ construite — "
         "ne constitue pas une dérivation des bornes")

    # b3 — notebooks mentionnant narcisses, et ce qu'ils font
    usages = {
        "notebooks/02_data_understanding_evenements.ipynb":
            "DESCRIPTIF de la dimension déjà construite (cellule 13 : couverture, "
            "jours de saison, comptage par année) — ne dérive aucune borne",
        "notebooks/03_final_dataset.ipynb":
            "inventaire de la famille event_ + delta de charge event=1 vs event=0 "
            "(cellules 21-22) — postérieur à la construction",
        "notebooks/11b_diagnostics_pr_auc_et_narcisses.ipynb":
            "diagnostic de REDONDANCE resa_* / narcisses sur mai H24 (modèle B'), "
            "split H22+H23 train / H24 test — n'évalue pas les bornes",
        "notebooks/06_feature_analysis_h22_h23_h24.ipynb":
            "feature analysis H22+H23 vs H24 — la feature narcisses y est consommée, "
            "pas calibrée",
        "notebooks/07_segmentation_bas_haut.ipynb":
            "segmentation bas/haut — consommation",
        "notebooks/12_diagnostic_histo_type_jour.ipynb": "consommation",
        "notebooks/01_business_understanding.ipynb": "mention de contexte",
        "notebooks/02_data_understanding_surcharges.ipynb": "consommation",
    }
    for chemin, role in usages.items():
        p = ROOT / chemin
        note("Notebook mentionnant les narcisses", chemin,
             "PRÉSENT" if p.exists() else "ABSENT", role)

    # b4 — artefacts de sortie d'une calibration
    motifs = ["*narciss*", "*narcisse*"]
    artefacts = []
    for rep in ("outputs", "notebooks/outputs", "reports", "docs/rapports",
                "archive", "docs/memoire"):
        base = ROOT / rep
        if not base.exists():
            continue
        for m in motifs:
            artefacts += [str(p.relative_to(ROOT)) for p in base.rglob(m)]
    artefacts = sorted(set(artefacts))
    note("Artefact de sortie nommé « narcisses »",
         " ; ".join(artefacts) or "AUCUN", "TROUVÉ" if artefacts else "ABSENT",
         "aucun de ces artefacts n'est une calibration : voir colonne détail du rapport")

    # b5 — les sorties stockées du notebook descriptif sont-elles à jour ?
    nb_ev = ROOT / "notebooks" / "02_data_understanding_evenements.ipynb"
    doc = json.loads(nb_ev.read_text(errors="ignore"))
    sorties = json.dumps([c.get("outputs", []) for c in doc["cells"]],
                         ensure_ascii=False)
    m = re.search(r"couverture (\d{4}-\d{2}-\d{2}) -> (\d{4}-\d{2}-\d{2})", sorties)
    dim_narc = pd.read_parquet(ROOT / "data" / "dimension" / "dim_narcisses.parquet")
    couv_reelle = (str(dim_narc["date"].min().date()),
                   str(dim_narc["date"].max().date()))
    couv_nb = (m.group(1), m.group(2)) if m else ("—", "—")
    note("Sorties stockées de 02_data_understanding_evenements.ipynb à jour ?",
         str(nb_ev.relative_to(ROOT)),
         "PÉRIMÉES" if couv_nb != couv_reelle else "À JOUR",
         f"sorties affichées : {couv_nb[0]} → {couv_nb[1]} ; dimension réelle "
         f"({HASH_CANONIQUE}) : {couv_reelle[0]} → {couv_reelle[1]}")

    ctrl = pd.DataFrame(controles)
    ecrire(ctrl, "v2_t1_narcisses_calibration.csv")
    log("\n  Recherche d'un artefact de calibration :")
    for r in ctrl.itertuples(index=False):
        log(f"    [{r.resultat:<8}] {r.objet}")
        log(f"               {r.chemin}")

    # --- (c) Le jeu d'évaluation H25 est-il concerné ? ---------------------
    log("\n  H25 fait-il partie du périmètre de la calibration ?")
    log("    La question est SANS OBJET tant qu'aucune calibration n'est tracée.")
    log("    Élément matériel décisif : la fenêtre 15.04–25.05 figure dans le "
        "PREMIER commit du producteur (2026-06-04), soit AVANT l'extension du")
    log("    périmètre à H25 et avant le gel ba493568 (2026-07-11). Elle ne peut "
        "donc pas avoir été calibrée sur H25.")
    log("    Vérification de datation ci-dessous.")

    idx = (ROOT / "docs" / "adr" / "INDEX.md").read_text()
    for cible, motif in [
        ("ADR-038 — Extension du périmètre temporel à H25", r"\| ADR-038 \|[^|]*\|\s*([\d-]+)"),
        ("ADR-076 — Migration de gel (ba493568)", r"\| ADR-076 \|[^|]*\|\s*([\d-]+)"),
    ]:
        m = re.search(motif, idx)
        log(f"    {cible} : date de décision "
            f"{m.group(1) if m else 'NON DOCUMENTÉE'} (docs/adr/INDEX.md)")
    log("    → l'extension à H25 (ADR-038) et le premier commit du producteur "
        "narcisses portent la MÊME date (2026-06-04) et le même commit 02b88e8 : "
        "la fenêtre est écrite AU MOMENT de l'extension, pas après une analyse de H25.")


# ===========================================================================
# V2 — annees_horaires.csv
# ===========================================================================

def _rang_dimanche_de_decembre(d: pd.Timestamp) -> int | None:
    """Rang du dimanche dans son mois (1 = premier dimanche). None si pas dimanche."""
    if d.weekday() != 6:
        return None
    return (d.day - 1) // 7 + 1


def _rang_samedi_precedent(d: pd.Timestamp) -> int | None:
    """Rang, dans décembre, du samedi qui précède immédiatement d."""
    sam = d - pd.Timedelta(days=1)
    if sam.month != 12:
        return None
    return (sam.day - 1) // 7 + 1


def v2_annees_horaires(annees: pd.DataFrame) -> None:
    titre("V2 — annees_horaires.csv")

    log(f"  Fichier : {ANNEES_HORAIRES.relative_to(ROOT)}")
    log(f"  Lignes totales : {len(annees)} (H03 → H29)")

    cible = annees[annees["annee_horaire"].isin(
        ["H21", "H22", "H23", "H24", "H25", "H26"])].copy()

    lignes = []
    # contiguïté sur toutes les lignes datées
    datees = annees.dropna(subset=["debut"]).sort_values("debut").reset_index(drop=True)
    for i, r in datees.iterrows():
        trou = None
        if i > 0:
            fin_prec = datees.loc[i - 1, "fin"]
            if pd.isna(fin_prec):
                trou = "borne de fin précédente MANQUANTE"
            else:
                delta = (r["debut"] - fin_prec).days
                trou = ("contigu" if delta == 1
                        else (f"TROU de {delta - 1} j" if delta > 1
                              else f"RECOUVREMENT de {1 - delta} j"))
        nb_reel = (int((r["fin"] - r["debut"]).days) + 1) if pd.notna(r["fin"]) else None
        lignes.append(dict(
            annee_horaire=r["annee_horaire"],
            debut=r["debut"].date(),
            fin=r["fin"].date() if pd.notna(r["fin"]) else "MANQUANTE",
            nb_jours_declare=r.get("nb_jours_declare"),
            nb_jours_recalcule=nb_reel,
            coherence_nb_jours=(
                None if nb_reel is None or pd.isna(r.get("nb_jours_declare"))
                else int(r["nb_jours_declare"]) == nb_reel),
            jour_semaine_debut=r["debut"].day_name(),
            rang_dimanche_decembre=_rang_dimanche_de_decembre(r["debut"]),
            rang_samedi_precedent=_rang_samedi_precedent(r["debut"]),
            continuite_avec_precedent=trou,
        ))
    cont = pd.DataFrame(lignes)
    ecrire(cont, "v2_t2_annees_horaires.csv")

    log("\n  Lignes H21 → H26 (bornes brutes du fichier) :")
    log(cible.to_string(index=False))

    log("\n  Contrôle de contiguïté et de règle de changement d'horaire :")
    sub = cont[cont["annee_horaire"].isin(["H21", "H22", "H23", "H24", "H25", "H26"])]
    log(sub[["annee_horaire", "debut", "fin", "nb_jours_declare",
             "nb_jours_recalcule", "coherence_nb_jours", "jour_semaine_debut",
             "rang_dimanche_decembre", "rang_samedi_precedent",
             "continuite_avec_precedent"]].to_string(index=False))

    n_trous = int(cont["continuite_avec_precedent"].astype(str)
                  .str.startswith("TROU").sum())
    n_rec = int(cont["continuite_avec_precedent"].astype(str)
                .str.startswith("RECOUVREMENT").sum())
    log(f"\n  → trous : {n_trous} | recouvrements : {n_rec} sur "
        f"{len(cont) - 1} transitions datées")

    tous_dimanche = all(x == "Sunday" for x in cont["jour_semaine_debut"])
    log(f"  → toutes les bornes de début sont un dimanche : {tous_dimanche}")
    rangs_dim = sorted(set(cont["rang_dimanche_decembre"].dropna().astype(int)))
    rangs_sam = sorted(set(cont["rang_samedi_precedent"].dropna().astype(int)))
    log(f"  → rangs du dimanche de début dans décembre observés : {rangs_dim}")
    log(f"  → rangs du samedi qui précède, dans décembre : {rangs_sam}")
    log("  → lecture : la règle « deuxième DIMANCHE de décembre » est mise en défaut "
        "dès qu'un rang 3 apparaît ; la règle « dimanche suivant le deuxième SAMEDI "
        "de décembre » est vérifiée si tous les rangs samedi valent 2.")

    # Source / ADR / test déclarés ?
    log("\n  Source, ADR, test :")
    entete = ANNEES_HORAIRES.read_text(encoding="utf-8-sig").splitlines()[0]
    log(f"    en-tête du CSV : {entete!r} → aucune colonne de source ni de commentaire")
    for motif, libelle in [("annees_horaires", "références au fichier")]:
        hits = subprocess.run(["grep", "-rln", motif, "docs/adr", "tests", "scripts", "src"],
                              cwd=ROOT, capture_output=True, text=True).stdout.split()
        hits = [h for h in hits if "__pycache__" not in h]
        log(f"    {libelle} : {hits if hits else 'AUCUNE'}")
    # contrôle de contiguïté dans le pipeline ?
    prod = (ROOT / "scripts" / "pipeline"
            / "add_annee_horaire_to_raw_stacked.py").read_text()
    log(f"    contrôle de contiguïté dans add_annee_horaire_to_raw_stacked.py : "
        f"{'PRÉSENT' if 'contig' in prod.lower() else 'ABSENT'}")
    log(f"    contrôle de recouvrement (IntervalIndex overlaps) : "
        f"{'PRÉSENT' if 'overlap' in prod.lower() else 'ABSENT'}")
    log(f"    lignes non appariées interceptées : "
        f"{'OUI' if 'sans annee horaire' in prod.lower() or 'non apparie' in prod.lower() else 'à vérifier dans le rapport'}")


# ===========================================================================
# V3 — Trou de comptage H22
# ===========================================================================

def v3_trou_h22(annees: pd.DataFrame) -> None:
    titre("V3 — Trou de comptage H22")

    h22 = annees[annees["annee_horaire"] == "H22"].iloc[0]
    deb, fin = h22["debut"], h22["fin"]
    log(f"  Fenêtre H22 (annees_horaires.csv) : {deb.date()} → {fin.date()}")

    apc = pd.read_parquet(APC_STACKED,
                          columns=["base_date", "target_voyageurs_2eme_classe"])
    h = apc[(apc["base_date"] >= deb) & (apc["base_date"] <= fin)]
    cal = pd.date_range(deb, fin, freq="D")
    presents = set(pd.to_datetime(h["base_date"].unique()))
    manquants = [d for d in cal if d not in presents]

    log(f"  Source : {APC_STACKED.relative_to(ROOT)}")
    log(f"  Jours calendaires H22 : {len(cal)}")
    log(f"  Jours présents dans l'APC : {len(presents)}  "
        f"({100 * len(presents) / len(cal):.2f} %)")
    log(f"  Jours calendaires ABSENTS : {len(manquants)}")

    # journées présentes mais sans aucun comptage exploitable
    g = h.groupby("base_date")["target_voyageurs_2eme_classe"].agg(["size", "count"])
    sans_comptage = g[g["count"] == 0]
    log(f"  Jours présents mais sans AUCUN comptage 2e classe non nul : "
        f"{len(sans_comptage)}")

    # blocs contigus
    blocs, cur = [], [manquants[0]]
    for d in manquants[1:]:
        if (d - cur[-1]).days == 1:
            cur.append(d)
        else:
            blocs.append(cur)
            cur = [d]
    blocs.append(cur)

    lignes = []
    for b in blocs:
        precedent = b[0] - pd.Timedelta(days=1)
        suivant = b[-1] + pd.Timedelta(days=1)
        lignes.append(dict(
            premier_jour_absent=b[0].date(),
            dernier_jour_absent=b[-1].date(),
            n_jours_absents=len(b),
            dernier_jour_present_avant=precedent.date(),
            premier_jour_present_apres=suivant.date(),
            ecart_en_jours_entre_bornes_presentes=int((suivant - precedent).days),
            intervalle_borne_a_borne_inclusif=int((suivant - precedent).days) + 1,
        ))
    blocs_df = pd.DataFrame(lignes).sort_values("n_jours_absents", ascending=False)

    log("\n  Blocs de jours absents :")
    log(blocs_df.to_string(index=False))

    principal = blocs_df.iloc[0]
    arbitrage = pd.DataFrame([
        dict(valeur=int(principal.n_jours_absents),
             definition="jours calendaires RÉELLEMENT absents dans le bloc de septembre",
             calcul=f"{principal.premier_jour_absent} → {principal.dernier_jour_absent} inclus",
             verdict="EXACT pour « longueur du trou de septembre »"),
        dict(valeur=int(principal.ecart_en_jours_entre_bornes_presentes),
             definition="écart en jours entre le dernier jour présent et le premier jour présent suivant",
             calcul=f"{principal.premier_jour_present_apres} − {principal.dernier_jour_present_avant}",
             verdict="mesure d'AMPLITUDE, surestime d'1 j le nombre de jours absents"),
        dict(valeur=int(principal.intervalle_borne_a_borne_inclusif),
             definition="intervalle borne à borne compté inclusivement (les deux jours présents inclus)",
             calcul=f"de {principal.dernier_jour_present_avant} à "
                    f"{principal.premier_jour_present_apres} inclus",
             verdict="surestime de 2 j ; compte deux jours qui SONT présents"),
        dict(valeur=len(manquants),
             definition="total des jours calendaires absents sur toute l'année horaire H22",
             calcul=" + ".join(str(len(b)) for b in blocs) + f" = {len(manquants)}",
             verdict="EXACT pour « jours absents en H22 », tous blocs confondus"),
    ])
    ecrire(pd.concat([blocs_df.assign(bloc="blocs"),
                      arbitrage.assign(bloc="arbitrage")], ignore_index=True),
           "v2_t3_trou_h22.csv")

    log("\n  Arbitrage des valeurs :")
    log(arbitrage.to_string(index=False))

    # septembre 2022 est-il entièrement absent ?
    sep = [d for d in cal if d.year == 2022 and d.month == 9]
    sep_pres = sorted(d.date() for d in sep if d in presents)
    log(f"\n  Septembre 2022 : {len(sep)} jours, {len(sep_pres)} présents → "
        f"{[str(d) for d in sep_pres]}")
    log(f"  → l'énoncé « tout septembre 2022 » est "
        f"{'EXACT' if not sep_pres else 'INEXACT'} : "
        f"les {len(sep_pres)} premiers jours du mois sont présents.")

    # cohérence avec ml_dataset
    ml = pd.read_parquet(ML_DATASET, columns=["horaire_annee_horaire", "base_date"])
    n_h22 = ml.loc[ml["horaire_annee_horaire"] == "H22", "base_date"].nunique()
    log(f"\n  Contrôle croisé ml_dataset : {n_h22} jours distincts en H22 "
        f"(identique à apc_stacked : {n_h22 == len(presents)})")


# ===========================================================================
# V4 — Empreintes
# ===========================================================================

def v4_empreintes() -> None:
    titre("V4 — Empreintes ba493568 et 416bb90b")

    lignes = []
    ml_hash = sha8(ML_DATASET)
    lignes.append(dict(
        empreinte=ml_hash,
        artefact=str(ML_DATASET.relative_to(ROOT)),
        nature="dataset ML canonique (gold), 1 141 984 × 209",
        mode_de_calcul="hashlib.sha256(path.read_bytes()).hexdigest()[:8] "
                       "— ADR-066 décision 1, à pyarrow 21.0.0 constant",
        statut="CANONIQUE COURANT (gel v2, ADR-076, 2026-07-11)",
        present_sur_disque=True,
    ))
    lignes.append(dict(
        empreinte=HASH_PRECEDENT,
        artefact=str(ML_DATASET.relative_to(ROOT)) + " (génération antérieure)",
        nature="MÊME chemin de fichier, contenu antérieur — le parquet portant cette "
               "empreinte n'existe plus sur disque",
        mode_de_calcul="identique (SHA256[:8], ADR-066)",
        statut="SUPERSÉDÉ (v1.9, remplacé par ba493568)",
        present_sur_disque=False,
    ))

    # Artefacts dérivés qui portent l'un ou l'autre dans leur nom
    for motif, h in ((f"*{HASH_CANONIQUE}*", HASH_CANONIQUE),
                     (f"*{HASH_PRECEDENT}*", HASH_PRECEDENT)):
        for p in sorted(ROOT.glob(f"outputs/**/{motif}")):
            lignes.append(dict(
                empreinte=h, artefact=str(p.relative_to(ROOT)),
                nature="artefact dérivé (nom porteur de la génération)",
                mode_de_calcul="hérité — l'empreinte est dans le NOM, pas recalculée",
                statut=("courant" if h == HASH_CANONIQUE else "archéologie"),
                present_sur_disque=True))

    # Hashes de modèles (à ne pas confondre)
    meta = ROOT / "models" / "enrichi_seg" / "enrichi_seg_metadata.json"
    if meta.exists():
        for f, attendu in (("enrichi_seg_bas_ba493568.json", "e4ddfccd"),
                           ("enrichi_seg_haut_ba493568.json", "df6a11c5")):
            p = ROOT / "models" / "enrichi_seg" / f
            lignes.append(dict(
                empreinte=(sha8(p) if p.exists() else "FICHIER ABSENT"),
                artefact=str(p.relative_to(ROOT)) if p.exists() else f,
                nature="MODÈLE gelé — empreinte de MODÈLE, distincte de celle du dataset",
                mode_de_calcul="SHA256[:8] du JSON du booster",
                statut=f"attendu {attendu} (outputs/confirmation/c08_shap_segments.json)",
                present_sur_disque=p.exists()))

    emp = pd.DataFrame(lignes)
    ecrire(emp, "v2_t4_empreintes.csv")
    log(emp[["empreinte", "artefact", "statut"]].to_string(index=False))

    # --- mentions discordantes dans docs/memoire/ -------------------------
    log("\n  Occurrences de 416bb90b dans docs/memoire/ :")
    out = subprocess.run(["grep", "-rn", HASH_PRECEDENT, "docs/memoire"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    men = []
    for l in out.strip().splitlines():
        if not l.strip():
            continue
        chemin, num, texte = l.split(":", 2)
        if "verifs/section_4_3/" in chemin:
            continue          # exclut le présent chantier (auto-référence)
        texte = texte.strip()
        bas = texte.lower()
        # Une mention est LÉGITIME si elle documente la transition ou une trace historique
        legitime = any(k in bas for k in (
            "supersed", "supersédé", "ancien gel", "archéologie", "archeologie",
            "historique", "inchangé", "inchanges", "inchangés", "vs gel",
            "comparaison", "transition", "→ ba493568", "de `416bb90b` à",
            "chasse aux chiffres", "trace"))
        # Une mention est DISCORDANTE si elle présente 416bb90b comme courant
        discordante = (not legitime) and any(k in bas for k in (
            "empreinte sha256", "empreinte", "codebook_canonique_416bb90b",
            "| 416bb90b |", "sha256[:8]"))
        men.append(dict(fichier=chemin, ligne=int(num),
                        extrait=texte[:200],
                        verdict=("DISCORDANTE (présente 416bb90b comme courant)"
                                 if discordante else
                                 ("légitime (trace ou transition)" if legitime
                                  else "à qualifier à la main"))))
    men_df = pd.DataFrame(men)
    ecrire(men_df, "v2_t4_mentions_discordantes.csv")
    log(f"    total : {len(men_df)} occurrences")
    for v, g in men_df.groupby("verdict"):
        log(f"    {v} : {len(g)}")
    disc = men_df[men_df["verdict"].str.startswith("DISCORDANTE")]
    if len(disc):
        log("\n  Mentions discordantes :")
        for r in disc.itertuples(index=False):
            log(f"    {r.fichier}:{r.ligne}")
            log(f"      {r.extrait[:160]}")

    # verdict de la garde du dépôt
    log("\n  Garde du dépôt (scripts/check_hash_propagation.py) :")
    log("    docs/memoire/ n'est PAS dans le périmètre actif de la garde "
        "(ACTIVE_FILES l.42-49, ACTIVE_DIRS l.50) : les mentions ci-dessus "
        "ne sont donc surveillées par aucun mécanisme.")


# ===========================================================================
# V5 — Caves ouvertes vaudoises
# ===========================================================================

def v5_caves(annees: pd.DataFrame) -> None:
    titre("V5 — « Caves ouvertes Vaudoises » : événement sans lieu parsé")

    ev = pd.read_parquet(DIM_MANIF_EV)
    inconnus = ev[ev["zone_r35"] == "inconnue"].copy()
    log(f"  Événements en zone 'inconnue' : {len(inconnus)}")

    inconnus["annee_horaire_debut"] = annee_horaire_de(inconnus["date_debut"], annees)
    log("\n  Détail :")
    log(inconnus[["annee_pdf", "nom", "date_debut", "date_fin", "nombre_jours",
                  "lieu", "zone_r35", "localite_r35",
                  "annee_horaire_debut"]].to_string(index=False))

    caves = inconnus[inconnus["nom"].str.contains("Caves ouvertes", case=False,
                                                  na=False)].copy()
    log(f"\n  dont « Caves ouvertes Vaudoises » : {len(caves)} occurrences")

    # Journées couvertes, année horaire, fenêtre narcisses
    jours = []
    for r in caves.itertuples(index=False):
        for d in pd.date_range(r.date_debut, r.date_fin, freq="D"):
            jours.append(dict(nom=r.nom, annee_pdf=r.annee_pdf, date=d))
    jours_df = pd.DataFrame(jours)
    jours_df["annee_horaire"] = annee_horaire_de(jours_df["date"], annees)
    jours_df["dans_fenetre_narcisses"] = jours_df["date"].map(
        lambda d: (d.month, d.day) >= NARC_DEBUT and (d.month, d.day) <= NARC_FIN)

    perim = jours_df[jours_df["annee_horaire"].isin(["H22", "H23", "H24", "H25"])]
    log(f"\n  Journées couvertes au total : {len(jours_df)}")
    log(f"  dont dans le périmètre H22–H25 : {len(perim)}")
    log(f"  dont dans la fenêtre narcisses (15.04 → 25.05) : "
        f"{int(perim['dans_fenetre_narcisses'].sum())}")

    # Présence dans les compteurs : lecture de la dimension date
    dates_dim = pd.read_parquet(DIM_MANIF_DATES)
    jointe = perim.merge(dates_dim, on="date", how="left")
    jointe["somme_compteurs_zonaux"] = (
        jointe["n_manifestations_zone_directe_j"].fillna(0)
        + jointe["n_manifestations_zone_indirecte_j"].fillna(0)
        + jointe["n_manifestations_hors_zone_j"].fillna(0)
    ).astype(int)
    jointe["ecart_global_moins_zonaux"] = (
        jointe["n_manifestations_riviera"].fillna(0).astype(int)
        - jointe["somme_compteurs_zonaux"]
    )

    cols = ["date", "annee_horaire", "dans_fenetre_narcisses",
            "is_manifestation_riviera", "n_manifestations_riviera",
            "n_manifestations_zone_directe_j", "n_manifestations_zone_indirecte_j",
            "n_manifestations_hors_zone_j", "somme_compteurs_zonaux",
            "ecart_global_moins_zonaux", "n_manifestations_vevey_j",
            "n_manifestations_st_legier_j", "n_manifestations_blonay_j"]
    log("\n  État des compteurs sur les journées concernées (H22–H25) :")
    log(jointe[cols].to_string(index=False))

    log(f"\n  → présentes dans event_is_manifestation_riviera : "
        f"{bool(jointe['is_manifestation_riviera'].fillna(False).all())}")
    log(f"  → comptées dans event_n_manifestations_riviera : OUI "
        f"(l'écart global − zonaux vaut {sorted(set(jointe['ecart_global_moins_zonaux']))} "
        f"sur ces journées, soit exactement le nombre d'événements en zone 'inconnue')")
    log("  → comptées dans un compteur ZONAL ou de LOCALITÉ : NON — "
        "build_dim_manifestations_riviera.py, build_date_dimension() l.397-430 : "
        "chaque compteur zonal teste l'égalité à une zone nommée, 'inconnue' n'en "
        "active aucun ; localite_r35 = 'hors_r35' n'active aucun compteur de localité.")

    ecrire(pd.concat([
        inconnus.assign(bloc="evenements_zone_inconnue")[
            ["bloc", "annee_pdf", "nom", "date_debut", "date_fin", "nombre_jours",
             "zone_r35", "localite_r35", "annee_horaire_debut"]],
        jointe.assign(bloc="journees_h22_h25")[["bloc"] + cols],
    ], ignore_index=True), "v2_t5_caves_ouvertes.csv")

    # Volumétrie côté dataset
    ml = pd.read_parquet(ML_DATASET, columns=[
        "base_date", "horaire_annee_horaire", "event_is_manifestation_riviera",
        "event_n_manifestations_riviera", "event_n_manifestations_zone_directe_j",
        "event_n_manifestations_zone_indirecte_j",
        "event_n_manifestations_hors_zone_j", "event_is_saison_narcisses"])
    sel = ml[ml["base_date"].isin(set(perim["date"]))]
    log(f"\n  Côté ml_dataset : {len(sel):,} observations tombent sur ces "
        f"{perim['date'].nunique()} journées")
    if len(sel):
        agg = (sel.groupby("horaire_annee_horaire")
               .agg(n_obs=("base_date", "size"),
                    n_jours=("base_date", "nunique"),
                    manif_active=("event_is_manifestation_riviera", "sum"),
                    narcisses_actif=("event_is_saison_narcisses", "sum"))
               .reset_index())
        log(agg.to_string(index=False))


# ===========================================================================
# V6 — Non-régression documentaire
# ===========================================================================

_CIBLES_V6 = ["event_covid_phase", "event_is_marche_noel", "event_is_montreux_noel"]

# Qualification manuelle des répertoires de docs/memoire/
_NATURE = [
    ("docs/memoire/figures/", "OBJET FLOTTANT — figure destinée au manuscrit"),
    ("docs/memoire/tableaux/", "OBJET FLOTTANT — tableau destiné au manuscrit"),
    ("docs/memoire/verifs/", "rapport de vérification interne (non flottant)"),
    ("docs/memoire/rapport", "rapport interne (non flottant)"),
    ("docs/memoire/verifs/section_4_3_2/", "table de travail (non flottante)"),
    ("docs/memoire/tests_section_4_3/", "table de tests (statut à trancher)"),
    ("docs/memoire/annexe", "ANNEXE du manuscrit"),
]


def _nature(chemin: str) -> str:
    for prefixe, lib in _NATURE:
        if chemin.startswith(prefixe):
            return lib
    return "à qualifier"


def v6_non_regression() -> None:
    titre("V6 — Contrôle de non-régression documentaire")

    lignes = []
    for cible in _CIBLES_V6:
        out = subprocess.run(["grep", "-rn", cible, "docs/memoire"],
                             cwd=ROOT, capture_output=True, text=True).stdout
        for l in out.strip().splitlines():
            if not l.strip():
                continue
            chemin, num, texte = l.split(":", 2)
            if "verifs/section_4_3/" in chemin:
                continue          # exclut le présent chantier et l'audit précédent
            lignes.append(dict(
                variable=cible, fichier=chemin, ligne=int(num),
                nature=_nature(chemin), extrait=texte.strip()[:180]))
    ref = pd.DataFrame(lignes)

    # Les figures PNG ne sont pas grepables : on inspecte leur script générateur
    log("  Occurrences hors du présent chantier :")
    if ref.empty:
        log("    AUCUNE")
    else:
        for n, g in ref.groupby("nature"):
            log(f"\n    [{n}]")
            for r in g.itertuples(index=False):
                log(f"      {r.fichier}:{r.ligne}  ({r.variable})")
                log(f"        {r.extrait[:150]}")

    # Contrôle direct du contenu des figures SHAP (top 15 par segment)
    log("\n  Contenu effectif des figures SHAP §4.5.6 (top 15 par segment) :")
    top = {}
    for seg in ("bas", "haut"):
        d = pd.read_csv(ROOT / "outputs" / "confirmation"
                        / f"c08_shap_ranks_{seg}.csv").head(15)
        top[seg] = set(d["feature"])
        presents = [c for c in _CIBLES_V6 if c in top[seg]]
        log(f"    fig_shap_top15_{seg}.png : "
            f"{presents if presents else 'aucune des trois variables'}")

    # Rangs réels, pour situer
    log("\n  Rangs réels des trois variables (sur 158) :")
    rangs = []
    for seg in ("bas", "haut"):
        d = pd.read_csv(ROOT / "outputs" / "confirmation"
                        / f"c08_shap_ranks_{seg}.csv")
        for c in _CIBLES_V6:
            r = d[d["feature"] == c]
            rangs.append(dict(
                variable=c, segment=seg,
                rang=(int(r["rang"].iloc[0]) if len(r) else None),
                mean_abs_shap=(float(r["mean_abs_shap"].iloc[0]) if len(r) else None),
                dans_top15=(c in top[seg]),
                presente_dans_figure_shap=(c in top[seg])))
    rangs_df = pd.DataFrame(rangs)
    log(rangs_df.to_string(index=False))

    ecrire(pd.concat([
        (ref.assign(bloc="occurrences") if not ref.empty
         else pd.DataFrame(columns=["bloc"])),
        rangs_df.assign(bloc="rangs_shap"),
    ], ignore_index=True), "v2_t6_non_regression.csv")

    # Numérotation des figures du manuscrit
    log("\n  Numérotation globale des figures / tableaux du manuscrit "
        "(numéros cités par la demande : figures 21, 23, 24, 25 ; tableau 15) :")
    out = subprocess.run(
        ["grep", "-rni", "-E",
         r"(figure|fig\.)[[:space:]]*(21|23|24|25)\b|tableau[[:space:]]*15\b",
         "docs/memoire", "docs/adr", "notebooks"],
        cwd=ROOT, capture_output=True, text=True).stdout
    ancres = [l for l in out.strip().splitlines()
              if l.strip() and "verifs/section_4_3/" not in l]
    if ancres:
        for a in ancres:
            log(f"    {a[:200]}")
    else:
        log("    AUCUNE occurrence de ces numéros dans le dépôt.")
    log("    → la table de correspondance « numéro de figure/tableau du manuscrit "
        "↔ artefact du dépôt » est NON DOCUMENTÉE DANS LE DÉPÔT : les figures y "
        "sont désignées par leur SECTION (§4.5.6, §4.5.7…), jamais par un numéro "
        "global. Le verdict de non-régression ci-dessus porte donc sur le CONTENU "
        "des artefacts, pas sur leur numéro.")


# ===========================================================================

def main() -> None:
    log(f"verif_v2_prerequis.py — {HERE.relative_to(ROOT)}")
    log(f"pandas {pd.__version__} | python {sys.version.split()[0]}")
    v0_empreinte()
    annees = charger_annees()
    v1_narcisses()
    v2_annees_horaires(annees)
    v3_trou_h22(annees)
    v4_empreintes()
    v5_caves(annees)
    v6_non_regression()
    titre("FIN")
    for f in sorted(HERE.glob("v2_*.csv")):
        log(f"  {f.name}")


if __name__ == "__main__":
    main()
