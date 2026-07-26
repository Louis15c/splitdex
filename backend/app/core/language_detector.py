"""Détection de la langue d'impression d'une carte via OCR (Tesseract).

Approche par **score de vocabulaire pondéré sur le texte des attaques** :
les cartes Pokémon regorgent de formules ultra-caractéristiques par langue
("Lancez une pièce... dégâts" / "Flip a coin... damage" / "Wirf eine
Münze... Schaden" / "Lanza una moneda..." / "Lancia una moneta...") — bien
plus discriminantes et nombreuses que les seuls mots-clés de mise en page
(PV/Faiblesse/Retraite) utilisés initialement, que l'OCR écorchait trop
souvent (mesuré sur 52 cartes françaises réelles : 2 détectées seulement,
13 faussement étiquetées japonaises). Le score se calcule sur les tokens du
texte normalisé (accents retirés, majuscules) : robuste aux accents perdus
par l'OCR.

Le japonais n'est PAS décidé ici : mesuré sur de vraies cartes, l'OCR
japonais hallucine sur les reflets holographiques des cartes latines des
statistiques CJK (proportion, kana purs, kanji) **indiscernables** de celles
d'une vraie carte japonaise (ratio 0,37 pour la vraie vs jusqu'à 0,47
halluciné) — aucun seuil ne sépare les deux. La langue japonaise est donc
établie en aval, par deux signaux fiables : la correspondance exacte du nom
d'espèce dans la table japonaise (`name_detector.py`, ex: "ガメール") et le
vote majoritaire par photo (`api/identify.py`).

Si Tesseract (le binaire système) n'est pas installé, ce module ne plante
pas : `detect_language` retourne simplement `None` (langue indéterminée),
comme si aucun marqueur n'avait été trouvé. Idem si un pack de langue donné
(ex: `kor`) n'est pas installé : cette langue est simplement ignorée.

Deux réglages Tesseract se sont révélés déterminants en pratique, sur des
crops réels qui ne renvoyaient auparavant aucun texte exploitable :
- **`--psm 11`** (texte épars, sans ordre particulier) plutôt que le mode par
  défaut (page complète structurée) : la mise en page d'une carte (gros nom,
  illustration, texte d'attaque, petit numéro) n'est pas une page de texte
  classique, et le mode par défaut échoue souvent à en extraire quoi que ce
  soit.
- **Passes séparées par famille de script** plutôt qu'un seul appel avec
  toutes les langues combinées : mélanger le japonais avec les langues
  latines dilue nettement la reconnaissance de chacune (testé : "カメール"
  illisible avec `eng+fra+...+jpn` combinés, correctement lu avec `jpn` seul).
"""

import os
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

# Tesseract (sous-processus) parallélise en interne via OpenMP (~4 threads).
# Quand plusieurs crops sont OCRisés en parallèle (voir api/identify.py),
# plusieurs instances multi-threads se disputent les mêmes cœurs et les
# spinlocks OpenMP s'effondrent (constaté : passes de ~1,5s devenues des
# minutes). Un seul thread interne par instance : à peine plus lent seul,
# et la parallélisation entre crops devient réellement efficace.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

MIN_OCR_WIDTH = 1200  # Tesseract lit mal le texte fin des cartes en dessous de cette taille

# Verdict japonais (voir la fin de `detect_language`) : volume de katakana ET
# absence de vocabulaire latin, les deux conditions étant nécessaires.
_KATAKANA = re.compile(r"[゠-ヿ]")
MIN_KATAKANA_FOR_JAPANESE = 10
MAX_LATIN_FOR_JAPANESE = 10

