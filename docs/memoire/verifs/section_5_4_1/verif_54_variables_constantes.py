#!/usr/bin/env python3
"""
verif_54_variables_constantes.py — VÉRIF 1 (§5.4).

Question : parmi les 158 variables effectivement mobilisées par le modèle retenu,
combien sont CONSTANTES au grain (tronçon orienté, date), c'est-à-dire ne varient
pas d'une course à l'autre à l'intérieur d'une même journée sur un même tronçon ?

Grain de comparaison : (course, date), qui répond à la question symétrique — combien
de variables ne varient pas d'un tronçon à l'autre à l'intérieur d'une même course ?

Discipline : LECTURE SEULE. Aucune modification du dataset, des modèles ni de la
recette. La liste des 158 variables est LUE depuis la configuration gelée
(`outputs/couche2/features_158f_sans_simba.json`), jamais reconstruite à la main.
Les valeurs manquantes sont traitées comme une modalité à part entière.

Sorties :
  - docs/memoire/verifs/section_5_4/variables_constantes_troncon_jour.md
  - docs/memoire/verifs/section_5_4/variables_constantes_troncon_jour.csv
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
FEAT_JSON = ROOT / "outputs/couche2/features_158f_sans_simba.json"
HASH_DATASET = "ba493568"
ANNEES = ["H22", "H23", "H24", "H25"]

# Clé de tronçon ORIENTÉ : couple ordonné (gare de départ, gare d'arrivée), en BPUIC.
# Convention canonique du projet (cf. c10_comparatif_algos.py : « tronçon dep×arr bpuic »).
CLE_TRONCON = ["id_gare_depart_bpuic", "id_gare_arrivee_bpuic"]
CLE_COURSE = ["horaire_numero_train"]
CLE_DATE = "base_date"

# Familles de préfixe demandées par la consigne (l'ordre est celui de la consigne).
FAMILLES = ["spatial_", "ist_", "meteo_", "event_", "histo_", "cal_", "base_",
            "resa_", "id_", "vmcv_", "horaire_"]

SEUIL_QUASI = 0.999   # « une seule valeur distincte dans plus de 99,9 % des groupes »


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def git_commit() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def fr(n) -> str:
    """Séparateur de milliers par espace insécable fine (convention typographique du mémoire)."""
    return f"{int(n):,}".replace(",", " ")


def famille_de(col: str) -> str:
    for f in FAMILLES:
        if col.startswith(f):
            return f
    return "(autre)"


def distinct_par_groupe(g: np.ndarray, ng: int, valeurs) -> np.ndarray:
    """Nombre de valeurs DISTINCTES de `valeurs` dans chaque groupe de `g`.

    Les manquants forment une modalité à part (`use_na_sentinel=False`). Le calcul
    encode le couple (groupe, modalité) sur un entier unique, puis dénombre les
    couples distincts par groupe : strictement équivalent à
    `groupby(g)[col].nunique(dropna=False)`, mais sans boucle Python.
    """
    codes, uniques = pd.factorize(valeurs, use_na_sentinel=False)
    nv = max(len(uniques), 1)
    cle = g.astype(np.int64) * np.int64(nv) + codes.astype(np.int64)
    gid = np.unique(cle) // np.int64(nv)
    return np.bincount(gid, minlength=ng)


def analyse_grain(df: pd.DataFrame, cles: list, feats: list, etiquette: str) -> dict:
    """Classement des 158 variables selon leur constance dans les groupes définis par `cles`."""
    g, uniq = pd.factorize(pd.MultiIndex.from_frame(df[cles]))
    ng = len(uniq)
    taille = np.bincount(g, minlength=ng)
    multi = taille >= 2                      # groupes réellement informatifs (>= 2 lignes)
    n_multi = int(multi.sum())

    lignes = {}
    for c in feats:
        nd = distinct_par_groupe(g, ng, df[c].values)
        n_1val = int((nd == 1).sum())
        n_1val_multi = int((nd[multi] == 1).sum())
        part = n_1val / ng
        part_multi = (n_1val_multi / n_multi) if n_multi else float("nan")
        if part >= 1.0:
            cat = "strictement constante"
        elif part > SEUIL_QUASI:
            cat = "quasi constante"
        else:
            cat = "variable"
        lignes[c] = {
            f"{etiquette}_n_groupes": ng,
            f"{etiquette}_n_groupes_multi": n_multi,
            f"{etiquette}_groupes_1_valeur": n_1val,
            f"{etiquette}_part_groupes_1_valeur": part,
            f"{etiquette}_groupes_multi_1_valeur": n_1val_multi,
            f"{etiquette}_part_groupes_multi_1_valeur": part_multi,
            f"{etiquette}_max_valeurs_distinctes": int(nd.max()),
            f"{etiquette}_moy_valeurs_distinctes": float(nd.mean()),
            f"{etiquette}_categorie": cat,
        }
    return {"n_groupes": ng, "n_groupes_multi": n_multi,
            "taille_moyenne": float(taille.mean()), "taille_max": int(taille.max()),
            "n_groupes_singleton": int((taille == 1).sum()), "lignes": lignes}


def main() -> int:
    h = sha8(ML_DATASET)
    if h != HASH_DATASET:
        raise RuntimeError(f"STOP empreinte dataset {h} != {HASH_DATASET} attendu.")

    feats = json.loads(FEAT_JSON.read_text())["features"]
    assert len(feats) == 158, f"attendu 158 variables, obtenu {len(feats)}"

    besoins = sorted(set(feats) | set(CLE_TRONCON) | set(CLE_COURSE) |
                     {CLE_DATE, "horaire_annee_horaire"})
    df = pd.read_parquet(ML_DATASET, columns=besoins)
    n_total = len(df)
    df = df[df["horaire_annee_horaire"].isin(ANNEES)].copy()
    df["_date"] = pd.to_datetime(df[CLE_DATE]).dt.normalize()

    tj = analyse_grain(df, CLE_TRONCON + ["_date"], feats, "tj")
    cd = analyse_grain(df, CLE_COURSE + ["_date"], feats, "cd")

    tab = pd.DataFrame([
        {"variable": c, "famille": famille_de(c), "dtype": str(df[c].dtype),
         "n_modalites_perimetre": int(pd.factorize(df[c].values, use_na_sentinel=False)[1].size),
         "part_manquants": float(df[c].isna().mean()),
         **tj["lignes"][c], **cd["lignes"][c]}
        for c in feats
    ])
    csv_path = OUT_DIR / "variables_constantes_troncon_jour.csv"
    tab.to_csv(csv_path, index=False, float_format="%.17g")

    # ── Comptes ────────────────────────────────────────────────────────────────
    ordre = ["strictement constante", "quasi constante", "variable"]
    cnt_tj = tab["tj_categorie"].value_counts().reindex(ordre, fill_value=0)
    cnt_cd = tab["cd_categorie"].value_counts().reindex(ordre, fill_value=0)
    fam_tj = (tab.groupby("famille")["tj_categorie"].value_counts().unstack(fill_value=0)
              .reindex(columns=ordre, fill_value=0))
    fam_cd = (tab.groupby("famille")["cd_categorie"].value_counts().unstack(fill_value=0)
              .reindex(columns=ordre, fill_value=0))

    def bloc_familles(fam: pd.DataFrame) -> str:
        ordre_fam = [f for f in FAMILLES if f in fam.index] + \
                    [f for f in fam.index if f not in FAMILLES]
        out = ["| Famille | Présentes | Strictement constante | Quasi constante | Variable |",
               "|---|---:|---:|---:|---:|"]
        for f in ordre_fam:
            r = fam.loc[f]
            out.append(f"| `{f}` | {int(r.sum())} | {r[ordre[0]]} | {r[ordre[1]]} | {r[ordre[2]]} |")
        for f in FAMILLES:
            if f not in fam.index:
                out.append(f"| `{f}` | 0 | 0 | 0 | 0 |")
        out.append(f"| **Total** | **{int(fam.values.sum())}** | "
                   f"**{int(fam[ordre[0]].sum())}** | **{int(fam[ordre[1]].sum())}** | "
                   f"**{int(fam[ordre[2]].sum())}** |")
        return "\n".join(out)

    def liste(cat: str, col: str) -> str:
        v = sorted(tab.loc[tab[col] == cat, "variable"])
        return "\n".join(f"- `{x}`" for x in v) if v else "_(aucune)_"

    n_const_tj = int(cnt_tj[ordre[0]] + cnt_tj[ordre[1]])
    n_const_cd = int(cnt_cd[ordre[0]] + cnt_cd[ordre[1]])

    # part de groupes >= 2 lignes, lecture de robustesse
    tab_multi = tab.assign(
        tj_cat_multi=np.where(tab["tj_part_groupes_multi_1_valeur"] >= 1.0, ordre[0],
                     np.where(tab["tj_part_groupes_multi_1_valeur"] > SEUIL_QUASI, ordre[1], ordre[2])))
    cnt_tj_multi = tab_multi["tj_cat_multi"].value_counts().reindex(ordre, fill_value=0)

    md = f"""# Variables constantes au grain tronçon-journée

