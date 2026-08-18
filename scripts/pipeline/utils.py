"""
Utilitaires partagés entre les scripts de la pipeline R35.
"""

from __future__ import annotations

import pandas as pd


def non_missing_mask(values: pd.Series) -> pd.Series:
    """Retourne True pour les valeurs non-nulles et non-vides après strip."""
    strings = values.astype("string").str.strip()
    return strings.notna() & strings.ne("")
