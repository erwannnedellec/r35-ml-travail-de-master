# Annexe X : Catalogue et diagnostics des sources de données

Squelette de travail. Douze fiches normalisées, à remplir avant tout retrait de contenu du corps de la section 4.3. Version cible : intégration au docx après validation du contenu, en préservant les champs Zotero.

## Règles de remplissage (à supprimer avant intégration)

1. Ne pas copier-coller la prose retirée du corps : la convertir au format fiche (rubriques courtes, phrases denses, pas de narration).
2. Chaque valeur chiffrée est vérifiée contre les fichiers parquet canoniques ou le codebook `outputs/codebook_canonique_ba493568.csv` avant insertion. Marquer [à vérifier] tant que ce n'est pas fait.
3. Chaque fiche distingue deux blocs : le bloc A documente la source telle qu'elle existe (miroir de 4.3) ; le bloc B renvoie aux décisions et résultats (4.4 et suivantes, ADR). Aucune décision n'est énoncée dans le bloc A ; le bloc B ne fait que renvoyer, il ne réargumente pas. Cette séparation est le prolongement en annexe de la frontière 4.3/4.4.
4. Le statut dans le dispositif (bloc B) cite toujours la section du mémoire où la décision est établie et l'ADR correspondante. C'est ce renvoi qui rend légitime la présence du statut en annexe sans anachronisme.
5. Conventions : guillemets français, pas de tiret cadratin ni demi-cadratin, prose sans puces sauf énumérations de variables.
6. Les figures détaillées ne vivent pas dans les fiches : elles vont dans l'atlas EDA (annexe Y), la fiche y renvoie.

