"""Traductions et conventions françaises pour l'affichage des cartes.

pokemontcg.io ne fournit que des noms de séries/sets en anglais. Ces tables
les traduisent vers les noms officiels français (ou l'usage courant chez les
collectionneurs francophones, ex: "Wizards" pour désigner l'ère Base/Jungle/
Gym/Neo publiée par Wizards of the Coast avant que Nintendo ne reprenne
l'édition) — reconstruit à partir d'exemples réels d'annonces Vinted.

Couverture volontairement partielle (les séries/sets les plus courants,
surtout récents) : ce qui n'est pas dans la table est affiché tel quel en
anglais plutôt que de deviner une traduction. Facile à compléter au besoin.
"""

# Ère WOTC (avant que Nintendo/The Pokémon Company ne reprenne l'édition) :
# les collectionneurs francophones disent couramment "bloc Wizards" plutôt que
# le découpage plus fin de pokemontcg.io (Base / Gym / Neo / E-Card).
SERIES_NAME_FR = {
    "Base": "Wizards",
    "Gym": "Wizards",
    "Neo": "Wizards",
    "E-Card": "Wizards",
    "EX": "EX",
    "Diamond & Pearl": "Diamant & Perle",
    "Platinum": "Platine",
    "HeartGold & SoulSilver": "HeartGold & SoulSilver",
    "Black & White": "Noir & Blanc",
    "XY": "XY",
    "Sun & Moon": "Soleil et Lune",
    "Sword & Shield": "Épée et Bouclier",
    "Scarlet & Violet": "Écarlate et Violet",
    "POP": "POP",
}

SET_NAME_FR = {
    # Wizards (Base/Jungle/Gym/Neo/E-Card)
    "Base": "Base",
    "Jungle": "Jungle",
    "Fossil": "Fossile",
    "Base Set 2": "Set de Base 2",
    "Team Rocket": "Team Rocket",
    "Gym Heroes": "Défis de Dresseurs",
    "Gym Challenge": "Défis de Dresseurs 2",
    "Neo Genesis": "Néo Genèse",
    "Neo Discovery": "Néo Découverte",
    "Neo Destiny": "Néo Destinée",
    "Neo Revelation": "Néo Révélation",
    "Legendary Collection": "Collection Légendaire",
    "Expedition Base Set": "Expédition",
    "Aquapolis": "Aquapolis",
    "Skyridge": "Portrait des Cieux",
    # EX
    "Ruby & Sapphire": "Rubis & Saphir",
    "Team Magma vs Team Aqua": "Team Magma contre Team Aqua",
    "Dragon": "Dragon",
    "FireRed & LeafGreen": "Rouge Feu & Vert Feuille",
    "Team Rocket Returns": "Team Rocket Revient",
    "Deoxys": "Deoxys",
    "Emerald": "Émeraude",
    "Unseen Forces": "Forces Inconnues",
    "Delta Species": "Espèce Delta",
    "Legend Maker": "Créateur de Légende",
    "Holon Phantoms": "Fantômes de Holon",
    "Crystal Guardians": "Gardiens de Cristal",
    "Dragon Frontiers": "Frontières Draconiques",
    "Power Keepers": "Gardiens du Pouvoir",
    # Diamond & Pearl / Platinum
    "Diamond & Pearl": "Diamant & Perle",
    "Mysterious Treasures": "Trésors Mystérieux",
    "Secret Wonders": "Merveilles Secrètes",
    "Great Encounters": "Grandes Rencontres",
    "Majestic Dawn": "Aube Majestueuse",
    "Legends Awakened": "Légendes Retrouvées",
    "Stormfront": "Front de Tempête",
    "Platinum": "Platine",
    "Rising Rivals": "Rivaux Émergents",
    "Supreme Victors": "Vainqueurs Suprêmes",
    "Arceus": "Arceus",
    # HeartGold & SoulSilver
    "HeartGold & SoulSilver": "HeartGold & SoulSilver",
    "Unleashed": "Déchaînement",
    "Undaunted": "Impact des Destins",
    "Triumphant": "Triomphe",
    "Call of Legends": "Appel des Légendes",
    # Black & White
    "Black & White": "Noir & Blanc",
    "Emerging Powers": "Pouvoirs Émergents",
    "Noble Victories": "Victoires Nobles",
    "Next Destinies": "Destinées Futures",
    "Dark Explorers": "Explorateurs Obscurs",
    "Dragons Exalted": "Dragons Exaltés",
    "Boundaries Crossed": "Frontières Franchies",
    "Plasma Storm": "Tempête Plasma",
    "Plasma Freeze": "Gel Plasma",
    "Plasma Blast": "Explosion Plasma",
    "Legendary Treasures": "Trésors Légendaires",
    # XY
    "XY": "XY",
    "Flashfire": "Offensive Vapeur",
    "Furious Fists": "Poings Furieux",
    "Phantom Forces": "Forces Fantômes",
    "Primal Clash": "Primo Choc",
    "Roaring Skies": "Ciels Rugissants",
    "Ancient Origins": "Origines Antiques",
    "BREAKthrough": "Impact",
    "BREAKpoint": "Point de Rupture",
    "Fates Collide": "Destins Croisés",
    "Steam Siege": "Vapeur Assiegeante",
    "Evolutions": "Évolutions",
    "Generations": "Generations",
    # Sun & Moon
    "Sun & Moon": "Soleil et Lune",
    "Guardians Rising": "Gardiens Ascendants",
    "Burning Shadows": "Ombres Ardentes",
    "Crimson Invasion": "Invasion Écarlate",
    "Ultra Prism": "Ultra Prisme",
    "Forbidden Light": "Lumière Interdite",
    "Celestial Storm": "Tempête Céleste",
    "Lost Thunder": "Tonnerre Perdu",
    "Team Up": "Alliance Offensive",
    "Unbroken Bonds": "Liens Indestructibles",
    "Unified Minds": "Esprits Unis",
    "Cosmic Eclipse": "Éclipse Cosmique",
    "Hidden Fates": "Destinées Cachées",
    # Sword & Shield
    "Sword & Shield": "Épée et Bouclier",
    "Rebel Clash": "Clash des Rebelles",
    "Darkness Ablaze": "Ténèbres Embrasées",
    "Vivid Voltage": "Voltage Éclatant",
    "Battle Styles": "Styles de Combat",
    "Chilling Reign": "Règne de Glace",
    "Evolving Skies": "Ciel Immense",
    "Fusion Strike": "Fusion Attaque",
    "Brilliant Stars": "Stars Étincelantes",
    "Astral Radiance": "Astres Radieux",
    "Lost Origin": "Origine Perdue",
    "Silver Tempest": "Tempête Argentée",
    "Crown Zenith": "Zénith Suprême",
    # Scarlet & Violet
    "Scarlet & Violet": "Écarlate et Violet",
    "Paldea Evolved": "Évolutions à Paldea",
    "Obsidian Flames": "Flammes Obsidiennes",
    "Paradox Rift": "Faille Paradoxe",
    "Paldean Fates": "Destinées de Paldea",
    "Temporal Forces": "Forces Temporelles",
    "Twilight Masquerade": "Mascarade Crépusculaire",
    "Shrouded Fable": "Fable Éclipsée",
    "Stellar Crown": "Couronne Stellaire",
    "Surging Sparks": "Étincelles Déferlantes",
    "Prismatic Evolutions": "Évolutions Prismatiques",
}

