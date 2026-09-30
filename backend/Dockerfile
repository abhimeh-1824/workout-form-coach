# ==============================================================================
# Workout Form Coach - Unified Backend Service Dockerfile
# Runs FastAPI Uvicorn Server & Video Processing Worker in a single container
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MEDIA_ROOT=media

WORKDIR /app

# Install native Linux shared libraries required by OpenCV, MediaPipe, and video tools
# - libxcb1: provides libxcb.so.1 (resolves OpenCV / GUI import issue)
# - libgl1: provides libGL.so.1 (OpenGL rendering support)
# - libglib2.0-0: provides libgthread-2.0.so.0 / libglib-2.0.so.0
# - ffmpeg: hardware/software video decoding and audio extraction
# - curl: container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    libgl1 \
    libegl1 \
    libgles2 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Alembic database migrations and configuration
COPY alembic.ini .
COPY alembic/ alembic/

# Copy application code and pose estimation assets
COPY app/ app/

# Copy entrypoint script and set executable permissions
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create local media directory for video storage
RUN mkdir -p media/jobs media/processed media/temp

# Default port (Render overrides this with dynamic $PORT)
EXPOSE 8000

# Start both FastAPI API server and Background Queue Worker
ENTRYPOINT ["/bin/bash", "./entrypoint.sh"]
