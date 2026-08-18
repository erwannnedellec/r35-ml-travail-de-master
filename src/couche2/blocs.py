"""
src/couche2/blocs.py — Baseline humaine UM canonique + grain BLOC (couche 2).

SEULE implémentation autorisée du grain bloc et de la sémantique d'UM. Les deux
usages historiques (rapport_synthese_couche1.ipynb, baseline_definitive_bloc.py)
doivent importer ce module. Lecture seule sur le canonique : n'entraîne rien,
ne modifie pas ml_dataset (hash ba493568, ADR-076), n'écrit que son JSON de sortie.

═══════════════════════════════════════════════════════════════════════════════
CONVENTION CANONIQUE (arbitrage data lead, 2026-07)
═══════════════════════════════════════════════════════════════════════════════

Sémantique d'UM — PARSING SET-DEDUP
  Une UM est un accouplement de DEUX rames RAIL DISTINCTES (série 7501–7508).
  La composition est lue en ENSEMBLE dédoublonné : un même numéro écrit deux fois
  (« 7508,7508 ») désigne UNE rame physique = course SIMPLE, pas une UM (une rame
  ne peut être accouplée à elle-même). Grain :
    - segment UM   : len(parse_rails(CompositionOrdreVehicules)) >= 2
    - course UM    : au moins un de ses segments est UM
  Anomalies de saisie CONNUES (résolues par la règle générale, aucune correction
  nécessaire) : service 1334 BLON→VV, 2023-11-24 (« 7508,7508 ») et 2024-06-26
  (« 7506,7506 ») — repositionnements roulant en simple, doublon d'écriture.
  Compte canonique DÉFINITIF : 914 UM (dont 881 appariées APC).

Clé de BLOC — IDENTITÉ DE COMPOSITION, COURSE ATOMIQUE (option 1)
  (a) Un bloc est une suite maximale de courses CONSÉCUTIVES d'un même véhicule
      dont l'ensemble accouplé (signature de composition) est IDENTIQUE. Un
      changement de partenaire en cours de journée (7501+7502 → 7501+7506) ferme
      le bloc : ce sont deux décisions d'accouplement distinctes.
  (b) STRUCTURE physique complète : la séquence établissant la consécutivité
      inclut TOUTES les courses rail du véhicule (y compris sans mesure APC),
      ordonnées par l'horaire réel istdaten. L'accouplement est un fait physique,
      indépendant de la présence d'un capteur.
  (c) COMPTAGE mesuré uniquement : numérateur ET dénominateur restreints aux 881
      courses UM appariées APC. Les courses UM non mesurées structurent les
      chaînes mais ne sont JAMAIS comptées.
  (d) DÉTERMINISME : tri stable, tie-break explicite (heure de départ istdaten,
      puis numero_train) ; sortie JSON reproductible byte-exact (2 exécutions).
  Signature de composition d'une course (course atomique, option 1) = ensemble
  accouplé MAXIMAL = union des rails des segments UM de la course. Les 77 courses
  UM « partielles » (renfort accouplé/découplé à Blonay : UM sur une jambe, simple
  sur l'autre — 77/914) sont des UM à part entière, rattachées au bloc de leur
  signature ; la jambe simple intra-course n'ouvre pas de sous-bloc (convention
  identique à celle du label is_UM = OR sur les segments).

Grains rapportés (D6) : COURSE = headline (23,0 % = 203/881), BLOC = lecture
conséquence, TOUR = annexe diagnostique, toujours étiquetée « permissif ».
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pandas as pd

# ── Constantes nommées (rien en dur ailleurs) ──────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]  # racine du dépôt (src/couche2/ -> r35_ml)
ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
ROTATIONS = ROOT / "data/external/rotations/rotations_23_25.csv"
APC_STACKED = ROOT / "data/processed/sources/apc_stacked.parquet"
ISTDATEN = ROOT / "data/processed/sources/istdaten_clean.parquet"
ANNEES_HORAIRES = ROOT / "data/dimension/annees_horaires.csv"
OUT_JSON = ROOT / "outputs/couche2/baseline_um_canonique.json"

HASH_CANONIQUE = "ba493568"          # SHA256[:8] de ml_dataset.parquet (gel v2, ADR-076)
RAILS = frozenset({"7501", "7502", "7503", "7504", "7505", "7506", "7507", "7508"})
SEUIL_ASSISES = 63                   # places assises 2e classe (ADR-060)
SEUIL_SATURATION = 94                # offre nominale strapontins compris (ADR-060)
ORDRE_PLAINE_MAX = 10                # gare ordre <=10 = plaine (bas) ; >10 = crémaillère (haut)

# ── Mécanisme de disposition des anomalies ─────────────────────────────────────
# Whitelist de CORRECTIONS tracées qui ALTÈRENT la donnée d'entrée. Initialisée
# VIDE : les 2 anomalies 1334 ne nécessitent aucune correction (le set-dedup les
# classe correctement en simple). Toute correction future se déclare ici.
WHITELIST_CORRECTIONS: list[dict] = []

# Doublons d'écriture CONNUS et TOLÉRÉS par le garde-fou anti-doublon (neutralisés
# par le set-dedup, donc simples ; aucune donnée modifiée). Tout NOUVEAU doublon
# non listé ici déclenche une RuntimeError (protège les recalculs futurs).
DOUBLONS_SAISIE_TOLERES: list[dict] = [
    {"date": "2023-11-24", "numero_train": "1334", "composition": "7508,7508",
     "disposition": "unité simple (rame 7508), doublon d'écriture",
     "source": "data lead 2026-07 (vérité terrain)"},
    {"date": "2024-06-26", "numero_train": "1334", "composition": "7506,7506",
     "disposition": "unité simple (rame 7506), doublon d'écriture",
     "source": "data lead 2026-07 (vérité terrain)"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Parsing composition (set-dedup) + garde-fous
# ═══════════════════════════════════════════════════════════════════════════════
def parse_rails(composition) -> frozenset:
    """Ensemble DÉDOUBLONNÉ des rames rail d'un segment. '7508,7508' -> {'7508'}."""
    if pd.isna(composition):
        return frozenset()
    return frozenset(v.strip() for v in str(composition).split(",") if v.strip() in RAILS)


