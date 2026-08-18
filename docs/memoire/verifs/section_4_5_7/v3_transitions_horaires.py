#!/usr/bin/env python3
"""
V3 — Stabilité des numéros de train aux transitions d'horaire H22→H23, H23→H24, H24→H25.

Le manuscrit (§4.5.1) affirme que la transition de décembre 2023 « n'avait modifié aucun »
numéro de train, par contraste avec celle de 2024. Ce script calcule les cardinaux
directement, sur les deux référentiels et sous trois filtres.

LECTURE SEULE. N'écrit que sous docs/memoire/verifs/section_4_5/.

RÉFÉRENTIELS
  ml_dataset  `ml_dataset.parquet` — trains effectivement MESURÉS par l'APC (périmètre du
              modèle) ; un seul filtre possible.
  istdaten    `istdaten_clean.parquet` — trains effectivement CIRCULÉS. Trois filtres :
                tous        toutes les lignes
                hors_annules                     is_annule == False
                grille_reguliere                 is_annule == False ET is_supplementaire == False
              Le troisième isole la GRILLE RÉGULIÈRE : un train de renfort porte un numéro
              qui n'appartient pas à la grille cadencée et gonfle artificiellement les
              cardinaux d'une année horaire.

BORNES D'ANNÉE HORAIRE — dérivées des données (min/max de `base_date` par
`horaire_annee_horaire` dans ml_dataset), jamais codées en dur. Deux découpages :
  observees   [min, max] observés — laisse un interstice de quelques jours entre années
  contigue    [début(H_n), début(H_n+1) − 1 j] — partition sans perte de jour
Les deux sont calculés : si le résultat en dépendait, il faudrait le dire.

Sorties :
  - v3_ensembles_par_annee.csv   cardinaux par (référentiel, filtre, découpage, année)
  - v3_transitions.csv           cardinaux de transition, une ligne par transition
  - v3_numeros_hors_grille.csv   numéros vus uniquement en supplémentaire ou annulé
  - v3_transitions.json          synthèse machine

Usage :
    ./venv/bin/python docs/memoire/verifs/section_4_5/v3_transitions_horaires.py
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ML = ROOT / "data/processed/ml_dataset.parquet"
IST = ROOT / "data/processed/sources/istdaten_clean.parquet"
HASH_ATTENDU = "ba493568"

ANNEES = ["H22", "H23", "H24", "H25"]
TRANSITIONS = [("H22", "H23"), ("H23", "H24"), ("H24", "H25")]


def sha8(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]


def bornes(df):
    """Deux découpages en années horaires, dérivés de ml_dataset."""
    b = df.groupby("horaire_annee_horaire")["base_date"].agg(debut="min", fin="max",
                                                             n_jours="nunique")
    b = b.reindex([a for a in ANNEES if a in b.index])
    obs, cont = {}, {}
    idx = list(b.index)
    for i, a in enumerate(idx):
        obs[a] = (b.loc[a, "debut"], b.loc[a, "fin"])
        fin_c = (b.loc[idx[i + 1], "debut"] - pd.Timedelta(days=1)) if i + 1 < len(idx) \
            else b.loc[a, "fin"]
        cont[a] = (b.loc[a, "debut"], fin_c)
    return b, {"observees": obs, "contigue": cont}


def main() -> int:
    print("=== V3 — stabilité des numéros de train aux transitions d'horaire (lecture seule) ===")
    h = sha8(ML)
    if h != HASH_ATTENDU:
        raise RuntimeError(f"STOP : hash ml_dataset {h} != {HASH_ATTENDU}")

    ml = pd.read_parquet(ML, columns=["horaire_annee_horaire", "horaire_numero_train",
                                      "base_date"])
    b, decoupages = bornes(ml)
    print("  bornes dérivées de ml_dataset :")
    for a in b.index:
        print(f"    {a} : {b.loc[a, 'debut'].date()} → {b.loc[a, 'fin'].date()} "
              f"({int(b.loc[a, 'n_jours'])} jours)")
    interstices = []
    idx = list(b.index)
    for i in range(len(idx) - 1):
        d = (b.loc[idx[i + 1], "debut"] - b.loc[idx[i], "fin"]).days - 1
        interstices.append({"transition": f"{idx[i]}→{idx[i + 1]}", "jours_sans_observation": int(d)})
    print(f"  interstices entre années horaires observées : "
          f"{[(x['transition'], x['jours_sans_observation']) for x in interstices]}")

    # ── Ensembles de numéros ───────────────────────────────────────────────────
    ensembles = {}   # (referentiel, filtre, decoupage) -> {annee: set}

    # Référentiel 1 : ml_dataset (le découpage est porté par la colonne elle-même)
    e = {a: set(g["horaire_numero_train"].dropna().astype(int))
         for a, g in ml.groupby("horaire_annee_horaire")}
    ensembles[("ml_dataset", "mesure_apc", "colonne_annee_horaire")] = e

    # Référentiel 2 : istdaten_clean
    if not IST.exists():
        raise RuntimeError("STOP : istdaten_clean.parquet absent — V3 exige les deux référentiels")
    di = pd.read_parquet(IST, columns=["date", "numero_train", "is_annule", "is_supplementaire"])
    di["date"] = pd.to_datetime(di["date"])
    FILTRES = {
        "tous": pd.Series(True, index=di.index),
        "hors_annules": ~di["is_annule"],
        "grille_reguliere": (~di["is_annule"]) & (~di["is_supplementaire"]),
    }
    for nom_dec, dec in decoupages.items():
        for nom_f, f in FILTRES.items():
            d = di[f]
            ensembles[("istdaten", nom_f, nom_dec)] = {
                a: set(d.loc[(d["date"] >= deb) & (d["date"] <= fin), "numero_train"]
                       .dropna().astype(int))
                for a, (deb, fin) in dec.items()}

    # ── Cardinaux par année ────────────────────────────────────────────────────
    lignes = []
    for (ref, filt, dec), e in ensembles.items():
        for a in ANNEES:
            if a in e:
                lignes.append({"referentiel": ref, "filtre": filt, "decoupage": dec,
                               "annee_horaire": a, "n_numeros_train": len(e[a])})
    card = pd.DataFrame(lignes)
    card.to_csv(OUT / "v3_ensembles_par_annee.csv", index=False)

    # ── Transitions ────────────────────────────────────────────────────────────
    lignes = []
    for (ref, filt, dec), e in ensembles.items():
        for a, c in TRANSITIONS:
            if a not in e or c not in e:
                continue
            A, B = e[a], e[c]
            lignes.append({
                "referentiel": ref, "filtre": filt, "decoupage": dec,
                "transition": f"{a}→{c}",
                "n_avant": len(A), "n_apres": len(B),
                "n_intersection": len(A & B),
                "n_disparus": len(A - B), "n_nouveaux": len(B - A),
                "n_union": len(A | B),
                "stabilite_pct": round(100 * len(A & B) / len(A | B), 2),
                "part_nouveaux_dans_apres_pct": round(100 * len(B - A) / len(B), 2),
                "numeros_disparus": ";".join(str(x) for x in sorted(A - B)),
                "numeros_nouveaux": ";".join(str(x) for x in sorted(B - A)),
            })
    tr = pd.DataFrame(lignes)
    tr.to_csv(OUT / "v3_transitions.csv", index=False)

    print("\n  transitions (indice de stabilité = |∩| / |∪|) :")
    vue = tr[tr["decoupage"].isin(["colonne_annee_horaire", "observees"])]
    for _, r in vue.iterrows():
        print(f"    [{r.referentiel:10} {r.filtre:16}] {r.transition} : "
              f"{r.n_avant:3} → {r.n_apres:3} | ∩={r.n_intersection:3} "
              f"| −{r.n_disparus:2} +{r.n_nouveaux:2} | stabilité {r.stabilite_pct:6.2f} %")

    # ── Numéros hors grille régulière ──────────────────────────────────────────
    e_tous = ensembles[("istdaten", "tous", "observees")]
    e_reg = ensembles[("istdaten", "grille_reguliere", "observees")]
    hors = []
    for a in ANNEES:
        for n in sorted(e_tous.get(a, set()) - e_reg.get(a, set())):
            m = (di["numero_train"] == n) & (di["date"] >= decoupages["observees"][a][0]) \
                & (di["date"] <= decoupages["observees"][a][1])
            hors.append({"annee_horaire": a, "numero_train": int(n),
                         "n_passages": int(m.sum()),
                         "n_passages_supplementaires": int((m & di["is_supplementaire"]).sum()),
                         "n_passages_annules": int((m & di["is_annule"]).sum()),
                         "n_jours": int(di.loc[m, "date"].nunique())})
    hg = pd.DataFrame(hors)
    hg.to_csv(OUT / "v3_numeros_hors_grille.csv", index=False)
    print("\n  numéros vus uniquement hors grille régulière (renfort ou annulé) :")
    print("   " + (hg.to_string(index=False).replace("\n", "\n   ") if len(hg) else "aucun"))

    # ── Verdict sur l'affirmation du manuscrit ─────────────────────────────────
    def get(ref, filt, dec, trans):
        s = tr[(tr.referentiel == ref) & (tr.filtre == filt) & (tr.decoupage == dec)
               & (tr.transition == trans)]
        return None if s.empty else s.iloc[0].to_dict()

    verdict = {}
    for trans in ("H22→H23", "H23→H24", "H24→H25"):
        cas = {
            "ml_dataset": get("ml_dataset", "mesure_apc", "colonne_annee_horaire", trans),
            "istdaten_grille_reguliere": get("istdaten", "grille_reguliere", "observees", trans),
            "istdaten_tous_passages": get("istdaten", "tous", "observees", trans),
        }
        aucun_changement = {k: (v is not None and v["n_disparus"] == 0 and v["n_nouveaux"] == 0)
                            for k, v in cas.items()}
        verdict[trans] = {"cas": cas, "aucun_changement_de_numero": aucun_changement}

    # Le résultat dépend-il du découpage ? (comparaison restreinte aux lignes qui
    # existent sous LES DEUX découpages — ml_dataset n'en a qu'un, sa colonne d'année)
    piv = (tr[tr["decoupage"].isin(["observees", "contigue"])]
           .pivot_table(index=["referentiel", "filtre", "transition"], columns="decoupage",
                        values=["n_avant", "n_apres", "n_disparus", "n_nouveaux"],
                        aggfunc="first"))
    paires = [c for c in ("n_avant", "n_apres", "n_disparus", "n_nouveaux")
              if (c, "observees") in piv.columns and (c, "contigue") in piv.columns]
    comparables = piv.dropna(subset=[(c, d) for c in paires for d in ("observees", "contigue")])
    dep = bool(any((comparables[(c, "observees")] != comparables[(c, "contigue")]).any()
                   for c in paires))
    print(f"\n  découpage : {len(comparables)} transitions comparables sous les deux "
          f"variantes | le résultat en dépend-il ? {'OUI' if dep else 'NON'}")

    payload = {
        "script": "v3_transitions_horaires.py",
        "sources": {"ml_dataset.parquet": HASH_ATTENDU, "istdaten_clean.parquet": sha8(IST)},
        "bornes": [{"annee_horaire": a, "debut": str(b.loc[a, "debut"].date()),
                    "fin": str(b.loc[a, "fin"].date()), "n_jours": int(b.loc[a, "n_jours"])}
                   for a in b.index],
        "interstices_entre_annees": interstices,
        "sensibilite_au_decoupage": dep,
        "cardinaux_par_annee": card.to_dict(orient="records"),
        "transitions": tr.drop(columns=["numeros_disparus", "numeros_nouveaux"]).to_dict(orient="records"),
        "numeros_hors_grille_reguliere": hors,
        "verdict_par_transition": verdict,
        "affirmation_manuscrit_4_5_1": "la transition de décembre 2023 n'avait modifié "
                                       "aucun numéro de train",
    }
    (OUT / "v3_transitions.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                                       default=str))
    print(f"[OK] sorties dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
