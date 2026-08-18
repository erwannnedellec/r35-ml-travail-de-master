#!/usr/bin/env python3
"""Vérif §4.3 — Profil de charge ORIENTÉ de la R35 (charge 2e classe + montées/descentes
par gare), séparément pour le sens aller (Vevey → Les Pléiades) et retour (PLEI → VV).

LECTURE SEULE. Aucune valeur n'est recopiée d'un rapport ; tout est recalculé ici depuis
les tables canoniques. Ce module expose aussi les fonctions d'agrégation consommées par
la figure `../figures/section_4_3/fig_profil_charge_oriente.py` (DRY, même périmètre).

────────────────────────────────────────────────────────────────────────────────────────
ÉTAPE 1 — SOURCE CANONIQUE
────────────────────────────────────────────────────────────────────────────────────────
Fichier retenu : data/processed/sources/apc_stacked.parquet
  · SHA256[:8] = e11a203c ; 2 360 762 lignes (grain course × tronçon × sens × date, H16→H25) ;
    58 colonnes. C'est la table APC LUE par la couche 2 canonique (src/couche2/blocs.py,
    `APC_STACKED`) — celle qui définit l'iso-périmètre d'évaluation. Elle porte, au grain
    course × tronçon, TOUTES les grandeurs requises :
      - charge 2e classe .......... target_voyageurs_2eme_classe
      - montées 2e classe ......... base_passagers_montant_2eme_classe   (gare de DÉPART)
      - descentes 2e classe ....... base_passagers_descendants_2eme_classe (gare d'ARRIVÉE)
      - identifiant de tronçon .... (id_gare_depart_bpuic, id_gare_arrivee_bpuic) + ordres
      - sens de circulation ....... base_sens ∈ {"VV -> PLEI", "PLEI -> VV"}
  Le dataset couche 1 canonique ml_dataset.parquet (ba493568) NE PORTE PAS montées/descentes ;
  apc_stacked en est la source amont directe (mêmes 2 360 762 lignes que stage_01, colonnes
  APC brutes conservées). La charge y est byte-identique à celle de ml_dataset (vérifié).

RÈGLE DE SENS (déterministe, non ambiguë) : le sens est lu directement dans `base_sens`.
  Cohérence de contrôle avec la géographie : "VV -> PLEI" ⇔ ordre(arrivée) > ordre(départ)
  à 100 % (et réciproquement pour "PLEI -> VV"). Aucune inférence n'est faite : base_sens fait foi.

────────────────────────────────────────────────────────────────────────────────────────
PÉRIMÈTRE — H25, iso-périmètre d'évaluation (référence 29 222 courses)
────────────────────────────────────────────────────────────────────────────────────────
Iso-périmètre couche 2 (ADR-073 §Référence D5, `decision.ISO_PERIMETRE_H25 = 29222`) =
  intersection stricte, au grain course (date, numéro de train) :
    prédiction (ml_dataset H25)  ∩  décision UM humaine (rotations)  ∩  label observé (APC).
Reconstruit ici par clés (sans modèle) : ml_dataset[H25] ∩ (rotations ∩ apc_stacked).
Le compte obtenu est CONTRÔLÉ == 29 222 (RuntimeError sinon — on signale, on n'absorbe pas).
ml_dataset H25 compte 29 224 courses ; 2 sont « ml-only » (hors décision humaine) → 29 222.

────────────────────────────────────────────────────────────────────────────────────────
CONVENTION DE CONSERVATION (déterminée empiriquement, non supposée)
────────────────────────────────────────────────────────────────────────────────────────
Les montées sont enregistrées à la gare de DÉPART du tronçon, les descentes à la gare
d'ARRIVÉE. La loi de conservation qui se vérifie (≈99,4–99,9 %) est donc, pour deux
tronçons consécutifs t → t+1 partageant la gare G (arrivée de t = départ de t+1) :

    charge(t+1) = charge(t) + montées(G) − descentes(G)
                = charge(t) + montant(t+1) − descendant(t)

L'attribution alternative (descentes à la gare de départ) est massivement fausse
(45–76 % de paires non conservatives) et est reportée comme contre-épreuve.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]  # section_4_3/ → verifs/ → memoire/ → docs/ → racine
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

APC = ROOT / "data/processed/sources/apc_stacked.parquet"
ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"

SENS_ALLER = "VV -> PLEI"     # Vevey → Les Pléiades
SENS_RETOUR = "PLEI -> VV"    # Les Pléiades → Vevey
ORDRE_PLAINE_MAX = 10         # gare ordre <=10 = plaine (bas) ; >10 = crémaillère (haut) (blocs.py)
ISO_PERIMETRE_H25 = 29222     # decision.ISO_PERIMETRE_H25 (ADR-073)
SEUIL_ASSISES, SEUIL_SATURATION = 63, 94


# ════════════════════════════════════════════════════════════════════════════════════════
# Périmètre + chargement
# ════════════════════════════════════════════════════════════════════════════════════════
def reconstruire_perimetre_h25() -> pd.DataFrame:
    """Iso-périmètre H25 (29 222 courses) par clés : ml_dataset[H25] ∩ (rotations ∩ apc)."""
    from couche2 import blocs
    blocs.assert_canonical_dataset()  # garde-fou dur : ml_dataset = ba493568

    mdf = pd.read_parquet(ML_DATASET, columns=[
        "base_date", "horaire_annee_horaire", "horaire_numero_train"])
    mdf = mdf[mdf.horaire_annee_horaire == "H25"]
    mdf["date"] = pd.to_datetime(mdf.base_date).dt.normalize()
    mdf["numero_train"] = mdf.horaire_numero_train.astype("Int64").astype(str)
    mlk = mdf[["date", "numero_train"]].drop_duplicates()

    comp = blocs.load_composition()                 # rotations (décision UM humaine)
    charge = blocs.load_charge()                     # APC agrégée course
    comp["date"] = pd.to_datetime(comp.date).dt.normalize()
    charge["date"] = pd.to_datetime(charge.date).dt.normalize()
    human = comp.merge(charge, on=["date", "numero_train"], how="inner")[
        ["date", "numero_train"]].drop_duplicates()

    peri = mlk.merge(human, on=["date", "numero_train"], how="inner").drop_duplicates()
    n = len(peri)
    if n != ISO_PERIMETRE_H25:
        raise RuntimeError(
            f"Iso-périmètre H25 reconstruit = {n} != {ISO_PERIMETRE_H25} attendu "
            f"(ml_dataset H25 = {len(mlk)}, ml-only = {len(mlk) - n}). ÉCART SIGNALÉ.")
    return peri


def charger_apc_perimetre(peri: pd.DataFrame) -> pd.DataFrame:
    """Retourne les lignes course × tronçon de apc_stacked restreintes à l'iso-périmètre H25.
    Colonnes normalisées : date, numero_train, base_sens, do/ao (ordres), noms, km,
    charge, mont, desc, seg (bas/haut selon ordre>10)."""
    apc = pd.read_parquet(APC, columns=[
        "base_date", "horaire_numero_train", "base_sens",
        "id_gare_depart", "id_gare_arrivee",
        "id_gare_depart_bpuic", "id_gare_arrivee_bpuic",
        "spatial_gare_depart_nom", "spatial_gare_arrivee_nom",
        "spatial_gare_depart_ordre", "spatial_gare_arrivee_ordre",
        "spatial_gare_depart_km", "spatial_gare_arrivee_km",
        "target_voyageurs_2eme_classe",
        "base_passagers_montant_2eme_classe", "base_passagers_descendants_2eme_classe"])
    apc["date"] = pd.to_datetime(apc.base_date).dt.normalize()
    apc["numero_train"] = apc.horaire_numero_train.astype("Int64").astype(str)
    d = apc.merge(peri, on=["date", "numero_train"], how="inner").copy()
    d.rename(columns={
        "target_voyageurs_2eme_classe": "charge",
        "base_passagers_montant_2eme_classe": "mont",
        "base_passagers_descendants_2eme_classe": "desc",
        "spatial_gare_depart_ordre": "do", "spatial_gare_arrivee_ordre": "ao",
        "spatial_gare_depart_nom": "nom_dep", "spatial_gare_arrivee_nom": "nom_arr",
        "spatial_gare_depart_km": "km_dep", "spatial_gare_arrivee_km": "km_arr",
        "id_gare_depart": "ab_dep", "id_gare_arrivee": "ab_arr"}, inplace=True)
    d["seg"] = np.where((d.do > ORDRE_PLAINE_MAX) | (d.ao > ORDRE_PLAINE_MAX), "haut", "bas")
    # clé d'ordonnancement le long du trajet (croissant dans le sens de circulation)
    d["routepos"] = np.where(d.base_sens == SENS_ALLER, d.do, -d.do)
    return d


def ordres_desservis(d: pd.DataFrame) -> list[int]:
    """Liste ordonnée des ordres de gares desservies (H25 : 0,2,4,5,…,18 — 17 gares)."""
    return sorted(set(d.do) | set(d.ao))


def carte_gares(d: pd.DataFrame) -> pd.DataFrame:
    """Table ordre → (abréviation, nom, km) pour l'axe des gares (union départ/arrivée)."""
    a = d[["do", "ab_dep", "nom_dep", "km_dep"]].rename(
        columns={"do": "ordre", "ab_dep": "ab", "nom_dep": "nom", "km_dep": "km"})
    b = d[["ao", "ab_arr", "nom_arr", "km_arr"]].rename(
        columns={"ao": "ordre", "ab_arr": "ab", "nom_arr": "nom", "km_arr": "km"})
    g = pd.concat([a, b]).drop_duplicates("ordre").sort_values("ordre").reset_index(drop=True)
    return g


