"""
Stores model predictions to the predictions table.

Why store predictions?
----------------------
Storing each inference result lets us:
- Track how the model's probability estimates evolve for a product over time
- Compute business metrics later (was the model right? did the price actually drop?)
- Debug production anomalies (why did the recommendation change for this product?)
- Detect model drift (are probabilities shifting systematically over time?)

We only store predictions when ML inference actually ran (drop_probability_7d
is not None). Rule-based fallback responses are not stored here.
"""
import logging

from sqlalchemy.orm import Session

from app.db.models import Prediction

logger = logging.getLogger(__name__)


def store_prediction(
    db: Session,
    product_id: str,
    model_version: str,
    drop_probability_7d: float | None,
    recommendation: str,
    confidence: str,
    explanation: list[str],
) -> None:
    """
    Insert a prediction row. The caller is responsible for committing.
    Silently skips if drop_probability_7d is None (no ML output to store).
    """
    if drop_probability_7d is None:
        return

    prediction = Prediction(
        product_id=product_id,
        model_version=model_version,
        drop_probability_7d=round(drop_probability_7d, 4),
        recommendation=recommendation,
        confidence=confidence,
        explanation=explanation,
    )
    db.add(prediction)
    logger.debug(
        "Queued prediction for product %s: prob=%.3f recommendation=%s",
        product_id, drop_probability_7d, recommendation,
    )
