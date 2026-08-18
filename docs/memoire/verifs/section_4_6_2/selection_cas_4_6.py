#!/usr/bin/env python3
"""§4.6.2 / §4.6.3 — Sélection DÉTERMINISTE du cas illustratif (couche 2, gel v2 `ba493568`).

Objet. Choisir, sans arbitraire, une course H25 qui illustre le menu de décision de la
couche 2 : une course RECOMMANDÉE par les règles b (rappel renforcé) et c (haute précision)
mais PAS par a′ (iso-volume), et en surcharge RÉELLE. Le cas sert de support commun aux
figures 4.6.2 (charge observée) et 4.6.3 (charge prédite).

Règle de sélection (pré-spécifiée, sans réglage a posteriori). Parmi les courses H25
iso-périmètre (∩ baseline humaine, 29 222 courses) :
  1. label de surcharge observée = 1 (au moins un tronçon 2e classe > 63, ADR-060) ;
  2. score de course (= MAX des prédictions couche 1 sur les tronçons, D3) STRICTEMENT
     compris entre τ(c)=64,12 et τ(a′)=78,99 → recommandée par b et c, jamais par a′ ;
  3. au moins 8 tronçons desservis ;
  puis retenir la course dont le score est le plus proche de 71,5 ; départage par date la
  plus ancienne, puis numero_train croissant. Si l'ensemble (1)+(2)+(3) est VIDE, la
  contrainte (3) est relâchée (documenté dans le .md).

Discipline. LECTURE SEULE. Modèles figés `enrichi_seg_{bas,haut}_ba493568.json` (hash
e4ddfccd / df6a11c5), dataset `ba493568`. Les prédictions par tronçon sont recalculées
dans le CONTEXTE CANONIQUE (lot complet H24+H25, mêmes codes de catégorie que
`decision.load_troncon_predictions`) : une prédiction sur la seule course donnerait des
codes de catégorie différents et un score FAUX. Une assertion vérifie que le MAX des
prédictions du cas retenu reproduit exactement son score du jeu de décision.

Sorties (docs/memoire/verifs/section_4_6/) :
  - cas_illustratif_4_6.md    documentation (Tâche 1) ;
  - cas_4_6_troncons.csv      table canonique par tronçon (support des figures A et B) ;
  - cas_4_6_meta.json         identifiants, seuils, tronçon déterminant, audit sélection.
Le markdown est reconstruit UNIQUEMENT depuis cas_4_6_troncons.csv + cas_4_6_meta.json
(`build_md`) : il est régénérable sans relancer le balayage complet.

Exécuter :  python3 docs/memoire/verifs/section_4_6/selection_cas_4_6.py
"""
from __future__ import annotations
import os, sys, json
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision, blocs  # noqa: E402

OUT = ROOT / "docs/memoire/verifs/section_4_6_2"
CIBLE_SCORE = 71.5
NTRONCONS_MIN = 8

# ── Seuils du menu (calibration H24 figée) ─────────────────────────────────────
CALIB = json.loads((ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json").read_text())
TAU_A = CALIB["regles_deployables"]["a_iso_volume"]["seuil"]        # 78,99047
TAU_B = CALIB["regles_deployables"]["b_rappel_renforce"]["seuil"]   # 51,30576
TAU_C = CALIB["regles_deployables"]["c_haute_precision"]["seuil"]   # 64,11588
SEUIL_MESURE = blocs.SEUIL_ASSISES                                  # 63

# ── Libellés gares (dim_gare) + français (sans locale) ─────────────────────────
GARE = pd.read_parquet(ROOT / "data/dimension/dim_gare.parquet",
                       columns=["abreviation", "nom", "ordre"]).set_index("abreviation")
NOM_GARE = GARE["nom"].to_dict()
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]
TYPE_JOUR_FR = {
    "ouvrable_hors_vacances": "jour ouvrable hors vacances",
    "ouvrable_vacances": "jour ouvrable en vacances scolaires",
    "samedi": "samedi", "dimanche_ou_ferie": "dimanche ou jour férié",
}


def date_fr(ts: pd.Timestamp) -> str:
    return f"{JOURS_FR[ts.weekday()]} {ts.day} {MOIS_FR[ts.month]} {ts.year}"


def vfr(x: float, dec: int = 2) -> str:
    """Nombre au format français (virgule décimale)."""
    return f"{x:.{dec}f}".replace(".", ",")


# ── 1) Jeu de décision iso-périmètre H25 + sélection déterministe ──────────────
def selectionner():
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)                 # gardes 29 222 / 2 072
    h25 = ds[ds["annee"] == "H25"].copy()

    def pool(ntmin):
        return h25[(h25["label"]) & (h25["score"] > TAU_C) & (h25["score"] < TAU_A)
                   & (h25["n_troncons"] >= ntmin)].copy()

    relache = False
    cand = pool(NTRONCONS_MIN)
    if len(cand) == 0:                                              # repli documenté
        relache = True
        cand = pool(1)
    cand["ntrain_int"] = cand["numero_train"].astype(int)
    cand["dist"] = (cand["score"] - CIBLE_SCORE).abs()
    cand = cand.sort_values(["dist", "date", "ntrain_int"]).reset_index(drop=True)
    return h25, cand, relache, info