# ════════════════════════════════════════════════════════════════════════════════════════
# Agrégats : flux par gare, charge par tronçon (consommés par la figure)
# ════════════════════════════════════════════════════════════════════════════════════════
def flux_par_gare(d: pd.DataFrame, sens: str) -> pd.DataFrame:
    """Montées (à la gare de DÉPART) et descentes (à la gare d'ARRIVÉE) moyennes par gare.
    montées[G] = moyenne(montant) des tronçons partant de G ;
    descentes[G] = moyenne(descendant) des tronçons arrivant à G."""
    s = d[d.base_sens == sens]
    mont = s.groupby("do").agg(montees_moy=("mont", "mean"), n_dep=("mont", "size"))
    desc = s.groupby("ao").agg(descentes_moy=("desc", "mean"), n_arr=("desc", "size"))
    mont.index.name = "ordre"; desc.index.name = "ordre"
    g = pd.concat([mont, desc], axis=1)
    g["montees_moy"] = g["montees_moy"].fillna(0.0)
    g["descentes_moy"] = g["descentes_moy"].fillna(0.0)
    g["n_dep"] = g["n_dep"].fillna(0).astype(int)
    g["n_arr"] = g["n_arr"].fillna(0).astype(int)
    return g.sort_index()


def profil_charge_troncon(d: pd.DataFrame, sens: str, gares: pd.DataFrame,
                          n_min: int = 50) -> pd.DataFrame:
    """Statistiques de charge par tronçon canonique (paires de gares consécutives desservies).
    Positionne chaque tronçon par pos = min(ordre_dep, ordre_arr) = gare aval (ordre inférieur).
    Rattache montées/descentes moyennes à la gare d'ORIGINE (départ) du tronçon."""
    O = list(gares.ordre)
    nxt = {O[i]: O[i + 1] for i in range(len(O) - 1)}
    nom = dict(zip(gares.ordre, gares.nom)); ab = dict(zip(gares.ordre, gares.ab))
    km = dict(zip(gares.ordre, gares.km))
    fg = flux_par_gare(d, sens)

    s = d[d.base_sens == sens].copy()
    s["pos"] = s[["do", "ao"]].min(axis=1)
    s["posmax"] = s[["do", "ao"]].max(axis=1)
    # tronçon canonique = paire consécutive desservie (posmax == next(pos))
    s["canon"] = s.apply(lambda r: nxt.get(r.pos) == r.posmax, axis=1)
    rares = s[~s.canon]
    if len(rares):
        rr = rares.groupby(["do", "ao"]).size()
        print(f"  [{sens}] tronçons non canoniques (skips intra-H25) exclus : "
              f"{len(rares)} lignes / {len(rr)} paires — {dict(rr)}")
    s = s[s.canon]

    rows = []
    for pos, grp in s.groupby("pos"):
        c = grp.charge.astype(float)
        orig = pos if sens == SENS_ALLER else nxt[pos]   # gare d'origine (départ) du tronçon
        rows.append({
            "sens": sens,
            "troncon": f"{ab[pos]}-{ab[nxt[pos]]}",
            "gare_aval": nom[pos], "gare_amont": nom[nxt[pos]],
            "ordre_aval": pos, "ordre_amont": nxt[pos],
            "km_aval": km[pos], "km_amont": km[nxt[pos]],
            "gare_origine": nom[orig],
            "segment": "haut" if (pos > ORDRE_PLAINE_MAX or nxt[pos] > ORDRE_PLAINE_MAX) else "bas",
            "n_courses": len(grp),
            "charge_moy": c.mean(), "charge_med": c.median(),
            "charge_p90": c.quantile(0.90), "charge_p95": c.quantile(0.95),
            "charge_p99": c.quantile(0.99), "charge_max": c.max(),
            "montees_moy_origine": fg.loc[orig, "montees_moy"] if orig in fg.index else 0.0,
            "descentes_moy_origine": fg.loc[orig, "descentes_moy"] if orig in fg.index else 0.0,
        })
    return pd.DataFrame(rows).sort_values("ordre_aval").reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════════════════
