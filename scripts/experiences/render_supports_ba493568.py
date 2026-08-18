#!/usr/bin/env python3
"""
Rendu des supports d'entretien depuis la SOURCE UNIQUE supports_donnees_ba493568.json :
  - 6 markdown par cas (docs/entretiens/supports/cas_N_XXXX.md), 3 sections separees par le
    marqueur de revelation ;
  - 00_presentation_outil.md, fiche_intervieweur.md, table_traduction_shap.md ;
  - 12 figures PNG (2 par cas) sous la charte figures_style (Okabe-Ito, 300 DPI, SOURCE_DATE_EPOCH).

Pare-feu (guide 2.2) sur les markdown du JEU A ET les libelles de figures : refus si un interdit
fuit. La figure de section 2 ne contient AUCUNE serie realisee (verifie). Registre sans cadratins.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import figures_style as fs  # noqa: E402

DATA = json.loads((ROOT / "outputs/entretiens/supports_donnees_ba493568.json").read_text())
CASES = json.loads((ROOT / "outputs/entretiens/cas_entretien_deploiement_ba493568.json").read_text())
NOTES = {f["bloc_J1"]["identifiant"]["numero_train"]: f for f in CASES["fiches"]}
OUTDIR = ROOT / "docs/entretiens/supports"
FIGDIR = OUTDIR / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True); FIGDIR.mkdir(parents=True, exist_ok=True)
ORDRE = DATA["meta"]["ordre_cas"]

SKIP_FIGURES = "--no-figures" in sys.argv        # figures inchangees (aucune regeneration)
REVEL = "--- REVELATION : ne pas montrer avant elicitation ---"
FORBIDDEN = [r"\bVP\b", r"\bFP\b", r"\bFN\b", r"\bVN\b", "166", "12,7", "12.7", r"\bscore\b",
             "precision", "précision", "rappel", "recall", "cout", "coût", "matrice",
             "raison de selection", "raison de sélection", "seuil de planification",
             "deux sur trois", "66 %", "66%", "un sur deux"]
NEUTRE, ACCENT = "#56B4E9", "#D55E00"   # Okabe-Ito : bleu ciel neutre / vermillon accent
NOIR = "#000000"
CAP_LABEL = "capacite assise (63)"


def ligne_encadrants(enc):
    """Ligne de cadence du bloc d'identite (heures et minutes uniquement)."""
    if enc["premier_du_service"] and enc["dernier_du_service"]:
        return "Trains encadrants ce jour-la : seule course du service (aucun encadrant)"
    gauche = ("premier train du service (aucun precedent)" if enc["premier_du_service"]
              else f"precedent {enc['precedent']['heure']}")
    droite = ("dernier train du service (aucun suivant)" if enc["dernier_du_service"]
              else f"suivant {enc['suivant']['heure']}")
    av, ap = enc["intervalle_avant_min"], enc["intervalle_apres_min"]
    if enc["cadence_uniforme"]:
        suff = f" (cadence {av} minutes)"
    elif av is not None and ap is not None:
        suff = f" (intervalles {av} min / {ap} min)"
    elif ap is not None:
        suff = f" (intervalle au suivant {ap} min)"
    elif av is not None:
        suff = f" (intervalle au precedent {av} min)"
    else:
        suff = ""
    return f"Trains encadrants ce jour-la : {gauche}, {droite}{suff}"


def firewall(text, label):
    hits = [(p, text[max(0, m.start() - 25):m.end() + 25]) for p in FORBIDDEN
            for m in re.finditer(p, text, re.IGNORECASE)]
    if hits:
        print(f"[FIREWALL] {label} : {len(hits)} fuite(s)")
        for p, ctx in hits[:15]:
            print(f"    {p} -> ...{ctx.strip()}...")
        raise SystemExit(f"Firewall {label} : interdit detecte.")
    return text


