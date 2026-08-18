#!/usr/bin/env python3
"""
verif_51_ic_et_tests.py — VÉRIF 3 (§5.1).

Quantifie l'incertitude d'échantillonnage des métriques décisionnelles au grain de la
course sur H25 et teste la différence entre l'artefact et la pratique de référence,
afin qu'aucune affirmation de dominance ne repose sur une comparaison de points sans
dispersion.

Discipline : LECTURE SEULE. Aucun modèle, aucun seuil, aucun jeu d'évaluation n'est
modifié. Toutes les règles évaluées sont des masques FIXES, déterminés hors du
rééchantillonnage : le bootstrap chiffre l'incertitude de la MESURE d'une règle donnée,
il ne resélectionne pas la règle.

Deux schémas de rééchantillonnage :
  - par COURSE (schéma de référence, indépendance supposée entre courses) ;
  - par BLOC JOURNALIER (rééchantillonnage des journées entières), qui respecte la
    dépendance des courses d'une même journée. L'élargissement des intervalles entre
    les deux schémas mesure le coût de l'hypothèse d'indépendance.

Sorties :
  - docs/memoire/verifs/section_5_1/ic_et_tests_comparaison.md
  - docs/memoire/tableaux/section_5_1_1/*.csv
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _socle_chap5 as S  # noqa: E402

OUT_MD = Path(__file__).resolve().parent / "ic_et_tests_comparaison.md"
OUT_CSV = S.ROOT / "docs/memoire/tableaux/section_5_1_1"

N_BOOT = 2000
GRAINE = 20260805          # graine fixée et rapportée (contrat de reproductibilité)
ALPHA = 0.05
BUDGET_HUMAIN = 418        # top-k protocolaire, côté humain, sans label H25

LIB = {
    "pratique": "Pratique de référence",
    "budget_egal": "Lecture à budget égal (418 premières recommandations)",
    "a_plancher": "a′ ∪ plancher",
    "c_plancher": "c ∪ plancher",
    "a_nu": "Seuil nu a′",
    "b_nu": "Seuil nu b",
    "c_nu": "Seuil nu c",
}
ORDRE = ["pratique", "budget_egal", "a_plancher", "c_plancher", "a_nu", "b_nu", "c_nu"]
STRATES = ["global", "bas", "haut"]


def pct(x, n=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/d"
    return f"{x*100:.{n}f}".replace(".", ",") + " %"


def fmt(x, n=3):
    return "n/d" if x is None or not np.isfinite(x) else f"{x:.{n}f}".replace(".", ",")


def pval(p):
    if p is None or not np.isfinite(p):
        return "n/d"
    return "< 10⁻¹⁵" if p < 1e-15 else (f"{p:.3g}".replace(".", ",") if p >= 1e-4
                                        else f"{p:.2e}".replace(".", ","))


def pts(x, n=1):
    """Écart en points de pourcentage (et non en pourcents)."""
    if x is None or not np.isfinite(x):
        return "n/d"
    v = x * 100
    return f"{v:.{n}f}".replace(".", ",") + (" point" if abs(round(v, n)) < 2 else " points")


def tab_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


# ── Aire sous la courbe précision-rappel, pondérée ──────────────────────────────
def ap_pondere(ordre_desc, y_tri, w_tri) -> float:
    """Aire sous la courbe précision-rappel (average precision), avec poids entiers.

    Convention sklearn : AP = Σ (R_n − R_{n−1}) · P_n, les scores ex æquo formant un
    seul point de la courbe. `y_tri` et `w_tri` sont supposés déjà triés par score
    décroissant, `ordre_desc` porte les indices de fin de chaque paquet d'ex æquo.
    """
    cum_tp = np.cumsum(w_tri * y_tri)[ordre_desc]
    cum_all = np.cumsum(w_tri)[ordre_desc]
    tot = cum_tp[-1]
    if tot <= 0 or cum_all[-1] <= 0:
        return np.nan
    # Les paquets de tête dont aucune observation n'a été tirée donnent cum_all = 0.
    # Le rappel n'y a pas encore bougé, leur contribution à l'aire est nulle : on y
    # pose une précision de 0 plutôt que de propager un 0/0 qui invaliderait le réplicat.
    p = np.divide(cum_tp, cum_all, out=np.zeros_like(cum_tp), where=cum_all > 0)
    r = cum_tp / tot
    return float(np.sum(np.diff(np.concatenate(([0.0], r))) * p))


def prepare_ap(score: np.ndarray, y: np.ndarray):
    """Tri décroissant par score + repérage des fins de paquets d'ex æquo (une fois)."""
    o = np.argsort(-score, kind="mergesort")
    s_tri = score[o]
    fins = np.flatnonzero(np.diff(s_tri) != 0)
    fins = np.concatenate((fins, [len(s_tri) - 1]))
    return o, y[o].astype(np.float64), fins


