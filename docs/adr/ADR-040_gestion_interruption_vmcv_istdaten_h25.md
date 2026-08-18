---
id: ADR-040
ancien_id: ADR-42
date_decision: 2026-06-04
statut: actif
modifie: [ADR-021]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-040 — Gestion de l'interruption VMCV ISTDATEN H25 (01.09 – 13.10.2025)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-021.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-04 |
| **Décideur** | Erwann Nedellec (data analyste MOB) |
| **ADR liés** | ADR-021 (features concurrence modale VMCV), ADR-039 v2 (convention `_source` analogue), ADR-038 (extension périmètre H25) |

## Contexte

L'ingestion ISTDATEN H25 a révélé une interruption de publication des données VMCV (Vevey-Montreux-Chillon-Villeneuve) entre le 01.09.2025 et le 13.10.2025 inclus (43 jours, ~12 % du test set H25). Avant et après cette période, VMCV publie normalement.

Cette interruption affecte les 4 features `vmcv_*` du modèle (concurrence modale bus, cf. ADR-021) : `vmcv_n_lignes_concurrentes`, `vmcv_frequence_horaire_bus`, `vmcv_ratio_temps_trajet`, `vmcv_chevauchement_horaire`. Les données R35 (MVR-cev) elles-mêmes sont intactes (validation : 32 842 lignes en septembre 2025, conforme à août et octobre).

Un backfill n'est pas envisageable dans un délai compatible avec le mémoire (service tiers, dépendance externe non maîtrisée).

## Options considérées

| Option | Description | Forces | Faiblesses |
|---|---|---|---|
| A. NaN avec traçabilité | Laisser NaN sur les 43 jours, XGBoost gère nativement via default direction routing | Aucune donnée inventée, transparence totale | Asymétrie train/test sur l'occurrence des NaN |
| B. Imputation par moyennes historiques | Imputer les 43 jours par moyenne H22-H24 stratifiée | Préserve la cohérence de régime d'entrée | Invente des données ; complexité d'implémentation ; choix de granularité non trivial |
| C. Exclusion des features VMCV du modèle | Retirer vmcv_* du jeu de features | Aucune asymétrie | Perd le signal VMCV sur 88 % du test où il est dispo |

## Décision

**Option A retenue : laisser NaN sur les 43 jours d'interruption, avec traçabilité explicite.**

Justifications :

1. **Importance secondaire de VMCV** : les 4 features `vmcv_*` apparaissent dans la moitié inférieure du classement SHAP du modèle B (cf. notebook synthèse Section 7). VMCV a un signal pertinent sur le segment bas mais largement redondant avec d'autres features. Sur le segment haut, VMCV n'a aucune pertinence opérationnelle (pas de bus concurrent dans les hauteurs). L'impact attendu du NaN sur 12 % du test est donc faible.

2. **Gestion native XGBoost** : XGBoost apprend une direction par défaut pour les NaN à chaque split d'arbre. Quelques NaN naturels existent dans le training H22-H24 (cas de bus manquants ponctuels traités par le pipeline VMCV existant), donc le routage par défaut est appris au moins partiellement pour les features `vmcv_*`.

3. **Transparence vs inventivité** : laisser NaN est plus défendable que d'imputer par des valeurs construites, particulièrement face à un jury qui valorise la pureté méthodologique. L'imputation aurait introduit une dépendance à un choix de granularité (gare × type_jour × créneau horaire ?) discutable.

4. **Validation empirique a posteriori** : l'impact réel sera mesuré au moment du run final en stratifiant les métriques par sous-période (jours avec VMCV publié vs jours d'interruption). Si l'effet est mesurable, il sera documenté en limitation du mémoire.

## Convention de traçabilité

Deux colonnes sont ajoutées au pipeline VMCV :

- `vmcv_source_depart`
- `vmcv_source_arrivee`

Avec valeurs :

| Valeur | Signification |
|---|---|
| `publie` | Données VMCV publiées normalement sur ISTDATEN |
| `manquant_interruption_vmcv` | Interruption de publication VMCV (43 jours, 01.09.2025 – 13.10.2025) |

Convention cohérente avec `event_ski_source`, `event_narcisses_source`, `event_covid_phase`, `spatial_statpop_source_*` (ADR-039).

**Important** : ces colonnes sont des métadonnées de traçabilité, à ajouter à la liste `COLS_EXCLUES` du notebook synthèse lors du run final coordonné.

## Modifications à apporter

### Script pipeline VMCV

Identifier le script qui produit les features `vmcv_*` (probablement `scripts/pipeline/add_vmcv_to_raw_stacked.py` ou nom équivalent — à confirmer par diagnostic préalable).

Modifications :

1. **Ajouter une constante** définissant la période d'interruption :

```python
# Période d'interruption de publication VMCV sur ISTDATEN.
# Validé par diagnostic ingestion H25 (cf. rapport 04.06.2026, ADR-040).
VMCV_INTERRUPTION_DEBUT = pd.Timestamp("2025-09-01")
VMCV_INTERRUPTION_FIN = pd.Timestamp("2025-10-13")  # inclus
```

2. **Logique de jointure inchangée** : les NaN apparaissent naturellement quand la jointure échoue (pas de données VMCV pour les 43 jours).

