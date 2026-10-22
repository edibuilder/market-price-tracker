"""eBay Browse API provider (OAuth client-credentials flow)."""
import base64
import time
from decimal import Decimal, InvalidOperation

import requests

from app.config import settings
from app.providers.base import Listing, ProviderError

HOSTS = {"production": "https://api.ebay.com", "sandbox": "https://api.sandbox.ebay.com"}
SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayProvider:
    name = "ebay"

    def __init__(self):
        self.host = HOSTS.get(settings.ebay_env, HOSTS["production"])
        self._token: str | None = None
        self._token_expires = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        if not settings.ebay_client_id or not settings.ebay_client_secret:
            raise ProviderError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not configured")
        creds = base64.b64encode(f"{settings.ebay_client_id}:{settings.ebay_client_secret}".encode()).decode()
        r = requests.post(
            f"{self.host}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": SCOPE},
            timeout=20,
        )
        if r.status_code != 200:
            raise ProviderError(f"eBay auth failed ({r.status_code}): {r.text[:200]}")
        data = r.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + int(data.get("expires_in", 7200))
        return self._token

    def search(self, query: str, limit: int) -> list[Listing]:
        r = requests.get(
            f"{self.host}/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {self._get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": settings.ebay_marketplace,
            },
            params={"q": query, "limit": min(limit, 200), "filter": "buyingOptions:{FIXED_PRICE}"},
            timeout=30,
        )
        if r.status_code != 200:
            raise ProviderError(f"eBay search failed ({r.status_code}): {r.text[:200]}")

        listings: list[Listing] = []
        for it in r.json().get("itemSummaries", []):
            try:
                price = Decimal(it["price"]["value"])
                currency = it["price"]["currency"]
            except (KeyError, InvalidOperation):
                continue
            cats = it.get("categories") or []
            listings.append(
                Listing(
                    external_id=it["itemId"],
                    title=it.get("title", "")[:500],
                    price=price,
                    currency=currency,
                    category=cats[0]["categoryName"] if cats else None,
                    condition=it.get("condition"),
                    image_url=(it.get("image") or {}).get("imageUrl"),
                    item_url=it.get("itemWebUrl"),
                )
            )
        return listings
