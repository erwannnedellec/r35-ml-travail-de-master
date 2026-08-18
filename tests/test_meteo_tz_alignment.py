"""
Tests d'alignement fuseau horaire pour la jointure météo R35 ↔ MétéoSuisse.

Valide que la conversion Europe/Zurich → UTC produit les bons timestamps de
jointure. Exécution directe sans framework de test :

    python3 scripts/tests/test_meteo_tz_alignment.py

Trois cas obligatoires (cf. ADR-022, specs refonte météo 2026-05) :
  1. Hiver (UTC+1)   : 15 jan 2023 08h00 local → MétéoSuisse 07:00 UTC
  2. Été   (UTC+2)   : 15 jul 2023 08h00 local → MétéoSuisse 06:00 UTC
  3. Transition      : 26 mar 2023 (dernier dim. mars, passage heure été)
                       → pas d'exception, pas de double match, pas d'absence

Utilise la fonction build_join_key_utc de add_meteo_to_raw_stacked.py pour
tester le code réel, pas une ré-implémentation parallèle.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.pipeline.add_meteo_to_raw_stacked import build_join_key_utc  # noqa: E402


def _make_row(date_str: str, hour: int, minute: int = 0) -> pd.DataFrame:
    """Construit un DataFrame d'une ligne avec base_depart_datetime."""
    dt = pd.Timestamp(f"{date_str} {hour:02d}:{minute:02d}:00")
    return pd.DataFrame({"base_depart_datetime": [dt]})


def test_hiver_utc_plus_1() -> None:
    """15 janvier 2023 08h00 Europe/Zurich (UTC+1) → clé de jointure 07:00 UTC."""
    df = _make_row("2023-01-15", 8)
    key = build_join_key_utc(df).iloc[0]
    expected = pd.Timestamp("2023-01-15 07:00:00")
    assert key == expected, (
        f"CAS 1 ÉCHEC : attendu {expected}, obtenu {key}\n"
        "En hiver (UTC+1), 08h00 local doit correspondre à 07h00 UTC."
    )
    print(f"  CAS 1 OK — hiver : 08h00 CET → {key} UTC")


def test_ete_utc_plus_2() -> None:
    """15 juillet 2023 08h00 Europe/Zurich (UTC+2) → clé de jointure 06:00 UTC."""
    df = _make_row("2023-07-15", 8)
    key = build_join_key_utc(df).iloc[0]
    expected = pd.Timestamp("2023-07-15 06:00:00")
    assert key == expected, (
        f"CAS 2 ÉCHEC : attendu {expected}, obtenu {key}\n"
        "En été (UTC+2), 08h00 local doit correspondre à 06h00 UTC."
    )
    print(f"  CAS 2 OK — été  : 08h00 CEST → {key} UTC")


def test_transition_passage_heure_ete() -> None:
    """
    26 mars 2023 (dernier dimanche de mars, passage heure été).
    Le passage se fait à 02h00 local : l'heure 02:00:00 n'existe pas,
    les horloges sautent directement à 03:00:00 (CEST, UTC+2).

    Attend :
    - Aucune exception levée (nonexistent='shift_forward')
    - Un seul enregistrement en sortie (pas de duplication)
    - La clé de jointure est non-NaT (pas d'absence silencieuse)
    - 01h30 local (CET) → 00h30 UTC → clé 00:00 UTC (floor h)
    - 03h30 local (CEST, après transition) → 01h30 UTC → clé 01:00 UTC
    """
    # Avant la transition : 01h30 CET = UTC+1
    df_avant = _make_row("2023-03-26", 1, 30)
    key_avant = build_join_key_utc(df_avant).iloc[0]
    assert pd.notna(key_avant), "CAS 3a ÉCHEC : clé NaT avant la transition"
    expected_avant = pd.Timestamp("2023-03-26 00:00:00")
    assert key_avant == expected_avant, (
        f"CAS 3a ÉCHEC : attendu {expected_avant}, obtenu {key_avant}"
    )
    print(f"  CAS 3a OK — avant transition : 01h30 CET → {key_avant} UTC")

    # Après la transition : 03h30 CEST = UTC+2
    df_apres = _make_row("2023-03-26", 3, 30)
    key_apres = build_join_key_utc(df_apres).iloc[0]
    assert pd.notna(key_apres), "CAS 3b ÉCHEC : clé NaT après la transition"
    expected_apres = pd.Timestamp("2023-03-26 01:00:00")
    assert key_apres == expected_apres, (
        f"CAS 3b ÉCHEC : attendu {expected_apres}, obtenu {key_apres}"
    )
    print(f"  CAS 3b OK — après transition : 03h30 CEST → {key_apres} UTC")

    # Heure inexistante : 02h00 (nonexistent='shift_forward' → devient 03h00 CEST)
    df_inexistant = _make_row("2023-03-26", 2, 0)
    try:
        key_inexistant = build_join_key_utc(df_inexistant).iloc[0]
        assert pd.notna(key_inexistant), (
            "CAS 3c ÉCHEC : clé NaT pour heure inexistante — shift_forward non appliqué"
        )
        # 02h00 inexistante → shift → 03h00 CEST (UTC+2) → 01h00 UTC → floor → 01:00
        expected_inexistant = pd.Timestamp("2023-03-26 01:00:00")
        assert key_inexistant == expected_inexistant, (
            f"CAS 3c ÉCHEC : attendu {expected_inexistant}, obtenu {key_inexistant}"
        )
        print(f"  CAS 3c OK — inexistante : 02h00 → shift → {key_inexistant} UTC")
    except Exception as exc:  # noqa: BLE001
        print(f"  CAS 3c ÉCHEC : exception levée pour heure inexistante : {exc}")
        raise


def main() -> None:
    print("\nTests d'alignement fuseau horaire R35 ↔ MétéoSuisse UTC\n")
    tests = [
        ("CAS 1 — hiver UTC+1",          test_hiver_utc_plus_1),
        ("CAS 2 — été UTC+2",            test_ete_utc_plus_2),
        ("CAS 3 — transition heure été", test_transition_passage_heure_ete),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as exc:
            print(f"\n  ÉCHEC {name} : {exc}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"  {passed} test(s) réussi(s), {failed} échec(s)")
    if failed:
        sys.exit(1)
    print("  Alignement fuseau horaire : OK")


if __name__ == "__main__":
    main()
