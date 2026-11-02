FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-api.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements-api.txt \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/models && chown appuser:appuser /app/models
COPY app ./app
COPY config.py ./
COPY static ./static
ENV HOST=0.0.0.0 PORT=8000 MODEL_PATH=/app/models LOG_LEVEL=info
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --log-level ${LOG_LEVEL:-info} --ws-ping-interval 20 --ws-ping-timeout 20 --ws-max-size 32768 --ws-max-queue 8"]
