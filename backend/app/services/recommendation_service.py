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

# Sentinel value that represents "no data" in the feature vector (matches train.py NAN_FILL)
_NAN_FILL = -1.0


@dataclass
class RecommendationResult:
    recommendation: str         # internal enum string
    recommendation_label: str   # user-facing label
    confidence: str             # "high" | "medium" | "low"
    explanation: list[str]


def generate_recommendation(
    summary: PriceSummary,
    drop_probability_7d: Optional[float] = None,
    top_features: Optional[list[dict]] = None,
) -> RecommendationResult:
    """
    Generate a recommendation combining ML probability with deterministic rules.

    When ML probability is available, it drives the primary decision and rules
    act as safety nets (e.g. never recommend Buy when price is 20% above average).
    SHAP top_features, when provided, replace generic explanation strings with
    sentences derived from the actual signals the model used for this prediction.

    When ML probability is None (model not loaded, insufficient history), the
    function falls back to the pure rule-based logic from Phase 1.

    Thresholds:
        drop_prob >= 0.60  →  WAIT_FOR_DROP  (model is confident a drop is coming)
        drop_prob <= 0.35  →  consider BUY_NOW (model sees no drop coming)
        0.35 < drop_prob < 0.60  →  WATCH_CLOSELY (uncertain)

    Override rules (applied regardless of ML probability):
        - Insufficient history → INSUFFICIENT_DATA
        - Price > avg_30d * 1.15 → AVOID_THIS_DEAL
        - Price <= lowest * 1.03 AND drop_prob <= 0.35 → BUY_NOW (price already at low)
    """
    price = summary.current_price
    top_features = top_features or []

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
        return _ml_recommendation(price, drop_probability_7d, lowest, avg_30d, top_features)

    # --- Rule-based fallback (no ML) ---
    return _rules_recommendation(price, lowest, avg_30d)


def _feature_sentence(name: str, value: float, shap: float) -> Optional[str]:
    """
    Convert one SHAP feature into a plain-English sentence.

    shap > 0 means this feature pushed the model toward predicting a price drop.
    shap < 0 means it pushed toward predicting no drop.
    Returns None for features that don't translate into useful user-facing text.
    """
    if value == _NAN_FILL:
        return None

    pushing_drop = shap > 0

    if name == "price_vs_avg_30d_pct":
        pct = abs(value) * 100
        direction = "above" if value > 0 else "below"
        note = "— historically elevated, may pull back" if pushing_drop else "— at or below average, a fair price"
        return f"Price is {pct:.0f}% {direction} the 30-day average {note}."

    if name == "price_vs_max_30d_pct":
        # Negative value means price is below the 30-day high (expected); positive means at/above it.
        pct = abs(value) * 100
        if value >= -0.01:
            return "Price is at or near its 30-day high — likely an elevated entry point." if pushing_drop else None
        note = "— a discount from the recent peak" if not pushing_drop else "— but may fall further from here"
        return f"Price is {pct:.0f}% below its 30-day high {note}."

    if name == "price_vs_min_30d_pct":
        pct = value * 100
        if pct < 1:
            return "Price is at or near its 30-day low — historically a good entry point."
        note = "— room to drop back toward the recent floor" if pushing_drop else "— still close to its recent low"
        return f"Price is {pct:.0f}% above its 30-day low {note}."

    if name == "num_drops_7d":
        n = int(value)
        if n == 0:
            return None if pushing_drop else "No price drops in the last 7 days — price appears stable."
        return (
            f"{n} price drop{'s' if n > 1 else ''} in the last 7 days — active discounting pattern."
            if pushing_drop else
            f"{n} recent price drop{'s' if n > 1 else ''}, but price has since stabilized."
        )

    if name == "num_drops_30d":
        n = int(value)
        if n == 0:
            return None if pushing_drop else "Price has been stable for the past 30 days."
        return (
            f"{n} price drop{'s' if n > 1 else ''} in the last 30 days — this product discounts regularly."
            if pushing_drop else
            f"Price has dropped {n} time{'s' if n > 1 else ''} recently and is now at a good level."
        )

    if name == "days_since_last_drop":
        days = int(value)
        if days == 0:
            return "Price just dropped — may stabilize before dropping further." if not pushing_drop else None
        note = "— may be due for another soon" if pushing_drop and days > 7 else "— price may stabilize from here" if not pushing_drop else ""
        return f"Last price drop was {days} day{'s' if days != 1 else ''} ago {note}."

    if name == "price_change_prev_pct":
        pct = abs(value) * 100
        if pct < 0.5:
            return None  # sub-0.5% change is noise, not worth surfacing
        direction = "rose" if value > 0 else "fell"
        return f"Price {direction} {pct:.0f}% from the previous observation."

    if name in ("price_std_7d", "price_std_30d") and value > 0:
        window = "week" if name == "price_std_7d" else "30 days"
        return (
            f"High price volatility over the last {window} — price is moving frequently."
            if pushing_drop else
            f"Price has been relatively stable over the last {window}."
        )

    if name == "observation_count":
        n = int(value)
        if n < 10:
            return f"Based on only {n} price observations — confidence is lower than usual."
        return None  # ample data is not interesting to surface

    return None