VÉRIF 1 de la section 5.4. Rapport produit en lecture seule par
`docs/memoire/verifs/section_5_4/verif_54_variables_constantes.py`. Aucune modification
du dataset, des modèles ni de la recette de modélisation.

## 1. Empreintes et périmètre

| Rôle | Chemin | Empreinte SHA256[:8] |
|---|---|---|
| Table canonique | `data/processed/ml_dataset.parquet` | `{h}` |
| Recette gelée (liste des variables) | `outputs/couche2/features_158f_sans_simba.json` | `{sha8(FEAT_JSON)}` |

Branche `restructuration-publication`, commit `{git_commit()}`.

La liste des 158 variables est lue depuis la configuration gelée, jamais reconstruite.
Le contrôle `len(feats) == 158` est posé en dur avant tout calcul.

Périmètre : années horaires {", ".join(ANNEES)}, soit **{fr(len(df))}** observations au grain
tronçon sur les {fr(n_total)} de la table. Les valeurs manquantes sont traitées comme une
**modalité à part entière** : deux courses dont l'une porte une valeur et l'autre un
manquant comptent pour deux valeurs distinctes.

Le tronçon **orienté** est le couple ordonné (`id_gare_depart_bpuic`,
`id_gare_arrivee_bpuic`) : Vevey→Blonay et Blonay→Vevey sont deux tronçons distincts.
C'est la convention canonique du projet (« tronçon dep×arr bpuic », `c10_comparatif_algos.py`).

