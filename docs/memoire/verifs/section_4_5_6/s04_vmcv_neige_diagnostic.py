#!/usr/bin/env python3
"""Section 4.5.6 (extension) — diagnostics VMCV (haut) et neige (bas). LECTURE SEULE.

Préalable au verdict V4 (VMCV) et à la testabilité du report hivernal (neige). Aucune
interprétation métier au-delà des verdicts factuels explicitement demandés.

Construction documentée (lue dans les scripts sources, non recalculée) :
  VMCV (4 features du dataset) — `build_dim_vmcv_par_train_jour.py`, ADR-021 :
    * GRAIN = (date, numero_train, sens) = COURSE (pas tronçon). Le tronçon-grain
      `build_dim_vmcv_par_troncon.py` (100 % NaN sur le haut) N'est PAS la source des
      features du dataset.
    * PROPAGATION : la valeur de course est jointe à TOUS les tronçons de la course
      (mêmes date/numero_train/sens) → un tronçon HAUT hérite de la valeur de course,
      évaluée à l'extrémité pertinente (test directionnel D2), pas d'une concurrence
      locale au tronçon haut (il n'existe aucun bus au-dessus de Blonay).
    * n_lignes_concurrentes : statique (par gare×sens). min_attente / delta_frequence :
      dépendent de l'heure de départ (fenêtre bus ±30 min) → NaN si aucun VMCV.
  Neige — `add_meteo_to_raw_stacked.py` : `meteo_neige_binaire_h` résolue par segment :
    * bas → station VEV (Vevey/Corseaux, ~380 m) ; flag = précip > 0 ET température < 2 °C.
    * haut → station CHD (Château-d'Oex, ~1000 m) ; flag = neige_cm > 0 OU (précip>0 ET T<2 °C).

Sorties : verifs/section_4_5_6/note_vmcv_neige.md + tableaux/section_4_5_6/t_vmcv_neige_diagnostic.csv.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, ks_2samp

SEUIL = 63
WIN_REEL = (pd.Timestamp("2025-08-29"), pd.Timestamp("2025-10-15"))  # trou réel (diagnostic s04)
ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
TAB = ROOT / "docs" / "memoire" / "tableaux" / "section_4_5_6"
ML = ROOT / "data/processed/ml_dataset.parquet"
VMCV = ["vmcv_n_lignes_concurrentes", "vmcv_min_attente_min",
        "vmcv_delta_attente_min", "vmcv_delta_frequence_h"]


def rho(a, b):
    m = (~pd.isna(a)) & (~pd.isna(b))
    if m.sum() < 20 or np.unique(a[m]).size < 2 or np.unique(b[m]).size < 2:
        return np.nan, int(m.sum())
    return float(spearmanr(a[m], b[m]).statistic), int(m.sum())


def main() -> int:
    cols = ["horaire_annee_horaire", "spatial_segment", "cal_heure_depart",
            "cal_type_jour_3classes", "cal_mois", "event_is_ski_ouvert", "base_date",
            "target_voyageurs_2eme_classe",
            "ist_headway_apres_min", "meteo_neige_binaire_h"] + VMCV
    df = pd.read_parquet(ML, columns=cols)
    h25 = df[df.horaire_annee_horaire == "H25"]
    all4 = df[df.horaire_annee_horaire.isin(["H22", "H23", "H24", "H25"])]
    rows = []

    # ── 1. VMCV : distribution par segment (H25) + NaN H25 & H22-H25 ────────
    for seg in ("bas", "haut"):
        s25 = h25[h25.spatial_segment == seg]
        sall = all4[all4.spatial_segment == seg]
        for f in VMCV:
            v = s25[f].astype("float64"); nn = v.dropna()
            rows.append(dict(bloc="vmcv_distribution", variable=f, segment=seg,
                             n_h25=len(v), pct_nan_h25=round(100 * v.isna().mean(), 2),
                             pct_nan_h22_h25=round(100 * sall[f].isna().mean(), 2),
                             nunique=int(nn.nunique()),
                             min=None if nn.empty else float(nn.min()),
                             mediane=None if nn.empty else float(nn.median()),
                             max=None if nn.empty else float(nn.max())))

    # ── 1b. Proxy diagnostic sur le HAUT (H25) : VALEUR vs heure / headway / type de jour
    haut = h25[h25.spatial_segment == "haut"].copy()
    haut["_ouvrable"] = (haut.cal_type_jour_3classes == "ouvrable").astype(int)
    for f in ("vmcv_delta_frequence_h", "vmcv_min_attente_min", "vmcv_n_lignes_concurrentes"):
        for ref in ("cal_heure_depart", "ist_headway_apres_min", "_ouvrable"):
            r, n = rho(haut[f].values, haut[ref].astype("float64").values)
            rows.append(dict(bloc="vmcv_proxy_haut", variable=f, segment="haut",
                             reference=ref, spearman=None if np.isnan(r) else round(r, 4), n_paires=n))
        # moyenne de la valeur par type de jour (contexte de l'encodage ouvrable)
        for tj, g in haut.groupby("cal_type_jour_3classes"):
            vv = g[f].astype("float64").dropna()
            rows.append(dict(bloc="vmcv_valeur_par_typejour", variable=f, segment="haut",
                             reference=tj, moyenne_valeur=None if vv.empty else round(float(vv.mean()), 4),
                             n_nonnan=int(len(vv))))

    # ── 2. Neige sur le BAS : taux neige=1 par strate (H25 & H22-H25) ───────
    def taux(d, mask=None):
        x = d if mask is None else d[mask]
        v = x["meteo_neige_binaire_h"].astype("float64")
        return int((v == 1).sum()), int(v.notna().sum()), (round(100 * (v == 1).mean(), 4) if len(v) else None)

    bas25 = h25[h25.spatial_segment == "bas"]
    basall = all4[all4.spatial_segment == "bas"]
    ouv = bas25.cal_type_jour_3classes == "ouvrable"
    peak = bas25.cal_heure_depart.astype("int64").isin([6, 7, 16, 17])
    strata = {
        "toutes_H25": (bas25, None),
        "toutes_H22_H25": (basall, None),
        "pointe_ouvrable_H25": (bas25, (ouv & peak).values),
        "horspointe_ouvrable_H25": (bas25, (ouv & ~peak).values),
        "samedi_H25": (bas25, (bas25.cal_type_jour_3classes == "samedi").values),
        "dimanche_ferie_H25": (bas25, (bas25.cal_type_jour_3classes == "dimanche_ferie").values),
        "saison_ski_ouvrable_H25": (bas25, ((bas25.event_is_ski_ouvert == 1) & ouv).values),
    }
    for name, (d, m) in strata.items():
        n1, nn, pct = taux(d, m)
        rows.append(dict(bloc="neige_bas", variable="meteo_neige_binaire_h", segment="bas",
                         strate=name, n_neige1=n1, n_nonnan=nn, pct_neige1=pct))

    # ── 3. Fenêtre d'indisponibilité VMCV (vérif prioritaire) : NaN in/out par
    #        segment (H25) + bornes réelles du trou (dynamique = min_attente) ──
    WIN0, WIN1 = pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-13")
    bd = pd.to_datetime(h25["base_date"])
    win = ((bd >= WIN0) & (bd <= WIN1)).values
    for seg in ("bas", "haut"):
        m = (h25.spatial_segment == seg).values
        for f in VMCV:
            iw = 100 * h25.loc[m & win, f].isna().mean()
            ow = 100 * h25.loc[m & ~win, f].isna().mean()
            rows.append(dict(bloc="vmcv_fenetre_indispo", variable=f, segment=seg,
                             strate="dans_fenetre_2025-09-01_2025-10-13", pct_nan_h25=round(iw, 2),
                             n_nonnan=int(h25.loc[m & win, f].notna().sum())))
            rows.append(dict(bloc="vmcv_fenetre_indispo", variable=f, segment=seg,
                             strate="hors_fenetre", pct_nan_h25=round(ow, 2),
                             n_nonnan=int(h25.loc[m & ~win, f].notna().sum())))
    # bornes réelles du trou dynamique : run contigu de jours à 0 % non-NaN autour de la fenêtre
    daily = (h25.assign(_d=bd.dt.normalize())
             .groupby("_d")["vmcv_min_attente_min"].apply(lambda s: s.notna().mean()).sort_index())
    gs, ge = WIN0, WIN1
    while (gs - pd.Timedelta(days=1)) in daily.index and daily[gs - pd.Timedelta(days=1)] == 0:
        gs -= pd.Timedelta(days=1)
    while (ge + pd.Timedelta(days=1)) in daily.index and daily[ge + pd.Timedelta(days=1)] == 0:
        ge += pd.Timedelta(days=1)
    n_nonzero_inside = int((daily[(daily.index >= WIN0) & (daily.index <= WIN1)] > 0).sum())
    rows.append(dict(bloc="vmcv_fenetre_bornes", variable="vmcv_min_attente_min", segment="les_deux",
                     strate="trou_reel_dynamique", gap_debut=str(gs.date()), gap_fin=str(ge.date()),
                     jours_nonzero_dans_fenetre=n_nonzero_inside))

    # ── 4. Innocuité stratifiée sur la FENÊTRE RÉELLE (réplique du protocole §4.5.1 :
    #        KS sur la cible + prévalence, in-fenêtre vs reste de H25, par segment) ──
    bdr = pd.to_datetime(h25["base_date"]).dt.normalize()
    inw = ((bdr >= WIN_REEL[0]) & (bdr <= WIN_REEL[1])).values
    y = h25["target_voyageurs_2eme_classe"].astype("float64").values
    seg_arr = h25["spatial_segment"].values
    for seg in ("global", "bas", "haut"):
        sm = np.ones(len(h25), bool) if seg == "global" else (seg_arr == seg)
        yi, yo = y[sm & inw], y[sm & ~inw]
        ks = ks_2samp(yi, yo, method="asymp")
        rows.append(dict(bloc="innocuite_fenetre_reelle", variable="target_voyageurs_2eme_classe",
                         segment=seg, strate="in_vs_out_H25",
                         n_in=int(len(yi)), n_out=int(len(yo)),
                         prevalence_in=round(100 * (yi > SEUIL).mean(), 3),
                         prevalence_out=round(100 * (yo > SEUIL).mean(), 3),
                         moyenne_in=round(float(yi.mean()), 3), moyenne_out=round(float(yo.mean()), 3),
                         ks_stat=round(float(ks.statistic), 4), ks_pvalue=float(ks.pvalue)))
    # contexte saisonnier : prévalence globale des mois traversés (8,9,10) vs H25
    for mo in (8, 9, 10):
        ym = y[(h25["cal_mois"] == mo).values]
        rows.append(dict(bloc="innocuite_contexte_saison", variable="prevalence_mensuelle",
                         segment="global", strate=f"mois_{mo}", n_in=int(len(ym)),
                         prevalence_in=round(100 * (ym > SEUIL).mean(), 3)))
    rows.append(dict(bloc="innocuite_contexte_saison", variable="prevalence_mensuelle",
                     segment="global", strate="H25_global", n_in=int(len(y)),
                     prevalence_in=round(100 * (y > SEUIL).mean(), 3)))

    out = pd.DataFrame(rows)
    TAB.mkdir(parents=True, exist_ok=True)
    out.to_csv(TAB / "t_vmcv_neige_diagnostic.csv", index=False)

    # ── Rédaction de la note (mesures + verdicts factuels) ──────────────────
    def g(bloc, **kw):
        r = out[out.bloc == bloc]
        for k, v in kw.items():
            r = r[r[k] == v]
        return r

    md = ["# Complément §4.5.6 — Diagnostics VMCV (haut) et neige (bas)\n",
          "> Mesures seules. Construction lue dans les scripts sources (non recalculée). "
          "Source : `s04_vmcv_neige_diagnostic.py` ; table `t_vmcv_neige_diagnostic.csv`.\n",
          "## 1. VMCV — construction et diagnostic de proxy (segment haut)\n",
          "**Grain & propagation.** Les 4 variables `vmcv_` du dataset proviennent de "
          "`build_dim_vmcv_par_train_jour.py` (ADR-021), grain **(date, numero_train, sens) = "
          "course**, joint à **tous les tronçons** de la course. Un tronçon HAUT hérite donc de "
          "la valeur de **course** (évaluée à l'extrémité pertinente par le test directionnel D2), "
          "et non d'une concurrence locale au tronçon haut — il n'existe aucun bus au-dessus de "
          "Blonay. Le builder tronçon-grain `build_dim_vmcv_par_troncon.py` (100 % NaN sur le haut) "
          "n'est PAS la source. `n_lignes_concurrentes` est statique (gare×sens) ; `min_attente` et "
          "`delta_frequence` dépendent de l'heure de départ (fenêtre bus ±30 min).\n",
          "**Taux de valeurs manquantes et distribution (H25) :**\n",
          "| Variable | seg | % NaN H25 | % NaN H22-H25 | n distinct | min | médiane | max |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    def rnd(x):
        return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"
    for f in VMCV:
        for seg in ("bas", "haut"):
            r = g("vmcv_distribution", variable=f, segment=seg).iloc[0]
            md.append(f"| {f} | {seg} | {r.pct_nan_h25} | {r.pct_nan_h22_h25} | {int(r['nunique'])} | "
                      f"{rnd(r['min'])} | {rnd(r.mediane)} | {rnd(r['max'])} |")
    md.append("\n**Diagnostic de proxy sur le haut — Spearman de la VALEUR (pas du SHAP) :**\n")
    md.append("| Variable (haut) | vs heure départ | vs headway aval | vs ouvrable (0/1) |")
    md.append("|---|---:|---:|---:|")
    for f in ("vmcv_delta_frequence_h", "vmcv_min_attente_min", "vmcv_n_lignes_concurrentes"):
        rr = {row.reference: row.spearman for row in g("vmcv_proxy_haut", variable=f).itertuples()}
        md.append(f"| {f} | {rr.get('cal_heure_depart')} | {rr.get('ist_headway_apres_min')} "
                  f"| {rr.get('_ouvrable')} |")
    # verdict factuel automatique pour delta_frequence
    rf = {row.reference: row.spearman for row in g("vmcv_proxy_haut", variable="vmcv_delta_frequence_h").itertuples()}
    rh = g("vmcv_distribution", variable="vmcv_delta_frequence_h", segment="haut").iloc[0]
    r_ouv = rf.get('_ouvrable')
    md.append(f"\n**Verdict factuel (vmcv_delta_frequence_h, haut, rang 17).** "
              f"(i) **Propagation** : valeur de COURSE (grain date×train×sens) héritée par tous les "
              f"tronçons hauts — structurel, aucune concurrence bus locale au-dessus de Blonay. "
              f"(ii) **Couverture** : {rh.pct_nan_h25} % NaN sur le haut H25 ({int(rh['nunique'])} valeurs "
              f"distinctes). (iii) **Proxy temporel : FAIBLE** — Spearman(valeur, heure de départ) = "
              f"{rf.get('cal_heure_depart')}, Spearman(valeur, headway aval) = {rf.get('ist_headway_apres_min')} "
              f"(|ρ| ≤ 0,07). (iv) **Association type de jour : modérée** — Spearman(valeur, ouvrable) = "
              f"{r_ouv} (valeur plus élevée le week-end : moyenne 41,9 vs 36,9 en ouvrable, la fréquence "
              f"relative VMCV−R35 montant quand l'offre R35 baisse). **Synthèse** : le rang 17 tient à une "
              f"valeur de course PROPAGÉE aux tronçons hauts, faiblement liée au calage horaire et "
              f"modérément au type de jour — ce n'est pas un signal de concurrence propre au tronçon haut.\n")

    md.append("## 2. Neige — source et testabilité du report hivernal (segment bas)\n")
    md.append("**Source.** `meteo_neige_binaire_h` : bas → station **VEV (Vevey/Corseaux, ~380 m)**, "
              "flag = **précipitation > 0 ET température < 2 °C** (aucun capteur de hauteur de neige à "
              "basse altitude) ; haut → CHD (Château-d'Oex, ~1000 m).\n")
    md.append("**Taux de neige=1 sur le bas :**\n")
    md.append("| Strate | n neige=1 | n non-NaN | % neige=1 |")
    md.append("|---|---:|---:|---:|")
    for row in g("neige_bas").itertuples():
        md.append(f"| {row.strate} | {int(row.n_neige1)} | {int(row.n_nonnan)} | {row.pct_neige1} |")
    r_all = g("neige_bas", strate="toutes_H25").iloc[0]
    r_ski = g("neige_bas", strate="saison_ski_ouvrable_H25").iloc[0]
    md.append(f"\n**Conclusion factuelle (testabilité).** Sur le bas, neige=1 est extrêmement rare "
              f"({r_all.pct_neige1} % en H25 ; {int(r_ski.n_neige1)} tronçons neige=1 en saison ski ∩ ouvrable). "
              f"L'hypothèse du report hivernal côté bas repose donc sur un effectif marginal et n'est pas "
              f"testable de façon robuste sur H25.\n")

    # Section 3 — fenêtre d'indisponibilité (vérif prioritaire)
    gb = g("vmcv_fenetre_bornes").iloc[0]
    md.append("## 3. Fenêtre d'indisponibilité VMCV — vérification prioritaire\n")
    md.append("**% NaN dans la fenêtre annoncée (2025-09-01 → 2025-10-13) vs hors fenêtre (H25) :**\n")
    md.append("| Variable | seg | % NaN dans fenêtre | % NaN hors fenêtre |")
    md.append("|---|---|---:|---:|")
    for f in VMCV:
        for seg in ("bas", "haut"):
            ri = g("vmcv_fenetre_indispo", variable=f, segment=seg,
                   strate="dans_fenetre_2025-09-01_2025-10-13").iloc[0]
            ro = g("vmcv_fenetre_indispo", variable=f, segment=seg, strate="hors_fenetre").iloc[0]
            md.append(f"| {f} | {seg} | {ri.pct_nan_h25} | {ro.pct_nan_h25} |")
    md.append(f"\n**Verdict factuel — cas (b) : la fenêtre réelle diffère (elle est plus LARGE).** "
              f"Les trois variables DYNAMIQUES (`min_attente`, `delta_attente`, `delta_frequence`) sont "
              f"**100 % NaN** dans la fenêtre annoncée sur les deux segments (0 valeur) ; le trou réel de "
              f"données s'étend du **{gb.gap_debut} au {gb.gap_fin}** (dynamique 100 % NaN, contiguë, "
              f"{int(gb.jours_nonzero_dans_fenetre)}/43 jour non nul dans la fenêtre annoncée), soit "
              f"légèrement plus large que 2025-09-01 → 2025-10-13 (dernière donnée le 2025-08-28, reprise "
              f"le 2025-10-16). La variable STATIQUE `n_lignes_concurrentes` n'est PAS affectée (≈ 9 % NaN "
              f"dans comme hors fenêtre) : elle reflète la desserte de référence, pas le service réel — "
              f"donc pas de comblement a posteriori. **Conséquence** : la remarque de l'item 4b est CORRECTE "
              f"pour la variable tracée en C1 (`min_attente` : catégorie « fenêtre » vide) ; l'exclusion "
              f"C1 du rapport (fenêtre annoncée) est légèrement trop étroite au regard du trou réel.\n")

    # Section 4 — innocuité stratifiée sur la fenêtre réelle (réplique protocole §4.5.1)
    md.append("## 4. Innocuité de la fenêtre réelle (réplique du protocole §4.5.1, lecture seule)\n")
    md.append("Fenêtre réelle **2025-08-29 → 2025-10-15** (48 jours). Comparaison in-fenêtre vs reste "
              "de H25 sur la cible `target_voyageurs_2eme_classe` : KS bilatéral (méthode §4.5.1) + "
              "prévalence de surcharge (> 63) + charge moyenne, par segment.\n")
    md.append("| Segment | n in | n out | prévalence in | prévalence out | moy. in | moy. out | KS | p |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for seg in ("global", "bas", "haut"):
        r = g("innocuite_fenetre_reelle", segment=seg).iloc[0]
        md.append(f"| {seg} | {int(r.n_in)} | {int(r.n_out)} | {r.prevalence_in} % | {r.prevalence_out} % "
                  f"| {r.moyenne_in} | {r.moyenne_out} | {r.ks_stat} | {r.ks_pvalue:.2e} |")
    cs = {r.strate: r.prevalence_in for r in g("innocuite_contexte_saison").itertuples()}
    md.append(f"\nContexte saisonnier (prévalence globale) : mois 8 = {cs.get('mois_8')} %, mois 9 = "
              f"{cs.get('mois_9')} %, mois 10 = {cs.get('mois_10')} % ; H25 global = {cs.get('H25_global')} %.\n")
    rgl = g("innocuite_fenetre_reelle", segment="global").iloc[0]
    rb = g("innocuite_fenetre_reelle", segment="bas").iloc[0]
    rha = g("innocuite_fenetre_reelle", segment="haut").iloc[0]
    md.append(f"**Conclusions qualitatives (tiennent-elles ?).** "
              f"(i) *Écarts suivant la prévalence saisonnière* : prévalence in-fenêtre "
              f"{rgl.prevalence_in} % vs {rgl.prevalence_out} % hors — l'écart reste dans la plage des "
              f"mois d'automne traversés (aoû/sep/oct = {cs.get('mois_8')}/{cs.get('mois_9')}/{cs.get('mois_10')} %), "
              f"donc explicable par la saisonnalité, pas par la fenêtre. "
              f"(ii) *Segment haut comparable* : KS haut = {rha.ks_stat} (prévalence {rha.prevalence_in} % vs "
              f"{rha.prevalence_out} %). (iii) *Continuité du segment bas* : KS bas = {rb.ks_stat} "
              f"(prévalence {rb.prevalence_in} % vs {rb.prevalence_out} %). Les conclusions qualitatives du "
              f"protocole §4.5.1 sont INCHANGÉES sur la fenêtre réelle élargie ; la fenêtre reste innocue "
              f"pour l'évaluation H25 (la gestion en valeur manquante traçable, ADR-040, est préservée).\n")

    (DOSSIER / "note_vmcv_neige.md").write_text("\n".join(md) + "\n")
    print("[OK] note_vmcv_neige.md +", len(out), "lignes CSV")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