# Contrôles : conservation, part bas, typologie d'extension
# ════════════════════════════════════════════════════════════════════════════════════════
def controle_conservation(d: pd.DataFrame) -> pd.DataFrame:
    """charge(t+1) = charge(t) + montant(t+1) − descendant(t) [H2, descentes à l'arrivée].
    Contre-épreuve H1 (descentes au départ). Écart moyen + part de paires non conservatives."""
    d2 = d.sort_values(["date", "numero_train", "routepos"]).copy()
    g = d2.groupby(["date", "numero_train"], sort=False)
    charge_next = g["charge"].shift(-1)
    mont_next = g["mont"].shift(-1)
    desc_next = g["desc"].shift(-1)
    d2["r_H2"] = charge_next - d2["charge"] - mont_next + d2["desc"]        # desc à l'arrivée
    d2["r_H1"] = charge_next - d2["charge"] - mont_next + desc_next          # desc au départ
    d2["valide"] = charge_next.notna()
    pairs = d2[d2.valide]
    rows = []
    for sens in [SENS_ALLER, SENS_RETOUR]:
        p = pairs[pairs.base_sens == sens]
        for hyp, col in [("H2_descentes_arrivee", "r_H2"), ("H1_descentes_depart", "r_H1")]:
            r = p[col].astype(float)
            rows.append({
                "sens": sens, "hypothese": hyp, "n_paires": len(p),
                "ecart_moyen_abs": r.abs().mean(), "ecart_moyen_signe": r.mean(),
                "part_non_conservatif_pct": 100.0 * (r.abs() > 1e-9).mean(),
                "part_ecart_sup1_pct": 100.0 * (r.abs() > 1.0).mean(),
            })
    return pd.DataFrame(rows)


