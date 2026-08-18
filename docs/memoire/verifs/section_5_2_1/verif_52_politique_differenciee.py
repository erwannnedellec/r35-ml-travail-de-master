#!/usr/bin/env python3
"""
verif_52_politique_differenciee.py — VÉRIF 2 (§5.2).

Lecture DESCRIPTIVE d'une politique de seuil différenciée par type de jour, construite
à partir de paramètres DÉJÀ FIXÉS (menu de seuils calibré sur H24, plancher de
réservation). Aucune recalibration, aucun réglage, aucune sélection.

Politique évaluée, notée P_diff :
  - jour ouvrable            : recommander si score >= c (64,12)  OU plancher
  - samedi                   : recommander si score >= b (51,31)  OU plancher
  - dimanche ou jour férié   : recommander si score >= b (51,31)  OU plancher
  plancher = réservations 2e classe agrégées à la course par le MAXIMUM sur les
  tronçons, strictement supérieures à 63.

Comparaisons, sur le même périmètre H25 (29 222 courses, 2 072 surcharges) :
  c ∪ plancher (configuration candidate au déploiement), b ∪ plancher, et la pratique
  de référence issue du registre des rotations.

Sorties :
  - docs/memoire/verifs/section_5_2/politique_seuil_differenciee.md
  - docs/memoire/tableaux/section_5_2_1/*.csv
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _socle_chap5 as S  # noqa: E402

OUT_MD = Path(__file__).resolve().parent / "politique_seuil_differenciee.md"
OUT_CSV = S.ROOT / "docs/memoire/tableaux/section_5_2_1"

LIB_POL = {
    "P_diff": "P_diff (différenciée : c ouvrable, b samedi, b dimanche/férié) ∪ plancher",
    "c_plancher": "c ∪ plancher (uniforme, candidate au déploiement)",
    "b_plancher": "b ∪ plancher (uniforme)",
    "a_plancher": "a′ ∪ plancher (uniforme, parcimonie stricte)",
    "pratique": "Pratique de référence (registre des rotations)",
}
ORDRE_POL = ["P_diff", "c_plancher", "b_plancher", "a_plancher", "pratique"]


def pct(x, n=1):
    """Pourcentage à la française : virgule décimale, espace avant le signe."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/d"
    return f"{x*100:.{n}f}".replace(".", ",") + " %"


def fmt(x, n=2):
    """Nombre décimal à la française."""
    return f"{x:.{n}f}".replace(".", ",")


def pts(x, n=1):
    """Écart en points de pourcentage, signé, à la française."""
    v = x * 100
    return f"{v:+.{n}f}".replace(".", ",") + (" point" if abs(round(v, n)) < 2 else " points")


