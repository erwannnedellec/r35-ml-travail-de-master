---
id: ADR-068
ancien_id: ADR-CF24
date_decision: 2026-06-22
statut: actif
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-068 — Traçabilité a posteriori du retrait des identifiants de gare (`id_gare_*`) de la liste de features

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> **Précision au gel.** Le `xgb_M0` cité ici (12 variables) est un **objet distinct** de la baseline M0 du mémoire (31 variables, §4.5.2). L'homonymie est signalée, non résolue.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté (traçabilité a posteriori) — 2026-06-22 |
| **Date** | 2026-06-22 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-033 (pivot, ère 160f — listait `id_gare_*`), ADR-036 (modèle B 168f), ADR-017 (ablation `horaire_numero_train`), ADR-037 (grain histo B_prime), ADR-048 (sélection externe sur 179f) |
| **Version modèle** | Enrichi_Seg v1.9 (158f, Split C, hash dataset `416bb90b`) |

---

## Objet

Cet ADR **constate et trace a posteriori** le retrait des features `id_gare_depart` et
`id_gare_arrivee` de la liste de features du modèle. Cette décision **n'avait pas été
formalisée au moment où elle a eu lieu** ; le présent document la documente après coup,
sans réintroduire les features ni modifier le hash canonique.

**Aucun changement de modèle, de dataset ou de hash n'est induit par cet ADR — il est purement documentaire.**

## Constat factuel (chronologie vérifiée)

Vérification par extraction des `feature_names` des modèles sérialisés et confrontation des listes de features :

| Modèle | n features | `id_gare_depart` / `id_gare_arrivee` |
|---|---|---|
| `xgb_M0` (12f) | 12 | présent (`id_gare_depart`) |
| `xgb_A` (160f, ADR-033) | 160 | **présents** |
| `xgb_B` (168f, ADR-036) | 168 | **présents** |
| `xgb_B_prime` (179f) | 179 | **absents** |
| 171f / 170f / 169f / **158f canonique** | … | **absents** |

- **Transition exacte** : `xgb_B` (168f) → `xgb_B_prime` (179f), datée par git **2026-06-04 → 2026-06-05**.
- **Diff identifiants retirés au même moment** : `id_gare_depart`, `id_gare_arrivee`, `base_sens`, `horaire_numero_train` (différence exacte des deux listes de features).
- Le notebook 07 (segmentation, 2026-05-29, ère B) gardait encore `id_gare_depart`/`id_gare_arrivee` comme features catégorielles (seules les variantes `_bpuic` étaient exclues via `COLS_EXCLUES_ML`).

## Rationnel (sourcé, non reconstruit après coup)

Le retrait est cohérent avec des éléments **mesurés à l'époque**, même s'il n'avait pas été
formalisé comme décision :

1. **Importance mesurée négligeable.** CONTEXT.md « Finding B » : dans le modèle B (168f),
   `id_gare_depart` / `id_gare_arrivee` se classent **rang 149/168 et 152/168** au gain XGBoost
   (gain **0,049 % et 0,035 %**).
2. **Redondance structurelle.** `spatial_gare_depart_ordre` et `spatial_gare_arrivee_ordre`
   encodent la position des gares sur la ligne et **figurent dans les 158 features canoniques**
   (rangs #60 et #61 de `features_158f_sans_simba.json`). La topologie est donc préservée sans
   les identifiants nominaux.
3. **Robustesse out-of-time.** Un identifiant **nominal** (LabelEncodé, traité comme ordinal
   arbitraire par XGBoost) généralise mal à une topologie qui change entre millésimes
   (Gilamont → VVVI, ADR-065), là où l'**ordre ordinal de position** (`spatial_gare_*_ordre`)
   généralise par position relative.
4. **Cohérence de nettoyage.** Le retrait s'inscrit dans le nettoyage groupé des identifiants
   bruts à la construction de B_prime (`horaire_numero_train` tracé par **ADR-017** ; `base_sens`
   conservé uniquement comme **clé** de groupement `histo_*` — ADR-062 — et exclu des features
   au titre des clés d'identification, cf. §3.4 du rapport de synthèse).

## Honnêteté de traçabilité

- La décision **n'a pas été formalisée** au moment du retrait (2026-06-05) : aucun commit,
  ADR ou note ne l'enregistrait. Elle est tracée **a posteriori** ici.
- **ADR-033 n'est pas réécrit** : il reste un document daté de l'ère 160f où `id_gare_*` étaient
  effectivement des features importantes (par divergence inter-segment). Sa lecture doit se faire
  dans ce contexte historique.

## Décision

1. **Ne pas réintégrer** `id_gare_depart` / `id_gare_arrivee` dans les features : apport mesuré
   négligeable, redondance avec `spatial_gare_*_ordre`, réintégration changerait le hash
   canonique `416bb90b` et dégraderait la robustesse OOT pour un gain attendu nul.
2. **Tracer** le retrait via le présent ADR.
3. **Aligner** CONTEXT.md « Finding B » (qui décrivait encore les `id_gare_*` comme présentes)
   sur l'état réel, sans effacer la mesure historique (rang 149/152 reste un fait utile).

## Conséquences

- Aucune sur le modèle, le dataset ou le hash (`416bb90b` figé).
- Documentaire : cohérence rétablie entre la liste de features réelle, le rapport de synthèse
  (§4.4 corrigé) et CONTEXT.md « Finding B ».
- `ALL_ADRS.md` (digest généré) devra être régénéré pour inclure cet ADR.
