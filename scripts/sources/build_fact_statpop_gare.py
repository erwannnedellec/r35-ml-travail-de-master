"""
Construit la table de fait STATPOP x gares R35 avec variables metier agregees.

Objectif
--------
Ce script produit, pour chaque millesime STATPOP et chaque gare R35 active, une
table resumant le profil socio-demographique de la zone d'influence de la gare.

Contrairement a une table brute STATPOP, la sortie ne conserve pas toutes les
colonnes OFS d'origine. Elle ne contient que des variables consolidees utiles
pour un modele de frequentation ferroviaire : densite residentielle, structure
des menages, structure d'age, stabilite residentielle, mobilite residentielle
recente et indicateurs de qualite HPI.

Unite spatiale — Voronoi clippe a 500 m (cf. ADR-025)
-----------------------------------------------------
Depuis la refonte ADR-025, chaque gare est associee a une zone d'influence de
type Voronoi clippee plutot qu'un simple disque de 500 m. Pour chaque millesime
STATPOP et chaque topologie active (cf. mapping STATPOP_YEAR_TO_HORAIRE), on
calcule un diagramme de Voronoi sur les gares actives, puis on clippe chaque
polygone a un disque de RADIUS_M metres. Cette approche garantit :
  - aucun chevauchement entre zones de gares actives (partition de Voronoi) ;
  - une zone maximale de RADIUS_M metres depuis chaque gare (clippage disque) ;
  - coherence topologique : les zones refletent les gares effectivement actives
    pour chaque millesime (ex. GIL disparait en H23, remplace par VVVI).

La topologie active pour chaque millesime STATPOP est derivee de la table
horaires_r35_arrets_officiels.parquet (PDFs officiels H16-H25), selon la
convention : STATPOP annee Y utilise la topologie de l'annee horaire HY
(meme numero). Pour STATPOP 2015 (anterieur a H16), la topologie H16 est
utilisee par defaut.

Coordonnees : MN95 / LV95 (EPSG:2056). Dans STATPOP, E_KOORD et N_KOORD
correspondent au coin sud-ouest de l'hectare. Le centroide (+50 m) est utilise.

Choix de transformation et d'agregation
---------------------------------------
Le classeur OFS data/external/statpop/be-b-00.03-10-STATPOP-v123-tab.xlsx
documente les variables STATPOP. Les colonnes OFS sont utilisees comme sources,
mais la table finale ne conserve que les variables derivees suivantes :

1. Intensite residentielle :
   - population_500m_total
   - menages_500m_total
   - densite_population_500m_km2
   - densite_menages_500m_km2
   - population_par_menage_500m

2. Structure des menages :
   - part_menages_1_personne
   - part_grands_menages_4p_plus
   - taille_menage_moyenne_estimee

3. Structure d'age :
   - part_population_0_14_ans
   - part_population_15_24_ans
   - part_population_25_64_ans
   - part_population_65_plus
   - part_population_80_plus

4. Dynamique residentielle :
   - indice_stabilite_residentielle
   - indice_mobilite_residentielle
   - part_nouveaux_arrivants_1_an

5. Variables secondaires potentiellement utiles :
   - part_population_etrangere
   - part_population_nee_etranger

6. Qualite / fiabilite :
   - hpi_classe_max_500m
   - hpi_hectares_classe_1_count
   - hpi_hectares_classe_2_count
   - hpi_hectares_classe_manquante_count
   - hpi_hectares_autre_classe_count
   - part_hectares_hpi_non_plausible
   - flag_qualite_statpop_faible

Pourquoi ne pas conserver les colonnes brutes ?
-----------------------------------------------
Les colonnes OFS detaillees sont nombreuses et parfois tres fines. Pour un
modele de frequentation a court terme, elles risquent d'ajouter du bruit,
de la colinearite et une interpretation difficile. Le script privilegie donc
des agregats larges et interpretables, notamment parce que :

- les valeurs STATPOP < 3 sont remplacees par 3 pour la protection des donnees ;
- les effectifs tres faibles ne doivent pas etre surinterpretes ;
- les parts et indices sont bornes a [0, 1] pour neutraliser les petits
  depassements mecaniques dus aux cellules protegees ;
- les variables STATPOP sont des variables lentes, mises a jour annuellement ;
- leur role est surtout de contextualiser la demande locale autour des gares.

Variantes entre fichiers STATPOP
--------------------------------
- 2015-2019 : separateur `,`, colonnes prefixees par l'annee (ex. B15BTOT)
- 2020      : separateur `;`, colonnes prefixees par l'annee (ex. B20BTOT)
- 2021      : separateur `;`, colonnes prefixees, sans donnees menages (HP*) ni HPI
- 2022      : separateur `;`, colonnes prefixees par l'annee (ex. B22BTOT)
- 2023      : separateur `;`, colonnes generiques + ERHJAHR/PUBJAHR ;
              colonnes menages parfois presentes mais vides, HPI absent
- 2024      : separateur `;`, colonnes generiques + ERHJAHR/PUBJAHR

Gestion des valeurs manquantes structurelles (imputation causale - ADR-076)
---------------------------------------------------------------------------
Les millesimes 2021 et 2023 ne contiennent pas de donnees menages (HP*) ni HPI.
Le script les impute par FORWARD-FILL CAUSAL (LOCF) via `impute_forward_fill_causal()`,
sur TOUTES les colonnes imputees, continues comme categorielles : report du dernier
millesime publie AVANT la date cible (2021 <- 2020 ; 2023 <- 2022).

C'est la recette d'origine promue au pipeline (ADR-076), prouvee par l'archeologie
`scripts/experiences/rebuild_statpop_origine.py`. Elle REMPLACE l'ancienne imputation
non-causale (interpolation lineaire par index + max des millesimes adjacents avec
fallback backward-fill garde par `notna().all()`). Cette garde etait le SYMPTOME, non
la cause (ADR-075 la designait a tort comme le defaut) : le geste canonique est le
forward-fill integral, seul a reproduire les valeurs d'ancrage CHBL/HTV/STLE
(2021=1, 2023=2).

VVVI (Vevey-Vignerons, active depuis H23) est reconstruite pour les millesimes
2020/2021/2022 par `build_vvvi_rows_h23()` (zone Voronoi figee sur la topologie H23).
La ligne inerte VVVI-2019 est ajoutee au consommateur (add_statpop..., jamais mobilisee
par la jointure Z-2).

Sources
-------
- data/dimension/dim_gare.parquet
- data/intermediate/horaires_r35_arrets_officiels.parquet  (topologie active par annee horaire)
- data/external/statpop/STATPOP{YYYY}.csv  (une par annee)

Sortie (branche STATPOP refabricable - ADR-076, n'est plus une entree figee)
----------------------------------------------------------------------------
- data/processed/sources/statpop_clean_causal.csv
- data/processed/sources/statpop_clean_causal.parquet
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
import pandas as pd
import shapely
import shapely.geometry
import shapely.ops


# -----------------------------------------------------------------------------
# Parametres generaux
# -----------------------------------------------------------------------------

DIM_GARE_PATH = Path("data/dimension/dim_gare.parquet")
STATPOP_DIR = Path("data/external/statpop")
STATPOP_DOCUMENTATION_PATH = STATPOP_DIR / "be-b-00.03-10-STATPOP-v123-tab.xlsx"
# Topologie active par annee horaire. Artefact produit par
# scripts/sources/build_horaires_r35_from_pdfs.py ; chemin canonique declare par
# pipeline.paths.HORAIRES_ARRETS_OFFICIELS (data/intermediate/). Le chemin
# data/processed/ utilise jusqu'ici pointait sur une copie d'epoque, byte-identique
# (SHA-256 5c79ca5f...) mais NON regeneree par `make clean-all` : l'invariant de
# reproduction ne tenait pas sur cette branche (correctif pre-publication, ADR-078 5.2).
HORAIRES_OFFICIELS_PATH = Path("data/intermediate/horaires_r35_arrets_officiels.parquet")
OUTPUT_CSV = Path("data/processed/sources/statpop_clean_causal.csv")
OUTPUT_PARQUET = Path("data/processed/sources/statpop_clean_causal.parquet")

RADIUS_M = 500
BUFFER_AREA_KM2 = np.pi * (RADIUS_M / 1000) ** 2  # surface du disque complet (reference)
VORONOI_ENVELOPE_BUFFER = 5_000  # m — extension bounding box pour le calcul Voronoi

GARE_E = "lv95East"
GARE_N = "lv95North"

# Mapping millesime STATPOP (annee civile Y) → annee horaire HY.
# Convention : HY couvre dec(Y-1)–dec(Y), donc la majeure partie de l'annee civile Y.
# STATPOP 2015 n'a pas de HY correspondant (H15 avant notre periode) : on utilise H16 par defaut.
# Sources : horaires_r35_arrets_officiels.parquet (PDFs H16–H25).
STATPOP_YEAR_TO_HORAIRE: dict[int, str] = {
    2015: "H16",
    2016: "H16",
    2017: "H17",
    2018: "H18",
    2019: "H19",
    2020: "H20",
    2021: "H21",
    2022: "H22",
    2023: "H23",
    2024: "H24",
}

# Seuil de 20% : si plus d'un cinquieme des hectares dans le buffer 500 m
# presentent des menages "non plausibles" (HPI = 2), la fiabilite des variables
# menages est consideree insuffisante pour cette gare-annee. Le choix de 20%
# est un seuil prudent qui penalise les zones a fortes perturbations cadastrales
# sans disqualifier les arrêts ruraux (ou HPI = 2 sur quelques hectares isoles
# est un artefact de zonage plutot qu'un vrai probleme de qualite OFS).
HPI_QUALITY_WARNING_THRESHOLD = 0.20


# -----------------------------------------------------------------------------
# Expressions regulieres
# -----------------------------------------------------------------------------

# B15BTOT -> BBTOT, H15PTOT -> HPTOT, B21BM01 -> BBM01.
_YEAR_PREFIX_RE = re.compile(r"^([BH])\d{2}(.+)$")
_STATPOP_YEAR_RE = re.compile(r"STATPOP(\d{4})$")


# -----------------------------------------------------------------------------
# Codes STATPOP necessaires aux variables metier
# -----------------------------------------------------------------------------

# Codes age STATPOP par classes quinquennales.
# Les colonnes existent separement pour les hommes (BBMxx) et femmes (BBWxx).
AGE_CODES_0_14 = ["01", "02", "03"]
AGE_CODES_15_24 = ["04", "05"]
AGE_CODES_25_64 = ["06", "07", "08", "09", "10", "11", "12", "13"]
AGE_CODES_65_PLUS = ["14", "15", "16", "17", "18", "19"]
AGE_CODES_80_PLUS = ["17", "18", "19"]

# Colonnes brutes necessaires pour construire les variables finales.
# Elles ne seront pas conservees dans la table de sortie.
REQUIRED_POPULATION_COLUMNS = [
    "BBTOT",  # population residante permanente totale
    "BB12",  # population residante permanente etrangere totale
    "BB26",  # population nee a l'etranger totale
    "BB41",  # duree de residence dans la commune : moins d'un an
    "BB42",  # duree de residence dans la commune : 1-5 ans
    "BB44",  # duree de residence dans la commune : plus de 10 ans
    "BB45",  # duree de residence dans la commune : depuis la naissance
    "BB52",  # domicile un an auparavant : meme canton
    "BB53",  # domicile un an auparavant : autre canton
    "BB54",  # domicile un an auparavant : etranger
    *[f"BBM{code}" for code in AGE_CODES_0_14 + AGE_CODES_15_24 + AGE_CODES_25_64 + AGE_CODES_65_PLUS],
    *[f"BBW{code}" for code in AGE_CODES_0_14 + AGE_CODES_15_24 + AGE_CODES_25_64 + AGE_CODES_65_PLUS],
]

REQUIRED_HOUSEHOLD_COLUMNS = [
    "HPTOT",  # menages prives total
    "HP01",  # menages prives 1 personne
    "HP02",  # menages prives 2 personnes
    "HP03",  # menages prives 3 personnes
    "HP04",  # menages prives 4 personnes
    "HP05",  # menages prives 5 personnes
    "HP06",  # menages prives 6 personnes ou plus
]

REQUIRED_SUM_COLUMNS = sorted(set(REQUIRED_POPULATION_COLUMNS + REQUIRED_HOUSEHOLD_COLUMNS))


# -----------------------------------------------------------------------------
# Schema de sortie
# -----------------------------------------------------------------------------

BASE_OUTPUT_COLUMNS = [
    "annee_enquete_statpop",
    "annee_publication_statpop",
    "gare_abreviation",
    "gare_bpuic",
    "gare_nom",
    "gare_commune",
    "gare_km",
    "statpop_hectares_count",
]

FEATURE_OUTPUT_COLUMNS = [
    # Intensite residentielle
    "population_500m_total",
    "menages_500m_total",
    "densite_population_500m_km2",
    "densite_menages_500m_km2",
    "population_par_menage_500m",
    # Structure des menages
    "part_menages_1_personne",
    "part_grands_menages_4p_plus",
    "taille_menage_moyenne_estimee",
    # Structure d'age
    "part_population_0_14_ans",
    "part_population_15_24_ans",
    "part_population_25_64_ans",
    "part_population_65_plus",
    "part_population_80_plus",
    # Dynamique residentielle
    "indice_stabilite_residentielle",
    "indice_mobilite_residentielle",
    "part_nouveaux_arrivants_1_an",
    # Variables secondaires / territoriales
    "part_population_etrangere",
    "part_population_nee_etranger",
    # Qualite HPI
    "hpi_classe_max_500m",
    "hpi_hectares_classe_1_count",
    "hpi_hectares_classe_2_count",
    "hpi_hectares_classe_manquante_count",
    "hpi_hectares_autre_classe_count",
    "part_hectares_hpi_non_plausible",
    "flag_qualite_statpop_faible",
]

OUTPUT_COLUMN_ORDER = [*BASE_OUTPUT_COLUMNS, *FEATURE_OUTPUT_COLUMNS]

INTEGER_OUTPUT_COLUMNS = [
    "annee_enquete_statpop",
    "annee_publication_statpop",
    "gare_bpuic",
    "statpop_hectares_count",
    "population_500m_total",
    "menages_500m_total",
    "hpi_classe_max_500m",
    "hpi_hectares_classe_1_count",
    "hpi_hectares_classe_2_count",
    "hpi_hectares_classe_manquante_count",
    "hpi_hectares_autre_classe_count",
    "flag_qualite_statpop_faible",
]

# Colonnes continues interpolees lineairement pour les millesimes 2021 et 2023.
# Exclut les indicateurs categoriels/binaires traites separement.
INTERPOLATION_COLUMNS = [
    "menages_500m_total",
    "densite_menages_500m_km2",
    "population_par_menage_500m",
    "part_menages_1_personne",
    "part_grands_menages_4p_plus",
    "taille_menage_moyenne_estimee",
    "hpi_hectares_classe_1_count",
    "hpi_hectares_classe_2_count",
    "hpi_hectares_classe_manquante_count",
    "hpi_hectares_autre_classe_count",
    "part_hectares_hpi_non_plausible",
]

# Indicateurs categoriels/binaires imputes par le maximum des millesimes adjacents
# (principe de precaution : on herite de la valeur "degradee" si l'une des annees
# voisines l'est, plutot que de lisser vers une valeur intermediaire sans sens).
IMPUTATION_MAX_COLUMNS = [
    "hpi_classe_max_500m",     # ordinal 1/2 : la classe la plus elevee est retenue
    "flag_qualite_statpop_faible",  # binaire 0/1 : OR logique entre annees adjacentes
]

# -----------------------------------------------------------------------------
# Imputation causale et perimetre (ADR-076)
# -----------------------------------------------------------------------------
# Millesimes sans donnees menages/HPI, combles par forward-fill causal (LOCF).
GAP_YEARS = {2021, 2023}

# Toutes les colonnes imputees (continues + categorielles) recoivent le meme geste
# causal (report du millesime precedent). Voir impute_forward_fill_causal.
IMPUTED_COLUMNS = INTERPOLATION_COLUMNS + IMPUTATION_MAX_COLUMNS

# VVVI (active depuis H23) reconstruite pour ces millesimes via la topologie H23.
# 2019 volontairement EXCLU : la ligne inerte VVVI-2019 est ajoutee au consommateur
# (add_statpop..., jamais mobilisee par la jointure Z-2). Reproduit le bocal 40ae0fe0.
VVVI_FIX_YEARS = [2020, 2021, 2022]

# Perimetre consomme par le mapping Z-2 (observations H22-H25) : millesimes 2019-2023.
KEEP_MILLESIMES = [2019, 2020, 2021, 2022, 2023]

FLOAT_OUTPUT_COLUMNS = [
    "gare_km",
    "densite_population_500m_km2",
    "densite_menages_500m_km2",
    "population_par_menage_500m",
    "part_menages_1_personne",
    "part_grands_menages_4p_plus",
    "taille_menage_moyenne_estimee",
    "part_population_0_14_ans",
    "part_population_15_24_ans",
    "part_population_25_64_ans",
    "part_population_65_plus",
    "part_population_80_plus",
    "indice_stabilite_residentielle",
    "indice_mobilite_residentielle",
    "part_nouveaux_arrivants_1_an",
    "part_population_etrangere",
    "part_population_nee_etranger",
    "part_hectares_hpi_non_plausible",
]


# -----------------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class StatpopFileMetadata:
    """Metadonnees constantes a l'echelle d'un fichier STATPOP."""

    survey_year: int
    publication_year: object


@dataclass(frozen=True)
class StatpopMeasureColumns:
    """Colonnes effectivement disponibles dans un millesime STATPOP normalise."""

    available_sum_cols: list[str]
    has_hpi: bool
    missing_required_cols: list[str]
    ignored_cols: list[str]


# -----------------------------------------------------------------------------
# Fonctions utilitaires generales
# -----------------------------------------------------------------------------

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime le prefixe d'annee des colonnes STATPOP.

    Exemples
    --------
    - B15BTOT devient BBTOT
    - H20PTOT devient HPTOT
    - B21BM01 devient BBM01

    Les fichiers recents utilisent deja des codes generiques ; ils ne sont donc
    pas modifies.
    """
    rename: dict[str, str] = {}
    for col in df.columns:
        match = _YEAR_PREFIX_RE.match(col)
        if match:
            rename[col] = match.group(1) + match.group(2)
    return df.rename(columns=rename) if rename else df


