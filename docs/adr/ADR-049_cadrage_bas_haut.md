---
id: ADR-049
ancien_id: ADR-CF06
date_decision: 2026-06-06
statut: révoqué
revoque_par: [ADR-052, ADR-073]
chiffres_perimes: [seuil94]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-049 — Cadrage bas/haut : angle mort et stratégie de seuil

> **État au gel de la remise (2026-08-16) — statut : révoqué.**
> Cette décision a été révoquée par ADR-052, ADR-073.
> Les décomptes de surcharge de ce document sont calculés au **seuil 94** ; le seuil en vigueur est **63** depuis ADR-060.
> **Précision au gel.** L'architecture R3 instruite ici (seuils de décision distincts par segment) **n'a pas été implémentée** : la couche 2 applique un seuil unique au score de course (ADR-073).
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-06 — requalifié 2026-06-10  
**Statut** : **Exploration méthodologique — valeurs numériques caduques, conclusion qualitative conservée**  
**Décideur** : Erwann Nédellec  
**Modèle d'exploration** : APC-only 38 features (exploration uniquement) — modèle final : Enrichi_Seg 170f (ADR-052)  
**Lié à** : ADR-045 (grille 2×3), ADR-046 (critère F-beta, en attente), ADR-047 (hyperparams), ADR-048 (feature selection), ADR-060 (seuil 94→63, cause de caducité)

> **Requalification 2026-06-10 — Exploration méthodologique.** CF06 est orphelin dans l'architecture finale : vérification en lecture seule confirme que les seuils R1/R2/R3 (32.22 / 66.69 / 66.94) ne sont référencés dans aucun composant de production. Le modèle final (ADR-052) est un régresseur pur — aucun seuil WF n'est produit en sortie. La décision UM (ADR-033) s'ancre sur `pred ≥ SEUIL_UM_2C = 63` directement.
>
> **Deux dimensions de caducité des valeurs numériques** : (a) labels définis à ≥94 au lieu de >63 (ADR-060) ; (b) modèle sous-jacent APC-only 38f au lieu d'Enrichi_Seg 170f (ADR-052). Toutes les valeurs numériques de cet ADR (seuils, PR-AUC, rappels, précisions, décomptes) sont des **valeurs d'exploration, non valides pour l'architecture finale**.
>
> **Conclusion qualitative conservée** : le principe de seuils de décision distincts par segment (R3 — bas pendulaire ≠ haut touristique) est structurel et indépendant du seuil et du modèle. Il constitue l'apport durable de CF06 pour la conception de la couche 2.
>
> La calibration effective des seuils (valeurs numériques) sera réalisée en couche 2, sur seuil >63, modèle Enrichi_Seg 170f, critère F-beta à acter (ADR-046 en attente).

---

## Contexte

Tout le travail de calibration et de sélection (étapes 2, 3, 3bis) a été focalisé sur le **segment haut**
(touristique, Lally–Les Pléiades). Cette analyse vérifie que ce choix était justifié
et que le bas (pendulaire, VV–Lally) n'est pas un angle mort.

---

## Partie A — Décompte absolu des surcharges _(valeurs d'exploration — caduques)_

### H25 post-embargo (9j) — 300 473 observations totales

> ⚠️ **Valeurs d'exploration, non valides pour l'architecture finale.** Labels définis à ≥94 (offre APC) et modèle APC-only 38f. Décomptes à recalculer en couche 2 sur labels >63. Pour référence, les décomptes H25 complet (emb0) à seuil >63 : BAS=8 392, HAUT=1 192, GLOBAL=9 584 (source : `q7_zone_metrics_gt63.json`).

_Décomptes d'exploration calculés avec surcharge ≥ 94 (offre APC — caduque)._

| Segment | N obs | N surch ≥94 _(exploration)_ | Prévalence _(exploration)_ |
|---------|-------|--------------------------|-----------|
| **Bas (pendulaire)** | 223 211 | **1 215** | **0.544 %** |
| Haut (touristique) | 77 262 | 297 | 0.384 % |
| **Global** | 300 473 | **1 512** | **0.503 %** |

**Observation structurelle conservée** : le bas représente ~80 % des surcharges à seuil=94. À seuil>63, le bas représente 8 392 / 9 584 = **87.6 %** — la dominance pendulaire est encore plus marquée. Ce ratio asymétrique (bas ×7.2, haut ×4.2 par rapport à seuil=94) confirme que les deux segments ont des dynamiques de surcharge fondamentalement différentes.

### Répartition temporelle

