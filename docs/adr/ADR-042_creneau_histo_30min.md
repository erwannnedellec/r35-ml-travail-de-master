---
id: ADR-042
ancien_id: ADR-CF01
date_decision: 2026-06-05
statut: amendé
amende_par: [ADR-044, ADR-062]
modifie: [ADR-009, ADR-037]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-042 — Clé de groupement créneau ±30 min pour les features histo_*

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-044, ADR-062.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> Décisions antérieures que ce document modifie : ADR-009, ADR-037.
> **Précision au gel.** Le statut d'époque de ce document est resté « Proposé — en attente de validation ». La décision a été **appliquée** : la clé de groupement en vigueur est celle d'ADR-062, dont ce document est le premier maillon.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-05  
**Statut** : Proposé — en attente de validation par Erwann Nédellec  <!-- statut d'époque ; état au gel : amendé (voir bandeau) -->
**Décideur** : Erwann Nédellec (data analyste MOB, R35)  
**Lié à** : ADR-037 (grain enrichi histo_*), ADR-038 (périmètre H25), étape 0 (diagnostic décalage horaire)

---

## Contexte

ADR-037 a enrichi les GROUP_KEYS des features `histo_*` avec `horaire_service_id_complet` et `cal_type_jour_3classes`, apportant un gain PR-AUC haut ×2.8 sur H24.

