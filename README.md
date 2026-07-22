# Splitdex

Application locale de scan et listing de cartes Pokémon pour Vinted.
Tourne entièrement sur ta machine (aucun cloud, aucune exposition Internet),
mais accessible depuis les autres appareils de ton réseau local (LAN) — par
exemple un Mac qui se connecte via le navigateur.

## État actuel : Phase 5

- Backend FastAPI qui écoute sur `0.0.0.0:8000` (accessible en LAN).
- Endpoint `POST /api/upload` : upload d'une photo (JPEG/PNG/WEBP, 25 Mo max).
- Endpoint `GET /api/uploads` : liste des photos déjà envoyées.
- Endpoint `POST /api/photos/{id}/crops` : détecte et découpe automatiquement
  les cartes sur une photo (OpenCV), redresse la perspective, enregistre un
  crop par carte détectée.
- Endpoint `GET /api/photos/{id}/crops` : relit les crops déjà générés pour
  une photo, sans relancer la détection.
- **Nouveau** — Cache local de cartes de référence (SQLite) synchronisé
  depuis l'API pokemontcg.io : `backend/app/scripts/sync_cards.py`.
- **Nouveau** — Endpoint `POST /api/photos/{id}/identify` : identifie chaque
  carte découpée par comparaison d'image contre le cache local (nom, set,
  numéro, rareté). `GET /api/photos/{id}/identify` relit les résultats déjà
  calculés.
- **Nouveau** — Endpoint `GET /api/reference/status` : nombre de cartes
  actuellement en cache local.
- Endpoint `POST /api/photos/{id}/listings/generate` : génère un titre + une
  description Vinted prêts à copier-coller pour chaque carte identifiée, à
  partir d'un gabarit Jinja2 éditable. `GET /api/photos/{id}/listings` relit
  les fiches déjà générées.
- **Nouveau** — Endpoint `PATCH /api/photos/{id}/listings/{crop_filename}` :
  corrige la carte retenue, l'état, le prix, ou modifie le titre/la
  description à la main.
- **Nouveau** — Endpoint `POST /api/photos/{id}/listings/{crop_filename}/regenerate` :
  regénère le titre/description à partir de la carte/état/prix actuels
  (utile après une correction, sans perdre un texte déjà édité à la main tant
  qu'on ne clique pas dessus explicitement).
- **Nouveau** — Endpoint `GET /api/reference/search?q=...` : recherche par nom
  dans le cache local, pour corriger une identification quand aucune des
  alternatives proposées n'est la bonne carte.
- **Nouveau** — Endpoint `GET /api/photos/{id}/export` : télécharge un ZIP
  contenant, pour chaque carte, l'image du crop + un fichier texte
  (titre + description prêts à coller sur Vinted).
- Frontend : formulaire d'upload, galerie, boutons "Découper les cartes",
  "Identifier les cartes", "Générer les descriptions" puis "Exporter (ZIP)"
  par photo. Chaque carte affiche : la carte de référence (badge
  "Fiable"/"Incertain" + alternatives cliquables "Choisir"), un sélecteur
  d'état, un champ prix, un titre et une description **éditables** avec
  bouton "Copier", un bouton "Régénérer le texte", et une recherche manuelle
  de correction si aucune alternative ne convient.
- **Nouveau** — Détection de la langue d'impression (français, anglais,
  japonais, allemand, espagnol, italien) par OCR (Tesseract), affichée dans
  le panneau d'identification et corrigible via un sélecteur dans la fiche.
  Nécessite Tesseract installé (voir plus bas) — sans lui, la langue reste
  simplement indéterminée, rien ne casse.
- Pas encore d'OCR du numéro de carte (pour lever certaines ambiguïtés entre
  variantes très proches, ex: deux impressions différentes du même Pokémon).

### Upload multiple + détection automatique

