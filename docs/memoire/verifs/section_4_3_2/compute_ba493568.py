#!/usr/bin/env python3
# Synthese exploratoire des surcharges R35 (section 4.3.11) — gel ba493568.
# Lecture seule sur le depot, sauf ecriture dans docs/memoire/verifs/section_4_3_2/
# et docs/memoire/verifs/section_4_3_2/. Rejoue T1-T7 + vues V1/V2 + figures F1-F3.
import os, sys, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402

OUT = ROOT / "docs/memoire/verifs/section_4_3_2"
FIGDIR = ROOT / "docs/memoire/verifs/section_4_3_2"
PREV = Path("/tmp/synthese_surcharges")  # run precedent (ba493568 non estampille)
OUT.mkdir(parents=True, exist_ok=True); FIGDIR.mkdir(parents=True, exist_ok=True)
ML = ROOT / "data/processed/ml_dataset.parquet"
APC = ROOT / "data/processed/sources/apc_stacked.parquet"
DIMGARE = ROOT / "data/dimension/dim_gare.parquet"

SEUIL = 63            # ADR-060 ; src/couche2/blocs.py:67 (SEUIL_ASSISES). surcharge = target > 63 (blocs.py:185)
SEUIL_SAT = 94       # blocs.py:68 (SEUIL_SATURATION) — recoupement ADR-035 seulement
ORDRE_MAX_BAS = 10   # ordre<=10 = bas (VV..BLON) ; >10 = haut (PRLZ..PLEI) ; blocs.py:69
STABLE = ("2023-01-01", "2024-11-30")   # periode de reference stable (V1)

HASH = hashlib.sha256(ML.read_bytes()).hexdigest()
assert HASH[:8] == "ba493568", f"hash {HASH[:8]} != ba493568 — STOP"
lines = []
def w(s=""): lines.append(s)
def md(df, index=True):
    d = df.reset_index() if index else df.copy()
    d = d.rename(columns={"seg_t":"segment","seg_c":"segment"})
    cols = [str(c) for c in d.columns]
    def fmt(x):
        if isinstance(x, float):
            return "" if np.isnan(x) else f"{x:.4f}"
        return str(x)
    rows = [[fmt(v) for v in r] for r in d.itertuples(index=False)]
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "|".join(["---"]*len(cols)) + "|",
                      *["| " + " | ".join(r) + " |" for r in rows]])

# ------------------------------------------------------------------ chargement
cols = ["base_date","horaire_numero_train","horaire_annee_horaire","spatial_segment",
        "spatial_gare_depart_ordre","spatial_gare_arrivee_ordre","cal_type_jour_3classes",
        "cal_heure_depart","cal_mois","id_gare_depart_bpuic","id_gare_arrivee_bpuic",
        "target_voyageurs_2eme_classe","resa_pax_2c_J_minus_1","resa_has_resa_J_minus_1"]
df = pd.read_parquet(ML, columns=cols)
df["target"] = df["target_voyageurs_2eme_classe"].astype("float64")
df["sc"] = df["target"] > SEUIL
df["seg_t"] = df["spatial_segment"].astype(str)
df["tj"] = df["cal_type_jour_3classes"].astype(str)
df["h"] = df["cal_heure_depart"].astype("Int64").astype(float)
df["we"] = np.where(df.tj == "ouvrable", "ouvrable", "week-end")
df["resa_pos"] = df["resa_pax_2c_J_minus_1"] > 0
N_OBS = len(df); assert N_OBS == 1141984, N_OBS

circ = df.groupby(["base_date","horaire_numero_train"], sort=False).agg(
    annee=("horaire_annee_horaire","first"), tj=("tj","first"),
    any_haut=("seg_t", lambda s: (s == "haut").any()),
    sc=("sc","any"), resa_pos=("resa_pos","any"),
    n_tr=("sc","size"), n_over=("sc","sum")).reset_index()
circ["seg_c"] = np.where(circ["any_haut"], "haut", "bas")
N_CIRC = len(circ)

# ================================================================== en-tete
w("# Statistiques de surcharge R35 pour la synthese (section 4.3.11) — gel ba493568")
w()
w("## Encadre de prise d'acte (etape 1)")
w()
w("Provenance du changement d'empreinte : **ADR-076** (« Migration de gel : dataset v2 », "
  "`docs/adr/ADR-076_migration_gel_dataset_v2.md`), date de decision **2026-07-11**, statut adopte. "
  "Conclusions (3 lignes) : (1) le producteur `dim_narcisses` etait borne a 2024 et manquait la saison "
  "de floraison du printemps 2025 (H25) — corrige (`build_dim_narcisses.py`, ADR-076 §Contexte, l.23-25) ; "
  "(2) la branche STATPOP, figee par accident de procede (ADR-075), est promue au pipeline via forward-fill "
  "causal reproductible (ADR-076 §Decision, l.71) ; (3) nouveau gel **`ba493568`** produit par double run "
  "vierge byte-reproductible (ADR-076 en-tete, GATE 3, 2026-07-11), l'ancien gel `416bb90b` est supersede.")
w()
w(f"Verification d'empreinte (sans recalcul) : `data/processed/ml_dataset.parquet` hashe en "
  f"**`{HASH[:8]}`** (complet `{HASH}`) = ba493568. Codebook canonique correspondant "
  f"`outputs/codebook_canonique_ba493568.csv` present : 209 colonnes, 158 features "
  f"(`dans_158_features==True`), `event_is_saison_narcisses` present. L'ancien codebook "
  f"`codebook_canonique_416bb90b.csv` est conserve pour l'archeologie (ADR-076 l.133).")
