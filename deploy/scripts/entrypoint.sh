#!/bin/bash
# Chameleon Audio Processing Framework - Production Entrypoint Script
# Production-grade container initialization with comprehensive health checks

set -euo pipefail

# Configuration
export CHAMELEON_HOME="/app"
export CHAMELEON_CONFIG_PATH="${CHAMELEON_CONFIG_PATH:-/app/config/config.yaml}"
export CHAMELEON_LOG_LEVEL="${CHAMELEON_LOG_LEVEL:-WARNING}"
export PYTHONPATH="${CHAMELEON_HOME}:${PYTHONPATH:-}"

# Logging functions
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $*" >&2
}

log_warn() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $*" >&2
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
}

# Error handling
trap 'log_error "Unexpected error occurred. Exiting..."; exit 1' ERR

# Signal handling for graceful shutdown
shutdown_handler() {
    log_info "Received shutdown signal. Cleaning up..."
    
    # Kill background processes
    if [ -n "${HEALTH_SERVER_PID:-}" ]; then
        kill "${HEALTH_SERVER_PID}" 2>/dev/null || true
    fi
    
    # Clean up temporary files
    find /app/temp -type f -name "*.tmp" -delete 2>/dev/null || true
    
    log_info "Cleanup completed. Shutting down."
    exit 0
}

trap shutdown_handler SIGTERM SIGINT

# System requirements check
check_system_requirements() {
    log_info "Checking system requirements..."
    
    # Check required commands
    local required_commands=("python3" "ffmpeg" "sox")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log_error "Required command '$cmd' not found"
            return 1
        fi
    done
    
    # Check Python version
    local python_version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local min_version="3.8"
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_error "Python version ${python_version} is too old. Minimum required: ${min_version}"
        return 1
    fi
    
    log_info "Python version: ${python_version} (OK)"
    
    # Check available memory
    local available_memory
    if available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}'); then
        if [ "$available_memory" -lt 128 ]; then
            log_warn "Low available memory: ${available_memory}MB. Recommended: >256MB"
        fi
        log_info "Available memory: ${available_memory}MB"
    fi
    
    # Check disk space
    local available_space
    if available_space=$(df /app | awk 'NR==2 {print $4}'); then
        available_space=$((available_space / 1024))  # Convert to MB
        if [ "$available_space" -lt 100 ]; then
            log_warn "Low disk space: ${available_space}MB. Recommended: >500MB"
        fi
        log_info "Available disk space: ${available_space}MB"
    fi
}

# Directory setup
setup_directories() {
    log_info "Setting up directories..."
    
    local directories=("/app/logs" "/app/temp" "/app/output" "/app/profiles" "/app/backups")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "Created directory: $dir"
        fi
        
        # Ensure proper permissions
        chmod 755 "$dir"
    done
    
    # Clean up old temporary files
    find /app/temp -type f -mtime +1 -delete 2>/dev/null || true
    
    # Ensure log directory is writable
    if [ ! -w "/app/logs" ]; then
        log_error "Log directory /app/logs is not writable"
        return 1
    fi
}

# Configuration validation
validate_configuration() {
    log_info "Validating configuration..."
    
    if [ ! -f "$CHAMELEON_CONFIG_PATH" ]; then
        log_error "Configuration file not found: $CHAMELEON_CONFIG_PATH"
        return 1
    fi
    
    # Test configuration loading
    if ! python3 -c "
import yaml
import sys
try:
    with open('$CHAMELEON_CONFIG_PATH', 'r') as f:
        config = yaml.safe_load(f)
    if not config:
        raise ValueError('Empty configuration')
    if 'app' not in config:
        raise ValueError('Missing app section')
    print('Configuration validation: OK')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    sys.exit(1)
" 2>&1; then
        log_info "Configuration validation passed"
    else
        log_error "Configuration validation failed"
        return 1
    fi
}

# Python dependencies check
check_python_dependencies() {
    log_info "Checking Python dependencies..."
    
    # Essential dependencies
    local essential_deps=("yaml" "struct" "wave" "os" "sys")
    
    for dep in "${essential_deps[@]}"; do
        if ! python3 -c "import $dep" 2>/dev/null; then
            log_error "Essential Python module '$dep' not available"
            return 1
        fi
    done
    
    # Optional dependencies (warn if missing)
    local optional_deps=("psutil" "numpy" "soundfile" "sounddevice")
    local missing_optional=()
    
    for dep in "${optional_deps[@]}"; do
        if ! python3 -c "import $dep" 2>/dev/null; then
            missing_optional+=("$dep")
        fi
    done
    
    if [ ${#missing_optional[@]} -gt 0 ]; then
        log_warn "Optional dependencies missing: ${missing_optional[*]}"
        log_warn "Some features may be limited"
    fi
    
    log_info "Python dependencies check completed"
}

# Health check server
start_health_server() {
    log_info "Starting health check server..."
    
    # Simple health check server using Python
    python3 -c "
import http.server
import socketserver
import json
import sys
import threading
import signal
from datetime import datetime

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_data = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'chameleon-audio',
                'version': '2.0.0'
            }
            
            self.wfile.write(json.dumps(health_data).encode())
        elif self.path == '/ready':
            # Readiness check
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            ready_data = {
                'ready': True,
                'timestamp': datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(ready_data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_server():
    port = 8080
    handler = HealthHandler
    
    try:
        with socketserver.TCPServer(('', port), handler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print(f'Health server error: {e}', file=sys.stderr)

if __name__ == '__main__':
    start_server()
" &
    
    HEALTH_SERVER_PID=$!
    sleep 2
    
    # Verify health server is running
    if kill -0 $HEALTH_SERVER_PID 2>/dev/null; then
        log_info "Health check server started (PID: $HEALTH_SERVER_PID)"
    else
        log_warn "Health check server failed to start"
    fi
}

# Application initialization
initialize_application() {
    log_info "Initializing Chameleon application..."
    
    # Test basic functionality
    if ! python3 -c "
import sys
sys.path.insert(0, '/app')

try:
    # Test core imports
    from core import generate_sine_wave, write_wav_file
    
    # Test basic functionality
    audio_data = generate_sine_wave(440, 0.1, 44100)
    if not audio_data:
        raise Exception('Failed to generate test audio')
    
    print('Application initialization: OK')
except Exception as e:
    print(f'Application initialization failed: {e}')
    sys.exit(1)
" 2>&1; then
        log_info "Application initialization successful"
    else
        log_error "Application initialization failed"
        return 1
    fi
}

# Main initialization sequence
main() {
    log_info "Starting Chameleon Audio Processing Framework..."
    log_info "Version: 2.0.0"
    log_info "Environment: Production"
    log_info "Configuration: $CHAMELEON_CONFIG_PATH"
    
    # Run initialization checks
    check_system_requirements || exit 1
    setup_directories || exit 1
    validate_configuration || exit 1
    check_python_dependencies || exit 1
    initialize_application || exit 1
    
    # Start health check server
    start_health_server
    
    log_info "Initialization completed successfully"
    
    # If no arguments provided, start interactive mode
    if [ $# -eq 0 ]; then
        log_info "Starting in interactive mode..."
        log_info "Use 'chameleon --help' for available commands"
        exec /bin/bash
    fi
    
    # Execute the provided command
    log_info "Executing command: $*"
    exec "$@"
}

# Run main function with all arguments
main "$@"