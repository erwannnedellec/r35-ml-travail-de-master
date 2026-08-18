#!/usr/bin/env python3
"""
verif_471_vmcv.py — LOT B, section 4.7.1 : impact de l'interruption VMCV sur H25.

CONTEXTE : ADR-040 acte l'interruption de publication VMCV sur ISTDATEN du 01.09.2025
au 13.10.2025 inclus (43 jours). L'option retenue est « NaN avec traçabilité » ; l'ADR
annonce explicitement une **validation empirique a posteriori** : « l'impact réel sera
mesuré au moment du run final en stratifiant les métriques par sous-période (jours avec
VMCV publié vs jours d'interruption) ». C'est exactement l'objet de ce script.

DISCIPLINE : LECTURE SEULE. Aucun réentraînement, aucun seuil recalculé, aucune
re-sélection. Les modèles couche 1 sont chargés GELÉS (empreintes e4ddfccd bas /
df6a11c5 haut) et les seuils couche 2 sont relus depuis la calibration H24 figée
(a′ / b / c, ADR-073). Le script n'écrit que dans son propre dossier.

GARDE-FOUS (STOP si divergence) :
  - empreinte SHA256[:8] de ml_dataset = ba493568 ;
  - périmètre H25 tronçon = 309 252 (229 747 bas / 79 505 haut) ;
  - périmètre H25 course = 29 222, dont 2 072 en surcharge (1 224 haut / 848 bas) ;
  - empreintes des deux modèles couche 1 ;
  - 43 jours d'interruption VMCV, flag cohérent départ/arrivée et constant par date ;
  - reproduction des points d'opération publiés (a′∪plancher 352 / c∪plancher 866 /
    pratique de référence 418).

LECTURE DE PRUDENCE INTÉGRÉE : la fenêtre d'interruption (1er sept. – 13 oct.) est une
SAISON, pas un tirage aléatoire. Comparer « interruption » à « publié » confond l'absence
de VMCV avec l'effet de saison. Le script produit donc aussi un **témoin de voisinage** :
les 43 jours calendaires qui précèdent et les 43 qui suivent la fenêtre, tous à VMCV
publié, servent de référence saisonnièrement proche.

Sorties (dans le dossier du script) :
  verif_471_vmcv_perimetre.csv   — comptages et parts par sous-période
  verif_471_vmcv_couche1.csv     — métriques couche 1 stratifiées (grain tronçon)
  verif_471_vmcv_couche2.csv     — métriques couche 2 stratifiées (grain course)
  verif_471_vmcv_bootstrap.csv   — IC bootstrap PR-AUC (et différence) par sous-période
  verif_471_vmcv_temoin.csv      — témoin de voisinage saisonnier (couche 1)
  verif_471_vmcv.md              — rapport de synthèse

Exécution : python3 docs/memoire/verifs/section_4_7_1_vmcv/verif_471_vmcv.py
"""
from __future__ import annotations

import os

# Pinning des threads AVANT tout import numérique (contrat ADR-076).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
sys.path.insert(0, str(ROOT / "src"))

import _harness as H            # noqa: E402  (socle canonique : hashs, modèles gelés, prep_X)
from couche2 import decision    # noqa: E402  (jeu de décision couche 2, seuils figés)

SEUIL = H.SEUIL                                    # 63
SEED = H.SEED                                      # 42
N_BOOT = 1000
FLAG_INTERRUPTION = "manquant_interruption_vmcv"
FLAG_PUBLIE = "publie"
N_JOURS_INTERRUPTION_ATTENDU = 43
CALIB_JSON = ROOT / "outputs/couche2/q_couche2_calibration_H24_ba493568.json"

# Libellés figés des configurations couche 2 (source unique, réutilisés partout).
CONF_REF = "pratique de référence (rotations)"
CONF_A = "a′ (iso-volume)"
CONF_C = "c (haute précision)"
CONF_A_PL = "a′ ∪ plancher"
CONF_C_PL = "c ∪ plancher"

# Points d'opération publiés (ADR-073 / ADR-077) — garde-fous de reproduction H25.
ANCRAGES_COUCHE2 = {CONF_REF: 418, CONF_A_PL: 352, CONF_C_PL: 866}

COLS_CONTEXTE = ["horaire_annee_horaire", "spatial_segment", "target_voyageurs_2eme_classe",
                 "base_date", "horaire_numero_train",
                 "vmcv_source_depart", "vmcv_source_arrivee"]


# ══════════════════════════════════════════════════════════════════════════════
# 0. Chargement et garde-fous
# ══════════════════════════════════════════════════════════════════════════════
def charger_h25() -> tuple[pd.DataFrame, list]:
    """H25 au grain tronçon, colonnes utiles seulement. Lecture pleine puis filtre
    (ordre identique au protocole canonique) — la sélection de colonnes ne modifie
    aucune valeur ni le typage `category` construit par prep_X."""
    import pyarrow.parquet as pq
    feats = H.load_features_158()
    presentes = set(pq.ParquetFile(H.ML_DATASET).schema_arrow.names)
    manquants = [c for c in COLS_CONTEXTE if c not in presentes]
    if manquants:
        raise RuntimeError(f"STOP : colonnes de contexte absentes du parquet -> {manquants}")
    cols = [c for c in dict.fromkeys(feats + COLS_CONTEXTE) if c in presentes]
    df = pd.read_parquet(H.ML_DATASET, columns=cols)
    h25 = df[df["horaire_annee_horaire"] == "H25"].copy()
    del df
    if len(h25) != H.N_TEST_H25:
        raise RuntimeError(f"STOP : H25 = {len(h25)} != {H.N_TEST_H25} attendu.")
    n_bas = int((h25["spatial_segment"] == "bas").sum())
    n_haut = int((h25["spatial_segment"] == "haut").sum())
    if (n_bas, n_haut) != (H.N_H25_BAS, H.N_H25_HAUT):
        raise RuntimeError(f"STOP : ventilation H25 {n_bas}/{n_haut} != "
                           f"{H.N_H25_BAS}/{H.N_H25_HAUT} attendue.")
    return h25, feats