# ── 2) Prédictions par tronçon dans le CONTEXTE CANONIQUE (lot complet H24+H25) ─
def troncons_canoniques(date: pd.Timestamp, numero_train: str) -> pd.DataFrame:
    blocs.assert_canonical_dataset()
    decision._assert_models()
    feats = json.loads((ROOT / "outputs/couche2/features_158f_sans_simba.json").read_text())["features"]
    assert len(feats) == 158

    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    df = df[df["horaire_annee_horaire"].isin(["H24", "H25"])].copy()   # même lot que decision.py
    mb = xgb.XGBRegressor(); mb.load_model(str(decision.MODEL_BAS))
    mh = xgb.XGBRegressor(); mh.load_model(str(decision.MODEL_HAUT))
    pred = np.empty(len(df), dtype="float64")
    m_bas = (df["spatial_segment"] == "bas").values
    m_haut = (df["spatial_segment"] == "haut").values
    pred[m_bas] = mb.predict(decision._prep_X(df[m_bas], feats)).astype("float64")
    pred[m_haut] = mh.predict(decision._prep_X(df[m_haut], feats)).astype("float64")
    df["pred"] = pred

    c = df[(df["base_date"] == date) & (df["horaire_numero_train"] == int(numero_train))
           & (df["horaire_annee_horaire"] == "H25")].copy()
    c = c.sort_values("spatial_gare_depart_ordre").reset_index(drop=True)
    t = pd.DataFrame({
        "rang": np.arange(1, len(c) + 1),
        "ordre_depart": c["spatial_gare_depart_ordre"].astype(int).values,
        "ordre_arrivee": c["spatial_gare_arrivee_ordre"].astype(int).values,
        "gare_depart": c["id_gare_depart"].astype(str).values,
        "gare_arrivee": c["id_gare_arrivee"].astype(str).values,
        "segment": c["spatial_segment"].astype(str).values,
        "charge_observee_2c": c["target_voyageurs_2eme_classe"].astype(int).values,
        "charge_predite": c["pred"].round(6).values,
        "resa_pax_2c_j1": c["resa_pax_2c_J_minus_1"].astype(int).values,
    })
    return t


