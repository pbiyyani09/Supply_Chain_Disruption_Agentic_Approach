# ── Builder stage ─────────────────────────────────────────────────────────────
# Python 3.13: the project uses PEP 695 generics (schemas.py) and requires >=3.13.
FROM python:3.13-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy installed packages from builder (slim image, no build toolchain).
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source (.dockerignore keeps the context small).
COPY . .

# Data dir for the SQLite databases (main + vector store).
RUN mkdir -p /data

ENV DATABASE_URL=sqlite:////data/chainwatch.db
ENV VECTOR_DB_PATH=/data/chainwatch_vectors.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 8501

# Default: run the API server (compose overrides for the dashboard service).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