# ── figures ─────────────────────────────────────────────────────────────────
def _profil_axes(profil, det_ordre):
    labels = [p["gare"] for p in profil]
    preds = [p["predit"] for p in profil]
    couleurs = [ACCENT if p["ordre"] == det_ordre else NEUTRE for p in profil]
    return labels, preds, couleurs


def _label_bar(ax, i, val, color="#222222", dy=2):
    ax.annotate(f"{round(val)}", (i, val), ha="center", va="bottom", fontsize=8,
                color=color, xytext=(0, dy), textcoords="offset points")


def fig_predit(cas, course):
    profil = cas["outil"]["profil_predit"]; det = cas["outil"]["determinant_ordre"]
    labels, preds, couleurs = _profil_axes(profil, det)
    fs.apply_style()
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    x = list(range(len(profil)))
    ax.bar(x, preds, color=couleurs)
    for i, p in enumerate(preds):                                # etiquettes de valeur (>=8 pt)
        _label_bar(ax, i, p)
    ax.set_ylim(0, max(preds) * 1.20)
    ax.axhline(fs.SEUIL_UM, color=NOIR, linestyle="--", linewidth=1.0)
    ax.plot([], [], color=NOIR, linestyle="--", linewidth=1.0, label=CAP_LABEL)
    ax.plot([], [], color=ACCENT, linewidth=6, label="troncon determinant")
    ax.plot([], [], color=NEUTRE, linewidth=6, label="autres troncons")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3, fontsize=8)
    fs.finalize(ax, xlabel="Troncon (gare de depart, sens du parcours)",
                ylabel="Voyageurs 2e classe (estimation)")
    etiquettes = [str(round(p)) for p in preds]
    labels_txt = " ".join(labels + etiquettes + [CAP_LABEL, "troncon determinant", "autres troncons",
                          "Troncon gare de depart sens du parcours", "Voyageurs 2e classe estimation"])
    firewall(labels_txt, f"figure predit Cas {cas['cas']}")
    assert "realise" not in labels_txt.lower()                   # section 2 : aucune serie realisee
    path = FIGDIR / f"cas_{cas['cas']}_{course}_profil_predit.png"
    fs.save(fig, path); plt.close(fig)
    return path


def fig_compare(cas, course):
    profil = cas["realise"]["profil"]; det = cas["realise"]["determinant_ordre"]
    labels, preds, couleurs = _profil_axes(profil, det)
    reals = [p["realise"] for p in profil]
    det_i = next(i for i, p in enumerate(profil) if p["ordre"] == det)
    fs.apply_style()
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    x = list(range(len(profil)))
    ax.bar(x, preds, color=couleurs, zorder=2)
    ax.plot(x, reals, color=NOIR, marker="o", markersize=4, linewidth=1.3, zorder=3, label="realise")
    # etiquettes : realise sur tous les troncons ; estimation UNIQUEMENT sur le determinant (toujours les deux)
    for i, r in enumerate(reals):
        _label_bar(ax, i, r, color=NOIR, dy=3)
    _label_bar(ax, det_i, preds[det_i], color="#7a3b00", dy=2)
    ax.set_ylim(0, max(max(preds), max(reals)) * 1.20)
    ax.axhline(fs.SEUIL_UM, color=NOIR, linestyle="--", linewidth=1.0)
    ax.plot([], [], color=NEUTRE, linewidth=6, label="estimation")
    ax.plot([], [], color=NOIR, linestyle="--", linewidth=1.0, label=CAP_LABEL)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3, fontsize=8)
    fs.finalize(ax, xlabel="Troncon (gare de depart, sens du parcours)",
                ylabel="Voyageurs 2e classe")
    etiquettes = [str(round(v)) for v in reals] + [str(round(preds[det_i]))]
    labels_txt = " ".join(labels + etiquettes + [CAP_LABEL, "estimation", "realise",
                          "Troncon gare de depart sens du parcours", "Voyageurs 2e classe"])
    firewall(labels_txt, f"figure compare Cas {cas['cas']}")
    path = FIGDIR / f"cas_{cas['cas']}_{course}_profil_compare.png"
    fs.save(fig, path); plt.close(fig)
    return path


