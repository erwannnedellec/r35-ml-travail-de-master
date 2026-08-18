---
id: ADR-029
ancien_id: ADR-30
date_decision: 2026-05-23
statut: actif
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-029 — Reclassification zonale Montreux et décomposition événementielle par localité R35

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-23 |
| **Décideur** | Erwann Nedellec |
| **Scripts modifiés** | `scripts/sources/build_dim_manifestations_riviera.py`, `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` |

---

## 1. Contexte

Le système événementiel (cf. CONTEXT.md section « Sources intégrées ») agrège les manifestations
Montreux Riviera Tourisme en 3 zones géographiques (`zone_directe`, `zone_indirecte`, `hors_zone`)
selon le champ `lieu` des PDFs sources. Deux limites structurelles ont été identifiées lors de
l'audit pré-modélisation.

**Limite 1 — Confusion entre proximité géographique et connectivité ferroviaire.**

La classification initiale plaçait Montreux et ses dépendances (Territet, Clarens, Chailly,
Veytaux, Glion, Caux, Villeneuve, etc.) en `hors_zone`. Or :

- Montreux est directement connectée à Vevey (terminus R35) par la ligne du Léman à haute fréquence.
- Les grosses manifestations montreusiennes (Montreux Jazz Festival, Montreux Noël, Marché de Noël,
  Montreux Trail Festival, Freddie Celebration Days, MAG Montreux Art Gallery, Foire des Planches,
  Montreux Nestlé Open) génèrent un effet d'attraction régional qui déborde mécaniquement sur la R35
  par plusieurs canaux :
  - Visiteurs logeant dans le segment R35 (Blonay, Saint-Légier) et se déplaçant vers Montreux.
  - Excursions touristiques aux Pléiades pendant les festivals (offre montagne complémentaire).
  - Saturation hôtelière qui pousse les visiteurs vers le segment haut de la ligne.

Classer ces événements en `hors_zone` confondait proximité géographique (Montreux est loin du
segment Blonay) et connectivité fonctionnelle (Montreux est directement reliée à Vevey).

**Limite 2 — Granularité spatiale insuffisante en zone directe.**

Le compteur `event_n_manifestations_zone_directe_j` agrégeait les manifestations des 3 localités
traversées par la R35 sans distinction. Or chaque localité correspond à un régime de trafic distinct :

- **Vevey** : terminus urbain lacustre, fort flux pendulaire et touristique.
- **Saint-Légier** : corridor piémont résidentiel pavillonnaire.
- **Blonay** : pôle crémaillère + accès montagne touristique (Pléiades).

Un événement à Vevey n'impacte probablement pas le segment R35 de la même manière qu'un événement
à Saint-Légier ou Blonay. L'agrégation masquait cette asymétrie.

---

## 2. Décisions

### Décision 1 — Reclassification zonale Montreux

Le mapping `LIEU_TO_ZONE_NORMALIZED` dans `build_dim_manifestations_riviera.py` est modifié.

**Reclassement de `hors_zone` vers `zone_indirecte`** (14 lieux) :

| Lieu normalisé | Justification |
|---|---|
| montreux | Terminus ligne du Léman côté Montreux, connexion directe à Vevey |
| territet | Quartier de Montreux, même bassin de correspondance |
| clarens, clarens s/montreux | Commune entre Montreux et Vevey |
| chailly, chailly s/montreux | Localité sur les hauteurs de Montreux |
| chernex | Commune de la commune de Montreux |
| vernex | Quartier de Montreux |
| veytaux | Commune entre Montreux et Villeneuve |
| villeneuve, villeneuve-montreux | Terminus est de la ligne du Léman |
| glion | Hauteurs de Montreux, accessible via Montreux |
| caux | Idem |
| brent | Hameau sur les hauteurs de Montreux |

**Maintien en `hors_zone`** (lieux sans connectivité pertinente vers la R35) :

| Lieu normalisé | Justification |
|---|---|
| jaman, rochers-de-naye, les avants | Accessibles uniquement via ligne MOB Montreux–Rochers, pas par la R35 |
| cully, lutry, epesses, rivaz, st-saphorin | Côté Lavaux/Lausanne, opposé à la R35 |
| lausanne | Hors périmètre Riviera R35 |
| aran s, villette | Proches de Cully |
| riviera | Région entière, signal trop large pour être discriminant |

### Décision 2 — Décomposition événementielle par localité R35

Ajout de 3 features de comptage journalier dans `dim_manifestations_riviera` et propagation
dans le stage 03, **en complément** des features zonales existantes (conservées).

| Feature | Type | Description |
|---|---|---|
| `event_n_manifestations_vevey_j` | Int8 | Manifestations à Vevey ce jour |
| `event_n_manifestations_st_legier_j` | Int8 | Manifestations à Saint-Légier ce jour |
| `event_n_manifestations_blonay_j` | Int8 | Manifestations à Blonay et localités rattachées (Pléiades, etc.) ce jour |

**Logique de classification par sous-chaîne** (fonction `classify_localite_r35`) :

Le champ `lieu` est normalisé (lowercase, suppression des diacritiques) puis examiné par
recherche de sous-chaîne dans l'ordre de priorité suivant :

1. `"vevey"` dans le lieu normalisé → localité **Vevey**
2. `"legier"` dans le lieu normalisé → localité **Saint-Légier**
3. `"blonay"` ou `"pleiades"` dans le lieu normalisé → localité **Blonay**
4. Sinon → `hors_r35` (ne contribue à aucun des 3 compteurs)