def _shap_explanation(top_features: list[dict]) -> list[str]:
    """Convert the top SHAP features into a list of plain-English sentences."""
    sentences = []
    for feat in top_features:
        sentence = _feature_sentence(feat["name"], feat["value"], feat["shap"])
        if sentence:
            sentences.append(sentence)
    return sentences


def _ml_recommendation(
    price: float,
    prob: float,
    lowest: Optional[float],
    avg_30d: Optional[float],
    top_features: list[dict],
) -> RecommendationResult:
    """ML probability drives the recommendation label; SHAP features drive the explanation."""
    shap_sentences = _shap_explanation(top_features)

    if prob >= DROP_PROB_HIGH:
        generic = [
            "Historical patterns suggest this product tends to drop after its current price level.",
            "Waiting a week may result in meaningful savings.",
        ]
        explanation = (
            [f"The model predicts a {prob:.0%} chance of a price drop within 7 days."]
            + (shap_sentences if shap_sentences else generic)
        )
        return RecommendationResult(
            recommendation="WAIT_FOR_DROP",
            recommendation_label="Wait for Drop",
            confidence="high" if prob >= 0.75 else "medium",
            explanation=explanation,
        )

    if prob <= DROP_PROB_LOW:
        if lowest and price <= lowest * NEAR_HISTORICAL_LOW_RATIO:
            generic = [f"The model predicts only a {prob:.0%} chance of a further price drop."]
            explanation = (
                [f"Current price (${price:.2f}) is at or near the historical low (${lowest:.2f})."]
                + (shap_sentences if shap_sentences else generic)
                + ["This looks like a good time to buy."]
            )
            return RecommendationResult(
                recommendation="BUY_NOW",
                recommendation_label="Buy Now",
                confidence="high",
                explanation=explanation,
            )
        generic = [
            "Price appears stable at its current level.",
            "If you need this product, now is a reasonable time to buy.",
        ]
        explanation = (
            [f"The model predicts only a {prob:.0%} chance of a price drop in the next 7 days."]
            + (shap_sentences if shap_sentences else generic)
        )
        return RecommendationResult(
            recommendation="BUY_NOW",
            recommendation_label="Buy Now",
            confidence="medium",
            explanation=explanation,
        )

    generic = [
        "Price is within normal range for this product.",
        "Track it and check back in a few days.",
    ]
    explanation = (
        [f"The model gives a {prob:.0%} chance of a price drop — not a strong signal either way."]
        + (shap_sentences if shap_sentences else generic)
    )
    return RecommendationResult(
        recommendation="WATCH_CLOSELY",
        recommendation_label="Watch Closely",
        confidence="low",
        explanation=explanation,
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
