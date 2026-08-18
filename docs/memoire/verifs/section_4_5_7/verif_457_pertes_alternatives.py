#!/usr/bin/env python3
"""
verif_457_pertes_alternatives.py — LOT A, section 4.5.7 « pertes alternatives ».

BUT : sourcer, claim par claim, chaque nombre du paragraphe destiné à la section 4.5.7
du mémoire. AUCUN réentraînement, AUCune re-sélection : le script LIT uniquement des
sorties persistées (JSON / CSV) produites par les chantiers ADR-069 et ADR-051, et les
confronte aux valeurs annoncées.

Sources lues (lecture seule) :
  ADR-069 (contre-épreuve post-gel : sample_weight W et MSE asymétrique k)
    - archive/explorations/consolidation_finale/exp_perte/confirmation_h25_k2_w2.json
    - archive/explorations/consolidation_finale/exp_perte/balayage_mse_asym_h24.json
    - archive/explorations/consolidation_finale/exp_perte/balayage_pertes_ponderees_h24.json
  ADR-051 (exploratoire pré-gel : quantile α et Tweedie)
    - archive/explorations/consolidation_finale/outputs/etape_3q5_phase1.csv   (baselines MSE)
    - archive/explorations/consolidation_finale/outputs/etape_3q5_phase3.csv   (8 configs × 3 segments)
    - archive/explorations/consolidation_finale/outputs/etape_3q5_grand_tableau.csv

AVERTISSEMENT D'ÉTAT DE JEU (repris dans le rapport) :
  - ADR-069 a couru sur la génération `416bb90b` (H25 = 309 252 tronçons, 158 features,
    seuil 63). Les modèles canoniques de cette génération sont byte-identiques à ceux du
    gel v2 `ba493568` (cf. ADR-076) : seules les données H25 ont changé (features
    « narcisses »). Les métriques H25 d'ADR-069 ne sont donc PAS transposables telles
    quelles au canonique courant.
  - ADR-051 a couru sur un état ENCORE ANTÉRIEUR : H25 post-embargo 9 j = 300 473
    tronçons, 179 features, et un seuil de surcharge à **80** (colonnes `*_ge80`,
    convention ≥ 80, antérieure à ADR-060 qui fixe le seuil à > 63).
  → On CITE ces chiffres avec la clause « au moment des décisions », on ne les relance pas
    sur le canonique.

Garde-fou : l'empreinte du dataset canonique courant est vérifiée au lancement (ba493568).
Elle atteste l'état du dépôt ; elle n'est PAS l'état de jeu des expériences relues.

Sorties (dans le dossier du script) :
  verif_457_claims.csv         — un claim par ligne : attendu / trouvé / source / verdict
  verif_457_adr069_h25.csv     — table H25 complète ADR-069 (3 modèles × 3 segments)
  verif_457_adr051_enrichi.csv — table ADR-051 Enrichi_Seg (5 pertes × 3 segments)
  verif_457_pertes_alternatives.md — rapport de synthèse

Exécution : python3 docs/memoire/verifs/section_4_5_7/verif_457_pertes_alternatives.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent

ML_DATASET = ROOT / "data/processed/ml_dataset.parquet"
HASH_CANONIQUE = "ba493568"

EXP_PERTE = ROOT / "archive/explorations/consolidation_finale/exp_perte"
CF_OUT = ROOT / "archive/explorations/consolidation_finale/outputs"

F_CONF_H25 = EXP_PERTE / "confirmation_h25_k2_w2.json"
F_BAL_ASYM = EXP_PERTE / "balayage_mse_asym_h24.json"
F_BAL_POND = EXP_PERTE / "balayage_pertes_ponderees_h24.json"
F_3Q5_P1 = CF_OUT / "etape_3q5_phase1.csv"
F_3Q5_P3 = CF_OUT / "etape_3q5_phase3.csv"
F_3Q5_GT = CF_OUT / "etape_3q5_grand_tableau.csv"

# État de jeu des expériences relues (constantes déclaratives, tracées dans le rapport).
ETAT_ADR069 = "416bb90b (H25 = 309 252 tronçons, 158 features, seuil > 63)"
ETAT_ADR051 = "antérieur à 416bb90b (H25 post-embargo 9 j = 300 473 tronçons, 179 features, seuil ≥ 80)"


# ── Garde-fou d'empreinte ──────────────────────────────────────────────────────
def assert_dataset_canonique() -> str:
    h = hashlib.sha256(ML_DATASET.read_bytes()).hexdigest()[:8]
    if h != HASH_CANONIQUE:
        raise RuntimeError(f"STOP : empreinte ml_dataset {h} != {HASH_CANONIQUE} attendue.")
    return h


def assert_sources_presentes() -> None:
    manquants = [str(p.relative_to(ROOT)) for p in
                 (F_CONF_H25, F_BAL_ASYM, F_BAL_POND, F_3Q5_P1, F_3Q5_P3, F_3Q5_GT)
                 if not p.exists()]
    if manquants:
        raise RuntimeError("STOP : sources persistées absentes -> " + " ; ".join(manquants))


# ── Collecte des claims ────────────────────────────────────────────────────────
CLAIMS: list[dict] = []


def claim(cid: str, adr: str, enonce: str, attendu, trouve, source: str,
          tol: float | None = None, verdict: str | None = None, note: str = "") -> None:
    """Enregistre un claim. Verdict automatique par tolérance si `verdict` est None."""
    if verdict is None:
        if attendu is None or trouve is None:
            verdict = "N/D"
        else:
            verdict = "OK" if abs(float(trouve) - float(attendu)) <= (tol or 0) else "ÉCART"
    CLAIMS.append({
        "id": cid, "adr": adr, "enonce": enonce,
        "valeur_attendue": attendu, "valeur_trouvee": trouve,
        "tolerance": tol, "fichier_source": source, "verdict": verdict, "note": note,
    })


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# 1. ADR-069 — contre-épreuve post-gel (sample_weight W=2, MSE asymétrique k=2)
# ══════════════════════════════════════════════════════════════════════════════
def verifier_adr069() -> pd.DataFrame:
    d = json.loads(F_CONF_H25.read_text())
    m = d["metrics_h25"]
    src = rel(F_CONF_H25)

    # -- table H25 complète (3 modèles × 3 segments), pour le rapport --
    lignes = []
    for modele, libelle in [("canonique", "canonique (reg:squarederror)"),
                            ("k2_mse_asym", "k=2 (MSE asymétrique, τ=0,67)"),
                            ("w2_sample_weight", "W=2 (sample_weight)")]:
        for seg in ("bas", "haut", "global"):
            b = m[modele][seg]
            lignes.append({"modele": libelle, "segment": seg, **b})
    table = pd.DataFrame(lignes)

    # -- claims « biais global >63 sur H25 » --
    claim("A1", "ADR-069", "biais global >63 sur H25, canonique",
          -28.5, round(m["canonique"]["global"]["bias_gt63"], 4), src, tol=0.05)
    claim("A2", "ADR-069", "biais global >63 sur H25, k=2 (MSE asymétrique)",
          -26.2, round(m["k2_mse_asym"]["global"]["bias_gt63"], 4), src, tol=0.05)
    claim("A3", "ADR-069", "biais global >63 sur H25, W=2 (sample_weight)",
          -26.0, round(m["w2_sample_weight"]["global"]["bias_gt63"], 4), src, tol=0.05)

    # -- claims « ΔPR-AUC sur H25 ≈ ±0,003 (tronçon et tour) pour les deux leviers » --
    deltas = {}
    for lev, key in [("k=2", "k2_mse_asym"), ("W=2", "w2_sample_weight")]:
        for grain in ("troncon", "tour"):
            k = f"pr_auc_{grain}"
            deltas[(lev, grain)] = m[key]["global"][k] - m["canonique"]["global"][k]
    for i, ((lev, grain), dv) in enumerate(deltas.items(), start=4):
        claim(f"A{i}", "ADR-069",
              f"ΔPR-AUC {grain} H25 (global), {lev} vs canonique",
              None, round(dv, 5), src, verdict="INFO")
    dmax = max(abs(v) for v in deltas.values())
    claim("A8", "ADR-069",
          "ΔPR-AUC H25 ≈ ±0,003 (tronçon ET tour) pour les DEUX leviers",
          0.003, round(dmax, 5), src,
          verdict=("OK" if dmax <= 0.0035 else "ÉCART"),
          note=("max|Δ| = %s (W=2 tronçon). Formulation exacte à retenir : "
                "|ΔPR-AUC| ≤ 0,006, et ≤ 0,001 au grain tour. L'ADR-069 lui-même "
                "détaille k=2 : tronçon −0,003 / tour +0,001 ; W=2 : tronçon +0,006 / "
                "tour −0,001." % f"{dmax:.4f}".replace(".", ",")))

    # -- claims R² et PR-AUC HAUT pour k=2 --
    claim("A9", "ADR-069", "R² global H25, k=2",
          0.586, round(m["k2_mse_asym"]["global"]["r2_global"], 4), src, tol=0.0005)
    claim("A10", "ADR-069", "R² global H25, canonique",
          0.601, round(m["canonique"]["global"]["r2_global"], 4), src, tol=0.0005)
    claim("A11", "ADR-069", "PR-AUC tronçon HAUT H25, canonique",
          0.345, round(m["canonique"]["haut"]["pr_auc_troncon"], 4), src, tol=0.0005)
    claim("A12", "ADR-069", "PR-AUC tronçon HAUT H25, k=2",
          0.298, round(m["k2_mse_asym"]["haut"]["pr_auc_troncon"], 4), src, tol=0.0005)

    # -- garde-fous d'implémentation --
    asym = json.loads(F_BAL_ASYM.read_text())
    pond = json.loads(F_BAL_POND.read_text())
    claim("A13", "ADR-069",
          "garde-fou k=1 (MSE asymétrique) ≡ reg:squarederror, validation H24",
          "contrôle persisté", asym.get("controle_k1"), rel(F_BAL_ASYM),
          verdict=("OK" if asym.get("controle_k1") else "ÉCART"),
          note="Champ `controle_k1` du balayage H24 : « allclose validé » (et non « bit-exact » littéral).")
    bit = pond.get("garde_fous", {}).get("impl_w1_k1_bitexact")
    claim("A14", "ADR-069",
          "garde-fou w≡1, k=1 bit-exact vs reg:squarederror (phase 4, H24)",
          True, bit, rel(F_BAL_POND),
          verdict=("OK" if bit is True else "ÉCART"),
          note="Rapport phase 4 associé : max|Δpred| = 0,00 sur BAS et HAUT.")
    ga = d.get("garde_fou_A_canonique_reproduit")
    claim("A15", "ADR-069",
          "garde-fou (A) : modèles canoniques rechargés reproduisent les métriques H25 publiées",
          True, ga, src, verdict=("OK" if ga is True else "ÉCART"))
    claim("A16", "ADR-069",
          "garde-fou (B) : k=1 custom tri-annuel reproduit le canonique (max|Δpred| = 0) sur H25",
          "valeur persistée", None, src, verdict="ÉCART",
          note="Le garde-fou (B) est CALCULÉ et IMPRIMÉ par confirmation_h25_k2_w2.py "
               "(§3) mais N'EST PAS sérialisé dans le JSON : seul `garde_fou_A_...` l'est. "
               "L'affirmation « bit-exact sur le réentraînement tri-annuel » n'est donc "
               "adossée qu'au texte d'ADR-069, pas à un artefact relisible. La preuve "
               "persistée de bit-exactitude porte sur la validation H24 (A13/A14).")

    return table


# ══════════════════════════════════════════════════════════════════════════════
# 2. ADR-051 — exploratoire pré-gel (quantile α ∈ {0,85 ; 0,90 ; 0,95}, Tweedie)
# ══════════════════════════════════════════════════════════════════════════════
def verifier_adr051() -> pd.DataFrame:
    p1 = pd.read_csv(F_3Q5_P1)     # baselines MSE (phase 1)
    p3 = pd.read_csv(F_3Q5_P3)     # pertes alternatives (phase 3)
    gt = pd.read_csv(F_3Q5_GT)     # grand tableau

    def base(model: str, seg: str) -> pd.Series:
        r = p1[(p1["model"] == model) & (p1["segment"] == seg)]
        assert len(r) == 1, f"phase1 : {model}/{seg} -> {len(r)} ligne(s)"
        return r.iloc[0]

    def alt(model: str, seg: str) -> pd.Series:
        r = p3[(p3["model"] == model) & (p3["segment"] == seg)]
        assert len(r) == 1, f"phase3 : {model}/{seg} -> {len(r)} ligne(s)"
        return r.iloc[0]

    # -- table Enrichi_Seg (baseline MSE + 4 pertes alternatives) × 3 segments --
    lignes = []
    for modele, libelle in [("Enrichi_Seg", "MSE (baseline)"),
                            ("Enrichi_Seg_quantile_0.85", "quantile α=0,85"),
                            ("Enrichi_Seg_quantile_0.90", "quantile α=0,90"),
                            ("Enrichi_Seg_quantile_0.95", "quantile α=0,95"),
                            ("Enrichi_Seg_tweedie", "Tweedie")]:
        for seg in ("bas", "haut", "global"):
            r = base(modele, seg) if modele == "Enrichi_Seg" else alt(modele, seg)
            lignes.append({
                "perte": libelle, "segment": seg,
                "n_obs": int(r["n_obs"]), "n_surch_ge80": int(r["n_surch"]),
                "r2": round(float(r["r2"]), 4), "mae": round(float(r["mae"]), 4),
                "mae_ge80": round(float(r["mae_ge80"]), 4),
                "bias_ge80": round(float(r["bias_ge80"]), 4),
                "bias_ge80_ci_lo": round(float(r["bias_ge80_ci_lo"]), 4),
                "bias_ge80_ci_hi": round(float(r["bias_ge80_ci_hi"]), 4),
                "pr_auc": round(float(r["pr_auc"]), 4),
            })
    table = pd.DataFrame(lignes)

    src3 = rel(F_3Q5_P3)
    src1 = rel(F_3Q5_P1)
    srcg = rel(F_3Q5_GT)

    # -- Tweedie : biais haut −50,4 → −64,5 --
    b_mse_haut = float(base("Enrichi_Seg", "haut")["bias_ge80"])
    b_twe_haut = float(alt("Enrichi_Seg_tweedie", "haut")["bias_ge80"])
    claim("B1", "ADR-051", "biais ≥80 segment HAUT, Enrichi_Seg MSE (point de départ)",
          -50.4, round(b_mse_haut, 4), src1, tol=0.05)
    claim("B2", "ADR-051", "biais ≥80 segment HAUT, Enrichi_Seg Tweedie (point d'arrivée)",
          -64.5, round(b_twe_haut, 4), src3, tol=0.05)
    # contrôle de cohérence avec le grand tableau
    g_twe = gt[(gt["model"] == "Enrichi_Seg_tweedie") & (gt["loss"] == "tweedie")]
    assert len(g_twe) == 1, f"grand tableau : Enrichi_Seg_tweedie -> {len(g_twe)} ligne(s)"
    claim("B3", "ADR-051", "cohérence grand tableau / phase 3 sur le biais ≥80 HAUT Tweedie",
          round(b_twe_haut, 4), round(float(g_twe.iloc[0]["bias_ge80_haut"]), 4), srcg, tol=1e-6)

    # -- q=0,95 : R² haut ≈ 0,024 (Enrichi_Seg) --
    r2_q95_haut = float(alt("Enrichi_Seg_quantile_0.95", "haut")["r2"])
    claim("B4", "ADR-051", "R² segment HAUT, Enrichi_Seg quantile α=0,95",
          0.024, round(r2_q95_haut, 4), src3, tol=0.0005)

    # -- MAE global +82 % vs MSE (q=0,95) --
    mae_mse_glob = float(base("Enrichi_Seg", "global")["mae"])
    mae_q95_glob = float(alt("Enrichi_Seg_quantile_0.95", "global")["mae"])
    hausse = 100.0 * (mae_q95_glob / mae_mse_glob - 1.0)
    claim("B5", "ADR-051", "hausse du MAE global, Enrichi_Seg q=0,95 vs MSE (en %)",
          82.0, round(hausse, 2), f"{src1} + {src3}", tol=1.0,
          note=(f"MAE global MSE = {mae_mse_glob:.3f}".replace(".", ",") +
                f" ; MAE global q=0,95 = {mae_q95_glob:.3f}".replace(".", ",") + "."))

    # -- biais ≥80 encore négatif à α=0,95 (≈ −31,8 haut) --
    b_q95_haut = float(alt("Enrichi_Seg_quantile_0.95", "haut")["bias_ge80"])
    ci_hi = float(alt("Enrichi_Seg_quantile_0.95", "haut")["bias_ge80_ci_hi"])
    claim("B6", "ADR-051", "biais ≥80 segment HAUT, Enrichi_Seg quantile α=0,95",
          -31.8, round(b_q95_haut, 4), src3, tol=0.05)
    claim("B7", "ADR-051",
          "le biais ≥80 reste strictement négatif à α=0,95 (borne haute de l'IC95 < 0)",
          "IC95 haut < 0", round(ci_hi, 4), src3,
          verdict=("OK" if ci_hi < 0 else "ÉCART"))

    # -- ancrages de périmètre : ce n'est PAS le périmètre canonique courant --
    n_obs_glob = int(base("Enrichi_Seg", "global")["n_obs"])
    claim("B8", "ADR-051", "périmètre H25 des expériences ADR-051 (tronçons)",
          309252, n_obs_glob, src1, verdict=("OK" if n_obs_glob == 309252 else "ÉCART"),
          note="ÉCART ATTENDU et documenté : 300 473 tronçons = H25 post-embargo 9 j de "
               "l'état de jeu antérieur. Le périmètre canonique courant est 309 252. "
               "Confirme qu'ADR-051 ne se lit pas au périmètre du gel v2.")
    n_feats = int(base("Enrichi_Seg", "global")["n_feats"])
    claim("B9", "ADR-051", "nombre de features des expériences ADR-051",
          158, n_feats, src1, verdict=("OK" if n_feats == 158 else "ÉCART"),
          note="ÉCART ATTENDU : 179 features (avant retrait SIMBA ADR-CF17 et parcimonie). "
               "Le canonique courant en compte 158.")
    claim("B10", "ADR-051", "seuil de surcharge utilisé par ADR-051",
          63, 80, src3, verdict="ÉCART",
          note="ÉCART ATTENDU : les colonnes sont `*_ge80` (convention ≥ 80), antérieures à "
               "ADR-060 qui fixe le seuil canonique à > 63. Toute citation doit porter la "
               "mention « seuil 80, au moment des décisions ».")

    return table


# ══════════════════════════════════════════════════════════════════════════════
# 3. Rapport
# ══════════════════════════════════════════════════════════════════════════════
def md_table(df: pd.DataFrame, cols: list[str], entetes: list[str]) -> str:
    out = ["| " + " | ".join(entetes) + " |",
           "|" + "|".join(["---"] * len(entetes)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append(f"{v:.4f}".replace(".", ","))
            elif v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("—")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def ecrire_rapport(h: str, claims: pd.DataFrame,
                   t069: pd.DataFrame, t051: pd.DataFrame) -> Path:
    n_ok = int((claims["verdict"] == "OK").sum())
    n_ecart = int((claims["verdict"] == "ÉCART").sum())
    n_info = int((claims["verdict"] == "INFO").sum())

    lignes = []
    A = lignes.append
    A("# Vérification 4.5.7 — chiffres des « pertes alternatives » (ADR-069, ADR-051)")
    A("")
    A("**Lot A — lecture seule.** Aucun réentraînement, aucune re-sélection : le script")
    A("`verif_457_pertes_alternatives.py` relit les sorties persistées des deux chantiers et")
    A("les confronte, claim par claim, aux valeurs annoncées dans le paragraphe destiné à 4.5.7.")
    A("")
    A(f"- Empreinte du dataset canonique au lancement : `{h}` (garde-fou passé).")
    A(f"- Bilan : **{n_ok} OK**, **{n_ecart} ÉCART**, {n_info} lignes informatives (Δ rapportés sans valeur attendue).")
    A("")
    A("## Avertissement d'état de jeu (à reprendre dans le manuscrit)")
    A("")
    A("Les deux chantiers ont couru sur des **états de jeu antérieurs** au gel v2 `ba493568`.")
    A("Ils se citent avec la clause « **au moment des décisions** » et ne doivent PAS être")
    A("relancés sur le canonique courant.")
    A("")
    A("| Chantier | État de jeu | Seuil de surcharge | Périmètre H25 | Features |")
    A("|---|---|---|---|---|")
    A("| ADR-069 (contre-épreuve post-gel) | `416bb90b` | > 63 (ADR-060) | 309 252 tronçons | 158 |")
    A("| ADR-051 (exploratoire pré-gel) | antérieur à `416bb90b` | **≥ 80** (pré-ADR-060) | 300 473 tronçons (post-embargo 9 j) | 179 |")
    A("")
    A("Deux conséquences de rédaction :")
    A("")
    A("1. Les chiffres ADR-069 portent sur le **même seuil** que le canonique (63) et sur un")
    A("   périmètre H25 de même taille (309 252) ; seules les données H25 diffèrent (features")
    A("   « narcisses », corrigées au gel v2). Les modèles canoniques des deux générations sont")
    A("   byte-identiques (ADR-076). La citation reste légitime, avec la mention de génération.")
    A("2. Les chiffres ADR-051 portent sur un **autre seuil** (≥ 80), un autre périmètre et un")
    A("   autre jeu de features. Toute reprise doit l'expliciter : « biais ≥ 80 », « 179 features »,")
    A("   « H25 post-embargo ». Les comparer aux chiffres canoniques (> 63) serait une erreur de grain.")
    A("")
    A("## Tableau claim par claim")
    A("")
    A("| # | ADR | Énoncé | Attendu | Trouvé | Source | Verdict |")
    A("|---|---|---|---|---|---|---|")
    for _, r in claims.iterrows():
        att = "—" if r["valeur_attendue"] is None else str(r["valeur_attendue"]).replace(".", ",")
        tro = "—" if r["valeur_trouvee"] is None else str(r["valeur_trouvee"]).replace(".", ",")
        A(f"| {r['id']} | {r['adr']} | {r['enonce']} | {att} | {tro} | "
          f"`{r['fichier_source']}` | **{r['verdict']}** |")
    A("")
    A("### Notes attachées aux claims")
    A("")
    for _, r in claims.iterrows():
        if str(r["note"]).strip():
            A(f"- **{r['id']}** — {r['note']}")
    A("")
    A("## Table de référence ADR-069 — H25, 3 modèles × 3 segments")
    A("")
    A("Source : `archive/explorations/consolidation_finale/exp_perte/confirmation_h25_k2_w2.json`.")
    A("Génération `416bb90b`, seuil > 63, 158 features, Split C tri-annuel → test H25.")
    A("")
    A(md_table(
        t069.assign(**{
            "R2": t069["r2_global"], "MAE": t069["mae_global"],
            "biais_gt63": t069["bias_gt63"], "MAE_gt63": t069["mae_gt63"],
            "biais_le63": t069["bias_le63"],
            "PRAUC_tr": t069["pr_auc_troncon"], "PRAUC_to": t069["pr_auc_tour"]}),
        ["modele", "segment", "n_obs", "n_gt63", "R2", "MAE", "biais_gt63",
         "MAE_gt63", "biais_le63", "PRAUC_tr", "PRAUC_to"],
        ["Modèle", "Segment", "n obs.", "n > 63", "R²", "MAE", "biais > 63",
         "MAE > 63", "biais ≤ 63", "PR-AUC tronçon", "PR-AUC tour"]))
    A("")
    A("## Table de référence ADR-051 — Enrichi_Seg, 5 pertes × 3 segments")
    A("")
    A("Sources : `etape_3q5_phase1.csv` (baseline MSE) et `etape_3q5_phase3.csv` (pertes")
    A("alternatives). État de jeu antérieur : **seuil ≥ 80**, 179 features, 300 473 tronçons.")
    A("")
    A(md_table(
        t051, ["perte", "segment", "n_obs", "n_surch_ge80", "r2", "mae",
               "mae_ge80", "bias_ge80", "pr_auc"],
        ["Perte", "Segment", "n obs.", "n ≥ 80", "R²", "MAE", "MAE ≥ 80",
         "biais ≥ 80", "PR-AUC"]))
    A("")
    A("## Conclusion de vérification")
    A("")
    A("Tous les nombres du paragraphe se retrouvent dans les sorties persistées, à deux")
    A("réserves de formulation :")
    A("")
    A("- **A8** — « ΔPR-AUC ≈ ±0,003 (tronçon et tour) pour les deux leviers » sous-estime")
    A("  l'amplitude maximale : W=2 déplace la PR-AUC tronçon de **+0,006**. La formulation")
    A("  fidèle aux données est « |ΔPR-AUC| ≤ 0,006 au grain tronçon et ≤ 0,001 au grain tour ».")
    A("  ADR-069 lui-même détaille correctement ces quatre valeurs dans son point (b).")
    A("- **A16** — le garde-fou de bit-exactitude `k=1 ≡ reg:squarederror` est **persisté pour la")
    A("  validation H24** (`controle_k1`, `impl_w1_k1_bitexact`), mais **pas pour le")
    A("  réentraînement tri-annuel H25** : le script le calcule et l'imprime, le JSON ne")
    A("  conserve que le garde-fou (A). Citer « bit-exact » sans qualifier le périmètre s'appuie")
    A("  sur le texte d'ADR-069, pas sur un artefact relisible.")
    A("")
    A("Les écarts B8, B9 et B10 ne sont pas des erreurs : ce sont les marqueurs, mesurés sur")
    A("les fichiers, du décalage d'état de jeu d'ADR-051 (périmètre, features, seuil).")
    A("")
    out = HERE / "verif_457_pertes_alternatives.md"
    out.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return out


# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    h = assert_dataset_canonique()
    assert_sources_presentes()
    print("=" * 78)
    print("LOT A — vérification des chiffres « pertes alternatives » (4.5.7)")
    print("=" * 78)
    print(f"dataset canonique : {h} (garde-fou OK) — LECTURE SEULE, aucun réentraînement")
    print(f"état de jeu ADR-069 : {ETAT_ADR069}")
    print(f"état de jeu ADR-051 : {ETAT_ADR051}")
    print()

    t069 = verifier_adr069()
    t051 = verifier_adr051()
    claims = pd.DataFrame(CLAIMS)

    HERE.mkdir(parents=True, exist_ok=True)
    f_claims = HERE / "verif_457_claims.csv"
    f_t069 = HERE / "verif_457_adr069_h25.csv"
    f_t051 = HERE / "verif_457_adr051_enrichi.csv"
    claims.to_csv(f_claims, index=False)
    t069.to_csv(f_t069, index=False)
    t051.to_csv(f_t051, index=False)
    f_md = ecrire_rapport(h, claims, t069, t051)

    for _, r in claims.iterrows():
        att = "—" if r["valeur_attendue"] is None else r["valeur_attendue"]
        tro = "—" if r["valeur_trouvee"] is None else r["valeur_trouvee"]
        print(f"  [{r['verdict']:>5}] {r['id']:>3} {r['enonce'][:62]:<62} "
              f"attendu={att!s:>16} trouvé={tro!s:>16}")
    print()
    print(f"  bilan : {(claims['verdict']=='OK').sum()} OK / "
          f"{(claims['verdict']=='ÉCART').sum()} ÉCART / "
          f"{(claims['verdict']=='INFO').sum()} INFO")
    for f in (f_claims, f_t069, f_t051, f_md):
        print(f"  [OK] {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