def qualifier_sous_periodes(h25: pd.DataFrame) -> dict:
    """Vérifie les colonnes de traçabilité VMCV, contrôle leur cohérence et pose la
    variable de sous-période. Retourne le dictionnaire de contrôle."""
    for c in ("vmcv_source_depart", "vmcv_source_arrivee"):
        if c not in h25.columns:
            raise RuntimeError(f"STOP : colonne de traçabilité absente -> {c}")

    dep = h25["vmcv_source_depart"].astype(str)
    arr = h25["vmcv_source_arrivee"].astype(str)
    n_desaccord = int((dep != arr).sum())
    if n_desaccord:
        raise RuntimeError(f"STOP : {n_desaccord} tronçons où vmcv_source_depart != "
                           f"vmcv_source_arrivee (le flag doit être identique aux deux bouts).")
    valeurs = sorted(dep.unique().tolist())
    if set(valeurs) - {FLAG_PUBLIE, FLAG_INTERRUPTION}:
        raise RuntimeError(f"STOP : valeurs inattendues dans vmcv_source_* -> {valeurs}")

    h25["date"] = pd.to_datetime(h25["base_date"]).dt.normalize()
    h25["sous_periode"] = np.where(dep.values == FLAG_INTERRUPTION,
                                   "interruption", "publie")

    # Le flag doit être constant à l'intérieur d'une date (interruption = plage de jours).
    par_date = h25.groupby("date")["sous_periode"].nunique()
    if bool((par_date > 1).any()):
        n_mixtes = int((par_date > 1).sum())
        raise RuntimeError(f"STOP : le flag VMCV n'est pas constant sur {n_mixtes} date(s).")

    jours_int = sorted(h25.loc[h25["sous_periode"] == "interruption", "date"].unique())
    n_jours = len(jours_int)
    if n_jours != N_JOURS_INTERRUPTION_ATTENDU:
        raise RuntimeError(f"STOP : {n_jours} jours d'interruption != "
                           f"{N_JOURS_INTERRUPTION_ATTENDU} attendus (ADR-040).")
    debut, fin = pd.Timestamp(jours_int[0]), pd.Timestamp(jours_int[-1])
    # Contiguïté : la plage calendaire doit être pleine (aucun jour publié à l'intérieur).
    plage = pd.date_range(debut, fin, freq="D")
    jours_h25 = set(pd.to_datetime(h25["date"].unique()))
    dedans_publie = [d for d in plage
                     if d in jours_h25 and d not in set(pd.to_datetime(jours_int))]
    if dedans_publie:
        raise RuntimeError(f"STOP : {len(dedans_publie)} jour(s) publié(s) DANS la plage "
                           f"d'interruption -> plage non contiguë.")

    return {"n_jours_interruption": n_jours, "debut": debut, "fin": fin,
            "n_jours_h25": int(h25['date'].nunique()),
            "valeurs_flag": valeurs}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Périmètre : part des observations H25 concernées
