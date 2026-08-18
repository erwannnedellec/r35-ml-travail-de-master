---
id: ADR-038
ancien_id: ADR-40
date_decision: 2026-06-04
statut: amendé
amende_par: [ADR-065]
modifie: [ADR-016, ADR-027]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-038 — Extension du périmètre temporel à H25

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-065.
> Décisions antérieures que ce document modifie : ADR-016, ADR-027.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** Les métriques H25 publiées ici sous le libellé « Enrichi_Seg 158f » précèdent la correction de fuite temporelle d'ADR-062 et la migration de gel d'ADR-076. Elles diffèrent sensiblement de celles du mémoire (tableau 16), notamment sur le segment haut, et ne doivent pas être lues comme les résultats du modèle final.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-06-04 |
| **Décideur** | Erwann Nédellec (data analyste MOB, R35) |
| **ADR liés** | ADR-027 (split temporel H22-H23 / H24), ADR-037 (grain enrichi histo_*), ADR-039 (carry-forward STATPOP H25) |

---

## Contexte

L'ADR-027 (2026-05) avait acté un périmètre H22-H23 train / H24 test, intersection minimale entre disponibilité des sources, qualité APC et stationnarité distributionnelle. Au gel initial du dataset, H25 était partielle (10.5 / 12 mois) et l'ingestion des sources externes 2025 n'était pas finalisée.

L'ingestion des deux dernières sources critiques rend désormais H25 méthodologiquement exploitable comme test OOT :

- **Événements Riviera 2025** : reçus de Montreux Riviera Tourisme le 2026-06-04
- **ISTDATEN 2025** : exportés et nettoyés le 2026-06-04

Le millésime STATPOP 2025 reste indisponible (latence usuelle OFS), géré par carry-forward selon ADR-039.

---

## Décision

Adoption d'un nouveau périmètre temporel :

- **Entraînement** : H22 + H23 + H24 (832 732 observations, ml_dataset hash daf936c8)
- **Test OOT** : H25 (309 252 observations, hash daf936c8)

---

## Justification empirique

### Critère 1 — Stationnarité distributionnelle (à recalculer avec H25)

Le test KS entre années horaires confirme la cohérence du nouveau périmètre d'entraînement (valeurs ADR-027 sur `target_voyageurs_total`, n = 2 051 510) :

| Paire | Valeur KS | Seuil | Statut |
|---|---|---|---|
| H22 vs H23 | 0.0821 | ≤ 0.15 | ✅ (ADR-027) |
| H22 vs H24 | 0.0775 | ≤ 0.15 | ✅ (ADR-027) |
| H23 vs H24 | 0.1231 | ≤ 0.15 | ✅ (ADR-027) |
| H22 vs H25 | 0.0650 | ≤ 0.20 | ✅ |
| H23 vs H25 | 0.1056 | ≤ 0.20 | ✅ |
| H24 vs H25 | 0.0248 | ≤ 0.20 | ✅ |

Si toutes les paires (Hxx, H25) restent < 0.20, le périmètre est validé. Un seuil légèrement plus permissif que pour le bloc d'entraînement est acceptable pour le test : une légère dérive distributionnelle entre train et test est attendue et mesurer la robustesse à cette dérive est précisément l'objet d'un test OOT. La paire H24 vs H25 est le critère le plus discriminant — H24 et H25 étant les deux années les plus proches temporellement.

### Critère 1bis — TCE hétérogène entre années d'entraînement

L'inclusion de H22 dans le jeu d'entraînement introduit une hétérogénéité de qualité APC :

| Année horaire | TCE APC | Source |
|---|---|---|
| H22 | 52 % | Système de comptage en transition |
| H23 | 98 % | Nouveau système opérationnel |
| H24 | 100 % | Nouveau système stabilisé |

Cette hétérogénéité représente un point de vigilance documenté. Trois arguments justifient néanmoins l'inclusion de H22 :

1. **Compatibilité distributionnelle** : KS(H22, H24) = 0.0775 est meilleure que KS(H23, H24) = 0.1231. La portion H22 reste statistiquement cohérente avec le régime opérationnel courant.

2. **Volume additionnel** : ~830 K observations supplémentaires renforcent la portance des fenêtres `histo_*` (cf. ADR-037), particulièrement sur les courses peu fréquentes du segment haut où la fenêtre 7-occurrences se remplit lentement.

3. **Robustesse XGBoost au bruit** : un signal APC partiellement bruité sur 1/3 du training (H22) est compensé par 2/3 d'observations de qualité maximale (H23, H24). XGBoost est par construction robuste à ce type d'hétérogénéité.

