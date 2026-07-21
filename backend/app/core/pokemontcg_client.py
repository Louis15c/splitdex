"""Client minimal pour l'API publique pokemontcg.io (v2).

Fonctionne sans clé API (rate-limit strict côté serveur pokemontcg.io) ou
avec une clé gratuite (https://pokemontcg.io) définie dans `.env` via
POKEMONTCG_API_KEY, ce qui relève fortement la limite de requêtes.
"""

import time

import httpx

from app.core.config import POKEMONTCG_API_BASE_URL, POKEMONTCG_API_KEY

PAGE_SIZE = 250
MAX_RETRIES = 8


def _headers() -> dict:
    if POKEMONTCG_API_KEY:
        return {"X-Api-Key": POKEMONTCG_API_KEY}
    return {}


def iter_all_cards(page_size: int = PAGE_SIZE):
    """Itère sur toutes les cartes du catalogue pokemontcg.io, page par page.

    Gère le rate-limiting (HTTP 429) avec un backoff exponentiel plutôt que
    d'abandonner : sans clé API, pokemontcg.io peut renvoyer des 429 assez
    tôt lors d'une synchronisation complète.
    """
    with httpx.Client(base_url=POKEMONTCG_API_BASE_URL, headers=_headers(), timeout=60.0) as client:
        page = 1
        while True:
            data = _get_page_with_retry(client, page, page_size)
            cards = data.get("data", [])
            if not cards:
                return
            yield from cards

            total_count = data.get("totalCount", 0)
            fetched_so_far = page * page_size
            if fetched_so_far >= total_count:
                return
            page += 1


def _get_page_with_retry(client: httpx.Client, page: int, page_size: int) -> dict:
    """pokemontcg.io renvoie occasionnellement des erreurs transitoires
    (429, mais aussi parfois un 404/5xx sur une page pourtant valide — observé
    en pratique). On retente sur n'importe quelle erreur HTTP, pas seulement
    le rate-limit, avant d'abandonner.
    """
    last_error: Exception | None = None
    response: httpx.Response | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.get("/cards", params={"page": page, "pageSize": page_size})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            response = None
            time.sleep(min(2**attempt * 3, 60))
            continue

        if response.status_code == 429:
            time.sleep(min(2**attempt * 5, 120))
            continue
        if response.status_code >= 400:
            time.sleep(min(2**attempt * 3, 30))
            continue

        return response.json()

    if response is not None:
        response.raise_for_status()
    raise last_error