def detect_separator(path: Path) -> str:
    """Detecte grossierement le separateur d'un CSV STATPOP."""
    sample = path.read_text(encoding="utf-8", errors="replace")[:1000]
    return ";" if sample.count(";") > sample.count(",") else ","


def extract_statpop_year(path: Path) -> int:
    """Extrait l'annee depuis un nom de fichier de type STATPOP2024.csv."""
    match = _STATPOP_YEAR_RE.match(path.stem)
    if not match:
        raise ValueError(f"Nom de fichier STATPOP inattendu : {path.name}")
    return int(match.group(1))


def unique_int_or_na(df: pd.DataFrame, col: str) -> object:
    """Retourne l'unique valeur entiere d'une colonne, sinon pd.NA."""
    if col not in df.columns:
        return pd.NA
    values = pd.to_numeric(df[col], errors="coerce").dropna().unique()
    if len(values) != 1:
        return pd.NA
    return int(values[0])


def safe_divide(numerator: object, denominator: object) -> object:
    """Division robuste retournant pd.NA si le denominateur est nul ou manquant."""
    if pd.isna(denominator) or denominator == 0:
        return pd.NA
    if pd.isna(numerator):
        return pd.NA
    return float(numerator) / float(denominator)


def safe_share(numerator: object, denominator: object) -> object:
    """Ratio borne a [0, 1] pour les variables interpretees comme parts."""
    ratio = safe_divide(numerator, denominator)
    if pd.isna(ratio):
        return pd.NA
    return min(max(float(ratio), 0.0), 1.0)


