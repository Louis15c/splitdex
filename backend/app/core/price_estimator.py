"""Estimation de prix (Cardmarket, EUR) via TCGdex — pokemontcg.io ne fournit
aucune donnée de prix.

Le prix est demandé dans le **catalogue TCGdex de la langue détectée** : la
cote d'une même carte varie énormément selon la langue d'impression (constaté
en pratique : une Illustration Rare à ~70€ en international/français mais une
poignée d'euros en japonais), donc pas question de servir un prix
"international" par défaut pour une carte non anglaise. Chaque locale TCGdex
exige le nom dans sa langue (vérifié : "Wartortle" ne donne rien en locale
`fr`/`ja`, il faut "Carabaffe"/"カメール") — d'où les tables de traduction.
Les langues sans table (allemand, espagnol, italien) partagent de toute façon
le même produit Cardmarket que l'anglais chez TCGdex (vérifié : même
`idProduct` en `fr`/`en`), le prix `en` est donc correct pour elles.

**Choix de la variante de prix** : Cardmarket distingue le prix de la
version normale et de la version holo d'un même produit (champs `avg-holo`,
`trend-holo`...). Pour une carte de rareté spéciale (holo, EX, Illustration
Rare...), le prix "normal" peut refléter la version commune du même numéro
(bug de rattachement constaté chez TCGdex côté japonais) — on préfère donc
les champs holo quand la rareté n'est pas Common/Uncommon et qu'ils existent.

Repli : si le catalogue de la langue n'a pas la carte ou pas de prix, on
retombe sur le prix anglais **avec un avertissement explicite** (`note`),
jamais silencieusement.
"""

from dataclasses import dataclass

from app.core.pokemon_names_fr import POKEMON_NAME_FR
from app.core.pokemon_names_jp import POKEMON_NAME_JP
from app.core.tcgdex_client import find_card

# Locale TCGdex + table de traduction du nom (None = le nom anglais est déjà
# celui du catalogue). L'allemand/espagnol/italien pointent sur `en` : même
# produit Cardmarket, et pas de table de noms dans ces langues de toute façon.
LOCALE_BY_LANGUAGE = {
    None: ("en", None),
    "Anglaise": ("en", None),
    "Français": ("fr", POKEMON_NAME_FR),
    "Japonaise": ("ja", POKEMON_NAME_JP),
    "Allemande": ("en", None),
    "Espagnole": ("en", None),
    "Italienne": ("en", None),
}

COMMON_RARITIES = {"common", "uncommon"}


@dataclass
class PriceEstimate:
    suggested: float | None  # prix conseillé (pré-rempli) : trend > avg30 > avg7 > avg
    trend: float | None      # "prix du marché" Cardmarket (estimation actuelle)
    avg30: float | None      # moyenne des ventes sur 30 jours
    avg: float | None        # moyenne (long terme, peut être décalée)
    low: float | None        # plus bas en vente (souvent une carte abîmée, indicatif)
    currency: str
    source_language: str  # locale TCGdex dont provient le prix ("fr", "ja", "en"...)
    note: str | None = None  # avertissement à afficher si repli ou donnée incertaine


def _pick_prices(cardmarket: dict, rarity: str | None) -> dict:
    """Prix normal ou holo selon la rareté (voir docstring du module).

    On privilégie `trend` (estimation du prix marché actuel de Cardmarket) plutôt
    que `avg` (moyenne, tirée par d'anciennes ventes) : c'est la référence la plus
    juste pour fixer un prix. `avg30` sert de repli récent, `avg` de dernier repli.
    """
    is_special = rarity is not None and rarity.lower() not in COMMON_RARITIES
    suffix = "-holo" if (is_special and cardmarket.get("avg-holo") is not None) else ""

    def field(key):
        return cardmarket.get(key + suffix)

    prices = {
        "trend": field("trend"),
        "avg30": field("avg30"),
        "avg7": field("avg7"),
        "avg": field("avg"),
        "low": field("low"),
    }
    # Prix conseillé : premier champ non nul et > 0, du plus pertinent au moins.
    prices["suggested"] = next(
        (prices[k] for k in ("trend", "avg30", "avg7", "avg") if prices.get(k)), None
    )
    return prices