Le formulaire d'upload accepte **plusieurs photos en un envoi** (cas
d'usage : une rafale de photos de cartes unitaires), plafonné à
`MAX_PHOTOS_PER_BATCH` (20, dans `config.py`) — le serveur fait autorité sur
la limite, le frontend en garde une copie pour un message d'erreur immédiat.
Les types de fichiers sont validés pour tout le lot avant d'écrire quoi que
ce soit (pas d'état à moitié réussi). Après l'envoi, la **détection des
cartes se lance automatiquement** photo par photo, avec progression affichée
— plus besoin de cliquer "Découper les cartes" pour chaque photo.

### Comment fonctionne la revue/correction (Phase 5)

- **Corriger l'identification** : cliquer "Choisir" sur une des 2
  alternatives proposées (panneau d'identification), ou utiliser la
  recherche par nom si aucune ne convient — remplace la carte retenue et
  regénère automatiquement le texte. La recherche accepte le **français
  comme l'anglais** ("Carapuce" trouve les cartes Squirtle, via la table
  `pokemon_names_fr.py`), et tous les noms affichés dans l'interface sont
  traduits en français.
- **État et prix** : sélecteur + champ numérique, sauvegardés dès qu'on quitte
  le champ (`PATCH`). Ne régénèrent **pas** automatiquement le titre/la
  description (pour ne pas écraser un texte déjà modifié à la main) — pense à
  cliquer "Régénérer le texte" après avoir changé l'état ou le prix si tu
  veux que le texte les reflète.
- **Titre/description** : zones de texte éditables directement, sauvegardées
  dès qu'on quitte le champ. Bouton "Copier" à côté de chacun pour coller
  dans les deux champs séparés du formulaire Vinted.
- **Export** : le bouton "Exporter (ZIP)" télécharge, pour chaque carte de la
  photo, l'image du crop (`01_NomDeLaCarte.jpg`) et un fichier texte
  (`01_NomDeLaCarte.txt`) avec le titre et la description — prêt à réutiliser
  pour créer l'annonce sur Vinted.

### Remplissage du formulaire Vinted (`backend/app/api/vinted.py`)

**Pas un bot** — Vinted interdit l'automatisation de la publication, et rien
ici ne publie ni ne soumet quoi que ce soit : c'est l'équivalent d'un
copier-coller multi-champs, déclenché manuellement, avec relecture et clic
final ("Ajouter") toujours faits à la main.

Installation (une fois) :
1. Installer l'extension **Tampermonkey** dans le navigateur (Chrome/Firefox ;
   sur Safari, l'app "Userscripts" fait le même travail).
2. Ouvrir `http://<IP-du-serveur>:8000/vinted-autofill.user.js` —
   Tampermonkey propose l'installation. L'adresse du serveur Splitdex est
   injectée automatiquement dans le script au moment où il est servi (IP LAN
   sur la VM, localhost plus tard sur le Mac : rien à éditer).

Usage :
1. Dans Splitdex, sur la fiche d'une carte : bouton **"Envoyer vers Vinted"**
   (mémorise titre/description/prix/état tels qu'affichés, y compris les
   éditions en cours — en mémoire serveur uniquement, une fiche à la fois).
2. Sur `vinted.fr` → "Vendre" (page ouverte normalement, en étant connecté) :
   bouton flottant **"📋 Remplir depuis Splitdex"** en bas à droite → remplit
   titre, description, prix, et sélectionne la **catégorie** ("Cartes à
   collectionner", en naviguant dans l'arborescence par simulation de clics),
   la **marque** ("Pokémon", via son champ de recherche) et l'**état** (celui
   de la fiche — "Très bon état" par défaut, cf. `DEFAULT_LISTING_CONDITION` ;
   "Neuf" est traduit en "Neuf sans étiquette", vocabulaire Vinted). Un toast
   récapitule ce qui a été rempli et ce qui reste : **photos** (dans l'export
   ZIP) puis relecture.

Vinted étant une application React, le script passe par les setters natifs +
événements `input` (une simple assignation de `.value` serait ignorée par
React). Les sélecteurs de champs sont volontairement multiples (name,
data-testid...) car le markup de Vinted évolue : si un champ n'est plus
trouvé, le toast le signale explicitement — les sélecteurs sont regroupés en
tête de `USERSCRIPT_TEMPLATE` dans `vinted.py`, faciles à compléter.

### Détection de la langue d'impression (`backend/app/core/language_detector.py`)

Le public visé est francophone : une carte **française n'est jamais
mentionnée** dans le titre/la description (langue par défaut implicite,
inutile de l'affirmer) — mais une carte anglaise, japonaise, allemande,
espagnole ou italienne est signalée explicitement dans les deux, pour que
l'acheteur ne soit pas surpris.

Fonctionnement : OCR sur la **région native de la photo originale** (re-warpée
à la volée depuis les corners de `meta.json` — le crop sauvegardé subit un
rééchantillonnage à 480px + une recompression JPEG qui détruisent le petit
texte quand la carte ne fait que ~300px dans la photo), puis **score de
vocabulaire pondéré sur le texte des attaques** — les formules du TCG sont
ultra-caractéristiques par langue ("Lancez une pièce... dégâts" / "Flip a
coin... damage" / "Wirf eine Münze... Schaden") et bien plus nombreuses que
les seuls mots-clés de mise en page (PV/Faiblesse/Retraite) essayés
initialement, que l'OCR écorchait trop souvent (2 cartes détectées sur 52
françaises réelles). Les tokens sont normalisés (accents retirés, majuscules)
pour résister aux accents perdus par l'OCR, et une décision exige un score
minimum, une avance nette sur la 2e langue ET au moins un mot "substantiel"
(long et distinctif type ATTAQUE ou DAMAGE — les jetons courts type PS/PV
sortent par hasard du bruit OCR).

Le japonais n'est **pas** décidé par les statistiques CJK de l'OCR : mesuré
sur de vraies cartes, la passe `jpn` hallucine sur les reflets holographiques
des cartes latines des proportions de kana/kanji indiscernables d'une vraie
carte japonaise (13 fausses "Japonaise" sur 52 françaises avec l'ancienne
approche). Il est établi par la correspondance exacte du nom d'espèce en
katakana (`name_detector.py`, ex: "ガメール") — quasi impossible à halluciner.

Dernier filet : le **vote majoritaire par photo** (`api/identify.py`). Les
cartes d'un même envoi sont presque toujours imprimées dans la même langue,
donc les cartes déterminées (vocabulaire ou nom d'espèce) votent pour celles
restées indéterminées (texte illisible en basse résolution, full-arts au
texte minuscule) — sans jamais écraser une détermination individuelle. Le
remplissage exige une majorité **écrasante** (≥80% des déterminées) : une
photo homogène ou un classeur presque homogène (8 FR + 1 JP = 89%) remplit
tout, mais une photo franchement mixte (10 FR + 5 EN mesurée = 67%) ne
remplit rien — une carte anglaise illisible y serait étiquetée "Français", et
une langue fausse est pire qu'une absente (le prix serait cherché dans le
mauvais catalogue sans que rien ne le signale) ; ces cartes restent à choisir
via le sélecteur de la fiche.

Réglages Tesseract déterminants, mesurés sur crops réels (`ocr_text()`,
utilisé par `detect_language`, `number_detector.py` et `name_detector.py`) :
- **`--psm 11`** (texte épars) au lieu du mode par défaut (page structurée,
  mal adapté à la mise en page d'une carte) ;
- **passes séparées par famille de script** (langues latines combinées d'un
  côté, japonais seul de l'autre) — mélangées, elles se diluent mutuellement
  ("カメール" illisible en `eng+...+jpn` combinés, lu correctement en `jpn`
  seul) ;
- **seconde passe latine `--psm 6` sur image renforcée** (gris + unsharp
  mask) : sur les cartes à faible résolution optique, `--psm 11` ne rend
  quasi rien alors que cette passe récupère les gros caractères (nom, noms
  d'attaque, STAGE/NIVEAU) — suffisants pour le vocabulaire et les indices
  d'identification (2 cartes anglaises passées de score 2 à 8-12) ;
- **passe de sauvetage conditionnelle par binarisation adaptative** : sur les
  cartes dont le texte est imprimé sur une bande COLORÉE (rose/rouge des
  types Fée, lavande des Psy...), le passage en niveaux de gris écrase le
  contraste et les deux passes précédentes rendent 0 — le seuil local
  gaussien le restaure (3 cartes lisibles à l'œil mais muettes à l'OCR :
  scores 5-12 après binarisation, toutes décidées). Déclenchée uniquement si
  le score de vocabulaire reste < 8 après les passes standard : les cartes
  bien lues ne paient pas cette passe supplémentaire.

Un score ambigu (trop faible, avance insuffisante, ou aucun mot substantiel)
renvoie `None` plutôt que de trancher au hasard — c'est le vote par photo ou
la correction manuelle qui prend le relais.

**Nécessite le binaire système Tesseract**, à installer toi-même :
```bash
sudo apt install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-jpn tesseract-ocr-deu tesseract-ocr-spa tesseract-ocr-ita
```
Sans lui, la langue reste simplement indéterminée (`None`) partout — rien ne
plante, la détection se contente de ne rien trouver. La langue détectée est
affichée dans le panneau d'identification et corrigible via un sélecteur
dans la fiche (utile si l'OCR se trompe, ou pour une langue non gérée).

Compte à rebours ~2s/carte pour l'OCR (s'ajoute au temps de l'étape
"Identifier les cartes" sur une planche de plusieurs dizaines de cartes).

### Style des descriptions (`templates/` + `backend/app/core/card_translations.py`)

Les gabarits sont des fichiers texte Jinja2 à la racine du projet, reconstruits
à partir de vraies annonces Vinted fournies par l'utilisateur :
- `templates/vinted_title.txt.j2` — titre de l'annonce
- `templates/vinted_description.txt.j2` — corps de la description

Structure observée et reproduite : `{nom} {variante} {tag langue} {numéro}/{total}
{extension}` en titre ; en description, `Carte Pokémon {adjectif langue} {nom}
{variante} {numéro}/{total}, provenant du bloc {série}, extension {extension},
carte en {état}.` suivi d'un appel aux lots ("N'hésitez pas à faire des lots
avec d'autres produits de ma boutique !") et d'une ligne de hashtags
(`#pokemon #pokemoncards #{nom} #{variante...} #{TAG_LANGUE} #{série}
#{extension} #collection #tonio28`). **Le prix n'apparaît jamais dans le
texte** — sur Vinted c'est un champ structuré séparé, pas du texte libre.

Le **nom de l'espèce** est traduit vers le français dans le titre, la
description et les hashtags (via `translate_card_name_to_fr` dans
`pokemon_names_fr.py`, qui gère les variantes suffixées : "Venusaur-EX" →
"Florizarre-EX", "Mega Charizard X ex" → "Méga-Dracaufeu X ex"). Ce qui n'est
pas couvert par la table (cartes Dresseur, espèces manquantes) reste en
anglais.

`backend/app/core/card_translations.py` traduit vers le français ce que
pokemontcg.io ne fournit qu'en anglais :
- `SERIES_NAME_FR` : le bloc/l'ère (ex: "Sword & Shield" → "Épée et Bouclier").
  L'ère Wizards (avant que Nintendo ne reprenne l'édition) est regroupée sous
  "Wizards" plutôt que le découpage plus fin de pokemontcg.io (Base/Gym/Neo/
  E-Card), comme le font les collectionneurs francophones.
- `SET_NAME_FR` : le nom de l'extension (ex: "Flashfire" → "Offensive Vapeur").
  Couverture volontairement partielle (sets les plus courants, surtout
  récents) — ce qui n'est pas dans la table s'affiche en anglais plutôt que
  de deviner une traduction fausse. Facile à compléter (dict Python).
- `RARITY_DISPLAY_FR` : dérive un mot de variante ("holo", "AR", "ultra
  rare"...) depuis la rareté pokemontcg.io. Approximatif par nature : le
  "reverse", le "full art" ou la "1ère édition" sont des variantes visuelles
  que pokemontcg.io ne décrit pas assez finement pour être fiables
  automatiquement — à ajuster à la main si besoin (titre/description
  éditables, Phase 5).
- `LANGUAGE_TAGS` : tag court pour le titre/hashtags ("ITA", "JAP"...) et
  adjectif féminin pour la description ("italienne", "japonaise"...).

`SHOP_HASHTAG` (dans `config.py`, "tonio28" par défaut) et `LISTING_CONDITIONS`
/ `CONDITION_PHRASES` (les 4 états réels de Vinted : Neuf, Très bon état, Bon
état, Satisfaisant) sont aussi dans `config.py`, à ajuster si besoin.

### Comment fonctionne l'identification (`backend/app/core/card_identifier.py`)

pokemontcg.io ne fournit que des cartes en **anglais** (pas de variantes
FR/JP/DE avec noms/images traduits). L'identification par image te dit donc
"à quelle carte anglaise ça correspond" (nom, set, numéro, rareté) — la
langue d'impression réelle de ta carte physique est déterminée séparément,
par OCR (voir la section dédiée ci-dessus).

Plusieurs stratégies de présélection, essayées dans l'ordre :
1. **Indices numéro + nom (OCR)** — `number_detector.py` + `name_detector.py` :
   - Le **numéro** imprimé ("170/165") est indépendant de la langue
     d'impression (chiffres identiques en français/anglais/japonais/etc.,
     contrairement au texte des attaques) — s'il est lu avec confiance, on ne
     compare qu'aux cartes qui portent ce même numéro (une poignée, un
     numéro n'existe qu'une fois par set). Validé : ~450 correspondances ORB
     sur une poignée de candidats au lieu de ~30-60 sur 25 via pHash.
   - Le **nom de l'espèce** (gros caractères en haut, bien plus facile à
     OCRiser que le petit numéro) est cherché dans trois tables : français
     et japonais (traduits vers l'anglais via `pokemon_names_fr.py` /
     `pokemon_names_jp.py`) et **anglais directement** (les cartes anglaises
     — mais aussi espagnoles/italiennes — impriment le nom d'espèce anglais,
     celui du cache de référence ; c'est souvent le seul texte lisible d'un
     crop à basse résolution optique). Les tables couvrent les **1025
     espèces** (base générée depuis le CSV statique de PokeAPI,
     `pokemon_species_names.py`, les tables manuelles vérifiées prévalant en
     cas de doublon). Un nom identique en français et en anglais
     ("Granbull", "Anorith") est un indice d'IDENTITÉ mais ne porte AUCUNE
     information de LANGUE — sans ce garde-fou, chaque carte anglaise dont
     l'espèce garde son nom en français serait étiquetée "Français". Le nom
     lu est comparé par **préfixe** (pas égalité stricte) pour couvrir les
     variantes suffixées ("Celebi" matche aussi "Celebi-EX") — laisser un
     préfixe trop court créerait des faux positifs, mais un nom d'espèce
     complet ne pose pas ce risque (minimum 4 caractères pour la table
     anglaise). Trois règles durcies sur cas réels (`name_detector.py`) :
     recherche en **bornes de mots** ("MAGNETI" matchait dans
     "...attraction MAGNETIQUE" du texte de saveur d'un Métang → identifié
     Magnéti) ; un nom précédé d'un marqueur de **ligne d'évolution**
     ("Évolution de : X", "Evolves from X"...) est ignoré (c'est la
     pré-évolution — une carte Blancoton était identifiée "Tournicoton") ;
     et si AUCUN nom ne matche en bornes strictes, seconde passe tolérante
     sur la fin du mot (l'OCR colle parfois du bruit : "ELECTRODEWSS" lu sur
     une vraie carte Electrode).
     Pour le japonais, une passe exacte est tentée en premier, puis en repli
     une passe tolérante à une erreur d'OCR sur le dakuten/handakuten
     ("ガメール" lu à la place de "カメール"/Wartortle, observé en pratique) —
     ce repli exclut les clés rendues ambiguës par ce nivellement (ex:
     "カラカラ"/Cubone et "ガラガラ"/Marowak ne différent que par ce trait).
   - Ces deux indices sont indépendants de la classification de langue
     globale (`detect_language`, plus haut) : celle-ci peut renvoyer
     "indéterminée" sur une vraie carte française si l'OCR écorche
     légèrement ses mots-clés stricts, alors que le nom de l'espèce reste
     lisible — on tente donc l'indice nom dès que la langue n'est pas
     *confirmée* être une autre langue précise.
2. **pHash sur tout le cache** (présélection élargie à 400 candidats), si aucun
   indice n'est trouvé ou n'est assez confiant (calcul vectorisé avec numpy,
   reste rapide même à plusieurs dizaines de milliers de cartes) — moins fin à
   lui seul : c'est un hash GLOBAL, à mauvais rappel sur les full-arts /
   illustration-rares où l'illustration plein cadre + le texte d'une autre
   langue décalent le hash (mesuré : Plusle AR japonaise → la bonne carte
   anglaise en rang **287**e par pHash, alors que l'ORB donne 54 contre elle).
   D'où la présélection large, laissée trancher par l'ORB.
3. **Embeddings DINOv2** (`card_embedder.py`), en dernier repli si l'ORB reste
   faible (< 20) : voir la section dédiée plus bas — c'est ce qui rattrape les
   cartes holographiques/reverse-holo que le pHash ne présélectionne pas.

Dans tous les cas, la présélection est reclassée par **feature matching
ORB** — beaucoup plus discriminant qu'un hash global car il compare des
points d'intérêt locaux. Validé en pratique : ~130-450 correspondances ORB
pour la bonne carte contre ~5-20 pour une carte proche mais différente.
Chaque résultat indique `matched_by` ("number", "name", "number+name",
"image", "embedding+image") pour savoir quelle stratégie a tranché.

**Cartes pivotées** (BREAK/TURBO à l'illustration paysage, souvent
photographiées à l'horizontale, ou photo tête-bêche) : quand le meilleur ORB à
0° est faible, la voie image retente les orientations 90/180/270° et ne bascule
que si une orientation est *nettement* meilleure (un vrai pivot fait bondir
l'ORB, un écart d'un point n'est que du bruit).

Confiance dans les indices : un **nom d'espèce** lu en entier (sous-chaîne
exacte de 4+ caractères) est quasi certain — on reste dans sa shortlist même
si le score ORB est faible, car le repli pHash sur les 20 000 cartes se
trompe presque toujours davantage qu'un mauvais choix PARMI les variantes de
la bonne espèce (mesuré : "Froslass" lisible ignoré → le pHash répondait
"Tympole"). Un indice **numéro seul** reste soumis au seuil de confiance
ORB (`NUMBER_HINT_MIN_ORB_SCORE` = 15, ou 10 avec une avance ≥2x sur le
suivant) : un chiffre mal lu est fréquent et la shortlist serait alors hors
sujet — en dessous du seuil on retombe sur le pHash complet. Si numéro et
nom sont incompatibles (shortlist vide), le numéro est présumé fautif et on
retente sur le nom seul.

### Repli embeddings DINOv2 (`backend/app/core/card_embedder.py`)

pHash et ORB s'effondrent tous deux sur les cartes à **foil holographique
lourd** : le pHash global est décalé par le reflet, et l'ORB ne trouve plus de
points d'intérêt stables sur une surface irisée (mesuré : score ORB ~8-12 même
contre la bonne référence). Un réseau **auto-supervisé DINOv2** (ViT-S, modèle
LOCAL — comme YOLO, seuls les poids sont téléchargés une fois, aucun appel
réseau à l'inférence) produit un vecteur dense qui capte le CONTENU de
l'illustration, robuste au foil, à l'éclairage et à l'écart photo↔scan.

Fonctionnement : un index des embeddings des 20 000+ cartes est précalculé
(`python -m app.scripts.build_card_embeddings`, ~45 min sur la VM, quelques
minutes sur un M1, reprend sur interruption ; fichiers `data/db/card_embeddings.npy`
+ `_ids.json`). À l'identification, **uniquement si le meilleur ORB reste
faible** (< 20 — donc jamais sur les cartes classiques déjà bien reconnues,
qui n'en paient pas le coût), on calcule l'embedding du crop (aux 4
orientations, l'embedding n'étant pas invariant à la rotation), on
présélectionne les 10 plus proches par similarité cosinus, **puis l'ORB
confirme** : on n'adopte ce résultat que si son score ORB dépasse l'existant
et atteint un vrai seuil de confiance. L'embedding sert de **rappel** (il
propose la bonne carte que le pHash manque), l'ORB de **précision**.

On ne se fie **jamais à la seule similarité cosinus** : sur le gold *pur*
(illustration entièrement dorée, ORB inexploitable), l'espace d'embedding
confond les cartes dorées entre elles (mesuré : un Zoroark BREAK gold matché
sur un Sharpedo gold à 0.64) — s'y fier dégradait des cartes déjà correctes.
Le modèle est préchauffé au démarrage du serveur si l'index existe.

Résultat mesuré sur des cartes réelles difficiles (reverse-holo, full-arts,
BREAK, gold) : de 3/8 à 6/8, notamment un Ténéfix reverse-holo + watermark
Team Plasma passé d'un faux positif (ORB 12) à la bonne carte (ORB 48 après
que l'embedding la lui a proposée), sans aucune régression sur les planches de
cartes classiques (mixte 15/15, Zénith 25/25).

**Limites restantes** :
- Couverture des tables de traduction nom → anglais volontairement partielle
  (voir `pokemon_names_fr.py` et `pokemon_names_jp.py`) : ce qui manque
  retombe simplement sur le pHash.
- **Gold pur** (BREAK/TURBO et UR entièrement dorées) : ni ORB ni pHash ni la
  discrimination par embedding ne les séparent de façon fiable (toutes les
  cartes gold se ressemblent trop). Une photo nette, sans reflet direct et un
  peu zoomée aide ; une discrimination spécifique au gold reste un chantier
  ouvert.

Le résultat est marqué "Fiable" si le score ORB du meilleur candidat dépasse
un seuil (15), "Incertain" sinon — dans les deux cas, les 2 alternatives
suivantes sont affichées pour permettre une correction manuelle (Phase 5).

**Performance** : l'OCR (Tesseract) est de très loin l'étape la plus lente
(~3s par crop). Trois optimisations, sans aucun changement de résultat
(vérifié sur les 25 cartes des photos de test, résultats identiques) :
- **une seule passe OCR par crop**, partagée entre la détection de langue et
  les indices numéro/nom (avant : 3 passes identiques par crop) ;
- **crops traités en parallèle** (3 workers, `api/identify.py`) — nécessite
  `OMP_THREAD_LIMIT=1` (posé dans `language_detector.py`) : sans ça, chaque
  Tesseract lance ses propres threads OpenMP et plusieurs instances
  simultanées s'effondrent en se disputant les cœurs (constaté : passes de
  1,5s devenues des minutes) ;
- **cache des descripteurs ORB** des vignettes de référence (recalculés à
  chaque reclassement auparavant).

Mesuré sur la VM (4 cœurs) : 9 cartes identifiées en ~11s et 16 cartes en
~18s, contre plusieurs minutes avant. Autres optimisations issues de la revue
du système :
- **endpoints lourds en `def` synchrone** (et non `async def`) : FastAPI les
  exécute dans son pool de threads, le serveur reste réactif (~1 ms sur
  `/api/health`) pendant une identification — avant, tout le serveur était
  gelé pendant toute la durée du traitement ;
- **index de référence en cache** entre les requêtes (20 000+ lignes + matrice
  numpy reconstruites à chaque identification auparavant), invalidé par la
  date de modification du fichier SQLite ;
- **estimations de prix en cache** (15 min) + client HTTP TCGdex partagé :
  re-cliquer sur "Estimer le prix" répond en ~15 ms au lieu de refaire
  jusqu'à 4 requêtes réseau ;
- **cache ORB borné** (4096 entrées, ~65 Mo max) pour ne pas gonfler la
  mémoire de la VM sur de longues sessions ;
- **validation des identifiants d'URL** (`photo_id`, `crop_filename`) avant
  toute construction de chemin disque (anti-traversée de chemin —
  `app/core/validation.py`).

**Portabilité (cible finale : MacBook Pro M1)** — le matériel est détecté à
l'exécution, aucun réglage à changer en migrant :
- le nombre de workers d'identification s'adapte aux cœurs disponibles
  (cœurs − 1, borné à [2, 6] : 3 sur la VM, 6 sur un M1) ;
- YOLO utilise le GPU intégré Apple Silicon (`mps`) quand PyTorch le
  propose, sinon le CPU (cas de la VM Linux). Les résultats (précision) sont
  identiques quel que soit le matériel — seule la vitesse change.

### Estimation de prix (`backend/app/core/price_estimator.py` + `tcgdex_client.py`)

La cote (Cardmarket, EUR) vient de l'API ouverte TCGdex (https://tcgdex.dev,
sans clé) — pokemontcg.io n'a aucune donnée de prix. Points clés :
- **Le prix est demandé dans le catalogue de la langue détectée** : la cote
  varie énormément selon la langue d'impression (constaté : une Illustration
  Rare à ~65-70€ en français/international, une poignée d'euros en japonais).
  Chaque locale TCGdex exige le nom dans sa langue (les tables
  `pokemon_names_fr.py`/`pokemon_names_jp.py` servent aussi à ça). Le
  japonais est un catalogue TCGdex entièrement séparé ; l'allemand/espagnol/
  italien partagent le produit Cardmarket de l'anglais (vérifié : même
  `idProduct`), le prix `en` est donc correct pour eux.
- **Préférence aux champs de prix "holo"** (`avg-holo`...) pour les raretés
  spéciales : TCGdex rattache parfois une carte rare japonaise au produit
  Cardmarket de sa version commune (constaté : 0,21€ affiché pour une
  Illustration Rare) — le prix holo du même produit est alors le bon signal.
- Si le catalogue de la langue n'a pas la carte, repli sur le prix anglais
  **avec un avertissement explicite** dans la réponse, jamais silencieusement.

Endpoint `GET /api/photos/{id}/listings/{crop}/price-estimate`, bouton
"Estimer le prix" dans la fiche (pré-remplit le champ prix, modifiable). La
couverture TCGdex n'est pas totale (sets anciens/obscurs) : dans ce cas le
bouton indique simplement qu'aucune estimation n'est disponible.

### Synchroniser le cache de cartes de référence

```bash
cd backend && source .venv/bin/activate
python -m app.scripts.sync_cards            # catalogue complet pokemontcg.io
python -m app.scripts.sync_cards --limit 200 # test rapide, 200 cartes seulement
python -m app.scripts.sync_cards --force     # re-télécharge tout, y compris ce qui est déjà en cache
```

Le script est **idempotent et reprenable** : relance-le simplement s'il est
interrompu, les cartes déjà en cache sont sautées.

Sans clé API pokemontcg.io, la récupération des métadonnées est fortement
limitée en débit (avec retry/backoff automatique, donc ça finit par passer,
mais lentement). Avec une clé gratuite (à créer sur pokemontcg.io), copie
`.env.example` en `.env` et renseigne `POKEMONTCG_API_KEY=...` — non
versionné, ça accélère fortement la synchronisation complète du catalogue
(~18000+ cartes).

### Détection principale : modèle YOLO (`backend/app/core/card_detector_yolo.py`)

Un modèle YOLOv8-nano, fine-tuné sur le dataset public Roboflow "Trading
Card Detection" (434 images, forké dans un workspace personnel — le projet
d'origine n'autorisait pas la génération de version via l'API pour un
compte tiers). Entraîné localement (CPU, ~1h40 pour 60 époques) via
`backend/app/scripts/train_card_yolo.py` :

