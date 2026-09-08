import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.api import api_router
from app.websockets import ws_router, ws_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    ws_manager.set_event_loop(loop)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Smart Attendance and Facial Recognition Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard (React, Vite, Next.js or external clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API and WebSocket routes
app.include_router(api_router)
app.include_router(ws_router)

# Mount static files and web interfaces
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/dashboard", tags=["Web Interface"])
def serve_dashboard():
    """Serves the real-time instructor classroom attendance dashboard."""
    dashboard_html = STATIC_DIR / "dashboard.html"
    if dashboard_html.exists():
        return FileResponse(str(dashboard_html))
    return JSONResponse(status_code=404, content={"message": "Dashboard template not found."})

@app.get("/enroll", tags=["Web Interface"])
def serve_enrollment_station():
    """Serves the interactive student face capture and enrollment web station."""
    enroll_html = STATIC_DIR / "enroll.html"
    if enroll_html.exists():
        return FileResponse(str(enroll_html))
    return JSONResponse(status_code=404, content={"message": "Enrollment page template not found."})

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for the backend service."""
    return {"status": "ok", "environment": settings.ENVIRONMENT, "database": settings.DATABASE_URL.split("///")[-1]}

@app.get("/", tags=["Root"])
def root():
    return {
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "dashboard_url": "/dashboard",
        "enroll_station_url": "/enroll",
        "api_prefix": "/api"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
