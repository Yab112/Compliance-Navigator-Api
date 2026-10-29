from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from config.config import settings
from database.database import initiate_database
from services.ai_admin import load_overrides
from services.approvals import PendingApproval
from services.db import run_migrations
from core.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "production" and (
        settings.secret_key.startswith("change-me") or len(settings.secret_key) < 32
    ):
        raise RuntimeError("Set a strong SECRET_KEY (32+ random characters) before running in production")
    if settings.auth_cookie_samesite == "none" and not settings.auth_cookie_secure:
        raise RuntimeError("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true")
    initiate_database()
    run_migrations()
    load_overrides()
    # Test IDs from the Fayda sandbox never count once real Fayda is switched on
    from services.id_verification import retire_sandbox_verifications

    retire_sandbox_verifications()
    yield
    print("App shutdown complete.")


# The interactive API docs are for developers only; production does not publish them
_docs_off = settings.environment == "production"

app = FastAPI(
    lifespan=lifespan,
    docs_url=None if _docs_off else "/docs",
    redoc_url=None if _docs_off else "/redoc",
    openapi_url=None if _docs_off else "/openapi.json",
    description="Compliance Navigator API.",
    contact={"email": "eshetieyabibal@gmail.com", "tel": "0962473792"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PendingApproval)
async def pending_approval(request: Request, exc: PendingApproval):
    """A risky staff action was stored for a second person to approve instead of running now."""
    return JSONResponse(status_code=202, content={"message": "approval_required",
                                                  "payload": {"approval": jsonable_encoder(exc.request)}})


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to Compliance Navigator API."}


app.include_router(api_router)

# Agent profile photos only, ID documents live in uploads/private (admin endpoint)
PUBLIC_UPLOADS = Path("uploads/public")
PUBLIC_UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/public", StaticFiles(directory=PUBLIC_UPLOADS), name="public-uploads")


@app.middleware("http")
async def harden_public_uploads(request, call_next):
    """Uploaded files are never sniffed or run as pages on the API origin, whatever they contain."""
    response = await call_next(request)
    if request.url.path.startswith("/uploads/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; sandbox"
        if not response.headers.get("content-type", "").startswith("image/"):
            response.headers["Content-Disposition"] = "attachment"
    return response
