from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, field_validator, model_validator

SUPPORTED_RETAILERS = {"amazon", "bestbuy"}
SUPPORTED_CURRENCIES = {"USD"}


class ProductObservation(BaseModel):
    retailer: str
    product_url: str
    title: str
    price: float
    currency: str = "USD"
    availability: Optional[str] = None
    image_url: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    retailer_product_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    @field_validator("retailer")
    @classmethod
    def validate_retailer(cls, v: str) -> str:
        normalized = v.lower().strip()
        if normalized not in SUPPORTED_RETAILERS:
            raise ValueError(f"Unsupported retailer '{v}'. Supported: {SUPPORTED_RETAILERS}")
        return normalized

    @field_validator("product_url")
    @classmethod
    def validate_product_url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("product_url must be an http or https URL")
        if not parsed.netloc:
            raise ValueError("product_url must include a valid domain")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be a positive number")
        if v > 1_000_000:
            raise ValueError("Price value is suspiciously large")
        return round(v, 2)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        upper = v.upper().strip()
        if upper not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency '{v}'. MVP supports: {SUPPORTED_CURRENCIES}")
        return upper

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Product title cannot be empty")
        if len(stripped) < 3:
            raise ValueError("Product title is too short to be valid")
        return stripped

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 5):
            raise ValueError("Rating must be between 0 and 5")
        return v

    @field_validator("review_count")
    @classmethod
    def validate_review_count(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Review count cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_timestamp_not_future(self) -> "ProductObservation":
        if self.timestamp:
            # Normalize both to UTC — handles naive timestamps by assuming UTC
            now_utc = datetime.now(timezone.utc)
            if self.timestamp.tzinfo is None:
                ts_utc = self.timestamp.replace(tzinfo=timezone.utc)
            else:
                ts_utc = self.timestamp.astimezone(timezone.utc)
            # 60-second grace period for client/server clock skew
            if ts_utc > now_utc + timedelta(seconds=60):
                raise ValueError("Timestamp cannot be in the future")
        return self


class PriceSummary(BaseModel):
    current_price: float
    lowest_price_seen: Optional[float]
    highest_price_seen: Optional[float]
    average_price_30d: Optional[float]
    observation_count: int


class ProductAnalysisResponse(BaseModel):
    product_id: str
    recommendation: str
    recommendation_label: str
    confidence: str
    drop_probability_7d: Optional[float]
    current_price: float
    average_price_30d: Optional[float]
    lowest_price_seen: Optional[float]
    highest_price_seen: Optional[float]
    explanation: list[str]
    warnings: list[str]
    price_history_available: bool
    model_version: str
    latency_ms: Optional[int]