```bash
cd backend && source .venv/bin/activate
python -m app.scripts.train_card_yolo            # télécharge le dataset + entraîne (~1h40 CPU)
python -m app.scripts.train_card_yolo --epochs 30 --batch 8  # ajuster si RAM limitée
```

Nécessite une clé API Roboflow gratuite (https://roboflow.com) dans `.env`
(`ROBOFLOW_API_KEY=...`) — utilisée une seule fois pour le téléchargement ;
l'entraînement et l'inférence ensuite sont 100% locaux. Le modèle entraîné
est copié vers `data/models/card_detector.pt` ; `detect_cards()` l'utilise
automatiquement s'il existe, sinon se rabat sur le pipeline OpenCV
(`card_detector.py`, voir plus bas).

**Pipeline d'inférence robuste** (revue dédiée de la détection) — les
détections brutes du modèle passent par des filtres qui exploitent la
géométrie connue du problème (toutes les cartes font la même taille et le
même ratio 63:88) :
1. **filtre de ratio** : une boîte hors des plages carte debout (~0,72) ou
   couchée (~1,40) est un faux positif (constaté : boîtes à ratio 2,2 sur un
   scan, motifs de fond) ;
2. **dédoublonnage par recouvrement** (aire d'intersection / plus petite
   boîte) : élimine les doublons et les boîtes incluses dans une autre ;
3. **filtre d'aire médiane** (à partir de 3 boîtes) : une aire à ±2x de la
   médiane est une fusion de deux cartes ou une moitié de carte ;
4. **escalade multi-échelle** 640 → 960 → 1280 px si rien ne survit aux
   filtres ;
5. **canevas rembourré en dernier recours** : une carte scannée plein cadre
   n'est jamais vue à l'entraînement (cartes posées dans des scènes) — la
   photo est rétrécie au centre d'un canevas gris x2,5 pour redonner à la
   carte une taille relative habituelle (validé : scan qui échouait à toutes
   les échelles détecté à conf 0,85) ;
6. si YOLO ne trouve toujours rien, **repli sur les contours OpenCV**.

Le modèle est **préchargé au démarrage du serveur** (thread) : la première
découpe ne paie plus les ~3s de chargement des poids.

Résultats mesurés sur les 8 photos réelles de test (97 cartes au total,
vérités terrain vérifiées visuellement) : **97/97 détectées, zéro faux
positif**, en 0,06-0,4s par photo une fois le modèle chaud — classeur 9/9,
fonds à motif très contrasté 10/10 (x2), planches 16/16 (x2) et 25/25,
photo 10 cartes, scan HD plein cadre 1/1. Les boîtes détectées ne suivent
pas toujours exactement le ratio 63:88 d'une vraie carte (imprécision du
modèle, surtout si la carte est légèrement tournée) —
`_expand_box_to_card_ratio` élargit toujours la boîte vers ce ratio plutôt
que de l'étirer au redimensionnement final, pour éviter des crops déformés.