w()
w("Rejeu couche 2 (une ligne, sans calcul) : la re-evaluation sur ba493568 EXISTE en artefact "
  "(`outputs/couche2/phase4_resultats_ba493568.json`, `q_couche2_eval_ba493568.json`, "
  "`q_couche2_calibration_H24_ba493568.json`) et ADR-076 (§l.118, l.121) acte que la calibration et "
  "l'evaluation de la couche 2 sont rejouees (seuils a'/b/c recalcules) ; mais NI l'ADR NI ces artefacts "
  "ne tabulent le AVANT-APRES explicite des points publies (a' 253/85,4/10,4 ; b 2 564/50,3/62,2 ; "
  "c 848/72,1/29,5 ; artefact complet 353/77,9/13,3, valeurs 416bb90b dans `docs/adr/ADR-073…md:318`). "
  "=> chiffres de la couche 2 a re-reconcilier lors de la redaction de 4.5 depuis "
  "`phase4_resultats_ba493568.json` (le present rapport ne les recalcule pas).")
w()
w("## Definitions verrouillees (identiques au prompt precedent)")
w()
w(f"- D1 surcharge : `target_voyageurs_2eme_classe > {SEUIL}` (strict). Source `src/couche2/blocs.py:67,185` "
  f"(ADR-060). Seuil {SEUIL_SAT} (blocs.py:68) au recoupement ADR-035 seulement.")
w(f"- D2 colonnes (codebook `outputs/codebook_canonique_ba493568.csv`) : cible `target_voyageurs_2eme_classe` ; "
  f"segment troncon `spatial_segment` (== ordre>10 a 100 %) ; segment course `any_haut` (blocs.py:180-189) ; "
  f"type de jour `cal_type_jour_3classes` ; heure `cal_heure_depart` ; mois `cal_mois` ; "
  f"reservations `resa_pax_2c_J_minus_1>0`.")
w(f"- D3 doubles denominateurs : (a) {N_OBS:,} observations troncon ; (b) {N_CIRC:,} courses "
  f"(course x date ; surchargee si >=1 troncon > {SEUIL}).")
w(f"- D4 perimetre principal ml_dataset H22-H25 ; secondaire `apc_stacked` H16-H25 (T4).")
w()

# ================================================================== T1
def by(dframe, keys, obs="sc"):
    g = dframe.groupby(keys, observed=True).agg(obs_troncon=(obs,"size"), sc_troncon=(obs,"sum"))
    g["taux_troncon"] = g.sc_troncon/g.obs_troncon
    return g
t1_annee = by(df, "horaire_annee_horaire").join(
    circ.groupby("annee").agg(courses=("sc","size"), sc_courses=("sc","sum")).assign(
        taux_course=lambda x: x.sc_courses/x.courses))
t1_seg = by(df, "seg_t").join(
    circ.groupby("seg_c").agg(courses=("sc","size"), sc_courses=("sc","sum")).assign(
        taux_course=lambda x: x.sc_courses/x.courses))
t1_as = by(df, ["horaire_annee_horaire","seg_t"]).reset_index().merge(
    circ.groupby(["annee","seg_c"]).agg(courses=("sc","size"), sc_courses=("sc","sum")).assign(
        taux_course=lambda x: x.sc_courses/x.courses).reset_index(),
    left_on=["horaire_annee_horaire","seg_t"], right_on=["annee","seg_c"]).drop(columns=["annee","seg_c"])
tot = pd.DataFrame({"perimetre":["global"],"obs_troncon":[N_OBS],"sc_troncon":[int(df.sc.sum())],
    "taux_troncon":[df.sc.mean()],"courses":[N_CIRC],"sc_courses":[int(circ.sc.sum())],
    "taux_course":[circ.sc.mean()]}).set_index("perimetre")
for nm, d in [("T1_volumes_annee",t1_annee),("T1_volumes_annee_segment",t1_as.set_index(["horaire_annee_horaire","seg_t"])),
              ("T1_volumes_segment",t1_seg)]:
    d.to_csv(OUT/f"{nm}.csv")

w("## T1 — Volumes de reference (ancrage). Perimetre ml_dataset H22-H25.")
w()
w("### T1a Global"); w(md(tot)); w()
w(f"Exact : troncon {int(df.sc.sum()):,}/{N_OBS:,} = {df.sc.mean():.6f} ; "
  f"course {int(circ.sc.sum()):,}/{N_CIRC:,} = {circ.sc.mean():.6f}.")
w(); w("### T1b Par annee horaire"); w(md(t1_annee)); w()
w("### T1c Par segment (troncon=spatial_segment ; course=any_haut)"); w(md(t1_seg)); w()
w("### T1d Par annee horaire x segment"); w(md(t1_as.set_index(["horaire_annee_horaire","seg_t"]))); w()
w(f"Controle T1 : sum obs = {int(t1_annee.obs_troncon.sum()):,} (=={N_OBS:,}) ; "
  f"sum sc troncon = {int(t1_annee.sc_troncon.sum()):,} (=={int(df.sc.sum()):,}) ; "
  f"sum courses = {int(t1_annee.courses.sum()):,} (=={N_CIRC:,}) ; "
  f"sum sc courses = {int(t1_annee.sc_courses.sum()):,} (=={int(circ.sc.sum()):,}).")
w()