# Vocabulaire pondéré par langue, tokens NORMALISÉS (accents retirés,
# majuscules — voir _normalize). Poids 3 : formules quasi exclusives au TCG
# dans cette langue (verbes d'attaque, termes de règles). Poids 2 :
# distinctifs mais parfois écorchés/partagés. Poids 1 : mots courants,
# individuellement ambigus mais nombreux dans un texte réel.
LANGUAGE_VOCABULARY = {
    "Français": {
        3: ["LANCEZ", "PIOCHEZ", "DEFAUSSEZ", "MELANGEZ", "CHERCHEZ", "DEGATS",
            "INFLIGE", "FAIBLESSE", "RETRAITE", "DRESSEUR", "PIECE", "ADVERSE",
            "POIDS", "TAILLE"],
        2: ["VOTRE", "CETTE", "CHAQUE", "ATTAQUE", "BANC", "PV", "NIVEAU",
            "ENERGIE", "POKEMON", "EVOLUTION"],
        1: ["LE", "LES", "DES", "UNE", "EST", "SUR", "POUR", "AVEC", "VOS", "AU"],
    },
    "Anglaise": {
        3: ["FLIP", "COIN", "COINS", "DAMAGE", "HEADS", "TAILS", "DISCARD",
            "OPPONENT", "WEAKNESS", "RETREAT", "TRAINER", "BENCH", "SHUFFLE",
            "EVOLVES"],
        2: ["YOUR", "EACH", "THIS", "ATTACK", "SEARCH", "ENERGY", "CARD", "HP",
            "DECK", "BASIC", "STAGE"],
        1: ["THE", "OF", "IF", "MAY", "FROM", "AND", "DOES", "LBS"],
    },
    "Allemande": {
        3: ["WIRF", "MUNZE", "SCHADEN", "GEGNER", "ABLEGESTAPEL", "SCHWACHE",
            "RUCKZUG", "MISCHE", "DURCHSUCHE"],
        2: ["DEINEM", "DEINEN", "DEINER", "FALLS", "KOPF", "ZAHL", "KARTE",
            "KP", "BASIS", "BEI"],
        1: ["DER", "DIE", "DAS", "UND", "EINE", "EINEN", "MIT", "AUF"],
    },
    "Espagnole": {
        3: ["LANZA", "MONEDA", "DANO", "BARAJA", "DESCARTA", "DEBILIDAD",
            "RETIRADA", "ENTRENADOR", "RIVAL"],
        2: ["BUSCA", "CRUZ", "TUS", "ATAQUE", "BANCA", "PS", "BASICO", "ESTE"],
        1: ["EL", "LOS", "TU", "CARA", "PARA", "CADA", "QUE"],
    },
    "Italienne": {
        3: ["LANCIA", "MONETA", "DANNI", "MAZZO", "AVVERSARIO", "DEBOLEZZA",
            "RITIRATA", "ALLENATORE", "PANCHINA", "RIMESCOLA"],
        2: ["CERCA", "SCARTA", "TESTA", "TUO", "TUOI", "ATTACCO", "PS", "QUESTO"],
        1: ["IL", "GLI", "DEL", "CHE", "OGNI", "CON", "PER"],
    },
}

TESSERACT_LANG_CODES = {
    "Français": "fra",
    "Anglaise": "eng",
    "Allemande": "deu",
    "Espagnole": "spa",
    "Italienne": "ita",
}

CANDIDATE_TESSERACT_CODES = ["eng", "fra", "deu", "spa", "ita", "jpn"]



# Seuils de décision du score de vocabulaire (voir detect_language) : score
# et avance minimum sur la 2e langue pour trancher — en dessous, on préfère
# "indéterminé" (rattrapé en aval par le nom d'espèce ou le vote par photo)
# à une affirmation risquée.
MIN_VOCAB_SCORE = 4
MIN_VOCAB_MARGIN = 2


def available_ocr_languages() -> list[str]:
    try:
        installed = set(pytesseract.get_languages(config=""))
    except Exception:
        return []
    return [code for code in CANDIDATE_TESSERACT_CODES if code in installed]




def upscale_for_ocr(image_bgr: np.ndarray) -> np.ndarray:
    width = image_bgr.shape[1]
    if width >= MIN_OCR_WIDTH:
        return image_bgr
    scale = MIN_OCR_WIDTH / width
    new_size = (round(image_bgr.shape[1] * scale), round(image_bgr.shape[0] * scale))
    return cv2.resize(image_bgr, new_size, interpolation=cv2.INTER_CUBIC)


def _sharpened_gray(image_bgr: np.ndarray) -> np.ndarray:
    """Agrandissement Lanczos + niveaux de gris + masque flou (unsharp) :
    prépare les petits caractères pour la passe `--psm 6`."""
    width = image_bgr.shape[1]
    scale = max(1.0, MIN_OCR_WIDTH / width)
    upscaled = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    return cv2.addWeighted(gray, 1.8, blurred, -0.8, 0)


