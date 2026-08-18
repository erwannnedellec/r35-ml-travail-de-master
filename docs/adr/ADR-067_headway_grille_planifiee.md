---
id: ADR-067
ancien_id: ADR-CF23
date_decision: 2026-06-20
statut: actif
modifie: [ADR-018]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-067 — Headway calculé sur la grille horaire planifiée connue à J-1 (annulés et suppléments inclus)

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-018.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Date** : 2026-06-20
**Statut** : Accepté
**Décideur** : Erwann Nédellec
**Périmètre** : features `ist_headway_*` uniquement (`build_dim_headway.py`)
**Lié à** : ADR-018 (features `ist_headway_*` depuis ISTDATEN), ADR-022 (disponibilité J-1), ADR-062 (cutoff histo_*, autre correction du même rebuild canonique)

---

## Contexte

Les features `ist_headway_*` mesurent l'isolement temporel d'un train sur son tronçon × sens
(minutes depuis le train précédent / jusqu'au train suivant, à l'horaire **théorique**).
Elles sont calculées par `build_dim_headway.py` à partir d'ISTDATEN, qui est construite depuis
l'**horaire planifié** : tous les trains prévus y figurent avec un statut (`is_annule`,
`is_supplementaire`).

L'implémentation antérieure filtrait les trains annulés avant de reconstruire les tronçons :

```python
df = df_istdaten[~df_istdaten["is_annule"]].copy()
```

Un audit externe (2026-06-20) a relevé que ce filtre fait dépendre le headway d'une information
de **statut réalisé** : retirer un train parce qu'il a été annulé suppose que l'annulation est
connue au moment du calcul. Or la décision UM se prend à **J-1**, et l'annulation d'un train du
jour J n'est **pas connue à J-1**. Le headway antérieur injectait donc, sur une fraction des
tronçons, une information non disponible à l'inférence (distribution shift entraînement/inférence).

---

## Décision

Le headway se calcule sur **tous les trains de la grille horaire planifiée connue à J-1**, sans
aucun filtre de statut réalisé. Critère unique : *« le train était-il dans la grille planifiée
connue à J-1 ? »*

| Statut | Connu à J-1 ? | Décision |
|---|---|---|
| Régulier | Oui | **Inclus** |
| **Annulé** (`is_annule = True`) | Oui (planifié) ; l'annulation n'est **pas** connue à J-1 | **Inclus** (changement) |
| **Supplémentaire** (`is_supplementaire = True`) | Oui — planifié en amont | **Inclus** (déjà le cas) |

**Justification du maintien des suppléments.** Le processus de planification MOB n'autorise pas
l'ajout d'un train le jour J : tout supplément est planifié en amont et figure donc dans la grille
connue à J-1 (source : E. Nédellec, data lead MOB). La cohérence est confirmée par les données :
les trains supplémentaires ont un `horaire_depart` théorique renseigné dans 88,7 % des cas
(≈ le taux des réguliers, 91,3 %), signe de leur présence à la grille planifiée.

**Modification** : retrait du filtre `~is_annule` dans `_reconstruire_troncons`
(`build_dim_headway.py`). Aucun autre changement (toujours `horaire_depart` théorique uniquement,
aucun fallback sur `reel_depart`, cf. ADR-018).

---

## Ampleur mesurée (dataset 51e459ff → 416bb90b)

- **+22 555 tronçons** réintégrés (présents à la grille planifiée, auparavant écartés car annulés).
- **3 989 tronçons existants modifiés (0,174 %)** — un train annulé intercalé décale le voisin
  immédiat. Médiane du headway **inchangée (30,0 min)** ; l'effet est strictement local.
- Couverture `ist_headway_*` dans ml_dataset : 78,9 % / 79,3 % (avant/après) ; NaN structurels =
  premiers/derniers de journée (3,5 %).
- Note : 3 941 lignes étaient à la fois `is_annule` ET `is_supplementaire` ; auparavant exclues
  par le filtre annulé, désormais incluses.

**Validité de l'horaire théorique par statut** (taux d'`horaire_depart` manquant) : régulier
8,68 %, annulé 9,56 %, supplément 11,33 % — taux comparables, aucune anomalie. Les rares lignes
sans horaire théorique produisent un headway NaN (comportement identique pour tous les statuts).

---

## Rang SHAP des features `ist_headway_*` (H25, Enrichi_Seg)

`ist_headway_apres_min` et `ist_headway_avant_min` sont des features **importantes**
(rangs #17 et #19/158 sur le segment BAS ; #36 et #61/158 sur HAUT) — d'où l'intérêt de les
calculer sur la bonne grille. Les flags `is_first/last_of_day` sont en queue de classement
(rangs > 130). La part d'information réalisée retirée par cette correction reste néanmoins
**bornée à 0,174 %** des tronçons.

---

## Conséquences

- **Une des deux corrections du rebuild canonique `416bb90b`** (2026-06-20), avec l'amendement
  ADR-062 (cutoff composé). Orthogonalité stricte vérifiée : seules les 4 colonnes
  `ist_headway_*` changent du fait de cette correction (16 colonnes `histo_*` du côté CF18) ;
  189/209 colonnes byte-identiques à 51e459ff.
- **ADR-018** : révisé — le headway reste théorique mais sur la grille planifiée complète
  (le filtre `~is_annule` antérieur est supprimé).
- Effet combiné CF18+CF23 sur métriques H25 : faible et conforme au retrait de biais
  (cf. CONTEXT.md, section Enrichi_Seg v1.9).

---

## Fichiers impactés

| Fichier | Modification (2026-06-20) |
|---|---|
| `scripts/sources/build_dim_headway.py` | retrait du filtre `~is_annule` dans `_reconstruire_troncons` + docstring |
| `data/processed/sources/dim_headway.parquet` | recalculé (grille planifiée complète) |
| `data/processed/ml_dataset.parquet` | hash canonique `416bb90b` (avec ADR-062 composé) |

---

## Références

- ADR-018 — Features `ist_headway_*` depuis ISTDATEN exclusivement (révisé par cet ADR)
- ADR-062 — Amendement règle composée du cutoff histo_* (même rebuild canonique)
- Audit externe headway/cutoff, 2026-06-20 (5 points ; CF23 = point 4, CF18 amendé = point 3)
