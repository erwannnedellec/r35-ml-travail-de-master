"""
Helpers d'entrée/sortie partagés entre les scripts de la pipeline R35.

Problème résolu
---------------
Chaque script d'enrichissement répétait le même bloc de 15 lignes pour :
    1. lire un parquet (avec fallback CSV si le parquet est absent) ;
    2. écrire un parquet de façon atomique (fichier temporaire + rename)
       pour éviter qu'un stage partiel soit lisible par l'étape suivante.

Ce module centralise ces deux opérations.

Conventions
-----------
- Le parquet est la forme canonique de chaque stage.
- Le CSV est optionnel : activer via la variable d'environnement ``WRITE_CSV=1``.
  Il n'est jamais écrit par défaut car les stages sont volumineux.
- L'écriture atomique garantit qu'un stage est soit complet, soit absent ;
  jamais partiellement écrit.

Usage
-----
    from pipeline.io import read_stage, write_stage

    df = read_stage(STAGE_02_CALENDRIER)
    # ... enrichissement ...
    write_stage(enriched, STAGE_04_METEO_VEV)
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Résolution de la variable d'environnement WRITE_CSV
# ---------------------------------------------------------------------------

def _env_write_csv() -> bool:
    return os.environ.get("WRITE_CSV", "").strip().lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def read_stage(parquet_path: Path, csv_path: Path | None = None) -> pd.DataFrame:
    """Lit un stage pipeline : parquet préféré, CSV en fallback.

    Parameters
    ----------
    parquet_path:
        Chemin du fichier parquet attendu.
    csv_path:
        Chemin CSV de repli, utilisé uniquement si le parquet est absent.
        Si ``None``, aucun fallback n'est tenté.

    Returns
    -------
    pd.DataFrame
        Contenu du stage.

    Raises
    ------
    FileNotFoundError
        Si ni le parquet ni le CSV ne sont présents.
    """
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)

    if csv_path is not None and csv_path.exists():
        return pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)

    fallback = f" ou {csv_path}" if csv_path else ""
    raise FileNotFoundError(
        f"Stage introuvable : {parquet_path}{fallback}\n"
        "Vérifier que l'étape précédente a bien été exécutée "
        "(voir le Makefile ou pipeline/paths.py)."
    )


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def write_stage(
    df: pd.DataFrame,
    parquet_path: Path,
    *,
    write_csv: bool | None = None,
) -> None:
    """Écrit un stage pipeline de façon atomique.

    L'écriture parquet passe par un fichier temporaire (``.tmp.parquet``)
    puis un ``rename`` atomique, ce qui garantit qu'un stage partiel n'est
    jamais lisible par l'étape suivante en cas d'interruption.

    Parameters
    ----------
    df:
        DataFrame à persister.
    parquet_path:
        Chemin cible du parquet. Le répertoire parent est créé si nécessaire.
    write_csv:
        Si ``True``, écrit aussi un CSV (encodage ``utf-8-sig``) à côté du
        parquet. Si ``None`` (défaut), hérite de la variable d'environnement
        ``WRITE_CSV``.
    """
    if write_csv is None:
        write_csv = _env_write_csv()

    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = parquet_path.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False)
        tmp.rename(parquet_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    print(f"  parquet : {parquet_path}  ({len(df):,} lignes, {df.shape[1]} colonnes)")

    if write_csv:
        csv_path = parquet_path.with_suffix(".csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  csv     : {csv_path}")