def part_charge_bas(d: pd.DataFrame) -> pd.DataFrame:
    """Part de la charge 2e classe portée par le segment bas (ordre<=10) : H25 iso, par sens,
    + reproduction du 88,35 % du manuscrit (ml_dataset FULL H22-H25) et ml FULL H25."""
    rows = []

    def _p(sub, label, perim):
        tot = float(sub.charge.sum()); bas = float(sub[sub.seg == "bas"].charge.sum())
        rows.append({"chiffre": label, "perimetre": perim,
                     "charge_bas": int(bas), "charge_totale": int(tot),
                     "part_bas_pct": 100.0 * bas / tot})

    for sens in [SENS_ALLER, SENS_RETOUR]:
        _p(d[d.base_sens == sens], f"part_bas_{sens}", "H25 iso-périmètre (29 222 courses)")
    _p(d, "part_bas_sens_confondus", "H25 iso-périmètre (29 222 courses)")

    ml = pd.read_parquet(ML_DATASET, columns=[
        "horaire_annee_horaire", "spatial_segment", "target_voyageurs_2eme_classe"])
    ml["charge"] = ml.target_voyageurs_2eme_classe.astype(float)
    ml["seg"] = ml.spatial_segment.astype(str)
    _p(ml, "part_bas_manuscrit", "ml_dataset FULL H22-H25, sens confondus")
    _p(ml[ml.horaire_annee_horaire == "H25"], "part_bas_ml_full_H25",
       "ml_dataset FULL H25 seul, sens confondus")
    return pd.DataFrame(rows)