def _raw_rails(composition) -> list:
    """Liste BRUTE des rames rail (doublons conservés) — pour le garde-fou seul."""
    if pd.isna(composition):
        return []
    return [v.strip() for v in str(composition).split(",") if v.strip() in RAILS]


def assert_canonical_dataset(path: Path = ML_DATASET, expected: str = HASH_CANONIQUE) -> str:
    """Garde-fou dur : le monde de données est bien le canonique couche 1 (gel v2, ADR-076)."""
    h = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    if h != expected:
        raise RuntimeError(f"Hash ml_dataset {h} != canonique {expected} — couche 1 non figée.")
    return h


def check_no_unexpected_duplicates(rot_rail: pd.DataFrame,
                                   tolerated: list[dict] = DOUBLONS_SAISIE_TOLERES) -> None:
    """Assertion qualité (scellement d) : aucun numéro de véhicule dupliqué dans une
    composition, HORS anomalies tolérées. RuntimeError sur tout nouveau doublon."""
    tol = {(t["date"], t["numero_train"]) for t in tolerated}
    nouveaux = []
    for d, n, comp in rot_rail[["date", "numero_train", "CompositionOrdreVehicules"]].itertuples(index=False):
        raw = _raw_rails(comp)
        if len(raw) != len(set(raw)) and (str(pd.Timestamp(d).date()), str(n)) not in tol:
            nouveaux.append((str(pd.Timestamp(d).date()), str(n), comp))
    if nouveaux:
        raise RuntimeError(
            f"{len(nouveaux)} doublon(s) de véhicule NON tolérés (artefact de saisie ?) : "
            f"{nouveaux[:10]} — ajouter à DOUBLONS_SAISIE_TOLERES après vérification terrain.")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Composition des courses (rotations, set-dedup)
