from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from database.database import initiate_database

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
    initiate_database()
    yield
    print("App shutdown complete.")


app = FastAPI(
    lifespan=lifespan,
    description="Compliance Navigator API.",
    contact={"email": "eshetieyabibal@gmail.com", "tel": "0962473792"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to Compliance Navigator API."}


app.include_router(api_router)