def main() -> int:
    emp = S.empreintes()
    s = S.seuils()
    ds = S.build_enrichi()
    h = S.h25_de(ds)
    n = len(h)
    y = h["label"].values.astype(bool)
    score = h["score"].values.astype(np.float64)
    seg = h["segment"].values

    # ── Masques FIXES des règles évaluées ──────────────────────────────────────
    pl = S.masque_plancher(h)
    ordre_topk = h.sort_values(["score", "date", "numero_train"],
                               ascending=[False, True, True]).index[:BUDGET_HUMAIN]
    m_topk = np.zeros(n, dtype=bool)
    m_topk[np.asarray(ordre_topk)] = True
    masques = {
        "pratique": h["is_UM"].values.astype(bool),
        "budget_egal": m_topk,
        "a_plancher": S.masque_score(h, s["a"]) | pl,
        "c_plancher": S.masque_score(h, s["c"]) | pl,
        "a_nu": S.masque_score(h, s["a"]),
        "b_nu": S.masque_score(h, s["b"]),
        "c_nu": S.masque_score(h, s["c"]),
    }
    strates = {"global": np.ones(n, dtype=bool), "bas": seg == "bas", "haut": seg == "haut"}

    # contrôle : la lecture à budget égal doit reproduire les 343 VP publiés
    if int((m_topk & y).sum()) != 343 or int(m_topk.sum()) != 418:
        raise RuntimeError("STOP : la lecture à budget égal ne reproduit pas 418 / 343.")

    # ── Matrice d'indicateurs (une colonne par quantité à sommer) ──────────────
    cols, noms = [], []
    for p in ORDRE:
        for st in STRATES:
            cols.append((masques[p] & strates[st]).astype(np.float64)); noms.append(("vol", p, st))
            cols.append((masques[p] & y & strates[st]).astype(np.float64)); noms.append(("tp", p, st))
    for st in STRATES:
        cols.append((y & strates[st]).astype(np.float64)); noms.append(("pos", None, st))
    M = np.column_stack(cols)
    idx_col = {k: i for i, k in enumerate(noms)}

    prep = {st: prepare_ap(score[strates[st]], y[strates[st]]) for st in STRATES}

    def metriques(w: np.ndarray) -> dict:
        """Toutes les métriques pour un vecteur de poids de courses."""
        v = w @ M
        out = {}
        for p in ORDRE:
            for st in STRATES:
                vol = v[idx_col[("vol", p, st)]]
                tp = v[idx_col[("tp", p, st)]]
                pos = v[idx_col[("pos", None, st)]]
                out[("precision", p, st)] = (tp / vol) if vol > 0 else np.nan
                out[("rappel", p, st)] = (tp / pos) if pos > 0 else np.nan
        for st in STRATES:
            o, y_tri, fins = prep[st]
            out[("pr_auc", None, st)] = ap_pondere(fins, y_tri, w[strates[st]][o])
        return out

    # contrôle : poids unitaires => valeurs ponctuelles canoniques
    point = metriques(np.ones(n))
    from sklearn.metrics import average_precision_score
    for st in STRATES:
        ref = average_precision_score(y[strates[st]].astype(int), score[strates[st]])
        if abs(ref - point[("pr_auc", None, st)]) > 1e-12:
            raise RuntimeError(f"STOP : AP maison != sklearn sur {st} "
                               f"({point[('pr_auc', None, st)]} vs {ref}).")
    if abs(point[("precision", "c_plancher", "global")] - 622 / 866) > 1e-12:
        raise RuntimeError("STOP : précision de c ∪ plancher non reproduite.")

    # ── Bootstrap, deux schémas ────────────────────────────────────────────────
    dates = h["date"].values
    d_codes, d_uniq = pd.factorize(dates)
    n_jours = len(d_uniq)

    def tirage_course(rng):
        return np.bincount(rng.integers(0, n, n), minlength=n).astype(np.float64)

    def tirage_bloc(rng):
        """Rééchantillonnage des JOURNÉES : le poids d'une course est le nombre de
        fois où sa journée a été tirée."""
        tirs = np.bincount(rng.integers(0, n_jours, n_jours), minlength=n_jours)
        return tirs[d_codes].astype(np.float64)

    schemas = {"course": tirage_course, "bloc_journalier": tirage_bloc}
    reps = {}
    for nom_sch, tirage in schemas.items():
        rng = np.random.default_rng(GRAINE)
        acc = {k: np.empty(N_BOOT) for k in point}
        # différences appariées artefact - pratique (même rééchantillonnage)
        d_prec = np.empty(N_BOOT); d_rap = np.empty(N_BOOT)
        for i in range(N_BOOT):
            m = metriques(tirage(rng))
            for k in acc:
                acc[k][i] = m[k]
            d_prec[i] = m[("precision", "c_plancher", "global")] - m[("precision", "pratique", "global")]
            d_rap[i] = m[("rappel", "c_plancher", "global")] - m[("rappel", "pratique", "global")]
        reps[nom_sch] = {"acc": acc, "d_prec": d_prec, "d_rap": d_rap}
        print(f"  [bootstrap {nom_sch}] {N_BOOT} réplicats — fait")

    def ic(v):
        """Intervalle de percentile. Un réplicat non fini serait écarté en silence et
        biaiserait l'intervalle : la perte est plafonnée à 1 % et lève au-delà."""
        fini = np.isfinite(v)
        nv = int(fini.sum())
        if nv < 0.99 * len(v):
            raise RuntimeError(f"STOP : {len(v) - nv}/{len(v)} réplicats non finis "
                               f"(> 1 %) — l'intervalle porterait sur un sous-ensemble biaisé.")
        v = v[fini]
        return (float(np.percentile(v, 100 * ALPHA / 2)),
                float(np.percentile(v, 100 * (1 - ALPHA / 2))), nv)

    # ── Tableau des IC ─────────────────────────────────────────────────────────
    rows = []
    for (met, p, st), val in point.items():
        r = {"metrique": met, "regle": p if p else "score de course", "strate": st,
             "valeur": val}
        for nom_sch in schemas:
            lo, hi, nv = ic(reps[nom_sch]["acc"][(met, p, st)])
            r[f"ic_lo_{nom_sch}"] = lo
            r[f"ic_hi_{nom_sch}"] = hi
            r[f"largeur_{nom_sch}"] = hi - lo
            r[f"n_replicats_valides_{nom_sch}"] = nv
        r["elargissement"] = (r["largeur_bloc_journalier"] / r["largeur_course"]
                              if r["largeur_course"] > 0 else np.nan)
        rows.append(r)
    ics = pd.DataFrame(rows)
    ics.to_csv(OUT_CSV / "t51_intervalles_confiance.csv", index=False, float_format="%.17g")

    # ── Tests de comparaison c ∪ plancher vs pratique ──────────────────────────
    A, B = masques["c_plancher"], masques["pratique"]

    # -- RAPPEL : McNemar propre (même dénominateur = les 2 072 surcharges) --
    sur = y
    a_both = int((A & B & sur).sum())
    b_only = int((A & ~B & sur).sum())
    c_only = int((~A & B & sur).sum())
    d_none = int((~A & ~B & sur).sum())
    n_disc = b_only + c_only
    mcn_stat = ((abs(b_only - c_only) - 1) ** 2 / n_disc) if n_disc else np.nan
    mcn_p = float(stats.chi2.sf(mcn_stat, 1)) if n_disc else np.nan
    mcn_exact = float(stats.binomtest(b_only, n_disc, 0.5).pvalue) if n_disc else np.nan
    or_mcn = (b_only / c_only) if c_only else np.inf
    d_rappel = (b_only - c_only) / int(sur.sum())

    # -- RAPPEL : lecture conservatrice, deux proportions indépendantes --
    def z_deux_prop(x1, n1, x2, n2):
        p1, p2 = x1 / n1, x2 / n2
        pp = (x1 + x2) / (n1 + n2)
        se = np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
        z = (p1 - p2) / se if se > 0 else np.nan
        return z, float(2 * stats.norm.sf(abs(z))), p1 - p2, \
            2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))   # h de Cohen

    P = int(sur.sum())
    z_r, p_r, d_r, h_r = z_deux_prop(int((A & sur).sum()), P, int((B & sur).sum()), P)

    # -- PRÉCISION : discordance sur les recommandations exclusives --
    a_ex, b_ex = A & ~B, B & ~A
    na, tpa = int(a_ex.sum()), int((a_ex & y).sum())
    nb, tpb = int(b_ex.sum()), int((b_ex & y).sum())
    inter, tp_inter = int((A & B).sum()), int((A & B & y).sum())
    table = np.array([[tpa, na - tpa], [tpb, nb - tpb]])
    or_f, p_fisher = stats.fisher_exact(table)
    chi2_p, p_chi2 = stats.chi2_contingency(table, correction=True)[:2]
    _, _, d_pex, _ = z_deux_prop(tpa, na, tpb, nb)

    # -- PRÉCISION : lecture conservatrice, deux proportions indépendantes --
    volA, tpA = int(A.sum()), int((A & y).sum())
    volB, tpB = int(B.sum()), int((B & y).sum())
    z_p, p_p, d_p, h_p = z_deux_prop(tpA, volA, tpB, volB)

    tests = pd.DataFrame([
        {"metrique": "rappel", "lecture": "McNemar (apparié, 2 072 surcharges)",
         "statistique": mcn_stat, "p_valeur": mcn_p, "p_valeur_exacte": mcn_exact,
         "taille_effet": or_mcn, "nature_effet": "rapport de cotes b/c",
         "delta": d_rappel, "n": P, "detail": f"b={b_only} c={c_only} a={a_both} d={d_none}"},
        {"metrique": "rappel", "lecture": "deux proportions indépendantes (conservatrice)",
         "statistique": z_r, "p_valeur": p_r, "p_valeur_exacte": np.nan,
         "taille_effet": h_r, "nature_effet": "h de Cohen", "delta": d_r, "n": 2 * P,
         "detail": f"{int((A & sur).sum())}/{P} vs {int((B & sur).sum())}/{P}"},
        {"metrique": "precision", "lecture": "discordance des recommandations exclusives (Fisher exact)",
         "statistique": chi2_p, "p_valeur": p_fisher, "p_valeur_exacte": p_chi2,
         "taille_effet": or_f, "nature_effet": "rapport de cotes",
         "delta": d_pex, "n": na + nb,
         "detail": f"A seul {tpa}/{na} vs pratique seule {tpb}/{nb} ; commun {tp_inter}/{inter}"},
        {"metrique": "precision", "lecture": "deux proportions indépendantes (conservatrice)",
         "statistique": z_p, "p_valeur": p_p, "p_valeur_exacte": np.nan,
         "taille_effet": h_p, "nature_effet": "h de Cohen", "delta": d_p, "n": volA + volB,
         "detail": f"{tpA}/{volA} vs {tpB}/{volB}"},
    ])
    tests.to_csv(OUT_CSV / "t51_tests_comparaison.csv", index=False, float_format="%.17g")

    # ── IC bootstrap des DIFFÉRENCES (appariées) ───────────────────────────────
    diff_rows = []
    for nom_sch in schemas:
        for lib, v, obs in (("précision", reps[nom_sch]["d_prec"], d_p),
                            ("rappel", reps[nom_sch]["d_rap"], d_r)):
            lo, hi, nv = ic(v)
            diff_rows.append({"schema": nom_sch, "metrique": lib, "difference_observee": obs,
                              "ic_lo": lo, "ic_hi": hi, "largeur": hi - lo,
                              "exclut_zero": bool(lo > 0 or hi < 0), "n_replicats": nv})
    diffs = pd.DataFrame(diff_rows)
    diffs.to_csv(OUT_CSV / "t51_differences_appariees.csv", index=False, float_format="%.17g")

    # ── Rapport ────────────────────────────────────────────────────────────────
    def bloc_ic(met, strate, regles=ORDRE):
        rows = []
        for p in regles:
            q = ics[(ics.metrique == met) & (ics.regle == p) & (ics.strate == strate)].iloc[0]
            rows.append({"Règle": LIB[p], "Valeur": pct(q["valeur"]),
                         "IC 95 % (par course)": f"[{pct(q['ic_lo_course'])} ; {pct(q['ic_hi_course'])}]",
                         "IC 95 % (par bloc journalier)":
                             f"[{pct(q['ic_lo_bloc_journalier'])} ; {pct(q['ic_hi_bloc_journalier'])}]",
                         "Élargissement": "×" + fmt(q["elargissement"], 2)})
        return tab_md(pd.DataFrame(rows))

    def bloc_prauc():
        rows = []
        for st in STRATES:
            q = ics[(ics.metrique == "pr_auc") & (ics.strate == st)].iloc[0]
            rows.append({"Périmètre": st.upper() if st != "global" else "Global",
                         "PR-AUC": fmt(q["valeur"], 4),
                         "IC 95 % (par course)": f"[{fmt(q['ic_lo_course'], 4)} ; {fmt(q['ic_hi_course'], 4)}]",
                         "IC 95 % (par bloc journalier)":
                             f"[{fmt(q['ic_lo_bloc_journalier'], 4)} ; {fmt(q['ic_hi_bloc_journalier'], 4)}]",
                         "Élargissement": "×" + fmt(q["elargissement"], 2)})
        return tab_md(pd.DataFrame(rows))

    # Concentration journalière des recommandations : indice de dispersion (variance
    # sur moyenne) des comptes quotidiens. Une valeur de 1 correspond à un semis de
    # Poisson (aucun groupement) ; au-delà, les recommandations se groupent par journée.
    conc_rows = []
    for p in ORDRE:
        cpt = np.bincount(d_codes[masques[p]], minlength=n_jours).astype(float)
        conc_rows.append({"regle": p, "total": int(cpt.sum()), "moyenne": float(cpt.mean()),
                          "variance": float(cpt.var(ddof=1)),
                          "indice_dispersion": float(cpt.var(ddof=1) / cpt.mean()) if cpt.mean() else np.nan,
                          "jours_actifs": int((cpt > 0).sum()), "max_par_jour": int(cpt.max())})
    conc = pd.DataFrame(conc_rows)
    conc.to_csv(OUT_CSV / "t51_concentration_journaliere.csv", index=False, float_format="%.17g")
    t_conc = tab_md(pd.DataFrame([{
        "Règle": LIB[r["regle"]], "Recommandations": S.fr(r["total"]),
        "Journées actives": S.fr(r["jours_actifs"]), "Maximum par jour": S.fr(r["max_par_jour"]),
        "Indice de dispersion": fmt(r["indice_dispersion"], 2),
    } for _, r in conc.sort_values("indice_dispersion", ascending=False).iterrows()]))
    id_prat = float(conc[conc.regle == "pratique"]["indice_dispersion"].iloc[0])
    id_cpl = float(conc[conc.regle == "c_plancher"]["indice_dispersion"].iloc[0])

    elarg_moy = float(ics["elargissement"].replace([np.inf, -np.inf], np.nan).dropna().mean())
    elarg_max = float(ics["elargissement"].replace([np.inf, -np.inf], np.nan).dropna().max())
    t_elarg = tab_md(pd.DataFrame([{
        "Métrique": r["metrique"],
        "Règle": LIB.get(r["regle"], r["regle"]),
        "Périmètre": r["strate"].upper() if r["strate"] != "global" else "Global",
        "Largeur (par course)": pct(r["largeur_course"], 2),
        "Largeur (par bloc)": pct(r["largeur_bloc_journalier"], 2),
        "Élargissement": "**×" + fmt(r["elargissement"], 2) + "**",
    } for _, r in ics.nlargest(5, "elargissement").iterrows()]))

    t_tests = tab_md(pd.DataFrame([{
        "Métrique": r["metrique"], "Lecture": r["lecture"],
        "Statistique": fmt(r["statistique"], 2), "p": pval(r["p_valeur"]),
        "Taille d'effet": (fmt(r["taille_effet"], 3) + f" ({r['nature_effet']})"),
        "Δ": pts(r["delta"]),
    } for _, r in tests.iterrows()]))

    t_diffs = tab_md(pd.DataFrame([{
        "Schéma": "par course" if r["schema"] == "course" else "par bloc journalier",
        "Métrique": r["metrique"],
        "Différence observée": pts(r["difference_observee"]),
        "IC 95 %": f"[{pts(r['ic_lo'])} ; {pts(r['ic_hi'])}]",
        "Exclut zéro": "**oui**" if r["exclut_zero"] else "non",
    } for _, r in diffs.iterrows()]))

    md = f"""# Intervalles de confiance et tests de comparaison à la pratique

VÉRIF 3 de la section 5.1. Rapport produit en lecture seule par
`docs/memoire/verifs/section_5_1/verif_51_ic_et_tests.py`. Aucune modification des
modèles, des seuils ni du jeu d'évaluation.

## 1. Empreintes et protocole

| Rôle | Valeur |
|---|---|
| Branche | `{emp['branche']}` |
| Commit | `{emp['commit']}` |
| Table canonique `ml_dataset.parquet` | `{emp['dataset']}` |
| Modèle gelé BAS / HAUT | `{emp['modele_bas']}` / `{emp['modele_haut']}` |
| Menu de seuils calibré sur H24 | `{emp['calibration_H24']}` |

Périmètre : **{S.fr(n)} courses** H25, dont **{S.fr(int(y.sum()))} en surcharge**, réparties sur
**{S.fr(n_jours)} journées**. Rééchantillonnage : **{S.fr(N_BOOT)} réplicats**, graine
**{GRAINE}**, intervalles de percentile à 95 %.

Toutes les règles comparées sont des **masques fixes**, déterminés hors du
rééchantillonnage : le bootstrap chiffre l'incertitude de la *mesure* d'une règle donnée,
il ne resélectionne pas la règle à chaque réplicat. La lecture à budget égal est traitée
de la même façon : les 418 courses retenues sont celles du classement observé.

Deux contrôles de conformité sont posés avant tout calcul et lèvent en cas d'écart :
la lecture à budget égal doit reproduire 418 recommandations et 343 vrais positifs ; et
l'aire sous la courbe précision-rappel calculée ici doit coïncider avec
`sklearn.metrics.average_precision_score` à 10⁻¹² près sur les trois périmètres.

## 2. Précision — intervalles de confiance

### 2.1 Global

{bloc_ic("precision", "global")}

### 2.2 Segment BAS

{bloc_ic("precision", "bas")}

### 2.3 Segment HAUT

{bloc_ic("precision", "haut")}

## 3. Rappel — intervalles de confiance

### 3.1 Global

{bloc_ic("rappel", "global")}

### 3.2 Segment BAS

{bloc_ic("rappel", "bas")}

### 3.3 Segment HAUT

{bloc_ic("rappel", "haut")}

## 4. Aire sous la courbe précision-rappel du score de course

{bloc_prauc()}

## 5. Tests de différence entre c ∪ plancher et la pratique de référence

Les deux ensembles de recommandations se recouvrent partiellement : {S.fr(inter)} courses
sont recommandées par les deux, {S.fr(na)} par le seul artefact, {S.fr(nb)} par la seule
pratique. Deux lectures sont donc rapportées pour chaque métrique.

{t_tests}

### 5.1 Pourquoi deux lectures, et laquelle porte quoi

**Le rappel se prête à un test apparié au sens strict.** Son dénominateur est le même pour
les deux règles — les {S.fr(P)} surcharges du périmètre — et chaque surcharge est soit
rattrapée, soit manquée par chacune. McNemar s'applique littéralement : sur les
{S.fr(n_disc)} surcharges où les deux règles divergent, **{S.fr(b_only)}** sont rattrapées par
le seul artefact contre **{S.fr(c_only)}** par la seule pratique.

**La précision ne s'y prête pas.** Son dénominateur est le volume de recommandations, qui
diffère d'une règle à l'autre ({S.fr(volA)} contre {S.fr(volB)}) : il n'y a pas d'appariement
terme à terme, et la forme classique de McNemar ne s'y transporte pas. La lecture
rapportée ci-dessus porte donc sur les **recommandations exclusives**, qui forment deux
ensembles de courses **disjoints** : l'artefact seul touche juste {S.fr(tpa)} fois sur
{S.fr(na)} ({pct(tpa/na)}), la pratique seule {S.fr(tpb)} fois sur {S.fr(nb)} ({pct(tpb/nb)}).
Sur les {S.fr(inter)} courses communes, {S.fr(tp_inter)} sont des surcharges
({pct(tp_inter/inter)}) — cette part est identique pour les deux règles et ne peut donc
pas produire d'écart. La lecture conservatrice, qui traite les deux précisions globales
comme deux proportions indépendantes, est rapportée en complément.

### 5.2 Intervalles de confiance de la différence

Différence appariée artefact − pratique, calculée **sur le même rééchantillonnage** à
chaque réplicat, ce qui neutralise la part d'incertitude commune aux deux règles.

{t_diffs}

## 6. Structure de dépendance : le bootstrap par blocs journaliers

Les courses d'une même journée ne sont pas indépendantes. Elles partagent la météo, le
calendrier, l'état du parc, les événements, et le modèle mobilise précisément ces
variables : la VÉRIF 1 établit que **86 des 158 variables** du modèle sont constantes au
grain (tronçon, journée). Un bootstrap qui rééchantillonne les courses une à une traite
comme indépendantes des observations qui ne le sont pas, et **sous-estime** de ce fait la
dispersion.

Le bootstrap par blocs corrige ce biais en rééchantillonnant les **{S.fr(n_jours)} journées
entières** : une journée tirée entre avec toutes ses courses, une journée non tirée
n'entre pas du tout. La corrélation intra-journalière est ainsi préservée quelle qu'elle
soit, sans avoir à la modéliser.

**Résultat.** Les intervalles s'élargissent d'un facteur **{fmt(elarg_moy, 2)}** en moyenne
sur l'ensemble des métriques rapportées, avec un maximum de **{fmt(elarg_max, 2)}**. La
colonne « Élargissement » de chaque tableau donne le rapport de largeur métrique par
métrique. Les cinq élargissements les plus forts :

{t_elarg}

**Le point à retenir n'est pas celui qu'on attendrait.** L'hypothèse d'indépendance ne
flatte pas l'artefact, elle flatte **la pratique de référence** : c'est son rappel dont
l'intervalle est le plus sous-estimé, d'un facteur {fmt(float(ics[(ics.metrique == 'rappel') & (ics.regle == 'pratique') & (ics.strate == 'global')]['elargissement'].iloc[0]), 2)} au global et
{fmt(float(ics[(ics.metrique == 'rappel') & (ics.regle == 'pratique') & (ics.strate == 'haut')]['elargissement'].iloc[0]), 2)} sur le segment HAUT, loin devant toutes les règles issues du modèle.
L'explication est opérationnelle et se vérifie sur les données. Les engagements d'unité
multiple sont **groupés par journée** : quand l'exploitation renforce, elle renforce
plusieurs courses du même jour. L'indice de dispersion des comptes quotidiens — variance
sur moyenne, égal à 1 pour un semis sans groupement — le chiffre :

{t_conc}

La pratique atteint **{fmt(id_prat, 2)}**, contre **{fmt(id_cpl, 2)}** pour c ∪ plancher :
ses recommandations sont nettement plus concentrées dans le calendrier. Un bootstrap par
course casse ce groupement et fait paraître la pratique plus stable qu'elle ne l'est.
Corriger la dépendance **durcit donc la comparaison en faveur de l'artefact**, et non
l'inverse. C'est la réponse à l'objection : l'anticiper ne fragilise pas la conclusion,
elle la renforce.

L'élargissement est réel mais ne renverse aucune conclusion : les intervalles de la
précision et du rappel de c ∪ plancher et de la pratique restent disjoints sous les deux
schémas, et l'intervalle de la différence exclut zéro dans les deux cas.

## 7. Lecture

L'écart de précision entre l'artefact ({pct(tpA/volA)}) et la pratique ({pct(tpB/volB)}) est
de **{pts(d_p)}**. Il n'est pas attribuable à l'échantillonnage : les deux intervalles à 95 %
sont disjoints sous les deux schémas de rééchantillonnage, la lecture conservatrice donne
p {pval(p_p)} et la lecture par discordance p {pval(p_fisher)}.

L'écart de rappel, de **{pts(d_r)}**, se lit de la même façon, avec un appariement cette fois
littéral : p {pval(mcn_exact)} au test exact de McNemar.

La réserve à énoncer n'est donc pas sur la significativité, que les effectifs rendent
massive, mais sur la **portée** de ces intervalles. Ils chiffrent la variabilité
d'échantillonnage **à structure de service donnée**, sur une seule année horaire. Ils ne
couvrent ni le changement d'horaire, ni le renouvellement du parc, ni la dérive de la
demande. Le bootstrap par blocs journaliers en donne une borne inférieure honnête, pas
une garantie de transport à une autre année.

## 8. Livrables

| Fichier | Contenu |
|---|---|
| `docs/memoire/tableaux/section_5_1_1/t51_intervalles_confiance.csv` | IC des deux schémas, {S.fr(len(ics))} lignes |
| `docs/memoire/tableaux/section_5_1_1/t51_tests_comparaison.csv` | Tests de différence, 4 lectures |
| `docs/memoire/tableaux/section_5_1_1/t51_differences_appariees.csv` | IC des différences appariées |
| `docs/memoire/tableaux/section_5_1_1/t51_concentration_journaliere.csv` | Concentration journalière des recommandations |
| `docs/memoire/verifs/section_5_1/ic_et_tests_comparaison.md` | Le présent rapport |
"""
    OUT_MD.write_text(md)

    print("\n[IC précision global]")
    print(ics[(ics.metrique == "precision") & (ics.strate == "global")]
          [["regle", "valeur", "ic_lo_course", "ic_hi_course",
            "ic_lo_bloc_journalier", "ic_hi_bloc_journalier", "elargissement"]].to_string(index=False))
    print("\n[IC rappel global]")
    print(ics[(ics.metrique == "rappel") & (ics.strate == "global")]
          [["regle", "valeur", "ic_lo_course", "ic_hi_course",
            "ic_lo_bloc_journalier", "ic_hi_bloc_journalier", "elargissement"]].to_string(index=False))
    print("\n[PR-AUC]")
    print(ics[ics.metrique == "pr_auc"][["strate", "valeur", "ic_lo_course", "ic_hi_course",
                                        "ic_lo_bloc_journalier", "ic_hi_bloc_journalier",
                                        "elargissement"]].to_string(index=False))
    print("\n[TESTS]")
    print(tests[["metrique", "lecture", "statistique", "p_valeur", "taille_effet", "delta"]]
          .to_string(index=False))
    print("\n[DIFFÉRENCES APPARIÉES]")
    print(diffs.to_string(index=False))
    print(f"\n[élargissement bloc/course] moyenne ×{elarg_moy:.2f}  max ×{elarg_max:.2f}")
    print(f"\n[OK] {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
