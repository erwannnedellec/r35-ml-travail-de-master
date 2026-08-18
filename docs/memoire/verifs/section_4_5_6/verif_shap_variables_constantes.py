#!/usr/bin/env python3
"""Vérif §4.5.6 — dispersion des valeurs SHAP de variables constantes sur H25.

Question
--------
`event_covid_phase` et `event_is_covid_restrictions` ne prennent qu'une seule
modalité sur H25, périmètre sur lequel `c08_shap_segments.py` calcule les rangs
SHAP. Une variable constante a-t-elle pour autant des valeurs SHAP constantes ?

Sous TreeSHAP (`pred_contribs=True`), l'attribution portée par une variable
dépend du chemin parcouru dans chaque arbre, donc des AUTRES variables. Rien
n'impose a priori que la dispersion soit nulle. Ce script la mesure.

Protocole
---------
Reprise exacte de `scripts/confirmation/c08_shap_segments.py` :
  - mêmes modèles gelés `enrichi_seg_{bas,haut}_ba493568.json`, empreintes
    vérifiées par le harnais ;
  - même périmètre : H25 seul (`horaire_annee_horaire == "H25"`), puis
    segmentation par `spatial_segment` ;
  - même préparation des features (`_harness.prep_X`, ordre canonique des 158) ;
  - même appel `booster.predict(dm, pred_contribs=True)`.
La seule différence est l'agrégation : c08 ne conserve que la moyenne des
valeurs absolues, ce script conserve en outre moyenne signée, écart-type,
minimum, maximum et nombre de valeurs distinctes.

LECTURE SEULE. Aucun réentraînement, aucun artefact de modèle modifié.

Contrôle de conformité bloquant
-------------------------------
Le `mean|SHAP|` recalculé doit reproduire à l'identique celui des fichiers
`outputs/confirmation/c08_shap_ranks_{bas,haut}.csv`, sur les 158 features et
non seulement sur les variables étudiées. Tout écart arrête le script.

Exécution (une commande, déterministe) :

    venv/bin/python docs/memoire/verifs/section_4_5_6/verif_shap_variables_constantes.py
"""
from __future__ import annotations

import os

# Threads numériques fixés à 1 AVANT tout import numérique, comme le fait le
# Makefile et l'en-tête de c08 : sans ce pinning, les réductions flottantes du
# BLAS multi-thread rendent le contrôle de conformité non reproductible.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts" / "confirmation"))
import _harness as H  # noqa: E402

HASH_ATTENDU = "ba493568"
N_FEATURES = 158

CIBLES = ["event_covid_phase", "event_is_covid_restrictions"]

OUT_CSV = DOSSIER / "verif_456_shap_dispersion.csv"
OUT_MD = DOSSIER / "verif_shap_variables_constantes.md"


def sha256_8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def stop(msg: str) -> None:
    print(f"\n*** STOP — {msg}", file=sys.stderr)
    sys.exit(1)


