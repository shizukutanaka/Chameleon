# Chameleon Audio System - Deployment Guide

## Quick Deployment

### Development Environment (5 minutes)

```bash
# Clone and setup
git clone https://github.com/shizukutanaka/Chameleon.git
cd Chameleon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Test
python validation_test.py
```

### Docker Deployment (10 minutes)

```bash
# Build
docker build -t chameleon:latest .

# Run
docker run -v /audio:/data chameleon:latest analyze /data/file.wav
```

### Production Server (30 minutes)

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.10 python3-pip python3-venv

# Create application user
sudo useradd -r -s /bin/false chameleon

# Setup application
sudo mkdir -p /opt/chameleon
sudo chown chameleon:chameleon /opt/chameleon
cd /opt/chameleon

# Deploy application
sudo -u chameleon git clone https://github.com/shizukutanaka/Chameleon.git .
sudo -u chameleon python3 -m venv .venv
sudo -u chameleon .venv/bin/pip install -r requirements.txt

# Create systemd service
sudo cat > /etc/systemd/system/chameleon.service <<EOF
[Unit]
Description=Chameleon Audio Processing Service
After=network.target

[Service]
Type=simple
User=chameleon
WorkingDirectory=/opt/chameleon
Environment="PATH=/opt/chameleon/.venv/bin"
ExecStart=/opt/chameleon/.venv/bin/python main.py server --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable chameleon
sudo systemctl start chameleon
```

## Security Configuration

### Trusted Directories

Create `/opt/chameleon/.env`:
```bash
CHAMELEON_TRUSTED_ROOTS=/audio/workspace:/secure/files
CHAMELEON_LOG_DIR=/var/log/chameleon
CHAMELEON_MAX_FILE_SIZE=524288000
```

### TLS/HTTPS Setup

```bash
# Generate self-signed certificate (development only)
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout /etc/ssl/private/chameleon.key \
  -out /etc/ssl/certs/chameleon.crt \
  -days 365

# For production, use Let's Encrypt
sudo certbot certonly --standalone -d audio.example.com

# Update service to use TLS
# Add to systemd service:
# ExecStart=/opt/chameleon/.venv/bin/python main.py server \
#   --host 0.0.0.0 --port 8443 \
#   --cert /etc/letsencrypt/live/audio.example.com/fullchain.pem \
#   --key /etc/letsencrypt/live/audio.example.com/privkey.pem
```

### Firewall Configuration

```bash
# Allow API access
sudo ufw allow 8080/tcp
sudo ufw allow 8443/tcp

# Restrict SSH
sudo ufw allow from 192.168.1.0/24 to any port 22

# Enable firewall
sudo ufw enable
```

## Kubernetes Deployment

### Apply Manifests

```bash
# Create namespace
kubectl create namespace chameleon

# Create secrets
kubectl create secret generic chameleon-secrets \
  --from-literal=api-key=$(openssl rand -hex 32) \
  -n chameleon

# Apply configuration
kubectl apply -f k8s-deployment.yaml -n chameleon
```

### Scale Deployment

```bash
# Manual scaling
kubectl scale deployment chameleon --replicas=5 -n chameleon

# Autoscaling
kubectl autoscale deployment chameleon \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n chameleon
```

## Monitoring Setup

### What the server exposes

There is **no Prometheus exporter and no `/metrics` endpoint**. Earlier versions
of this guide configured a scrape job against `/metrics` and a Grafana dashboard
querying `chameleon_processing_duration_seconds`, `chameleon_queue_length` and
`chameleon_errors_total`; the API exports none of those, so the scrape returned
404 and every panel stayed empty.

Monitor the endpoints that exist:

```bash
# Liveness. Returns 200 with uptime_seconds and a timestamp; no auth required.
curl -sf http://localhost:8080/health

# Runtime counters (requires an authenticated session).
curl -sf -H "X-API-Key: $CHAMELEON_API_KEY" http://localhost:8080/system/status
```

`/health` is what the container's own `HEALTHCHECK` and the Kubernetes
liveness, readiness and startup probes all use, so anything that can poll an
HTTP endpoint is enough for uptime alerting.

### Logs

Two files, both plain text and both rotated by the application:

```bash
tail -f ~/.chameleon/logs/chameleon.log      # application log
tail -f ~/.chameleon/logs/api-audit.log      # per-request audit trail
```

Set `CHAMELEON_LOG_DIR` to relocate them. The audit trail is also readable over
HTTP at `GET /audit/log?limit=100` for an authenticated session.

## Backup Strategy

### Automated Backups

```bash
#!/bin/bash
# /opt/chameleon/backup.sh

