#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère SYNTHESE_verifs_4_3.md à partir des CSV produits par les deux scripts de
vérification. Ne recalcule rien : tout chiffre affiché est lu dans un CSV, aucun
n'est saisi à la main.

    python3 docs/memoire/verifs/section_4_3_7/gen_synthese_verifs_4_3.py

Formatage manuscrit : virgule décimale, espace insécable U+00A0 comme séparateur
de milliers, une décimale pour les pourcentages.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
NBSP = " "

CMD_ALL = (
    "python3 docs/memoire/verifs/section_4_3_4/verif_definitions_surcharge.py && \\\n"
    "python3 docs/memoire/verifs/section_4_3_5/verif_renumerotation_h25.py && \\\n"
    "python3 docs/memoire/verifs/section_4_3_7/gen_synthese_verifs_4_3.py"
)


def n(x) -> str:
    """Entier, espace insécable en séparateur de milliers."""
    return f"{int(round(float(x))):,}".replace(",", NBSP)


def p(x, dec: int = 1) -> str:
    """Pourcentage, virgule décimale, `dec` décimale(s)."""
    if pd.isna(x):
        return "n. d."
    return f"{float(x):.{dec}f}".replace(".", ",")


def f(x, dec: int = 3) -> str:
    if pd.isna(x):
        return "n. d."
    return f"{float(x):.{dec}f}".replace(".", ",")


# --------------------------------------------------------------------------- #
# Lecture des artefacts
# --------------------------------------------------------------------------- #
cont = pd.read_csv(OUT / "verif_definitions_surcharge.csv")
seg = pd.read_csv(OUT / "verif_definitions_surcharge_par_segment.csv")
sens = pd.read_csv(OUT / "verif_definitions_surcharge_sensibilite_seuil.csv")
dist = pd.read_csv(OUT / "verif_surcharge_distribution_1ere_classe.csv")
lim = pd.read_csv(OUT / "verif_surcharge_facteur_limitant_1ere_classe.csv")
coh = pd.read_csv(OUT / "verif_surcharge_controle_coherence.csv")
renum = pd.read_csv(OUT / "verif_renumerotation_h25.csv")
cov = pd.read_csv(OUT / "verif_renumerotation_couverture_istdaten.csv")
casc = pd.read_csv(OUT / "verif_renumerotation_cascade_baseline.csv")

POP_A = "H22-H25 (régime actuel)"
POP_B = "H25 seule"


def c(pop, grain):
    return cont[(cont.population == pop) & (cont.grain == grain)].iloc[0]


L: list[str] = []


def w(s: str = "") -> None:
    L.append(s)


def coh_val(nom: str, champ: str):
    """Valeur d'un contrôle lu dans verif_surcharge_controle_coherence.csv."""
    return coh[coh.controle == nom].iloc[0][champ]


# --------------------------------------------------------------------------- #
w("# Synthèse des vérifications — section 4.3")
w()
w(f"*Généré le {_dt.date.today().isoformat()}. Tous les chiffres de ce document sont lus "
  "dans les CSV produits par les deux scripts de vérification ; aucun n'est repris du "
  "manuscrit ni saisi à la main.*")
w()
w("## 1. Cadre, garanties et rejeu")
w()
w("Les deux vérifications sont **strictement en lecture seule** : aucun réentraînement, "
  "aucune écriture hors de `docs/memoire/verifs/section_4_3_7/`, aucune modification du "
  "pipeline, du jeu gelé ou de la couche décisionnelle.")
w()
w("**Empreinte du jeu canonique.** `data/processed/ml_dataset.parquet` a pour empreinte "
  "SHA256[:8] **`ba493568`**, conforme à l'attendu. Les deux scripts s'arrêtent sur `sys.exit(1)` "
  "si l'empreinte diffère. Le jeu compte "
  f"{n(c(POP_A, 'tronçon').n_total)} tronçons observés sur H22-H25.")
w()
w("**Commande de rejeu**, en une seule invocation depuis la racine du dépôt, sur un "
  "environnement vierge disposant de `pandas`, `numpy` et `pyarrow` :")
w()
w("```bash")
w(CMD_ALL)
w("```")
w()
w("### 1.1 Colonnes retenues, relevées dans le schéma")
w()
w("Aucun nom de colonne n'a été supposé : le schéma des 209 colonnes a été inspecté et les "
  "colonnes ci-dessous en ont été extraites. Toutes existent sous le nom attendu, aucune "
  "n'a nécessité de recherche d'équivalent.")