# ── 3) Assemblage + écriture des livrables ─────────────────────────────────────
def main():
    h25, cand, relache, info = selectionner()
    if len(cand) == 0:
        raise RuntimeError("Aucune course candidate même après relâchement de la contrainte de tronçons.")
    win = cand.iloc[0]
    date = pd.Timestamp(win["date"]); ntrain = str(win["numero_train"])

    t = troncons_canoniques(date, ntrain)
    score = float(t["charge_predite"].max())
    assert abs(score - float(win["score"])) < 1e-3, \
        f"score tronçon {score} != score jeu de décision {win['score']}"

    i_score = int(t["charge_predite"].idxmax())          # tronçon porteur du score (max préd)
    obs_max = int(t["charge_observee_2c"].max())
    obs_max_rangs = t.index[t["charge_observee_2c"] == obs_max].tolist()
    resa_course = int(t["resa_pax_2c_j1"].max())         # entrée du plancher (max sur tronçons)
    t["porteur_score"] = False; t.loc[i_score, "porteur_score"] = True
    t["charge_obs_maximale"] = t["charge_observee_2c"] == obs_max

    det = t.loc[i_score]                                  # tronçon déterminant = porteur du score
    det_lib = f"{det['gare_depart']}→{det['gare_arrivee']}"

    statut = {
        "a_prime_iso_volume": {"seuil": TAU_A, "recommande": bool(score >= TAU_A)},
        "b_rappel_renforce":  {"seuil": TAU_B, "recommande": bool(score >= TAU_B)},
        "c_haute_precision":  {"seuil": TAU_C, "recommande": bool(score >= TAU_C)},
        "plancher_reservation": {"seuil": SEUIL_MESURE, "resa_pax_2c_j1": resa_course,
                                 "declenche": bool(resa_course > SEUIL_MESURE)},
    }

    # ---- CSV support des figures ----
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "cas_4_6_troncons.csv", index=False)

    # ---- meta / audit ----
    top = cand.head(12)[["date", "numero_train", "segment", "score", "charge_max",
                         "resa2c", "n_troncons", "is_UM", "dist"]].copy()
    top["date"] = top["date"].astype(str)
    meta = {
        "hash_dataset": blocs.HASH_CANONIQUE,
        "modeles": {"bas": decision.HASH_MODEL_BAS, "haut": decision.HASH_MODEL_HAUT},
        "seuils": {"a_prime": TAU_A, "b": TAU_B, "c": TAU_C, "seuil_mesure": SEUIL_MESURE},
        "regle_selection": {
            "perimetre": "H25 iso-périmètre (∩ baseline humaine)", "n_courses_H25": info["n_h25"],
            "criteres": ["label=1", f"{TAU_C} < score < {TAU_A}", f"n_troncons >= {NTRONCONS_MIN}"],
            "cible_score": CIBLE_SCORE, "departage": "date la plus ancienne puis numero_train croissant",
            "contrainte_troncons_relachee": relache, "n_candidats": int(len(cand)),
        },
        "cas_retenu": {
            "numero_train": ntrain, "date": str(date.date()), "date_fr": date_fr(date),
            "type_jour_fr": type_jour_fr(date, ntrain),
            "segment_course": str(win["segment"]), "score": score,
            "charge_observee_max": obs_max, "n_troncons": int(len(t)),
            "is_UM_humaine": bool(win["is_UM"]),
            "resa_plancher": resa_course,
            "troncon_determinant": det_lib,
            "troncon_determinant_rang": int(det["rang"]),
            "charge_obs_max_troncons": [f"{t.loc[r,'gare_depart']}→{t.loc[r,'gare_arrivee']}"
                                        for r in obs_max_rangs],
        },
        "statut_menu": statut,
        "audit_top12_candidats": top.to_dict(orient="records"),
    }
    (OUT / "cas_4_6_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # ---- markdown (reconstruit UNIQUEMENT depuis t + meta : régénérable sans re-scan) ----
    (OUT / "cas_illustratif_4_6.md").write_text(build_md(t, meta))

    print(f"[OK] cas retenu = {ntrain} du {date.date()} | score={vfr(score)} | "
          f"charge_obs_max={obs_max} | tronçon déterminant={det_lib}")
    print(f"[OK] écrits : cas_illustratif_4_6.md, cas_4_6_troncons.csv, cas_4_6_meta.json "
          f"({len(cand)} candidats)")


# ── 4) Markdown (blocs séparés par ligne vide, à partir de t + meta uniquement) ─
def build_md(t: pd.DataFrame, meta: dict) -> str:
    s = meta["seuils"]; c = meta["cas_retenu"]; st = meta["statut_menu"]; rs = meta["regle_selection"]
    ta, tb, tc = s["a_prime"], s["b"], s["c"]
    score = c["score"]; obs_max = c["charge_observee_max"]; det_lib = c["troncon_determinant"]
    resa = c["resa_plancher"]; obs_max_libs = c["charge_obs_max_troncons"]
    B = []  # blocs markdown

    B.append("# Cas illustratif du menu de décision (couche 2) — §4.6.2 / §4.6.3")
    B.append("**Objet.** Sélection *déterministe* d'une course H25 illustrant une décision "
             "« recommandée par b et c mais pas par a′ », en surcharge réelle. Support commun des "
             "figures 4.6.2 (charge observée) et 4.6.3 (charge prédite). Lecture seule ; aucun "
             "artefact modifié.")
    B.append("**Génération.** Dataset gel v2 `ba493568` ; modèles figés "
             f"`enrichi_seg_bas`=`{meta['modeles']['bas']}`, `enrichi_seg_haut`=`{meta['modeles']['haut']}`. "
             "Prédictions par tronçon recalculées dans le contexte canonique (lot complet H24+H25) ; "
             "le MAX reproduit exactement le score du jeu de décision (`src/couche2/decision.py`). "
             "Script : `selection_cas_4_6.py`.")

    B.append("## 1. Règle de sélection et déroulé")
    B.append(f"Périmètre : **{rs['n_courses_H25']:,} courses H25 iso-périmètre** "
             "(intersection prédiction ∩ décision UM humaine ∩ label observé).".replace(",", " "))
    B.append("Critères (pré-spécifiés) :\n\n"
             "1. label de surcharge observée = 1 (au moins un tronçon 2e classe > 63) ;\n"
             f"2. score de course (D3 = max des prédictions par tronçon) strictement compris entre "
             f"**τ(c)={vfr(tc)}** et **τ(a′)={vfr(ta)}** → recommandée par **b** et **c**, pas par **a′** ;\n"
             f"3. au moins **{NTRONCONS_MIN} tronçons** desservis.")
    B.append(f"Puis **score le plus proche de {vfr(CIBLE_SCORE,1)}** ; départage par date la plus "
             "ancienne, puis numero_train croissant.")
    if rs["contrainte_troncons_relachee"]:
        B.append("> ⚠️ L'ensemble (1)+(2)+(3) était vide : la contrainte des 8 tronçons a été "
                 "**relâchée** (documenté ici, conformément à la consigne).")
    else:
        B.append(f"L'ensemble n'est pas vide : **{rs['n_candidats']} courses candidates** satisfont "
                 "(1)+(2)+(3). Aucune relâche nécessaire.")

    B.append("### Cas retenu")
    cas_rows = [
        ("numero_train", f"**{c['numero_train']}**"),
        ("date", f"**{c['date_fr']}** ({c['date']})"),
        ("type de jour", c["type_jour_fr"]),
        ("segment de la course", c["segment_course"]),
        ("score de course (max prédit)", f"**{vfr(score)}**"),
        ("charge observée maximale (2e classe)", f"**{obs_max}**"),
        ("tronçon déterminant (max)", f"**{det_lib}**"),
        ("nombre de tronçons", str(c["n_troncons"])),
        ("UM déployée par l'humain", "oui" if c["is_UM_humaine"] else "non"),
        ("résa 2e classe J-1 (max tronçon)", str(resa)),
    ]
    B.append("| Attribut | Valeur |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in cas_rows))

    B.append("## 2. Détail par tronçon (ordre de la marche)")
    B.append("Charge observée = comptage APC 2e classe ; charge prédite = modèle figé du segment. "
             "Le tronçon **déterminant** (porteur du max observé *et* du score) est marqué ★.")
    trows = ["| Rang | Tronçon (départ → arrivée) | Segment | Charge observée 2e cl. | Charge prédite |",
             "|---:|---|:--:|---:|---:|"]
    for _, r in t.iterrows():
        star = " ★" if r["porteur_score"] else ""
        dep = f"{r['gare_depart']} ({NOM_GARE.get(r['gare_depart'], r['gare_depart'])})"
        arr = f"{r['gare_arrivee']} ({NOM_GARE.get(r['gare_arrivee'], r['gare_arrivee'])})"
        trows.append(f"| {r['rang']} | {dep} → {arr}{star} | {r['segment']} | "
                     f"{r['charge_observee_2c']} | {vfr(float(r['charge_predite']))} |")
    B.append("\n".join(trows))

    tie = ("**Max observé = " + str(obs_max) + "** sur " + " et ".join(f"`{x}`" for x in obs_max_libs)
           + (f" (deux tronçons adjacents à égalité ; le tronçon `{det_lib}`, qui porte aussi le "
              "score du modèle, est retenu comme déterminant et mis en évidence dans les figures)."
              if len(obs_max_libs) > 1 else f". Ce tronçon `{det_lib}` porte aussi le score du modèle."))
    B.append(tie + f"\n\n**Score de course = {vfr(score)}** = max des prédictions par tronçon, "
             f"atteint sur `{det_lib}` (segment haut).")

    B.append("## 3. Statut vis-à-vis du menu de décision et du plancher")
    def mark(b, gras_oui=True):
        if gras_oui:
            return "**oui**" if b else "non"
        return "oui" if b else "**non**"
    stat_rows = [
        f"| a′ (iso-volume) | {vfr(ta)} | {vfr(score)} | {mark(st['a_prime_iso_volume']['recommande'], False)} |",
        f"| b (rappel renforcé, F₂) | {vfr(tb)} | {vfr(score)} | {mark(st['b_rappel_renforce']['recommande'])} |",
        f"| c (haute précision, F0,5) | {vfr(tc)} | {vfr(score)} | {mark(st['c_haute_precision']['recommande'])} |",
        f"| plancher (résa 2C J-1 > 63) | {s['seuil_mesure']} | {resa} | "
        f"{'oui' if st['plancher_reservation']['declenche'] else 'non'} |",
    ]
    B.append("| Règle | Seuil | Score/valeur | Recommande ? |\n|---|---:|---:|:--:|\n" + "\n".join(stat_rows))
    B.append(f"Le score **{vfr(score)}** franchit **b** ({vfr(tb)}) et **c** ({vfr(tc)}) mais "
             f"**pas a′** ({vfr(ta)}) : c'est exactement l'illustration recherchée. Le plancher de "
             f"demande annoncée se déclenche aussi (résa J-1 = {resa} > {s['seuil_mesure']}) ; il "
             "fournit ici une couverture *redondante* de la course, indépendante du score, et "
             "n'affecte pas l'illustration du menu par le score.")
    B.append(f"> Lecture : dans la configuration de déploiement `c ∪ plancher` (ADR-077), cette "
             f"course est un **vrai positif** — captée par c (score {vfr(score)} ≥ {vfr(tc)}) *et* par "
             f"le plancher (résa {resa} > {s['seuil_mesure']}) ; la charge réellement observée "
             f"({obs_max}) confirme la surcharge.")

    B.append("## 4. Audit de détermination (12 meilleures candidates)")
    B.append("Départage : `dist` = |score − 71,5|, puis date, puis numero_train. La première ligne "
             "est le cas retenu.")
    arows = ["| Rang | date | numero_train | segment | score | charge max | résa2c | tronçons | UM | dist |",
             "|---:|---|---:|:--:|---:|---:|---:|---:|:--:|---:|"]
    for i, r in enumerate(meta["audit_top12_candidats"], start=1):
        arows.append(f"| {i} | {r['date']} | {r['numero_train']} | {r['segment']} | "
                     f"{vfr(float(r['score']))} | {int(r['charge_max'])} | {int(r['resa2c'])} | "
                     f"{int(r['n_troncons'])} | {'oui' if r['is_UM'] else 'non'} | {vfr(float(r['dist']),4)} |")
    B.append("\n".join(arows))

    B.append("## Sources\n\n"
             "- Jeu de décision & score D3 : `src/couche2/decision.py` "
             "(`build_decision_set`, `load_troncon_predictions`).\n"
             "- Seuils du menu : `outputs/couche2/q_couche2_calibration_H24_ba493568.json` "
             "(a′=`:5`, b=`:16`, c=`:23`).\n"
             "- Topologie / segment (frontière à Blonay) : `data/dimension/dim_gare.parquet`, "
             "`spatial_segment` (ordre ≤ 10 = bas, > 10 = haut ; `blocs.ORDRE_PLAINE_MAX`).\n"
             "- Support des figures : `cas_4_6_troncons.csv` + `cas_4_6_meta.json` (ce dossier).")

    return "\n\n".join(B) + "\n"


# -- helper type de jour (lecture ml_dataset, une valeur) -----------------------
_TJ_CACHE = {}
def _type_jour(date, ntrain):
    key = (str(date.date()), str(ntrain))
    if key not in _TJ_CACHE:
        d = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet",
                            columns=["base_date", "horaire_numero_train", "cal_type_jour"])
        row = d[(d["base_date"] == date) & (d["horaire_numero_train"] == int(ntrain))]
        _TJ_CACHE[key] = str(row["cal_type_jour"].iloc[0]) if len(row) else "?"
    return _TJ_CACHE[key]
def type_jour_fr(date, ntrain):
    return TYPE_JOUR_FR.get(_type_jour(date, ntrain), _type_jour(date, ntrain))


if __name__ == "__main__":
    main()
