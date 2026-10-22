from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class Listing:
    external_id: str
    title: str
    price: Decimal
    currency: str
    category: str | None = None
    condition: str | None = None
    image_url: str | None = None
    item_url: str | None = None


class ProviderError(Exception):
    pass


class PriceProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[Listing]: ...
