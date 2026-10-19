# ==============================================================================
# Vazus SuperGraph OS — Production Containerfile
# Base: Debian Bookworm Slim with Python 3.12
# ==============================================================================
FROM python:3.12-slim-bookworm

# Build arguments
ARG INSTALL_HEAVY_AI=false

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VAZUS_ROOT=/app \
    PYTHONPATH=/app \
    VAZUS_DB_PATH=/app/services/memory/vazus.db \
    PORT=8000 \
    HOST=0.0.0.0

# 1. Install base system dependencies and SQLite tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    libsqlite3-0 \
    ca-certificates \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 2. Create non-root system user (matching standard Linux desktop UID/GID 1000)
RUN groupadd -g 1000 vazus && \
    useradd -u 1000 -g vazus -m -s /bin/bash vazus

WORKDIR /app

# 3. Install Python dependencies
COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_HEAVY_AI" = "true" ]; then \
        pip install --no-cache-dir -r requirements-ai.txt; \
    fi && \
    apt-get purge -y gcc g++ make && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# 4. Create directory structure
RUN mkdir -p /app/data/logs /app/data/cache /app/data/models /app/services/memory /app/projects && \
    chown -R vazus:vazus /app

# 5. Copy application source
COPY --chown=vazus:vazus . /app

# 6. Setup entrypoint
COPY --chown=vazus:vazus docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 7. Switch to non-root user
USER vazus

# 8. Network ports (8000: API & Dashboard)
EXPOSE 8000

# 9. Healthcheck verification
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 10. Container execution
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "vazus_core/integrations/dashboard_server.py", "--host", "0.0.0.0", "--port", "8000"]
