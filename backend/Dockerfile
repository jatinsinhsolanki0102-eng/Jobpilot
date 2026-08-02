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
# start.sh runs the idempotent seed then starts uvicorn.
CMD ["sh", "/app/start.sh"]
