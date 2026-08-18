---
id: ADR-020
ancien_id: ADR-22
date_decision: 2026-05-18
statut: remplacé
remplace_par: [ADR-021]
corroboration_date: dépôt de travail, commit du 2026-06-04
gel_registre: 2026-08-16
---

# ADR-020 — Refonte des features VMCV : concurrence modale au grain tronçon

> **État au gel de la remise (2026-08-16) — statut : remplacé.**
> Cette décision a été remplacée par ADR-021.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

**Statut** : Remplacé par ADR-021  
**Date** : 2026-05-18  
**Auteur** : E. Nédellec  

---

## Contexte

La première version des features VMCV (implémentée dans `build_dim_vmcv_par_gare.py`)
présentait quatre limites identifiées lors de la revue du pipeline :

1. **Grain gare, pas tronçon** : la concurrence était agrégée au niveau de la gare,
   sans distinguer le sens de circulation. Une gare peut être desservie par VMCV dans
   un sens seulement, ou avec des fréquences très différentes selon la direction.

2. **Présence/absence seulement** : les features binaires ne capturaient pas
   l'avantage ou le désavantage relatif (attente, temps de trajet, fréquence).

3. **Statique** : les features ne variaient pas d'un jour à l'autre ni d'un train
   à l'autre, limitant leur pouvoir prédictif en interaction avec les features temporelles.

4. **Chaîne de dépendances longue** : `dim_vmcv_lignes_concurrentes` →
   `dim_vmcv_lignes_par_gare_r35` → `dim_vmcv_par_gare` → jointure dans la pipeline.

---

## Décisions

### D1 — Trois features différentielles au grain tronçon × train × jour

| Feature | Description | Signe positif |
|---------|-------------|---------------|
| `vmcv_delta_attente_min` | (attente R35) − (attente prochain VMCV dans [−5min, +30min]) | VMCV passe avant R35 |
| `vmcv_delta_trajet_min` | (trajet R35 sur tronçon) − (moyenne journalière du trajet VMCV sur le même tronçon) | VMCV plus rapide |
| `vmcv_delta_frequence_h` | (nb VMCV dans ±30min) − (nb R35 dans ±30min) | VMCV plus fréquent |

NaN si aucun arrêt VMCV alternatif dans le rayon RAYON_PROXIMITE_M (200m) pour les
deux extrémités du tronçon.

Note sur `delta_frequence` — convention de signe : la formule est inversée par rapport à la
définition littérale « (freq_R35 − freq_VMCV) » pour rester cohérente avec la
convention globale « delta > 0 = VMCV avantageux » de D1.

Note sur `delta_frequence` — auto-inclusion R35 : le train R35 courant est inclus dans
le décompte de sa propre fréquence (self-join sur le tronçon dans ±30min). Ce choix est
intentionnel : le voyageur perçoit la densité globale du service R35 sur le tronçon,
pas uniquement les « autres » trains. Conséquence : pour un train R35 isolé face à 1 VMCV,
`delta_frequence = 1 − 1 = 0`.