# ═══════════════════════════════════════════════════════════════════════════════
def course_signature(compositions) -> tuple:
    """Signature d'une course à partir des CompositionOrdreVehicules de ses segments.
    Retourne (is_UM, compo, vehicles) — option 1, course atomique :
      - is_UM   : au moins un segment a >=2 rails distincts (set-dedup)
      - compo   : ensemble accouplé MAXIMAL = union des rails des segments UM (tuple trié)
      - vehicles: toutes les rames physiques utilisées par la course (tuple trié)
    Les 77 courses UM partielles (une jambe UM, une jambe simple) -> compo = jambe UM."""
    segs = [parse_rails(c) for c in compositions]
    seg_um = [len(s) >= 2 for s in segs]
    is_um = any(seg_um)
    compo = frozenset().union(*[s for s, u in zip(segs, seg_um) if u]) if is_um else frozenset()
    vehicles = frozenset().union(*segs) if segs else frozenset()
    return is_um, tuple(sorted(compo)), tuple(sorted(vehicles))


def load_composition() -> pd.DataFrame:
    """Une ligne par course rail (date × numero_train) : is_UM, signature accouplée,
    véhicules physiques. Applique le garde-fou anti-doublon."""
    rot = pd.read_csv(ROTATIONS, sep=";", encoding="utf-8-sig", on_bad_lines="skip")
    rot["date"] = pd.to_datetime(rot.TrainDate)
    rot["numero_train"] = rot.TrainNumeroTrain.astype(str)
    r = rot[(rot.TrainProprietaire == "voy") & (rot.TrainType == "Régulier")].copy()
    r["railset"] = r.CompositionOrdreVehicules.apply(parse_rails)   # set-dedup par segment
    r = r[r.railset.apply(len) >= 1].copy()                          # segments porteurs de rail
    check_no_unexpected_duplicates(r)

    def _course(g):
        is_um, compo, vehicles = course_signature(g.CompositionOrdreVehicules)
        return pd.Series({"is_UM": is_um, "compo": compo, "vehicles": vehicles})

    comp = r.groupby(["date", "numero_train"], sort=True).apply(_course, include_groups=False).reset_index()
    return comp


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Charge APC par course (source observée) + segment
# ═══════════════════════════════════════════════════════════════════════════════
def load_charge() -> pd.DataFrame:
    """Charge 2e classe observée agrégée à la course (max sur tronçons) + surcharge
    aux deux seuils + segment bas/haut (D2/D3 : label = au moins un tronçon >63)."""
    apc = pd.read_parquet(APC_STACKED, columns=[
        "base_date", "horaire_numero_train", "target_voyageurs_2eme_classe",
        "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre"])
    apc["date"] = pd.to_datetime(apc.base_date)
    apc["numero_train"] = apc.horaire_numero_train.astype("Int64").astype(str)
    apc["charge2"] = apc.target_voyageurs_2eme_classe.astype("Float64").astype(float)
    apc["haut"] = ((apc.spatial_gare_depart_ordre > ORDRE_PLAINE_MAX) |
                   (apc.spatial_gare_arrivee_ordre > ORDRE_PLAINE_MAX)).fillna(False)
    course = apc.groupby(["date", "numero_train"], sort=True).agg(
        charge_max=("charge2", "max"),
        n_troncons_valides=("charge2", lambda s: int(s.notna().sum())),
        surcharge_63=("charge2", lambda s: bool((s > SEUIL_ASSISES).any())),
        surcharge_94=("charge2", lambda s: bool((s > SEUIL_SATURATION).any())),
        any_haut=("haut", "max")).reset_index()
    course = course[course.n_troncons_valides >= 1].copy()
    course["segment"] = course.any_haut.map({True: "haut", False: "bas"})
    return course


def load_departs() -> dict:
    """Heure de départ réelle (istdaten) par course, pour l'ordre de chaînage."""
    ist = pd.read_parquet(ISTDATEN, columns=["date", "numero_train", "horaire_depart"])
    ist["date"] = pd.to_datetime(ist.date)
    ist["numero_train"] = ist.numero_train.astype("Int64").astype(str)
    return ist.groupby(["date", "numero_train"]).horaire_depart.min().to_dict()


