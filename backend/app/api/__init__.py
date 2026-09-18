from fastapi import APIRouter
from app.api.students import router as students_router
from app.api.sessions import router as sessions_router
from app.api.events import router as events_router
from app.api.reports import router as reports_router
from app.api.auth import router as auth_router
from app.api.materias import router as materias_router

api_router = APIRouter(prefix="/api")
api_router.include_router(students_router)
api_router.include_router(sessions_router)
api_router.include_router(events_router)
api_router.include_router(reports_router)
api_router.include_router(auth_router)
api_router.include_router(materias_router)

__all__ = ["api_router"]
