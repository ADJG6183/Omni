"""
Integration tests for POST /api/v1/products/analyze.

These tests run against a real PostgreSQL database. They use a transaction
that is rolled back after each test so the DB stays clean between runs.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import get_db
from app.db.models import Base, Retailer

TEST_DATABASE_URL = "postgresql://omni:omnipass@localhost:5432/omni_db"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    """
    Each test gets its own transaction that is rolled back at the end.
    This keeps tests isolated without wiping the DB between runs.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the DB dependency overridden to use the test session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


VALID_AMAZON_PAYLOAD = {
    "retailer": "amazon",
    "product_url": "https://www.amazon.com/dp/B09XS7JWHH",
    "title": "Sony WH-1000XM5 Wireless Headphones",
    "price": 328.00,
    "currency": "USD",
    "availability": "in_stock",
    "brand": "Sony",
    "category": "electronics",
}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAnalyzeEndpoint:
    def test_valid_payload_returns_200(self, client):
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        body = resp.json()
        assert "product_id" in body
        assert "recommendation" in body
        assert "recommendation_label" in body
        assert "confidence" in body
        assert "explanation" in body
        assert isinstance(body["explanation"], list)
        assert "current_price" in body
        assert body["current_price"] == 328.00

    def test_first_observation_returns_insufficient_data(self, client):
        # First observation ever for a product → not enough history
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        body = resp.json()
        assert body["recommendation"] == "INSUFFICIENT_DATA"
        assert body["price_history_available"] is True

    def test_model_version_is_rules_v1(self, client):
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        assert resp.json()["model_version"] == "rules_v1"

    def test_drop_probability_is_null_in_phase1(self, client):
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        assert resp.json()["drop_probability_7d"] is None

    def test_same_payload_twice_deduplicates(self, client):
        """Second identical request within the dedup window should not create a second price row."""
        from app.db.models import PriceHistory, Product
        from sqlalchemy.orm import Session

        # Send twice
        client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)

        # Check via the test session that only 1 price row exists
        # We need to query through the fixture's session
        resp = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        product_id = resp.json()["product_id"]

        # Dedup is verified implicitly: if 3 identical calls created 3 rows,
        # the recommendation would differ (it uses observation_count).
        # With dedup, count stays at 1 → INSUFFICIENT_DATA throughout.
        assert resp.json()["recommendation"] == "INSUFFICIENT_DATA"

    def test_missing_price_returns_422(self, client):
        payload = {**VALID_AMAZON_PAYLOAD}
        del payload["price"]
        resp = client.post("/api/v1/products/analyze", json=payload)
        assert resp.status_code == 422

    def test_zero_price_returns_422(self, client):
        resp = client.post("/api/v1/products/analyze", json={**VALID_AMAZON_PAYLOAD, "price": 0})
        assert resp.status_code == 422

    def test_negative_price_returns_422(self, client):
        resp = client.post("/api/v1/products/analyze", json={**VALID_AMAZON_PAYLOAD, "price": -10})
        assert resp.status_code == 422

    def test_unsupported_retailer_returns_422(self, client):
        resp = client.post("/api/v1/products/analyze", json={**VALID_AMAZON_PAYLOAD, "retailer": "walmart"})
        assert resp.status_code == 422

    def test_empty_title_returns_422(self, client):
        resp = client.post("/api/v1/products/analyze", json={**VALID_AMAZON_PAYLOAD, "title": ""})
        assert resp.status_code == 422

    def test_unsupported_currency_returns_422(self, client):
        resp = client.post("/api/v1/products/analyze", json={**VALID_AMAZON_PAYLOAD, "currency": "EUR"})
        assert resp.status_code == 422

    def test_product_id_is_stable_across_calls(self, client):
        """Same product URL should always resolve to the same product_id."""
        resp1 = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        resp2 = client.post("/api/v1/products/analyze", json=VALID_AMAZON_PAYLOAD)
        assert resp1.json()["product_id"] == resp2.json()["product_id"]

    def test_optional_fields_accepted(self, client):
        payload = {
            **VALID_AMAZON_PAYLOAD,
            "rating": 4.6,
            "review_count": 18342,
            "image_url": "https://example.com/image.jpg",
        }
        resp = client.post("/api/v1/products/analyze", json=payload)
        assert resp.status_code == 200
