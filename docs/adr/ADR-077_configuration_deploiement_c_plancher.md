---
id: ADR-077
ancien_id: aucun
date_decision: 2026-07-12
statut: actif
modifie: [ADR-073]
corroboration_date: en attente
gel_registre: 2026-08-16
---

# ADR-077 - Configuration de déploiement recommandée : règle c + plancher réservations

> **État au gel de la remise (2026-08-16) — statut : actif.**
> Décisions antérieures que ce document modifie : ADR-073.
> Le corps ci-dessous est **conservé dans sa rédaction d'origine** : conformément au principe
> du registre (mémoire, §3.3), un ADR consigne l'état du raisonnement au moment de la décision,
> et non une position finale continûment révisée. Chaîne complète dans [`INDEX.md`](INDEX.md).

| Champ | Valeur |
|---|---|
| **Statut** | Accepté le 2026-07-24 (addendum), proposé le 2026-07-12 |  <!-- statut d'époque ; état au gel : actif (voir bandeau) -->
| **Date** | 2026-07-12 |
| **Décideur** | Erwann Nédellec |
| **ADRs liés** | ADR-073 (problème de décision couche 2 : famille de points d'exploitation + plancher = l'ARTEFACT) ; ADR-076 (gel v2 `ba493568`) ; ADR-060 (seuil de surcharge 63) |
| **Génération** | `ba493568` (gel v2) |

---

## Contexte

L'artefact de couche 2 (ADR-073) est une **famille de points d'exploitation** (menu déployable a'/b/c) plus un **plancher de demande annoncée** (réservations J-1). Il ne prescrit pas un point unique : le choix relève des exigences métier. Deux exigences élicitées désignent une instanciation :

1. **Ratio de tolérance du décideur** (responsable de production, notes d'entretien informel de juillet 2026 ; hypothèses A16-A18 du guide v2.11) : précision **idéalement ~66 %**, **limite ~50 %**. Le point **c** (F0.5, precision-weighted, seuil H24 = 64,12) vise cette bande.
2. **Contrainte de conception (garantie des réservations)** : toute demande annoncée dépassant le seuil de places doit être garantie — une réservation est un **engagement commercial**. D'où le **plancher** `resa2c > 63`, uni au score.

D'où la configuration de déploiement : **recommandation = (score ≥ 64,12 au grain course, max tronçon) OU (resa2c > 63)**.

## Décision

La **configuration de déploiement recommandée** est **c ∪ plancher**. Ce n'est **ni une re-conception ni une re-calibration** : la famille de points et le plancher sont l'artefact (ADR-073) ; le seuil c est celui calibré sur H24 (ADR-073, inchangé) ; on **instancie** l'artefact selon les exigences ci-dessus.

**On AJOUTE une configuration, on ne remplace rien.** La configuration d'évaluation **a' ∪ plancher** (iso-volume, 352/77,8 %/13,2 %) conserve son rôle : **comparaison loyale à la pratique humaine** (même budget que les 418 UM). Les deux coexistent avec des fonctions distinctes (évaluation iso-volume vs déploiement).

## Chiffres H25 (grain course, iso-périmètre 29 222 courses / 2 072 surcharges, gardes tenues)

| Configuration (global) | volume | VP | FP | précision | rappel |
|---|---|---|---|---|---|
| **Déploiement c ∪ plancher** | **866** | 622 | 244 | **71,8 %** | **30,0 %** |
| c seul (F0.5) | 840 | 605 | 235 | 72,0 % | 29,2 % |
| a' ∪ plancher (évaluation iso-volume) | 352 | 274 | 78 | 77,8 % | 13,2 % |
| b (F2, rappel) | 2 563 | 1 292 | 1 271 | 50,4 % | 62,4 % |
| humaine (418 UM) | 418 | 140 | 278 | 33,5 % | 6,8 % |

Déploiement par segment : HAUT 395 / 68,6 % / 22,1 % ; BAS 471 / 74,5 % / 41,4 %.

**Recouvrement (H25)** : score seul **712**, plancher seul **26**, intersection **128**, union **866**. L'union ne s'extrapolait pas de a' ∪ plancher : à seuil c (64,12, plus bas que a' 78,99), le score capture déjà l'essentiel de ce que le plancher apportait à a' — le plancher n'ajoute que **26 courses propres** (contre 100 pour a').

