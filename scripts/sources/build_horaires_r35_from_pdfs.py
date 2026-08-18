"""
Construit une table horaire R35 exploitable pour auditer les comptages APC.

Le grain principal de sortie est:
  annee_horaire + date + numero_train + gare_depart + gare_arrivee + depart + arrivee

Sorties:
  - data/intermediate/horaires_r35_arrets_officiels.parquet
  - data/intermediate/horaires_r35_arrets_officiels.csv
  - data/intermediate/horaires_r35_troncons_template.parquet
  - data/intermediate/horaires_r35_troncons_template.csv
  - data/intermediate/horaires_r35_troncons_jour.parquet
  - data/intermediate/horaires_r35_troncons_jour.csv

Important:
  Les PDF ne stockent pas tous les signes de circulation comme du texte: les
  renvois numerotes sont souvent de petits rectangles noirs. Le script extrait
  donc a la fois les mots et ces objets graphiques pour construire un calendrier
  de circulation explicite avant de developper les troncons par jour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd
import pdfplumber

try:
    import pypdfium2 as pdfium
    from PIL import ImageChops
except ImportError:  # pragma: no cover - fallback documented in audit columns
    pdfium = None
    ImageChops = None


PROJECT_ROOT    = Path(__file__).resolve().parents[2]
SCHEDULE_DIR    = PROJECT_ROOT / "data" / "external" / "horaires_r35"
DIM_GARE_PATH   = PROJECT_ROOT / "data" / "dimension" / "dim_gare.parquet"
ANNEES_HORAIRES_PATH = PROJECT_ROOT / "data" / "dimension" / "annees_horaires.csv"

# Artefacts intermédiaires — data/intermediate/
_INTERMEDIATE   = PROJECT_ROOT / "data" / "intermediate"
OUTPUT_STOPS_PATH            = _INTERMEDIATE / "horaires_r35_arrets_officiels.parquet"
OUTPUT_TEMPLATE_PATH         = _INTERMEDIATE / "horaires_r35_troncons_template.parquet"
OUTPUT_COURSE_CALENDAR_PATH  = _INTERMEDIATE / "horaires_r35_calendrier_circulation.parquet"
OUTPUT_SERVICE_NOTES_PATH    = _INTERMEDIATE / "horaires_r35_notes_circulation_pdf.parquet"
OUTPUT_STOPS_CSV_PATH        = _INTERMEDIATE / "horaires_r35_arrets_officiels.csv"
OUTPUT_TEMPLATE_CSV_PATH     = _INTERMEDIATE / "horaires_r35_troncons_template.csv"
OUTPUT_COURSE_CALENDAR_CSV_PATH = _INTERMEDIATE / "horaires_r35_calendrier_circulation.csv"
OUTPUT_SERVICE_NOTES_CSV_PATH   = _INTERMEDIATE / "horaires_r35_notes_circulation_pdf.csv"
OUTPUT_AUDIT_PATH            = _INTERMEDIATE / "horaires_r35_extraction_audit.csv"

# Table propre finale — data/processed/sources/
_SOURCES        = PROJECT_ROOT / "data" / "processed" / "sources"
OUTPUT_DAILY_PATH     = _SOURCES / "horaires_clean.parquet"
OUTPUT_DAILY_CSV_PATH = _SOURCES / "horaires_clean.csv"

TRAIN_MIN = 1300
TRAIN_MAX = 1599

DAY_TYPE_BY_WEEKDAY = {
    0: "Lu",
    1: "Ma",
    2: "Me",
    3: "Je",
    4: "Ve",
    5: "Sa",
    6: "Di",
}

WEEKDAY_CODES = {1, 2, 3, 4, 5}
WEEKEND_CODES = {6, 7}
ALL_WEEKDAY_CODES = {1, 2, 3, 4, 5, 6, 7}

LEGACY_SERVICE_SYMBOLS = {
    "A": "A",
    "C": "C",
    "R": "A",
    "T": "Sa",
    "U": "Di",
}

NOTE_REF_SCORE_MAX = 65.0


@dataclass(frozen=True)
class StationMapper:
    station_lookup: dict[str, str]
    manual_aliases: dict[str, str]
    prefixes: list[str]


@dataclass(frozen=True)
class NoteTemplate:
    note_id: str
    image: object


@dataclass
class PdfNoteIndex:
    note_rects_by_page: dict[int, list[dict]]
    service_notes: pd.DataFrame
    status: str


def non_missing_mask(values: pd.Series) -> pd.Series:
    strings = values.astype("string").str.strip()
    return strings.notna() & strings.ne("")


def parse_date_column(values: pd.Series, column: str, date_format: str) -> pd.Series:
    strings = values.astype("string").str.strip()
    strings = strings.mask(strings.eq(""), pd.NA)
    parsed = pd.to_datetime(strings, format=date_format, errors="coerce")

    invalid_mask = non_missing_mask(values) & parsed.isna()
    if invalid_mask.any():
        examples = values.loc[invalid_mask].drop_duplicates().head(5).tolist()
        raise ValueError(f"Valeurs invalides dans {column}: {examples}")

    return parsed


def load_annees_horaires(path: Path = ANNEES_HORAIRES_PATH) -> pd.DataFrame:
    annees = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype="string")
    required_columns = {"Annee", "Debut", "Fin"}
    missing_columns = sorted(required_columns - set(annees.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans {path}: {missing_columns}")

    annees = annees[["Annee", "Debut", "Fin"]].rename(
        columns={
            "Annee": "annee_horaire",
            "Debut": "debut_annee_horaire",
            "Fin": "fin_annee_horaire",
        }
    )
    annees["annee_horaire"] = annees["annee_horaire"].astype("string").str.strip()
    annees = annees.loc[annees["annee_horaire"].notna() & annees["annee_horaire"].ne("")].copy()
    annees["debut_annee_horaire"] = parse_date_column(
        annees["debut_annee_horaire"],
        "debut_annee_horaire",
        "%d.%m.%Y",
    )
    annees["fin_annee_horaire"] = parse_date_column(
        annees["fin_annee_horaire"],
        "fin_annee_horaire",
        "%d.%m.%Y",
    )
    return annees.loc[
        annees["debut_annee_horaire"].notna() & annees["fin_annee_horaire"].notna()
    ].copy()


def normalize_key(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_cell(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def pipe_join(values) -> str:
    cleaned = sorted({str(value).strip() for value in values if str(value).strip()})
    return "|".join(cleaned)


def split_pipe(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [item for item in str(value).split("|") if item]


def normalize_note_text(value) -> str:
    text = clean_cell(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("−", "–").replace("-", "–")
    text = re.sub(r"\s+\d+\s*/\s*\d+\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def small_note_rects(page) -> list[dict]:
    rects = []
    for rect in page.rects:
        color = rect.get("non_stroking_color")
        if not isinstance(color, tuple) or len(color) < 3:
            continue
        if max(color[:3]) >= 0.82:
            continue
        if not (4 <= rect["width"] <= 10 and 4 <= rect["height"] <= 9):
            continue
        rects.append(dict(rect))
    return rects


def crop_rect_image(page_image, rect: dict, scale: int = 6, pad: float = 0.8):
    left = int((rect["x0"] - pad) * scale)
    top = int((rect["top"] - pad) * scale)
    right = int((rect["x1"] + pad) * scale)
    bottom = int((rect["bottom"] + pad) * scale)
    return page_image.crop((left, top, right, bottom)).convert("L").resize((80, 80))


def image_diff(left, right) -> float:
    if ImageChops is None:
        return float("inf")
    return float(np.asarray(ImageChops.difference(left, right), dtype=np.int16).mean())


def render_pdf_page(pdf_path: Path, page_index: int, scale: int = 6):
    if pdfium is None:
        return None
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return pdf[page_index].render(scale=scale).to_pil()
    finally:
        pdf.close()


def cluster_x_positions(rects: list[dict], tolerance: float = 8.0) -> dict[int, int]:
    clusters: list[float] = []
    assignments: dict[int, int] = {}
    for index, rect in enumerate(sorted(rects, key=lambda item: item["x0"])):
        for cluster_index, cluster_x in enumerate(clusters):
            if abs(rect["x0"] - cluster_x) <= tolerance:
                assignments[id(rect)] = cluster_index
                clusters[cluster_index] = (cluster_x + rect["x0"]) / 2
                break
        else:
            assignments[id(rect)] = len(clusters)
            clusters.append(rect["x0"])
    return assignments


def find_explication_top(words: list[dict]) -> float | None:
    for word in words:
        if normalize_key(word["text"]) == "explication":
            same_line = [
                other["text"]
                for other in words
                if abs(other["top"] - word["top"]) < 3 and other["x0"] >= word["x0"]
            ]
            if "signes" in normalize_key(" ".join(same_line)):
                return float(word["top"])
    return None


def detect_legend_rects(page, words: list[dict], rects: list[dict]) -> list[dict]:
    if not rects:
        return []

    explication_top = find_explication_top(words)
    if explication_top is not None:
        note_start = explication_top + 20
        return [rect for rect in rects if rect["top"] >= note_start]

    footer_candidates = [
        rect
        for rect in rects
        if rect["x0"] < 90 and rect["top"] > page.height * 0.72
    ]
    if not footer_candidates:
        return []
    note_start = min(rect["top"] for rect in footer_candidates)
    return [rect for rect in rects if rect["top"] >= note_start - 1]


def sort_legend_rects(rects: list[dict]) -> list[dict]:
    if not rects:
        return []
    assignments = cluster_x_positions(rects)
    return sorted(rects, key=lambda rect: (assignments[id(rect)], rect["top"], rect["x0"]))


def extract_note_text_for_rect(page, words: list[dict], legend_rects: list[dict], rect: dict) -> str:
    same_column = [
        other
        for other in legend_rects
        if abs(other["x0"] - rect["x0"]) <= 8 and other["top"] > rect["top"] + 1
    ]
    next_top = min([other["top"] for other in same_column], default=page.height)
    next_top = min(next_top, rect["top"] + 65)

    right_columns = sorted({other["x0"] for other in legend_rects if other["x0"] > rect["x0"] + 8})
    right_bound = right_columns[0] - 4 if right_columns else page.width - 20

    selected = [
        word
        for word in words
        if rect["top"] - 3 <= word["top"] < next_top - 2
        and word["x0"] >= rect["x1"] + 2
        and word["x0"] < right_bound
    ]
    selected = sorted(selected, key=lambda word: (word["top"], word["x0"]))
    text = normalize_note_text(" ".join(word["text"] for word in selected))
    for stop_phrase in [
        "Horaires dans le sens",
        "Heure de départ",
        "de départ sur demande",
        "Arrêt sur demande",
        "autocontrôle",
        "Train",
        "Regio",
        "Les fêtes générales",
        "Battement minimum",
        "Remarques",
    ]:
        if stop_phrase in text:
            text = text.split(stop_phrase, 1)[0]
    return normalize_note_text(text)


def match_note_template(rect: dict, page_image, templates: list[NoteTemplate], scale: int = 6) -> tuple[str, float]:
    if page_image is None or not templates:
        return "", float("inf")
    cropped = crop_rect_image(page_image, rect, scale=scale)
    scores = sorted((image_diff(cropped, template.image), template.note_id) for template in templates)
    score, note_id = scores[0]
    return note_id, score


def infer_note_id_from_note_text(note_text: str) -> str | None:
    text_norm = normalize_key(note_text)
    if "15 12" in text_norm and "13 12" in text_norm:
        return "22"
    if re.fullmatch(r"10 4 1 8", text_norm):
        return "23"
    return None


def build_pdf_note_index(pdf_path: Path, pdf) -> PdfNoteIndex:
    if pdfium is None or ImageChops is None:
        return PdfNoteIndex({}, pd.DataFrame(), "pypdfium2_ou_pillow_indisponible")

    page_infos = []
    for page_number, page in enumerate(pdf.pages, start=1):
        words = (
            page.extract_words(
                x_tolerance=1,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
            )
            or []
        )
        rects = small_note_rects(page)
        legend_rects = sort_legend_rects(detect_legend_rects(page, words, rects))
        page_infos.append(
            {
                "page_number": page_number,
                "page": page,
                "words": words,
                "rects": rects,
                "legend_rects": legend_rects,
            }
        )

    source_info = max(page_infos, key=lambda info: len(info["legend_rects"]), default=None)
    if source_info is None or not source_info["legend_rects"]:
        return PdfNoteIndex({}, pd.DataFrame(), "aucune_legende_note_detectee")

    scale = 6
    source_image = render_pdf_page(pdf_path, source_info["page_number"] - 1, scale=scale)
    if source_image is None:
        return PdfNoteIndex({}, pd.DataFrame(), "rendu_pdf_indisponible")

    templates = [
        NoteTemplate(str(note_id), crop_rect_image(source_image, rect, scale=scale))
        for note_id, rect in enumerate(source_info["legend_rects"], start=10)
    ]
    known_template_ids = {template.note_id for template in templates}
    for info in page_infos:
        if not info["legend_rects"]:
            continue
        page_image = render_pdf_page(pdf_path, info["page_number"] - 1, scale=scale)
        for rect in info["legend_rects"]:
            inferred_note_id = infer_note_id_from_note_text(
                extract_note_text_for_rect(
                    info["page"],
                    info["words"],
                    info["legend_rects"],
                    rect,
                )
            )
            if inferred_note_id and inferred_note_id not in known_template_ids and page_image is not None:
                templates.append(
                    NoteTemplate(inferred_note_id, crop_rect_image(page_image, rect, scale=scale))
                )
                known_template_ids.add(inferred_note_id)

    note_rows = []
    note_rects_by_page: dict[int, list[dict]] = {}
    for info in page_infos:
        page_image = render_pdf_page(pdf_path, info["page_number"] - 1, scale=scale)
        legend_ids: set[str] = set()

        for rect in info["legend_rects"]:
            note_id, score = match_note_template(rect, page_image, templates, scale=scale)
            if not note_id or score > NOTE_REF_SCORE_MAX:
                continue
            note_text = extract_note_text_for_rect(
                info["page"],
                info["words"],
                info["legend_rects"],
                rect,
            )
            note_id = infer_note_id_from_note_text(note_text) or note_id
            scoped_note_id = f"p{info['page_number']}:{note_id}"
            note_ids_to_write = [scoped_note_id]
            if info["page_number"] == source_info["page_number"]:
                note_ids_to_write.append(note_id)
            for note_id_to_write in note_ids_to_write:
                legend_ids.add(note_id_to_write)
                note_rows.append(
                    {
                        "pdf_file": pdf_path.name,
                        "annee_horaire": annee_horaire_from_pdf(pdf_path),
                        "page": info["page_number"],
                        "note_id": note_id_to_write,
                        "note_text": note_text,
                        "template_match_score": score,
                    }
                )

        page_note_rects = []
        for rect in info["rects"]:
            note_id, score = match_note_template(rect, page_image, templates, scale=scale)
            if not note_id or score > NOTE_REF_SCORE_MAX:
                continue
            if rect in info["legend_rects"]:
                continue
            scoped_note_id = f"p{info['page_number']}:{note_id}"
            if info["legend_rects"] and scoped_note_id in legend_ids:
                note_id = scoped_note_id
            page_note_rects.append(
                {
                    "x0": rect["x0"],
                    "x1": rect["x1"],
                    "top": rect["top"],
                    "bottom": rect["bottom"],
                    "note_id": note_id,
                    "template_match_score": score,
                }
            )
        note_rects_by_page[info["page_number"]] = page_note_rects

    notes = pd.DataFrame.from_records(note_rows)
    if not notes.empty:
        notes["note_text"] = notes["note_text"].map(normalize_note_text)
        notes = notes.sort_values(["pdf_file", "page", "note_id"]).drop_duplicates(
            ["pdf_file", "page", "note_id", "note_text"]
        )
    return PdfNoteIndex(note_rects_by_page, notes, "ok")


def clean_station_name(value) -> str:
    text = clean_cell(value)
    text = re.sub(r"^\s*[0-9]+[’'`´]*\s*", "", text)
    text = re.sub(r"\b(arr|dep|dép)\.?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(K|Æ|Ä|R|T|U|S7)\b", "", text)
    text = text.replace("ô", "")
    return re.sub(r"\s+", " ", text).strip(" -")


def load_station_mapper(dim_gare: pd.DataFrame) -> StationMapper:
    station_lookup: dict[str, str] = {}
    for _, row in dim_gare.iterrows():
        station_lookup[normalize_key(row["nom"])] = row["abreviation"]
        station_lookup[normalize_key(row["abreviation"])] = row["abreviation"]

    manual_aliases = {
        "vevey vignerons": "VVVI",
        "vevey vigneron": "VVVI",
        "clies": "CLIE",
        "clies gare": "CLIE",
        "hauteville gare": "HTV",
        "ondallaz l alliaz": "OND",
        "ondallaz alliaz": "OND",
        "prelaz sur blonay": "PRLZ",
        "les pleiades": "PLEI",
        "bois de chexbres": "BCHX",
        "st legier gare": "STLE",
        "st legier village": "STLV",
        "chateau d hauteville": "CHTV",
        "chateau de blonay": "CHBL",
    }
    prefixes = sorted(set(station_lookup) | set(manual_aliases), key=len, reverse=True)
    return StationMapper(station_lookup=station_lookup, manual_aliases=manual_aliases, prefixes=prefixes)


def station_to_abbreviation(station_pdf, mapper: StationMapper):
    key = normalize_key(station_pdf)
    if key in mapper.manual_aliases:
        return mapper.manual_aliases[key]
    if key in mapper.station_lookup:
        return mapper.station_lookup[key]
    for prefix in mapper.prefixes:
        if key.startswith(prefix + " "):
            return mapper.manual_aliases.get(prefix, mapper.station_lookup.get(prefix, pd.NA))
    return pd.NA


def annee_horaire_from_pdf(pdf_path: Path) -> str:
    match = re.search(r"(20\d{2})", pdf_path.stem)
    if not match:
        return pd.NA
    return f"H{int(match.group(1)) % 100:02d}"


def group_pdf_words_into_lines(words, y_tol=2.2):
    lines = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(lines[-1]["top"] - word["top"]) > y_tol:
            lines.append({"top": word["top"], "words": [word]})
        else:
            n_words = len(lines[-1]["words"])
            lines[-1]["words"].append(word)
            lines[-1]["top"] = (lines[-1]["top"] * n_words + word["top"]) / (n_words + 1)

    for line in lines:
        line["words"] = sorted(line["words"], key=lambda item: item["x0"])
        line["text"] = " ".join(word["text"] for word in line["words"])
    return lines


def digits_from_time_token(text: str) -> str | None:
    token = str(text).strip()
    if not token:
        return None

    compact_match = re.search(r"([0-2]?\d[0-5]\d)$", re.sub(r"[^0-9]", "", token))
    if not compact_match:
        return None

    digits = compact_match.group(1)
    if len(digits) == 3:
        hour = int(digits[0])
        minute = int(digits[1:])
    elif len(digits) == 4:
        hour = int(digits[:2])
        minute = int(digits[2:])
    else:
        return None

    if hour > 29 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}:00"


def service_symbols_from_token(text: str) -> list[str]:
    token = str(text).strip()
    if not token:
        return []
    compact = re.sub(r"[0-9\s:.'’`´,+\"-]", "", token)
    symbols = []
    for char in compact:
        mapped = LEGACY_SERVICE_SYMBOLS.get(char)
        if mapped and mapped not in symbols:
            symbols.append(mapped)
    return symbols


def service_note_refs_near_point(point: dict, note_rects: list[dict]) -> list[str]:
    refs = []
    for rect in note_rects:
        if abs(rect["top"] - point["top"]) > 5:
            continue
        if -2 <= rect["x0"] - point["x1"] <= 12:
            refs.append(str(rect["note_id"]))
    return sorted(set(refs))


def previous_word_service_symbols(words: list[dict], index: int) -> list[str]:
    if index <= 0:
        return []
    previous = words[index - 1]
    current = words[index]
    if not (0 <= current["x0"] - previous["x1"] <= 7):
        return []
    return service_symbols_from_token(previous["text"])


def extract_time_points_from_line(words, note_rects: list[dict] | None = None):
    note_rects = note_rects or []
    points = []
    consumed_indexes: set[int] = set()

    i = 0
    while i < len(words) - 1:
        hour_word = words[i]
        minute_word = words[i + 1]
        if (
            re.fullmatch(r"\d{1,2}", hour_word["text"])
            and re.fullmatch(r"\d{2}", minute_word["text"])
            and 0 <= minute_word["x0"] - hour_word["x1"] <= 8
        ):
            hour = int(hour_word["text"])
            minute = int(minute_word["text"])
            if hour <= 29 and minute <= 59:
                point = {
                    "x0": hour_word["x0"],
                    "x1": minute_word["x1"],
                    "top": hour_word["top"],
                    "heure": f"{hour:02d}:{minute:02d}:00",
                    "service_symbols": previous_word_service_symbols(words, i),
                    "service_note_refs": [],
                    "time_raw": hour_word["text"] + " " + minute_word["text"],
                }
                point["service_note_refs"] = service_note_refs_near_point(point, note_rects)
                points.append(point)
                consumed_indexes.update({i, i + 1})
                i += 2
                continue
        i += 1

    for index, word in enumerate(words):
        if index in consumed_indexes:
            continue
        heure = digits_from_time_token(word["text"])
        if heure is not None:
            symbols = service_symbols_from_token(word["text"])
            if not symbols:
                symbols = previous_word_service_symbols(words, index)
            point = {
                "x0": word["x0"],
                "x1": word["x1"],
                "top": word["top"],
                "heure": heure,
                "service_symbols": symbols,
                "service_note_refs": [],
                "time_raw": word["text"],
            }
            point["service_note_refs"] = service_note_refs_near_point(point, note_rects)
            points.append(point)

    points = sorted(points, key=lambda item: item["x0"])
    deduplicated = []
    for point in points:
        if deduplicated and abs(deduplicated[-1]["x0"] - point["x0"]) < 1:
            continue
        deduplicated.append(point)
    return deduplicated


def extract_train_candidates_from_line(words):
    candidates = []
    for word in words:
        digits = re.sub(r"[^0-9]", "", word["text"])
        if len(digits) != 4:
            continue
        numero_train = int(digits)
        if TRAIN_MIN <= numero_train <= TRAIN_MAX:
            candidates.append(
                {
                    "numero_train": numero_train,
                    "x0": word["x0"],
                    "xcenter": (word["x0"] + word["x1"]) / 2,
                    "header_raw": word["text"],
                }
            )
    return candidates


def line_station_prefix(line, mapper: StationMapper):
    time_points = extract_time_points_from_line(line["words"])
    if not time_points:
        return pd.NA, ""
    first_time_x0 = min(point["x0"] for point in time_points)
    station_text = clean_station_name(
        " ".join(word["text"] for word in line["words"] if word["x1"] < first_time_x0 - 3)
    )
    return station_to_abbreviation(station_text, mapper), station_text


def parse_pdf_page(
    page,
    pdf_path: Path,
    page_number: int,
    mapper: StationMapper,
    note_rects: list[dict] | None = None,
):
    words = (
        page.extract_words(
            x_tolerance=1,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
        )
        or []
    )
    lines = group_pdf_words_into_lines(words)
    records = []
    section_id = -1
    train_columns = []

    for row_index, line in enumerate(lines):
        station_abbr, station_text = line_station_prefix(line, mapper)
        train_candidates = extract_train_candidates_from_line(line["words"])

        if len(train_candidates) >= 2 and pd.isna(station_abbr):
            section_id += 1
            train_columns = [
                {**candidate, "column_index": column_index}
                for column_index, candidate in enumerate(train_candidates)
            ]
            continue

        if not train_columns or pd.isna(station_abbr):
            continue

        time_points = extract_time_points_from_line(line["words"], note_rects)
        for point in time_points:
            closest_column = min(train_columns, key=lambda column: abs(column["x0"] - point["x0"]))
            if abs(closest_column["x0"] - point["x0"]) > 24:
                continue
            records.append(
                {
                    "annee_horaire": annee_horaire_from_pdf(pdf_path),
                    "pdf_file": pdf_path.name,
                    "page": page_number,
                    "section_id": section_id,
                    "row_index": row_index,
                    "column_index": closest_column["column_index"],
                    "numero_train": int(closest_column["numero_train"]),
                    "station_pdf": station_text,
                    "gare": station_abbr,
                    "heure": point["heure"],
                    "time_raw": point.get("time_raw", ""),
                    "service_symbols_raw": pipe_join(point.get("service_symbols", [])),
                    "service_note_refs": pipe_join(point.get("service_note_refs", [])),
                    "header_raw": closest_column["header_raw"],
                }
            )
    return records


def extract_schedule_stops(schedule_dir: Path, dim_gare: pd.DataFrame):
    mapper = load_station_mapper(dim_gare)
    records = []
    audit_rows = []
    note_frames = []
    for pdf_path in sorted(schedule_dir.glob("112_*.pdf")):
        pdf_records = []
        note_index = PdfNoteIndex({}, pd.DataFrame(), "non_initialise")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                note_index = build_pdf_note_index(pdf_path, pdf)
                for page_number, page in enumerate(pdf.pages, start=1):
                    pdf_records.extend(
                        parse_pdf_page(
                            page,
                            pdf_path,
                            page_number,
                            mapper,
                            note_index.note_rects_by_page.get(page_number, []),
                        )
                    )
                pages = len(pdf.pages)
        except Exception as exc:
            pages = pd.NA
            audit_rows.append(
                {
                    "pdf_file": pdf_path.name,
                    "annee_horaire": annee_horaire_from_pdf(pdf_path),
                    "pages": pages,
                    "arrets_extraits": 0,
                    "trains_extraits": 0,
                    "notes_circulation_extraites": 0,
                    "note_index_status": f"erreur: {note_index.status}",
                    "status": f"erreur: {exc}",
                }
            )
            continue

        records.extend(pdf_records)
        if not note_index.service_notes.empty:
            note_frames.append(note_index.service_notes)
        audit_rows.append(
            {
                "pdf_file": pdf_path.name,
                "annee_horaire": annee_horaire_from_pdf(pdf_path),
                "pages": pages,
                "arrets_extraits": len(pdf_records),
                "trains_extraits": len({record["numero_train"] for record in pdf_records}),
                "notes_circulation_extraites": 0
                if note_index.service_notes.empty
                else len(note_index.service_notes),
                "note_index_status": note_index.status,
                "status": "ok" if pdf_records else "aucun_arret_extrait",
            }
        )

    stops = pd.DataFrame.from_records(records)
    audit = pd.DataFrame.from_records(audit_rows)
    service_notes = pd.concat(note_frames, ignore_index=True) if note_frames else pd.DataFrame()
    if stops.empty:
        return stops, audit, service_notes

    dim = dim_gare[["abreviation", "ordre"]].rename(columns={"abreviation": "gare", "ordre": "gare_ordre"})
    stops = stops.merge(dim, on="gare", how="left")
    stops = stops.dropna(subset=["gare", "gare_ordre"]).copy()
    stops["horaire_course_id"] = (
        stops["annee_horaire"].astype(str)
        + "|"
        + stops["pdf_file"].astype(str)
        + "|p"
        + stops["page"].astype(str)
        + "|s"
        + stops["section_id"].astype(str)
        + "|c"
        + stops["column_index"].astype(str)
        + "|"
        + stops["numero_train"].astype(str)
    )
    stops = stops.sort_values(
        ["annee_horaire", "pdf_file", "page", "section_id", "column_index", "row_index"]
    )
    stops["sequence_arret"] = stops.groupby("horaire_course_id").cumcount()
    return stops.reset_index(drop=True), audit, service_notes


def time_to_minutes(time_value) -> int:
    if hasattr(time_value, "hour") and hasattr(time_value, "minute"):
        return int(time_value.hour) * 60 + int(time_value.minute)
    hour, minute, *_ = str(time_value).split(":")
    return int(hour) * 60 + int(minute)


def to_time_object(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%H:%M:%S", errors="coerce").dt.time


def collapse_consecutive_station_blocks(group: pd.DataFrame) -> pd.DataFrame:
    horaire_course_id = group.name
    rows = group.sort_values("sequence_arret").to_dict("records")
    blocks = []
    for row in rows:
        if blocks and blocks[-1]["gare"] == row["gare"]:
            blocks[-1]["depart"] = row["heure"]
            blocks[-1]["last_sequence_arret"] = row["sequence_arret"]
            blocks[-1]["station_pdf_last"] = row["station_pdf"]
        else:
            blocks.append(
                {
                    "horaire_course_id": horaire_course_id,
                    "annee_horaire": row["annee_horaire"],
                    "pdf_file": row["pdf_file"],
                    "page": row["page"],
                    "section_id": row["section_id"],
                    "column_index": row["column_index"],
                    "numero_train": row["numero_train"],
                    "gare": row["gare"],
                    "gare_ordre": row["gare_ordre"],
                    "arrivee": row["heure"],
                    "depart": row["heure"],
                    "first_sequence_arret": row["sequence_arret"],
                    "last_sequence_arret": row["sequence_arret"],
                    "station_pdf_first": row["station_pdf"],
                    "station_pdf_last": row["station_pdf"],
                }
            )
    return pd.DataFrame(blocks)


def build_course_service_markers(stops: pd.DataFrame) -> pd.DataFrame:
    if stops.empty:
        return pd.DataFrame(columns=["horaire_course_id", "service_note_refs", "service_symbols_raw"])

    rows = []
    for horaire_course_id, group in stops.groupby("horaire_course_id"):
        note_refs = []
        symbols = []
        for value in group.get("service_note_refs", pd.Series(dtype="string")).dropna():
            note_refs.extend(split_pipe(value))
        for value in group.get("service_symbols_raw", pd.Series(dtype="string")).dropna():
            symbols.extend(split_pipe(value))
        rows.append(
            {
                "horaire_course_id": horaire_course_id,
                "service_note_refs": pipe_join(note_refs),
                "service_symbols_raw": pipe_join(symbols),
            }
        )
    return pd.DataFrame.from_records(rows)


def build_segment_templates(stops: pd.DataFrame, dim_gare: pd.DataFrame) -> pd.DataFrame:
    if stops.empty:
        return pd.DataFrame()

    collapsed = (
        stops.groupby("horaire_course_id", group_keys=False)
        .apply(collapse_consecutive_station_blocks, include_groups=False)
        .reset_index(drop=True)
    )
    collapsed["next_gare"] = collapsed.groupby("horaire_course_id")["gare"].shift(-1)
    collapsed["next_gare_ordre"] = collapsed.groupby("horaire_course_id")["gare_ordre"].shift(-1)
    collapsed["next_arrivee"] = collapsed.groupby("horaire_course_id")["arrivee"].shift(-1)
    collapsed["next_station_pdf_first"] = collapsed.groupby("horaire_course_id")["station_pdf_first"].shift(-1)

    segments = collapsed.dropna(subset=["next_gare"]).copy()
    segments = segments.loc[segments["gare"].ne(segments["next_gare"])].copy()
    segments = segments.drop(columns=["arrivee"], errors="ignore")
    segments = segments.rename(
        columns={
            "gare": "gare_depart",
            "next_gare": "gare_arrivee",
            "gare_ordre": "gare_depart_ordre",
            "next_gare_ordre": "gare_arrivee_ordre",
            "depart": "depart",
            "next_arrivee": "arrivee",
            "station_pdf_last": "station_depart_pdf",
            "next_station_pdf_first": "station_arrivee_pdf",
        }
    )
    segments["sequence_troncon"] = segments.groupby("horaire_course_id").cumcount()
    segments["sens"] = np.where(
        segments["gare_arrivee_ordre"].gt(segments["gare_depart_ordre"]),
        "VV -> PLEI",
        "PLEI -> VV",
    )
    course_markers = build_course_service_markers(stops)
    segments = segments.merge(course_markers, on="horaire_course_id", how="left")
    segments["service_note_refs"] = segments["service_note_refs"].fillna("")
    segments["service_symbols_raw"] = segments["service_symbols_raw"].fillna("")
    segments["service_validity"] = np.where(
        segments["service_note_refs"].ne("") | segments["service_symbols_raw"].ne(""),
        "interprete_depuis_signes_pdf",
        "tous_les_jours_sans_signe_pdf_detecte",
    )
    segments["source"] = "horaire_pdf"
    segments["source_file"] = segments["pdf_file"]

    segments = segments.drop(columns=["gare_depart_ordre", "gare_arrivee_ordre"], errors="ignore")
    segments = enrich_with_station_dimensions(segments, dim_gare)
    segments["distance_km"] = (segments["gare_arrivee_km"] - segments["gare_depart_km"]).abs()
    segments["troncon_km"] = segments.apply(build_troncon_key, axis=1)
    segments["horaire_segment_id"] = (
        segments["horaire_course_id"].astype(str) + "|seg" + segments["sequence_troncon"].astype(str)
    )

    template_columns = [
        "horaire_segment_id",
        "horaire_course_id",
        "annee_horaire",
        "source_file",
        "source",
        "numero_train",
        "sens",
        "gare_depart",
        "gare_arrivee",
        "depart",
        "arrivee",
        "sequence_troncon",
        "station_depart_pdf",
        "station_arrivee_pdf",
        "page",
        "section_id",
        "column_index",
        "service_validity",
        "service_note_refs",
        "service_symbols_raw",
        "distance_km",
        "troncon_km",
    ]
    station_columns = [column for column in segments.columns if column.startswith("gare_depart_")]
    station_columns += [column for column in segments.columns if column.startswith("gare_arrivee_")]
    template_columns += [column for column in station_columns if column not in template_columns]

    segments = segments[template_columns].drop_duplicates(
        subset=[
            "annee_horaire",
            "numero_train",
            "gare_depart",
            "gare_arrivee",
            "depart",
            "arrivee",
        ]
    )
    return segments.sort_values(
        ["annee_horaire", "numero_train", "depart", "sequence_troncon", "gare_depart_ordre"]
    ).reset_index(drop=True)


def enrich_with_station_dimensions(df: pd.DataFrame, dim_gare: pd.DataFrame) -> pd.DataFrame:
    station_dim = dim_gare.rename(
        columns={
            "abreviation": "gare",
            "commune": "locality_name",
        }
    )
    depart_dim = station_dim.add_prefix("gare_depart_").rename(columns={"gare_depart_gare": "gare_depart"})
    arrivee_dim = station_dim.add_prefix("gare_arrivee_").rename(columns={"gare_arrivee_gare": "gare_arrivee"})
    enriched = df.merge(depart_dim, on="gare_depart", how="left")
    enriched = enriched.merge(arrivee_dim, on="gare_arrivee", how="left")
    return enriched


def build_troncon_key(row: pd.Series) -> str:
    depart_order = row.get("gare_depart_ordre")
    arrivee_order = row.get("gare_arrivee_ordre")
    if pd.notna(depart_order) and pd.notna(arrivee_order):
        if depart_order <= arrivee_order:
            return f"{row['gare_depart']}-{row['gare_arrivee']}"
        return f"{row['gare_arrivee']}-{row['gare_depart']}"
    return f"{row['gare_depart']}-{row['gare_arrivee']}"


def easter_date(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def federal_fast_monday(year: int) -> date:
    first = date(year, 9, 1)
    first_sunday = first + timedelta(days=(6 - first.weekday()) % 7)
    federal_fast_sunday = first_sunday + timedelta(days=14)
    return federal_fast_sunday + timedelta(days=1)


def public_holidays_for_year(year: int) -> dict[date, str]:
    easter = easter_date(year)
    return {
        date(year, 1, 1): "Nouvel an",
        date(year, 1, 2): "Saint-Berchtold",
        easter - timedelta(days=2): "Vendredi saint",
        easter + timedelta(days=1): "Lundi de Paques",
        easter + timedelta(days=39): "Ascension",
        easter + timedelta(days=50): "Lundi de Pentecote",
        date(year, 8, 1): "Fete nationale",
        federal_fast_monday(year): "Lundi du Jeune federal",
        date(year, 12, 25): "Noel",
        date(year, 12, 26): "Saint-Etienne",
    }


def build_base_calendar(annees_horaires: pd.DataFrame, annee_filter=None) -> pd.DataFrame:
    calendar_rows = []
    for _, row in annees_horaires.iterrows():
        if annee_filter is not None and row["annee_horaire"] not in annee_filter:
            continue
        dates = pd.date_range(row["debut_annee_horaire"], row["fin_annee_horaire"], freq="D")
        calendar_rows.append(
            pd.DataFrame(
                {
                    "annee_horaire": row["annee_horaire"],
                    "date": dates,
                    "type_jour": [DAY_TYPE_BY_WEEKDAY[date.weekday()] for date in dates],
                    "jour_semaine_code": [date.weekday() + 1 for date in dates],
                    "debut_annee_horaire": row["debut_annee_horaire"],
                    "fin_annee_horaire": row["fin_annee_horaire"],
                }
            )
        )
    if not calendar_rows:
        return pd.DataFrame()
    calendar = pd.concat(calendar_rows, ignore_index=True)

    holidays = {}
    for year in sorted(set(calendar["date"].dt.year)):
        holidays.update(public_holidays_for_year(int(year)))
    calendar["holiday_name"] = calendar["date"].dt.date.map(holidays).fillna("")
    calendar["is_public_holiday"] = calendar["holiday_name"].ne("")
    calendar["is_weekend"] = calendar["jour_semaine_code"].isin(WEEKEND_CODES)
    return calendar


def day_month_to_date(day: int, month: int, start: pd.Timestamp, end: pd.Timestamp) -> pd.Timestamp | None:
    candidates = []
    for year in sorted({start.year, end.year, start.year + 1, end.year - 1}):
        try:
            candidate = pd.Timestamp(date(year, month, day))
        except ValueError:
            continue
        if start.normalize() <= candidate <= end.normalize():
            candidates.append(candidate)
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: abs((candidate - start).days))


def expand_date_range(
    start_day: int,
    start_month: int,
    end_day: int,
    end_month: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> set[pd.Timestamp]:
    start_date = day_month_to_date(start_day, start_month, start, end)
    end_date = day_month_to_date(end_day, end_month, start, end)
    if start_date is None or end_date is None:
        return set()
    if end_date < start_date:
        try:
            end_date = pd.Timestamp(date(start_date.year + 1, end_month, end_day))
        except ValueError:
            return set()
    return set(pd.date_range(start_date, end_date, freq="D"))


def explicit_dates_from_text(text: str, start: pd.Timestamp, end: pd.Timestamp) -> set[pd.Timestamp]:
    dates = set()
    for day, month in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.", text):
        parsed = day_month_to_date(int(day), int(month), start, end)
        if parsed is not None:
            dates.add(parsed.normalize())
    return dates


def date_ranges_from_text(text: str, start: pd.Timestamp, end: pd.Timestamp) -> set[pd.Timestamp]:
    ranges = set()
    for start_day, start_month, end_day, end_month in re.findall(
        r"\b(\d{1,2})\.(\d{1,2})\.\s*[–-]\s*(\d{1,2})\.(\d{1,2})\.",
        text,
    ):
        ranges.update(
            expand_date_range(
                int(start_day),
                int(start_month),
                int(end_day),
                int(end_month),
                start,
                end,
            )
        )
    return ranges


def remove_ranges_from_explicit_dates(text: str) -> str:
    return re.sub(r"\b\d{1,2}\.\d{1,2}\.\s*[–-]\s*\d{1,2}\.\d{1,2}\.", " ", text)


def infer_note_rule(note_id: str, note_text: str, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    note_label = str(note_id).rsplit(":", 1)[-1]
    text = normalize_note_text(note_text)
    text_norm = normalize_key(text)
    explicit_dates = explicit_dates_from_text(remove_ranges_from_explicit_dates(text), start, end)
    range_dates = date_ranges_from_text(text, start, end)

    base_kind = "all"
    weekdays: set[int] | None = None
    include_public_holidays = False
    exclude_public_holidays = False
    include_dates: set[pd.Timestamp] = set()
    exclude_dates: set[pd.Timestamp] = set()
    required_dates: set[pd.Timestamp] | None = None
    status = "parsed"

    if "nuit" in text_norm:
        base_kind = "night"
        if note_label in {"20", "21"}:
            weekdays = {6, 7}

    if "sauf" in text_norm and ("sauf 22 9" in text_norm or "sauf 21 9" in text_norm):
        base_kind = "A"
        weekdays = WEEKDAY_CODES
        exclude_public_holidays = True
        exclude_dates.update(explicit_dates)
    elif "ainsi que 22 9" in text_norm or "ainsi que 21 9" in text_norm:
        base_kind = "C"
        weekdays = WEEKEND_CODES
        include_public_holidays = True
        include_dates.update(explicit_dates)
    elif "ainsi que" in text_norm and "sauf" not in text_norm and "du " not in text_norm:
        if note_label == "17":
            weekdays = {5, 6}
        elif note_label in {"20", "21"}:
            weekdays = {6, 7}
        include_dates.update(explicit_dates)
    elif text_norm in {"", ""} or re.fullmatch(r"[–,\s/]*", text):
        if note_label == "10":
            weekdays = WEEKDAY_CODES
        elif note_label == "11":
            weekdays = WEEKEND_CODES
        elif note_label == "15":
            weekdays = {5, 6}
        elif note_label == "16":
            weekdays = {1, 2, 3, 4, 7}
        else:
            status = "unparsed_empty_note"
    elif "du " in text_norm and range_dates and "sauf" not in text_norm:
        required_dates = range_dates
        if note_label in {"15", "17", "20"}:
            weekdays = {1, 2, 3, 4, 7}
        elif note_label == "18" and "24 12" in text_norm:
            weekdays = {2, 3}
        elif note_label in {"16", "18", "21"}:
            weekdays = {5, 6}
        elif note_label == "22":
            weekdays = ALL_WEEKDAY_CODES
        else:
            weekdays = ALL_WEEKDAY_CODES
        include_dates.update(explicit_dates - range_dates)
    elif "sauf fetes generales" in text_norm:
        exclude_public_holidays = True
        if note_label in {"16", "18", "21", "22"}:
            weekdays = {5, 6}
        include_dates.update(range_dates)
        include_dates.update(explicit_dates)
    elif "sauf" in text_norm:
        exclude_dates.update(range_dates)
        exclude_dates.update(explicit_dates)
        if note_label in {"12", "13", "19"}:
            base_kind = "A"
            weekdays = WEEKDAY_CODES
            exclude_public_holidays = True
    elif explicit_dates or range_dates:
        required_dates = range_dates if range_dates else None
        include_dates.update(explicit_dates)
    else:
        status = "unparsed_text"

    return {
        "note_id": note_id,
        "note_text": text,
        "base_kind": base_kind,
        "weekdays": weekdays,
        "include_public_holidays": include_public_holidays,
        "exclude_public_holidays": exclude_public_holidays,
        "include_dates": include_dates,
        "exclude_dates": exclude_dates,
        "required_dates": required_dates,
        "parse_status": status,
    }


def infer_symbol_rule(symbol: str) -> dict:
    if symbol == "A":
        return {
            "base_kind": "A",
            "weekdays": WEEKDAY_CODES,
            "include_public_holidays": False,
            "exclude_public_holidays": True,
            "include_dates": set(),
            "exclude_dates": set(),
            "required_dates": None,
            "parse_status": "parsed_symbol_A",
        }
    if symbol == "C":
        return {
            "base_kind": "C",
            "weekdays": WEEKEND_CODES,
            "include_public_holidays": True,
            "exclude_public_holidays": False,
            "include_dates": set(),
            "exclude_dates": set(),
            "required_dates": None,
            "parse_status": "parsed_symbol_C",
        }
    if symbol == "Sa":
        weekdays = {6}
    elif symbol == "Di":
        weekdays = {7}
    else:
        weekdays = ALL_WEEKDAY_CODES
    return {
        "base_kind": symbol,
        "weekdays": weekdays,
        "include_public_holidays": False,
        "exclude_public_holidays": False,
        "include_dates": set(),
        "exclude_dates": set(),
        "required_dates": None,
        "parse_status": f"parsed_symbol_{symbol}",
    }


def evaluate_rule_on_calendar(rule: dict, calendar: pd.DataFrame) -> pd.Series:
    valid = pd.Series(True, index=calendar.index)
    weekdays = rule.get("weekdays")
    if weekdays is not None:
        valid &= calendar["jour_semaine_code"].isin(weekdays)
    if rule.get("required_dates") is not None:
        required_dates = {pd.Timestamp(value).normalize() for value in rule["required_dates"]}
        valid &= calendar["date"].dt.normalize().isin(required_dates)
    if rule.get("exclude_public_holidays"):
        valid &= ~calendar["is_public_holiday"]
    if rule.get("include_public_holidays"):
        valid |= calendar["is_public_holiday"]

    include_dates = {pd.Timestamp(value).normalize() for value in rule.get("include_dates", set())}
    exclude_dates = {pd.Timestamp(value).normalize() for value in rule.get("exclude_dates", set())}
    if include_dates:
        valid |= calendar["date"].dt.normalize().isin(include_dates)
    if exclude_dates:
        valid &= ~calendar["date"].dt.normalize().isin(exclude_dates)
    return valid


def prepare_service_note_rules(service_notes: pd.DataFrame, annees_horaires: pd.DataFrame) -> pd.DataFrame:
    if service_notes.empty:
        return pd.DataFrame()

    annees = annees_horaires.set_index("annee_horaire")
    rows = []
    collapsed = (
        service_notes.sort_values(["pdf_file", "page", "note_id"])
        .groupby(["pdf_file", "annee_horaire", "note_id"], as_index=False)
        .agg(note_text=("note_text", lambda values: pipe_join(values)))
    )
    for _, row in collapsed.iterrows():
        if row["annee_horaire"] not in annees.index:
            continue
        bounds = annees.loc[row["annee_horaire"]]
        rule = infer_note_rule(
            str(row["note_id"]),
            row["note_text"],
            bounds["debut_annee_horaire"],
            bounds["fin_annee_horaire"],
        )
        rows.append(
            {
                "pdf_file": row["pdf_file"],
                "annee_horaire": row["annee_horaire"],
                "note_id": str(row["note_id"]),
                "note_text": row["note_text"],
                "base_kind": rule["base_kind"],
                "weekdays": pipe_join(rule["weekdays"] or []),
                "include_public_holidays": rule["include_public_holidays"],
                "exclude_public_holidays": rule["exclude_public_holidays"],
                "include_dates": pipe_join(pd.Timestamp(value).strftime("%Y-%m-%d") for value in rule["include_dates"]),
                "exclude_dates": pipe_join(pd.Timestamp(value).strftime("%Y-%m-%d") for value in rule["exclude_dates"]),
                "required_dates": pipe_join(pd.Timestamp(value).strftime("%Y-%m-%d") for value in (rule["required_dates"] or [])),
                "parse_status": rule["parse_status"],
            }
        )
    return pd.DataFrame.from_records(rows)


def build_course_calendar(
    templates: pd.DataFrame,
    annees_horaires: pd.DataFrame,
    service_notes: pd.DataFrame,
) -> pd.DataFrame:
    if templates.empty:
        return pd.DataFrame()

    calendar = build_base_calendar(
        annees_horaires,
        annee_filter=set(templates["annee_horaire"].dropna().unique()),
    )
    notes_by_key = {}
    if not service_notes.empty:
        collapsed = (
            service_notes.sort_values(["pdf_file", "page", "note_id"])
            .groupby(["pdf_file", "annee_horaire", "note_id"], as_index=False)
            .agg(note_text=("note_text", lambda values: pipe_join(values)))
        )
        bounds = annees_horaires.set_index("annee_horaire")
        for _, row in collapsed.iterrows():
            if row["annee_horaire"] not in bounds.index:
                continue
            period = bounds.loc[row["annee_horaire"]]
            notes_by_key[(row["pdf_file"], row["annee_horaire"], str(row["note_id"]))] = infer_note_rule(
                str(row["note_id"]),
                row["note_text"],
                period["debut_annee_horaire"],
                period["fin_annee_horaire"],
            )

    course_rows = templates[
        [
            "horaire_course_id",
            "annee_horaire",
            "source_file",
            "numero_train",
            "sens",
            "service_note_refs",
            "service_symbols_raw",
        ]
    ].drop_duplicates()

    valid_frames = []
    for _, course in course_rows.iterrows():
        course_calendar = calendar.loc[calendar["annee_horaire"].eq(course["annee_horaire"])].copy()
        rule_masks = []
        rule_labels = []
        parse_statuses = []

        for note_id in split_pipe(course["service_note_refs"]):
            rule = notes_by_key.get((course["source_file"], course["annee_horaire"], note_id))
            if rule is None:
                parse_statuses.append(f"missing_note_{note_id}")
                continue
            rule_masks.append(evaluate_rule_on_calendar(rule, course_calendar))
            rule_labels.append(f"note_{note_id}:{rule['base_kind']}")
            parse_statuses.append(rule["parse_status"])

        for symbol in split_pipe(course["service_symbols_raw"]):
            rule = infer_symbol_rule(symbol)
            rule_masks.append(evaluate_rule_on_calendar(rule, course_calendar))
            rule_labels.append(f"symbol_{symbol}:{rule['base_kind']}")
            parse_statuses.append(rule["parse_status"])

        if rule_masks:
            valid = rule_masks[0].copy()
            for mask in rule_masks[1:]:
                valid &= mask
        else:
            valid = pd.Series(True, index=course_calendar.index)
            rule_labels.append("all_days_no_marker")
            parse_statuses.append("parsed_no_marker")

        course_calendar = course_calendar.loc[valid].copy()
        if course_calendar.empty:
            continue
        course_calendar["horaire_course_id"] = course["horaire_course_id"]
        course_calendar["source_file"] = course["source_file"]
        course_calendar["numero_train"] = course["numero_train"]
        course_calendar["sens"] = course["sens"]
        course_calendar["service_note_refs"] = course["service_note_refs"]
        course_calendar["service_symbols_raw"] = course["service_symbols_raw"]
        course_calendar["service_validity_rule"] = pipe_join(rule_labels)
        course_calendar["service_validity_parse_status"] = pipe_join(parse_statuses)
        valid_frames.append(course_calendar)

    if not valid_frames:
        return pd.DataFrame()
    return pd.concat(valid_frames, ignore_index=True)


def expand_templates_by_day(
    templates: pd.DataFrame,
    annees_horaires: pd.DataFrame,
    service_notes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    course_calendar = build_course_calendar(templates, annees_horaires, service_notes)
    if course_calendar.empty:
        return pd.DataFrame(), course_calendar

    daily = course_calendar.merge(
        templates,
        on=["horaire_course_id", "annee_horaire", "source_file", "numero_train", "sens"],
        how="inner",
        suffixes=("", "_template"),
    )
    for column in ["service_note_refs", "service_symbols_raw"]:
        template_column = f"{column}_template"
        if template_column in daily.columns:
            daily[column] = daily[column].fillna(daily[template_column])
            daily = daily.drop(columns=[template_column])
    daily["depart_minutes"] = daily["depart"].map(time_to_minutes)
    daily["arrivee_minutes"] = daily["arrivee"].map(time_to_minutes)
    daily["arrivee_day_offset"] = np.where(daily["arrivee_minutes"] < daily["depart_minutes"], 1, 0)
    daily["depart_datetime"] = daily["date"] + pd.to_timedelta(daily["depart_minutes"], unit="m")
    daily["arrivee_datetime"] = (
        daily["date"]
        + pd.to_timedelta(daily["arrivee_day_offset"], unit="D")
        + pd.to_timedelta(daily["arrivee_minutes"], unit="m")
    )
    daily = daily.drop(columns=["depart_minutes", "arrivee_minutes"])
    daily["depart"] = to_time_object(daily["depart"])
    daily["arrivee"] = to_time_object(daily["arrivee"])

    first_columns = [
        "source_file",
        "type_jour",
        "date",
        "annee_horaire",
        "numero_train",
        "sens",
        "gare_depart",
        "gare_arrivee",
        "depart",
        "arrivee",
        "depart_datetime",
        "arrivee_datetime",
        "arrivee_day_offset",
        "sequence_troncon",
        "horaire_segment_id",
        "horaire_course_id",
        "service_validity",
        "service_validity_rule",
        "service_validity_parse_status",
        "service_note_refs",
        "service_symbols_raw",
        "jour_semaine_code",
        "is_weekend",
        "is_public_holiday",
        "holiday_name",
        "source",
        "distance_km",
        "troncon_km",
    ]
    remaining_columns = [column for column in daily.columns if column not in first_columns]
    daily = daily[first_columns + remaining_columns].sort_values(
        ["annee_horaire", "date", "numero_train", "depart_datetime", "sequence_troncon"]
    ).reset_index(drop=True)
    return daily, course_calendar.sort_values(
        ["annee_horaire", "date", "numero_train", "horaire_course_id"]
    ).reset_index(drop=True)


def main() -> None:
    dim_gare = pd.read_parquet(DIM_GARE_PATH)
    annees_horaires = load_annees_horaires()

    stops, audit, service_notes = extract_schedule_stops(SCHEDULE_DIR, dim_gare)
    templates = build_segment_templates(stops, dim_gare)
    note_rules = prepare_service_note_rules(service_notes, annees_horaires)
    if not note_rules.empty:
        note_rule_columns = [column for column in note_rules.columns if column != "note_text"]
        service_notes = service_notes.merge(
            note_rules[note_rule_columns],
            on=["pdf_file", "annee_horaire", "note_id"],
            how="left",
        )
    daily, course_calendar = expand_templates_by_day(templates, annees_horaires, service_notes)
    templates = templates.copy()
    templates["depart"] = to_time_object(templates["depart"])
    templates["arrivee"] = to_time_object(templates["arrivee"])

    OUTPUT_STOPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    stops.to_parquet(OUTPUT_STOPS_PATH, index=False)
    templates.to_parquet(OUTPUT_TEMPLATE_PATH, index=False)
    service_notes.to_parquet(OUTPUT_SERVICE_NOTES_PATH, index=False)
    course_calendar.to_parquet(OUTPUT_COURSE_CALENDAR_PATH, index=False)
    daily.to_parquet(OUTPUT_DAILY_PATH, index=False)
    stops.to_csv(OUTPUT_STOPS_CSV_PATH, index=False, encoding="utf-8-sig")
    templates.to_csv(OUTPUT_TEMPLATE_CSV_PATH, index=False, encoding="utf-8-sig")
    service_notes.to_csv(OUTPUT_SERVICE_NOTES_CSV_PATH, index=False, encoding="utf-8-sig")
    course_calendar.to_csv(OUTPUT_COURSE_CALENDAR_CSV_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(OUTPUT_DAILY_CSV_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(OUTPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")

    print(f"{len(stops):,} arrets horaires ecrits dans {OUTPUT_STOPS_PATH}")
    print(f"{len(stops):,} arrets horaires ecrits dans {OUTPUT_STOPS_CSV_PATH}")
    print(f"{len(templates):,} troncons horaires templates ecrits dans {OUTPUT_TEMPLATE_PATH}")
    print(f"{len(templates):,} troncons horaires templates ecrits dans {OUTPUT_TEMPLATE_CSV_PATH}")
    print(f"{len(service_notes):,} notes de circulation ecrites dans {OUTPUT_SERVICE_NOTES_PATH}")
    print(f"{len(service_notes):,} notes de circulation ecrites dans {OUTPUT_SERVICE_NOTES_CSV_PATH}")
    print(f"{len(course_calendar):,} lignes calendrier course-jour ecrites dans {OUTPUT_COURSE_CALENDAR_PATH}")
    print(f"{len(course_calendar):,} lignes calendrier course-jour ecrites dans {OUTPUT_COURSE_CALENDAR_CSV_PATH}")
    print(f"{len(daily):,} troncons horaires par jour ecrits dans {OUTPUT_DAILY_PATH}")
    print(f"{len(daily):,} troncons horaires par jour ecrits dans {OUTPUT_DAILY_CSV_PATH}")
    print(f"Audit extraction ecrit dans {OUTPUT_AUDIT_PATH}")
    print("\nAudit par PDF:")
    print(audit.to_string(index=False))
    if not service_notes.empty:
        print("\nStatut parsing des notes:")
        print(service_notes["parse_status"].value_counts(dropna=False).to_string())
    print("\nTroncons par annee horaire:")
    print(daily.groupby("annee_horaire").size().rename("rows").to_string())


if __name__ == "__main__":
    main()