### Détection de secours : contours OpenCV (`backend/app/core/card_detector.py`)

Utilisé si le modèle YOLO n'est pas disponible (pas encore
entraîné). Documentation conservée ci-dessous pour ce pipeline de secours :

1. Détection de contours (Canny + fermeture morphologique) sur la photo.
2. Filtrage par aire et par ratio d'aspect proche du format standard d'une
   carte à jouer (63×88mm).
3. Un contour dont l'aire ou le ratio ne correspond pas à une carte seule est
   considéré comme un amas de cartes qui se touchent/chevauchent ; on tente
   de le séparer par ligne de partage des eaux (watershed), amorcée par une
   érosion progressive du masque jusqu'à ce qu'il se scinde.
4. Chaque carte identifiée est redressée par correction de perspective vers
   une image de taille fixe (480×670px), orientée portrait.

Depuis un test sur une vraie photo (planche de cartes sur un plaid à motif
losanges très contrasté), l'étape 1 essaie plusieurs réglages dans l'ordre
(`CONTOUR_PRESETS`) si le premier (nominal, fond uni) ne trouve rien : flou
plus fort, seuils Canny plus élevés ou adaptatifs, fermeture morphologique
plus légère — pour limiter le risque qu'un fond texturé (bois, tissu à motif
discret) fusionne avec les bords des cartes en un seul gros contour. Chaque
crop indique quel réglage a servi (`degraded: true` si un réglage de secours
a été utilisé) ; l'interface affiche alors un avertissement "⚠ Détection en
mode dégradé" pour inviter à vérifier le cadrage plus attentivement.

