---
id: ADR-044
ancien_id: ADR-CF01c
date_decision: 2026-06-05
statut: amendé
amende_par: [ADR-062]
modifie: [ADR-009, ADR-037, ADR-042]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-044 — Ajout de `base_sens` à la clé de groupement créneau

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-062.
> Décisions antérieures que ce document modifie : ADR-009, ADR-037, ADR-042.
> **Précision au gel.** Le §Décision publie une clé à **trois** termes sous le titre « clé de
> groupement finale ». Ce n'est pas l'état au gel : ADR-062 y a ajouté le tronçon. La clé en
> vigueur dans le pipeline canonique (`scripts/pipeline/add_features_to_raw_stacked.py`,
> `GROUP_KEYS`) compte **cinq** termes : `[base_sens, creneau_anchor_30, cal_type_jour_3classes,
> id_gare_depart_bpuic, id_gare_arrivee_bpuic]`. `base_sens` y figure toujours, en première
> position, et le créneau ancré reste à ±30 min (`CRENEAU_LARGEUR_MIN = 30`). Le mot « finale »
> du §Décision se lit « finale à la date du 2026-06-05 ».
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Accepté — pipeline régénéré (hash intermédiaire 1a53590f → canonique final `11b58391`, 2026-06-05)  
**Décideur** : Erwann Nédellec  
**Lié à** : ADR-042 (créneau ±30), ADR-043 (simulation RF-1), étape 1ter

---

## Problème identifié

La clé de groupement créneau retenue à l'étape 1 était :
```python
GROUP_KEYS = ["creneau_anchor_30", "cal_type_jour_3classes"]
```

Cette clé **ne distingue pas le sens de circulation**. Un train montant (VV → Pléiades) à 08h30 et un train descendant (Pléiades → VV) à 08h35 se retrouvent dans le même groupe, avec des régimes de charge opposés (montée matinale forte, descente matinale faible).

### Preuve empirique (Tâche 1)

| Dimension | Orientée ? | Preuve |
|-----------|-----------|--------|
| `horaire_troncon_tgl` | **Non** — constante 0 | Toutes les 2.36 M lignes de stage_08 valent 0 |
| `(id_gare_depart, id_gare_arrivee)` | **Oui** | 0 tronçon sur 43 a deux directions |
| `horaire_service_id_complet` (ADR-037) | **Oui** implicite | 0 service sur 147 span les deux directions |
| Créneau étapes 1/1bis `[cren, tj]` | **Non** | 98 % des VV→PLEI ont un PLEI→VV à ±30 min |

ADR-037 était correct car `service_id` sépare implicitement les directions. Le créneau sans `base_sens` introduit un mélange de régimes incompatibles.

---

## Solution

Ajouter `base_sens` aux GROUP_KEYS :

```python
GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]
```

`horaire_troncon_tgl` est retiré de la liste (constante sans valeur discriminante). `base_sens` assure la séparation directionnelle explicite (VV → PLEI et PLEI → VV dans des groupes distincts).

**Note** : `base_sens` est redondant avec `(id_gare_depart, id_gare_arrivee)` dans les données (chaque tronçon orienté a un seul sens), mais il est préférable de l'inclure explicitement dans la clé pour la lisibilité et la robustesse.

---

## Impact sur la couverture H25 (Tâche 2)

La couverture **ne change pas** en ajoutant `base_sens` :

| Segment | ≤ 30 min SANS sens | ≤ 30 min AVEC sens |
|---------|-------------------|-------------------|
| Global  | 98.2 % | **98.2 %** |
| Bas     | 100.0 % | **100.0 %** |
| Haut    | 93.1 % | **93.1 %** |

Raison : le `troncon_id = (gare_depart, gare_arrivee)` encode déjà la direction dans l'analyse de couverture. Les anchors sont naturellement par direction, le filtre `base_sens` n'élimine aucun match.

---

## Impact sur la performance WF (Tâche 3)

Re-vérification avec la clé corrigée `[base_sens, creneau_30, type_jour]`, Fold2 H22+H23→H24 :

