"""Correspondance noms français -> anglais des Pokémon, pour retrouver
l'espèce à partir du texte OCRisé d'une carte imprimée en français (le nom
est en gros caractères en haut de la carte, bien plus facile à lire pour
l'OCR que le petit numéro en bas — voir `number_detector.py`).

Couverture volontairement partielle, comme les autres tables de traduction
(`card_translations.py`) : génération 1 complète (151 espèces, y compris le
set "151" lui-même), vérifiée espèce par espèce. Au-delà, seule une sélection
restreinte d'espèces dont le nom français est certain (starters et
légendaires très connus). Mieux vaut une table courte et fiable qu'une
grande table avec des erreurs qui identifieraient mal des cartes — ce qui
manque retombe simplement sur le pipeline pHash existant, rien ne casse.
"""

# Génération 1 (Kanto), complète — clé = nom anglais (pokemontcg.io), valeur
# = nom français officiel.
GENERATION_1_FR = {
    "Bulbasaur": "Bulbizarre", "Ivysaur": "Herbizarre", "Venusaur": "Florizarre",
    "Charmander": "Salamèche", "Charmeleon": "Reptincel", "Charizard": "Dracaufeu",
    "Squirtle": "Carapuce", "Wartortle": "Carabaffe", "Blastoise": "Tortank",
    "Caterpie": "Chenipan", "Metapod": "Chrysacier", "Butterfree": "Papilusion",
    "Weedle": "Aspicot", "Kakuna": "Coconfort", "Beedrill": "Dardargnan",
    "Pidgey": "Roucool", "Pidgeotto": "Roucoups", "Pidgeot": "Roucarnage",
    "Rattata": "Rattata", "Raticate": "Rattatac",
    "Spearow": "Piafabec", "Fearow": "Rapasdepic",
    "Ekans": "Abo", "Arbok": "Arbok",
    "Pikachu": "Pikachu", "Raichu": "Raichu",
    "Sandshrew": "Sabelette", "Sandslash": "Sablaireau",
    "Nidoran-F": "Nidoran♀", "Nidorina": "Nidorina", "Nidoqueen": "Nidoqueen",
    "Nidoran-M": "Nidoran♂", "Nidorino": "Nidorino", "Nidoking": "Nidoking",
    "Clefairy": "Mélofée", "Clefable": "Mélodelfe",
    "Vulpix": "Goupix", "Ninetales": "Feunard",
    "Jigglypuff": "Rondoudou", "Wigglytuff": "Grodoudou",
    "Zubat": "Nosferapti", "Golbat": "Nosferalto",
    "Oddish": "Mystherbe", "Gloom": "Ortide", "Vileplume": "Rafflesia",
    "Paras": "Paras", "Parasect": "Parasect",
    "Venonat": "Mimitoss", "Venomoth": "Aéromite",
    "Diglett": "Taupiqueur", "Dugtrio": "Triopikeur",
    "Meowth": "Miaouss", "Persian": "Persian",
    "Psyduck": "Psykokwak", "Golduck": "Akwakwak",
    "Mankey": "Ferosinge", "Primeape": "Colossinge",
    "Growlithe": "Caninos", "Arcanine": "Arcanin",
    "Poliwag": "Ptitard", "Poliwhirl": "Têtarte", "Poliwrath": "Tartard",
    "Abra": "Abra", "Kadabra": "Kadabra", "Alakazam": "Alakazam",
    "Machop": "Machoc", "Machoke": "Machopeur", "Machamp": "Mackogneur",
    "Bellsprout": "Chétiflor", "Weepinbell": "Boustiflor", "Victreebel": "Empiflor",
    "Tentacool": "Tentacool", "Tentacruel": "Tentacruel",
    "Geodude": "Racaillou", "Graveler": "Gravalanch", "Golem": "Grolem",
    "Ponyta": "Ponyta", "Rapidash": "Galopa",
    "Slowpoke": "Ramoloss", "Slowbro": "Flagadoss",
    "Magnemite": "Magnéti", "Magneton": "Magnéton",
    "Farfetch'd": "Canarticho",
    "Doduo": "Doduo", "Dodrio": "Dodrio",
    "Seel": "Otaria", "Dewgong": "Lamantine",
    "Grimer": "Tadmorv", "Muk": "Grotadmorv",
    "Shellder": "Kokiyas", "Cloyster": "Crustabri",
    "Gastly": "Fantominus", "Haunter": "Spectrum", "Gengar": "Ectoplasma",
    "Onix": "Onix",
    "Drowzee": "Soporifik", "Hypno": "Hypnomade",
    "Krabby": "Krabby", "Kingler": "Krabboss",
    "Voltorb": "Voltorbe", "Electrode": "Électrode",
    "Exeggcute": "Noeunoeuf", "Exeggutor": "Noadkoko",
    "Cubone": "Osselait", "Marowak": "Ossatueur",
    "Hitmonlee": "Kicklee", "Hitmonchan": "Tygnon",
    "Lickitung": "Excelangue",
    "Koffing": "Smogo", "Weezing": "Smogogo",
    "Rhyhorn": "Rhinocorne", "Rhydon": "Rhinoféros",
    "Chansey": "Leveinard",
    "Tangela": "Saquedeneu",
    "Kangaskhan": "Kangourex",
    "Horsea": "Hypotrempe", "Seadra": "Hypocean",
    "Goldeen": "Poissirène", "Seaking": "Poissoroy",
    "Staryu": "Stari", "Starmie": "Staross",
    "Mr. Mime": "M. Mime",
    "Scyther": "Insécateur",
    "Jynx": "Lippoutou",
    "Electabuzz": "Élektek",
    "Magmar": "Magmar",
    "Pinsir": "Scarabrute",
    "Tauros": "Tauros",
    "Magikarp": "Magicarpe", "Gyarados": "Léviator",
    "Lapras": "Lokhlass",
    "Ditto": "Métamorph",
    "Eevee": "Évoli", "Vaporeon": "Aquali", "Jolteon": "Voltali", "Flareon": "Pyroli",
    "Porygon": "Porygon",
    "Omanyte": "Amonita", "Omastar": "Amonistar",
    "Kabuto": "Kabuto", "Kabutops": "Kabutops",
    "Aerodactyl": "Ptéra",
    "Snorlax": "Ronflex",
    "Articuno": "Artikodin", "Zapdos": "Électhor", "Moltres": "Sulfura",
    "Dratini": "Minidraco", "Dragonair": "Draco", "Dragonite": "Dracolosse",
    "Mewtwo": "Mewtwo", "Mew": "Mew",
}

