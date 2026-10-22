def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_flow(client):
    r = client.post("/queries", json={"query": "test phone"})
    assert r.status_code == 201
    qid = r.json()["id"]
    assert client.post("/queries", json={"query": "test phone"}).status_code == 409

    r1 = client.post(f"/queries/{qid}/ingest").json()
    assert r1["listings"] == 3 and r1["new_products"] == 3
    r2 = client.post(f"/queries/{qid}/ingest").json()
    assert r2["new_products"] == 0  # same items, no duplicates

    trend = client.get(f"/queries/{qid}/trend").json()
    assert len(trend) == 2
    assert trend[0]["median_price"] == 201.0 and trend[1]["median_price"] == 202.0

    products = client.get(f"/products?query_id={qid}").json()
    assert len(products) == 3 and products[0]["snapshot_count"] == 2

    pid = products[0]["id"]
    stats = client.get(f"/products/{pid}/statistics").json()
    assert stats["snapshot_count"] == 2 and stats["absolute_change"] == 1.0
    assert len(client.get(f"/products/{pid}/history").json()) == 2

    ov = client.get("/analytics/overview").json()
    assert ov["products"] == 3 and ov["price_snapshots"] == 6

    assert client.delete(f"/queries/{qid}").status_code == 204
    assert client.get("/analytics/overview").json()["products"] == 0


def test_missing_product(client):
    assert client.get("/products/999").status_code == 404


def test_bestbuy_parsing(monkeypatch):
    from app.config import settings
    from app.providers import bestbuy

    monkeypatch.setattr(settings, "bestbuy_api_key", "k")

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"products": [
                {"sku": 123, "name": "MacBook Air", "salePrice": 899.99, "image": "i", "url": "u",
                 "condition": "New", "categoryPath": [{"name": "Computers"}, {"name": "Laptops"}]},
                {"sku": 124, "name": "No price"},
            ]}

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return R()

    monkeypatch.setattr(bestbuy.requests, "get", fake_get)
    out = bestbuy.BestBuyProvider().search("macbook air", 10)
    assert "search=macbook&search=air" in captured["url"]
    assert len(out) == 1 and out[0].external_id == "123" and out[0].category == "Laptops"
    assert str(out[0].price) == "899.99"


def test_cheapshark_parsing(monkeypatch):
    from app.providers import cheapshark

    class R:
        def __init__(self, data):
            self.data, self.status_code, self.text = data, 200, ""

        def json(self):
            return self.data

        def raise_for_status(self):
            pass

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/stores"):
            return R([{"storeID": "1", "storeName": "Steam"}])
        return R([
            {"gameID": "10", "storeID": "1", "dealID": "abc%3D", "title": "Batman", "salePrice": "4.99",
             "isOnSale": "1", "thumb": "t"},
            {"gameID": "11", "storeID": "1", "dealID": "x", "title": "Broken"},
        ])

    monkeypatch.setattr(cheapshark.requests, "get", fake_get)
    out = cheapshark.CheapSharkProvider().search("batman", 10)
    assert len(out) == 1 and out[0].external_id == "10-1"
    assert out[0].category == "Steam" and out[0].condition == "On sale" and str(out[0].price) == "4.99"
