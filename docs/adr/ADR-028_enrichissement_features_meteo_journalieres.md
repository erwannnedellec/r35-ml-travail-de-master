---
id: ADR-028
ancien_id: ADR-29
date_decision: 2026-05-23
statut: actif
modifie: [ADR-022]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-028 — Enrichissement des features météo : agrégats journaliers J, J-1, J+1

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-022.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-23 |
| **Décideur** | Erwann Nedellec |
| **Notebooks de référence** | `notebooks/02d_diagnostic_features_meteo.ipynb` |
| **Note de décision** | `notes/02d_recap_meteo_pour_decision.md` |

---

## 1. Contexte

Le modèle de référence (H22-H23 → H24, R²=0.62) ne fait apparaître aucune feature `meteo_*`
dans le top 20 SHAP, malgré le profil touristique marqué de la R35 (segment Blonay → Les Pléiades).

Le diagnostic empirique du notebook `02d_diagnostic_features_meteo.ipynb` révèle deux limites
structurelles des 9 features `meteo_*_h` actuelles (cf. ADR-022) :

**Limite 1 — Granularité horaire ponctuelle.** Les features actuelles capturent la météo à l'heure
exacte du passage du train. Or les décisions touristiques (aller au lac, en montagne, skier) répondent
aux conditions journalières globales anticipées, pas à la valeur ponctuelle à l'heure de départ.
La médiane des heures de départ est ~14h sur les deux segments : un voyageur décide le matin
en se basant sur la météo attendue pour la journée, pas sur la valeur observée à 6h.

**Limite 2 — Corrélations faibles entre valeurs horaires et agrégats journaliers.**
Mesurées sur le dataset H22-H24, segment bas :

| Feature horaire actuelle | Agrégat journalier candidat | Corrélation Pearson |
|---|---|---|
| `meteo_temperature_h` | T° max journalière | **r = 0.956** (quasi-redondant) |
| `meteo_precipitation_mm_h` | Total précipitations j | **r = 0.472** (signal différent) |
| `meteo_ensoleillement_min_h` | Total ensoleillement j | **r = 0.582** (signal différent) |
| `meteo_vent_max_h` | Rafale max j | **r = 0.590** (signal différent) |

La variabilité intra-journalière du rayonnement global (std 199 W/m², range 576 W/m² sur VEV 2024)
justifie également l'ajout d'un agrégat journalier pour ce paramètre, absent des features actuelles.

---

## 2. Décision — 18 nouvelles features réparties en 4 niveaux

### Niveau 1 — Agrégats journaliers J, locaux (4 features)

| Feature | Calcul | Station |
|---|---|---|
| `meteo_temperature_max_j` | T° max du jour J (°C) | VEV ou CHD selon `spatial_segment` |
| `meteo_precip_total_j` | Σ précipitations du jour J (mm) | VEV ou CHD |
| `meteo_ensol_total_j` | Σ ensoleillement du jour J (min) | VEV ou CHD |
| `meteo_vent_max_j` | Rafale max du jour J (km/h) | VEV ou CHD |

### Niveau 2 — Agrégats journaliers J, destination (4 features)

Même calcul que le niveau 1, avec la station mappée sur la **gare destination du tronçon**
selon `base_sens` (identique à la logique existante des `meteo_destination_*_h`) :

| Feature | Station |
|---|---|
| `meteo_destination_temperature_max_j` | CHD (montant VV→PLEI) / VEV (descendant PLEI→VV) |
| `meteo_destination_precip_total_j` | idem |
| `meteo_destination_ensol_total_j` | idem |
| `meteo_destination_vent_max_j` | idem |

### Niveau 3 — Contexte temporel J-1 et J+1 (8 features)

Précipitations et ensoleillement uniquement (paramètres les plus discriminants pour les
arbitrages comportementaux « il a fait / fera beau ») :

| Feature | Calcul | Station |
|---|---|---|
| `meteo_precip_total_j_moins_1` | Σ précip J-1 (mm), local | `spatial_segment` |
| `meteo_ensol_total_j_moins_1` | Σ ensol J-1 (min), local | `spatial_segment` |
| `meteo_destination_precip_total_j_moins_1` | Σ précip J-1 (mm), destination | `base_sens` |
| `meteo_destination_ensol_total_j_moins_1` | Σ ensol J-1 (min), destination | `base_sens` |
| `meteo_precip_total_j_plus_1` | Σ précip J+1 (mm), local | `spatial_segment` |
| `meteo_ensol_total_j_plus_1` | Σ ensol J+1 (min), local | `spatial_segment` |
| `meteo_destination_precip_total_j_plus_1` | Σ précip J+1 (mm), destination | `base_sens` |
| `meteo_destination_ensol_total_j_plus_1` | Σ ensol J+1 (min), destination | `base_sens` |

### Niveau 4 — Rayonnement global (2 features)

Paramètre disponible à 100% dans VEV et CHD, absent des features actuelles, fort signal
intra-journalier :

| Feature | Calcul | Station |
|---|---|---|
| `meteo_rayon_global_moy_j` | Rayonnement global moyen du jour J (W/m²), local | `spatial_segment` |
| `meteo_destination_rayon_global_moy_j` | Rayonnement global moyen du jour J, destination | `base_sens` |

