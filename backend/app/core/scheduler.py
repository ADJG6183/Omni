"""
Background job scheduler for Omni.

Uses APScheduler (v3.x) to run periodic maintenance tasks alongside the
FastAPI process.

Phase 2 jobs
------------
stale_product_check  — every 4 hours
    Log products whose most recent price observation is older than
    STALE_THRESHOLD_HOURS.  In Phase 5 this becomes the trigger for
    alert re-checks.

db_health_report     — daily at midnight
    Log a DB stats snapshot (product count, observation count, date range)
    useful for monitoring how much real data is accumulating.

Safety notes
------------
- Both jobs catch all exceptions so a failing job never takes down the API.
- The scheduler is skipped entirely when API_ENV == "testing" so unit and
  integration tests are unaffected.
- max_instances=1 prevents a slow job from stacking concurrent copies of
  itself.
- coalesce=True collapses multiple missed firings into a single run after
  the server recovers from downtime.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db.models import PriceHistory, Product
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

STALE_THRESHOLD_HOURS = 4

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _stale_product_check() -> None:
    """Log products that have not received a new observation recently."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_THRESHOLD_HOURS)

        stale_rows = (
            db.query(
                Product.id,
                Product.title,
                func.max(PriceHistory.observed_at).label("last_seen"),
            )
            .join(PriceHistory, PriceHistory.product_id == Product.id)
            .group_by(Product.id, Product.title)
            .having(func.max(PriceHistory.observed_at) < cutoff)
            .all()
        )

        if stale_rows:
            logger.info(
                "Stale product check: %d product(s) not seen in >%dh",
                len(stale_rows),
                STALE_THRESHOLD_HOURS,
            )
            for row in stale_rows:
                hours_ago = (
                    datetime.now(timezone.utc) - row.last_seen
                ).total_seconds() / 3600
                logger.debug(
                    "  Stale: %.50s (last seen %.1fh ago)", row.title, hours_ago
                )
        else:
            logger.info(
                "Stale product check: all products have recent observations."
            )
    except Exception:
        logger.exception("Stale product check job failed")
    finally:
        db.close()


def _db_health_report() -> None:
    """Log a daily snapshot of DB stats to track data collection progress."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        product_count = db.query(func.count(Product.id)).scalar() or 0
        price_count = db.query(func.count(PriceHistory.id)).scalar() or 0
        oldest = db.query(func.min(PriceHistory.observed_at)).scalar()
        newest = db.query(func.max(PriceHistory.observed_at)).scalar()

        # Break down by source (seed vs extension)
        source_counts = (
            db.query(PriceHistory.source, func.count(PriceHistory.id))
            .group_by(PriceHistory.source)
            .all()
        )
        source_summary = ", ".join(f"{s}={c}" for s, c in source_counts)

        logger.info(
            "DB health: %d products | %d price rows (%s) | range %s → %s",
            product_count,
            price_count,
            source_summary or "no data",
            oldest.date() if oldest else "n/a",
            newest.date() if newest else "n/a",
        )
    except Exception:
        logger.exception("DB health report job failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    global _scheduler

    if settings.api_env == "testing":
        logger.info("Scheduler disabled in test mode.")
        return

    _scheduler = BackgroundScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers=2)},
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )

    _scheduler.add_job(
        _stale_product_check,
        trigger="interval",
        hours=STALE_THRESHOLD_HOURS,
        id="stale_product_check",
        name="Stale product check",
    )

    _scheduler.add_job(
        _db_health_report,
        trigger="cron",
        hour=0,
        minute=0,
        id="db_health_report",
        name="Daily DB health report",
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — stale check every %dh, daily health report at midnight.",
        STALE_THRESHOLD_HOURS,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