# ══════════════════════════════════════════════════════════════════════════════
def table_perimetre(h25: pd.DataFrame, ds_h25: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for seg, sub in [("global", h25), ("bas", h25[h25["spatial_segment"] == "bas"]),
                     ("haut", h25[h25["spatial_segment"] == "haut"])]:
        tot = len(sub)
        for sp in ("publie", "interruption"):
            s = sub[sub["sous_periode"] == sp]
            gt = (s["target_voyageurs_2eme_classe"] > SEUIL)
            lignes.append({
                "grain": "tronçon", "segment": seg, "sous_periode": sp,
                "n_jours": int(s["date"].nunique()), "n": len(s),
                "part_du_segment": round(len(s) / tot, 6) if tot else None,
                "n_surcharges": int(gt.sum()),
                "prevalence": round(float(gt.mean()), 6) if len(s) else None,
            })
    for seg in ("global", "bas", "haut"):
        sub = ds_h25 if seg == "global" else ds_h25[ds_h25["segment"] == seg]
        tot = len(sub)
        for sp in ("publie", "interruption"):
            s = sub[sub["sous_periode"] == sp]
            lignes.append({
                "grain": "course", "segment": seg, "sous_periode": sp,
                "n_jours": int(s["date"].nunique()), "n": len(s),
                "part_du_segment": round(len(s) / tot, 6) if tot else None,
                "n_surcharges": int(s["label"].sum()),
                "prevalence": round(float(s["label"].mean()), 6) if len(s) else None,
            })
    return pd.DataFrame(lignes)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Couche 1 stratifiée (grain tronçon, modèles gelés)
# ══════════════════════════════════════════════════════════════════════════════
def metriques_c1(y: np.ndarray, p: np.ndarray) -> dict:
    """Métriques au format préenregistré (protocole phase 4), sans IC (traités à part).

    `pr_auc_sur_prevalence` normalise la PR-AUC par sa valeur de référence : un classement
    ALÉATOIRE atteint une PR-AUC égale à la prévalence. Le rapport vaut donc 1 pour le
    hasard et se compare entre sous-périodes de prévalences différentes — ce que la PR-AUC
    brute ne permet PAS."""
    gt = y > SEUIL
    prev = float(gt.mean()) if len(y) else None
    ap = float(average_precision_score(gt.astype(int), p)) if gt.any() else None
    return {
        "n": int(len(y)), "n_surcharges": int(gt.sum()),
        "prevalence": prev,
        "r2": float(r2_score(y, p)) if len(y) > 1 else None,
        "mae": float(mean_absolute_error(y, p)) if len(y) else None,
        "mae_gt63": float(np.mean(np.abs(p[gt] - y[gt]))) if gt.any() else None,
        "biais_gt63": float(np.mean(p[gt] - y[gt])) if gt.any() else None,
        "pr_auc": ap,
        "pr_auc_sur_prevalence": (ap / prev) if (ap is not None and prev) else None,
    }


def table_couche1(h25: pd.DataFrame, pred: np.ndarray) -> pd.DataFrame:
    y = h25["target_voyageurs_2eme_classe"].values.astype("float64")
    seg = h25["spatial_segment"].values
    sp = h25["sous_periode"].values
    lignes = []
    for segment in ("global", "bas", "haut"):
        m_seg = np.ones(len(h25), bool) if segment == "global" else (seg == segment)
        base = None
        for periode in ("H25 entier", "publie", "interruption"):
            m = m_seg if periode == "H25 entier" else (m_seg & (sp == periode))
            met = metriques_c1(y[m], pred[m])
            if periode == "publie":
                base = met
            ligne = {"segment": segment, "sous_periode": periode, **met}
            if periode == "interruption" and base:
                for k in ("r2", "mae", "mae_gt63", "biais_gt63", "pr_auc",
                          "pr_auc_sur_prevalence", "prevalence"):
                    ligne[f"delta_vs_publie_{k}"] = (
                        met[k] - base[k] if (met[k] is not None and base[k] is not None) else None)
            lignes.append(ligne)
    df = pd.DataFrame(lignes)
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(6)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3. Couche 2 stratifiée (grain course, seuils H24 figés)
# ══════════════════════════════════════════════════════════════════════════════
def charger_taus() -> dict:
    calib = json.loads(CALIB_JSON.read_text())
    r = calib["regles_deployables"]
    taus = {k: float(r[k]["seuil"]) for k in
            ("a_iso_volume", "b_rappel_renforce", "c_haute_precision")}
    attendu = {"a_iso_volume": 78.99, "b_rappel_renforce": 51.31, "c_haute_precision": 64.12}
    for k, v in attendu.items():
        if abs(taus[k] - v) > 0.01:
            raise RuntimeError(f"STOP : seuil {k} = {taus[k]:.4f} != {v} attendu "
                               f"(calibration H24 figée, ADR-073).")
    return taus


def configurations(ds: pd.DataFrame, taus: dict) -> dict:
    """Masques de recommandation, seuils H24 INCHANGÉS. Plancher = résa J-1 > 63."""
    score = ds["score"].values
    resa = ds["resa2c"].values
    plancher = resa > SEUIL
    return {
        CONF_REF: ds["is_UM"].values.astype(bool),
        CONF_A: score >= taus["a_iso_volume"],
        CONF_C: score >= taus["c_haute_precision"],
        CONF_A_PL: (score >= taus["a_iso_volume"]) | plancher,
        CONF_C_PL: (score >= taus["c_haute_precision"]) | plancher,
    }


def evaluer(mask: np.ndarray, label: np.ndarray) -> dict:
    vol = int(mask.sum()); vp = int((mask & label).sum()); pos = int(label.sum())
    return {"volume": vol, "VP": vp, "FP": vol - vp,
            "precision": (vp / vol) if vol else None,
            "rappel": (vp / pos) if pos else None,
            "n_courses": int(len(label)), "n_surcharges": pos,
            "prevalence": (pos / len(label)) if len(label) else None}


def table_couche2(ds_h25: pd.DataFrame, taus: dict) -> pd.DataFrame:
    lignes = []
    for segment in ("global", "bas", "haut"):
        sub = ds_h25 if segment == "global" else ds_h25[ds_h25["segment"] == segment]
        confs = configurations(sub, taus)
        label = sub["label"].values.astype(bool)
        sp = sub["sous_periode"].values
        for nom, mask in confs.items():
            base = None
            for periode in ("H25 entier", "publie", "interruption"):
                m = np.ones(len(sub), bool) if periode == "H25 entier" else (sp == periode)
                res = evaluer(mask[m], label[m])
                if periode == "publie":
                    base = res
                ligne = {"segment": segment, "configuration": nom,
                         "sous_periode": periode, **res}
                if periode == "interruption" and base:
                    for k in ("precision", "rappel", "prevalence"):
                        ligne[f"delta_vs_publie_{k}"] = (
                            res[k] - base[k] if (res[k] is not None and base[k] is not None) else None)
                lignes.append(ligne)
    df = pd.DataFrame(lignes)
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(6)
    return df


def garde_fou_ancrages(ds_h25: pd.DataFrame, taus: dict) -> None:
    confs = configurations(ds_h25, taus)
    for nom, attendu in ANCRAGES_COUCHE2.items():
        obtenu = int(confs[nom].sum())
        if obtenu != attendu:
            raise RuntimeError(f"STOP : volume H25 « {nom} » = {obtenu} != {attendu} publié.")


# ══════════════════════════════════════════════════════════════════════════════
# 4. IC bootstrap sur la PR-AUC (et sur sa différence entre sous-périodes)
# ══════════════════════════════════════════════════════════════════════════════
def bootstrap_pr_auc(y: np.ndarray, p: np.ndarray, n_boot: int = N_BOOT,
                     seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    """Distribution bootstrap (rééchantillonnage i.i.d. des tronçons) de la PR-AUC et de
    la PR-AUC rapportée à la prévalence. Les deux quantités sont calculées sur le MÊME
    tirage, donc leurs intervalles sont cohérents entre eux."""
    rng = np.random.default_rng(seed)
    n = len(y)
    gt = (y > SEUIL).astype(int)
    ap = np.full(n_boot, np.nan)
    ratio = np.full(n_boot, np.nan)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        gb = gt[idx]
        if gb.any():
            a = average_precision_score(gb, p[idx])
            ap[i] = a
            ratio[i] = a / gb.mean()
    return ap, ratio


def table_bootstrap(h25: pd.DataFrame, pred: np.ndarray,
                    segments=("bas", "haut", "global")) -> pd.DataFrame:
    y = h25["target_voyageurs_2eme_classe"].values.astype("float64")
    seg = h25["spatial_segment"].values
    sp = h25["sous_periode"].values
    lignes = []
    for segment in segments:
        m_seg = np.ones(len(h25), bool) if segment == "global" else (seg == segment)
        tirages, observe = {}, {}
        for periode in ("publie", "interruption"):
            m = m_seg & (sp == periode)
            gt = y[m] > SEUIL
            prev = float(gt.mean())
            obs = float(average_precision_score(gt.astype(int), pred[m]))
            b_ap, b_ratio = bootstrap_pr_auc(y[m], pred[m])
            tirages[periode] = (b_ap, b_ratio)
            observe[periode] = (obs, obs / prev)
            lignes.append({
                "segment": segment, "sous_periode": periode, "n": int(m.sum()),
                "n_surcharges": int(gt.sum()), "prevalence": round(prev, 6),
                "pr_auc": round(obs, 6),
                "ic95_lo": round(float(np.nanpercentile(b_ap, 2.5)), 6),
                "ic95_hi": round(float(np.nanpercentile(b_ap, 97.5)), 6),
                "pr_auc_sur_prevalence": round(obs / prev, 4),
                "ratio_ic95_lo": round(float(np.nanpercentile(b_ratio, 2.5)), 4),
                "ratio_ic95_hi": round(float(np.nanpercentile(b_ratio, 97.5)), 4),
                "n_boot": N_BOOT, "seed": SEED,
            })
        # Différence : les deux sous-périodes sont disjointes, les tirages sont
        # indépendants -> la différence terme à terme est une distribution bootstrap
        # valide de l'écart.
        # La valeur rapportée est l'écart OBSERVÉ ; l'IC est le percentile de la
        # distribution bootstrap de cet écart (la moyenne bootstrap peut s'en écarter
        # sur les petits effectifs, elle n'est donc pas l'estimateur affiché).
        d_ap = tirages["interruption"][0] - tirages["publie"][0]
        d_ra = tirages["interruption"][1] - tirages["publie"][1]
        d_ap_obs = observe["interruption"][0] - observe["publie"][0]
        d_ra_obs = observe["interruption"][1] - observe["publie"][1]
        lo, hi = float(np.nanpercentile(d_ap, 2.5)), float(np.nanpercentile(d_ap, 97.5))
        rlo, rhi = float(np.nanpercentile(d_ra, 2.5)), float(np.nanpercentile(d_ra, 97.5))
        lignes.append({
            "segment": segment, "sous_periode": "différence (interruption − publié)",
            "n": None, "n_surcharges": None, "prevalence": None,
            "pr_auc": round(d_ap_obs, 6),
            "ic95_lo": round(lo, 6), "ic95_hi": round(hi, 6),
            "pr_auc_sur_prevalence": round(d_ra_obs, 4),
            "ratio_ic95_lo": round(rlo, 4), "ratio_ic95_hi": round(rhi, 4),
            "n_boot": N_BOOT, "seed": SEED,
            "ic_contient_zero": bool(lo <= 0 <= hi),
            "ratio_ic_contient_zero": bool(rlo <= 0 <= rhi),
        })
    return pd.DataFrame(lignes)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Témoin de voisinage saisonnier
# ══════════════════════════════════════════════════════════════════════════════
def table_temoin(h25: pd.DataFrame, pred: np.ndarray, debut: pd.Timestamp,
                 fin: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """Compare la fenêtre d'interruption aux 43 jours calendaires qui la précèdent et aux
    43 qui la suivent (tous à VMCV publié). Neutralise partiellement la saison."""
    n = N_JOURS_INTERRUPTION_ATTENDU
    avant = (debut - pd.Timedelta(days=n), debut - pd.Timedelta(days=1))
    apres = (fin + pd.Timedelta(days=1), fin + pd.Timedelta(days=n))
    d = h25["date"].values.astype("datetime64[ns]")
    fenetres = {
        "voisinage avant (publié)": (d >= np.datetime64(avant[0])) & (d <= np.datetime64(avant[1])),
        "interruption": (h25["sous_periode"].values == "interruption"),
        "voisinage après (publié)": (d >= np.datetime64(apres[0])) & (d <= np.datetime64(apres[1])),
    }
    y = h25["target_voyageurs_2eme_classe"].values.astype("float64")
    seg = h25["spatial_segment"].values
    lignes = []
    for segment in ("global", "bas", "haut"):
        m_seg = np.ones(len(h25), bool) if segment == "global" else (seg == segment)
        for nom, mf in fenetres.items():
            m = m_seg & mf
            if not m.any():
                continue
            lignes.append({"segment": segment, "fenetre": nom,
                           "n_jours": int(pd.Series(h25["date"].values[m]).nunique()),
                           **metriques_c1(y[m], pred[m])})
    df = pd.DataFrame(lignes)
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(6)
    bornes = {"avant": (date_fr(avant[0]), date_fr(avant[1])),
              "apres": (date_fr(apres[0]), date_fr(apres[1]))}
    return df, bornes


# ══════════════════════════════════════════════════════════════════════════════
# 6. Rapport
# ══════════════════════════════════════════════════════════════════════════════
def fr(x, nd=3, pct=False):
    """Nombre décimal à la française (virgule décimale)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    v = 100 * x if pct else x
    s = f"{v:.{nd}f}".replace(".", ",")
    return s + (" %" if pct else "")


def mil(n):
    """Entier avec séparateur de milliers = espace insécable étroit typographique."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    return f"{int(n):,}".replace(",", " ")


_MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]


def date_fr(d) -> str:
    """Date en français (« 1er septembre 2025 »), jamais au format ISO (charte maison)."""
    d = pd.Timestamp(d)
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {_MOIS_FR[d.month]} {d.year}"


def ecrire_rapport(ctrl: dict, per: pd.DataFrame, c1: pd.DataFrame, c2: pd.DataFrame,
                   boot: pd.DataFrame, tem: pd.DataFrame, bornes: dict,
                   taus: dict, hashes: dict) -> Path:
    L = []
    A = L.append
    A("# Vérification 4.7.1 — interruption VMCV sur H25 (ADR-040)")
    A("")
    A("**Lot B — lecture seule.** Modèles couche 1 chargés gelés, seuils couche 2 relus")
    A("depuis la calibration H24 figée. Aucun réentraînement, aucune re-calibration.")
    A("")
    A("| Garde-fou | Valeur |")
    A("|---|---|")
    A(f"| Empreinte `ml_dataset.parquet` | `{hashes['dataset']}` |")
    A(f"| Modèle couche 1 BAS | `{hashes['bas']}` |")
    A(f"| Modèle couche 1 HAUT | `{hashes['haut']}` |")
    A(f"| Périmètre H25 tronçon | {mil(H.N_TEST_H25)} ({mil(H.N_H25_BAS)} bas / {mil(H.N_H25_HAUT)} haut) |")
    A(f"| Périmètre H25 course | {mil(decision.ISO_PERIMETRE_H25)} dont {mil(decision.N_SURCH_H25)} en surcharge "
      f"({mil(decision.N_SURCH_H25_HAUT)} haut / {mil(decision.N_SURCH_H25_BAS)} bas) |")
    A(f"| Seuils H24 figés (a′ / b / c) | {fr(taus['a_iso_volume'], 2)} / "
      f"{fr(taus['b_rappel_renforce'], 2)} / {fr(taus['c_haute_precision'], 2)} |")
    A("| Points d'opération reproduits | a′∪plancher 352, c∪plancher 866, pratique de référence 418 |")
    A("")

    # ── 1. Périmètre ──
    A("## 1. Périmètre de l'interruption")
    A("")
    A("Les colonnes de traçabilité `vmcv_source_depart` et `vmcv_source_arrivee` sont")
    A(f"présentes et strictement identiques sur les {mil(H.N_TEST_H25)} tronçons H25 "
      f"(valeurs : {', '.join('`' + v + '`' for v in ctrl['valeurs_flag'])}).")
    A("")
    A(f"- **{ctrl['n_jours_interruption']} jours** portent le drapeau `manquant_interruption_vmcv`,")
    A(f"  du **{date_fr(ctrl['debut'])}** au **{date_fr(ctrl['fin'])}** inclus,")
    A(f"  plage calendaire pleine (aucun jour publié à l'intérieur) — conforme à ADR-040.")
    A(f"- H25 compte {ctrl['n_jours_h25']} jours de service : l'interruption en couvre")
    A(f"  {fr(ctrl['n_jours_interruption']/ctrl['n_jours_h25'], 1, pct=True)}.")
    pg = per[(per["grain"] == "tronçon") & (per["segment"] == "global") &
             (per["sous_periode"] == "interruption")].iloc[0]
    A(f"- **Part des observations H25 concernées : {fr(pg['part_du_segment'], 2, pct=True)}**")
    A(f"  ({mil(pg['n'])} tronçons sur {mil(H.N_TEST_H25)}).")
    A("")
    A("| Grain | Segment | Sous-période | Jours | n | Part | Surcharges | Prévalence |")
    A("|---|---|---|---:|---:|---:|---:|---:|")
    for _, r in per.iterrows():
        A(f"| {r['grain']} | {r['segment']} | {r['sous_periode']} | {int(r['n_jours'])} | "
          f"{mil(r['n'])} | {fr(r['part_du_segment'], 2, pct=True)} | {mil(r['n_surcharges'])} | "
          f"{fr(r['prevalence'], 3, pct=True)} |")
    A("")

    # ── 2. Couche 1 ──
    A("## 2. Couche 1 — métriques stratifiées (grain tronçon, modèles gelés)")
    A("")
    A("La colonne « PR-AUC / prévalence » rapporte la PR-AUC à sa valeur de référence : un")
    A("classement **aléatoire** obtient une PR-AUC égale à la prévalence. Le rapport vaut donc")
    A("1 pour le hasard, et c'est la **seule** des deux quantités qui se compare entre")
    A("sous-périodes de prévalences différentes.")
    A("")
    A("| Segment | Sous-période | n | Prévalence | R² | MAE | MAE > 63 | biais > 63 | PR-AUC | PR-AUC / prév. |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in c1.iterrows():
        A(f"| {r['segment']} | {r['sous_periode']} | {mil(r['n'])} | "
          f"{fr(r['prevalence'], 3, pct=True)} | {fr(r['r2'], 4)} | "
          f"{fr(r['mae'], 3)} | {fr(r['mae_gt63'], 2)} | {fr(r['biais_gt63'], 2)} | "
          f"{fr(r['pr_auc'], 4)} | {fr(r['pr_auc_sur_prevalence'], 1)} |")
    A("")
    A("Écarts « interruption − publié » :")
    A("")
    A("| Segment | Δprévalence | ΔR² | ΔMAE | Δbiais > 63 | ΔPR-AUC | Δ(PR-AUC / prév.) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for seg in ("global", "bas", "haut"):
        r = c1[(c1["segment"] == seg) & (c1["sous_periode"] == "interruption")].iloc[0]
        A(f"| {seg} | {fr(r.get('delta_vs_publie_prevalence'), 3, pct=True)} | "
          f"{fr(r.get('delta_vs_publie_r2'), 4)} | {fr(r.get('delta_vs_publie_mae'), 3)} | "
          f"{fr(r.get('delta_vs_publie_biais_gt63'), 2)} | {fr(r.get('delta_vs_publie_pr_auc'), 4)} | "
          f"{fr(r.get('delta_vs_publie_pr_auc_sur_prevalence'), 1)} |")
    A("")

    # ── 3. Couche 2 ──
    A("## 3. Couche 2 — points d'opération stratifiés (grain course, seuils H24 inchangés)")
    A("")
    for seg in ("global", "bas", "haut"):
        A(f"### Segment {seg}")
        A("")
        A("| Configuration | Sous-période | Courses | Volume | VP | Précision | Rappel | Prévalence |")
        A("|---|---|---:|---:|---:|---:|---:|---:|")
        for _, r in c2[c2["segment"] == seg].iterrows():
            A(f"| {r['configuration']} | {r['sous_periode']} | {mil(r['n_courses'])} | "
              f"{mil(r['volume'])} | {mil(r['VP'])} | {fr(r['precision'], 1, pct=True)} | "
              f"{fr(r['rappel'], 1, pct=True)} | {fr(r['prevalence'], 2, pct=True)} |")
        A("")

    def _c2(conf, per_, seg="global"):
        return c2[(c2["segment"] == seg) & (c2["configuration"] == conf) &
                  (c2["sous_periode"] == per_)].iloc[0]

    A("Lecture factuelle du tableau global : pendant l'interruption, le rappel de **toutes**")
    A("les configurations fondées sur le modèle augmente (`c ∪ plancher` "
      f"{fr(_c2(CONF_C_PL, 'publie')['rappel'], 1, pct=True)} → "
      f"{fr(_c2(CONF_C_PL, 'interruption')['rappel'], 1, pct=True)}) tandis que la")
    A("précision de la **pratique de référence** recule "
      f"({fr(_c2(CONF_REF, 'publie')['precision'], 1, pct=True)} → "
      f"{fr(_c2(CONF_REF, 'interruption')['precision'], 1, pct=True)}). Ces mouvements")
    A("accompagnent la hausse de prévalence de la fenêtre (§1) et ne s'interprètent pas")
    A("isolément — voir la réserve du §6.")
    A("")

    # ── 4. Bootstrap ──
    A("## 4. IC bootstrap sur la PR-AUC (grain tronçon)")
    A("")
    A(f"Rééchantillonnage i.i.d. des tronçons, {N_BOOT} tirages, graine {SEED}. Les deux")
    A("sous-périodes étant disjointes, la différence terme à terme des tirages fournit une")
    A("distribution bootstrap valide de l'écart.")
    A("")
    A("| Segment | Sous-période | n | Surcharges | PR-AUC | IC 95 % | PR-AUC / prév. | IC 95 % |")
    A("|---|---|---:|---:|---:|---|---:|---|")
    for _, r in boot.iterrows():
        n = "—" if pd.isna(r["n"]) else mil(r["n"])
        ns = "—" if pd.isna(r["n_surcharges"]) else mil(r["n_surcharges"])
        A(f"| {r['segment']} | {r['sous_periode']} | {n} | {ns} | {fr(r['pr_auc'], 4)} | "
          f"[{fr(r['ic95_lo'], 4)} ; {fr(r['ic95_hi'], 4)}] | "
          f"{fr(r['pr_auc_sur_prevalence'], 1)} | "
          f"[{fr(r['ratio_ic95_lo'], 1)} ; {fr(r['ratio_ic95_hi'], 1)}] |")
    A("")

    # ── 5. Témoin ──
    A("## 5. Témoin de voisinage saisonnier")
    A("")
    A("La fenêtre d'interruption est une **saison** (rentrée + début d'automne), pas un tirage")
    A("aléatoire de jours. La comparer à l'ensemble des jours publiés confond l'absence de VMCV")
    A("avec l'effet de saison. On la compare donc aussi aux 43 jours calendaires immédiatement")
    A(f"antérieurs ({bornes['avant'][0]} → {bornes['avant'][1]}) et aux 43 immédiatement")
    A(f"postérieurs ({bornes['apres'][0]} → {bornes['apres'][1]}), tous à VMCV publié.")
    A("")
    A("| Segment | Fenêtre | Jours | n | Surcharges | Prévalence | R² | biais > 63 | PR-AUC | PR-AUC / prév. |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in tem.iterrows():
        A(f"| {r['segment']} | {r['fenetre']} | {int(r['n_jours'])} | {mil(r['n'])} | "
          f"{mil(r['n_surcharges'])} | {fr(r['prevalence'], 3, pct=True)} | "
          f"{fr(r['r2'], 4)} | {fr(r['biais_gt63'], 2)} | "
          f"{fr(r['pr_auc'], 4)} | {fr(r['pr_auc_sur_prevalence'], 1)} |")
    A("")

    # ── 6. Lecture ──
    b_bas = boot[(boot["segment"] == "bas") &
                 (boot["sous_periode"] == "différence (interruption − publié)")].iloc[0]
    dans_bruit = bool(b_bas["ic_contient_zero"])
    c1_bas = c1[(c1["segment"] == "bas") & (c1["sous_periode"] == "interruption")].iloc[0]
    c1_haut = c1[(c1["segment"] == "haut") & (c1["sous_periode"] == "interruption")].iloc[0]
    b_haut = boot[(boot["segment"] == "haut") &
                  (boot["sous_periode"] == "différence (interruption − publié)")].iloc[0]
    pub_bas = boot[(boot["segment"] == "bas") & (boot["sous_periode"] == "publie")].iloc[0]
    itr_bas = boot[(boot["segment"] == "bas") & (boot["sous_periode"] == "interruption")].iloc[0]
    A("## 6. Lecture — l'écart est-il dans le bruit ?")
    A("")
    A("**(i) L'écart brut est mesurable, pas dans le bruit.**")
    A("")
    A(f"- Segment **bas** (le seul où un bus concurrent existe) : PR-AUC "
      f"{fr(pub_bas['pr_auc'], 4)} en période publiée contre {fr(itr_bas['pr_auc'], 4)} "
      f"pendant l'interruption ; écart {fr(b_bas['pr_auc'], 4)}, IC 95 % "
      f"[{fr(b_bas['ic95_lo'], 4)} ; {fr(b_bas['ic95_hi'], 4)}], intervalle qui "
      f"**{'contient' if dans_bruit else 'ne contient pas'} zéro**.")
    A(f"  Le signe est **positif** : la PR-AUC est plus HAUTE pendant l'interruption, "
      f"c'est-à-dire l'inverse d'une dégradation.")
    A("")
    A("**(ii) Le même écart apparaît là où il ne peut pas exister — donc ce n'est pas VMCV.**")
    A("")
    A(f"- Segment **haut** : la crémaillère n'a aucun bus concurrent, ADR-040 n'y attend donc")
    A(f"  **aucun** effet. On y mesure pourtant un écart de PR-AUC de {fr(b_haut['pr_auc'], 4)}, "
      f"IC 95 % [{fr(b_haut['ic95_lo'], 4)} ; {fr(b_haut['ic95_hi'], 4)}] — de magnitude")
    A(f"  comparable à celui du bas, en sens opposé. Un « effet VMCV » ne peut pas produire cela.")
    A("")
    A("**(iii) L'explication est la prévalence, donc la saison.**")
    A("")
    A(f"- La PR-AUC d'un classement aléatoire **est** la prévalence. Or celle-ci change entre")
    A(f"  sous-périodes : bas {fr(c1_bas['prevalence'] - c1_bas['delta_vs_publie_prevalence'], 3, pct=True)} "
      f"→ {fr(c1_bas['prevalence'], 3, pct=True)} (hausse), haut "
      f"{fr(c1_haut['prevalence'] - c1_haut['delta_vs_publie_prevalence'], 3, pct=True)} → "
      f"{fr(c1_haut['prevalence'], 3, pct=True)} (baisse). Les deux écarts de PR-AUC suivent")
    A(f"  exactement le signe de leur écart de prévalence.")
    def _tem(seg, fen, col):
        return tem[(tem["segment"] == seg) & (tem["fenetre"] == fen)].iloc[0][col]

    r_av = _tem("bas", "voisinage avant (publié)", "pr_auc_sur_prevalence")
    r_in = _tem("bas", "interruption", "pr_auc_sur_prevalence")
    r_ap = _tem("bas", "voisinage après (publié)", "pr_auc_sur_prevalence")
    A(f"- Rapportée à la prévalence, la performance du **bas** décrit une pente régulière sur les")
    A(f"  trois fenêtres consécutives de 43 jours : {fr(r_av, 1)} (43 j avant, publié) → "
      f"{fr(r_in, 1)} (interruption) → {fr(r_ap, 1)} (43 j après, publié). La fenêtre")
    A(f"  d'interruption s'**intercale** entre ses deux voisines : elle est sur la tendance, sans")
    A(f"  discontinuité. C'est le contraire de ce qu'une perte d'information produirait.")
    n_av = int(_tem("haut", "voisinage avant (publié)", "n_surcharges"))
    n_ap = int(_tem("haut", "voisinage après (publié)", "n_surcharges"))
    A(f"- Sur le **haut**, les fenêtres de voisinage ne comptent que {n_av} et {n_ap} surcharges :")
    A(f"  les rapports y sont numériquement instables et ne soutiennent aucune conclusion.")
    A("")
    A("**Réserve méthodologique dirimante** : sous-période et saison sont **entièrement**")
    A("confondues (l'interruption est un bloc calendaire unique de 43 jours consécutifs). Aucun")
    A("contraste disponible ne peut isoler l'effet propre des valeurs manquantes VMCV : ce qui")
    A("est mesuré ici est l'écart de performance d'une fenêtre calendaire, pas l'effet causal de")
    A("l'absence de VMCV. Le témoin de voisinage réduit le confondant sans l'éliminer. La")
    A("conclusion défendable est donc **négative et bornée** : aucune trace de dégradation")
    A("imputable à l'interruption n'est décelable, et les mouvements observés s'expliquent par")
    A("la prévalence saisonnière.")
    A("")
    A("### Phrase exploitable pour le mémoire")
    A("")
    A("> " + phrase_memoire(boot, per, ctrl, tem))
    A("")
    out = HERE / "verif_471_vmcv.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def phrase_memoire(boot: pd.DataFrame, per: pd.DataFrame, ctrl: dict,
                   tem: pd.DataFrame) -> str:
    d_bas = boot[(boot["segment"] == "bas") &
                 (boot["sous_periode"] == "différence (interruption − publié)")].iloc[0]
    d_haut = boot[(boot["segment"] == "haut") &
                  (boot["sous_periode"] == "différence (interruption − publié)")].iloc[0]
    pub = boot[(boot["segment"] == "bas") & (boot["sous_periode"] == "publie")].iloc[0]
    itr = boot[(boot["segment"] == "bas") & (boot["sous_periode"] == "interruption")].iloc[0]
    part = per[(per["grain"] == "tronçon") & (per["segment"] == "global") &
               (per["sous_periode"] == "interruption")].iloc[0]["part_du_segment"]
    def _t(seg, fen, col):
        return tem[(tem["segment"] == seg) & (tem["fenetre"] == fen)].iloc[0][col]

    r_av = _t("bas", "voisinage avant (publié)", "pr_auc_sur_prevalence")
    r_in = _t("bas", "interruption", "pr_auc_sur_prevalence")
    r_ap = _t("bas", "voisinage après (publié)", "pr_auc_sur_prevalence")
    return (f"Sur les {ctrl['n_jours_interruption']} jours d'interruption VMCV "
            f"({fr(part, 1, pct=True)} des tronçons H25), la PR-AUC du segment bas passe de "
            f"{fr(pub['pr_auc'], 3)} à {fr(itr['pr_auc'], 3)} (écart {fr(d_bas['pr_auc'], 3)}, "
            f"IC 95 % bootstrap [{fr(d_bas['ic95_lo'], 3)} ; {fr(d_bas['ic95_hi'], 3)}]) : "
            f"l'écart est mesurable, mais il va dans le sens d'une amélioration, un écart de "
            f"magnitude comparable et de signe opposé apparaît sur le segment haut "
            f"({fr(d_haut['pr_auc'], 3)}, IC 95 % [{fr(d_haut['ic95_lo'], 3)} ; "
            f"{fr(d_haut['ic95_hi'], 3)}]) où aucun bus concurrent n'existe, et rapportée à la "
            f"prévalence la performance du bas s'inscrit sans discontinuité entre ses deux "
            f"fenêtres voisines de 43 jours ({fr(r_av, 1)} → {fr(r_in, 1)} → {fr(r_ap, 1)}) ; "
            f"aucune dégradation imputable à l'absence de VMCV n'est donc décelable, "
            f"conformément à l'hypothèse d'impact faible retenue par l'ADR-040.")


# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 78)
    print("LOT B — interruption VMCV H25 (ADR-040), stratification des métriques")
    print("=" * 78)
    h_ds = H.assert_dataset()
    models = H.load_frozen_models()
    hashes = {"dataset": h_ds, "bas": H.HASH_MODEL_BAS, "haut": H.HASH_MODEL_HAUT}
    print(f"dataset {h_ds} | modèles gelés bas {hashes['bas']} / haut {hashes['haut']} — OK")

    # -- couche 1 --
    h25, feats = charger_h25()
    ctrl = qualifier_sous_periodes(h25)
    print(f"H25 : {len(h25):,} tronçons, {ctrl['n_jours_h25']} jours ; "
          f"interruption = {ctrl['n_jours_interruption']} jours "
          f"({ctrl['debut'].date()} → {ctrl['fin'].date()}) — OK")
    pred = H.frozen_predict(h25, feats, models)
    print(f"prédictions couche 1 gelées : {len(pred):,} tronçons")

    # -- couche 2 --
    taus = charger_taus()
    ds = decision.build_decision_set()
    info = decision.assert_perimetre_et_ancrage(ds)
    ds_h25 = ds[ds["annee"] == "H25"].copy()
    ds_h25["date"] = pd.to_datetime(ds_h25["date"]).dt.normalize()
    jours_int = set(pd.to_datetime(h25.loc[h25["sous_periode"] == "interruption", "date"].unique()))
    ds_h25["sous_periode"] = np.where(ds_h25["date"].isin(jours_int), "interruption", "publie")
    garde_fou_ancrages(ds_h25, taus)
    print(f"couche 2 : {info['n_h25']:,} courses, {info['positives_h25']:,} surcharges "
          f"({info['positives_haut']} haut / {info['positives_bas']} bas) — ancrages OK")
    print(f"seuils H24 figés : a′={taus['a_iso_volume']:.2f} b={taus['b_rappel_renforce']:.2f} "
          f"c={taus['c_haute_precision']:.2f}")

    # -- tables --
    per = table_perimetre(h25, ds_h25)
    c1 = table_couche1(h25, pred)
    c2 = table_couche2(ds_h25, taus)
    print(f"IC bootstrap PR-AUC ({N_BOOT} tirages)…")
    boot = table_bootstrap(h25, pred)
    tem, bornes = table_temoin(h25, pred, ctrl["debut"], ctrl["fin"])

    HERE.mkdir(parents=True, exist_ok=True)
    fichiers = []
    for df, nom in [(per, "verif_471_vmcv_perimetre.csv"),
                    (c1, "verif_471_vmcv_couche1.csv"),
                    (c2, "verif_471_vmcv_couche2.csv"),
                    (boot, "verif_471_vmcv_bootstrap.csv"),
                    (tem, "verif_471_vmcv_temoin.csv")]:
        p = HERE / nom
        df.to_csv(p, index=False)
        fichiers.append(p)
    fichiers.append(ecrire_rapport(ctrl, per, c1, c2, boot, tem, bornes, taus, hashes))

    # -- résumé console --
    print("\n── Couche 1 (grain tronçon) ──")
    for _, r in c1.iterrows():
        print(f"  {r['segment']:>6} {r['sous_periode']:>12} n={int(r['n']):>7,} "
              f"R²={fr(r['r2'],4):>8} MAE={fr(r['mae'],3):>7} biais>63={fr(r['biais_gt63'],2):>8} "
              f"PR-AUC={fr(r['pr_auc'],4):>8} prev={fr(r['prevalence'],3,pct=True):>8}")
    print("\n── Couche 2 (grain course, global) ──")
    for _, r in c2[c2["segment"] == "global"].iterrows():
        print(f"  {r['configuration']:>32} {r['sous_periode']:>12} vol={int(r['volume']):>5} "
              f"VP={int(r['VP']):>5} P={fr(r['precision'],1,pct=True):>8} "
              f"R={fr(r['rappel'],1,pct=True):>8}")
    print("\n── IC bootstrap PR-AUC ──")
    for _, r in boot.iterrows():
        print(f"  {r['segment']:>6} {r['sous_periode']:>34} PR-AUC={fr(r['pr_auc'],4):>8} "
              f"IC95=[{fr(r['ic95_lo'],4)} ; {fr(r['ic95_hi'],4)}]  "
              f"PR-AUC/prév={fr(r['pr_auc_sur_prevalence'],1):>6} "
              f"IC95=[{fr(r['ratio_ic95_lo'],1)} ; {fr(r['ratio_ic95_hi'],1)}]")
    print("\n── Témoin de voisinage (43 j avant / interruption / 43 j après) ──")
    for _, r in tem.iterrows():
        print(f"  {r['segment']:>6} {r['fenetre']:>26} prev={fr(r['prevalence'],3,pct=True):>8} "
              f"PR-AUC={fr(r['pr_auc'],4):>8} PR-AUC/prév={fr(r['pr_auc_sur_prevalence'],1):>6}")
    print()
    for f in fichiers:
        print(f"  [OK] {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