| Modèle | Clé GROUP | PR-AUC haut | IC 95 % | Rappel@WF |
|--------|-----------|-------------|---------|-----------|
| B_ADR39 | [annee, sid, tj] | 0.123 | [0.084–0.190] | 11.5 % |
| B_cren30 (step 1, sans sens) | [cren, tj] | 0.112 | [0.075–0.168] | 13.5 % |
| **B_cren30_SENS (step 1ter)** | **[sens, cren, tj]** | **0.152** | **[0.095–0.221]** | **13.5 %** |

**Simulation masquage H24 (Tâche 3)** :

| Stratégie | PR-AUC haut | IC 95 % | Rappel@WF |
|-----------|-------------|---------|-----------|
| (a) service_id × sens, froid | 0.148 | [0.092–0.213] | 13.5 % |
| (b) créneau × sens | 0.152 | [0.095–0.221] | 13.5 % |

**Observations** :
1. **Neutralité de la simulation confirmée** avec sens — IC (a)/(b) superposés
2. **B_cren30_SENS au moins équivalent à B_ADR39** sur WF Fold2 (0.152 vs 0.123) — tendance favorable non significative : les IC chevauchent largement ([0.095–0.221] vs [0.084–0.190]), aucune amélioration ne peut être affirmée depuis les données d'entraînement seules
3. La version non orientée (step 1 sans sens, 0.112 `[0.075–0.168]`) mesure plus bas que la version orientée (0.152 `[0.095–0.221]`), mais les IC se chevauchent sur `[0.095–0.168]` et chaque estimation ponctuelle tombe dans l'IC de l'autre : l'écart est une **association compatible avec une baisse** due au mélange directionnel, sans qu'une dégradation puisse être affirmée — le même critère qu'à l'observation 2. La justification retenue pour l'ajout de `base_sens` est donc **structurelle et non métrique** : sans le sens, le créneau ±30 min regroupe par construction des régimes de charge opposés
4. **Anti-fuite** : H22+H23 corrélation A/B = 1.0000 — features training identiques

---

## Décision

**Clé de groupement finale pour les features `histo_*`** :

```python
GROUP_KEYS = ["base_sens", "creneau_anchor_30", "cal_type_jour_3classes"]
```

| Élément | Décision | Raison |
|---------|----------|--------|
| `horaire_troncon_tgl` | **Retiré** | Constante 0, sans valeur discriminante |
| `horaire_annee_horaire` | **Retiré** | Historique cross-années voulu (ADR-042) |
| `base_sens` | **Ajouté** | Sépare les directions opposées |
| `creneau_anchor_30` | **Conservé** | Ancrage créneau ±30 min (ADR-042) |
| `cal_type_jour_3classes` | **Conservé** | Séparation ouvrable/samedi/dimanche (ADR-037) |

### Apport de la décision
- **Correction du mélange directionnel** (justification structurelle principale) : VV→PLEI et PLEI→VV dans des groupes séparés — le mélange corrompait le signal historique
- **Au moins équivalent à ADR-037** sur le train : tendance favorable non significative (IC chevauchants), pas d'amélioration prouvée
- Justifié structurellement par la correction de l'échec `service_id` sur refonte d'horaire (trains renumérotés H25 absents de H22-H24 → signal histo_* perdu avec l'ancienne clé)
- **Neutralité simulation** maintenue avec sens

### Limitations
- Mêmes que ADR-042 et ADR-043 : RF-1 non démontré depuis le train (limitation structurelle, bénéfice attendu uniquement sur H25), couverture haut 93.1 % à ±30 min

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01ter_sens_creneau.ipynb` | Notebook complet 3 tâches |
| `consolidation_finale/outputs/etape_01ter_ecarts_avec_sens.csv` | Couverture par (tronçon, sens, type_jour) |
| `consolidation_finale/outputs/etape_01ter_wf_results.csv` | WF Fold2 + simulation masquage avec sens |
| `consolidation_finale/figures/etape_01ter_resultats.png` | WF et simulation comparaison |
| `consolidation_finale/figures/etape_01ter_synthese.png` | Tableau récapitulatif étapes 1→1ter |
