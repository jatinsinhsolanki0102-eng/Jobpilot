#!/bin/sh
set -e

# Create tables (create_all) + optional sample jobs for the dashboard.
python -m app.seed

# PORT is set by Railway; fall back to 8000 for docker-compose.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
