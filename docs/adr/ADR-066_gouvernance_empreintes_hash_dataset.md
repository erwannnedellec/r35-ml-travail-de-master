---
id: ADR-066
ancien_id: ADR-CF22
date_decision: 2026-06-20
statut: amendé
amende_par: [ADR-076]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-06-21
gel_registre: 2026-08-16
---

# ADR-066 — Gouvernance des empreintes de hash des datasets (SHA256[:8], rupture MD5→SHA256)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-076.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté — 2026-06-20 |
| **Date** | 2026-06-20 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-062 (cutoff mensuel histo), ADR-063 (STATPOP Z-2 causal), ADR-064 (retrait STATENT), ADR-065 (Split C) |
| **Version modèle** | Enrichi_Seg v1.7 (158f, Split C, hash dataset `d39d0bd8`) |
| **Environnement** | pyarrow 21.0.0, pandas 2.3.3 |

---

## Contexte

Chaque version du dataset `ml_dataset.parquet` est identifiée par une empreinte de hash tronquée à 8 caractères, censée garantir la traçabilité et la reproductibilité bit-à-bit de l'artefact d'entraînement. Lors de la consolidation finale (v1.7), un audit de cohérence a mis en évidence deux problèmes de gouvernance non documentés :

1. **Rupture d'algorithme de hachage en cours de chaîne.** Les versions antérieures et postérieures de la chaîne n'utilisent pas le même algorithme :

   | Version | Hash | Algorithme | Label dans les outputs |
   |---|---|---|---|
   | v1.2 | `fe9d6b4d` | **MD5[:8]** | `hash_md5_8` |
   | v1.3 | `961a0bd5` | **MD5[:8]** | `hash_md5_8` |
   | v1.4 | `c1ecfc19` | **MD5[:8]** | `hash_md5_8` |
   | seuil 63 | `daf936c8` | **MD5[:8]** | `hash_md5_8` |
   | v1.6 | `5fdca746` | **SHA256[:8]** | `hash_sha256_8` |
   | **v1.7** | **`d39d0bd8`** | **SHA256[:8]** | `hash_sha256_8` |

   La bascule MD5 → SHA256 est intervenue **au passage v1.4 → v1.6** (premiers scripts SHA256 : `q_all_v16_5fdca746.py`, `final_158f_split_c.py`). Le même fichier physique produit donc des empreintes différentes selon l'algorithme — exemple sur l'artefact courant : `MD5[:8] = e380d1e5`, `SHA256[:8] = d39d0bd8`.

2. **Absence de référence ADR.** La convention de hachage n'était formalisée dans aucun ADR. Le rapport de synthèse (`rapport_synthese_couche1`, §3.1) citait par erreur **ADR-015**, qui traite de la *logique opérationnelle J-2 des features ISTDATEN* et n'a aucun rapport avec le hachage.

## Décision

1. **Empreinte canonique = SHA256[:8] du fichier `ml_dataset.parquet`, à environnement pyarrow constant (21.0.0).** C'est le standard en vigueur **depuis v1.6 (`5fdca746`)** et il est confirmé pour toutes les versions ultérieures. Le hachage porte sur les octets bruts du parquet (`hashlib.sha256(path.read_bytes()).hexdigest()[:8]`).

2. **Rupture d'algorithme assumée et documentée.** Les versions **≤ `daf936c8`** (v1.2 `fe9d6b4d`, v1.3 `961a0bd5`, v1.4 `c1ecfc19`, seuil `daf936c8`) utilisent **MD5[:8]** ; les versions **≥ v1.6** (`5fdca746`, v1.7 `d39d0bd8`) utilisent **SHA256[:8]**.

3. **Conséquence assumée — hashs historiques non comparables et non recalculables.** Les empreintes de la chaîne historique ne sont pas comparables entre elles (algorithmes différents). Les parquets ≤ `daf936c8` ayant été archivés/supprimés (seul `ml_dataset.parquet` = `d39d0bd8` subsiste sur disque), leur SHA256 **n'est pas recalculable**. Les hashs MD5 antérieurs valent comme **repères d'archive**, non réconciliables avec le standard actuel.

4. **Reproductibilité de l'artefact canonique — vérifiée.** `d39d0bd8` (artefact canonique final v1.7) est **reproductible par `make` complet à pyarrow 21.0.0 constant**. C'est la version qui compte pour la reproductibilité de l'artefact ; la non-réconciliation des hashs historiques n'affecte pas la reproductibilité du dataset en production.

5. **Correction de la référence erronée.** La citation « ADR-015 » pour la convention de hachage a été retirée du rapport (§3.1). **Le présent ADR-066 est désormais la référence unique de la convention de hachage des datasets.**

## Recommandation future (gouvernance, non bloquant)

- **Double-tampon MD5 + SHA256** pour les versions futures, si un pont avec la chaîne historique MD5 est souhaité.
- **Noter la version de `pyarrow`** dans tout ADR critique : l'empreinte du parquet dépend du writer (schéma, compression, `created_by`). Un changement de version pyarrow peut modifier le hash sans changement de contenu.

## Preuve de reproductibilité (v1.7 / `d39d0bd8`)

Vérification réalisée le 2026-06-20 :

```
make clean            # suppression des stages (sources/dims conservées)
make                  # reconstruction complète de la chaîne de stages → ml_dataset.parquet
```

Résultat — parquet régénéré :

