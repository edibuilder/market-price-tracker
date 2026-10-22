from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrackedQuery(Base):
    """A search (e.g. 'iphone 15 128gb') whose market price we follow over time."""
    __tablename__ = "tracked_queries"
    __table_args__ = (UniqueConstraint("query", "marketplace", name="uq_query_marketplace"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(200))
    marketplace: Mapped[str] = mapped_column(String(20))
    max_items: Mapped[int] = mapped_column(Integer, default=50)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="query", cascade="all, delete-orphan")
    stats: Mapped[list["QueryStat"]] = relationship(
        back_populates="query", cascade="all, delete-orphan", order_by="QueryStat.captured_at"
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(100))
    query_id: Mapped[int] = mapped_column(ForeignKey("tracked_queries.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(60), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    item_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    query: Mapped[TrackedQuery] = relationship(back_populates="products")
    snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="PriceSnapshot.captured_at"
    )


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    product: Mapped[Product] = relationship(back_populates="snapshots")


class QueryStat(Base):
    """Aggregate market price of a tracked query at one point in time."""
    __tablename__ = "query_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("tracked_queries.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    listing_count: Mapped[int] = mapped_column(Integer)
    min_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    median_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    max_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))

    query: Mapped[TrackedQuery] = relationship(back_populates="stats")
