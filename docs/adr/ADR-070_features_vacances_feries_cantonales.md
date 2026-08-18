---
id: ADR-070
ancien_id: ADR-CF26
date_decision: 2026-06-28
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-070 — Features vacances/fériés cantonaux (VS/FR/NE/GE) : testées et écartées

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-28 |
| **Date** | 2026-06-28 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-069 (conservation perte MSE — « la piste suivante = enrichissement du signal »), ADR-052 (hyperparamètres XGBoost), ADR-060 (seuil surcharge 63), ADR-065 (Split C), ADR-049 (segmentation BAS/HAUT), ADR-061 (retrait SIMBA), ADR-033 (pivot régression + augmentation couche 2) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset, de hash, de pipeline.** |

---

## Contexte

Le directeur du travail de master a suggéré que les **vacances scolaires et jours fériés
des cantons voisins** (Valais, Fribourg, Neuchâtel, Genève) pourraient capter un trafic
**excursionniste** vers le segment HAUT touristique (Les Pléiades), là où le **plafond de
séparabilité est le plus bas** (PR-AUC HAUT ≈ 0,345 sur H25) et où ni la perte (ADR-069)
ni les hyperparamètres (tuning Optuna) n'avaient rien relevé.

Hypothèse à tester : **ces features relèvent-elles la PR-AUC HAUT ?** C'est, après la perte
et les HP, le **3ᵉ levier indépendant** examiné pour franchir ce plafond — et précisément
celui que l'ADR-069 désignait comme « la piste suivante : enrichissement du signal ».

## Décision

**Les 8 features ne sont PAS intégrées au modèle canonique.**
`event_is_vacances_{valais, fribourg, neuchatel, geneve}` et `event_is_ferie_{…}` restent
des **features candidates non retenues**. Le modèle 158f / hash `416bb90b` reste **inchangé**
(hash vérifié intact à chaque exécution expérimentale).

## Rationnel empirique — 3 phases, hors canonique

Chantier entièrement **hors canonique** (`exp_features/`), protocole strict, **iso-tout sauf
les features**, HP ADR-052, seed=42, segmentation BAS/HAUT, perte `reg:squarederror`,
seuil 63. **Protocole de choix** = train H22 (hors Gilamont, ADR-065) + H23 → **validation
H24** ; **H25 jamais utilisé pour le choix**, touché une seule fois pour la confirmation de
généralisation.

### Phase A — Construction & contrôle qualité

8 features binaires journalières construites et sourcées :
- **Valais** : 5 PDF « Plan de scolarité » coloriés (pas de dates explicites) → parseur de
  rectangles vectoriels (bleu/jaune = classe, **orange = férié cantonal**, blanc = congé),
  **datation par position de grille** (robuste aux coquilles source : ex. « 25 » imprimé
  pour « 15 »). Validation : 0 incohérence jour/position, totaux mensuels de jours de classe
  reproduits exactement, **72 fériés analytiques confirmés à 100 % par l'orange**.
- **Fribourg** : XLSX (périodes explicites, calendrier majoritaire francophone).
- **Neuchâtel** : arrêté 410.562 (table de périodes).
- **Genève** : PDF (chaque année liste aussi n+1 ; 2024-25 récupérée via le PDF 2023-24).

QC : **0 NaN**, plausibilité 23-26 % de jours/an en vacances (attendu ~25-27 %), **aucune
asymétrie train/test**, pas de fuite (calendriers statutaires publiés ex ante, connus J-1).
Corrélations avec le vaudois existant **0,67-0,91** (aucune > 0,95) → information
incrémentale présente. **Redondance interne férié VS≈FR (r = 0,97).**

### Phase B — Impact (validation H24, 158f vs 166f)

**Sur l'objectif HAUT : ÉCHEC.** Δ PR-AUC HAUT = **−0,0022** (tronçon) / +0,0015 (tour),
dans le bruit ; R² HAUT même **légèrement dégradé** (−0,012), MAE>63 HAUT +1,19. Seul signal
réel : **`event_is_vacances_valais` sur le BAS** (SHAP rang 7/166, +0,019 PR-AUC BAS) — **hors
cible**. Les 4 `event_is_ferie_*` et les vacances GE/FR sont **quasi morts** (SHAP < 0,1 % ;
la redondance VS≈FR se traduit par un SHAP partagé nul, l'info fériés étant déjà captée par
`event_is_ferie_vaud`).

### Phase C — Confirmation H25 (`event_is_vacances_valais` seule, 158f vs 159f)

Garde-fou parfait : le 158f reproduit les `metrics_h25` canoniques **à Δ = 0,0000** (R² et
PR-AUC, BAS/HAUT/global). Résultat :
- Le **gain BAS ne généralise qu'au quart** : PR-AUC BAS tronçon **+0,019 (H24) → +0,0055
  (H25)**, tour +0,012 → +0,0047 — sous le seuil d'intérêt (0,03).
- **Instabilité de segment** : le mouvement HAUT apparu sur H25 (+0,019 PR-AUC) **contredit**
  la validation H24 (−0,002) → artefact petit-échantillon du HAUT (620 / 1 192 surcharges),
  **pas un gain démontré**.
- SHAP **stable** (rang ~9/159 BAS) mais **effet métrique < 0,02 partout**, non reproductible.

## Verdict

Même le seul candidat survivant (`event_is_vacances_valais`) **ne relève pas le plafond
HAUT** et n'offre qu'un effet BAS **petit, atténué hors échantillon et instable en segment**.

*Note interprétative :* le signal valaisan sur le BAS est cohérent avec un possible flux
**pendulaire transfrontalier** (habitants du bas travaillant en Valais ; demande réduite les
jours fériés/vacances valaisans), mais **trop ténu** pour être exploité ou vérifié.

## Conséquence architecturale — triangulation des 3 chantiers

Avec la **perte** (ADR-069) et les **hyperparamètres** (tuning Optuna documenté), les
**features cantonales** constituent le **3ᵉ levier indépendant testé qui NE relève PAS la
PR-AUC HAUT**. Conclusion empirique **triangulée** :

> Le plafond de séparabilité du segment HAUT (~0,345) est **intrinsèque au signal disponible
> à J-1** sur ce segment rare et volatil — ce n'est ni un défaut de modélisation (perte, HP)
> ni un manque de cette source.

Implication : la **couche 2** choisit un point de fonctionnement sur une **courbe PR fixe** ;
relever le plafond HAUT exigerait des **sources de signal nouvelles non disponibles à ce
stade**. Ceci **clôt empiriquement** la piste « enrichissement du signal » ouverte par
ADR-069 pour la source vacances/fériés cantonaux.

## Traçabilité

Chantier dans `exp_features/` : `parse_valais.py`, `build_cantonal_features.py`,
`phaseB_impact_h24.py`, `phaseC_confirm_h25.py`, `RAPPORT_PHASE_{A,B,C}.md`, sorties dans
`exp_features/outputs/`. Garde-fous : baseline 158f reproduit le k=1 du chantier perte
(validation H24) et les `metrics_h25` canoniques (test H25) à Δ = 0. **Features candidates
non intégrées. Hash canonique `416bb90b` intact, vérifié. Aucune écriture dans le rapport,
le pipeline ou le dataset.**
