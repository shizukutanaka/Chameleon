#!/bin/bash
# Chameleon Audio Processing Framework - Health Check Script
# Comprehensive health monitoring for production deployments

set -euo pipefail

# Configuration
HEALTH_CHECK_URL="http://localhost:8080/health"
READY_CHECK_URL="http://localhost:8080/ready"
TIMEOUT=10
MAX_ATTEMPTS=3
CHAMELEON_HOME="/app"
CHAMELEON_CONFIG_PATH="${CHAMELEON_CONFIG_PATH:-/app/config/config.yaml}"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_FAILURE=1
readonly EXIT_WARNING=2

# Logging functions
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [HEALTH] [INFO] $*" >&2
}

log_warn() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [HEALTH] [WARN] $*" >&2
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [HEALTH] [ERROR] $*" >&2
}

# Health check result structure
declare -A health_results=(
    ["http_health"]=0
    ["app_functionality"]=0
    ["resource_usage"]=0
    ["file_system"]=0
    ["dependencies"]=0
    ["configuration"]=0
)

# HTTP health check
check_http_health() {
    local attempt=1
    
    while [ $attempt -le $MAX_ATTEMPTS ]; do
        if curl -f -s --max-time $TIMEOUT "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
            log_info "HTTP health check passed (attempt $attempt)"
            return 0
        fi
        
        log_warn "HTTP health check failed (attempt $attempt/$MAX_ATTEMPTS)"
        ((attempt++))
        
        if [ $attempt -le $MAX_ATTEMPTS ]; then
            sleep 2
        fi
    done
    
    log_error "HTTP health check failed after $MAX_ATTEMPTS attempts"
    return 1
}

# Readiness check
check_readiness() {
    if curl -f -s --max-time $TIMEOUT "$READY_CHECK_URL" >/dev/null 2>&1; then
        log_info "Readiness check passed"
        return 0
    else
        log_error "Readiness check failed"
        return 1
    fi
}

