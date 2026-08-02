FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Kolkata

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install chromium --with-deps

COPY . .

EXPOSE 8000

# PORT is set by Railway (default 3000); falls back to 8000 for docker-compose.
# seed is idempotent and only fills sample jobs for the dashboard.
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
