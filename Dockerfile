# Chameleon Audio Tool — container image
# Multi-stage build. Ships the CLI (main.py) and, when the [api] extra is
# installed, the REST API server (api_server.py, via `main.py server`).

# Build stage
FROM python:3.11-slim AS builder

ARG BUILD_DATE
ARG VERSION=1.0.0
ARG GIT_COMMIT

LABEL org.opencontainers.image.title="Chameleon Audio Tool"
LABEL org.opencontainers.image.description="Stdlib-only WAV processing CLI with an optional REST API"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/shizukutanaka/Chameleon"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libc6-dev make pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml setup.py ./
COPY main.py core.py security_validator.py advanced_validation.py \
     plugin_system.py midi_analysis.py api_server.py batch_automation.py \
     spectral_editor.py spectral_utils.py audio_restoration.py \
     mastering_chain.py performance_optimizer.py ux_improvements.py \
     bs1770_loudness.py ./
COPY README.md ./

# [audio] unlocks noise reduction/format conversion/--master/streaming;
# [api] unlocks `main.py server`. Both are optional at the pip level (the
# default `pip install -e .` stays stdlib-only per CHARTER §3) but bundled
# here since a container image is meant to be self-contained.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[audio,api]"

# Production stage
FROM python:3.11-slim AS production

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl tini gosu tzdata && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

RUN groupadd -r -g 1000 chameleon && \
    useradd -r -u 1000 -g chameleon -d /app -s /bin/bash chameleon

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=chameleon:chameleon /app /app

WORKDIR /app

RUN mkdir -p /app/data /app/logs && \
    chown -R chameleon:chameleon /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHAMELEON_PORT=8000

# Real, code-read configuration only (see README.md's "Environment Variables"
# section) — no fictional config file baked in here. Set at `docker run` time:
#   CHAMELEON_TRUSTED_ROOTS, CHAMELEON_MAX_FILE_SIZE, CHAMELEON_MAX_WORKERS,
#   CHAMELEON_API_KEY, CHAMELEON_ALLOWED_ORIGINS, CHAMELEON_ALLOWED_HOSTS

RUN cat > /app/docker-entrypoint.sh << 'EOF'
#!/bin/bash
set -e

# Switch to the unprivileged user if started as root.
if [ "$(id -u)" = "0" ]; then
    exec gosu chameleon "$0" "$@"
fi

python3 -c "import main, core" || {
    echo "Startup check failed: main.py/core.py did not import cleanly" >&2
    exit 1
}

case "$1" in
    "server"|"")
        exec python3 main.py server --host 0.0.0.0 --port "${CHAMELEON_PORT:-8000}"
        ;;
    "cli")
        shift
        exec python3 main.py "$@"
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

RUN cat > /app/health-check.sh << 'EOF'
#!/bin/bash
curl -f -s "http://localhost:${CHAMELEON_PORT:-8000}/health" > /dev/null || exit 1
EOF

RUN chmod +x /app/health-check.sh

# Real port only — 9090 (a "metrics" port) had no corresponding endpoint
# anywhere in api_server.py.
EXPOSE 8000

VOLUME ["/app/data", "/app/logs"]

# Only meaningful for the default "server" CMD; a container run with `cli`
# or `shell` will report unhealthy since nothing serves /health — that's
# expected, not a bug, for those modes.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD /app/health-check.sh

USER chameleon

ENTRYPOINT ["tini", "--", "/app/docker-entrypoint.sh"]
CMD ["server"]
