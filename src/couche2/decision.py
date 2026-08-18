"""
src/couche2/decision.py — Couche 2, phase 2 : jeu de décision + calibration.

Seuillage calibré des prédictions couche 1 FIGÉES (gel v2, hash ba493568, ADR-076) au grain
course (ADR-073). Consomme les modèles figés `enrichi_seg_{bas,haut}_ba493568.json`
en LECTURE SEULE (aucun réentraînement). Importe `couche2.blocs` pour l'attribution
de segment (P2) et la baseline humaine (périmètre + labels de référence).

Grains et définitions (ADR-073) :
  - D3 score de course = MAX des prédictions couche 1 sur les tronçons.
  - D2 label positif = au moins un tronçon OBSERVÉ > 63 (2e classe, ADR-060).
  - Périmètre iso H25 (§Référence D5) = intersection prédiction (ml_dataset) ∩
    décision UM humaine (rotations) ∩ label observé (APC) = 29 222 courses.
  - Segment de course : IMPORTÉ de blocs.py (P2) — pas de règle locale.

Discipline (ADR-073 D4) : tout seuil est calibré sur H24 ; H25 lu une seule fois.
Le top-k au budget humain H25 (k=418) est une constante de comparaison (protocole,
côté humain, sans labels H25), distincte des seuils déployables calibrés H24 (R6).
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from couche2 import blocs  # noqa: E402

# ── Chemins & constantes canoniques ────────────────────────────────────────────
ROOT = blocs.ROOT
FEAT_JSON = ROOT / "outputs/couche2/features_158f_sans_simba.json"
MODEL_BAS = ROOT / "models/enrichi_seg/enrichi_seg_bas_ba493568.json"
MODEL_HAUT = ROOT / "models/enrichi_seg/enrichi_seg_haut_ba493568.json"
HASH_MODEL_BAS, HASH_MODEL_HAUT = "e4ddfccd", "df6a11c5"
SEUIL = blocs.SEUIL_ASSISES              # 63

# Ancrages figés (ADR-073 §Référence D5, vérifiés phase 0/C2) — garde-fous P3.
ISO_PERIMETRE_H25 = 29222
N_SURCH_H25, N_SURCH_H25_HAUT, N_SURCH_H25_BAS = 2072, 1224, 848
BUDGET_HUMAIN_H25 = 418                   # top-k protocolaire (comparaison headline)
BUDGET_HUMAIN_H24 = 381                   # volume iso pour la règle déployable (a')


# ── Prédictions couche 1 figées (par tronçon, avec identifiants) ────────────────
def _prep_X(d: pd.DataFrame, feats: list) -> pd.DataFrame:
    """Réplique le prep_X canonique (q_all_v18) : object→category, Int→float64."""
    X = d[[c for c in feats if c in d.columns]].copy()
    for c in X.columns:
        dt = str(X[c].dtype)
        if dt in ("object", "string"):
            X[c] = X[c].astype("category")
        elif dt.startswith("Int") or dt.startswith("UInt"):
            X[c] = X[c].astype("float64")
    return X


def _assert_models():
    import hashlib
    for path, expected in [(MODEL_BAS, HASH_MODEL_BAS), (MODEL_HAUT, HASH_MODEL_HAUT)]:
        h = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        if h != expected:
            raise RuntimeError(f"Modèle {path.name} hash {h} != {expected} (couche 1 non figée).")


def load_troncon_predictions() -> pd.DataFrame:
    """Prédictions couche 1 figées sur H24 et H25, au grain TRONÇON, avec identifiants.
    Colonnes : date, numero_train, annee, spatial_segment, target, pred."""
    blocs.assert_canonical_dataset()                          # hash ba493568 (dur)
    _assert_models()
    import json
    with open(FEAT_JSON) as f:
        feats = json.load(f)["features"]
    assert len(feats) == 158, f"attendu 158 features, obtenu {len(feats)}"

    df = pd.read_parquet(ROOT / "data/processed/ml_dataset.parquet")
    df = df[df["horaire_annee_horaire"].isin(["H24", "H25"])].copy()

    mb = xgb.XGBRegressor(); mb.load_model(str(MODEL_BAS))
    mh = xgb.XGBRegressor(); mh.load_model(str(MODEL_HAUT))
    pred = np.empty(len(df), dtype="float64")
    m_bas = (df["spatial_segment"] == "bas").values
    m_haut = (df["spatial_segment"] == "haut").values
    pred[m_bas] = mb.predict(_prep_X(df[m_bas], feats)).astype("float64")
    pred[m_haut] = mh.predict(_prep_X(df[m_haut], feats)).astype("float64")

    return pd.DataFrame({
        "date": pd.to_datetime(df["base_date"]).dt.normalize().values,
        "numero_train": df["horaire_numero_train"].astype("Int64").astype(str).values,
        "annee": df["horaire_annee_horaire"].values,
        "spatial_segment": df["spatial_segment"].values,
        "target": df["target_voyageurs_2eme_classe"].astype("float64").values,
        "resa2c": df["resa_pax_2c_J_minus_1"].astype("Float64").astype(float).values,
        "pred": pred,
    })


# ── Jeu de décision au grain COURSE (score D3, label D2, segment P2, iso-périmètre) ──
def build_decision_set() -> pd.DataFrame:
    """Grain course, périmètre iso (∩ baseline humaine). Colonnes : date, numero_train,
    annee, segment (P2, de blocs), score (D3=max préd), label (D2=∃ tronçon>63), is_UM."""
    tr = load_troncon_predictions()
    # agrégation course : score = MAX préd (D3) ; label = ∃ tronçon observé > 63 (D2)
    course = tr.groupby(["date", "numero_train", "annee"], sort=True).agg(
        score=("pred", "max"),
        charge_max=("target", "max"),
        resa2c=("resa2c", "max"),
        n_troncons=("pred", "size")).reset_index()
    course["label"] = (course["charge_max"] > SEUIL)

    # baseline humaine (blocs) : segment (P2) + décision UM, sur son périmètre apparié
    comp = blocs.load_composition()
    charge = blocs.load_charge()                              # 'segment' = règle canonique (P2)
    human = comp.merge(charge, on=["date", "numero_train"], how="inner")[
        ["date", "numero_train", "is_UM", "segment"]].copy()
    human["date"] = pd.to_datetime(human["date"]).dt.normalize()

    # iso-périmètre = intersection stricte (prédiction ∩ décision humaine ∩ label)
    ds = course.merge(human, on=["date", "numero_train"], how="inner")
    ds["is_UM"] = ds["is_UM"].astype(bool)
    return ds


# ── Garde-fous P2 / P3 (ancrages figés) ────────────────────────────────────────
def assert_perimetre_et_ancrage(ds: pd.DataFrame) -> dict:
    """P3 : sur les 29 222 courses H25, le label D2 compte exactement 2 072 positives
    (1 224 HAUT / 848 BAS). P2 : segment strictement importé de blocs (cohérence)."""
    h25 = ds[ds["annee"] == "H25"]
    n = len(h25)
    if n != ISO_PERIMETRE_H25:
        raise RuntimeError(f"P3 périmètre H25 = {n} != {ISO_PERIMETRE_H25} attendu.")
    pos = int(h25["label"].sum())
    pos_h = int(h25[(h25["segment"] == "haut") & h25["label"]].shape[0])
    pos_b = int(h25[(h25["segment"] == "bas") & h25["label"]].shape[0])
    if (pos, pos_h, pos_b) != (N_SURCH_H25, N_SURCH_H25_HAUT, N_SURCH_H25_BAS):
        raise RuntimeError(f"P3 label D2 = {pos} ({pos_h} HAUT / {pos_b} BAS) != "
                           f"{N_SURCH_H25} ({N_SURCH_H25_HAUT}/{N_SURCH_H25_BAS}) attendu.")
    # P2 : la ventilation segment côté décision doit refléter blocs (source unique)
    seg = h25["segment"].value_counts().to_dict()
    return {"n_h25": n, "positives_h25": pos, "positives_haut": pos_h, "positives_bas": pos_b,
            "segment_counts_h25": seg}


# ── 2.2 Calibration H24 (règles déployables rang/volume, walk-forward, score shift) ──
def _metrics_at(s: np.ndarray, y: np.ndarray, tau: float) -> dict:
    rec = s >= tau
    vol = int(rec.sum()); tp = int((rec & y).sum())
    return {"seuil": float(tau), "volume": vol, "VP": tp, "FP": vol - tp,
            "precision": (tp / vol) if vol else None,
            "rappel": (tp / int(y.sum())) if y.sum() else None}


def _fbeta_threshold(s: np.ndarray, y: np.ndarray, beta: float) -> float:
    """Seuil H24 maximisant F_beta (calibration in-sample H24 ; labels H24 autorisés, D4)."""
    from sklearn.metrics import precision_recall_curve
    p, r, thr = precision_recall_curve(y, s)
    b2 = beta * beta
    f = (1 + b2) * p[:-1] * r[:-1] / (b2 * p[:-1] + r[:-1] + 1e-12)
    return float(thr[int(np.argmax(f))])


def calibrate(ds: pd.DataFrame) -> dict:
    """Trois règles DÉPLOYABLES calibrées sur H24 (rang/volume, P1), stabilité walk-forward,
    diagnostic de décalage de scores H24/H25 (sans labels H25). PRÉ-ENREGISTRÉ (figé)."""
    h24 = ds[ds["annee"] == "H24"].copy()
    h25 = ds[ds["annee"] == "H25"].copy()
    s24, y24 = h24["score"].values, h24["label"].values.astype(bool)
    s25 = h25["score"].values

    # règles exprimées en RANG/VOLUME (P1) — seuil = score H24 au volume/critère
    tau_a = float(np.sort(s24)[::-1][BUDGET_HUMAIN_H24 - 1])       # (a') iso-volume 381
    tau_b = _fbeta_threshold(s24, y24, 2.0)                        # (b) F2 (recall-weighted)
    tau_c = _fbeta_threshold(s24, y24, 0.5)                        # (c) F0.5 (precision-weighted)
    regles = {
        "a_iso_volume": {"definition": "seuil H24 tel que volume = budget humain H24 (381)",
                         **_metrics_at(s24, y24, tau_a)},
        "b_rappel_renforce": {"definition": "seuil H24 maximisant F2 (beta=2, recall-weighted)",
                              **_metrics_at(s24, y24, tau_b)},
        "c_haute_precision": {"definition": "seuil H24 maximisant F0.5 (beta=0.5, precision-weighted)",
                              **_metrics_at(s24, y24, tau_c)},
    }
    # walk-forward : 4 fenêtres temporelles H24 — STABILITÉ des seuils figés (modèle figé, P1)
    h24 = h24.sort_values(["date", "numero_train"])
    win = pd.qcut(h24["date"].rank(method="first"), 4, labels=["W1", "W2", "W3", "W4"]).values
    wf = {}
    for rk, tau in [("a_iso_volume", tau_a), ("b_rappel_renforce", tau_b), ("c_haute_precision", tau_c)]:
        wf[rk] = {w: _metrics_at(h24["score"].values[win == w], h24["label"].values.astype(bool)[win == w], tau)
                  for w in ["W1", "W2", "W3", "W4"]}
    # décalage de scores H24 vs H25 (scores dispo à J-1, AUCUN label H25)
    qs = [50, 75, 90, 95, 98, 99]
    shift = {
        "quantiles_H24": {str(q): float(np.percentile(s24, q)) for q in qs},
        "quantiles_H25": {str(q): float(np.percentile(s25, q)) for q in qs},
        "mean_std_H24": [float(s24.mean()), float(s24.std())],
        "mean_std_H25": [float(s25.mean()), float(s25.std())],
        "volume_H25_aux_seuils": {rk: int((s25 >= tau).sum())
                                  for rk, tau in [("a_iso_volume", tau_a), ("b_rappel_renforce", tau_b),
                                                  ("c_haute_precision", tau_c)]},
    }
    return {"regles_deployables": regles, "walk_forward_H24": wf, "score_shift_H24_H25": shift,
            "n_courses_H24": int(len(h24)), "n_positives_H24": int(y24.sum()),
            "budget_humain_H24": BUDGET_HUMAIN_H24, "budget_humain_H25": BUDGET_HUMAIN_H25}


# ── 2.3 Évaluation H25 (exécution UNIQUE, lecture finale) ──────────────────────
def _topn_mask(h25: pd.DataFrame, n: int) -> np.ndarray:
    """Masque top-n par score décroissant, tie-break [date, numero_train] (R3)."""
    order = h25.sort_values(["score", "date", "numero_train"], ascending=[False, True, True])
    sel = set(order.index[:n])
    return h25.index.isin(sel)


def _eval(mask: np.ndarray, y: np.ndarray, P: int) -> dict:
    vol = int(mask.sum()); tp = int((mask & y).sum())
    return {"volume": vol, "VP": tp, "FP": vol - tp,
            "precision": (tp / vol) if vol else None, "recall": (tp / P) if P else None}


def _eval_full(mask: np.ndarray, y: np.ndarray, seg: np.ndarray) -> dict:
    out = {"global": _eval(mask, y, int(y.sum()))}
    for s in ("haut", "bas"):
        sm = seg == s
        out[s] = _eval(mask & sm, y & sm, int((y & sm).sum()))
    return out


def evaluate_h25(ds: pd.DataFrame, calib: dict) -> dict:
    """Exécution unique H25 : top-k protocolaire (headline) + 3 règles déployables sous
    2 conventions (seuil figé / rang) + annexe tour permissive + point humain. Tous n bruts."""
    h25 = ds[ds["annee"] == "H25"].copy()
    y = h25["label"].values.astype(bool)
    seg = h25["segment"].values
    N, P = len(h25), int(y.sum())

    # -- humain H25 (recomputé depuis ds ; = référence canonique 140/418) --
    humain = _eval_full(h25["is_UM"].values.astype(bool), y, seg)

    # -- top-k protocolaire k=418 (headline) --
    topk = _eval_full(_topn_mask(h25, BUDGET_HUMAIN_H25), y, seg)

    # -- 3 règles déployables, 2 conventions --
    reg = calib["regles_deployables"]
    deployable = {}
    for rk in ("a_iso_volume", "b_rappel_renforce", "c_haute_precision"):
        tau = reg[rk]["seuil"]
        frac = reg[rk]["volume"] / calib["n_courses_H24"]
        deployable[rk] = {
            "seuil_fige": {"tau": tau, "convention": "déployabilité (primaire menu)",
                           **_eval_full((h25["score"].values >= tau), y, seg)},
            "rang_annuel": {"n": round(frac * N), "convention": "diagnostic de drift (non déployable)",
                            **_eval_full(_topn_mask(h25, round(frac * N)), y, seg)},
        }

    # -- artefact complet au POINT DE RÉFÉRENCE : score a' (seuil figé) UNION plancher (résa>63) --
    tau_a = reg["a_iso_volume"]["seuil"]
    reco_a = h25["score"].values >= tau_a
    reco_pl = h25["resa2c"].values > SEUIL
    reco_art = reco_a | reco_pl
    artefact = {"definition": "artefact complet au point de référence (ADR-073) : score a' (iso-volume, seuil figé) UNION plancher de demande annoncée (résa>63)",
                "recouvrement": {"a_seul": int((reco_a & ~reco_pl).sum()),
                                 "plancher_seul": int((reco_pl & ~reco_a).sum()),
                                 "intersection": int((reco_a & reco_pl).sum()),
                                 "union": int(reco_art.sum())},
                **_eval_full(reco_art, y, seg)}

    # -- annexe TOUR (permissif, P4 : côté modèle = top-k protocolaire) --
    comp = blocs.load_composition()
    comp["date"] = pd.to_datetime(comp["date"]).dt.normalize()
    h25["in_topk"] = _topn_mask(h25, BUDGET_HUMAIN_H25)
    cj = comp[["date", "numero_train", "vehicles"]].merge(
        h25[["date", "numero_train", "label", "is_UM", "in_topk"]],
        on=["date", "numero_train"], how="inner")
    rows = [(d, v, bool(lab), bool(um), bool(tk))
            for d, vehs, lab, um, tk in cj[["date", "vehicles", "label", "is_UM", "in_topk"]].itertuples(index=False)
            for v in vehs]
    vc = pd.DataFrame(rows, columns=["date", "veh", "label", "is_UM", "in_topk"])
    tour = vc.groupby(["date", "veh"]).agg(just=("label", "max"), hum=("is_UM", "max"),
                                           mod=("in_topk", "max")).reset_index()
    tour_annex = {
        "grain": "PERMISSIF (tour = jour × véhicule ; justifié si >=1 course surcharge). Même agrégation des deux côtés.",
        "humain": {"n_tours_UM": int(tour["hum"].sum()),
                   "precision": float(tour[tour["hum"]]["just"].mean())},
        "modele_topk": {"n_tours_reco": int(tour["mod"].sum()),
                        "precision": float(tour[tour["mod"]]["just"].mean())},
    }

    # -- courbe PR (pour figure) --
    from sklearn.metrics import precision_recall_curve
    p_curve, r_curve, _ = precision_recall_curve(y, h25["score"].values)

    # -- bloc fourchette H25 côté humain (blocs canonique, sans projection modèle, A1) --
    bum = None
    try:
        import json as _j
        b = _j.loads(blocs.OUT_JSON.read_text())["bloc"]["assises"]
        bum = {"canonique_H25": b["bloc_canonique_identite_composition"]["annee"]["H25"],
               "sensibilite_H25": b["bloc_sensibilite_consecutivite_simple"]["annee"]["H25"]}
    except Exception:
        pass

    return {
        "meta": {"hash": "ba493568", "n_courses_H25": N, "n_positives_H25": P,
                 "n_positives_haut": int((y & (seg == "haut")).sum()),
                 "n_positives_bas": int((y & (seg == "bas")).sum())},
        "headline_top_k_protocolaire": {"k": BUDGET_HUMAIN_H25, **topk},
        "humain_H25": humain,
        "deployable_menu": deployable,
        "artefact_complet_reference": artefact,
        "annexe_tour_permissif": tour_annex,
        "bloc_fourchette_H25_cote_humain": bum,
        "_pr_curve": {"precision": p_curve.tolist(), "recall": r_curve.tolist()},
    }


def make_pr_figure(ev: dict, out_path: Path):
    """Figure précision-rappel H25 (grain course) CONFORME À LA CHARTE (`figures_style`) :
    aucun titre dans l'image (le titre vit dans la légende du manuscrit), libellés français
    sans identifiant interne ni tiret cadratin, palette Okabe-Ito, PNG reproductible. Le
    contrôle `fs.check_conformite` s'exécute à l'enregistrement (lève si non conforme)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(ROOT / "scripts"))
    import figures_style as fs                                   # noqa: E402
    fs.apply_style()

    LIB = {"a_iso_volume": "Règle a′ (iso-volume, seuil figé)",
           "b_rappel_renforce": "Règle b (rappel renforcé, seuil figé)",
           "c_haute_precision": "Règle c (haute précision, seuil figé)"}
    COL = {"a_iso_volume": "#009E73", "b_rappel_renforce": "#CC79A7", "c_haute_precision": "#E69F00"}

    pr = ev["_pr_curve"]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(pr["recall"], pr["precision"], color=fs.COULEUR_BAS, lw=1.8,
            label="Modèle : courbe précision-rappel (H25, grain course)")
    tk = ev["headline_top_k_protocolaire"]
    ax.scatter(tk["global"]["recall"], tk["global"]["precision"], color="#D55E00",
               marker="*", s=150, zorder=5, label=f"Top-k protocolaire (k={tk['k']})")
    h = ev["humain_H25"]["global"]
    ax.scatter(h["recall"], h["precision"], color="#000000", marker="D", s=80, zorder=5,
               label="Pratique humaine H25 (418 unités multiples)")
    for rk, d in ev["deployable_menu"].items():
        g = d["seuil_fige"]["global"]
        ax.scatter(g["recall"], g["precision"], color=COL[rk], marker="o", s=70, zorder=4,
                   label=LIB[rk])
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(0.0, 1.03)
    fs.finalize(ax, xlabel="Rappel (grain course, H25)",
                ylabel="Précision (grain course, H25)", periode="H25")
    ax.legend(loc="upper right")
    fs.save(fig, out_path)
    plt.close(fig)


