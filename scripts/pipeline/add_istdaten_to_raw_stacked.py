"""
add_istdaten_to_raw_stacked.py
================================
Joint les trois familles de features ISTDATEN/VMCV refondues sur stage_06 et
produit stage_07.

Familles jointes
----------------
1. Profil de ponctualité par tronçon × train  (12 features, grain tronçon × train × jour)
   Source : dim_profil_train.parquet
   Clés   : APC[base_date=J, horaire_numero_train, id_gare_depart_bpuic,
                 id_gare_arrivee_bpuic, base_sens]
              ← ISTDATEN[date=J-2, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens]

2. Correspondances Vevey CFF ↔ R35  (12 features, grain train × jour, propagées sur tronçons)
   Source : dim_correspondances_vevey.parquet
   Clés   : APC[base_date=J, horaire_numero_train] ← ISTDATEN[date=J-2, numero_train]
   Note : NaN pour les trains ne passant pas par Vevey dans le sens concerné.

3. Concurrence modale VMCV par train × jour × sens  (4 features, propagées sur tronçons)
   Source : dim_vmcv_par_train_jour.parquet
   Clés   : APC[base_date=J, horaire_numero_train, base_sens]
              ← VMCV[date=J-2, numero_train, sens]
   Note : ADR-021 — décision à l'embarquement. NaN pour les trains sans concurrence VMCV.

Logique J-2
-----------
Pour éviter tout leakage opérationnel, toutes les features sont décalées de
+2 jours avant jointure :
  APC[base_date=J] ← ISTDATEN[date=J-2]

Ablation
--------
L'argument --familles permet de sélectionner un sous-ensemble pour les tests
d'ablation (Chapitre 4 du mémoire) :

  python add_istdaten_to_raw_stacked.py --familles profil_train
  python add_istdaten_to_raw_stacked.py --familles correspondances
  python add_istdaten_to_raw_stacked.py --familles vmcv
  python add_istdaten_to_raw_stacked.py --familles toutes   (défaut)

Inputs
------
  data/processed/stage_06_statpop.parquet
  data/processed/sources/dim_profil_train.parquet
  data/processed/sources/dim_correspondances_vevey.parquet
  data/processed/sources/dim_vmcv_par_train_jour.parquet

Output
------
  data/processed/stage_07_istdaten.parquet
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.paths import (
    DIM_CORRESPONDANCES_VEVEY,
    DIM_PROFIL_TRAIN,
    DIM_VMCV_PAR_TRAIN_JOUR,
    STAGE_06B_STATENT,
    STAGE_07_ISTDATEN,
)
from pipeline.io import read_stage, write_stage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optimisation mémoire — stage_06b fait 4.6 GB en mémoire brute (8 GB RAM)
# ---------------------------------------------------------------------------


def _optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Downcast les dtypes pour réduire l'empreinte mémoire avant les merges.

    Gains attendus sur stage_06b (~4.6 GB → ~1.1 GB) :
      - string → category : colonnes à faible cardinalité (~2.2 GB économisés)
      - Float64 → Float32  : précision suffisante pour nos métriques (~350 MB)
      - float64 → float32  : idem (~245 MB)
      - Int64   → Int16/32 : selon amplitude de la colonne (~700 MB)
    """
    mb_before = df.memory_usage(deep=True).sum() / 1e6

    # string / object à faible cardinalité → category
    for col in df.select_dtypes(include=["object", "string"]).columns:
        if df[col].nunique() < 1000:
            df[col] = df[col].astype("category")

    # Float64 (nullable) → Float32
    for col in df.select_dtypes(include=["Float64"]).columns:
        df[col] = df[col].astype("Float32")

    # float64 (numpy) → float32
    for col in df.select_dtypes(include=["float64"]).columns:
        df[col] = df[col].astype("float32")

    # Int64 (nullable) → Int16 ou Int32 selon amplitude
    for col in df.select_dtypes(include=["Int64"]).columns:
        col_min = df[col].min(skipna=True)
        col_max = df[col].max(skipna=True)
        if pd.isna(col_min) or pd.isna(col_max):
            continue
        if int(col_min) >= -32768 and int(col_max) <= 32767:
            df[col] = df[col].astype("Int16")
        elif int(col_min) >= -2_147_483_648 and int(col_max) <= 2_147_483_647:
            df[col] = df[col].astype("Int32")

    mb_after = df.memory_usage(deep=True).sum() / 1e6
    log.info("  _optimize_dtypes : %.0f MB → %.0f MB (%.0f%%)", mb_before, mb_after,
             100 * (1 - mb_after / mb_before))
    return df


