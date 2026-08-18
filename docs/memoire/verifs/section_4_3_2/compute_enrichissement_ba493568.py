#!/usr/bin/env python3
# Enrichissement de la synthese exploratoire des surcharges R35 (section 4.3.11) - gel ba493568.
# Blocs 1 (deux regimes), 2 (cible rare structuree), 3 (distribution changeante). Lecture seule
# sauf ecriture dans docs/memoire/verifs/section_4_3_2/ et docs/memoire/verifs/section_4_3_2/.
# Aucune interpretation causale : "coincide avec", jamais "explique".
import os, sys, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, gaussian_kde

os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402

OUT = ROOT / "docs/memoire/verifs/section_4_3_2"
FIG = ROOT / "docs/memoire/verifs/section_4_3_2"
OUT.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)
ML = ROOT / "data/processed/ml_dataset.parquet"
APC = ROOT / "data/processed/sources/apc_stacked.parquet"
HOR = ROOT / "data/processed/sources/horaires_clean.parquet"
SIMBA = ROOT / "data/dimension/dim_simba_r35.parquet"
STATPOP = ROOT / "data/processed/sources/statpop_clean_causal.parquet"
STATENT = ROOT / "data/processed/sources/statent_clean_causal.parquet"
DIMGARE = ROOT / "data/dimension/dim_gare.parquet"
ANNEES = ROOT / "data/dimension/annees_horaires.csv"

SEUIL = 63
ORDRE_MAX_BAS = 10
HASH = hashlib.sha256(ML.read_bytes()).hexdigest()
assert HASH[:8] == "ba493568", f"hash {HASH[:8]} != ba493568 — STOP"
RNG = np.random.default_rng(0)
lines = []
def w(s=""): lines.append(s)
def md(df, index=True):
    d = df.reset_index() if index else df.copy()
    cols=[str(c) for c in d.columns]
    def fmt(x):
        if isinstance(x, float): return "" if (isinstance(x,float) and np.isnan(x)) else f"{x:.4f}"
        return str(x)
    rows=[[fmt(v) for v in r] for r in d.itertuples(index=False)]
    return "\n".join(["| "+" | ".join(cols)+" |","|"+"|".join(["---"]*len(cols))+"|",
                      *["| "+" | ".join(r)+" |" for r in rows]])

gare = pd.read_parquet(DIMGARE, columns=["abreviation","bpuic","ordre","nom"])
ABBR2ORD = dict(zip(gare.abreviation, gare.ordre.astype(int)))
BPUIC2ORD = dict(zip(gare.bpuic.astype(int), gare.ordre.astype(int)))
BPUIC2ABBR = dict(zip(gare.bpuic.astype(int), gare.abreviation))
def seg_from_ordre(o): return "haut" if o>ORDRE_MAX_BAS else "bas"

def assign_annee(dates):
    ah=pd.read_csv(ANNEES, sep=";", encoding="utf-8-sig")
    ah=ah[ah.Debut.notna() & ah.Fin.notna()].copy()
    ah["d"]=pd.to_datetime(ah.Debut, format="%d.%m.%Y"); ah["f"]=pd.to_datetime(ah.Fin, format="%d.%m.%Y")
    out=pd.Series(["?"]*len(dates), index=dates.index, dtype=object)
    for _,r in ah.iterrows(): out[(dates>=r.d)&(dates<=r.f)]=r.Annee
    return out

# ============ chargements
ml = pd.read_parquet(ML, columns=["base_date","horaire_numero_train","horaire_annee_horaire",
    "spatial_segment","spatial_gare_depart_ordre","spatial_gare_arrivee_ordre","cal_heure_depart",
    "id_gare_depart_bpuic","id_gare_arrivee_bpuic","base_sens","target_voyageurs_2eme_classe",
    "resa_pax_2c_J_minus_1"])
ml["t"]=ml.target_voyageurs_2eme_classe.astype("float64")
ml["seg"]=ml.spatial_segment.astype(str)
ml["h"]=ml.cal_heure_depart.astype("Int64").astype(float)
ml["sc"]=ml.t>SEUIL
N_ML=len(ml)

w("# Enrichissement de la synthese exploratoire des surcharges R35 (section 4.3.11)")
w()
w(f"Empreinte : **ba493568** (`{HASH}`). Perimetre principal ml_dataset H22-H25 ({N_ML:,} obs troncon) ; "
  f"perimetre secondaire apc_stacked H16-H25 (signale). Complete `rapport_ba493568.md` (T1-T7, V1-V2, F1-F3) ; "
  f"ne le recalcule pas. Segment troncon = `spatial_segment` (== ordre>10 a 100 %) ; segment course = any_haut. "
  f"D1 surcharge = `target_voyageurs_2eme_classe > {SEUIL}`. Aucune interpretation causale (« coincide avec »).")
w()

# ====================================================================== BLOC 1a : profil charge / troncon
w("## Bloc 1a — Profil de charge de 2e classe le long de la ligne (grain troncon, ml_dataset H22-H25)")
w()
ml["dep_ord"]=ml.id_gare_depart_bpuic.astype(int).map(BPUIC2ORD)
ml["arr_ord"]=ml.id_gare_arrivee_bpuic.astype(int).map(BPUIC2ORD)
ml["dep_ab"]=ml.id_gare_depart_bpuic.astype(int).map(BPUIC2ABBR)
ml["arr_ab"]=ml.id_gare_arrivee_bpuic.astype(int).map(BPUIC2ABBR)
ml["pos"]=ml[["dep_ord","arr_ord"]].min(axis=1)             # position physique (troncon entre pos et pos+1)
ml["troncon_phys"]=ml.apply(lambda r: f"{min(r.dep_ab,r.arr_ab,key=lambda a:ABBR2ORD[a])}-"
                                       f"{max(r.dep_ab,r.arr_ab,key=lambda a:ABBR2ORD[a])}", axis=1)
# symetrie : mediane par troncon oriente vs sens inverse
orient = ml.groupby(["troncon_phys","base_sens"]).t.median().unstack()
orient_ok = orient.dropna()
sym_corr = orient_ok.corr().iloc[0,1] if orient_ok.shape[1]==2 else float("nan")
sym_maxdiff = (orient_ok.iloc[:,0]-orient_ok.iloc[:,1]).abs().max() if orient_ok.shape[1]==2 else float("nan")
w(f"Symetrie des sens : correlation des medianes par troncon entre les deux sens = {sym_corr:.4f} ; "
  f"ecart absolu median max = {sym_maxdiff:.1f} voyageurs. Les deux sens sont donc "
  f"{'agreges (symetriques)' if sym_corr>0.9 else 'presentes separement (non symetriques)'} dans le profil.")