# Passe de sauvetage : en dessous de ce score de vocabulaire après les deux
# passes latines standard, on tente une binarisation adaptative (voir
# ocr_text). Au-delà, la langue est déjà décidable, inutile de payer une
# passe Tesseract de plus.
RESCUE_MIN_TOP_SCORE = 8
RESCUE_TARGET_WIDTH = 1440


def _adaptive_binarized(image_bgr: np.ndarray) -> np.ndarray:
    """Binarisation adaptative gaussienne après agrandissement : sur les
    cartes dont le texte est imprimé sur une bande COLORÉE (rose/rouge des
    types Fée, lavande des Psy...), le passage en niveaux de gris écrase le
    contraste et Tesseract ne lit plus rien — le seuil local le restaure.
    Mesuré sur 3 cartes à texte pourtant lisible à l'œil mais score 0-2 avec
    les autres passes : scores 5-12 après binarisation, tous décidables."""
    scale = max(1.0, RESCUE_TARGET_WIDTH / image_bgr.shape[1])
    upscaled = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def ocr_text(image_bgr: np.ndarray) -> str:
    """OCR d'un crop de carte, robuste à sa mise en page (voir docstring du
    module) : passes séparées latin/japonais plutôt qu'un seul appel avec
    toutes les langues combinées (qui se dilueraient entre elles), et DEUX
    passes latines complémentaires — `--psm 11` (texte épars) lit bien les
    cartes nettes mais rend quasi rien sur les cartes photographiées à basse
    résolution optique, où `--psm 6` sur image renforcée (gris + unsharp)
    récupère au moins les gros caractères (nom, noms d'attaque, STAGE/NIVEAU),
    suffisants pour le score de vocabulaire (mesuré : 2 cartes anglaises
    passées de score 2 à 8-12 grâce à cette passe). Retourne la concaténation
    des passes (chaîne vide si Tesseract absent ou si aucune passe n'aboutit).
    La passe `jpn` sert aux indices de nom d'espèce japonais (name_detector) ;
    ses hallucinations sur les cartes latines sont sans effet sur la langue
    (voir docstring du module).
    """
    available = available_ocr_languages()
    if not available:
        return ""

    upscaled = upscale_for_ocr(image_bgr)
    pil_image = Image.fromarray(upscaled[:, :, ::-1])  # BGR -> RGB

    latin_languages = [lang for lang in available if lang != "jpn"]
    passes = []

    # Les deux passes standard latines décident la grande majorité des cartes.
    latin_decisive = False
    if latin_languages:
        latin_spec = "+".join(latin_languages)
        try:
            passes.append(pytesseract.image_to_string(pil_image, lang=latin_spec, config="--psm 11"))
        except Exception:
            pass
        try:
            sharp = Image.fromarray(_sharpened_gray(image_bgr))
            passes.append(pytesseract.image_to_string(sharp, lang=latin_spec, config="--psm 6"))
        except Exception:
            pass
        latin_scores = _vocabulary_scores("\n".join(passes))
        top_latin = max((score for score, _ in latin_scores.values()), default=0)
        latin_decisive = top_latin >= RESCUE_MIN_TOP_SCORE

    # Passes coûteuses supplémentaires (binarisation de sauvetage + japonais)
    # UNIQUEMENT quand le latin ne tranche pas franchement. Une carte latine
    # nette est déjà décidée : inutile de payer la passe japonaise (~une passe
    # OCR entière, soit ~2s) sur chaque carte française/anglaise — c'est le cas
    # courant. Une vraie carte japonaise donne un score latin faible (kana
    # illisibles en latin) et déclenche donc bien la passe `jpn`.
    if latin_languages and not latin_decisive:
        # Sauvetage : texte imprimé sur bande colorée écrasé en niveaux de gris
        # (voir _adaptive_binarized).
        try:
            binarized = Image.fromarray(_adaptive_binarized(image_bgr))
            passes.append(pytesseract.image_to_string(binarized, lang=latin_spec, config="--psm 6"))
        except Exception:
            pass

    if "jpn" in available and not latin_decisive:
        # Sert aux indices de nom d'espèce japonais (name_detector).
        try:
            passes.append(pytesseract.image_to_string(pil_image, lang="jpn", config="--psm 11"))
        except Exception:
            pass

    return "\n".join(passes)


