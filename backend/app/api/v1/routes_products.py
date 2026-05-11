import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import OmniError
from app.db.session import get_db
from app.schemas.product import ProductObservation, ProductAnalysisResponse
from app.services import product_service, price_service, recommendation_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/products/analyze", response_model=ProductAnalysisResponse)
def analyze_product(observation: ProductObservation, db: Session = Depends(get_db)) -> ProductAnalysisResponse:
    """
    Main endpoint: receive a product observation, store it, return a recommendation.

    Flow:
      1. Upsert product record (returns data quality warnings)
      2. Store price observation (with dedup)
      3. Commit — wrapped so any DB failure returns a clean retryable error
      4. Compute price summary from history
      5. Apply recommendation rules
      6. Return structured response with warnings
    """
    start = time.monotonic()
    warnings: list[str] = []

    observed_at = observation.timestamp or datetime.now(timezone.utc)

    # 1. Upsert product
    product, product_warnings = product_service.get_or_create_product(db, observation)
    warnings.extend(product_warnings)

    # 2. Store price observation
    price_service.store_price_observation(
        db=db,
        product_id=product.id,
        price=observation.price,
        currency=observation.currency,
        availability=observation.availability,
        observed_at=observed_at,
        source="extension",
    )

    # 3. Commit — if this fails, return a retryable error instead of a raw 500
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("DB commit failed for product observation: %s", exc)
        raise OmniError(
            code="DB_COMMIT_FAILED",
            message="Failed to save product data. Please try again.",
            status_code=503,
            retryable=True,
        )

    # 4. Price summary
    summary = price_service.get_price_summary(db, product.id, observation.price)

    # 5. Data quality warning: unusual price vs recent history
    if (
        summary.average_price_30d
        and abs(observation.price - summary.average_price_30d) / summary.average_price_30d > 0.80
    ):
        warnings.append(
            f"Current price (${observation.price:.2f}) differs by more than 80% from the "
            f"30-day average (${summary.average_price_30d:.2f}). Verify this is the correct price."
        )

    # 6. Recommendation
    result = recommendation_service.generate_recommendation(summary)

    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "analyze: product=%s recommendation=%s warnings=%d latency=%dms",
        product.id,
        result.recommendation,
        len(warnings),
        latency_ms,
    )

    return ProductAnalysisResponse(
        product_id=product.id,
        recommendation=result.recommendation,
        recommendation_label=result.recommendation_label,
        confidence=result.confidence,
        drop_probability_7d=None,
        current_price=summary.current_price,
        average_price_30d=summary.average_price_30d,
        lowest_price_seen=summary.lowest_price_seen,
        highest_price_seen=summary.highest_price_seen,
        explanation=result.explanation,
        warnings=warnings,
        price_history_available=summary.observation_count > 0,
        model_version="rules_v1",
        latency_ms=latency_ms,
    )
