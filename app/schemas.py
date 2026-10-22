from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class QueryCreate(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    max_items: int = Field(default=50, ge=5, le=200)


class QueryOut(ORM):
    id: int
    query: str
    marketplace: str
    max_items: int
    active: bool
    created_at: datetime


class QueryStatOut(ORM):
    captured_at: datetime
    listing_count: int
    min_price: float
    median_price: float
    avg_price: float
    max_price: float
    currency: str


class SnapshotOut(ORM):
    price: float
    currency: str
    captured_at: datetime


class ProductOut(ORM):
    id: int
    source: str
    external_id: str
    query_id: int
    title: str
    category: str | None
    condition: str | None
    image_url: str | None
    item_url: str | None
    latest_price: float | None = None
    currency: str | None = None
    snapshot_count: int = 0


class ProductDetail(ProductOut):
    snapshots: list[SnapshotOut] = []


class ProductStatistics(BaseModel):
    product_id: int
    current_price: float
    lowest_price: float
    highest_price: float
    average_price: float
    absolute_change: float
    percentage_change: float
    snapshot_count: int
    first_capture: datetime
    latest_capture: datetime
    currency: str


class Overview(BaseModel):
    tracked_queries: int
    products: int
    price_snapshots: int
    latest_capture: datetime | None


class IngestResult(BaseModel):
    query_id: int
    query: str
    listings: int
    new_products: int
    median_price: float | None
    currency: str | None