# ── markdown par cas ──────────────────────────────────────────────────────────
def md_cas(course):
    cas = DATA["cas"][course]
    idt = cas["identite"]; fam = cas["familles"]; o = cas["outil"]; rz = cas["realise"]
    fpng = f"figures/cas_{cas['cas']}_{course}_profil_predit.png"
    cpng = f"figures/cas_{cas['cas']}_{course}_profil_compare.png"
    L = []
    L.append(f"# Cas {cas['cas']} : course {course}\n")
    # --- Section 1 ---
    L.append("## Section 1 - Ce que l'on sait la veille (J-1)\n")
    L.append(f"**Course {course}** - {idt['date']}, {idt['type_jour'].replace('_', ' ')}  ")
    L.append(f"{idt['origine']} ({idt['heure_depart']}) vers {idt['terminus']} ({idt['heure_arrivee']}) - sens {idt['sens']}  ")
    L.append(f"{ligne_encadrants(cas['encadrants'])}\n")
    cal = fam["1_calendrier"]
    sais = ", ".join(cal["saison"]) if isinstance(cal["saison"], list) else cal["saison"]
    L.append(f"- **Calendrier** : {cal['type_jour'].replace('_', ' ')} ; vacances scolaires "
             f"{'oui' if cal['vacances_scolaires'] else 'non'} ; jour ferie {'oui' if cal['jour_ferie'] else 'non'} ; saison : {sais}")
    ev = fam["2_evenements"]
    if ev.get("noms"):
        evtxt = ", ".join(f"{n['nom']} ({n['commune']}, {n['zone'].replace('_', ' ')})*" for n in ev["noms"])
    else:
        evtxt = ev.get("libelle", "aucun evenement au calendrier")
    L.append(f"- **Evenements du jour** : {evtxt}")
    da = fam["3_demande_annoncee"]
    if da["resa2c"] <= 0:
        L.append("- **Demande annoncee** : aucune reservation de groupe annoncee")
    else:
        L.append(f"- **Demande annoncee** : {da['resa2c']} places reservees ({da['n_dossiers']} dossier(s), "
                 f"plus gros groupe {da['max_groupe_2c']})")
    me = fam["4_meteo_prevue"]
    L.append(f"- **Meteo prevue** : {me['temperature_C']} C, precipitations {me['precip_mm']} mm ; "
             f"ensoleillement environ {me['ensoleillement_h']} h (sur un maximum saisonnier d'environ "
             f"{me['ensoleillement_max_saisonnier_h']} h) - valeur proxy, proche du realise")
    hi = fam["5_historique_recent"]
    hv = hi["histo_win7_2c_max"]
    hv = "fenetre incomplete" if hv is None else f"environ {round(hv)} voyageurs"
    L.append(f"- **Historique recent** : charge 2e classe maximale des dernieres circulations comparables = {hv}\n")
    L.append("*detail issu de la brochure source ; l'outil connait la presence et le caractere calendaire "
             "de l'evenement, pas son nom.*\n")
    L.append(f"{REVEL}\n")
    # --- Section 2 ---
    L.append("## Section 2 - Ce que l'outil propose\n")
    L.append(f"**Estimation de charge au troncon le plus charge : environ {o['estimation']} voyageurs.**\n")
    L.append(f"**Recommandation : {o['recommandation']}.**  ")
    L.append(f"Declencheur : {o['declencheur']}.\n")
    if o["note_deux_composants"]:
        L.append(f"{o['note_deux_composants']}.\n")
    casc = o["cascade"]
    L.append("Decomposition de l'estimation (en voyageurs, ecarts par rapport a une course moyenne comparable) :\n")
    L.append(f"- Estimation de depart (course moyenne comparable) : {casc['base']}")
    for fa in casc["familles"]:
        L.append(f"- {fa['famille']} : {fa['delta']:+d}")
    L.append(f"- Autres facteurs : {casc['autres']:+d}")
    L.append(f"- **Estimation pour cette course : {casc['total']}**\n")
    L.append(f"![Profil de charge estimee par troncon]({fpng})\n")
    L.append(f"{REVEL}\n")
    # --- Section 3 ---
    L.append("## Section 3 - Ce qui s'est reellement passe\n")
    L.append(f"**Charge constatee au troncon que l'outil pointait : {rz['charge_determinant']} voyageurs.**  ")
    if rz["charge_parcours_max"] != rz["charge_determinant"]:
        L.append(f"**Au troncon le plus charge du parcours : {rz['charge_parcours_max']} voyageurs.**  ")
    L.append("")
    L.append(f"- Composition roulee ce jour-la : {rz['composition']}")
    L.append(f"- Decision de l'exploitation : {rz['decision']}\n")
    L.append(f"![Profil estime et realise par troncon]({cpng})\n")
    return "\n".join(L)


