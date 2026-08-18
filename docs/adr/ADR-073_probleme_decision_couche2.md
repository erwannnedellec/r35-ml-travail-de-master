---
id: ADR-073
ancien_id: ADR-44
date_decision: 2026-07-04
statut: amendé
amende_par: [ADR-077]
modifie: [ADR-049]
chiffres_perimes: [gel]
corroboration_date: dépôt de travail, commit du 2026-07-04
gel_registre: 2026-08-16
---

# ADR-073 — Problème de décision de la couche 2 : seuillage calibré des prédictions couche 1 au grain course (POC d'aide à la décision)

> **État au gel de la remise (2026-08-16) — statut : amendé.**
> Cette décision a été amendée par ADR-077.
> Les chiffres de ce document relèvent d'une **génération du jeu de données antérieure au gel canonique `ba493568`** (ADR-076) ; ils ne sont pas réalignés.
> Décisions antérieures que ce document modifie : ADR-049.
> **Précision au gel.** Le point de référence désigné en fin de document (règle a′ iso-volume seule) est remplacé par **a′ ∪ plancher** ; la configuration de déploiement recommandée est **c ∪ plancher** (ADR-077).
> **Précision au gel.** Ce document écarte la projection contrefactuelle du modèle au grain du bloc d'accouplement **du protocole d'évaluation qu'il arrête**, et en conclut que la comparaison à cette borne reste « indicative, non conclusive ». Cette projection a été **conduite après le gel de l'artefact**, comme analyse d'évaluation du mémoire (§4.7.2, lecture à deux grains) : la configuration de déploiement y atteint 72,3 % de précision et 31,4 % de rappel au grain du bloc, contre 58,9 % et 6,0 % pour la pratique. Elle est produite en lecture seule, sous garde d'empreinte `ba493568`, par `docs/memoire/verifs/section_4_7/v6_grain_bloc.py` (2026-08-05, dépôt de travail), et ne modifie ni l'artefact ni le protocole arrêtés ici : la réserve ci-dessous est levée par une analyse d'évaluation postérieure, non par une décision de conception ultérieure. Détail en ADR-078 §4.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | **Accepté** — 2026-07-04 (E. Nédellec, après double relecture) |
| **Date** | 2026-07-04 |
| **Décideur** | Erwann Nédellec (data lead R35) |
| **ADRs liés** | ADR-033 (pivot : augmentation métier couche 2), ADR-005 / ADR-060 (seuil 63), ADR-049 (segmentation BAS/HAUT), ADR-052 (hyperparamètres), ADR-007 (rotations = source de décision UM), ADR-030 / ADR-031 (découplage R²/rappel, plafond de séparabilité), ADR-035 / ADR-036 (réservations, modèle de référence), ADR-038 (extension périmètre H25) |
| **Version modèle couche 1** | Enrichi_Seg v1.9 (158 features, Split C, hash dataset `416bb90b`) — **consommée en lecture seule** |
| **Nature** | Décision d'**architecture** de la couche de décision + **protocole d'évaluation**. **Aucun changement couche 1** (ni features, ni pipeline, ni hyperparamètres, ni hash). |
| **Artefacts** | Module baseline `src/couche2/blocs.py` → `baseline_um_canonique.json` (SHA256 `5874cb14…`) ; tests `tests/couche2/test_blocs.py` (19, verts). |

---

## Contexte

Le pivot **ADR-033** a acté que le plafond de séparabilité des surcharges (PR-AUC HAUT ≈ 0,345,
signal disponible à J-1) est une **limite informationnelle**, pas algorithmique. La réponse n'est
donc pas une nouvelle architecture ML mais une **couche de décision** (couche 2) qui transforme les
prédictions figées de la couche 1 en une **recommandation d'unité multiple (UM)** exploitable, et
qui se compare au **comportement humain passé** (référentiel établi par `src/couche2/blocs.py`).