**Limite connue (chevauchement)** : deux cartes parfaitement alignées et
strictement adjacentes bord à bord (sans chevauchement ni angle) ne créent
aucune concavité exploitable dans le contour fusionné — aucune méthode
purement géométrique ne peut alors les séparer sans indice de
couleur/texture. En pratique, de vraies cartes physiques laissent presque
toujours une ombre ou un liseré visible à la jointure, ce qui contourne ce
cas.

**Limite connue (fond texturé)** : testé en conditions réelles sur un fond à
motif fortement contrasté (plaid à losanges), même les réglages de secours
produisent des découpes fausses (grand pan de fond + carte partielle)
plutôt que d'échouer proprement — aucun réglage géométrique ne peut
fiablement distinguer "bord de carte" de "bord du motif" quand les deux ont
une force de contour comparable. **Pour un fond à ce point texturé, la seule
solution fiable est une surface unie** (feuille de papier de couleur, tapis
neutre, etc.) — c'est le conseil pratique à suivre plutôt que d'attendre que
l'algorithme s'adapte à n'importe quel fond.

## Prérequis et installation (macOS Sequoia & Linux)

Le code est **multiplateforme** et détecte le matériel automatiquement : aucune
modification n'est nécessaire pour passer de la VM Linux au MacBook. Sur Apple
Silicon (M1/M2/M3), le GPU intégré **MPS** est utilisé tout seul pour YOLO
(détection) et DINOv2 (embeddings) ; sur Linux/CPU, tout retombe sur le CPU.