# Application functionality check
check_app_functionality() {
    log_info "Testing application functionality..."
    
    # Test basic audio generation
    if ! python3 -c "
import sys
sys.path.insert(0, '$CHAMELEON_HOME')

try:
    from core import generate_sine_wave
    audio_data = generate_sine_wave(440, 0.01, 44100)  # Very short test
    if not audio_data or len(audio_data[0]) == 0:
        raise Exception('Invalid audio data generated')
    print('Application functionality: OK')
except ImportError as e:
    print(f'Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Functionality test failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_error "Application functionality test failed"
        return 1
    fi
    
    log_info "Application functionality check passed"
    return 0
}

# Resource usage check
check_resource_usage() {
    log_info "Checking resource usage..."
    
    local warnings=0
    
    # Check memory usage
    if command -v free >/dev/null 2>&1; then
        local memory_usage
        memory_usage=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
        
        if (( $(echo "$memory_usage > 90.0" | bc -l) )); then
            log_error "Critical memory usage: ${memory_usage}%"
            return 1
        elif (( $(echo "$memory_usage > 80.0" | bc -l) )); then
            log_warn "High memory usage: ${memory_usage}%"
            ((warnings++))
        fi
        
        log_info "Memory usage: ${memory_usage}%"
    fi
    
    # Check disk space
    local disk_usage
    if disk_usage=$(df /app | awk 'NR==2 {print $5}' | sed 's/%//'); then
        if [ "$disk_usage" -gt 95 ]; then
            log_error "Critical disk usage: ${disk_usage}%"
            return 1
        elif [ "$disk_usage" -gt 85 ]; then
            log_warn "High disk usage: ${disk_usage}%"
            ((warnings++))
        fi
        
        log_info "Disk usage: ${disk_usage}%"
    fi
    
    # Check CPU load (if available)
    if command -v uptime >/dev/null 2>&1; then
        local load_avg
        load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
        
        # Get number of CPUs
        local cpu_count
        cpu_count=$(nproc 2>/dev/null || echo "1")
        
        if (( $(echo "$load_avg > ($cpu_count * 2)" | bc -l) )); then
            log_warn "High CPU load: ${load_avg} (CPUs: ${cpu_count})"
            ((warnings++))
        fi
        
        log_info "Load average: ${load_avg} (CPUs: ${cpu_count})"
    fi
    
    # Check process count
    local process_count
    if process_count=$(ps aux | wc -l); then
        if [ "$process_count" -gt 500 ]; then
            log_warn "High process count: $process_count"
            ((warnings++))
        fi
        log_info "Process count: $process_count"
    fi
    
    if [ $warnings -gt 0 ]; then
        log_warn "Resource usage check completed with $warnings warnings"
        return 2  # Warning status
    fi
    
    log_info "Resource usage check passed"
    return 0
}

# File system health check
check_file_system() {
    log_info "Checking file system health..."
    
    local critical_dirs=("/app/logs" "/app/temp" "/app/output" "/app/config")
    local warnings=0
    
    for dir in "${critical_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_error "Critical directory missing: $dir"
            return 1
        fi
        
        if [ ! -r "$dir" ] || [ ! -w "$dir" ]; then
            log_error "Directory permissions incorrect: $dir"
            return 1
        fi
    done
    
    # Check configuration file
    if [ ! -f "$CHAMELEON_CONFIG_PATH" ]; then
        log_error "Configuration file missing: $CHAMELEON_CONFIG_PATH"
        return 1
    fi
    
    if [ ! -r "$CHAMELEON_CONFIG_PATH" ]; then
        log_error "Configuration file not readable: $CHAMELEON_CONFIG_PATH"
        return 1
    fi
    
    # Check log file rotation
    local log_dir="/app/logs"
    local old_logs
    old_logs=$(find "$log_dir" -name "*.log*" -mtime +30 2>/dev/null | wc -l || echo "0")
    
    if [ "$old_logs" -gt 100 ]; then
        log_warn "Many old log files found: $old_logs (consider cleanup)"
        ((warnings++))
    fi
    
    # Check temporary files
    local temp_files
    temp_files=$(find /app/temp -type f 2>/dev/null | wc -l || echo "0")
    
    if [ "$temp_files" -gt 100 ]; then
        log_warn "Many temporary files found: $temp_files (consider cleanup)"
        ((warnings++))
    fi
    
    if [ $warnings -gt 0 ]; then
        log_warn "File system check completed with $warnings warnings"
        return 2
    fi
    
    log_info "File system health check passed"
    return 0
}

# Dependencies check
check_dependencies() {
    log_info "Checking dependencies..."
    
    local critical_commands=("python3" "curl")
    local optional_commands=("ffmpeg" "sox")
    local warnings=0
    
    # Check critical commands
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log_error "Critical command missing: $cmd"
            return 1
        fi
    done
    
    # Check optional commands
    for cmd in "${optional_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log_warn "Optional command missing: $cmd (some features may be limited)"
            ((warnings++))
        fi
    done
    
    # Check Python modules
    local critical_modules=("sys" "os" "json" "yaml")
    local optional_modules=("psutil" "numpy" "soundfile")
    
    for module in "${critical_modules[@]}"; do
        if ! python3 -c "import $module" 2>/dev/null; then
            log_error "Critical Python module missing: $module"
            return 1
        fi
    done
    
    for module in "${optional_modules[@]}"; do
        if ! python3 -c "import $module" 2>/dev/null; then
            log_warn "Optional Python module missing: $module"
            ((warnings++))
        fi
    done
    
    if [ $warnings -gt 0 ]; then
        log_warn "Dependencies check completed with $warnings warnings"
        return 2
    fi
    
    log_info "Dependencies check passed"
    return 0
}

# Configuration validation
check_configuration() {
    log_info "Validating configuration..."
    
    # Test YAML parsing
    if ! python3 -c "
import yaml
import sys

try:
    with open('$CHAMELEON_CONFIG_PATH', 'r') as f:
        config = yaml.safe_load(f)
    
    # Basic structure validation
    required_sections = ['app', 'security', 'audio', 'paths', 'logging']
    missing_sections = []
    
    for section in required_sections:
        if section not in config:
            missing_sections.append(section)
    
    if missing_sections:
        raise ValueError(f'Missing configuration sections: {missing_sections}')
    
    # Validate critical settings
    if config['app'].get('environment') != 'production':
        print('Warning: Not running in production environment', file=sys.stderr)
    
    print('Configuration validation: OK')
    
except Exception as e:
    print(f'Configuration validation failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
        log_error "Configuration validation failed"
        return 1
    fi
    
    log_info "Configuration validation passed"
    return 0
}

# Run all health checks
run_health_checks() {
    log_info "Starting comprehensive health check..."
    
    local overall_status=0
    local warning_count=0
    
    # HTTP health check
    if check_http_health; then
        health_results["http_health"]=0
    else
        health_results["http_health"]=1
        overall_status=1
    fi
    
    # Application functionality
    if check_app_functionality; then
        health_results["app_functionality"]=0
    else
        health_results["app_functionality"]=1
        overall_status=1
    fi
    
    # Resource usage
    local resource_status
    resource_status=$(check_resource_usage; echo $?)
    health_results["resource_usage"]=$resource_status
    if [ $resource_status -eq 1 ]; then
        overall_status=1
    elif [ $resource_status -eq 2 ]; then
        ((warning_count++))
    fi
    
    # File system
    local fs_status
    fs_status=$(check_file_system; echo $?)
    health_results["file_system"]=$fs_status
    if [ $fs_status -eq 1 ]; then
        overall_status=1
    elif [ $fs_status -eq 2 ]; then
        ((warning_count++))
    fi
    
    # Dependencies
    local deps_status
    deps_status=$(check_dependencies; echo $?)
    health_results["dependencies"]=$deps_status
    if [ $deps_status -eq 1 ]; then
        overall_status=1
    elif [ $deps_status -eq 2 ]; then
        ((warning_count++))
    fi
    
    # Configuration
    if check_configuration; then
        health_results["configuration"]=0
    else
        health_results["configuration"]=1
        overall_status=1
    fi
    
    # Summary
    local passed=0
    local failed=0
    local warned=0
    
    for check in "${!health_results[@]}"; do
        case ${health_results[$check]} in
            0) ((passed++)) ;;
            1) ((failed++)) ;;
            2) ((warned++)) ;;
        esac
    done
    
    log_info "Health check summary:"
    log_info "  Passed: $passed"
    log_info "  Failed: $failed"
    log_info "  Warnings: $warned"
    
    if [ $overall_status -eq 0 ] && [ $warning_count -eq 0 ]; then
        log_info "All health checks passed - System is healthy"
        return $EXIT_SUCCESS
    elif [ $overall_status -eq 0 ] && [ $warning_count -gt 0 ]; then
        log_warn "Health checks passed with $warning_count warnings"
        return $EXIT_WARNING
    else
        log_error "Health checks failed - System is unhealthy"
        return $EXIT_FAILURE
    fi
}

# Main function
main() {
    local check_type="${1:-all}"
    
    case "$check_type" in
        "http")
            check_http_health
            ;;
        "ready")
            check_readiness
            ;;
        "app")
            check_app_functionality
            ;;
        "resources")
            check_resource_usage
            ;;
        "filesystem")
            check_file_system
            ;;
        "deps")
            check_dependencies
            ;;
        "config")
            check_configuration
            ;;
        "all"|*)
            run_health_checks
            ;;
    esac
}

# Error handling
trap 'log_error "Health check script failed unexpectedly"; exit 1' ERR

# Run main function
main "$@"