| Mois horaire | Bas | Haut | Interprétation |
|-------------|-----|------|----------------|
| 1 (Déc↑) | 0 | **48** | Ski saison opening |
| 2 (Jan) | 95 | 29 | Ski hiver |
| 3 (Fév) | 40 | 32 | Ski hiver |
| 4-5 (Mar-Avr) | 110 | 0 | Scolaire bas |
| **6 (Jun)** | **238** | **170** | **Pic double** : narcisses haut + pendulaire bas |
| 7-8 (Jul-Aoû) | 86 | 8 | Été modéré |
| 9-12 | 501 | 10 | Automne/hiver bas |

**Haut** = surcharges concentrées ski (Déc-Fév) et narcisses (Juin).  
**Bas** = surcharges réparties toute l'année, pics Juin, Octobre, Novembre.

---

## Partie B — Performance APC-only sur le bas _(valeurs d'exploration — caduques)_

> ⚠️ **Valeurs d'exploration.** PR-AUC et rappels calculés sur modèle APC-only 38f avec labels ≥94. Non transposables au modèle final Enrichi_Seg 170f ni au seuil >63. Conservés pour la traçabilité de la démarche d'exploration.

| Segment | PR-AUC _(explor.)_ | IC 95 % _(explor.)_ | Rappel@WF _(explor.)_ | R² _(explor.)_ |
|---------|--------|---------|-----------|-----|
| **Bas** | **0.199** | [0.177–0.223] | **90.2 %** | 0.489 |
| Haut | 0.301 | [0.244–0.356] | 62.6 % | 0.283 |
| Global | 0.207 | [0.184–0.230] | 84.8 % | 0.503 |

**Observation structurelle conservée** : le bas n'est pas un angle mort du modèle (PR-AUC=0.199 > baseline aléatoire). Le problème est le seuil de détection, pas la capacité prédictive. Ce constat est indépendant du seuil et du modèle.

---

## Partie C — Comparaison des 3 régimes de seuil _(valeurs d'exploration — caduques)_

> ⚠️ **Valeurs d'exploration.** Seuils R1/R2/R3 (32.22 / 66.69 / 66.94) calibrés sur : (a) labels ≥94, (b) modèle APC-only 38f. Deux dimensions de caducité — non utilisables dans l'architecture finale. La calibration effective sera réalisée en couche 2.

### Seuils calibrés WF _(exploration, labels ≥94, APC-only)_

| Régime | Seuil bas _(explor.)_ | Seuil haut _(explor.)_ |
|--------|-----------|-----------|
| R1 — Seuil haut unique | 32.22 | 32.22 |
| R2 — Seuil global unique | 66.69 | 66.69 |
| R3 — Seuils par segment | **66.94** | **32.22** |

**Observation structurelle conservée** : le seuil bas (≈67) est structurellement plus élevé que le seuil haut (≈32), reflétant les charges moyennes plus élevées du segment pendulaire dense. Ce rapport (seuil bas >> seuil haut) sera recalculé mais restera probablement ordonné de même.

### Évaluation H25 _(exploration, labels ≥94, APC-only)_

#### Rappel _(exploration)_

| Régime | Bas | Haut | Global |
|--------|-----|------|--------|
| R1 Seuil haut (actuel) | **90.2 %** | 62.6 % | **84.8 %** |
| R2 Seuil global | 32.6 % | 20.5 % | 30.2 % |
| **R3 Par segment** | 32.3 % | **62.6 %** | **38.2 %** |

#### Précision (opérationnelle) _(exploration)_

| Régime | Bas | Haut | Global | Détections totales |
|--------|-----|------|--------|-------------------|
| R1 Seuil haut | **2.3 %** | 13.1 % | 2.6 % | **48 847** |
| R2 Seuil global | 24.7 % | 52.6 % | 26.6 % | 1 721 |
| **R3 Par segment** | **25.0 %** | **13.1 %** | **19.3 %** | **2 988** |

---

## Analyse des résultats _(raisonnement structurel conservé, valeurs numériques caduques)_

### 1. Le bas est un angle mort de SEUIL, pas de modèle _(conservé)_

Le modèle APC-only a PR-AUC=0.199 sur le bas — il n'est pas aveugle. Le problème structurel est qu'un seuil calibré sur le segment touristique rare est trop bas pour le segment pendulaire dense, générant un volume prohibitif de fausses alarmes. **Ce principe est indépendant du seuil (94 ou 63) et du modèle (APC-only ou Enrichi_Seg).** Il justifie la nécessité d'une stratégie de seuil différenciée par segment.