def sum_existing(values: dict[str, object], columns: list[str]) -> object:
    """Somme des colonnes disponibles dans un dictionnaire d'agregats.

    Retourne pd.NA si aucune des colonnes demandees n'est disponible. Cela evite
    de confondre une vraie somme nulle avec une absence de donnees dans le
    millesime STATPOP.
    """
    existing_values = [values[col] for col in columns if col in values and not pd.isna(values[col])]
    if not existing_values:
        return pd.NA
    return sum(existing_values)


# -----------------------------------------------------------------------------
# Topologie active et zones Voronoi
# -----------------------------------------------------------------------------

def load_active_gares_by_horaire(
    horaires_path: Path = HORAIRES_OFFICIELS_PATH,
) -> dict[str, set[str]]:
    """Charge les gares actives par annee horaire depuis les PDFs officiels.

    Returns:
        Dict {annee_horaire: set[abreviation]} derive de horaires_r35_arrets_officiels.parquet.
    """
    df = pd.read_parquet(horaires_path, columns=["annee_horaire", "gare"])
    return (
        df.groupby("annee_horaire")["gare"]
        .apply(lambda s: set(s.dropna().unique()))
        .to_dict()
    )


def compute_voronoi_zones(
    gares_actives: pd.DataFrame,
    radius_m: float = RADIUS_M,
    envelope_buffer: float = VORONOI_ENVELOPE_BUFFER,
) -> dict[str, "shapely.geometry.Polygon"]:
    """Calcule les zones Voronoi clippees a radius_m pour les gares actives.

    Pour chaque gare, la zone d'influence est l'intersection du polygone de
    Voronoi (calculé sur toutes les gares actives) avec le disque de rayon
    radius_m centre sur la gare. Cela garantit que chaque hectare STATPOP
    est attribue a au plus une gare active, et que la zone ne depasse pas
    radius_m metres.

    Args:
        gares_actives: DataFrame avec colonnes 'abreviation', 'lv95East', 'lv95North'.
        radius_m: rayon de clippage en metres (defaut RADIUS_M = 500 m).
        envelope_buffer: extension de la bounding box pour le calcul Voronoi (defaut 5 000 m).

    Returns:
        Dict {abreviation: shapely.Polygon} des zones d'influence.

    Raises:
        ValueError: si une gare ne recoit pas de polygone Voronoi.
    """
    from shapely.geometry import MultiPoint, Point, Polygon
    from shapely.ops import voronoi_diagram

    coords = list(zip(gares_actives["lv95East"], gares_actives["lv95North"]))
    abbrevs = gares_actives["abreviation"].tolist()

    if len(coords) < 2:
        raise ValueError(f"Au moins 2 gares requises pour le Voronoi, recu : {len(coords)}")

    multipoint = MultiPoint(coords)

    e_vals = gares_actives["lv95East"]
    n_vals = gares_actives["lv95North"]
    envelope = Polygon([
        (e_vals.min() - envelope_buffer, n_vals.min() - envelope_buffer),
        (e_vals.max() + envelope_buffer, n_vals.min() - envelope_buffer),
        (e_vals.max() + envelope_buffer, n_vals.max() + envelope_buffer),
        (e_vals.min() - envelope_buffer, n_vals.max() + envelope_buffer),
    ])

    voronoi = voronoi_diagram(multipoint, envelope=envelope)

    # Associer chaque polygone Voronoi a la gare dont le point est contenu.
    zones: dict[str, object] = {}
    for poly in voronoi.geoms:
        for abbr, (e, n) in zip(abbrevs, coords):
            if poly.contains(Point(e, n)):
                disk = Point(e, n).buffer(radius_m)
                zones[abbr] = poly.intersection(disk)
                break

    missing = set(abbrevs) - set(zones)
    if missing:
        raise ValueError(f"Zones Voronoi non attribuees : {missing}")

    return zones