**1. Python 3.10 → 3.12** (Sequoia : installer via [Homebrew](https://brew.sh)
plutôt que le Python système) :
```bash
brew install python@3.12        # macOS
# Linux Debian/Ubuntu : sudo apt install python3 python3-venv
```
> ⚠️ **Pas Python 3.13 ni 3.14** : trop récents. numpy 1.26 (requis pour le
> PyTorch de Mac Intel, cf. `requirements.txt`) n'a pas de binaire au-delà de
> 3.12, et 3.14 n'a de wheels pour presque rien. `run.sh` détecte
> automatiquement un `python3.12`/`3.11`/`3.10` installé et l'utilise, même si
> `python3` par défaut pointe vers une version non supportée (3.9 système ou 3.14).

**2. Tesseract** (OCR — langues + numéros/noms de cartes) :
```bash
# macOS : tesseract-lang fournit fra/jpn/deu/spa/ita d'un coup
brew install tesseract tesseract-lang
# Linux Debian/Ubuntu :
sudo apt install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-jpn \
                    tesseract-ocr-deu tesseract-ocr-spa tesseract-ocr-ita
```

> 💡 **Installation automatique (macOS)** : les étapes 1 et 2 sont facultatives
> si Homebrew est présent — `run.sh` installe tout seul `python@3.12` et
> `tesseract`/`tesseract-lang` s'ils manquent. (`requirements.txt` ne peut, lui,
> contenir que des paquets pip ; Python et Tesseract sont des dépendances
> système.) Sur Linux, l'installation apt reste manuelle (elle exige `sudo`).