def md_presentation():
    L = ["# L'outil d'aide au doublement : en bref\n",
         "## Ce qu'il fait\n",
         "- Pour chaque course du lendemain, il propose une recommandation binaire : doubler ou ne pas doubler.\n",
         "## Ce qu'il combine\n",
         "- Une prevision de frequentation appuyee sur environ 160 informations, regroupees en cinq familles "
         "(calendrier, evenements, demande annoncee, meteo prevue, historique recent),",
         "- et une regle de reservations (une demande de groupe annoncee au-dela de la capacite assise declenche le doublement).\n",
         "## Son reglage\n",
         "- Environ 850 recommandations par an ; regle pour qu'environ sept sur dix se confirment.\n",
         "## Ce qu'il ne fait pas\n",
         "- Il ne connait pas la disponibilite du materiel ni des conducteurs.\n"]
    return "\n".join(L)


# ── fiche intervieweur ────────────────────────────────────────────────────────
ATTENTION = {
    "1423": "Paire 166+ du jour (voir note du 18 mai). L'outil et l'exploitation convergent ici (recommandation confirmee).",
    "1326": "Pic recent eleve (environ 76) et 45 places reservees ont tire l'estimation vers le haut (+30 et +26 dans la cascade), "
            "mais la charge reelle est retombee a 13 (8 seulement au troncon pointe) : l'outil a suivi sa memoire courte, un jour finalement calme.",
    "1448": "Course non recommandee par l'outil mais doublee par l'exploitation : divergence a explorer (l'exploitation a vu ce que l'outil n'a pas).",
    "1435": "Silence correct : estimation basse, journee calme, pas de doublement. Cas de calibration du non-declenchement.",
    "1416": "Recommandation portee par la regle reservations (78 places), l'estimation de charge restant sous le seuil : pedagogie des deux composants.",
    "1508": "Estimation a deux voyageurs du seuil de declenchement ; pic recent environ 79 ; pluie annoncee. Cas limite : l'outil passe tout pres sans declencher.",
}
POSTURE = ("**Posture** : les six cas sont un echantillon CONTRASTE (3 recommandations justes dont une que la "
           "pratique a manquee, 3 erreurs surponderees par protocole), pas un bilan de performance. Chaque critique "
           "du repondant est une DONNEE (conditions de mefiance), pas un point perdu. Ne jamais defendre l'outil ; "
           "noter, relancer. Les chiffres d'ensemble viennent apres l'entretien, pas pendant.")
NOTE_SHAP = ("Note de lecture de la cascade : les contributions sont RELATIVES a la moyenne. L'estimation de depart "
             "est celle d'une course moyenne comparable ; chaque famille indique de combien elle ecarte l'estimation "
             "de cette moyenne (en voyageurs), ce n'est pas une charge absolue.")
NOTE_QUANTIF = ("Note explication quantifiee : la cascade chiffree en voyageurs a un pouvoir persuasif accru. Si le "
                "repondant valide l'explication du Cas 2 (ou l'outil s'est trompe avec assurance), la relance QD3 devient OBLIGATOIRE.")
