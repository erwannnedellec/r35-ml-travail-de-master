"""
Constantes métier du projet R35 ML.

Ce module est la source de vérité pour toutes les constantes liées au matériel
roulant, aux seuils opérationnels et aux décisions documentées dans les ADR.

Ne pas définir ces valeurs directement dans les notebooks ou scripts :
importer depuis ce module pour garantir la cohérence du projet.

Références ADR :
    ADR-005_seuil_um_94_2c.md   — définition seuil UM couche 2 (mis à jour ADR-060)
    ADR-060                    — correction seuil 94 → 63 (spec MOB ABeh 7501-7508)
    ADR-001_cible_2eme_classe.md — cible ML et rôle de target_voyageurs_total
"""

# ---------------------------------------------------------------------------
# Capacités SURF 7500 (rame simple) — Source : spec MOB ABeh 7501-7508
# Schéma véhicule (vehicules_portes_7500.png) + validation Responsable des Actifs Voyageurs, MOB
# (Responsable des Actifs Voyageurs, MOB, 2026-06-09). ADR-060.
#
# Distinction critique :
#   PLACES ASSISES = places fixes, réservables, utilisables sans restriction
#   OFFRE APC      = offre enregistrée dans le SI comptage = assises + strapontins
#                    (zones multi-usages : vélos, skis, bagages — spec P01)
# ---------------------------------------------------------------------------

CAPACITE_ASSISE_2C_SURF7500: int = 63
"""Places assises 2ème classe, rame SURF 7500 simple.
Spec MOB ABeh 7501-7508, colonne 'Places assises 2ème'. ADR-060.
Équation de réconciliation : 63 assises + 31 strapontins = 94 offre APC."""

OFFRE_TOTALE_2C_APC_SURF7500: int = 94
"""Offre totale 2ème classe enregistrée dans le SI APC, rame SURF 7500 simple.
Inclut 31 strapontins (zones multi-usages non mobilisables comme sièges).
Formule : 63 places assises + 31 strapontins = 94. ADR-060."""

CAPACITE_ASSISE_1C_SURF7500: int = 12
"""Places assises 1ère classe, rame SURF 7500 simple."""

CAPACITE_ASSISE_TOTAL_SURF7500: int = 75
"""Total places assises, rame SURF 7500 simple (2C + 1C = 63 + 12).
Note : l'offre APC totale est 106 = 94 + 12 (strapontins 2C inclus)."""

CAPACITE_ASSISE_2C_SURF7500_UM: int = 126
"""Places assises 2ème classe, Unité Multiple (2 rames couplées = 63 × 2)."""

OFFRE_TOTALE_2C_APC_UM: int = 188
"""Offre totale 2ème classe APC, Unité Multiple (2 rames couplées = 94 × 2)."""

CAPACITE_ASSISE_1C_SURF7500_UM: int = 24
"""Places assises 1ère classe, Unité Multiple (2 rames couplées)."""

CAPACITE_ASSISE_TOTAL_SURF7500_UM: int = 150
"""Total places assises, Unité Multiple (2 rames couplées = 75 × 2)."""

# Note (ADR-077) : la strate 166+ de l'évaluation couche 2 s'appuie sur une limite
# MASSIQUE (12,7 t de charge max admissible par rame), dont 166 est la projection
# conventionnelle en personnes (places debout comprises, hors strapontins/vélos/chaises
# roulantes ; élicitation écrite du 2026-07-09). 166 n'est donc PAS une capacité de places
# et ne contredit pas les valeurs ci-dessus (63/94/188) : grandeurs différentes.

# ---------------------------------------------------------------------------
# Seuil UM opérationnel
# Correspond à CAPACITE_ASSISE_2C_SURF7500 = 63 : charge > 63 signifie qu'au
# moins un voyageur se retrouve sans siège en 2ème classe.
# Convention pipeline (add_features_to_raw_stacked.py) :
#   is_surcharge_2c = target_voyageurs_2eme_classe > SEUIL_UM_2C
# ADR : ADR-005 (mis à jour ADR-060, 2026-06-09)
# ---------------------------------------------------------------------------

SEUIL_UM_2C: int = CAPACITE_ASSISE_2C_SURF7500
"""
Seuil UM opérationnel : charge 2ème classe > SEUIL_UM_2C → au moins un voyageur sans siège.

Convention (strictement supérieur — identique au pipeline feature win7_n_surcharges) :
  is_surcharge_2c          = target_voyageurs_2eme_classe >  SEUIL_UM_2C   # > 63
  recommandation_um        = prediction_voyageurs_2eme_classe > SEUIL_UM_2C  # couche 2

Valeur : 63 (places assises 2ème classe SURF 7500).
Ne pas confondre avec OFFRE_TOTALE_2C_APC_SURF7500 = 94 (offre APC, strapontins inclus).
"""

# ---------------------------------------------------------------------------
# Cible ML officielle
# ADR : ADR-001_cible_2eme_classe.md
# ---------------------------------------------------------------------------

TARGET_COL: str = "target_voyageurs_2eme_classe"
"""Colonne cible du modèle ML. Ne pas utiliser target_voyageurs_total."""

TARGET_CONTROLE_COL: str = "target_voyageurs_total"
"""Colonne de contrôle qualité uniquement — pas la cible ML."""

# ---------------------------------------------------------------------------
# Paramètres de reproductibilité
# ---------------------------------------------------------------------------

RANDOM_STATE: int = 42
"""Graine aléatoire fixe pour tous les appels stochastiques."""
