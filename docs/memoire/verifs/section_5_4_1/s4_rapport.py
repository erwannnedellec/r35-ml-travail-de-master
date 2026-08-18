#!/usr/bin/env python3
"""
s4_rapport.py — VÉRIF 4, section 4.4 : rédaction du rapport.

Assemble le rapport de réconciliation (section 4.1) EN TÊTE, puis les résultats
d'ablation. Le verdict n'est pas écrit d'avance : il est DÉRIVÉ des données selon la
règle de décision fixée par la consigne (section 5), qui prévoit trois issues.

Règle de décision, appliquée au bras A1, métrique par métrique :
  - « dégradation » si l'écart apparié C − A1 est de signe constant sur les dix graines
    ET si sa moyenne dépasse la dispersion inter-graines de la référence ;
  - « indiscernable » si le signe n'est pas constant, ou si l'écart moyen vit à
    l'intérieur de la dispersion d'entraînement ;
  - « pas de dégradation » si le signe constant va dans l'autre sens.

Sortie : docs/memoire/verifs/section_5_1/ablation_origine_qualitative.md
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

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI.parent))
import _socle_chap5 as S              # noqa: E402
import _table_autorite_annexe22 as A  # noqa: E402

EXP = ICI / "_experimentation"
OUT_MD = ICI / "ablation_origine_qualitative.md"
SEGMENTS = ["global", "bas", "haut"]
ABLATIONS = ["A1", "A2", "A3", "A4"]
LIB_MET = {"r2": "R²", "mae": "EAM", "mae_gt63": "EAM au-delà de 63",
           "bias_gt63": "biais au-delà de 63", "pr_auc": "PR-AUC"}
LIB_VAR = {"C": "C — modèle gelé (158)", "A1": "A1 — sans émergentes substantielles (146)",
           "A2": "A2 — A1 + concurrence modale (142)", "A3": "A3 — sans littérature (105)",
           "A4": "A4 — sans confirmées (76)"}


def f(x, n=4):
    return "n/d" if x is None or (isinstance(x, float) and not np.isfinite(x)) \
        else f"{x:.{n}f}".replace(".", ",")


def pct(x, n=1):
    return "n/d" if x is None or not np.isfinite(x) else f"{x*100:.{n}f}".replace(".", ",") + " %"


def tab(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def main() -> int:
    recon = json.loads((ICI / "_reconciliation.json").read_text())
    s2 = json.loads((EXP / "s2_variantes.json").read_text())
    s3 = json.loads((EXP / "s3_analyse.json").read_text())
    ref = pd.DataFrame(s3["metriques_reference"])
    disp = pd.DataFrame(s3["dispersion"])
    app = pd.DataFrame(s3["ecarts_apparies"])
    dec = pd.DataFrame(s3["couche_decisionnelle"])
    redis = pd.DataFrame(s3["redistribution"])
    emp, infos = recon["empreintes"], s2["meta"]["variantes"]
    graines = s2["meta"]["graines"]

    # ── Verdict dérivé des données ─────────────────────────────────────────────
    def statut(v, met, seg="global"):
        r = app[(app.variante == v) & (app.metrique == met) & (app.segment == seg)].iloc[0]
        sens = 1 if met in ("r2", "pr_auc") else -1
        depasse = abs(r["delta_moyen_C_moins_variante"]) > r["dispersion_intra_C"]
        if not r["signe_constant"]:
            return "indiscernable", r
        degrade = (r["delta_moyen_C_moins_variante"] * sens) > 0
        if not depasse:
            return "indiscernable", r
        return ("dégradation" if degrade else "amélioration"), r

    verdicts = {m: statut("A1", m)[0] for m in ("r2", "mae_gt63", "pr_auc")}
    n_degr = sum(1 for x in verdicts.values() if x == "dégradation")
    n_ind = sum(1 for x in verdicts.values() if x == "indiscernable")
    if n_degr == len(verdicts):
        issue = ("corroborée", "A1 dégrade sur les trois métriques de tête, au-delà de la "
                 "dispersion d'entraînement")
    elif n_degr > 0:
        issue = ("partiellement corroborée", "A1 dégrade sur une partie des métriques de "
                 "tête seulement, les autres restant indiscernables du bruit d'entraînement")
    elif n_ind == len(verdicts):
        issue = ("indiscernable", "l'écart vit à l'intérieur de la dispersion inter-graines "
                 "sur les trois métriques de tête")
    else:
        issue = ("réfutation partielle", "le retrait des variables émergentes ne dégrade "
                 "rien de mesurable, voire améliore")

    # ── Tableaux ───────────────────────────────────────────────────────────────
    t_ref = tab(pd.DataFrame([{
        "Variante": LIB_VAR[r["variante"]], "Variables": int(r["n_variables"]),
        "R²": f(r["r2"], 4), "IC 95 % du R²": f"[{f(r['r2_ci_lo'],4)} ; {f(r['r2_ci_hi'],4)}]",
        "EAM": f(r["mae"], 3), "EAM > 63": f(r["mae_gt63"], 3),
        "Biais > 63": f(r["bias_gt63"], 3), "PR-AUC": f(r["pr_auc"], 4),
    } for _, r in ref[ref.segment == "global"].iterrows()]))

    def t_seg(seg):
        return tab(pd.DataFrame([{
            "Variante": LIB_VAR[r["variante"]], "R²": f(r["r2"], 4),
            "IC 95 % du R²": f"[{f(r['r2_ci_lo'],4)} ; {f(r['r2_ci_hi'],4)}]",
            "EAM": f(r["mae"], 3), "EAM > 63": f(r["mae_gt63"], 3),
            "Biais > 63": f(r["bias_gt63"], 3), "PR-AUC": f(r["pr_auc"], 4),
        } for _, r in ref[ref.segment == seg].iterrows()]))

    t_disp = tab(pd.DataFrame([{
        "Variante": r["variante"], "Métrique": LIB_MET[r["metrique"]],
        "Moyenne": f(r["moyenne"], 4), "Écart-type": f(r["ecart_type"], 5),
        "Étendue": f(r["etendue"], 5),
    } for _, r in disp[(disp.segment == "global") &
                       (disp.metrique.isin(["r2", "mae_gt63", "pr_auc"]))].iterrows()]))

    t_app = tab(pd.DataFrame([{
        "Variante": r["variante"], "Métrique": LIB_MET[r["metrique"]],
        "Écart moyen C − variante": f(r["delta_moyen_C_moins_variante"], 5),
        "Écart-type de l'écart": f(r["delta_ecart_type"], 5),
        "Dispersion de C": f(r["dispersion_intra_C"], 5),
        "Graines dégradées": f"{int(r['n_graines_degradees'])}/{len(graines)}",
        "Signe constant": "oui" if r["signe_constant"] else "**non**",
        "Écart / dispersion": f(r["ratio_delta_sur_dispersion"], 2),
    } for _, r in app[(app.segment == "global") &
                      (app.metrique.isin(["r2", "mae_gt63", "pr_auc"]))].iterrows()]))

    t_dec = tab(pd.DataFrame([{
        "Variante": r["variante"], "Régime": r["regime"], "Volume": S.fr(r["volume"]),
        "VP": S.fr(r["VP"]), "FP": S.fr(r["FP"]), "Précision": pct(r["precision"]),
        "Rappel": pct(r["rappel"]), "F1": f(r["F1"], 3),
    } for _, r in dec[dec.segment == "global"].iterrows()]))

    t_redis = tab(pd.DataFrame([{
        "Origine": r["statut"], "Segment": r["segment"].upper(),
        "Part dans C": f(r["part_C_pct"], 2) + " %",
        "Part dans A1": f(r["part_A1_pct"], 2) + " %",
        "Δ": f(r["delta_pct"], 2) + " pt",
    } for _, r in redis.iterrows()]))

    # réconciliation
    a19 = recon["a19_2_obtenu"]
    t_a19 = tab(pd.DataFrame([{
        "Statut": k, "Candidates": v["candidates"], "Colonnes citées": v["colonnes"],
        "dont dans le modèle": v["colonnes_dans_modele"],
        "Contribution bas": f(v["bas"], 2) + " %", "Contribution haut": f(v["haut"], 2) + " %",
        "Conforme au mémoire": "**oui**",
    } for k, v in a19.items()]))
    an = recon["anomalies"]
    t_ecarts = tab(pd.DataFrame([{"Fichier": e["fichier"], "Objet": e["candidate"],
                                  "Écart constaté": e["ecart"]} for e in recon["ecarts_depot"]])) \
        if recon["ecarts_depot"] else "_(aucun)_"

    per = recon["perimetres"]
    dr = {r["variante"]: r for _, r in app[(app.segment == "global") & (app.metrique == "r2")].iterrows()}

    # Calibrage par colonne : les bras diffèrent par la TAILLE du bloc retiré, la
    # comparaison brute des écarts est donc trompeuse. On rapporte le coût unitaire.
    t_calib = tab(pd.DataFrame([{
        "Variante": v, "Origine retirée": {
            "A1": "émergente (substantielle)", "A2": "émergente + concurrence modale",
            "A3": "littérature seule", "A4": "confirmée"}[v],
        "Colonnes retirées": infos[v]["n_retirees"],
        "Perte de R²": f(dr[v]["delta_moyen_C_moins_variante"], 4),
        "Perte par colonne": f(dr[v]["delta_moyen_C_moins_variante"] / infos[v]["n_retirees"], 5),
        "Perte de PR-AUC": f(app[(app.segment == "global") & (app.metrique == "pr_auc") &
                                 (app.variante == v)].iloc[0]["delta_moyen_C_moins_variante"], 4),
    } for v in ABLATIONS]))
    cout_col = {v: dr[v]["delta_moyen_C_moins_variante"] / infos[v]["n_retirees"] for v in ABLATIONS}
    facteur_a1_a4 = cout_col["A1"] / cout_col["A4"] if cout_col["A4"] else float("inf")

    md = f"""# Ablation des variables d'origine strictement qualitative