if __name__ == "__main__":
    import json
    ds = build_decision_set()
    info = assert_perimetre_et_ancrage(ds)
    for a in ("H24", "H25"):
        s = ds[ds["annee"] == a]
        print(f"[{a}] courses iso={len(s):,} | positives(D2)={int(s['label'].sum())} "
              f"| UM humaines={int(s['is_UM'].sum())} | score[min,med,max]="
              f"[{s['score'].min():.1f}, {s['score'].median():.1f}, {s['score'].max():.1f}]")
    print(f"[P2/P3 OK] {info}\n")

    calib = calibrate(ds)
    out = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"
    out.write_text(json.dumps(calib, indent=2, ensure_ascii=False))
    print("── Règles déployables FIGÉES (calibration H24) ──")
    for rk, d in calib["regles_deployables"].items():
        print(f"  {rk:20} seuil={d['seuil']:.2f} | vol_H24={d['volume']} | "
              f"prec_H24={d['precision']:.3f} | rappel_H24={d['rappel']:.3f}")
    print("── Décalage de scores H24→H25 (volume H25 aux seuils figés) ──")
    for rk, v in calib["score_shift_H24_H25"]["volume_H25_aux_seuils"].items():
        print(f"  {rk:20} volume_H25={v}")
    print(f"  quantiles H24 95/99 = {calib['score_shift_H24_H25']['quantiles_H24']['95']:.1f}/"
          f"{calib['score_shift_H24_H25']['quantiles_H24']['99']:.1f} | "
          f"H25 95/99 = {calib['score_shift_H24_H25']['quantiles_H25']['95']:.1f}/"
          f"{calib['score_shift_H24_H25']['quantiles_H25']['99']:.1f}")
    print(f"[OK] {out.name}")

    # ── 2.3 exécution unique H25 ──
    ev = evaluate_h25(ds, calib)
    FIG = ROOT / "outputs/couche2/figures"
    make_pr_figure(ev, FIG / "couche2_pr_h25_ba493568.png")
    ev.pop("_pr_curve")
    eval_out = ROOT / "outputs/couche2/q_couche2_eval_ba493568.json"
    eval_out.write_text(json.dumps(ev, indent=2, ensure_ascii=False))

    def _g(d): return f"vol={d['global']['volume']} P={_p(d['global']['precision'])} R={_p(d['global']['recall'])}"
    _p = lambda x: "n/d" if x is None else f"{x*100:.1f}%"
    print("\n" + "=" * 70 + "\n2.3 — ÉVALUATION H25 (exécution unique)\n" + "=" * 70)
    print(f"  positives H25 = {ev['meta']['n_positives_H25']} ({ev['meta']['n_positives_haut']} HAUT / {ev['meta']['n_positives_bas']} BAS)")
    print(f"\n  HEADLINE top-k protocolaire (k=418) : {_g(ev['headline_top_k_protocolaire'])}")
    for s in ("haut", "bas"):
        d = ev['headline_top_k_protocolaire'][s]
        print(f"     {s.upper():4} vol={d['volume']} VP={d['VP']} P={_p(d['precision'])} R={_p(d['recall'])}")
    print(f"  HUMAIN H25 (418 UM)                 : {_g(ev['humain_H25'])}")
    for s in ("haut", "bas"):
        d = ev['humain_H25'][s]
        print(f"     {s.upper():4} vol={d['volume']} VP={d['VP']} P={_p(d['precision'])} R={_p(d['recall'])}")
    print("\n  MENU DÉPLOYABLE (global) :")
    for rk, d in ev['deployable_menu'].items():
        print(f"   {rk:20} seuil_figé: {_g(d['seuil_fige'])}  |  rang: {_g(d['rang_annuel'])}")
    t = ev['annexe_tour_permissif']
    print(f"\n  ANNEXE TOUR (permissif) : humain {t['humain']['n_tours_UM']} tours P={_p(t['humain']['precision'])}"
          f"  |  modèle top-k {t['modele_topk']['n_tours_reco']} tours P={_p(t['modele_topk']['precision'])}")
    b = ev['bloc_fourchette_H25_cote_humain']
    if b:
        print(f"  BLOC fourchette H25 humain : [{_p(b['canonique_H25']['precision_bloc'])} ; {_p(b['sensibilite_H25']['precision_bloc'])}] (sans projection modèle)")
    print(f"[OK] {eval_out.name} + couche2_pr_h25_ba493568.png")
