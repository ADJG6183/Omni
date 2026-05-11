import pytest
from pydantic import ValidationError
from app.schemas.product import ProductObservation


def base_payload(**overrides) -> dict:
    defaults = {
        "retailer": "amazon",
        "product_url": "https://www.amazon.com/dp/B09XS7JWHH",
        "title": "Sony WH-1000XM5 Headphones",
        "price": 328.00,
        "currency": "USD",
    }
    return {**defaults, **overrides}


class TestProductObservationValidation:
    def test_valid_payload_accepted(self):
        obs = ProductObservation(**base_payload())
        assert obs.price == 328.00
        assert obs.retailer == "amazon"

    def test_price_zero_rejected(self):
        with pytest.raises(ValidationError, match="positive"):
            ProductObservation(**base_payload(price=0))

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            ProductObservation(**base_payload(price=-10))

    def test_unsupported_retailer_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported retailer"):
            ProductObservation(**base_payload(retailer="walmart"))

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            ProductObservation(**base_payload(title=""))

    def test_unsupported_currency_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported currency"):
            ProductObservation(**base_payload(currency="EUR"))

    def test_invalid_rating_rejected(self):
        with pytest.raises(ValidationError):
            ProductObservation(**base_payload(rating=6.0))

    def test_negative_review_count_rejected(self):
        with pytest.raises(ValidationError):
            ProductObservation(**base_payload(review_count=-1))

    def test_retailer_normalized_to_lowercase(self):
        obs = ProductObservation(**base_payload(retailer="AMAZON"))
        assert obs.retailer == "amazon"

    def test_optional_fields_default_to_none(self):
        obs = ProductObservation(**base_payload())
        assert obs.brand is None
        assert obs.category is None
        assert obs.rating is None
