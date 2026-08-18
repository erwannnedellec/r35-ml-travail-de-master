---
id: ADR-019
ancien_id: ADR-21
date_decision: 2026-05-17
statut: actif
modifie: [ADR-010, ADR-012, ADR-014, ADR-016]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-019 — Refonte des features ISTDATEN : grain tronçon + rolling par type de jour

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-010, ADR-012, ADR-014, ADR-016.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Accepté  
**Date** : 2026-05-17  
**Auteur** : E. Nédellec  

---

## Contexte

La première version des features ISTDATEN (ponctualité et correspondances)
présentait trois limites identifiées lors de la revue critique du pipeline :

1. **Grain train-jour trop grossier** : la ponctualité était agrégée au niveau
   du train pour toute sa course. La dégradation cumulée des retards le long
   du parcours (souvent observée sur les lignes de montagne) était invisible.

2. **Correspondances unidirectionnelles** : seul le flux entrant (CFF → R35) était
   modélisé. Le flux sortant (R35 → CFF) est tout aussi structurant pour le
   comportement de report modal des voyageurs descendants.

3. **Rolling windows mélangent les types de jour** : grouper par `numero_train`
   sans filtrer par type de jour combine des observations hétérogènes (ex. un
   lundi chargé compte autant qu'un dimanche creux dans la fenêtre de 7 jours).
   De plus, `numero_train` ne distingue pas deux services portant le même numéro
   avant et après un changement d'horaire annuel.

---

## Décisions

### D1 — Grain tronçon pour `dim_profil_train`

Le grain de sortie passe de `(date, numero_train)` à
`(date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)`.

La reconstruction des tronçons suit la même logique que `build_dim_headway.py` :
tri par heure de départ effective, paires d'arrêts successifs, sens déduit du km.

La jointure dans `add_istdaten_to_raw_stacked.py` est mise à jour en conséquence
pour utiliser les cinq clés `(base_date, horaire_numero_train, id_gare_depart_bpuic,
id_gare_arrivee_bpuic, base_sens)`.

### D2 — Correspondances bidirectionnelles (`_in_` et `_out_`)

`build_dim_correspondances_vevey.py` produit désormais deux familles :
- `ist_corresp_in_*` : feeders CFF arrivant à Vevey avant le départ d'un R35 montant.
  Fenêtre théorique : [départ_R35 - 5 min, départ_R35 - 1 min].
  Garantie : arrivée effective CFF dans la même fenêtre basée sur le départ effectif R35
  (aucun seuil de retard — la fenêtre effective suffit comme critère).
- `ist_corresp_out_*` : CFF partant de Vevey après l'arrivée d'un R35 descendant.
  Fenêtre théorique : [arrivée_R35 + 1 min, arrivée_R35 + 5 min].
  Garantie : départ effectif CFF dans la même fenêtre basée sur l'arrivée effective R35.

Les features sont NaN pour les trains ne passant pas par Vevey dans le sens
concerné. La propagation sur tous les tronçons du train est faite lors de la
jointure (grain train × jour, not tronçon).

Un avertissement est émis si des trains apparaissent dans les deux sens sur
le même jour (correspondances bidirectionnelles).

### D3 — Rolling conditionnel par type de jour

Un utilitaire partagé `_rolling_par_type_jour.py` implémente des fenêtres
glissantes qui ne comptent que les occurrences du **même type de jour** :
- `ouvrable` (lun–ven, hors fériés)
- `samedi`
- `dimanche_ferie`

Cette classification est ajoutée au stage_02 sous le nom `cal_type_jour_3classes`
(dérivée de `cal_type_jour` à 9 classes existant).

### D4 — Groupement par service_id au lieu de numero_train

Le `group_key` des rolling windows passe de `numero_train` à `ist_service_id`
(`{numero_train}_{heure_origine_Hh}`), qui encode implicitement l'année horaire
via l'heure de première desserte.

Avantage : un train 1308 à 07h12 en H23 et un train 1308 à 07h15 en H24
(après recadençage) ne partagent plus le même historique.

### D5 — Deux fenêtres : 5 occurrences et 20 occurrences

| Fenêtre | `min_periods` | Usage |
|---------|--------------|-------|
| 5 occ   | 2            | Signal réactif (environ 1 semaine d'ouvrables) |
| 20 occ  | 5            | Signal de tendance (environ 1 mois d'ouvrables) |

Ces fenêtres remplacent les fenêtres 7j et 28j calendaires précédentes,
qui sous-pondéraient les weekends.

---

## Features produites

### `dim_profil_train` (12 features par tronçon-train-jour)

Pour `position ∈ {dep, arr}` et `fenêtre ∈ {5occ, 20occ}` :

| Feature | Description |
|---------|-------------|
| `ist_profil_train_retard_{pos}_troncon_mean_{fen}` | Retard moyen (s) sur les N dernières occurrences du même type de jour |
| `ist_profil_train_retard_{pos}_troncon_std_{fen}` | Écart-type du retard |
| `ist_profil_train_pct_en_retard_{pos}_troncon_{fen}` | Part des occurrences avec retard ≥ 180 s |

### `dim_correspondances_vevey` (12 features par train-jour)

Pour `sens ∈ {in, out}` et `fenêtre ∈ {5occ, 20occ}` :

| Feature | Description |
|---------|-------------|
| `ist_corresp_{sens}_n_theoriques_moy_{fen}` | Moyenne glissante du nb de CFF dans la fenêtre théorique |
| `ist_corresp_{sens}_n_garanties_moy_{fen}` | Moyenne glissante du nb de correspondances garanties |
| `ist_corresp_{sens}_pct_garanties_{fen}` | Moyenne glissante du taux de garantie |

Les features `_j` (valeurs journalières) sont calculées en interne pour le
rolling mais ne figurent pas dans le parquet de sortie.

---

## Conséquences

### Positives
- Le modèle peut capturer la dégradation de ponctualité le long du parcours.
- Le flux sortant enrichit la modélisation des voyageurs descendants.
- Les fenêtres par type de jour sont homogènes et interprétables.
- Le service_id évite le leakage cross-horaire sans nécessiter `horaire_annee_horaire`
  dans la clé de groupe.

### Négatives / Compromis
- La jointure profil_train dans `add_istdaten_to_raw_stacked.py` utilise 5 clés
  au lieu de 2. Risque de NaN plus élevé si les tronçons ISTDATEN ne couvrent pas
  exactement les tronçons APC (ex. tronçons supplémentaires ou réorganisés).
- Le calcul des rolling est plus lent (boucle par type de jour × groupe).
- La lecture des CSVs ISTDATEN est maintenant réalisée **deux fois** dans
  `build_dim_correspondances_vevey.py` (arrivées et départs). À optimiser si les
  temps d'exécution deviennent contraignants.

### Fichiers modifiés
| Fichier | Rôle |
|---------|------|
| `scripts/sources/_rolling_par_type_jour.py` | Nouveau — utilitaire partagé |
| `scripts/pipeline/add_vacances_feries_vaud_to_raw_stacked_annee_horaire.py` | Ajout `cal_type_jour_3classes` |
| `scripts/sources/build_dim_profil_train.py` | Refonte complète — grain tronçon |
| `scripts/sources/build_dim_correspondances_vevey.py` | Refonte — fenêtre [5,1], garantie sans seuil retard, rolling 3 features, output sans `_j` |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py` | Clés de jointure tronçon pour profil_train ; suppression famille VMCV |

---

## Alternatives rejetées

### A1 — Conserver le grain train-jour pour la ponctualité

Rejeté : la ponctualité en tête de ligne n'est pas représentative de la
ponctualité sur les tronçons hauts (Chamby–Les Pléiades), qui sont les plus
sensibles aux conditions météo. Le grain tronçon est nécessaire.

### A2 — Rolling par jour de semaine (7 classes au lieu de 3)

Rejeté : trop peu d'occurrences par groupe pour les jours rares (ex. pont,
veille de fériée). Trois classes donnent un compromis acceptable entre
homogénéité et volumétrie.

### A3 — Lire les CSVs ISTDATEN une seule fois pour _in_ et _out_

Possible en combinant la lecture en un seul passe. Non implémenté pour
conserver la lisibilité du code. À envisager si le temps de build > 30 min.
