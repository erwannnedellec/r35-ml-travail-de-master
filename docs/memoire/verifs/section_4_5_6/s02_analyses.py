#!/usr/bin/env python3
"""Section 4.5.6 (extension) — Phase 2 : lectures SHAP conditionnelles (mesures seules).

Lit le cache produit par s01_shap_values.py (SHAP signés H25, config c08) et produit :
  - tableaux/section_4_5_6/t_famille_strate.csv          (Phase 2A + 2B)
  - tableaux/section_4_5_6/t_verifications_variables.csv  (Phase 2C, C1-C8, format tidy)
  - verifs/section_4_5_6/rapport_shap_conditionnel.md     (réponses numérotées + effectifs)

Conventions gelées (Phase 0, validées) :
  - Fenêtre de pointe = CONVENTION B, demi-ouverte {6,7,16,17} (repro EXACTE du test T5
    §4.3.4 : OR 3,058 ; 31,21 % ; 57,11 % ; 5,970 %/2,034 %). Heure = cal_heure_depart.
  - Jour ouvrable = cal_type_jour_3classes == "ouvrable" (fériés exclus).
  - Segment = spatial_segment ; saison de ski = event_is_ski_ouvert == 1.
  - Familles = colonne `famille` du codebook canonique (libellés §4.4.4 / composition §4.5.4).
AUCUNE interprétation métier : mesures et effectifs de strate uniquement.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
TAB = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6"
CODEBOOK = ROOT / "outputs" / "codebook_canonique_ba493568.csv"
CACHE = Path(os.environ["R356_CACHE"]) if "R356_CACHE" in os.environ else DOSSIER / "_cache"

PEAK = {6, 7, 16, 17}          # convention B (demi-ouverte)
LIBELLE_FAMILLE = {            # miroir make_fig_composition_familles.py / _FAMILLE_BASE
    "base_": "Desserte", "cal_": "Calendrier", "event_": "Événement",
    "histo_": "Historique de charge", "horaire_": "Horaire", "id_": "Identifiant",
    "ist_": "Régularité et correspondances", "meteo_": "Météo",
    "resa_": "Réservation de groupe", "simba_": "Structure tarifaire",
    "spatial_": "Contexte spatial", "target_": "Cible", "vmcv_": "Concurrence modale",
}


def load():
    info = json.loads((CACHE / "feats_order.json").read_text())
    feats = info["feats"]
    cb = pd.read_csv(CODEBOOK)
    fam_pref = dict(zip(cb["colonne"], cb["famille"]))
    fam = {f: LIBELLE_FAMILLE[fam_pref[f]] for f in feats}
    data = {}
    for seg in ("bas", "haut"):
        shap = np.load(CACHE / f"shap_signed_{seg}.npy")            # (n,158) float32
        meta = pd.read_parquet(CACHE / f"meta_{seg}.parquet").reset_index(drop=True)
        data[seg] = {"shap": shap, "meta": meta,
                     "idx": {f: i for i, f in enumerate(feats)}}
    return info, feats, fam, data


def strata_masks(meta):
    h = meta["cal_heure_depart"].astype("int64")
    tj = meta["cal_type_jour_3classes"].astype(str)
    mois = meta["cal_mois"].astype("int64")
    ouvrable = tj == "ouvrable"
    peak = h.isin(PEAK)
    m = {
        "pointe_ouvrable": (ouvrable & peak).values,
        "horspointe_ouvrable": (ouvrable & ~peak).values,
        "samedi": (tj == "samedi").values,
        "dimanche_ferie": (tj == "dimanche_ferie").values,
    }
    ski = (meta["event_is_ski_ouvert"] == 1).values
    mai = (~ski) & (mois == 5).values
    jaout = (~ski) & (mois.isin([7, 8])).values
    autres = ~(ski | mai | jaout)
    seas = {"saison_ski": ski, "mai": mai, "juil_aout": jaout, "autres_mois": autres}
    extra = {"weekend": (m["samedi"] | m["dimanche_ferie"]),
             "ouvrable": ouvrable.values, "peak": peak.values,
             "soiree": (h >= 19).values,          # soirée = départ ≥ 19 h (borne incluse)
             "ete": mois.isin([6, 7, 8]).values, "hiver": mois.isin([12, 1, 2]).values}
    return m, seas, extra


def family_mass(shap, feats, fam, mask=None, fam_sizes=None):
    """mean|SHAP| par feature -> masse par famille (somme) + part normalisée + intensité
    par variable (masse / effectif de la famille). Renvoie (DF, n)."""
    s = shap if mask is None else shap[mask]
    cols = ["famille", "shap_abs_mean", "part", "shap_abs_mean_par_variable", "n_variables"]
    if len(s) == 0:
        return pd.DataFrame(columns=cols), 0
    mabs = np.abs(s).mean(axis=0)
    d = pd.DataFrame({"feature": feats, "mabs": mabs})
    d["famille"] = d["feature"].map(fam)
    g = d.groupby("famille")["mabs"].sum().rename("shap_abs_mean").reset_index()
    tot = g["shap_abs_mean"].sum()
    g["part"] = g["shap_abs_mean"] / tot
    g["n_variables"] = g["famille"].map(fam_sizes) if fam_sizes else np.nan
    g["shap_abs_mean_par_variable"] = g["shap_abs_mean"] / g["n_variables"]
    return g.sort_values("shap_abs_mean", ascending=False), len(s)


def ranks(shap, feats):
    mabs = np.abs(shap).mean(axis=0)
    d = pd.DataFrame({"feature": feats, "mean_abs_shap": mabs})
    d = d.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    d["rang"] = d.index + 1
    return d.set_index("feature")


def signed_and_corr(shap, meta, idx, feat, mask=None):
    """mean SHAP signé + Spearman(SHAP signé, valeur) sur les lignes (masquées) à valeur non nulle."""
    col = shap[:, idx[feat]].astype("float64")
    val = meta[feat].astype("float64").values if feat in meta.columns else None
    if mask is not None:
        col = col[mask]
        val = val[mask] if val is not None else None
    mean_signed = float(np.mean(col)) if len(col) else np.nan
    rho = np.nan
    if val is not None:
        ok = ~np.isnan(val)
        if ok.sum() > 10 and np.unique(val[ok]).size > 1 and np.unique(col[ok]).size > 1:
            rho = float(spearmanr(val[ok], col[ok]).statistic)
    return mean_signed, rho, int(len(col))


def fmt(x, n=4):
    return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{n}f}"


DAYTYPE_STRATA = ["pointe_ouvrable", "horspointe_ouvrable", "samedi", "dimanche_ferie"]
SEAS_STRATA = ["saison_ski", "mai", "juil_aout", "autres_mois"]
VMCV = ["vmcv_n_lignes_concurrentes", "vmcv_min_attente_min",
        "vmcv_delta_attente_min", "vmcv_delta_frequence_h"]
HEADWAY = ["ist_headway_avant_min", "ist_headway_apres_min",
           "ist_headway_avant_is_first_of_day", "ist_headway_apres_is_last_of_day"]
TEMP_ENSOL = ["meteo_temperature_h", "meteo_destination_temperature_h",
              "meteo_ensoleillement_min_h", "meteo_destination_ensoleillement_min_h"]
EVENTS_C5 = {"jazz": "event_is_montreux_jazz", "narcisses": "event_is_saison_narcisses",
             "marche_noel": "event_is_marche_noel", "ski": "event_is_ski_ouvert",
             "manifestation_riviera": "event_is_manifestation_riviera"}
POP_C7 = ["spatial_gare_depart_pop_500m_total", "spatial_gare_arrivee_pop_500m_total"]
NEIGE = "meteo_neige_binaire_h"
DENIV = "spatial_denivele_troncon_m"
# Fenêtre d'indisponibilité VMCV CORRIGÉE suite au diagnostic s04 (trou réel des variables
# dynamiques : min_attente/delta_attente/delta_frequence 100 % NaN). Annoncée 2025-09-01→2025-10-13.
WIN0, WIN1 = pd.Timestamp("2025-08-29"), pd.Timestamp("2025-10-15")
WIN_LABEL = "hors_fenetre_indispo_0829_1015"


def main() -> int:
    info, feats, fam, data = load()
    rk = {seg: ranks(data[seg]["shap"], feats) for seg in ("bas", "haut")}
    masks = {seg: strata_masks(data[seg]["meta"]) for seg in ("bas", "haut")}

    # ── Phase 2A + 2B : famille × segment × strate ──────────────────────────
    from collections import Counter
    fam_sizes = Counter(fam[f] for f in feats)          # effectif de chaque famille (158f)
    fam_rows = []

    def emit(seg, stratif, strate, g, n):
        for _, r in g.iterrows():
            fam_rows.append(dict(segment=seg, stratification=stratif, strate=strate, n_obs=n,
                                 famille=r.famille, shap_abs_mean=r.shap_abs_mean, part=r.part,
                                 shap_abs_mean_par_variable=r.shap_abs_mean_par_variable,
                                 n_variables=int(r.n_variables)))

    for seg in ("bas", "haut"):
        shap = data[seg]["shap"]
        emit(seg, "global", "global", *family_mass(shap, feats, fam, None, fam_sizes))
        dmask, smask, _ = masks[seg]
        for st in DAYTYPE_STRATA:                                  # 2B : type de jour
            emit(seg, "type_jour", st, *family_mass(shap, feats, fam, dmask[st], fam_sizes))
        if seg == "haut":                                          # 2B : saison (haut)
            for st in SEAS_STRATA:
                emit(seg, "saison", st, *family_mass(shap, feats, fam, smask[st], fam_sizes))
    fam_df = pd.DataFrame(fam_rows)
    TAB.mkdir(parents=True, exist_ok=True)
    fam_df.to_csv(TAB / "t_famille_strate.csv", index=False)

    # Masse totale moyenne |SHAP| par observation (voyageurs) + effectif, par segment × strate
    # (global + type de jour) — CSV propre pour la légende de figure / la prose du manuscrit.
    masse = (fam_df[fam_df.stratification.isin(["global", "type_jour"])]
             .groupby(["segment", "strate"], sort=False)
             .agg(masse_moy_obs=("shap_abs_mean", "sum"), n_obs=("n_obs", "first"))
             .reset_index())
    masse.to_csv(TAB / "t_masse_par_strate.csv", index=False)

    # ── Phase 2C : C1-C8 ────────────────────────────────────────────────────
    V = []   # lignes tidy pour t_verifications_variables.csv

    def add(check, variable, seg, strate, n_obs, rang=None, mabs=None,
            signed=None, rho=None, part=None, note=""):
        V.append(dict(check=check, variable=variable, segment=seg, strate=strate,
                      n_obs=n_obs, rang=rang, mean_abs_shap=mabs, mean_shap_signe=signed,
                      corr_spearman_valeur=rho, part_famille=part, note=note))

    def R(seg, f):   # (rang, mean_abs_shap) global du segment
        return int(rk[seg].loc[f, "rang"]), float(rk[seg].loc[f, "mean_abs_shap"])

    rep = []   # lignes du rapport md (numérotées)

    # C1 — VMCV / offre bus concurrente
    rep.append("## C1 — VMCV / offre bus concurrente")
    rep.append("_Fenêtre d'indisponibilité VMCV **corrigée suite au diagnostic s04** : "
               "2025-08-29 → 2025-10-15 (trou réel des variables dynamiques ; annoncée 2025-09-01→"
               "2025-10-13). Cf. `note_vmcv_neige.md` §3._")
    b = data["bas"]; hgt = data["haut"]
    bd = data["bas"]["meta"]["base_date"]
    win = ((bd >= WIN0) & (bd <= WIN1)).values
    for f in VMCV:
        rb, mb = R("bas", f); rh, mh = R("haut", f)
        s_all, rho_all, n_all = signed_and_corr(b["shap"], b["meta"], b["idx"], f)
        s_ex, rho_ex, n_ex = signed_and_corr(b["shap"], b["meta"], b["idx"], f, ~win)
        mabs_ex = float(np.abs(b["shap"][~win, b["idx"][f]]).mean())
        add("C1", f, "bas", "H25_complet", n_all, rb, mb, s_all, rho_all)
        add("C1", f, "bas", WIN_LABEL, n_ex, rb, mabs_ex, s_ex, rho_ex,
            note="mean_abs_shap recalculé hors fenêtre réelle (s04) ; rang = rang global H25")
        s_h, rho_h, n_h = signed_and_corr(hgt["shap"], hgt["meta"], hgt["idx"], f)
        add("C1", f, "haut", "H25_complet", n_h, rh, mh, s_h, rho_h, note="contrôle inertie")
        rep.append(f"- **{f}** — bas rang {rb} (|SHAP| {mb:.4f}) ; Spearman(SHAP,valeur)="
                   f"{fmt(rho_all)} ; SHAP signé moyen={fmt(s_all)} (n={n_all}). "
                   f"Hors fenêtre indispo : |SHAP| {mabs_ex:.4f}, Spearman={fmt(rho_ex)}, "
                   f"signé={fmt(s_ex)} (n={n_ex}). Haut : rang {rh}, |SHAP| {mh:.4f} (n={n_h}).")

    # C2 — headway / isolement temporel
    rep.append("\n## C2 — headway / isolement temporel")
    rep.append("_Buckets conditionnés au régime **ouvrable** (`cal_type_jour_3classes==ouvrable`, "
               "hypothèse V5 frein de fréquence). pointe={6,7,16,17} ; soirée = départ ≥ 19 h ; "
               "hors-pointe = ouvrable, hors pointe et hors soirée._")
    for seg in ("bas", "haut"):
        d = data[seg]; dm, sm, ex = masks[seg]
        ouv = ex["ouvrable"]
        buckets = {"pointe_ouvrable": ex["peak"] & ouv,
                   "horspointe_ouvrable": (~ex["peak"] & ~ex["soiree"]) & ouv,
                   "soiree_ouvrable": ex["soiree"] & ouv}
        for f in HEADWAY:
            rg, mb = R(seg, f)
            s_g, rho_g, n_g = signed_and_corr(d["shap"], d["meta"], d["idx"], f)
            add("C2", f, seg, "global", n_g, rg, mb, s_g, rho_g)
            line = [f"- **{f}** — {seg} rang {rg} (|SHAP| {mb:.4f}) ; global signé={fmt(s_g)}, "
                    f"Spearman={fmt(rho_g)} (n={n_g})."]
            for bk, mk in buckets.items():
                s_b, rho_b, n_b = signed_and_corr(d["shap"], d["meta"], d["idx"], f, mk)
                add("C2", f, seg, bk, n_b, rg, None, s_b, rho_b)
                line.append(f" {bk}: signé={fmt(s_b)}, Spearman={fmt(rho_b)} (n={n_b}).")
            rep.append("".join(line))

    # C3 — neige : bas (ski ∩ ouvrable, report hivernal) vs haut (ski ∩ ouvrable ET ski ∩ week-end)
    rep.append("\n## C3 — neige (report hivernal)")
    for seg in ("bas", "haut"):
        d = data[seg]; dm, sm, ex = masks[seg]
        rg, mb = R(seg, NEIGE)
        val = d["meta"][NEIGE].astype("float64").values
        col = d["shap"][:, d["idx"][NEIGE]].astype("float64")
        bases = [("ski_ouvrable", sm["saison_ski"] & ex["ouvrable"])]
        if seg == "haut":                                  # mécanisme haut dominé par le week-end
            bases.append(("ski_weekend", sm["saison_ski"] & ex["weekend"]))
        for bname, base in bases:
            for suff, sub in (("neige1", base & (val == 1)), ("neige0", base & (val == 0))):
                n = int(sub.sum()); ms = float(col[sub].mean()) if n else np.nan
                add("C3", NEIGE, seg, f"{bname}_{suff}", n, rg, mb, ms, None)
            n_all = int(base.sum()); s_all = float(col[base].mean()) if n_all else np.nan
            n1 = int((base & (val == 1)).sum()); n0 = int((base & (val == 0)).sum())
            s1 = float(col[base & (val == 1)].mean()) if n1 else np.nan
            s0 = float(col[base & (val == 0)].mean()) if n0 else np.nan
            rep.append(f"- **{seg} / {bname}** (n={n_all}) : SHAP signé moyen={fmt(s_all)} ; "
                       f"neige=1 signé={fmt(s1)} (n={n1}) ; neige=0 signé={fmt(s0)} (n={n0}) ; "
                       f"rang {rg}, |SHAP| {mb:.4f}.")

    # C4 — température & ensoleillement sur le haut, été/hiver
    rep.append("\n## C4 — température & ensoleillement (haut), été/hiver")
    d = data["haut"]; dm, sm, ex = masks["haut"]
    for f in TEMP_ENSOL:
        rg, mb = R("haut", f)
        for lab, mk in (("ete", ex["ete"]), ("hiver", ex["hiver"])):
            s_b, rho_b, n_b = signed_and_corr(d["shap"], d["meta"], d["idx"], f, mk)
            add("C4", f, "haut", lab, n_b, rg, mb, s_b, rho_b)
        s_e, rho_e, n_e = signed_and_corr(d["shap"], d["meta"], d["idx"], f, ex["ete"])
        s_h, rho_h, n_h = signed_and_corr(d["shap"], d["meta"], d["idx"], f, ex["hiver"])
        rep.append(f"- **{f}** — haut rang {rg} (|SHAP| {mb:.4f}). "
                   f"Été: signé={fmt(s_e)}, Spearman={fmt(rho_e)} (n={n_e}). "
                   f"Hiver: signé={fmt(s_h)}, Spearman={fmt(rho_h)} (n={n_h}).")

    # C5 — événements (jazz, narcisses, marchés, ski)
    rep.append("\n## C5 — variables événementielles")
    for lab, f in EVENTS_C5.items():
        for seg in ("bas", "haut"):
            d = data[seg]
            rg, mb = R(seg, f)
            act = (d["meta"][f] == 1).values
            col = d["shap"][:, d["idx"][f]].astype("float64")
            s_all = float(col.mean()); s_act = float(col[act].mean()) if act.sum() else np.nan
            add("C5", f, seg, "global", int(len(col)), rg, mb, s_all, None)
            add("C5", f, seg, "jours_actifs", int(act.sum()), rg, mb, s_act, None,
                note=f"événement={lab}")
            rep.append(f"- **{lab}** ({f}) — {seg} rang {rg} (|SHAP| {mb:.4f}) ; "
                       f"signé global={fmt(s_all)} ; jours actifs (n={int(act.sum())}) signé={fmt(s_act)}.")

    # C6 — dénivelé, deux segments
    rep.append("\n## C6 — dénivelé (deux segments)")
    for seg in ("bas", "haut"):
        d = data[seg]
        rg, mb = R(seg, DENIV)
        s_g, rho_g, n_g = signed_and_corr(d["shap"], d["meta"], d["idx"], DENIV)
        add("C6", DENIV, seg, "global", n_g, rg, mb, s_g, rho_g)
        rep.append(f"- **{seg}** — rang {rg}/158 (|SHAP| {mb:.4f}) ; signé moyen={fmt(s_g)}, "
                   f"Spearman(SHAP,dénivelé)={fmt(rho_g)} (n={n_g}).")

    # C7 — population des bassins
    rep.append("\n## C7 — population des bassins (500 m)")
    for f in POP_C7:
        for seg in ("bas", "haut"):
            d = data[seg]
            rg, mb = R(seg, f)
            s_g, rho_g, n_g = signed_and_corr(d["shap"], d["meta"], d["idx"], f)
            add("C7", f, seg, "global", n_g, rg, mb, s_g, rho_g)
            rep.append(f"- **{f}** — {seg} rang {rg} (|SHAP| {mb:.4f}) ; signé={fmt(s_g)}, "
                       f"Spearman={fmt(rho_g)} (n={n_g}).")

    # C8 — famille historique : part de contribution par régime
    rep.append("\n## C8 — famille « Historique de charge » : part par régime")
    for seg in ("bas", "haut"):
        d = data[seg]; dm, sm, ex = masks[seg]
        regimes = {"pointe_ouvrable": dm["pointe_ouvrable"],
                   "horspointe_ouvrable": dm["horspointe_ouvrable"],
                   "weekend": ex["weekend"]}
        for lab, mk in regimes.items():
            g, n = family_mass(d["shap"], feats, fam, mk)
            row = g[g["famille"] == "Historique de charge"]
            part = float(row["part"].iloc[0]); mass = float(row["shap_abs_mean"].iloc[0])
            add("C8", "famille:Historique de charge", seg, lab, n, None, mass, None, None, part)
            rep.append(f"- **{seg} / {lab}** (n={n}) : part famille historique="
                       f"{part:.4f} (masse |SHAP| {mass:.4f}).")

    verif_df = pd.DataFrame(V, columns=["check", "variable", "segment", "strate", "n_obs",
                                        "rang", "mean_abs_shap", "mean_shap_signe",
                                        "corr_spearman_valeur", "part_famille", "note"])
    verif_df.to_csv(TAB / "t_verifications_variables.csv", index=False)

    write_report(info, feats, fam, data, masks, rk, fam_df, rep)
    print(f"[OK] t_famille_strate.csv ({len(fam_df)} lignes), "
          f"t_verifications_variables.csv ({len(verif_df)} lignes), rapport écrit.")
    return 0


def _fam_table_md(fam_df, seg, stratif, strata):
    piv = (fam_df[(fam_df.segment == seg) & (fam_df.stratification.isin(["global", stratif]))]
           .pivot_table(index="famille", columns="strate", values="part"))
    cols = [c for c in (["global"] + strata) if c in piv.columns]
    piv = piv[cols].sort_values("global", ascending=False)
    lines = ["| Famille | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for famn, r in piv.iterrows():
        lines.append("| " + famn + " | " + " | ".join(f"{r[c]*100:.1f} %" if pd.notna(r[c]) else "—" for c in cols) + " |")
    return "\n".join(lines)


def write_report(info, feats, fam, data, masks, rk, fam_df, rep):
    eff = {}
    for seg in ("bas", "haut"):
        dm, sm, ex = masks[seg]
        eff[seg] = {**{k: int(v.sum()) for k, v in dm.items()},
                    **{k: int(v.sum()) for k, v in sm.items()}, "total": len(data[seg]["meta"])}
    out = []
    out.append("# Section 4.5.6 — Lectures SHAP conditionnelles (mesures)\n")
    out.append("> Généré par `s02_analyses.py` sur le cache `s01_shap_values.py`. "
               "Modèles gelés e4ddfccd/df6a11c5, dataset ba493568, H25. TreeSHAP exact "
               "(pred_contribs, tree_path_dependent, sans background — config c08). "
               "Aucune interprétation métier : mesures et effectifs seuls.\n")
    out.append("## Phase 0 — conventions retenues (rappel)\n")
    out.append(f"- Config SHAP : {info['shap_config']}")
    out.append(f"- Fenêtre de pointe : {info['peak_convention']}")
    out.append("- Jour ouvrable = `cal_type_jour_3classes == \"ouvrable\"` (fériés exclus).")
    out.append("- Familles = colonne `famille` du codebook canonique (9 familles sur 158f).")
    out.append(f"- Effectifs strates BAS : {eff['bas']}")
    out.append(f"- Effectifs strates HAUT : {eff['haut']}\n")
    out.append("## Phase 2A — Référence agrégée : part de la masse |SHAP| par famille\n")
    out.append("**BAS**\n\n" + _fam_table_md(fam_df, "bas", "type_jour", []) + "\n")
    out.append("\n**HAUT**\n\n" + _fam_table_md(fam_df, "haut", "type_jour", []) + "\n")
    out.append("\n## Phase 2B — Part par famille × strate type de jour\n")
    out.append("**BAS**\n\n" + _fam_table_md(fam_df, "bas", "type_jour", DAYTYPE_STRATA) + "\n")
    out.append("\n**HAUT**\n\n" + _fam_table_md(fam_df, "haut", "type_jour", DAYTYPE_STRATA) + "\n")
    out.append("\n**HAUT — stratification saisonnière**\n\n"
               + _fam_table_md(fam_df, "haut", "saison", SEAS_STRATA) + "\n")
    out.append("\n# Phase 2C — Vérifications ciblées\n")
    out.append("\n".join(rep))
    inter = TAB / "t_interactions_haut.csv"
    if inter.exists():
        di = pd.read_csv(inter)
        nech = int(di["n_echantillon"].iloc[0]) if "n_echantillon" in di.columns else None
        out.append("\n# Phase 2D (optionnel, INDICATIF) — interactions SHAP sur le HAUT\n")
        out.append(f"_Échantillon **{nech} obs HAUT (graine 42)** — réduit par coût "
                   f"(`pred_interactions` ≈ 2,15 s/obs ; 20 000 ≈ 12 h, infaisable). Résultat "
                   f"indicatif (classement des paires), non une estimation de précision. Convention : "
                   f"Phi_ij symétrique rapporté tel quel ; effet de paire complet = 2·Phi_ij (hors "
                   f"diagonale). Source : `s03_interactions.py`._\n")
        for rv in di["row_var"].unique():
            sub = di[(di.row_var == rv) & (di.cal_var != "_effet_principal_diagonal")] \
                .sort_values("mean_abs_interaction", ascending=False).head(6)
            items = "; ".join(f"{r.cal_var}={r.mean_abs_interaction:.4f}" for r in sub.itertuples())
            diag = di[(di.row_var == rv) & (di.cal_var == "_effet_principal_diagonal")]
            dval = f"{diag['mean_abs_interaction'].iloc[0]:.4f}" if len(diag) else "n/d"
            out.append(f"- **{rv}** (effet principal diagonal={dval} ; top |Phi_ij| calendrier) : {items}")
    out.append("\n" + AUDIT_CONVENTIONS)
    (Path(__file__).resolve().parent / "rapport_shap_conditionnel.md").write_text(
        "\n".join(out) + "\n")


AUDIT_CONVENTIONS = """# Annexe A — Audit des conventions de fenêtre de pointe (inventaire, aucune correction)

