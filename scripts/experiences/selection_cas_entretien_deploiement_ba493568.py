#!/usr/bin/env python3
"""
Selection des 6 cas d'entretien - protocole 2.3 (guide v2.11), regle evaluee = CONFIGURATION
DE DEPLOIEMENT c UNION plancher (ADR-077, gel ba493568). Repartition 2 VP / 1 FP / 1 VN / 2 FN.

Tout est RE-DERIVE depuis q_couche2_deploiement_ba493568.json (implicitement, via la meme
chaine decision.py), le parquet H25, dim_rotations (composition) et dim_manifestations (noms) ;
aucune saisie manuelle de chiffres. Gardes en tete (29 222 / 2 072 / ba493568). Threads = 1.
Lecture seule sur les entrees ; ecrit uniquement les deux livrables.

ETANCHEITE (guide 2.2). Les elements qui souffleraient la reponse a la validation de H7
(limite 166, seuil de planification, raison de selection, paire 166+, annexe composition) sont
marques NOTES DE CONDUITE INTERVIEWEUR (affichage_repondant=false ; encadre dans le md). Le
support repondant (chantier suivant) n'affichera au bloc REALISE que : charge realisee,
composition roulee factuelle (UM / rame simple), decision humaine constatee.

Regles preenregistrees (protocole 2.3) implementees telles quelles :
 - critere primaire = severite de l'ecart charge predite/realisee au troncon le plus charge ;
 - FN (2) : tri charge realisee desc ; sous-regle FERME : 1 de la strate 166+ non captee + 1 FN
   forte intensite hors 166+ (variete d'intensite) ;
 - VP (2) : tri marge (charge-63) desc ; sous-regle FERME : 1 de la strate 166+ captee ; diversite
   de mecanisme (score seul / plancher joue / divergence outil-humain) ; conflit 166+ resa2c=0 :
   la strate PRIME, derogation consignee ;
 - FP (1) : ecart predit-realise le plus NET, voie score (le no-show a reservation est EXCUSE,
   non prioritaire) ; operationnalisation = max(score - charge) sur le sous-groupe franchement
   bas (charge < 40) ; departage (b) DURCI en preference de non-reutilisation de course ;
 - VN (1) : proche seuil sans franchir, silence correct (pas un cas trivialement vide) ;
 - diversite d'ensemble : >=1 course passant le haut ; >=1 semaine et >=1 week-end ; >=1 evenement
   ou reservation de groupe ;
 - departages : (a) pas deux memes dates ; (b) max 2 occurrences d'une course, jamais meme cellule,
   preference de non-reutilisation ; (c) contexte J-1 le plus riche ; (d) plus petit numero ;
 - hierarchie : repartition > diversite d'ensemble > sous-regles de strate > severite > departages.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision, blocs  # noqa: E402

SEUIL = decision.SEUIL                # seuil de surcharge 2C (63 assises, ADR-060)
CAP_RAME = 166                        # seuil de planification en personnes : projection de la
#                                       charge maximale admissible 12,7 t/rame (elicitation ecrite
#                                       du 2026-07-09 ; ADR-077 addendum ; statut H7 a l'entretien)
MD = ROOT / "docs/entretiens/cas_entretien_deploiement_ba493568.md"
JS = ROOT / "outputs/entretiens/cas_entretien_deploiement_ba493568.json"
EVENTS = ["event_is_manifestation_riviera", "event_is_ski_ouvert", "event_is_saison_narcisses",
          "event_is_ferie_vaud", "event_is_vacances_vaud", "event_is_montreux_jazz",
          "event_is_marche_noel"]
METEO = ["meteo_destination_temperature_h", "meteo_destination_precipitation_mm_h"]
HISTO = "histo_voyageurs_2eme_classe_win7_max"
RESA_DETAIL = ["resa_n_dossiers_J_minus_1", "resa_max_groupe_2c_J_minus_1",
               "resa_part_scolaire_J_minus_1", "resa_part_tour_operator_J_minus_1"]

NOTE_FAMILLES = ("l'outil s'appuie sur environ 160 variables appartenant a ces familles ; "
                 "les valeurs presentees sont les plus informatives pour ce cas")
NOTE_EVENEMENTS = ("* detail issu de la brochure source ; l'outil voit la presence et les "
                   "caracteristiques calendaires de l'evenement, pas son nom")
NOTE_HISTO = ("pic de charge 2e classe (troncon le plus charge) sur la fenetre glissante "
              "d'historique recent - feature win7_max, 7 dernieres occurrences au grain "
              "jour-type/service (ADR-039) ; connu a J-1 par construction")
USAGE_INTERVIEWEUR = ("usage intervieweur uniquement - ne pas afficher au repondant "
                      "(biais de presupposition, guide 2.2)")
ELICITATION_166 = ("conversion de la charge maximale admissible 12,7 t par rame, "
                   "elicitation ecrite du 2026-07-09")
NOTE_CONDUITE_H7 = ("hypothese H7 - restent a etablir en entretien : (1) source documentaire du "
                     "12,7 t (fiche materiel 7500 ou prescription d'exploitation) ; (2) convention "
                     "de conversion (poids moyen par personne) ; (3) statut operationnel du "
                     "depassement - amorce empirique : 4 des 6 occurrences 166+ ont roule en rame "
                     "simple (dont une a 182), le comptage peut donc depasser 166 sans empecher la marche")
OPERATIONNALISATION_FP = ("cas FP retenu = max(score - charge) sur le sous-groupe franchement bas "
                          "(charge < 40), voie score pure (le no-show a reservation est excuse). "
                          "Departage (b) DURCI en preference de non-reutilisation de course, motive "
                          "par la lisibilite de l'entretien : eviter qu'une meme course porte deux "
                          "erreurs opposees et focalise la discussion sur la ligne plutot que sur l'outil")
ZONE_ORDRE = {"zone_directe": 0, "zone_indirecte": 1, "hors_zone": 2}


# ═══════════════════════════════════════════════════════════════════════════════
# Sources d'enrichissement (composition roulee, noms d'evenements)
# ═══════════════════════════════════════════════════════════════════════════════
def load_composition_idx():
    comp = blocs.load_composition()
    comp["date_s"] = pd.to_datetime(comp["date"]).dt.strftime("%Y-%m-%d")
    return comp.set_index(["date_s", "numero_train"])


def load_events():
    ev = pd.read_parquet(ROOT / "data/dimension/dim_manifestations_riviera_evenements.parquet")
    ev["d0"] = pd.to_datetime(ev["date_debut"])
    ev["d1"] = pd.to_datetime(ev["date_fin"])
    return ev


def noms_evenements(ev, date_s, flag_manif):
    """Noms des manifestations actives ce jour (in-perimetre d'abord). Volet 3 : jamais le
    generique seul ; a defaut de libelle mais avec flag present, mention explicite."""
    d = pd.to_datetime(date_s)
    m = ev[(ev["d0"] <= d) & (ev["d1"] >= d)].copy()
    m["zo"] = m["zone_r35"].map(ZONE_ORDRE).fillna(3)
    m = m.sort_values(["zo", "nom"])
    inper = m[m["zone_r35"].isin(["zone_directe", "zone_indirecte"])]
    use = inper if len(inper) else m
    noms = [{"nom": r.nom, "zone": r.zone_r35} for r in use.head(3).itertuples()]
    if noms:
        return {"present": True, "noms": noms}
    if bool(flag_manif):
        return {"present": True, "noms": [],
                "libelle": "presence d'evenement au calendrier, libelle non retrouve"}
    return {"present": False, "noms": []}


def evenements_md(fam):
    if fam["noms"]:
        return ", ".join(f"{n['nom']} ({n['zone'].replace('_', ' ')})*" for n in fam["noms"])
    if fam.get("libelle"):
        return fam["libelle"]
    return "aucun evenement au calendrier"


# ═══════════════════════════════════════════════════════════════════════════════
# Construction H25 (matrice + contexte + troncon critique + enrichissements)
# ═══════════════════════════════════════════════════════════════════════════════
def build_H25():
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)              # gardes 29 222 / 2 072
    calib = json.loads((ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json").read_text())
    tau_c = calib["regles_deployables"]["c_haute_precision"]["seuil"]
    h = ds[ds["annee"] == "H25"].copy()
    resa = h["resa2c"].fillna(0)
    h["reco_c"] = h["score"] >= tau_c
    h["reco_pl"] = resa > SEUIL
    h["reco"] = h["reco_c"] | h["reco_pl"]
    h["voie"] = np.where(h["reco_c"] & h["reco_pl"], "les_deux",
                np.where(h["reco_c"], "score", np.where(h["reco_pl"], "plancher", "aucune")))
    h["cell"] = "VN"
    h.loc[h["reco"] & h["label"], "cell"] = "VP"
    h.loc[h["reco"] & ~h["label"], "cell"] = "FP"
    h.loc[~h["reco"] & h["label"], "cell"] = "FN"
    h["marge"] = h["charge_max"] - SEUIL

    # contexte course (parquet H25) : type de jour, calendrier, evenements, meteo, resa detail, histo
    cols = (["base_date", "horaire_numero_train", "cal_type_jour"] + EVENTS + METEO
            + RESA_DETAIL + [HISTO])
    ml = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet", columns=cols)
    ml["date"] = pd.to_datetime(ml["base_date"]).dt.normalize()
    ml["numero_train"] = ml["horaire_numero_train"].astype("Int64").astype(str)
    agg = {"cal_type_jour": ("cal_type_jour", "first")}
    for e in EVENTS:
        agg[e] = (e, "max")
    agg["temp"] = (METEO[0], "mean")
    agg["precip"] = (METEO[1], "max")
    agg["histo_win7_2c_max"] = (HISTO, "max")                    # pic recent au troncon le plus charge
    agg["resa_n_dossiers"] = (RESA_DETAIL[0], "max")
    agg["resa_max_groupe_2c"] = (RESA_DETAIL[1], "max")
    agg["resa_part_scolaire"] = (RESA_DETAIL[2], "max")
    agg["resa_part_to"] = (RESA_DETAIL[3], "max")
    ctx = ml.groupby(["date", "numero_train"]).agg(**agg).reset_index()
    h = h.merge(ctx, on=["date", "numero_train"], how="left")

    # troncon critique (max realise) : prediction, realise, ecart
    tr = decision.load_troncon_predictions()
    tr = tr[tr["annee"] == "H25"]
    idx = tr.groupby(["date", "numero_train"])["target"].idxmax()
    crit = tr.loc[idx, ["date", "numero_train", "pred", "target"]].rename(
        columns={"pred": "pred_crit", "target": "charge_crit"})
    h = h.merge(crit, on=["date", "numero_train"], how="left")
    h["ecart_crit"] = h["charge_crit"] - h["pred_crit"]
    h["semaine"] = pd.to_datetime(h["date"]).dt.dayofweek < 5     # calendrier : lundi-vendredi
    h["date_s"] = h["date"].dt.strftime("%Y-%m-%d")
    return h, tau_c, info


def evenement_str(r):
    """Libelle calendaire generique (categories vues par l'outil), pour la diversite/annexe."""
    m = []
    if r.event_is_manifestation_riviera: m.append("manifestation Riviera")
    if r.event_is_ski_ouvert: m.append("domaine skiable ouvert")
    if r.event_is_saison_narcisses: m.append("saison des narcisses")
    if r.event_is_ferie_vaud: m.append("jour ferie vaudois")
    if getattr(r, "event_is_montreux_jazz", False): m.append("Montreux Jazz")
    if getattr(r, "event_is_marche_noel", False): m.append("marche de Noel")
    return ", ".join(m) if m else "aucun"


def saison_str(r):
    s = []
    if r.event_is_ski_ouvert: s.append("domaine skiable ouvert")
    if r.event_is_saison_narcisses: s.append("saison des narcisses")
    return s


def lecture_166plus(charge, is_UM):
    """Volet 1b (reformule) : lecture explicite de la demande extreme, statut 166 = seuil de
    planification (projection de 12,7 t). NOTE INTERVIEWEUR. Chiffre re-derive."""
    c = int(round(charge))
    if is_UM:
        return (f"{c} voyageurs comptes dans l'UM roulee : la demande depassait le seuil de "
                f"planification de {CAP_RAME} personnes ({ELICITATION_166}) ; le doublement "
                f"etait indispensable et a ete fait.")
    return (f"{c} voyageurs comptes dans une rame SIMPLE : depassement constate du seuil de "
            f"planification de {CAP_RAME} personnes ({ELICITATION_166}).")


def main():
    h, tau_c, info = build_H25()
    comp = load_composition_idx()
    ev = load_events()

    def compo_of(r):
        key = (r.date_s, r.numero_train)
        if key in comp.index:
            c = comp.loc[key]
            return bool(c.is_UM), [str(v) for v in (c.vehicles or ())]
        return bool(r.is_UM), []

    pris_dates, pris_courses, pris_cellules = set(), {}, set()

    def dispo(cand, cell):
        if cand.date in pris_dates:                               # departage (a) : pas deux memes dates
            return False
        if (cand.numero_train, cell) in pris_cellules:            # departage (b) : jamais meme cellule
            return False
        if pris_courses.get(cand.numero_train, 0) >= 2:           # departage (b) : max 2 occurrences
            return False
        return True

    def prendre(cand, cell):
        pris_dates.add(cand.date)
        pris_courses[cand.numero_train] = pris_courses.get(cand.numero_train, 0) + 1
        pris_cellules.add((cand.numero_train, cell))

    def choisir(pool, cell, motif):
        # departage (b) durci : preferer une course non encore utilisee (2 passes)
        for prefer_unused in (True, False):
            for cand in pool.itertuples():
                if prefer_unused and cand.numero_train in pris_courses:
                    continue
                if dispo(cand, cell):
                    prendre(cand, cell)
                    return cand, motif
        return None, motif

    picks = []
    # --- strate 166+ d'abord (FERME) ---
    vp166 = h[(h.cell == "VP") & (h.charge_max >= CAP_RAME)].sort_values("marge", ascending=False)
    fn166 = h[(h.cell == "FN") & (h.charge_max >= CAP_RAME)].sort_values("charge_max", ascending=False)
    vp_s, mvs = choisir(vp166, "VP", "strate 166+ captee (marge de depassement max)")
    picks.append(("VP", vp_s, mvs,
                  "diversite de mecanisme non satisfaite (vivier 166+ a resa2c=0, voie score seule) ; la strate 166+ PRIME"))
    fn_s, mfs = choisir(fn166, "FN", "strate 166+ manquee (charge realisee max, departage date applique)")
    picks.append(("FN", fn_s, mfs, ""))

    # --- VP2 : diversite de mecanisme (plancher joue de preference, sinon divergence outil-humain) ---
    vp_pl = h[(h.cell == "VP") & (~h.reco_c) & (h.reco_pl) & (h.charge_max < CAP_RAME)].sort_values("marge", ascending=False)
    vp_dv = h[(h.cell == "VP") & (~h.is_UM) & (h.charge_max < CAP_RAME)].sort_values("marge", ascending=False)
    vp2, m2 = choisir(vp_pl, "VP", "diversite de mecanisme : plancher joue (resa>63, score<seuil)")
    if vp2 is None:
        vp2, m2 = choisir(vp_dv, "VP", "diversite de mecanisme : divergence outil-humain (VP modele, non-UM humain)")
    picks.append(("VP", vp2, m2, ""))

    # --- FN2 : hors 166+, forte intensite (charge realisee max) ---
    fn2p = h[(h.cell == "FN") & (h.charge_max < CAP_RAME)].sort_values("charge_max", ascending=False)
    fn2, mf2 = choisir(fn2p, "FN", "FN hors 166+ de forte intensite (charge realisee max, departages appliques)")
    picks.append(("FN", fn2, mf2, ""))

    # --- FP : ecart predit-realise le plus net (voie score pure ; no-show a reservation exclu car excuse) ---
    fpp = h[(h.cell == "FP") & (h.voie == "score") & (h.charge_max < 40)].copy()
    fpp["over_pred"] = fpp["score"] - fpp["charge_max"]
    fpp = fpp.sort_values("over_pred", ascending=False)
    fp, mfp = choisir(fpp, "FP", "ecart predit-realise le plus net (voie score pure ; no-show a reservation ecarte car excuse)")
    picks.append(("FP", fp, mfp, ""))

    # --- VN : proche seuil sans franchir, silence correct ---
    vnp = h[(h.cell == "VN") & (h.charge_max >= 56) & (h.charge_max <= 63)].sort_values(
        ["charge_max", "score"], ascending=[False, True])
    vn, mvn = choisir(vnp, "VN", "proche seuil (charge <=63) sans franchir, silence correct")
    picks.append(("VN", vn, mvn, ""))

    picks = [(c, r, m, n) for (c, r, m, n) in picks if r is not None]
    retenus_cell = {r.numero_train: c for c, r, m, n in picks}

    # --- note de conduite du 18 mai (fiche 1423) : l'autre 166+ du jour, double par l'humain, manque par l'outil ---
    def note_conduite_18mai(r):
        # meme date, autre course de la STRATE 166+, roulee en UM par l'humain mais manquee par l'outil
        same = h[(h.date_s == r.date_s) & (h.numero_train != r.numero_train)
                 & (h.is_UM) & (h.charge_max >= CAP_RAME) & (h.cell == "FN")]
        if same.empty:
            return None
        autres = ", ".join(f"{x.numero_train} ({int(round(x.charge_max))}, manquee par l'outil)"
                           for x in same.sort_values("charge_max", ascending=False).itertuples())
        return (f"le {r.date_s}, la pratique humaine a double {r.numero_train} ET {autres} (les deux 166+ du jour) : "
                f"l'humain a couvert les deux, l'outil une seule. A connaitre avant que le repondant "
                f"ne le dise ; ne pas l'exhiber spontanement (la relance QD3 est l'endroit si le sujet vient).")

    # --- diversite d'ensemble (verification) ---
    sel = pd.DataFrame([{"cellule": c, "date": r.date, "numero_train": r.numero_train,
                         "segment": r.segment, "semaine": bool(r.semaine),
                         "evenement": evenement_str(r), "resa": int(r.resa2c or 0)} for c, r, m, n in picks])
    diversite = {
        "au_moins_un_haut": bool((sel.segment == "haut").any()),
        "au_moins_une_semaine": bool(sel.semaine.any()),
        "au_moins_un_week_end": bool((~sel.semaine).any()),
        "au_moins_evenement_ou_resa": bool(((sel.evenement != "aucun") | (sel.resa > SEUIL)).any()),
    }

    # --- ecartes VP/FN/VN : 2-3 mieux classes non retenus par cellule ---
    def rows_ecartes(pool, retenus_trains, n=3):
        out = []
        for cand in pool.itertuples():
            if cand.numero_train in retenus_trains:
                continue
            motif = ("severite inferieure au retenu" if cand.date not in pris_dates and pris_courses.get(cand.numero_train, 0) < 2
                     else ("meme date qu'un cas retenu" if cand.date in pris_dates
                           else f"occurrence deja maximale de la course {cand.numero_train}"))
            out.append({"date": str(cand.date.date()), "train": cand.numero_train, "segment": cand.segment,
                        "charge": int(round(cand.charge_max)), "score": round(float(cand.score), 1),
                        "resa": int(cand.resa2c or 0), "voie": cand.voie, "ecarte_par": motif})
            if len(out) >= n:
                break
        return out

    # --- ecartes FP : inclut le plus severe meme s'il est une course retenue ailleurs (item 4) ---
    def rows_ecartes_fp(pool, fp_pick, n=4):
        out = []
        for cand in pool.itertuples():
            if cand.numero_train == fp_pick.numero_train and cand.date == fp_pick.date:
                continue                                          # le FP retenu lui-meme
            if cand.numero_train in retenus_cell:                 # course retenue ailleurs -> non-reutilisation
                motif = (f"course deja retenue ({retenus_cell[cand.numero_train]}) ; preference de "
                         f"non-reutilisation de course (durcissement volontaire de (b))")
            elif cand.date in pris_dates:
                motif = "meme date qu'un cas retenu"
            else:
                motif = "ecart predit-realise inferieur au retenu"
            out.append({"date": str(cand.date.date()), "train": cand.numero_train, "segment": cand.segment,
                        "charge": int(round(cand.charge_max)), "score": round(float(cand.score), 1),
                        "over_pred": round(float(cand.score - cand.charge_max), 1),
                        "resa": int(cand.resa2c or 0), "voie": cand.voie, "ecarte_par": motif})
            if len(out) >= n:
                break
        return out

    retenus = set(retenus_cell)
    ecartes = {
        "VP": rows_ecartes(vp166, retenus) + rows_ecartes(vp_pl, retenus, 2),
        "FN": rows_ecartes(fn166, retenus) + rows_ecartes(fn2p, retenus, 2),
        "FP": rows_ecartes_fp(fpp, fp, 4),
        "VN": rows_ecartes(vnp, retenus, 3),
    }

    # --- annexe : strate 166+ / composition roulee (volet 1a) - NOTE INTERVIEWEUR ---
    s166 = h[h.charge_max >= CAP_RAME].sort_values("charge_max", ascending=False)
    annexe_166 = []
    for i, r in enumerate(s166.itertuples(), 1):
        is_um, veh = compo_of(r)
        annexe_166.append({
            "rang": i, "date": r.date_s, "numero_train": r.numero_train,
            "charge_realisee": int(round(r.charge_max)),
            "capture_config": ("capte" if r.cell == "VP" else "manque"),
            "score": round(float(r.score), 1), "resa2c": int(r.resa2c or 0),
            "UM_roulee": is_um, "vehicules": veh,
            "lecture": (f"demande {int(round(r.charge_max))} comptee dans l'UM roulee "
                        f"({'+'.join(veh)}) : depasse {CAP_RAME}, doublement effectue" if is_um
                        else f"demande {int(round(r.charge_max))} comptee dans une rame SIMPLE "
                             f"({veh[0] if veh else '?'}) : depasse {CAP_RAME}, non doublee")})
    n_um = sum(a["UM_roulee"] for a in annexe_166)
    n_capte = sum(a["capture_config"] == "capte" for a in annexe_166)
    annexe_synthese = (f"{len(annexe_166)} occurrences ; {n_um} roulees en UM, "
                       f"{len(annexe_166) - n_um} en rame simple ; la configuration en capte {n_capte}/{len(annexe_166)}")

    # --- fiches (bloc J-1 par familles / bloc REALISE factuel / notes intervieweur separes) ---
    def fiche(cellule, r, motif, derog):
        is_um, veh = compo_of(r)
        saison = saison_str(r)
        ev_fam = noms_evenements(ev, r.date_s, r.event_is_manifestation_riviera)
        histo_val = None if pd.isna(r.histo_win7_2c_max) else round(float(r.histo_win7_2c_max), 1)
        familles = {
            "1_calendrier": {"type_jour": r.cal_type_jour,
                             "vacances_scolaires": bool(r.event_is_vacances_vaud),
                             "jour_ferie": bool(r.event_is_ferie_vaud),
                             "saison": saison if saison else "aucune"},
            "2_evenements": {**ev_fam, "note": NOTE_EVENEMENTS},
            "3_demande_annoncee": {"resa2c": int(r.resa2c or 0),
                                   "n_dossiers": int(r.resa_n_dossiers or 0),
                                   "max_groupe_2c": int(r.resa_max_groupe_2c or 0),
                                   "part_scolaire": round(float(r.resa_part_scolaire or 0), 2),
                                   "part_tour_operator": round(float(r.resa_part_to or 0), 2)},
            "4_meteo_prevue": {"temperature_C": round(float(r.temp), 1) if pd.notna(r.temp) else None,
                               "precip_mm": round(float(r.precip), 1) if pd.notna(r.precip) else None,
                               "note": "proxy realise, legerement favorable"},
            "5_historique_recent": {"histo_win7_2c_max": histo_val,
                                    "fenetre_complete": histo_val is not None,
                                    "definition": NOTE_HISTO},
        }
        # bloc J-1 : support repondant (familles + prediction outil), SANS la raison de selection
        j1 = {"identifiant": {"numero_train": r.numero_train, "date": r.date_s,
                              "type_jour": r.cal_type_jour},
              "segment": r.segment, "cellule": cellule,
              "charge_predite_troncon_critique": round(float(r.pred_crit), 1),
              "familles": familles,
              "mecanisme": {"score": round(float(r.score), 1), "seuil_c": round(tau_c, 2),
                            "score_atteint_seuil": bool(r.reco_c),
                            "resa2c": int(r.resa2c or 0), "plancher_63": bool(r.reco_pl),
                            "voie_de_capture": r.voie}}
        # bloc REALISE : factuel (charge, composition, decision humaine), SANS la lecture 166+
        realise = {"charge_realisee": int(round(r.charge_max)),
                   "charge_realisee_troncon_critique": int(round(r.charge_crit)),
                   "ecart_predit_realise_troncon_critique": round(float(r.ecart_crit), 1),
                   "composition_roulee": {"is_UM": is_um, "vehicules": veh,
                                          "libelle": "UM" if is_um else "rame simple"},
                   "decision_humaine_constatee": {"UM_roulee": bool(r.is_UM),
                                                  "divergence_outil_humain": bool(r.reco != r.is_UM)}}
        # notes intervieweur : etanches (jamais affichees au repondant)
        est_166 = r.charge_max >= CAP_RAME
        notes = {"affichage_repondant": False, "usage": USAGE_INTERVIEWEUR,
                 "raison_selection": motif + (f" | derogation : {derog}" if derog else ""),
                 "lecture_166plus": lecture_166plus(r.charge_max, is_um) if est_166 else None,
                 "note_conduite_H7": NOTE_CONDUITE_H7 if est_166 else None,
                 "note_conduite": note_conduite_18mai(r) if r.numero_train == "1423" else None}
        return {"cellule": cellule, "bloc_J1": j1, "bloc_REALISE": realise, "notes_intervieweur": notes}

    fiches = [fiche(c, r, m, n) for c, r, m, n in picks]

    matrice = h["cell"].value_counts().to_dict()
    preambule = {
        "protocole": "guide 2.3 (v2.11), selection de 6 cas d'entretien",
        "regle_evaluee": f"CONFIGURATION DE DEPLOIEMENT c (F0.5, seuil H24 = {tau_c:.2f}) UNION plancher (resa2c>63) - ADR-077",
        "matrice_config_H25": {"VP": int(matrice.get("VP", 0)), "FP": int(matrice.get("FP", 0)),
                               "FN": int(matrice.get("FN", 0)), "VN": int(matrice.get("VN", 0)),
                               "volume_recommande": int((h.cell.isin(["VP", "FP"])).sum())},
        "gardes": {"n_courses_H25": info["n_h25"], "n_positives_H25": info["positives_h25"], "hash": "ba493568"},
        "repartition": "2 VP / 1 FP / 1 VN / 2 FN (surcharges manquees surponderees, protocole 2.3)",
        "note_familles": NOTE_FAMILLES,
        "note_evenements": NOTE_EVENEMENTS,
        "operationnalisation_fp": OPERATIONNALISATION_FP,
        "assomption": ("l'echantillon surrepresente deliberement la strate extreme (2 cas 166+ sur 6, "
                       "contre 6 occurrences sur 2 072 surcharges) : echantillon CONTRASTE par protocole "
                       "(surponderation des cas d'echec comme test le plus severe), NON representatif de "
                       "l'activite moyenne de l'outil ; choix de design d'evaluation assume."),
        "paire_166plus": {
            "affichage_repondant": False, "usage": USAGE_INTERVIEWEUR,
            "texte": ("les six cas comportent deliberement une PAIRE 166+ (un capte, un manque), "
                      "materialisation de la limite seuil-sur-moyenne-conditionnelle != garantie des queues "
                      "(QD3, hypothese H7).")},
        "diversite_ensemble": diversite,
    }
    out = {"preambule": preambule, "fiches": fiches,
           "annexe_strate_166plus": {"affichage_repondant": False, "usage": USAGE_INTERVIEWEUR,
                                     "synthese": annexe_synthese, "cas": annexe_166},
           "ecartes": ecartes}
    JS.parent.mkdir(parents=True, exist_ok=True)
    JS.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # ═══════════════════════════════════════════════════════════════════════════
    # markdown
    # ═══════════════════════════════════════════════════════════════════════════
    def L(s=""): lines.append(s)
    lines = []
    L(f"# Cas d'entretien - configuration de deploiement c + plancher (`ba493568`)\n")
    L("## Preambule\n")
    L(f"- Protocole : {preambule['protocole']}.")
    L(f"- Regle evaluee : {preambule['regle_evaluee']}.")
    mm = preambule["matrice_config_H25"]
    L(f"- Matrice H25 (config deploiement) : VP {mm['VP']} / FP {mm['FP']} / FN {mm['FN']} / VN {mm['VN']} "
      f"(volume recommande {mm['volume_recommande']}). Gardes : {info['n_h25']} courses / {info['positives_h25']} surcharges, hash ba493568.")
    L(f"- Repartition : {preambule['repartition']}.")
    L(f"- Familles d'information : {NOTE_FAMILLES}.")
    L(f"- Operationnalisation du FP : {OPERATIONNALISATION_FP}.")
    L(f"- Assomption : {preambule['assomption']}")
    L(f"- Diversite d'ensemble : {json.dumps(diversite, ensure_ascii=False)}")
    L(f"- **Paire 166+ ({USAGE_INTERVIEWEUR})** : {preambule['paire_166plus']['texte']}\n")
    L("## Les six fiches\n")
    L(f"> Bloc J-1 organise en cinq familles fixes (calendrier, evenements, demande annoncee, meteo prevue, "
      f"historique recent), identiques sur les six cas. {NOTE_FAMILLES}. Le score, le seuil et la voie de "
      f"capture restent dans le mecanisme de decision (sortie de l'outil), hors familles.\n")
    L(f"> {NOTE_EVENEMENTS}.\n")
    L(f"> Etancheite (guide 2.2) : chaque fiche porte un encadre **notes de conduite intervieweur** "
      f"(raison de selection, lecture 166+, conduite H7) qui ne doit JAMAIS etre affiche au repondant.\n")
    for f in fiches:
        j, r, nt = f["bloc_J1"], f["bloc_REALISE"], f["notes_intervieweur"]
        idd = j["identifiant"]
        fam = j["familles"]
        L(f"### {f['cellule']} - course {idd['numero_train']}, {idd['date']} ({idd['type_jour']}), segment {j['segment']}\n")
        L("**Bloc J-1 (connu a la decision) - support repondant**\n")
        L(f"- Charge predite au troncon critique : {j['charge_predite_troncon_critique']}")
        cal = fam["1_calendrier"]
        sais = ", ".join(cal["saison"]) if isinstance(cal["saison"], list) else cal["saison"]
        L(f"- Famille 1 - Calendrier : type de jour = {cal['type_jour']} ; vacances scolaires = {cal['vacances_scolaires']} ; "
          f"jour ferie = {cal['jour_ferie']} ; saison = {sais}")
        L(f"- Famille 2 - Evenements du jour : {evenements_md(fam['2_evenements'])}")
        da = fam["3_demande_annoncee"]
        L(f"- Famille 3 - Demande annoncee : resa2c = {da['resa2c']} (dossiers = {da['n_dossiers']}, "
          f"plus gros groupe 2C = {da['max_groupe_2c']}, part scolaire = {da['part_scolaire']}, part tour-operator = {da['part_tour_operator']})")
        me = fam["4_meteo_prevue"]
        L(f"- Famille 4 - Meteo prevue : T = {me['temperature_C']} C, precip = {me['precip_mm']} mm ({me['note']})")
        hi = fam["5_historique_recent"]
        hv = hi["histo_win7_2c_max"]
        L(f"- Famille 5 - Historique recent : histo_win7 (2C) = {hv if hv is not None else 'fenetre incomplete (debut d horaire)'} "
          f"[{hi['definition']}]")
        mec = j["mecanisme"]
        L(f"- Mecanisme de decision (sortie outil) : score {mec['score']} (seuil c {mec['seuil_c']}, atteint={mec['score_atteint_seuil']}) ; "
          f"resa2c {mec['resa2c']} (plancher 63={mec['plancher_63']}) ; voie de capture = {mec['voie_de_capture']}")
        L("\n**Bloc REALISE (revele apres) - support repondant : factuel**\n")
        cr = r["composition_roulee"]
        compo_txt = (f"UM ({'+'.join(cr['vehicules'])})" if cr["is_UM"]
                     else f"rame simple ({cr['vehicules'][0] if cr['vehicules'] else '?'})")
        L(f"- Charge realisee : {r['charge_realisee']} (troncon critique {r['charge_realisee_troncon_critique']}) ; "
          f"ecart predit-realise (troncon critique) = {r['ecart_predit_realise_troncon_critique']}")
        L(f"- Composition roulee : {compo_txt}")
        dh = r["decision_humaine_constatee"]
        L(f"- Decision humaine constatee : UM roulee = {dh['UM_roulee']} ; divergence outil-humain = {dh['divergence_outil_humain']}")
        # encadre notes de conduite intervieweur
        L(f"\n> **Notes de conduite - {USAGE_INTERVIEWEUR}**")
        L(f">")
        L(f"> - Raison de selection : {nt['raison_selection']}")
        if nt["lecture_166plus"]:
            L(f"> - Lecture 166+ : {nt['lecture_166plus']}")
        if nt["note_conduite_H7"]:
            L(f"> - Conduite H7 : {nt['note_conduite_H7']}")
        if nt["note_conduite"]:
            L(f"> - Conduite (18 mai) : {nt['note_conduite']}")
        L("")
    # --- annexe strate 166+ (note intervieweur) ---
    L(f"## Annexe - strate 166+ et composition roulee (volet C) - {USAGE_INTERVIEWEUR}\n")
    L(f"{annexe_synthese}.\n")
    L("| Rang | Date | Course | Charge | Capture config | Score | resa2c | Composition roulee | Lecture |")
    L("|---|---|---|---|---|---|---|---|---|")
    for a in annexe_166:
        compo = (f"UM {'+'.join(a['vehicules'])}" if a["UM_roulee"]
                 else f"simple {a['vehicules'][0] if a['vehicules'] else '?'}")
        L(f"| {a['rang']} | {a['date']} | {a['numero_train']} | {a['charge_realisee']} | {a['capture_config']} "
          f"| {a['score']} | {a['resa2c']} | {compo} | demande comptee "
          f"{'en UM' if a['UM_roulee'] else 'en rame SIMPLE'} |")
    L("")
    # --- ecartes ---
    L("## Ecartes (auditabilite de la non-selection)\n")
    for cell, rows in ecartes.items():
        L(f"**{cell}**")
        for e in rows:
            op = f", over_pred {e['over_pred']}" if "over_pred" in e else ""
            L(f"- {e['date']} course {e['train']} ({e['segment']}) : charge {e['charge']}, score {e['score']}{op}, "
              f"resa {e['resa']}, voie {e['voie']} -> ecarte : {e['ecarte_par']}")
        L("")
    MD.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines))

    # --- impression console ---
    print(f"Matrice deploiement H25 : {mm}")
    print(f"Diversite d'ensemble : {diversite}")
    print(f"Annexe 166+ : {annexe_synthese}")
    print("Ecartes FP (dont le plus severe) :")
    for e in ecartes["FP"]:
        print(f"  {e['date']} {e['train']} charge={e['charge']} score={e['score']} over_pred={e.get('over_pred')} -> {e['ecarte_par']}")
    print("Les 6 cas :")
    for c, r, m, n in picks:
        is_um, veh = compo_of(r)
        print(f"  {c:3} {r.date_s} {r.numero_train} {r.segment:4} ch={int(round(r.charge_max)):3} "
              f"sc={r.score:6.1f} resa={int(r.resa2c or 0):3} histo={r.histo_win7_2c_max} "
              f"UMh={int(r.is_UM)} veh={veh} voie={r.voie}")
    print(f"[OK] {MD.relative_to(ROOT)} + {JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
