"""Client minimal pour l'API publique TCGdex (https://tcgdex.dev), utilisée
uniquement pour récupérer une estimation de prix (Cardmarket, en EUR) —
pokemontcg.io ne fournit aucune donnée de prix.

Pas de clé requise, API ouverte.

Stratégie de recherche (du plus fiable au plus tolérant) :
1. **Accès direct par `card_id`** : les identifiants TCGdex du catalogue
   international coïncident très souvent avec ceux de pokemontcg.io
   (ex: `base1-1`, `swsh1-1`). Un seul appel suffit alors.
2. **Id de set remappé** : quand ils diffèrent (ex: `sv4` -> `sv04`,
   `mcd11` -> `2011bw`), on reconstruit l'id via `SET_TCGDEX_ID` + le numéro.
3. **Repli par (nom, numéro)** désambiguïsé par le set : indispensable pour le
   japonais (catalogue séparé, identifiants distincts) et les rares cas où
   l'id ne se résout pas. Sans désambiguïsation, une carte n°1 très commune
   remonte des dizaines de candidats (chaque set a un n°1) et était rejetée.
"""

import threading

import httpx

from app.core.tcgdex_set_ids import SET_TCGDEX_ID

BASE_URL = "https://api.tcgdex.net/v2"
TIMEOUT = 8.0

# Locales partageant le catalogue international (mêmes identifiants TCGdex) ;
# le japonais ("ja") est un catalogue distinct aux identifiants propres.
_INTERNATIONAL = {"en", "fr", "de", "es", "it"}

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    return _client


def _normalize_local_id(local_id: str) -> str:
    return local_id.lstrip("0") or "0"


def _has_cardmarket(card: dict | None) -> bool:
    return bool(card and (card.get("pricing") or {}).get("cardmarket"))


def _get_detail(card_path_id: str, locale: str) -> dict | None:
    """Détail complet d'une carte par son identifiant TCGdex, ou None si absente."""
    try:
        response = _get_client().get(f"/{locale}/cards/{card_path_id}")
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        pass
    return None


def find_card(
    name: str,
    number: str,
    locale: str = "en",
    card_id: str | None = None,
    set_id: str | None = None,
) -> dict | None:
    """Cherche la carte TCGdex correspondante dans le catalogue `locale` et
    retourne son détail complet (avec pricing) si trouvée avec confiance, sinon
    None. `card_id`/`set_id` (identifiants pokemontcg.io) servent à cibler et
    désambiguïser ; ignorés pour le japonais (catalogue distinct)."""
    target_number = _normalize_local_id(number)

    # 1 & 2 : résolution directe par identifiant (catalogue international).
    if card_id and locale in _INTERNATIONAL:
        detail = _get_detail(card_id, locale)
        if detail is not None:
            # Carte trouvée : verdict définitif (a un prix Cardmarket ou non).
            return detail if _has_cardmarket(detail) else None
        tcgdex_set = SET_TCGDEX_ID.get(set_id)
        if tcgdex_set:
            detail = _get_detail(f"{tcgdex_set}-{target_number}", locale)
            if detail is not None:
                return detail if _has_cardmarket(detail) else None

    # 3 : repli par recherche de nom, désambiguïsée par set.
    try:
        response = _get_client().get(f"/{locale}/cards", params={"name": name})
        if response.status_code != 200:
            return None
        candidates = [
            c for c in response.json()
            if _normalize_local_id(c.get("localId", "")) == target_number
        ]
    except httpx.HTTPError:
        return None

    if not candidates:
        return None

    chosen = None
    if card_id:
        chosen = next((c for c in candidates if c.get("id") == card_id), None)
    if chosen is None and set_id:
        tcgdex_set = SET_TCGDEX_ID.get(set_id, set_id)
        chosen = next(
            (c for c in candidates if c.get("id", "").rsplit("-", 1)[0] == tcgdex_set),
            None,
        )
    if chosen is None and len(candidates) == 1:
        chosen = candidates[0]
    if chosen is None:
        return None

    detail = _get_detail(chosen["id"], locale)
    return detail if _has_cardmarket(detail) else None
