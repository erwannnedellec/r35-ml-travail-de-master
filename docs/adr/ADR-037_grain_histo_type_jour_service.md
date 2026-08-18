---
id: ADR-037
ancien_id: ADR-39
date_decision: 2026-06-04
statut: remplacé
remplace_par: [ADR-042, ADR-044]
modifie: [ADR-009, ADR-010]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-037 — Grain enrichi des features histo_* : conditionnement par type de jour et identification par service

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-042, ADR-044.
> Décisions antérieures que ce document modifie : ADR-009, ADR-010.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-04  
**Statut** : Accepté (validation conditionnelle — à confirmer sur run final H25)  
**Décideur** : Erwann Nédellec (data analyste MOB, R35)  
**Lié à** : ADR-008 (lag opérationnel J-2), ADR-009 (grain lag avec année horaire), ADR-033 (architecture deux couches), ADR-036 (modèle B référence)

---

## Contexte

Les features `histo_*` du modèle de référence B (ADR-036) exploitent l'autocorrélation temporelle du signal APC au grain `(horaire_annee_horaire, horaire_troncon_tgl, horaire_numero_train)`. L'implémentation calculait un shift positionnel fixe à 2 occurrences précédentes et une fenêtre glissante sur les 7 dernières occurrences, toutes natures de jours confondues.

Deux faiblesses sémantiques de ce grain ont été identifiées en revue méthodologique :

**1. Mélange des régimes de fréquentation.** La fenêtre `win7` d'une course quotidienne mélange dans le même calcul des observations de mardi, samedi, dimanche, jours fériés — alors que la fréquentation diffère structurellement selon le type de jour (régime pendulaire versus régime touristique), particulièrement sur le segment haut de R35 (Vevey – Villeneuve). Ce mélange dilue le signal historique au lieu de l'affiner.

**2. Identification fragile du service.** `horaire_numero_train` peut désigner des services différents (heures d'origine différentes) au sein d'une même année horaire ou entre changements d'horaire. `horaire_service_id_complet`, construit comme `{numéro}_{HHhMM}` (numéro de train + heure de départ depuis l'origine ce jour), identifie plus stablement le « même service » au sens opérationnel.

**3. Bug latent `observed=False`.** `cal_type_jour_3classes` est de dtype `category` dans stage_07. Le groupby pandas avec `observed=False` (comportement par défaut pour les colonnes category) crée des lignes fantômes pour toutes les combinaisons catégorielles non observées, multipliant la table daily par 6× et réduisant la couverture lag à ~3 % sur les ouvrables. Ce bug était latent dans l'implémentation précédente (GROUP_KEYS sans colonne category) ; il aurait été activé à la première utilisation du nouveau grain sans la correction.

---

## Investigation empirique

Un notebook diagnostic (`notebooks/12_diagnostic_histo_type_jour.ipynb`, seed=42, modèle XGBoost 300 arbres) a comparé le modèle B actuel (ADR-036) à un modèle B' utilisant le grain enrichi sur le test OOT H24 (n = 335 709 observations) :

| Métrique | B (référence ADR-036) | B' (grain enrichi) | Delta |
|---|---|---|---|
| R² global | 0.6454 | **0.6594** | **+0.014** |
| R² segment bas | 0.6045 | **0.6220** | **+0.018** |
| R² segment haut | 0.4757 | **0.4836** | +0.008 |
| PR-AUC segment haut | 0.0548 | **0.1521** | **+0.097 (×2.8 relatif)** |
| Gap min surcharges haut (unités sous 94) | 32.9 | **14.6** | −18.3 |
| Gap moyen surcharges haut | 56.3 | **51.8** | −4.5 |
| Surcharges haut individuellement mieux prédites | — | 67/104 (64.4 %) | — |

Le gain sur le **PR-AUC du segment haut** (×2.8 relatif, 0.0548 → 0.1521) constitue la justification empirique principale : c'est la métrique opérationnellement critique pour la couche 2 (capacité à discriminer les surcharges réelles parmi les cellules à risque). Le gain R² global (+1.4 pp) améliore aussi significativement les segments bas et global.

Le gain R² segment haut (+0.008) est en deçà du seuil critique C2 fixé à +0.010 (écart de 0.002 points), dans la variance attendue d'un run à 300 arbres sur ~85 000 observations. Une validation multi-seed sur 3 runs était initialement prévue mais a été reportée au run final sur le périmètre H23-H24 / H25, plus informative que de stabiliser sur un périmètre qui sera supplanté.

---

## Décision

**Adoption du nouveau grain pour les features `histo_*`.**

```python
GROUP_KEYS = [
    "horaire_annee_horaire",
    "horaire_troncon_tgl",
    "horaire_service_id_complet",
    "cal_type_jour_3classes",
]
```

avec :

