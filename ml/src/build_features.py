"""
build_features.py

Generates a point-in-time ML feature matrix from price_history.

Each output row represents one price observation with features derived
exclusively from data at or before that observation's timestamp.
This is the core leakage-prevention guarantee.

Key concepts
------------
Point-in-time correctness:
    For an observation at time T, every rolling window (7D, 30D) only
    includes observations where observed_at <= T.  No future prices leak
    into features.  pandas time-based rolling() naturally enforces this
    when the DataFrame is sorted by time.

Irregular spacing:
    Observations are NOT uniformly spaced — a product might have a row on
    day 1, then nothing until day 9.  We use pandas time-based rolling
    windows ('7D', '30D') rather than row-count windows so the window
    covers the correct calendar duration regardless of spacing.

NaN handling:
    Rolling stats on early rows (e.g. only 1 observation in the last 7 days)
    will produce NaN for std/pct_change.  These are left as NaN — the ML
    model should either impute them or use algorithms that handle NaN
    (e.g. LightGBM, XGBoost with enable_categorical).

Usage
-----
    cd /path/to/PriceDropOS
    python ml/src/build_features.py
    python ml/src/build_features.py --output ml/data/features.csv
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db_utils import get_engine, load_price_history

logger = logging.getLogger(__name__)

MIN_OBSERVATIONS = 2   # Products with fewer rows are skipped


# ---------------------------------------------------------------------------
# Per-product feature computation
# ---------------------------------------------------------------------------

def _rolling_drop_count(prices: pd.Series, window: str) -> pd.Series:
    """Count how many times the price decreased within a backward time window."""
    # A decrease is any observation where price < previous observation
    is_drop = (prices.diff() < 0).astype(float)
    return is_drop.rolling(window, min_periods=1).sum()


def _days_since_last_drop(df: pd.DataFrame) -> pd.Series:
    """
    For each row, return the number of days since the most recent prior
    observation where the price decreased.  Returns NaN if no prior drop exists.
    """
    result = np.full(len(df), np.nan)
    drop_mask = df["price"].diff() < 0

    for i in range(1, len(df)):
        prior_drops = df.index[:i][drop_mask.iloc[:i]]
        if len(prior_drops) > 0:
            delta = df["observed_at"].iloc[i] - df["observed_at"].iloc[prior_drops[-1]]
            result[i] = delta.total_seconds() / 86400

    return pd.Series(result, index=df.index)


def _compute_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all features for a single product's sorted price history.
    Called once per product inside build_features().
    """
    g = group.sort_values("observed_at").copy().reset_index(drop=True)
    g = g.set_index("observed_at")
    prices = g["price"]

    # --- Rolling price stats (time-based windows, no leakage) ---
    g["price_avg_7d"]  = prices.rolling("7D",  min_periods=1).mean()
    g["price_avg_14d"] = prices.rolling("14D", min_periods=1).mean()
    g["price_avg_30d"] = prices.rolling("30D", min_periods=1).mean()
    g["price_min_7d"]  = prices.rolling("7D",  min_periods=1).min()
    g["price_min_30d"] = prices.rolling("30D", min_periods=1).min()
    g["price_max_7d"]  = prices.rolling("7D",  min_periods=1).max()
    g["price_max_30d"] = prices.rolling("30D", min_periods=1).max()
    # std requires at least 2 values — NaN for single-observation windows
    g["price_std_7d"]  = prices.rolling("7D",  min_periods=2).std()
    g["price_std_30d"] = prices.rolling("30D", min_periods=2).std()

    # --- Current price vs rolling stats ---
    # Safe division: avoid divide-by-zero if a stat is somehow 0
    def safe_pct(a, b):
        return (a - b) / b.replace(0, np.nan)

    g["price_vs_avg_30d_pct"] = safe_pct(prices, g["price_avg_30d"])
    g["price_vs_min_30d_pct"] = safe_pct(prices, g["price_min_30d"])
    g["price_vs_max_30d_pct"] = safe_pct(prices, g["price_max_30d"])

    # --- Price change from previous observation ---
    g["price_change_prev"]     = prices.diff()
    g["price_change_prev_pct"] = prices.pct_change()

    # --- Drop counts ---
    g["num_drops_7d"]  = _rolling_drop_count(prices, "7D")
    g["num_drops_30d"] = _rolling_drop_count(prices, "30D")

    # --- Days since last drop (requires reset_index for row-level logic) ---
    g = g.reset_index()
    g["days_since_last_drop"] = _days_since_last_drop(g)

    # --- History depth ---
    g["observation_count"] = range(1, len(g) + 1)

    # --- Time features ---
    g["day_of_week"] = g["observed_at"].dt.dayofweek   # 0=Monday, 6=Sunday
    g["is_weekend"]  = g["day_of_week"].isin([5, 6]).astype(int)
    g["month"]       = g["observed_at"].dt.month
    g["week_of_year"] = g["observed_at"].dt.isocalendar().week.astype(int)

    return g


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    obs_counts = df.groupby("product_id").size()
    valid_ids  = obs_counts[obs_counts >= MIN_OBSERVATIONS].index
    skipped    = len(obs_counts) - len(valid_ids)

    if skipped:
        logger.warning(
            "Skipping %d product(s) with fewer than %d observations.",
            skipped, MIN_OBSERVATIONS,
        )

    feature_frames = []
    for product_id, group in df[df["product_id"].isin(valid_ids)].groupby("product_id"):
        try:
            feature_frames.append(_compute_features(group))
        except Exception as exc:
            logger.warning("Feature computation failed for %s: %s", product_id, exc)

    if not feature_frames:
        logger.error("No features produced — is the DB populated? Run the seeder first.")
        return pd.DataFrame()

    result = pd.concat(feature_frames, ignore_index=True)
    feature_cols = [
        c for c in result.columns
        if c not in ("id", "product_id", "observed_at", "currency",
                     "source", "title", "brand", "category", "retailer")
    ]
    logger.info(
        "Feature matrix: %d rows × %d features | %d products",
        len(result), len(feature_cols), result["product_id"].nunique(),
    )
    return result


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Build ML feature matrix from price history")
    parser.add_argument("--output", default="ml/data/features.csv")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    df_raw = load_price_history(engine)
    logger.info(
        "Loaded %d observations across %d products from %d retailer(s).",
        len(df_raw), df_raw["product_id"].nunique(), df_raw["retailer"].nunique(),
    )

    if df_raw.empty:
        logger.error("No price data. Run:  cd backend && python -m app.db.seed")
        sys.exit(1)

    df_features = build_features(df_raw)
    if df_features.empty:
        sys.exit(1)

    df_features.to_csv(output_path, index=False)
    logger.info("Saved to %s", output_path)

    print(f"\nFeature matrix shape : {df_features.shape}")
    print(f"Products             : {df_features['product_id'].nunique()}")
    print(f"Retailers            : {sorted(df_features['retailer'].unique())}")
    print(f"Date range           : {df_features['observed_at'].min().date()} → "
          f"{df_features['observed_at'].max().date()}")

    nan_rates = df_features.isnull().mean().sort_values(ascending=False)
    nan_rates = nan_rates[nan_rates > 0]
    if not nan_rates.empty:
        print("\nNaN rates (expected for cold-start rows):")
        for col, rate in nan_rates.items():
            print(f"  {col:<35} {rate:.1%}")


if __name__ == "__main__":
    main()