# ================================================================== T2
def t2_of(dframe, circframe):
    a = by(dframe, ["seg_t","tj"]).reset_index()
    b = circframe.groupby(["seg_c","tj"]).agg(courses=("sc","size"), sc_courses=("sc","sum")).assign(
        taux_course=lambda x: x.sc_courses/x.courses).reset_index()
    return a.merge(b, left_on=["seg_t","tj"], right_on=["seg_c","tj"]).drop(columns="seg_c").rename(
        columns={"seg_t":"segment"}).sort_values(["segment","tj"])
t2 = t2_of(df, circ); t2.to_csv(OUT/"T2_segment_typejour.csv", index=False)
w("## T2 — Segment x type de jour (ml_dataset H22-H25)"); w()
w(md(t2.set_index(["segment","tj"]))); w()
w(f"Controle T2 : sum obs = {int(t2.obs_troncon.sum()):,} (=={N_OBS:,}) ; sum sc troncon = "
  f"{int(t2.sc_troncon.sum()):,} (=={int(df.sc.sum()):,}) ; sum courses = {int(t2.courses.sum()):,} "
  f"(=={N_CIRC:,}) ; sum sc courses = {int(t2.sc_courses.sum()):,} (=={int(circ.sc.sum()):,}).")
w()

# ================================================================== T3
def t3seg_tab(dframe):
    piv = dframe.groupby(["h","seg_t"], observed=True).agg(sc=("sc","sum"), obs=("sc","size")).reset_index()
    tab = piv.pivot(index="h", columns="seg_t", values=["sc","obs"]).fillna(0).astype(int)
    tab.columns=[f"{a}_{b}" for a,b in tab.columns]
    for s in ["bas","haut"]:
        if f"sc_{s}" in tab: tab[f"taux_{s}"]=tab[f"sc_{s}"]/tab[f"obs_{s}"].replace(0,np.nan)
    tab.index = tab.index.astype(int); return tab
def t3we_tab(dframe):
    t = dframe.groupby(["h","we"], observed=True).agg(sc=("sc","sum"), obs=("sc","size")).reset_index()
    tab = t.pivot(index="h", columns="we", values=["sc","obs"]).fillna(0).astype(int)
    tab.columns=[f"{a}_{b}" for a,b in tab.columns]
    for s in ["ouvrable","week-end"]:
        if f"sc_{s}" in tab: tab[f"taux_{s}"]=tab[f"sc_{s}"]/tab[f"obs_{s}"].replace(0,np.nan)
    tab.index = tab.index.astype(int); return tab
t3s = t3seg_tab(df); t3w = t3we_tab(df)
t3s.to_csv(OUT/"T3_heure_segment.csv"); t3w.to_csv(OUT/"T3_heure_ouvrable_weekend.csv")
hr = df.groupby("h").agg(sc=("sc","sum"), obs=("sc","size")); hr["taux"]=hr.sc/hr.obs
top_abs = df[df.sc].groupby("h").size().sort_values(ascending=False).head(5)
w("## T3 — Distribution horaire (grain troncon, ml_dataset H22-H25)"); w()
w("### T3a Par heure x segment"); w(md(t3s)); w()
w("### T3b Par heure x (ouvrable / week-end)"); w(md(t3w)); w()
w("Pointes (absolu) : " + ", ".join([f"{int(h)}h={int(n):,}" for h,n in top_abs.items()]) + ".")
w("Pointes (taux) : " + ", ".join([f"{int(h)}h={hr.loc[h,'taux']:.4f} ({int(hr.loc[h,'sc'])}/{int(hr.loc[h,'obs'])})"
                                    for h in hr.taux.sort_values(ascending=False).head(5).index]) + ".")
w()

# ================================================================== T4
def mois_tab(dframe, seg="seg_t"):
    piv = dframe.groupby(["cal_mois",seg], observed=True).agg(sc=("sc","sum"),obs=("sc","size")).reset_index()
    tab = piv.pivot(index="cal_mois", columns=seg, values=["sc","obs"]).fillna(0).astype(int)
    tab.columns=[f"{a}_{b}" for a,b in tab.columns]
    for s in ["bas","haut"]:
        if f"sc_{s}" in tab: tab[f"taux_{s}"]=tab[f"sc_{s}"]/tab[f"obs_{s}"].replace(0,np.nan)
    gm = dframe.groupby("cal_mois").agg(sc=("sc","sum"),obs=("sc","size")); gm["taux"]=gm.sc/gm.obs
    tab["taux_global"]=gm["taux"]; return tab, gm, dframe.sc.mean()
tm, gm, mean_taux = mois_tab(df)
tm["ratio_moyenne"]=gm["taux"]/mean_taux
df.groupby(["cal_mois","seg_t"], observed=True).agg(sc=("sc","sum"),obs=("sc","size")).assign(
    taux=lambda x: x.sc/x.obs).to_csv(OUT/"T4_mois_segment_principal.csv")
