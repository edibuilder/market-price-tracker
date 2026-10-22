import os

os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app, get_provider
from app.providers.base import Listing


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.round = 0

    def search(self, query, limit):
        self.round += 1
        bump = Decimal(self.round)
        return [
            Listing("a1", "Phone A", Decimal("100.00") + bump, "USD", "Phones", "New"),
            Listing("a2", "Phone B", Decimal("200.00") + bump, "USD", "Phones", "Used"),
            Listing("a3", "Phone C", Decimal("300.00") + bump, "USD", "Phones", "Used"),
        ]


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    fake = FakeProvider()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_provider] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()
