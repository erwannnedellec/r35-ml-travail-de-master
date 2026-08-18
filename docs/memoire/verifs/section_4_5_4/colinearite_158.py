#!/usr/bin/env python3
"""
Section 4.5.4 — dépistage de colinéarité sur le périmètre retenu (158 variables).

LECTURE SEULE. Aucun réentraînement, aucun modèle chargé, aucun ADR touché.
N'écrit que sous docs/memoire/verifs/section_4_5_4/.

Objet
-----
Sur les 158 variables du modèle gelé, restreint aux années horaires H22, H23 et H24
(H25 exclu), produire :
  1. les doublons stricts — paires à |r| >= 0.999, accord binaire parfait, ou égalité
     exacte de colonnes (y compris catégorielles) — avec familles et rangs SHAP par
     segment LUS depuis les artefacts existants (aucun recalcul SHAP) ;
  2. le nombre de paires à |r| >= 0.95 et |r| >= 0.90, et la liste des paires
     inter-familles (les deux membres dans des familles DIFFÉRENTES) ;
  3. le nombre de variables impliquées dans au moins une paire à |r| >= 0.95.

Périmètre
---------
Périmètre principal = Split C train (ADR-065) : H22 hors tronçons Gilamont
(BPUIC 8501260) + H23 + H24 — c'est exactement le périmètre d'apprentissage du
modèle gelé, et il satisfait la restriction H22-H24. Un contrôle de robustesse
recompute les décomptes sur H22-H24 SANS l'exclusion Gilamont, pour montrer que
cette exclusion ne change pas les conclusions.

Méthode
-------
Pearson en « pairwise complete » (55 des 152 colonnes numériques portent des NaN,
jusqu'à 81 % pour ist_corresp_*_pct_garanties_*) : chaque paire est calculée sur
les lignes où les DEUX variables sont observées. Implémentation en une passe par
blocs de lignes via quatre accumulateurs matriciels (N, Sx, Sxx, Sxy) sur données
centrées par la moyenne globale de colonne (invariance par translation de r,
conditionnement amélioré). Garde-fou : toute paire retenue (|r| >= 0.90) est
RECALCULÉE directement, deux colonnes à la fois, et c'est cette valeur directe qui
fait foi ; l'écart max entre les deux voies est reporté.

Les 6 variables catégorielles (string) sont hors matrice de Pearson, par
construction ; elles restent couvertes par le test d'égalité exacte de colonnes.

Accord binaire : pour les 17 variables à valeurs dans {0, 1}, part des lignes où
les deux variables coïncident, sur le support commun observé.

Sorties
-------
  colinearite_158_paires.csv          paires |r| >= 0.90 (table maîtresse)
  colinearite_158_binaires_accord.csv accord ligne à ligne, 17 binaires
  colinearite_158_variables_r095.csv  variables impliquées dans >= 1 paire |r|>=0.95
  colinearite_158_synthese.json       décomptes + empreintes + garde-fous
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

HASH = "ba493568"                     # sha256[:8] de ml_dataset.parquet (gel v2, ADR-076)
GILAMONT_BPUIC = 8501260              # tronçons exclus de H22 (Split C, ADR-065)
N_TRAIN_SPLIT_C = 801_282             # ancrage de volumétrie (STOP si écart)
ANNEES = ("H22", "H23", "H24")

ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
FEAT_JSON = ROOT / "outputs" / "couche2" / "features_158f_sans_simba.json"
CODEBOOK = ROOT / "outputs" / f"codebook_canonique_{HASH}.csv"
SHAP_BAS = ROOT / "outputs" / "confirmation" / "c08_shap_ranks_bas.csv"
SHAP_HAUT = ROOT / "outputs" / "confirmation" / "c08_shap_ranks_haut.csv"

SEUIL_DOUBLON = 0.999
SEUIL_HAUT = 0.95
SEUIL_BAS = 0.90
CHUNK = 100_000                       # lignes par bloc dans la passe matricielle

# Libellés français des familles — tableau des familles de §4.4.4
# (miroir strict de scripts/build_codebook_canonique.py:_FAMILLE_BASE).
LIBELLE_FAMILLE = {
    "base_": "Desserte", "cal_": "Calendrier", "event_": "Événement",
    "histo_": "Historique de charge", "horaire_": "Horaire",
    "id_": "Identifiant", "ist_": "Régularité et correspondances",
    "meteo_": "Météo", "resa_": "Réservation de groupe",
    "simba_": "Structure tarifaire", "spatial_": "Contexte spatial",
    "target_": "Cible", "vmcv_": "Concurrence modale",
}


# ── Préambule : empreinte ───────────────────────────────────────────────────────
def assert_empreinte() -> str:
    """Garde-fou dur : le dataset lu est bien le canonique gelé ba493568."""
    from couche2 import blocs
    h = blocs.assert_canonical_dataset(ML_DATASET, HASH)
    print(f"[preambule] ml_dataset.parquet sha256[:8] = {h}  (attendu {HASH}) — OK")
    return h


def sha8(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


# ── Chargement ──────────────────────────────────────────────────────────────────
def load_features() -> list:
    feats = json.loads(FEAT_JSON.read_text())["features"]
    assert len(feats) == len(set(feats)) == 158, f"attendu 158 features, obtenu {len(feats)}"
    return feats


def load_perimetre(feats: list):
    """Renvoie (split_c, h22_h24_brut) restreints aux 158 colonnes."""
    aux = ["horaire_annee_horaire", "id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]
    cols = feats + [c for c in aux if c not in feats]
    df = pd.read_parquet(ML_DATASET, columns=cols)
    brut = df[df["horaire_annee_horaire"].isin(ANNEES)]
    h22 = brut[brut["horaire_annee_horaire"] == "H22"]
    gil = ((h22["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
           (h22["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC))
    split_c = pd.concat(
        [h22[~gil], brut[brut["horaire_annee_horaire"].isin(["H23", "H24"])]],
        ignore_index=True)
    if len(split_c) != N_TRAIN_SPLIT_C:
        raise RuntimeError(
            f"STOP Split C : n={len(split_c)} != {N_TRAIN_SPLIT_C} attendu.")
    print(f"[perimetre] Split C train = {len(split_c):,} lignes ; "
          f"H22-H24 brut = {len(brut):,} lignes".replace(",", " "))
    return split_c[feats], brut[feats]


def classer_colonnes(d: pd.DataFrame, feats: list):
    """(numeriques, categorielles, binaires) sur le périmètre courant."""
    num, cat, bina = [], [], []
    for c in feats:
        s = d[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            num.append(c)
            u = pd.unique(s.dropna())
            vals = set(np.unique(np.asarray(u, dtype="float64"))) if len(u) else set()
            if vals == {0.0, 1.0}:
                bina.append(c)
        else:
            cat.append(c)
    return num, cat, bina


# ── Pearson pairwise-complete, une passe par blocs ──────────────────────────────
def pearson_pairwise(d: pd.DataFrame, num: list) -> np.ndarray:
    """Matrice p×p des r de Pearson, chaque paire sur son support commun observé.

    Accumulateurs sur données centrées par la moyenne globale de colonne :
      N[i,j]   = # lignes où i et j sont tous deux observés
      Sx[i,j]  = somme de x_i sur ce support        (Sy = Sx.T)
      Sxx[i,j] = somme de x_i^2 sur ce support      (Syy = Sxx.T)
      Sxy[i,j] = somme de x_i * x_j sur ce support
    """
    p = len(num)
    mu = np.empty(p)
    for k, c in enumerate(num):
        mu[k] = float(pd.to_numeric(d[c], errors="coerce").mean())

    N = np.zeros((p, p)); Sx = np.zeros((p, p))
    Sxx = np.zeros((p, p)); Sxy = np.zeros((p, p))
    n = len(d)
    for start in range(0, n, CHUNK):
        blk = d.iloc[start:start + CHUNK]
        X = np.empty((len(blk), p), dtype="float64")
        for k, c in enumerate(num):
            X[:, k] = pd.to_numeric(blk[c], errors="coerce").to_numpy(dtype="float64")
        M = np.isfinite(X).astype("float64")
        Z = np.where(np.isfinite(X), X - mu, 0.0)
        N += M.T @ M
        Sx += Z.T @ M
        Sxx += (Z * Z).T @ M
        Sxy += Z.T @ Z
        print(f"  bloc {start:>9,}-{min(start + CHUNK, n):>9,}".replace(",", " "), flush=True)

    Sy, Syy = Sx.T, Sxx.T
    num_ = N * Sxy - Sx * Sy
    varx = N * Sxx - Sx * Sx
    vary = N * Syy - Sy * Sy
    den = np.sqrt(np.clip(varx, 0, None) * np.clip(vary, 0, None))
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.where(den > 0, num_ / den, np.nan)
    return R, N


def r_direct(d: pd.DataFrame, a: str, b: str):
    """r de Pearson recalculé directement sur les deux colonnes (voie de contrôle)."""
    x = pd.to_numeric(d[a], errors="coerce").to_numpy(dtype="float64")
    y = pd.to_numeric(d[b], errors="coerce").to_numpy(dtype="float64")
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return np.nan, int(m.sum())
    xv, yv = x[m], y[m]
    xv = xv - xv.mean(); yv = yv - yv.mean()
    dd = np.sqrt((xv * xv).sum() * (yv * yv).sum())
    return (float((xv * yv).sum() / dd) if dd > 0 else np.nan), int(m.sum())


# ── Accord binaire et égalité exacte ────────────────────────────────────────────
def accord_binaire(d: pd.DataFrame, bina: list) -> pd.DataFrame:
    rows = []
    arr = {c: pd.to_numeric(d[c], errors="coerce").to_numpy(dtype="float64") for c in bina}
    for a, b in combinations(bina, 2):
        x, y = arr[a], arr[b]
        m = np.isfinite(x) & np.isfinite(y)
        n = int(m.sum())
        acc = float((x[m] == y[m]).mean()) if n else np.nan
        rows.append({"var_a": a, "var_b": b, "n_commun": n, "accord": acc})
    return pd.DataFrame(rows).sort_values("accord", ascending=False).reset_index(drop=True)


def doublons_exacts(d: pd.DataFrame, feats: list) -> list:
    """Colonnes strictement identiques (valeurs ET motif de NaN), toutes familles,
    catégorielles comprises. Pré-filtrage par empreinte de colonne."""
    emp = {}
    for c in feats:
        h = hashlib.sha256(
            pd.util.hash_pandas_object(d[c], index=False).to_numpy().tobytes()
        ).hexdigest()
        emp.setdefault(h, []).append(c)
    pairs = []
    for _, group in emp.items():
        if len(group) > 1:
            for a, b in combinations(group, 2):
                if d[a].equals(d[b]):
                    pairs.append((a, b))
    return pairs


# ── Familles et rangs SHAP (lecture d'artefacts, aucun recalcul) ────────────────
def charge_familles(feats: list) -> dict:
    cb = pd.read_csv(CODEBOOK)
    fam = dict(zip(cb["colonne"], cb["famille"]))
    manquants = [f for f in feats if f not in fam]
    assert not manquants, f"variables absentes du codebook : {manquants}"
    return {f: LIBELLE_FAMILLE.get(fam[f], fam[f]) for f in feats}


def charge_rangs_shap() -> dict:
    out = {}
    for seg, path in (("bas", SHAP_BAS), ("haut", SHAP_HAUT)):
        t = pd.read_csv(path)
        assert len(t) == 158, f"{path.name} : {len(t)} lignes, attendu 158"
        out[seg] = dict(zip(t["feature"], t["rang"]))
    return out


# ── Main ────────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=== §4.5.4 — dépistage de colinéarité, 158 variables, H22-H24 ===")
    h = assert_empreinte()
    feats = load_features()
    fam = charge_familles(feats)
    rangs = charge_rangs_shap()

    d, brut = load_perimetre(feats)
    num, cat, bina = classer_colonnes(d, feats)
    print(f"[colonnes] {len(num)} numériques, {len(cat)} catégorielles, "
          f"{len(bina)} binaires {{0,1}}")
    print(f"[colonnes] catégorielles hors Pearson : {cat}")

    print("[pearson] passe matricielle, Split C…")
    R, N = pearson_pairwise(d, num)
    iu = np.triu_indices(len(num), k=1)
    rv, nv = R[iu], N[iu]
    n_indef = int(np.isnan(rv).sum())
    absr = np.abs(rv)

    # Table maîtresse : paires |r| >= 0.90, valeur DIRECTE faisant foi.
    sel = np.where(np.nan_to_num(absr, nan=-1.0) >= SEUIL_BAS)[0]
    print(f"[pearson] {len(sel)} paires candidates |r| >= {SEUIL_BAS} → recalcul direct")
    rows, ecart_max = [], 0.0
    for k in sel:
        i, j = iu[0][k], iu[1][k]
        a, b = num[i], num[j]
        rd, ncom = r_direct(d, a, b)
        ecart_max = max(ecart_max, abs(rd - rv[k]))
        rows.append({
            "var_a": a, "var_b": b,
            "famille_a": fam[a], "famille_b": fam[b],
            "meme_famille": fam[a] == fam[b],
            "r": rd, "abs_r": abs(rd), "n_commun": ncom,
            "binaire_a": a in bina, "binaire_b": b in bina,
            "rang_shap_bas_a": rangs["bas"][a], "rang_shap_bas_b": rangs["bas"][b],
            "rang_shap_haut_a": rangs["haut"][a], "rang_shap_haut_b": rangs["haut"][b],
            "r_passe_matricielle": rv[k],
        })
    paires = pd.DataFrame(rows).sort_values("abs_r", ascending=False).reset_index(drop=True)
    print(f"[controle] écart max passe matricielle vs recalcul direct : {ecart_max:.3e}")
    assert ecart_max < 1e-9, f"divergence des deux voies de calcul : {ecart_max:.3e}"

    n_090 = int((paires["abs_r"] >= SEUIL_BAS).sum())
    n_095 = int((paires["abs_r"] >= SEUIL_HAUT).sum())
    n_0999 = int((paires["abs_r"] >= SEUIL_DOUBLON).sum())

    # Paires INTER-FAMILLES les plus fortes, tous seuils confondus : sert à qualifier
    # le décompte inter-familles (combien la frontière de famille est-elle « loin »
    # des seuils ?), pas seulement à constater qu'il est nul.
    fam_arr = np.array([fam[c] for c in num])
    inter = fam_arr[iu[0]] != fam_arr[iu[1]]
    ordre = np.argsort(-np.nan_to_num(absr, nan=-1.0))
    ordre = [k for k in ordre if inter[k]][:20]
    top_inter = pd.DataFrame([{
        "var_a": num[iu[0][k]], "var_b": num[iu[1][k]],
        "famille_a": fam[num[iu[0][k]]], "famille_b": fam[num[iu[1][k]]],
        "r": r_direct(d, num[iu[0][k]], num[iu[1][k]])[0],
        "n_commun": int(nv[k]),
    } for k in ordre])
    top_inter["abs_r"] = top_inter["r"].abs()
    top_inter = top_inter.sort_values("abs_r", ascending=False).reset_index(drop=True)
    abs_r_max_inter = float(top_inter["abs_r"].iloc[0])
    print(f"[inter-familles] |r| max hors famille : {abs_r_max_inter:.4f} "
          f"({top_inter['var_a'].iloc[0]} / {top_inter['var_b'].iloc[0]})")

    # Variables impliquées dans >= 1 paire |r| >= 0.95.
    p95 = paires[paires["abs_r"] >= SEUIL_HAUT]
    impliquees = sorted(set(p95["var_a"]) | set(p95["var_b"]))
    tbl_impl = pd.DataFrame({
        "variable": impliquees,
        "famille": [fam[v] for v in impliquees],
        "n_paires_r095": [int(((p95["var_a"] == v) | (p95["var_b"] == v)).sum())
                          for v in impliquees],
        "abs_r_max": [float(p95[(p95["var_a"] == v) | (p95["var_b"] == v)]["abs_r"].max())
                      for v in impliquees],
        "rang_shap_bas": [rangs["bas"][v] for v in impliquees],
        "rang_shap_haut": [rangs["haut"][v] for v in impliquees],
    }).sort_values(["n_paires_r095", "abs_r_max"], ascending=False).reset_index(drop=True)

    # Accord binaire ligne à ligne + doublons exacts de colonnes.
    acc = accord_binaire(d, bina)
    acc_parfait = acc[acc["accord"] == 1.0]
    exacts = doublons_exacts(d, feats)
    print(f"[binaire] {len(acc)} paires binaires ; accord parfait : {len(acc_parfait)}")
    print(f"[exact]   doublons stricts de colonnes (toutes familles) : {len(exacts)}")

    # Contrôle de robustesse : mêmes décomptes sans l'exclusion Gilamont.
    print("[robustesse] passe matricielle, H22-H24 brut (Gilamont inclus)…")
    Rb, _ = pearson_pairwise(brut, num)
    ab = np.abs(Rb[iu])
    rob = {
        "n_lignes": int(len(brut)),
        "n_paires_r090": int((np.nan_to_num(ab, nan=-1.0) >= SEUIL_BAS).sum()),
        "n_paires_r095": int((np.nan_to_num(ab, nan=-1.0) >= SEUIL_HAUT).sum()),
        "n_paires_r0999": int((np.nan_to_num(ab, nan=-1.0) >= SEUIL_DOUBLON).sum()),
    }
    set_c = {(num[i], num[j]) for i, j in zip(iu[0][sel], iu[1][sel])}
    sel_b = np.where(np.nan_to_num(ab, nan=-1.0) >= SEUIL_BAS)[0]
    set_b = {(num[i], num[j]) for i, j in zip(iu[0][sel_b], iu[1][sel_b])}
    rob["paires_r090_seulement_split_c"] = sorted("|".join(p) for p in set_c - set_b)
    rob["paires_r090_seulement_h22_h24_brut"] = sorted("|".join(p) for p in set_b - set_c)
    print(f"[robustesse] |r|>=0.90 : {rob['n_paires_r090']} (Split C : {n_090}) ; "
          f"symétrie de la différence = "
          f"{len(rob['paires_r090_seulement_split_c']) + len(rob['paires_r090_seulement_h22_h24_brut'])}")

    # Écritures.
    DOSSIER.mkdir(parents=True, exist_ok=True)
    paires.to_csv(DOSSIER / "colinearite_158_paires.csv", index=False)
    acc.to_csv(DOSSIER / "colinearite_158_binaires_accord.csv", index=False)
    tbl_impl.to_csv(DOSSIER / "colinearite_158_variables_r095.csv", index=False)
    top_inter.to_csv(DOSSIER / "colinearite_158_inter_familles_top.csv", index=False)

    synth = {
        "meta": {
            "objet": "dépistage de colinéarité, 158 variables du modèle gelé",
            "empreinte_ml_dataset_sha8": h,
            "empreinte_attendue": HASH,
            "perimetre_principal": "Split C train — H22 hors Gilamont + H23 + H24 (H25 exclu)",
            "n_lignes_split_c": int(len(d)),
            "n_lignes_h22_h24_brut": int(len(brut)),
            "lecture_seule": True,
            "reentrainement": False,
            "artefacts_lus": {
                "features_158": str(FEAT_JSON.relative_to(ROOT)),
                "codebook": str(CODEBOOK.relative_to(ROOT)),
                "shap_bas": f"{SHAP_BAS.relative_to(ROOT)} (sha8 {sha8(SHAP_BAS)})",
                "shap_haut": f"{SHAP_HAUT.relative_to(ROOT)} (sha8 {sha8(SHAP_HAUT)})",
            },
        },
        "colonnes": {
            "n_total": len(feats), "n_numeriques": len(num),
            "n_categorielles": len(cat), "categorielles": cat,
            "n_binaires": len(bina), "binaires": bina,
        },
        "pearson": {
            "n_paires_evaluees": int(len(rv)),
            "n_paires_indefinies": n_indef,
            "n_min_support_commun": int(np.nanmin(nv)),
            "n_paires_r0999": n_0999,
            "n_paires_r095": n_095,
            "n_paires_r090": n_090,
            "n_paires_r095_inter_familles": int((~p95["meme_famille"]).sum()),
            "n_paires_r090_inter_familles": int((~paires["meme_famille"]).sum()),
            "n_variables_impliquees_r095": len(impliquees),
            "abs_r_max_inter_familles": abs_r_max_inter,
            "paire_inter_familles_la_plus_forte":
                f"{top_inter['var_a'].iloc[0]}|{top_inter['var_b'].iloc[0]}",
            "ecart_max_matriciel_vs_direct": float(ecart_max),
        },
        "binaire": {
            "n_paires": int(len(acc)),
            "n_accord_parfait": int(len(acc_parfait)),
            "accord_max": float(acc["accord"].max()),
            "paires_accord_parfait": ["|".join(r) for r in
                                      acc_parfait[["var_a", "var_b"]].to_numpy()],
        },
        "doublons_exacts_colonnes": ["|".join(p) for p in exacts],
        "robustesse_sans_exclusion_gilamont": rob,
    }
    (DOSSIER / "colinearite_158_synthese.json").write_text(
        json.dumps(synth, indent=2, ensure_ascii=False))

    print(f"\n[resultat] |r|>=0.999 : {n_0999} | >=0.95 : {n_095} | >=0.90 : {n_090}")
    print(f"[resultat] variables impliquées (>=0.95) : {len(impliquees)}")
    print(f"[resultat] paires inter-familles : >=0.95 → {int((~p95['meme_famille']).sum())}"
          f" ; >=0.90 → {int((~paires['meme_famille']).sum())}")
    print(f"[ecrit] {DOSSIER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
