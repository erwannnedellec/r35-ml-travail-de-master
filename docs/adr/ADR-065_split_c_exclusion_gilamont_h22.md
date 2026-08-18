---
id: ADR-065
ancien_id: ADR-CF21
date_decision: 2026-06-18
statut: actif
modifie: [ADR-027, ADR-038]
chiffres_perimes: [gel]
corroboration_date: déclaratif (aucun commit d'époque)
gel_registre: 2026-08-16
---

# ADR-065 — Split C : exclusion des tronçons Gilamont H22, conservation du reste de H22

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-027, ADR-038.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-18 |
| **Date** | 2026-06-18 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-027 (split H22+H23/H24), ADR-038 (extension H25), ADR-063 (STATPOP Z-2) |
| **Version modèle** | Enrichi_Seg v1.6 (158f, Split C, hash dataset 5fdca746) |

---

## Contexte

L'ADR-038 avait acté le split H22+H23+H24 train / H25 test. La question de la qualité de H22 dans le jeu d'entraînement a été posée en vue de la consolidation finale. Deux signaux justifiaient une investigation :

1. **TCE H22 = 48.9 %** : seule la moitié des courses ISTDATEN H22 est présente dans les données APC. Le notebook 02 documente ce phénomène comme un "artefact format APC H22" (variation intra-annuelle : 9 % en septembre 2022, 83 % en juillet 2022). La cause n'est pas entièrement élucidée ; la distribution des courses capturées est cohérente (biais de sélection non détecté sur créneaux, type de jour, mois, segment).

2. **Bascule Gilamont → VVVI en H23** : la gare Gilamont (BPUIC 8501260, km 1.21 sur la ligne) a été remplacée par Vevey Vignerons (VVVI, BPUIC 8502476, km 1.45) à l'ouverture de H23. Les 4 tronçons Gilamont (GIL↔VV, GIL↔HTV) existent uniquement en H22 et n'ont aucun équivalent en H23-H25. Leur présence dans le train introduit une topologie réseau que le modèle ne rencontrera jamais en production.

### Évaluation empirique : Split A vs B vs C

Trois configurations ont été comparées sur test H25 (158 features, seed=42, même hyperparamètres) :

| Configuration | Train | HAUT R² | BAS R² | GLOBAL R² |
|---|---|---|---|---|
| **A (actuel)** | H22+H23+H24 (832 732) | 0.498 | 0.563 | 0.593 |
| **B (sans H22)** | H23+H24 (671 135) | 0.456 | 0.562 | 0.586 |
| **C (H22 sans Gilamont)** | H22_valid+H23+H24 (801 282) | **0.498** | **0.566** | **0.596** |

### Localisation de la valeur HAUT de H22

Le gain HAUT de +4.2 pts R² (A vs B) est **entièrement attribuable aux tronçons Blonay-Pléiades de H22**, qui sont topologiquement identiques sur H22-H25. La gare Gilamont est dans la section BAS (VV→Blonay) ; les tronçons Gilamont exclus du train sont intégralement classifiés segment BAS. Retirer Gilamont n'affecte pas une seule observation HAUT de H22 (Split C HAUT = Split A HAUT, ΔR² = 0.0000 exactement).

### Validité topologique de Split C

La validité du nettoyage H22 BAS a été vérifiée sur les 12 tronçons BAS partagés (ni Gilamont ni VVVI) :

| Périmètre | KS max H22 vs H23 | Seuil ADR-027 |
|---|---|---|
| Tronçons voisins HTV (CHTV↔HTV) | **0.095** | 0.15 ✅ |
| Tronçons intérieurs BAS | **0.080** | 0.15 ✅ |

Aucun signal de redistribution de flux sur les tronçons adjacents à la bascule Gilamont→VVVI. Les décalages observés (H22 légèrement > H23 < H24) correspondent à la tendance temporelle générale du trafic post-COVID, non à un effet topologique.

**Cohérence de l'ordre spatial** : `spatial_gare_depart_ordre` et `spatial_gare_arrivee_ordre` sont stables par gare sur H22-H25 (ancrage par position km, non par rang séquentiel). HTV = ordre 4 en H22 comme en H23-H25. Aucune correction nécessaire.

**Note topographique** : Gilamont (km 1.21) et VVVI (km 1.45) sont à 244 m l'une de l'autre. Ce n'est pas un simple renommage mais un déplacement de gare. Les tronçons GIL↔VV/HTV et VVVI↔VV/HTV sont des arêtes distinctes du graphe réseau.

**Note CLIE** : Clies (BPUIC 8501261, ordre 3) est absente de ml_dataset sur toutes les années. Cette gare ne constitue pas un tronçon direct dans les données APC (services directs GIL→HTV / VVVI→HTV). Elle est conservée dans dim_gare pour historique.

---

## Décision

**Split C** : jeu d'entraînement = H22 (tronçons Gilamont exclus) + H23 + H24, test = H25.

**Règle d'exclusion** : retirer du train toutes les observations dont `id_gare_depart_bpuic = 8501260` OU `id_gare_arrivee_bpuic = 8501260` (Gilamont). Soit 31 450 observations BAS H22 sur 161 597 totales H22 (19.5 %).

**H22 conservé** pour :
- Le segment HAUT (Blonay-Pléiades) : topologie identique H22-H25, 3ème cycle saisonnier qui apporte +4.2 pts R² HAUT vs Split B.
- Le segment BAS hors Gilamont : 10 tronçons BAS topologiquement stables (KS < 0.10), nettoyage améliore BAS +0.003 R² vs Split A.

---

## Implémentation

```python
GILAMONT_BPUIC = 8501260
gilamont_mask = (
    (df["id_gare_depart_bpuic"] == GILAMONT_BPUIC) |
    (df["id_gare_arrivee_bpuic"] == GILAMONT_BPUIC)
)
h22_valid = df[(df["horaire_annee_horaire"] == "H22") & ~gilamont_mask]
train_c = pd.concat([h22_valid,
                     df[df["horaire_annee_horaire"].isin(["H23", "H24"])]])
```

---

## Résultat

| Segment | R² H25 | PR-AUC H25 | MAE>63 | biais>63 |
|---|---|---|---|---|
| BAS | 0.5655 | 0.4358 | 28.7 | −27.8 |
| HAUT | 0.4982 | 0.4322 | 39.5 | −39.2 |
| GLOBAL | 0.5955 | — | MAE=7.90 | — |

Enrichi_Seg v1.6 — dataset `5fdca746`, 158 features (sans SIMBA, sans STATENT).

---

## Limites documentées

- **TCE H22 = 48.9 %** : 51 % des courses ISTDATEN H22 sont absentes des données APC. La cause est labelisée "artefact format" dans le notebook 02 mais non entièrement élucidée. La distribution des courses capturées est cohérente. Un biais sur les courses absentes (notamment septembre 2022 à 9 % de TCE) ne peut pas être totalement exclu.
- La stationnarité de H22 BAS non-Gilamont a été vérifiée par KS (< 0.10), non par une analyse complète de la représentativité des courses manquantes H22 vs ISTDATEN.
