"""Extraction OCR du nom de l'espèce imprimé sur une carte (gros caractères
en haut, bien plus faciles à lire pour l'OCR que le petit numéro en bas —
voir `number_detector.py`), pour identifier l'espèce avant de comparer
l'artwork. Traduit vers le nom anglais utilisé dans le cache
(`reference_cards.name`) via `pokemon_names_fr.py` / `pokemon_names_jp.py`.

Couverture par langue volontairement partielle (voir ces modules) — les
langues/espèces non couvertes retombent simplement sur le pipeline pHash
existant, rien ne casse. On tente la table d'une langue dès que la langue
détectée n'est pas *confirmée* être une AUTRE langue précise : `detect_language`
utilise des mots-clés de mise en page assez stricts (voir son docstring) et
peut renvoyer `None` (indéterminée) sur une carte pourtant bien dans cette
langue si l'OCR écorche légèrement ces mots-clés précis (ex: "Fablesse" pour
"Faiblesse"), même quand le reste du texte — dont le nom de l'espèce — reste
bien lisible. Ne pas gâcher cette lisibilité à cause d'un classement de
langue trop prudent.
"""

import re
from difflib import SequenceMatcher

import numpy as np

from app.core.language_detector import ocr_text
from app.core.pokemon_names_fr import (
    POKEMON_NAME_EN_BY_NORMALIZED_FR,
    POKEMON_NAME_FR,
    normalize_name,
)
from app.core.pokemon_names_jp import (
    POKEMON_NAME_EN_BY_JP,
    POKEMON_NAME_EN_BY_NORMALIZED_JP,
    POKEMON_NAME_JP,
)

# Noms ANGLAIS normalisés — ceux du cache de référence lui-même. Une carte
# anglaise (mais aussi espagnole/italienne, qui impriment les noms d'espèce
# anglais) affiche ce nom en gros caractères : c'est souvent le seul texte
# lisible sur un crop à basse résolution optique. Minimum 4 caractères : un
# nom très court ("Mew", "Muk") sortirait trop facilement du bruit OCR en
# recherche par sous-chaîne.
POKEMON_NAME_EN_BY_NORMALIZED_EN = {
    normalize_name(name_en): name_en
    for name_en in POKEMON_NAME_FR
    if len(normalize_name(name_en)) >= 4
}


# Ligne "Évolution de : X" / "Evolves from X" (et équivalents DE/ES/IT) : le
# nom qui suit est celui de la PRÉ-évolution, pas celui de la carte. Sans ce
# filtre, une carte Blancoton était identifiée "Tournicoton" — la ligne
# d'évolution contient un nom d'espèce parfaitement valide et souvent plus
# long que le vrai nom (la règle du plus-long-match le préférait).
# Le français élide : "Évolution d'Herbizarre", "Évolution de Racaillou",
# "Évolution du/des ..." — d'où le groupe (DE|DES|DU|D'…). Sans la variante
# élidée "D'", le Florizarre du Set de Base était identifié "Herbizarre"
# (Ivysaur, sa pré-évolution citée juste sous le titre).
_EVOLUTION_MARKER = re.compile(
    r"(?:EVOLUTION\s*(?:DES|DE|DU|D['’]?)?|EVOLVES\s*FROM|ENTWICKELT\s*SICH\s*AUS|"
    r"EVOLUCIONA\s*DE|SI\s*EVOLVE\s*DA)\s*:?\s*$"
)
_EVOLUTION_CONTEXT_CHARS = 24


