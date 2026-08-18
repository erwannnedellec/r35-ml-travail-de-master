# CHANTIER FEATURES — Phase A : vacances & fériés cantonaux (VS, FR, NE, GE)

**Statut : construction + contrôle qualité terminés. ARRÊT avant tout test d'impact.**
Espace dédié `exp_features/` — **hors canonique**. Le hash `416bb90b` et le
`ml_dataset` canonique ne sont **pas** touchés. Aucune jointure, aucun entraînement.
`cal_type_jour` et les features vaudoises existantes sont intactes — les 8 nouvelles
features sont purement additionnelles.

## Livrables
| Fichier | Contenu |
|---|---|
| `exp_features/parse_valais.py` | Parseur PDF Valais (rects vectoriels colorés → jour de classe / férié / congé) |
| `exp_features/build_cantonal_features.py` | Construction des 8 features binaires (grain journalier) |
| `exp_features/qc_report.py` | Contrôle qualité (couverture, plausibilité, corrélations) |
| `exp_features/outputs/features_vacances_feries_cantonales.parquet` / `.csv` | **8 features**, `date` + 8 colonnes binaires, 2021-12-01 → 2025-12-31 (1492 j) |
| `exp_features/outputs/audit_periodes_vacances.csv` | 84 périodes de vacances reconstruites (début/fin/durée) |
| `exp_features/outputs/audit_feries.csv` | 183 jours fériés (date + jour de semaine) |

Features : `event_is_vacances_{valais,fribourg,neuchatel,geneve}`,
`event_is_ferie_{valais,fribourg,neuchatel,geneve}` — nommage en toutes lettres,
cohérent avec `event_is_vacances_vaud` / `event_is_ferie_vaud`.

Plage cible (dataset canonique) : **2021-12-12 → 2025-12-13**. Couverture requise =
années scolaires 2021-2022 → 2025-2026.

---

## ÉTAPE 1 — Inventaire des sources

