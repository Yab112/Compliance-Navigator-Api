from fastapi import APIRouter

from api.v1 import assistant, auth, catalog, organizations, chat, feedback, guday, notifications, offices, payments, processes, providers, reputation, roadmaps, support
from api.v1.admin import assistant as admin_assistant, dashboard, organizations as admin_organizations, jobs, marketplace as admin_marketplace, rag, references, settings as admin_settings, tasks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(processes.router)
api_router.include_router(roadmaps.router)
api_router.include_router(offices.router)
api_router.include_router(chat.router)
api_router.include_router(catalog.router)
api_router.include_router(guday.router)
api_router.include_router(providers.router)
api_router.include_router(admin_marketplace.router)
api_router.include_router(feedback.router)
api_router.include_router(notifications.router)
api_router.include_router(organizations.router)
api_router.include_router(admin_organizations.router)
api_router.include_router(dashboard.router)
api_router.include_router(jobs.router)
api_router.include_router(tasks.router)
api_router.include_router(references.router)
api_router.include_router(rag.router)
api_router.include_router(assistant.router)
api_router.include_router(admin_assistant.router)
api_router.include_router(support.router)
api_router.include_router(payments.router)
api_router.include_router(reputation.router)
api_router.include_router(support.admin_router)
api_router.include_router(admin_settings.router)