Note de remplissage (2026-07-11, mise à jour d'empreinte le 2026-07-30) : les valeurs chiffrées ci-dessous ont été vérifiées lors du remplissage contre les parquet canoniques et le codebook de la génération alors courante. La génération canonique est désormais `ba493568` (gel v2, ADR-076) et le codebook de référence est `outputs/codebook_canonique_ba493568.csv` ; le remplissage d'origine s'appuyait sur `codebook_canonique_416bb90b.csv`, génération supersédée. Trois écarts entre le squelette et le dépôt sont signalés en clair dans les fiches concernées (bascule ISTDATEN, couverture STATPOP, renvoi de section SIMBA). Les rubriques restées vides correspondent à des métadonnées que le projet ne documente pas (à sourcer dans la documentation OFS externe pour STATPOP et STATENT).

## Gabarit de fiche (référence)

**Bloc A : compréhension de la source**
Fournisseur et mode d'acquisition / Grain natif / Couverture temporelle / Volumétrie / Variables ou champs disponibles (familles) / Limites structurelles / Diagnostics empiriques de qualité (renvoi atlas) / Disponibilité à l'horizon J-1

**Bloc B : usage dans le dispositif (renvois uniquement)**
Transformations appliquées (renvoi 4.4.x) / Features produites (familles, renvoi codebook) / Statut dans le dispositif (renvoi section + ADR) / ADR associées

---

## Fiche S01 : Comptage automatique des voyageurs (APC / HOP-REP-WEB)

**Bloc A**
Fournisseur et acquisition : capteurs DILAX embarqués (SURF 7500), traitement Citisense, restitution HOP-REP-WEB (CFF). Export mesuré, équilibré, non extrapolé.
Grain natif : montées et descentes à l'arrêt ; charge au tronçon ; export jour × course × arrêt. Grain de la table canonique : course (`horaire_numero_train`) × tronçon (gare de départ, gare d'arrivée) × sens × date.
Couverture : H16 à H25, soit 2015-12-13 à 2025-12-13 (une année horaire Hnn débute mi-décembre de l'année civile nn-1). Couverture calendaire par année de 99,7 à 100 %, sauf H22 (92,0 %, cf. trou de septembre 2022).
Volumétrie : 267 Mo. Table canonique `apc_stacked` = 2 360 762 lignes (58 colonnes) ; périmètre de modélisation `ml_dataset` (filtre H22-H25) = 1 141 984 lignes, empreinte SHA256[:8] `ba493568`.
Contenu déplacé depuis le corps (triage validé) : mécanique optique détaillée des capteurs (faisceaux réfléchis, réflexions parasites, obstacles) ; horaires et lieux de dépôt FTP ; tableau des paramètres Citisense (ex-tableau 4.3, à insérer ici avec sa légende) ; détail de la liste 64 (délai de quinze jours, rôle de reporting).
Limites structurelles : incertitude métrologique intrinsèque des compteurs (bruit estimé de l'ordre de plus ou moins deux voyageurs, cohérent avec la tolérance connue des compteurs automatiques ; conservation montées-descentes exacte dans 96,7 % des transitions entre gares adjacentes, 99,8 % à plus ou moins deux voyageurs). Échecs d'appariement APC contre ISTDATEN : certaines rames circulent sans comptage, en particulier les navettes de bas de ligne le week-end (rames sans équipement AFZ) et les trains saisonniers estivaux H25. Publication mensuelle consolidée, sans canal plus fréquent.
Diagnostics empiriques : doublons de recouvrement calendaire entre fichiers d'export, 1 252 paires strictes concentrées sur exactement trois dates (2020-10-24 : 485 paires ; 2020-10-25 : 329 ; 2024-10-19 : 438) ; contenu identique, aucune observation réelle retirée (renvoi atlas). Taux de comptage effectif (TCE = courses comptées APC rapportées aux courses réellement effectuées d'après ISTDATEN non annulé) : global 74,1 %, période de référence stable H23-H24 95,7 %, chute structurelle le week-end sur le bas de ligne (samedi 66,3 %, dimanche 62,6 %) et sur les trains saisonniers H25 (juillet-novembre 75,5 % contre 94,6 % janvier-juin) (renvoi atlas). Colonnes de capacité (`base_offre_*`, taux d'occupation, taux d'équipement AFZ) invalidées comme variables : `base_offre_2eme_classe` est sur-déclarante et non vérifiée, contredite par le registre des rotations (99,3 % de concordance sur 40 797 course-jours, mais 45 unités multiples captées par les seules rotations que l'offre APC ne reflète pas) ; `tx_equipement_afz` est un marqueur de régime d'export (0 % jusqu'à H22 puis 100 % à partir de H23, bascule à la frontière des fichiers) et non une variable de qualité. Part de comptage automatique AFZ 99,77 % ; trou de 23 jours consécutifs, du 8 au 30 septembre 2022, 29 jours calendaires absents au total sur H22.
Disponibilité J-1 : non, lot mensuel publié trois jours après clôture du mois (mois M disponible à partir du 3 de M+1 ; latence observation-publication médiane de 18 jours).

**Bloc B**
Transformations : renvoi 4.4.x. Cutoff mensuel causal (ADR-062, remplace le décalage J-2 d'ADR-008) : la fenêtre `histo_*` s'arrête au dernier mois entièrement publié à la date de décision (veille du trajet), règle composée intégrant le délai de publication du 3 de M+1 plus un jour d'ingestion ; 6,84 % des lignes basculent sur M-2. Fenêtre `win7` (sept dernières occurrences). Dédoublonnage strict sur les 31 colonnes du schéma brut (`keep="first"`), retirant les 1 252 paires ci-dessus.
Features produites : famille `histo_` (charge à J-2 et statistiques de fenêtre 7 occurrences : `lag2`, `win7` moyenne, médiane, max, écart-type par classe, plus `win7_n_surcharges`) ; variable cible `target_voyageurs_2eme_classe` [renvoi codebook].
Statut : retenue, variable cible (notebook 02_data_understanding_apc §2.1.1 et section 4.4 ; ADR-001). Les colonnes de capacité `base_offre_*` sont conservées comme variables diagnostiques hors matrice ML (ADR-034).
ADR : ADR-001 (cible 2e classe), ADR-008 (décalage opérationnel, corrigé par ADR-062), ADR-010 (famille des 6 statistiques historiques), ADR-034 (périmètre `base_offre` diagnostique), ADR-062 (virage leakage : cutoff mensuel, tronçon dans la clé, fenêtre win7), ADR-038 (extension H25), ADR-065 (Split C, exclusion des tronçons Gilamont en H22).

---

## Fiche S02 : Réalisation de l'offre (ISTDATEN)

**Bloc A**
Fournisseur et acquisition : opentransportdata.swiss (OFT), open data, extrait corridor R35 + VMCV + nœud de Vevey.
Grain natif : arrêt × course × jour d'exploitation.
Couverture : janvier 2018 à décembre 2025 (années horaires H18 à H25 ; pas de couverture H16-H17, la source ne publie que depuis fin 2018).
Volumétrie : 6,96 Go pour l'extrait R35, mesure directe des 96 fichiers `data/external/istdaten/istdaten_2018-01.csv` à `istdaten_2025-12.csv` (6 963 072 504 octets, soit 6,96 Go décimaux ou 6,48 Gio, mesure du 2026-07-11). Table canonique `istdaten_clean` = 2 924 792 lignes (14 colonnes) ; fait de modélisation `fact_istdaten_r35` = 1 181 193 lignes (années civiles 2021-2024).
Contenu déplacé depuis le corps : description du format CSV ligne à ligne et reconstitution des courses par identifiant ; ordre de grandeur du flux national ; détail du changement de format.
Versions et format (trois faits, trois provenances) : premièrement, une version 2 du jeu de données est disponible depuis le 13 juillet 2025 (fait externe, source : documentation de la plateforme opentransportdata.swiss, référence APA à intégrer au mémoire). Deuxièmement, la mise hors service définitive des anciennes versions est annoncée pour le 30 juin 2026 (même source externe ; corrige toute mention du 30 juin 2025). Troisièmement, le seul changement de format documenté dans le dépôt est l'ajout de la colonne `SLOID` aux fichiers en octobre 2025 (schéma historique à 21 champs), absorbé par la sélection explicite des 21 colonnes historiques (sources : `scripts/sources/build_fact_istdaten_r35.py:154-156`, `scripts/sources/build_istdaten_ponctualite.py:194-195`, `scripts/sources/build_dim_correspondances_vevey.py:117`).
Limites structurelles : système conçu pour l'information voyageurs, usage statistique dérivé ; statuts REAL (heure réelle, disponible depuis le 2023-05-31) / GESCHAETZT (estimé, absent de l'extrait) / PROGNOSE (dernière prévision, souvent utilisée comme trajet réel pour les statistiques) / UNBEKANNT (aucune information transmise, horodatages toujours absents), sémantique documentée par la norme VDV 454.
Diagnostics empiriques : horodatages UNBEKANNT (UNKNOWN) massifs sur 2021 et 2022, de l'ordre de 91 % à l'échelle des années civiles pleines et de 100 % sur le périmètre R35 restreint, aucun horodatage réel, d'où une valeur manquante structurelle des features de profil de retard sur H22 ; absence complète H16-H17 (750 jours de la période calendaire APC, environ 20,5 %) ; couverture VMCV intermittente, montée en régime progressive (H21 7,7 %, H22 30,6 %, H23 60,9 %, H24 58,1 %, couverture globale des features d'attente 20,1 %) et interruption VMCV du 01-09 au 13-10-2025 (43 jours, environ 12 % du jeu de test H25) (renvoi atlas).
Disponibilité J-1 : rétrospective, latence de publication de l'ordre de la journée (d'où un usage décalé à J-2 des features dérivées).

**Bloc B**
Transformations : renvoi 4.4.x. Décalage causal J-2 à la jointure (ADR-015, ADR-022) ; métriques de ponctualité calculées sur les seuls statuts réels {REAL, GESCHAETZT} et ponctualité par valeur absolue (ADR-013) ; refonte au grain tronçon avec rolling conditionnel par type de jour et fenêtres 5 et 20 occurrences (ADR-019, révise ADR-012) ; correspondances Vevey sur fenêtre [-20, -2] minutes incluant IR90 et IR (ADR-014, ADR-023) ; intervalles `headway` calculés sur la grille horaire planifiée connue à J-1, annulés et suppléments inclus (ADR-067, révise ADR-018) ; concurrence modale VMCV recomposée en décision à l'embarquement (ADR-021, révise ADR-020) ; interruption VMCV H25 gérée en valeur manquante traçable (ADR-040).
Features produites : famille `ist_` (profil de retard départ et arrivée, part en retard, correspondances entrantes et sortantes garanties et théoriques, intervalles `headway`) et famille `vmcv_` (4 features de concurrence modale : nombre de lignes concurrentes, attente minimale, delta d'attente, delta de fréquence) [renvoi codebook].
Statut : retenue partiellement. Périmètre retenu = features `ist_` au grain tronçon et 4 features `vmcv_` à l'embarquement ; le caractère partiel tient à la couverture VMCV concentrée sur Vevey-Blonay et à la valeur manquante massive des features `ist_` en H22 (section 4.4 ; ADR-012, ADR-019, ADR-021, ADR-067).
ADR : ADR-012, ADR-013, ADR-014, ADR-015, ADR-016, ADR-018 (remplacée par ADR-067), ADR-019, ADR-020 (remplacée par ADR-021), ADR-021, ADR-022, ADR-023, ADR-040, ADR-067.

---

## Fiche S03 : Population (STATPOP)

**Bloc A**
Fournisseur et acquisition : OFS / GEOSTAT, registres administratifs harmonisés, fichiers géocodés.
Grain natif : hectare (100 m, cadre MN95 / LV95, identifiant RELI, EPSG:2056), cliché annuel au 31 décembre.
Couverture : 2015 à 2024 dans le dépôt (10 millésimes CSV). Note de vérification : le squelette indique 2010 à 2024 ; l'antériorité à 2015 n'est pas attestée par les fichiers présents. La borne 2010 relève de l'existence de la source à l'OFS, non des données mobilisées ici.
Volumétrie : brut 637 Mo (millésimes STATPOP2015 à STATPOP2024, environ 65 Mo par fichier, Suisse entière au grain hectare). Table canonique gelée `statpop_clean_causal` = 88 lignes (33 colonnes), grain millésime × gare, millésimes présents 2019 à 2023 (mapping causal Z-2), empreinte SHA256[:8] `40ae0fe0`.
Contenu déplacé depuis le corps : liste des registres sources ; géocodage RegBL et identificateur de bâtiment ; variables ménages depuis 2012 ; agrégation communale par l'angle sud-ouest ; fusions de communes et modifications de périmètre.
Limites structurelles : censure des valeurs 1 à 3 ; hectares collectifs. (Métadonnées OFS non documentées dans le projet ; à sourcer dans la documentation OFS externe.)
Diagnostics empiriques : la population totale est disponible sans interruption 2015-2024 ; en revanche les millésimes 2021 et 2023 sont structurellement incomplets, l'OFS ne publiant pas pour ces deux années les champs ménages et les indicateurs de plausibilité d'habitation (13 variables concernées). Défaut géographique corrigé sur VVVI : la gare Vevey Vignerons (VVVI) remplace Gilamont (GIL) à partir de H23, ce que le mapping initial ne reflétait pas, produisant jusqu'à 66 654 valeurs manquantes de features spatiales (100 % des features ménages et habitation de VVVI en H23), ramenées à zéro après recalcul du Voronoï sur la topologie H23 (renvoi atlas).
Disponibilité J-1 : millésime retardé (publication l'année suivant l'enquête, mobilisée avec un recul de deux ans).

**Bloc B**
Transformations : renvoi 4.4.x. Rattachement aux bassins d'arrêts par Voronoï clippé à 500 m recalculé par année horaire sur les gares actives (ADR-025) ; sélection de features avec retrait des redondances arithmétiques (densités et taille de ménage moyenne, ADR-024) ; disponibilité causale par mapping Z-2 indexé sur l'année civile et forward-fill causal des champs incomplets 2021 et 2023 (ADR-063, remplace l'interpolation linéaire d'ADR-011) ; carry-forward 2024 pour l'année civile 2025 (ADR-039) ; correction géographique VVVI (ADR-055) ; entrée figée rematérialisée (ADR-075).
Features produites : famille `spatial_` d'origine STATPOP (25 indicateurs par côté départ et arrivée, 48 conservées après ADR-024 : population et ménages dans 500 m, structure par âge, indices de stabilité et de mobilité résidentielle, part de population étrangère et née à l'étranger, classes d'habitation individuelle) [renvoi codebook].
Statut : retenue (notebook 02_data_understanding_statpop §8, quality gate « GO avec réserves » ; section 4.4). La rigueur causale Z-2 avec forward-fill améliore le segment HAUT (+0,052 R², +9 points de PR-AUC).
ADR : ADR-006, ADR-011 (remplacée par ADR-063 sur l'imputation), ADR-024, ADR-025, ADR-039, ADR-055, ADR-063, ADR-075.

---

## Fiche S04 : Emplois et entreprises (STATENT)

**Bloc A**
Fournisseur et acquisition : OFS / GEOSTAT, relevé exhaustif fondé sur les registres (essentiellement AVS).
Grain natif : hectare (100 m, cadre MN95, identifiant RELI), identique à STATPOP.
Couverture : annuelle ; 2015 à 2023 dans le dépôt (9 millésimes). Table canonique restreinte aux millésimes 2018 à 2022 (mapping causal Z-3).
Volumétrie : brut 2,6 Go (dossiers STATENT2015 à STATENT2023). Table canonique gelée `statent_clean_causal` = 91 lignes (7 colonnes), grain millésime × gare.
Contenu déplacé depuis le corps : seuil d'assujettissement AVS de 2 300 francs ; définition de l'établissement ; sources du secteur primaire ; périodes de référence différenciées par secteur ; agrégation communale par l'angle sud-ouest ; rupture des équivalents plein temps 2014-2015. (Métadonnées OFS non documentées dans le projet ; le seuil AVS, les localisations estimées et la rupture EPT 2014-2015 ne figurent pas dans le dépôt et sont hors de la fenêtre de données mobilisée. À sourcer dans la documentation OFS externe.)
Limites structurelles : censure des valeurs inférieures à 4 (protection statistique au grain hectare ; après agrégation aux buffers de 500 m, une seule ligne canonique atteint la valeur plancher 4) ; localisations estimées indistinguables des localisations précises.
Diagnostics empiriques : aucun notebook de data understanding dédié à STATENT n'existe. Diagnostics disponibles depuis ADR-064 et la table canonique : valeur manquante nulle après correction VVVI ; latence de publication de deux ans (année de publication = année d'enquête + 2) ; variance forte entre gares (coefficient de variation d'environ 1,85) et quasi nulle dans le temps pour une gare donnée, ce qui fait agir ces features comme des quasi-identifiants géographiques ; emplois dans 500 m de 4 (Bois-de-Chexbres, 2019) à 8 755 (Vevey, 2021) (renvoi atlas).
Disponibilité J-1 : délai de publication d'environ dix-huit mois (mobilisée avec un recul de trois ans, Z-3).

**Bloc B**
Transformations : renvoi 4.4.x. Rattachement aux bassins par Voronoï de 500 m (RELI réutilisé de STATPOP) ; disponibilité causale par mapping Z-3 et forward-fill causal cohérent avec ADR-063 ; correction géographique VVVI (topologie H23 appliquée rétrospectivement).
Features produites : famille `spatial_` d'origine STATENT (4 features : emplois totaux et emplois de services dans 500 m, par côté départ et arrivée) [renvoi codebook].
Statut : exclue après ablation (couche 1, ADR-064 amendement du 2026-06-18). Le résultat d'ablation sur le dataset causal montre une dégradation du segment critique HAUT (ΔR² HAUT de -0,016) pour un apport global nul, la source étant redondante avec les identifiants et la topologie de gare ; STATENT reste dans le pipeline et le `ml_dataset` mais hors de la liste de features du modèle (statut `hors_matrice_retrait_trace`). Ne pas anticiper ce statut dans le corps de 4.3.
ADR : ADR-064.

---

## Fiche S05 : Météorologie (MétéoSuisse)

**Bloc A**
Fournisseur et acquisition : MétéoSuisse, open data, réseau SwissMetNet, stations de Vevey (Corseaux) et Château-d'Oex.
Grain natif : station × heure à la source (fichiers horaires) ; le grain retenu au dataset est l'agrégat journalier par station (pas d'infra-journalier dans le modèle).
Couverture : Vevey depuis le 8 septembre 2015 ; Château-d'Oex depuis le 8 février 2012 ; jusqu'au 31 décembre 2025.
Volumétrie : brut 25 Mo. Tables canoniques horaires `meteo_vev_clean` = 90 376 lignes (20 colonnes) et `meteo_chd_clean` = 121 700 lignes (27 colonnes).
Contenu déplacé depuis le corps : énumération des paramètres mesurés (températures moyenne, minimum, maximum, précipitations, ensoleillement, rayonnement global, humidité, vent, hauteur de neige).
Limites structurelles : aucune station au terminus des Pléiades (1348 m), Château-d'Oex (1040 m) servant de proxy d'altitude, d'où une incertitude de représentativité altitudinale ; distinction structurelle entre mesures observées (historique) et produits de prévision (nécessaires en exploitation).
Diagnostics empiriques : complétude élevée hors hauteur de neige (environ 99,9 % à Vevey, 99,3 % à Château-d'Oex) ; la hauteur de neige est manquante à 77 % (Vevey) et 82 % (Château-d'Oex), le paramètre n'ayant pas été instrumenté avant 2023 ; lacune temporelle isolée à Château-d'Oex en juillet 2017 (environ 600 observations horaires), sans effet après agrégation journalière ; 6 631 valeurs de hauteur de neige négatives à Château-d'Oex (artefacts capteur clippés à zéro) ; écart médian Château-d'Oex moins Vevey de -4,74 °C, cohérent avec le gradient altitudinal (renvoi atlas).
Disponibilité J-1 : observation du jour cible indisponible par construction, prévision nécessaire en exploitation (le catalogue OGD ne conserve pas rétrospectivement les prévisions).

**Bloc B**
Transformations : renvoi 4.4.x. Combinaison des deux stations par rattachement géographique (segment haut vers Château-d'Oex, segment bas vers Vevey) et par sens de circulation pour la température de destination ; agrégats journaliers J, J-1 et J+1 (ADR-028) ; disponibilité J-1 documentée et retrait de trois features de hauteur de neige pour changement d'instrumentation (ADR-022). L'indicatrice `meteo_neige_binaire_h` n'est pas un seuil sur la seule hauteur mesurée, en grande partie manquante, mais une règle combinée dépendante de la station : à Vevey (bas), précipitations supérieures au seuil et température inférieure à 2 °C ; à Château-d'Oex (haut), hauteur de neige mesurée positive ou bien précipitations supérieures au seuil et température inférieure à 2 °C, la composante précipitations-température assurant la couverture avant l'instrumentation de la hauteur de neige en 2023 (source : `scripts/pipeline/add_meteo_to_raw_stacked.py:58-60` et `:299-308`).
Features produites : famille `meteo_` (température, précipitations, ensoleillement, vent maximal, rayonnement global, neige binaire ; variantes locale, destination, J-1 et J+1) [renvoi codebook].
Statut : retenue avec limite documentée (section 4.4 ; ADR-028 pour l'enrichissement journalier, ADR-022 pour la disponibilité J-1 et la limite prévision-observation).
ADR : ADR-022, ADR-028.

---

## Fiche S06 : Événements (manifestations régionales)

**Bloc A**
Fournisseur et acquisition : Montreux Riviera / Montreux-Vevey Tourisme, liste annuelle au format PDF transmise sur demande.
Grain natif : manifestation × date(s) × lieu (commune ou secteur).
Couverture : annuelle, 2015 à 2025 (11 fichiers PDF).
Volumétrie : brut 2,8 Mo. Dimension `dim_manifestations_riviera` = 2 337 jours de manifestation (13 colonnes) ; dimension des événements distincts `dim_manifestations_riviera_evenements` = 697 événements.
Contenu déplacé depuis le corps : détail des champs d'une entrée ; tenue manuelle, entrées irrégulières, énumérations de dates ; non-standardisation des noms de lieux.
Limites structurelles : sélection éditoriale sans critère systématique (choix de l'office du tourisme) ; présence sans ampleur ni horaires (grain journalier, aucune jauge de fréquentation) ; portée géographique dépassant le corridor, avec un jugement de proximité qui confond proximité géographique et connectivité ferroviaire.
Diagnostics empiriques : 697 événements répartis par année de 76 (2015) à 65 (2025), avec un creux marqué en 2020 (14, effet COVID) ; répartition par zone de proximité : zone directe 235, zone indirecte 289, hors zone 162, indéterminée 11 ; au sein de la zone directe, Vevey domine (194 événements, 82,6 %), devant Blonay (29, 12,3 %) et Saint-Légier (12, 5,1 %) ; événements récurrents nommés (Montreux Jazz, Marché de Noël, Montreux Noël) présents dix années sur onze (absents en 2020) ; part des événements annulés exclus non chiffrée dans le dépôt (renvoi atlas).
Disponibilité J-1 : oui, calendrier établi à l'avance.

**Bloc B**
Transformations : renvoi 4.4.x. Extraction depuis les PDF, normalisation des lieux (minuscules, diacritiques), mapping zonal par connectivité ferroviaire, jugement de proximité en trois zones, classification par localité, exclusion des annulés, indicateurs journaliers de comptage (ADR-029).
Features produites : famille `event_` liée aux manifestations (présence et nombre de manifestations Riviera, comptages par zone directe, indirecte et hors zone, comptages par localité Vevey, Saint-Légier et Blonay, indicatrices d'événements nommés Montreux Jazz, Marché de Noël et Montreux Noël, indicatrice de saison des narcisses) [renvoi codebook]. La saison des narcisses est encodée séparément par une règle calendaire (dimension `dim_narcisses`, ADR-076).
Statut : retenue comme indicateur de contexte (section 4.4 ; ADR-029).
ADR : ADR-029 ; ADR-076 pour la règle calendaire de la saison des narcisses.

---

## Fiche S07 : Réservations de groupes (ResSys)

**Bloc A**
Fournisseur et acquisition : MOB, logiciel ResSys (Infosystem), export propre à la R35 (fichiers annuels par année horaire).
Grain natif : réservation × train × date de voyage, passagers par classe.
Couverture : H16 à H25 (10 exports) ; périmètre de modélisation H22 à H25 (réservation connue à J-1).
Volumétrie : brut 1,2 Mo. Après filtrage des réservations abouties et anticipation d'au moins un jour : 9 125 réservations ; sous-ensemble du périmètre de modélisation H22-H25 : 4 113 réservations. Il n'existe pas de table gold committée : la vue réservation est reconstruite à l'exécution depuis les exports.
Contenu déplacé depuis le corps : énumération complète des champs de l'export.
Variables ou champs disponibles : champs d'analyse non nominatifs (`pax_1c`, `pax_2c`, `lead_days`, `cat_train`, `canal` de vente, `pays`, `marche`, `langue`, `reiseart` = type de voyage) et champs nominatifs non affichés (numéro de dossier, nom du groupe, partenaire commercial). Note de vérification : aucun champ « liaison CAPRE » n'existe ; CAPRE et ResSys désignent le système source, pas une colonne.
Limites structurelles : couvre les seuls groupes (environ 0,48 % du trafic voyageurs-tronçon) ; réservation comme intention distincte de l'embarquement (une composante spontanée s'y ajoute) ; absence de date d'annulation dans le fichier (surestimation légère possible des features) ; hétérogénéité de saisie (classification scolaire ou voyagiste par heuristiques sur champs libres).
Diagnostics empiriques : anticipation commande-voyage de médiane 32 jours (moyenne 40,5, 90e centile 84, maximum 525) ; à J-1, 100 % des réservations et 99,9 % des voyageurs sont connus ; voyageurs 2e classe par réservation de médiane 25 (90e centile 70, maximum 210) ; part scolaire 32,7 %, part voyagiste 2,4 %, 9 pays et 4 langues distincts ; deux statuts (aboutie et annulée), seules les abouties étant retenues (renvoi atlas).
Disponibilité J-1 : oui, date de commande antérieure au voyage, souvent de plusieurs semaines.

**Bloc B**
Transformations : renvoi 4.4.x. Filtrage par statut (seules les réservations abouties), cutoff d'anticipation d'au moins un jour, agrégation au grain course × date × tronçon (ADR-035) ; adoption comme modèle de référence de la couche 1 (ADR-036).
Features produites : famille `resa_` (8 features à J-1 : voyageurs 2e classe réservés, nombre de dossiers, maximum de groupe, part scolaire, part voyagiste, nombre de pays et de langues distincts, indicatrice de présence de réservation) [renvoi codebook].
Statut : retenue, signal anticipé de la composante groupe (gain R² du segment HAUT de +0,148 avec les réservations) ; rôle dans le plancher de demande annoncée de la Couche 2 (règle candidate de recommandation des courses dont la réservation 2e classe dépasse la capacité assise, filet complémentaire au score prédictif) (section 4.4 et section Couche 2 ; ADR-035, ADR-036, ADR-073).
ADR : ADR-035, ADR-036, ADR-073.

---

## Fiche S08 : Registre des rotations (compositions engagées)

**Bloc A**
Fournisseur et acquisition : MOB, tableau de bord ; source authoritative pour les unités multiples (UM). Export CSV des compositions engagées.
Grain natif : course (date × numéro de train × tronçon) rattachée à un tour de service, avec rang dans le tour ; l'UM se lit dans l'ordre des véhicules (deux rames SURF accouplées).
Couverture : la source existe au dépôt en deux objets de vintages différents, à ne pas confondre. La table de dimension figée `dim_rotations_r35.parquet` couvre du 2023-09-01 au 2024-12-31, soit H23 et H24 entiers plus les dix-sept premiers jours de H25 seulement (2024-12-15 au 2024-12-31) ; elle ne contient donc pas H25 complet. Le fichier brut présent `rotations_23_25.csv` couvre du 2023-05-28 au 2025-12-31, soit H23 à H25 entiers (la borne de fin H25 est le 2025-12-13 d'après `data/dimension/annees_horaires.csv`). C'est ce brut, et non la dimension figée, qui rend possible une baseline mesurée sur H25.
Volumétrie : brut présent `data/external/rotations/rotations_23_25.csv` = 82 266 lignes (5,1 Mo), 871 dates distinctes, 2023-05-28 au 2025-12-31. Table de dimension figée `dim_rotations_r35.parquet` = 44 877 lignes (11 colonnes), 1 953 tours de service, empreinte SHA256[:12] `688e943b5ea9` (calcul direct du 2026-07-11), entrée figée ; sa colonne `source_version` vaut `rotations_22_24.csv`, brut d'origine non présent au dépôt dont le nom ne reflète pas l'étendue réelle de la dimension (jusqu'à fin 2024) et qui est distinct du brut présent `rotations_23_25.csv`.
Limites structurelles : héritage du roulement, la composition matérielle (rame simple ou UM) étant décidée au niveau du tour de service et héritée le long du roulement (une rame accouplée n'est décrochée qu'à Vevey ou Blonay) ; la composition d'une course peut donc résulter du tour et non d'une décision propre à la course (courses héritées subies, non décidées). Changements en cours de service (panne, renfort) non couverts ; couverture APC réduite à l'automne 2025 (environ 75 %).
Diagnostics empiriques : source d'autorité pour les UM, distincte du proxy `base_offre` de l'APC (composition lue dans l'ordre des véhicules, deux rames rail distinctes de la série 7501 à 7508 accouplées). La baseline UM humaine H25 n'est pas calculée sur la dimension figée, qui s'arrête fin 2024, mais par le module canonique `src/couche2/blocs.py`, qui lit directement le brut `rotations_23_25.csv` (constante `ROTATIONS`, `src/couche2/blocs.py:59-60`), l'intersecte avec l'APC (`apc_stacked.parquet`) et affecte l'année horaire depuis `annees_horaires.csv` (`assign_annee`, `src/couche2/blocs.py:201-210`) ; le décompte de 418 est le budget d'unités multiples humaines déployées dans H25 au seuil des places assises (`budget_UM_H25 = h25g["UM_deployees"]`, `src/couche2/blocs.py:352`, avec le commentaire « 418 = courses-UM humaines DANS H25 »). La triangulation historique APC contre rotations (notebook `04h_triangulation_baseline_rotations.ipynb`, 99,3 % de concordance) porte sur le brut d'origine `rotations_22_24.csv` au périmètre H23-H24 (`ROTATIONS_FILE`, cellule 122 du notebook). Trois objets distincts sont donc à tenir séparés : la dimension figée `dim_rotations_r35` (analyse descriptive et triangulation H23-H24), le brut présent `rotations_23_25.csv` (source de la baseline H25), le brut d'origine `rotations_22_24.csv` (dont dérive la dimension, absent du dépôt). Longueur médiane d'un tour de 23 courses, trains à vide 0,9 %, points de changement possibles 80,2 % ; précision au grain course de 33,5 % en H25 (140 sur 418), 23,0 % sur la période totale (203 sur 881) (renvoi atlas).
Disponibilité J-1 : oui.

**Bloc B**
Transformations : renvoi 4.4.x.
Features produites : aucune (source hors matrice de features, confirmé contre le codebook).
Statut : référence d'évaluation de la Couche 2 et de la comparaison à la référence humaine (baseline de 418 UM en H25) ; n'entre pas dans le modèle prédictif, consommée en lecture seule après la prédiction (section Couche 2 ; ADR-007, ADR-073).
ADR : ADR-007, ADR-073.

---

## Fiche S09 : Vacances scolaires et jours fériés

**Bloc A**
Fournisseur et acquisition : canton de Vaud, calendrier scolaire officiel (département de la formation, transcrit depuis deux PDF officiels et complété pour le millésime 2021-2022 par le calendrier publié sur vd.ch) ; jours fériés officiels listés par l'État de Vaud (Nouvel An, 2 janvier, Vendredi Saint, Lundi de Pâques, Ascension, Lundi de Pentecôte, 1er août, Lundi du Jeûne fédéral, Noël), le congé administratif du 26 décembre n'étant pas retenu comme férié officiel. Acquisition par transcription des dates et calcul algorithmique de Pâques et du Jeûne fédéral.
Grain natif : jour × juridiction (canton de Vaud).
Couverture : du 2014-08-25 au 2031-08-24 (17 années scolaires vaudoises), dimension `dim_vacances_feries_vaud` = 6 209 lignes journalières.
Limites structurelles : juridiction vaudoise uniquement ; grain natif riche (types de congés, repères scolaires) réduit à des indicatrices binaires en features ; millésime 2021-2022 issu d'une source secondaire (vd.ch en ligne).
Disponibilité J-1 : oui, calendrier déterministe.

**Bloc B**
Transformations : renvoi 4.4.x. Jointure sur la date de circulation et calcul d'une catégorie métier de type de jour à 9 niveaux (ponts, veilles et lendemains de fériés).
Features produites : indicatrices `event_is_vacances_vaud`, `event_is_ferie_vaud`, `event_is_vacances_ou_ferie_vaud` (famille calendriers-événements) [renvoi codebook].
Statut : retenue (section 4.4). L'extension cantonale au Valais, Fribourg, Neuchâtel et Genève a été testée et écartée : elle n'améliore pas le PR-AUC du segment HAUT (delta de -0,0022 en validation H24), le seul signal réel étant les vacances valaisannes sur le segment BAS, hors cible, non généralisé en H25 (ADR-070).
ADR : ADR-070.

---

## Fiche S10 : Exploitation du ski aux Pléiades

**Bloc A**
Fournisseur et acquisition : Coopérative des Pléiades (Pistes de fond des Tenasses, Les Pléiades), PDF annuels des dates d'exploitation officielles et deux PDF historiques d'ouverture. Acquisition par transcription des dates d'ouverture et de fermeture.
Grain natif : jour d'exploitation (une ligne par jour ouvert).
Couverture : saisons H16 à H26, du 2015-12-12 au 2025-12-13. Dimension `dim_ski_pleiades` = 882 lignes ; saisons H20 à H25 renseignées par les dates officielles (531 lignes), saisons H16 à H19 reconstruites empiriquement (351 lignes), saison 2025-2026 intégrée partiellement (un seul jour tombant dans H25).
Limites structurelles : pas de prise en compte de l'enneigement réel ni des fermetures techniques ; pas de distinction des ouvertures partielles ; saisons H16 à H19 reconstruites sans archives officielles (marquées comme reconstruites pour pondération ou exclusion en analyse de sensibilité).
Disponibilité J-1 : oui, l'état d'ouverture du jour est un flag calendaire publié avant la saison (aucune donnée de fréquentation observée ingérée).

**Bloc B**
Transformations : renvoi 4.4.x. Transcription des périodes officielles et reconstruction empirique H16-H19 (règle : ouverture le premier samedi à partir du 12 décembre, fermeture le dernier dimanche au plus tard le 15 mars).
Features produites : indicatrice `event_is_ski_ouvert` et `event_ski_source` (famille calendriers-événements) [renvoi codebook].
Statut : retenue (section 4.4 ; ADR-058, régénération de la dimension et intégration partielle de la saison 2025-2026).
ADR : ADR-058.

---

## Fiche S11 : Horaires publiés

**Bloc A**
Fournisseur et acquisition : horaires officiels publiés MOB / MVR de la ligne 112 (Vevey - Les Pléiades), 10 PDF annuels. Acquisition par parsing PDF (extraction des mots et des objets graphiques, les renvois de circulation étant de petits rectangles noirs) et reconstruction d'un calendrier de circulation développé par tronçon et par jour.
Grain natif : course × arrêt × année horaire (sortie année horaire + date + numéro de train + gares de départ et d'arrivée + heures).
Couverture : H16 à H25 (2015-12-13 au 2025-12-13), table canonique `horaires_clean` = 2 962 919 lignes (55 colonnes).
Limites structurelles : changements d'horaire annuels de mi-décembre, avec réutilisation des numéros de train d'une année sur l'autre pouvant désigner des services différents. La transition H23 vers H24 est stable (108 trains sur 108) ; la refonte de décembre 2024 (H24 vers H25) renumérote 52 trains sur 103 (environ 50 %), cause structurelle des valeurs manquantes SIMBA sur H25.
Disponibilité J-1 : oui, horaire publié à l'avance.

**Bloc B**
Transformations : renvoi 4.4.x. Reconstruction depuis les PDF ; les intervalles `headway` sont calculés sur la grille horaire planifiée connue à J-1, annulés et suppléments inclus (ADR-067). Groupement par numéro de train conservé, avec un encodage composite (numéro et heure d'origine) valide sur la transition stable H23-H24 (ADR-016).
Features produites : famille `horaire_` (année horaire, numéro de train, identifiant de service complet ; statut de traçabilité, non features prédictives directes) et features `ist_headway_` d'intervalle amont et aval (features de modèle) [renvoi codebook].
Statut : retenue (section 4.4 ; ADR-067 pour le headway sur grille planifiée, ADR-016 pour la stabilité des numéros de train).
ADR : ADR-016, ADR-067.

---

## Fiche S12 : Origine-destination (SIMBA)

**Bloc A**
Fournisseur et acquisition : SIMBA FQkal (modèle de demande origine-destination de l'unité SBB Angebotsplanung), enquêtes de fréquentation calibrées via les comptages automatiques (chaîne AFZ vers HOP vers calibration). Mise à disposition par les CFF aux entreprises de transport concessionnaires (dont MOB / MVR) au format CSV annuel (`zuginout_MOB_YYYY.csv`).
Grain natif : OD × millésime (granularité annuelle pure, aucune dimension infra-annuelle ; moyennes journalières annuelles par relation).
Couverture : millésimes 2022 à 2025. Brut 42 Mo ; table canonique `dim_simba_r35` = 4 239 lignes (grain train × tronçon × millésime, 17 colonnes).
Limites structurelles : instabilité temporelle (profil structurel constant sur l'année, sans distinction de type de jour) ; indisponibilité opérationnelle (latence de publication de quatre à cinq mois, le millésime Y paraissant en avril-mai Y+1) ; maille inadaptée (46,6 % des observations H25 sans valeur, les 52 trains renumérotés après la refonte de décembre 2024 étant absents du millésime disponible).
Diagnostics empiriques, propriétés de la source (compréhension des données, mobilisables en 4.3) : instabilité inter-annuelle quasi nulle (corrélation 2023 contre 2024 de 0,056 sur la part GA, feature dominante) ; latence de publication de quatre à cinq mois entraînant un leakage de disponibilité sur 21,6 % de H25 ; valeurs manquantes structurelles sur H25 de 46,6 % (52 trains renumérotés après la refonte de décembre 2024, valeur manquante confirmée après investigation de cinq voies de jointure ; valeur manquante globale au codebook de 29,6 %) ; leakage circulaire mesuré, corrélation de 0,97 entre l'occupation reconstruite depuis SIMBA et la charge APC 2e classe H24, d'où le lag N-1 impératif (renvoi atlas).
Diagnostics empiriques, résultats de modélisation (renvoi couche 1, à ne pas mobiliser dans le corps de 4.3.10) : bas du classement SHAP (environ 5 % de l'importance) ; le retrait des 12 features laisse le R² global stable à marginalement meilleur (0,5884, delta de +0,007) avec un gain du segment HAUT (delta de +0,0415).
Disponibilité J-1 : non adaptée.

**Bloc B**
Transformations : aucune feature retenue au modèle final (source écartée) ; lors de son intégration exploratoire, lag N-1 systématique (ADR-026) et gestion de la refonte d'horaire H25 (ADR-041).
Features produites : aucune au modèle final. Les 12 features `simba_part_*` (plus deux colonnes de source) sont tracées hors matrice (statut `hors_matrice_retrait_trace`).
Statut : écartée au titre des propriétés de la source (renvoi 4.3.10 et ADR-061). L'écartement est légitime en 4.3 car il découle de la compréhension de la source, non d'un résultat de modélisation. Usage exploratoire conservé dans la synthèse (caractérisation des titres de transport bas et haut) avec la prudence correspondante. Note de vérification : dans le rapport de synthèse, cette caractérisation exploratoire figure aux sections 1.5 et 2.5 (la numérotation 4.3.10 renvoie à la section correspondante du corps du mémoire).
ADR : ADR-026 (intégration initiale, lag N-1), ADR-041 (refonte d'horaire H25), ADR-056 (valeur manquante de jointure confirmée), ADR-061 (retrait définitif).

---

## Corrections à reporter dans le corps du mémoire (docx, hors périmètre de ce prompt)

Cette section liste les corrections identifiées lors de la relecture du catalogue, à appliquer au docx du mémoire. Aucune de ces modifications n'est effectuée ici.

Retrait de l'ancienne version ISTDATEN : la mise hors service définitive est annoncée pour le 30 juin 2026, et non le 30 juin 2025 ; corriger la mention correspondante en section 4.3.2 (source externe : documentation opentransportdata.swiss, référence APA à intégrer).

Couverture STATPOP mobilisée : la fenêtre effectivement mobilisée est 2015 à 2024, et non 2010 à 2024 ; corriger la section 4.3.3 et le tableau 4.2 (les fichiers présents au dépôt sont les millésimes 2015 à 2024).

Rupture des équivalents plein temps STATENT 2014-2015 : supprimer la mention du corps de la section 4.3.4 (verdict CC-1) ; aucune feature d'équivalent plein temps ne figure au modèle et la rupture est hors de la fenêtre des millésimes mobilisés (canonique 2018 à 2022).

Robustesse aux fusions de communes : l'ajout de la demi-phrase de robustesse en section 4.3.3 est justifié (verdict CC-2 confirmé par V4). La préparation STATPOP et STATENT n'agrège par aucun identifiant ni périmètre communal : le rattachement est hectométrique (préfiltre rectangulaire sur les coordonnées E et N puis Voronoï clippé à 500 m) ; `GMDE` et `HIST_GMDE` sont classés colonnes techniques et exclus des mesures sommées (`scripts/sources/build_fact_statpop_gare.py:623-637`), `gare_commune` n'est qu'un libellé descriptif de la gare, et `build_fact_statent_gare.py` ne référence aucune commune.

Volumétrie ISTDATEN (tableau 4.2) : le chiffre 6,96 Go est confirmé par mesure directe (96 fichiers `data/external/istdaten/istdaten_2018-01.csv` à `istdaten_2025-12.csv`, 6 963 072 504 octets, mesure du 2026-07-11) ; le consigner avec sa provenance plutôt que le supprimer.
