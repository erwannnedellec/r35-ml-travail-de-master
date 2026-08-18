"""
Construit la dimension des manifestations Montreux Riviera Tourisme.

Sources
-------
data/external/evenements/Manifestations YYYY.pdf  (2015-2024)

Chaque PDF liste les manifestations de l'année avec :
  - nom de l'événement
  - date de début (DD.MM.YYYY)
  - date de fin optionnelle (DD.MM.YYYY) — absent = événement sur un seul jour
  - lieu

Événements exclus
-----------------
- ANNULÉ/ANNULE  : événement supprimé
- REPORTÉ/REPORTE : date incertaine, non intégrable
- Lignes sans date DD.MM.YYYY complète : «En 2016», dates partielles, etc.

Classification géographique
---------------------------
Le critère de zonage est la **connectivité ferroviaire avec la R35**, pas la proximité
géographique pure. Trois zones :

  zone_directe   — gares desservies par la R35 (Vevey, Blonay, St-Légier, Pléiades…)
  zone_indirecte — communes connectées à Vevey/R35 par correspondance fréquente,
                   pouvant générer un débordement de fréquentation sur la R35.
                   Inclut Montreux et ses dépendances (Territet, Clarens, Chailly…) :
                   Montreux est connectée à Vevey (origine R35) par ligne du Léman à
                   haute fréquence ; ses grands événements (Jazz, Noël, trail…) génèrent
                   un effet d'attraction régional qui déborde sur le segment R35 via
                   visiteurs logés à Blonay/St-Légier et excursions aux Pléiades.
  hors_zone      — lieux sans connectivité pertinente vers la R35 :
                   côté Lavaux/Lausanne (Cully, Lutry, Rivaz…) et lieux desservis
                   exclusivement par d'autres lignes MOB (Rochers-de-Naye, Jaman).
  inconnue       — lieu non reconnu dans le mapping (WARNING loggé)

Événements signature R35
------------------------
Deux événements d'ampleur régionale sont détectés par matching sur le nom :
  is_montreux_jazz   — Montreux Jazz Festival (~16 j, fin juin/début juillet)
  is_marche_noel     — Marché de Noël de Montreux (~mi-nov → 24 déc)

Sorties
-------
- data/dimension/dim_manifestations_riviera_evenements.parquet  grain : 1 événement
- data/dimension/dim_manifestations_riviera.parquet             grain : 1 date (pour join)

CSV optionnels : toujours écrits à côté du parquet (petites tables).

Usage
-----
    python3 scripts/sources/build_dim_manifestations_riviera.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
import warnings
from pathlib import Path

import pandas as pd
import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

EVENTS_DIR = PROJECT_ROOT / "data" / "external" / "evenements"
DIM_DIR    = PROJECT_ROOT / "data" / "dimension"

OUTPUT_EVENEMENTS = DIM_DIR / "dim_manifestations_riviera_evenements.parquet"
OUTPUT_DATES      = DIM_DIR / "dim_manifestations_riviera.parquet"

DATE_RE    = re.compile(r"\b(\d{1,2})\.(\d{2})\.(\d{4})\b")
ANNULE_RE  = re.compile(r"annul[eé]", re.IGNORECASE)
REPORTE_RE = re.compile(r"report[eé]", re.IGNORECASE)

SKIP_PREFIXES = (
    "liste de manifestations",
    "manifestation",
)

# ---------------------------------------------------------------------------
# Classification géographique
# ---------------------------------------------------------------------------
# Mapping normalisé (lower + sans diacritiques) → zone
# Chaque entrée doit être dérivable d'une valeur réelle du catalogue.
# Compléter LIEU_TO_ZONE_NORMALIZED après le premier run en ajoutant les
# lieux inconnus signalés dans les WARNINGs.

LIEU_TO_ZONE_NORMALIZED: dict[str, str] = {
    # zone_directe — gares ou localités R35
    "vevey": "zone_directe",
    "blonay": "zone_directe",
    "blonay-chamby": "zone_directe",
    "st-legier": "zone_directe",
    "saint-legier": "zone_directe",
    "st legier": "zone_directe",
    "les pleiades": "zone_directe",
    "pleiades": "zone_directe",
    "hauteville": "zone_directe",
    "lally": "zone_directe",
    "tusinge": "zone_directe",
    "la chiesaz": "zone_directe",
    "vevey-vignerons": "zone_directe",
    # zone_indirecte — communes proches pouvant générer des correspondances
    "la tour-de-peilz": "zone_indirecte",
    "tour-de-peilz": "zone_indirecte",
    "corseaux": "zone_indirecte",
    "chexbres": "zone_indirecte",
    "corsier-sur-vevey": "zone_indirecte",
    "corsier s/vevey": "zone_indirecte",
    "corsier": "zone_indirecte",
    "chardonne": "zone_indirecte",
    "mont-pelerin": "zone_indirecte",
    "puidoux": "zone_indirecte",
    # zone_indirecte — Montreux et dépendances : connectées à Vevey par ligne du Léman
    # à haute fréquence. Grands événements (Jazz, Noël…) génèrent un effet d'attraction
    # régional qui déborde sur la R35 via Vevey. Reclassé de hors_zone → zone_indirecte.
    "montreux": "zone_indirecte",
    "territet": "zone_indirecte",
    "glion": "zone_indirecte",
    "caux": "zone_indirecte",
    "chillon": "zone_indirecte",
    "villeneuve": "zone_indirecte",
    "villeneuve-montreux": "zone_indirecte",
    "clarens": "zone_indirecte",
    "clarens s/montreux": "zone_indirecte",
    "vernex": "zone_indirecte",
    "veytaux": "zone_indirecte",
    "brent": "zone_indirecte",
    "chailly": "zone_indirecte",
    "chailly s/montreux": "zone_indirecte",
    "chernex": "zone_indirecte",
    # hors_zone — lieux sans connectivité pertinente vers la R35
    "rochers-de-naye": "hors_zone",   # ligne MOB Montreux-Rochers, pas de lien R35
    "jaman": "hors_zone",             # idem, col de Jaman accessible depuis Montreux
    "les avants": "hors_zone",        # idem
    "cully": "hors_zone",             # Lavaux, côté Lausanne
    "epesses": "hors_zone",
    "lavaux": "hors_zone",
    "lutry": "hors_zone",
    "rivaz": "hors_zone",
    "st-saphorin": "hors_zone",
    "lausanne": "hors_zone",
    # Fragments issus du split de "Aran s/Villette" (commune voisine de Cully)
    "aran s": "hors_zone",
    "aran": "hors_zone",
    "villette": "hors_zone",
    # Lavaux — "Grandvaux + Aran" : lieu combiné, format non splittable (séparateur +)
    "grandvaux + aran": "hors_zone",
    "grandvaux": "hors_zone",
    "riviera": "hors_zone",           # région entière, signal trop large
}

# Priorité des zones pour les lieux multi-localisations
ZONE_PRIORITY: dict[str, int] = {
    "zone_directe":   0,
    "zone_indirecte": 1,
    "hors_zone":      2,
    "inconnue":       3,
}

# Séparateurs de lieux multiples dans le champ `lieu`
_LIEU_SEPARATORS = re.compile(r"[/,]| et | - ")

# ---------------------------------------------------------------------------
# Patterns événements signature R35
# ---------------------------------------------------------------------------
# Matching insensible à la casse sur le nom de l'événement.
_JAZZ_RE       = re.compile(r"montreux\s+jazz|mjf\b", re.IGNORECASE)
# Noms réels observés dans les PDFs : "Montreux Noël", "25e Montreux Noël"
_NOEL_RE       = re.compile(r"montreux\s+no[eë]l|no[eë]l.*montreux|march[eé]\s+de?\s*no[eë]l|christmas\s+market", re.IGNORECASE)
# Noms réels observés dans les PDFs : "Montreux Noël", "25e Montreux Noël"
# Distinct de _NOEL_RE (is_marche_noel) : flag dédié au marché de Noël Montreux
_MONTREUX_NOEL_RE = re.compile(r"montreux\s+no[eë]l|no[eë]l.*montreux", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Extraction et parsing PDF
# ---------------------------------------------------------------------------

def extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def normalize_text(text: str) -> str:
    """Remplace les caractères typographiques non-ASCII courants."""
    return (
        text
        .replace("‐", "-")
        .replace("‑", "-")
        .replace(" ", " ")
        .replace("–", "-")
        .replace("—", "-")
    )


def normalize_lieu(lieu: str) -> str:
    """Normalise un lieu : suppression parenthèses isolées, lower, diacritiques, strip."""
    lieu = re.sub(r"[()]+", "", lieu)   # artefacts PDF : "Lausanne)" → "Lausanne"
    nfkd = unicodedata.normalize("NFKD", lieu)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_str.lower().strip()


def _try_parse_date(dd: str, mm: str, yyyy: str) -> pd.Timestamp | None:
    year = int(yyyy)
    # Typo récurrente dans les PDFs source : 1015 → 2015, 1023 → 2023, etc.
    if 1000 <= year < 2000 and 2010 <= year + 1000 <= 2030:
        year += 1000
    try:
        return pd.Timestamp(year, int(mm), int(dd))
    except ValueError:
        return None


def parse_line(line: str) -> dict | None:
    """
    Parse une ligne de texte PDF en événement.
    Retourne None si la ligne doit être ignorée.
    """
    line = normalize_text(line).strip()
    if not line:
        return None

    low = line.lower()
    if any(low.startswith(tok) for tok in SKIP_PREFIXES):
        return None

    if ANNULE_RE.search(line) or REPORTE_RE.search(line):
        return None

    matches = [
        (m.start(), m.end(), _try_parse_date(m.group(1), m.group(2), m.group(3)))
        for m in DATE_RE.finditer(line)
    ]
    valid = [(start, end, d) for start, end, d in matches if d is not None]
    if not valid:
        return None

    first_start, _, date_debut = valid[0]
    _, last_end, date_fin = valid[-1]

    nom = re.sub(r"[\s\-+]+$", "", line[:first_start]).strip()
    if not nom:
        return None

    lieu_raw = line[last_end:].strip()
    lieu = lieu_raw if lieu_raw else None

    return {
        "nom":          nom,
        "date_debut":   date_debut,
        "date_fin":     date_fin,
        "lieu":         lieu,
        "nombre_jours": (date_fin - date_debut).days + 1,
    }


def parse_pdf(pdf_path: Path) -> tuple[int, list[dict]]:
    """Parse un PDF, retourne (annee_pdf, liste d'événements)."""
    year_match = re.search(r"(\d{4})", pdf_path.stem)
    if not year_match:
        return 0, []
    annee_pdf = int(year_match.group(1))
    text = extract_text(pdf_path)
    events = []
    for raw_line in text.splitlines():
        row = parse_line(raw_line)
        if row is not None:
            row["annee_pdf"]  = annee_pdf
            row["source_pdf"] = pdf_path.name
            events.append(row)
    return annee_pdf, events


# ---------------------------------------------------------------------------
# Classification géographique
# ---------------------------------------------------------------------------

def classify_lieu(lieu: str | None) -> str:
    """
    Retourne la zone géographique d'un lieu.
    Pour les lieux multi-localisations, retourne la zone la plus prioritaire.
    """
    if not lieu or not str(lieu).strip():
        return "inconnue"

    parts = _LIEU_SEPARATORS.split(str(lieu))
    best_zone = "inconnue"
    best_priority = ZONE_PRIORITY["inconnue"]

    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Nettoyer les artefacts PDF : parenthèses, dates résiduelles, etc.
        part_clean = re.sub(r"\(.*?\)", "", part).strip()
        norm = normalize_lieu(part_clean)
        zone = LIEU_TO_ZONE_NORMALIZED.get(norm, "inconnue")
        prio = ZONE_PRIORITY.get(zone, 3)
        if prio < best_priority:
            best_priority = prio
            best_zone = zone

    return best_zone


def classify_localite_r35(lieu: str | None) -> str:
    """Classe un lieu dans l'une des 3 localités R35 par recherche de sous-chaîne.

    Détection insensible à la casse et aux diacritiques (via ``normalize_lieu``).
    Les trois noms sont distincts et discriminants — pas de mapping exhaustif nécessaire.

    Cas particuliers documentés :
    - "Les Pléiades" / "Pléiades" → "blonay" (crémaillère au-dessus de Blonay).
    - Lieux multi-localisations (ex. "Vevey/La Tour-de-Peilz/St-Légier") :
      priorité Vevey > Saint-Légier > Blonay (premier match dans l'ordre).

    Args:
        lieu: Champ lieu brut depuis le PDF (peut contenir des caractères spéciaux).

    Returns:
        "vevey", "saint_legier", "blonay", ou "hors_r35".
    """
    if not lieu or not str(lieu).strip():
        return "hors_r35"

    lieu_norm = normalize_lieu(str(lieu))

    if "vevey" in lieu_norm:
        return "vevey"
    if "legier" in lieu_norm:
        return "saint_legier"
    if "blonay" in lieu_norm or "pleiades" in lieu_norm:
        return "blonay"

    return "hors_r35"


def flag_signature_events(nom: str) -> tuple[bool, bool, bool]:
    """Retourne (is_montreux_jazz, is_marche_noel, is_montreux_noel_candidat) pour un nom.

    is_montreux_noel_candidat est le résultat brut du pattern — le garde-fou hors_zone
    est appliqué dans main() après classification géographique.
    """
    is_jazz                  = bool(_JAZZ_RE.search(nom))
    is_noel                  = bool(_NOEL_RE.search(nom))
    is_montreux_noel_candidat = bool(_MONTREUX_NOEL_RE.search(nom))
    return is_jazz, is_noel, is_montreux_noel_candidat


# ---------------------------------------------------------------------------
# Construction de la dimension date
# ---------------------------------------------------------------------------

def build_date_dimension(events: pd.DataFrame) -> pd.DataFrame:
    """Expand events → 1 ligne par date de manifestation, avec compteurs par zone."""
    if events.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "is_manifestation_riviera",
                "n_manifestations_riviera",
                "noms_manifestations_riviera",
                "n_manifestations_zone_directe_j",
                "n_manifestations_zone_indirecte_j",
                "n_manifestations_hors_zone_j",
                "n_manifestations_vevey_j",
                "n_manifestations_st_legier_j",
                "n_manifestations_blonay_j",
                "is_montreux_jazz",
                "is_marche_noel",
                "is_montreux_noel",
            ]
        )

    rows: list[dict] = []
    for _, ev in events.iterrows():
        for d in pd.date_range(ev["date_debut"], ev["date_fin"], freq="D"):
            rows.append({
                "date":        d,
                "nom":         ev["nom"],
                "zone_r35":    ev["zone_r35"],
                "localite_r35": ev["localite_r35"],
                "is_jazz":     ev["is_montreux_jazz"],
                "is_noel":     ev["is_marche_noel"],
                "is_montreux_noel": ev["is_montreux_noel"],
            })

    expanded = pd.DataFrame(rows)

    dim = (
        expanded.groupby("date", as_index=False)
        .agg(
            n_manifestations_riviera=(
                "nom", "count"
            ),
            noms_manifestations_riviera=(
                "nom", lambda x: "|".join(sorted(set(x)))
            ),
            n_manifestations_zone_directe_j=(
                "zone_r35", lambda x: (x == "zone_directe").sum()
            ),
            n_manifestations_zone_indirecte_j=(
                "zone_r35", lambda x: (x == "zone_indirecte").sum()
            ),
            n_manifestations_hors_zone_j=(
                "zone_r35", lambda x: (x == "hors_zone").sum()
            ),
            n_manifestations_vevey_j=(
                "localite_r35", lambda x: (x == "vevey").sum()
            ),
            n_manifestations_st_legier_j=(
                "localite_r35", lambda x: (x == "saint_legier").sum()
            ),
            n_manifestations_blonay_j=(
                "localite_r35", lambda x: (x == "blonay").sum()
            ),
            is_montreux_jazz=("is_jazz", "any"),
            is_marche_noel=("is_noel", "any"),
            is_montreux_noel=("is_montreux_noel", "any"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    dim.insert(1, "is_manifestation_riviera", True)

    # Typage
    for col in (
        "n_manifestations_riviera",
        "n_manifestations_zone_directe_j",
        "n_manifestations_zone_indirecte_j",
        "n_manifestations_hors_zone_j",
        "n_manifestations_vevey_j",
        "n_manifestations_st_legier_j",
        "n_manifestations_blonay_j",
    ):
        dim[col] = dim[col].astype("Int8")
    dim["is_montreux_jazz"] = dim["is_montreux_jazz"].astype(bool)
    dim["is_marche_noel"]   = dim["is_marche_noel"].astype(bool)
    dim["is_montreux_noel"]    = dim["is_montreux_noel"].astype(bool)

    return dim


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(events: pd.DataFrame, date_dim: pd.DataFrame) -> None:
    if events.empty:
        raise ValueError("Aucun événement parsé — vérifier le contenu des PDFs")

    dup = date_dim.loc[date_dim["date"].duplicated(keep=False)]
    if not dup.empty:
        raise ValueError(
            f"Dates dupliquées dans la dimension ({len(dup)} lignes) : "
            f"{dup['date'].head(5).tolist()}"
        )

    neg_duration = events.loc[events["nombre_jours"] < 1]
    if not neg_duration.empty:
        raise ValueError(
            f"{len(neg_duration)} événement(s) avec durée < 1 jour :\n"
            f"{neg_duration[['nom', 'date_debut', 'date_fin']].head(5)}"
        )


# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------

def print_summary(events: pd.DataFrame, date_dim: pd.DataFrame, unknown_lieux: list[str]) -> None:
    print(f"\nDimension manifestations Riviera :")
    print(f"  événements          : {len(events):,}")
    print(f"  dates avec manifest.: {len(date_dim):,}")
    print(f"  couverture          : {date_dim['date'].min().date()} → {date_dim['date'].max().date()}")
    print(f"  max simultané       : {int(date_dim['n_manifestations_riviera'].max())}")

    print("\nRépartition par zone géographique :")
    zone_counts = events["zone_r35"].value_counts()
    for zone, count in zone_counts.items():
        pct = count / len(events) * 100
        print(f"  {zone:<25}: {count:>4} événements ({pct:.1f}%)")

    print("\nRépartition par localité R35 (zone_directe uniquement) :")
    directe_mask = events["zone_r35"] == "zone_directe"
    localite_counts = events.loc[directe_mask, "localite_r35"].value_counts()
    for localite in ("vevey", "saint_legier", "blonay", "hors_r35"):
        count = int(localite_counts.get(localite, 0))
        pct = count / max(int(directe_mask.sum()), 1) * 100
        print(f"  {localite:<20}: {count:>4} événements ({pct:.1f}%)")

    print("\nÉvénements signature :")
    n_jazz = int(events["is_montreux_jazz"].sum())
    n_noel = int(events["is_marche_noel"].sum())
    n_montreux_noel = int(events["is_montreux_noel"].sum())
    print(f"  Montreux Jazz Festival : {n_jazz} occurrences")
    print(f"  Marché de Noël Montreux: {n_noel} occurrences")
    print(f"  Montreux Noël             : {n_montreux_noel} occurrences")

    if n_montreux_noel > 0:
        print("\n  Détail Montreux Noël par année :")
        vn = events[events["is_montreux_noel"]][["annee_pdf", "nom", "date_debut", "date_fin"]]
        for _, row in vn.iterrows():
            print(f"    {row.annee_pdf} : {row.nom!r} ({row.date_debut.date()} → {row.date_fin.date()})")

    if unknown_lieux:
        print(f"\n[WARNING] {len(unknown_lieux)} lieu(x) non reconnu(s) — à ajouter dans LIEU_TO_ZONE_NORMALIZED :")
        for lieu in sorted(set(unknown_lieux)):
            print(f"  - {repr(lieu)}")

    print("\nPar PDF source :")
    for annee, grp in events.groupby("annee_pdf"):
        print(f"  {annee} : {len(grp):,} événements")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    pdf_paths = sorted(EVENTS_DIR.glob("Manifestations *.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(
            f"Aucun PDF de manifestations trouvé dans {EVENTS_DIR}\n"
            "Vérifier que les fichiers 'Manifestations YYYY.pdf' sont présents."
        )

    all_events: list[dict] = []
    for path in pdf_paths:
        annee_pdf, events = parse_pdf(path)
        if annee_pdf == 0:
            print(f"  Ignoré (année non détectable) : {path.name}")
            continue
        print(f"  {path.name} : {len(events)} événements retenus")
        all_events.extend(events)

    events_df = (
        pd.DataFrame(all_events)
        .sort_values(["date_debut", "nom"])
        .reset_index(drop=True)
    )

    # Classification géographique (zone) et localité R35
    events_df["zone_r35"]     = events_df["lieu"].apply(classify_lieu)
    events_df["localite_r35"] = events_df["lieu"].apply(classify_localite_r35)

    # Lieux inconnus — WARNING
    unknown_mask  = events_df["zone_r35"] == "inconnue"
    unknown_lieux = events_df.loc[unknown_mask & events_df["lieu"].notna(), "lieu"].tolist()
    if unknown_lieux:
        warnings.warn(
            f"{len(unknown_lieux)} événement(s) avec lieu non reconnu dans LIEU_TO_ZONE_NORMALIZED. "
            f"Exemples : {sorted(set(unknown_lieux))[:10]}",
            stacklevel=2,
        )

    # Événements signature
    flags = events_df["nom"].apply(flag_signature_events)
    events_df["is_montreux_jazz"]        = [x[0] for x in flags]
    events_df["is_marche_noel"]          = [x[1] for x in flags]
    montreux_noel_candidat                  = [x[2] for x in flags]

    # Garde-fou Montreux Noël : pattern match + zone Montreux obligatoire.
    # Montreux est désormais classé zone_indirecte (connectivité ferroviaire R35).
    # Le garde-fou accepte zone_indirecte et hors_zone pour tolérer un éventuel
    # reclassement futur, tout en bloquant les faux positifs en zone_directe.
    candidat_series       = pd.Series(montreux_noel_candidat, index=events_df.index)
    montreux_noel_zone_ok = events_df["zone_r35"].isin(["zone_indirecte", "hors_zone"])
    events_df["is_montreux_noel"] = (candidat_series & montreux_noel_zone_ok)

    # WARNING si le pattern a matché en zone_directe (improbable — serait un faux positif)
    faux_pos_mask = candidat_series & ~montreux_noel_zone_ok
    if faux_pos_mask.any():
        faux_positifs = events_df.loc[faux_pos_mask, "nom"].tolist()
        warnings.warn(
            f"is_montreux_noel : {len(faux_positifs)} faux positif(s) — pattern matché en zone_directe. "
            f"Noms : {faux_positifs[:5]}",
            stacklevel=2,
        )

    # Ordre des colonnes catalogue événements
    events_df = events_df[
        [
            "annee_pdf", "nom", "date_debut", "date_fin", "lieu",
            "nombre_jours", "zone_r35", "localite_r35",
            "is_montreux_jazz", "is_marche_noel", "is_montreux_noel",
            "source_pdf",
        ]
    ]

    date_dim = build_date_dimension(events_df)
    validate(events_df, date_dim)

    DIM_DIR.mkdir(parents=True, exist_ok=True)

    events_df.to_parquet(OUTPUT_EVENEMENTS, index=False)
    events_df.to_csv(OUTPUT_EVENEMENTS.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    print(f"\n  parquet événements : {OUTPUT_EVENEMENTS}  ({len(events_df):,} lignes)")

    date_dim.to_parquet(OUTPUT_DATES, index=False)
    date_dim.to_csv(OUTPUT_DATES.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    print(f"  parquet dates      : {OUTPUT_DATES}  ({len(date_dim):,} lignes)")

    print_summary(events_df, date_dim, unknown_lieux)


if __name__ == "__main__":
    main()
