"""
Contrat de l'imputation STATPOP causale (ADR-076).

Remplace `test_statpop_frozen_input_stability.py` (retire). Ce dernier protegeait
un INVARIANT : la stabilite de l'entree STATPOP consommee, quand statpop_clean_causal
etait une ENTREE FIGEE rematerialisee depuis le gele. La branche STATPOP etant
desormais REFABRIQUEE depuis les bruts par le forward-fill causal (ADR-076), ce
n'est pas le test qui doit survivre mais l'invariant, reformule pour la nouvelle
chaine. Trois verrous du nouveau contrat :

  (a) l'imputation est CAUSALE : aucune valeur imputee ne depend d'un millesime
      futur (cas synthetique a trois millesimes) ;
  (b) les valeurs d'ancrage d'ADR-075 (CHBL/HTV/STLE : 2021=1, 2023=2) sont
      reproduites par le forward-fill integral, la ou l'ancienne imputation
      non-causale (interpolate + max-des-voisins) divergeait ;
  (c) VVVI est reconstruite via la topologie H23 pour 2020/2021/2022 ; VVVI-2019
      est volontairement exclu du producteur (ligne inerte ajoutee au consommateur,
      jamais mobilisee par la jointure Z-2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "sources"))

import build_fact_statpop_gare as B  # noqa: E402


# --- (a) Invariant causal : l'imputation ne regarde jamais le futur -----------
def test_imputation_causale_ne_depend_pas_du_futur():
    # 2021 est en trou entre 2020 et 2022. Le forward-fill doit reporter 2020
    # (passe), jamais 2022 (futur). Une interpolation donnerait la moyenne (150),
    # un backward-fill donnerait 2022 : les deux echoueraient ce test.
    fact = pd.DataFrame(
        {
            "annee_enquete_statpop": [2020, 2021, 2022],
            "gare_abreviation": ["AAA", "AAA", "AAA"],
            "menages_500m_total": [100.0, float("nan"), 200.0],
            "hpi_classe_max_500m": [1.0, float("nan"), 2.0],
        }
    )
    out = B.impute_forward_fill_causal(fact)
    v = out.loc[out["annee_enquete_statpop"] == 2021].iloc[0]
    assert v["menages_500m_total"] == 100.0  # 2020 (passe), pas 200 (futur) ni 150 (moyenne)
    assert v["hpi_classe_max_500m"] == 1.0   # 2020 (passe), pas 2 (futur/max)


# --- (b) Valeurs d'ancrage ADR-075 reproduites -------------------------------
def test_valeurs_ancrage_adr075_hpi_classe_max():
    # Ancrages ADR-075 (CHBL/HTV/STLE) : 2020=1, 2022=2, 2024=1 ; 2021 et 2023 en trou.
    # Forward-fill causal : 2021<-2020=1, 2023<-2022=2. Le max-des-voisins d'epoque
    # aurait donne 2021=max(1,2)=2 (divergent du canonique).
    rows = []
    for g in ["CHBL", "HTV", "STLE"]:
        rows += [
            {"annee_enquete_statpop": 2020, "gare_abreviation": g, "hpi_classe_max_500m": 1.0},
            {"annee_enquete_statpop": 2021, "gare_abreviation": g, "hpi_classe_max_500m": float("nan")},
            {"annee_enquete_statpop": 2022, "gare_abreviation": g, "hpi_classe_max_500m": 2.0},
            {"annee_enquete_statpop": 2023, "gare_abreviation": g, "hpi_classe_max_500m": float("nan")},
            {"annee_enquete_statpop": 2024, "gare_abreviation": g, "hpi_classe_max_500m": 1.0},
        ]
    out = B.impute_forward_fill_causal(pd.DataFrame(rows)).set_index(
        ["annee_enquete_statpop", "gare_abreviation"]
    )
    for g in ["CHBL", "HTV", "STLE"]:
        assert out.loc[(2021, g), "hpi_classe_max_500m"] == 1.0
        assert out.loc[(2023, g), "hpi_classe_max_500m"] == 2.0


# --- (c) VVVI : perimetre de reconstruction (2020-2022), VVVI-2019 exclu ------
def test_vvvi_fix_years_reproduisent_le_bocal():
    # Le producteur reconstruit VVVI pour 2020/2021/2022 (topologie H23) et NON
    # 2019 : la ligne inerte VVVI-2019 est ajoutee au consommateur (_patch_vvvi_statpop),
    # jamais mobilisee par la jointure Z-2. Reproduit le perimetre du bocal 40ae0fe0.
    assert B.VVVI_FIX_YEARS == [2020, 2021, 2022]
    assert 2019 not in B.VVVI_FIX_YEARS
    assert B.KEEP_MILLESIMES == [2019, 2020, 2021, 2022, 2023]