_voronoi_cache: dict[frozenset, dict[str, object]] = {}


def get_voronoi_zones_for_year(
    statpop_year: int,
    gares: pd.DataFrame,
    active_by_horaire: dict[str, set[str]],
) -> dict[str, "shapely.geometry.Polygon"]:
    """Retourne les zones Voronoi pour un millesime STATPOP, avec cache par topologie.

    Args:
        statpop_year: annee civile du millesime STATPOP.
        gares: DataFrame complet avec coordonnees LV95.
        active_by_horaire: dict {annee_horaire: set[abreviation]}.

    Returns:
        Dict {abreviation: shapely.Polygon} des zones actives pour ce millesime.
    """
    annee_horaire = STATPOP_YEAR_TO_HORAIRE.get(statpop_year)
    if annee_horaire is None:
        raise ValueError(f"Millesime STATPOP {statpop_year} absent de STATPOP_YEAR_TO_HORAIRE")

    if annee_horaire not in active_by_horaire:
        raise ValueError(
            f"Annee horaire {annee_horaire} absente de horaires_r35_arrets_officiels. "
            f"Annees disponibles : {sorted(active_by_horaire)}"
        )

    active_abbrevs = active_by_horaire[annee_horaire]
    topology_key = frozenset(active_abbrevs)

    if topology_key not in _voronoi_cache:
        gares_actives = gares[gares["abreviation"].isin(active_abbrevs)].copy()
        gares_actives = gares_actives.dropna(subset=[GARE_E, GARE_N])
        _voronoi_cache[topology_key] = compute_voronoi_zones(gares_actives)

    return _voronoi_cache[topology_key]


# -----------------------------------------------------------------------------
# Lecture et preparation des fichiers STATPOP
# -----------------------------------------------------------------------------

