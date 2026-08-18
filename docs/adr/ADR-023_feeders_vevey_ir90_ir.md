---
id: ADR-023
ancien_id: ADR-24
date_decision: 2026-05-21
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-023 — Inclusion de IR90 et IR dans les feeders Vevey

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté
**Date** : 2026-05-21
**Décideur** : Erwann Nédellec (superviseur)

## Contexte

Le calcul des correspondances Vevey CFF ↔ R35 (`build_dim_correspondances_vevey.py`,
`build_istdaten_ponctualite.py`) utilise une liste de lignes "feeders" qui
alimentent ou captent les voyageurs du R35 à la gare de Vevey (BPUIC=8501200).

La liste initiale (`S3`, `S4`, `S7`, `R3`, `R4`, `R7`, `RE`, `RE33`) couvrait les
lignes régionales et le RE33 mais omettait les lignes InterRegio passant par Vevey.

## Diagnostic (données ISTDATEN 2024, BPUIC=8501200, hors transit et annulés)

| LINIEN_TEXT | Passages 2024 | Commentaire |
|---|---|---|
| R35 | 32 030 | La ligne elle-même — pas un feeder |
| RE33 | 23 421 | ✅ inclus |
| **IR90** | **22 975** | ❌ absent — Genève-Aéroport–Brig |
| R3 | 14 616 | ✅ inclus |
| R4 | 14 269 | ✅ inclus |
| R7 | 13 201 | ✅ inclus |
| **IR** | **3 236** | ❌ absent — désignation générique (voir ci-dessous) |
| RE | 1 434 | ✅ inclus |
| IR95 | 590 | ❌ exclus (volume marginal) |
| SN / EC / EXT | < 250 | ❌ exclus (internationaux / exceptionnels) |

### Analyse de "IR" (sans suffixe numérique)

- **Opérateur** : SBB uniquement.
- **Distribution horaire** : 72% des passages entre 5h et 7h, + 0h et 23h.
  Ces trains correspondent aux premières et dernières courses du jour sur
  l'axe Genève–Brig (même axe qu'IR90), qui conservent l'ancien label générique
  "IR" dans ISTDATEN tandis que les trains de journée ont été renommés "IR90".
- **LINIEN_IDs** : distincts des LINIEN_IDs IR90 — pas de doublons.
- **Conclusion** : feeders réels concentrés en heures de pointe matinale.

## Décision

Ajouter **IR90** et **IR** à `LINIEN_FEEDERS_VEVEY` / `LINIEN_FEEDERS` dans les
deux scripts concernés. Exclusions maintenues :

| Ligne | Décision | Motif |
|---|---|---|
| IR90 | ✅ inclus | Volume identique à RE33, ligne touristique Genève–Brig directe |
| IR | ✅ inclus | Premiers/derniers trains du jour sur axe IR90, feeders matinaux pertinents |
| IR95 | ❌ exclus | < 600 passages/an, impact statistique négligeable |
| SN | ❌ exclus | Scenic Night / services nocturnes internationaux |
| EC | ❌ exclus | EuroCity, clientèle longue distance, peu de correspondances R35 |
| EXT / EXT3 / EXT33 | ❌ exclus | Trains exceptionnels (<200 passages), bruit catégoriel |

## Justification de l'inclusion IR90

La R35 dessert Les Pléiades, destination touristique de référence du chablais vaudois.
L'IR90 Genève-Aéroport–Brig (via Lausanne, Vevey, Montreux) est la liaison principale
amenant la clientèle touristique depuis Genève, Lausanne et le Valais vers Vevey, point
de correspondance naturel avec la R35. Son omission initiale constituait un biais
systématique dans les features de correspondance.

## Conséquences

- `ist_vevey_n_arrivees_j` et indicateurs associés augmenteront (~+5-10% de passages).
- `ist_corresp_in_n_theoriques_j` et `ist_corresp_out_n_theoriques_j` augmenteront
  pour les trains R35 dont les horaires coïncident avec les IR90/IR.
- Le pipeline de dimension `dim_correspondances_vevey` doit être régénéré.
- L'impact quantitatif est documenté dans le message de comparaison AVANT/APRÈS.

## Fichiers impactés

- `scripts/sources/build_istdaten_ponctualite.py` — `LINIEN_FEEDERS_VEVEY`
- `scripts/sources/build_dim_correspondances_vevey.py` — `LINIEN_FEEDERS`
