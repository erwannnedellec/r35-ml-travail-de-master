---
id: ADR-014
ancien_id: ADR-14
date_decision: 2026-05-15
statut: remplacé
remplace_par: [ADR-019]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-014 — Fenêtre de correspondance Vevey [-20, -2] minutes

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-019.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Pour calculer les correspondances CFF→R35 à Vevey, il faut définir quelle
fenêtre temporelle avant le départ R35 constitue une correspondance valide.

Deux paramètres structurent cette fenêtre :
- **Borne amont** : au-delà de combien de minutes d'attente un voyageur ne
  prend-il plus le R35 pour rejoindre un destination par une autre voie ?
- **Borne aval** : en-deçà de combien de minutes avant le départ le voyageur
  ne peut-il plus monter dans le train ?

Un troisième paramètre définit le seuil de retard au-delà duquel une
correspondance est considérée comme ratée :
- **Seuil retard feeder** : au-delà de ce retard, le voyageur rate le R35.

## Décision

Fenêtre retenue : `[depart_R35 - 20 min, depart_R35 - 2 min]`  
Seuil retard feeder : 5 minutes (300 secondes)

| Paramètre | Valeur | Justification |
|---|---|---|
| Borne amont | 20 min | Temps maximal d'attente acceptable à Vevey gare (quai couvert) |
| Borne aval | 2 min | Temps minimal de transfert entre quai CFF et quai R35 |
| Seuil retard | 5 min | Marge de tolérance opérationnelle CFF/MVR-cev |

## Conséquences

- Un train R35 partant à 9h30 compte les feeders arrivés entre 9h10 et 9h28.
- Un feeder arrivé à 9h25 avec 6 min de retard (heure prévue 9h19) est comptabilisé
  dans la fenêtre mais NOT comme correspondance effective.
- Les trains R35 ne partant pas de Vevey (BPUIC ≠ 8501200) ont NaN pour
  toutes les features correspondances — comportement attendu et géré par XGBoost.

## Sensibilité à tester (Phase 4)

Variants à évaluer :
- Borne amont 15 min (voyageurs qui arrivent juste avant le départ)
- Seuil retard feeder 3 min (plus strict)
- Exclusion des feeders RE33 (longue distance, correspondances moins systématiques)

## Addendum (2026-07-24)

La fenêtre de correspondance [-20, -2] minutes est supersédée par ADR-019, qui fixe la fenêtre finale de une à cinq minutes entre l'arrivée du train apporteur et le départ R35 (mémoire, section 4.4.2).