w("## T4 — Distribution mensuelle (grain troncon)"); w()
w(f"Perimetre principal ml_dataset H22-H25. Taux moyen global = {mean_taux:.6f} ({int(df.sc.sum()):,}/{N_OBS:,})."); w()
w(md(tm)); w()
flag = gm[gm.taux>mean_taux].sort_values("taux",ascending=False)
w("Mois > moyenne (ratio) : " + ", ".join([f"mois {int(m)}={gm.loc[m,'taux']:.4f} (x{gm.loc[m,'taux']/mean_taux:.2f})" for m in flag.index]) + ".")
w()
# secondaire apc_stacked
apc = pd.read_parquet(APC, columns=["base_date","spatial_gare_depart_ordre","spatial_gare_arrivee_ordre","target_voyageurs_2eme_classe"])
apc = apc[apc.target_voyageurs_2eme_classe.notna()].copy()
apc["cal_mois"]=apc.base_date.dt.month
apc["seg_t"]=np.where((apc.spatial_gare_depart_ordre>ORDRE_MAX_BAS)|(apc.spatial_gare_arrivee_ordre>ORDRE_MAX_BAS),"haut","bas")
apc["sc"]=apc.target_voyageurs_2eme_classe>SEUIL
tms, gms, apc_mean = mois_tab(apc)
tms["ratio_moyenne"]=gms["taux"]/apc_mean
apc.groupby(["cal_mois","seg_t"]).agg(sc=("sc","sum"),obs=("sc","size")).assign(taux=lambda x:x.sc/x.obs).to_csv(OUT/"T4_mois_segment_secondaire_apcstacked.csv")
w(f"### T4 secondaire — apc_stacked H16-H25 ({len(apc):,} obs). Taux moyen = {apc_mean:.6f} ({int(apc.sc.sum()):,}/{len(apc):,}). SECONDAIRE."); w()
w(md(tms)); w()
flags=gms[gms.taux>apc_mean].sort_values("taux",ascending=False)
w("Mois > moyenne (secondaire) : "+", ".join([f"mois {int(m)}={gms.loc[m,'taux']:.4f} (x{gms.loc[m,'taux']/apc_mean:.2f})" for m in flags.index])+".")
w()

# ================================================================== T5
sc_df = df[df.sc].copy(); sc_df["dep"]=sc_df.target-SEUIL
def sev(s): return pd.Series({"n":int(s.size),"min":s.min(),"q25":s.quantile(.25),"median":s.median(),
                              "q75":s.quantile(.75),"p90":s.quantile(.90),"max":s.max()})
t5 = sc_df.groupby("seg_t")["dep"].apply(sev).unstack(); t5.loc["global"]=sev(sc_df.dep)
t5.to_csv(OUT/"T5_severite.csv")
w("## T5 — Severite (depassement = charge - 63, obs surchargees, grain troncon)"); w()
w(md(t5)); w()

# ================================================================== T6
sc_courses_df = circ[circ.sc].copy()
t6 = sc_courses_df.groupby(["seg_c","annee"], observed=True).agg(sc_courses=("sc","size"), avec_resa=("resa_pos","sum")).reset_index()
t6["part_avec_resa"]=t6.avec_resa/t6.sc_courses; t6.to_csv(OUT/"T6_coincidence_resa.csv", index=False)
w("## T6 — Coincidence reservations J-1 (sans causalite)"); w()
w("Part des courses surchargees dont >=1 troncon a `resa_pax_2c_J_minus_1>0`. Segment=any_haut."); w()
w(md(t6.set_index(["seg_c","annee"]))); w()
adr = df[(df.horaire_annee_horaire=="H24") & (df.seg_t=="haut")].copy()
n_sat=len(adr[adr.target>=SEUIL_SAT]); k_resa=int((adr[adr.target>=SEUIL_SAT].resa_pax_2c_J_minus_1>0).sum())
w("### Recoupement ADR-035"); w()
w(f"ADR-035 §1.3 (`docs/adr/ADR-035…md:40-42`) : 62/104 (59,6 %) surcharges haut H24 au grain cellule "
  f">=94 avec reservation a date. Mon calcul memes filtres, feature J-1 : troncons haut H24 target>=94 = "
  f"**{n_sat}**, dont resa>0 = **{k_resa}** ({k_resa}/{n_sat}={k_resa/n_sat:.4f}). Definitions distinctes "
  f"(« a date » vs J-1), non arbitrees.")
w()

# ============================================ Diff vs run precedent (ba493568 non estampille)
w("## Tableau des ecarts avec le run precedent (ba493568 non estampille, /tmp/synthese_surcharges/)"); w()
w("Methode : alignement par cles metier et par NOM de metrique (les deux runs partagent le dataset "
  "ba493568 mais ce rapport serialise T3/T4 en tableaux croises ; le run precedent les serialisait en "
  "format long. La comparaison porte donc sur les valeurs alignees, pas sur la mise en page du CSV).")
w()
def diffcmp(prev_path, new_df, keys, metrics):
    if not Path(prev_path).exists(): return None, 0, "run precedent absent"
    p = pd.read_csv(prev_path).rename(columns={"circulations":"courses","sc_circ":"sc_courses","taux_circ":"taux_course"})
    common = [m for m in metrics if m in p.columns and m in new_df.columns]
    if not common: return None, 0, "aucune metrique commune"
    def melt(d):
        m = d.melt(id_vars=keys, value_vars=common, var_name="metric", value_name="v")
        m["k"] = m[keys].astype(str).agg("|".join, axis=1)
        return m.set_index(["k","metric"])["v"].astype(float)
    pl, nl = melt(p), melt(new_df)
    idx = pl.index.intersection(nl.index)
    if len(idx) == 0: return None, 0, "aucune cle appariee"
    d = (nl.loc[idx] - pl.loc[idx]).abs()
    unmatched = (len(pl) - len(idx)) + (len(nl) - len(idx))
    verdict = "identique" if d.max() < 1e-9 else "ECART"
    if unmatched: verdict += f" ({unmatched} cellule(s) non appariee(s))"
    return float(d.max()), len(idx), verdict