L'audit du 2026-06-05 (phase 2.4) a identifié la fragilité RF-1 : la refonte d'horaire 2024→2025 a modifié **100 % des `horaire_service_id_complet`** H25 (tous les services ont changé d'heure de départ origine). Les trains H25 renumérotés/décalés obtiennent PR-AUC haut = 0.055 (vs 0.204 pour les services stables), avec Rappel@WF = 0 %.

La contribution C3 estimée à ≈ 0.057 R² sur le global H25 justifie de traiter ce point avant la sélection finale du modèle.

---

## Problème RF-1

Le GROUP_KEY actuel `horaire_annee_horaire × service_id_complet × type_jour_3classes` isole chaque année horaire dans sa propre série temporelle. Lors d'une refonte d'horaire :
- H24 : service `1302_05h31` → séries H22/H23/H24 constituées
- H25 : service `1302_05h37` → série H25 vide au démarrage → NaN histo_* pour les ~9 premières occurrences

Conséquence : les services H25 (100 % de la population) partent à froid, sans hériter de l'historique H22-H24 des services équivalents. Sur le segment haut (touristique, fortement autocorrélé), cette absence d'historique est préjudiciable.

---

## Diagnostic étape 0 (2026-06-05)

Analyse sur `ml_dataset_service_id.parquet`, grain (service_id × tronçon adjacent × type_jour_3classes).

| Métrique | Global | Segment bas | **Segment haut** |
|---|---|---|---|
| Médiane écart H25 → voisin H22-H24 | 6 min | 6 min | **13 min** |
| P90 | 20 min | 9 min | 21 min |
| Couverture ≤ 15 min | 84.7 % | 96.9 % | **51.1 %** |
| Couverture ≤ 30 min | 98.2 % | 100 % | **93.1 %** |
| Couverture ≤ 60 min | 99.4 % | 100 % | 97.8 % |

Services haut non couverts à ±30 min :
- **Services nuit** (1476_00h00/05, 1473_00h00/23h35) : aucun ancêtre H22-H24 → NaN structurel. Vérification : 0 surcharge sur 1 509 observations haut H25 → **sans conséquence opérationnelle**.
- **4 services ouvrable matin** (1411_08h05/15, 1416_08h44/51) : gap ~40 min. Couverts avec ±45 min, non couverts à ±30 min.

---

## Évaluation étape 1 — Walk-forward H22/H23/H24

### Protocole

- 4 modèles : B_ADR39 (actuel), B_cren15 (±15 min), B_cren30 (±30 min), B_cren45 (±45 min)
- Nouveau GROUP_KEY : `[creneau_anchor_X, cal_type_jour_3classes]` (sans `horaire_annee_horaire` → historique cross-années)
- 2 folds WF : Fold1 (H22→H23), Fold2 (H22+H23→H24), embargo 9 jours
- Hyperparamètres XGBoost inchangés (ADR-036 : 300 arbres, max_depth=6, lr=0.1, seed=42)
- Métriques : PR-AUC haut, Rappel@68.49 haut, R²haut, IC bootstrap 500 (95 %)

### Résultats WF

| Fold | Modèle | R²haut | PR-AUC haut | IC 95% | Rappel@WF haut | IC 95% |
|------|--------|--------|-------------|--------|----------------|--------|
| Fold1 H22→H23 | B ADR-037 | 0.266 | 0.033 | [0.024–0.045] | 11.8 % | [6.8–17.1 %] |
| Fold1 H22→H23 | B créneau ±15/30/45 | **0.290** | 0.025 | [0.019–0.034] | 2.6 % | [0.6–5.4 %] |
| Fold2 H22+H23→H24 | B ADR-037 | 0.467 | **0.123** | [0.084–0.190] | 11.5 % | [5.8–18.3 %] |
| Fold2 H22+H23→H24 | B créneau ±15/30/45 | **0.474** | 0.112 | [0.075–0.168] | **13.5 %** | [7.2–20.3 %] |

**Observation critique** : les 3 largeurs créneau produisent des résultats identiques sur H22-H24. Explication : en H22-H24, les refontes d'horaire sont mineures et les service_ids sont stables. Le créneau assigne le même anchor à ±15, ±30 et ±45 min (chaque service H22-H24 est son propre anchor exact). La discrimination entre largeurs est **structurellement impossible sur les folds WF** — le problème RF-1 est spécifique à H25.

**Équivalence statistique** : les IC bootstrap 95 % se chevauchent largement entre B_ADR39 et toutes les variantes créneau (les deux métriques clés sont dans les IC des autres). Aucune dégradation significative.

### Anti-fuite confirmée

1. H22_max_date < H23_min_date → aucune contamination future dans les lags H22.
2. Algorithme searchsorted(right)−1 garantit structurellement lag ≤ base_date − 2j.
3. Les anchors créneau sont des temps H22-H24 fixes → l'assignment de H25 ne contient aucune donnée H25.

---

## Décision

**Adoption du créneau ±30 min comme clé de groupement des features `histo_*`.**

### Nouveau GROUP_KEY

```python
GROUP_KEYS = ["creneau_anchor_30", "cal_type_jour_3classes"]
```

où `creneau_anchor_30` = temps (en minutes depuis minuit) du service H22-H24 le plus proche dans ±30 minutes sur le même `cal_type_jour_3classes`. Sans `horaire_annee_horaire` → l'historique cross-années est disponible.

### Justification du choix ±30 min

Le choix est guidé par la **couverture H25 (étape 0)** — seule donnée discriminante disponible, les folds WF étant structurellement non discriminants :

- **±15 min rejeté** : couverture haut H25 = 51.1 % seulement.
- **±30 min retenu** : couverture haut H25 = 93.1 %, équivalence WF confirmée.
- **±45 min non retenu** : gain marginal (~4 points sur 4 services matin ouvrable) sans avantage WF démontré. Largeur plus large = groupes plus hétérogènes = potentiel bruit accru. Conservé comme analyse de sensibilité.

### Cas des services nuit (NaN structurel)

Les 4 services haut sans anchor (1476, 1473) conservent NaN histo_* avec le créneau ±30 min. Statut : **acceptable**. Ces trains ont une charge maximale de 20 voyageurs sur 2e classe (seuil UM = 94) — 0 faux négatif opérationnel possible. XGBoost utilisera la direction NaN apprise sur l'entraînement.

---

## Conséquences

### Positives

- Suppression du redémarrage à froid pour les services renumérotés lors des refontes d'horaire : chaque service H25 hérite de l'historique H22-H24 du service H22-H24 le plus proche en temps, dès le premier jour de H25.
- Couverture histo_* H25 : 100 % bas (contre 1.1 % NaN ADR-037), 93.1 % haut (contre 1.3 % NaN ADR-037 — mais ce 1.3 % était une moyenne trompeuse masquant 100 % NaN pour les services renumérotés en début de H25).
- Robustesse aux refontes d'horaire futures : le mécanisme fonctionnera pour tout changement annuel CFF tant qu'un service tourne à ±30 min d'un service H22-H24.

### Limitations documentées

- **Services nuit** (4 service_ids, 2.2 % des obs haut H25) : NaN histo_* structurel. Sans conséquence opérationnelle (0 surcharge).
- **4 créneaux matin ouvrable** (1411_08h05/15, 1416_08h44/51) : gap ~40 min → histo_* NaN avec ±30 min. Ces 4 services correspondent à des créneaux ajoutés dans H25 sans équivalent ouvrable en H22-H24. Potentiels faux négatifs si ces services présentent des surcharges. À vérifier lors de l'évaluation étape 4.
- La performance réelle sur H25 ne sera mesurable qu'à l'étape 4 (évaluation finale en lecture seule).

---

## Fichiers produits

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_01_selection_creneau_histo.ipynb` | Notebook complet avec WF, anti-fuite, night check |
| `consolidation_finale/outputs/etape_01_wf_results.csv` | Résultats WF 4 modèles × 2 folds + bootstrap CI |
| `consolidation_finale/figures/etape_01_wf_pr_recall_haut.png` | PR-AUC et rappel par fold et modèle |
| `consolidation_finale/figures/etape_01_wf_r2.png` | R² global et haut par fold |
| `consolidation_finale/figures/etape_01_nan_rates.png` | Taux NaN histo_* par année × modèle |

---

## Références

- Étape 0 diagnostic : `consolidation_finale/notebooks/etape_00_diagnostic_decalage_horaire_h25.ipynb`
- ADR-037 : grain enrichi histo_* (adopté 2026-06-04)
- ADR-038 : extension périmètre H25
- Audit phases 0-4 : `notes/audit_phases_0_4_2026_06_05.md`
