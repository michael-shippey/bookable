#!/bin/sh
# Production start-up: apply any pending database migrations, then run the server.
# Hosts that tell us which port to use set $PORT; locally it falls back to 8000.
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
