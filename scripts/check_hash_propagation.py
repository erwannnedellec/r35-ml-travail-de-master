#!/usr/bin/env python3
"""
check_hash_propagation.py - garde permanente de propagation du hash canonique (ADR-076).

Transforme l'inventaire 0b (photographie ponctuelle) en MECANISME (garde permanente),
sur le modele de scripts/pipeline/coverage_guard.py. LECTURE SEULE stricte : ne modifie
aucun fichier. Sert aussi de GARDE DE SORTIE du chantier notebooks differe.

Deux regles :
  A (negative) : aucun hash perime dans le PERIMETRE ACTIF, hors allowlist historique.
  B (positive) : le hash canonique CANONICAL_HASH est present la ou il doit l'etre.

PENDING : les notebooks canoniques (03c, 02 APC, 08 v2, rapport_synthese) sont attendus
en echec de la regle B jusqu'au chantier notebooks differe. Ils sont signales PENDING,
pas FAIL. Quand DEFERRED_UNTIL_NOTEBOOKS sera vide, ils passeront en bloquant (regles A et B).

Sortie : PASS/FAIL par regle, violations listees, section PENDING a part.
Code retour : non-zero si FAIL ; PENDING seul = 0 (avec avertissement).
Cible Makefile : make check-propagation, dans le DEPOT DE TRAVAIL (distincte de
check-sources). Le present depot publie l'artefact seul : les notebooks, sorties et
figures dont la regle B exige la presence n'y figurent pas, la cible n'y est donc pas
exposee. Le script est conserve comme piece du registre (ADR-066, ADR-076).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# =============================== Parametres ===============================
CANONICAL_HASH = "ba493568"          # gel v2 (ADR-076)
STALE_HASHES = [                     # generations anterieures supersedees
    "416bb90b",   # v1.9 (generation precedente immediate)
    "51e459ff",   # v1.8
    "d39d0bd8",   # v1.7
    "5fdca746",   # v1.6
    "c1ecfc19",   # v1.4
    "daf936c8",   # seuil 63 (pre-v1.6, MD5)
]
STALE_RE = re.compile("|".join(re.escape(h) for h in STALE_HASHES))

# --- Perimetre ACTIF (regle A) : ou un hash perime = fuite de propagation ---
ACTIVE_FILES = [
    "Makefile", "README.md", "data/README.md", "CONTEXT.md",
    "docs/glossaire.md", "docs/gabarit_notebooks.md", "docs/architecture.md",
    "models/enrichi_seg/enrichi_seg_metadata.json",
    f"outputs/codebook_canonique_{CANONICAL_HASH}.csv",
]
ACTIVE_DIRS = ["src", "tests", "scripts"]   # scripts hors EXCLUDED_SUBTREES
SCAN_SUFFIXES = {".py", ".sh", ".md", ".json", ".csv", ".ipynb", ".cfg", ".ini", ".toml"}
EXCLUDED_SUBTREES = ("scripts/archive/", "scripts/experiences/")

# --- Allowlist regle A : hash perime LEGITIME (histoire), chaque entree justifiee ---
ALLOWLIST_PREFIXES = {
    "archive/": "traces historiques de la demarche iterative (doctrine d'exhibit)",
    "scripts/archive/": "chaine manuelle STATPOP retiree, exhibit (ADR-076 decision 6)",
    "scripts/experiences/": "pieces archeologiques (rebuild_statpop_origine cite le hash d'epoque par fonction)",
    "scripts/confirmation/": "suite de confirmation post-gel : 416bb90b cite comme generation de comparaison "
                             "(invariance inter-generations ; c06/c07 reproduisent e4ddfccd/df6a11c5)",
    "docs/adr/": "les ADR portent l'histoire (notes de generation, ADR-075/076, INDEX, ALL_ADRS)",
    "docs/rapports/": "rapports dates d'epoque (archeologie, check narcisses, prep cout, rapport de cloture)",
    "scripts/check_hash_propagation.py": "la garde elle-meme definit les hashes perimes qu'elle surveille",
}
# Fichiers du perimetre actif ou un nombre BORNE de hash perimes est legitime (genealogie).
# La valeur = nombre d'occurrences STALE attendues ; toute DERIVE (!=) est FAIL (nouvelle
# occurrence non historique, ou disparition d'un fait d'histoire a re-verifier).
ALLOWLIST_HISTORY_COUNTS = {
    "CONTEXT.md": 56,   # genealogie des versions + gouvernance ADR-066 (faits d'histoire ;
                        #                     comptage en OCCURRENCES, la ligne genealogie en porte 6)
    "docs/architecture.md": 1,   # ligne "416bb90b (v1.9) reste la trace historique"
    "README.md": 1,     # "416bb90b (v1.9) reste la trace historique"
    "models/enrichi_seg/enrichi_seg_metadata.json": 1,  # supersedes v1.9 (genealogie)
}

# --- Regle B (positive) : le hash canonique doit etre present / les fichiers exister ---
REQUIRE_HASH_IN = [
    "src/couche2/decision.py", "src/couche2/blocs.py",
    "models/enrichi_seg/enrichi_seg_metadata.json", "README.md", "CONTEXT.md",
]
REQUIRE_FILE_EXISTS = [
    f"outputs/codebook_canonique_{CANONICAL_HASH}.csv",
    f"models/enrichi_seg/enrichi_seg_bas_{CANONICAL_HASH}.json",
    f"models/enrichi_seg/enrichi_seg_haut_{CANONICAL_HASH}.json",
    f"outputs/couche2/q_couche2_eval_{CANONICAL_HASH}.json",
]
# --- PENDING : hash canonique attendu ici, DIFFERE au chantier notebooks ---
# A VIDER au chantier notebooks : quand cette liste sera vide, ces fichiers passeront
# en bloquant (regle A : scannes ; regle B : requis). Tant qu'ils y figurent, ils sont
# signales PENDING (pas FAIL) et exemptes de la regle A.
DEFERRED_UNTIL_NOTEBOOKS = [
    "notebooks/03c_du_ml_dataset_canonique.ipynb",
    "notebooks/02_data_understanding_apc_canonique.ipynb",
    "notebooks/08_evaluation_consolidee_h25_v2.ipynb",
    "docs/rapports/rapport_synthese_couche1.ipynb",
]

# --- Sources FIGEES non canoniques (regle C) : empreinte REQUISE la ou documentee ---
# Distinctes des STALE_HASHES : ces empreintes ne sont PAS perimees. Ce sont des
# intermediaires figes en entree d'un livrable ; leur presence est EXIGEE (pas
# proscrite). Chaque entree est enregistree par un addendum ADR date.
FROZEN_SOURCES = {
    "954135f9": {
        "fichier": "data/processed/stage_09_simba.parquet",
        "role": "source figee des figures de stationnarite H16-H25 (section 4.5.1)",
        "adr": "ADR-066 (addendum 2026-07-12)",
        "present_dans": [
            "docs/adr/ADR-066_gouvernance_empreintes_hash_dataset.md",
            "docs/memoire/figures/section_4_5_1/make_fig_4_5_1.py",
        ],
    },
}


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def allowlisted_prefix(r: str):
    for pref, why in ALLOWLIST_PREFIXES.items():
        if r.startswith(pref):
            return why
    return None


def gather_active_files() -> dict:
    """Fichiers du perimetre actif a scanner (regle A). Inclut les notebooks differes
    (scannes des que retires de DEFERRED_UNTIL_NOTEBOOKS)."""
    seen: dict[str, Path] = {}
    for f in ACTIVE_FILES + DEFERRED_UNTIL_NOTEBOOKS:
        p = ROOT / f
        if p.is_file():
            seen[rel(p)] = p
    for d in ACTIVE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            r = rel(p)
            if any(r.startswith(e) for e in EXCLUDED_SUBTREES):
                continue
            if p.suffix.lower() in SCAN_SUFFIXES:
                seen[r] = p
    return seen


def stale_hits(p: Path) -> list:
    try:
        lines = p.read_text(errors="replace").splitlines()
    except Exception:
        return []
    return [(i, m.group(0), ln.strip()[:90])
            for i, ln in enumerate(lines, 1) for m in STALE_RE.finditer(ln)]


def rule_A():
    fails, history = [], {}
    for r, p in sorted(gather_active_files().items()):
        if r in DEFERRED_UNTIL_NOTEBOOKS:            # exempt jusqu'au chantier notebooks
            continue
        hits = stale_hits(p)
        if not hits:
            continue
        if allowlisted_prefix(r):                    # dossier historique
            continue
        if r in ALLOWLIST_HISTORY_COUNTS:            # genealogie bornee : detecter la derive
            exp = ALLOWLIST_HISTORY_COUNTS[r]
            history[r] = (len(hits), exp)
            if len(hits) != exp:
                fails.append((r, None, f"DERIVE genealogie : {len(hits)} occurrences, {exp} attendues"))
            continue
        for i, h, ln in hits:                        # sinon : fuite de propagation
            fails.append((r, i, f"{h} : {ln}"))
    return fails, history


def rule_B():
    fails, pending = [], []
    for f in REQUIRE_HASH_IN:
        p = ROOT / f
        if not (p.is_file() and CANONICAL_HASH in p.read_text(errors="replace")):
            fails.append((f, "hash canonique absent"))
    for f in REQUIRE_FILE_EXISTS:
        if not (ROOT / f).is_file():
            fails.append((f, "fichier attendu absent"))
    for f in DEFERRED_UNTIL_NOTEBOOKS:
        p = ROOT / f
        if not (p.is_file() and CANONICAL_HASH in p.read_text(errors="replace")):
            pending.append(f)
    return fails, pending


def rule_C():
    """Regle C (positive) : chaque source figee est presente la ou elle est documentee."""
    fails, ok = [], {}
    for h, meta in FROZEN_SOURCES.items():
        for f in meta["present_dans"]:
            p = ROOT / f
            present = p.is_file() and h in p.read_text(errors="replace")
            ok[(h, f)] = present
            if not present:
                fails.append((h, f, "empreinte de source figee absente"))
    return fails, ok


def main() -> int:
    print("=" * 72)
    print(f"check_hash_propagation - canonique = {CANONICAL_HASH}")
    print(f"  hashes perimes surveilles : {', '.join(STALE_HASHES)}")
    print("=" * 72)

    a_fails, history = rule_A()
    b_fails, pending = rule_B()
    c_fails, c_ok = rule_C()

    print("\n[Regle A] aucun hash perime dans le perimetre actif (hors allowlist)")
    for r, (n, e) in sorted(history.items()):
        flag = "OK" if n == e else "DERIVE"
        print(f"  allowlist histoire [{flag}] : {r}  ({n}/{e} occurrences)")
    if a_fails:
        print(f"  FAIL ({len(a_fails)} fuite(s)) :")
        for r, i, msg in a_fails:
            print(f"    {r}{(':' + str(i)) if i else ''}  {msg}")
    else:
        print("  PASS")

    print("\n[Regle B] hash canonique present la ou il doit l'etre")
    if b_fails:
        print(f"  FAIL ({len(b_fails)}) :")
        for f, msg in b_fails:
            print(f"    {f}  {msg}")
    else:
        print("  PASS")

    print("\n[Regle C] empreintes de sources figees presentes la ou documentees")
    for (h, f), present in sorted(c_ok.items()):
        print(f"  [{'OK' if present else 'FAIL'}] {h}  {f}")
    if c_fails:
        print(f"  FAIL ({len(c_fails)}) :")
        for h, f, msg in c_fails:
            print(f"    {h}  {f}  {msg}")
    else:
        print("  PASS")

    if pending:
        print(f"\n[PENDING] {len(pending)} attendus au chantier notebooks (non bloquant, a vider alors) :")
        for f in pending:
            print(f"    {f}")

    n_fail = len(a_fails) + len(b_fails) + len(c_fails)
    print("\n" + "=" * 72)
    verdict = "ECHEC" if n_fail else ("OK (avec PENDING notebooks)" if pending else "OK")
    print(f"RESULTAT : {verdict} - {n_fail} FAIL, {len(pending)} PENDING notebooks")
    print("=" * 72)
    if n_fail:
        print("Toute FAIL est une fuite de propagation a corriger seance tenante.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
