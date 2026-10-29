from contextlib import asynccontextmanager
import logging

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from config.config import settings
from database.database import initiate_database
from services.ai_admin import load_overrides
from services.db import run_migrations

FORMAT = (
    "%(levelname)s: %(asctime)-15s: %(filename)s: %(funcName)s: "
    "%(module)s: %(message)s"
)
logging.basicConfig(
    filename="example.log",
    encoding="utf-8",
    level=logging.DEBUG,
    format=FORMAT,
)


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
    yield
    print("App shutdown complete.")


app = FastAPI(
    lifespan=lifespan,
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


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to Compliance Navigator API."}


app.include_router(api_router)

# Agent profile photos only, ID documents live in uploads/private (admin endpoint)
PUBLIC_UPLOADS = Path("uploads/public")
PUBLIC_UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/public", StaticFiles(directory=PUBLIC_UPLOADS), name="public-uploads")