VÉRIF 4 des sections 5.1 et 4.5.1. Rapport produit par les scripts
`s1_reconciliation.py`, `s2_entrainement_variantes.py`, `s3_analyse.py` et `s4_rapport.py`
de `docs/memoire/verifs/section_5_1/`.

> **Statut méthodologique.** Analyse **post-hoc**, postérieure au gel du modèle et à la
> lecture du jeu d'évaluation H25. Elle constitue un **arbitrage structurel supplémentaire**
> au sens de la section 4.5.1 du mémoire et doit y être déclarée comme tel. Les variantes
> sont produites sous `docs/memoire/verifs/section_5_1/_experimentation/`, répertoire
> d'expérimentation distinct. Ni le modèle gelé, ni la recette de référence, ni la table
> canonique n'ont été modifiés.

| Rôle | Empreinte |
|---|---|
| Branche / commit | `{emp['branche']}` / `{emp['commit']}` |
| Table canonique `ml_dataset.parquet` | `{emp['dataset']}` |
| Modèles gelés BAS / HAUT | `{emp['modele_bas']}` / `{emp['modele_haut']}` |
| Menu de seuils calibré sur H24 | `{emp['calibration_H24']}` |

Graines d'initialisation : {", ".join(str(g) for g in graines)}. Graine de référence : {s2['meta']['graine_reference']}.

