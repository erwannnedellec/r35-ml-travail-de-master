"""Test de la garde de provenance de la table STATPOP (ADR-063, ADR-076).

Correctif pre-publication, ADR-078 section 5.2. La garde d'epoque ne pouvait pas se
declencher : elle testait une etiquette derivee d'une constante du module consommateur,
et jamais la table lue. Ce test etablit que la garde actuelle, elle, distingue bien les
deux recettes d'imputation.

Trois cas :
  - une table CAUSALE (report du millesime precedent, LOCF) passe la garde ;
  - une table INTERPOLEE (moyenne des millesimes adjacents) la fait echouer — c'est le
    test negatif explicite : substituer statpop_clean.parquet a
    statpop_clean_causal.parquet doit interrompre le pipeline ;
  - une table causale ou la seule gare reconstruite (VVVI) porte des valeurs propres
    passe la garde, cette gare etant hors du test d'egalite par construction.

Executable seul (`python3 tests/test_statpop_provenance_causale.py`) ou via pytest.
"""

from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pipeline.add_statpop_to_raw_stacked_annee_horaire_meteo_vev import (  # noqa: E402
    STATPOP_COLONNES_IMPUTEES,
    assert_statpop_provenance_causale,
)

GARES = ["VV", "BLON", "PLEI", "STLE", "CHBL", "HTV"]
MILLESIMES = [2020, 2021, 2022, 2023]


def _socle() -> dict:
    """Valeurs publiees (millesimes 2020 et 2022), arbitraires mais distinctes."""
    socle = {}
    for i, gare in enumerate(GARES):
        for j, annee in enumerate((2020, 2022)):
            socle[(gare, annee)] = {
                col: 100.0 + 10 * i + 37 * j + 3 * k
                for k, col in enumerate(STATPOP_COLONNES_IMPUTEES)
            }
    return socle


def _table(mode: str, vvvi_propre: bool = False) -> pd.DataFrame:
    """Construit une table STATPOP synthetique.

    mode='causal'    : 2021 <- 2020 et 2023 <- 2022 (report exact, LOCF).
    mode='interpole' : 2021 = moyenne(2020, 2022), 2023 = 2022 majore (recette d'epoque).
    """
    socle = _socle()
    lignes = []
    gares = GARES + (["VVVI"] if vvvi_propre else [])
    for gare in gares:
        base_2020 = socle.get((gare, 2020)) or {c: 500.0 for c in STATPOP_COLONNES_IMPUTEES}
        base_2022 = socle.get((gare, 2022)) or {c: 900.0 for c in STATPOP_COLONNES_IMPUTEES}
        for annee in MILLESIMES:
            if annee == 2020:
                vals = dict(base_2020)
            elif annee == 2022:
                vals = dict(base_2022)
            elif annee == 2021:
                if gare == "VVVI" and vvvi_propre:
                    vals = {c: base_2020[c] + 41.0 for c in STATPOP_COLONNES_IMPUTEES}
                elif mode == "causal":
                    vals = dict(base_2020)
                else:
                    vals = {c: (base_2020[c] + base_2022[c]) / 2.0 for c in STATPOP_COLONNES_IMPUTEES}
            else:  # 2023
                if mode == "causal":
                    vals = dict(base_2022)
                else:
                    vals = {c: base_2022[c] * 1.05 for c in STATPOP_COLONNES_IMPUTEES}
            lignes.append({"annee_enquete_statpop": annee, "gare_abreviation": gare, **vals})
    return pd.DataFrame(lignes)


def test_table_causale_passe_la_garde():
    comptes = assert_statpop_provenance_causale(_table("causal"))
    assert comptes["ecarts"] == 0
    assert comptes["total"] == len(GARES) * len(STATPOP_COLONNES_IMPUTEES) * 2


def test_table_interpolee_fait_echouer_la_garde():
    """Test negatif : la mauvaise source doit interrompre le pipeline."""
    with pytest.raises(RuntimeError) as err:
        assert_statpop_provenance_causale(_table("interpole"), chemin="statpop_clean.parquet")
    message = str(err.value)
    assert "PROVENANCE STATPOP ECHOUEE" in message
    assert "statpop_clean_causal.parquet" in message
    assert "signature de la recette" in message


def test_gare_reconstruite_exclue_du_test():
    """VVVI porte des valeurs propres en 2021 sans faire echouer la garde."""
    comptes = assert_statpop_provenance_causale(_table("causal", vvvi_propre=True))
    assert comptes["ecarts"] == 0


def test_millesime_source_absent_est_signale():
    table = _table("causal")
    with pytest.raises(RuntimeError, match="millesime source 2020 est absent"):
        assert_statpop_provenance_causale(table[table["annee_enquete_statpop"] != 2020])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
