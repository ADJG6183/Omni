import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
      1. Upsert product record
      2. Store price observation (with dedup)
      3. Compute price summary from history
      4. Apply recommendation rules
      5. Return structured response
    """
    start = time.monotonic()

    observed_at = observation.timestamp or datetime.now(timezone.utc)

    # 1. Upsert product
    product = product_service.get_or_create_product(db, observation)

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

    db.commit()

    # 3. Price summary from stored history
    summary = price_service.get_price_summary(db, product.id, observation.price)

    # 4. Recommendation
    result = recommendation_service.generate_recommendation(summary)

    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "analyze: product=%s recommendation=%s latency=%dms",
        product.id,
        result.recommendation,
        latency_ms,
    )

    return ProductAnalysisResponse(
        product_id=product.id,
        recommendation=result.recommendation,
        recommendation_label=result.recommendation_label,
        confidence=result.confidence,
        drop_probability_7d=None,  # Phase 3: ML model will populate this
        current_price=summary.current_price,
        average_price_30d=summary.average_price_30d,
        lowest_price_seen=summary.lowest_price_seen,
        highest_price_seen=summary.highest_price_seen,
        explanation=result.explanation,
        price_history_available=summary.observation_count > 0,
        model_version="rules_v1",
        latency_ms=latency_ms,
    )
