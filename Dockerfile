# Chameleon Audio Tool - Enterprise Production Docker Image
# Multi-stage build for optimal security and performance

# Build stage
FROM python:3.11-slim AS builder

# Set build metadata
ARG BUILD_DATE
ARG VERSION=2.0.0
ARG GIT_COMMIT

LABEL org.opencontainers.image.title="Chameleon Audio Tool - Enterprise Edition"
LABEL org.opencontainers.image.description="National-level audio processing with military-grade security"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.licenses="MIT"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libc6-dev make pkg-config git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy and install application
COPY . .
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim AS production

# Install runtime dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl tini gosu tzdata && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

# Create application user
RUN groupadd -r -g 1000 chameleon && \
    useradd -r -u 1000 -g chameleon -d /app -s /bin/bash chameleon

# Copy Python environment and application
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=chameleon:chameleon /app /app

WORKDIR /app

# Create directories and set permissions
RUN mkdir -p /app/{data,logs,config,backups,temp} && \
    chown -R chameleon:chameleon /app

# Environment configuration
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHAMELEON_ENV=production \
    CHAMELEON_SECURITY_ENABLED=true \
    CHAMELEON_PARALLEL_PROCESSING=true

# Create production configuration
RUN cat > /app/config/production.yaml << 'EOF'
version: "2.0.0"
environment: "production"
security:
  enable_authentication: true
  enable_encryption: true
  enable_audit_logging: true
performance:
  enable_parallel_processing: true
  enable_simd: true
  max_concurrent_operations: 50
network:
  bind_address: "0.0.0.0"
  port: 8080
EOF

# Create entrypoint script
RUN cat > /app/docker-entrypoint.sh << 'EOF'
#!/bin/bash
set -e

echo "🎵 Chameleon Audio Tool - Enterprise Edition v2.0.0"
echo "🔒 National-level deployment ready"

# Switch to chameleon user if running as root
if [ "$(id -u)" = "0" ]; then
    exec gosu chameleon "$0" "$@"
fi

# Health checks
python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from chameleon_enhanced import EnhancedChameleon
    from enterprise_config import EnterpriseConfiguration
    config = EnterpriseConfiguration()
    app = EnhancedChameleon(config)
    print('✅ System initialization: OK')
except Exception as e:
    print(f'❌ Initialization failed: {e}')
    sys.exit(1)
"

# Start application
case "$1" in
    "server"|"")
        echo "🚀 Starting server mode on port ${CHAMELEON_PORT:-8080}"
        exec python3 chameleon_enhanced.py server --host 0.0.0.0 --port ${CHAMELEON_PORT:-8080}
        ;;
    "cli")
        shift
        exec python3 chameleon_enhanced.py "$@"
        ;;
    "shell")
        exec /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac
EOF

RUN chmod +x /app/docker-entrypoint.sh

# Health check script
RUN cat > /app/health-check.sh << 'EOF'
#!/bin/bash
curl -f -s "http://localhost:${CHAMELEON_PORT:-8080}/health" > /dev/null || exit 1
echo "Health check passed"
EOF

RUN chmod +x /app/health-check.sh

# Expose ports
EXPOSE 8080 9090

# Set volumes for persistent data
VOLUME ["/app/data", "/app/logs", "/app/config", "/app/backups"]

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/health-check.sh

USER chameleon

ENTRYPOINT ["tini", "--", "/app/docker-entrypoint.sh"]
CMD ["server"]