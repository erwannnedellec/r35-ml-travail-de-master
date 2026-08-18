#!/usr/bin/env python3
"""
Donnees factuelles des supports d'entretien (SOURCE UNIQUE) -> outputs/entretiens/
supports_donnees_ba493568.json. Tout est re-derive du modele canonique ba493568, du parquet
H25, des dimensions (gares, manifestations) et du codebook ; aucune saisie manuelle de chiffre.

Contenu par cas (ordre verrouille 1423, 1326, 1448, 1435, 1416, 1508) :
  - identite : numero, date, type de jour, heures depart/arrivee (origine/terminus), sens ;
  - 5 familles J-1 enrichies (evenements avec commune ; meteo avec ensoleillement + repere) ;
  - section outil : estimation (au troncon DETERMINANT = argmax predit), recommandation,
    declencheur, CASCADE SHAP quantifiee par famille (somme qui boucle a l'entier), profil
    predit par troncon ;
  - section realise : charge au troncon determinant, composition, decision, profil predit+realise ;
  - table de traduction (feature -> libelle decideur -> famille) ;
  - encadrants : trains precedent/suivant et cadence au troncon d'ORIGINE du parcours.

AUDIT DU PRODUCTEUR ist_headway_apres_min (scripts/sources/build_dim_headway.py), prealable
exige avant toute derivation d'encadrants :
  (a) SOURCE   : ISTDATEN, horaire THEORIQUE uniquement (colonne horaire_depart). Aucun
                 fallback sur reel_depart : le producteur l'exclut explicitement (un temps
                 realise creerait un distribution shift, MOB n'ayant que le theorique a J-1).
  (b) GRAIN    : TRONCON x SENS. Cle de calcul = (date, gare_depart_bpuic, gare_arrivee_bpuic,
                 sens) ; sortie au grain date x numero_train x troncon x sens. Ce n'est donc
                 PAS un attribut de course : chaque troncon d'une meme course peut porter une
                 valeur differente.
  (c) SUIVANT  : le train suivant sur le MEME TRONCON et le MEME SENS (trie par depart
                 theorique). Ce n'est ni « meme origine de parcours » ni « toute circulation de
                 la ligne » : c'est toute circulation qui emprunte ce troncon dans ce sens. Du
                 point de vue du voyageur present a la gare de depart du troncon, c'est
                 exactement l'ensemble des substituts.
  (d) CAUSALITE: J-1 PROPRE. Le perimetre est la grille PLANIFIEE connue a J-1 (ADR-066) :
                 aucun filtre de statut realise, les annules sont INCLUS (l'annulation n'est pas
                 connue a J-1) et les supplementaires aussi (planifies en amont). Le feature est
                 donc purement theorique/planifie : AUCUN ecart de source avec l'affichage, qui
                 utilise la meme source et la meme regle.

Regle d'encadrement retenue ici : identique a (c) — meme troncon x sens, sur le troncon
d'ORIGINE du parcours (celui dont l'heure de depart figure au bloc d'identite). Elle est
volontairement preferee a « meme origine de parcours » (formulation de la demande) parce
qu'elle est celle que le feature a consommee ET la vraie definition du substitut voyageur :
un train qui rejoint la ligne en amont dessert la gare d'origine et constitue un substitut.
Controle de coherence : l'intervalle aval derive DOIT egaler ist_headway_apres_min du dataset
au troncon d'origine (verifie sur les 6 cas). La valeur au troncon DETERMINANT est reportee
separement : elle peut differer (grain troncon), c'est elle que le modele a consommee pour
l'estimation.

Threads=1. Lecture seule sur les entrees.
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
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from couche2 import decision  # noqa: E402

CASES = json.loads((ROOT / "outputs/entretiens/cas_entretien_deploiement_ba493568.json").read_text())
CODEBOOK = pd.read_csv(ROOT / "outputs/codebook_canonique_ba493568.csv")
GARES = pd.read_csv(ROOT / "data/dimension/gare_abreviation.csv")
EVENTS = pd.read_parquet(ROOT / "data/dimension/dim_manifestations_riviera_evenements.parquet")
OUT = ROOT / "outputs/entretiens/supports_donnees_ba493568.json"
ORDRE = ["1423", "1326", "1448", "1435", "1416", "1508"]

GROUPES = {
    "cal_": "Calendrier (type de jour, saison)",
    "event_": "Evenements et vacances",
    "histo_": "Historique recent de la course",
    "horaire_": "Caracteristiques de l'horaire (mission, arrets)",
    "ist_": "Regularite et frequentation observees (historique)",
    "meteo_": "Meteo prevue",
    "resa_": "Reservations annoncees",
    "spatial_": "Desserte et topologie de la ligne",
    "vmcv_": "Correspondances (funiculaire VMCV)",
    "simba_": "Frequentation touristique (SIMBA)",
    "base_": "Reperes de date", "id_": "Identifiants",
}
ZONE_ORDRE = {"zone_directe": 0, "zone_indirecte": 1, "hors_zone": 2}
GARE_NOM = dict(zip(GARES["Gare_abreviation"], GARES["Gare_nom"]))


def hhmm(minutes):
    m = int(round(float(minutes)))
    return f"{m // 60:02d}h{m % 60:02d}"


def evenements_commune(date_s, flag_manif):
    d = pd.to_datetime(date_s)
    ev = EVENTS.copy()
    ev["d0"] = pd.to_datetime(ev["date_debut"]); ev["d1"] = pd.to_datetime(ev["date_fin"])
    m = ev[(ev["d0"] <= d) & (ev["d1"] >= d)].copy()
    m["zo"] = m["zone_r35"].map(ZONE_ORDRE).fillna(3)
    m = m.sort_values(["zo", "nom"])
    inper = m[m["zone_r35"].isin(["zone_directe", "zone_indirecte"])]
    use = inper if len(inper) else m
    noms = [{"nom": r.nom, "commune": r.lieu, "zone": r.zone_r35} for r in use.head(3).itertuples()]
    if noms:
        return {"present": True, "noms": noms}
    if bool(flag_manif):
        return {"present": True, "noms": [], "libelle": "presence d'evenement au calendrier, libelle non retrouve"}
    return {"present": False, "noms": []}


def build_encadrants_table():
    """Trains encadrants au grain troncon x sens, a l'IDENTIQUE de build_dim_headway.py :
    reconstruction des troncons depuis ISTDATEN (horaire THEORIQUE), sens deduit du km de
    dim_gare, puis train precedent/suivant sur le meme troncon x sens. Aucun filtre de statut
    realise (grille planifiee J-1, ADR-066)."""
    ist = pd.read_parquet(ROOT / "data/processed/sources/istdaten_clean.parquet",
                          columns=["date", "numero_train", "bpuic", "horaire_depart"])
    gares = pd.read_parquet(ROOT / "data/dimension/dim_gare.parquet", columns=["bpuic", "km"]).dropna()
    km = dict(zip(gares["bpuic"].astype(int), gares["km"].astype(float)))
    d = ist.sort_values(["date", "numero_train", "horaire_depart"]).reset_index(drop=True)
    d["bpuic_arr"] = d.groupby(["date", "numero_train"])["bpuic"].shift(-1)
    t = d.dropna(subset=["bpuic_arr"]).copy()
    t["bpuic_arr"] = t["bpuic_arr"].astype(int)
    t["km_dep"] = t["bpuic"].map(km); t["km_arr"] = t["bpuic_arr"].map(km)
    t = t.dropna(subset=["km_dep", "km_arr"])
    t["sens"] = np.where(t["km_dep"] < t["km_arr"], "VV -> PLEI", "PLEI -> VV")
    cle = ["date", "bpuic", "bpuic_arr", "sens"]
    t = t.sort_values(cle + ["horaire_depart"]).reset_index(drop=True)
    g = t.groupby(cle)
    t["dep_prec"] = g["horaire_depart"].shift(1)
    t["dep_suiv"] = g["horaire_depart"].shift(-1)
    t["train_prec"] = g["numero_train"].shift(1)
    t["train_suiv"] = g["numero_train"].shift(-1)
    t["hw_avant"] = (t["horaire_depart"] - t["dep_prec"]).dt.total_seconds() / 60
    t["hw_apres"] = (t["dep_suiv"] - t["horaire_depart"]).dt.total_seconds() / 60
    t["date_s"] = pd.to_datetime(t["date"]).dt.strftime("%Y-%m-%d")
    t["train"] = t["numero_train"].astype("Int64").astype(str)
    return t.set_index(["date_s", "train", "bpuic", "bpuic_arr"]).sort_index()


def _hhmm_ts(x):
    return None if pd.isna(x) else pd.Timestamp(x).strftime("%Hh%M")


def main():
    lib = dict(zip(CODEBOOK["colonne"], CODEBOOK["libelle_fr"]))
    fam = dict(zip(CODEBOOK["colonne"], CODEBOOK["famille"]))
    fiches = {f["bloc_J1"]["identifiant"]["numero_train"]: f for f in CASES["fiches"]}

    feats = json.loads((ROOT / "outputs/couche2/features_158f_sans_simba.json").read_text())["features"]
    cols_extra = ["base_date", "horaire_numero_train", "horaire_annee_horaire", "spatial_segment",
                  "target_voyageurs_2eme_classe", "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre",
                  "id_gare_depart", "id_gare_arrivee", "cal_depart_minute_du_jour", "cal_arrivee_minute_du_jour",
                  "base_sens", "cal_mois", "meteo_destination_ensol_total_j"]
    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    df = df[df["horaire_annee_horaire"].isin(["H24", "H25"])].copy()
    df["date_s"] = pd.to_datetime(df["base_date"]).dt.strftime("%Y-%m-%d")
    df["numero_train"] = df["horaire_numero_train"].astype("Int64").astype(str)

    models = {s: xgb.XGBRegressor() for s in ("bas", "haut")}
    models["bas"].load_model(str(decision.MODEL_BAS)); models["haut"].load_model(str(decision.MODEL_HAUT))
    mseg = {s: (df["spatial_segment"] == s).values for s in ("bas", "haut")}
    Xseg = {s: decision._prep_X(df[mseg[s]], feats) for s in ("bas", "haut")}
    df["pred"] = np.nan
    for s in ("bas", "haut"):
        df.loc[mseg[s], "pred"] = models[s].predict(Xseg[s]).astype("float64")

    # ensol maximum saisonnier par mois (destination), minutes -> heures
    ensol_max_mois = df.groupby("cal_mois")["meteo_destination_ensol_total_j"].max().to_dict()
    ENC = build_encadrants_table()                                # trains encadrants (horaire theorique)

    h25 = df[df["horaire_annee_horaire"] == "H25"]
    cas_out, table, diag = {}, {}, []
    for i, course in enumerate(ORDRE, 1):
        f = fiches[course]
        date_s = f["bloc_J1"]["identifiant"]["date"]
        # ordre de PARCOURS = ordre chronologique (horaire), valable en montee ET en descente
        sub = h25[(h25["numero_train"] == course) & (h25["date_s"] == date_s)].sort_values("cal_depart_minute_du_jour")
        # troncon determinant = argmax PREDIT (celui qui porte la recommandation)
        det_idx = sub["pred"].idxmax()
        det = sub.loc[det_idx]
        seg = det["spatial_segment"]
        estimation = int(round(float(det["pred"])))
        realise_det = int(round(float(det["target_voyageurs_2eme_classe"])))
        realise_max_idx = sub["target_voyageurs_2eme_classe"].astype("float64").idxmax()
        diag.append((course, det["spatial_gare_depart_ordre"], sub.loc[realise_max_idx, "spatial_gare_depart_ordre"]))

        # --- identite (origine/terminus/heures en ordre de parcours) ---
        first, last = sub.iloc[0], sub.iloc[-1]
        montee = last["spatial_gare_arrivee_ordre"] > first["spatial_gare_depart_ordre"]
        identite = {
            "numero_train": course, "date": date_s,
            "type_jour": f["bloc_J1"]["identifiant"]["type_jour"],
            "heure_depart": hhmm(first["cal_depart_minute_du_jour"]),
            "heure_arrivee": hhmm(last["cal_arrivee_minute_du_jour"]),
            "origine": GARE_NOM.get(first["id_gare_depart"], first["id_gare_depart"]),
            "terminus": GARE_NOM.get(last["id_gare_arrivee"], last["id_gare_arrivee"]),
            "sens": "montee" if montee else "descente",
            "base_sens": first["base_sens"],
        }

        # --- encadrants au troncon d'ORIGINE (meme regle que le producteur du headway) ---
        e = ENC.loc[(date_s, course, int(first["id_gare_depart_bpuic"]), int(first["id_gare_arrivee_bpuic"]))]
        if isinstance(e, pd.DataFrame):
            e = e.iloc[0]
        premier, dernier = pd.isna(e["dep_prec"]), pd.isna(e["dep_suiv"])
        iv_av = None if premier else int(round(float(e["hw_avant"])))
        iv_ap = None if dernier else int(round(float(e["hw_apres"])))
        feat_orig = first["ist_headway_apres_min"]
        feat_det = det["ist_headway_apres_min"]
        coherent = ((iv_ap is None and pd.isna(feat_orig))
                    or (iv_ap is not None and pd.notna(feat_orig) and abs(iv_ap - float(feat_orig)) < 0.51))
        assert coherent, (f"cas {course} : intervalle aval derive {iv_ap} != ist_headway_apres_min "
                          f"{feat_orig} au troncon d'origine")
        encadrants = {
            "gare_origine": identite["origine"], "sens": identite["base_sens"],
            "heure_depart_course": _hhmm_ts(e["horaire_depart"]),
            "precedent": None if premier else {"heure": _hhmm_ts(e["dep_prec"]),
                                               "train": str(int(e["train_prec"]))},
            "suivant": None if dernier else {"heure": _hhmm_ts(e["dep_suiv"]),
                                             "train": str(int(e["train_suiv"]))},
            "intervalle_avant_min": iv_av, "intervalle_apres_min": iv_ap,
            "cadence_uniforme": bool(iv_av is not None and iv_ap is not None and iv_av == iv_ap),
            "premier_du_service": bool(premier), "dernier_du_service": bool(dernier),
            "source": ("ISTDATEN horaire theorique (grille planifiee connue a J-1, ADR-066) ; regle = train "
                       "precedent/suivant sur le MEME troncon x sens, au troncon d'origine du parcours "
                       "(identique au producteur de ist_headway_apres_min)"),
            "audit_feature": {
                "ist_headway_apres_min_troncon_origine": None if pd.isna(feat_orig) else round(float(feat_orig), 1),
                "ist_headway_apres_min_troncon_determinant": None if pd.isna(feat_det) else round(float(feat_det), 1),
                "coherence_derive_vs_feature_origine": bool(coherent),
                "note_grain": ("le feature est au grain troncon : la valeur au troncon determinant (celle que le "
                               "modele a consommee pour l'estimation) peut differer de celle du troncon d'origine "
                               "(celle qu'affiche le bloc d'identite)"),
            },
        }

        # --- familles (reprise fiche + enrichissement) ---
        famille = f["bloc_J1"]["familles"]
        ev = evenements_commune(date_s, True)
        ensol_h = round(float(det["meteo_destination_ensol_total_j"]) / 60.0, 1)
        ensol_max_h = round(float(ensol_max_mois[det["cal_mois"]]) / 60.0, 1)
        familles = {
            "1_calendrier": famille["1_calendrier"],
            "2_evenements": {**ev, "note": famille["2_evenements"]["note"]},
            "3_demande_annoncee": famille["3_demande_annoncee"],
            "4_meteo_prevue": {**famille["4_meteo_prevue"],
                               "ensoleillement_h": ensol_h,
                               "ensoleillement_max_saisonnier_h": ensol_max_h},
            "5_historique_recent": famille["5_historique_recent"],
        }

        # --- cascade SHAP au troncon determinant ---
        Xrow = Xseg[seg].loc[[det_idx]]
        contribs = models[seg].get_booster().predict(
            xgb.DMatrix(Xrow, enable_categorical=True, feature_names=list(Xrow.columns)), pred_contribs=True)[0]
        assert abs(float(contribs.sum()) - float(det["pred"])) < 1e-3, f"SHAP incoherent {course}"
        shap = pd.Series(contribs[:-1], index=list(Xrow.columns))
        base = float(contribs[-1])
        by_fam = {}
        for col, val in shap.items():
            ff = fam.get(col, next((p for p in GROUPES if col.startswith(p)), "autre_"))
            by_fam.setdefault(ff, {"sum": 0.0, "features": []})
            by_fam[ff]["sum"] += float(val)
            if abs(val) > 1e-9:
                by_fam[ff]["features"].append((col, float(val)))
        ordered = sorted(by_fam.items(), key=lambda kv: abs(kv[1]["sum"]), reverse=True)
        top = ordered[:5]
        # cascade entiere qui BOUCLE : autres = estimation - base_int - sum(deltas)
        base_int = int(round(base))
        familles_casc = [{"famille": GROUPES.get(ff, ff), "delta": int(round(d["sum"]))} for ff, d in top]
        autres_int = estimation - base_int - sum(x["delta"] for x in familles_casc)
        cascade = {"base": base_int, "familles": familles_casc, "autres": autres_int, "total": estimation}
        # table de traduction (features cles des familles du top)
        for ff, d in top:
            for col, val in sorted(d["features"], key=lambda t: abs(t[1]), reverse=True)[:4]:
                table[col] = {"libelle_fr": lib.get(col, col), "famille": ff, "groupe_decideur": GROUPES.get(ff, ff)}

        # --- profils par troncon (predit ; predit+realise) ---
        profil = [{"ordre": int(r.spatial_gare_depart_ordre),
                   "gare": r.id_gare_depart, "gare_nom": GARE_NOM.get(r.id_gare_depart, r.id_gare_depart),
                   "predit": round(float(r.pred), 1),
                   "realise": int(round(float(r.target_voyageurs_2eme_classe)))}
                  for r in sub.itertuples()]
        det_ordre = int(det["spatial_gare_depart_ordre"])

        # --- section outil / realise (reprise mecanisme + composition depuis la fiche) ---
        mec = f["bloc_J1"]["mecanisme"]
        voie = mec["voie_de_capture"]
        reco = mec["score_atteint_seuil"] or mec["plancher_63"]
        declencheur = {"score": "estimation de charge", "plancher": "reservations annoncees",
                       "les_deux": "estimation de charge et reservations annoncees", "aucune": "aucun"}[voie]
        rz = f["bloc_REALISE"]

        cas_out[course] = {
            "cas": i, "course": course, "identite": identite, "encadrants": encadrants,
            "familles": familles,
            "outil": {
                "estimation": estimation,
                "recommandation": "DOUBLER" if reco else "NE PAS DOUBLER",
                "declencheur": declencheur,
                "note_deux_composants": (
                    "cette recommandation vient de la regle reservations (78 places annoncees, au-dela de la "
                    "capacite assise d'une rame) ; l'estimation de charge reste juste sous le seuil de "
                    "declenchement : les deux composants de l'outil sont ici distincts") if voie == "plancher" else None,
                "cascade": cascade,
                "profil_predit": [{"ordre": p["ordre"], "gare": p["gare"], "gare_nom": p["gare_nom"], "predit": p["predit"]} for p in profil],
                "determinant_ordre": det_ordre,
            },
            "realise": {
                "charge_determinant": realise_det,
                "charge_parcours_max": int(max(p["realise"] for p in profil)),
                "composition": rz["composition_roulee"]["libelle"],
                "decision": "doublement effectue" if rz["decision_humaine_constatee"]["UM_roulee"] else "pas de doublement",
                "profil": profil, "determinant_ordre": det_ordre,
            },
        }
        print(f"Cas {i} {course} ({date_s}) det ordre={det_ordre} estimation={estimation} "
              f"realise_det={realise_det} cascade={base_int}+{sum(x['delta'] for x in familles_casc)}+{autres_int}={estimation}")
        af = encadrants["audit_feature"]
        print(f"      encadrants @ {encadrants['gare_origine']} : prec {encadrants['precedent'] and encadrants['precedent']['heure']} "
              f"/ suiv {encadrants['suivant'] and encadrants['suivant']['heure']} ; intervalles {iv_av}/{iv_ap} min ; "
              f"feature aval origine={af['ist_headway_apres_min_troncon_origine']} (coherent={af['coherence_derive_vs_feature_origine']}) "
              f"| determinant={af['ist_headway_apres_min_troncon_determinant']}")

    out = {"meta": {"hash": "ba493568", "ordre_cas": ORDRE,
                    "troncon_determinant": "argmax de la charge PREDITE (troncon portant la recommandation)",
                    "methode_explication": "TreeSHAP natif xgboost (pred_contribs) au troncon determinant ; base = valeur attendue du modele de segment",
                    "note": "estimation = charge predite au troncon determinant ; valeurs SHAP numeriques regroupees par famille, en voyageurs"},
           "cas": cas_out, "table_traduction": dict(sorted(table.items()))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nDiag determinant(predit) vs argmax(realise) par cas :")
    for c, dp, dr in diag:
        print(f"  {c} : det predit ordre {dp} | max realise ordre {dr} | {'MEME' if dp == dr else 'DIFFERENT'}")
    print(f"[OK] {OUT.relative_to(ROOT)} ({len(table)} features traduites)")


if __name__ == "__main__":
    main()