3. **Ajouter les colonnes de traçabilité** après les jointures :

```python
# Marqueur de source VMCV (métadonnée, exclu du training)
mask_interruption = (
    (df["base_date"] >= VMCV_INTERRUPTION_DEBUT)
    & (df["base_date"] <= VMCV_INTERRUPTION_FIN)
)
df["vmcv_source_depart"] = pd.Series("publie", index=df.index, dtype="string")
df["vmcv_source_arrivee"] = pd.Series("publie", index=df.index, dtype="string")
df.loc[mask_interruption, "vmcv_source_depart"] = "manquant_interruption_vmcv"
df.loc[mask_interruption, "vmcv_source_arrivee"] = "manquant_interruption_vmcv"
```

4. **Vérification de cohérence** post-construction :

```python
n_interruption = (df["vmcv_source_depart"] == "manquant_interruption_vmcv").sum()
n_total_h25 = (df["horaire_annee_horaire"] == "H25").sum()
print(f"  VMCV interruption : {n_interruption:,} lignes "
      f"({100*n_interruption/n_total_h25:.1f}% du test H25)")

# Cohérence : sur les jours d'interruption, vmcv_n_lignes_concurrentes doit être NaN
nan_interruption = df.loc[mask_interruption, "vmcv_n_lignes_concurrentes"].isna().sum()
print(f"  NaN vmcv_n_lignes_concurrentes sur interruption : "
      f"{nan_interruption}/{n_interruption} "
      f"({'OK' if nan_interruption == n_interruption else 'ANOMALIE'})")
```

### Notebook synthèse

À faire au run final coordonné (pas maintenant) : ajouter `vmcv_source_depart` et `vmcv_source_arrivee` à la liste `COLS_EXCLUES` du notebook synthèse, aux deux endroits où elle apparaît (Section 4.2 et Section 5).

### Validation empirique à conduire au run final

Stratifier les métriques d'évaluation sur H25 par sous-période :

- Métriques sur H25 complet
- Métriques sur H25 hors période d'interruption (88 % du test)
- Métriques sur les 43 jours d'interruption uniquement

Si l'écart de R² entre les deux sous-périodes est < 0.005, l'impact est négligeable. Si l'écart est > 0.005, documenter en limitation du mémoire. Idéalement, faire la stratification par segment (bas / haut) pour isoler l'effet : VMCV n'ayant pas de pertinence sur le segment haut, on s'attend à ce que l'écart soit nul sur le haut et marginal sur le bas.

## Conséquences

### Positives

- Aucune donnée inventée, transparence totale sur la dégradation de la couverture
- Traçabilité par colonne `vmcv_source`, audit méthodologique possible
- Gestion native XGBoost cohérente avec le reste du pipeline
- Simplicité d'implémentation

### Limitations à documenter dans le mémoire

- 12 % du test set H25 présente des NaN sur 4 features VMCV
- Le routage XGBoost des NaN sur ces features n'est appris que partiellement (via les rares NaN naturels du training)
- Impact réel à quantifier par stratification des métriques au run final
- Une régression structurelle de VMCV (changement de service, nouvelles lignes) entre 01.09 et 13.10.2025 ne serait pas captée même si elle avait lieu

## Précision sur les features VMCV statiques vs dynamiques (ajout 2026-06-04)

L'audit pré-entraînement a révélé que parmi les 4 features `vmcv_*` du modèle, une est **statique** et trois sont **dynamiques** :

- **Statique** (non affectée par l'interruption ISTDATEN) :
  - `vmcv_n_lignes_concurrentes` — calculée depuis `dim_vmcv_lignes_concurrentes`, qui décrit la topologie des lignes VMCV indépendamment du calendrier quotidien

- **Dynamiques** (NaN pendant l'interruption, attendus à 100 %) :
  - `vmcv_min_attente_min` — attente minimale calculée depuis les horaires VMCV ISTDATEN
  - `vmcv_delta_attente_min` — dérivée de la précédente
  - `vmcv_delta_frequence_h` — fréquence comparative calculée depuis ISTDATEN

Le contrôle de cohérence post-construction du script `add_istdaten_to_raw_stacked.py` utilise désormais `vmcv_min_attente_min` (dynamique) plutôt que `vmcv_n_lignes_concurrentes` (statique) pour vérifier que les features sont bien NaN pendant les 43 jours d'interruption. Cette correction supprime un faux positif `[ANOMALIE]` dans les logs sans changer la décision ni la convention de traçabilité.

Conséquence pratique : sur les 31 594 lignes `manquant_interruption_vmcv`, `vmcv_n_lignes_concurrentes` reste non-NaN (information topologique préservée), mais les 3 features dynamiques sont NaN. XGBoost dispose donc d'une information partielle sur ces 43 jours — un comportement plus correct que des NaN totaux.

## Références

- Rapport d'ingestion ISTDATEN H25, 04.06.2026 (interruption VMCV identifiée)
- ADR-021 : Features de concurrence modale VMCV, D3 (statique vs dynamique)
- ADR-039 v2 : Carry-forward STATPOP (convention `_source` analogue)
- Notebook synthèse Section 7 : classement SHAP montrant VMCV en moitié inférieure
