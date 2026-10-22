"""CheapShark provider: real PC game prices across many stores. No API key required."""
from decimal import Decimal, InvalidOperation
from math import ceil

import requests

from app.providers.base import Listing, ProviderError

BASE = "https://www.cheapshark.com/api/1.0"

HEADERS = {"User-Agent": "PriceIntelligence/2.0 (personal portfolio project)"}
PAGE_SIZE = 60


class CheapSharkProvider:
    name = "cheapshark"

    def __init__(self):
        self._stores: dict[str, str] | None = None

    def _store_names(self) -> dict[str, str]:
        if self._stores is None:
            try:
                r = requests.get(f"{BASE}/stores", headers=HEADERS, timeout=20)
                r.raise_for_status()
                self._stores = {s["storeID"]: s["storeName"] for s in r.json()}
            except Exception:
                return {}
        return self._stores

    def search(self, query: str, limit: int) -> list[Listing]:
        stores = self._store_names()
        listings: list[Listing] = []
        for page in range(ceil(limit / PAGE_SIZE)):
            r = requests.get(
                f"{BASE}/deals",
                params={"title": query, "pageSize": min(PAGE_SIZE, limit), "pageNumber": page, "sortBy": "Title"},
                headers=HEADERS,
                timeout=30,
            )
            if r.status_code != 200:
                raise ProviderError(f"CheapShark request failed ({r.status_code}): {r.text[:200]}")
            items = r.json()
            for it in items:
                try:
                    price = Decimal(str(it["salePrice"]))
                except (KeyError, InvalidOperation):
                    continue

                listings.append(Listing(
                    external_id=f"{it['gameID']}-{it['storeID']}",
                    title=(it.get("title") or "")[:500],
                    price=price,
                    currency="USD",
                    category=stores.get(it["storeID"], f"Store {it['storeID']}"),
                    condition="On sale" if str(it.get("isOnSale")) == "1" else "Regular price",
                    image_url=it.get("thumb"),
                    item_url=f"https://www.cheapshark.com/redirect?dealID={it['dealID']}",
                ))
            if len(items) < PAGE_SIZE:
                break
        return listings[:limit]