Trois conventions coexistent dans le dépôt sous des libellés proches. Reproductions
sanctionnées par `s00_verif_convention_pointe.py` (grain tronçon, H22-H25 ;
`t_verif_convention_pointe.csv`), jour ouvrable = `cal_type_jour_3classes==ouvrable` :

| Convention | Heures (départ) | Bas exposition | Bas occurrence | Bas OR | Haut pointe (tous jours) |
|---|---|---:|---:|---:|---:|
| A — 3 h {6,7,8,16,17,18} | bornes incluses | 46,60 % | 74,26 % | 3,434 | 12,84 % |
| **B — 2 h {6,7,16,17}** | demi-ouverte (**RETENUE**) | **31,21 %** | **57,11 %** | **3,058** | **11,43 %** |
| C — large {5,6,7,8,16,17,18,19} | 5-8 / 16-19 | 54,73 % | 75,31 % | 2,594 | 13,02 % |

**La convention B est celle du manuscrit §4.3.4.** Les chiffres têtes du §4.3.4 —
**57,1 %** (surcharges bas en pointe parmi les ouvrables), **11,4 %** (surcharges haut en
pointe, tous jours), **85,4 %** (surcharges bas en jours ouvrables), **44,2 %** (surcharges
haut en jours ouvrables) — sont reproduits EXACTEMENT sous B (s00 : 57,11 / 11,43 / 85,38 /
44,18 ; les deux derniers sont des parts par type de jour, indépendantes de la fenêtre).
Le **11,4 %** du manuscrit correspond à B (11,43 %), **pas** à C (13,02 %) : aucune
incohérence de convention dans le texte du §4.3.4.