| Canton | Fichiers | Format | Couverture AS | Statut |
|---|---|---|---|---|
| **Valais** | 5 `DEF-PlanDeScolarite*` (+ 2017-2021) | PDF (calendrier colorié) | 2021-22 → 2025-26 | ✅ complet |
| **Fribourg** | `calendrier_20-25_majoritaire_corrigé_2.xlsx`, `calendrier-general-20252030.xlsx` | XLSX (périodes explicites) | 2020-21 → 2029-30 | ✅ complet |
| **Neuchâtel** | `410.562.pdf` (+ arrêté 2014-2024) | PDF (table d'arrêté) | 2019-20 → 2029-30 | ✅ complet |
| **Genève** | `calendrier_vacances_scolaires_{2021_2022, 2022_2023, 2023_2024, 2025_2026}.pdf` | PDF (grille + bloc texte) | 2021-22 → 2025-26 | ✅ complet* |

**Lacunes signalées :**
- **Genève — dossier initialement vide** (ajouté en cours de chantier par l'utilisateur).
- **Genève — pas de PDF autonome 2024-2025.** Résolu sans recours externe :
  chaque PDF genevois liste **aussi l'année n+1** ; le PDF 2023-2024 fournit donc
  les dates 2024-2025 (colonne droite). La **rentrée 2024 (lun. 26.08.2024)**, non
  listée localement, a été confirmée sur le calendrier officiel ge.ch.
- **Genève 2025-2026** : texte du PDF illisible (encodage de police CID) ; dates
  relues sur le **rendu image** du même PDF local + recoupées ge.ch.
- Aucune **asymétrie train/test** : les 4 cantons couvrent H22→H25 de façon
  symétrique (cf. ÉTAPE 5 §5).

---

## ÉTAPE 2 — Périodes de vacances extraites (méthode par canton)

- **Valais** — *parsing du document colorié* : les PDF n'indiquent pas de dates,
  ils colorient les jours (bleu/jaune = classe, **orange = férié cantonal**, blanc =
  congé). Le parseur extrait les rectangles vectoriels colorés et les positionne sur
  la grille. **Datation par position** (k-ᵉ occurrence du jour de semaine dans le
  mois) et non par le chiffre imprimé → robuste aux **coquilles source** détectées
  (ex. PDF 2023-2024 : « 25 » imprimé à la place de « 15 » un jeudi de février).
  Validation : **0 incohérence jour/position** sur les 5 fichiers, et **totaux
  mensuels de jours de classe reproduits exactement** (checksum imprimé sur chaque
  calendrier). Vacances = blocs ≥ 4 jours ouvrables non-classe ; été = intervalle
  entre fichiers consécutifs (couvre juillet, absent des grilles).
- **Fribourg** — périodes explicites des XLSX (calendrier *majoritaire francophone*,
  onglet par année). Été = (dernier jour de classe +1) → (rentrée suivante −1).
- **Neuchâtel** — périodes explicites de la table de l'arrêté 410.562 (automne,
  Noël, « 1er mars »/février, printemps/Pâques, été).
- **Genève** — périodes explicites du bloc texte de chaque PDF (Jeûne genevois,
  automne, Noël, février, Pâques, été dès…). Été = (début) → (rentrée suivante −1).

**Plausibilité des dates : conforme.** Été ≈ juil.–août, Noël ≈ fin déc., etc.
Détail des 84 périodes : `outputs/audit_periodes_vacances.csv`. Exemples (2023-2024) :

| Période | Valais | Fribourg | Neuchâtel | Genève |
|---|---|---|---|---|
| Automne | 19→27 oct (9j) | 16→27 oct (12j) | 02→13 oct (12j) | 23→27 oct (**5j**) |
| Noël | 25/12→05/01 | 25/12→05/01 | 21/12→05/01 | 25/12→05/01 |
| Février/Carnaval | 12→16 fév (5j) | 12→16 fév (5j) | 26/02→01/03 | 19→23 fév |
| Pâques | 29/03→05/04 (8j) | 29/03→12/04 (**15j**) | 29/03→12/04 (15j) | 29/03→12/04 (15j) |
| Été | 22/06→18/08 (58j) | 06/07→21/08 (47j) | 08/07→16/08 (**40j**) | 01/07→25/08 (56j) |

Les écarts (automne court à Genève, Pâques courte au Valais, été court à Neuchâtel)
sont réels et expliquent les corrélations inter-cantonales **modérées** (§3).

---

## ÉTAPE 3 — Jours fériés cantonaux (disponibilité ex ante)

Tous fixés par **loi cantonale**, publiés des années à l'avance → **connus J-1, aucune
fuite**. Calculés analytiquement (Pâques grégorienne + dates fixes), recoupés aux
documents quand c'est possible.

| Canton | Jours fériés retenus | Spécificités | Source |
|---|---|---|---|
| **Valais** | Nouvel An, **St-Joseph 19/3**, Vendredi Saint, Lundi Pâques, Ascension, Lundi Pentecôte, **Fête-Dieu**, 1ᵉʳ août, **Assomption 15/8**, **Toussaint 1/11**, **Immaculée 8/12**, Noël | catholique (12/an) | **orange des PDF** (100 % confirmé) + loi VS |
| **Fribourg** | id. Valais **sans St-Joseph** (11/an) | catholique | XLSX (Toussaint, Immaculée, Ascension, Pentecôte, Fête-Dieu) + loi FR |
| **Neuchâtel** | Nouvel An, **2 janvier**, **1ᵉʳ Mars** (Instauration Rép.), Vendredi Saint, Lundi Pâques, **1ᵉʳ Mai**, Ascension, Lundi Pentecôte, 1ᵉʳ août, **Lundi du Jeûne fédéral**, Noël | protestant ; 1ᵉʳ Mars & 1ᵉʳ Mai propres (11/an) | arrêté 410.562 + loi NE |
| **Genève** | Nouvel An, Vendredi Saint, Lundi Pâques, **1ᵉʳ Mai**, Ascension, Lundi Pentecôte, 1ᵉʳ août, **Jeûne genevois**, Noël, **Restauration 31/12** | protestant ; Jeûne genevois & Restauration propres (10/an) | PDF (pastilles roses) + loi GE J 1 45 |

Recoupement Valais : **les 72 fériés analytiques tombant en jour ouvrable dans la
plage des documents sont tous marqués orange** (`orange_confirm_misses = []`).

**Points d'attention (à valider) :** NE `2 janvier` et `1er Mai`, GE `1er Mai` et
`Restauration 31/12` reposent sur la loi cantonale (non tous visibles dans les
documents scolaires). Le 1ᵉʳ Mai genevois est confirmé par les pastilles roses du PDF.

---

## ÉTAPE 4 — Construction

8 colonnes binaires `int8`, grain journalier, clé `date`, 1492 lignes
(2021-12-01 → 2025-12-31). Prêtes à joindre par date. **Non jointes.**

---

## ÉTAPE 5 — Rapport qualité (périmètre dataset 2021-12-12 → 2025-12-13, 1463 j)

**1. Couverture** — 0 NaN (features construites). Chaque canton a des vacances
**chaque année** (2021 partiel = Noël uniquement, normal) :

| année | VS | FR | NE | GE |
|---|---|---|---|---|
| 2022 | 89 | 92 | 82 | 81 |
| 2023 | 89 | 92 | 89 | 87 |
| 2024 | 94 | 93 | 86 | 95 |
| 2025 | 88 | 89 | 72 | 77 |

(2025 plus bas : la plage s'arrête au 13/12, avant les vacances de Noël.)

**2. Plausibilité** — % jours/an en vacances (années pleines 2022-2024) :
VS 24.8 %, FR 25.3 %, NE 23.4 %, GE 24.0 % → **conforme à l'attendu ~25-27 %**
(13-14 semaines). Fériés/an : VS 12, FR 11, NE 11, GE 10 → cohérent.

**3. Corrélation inter-cantonale** (jours ouvrables) :
- *Vacances* : **0.63 – 0.77** (NE le plus distinct). Calendriers romands proches
  mais **non redondants** → signal propre à chaque canton.
- *Fériés* : **VS–FR = 0.974** (deux calendriers catholiques quasi identiques —
  redondance à noter) ; NE–GE = 0.77 ; VS/FR–NE/GE ≈ 0.61-0.67.

**4. Corrélation avec le vaudois existant (crucial — redondance ?)** :

| | vs `…_vaud` (r) | jaccard |
|---|---|---|
| vacances VS / FR / NE / GE | 0.77 / 0.82 / 0.68 / 0.80 | 0.71 / 0.76 / 0.62 / 0.75 |
| fériés VS / FR / NE / GE | 0.67 / 0.69 / **0.91** / 0.74 | 0.51 / 0.53 / 0.84 / 0.60 |

→ **Aucune feature n'est quasi-identique (>0.95) au vaudois.** La plus proche est
`event_is_ferie_neuchatel` (r=0.91, calendriers protestants voisins) mais NE apporte
1ᵉʳ Mars/1ᵉʳ Mai. **Les 8 features portent une information incrémentale** vs le vaudois.

**5. Asymétrie train/test** (split H24/H25 ≈ 2024-12-15) — vacances de chaque côté :
VS 271/97, FR 276/98, NE 256/81, GE 262/86 → **aucune asymétrie** (bloquant écarté).

---

## Conclusion Phase A

8 features construites et vérifiées, sourcées et reproductibles, sans fuite (fériés
statutaires, vacances publiées à l'avance), sans NaN ni asymétrie train/test.
Redondances connues avant tout test : **VS≈FR sur les fériés** (r=0.97) et corrélation
notable mais < 0.95 partout vs le vaudois. **Features candidates non intégrées.**
**ARRÊT** : ni jointure, ni entraînement, ni test d'impact (Phase B ultérieure).