w()
prof_all = ml.groupby("troncon_phys").agg(pos=("pos","first"), n=("t","size"),
    mediane=("t","median"), moyenne=("t","mean"),
    p90=("t", lambda s: s.quantile(0.90))).reset_index()
prof_all["segment"]=prof_all.pos.apply(lambda p: "bas" if p<ORDRE_MAX_BAS else "haut")
prof_all.sort_values("pos").to_csv(OUT/"B1a_profil_charge_troncon.csv", index=False)  # tous, tracable
SEUIL_N = 1000
excl = prof_all[prof_all.n < SEUIL_N]
prof = prof_all[prof_all.n >= SEUIL_N].sort_values(["pos","troncon_phys"]).reset_index(drop=True)
w(f"Tronçons non adjacents a effectif negligeable exclus du profil (n < {SEUIL_N}) : "
  + ", ".join([f"{r.troncon_phys} (n={int(r.n)})" for r in excl.itertuples()]) + ". "
  "Chaque tronçon retenu compte au moins 15 000 observations. GIL (H22) et VVVI (H23+) coexistent "
  "car ils desservent la meme position selon la topologie de l'annee.")
w()
w(md(prof.set_index("troncon_phys")[["pos","n","mediane","moyenne","p90","segment"]]))
w()
seg_prof = ml.groupby("seg").t.agg(mediane="median", moyenne="mean", p90=lambda s:s.quantile(.90))
w(f"Resume : charge mediane bas={seg_prof.loc['bas','mediane']:.1f} vs haut={seg_prof.loc['haut','mediane']:.1f} ; "
  f"moyenne bas={seg_prof.loc['bas','moyenne']:.2f} vs haut={seg_prof.loc['haut','moyenne']:.2f} ; "
  f"90e centile bas={seg_prof.loc['bas','p90']:.1f} vs haut={seg_prof.loc['haut','p90']:.1f}.")
# part de la charge sur VV-VVVI et VV-BLON
tot_charge=ml.t.sum()
vvvvi = ml[(ml.pos==0)].t.sum()   # troncon commencant a VV (ordre 0)
bas_charge = ml[ml.seg=="bas"].t.sum()
w(f"Concentration : le troncon d'extremite Vevey (position 0) porte {vvvvi/tot_charge*100:.2f} % "
  f"({int(vvvvi):,}/{int(tot_charge):,}) de la charge 2e classe totale ; le segment bas en porte "
  f"{bas_charge/tot_charge*100:.2f} % ({int(bas_charge):,}/{int(tot_charge):,}).")
