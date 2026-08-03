"""Génération de titre + description Vinted à partir des métadonnées d'une
carte identifiée, via des gabarits Jinja2 éditables dans `templates/` à la
racine du projet (pas besoin de toucher au code Python pour changer le
style). Structure et ton reconstruits à partir d'exemples réels d'annonces
Vinted fournis par l'utilisateur.
"""

from jinja2 import Environment, FileSystemLoader

from app.core.card_translations import (
    hashtag,
    language_tags,
    rarity_display,
    translate_series,
    translate_set_name,
    variant_title,
)
from app.core.config import CONDITION_PHRASES, DEFAULT_LISTING_CONDITION, SHOP_HASHTAG, TEMPLATES_DIR
from app.core.pokemon_names_fr import translate_card_name_to_fr

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _build_hashtags(name: str | None, variant: str | None, language_tag: str | None, series: str | None, set_name: str | None) -> list[str]:
    tags = ["pokemon", "pokemoncards"]
    if name:
        tags.append(hashtag(name))
    if variant:
        tags.extend(hashtag(word) for word in variant.split())
    if language_tag:
        tags.append(language_tag)  # conservé en majuscules, ex: "#ITA" (pas de minuscule ici)
    if series:
        tags.append(hashtag(series))
    if set_name:
        tags.append(hashtag(set_name))
    tags.append("collection")
    tags.append(SHOP_HASHTAG)

    seen = set()
    unique_tags = []
    for tag in tags:
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            unique_tags.append(tag)
    return unique_tags


def generate_listing_text(
    card: dict,
    condition: str | None = None,
    language: str | None = None,
    variant: str | None = None,
) -> dict:
    """`card` attend les clés name, set_name, series, number, printed_total,
    rarity (celles stockées dans `reference_cards`).

    Le public visé est francophone : une carte en français n'a donc pas
    besoin d'être signalée (c'est la langue par défaut implicite) — seule une
    carte non-française (anglaise, japonaise, ...) est mentionnée, dans le
    titre et la description, avec un tag court ("ITA", "JAP"...) comme
    observé dans de vraies annonces. `language=None` (indéterminée) est
    traité comme le français : pas de mention plutôt qu'une affirmation qui
    pourrait être fausse.

    Le prix n'apparaît jamais dans le texte généré : sur Vinted c'est un
    champ structuré séparé du titre/de la description, pas un élément du
    texte libre (confirmé par les exemples fournis).
    """
    resolved_condition = condition or DEFAULT_LISTING_CONDITION
    displayed_language = language if language and language != "Français" else None
    language_tag, language_adjective = language_tags(displayed_language)

    # Le cache (pokemontcg.io) ne connaît que les noms anglais : le public
    # visé étant francophone, le nom d'espèce est traduit partout (titre,
    # description, hashtags). Non couvert par la table = reste en anglais.
    # Nom OFFICIEL français quand TCGdex le publie ("Taupiqueur de la Team
    # Rocket", "Carchacrok-ex") ; sinon seulement, traduction reconstruite.
    name = card.get("name_fr") or translate_card_name_to_fr(card.get("name"))
    set_name_fr = translate_set_name(card.get("set_name"), card.get("set_id"))
    series_fr = translate_series(card.get("series"))
    # Variante choisie à la main si elle existe : elle décrit la FINITION réelle
    # de l'exemplaire (holo, reverse holo), que le catalogue ignore — seul le
    # vendeur, carte en main, peut la constater. Sinon on retombe sur ce que la
    # rareté permet de déduire.
    variant = variant or rarity_display(card.get("rarity"))

    # Le set de base d'une série porte souvent le même nom que la série elle-
    # même (ex: set "Scarlet & Violet" dans la série "Scarlet & Violet") : sans
    # ça, la description dirait "provenant du bloc X, extension X". Le titre
    # garde `set_name` tel quel (pas de répétition du bloc dans le titre).
    extension_name = None if set_name_fr and set_name_fr == series_fr else set_name_fr

    context = {
        "name": name,
        "set_name": set_name_fr,
        "extension": extension_name,
        "series": series_fr,
        "number": card.get("number"),
        "printed_total": card.get("printed_total"),
        "variant": variant,
        # Titre : forme courte ("reverse" plutôt que "reverse holo").
        "variant_title": variant_title(variant),
        "language_tag": language_tag,
        "language_adjective": language_adjective,
        "condition_phrase": CONDITION_PHRASES.get(resolved_condition, resolved_condition.lower()),
        "hashtags": _build_hashtags(name, variant, language_tag, series_fr, set_name_fr),
    }

    title = _env.get_template("vinted_title.txt.j2").render(**context).strip()
    description = _env.get_template("vinted_description.txt.j2").render(**context).strip()

    return {"title": title, "description": description}
