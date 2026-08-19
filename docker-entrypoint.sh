#!/bin/sh
# TejaratYar entrypoint — makes the mounted data volume writable by the app
# user (uid 1000), then starts the server. Runs as the "user" user; if a fresh
# Docker volume is mounted at /data it may be owned by root, so we normalize it
# before gunicorn starts.

set -e

# If running as root (e.g. someone overrides USER), take ownership.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${DATA_DIR:-/data}/jobs" "${DATA_DIR:-/data}/outputs"
  chown -R user:user "${DATA_DIR:-/data}"
  exec su user -c 'gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 300 --access-logfile - --error-logfile -'
fi

# Normal path: running as uid 1000. Ensure dirs exist and are writable.
mkdir -p "${DATA_DIR:-/data}/jobs" "${DATA_DIR:-/data}/outputs"

exec gunicorn app:app \
  --bind 0.0.0.0:${PORT} \
  --workers 1 \
  --threads 8 \
  --timeout 300 \
  --access-logfile - \
  --error-logfile -