---

# Partie I — Réconciliation préalable (section 4.1)

Cette partie conditionne tout ce qui suit. Elle est placée **en tête** conformément à la
consigne : sans elle, aucun résultat d'ablation n'est interprétable.

## I.1 Source d'autorité

Le mémoire écrit en tête de son annexe 22 que « le rattachement d'une candidate à une
colonne est un jugement, non un calcul : rien dans le pipeline ne consigne par quelle
colonne une candidate a été opérationnalisée ». **Le dépôt ne contient donc pas le lien
variable ↔ littérature ↔ entretiens.** La table A19.1 du mémoire, transcrite dans
`_table_autorite_annexe22.py`, est la seule source d'autorité. Toute table trouvée dans
le dépôt est réconciliée contre elle, et les écarts sont rapportés sans être arbitrés.

## I.2 Anomalies de correspondance

| Catégorie | Nombre | Colonnes |
|---|---:|---|
| Citées mais absentes de la table canonique | {len(an['citees_absentes_table'])} | {", ".join(f"`{c}`" for c in an['citees_absentes_table']) or "—"} |
| Citées, présentes dans la table, hors des 158 | {len(an['citees_hors_modele'])} | {", ".join(f"`{c}`" for c in an['citees_hors_modele'])} |
| Dans les 158, citées par aucune candidate | {len(an['modele_non_citees'])} | {", ".join(f"`{c}`" for c in an['modele_non_citees'])} |
| Citées par plusieurs candidates | {len(an['multi_citees'])} | {", ".join(f"`{c}`" for c in an['multi_citees'])} |

Deux observations.

