---
id: ADR-015
ancien_id: ADR-15
date_decision: 2026-05-15
statut: actif
modifie: [ADR-008]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-015 — Logique opérationnelle J-2 pour les features ISTDATEN

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-008.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-15

## Contexte

Le pipeline de prédiction produit chaque matin du jour J une prédiction de
fréquentation pour le lendemain (jour J+1). Les features ISTDATEN (profil de
ponctualité, correspondances Vevey) sont calculées à partir des données
real-time publiées par l'OFT.

La question est : jusqu'à quelle date les données ISTDATEN sont-elles
disponibles au moment où le pipeline tourne ?

## Contrainte opérationnelle

L'OFT publie les données ISTDATEN avec un décalage de traitement d'environ
24h. Au matin du jour J, les données disponibles couvrent jusqu'à J-2 au plus
tôt de manière fiable. Les données de J-1 peuvent être incomplètes ou absentes.

Conséquence : toute feature ISTDATEN utilisée pour prédire J+1 (depuis le
pipeline tournant le matin de J) doit être calculée à partir de données
≤ J-2.

## Décision

Le décalage J-2 est porté **exclusivement par la jointure** dans
`add_istdaten_to_raw_stacked.py`. Les fenêtres glissantes dans les scripts
de dimension utilisent `lag=0` (aucun décalage interne).

| Composant | V1 (incorrect) | V2 (double-lag, incorrect) | V3 (correct) |
|---|---|---|---|
| `build_dim_profil_train.py` — rolling | `shift(1)` | `shift(2)` | `shift(0)` |
| `build_dim_correspondances_vevey.py` — rolling | `shift(1)` | `shift(2)` | `shift(0)` |
| `add_istdaten_to_raw_stacked.py` — jointure | `Timedelta(days=1)` | `Timedelta(days=2)` | `Timedelta(days=2)` ✓ |

**Pourquoi V2 était incorrect** : avec `lag=2` dans le rolling ET `+2j` dans
la jointure, pour `base_date=J` on lisait la ligne ISTDATEN de `date=J-2`,
dont la fenêtre rolling se terminait à `(J-2) - 2 occurrences du même type de jour`.
Pour les jours ouvrables c'est J-4, pour les samedis c'est J-2-14j = J-16.
Double-décalage non voulu.

**V3** : rolling avec `lag=0` à `date=J-2` → fenêtre couvrant les N dernières
occurrences du même type de jour se terminant à J-2 inclus. La jointure
matérialise ensuite J-2 → `base_date=J`. Décalage J-2 strict respecté.

Les features VMCV sont statiques (pas de dimension temporelle) : non affectées.

## Conséquences

- Pour une prédiction du jour J+1 produite le matin de J, les features
  ISTDATEN reflètent l'historique jusqu'à J-2 inclus (2 jours de plus de
  données qu'avec V2).
- La couverture des features roulantes augmente (V2 pouvait être à J-4 ou plus).
- Le test `TestJointureJMoins2` vérifie explicitement que J-1 ne matche pas
  et que J-2 matche.

## Alternative écartée

**Shift(1) / J-1** : acceptable si le pipeline tourne après la publication
complète des données ISTDATEN de la veille. Écarté car les données de J-1
sont publiées avec un décalage variable et non garanti avant l'heure de
lancement du pipeline.