def _find_matches(
    haystack: str, table: dict[str, str], table_language: str | None, relaxed: bool = False
) -> list[tuple[str, str, str | None]]:
    """Cherche chaque nom de la table dans le texte, en BORNES DE MOTS : la
    recherche en sous-chaîne brute matchait "MAGNETI" (Magnéti/Magnemite) à
    l'intérieur de "MAGNETIQUE" dans le texte de saveur d'un Métang — plus
    long que "METANG", il gagnait le plus-long-match. Une occurrence qui ne
    suit pas immédiatement un marqueur de ligne d'évolution suffit à retenir
    le nom.

    `relaxed` : tolère du bruit OCR collé au nom, des DEUX côtés — à la fin
    ("ELECTRODEWSS" lu sur une vraie carte Electrode) comme au début
    ("peReptincel" lu sur une vraie carte Reptincel, le "pe" venant du logo
    d'évolution voisin). Le préfixe toléré est court (≤ 3 lettres) pour rester
    du bruit de bord et ne pas transformer la recherche en sous-chaîne libre au
    milieu d'un mot quelconque. À n'utiliser qu'en second recours, si la passe
    stricte n'a rien trouvé sur AUCUNE table : sinon "MAGNETIQUE" redeviendrait
    un match de "MAGNETI"."""
    results = []
    for key, name_en in table.items():
        if not key:
            continue
        if relaxed:
            pattern = rf"(?<![A-Z0-9])[A-Z]{{0,3}}{re.escape(key)}"
        else:
            pattern = rf"(?<![A-Z0-9]){re.escape(key)}(?![A-Z0-9])"
        for match in re.finditer(pattern, haystack):
            prefix = haystack[max(0, match.start() - _EVOLUTION_CONTEXT_CHARS):match.start()]
            if _EVOLUTION_MARKER.search(prefix):
                continue  # pré-évolution mentionnée, pas le nom de la carte
            results.append((key, name_en, table_language))
            break
    return results


# Confirmation « japonaise » a posteriori : suffisamment de similarité entre le
# nom japonais de la carte IDENTIFIÉE et un mot CJK lu par l'OCR. Mesuré sur des
# cartes réelles : 0.57 (プラスル lu "人ラス") et 0.67 (ガブリアス lu "ウリアズ")
# pour de vraies cartes japonaises, contre 0.00 sur huit cartes françaises —
# la séparation est nette, 0.5 laisse de la marge des deux côtés.
_JAPANESE_CONFIRM_RATIO = 0.5
_CJK_RUN = re.compile(r"[゠-ヿ぀-ゟ一-鿿]+")


def _japanese_species_name(card_name_en: str | None) -> str | None:
    """Nom japonais de l'espèce portée par un nom de carte de référence
    ("Garchomp ex" -> ガブリアス, "Team Rocket's Diglett" -> ディグダ) : on teste
    chaque mot et on garde le plus long qui est une espèce connue, les noms de
    cartes portant des préfixes/suffixes de variante autour de l'espèce."""
    if not card_name_en:
        return None
    best = None
    for token in re.split(r"[^A-Za-z]+", card_name_en):
        japanese = POKEMON_NAME_JP.get(token)
        if japanese and (best is None or len(token) > len(best[0])):
            best = (token, japanese)
    return best[1] if best else None


def japanese_name_confirms(text: str | None, card_name_en: str | None) -> bool:
    """Vrai si le nom japonais de la carte identifiée se retrouve, même écorché,
    dans le texte OCR — signal de langue japonaise.

    L'OCR lit le katakana de façon très approximative (プラスル -> "人ラス") : la
    correspondance EXACTE de `detect_pokemon_name_hint` échoue alors, et une
    recherche floue parmi les 1025 espèces produirait des faux positifs. Ici on
    ne teste qu'UNE chaîne, celle de la carte déjà identifiée par l'image : le
    risque de coïncidence est minime, et une carte non japonaise n'a de toute
    façon aucun katakana à offrir."""
    target = _japanese_species_name(card_name_en)
    if not target or not text:
        return False
    target = normalize_name(target)  # neutralise dakuten/handakuten (cf. module JP)
    if len(target) < 3:
        return False
    for run in _CJK_RUN.findall(text):
        run = normalize_name(run)
        # Fenêtre glissante de la taille du nom (±1 caractère) : le nom est noyé
        # dans un mot plus long quand l'OCR colle le texte voisin.
        for size in (len(target), len(target) + 1):
            for start in range(max(1, len(run) - size + 1)):
                window = run[start : start + size]
                if SequenceMatcher(None, target, window).ratio() >= _JAPANESE_CONFIRM_RATIO:
                    return True
    return False