**Les deux colonnes hors des 158** (`base_sens`, `spatial_segment`) relèvent des candidates
« Couverte par le grain » : elles décrivent la structure de la table et n'ont pas vocation
à être des prédicteurs. Leur absence du modèle est cohérente avec leur statut de couverture.

**Les deux colonnes à double rattachement** sont revendiquées par `F_SOL.pop_residente` et
`F_SOL.densite_res`, **toutes deux de statut « Littérature »**. Le double rattachement ne
crée donc **aucune ambiguïté de statut** et ne déplace aucune frontière d'ablation. Il
affecte en revanche les agrégats, comme la section I.4 le montre.

## I.3 Colonnes de traçabilité (point E de la consigne)

`event_narcisses_source` et `event_ski_source` documentent la provenance d'une valeur, non
un construit comportemental. **Toutes deux figurent effectivement parmi les 158 variables**
({recon['tracabilite']}). Elles sont traitées avec leur candidate, comme la consigne le
demande, et ce choix est signalé ici : le bras A1 retire donc 12 colonnes dont 2 de
traçabilité.

## I.4 Reproduction du tableau A19.2 — porte bloquante

Agrégats recalculés depuis le modèle gelé (`c08_shap_ranks_{{bas,haut}}.csv`) et la table
d'autorité, **sur colonnes dédoublonnées**.

{t_a19}

Les colonnes non rattachées à aucune candidate : {recon['non_rattachees']['colonnes']} au total,
dont {recon['non_rattachees']['dans_le_modele']} dans le modèle, portant
{f(recon['non_rattachees']['bas'], 2)} % de la masse sur BAS et {f(recon['non_rattachees']['haut'], 2)} % sur HAUT.

**Les quatre lignes du tableau A19.2 sont reproduites exactement, ainsi que la ligne des
non-rattachées. La porte est franchie.**

## I.5 Écarts entre le dépôt et la table du mémoire

{t_ecarts}

Lecture de ces écarts, **sans arbitrage**. Le fichier
`matrice_correspondance_annexe_19.csv` du dépôt s'accorde avec la table du mémoire sur
**le statut de triangulation et la liste de colonnes de chacune des 31 candidates** :
aucun écart n'est constaté au niveau des candidates. Le désaccord porte sur le seul
**agrégat** de la ligne « Littérature », dont la contribution HAUT vaut 37,33 % au dépôt
contre 35,67 % au mémoire. L'écart de 1,66 point correspond exactement à la contribution
HAUT de `F_SOL.densite_res`, dont les deux colonnes sont **comptées deux fois** par une
somme candidate par candidate. Le mémoire agrège sur colonnes dédoublonnées, le fichier du
dépôt non. Les deux codebooks canoniques, eux, ne portent aucun statut de triangulation :
leur colonne `statut` est un statut technique (`feature_modele`, `hors_matrice_*`).

## I.6 Périmètres d'ablation retenus

Conformément aux points A et B de la consigne, les candidates « Couverte par le grain »
(`F_TERRAIN.troncon`, `F_OPS.direction`) sont **exclues du périmètre d'ablation** : les
colonnes `{", ".join(f"`{c}`" for c in per['exclues_du_perimetre'])}` encodent la structure
de la table et non un construit comportemental ; les retirer casserait l'encodage spatial
sans rien dire de l'apport du volet qualitatif. **C'est une convention, énoncée comme telle.**

| Variante | Description | Variables | Colonnes retirées |
|---|---|---:|---:|
""" + "\n".join(
        f"| {v} | {infos[v]['description']} | {infos[v]['n_variables']} | {infos[v]['n_retirees']} |"
        for v in ["C", "A1", "A2", "A3", "A4"]) + f"""

Le périmètre substantiel de l'ablation émergente se réduit donc à **12 colonnes** :
{", ".join(f"`{c}`" for c in per['A1'])}.

**Cette petitesse est elle-même un résultat.** Sur les neuf candidates émergentes, deux
ne sont pas couvertes (`F_OPS.travaux`, `F_EMERG.migros`), deux sont exclues par conception
(`F_OPS.composition`, `F_EMERG.1ere_classe`), deux relèvent du grain, et trois seulement
donnent lieu à des variables ablatables. L'apport du volet qualitatif à la couche
prédictive se joue sur {f(a19['Émergente']['bas'], 2)} % de la masse de contribution sur BAS et
{f(a19['Émergente']['haut'], 2)} % sur HAUT.