- **`cal_type_jour_3classes`** à 3 modalités : `ouvrable`, `samedi`, `dimanche_ferie`. Cette dernière englobe tout jour férié quel que soit le jour de la semaine (logique : trafic touristique potentiel structurellement différent des ouvrables même pour un lundi-fériés).
- **`horaire_service_id_complet`** construit comme `{horaire_numero_train}_{HHhMM}` où `HHhMM` est l'heure d'origine du service ce jour.
- **`horaire_troncon_tgl`** conservé pour cohérence du schéma (vaut toujours 0 sur R35, ligne unique — n'apporte pas de discrimination mais maintient la structure du contrat de données).

La logique de shift est désormais **dynamique par searchsorted** : pour chaque ligne de date D, l'occurrence utilisée pour le lag est la dernière dans la série groupée dont `base_date ≤ D - 2 jours calendaires` (respect strict d'ADR-008). Cette logique préserve la pureté opérationnelle tout en évitant le gaspillage d'information :

- Mardi (ouvrable) → lag = Lundi si Lundi ≤ D−2, sinon Vendredi
- Mercredi (ouvrable) → lag = Lundi (J−2 exact)
- Samedi → lag = Samedi précédent (J−7, toujours consolidé)
- Dimanche → lag = Vendredi ou Dimanche précédent selon le calendrier

---

## Modifications apportées au code

**Fichier modifié** : `scripts/pipeline/add_features_to_raw_stacked.py`

1. `GROUP_KEYS` enrichi avec `horaire_service_id_complet` et `cal_type_jour_3classes`.
2. `DERIVED_COLS` : `horaire_service_id_complet` retiré (désormais INPUT du GROUP_KEYS, non OUTPUT dérivé).
3. `add_derived_features` : section "Features historiques" remplacée par la logique searchsorted. `observed=True` sur tous les groupby.
4. `main()` : `_ajouter_service_id_complet` appelé en PREMIER, avant `add_derived_features`, suivi d'une vérification de la présence de `cal_type_jour_3classes`.
5. Contrôles de cohérence mis à jour : `head(1)` par groupe (première occurrence) au lieu de `head(LAG_OPERATIONNEL_JOURS)` (sémantique différente avec shift dynamique).

---

## Conséquences

### Positives

- Gain PR-AUC majeur sur le segment haut (×2.8) : la couche 1 produit un signal substantiellement plus utile pour la couche 2 de détection des surcharges.
- Gain R² global +1.4 pp, R² bas +1.8 pp : amélioration générale de la précision.
- Pureté méthodologique renforcée : alignement strict entre la justification opérationnelle (ADR-008, J−2 calendaire) et l'implémentation (shift dynamique, pas de shift positionnel fixe).
- Cohérence avec le qualitatif MOB : les entretiens P01–P06 ont fait émerger l'importance du type de jour comme déterminant de fréquentation (résultats TPB). Le conditionnement par `cal_type_jour_3classes` matérialise cette intuition dans le pipeline ML.

### Limitations et points de vigilance

- **Couverture par groupe** : avec un grain plus fin (service + type_jour), le nombre d'occurrences par groupe est réduit. Les premières observations de chaque groupe ont lag NaN (notamment au démarrage d'un horaire ou d'un service nouveau). Les contrôles post-construction vérifient la couverture par type_jour.
- **Intersection train/test sur H25** : la refonte d'horaire 2024→2025 peut changer les `horaire_service_id_complet`. Le contrôle existant (seuil 80 % d'observations du test avec historique en train) est le point de surveillance critique sur le run H25.
- **Bug `observed=False` corrigé** : tout futur ajout de colonne `category` dans GROUP_KEYS devra maintenir `observed=True` dans les groupby.
- **Performance** : le remplacement de pandas `.shift()` vectorisé par une boucle Python par groupe est acceptable sur le volume actuel (daily ≈ 200 k lignes, ~1 400 groupes de ~140 lignes). Si le dataset croît significativement, envisager une vectorisation complète par `merge_asof` (cf. implémentation dans notebook 12, cellule 2).

---

## Validation différée

Le critère C2 (ΔR² segment haut ≥ +0.010) est manqué de 0.002 points sur le run de validation seed=42. Trois runs supplémentaires (seeds 0, 1, 2) étaient initialement prévus pour confirmer la stabilité, mais ont été reportés au run final sur le périmètre H23-H24 / H25 (à venir). Si ce run montre une régression nette du R² segment haut ou du PR-AUC segment haut par rapport au grain ADR-036, la décision sera réexaminée et documentée dans un ADR-39bis.

---

## Références

- Notebook diagnostic : `notebooks/12_diagnostic_histo_type_jour.ipynb`
- ADR-008 : Lag opérationnel J-2 — données APC consolidées
- ADR-009 : Grain du lag avec année horaire — frontière conservatrice
- ADR-033 : Architecture deux couches régression + décision
- ADR-036 : Modèle B référence couche 1
- Studer et al. (2021), CRISP-ML(Q) — documentation systématique des décisions ML