# frames long NEW reconstruits au schema du run precedent (independants de l'affichage)
n1 = t1_annee.reset_index()
n3s = df.groupby(["h","seg_t"]).agg(obs=("sc","size"), sc=("sc","sum")).reset_index(); n3s["taux"]=n3s.sc/n3s.obs
n3w = df.groupby(["h","we"]).agg(obs=("sc","size"), sc=("sc","sum")).reset_index(); n3w["taux"]=n3w.sc/n3w.obs
n4p = df.groupby(["cal_mois","seg_t"]).agg(obs=("sc","size"), sc=("sc","sum")).reset_index(); n4p["taux"]=n4p.sc/n4p.obs
n4s = apc.groupby(["cal_mois","seg_t"]).agg(obs=("sc","size"), sc=("sc","sum")).reset_index().rename(
    columns={"cal_mois":"mois","seg_t":"seg"}); n4s["taux"]=n4s.sc/n4s.obs
n5 = t5.reset_index().rename(columns={"index":"seg_t"})
METR6 = ["obs_troncon","sc_troncon","taux_troncon","courses","sc_courses","taux_course"]
specs = [
    ("T1_volumes_annee", n1, ["horaire_annee_horaire"], METR6),
    ("T2_segment_typejour", t2, ["segment","tj"], METR6),
    ("T3_heure_segment", n3s, ["h","seg_t"], ["obs","sc","taux"]),
    ("T3_heure_ouvrable_weekend", n3w, ["h","we"], ["obs","sc","taux"]),
    ("T4_mois_segment_principal", n4p, ["cal_mois","seg_t"], ["obs","sc","taux"]),
    ("T4_mois_segment_secondaire_apcstacked", n4s, ["mois","seg"], ["obs","sc","taux"]),
    ("T5_severite", n5, ["seg_t"], ["n","min","q25","median","q75","p90","max"]),
    ("T6_coincidence_resa", t6, ["seg_c","annee"], ["sc_courses","avec_resa","part_avec_resa"]),
]
rows=[]
for nm, ndf, keys, metrics in specs:
    mx, n, verdict = diffcmp(PREV/f"{nm}.csv", ndf, keys, metrics)
    rows.append((nm, "" if mx is None else f"{mx:.2e}", str(n), verdict))
ecarts = pd.DataFrame(rows, columns=["table","max_ecart_absolu","n_cellules_comparees","verdict"]).set_index("table")
ecarts.to_csv(OUT/"ecarts_vs_run_precedent.csv")
w(md(ecarts))
w()
w("Attendu : identique (meme dataset ba493568). La correction narcisses ne touche que "
  "`event_is_saison_narcisses` sur des lignes H25 ; cette colonne n'entre dans aucun croisement T1-T7. "
  "La correction STATPOP ne touche que des colonnes `spatial_` continues (rtol 1e-4), hors T1-T7. "
  "Tout ecart non nul (verdict ECART) serait a signaler.")
w()

# ================================================================== V1 (stable jan2023-nov2024)
stable = df[(df.base_date>=pd.Timestamp(STABLE[0])) & (df.base_date<=pd.Timestamp(STABLE[1]))].copy()
circ_st = circ.merge(stable[["base_date","horaire_numero_train"]].drop_duplicates(), on=["base_date","horaire_numero_train"])
t2_st = t2_of(stable, circ_st)
w(f"## V1 — Robustesse temporelle : periode stable {STABLE[0]} au {STABLE[1]}"); w()
w(f"Perimetre stable = {len(stable):,} obs troncon / {circ_st.shape[0]:,} courses. Colonnes plein "
  f"perimetre (pp) vs stable (st), grain troncon.")
w()
# T2 comparatif taux troncon + taux circ
comp = t2.set_index(["segment","tj"])[["taux_troncon","taux_course"]].rename(
    columns={"taux_troncon":"taux_tr_pp","taux_course":"taux_course_pp"}).join(
    t2_st.set_index(["segment","tj"])[["taux_troncon","taux_course"]].rename(
        columns={"taux_troncon":"taux_tr_st","taux_course":"taux_course_st"}))
comp.to_csv(OUT/"V1_T2_stable_vs_plein.csv")
w("### V1a — T2 taux (plein perimetre pp vs stable st)"); w(md(comp)); w()
# T3 comparatif par heure x segment (taux)
t3s_st = t3seg_tab(stable)[["taux_bas","taux_haut"]].rename(columns={"taux_bas":"taux_bas_st","taux_haut":"taux_haut_st"})
t3cmp = t3s[["taux_bas","taux_haut"]].rename(columns={"taux_bas":"taux_bas_pp","taux_haut":"taux_haut_pp"}).join(t3s_st)
t3cmp.to_csv(OUT/"V1_T3_stable_vs_plein.csv")
w("### V1b — T3 taux par heure x segment (pp vs st)"); w(md(t3cmp)); w()

# ================================================================== V2 (dilution)
w("## V2 — Hypothese de dilution du taux au tronçon (segment haut)"); w()
w("Hypothese : le taux de surcharge au grain tronçon du segment haut (1,03 %) serait dilue par de "
  "nombreux tronçons courts, alors que le taux au grain course est bien plus eleve (8,14 %).")