Note sur `delta_trajet_min` — fenêtre journalière : la moyenne de référence est calculée
sur **tous les services VMCV du jour** sur le tronçon (pas seulement ceux dans la fenêtre
d'attente). Cela stabilise le calcul lorsque peu de services VMCV coincident avec la
fenêtre d'attente d'un train R35 donné, et capture la vitesse structurelle de la ligne.

### D2 — Identification des alternatives VMCV par proximité géographique (200m)

Un arrêt VMCV est considéré alternatif à une gare R35 si la distance haversine est
≤ 200m. La condition s'applique aux **deux** extrémités du tronçon : un tronçon R35
n'a de features non-NaN que si ses deux gares ont chacune un arrêt VMCV alternatif
sur la **même ligne** (même `LINIEN_TEXT`).

En pratique, seul le tronçon VV↔GIL est couvert (lignes 202, 215) car la gare
VVVI (km=1.45), entre GIL (km=1.21) et CLIE (km=2.66), est trop éloignée des arrêts
VMCV pour être dans le rayon. Tous les tronçons hauts (Blonay-Pléiades) retourneront
NaN (aucune alternative bus).

### D3 — Reconstruction des tronçons VMCV via FAHRT_BEZEICHNER

Les passages VMCV sont extraits des CSV ISTDATEN bruts (filtrés sur
`BETREIBER_ABK == "VMCV"` et les BPUICs pertinents). La reconstruction des tronçons
utilise `FAHRT_BEZEICHNER` pour grouper les arrêts d'un même service, puis joint
les lignes de départ avec les lignes d'arrivée en imposant `h_dep < h_arr`. Seules
les paires correspondant au mapping statique (D2) sont conservées.

### D4 — Couverture temporelle : VMCV dans ISTDATEN à partir d'octobre 2018

Les données VMCV dans ISTDATEN débutent en octobre 2018. Avant cette date, toutes
les features VMCV sont NaN (XGBoost gère nativement les valeurs manquantes).

### D5 — Jointure J-2 dans add_istdaten_to_raw_stacked.py

Le décalage opérationnel J-2 est appliqué à la jointure via `_joindre_troncon_j_moins_2`
avec les 5 clés :
`(base_date, horaire_numero_train, id_gare_depart_bpuic, id_gare_arrivee_bpuic, base_sens)`

Même logique que `dim_profil_train` (ADR-019, D1). Le grain des deux tables est aligné.

---

## Features produites

Grain : `(date, numero_train, gare_depart_bpuic, gare_arrivee_bpuic, sens)`

| Feature | Type | NaN si... |
|---------|------|-----------|
| `vmcv_delta_attente_min` | float | Pas d'alternative VMCV dans [−5, +30min] avant/après le départ R35 |
| `vmcv_delta_trajet_min` | float | Aucun service VMCV sur ce tronçon ce jour-là |
| `vmcv_delta_frequence_h` | float | Aucun VMCV dans ±30min autour du départ R35 |

---

## Conséquences

### Positives
- Features dynamiques : varient par train, par jour, par tronçon.
- Interprétables directement comme avantage compétitif instantané du mode bus.
- NaN naturels pour les tronçons sans alternative modale (pas d'imputation nécessaire).
- Grain cohérent avec `dim_profil_train` (ADR-019) → même jointure 5-clés.

### Négatives / Compromis
- Couverture limitée en pratique : seul VV↔GIL non-NaN (tous les tronçons hauts = NaN).
- La lecture des 84 CSV ISTDATEN bruts est nécessaire (plusieurs minutes d'exécution).
- La jointure sur 5 clés augmente le risque de NaN si les tronçons VMCV ne correspondent
  pas exactement aux tronçons APC (tolérance = 0).

### Fichiers modifiés / créés
| Fichier | Rôle |
|---------|------|
| `scripts/sources/build_dim_vmcv_par_troncon.py` | Nouveau — remplace `build_dim_vmcv_par_gare.py` |
| `scripts/pipeline/add_istdaten_to_raw_stacked.py` | Ajout famille 3 VMCV avec jointure tronçon |
| `scripts/pipeline/paths.py` | Ajout `DIM_VMCV_PAR_TRONCON`, `DIM_VMCV_PAR_GARE` marqué DEPRECATED |
| `Makefile` | Règle `dim_vmcv_par_troncon`, mise à jour `dims` et `stage_07` |

---

## Alternatives rejetées

### A1 — Conserver le grain gare avec features quantitatives

Rejeté : le grain gare masque les variations directionnelles. Le grain tronçon est
cohérent avec ADR-019 (dim_profil_train) et permet la jointure sur 5 clés.

### A2 — Rayon de 500m au lieu de 200m

Rejeté : un rayon plus large inclut des arrêts de bus non-alternatifs (ex. arrêts
sur une avenue parallèle sans continuité de service). 200m garantit une proximité
physique directe (même carrefour ou passage piéton immédiat).

### A3 — Rolling windows temporelles pour les features VMCV

Non implémenté : les features VMCV sont calculées à la date réelle du service R35 et
varient naturellement d'un jour à l'autre via les grilles horaires VMCV effectives.
Un rolling ajouterait de la complexité sans gain interprétatif clair sur 3 features.
