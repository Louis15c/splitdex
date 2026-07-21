"""Correspondance noms japonais -> anglais des Pokémon, pour retrouver
l'espèce à partir du texte OCRisé d'une carte imprimée en japonais (le nom
est en gros caractères en haut de la carte, bien plus facile à lire pour
l'OCR que le petit numéro en bas — voir `number_detector.py`).

Couverture volontairement partielle, comme `pokemon_names_fr.py` : génération
1 (151 espèces, y compris le set japonais "151"/SV2a) uniquement pour
l'instant, noms canoniques bien documentés. Au-delà, ce qui manque retombe
simplement sur le pipeline pHash existant, rien ne casse.
"""

# Génération 1 (Kanto) — clé = nom anglais (pokemontcg.io), valeur = nom
# japonais officiel (katakana).
GENERATION_1_JP = {
    "Bulbasaur": "フシギダネ", "Ivysaur": "フシギソウ", "Venusaur": "フシギバナ",
    "Charmander": "ヒトカゲ", "Charmeleon": "リザード", "Charizard": "リザードン",
    "Squirtle": "ゼニガメ", "Wartortle": "カメール", "Blastoise": "カメックス",
    "Caterpie": "キャタピー", "Metapod": "トランセル", "Butterfree": "バタフリー",
    "Weedle": "ビードル", "Kakuna": "コクーン", "Beedrill": "スピアー",
    "Pidgey": "ポッポ", "Pidgeotto": "ピジョン", "Pidgeot": "ピジョット",
    "Rattata": "コラッタ", "Raticate": "ラッタ",
    "Spearow": "オニスズメ", "Fearow": "オニドリル",
    "Ekans": "アーボ", "Arbok": "アーボック",
    "Pikachu": "ピカチュウ", "Raichu": "ライチュウ",
    "Sandshrew": "サンド", "Sandslash": "サンドパン",
    "Nidoran-F": "ニドラン♀", "Nidorina": "ニドリーナ", "Nidoqueen": "ニドクイン",
    "Nidoran-M": "ニドラン♂", "Nidorino": "ニドリーノ", "Nidoking": "ニドキング",
    "Clefairy": "ピッピ", "Clefable": "ピクシー",
    "Vulpix": "ロコン", "Ninetales": "キュウコン",
    "Jigglypuff": "プリン", "Wigglytuff": "プクリン",
    "Zubat": "ズバット", "Golbat": "ゴルバット",
    "Oddish": "ナゾノクサ", "Gloom": "クサイハナ", "Vileplume": "ラフレシア",
    "Paras": "パラス", "Parasect": "パラセクト",
    "Venonat": "コンパン", "Venomoth": "モルフォン",
    "Diglett": "ディグダ", "Dugtrio": "ダグトリオ",
    "Meowth": "ニャース", "Persian": "ペルシアン",
    "Psyduck": "コダック", "Golduck": "ゴルダック",
    "Mankey": "マンキー", "Primeape": "オコリザル",
    "Growlithe": "ガーディ", "Arcanine": "ウインディ",
    "Poliwag": "ニョロモ", "Poliwhirl": "ニョロゾ", "Poliwrath": "ニョロボン",
    "Abra": "ケーシィ", "Kadabra": "ユンゲラー", "Alakazam": "フーディン",
    "Machop": "ワンリキー", "Machoke": "ゴーリキー", "Machamp": "カイリキー",
    "Bellsprout": "マダツボミ", "Weepinbell": "ウツドン", "Victreebel": "ウツボット",
    "Tentacool": "メノクラゲ", "Tentacruel": "ドククラゲ",
    "Geodude": "イシツブテ", "Graveler": "ゴローン", "Golem": "ゴローニャ",
    "Ponyta": "ポニータ", "Rapidash": "ギャロップ",
    "Slowpoke": "ヤドン", "Slowbro": "ヤドラン",
    "Magnemite": "コイル", "Magneton": "レアコイル",
    "Farfetch'd": "カモネギ",
    "Doduo": "ドードー", "Dodrio": "ドードリオ",
    "Seel": "パウワウ", "Dewgong": "ジュゴン",
    "Grimer": "ベトベター", "Muk": "ベトベトン",
    "Shellder": "シェルダー", "Cloyster": "パルシェン",
    "Gastly": "ゴース", "Haunter": "ゴースト", "Gengar": "ゲンガー",
    "Onix": "イワーク",
    "Drowzee": "スリープ", "Hypno": "スリーパー",
    "Krabby": "クラブ", "Kingler": "キングラー",
    "Voltorb": "ビリリダマ", "Electrode": "マルマイン",
    "Exeggcute": "タマタマ", "Exeggutor": "ナッシー",
    "Cubone": "カラカラ", "Marowak": "ガラガラ",
    "Hitmonlee": "サワムラー", "Hitmonchan": "エビワラー",
    "Lickitung": "ベロリンガ",
    "Koffing": "ドガース", "Weezing": "マタドガス",
    "Rhyhorn": "サイホーン", "Rhydon": "サイドン",
    "Chansey": "ラッキー",
    "Tangela": "モンジャラ",
    "Kangaskhan": "ガルーラ",
    "Horsea": "タッツー", "Seadra": "シードラ",
    "Goldeen": "トサキント", "Seaking": "アズマオウ",
    "Staryu": "ヒトデマン", "Starmie": "スターミー",
    "Mr. Mime": "バリヤード",
    "Scyther": "ストライク",
    "Jynx": "ルージュラ",
    "Electabuzz": "エレブー",
    "Magmar": "ブーバー",
    "Pinsir": "カイロス",
    "Tauros": "ケンタロス",
    "Magikarp": "コイキング", "Gyarados": "ギャラドス",
    "Lapras": "ラプラス",
    "Ditto": "メタモン",
    "Eevee": "イーブイ", "Vaporeon": "シャワーズ", "Jolteon": "サンダース", "Flareon": "ブースター",
    "Porygon": "ポリゴン",
    "Omanyte": "オムナイト", "Omastar": "オムスター",
    "Kabuto": "カブト", "Kabutops": "カブトプス",
    "Aerodactyl": "プテラ",
    "Snorlax": "カビゴン",
    "Articuno": "フリーザー", "Zapdos": "サンダー", "Moltres": "ファイヤー",
    "Dratini": "ミニリュウ", "Dragonair": "ハクリュー", "Dragonite": "カイリュー",
    "Mewtwo": "ミュウツー", "Mew": "ミュウ",
}

