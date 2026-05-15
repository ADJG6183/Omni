"""
Model loader — loads the trained price-drop model once at FastAPI startup.

Why module-level state?
-----------------------
The model object lives as a module-level variable (_loaded). Every part of
the backend that needs predictions calls get_model(), which returns the same
in-memory object. Loading from disk on every request would add 200–500ms of
disk I/O latency to every API call. Since sklearn models are read-only after
training, multiple concurrent requests can safely share the same object.

Model location
--------------
The loader looks for artifacts in ml/artifacts/ relative to the project root.
If no artifact is found, inference is disabled and the API falls back to
rule-based recommendations — requests still succeed, just without ML.

Version tracking
----------------
load_model() also registers the loaded model in the model_registry DB table
so predictions can be traced back to the exact model version that generated them.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ml/artifacts/ relative to project root (backend/app/ml_runtime/ → up 4 levels)
_ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "ml" / "artifacts"
_VERSION = "v1"


@dataclass
class LoadedModel:
    model: Any              # sklearn estimator (Pipeline or direct classifier)
    feature_columns: list[str]
    model_version: str      # e.g. "price_drop_random_forest_v1"
    model_type: str         # "random_forest" | "logistic_regression"
    artifact_path: str


_loaded: LoadedModel | None = None


def load_model(model_type: str = "random_forest") -> None:
    """
    Load model artifact from ml/artifacts/ into module-level state.
    Called once during FastAPI lifespan startup.

    If the artifact file doesn't exist (e.g. train.py has never been run),
    logs a warning and leaves _loaded as None. The API will serve rule-based
    recommendations until a model is trained and the server restarts.
    """
    global _loaded

    artifact_path = _ARTIFACTS_DIR / f"price_drop_{model_type}_{_VERSION}.pkl"
    columns_path  = _ARTIFACTS_DIR / f"feature_columns_{_VERSION}.json"

    if not artifact_path.exists():
        logger.warning(
            "Model artifact not found at %s. "
            "Run: python ml/src/train.py — then restart the server. "
            "Falling back to rule-based recommendations.",
            artifact_path,
        )
        return

    if not columns_path.exists():
        logger.warning("feature_columns_%s.json not found. Cannot load model safely.", _VERSION)
        return

    try:
        model = joblib.load(artifact_path)
        with open(columns_path) as f:
            feature_columns = json.load(f)

        _loaded = LoadedModel(
            model=model,
            feature_columns=feature_columns,
            model_version=f"price_drop_{model_type}_{_VERSION}",
            model_type=model_type,
            artifact_path=str(artifact_path),
        )
        logger.info(
            "ML model loaded: %s | %d features | artifact: %s",
            _loaded.model_version,
            len(feature_columns),
            artifact_path.name,
        )
    except Exception:
        logger.exception("Failed to load model artifact — falling back to rules.")
        _loaded = None


def get_model() -> LoadedModel | None:
    return _loaded


def is_model_available() -> bool:
    return _loaded is not None


def register_model_in_db(db: Session) -> None:
    """
    Write the currently loaded model into the model_registry table.

    Called once from main.py after load_model() succeeds. Deactivates any
    previously active model first, then upserts the current version as active.
    model_version has a UNIQUE constraint, so we update the existing row rather
    than inserting a duplicate when the server restarts with the same artifact.
    """
    if _loaded is None:
        return

    from app.db.models import ModelRegistry

    metrics: dict | None = None
    metrics_path = _ARTIFACTS_DIR / f"metrics_{_VERSION}.json"
    if metrics_path.exists():
        try:
            with open(metrics_path) as f:
                all_metrics = json.load(f)
            metrics = all_metrics.get(_loaded.model_type)
        except Exception:
            logger.warning("Could not read metrics file — registry row will have no metrics.")

    try:
        # Deactivate any currently active model
        db.query(ModelRegistry).filter(ModelRegistry.is_active.is_(True)).update(
            {"is_active": False}, synchronize_session=False
        )

        # Upsert: update existing row if version already registered, else insert
        existing = db.query(ModelRegistry).filter(
            ModelRegistry.model_version == _loaded.model_version
        ).first()

        if existing:
            existing.is_active = True
            existing.metrics = metrics
            existing.artifact_path = _loaded.artifact_path
        else:
            db.add(ModelRegistry(
                model_name=f"price_drop_{_loaded.model_type}",
                model_version=_loaded.model_version,
                model_type=_loaded.model_type,
                artifact_path=_loaded.artifact_path,
                feature_columns=_loaded.feature_columns,
                metrics=metrics,
                is_active=True,
            ))

        db.commit()
        logger.info("Model registered in model_registry: %s (active)", _loaded.model_version)

    except Exception:
        db.rollback()
        logger.exception("Failed to register model in DB — inference will still work.")
