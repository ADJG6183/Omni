"""
Database connection helper for ML scripts.

Reads DATABASE_URL from the .env file at the project root.
Usage:
    from src.db_utils import get_engine
    engine = get_engine()
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
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