def mil(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def stats_shap(v: np.ndarray) -> dict:
    """Statistiques descriptives d'un vecteur de valeurs SHAP signées."""
    return {
        "mean_abs_shap": float(np.abs(v).mean()),
        "moyenne_signee": float(v.mean()),
        "ecart_type": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        "min": float(v.min()),
        "max": float(v.max()),
        "n_valeurs_distinctes": int(len(np.unique(v))),
    }


def main() -> None:
    lignes: list[str] = []

    def emit(s: str = "") -> None:
        lignes.append(s)

    def tick(b: bool) -> str:
        return "OK" if b else "ÉCART"

    # --- Préambule --------------------------------------------------------- #
    h_canon = sha256_8(H.ML_DATASET)
    if h_canon != HASH_ATTENDU:
        stop(f"empreinte du dataset non conforme : lue {h_canon!r}, "
             f"attendue {HASH_ATTENDU!r}. Aucune sortie n'est produite.")
    H.assert_dataset()  # garde du harnais, identique à celle de c08

    feats = H.load_features_158()
    if len(feats) != N_FEATURES:
        stop(f"{len(feats)} features chargées, attendu {N_FEATURES}")

    df = H.load_dataset()
    h25 = df[df["horaire_annee_horaire"] == "H25"]   # c08_shap_segments.py:35

    # --- Boucle segments, protocole c08 ------------------------------------ #
    resultats: list[dict] = []
    meta_seg: dict[str, dict] = {}
    ecarts_conformite: list[str] = []

    for seg in ("bas", "haut"):
        model_file = H.MODEL_DIR / f"enrichi_seg_{seg}_ba493568.json"
        attendu = H.HASH_MODEL_BAS if seg == "bas" else H.HASH_MODEL_HAUT
        if H.sha8(model_file) != attendu:
            stop(f"empreinte du modèle {seg} non canonique")

        m = xgb.XGBRegressor()
        m.load_model(str(model_file))
        sub = h25[h25["spatial_segment"] == seg]      # c08_shap_segments.py:44
        X = H.prep_X(sub, feats)[feats]
        dm = xgb.DMatrix(X, enable_categorical=True)
        contribs = m.get_booster().predict(dm, pred_contribs=True)
        shap_mat = contribs[:, :-1]                   # dernière colonne = biais

        # --- Contrôle de conformité BLOQUANT sur les 158 features ---------- #
        # `contribs` est en float32, donc `mabs` aussi, et c08 sérialise cette
        # colonne float32 : le CSV ne porte que ~8 chiffres significatifs. Une
        # comparaison en float64 contre la valeur relue échouerait donc sur un
        # simple artefact de sérialisation (écart ~1e-7), sans qu'aucun élément
        # du protocole ne diffère. Le contrôle est mené à deux niveaux :
        #   (a) égalité binaire des vecteurs float32 ;
        #   (b) égalité du TEXTE CSV obtenu en rejouant la sérialisation de c08
        #       (lignes 49-57), qui est le contrôle le plus strict disponible.
        mabs = np.abs(shap_mat).mean(axis=0)
        chemin_ref = H.OUT_DIR / f"c08_shap_ranks_{seg}.csv"
        ref_txt = chemin_ref.read_text()
        ref = pd.read_csv(chemin_ref).set_index("feature")
        ref_vec = ref.loc[feats, "mean_abs_shap"].to_numpy(dtype="float32")

        egal_float32 = bool(np.array_equal(mabs.astype("float32"), ref_vec))
        ecart_max = float(np.max(np.abs(
            mabs.astype("float64") - ref_vec.astype("float64"))))

        total_seg = float(mabs.sum())
        rejoue = pd.DataFrame({"feature": feats, "mean_abs_shap": mabs})
        rejoue = rejoue.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
        rejoue["rang"] = rejoue.index + 1
        rejoue["pct_du_total"] = rejoue["mean_abs_shap"] / total_seg * 100
        egal_texte = bool(rejoue.to_csv(index=False) == ref_txt)

        identiques = egal_float32 and egal_texte
        if not identiques:
            pires = np.argsort(-np.abs(
                mabs.astype("float64") - ref_vec.astype("float64")))[:5]
            detail = "; ".join(f"{feats[i]} recalculé={mabs[i]!r} "
                               f"c08={ref_vec[i]!r}" for i in pires)
            ecarts_conformite.append(
                f"{seg} : égalité float32 {egal_float32}, égalité du texte CSV "
                f"{egal_texte}, écart max {ecart_max:.3e} ({detail})")

        # Constance mesurée sur le périmètre exact du calcul SHAP
        constante = {f: bool(sub[f].nunique(dropna=False) <= 1) for f in feats}
        rang = ref["rang"].to_dict()

        meta_seg[seg] = {
            "n_obs": int(len(sub)),
            "somme_mean_abs_shap": float(mabs.sum()),
            "conformite": identiques,
            "egal_float32": egal_float32,
            "egal_texte": egal_texte,
            "ecart_max": ecart_max,
            "n_constantes": sum(constante.values()),
            "constantes": [f for f in feats if constante[f]],
            "biais_moyen": float(contribs[:, -1].mean()),
        }

        idx = {f: i for i, f in enumerate(feats)}

        def temoin(cible: str, veut_constante: bool) -> str | None:
            """Feature de rang le plus proche de `cible`, du régime demandé.

            Départage déterministe : distance de rang croissante, puis rang
            croissant. Les deux variables étudiées sont exclues du choix.
            """
            cands = [f for f in feats
                     if f not in CIBLES and constante[f] == veut_constante]
            if not cands:
                return None
            r0 = rang[cible]
            return sorted(cands, key=lambda f: (abs(rang[f] - r0), rang[f]))[0]

        for cible in CIBLES:
            for role, nom in (
                ("cible", cible),
                ("témoin variable", temoin(cible, False)),
                ("témoin constant", temoin(cible, True)),
            ):
                if nom is None:
                    resultats.append({
                        "segment": seg, "cible_de_reference": cible, "role": role,
                        "variable": "", "rang": "", "ecart_de_rang": "",
                        "constante_sur_le_segment": "",
                        "n_modalites_variable": "", "mean_abs_shap": "",
                        "moyenne_signee": "", "ecart_type": "", "min": "", "max": "",
                        "n_valeurs_distinctes": "",
                        "remarque": "aucune feature de ce régime hors des deux cibles",
                    })
                    continue
                st = stats_shap(shap_mat[:, idx[nom]])
                resultats.append({
                    "segment": seg, "cible_de_reference": cible, "role": role,
                    "variable": nom, "rang": int(rang[nom]),
                    "ecart_de_rang": abs(int(rang[nom]) - int(rang[cible])),
                    "constante_sur_le_segment": "oui" if constante[nom] else "non",
                    "n_modalites_variable": int(sub[nom].nunique(dropna=False)),
                    **{k: round(v, 10) if isinstance(v, float) else v
                       for k, v in st.items()},
                    "remarque": "",
                })

    if ecarts_conformite:
        stop("contrôle de conformité en échec, le mean|SHAP| recalculé ne "
             "reproduit pas c08 :\n    " + "\n    ".join(ecarts_conformite)
             + "\n    Aucune sortie n'est produite.")

    res = pd.DataFrame(resultats)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT_CSV, index=False, encoding="utf-8")

    # --- Rapport ----------------------------------------------------------- #
    emit("# Dispersion des valeurs SHAP de variables constantes sur H25")
    emit()
    emit("Vérif §4.5.6. Rapport produit en lecture seule par "
         "`docs/memoire/verifs/section_4_5_6/verif_shap_variables_constantes.py`. "
         "Aucun réentraînement, aucun artefact de modèle modifié.")
    emit()

    emit("## 1. Protocole et empreintes")
    emit()
    emit("Reprise exacte du protocole de `scripts/confirmation/c08_shap_segments.py` : "
         "mêmes modèles gelés, même périmètre H25 (ligne 35), même segmentation par "
         "`spatial_segment` (ligne 44), même préparation `_harness.prep_X`, même appel "
         "`booster.predict(dm, pred_contribs=True)`. La seule différence porte sur "
         "l'agrégation : c08 ne conserve que la moyenne des valeurs absolues, ce "
         "script conserve en outre la moyenne signée, l'écart-type, les extrêmes et "
         "le nombre de valeurs distinctes.")
    emit()
    emit("| Rôle | Chemin | Empreinte SHA256[:8] |")
    emit("|---|---|---|")
    emit(f"| Table canonique | `data/processed/ml_dataset.parquet` | `{h_canon}` |")
    for seg in ("bas", "haut"):
        f = H.MODEL_DIR / f"enrichi_seg_{seg}_ba493568.json"
        emit(f"| Modèle gelé {seg.upper()} | `{f.relative_to(ROOT)}` | `{H.sha8(f)}` |")
    for seg in ("bas", "haut"):
        f = H.OUT_DIR / f"c08_shap_ranks_{seg}.csv"
        emit(f"| Référence de conformité {seg.upper()} | `{f.relative_to(ROOT)}` | "
             f"`{sha256_8(f)}` |")
    emit()
    emit(f"Périmètre : H25, {mil(len(h25))} observations, réparties en "
         f"{mil(meta_seg['bas']['n_obs'])} sur BAS et "
         f"{mil(meta_seg['haut']['n_obs'])} sur HAUT.")
    emit()

    emit("## 2. Contrôle de conformité")
    emit()
    emit("Le `mean|SHAP|` recalculé est confronté à celui de c08 sur les **158 "
         "features**, et non sur les seules variables étudiées.")
    emit()
    emit("`pred_contribs` renvoie du float32, donc `mean|SHAP|` est en float32 et "
         "c08 sérialise cette colonne telle quelle : ses CSV ne portent qu'environ "
         "huit chiffres significatifs. Comparer en float64 la valeur recalculée à "
         "la valeur relue échouerait sur ce seul artefact de sérialisation, avec "
         "un écart de l'ordre de 1e-7, sans qu'aucun élément du protocole ne "
         "diffère. Le contrôle est donc mené à deux niveaux, le second étant le "
         "plus strict disponible.")
    emit()
    emit("| Segment | Features | Égalité binaire float32 | Égalité du texte CSV rejoué | "
         "Écart max en float64 |")
    emit("|---|---|---|---|---|")
    for seg in ("bas", "haut"):
        mseg = meta_seg[seg]
        emit(f"| {seg.upper()} | {N_FEATURES} | **{tick(mseg['egal_float32'])}** | "
             f"**{tick(mseg['egal_texte'])}** | {mseg['ecart_max']:.3e} |")
    emit()
    emit("Le second contrôle rejoue la sérialisation de c08 (tri décroissant, "
         "colonnes `rang` et `pct_du_total`, `to_csv`) et compare le texte obtenu "
         "au fichier publié, octet pour octet. Il passe sur les deux segments : le "
         "protocole reproduit donc c08 exactement, y compris sa sortie. Les "
         "statistiques de dispersion ci-dessous portent ainsi sur la même matrice "
         "de contributions que les rangs publiés.")
    emit()

    emit("## 3. Variables constantes sur le périmètre de calcul")
    emit()
    emit("La constance est mesurée sur le sous-ensemble effectivement soumis au "
         "modèle, c'est-à-dire H25 croisé avec le segment, et non sur H25 entier.")
    emit()
    for seg in ("bas", "haut"):
        mseg = meta_seg[seg]
        emit(f"**Segment {seg.upper()}** ({mil(mseg['n_obs'])} observations) : "
             f"{mseg['n_constantes']} feature(s) constante(s) parmi les 158.")
        emit()
        for f in mseg["constantes"]:
            marque = " *(variable étudiée)*" if f in CIBLES else ""
            emit(f"- `{f}`{marque}")
        emit()
    emit("Sur BAS, les deux variables étudiées sont les **seules** constantes des "
         "158. Aucun témoin constant n'y est donc disponible, ce que le tableau "
         "de la section 4 signale explicitement plutôt que de substituer un "
         "témoin d'un autre régime.")
    emit()
    emit("Sur HAUT, trois autres constantes existent, mais toutes en fond de "
         "classement :")
    emit()
    emit("| Feature constante (hors variables étudiées) | Rang | mean\\|SHAP\\| |")
    emit("|---|---|---|")
    ref_haut = pd.read_csv(H.OUT_DIR / "c08_shap_ranks_haut.csv").set_index("feature")
    for f in meta_seg["haut"]["constantes"]:
        if f in CIBLES:
            continue
        emit(f"| `{f}` | {int(ref_haut.loc[f, 'rang'])} | "
             f"{ref_haut.loc[f, 'mean_abs_shap']:.8f} |")
    emit()
    emit("**La consigne d'un témoin constant « de rang voisin » n'est donc "
         "satisfaisable sur aucun des deux segments.** Le témoin retenu sur HAUT "
         "est le plus proche disponible, mais l'écart de rang reste considérable, "
         "et la colonne « Δ rang » du tableau de la section 4 le chiffre. Ce "
         "constat est lui-même un résultat : parmi les 158 features, les seules "
         "constantes bien classées sont précisément les deux variables étudiées, "
         "toutes les autres se tenant aux trois derniers rangs avec un "
         "`mean|SHAP|` nul ou quasi nul.")
    emit()

    emit("## 4. Résultats")
    emit()
    emit("Témoins choisis par proximité de rang sur le même segment, à régime de "
         "constance imposé, les deux variables étudiées étant exclues du choix. "
         "Départage déterministe : distance de rang croissante, puis rang "
         "croissant.")
    emit()
    for seg in ("bas", "haut"):
        emit(f"### 4.{1 if seg == 'bas' else 2} Segment {seg.upper()} "
             f"({mil(meta_seg[seg]['n_obs'])} observations)")
        emit()
        emit("| Rôle | Variable | Rang | Δ rang | Constante | Modalités | "
             "mean\\|SHAP\\| | Moyenne signée | Écart-type | Min | Max | "
             "Valeurs distinctes |")
        emit("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for _, r in res[res["segment"] == seg].iterrows():
            if r["variable"] == "":
                emit(f"| {r['role']} | — | — | — | — | — | — | — | — | — | — | — |")
                continue
            emit(f"| {r['role']} | `{r['variable']}` | {r['rang']} | "
                 f"{r['ecart_de_rang']} | "
                 f"{r['constante_sur_le_segment']} | {r['n_modalites_variable']} | "
                 f"{r['mean_abs_shap']:.6f} | {r['moyenne_signee']:+.6f} | "
                 f"{r['ecart_type']:.6f} | {r['min']:+.6f} | {r['max']:+.6f} | "
                 f"{mil(int(r['n_valeurs_distinctes']))} |")
        emit()
        vides = res[(res["segment"] == seg) & (res["variable"] == "")]
        for _, r in vides.iterrows():
            emit(f"Ligne vide, rôle « {r['role']} » pour `{r['cible_de_reference']}` : "
                 f"{r['remarque']}.")
        if len(vides):
            emit()

    emit("## 5. Lecture")
    emit()
    emit("Le résultat central se lit dans la colonne « Valeurs distinctes ». Une "
         "variable strictement constante sur le périmètre y présente néanmoins "
         "plusieurs milliers de valeurs SHAP distinctes, avec un écart-type non "
         "nul et des extrêmes de signes opposés. La constance de l'entrée "
         "n'entraîne donc pas la constance de l'attribution.")
    emit()
    emit("L'explication tient à la nature de TreeSHAP. La contribution attribuée "
         "à une variable dans un arbre dépend du chemin réellement parcouru, donc "
         "des valeurs prises par les autres variables. Deux observations "
         "partageant la même modalité constante mais différant ailleurs "
         "atteignent des sous-arbres différents, où la contribution marginale de "
         "cette variable n'est pas la même. Le modèle a appris ces découpes sur "
         "H22-H24, où les deux variables varient effectivement, et il continue de "
         "les mobiliser sur H25 où elles ne varient plus.")
    emit()
    emit("La dispersion n'est pas pour autant automatique. Le témoin constant du "
         "segment HAUT, `spatial_gare_arrivee_part_hpi_non_plausible`, est lui "
         "aussi figé, mais son écart-type est de trois ordres de grandeur "
         "inférieur et ses valeurs SHAP se réduisent à une poignée de modalités. "
         "La différence tient à l'usage que le modèle fait de la variable : une "
         "variable figée que les arbres ne mobilisent presque pas reçoit une "
         "attribution quasi dégénérée, tandis qu'une variable figée que les "
         "arbres mobilisent abondamment reçoit une attribution largement "
         "dispersée. La dispersion mesure l'intensité des interactions, non la "
         "variabilité de l'entrée.")
    emit()
    emit("Conséquence méthodologique pour le manuscrit : un `mean|SHAP|` élevé ne "
         "garantit pas qu'une variable porte de l'information discriminante sur "
         "le périmètre d'évaluation. Il mesure l'ampleur de l'attribution, pas la "
         "variabilité de l'entrée. Une variable figée peut recevoir une "
         "attribution substantielle par le seul jeu des interactions, et le rang "
         "SHAP doit être lu avec cette réserve.")
    emit()
    emit("Sur la reproductibilité : le contrôle de conformité de la section 2 "
         "établit que le calcul mené ici reproduit octet pour octet la sortie de "
         "c08, produite lors d'une exécution antérieure et indépendante. C'est "
         "une preuve de reproductibilité plus forte qu'une simple répétition du "
         "présent script.")
    emit()

    emit("## 6. Livrables")
    emit()
    emit("| Fichier | Contenu |")
    emit("|---|---|")
    emit(f"| `{OUT_CSV.relative_to(ROOT)}` | Statistiques, {len(res)} lignes |")
    emit(f"| `{OUT_MD.relative_to(ROOT)}` | Le présent rapport |")
    emit(f"| `{Path(__file__).relative_to(ROOT)}` | Script, réexécutable en une commande |")
    emit()

    OUT_MD.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(f"Conformité mean|SHAP| vs c08 : "
          f"BAS {tick(meta_seg['bas']['conformite'])} / "
          f"HAUT {tick(meta_seg['haut']['conformite'])}")
    for seg in ("bas", "haut"):
        for cible in CIBLES:
            r = res[(res["segment"] == seg) & (res["variable"] == cible)].iloc[0]
            print(f"  {seg:<4} {cible:<30} sd={r['ecart_type']:.6f} "
                  f"n_distinctes={int(r['n_valeurs_distinctes'])}")


if __name__ == "__main__":
    main()
