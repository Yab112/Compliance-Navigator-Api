from database.database import initiate_database
from routes.posts import PostRouter
from routes.users import UserRouter
from routes.auth import AuthRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    initiate_database()
    yield
    # You can also close DB connections here if needed
    print("App shutdown complete.")

app = FastAPI(lifespan=lifespan, description="Template for building FastAPI applications with Neo4j.", contact={"email": "samanidarix@gmail.com", "tel": "691439424"})


FORMAT = '%(levelname)s: %(asctime)-15s: %(filename)s: %(funcName)s: %(module)s: %(message)s'
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG, format=FORMAT)




@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to this fantastic app."}


app.include_router(UserRouter, tags=["Users"], prefix="/users")
app.include_router(AuthRouter, tags=["Auth"], prefix="/auth")
app.include_router(PostRouter, tags=["Posts"], prefix="/posts")