# Fusion : la table générée PokeAPI (1025 espèces, toutes générations) sert
# de base, la table manuelle génération 1 (vérifiée) prévaut en cas de doublon.
from app.core.pokemon_species_names import SPECIES_EN_BY_JP

POKEMON_NAME_JP = {
    **{name_en: name_jp for name_jp, name_en in SPECIES_EN_BY_JP.items()},
    **GENERATION_1_JP,
}

# Table inversée JP -> EN, texte exact (aucune normalisation) : à utiliser en
# priorité, zéro risque d'ambiguïté.
POKEMON_NAME_EN_BY_JP = {name_jp: name_en for name_en, name_jp in POKEMON_NAME_JP.items()}

# Repli tolérant à une erreur d'OCR sur le dakuten/handakuten (une carte
# japonaise réelle a donné "ガメール" au lieu de "カメール"/Wartortle) : on
# réutilise `normalize_name` (NFKD + suppression des caractères combinants)
# pour ce cas précis, car la décomposition NFKD du katakana traite le
# dakuten/handakuten comme un caractère combinant — un heureux hasard qui
# nivelle exactement ce type de faute. Mais ce nivellement rend aussi deux
# espèces distinctes indiscernables quand elles ne diffèrent que par ce trait
# (ex: "カラカラ"/Cubone vs "ガラガラ"/Marowak) : ces clés ambiguës sont
# exclues plutôt que de risquer un mauvais match, et cette table n'est donc
# utilisée qu'en repli, après la table exacte ci-dessus.
from app.core.pokemon_names_fr import normalize_name  # noqa: E402

_normalized_groups: dict[str, set[str]] = {}
for _name_en, _name_jp in POKEMON_NAME_JP.items():
    _normalized_groups.setdefault(normalize_name(_name_jp), set()).add(_name_en)

POKEMON_NAME_EN_BY_NORMALIZED_JP = {
    _key: next(iter(_names)) for _key, _names in _normalized_groups.items() if len(_names) == 1
}
