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
    "Mega Evolution": "Méga-Évolution",
    "NP": "Promo",
    "Other": "Autres",
}

# Noms FR officiels des extensions, CLÉ = id de set pokemontcg.io (stable et
# non ambigu). Généré depuis TCGdex (catalogue FR de référence) complété par
# quelques entrées manuelles pour les sets absents de TCGdex — couverture
# COMPLÈTE des 170 sets du cache. C'est la source prioritaire ; SET_NAME_FR
# (par nom anglais) ne sert plus que de repli si un set_id est inconnu.
SET_ID_FR = {
    'base1': 'Base',
    'base2': 'Jungle',
    'base3': 'Fossile',
    'base4': 'Set de Base 2',
    'base5': 'Team Rocket',
    'base6': 'Collection Légendaire',
    'basep': 'Wizards Black Star Promos',
    'bp': 'Best of Game',
    'bw1': 'Noir & Blanc',
    'bw10': 'Explosion Plasma',
    'bw11': 'Trésors Légendaires',
    'bw2': 'Pouvoirs Émergents',
    'bw3': 'Nobles Victoires',
    'bw4': 'Destinées Futures',
    'bw5': 'Explorateurs Obscurs',
    'bw6': 'Dragons Éxaltés',
    'bw7': 'Frontières Franchies',
    'bw8': 'Tempète Plasma',
    'bw9': 'Glaciation Plasma',
    'bwp': 'Promo BW',
    'cel25': 'Célébrations',
    'cel25c': 'Célébrations Collection Classique',
    'col1': "L'appel des Légendes",
    'dc1': 'Double Danger',
    'det1': 'Détective Pikachu',
    'dp1': 'Diamant & Perle',
    'dp2': 'Trésors Mystérieux',
    'dp3': 'Merveilles Secrètes',
    'dp4': 'Duels au Sommets',
    'dp5': 'Aube Majestueuse',
    'dp6': 'Éveil des Légendes',
    'dp7': 'Tempête',
    'dpp': 'Promo DP',
    'dv1': 'Coffre des Dragons',
    'ecard1': 'Expedition',
    'ecard2': 'Aquapolis',
    'ecard3': 'Portrait des Cieux',
    'ex1': 'EX Rubis & Saphir',
    'ex10': 'EX Forces Cachées',
    'ex11': 'EX Espèces Delta',
    'ex12': 'EX Créateurs de légendes',
    'ex13': 'EX Fantômes Holon',
    'ex14': 'EX Gardiens de Cristal',
    'ex15': 'EX Île des Dragons',
    'ex16': 'EX Gardiens du Pouvoir',
    'ex2': 'EX Tempête de sable',
    'ex3': 'EX Dragon',
    'ex4': 'EX Team Magma vs Team Aqua',
    'ex5': 'EX Légendes Oubliées',
    'ex6': 'EX Rouge Feu & Vert Feuille',
    'ex7': 'Team Rocket Revient',
    'ex8': 'EX Deoxys',
    'ex9': 'EX Émeraude',
    'fut20': 'Collection Futsal Pokémon',
    'g1': 'Générations',
    'gym1': 'Défis de Dresseurs',
    'gym2': 'Défis de Dresseurs 2',
    'hgss1': 'HeartGold & SoulSilver',
    'hgss2': 'Déchaînement',
    'hgss3': 'Indomptable',
    'hgss4': 'Triomphant',
    'hsp': 'Promo HGSS',
    'mcd11': "Collection McDonald's 2011",
    'mcd12': "Collection McDonald's 2012",
    'mcd16': "Collection McDonald's 2016",
    'mcd19': "Collection McDonald's 2019",
    'mcd21': "Collection McDonald's 2021",
    'mcd22': "Collection McDonald's 2022",
    'me1': 'Méga-Évolution',
    'me2': 'Flammes Fantasmagoriques',
    'me2pt5': 'Héros Transcendants',
    'me3': 'Équilibre Parfait',
    'me4': 'Chaos Ascendant',
    'me5': 'Nuit Noire',
    'neo1': 'Neo Genesis',
    'neo2': 'Neo Discovery',
    'neo3': 'Neo Revelation',
    'neo4': 'Neo Destiny',
    'np': 'Promo Nintendo',
    'pgo': 'Pokémon GO',
    'pl1': 'Platine',
    'pl2': 'Rivaux Émergeants',
    'pl3': 'Vainqueurs Suprêmes',
    'pl4': 'Arceus',
    'pop1': 'POP Série 1',
    'pop2': 'POP Série 2',
    'pop3': 'POP Série 3',
    'pop4': 'POP Série 4',
    'pop5': 'POP Série 5',
    'pop6': 'POP Série 6',
    'pop7': 'POP Série 7',
    'pop8': 'POP Série 8',
    'pop9': 'POP Série 9',
    'rsv10pt5': 'Flamme Blanche',
    'ru1': 'Pokémon Rumble',
    'si1': 'Îles du Sud',
    'sm1': 'Soleil et Lune',
    'sm10': 'Alliance Infaillible',
    'sm11': 'Harmonie des Esprits',
    'sm115': 'Destinées Occultes',
    'sm12': 'Éclipse Cosmique',
    'sm2': 'Gardiens Ascendants',
    'sm3': 'Ombres Ardentes',
    'sm35': 'Légendes Brillantes',
    'sm4': 'Invasion Carmin',
    'sm5': 'Ultra-Prisme',
    'sm6': 'Lumière Interdite',
    'sm7': 'Tempête Céleste',
    'sm75': 'Majesté Des Dragons',
    'sm8': 'Tonnerre Perdu',
    'sm9': 'Duo de Choc',
    'sma': 'Destinées Occultes Coffre Étincelant',
    'smp': 'Promo SM',
    'sv1': 'Écarlate et Violet',
    'sv10': 'Rivalités Destinées',
    'sv2': 'Évolutions à Paldea',
    'sv3': 'Flammes Obsidiennes',
    'sv3pt5': '151',
    'sv4': 'Faille Paradoxe',
    'sv4pt5': 'Destinées de Paldea',
    'sv5': 'Forces Temporelles',
    'sv6': 'Mascarade Crépusculaire',
    'sv6pt5': 'Fable Nébuleuse',
    'sv7': 'Couronne Stellaire',
    'sv8': 'Étincelles Déferlantes',
    'sv8pt5': 'Évolutions Prismatiques',
    'sv9': 'Aventures Ensemble',
    'sve': 'Énergies Écarlate et Violet',
    'svp': 'Promo Écarlate et Violet',
    'swsh1': 'Épée et Bouclier',
    'swsh10': 'Astres Radieux',
    'swsh10tg': 'Astres Radieux Galerie de Dresseurs',
    'swsh11': 'Origine Perdue',
    'swsh11tg': 'Origine Perdue Galerie de Dresseurs',
    'swsh12': 'Tempête Argentée',
    'swsh12pt5': 'Zénith Suprême',
    'swsh12pt5gg': 'Zénith Suprême Galerie Galaroise',
    'swsh12tg': 'Tempête Argentée Galerie de Dresseurs',
    'swsh2': 'Clash des Rebelles',
    'swsh3': 'Ténèbres Embrasées',
    'swsh35': 'La Voie du Maître',
    'swsh4': 'Voltage Éclatant',
    'swsh45': 'Destinées Radieuses',
    'swsh45sv': 'Destinées Radieuses Coffre Étincelant',
    'swsh5': 'Styles de combat',
    'swsh6': 'Règne de Glace',
    'swsh7': 'Évolution Céleste',
    'swsh8': 'Poing de Fusion',
    'swsh9': 'Stars Étincelantes',
    'swsh9tg': 'Stars Étincelantes Galerie de Dresseurs',
    'swshp': 'Promo SWSH',
    'tk1a': 'EX Kit dresseur (Latias)',
    'tk1b': 'EX Kit dresseur (Latios)',
    'tk2a': 'EX Kit dresseur (Positi)',
    'tk2b': 'EX Kit dresseur (Négapi)',
    'xy0': 'Bienvenue à Kalos',
    'xy1': 'XY',
    'xy10': 'Impact des Destins',
    'xy11': 'Offensive Vapeur',
    'xy12': 'Évolutions',
    'xy2': 'Étincelles',
    'xy3': 'Poings Furieux',
    'xy4': 'Vigueur Spectrale',
    'xy5': 'Primo-Choc',
    'xy6': 'Ciel Rugissant',
    'xy7': 'Origines Antiques',
    'xy8': 'Impulsion Turbo',
    'xy9': 'Rupture Turbo',
    'xyp': 'Promo XY',
    'zsv10pt5': 'Foudre Noire',
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
    "Rare Ultra": "full art",
    "Rare Secret": "secrète",
    "Rare Rainbow": "arc-en-ciel",
    "Rare Shiny": "shiny",
    "Rare Shiny GX": "shiny GX",
    "Amazing Rare": "AR",
    "Promo": "promo",
    "Radiant Rare": "radieuse",
    "Double Rare": "double rare",
    "Illustration Rare": "AR full art",
    "Special Illustration Rare": "SAR full art",
    "Hyper Rare": "gold UR",
    "ACE SPEC Rare": "ACE SPEC",
    "Rare BREAK": "BREAK",
    "LEGEND": "LEGEND",
    # Raretés spéciales ajoutées après audit du cache : elles ne produisaient
    # AUCUNE mention alors qu'elles désignent des cartes à part entière (numéro
    # et rareté propres), que le vendeur n'a donc pas à renseigner à la main.
    "Ultra Rare": "full art",  # les cartes ex full art des sets Écarlate et Violet
    "Shiny Rare": "shiny",
    "Shiny Ultra Rare": "shiny ultra rare",
    "Trainer Gallery Rare Holo": "Trainer Gallery",
    "Rare Holo LV.X": "LV.X",
    "Rare Prism Star": "Prism Star",
    "Rare Prime": "Prime",
    "Rare Holo Star": "Star",
    "Rare Shining": "shining",
    "Rare ACE": "ACE",
    "Mega Hyper Rare": "gold UR",
    "Classic Collection": "collection classique",
    # Numérotées au-delà du total du set (265/217, 172/86) : des secrètes.
    "MEGA_ATTACK_RARE": "secrète",
    "Black White Rare": "secrète",
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


def translate_set_name(set_name: str | None, set_id: str | None = None) -> str | None:
    # Priorité à l'id de set (couverture complète, non ambigu) ; repli sur le
    # nom anglais, puis sur le nom tel quel si vraiment inconnu.
    if set_id and set_id in SET_ID_FR:
        return SET_ID_FR[set_id]
    if not set_name:
        return set_name
    return SET_NAME_FR.get(set_name, set_name)


# Forme courte pour le TITRE, comme pour la langue ("ITA" en titre, "italienne"
# en description) : le titre Vinted est court et lu en diagonale, "reverse" y
# suffit — la description garde la formulation complète.
VARIANT_TITLE_SHORT = {"reverse holo": "reverse"}


def variant_title(variant: str | None) -> str | None:
    if not variant:
        return variant
    return VARIANT_TITLE_SHORT.get(variant, variant)


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
