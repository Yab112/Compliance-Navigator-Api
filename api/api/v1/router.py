from fastapi import APIRouter

from api.v1 import auth, chat, offices, processes, roadmaps, users
from api.v1.admin import jobs, rag, references, tasks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(processes.router)
api_router.include_router(roadmaps.router)
api_router.include_router(offices.router)
api_router.include_router(chat.router)
api_router.include_router(jobs.router)
api_router.include_router(tasks.router)
api_router.include_router(references.router)
api_router.include_router(rag.router)
