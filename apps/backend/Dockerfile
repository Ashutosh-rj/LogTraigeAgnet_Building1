FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application files BEFORE installation
COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install "." \
    && apt-get purge -y --auto-remove build-essential

# Create non-root user
RUN adduser --disabled-password --gecos "" --home /app appuser

# Set permissions
RUN chown -R appuser:appuser /app \
    && chmod +x /app/entrypoint.sh

EXPOSE 8080

USER appuser

CMD ["./entrypoint.sh"]