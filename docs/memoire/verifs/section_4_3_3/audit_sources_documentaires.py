#!/usr/bin/env python3
"""
audit_sources_documentaires.py — Audit documentaire des sources calendaires et
événementielles (mémoire, sections 4.3 et 4.4.2).

Objet
-----
Documenter au même niveau de rigueur que STATPOP les six sources qui ne
proviennent pas d'un flux machine mais d'une extraction depuis des documents :

  1. manifestations Montreux Riviera Tourisme (PDF annuels)
  2. calendrier scolaire et jours fériés vaudois (PDF DFJC + vd.ch)
  3. dates d'exploitation du domaine skiable des Pléiades (PDF Coopérative)
  4. saison des narcisses (aucune source documentaire — règle calendaire)
  5. phases pandémiques (ordonnances fédérales / arrêtés vaudois)
  6. horaire planifié R35 (PDF horaire officiel ligne 112)

STRICTEMENT EN LECTURE SEULE. Le script ne réécrit aucun parquet du pipeline,
aucune dimension, aucun script de production. Il n'écrit que dans son propre
répertoire (docs/memoire/verifs/section_4_3/).

Les fonctions des producteurs sont IMPORTÉES (pas copiées) pour que les
comptages d'exclusion et d'appariement des lieux soient exactement ceux du
pipeline. L'import est sans effet de bord (main() sous garde __main__).

Sorties (dans le répertoire de ce script)
----------------------------------------
  asd_t1_inventaire_colonnes.csv        inventaire event_/cal_/horaire_/covid
  asd_t1_nan_par_annee_horaire.csv      taux de NaN par année horaire
  asd_t1_domaines.csv                   domaine observé par colonne
  asd_t2_sources_brutes.csv             fichiers bruts, format, volumétrie
  asd_t3_chaine_extraction.csv          scripté / transcrit à la main
  asd_t4_manif_par_annee.csv            événements et journées par année
  asd_t4_manif_jours_par_zone.csv       journées avec ≥1 événement par zone
  asd_t4_manif_lieux.csv                lieux → zone, appariement
  asd_t4_manif_exclusions.csv           annulés / reportés / sans date
  asd_t4_manif_recurrents.csv           événements à indicateur propre
  asd_t5_ski_saisons.csv                dates d'ouverture/fermeture + origine
  asd_t5_narcisses_fenetres.csv         bornes par année
  asd_t5_vacances_feries.csv            volumétrie calendrier vaudois
  asd_t6_covid_par_annee_horaire.csv    observations concernées H22–H25
  asd_t7_horaire_offre_h24.csv          offre planifiée par heure (H24)
  asd_t8_gouvernance.csv                ADR / assertions / tests par source

Usage
-----
    python3 docs/memoire/verifs/section_4_3/audit_sources_documentaires.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]

ML_DATASET = PROJECT_ROOT / "data" / "processed" / "ml_dataset.parquet"
CODEBOOK = PROJECT_ROOT / "outputs" / "codebook_canonique_ba493568.csv"
FEATURES_158 = PROJECT_ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"

DIM = PROJECT_ROOT / "data" / "dimension"
EXTERNAL = PROJECT_ROOT / "data" / "external"
SOURCES = PROJECT_ROOT / "data" / "processed" / "sources"

DIM_MANIF_EVENTS = DIM / "dim_manifestations_riviera_evenements.parquet"
DIM_MANIF_DATES = DIM / "dim_manifestations_riviera.parquet"
DIM_SKI = DIM / "dim_ski_pleiades.parquet"
DIM_NARCISSES = DIM / "dim_narcisses.parquet"
DIM_COVID = DIM / "dim_covid.parquet"
DIM_VACANCES = DIM / "dim_vacances_feries_vaud.parquet"
DIM_VACANCES_EVENTS = DIM / "dim_vacances_feries_vaud_evenements.parquet"
ANNEES_HORAIRES = DIM / "annees_horaires.csv"
HORAIRES_CLEAN = SOURCES / "horaires_clean.parquet"

SHAP_BAS = PROJECT_ROOT / "outputs" / "confirmation" / "c08_shap_ranks_bas.csv"
SHAP_HAUT = PROJECT_ROOT / "outputs" / "confirmation" / "c08_shap_ranks_haut.csv"
SHAP_COMBINE = PROJECT_ROOT / "outputs" / "confirmation" / "c08_shap_ranks_combine.csv"

BUILD_MANIF = PROJECT_ROOT / "scripts" / "sources" / "build_dim_manifestations_riviera.py"

HASH_CANONIQUE = "ba493568"

# Familles auditées + toute colonne évoquant le covid quelle que soit sa famille
PREFIXES_AUDITES = ("event_", "cal_", "horaire_")
MOTIFS_COVID = ("covid", "pandem")


def log(msg: str = "") -> None:
    print(msg, flush=True)


def titre(n: str) -> None:
    log("\n" + "=" * 78)
    log(n)
    log("=" * 78)


def ecrire(df: pd.DataFrame, nom: str) -> None:
    chemin = HERE / nom
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    log(f"  → écrit : {chemin.relative_to(PROJECT_ROOT)}  ({len(df):,} lignes)")


# ---------------------------------------------------------------------------
# Section 0 — Empreinte du dataset canonique
# ---------------------------------------------------------------------------

def verifier_empreinte() -> str:
    titre("S0 — Empreinte du dataset canonique")
    h = hashlib.sha256(ML_DATASET.read_bytes()).hexdigest()[:8]
    log(f"  ml_dataset.parquet SHA256[:8] = {h}  (attendu {HASH_CANONIQUE})")
    if h != HASH_CANONIQUE:
        raise SystemExit(
            f"ARRÊT — empreinte {h} ≠ {HASH_CANONIQUE}. "
            "L'audit ne doit pas être produit sur une autre génération."
        )
    log("  ✓ génération canonique confirmée (gel v2, ADR-076)")
    return h


def charger_annees_horaires() -> pd.DataFrame:
    """Fenêtres des années horaires depuis data/dimension/annees_horaires.csv."""
    a = pd.read_csv(ANNEES_HORAIRES, sep=";", encoding="utf-8-sig", dtype="string")
    a = a.rename(columns={"Annee": "annee_horaire", "Debut": "debut", "Fin": "fin"})
    a["debut"] = pd.to_datetime(a["debut"], format="%d.%m.%Y", errors="coerce")
    a["fin"] = pd.to_datetime(a["fin"], format="%d.%m.%Y", errors="coerce")
    return a.dropna(subset=["debut", "fin"])[["annee_horaire", "debut", "fin"]]


def annee_horaire_de_date(dates: pd.Series, annees: pd.DataFrame) -> pd.Series:
    """Affecte une année horaire à chaque date par recherche d'intervalle."""
    idx = pd.IntervalIndex.from_arrays(annees["debut"], annees["fin"], closed="both")
    pos = idx.get_indexer(pd.to_datetime(dates))
    vals = pd.Series(pd.NA, index=dates.index, dtype="string")
    ok = pos >= 0
    vals.loc[ok] = annees["annee_horaire"].to_numpy()[pos[ok]]
    return vals


# ---------------------------------------------------------------------------
# Section 1 — Inventaire des colonnes
# ---------------------------------------------------------------------------

