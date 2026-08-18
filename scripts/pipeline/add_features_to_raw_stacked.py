"""
add_features_to_raw_stacked.py
================================
Feature construction terminal : calcule toutes les variables dérivées
sur stage_07 et produit stage_08 (dernière étape avant build_ml_dataset).

Variables créées
----------------
  cal_depart_minute_du_jour     minutes depuis minuit au départ (0-1439)
  cal_arrivee_minute_du_jour    minutes depuis minuit à l'arrivée (0-1439)
  target_voyageurs_total        somme 1ère + 2ème — variable de contrôle qualité
  base_offre_total              somme offre 1ère + 2ème (NaN si les deux manquent)

  Note : spatial_gare_depart_ordre, spatial_gare_arrivee_ordre et spatial_segment
  sont calculés en amont par add_spatial_to_raw_stacked.py (stage_03e) et
  arrivent par passthrough depuis stage_07.

  Features headway (cf. ADR-018) :
  ist_headway_avant_min                minutes depuis le train précédent (horaire théorique)
  ist_headway_apres_min                minutes jusqu'au train suivant (horaire théorique)
  ist_headway_avant_is_first_of_day    1 si premier train de la journée sur ce tronçon × sens
  ist_headway_apres_is_last_of_day     1 si dernier train de la journée sur ce tronçon × sens

  Features historiques (cf. ADR-008, ADR-009, ADR-037) :
  Pour X ∈ {1ere_classe, 2eme_classe, total} :
  histo_voyageurs_{X}_lag2              valeur de la dernière occurrence consolidée
  histo_voyageurs_{X}_win7_mean         moyenne sur les 7 dernières occurrences consolidées
  histo_voyageurs_{X}_win7_median       médiane sur même fenêtre
  histo_voyageurs_{X}_win7_max          max sur même fenêtre
  histo_voyageurs_{X}_win7_std          écart-type sur même fenêtre
  histo_voyageurs_{X}_win7_n_surcharges  compte d'occurrences avec valeur > 63
                                          (calculé uniquement pour 2eme_classe)

Conventions méthodologiques
---------------------------
- Grain de groupement créneau (ADR-044, 2026-06-05) :
    base_sens × creneau_anchor_30 × cal_type_jour_3classes
  Remplace ADR-037 (annee_horaire × troncon_tgl × service_id_complet × type_jour).
  Cf. docs/adr/ADR-044_creneau_avec_sens.md.
  Avantages :
    • base_sens sépare VV→Pléiades et Pléiades→VV (régimes opposés).
    • creneau_anchor_30 permet l'historique cross-années : un service H25
      renuméroté hérite de l'historique H22-H24 du service H22-H24 le plus
      proche en temps (même sens, même type_jour, ±30 min).
    • horaire_troncon_tgl retiré (constante 0, sans valeur discriminante).
    • horaire_annee_horaire retiré (historique cross-années voulu).

- Décalage opérationnel des features historiques (ADR-062, corrige ADR-008 pour les
  APC) : la décision UM se prend à J-1, mais les comptages APC ne sont consolidés que
  dans le rapport mensuel HOP-REP-WEB (mois M disponible le 3 de M+1). Les features
  historiques utilisent donc la dernière occurrence du même groupe dont la date est
  ≤ cutoff_mensuel(base_date) (cutoff composé T-1 + ingestion, `_cutoff_mensuel_seuils`,
  ADR-066), et NON un lag J-2 (qui mobiliserait des comptages non encore publiés). Le
  shift est calculé dynamiquement par np.searchsorted ; la garde
  `_assert_histo_conformite_adr_cf18` échoue si le délai retombe à ~2 j. Le suffixe de
  colonne `lag2` est un vestige de nom (design ADR-008), pas la sémantique courante.

- Anti-fuite créneau : les anchors sont construits depuis ANNEES_ANCRES uniquement
  (H22-H24), jamais depuis le jeu de test H25. La série temporelle cross-années
  respecte le cutoff mensuel par construction (searchsorted sur les dates triées).

- observed=True : cal_type_jour_3classes et base_sens sont des colonnes
  category/string ; groupby pandas utilise observed=True pour éviter les lignes
  fantômes.

Note : horaire_service_id_complet est construit en début de main() AVANT
creneau_anchor_30 car il fournit les temps d'origine nécessaires à l'ancrage.
La colonne creneau_anchor_30 est construite AVANT add_derived_features.

Sources
-------
- data/processed/stage_07_istdaten.parquet
- data/processed/sources/dim_headway.parquet

Sortie
------
- data/processed/stage_08_features.parquet

CSV optionnel : ``WRITE_CSV=1 python3 scripts/pipeline/add_features_to_raw_stacked.py``
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import DIM_HEADWAY, STAGE_07_ISTDATEN, STAGE_08_FEATURES  # noqa: E402
from pipeline.io import read_stage, write_stage  # noqa: E402

# ADR-008 (lag opérationnel J-2) : valeur historique conservée pour mémoire. Elle n'est
# PLUS appliquée aux features historiques APC : ADR-062 lui a substitué un cutoff mensuel
# composé (`_cutoff_mensuel_seuils`), les comptages APC n'étant publiés qu'au rapport
# mensuel. Constante vestigiale : non référencée par la logique de build (cf. docstring).
LAG_OPERATIONNEL_JOURS = 2  # vestige ADR-008, superseded by monthly cutoff (ADR-062)

# Années de référence pour la construction des anchors créneau.
# Restreint aux années d'entraînement (ADR-038 : H22-H24) pour isoler H25 (test OOT).
ANNEES_ANCRES: list[str] = ["H22", "H23", "H24"]

# Demi-largeur de la fenêtre de proximité temporelle pour le créneau (ADR-044).
CRENEAU_LARGEUR_MIN: int = 30

# Grain de groupement créneau (ADR-044, 2026-06-05) :
# - base_sens : sépare VV→Pléiades et Pléiades→VV (régimes de charge opposés).
# - creneau_anchor_30 : temps d'origine (minutes) du service H22-H24 le plus
#   proche à ±CRENEAU_LARGEUR_MIN min (même sens, même type_jour). Permet
#   l'historique cross-années pour les services renumérotés lors de refontes.
# - cal_type_jour_3classes : évite le mélange ouvrable/samedi/dimanche_ferie.
# NB : horaire_annee_horaire et horaire_troncon_tgl sont intentionnellement absents.
# Cf. docs/adr/ADR-044_creneau_avec_sens.md
GROUP_KEYS = [
    "base_sens",
    "creneau_anchor_30",
    "cal_type_jour_3classes",
    "id_gare_depart_bpuic",
    "id_gare_arrivee_bpuic",
]
# ADR-062 §2 : le tronçon (id_gare_depart_bpuic, id_gare_arrivee_bpuic) fait partie
# de la clé de groupement histo_*. Sans lui, la moyenne s'effectuait sur tous les
# tronçons d'une même course (profils de charge radicalement différents), lissant
# l'historique. La clé tronçon supprime ce lissage. Le tronçon est ajouté à la CLÉ
# de calcul, pas comme feature supplémentaire (total features inchangé).

DATE_COL = "base_date"

# Colonnes sources pour les features historiques
LAG_SOURCE_COLS = [
    "target_voyageurs_1ere_classe",
    "target_voyageurs_2eme_classe",
    "target_voyageurs_total",
]

# Suffixes des features dérivées
LAG_POINT_SUFFIX = "lag2"
WIN7_MEAN_SUFFIX = "win7_mean"
WIN7_MEDIAN_SUFFIX = "win7_median"
WIN7_MAX_SUFFIX = "win7_max"
WIN7_STD_SUFFIX = "win7_std"
WIN7_NSURCHARGES_SUFFIX = "win7_n_surcharges"

# Seuil de surcharge = places assises 2ème classe SURF 7500 = 63.
# Spec MOB ABeh 7501-7508 (colonne "Places assises 2ème"), validé Responsable des Actifs Voyageurs, MOB
# (Responsable des Actifs Voyageurs, 2026-06-09). Source versionnée :
# data/external/spec_materiel/ (spécification interne du matériel roulant voyageurs) +
# vehicules_portes_7500.png. Réconciliation : 63 assises + 31 strapontins = 94 (offre APC).
# Le 94 de l'offre APC inclut les 31 strapontins ; ceux-ci ne sont pas mobilisables
# comme places assises (usage multi : vélos, skis, bagages — spec active + entretien P01).
# Note : le fichier Excel contient une coquille (32 strapontins au lieu de 31) ;
# le schéma véhicule et les données APC (offre − voyageurs = 31 quand voyageurs = 63)
# confirment 31. Cf. ADR-060 pour la traçabilité complète du changement 94 → 63.
SEUIL_UM_2EME = 63

HISTO_SUFFIXES = [
    LAG_POINT_SUFFIX,
    WIN7_MEAN_SUFFIX,
    WIN7_MEDIAN_SUFFIX,
    WIN7_MAX_SUFFIX,
    WIN7_STD_SUFFIX,
    WIN7_NSURCHARGES_SUFFIX,
]


def _cutoff_mensuel_seuils(dates_arr: np.ndarray) -> np.ndarray:
    """Calcule le seuil de consolidation APC par cutoff mensuel composé (ADR-066).

    Deux délais se composent (corrige ADR-062 qui calculait sur base_date=T au
    seuil du 3, sans décision T-1 ni ingestion) :
      (a) Décision à T-1 : la décision UM se prend la veille du trajet. Le cutoff
          se base donc sur la date de DÉCISION D_dec = base_date − 1 jour, pas sur
          la date du trajet T.
      (b) Ingestion APC d'un jour : les comptages d'un mois M sont publiés sur
          PrepWeb (HOP-REP-WEB) le 3 du mois M+1, mais ne sont ingérés/utilisables
          que le lendemain — le 4 de M+1.

    Règle composée : un mois M est utilisable pour une décision à D_dec si
        (3 de M+1) + 1 jour d'ingestion <= D_dec, c'est-à-dire (4 de M+1) <= D_dec.

    Règle conditionnelle à la date (PAS un lag fixe), appliquée sur D_dec = T−1 :
        - le dernier mois utilisable à D_dec est (mois de D_dec − 1) si D_dec.day >= 4,
          sinon (mois de D_dec − 2) — car le mois précédent n'est ingéré que le 4.
        - le seuil est le dernier jour de ce mois utilisable.

    Exemples (ADR-066) :
        trajet 4 juillet  -> décision 3 juillet (jour 3 < 4) -> juin pas encore
                             utilisable le 3 -> dernier mois = mai  -> seuil 31 mai
        trajet 5 juillet  -> décision 4 juillet (jour 4 >= 4) -> juin utilisable
                             -> dernier mois = juin -> seuil 30 juin
    """
    d_dec = pd.DatetimeIndex(dates_arr) - pd.Timedelta(days=1)   # (a) décision à T-1
    back = np.where(d_dec.day >= 4, 1, 2).astype("int64")        # (b) publié le 3 + 1j ingestion -> utilisable le 4
    month_start = d_dec.values.astype("datetime64[M]")           # 1er du mois de D_dec
    cutoff_month = month_start - back.astype("timedelta64[M]")
    next_month = cutoff_month + np.timedelta64(1, "M")
    cutoff = next_month.astype("datetime64[D]") - np.timedelta64(1, "D")  # dernier jour du mois utilisable
    return cutoff.astype("datetime64[ns]")


def _assert_histo_conformite_adr_cf18(df: "pd.DataFrame") -> None:
    """Garde-fou ADR-062 : échoue si un build réintroduit le lag J-2 ou la clé 3-termes.

    Cet écart ADR/données s'est produit une fois (le code inc1 cutoff mensuel + clé tronçon
    n'avait jamais été commité, le pipeline canonique appliquait encore J-2 + clé 3-termes).
    Cette assertion empêche toute régression silencieuse.
    """
    mn = _feature_col("target_voyageurs_2eme_classe", WIN7_MEAN_SUFFIX)
    lag2 = _feature_col("target_voyageurs_2eme_classe", LAG_POINT_SUFFIX)

    # (1) Clé tronçon (ADR-062 §2) : pour une même course (date×train×sens), les tronçons
    #     doivent avoir des valeurs histo DIFFÉRENTES. Sous clé 3-termes, elles seraient identiques.
    g = df.groupby(["base_date", "horaire_numero_train", "base_sens"], observed=True)
    n_troncons = g["id_gare_depart_bpuic"].nunique()
    n_distinct = g[mn].nunique(dropna=False)
    multi = n_troncons[n_troncons > 1].index
    sel = n_distinct[n_distinct.index.isin(multi)]
    frac_varie = float((sel > 1).mean()) if len(sel) else 0.0
    if frac_varie < 0.5:
        raise RuntimeError(
            f"ADR-062 violé (clé tronçon) : histo_* varie selon le tronçon dans seulement "
            f"{frac_varie:.1%} des courses multi-tronçons (attendu > 50 %, ~98 % nominal). "
            f"Régression probable vers la clé 3-termes — vérifier GROUP_KEYS."
        )

    # (2) Cutoff mensuel composé (ADR-066, corrige ADR-062 §1) : le délai médian entre la
    #     1ère occurrence d'un groupe et son 1er lag2 valide doit refléter le cutoff mensuel
    #     (~3 semaines, légèrement plus élevé sous la règle composée décision T-1 + ingestion),
    #     PAS un lag J-2 (~2 j).
    def _first_gap(grp):
        grp = grp.sort_values(DATE_COL)
        fd = grp[DATE_COL].iloc[0]
        valid = grp.loc[grp[lag2].notna(), DATE_COL]
        return (valid.iloc[0] - fd).days if len(valid) else np.nan

    gaps = df.groupby(GROUP_KEYS, observed=True).apply(_first_gap)
    med_gap = float(np.nanmedian(gaps.values))
    if med_gap < 10:
        raise RuntimeError(
            f"ADR-062 violé (cutoff mensuel) : délai médian 1ère occurrence -> 1er lag2 valide "
            f"= {med_gap:.0f} j (attendu >= 10 j sous cutoff mensuel, ~21 j nominal ; "
            f"un lag J-2 donnerait ~2 j). Régression probable vers le lag J-2 — vérifier _cutoff_mensuel_seuils."
        )

    print(
        f"  [ADR-062] Conformité histo_* OK : tronçon dans la clé "
        f"({frac_varie:.1%} de variation inter-tronçon), cutoff mensuel "
        f"(délai médian 1ère occ. -> 1er lag2 = {med_gap:.0f} j)."
    )


def _feature_col(source: str, suffix: str) -> str:
    """Construit le nom de la colonne histo_ à partir de la source target_ et d'un suffixe.

    Exemples :
        _feature_col("target_voyageurs_2eme_classe", "lag2")
            -> "histo_voyageurs_2eme_classe_lag2"
        _feature_col("target_voyageurs_2eme_classe", "win7_mean")
            -> "histo_voyageurs_2eme_classe_win7_mean"
    """
    base = source.replace("target_", "")
    return f"histo_{base}_{suffix}"


TIME_COLS = [
    "cal_depart_minute_du_jour",
    "cal_arrivee_minute_du_jour",
]

# spatial_gare_depart_ordre, spatial_gare_arrivee_ordre et spatial_segment
# sont calculés par add_spatial_to_raw_stacked.py (stage_03e) — passthrough ici.

# Note : ni horaire_service_id_complet ni creneau_anchor_30 ne sont dans DERIVED_COLS :
# les deux sont construits en amont dans main() avant add_derived_features, et font
# partie de GROUP_KEYS. Les inclure dans DERIVED_COLS les ferait supprimer au début
# de add_derived_features, puis ils manqueraient pour le calcul du grain.
# win7_n_surcharges est calculé uniquement pour target_voyageurs_2eme_classe (ADR-010).
# Les sources 1ere_classe et total ne génèrent pas ce suffixe : 3×6 − 2 = 16 features.
DERIVED_COLS = (
    TIME_COLS
    + ["target_voyageurs_total", "base_offre_total"]
    + [
        _feature_col(c, s)
        for c in LAG_SOURCE_COLS
        for s in HISTO_SUFFIXES
        if not (s == WIN7_NSURCHARGES_SUFFIX and c != "target_voyageurs_2eme_classe")
    ]
)


def _ajouter_service_id_complet(df: pd.DataFrame) -> pd.DataFrame:
    """Construit horaire_service_id_complet depuis numero_train + heure d'origine.

    Pour chaque (base_date, horaire_numero_train), identifie le plus tôt
    base_depart_datetime (= premier arrêt du train ce jour) et construit
    un identifiant composite stable pour tous les tronçons.
    Fallback : «{numero}_NA» si aucun arrêt n'a de datetime valide.
    """
    origines = (
        df.groupby(["base_date", "horaire_numero_train"], as_index=False)
        .agg(heure_origine=("base_depart_datetime", "min"))
    )
    heure_str = origines["heure_origine"].dt.strftime("%Hh%M").fillna("NA")
    origines["horaire_service_id_complet"] = (
        origines["horaire_numero_train"].astype(str) + "_" + heure_str
    )
    return df.merge(
        origines[["base_date", "horaire_numero_train", "horaire_service_id_complet"]],
        on=["base_date", "horaire_numero_train"],
        how="left",
    )


def _ajouter_creneau_anchor_30(df: pd.DataFrame) -> pd.DataFrame:
    """Construit creneau_anchor_30 : temps d'ancrage créneau ±CRENEAU_LARGEUR_MIN min.

    Pour chaque ligne, extrait le temps d'origine depuis horaire_service_id_complet
    (format {num}_{HHhMM}) puis assigne le service H22-H24 le plus proche à
    ±CRENEAU_LARGEUR_MIN min sur le même (base_sens, cal_type_jour_3classes).

    Les anchors sont construits depuis ANNEES_ANCRES (H22-H24) uniquement
    pour ne pas contaminer la clé de groupement avec des données H25 (test OOT).
    Valeur NaN si aucun anchor H22-H24 n'est trouvé à ±CRENEAU_LARGEUR_MIN min
    (services nuit sans équivalent → histo_* NaN structurel, cf. ADR-044 §services nuit).

    Args:
        df: DataFrame contenant horaire_service_id_complet, horaire_annee_horaire,
            base_sens et cal_type_jour_3classes.

    Returns:
        DataFrame avec colonne creneau_anchor_30 ajoutée (float64, minutes depuis minuit).
    """
    # 1. Temps d'origine en minutes depuis minuit (depuis le format {num}_{HHhMM})
    _pat = re.compile(r"_(\d{2})h(\d{2})$")

    def _sid_to_mins(sid: str) -> float:
        m = _pat.search(str(sid))
        return float(int(m.group(1)) * 60 + int(m.group(2))) if m else float("nan")

    unique_sids = df["horaire_service_id_complet"].unique()
    mins_map = {s: _sid_to_mins(s) for s in unique_sids}
    df = df.copy()
    df["_mins_origine"] = df["horaire_service_id_complet"].map(mins_map).astype("float64")

    # 2. Table d'anchors : temps uniques par (base_sens, cal_type_jour_3classes) en H22-H24
    ancres = df[df["horaire_annee_horaire"].isin(ANNEES_ANCRES)]
    anchors_by_key: dict[tuple[str, str], np.ndarray] = {}
    for (sens, tj), grp in ancres.groupby(
        ["base_sens", "cal_type_jour_3classes"], observed=True
    ):
        times = np.sort(grp["_mins_origine"].dropna().unique())
        if len(times) > 0:
            anchors_by_key[(str(sens), str(tj))] = times

    # 3. Assignation vectorisée de l'anchor le plus proche
    creneau = np.full(len(df), float("nan"))
    sens_arr = df["base_sens"].astype(str).values
    tj_arr   = df["cal_type_jour_3classes"].astype(str).values
    mins_arr = df["_mins_origine"].values

    for (sens, tj), anc in anchors_by_key.items():
        mask = (sens_arr == sens) & (tj_arr == tj) & (~np.isnan(mins_arr))
        if not mask.any():
            continue
        m_sub = mins_arr[mask].astype(float)
        idx = np.clip(np.searchsorted(anc, m_sub, side="left"), 0, len(anc) - 1)
        ip  = np.maximum(idx - 1, 0)
        dc  = np.abs(anc[idx] - m_sub)
        dp  = np.abs(anc[ip]  - m_sub)
        best = np.where(dp < dc, ip, idx)
        best_dist = np.minimum(dc, dp)
        creneau[mask] = np.where(best_dist <= CRENEAU_LARGEUR_MIN, anc[best], float("nan"))

    df["creneau_anchor_30"] = creneau
    df = df.drop(columns=["_mins_origine"])

    n_total   = len(df)
    n_nan     = int(np.isnan(creneau).sum())
    n_ancres  = sum(len(v) for v in anchors_by_key.values())
    pct_cov   = 100.0 * (n_total - n_nan) / n_total
    print(
        f"  creneau_anchor_30 : {len(anchors_by_key)} groupes (sens×type_jour), "
        f"{n_ancres} anchors H22-H24, couverture={pct_cov:.1f}% ({n_nan} NaN structurels)"
    )
    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    # Supprimer uniquement les colonnes dérivées (DERIVED_COLS), pas horaire_service_id_complet
    # qui est désormais un GROUP_KEY construit en amont dans main().
    result = df.drop(columns=[c for c in DERIVED_COLS if c in df.columns]).copy()

    # --- Minutes depuis minuit (cal_heure et cal_minute existent depuis stack_raw_csv) ---

    h_dep = pd.to_numeric(result["cal_heure_depart"], errors="coerce")
    m_dep = pd.to_numeric(result["cal_minute_depart"], errors="coerce")
    h_arr = pd.to_numeric(result["cal_heure_arrivee"], errors="coerce")
    m_arr = pd.to_numeric(result["cal_minute_arrivee"], errors="coerce")

    depart_min = (h_dep * 60 + m_dep).astype("Int64")
    arrivee_min = (h_arr * 60 + m_arr).astype("Int64")

    insert_after = result.columns.get_loc("cal_minute_arrivee") + 1
    result.insert(insert_after, "cal_arrivee_minute_du_jour", arrivee_min)
    result.insert(insert_after, "cal_depart_minute_du_jour", depart_min)

    # --- Variables simples ---

    # Garde défensive (audit NaN 2026-06-07) : détecte toute valeur non-numérique
    # qui serait silencieusement convertie en 0 par errors="coerce" + fillna(0).
    # Sur données propres : aucun effet (compte = 0, aucune erreur, hash inchangé).
    # Sur données corrompues : arrêt immédiat — un faux zéro sur la cible empoisonne
    # l'entraînement sans laisser de trace visible.
    _v1_raw = result["target_voyageurs_1ere_classe"]
    _v2_raw = result["target_voyageurs_2eme_classe"]
    _v1_coerced = pd.to_numeric(_v1_raw, errors="coerce")
    _v2_coerced = pd.to_numeric(_v2_raw, errors="coerce")
    _mask_corrupt_v1 = _v1_raw.notna() & _v1_coerced.isna()
    _mask_corrupt_v2 = _v2_raw.notna() & _v2_coerced.isna()
    _n_corrupt = int(_mask_corrupt_v1.sum()) + int(_mask_corrupt_v2.sum())
    if _n_corrupt > 0:
        raise ValueError(
            f"{_n_corrupt} valeur(s) non-numérique(s) dans les comptages voyageurs — "
            f"corruption silencieuse de la cible inacceptable. "
            f"1ère classe ({int(_mask_corrupt_v1.sum())}) : "
            f"{_v1_raw[_mask_corrupt_v1].head(5).tolist()} | "
            f"2ème classe ({int(_mask_corrupt_v2.sum())}) : "
            f"{_v2_raw[_mask_corrupt_v2].head(5).tolist()}"
        )

    v1 = _v1_coerced.fillna(0)
    v2 = _v2_coerced.fillna(0)
    result["target_voyageurs_total"] = (v1 + v2).astype("float64")

    o1 = pd.to_numeric(result["base_offre_1ere_classe"], errors="coerce")
    o2 = pd.to_numeric(result["base_offre_2eme_classe"], errors="coerce")
    result["base_offre_total"] = (
        pd.concat([o1, o2], axis=1).sum(axis=1, min_count=1).astype("float64")
    )

    # --- Features historiques (cutoff mensuel + clé tronçon, ADR-062) ---
    #
    # Grain : GROUP_KEYS = [base_sens, creneau_anchor_30, cal_type_jour_3classes,
    #                       id_gare_depart_bpuic, id_gare_arrivee_bpuic]  (clé tronçon, ADR-062 §2)
    #
    # Pour chaque ligne de date D, le lag est la valeur de la dernière occurrence
    # du MÊME groupe dont la date est ≤ cutoff_mensuel(D) (ADR-062 §1) :
    # les comptages APC ne sont consolidés que dans le rapport mensuel HOP-REP-WEB
    # (mois M disponible le 3 de M+1), un lag J-2 utiliserait des comptages non publiés.
    # La série est cross-années (horaire_annee_horaire absent des GROUP_KEYS) :
    # un service H25 dans un créneau×tronçon hérite de l'historique H22-H24.
    # La fenêtre win7 couvre les 7 occurrences du même groupe terminant à ce lag.
    #
    # Implémentation : np.searchsorted sur les dates triées par groupe.
    # observed=True : évite les lignes fantômes pour les colonnes category.
    # Cf. ADR-062 (corrige le lag J-2 d'ADR-008 pour les APC), ADR-044.

    # 1. Agrégation journalière par groupe + date
    tmp = result[GROUP_KEYS + [DATE_COL]].copy()
    tmp[DATE_COL] = pd.to_datetime(tmp[DATE_COL], errors="coerce")
    for col in LAG_SOURCE_COLS:
        tmp[col] = pd.to_numeric(result[col], errors="coerce")

    daily = (
        tmp.groupby(GROUP_KEYS + [DATE_COL], dropna=False, sort=True, observed=True)[LAG_SOURCE_COLS]
        .mean()
        .reset_index()
        .sort_values(GROUP_KEYS + [DATE_COL])
        .reset_index(drop=True)
    )

    # 2. Calcul des features par groupe avec shift dynamique (searchsorted)
    all_groups_results = []

    for _group_vals, group_df in daily.groupby(GROUP_KEYS, sort=False, dropna=False, observed=True):
        group_df = group_df.sort_values(DATE_COL).reset_index(drop=True)
        dates_arr = group_df[DATE_COL].values  # datetime64[ns]
        seuils_arr = _cutoff_mensuel_seuils(dates_arr)  # ADR-066 (cutoff composé T-1 + ingestion, PAS J-2)

        # Pour chaque ligne i, trouver le dernier indice j tel que dates_arr[j] <= seuils_arr[i]
        # = searchsorted(right) - 1. Vaut -1 si aucune occurrence consolidée n'existe.
        idx_consol = np.searchsorted(dates_arr, seuils_arr, side="right") - 1

        for col in LAG_SOURCE_COLS:
            vals = group_df[col].values.astype("float64")
            base = col.replace("target_", "")
            n = len(group_df)

            # Feature ponctuelle : valeur à idx_consol
            lag_vals = np.where(
                idx_consol >= 0,
                vals[np.maximum(idx_consol, 0)],
                np.nan,
            )
            # Propager le NaN d'origine de vals (val NaN à l'indice consolidé → lag NaN)
            has_consol = idx_consol >= 0
            lag_vals = np.where(
                has_consol & np.isnan(vals[np.where(has_consol, idx_consol, 0)]),
                np.nan,
                lag_vals,
            )
            group_df[_feature_col(col, LAG_POINT_SUFFIX)] = lag_vals.astype("float64")

            # Features de fenêtre glissante : 7 occurrences terminant à idx_consol
            for stat, suffix in [
                ("mean",   WIN7_MEAN_SUFFIX),
                ("median", WIN7_MEDIAN_SUFFIX),
                ("max",    WIN7_MAX_SUFFIX),
                ("std",    WIN7_STD_SUFFIX),
            ]:
                stat_vals = np.full(n, np.nan)
                for i in range(n):
                    if idx_consol[i] < 0:
                        continue
                    start = max(0, idx_consol[i] - 6)
                    end = idx_consol[i] + 1
                    win = vals[start:end]
                    win = win[~np.isnan(win)]
                    if len(win) == 0:
                        continue
                    if stat == "mean":
                        stat_vals[i] = np.mean(win)
                    elif stat == "median":
                        stat_vals[i] = np.median(win)
                    elif stat == "max":
                        stat_vals[i] = np.max(win)
                    elif stat == "std":
                        stat_vals[i] = np.std(win, ddof=1) if len(win) > 1 else 0.0
                group_df[_feature_col(col, suffix)] = stat_vals.astype("float64")

            # n_surcharges : uniquement pour target_voyageurs_2eme_classe
            if col == "target_voyageurs_2eme_classe":
                ns_vals = np.full(n, np.nan)
                for i in range(n):
                    if idx_consol[i] < 0:
                        continue
                    start = max(0, idx_consol[i] - 6)
                    end = idx_consol[i] + 1
                    win = vals[start:end]
                    win = win[~np.isnan(win)]
                    if len(win) == 0:
                        continue
                    ns_vals[i] = float(np.sum(win > SEUIL_UM_2EME))
                group_df[_feature_col(col, WIN7_NSURCHARGES_SUFFIX)] = ns_vals.astype("float64")

        all_groups_results.append(group_df)

    daily = pd.concat(all_groups_results, ignore_index=True)

    # 3. Jointure vers la table originale
    # win7_n_surcharges uniquement pour 2ème classe (ADR-010).
    feature_cols = [
        _feature_col(c, s)
        for c in LAG_SOURCE_COLS
        for s in HISTO_SUFFIXES
        if not (s == WIN7_NSURCHARGES_SUFFIX and c != "target_voyageurs_2eme_classe")
    ]

    result[DATE_COL] = pd.to_datetime(result[DATE_COL], errors="coerce")
    n_before = len(result)
    result = result.merge(
        daily[GROUP_KEYS + [DATE_COL] + feature_cols],
        on=GROUP_KEYS + [DATE_COL],
        how="left",
    )
    if len(result) != n_before:
        raise ValueError(
            f"Le merge a modifié le nombre de lignes : {n_before} -> {len(result)}. "
            "Vérifier l'unicité de (GROUP_KEYS, base_date) dans daily."
        )

    return result


def print_feature_coverage(enriched: pd.DataFrame) -> None:
    n = len(enriched)
    print(f"\nCouverture des features historiques (n={n:,}) :")
    for col in LAG_SOURCE_COLS:
        print(f"\n  Source : {col}")
        for suffix in HISTO_SUFFIXES:
            feat = _feature_col(col, suffix)
            if feat in enriched.columns:
                n_valid = enriched[feat].notna().sum()
                pct = 100 * n_valid / n
                print(f"    {feat:<60s} : {n_valid:>10,} ({pct:5.1f}%)")


def main() -> None:
    df = read_stage(STAGE_07_ISTDATEN)
    print(f"  {len(df):,} lignes, {df.shape[1]} colonnes")

    # ADR-044 : ordre de construction obligatoire en début de main() —
    # horaire_service_id_complet fournit les temps d'origine pour creneau_anchor_30.
    # creneau_anchor_30 doit exister AVANT add_derived_features (GROUP_KEYS).
    print("Construction horaire_service_id_complet ...")
    df = _ajouter_service_id_complet(df)
    n_services = df["horaire_service_id_complet"].nunique()
    print(f"  {n_services} modalités distinctes")

    # Vérifications préalables aux GROUP_KEYS.
    for col_requis, stage in [
        ("cal_type_jour_3classes", "add_vacances_feries_vaud"),
        ("base_sens", "stack_raw_csv"),
    ]:
        if col_requis not in df.columns:
            raise ValueError(
                f"Colonne {col_requis!r} absente de stage_07. "
                f"Vérifier le stage amont ({stage})."
            )
    print(f"  cal_type_jour_3classes : {df['cal_type_jour_3classes'].value_counts().to_dict()}")
    print(f"  base_sens : {df['base_sens'].value_counts().to_dict()}")

    print("Construction creneau_anchor_30 (ADR-044) ...")
    df = _ajouter_creneau_anchor_30(df)

    existing = [c for c in DERIVED_COLS if c in df.columns]
    if existing:
        print(f"  Colonnes existantes qui seront recalculées : {existing}")

    print("Calcul des variables dérivées ...")
    enriched = add_derived_features(df)
    new_cols = [c for c in DERIVED_COLS if c not in df.columns]
    print(f"  {enriched.shape[1]} colonnes au total ({len(new_cols)} nouvelles : {new_cols})")

    print_feature_coverage(enriched)

    # --- Headway ISTDATEN : isolement temporel par tronçon × sens (cf. ADR-018) ---
    print("Jointure ist_headway_avant_min / ist_headway_apres_min ...")
    headway = pd.read_parquet(DIM_HEADWAY)
    headway["base_date"] = pd.to_datetime(headway["date"])
    headway = headway.drop(columns=["date"]).rename(columns={
        "numero_train": "horaire_numero_train",
        "gare_depart_bpuic": "id_gare_depart_bpuic",
        "gare_arrivee_bpuic": "id_gare_arrivee_bpuic",
        "sens": "base_sens",
    })
    _headway_cols = [
        "ist_headway_avant_min", "ist_headway_apres_min",
        "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day",
    ]
    enriched = enriched.merge(
        headway[[
            "base_date", "horaire_numero_train",
            "id_gare_depart_bpuic", "id_gare_arrivee_bpuic", "base_sens",
        ] + _headway_cols],
        on=[
            "base_date", "horaire_numero_train",
            "id_gare_depart_bpuic", "id_gare_arrivee_bpuic", "base_sens",
        ],
        how="left",
    )
    for col in ["ist_headway_avant_min", "ist_headway_apres_min"]:
        n_couv = enriched[col].notna().sum()
        print(
            f"  Couverture {col} : {n_couv:,} / {len(enriched):,} "
            f"({100 * n_couv / len(enriched):.1f}%)"
        )

    # --- Validation créneau_anchor_30 (remplace validation service_id — ADR-044) ---
    if "creneau_anchor_30" in enriched.columns:
        print(f"  service_id_complet : {n_services} modalités distinctes (métadonnée, hors GROUP_KEYS)")
        # Couverture créneau par annee_horaire
        for annee in ANNEES_ANCRES + ["H25"]:
            sub = enriched[enriched["horaire_annee_horaire"] == annee]
            if len(sub) == 0:
                continue
            cov = sub["creneau_anchor_30"].notna().mean() * 100
            print(f"    {annee} : couverture creneau_anchor_30 = {cov:.1f}%")
        # Anti-fuite : anchors construits depuis H22-H24 uniquement
        anchors_utilises = enriched["creneau_anchor_30"].dropna().unique()
        print(f"  Anchors uniques utilisés : {len(anchors_utilises)}")

    # --- Garde-fou conformité ADR-062 (avant écriture) ---
    _assert_histo_conformite_adr_cf18(enriched)

    write_stage(enriched, STAGE_08_FEATURES)

    # --- Contrôles de cohérence post-construction (ADR-037) ---
    print("\n=== Contrôles de cohérence ===")

    lag2_col = _feature_col("target_voyageurs_2eme_classe", LAG_POINT_SUFFIX)

    # 1. Pour chaque groupe créneau, la première obs dans le temps doit avoir lag NaN.
    #    (aucune occurrence consolidée ne peut exister avant la première date du groupe)
    # Note : avec cross-années, certains groupes H25 peuvent avoir lag dès J=1
    # si H22-H24 fournit de l'historique → on vérifie seulement qu'il n'y a pas
    # de lag positif AVANT la première occurrence du groupe.
    first_obs_per_group = (
        enriched.sort_values(GROUP_KEYS + [DATE_COL])
        .groupby(GROUP_KEYS, sort=False, observed=True)
        .head(1)
    )
    n_first_nan = first_obs_per_group[lag2_col].isna().sum()
    n_first_total = len(first_obs_per_group)
    print(f"  Premiere obs/groupe avec lag2 NaN : "
          f"{n_first_nan}/{n_first_total} "
          f"({'OK' if n_first_nan == n_first_total else f'ATTENDU si cross-annee : {n_first_total - n_first_nan} groupes ont historique dès J=1'})")

    # 2. Cohérence interne : win7_max >= win7_mean (sur les lignes non-NaN)
    mean_col = _feature_col("target_voyageurs_2eme_classe", WIN7_MEAN_SUFFIX)
    max_col  = _feature_col("target_voyageurs_2eme_classe", WIN7_MAX_SUFFIX)
    mask_valid = enriched[max_col].notna() & enriched[mean_col].notna()
    violations = (enriched.loc[mask_valid, max_col] < enriched.loc[mask_valid, mean_col]).sum()
    print(f"  Violations win7_max >= win7_mean : {violations} "
          f"({'OK' if violations == 0 else 'ANOMALIE'})")

    # 3. Couverture lag2 par type_jour (post-jointure ml_dataset, indicatif)
    print(f"  Couverture lag2 par type_jour :")
    for tj in ["ouvrable", "samedi", "dimanche_ferie"]:
        mask_tj = enriched["cal_type_jour_3classes"] == tj
        sub = enriched[mask_tj]
        if len(sub) == 0:
            continue
        cov = sub[lag2_col].notna().mean() * 100
        print(f"    [{tj:<15s}] n={len(sub):>10,}  lag2={cov:.1f}%")


if __name__ == "__main__":
    main()
