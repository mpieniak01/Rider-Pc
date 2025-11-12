# Rider-PC Dockerfile
# Multi-stage build for optimized production image

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY pc_client/ ./pc_client/
COPY config/ ./config/
COPY web/ ./web/
COPY run.sh .

# Create data directory for cache
RUN mkdir -p /app/data

# Download AI models (optional, comment out for faster builds)
# RUN python -c "import whisper; whisper.load_model('base')"
# RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=5)" || exit 1

# Run the application
CMD ["python", "-m", "pc_client.main"]