**Total : 18 nouvelles features.** Dataset ML passe de 9 à 27 features `meteo_*`.

---

## 3. Mapping spatial unifié (spatial_segment)

Toutes les features météo — horaires (`meteo_*_h`, stage_04) et journalières
(`meteo_*_j`, stage_04b) — utilisent **le même critère de rattachement à la station** :

### Features locales (niveaux 1, 3 et 4)

> **`spatial_segment == "haut"` → station CHD ; `spatial_segment == "bas"` → VEV**

`spatial_segment` est calculé en stage_03e : une ligne est `"haut"` dès qu'au moins une gare
du tronçon a `ordre > 10` (soit Lally et au-delà, où la crémaillère est engagée).

Ce critère opérationnel est retenu pour garantir la **cohérence sémantique entre les deux
familles de features météo** et simplifier l'argumentaire du modèle (une seule frontière VEV/CHD
pour les 27 features `meteo_*`).

**Note sur Blonay (BLON, 620 m, ordre = 10)** : lorsque Blonay est la gare haute d'un tronçon
(ex. STLE–BLON), `spatial_segment = "bas"` → VEV. Lorsqu'elle est la gare basse d'un tronçon
de crémaillère (BLON–PRLZ), `spatial_segment = "haut"` → CHD. Ce comportement est cohérent avec
la frontière opérationnelle de la ligne (changement de matériel roulant à Blonay).

### Mapping destination (niveaux 2, 3, 4)

La logique `base_sens` est conservée à l'identique des features horaires existantes :
- `"VV -> PLEI"` (train montant) → CHD
- `"PLEI -> VV"` (train descendant) → VEV

---

## 4. Disponibilité J-1 et statut de proxy (cohérence ADR-022)

Toutes les nouvelles features utilisent les observations météo historiques comme proxy
des prévisions disponibles à J-1 en production, selon le même statut épistémique que
les features horaires existantes (catégorie 2 — prévisionnelle, cf. ADR-022 §5).

**Agrégats J** : en entraînement, la météo du jour J est disponible (observations a posteriori).
En production, l'équivalent sont les **prévisions horaires MétéoSuisse** pour le jour J,
disponibles la veille à 8h (API ICON-CH2-EPS, paramètres vérifiés : `tre200dx`, `rka150p0`,
`sre000h0`, `fu3010h1`, `gre000h0`). Le même train/serve skew documenté en ADR-022 s'applique.

**Agrégats J-1** : disponibles à J-1 depuis les observations. Pas de skew sur J-1.

**Agrégats J+1** : en entraînement, disponibles a posteriori. En production,
prévisions MétéoSuisse pour J+1 disponibles à J-1 (horizon J+2 de la veille).

**Couverture temporelle confirmée** : VEV (2015-09-08 → 2025-12-31) et CHD (2012-02-08 → 2025-12-31)
couvrent intégralement le périmètre H22-H24. Pas de NaN structurel sur J-1 ni J+1.

---

## 5. Trade-offs et limites

- **18 features supplémentaires** : enrichissement substantiel ; l'analyse SHAP post-entraînement
  permettra d'identifier les features non-informatives à retirer dans une itération ultérieure.
- **Frontière VEV/CHD unique** : le critère `spatial_segment` correspond à la frontière opérationnelle
  de la ligne (crémaillère, changement de matériel), pas à la transition climatique réelle (~1 000 m).
  CHD reste une approximation pour PRLZ–FAY (661–972 m), acceptée au niveau prototypique.
- **J+1 sur les dernières journées H24** : NaN pour le 14 décembre 2024 (dernier jour H24 — pas de J+1
  dans la période de couverture). XGBoost gère nativement les NaN.

---

## 6. Paramètres reportés à une itération future

- Nébulosité (codes SMN `nprolohs`, `npromths`, `nprohihs`) : sémantique à clarifier
- Isotherme zéro (`zprfr0hs`) : à intégrer dans les données historiques d'abord
- Pictogramme MétéoSuisse journalier (`jp2000d0`) : table de correspondance des codes à documenter
- Features de variation et tendance (variation T° sur 3j, cumul neige 7j) : gain incertain,
  à évaluer après le prochain cycle SHAP

---

## 7. Implémentation

| Artefact | Action |
|---|---|
| `scripts/pipeline/add_meteo_journaliere_to_raw_stacked.py` | Nouveau stage 04b |
| `scripts/pipeline/paths.py` | Ajout `STAGE_04B_METEO_J` |
| `Makefile` | Chaînage `STAGE_04 → STAGE_04B → STAGE_06` |
| `CONTEXT.md` | Mise à jour section météo + table stages |

---

## Références

- Notebook `notebooks/02d_diagnostic_features_meteo.ipynb` — justification empirique complète
- Note `notes/02d_recap_meteo_pour_decision.md` — synthèse et recommandations
- ADR-022 — granularité horaire, mapping VEV/CHD, train/serve skew
- ADR-027 — split temporel H22-H23 / H24 (périmètre du modèle de référence)