def assign_annee(dates: pd.Series) -> pd.Series:
    """Année horaire (H23/H24/H25) d'une date, depuis annees_horaires.csv (bornes Debut/Fin)."""
    ah = pd.read_csv(ANNEES_HORAIRES, sep=";", encoding="utf-8-sig")
    ah = ah[ah.Debut.notna() & ah.Fin.notna()].copy()
    ah["d"] = pd.to_datetime(ah.Debut, format="%d.%m.%Y")
    ah["f"] = pd.to_datetime(ah.Fin, format="%d.%m.%Y")
    out = pd.Series(["?"] * len(dates), index=dates.index, dtype=object)
    for _, row in ah.iterrows():
        out[(dates >= row.d) & (dates <= row.f)] = row.Annee
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Construction des blocs (identité de composition, structure physique complète)
# ═══════════════════════════════════════════════════════════════════════════════
REGLE_CANONIQUE = "identite_composition"       # ta règle actée (a)
REGLE_SENSIBILITE = "consecutivite_simple"     # variante de robustesse (E1)


def build_blocs(comp: pd.DataFrame, departs: dict, rule: str = REGLE_CANONIQUE) -> dict:
    """Retourne {(date, numero_train) -> bloc_id} pour les courses UM.
    Structure = toutes les courses rail (b) ; ordre = départ istdaten puis
    numero_train (d). Chaîne deux courses UM CONSÉCUTIVES d'un même véhicule si :
      - rule='identite_composition' (canonique) : leur signature est IDENTIQUE (a) ;
      - rule='consecutivite_simple' (sensibilité E1) : dès qu'elles sont consécutives."""
    info = {(d, n): (bool(u), c) for d, n, u, c in
            comp[["date", "numero_train", "is_UM", "compo"]].itertuples(index=False)}
    # séquence par véhicule physique : (véhicule -> liste de courses ordonnées)
    seq = {}
    for d, n, vehs in comp[["date", "numero_train", "vehicles"]].itertuples(index=False):
        for v in vehs:
            seq.setdefault((d, v), []).append((d, n))

    parent: dict = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (d, _v), courses in seq.items():
        # tie-break déterministe : (départ istdaten, numero_train)
        courses = sorted(courses, key=lambda k: (departs.get(k) is None, departs.get(k), k[1]))
        prev = None
        for k in courses:
            is_um, compo = info[k]
            if is_um:
                find(k)
                meme_bloc = prev is not None and (
                    rule == REGLE_SENSIBILITE or info[prev][1] == compo)
                if meme_bloc:
                    union(prev, k)
                prev = k
            else:
                prev = None                                          # course simple rompt la chaîne
    return {k: find(k) for k in info if info[k][0]}                  # UM uniquement


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Baseline complète (course headline / bloc conséquence / tour permissif)
# ═══════════════════════════════════════════════════════════════════════════════
def _confusion(sub: pd.DataFrame, col: str) -> dict:
    um = sub.is_UM.values.astype(bool)
    sc = sub[col].values.astype(bool)
    VP = int((um & sc).sum()); FP = int((um & ~sc).sum())
    FN = int((~um & sc).sum()); VN = int((~um & ~sc).sum())
    return {"n": int(len(sub)), "VP": VP, "FP": FP, "FN": FN, "VN": VN,
            "UM_deployees": VP + FP, "courses_besoin_UM": VP + FN,
            "precision": (VP / (VP + FP)) if (VP + FP) else None,
            "rappel": (VP / (VP + FN)) if (VP + FN) else None}


