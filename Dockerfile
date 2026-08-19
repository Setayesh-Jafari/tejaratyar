# TejaratYar — permanent deployment image
# The app runs jobs in background threads, so gunicorn must stay single-worker
# (threads handle concurrency; in-memory JOBS dict lives in one process).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    APP_TIMEZONE=Asia/Tehran \
    DATA_DIR=/data \
    MAX_ACTIVE_JOBS=3 \
    JOB_TTL_HOURS=24

WORKDIR /app

# curl is used by the Docker HEALTHCHECK; gcc/musl not required (wheels only).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root runtime user. The data dir is prepared for the mounted volume.
RUN useradd --create-home --uid 1000 --shell /bin/bash user \
    && mkdir -p /data/jobs /data/outputs \
    && chown -R user:user /data /app

COPY --chown=user:user . .

# Ensure the mounted volume is writable by our uid (handles fresh named volumes).
RUN chmod +x docker-entrypoint.sh
USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
