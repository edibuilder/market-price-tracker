# Price Intelligence API (v2)

Tracks **real product prices** over time from CheapShark (default, no key), Best Buy or eBay. FastAPI + PostgreSQL + SQLAlchemy + Alembic + Docker + Chart.js dashboard.

```
eBay Browse API -> ingestion (manual or scheduled) -> PostgreSQL -> analytics endpoints -> dashboard
```

## How it works
- You add **tracked searches** (e.g. `iphone 15 128gb`).
- Each ingestion fetches matching fixed-price listings, stores a **price snapshot per listing** and one **aggregate (min / median / avg / max / count)** per search.
- A background scheduler repeats ingestion every `INGEST_INTERVAL_MINUTES` (default 360), so history builds up by itself.

Tables: `tracked_queries`, `products`, `price_snapshots`, `query_stats`.

## Setup
Choose the source with `PRICE_PROVIDER` (`cheapshark`, `bestbuy` or `ebay`).

**CheapShark (default):** real PC game prices from Steam, GOG, Humble etc. No account or key needed. Track game titles, e.g. `batman`, `witcher`.

**Best Buy:** get a free key at https://developer.bestbuy.com and set `BESTBUY_API_KEY`.

**eBay:**
1. Create a free eBay developer account: https://developer.ebay.com -> Application Keys -> Production keyset.
2. `cp .env.example .env` and fill in `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`.

### Run with Docker (DB + API)
```
docker compose up --build
```
### Run locally
```
docker compose up -d db
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```
Dashboard: http://127.0.0.1:8000/dashboard/ - Swagger: http://127.0.0.1:8000/docs

## Tests
```
pytest
```
