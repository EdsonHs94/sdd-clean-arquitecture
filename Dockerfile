FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.12.22 \
    && useradd --create-home --uid 10001 app
COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/init_local_bucket.py ./scripts/init_local_bucket.py

FROM base AS local-s3
RUN uv sync --locked --only-group dev
USER app
EXPOSE 9000
CMD ["moto_server", "-H", "0.0.0.0", "-p", "9000"]

FROM base AS api
RUN uv sync --locked --no-dev
USER app
EXPOSE 8000
CMD ["uvicorn", "app.bootstrap:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
