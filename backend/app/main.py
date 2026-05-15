from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import OmniError, omni_error_handler
from app.core.logging import configure_logging
from app.api.v1 import routes_health, routes_products


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    from app.core.scheduler import start_scheduler, stop_scheduler
    from app.ml_runtime.model_loader import load_model, register_model_in_db
    from app.db.session import SessionLocal
    load_model(model_type="random_forest")
    db = SessionLocal()
    try:
        register_model_in_db(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Omni API",
    description="AI Price Intelligence Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(OmniError, omni_error_handler)

app.include_router(routes_health.router, tags=["health"])
app.include_router(routes_products.router, prefix="/api/v1", tags=["products"])
