<<<<<<< HEAD
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

# System dependencies needed for building native extensions
=======
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

<<<<<<< HEAD
# Copy only the dependency manifest first for layer caching
COPY pyproject.toml ./

# Install Python dependencies in builder stage
RUN pip install --upgrade pip --timeout 120 --retries 5 \
    && pip install --timeout 120 --retries 5 ".[dev]"

# ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime system deps only (no build-essential)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
=======
# Copy application files BEFORE installation
COPY pyproject.toml ./
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh

<<<<<<< HEAD
# Create non-root user
RUN adduser --disabled-password --gecos "" --home /app appuser \
    && chown -R appuser:appuser /app \
=======
# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install "." \
    && apt-get purge -y --auto-remove build-essential

# Create non-root user
RUN adduser --disabled-password --gecos "" --home /app appuser

# Set permissions
RUN chown -R appuser:appuser /app \
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
    && chmod +x /app/entrypoint.sh

EXPOSE 8080

USER appuser

CMD ["./entrypoint.sh"]