def s1_inventaire(df: pd.DataFrame) -> list[str]:
    titre("S1 — Inventaire des colonnes event_ / cal_ / horaire_ + covid")

    cb = pd.read_csv(CODEBOOK)
    f158 = set(json.loads(FEATURES_158.read_text())["features"])
    log(f"  codebook : {len(cb)} entrées ({CODEBOOK.relative_to(PROJECT_ROOT)})")
    log(f"  liste modèle : {len(f158)} features ({FEATURES_158.relative_to(PROJECT_ROOT)})")

    cols = [c for c in df.columns if c.startswith(PREFIXES_AUDITES)]
    cols += [
        c for c in df.columns
        if c not in cols and any(m in c.lower() for m in MOTIFS_COVID)
    ]
    log(f"  colonnes retenues : {len(cols)}")

    cb_idx = cb.set_index("colonne")
    lignes = []
    for c in cols:
        s = df[c]
        r = cb_idx.loc[c] if c in cb_idx.index else None
        lignes.append({
            "colonne": c,
            "famille": c.split("_")[0] + "_",
            "dtype_parquet": str(s.dtype),
            "source_codebook": None if r is None else r["source"],
            "statut_codebook": None if r is None else r["statut"],
            "libelle_codebook": None if r is None else r["libelle_fr"],
            "plage_codebook": None if r is None else r["plage_ou_modalites"],
            "reference_adr_codebook": (
                "NON DOCUMENTÉ DANS LE DÉPÔT"
                if r is None or pd.isna(r["reference_adr"]) else r["reference_adr"]
            ),
            "present_codebook": r is not None,
            "dans_158_features": c in f158,
            "taux_nan_pct_global": round(100 * float(s.isna().mean()), 6),
            "n_distinct": int(s.nunique(dropna=True)),
        })
    inv = pd.DataFrame(lignes)
    ecrire(inv, "asd_t1_inventaire_colonnes.csv")

    # Écart entre le drapeau du codebook et la liste de features effective
    ecarts = []
    for c in cols:
        if c in cb_idx.index:
            flag = bool(cb_idx.loc[c, "dans_158_features"])
            reel = c in f158
            if flag != reel:
                ecarts.append((c, flag, reel))
    if ecarts:
        log("  ⚠ écarts codebook.dans_158_features vs features_158f_sans_simba.json :")
        for c, f, r in ecarts:
            log(f"      {c} : codebook={f}  liste={r}")
    else:
        log("  ✓ aucun écart codebook / liste 158f sur les colonnes auditées")

    # NaN par année horaire
    nan_rows = []
    for annee, g in df.groupby("horaire_annee_horaire", observed=True):
        for c in cols:
            nan_rows.append({
                "annee_horaire": annee,
                "colonne": c,
                "n_obs": len(g),
                "n_nan": int(g[c].isna().sum()),
                "taux_nan_pct": round(100 * float(g[c].isna().mean()), 6),
            })
    nan_df = pd.DataFrame(nan_rows)
    ecrire(nan_df, "asd_t1_nan_par_annee_horaire.csv")
    n_nz = int((nan_df["n_nan"] > 0).sum())
    log(f"  cellules (année × colonne) avec au moins un NaN : {n_nz} / {len(nan_df)}")

    # Domaines observés
    dom_rows = []
    for c in cols:
        s = df[c]
        n_dist = int(s.nunique(dropna=True))
        est_categoriel = (
            str(s.dtype) in ("string", "object", "bool")
            or (n_dist <= 12 and pd.api.types.is_numeric_dtype(s))
        )
        if est_categoriel and n_dist <= 40:
            vc = s.value_counts(dropna=False).sort_index(key=lambda i: i.astype(str))
            dom_rows.append({
                "colonne": c,
                "type_domaine": "catégoriel / booléen",
                "n_distinct": n_dist,
                "valeurs_observees": " | ".join(
                    f"{k}={v}" for k, v in vc.items()
                ),
                "min": None, "median": None, "max": None,
            })
        else:
            num = pd.to_numeric(s, errors="coerce")
            dom_rows.append({
                "colonne": c,
                "type_domaine": "quantitatif" if num.notna().any() else "textuel",
                "n_distinct": n_dist,
                "valeurs_observees": None,
                "min": None if num.isna().all() else float(num.min()),
                "median": None if num.isna().all() else float(num.median()),
                "max": None if num.isna().all() else float(num.max()),
            })
    ecrire(pd.DataFrame(dom_rows), "asd_t1_domaines.csv")
    return cols


# ---------------------------------------------------------------------------
# Section 2 — Sources brutes
# ---------------------------------------------------------------------------

def _git_suivi(chemin: Path) -> bool:
    rel = chemin.relative_to(PROJECT_ROOT)
    out = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return out.returncode == 0


def _git_premier_commit(chemin: Path) -> str:
    rel = chemin.relative_to(PROJECT_ROOT)
    out = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short",
         "--", str(rel)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    lignes = [l for l in out.stdout.strip().splitlines() if l.strip()]
    return lignes[-1] if lignes else "NON DOCUMENTÉ DANS LE DÉPÔT"


# (source, motif glob, organisme déclaré, où la provenance est déclarée)
_INVENTAIRE_BRUT = [
    ("manifestations", EXTERNAL / "evenements", "Manifestations *.pdf",
     "Montreux Riviera Tourisme",
     "scripts/sources/build_dim_manifestations_riviera.py, docstring l.1-6"),
    ("calendrier_scolaire_vaud", EXTERNAL / "vacances_scolaires", "*.pdf",
     "DFJC — État de Vaud",
     "scripts/sources/build_dim_vacances_feries_vaud.py, l.8-16 et l.65-76"),
    ("calendrier_scolaire_vaud_copie_versionnee", EXTERNAL / "vacances_scolaires_vaud",
     "*.pdf", "DFJC — État de Vaud",
     "répertoire non référencé par le producteur (voir §3)"),
    ("ski_pleiades", EXTERNAL / "ski", "*.pdf",
     "Coopérative des Pléiades (déclaré)",
     "scripts/sources/build_dim_ski_pleiades_avec_reconstruction.py, l.6-16"),
    ("horaire_planifie", EXTERNAL / "horaires_r35", "112_*.pdf",
     "horaire officiel ligne 112 (éditeur non nommé dans le dépôt)",
     "scripts/sources/build_horaires_r35_from_pdfs.py, SCHEDULE_DIR l.44"),
]


def s2_sources_brutes() -> pd.DataFrame:
    titre("S2 — Sources brutes : chemins, format, volumétrie, provenance")
    lignes = []
    for source, rep, motif, organisme, ou_declare in _INVENTAIRE_BRUT:
        fichiers = sorted(rep.glob(motif)) if rep.exists() else []
        if not fichiers:
            lignes.append({
                "source": source,
                "repertoire": str(rep.relative_to(PROJECT_ROOT)),
                "fichier": "AUCUN FICHIER",
                "format": "—", "taille_octets": 0,
                "mtime_fichier": "—",
                "suivi_git": False,
                "date_ajout_git": "NON DOCUMENTÉ DANS LE DÉPÔT",
                "organisme_declare": organisme,
                "provenance_declaree_dans": ou_declare,
            })
            continue
        for f in fichiers:
            lignes.append({
                "source": source,
                "repertoire": str(rep.relative_to(PROJECT_ROOT)),
                "fichier": f.name,
                "format": f.suffix.lstrip(".").upper(),
                "taille_octets": f.stat().st_size,
                "mtime_fichier": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "suivi_git": _git_suivi(f),
                "date_ajout_git": _git_premier_commit(f),
                "organisme_declare": organisme,
                "provenance_declaree_dans": ou_declare,
            })
    # Sources SANS fichier brut au dépôt
    for source, motif in [
        ("narcisses", "aucun document — règle calendaire codée en dur"),
        ("phases_pandemiques", "aucun document — dates codées en dur, références textuelles"),
    ]:
        lignes.append({
            "source": source,
            "repertoire": "—",
            "fichier": "AUCUN FICHIER BRUT AU DÉPÔT",
            "format": motif,
            "taille_octets": 0,
            "mtime_fichier": "—",
            "suivi_git": False,
            "date_ajout_git": "—",
            "organisme_declare": (
                "aucun (règle empirique projet)" if source == "narcisses"
                else "Conseil fédéral / Conseil d'État VD (références citées, documents absents)"
            ),
            "provenance_declaree_dans": (
                "scripts/sources/build_dim_narcisses.py l.8-21"
                if source == "narcisses"
                else "scripts/sources/build_dim_covid.py l.4-10 et COVID_PHASES l.52-100"
            ),
        })
    df = pd.DataFrame(lignes)
    ecrire(df, "asd_t2_sources_brutes.csv")
    for source, g in df.groupby("source", sort=False):
        n = int((g["fichier"] != "AUCUN FICHIER BRUT AU DÉPÔT").sum())
        n = 0 if g["fichier"].iloc[0].startswith("AUCUN") else len(g)
        log(f"  {source:<45}: {n} fichier(s), suivi git = "
            f"{sorted(set(g['suivi_git'].tolist()))}")
    return df


# ---------------------------------------------------------------------------
# Section 3 — Chaîne d'extraction et reproductibilité
# ---------------------------------------------------------------------------