## 2. Volumétrie des groupes

| Grain | Nombre de groupes | Taille moyenne | Taille maximale | Groupes à une seule ligne |
|---|---:|---:|---:|---:|
| (tronçon orienté, date) | **{fr(tj['n_groupes'])}** | {tj['taille_moyenne']:.2f} | {fr(tj['taille_max'])} | {fr(tj['n_groupes_singleton'])} |
| (course, date) | **{fr(cd['n_groupes'])}** | {cd['taille_moyenne']:.2f} | {fr(cd['taille_max'])} | {fr(cd['n_groupes_singleton'])} |

Le calcul de constance au grain tronçon-journée porte donc sur **{fr(tj['n_groupes'])} groupes
(tronçon orienté, date)**, dont **{fr(tj['n_groupes_multi'])}** contiennent au moins deux
courses et sont seuls réellement informatifs (un groupe d'une seule ligne est constant
par construction, quelle que soit la variable).

## 3. Résultat principal — grain (tronçon orienté, date)

Une variable est dite *strictement constante* si elle ne prend qu'une seule valeur
distincte dans **100 %** des groupes, *quasi constante* si c'est le cas dans plus de
**99,9 %** des groupes sans l'être dans tous, *variable* sinon.

| Catégorie | Nombre de variables sur 158 |
|---|---:|
| Strictement constante | **{cnt_tj[ordre[0]]}** |
| Quasi constante | **{cnt_tj[ordre[1]]}** |
| Variable | **{cnt_tj[ordre[2]]}** |
| **Total** | **158** |

