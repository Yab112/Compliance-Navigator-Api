FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv \
    && useradd --create-home --uid 10001 app

WORKDIR /app

# Dependencies first so code changes do not reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# .dockerignore keeps .env, logs, uploads and tests out of the image
COPY --chown=app:app . .
# models_store is not in git: it is filled from a local copy at build time or kept on the models volume
RUN mkdir -p uploads logs .cache models_store && chown -R app:app uploads logs .cache models_store

USER app

# Production defaults; override at run time. LOG_FILE empty = log to stdout only.
ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8080 \
    WEB_CONCURRENCY=1 \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    LOG_LEVEL=INFO \
    LOG_FILE=""

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('PORT', '8080'), timeout=4)"

CMD ["python", "main.py"]