La couche 1 est **figée** (v1.9, hash `416bb90b`) : la couche 2 la consomme, ne la réentraîne pas,
ne touche ni aux features ni au pipeline. Le présent ADR fixe le **problème de décision**, le
**protocole d'évaluation** et les **limites assumées** de la couche 2, avant toute implémentation.

---

## Décision (D1–D7)

**D1 — Nature.** La couche 2 est un **seuillage calibré des prédictions couche 1 au grain course**.
C'est un **POC d'aide à la décision**. Elle **n'inclut ni optimisation par chaîne, ni simulation de
faisabilité opérationnelle** (découplage, disponibilité du matériel roulant, contraintes de
roulement) : ces contraintes relèvent du métier, **par conception**.

**D2 — Label positif (vérité terrain).** Une course est **positive** si **au moins un de ses
tronçons observés** dépasse **63 voyageurs** en 2ᵉ classe (places assises, ADR-060).

**D3 — Score de décision.** Le score d'une course est le **maximum des prédictions couche 1** sur
ses tronçons.

**D4 — Calibration causale.** Tout **paramètre de l'artefact** (seuils de score, points d'opération
déployables) est calibré sur **H24 uniquement**, en **walk-forward temporel**. **Aucun paramètre
n'est jamais ajusté sur H25.** H25 est lu **une seule fois** en lecture finale. *Distinction (R6) :
le **top-k au budget humain H25 (k = 418)** utilisé pour la comparaison headline n'est **pas** un
paramètre de l'artefact — c'est une **constante du protocole de comparaison** (volume d'engagement
emprunté au côté **humain**), qui **n'utilise pas les labels H25** et ne contrevient donc pas à D4
(voir Conséquences).*

**D5 — Comparaison à l'humain : iso-budget et iso-périmètre (sur H25).** Voir section dédiée. Le
**budget** = nombre de courses-UM humaines **dans H25** = **418** (et non 883, qui est la période
totale). La précision et le rappel humains de référence sont recalculés **sur H25 seul** :
**précision 33,5 % (140/418)**, **rappel 6,8 % (140/2072)**. La comparaison porte sur le **couple
précision-rappel**, pas sur la précision seule. Ce **top-k = 418 est la constante de comparaison
headline** (protocole, côté humain) ; il est **distinct des seuils déployables du menu**, calibrés sur
H24 (D4, Conséquences R6).