**{n_const_tj} variables sur 158** sont donc constantes ou quasi constantes au grain
tronçon-journée : elles ne distinguent pas une course d'une autre à l'intérieur d'une
même journée sur un même tronçon. Les **{cnt_tj[ordre[2]]}** restantes portent seules
l'information proprement infra-journalière.

### 3.1 Ventilation par famille de préfixe

{bloc_familles(fam_tj)}

Les familles `id_` et `horaire_` sont vides : aucune des 158 variables retenues n'en
relève. Les identifiants (`id_gare_*_bpuic`) et les descripteurs d'horaire
(`horaire_numero_train`, `horaire_annee_horaire`, `horaire_service_id_complet`) sont
présents dans la table mais **hors recette** — ils servent de clés, pas de prédicteurs.

### 3.2 Lecture de robustesse : groupes d'au moins deux courses

Restreint aux {fr(tj['n_groupes_multi'])} groupes contenant au moins deux courses, le
classement devient :

| Catégorie | Nombre de variables sur 158 |
|---|---:|
| Strictement constante | **{cnt_tj_multi[ordre[0]]}** |
| Quasi constante | **{cnt_tj_multi[ordre[1]]}** |
| Variable | **{cnt_tj_multi[ordre[2]]}** |

Cette lecture est la plus exigeante : elle écarte les groupes où la constance est un
artefact d'effectif. Les deux lectures sont fournies dans le CSV.

## 4. Grain de comparaison — (course, date)

Même calcul, groupes définis par (`horaire_numero_train`, date) : combien de variables
ne varient pas d'un **tronçon à l'autre** à l'intérieur d'une même course ?

| Catégorie | Nombre de variables sur 158 |
|---|---:|
| Strictement constante | **{cnt_cd[ordre[0]]}** |
| Quasi constante | **{cnt_cd[ordre[1]]}** |
| Variable | **{cnt_cd[ordre[2]]}** |
| **Total** | **158** |

Soit **{n_const_cd} variables sur 158** constantes à l'échelle d'une course entière.

### 4.1 Ventilation par famille de préfixe

{bloc_familles(fam_cd)}

## 5. Listes nominatives

### 5.1 Strictement constantes au grain (tronçon, date)

{liste(ordre[0], 'tj_categorie')}

### 5.2 Quasi constantes au grain (tronçon, date)

{liste(ordre[1], 'tj_categorie')}

### 5.3 Strictement constantes au grain (course, date)

{liste(ordre[0], 'cd_categorie')}

### 5.4 Quasi constantes au grain (course, date)

{liste(ordre[1], 'cd_categorie')}

## 6. Livrables

| Fichier | Contenu |
|---|---|
| `variables_constantes_troncon_jour.csv` | Tableau détaillé, 158 lignes, aucun arrondi (`%.17g`) |
| `variables_constantes_troncon_jour.md` | Le présent rapport |
| `verif_54_variables_constantes.py` | Script, réexécutable en une commande |
"""
    (OUT_DIR / "variables_constantes_troncon_jour.md").write_text(md)

    print(f"[dataset] {h} | {fr(len(df))} obs sur {ANNEES}")
    print(f"[groupes] (tronçon,date) = {fr(tj['n_groupes'])} dont {fr(tj['n_groupes_multi'])} multi-courses")
    print(f"[groupes] (course,date)  = {fr(cd['n_groupes'])} dont {cd['n_groupes_multi']:,} multi-tronçons")
    print(f"\n[GRAIN TRONÇON-JOUR] {dict(cnt_tj)}  -> constantes+quasi = {n_const_tj}/158")
    print(f"[  robustesse >=2  ] {dict(cnt_tj_multi)}")
    print(f"[GRAIN COURSE-JOUR ] {dict(cnt_cd)}  -> constantes+quasi = {n_const_cd}/158")
    print("\n[familles, grain tronçon-jour]")
    print(fam_tj.to_string())
    print(f"\n[OK] {csv_path.name} + variables_constantes_troncon_jour.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
