# syntax=docker/dockerfile:1.7
# AKSHARA API and worker image (same codebase, decision D1).
#
# Behind a TLS-intercepting proxy, pass its CA without baking it into the image:
#   docker build --secret id=extra_ca,src=/path/to/ca.pem ...
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY infra/docker/with-ca.sh /usr/local/bin/with-ca
RUN --mount=type=secret,id=extra_ca,required=false with-ca pip install --no-cache-dir "uv>=0.9,<0.10"

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=extra_ca,required=false with-ca uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN --mount=type=secret,id=extra_ca,required=false with-ca uv sync --frozen --no-dev \
 && rm -f .env && useradd --system --uid 10001 --home /app akshara \
 && mkdir -p /data/blobs && chown -R akshara /data

ENV PATH="/app/.venv/bin:$PATH" AKSHARA_STORAGE_ROOT=/data/blobs
USER akshara
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
