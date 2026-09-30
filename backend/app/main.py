import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, jobs
from app.core.config import settings

# Configure basic logging using standard logging library
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("workout_form_coach")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Starting %s in [%s] environment", settings.APP_NAME, settings.APP_ENV)
    logger.info("Configured CORS allowed origin: %s", settings.FRONTEND_URL)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title="Workout Form Coach API",
    lifespan=lifespan,
)

# CORS middleware configuration
cors_origins = {settings.FRONTEND_URL, settings.FRONTEND_URL.rstrip("/")}
if settings.FRONTEND_URL.startswith("https://"):
    cors_origins.add(settings.FRONTEND_URL.replace("https://", "http://", 1))

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler to avoid leaking internal details in responses."""
    logger.error(
        "Unhandled error processing %s %s: %s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Root endpoint
@app.get("/", summary="Root Endpoint")
def read_root() -> dict[str, str]:
    """Return welcome message from Workout Form Coach API."""
    return {"message": "Workout Form Coach API"}


# Mount routes
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth")
app.include_router(jobs.router, prefix=f"{settings.API_V1_PREFIX}/jobs")
