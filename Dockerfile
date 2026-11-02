FROM python:3.11-slim
WORKDIR /srv/app
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt && useradd --create-home --uid 10001 appuser
COPY app ./app
COPY config.py ./
COPY static ./static
USER appuser
ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8000') + '/api/v1/health', timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --ws-ping-interval 20 --ws-ping-timeout 20 --ws-max-size 32768 --ws-max-queue 8"]