```
SHA256[:8] = d39d0bd8   ✓  (== empreinte canonique attendue)
MD5[:8]    = e380d1e5       (cohérent avec l'artefact d'origine)
1 141 984 lignes × 209 colonnes ; années H22-H25
pyarrow 21.0.0 | pandas 2.3.3
```

Cohérence de la chaîne amont confirmée sur l'artefact régénéré :
- STATPOP : `statpop_clean_causal` branché, label `forward_fill` (630 413 obs) + `exact` (511 571), mapping Z-2 — aucun `interpole`/`carry_forward` résiduel ;
- Ski : `event_ski_source` ∈ {`officiel`, `hors_saison`} — `reconstruit` absent du dataset ML ;
- STATENT : absent des 209 colonnes conservées (retiré au build — ADR-064) ;
- ResSys : intégré en ligne dans la passe finale (`build_ml_dataset.py` dépend de `stage_09`, pas de `stage_10` ; `stage_10` = artefact d'audit hors flux principal) ;
- Split C (ADR-065) : sélection appliquée en aval de la construction (le parquet contient l'intégralité des observations H22-H25).

## Conséquences

- **Positif** : convention de hachage formalisée et tracée ; reproductibilité de l'artefact canonique prouvée ; suppression d'une citation ADR erronée ; algorithme robuste (SHA256) confirmé comme standard.
- **Négatif assumé** : la chaîne historique MD5 reste non réconciliable (parquets archivés/supprimés) — accepté, car seule la version canonique en production importe pour la reproductibilité.
- **Dépendance environnementale** : l'empreinte est garantie à `pyarrow 21.0.0` constant ; tout changement de version du writer devra être réévalué et acté.

## Mise à jour 2026-06-20 — hash canonique courant `51e459ff`

`d39d0bd8` (v1.7) est **supersédé** par **`51e459ff`** (v1.8) : application réelle d'ADR-062 (histo_* cutoff mensuel + clé tronçon, voir amendement ADR-062). `51e459ff` est un **SHA256[:8]** (même convention), **reproductible** par `make clean && make` (pyarrow 21.0.0, vérifié 2026-06-20). La convention de hachage reste inchangée ; seul le pointeur canonique évolue d39d0bd8 → 51e459ff.

## Mise à jour 2026-06-20 bis — hash canonique courant `416bb90b`

`51e459ff` (v1.8) est **supersédé** par **`416bb90b`** (v1.9) : deux dernières corrections de leakage — cutoff APC composé décision T-1 + ingestion (amendement ADR-062) et headway sur grille planifiée (ADR-067). `416bb90b` est un **SHA256[:8]** (convention inchangée), **reproductible** : deux `make clean && make` indépendants → `416bb90b` byte-exact (pyarrow 21.0.0, vérifié 2026-06-20). Pointeur canonique : d39d0bd8 → 51e459ff → **`416bb90b`**. Cette convention de hachage (ADR-066) reste la référence unique et **n'est pas modifiée** par la bascule ; seul le pointeur évolue.

## Addendum 2026-07-12 — source figée des figures de stationnarité (section 4.5.1) : `stage_09_simba.parquet` (SHA256[:8] `954135f9`)

Les figures de stationnarité H16-H25 de la section 4.5.1 (matrice KS et KDE de la cible 2e classe) ne peuvent pas être produites depuis le gel canonique `ml_dataset.parquet` (`ba493568`), qui ne couvre que H22-H25 (filtre temporel du build, ADR-027/038). Elles s'appuient sur la table amont pré-filtre `data/processed/stage_09_simba.parquet`, **SHA256[:8] = `954135f9`** (pyarrow 21.0.0), consignée ici comme **source figée** de ces figures.

**Statut d'empreinte.** `954135f9` est un intermédiaire du pipeline médaillon, **hors du périmètre de gouvernance canonique** du présent ADR (seul `ba493568`, empreinte du `ml_dataset.parquet`, est le pointeur canonique gouverné). Elle est **figée en entrée** des figures (prise telle quelle sur disque) et ne fait l'objet d'**aucun contrat de reproductibilité propre** : sa reconstruction dépendrait d'un run complet du pipeline (hors périmètre du chantier figures, lecture seule), non rejoué ni re-vérifié ici. Elle est donc consignée comme non re-générable dans ce cadre, à la différence de `ba493568`.

**Validation par recoupement (deux ancrages indépendants).**
1. **Cardinalité** : `stage_09` restreint à H16-H24 compte **2 051 510** observations, identique au chiffre déclaré par ADR-027 (l.20 : « 2 051 510 observations dans stage_09 »).
2. **Identité octet à octet du sous-ensemble courant** : la cible `target_voyageurs_2eme_classe` de `stage_09` sur H22, H23, H24, H25 est **identique ligne à ligne** à celle du canonique `ba493568` (cross-check 4/4 années : effectifs 161 597 / 335 426 / 335 709 / 309 252, séries triées égales).

**Surveillance.** `954135f9` est ajoutée à `scripts/check_hash_propagation.py` comme empreinte de **source figée** (règle positive de présence : attendue dans le présent ADR et dans le générateur `docs/memoire/figures/section_4_5_1/make_fig_4_5_1.py`), distincte des empreintes canoniques supersédées surveillées par la règle A (elle n'est pas « périmée » : sa présence est requise, pas proscrite).

**Convention inchangée.** La convention de hachage (SHA256[:8] sur les octets du parquet, pyarrow 21.0.0) reste celle du présent ADR ; cet addendum n'ajoute qu'un registre de source figée, il ne modifie ni la gouvernance canonique ni les empreintes historiques.
