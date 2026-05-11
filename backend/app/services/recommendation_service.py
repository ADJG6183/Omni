from dataclasses import dataclass

from app.schemas.product import PriceSummary

MIN_OBSERVATIONS_FOR_RECOMMENDATION = 2

# Thresholds
NEAR_HISTORICAL_LOW_RATIO = 1.03    # within 3% of all-time low → good deal
OVERPRICED_VS_AVG_RATIO = 1.15      # 15% above 30d average → overpriced


@dataclass
class RecommendationResult:
    recommendation: str         # internal enum string
    recommendation_label: str   # user-facing label
    confidence: str             # "high" | "medium" | "low"
    explanation: list[str]


def generate_recommendation(summary: PriceSummary) -> RecommendationResult:
    """
    Rule-based recommendation engine for Phase 1.
    No ML — purely deterministic rules based on price context.
    Phase 3 will replace/augment this with model inference.
    """
    price = summary.current_price

    # Not enough data to make a meaningful recommendation
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

    # Current price is at or near all-time low
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

    # Price is significantly above recent average — likely inflated
    if avg_30d and price > avg_30d * OVERPRICED_VS_AVG_RATIO:
        return RecommendationResult(
            recommendation="AVOID_THIS_DEAL",
            recommendation_label="Avoid This Deal",
            confidence="medium",
            explanation=[
                f"Current price (${price:.2f}) is {((price / avg_30d) - 1) * 100:.0f}% above the 30-day average (${avg_30d:.2f}).",
                "This product has been cheaper recently.",
                "Consider waiting for the price to return to normal.",
            ],
        )

    # Default: we have some data but no strong signal
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