def get_file_metadata(df: pd.DataFrame, file_year: int) -> StatpopFileMetadata:
    """Determine l'annee d'enquete et l'annee de publication du fichier."""
    survey_year = unique_int_or_na(df, "ERHJAHR")
    publication_year = unique_int_or_na(df, "PUBJAHR")
    return StatpopFileMetadata(
        survey_year=file_year if pd.isna(survey_year) else int(survey_year),
        publication_year=publication_year,
    )


def get_measure_columns(df: pd.DataFrame) -> StatpopMeasureColumns:
    """Identifie les colonnes STATPOP necessaires et disponibles.

    On ne conserve en memoire d'agregation que les colonnes requises pour les
    variables finales. Si une colonne existe mais ne contient que des valeurs
    manquantes, elle est consideree comme indisponible.
    """
    available_sum_cols = [
        col
        for col in REQUIRED_SUM_COLUMNS
        if col in df.columns and df[col].notna().any()
    ]

    missing_required_cols = sorted(set(REQUIRED_SUM_COLUMNS) - set(available_sum_cols))

    technical_cols = {
        "ERHJAHR",
        "PUBJAHR",
        "RELI",
        "E_KOORD",
        "N_KOORD",
        "X_KOORD",
        "Y_KOORD",
        "E_CTR",
        "N_CTR",
        "GMDE",
        "HIST_GMDE",
        "HPI",
    }
    used_cols = set(available_sum_cols) | technical_cols
    ignored_cols = sorted(set(df.columns) - used_cols)

    return StatpopMeasureColumns(
        available_sum_cols=available_sum_cols,
        has_hpi="HPI" in df.columns and df["HPI"].notna().any(),
        missing_required_cols=missing_required_cols,
        ignored_cols=ignored_cols,
    )


def load_statpop(
    path: Path,
    e_min: float,
    e_max: float,
    n_min: float,
    n_max: float,
) -> tuple[pd.DataFrame, StatpopMeasureColumns, StatpopFileMetadata]:
    """Charge, normalise et prefiltre un fichier STATPOP.

    Le prefiltre spatial est volontairement rectangulaire. Il limite le nombre
    d'hectares utilises pour le calcul exact des distances autour de chaque gare.
    """
    file_year = extract_statpop_year(path)
    sep = detect_separator(path)

    df = pd.read_csv(path, sep=sep, dtype={"RELI": str})
    df = normalize_column_names(df)

    metadata = get_file_metadata(df, file_year)
    measure_cols = get_measure_columns(df)

    required_coordinates = {"E_KOORD", "N_KOORD"}
    missing_coordinates = required_coordinates - set(df.columns)
    if missing_coordinates:
        raise KeyError(
            f"Le fichier {path.name} ne contient pas les coordonnees attendues : "
            f"{sorted(missing_coordinates)}"
        )

    # Centroide de l'hectare STATPOP.
    df["E_CTR"] = pd.to_numeric(df["E_KOORD"], errors="coerce") + 50
    df["N_CTR"] = pd.to_numeric(df["N_KOORD"], errors="coerce") + 50

    # Conversion numerique uniquement pour les colonnes utiles a l'agregation.
    for col in measure_cols.available_sum_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "HPI" in df.columns:
        df["HPI"] = pd.to_numeric(df["HPI"], errors="coerce")

    mask = (
        (df["E_CTR"] >= e_min)
        & (df["E_CTR"] <= e_max)
        & (df["N_CTR"] >= n_min)
        & (df["N_CTR"] <= n_max)
    )

    cols_to_keep = ["E_CTR", "N_CTR", *measure_cols.available_sum_cols]
    if "HPI" in df.columns:
        cols_to_keep.append("HPI")

    return df.loc[mask, cols_to_keep].copy(), measure_cols, metadata


# -----------------------------------------------------------------------------
# Agregation spatiale et creation des variables metier
# -----------------------------------------------------------------------------

def aggregate_raw_values_for_station(
    statpop: pd.DataFrame,
    zone: "shapely.geometry.Polygon",
    measure_cols: StatpopMeasureColumns,
) -> tuple[dict[str, object], pd.Series]:
    """Agrege les colonnes STATPOP necessaires dans la zone Voronoi d'une gare.

    Cette fonction produit encore des valeurs intermediaires sur la base des
    codes OFS. Elles sont ensuite transformees en variables metier par
    build_features_from_raw_aggregates().
    """
    pts_e = statpop["E_CTR"].to_numpy(dtype=float)
    pts_n = statpop["N_CTR"].to_numpy(dtype=float)
    points_arr = shapely.points(pts_e, pts_n)
    within_mask = shapely.within(points_arr, zone)
    within = statpop.loc[within_mask]

    raw: dict[str, object] = {"statpop_hectares_count": int(len(within))}

    for source_col in measure_cols.available_sum_cols:
        # min_count=1 retourne NaN si toutes les valeurs sont NA, mais 0 si
        # aucun hectare n'est retenu. Ici, aucun hectare = 0 effectif.
        raw[source_col] = 0 if within.empty else within[source_col].sum(min_count=1)

    hpi = pd.Series(dtype="float64")
    if "HPI" in within.columns:
        hpi = pd.to_numeric(within["HPI"], errors="coerce")

    return raw, hpi


def build_hpi_features(hpi: pd.Series, hectares_count: int) -> dict[str, object]:
    """Construit les indicateurs de qualite lies a HPI.

    HPI est une classe qualitative :
    - 1 = menages prives plausibles dans l'hectare ;
    - 2 = au moins un menage prive non plausible.

    Le champ n'est donc jamais somme. On conserve des comptes d'hectares par
    classe et un ratio d'hectares non plausibles.
    """
    if hpi.empty:
        return {
            "hpi_classe_max_500m": pd.NA,
            "hpi_hectares_classe_1_count": pd.NA,
            "hpi_hectares_classe_2_count": pd.NA,
            "hpi_hectares_classe_manquante_count": pd.NA,
            "hpi_hectares_autre_classe_count": pd.NA,
            "part_hectares_hpi_non_plausible": pd.NA,
            "flag_qualite_statpop_faible": pd.NA,
        }

    hpi_values = hpi.dropna()
    class_1_count = int((hpi == 1).sum())
    class_2_count = int((hpi == 2).sum())
    missing_count = int(hpi.isna().sum())
    other_count = int((hpi.notna() & ~hpi.isin([1, 2])).sum())

    part_non_plausible = safe_share(class_2_count, hectares_count)
    flag_quality_low = (
        pd.NA
        if pd.isna(part_non_plausible)
        else int(part_non_plausible > HPI_QUALITY_WARNING_THRESHOLD)
    )

    return {
        "hpi_classe_max_500m": int(hpi_values.max()) if not hpi_values.empty else pd.NA,
        "hpi_hectares_classe_1_count": class_1_count,
        "hpi_hectares_classe_2_count": class_2_count,
        "hpi_hectares_classe_manquante_count": missing_count,
        "hpi_hectares_autre_classe_count": other_count,
        "part_hectares_hpi_non_plausible": part_non_plausible,
        "flag_qualite_statpop_faible": flag_quality_low,
    }


