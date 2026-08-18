---
id: ADR-002
ancien_id: ADR-02
date_decision: 2026-05
statut: remplacé
remplace_par: [ADR-027]
corroboration_date: dépôt de travail, commit du 2026-05-12
gel_registre: 2026-08-16
---

# ADR-002 — Stratégie de split temporel : scénario candidat H17–H22 / H23 / H24

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-027.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Proposition — décision finale reportée à la phase de modélisation |
| **Date** | 2026-05 |
| **Décideur** | Erwann Nedellec |
| **Notebook de référence** | `02_data_understanding_apc.ipynb` §5 |

## Contexte

La décision définitive du split train / validation / test ne peut pas être prise en phase de Data Understanding. Elle dépend de facteurs qui ne sont pas tous connus à ce stade :

- Stationnarité temporelle des APC (partiellement analysée en §5)
- Disponibilité effective des variables explicatives par année horaire (ISTDATEN disponible seulement à partir de 2018)
- Ruptures topologiques de la ligne (CLIE actif H16–H18, GIL actif H16–H22, VVVI depuis H23)
- Ruptures d'offre ou d'exploitation (COVID H20–H22, modifications de service)
- Disponibilité des sources externes (ski H20–H25, météo CHD, etc.)
- Performances obtenues lors des premiers entraînements
- Importance réelle des features selon la modélisation
- Contraintes d'évaluation temporelle propres à un cas J-1

Cette ADR documente le **scénario candidat** le plus robuste identifié en Data Understanding, sans le présenter comme définitivement retenu.

## Scénario candidat analysé

Trois options ont été envisagées ou analysées :

| Option | Train | Val | Test | Statut |
|---|---|---|---|---|
| A (restrictive) | H22–H23 | walk-forward trim. intra-H23 | H24 | Conservée en analyse de sensibilité |
| B (candidat) | H17–H22 | H23 | H24 | Scénario initial — ISTDATEN OK, stationnarité démontrée |
| C (candidat étendu) | H16–H22 | H23 | H24 | En analyse NB01/NB02 §5.2 — H16 exploitable avec `target_2eme_classe` |

Les tests KS conduits en §5 ont fourni des éléments favorables aux options B et C :
- KS(H22, H23) = 0.076 < 0.15 — stationnarité entre train et val démontrée
- KS(H23, H24) = 0.072 < 0.15 — stationnarité entre val et test démontrée
- 5–7 ans d'historique (H17–H22 ou H16–H22) offrent un signal de robustesse incluant la période COVID
- H23 est la première année avec ISTDATEN stable (TCE cours > 93 %)

**Note H16** : initialement exclue pour 55,5 % de nulls sur `voyageurs_1ere_classe`. Avec la cible `target_voyageurs_2eme_classe` (0,7 % de nulls), H16 peut être incluse dans l'entraînement si la stationnarité KS(H16, H17–H22) est confirmée en NB02 §5.2. Cette décision fait partie des arbitrages à finaliser en phase de modélisation.

## Éléments d'aide à la décision

Les analyses APC et les tests KS constituent des **éléments d'aide à la définition du split**, non une décision finale. Le split final sera déterminé de manière itérative dans la phase de modélisation, en tenant compte :

1. De la disponibilité des features `ist_*` (NA sur H17–H21 → impact sur la richesse réelle du train set)
2. Des ruptures topologiques (VVVI actif depuis H23 → impact sur la cohérence des tronçons)
3. Des premiers résultats de modélisation et de la distribution des erreurs par sous-période
4. De la pertinence métier de l'évaluation (représentativité de H24 pour les conditions actuelles)

## Statut de H25

H25 (14 déc. 2024 en cours) est disponible partiellement dans les tables APC. Elle peut être analysée à titre descriptif pour vérifier la couverture des données.

**H25 n'est pas scellée comme test final à ce stade.** Elle ne sera éventuellement désignée comme holdout final qu'après décision explicite en phase de modélisation, selon les données disponibles et la complétude de l'année horaire.

## Conséquences provisoires

- **Walk-forward candidat** : H17–H22 → Val H23 → Test H24. Validation trimestrielle intra-H23 disponible en robustesse.
- **ISTDATEN** : features `ist_*` à NaN sur H17–H21 — gérées nativement par LightGBM/XGBoost, mais à évaluer sur la richesse informative effective du train set.
- **Pondération H20–H22Q1** : la rupture COVID (KS 2022Q1→Q2 = 0.123) peut justifier une pondération réduite des observations de cette période — à décider en `04_data_preparation`.
- **Analyse de sensibilité** : split court H22/H23 (option A) présenté en annexe Ch. 4 comme variante restrictive.

## Formulation recommandée pour la documentation

"À ce stade, les analyses de stationnarité APC et les ruptures topologiques documentées fournissent des éléments d'aide à la définition du futur split train / validation / test. Le split final n'est toutefois pas arrêté dans la phase de Data Understanding. Il sera déterminé ultérieurement de manière itérative, en tenant compte de la disponibilité des variables explicatives, de la stabilité temporelle, des premiers résultats de modélisation et de la pertinence métier de l'évaluation."

## Alternatives considérées

| Alternative | Raison d'exclusion |
|---|---|
| Split court H22–H23/H24 (option A) | Conservé en analyse de sensibilité ; écarté comme split principal car richesse 5 ans disponible |
| Split aléatoire | Interdit — leakage temporel |
| Leave-one-year-out | Coût computationnel disproportionné pour le gain attendu |

## Fichiers impactés

- `notebooks/01_business_understanding.ipynb` §6 (scénario de split)
- `notebooks/02_data_understanding_apc.ipynb` §5 (tests KS, stationnarité)
- Future : `notebooks/04_data_preparation.ipynb` (décision finale du split)