Cette logique couvre naturellement les variantes orthographiques rencontrées dans les PDFs
(Vevey-Vignerons, Saint-Légier, St Légier, Blonay-Chamby, Les Pléiades, etc.).

La priorité Vevey > Saint-Légier > Blonay gère les rares lieux multi-localisations
(ex. `"Vevey/La Tour-de-Peilz/St-Légier"` → Vevey).

**Correspondance avec la topologie R35 :**

| Localité R35 | Gares R35 rattachées |
|---|---|
| Vevey | VV, VVVI, GIL (historique H16-H22), CLIE (historique H16-H18) |
| Saint-Légier | HTV, CHTV, STLV, STLE, CHIZ |
| Blonay | CHBL, BLON, PRLZ, TUS, CHEV, BCHX, FAY, OND, LAL, PLEI |

---

## 3. Validation empirique post-implémentation

### Couverture de la classification par localité

Sur les 212 événements en `zone_directe` (PDFs 2015–2024) :

| Localité | Événements | % | Nature dominante |
|---|---|---|---|
| Vevey | 174 | 82.1 % | Festivals lacustres, marchés folkloriques, fêtes culturelles |
| Blonay | 28 | 13.2 % | Crémaillère, montagne, Pléiades, Désalpe, Léman Retro |
| Saint-Légier | 10 | 4.7 % | Semaine Internationale de Piano principalement |
| hors_r35 | **0** | **0.0 %** | Aucun événement zone directe non rattaché |

Le résultat `hors_r35 = 0` confirme que les 3 sous-chaînes couvrent l'intégralité des
événements zone directe répertoriés dans les PDFs sources sur la période 2015–2024.

Cas particulier résolu : `'Les Pléiades'` ne contient ni « vevey » ni « legier » ni « blonay »,
mais contient « pleiades » → correctement classé en `blonay`.

### Intégrité pipeline

| Indicateur | Valeur | Statut |
|---|---|---|
| `ml_dataset.parquet` lignes | 832 732 | Inchangé ✓ |
| Colonnes totales | 192 | +3 vs avant ✓ |
| Features `event_*` totales | 20 | +3 nouvelles ✓ |
| Warnings pipeline | 0 | ✓ |

---

## 4. Trade-offs et limites

**Limite 1 — Compteur Saint-Légier creux.**
`event_n_manifestations_st_legier_j` sera actif sur environ 8–10 jours par an (essentiellement
la Semaine Internationale de Piano, août). Le signal est faible en volume mais potentiellement
précis. Le SHAP révélera si la feature est exploitable malgré sa rareté.

**Limite 2 — Compteur Vevey dominant.**
Vevey concentre 82 % des événements zone directe. `event_n_manifestations_vevey_j` pourrait
être redondant avec `event_n_manifestations_zone_directe_j` (dominé par Vevey). Si cette
redondance est confirmée par le SHAP, la feature zonale pourra être retirée dans une itération
future sans modifier la dim ni le pipeline.

**Limite 3 — Localités rattachées non couvertes si absentes des PDFs actuels.**
La logique par sous-chaîne ne capte pas Hauteville, Chevalleyres, Fayaux, Tusinge si ces noms
apparaissent comme lieu principal dans un PDF futur. La validation empirique sur 2015–2024 montre
0 occurrence — le risque est nul sur le périmètre actuel. À surveiller lors de la mise à jour
annuelle de la dimension.

**Limite 4 — Effet de débordement Montreux non quantifié.**
La reclassification en `zone_indirecte` est justifiée conceptuellement (connectivité ferroviaire,
saturation hôtelière) mais l'ampleur empirique du débordement sur la R35 reste à mesurer via le
SHAP post-entraînement. Si `event_n_manifestations_zone_indirecte_j` émerge dans le top SHAP,
l'hypothèse sera validée empiriquement.

---

## 5. Cohérence opérationnelle (anti-leakage J-1)

Les 3 nouvelles features héritent du statut épistémique des features `event_*` existantes :

> Les manifestations sont planifiées à l'avance et publiées par Montreux Riviera Tourisme.
> Toutes les features sont déterminables à J-1. Aucune fuite temporelle.

---

## 6. Implémentation

| Artefact | Modification |
|---|---|
| `scripts/sources/build_dim_manifestations_riviera.py` | Mapping zonal Montreux modifié + fonction `classify_localite_r35` ajoutée + 3 colonnes localité dans la dim date + docstring module mis à jour |
| `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` | `_NEW_COLS` étendu avec 3 colonnes + 3 features `event_*` créées et typées |
| `data/dimension/dim_manifestations_riviera.parquet` | Reconstruit : 2 116 dates, 13 colonnes (dont 3 nouvelles) |
| `data/dimension/dim_manifestations_riviera_evenements.parquet` | Reconstruit : 632 événements, colonne `localite_r35` ajoutée |
| `data/processed/stage_03_manifestations.parquet` | Régénéré : 2 051 510 lignes × 82 colonnes (+3) |
| `data/processed/ml_dataset.parquet` | Régénéré : 832 732 lignes × 192 colonnes |

---

## 7. Références

- `scripts/sources/build_dim_manifestations_riviera.py` — implémentation zonale et localité
- `scripts/pipeline/add_manifestations_riviera_to_raw_stacked.py` — propagation stage 03
- ADR-027 — split temporel H22+H23 / H24 (périmètre du modèle concerné)
- ADR-028 — enrichissement features météo journalières (modification structurelle parallèle)
- PDFs sources : `data/external/evenements/Manifestations YYYY.pdf` (2015–2024)
