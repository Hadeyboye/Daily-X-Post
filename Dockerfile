# daily_x_posts - Production Dockerfile
# Optimized for Novita AI Sandbox (E2B-compatible) and local GPU/CPU
# Python 3.12 slim + all runtime deps for agents, UI, multimodal, browser fallback

FROM python:3.12-slim-bookworm

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create app user (security)
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (needed for browser fallback posting)
RUN playwright install chromium --with-deps

# Copy entire source
COPY . .

# Create runtime dirs
RUN mkdir -p /app/data /app/outputs /app/chroma_db /app/logs && \
    chown -R appuser:appuser /app

USER appuser

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    # Prevent protobuf 4.x descriptor errors with ChromaDB on Cloud / containers
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Expose Streamlit + optional FastAPI later
EXPOSE 8501

# Healthcheck (simple)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: Run Streamlit dashboard (production entry)
# For full autonomy headless: docker run ... python main.py --autonomy
CMD ["streamlit", "run", "main.py", "--server.headless", "true", "--server.port", "8501"]
