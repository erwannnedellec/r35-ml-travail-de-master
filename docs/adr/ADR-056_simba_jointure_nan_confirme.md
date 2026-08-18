---
id: ADR-056
ancien_id: ADR-CF13
date_decision: 2026-06-07
statut: révoqué
revoque_par: [ADR-061]
modifie: [ADR-041]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-056 — Jointure SIMBA : NaN tracé confirmé après investigation exhaustive

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-061.
> Décisions antérieures que ce document modifie : ADR-041.
> **Précision au gel.** Les variables `simba_*` dont ce document confirme la valeur manquante sont **retirées du modèle** par ADR-061.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — définitif |
| **Date** | 2026-06-07 |
| **Décideur** | Erwann Nedellec |
| **Supersède** | ADR-041 (`docs/adr/ADR-041_simba_refonte_horaire_h25.md`) |
| **ADRs liés** | ADR-026 (leakage SIMBA, lag N-1), ADR-044 (créneau×sens histo_), ADR-055 (STATPOP VVVI) |
| **Dataset de référence** | `ml_dataset.parquet` hash **0c0b7807** (post-correctif STATPOP VVVI, ADR-055) |
| **Modifications pipeline** | Aucune — documentation pure |

---

## Contexte

L'ADR-041 (2026-06-04) a établi que 46.6 % des observations H25 ont les features `simba_*` à NaN en raison de la refonte d'horaire CFF décembre 2024 : 52 trains sur 103 ont été renumérotés, leurs nouveaux numéros étant absents de SIMBA 2024 (millésime de référence pour H25, règle lag N-1 de l'ADR-026). L'Option A — NaN tracé — avait été retenue à titre conservatoire, en cohérence méthodologique avec le principe anti-leakage, mais sans validation empirique des alternatives.

Le présent ADR documente l'investigation complète conduite pour évaluer cinq voies alternatives avant d'acter définitivement la décision. Il remplace l'ADR-041 qui reste une référence historique mais n'est plus la décision en vigueur.

---

## Contraintes héritées (non réexaminées)

### Lag N-1 obligatoire — ADR-026

SIMBA FQkal est produit par la chaîne `AFZ (APC) → FRASY → HOP → calibration FQkal`. La corrélation entre SIMBA(N) et APC(N) est r = **0.97** sur R35 H24 (mesurée sur expansion OD → tronçon). Utiliser SIMBA de l'année courante pour prédire l'occupation de la même année constitue un leakage circulaire tautologique qui rendrait les métriques d'entraînement non représentatives des conditions de production.

**Règle maintenue sans exception** : pour une prédiction sur H(Y), seul SIMBA(Y-1) est autorisé — jamais SIMBA(Y).

Cette contrainte exclut d'emblée toute jointure utilisant SIMBA 2025 pour récupérer les 52 trains renumérotés H25. L'Option B de l'ADR-041 (jointure secondaire SIMBA 2025) reste invalide pour l'évaluation principale.

### Colonnes de traçabilité

Les colonnes `simba_source_depart` / `simba_source_arrivee` (introduites en ADR-041, convention cohérente avec ADR-039 v2 et ADR-040) sont **maintenues**.

| Valeur | Signification |
|---|---|
| `match_simba_n_minus_1` | Jointure réussie sur numéro de train, millésime N-1 |
| `manquant_simba_n_minus_1` | Aucun match (millésime N-1 indisponible ou train renuméroté) |

Ces colonnes permettent de stratifier les métriques H25 au moment du réentraînement final (cf. §Validation empirique).

---

## Profil de la couverture SIMBA H25

| Catégorie | Trains | Observations H25 | % |
|---|---|---|---|
| Trains conservés H24→H25 | 51 | 160 147 | 51.8 % |
| Trains renumérotés, absents de SIMBA 2024 | 52 | 143 867 | 46.5 % |
| Couverture partielle (train 1416) | 1 | ~2 000 | 0.6 % NaN internes |
| **Total H25** | **103** | **~308 000** | — |

La distribution est stable temporellement (≈ 46 % NaN sur tous les mois H25) et asymétrique par sens : sens VV→PLEI ouvrables concentre 54–64 % de NaN (trains de pointe du matin majoritairement renumérotés).

---

## Investigation — cinq voies testées

### Voie 1 — Jointure par numéro de train (état initial ADR-041)

**Grain** : (millesime × numero_train × gare_min × gare_max)

**Résultat** : couverture H25 = 53.4 % (52 trains renumérotés absents de SIMBA 2024 → 46.6 % NaN). Pour H23 et H24, la couverture reste 94–96 % (quelques trains nouveaux par renouvellement annuel mineur, géré nativement par XGBoost).

La stabilité inter-années (2022 vs 2023, proxy du saut inter-millésimes) des features existantes au grain train×tronçon (L0) :

| Feature | W-MAE L0 (pondéré volume) | Corrélation inter-millésimes | Seuil 0.05 |
|---|---|---|---|
| `simba_part_ga` | **0.094** | 0.14 | ✗ |
| `simba_part_mobilis` | **0.131** | 0.55 | ✗ |
| `simba_part_intra_r35` | **0.211** | 0.24 | ✗ |
| `simba_part_corresp_amont` | **0.130** | 0.63 | ✗ |
| `simba_part_corresp_aval` | **0.093** | — | ✗ |
| `simba_part_billet_hta` | **0.070** | — | ✗ |
| `simba_part_spar` | 0.014 | −0.05 (variance nulle) | ✓ (trivial) |
| `simba_part_premiere_classe` | **0.020** | — | ✓ |

Seules les features à quasi-variance nulle (spar) ou à signal très faible (premiere_classe) passent le seuil. Les quatre features informatives (GA, Mobilis, intra R35, correspondances) échouent.

---

### Voie 2 — Agrégation au grain tronçon (L1, tous trains agrégés)

**Grain** : (millesime × gare_min × gare_max) — tous les trains du même tronçon fusionnés

**Raisonnement** : en agrégeant sur tous les trains, le dénominateur devient très grand et le profil plus stable.

**Résultat** :

| Feature | W-MAE L1 | R² géographique | Bilan |
|---|---|---|---|
| `simba_part_ga` | **0.038** (stable ✓) | **0.003** — quasi-nul | Stable mais plat |
| `simba_part_mobilis` | **0.035** (stable ✓) | **0.563** — fort | Stable ET discriminant |
| `simba_part_intra_r35` | 0.061 (limite) | 0.230 — moyen | Borderline |
| `simba_part_corresp_amont` | 0.208 | — | Pire qu'à L0 |

La stabilité de `part_ga` à L1 est **illusoire** : le signal géographique est quasi-inexistant (R² = 0.003, range inter-tronçons = 2.8 pp, toutes sections à ≈ 12 %). En agrégeant tous les trains du même tronçon, on obtient une constante — stable parce qu'informationnellement vide. Le signal GA était train-spécifique, pas géographique.

Pour les correspondances, L1 est pire que L0 (0.208 vs 0.130) : les correspondances sont un attribut de service spécifique à chaque train, pas une propriété géographique invariante du tronçon.

**Verdict voie 2** : stabilité atteinte au prix de la discriminance pour GA — la jointure L1 ne fournit pas de signal utile.

---

### Voie 3 — Décomposition numérateur/dénominateur (Kitagawa)

**Question** : l'instabilité des parts vient-elle d'un artefact de ratio (dénominateur variable) ou d'une dérive réelle de la demande (numérateur) ?

**Méthode** : pour chaque cellule commune entre SIMBA 2022 et 2023, décomposer l'erreur en :
- Effet **dénominateur** : fixer le numérateur (voyageurs GA) à la valeur 2022, appliquer le dénominateur (total) de 2023 → erreur attributable au seul volume global
- Effet **numérateur** : appliquer le numérateur 2023 au dénominateur 2022 → erreur attributable à la seule composition de clientèle

**Résultat pour `part_ga`** :

| Composante | Contribution |
|---|---|
| Dénominateur seul (volume global) | corrélation inter-millésimes ≈ **0.85** — stable |
| Numérateur seul (voyageurs GA absolus) | **76 % de l'erreur totale** |

**Verdict voie 3** : l'instabilité est une dérive comportementale réelle — le nombre absolu de voyageurs GA varie significativement d'une année à l'autre sur les mêmes trains. Ce n'est pas un artefact de mise en pourcentage. Les hypothèses "ratio instable mais signal stable" sont **réfutées**.

---

### Voie 4 — Signature horaire par créneau de proximité (creneau_anchor_30)

**Hypothèse** : le profil tarifaire par créneau (matin = pendulaires GA/Mobilis, midi = occasionnels billets) constitue une signature stable inter-années, robuste aux refontes d'horaire puisqu'un nouveau train à 07h11 porte le même type de clientèle qu'un ancien train à 07h11.

**Construction de creneau_anchor_30** (code : `add_features_to_raw_stacked.py`, ligne 209) : pour chaque train H22-H24, extraire le temps de départ en minutes depuis minuit depuis le format `{num}_{HHhMM}` du `service_id`. Les temps uniques constituent une table d'anchors par (sens × type_jour). Chaque nouvelle observation reçoit l'anchor le plus proche à ±30 min.

**Bijectivité découverte** : le grain (creneau_anchor_30 × tronçon × sens) est **bijectif avec le grain train** — 1 062 / 1 062 cellules contiennent exactement 1 train SIMBA. Explication : les anchors sont les temps de départ exacts de chaque train H22-H24 ; deux trains consécutifs à 07h11 et 07h26 reçoivent des anchors distincts (431 et 446 minutes). L'agrégation n'a jamais lieu. Le créneau de proximité est un réétiquetage du train, pas une agrégation temporelle.

**Vérification de l'hypothèse de signal horaire** (SIMBA 2024, pondéré volume) :

| Tranche | GA | Mobilis |
|---|---|---|
| Matin peak (06h30–08h30) | 10.4 % | 68.7 % |
| Midi (11h–13h30) | 9.6 % | 68.0 % |
| Soir peak (16h30–19h30) | 12.5 % | 66.8 % |
| **Soirée (> 19h30)** | **16.5 %** | 61.0 % |

R²(tranche horaire) pour GA = 12.4 %. La signature "matin = pendulaires GA élevés" est infirmée : la part GA est maximale en soirée (16.5 %), pas au matin peak (10.4 %). Mobilis domine à toute heure (60–70 %), ce qui atténue la discrimination pendulaire/occasionnel caractéristique des lignes urbaines. La R35/MOB a un profil Mobilis structurel homogène.

**Résultat stabilité** (W-MAE créneau×tronçon vs L0) :

| Feature | W-MAE créneau proximité | W-MAE L0 | Gain |
|---|---|---|---|
| `part_ga` | 0.0929 | 0.0944 | +1.6 % — gain nul |
| `part_mobilis` | 0.1310 | 0.1315 | +0.4 % — gain nul |

**Verdict voie 4** : la bijectivité est un **artefact de construction de la clé** (pas une propriété de la ligne, qui a bien une cadence de 15 min aux heures de pointe). Le test n'a pas évalué la vraie signature temporelle — il a recouru au test L0 sous un label différent. Le grain créneau-proximité n'agrège jamais deux trains, donc ne peut pas améliorer la stabilité.

---

### Voie 5 — Agrégation par tranches fixes de 30 min (vraie agrégation)

**Motivation** : la voie 4 a identifié l'artefact. La vraie agrégation temporelle consiste à affecter chaque train à une fenêtre fixe (plancher à la demi-heure la plus proche : 07h00–07h30, 07h30–08h00…) indépendamment de son numéro. Aux heures de pointe, deux trains consécutifs à 15 min d'intervalle tombent dans la même fenêtre : vraie agrégation, volume doublé, profil moyenné.

**Structure des données** :

- Sur H24 VV→PLEI ouvrables : **14 fenêtres à 2 trains SIMBA** (aux heures de pointe AM 05h30–08h30 et PM 15h30–19h00)
- **63.7 % du volume SIMBA total** est concentré dans ces fenêtres peak (11 897 / 18 670 DWV)

**Résultats stabilité** (SIMBA 2022 vs 2023, 100 % de trains matchés) :

| Feature | W-MAE L0 | W-MAE fixe global | W-MAE fixe **peak** | Amélio peak | Seuil 0.05 |
|---|---|---|---|---|---|
| `simba_part_ga` | 0.094 | 0.0824 | **0.0570** | −39 % | ✗ (+14 % au-dessus) |
| `simba_part_mobilis` | 0.131 | 0.1056 | **0.0770** | −41 % | ✗ |
| `simba_part_billet_hta` | 0.070 | 0.0330 | **0.0217** | −69 % | **✓** |
| `simba_part_intra_r35` | 0.211 | 0.1582 | **0.1240** | −41 % | ✗ |
| `simba_part_corresp_amont` | 0.130 | 0.0891 | **0.0460** | −65 % | **✓** |
| `simba_part_corresp_aval` | 0.093 | 0.0832 | **0.0893** | −4 % | ✗ |
| `simba_part_premiere_classe` | 0.020 | 0.0354 | **0.0281** | (dégradé) | ✓ (trivial) |

**Discriminance confirmée** au grain tranche-fixe :

| Feature | R²(fenêtre) | R²(géographique) |
|---|---|---|
| `ga` | 0.41 | 0.01 |
| `mobilis` | 0.37 | 0.28 |
| `intra_r35` | 0.46 | 0.01 |
| `corresp_amont` | 0.33 | 0.003 |

La variation est essentiellement temporelle — le signal existe.

**Décomposition bruit/dérive aux fenêtres peak** :

L'amélioration de 39 % sur GA (0.094 → 0.057) est réelle : doubler le volume agrégé réduit effectivement le bruit de ratio. Mais la décomposition numérateur/dénominateur confirme que la dérive comportementale du numérateur (variation absolue des voyageurs GA d'une année à l'autre) **domine toujours après agrégation** et absorbe la majorité du gain potentiel. Le résidu de 0.057 est de la dérive genuinement non récupérable par agrégation.

**Verdict voie 5** : l'agrégation par tranches fixes est la meilleure voie testée — amélioration de 39–65 % sur les fenêtres peak. Elle rend stables ET discriminantes les features secondaires (`corresp_amont` W-MAE 0.046, `billet_hta` 0.022). Mais les deux features à plus fort poids SHAP — GA (0.057) et Mobilis (0.077) — **restent au-dessus du seuil 0.05**, la dérive comportementale inter-années dominant et résistant à l'agrégation double volume.

---

## Tableau de synthèse des cinq voies

| Voie | Grain | Stable GA ? | Discriminant GA ? | Couverture H25 | Verdict |
|---|---|---|---|---|---|
| 1 — Numéro de train (L0) | train × tronçon | ✗ (0.094) | Oui | 53.4 % | Instable — état initial |
| 2 — Tronçon (L1) | tronçon | ✓ (0.038) | ✗ (R²=0.003) | ~100 % potentiel | Stable mais plat — rejeté |
| 3 — Kitagawa | décomposition | — (76 % num) | — | — | Dérive réelle confirmée |
| 4 — Créneau proximité | anchor unique ≡ train | ✗ (0.093) | Partiel | 53.4 % | Artefact bijectif — rejeté |
| 5 — Tranches fixes | fenêtre 30 min × tronçon | ✗ GA 0.057 (**−39 %**) | Oui (R²=0.41) | ~100 % potentiel | Meilleure voie mais GA échoue |

---

## Décision

**Option A maintenue : NaN tracé intégral pour toutes les features SIMBA sur les trains renumérotés H25.**

### Pourquoi pas l'option hybride ?

La voie 5 rend stables et discriminantes `corresp_amont` et `billet_hta` sur les fenêtres peak. Une option hybride serait techniquement possible : jointure par tranches fixes pour ces deux features, NaN maintenu pour GA et Mobilis.

Cette option est **rejetée** pour les raisons suivantes :

1. **Rapport bénéfice/complexité défavorable** : SIMBA représente environ 5 % de l'importance SHAP globale du modèle. `corresp_amont` et `billet_hta` sont en bas du classement interne des features SIMBA. Le gain de couverture sur deux features secondaires ne justifie pas une logique de jointure hétérogène par-feature dans le pipeline.

2. **Cohérence de la traçabilité** : avec une jointure hybride, la colonne `simba_source_*` aurait une sémantique ambiguë (certaines features seraient remplies par tranches-fixes, d'autres resteraient NaN). La convention `match/manquant` perdrait son interprétation univoque.

3. **Défendabilité** : le NaN intégral est transparent et auditables. Le routage XGBoost est appris de façon cohérente sur l'ensemble des features SIMBA. Une jointure hybride par-feature introduirait une hétérogénéité dans le signal qui complexifie l'interprétation des SHAP sans bénéfice mesurable sur les métriques attendues (ΔR² < 0.01 sur le segment critique haut).

### Gestion native par XGBoost

XGBoost apprend une direction de routage par défaut pour les NaN via la pression du gradient. Sur les features SIMBA, ce routage est calibré sur les **100 % de NaN de H22** (SIMBA 2021 indisponible, ADR-026). Il est donc déjà stable, robuste, et représentatif d'une proportion élevée de NaN — contrairement à une feature dont les NaN seraient rares et accidentels.

---

## Limites structurelles à documenter

### SIMBA sans type_jour

SIMBA FQkal produit un profil annuel moyen par numéro de train, **indifférencié par type de jour** (ouvrable, samedi, dimanche). Un train aura le même `simba_part_ga` un lundi et un dimanche. Cette limite est **commune à toutes les variantes de jointure** — elle s'applique identiquement aux voies 1 à 5 et ne peut pas être contournée sans que SBB révise le format de publication. Le modèle compense partiellement via les features `histo_*` (lags APC par créneau × type_jour, discriminants) et `cal_*` (calendrier).

### Couverture H25

46.6 % des observations H25 sans signal SIMBA. Le modèle dispose de ses 167 autres features actives pour ces observations. L'impact est mesurable et mesuré au §Validation empirique ci-dessous.

---

## Finding méthodologique généralisable (résultat de thèse)

> **La jointure par créneau ou agrégation temporelle ne transfère correctement que des quantités stables au grain où le créneau procure une vraie agrégation.**

L'investigation distingue deux cas :

- **`histo_*` (lags APC)** : la jointure par créneau réussit car la charge d'un créneau horaire (nombre de voyageurs) est **stable inter-années** sur la même ligne. Le créneau agrège plusieurs jours d'observation du même service, réduisant le bruit tout en préservant le signal.

- **Features SIMBA (profils tarifaires)** : la jointure par créneau échoue car la composition de clientèle (proportion GA, Mobilis) **dérive réellement entre années** — dérive comportementale confirmée par la décomposition Kitagawa (76 % du numérateur). L'agrégation de deux trains par fenêtre fixe réduit le bruit de 39–65 % mais ne supprime pas la dérive sous-jacente, qui reste supérieure au seuil d'acceptabilité pour les features informatives.

La condition de succès d'une jointure temporelle est donc que **la quantité jointe soit stable au grain agrégé**. Cette condition est vérifiable empiriquement (W-MAE inter-millésimes, décomposition Kitagawa) avant toute implémentation, et devrait systématiquement précéder toute décision d'ingénierie de features dans les projets ML transport.

---

## Validation empirique — réentraînement final

Conduire au moment de l'évaluation H25 :

1. **Stratification par `simba_source_depart`** :
   - Métriques sur `match_simba_n_minus_1` (51.8 % de H25)
   - Métriques sur `manquant_simba_n_minus_1` (46.5 % de H25)
   - Si ΔR² < 0.01 entre les deux sous-populations : absence de SIMBA sur les renumérotés sans biais — **Option A définitivement validée**
   - Si ΔR² > 0.02 : documenter en limite quantifiée dans le mémoire

2. **SHAP des features `simba_*` sur H25** : confirmer que le rang reste dans la moitié inférieure (cohérence ADR-036). Une remontée signalerait un biais de signal.

3. **Analyse de sensibilité (annexe)** : entraîner un modèle avec jointure secondaire SIMBA 2025 pour les 52 trains renumérotés ; quantifier l'écart de métriques. Si ΔR² < 0.005, valide rétrospectivement l'Option A et documente le coût réel du respect du principe N-1.

---

## Conséquences

- `add_simba_to_raw_stacked.py` : **aucune modification**
- `dim_simba_r35.parquet` : **aucune modification**
- `ml_dataset.parquet` hash **0c0b7807** : **inchangé**
- Colonnes `simba_source_*` : **maintenues** pour la stratification
- ADR-041 : supersédé — voir présent ADR pour la décision en vigueur

---

## Numérotation ADR

- ADR-055 — Correction Voronoï STATPOP VVVI (2026-06-07) — pas de collision
- **ADR-056 — présent ADR** — SIMBA jointure NaN définitif
- ADR-057 — Dénivelé tronçon spatial — pas de collision

---

## Références

- `scripts/pipeline/add_simba_to_raw_stacked.py` — jointure actuelle, inchangée
- `scripts/pipeline/add_features_to_raw_stacked.py`, ligne 209 — construction `creneau_anchor_30` (proximité)
- ADR-026 (`docs/adr/ADR-026_integration_simba_fqkal_lag_n_moins_1.md`) — leakage r=0.97, lag N-1
- ADR-041 (`docs/adr/ADR-041_simba_refonte_horaire_h25.md`) — décision NaN tracé initiale, supersédé
- ADR-044 — créneau×sens pour `histo_*` (contexte comparatif)
- Données : `data/external/simba/zuginout_MOB_2023.csv`, `zuginout_MOB_2024.csv`
- Données : `data/dimension/dim_simba_r35.parquet` (4 239 lignes, millésimes 2022–2025)
- Notebooks : `02_data_understanding_apc.ipynb`, `SYNTHESE_modele_R35_evaluation_complete.ipynb`