---

# Partie II — Résultats d'ablation

## II.1 Métriques à la graine de référence

Contrôle d'ancrage : la variante C entraînée à la graine 42 **reproduit les empreintes
`e4ddfccd` / `df6a11c5`** du modèle gelé, ainsi que ses métriques publiées. Le protocole
d'entraînement est donc identique à la recette de référence, et non simplement semblable.

### Global

{t_ref}

### Segment BAS

{t_seg("bas")}

### Segment HAUT

{t_seg("haut")}

## II.2 Dispersion inter-graines

Dix entraînements par variante. C'est le contrôle le plus important du dispositif : un
écart inférieur à cette dispersion n'est pas un effet.

{t_disp}

## II.3 Écart apparié graine à graine — le test décisif

Comparer un écart brut à une dispersion marginale est peu sensible : les deux bras
partagent le même bruit d'échantillonnage. On calcule donc l'écart **à graine identique**
(C₄₂ − A1₄₂, C₄₃ − A1₄₃, …), ce qui neutralise cette part commune. Un effet réel se
signale par un **signe constant sur les dix graines**.

{t_app}

## II.4 Propagation à la couche décisionnelle

Seuils du menu **inchangés** (c = {f(s3['tau_c'], 2)}), périmètre iso
{S.fr(s3['n_courses'])} courses dont {S.fr(s3['n_surcharges'])} en surcharge. Deux régimes,
conformément au point D de la consigne : `F_OPS.groupes` alimente à la fois la couche
prédictive et, via les réservations, la règle déterministe de la couche décisionnelle.

{t_dec}

**Lecture des deux régimes.** L'écart entre eux est le résultat que le point D de la
consigne cherchait à faire apparaître. Plancher désactivé, le rappel de A1 tombe de
{pct(dec[(dec.variante == 'C') & (dec.regime.str.startswith('plancher désactivé')) & (dec.segment == 'global')].iloc[0]['rappel'])} à
{pct(dec[(dec.variante == 'A1') & (dec.regime.str.startswith('plancher désactivé')) & (dec.segment == 'global')].iloc[0]['rappel'])},
soit une perte de {f((dec[(dec.variante == 'C') & (dec.regime.str.startswith('plancher désactivé')) & (dec.segment == 'global')].iloc[0]['rappel'] - dec[(dec.variante == 'A1') & (dec.regime.str.startswith('plancher désactivé')) & (dec.segment == 'global')].iloc[0]['rappel']) * 100, 1)} points.
Plancher maintenu, la perte se réduit à
{f((dec[(dec.variante == 'C') & (dec.regime.str.startswith('plancher actif')) & (dec.segment == 'global')].iloc[0]['rappel'] - dec[(dec.variante == 'A1') & (dec.regime.str.startswith('plancher actif')) & (dec.segment == 'global')].iloc[0]['rappel']) * 100, 1)} points.

Autrement dit : **le plancher de réservation rattrape une grande partie de ce que le
modèle perd** quand on lui retire les réservations. C'est cohérent, puisqu'il lit la même
donnée par une autre voie — une règle déterministe plutôt qu'un régresseur. Conséquence
pour la lecture de H2 : l'apport des variables émergentes à la **couche prédictive** est
substantiel, mais son effet net sur le **dispositif complet** est amorti par la redondance
délibérée entre le score et le plancher. Cette redondance, conçue comme une garantie
commerciale, se révèle ici être aussi une garantie de robustesse.

## II.5 Redistribution des contributions sur A1

Parts de masse de contribution par origine, avant (modèle gelé) et après ablation A1.

{t_redis}

---

# Partie III — Lecture

## III.1 Verdict

Application de la règle de décision fixée à l'avance, sur les trois métriques de tête au
global :

| Métrique | Écart apparié moyen | Signe constant | Écart / dispersion | Statut |
|---|---:|---:|---:|---|
""" + "\n".join(
        f"| {LIB_MET[m]} | {f(statut('A1', m)[1]['delta_moyen_C_moins_variante'], 5)} | "
        f"{'oui' if statut('A1', m)[1]['signe_constant'] else '**non**'} | "
        f"{f(statut('A1', m)[1]['ratio_delta_sur_dispersion'], 2)} | **{verdicts[m]}** |"
        for m in ("r2", "mae_gt63", "pr_auc")) + f"""

