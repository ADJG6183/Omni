"""
Database connection helper for ML scripts.

Reads DATABASE_URL from the .env file at the project root.
Usage:
    from src.db_utils import get_engine
    engine = get_engine()
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ml/src/ → ml/ → project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_engine() -> Engine:
    load_dotenv(_PROJECT_ROOT / ".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Ensure a .env file exists at the project root with DATABASE_URL defined."
        )

    return create_engine(database_url, pool_pre_ping=True)


def load_price_history(engine: Engine) -> pd.DataFrame:
    """
    Load all price history with product and retailer metadata.

    Shared by build_features.py and create_labels.py so the DB query
    is defined once. Scripts that only need a subset of columns can
    drop them after loading.
    """
    query = text("""
        SELECT
            ph.id,
            ph.product_id,
            ph.price::float          AS price,
            ph.currency,
            ph.availability,
            ph.observed_at,
            ph.source,
            p.title,
            p.brand,
            p.category,
            r.name                   AS retailer
        FROM price_history ph
        JOIN products  p ON ph.product_id = p.id
        JOIN retailers r ON p.retailer_id  = r.id
        ORDER BY ph.product_id, ph.observed_at
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
    return df
