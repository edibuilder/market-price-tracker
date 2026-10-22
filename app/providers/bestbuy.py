"""Best Buy Products API provider (simple API-key auth)."""
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import requests

from app.config import settings
from app.providers.base import Listing, ProviderError

BASE = "https://api.bestbuy.com/v1/products"
FIELDS = "sku,name,salePrice,image,url,condition,categoryPath.name"


class BestBuyProvider:
    name = "bestbuy"

    def search(self, query: str, limit: int) -> list[Listing]:
        if not settings.bestbuy_api_key:
            raise ProviderError("BESTBUY_API_KEY is not configured")
        words = [w for w in query.split() if w]
        if not words:
            return []
        
        search = "&".join(f"search={quote(w, safe='')}" for w in words)
        r = requests.get(
            f"{BASE}(({search}))",
            params={"apiKey": settings.bestbuy_api_key, "format": "json", "show": FIELDS,
                    "pageSize": min(limit, 100), "sort": "salePrice.asc"},
            timeout=30,
        )
        if r.status_code != 200:
            raise ProviderError(f"Best Buy search failed ({r.status_code}): {r.text[:200]}")

        listings: list[Listing] = []
        for it in r.json().get("products", []):
            try:
                price = Decimal(str(it["salePrice"]))
            except (KeyError, InvalidOperation):
                continue
            cats = it.get("categoryPath") or []
            listings.append(
                Listing(
                    external_id=str(it["sku"]),
                    title=(it.get("name") or "")[:500],
                    price=price,
                    currency="USD",
                    category=cats[-1]["name"] if cats else None,
                    condition=it.get("condition"),
                    image_url=it.get("image"),
                    item_url=it.get("url"),
                )
            )
        return listings