**3. Lancer** — `./run.sh` crée le venv, installe les dépendances Python
(`backend/requirements.txt`) et démarre le serveur. **Note torch/PyTorch** :
sur macOS, `pip` installe automatiquement la roue standard (avec support MPS) —
ne PAS utiliser l'index `download.pytorch.org/whl/cpu`, qui est réservé à
Linux. Rien de spécial à faire, `run.sh` s'en charge.

**4. Modèle d'embeddings DINOv2** : téléchargé automatiquement au premier
lancement (via `torch.hub`, une seule fois, nécessite un accès Internet). Voir
la section « Repli embeddings » plus haut.

**5. Application Mac (facultatif)** : `macos/Splitdex.app` est un lanceur —
double-clic → démarre le serveur (via `run.sh`) et ouvre `localhost:8000` dans
Chrome (repli : navigateur par défaut). Glissez-la dans le **Dock** ou vers
**Applications** pour un accès en un clic, avec l'icône Pokéball. Comme elle
n'est pas signée, au **premier** lancement : clic droit → **Ouvrir** (ou
`xattr -dr com.apple.quarantine macos/Splitdex.app`). Gardez le `.app` dans le
dossier `macos/` du projet — il repère la racine par sa position.

### Données : cache de référence, modèle, embeddings

Le dépôt **ne versionne pas** les données volumineuses et régénérables (~3 Go) :
le cache de 20 000+ cartes (`data/db/`), les uploads (`data/uploads/`) et les
artefacts d'entraînement. Le **modèle de détection** `data/models/card_detector.pt`
(6 Mo), lui, **est versionné** — l'app détecte les cartes dès le clone.

Pour rendre l'identification opérationnelle sur une nouvelle machine, deux
options :
- **Copier** le dossier `data/` depuis une machine déjà configurée (rsync/scp)
  — le plus rapide, réutilise le cache et les embeddings déjà calculés ;
- **Reconstruire** :
  ```bash
  cd backend && source .venv/bin/activate
  python -m app.scripts.sync_cards            # cache pokemontcg.io (long sans clé API)
  python -m app.scripts.build_card_embeddings # index DINOv2 (~45 min VM, ~qq min M1)
  ```

## Lancer l'application

```bash
./run.sh
```

Le script crée un environnement virtuel Python dans `backend/.venv/`, installe
les dépendances, puis démarre le serveur sur `0.0.0.0:8000`.

