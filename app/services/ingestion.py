from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PriceSnapshot, Product, QueryStat, TrackedQuery
from app.providers.base import PriceProvider
from app.schemas import IngestResult

CENT = Decimal("0.01")


def ingest_query(db: Session, provider: PriceProvider, tq: TrackedQuery) -> IngestResult:
    listings = provider.search(tq.query, tq.max_items)
    if not listings:
        return IngestResult(query_id=tq.id, query=tq.query, listings=0, new_products=0,
                            median_price=None, currency=None)

    # Keep only the dominant currency so aggregates are comparable
    currency = Counter(l.currency for l in listings).most_common(1)[0][0]
    listings = [l for l in listings if l.currency == currency]
    now = datetime.now(timezone.utc)
    new_products = 0

    for l in listings:
        product = db.scalar(
            select(Product).where(Product.source == provider.name, Product.external_id == l.external_id)
        )
        if product is None:
            product = Product(source=provider.name, external_id=l.external_id, query_id=tq.id,
                              title=l.title, category=l.category, condition=l.condition,
                              image_url=l.image_url, item_url=l.item_url)
            db.add(product)
            db.flush()
            new_products += 1
        else:
            product.title, product.category, product.condition = l.title, l.category, l.condition
            product.image_url, product.item_url = l.image_url, l.item_url
        db.add(PriceSnapshot(product_id=product.id, price=l.price, currency=l.currency, captured_at=now))

    prices = [l.price for l in listings]
    med = Decimal(median(prices)).quantize(CENT)
    db.add(QueryStat(
        query_id=tq.id, captured_at=now, listing_count=len(prices), currency=currency,
        min_price=min(prices), max_price=max(prices), median_price=med,
        avg_price=(sum(prices) / len(prices)).quantize(CENT),
    ))
    db.commit()
    return IngestResult(query_id=tq.id, query=tq.query, listings=len(prices),
                        new_products=new_products, median_price=float(med), currency=currency)


def ingest_all(db: Session, provider: PriceProvider) -> list[IngestResult]:
    results = []
    for tq in db.scalars(select(TrackedQuery).where(TrackedQuery.active.is_(True))):
        try:
            results.append(ingest_query(db, provider, tq))
        except Exception:  # one failing query must not stop the others
            db.rollback()
    return results