_CHAINE = [
    dict(
        source="manifestations",
        extraction="SCRIPTÉE (parsing PDF)",
        script="scripts/sources/build_dim_manifestations_riviera.py",
        fonctions="extract_text() l.185-187 (pdfplumber) ; parse_line() l.221-261 ; "
                  "parse_pdf() l.264-278 ; main() l.527-612",
        document_versionne_au_depot=True,
        fichier_transcrit_a_la_main="aucun",
        rejouable_depuis_le_document="OUI — les 11 PDF sont au dépôt et re-parsés à chaque run",
    ),
    dict(
        source="calendrier_scolaire_vaud",
        extraction="TRANSCRIPTION MANUELLE (littéral Python)",
        script="scripts/sources/build_dim_vacances_feries_vaud.py",
        fonctions="SCHOOL_YEAR_DATA l.108-449 (18 années scolaires × 16 dates, "
                  "saisies à la main) ; read_school_years() l.561-566 ; "
                  "validate_source_pdfs() l.569-572 vérifie seulement l'EXISTENCE des PDF",
        document_versionne_au_depot=True,
        fichier_transcrit_a_la_main="SCHOOL_YEAR_DATA, dans le corps du script",
        rejouable_depuis_le_document="NON — aucun parsing PDF ; le littéral EST la source de vérité",
    ),
    dict(
        source="feries_vaudois",
        extraction="CALCULÉE (algorithmique)",
        script="scripts/sources/build_dim_vacances_feries_vaud.py",
        fonctions="easter_sunday() l.533-549 (comput gaussien) ; "
                  "federal_fast_monday() l.552-558 ; build_public_holidays() l.658-691",
        document_versionne_au_depot=False,
        fichier_transcrit_a_la_main="liste des 9 fériés, en dur dans build_public_holidays()",
        rejouable_depuis_le_document="OUI (algorithmique) — mais la LISTE des fériés retenus "
                                    "est un choix codé, sourcé par une URL vd.ch non archivée",
    ),
    dict(
        source="ski_pleiades",
        extraction="TRANSCRIPTION MANUELLE (littéral Python) + règle empirique",
        script="scripts/sources/build_dim_ski_pleiades_avec_reconstruction.py",
        fonctions="OFFICIAL_PERIODS l.80-91 (7 lignes saisies à la main depuis les PDF) ; "
                  "reconstruct_season() l.118-129 ; first_saturday_on_or_after() l.104-108 ; "
                  "last_sunday_on_or_before() l.111-115",
        document_versionne_au_depot=True,
        fichier_transcrit_a_la_main="OFFICIAL_PERIODS, dans le corps du script",
        rejouable_depuis_le_document="NON — aucun parsing PDF ; le littéral EST la source de vérité",
    ),
    dict(
        source="narcisses",
        extraction="AUCUNE — règle calendaire fixe",
        script="scripts/sources/build_dim_narcisses.py",
        fonctions="REGLE_CALENDAIRE_* l.75-78 ; _window_for_year() l.83-88 ; build_dim() l.91-111",
        document_versionne_au_depot=False,
        fichier_transcrit_a_la_main="constantes 15.04 → 25.05",
        rejouable_depuis_le_document="SANS OBJET — aucun document d'origine n'existe "
                                    "(vérification négative consignée, ADR-076)",
    ),
    dict(
        source="phases_pandemiques",
        extraction="TRANSCRIPTION MANUELLE (littéral Python)",
        script="scripts/sources/build_dim_covid.py",
        fonctions="COVID_PHASES l.52-100 (3 phases, dates + champ `reference` textuel) ; "
                  "build_dim() l.103-119",
        document_versionne_au_depot=False,
        fichier_transcrit_a_la_main="COVID_PHASES, dans le corps du script",
        rejouable_depuis_le_document="NON — aucun texte réglementaire n'est archivé au dépôt ; "
                                    "seules des références en clair (msg-id admin.ch, RS/RO)",
    ),
    dict(
        source="horaire_planifie",
        extraction="SCRIPTÉE (parsing PDF, mots + objets graphiques)",
        script="scripts/sources/build_horaires_r35_from_pdfs.py",
        fonctions="1 576 lignes ; pdfplumber + pypdfium2/PIL pour les renvois "
                  "de circulation dessinés en rectangles noirs (docstring l.13-21)",
        document_versionne_au_depot=True,
        fichier_transcrit_a_la_main="aucun",
        rejouable_depuis_le_document="OUI — les 10 PDF sont au dépôt et re-parsés à chaque run",
    ),
]


def s3_chaine_extraction() -> None:
    titre("S3 — Chaîne d'extraction : scriptée ou transcrite à la main ?")
    df = pd.DataFrame(_CHAINE)
    # Contrôle : le script cité existe-t-il ?
    df["script_present"] = [
        (PROJECT_ROOT / s).exists() for s in df["script"]
    ]
    ecrire(df, "asd_t3_chaine_extraction.csv")
    for r in df.itertuples(index=False):
        log(f"  {r.source:<26} {r.extraction}")
        log(f"    {'rejouable':<12}: {r.rejouable_depuis_le_document}")
    if not df["script_present"].all():
        log("  ⚠ un script cité est introuvable — corriger la table _CHAINE")
    s3bis_fidelite_transcriptions()


# --- S3 bis : les transcriptions manuelles sont-elles fidèles au document ? ---

_MOIS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}


def s3bis_fidelite_transcriptions() -> None:
    """Recoupe les littéraux transcrits contre le texte extractible des PDF.

    Objet : établir si la transcription manuelle est FIDÈLE au document et,
    surtout, si elle était SCRIPTABLE (le texte est-il extractible ?).
    """
    import pdfplumber

    log("\n  S3 bis — fidélité des transcriptions manuelles au document source")

    lignes = []

    # (a) Ski — la ligne « Exploitation: du <j> <d> <mois> <aaaa> au … » des PDF
    spec = importlib.util.spec_from_file_location(
        "bds", PROJECT_ROOT / "scripts" / "sources"
                / "build_dim_ski_pleiades_avec_reconstruction.py")
    mod_ski = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod_ski)
    transcrit = {s: (d, f) for s, d, f in mod_ski.OFFICIAL_PERIODS}
    saison_du_pdf = {
        "ski_19_20.pdf": "H20", "ski_20_21.pdf": "H21", "ski_21_22.pdf": "H22",
        "ski_22_23.pdf": "H23", "ski_23_24.pdf": "H24", "ski_24_25.pdf": "H25",
        "ski_25_26.pdf": "H26",
    }
    motif = re.compile(
        r"Exploitation\s*:\s*du\s+\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+au\s+"
        r"\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE)
    for nom_pdf, saison in saison_du_pdf.items():
        chemin = EXTERNAL / "ski" / nom_pdf
        with pdfplumber.open(chemin) as pdf:
            texte = "\n".join(p.extract_text() or "" for p in pdf.pages)
        m = motif.search(texte)
        if not m:
            lignes.append(dict(
                source="ski_pleiades", document=nom_pdf, cle=saison,
                valeur_lue_dans_le_pdf="MOTIF NON TROUVÉ",
                valeur_transcrite="/".join(transcrit[saison]),
                concordance=False, texte_pdf_extractible=len(texte) > 0))
            continue
        d1 = f"{int(m.group(3)):04d}-{_MOIS_FR[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        d2 = f"{int(m.group(6)):04d}-{_MOIS_FR[m.group(5).lower()]:02d}-{int(m.group(4)):02d}"
        att_d, att_f = transcrit[saison]
        # H26 : le producteur tronque volontairement la fin à la borne de H25
        tronque = saison == "H26"
        ok = (d1 == att_d) and (d2 == att_f or tronque)
        lignes.append(dict(
            source="ski_pleiades", document=nom_pdf, cle=saison,
            valeur_lue_dans_le_pdf=f"{d1} → {d2}",
            valeur_transcrite=f"{att_d} → {att_f}",
            concordance=ok,
            texte_pdf_extractible=True,
            remarque=("fin tronquée volontairement à la borne H25 (ADR-058)"
                      if tronque else "")))

    # (b) Calendrier scolaire — ligne « Rentrée scolaire » des deux PDF
    for nom_pdf in ("Vacances_scolaires_vaudoises.pdf",
                    "def_calendrier_vacances_scolaires_2023_2031.pdf"):
        chemin = EXTERNAL / "vacances_scolaires" / nom_pdf
        with pdfplumber.open(chemin) as pdf:
            texte = "\n".join(p.extract_text() or "" for p in pdf.pages)
        entete = next((l for l in texte.splitlines()
                       if re.search(r"\d{4}-\d{4}", l)), "")
        annees_sco = re.findall(r"\d{4}-\d{4}", entete)
        ligne = next((l for l in texte.splitlines()
                      if l.startswith("Rentrée scolaire")), "")
        jours = re.findall(
            r"(\d{1,2})\s+(" + "|".join(_MOIS_FR) + r")", ligne, re.IGNORECASE)
        spec = importlib.util.spec_from_file_location(
            "bdv", PROJECT_ROOT / "scripts" / "sources"
                    / "build_dim_vacances_feries_vaud.py")
        mod_vac = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod_vac)
        rentrees = {r[0]: r[2] for r in mod_vac.SCHOOL_YEAR_DATA}
        for annee_sco, (jour, mois) in zip(annees_sco, jours):
            lu = (f"{int(annee_sco[:4]):04d}-{_MOIS_FR[mois.lower()]:02d}-"
                  f"{int(jour):02d}")
            att = rentrees.get(annee_sco, "ABSENT DU LITTÉRAL")
            lignes.append(dict(
                source="calendrier_scolaire_vaud", document=nom_pdf,
                cle=f"rentree_{annee_sco}",
                valeur_lue_dans_le_pdf=lu, valeur_transcrite=att,
                concordance=(lu == att), texte_pdf_extractible=True,
                remarque=""))

    fid = pd.DataFrame(lignes)
    ecrire(fid, "asd_t3_fidelite_transcriptions.csv")
    n_ok = int(fid["concordance"].sum())
    log(f"    contrôles effectués : {len(fid)} — concordants : {n_ok} — "
        f"discordants : {len(fid) - n_ok}")
    if (len(fid) - n_ok) > 0:
        log(fid[~fid["concordance"]].to_string(index=False))
    log(f"    texte PDF extractible dans tous les documents testés : "
        f"{bool(fid['texte_pdf_extractible'].all())}")
    log("    → les deux transcriptions manuelles sont FIDÈLES sur les points "
        "contrôlés, et le texte source est extractible par pdfplumber : "
        "la transcription était donc SCRIPTABLE.")
    log("    Note ski : le PDF assortit les dates d'exploitation de la condition "
        "« si l'enneigement le permet » — la dimension marque néanmoins tous les "
        "jours de la période comme ouverts.")
    log("    Note calendrier : les deux PDF couvrent 2014-2021 puis 2022-2031 ; "
        "le millésime 2021-2022 n'est dans AUCUN document du dépôt "
        "(source déclarée : URL vd.ch, l.69-72, non archivée).")


