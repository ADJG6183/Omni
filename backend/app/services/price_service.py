import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import PriceHistory
from app.schemas.product import PriceSummary

logger = logging.getLogger(__name__)

DEDUP_WINDOW_HOURS = 6


def store_price_observation(
    db: Session,
    product_id: str,
    price: float,
    currency: str,
    availability: str | None,
    observed_at: datetime,
    source: str = "extension",
) -> PriceHistory | None:
    """
    Insert a new price observation, skipping duplicates.

    Dedup rule: if the same product has the same price + availability
    recorded within the last DEDUP_WINDOW_HOURS, skip the insert.
    This prevents noise in the price history from repeated page visits.
    """
    cutoff = observed_at - timedelta(hours=DEDUP_WINDOW_HOURS)

    recent = (
        db.query(PriceHistory)
        .filter(
            PriceHistory.product_id == product_id,
            PriceHistory.observed_at >= cutoff,
            PriceHistory.price == Decimal(str(price)),
            PriceHistory.availability == availability,
        )
        .first()
    )

    if recent:
        logger.debug(
            "Skipping duplicate price observation for product %s (price=%.2f, within %dh window)",
            product_id,
            price,
            DEDUP_WINDOW_HOURS,
        )
        return None

    observation = PriceHistory(
        product_id=product_id,
        price=Decimal(str(price)),
        currency=currency,
        availability=availability,
        observed_at=observed_at,
        source=source,
    )
    db.add(observation)
    db.flush()
    logger.info("Stored price observation for product %s: %.2f %s", product_id, price, currency)
    return observation


def get_price_summary(db: Session, product_id: str, current_price: float) -> PriceSummary:
    """
    Compute a price summary from stored price history.
    Uses a 30-day window for rolling stats.
    """
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    row = (
        db.query(
            func.min(PriceHistory.price).label("min_price"),
            func.max(PriceHistory.price).label("max_price"),
            func.avg(PriceHistory.price).label("avg_price"),
            func.count(PriceHistory.id).label("count"),
        )
        .filter(
            PriceHistory.product_id == product_id,
            PriceHistory.observed_at >= cutoff_30d,
        )
        .one()
    )

    all_time = (
        db.query(
            func.min(PriceHistory.price).label("min_price"),
            func.max(PriceHistory.price).label("max_price"),
            func.count(PriceHistory.id).label("count"),
        )
        .filter(PriceHistory.product_id == product_id)
        .one()
    )

    return PriceSummary(
        current_price=current_price,
        lowest_price_seen=float(all_time.min_price) if all_time.min_price else None,
        highest_price_seen=float(all_time.max_price) if all_time.max_price else None,
        average_price_30d=float(row.avg_price) if row.avg_price else None,
        observation_count=all_time.count or 0,
    )