| Convention | Code | Chiffres qui en dépendent | Localisation | Features modèle |
|---|---|---|---|---|
| **A — 3 h** | `fig_profils_horaires.py` (POINTE, BANDES) ; `compute_enrichissement_ba493568.py` (POINTE_OUV) | **Figure 7 §4.3.2** (surlignage des bandes de pointe) ; part de charge en pointe **51,9 % bas / 30,5 % haut** (33,0/47,8 ; 23,7/27,9) ; **74,26 %** surcharges bas ouvrable en pointe et **88,26 %** surcharges haut en milieu de journée (10-16 h) | `verif_432_dualite.md`, `rapport_enrichissement_ba493568.md` B2b (**dépôt** ; la figure 7 est au manuscrit) | **AUCUNE** |
| **B — 2 h (RETENUE)** | `resultats_tests_4_3.md`, `t5_exposition_surcharge.csv`, `t5b_haut_et_raccords.csv` | **§4.3.4 manuscrit** : 57,1 % / 11,4 % / 85,4 % / 44,2 % ; OR 3,058 ; T2 pondéré 35,9 %/21,5 % | manuscrit §4.3.4 + tests dépôt | AUCUNE |
| **C — large** | `build_istdaten_ponctualite.py` (HEURES_POINTE_*) ; `verif_434_cible.py` (POINTE_MATIN/SOIR) | **71,7 %** (surcharges bas tous jours, fenêtre large) ; **13,0 %** (haut, fenêtre large) | **fichiers de vérification du dépôt uniquement** (`t5_exposition_surcharge.csv` occurrence_tous_jours_large ; `resultats_tests_4_3.md`) — **PAS** dans le manuscrit §4.3.4 | `ist_vevey_n_arrivees_pointe_j` bâtie sous C **mais NON jointe dans `ml_dataset`** → aucune |

**Constat d'audit (sans correction).** (i) Le manuscrit §4.3.4 est cohérent avec B ; les
valeurs 71,7 %/13,0 % relèvent de la fenêtre large C et **vivent dans les fichiers de
vérification du dépôt, non dans le texte** — l'attribution antérieure au §4.3.4 était
erronée. (ii) La figure 7 (§4.3.2) surligne la fenêtre A (3 h) ; les variables `ist_` de
ponctualité en 5-8/16-19 relèvent de C. (iii) **Aucune des 158 variables du modèle gelé ne
dépend d'une convention de fenêtre de pointe** : le choix A/B/C n'affecte que des
statistiques descriptives et un agrégat istdaten intermédiaire non mobilisé dans
`ml_dataset` ; le choix de B pour les strates SHAP est donc sans effet sur le modèle. La
décision d'harmonisation des conventions descriptives est explicitement hors périmètre."""


if __name__ == "__main__":
    sys.exit(main())
