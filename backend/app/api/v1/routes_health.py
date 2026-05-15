from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ml_runtime.model_loader import get_model

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Returns the operational status of the API, database, and ML model.

    DB check: runs a trivial query. If the DB is unreachable this returns
    db.status='error' rather than crashing — callers can treat a degraded
    health response as an alert without getting a 500.

    ML check: reports whether the model artifact was loaded at startup.
    status='rules_only' means inference is falling back to rule-based
    recommendations — not a crash, but a signal that train.py needs to run.
    """
    # DB ping
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # ML status
    loaded = get_model()
    if loaded:
        ml = {
            "status": "ok",
            "model_version": loaded.model_version,
            "model_type": loaded.model_type,
            "feature_count": len(loaded.feature_columns),
        }
    else:
        ml = {
            "status": "rules_only",
            "model_version": None,
            "model_type": None,
            "feature_count": 0,
        }

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "service": "omni-api",
        "version": "0.1.0",
        "db": {"status": db_status},
        "ml": ml,
    }