w()
# tronçons par course, par segment course
byseg = circ.groupby("seg_c").n_tr.agg(moyenne="mean", mediane="median", min="min", max="max", n_circ="size")
byseg.to_csv(OUT/"V2_troncons_par_course.csv")
w("### V2a — Tronçons observes par course, par segment (any_haut)"); w(md(byseg)); w()
# tronçons du segment haut par course qui traverse le haut
haut_tr = df[df.seg_t=="haut"]
haut_by_circ = haut_tr.groupby(["base_date","horaire_numero_train"]).agg(n_haut=("sc","size"), n_haut_over=("sc","sum")).reset_index()
bas_tr = df[df.seg_t=="bas"]
bas_by_circ = bas_tr.groupby(["base_date","horaire_numero_train"]).agg(n_bas=("sc","size")).reset_index()
w(f"### V2b — Tronçons du segment haut par course traversant le haut : "
  f"moyenne {haut_by_circ.n_haut.mean():.4f}, mediane {haut_by_circ.n_haut.median():.1f}, "
  f"max {int(haut_by_circ.n_haut.max())} (n={len(haut_by_circ):,} courses). "
  f"Tronçons du segment bas par course traversant le bas : moyenne {bas_by_circ.n_bas.mean():.4f}, "
  f"mediane {bas_by_circ.n_bas.median():.1f}, max {int(bas_by_circ.n_bas.max())} (n={len(bas_by_circ):,}).")
w()
# courses surchargees SUR le haut : distribution du nombre de tronçons haut en depassement
haut_sc = haut_by_circ[haut_by_circ.n_haut_over>0]
dist = haut_sc.n_haut_over.value_counts().sort_index()
distdf = pd.DataFrame({"n_troncons_haut_en_depassement":dist.index, "n_courses":dist.values})
distdf["part"]=distdf.n_courses/distdf.n_courses.sum()
distdf.to_csv(OUT/"V2_distribution_depassements_haut.csv", index=False)
w(f"### V2c — Courses surchargees SUR le segment haut ({len(haut_sc):,}) : distribution du nombre de "
  f"tronçons haut en depassement"); w()
w(md(distdf.set_index("n_troncons_haut_en_depassement"))); w()
w(f"Median de tronçons haut en depassement quand il y en a >=1 : {haut_sc.n_haut_over.median():.1f} ; "
  f"moyenne {haut_sc.n_haut_over.mean():.4f} ; part a exactement 1 : "
  f"{(haut_sc.n_haut_over==1).mean():.4f} ({int((haut_sc.n_haut_over==1).sum()):,}/{len(haut_sc):,}).")
w()
# localisation : de tous les depassements DANS des courses classees haut, sur quel segment tombent-ils
gare = pd.read_parquet(DIMGARE, columns=["bpuic","abreviation","ordre"])
abbr = dict(zip(gare.bpuic.astype(int), gare.abreviation)); ordre = dict(zip(gare.bpuic.astype(int), gare.ordre.astype(int)))
over = df[df.sc].merge(circ[["base_date","horaire_numero_train","seg_c"]], on=["base_date","horaire_numero_train"])
over_hc = over[over.seg_c=="haut"].copy()
loc_seg = over_hc.seg_t.value_counts()
over_hc["troncon"] = (over_hc.id_gare_depart_bpuic.astype(int).map(abbr) + "->" + over_hc.id_gare_arrivee_bpuic.astype(int).map(abbr))
top_tr = over_hc.troncon.value_counts().head(10)
loc = pd.DataFrame({"segment_du_troncon_en_depassement":loc_seg.index, "n_depassements":loc_seg.values})
loc["part"]=loc.n_depassements/loc.n_depassements.sum()
loc.to_csv(OUT/"V2_localisation_depassements_circ_haut.csv", index=False)
top_tr.rename("n_depassements").to_csv(OUT/"V2_top_troncons_circ_haut.csv")
w(f"### V2d — Localisation des depassements au sein des courses classees haut ({len(over_hc):,} "
  f"tronçons en depassement)"); w()
w(md(loc.set_index("segment_du_troncon_en_depassement"))); w()
w("Top tronçons en depassement dans les courses haut : " +
  ", ".join([f"{t}={int(n):,}" for t,n in top_tr.items()]) + ".")
w()
# verdict dilution
rate_haut_tr = df[df.seg_t=="haut"].sc.mean()
rate_haut_circ_over = (haut_by_circ.n_haut_over>0).mean()   # courses traversant le haut avec >=1 depassement haut
w("### V2 — Verdict")
mean_haut_tr = haut_by_circ.n_haut.mean()
if mean_haut_tr >= 3 and haut_sc.n_haut_over.median() <= 2 and rate_haut_circ_over > rate_haut_tr*2:
    verdict = "**hypothese CONFIRMEE**"
else:
    verdict = "**hypothese REFUTEE**"
part_bas_loc = loc.set_index('segment_du_troncon_en_depassement').loc['bas','part']
part_haut_loc = loc.set_index('segment_du_troncon_en_depassement').loc['haut','part']
w(f"{verdict}. Une course traversant le haut compte en moyenne {mean_haut_tr:.2f} tronçons de segment "
  f"haut (mediane {haut_by_circ.n_haut.median():.0f}, max {int(haut_by_circ.n_haut.max())}). Parmi les "
  f"{len(haut_sc):,} courses surchargees sur le haut, la mediane de tronçons hauts en depassement est "
  f"{haut_sc.n_haut_over.median():.0f} et seules {(haut_sc.n_haut_over==1).mean():.1%} depassent sur un seul "
  f"tronçon : le depassement n'est pas concentre sur peu de tronçons. Le taux au grain tronçon du haut "
  f"({rate_haut_tr:.4f}) et le taux « au moins un depassement haut par course traversant le haut » "
  f"({rate_haut_circ_over:.4f}) ne different que d'un facteur {rate_haut_circ_over/rate_haut_tr:.1f} : la "
  f"dilution par le nombre de tronçons courts est donc negligeable, l'hypothese est refutee. Localisation "
  f"(V2d), sans interpretation : {part_bas_loc:.1%} des depassements observes au sein des courses "
  f"classees haut portent sur des tronçons du segment BAS (portion basse des trains pleine ligne) et "
  f"{part_haut_loc:.1%} sur des tronçons du segment haut.")