# ---------------------------------------------------------------------------
# Constantes ADR-040 — interruption de publication VMCV sur ISTDATEN H25
# ---------------------------------------------------------------------------

# Période d'interruption de publication VMCV sur ISTDATEN.
# Validée par diagnostic ingestion H25 (cf. rapport 04.06.2026, ADR-040).
# Pendant cette période, les jointures VMCV produisent naturellement des NaN.
# Les colonnes vmcv_source_* tracent cette interruption pour audit.
VMCV_INTERRUPTION_DEBUT = pd.Timestamp("2025-09-01")
VMCV_INTERRUPTION_FIN = pd.Timestamp("2025-10-13")  # inclus


# ---------------------------------------------------------------------------
# Jointure avec logique J-2 — grain train × jour (correspondances)
# ---------------------------------------------------------------------------


def _joindre_train_jour_j_moins_2(
    df_apc: pd.DataFrame,
    df_ist: pd.DataFrame,
    cle_train_ist: str = "numero_train",
    cle_train_apc: str = "horaire_numero_train",
) -> pd.DataFrame:
    """Joint une table ISTDATEN (date, numero_train) sur stage_06 avec logique J-2.

    Décale les dates ISTDATEN de +2 jours avant la jointure, de sorte que :
      APC[base_date=J, horaire_numero_train=T]
        ← ISTDATEN[date=J-2, numero_train=T]
    """
    df_join = df_ist.copy()
    df_join["base_date"] = pd.to_datetime(df_join["date"]) + pd.Timedelta(days=2)
    df_join = df_join.drop(columns=["date"]).rename(columns={cle_train_ist: cle_train_apc})
    return df_apc.merge(df_join, on=["base_date", cle_train_apc], how="left")


# ---------------------------------------------------------------------------
# Jointure avec logique J-2 — grain tronçon × train × jour (profil_train)
# ---------------------------------------------------------------------------


def _joindre_troncon_j_moins_2(
    df_apc: pd.DataFrame,
    profil_train: pd.DataFrame,
) -> pd.DataFrame:
    """Joint dim_profil_train (grain tronçon) sur stage_06 avec logique J-2.

    Clés de jointure :
      APC : base_date, horaire_numero_train, id_gare_depart_bpuic,
            id_gare_arrivee_bpuic, base_sens
      IST : date+2j, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens
    """
    df_join = profil_train.copy()
    df_join["base_date"] = pd.to_datetime(df_join["date"]) + pd.Timedelta(days=2)
    df_join = df_join.drop(columns=["date"]).rename(columns={
        "numero_train":       "horaire_numero_train",
        "gare_depart_bpuic":  "id_gare_depart_bpuic",
        "gare_arrivee_bpuic": "id_gare_arrivee_bpuic",
        "sens":               "base_sens",
    })

    cles = [
        "base_date", "horaire_numero_train",
        "id_gare_depart_bpuic", "id_gare_arrivee_bpuic", "base_sens",
    ]
    return df_apc.merge(df_join, on=cles, how="left")


# ---------------------------------------------------------------------------
# Jointure avec logique J-2 — grain train × jour × sens (VMCV ADR-021)
# ---------------------------------------------------------------------------


