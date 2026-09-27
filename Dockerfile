# syntax=docker/dockerfile:1

# Multi-stage build: dependencies are resolved in a builder stage and only the
# resulting site-packages are copied into the slim runtime image, so build
# tooling and pip cache never ship to production.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

# curl backs the HEALTHCHECK below; the rest of the runtime is stdlib-only.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user: the app never needs root.
RUN groupadd --system app \
    && useradd --system --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY pyproject.toml ./
COPY theteam/ ./theteam/

# Writable locations for state, backups and audit logs.
RUN mkdir -p /app/state /app/backups /app/.omp/theteam \
    && chown -R app:app /app

USER app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THETEAM_METRICS_PORT=8000 \
    THETEAM_PROJECT_ROOT=/app

EXPOSE 8000

# The health endpoint is the same one Prometheus scrapes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${THETEAM_METRICS_PORT}/health" || exit 1

CMD ["python", "-m", "theteam.cli", "serve"]