La limitation sera explicitement reconnue dans la section méthodologique du mémoire.

### Critère 2 — Disponibilité des sources

Toutes les sources du modèle B (ADR-036) sont disponibles sur H23-H25, avec carry-forward STATPOP 2024 pour H25 (ADR-039). Confirmation à date :

| Source | H23 | H24 | H25 |
|---|---|---|---|
| ISTDATEN APC | ✅ | ✅ | ✅ (2026-06-04) |
| Événements Riviera | ✅ | ✅ | ✅ (2026-06-04) |
| Météo CdH / Vevey | ✅ | ✅ | ✅ |
| SIMBA FQkal | ✅ | ✅ | ✅ (lag N-1 = SIMBA 2024, ADR-041 — SIMBA 2025 exclu pour éviter leakage) |
| STATPOP | ✅ (2023) | ✅ (2024) | carry-forward 2024 (ADR-039) |
| Réservations ResSys | ✅ | ✅ | ✅ |

### Critère 3 — Refonte d'horaire 2024 → 2025

La refonte d'horaire CFF/MOB de décembre 2024 a affecté l'ensemble des trains R35 (cf. ADR-041) :

- **Trains maintenus H24 → H25 (même numéro)** : 51 / ~103 trains (49 %), représentant 51,8 % des observations H25 (160 147 obs). Match SIMBA 2024 complet sur ces services.
- **Trains renumérotés** : 52 trains (50 %), représentant 46,5 % des observations H25 (143 867 obs). Aucun match SIMBA 2024.
- **`horaire_service_id_complet` H24 maintenus en H25 : 0 / ~103 (0 %)** — la refonte a modifié 100 % des heures de départ à l'origine pour tous les trains R35, changeant de facto tous les identifiants (ADR-042).
- **Contrôle pipeline (seuil 80 %) : FAIL** (0 % < 80 %).

**Conséquences sur les features `histo_*`** : les features histo_* (clé `horaire_service_id_complet` + `cal_type_jour_3classes`, ADR-037) produisent NaN pour tous les services H25 en début de période test — XGBoost gère les NaN nativement. La dégradation observée sur les services renumérotés (PR-AUC haut = 0.055 vs 0.204 pour les services stables, ADR-042) est documentée comme fragilité RF-1 du modèle. Le contrôle < 80 % est attendu et documenté ; il n'invalide pas le test OOT mais signale une limite opérationnelle à mentionner dans le mémoire.

### Critère 4 — Volume d'entraînement

Le périmètre H22+H23+H24 est supérieur au précédent H22+H23 grâce à l'ajout de H24 :

| Périmètre | N entraînement | N test |
|---|---|---|
| H22+H23 / H24 (ADR-027) | ~497 000 | 335 709 |
| H22+H23+H24 / H25 (ADR-038) | 832 732 | 309 252 |

---

## Observation de l'ADR-037 au run H25

L'ADR-037 (adoption du grain enrichi `histo_*`) a été validée empiriquement sur le diagnostic seed=42 (test H24) avec un gain qualitatif substantiel (PR-AUC haut ×2.8, gap min divisé par 2, 64.4 % des surcharges individuellement mieux prédites). Aucun double entraînement n'est conduit sur H25 : la validation devient observationnelle.

**Critère de réinvestigation a posteriori** : si une régression majeure et inexpliquée du PR-AUC haut survient sur H25 (PR-AUC haut < 0.05, soit pire que le baseline B avant ADR-037 sur H24), une réinvestigation rétrospective sera conduite et documentée par un ADR-39bis. Aucun seuil moins strict ne déclenchera de remise en cause de l'ADR-037 : son adoption repose sur le gain qualitatif observé sur H24, qui n'a pas vocation à être réfuté par une seule mesure ponctuelle sur un autre périmètre.

Cette posture est cohérente avec le principe CRISP-ML(Q) de documentation des décisions méthodologiques : un gain empirique validé une fois sur un test substantiel reste valide tant qu'aucune contre-évidence claire n'émerge.

### Résultats observés

| Métrique | Enrichi_Seg v1.1 158f sur H25 | Critère de réinvestigation |
|---|---|---|
| R² global H25 | **0.588** (IC 95% [0.585, 0.592]) | — |
| R² segment haut H25 | **0.504** (IC 95% [0.493, 0.514]) | — |
| PR-AUC segment haut H25 | **0.191** (IC 95% [0.160, 0.234], ADR-047) | < 0.05 → ADR-39bis |
| R² segment bas H25 | **0.555** (IC 95% [0.551, 0.559]) | — |