def _joindre_train_jour_sens_j_moins_2(
    df_apc: pd.DataFrame,
    df_vmcv: pd.DataFrame,
) -> pd.DataFrame:
    """Joint dim_vmcv_par_train_jour (grain date × train × sens) avec J-2.

    Chaque tronçon APC d'un train reçoit les mêmes 4 features VMCV (propagation).
    Clés :
      APC  : base_date, horaire_numero_train, base_sens
      VMCV : date+2j,   numero_train,         sens
    """
    df_join = df_vmcv.copy()
    df_join["base_date"] = pd.to_datetime(df_join["date"]) + pd.Timedelta(days=2)
    df_join = df_join.drop(columns=["date"]).rename(columns={
        "numero_train": "horaire_numero_train",
        "sens":         "base_sens",
    })
    return df_apc.merge(
        df_join,
        on=["base_date", "horaire_numero_train", "base_sens"],
        how="left",
    )


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Joint les features ISTDATEN refondues sur stage_06."
    )
    parser.add_argument(
        "--familles",
        nargs="+",
        choices=["profil_train", "correspondances", "vmcv", "toutes"],
        default=["toutes"],
        help="Familles ISTDATEN à intégrer (défaut : toutes).",
    )
    args = parser.parse_args()

    familles_actives: set[str]
    if "toutes" in args.familles:
        familles_actives = {"profil_train", "correspondances", "vmcv"}
    else:
        familles_actives = set(args.familles)

    log.info("Familles actives : %s", sorted(familles_actives))

    log.info("Lecture de %s ...", STAGE_06B_STATENT.name)
    df = read_stage(STAGE_06B_STATENT)
    log.info("  %d lignes × %d colonnes", df.shape[0], df.shape[1])
    log.info("Optimisation dtypes stage_06b (RAM limitée) ...")
    df = _optimize_dtypes(df)
    df["base_date"] = pd.to_datetime(df["base_date"])

    # --- Famille 1 : profil de ponctualité par tronçon (J-2, grain tronçon) ---
    if "profil_train" in familles_actives:
        log.info("Jointure profil de ponctualité par tronçon (J-2, grain tronçon) ...")
        profil_train = pd.read_parquet(DIM_PROFIL_TRAIN)
        profil_train = _optimize_dtypes(profil_train)
        log.info("  %d lignes (date × train × tronçon)", len(profil_train))

        n_avant = len(df)
        df = _joindre_troncon_j_moins_2(df, profil_train)
        if len(df) != n_avant:
            raise ValueError(
                f"La jointure profil_train a modifié le nombre de lignes : "
                f"{n_avant} → {len(df)}. Vérifier l'unicité du grain tronçon."
            )

        # Couverture : premier feature disponible
        col_ex = next(
            (c for c in profil_train.columns if c.startswith("ist_profil_train_")), None
        )
        if col_ex and col_ex in df.columns:
            n_couv = df[col_ex].notna().sum()
            log.info(
                "  Couverture %s : %d / %d (%.1f%%)",
                col_ex, n_couv, len(df), 100 * n_couv / len(df),
            )

    # --- Famille 2 : correspondances Vevey CFF ↔ R35 (J-2, grain train × jour) ---
    if "correspondances" in familles_actives:
        log.info("Jointure correspondances Vevey CFF ↔ R35 (J-2) ...")
        correspondances = pd.read_parquet(DIM_CORRESPONDANCES_VEVEY)
        log.info("  %d combinaisons (train, jour) avec correspondances", len(correspondances))

        df = _joindre_train_jour_j_moins_2(df, correspondances)

        # Couverture sens _in_ et _out_
        for sens in ("in", "out"):
            col_ex = f"ist_corresp_{sens}_n_theoriques_moy_5occ"
            if col_ex in df.columns:
                n_couv = df[col_ex].notna().sum()
                log.info(
                    "  Couverture corresp_%s : %d / %d (%.1f%%)",
                    sens, n_couv, len(df), 100 * n_couv / len(df),
                )

    # --- Famille 3 : concurrence modale VMCV par train × jour × sens (J-2, ADR-021) ---
    if "vmcv" in familles_actives:
        log.info("Jointure concurrence VMCV par train × jour × sens (J-2, ADR-021) ...")
        vmcv = pd.read_parquet(DIM_VMCV_PAR_TRAIN_JOUR)
        log.info("  %d combinaisons (date × train × sens)", len(vmcv))

        n_avant = len(df)
        df = _joindre_train_jour_sens_j_moins_2(df, vmcv)
        if len(df) != n_avant:
            raise ValueError(
                f"La jointure vmcv a modifié le nombre de lignes : "
                f"{n_avant} → {len(df)}. Vérifier l'unicité du grain train × jour × sens."
            )

        for col in ["vmcv_n_lignes_concurrentes", "vmcv_min_attente_min",
                    "vmcv_delta_attente_min", "vmcv_delta_frequence_h"]:
            if col in df.columns:
                n_couv = df[col].notna().sum()
                log.info(
                    "  Couverture %s : %d / %d (%.1f%%)",
                    col, n_couv, len(df), 100 * n_couv / len(df),
                )

        # Marqueurs de source VMCV (métadonnées de traçabilité, ADR-040).
        # À ajouter à COLS_EXCLUES du notebook de modélisation (Section 4.2 et Section 5).
        mask_interruption = (
            (df["base_date"] >= VMCV_INTERRUPTION_DEBUT)
            & (df["base_date"] <= VMCV_INTERRUPTION_FIN)
        )
        df["vmcv_source_depart"] = pd.Series("publie", index=df.index, dtype="string")
        df["vmcv_source_arrivee"] = pd.Series("publie", index=df.index, dtype="string")
        df.loc[mask_interruption, "vmcv_source_depart"] = "manquant_interruption_vmcv"
        df.loc[mask_interruption, "vmcv_source_arrivee"] = "manquant_interruption_vmcv"

    new_cols = [c for c in df.columns if c.startswith("ist_") or c.startswith("vmcv_")]
    log.info(
        "%d colonnes ISTDATEN+VMCV ajoutées | période %s → %s",
        len(new_cols),
        df["base_date"].min().date(),
        df["base_date"].max().date(),
    )

    # --- Vérification de cohérence interruption VMCV (ADR-040) ---
    if "vmcv_source_depart" in df.columns:
        log.info("=== Vérification cohérence interruption VMCV (ADR-040) ===")

        n_interruption = int((df["vmcv_source_depart"] == "manquant_interruption_vmcv").sum())
        n_publie = int((df["vmcv_source_depart"] == "publie").sum())

        if "horaire_annee_horaire" in df.columns:
            n_total_h25 = int((df["horaire_annee_horaire"] == "H25").sum())
            if n_total_h25 > 0:
                log.info(
                    "  VMCV interruption : %d lignes (%.1f%% du test H25)",
                    n_interruption, 100 * n_interruption / n_total_h25,
                )
            else:
                log.info("  VMCV interruption : %d lignes (H25 absent du DataFrame)", n_interruption)
        else:
            log.info("  VMCV interruption : %d lignes", n_interruption)

        # Vérifier une feature DYNAMIQUE (calendrier d'attente), pas la feature statique.
        # vmcv_n_lignes_concurrentes est statique (topologie, indépendante d'ISTDATEN) →
        # elle reste non-NaN même pendant l'interruption, ce qui n'est pas une anomalie.
        # vmcv_min_attente_min est dynamique (horaires VMCV ISTDATEN) → doit être NaN
        # pendant les 43 jours d'interruption (cf. ADR-040, ADR-021 D3).
        if "vmcv_min_attente_min" in df.columns:
            mask_interr = df["vmcv_source_depart"] == "manquant_interruption_vmcv"
            nan_interr = int(df.loc[mask_interr, "vmcv_min_attente_min"].isna().sum())
            n_interr = int(mask_interr.sum())
            status = "OK" if nan_interr == n_interr else "ANOMALIE"
            log.info(
                "  NaN vmcv_min_attente_min sur interruption : %d/%d [%s]",
                nan_interr, n_interr, status,
            )

        log.info("  Lignes vmcv_source='publie' : %d", n_publie)
        log.info("  Lignes vmcv_source='manquant_interruption_vmcv' : %d", n_interruption)
        total_source = n_publie + n_interruption
        attendu = len(df)
        log.info("  Total : %d (attendu = %d) [%s]",
                 total_source, attendu, "OK" if total_source == attendu else "ANOMALIE")

    # Restaurer category → string avant sérialisation parquet.
    # Les économies mémoire de _optimize_dtypes ne sont utiles que pendant les merges.
    # Si on écrit les category telles quelles, PyArrow les relit comme category downstream
    # et les comparaisons >= / <= sur horaire_annee_horaire, base_sens, etc. échouent.
    cat_cols = df.select_dtypes(include=["category"]).columns.tolist()
    if cat_cols:
        log.info("Restauration category → string pour %d colonnes avant écriture", len(cat_cols))
        for col in cat_cols:
            df[col] = df[col].astype("string")

    write_stage(df, STAGE_07_ISTDATEN)


if __name__ == "__main__":
    main()
