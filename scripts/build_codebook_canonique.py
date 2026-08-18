#!/usr/bin/env python3
"""
build_codebook_canonique.py - dictionnaire des variables du dataset gele ba493568.

Produit un codebook des 209 colonnes de data/processed/ml_dataset.parquet (ba493568),
croise avec la liste des 158 features du modele (outputs/couche2/features_158f_sans_simba.json).
Destine a l'annexe dictionnaire des variables du manuscrit et a solder la dette documentaire
sur le nombre de features (ADR-072). Chaque colonne est classee par statut et rattachee a sa
source amont.

Vocabulaire (voir docs/glossaire.md) :
  - colonnes du dataset          : 209 (ba493568) ;
  - features du modele           : 158 (Enrichi_Seg v1.9, ADR-061 sans SIMBA, ADR-064 sans STATENT) ;
  - colonnes hors matrice        : conservees pour la tracabilite (identifiants/cles) ou retirees
                                    par decision tracee (SIMBA ADR-061, STATENT ADR-064).

Chaque colonne recoit aussi un libelle francais (libelle_fr) et une unite (unite). Ces deux
colonnes sont la SOURCE UNIQUE des libelles d'axes des figures du chantier 1bis
(scripts/figures_style.py les lit : pas de double maintenance). Elles sont produites par
(1) une table d'exceptions revue a la main pour les colonnes effectivement tracees par les
figures (cible, features des correlations affichees, colonnes du notebook d'evaluation) et
(2) des regles famille/suffixe pour le reste. La table d'exceptions est extensible au fil
des volets 3 et 4.

Sortie : outputs/codebook_canonique_ba493568.csv (artefact genere, committe).
Le bilan (1 cible + 158 features + hors-matrice + cibles alternatives = 209, et toutes les
entrees de features_158f retrouvees) est verifie par ASSERTION bloquante, de meme que
l'absence de nom de colonne brut dans les libelles.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEATS = ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"
OUT = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
EXPECTED_HASH8 = "ba493568"

SOURCE_BY_PREFIX = {
    "target_": "APC", "base_": "APC", "histo_": "APC",
    "meteo_": "MeteoSuisse", "event_": "calendriers/evenements", "cal_": "calendrier",
    "ist_": "ISTDATEN", "vmcv_": "ISTDATEN (VMCV)", "simba_": "SIMBA",
    "resa_": "ResSys/CAPRE", "horaire_": "horaires", "id_": "referentiels/identifiants",
}
# Familles dont les valeurs derivent de comptages APC : plage plutot qu'exemple (depot publie).
APC_DERIVED = ("target_", "histo_", "base_")


def sha8(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def source_of(col: str) -> str:
    if col.startswith("spatial_"):
        if "emplois" in col:
            return "STATENT"
        if any(k in col for k in ("segment", "troncon", "denivele", "_km", "ordre", "bpuic")):
            return "topologie/referentiels"
        return "STATPOP"
    for pref, src in SOURCE_BY_PREFIX.items():
        if col.startswith(pref):
            return src
    return "autre"


# ---------------------------------------------------------------------------
# Libelles francais + unites (annexe dictionnaire des variables + source unique
# des libelles d'axes de figures_style.py). Deux niveaux :
#   (1) LIBELLE_EXCEPTIONS : revue humaine, colonnes tracees par les figures ;
#   (2) libelle_unite()    : regles famille/suffixe pour toutes les autres.
# ---------------------------------------------------------------------------

# (1) Exceptions revues a la main. Format : colonne -> (libelle_fr, unite).
# Extensible au fil des volets 3 (correlations affichees) et 4 (evaluation).
LIBELLE_EXCEPTIONS = {
    "target_voyageurs_2eme_classe": ("Charge de 2e classe", "voyageurs"),
    "target_voyageurs_1ere_classe": ("Charge de 1re classe", "voyageurs"),
    "target_voyageurs_total": ("Charge totale", "voyageurs"),
    "spatial_segment": ("Segment de ligne", ""),
    "spatial_distance_km": ("Longueur du tronçon", "km"),
    "spatial_denivele_troncon_m": ("Dénivelé du tronçon", "m"),
    "spatial_gare_depart_pop_500m_total": ("Population dans 500 m (gare de départ)", "habitants"),
    "spatial_gare_arrivee_pop_500m_total": ("Population dans 500 m (gare d'arrivée)", "habitants"),
    "base_date": ("Date de circulation", ""),
    "base_sens": ("Sens de circulation", ""),
    "cal_type_jour": ("Type de jour", ""),
    "cal_type_jour_3classes": ("Type de jour (3 classes)", ""),
    "cal_is_weekend": ("Week-end", "indicatrice"),
    "ist_headway_avant_min": ("Intervalle au train précédent (amont)", "minutes"),
    "ist_headway_apres_min": ("Intervalle au train suivant (aval)", "minutes"),
    "resa_pax_2c_J_minus_1": ("Voyageurs réservés 2e classe (J-1)", "voyageurs"),
    "resa_n_dossiers_J_minus_1": ("Dossiers de réservation (J-1)", "nombre"),
    "resa_has_resa_J_minus_1": ("Présence d'une réservation (J-1)", "indicatrice"),
    # Cutoff mensuel (ADR-062/066), PAS J-2 : la valeur consolidée provient du dernier
    # rapport APC mensuel publié (mois M disponible le 3 de M+1) ; l'ancien libellé « J-2 »
    # décrivait le design pré-ADR-062. Le suffixe de colonne `lag2` est un vestige de nom.
    "histo_voyageurs_2eme_classe_lag2":
        ("Charge de 2e classe, dernière occ. consolidée (cutoff mensuel)", "voyageurs"),
    "histo_voyageurs_2eme_classe_win7_mean":
        ("Charge de 2e classe, moyenne 7 occ. consolidées", "voyageurs"),
    "histo_voyageurs_2eme_classe_win7_max":
        ("Charge de 2e classe, maximum 7 occ. consolidées", "voyageurs"),
    "histo_voyageurs_2eme_classe_win7_n_surcharges":
        ("Surcharges sur 7 occ. consolidées", "nombre"),
    "event_is_vacances_vaud": ("Vacances scolaires vaudoises", "indicatrice"),
    "event_is_ferie_vaud": ("Jour férié vaudois", "indicatrice"),
    "event_is_ski_ouvert": ("Domaine skiable ouvert", "indicatrice"),
}

# (2) Bases par famille (accentuees, pour l'annexe dictionnaire).
_FAMILLE_BASE = {
    "base_": "Desserte", "cal_": "Calendrier", "event_": "Événement",
    "histo_": "Historique de charge", "horaire_": "Horaire",
    "id_": "Identifiant", "ist_": "Régularité et correspondances",
    "meteo_": "Météo", "resa_": "Réservation de groupe",
    "simba_": "Structure tarifaire", "spatial_": "Contexte spatial",
    "target_": "Cible", "vmcv_": "Concurrence modale",
}

# Unites par motif dans le nom de colonne (premier motif rencontre).
_UNITE_MOTIF = [
    ("temperature", "°C"), ("precip", "mm"), ("ensol", "min"),
    ("vent", "km/h"), ("rayon_global", "W/m2"), ("retard", "secondes"),
    ("headway", "minutes"), ("_km", "km"), ("denivele", "m"),
    ("pop_500m_total", "habitants"), ("menages_500m_total", "ménages"),
    ("emplois_500m", "emplois"), ("neige", "indicatrice"),
    ("minute_du_jour", "minutes"),
]

# Remplacements de tokens (ordre significatif : composes d'abord).
_REMPLACEMENTS = [
    ("gare_depart", "gare de départ"), ("gare_arrivee", "gare d'arrivée"),
    ("source_depart", "source au départ"), ("source_arrivee", "source à l'arrivée"),
    ("1ere_classe", "1re classe"), ("2eme_classe", "2e classe"),
    ("J_minus_1", "J-1"), ("j_moins_1", "J-1"), ("j_plus_1", "J+1"),
    ("win7", "fenêtre 7 occ."), ("lag2", "dernière occ. consolidée"),
    ("_5occ", " (5 occ.)"), ("_20occ", " (20 occ.)"),
    ("pct", "part"), ("moy", "moyenne"), ("std", "écart-type"),
]

# Prefixes de familles : sert a detecter une fuite de nom brut dans un libelle.
_RAW_PREFIX = re.compile(
    r"(?:^|_)(?:target|base|histo|meteo|ist|vmcv|spatial|resa|simba|horaire|event|cal|id)_"
)


def libelle_unite(col: str, famille: str) -> tuple:
    """Renvoie (libelle_fr, unite) pour une colonne. Exceptions prioritaires."""
    if col in LIBELLE_EXCEPTIONS:
        return LIBELLE_EXCEPTIONS[col]
    base = _FAMILLE_BASE.get(famille, famille.rstrip("_"))
    reste = col[len(famille):] if col.startswith(famille) else col
    texte = reste
    for a, b in _REMPLACEMENTS:
        texte = texte.replace(a, b)
    texte = texte.replace("_", " ").strip()
    libelle = base if not texte else f"{base} : {texte}"
    unite = ""
    # Motif cherche dans le reste (hors prefixe famille) pour eviter les faux
    # positifs de sous-chaine, ex. "vent" dans "event_".
    for motif, u in _UNITE_MOTIF:
        if motif in reste:
            unite = u
            break
    if unite == "" and "part_" in reste:
        unite = "proportion"
    elif unite == "" and (reste.startswith("is_") or "_is_" in reste):
        unite = "indicatrice"
    return (libelle, unite)


def main() -> int:
    got = sha8(ML)
    if got != EXPECTED_HASH8:
        raise SystemExit(f"ARRET : ml_dataset.parquet = {got}, attendu {EXPECTED_HASH8}.")
    df = pd.read_parquet(ML)
    feats = json.load(open(FEATS))
    feats = feats if isinstance(feats, list) else feats.get("features", feats)
    fset = set(feats)

    rows = []
    for col in df.columns:
        if col == "target_voyageurs_2eme_classe":
            statut, adr = "cible", ""
        elif col.startswith("target_"):
            statut, adr = "cible_alternative", ""
        elif col in fset:
            statut, adr = "feature_modele", ""
        elif col.startswith("simba_"):
            statut, adr = "hors_matrice_retrait_trace", "ADR-061"
        elif "emplois" in col:
            statut, adr = "hors_matrice_retrait_trace", "ADR-064"
        else:
            statut, adr = "hors_matrice_tracabilite", ""
        s = df[col]
        famille = (col.split("_")[0] + "_") if "_" in col else col
        if pd.api.types.is_numeric_dtype(s):
            plage = f"[{s.min()}, {s.max()}]"
        else:
            plage = f"{s.nunique()} modalites"
        libelle, unite = libelle_unite(col, famille)
        rows.append({
            "colonne": col,
            "famille": famille,
            "source": source_of(col),
            "dtype": str(s.dtype),
            "statut": statut,
            "dans_158_features": col in fset,
            "reference_adr": adr,
            "taux_nan_pct": round(100 * float(s.isna().mean()), 3),
            "plage_ou_modalites": plage,
            "libelle_fr": libelle,
            "unite": unite,
        })
    cb = pd.DataFrame(rows)

    # --- Assertions bloquantes (bilan) ---
    n_cible = int((cb.statut == "cible").sum())
    feat_cols = set(cb.loc[cb.statut == "feature_modele", "colonne"])
    assert n_cible == 1, f"cible = {n_cible}, attendu 1"
    assert feat_cols == fset, (
        f"feature_modele != features_158f : manquantes {sorted(fset - feat_cols)[:5]}, "
        f"en trop {sorted(feat_cols - fset)[:5]}"
    )
    assert len(feat_cols) == 158, f"features = {len(feat_cols)}, attendu 158"
    assert len(cb) == 209, f"colonnes = {len(cb)}, attendu 209"

    # Libelles : non vides et sans fuite de nom de colonne brut (underscore ou prefixe famille).
    vides = cb.loc[cb.libelle_fr.str.len() == 0, "colonne"].tolist()
    assert not vides, f"libelle_fr vide : {vides[:5]}"
    fuites = cb.loc[
        cb.libelle_fr.str.contains("_", regex=False)
        | cb.libelle_fr.str.contains(_RAW_PREFIX)
        | (cb.libelle_fr == cb.colonne),
        "colonne",
    ].tolist()
    assert not fuites, f"libelle_fr contient un nom brut : {fuites[:5]}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cb.to_csv(OUT, index=False)
    print(f"[OK] {OUT}  ({len(cb)} colonnes)")
    print(cb.statut.value_counts().to_string())
    print(f"bilan : 1 cible + 158 features + "
          f"{int((cb.statut=='hors_matrice_retrait_trace').sum())} retrait_trace + "
          f"{int((cb.statut=='hors_matrice_tracabilite').sum())} tracabilite + "
          f"{int((cb.statut=='cible_alternative').sum())} cible_alt = {len(cb)}")
    print(f"SHA256[:8] codebook = {sha8(OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
