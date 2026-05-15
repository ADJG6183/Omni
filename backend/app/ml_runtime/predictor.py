"""
Predictor — builds a feature vector from stored price history and runs inference.

Training vs inference feature parity
-------------------------------------
The feature computation here mirrors ml/src/build_features.py. Both produce
the same column names and rolling window logic. This intentional duplication
trades DRY code for architectural independence: the training pipeline can run
anywhere (a laptop, a CI job, a cron job) without coupling to the FastAPI
process, and the serving stack can evolve its performance characteristics
(caching, batching) without affecting offline training.

The contract between them is ml/artifacts/feature_columns_v1.json. If a feature
is renamed or removed in build_features.py, it must be updated here too, and
a new model version trained with the updated column list.

Fallback behaviour
------------------
If the model is not loaded (artifact missing or startup failed), returns
(None, "rules_v1") so the caller falls back gracefully to rule-based
recommendations. The API never errors out because ML is unavailable.
"""
import logging

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import PriceHistory
from app.ml_runtime.model_loader import get_model

logger = logging.getLogger(__name__)

NAN_FILL = -1.0  # sentinel value for missing features (matches train.py)


# ---------------------------------------------------------------------------
# Feature computation — mirrors build_features.py _compute_features()
# ---------------------------------------------------------------------------

def _rolling_drop_count(prices: pd.Series, window: str) -> pd.Series:
    is_drop = (prices.diff() < 0).astype(float)
    return is_drop.rolling(window, min_periods=1).sum()


def _days_since_last_drop(g: pd.DataFrame) -> np.ndarray:
    result = np.full(len(g), np.nan)
    drop_mask = g["price"].diff() < 0
    for i in range(1, len(g)):
        prior_drops = g.index[:i][drop_mask.iloc[:i]]
        if len(prior_drops) > 0:
            delta = g["observed_at"].iloc[i] - g["observed_at"].iloc[prior_drops[-1]]
            result[i] = delta.total_seconds() / 86400
    return result


def _compute_features(history_rows: list[PriceHistory]) -> pd.DataFrame:
    """
    Given a product's price history (sorted ascending by time), compute the
    same feature set that build_features.py produces. Returns a DataFrame
    with one row per observation. The caller takes the last row.
    """
    records = [
        {"observed_at": row.observed_at, "price": float(row.price)}
        for row in history_rows
    ]
    g = pd.DataFrame(records).sort_values("observed_at").reset_index(drop=True)
    g = g.set_index("observed_at")
    prices = g["price"]

    g["price_avg_7d"]  = prices.rolling("7D",  min_periods=1).mean()
    g["price_avg_14d"] = prices.rolling("14D", min_periods=1).mean()
    g["price_avg_30d"] = prices.rolling("30D", min_periods=1).mean()
    g["price_min_7d"]  = prices.rolling("7D",  min_periods=1).min()
    g["price_min_30d"] = prices.rolling("30D", min_periods=1).min()
    g["price_max_7d"]  = prices.rolling("7D",  min_periods=1).max()
    g["price_max_30d"] = prices.rolling("30D", min_periods=1).max()
    g["price_std_7d"]  = prices.rolling("7D",  min_periods=2).std()
    g["price_std_30d"] = prices.rolling("30D", min_periods=2).std()

    def safe_pct(a, b):
        return (a - b) / b.replace(0, np.nan)

    g["price_vs_avg_30d_pct"] = safe_pct(prices, g["price_avg_30d"])
    g["price_vs_min_30d_pct"] = safe_pct(prices, g["price_min_30d"])
    g["price_vs_max_30d_pct"] = safe_pct(prices, g["price_max_30d"])
    g["price_change_prev"]     = prices.diff()
    g["price_change_prev_pct"] = prices.pct_change()
    g["num_drops_7d"]          = _rolling_drop_count(prices, "7D")
    g["num_drops_30d"]         = _rolling_drop_count(prices, "30D")

    g = g.reset_index()
    g["days_since_last_drop"] = _days_since_last_drop(g)
    g["observation_count"]    = range(1, len(g) + 1)
    g["day_of_week"]          = g["observed_at"].dt.dayofweek
    g["is_weekend"]           = g["day_of_week"].isin([5, 6]).astype(int)
    g["month"]                = g["observed_at"].dt.month
    g["week_of_year"]         = g["observed_at"].dt.isocalendar().week.astype(int)

    return g


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def predict_drop_probability(
    db: Session,
    product_id: str,
) -> tuple[float | None, str]:
    """
    Returns (drop_probability_7d, model_version).

    drop_probability_7d is None when:
    - the model is not loaded (returns "rules_v1")
    - the product has fewer than 2 observations (too little history)
    - feature computation fails unexpectedly

    The caller should fall back to rule-based recommendations when None is returned.
    """
    loaded = get_model()
    if not loaded:
        return None, "rules_v1"

    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.observed_at)
        .all()
    )

    if len(history) < 2:
        logger.debug("Insufficient history for ML inference on product %s (%d obs)", product_id, len(history))
        return None, loaded.model_version

    try:
        feature_df = _compute_features(history)
    except Exception:
        logger.exception("Feature computation failed for product %s", product_id)
        return None, loaded.model_version

    last_row = feature_df.iloc[[-1]]

    # Build feature vector with exactly the columns the model was trained on.
    # Any column the model expects but that we couldn't compute gets NAN_FILL.
    X = pd.DataFrame(index=last_row.index)
    for col in loaded.feature_columns:
        X[col] = last_row[col].values if col in last_row.columns else NAN_FILL
    X = X.fillna(NAN_FILL)

    try:
        prob = float(loaded.model.predict_proba(X)[0][1])
    except Exception:
        logger.exception("Model inference failed for product %s", product_id)
        return None, loaded.model_version

    logger.debug("Prediction for product %s: %.3f (model=%s)", product_id, prob, loaded.model_version)
    return prob, loaded.model_version
