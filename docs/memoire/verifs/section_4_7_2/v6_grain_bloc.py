#!/usr/bin/env python3
"""
V6 — Projection de l'artefact au grain du bloc d'accouplement (section 4.7.2).

Le manuscrit mesure la precision de la pratique humaine au grain du bloc, entre
58,9 % et 66,8 % selon la definition du bloc, et indique que la projection
equivalente n'a pas ete faite cote artefact. Ce script la produit.

DIFFICULTE DE DEFINITION, NON TRANCHEE ICI
------------------------------------------
Un bloc humain est un fait REALISE : une suite maximale de courses consecutives
d'un meme vehicule effectivement accouplees (src/couche2/blocs.py:26-44). Une
recommandation de l'artefact ne designe pas un bloc de la meme maniere : elle
porte sur une course, et rien dans l'artefact ne dit combien de courses
consecutives l'accouplement recommande couvrirait. Deux operationnalisations sont
donc produites cote a cote, sans arbitrage :

  OP1 « bloc induit par la decision » — analogue structurel fidele. Chaque cote
      chaine ses PROPRES decisions : une suite maximale de courses consecutives
      d'un meme vehicule toutes decidees. C'est exactement la construction du
      bloc humain, ou le predicat « la course est une UM » est remplace par
      « la course est recommandee ». Reserve : le chainage mobilise l'affectation
      de vehicule des roulements, connue a posteriori, que l'artefact n'utilise
      pas a J-1.

  OP2 « partition exogene de roulement » — meme decoupage pour les deux cotes.
      Toutes les courses sont partitionnees en blocs de roulement realises
      (suites consecutives d'un meme vehicule, a composition realisee identique
      ou non selon la regle), independamment de toute decision. Un cote est
      credite d'un bloc des qu'il y engage au moins une course. Reserve : pour
      une course jamais accouplee, le bloc de roulement n'a pas la signification
      operationnelle d'une decision d'accouplement.

Les deux regles de bloc du manuscrit sont conservees dans chaque
operationnalisation : identite de composition (canonique) et consecutivite simple
(sensibilite).

Lecture seule stricte. Les valeurs humaines publiees sont REPRODUITES en garde
avant toute projection.

Sorties : docs/memoire/verifs/section_4_7/v6_*.csv
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import pandas as pd  # noqa: E402

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
from _garde import ROOT, garde  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
from couche2 import blocs, decision  # noqa: E402

OUT = _HERE
CALIB = ROOT / "outputs" / "couche2" / "q_couche2_calibration_H24_ba493568.json"
SEUIL = 63
ANNEE = "H25"

REGLES = {"identite_composition": "canonique (identite de composition)",
          "consecutivite_simple": "sensibilite (consecutivite simple)"}


# ── Chainage generalise : la construction de blocs.build_blocs, parametree ─────
def chainer(comp: pd.DataFrame, departs: dict, actif: dict, signature: dict,
            rule: str) -> dict:
    """Suites maximales de courses consecutives d'un meme vehicule toutes ACTIVES.

    Transposition litterale de src/couche2/blocs.py:220-261 : la structure de
    consecutivite mobilise TOUTES les courses rail du vehicule (y compris celles
    hors perimetre), une course non active rompt la chaine, et l'union-find
    fusionne les blocs quand une course porte plusieurs vehicules.

    actif      : {(date, numero_train) -> bool}   predicat de decision
    signature  : {(date, numero_train) -> tuple}  signature comparee si rule =
                 'identite_composition' (ignoree sinon)
    """
    seq: dict = {}
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

    for (_d, _v), courses in seq.items():
        courses = sorted(courses, key=lambda k: (departs.get(k) is None, departs.get(k), k[1]))
        prev = None
        for k in courses:
            if actif.get(k, False):
                find(k)
                meme = prev is not None and (
                    rule == "consecutivite_simple" or signature.get(prev) == signature.get(k))
                if meme:
                    union(prev, k)
                prev = k
            else:
                prev = None
    return {k: find(k) for k in actif if actif.get(k, False)}


def partition_roulement(comp: pd.DataFrame, departs: dict, signature: dict,
                        rule: str) -> dict:
    """Partition EXOGENE : toutes les courses rail sont chainees, sans predicat."""
    tous = {(d, n): True for d, n in comp[["date", "numero_train"]].itertuples(index=False)}
    return chainer(comp, departs, tous, signature, rule)


def _pr(x):
    return "n/d" if x is None else f"{100 * x:.1f} %"


def main() -> None:
    garde()
    print("=" * 78)
    print("V6 — PROJECTION DE L'ARTEFACT AU GRAIN DU BLOC")
    print("=" * 78)

    comp = blocs.load_composition()
    charge = blocs.load_charge()
    departs = blocs.load_departs()

    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)
    print(f"\n[1] Gardes : {info['n_h25']} courses {ANNEE} / {info['positives_h25']} surcharges")

    calib = json.loads(CALIB.read_text())
    tau_c = calib["regles_deployables"]["c_haute_precision"]["seuil"]
    tau_a = calib["regles_deployables"]["a_iso_volume"]["seuil"]
    print(f"    seuils H24 : c {tau_c:.2f} | a' {tau_a:.2f}")

    h25 = ds[ds["annee"] == ANNEE].copy()
    h25["reco_deploiement"] = (h25["score"] >= tau_c) | (h25["resa2c"] > SEUIL)
    h25["reco_a_plancher"] = (h25["score"] >= tau_a) | (h25["resa2c"] > SEUIL)
    h25["cle"] = list(zip(pd.to_datetime(h25["date"]), h25["numero_train"].astype(str)))

    # signature de composition realisee, par course (identique a blocs.py)
    signature = {(d, n): c for d, n, c in
                 comp[["date", "numero_train", "compo"]].itertuples(index=False)}

    # ── Garde : reproduction des valeurs humaines publiees ────────────────────
    print("\n[2] Garde — reproduction des valeurs humaines publiees (section 4.7.2)")
    m = comp.merge(charge, on=["date", "numero_train"], how="inner")
    m["annee"] = blocs.assign_annee(m.date)
    m_um = m[m.is_UM].copy()
    m_um["cle"] = list(zip(m_um["date"], m_um["numero_train"].astype(str)))
    um25 = m_um[m_um["annee"] == ANNEE]

    actif_um = {(d, n): bool(u) for d, n, u in
                comp[["date", "numero_train", "is_UM"]].itertuples(index=False)}
    garde_rows = []
    for rule in REGLES:
        bo = chainer(comp, departs, actif_um, signature, rule)
        sub = um25.copy()
        sub["bloc"] = [bo[k] for k in sub["cle"]]
        just = m_um.assign(bloc=[bo[k] for k in m_um["cle"]]).groupby("bloc")["surcharge_63"].max()
        bj = sub["bloc"].map(just)
        p = float(bj.sum()) / len(sub)
        garde_rows.append({"regle": rule, "base_um_mesurees_H25": len(sub),
                           "justif_course": int(sub["surcharge_63"].sum()),
                           "justif_bloc": int(bj.sum()),
                           "precision_bloc_pct": round(100 * p, 4)})
        print(f"    {REGLES[rule]:44} {int(bj.sum())}/{len(sub)} = {100 * p:.2f} % "
              f"(arrondi a une decimale : {100 * p:.1f} %)")
    pd.DataFrame(garde_rows).to_csv(OUT / "v6_garde_valeurs_humaines.csv", index=False)

    # ── Predicats de decision, cote a cote ────────────────────────────────────
    # ASYMETRIE DE PERIMETRE, documentee et quantifiee :
    # le bloc humain publie chaine les UM sur la structure physique COMPLETE, y
    # compris les UM sans mesure APC (914 UM dont 881 appariees). L'artefact, lui,
    # n'a de score que sur les 29 222 courses de l'iso-perimetre : une course hors
    # perimetre ne peut pas etre recommandee et rompt donc la chaine. Les deux
    # variantes humaines sont produites pour mesurer l'effet de cette asymetrie.
    COTES = {
        # variante publiee : predicat sur toute la structure (blocs.py:220-261)
        "humaine_UM_structure_complete": {(d, n): bool(u) for d, n, u in
                                          comp[["date", "numero_train", "is_UM"]]
                                          .itertuples(index=False)},
        # variante strictement iso-perimetre : comparable terme a terme a l'artefact
        "humaine_UM_iso_perimetre": {k: bool(v) for k, v in
                                     zip(h25["cle"], h25["is_UM"])},
        "artefact_deploiement_c_plancher": {k: bool(v) for k, v in
                                            zip(h25["cle"], h25["reco_deploiement"])},
        "artefact_a_plancher_iso_volume": {k: bool(v) for k, v in
                                           zip(h25["cle"], h25["reco_a_plancher"])},
    }
    label = dict(zip(h25["cle"], h25["label"].astype(bool)))
    seg = dict(zip(h25["cle"], h25["segment"]))
    perim = set(h25["cle"])

    # ── OP1 : bloc induit par la decision ─────────────────────────────────────
    print("\n[3] OP1 — bloc induit par la decision (analogue structurel fidele)")
    op1 = []
    for cote, actif in COTES.items():
        for rule in REGLES:
            bo = chainer(comp, departs, actif, signature, rule)
            cles = [k for k in bo if k in perim]
            bloc_of = {k: bo[k] for k in cles}
            dfb = pd.DataFrame({"cle": cles,
                                "bloc": [bloc_of[k] for k in cles],
                                "surch": [label[k] for k in cles],
                                "seg": [seg[k] for k in cles]})
            just = dfb.groupby("bloc")["surch"].max()
            dfb["bloc_justifie"] = dfb["bloc"].map(just)
            n = len(dfb)
            op1.append({"operationnalisation": "OP1_bloc_induit_par_la_decision",
                        "cote": cote, "regle_bloc": rule,
                        "courses_engagees": n,
                        "n_blocs": int(dfb["bloc"].nunique()),
                        "taille_moyenne_bloc": round(n / max(1, int(dfb["bloc"].nunique())), 2),
                        "courses_justifiees_au_grain_course": int(dfb["surch"].sum()),
                        "courses_justifiees_au_grain_bloc": int(dfb["bloc_justifie"].sum()),
                        "heritage": int((~dfb["surch"] & dfb["bloc_justifie"]).sum()),
                        "precision_course_pct": round(100 * float(dfb["surch"].mean()), 2),
                        "precision_bloc_pct": round(100 * float(dfb["bloc_justifie"].mean()), 2),
                        "blocs_justifies": int(just.sum()),
                        "precision_par_bloc_pct": round(100 * float(just.mean()), 2)})
            print(f"    {cote:34} {REGLES[rule]:44} "
                  f"{int(dfb['bloc_justifie'].sum())}/{n} = "
                  f"{_pr(float(dfb['bloc_justifie'].mean()))}")
    op1df = pd.DataFrame(op1)
    op1df.to_csv(OUT / "v6_op1_bloc_induit_precision.csv", index=False)

    # rappel OP1 : blocs de BESOIN = suites consecutives de courses surchargees
    print("\n[4] OP1 — rappel : blocs de besoin (suites consecutives de courses surchargees)")
    actif_besoin = {k: bool(label.get(k, False)) for k in perim}
    rap1 = []
    for rule in REGLES:
        bb = chainer(comp, departs, actif_besoin, signature, rule)
        besoin = pd.DataFrame({"cle": list(bb), "bloc": [bb[k] for k in bb]})
        n_blocs_besoin = besoin["bloc"].nunique()
        for cote, actif in COTES.items():
            besoin["couvert"] = [bool(actif.get(k, False)) for k in besoin["cle"]]
            cov = besoin.groupby("bloc")["couvert"].max()
            rap1.append({"operationnalisation": "OP1_bloc_induit_par_la_decision",
                         "cote": cote, "regle_bloc": rule,
                         "courses_en_surcharge": len(besoin),
                         "blocs_de_besoin": int(n_blocs_besoin),
                         "blocs_de_besoin_couverts": int(cov.sum()),
                         "rappel_bloc_pct": round(100 * float(cov.mean()), 2),
                         "rappel_course_pct": round(100 * float(besoin["couvert"].mean()), 2)})
            print(f"    {cote:34} {REGLES[rule]:44} "
                  f"{int(cov.sum())}/{int(n_blocs_besoin)} = {_pr(float(cov.mean()))}")
    rap1df = pd.DataFrame(rap1)
    rap1df.to_csv(OUT / "v6_op1_bloc_induit_rappel.csv", index=False)

    # ── OP2 : partition exogene de roulement ──────────────────────────────────
    print("\n[5] OP2 — partition exogene de roulement (meme decoupage des deux cotes)")
    op2, rap2 = [], []
    for rule in REGLES:
        part = partition_roulement(comp, departs, signature, rule)
        cles = [k for k in perim if k in part]
        base = pd.DataFrame({"cle": cles, "bloc": [part[k] for k in cles],
                             "surch": [label[k] for k in cles]})
        just = base.groupby("bloc")["surch"].max()
        n_blocs_besoin = int(just.sum())
        taille_moy = len(base) / max(1, base["bloc"].nunique())
        print(f"    [{REGLES[rule]}] blocs de roulement couvrant le perimetre : "
              f"{base['bloc'].nunique()} ; dont justifies : {n_blocs_besoin} ; "
              f"taille moyenne : {taille_moy:.1f} courses")
        for cote, actif in COTES.items():
            base["engage"] = [bool(actif.get(k, False)) for k in base["cle"]]
            eng = base[base["engage"]].copy()
            eng["bloc_justifie"] = eng["bloc"].map(just)
            op2.append({"operationnalisation": "OP2_partition_exogene_roulement",
                        "cote": cote, "regle_bloc": rule,
                        "blocs_de_roulement": int(base["bloc"].nunique()),
                        "taille_moyenne_bloc": round(taille_moy, 2),
                        "courses_engagees": len(eng),
                        "blocs_touches": int(eng["bloc"].nunique()),
                        "courses_justifiees_au_grain_course": int(eng["surch"].sum()),
                        "courses_justifiees_au_grain_bloc": int(eng["bloc_justifie"].sum()),
                        "heritage": int((~eng["surch"] & eng["bloc_justifie"]).sum()),
                        "precision_course_pct": round(100 * float(eng["surch"].mean()), 2),
                        "precision_bloc_pct": round(100 * float(eng["bloc_justifie"].mean()), 2)})
            touche = base.groupby("bloc")["engage"].max()
            couverts = int((touche & just).sum())
            rap2.append({"operationnalisation": "OP2_partition_exogene_roulement",
                         "cote": cote, "regle_bloc": rule,
                         "blocs_de_roulement": int(base["bloc"].nunique()),
                         "blocs_avec_surcharge": n_blocs_besoin,
                         "blocs_avec_surcharge_touches": couverts,
                         "rappel_bloc_pct": round(100 * couverts / max(1, n_blocs_besoin), 2)})
            print(f"      {cote:34} precision {_pr(float(eng['bloc_justifie'].mean())):8} "
                  f"| rappel {couverts}/{n_blocs_besoin} = "
                  f"{_pr(couverts / max(1, n_blocs_besoin))}")
    pd.DataFrame(op2).to_csv(OUT / "v6_op2_partition_exogene_precision.csv", index=False)
    pd.DataFrame(rap2).to_csv(OUT / "v6_op2_partition_exogene_rappel.csv", index=False)

    # ── Tableau de synthese : humain / artefact, cote a cote ──────────────────
    print("\n[6] Synthese — precision au grain du bloc, humain et artefact cote a cote")
    syn = pd.concat([op1df.assign(source="OP1"),
                     pd.DataFrame(op2).assign(source="OP2")], ignore_index=True)
    piv = syn.pivot_table(index=["operationnalisation", "regle_bloc"], columns="cote",
                          values="precision_bloc_pct")
    piv.to_csv(OUT / "v6_synthese_precision_bloc.csv")
    print(piv.to_string())
    print("\n    Grain course (rappel de reference, meme perimetre) :")
    ref = syn.drop_duplicates(["cote"]).set_index("cote")["precision_course_pct"]
    print(ref.to_string())

    print(f"\n[OK] sorties ecrites dans {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