**Rappels par strate H25** (déploiement / c seul / a'∪plancher) : 63-93 **24,8 %** / 24,0 % / 8,2 % ; 94-165 **56,2 %** / 55,0 % / 38,2 % ; 166+ **50,0 %** / 50,0 % / 33,3 %.

**Capture des 166+ (6 cas)** : l'union en capte **3/6**, tous par le **score** (les 6 cas ont `resa2c = 0`, le plancher n'ajoute rien sur cette queue). Détail : 206 (score 74,9, capté), 182 (95,7, capté), 167 (94,1, capté) ; 174 (62,0), 172 (57,9), 166 (57,9) non captés (score < 64,12, sans réservation).

**Coûts FP (volet B, tare 54,2 t × distance × 0,06444 CHF/tbkm — provenance en addendum du 2026-08-18)** : déploiement **244 FP / 6 922 CHF** (c seul 235 / 6 592 ; a'∪plancher 78 / 2 495 ; humaine 278 / 8 719).

## Cohérence de calibration (H24, constat, PAS re-calibration)

Sur H24 (année de calibration) : c seul **1 546 / 85,1 % / 55,3 %** ; c ∪ plancher **1 573 / 83,7 % / 55,3 %** (le plancher n'ajoute que 27 courses). La précision reste **au-dessus de la bande cible** (idéal 66 %, limite 50 %) sur l'année de calibration : la configuration est cohérente avec l'exigence de précision.

## Justification : le plancher, garantie inconditionnelle et non contribution statistique

Le recouvrement H25 le montre : à seuil c (64,12), le plancher n'apporte que **26 courses propres** (contre 100 à a') et ne capte **aucun des six 166+** (`resa2c = 0` sur les six). Le plancher est conservé **non pour sa contribution statistique** — marginale à ce seuil — **mais pour sa fonction de garantie inconditionnelle** : une réservation annoncée dépassant le seuil de places est un **engagement commercial**, garanti **par construction** (indépendamment du score du modèle). Sa **redondance croissante** quand le score devient plus sensible (de a' à c) est une **propriété de robustesse** — deux filets, l'un statistique (score), l'autre commercial (plancher) — **pas un défaut**.

## Pare-feu de restitution

L'évaluation naturaliste de mardi (Human Risk & Effectiveness) porte sur **cette configuration de déploiement**. Le **pare-feu de restitution** (guide 2.2) reste entier : ni la **justification chiffrée** du choix de c, ni la **cartographie des points d'exploitation** ne sont présentées avant ou pendant la section D de l'entretien.

## Sources datées et validation

- Notes d'entretien informel (ratio 66/50, juillet 2026).
- Contrainte de garantie des réservations (concepteur / responsable des données).
- Hypothèses **A16-A18** du guide d'entretien v2.11. **Leur validation formelle intervient à l'entretien de mardi** : si la grille les infirme, un **addendum post-entretien** est porté au présent ADR (la décision de configuration est alors ré-examinée).

- **Provenance de la convention de coût (addendum du 2026-08-18)** — tare de **54,2 t** : Stadler, esquisse-type ABeh 2/6 7500, plan n° BZ 2004242 indice c. Prix du sillon **0,06444 CHF/tbkm** : Transports Montreux-Vevey-Riviera SA, « MVR prix du sillon TRV 2025 », document interne, juillet 2024. Facteur agrégé 54,2 × 0,06444 = **3,4926 CHF/km de course**, arrondi à 3,49 au manuscrit (§4.7.2). Complément documentaire : aucune valeur ni décision du présent ADR n'est modifiée.

## Limites

Les **trois 166+ non captés** (2025-09-02 course 1508 ; 2025-05-18 course 1419 ; 2025-08-26 course 1508) ont tous `resa2c = 0` et des **scores 57-62** (sous le seuil c = 64,12) : **ni le filet commercial ni le filet statistique ne voient cette queue**. C'est la **démonstration empirique de la limite théorique** : un seuil sur une moyenne conditionnelle (le score de régression) ne **garantit pas les queues**. La **règle composite par quantile** (garantie sur les queues) reste le **travail futur désigné** ; renvoi à la discussion du mémoire.

## Addendum de formulation (2026-07-12, statut 166 clarifié par élicitation écrite) : définition et statut de la strate 166+

Formulation seule, aucun chiffre de la décision modifié.

**Cible mesurée contre la capacité d'une rame simple (non-circularité).** La strate 166+ (volet C) mesure la **demande** (charge 2ème classe réalisée au tronçon le plus chargé) rapportée à la **capacité de référence d'une rame simple**, indépendamment de la composition effectivement roulée. Justification : mesurer la surcharge contre la capacité roulée rendrait la cible circulaire ; les doublements décidés à bon escient effaceraient les positifs qu'ils traitent ; la demande est donc rapportée à la capacité de référence d'une rame simple. C'est déjà la logique du seuil de surcharge lui-même (63 places assises d'une rame simple, ADR-060), appliquée à la borne haute.

**Statut de la borne 166 (arbitrage 94/166/188 clos par élicitation écrite).** La borne 166 est la **conversion en personnes** (places debout comprises, hors strapontins, vélos et chaises roulantes) d'une **charge maximale admissible de 12,7 tonnes par rame**, définie par le responsable de production (élicitation écrite du 2026-07-09, citation intégrale au dossier d'élicitation `docs/entretiens/dossier_elicitation_deploiement.md`). La limite primaire est **massique** ; 166 en est la **projection conventionnelle** utilisée comme **seuil de planification**. L'écart apparent avec `src/r35/constants.py` (63 assises 2C, 94 d'offre APC totale, 188 pour une UM) est **clos** : 63 et 94 sont des capacités de **places**, 166 une limite de **masse convertie** — grandeurs différentes, aucune contradiction.

