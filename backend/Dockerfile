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

# Embed the build identity into the artefact, before it is switched to a
# non-root user, so the image carries the same provenance contract as a real
# deployment.
#
# Without this the image has no app/build_revision.txt, read_embedded_revision()
# raises ProvenanceError, and /health answers 503 "Build identity unavailable"
# forever - which is the health endpoint correctly refusing to name a commit it
# was never told. The container then failed its own smoke test and the preflight
# Docker gate. Neither was visible while both gates reported tee's exit status.
#
# Off-platform this writes the development marker rather than a SHA, because a
# local or CI image is not a deployment and must be distinguishable from one by
# inspection. On Vercel the same script records the real commit SHA, because
# vercel.json declares it as the buildCommand. The script exits non-zero rather
# than shipping an artefact with no identity, so this cannot pass silently.
RUN python scripts/embed_build_revision.py

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
