FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAG_UPLOAD_DIR=/data/cargas

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --create-home rag \
    && mkdir -p /data/cargas \
    && chown -R rag:rag /data

COPY --chown=rag:rag . .
USER rag
EXPOSE 8080

CMD ["sh", "-c", "exec python -m uvicorn api_http:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --no-proxy-headers"]