**Restent à établir en entretien (hypothèse A16).** (1) source documentaire du 12,7 t (fiche matériel 7500 ou prescription d'exploitation) ; (2) convention de conversion (poids moyen par personne) ; (3) statut opérationnel du dépassement en exploitation. **Amorce empirique** (annexe des cas d'entretien) : **4 des 6 occurrences 166+ ont roulé en rame simple** (dont une à 182), donc le comptage peut dépasser 166 sans que la marche soit empêchée — masse réelle inférieure au comptage, ou tolérance : à éliciter (troisième question A16).

## Addendum (2026-07-16) : renumérotation du guide d'entretien

Renumérotation du guide d'entretien (v2.15) : l'hypothèse **A16** citée dans l'addendum du 2026-07-12 est désormais **H7** ; table de correspondance dans la note de révision du guide. Le corps et l'addendum du 2026-07-12 ne sont pas réécrits (immutabilité de l'ADR) : cette note suffit à la traçabilité de l'identifiant.

## Conséquences

- Artefact `outputs/couche2/q_couche2_deploiement_ba493568.json` (mêmes gardes et meta que `q_couche2_eval`), canonique, généré par `scripts/experiences/deploiement_c_plancher_ba493568.py` (protocole préenregistré en tête).
- La configuration d'évaluation a' ∪ plancher est **inchangée** dans tous les documents existants.
- Chiffres H25 de l'union consignés ci-dessus (produits avant la sélection des cas d'entretien).

## Addendum (2026-07-24)

Statut porté de proposé à accepté. Les entretiens décideurs D01 et D02 (14.07.2026) et l'évaluation organisationnelle (mémoire, section 4.7.4) n'ont pas remis en cause la configuration c ∪ plancher, retenue comme configuration de déploiement recommandée. Deux conditions : la lecture calendaire post-hoc (mémoire, section 4.7.1) établit un rappel de week-end inférieur à la pratique pour les postures de parcimonie, motivant l'étude d'une politique de seuil différenciée par type de jour (recommandation, section 5.2) ; la confirmation sur une année horaire vierge reste requise avant industrialisation.