def build_features_from_raw_aggregates(
    raw: dict[str, object],
    hpi: pd.Series,
    zone_area_km2: float = BUFFER_AREA_KM2,
) -> dict[str, object]:
    """Transforme les agregats OFS bruts en variables metier interpretables.

    Args:
        raw: agregats OFS bruts par colonne source.
        hpi: serie des valeurs HPI pour les hectares de la zone.
        zone_area_km2: surface reelle de la zone Voronoi clippee en km²
            (utile pour les features de densite ; defaut = surface disque 500m).
    """
    hectares_count = int(raw.get("statpop_hectares_count", 0))

    # 1. Volumes principaux
    population_total = raw.get("BBTOT", pd.NA)
    menages_total = raw.get("HPTOT", pd.NA)

    # 2. Structure des menages
    menages_1p = raw.get("HP01", pd.NA)
    grands_menages = sum_existing(raw, ["HP04", "HP05", "HP06"])

    taille_menage_numerator = sum_existing(
        {
            "HP01": raw.get("HP01", pd.NA),
            "HP02": pd.NA if pd.isna(raw.get("HP02", pd.NA)) else 2 * raw.get("HP02"),
            "HP03": pd.NA if pd.isna(raw.get("HP03", pd.NA)) else 3 * raw.get("HP03"),
            "HP04": pd.NA if pd.isna(raw.get("HP04", pd.NA)) else 4 * raw.get("HP04"),
            "HP05": pd.NA if pd.isna(raw.get("HP05", pd.NA)) else 5 * raw.get("HP05"),
            # Approximation : HP06 signifie 6 personnes ou plus. On utilise 6
            # comme borne minimale prudente.
            "HP06": pd.NA if pd.isna(raw.get("HP06", pd.NA)) else 6 * raw.get("HP06"),
        },
        ["HP01", "HP02", "HP03", "HP04", "HP05", "HP06"],
    )

    # 3. Structure d'age
    age_0_14 = sum_existing(raw, [f"BBM{c}" for c in AGE_CODES_0_14] + [f"BBW{c}" for c in AGE_CODES_0_14])
    age_15_24 = sum_existing(raw, [f"BBM{c}" for c in AGE_CODES_15_24] + [f"BBW{c}" for c in AGE_CODES_15_24])
    age_25_64 = sum_existing(raw, [f"BBM{c}" for c in AGE_CODES_25_64] + [f"BBW{c}" for c in AGE_CODES_25_64])
    age_65_plus = sum_existing(raw, [f"BBM{c}" for c in AGE_CODES_65_PLUS] + [f"BBW{c}" for c in AGE_CODES_65_PLUS])
    age_80_plus = sum_existing(raw, [f"BBM{c}" for c in AGE_CODES_80_PLUS] + [f"BBW{c}" for c in AGE_CODES_80_PLUS])

    # 4. Dynamique residentielle
    stable_residence = sum_existing(raw, ["BB44", "BB45"])
    mobile_residence = sum_existing(raw, ["BB41", "BB42"])
    nouveaux_arrivants = sum_existing(raw, ["BB52", "BB53", "BB54"])

    # 5. Variables secondaires
    population_etrangere = raw.get("BB12", pd.NA)
    population_nee_etranger = raw.get("BB26", pd.NA)

    features = {
        # Intensite residentielle
        "population_500m_total": population_total,
        "menages_500m_total": menages_total,
        "densite_population_500m_km2": safe_divide(population_total, zone_area_km2),
        "densite_menages_500m_km2": safe_divide(menages_total, zone_area_km2),
        "population_par_menage_500m": safe_divide(population_total, menages_total),
        # Structure des menages
        "part_menages_1_personne": safe_share(menages_1p, menages_total),
        "part_grands_menages_4p_plus": safe_share(grands_menages, menages_total),
        "taille_menage_moyenne_estimee": safe_divide(taille_menage_numerator, menages_total),
        # Structure d'age
        "part_population_0_14_ans": safe_share(age_0_14, population_total),
        "part_population_15_24_ans": safe_share(age_15_24, population_total),
        "part_population_25_64_ans": safe_share(age_25_64, population_total),
        "part_population_65_plus": safe_share(age_65_plus, population_total),
        "part_population_80_plus": safe_share(age_80_plus, population_total),
        # Dynamique residentielle
        "indice_stabilite_residentielle": safe_share(stable_residence, population_total),
        "indice_mobilite_residentielle": safe_share(mobile_residence, population_total),
        "part_nouveaux_arrivants_1_an": safe_share(nouveaux_arrivants, population_total),
        # Variables secondaires / territoriales
        "part_population_etrangere": safe_share(population_etrangere, population_total),
        "part_population_nee_etranger": safe_share(population_nee_etranger, population_total),
    }

    features.update(build_hpi_features(hpi, hectares_count))
    return features


def aggregate_for_station(
    statpop: pd.DataFrame,
    zone: "shapely.geometry.Polygon",
    measure_cols: StatpopMeasureColumns,
) -> dict[str, object]:
    """Produit les variables finales STATPOP pour une gare donnee.

    Args:
        statpop: DataFrame des hectares STATPOP pre-filtres dans la bounding box.
        zone: polygone Voronoi clippe de la gare (zone d'influence exclusive).
        measure_cols: colonnes sources disponibles dans ce millesime.
    """
    zone_area_km2 = zone.area / 1_000_000
    raw, hpi = aggregate_raw_values_for_station(statpop, zone, measure_cols)
    features = build_features_from_raw_aggregates(raw, hpi, zone_area_km2)

    return {
        "statpop_hectares_count": raw["statpop_hectares_count"],
        **features,
    }


# -----------------------------------------------------------------------------
# Finalisation du schema
# -----------------------------------------------------------------------------

