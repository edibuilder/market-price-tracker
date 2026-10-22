from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal, get_db
from app.models import PriceSnapshot, Product, QueryStat, TrackedQuery
from app.providers.base import ProviderError
from app.providers.bestbuy import BestBuyProvider
from app.providers.cheapshark import CheapSharkProvider
from app.providers.ebay import EbayProvider
from app.schemas import (IngestResult, Overview, ProductDetail, ProductOut, ProductStatistics,
                         QueryCreate, QueryOut, QueryStatOut, SnapshotOut)
from app.services.ingestion import ingest_all, ingest_query

PROVIDERS = {"cheapshark": CheapSharkProvider, "bestbuy": BestBuyProvider, "ebay": EbayProvider}
if settings.price_provider not in PROVIDERS:
    raise RuntimeError(f"PRICE_PROVIDER must be one of {list(PROVIDERS)}")
provider = PROVIDERS[settings.price_provider]()
MARKETPLACE = settings.ebay_marketplace if settings.price_provider == "ebay" else settings.price_provider.upper()


def get_provider():
    return provider


def scheduled_job():
    db = SessionLocal()
    try:
        ingest_all(db, provider)
    except ProviderError:
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = BackgroundScheduler()
        scheduler.add_job(scheduled_job, "interval", minutes=settings.ingest_interval_minutes,
                          id="ingest", max_instances=1, coalesce=True)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Price Intelligence API", version="2.0.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard/")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/queries", response_model=list[QueryOut])
def list_queries(db: Session = Depends(get_db)):
    return db.scalars(select(TrackedQuery).order_by(TrackedQuery.id)).all()


@app.post("/queries", response_model=QueryOut, status_code=201)
def create_query(body: QueryCreate, db: Session = Depends(get_db)):
    q = body.query.strip()
    exists = db.scalar(select(TrackedQuery).where(
        TrackedQuery.query == q, TrackedQuery.marketplace == MARKETPLACE))
    if exists:
        raise HTTPException(409, "This query is already tracked")
    tq = TrackedQuery(query=q, marketplace=MARKETPLACE, max_items=body.max_items)
    db.add(tq)
    db.commit()
    return tq


@app.delete("/queries/{query_id}", status_code=204)
def delete_query(query_id: int, db: Session = Depends(get_db)):
    tq = db.get(TrackedQuery, query_id)
    if not tq:
        raise HTTPException(404, "Query not found")
    db.delete(tq)
    db.commit()


@app.get("/queries/{query_id}/trend", response_model=list[QueryStatOut])
def query_trend(query_id: int, db: Session = Depends(get_db)):
    if not db.get(TrackedQuery, query_id):
        raise HTTPException(404, "Query not found")
    return db.scalars(select(QueryStat).where(QueryStat.query_id == query_id)
                      .order_by(QueryStat.captured_at)).all()


@app.post("/ingest", response_model=list[IngestResult])
def ingest_everything(db: Session = Depends(get_db), prov=Depends(get_provider)):
    try:
        return ingest_all_strict(db, prov)
    except ProviderError as e:
        raise HTTPException(503, str(e))


def ingest_all_strict(db, prov):
    results = []
    for tq in db.scalars(select(TrackedQuery).where(TrackedQuery.active.is_(True))).all():
        results.append(ingest_query(db, prov, tq))
    return results


@app.post("/queries/{query_id}/ingest", response_model=IngestResult)
def ingest_one(query_id: int, db: Session = Depends(get_db), prov=Depends(get_provider)):
    tq = db.get(TrackedQuery, query_id)
    if not tq:
        raise HTTPException(404, "Query not found")
    try:
        return ingest_query(db, prov, tq)
    except ProviderError as e:
        raise HTTPException(503, str(e))


def _to_out(p: Product, cls=ProductOut):
    last = p.snapshots[-1] if p.snapshots else None
    data = cls.model_validate(p).model_dump()
    data.update(latest_price=float(last.price) if last else None,
                currency=last.currency if last else None, snapshot_count=len(p.snapshots))
    return data


@app.get("/products", response_model=list[ProductOut])
def list_products(query_id: int | None = None, search: str | None = None,
                  skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db)):
    stmt = select(Product).order_by(Product.id.desc())
    if query_id:
        stmt = stmt.where(Product.query_id == query_id)
    if search:
        stmt = stmt.where(Product.title.ilike(f"%{search}%"))
    return [_to_out(p) for p in db.scalars(stmt.offset(skip).limit(limit)).all()]


def _product_or_404(db, product_id) -> Product:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@app.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = _product_or_404(db, product_id)
    data = _to_out(p, ProductDetail)
    data["snapshots"] = [SnapshotOut.model_validate(s) for s in p.snapshots]
    return data


@app.get("/products/{product_id}/history", response_model=list[SnapshotOut])
def product_history(product_id: int, db: Session = Depends(get_db)):
    return _product_or_404(db, product_id).snapshots


@app.get("/products/{product_id}/latest-price", response_model=SnapshotOut)
def latest_price(product_id: int, db: Session = Depends(get_db)):
    p = _product_or_404(db, product_id)
    if not p.snapshots:
        raise HTTPException(404, "No snapshots yet")
    return p.snapshots[-1]


@app.get("/products/{product_id}/statistics", response_model=ProductStatistics)
def product_statistics(product_id: int, db: Session = Depends(get_db)):
    p = _product_or_404(db, product_id)
    if not p.snapshots:
        raise HTTPException(404, "No snapshots yet")
    prices = [float(s.price) for s in p.snapshots]
    first, last = prices[0], prices[-1]
    return ProductStatistics(
        product_id=p.id, current_price=last, lowest_price=min(prices), highest_price=max(prices),
        average_price=round(sum(prices) / len(prices), 2), absolute_change=round(last - first, 2),
        percentage_change=round((last - first) / first * 100, 2) if first else 0.0,
        snapshot_count=len(prices), first_capture=p.snapshots[0].captured_at,
        latest_capture=p.snapshots[-1].captured_at, currency=p.snapshots[-1].currency)


@app.get("/analytics/overview", response_model=Overview)
def overview(db: Session = Depends(get_db)):
    return Overview(
        tracked_queries=db.scalar(select(func.count(TrackedQuery.id))) or 0,
        products=db.scalar(select(func.count(Product.id))) or 0,
        price_snapshots=db.scalar(select(func.count(PriceSnapshot.id))) or 0,
        latest_capture=db.scalar(select(func.max(PriceSnapshot.captured_at))))


static_dir = Path(__file__).parent / "static"
app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")
