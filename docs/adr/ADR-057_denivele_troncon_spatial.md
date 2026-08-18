---
id: ADR-057
ancien_id: ADR-CF14
date_decision: 2026-06-07
statut: actif
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-057 — Feature topologique : dénivelé signé du tronçon (`spatial_denivele_troncon_m`)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date :** 2026-06-07  
**Statut :** Accepté  
**Auteur :** Erwann Nedellec  

---

## Contexte

Le ml_dataset (hash `d3000f48`, 204 colonnes) contient déjà deux features topologiques
d'ordre (`spatial_gare_depart_ordre`, `spatial_gare_arrivee_ordre`) et une feature de
segment (`spatial_segment` = bas/haut). Ces features capturent la position et le contexte
géographique du tronçon sur la ligne, mais pas l'intensité ni le sens de la pente.

La ligne R35 présente un profil altimétrique très marqué : de Vevey (386 m) aux Pléiades
(1348 m), soit 962 m de dénivelé positif sur 11 km. La crémaillère commence à partir de
Blonay. Certains tronçons sont très pentus (ex. Lally→Ondallaz : +147 m), d'autres
quasi-plats (ex. Vevey→Gilamont : +45 m). Cette variabilité d'intensité n'est capturée
par aucune feature actuelle.

Par ailleurs, le sens de circulation est structurellement asymétrique : la montée
(VV→PLEI) peut générer des profils de charge différents de la descente (PLEI→VV) à
position et contexte identiques, notamment sur les tronçons touristiques de crémaillère.

---

## Décision

Ajouter **une seule feature**, `spatial_denivele_troncon_m`, définie comme :

```
spatial_denivele_troncon_m = altitude_gare_arrivee − altitude_gare_depart  [mètres, signé]
```

- **Positif** : tronçon parcouru en montée (arrivée plus haute que départ)
- **Négatif** : tronçon parcouru en descente
- **Préfixe** `spatial_` : cohérent avec la topologie du tronçon (même famille que
  `spatial_segment`, `spatial_gare_depart_ordre`, etc.)
- **Stage** : `03e` (`add_spatial_to_raw_stacked.py`) — stage naturel pour les features
  topologiques, là où `spatial_segment` est déjà calculé

Les altitudes sont lues depuis **`data/dimension/dim_gare.csv`** (source de vérité,
19 entrées, toutes avec altitude valide) et non depuis les colonnes
`spatial_gare_depart_altitude` / `spatial_gare_arrivee_altitude` déjà présentes dans
le pipeline, qui héritent d'un NaN pour GIL et CLIE (héritage du fallback sans `height`
dans `stack_raw_csv.py` / `gare_GIL_CLIE.csv`).

---

## Justification du signal orthogonal

| Feature existante | Ce qu'elle capture | Ce qu'elle ne capture pas |
|---|---|---|
| `spatial_gare_depart_ordre` | Position ordinale de la gare de départ | Intensité de la pente entre les deux gares |
| `spatial_gare_arrivee_ordre` | Position ordinale de la gare d'arrivée | Idem |
| `spatial_segment` (bas/haut) | Contexte crémaillère vs plaine | Finesse intra-segment (ex. OND→LAL vs TUS→CHEV) |
| `spatial_denivele_troncon_m` | **Intensité + sens de la pente** | — |

Le dénivelé signé apporte un signal **orthogonal** : deux tronçons peuvent avoir le même
ordre de départ et d'arrivée mais des dénivelés très différents (ex. tronçons non-adjacents
dans les APC). Le sens distingue la montée touristique (surcharge crémaillère le matin)
de la descente (retours, profils inverses).

---

## Décision de NE PAS ajouter l'altitude brute

Deux features d'altitude brute (`spatial_gare_depart_altitude`,
`spatial_gare_arrivee_altitude`) sont déjà présentes dans les stages intermédiaires
mais **exclues du ml_dataset** (elles ne figurent pas dans la liste des features conservées
par `build_ml_dataset.py`).

Cette exclusion est maintenue délibérément :
- L'altitude de départ et d'arrivée est **fortement corrélée** à `spatial_gare_depart_ordre`
  et `spatial_gare_arrivee_ordre` (relation monotone sur la ligne) → redondance.
- Le modèle dispose déjà de `spatial_gare_depart_km` et `spatial_gare_arrivee_km` comme
  proxy kilométrique de la position.
- Le dénivelé **signé** apporte le signal manquant (pente orientée) sans double-compter
  l'information de position déjà couverte.

---

## Vérification préalable des données

| Gare | Période active | Altitude dim_gare.csv | Altitude dim_gare.parquet | Statut |
|------|---------------|----------------------|--------------------------|--------|
| VV (Vevey) | H16–H25 | 386.5 m | 386.5 m | ✅ |
| GIL (Gilamont) | H16–H22 | 431.7 m | NaN ⚠ | ✅ lu depuis CSV |
| CLIE (Clies) | H16–H18 | 457.9 m | NaN ⚠ | ✅ lu depuis CSV (hors périmètre H22–H25) |
| VVVI (Vevey Vignerons) | H23–H25 | 444.4 m | 444.4 m | ✅ |
| PLEI (Les Pléiades) | H16–H25 | 1348.2 m | 1348.2 m | ✅ |
| Autres 14 gares | H16–H25 | présentes | présentes | ✅ |

Le NaN de GIL et CLIE dans `dim_gare.parquet` provient du script `build_dim_gare.py` /
`stack_raw_csv.py` qui initialise `height = NaN` pour le fallback (`gare_GIL_CLIE.csv`
sans colonne `height`). La lecture directe depuis `dim_gare.csv` résout le problème sans
régénérer la chaîne entière depuis `apc_stacked`.

---

## Non-régression

Test exécuté après régénération complète de stage_03e → stage_10 → ml_dataset :

- Lignes : 1 141 984 (inchangé)
- Colonnes ml_dataset : 204 → **205** (+1 exactement)
- `spatial_denivele_troncon_m` : **0 NaN**, min=−153.9 m, max=+153.9 m, mean=−0.6 m
- Toutes les autres colonnes et toutes les lignes : inchangées

---

## Résultat

- Nouveau hash `ml_dataset.parquet` : **`0c0b7807`** (remplace `d3000f48`)
- Feature ajoutée au stage_03e (`add_spatial_to_raw_stacked.py`)
- `DIM_GARE_CSV` ajouté à `scripts/pipeline/paths.py` comme constante canonique

---

## Liens

- ADR-055 : correction VVVI STATPOP 2022 (hash `d3000f48`)
- ADR-056 : SIMBA jointure NaN confirmé empiriquement
