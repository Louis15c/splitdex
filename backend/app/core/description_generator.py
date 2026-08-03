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
from app.core.japanese_matcher import find_japanese_equivalent, japanese_set_label
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
        # Les acronymes gardent leurs capitales et font tag à part, le reste est
        # collé en un seul mot : "AR full art" -> #AR #fullart, comme dans les
        # annonces réelles (découper mot à mot donnait "#full #art", des tags
        # que personne ne cherche).
        words = variant.split()
        tags.extend(word for word in words if word.isupper())
        remaining = [word for word in words if not word.isupper()]
        if remaining:
            tags.append(hashtag("".join(remaining)))
    # Ordre repris des annonces réelles : provenance (bloc puis extension) avant
    # la langue, elle-même juste avant les tags de boutique.
    if series:
        # Un code de set japonais garde ses capitales ("#SV3A"), un nom de bloc
        # se normalise comme le reste ("#écarlateetviolet").
        tags.append(series if series.isupper() and " " not in series else hashtag(series))
    if set_name:
        tags.append(hashtag(set_name))
    if language_tag:
        # Minuscules dans les hashtags ("#jap"), alors que le TITRE garde la
        # forme courte en capitales ("JAP") — conforme aux annonces réelles.
        tags.append(language_tag.lower())
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

    number = card.get("number")
    printed_total = card.get("printed_total")

    # Carte japonaise : c'est la référence IMPRIMÉE SUR ELLE qu'attend
    # l'acheteur ("65/62 raging surf"), pas celle de l'édition internationale
    # ("193/182 Faille Paradoxe") que connaît notre catalogue.
    if language == "Japonaise" and card.get("id"):
        japanese = find_japanese_equivalent(card["id"], card.get("name"))
        if japanese:
            number = japanese["number"]
            printed_total = japanese["printed_total"]
            set_name_fr = japanese_set_label(japanese["set_id"])
            series_fr = japanese["set_id"].upper()

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
        "number": number,
        "printed_total": printed_total,
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