w()
# F4 (profil : ombrage des segments + bande mediane-90e + labels 45 deg)
fs.apply_style()
pp=prof.sort_values(["pos","troncon_phys"]).reset_index(drop=True)
x=np.arange(len(pp)); bnd=int(np.argmax(pp.pos.values>=ORDRE_MAX_BAS))
fig,ax=plt.subplots(figsize=(7.2,4.6))
ax.axvspan(-0.5, bnd-0.5, color=fs.COULEUR_BAS, alpha=0.06)
ax.axvspan(bnd-0.5, len(pp)-0.5, color=fs.COULEUR_HAUT, alpha=0.06)
ax.fill_between(x, pp.mediane, pp.p90, color="#c0c0c0", alpha=0.35, linewidth=0, label="Médiane à 90e centile")
ax.plot(x, pp.p90, color="#8a8a8a", lw=1.4)
ax.plot(x, pp.moyenne, color=fs.COULEUR_BAS, lw=2.2, marker="o", ms=4, label="Moyenne")
ax.plot(x, pp.mediane, color=fs.COULEUR_HAUT, lw=2.2, marker="s", ms=4, label="Médiane")
fs.seuil_um_line(ax, orientation="h")
ax.text(bnd/2, 61, "segment bas", ha="center", va="top", fontsize=9, color=fs.COULEUR_BAS, fontweight="bold")
ax.text((bnd+len(pp))/2, 61, "segment haut", ha="center", va="top", fontsize=9, color=fs.COULEUR_HAUT, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(pp.troncon_phys, rotation=45, ha="right", fontsize=7)
ax.set_xlim(-0.5,len(pp)-0.5); ax.grid(axis="x", visible=False); ax.margins(y=0.02)
fs.finalize(ax, xlabel="Tronçon (de Vevey aux Pléiades)", ylabel="Charge de 2e classe (voyageurs)")
ax.legend(loc="center right", fontsize=8)
p4=FIG/"fig_4_3_11_F4_profil_charge_troncon.png"; fs.save(fig,p4); plt.close(fig)

# ====================================================================== BLOC 1b : concentration horaire
w("## Bloc 1b — Concentration horaire de la charge (grain troncon, ml_dataset H22-H25)")
w()
tj3 = pd.read_parquet(ML, columns=["cal_type_jour_3classes"])["cal_type_jour_3classes"].astype(str).values
ml["we"]=np.where(tj3=="ouvrable","ouvrable","week-end")
def concentration(sub):
    s=sub.groupby("h").t.sum()
    s=s.reindex(range(24), fill_value=0.0)
    tot=s.sum(); p=(s/tot) if tot>0 else s*0
    top3=p.sort_values(ascending=False).head(3).sum()
    pnz=p[p>0]
    ent=-(pnz*np.log(pnz)).sum()/np.log(len(pnz)) if len(pnz)>1 else 0.0   # entropie normalisee
    srt=np.sort(p.values); n=len(srt); cum=np.cumsum(srt)
    gini=(n+1-2*(cum/cum[-1]).sum())/n if cum[-1]>0 else 0.0
    return p, top3, ent, gini, tot
rows=[]; profils={}
for seg in ["bas","haut"]:
    for grp in ["ouvrable","week-end"]:
        sub=ml[(ml.seg==seg)&(ml.we==grp)]
        p,top3,ent,gini,tot=concentration(sub)
        profils[(seg,grp)]=p
        rows.append((seg,grp,top3,ent,gini,int(tot)))
conc=pd.DataFrame(rows,columns=["segment","type_jour","part_top3_heures","entropie_normalisee","gini_horaire","charge_totale"])
conc.to_csv(OUT/"B1b_concentration_horaire.csv", index=False)
w(md(conc.set_index(["segment","type_jour"])))
w()
w("part_top3_heures = somme des parts des 3 heures les plus chargees ; entropie_normalisee dans [0,1] "
  "(1 = charge etalee uniformement sur les heures actives, 0 = concentree) ; gini_horaire (1 = concentre). "
  "Denominateur = charge 2e classe totale de la cellule segment x type de jour.")
w()
# F5
fig,axes=plt.subplots(1,2,figsize=(6.3,3.4),sharey=True)
for ax_i,(grp,lettre) in zip(axes,[("ouvrable","a"),("week-end","b")]):
    for seg,col in [("bas",fs.COULEUR_BAS),("haut",fs.COULEUR_HAUT)]:
        p=profils[(seg,grp)]
        ax_i.plot(range(24), p.values*100, color=col, label=f"Segment {seg}")
    ax_i.set_xticks([0,6,9,12,15,18,21]); fs.lettre_panneau(ax_i,lettre)
    fs.finalize(ax_i, xlabel="Heure de départ (h)", ylabel="Part de la charge journalière (%)")
axes[0].legend(loc="upper left", fontsize=8)
p5=FIG/"fig_4_3_11_F5_concentration_horaire.png"; fs.save(fig,p5); plt.close(fig)

# ====================================================================== BLOC 1c : gradients territoriaux
w("## Bloc 1c — Gradients territoriaux (STATPOP dernier millesime, STATENT dernier millesime)")
w()
sp=pd.read_parquet(STATPOP)
sp=sp.sort_values("annee_enquete_statpop").groupby("gare_abreviation").tail(1)   # dernier millesime par gare
sp["ordre"]=sp.gare_abreviation.map(ABBR2ORD); sp["segment"]=sp.ordre.apply(seg_from_ordre)
se=pd.read_parquet(STATENT)
se=se.sort_values("annee_enquete_statent").groupby("gare_abreviation").tail(1)
se["ordre"]=se.gare_abreviation.map(ABBR2ORD); se["segment"]=se.ordre.apply(seg_from_ordre)
terr=sp[["gare_abreviation","ordre","segment","annee_enquete_statpop","population_500m_total","menages_500m_total"]].merge(
    se[["gare_abreviation","annee_enquete_statent","emplois_500m_total","emplois_500m_services"]],
    on="gare_abreviation", how="left").sort_values("ordre")
terr.to_csv(OUT/"B1c_gradients_territoriaux.csv", index=False)
w(f"Millesimes : STATPOP {int(sp.annee_enquete_statpop.min())}-{int(sp.annee_enquete_statpop.max())} "
  f"(dernier par gare), STATENT {int(se.annee_enquete_statent.min())}-{int(se.annee_enquete_statent.max())}.")
w(md(terr.set_index("gare_abreviation")[["ordre","segment","population_500m_total","emplois_500m_total","emplois_500m_services"]]))
w()
rp=terr.groupby("segment").population_500m_total.mean(); re=terr.groupby("segment").emplois_500m_total.mean()
w(f"Ratio bas/haut : population 500 m moyenne bas={rp['bas']:.0f} vs haut={rp['haut']:.0f} "
  f"(ratio {rp['bas']/rp['haut']:.1f}) ; emplois 500 m moyenne bas={re['bas']:.0f} vs haut={re['haut']:.0f} "
  f"(ratio {re['bas']/re['haut']:.1f}). Gare de Vevey : population {int(terr[terr.gare_abreviation=='VV'].population_500m_total.iloc[0]):,}, "
  f"emplois {int(terr[terr.gare_abreviation=='VV'].emplois_500m_total.iloc[0]):,}.")
w()
# F6
# F6 : carte geospatiale (bulles = population, couleur = EPT/habitant), qui remplace les
# deux barres pop/emplois. Elle est produite par le script dedie
# docs/memoire/verifs/section_4_3_2/carte_gares_pop_emploi.py (fond de carte externe
# CartoDB/OSM, hors chaine byte-reproductible). Les donnees B1c ci-dessus l'alimentent.

# ====================================================================== BLOC 1d : reponse de l'offre
w("## Bloc 1d — Reponse de l'offre : courses planifiees par heure et par segment (horaires_clean, H24)")
w()
w("Annee horaire representative : H24 (annee complete, 371 jours, materiel SURF, frequentation post-COVID "
  "normalisee, numerotation stable anterieure a la refonte de decembre 2024 ; c'est aussi l'annee de test "
  "du split canonique). Source : `horaires_clean.parquet` filtre H24. ouvrable/week-end depuis `is_weekend` "
  "et `is_public_holiday`.")
w()
ho=pd.read_parquet(HOR, columns=["annee_horaire","date","numero_train","depart_datetime",
    "gare_depart_ordre","gare_arrivee_ordre","is_weekend","is_public_holiday"])
ho=ho[ho.annee_horaire=="H24"].copy()
ho["seg"]=np.where((ho.gare_depart_ordre>ORDRE_MAX_BAS)|(ho.gare_arrivee_ordre>ORDRE_MAX_BAS),"haut","bas")
ho["h"]=ho.depart_datetime.dt.hour
ho["we"]=np.where(ho.is_weekend | ho.is_public_holiday,"week-end","ouvrable")
ndays=ho.groupby("we").date.nunique().to_dict()
# trains distincts desservant le segment, par heure de depart du troncon, moyenne par jour
offre=(ho.groupby(["we","seg","h","date"]).numero_train.nunique().reset_index()
         .groupby(["we","seg","h"]).numero_train.mean().reset_index())
offre.columns=["we","seg","h","trains_par_jour"]
offre.to_csv(OUT/"B1d_offre_par_heure.csv", index=False)
w(f"Jours par type dans H24 : {ndays}. Valeur = nombre moyen de trains distincts desservant le segment par "
  f"heure et par jour (un train pleine ligne compte sur les deux segments aux heures ou il les parcourt).")
w()
# F7
fig,axes=plt.subplots(1,2,figsize=(6.3,3.4),sharey=True)
for ax_i,(grp,lettre) in zip(axes,[("ouvrable","a"),("week-end","b")]):
    for seg,col in [("bas",fs.COULEUR_BAS),("haut",fs.COULEUR_HAUT)]:
        s=offre[(offre.we==grp)&(offre.seg==seg)].set_index("h").trains_par_jour.reindex(range(24),fill_value=0)
        ax_i.plot(range(24), s.values, color=col, label=f"Segment {seg}")
    ax_i.set_xticks([0,6,9,12,15,18,21]); fs.lettre_panneau(ax_i,lettre)
    fs.finalize(ax_i, xlabel="Heure de départ (h)", ylabel="Trains par heure et par jour (nombre)")
axes[0].legend(loc="upper left", fontsize=8)
p7=FIG/"fig_4_3_11_F7_offre_par_heure.png"; fs.save(fig,p7); plt.close(fig)

# ====================================================================== BLOC 1e : structure des titres SIMBA
w("## Bloc 1e — Structure des titres de transport (SIMBA, usage exploratoire, millesime 2024)")
w()
sb=pd.read_parquet(SIMBA)
sb=sb[sb.simba_millesime==2024].copy()
sb["dep_o"]=sb.gare_depart.map(ABBR2ORD); sb["arr_o"]=sb.gare_arrivee.map(ABBR2ORD)
sb["seg"]=np.where((sb.dep_o>ORDRE_MAX_BAS)|(sb.arr_o>ORDRE_MAX_BAS),"haut","bas")
sb["w"]=sb.simba_voyageurs_dwv_total
def wmean(g,col):
    m=g[col].notna() & g.w.notna() & (g.w>0)
    return float(np.average(g[col][m], weights=g.w[m])) if m.sum()>0 else np.nan
titres=[]
for seg,g in sb.groupby("seg"):
    abo=wmean(g,"simba_part_ga")+wmean(g,"simba_part_mobilis")+wmean(g,"simba_part_abonnement")
    titres.append((seg, wmean(g,"simba_part_ga"), wmean(g,"simba_part_mobilis"), wmean(g,"simba_part_abonnement"),
                   abo, wmean(g,"simba_part_billet_hta"), wmean(g,"simba_part_spar"), wmean(g,"simba_part_jeunes"),
                   int(g.w.sum())))
tit=pd.DataFrame(titres,columns=["segment","part_ga","part_mobilis","part_autres_abonnements",
    "part_abonnements_total","part_billet_plein","part_billet_spar","part_jeunes","voyageurs_dwv"])
tit.to_csv(OUT/"B1e_structure_titres_simba.csv", index=False)
w("RESERVE D'USAGE (4.3.10) : SIMBA est a granularite annuelle, publie avec plusieurs mois de latence, et "
  "presente une circularite documentee avec l'APC ; ces chiffres ILLUSTRENT la composition des titres, ils ne "
  "demontrent rien seuls. Parts moyennes ponderees par les voyageurs DWV du millesime 2024.")
w()
w(md(tit.set_index("segment")))
w()

# ====================================================================== BLOC 2a : coincidence resa par severite
w("## Bloc 2a — Coincidence des reservations J-1 selon la severite (ml_dataset H22-H25)")
w()
sc=ml[ml.sc].copy()
sc["bande"]=pd.cut(sc.t, bins=[63,79,93,np.inf], labels=["64-79","80-93","94+"], right=True)
# grain troncon
g_tr=sc.groupby(["seg","bande"], observed=True).agg(n=("t","size"), avec_resa=("resa_pax_2c_J_minus_1", lambda s:int((s>0).sum())))
g_tr["part_avec_resa"]=g_tr.avec_resa/g_tr.n
g_tr.to_csv(OUT/"B2a_resa_par_severite_troncon.csv")
w("### Grain troncon : part des observations surchargees avec `resa_pax_2c_J_minus_1 > 0`, par bande de severite")
w(md(g_tr)); w()
# grain course : severite = charge max de la course
mlc=ml.groupby(["base_date","horaire_numero_train"]).agg(
    seg=("spatial_segment", lambda s:"haut" if (s=="haut").any() else "bas"),
    tmax=("t","max"), resa=("resa_pax_2c_J_minus_1", lambda s:int((s>0).any())), sc=("sc","any")).reset_index()
scc=mlc[mlc.sc].copy(); scc["bande"]=pd.cut(scc.tmax, bins=[63,79,93,np.inf], labels=["64-79","80-93","94+"], right=True)
g_co=scc.groupby(["seg","bande"], observed=True).agg(n=("tmax","size"), avec_resa=("resa","sum"))
g_co["part_avec_resa"]=g_co.avec_resa/g_co.n
g_co.to_csv(OUT/"B2a_resa_par_severite_course.csv")
w("### Grain course : part des courses surchargees (severite = charge max) avec au moins une reservation J-1")
w(md(g_co)); w()
# monotonie
def mono(g,seg):
    vals=[g.loc[(seg,b),"part_avec_resa"] for b in ["64-79","80-93","94+"] if (seg,b) in g.index]
    return all(vals[i]<=vals[i+1] for i in range(len(vals)-1)), vals
mt_h,_=mono(g_tr,"haut"); mt_b,_=mono(g_tr,"bas"); mc_h,_=mono(g_co,"haut"); mc_b,_=mono(g_co,"bas")
w(f"Monotonie croissante de la part avec reservation selon la severite : grain troncon haut={mt_h}, bas={mt_b} ; "
  f"grain course haut={mc_h}, bas={mc_b}.")
w()
# F8 (grain course, barres groupees bande x segment)
fig,ax=plt.subplots(figsize=(6.3,4.0))
bandes=["64-79","80-93","94+"]; x=np.arange(len(bandes)); ww=0.38
vb=[g_co.loc[("bas",b),"part_avec_resa"] if ("bas",b) in g_co.index else np.nan for b in bandes]
vh=[g_co.loc[("haut",b),"part_avec_resa"] if ("haut",b) in g_co.index else np.nan for b in bandes]
ax.bar(x-ww/2,[v*100 for v in vb],ww,color=fs.COULEUR_BAS,label="Segment bas")
ax.bar(x+ww/2,[v*100 for v in vh],ww,color=fs.COULEUR_HAUT,label="Segment haut")
ax.set_xticks(x); ax.set_xticklabels(["64 à 79","80 à 93","94 et plus"])
fs.finalize(ax, xlabel="Bande de charge de 2e classe (voyageurs)", ylabel="Part avec réservation J-1 (%)")
ax.legend()
p8=FIG/"fig_4_3_11_F8_resa_par_severite.png"; fs.save(fig,p8); plt.close(fig)

# ====================================================================== BLOC 2b : part surcharges en pointe
w("## Bloc 2b — Part des surcharges en pointe (grain troncon, ml_dataset H22-H25)")
w()
POINTE_OUV={6,7,8,16,17,18}; MIDI_HAUT={10,11,12,13,14,15,16}
sc_ouv=ml[(ml.sc)&(ml.we=="ouvrable")]
bas_ouv=sc_ouv[sc_ouv.seg=="bas"]; part_bas_pointe=(bas_ouv.h.isin(POINTE_OUV)).mean()
haut_all=ml[(ml.sc)&(ml.seg=="haut")]; part_haut_midi=(haut_all.h.isin(MIDI_HAUT)).mean()
w(f"Pointe ouvrable definie 6-8 h et 16-18 h (d'apres T3 : pics du bas a 7 h et 17 h). "
  f"Part des surcharges du BAS en jours ouvrables survenant en pointe = {part_bas_pointe:.4f} "
  f"({int((bas_ouv.h.isin(POINTE_OUV)).sum()):,}/{len(bas_ouv):,}). "
  f"Plage de milieu de journee du HAUT definie 10-16 h ; part des surcharges du HAUT (tous types de jour) "
  f"dans cette plage = {part_haut_midi:.4f} ({int((haut_all.h.isin(MIDI_HAUT)).sum()):,}/{len(haut_all):,}).")
w()

# ====================================================================== BLOC 3a : KS recompute
w("## Bloc 3a — Distribution changeante : tests KS entre annees horaires")
w()
w("Analyses existantes (localisees, provenance et statut) : "
  "(i) `notebooks/02_data_understanding_apc.ipynb` §5 cell 50-52 (matrice KS 10x10 + KDE) — statut HISTORIQUE "
  "(bandeau cell 0, anterieur au gel `416bb90b`), et porte sur `target_voyageurs_total`, PAS la cible 2e classe ; "
  "(ii) `docs/rapports/rapport_synthese_couche1.ipynb` cell 53/131 (KS + gaussian_kde H24 vs H25 sur la cible 2e "
  "classe, KS=0.029) — sur le hash `416bb90b` desormais supersede, sorties `.ipynb` videes ; "
  "(iii) `notebooks/06_feature_analysis_h22_h23_h24.ipynb` cell 6 (KS H22+H23 vs H24 = 0.1026) — HISTORIQUE. "
  "Aucune analyse KS/KDE par annee de la cible 2e classe n'existe sur `ba493568` : recalcul ci-dessous sur "
  "`apc_stacked` (perimetre H16-H25, avec la reserve du taux de comptage variable selon l'annee).")
w()
apc=pd.read_parquet(APC, columns=["base_date","target_voyageurs_2eme_classe","spatial_gare_depart_ordre","spatial_gare_arrivee_ordre"])
apc=apc[apc.target_voyageurs_2eme_classe.notna()].copy()
apc["annee"]=assign_annee(apc.base_date)
apc=apc[apc.annee!="?"]
apc["t"]=apc.target_voyageurs_2eme_classe.astype(float)
apc["seg"]=np.where((apc.spatial_gare_depart_ordre>ORDRE_MAX_BAS)|(apc.spatial_gare_arrivee_ordre>ORDRE_MAX_BAS),"haut","bas")
years=[f"H{n}" for n in range(16,26)]
def ksmat(sub):
    m=pd.DataFrame(index=years,columns=years,dtype=float)
    for i,a in enumerate(years):
        xa=sub[sub.annee==a].t.values
        for b in years:
            xb=sub[sub.annee==b].t.values
            if len(xa)>10 and len(xb)>10: m.loc[a,b]=ks_2samp(xa,xb).statistic
    return m
ks_glob=ksmat(apc); ks_glob.to_csv(OUT/"B3a_ks_global.csv")
w("### Matrice KS (statistique D) sur la charge 2e classe, toutes observations, apc_stacked H16-H25")
w(md(ks_glob)); w()
# consecutifs + H24-H25 par segment
cons=[(years[i],years[i+1]) for i in range(len(years)-1)]
rows=[]
for a,b in cons:
    r={"paire":f"{a}-{b}"}
    for seg,lab in [(None,"global"),("bas","bas"),("haut","haut")]:
        sub=apc if seg is None else apc[apc.seg==seg]
        xa=sub[sub.annee==a].t.values; xb=sub[sub.annee==b].t.values
        r[lab]=ks_2samp(xa,xb).statistic if len(xa)>10 and len(xb)>10 else np.nan
    rows.append(r)
ks_cons=pd.DataFrame(rows).set_index("paire"); ks_cons.to_csv(OUT/"B3a_ks_consecutifs_segment.csv")
w("### KS entre annees consecutives, global et par segment"); w(md(ks_cons)); w()

# ====================================================================== BLOC 3b : pre/post COVID
w("## Bloc 3b — Niveau de charge pre / post COVID (apc_stacked H16-H25)")
w()
w("Reserve : le taux de comptage APC varie fortement selon l'annee (H22 partiel) ; les moyennes par observation "
  "sont plus robustes que les totaux. Charge moyenne par course = somme de charge de la course, moyennee sur les courses.")
w()
apc["course"]=apc.base_date.astype(str)+"_"+apc.index.astype(str)  # placeholder, recalcule ci-dessous
# recharge avec numero_train pour la course
apc2=pd.read_parquet(APC, columns=["base_date","horaire_numero_train","target_voyageurs_2eme_classe","spatial_gare_depart_ordre","spatial_gare_arrivee_ordre"])
apc2=apc2[apc2.target_voyageurs_2eme_classe.notna()].copy()
apc2["annee"]=assign_annee(apc2.base_date); apc2=apc2[apc2.annee!="?"]
apc2["t"]=apc2.target_voyageurs_2eme_classe.astype(float)
apc2["seg"]=np.where((apc2.spatial_gare_depart_ordre>ORDRE_MAX_BAS)|(apc2.spatial_gare_arrivee_ordre>ORDRE_MAX_BAS),"haut","bas")
ann=apc2.groupby("annee").agg(obs=("t","size"), charge_totale=("t","sum"), charge_moy_troncon=("t","mean"))
crs=apc2.groupby(["annee","base_date","horaire_numero_train"]).t.sum().groupby("annee").mean().rename("charge_moy_course")
ann=ann.join(crs).reindex(years)
ann.to_csv(OUT/"B3b_niveau_annuel.csv")
w(md(ann)); w()
def gap(seg):
    d=apc2 if seg is None else apc2[apc2.seg==seg]
    pre=d[d.annee.isin(["H17","H18","H19"])].t.mean(); post=d[d.annee.isin(["H23","H24","H25"])].t.mean()
    return pre,post,(post-pre)/pre*100
for seg,lab in [(None,"global"),("bas","bas"),("haut","haut")]:
    pre,post,g=gap(seg)
    w(f"Ecart charge moyenne par troncon, {lab} : pre-COVID (H17-H19)={pre:.2f} vs post-COVID (H23-H25)={post:.2f}, "
      f"soit {g:+.2f} %.")
w()
# F9 : KDE par periode et par segment + courbe annuelle
periodes={"Pré-COVID (H16-H19)":["H16","H17","H18","H19"],"COVID (H20-H21)":["H20","H21"],"Post-COVID (H22-H25)":["H22","H23","H24","H25"]}
per_col={"Pré-COVID (H16-H19)":fs.COULEUR_BAS,"COVID (H20-H21)":"#999999","Post-COVID (H22-H25)":fs.COULEUR_HAUT}
def kde_sample(vals, cap=30000):
    v=vals[np.isfinite(vals)]
    if len(v)>cap: v=v[RNG.choice(len(v),cap,replace=False)]
    return v
fig,axes=plt.subplots(1,2,figsize=(6.6,3.6),sharey=True)
for ax_i,(seg,lettre) in zip(axes,[("bas","a"),("haut","b")]):
    for lab,yy in periodes.items():
        v=kde_sample(apc2[(apc2.seg==seg)&(apc2.annee.isin(yy))].t.values)
        if len(v)>50:
            sns.kdeplot(x=v, ax=ax_i, color=per_col[lab], label=lab, fill=True,
                        alpha=0.12, linewidth=1.8, clip=(0,None), bw_adjust=1.1, cut=0)
    ax_i.set_xlim(0,120); ax_i.grid(axis="x", visible=False); fs.lettre_panneau(ax_i,lettre)
    fs.finalize(ax_i, xlabel="Charge de 2e classe (voyageurs)", ylabel="Densité")
    fs.seuil_um_line(ax_i, orientation="v", annotate=False)
axes[0].legend(fontsize=8, loc="upper right")
p9=FIG/"fig_4_3_11_F9_kde_charge_periode.png"; fs.save(fig,p9); plt.close(fig)

# ====================================================================== BLOC 3c : rupture H24->H25
w("## Bloc 3c — Rupture H24 vers H25")
w()
hall=pd.read_parquet(HOR, columns=["annee_horaire","date","numero_train","gare_depart","gare_arrivee"])
n24=set(hall[hall.annee_horaire=="H24"].numero_train.unique()); n25=set(hall[hall.annee_horaire=="H25"].numero_train.unique())
nouv=n25-n24
h25=hall[hall.annee_horaire=="H25"].copy()
circ25=h25.drop_duplicates(["date","numero_train"])
part_circ_nouv=circ25.numero_train.isin(nouv).mean()
# sur ml_dataset (comptees)
ml25=ml[ml.horaire_annee_horaire=="H25"].drop_duplicates(["base_date","horaire_numero_train"])
part_ml_nouv=ml25.horaire_numero_train.isin(nouv).mean()
w(f"Numeros de train : {len(n24)} distincts en H24, {len(n25)} en H25 ; {len(nouv)} numeros de H25 "
  f"absents de H24 (en numeros distincts). En VOLUME de courses planifiees (horaires_clean H25) : "
  f"{part_circ_nouv:.4f} des courses H25 portent un numero absent de H24 "
  f"({int(circ25.numero_train.isin(nouv).sum()):,}/{len(circ25):,}). Sur les courses COMPTEES (ml_dataset H25) : "
  f"{part_ml_nouv:.4f} ({int(ml25.horaire_numero_train.isin(nouv).sum()):,}/{len(ml25):,}).")
w()
# gares par annee horaire
gares_an={}
for an in years:
    sub=hall[hall.annee_horaire==an]
    gares_an[an]=set(sub.gare_depart.unique())|set(sub.gare_arrivee.unique())
rowsg=[]
prev=None
for an in years:
    g=gares_an.get(an,set())
    if not g: continue
    added=g-prev if prev is not None else set()
    removed=prev-g if prev is not None else set()
    rowsg.append((an, len(g), ",".join(sorted(added)) if added else "", ",".join(sorted(removed)) if removed else ""))
    prev=g
gares_df=pd.DataFrame(rowsg,columns=["annee_horaire","n_gares","gares_ajoutees","gares_retirees"])
gares_df.to_csv(OUT/"B3c_gares_par_annee.csv", index=False)
w("### Gares actives par annee horaire (apparitions / disparitions, horaires_clean)")
w(md(gares_df.set_index("annee_horaire"))); w()

# ====================================================================== BLOC 4 : ADR
w("## Bloc 4 — Balayage des ADR : constats additionnels et cartographie constat vers decisions")
w()
w("Rappel des quatre constats canoniques : C1 deux regimes structurels (bas pendulaire / haut touristique) ; "
  "C2 cible rare mais non aleatoire ; C3 distribution changeante ; C4 asymetrie J-1.")
w()
w("### 4a — Constats additionnels (hors des quatre canoniques)")
w()
w("Trois constats de comprehension des donnees ne se reduisent a aucun des quatre et sont **candidats a la "
  "synthese 4.3.11** :")
w("- **Defaut structurel de couverture APC en H22** (« artefact de format ») : le taux de comptage "
  "course-a-course de H22 chute a environ 48,9 %, avec une variabilite intra-annuelle extreme (9 % en septembre "
  "2022, 83 % en juillet 2022), sans biais de selection detecte sur creneau, type de jour ou segment, cause non "
  "entierement elucidee. Provenance : ADR-065 (renvoi `02_data_understanding_apc.ipynb`), corrobore ADR-035, "
  "ADR-039, ADR-073. Distinct du trou de distribution C3 (trou de mesure, pas changement de regime de charge).")
w("- **Profil altimetrique marque et denivele signe du tronçon** : la ligne monte de Vevey (386 m) aux Pleiades "
  "(1348 m), soit 962 m sur environ 11 km ; deniveles de tronçon signes de -153,9 m a +153,9 m, forte "
  "heterogeneite intra-segment. Provenance : ADR-057. Dimension topologique orthogonale a l'opposition bas/haut, "
  "sous-tend la feature denivele (cf. gradients B1c).")
w("- **Refonte d'horaire de decembre 2024 comme rupture d'identite des services** : au passage H24 vers H25 "
  "environ la moitie des trains sont renumerotes, ce qui casse l'appariement par numero de train entre historique "
  "et cible. Provenance : ADR-041, corrobore ADR-042, ADR-047. Rupture d'appariement d'entites, distincte de la "
  "derive de charge C3 (cf. B3c : 43,66 % des courses H25 a numero nouveau).")
w()
w("Faits deja couverts par C1-C4 (tracabilite, non additionnels) : divergence de distribution bas/haut "
  "KS≈0,456 (ADR-003, C1) ; desequilibre extreme de la cible 341:1 en H24 (ADR-030/031, C2) ; reservations "
  "signal du haut 62/104 (ADR-035, C2) ; clusters pre/COVID/post-COVID et KS inter-annees (ADR-002/027, C3) ; "
  "contamination `base_offre` par transition materielle (ADR-034, C3) ; latence mensuelle APC (ADR-062, C4) ; "
  "instabilite SIMBA r=0,056 (ADR-026/056/061, C4) ; representativite STATPOP Z-2 (ADR-063/075, C4).")
w()
w("Motivations locales de section 4.4 (vivent deja en preparation, pas besoin de la synthese) : couverture VMCV "
  "20 % (ADR-021) ; redondance geographique STATENT (ADR-064) ; shift d'instrumentation neige avant 2023 "
  "(ADR-022 §6) ; redondance arithmetique STATPOP (ADR-024).")
w()
w("### 4b — Cartographie constat vers decisions")
w()
w("Identifiants verifies contre `docs/adr/INDEX.md`. La colonne « section memoire » est un rattachement de "
  "niveau (4.4 preparation / chapitre modelisation / couche 2) infere des notebooks cites par chaque ADR, a "
  "confirmer contre le plan reel du memoire. ADR-032 est revoque (par ADR-034) et ecarte. ADR-030 et ADR-049 "
  "apparaissent sous C1 et C2 (motivation conjointe, signale).")
w()
CARTO = [
 ("C1 deux regimes", "ADR-003 architecture (modele unique + base_segment)", "chapitre modelisation"),
 ("C1 deux regimes", "ADR-030 revision strategie (decouplage R2/rappel)", "chapitre modelisation"),
 ("C1 deux regimes", "ADR-031 verdict classe rare + exploration segmentation", "chapitre modelisation"),
 ("C1 deux regimes", "ADR-049 cadrage bas/haut (seuils par segment)", "couche 2 / decision"),
 ("C1 deux regimes", "ADR-052 modele final Enrichi_Seg (segmente)", "chapitre modelisation"),
 ("C1 deux regimes", "ADR-057 denivele signe du tronçon", "4.4 preparation"),
 ("C1 deux regimes", "ADR-028 meteo par station/segment", "4.4 preparation"),
 ("C1 deux regimes", "ADR-029 reclassification zonale evenements", "4.4 preparation"),
 ("C2 cible rare", "ADR-005 / ADR-060 seuil de surcharge (94 -> 63)", "4.4 preparation"),
 ("C2 cible rare", "ADR-030 formulation orientee detection classe rare", "chapitre modelisation"),
 ("C2 cible rare", "ADR-046 critere de calibration du seuil (Walk-Forward)", "couche 2 / decision"),
 ("C2 cible rare", "ADR-049 strategie de seuil (angle mort du bas)", "couche 2 / decision"),
 ("C2 cible rare", "ADR-050 grille regression + sample weighting", "chapitre modelisation"),
 ("C2 cible rare", "ADR-035 / ADR-036 integration reservations groupes", "4.4 prep / modelisation"),
 ("C2 cible rare", "ADR-051 / ADR-069 pertes alternatives (ecartees, MSE conservee)", "chapitre modelisation"),
 ("C3 distribution changeante", "ADR-002 / ADR-027 split temporel (KS, clusters COVID)", "4.4 preparation / split"),
 ("C3 distribution changeante", "ADR-065 Split C : exclusion tronçons Gilamont H22", "4.4 preparation / split"),
 ("C3 distribution changeante", "ADR-038 extension du perimetre a H25", "4.4 preparation / split"),
 ("C3 distribution changeante", "ADR-037 grain enrichi histo_* (type_jour + service)", "4.4 preparation"),
 ("C3 distribution changeante", "ADR-041 gestion refonte horaire H24->H25 (SIMBA)", "4.4 preparation"),
 ("C3 distribution changeante", "ADR-016 stabilite des numeros de train R35", "4.4 preparation"),
 ("C3 distribution changeante", "ADR-034 perimetre base_offre (transition materielle)", "4.4 preparation / diagnostic"),
 ("C4 asymetrie J-1", "ADR-062 cutoff mensuel causal APC", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-008 / ADR-015 lag J-2 (APC / ISTDATEN)", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-022 disponibilite J-1 + strategie meteo", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-063 causalite STATPOP (Z-2, forward-fill)", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-064 STATENT (mapping Z-3)", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-067 headway sur grille planifiee (J-1)", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-061 / ADR-026 SIMBA (retrait, lag N-1)", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-040 interruption VMCV H25", "4.4 preparation"),
 ("C4 asymetrie J-1", "ADR-006 / ADR-011 STATPOP dernier millesime / imputation causale", "4.4 preparation"),
]
w(md(pd.DataFrame(CARTO, columns=["Constat","ADR (id + titre court)","Section memoire"]).set_index("Constat")))
w()

# ====================================================================== chiffres candidats
w("## Chiffres candidats pour la prose (provenance complete)")
w()
def pct(n,d): return f"{n/d*100:.2f} % ({n:,}/{d:,})"
C=[]
C.append(f"1. [B1a] Charge 2e classe mediane bas={seg_prof.loc['bas','mediane']:.1f} vs haut={seg_prof.loc['haut','mediane']:.1f} voyageurs ; 90e centile bas={seg_prof.loc['bas','p90']:.1f} vs haut={seg_prof.loc['haut','p90']:.1f} (ml_dataset H22-H25, table B1a).")
C.append(f"2. [B1a] Le segment bas porte {pct(int(bas_charge),int(tot_charge))} de la charge 2e classe totale de la ligne (H22-H25).")
C.append(f"3. [B1a] Symetrie des sens : correlation des medianes par troncon = {sym_corr:.3f} (ecart max {sym_maxdiff:.0f} voyageurs).")
C.append(f"4. [B1b] Concentration horaire (part des 3 heures les plus chargees) : bas ouvrable={conc.set_index(['segment','type_jour']).loc[('bas','ouvrable'),'part_top3_heures']:.3f} vs haut ouvrable={conc.set_index(['segment','type_jour']).loc[('haut','ouvrable'),'part_top3_heures']:.3f} (table B1b).")
C.append(f"5. [B1b] Entropie horaire normalisee bas ouvrable={conc.set_index(['segment','type_jour']).loc[('bas','ouvrable'),'entropie_normalisee']:.3f} vs haut ouvrable={conc.set_index(['segment','type_jour']).loc[('haut','ouvrable'),'entropie_normalisee']:.3f} (1 = etale, 0 = concentre).")
C.append(f"6. [B1c] Population 500 m moyenne bas={rp['bas']:.0f} vs haut={rp['haut']:.0f} habitants (ratio {rp['bas']/rp['haut']:.1f}), STATPOP dernier millesime.")
C.append(f"7. [B1c] Emplois 500 m moyenne bas={re['bas']:.0f} vs haut={re['haut']:.0f} (ratio {re['bas']/re['haut']:.1f}), STATENT dernier millesime.")
C.append(f"8. [B1e] SIMBA 2024 : part d'abonnements (GA+Mobilis+autres) bas={tit.set_index('segment').loc['bas','part_abonnements_total']:.3f} vs haut={tit.set_index('segment').loc['haut','part_abonnements_total']:.3f} ; part GA bas={tit.set_index('segment').loc['bas','part_ga']:.3f} vs haut={tit.set_index('segment').loc['haut','part_ga']:.3f} (usage exploratoire, reserve 4.3.10).")
for b in ["64-79","80-93","94+"]:
    if ("haut",b) in g_co.index:
        C.append(f"9.{b} [B2a] Grain course, segment haut, bande {b} : part avec reservation J-1 = {g_co.loc[('haut',b),'part_avec_resa']:.4f} ({int(g_co.loc[('haut',b),'avec_resa'])}/{int(g_co.loc[('haut',b),'n'])}).")
C.append(f"10. [B2b] {pct(int((bas_ouv.h.isin(POINTE_OUV)).sum()),len(bas_ouv))} des surcharges du bas en jours ouvrables surviennent en pointe (6-8 h, 16-18 h).")
C.append(f"11. [B2b] {pct(int((haut_all.h.isin(MIDI_HAUT)).sum()),len(haut_all))} des surcharges du haut surviennent en milieu de journee (10-16 h).")
C.append(f"12. [B3a] KS charge 2e classe H23-H24 (global) = {ks_cons.loc['H23-H24','global']:.4f} ; H24-H25 = {ks_cons.loc['H24-H25','global']:.4f} (apc_stacked).")
C.append(f"13. [B3a] KS H16 vs H22 (global) = {ks_glob.loc['H16','H22']:.4f} ; H20 vs H24 = {ks_glob.loc['H20','H24']:.4f} (rupture COVID).")
pre,post,gg=gap(None)
C.append(f"14. [B3b] Charge moyenne par troncon post-COVID (H23-H25)={post:.2f} vs pre-COVID (H17-H19)={pre:.2f}, soit {gg:+.2f} %.")
C.append(f"15. [B3c] {part_circ_nouv*100:.2f} % des courses planifiees H25 portent un numero absent de H24 ({int(circ25.numero_train.isin(nouv).sum()):,}/{len(circ25):,}).")
for c in C: w(c)
w()

# ====================================================================== legendes figures
w("## Figures produites (legendes candidates, classification corps/atlas)")
w()
FIGS=[
 ("F4","fig_4_3_11_F4_profil_charge_troncon.png","Profil de charge de 2e classe le long de la ligne (Vevey aux Pléiades)",
  "Source : ml_dataset R35, gel ba493568, H22-H25, grain troncon. Table B1a. Mediane, moyenne et 90e centile de "
  "target_voyageurs_2eme_classe par troncon physique (deux sens agreges), ordonnes par position. Trait pointille "
  "= frontiere segment bas / segment haut ; trait tirete = seuil 63 (D1). Structurante (corps)."),
 ("F5","fig_4_3_11_F5_concentration_horaire.png","Profil horaire normalise de la charge, par segment et type de jour",
  "Source : ml_dataset ba493568, H22-H25, grain troncon. Table B1b. Part de la charge 2e classe journaliere par heure "
  "de depart, (a) jours ouvrables, (b) week-end. Denominateur = charge totale de la cellule. Support (atlas EDA)."),
 ("F6","fig_4_3_11_F6_carte_pop_emploi.png","Carte de la ligne R35 : population et intensite d'emploi par gare",
  "Source : dim_gare (coordonnees WGS84), statpop_clean_causal et statent_clean_causal (dernier millesime), gel ba493568 ; table B1c. "
  "Bulles dimensionnees par la population dans 500 m (STATPOP) ; couleur = taux d'emploi (emplois EPT par habitant dans 500 m, STATENT) ; "
  "trace = ligne R35 dans l'ordre des gares. Fond de carte CartoDB Voyager (© OpenStreetMap, © CARTO). Figure geospatiale HORS chaine "
  "byte-reproductible (tuiles externes), produite par le script dedie carte_gares_pop_emploi.py. Structurante (corps)."),
 ("F7","fig_4_3_11_F7_offre_par_heure.png","Reponse de l'offre : trains planifies par heure et par segment (H24)",
  "Source : horaires_clean, annee horaire H24 (371 jours). Table B1d. Nombre moyen de trains distincts desservant le "
  "segment par heure et par jour, (a) jours ouvrables, (b) week-end. Support (atlas EDA)."),
 ("F8","fig_4_3_11_F8_resa_par_severite.png","Coincidence des reservations J-1 selon la severite de la surcharge (grain course)",
  "Source : ml_dataset ba493568, H22-H25, grain course. Table B2a. Part des courses surchargees (severite = charge max) "
  "coincidant avec au moins une reservation resa_pax_2c_J_minus_1 > 0, par bande de charge et par segment. "
  "Sans lien causal. Structurante (corps) si la relation est monotone."),
 ("F9","fig_4_3_11_F9_kde_charge_periode.png","Densite de la charge de 2e classe par periode et par segment",
  "Source : apc_stacked, H16-H25 (perimetre secondaire, taux de comptage variable). Table B3a/B3b. Densites (KDE) "
  "de target_voyageurs_2eme_classe pour (a) segment bas, (b) segment haut, par periode pre-COVID / COVID / post-COVID ; "
  "trait tirete = seuil 63. Echantillon KDE plafonne a 30 000 par groupe (graine fixe). Structurante (corps)."),
]
for code,fn,titre,note in FIGS:
    w(f"### {code} — `{fn}`")
    w(f"Titre (au-dessus, Word) : « {titre} ».")
    w(f"Note de source (en-dessous) : {note}")
    w()

Path(OUT/"rapport_enrichissement_ba493568.md").write_text("\n".join(lines), encoding="utf-8")
print("REPORT ecrit :", OUT/"rapport_enrichissement_ba493568.md")
for p in [p4,p5,p7,p8,p9]: print("FIGURE:", p.name, "OK")
print("FIGURE: fig_4_3_11_F6_carte_pop_emploi.png (script dedie carte_gares_pop_emploi.py)")
print("DONE")