---

## Conséquences

### Positives

- Test OOT sur l'année la plus récente disponible (H25) : meilleure pertinence opérationnelle pour la couche 2 et le déploiement futur.
- Validation indirecte de la robustesse face à la refonte d'horaire 2024→2025 (généralisation à un nouvel horaire).
- **Volume d'entraînement maximisé** : 832 732 observations (H22+H23+H24), tirant pleinement parti de la période où toutes les sources sont disponibles avec une qualité acceptable.
- ADR-037 traité par observation et non par re-validation systématique, simplifiant la séquence d'exécution du run final.

### Limitations à documenter dans le mémoire

- **Carry-forward STATPOP 2025 → 2024** (ADR-039) : approximation documentée, erreur attendue < 1 % sur les features démographiques.
- **Stabilité de `horaire_service_id_complet`** entre H24 et H25 : risque de couverture réduite des features `histo_*` si la refonte d'horaire est majeure.
- **TCE hétérogène entre années d'entraînement** : H22 (52 %) vs H23-H24 (98-100 %). Documentée en critère 1bis ci-dessus.
- L'ADR-037 n'est pas re-validée par double entraînement sur H25, mais observée a posteriori. Un PR-AUC haut < 0.05 sur H25 déclencherait un ADR-39bis.

---

## Références

- ADR-027 : Split temporel initial H22-H23 / H24 (révoqué par cet ADR pour la version finale du mémoire)
- ADR-037 : Grain enrichi des features `histo_*` (adoption directe, observation a posteriori sur H25)
- ADR-039 : Carry-forward STATPOP 2024 pour année calendaire 2025
- Notebook KS : `notebooks/04_model_engineering_split.ipynb`
- Notebook synthèse : `notebooks/SYNTHESE_modele_R35_evaluation_complete.ipynb` (à mettre à jour avec les nouveaux chiffres après run final)

## Addendum 2026-07-12 — micro-vérification de KS(H22,H23) = 0,0821 (Critère 1, l.50) : IRREPRODUIT

Contrôle conduit pour la section 4.5.1 : tenter de reproduire la valeur **KS(H22,H23) = 0,0821** du tableau du Critère 1 (l.50). Ce tableau annonce des KS calculés « sur `target_voyageurs_total`, n = 2 051 510 » (l.46).

**Résultats bruts** (source `stage_09_simba.parquet`, SHA256[:8] `954135f9` — cf. addendum ADR-066 2026-07-12 ; la cible est générationnellement invariante, ces valeurs valent donc aussi pour le gel d'époque `daf936c8`, non conservé sur disque) :

| Variable | Population | KS(H22,H23) |
|---|---|---|
| `target_voyageurs_total` | pleine (NaN retirés) | **0,0722** |
| `target_voyageurs_total` | H22 sans Gilamont | 0,0292 |
| `target_voyageurs_2eme_classe` | pleine (NaN retirés) | **0,0833** |
| `target_voyageurs_2eme_classe` | H22 sans Gilamont | 0,0402 |
| `target_voyageurs_2eme_classe` | brute (NaN inclus) | 0,0833 |

NaN de la cible sur H22 et H23 = 0 pour les deux variables ; l'inclusion des NaN est sans effet.

**Conclusion : 0,0821 IRREPRODUIT.** Aucune combinaison variable × population ne le reproduit. Sur la variable déclarée par la ligne (`target_voyageurs_total`), la valeur reproductible est **0,0722**, identique à ADR-027 (l.59). Les deux autres cellules de la même ligne d'ADR-038 se reproduisent, elles, exactement sur `total` : KS(H22,H24) = 0,0775 (l.51) et KS(H23,H24) = 0,1231 (l.52). Seule la cellule H22×H23 diverge (0,0821 déclaré vs 0,0722 reproduit). La valeur la plus proche toutes variantes confondues est 0,0833 (cible 2e classe, pleine ; Δ = +0,0012), qui ne correspond ni à la variable déclarée par la ligne ni à 0,0821.

**Lecture (sans modification des valeurs historiques).** Deux cellules sur trois reproduites à l'identique sur `total`, une seule cellule isolément divergente : profil cohérent avec une **anomalie ponctuelle de transcription** de la cellule H22×H23 (l.50), la ligne recopiant par ailleurs les valeurs `total` d'ADR-027. La valeur historique 0,0821 est **conservée telle quelle** ; le présent addendum documente l'écart, il ne le corrige pas.
