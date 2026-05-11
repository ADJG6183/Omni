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
    yield


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