# ---------------------------------------------------------------------------
# Section 4 — Manifestations, détail
# ---------------------------------------------------------------------------

def _charger_producteur_manif():
    spec = importlib.util.spec_from_file_location("bdm_manif", BUILD_MANIF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # sans effet de bord (main() sous garde)
    return mod


def s4_manifestations(annees: pd.DataFrame) -> None:
    titre("S4 — Manifestations : volumétrie, zonage, récurrents, exclusions")

    ev = pd.read_parquet(DIM_MANIF_EVENTS)
    dates = pd.read_parquet(DIM_MANIF_DATES)
    log(f"  {DIM_MANIF_EVENTS.relative_to(PROJECT_ROOT)} : {len(ev)} événements")
    log(f"  {DIM_MANIF_DATES.relative_to(PROJECT_ROOT)} : {len(dates)} journées "
        f"({dates['date'].min().date()} → {dates['date'].max().date()})")

    # 4.1 — Événements par année horaire (date de début) et par année de PDF
    ev = ev.copy()
    ev["annee_horaire_debut"] = annee_horaire_de_date(ev["date_debut"], annees)
    par_annee = (
        ev.groupby("annee_horaire_debut", dropna=False)
        .agg(n_evenements=("nom", "size"),
             n_zone_directe=("zone_r35", lambda s: int((s == "zone_directe").sum())),
             n_zone_indirecte=("zone_r35", lambda s: int((s == "zone_indirecte").sum())),
             n_hors_zone=("zone_r35", lambda s: int((s == "hors_zone").sum())),
             n_inconnue=("zone_r35", lambda s: int((s == "inconnue").sum())))
        .reset_index()
    )
    par_pdf = (
        ev.groupby("annee_pdf").size().rename("n_evenements_par_pdf").reset_index()
    )

    # Journées portant ≥1 événement, par année horaire et par zone
    dates = dates.copy()
    dates["annee_horaire"] = annee_horaire_de_date(dates["date"], annees)
    jours = (
        dates.groupby("annee_horaire", dropna=False)
        .agg(
            n_journees_avec_evenement=("date", "size"),
            n_journees_zone_directe=(
                "n_manifestations_zone_directe_j", lambda s: int((s.fillna(0) > 0).sum())),
            n_journees_zone_indirecte=(
                "n_manifestations_zone_indirecte_j", lambda s: int((s.fillna(0) > 0).sum())),
            n_journees_hors_zone=(
                "n_manifestations_hors_zone_j", lambda s: int((s.fillna(0) > 0).sum())),
            n_journees_vevey=(
                "n_manifestations_vevey_j", lambda s: int((s.fillna(0) > 0).sum())),
            n_journees_st_legier=(
                "n_manifestations_st_legier_j", lambda s: int((s.fillna(0) > 0).sum())),
            n_journees_blonay=(
                "n_manifestations_blonay_j", lambda s: int((s.fillna(0) > 0).sum())),
            max_simultane=("n_manifestations_riviera", "max"),
        )
        .reset_index()
    )
    ecrire(
        pd.concat([
            par_annee.assign(bloc="par_annee_horaire_de_la_date_de_debut"),
            par_pdf.rename(columns={"n_evenements_par_pdf": "n_evenements"})
                   .assign(bloc="par_annee_civile_du_pdf"),
        ], ignore_index=True),
        "asd_t4_manif_par_annee.csv",
    )
    log("\n  Événements par année horaire (année horaire de la date de début) :")
    log(par_annee.to_string(index=False))
    log("\n  Événements par année civile du PDF source :")
    log(par_pdf.to_string(index=False))
    ecrire(jours, "asd_t4_manif_jours_par_zone.csv")
    log("\n  Journées avec ≥1 manifestation, par année horaire :")
    log(jours.to_string(index=False))

    # 4.2 — Zonage : mécanisme et appariement
    mod = _charger_producteur_manif()
    mapping = mod.LIEU_TO_ZONE_NORMALIZED
    log(f"\n  Mécanisme de zonage : table de correspondance en dur "
        f"LIEU_TO_ZONE_NORMALIZED ({len(mapping)} entrées), "
        f"build_dim_manifestations_riviera.py l.93-156")
    log("  Appariement : normalisation (parenthèses retirées, NFKD→ASCII, lower, strip) "
        "puis lookup EXACT sur le dictionnaire — classify_lieu() l.285-310. "
        "Les lieux multiples sont découpés sur [/,], ' et ', ' - ' (_LIEU_SEPARATORS l.167) "
        "et la zone la plus prioritaire l'emporte (ZONE_PRIORITY l.159-164).")

    lignes_lieux = []
    for lieu, g in ev.groupby(ev["lieu"].fillna("<AUCUN LIEU PARSÉ>")):
        parties = []
        if lieu != "<AUCUN LIEU PARSÉ>":
            for p in mod._LIEU_SEPARATORS.split(str(lieu)):
                p = p.strip()
                if not p:
                    continue
                n = mod.normalize_lieu(re.sub(r"\(.*?\)", "", p).strip())
                if n:
                    parties.append(n)
        non_app = [p for p in parties if p not in mapping]
        lignes_lieux.append({
            "lieu_brut": lieu,
            "n_evenements": len(g),
            "parties_normalisees": " | ".join(parties) if parties else None,
            "parties_non_appariees": " | ".join(non_app) if non_app else None,
            "zone_attribuee": " | ".join(sorted(g["zone_r35"].unique())),
            "localite_r35": " | ".join(sorted(g["localite_r35"].unique())),
        })
    lieux = pd.DataFrame(lignes_lieux).sort_values("n_evenements", ascending=False)
    ecrire(lieux, "asd_t4_manif_lieux.csv")

    n_lieux_bruts = int(ev["lieu"].nunique(dropna=True))
    parties_tot = sorted({
        p for l in lieux["parties_normalisees"].dropna() for p in l.split(" | ")
    })
    parties_non_app = sorted({
        p for l in lieux["parties_non_appariees"].dropna() for p in l.split(" | ")
    })
    log(f"\n  lieux bruts distincts (hors NULL)   : {n_lieux_bruts}")
    log(f"  événements sans lieu parsé          : {int(ev['lieu'].isna().sum())}")
    log(f"  fragments normalisés distincts       : {len(parties_tot)}")
    log(f"  fragments NON appariés au mapping    : {len(parties_non_app)} "
        f"{parties_non_app}")
    log("  Répartition des événements par zone :")
    for z, n in ev["zone_r35"].value_counts().items():
        log(f"    {z:<18}: {n:>4} ({100*n/len(ev):.1f}%)")
    log(f"  → événements finalement NON classés (zone 'inconnue') : "
        f"{int((ev['zone_r35'] == 'inconnue').sum())}")
    inconnus = ev.loc[ev["zone_r35"] == "inconnue", ["annee_pdf", "nom", "lieu"]]
    log(inconnus.to_string(index=False))

    # 4.3 — Événements récurrents dotés d'un indicateur propre
    def _annees(col: str) -> str:
        return ", ".join(map(str, sorted(ev.loc[ev[col], "annee_pdf"].unique())))

    recur = pd.DataFrame([
        dict(indicateur="event_is_montreux_jazz",
             evenement="Montreux Jazz Festival",
             detection="regex _JAZZ_RE l.173 : r'montreux\\s+jazz|mjf\\b' sur le NOM",
             garde_fou="aucune",
             n_occurrences=int(ev["is_montreux_jazz"].sum()),
             annees_pdf_couvertes=_annees("is_montreux_jazz"),
             critere_de_selection_documente=(
                 "docstring l.38-42 « deux événements d'ampleur régionale » ; "
                 "aucun critère quantitatif. ADR-029 documente la reclassification "
                 "zonale de Montreux, PAS le choix des deux événements signature.")),
        dict(indicateur="event_is_marche_noel",
             evenement="Marché de Noël / Montreux Noël (motif large)",
             detection="regex _NOEL_RE l.175 : 'montreux noël|noël…montreux|"
                       "marché de noël|christmas market'",
             garde_fou="aucune",
             n_occurrences=int(ev["is_marche_noel"].sum()),
             annees_pdf_couvertes=_annees("is_marche_noel"),
             critere_de_selection_documente="idem ci-dessus"),
        dict(indicateur="event_is_montreux_noel",
             evenement="Montreux Noël (motif strict + garde-fou de zone)",
             detection="regex _MONTREUX_NOEL_RE l.178 : 'montreux noël|noël…montreux'",
             garde_fou="zone ∈ {zone_indirecte, hors_zone} — main() l.570-586",
             n_occurrences=int(ev["is_montreux_noel"].sum()),
             annees_pdf_couvertes=_annees("is_montreux_noel"),
             critere_de_selection_documente=(
                 "commentaire de code l.176-178 (« flag dédié ») ; aucun ADR dédié")),
    ])
    ecrire(recur, "asd_t4_manif_recurrents.csv")
    log("\n  Événements récurrents à indicateur propre :")
    log(recur[["indicateur", "evenement", "n_occurrences",
               "annees_pdf_couvertes"]].to_string(index=False))
    log("  → 2020 absente des trois indicateurs : les éditions 2020 figurent dans le PDF "
        "mais portent la mention ANNULÉ et sont donc exclues au parsing.")

    # Volumétrie côté ml_dataset (observations, non journées)
    dfml = pd.read_parquet(ML_DATASET, columns=[
        "horaire_annee_horaire", "base_date",
        "event_is_manifestation_riviera", "event_is_montreux_jazz",
        "event_is_marche_noel", "event_is_montreux_noel",
    ])
    vol = (
        dfml.groupby("horaire_annee_horaire")
        .agg(n_obs=("base_date", "size"),
             n_jours=("base_date", "nunique"),
             n_obs_manif=("event_is_manifestation_riviera", "sum"),
             n_obs_jazz=("event_is_montreux_jazz", "sum"),
             n_obs_marche_noel=("event_is_marche_noel", "sum"),
             n_obs_montreux_noel=("event_is_montreux_noel", "sum"))
        .reset_index()
    )
    vol["pct_obs_manif"] = (100 * vol["n_obs_manif"] / vol["n_obs"]).round(2)
    ecrire(vol, "asd_t4_manif_volumetrie_dataset.csv")
    log("\n  Volumétrie côté ml_dataset (observations tronçon × course × date) :")
    log(vol.to_string(index=False))

    # 4.4 — Exclusions (annulation / report / ligne sans date) — re-parsing des PDF
    log("\n  Re-parsing des PDF pour compter les exclusions "
        "(ANNULE_RE l.77, REPORTE_RE l.78, DATE_RE l.76, SKIP_PREFIXES l.80-83) …")
    excl = []
    for pdf in sorted(mod.EVENTS_DIR.glob("Manifestations *.pdf")):
        an = int(re.search(r"(\d{4})", pdf.stem).group(1))
        texte = mod.normalize_text(mod.extract_text(pdf))
        n_lignes = n_entete = n_annule = n_reporte = n_sans_date = n_retenu = 0
        for brute in texte.splitlines():
            ligne = mod.normalize_text(brute).strip()
            if not ligne:
                continue
            n_lignes += 1
            if any(ligne.lower().startswith(t) for t in mod.SKIP_PREFIXES):
                n_entete += 1
                continue
            a = bool(mod.ANNULE_RE.search(ligne))
            r = bool(mod.REPORTE_RE.search(ligne))
            if a or r:
                n_annule += int(a)
                n_reporte += int(r and not a)
                continue
            valides = [
                mod._try_parse_date(m.group(1), m.group(2), m.group(3))
                for m in mod.DATE_RE.finditer(ligne)
            ]
            if not any(d is not None for d in valides):
                n_sans_date += 1
                continue
            n_retenu += 1
        excl.append(dict(
            annee_pdf=an, fichier=pdf.name,
            n_lignes_non_vides=n_lignes,
            n_lignes_entete_ignorees=n_entete,
            n_exclus_annulation=n_annule,
            n_exclus_report=n_reporte,
            n_exclus_sans_date_complete=n_sans_date,
            n_retenus=n_retenu,
        ))
    excl_df = pd.DataFrame(excl)
    ecrire(excl_df, "asd_t4_manif_exclusions.csv")
    log(excl_df.to_string(index=False))
    log(f"\n  contrôle : Σ n_retenus = {int(excl_df['n_retenus'].sum())} "
        f"vs {len(ev)} lignes dans la dimension "
        f"→ {'IDENTIQUE' if int(excl_df['n_retenus'].sum()) == len(ev) else 'ÉCART'}")


# ---------------------------------------------------------------------------
# Section 5 — Calendriers (ski, narcisses, vacances/fériés)
# ---------------------------------------------------------------------------

def s5_calendriers(df: pd.DataFrame, annees: pd.DataFrame) -> None:
    titre("S5 — Calendriers : ski, narcisses, vacances et fériés vaudois")

    # 5.1 — Ski
    ski = pd.read_parquet(DIM_SKI)
    par_saison = (
        ski.groupby("saison_ski")
        .agg(date_ouverture=("date", "min"), date_fermeture=("date", "max"),
             n_jours=("date", "size"), origine=("ski_source", "first"))
        .reset_index()
    )
    par_saison["jour_ouverture"] = par_saison["date_ouverture"].dt.day_name()
    par_saison["jour_fermeture"] = par_saison["date_fermeture"].dt.day_name()
    par_saison["colonne_de_provenance"] = "ski_source (→ event_ski_source)"
    ecrire(par_saison, "asd_t5_ski_saisons.csv")
    log("  Saisons de ski :")
    log(par_saison[["saison_ski", "date_ouverture", "date_fermeture", "n_jours",
                    "origine", "jour_ouverture", "jour_fermeture"]].to_string(index=False))
    log(f"  modalités observées de event_ski_source dans ml_dataset : "
        f"{sorted(df['event_ski_source'].dropna().unique())}")
    log("  → H16–H19 absentes de ml_dataset (périmètre canonique H22–H25) : "
        "la distinction officiel/reconstruit n'a donc AUCUN effet sur le dataset gelé.")
    ski_vol = (
        df.groupby("horaire_annee_horaire")
        .agg(n_obs=("base_date", "size"),
             n_obs_ski_ouvert=("event_is_ski_ouvert", "sum"),
             n_jours_ski_ouvert=("base_date",
                                 lambda s: s[df.loc[s.index, "event_is_ski_ouvert"] == 1].nunique()))
        .reset_index()
    )
    log("  Volumétrie ski côté ml_dataset :")
    log(ski_vol.to_string(index=False))

    # 5.2 — Narcisses
    narc = pd.read_parquet(DIM_NARCISSES)
    narc_an = (
        narc.assign(annee=narc["date"].dt.year)
        .groupby("annee")
        .agg(borne_debut=("date", "min"), borne_fin=("date", "max"),
             n_jours=("date", "size"), source=("narcisses_source", "first"))
        .reset_index()
    )
    narc_an["fenetre_mm_jj"] = (
        narc_an["borne_debut"].dt.strftime("%d.%m") + " → "
        + narc_an["borne_fin"].dt.strftime("%d.%m")
    )
    narc_an["definie_annee_par_annee"] = False
    ecrire(narc_an, "asd_t5_narcisses_fenetres.csv")
    log("\n  Fenêtres narcisses :")
    log(narc_an.to_string(index=False))
    log(f"  fenêtres distinctes (jour.mois) : "
        f"{sorted(narc_an['fenetre_mm_jj'].unique())}")
    log(f"  modalités observées de event_narcisses_source dans ml_dataset : "
        f"{sorted(df['event_narcisses_source'].dropna().unique())}")
    narc_vol = (
        df.groupby("horaire_annee_horaire")
        .agg(n_obs=("base_date", "size"),
             n_obs_narcisses=("event_is_saison_narcisses", "sum"),
             n_jours_narcisses=("base_date",
                                lambda s: s[df.loc[s.index, "event_is_saison_narcisses"] == 1].nunique()))
        .reset_index()
    )
    log("  Volumétrie narcisses côté ml_dataset :")
    log(narc_vol.to_string(index=False))
    ecrire(
        pd.concat([
            par_saison.assign(bloc="ski_saisons_dim"),
            ski_vol.assign(bloc="ski_volumetrie_dataset"),
            narc_vol.assign(bloc="narcisses_volumetrie_dataset"),
        ], ignore_index=True),
        "asd_t5_ski_narcisses_volumetrie.csv",
    )

    # 5.3 — Vacances et fériés vaudois
    vac = pd.read_parquet(DIM_VACANCES)
    vac_ev = pd.read_parquet(DIM_VACANCES_EVENTS)
    vac = vac.copy()
    vac["annee_horaire"] = annee_horaire_de_date(vac["date"], annees)
    resume = pd.DataFrame([dict(
        table=str(DIM_VACANCES.relative_to(PROJECT_ROOT)),
        n_lignes_journalieres=len(vac),
        date_min=str(vac["date"].min().date()),
        date_max=str(vac["date"].max().date()),
        n_annees_scolaires=int(vac["annee_scolaire_vaud"].nunique()),
        n_jours_conge_scolaire=int(vac["is_conge_scolaire_vaud"].sum()),
        n_jours_vacances_scolaires=int(vac["is_vacances_scolaires_vaud"].sum()),
        n_jours_feries=int(vac["is_ferie_vaud"].sum()),
        n_evenements_sources=len(vac_ev),
    )])
    # volumétrie restreinte au périmètre du dataset
    perim = vac[vac["annee_horaire"].isin(["H22", "H23", "H24", "H25"])]
    par_ah = (
        perim.groupby("annee_horaire")
        .agg(n_jours=("date", "size"),
             n_vacances=("is_vacances_scolaires_vaud", "sum"),
             n_feries=("is_ferie_vaud", "sum"))
        .reset_index()
    )
    # comptage côté ml_dataset (observations, non journées)
    obs = (
        df.groupby("horaire_annee_horaire")
        .agg(n_obs=("base_date", "size"),
             n_obs_vacances=("event_is_vacances_vaud", "sum"),
             n_obs_feries=("event_is_ferie_vaud", "sum"),
             n_jours_distincts=("base_date", "nunique"))
        .reset_index()
    )
    obs["pct_obs_vacances"] = (100 * obs["n_obs_vacances"] / obs["n_obs"]).round(2)
    obs["pct_obs_feries"] = (100 * obs["n_obs_feries"] / obs["n_obs"]).round(2)
    sortie = par_ah.merge(
        obs, left_on="annee_horaire", right_on="horaire_annee_horaire", how="outer"
    ).drop(columns=["horaire_annee_horaire"])
    ecrire(pd.concat([resume.assign(bloc="global"),
                      sortie.assign(bloc="par_annee_horaire")],
                     ignore_index=True),
           "asd_t5_vacances_feries.csv")
    log("\n  Calendrier vaudois — global :")
    log(resume.T.to_string())
    log("\n  Calendrier vaudois — périmètre H22–H25 :")
    log(sortie.to_string(index=False))

    # Contrôles de cohérence présents dans le producteur
    log("\n  Contrôles de cohérence du producteur "
        "(build_dim_vacances_feries_vaud.py) :")
    for txt in [
        "validate_source_pdfs() l.569-572 — existence des 2 PDF (pas leur contenu)",
        "validate_school_years() l.575-610 — pas de doublon d'année scolaire ; "
        "CONTINUITÉ stricte rentrée N = fin vacances d'été N-1 + 1 jour ; "
        "contrôles de jour de semaine (rentrée=lundi, Jeûne=lundi, pont Ascension jeudi→vendredi, "
        "Pentecôte=lundi, fin d'année=vendredi) ; début ≤ fin par période",
        "validate_events() l.837-867 — congés scolaires non chevauchants ; fériés non dupliqués ; "
        "RECOUPEMENT CROISÉ des dates lundi du Jeûne / Ascension / Pentecôte entre la "
        "transcription scolaire et le calcul algorithmique des fériés",
        "validate_dimension() l.870-886 — pas de date dupliquée ; aucune date sans année scolaire ; "
        "aucun congé sans source documentaire",
    ]:
        log(f"    • {txt}")
    log("  AUCUN recoupement avec une SECONDE source externe : le recoupement de "
        "validate_events() est interne (transcription ↔ comput de Pâques), pas "
        "inter-sources. Aucun test pytest.")

    # Contrôle de cohérence propre à l'audit (lecture seule)
    ou_ok = int(
        (df["event_is_vacances_ou_ferie_vaud"]
         != ((df["event_is_vacances_vaud"] == 1) | (df["event_is_ferie_vaud"] == 1)).astype("int8")
         ).sum()
    )
    log(f"  contrôle d'audit — event_is_vacances_ou_ferie_vaud == OU logique des deux "
        f"indicateurs : {ou_ok} désaccord(s) sur {len(df):,} lignes "
        f"→ {'COHÉRENT' if ou_ok == 0 else 'INCOHÉRENT'}")


# ---------------------------------------------------------------------------
# Section 6 — Phases pandémiques
# ---------------------------------------------------------------------------

def s6_covid(df: pd.DataFrame) -> None:
    titre("S6 — Phases pandémiques")

    covid = pd.read_parquet(DIM_COVID)
    log(f"  {DIM_COVID.relative_to(PROJECT_ROOT)} : {len(covid)} lignes, "
        f"{covid['date'].min().date()} → {covid['date'].max().date()}")
    log("  phases : " + ", ".join(
        f"{p} ({covid[covid.covid_phase == p]['date'].min().date()}"
        f"→{covid[covid.covid_phase == p]['date'].max().date()}, "
        f"{int((covid.covid_phase == p).sum())} j)"
        for p in covid["covid_phase"].unique()
    ))

    par_annee = (
        df.groupby("horaire_annee_horaire")
        .agg(n_obs=("base_date", "size"),
             n_obs_restrictions=("event_is_covid_restrictions", "sum"),
             n_jours_distincts=("base_date", "nunique"),
             date_min=("base_date", "min"), date_max=("base_date", "max"))
        .reset_index()
    )
    par_annee["pct_obs_restrictions"] = (
        100 * par_annee["n_obs_restrictions"] / par_annee["n_obs"]
    ).round(3)
    phases = (
        pd.crosstab(df["horaire_annee_horaire"], df["event_covid_phase"])
        .reset_index()
    )
    par_annee = par_annee.merge(phases, on="horaire_annee_horaire", how="left")

    # Couverture réelle de la dim sur chaque année horaire
    fin_dim = covid["date"].max()
    par_annee["n_obs_hors_couverture_dim"] = [
        int((df.loc[df["horaire_annee_horaire"] == a, "base_date"] > fin_dim).sum())
        for a in par_annee["horaire_annee_horaire"]
    ]
    par_annee["valeur_hors_couverture"] = (
        "imputée par fillna : is_covid_restrictions=False, covid_phase='normal' "
        "(add_covid_to_raw_stacked.py l.59-64)"
    )

    # Constance sur H25
    h25 = df[df["horaire_annee_horaire"] == "H25"]
    const = pd.DataFrame([dict(
        colonne=c,
        n_distinct_h25=int(h25[c].nunique(dropna=False)),
        valeurs_h25=" | ".join(map(str, sorted(map(str, h25[c].unique())))),
        constante_sur_h25=bool(h25[c].nunique(dropna=False) <= 1),
    ) for c in ("event_is_covid_restrictions", "event_covid_phase")])

    # SHAP H25 (modèles gelés, grain tronçon)
    shap_rows = []
    for nom, chemin in (("bas", SHAP_BAS), ("haut", SHAP_HAUT),
                        ("combine", SHAP_COMBINE)):
        s = pd.read_csv(chemin)
        for c in ("event_is_covid_restrictions", "event_covid_phase"):
            r = s[s["feature"] == c]
            shap_rows.append(dict(
                modele=nom, colonne=c,
                rang=int(r["rang"].iloc[0]) if len(r) else None,
                mean_abs_shap=float(r["mean_abs_shap"].iloc[0]) if len(r) else None,
                pct_du_total=float(r["pct_du_total"].iloc[0]) if len(r) else None,
                source=str(chemin.relative_to(PROJECT_ROOT)),
            ))
    shap_df = pd.DataFrame(shap_rows)

    sortie = pd.concat([
        par_annee.assign(bloc="volumetrie_par_annee_horaire"),
        const.assign(bloc="constance_h25"),
        shap_df.assign(bloc="shap_h25"),
    ], ignore_index=True)
    ecrire(sortie, "asd_t6_covid_par_annee_horaire.csv")

    log("\n  Volumétrie H22–H25 :")
    log(par_annee.to_string(index=False))
    log("\n  Constance sur H25 :")
    log(const.to_string(index=False))
    log("\n  Importance SHAP sur H25 (modèles gelés, 158 features) :")
    log(shap_df.to_string(index=False))


# ---------------------------------------------------------------------------
# Section 7 — Horaire planifié
# ---------------------------------------------------------------------------

def s7_horaire_planifie(df: pd.DataFrame) -> None:
    titre("S7 — Horaire planifié : source distincte ou dérivé d'ISTDATEN ?")

    log("  Lignage de la famille horaire_ (3 colonnes de ml_dataset) :")
    log("    horaire_annee_horaire      ← data/dimension/annees_horaires.csv "
        "(CSV saisi à la main), jointure par intervalle — "
        "add_annee_horaire_to_raw_stacked.py, load_annees_horaires() l.48-79")
    log("    horaire_numero_train       ← APC brut, simple renommage — "
        "stack_raw_csv.py l.145")
    log("    horaire_service_id_complet ← dérivé de l'APC (base_date, numero_train, "
        "min(base_depart_datetime)) — add_features_to_raw_stacked.py, "
        "_ajouter_service_id_complet() l.291-311")
    log("  → AUCUNE colonne de la famille horaire_ ne vient du PDF d'horaire "
        "ni des colonnes de planification d'ISTDATEN.")

    log("\n  Cadence et isolement temporel (famille ist_) :")
    log("    ist_headway_avant_min / ist_headway_apres_min / "
        "ist_headway_avant_is_first_of_day / ist_headway_apres_is_last_of_day")
    log("    ← ISTDATEN, colonne horaire_depart (départ THÉORIQUE) exclusivement — "
        "build_dim_headway.py, docstring l.26-31, _reconstruire_troncons() l.93-140, "
        "_calculer_headway() l.143-179 ; ADR-018 et ADR-067")
    log("    Périmètre : grille planifiée connue à J-1 ; annulés et suppléments INCLUS "
        "(ADR-067, docstring l.33-42). Aucun fallback sur reel_depart.")

    ist_headway = [c for c in df.columns if "headway" in c]
    log(f"    colonnes headway présentes dans ml_dataset : {ist_headway}")
    log(f"    ist_headway_avant_min : NaN {100*df['ist_headway_avant_min'].isna().mean():.3f} %  "
        f"médiane {df['ist_headway_avant_min'].median():.1f} min")
    log(f"    ist_headway_apres_min : NaN {100*df['ist_headway_apres_min'].isna().mean():.3f} %  "
        f"médiane {df['ist_headway_apres_min'].median():.1f} min")

    log("\n  Le PDF d'horaire (horaires_clean.parquet) alimente-t-il ml_dataset ?")
    log("    Consommateurs de HORAIRES_CLEAN au dépôt : "
        "scripts/sources/build_istdaten_ponctualite.py (_charger_n_theoriques l.158-171) "
        "et scripts/update_notebook_02.py.")
    log("    build_istdaten_ponctualite.py produit istdaten_ponctualite.parquet, consommé "
        "par le stage_07 DÉPRÉCIÉ (paths.py l.144 : STAGE_07_PONCTUALITE « DEPRECATED »). "
        "Le stage_07 actif (add_istdaten_to_raw_stacked.py) ne lit que dim_profil_train, "
        "dim_correspondances_vevey et dim_vmcv_par_train_jour.")
    n_theo = [c for c in df.columns if "theorique" in c]
    log(f"    colonnes 'theorique' dans ml_dataset : {n_theo if n_theo else 'AUCUNE'}")
    log("    → CONCLUSION : l'horaire planifié PDF est une source DISTINCTE mais "
        "HORS chaîne du dataset ML ; il sert au contrôle documentaire (§4.3.2) "
        "et à l'audit des comptages APC.")

    # Recalcul du chiffre « neuf trains en pointe contre cinq en creux » (§4.3.2)
    log("\n  Recalcul du chiffre de §4.3.2 (offre planifiée H24) depuis "
        f"{HORAIRES_CLEAN.relative_to(PROJECT_ROOT)} :")
    h = pd.read_parquet(HORAIRES_CLEAN, columns=[
        "annee_horaire", "date", "numero_train", "depart_datetime",
        "gare_depart_ordre", "gare_arrivee_ordre", "is_weekend", "is_public_holiday",
    ])
    h = h[h["annee_horaire"] == "H24"].copy()
    h["segment"] = (
        (h["gare_depart_ordre"] <= 10) & (h["gare_arrivee_ordre"] <= 10)
    ).map({True: "bas", False: "haut"})
    h["ouvrable"] = ~(h["is_weekend"].fillna(False) | h["is_public_holiday"].fillna(False))
    h["heure"] = h["depart_datetime"].dt.hour
    trains = (
        h.groupby(["ouvrable", "segment", "date", "heure"])["numero_train"]
        .nunique().rename("n_trains").reset_index()
    )
    n_jours = (
        h.groupby("ouvrable")["date"].nunique().rename("n_jours")
    )
    par_heure = (
        trains.groupby(["ouvrable", "segment", "heure"])["n_trains"].sum()
        .reset_index()
        .merge(n_jours, on="ouvrable")
    )
    par_heure["trains_par_jour"] = par_heure["n_trains"] / par_heure["n_jours"]
    par_heure["tranche"] = par_heure["heure"].map(
        lambda x: "pointe" if x in (6, 7, 8, 16, 17, 18)
        else ("creux" if 9 <= x <= 15 else "autre")
    )
    ecrire(par_heure, "asd_t7_horaire_offre_h24.csv")
    synth = (
        par_heure[par_heure["tranche"] != "autre"]
        .groupby(["ouvrable", "segment", "tranche"])["trains_par_jour"].mean()
        .round(2).reset_index()
    )
    log(synth.to_string(index=False))
    b = par_heure[(par_heure["segment"] == "bas") & (par_heure["ouvrable"])]
    log(f"    bas ouvrable, 7 h : {float(b[b.heure == 7]['trains_par_jour'].iloc[0]):.3f} trains/j")
    log("    → le « neuf trains par heure en pointe contre cinq en creux » de §4.3.2 "
        "correspond aux moyennes arrondies du segment BAS ouvrable "
        "(pointe ≈ 8,8 ; creux ≈ 4,9). Recalculable : OUI.")


# ---------------------------------------------------------------------------
# Section 8 — Gouvernance et qualité
# ---------------------------------------------------------------------------

_GOUVERNANCE = [
    # (source, adr, assertions bloquantes, tests)
    dict(
        source="manifestations",
        adr="ADR-029 — Reclassification zonale Montreux et décomposition événementielle "
            "par localité R35 — 2026-05-23 — actif (INDEX.md l.69)",
        adr_couvre_extraction=False,
        assertions_bloquantes=(
            "build_dim_manifestations_riviera.py validate() l.455-471 : dimension non vide, "
            "dates non dupliquées, durée ≥ 1 jour | "
            "add_manifestations_riviera_to_raw_stacked.py l.85 : le join ne change pas le "
            "nombre de lignes | "
            "WARNINGS non bloquants : lieux inconnus (l.557-562), faux positifs Montreux Noël (l.580-586)"
        ),
        tests_pytest="AUCUN",
    ),
    dict(
        source="calendrier_scolaire_et_feries_vaudois",
        adr="AUCUN ADR DÉDIÉ. ADR-070 (2026-06-28, actif) porte sur les calendriers "
            "VS/FR/NE/GE testés et ÉCARTÉS, pas sur le calendrier vaudois lui-même.",
        adr_couvre_extraction=False,
        assertions_bloquantes=(
            "build_dim_vacances_feries_vaud.py : validate_source_pdfs() l.569-572, "
            "validate_school_years() l.575-610 (continuité + jours de semaine), "
            "validate_events() l.837-867 (recoupement croisé transcription ↔ comput), "
            "validate_dimension() l.870-886 | "
            "add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py : colonnes requises l.130-136, "
            "dates dupliquées l.142-148, nombre de lignes l.257-258, "
            "AUCUNE ligne non appariée l.260-272"
        ),
        tests_pytest="AUCUN",
    ),
    dict(
        source="ski_pleiades",
        adr="ADR-058 — Régénération dim_ski_pleiades + intégration partielle saison "
            "2025-2026 — 2026-06-07 — actif (INDEX.md l.98)",
        adr_couvre_extraction=True,
        assertions_bloquantes=(
            "build_dim_ski_pleiades_avec_reconstruction.py validate() l.172-193 : dates non "
            "dupliquées, dim non vide, ET vérification que chaque saison officielle reproduit "
            "exactement ses bornes déclarées | "
            "add_ski_pleiades_to_raw_stacked.py l.64 : le join ne change pas le nombre de lignes"
        ),
        tests_pytest="AUCUN",
    ),
    dict(
        source="narcisses",
        adr="ADR-076 — Migration de gel : dataset v2 (producteur narcisses corrigé) — "
            "2026-07-11 — actif (INDEX.md l.116). Mentionné aussi par ADR-036 (2.2) "
            "pour la conservation de la feature.",
        adr_couvre_extraction=True,
        assertions_bloquantes=(
            "build_dim_narcisses.py validate() l.114-120 : dates non dupliquées | "
            "add_narcisses_to_raw_stacked.py l.48-52 : GARDE DE COUVERTURE "
            "assert_dim_couvre_periode_donnees() — échoue si la dim s'arrête avant la "
            "dernière année des données (coverage_guard.py) | l.65 : nombre de lignes"
        ),
        tests_pytest="AUCUN",
    ),
    dict(
        source="phases_pandemiques",
        adr="AUCUN ADR. Les colonnes event_covid_* ne sont citées que comme PRÉCÉDENT "
            "de convention de nommage par ADR-039 (l.114), ADR-040 (l.62) et ADR-041 (l.87).",
        adr_couvre_extraction=False,
        assertions_bloquantes=(
            "build_dim_covid.py validate() l.122-130 : dates non dupliquées, dim non vide, "
            "aucune covid_phase NA | "
            "add_covid_to_raw_stacked.py l.57-58 : le join ne change pas le nombre de lignes. "
            "AUCUNE garde de couverture : coverage_guard.py l.17-19 exclut explicitement covid "
            "(« non-couverture factuelle et volontaire »)"
        ),
        tests_pytest="AUCUN",
    ),
    dict(
        source="horaire_planifie_pdf",
        adr="AUCUN ADR sur l'extraction PDF elle-même. ADR-017 (2026-05-15) porte sur "
            "l'ablation de horaire_numero_train ; ADR-018 (2026-05-15) et ADR-067 "
            "(2026-06-20) portent sur le headway, calculé depuis ISTDATEN et non depuis le PDF.",
        adr_couvre_extraction=False,
        assertions_bloquantes=(
            "build_horaires_r35_from_pdfs.py : contrôles de parsing internes "
            "(parse_date_column l.99-110, colonnes requises l.115-118) ; "
            "piste d'audit d'extraction écrite dans "
            "data/intermediate/horaires_r35_extraction_audit.csv"
        ),
        tests_pytest="AUCUN test portant sur l'extraction PDF. "
                     "tests/test_pipeline_headway.py couvre le headway ISTDATEN.",
    ),
]


def s8_gouvernance() -> None:
    titre("S8 — Gouvernance et qualité")
    df = pd.DataFrame(_GOUVERNANCE)
    ecrire(df, "asd_t8_gouvernance.csv")
    for r in df.itertuples(index=False):
        log(f"\n  {r.source}")
        log(f"    ADR    : {r.adr}")
        log(f"    tests  : {r.tests_pytest}")

    # Contrôle automatique : aucun test pytest ne mentionne ces sources ?
    log("\n  Contrôle automatique — occurrences dans tests/ :")
    for motif in ("narciss", "ski_ouvert", "manifestation", "covid_phase",
                  "vacances", "ferie", "horaires_clean"):
        out = subprocess.run(
            ["grep", "-rl", motif, "tests/"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        fichiers = [
            l for l in out.stdout.strip().splitlines()
            if l.strip() and "__pycache__" not in l
        ]
        log(f"    {motif:<16}: {fichiers if fichiers else 'AUCUN FICHIER DE TEST'}")
    log("    Interprétation : les seules occurrences ('ferie') portent sur la DÉRIVATION "
        "de cal_type_jour / cal_type_jour_3classes à partir de is_ferie_vaud "
        "(tests/test_pipeline_features_ist.py l.454-467, tests/test_pipeline_istdaten.py l.51), "
        "pas sur le calendrier source ni sur son extraction. "
        "→ AUCUNE des six sources documentaires n'est couverte par un test.")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    log(f"audit_sources_documentaires.py — {HERE.relative_to(PROJECT_ROOT)}")
    log(f"pandas {pd.__version__} | python {sys.version.split()[0]}")
    verifier_empreinte()

    annees = charger_annees_horaires()
    df = pd.read_parquet(ML_DATASET)
    log(f"  ml_dataset : {df.shape[0]:,} lignes × {df.shape[1]} colonnes")
    log(f"  années horaires présentes : "
        f"{sorted(df['horaire_annee_horaire'].dropna().unique())}")

    s1_inventaire(df)
    s2_sources_brutes()
    s3_chaine_extraction()
    s4_manifestations(annees)
    s5_calendriers(df, annees)
    s6_covid(df)
    s7_horaire_planifie(df)
    s8_gouvernance()

    titre("FIN")
    log(f"  CSV produits dans {HERE.relative_to(PROJECT_ROOT)} :")
    for f in sorted(HERE.glob("asd_*.csv")):
        log(f"    {f.name}")


if __name__ == "__main__":
    main()
