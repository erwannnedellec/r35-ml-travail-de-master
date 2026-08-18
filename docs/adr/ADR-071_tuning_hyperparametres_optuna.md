---
id: ADR-071
ancien_id: ADR-CF27
date_decision: 2026-06-28
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-071 — Conservation des hyperparamètres ADR-052 : optimisation Optuna conduite, CF09 confirmé robuste out-of-time

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
| **ADRs liés** | ADR-052 (hyperparamètres XGBoost — confirmés ici), ADR-069 (perte MSE conservée), ADR-070 (features cantonales écartées), ADR-065 (Split C), ADR-049 (segmentation BAS/HAUT), ADR-060 (seuil 63), ADR-030 / ADR-031 (découplage R²/rappel classe rare) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) — **inchangée** |
| **Nature** | Décision méthodologique. **Aucun changement de modèle, de dataset, de hash, de pipeline.** |

---

## Contexte

Le directeur du travail de master a relevé que les hyperparamètres ADR-052 (n_est=300,
depth=6, lr=0.1, subsample/colsample=0.8) étaient présentés **sans méthode d'optimisation
documentée** — « on pourrait penser à de bonnes pratiques, mais il n'y en a pas vraiment ».
Il a suggéré une **optimisation systématique** (Optuna / RandomSearch plutôt que GridSearch,
trop lourd).

Question : **une optimisation des HP améliore-t-elle le modèle, et faut-il changer CF09 ?**

## Décision

**Les hyperparamètres ADR-052 sont CONSERVÉS.** Le candidat optimal Optuna (« best-R² »,
HP différenciés par segment) **n'est PAS adopté**. Le modèle 158f / hash `416bb90b` reste
**inchangé** (hash vérifié intact à chaque exécution).

## Rationnel empirique — protocole strict, hors canonique (`exp_hpo/`)

**Méthode d'optimisation.** Optuna, sampler **TPE bayésien**, **multi-objectif** [maximiser
R²_H24, minimiser |biais>63|_H24] avec **front de Pareto** (pas de pondération λ arbitraire).
**Pas de CV aléatoire** (respect de la causalité temporelle). Optimisation sur train
H22 (hors Gilamont, ADR-065) + H23 → **validation H24**, **par segment** (BAS / HAUT,
50 essais chacun). **H25 jamais utilisé pour le tuning.**

**Constat en validation H24.** CF09 est **quasi optimal**. Le meilleur point (best-R²) ne
gagne que **+0,02 de R²** sur H24 ; le biais>63 ne bouge quasiment pas (les HP ne changent
pas l'estimand `reg:squarederror`) ; un mouvement **PR-AUC HAUT (+0,043)** apparaît en
validation. Profils best-R² : **régularisation plus forte + lr plus bas**, différenciés par
segment — BAS depth=8 / lr=0,029 / n=360 / min_child_weight=10 / γ=4,47 / λ=3,88 / α=1,88 ;
HAUT depth=5 / lr=0,077 / n=349 / γ=3,37 / λ=3,44.

**Confirmation sur H25** (critère d'adoption posé **avant** de voir les chiffres : adoption
seulement si **aucune dégradation matérielle** de R² global, biais>63, PR-AUC tronçon ET tour
par segment). Réentraînement tri-annuel H22+H23+H24 (Split C, 801 282 obs) → test H25
(309 252 obs). **Garde-fou : CF09 reproduit les `metrics_h25` canoniques à Δ = 0,0000.**

**best-R² ÉCHOUE le critère.** Sur H25 il :
- **aggrave le biais>63 sur tous les segments** (HAUT **−2,04**, BAS −0,97, global −1,11 ;
  MAE>63 pire partout) ;
- **dégrade la PR-AUC HAUT** (tronçon **−0,0068**, tour **−0,0090**) — **pire sur l'objectif
  même** ;
- pour un gain marginal de **+0,004 de R² global**, obtenu en ajustant mieux la masse au
  **détriment de la zone >63** (tension R²/classe rare, ADR-030/32).

### Synthèse chiffrée (H25, GLOBAL puis HAUT)

| | R² glob | biais>63 | MAE>63 | PR-AUC tronçon HAUT | PR-AUC tour HAUT |
|---|---:|---:|---:|---:|---:|
| **CF09** (canonique) | 0,6013 | −28,47 | 29,09 | 0,3452 | 0,3459 |
| best-R² (par segment) | 0,6054 | −29,57 | 29,92 | 0,3384 | 0,3369 |
| **Δ (best − CF09)** | **+0,0040** | **−1,11** | +0,83 | **−0,0068** | **−0,0090** |

**Le mirage de validation.** Le mouvement PR-AUC HAUT de validation (**+0,043**) **s'inverse
sur H25 (−0,007)** — **bruit de segment** (HAUT ≈ 600 / 1 200 surcharges, statistiquement
instable), **même profil que k=2** (ADR-069) **et que les features en Phase C** (ADR-070).

| segment | ΔR² H24 → H25 | ΔPR-AUC tronçon H24 → H25 |
|---|---|---|
| bas | +0,020 → +0,004 | +0,019 → +0,003 |
| **haut** | +0,017 → +0,005 | **+0,043 → −0,007** |

## Conséquence — triangulation complète

Les **hyperparamètres** constituent le **3ᵉ levier indépendant testé** (avec la **perte**
ADR-069 et les **features** ADR-070) **qui NE relève PAS la PR-AUC HAUT**. Conclusion
empirique **triangulée et confirmée** :

> Le plafond de séparabilité du segment HAUT (~0,345) est **intrinsèque au signal disponible
> à J-1**, non un défaut de modélisation (perte, features, HP).

Apports de ce chantier :
1. **Procédure d'optimisation documentée et défendable** (réponse directe au point soulevé par le directeur du travail de master) :
   Optuna TPE multi-objectif Pareto, par segment, sans fuite temporelle.
2. **CF09 confirmé quasi optimal ET robuste out-of-time** : le candidat sélectionné sur
   validation **dégrade le test** — CF09 généralise mieux.
3. **Un re-tuning serait à refaire sur tout nouveau jeu de features** — **sans objet ici** :
   les features cantonales ayant été écartées (ADR-070), le jeu reste **158f**.

## Traçabilité

`consolidation_finale/exp_hpo/` : `tuning_optuna_h24.py` / `_resultats.json` / `_trials.csv`,
`postprocess_h24.py`, figures (`pareto_*`, `param_importance_*`, `history_*`),
`test_h25_best_r2_vs_cf09.py` / `.json`, `RAPPORT_TEST_H25_best_r2.md`. **Garde-fou : CF09
reproduit les `metrics_h25` canoniques à Δ = 0.** Modèles expérimentaux non sauvegardés.
**Hash canonique `416bb90b` intact, vérifié.** Aucune écriture dans le rapport ni le pipeline.
ADR autonome : `docs/adr/ADR-071_tuning_hyperparametres_optuna.md`.