# Au-delà de la génération 1 : uniquement des noms dont je suis certain
# (starters de chaque génération + légendaires très médiatisés). Le reste
# retombe sur le pipeline pHash existant plutôt que de risquer un nom faux.
OTHER_GENERATIONS_FR = {
    # Gen 2 — starters, légendaires, Johto
    "Chikorita": "Germignon", "Bayleef": "Macronium", "Meganium": "Méganium",
    "Cyndaquil": "Héricendre", "Quilava": "Feurisson", "Typhlosion": "Typhlosion",
    "Totodile": "Kaiminus", "Croconaw": "Crocrodil", "Feraligatr": "Aligatueur",
    "Furret": "Fouinar", "Chinchou": "Loupio",
    "Ampharos": "Pharamp",
    "Espeon": "Mentali", "Umbreon": "Noctali",
    "Wobbuffet": "Qulbutoké",
    "Scizor": "Cizayox", "Heracross": "Scarhino",
    "Houndoom": "Démolosse",
    "Kingdra": "Hyporoi",
    "Donphan": "Donphan",
    "Raikou": "Raikou", "Entei": "Entei", "Suicune": "Suicune",
    "Tyranitar": "Tyranocif",
    "Lugia": "Lugia", "Ho-Oh": "Ho-Oh", "Celebi": "Celebi",
    # Gen 3 — starters, légendaires
    "Torchic": "Poussifeu", "Combusken": "Galifeu", "Blaziken": "Braségali",
    "Mudkip": "Gobou", "Marshtomp": "Flobio", "Swampert": "Laggron",
    "Ralts": "Tarsal", "Kirlia": "Kirlia", "Gardevoir": "Gardevoir",
    "Sableye": "Ténéfix", "Absol": "Absol",
    "Bagon": "Draby", "Shelgon": "Drackhaus", "Salamence": "Drattak",
    "Beldum": "Balbeat", "Metang": "Métang", "Metagross": "Métalosse",
    "Regirock": "Regirock", "Regice": "Regice", "Registeel": "Registeel",
    "Latias": "Latias", "Latios": "Latios",
    "Kyogre": "Kyogre", "Groudon": "Groudon", "Rayquaza": "Rayquaza",
    "Jirachi": "Jirachi", "Deoxys": "Deoxys",
    "Gulpin": "Gloupti", "Milotic": "Milobellus",
    # Gen 4 — starters, légendaires
    "Turtwig": "Tortipouss", "Grotle": "Boskara", "Torterra": "Torterra",
    "Chimchar": "Ouisticram", "Monferno": "Chimpenfeu", "Infernape": "Simiabraz",
    "Piplup": "Tiplouf", "Prinplup": "Prinplouf", "Empoleon": "Pingoléon",
    "Riolu": "Riolu", "Lucario": "Lucario",
    "Garchomp": "Carchacrok", "Gible": "Griknot", "Gabite": "Carmache",
    "Weavile": "Dimoret",
    "Togekiss": "Togekiss",
    "Leafeon": "Phyllali", "Glaceon": "Givrali",
    "Gallade": "Gallame",
    "Dialga": "Dialga", "Palkia": "Palkia", "Giratina": "Giratina",
    "Darkrai": "Darkrai", "Shaymin": "Shaymin", "Arceus": "Arceus",
    "Victini": "Victini",
    # Gen 5 — starters, légendaires
    "Tepig": "Gruikui", "Pignite": "Grotichon", "Emboar": "Roitiflam",
    "Oshawott": "Moustillon", "Dewott": "Mateloutre", "Samurott": "Clamiral",
    "Zorua": "Zorua", "Zoroark": "Zoroark",
    "Emolga": "Emolga",
    "Reshiram": "Reshiram", "Zekrom": "Zekrom", "Kyurem": "Kyurem",
    # Gen 6 — starters
    "Froakie": "Grenousse", "Frogadier": "Croâporal", "Greninja": "Amphinobi",
    "Fennekin": "Feunnec", "Braixen": "Roussil", "Delphox": "Goupelin",
    "Chespin": "Marisson", "Quilladin": "Boguérisse", "Chesnaught": "Blindépique",
    "Sylveon": "Nymphali",
    # Gen 7 — starters
    "Rowlet": "Brindibou", "Dartrix": "Efflèche", "Decidueye": "Archéduc",
    "Litten": "Flamiaou", "Torracat": "Matoufeu", "Incineroar": "Félinferno",
    "Popplio": "Otaquin", "Brionne": "Otarlette", "Primarina": "Oratoria",
    # Gen 8 — starters
    "Grookey": "Ouistempo", "Thwackey": "Badabouin", "Rillaboom": "Gorythmic",
    "Scorbunny": "Flambino", "Raboot": "Lapyro", "Cinderace": "Pyrobut",
    "Sobble": "Larméléon", "Drizzile": "Arrozard", "Inteleon": "Lézargus",
    # Gen 9 — starters
    "Sprigatito": "Poussacha", "Floragato": "Matourgeon", "Meowscarada": "Miascarade",
    "Fuecoco": "Chochodile", "Crocalor": "Crocorible", "Skeledirge": "Skelenox",
    "Quaxly": "Coiffeton", "Quaxwell": "Palarbeau", "Quaquaval": "Flamenroule",
}