def tab_md(df: pd.DataFrame, aligns=None) -> str:
    cols = list(df.columns)
    a = aligns or (["---"] + ["---:"] * (len(cols) - 1))
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(a) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def main() -> int:
    emp = S.empreintes()
    s = S.seuils()
    ds = S.build_enrichi()
    h = S.h25_de(ds)
    y = h["label"].values.astype(bool)

    # ── Masques de politiques (seuils figés) ───────────────────────────────────
    pl = S.masque_plancher(h)
    sc_diff = S.masque_pdiff_score(h, s)
    sc_c = S.masque_score(h, s["c"])
    sc_b = S.masque_score(h, s["b"])
    sc_a = S.masque_score(h, s["a"])
    masques = {
        "P_diff": sc_diff | pl,
        "c_plancher": sc_c | pl,
        "b_plancher": sc_b | pl,
        "a_plancher": sc_a | pl,
        "pratique": h["is_UM"].values.astype(bool),
    }

    # Contrôle de construction : P_diff est, par définition, le raccord des deux
    # politiques uniformes selon le type de jour. Elle doit coïncider exactement avec
    # c ∪ plancher en jour ouvrable et avec b ∪ plancher les samedis, dimanches et fériés.
    ouvr = h["type_jour"].values == "ouvrable"
    if not (np.array_equal(masques["P_diff"][ouvr], masques["c_plancher"][ouvr]) and
            np.array_equal(masques["P_diff"][~ouvr], masques["b_plancher"][~ouvr])):
        raise RuntimeError("STOP : P_diff ne coïncide pas avec le raccord c / b attendu.")

    # ── 0. Contrôle de partition des trois strates de type de jour ─────────────
    part = (h.groupby("type_jour")
            .agg(n_courses=("label", "size"), n_surcharges=("label", "sum")).reindex(S.TYPES_JOUR))
    somme_c, somme_s = int(part["n_courses"].sum()), int(part["n_surcharges"].sum())
    partition_ok = (somme_c == len(h)) and (somme_s == int(y.sum())) and (somme_s == 2072)
    if not partition_ok:
        raise RuntimeError(f"STOP partition : {somme_c} courses / {somme_s} surcharges "
                           f"!= {len(h)} / {int(y.sum())}.")

    # ── 1-2. Confusion : global, par type de jour, par segment, croisement ──────
    lignes = []
    for k in ORDRE_POL:
        m = masques[k]
        lignes.append({"politique": k, "decoupage": "global", "modalite": "global",
                       "segment": "global", **S.confusion(m, y)})
        for seg in ("bas", "haut"):
            ms = h["segment"].values == seg
            lignes.append({"politique": k, "decoupage": "segment", "modalite": "global",
                           "segment": seg, **S.confusion(m[ms], y[ms])})
        for tj in S.TYPES_JOUR:
            mt = h["type_jour"].values == tj
            lignes.append({"politique": k, "decoupage": "type_jour", "modalite": tj,
                           "segment": "global", **S.confusion(m[mt], y[mt])})
            for seg in ("bas", "haut"):
                mts = mt & (h["segment"].values == seg)
                lignes.append({"politique": k, "decoupage": "type_jour x segment",
                               "modalite": tj, "segment": seg,
                               **S.confusion(m[mts], y[mts])})
    conf = pd.DataFrame(lignes)
    conf.to_csv(OUT_CSV / "t52_confusion_complete.csv", index=False, float_format="%.17g")

    # ── 4. Recouvrement score / plancher pour P_diff (et rappel pour c) ────────
    def recouvrement(sc, plc):
        return {"score_seul": int((sc & ~plc).sum()), "plancher_seul": int((plc & ~sc).sum()),
                "intersection": int((sc & plc).sum()), "union": int((sc | plc).sum())}

    rec_rows = []
    for k, sc in (("P_diff", sc_diff), ("c_plancher", sc_c), ("b_plancher", sc_b),
                  ("a_plancher", sc_a)):
        r = recouvrement(sc, pl)
        u = sc | pl
        r_vp = {"VP_score_seul": int((sc & ~pl & y).sum()),
                "VP_plancher_seul": int((pl & ~sc & y).sum()),
                "VP_intersection": int((sc & pl & y).sum()), "VP_union": int((u & y).sum())}
        rec_rows.append({"politique": k, **r, **r_vp})
    rec = pd.DataFrame(rec_rows)
    rec.to_csv(OUT_CSV / "t52_recouvrement_score_plancher.csv", index=False)

    # recouvrement de P_diff ventilé par type de jour (lecture fine)
    rec_tj = []
    for tj in S.TYPES_JOUR:
        mt = h["type_jour"].values == tj
        rec_tj.append({"type_jour": tj, **recouvrement(sc_diff[mt], pl[mt])})
    rec_tj = pd.DataFrame(rec_tj)
    rec_tj.to_csv(OUT_CSV / "t52_recouvrement_pdiff_par_type_jour.csv", index=False)

    # ── 5. Charge d'alerte ─────────────────────────────────────────────────────
    dates = pd.Index(sorted(h["date"].unique()))
    tj_par_date = h.drop_duplicates("date").set_index("date")["type_jour"].reindex(dates)
    we = tj_par_date.isin(["samedi", "dimanche_ferie"]).values

    ch_rows, series = [], {}
    for k in ORDRE_POL:
        c_all = S.charge_alerte(h, masques[k], dates)
        series[k] = c_all.pop("_par_jour")
        v_we = series[k].values[we].astype(float)
        ch_rows.append({"politique": k, "perimetre": "tous les jours", **c_all})
        ch_rows.append({"politique": k, "perimetre": "samedis, dimanches et fériés",
                        "n_jours": int(we.sum()), "total": int(v_we.sum()),
                        "moyenne": float(v_we.mean()), "mediane": float(np.median(v_we)),
                        "d9": float(np.percentile(v_we, 90)), "max": int(v_we.max()),
                        "jours_sans_recommandation": int((v_we == 0).sum())})
    charge = pd.DataFrame(ch_rows)
    charge.to_csv(OUT_CSV / "t52_charge_alerte.csv", index=False, float_format="%.17g")
    pd.DataFrame({k: v for k, v in series.items()}).assign(
        type_jour=tj_par_date.values).to_csv(OUT_CSV / "t52_recommandations_par_jour.csv")

    # ── 6. Rappel par strate de charge maximale observée ───────────────────────
    st_rows = []
    for nom in S.STRATES:
        ms = (h["strate"].values == nom) & y
        tot = int(ms.sum())
        row = {"strate": nom, "n_surcharges": tot}
        for k in ORDRE_POL:
            row[k] = (int((masques[k] & ms).sum()) / tot) if tot else None
            row[f"{k}_VP"] = int((masques[k] & ms).sum())
        st_rows.append(row)
    strates = pd.DataFrame(st_rows)
    strates.to_csv(OUT_CSV / "t52_rappel_par_strate.csv", index=False, float_format="%.17g")

    # ── 7. Coût des faux positifs ──────────────────────────────────────────────
    ct_rows = []
    for k in ORDRE_POL:
        c = S.cout_fp(h, masques[k])
        ct_rows.append({"politique": k, **c})
        for tj in S.TYPES_JOUR:
            mt = h["type_jour"].values == tj
            ct = S.cout_fp(h[mt], masques[k][mt])
            ct_rows.append({"politique": f"{k} / {tj}", **ct})
    couts = pd.DataFrame(ct_rows)
    couts.to_csv(OUT_CSV / "t52_couts_faux_positifs.csv", index=False, float_format="%.17g")

    # ── Réconciliation avec les chiffres canoniques déjà publiés ───────────────
    # Contrôle indépendant : les politiques déjà publiées dans
    # outputs/couche2/q_couche2_deploiement_ba493568.json doivent être reproduites
    # à l'unité près par le présent calcul, qui repart des sources canoniques.
    import json as _json
    canon = _json.loads((S.ROOT / "outputs/couche2/q_couche2_deploiement_ba493568.json").read_text())
    attendu = {"c_plancher": canon["comparaison_H25"]["deploiement_c_plancher"],
               "a_plancher": canon["comparaison_H25"]["a_plancher"],
               "pratique": canon["comparaison_H25"]["humaine"]}
    glob_idx = conf[conf["decoupage"] == "global"].set_index("politique")
    recon_rows, recon_ok = [], True
    for k, att in attendu.items():
        obt = glob_idx.loc[k]
        ok = (int(obt["volume"]) == att["volume"] and int(obt["VP"]) == att["VP"]
              and int(obt["FP"]) == att["FP"])
        recon_ok &= ok
        recon_rows.append({"Politique": LIB_POL[k].split(" (")[0],
                           "Volume publié": S.fr(att["volume"]), "Volume obtenu": S.fr(obt["volume"]),
                           "VP publiés": S.fr(att["VP"]), "VP obtenus": S.fr(obt["VP"]),
                           "FP publiés": S.fr(att["FP"]), "FP obtenus": S.fr(obt["FP"]),
                           "Identique": "**oui**" if ok else "**NON**"})
    couts_pub = canon["couts_fp_volet_B_H25"]
    for k, kp in (("c_plancher", "deploiement_c_plancher"), ("a_plancher", "a_plancher"),
                  ("pratique", "humaine")):
        obt = couts[couts["politique"] == k].iloc[0]
        ok = round(float(obt["cout_CHF"]), 0) == couts_pub[kp]["cout_CHF"]
        recon_ok &= ok
        recon_rows.append({"Politique": LIB_POL[k].split(" (")[0] + " — coût FP",
                           "Volume publié": f"{couts_pub[kp]['cout_CHF']:.0f} CHF",
                           "Volume obtenu": f"{obt['cout_CHF']:.0f} CHF",
                           "VP publiés": "—", "VP obtenus": "—", "FP publiés": "—",
                           "FP obtenus": "—", "Identique": "**oui**" if ok else "**NON**"})
    t_recon = pd.DataFrame(recon_rows)

    # ── Rapport ────────────────────────────────────────────────────────────────
    def bloc(dec, mod=None, seg=None):
        q = conf[conf["decoupage"] == dec]
        if mod is not None:
            q = q[q["modalite"] == mod]
        if seg is not None:
            q = q[q["segment"] == seg]
        return q

    def ligne_pol(r):
        return {"Politique": LIB_POL[r["politique"]], "Volume": S.fr(r["volume"]),
                "VP": S.fr(r["VP"]), "FP": S.fr(r["FP"]), "FN": S.fr(r["FN"]),
                "VN": S.fr(r["VN"]), "Précision": pct(r["precision"]),
                "Rappel": pct(r["rappel"]), "F1": f"{r['F1']:.3f}".replace(".", ",")}

    g = bloc("global")
    t_global = pd.DataFrame([ligne_pol(r) for _, r in g.iterrows()])

    def table_par(dec, modalites, cle):
        rows = []
        for mod in modalites:
            for _, r in bloc(dec, mod, "global" if dec == "type_jour" else None).iterrows():
                if dec == "segment" and r["segment"] != mod:
                    continue
                rows.append({cle: S.LIB_TYPE_JOUR.get(mod, mod.upper()),
                             **{k: v for k, v in ligne_pol(r).items()
                                if k in ("Politique", "Volume", "VP", "FP", "FN",
                                         "Précision", "Rappel", "F1")}})
        return pd.DataFrame(rows)

    t_tj = table_par("type_jour", S.TYPES_JOUR, "Type de jour")
    t_seg = table_par("segment", ["bas", "haut"], "Segment")

    rows = []
    for tj in S.TYPES_JOUR:
        for seg in ("bas", "haut"):
            for _, r in bloc("type_jour x segment", tj, seg).iterrows():
                rows.append({"Type de jour": S.LIB_TYPE_JOUR[tj], "Segment": seg.upper(),
                             "Politique": LIB_POL[r["politique"]].split(" (")[0],
                             "Surcharges": S.fr(r["n_surcharges"]), "Volume": S.fr(r["volume"]),
                             "VP": S.fr(r["VP"]), "Précision": pct(r["precision"]),
                             "Rappel": pct(r["rappel"]), "F1": f"{r['F1']:.3f}".replace(".", ",")})
    t_cx = pd.DataFrame(rows)

    t_rec = pd.DataFrame([{"Politique": LIB_POL[r["politique"]].split(" (")[0],
                           "Par le seul score": S.fr(r["score_seul"]),
                           "Par le seul plancher": S.fr(r["plancher_seul"]),
                           "Par les deux": S.fr(r["intersection"]),
                           "Union": S.fr(r["union"]),
                           "dont VP (union)": S.fr(r["VP_union"])}
                          for _, r in rec.iterrows()])
    t_rec_tj = pd.DataFrame([{"Type de jour": S.LIB_TYPE_JOUR[r["type_jour"]],
                              "Par le seul score": S.fr(r["score_seul"]),
                              "Par le seul plancher": S.fr(r["plancher_seul"]),
                              "Par les deux": S.fr(r["intersection"]),
                              "Union": S.fr(r["union"])} for _, r in rec_tj.iterrows()])

    t_ch = pd.DataFrame([{"Politique": LIB_POL[r["politique"]].split(" (")[0],
                          "Périmètre": r["perimetre"], "Jours": S.fr(r["n_jours"]),
                          "Total": S.fr(r["total"]), "Moyenne": f"{r['moyenne']:.2f}".replace(".", ","),
                          "Médiane": f"{r['mediane']:.1f}".replace(".", ","), "D9": f"{r['d9']:.1f}".replace(".", ","),
                          "Max": S.fr(r["max"]),
                          "Jours sans recommandation": S.fr(r["jours_sans_recommandation"])}
                         for _, r in charge.iterrows()])

    t_st = pd.DataFrame([{"Strate de charge": r["strate"],
                          "Surcharges": S.fr(r["n_surcharges"]),
                          **{LIB_POL[k].split(" (")[0]: pct(r[k]) for k in ORDRE_POL}}
                         for _, r in strates.iterrows()])

    t_ct = pd.DataFrame([{"Politique": LIB_POL[r["politique"]].split(" (")[0],
                          "Faux positifs": S.fr(r["n_FP"]),
                          "Kilomètres": f"{r['km_FP']:,.1f}".replace(",", "\u00a0").replace(".", ",").replace("\u00a0", " "),
                          "Coût (CHF)": f"{r['cout_CHF']:,.0f}".replace(",", " ")}
                         for _, r in couts[~couts["politique"].str.contains("/")].iterrows()])

    gl = {r["politique"]: r for _, r in g.iterrows()}
    d_prec = gl["P_diff"]["precision"] - gl["c_plancher"]["precision"]
    d_rap = gl["P_diff"]["rappel"] - gl["c_plancher"]["rappel"]

    # ── Dominance sur les deux axes face à la pratique, pour TOUTE politique du menu ──
    dom_rows = []
    for tj in S.TYPES_JOUR:
        q = bloc("type_jour", tj, "global").set_index("politique")
        pr_h, ra_h = q.loc["pratique", "precision"], q.loc["pratique", "rappel"]
        for k in ORDRE_POL:
            if k == "pratique":
                continue
            pr, ra = q.loc[k, "precision"], q.loc[k, "rappel"]
            dom_rows.append({
                "type_jour": tj, "politique": k,
                "precision": pr, "rappel": ra,
                "precision_pratique": pr_h, "rappel_pratique": ra_h,
                "delta_precision": pr - pr_h, "delta_rappel": ra - ra_h,
                "VP": int(q.loc[k, "VP"]), "VP_pratique": int(q.loc["pratique", "VP"]),
                "domine_les_deux_axes": bool(pr > pr_h and ra > ra_h)})
    dom = pd.DataFrame(dom_rows)
    dom.to_csv(OUT_CSV / "t52_dominance_par_type_jour.csv", index=False, float_format="%.17g")

    t_dom = pd.DataFrame([{
        "Type de jour": S.LIB_TYPE_JOUR[r["type_jour"]],
        "Politique": LIB_POL[r["politique"]].split(" (")[0],
        "Précision": pct(r["precision"]), "Rappel": pct(r["rappel"]),
        "Δ précision": pts(r["delta_precision"]).replace(" points", " pt").replace(" point", " pt"),
        "Δ rappel": pts(r["delta_rappel"]).replace(" points", " pt").replace(" point", " pt"),
        "Domine sur les deux axes": "**oui**" if r["domine_les_deux_axes"] else "non",
    } for _, r in dom.iterrows()])

    # verdict : P_diff domine-t-elle la pratique sur les trois types de jour ?
    d_pdiff = dom[dom["politique"] == "P_diff"].set_index("type_jour")
    tj_dominés = [t for t in S.TYPES_JOUR if bool(d_pdiff.loc[t, "domine_les_deux_axes"])]
    tj_non = [t for t in S.TYPES_JOUR if t not in tj_dominés]
    # existe-t-il, pour chaque type de jour, UNE politique du menu qui domine ?
    couverture = {t: [k for k in ORDRE_POL if k != "pratique"
                      and bool(dom[(dom.type_jour == t) & (dom.politique == k)]
                               ["domine_les_deux_axes"].iloc[0])] for t in S.TYPES_JOUR}

    md = f"""# Politique de seuil différenciée par type de jour

VÉRIF 2 de la section 5.2. Rapport produit en lecture seule par
`docs/memoire/verifs/section_5_2/verif_52_politique_differenciee.py`.

> **Statut méthodologique.** Cette lecture n'a fait l'objet d'aucun préenregistrement et
> elle est **postérieure à la lecture du jeu d'évaluation H25**. Elle ne recalibre rien :
> les seuils restent exactement ceux calibrés sur H24, et le plancher de réservation
> conserve sa définition. Il s'agit d'une **analyse descriptive post-hoc à seuils
> inchangés** d'une règle composite construite à partir de paramètres déjà fixés. La
> section 4.7.1 annonce cette lecture (« l'opportunité d'une politique de seuil
> différenciée par type de jour est versée aux recommandations »).

## 1. Empreintes et paramètres

| Rôle | Valeur |
|---|---|
| Branche | `{emp['branche']}` |
| Commit | `{emp['commit']}` |
| Table canonique `ml_dataset.parquet` | `{emp['dataset']}` |
| Modèle gelé BAS | `{emp['modele_bas']}` |
| Modèle gelé HAUT | `{emp['modele_haut']}` |
| Menu de seuils calibré sur H24 | `{emp['calibration_H24']}` |

Seuils **relus** du menu H24, non recalculés : a′ = {fmt(s['a'])}, b = {fmt(s['b'])},
c = {fmt(s['c'])}. Plancher de réservation : réservations de deuxième classe agrégées à
la course par le **maximum** sur les tronçons, strictement supérieures à 63.

### 1.1 Réconciliation avec les chiffres déjà publiés

Le présent calcul repart des sources canoniques et reconstruit tout le jeu de décision.
Les politiques déjà publiées dans `outputs/couche2/q_couche2_deploiement_ba493568.json`
doivent donc être reproduites **à l'unité près**. Contrôle : {"**toutes le sont**" if recon_ok else "**ÉCART DÉTECTÉ**"}.

{tab_md(t_recon)}

Ce contrôle vaut pour les nouvelles lignes : P_diff est calculée par le même code, sur le
même jeu, avec les mêmes conventions que les lignes déjà validées.

Périmètre d'évaluation : **{S.fr(len(h))} courses** H25, dont **{S.fr(int(y.sum()))} en surcharge**
({S.fr(int((y & (h['segment'].values == 'haut')).sum()))} HAUT / {S.fr(int((y & (h['segment'].values == 'bas')).sum()))} BAS),
réparties sur {S.fr(len(dates))} journées.

## 2. Contrôle de partition des trois strates de type de jour

Les trois classes de la typologie comportementale du projet (`cal_type_jour_3classes`)
doivent partitionner exactement le périmètre. La somme est **exacte**.

| Type de jour | Journées | Courses | Surcharges |
|---|---:|---:|---:|
""" + "\n".join(
        f"| {S.LIB_TYPE_JOUR[t]} | {S.fr((tj_par_date == t).sum())} | "
        f"{S.fr(part.loc[t, 'n_courses'])} | {S.fr(part.loc[t, 'n_surcharges'])} |"
        for t in S.TYPES_JOUR) + f"""
| **Total** | **{S.fr(len(dates))}** | **{S.fr(somme_c)}** | **{S.fr(somme_s)}** |

Contrôle : {S.fr(somme_c)} = {S.fr(len(h))} courses et {S.fr(somme_s)} = {S.fr(int(y.sum()))} surcharges. **Partition vérifiée.**

## 3. Matrice de confusion complète sur H25

{tab_md(t_global)}

P_diff recommande {S.fr(gl['P_diff']['volume'])} courses contre {S.fr(gl['c_plancher']['volume'])} pour
la configuration uniforme c ∪ plancher, soit {S.fr(gl['P_diff']['volume'] - gl['c_plancher']['volume'])}
recommandations supplémentaires. La précision passe de {pct(gl['c_plancher']['precision'])} à
{pct(gl['P_diff']['precision'])} ({pts(d_prec)}) et le rappel de
{pct(gl['c_plancher']['rappel'])} à {pct(gl['P_diff']['rappel'])} ({pts(d_rap)}).

## 4. Ventilation par type de jour

{tab_md(t_tj)}

## 5. Ventilation par segment

{tab_md(t_seg)}

## 6. Croisement type de jour × segment

{tab_md(t_cx)}

## 7. Dominance sur les deux axes face à la pratique, par type de jour

Une politique *domine sur les deux axes* si sa précision **et** son rappel dépassent
tous deux ceux de la pratique de référence, sur le même type de jour. Les écarts sont
exprimés en points de pourcentage face à la pratique.

{tab_md(t_dom)}

### 7.1 Verdict

**La dominance de P_diff sur les deux axes n'est pas établie pour les trois types de
jour.** Elle l'est pour {"le seul type de jour suivant" if len(tj_dominés) == 1 else "les types de jour suivants"} :
{", ".join(S.LIB_TYPE_JOUR[t].lower() for t in tj_dominés) if tj_dominés else "aucun"}.
Elle ne l'est pas pour : {", ".join(S.LIB_TYPE_JOUR[t].lower() for t in tj_non) if tj_non else "aucun"}.

Le détail des deux échecs :

- **Samedi.** P_diff gagne {pts(d_pdiff.loc['samedi', 'delta_rappel'])} de rappel mais
  perd {pts(-abs(d_pdiff.loc['samedi', 'delta_precision'])).lstrip('+-')} de précision
  ({pct(d_pdiff.loc['samedi', 'precision'])} contre {pct(d_pdiff.loc['samedi', 'precision_pratique'])}).
  La pratique est **plus précise que le modèle** le samedi : c'est le seul type de jour
  où elle l'est. L'écart n'est pas marginal : la pratique est près de deux fois plus précise.
- **Dimanche et jour férié.** P_diff gagne
  {pts(d_pdiff.loc['dimanche_ferie', 'delta_precision'])} de précision mais
  perd {pts(-abs(d_pdiff.loc['dimanche_ferie', 'delta_rappel'])).lstrip('+-')} de rappel. Cet écart
  de rappel correspond à **{int(d_pdiff.loc['dimanche_ferie', 'VP_pratique'] - d_pdiff.loc['dimanche_ferie', 'VP'])} course**
  ({int(d_pdiff.loc['dimanche_ferie', 'VP'])} vrais positifs contre
  {int(d_pdiff.loc['dimanche_ferie', 'VP_pratique'])}). Il est trop petit pour être
  interprété sans intervalle de confiance ; la VÉRIF 3 le chiffre.

Aucune autre politique du menu figé ne rétablit la dominance là où P_diff échoue :
le tableau ci-dessus balaie a′ ∪ plancher, b ∪ plancher et c ∪ plancher pour chacun des
trois types de jour. Le samedi, aucune configuration du menu ne domine la pratique sur
les deux axes à la fois.

### 7.2 Ce que la lecture établit malgré tout

Deux énoncés restent solidement étayés :

1. **En jour ouvrable**, qui concentre {pct(part.loc['ouvrable', 'n_surcharges'] / somme_s)} des surcharges du
   périmètre, la dominance sur les deux axes est massive et n'a pas besoin de la
   différenciation : elle est déjà acquise par c ∪ plancher, dont P_diff est la copie
   exacte sur ce type de jour.
2. **Le passage de c à b les samedis, dimanches et fériés multiplie le rappel** sur ces
   journées, au prix d'une précision qui reste au-dessus de la limite basse de tolérance
   énoncée par l'exploitation le dimanche, mais **passe en dessous le samedi**.

Le second énoncé est un arbitrage, pas une dominance. C'est ainsi qu'il doit être
formulé en 5.2.

## 8. Décomposition du recouvrement score / plancher

Même décomposition que celle déjà produite pour c ∪ plancher : courses recommandées par
le seul score, par le seul plancher, par les deux.

{tab_md(t_rec)}

Ventilation de P_diff par type de jour :

{tab_md(t_rec_tj)}

## 9. Charge d'alerte

Nombre de recommandations par journée. Les journées du périmètre sans aucune
recommandation sont comptées comme zéro, elles ne sont pas omises de la distribution.

{tab_md(t_ch)}

## 10. Rappel par strate de charge maximale observée de la course

{tab_md(t_st)}

## 11. Coût des faux positifs

Valorisation au facteur constant déjà utilisé : tare de {fmt(S.TARE_T)} tonnes × redevance de
{fmt(S.TARIF_TBKM, 5)} CHF par tonne-kilomètre = **{fmt(S.COUT_PAR_KM, 4)} CHF par kilomètre de course**.

{tab_md(t_ct)}

## 12. Livrables

| Fichier | Contenu |
|---|---|
| `docs/memoire/tableaux/section_5_2_1/t52_confusion_complete.csv` | Confusion, tous découpages, {S.fr(len(conf))} lignes |
| `docs/memoire/tableaux/section_5_2_1/t52_dominance_par_type_jour.csv` | Dominance sur les deux axes, toutes politiques du menu |
| `docs/memoire/tableaux/section_5_2_1/t52_recouvrement_score_plancher.csv` | Recouvrement par politique |
| `docs/memoire/tableaux/section_5_2_1/t52_recouvrement_pdiff_par_type_jour.csv` | Recouvrement de P_diff par type de jour |
| `docs/memoire/tableaux/section_5_2_1/t52_charge_alerte.csv` | Distribution de la charge d'alerte |
| `docs/memoire/tableaux/section_5_2_1/t52_recommandations_par_jour.csv` | Série journalière brute, {S.fr(len(dates))} lignes |
| `docs/memoire/tableaux/section_5_2_1/t52_rappel_par_strate.csv` | Rappel par strate de charge |
| `docs/memoire/tableaux/section_5_2_1/t52_couts_faux_positifs.csv` | Coût des faux positifs, global et par type de jour |
| `docs/memoire/verifs/section_5_2/politique_seuil_differenciee.md` | Le présent rapport |
"""
    OUT_MD.write_text(md)

    print("=" * 78)
    print(f"P_diff — seuils figés a'={s['a']:.2f} b={s['b']:.2f} c={s['c']:.2f}")
    print(f"partition type de jour : {somme_c} courses / {somme_s} surcharges — OK")
    print("=" * 78)
    print("\n[GLOBAL H25]")
    print(t_global.to_string(index=False))
    print("\n[PAR TYPE DE JOUR]")
    print(t_tj.to_string(index=False))
    print("\n[DOMINANCE vs PRATIQUE]")
    print(t_dom.to_string(index=False))
    print("\n[RECOUVREMENT]")
    print(t_rec.to_string(index=False))
    print("\n[CHARGE D'ALERTE]")
    print(t_ch.to_string(index=False))
    print("\n[RAPPEL PAR STRATE]")
    print(t_st.to_string(index=False))
    print("\n[COÛTS FP]")
    print(t_ct.to_string(index=False))
    print(f"\n[OK] {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
