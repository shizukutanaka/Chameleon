# Error Recovery Playbook - Chameleon Audio Tool

## Purpose

This guide documents practical recovery steps for CLI-based deployments. The focus is on deterministic handling of file-system, network, and configuration failures while preserving auditability.

## Core Principles

- **Fail Fast**: Detect invalid paths or URLs through `security_validator.py` before heavy processing begins.
- **Recover Predictably**: Retry only idempotent operations and record every attempt in the application log.
- **Protect Evidence**: Preserve logs and temporary artifacts required for post-incident review.

## Common Failure Scenarios

### 1. Directory Validation Failure
- **Symptoms**: `SecurityError` mentioning missing directory or improper permissions.
- **Action**:
  ```bash
  # Path containment is enforced against CHAMELEON_TRUSTED_ROOTS. Confirm the
  # directory is inside one of them, then fix its permissions.
  echo "$CHAMELEON_TRUSTED_ROOTS"
  chmod 750 /absolute/path/output
  chameleon analyze /absolute/path/output/probe.wav   # rejected paths fail here
  ```
- **Audit**: Rejections are logged to `~/.chameleon/logs/chameleon.log` (or
  `$CHAMELEON_LOG_DIR/chameleon.log`). Note the corrective action.

### 2. API Authentication Failure
- **Symptoms**: `401 Invalid authentication token` or `403 Invalid API key`
  from `main.py server` endpoints.
- **Action**:
  - Expired or missing session — log in again via `POST /auth/login` to get
    a fresh bearer token.
  - When `CHAMELEON_API_KEY` is configured, every request must also carry
    the `X-API-Key` header with the same value; a mismatch is a 403.
  - If the key should not be required at all, `CHAMELEON_API_KEY` must be
    unset in the service environment — a key the code never reads (e.g. an
    injected env var under a different name) leaves the check silently off,
    which is the opposite failure: verify what the process actually sees.
- **Audit**: Authentication attempts and denials are recorded in
  `$CHAMELEON_LOG_DIR/api-audit.log` (default `~/.chameleon/logs/`).

### 3. Disk Capacity Exhaustion
- **Symptoms**: `OSError: No space left on device` during batch jobs.
- **Action**:
  ```bash
  du -sh /absolute/path/output
  sudo find /absolute/path/output -type f -mtime +14 -delete
  ```
- **Audit**: Record cleanup actions and affected batch IDs.

### 4. Long-Running Job Timeout
- **Symptoms**: Batch automation stops with timeout events.
- **Action**:
  - Reduce `batch_automation.py` workload by splitting manifests.
  - Re-run the job with fewer workers — `--max-workers` is a global flag
    and goes before the sub-command:
    ```bash
    chameleon --max-workers 2 batch ./audio normalize --output-dir out/
    ```
- **Audit**: Capture updated job parameters in the audit log.

## Recovery Workflow

```python
import logging
from security_validator import SecurityValidator, SecurityError

logger = logging.getLogger("recovery")
validator = SecurityValidator()

def guarded_operation(operation_name, func, *args, **kwargs):
    attempts = 0
    max_attempts = 2

    while attempts < max_attempts:
        try:
            return func(*args, **kwargs)
        except SecurityError as exc:
            # Security rejections are never retried -- the input is the
            # problem, not timing. Record and propagate.
            logger.warning(
                "%s rejected on attempt %d: %s",
                operation_name, attempts, exc,
            )
            raise
        except OSError as exc:
            attempts += 1
            logger.warning(
                "%s failed on attempt %d (of %d): %s",
                operation_name, attempts, max_attempts, exc,
            )
            if attempts >= max_attempts:
                raise

    raise RuntimeError("Guarded operation failed to retry correctly")
```

## Checklist Before Restarting Jobs

- **Validate Paths**: `chameleon analyze /absolute/path/input/probe.wav` — a path
  outside `$CHAMELEON_TRUSTED_ROOTS` is rejected before any read.
- **Review Logs**: `tail -n 50 ~/.chameleon/logs/chameleon.log`
  (or `$CHAMELEON_LOG_DIR/chameleon.log`).
- **Clear Stale Temp Data** (POSIX):
  ```bash
  sudo find /tmp -maxdepth 1 -type f -name 'chameleon_*' -mmin +30 -delete
  ```

## Escalation Guidance
- If repeated failures occur in the same workflow, pause operations and open an incident report.
- Attach relevant log excerpts and validator audit entries.
- Clearly state whether input data or configuration changed between attempts.

Use this playbook to keep recovery behaviour predictable and to keep a record
of what was changed between attempts.
