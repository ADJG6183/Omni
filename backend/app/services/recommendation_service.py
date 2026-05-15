from dataclasses import dataclass
from typing import Optional

from app.schemas.product import PriceSummary

MIN_OBSERVATIONS_FOR_RECOMMENDATION = 2

# ML probability thresholds
DROP_PROB_HIGH = 0.60   # above this → model is confident a drop is coming → Wait
DROP_PROB_LOW  = 0.35   # below this → model is confident no drop soon → consider Buy

# Price-rule thresholds (used as safety nets even when ML is available)
NEAR_HISTORICAL_LOW_RATIO = 1.03    # within 3% of all-time low → strong buy signal
OVERPRICED_VS_AVG_RATIO   = 1.15    # 15% above 30d average → avoid regardless of ML


@dataclass
class RecommendationResult:
    recommendation: str         # internal enum string
    recommendation_label: str   # user-facing label
    confidence: str             # "high" | "medium" | "low"
    explanation: list[str]


def generate_recommendation(
    summary: PriceSummary,
    drop_probability_7d: Optional[float] = None,
) -> RecommendationResult:
    """
    Generate a recommendation combining ML probability with deterministic rules.

    When ML probability is available, it drives the primary decision and rules
    act as safety nets (e.g. never recommend Buy when price is 20% above average).

    When ML probability is None (model not loaded, insufficient history), the
    function falls back to the pure rule-based logic from Phase 1.

    Thresholds:
        drop_prob >= 0.60  →  WAIT_FOR_DROP  (model is confident a drop is coming)
        drop_prob <= 0.35  →  consider BUY_NOW (model sees no drop coming)
        0.35 < drop_prob < 0.60  →  WATCH_CLOSELY (uncertain)

    Override rules (applied regardless of ML probability):
        - Out of stock → WATCH_CLOSELY
        - Insufficient history → INSUFFICIENT_DATA
        - Price > avg_30d * 1.15 → AVOID_THIS_DEAL
        - Price <= lowest * 1.03 AND drop_prob <= 0.35 → BUY_NOW (price already at low)
    """
    price = summary.current_price

    if summary.observation_count < MIN_OBSERVATIONS_FOR_RECOMMENDATION:
        return RecommendationResult(
            recommendation="INSUFFICIENT_DATA",
            recommendation_label="Not Enough Data Yet",
            confidence="low",
            explanation=[
                "Omni has limited price history for this product.",
                "Track this product to improve future recommendations.",
                "Check back after a few more price observations.",
            ],
        )

    lowest = summary.lowest_price_seen
    avg_30d = summary.average_price_30d

    # Safety override: price significantly above recent average → avoid
    if avg_30d and price > avg_30d * OVERPRICED_VS_AVG_RATIO:
        return RecommendationResult(
            recommendation="AVOID_THIS_DEAL",
            recommendation_label="Avoid This Deal",
            confidence="medium",
            explanation=[
                f"Current price (${price:.2f}) is {((price / avg_30d) - 1) * 100:.0f}% "
                f"above the 30-day average (${avg_30d:.2f}).",
                "This product has been cheaper recently.",
                "Consider waiting for the price to return to normal.",
            ],
        )

    # --- ML-driven path ---
    if drop_probability_7d is not None:
        return _ml_recommendation(price, drop_probability_7d, lowest, avg_30d)

    # --- Rule-based fallback (no ML) ---
    return _rules_recommendation(price, lowest, avg_30d)


def _ml_recommendation(
    price: float,
    prob: float,
    lowest: Optional[float],
    avg_30d: Optional[float],
) -> RecommendationResult:
    """ML probability drives the recommendation label."""

    if prob >= DROP_PROB_HIGH:
        return RecommendationResult(
            recommendation="WAIT_FOR_DROP",
            recommendation_label="Wait for Drop",
            confidence="high" if prob >= 0.75 else "medium",
            explanation=[
                f"The model predicts a {prob:.0%} chance of a price drop within 7 days.",
                "Historical patterns suggest this product tends to drop after its current price level.",
                "Waiting a week may result in meaningful savings.",
            ],
        )

    if prob <= DROP_PROB_LOW:
        if lowest and price <= lowest * NEAR_HISTORICAL_LOW_RATIO:
            return RecommendationResult(
                recommendation="BUY_NOW",
                recommendation_label="Buy Now",
                confidence="high",
                explanation=[
                    f"Current price (${price:.2f}) is at or near the historical low (${lowest:.2f}).",
                    f"The model predicts only a {prob:.0%} chance of a further price drop.",
                    "This looks like a good time to buy.",
                ],
            )
        return RecommendationResult(
            recommendation="BUY_NOW",
            recommendation_label="Buy Now",
            confidence="medium",
            explanation=[
                f"The model predicts only a {prob:.0%} chance of a price drop in the next 7 days.",
                "Price appears stable at its current level.",
                "If you need this product, now is a reasonable time to buy.",
            ],
        )

    return RecommendationResult(
        recommendation="WATCH_CLOSELY",
        recommendation_label="Watch Closely",
        confidence="low",
        explanation=[
            f"The model gives a {prob:.0%} chance of a price drop — not a strong signal either way.",
            "Price is within normal range for this product.",
            "Track it and check back in a few days.",
        ],
    )


def _rules_recommendation(
    price: float,
    lowest: Optional[float],
    avg_30d: Optional[float],
) -> RecommendationResult:
    """Pure rule-based fallback when ML is not available."""
    if lowest and price <= lowest * NEAR_HISTORICAL_LOW_RATIO:
        return RecommendationResult(
            recommendation="BUY_NOW",
            recommendation_label="Buy Now",
            confidence="medium",
            explanation=[
                f"Current price (${price:.2f}) is at or near the lowest recorded price (${lowest:.2f}).",
                "Historically, this is a good time to buy.",
                "Price drops below this level are uncommon.",
            ],
        )

    return RecommendationResult(
        recommendation="WATCH_CLOSELY",
        recommendation_label="Watch Closely",
        confidence="low",
        explanation=[
            "Current price is within the normal range for this product.",
            "No strong signal for an imminent price drop or spike.",
            "Track this product to get notified if conditions change.",
        ],
    )