**D6 — Hiérarchie des grains.** **Course = headline** (grain de la décision et de l'évaluation).
**Bloc = lecture conséquence** (grain de la décision d'accouplement), lu en **fourchette H25** côté
humain **[canonique 58,9 % (246/418) ; sensibilité 66,7 % (279/418)]** (pour mémoire, *période
totale* : 40,5 % / 45,7 %). **Tour = annexe diagnostique uniquement**, **toujours étiqueté
« permissif »**, et — s'il est présenté — calculé avec la **même agrégation des deux côtés**.

**D7 — Contribution de la couche 2.** La valeur ajoutée est la **formalisation de la décision, le
choix explicite du point d'opération et la transparence** — **pas un gain de détection**. La couche 2
**hérite du plafond PR-AUC HAUT ≈ 0,345** de la couche 1, et la documentation le dit explicitement.

---

## Convention de bloc (grain « lecture conséquence »)

Le grain bloc mesure l'**effet d'héritage** : la composition UM est décidée par anticipation et
**héritée le long du roulement** (une rame accouplée n'est décrochée qu'à Vevey ou Blonay). Un bloc
regroupe donc les courses d'**une même décision d'accouplement**.

**(a) Clé = identité de composition, course atomique.** Un bloc est une suite maximale de courses
consécutives d'un même véhicule dont l'**ensemble accouplé est identique** ; un **changement de
partenaire** en cours de journée (ex. 7501+7502 → 7501+7506) **ferme le bloc** — ce sont deux
décisions distinctes. La signature d'une course = ensemble accouplé **maximal** (segment UM).

**(b) Structure physique complète.** La consécutivité est établie sur **toutes** les courses rail du
véhicule (y compris sans mesure APC), ordonnées par l'**horaire réel istdaten** ; tie-break
déterministe **[heure de départ, numéro de train]**.

**(c) Comptage mesuré uniquement.** Numérateur **et** dénominateur restreints aux **881 courses UM
appariées APC**. Les UM non mesurées structurent les chaînes mais ne sont jamais comptées.

**(d) Sémantique d'UM = set-dedup.** Une UM = **≥ 2 rames rail distinctes** (série 7501–7508). Un
numéro écrit deux fois (« 7508,7508 ») = une seule rame = course **simple**. Compte canonique
(*période totale*) : **914 UM / 881 appariées** APC ; dont **418 UM en H25** (budget D5).

**Cas particuliers documentés.**
- **77 courses UM « partielles »** (renfort accouplé/découplé à Blonay : UM sur une jambe, simple sur
  l'autre — 77/914) : traitées comme **UM à part entière** (course atomique), rattachées au bloc de
  leur signature ; la jambe simple n'ouvre pas de sous-bloc (convention identique à `is_UM = OR` sur
  les segments).
- **2 anomalies de saisie** (service 1334 BLON→VV : `7508,7508` le 2023-11-24, `7506,7506` le
  2024-06-26) : **doublons d'écriture** reclassés en unité simple par le set-dedup, sans correction de
  donnée. Un **garde-fou** (`blocs.py`) lève une erreur sur tout **nouveau** doublon.

**Séquence chronologique et non-révisabilité (E2).** La convention (a)–(d) a été **actée *ex ante*** sur
un argument de principe (« un bloc = une décision d'accouplement »), **avant** l'observation des
chiffres. Les valeurs de justification bloc (**40,5 %** *période totale* ; **58,9 %** restreinte à
H25) en sont le résultat **constaté *ex post***. La convention **n'est plus rediscutable après
observation des chiffres**, dans un sens comme dans l'autre.

**Garde-fou de robustesse (E1).** La variante **consécutivité simple** est **conservée et étiquetée**
dans `baseline_um_canonique.json` à côté de la canonique, aux deux périmètres :
*période totale* 45,7 % (403/881, 532 blocs) vs 40,5 % (357/881, 621 blocs) ; **H25** 66,7 % (279/418)
vs 58,9 % (246/418). L'écart canonique↔sensibilité en *période totale* (−5,2 pts, 46 courses) est
intégralement tracé (`e3_courses_perdant_justification.csv`) : ce sont des courses **non surchargées**
dont l'héritage traversait un changement de partenaire.

---

## Référence de comparaison (D5) — iso-budget et iso-périmètre H25

**Iso-budget (comparaison headline).** Le modèle est classé par score (D3) ; on retient le **top-k au
budget humain H25** (**k = 418** courses-UM). C'est une **constante de protocole** (volume emprunté au
côté humain, sans labels H25), **pas un seuil déployable** (R6). Précision/rappel au **grain course**
(headline), en global et par segment BAS/HAUT. **Départage déterministe du classement**
(reproductibilité byte-exact, R3) : **score décroissant, puis tie-break `[date, numero_train]`** ; la
k-ième course est incluse selon ce même ordre (pas d'ex æquo ambigu au budget).

**Barre humaine H25 (grain course, n bruts — précision ET rappel, R4).**

| | budget UM (VP+FP) | VP | FP | FN | n surcharges (VP+FN) | précision | rappel |
|---|---|---|---|---|---|---|---|
| **Global** | **418** | 140 | 278 | 1 932 | 2 072 | **33,5 %** (140/418) | **6,8 %** (140/2072) |
| HAUT | 328 | 138 | 190 | 1 086 | 1 224 | 42,1 % (138/328) | 11,3 % (138/1224) |
| BAS | 90 | 2 | 88 | 846 | 848 | 2,2 % (2/90) | 0,24 % (2/848) |

Le **23,0 %** (*période totale*, précision course) est rapporté mais **n'est PAS la barre** de
comparaison.

**Iso-périmètre H25 = 29 222 courses** (vérifié, précondition C2) : intersection stricte
**prédiction couche 1 (`ml_dataset`) ∩ décision UM humaine (rotations) ∩ label observé (APC)**. Toutes
les **418 UM humaines** et les **29 222 courses** de la baseline H25 sont présentes dans le
`ml_dataset` (bornes identiques 2024-12-15 → 2025-12-13). **2 courses** présentes dans `ml_dataset`
mais absentes des rotations (2025-09-15 t1312, 2025-11-16 t1415 ; toutes deux **non surchargées**,
décision UM indéfinie) sont **exclues** du périmètre de comparaison (immatériel).

**Lecture conséquence (bloc), côté humain uniquement.** Le résultat course du modèle est lu contre
la **fourchette humaine H25 au grain bloc** **[58,9 % (246/418) ; 66,7 % (279/418)]**, **sans
projection du modèle** (voir alternatives écartées). *(Ces valeurs sont restreintes à H25 ; la
fourchette de période totale — 40,5 % / 45,7 % — est nettement plus basse, l'écart reflétant le
**label shift** de prévalence H25.)* Interprétation : le grain course **sous-estime** la qualité
décisionnelle humaine (courses héritées subies, non décidées) ; le bloc la mesure au niveau de la
décision d'accouplement. L'absence de projection bloc côté modèle rend la comparaison à cette borne
**indicative, non conclusive**.

---

## Segments et UM de repositionnement (E6)

- L'évaluation **headline est GLOBALE** (grain course, iso-budget). Les lectures **BAS et HAUT** sont
  rapportées **systématiquement, à statut égal** : aucun segment n'est désigné comme référence
  prioritaire. Le bas de ligne (pendulaire Vevey–Blonay) concentre l'essentiel du trafic ; le haut
  (touristique) a ses dynamiques propres ; les surcharges des deux segments ont le **même statut**.
- **Caveat baseline humaine BAS.** La précision humaine de **2,2 % en BAS (H25)** (rappel 0,24 %) est
  **structurellement déprimée** par les **UM de repositionnement** (service **1334**, dépôt de
  Blonay), qui ne sont **pas des décisions de demande**. Ce chiffre **sous-estime** la qualité
  décisionnelle humaine sur ce segment et doit être lu avec cette réserve. Le **42,1 % HAUT (H25)**
  (rappel 11,3 %) n'est **pas** affecté par cet artefact.
- Les UM de repositionnement **restent dans la population** de comparaison (pas d'exclusion) ; la
  réserve est portée par le **texte**, pas par un retraitement des données.
- Les 2 anomalies de saisie ci-dessus concernent **le même service 1334** : **qualité de saisie à
  surveiller** sur ce service.

---

## Alternatives écartées

**A1 — Projection contrefactuelle du modèle au grain bloc.** *Écartée.* Projeter les recommandations
du modèle sur des blocs (pour un chiffre « bloc » côté modèle) suppose de **reconstruire des blocs
contrefactuels** à partir de décisions que le modèle n'a pas prises — **coût** et **fragilité
d'hypothèse** élevés (points de découplage non modélisés). **Remplacée** par la **lecture en
fourchette** (D5) : le modèle (course) est lu contre l'intervalle bloc **humain**.

**A2 — Optimisation par chaîne / roulement.** *Écartée du POC, documentée en perspective.* Optimiser
la décision au niveau du **roulement** plutôt que de la course isolée est méthodologiquement possible
et l'**information existe à J-1** : le roulement planifié est connu **~J-20 h** via la séance
**GOP-CAT**. C'est une **piste d'extension** réaliste, mais **hors périmètre** du POC (D1), qui reste
au grain course pour la clarté décisionnelle et l'auditabilité.

**A3 — Grain tour comme barre de comparaison.** *Écartée.* Le grain tour (**73,4 %**, *période totale*,
1 047 tours UM) est **permissif** par construction (un tour est justifié dès qu'une de ses courses
surcharge) ; il **reproduit l'ancien 72,7 %** et sert **uniquement de diagnostic**, jamais de barre
(D6).

---

## Limites assumées

- **Plafond de détection hérité (D7).** La couche 2 hérite du plafond **PR-AUC HAUT ≈ 0,345**
  (signal J-1) ; elle **ne relève pas la détection**. Sa contribution est décisionnelle
  (formalisation, point d'opération, transparence).
- **Propagation bloc = chaînage observé, côté humain uniquement.** L'héritage bloc est reconstruit
  par chaînage des compositions **observées** (rotations + istdaten), **sans modélisation des points
  de découplage**. Aucune projection bloc n'est faite côté modèle.
- **Caveat label shift.** La tendance annuelle apparente (précision course H24 ~14 % → H25 ~33 %) est
  **en partie mécanique** : la **prévalence des surcharges est plus élevée en H25** (~×1,93 en
  tronçon) et, à comportement d'engagement constant, la précision apparente **monte avec la
  prévalence**. À lire comme « précision apparente en hausse, **en partie portée par la prévalence** »,
  **pas** comme une amélioration décisionnelle avérée.
- **Hypothèse d'inélasticité** de la demande à la capacité (la charge observée en UM aurait été la
  même en rame simple) — non testable ici, assumée.
- **Couverture APC réduite à l'automne 2025** (~75 % vs ~95 %) : échantillon H25 partiel sur les
  derniers mois ; ne pas sur-lire H25 Q3-Q4.

---

## Conséquences

- **Phase 2** (implémentation) : `src/couche2/decision.py` (chargement prédictions v1.9 H24/H25,
  agrégation max D3, label D2), calibration H24 walk-forward (D4), évaluation H25 unique (D5) sur le
  **périmètre iso 29 222**.
- **Deux objets distincts (R6) — à ne pas confondre.**
  - **Top-k protocolaire (comparaison headline).** Le **top-k au budget humain H25 (k = 418)** est une
    **constante du protocole de comparaison**, définie par la baseline **humaine** — **pas un paramètre
    de l'artefact**. Il n'est **pas « calibré »** et **ne contrevient pas à D4** : il **emprunte au côté
    humain le volume d'engagement** pour rendre la comparaison équitable, **sans utiliser les labels
    H25**. C'est la lecture **headline** (modèle vs humain, à volume égal).
  - **Points d'opération DÉPLOYABLES (menu métier), calibrés sur H24 (D4).** Seuils sur le **score**,
    réalistes en production (ne connaissent pas le budget H25 a priori) : **(a′) iso-volume** — seuil
    H24 tel que le **volume de recommandations = budget humain H24 (381)**, **appliqué tel quel à H25**
    (volume H25 résultant **proche de 418 mais non contraint**) ; **(b) rappel renforcé** (seuil
    abaissé — plus de détections, plus de FP) ; **(c) haute précision** (seuil relevé — moins de FP).
  - **Choix final** du point déployable : **pas statistique** — **ratio de coûts FN:FP élicité auprès
    du responsable de production** (Responsable de production, MOB), **consigné dans un mémo daté**. La couche 2 fournit la
    **courbe et la transparence** ; le métier tranche. Le **menu** (et non un point unique) est
    **présenté en évaluation organisationnelle** (cf. guide d'entretien §2.3).
- **Sorties D5 séparées.** `q_couche2_eval_416bb90b.json` et les figures rapportent **distinctement**
  (i) le **top-k protocolaire** (k = 418, comparaison headline vs humain) et (ii) les **trois seuils
  déployables** (a′ / b / c, menu métier) — jamais mélangés. Tous n bruts.
- **Tests** exigés : label course (D2), agrégation max (D3), respect du budget (D5),
  **non-contamination H25** (aucun paramètre dérivé de H25, D4).
- **Aucun impact couche 1** : hash `416bb90b` inchangé, vérifié par assertion en tête de chaque
  script couche 2.
- Intégration au digest `ALL_ADRS.md` **après passage en Accepté**.

---

## Addendum post-acceptation (2026-07-04, pré-lecture H25)

*Ajouté **après acceptation** et **avant toute lecture des résultats H25**, dans le cadre de la
phase 2 (P1 / verrouillage V-lock). N'édite pas le corps accepté ci-dessus ; le complète.*

- **Calibration in-sample (H24 ∈ train Split C).** Les prédictions couche 1 sur H24 sont **in-sample**.
  Le « walk-forward H24 » teste la **stabilité de seuils globaux entre sous-périodes de H24** (modèle
  figé), **pas** une validation séquentielle ni une causalité d'apprentissage. Les précisions H24 (ex.
  99,0 % à l'iso-volume) sont **in-sample** et ne se transfèrent pas telles quelles.
- **Décalage de scores H24→H25.** Diagnostic **sans labels** (scores disponibles à J-1) : les scores
  H25 sont plus bas (~6 pts au sommet de distribution). Ce décalage **confond optimisme in-sample et
  drift de population** — **indissociables sans labels H25** ; aucune attribution unilatérale.
- **Règles de rang.** Les trois règles déployables sont **exprimées en rang/volume** (quantiles de
  score H24), pas en score absolu, pour atténuer le risque de transfert.
- **Convention de transfert (V2, verrouillée).** En évaluation H25, **deux** conventions sont
  rapportées : **(i) seuil figé** = lecture de **déployabilité** (primaire pour le menu métier ; la
  sous-recommandation attendue — ~253 vs budget 418 — est un **résultat** de dérive de calibration en
  déploiement, motivant une **recalibration périodique** ; perspective : quantile glissant sur fenêtre
  écoulée, déployable à J-1) ; **(ii) rang annuel** = lecture **diagnostic de drift**, étiquetée
  « **convention d'évaluation, non déployable telle quelle** » (le rang dans la distribution annuelle
  H25 n'est pas connaissable à J-1). **Aucune des deux n'est le headline** : le headline reste le
  **top-k protocolaire k = 418** (R6). Cette hiérarchie **ne change pas** après lecture des résultats.
- **Limitation assumée (P1).** Seuils calibrés sur prédictions **in-sample** ; risque de transfert
  documenté ; atténué par règles de rang ; convention de transfert V2 ci-dessus.

---

## Addendum post-lecture H25 (2026-07-04) — plancher de demande annoncée (candidat au menu déployable)

*Chronologie : ajouté **après** la lecture des résultats H25 (phase 2.3), comme composant **candidat**
du menu déployable. **Statut : à valider en entretien (A17).** N'édite pas le corps accepté.*

- **Règle candidate.** « **Plancher de demande annoncée** » : recommander toute course dont la
  **réservation 2ᵉ classe à J-1** (`resa_pax_2c_J_minus_1`) dépasse la **capacité assise** (> 63). Il ne
  s'agit **pas d'une garantie** (voir taux de réalisation).
- **Justification a priori** (indépendante des résultats H25) : une **demande annoncée** supérieure à la
  capacité assise **exige une réponse** — signal **déterministe** de niveau opérationnel, **orthogonal**
  au score prédictif (histo-piloté).
- **Chiffres H25 en appui (X6, n bruts).** 154 courses résa>63 (142 HAUT / 12 BAS) ; **taux de
  réalisation 64 %** (99/154 ; H24 : 70 %, 64/92) → **no-show/annulation implicite ~30-36 %** (d'où
  « plancher de demande annoncée », pas une garantie). Croisement top-418 : **94 déjà couvertes**
  (redondance), **60 d'apport propre** (hors top-418, majoritairement HAUT), dont **31 surcharges
  réalisées**.
- **Architecture cible (si retenue).** **Plancher déterministe du menu déployable** : la règle **force**
  la recommandation (demande annoncée > capacité), le score la **complète** ; **jamais fondue dans le
  top-k protocolaire** (comparaison headline). Complémentaire au score histo-piloté, qui rattrape les
  nouveaux services en ~1 mois (addendum 1 / X9).

---

## Addendum post-lecture H25 (2026-07-05) — remplacement de la comparaison headline D5

*Chronologie : ajouté **après** la lecture des résultats H25. **Aucun recalcul, aucun résultat
préenregistré supprimé** : le top-k=418 reste intégralement rapporté en **annexe**. On change la
**lecture principale**, pas les nombres.*

- **Décision.** La comparaison **iso-budget top-k = 418** (préenregistrée et exécutée) est **remplacée
  comme lecture principale** par la comparaison à **points d'opération naturels** : les **matrices de
  confusion des règles déployables** (a′, b, c — **seuil figé**) **+ le plancher de demande annoncée**,
  **chacune à son volume propre**, contre la **pratique humaine H25 observée** (418 UM, précision course
  **33,5 %** / rappel **6,8 %**).
- **Critère de validité (dominance).** Une règle est validée si elle **domine simultanément** le point
  humain sur **précision ET rappel**. Résultat H25 (seuil figé) :

  | Point d'opération (seuil figé, H25) | volume | VP | FP | précision | rappel | domine (P>33,5 % ET R>6,8 %) |
  |---|---|---|---|---|---|---|
  | **(a′) iso-volume** | **253** | 216 | 37 | **85,4 %** | **10,4 %** | **✓✓ — à volume INFÉRIEUR à la pratique (253 < 418)** |
  | (b) rappel renforcé | 2 564 | 1 289 | 1 275 | 50,3 % | 62,2 % | ✓✓ |
  | (c) haute précision | 848 | 611 | 237 | 72,1 % | 29,5 % | ✓✓ |
  | plancher de demande annoncée | 154 | 99 | 55 | 64,3 % | 4,8 % | **complément** (rappel < humain, jamais seul) |
  | **artefact complet (a′ ∪ plancher) — RÉFÉRENCE** | **353** | 275 | 78 | **77,9 %** | **13,3 %** | **✓✓** |

  Le fait le plus fort : **(a′) domine l'humain en engageant MOINS de courses** (253 vs 418).

  **Discipline de dominance (F1).** La dominance simultanée précision **ET** rappel ne s'applique qu'aux
  **trois règles de score (a′, b, c)**. Le **plancher seul ne domine PAS** (rappel 4,8 % < 6,8 %) : c'est un
  **filet complémentaire** — couverture du **risque de demande annoncée que le score manque** (X6 : 60 courses
  HAUT hors classement) — **jamais déployé seul**. L'**artefact complet** = **score (a′) ∪ plancher** : à
  **volume 353** (recouvrement : 199 a′ seul + 100 plancher seul + 54 communs), il **domine** l'humain
  (77,9 % / 13,3 %) et constitue le **point de référence** rapporté en lecture principale et sur les supports
  d'entretien (3.3).
- **Motif.** Le **volume humain (418) n'est pas une enveloppe allouée** mais la **résultante de contraintes
  locales** (matériel disponible, roulements, maintenance). La contrainte **iso-volume n'a donc pas
  d'interprétation opérationnelle** ; comparer à volume égal impose au modèle une contrainte que
  l'exploitant ne subit pas comme un budget. Les points d'opération **déployables** (seuils calibrés H24)
  sont la lecture pertinente.
- **Intégrité du préenregistrement.** Le top-k=418 (résultats P=82,1 % / R=16,6 %) **reste rapporté** dans
  le JSON canonique et **en annexe du notebook**, avec mention de statut, **sans rôle narratif**. Rien
  n'est supprimé ; la transparence du protocole préenregistré est préservée.

### Point d'opération de référence de l'artefact

En attendant le **choix du métier en entretien (A17)**, le **point de référence** de l'artefact est la
règle **(a′) iso-volume** : **calibrée sur H24**, seuil ancré sur le **volume de pratique H24 = 381**
(déployable, ne connaît pas le budget H25 a priori), **appliquée à H25** (volume résultant 253). C'est le
point **le plus conservateur** (précision 85,4 %, volume inférieur à la pratique) et le plus directement
**déployable**. Les règles (b)/(c) et le plancher restent au menu pour l'arbitrage coût FN:FP.