BACKUP_DIR=/backup/chameleon
DATE=$(date +%Y%m%d_%H%M%S)

# Backup configuration
mkdir -p $BACKUP_DIR/config
cp -r /opt/chameleon/.env $BACKUP_DIR/config/

# Backup secrets
mkdir -p $BACKUP_DIR/secrets
sudo -u chameleon cp -r /home/chameleon/.chameleon/secrets $BACKUP_DIR/

# Backup logs
mkdir -p $BACKUP_DIR/logs
cp -r /var/log/chameleon $BACKUP_DIR/logs/

# Create archive
tar -czf $BACKUP_DIR/chameleon_$DATE.tar.gz -C $BACKUP_DIR .

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

Add to crontab:
```bash
0 2 * * * /opt/chameleon/backup.sh
```

## Performance Tuning

### System Limits

Edit `/etc/security/limits.conf`:
```
chameleon soft nofile 65536
chameleon hard nofile 65536
chameleon soft nproc 4096
chameleon hard nproc 4096
```

### Application Tuning

Edit `/opt/chameleon/.env`:
```bash
CHAMELEON_MAX_WORKERS=8
CHAMELEON_CHUNK_SIZE=131072
CHAMELEON_PERFORMANCE_MODE=fast
CHAMELEON_PARALLEL=true
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status chameleon

# View logs
sudo journalctl -u chameleon -n 50 --no-pager

# Check permissions
sudo -u chameleon ls -la /opt/chameleon

# Test manual start
sudo -u chameleon /opt/chameleon/.venv/bin/python main.py server
```

### High Memory Usage

```bash
# Monitor memory
watch -n 1 'ps aux | grep chameleon'

# Reduce workers
export CHAMELEON_MAX_WORKERS=2

# Enable streaming mode for large files
export CHAMELEON_PERFORMANCE_MODE=safe
```

### Connection Refused

```bash
# Check if port is listening
sudo netstat -tlnp | grep 8080

# Check firewall
sudo ufw status

# Test locally
curl http://localhost:8080/health
```

## Disaster Recovery

### Recovery Procedure

1. Stop service:
```bash
sudo systemctl stop chameleon
```

2. Restore from backup:
```bash
LATEST_BACKUP=$(ls -t /backup/chameleon/*.tar.gz | head -1)
tar -xzf $LATEST_BACKUP -C /opt/chameleon/
```

3. Verify integrity:
```bash
cd /opt/chameleon
python validation_test.py
```

4. Restart service:
```bash
sudo systemctl start chameleon
sudo systemctl status chameleon
```

### Rollback Procedure

```bash
# Keep previous version
sudo cp -r /opt/chameleon /opt/chameleon.backup

# Rollback
sudo systemctl stop chameleon
sudo rm -rf /opt/chameleon
sudo mv /opt/chameleon.backup /opt/chameleon
sudo systemctl start chameleon
```

## Maintenance

### Update Procedure

```bash
# Backup current version
sudo cp -r /opt/chameleon /opt/chameleon.$(date +%Y%m%d)

# Pull updates
cd /opt/chameleon
sudo -u chameleon git fetch origin
sudo -u chameleon git checkout main
sudo -u chameleon git pull origin main

# Update dependencies
sudo -u chameleon .venv/bin/pip install --upgrade -r requirements.txt

# Run tests
sudo -u chameleon .venv/bin/python validation_test.py

# Restart service
sudo systemctl restart chameleon
```

### Health Checks

```bash
# Automated health check script
#!/bin/bash
# /opt/chameleon/healthcheck.sh

ENDPOINT="http://localhost:8080/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $ENDPOINT)

if [ $RESPONSE -eq 200 ]; then
    exit 0
else
    echo "Health check failed: HTTP $RESPONSE"
    exit 1
fi
```

Add to cron:
```bash
*/5 * * * * /opt/chameleon/healthcheck.sh || systemctl restart chameleon
```

---

**Version:** 1.0.0
**Last Updated:** 2025-10-05