def _lookup(
    name: str,
    number: str,
    locale: str,
    name_table: dict | None,
    card_id: str | None = None,
    set_id: str | None = None,
) -> dict | None:
    """Cherche la carte dans le catalogue `locale` et retourne son bloc de
    prix Cardmarket, ou `None` (carte absente, nom intraduisible, pas de prix).
    """
    localized_name = name_table.get(name) if name_table is not None else name
    if not localized_name:
        return None
    card = find_card(localized_name, number, locale=locale, card_id=card_id, set_id=set_id)
    if not card:
        return None
    return card.get("pricing", {}).get("cardmarket")


# Cache des estimations : les cotes Cardmarket ne bougent pas à la minute, et
# chaque estimation coûte jusqu'à 4 requêtes TCGdex — inutile de les refaire
# quand l'utilisateur re-clique sur la même carte ou regénère une planche.
_estimate_cache: dict[tuple, tuple[float, "PriceEstimate | None"]] = {}
ESTIMATE_CACHE_TTL_SECONDS = 15 * 60
MAX_CACHED_ESTIMATES = 512


def estimate_price(
    name: str,
    number: str,
    language: str | None,
    rarity: str | None = None,
    card_id: str | None = None,
    set_id: str | None = None,
) -> PriceEstimate | None:
    """Retourne l'estimation de prix pour la carte dans sa langue, ou `None`
    si introuvable partout (couverture TCGdex partielle sur les sets
    anciens/obscurs). `card_id`/`set_id` (pokemontcg.io) ciblent la carte dans
    TCGdex sans ambiguïté (voir `tcgdex_client.find_card`)."""
    import time

    cache_key = (card_id, name, number, language, rarity)
    cached = _estimate_cache.get(cache_key)
    if cached is not None and time.monotonic() - cached[0] < ESTIMATE_CACHE_TTL_SECONDS:
        return cached[1]

    estimate = _estimate_price_uncached(name, number, language, rarity, card_id, set_id)

    if len(_estimate_cache) >= MAX_CACHED_ESTIMATES:
        _estimate_cache.clear()
    _estimate_cache[cache_key] = (time.monotonic(), estimate)
    return estimate


def _estimate_price_uncached(
    name: str,
    number: str,
    language: str | None,
    rarity: str | None,
    card_id: str | None = None,
    set_id: str | None = None,
) -> PriceEstimate | None:
    locale, name_table = LOCALE_BY_LANGUAGE.get(language, ("en", None))

    def build(picked: dict, unit: str, source: str, note: str | None = None) -> PriceEstimate:
        return PriceEstimate(
            suggested=picked["suggested"],
            trend=picked["trend"],
            avg30=picked["avg30"],
            avg=picked["avg"],
            low=picked["low"],
            currency=unit,
            source_language=source,
            note=note,
        )

    prices = _lookup(name, number, locale, name_table, card_id=card_id, set_id=set_id)
    if prices is not None:
        picked = _pick_prices(prices, rarity)
        if picked["suggested"] is not None:
            return build(picked, prices.get("unit", "EUR"), locale)

    if locale == "en":
        return None

    # Catalogue de la langue muet : prix anglais en repli, clairement signalé.
    fallback_prices = _lookup(name, number, "en", None, card_id=card_id, set_id=set_id)
    if fallback_prices is None:
        return None
    picked = _pick_prices(fallback_prices, rarity)
    if picked["suggested"] is None:
        return None
    return build(
        picked,
        fallback_prices.get("unit", "EUR"),
        "en",
        note=(
            "Cote introuvable dans la langue de la carte — prix de l'édition anglaise "
            "affiché à la place, la cote réelle peut fortement différer."
        ),
    )