def typologie_extension(d: pd.DataFrame, gares: pd.DataFrame) -> pd.DataFrame:
    """Courses limitées à Blonay (0↔10) vs complètes (0↔18) vs intermédiaires, par sens."""
    ext = d.groupby(["date", "numero_train", "base_sens"]).agg(
        lo=("do", "min"), lo2=("ao", "min"), hi=("do", "max"), hi2=("ao", "max")).reset_index()
    ext["lo"] = ext[["lo", "lo2"]].min(axis=1)
    ext["hi"] = ext[["hi", "hi2"]].max(axis=1)

    def cat(r):
        if r.lo == 0 and r.hi == 18:
            return "complete (Vevey<->Pleiades)"
        if r.lo == 0 and r.hi == ORDRE_PLAINE_MAX:
            return "limitee a Blonay (Vevey<->Blonay)"
        if r.lo == 0 and ORDRE_PLAINE_MAX < r.hi < 18:
            return "montagne partielle (Vevey<->intermediaire haut)"
        if r.lo >= ORDRE_PLAINE_MAX:
            return "navette haute (depart >= Blonay)"
        return "autre"
    ext["categorie"] = ext.apply(cat, axis=1)
    piv = ext.groupby(["base_sens", "categorie"]).size().rename("n_courses").reset_index()
    tot = ext.groupby("base_sens").size().rename("n_total").reset_index()
    piv = piv.merge(tot, on="base_sens")
    piv["part_pct"] = 100.0 * piv.n_courses / piv.n_total
    ordre_cat = ["complete (Vevey<->Pleiades)", "limitee a Blonay (Vevey<->Blonay)",
                 "montagne partielle (Vevey<->intermediaire haut)",
                 "navette haute (depart >= Blonay)", "autre"]
    piv["k"] = piv.categorie.map({c: i for i, c in enumerate(ordre_cat)})
    return piv.sort_values(["base_sens", "k"]).drop(columns="k").reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 88)
    print("VÉRIF §4.3 — Profil de charge orienté R35 (H25, iso-périmètre 29 222 courses)")
    print("Source : data/processed/sources/apc_stacked.parquet")
    print("=" * 88)

    peri = reconstruire_perimetre_h25()
    print(f"Iso-périmètre H25 CONFIRMÉ : {len(peri)} courses (== {ISO_PERIMETRE_H25}).")
    d = charger_apc_perimetre(peri)
    print(f"Lignes course × tronçon (H25 iso) : {len(d):,} | "
          f"NaN charge={int(d.charge.isna().sum())} montant={int(d.mont.isna().sum())} "
          f"descentes={int(d.desc.isna().sum())}")
    n_sens = d.drop_duplicates(["date", "numero_train"]).base_sens.value_counts().to_dict()
    print(f"Courses par sens : aller (VV→PLEI)={n_sens.get(SENS_ALLER)} | "
          f"retour (PLEI→VV)={n_sens.get(SENS_RETOUR)} "
          f"(ANOMALIE À SIGNALER : asymétrie {n_sens.get(SENS_RETOUR) - n_sens.get(SENS_ALLER)} "
          f"courses de plus au retour).")

    gares = carte_gares(d)
    print(f"\nGares desservies H25 : {len(gares)} (ordres {list(gares.ordre)})")

    # -- Tables par tronçon (les deux sens) --
    prof = pd.concat([profil_charge_troncon(d, SENS_ALLER, gares),
                      profil_charge_troncon(d, SENS_RETOUR, gares)], ignore_index=True)
    # -- Flux par gare (les deux sens) --
    fg_rows = []
    nom = dict(zip(gares.ordre, gares.nom)); ab = dict(zip(gares.ordre, gares.ab))
    for sens in [SENS_ALLER, SENS_RETOUR]:
        fg = flux_par_gare(d, sens).reset_index()
        fg["sens"] = sens; fg["gare"] = fg.ordre.map(nom); fg["ab"] = fg.ordre.map(ab)
        fg_rows.append(fg)
    flux = pd.concat(fg_rows, ignore_index=True)[
        ["sens", "ordre", "ab", "gare", "montees_moy", "descentes_moy", "n_dep", "n_arr"]]

    cons = controle_conservation(d)
    partb = part_charge_bas(d)
    typo = typologie_extension(d, gares)

    print("\n--- CONSERVATION (charge(t+1)=charge(t)+montant(t+1)−descendant(t)) ---")
    print(cons.to_string(index=False))
    print("\n--- PART DE CHARGE — SEGMENT BAS ---")
    print(partb.to_string(index=False))
    print("\n--- TYPOLOGIE D'EXTENSION ---")
    print(typo.to_string(index=False))
    print("\n--- PROFIL DE CHARGE PAR TRONÇON (extrait) ---")
    print(prof[["sens", "troncon", "n_courses", "charge_moy", "charge_med",
                "charge_p90", "charge_p99", "charge_max"]].to_string(index=False))

    # -- Écritures --
    prof.round(3).to_csv(DOSSIER / "verif_43_profil_troncon.csv", index=False, encoding="utf-8-sig")
    flux.round(3).to_csv(DOSSIER / "verif_43_flux_gare.csv", index=False, encoding="utf-8-sig")
    cons.round(4).to_csv(DOSSIER / "verif_43_conservation.csv", index=False, encoding="utf-8-sig")
    partb.round(3).to_csv(DOSSIER / "verif_43_part_bas.csv", index=False, encoding="utf-8-sig")
    typo.round(3).to_csv(DOSSIER / "verif_43_extension.csv", index=False, encoding="utf-8-sig")
    print("\nCSV écrits dans", DOSSIER.relative_to(ROOT))


if __name__ == "__main__":
    main()
