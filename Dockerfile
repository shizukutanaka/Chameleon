# Multi-stage build for minimal production image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Copy requirements
COPY requirements.txt requirements_optional.txt ./

# Install build dependencies and compile Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev && \
    pip wheel --no-cache-dir --wheel-dir /wheels \
        -r requirements.txt \
        -r requirements_optional.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHAMELEON_HOME=/app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 chameleon && \
    mkdir -p /app /data && \
    chown -R chameleon:chameleon /app /data

# Set working directory
WORKDIR /app

# Copy wheels from builder
COPY --from=builder /wheels /wheels

# Install Python packages
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
        psutil pyyaml numpy && \
    rm -rf /wheels

# Copy application code
COPY --chown=chameleon:chameleon *.py ./
COPY --chown=chameleon:chameleon examples/ ./examples/
COPY --chown=chameleon:chameleon scripts/ ./scripts/
COPY --chown=chameleon:chameleon tests/ ./tests/

# Switch to non-root user
USER chameleon

# Volume for data
VOLUME ["/data"]

# Default command
CMD ["python", "chameleon.py", "--help"]