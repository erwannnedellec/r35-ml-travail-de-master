#!/usr/bin/env python3
"""Section 4.4.1 — Matrice de couverture des sources par annee horaire (H16-H25).

Deux livrables, dans l'ordre exige par la consigne :
  1. VERIFICATION D'ABORD : pour chaque source x annee horaire, l'etat
     (disponible / partiel ou degrade / indisponible) est DERIVE des donnees elles-memes
     (comptages par annee dans les tables sources canoniques), par des regles explicites.
     Le tableau de verification et les preuves sont imprimes puis ecrits dans
     `docs/memoire/rapport_verifs_section_4_4_1.md`.
  2. FIGURE : `fig_couverture_sources.png` — matrice 12 sources x 10 annees, trois etats
     en teintes Okabe-Ito distinctes, perimetre retenu H22-H25 (= perimetre du `ml_dataset`
     canonique, PAS la fenetre d'entrainement) marque d'un encadre sobre.

Charte : `src/memoire/figstyle.py` (Okabe-Ito, 16 cm, 300 DPI, sans titre embarque,
bbox tight). Reproductibilite byte-a-byte : SOURCE_DATE_EPOCH=1782000000 pose en tete.

Semantique du « partiel » et cellules signalees : voir le rapport de verification.
LECTURE SEULE sur les donnees ; ecrit un PNG et un MD.
"""
import os
os.environ.setdefault("SOURCE_DATE_EPOCH", "1782000000")  # byte-repro, en tete (avant matplotlib)

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DOSSIER = Path(__file__).resolve().parent
RAPPORT = ROOT / "docs" / "memoire" / "rapport_verifs_section_4_4_1.md"
sys.path.insert(0, str(ROOT / "src" / "memoire"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Patch  # noqa: E402

P = ROOT / "data"
YEARS = [f"H{n}" for n in range(16, 26)]
CANONIQUE = "ba493568"           # empreinte du ml_dataset gele (perimetre retenu H22-H25)
INDISPO, PARTIEL, DISPO = 0, 1, 2
ETIQ = {DISPO: "disponible", PARTIEL: "partiel ou degrade", INDISPO: "indisponible"}

# --- Libelles de lignes alignes sur les titres de 4.3 (francais accentue, sans id interne) ---
SOURCES = [
    ("S01", "Comptage automatique des voyageurs (APC)"),
    ("S02", "Réalisation de l'offre (ISTDATEN)"),
    ("S03", "Population (STATPOP)"),
    ("S04", "Emplois et entreprises (STATENT)"),
    ("S05", "Météorologie (MétéoSuisse)"),
    ("S06", "Événements (manifestations régionales)"),
    ("S07", "Réservations de groupes (ResSys)"),
    ("S08", "Registre des rotations (compositions engagées)"),
    ("S09", "Vacances scolaires et jours fériés"),
    ("S10", "Exploitation du ski aux Pléiades"),
    ("S11", "Horaires publiés"),
    ("S12", "Origine-destination (SIMBA)"),
]


# ---------------------------------------------------------------------------
# Utilitaires : mapping date -> annee horaire (dimension officielle)
# ---------------------------------------------------------------------------
def _dim_annees():
    dim = pd.read_csv(P / "dimension/annees_horaires.csv", sep=";")
    dim["Debut"] = pd.to_datetime(dim["Debut"], format="%d.%m.%Y", errors="coerce")
    dim["Fin"] = pd.to_datetime(dim["Fin"], format="%d.%m.%Y", errors="coerce")
    caldays = {r.Annee: int(r["Nombre de jours"]) for _, r in dim.iterrows()
               if pd.notna(r["Nombre de jours"])}
    bornes = [(r.Annee, r.Debut, r.Fin) for _, r in dim.iterrows()
              if r.Annee in YEARS and pd.notna(r.Debut) and pd.notna(r.Fin)]
    return caldays, bornes


CALDAYS, BORNES = _dim_annees()


def to_hnn(dts):
    s = pd.to_datetime(dts, errors="coerce")
    out = pd.Series(pd.NA, index=s.index, dtype="object")
    for annee, deb, fin in BORNES:
        out[(s >= deb) & (s <= fin)] = annee
    return out


def couv_calendaire(dates):
    """jours distincts / jours calendaires, par annee horaire."""
    h = to_hnn(dates)
    d = pd.DataFrame({"h": h, "d": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna(subset=["h"])
    g = d.groupby("h")["d"].nunique()
    return {y: g.get(y, 0) / CALDAYS[y] for y in YEARS}


# ---------------------------------------------------------------------------
# 1. VERIFICATION : evidences + derivation des etats par regles explicites
# ---------------------------------------------------------------------------
def verifier():
    lignes_preuve = []  # (code, [evidence par annee], etats)
    etats = {}          # code -> np.array de 10 etats
    preuves = {}        # code -> dict annee -> texte court

    # -- S01 APC : couverture calendaire (base_date). partiel si trou notable. --
    apc = pd.read_parquet(P / "processed/sources/apc_stacked.parquet",
                          columns=["base_date", "id_mode_comptage",
                                   "base_tx_equipement_afz_2eme_classe"])
    c_apc = couv_calendaire(apc["base_date"])
    st = []
    for y in YEARS:
        c = c_apc[y]
        st.append(DISPO if c >= 0.98 else (PARTIEL if c >= 0.50 else INDISPO))
    etats["S01"] = np.array(st)
    preuves["S01"] = {y: f"couv. {100*c_apc[y]:.1f}%" for y in YEARS}
    # element de reponse « APC avant H22 » : mode de comptage + taux d'equipement AFZ
    apc["h"] = to_hnn(apc["base_date"])
    part_afz = apc.dropna(subset=["h"]).groupby("h")["id_mode_comptage"].apply(
        lambda s: 100 * (s == "AFZ").mean())
    txeq = apc.dropna(subset=["h"]).groupby("h")["base_tx_equipement_afz_2eme_classe"].mean()
    apc_note = {y: (round(float(part_afz.get(y, np.nan)), 1), round(float(txeq.get(y, np.nan)), 0))
                for y in YEARS}

    # -- S02 ISTDATEN : realisation (dates) + horodatage reel (profil de retard). --
    ist = pd.read_parquet(P / "processed/sources/istdaten_clean.parquet",
                          columns=["date", "reel_depart"])
    c_ist = couv_calendaire(ist["date"])
    ist["h"] = to_hnn(ist["date"])
    reel = ist.dropna(subset=["h"]).groupby("h")["reel_depart"].apply(lambda s: s.notna().mean())
    st = []
    for y in YEARS:
        if c_ist[y] < 0.05:
            st.append(INDISPO)                    # H16-H17 : source non publiee
        elif float(reel.get(y, 0.0)) >= 0.70:
            st.append(DISPO)                      # horodatage reel majoritaire (H24-H25)
        else:
            st.append(PARTIEL)                    # realisation OK, ponctualite absente/en montee
    etats["S02"] = np.array(st)
    preuves["S02"] = {y: (f"couv. {100*c_ist[y]:.0f}% ; réel {100*float(reel.get(y,0)):.0f}%"
                          if c_ist[y] >= 0.05 else "absente") for y in YEARS}

    # -- S03 STATPOP : millesime majoritaire (Z-2) present au grain gare ? --
    sp = pd.read_parquet(P / "processed/sources/statpop_clean.parquet",
                         columns=["annee_enquete_statpop"])
    mill_sp = set(int(v) for v in sp.annee_enquete_statpop.dropna().unique())
    st, pr = [], {}
    for i, y in enumerate(YEARS):
        m = 2016 + i - 2                          # H(16+i) -> civil 2016+i -> Z-2
        ok = m in mill_sp
        st.append(DISPO if ok else INDISPO)
        pr[y] = f"millésime {m} " + ("présent" if ok else "absent")
    etats["S03"] = np.array(st)
    preuves["S03"] = pr

    # -- S04 STATENT : millesime majoritaire (Z-3) present au grain gare ? --
    stt = pd.read_parquet(P / "processed/sources/statent_clean_causal.parquet",
                          columns=["annee_enquete_statent"])
    mill_st = set(int(v) for v in stt.annee_enquete_statent.dropna().unique())
    st, pr = [], {}
    for i, y in enumerate(YEARS):
        m = 2016 + i - 3                          # Z-3
        ok = m in mill_st
        st.append(DISPO if ok else INDISPO)
        pr[y] = f"millésime {m} " + ("présent" if ok else "absent (grain gare)")
    etats["S04"] = np.array(st)
    preuves["S04"] = pr

    # -- S05 METEO : couverture calendaire station Vevey. --
    mv = pd.read_parquet(P / "processed/sources/meteo_vev_clean.parquet",
                         columns=["reference_timestamp"])
    c_me = couv_calendaire(mv["reference_timestamp"])
    etats["S05"] = np.array([DISPO if c_me[y] >= 0.98 else PARTIEL for y in YEARS])
    preuves["S05"] = {y: f"couv. {100*c_me[y]:.0f}%" for y in YEARS}

    # -- S06 EVENEMENTS : liste annuelle presente (dim couvre l'annee). --
    ev = pd.read_parquet(P / "dimension/dim_manifestations_riviera.parquet", columns=["date"])
    nj = to_hnn(ev["date"]).value_counts()
    etats["S06"] = np.array([DISPO if int(nj.get(y, 0)) > 0 else INDISPO for y in YEARS])
    preuves["S06"] = {y: f"{int(nj.get(y,0))} jours-manif." for y in YEARS}

    # -- S07 RESA : reservations natives (exports) presentes l'annee de voyage. --
    nres = _resa_natif()
    etats["S07"] = np.array([DISPO if nres[y] > 0 else INDISPO for y in YEARS])
    preuves["S07"] = {y: f"{nres[y]} résa abouties J-1" for y in YEARS}

    # -- S08 ROTATIONS : couverture calendaire du brut rotations_23_25. --
    rot = pd.read_csv(P / "external/rotations/rotations_23_25.csv", sep=None, engine="python")
    dcol = rot.columns[0]  # TrainDate (BOM)
    c_rot = couv_calendaire(rot[dcol])
    etats["S08"] = np.array([DISPO if c_rot[y] >= 0.98 else (PARTIEL if c_rot[y] >= 0.05 else INDISPO)
                             for y in YEARS])
    preuves["S08"] = {y: (f"couv. {100*c_rot[y]:.0f}%" if c_rot[y] > 0 else "absente") for y in YEARS}

    # -- S09 VACANCES/FERIES : calendrier deterministe couvre l'annee. --
    va = pd.read_parquet(P / "dimension/dim_vacances_feries_vaud.parquet", columns=["date"])
    c_va = couv_calendaire(va["date"])
    etats["S09"] = np.array([DISPO if c_va[y] >= 0.98 else PARTIEL for y in YEARS])
    preuves["S09"] = {y: f"couv. {100*c_va[y]:.0f}%" for y in YEARS}

    # -- S10 SKI : source officielle vs reconstruite (dim_ski_pleiades). --
    sk = pd.read_parquet(P / "dimension/dim_ski_pleiades.parquet")
    dcol_sk = "date" if "date" in sk.columns else [c for c in sk.columns if "date" in c.lower()][0]
    scol = [c for c in sk.columns if "source" in c.lower()][0]
    sk["h"] = to_hnn(sk[dcol_sk])
    st, pr = [], {}
    for y in YEARS:
        sub = sk.loc[sk["h"] == y, scol].astype(str)
        n_off = int((sub.str.contains("official|officiel", case=False)).sum())
        n_rec = int((sub.str.contains("reconstru", case=False)).sum())
        if len(sub) == 0:
            st.append(INDISPO); pr[y] = "absente"
        elif n_off >= max(1, n_rec):
            st.append(DISPO); pr[y] = f"officielle ({n_off} j.)"
        else:
            st.append(PARTIEL); pr[y] = f"reconstruite ({n_rec} j.)"
    etats["S10"] = np.array(st)
    preuves["S10"] = pr

    # -- S11 HORAIRES : PDF annuel reconstruit, couverture calendaire. --
    ho = pd.read_parquet(P / "processed/horaires_r35_calendrier_circulation.parquet",
                         columns=["date", "annee_horaire"])
    g = ho.groupby("annee_horaire")["date"].nunique()
    c_ho = {y: int(g.get(y, 0)) / CALDAYS[y] for y in YEARS}
    etats["S11"] = np.array([DISPO if c_ho[y] >= 0.98 else (PARTIEL if c_ho[y] > 0 else INDISPO)
                             for y in YEARS])
    preuves["S11"] = {y: f"couv. {100*c_ho[y]:.0f}%" for y in YEARS}

    # -- S12 SIMBA : millesime lag N-1 present + part non-nulle. --
    sim = pd.read_parquet(P / "dimension/dim_simba_r35.parquet", columns=["simba_millesime"])
    mill_si = set(int(v) for v in sim.simba_millesime.dropna().unique())
    s10 = pd.read_parquet(P / "processed/stage_10_reservations.parquet",
                          columns=["horaire_annee_horaire", "simba_part_ga"])
    nn = s10.groupby("horaire_annee_horaire")["simba_part_ga"].apply(lambda s: s.notna().mean())
    st, pr = [], {}
    for i, y in enumerate(YEARS):
        m = 2016 + i - 1                          # lag N-1 : H(16+i) -> millesime civil-1
        share = float(nn.get(y, 0.0))
        if m not in mill_si:
            st.append(INDISPO); pr[y] = f"millésime {m} absent"
        elif share >= 0.70:
            st.append(DISPO); pr[y] = f"non-nul {100*share:.0f}%"
        else:
            st.append(PARTIEL); pr[y] = f"non-nul {100*share:.0f}%"
    etats["S12"] = np.array(st)
    preuves["S12"] = pr

    return etats, preuves, apc_note


def _resa_natif():
    """Reservations natives abouties anticipees (>=1 j) par annee de voyage, depuis les exports."""
    out = {y: 0 for y in YEARS}
    for f in sorted(glob.glob(str(P / "external/reservations/*.xlsx"))):
        df = pd.read_excel(f)
        h = to_hnn(df["Date de voyage"])
        dc = pd.to_datetime(df["Date de commande"], errors="coerce").dt.normalize()
        dv = pd.to_datetime(df["Date de voyage"], errors="coerce").dt.normalize()
        lead = (dv - dc).dt.days
        abouti = df["Statut de la réservation"].astype(str).str.contains("Abgeschlossen")
        keep = abouti & (lead >= 1)
        for y in YEARS:
            out[y] += int(((h == y) & keep).sum())
    return out


# ---------------------------------------------------------------------------
# 2. Matrice attendue (garde-fou : la derivation doit la reproduire exactement)
# ---------------------------------------------------------------------------
EXPECTED = {
    "S01": [2, 2, 2, 2, 2, 2, 1, 2, 2, 2],
    "S02": [0, 0, 1, 1, 1, 1, 1, 1, 2, 2],
    "S03": [0, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S04": [0, 0, 0, 0, 0, 2, 2, 2, 2, 2],
    "S05": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S06": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S07": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S08": [0, 0, 0, 0, 0, 0, 0, 1, 2, 2],
    "S09": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S10": [1, 1, 1, 1, 2, 2, 2, 2, 2, 2],
    "S11": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    "S12": [0, 0, 0, 0, 0, 0, 0, 2, 2, 1],
}


# ---------------------------------------------------------------------------
# 3. Rapport de verification (markdown)
# ---------------------------------------------------------------------------
def ecrire_rapport(etats, preuves, apc_note, h_ml):
    sym = {DISPO: "●", PARTIEL: "◐", INDISPO: "○"}
    L = []
    L.append("# Vérification — matrice de couverture des sources (section 4.4.1)\n")
    L.append("_Document généré par `docs/memoire/figures/section_4_4_1/make_fig_couverture_sources.py`. "
             "Toutes les valeurs sont dérivées des tables sources canoniques du dépôt. "
             "Périmètre retenu (encadré de la figure) = `ml_dataset.parquet` (H22-H25), "
             f"empreinte SHA256[:8] `{h_ml}` (attendu `{CANONIQUE}`)._\n")

    L.append("## Sémantique des trois états\n")
    L.append("- **● disponible** : la source fournit des enregistrements couvrant l'année horaire de "
             "façon nominale — couverture calendaire ≥ 98 % pour une source journalière ; millésime "
             "annuel causalement mobilisable et présent au grain gare pour une source annuelle ; "
             "réservations présentes pour ResSys.")
    L.append("- **◐ partiel ou dégradé** : enregistrements présents mais couverture calendaire "
             "incomplète (trou), dimension structurelle manquante ou en montée en charge, dates "
             "reconstruites, ou millésime partiellement renseigné. Le motif précis est nommé cellule "
             "par cellule ci-dessous.")
    L.append("- **○ indisponible** : aucun enregistrement natif ne couvre l'année horaire au grain "
             "exploitable (source non publiée, ou millésime causalement requis absent du dépôt au grain "
             "gare).\n")

    # tableau symbolique
    L.append("## Matrice vérifiée\n")
    L.append("| Source | " + " | ".join(YEARS) + " |")
    L.append("|" + "---|" * (len(YEARS) + 1))
    for code, lib in SOURCES:
        L.append(f"| {lib} | " + " | ".join(sym[int(v)] for v in etats[code]) + " |")
    L.append("\nLégende : ● disponible · ◐ partiel ou dégradé · ○ indisponible. "
             "Périmètre retenu H22-H25 (4 dernières colonnes).\n")

    # preuves détaillées
    L.append("## Preuves par cellule (comptages dans les tables sources)\n")
    for code, lib in SOURCES:
        L.append(f"**{code} — {lib}** — `" + "` `".join(
            f"{y}:{sym[int(etats[code][i])]} {preuves[code][y]}" for i, y in enumerate(YEARS)) + "`\n")

    # APC avant H22
    L.append("## Point de vérification demandé : APC avant H22 (taux d'équipement ? mode de comptage ?)\n")
    L.append("Le mode de comptage est homogène et automatique dès H16 : part AFZ par année horaire = "
             + ", ".join(f"{y} {apc_note[y][0]:.0f} %" for y in YEARS) + " (le complément de H16, ≈ 2 %, "
             "relève du mode ELAZ). La colonne `base_tx_equipement_afz_2eme_classe` vaut "
             + ", ".join(f"{y} {apc_note[y][1]:.0f}" for y in YEARS) + " : le passage 0 → 100 à la "
             "frontière H22/H23 est un **marqueur de régime d'export** (bascule de fichiers), non une "
             "absence de comptage automatique avant H23. Conclusion : APC n'est **pas** « partiel » "
             "avant H22 du fait de l'équipement ; le seul état dégradé APC est **H22** (trou calendaire "
             "de 29 jours, 92,0 % de couverture, concentré sur septembre 2022).\n")

    # cellules signalées / non directement vérifiables
    L.append("## Cellules signalées (sémantique et limites de vérifiabilité)\n")
    L.append("- **STATPOP H17-H20 (●)** : dérivées de la règle causale Z-2 appliquée aux millésimes "
             "bruts au grain gare 2015-2018 (présents dans `statpop_clean.parquet`). Ces millésimes ne "
             "sont **pas** intégrés au pipeline gelé (`statpop_clean_causal` ne retient que 2019-2023, "
             "→ H21-H25), le périmètre retenu étant H22-H25 : cellules *mobilisables mais non "
             "mobilisées*.")
    L.append("- **STATENT H16-H20 (○)** : les millésimes bruts hectares 2015-2017 existent au dépôt "
             "(`data/external/statent`) mais n'ont **jamais** été agrégés au grain gare (aucune table "
             "gare-grain antérieure à 2018) : couverture non vérifiable au grain gare → marquée "
             "indisponible.")
    L.append("- **ResSys H16-H21 (●)** : réservations natives présentes et comptées dans les exports "
             "(abouties anticipées : H16 978, H17 908, H18 837, H19 956, H20 571, H21 762). Les features "
             "`resa_*` ne sont toutefois jointes au pipeline que sur H22-H25 (périmètre) : source "
             "disponible, non mobilisée hors périmètre.")
    L.append("- **STATPOP H23 et H25** : les millésimes OFS 2021 et 2023 sont structurellement "
             "incomplets (champs ménages / plausibilité d'habitation non publiés) et forward-fillés "
             "(ADR-063) ; le signal population reste complet, seuls des sous-champs ménages sont imputés "
             "— non dégradé au niveau de la couverture source.")
    L.append("- **ISTDATEN H18-H23 (◐)** : la réalisation de l'offre (courses / annulations) est "
             "présente, mais l'horodatage réel (⇒ profil de retard, ponctualité) est quasi absent "
             "jusqu'à H22 (≤ 6 %) puis en montée en H23 (≈ 41 %, statut REAL publié dès le 31-05-2023). "
             "Le sous-flux VMCV (concurrence modale) reste par ailleurs partiel sur tout le périmètre "
             "(≤ 61 % des courses).")
    L.append("- **SIMBA (couverture ≠ rétention)** et **STATENT (idem)** : la matrice montre la "
             "couverture temporelle native ; les décisions de rejet de SIMBA (ADR-061) et d'exclusion "
             "de STATENT après ablation (ADR-064) relèvent de 4.3.10 / 4.5 et ne sont pas figurées ici.")
    L.append("- Aucune cellule **colorée** n'est sans preuve chiffrée ; les seules cellules "
             "« indisponibles par non-construction » (STATENT H16-H20) sont explicitement signalées "
             "ci-dessus.\n")

    RAPPORT.write_text("\n".join(L), encoding="utf-8")
    return RAPPORT


# ---------------------------------------------------------------------------
# 4. Figure : matrice categorielle 3 etats + encadre perimetre H22-H25
# ---------------------------------------------------------------------------
def figure(etats):
    # Teintes Okabe-Ito distinctes (sures daltonisme) + variation de clarte pour l'ordinal.
    COUL = {
        DISPO:   fs.OKABE_ITO["vert"],       # #009E73 present/complet
        PARTIEL: fs.OKABE_ITO["orange"],     # #E69F00 attention
        INDISPO: "#E6E6E6",                  # neutre : absence (hors des deux teintes de presence)
    }
    HACHURE = {PARTIEL: "///"}               # redondance non-coloree (lisible en niveaux de gris)

    M = np.array([etats[c] for c, _ in SOURCES])          # 12 x 10
    nrow, ncol = M.shape
    i22 = YEARS.index("H22")

    fs.apply_style()
    fig, ax = fs.new_fig(fs.LARGE, hauteur=fs.LARGE * 0.72)

    for r in range(nrow):
        for c in range(ncol):
            v = int(M[r, c])
            ax.add_patch(Rectangle((c, nrow - 1 - r), 1, 1,
                                   facecolor=COUL[v], edgecolor="white", linewidth=1.4,
                                   hatch=HACHURE.get(v), zorder=2))

    # encadre sobre du perimetre retenu H22-H25 (colonnes i22..fin), sur toutes les lignes
    ax.add_patch(Rectangle((i22, 0), ncol - i22, nrow, fill=False,
                           edgecolor="#222222", linewidth=1.8, zorder=5))
    ax.annotate("Périmètre retenu (H22-H25)", xy=(i22 + (ncol - i22) / 2, nrow + 0.18),
                ha="center", va="bottom", fontsize=8.5, color="#222222", fontweight="bold")

    ax.set_xlim(-0.02, ncol + 0.02)
    ax.set_ylim(-0.02, nrow + 0.55)
    ax.set_xticks([c + 0.5 for c in range(ncol)])
    ax.set_xticklabels(YEARS, fontsize=9)
    ax.set_yticks([nrow - 1 - r + 0.5 for r in range(nrow)])
    ax.set_yticklabels([lib for _, lib in SOURCES], fontsize=8.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xlabel("Année horaire")

    leg = [
        Patch(facecolor=COUL[DISPO], edgecolor="white", label="Disponible"),
        Patch(facecolor=COUL[PARTIEL], edgecolor="white", hatch="///", label="Partiel ou dégradé"),
        Patch(facecolor=COUL[INDISPO], edgecolor="white", label="Indisponible"),
        Patch(facecolor="none", edgecolor="#222222", linewidth=1.8, label="Périmètre retenu (H22-H25)"),
    ]
    ax.legend(handles=leg, loc="center left", bbox_to_anchor=(1.01, 0.5),
              fontsize=8.5, frameon=True, borderaxespad=0.0, handlelength=1.4)

    p = fs.save_fig(fig, "fig_couverture_sources", DOSSIER, largeur=fs.LARGE)
    plt.close(fig)
    return p


# ---------------------------------------------------------------------------
def main():
    import hashlib
    h_ml = hashlib.sha256((P / "processed/ml_dataset.parquet").read_bytes()).hexdigest()[:8]
    ml_years = sorted(pd.read_parquet(P / "processed/ml_dataset.parquet",
                                      columns=["horaire_annee_horaire"])["horaire_annee_horaire"].unique())
    print("=" * 78)
    print("Section 4.4.1 — Vérification de la couverture des sources (avant figure)")
    print("=" * 78)
    print(f"[perimetre] ml_dataset annees = {ml_years}  | empreinte {h_ml} (attendu {CANONIQUE})")
    assert ml_years == ["H22", "H23", "H24", "H25"], f"Perimetre inattendu : {ml_years}"

    etats, preuves, apc_note = verifier()

    # garde-fou : la derivation depuis les donnees doit reproduire la matrice documentee
    sym = {DISPO: "●", PARTIEL: "◐", INDISPO: "○"}
    print(f"\n{'source':46s} " + " ".join(y.rjust(3) for y in YEARS))
    ok = True
    for code, lib in SOURCES:
        got = list(int(v) for v in etats[code])
        exp = EXPECTED[code]
        flag = "" if got == exp else f"  != attendu {exp}"
        ok = ok and (got == exp)
        print(f"{code} {lib[:42]:42s} " + " ".join(sym[v].rjust(3) for v in got) + flag)
    assert ok, "La derivation des etats ne reproduit pas la matrice attendue (voir ci-dessus)."
    print("\n[OK] Etats derives des donnees == matrice documentee (EXPECTED).")

    r = ecrire_rapport(etats, preuves, apc_note, h_ml)
    print(f"[ecrit] {r.relative_to(ROOT)}")

    p = figure(etats)
    print(f"[ecrit] {p.relative_to(ROOT)}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