# Dérivé de la rareté pokemontcg.io (anglais) vers un libellé affichable dans
# le titre/la description, dans l'esprit des variantes observées dans de
# vraies annonces ("reverse", "holo", "shiny full art"...). Couverture
# volontairement partielle : le "full art", "reverse", "1ère édition"... sont
# des variantes visuelles que pokemontcg.io ne décrit pas assez finement pour
# être fiables automatiquement — à ajouter/ajuster à la main au besoin
# (Phase 5, édition libre du titre/de la description).
RARITY_DISPLAY_FR = {
    "Rare Holo": "holo",
    "Rare Holo EX": "holo EX",
    "Rare Holo GX": "holo GX",
    "Rare Holo V": "holo V",
    "Rare Holo VMAX": "holo VMAX",
    "Rare Holo VSTAR": "holo VSTAR",
    "Rare Ultra": "ultra rare",
    "Rare Secret": "secrète",
    "Rare Rainbow": "arc-en-ciel",
    "Rare Shiny": "shiny",
    "Rare Shiny GX": "shiny GX",
    "Amazing Rare": "AR",
    "Promo": "promo",
    "Radiant Rare": "radieuse",
    "Double Rare": "double rare",
    "Illustration Rare": "illustration rare",
    "Special Illustration Rare": "illustration spéciale",
    "Hyper Rare": "hyper rare",
    "ACE SPEC Rare": "ACE SPEC",
    "Rare BREAK": "BREAK",
    "LEGEND": "LEGEND",
}

# Langue détectée (`language_detector.py`) -> (tag court pour le titre, à la
# manière de "ITA"/"JAP" observés dans de vraies annonces ; adjectif féminin
# pour la description, ex: "carte italienne"). Le français n'apparaît jamais
# (langue par défaut implicite, voir description_generator.py).
LANGUAGE_TAGS = {
    "Anglaise": ("ANG", "anglaise"),
    "Japonaise": ("JAP", "japonaise"),
    "Allemande": ("ALL", "allemande"),
    "Espagnole": ("ESP", "espagnole"),
    "Italienne": ("ITA", "italienne"),
}


def translate_series(series: str | None) -> str | None:
    if not series:
        return series
    return SERIES_NAME_FR.get(series, series)


def translate_set_name(set_name: str | None) -> str | None:
    if not set_name:
        return set_name
    return SET_NAME_FR.get(set_name, set_name)


def rarity_display(rarity: str | None) -> str | None:
    if not rarity:
        return None
    return RARITY_DISPLAY_FR.get(rarity)


def hashtag(text: str) -> str:
    """Nettoie un texte pour en faire un hashtag, à la manière des exemples
    observés (accents conservés, ex: "#évolutions", "#écarlateetviolet") —
    seuls les espaces, apostrophes et tirets sont retirés."""
    return "".join(ch for ch in text if ch.isalnum()).lower()


def language_tags(language: str | None) -> tuple[str | None, str | None]:
    """Retourne (tag_titre, adjectif_description), ou (None, None) si
    français/indéterminé (pas de mention dans le texte)."""
    if not language or language == "Français":
        return None, None
    return LANGUAGE_TAGS.get(language, (None, None))