def _normalize(text: str) -> str:
    """Majuscules + accents retirés : l'OCR perd souvent les accents
    ("dégâts" lu "degats"), le vocabulaire est stocké déjà normalisé."""
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).upper()


# Une décision exige au moins un mot "substantiel" : poids >= 2 ET assez
# long pour ne pas sortir du bruit OCR. Constaté sans ce garde-fou : une
# full-art française au texte minuscule étiquetée "Italienne" parce que
# l'OCR-garbage contenait "PS" (poids 2) et "IL" — des jetons de 2 lettres
# apparaissent par hasard dans n'importe quel charabia, "ATTAQUE" ou
# "DAMAGE" jamais.
SUBSTANTIAL_MIN_WEIGHT = 2
SUBSTANTIAL_MIN_LENGTH = 4


def _vocabulary_scores(text: str) -> dict[str, tuple[int, bool]]:
    """Par langue : (score pondéré, présence d'un mot substantiel), calculé
    sur les TOKENS du texte normalisé (pas de recherche en sous-chaîne :
    "LE" ne doit pas matcher dans "TABLE")."""
    import re

    tokens = re.findall(r"[A-Z]+", _normalize(text))
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    scores = {}
    for language, weighted_words in LANGUAGE_VOCABULARY.items():
        score = 0
        substantial = False
        for weight, words in weighted_words.items():
            for word in words:
                occurrences = counts.get(word, 0)
                if not occurrences:
                    continue
                # Un même mot répété compte plusieurs fois (borné à 3 pour
                # qu'un artefact d'OCR répétitif ne fausse pas tout).
                score += weight * min(occurrences, 3)
                if weight >= SUBSTANTIAL_MIN_WEIGHT and len(word) >= SUBSTANTIAL_MIN_LENGTH:
                    substantial = True
        scores[language] = (score, substantial)
    return scores


def detect_language(image_bgr: np.ndarray, text: str | None = None) -> str | None:
    """Retourne un libellé ("Français", "Anglaise", "Japonaise", ...) ou
    `None` si indéterminable (Tesseract absent, ou signal trop faible).

    `text` : résultat d'`ocr_text` déjà calculé pour ce crop, à fournir quand
    l'appelant enchaîne plusieurs détecteurs OCR sur la même image — l'OCR
    est de loin l'étape la plus lente du pipeline (~3s par passe), le
    recalculer à chaque détecteur triplait le temps d'identification.
    """
    available = available_ocr_languages()
    if not available:
        return None

    if text is None:
        text = ocr_text(image_bgr)
    if not text:
        return None

    scores = _vocabulary_scores(text)
    ranked = sorted(scores.items(), key=lambda item: item[1][0], reverse=True)
    top_language, (top_score, top_substantial) = ranked[0]
    runner_up_score = ranked[1][1][0] if len(ranked) > 1 else 0

    if (
        top_substantial
        and top_score >= MIN_VOCAB_SCORE
        and top_score >= runner_up_score + MIN_VOCAB_MARGIN
    ):
        return top_language

    # Verdict "Japonaise" : beaucoup de katakana ET quasiment aucun vocabulaire
    # latin. La seule présence de katakana ne suffit pas — la passe `jpn`
    # hallucine des kana sur les reflets holographiques des cartes latines
    # (mesuré : 22 katakana sur une carte française reverse-holo, soit PLUS que
    # sur une vraie carte japonaise à 17). Ce qui sépare vraiment les deux,
    # c'est le texte latin : une carte française lisible score 14 à 64 de
    # vocabulaire, une vraie japonaise 2 à 8, l'OCR n'ayant presque rien de
    # latin à se mettre sous la dent.
    if len(_KATAKANA.findall(text)) >= MIN_KATAKANA_FOR_JAPANESE and top_score <= MAX_LATIN_FOR_JAPANESE:
        return "Japonaise"

    return None  # signal trop faible ou ambigu : on ne devine pas