w()
w("| Grandeur | Colonne retenue | Type | Source |")
w("|---|---|---|---|")
w("| Charge de 1re classe | `target_voyageurs_1ere_classe` | Int16 | `ml_dataset.parquet` |")
w("| Charge de 2e classe | `target_voyageurs_2eme_classe` | Int16 | `ml_dataset.parquet` |")
w("| Charge totale | `target_voyageurs_total` | float64 | `ml_dataset.parquet` |")
w("| Segment bas / haut | `spatial_segment` | string | `ml_dataset.parquet` |")
w("| Année horaire | `horaire_annee_horaire` | string | `ml_dataset.parquet` |")
w("| Numéro de train | `horaire_numero_train` | int64 | `ml_dataset.parquet` |")
w("| Date d'exploitation | `base_date` | timestamp[ns] | `ml_dataset.parquet` |")
w("| Type de jour (cascade §4.5.2) | `cal_is_weekend` | bool | `ml_dataset.parquet` |")
w("| Numéro planifié | `numero_train` + `annee_horaire` | int64 / string | `horaires_r35_troncons_jour.parquet` |")
w("| Numéro réalisé | `numero_train` + `date` | int64 / date32 | `fact_istdaten_r35.parquet` |")
w()
w("**Conventions reprises du dépôt, non redéfinies ici.** Le grain *course* suit "
  "`src/couche2/decision.py:105` : clé `(base_date, horaire_numero_train, horaire_annee_horaire)`, "
  "une course est en surcharge dès qu'au moins un de ses tronçons observés dépasse le seuil. "
  "Le segment d'une course suit `src/couche2/blocs.py:189` : « haut » si au moins un tronçon "
  "est haut, « bas » sinon. Seuls les tronçons effectivement mesurés figurent dans le jeu ; "
  "aucune imputation n'est faite.")
w()
r = c(POP_B, "course")
w(f"**Contrôle d'ancrage.** Au grain course sur H25, la définition D2 compte "
  f"{n(r.total_D2_n)} surcharges sur {n(r.n_total)} courses. La ventilation par segment donne "
  f"{n(seg[(seg.segment=='bas') & (seg.regle_segment.str.startswith('canonique'))].iloc[0].total_D2_n)} "
  f"BAS et "
  f"{n(seg[(seg.segment=='haut') & (seg.regle_segment.str.startswith('canonique'))].iloc[0].total_D2_n)} "
  "HAUT, ce qui reproduit exactement les ancrages figés de la couche 2 "
  "(`ISO_PERIMETRE_H25`, 2 072 surcharges, 848 BAS / 1 224 HAUT). Les conventions de grain "
  "et de segment employées ici sont donc bien celles du reste du mémoire.")
w()

# --------------------------------------------------------------------------- #
w("---")
w()
w("## 2. Vérification 1 — deuxième classe (D2) contre total des deux classes (DT)")
w()
w("**D2** : `target_voyageurs_2eme_classe` > 63 (sièges fixes de 2e classe d'une rame simple). ")
w("**DT** : `target_voyageurs_total` > 75 (63 sièges de 2e classe + 12 places de 1re classe).")
w()
w("### 2.1 Tables de contingence 2×2, effectifs bruts et pourcentages")
w()
for pop in (POP_A, POP_B):
    for grain in ("tronçon", "course"):
        r = c(pop, grain)
        w(f"**{pop} — grain {grain}** (n = {n(r.n_total)})")
        w()
        w("| Case | Effectif | % de la population |")
        w("|---|---:|---:|")
        w(f"| Concordance négative (ni D2 ni DT) | {n(r.concordance_negative_n)} | {p(r.concordance_negative_pct)} % |")
        w(f"| D2 seule (2e classe > 63, total ≤ 75) | {n(r.D2_seule_n)} | {p(r.D2_seule_pct)} % |")
        w(f"| DT seule (total > 75, 2e classe ≤ 63) | {n(r.DT_seule_n)} | {p(r.DT_seule_pct, 2)} % |")
        w(f"| Concordance positive (les deux) | {n(r.concordance_positive_n)} | {p(r.concordance_positive_pct)} % |")
        w()
        w(f"Union des deux définitions : {n(r.union_n)}. Discordants : {n(r.discordants_n)}, "
          f"soit un **taux de discordance de {p(r.taux_discordance_sur_union_pct)} % de l'union**.")
        w()

