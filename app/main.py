"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.admin.routes import router as admin_router
from app.api.chat import router as chat_router
from app.api.classify import router as classify_router
from app.api.tickets import router as ticket_router
from app.api.voice import router as voice_router
from app.config import get_settings
from app.db import check_database_connection
from app.logging_config import configure_logging
from app.schemas import HealthResponse
from app.web.routes import router as web_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Multilingual citizen grievance intake, routing and status tracking.",
    debug=settings.debug,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_host_list,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(ticket_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(classify_router)
app.include_router(web_router)
app.include_router(voice_router)


@app.middleware("http")
async def security_headers_and_body_limit(request: Request, call_next):
    """Apply baseline browser security headers and reject oversized requests."""

    content_length = request.headers.get("content-length")
    max_bytes = settings.max_request_body_mb * 1024 * 1024
    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
        return JSONResponse(
            status_code=413,
            content={"error": "request_too_large", "message": "Request body is too large."},
        )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "microphone=(self)")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a consistent response for invalid request data."""

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": jsonable_encoder(exc.errors()),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors without exposing internal details to citizens."""

    logger.exception("Unhandled request error at %s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Return a small service description."""

    return {"service": settings.app_name, "status": "ok"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return service and database health without exposing secrets."""

    database_name = "postgresql" if settings.database_url.startswith("postgres") else "sqlite"
    database_ok = check_database_connection()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        service=settings.app_name,
        environment=settings.app_env,
        database=database_name,
        database_status="ok" if database_ok else "unavailable",
    )