### 2. R1 (seuil unique côté haut) — inadapté au bas _(conservé)_

Un seuil unique calibré sur le haut touristique génère un ratio fausses alarmes/surcharges opérationnellement inutilisable sur le bas pendulaire dense (précision ~2 % dans cette exploration). **Ce constat qualitatif est robuste** : les dynamiques de charge sont structurellement différentes entre bas et haut.

### 3. R2 (seuil global unique) — détériore la détection haut _(conservé)_

Un seuil global unique protège la précision globale mais dégrade la détection sur le haut touristique rare. Inacceptable pour la mission principale (surcharges touristiques imprévisibles). **Ce constat qualitatif reste valide** avec tout modèle ou seuil.

### 4. R3 (seuils distincts par segment) — architecture recommandée _(conservé)_

Le principe : seuils distincts bas/haut permet de maintenir la détection haut tout en réduisant le bruit bas. **C'est la conclusion structurelle durable de CF06** : la couche 2 doit distinguer les deux segments pour la calibration du seuil de décision.

---

## Conclusion qualitative conservée — Apport durable de CF06

**L'architecture R3 (seuils distincts par segment) est la conclusion méthodologique de cet ADR.** Elle reste valide indépendamment du seuil de surcharge (94 ou 63) et du modèle (APC-only ou Enrichi_Seg), car elle repose sur une asymétrie structurelle entre segments :

- **Bas (pendulaire)** : charges moyennes plus élevées, surcharges 87.6 % du total >63 (8 392/9 584), profil régulier — seuil de décision mécaniquement plus élevé
- **Haut (touristique)** : charges plus variables, surcharges rares et événementielles — seuil de décision plus bas requis pour la sensibilité

Cette asymétrie est confirmée par les ratios de surcharge à seuil >63 : bas ×7.2, haut ×4.2 par rapport à seuil=94. Elle est structurelle (différences de demande, de fréquentation, de saisonnalité).

---

## Décision — Statut requalifié

### Modèle couche 1

Le modèle final est **Enrichi_Seg 170f** (ADR-052) — pas APC-only. Décision close. CF06 utilisait APC-only à titre d'exploration.

### Couche 2 — Principe de seuil par segment (R3) : **RETENU comme architecture à implémenter**

L'architecture R3 — seuils distincts bas/haut, calibrés sur H22-H24 en walk-forward — est recommandée pour la couche 2. La **décision qualitative est figée**. Les **valeurs numériques** (32.22, 66.94) sont caduques et seront recalculées avec :
- Modèle : Enrichi_Seg 170f (ADR-052)
- Labels : target > 63 (ADR-060)
- Critère F-beta : à acter (ADR-046 en attente)
- Protocole : walk-forward H22-H24, jamais H25

La compatibilité avec l'unité de décision UM au niveau du tour (ADR-007) reste valide — la stratégie par segment s'applique au niveau du tronçon puis s'agrège au tour.

### Limitations

- La PR-AUC bas et les rappels R3 de cette exploration (APC-only, labels ≥94) ne sont pas transposables. Avec Enrichi_Seg 170f et labels >63, les valeurs seront différentes.
- La sous-estimation systématique du modèle dans la zone de surcharge (biais>63 : −30.4 BAS, −37.8 HAUT — ADR-052) est un facteur à intégrer dans la calibration du seuil de décision couche 2.

---

## Fichiers

_Tous les outputs ci-dessous sont des artefacts d'exploration (labels ≥94, APC-only 38f). Ils documentent la démarche méthodologique mais leurs valeurs numériques ne sont pas valides pour l'architecture finale._

| Fichier | Contenu |
|---------|---------|
| `consolidation_finale/notebooks/etape_03ter_cadrage_bas_haut.ipynb` | Notebook d'exploration (SEUIL_UM=63, > strict — mis à jour pour cohérence, mais valeurs dans les outputs sont issues de la run ≥94) |
| `consolidation_finale/outputs/etape_03ter_surcharges_par_segment.csv` | Décomptes d'exploration (≥94) |
| `consolidation_finale/outputs/etape_03ter_surcharges_temporel.csv` | Distribution mensuelle d'exploration |
| `consolidation_finale/outputs/etape_03ter_pr_auc_par_segment.csv` | PR-AUC exploration APC-only |
| `consolidation_finale/outputs/etape_03ter_regimes_seuil.csv` | Comparaison 3 régimes d'exploration |
| `consolidation_finale/figures/etape_03ter_*.png` | Figures d'exploration — 300 DPI |