Sur la machine hôte (celle qui fait tourner l'app) :
- http://localhost:8000

Depuis un autre appareil du même réseau Wi-Fi/Ethernet (ex: le Mac) :
- http://ADRESSE_IP_DE_LA_MACHINE_HOTE:8000

## Trouver l'adresse IP locale de la machine hôte

```bash
# macOS (Wi-Fi = en0, Ethernet = en1 selon la machine) :
ipconfig getifaddr en0

# Linux :
hostname -I
# ou, plus détaillé :
ip addr show | grep "inet " | grep -v 127.0.0.1
```

Cherche une adresse de la forme `192.168.x.x` ou `10.x.x.x` (réseau privé).
C'est celle-ci qu'il faut utiliser depuis le Mac, ex : `http://192.168.1.42:8000`.

## Vérifier qu'aucun pare-feu ne bloque le port 8000

- **UFW** (Ubuntu/Debian) :
  ```bash
  sudo ufw status
  sudo ufw allow 8000/tcp   # si nécessaire
  ```
- **firewalld** (Fedora/RHEL) :
  ```bash
  sudo firewall-cmd --list-ports
  sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload
  ```
- Si aucun pare-feu logiciel n'est actif sur la machine (`ufw` inactif,
  `firewalld` absent), rien à faire de plus. Vérifie aussi que le Mac et la
  machine hôte sont bien sur le **même réseau/sous-réseau** (pas de VLAN
  invités isolé sur la box internet, par exemple).

## Sécurité / authentification

Aucune authentification en V1 (usage LAN de confiance uniquement — ne pas
exposer ce port sur Internet, ex: pas de redirection NAT/port-forwarding sur
la box). La structure du backend (routers séparés dans `backend/app/api/`)
permettra d'ajouter facilement un middleware d'auth (ex: token partagé, Basic
Auth) plus tard si besoin.

## Arborescence du projet

```
Splitdex/
├── run.sh                     # lance le backend (venv + uvicorn --host 0.0.0.0)
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # app FastAPI, monte le frontend + les routes API
│       ├── core/
│       │   ├── config.py           # chemins, constantes, clé API pokemontcg.io
│       │   ├── card_detector.py    # détection & découpe des cartes (OpenCV, secours)
│       │   ├── card_detector_yolo.py # détection & découpe par modèle YOLO (principale)
│       │   ├── db.py               # connexion SQLite + schéma
│       │   ├── pokemontcg_client.py # client API pokemontcg.io (pagination, retry)
│       │   ├── phash.py            # perceptual hash (empreinte d'image)
│       │   ├── number_detector.py  # OCR du numéro de carte (indice d'identification)
│       │   ├── name_detector.py    # OCR du nom d'espèce (indice d'identification)
│       │   ├── pokemon_names_fr.py # correspondance noms FR -> EN (génération 1 + sélection)
│       │   ├── pokemon_names_jp.py # correspondance noms JP -> EN (génération 1)
│       │   ├── card_identifier.py  # identification : indices numéro/nom > pHash, puis ORB
│       │   ├── language_detector.py # détection langue d'impression (OCR + mots-clés)
│       │   ├── card_translations.py # traductions FR (séries/sets/raretés/langues)
│       │   ├── validation.py       # validation des ids d'URL (anti-traversée de chemin)
│       │   ├── tcgdex_client.py    # client API TCGdex (recherche carte par nom/numéro)
│       │   ├── price_estimator.py  # cote Cardmarket selon la langue détectée
│       │   └── description_generator.py # rendu des gabarits Jinja2 (titre + description)
│       ├── api/
│       │   ├── uploads.py      # routes /api/upload, /api/uploads
│       │   ├── crops.py        # routes /api/photos/{id}/crops
│       │   ├── vinted.py       # fiche préparée + userscript de remplissage Vinted
│       │   ├── identify.py     # routes /api/photos/{id}/identify
│       │   ├── reference.py    # routes /api/reference/status, /search, /conditions
│       │   └── listings.py     # routes /api/photos/{id}/listings, /export
│       └── scripts/
│           ├── sync_cards.py       # synchronisation du cache de cartes (CLI)
│           └── train_card_yolo.py  # entraînement du modèle de détection YOLO (CLI)
├── frontend/                   # HTML/JS léger, servi par FastAPI (pas de build)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── templates/                   # gabarits Jinja2 des descriptions Vinted (éditables)
│   ├── vinted_title.txt.j2
│   └── vinted_description.txt.j2
├── .env.example                 # copier en .env pour POKEMONTCG_API_KEY/ROBOFLOW_API_KEY (non versionné)
└── data/
    ├── uploads/                 # photos originales uploadées
    │   └── crops/{photo_id}/     # cartes découpées + meta.json (Phase 2)
    ├── models/                  # dataset + poids du modèle de détection YOLO
    └── db/
        ├── splitdex.sqlite3      # cache cartes de référence + résultats d'identification
        └── reference_thumbnails/ # miniatures des cartes de référence (cache local)
```

## Roadmap

1. ✅ Phase 1 — setup projet, upload de photo, accessibilité LAN.
2. ✅ Phase 2 — détection & découpe automatique des cartes sur une photo
   (OpenCV, correction de perspective), affichage des crops.
3. ✅ Phase 3 — cache local pokemontcg.io (SQLite) + identification des
   cartes (pHash + reclassement ORB). OCR différé (Tesseract non installé).
4. ✅ Phase 4 — génération de titre + description Vinted via gabarit Jinja2
   personnalisable (`templates/`), bouton "Copier" dans l'interface.
5. ✅ Phase 5 — interface de revue/correction (identification, état, prix,
   texte) + export ZIP final (images + textes prêts pour Vinted).

Toutes les phases initialement prévues sont là. Prochaines pistes possibles
(à discuter) : OCR (numéro de carte, langue), affinage du style des
descriptions avec tes propres exemples, authentification si l'usage
s'élargit au-delà du LAN de confiance.