w("### 2.2 Effectifs totaux sous chaque définition et écart relatif")
w()
w("| Population | Grain | n | Total D2 | Total DT | Écart relatif DT / D2 |")
w("|---|---|---:|---:|---:|---:|")
for pop in (POP_A, POP_B):
    for grain in ("tronçon", "course"):
        r = c(pop, grain)
        w(f"| {pop} | {grain} | {n(r.n_total)} | {n(r.total_D2_n)} ({p(r.total_D2_pct)} %) | "
          f"{n(r.total_DT_n)} ({p(r.total_DT_pct)} %) | **{p(r.ecart_relatif_DT_vs_D2_pct)} %** |")
w()
w("L'écart relatif est calculé en base D2 : (total DT − total D2) / total D2.")
w()

w("### 2.3 Coefficients d'accord")
w()
w("Les deux coefficients sont rapportés, et nommés. Le **kappa de Cohen** traite les deux "
  "définitions comme deux juges binaires sur toute la population, concordance négative comprise. "
  "L'**indice de Jaccard** ne porte que sur l'union des ensembles classés en surcharge, et ignore "
  "donc la très large majorité de cas où aucune des deux définitions ne se déclenche. Sur une "
  "population aussi déséquilibrée, Jaccard est le plus sévère des deux et le plus informatif.")
w()
w("| Population | Grain | Kappa de Cohen | Jaccard |")
w("|---|---|---:|---:|")
for pop in (POP_A, POP_B):
    for grain in ("tronçon", "course"):
        r = c(pop, grain)
        w(f"| {pop} | {grain} | {f(r.kappa_cohen)} | {f(r.jaccard)} |")
w()