def compute_baseline() -> dict:
    """Baseline humaine UM canonique complète (n bruts partout). Aucune valeur en dur."""
    comp = load_composition()
    charge = load_charge()
    departs = load_departs()

    n_um_total = int(comp.is_UM.sum())                               # attendu 914
    m = comp.merge(charge, on=["date", "numero_train"], how="inner")  # composition ∩ charge
    m["annee"] = assign_annee(m.date)                                # H23 / H24 / H25
    n_um_apparie = int(m.is_UM.sum())                                # attendu 881

    # -- Grain COURSE (headline) : global / segment / année horaire --
    matrices = {}
    for lbl, col in [("assises", "surcharge_63"), ("saturation", "surcharge_94")]:
        matrices[lbl] = {
            "global": _confusion(m, col),
            "segment": {s: _confusion(m[m.segment == s], col) for s in ("bas", "haut")},
            "annee": {a: _confusion(m[m.annee == a], col) for a in ("H23", "H24", "H25")}}

    # -- Grain BLOC (conséquence) : comptage sur les 881 UM appariées (c) --
    # E1 : deux variantes conservées et étiquetées — canonique (identité-composition)
    # + sensibilité (consécutivité simple), lues côte à côte en phase 2.
    m_um = m[m.is_UM].copy()
    variantes = {"bloc_canonique_identite_composition": build_blocs(comp, departs, REGLE_CANONIQUE),
                 "bloc_sensibilite_consecutivite_simple": build_blocs(comp, departs, REGLE_SENSIBILITE)}
    bloc = {"assises": {}, "saturation": {}}
    for vlbl, bloc_of in variantes.items():
        m_um["bloc"] = [bloc_of[(d, n)] for d, n in m_um[["date", "numero_train"]].itertuples(index=False)]
        for lbl, col in [("assises", "surcharge_63"), ("saturation", "surcharge_94")]:
            just = m_um.groupby("bloc")[col].max()                  # bloc justifié si >=1 course mesurée surchargée
            bj = m_um.bloc.map(just)
            jc = int(m_um[col].sum()); jjb = int(bj.sum())
            # ventilation annuelle au grain bloc (les blocs ne traversent pas les dates -> intra-année)
            annee_bloc = {}
            for a in ("H23", "H24", "H25"):
                sub = m_um[m_um.annee == a]
                bja = sub.bloc.map(just)
                annee_bloc[a] = {
                    "base_um_mesurees": int(len(sub)),
                    "justif_course": int(sub[col].sum()),
                    "justif_bloc": int(bja.sum()),
                    "heritage": int(((~sub[col].astype(bool)) & bja.astype(bool)).sum()),
                    "precision_bloc": (int(bja.sum()) / len(sub)) if len(sub) else None}
            bloc[lbl][vlbl] = {"base_um_mesurees": int(len(m_um)),
                               "n_blocs": int(m_um.bloc.nunique()),
                               "justif_course": jc, "justif_bloc": jjb,
                               "heritage": int(((~m_um[col].astype(bool)) & bj.astype(bool)).sum()),
                               "precision_bloc": jjb / len(m_um) if len(m_um) else None,
                               "annee": annee_bloc}

    # -- Grain TOUR (annexe PERMISSIVE) : (date × véhicule), même agrégation des 2 côtés --
    rows = [(d, v, n) for d, n, vehs in m[["date", "numero_train", "vehicles"]].itertuples(index=False) for v in vehs]
    vc = pd.DataFrame(rows, columns=["date", "veh", "numero_train"]).merge(
        m[["date", "numero_train", "is_UM", "surcharge_63", "surcharge_94"]], on=["date", "numero_train"])
    tour = {}
    for lbl, col in [("assises", "surcharge_63"), ("saturation", "surcharge_94")]:
        tg = vc.groupby(["date", "veh"]).agg(tUM=("is_UM", "max"), tsc=(col, "max")).reset_index()
        um_t = tg[tg.tUM]
        tour[lbl] = {"grain": "PERMISSIF (tour = jour × véhicule ; justifié si >=1 course surcharge)",
                     "n_tours_UM": int(len(um_t)),
                     "precision_permissive": float(um_t.tsc.mean()) if len(um_t) else None}

    # -- Référence D5 : barre iso-budget de la phase 2 = précision humaine H25, grain course --
    # (le budget = nombre de courses-UM humaines DANS H25 ; le 23,0 % période totale reste
    #  rapporté mais n'est PAS la barre de comparaison.)
    h25g = matrices["assises"]["annee"]["H25"]
    def _h25seg(s):                                                   # confusion H25 d'un segment (n bruts complets)
        c = _confusion(m[(m.annee == "H25") & (m.segment == s)], "surcharge_63")
        return {"VP": c["VP"], "FP": c["FP"], "FN": c["FN"],
                "n_surcharges": c["courses_besoin_UM"],              # dénominateur du rappel segmenté = VP+FN
                "precision": c["precision"], "rappel": c["rappel"]}
    reference_phase2 = {
        "definition": "baseline humaine H25 au grain course, seuil 63 — barre iso-budget phase 2 (D5). "
                      "La comparaison porte sur le COUPLE précision-rappel, pas la précision seule.",
        "budget_UM_H25": h25g["UM_deployees"],                        # 418 = courses-UM humaines DANS H25
        "n_surcharges_H25": h25g["courses_besoin_UM"],               # 2072 = VP+FN = courses à surcharge >63 en H25
        "global": {"VP": h25g["VP"], "FP": h25g["FP"], "FN": h25g["FN"],
                   "precision": h25g["precision"], "rappel": h25g["rappel"]},
        "segment": {s: _h25seg(s) for s in ("bas", "haut")},
    }

    return {
        "meta": {
            "hash_canonique": HASH_CANONIQUE,
            "convention": "set-dedup UM ; bloc = identité de composition, course atomique (option 1) ; comptage sur UM mesurées",
            "seuils": {"assises": SEUIL_ASSISES, "saturation": SEUIL_SATURATION},
            "periode": [str(m.date.min().date()), str(m.date.max().date())],
            "n_UM_total": n_um_total, "n_UM_appariees_APC": n_um_apparie,
            "n_courses_appariees": int(len(m)),
            "anomalies_saisie_tolerees": DOUBLONS_SAISIE_TOLERES,
            "corrections_appliquees": WHITELIST_CORRECTIONS,
            "note_77_partielles": "77/914 UM à composition intra-course (renfort Blonay), rattachées au bloc de leur signature",
        },
        "course": matrices,
        "reference_phase2_course_H25": reference_phase2,
        "bloc": bloc,
        "tour": tour,
    }