def finalize_schema(fact: pd.DataFrame) -> pd.DataFrame:
    """Garantit l'ordre des colonnes, les types et le tri final."""
    for col in OUTPUT_COLUMN_ORDER:
        if col not in fact.columns:
            fact[col] = pd.NA

    fact = fact[OUTPUT_COLUMN_ORDER].copy()

    for col in INTEGER_OUTPUT_COLUMNS:
        fact[col] = pd.to_numeric(fact[col], errors="coerce").astype("Int64")

    for col in FLOAT_OUTPUT_COLUMNS:
        fact[col] = pd.to_numeric(fact[col], errors="coerce").astype("Float64")

    return fact.sort_values(["annee_enquete_statpop", "gare_km"]).reset_index(drop=True)


# -----------------------------------------------------------------------------
# Interpolation des millesimes incomplets
# -----------------------------------------------------------------------------

def _impute_column(
    fact: pd.DataFrame,
    col: str,
    pivot_imputed: pd.DataFrame,
    years_with_gaps: set[int],
) -> pd.DataFrame:
    """Applique les valeurs imputees d'une colonne sur les annees cibles."""
    for year in years_with_gaps:
        if year not in pivot_imputed.index:
            continue
        mask_year = fact["annee_enquete_statpop"] == year
        if not fact.loc[mask_year, col].isna().any():
            continue
        for gare, val in pivot_imputed.loc[year].items():
            if pd.isna(val):
                continue
            mask = mask_year & (fact["gare_abreviation"] == gare)
            fact.loc[mask, col] = round(val) if col in INTEGER_OUTPUT_COLUMNS else val
    return fact


def impute_forward_fill_causal(fact: pd.DataFrame) -> pd.DataFrame:
    """Impute les millesimes 2021 et 2023 par forward-fill causal (LOCF) - ADR-076.

    Report du dernier millesime publie AVANT la date cible (2021 <- 2020,
    2023 <- 2022), applique a TOUTES les colonnes imputees, continues comme
    categorielles (hpi_classe_max, flag). C'est la recette d'origine promue au
    pipeline, prouvee par l'archeologie (rebuild_statpop_origine.py) : elle
    remplace l'imputation non-causale d'epoque (interpolation lineaire par index
    + max des millesimes adjacents avec fallback backward-fill garde par
    notna().all()). Seul le forward-fill reproduit les valeurs d'ancrage
    CHBL/HTV/STLE (2021=1, 2023=2, ADR-075) ; la garde notna().all() etait le
    symptome, non la cause, et disparait avec le bloc qu'elle gardait.
    """
    fact = fact.copy()
    for col in [c for c in IMPUTED_COLUMNS if c in fact.columns]:
        pivot = fact.pivot(index="annee_enquete_statpop", columns="gare_abreviation", values=col)
        pivot_ffill = pivot.astype(float).ffill()  # LOCF : millesime precedent (causal)
        fact = _impute_column(fact, col, pivot_ffill, GAP_YEARS)
    return fact


def build_vvvi_rows_h23(
    gares: pd.DataFrame,
    years: list[int] | None = None,
) -> list[dict[str, object]]:
    """Reconstruit les lignes VVVI via la topologie H23 pour `years` - ADR-076.

    VVVI (Vevey-Vignerons) a ouvert en H23 ; STATPOP ne la couvre pas avant. Sa
    zone Voronoi est figee sur la topologie H23 (VVVI active, GIL absent) et les
    hectares RELI de chaque millesime y sont agreges. Reutilise les fonctions du
    module (load_statpop / aggregate_for_station / compute_voronoi_zones).
    Recette d'origine promue au pipeline (cf. rebuild_statpop_origine.py).
    Defaut : VVVI_FIX_YEARS = [2020, 2021, 2022] (VVVI-2019 ajoute au consommateur).
    """
    if years is None:
        years = VVVI_FIX_YEARS
    active = load_active_gares_by_horaire()
    coords = gares.dropna(subset=[GARE_E, GARE_N])
    h23_gares = coords[coords["abreviation"].isin(active["H23"])].copy()
    zones = compute_voronoi_zones(h23_gares)
    vvvi_zone = zones["VVVI"]
    vvvi = coords[coords["abreviation"] == "VVVI"].iloc[0]
    e_min = float(coords[GARE_E].min()) - RADIUS_M
    e_max = float(coords[GARE_E].max()) + RADIUS_M
    n_min = float(coords[GARE_N].min()) - RADIUS_M
    n_max = float(coords[GARE_N].max()) + RADIUS_M

    rows: list[dict[str, object]] = []
    for year in years:
        statpop, measure_cols, metadata = load_statpop(
            STATPOP_DIR / f"STATPOP{year}.csv", e_min, e_max, n_min, n_max
        )
        agg = aggregate_for_station(statpop=statpop, zone=vvvi_zone, measure_cols=measure_cols)
        rows.append(
            {
                "annee_enquete_statpop": year,
                "annee_publication_statpop": metadata.publication_year,
                "gare_abreviation": "VVVI",
                "gare_bpuic": int(vvvi["bpuic"]),
                "gare_nom": vvvi["nom"],
                "gare_commune": vvvi["commune"],
                "gare_km": float(vvvi["km"]),
                **agg,
            }
        )
    return rows


# -----------------------------------------------------------------------------
# Construction de la table finale
# -----------------------------------------------------------------------------