# Fusion : la table générée PokeAPI (1025 espèces, toutes générations) sert
# de base, les tables manuelles vérifiées espèce par espèce prévalent en cas
# de doublon.
from app.core.pokemon_species_names import SPECIES_FR_BY_EN

POKEMON_NAME_FR = {**SPECIES_FR_BY_EN, **OTHER_GENERATIONS_FR, **GENERATION_1_FR}


def normalize_name(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).upper()


# Dresseurs/équipes dont la carte porte le nom ("Team Rocket's Diglett"), avec
# leur nom OFFICIEL français. L'article est inclus quand il en faut un, pour
# composer "de la Team Rocket" et non "de Team Rocket". Couverture volontairement
# limitée aux noms sûrs : un propriétaire inconnu garde son nom anglais, la
# STRUCTURE française étant de toute façon rétablie.
TRAINER_NAME_FR = {
    "Team Rocket": "la Team Rocket",
    "Rocket": "la Team Rocket",
    "The Rocket": "la Team Rocket",
    "Team Aqua": "la Team Aqua",
    "Team Magma": "la Team Magma",
    "Team Galactic": "la Team Galaxie",
    "Misty": "Ondine",
    "Brock": "Pierre",
    "Sabrina": "Morgane",
    "Blaine": "Auguste",
    "Lt. Surge": "Major Bob",
    "Koga": "Koga",
    "Erika": "Erika",
    "Giovanni": "Giovanni",
    "Janine": "Jeannine",
    "Karen": "Katherina",
    "Morty": "Mortimer",
    "Lance": "Peter",
    "Bill": "Léo",
    "Cynthia": "Cynthia",
    "Volkner": "Tanguy",
    "Cheren": "Tcheren",
    "Elesa": "Inezia",
    "Colress": "Achroma",
    "Cyrus": "Hélio",
    "Maxie": "Max",
    "Archie": "Arthur",
    "Clemont": "Lem",
    "Korrina": "Cornélia",
    "Lillie": "Lilie",
    "Gladion": "Gladio",
    "Hop": "Nabil",
    "Marnie": "Rosemary",
    "Iono": "Mashynn",
    "Arven": "Pepper",
    "Nemona": "Menzi",
    "Ash": "Sacha",
    "Professor Oak": "Professeur Chen",
    "Professor Elm": "Professeur Orme",
    "Professor Birch": "Professeur Seko",
}