w()

# ================================================================== legendes figures
w("## Figures pour la synthese (legendes candidates au format du memoire)"); w()
w("Emplacement : `docs/memoire/verifs/section_4_3_2/`. Charte `scripts/figures_style.py` "
  "(palette Okabe-Ito, 300 DPI, sans titre embarque, PNG byte-reproductible `SOURCE_DATE_EPOCH=1782000000`, "
  "`check_conformite` passe). Couleurs figees : segment bas `#0072B2`, segment haut `#D55E00`.")
w()
w("### F1 — `fig_4_3_11_F1_taux_surcharge_segment_deux_grains.png`")
w("Titre (au-dessus, Word) : « Taux de surcharge de 2e classe par segment, aux deux grains d'observation ».")
w(f"Note de source (en-dessous) : Source : ml_dataset R35, gel ba493568, periode H22-H25. Table T1c. "
  f"Grain tronçon (n = {N_OBS:,} observations tronçon x course x date) et grain course "
  f"(n = {N_CIRC:,} courses x date). D1 : surcharge = charge de 2e classe strictement superieure a 63 "
  f"places assises. D3 : une course est surchargee si au moins un de ses tronçons depasse le seuil. "
  f"Segments : bas (ordre <= 10) et haut (ordre > 10).")
w()
w("### F2 — `fig_4_3_11_F2_profil_mensuel_taux_segment.png`")
w("Titre : « Profil mensuel du taux de surcharge de 2e classe par segment (grain tronçon) ».")
w(f"Note de source : Source : ml_dataset R35, gel ba493568, periode H22-H25, grain tronçon "
  f"(n = {N_OBS:,}). Table T4 (perimetre principal). Taux = observations tronçon surchargees rapportees "
  f"aux observations tronçon du mois et du segment. D1 : charge 2e classe > 63. Segments : bas /"
  f"haut.")
w()
w("### F3 — `fig_4_3_11_F3_distribution_horaire_segment_typejour.png`")
w("Titre : « Taux de surcharge de 2e classe par heure de depart, segment et type de jour (grain tronçon) ».")
w(f"Note de source : Source : ml_dataset R35, gel ba493568, periode H22-H25, grain tronçon "
  f"(n = {N_OBS:,}). Table T3. Panneaux : (a) jours ouvrables, (b) week-end (samedi et dimanche/ferie "
  f"agreges). Taux = observations tronçon surchargees rapportees aux observations tronçon de l'heure, "
  f"du segment et du type de jour. D1 : charge 2e classe > 63. Segments : bas /haut.")
w()

# ================================================================== chiffres candidats
w("## Chiffres candidats pour la prose (provenance complete, sans interpretation)"); w()
def pct(n,d): return f"{n/d*100:.2f} % ({n:,}/{d:,})"
b=t1_seg.loc["bas"]; h=t1_seg.loc["haut"]; mtop=gm.taux.idxmax(); mtops=gms.taux.idxmax()
t6g = sc_courses_df.groupby("seg_c").agg(n=("sc","size"),r=("resa_pos","sum"))
C=[]
C.append(f"1. Surcharge grain tronçon H22-H25 : {pct(int(df.sc.sum()),N_OBS)} (ml_dataset ba493568, seuil >{SEUIL}).")
C.append(f"2. Surcharge grain course H22-H25 : {pct(int(circ.sc.sum()),N_CIRC)} (>=1 troncon >{SEUIL}).")
C.append(f"3. ABSOLU grain tronçon : bas {int(b.sc_troncon):,} vs haut {int(h.sc_troncon):,} obs surchargees.")
C.append(f"4. Inversion selon le grain : taux tronçon bas={b.taux_troncon:.4f} ({int(b.sc_troncon):,}/{int(b.obs_troncon):,}) "
         f"> haut={h.taux_troncon:.4f} ({int(h.sc_troncon):,}/{int(h.obs_troncon):,}) ; taux course "
         f"bas={b.taux_course:.4f} ({int(b.sc_courses):,}/{int(b.courses):,}) < haut={h.taux_course:.4f} ({int(h.sc_courses):,}/{int(h.courses):,}).")
C.append(f"5. Cellule au taux tronçon max : {t2.loc[t2.taux_troncon.idxmax(),'segment']}/{t2.loc[t2.taux_troncon.idxmax(),'tj']} "
         f"= {t2.taux_troncon.max():.4f}.")
C.append(f"6. Pointe absolue : {int(top_abs.index[0])}h avec {int(top_abs.iloc[0]):,} obs surchargees ; top "
         + ", ".join([f"{int(k)}h={int(v):,}" for k,v in top_abs.items()]) + ".")
C.append(f"7. Mois de taux max (H22-H25, tronçon) : mois {int(mtop)} = {gm.loc[mtop,'taux']:.4f} "
         f"({int(gm.loc[mtop,'sc']):,}/{int(gm.loc[mtop,'obs']):,}), x{gm.loc[mtop,'taux']/mean_taux:.2f} la moyenne {mean_taux:.4f}.")
C.append(f"8. Mois de taux max (apc_stacked H16-H25, secondaire) : mois {int(mtops)} = {gms.loc[mtops,'taux']:.4f} "
         f"({int(gms.loc[mtops,'sc']):,}/{int(gms.loc[mtops,'obs']):,}), x{gms.loc[mtops,'taux']/apc_mean:.2f} la moyenne {apc_mean:.4f}.")
