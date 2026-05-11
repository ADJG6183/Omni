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


class TestProductUrlValidation:
    def test_valid_https_url_accepted(self):
        obs = ProductObservation(**base_payload(product_url="https://www.amazon.com/dp/B09XS7JWHH"))
        assert obs.product_url == "https://www.amazon.com/dp/B09XS7JWHH"

    def test_non_http_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http or https"):
            ProductObservation(**base_payload(product_url="javascript:alert(1)"))

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http or https"):
            ProductObservation(**base_payload(product_url="ftp://amazon.com/dp/B09XS7JWHH"))

    def test_url_without_domain_rejected(self):
        with pytest.raises(ValidationError, match="valid domain"):
            ProductObservation(**base_payload(product_url="https://"))

    def test_plain_string_rejected(self):
        with pytest.raises(ValidationError, match="http or https"):
            ProductObservation(**base_payload(product_url="not-a-url"))

    def test_http_url_accepted(self):
        # http (non-TLS) is allowed by the validator — enforcing https is a network concern
        obs = ProductObservation(**base_payload(product_url="http://www.amazon.com/dp/B09XS7JWHH"))
        assert obs.product_url.startswith("http://")


class TestTimestampValidation:
    def test_past_timestamp_accepted(self):
        from datetime import datetime, timezone, timedelta
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        obs = ProductObservation(**base_payload(timestamp=past.isoformat()))
        assert obs.timestamp is not None

    def test_future_timestamp_rejected(self):
        from datetime import datetime, timezone, timedelta
        from pydantic import ValidationError
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        with pytest.raises(ValidationError, match="future"):
            ProductObservation(**base_payload(timestamp=future.isoformat()))
