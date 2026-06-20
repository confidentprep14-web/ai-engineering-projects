# Stage 1: build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target /build/deps -r requirements.txt

# Stage 2: runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy dependencies from builder (keeps image smaller than pip install at runtime)
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copy application code
COPY src/ src/

# Create data directory (will be overridden by volume mount)
RUN mkdir -p /data

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

# Health check: call /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
