FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /service
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

FROM python:3.12-slim
ENV PATH="/service/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 10001 service
WORKDIR /service
COPY --from=builder --chown=service:service /service/.venv ./.venv
COPY --chown=service:service app ./app
COPY --chown=service:service migrations ./migrations
COPY --chown=service:service alembic.ini ./
USER service
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