def detect_pokemon_name_hint(
    image_bgr: np.ndarray, language: str | None, text: str | None = None
) -> tuple[str | None, str | None]:
    """Retourne `(nom anglais, langue de la table qui a matché)` — le nom
    pour interroger `reference_cards.name`, la langue pour fiabiliser
    `detect_language` : trouver un nom d'espèce exact dans une table donnée
    est un signal de langue au moins aussi fiable que les mots-clés
    génériques de `detect_language`, et permet de lever une indétermination
    (voir `card_identifier.identify`). `(None, None)` si indéterminable.

    `text` : résultat d'`ocr_text` déjà calculé pour ce crop (voir
    `detect_language` — évite de relancer l'OCR, l'étape la plus lente).
    """
    if text is None:
        text = ocr_text(image_bgr)
    if not text:
        return None, None

    normalized_text = normalize_name(text)

    def _scan(relaxed: bool) -> list[tuple[str, str, str | None]]:
        matches: list[tuple[str, str, str | None]] = []

        if language is None or language == "Français":
            for key, name_en, _lang in _find_matches(
                normalized_text, POKEMON_NAME_EN_BY_NORMALIZED_FR, "Français", relaxed
            ):
                # Un nom identique en français et en anglais ("Granbull",
                # "Anorith") ne porte AUCUNE information de langue : sans ce
                # garde-fou, chaque carte anglaise dont l'espèce garde son
                # nom anglais en français serait étiquetée "Français" via
                # cette table.
                carries_language = key != normalize_name(name_en)
                matches.append((key, name_en, "Français" if carries_language else None))

        if language not in ("Français", "Japonaise"):
            # Cartes anglaises — mais aussi espagnoles/italiennes, qui
            # impriment les noms d'espèce anglais. Indice d'identité
            # seulement (langue None) : le nom anglais est aussi celui
            # affiché sur les cartes de plusieurs autres langues, il ne
            # prouve pas l'anglais.
            matches += _find_matches(normalized_text, POKEMON_NAME_EN_BY_NORMALIZED_EN, None, relaxed)

        if language is None or language == "Japonaise":
            # Texte brut contre la table exacte d'abord (zéro ambiguïté) ; le
            # repli tolérant au dakuten (voir pokemon_names_jp.py) n'est
            # tenté que si cette passe stricte ne trouve rien.
            jp_matches = _find_matches(text, POKEMON_NAME_EN_BY_JP, "Japonaise", relaxed)
            if not jp_matches:
                jp_matches = _find_matches(
                    normalized_text, POKEMON_NAME_EN_BY_NORMALIZED_JP, "Japonaise", relaxed
                )
            matches += jp_matches

        return matches

    matches = _scan(relaxed=False)
    if not matches:
        # Aucun nom en bornes strictes : l'OCR a peut-être collé du bruit à
        # la fin du nom ("ELECTRODEWSS") — seconde chance, début borné
        # seulement (voir _find_matches).
        matches = _scan(relaxed=True)

    if not matches:
        return None, None

    # Le nom le plus long qui apparaît dans le texte : évite qu'un nom court
    # ("Abo") ne matche par coïncidence à l'intérieur d'un mot plus long.
    # À longueur égale, une entrée porteuse de langue prime (le même nom peut
    # matcher via deux tables, dont une seule prouve la langue).
    _best_key, best_en, matched_language = max(
        matches, key=lambda item: (len(item[0]), item[2] is not None)
    )
    return best_en, matched_language