def _contains_species(text: str) -> bool:
    """Vrai si le texte contient un nom d'espèce (bornes de mots). Sert à
    distinguer une carte Pokémon possédée ("Team Rocket's Diglett") d'une carte
    Dresseur ("Boss's Orders") : on ne peut pas se fier au fait que la
    traduction change le texte, beaucoup d'espèces portant le même nom dans les
    deux langues (Mewtwo, Zorua, Sharpedo...)."""
    import re

    return any(
        re.search(r"(?<![A-Za-z])" + re.escape(english) + r"(?![a-z])", text)
        for english in POKEMON_NAME_FR
    )


def _possessive_suffix(owner_en: str) -> str:
    """Compose le complément français : "de la Team Rocket", "d'Erika", "de
    Cynthia". L'élision suit la prononciation (voyelle ou h muet)."""
    owner = TRAINER_NAME_FR.get(owner_en, owner_en)
    if owner.split(" ", 1)[0].lower() in ("la", "le", "les", "l'"):
        return f"de {owner}"
    return f"d'{owner}" if owner[:1].lower() in "aeiouyhàâéèêîïôöûü" else f"de {owner}"


def translate_card_name_to_fr(name_en: str | None) -> str | None:
    """Traduit vers le français le nom d'une carte tel que stocké dans
    `reference_cards.name` — qui peut porter un suffixe/préfixe de variante
    autour du nom d'espèce ("Venusaur-EX", "Victini V", "Mega Charizard X
    ex"...). On remplace l'espèce (la plus longue qui matche, en bornes de
    mots) et on garde le reste tel quel. Ce qui n'est pas dans la table
    (cartes Dresseur, espèces non couvertes) reste en anglais — cohérent avec
    la philosophie des autres tables de traduction.
    """
    import re

    if not name_en:
        return name_en

    if name_en in POKEMON_NAME_FR:
        return POKEMON_NAME_FR[name_en]

    # Possessif : l'anglais antépose le propriétaire ("Team Rocket's Diglett"),
    # le français le postpose ("Taupiqueur de la Team Rocket"). Traduire mot à
    # mot donnait "Team Rocket's Taupiqueur", qui n'est le nom officiel de rien.
    # On ne transforme QUE si la partie possédée est bien une espèce : les
    # cartes Dresseur ("Professor's Research", "Boss's Orders") suivent d'autres
    # règles et restent intactes.
    possessive = re.match(r"^(.+?)'s\s+(.+)$", name_en)
    if possessive:
        owner_en, owned_en = possessive.group(1), possessive.group(2)
        if _contains_species(owned_en):
            owned_fr = translate_card_name_to_fr(owned_en)
            return f"{owned_fr} {_possessive_suffix(owner_en)}"

    for english, french in sorted(POKEMON_NAME_FR.items(), key=lambda item: -len(item[0])):
        # Bornes de mots : "Mew" ne doit pas matcher dans "Mewtwo" (le tri
        # par longueur fait passer "Mewtwo" d'abord, et la borne bloque le
        # reste), ni un nom au milieu d'un autre mot.
        pattern = r"(?<![A-Za-z])" + re.escape(english) + r"(?![a-z])"
        if re.search(pattern, name_en):
            translated = re.sub(pattern, french, name_en, count=1)
            # Convention française officielle pour les méga-évolutions.
            return translated.replace("Mega ", "Méga-")

    return name_en


# Table inversée FR -> EN, noms normalisés (majuscules, sans accents) pour un
# matching robuste à un OCR imparfait qui perd souvent les accents.
POKEMON_NAME_EN_BY_NORMALIZED_FR = {
    normalize_name(name_fr): name_en for name_en, name_fr in POKEMON_NAME_FR.items()
}
