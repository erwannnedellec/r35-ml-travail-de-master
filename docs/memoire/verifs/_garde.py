#!/usr/bin/env python3
"""
_garde.py — garde d'empreinte partagee par les verifications V1..V6.

Lecture seule stricte. Verifie et affiche l'empreinte SHA256[:8] du jeu canonique
`data/processed/ml_dataset.parquet` et s'arrete si elle differe de l'attendu.
Convention de hachage : ADR-066 (SHA256[:8] du parquet, pyarrow 21.0.0).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ML_DATASET = ROOT / "data" / "processed" / "ml_dataset.parquet"
HASH_ATTENDU = "ba493568"
# Generation figee de la couche decisionnelle citee par la commande de verification.
# NOTE : dans le depot, `416bb90b` designe le hash du dataset v1.9 (ADR-066), pas un
# artefact distinct de couche 2. Voir la synthese, section « Ambiguites signalees ».
HASH_GENERATION_PRECEDENTE = "416bb90b"


def sha8(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def garde(verbose: bool = True) -> str:
    if not ML_DATASET.exists():
        print(f"[ARRET] jeu canonique introuvable : {ML_DATASET}", file=sys.stderr)
        raise SystemExit(2)
    got = sha8(ML_DATASET)
    if verbose:
        print(f"[GARDE] {ML_DATASET.relative_to(ROOT)}")
        print(f"[GARDE] SHA256[:8] observe  = {got}")
        print(f"[GARDE] SHA256[:8] attendu  = {HASH_ATTENDU}")
    if got != HASH_ATTENDU:
        print(f"[ARRET] empreinte {got} != {HASH_ATTENDU} attendue — aucun calcul lance.",
              file=sys.stderr)
        raise SystemExit(1)
    if verbose:
        print("[GARDE] conforme — poursuite.\n")
    return got


def fr(n, dec: int = 0) -> str:
    """Nombre en convention francaise : virgule decimale, espace insecable milliers."""
    if n is None:
        return "n/d"
    s = f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


if __name__ == "__main__":
    garde()