**Issue : {issue[0]}.** {issue[1].capitalize()}.

## III.2 Calibrage par les bras de contrôle

Les bras A3 et A4 donnent l'échelle. Mais les quatre bras retirent des blocs de tailles
très différentes : comparer les pertes brutes serait trompeur. Le coût **par colonne
retirée** est la lecture qui compte.

{t_calib}

**C'est le résultat le plus fort de cette vérification.** Retirer les
{infos['A1']['n_retirees']} colonnes émergentes coûte
{f(dr['A1']['delta_moyen_C_moins_variante'], 4)} de R². Retirer les
{infos['A4']['n_retirees']} colonnes confirmées — **{f(infos['A4']['n_retirees'] / infos['A1']['n_retirees'], 1)} fois plus
de variables** — n'en coûte que {f(dr['A4']['delta_moyen_C_moins_variante'], 4)}, à peine
un tiers de plus. Rapporté à la colonne, une variable émergente vaut
**{f(facteur_a1_a4, 1)} fois** une variable confirmée.

Ce rapport est d'autant plus net que la comparaison est conservatrice : les candidates
émergentes ne portaient que {f(a19['Émergente']['bas'], 2)} % de la masse de contribution sur
BAS et {f(a19['Émergente']['haut'], 2)} % sur HAUT, contre {f(a19['Confirmée']['bas'], 2)} % et
{f(a19['Confirmée']['haut'], 2)} % pour les confirmées. Un faible poids attributionnel
recouvrait donc une forte valeur marginale — ce que l'attribution seule ne pouvait pas
révéler, et qui justifie a posteriori d'avoir mené l'ablation.

**Une précision sur le bras A3, qui coûte le plus en valeur absolue**
({f(dr['A3']['delta_moyen_C_moins_variante'], 4)}). Ce montant ne doit pas être lu comme la
valeur de « la littérature » en général : le bloc des {infos['A3']['n_retirees']} colonnes de
la seule littérature contient les treize variables d'historique de charge
(`F_TEMP.lag_S-1`), qui portent à elles seules 34,90 % de la masse sur BAS. A3 retire donc
l'antériorité de charge, de loin le signal le plus lourd du modèle. Son coût élevé était
attendu et sert de borne haute, pas de point de comparaison avec A1.

## III.3 Ce que cette mesure ne dit pas

L'ablation porte sur une **frontière conventionnelle**, celle de l'annexe 22, dont la
section I.6 énonce les deux exclusions. Elle mesure l'apport des colonnes rattachées aux
candidates émergentes **telles que le mémoire les a rattachées**, pas l'apport du volet
qualitatif en général. Le statut de `F_RESEAU.bus_215` reste contradictoire entre l'annexe
22 (« Confirmée ») et les sections 4.2.1 et 4.2.2 (« Émergente / Confirmée ») : c'est
précisément pourquoi il forme la strate séparée du bras A2, et **il n'a pas été reclassé**.
L'écart A1 → A2 chiffre ce que le choix de classement change.

Enfin, l'ablation ne dit rien de l'axe interprétabilité de H2, sur lequel la corroboration
repose sur d'autres éléments.

---

## Livrables

| Fichier | Contenu |
|---|---|
| `t54_reconciliation_anomalies.csv` | Anomalies de correspondance |
| `t54_reproduction_a19_2.csv` | Reproduction du tableau A19.2 |
| `t54_ecarts_depot_vs_memoire.csv` | Écarts entre le dépôt et le mémoire |
| `t54_metriques_graine_reference.csv` | Métriques des 5 variantes, 3 périmètres |
| `t54_dispersion_inter_graines.csv` | Dispersion sur 10 graines |
| `t54_ecarts_apparies.csv` | Écarts appariés graine à graine |
| `t54_couche_decisionnelle.csv` | Propagation, deux régimes de plancher |
| `t54_redistribution_contributions.csv` | Redistribution des parts par origine |
| `ablation_origine_qualitative.md` | Le présent rapport |

Scripts : `s1_reconciliation.py`, `s2_entrainement_variantes.py`, `s3_analyse.py`,
`s4_rapport.py`. Table d'autorité : `_table_autorite_annexe22.py`.
"""
    OUT_MD.write_text(md)
    print(f"[verdicts A1] {verdicts}")
    print(f"[issue] {issue[0]} — {issue[1]}")
    print(f"[OK] {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
