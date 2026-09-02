FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (libpq-dev for psycopg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chmod +x start.sh
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:${PORT:-8000}/health || exit 1

# Run the application via start.sh (validates SCHOLARZONE_DATABASE_URL before startup)
CMD ["bash", "start.sh"]
