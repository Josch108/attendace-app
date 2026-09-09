from fastapi import APIRouter
from app.api.students import router as students_router
from app.api.sessions import router as sessions_router
from app.api.events import router as events_router
from app.api.cameras import router as cameras_router

api_router = APIRouter(prefix="/api")
api_router.include_router(students_router)
api_router.include_router(sessions_router)
api_router.include_router(events_router)
api_router.include_router(cameras_router)

__all__ = ["api_router"]
