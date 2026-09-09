# ==============================================================================
# Smart Attendance System - Containerized Environment
# Provides FastAPI, Uvicorn, WebSockets, InsightFace & Computer Vision Runtime
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr for real-time logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for OpenCV, InsightFace, Pillow and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and datasets
COPY . .

# Ensure outputs and data directories exist
RUN mkdir -p /app/outputs /app/data/students /app/data/incoming_photos

# Set PYTHONPATH so internal packages (app, vision, scripts) resolve properly
ENV PYTHONPATH=/app/backend:/app

# Expose Web Interface & WebSocket port
EXPOSE 8000

# Health check to ensure the backend is responsive
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default execution: Launch FastAPI Backend with Uvicorn
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