def main() -> None:
    assert_canonical_dataset()
    res = compute_baseline()
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False, sort_keys=True))
    g = res["course"]["assises"]["global"]; t = res["tour"]["assises"]
    bc = res["bloc"]["assises"]["bloc_canonique_identite_composition"]
    bs = res["bloc"]["assises"]["bloc_sensibilite_consecutivite_simple"]
    print(f"[HASH] ml_dataset = {res['meta']['hash_canonique']} OK")
    print(f"[UM]   total={res['meta']['n_UM_total']} | appariées={res['meta']['n_UM_appariees_APC']}")
    print(f"[COURSE seuil63] VP={g['VP']} FP={g['FP']} FN={g['FN']} | "
          f"précision={g['VP']}/{g['UM_deployees']}={g['precision']:.4f} | rappel={g['VP']}/{g['courses_besoin_UM']}={g['rappel']:.4f}")
    print(f"[BLOC canon]  n_blocs={bc['n_blocs']} justif_bloc={bc['justif_bloc']}/{bc['base_um_mesurees']}"
          f"={bc['precision_bloc']:.4f} héritage=+{bc['heritage']}")
    print(f"[BLOC sensib] n_blocs={bs['n_blocs']} justif_bloc={bs['justif_bloc']}/{bs['base_um_mesurees']}"
          f"={bs['precision_bloc']:.4f} héritage=+{bs['heritage']}")
    print(f"[TOUR seuil63]  n_tours_UM={t['n_tours_UM']} précision_permissive={t['precision_permissive']:.4f} (PERMISSIF)")
    print(f"[OK] {OUT_JSON.name} écrit.")


if __name__ == "__main__":
    main()