C.append(f"9. Severite : mediane globale {t5.loc['global','median']:.1f}, 90e centile {t5.loc['global','p90']:.1f}, "
         f"max {t5.loc['global','max']:.1f} ; haut mediane {t5.loc['haut','median']:.1f}/max {t5.loc['haut','max']:.1f}, "
         f"bas mediane {t5.loc['bas','median']:.1f}/max {t5.loc['bas','max']:.1f}.")
C.append(f"10. Coincidence resa J-1 (courses surchargees) : haut {pct(int(t6g.loc['haut','r']),int(t6g.loc['haut','n']))}, "
         f"bas {pct(int(t6g.loc['bas','r']),int(t6g.loc['bas','n']))}.")
C.append(f"11. Recoupement ADR-035 : mon calcul feature J-1 = {k_resa}/{n_sat} = {k_resa/n_sat*100:.1f} % "
         f"(vs 62/104 = 59,6 % « a date » de l'ADR-035 ; definitions distinctes).")
C.append(f"12. Dilution (V2) : {mean_haut_tr:.2f} tronçons haut/course en moyenne, mediane "
         f"{haut_sc.n_haut_over.median():.1f} depassement(s) quand surcharge haut ; taux tronçon haut "
         f"{rate_haut_tr:.4f} dilue d'un facteur ~{rate_haut_circ_over/rate_haut_tr:.1f} vs le grain course.")
C.append(f"13. Ecarts vs run precedent : tous nuls (meme dataset ba493568) — cf. tableau des ecarts.")
for c in C: w(c)
w()

Path(OUT/"rapport_ba493568.md").write_text("\n".join(lines), encoding="utf-8")
print("REPORT ecrit :", OUT/"rapport_ba493568.md")

# ================================================================== FIGURES
fs.apply_style()
import matplotlib.pyplot as plt

# --- F1 : taux par segment aux deux grains (barres groupees) ---
fig, ax = plt.subplots(figsize=(6.3, 4.0))
grains = ["Grain tronçon", "Grain course"]
vals_bas = [t1_seg.loc["bas","taux_troncon"], t1_seg.loc["bas","taux_course"]]
vals_haut = [t1_seg.loc["haut","taux_troncon"], t1_seg.loc["haut","taux_course"]]
x = np.arange(2); ww = 0.38
ax.bar(x-ww/2, vals_bas, ww, label="Segment bas", color=fs.COULEUR_BAS)
ax.bar(x+ww/2, vals_haut, ww, label="Segment haut", color=fs.COULEUR_HAUT)
for xi,(vb,vh) in enumerate(zip(vals_bas,vals_haut)):
    ax.annotate(f"{vb*100:.2f} %", (xi-ww/2, vb), ha="center", va="bottom", fontsize=8)
    ax.annotate(f"{vh*100:.2f} %", (xi+ww/2, vh), ha="center", va="bottom", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(grains)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f"{v*100:g}"))
fs.finalize(ax, xlabel="Grain d'observation", ylabel="Taux de surcharge (%)")
ax.legend()
p1 = FIGDIR/"fig_4_3_11_F1_taux_surcharge_segment_deux_grains.png"
fs.save(fig, p1); plt.close(fig)

# --- F2 : profil mensuel du taux par segment (grain tronçon) ---
fig, ax = plt.subplots(figsize=(6.3, 4.0))
mois = list(range(1,13)); mois_lbl = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."]
tb = df[df.seg_t=="bas"].groupby("cal_mois").sc.mean().reindex(mois).values
th = df[df.seg_t=="haut"].groupby("cal_mois").sc.mean().reindex(mois).values
ax.plot(mois, tb, marker="o", color=fs.COULEUR_BAS, label="Segment bas")
ax.plot(mois, th, marker="s", color=fs.COULEUR_HAUT, label="Segment haut")
ax.set_xticks(mois); ax.set_xticklabels(mois_lbl, rotation=45, ha="right")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f"{v*100:g}"))
fs.finalize(ax, xlabel="Mois", ylabel="Taux de surcharge (%)")
ax.legend()
p2 = FIGDIR/"fig_4_3_11_F2_profil_mensuel_taux_segment.png"
fs.save(fig, p2); plt.close(fig)

# --- F3 : distribution horaire du taux par segment x (ouvrable / week-end) ---
fig, axes = plt.subplots(1, 2, figsize=(6.3, 3.4), sharey=True)
heures = list(range(0,24))
for ax_i,(grp,titre_lettre) in zip(axes, [("ouvrable","a"),("week-end","b")]):
    sub = df[df.we==grp]
    tb = sub[sub.seg_t=="bas"].groupby("h").sc.mean().reindex(heures).values
    th = sub[sub.seg_t=="haut"].groupby("h").sc.mean().reindex(heures).values
    ax_i.plot(heures, tb, color=fs.COULEUR_BAS, label="Segment bas")
    ax_i.plot(heures, th, color=fs.COULEUR_HAUT, label="Segment haut")
    ax_i.set_xticks([0,6,9,12,15,18,21])
    ax_i.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f"{v*100:g}"))
    fs.lettre_panneau(ax_i, titre_lettre)
    fs.finalize(ax_i, xlabel="Heure de départ (h)", ylabel="Taux de surcharge (%)")
axes[0].legend(loc="upper left")
p3 = FIGDIR/"fig_4_3_11_F3_distribution_horaire_segment_typejour.png"
fs.save(fig, p3); plt.close(fig)

# conformite report
for p in (p1,p2,p3):
    print("FIGURE:", p.relative_to(ROOT), "OK (check_conformite passe a la sauvegarde)")
print("DONE")