def build_fact(
    gares: pd.DataFrame,
    statpop_files: list[Path],
    active_by_horaire: dict[str, set[str]],
) -> pd.DataFrame:
    """Construit la table de fait complete (zones Voronoi clippees par topologie active).

    Pour chaque millesime STATPOP, seules les gares actives selon STATPOP_YEAR_TO_HORAIRE
    sont incluses. Les zones d'influence sont des polygones Voronoi clippes a RADIUS_M,
    partitionnant l'espace entre les gares actives de l'annee horaire correspondante.

    Args:
        gares: DataFrame dim_gare avec coordonnees LV95.
        statpop_files: liste des fichiers STATPOP*.csv.
        active_by_horaire: dict {annee_horaire: set[abreviation]} issue des horaires officiels.
    """
    # Bounding box sur toutes les gares (avec marge) pour le prefiltre spatial.
    gares_coords = gares.dropna(subset=[GARE_E, GARE_N])
    e_min = float(gares_coords[GARE_E].min()) - RADIUS_M
    e_max = float(gares_coords[GARE_E].max()) + RADIUS_M
    n_min = float(gares_coords[GARE_N].min()) - RADIUS_M
    n_max = float(gares_coords[GARE_N].max()) + RADIUS_M

    rows: list[dict[str, object]] = []

    for path in sorted(statpop_files):
        print(f"  {path.name}...", end=" ")

        statpop, measure_cols, metadata = load_statpop(path, e_min, e_max, n_min, n_max)
        hpi_status = "HPI present" if measure_cols.has_hpi else "HPI absent"

        # Zones Voronoi pour la topologie active de ce millesime (cache par topologie).
        voronoi_zones = get_voronoi_zones_for_year(
            statpop_year=metadata.survey_year,
            gares=gares_coords,
            active_by_horaire=active_by_horaire,
        )
        active_abbrevs = set(voronoi_zones)

        print(
            f"{len(statpop)} hectares dans la bounding box, "
            f"{len(measure_cols.available_sum_cols)} colonnes sources disponibles, {hpi_status}, "
            f"{len(active_abbrevs)} gares actives"
        )

        if measure_cols.missing_required_cols:
            print(
                "    Colonnes sources manquantes ou vides pour certaines variables finales : "
                f"{measure_cols.missing_required_cols}"
            )

        if measure_cols.ignored_cols:
            print(f"    {len(measure_cols.ignored_cols)} colonnes STATPOP ignorees car non utilisees.")

        for _, gare in gares_coords.iterrows():
            abbr = gare["abreviation"]
            if abbr not in voronoi_zones:
                continue  # gare inactive pour ce millesime

            agg = aggregate_for_station(
                statpop=statpop,
                zone=voronoi_zones[abbr],
                measure_cols=measure_cols,
            )

            rows.append(
                {
                    "annee_enquete_statpop": metadata.survey_year,
                    "annee_publication_statpop": metadata.publication_year,
                    "gare_abreviation": abbr,
                    "gare_bpuic": gare["bpuic"],
                    "gare_nom": gare["nom"],
                    "gare_commune": gare["commune"],
                    "gare_km": gare["km"],
                    **agg,
                }
            )

    return finalize_schema(pd.DataFrame(rows))


def build_causal_fact(
    gares: pd.DataFrame,
    statpop_files: list[Path],
    active_by_horaire: dict[str, set[str]],
) -> pd.DataFrame:
    """Construit la branche STATPOP causale refabricable (ADR-076).

    Enchaine : build_fact (Voronoi clippe par topologie active) -> reconstruction
    VVVI H23 (millesimes VVVI_FIX_YEARS) -> finalize_schema -> forward-fill causal
    (millesimes 2021/2023) -> perimetre KEEP_MILLESIMES. Sortie triee par le grain
    (annee_enquete_statpop, gare_abreviation).
    """
    fact = build_fact(gares, statpop_files, active_by_horaire)

    # Reconstruction VVVI (topologie H23) pour les millesimes ou VVVI n'etait pas active.
    vvvi_rows = build_vvvi_rows_h23(gares)
    mask_vvvi = (
        (fact["gare_abreviation"] == "VVVI")
        & (fact["annee_enquete_statpop"].isin(VVVI_FIX_YEARS))
    )
    fact = pd.concat([fact[~mask_vvvi], pd.DataFrame(vvvi_rows)], ignore_index=True)
    fact = finalize_schema(fact)

    # Imputation d'origine : forward-fill causal (LOCF) pour 2021/2023.
    fact = impute_forward_fill_causal(fact)

    # Perimetre consomme par le mapping Z-2 : millesimes 2019-2023.
    fact = fact[fact["annee_enquete_statpop"].isin(KEEP_MILLESIMES)].copy()
    return fact.sort_values(
        ["annee_enquete_statpop", "gare_abreviation"]
    ).reset_index(drop=True)


# -----------------------------------------------------------------------------
# Point d'entree
# -----------------------------------------------------------------------------

def main() -> None:
    print("Chargement de dim_gare...")
    gares = pd.read_parquet(DIM_GARE_PATH)

    missing_coordinates = gares[gares[GARE_E].isna() | gares[GARE_N].isna()]["abreviation"].tolist()
    if missing_coordinates:
        print(
            f"  Attention : {len(missing_coordinates)} gare(s) sans coordonnees LV95, "
            f"ignoree(s) : {missing_coordinates}"
        )

    print(f"  {len(gares)} gares dont {len(gares) - len(missing_coordinates)} avec coordonnees LV95")

    if STATPOP_DOCUMENTATION_PATH.exists():
        print(f"  Documentation OFS : {STATPOP_DOCUMENTATION_PATH}")
    else:
        print(f"  Attention : documentation OFS absente : {STATPOP_DOCUMENTATION_PATH}")

    print("Chargement des horaires officiels (topologie active par annee horaire)...")
    active_by_horaire = load_active_gares_by_horaire()
    for ah, abbrevs in sorted(active_by_horaire.items()):
        print(f"  {ah} : {len(abbrevs)} gares actives — {sorted(abbrevs)}")

    statpop_files = sorted(STATPOP_DIR.glob("STATPOP*.csv"))
    if not statpop_files:
        raise FileNotFoundError(f"Aucun fichier STATPOP*.csv trouve dans {STATPOP_DIR}")

    print(f"\n{len(statpop_files)} fichiers STATPOP | rayon Voronoi clippe {RADIUS_M} m")
    print("Construction de la branche STATPOP causale (forward-fill LOCF, VVVI H23) - ADR-076")
    print()

    fact = build_causal_fact(gares, statpop_files, active_by_horaire)

    na_remaining = fact[[c for c in IMPUTED_COLUMNS if c in fact.columns]].isna().sum().sum()
    print(f"\nTable finale : {len(fact):,} lignes x {len(fact.columns)} colonnes")
    print(f"  Millesimes : {sorted(fact['annee_enquete_statpop'].dropna().unique().tolist())}")
    print(f"  Gares      : {sorted(fact['gare_abreviation'].unique().tolist())}")
    print(f"  NA restants sur les colonnes imputees : {na_remaining}")

    preview_cols = [
        "annee_enquete_statpop",
        "gare_abreviation",
        "gare_nom",
        "statpop_hectares_count",
        "population_500m_total",
        "menages_500m_total",
        "densite_population_500m_km2",
        "part_grands_menages_4p_plus",
        "part_population_25_64_ans",
        "indice_stabilite_residentielle",
        "part_hectares_hpi_non_plausible",
    ]

    print()
    print(fact[[c for c in preview_cols if c in fact.columns]].to_string(index=False))

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nEcriture CSV     -> {OUTPUT_CSV}")
    fact.to_csv(OUTPUT_CSV, index=False)

    print(f"Ecriture Parquet -> {OUTPUT_PARQUET}")
    fact.to_parquet(OUTPUT_PARQUET, index=False)

    print("Termine.")


if __name__ == "__main__":
    main()