NOTE_DEPART = ("Note estimation de depart : l'estimation de depart de la cascade est la moyenne du modele du SEGMENT "
               "ou se trouve le troncon determinant (haut de ligne : environ 8 ; bas de ligne : environ 21). Si le "
               "repondant compare deux cascades : la course moyenne comparable n'est pas la meme selon que le troncon "
               "decisif est sur le haut ou le bas de la ligne ; le haut est en moyenne moins charge. (Seul le Cas 1 a "
               "son troncon determinant sur le haut.)")
NOTE_CADENCE = ("Cadence : les trains encadrants figurent au bloc d'identite. Distinction a connaitre : l'outil "
                "consomme l'intervalle au train suivant comme PREDICTEUR de charge (il influe sur l'estimation), "
                "mais ne raisonne PAS en report de charge au moment de recommander (aucune regle du type « seuil "
                "frole mais releve a 15 minutes, donc ne pas doubler »). Si le repondant mobilise ce raisonnement "
                "de report, c'est une DONNEE d'elicitation a creuser (relance : « l'outil devrait-il en tenir "
                "compte, et comment ? »), pas une objection a corriger. Source : horaire theorique ISTDATEN "
                "(grille planifiee connue a J-1), identique a celle du feature ; aucun ecart de source. Nuance de "
                "grain : le feature est calcule par troncon, la cadence affichee est celle du troncon d'origine.")
QD2 = ["Question(s) posee(s) au repondant (QD2, apres la section 2, AVANT la revelation de la section 3) :",
       "    - Sur ce cas, qu'auriez-vous decide, vous, avec les memes informations ?",
       "    - La recommandation de l'outil vous parait-elle justifiee ? Pourquoi ?",
       "    - Les facteurs affiches vous paraissent-ils plausibles et pertinents ? Cette explication renforce-t-elle ou nuance-t-elle votre confiance dans la recommandation ?",
       "    - (apres revelation de la section 3) Maintenant que vous voyez l'affluence reelle, cela change-t-il votre regard sur la recommandation ?"]
QD3 = ["QD3 :",
       "  - Apres avoir vu ces cas, dans quelles situations feriez-vous confiance a cet outil, et dans quelles situations vous mefieriez-vous ?",
       "  - Une explication convaincante suffit-elle a justifier la confiance, y compris sur les cas ou l'outil s'est trompe ?"]
QD4 = ["QD4 :",
       "  - Si l'outil vous donne une recommandation qui contredit votre intuition, que faites-vous ?",
       "  - Sur quoi vous fonderiez-vous pour le suivre ou le contredire ?"]


