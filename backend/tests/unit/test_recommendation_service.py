import pytest
from app.services.recommendation_service import generate_recommendation
from app.schemas.product import PriceSummary


def make_summary(**kwargs) -> PriceSummary:
    defaults = {
        "current_price": 300.0,
        "lowest_price_seen": 250.0,
        "highest_price_seen": 400.0,
        "average_price_30d": 310.0,
        "observation_count": 10,
    }
    return PriceSummary(**{**defaults, **kwargs})


class TestInsufficientData:
    def test_zero_observations(self):
        summary = make_summary(observation_count=0)
        result = generate_recommendation(summary)
        assert result.recommendation == "INSUFFICIENT_DATA"
        assert result.confidence == "low"

    def test_one_observation(self):
        summary = make_summary(observation_count=1)
        result = generate_recommendation(summary)
        assert result.recommendation == "INSUFFICIENT_DATA"

    def test_two_observations_is_enough(self):
        summary = make_summary(observation_count=2)
        result = generate_recommendation(summary)
        assert result.recommendation != "INSUFFICIENT_DATA"


class TestBuyNow:
    def test_price_at_historical_low(self):
        summary = make_summary(current_price=250.0, lowest_price_seen=250.0)
        result = generate_recommendation(summary)
        assert result.recommendation == "BUY_NOW"

    def test_price_within_3pct_of_low(self):
        # 250 * 1.03 = 257.5 — price of 255 should trigger BUY_NOW
        summary = make_summary(current_price=255.0, lowest_price_seen=250.0)
        result = generate_recommendation(summary)
        assert result.recommendation == "BUY_NOW"

    def test_price_just_above_threshold(self):
        # 250 * 1.03 = 257.5 — price of 260 should NOT trigger BUY_NOW
        summary = make_summary(current_price=260.0, lowest_price_seen=250.0, average_price_30d=270.0)
        result = generate_recommendation(summary)
        assert result.recommendation != "BUY_NOW"


class TestAvoidThisDeal:
    def test_price_15pct_above_avg(self):
        # avg=310, threshold=310*1.15=356.5 — price of 360 triggers AVOID
        summary = make_summary(current_price=360.0, average_price_30d=310.0, lowest_price_seen=250.0)
        result = generate_recommendation(summary)
        assert result.recommendation == "AVOID_THIS_DEAL"

    def test_price_just_below_avoid_threshold(self):
        # avg=310, threshold=356.5 — price of 355 should not trigger AVOID
        summary = make_summary(current_price=355.0, average_price_30d=310.0, lowest_price_seen=250.0)
        result = generate_recommendation(summary)
        assert result.recommendation != "AVOID_THIS_DEAL"


class TestWatchClosely:
    def test_midrange_price_returns_watch(self):
        # Not near low, not overpriced
        summary = make_summary(current_price=300.0, lowest_price_seen=250.0, average_price_30d=310.0)
        result = generate_recommendation(summary)
        assert result.recommendation == "WATCH_CLOSELY"

    def test_explanation_is_non_empty(self):
        summary = make_summary()
        result = generate_recommendation(summary)
        assert len(result.explanation) > 0
