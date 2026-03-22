FROM python:3.12.10-slim AS base

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app/prospectio_api_mcp

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

FROM base AS app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

COPY prospectio_api_mcp ./prospectio_api_mcp

RUN addgroup --gid 1001 --system appgroup && \
    adduser --uid 1001 --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 7002

CMD ["uv", "run", "fastapi", "run", "prospectio_api_mcp/main.py", "--host", "0.0.0.0", "--port", "7002"]
