# Chameleon Audio Processing Framework - Production Dockerfile
# Multi-stage build for optimal security and size

FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_ENV=production
ARG BUILD_VERSION=2.0.0

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libc6-dev \
    libffi-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create build user (security best practice)
RUN useradd --create-home --shell /bin/bash build

# Set working directory
WORKDIR /build

# Copy requirements first (better caching)
COPY requirements.txt .
COPY setup.py .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy source code
COPY . .

# Build wheel for production
RUN python setup.py bdist_wheel

# Production stage
FROM python:3.11-slim

# Set production environment
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BUILD_ENV=production
ENV CHAMELEON_CONFIG_PATH=/app/config/config.yaml

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio processing libraries
    ffmpeg \
    sox \
    libsndfile1 \
    libasound2-dev \
    # System utilities
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application user (security best practice)
RUN groupadd --gid 1001 chameleon \
    && useradd --uid 1001 --gid chameleon --shell /bin/bash --create-home chameleon

# Create application directories
RUN mkdir -p /app/config /app/logs /app/temp /app/output /app/profiles \
    && chown -R chameleon:chameleon /app

# Copy built application from builder stage
COPY --from=builder /build/dist/*.whl /tmp/
COPY --from=builder /root/.local /app/.local

# Copy configuration and scripts
COPY deploy/config/production.yaml /app/config/config.yaml
COPY deploy/scripts/entrypoint.sh /app/entrypoint.sh
COPY deploy/scripts/healthcheck.sh /app/healthcheck.sh

# Install application
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/*.whl

# Set proper permissions
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh \
    && chown -R chameleon:chameleon /app

# Switch to application user
USER chameleon

# Set working directory
WORKDIR /app

# Expose port for health checks
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# Default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["chameleon", "--config", "/app/config/config.yaml"]