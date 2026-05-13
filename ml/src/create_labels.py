"""
create_labels.py

Creates the binary classification target for the 7-day price-drop model.

Definition
----------
For each price observation at time T:
    future_min_price_7d  = min price observed in (T, T + 7 days]
    price_drop_pct_7d    = (price_at_T - future_min_price_7d) / price_at_T
    label_drop_7d        = 1 if price_drop_pct_7d >= DROP_THRESHOLD else 0

An observation is "labelable" only if there is at least one future
observation within the 7-day window.  Observations too close to the end of
the collected history are marked is_labelable=False and excluded from
training — they cannot be correctly labeled and must not be imputed.

Leakage note
------------
Future price data is ONLY used to create the label column.
Never merge label columns back into the feature matrix as a feature.
Merge only on the observation ID after both files are generated separately.

Usage
-----
    cd /path/to/PriceDropOS
    python ml/src/create_labels.py
    python ml/src/create_labels.py --threshold 0.03 --output ml/data/labels.csv
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db_utils import get_engine

logger = logging.getLogger(__name__)

DROP_THRESHOLD   = 0.05   # 5% price drop within 7 days = positive label
LABEL_WINDOW_DAYS = 7


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_price_history(engine) -> pd.DataFrame:
    query = text("""
        SELECT ph.id, ph.product_id, ph.price::float AS price, ph.observed_at
        FROM price_history ph
        ORDER BY ph.product_id, ph.observed_at
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
    return df


# ---------------------------------------------------------------------------
# Label creation
# ---------------------------------------------------------------------------

def create_labels(df: pd.DataFrame, threshold: float = DROP_THRESHOLD) -> pd.DataFrame:
    """
    Return a DataFrame with one row per price observation and columns:
        id, product_id, observed_at, price,
        label_drop_7d, future_min_price_7d, price_drop_pct_7d, is_labelable
    """
    rows = []

    for product_id, group in df.groupby("product_id"):
        g = group.sort_values("observed_at").reset_index(drop=True)
        last_obs = g["observed_at"].iloc[-1]

        for _, row in g.iterrows():
            t = row["observed_at"]
            price = row["price"]

            if price <= 0:
                # Guard: zero/negative price means bad data — skip labeling
                logger.warning(
                    "Skipping observation %s for product %s: non-positive price %.2f",
                    row["id"], product_id, price,
                )
                continue

            window_end = t + pd.Timedelta(days=LABEL_WINDOW_DAYS)

            # Is there any future data within the 7-day window?
            future = g[(g["observed_at"] > t) & (g["observed_at"] <= window_end)]
            is_labelable = not future.empty

            if not is_labelable:
                rows.append({
                    "id": row["id"],
                    "product_id": product_id,
                    "observed_at": t,
                    "price": price,
                    "label_drop_7d": np.nan,
                    "future_min_price_7d": np.nan,
                    "price_drop_pct_7d": np.nan,
                    "is_labelable": False,
                })
                continue

            future_min = future["price"].min()
            drop_pct   = (price - future_min) / price
            label      = 1 if drop_pct >= threshold else 0

            rows.append({
                "id": row["id"],
                "product_id": product_id,
                "observed_at": t,
                "price": price,
                "label_drop_7d": label,
                "future_min_price_7d": future_min,
                "price_drop_pct_7d": round(drop_pct, 6),
                "is_labelable": True,
            })

    result = pd.DataFrame(rows)

    labelable = result[result["is_labelable"]]
    if labelable.empty:
        logger.warning(
            "No labelable observations found. "
            "The dataset may not have enough future price data yet."
        )
        return result

    pos_rate = labelable["label_drop_7d"].mean()
    logger.info(
        "Labels: %d labelable | positive rate %.1f%% (threshold=%.0f%%)",
        len(labelable), pos_rate * 100, threshold * 100,
    )

    if pos_rate < 0.05:
        logger.warning(
            "Positive class is very sparse (%.1f%%). "
            "Consider lowering --threshold or collecting more volatile product data.",
            pos_rate * 100,
        )
    elif pos_rate > 0.65:
        logger.warning(
            "Positive class is very large (%.1f%%). "
            "This may indicate a data quality issue or a threshold that is too low.",
            pos_rate * 100,
        )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Create 7-day price drop labels")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DROP_THRESHOLD,
        help=f"Minimum fractional price drop to label as positive (default: {DROP_THRESHOLD})",
    )
    parser.add_argument("--output", default="ml/data/labels.csv")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    df = load_price_history(engine)

    if df.empty:
        logger.error("No price data found. Run:  cd backend && python -m app.db.seed")
        sys.exit(1)

    df_labels = create_labels(df, threshold=args.threshold)
    df_labels.to_csv(output_path, index=False)
    logger.info("Saved to %s", output_path)

    labelable = df_labels[df_labels["is_labelable"]]
    if not labelable.empty:
        n_pos = int(labelable["label_drop_7d"].sum())
        n_neg = int((labelable["label_drop_7d"] == 0).sum())
        print(f"\nLabel summary  (threshold = {args.threshold:.0%})")
        print(f"  Total observations   : {len(df_labels)}")
        print(f"  Labelable            : {len(labelable)}  ({len(labelable)/len(df_labels):.0%})")
        print(f"  Not labelable        : {(~df_labels['is_labelable']).sum()}  (no future window)")
        print(f"  Positive (drop ≥{args.threshold:.0%}) : {n_pos}  ({n_pos/len(labelable):.1%})")
        print(f"  Negative             : {n_neg}  ({n_neg/len(labelable):.1%})")


if __name__ == "__main__":
    main()