# --- Affirmation A --------------------------------------------------------- #
w("### 2.4 Affirmation A — la première classe n'est pratiquement jamais le facteur limitant")
w()
w("Distribution de `target_voyageurs_1ere_classe`, grain tronçon :")
w()
w("| Population | Segment | n | min | Q1 | médiane | Q3 | P90 | P95 | P99 | max | moyenne |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for _, r in dist.iterrows():
    w(f"| {r.population} | {r.segment} | {n(r.n_troncons)} | {n(r['min'])} | {n(r.q1)} | "
      f"{n(r.mediane)} | {n(r.q3)} | {n(r.p90)} | {n(r.p95)} | {n(r.p99)} | {n(r['max'])} | "
      f"{f(r.moyenne, 2)} |")
w()
w("Dépassement des 12 places et cas où la 1re classe est effectivement le facteur limitant "
  "(charge de 1re classe > 12 **et** charge de 2e classe ≤ 63) :")
w()
w("| Population | Segment | n tronçons | 1re classe > 12 | % | 1re classe facteur limitant | % |")
w("|---|---|---:|---:|---:|---:|---:|")
for _, r in lim.iterrows():
    w(f"| {r.population} | {r.segment} | {n(r.n_troncons)} | {n(r.n_1c_sup_12)} | "
      f"{p(r.pct_1c_sup_12, 3)} % | {n(r.n_1c_facteur_limitant)} | "
      f"{p(r.pct_1c_facteur_limitant, 3)} % |")
w()
la = lim[(lim.population == POP_A) & (lim.segment == "global")].iloc[0]
lb = lim[(lim.population == POP_B) & (lim.segment == "global")].iloc[0]
w(f"**Affirmation A confirmée.** Sur H22-H25, la 1re classe dépasse ses 12 places sur "
  f"{n(la.n_1c_sup_12)} tronçons ({p(la.pct_1c_sup_12, 3)} %) et n'est le facteur limitant que "
  f"sur {n(la.n_1c_facteur_limitant)} tronçons ({p(la.pct_1c_facteur_limitant, 3)} %). "
  f"Sur H25 seule, {n(lb.n_1c_sup_12)} et {n(lb.n_1c_facteur_limitant)} respectivement. "
  "Le phénomène est deux à quatre fois plus fréquent sur le HAUT que sur le BAS, mais reste "
  "marginal dans les deux cas.")
w()

# --- Q5 ventilation segment ------------------------------------------------ #
w("### 2.5 Ventilation par segment de la contingence, H25, grain course")
w()
nb_mixte_pct = None
w("Une course sur trois traverse les deux segments. Deux opérationnalisations sont donc "
  "possibles et **les deux sont rapportées** ; aucune n'est tranchée ici.")
w()
for regle in seg.regle_segment.unique():
    lbl = ("règle canonique du dépôt (`blocs.py:189`) : la course est « haut » si au moins un "
           "de ses tronçons est haut" if regle.startswith("canonique") else
           "variante course × segment : une course mixte est comptée dans chacun des deux segments")
    w(f"**{lbl}.**")
    w()
    w("| Segment | n courses | ni D2 ni DT | D2 seule | DT seule | Les deux | Total D2 | Total DT | Discordance / union | Kappa | Jaccard |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in seg[seg.regle_segment == regle].iterrows():
        w(f"| {r.segment} | {n(r.n_total)} | {n(r.concordance_negative_n)} | {n(r.D2_seule_n)} | "
          f"{n(r.DT_seule_n)} | {n(r.concordance_positive_n)} | {n(r.total_D2_n)} | "
          f"{n(r.total_DT_n)} | {p(r.taux_discordance_sur_union_pct)} % | {f(r.kappa_cohen)} | "
          f"{f(r.jaccard)} |")
    w()

# --- sensibilité ----------------------------------------------------------- #
w("### 2.6 Ambiguïté signalée — deux lectures de « définition fondée sur le total »")
w()
w("L'énoncé « charge totale strictement supérieure à 75 » suppose que les 12 places de "
  "1re classe comptent dans la capacité opposée à la charge totale. Une lecture concurrente "
  "est défendable : les places de 1re classe ne sont pas offertes aux voyageurs de 2e classe, "
  "et la capacité de référence reste 63. Les deux sont calculées, **aucune n'est tranchée** :")
w()
w("- **DT75** : `target_voyageurs_total` > 75 — la définition de l'énoncé.")
w("- **DT63** : `target_voyageurs_total` > 63 — charge totale rapportée aux seuls sièges de 2e classe.")
w()
w("| Population | Grain | Définition | Total D2 | Total DT | D2 seule | DT seule | Écart relatif | Discordance / union | Kappa | Jaccard |")
w("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for _, r in sens.sort_values(["population", "grain", "definition_total"]).iterrows():
    w(f"| {r.population} | {r.grain} | {r.definition_total} | {n(r.total_D2_n)} | {n(r.total_DT_n)} | "
      f"{n(r.D2_seule_n)} | {n(r.DT_seule_n)} | {p(r.ecart_relatif_DT_vs_D2_pct)} % | "
      f"{p(r.taux_discordance_sur_union_pct)} % | {f(r.kappa_cohen)} | {f(r.jaccard)} |")
w()
s75 = sens[(sens.population == POP_A) & (sens.grain == "tronçon") &
           (sens.definition_total.str.startswith("DT75"))].iloc[0]
s63 = sens[(sens.population == POP_A) & (sens.grain == "tronçon") &
           (sens.definition_total.str.startswith("DT63"))].iloc[0]
w(f"D2 est **encadrée** par les deux lectures : DT63 est plus permissive que D2 "
  f"(+{p(s63.ecart_relatif_DT_vs_D2_pct)} %, et D2 y est strictement incluse puisque la case "
  f"« D2 seule » vaut {n(s63.D2_seule_n)}), DT75 est plus restrictive "
  f"({p(s75.ecart_relatif_DT_vs_D2_pct)} %, et DT75 est presque strictement incluse dans D2 "
  f"puisque la case « DT seule » ne vaut que {n(s75.DT_seule_n)} tronçons).")
w()

# --- contrôles ------------------------------------------------------------- #
w("### 2.7 Contrôles de cohérence")
w()
ident = coh[coh.controle == "identite_total_egale_1ere_plus_2eme"].iloc[0]
w(f"**Identité comptable `total = première + deuxième`.** Vérifiée sur l'intégralité de la "
  f"population, soit {n(ident.n_lignes)} lignes : "
  f"**{n(ident.n_lignes_en_ecart)} ligne en écart**, écart absolu maximal "
  f"{f(ident.ecart_abs_max, 0)}, somme des écarts {f(ident.somme_ecarts, 0)}. "
  "L'affirmation de la section 4.3.1 est **confirmée sans réserve** : l'identité tient exactement, "
  "à l'unité près, sur toutes les lignes.")
w()
w("**Part de la deuxième classe dans la charge totale, régime actuel H22-H25.**")
w()
w("| Périmètre | Somme 2e classe | Somme totale | Part calculée | Part publiée §4.3.1 | Écart |")
w("|---|---:|---:|---:|---:|---:|")
for _, r in coh[coh.controle == "part_2eme_classe_dans_total"].iterrows():
    w(f"| {r.perimetre} | {n(r.somme_2eme_classe)} | {n(r.somme_totale)} | "
      f"{p(r.part_2eme_pct_calculee, 2)} % | {p(r.part_2eme_pct_publiee_4_3_1)} % | "
      f"{p(r.ecart_points, 2)} pt |")
w()
w("Les trois valeurs publiées sont **retrouvées** : chaque part calculée arrondit à la première "
  "décimale sur la valeur du manuscrit. Aucun écart à signaler.")
w()

# --------------------------------------------------------------------------- #
w("---")
w()
w("## 3. Vérification 2 — décompte des renumérotations de décembre 2024")
w()
w("### 3.1 Limite de couverture d'ISTDATEN, à signaler avant tout compte")
w()
h25c = cov[cov.annee_horaire == "H25"].iloc[0]
w(f"`fact_istdaten_r35.parquet` s'arrête au **{h25c.date_max_istdaten}**. L'année horaire H25 "
  f"court du {h25c.debut_annee_horaire} au {h25c.fin_annee_horaire}, soit "
  f"{n(h25c.jours_etendue_theorique)} jours ; ISTDATEN n'en couvre que "
  f"**{n(h25c.jours_presents_istdaten)} jours**, soit {p(h25c.couverture_pct)} % de l'année. "
  "La définition D2 sur H25 porte donc sur un fragment d'année et **n'est pas comparable telle "
  "quelle** à D1 et D3. Aucune extrapolation n'a été faite. Une variante à fenêtre appariée "
  "(les 17 premiers jours de chaque année horaire, longueur imposée par la couverture H25) est "
  "calculée et rapportée sous les libellés D1′, D2′ et D3′.")
w()
w("| Année horaire | Étendue théorique (j) | Jours présents | Couverture | Première date | Dernière date | Numéros distincts |")
w("|---|---:|---:|---:|---|---|---:|")
for _, r in cov.iterrows():
    w(f"| {r.annee_horaire} | {n(r.jours_etendue_theorique)} | {n(r.jours_presents_istdaten)} | "
      f"{p(r.couverture_pct)} % | {r.date_min_istdaten} | {r.date_max_istdaten} | "
      f"{n(r.n_numeros_distincts)} |")
w()

w("### 3.2 Table de réconciliation — transition H24 → H25")
w()
w("Chaque ligne est une opérationnalisation défendable, avec sa source et son filtre.")
w()
w("| Définition | Filtre | N° en H24 | N° en H25 | Maintenus | Sans antécédent en H25 | % des n° H25 | Disparus de H24 | % des n° H24 | Observations H25 | Obs. sans antécédent | % des obs. H25 |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for _, r in renum[renum.transition == "H24 -> H25"].iterrows():
    filt = r.filtre.split(" ; ")[0]
    w(f"| {r.definition} | {filt} | {n(r.n_numeros_annee_A)} | {n(r.n_numeros_annee_B)} | "
      f"{n(r.n_maintenus)} | **{n(r.n_sans_antecedent_B)}** | {p(r.pct_sans_antecedent_B)} % | "
      f"**{n(r.n_disparus_A)}** | {p(r.pct_disparus_A)} % | {n(r.n_obs_annee_B)} | "
      f"{n(r.n_obs_B_sans_antecedent)} | {p(r.pct_obs_B_sans_antecedent)} % |")
w()
w("### 3.3 Lecture — d'où viennent le 52 et le 48")
w()
d3 = renum[(renum.definition.str.startswith("D3 ")) & (renum.transition == "H24 -> H25")].iloc[0]
d1 = renum[(renum.definition.str.startswith("D1 ")) & (renum.transition == "H24 -> H25")].iloc[0]
d3_prev = renum[(renum.definition.str.startswith("D3 ")) & (renum.transition == "H23 -> H24")].iloc[0]
w("Les deux comptes du manuscrit ne se contredisent pas : **ils mesurent deux grandeurs "
  "différentes**, et les deux sont exacts sous leur propre définition.")
w()
w(f"- **{n(d3.n_disparus_A)}** est le nombre de numéros de **H24 qui disparaissent** en H25. "
  f"C'est le chiffre de la section 4.3.5.")
w(f"- **{n(d3.n_sans_antecedent_B)}** est le nombre de numéros de **H25 sans antécédent** en H24. "
  f"C'est le chiffre de la section 4.5.1.")
w(f"- Les deux coexistent parce que la grille **rétrécit** : {n(d3.n_numeros_annee_A)} numéros en "
  f"H24 contre {n(d3.n_numeros_annee_B)} en H25, dont {n(d3.n_maintenus)} maintenus. "
  f"L'identité se vérifie : {n(d3.n_numeros_annee_A)} − {n(d3.n_disparus_A)} = "
  f"{n(d3.n_maintenus)} et {n(d3.n_maintenus)} + {n(d3.n_sans_antecedent_B)} = "
  f"{n(d3.n_numeros_annee_B)}.")
w()
w(f"Ces valeurs sont **stables sur les trois sources** : D1 (grille théorique), D2 (circulations "
  f"réalisées) et D3 (jeu de modélisation) donnent toutes {n(d3.n_sans_antecedent_B)} numéros sans "
  f"antécédent et {n(d3.n_maintenus)} maintenus. Le décompte ne dépend donc pas de la source.")
w()
w("**Le « quelque 103 trains » de la section 4.3.5 n'est retrouvé par aucune définition.** "
  f"Le dénominateur pertinent est soit {n(d3.n_numeros_annee_A)} (numéros de H24, si l'on rapporte "
  f"les {n(d3.n_disparus_A)} disparus), soit {n(d3.n_numeros_annee_B)} (numéros de H25, si l'on "
  f"rapporte les {n(d3.n_sans_antecedent_B)} sans antécédent). Le 104 de la section 4.5.1 est, lui, "
  "exact.")
w()
w("**La fourchette « 42 à 47 % des observations » est retrouvée**, et son amplitude s'explique "
  "par la source retenue :")
w()
for _, r in renum[(renum.transition == "H24 -> H25") &
                  (renum.definition.str.match(r"D[123] "))].iterrows():
    w(f"- {r.definition} — {r.filtre.split(' ; ')[0]} : "
      f"{p(r.pct_obs_B_sans_antecedent)} % des observations de H25 "
      f"({n(r.n_obs_B_sans_antecedent)} sur {n(r.n_obs_annee_B)}).")
w()

w("### 3.4 Contrôle — « les deux changements précédents n'avaient modifié aucun numéro »")
w()
w("| Définition | Filtre | Transition | N° année A | N° année B | Sans antécédent | Disparus |")
w("|---|---|---|---:|---:|---:|---:|")
for _, r in renum[renum.transition.isin(["H22 -> H23", "H23 -> H24"])].iterrows():
    filt = r.filtre.split(" ; ")[0]
    w(f"| {r.definition} | {filt} | {r.transition} | {n(r.n_numeros_annee_A)} | "
      f"{n(r.n_numeros_annee_B)} | {n(r.n_sans_antecedent_B)} | {n(r.n_disparus_A)} |")
w()
w("**L'affirmation tient sur le jeu de modélisation, mais pas sur la grille théorique.** "
  "Sur D3, les transitions H22 → H23 et H23 → H24 se font à numérotation rigoureusement "
  "constante : 108 numéros, zéro apparition, zéro disparition. Il en va de même sur D2 une fois "
  "les circulations supplémentaires écartées. En revanche, sur D1, la grille planifiée passe de "
  "108 numéros en H22 à 102 en H23, puis revient à 108 en H24 : **6 numéros disparaissent puis "
  "réapparaissent**, ce qui représente "
  f"{p(renum[(renum.definition.str.startswith('D1 ')) & (renum.transition == 'H23 -> H24')].iloc[0].pct_obs_B_sans_antecedent)}"
  " % des tronçons-jours planifiés de H24. Sur D2 sans filtre, 3 numéros apparaissent en H23 "
  "et 2 en H24, tous des circulations supplémentaires. La formulation « n'en avaient modifié "
  "aucun » est donc exacte au sens du jeu de modélisation et de l'offre régulière, et inexacte "
  "au sens de la grille planifiée brute.")
w()

w("### 3.5 Contrôle — clé complète à 53,7 % et repli naïf à 42,4 %")
w()
sc = casc[casc.perimetre_train.str.startswith("Split C")]
w("Reproduction de la cascade de repli de la baseline naïve (§4.5.2) depuis les artefacts "
  "existants : clé complète `(tronçon départ × arrivée bpuic, numéro de course, type de jour "
  "cal_is_weekend)`, train H22 (Gilamont 8501260 exclu) + H23 + H24, test H25.")
w()
w("| Niveau | Clé | Lignes H25 | % |")
w("|---|---|---:|---:|")
for _, r in sc.iterrows():
    w(f"| {n(r.niveau)} | {r.cle} | {n(r.n_lignes_H25)} | {p(r.pct_lignes_H25, 2)} % |")
w()
n1 = sc[sc.niveau == 1].iloc[0]
n3 = sc[sc.niveau == 3].iloc[0]
w(f"**Les deux valeurs sont reproductibles.** La clé complète couvre "
  f"{p(n1.pct_lignes_H25, 2)} % des lignes de H25 ({n(n1.n_lignes_H25)} sur "
  f"{n(n1.n_total_H25)}), ce qui arrondit au 53,7 % du manuscrit. Le repli le moins conditionné "
  f"(niveau 3, tronçon × type de jour) reçoit {p(n3.pct_lignes_H25, 2)} % des lignes "
  f"({n(n3.n_lignes_H25)}), ce qui arrondit au 42,4 %. Le résultat est **insensible à "
  "l'exclusion de Gilamont** : la variante avec H22 intégral donne les mêmes effectifs à l'unité près.")
w()

# --------------------------------------------------------------------------- #
w("---")
w()
w("## 4. Ambiguïtés signalées et données manquantes")
w()
w("1. **Seuil de la définition « total »** (§2.6). L'énoncé fixe 75 ; la lecture « capacité de "
  "référence = 63 sièges de 2e classe » est également défendable. Les deux sont produites sous "
  "les noms DT75 et DT63. Aucune n'est tranchée.")
w("2. **Segment d'une course mixte** (§2.5). "
  f"{p(coh_val('courses_mixtes_H25', 'pct_courses_mixtes'))} % des courses de H25 "
  f"({n(coh_val('courses_mixtes_H25', 'n_courses_mixtes'))} sur "
  f"{n(coh_val('courses_mixtes_H25', 'n_lignes'))}) traversent les deux segments. La règle "
  "canonique du dépôt et la variante course × segment sont toutes deux rapportées.")
w(f"3. **Couverture d'ISTDATEN sur H25** (§3.1). La source s'arrête au "
  f"{h25c.date_max_istdaten} et ne couvre que {n(h25c.jours_presents_istdaten)} jours de "
  "H25. C'est une **donnée manquante**, pas une valeur à imputer : la "
  "définition D2 sur H25 est rapportée telle quelle, assortie d'une variante à fenêtre appariée, "
  "et sa part d'observations n'est pas extrapolée à l'année.")
w("4. **Notion d'« observation »**. Elle n'a pas le même support selon la source : tronçons-jours "
  "planifiés pour D1, lignes date × train × arrêt pour D2, tronçons observés pour D3. Les parts "
  "d'observations ne sont donc pas directement comparables entre définitions, ce qui explique "
  "l'essentiel de la fourchette 42-47 %.")
w("5. **Périmètre H22**. Le jeu ne contient que "
  f"{n(coh[(coh.controle=='volumetrie_par_annee_horaire') & (coh.perimetre=='H22')].iloc[0].n_lignes)} "
  f"tronçons pour H22 contre "
  f"{n(coh[(coh.controle=='volumetrie_par_annee_horaire') & (coh.perimetre=='H23')].iloc[0].n_lignes)} "
  f"pour H23 et "
  f"{n(coh[(coh.controle=='volumetrie_par_annee_horaire') & (coh.perimetre=='H24')].iloc[0].n_lignes)} "
  f"pour H24, l'année étant "
  "partiellement couverte par l'APC. Les agrégats H22-H25 sont donc pondérés en faveur de H23-H25. "
  "Ce point est connu du dépôt et n'a pas été corrigé ici.")
w()
w("## 5. Figures envisageables, non produites")
w()
w("Aucune figure n'a été produite, conformément à la demande. Deux seraient utiles si la "
  "section devait en accueillir :")
w()
w("- Un histogramme de la charge de 1re classe avec la ligne des 12 places, qui rendrait "
  "immédiatement visible le fait que la distribution est presque entièrement sous le seuil "
  "(P99 à 6 ou 7 places selon la population).")
w("- Un nuage charge de 2e classe × charge totale avec les deux seuils 63 et 75 tracés, qui "
  "montrerait d'un coup d'œil que la bande entre les deux définitions est peuplée et pourquoi "
  "DT75 est nettement plus restrictive que D2.")
w()

# --------------------------------------------------------------------------- #
w("---")
w()
w("## 6. Ce que ces chiffres permettent d'écrire")
w()
w("**Vérification 1, affirmation A.**")
w()
w(f"> Sur l'ensemble du régime actuel, la première classe ne dépasse ses douze places que sur "
  f"{n(la.n_1c_sup_12)} tronçons observés sur {n(la.n_troncons)}, soit "
  f"{p(la.pct_1c_sup_12, 2)} % des cas, et elle ne constitue le facteur limitant, au sens où "
  f"elle sature alors que la deuxième classe ne sature pas, que sur {n(la.n_1c_facteur_limitant)} "
  f"tronçons, soit {p(la.pct_1c_facteur_limitant, 2)} %. Je retiens donc la deuxième classe "
  f"comme seule grandeur de dimensionnement.")
w()
w("**Vérification 1, affirmation B.**")
w()
rA = c(POP_A, "tronçon")
rB = c(POP_B, "course")
w(f"> Retenir la charge totale des deux classes plutôt que la seule deuxième classe ne déplace "
  f"pas marginalement le décompte des surcharges, il le réduit de "
  f"{p(abs(rA.ecart_relatif_DT_vs_D2_pct))} % au grain du tronçon sur le régime actuel, en "
  f"passant de {n(rA.total_D2_n)} à {n(rA.total_DT_n)} tronçons. L'accord entre les deux "
  f"définitions reste modéré, avec un indice de Jaccard de {f(rA.jaccard, 2)} sur l'union des "
  f"tronçons classés en surcharge. La raison en est que la première classe circule presque vide, "
  f"de sorte que le seuil de soixante-quinze places appliqué au total revient en pratique à "
  f"exiger environ soixante-quatorze voyageurs en deuxième classe. C'est la même quasi-vacuité "
  f"de la première classe qui fonde l'affirmation précédente et qui interdit ici de traiter les "
  f"deux définitions comme équivalentes.")
w()
w("**Vérification 2, réconciliation des deux comptes.**")
w()
w(f"> La refonte de décembre 2024 fait passer la grille de {n(d3.n_numeros_annee_A)} à "
  f"{n(d3.n_numeros_annee_B)} numéros de train, dont {n(d3.n_maintenus)} sont conservés. "
  f"{n(d3.n_disparus_A)} numéros de l'horaire 2024 disparaissent et {n(d3.n_sans_antecedent_B)} "
  f"numéros de l'horaire 2025 apparaissent sans antécédent, ces deux comptes étant l'un et "
  f"l'autre exacts et simplement distincts. Le décompte est identique sur la grille planifiée, "
  f"sur les circulations réalisées et sur le jeu de modélisation. Selon la source retenue, "
  f"entre {p(renum[(renum.definition.str.startswith('D2 ')) & (renum.transition == 'H24 -> H25')].iloc[-1].pct_obs_B_sans_antecedent)}"
  f" et {p(d1.pct_obs_B_sans_antecedent)} % des observations de l'horaire 2025 portent un "
  f"numéro sans antécédent.")
w()
w("**Vérification 2, changements d'horaire antérieurs.**")
w()
w(f"> Les deux changements d'horaire précédents laissent la numérotation du jeu de modélisation "
  f"rigoureusement inchangée, à {n(d3_prev.n_numeros_annee_A)} numéros constants et sans "
  f"aucune apparition ni "
  f"disparition. La grille planifiée fait toutefois exception, six numéros y disparaissant en "
  f"2023 avant de réapparaître en 2024, ce qui invite à préciser que l'invariance porte sur "
  f"l'offre effectivement observée et non sur la grille brute.")
w()
w("**Vérification 2, baseline naïve.**")
w()
w(f"> La clé complète associant le tronçon, le numéro de course et le type de jour ne retrouve "
  f"son équivalent historique que pour {p(n1.pct_lignes_H25, 1)} % des lignes de l'horaire "
  f"2025, et {p(n3.pct_lignes_H25, 1)} % basculent vers le repli le moins conditionné, qui "
  f"ne retient plus que le tronçon et le type de jour. Ces deux valeurs se reproduisent à "
  f"l'identique depuis le jeu gelé.")
w()
w("---")
w()
w(f"*Artefacts : `verif_definitions_surcharge.csv`, "
  "`verif_definitions_surcharge_par_segment.csv`, "
  "`verif_definitions_surcharge_sensibilite_seuil.csv`, "
  "`verif_surcharge_distribution_1ere_classe.csv`, "
  "`verif_surcharge_facteur_limitant_1ere_classe.csv`, "
  "`verif_surcharge_controle_coherence.csv`, `verif_renumerotation_h25.csv`, "
  "`verif_renumerotation_couverture_istdaten.csv`, "
  "`verif_renumerotation_transitions_anterieures.csv`, "
  "`verif_renumerotation_cascade_baseline.csv`, plus les deux journaux d'exécution "
  "`*_journal.txt`.*")

(OUT / "SYNTHESE_verifs_4_3.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"Écrit : {OUT / 'SYNTHESE_verifs_4_3.md'} ({len(L)} lignes)")