def md_interviewer():
    L = ["# Fiche intervieweur - entretien naturaliste (section D)\n",
         "## Preambule et pare-feux\n",
         f"- {POSTURE}",
         "- Ordre de presentation verrouille : Cas 1 (1423), Cas 2 (1326), Cas 3 (1448), Cas 4 (1435), Cas 5 (1416), Cas 6 (1508).",
         "- Ne presenter aucun resultat agrege (precision, rappel, couts) avant ou pendant la section D.",
         "- Ne pas mentionner la limite de 166 personnes ni la charge de 12,7 t avant la grille H7 : laisser le repondant l'introduire.",
         "- Laisser le repondant faire lui-meme les rapprochements (ne pas souffler la cellule ni la raison de selection).",
         f"- {NOTE_SHAP}",
         f"- {NOTE_QUANTIF}",
         f"- {NOTE_DEPART}",
         f"- {NOTE_CADENCE}\n"]
    # contraste factuel de cadence : cas le plus serre et cas le plus large (re-derive)
    cad = {c: DATA["cas"][c]["encadrants"]["intervalle_apres_min"] for c in ORDRE
           if DATA["cas"][c]["encadrants"]["intervalle_apres_min"] is not None}
    c_serre = min(cad, key=lambda c: cad[c])
    c_large = max(cad, key=lambda c: cad[c])
    contraste = {}
    for c, qualif in ((c_serre, "serree"), (c_large, "large")):
        e = DATA["cas"][c]["encadrants"]
        contraste[c] = (f"Cadence la plus {qualif} des six cas : {e['intervalle_apres_min']} minutes au suivant "
                        f"(precedent {e['precedent']['heure']}, suivant {e['suivant']['heure']}, "
                        f"depart {e['heure_depart_course']}).")
    for course in ORDRE:
        cas = DATA["cas"][course]; nt = NOTES[course]["notes_intervieweur"]; cell = NOTES[course]["cellule"]
        L.append(f"## Cas {cas['cas']} - course {course} ({cas['identite']['date']}) - cellule {cell}\n")
        L.append(f"- Raison de selection : {nt['raison_selection']}")
        L.append(f"- Point d'attention : {ATTENTION[course]}")
        if course in contraste:
            L.append(f"- Point d'attention (cadence) : {contraste[course]}")
        if nt.get("lecture_166plus"):
            L.append(f"- Lecture 166+ (ne pas exhiber avant H7) : {nt['lecture_166plus']}")
        if nt.get("note_conduite_H7"):
            L.append(f"- Conduite H7 : {nt['note_conduite_H7']}")
        if nt.get("note_conduite"):
            L.append(f"- Conduite (18 mai) : {nt['note_conduite']}")
        L.append("- " + QD2[0])
        L.extend(QD2[1:])
        L.append("")
    L.append("## Apres le Cas 6\n")
    L.append("- " + QD3[0])
    L.extend(QD3[1:])
    L.append("- " + QD4[0])
    L.extend(QD4[1:])
    return "\n".join(L)


def md_table():
    L = ["# Table de traduction des facteurs (SHAP) - usage intervieweur\n",
         "Correspondance entre les variables du modele (au troncon determinant de chaque cas), leur libelle "
         "decideur (codebook, libelle_fr) et le regroupement metier affiche en section 2. Valeurs SHAP "
         "numeriques regroupees par famille dans les supports, jamais brutes.\n",
         "| Variable (pipeline) | Libelle decideur (codebook) | Regroupement affiche |",
         "|---|---|---|"]
    for col, d in DATA["table_traduction"].items():
        L.append(f"| `{col}` | {d['libelle_fr']} | {d['groupe_decideur']} |")
    return "\n".join(L) + "\n"


def main():
    produced = []
    # presentation + cas (JEU A) : firewall
    pres = firewall(md_presentation(), "presentation")
    (OUTDIR / "00_presentation_outil.md").write_text(pres); produced.append("00_presentation_outil.md")
    for course in ORDRE:
        cas = DATA["cas"][course]
        txt = firewall(md_cas(course), f"cas {cas['cas']} ({course})")
        (OUTDIR / f"cas_{cas['cas']}_{course}.md").write_text(txt)
        produced.append(f"cas_{cas['cas']}_{course}.md")
        if not SKIP_FIGURES:                                   # --no-figures : figures inchangees
            fig_predit(cas, course); fig_compare(cas, course)
            produced.append(f"figures/cas_{cas['cas']}_{course}_profil_predit.png")
            produced.append(f"figures/cas_{cas['cas']}_{course}_profil_compare.png")
    # jeu B + table (pas de firewall : documents intervieweur)
    (OUTDIR / "fiche_intervieweur.md").write_text(md_interviewer()); produced.append("fiche_intervieweur.md")
    (OUTDIR / "table_traduction_shap.md").write_text(md_table()); produced.append("table_traduction_shap.md")
    print("=== Livrables ===")
    for p in produced:
        print(f"  docs/entretiens/supports/{p}")
    print(f"\n[OK] {sum(1 for p in produced if p.endswith('.md'))} markdown + "
          f"{sum(1 for p in produced if p.endswith('.png'))} figures")


if __name__ == "__main__":
    main()
