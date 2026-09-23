# Error Recovery Playbook - Chameleon Audio Tool

## Purpose

This guide documents practical recovery steps for CLI-based deployments. The focus is on deterministic handling of file-system, network, and configuration failures while preserving auditability.

## Core Principles

- **Fail Fast**: Detect invalid paths through `security_validator.py` before heavy processing begins.
- **Recover Predictably**: Retry only idempotent operations and record every attempt in the `chameleon` log (`~/.chameleon/logs/chameleon.log`, or `$CHAMELEON_LOG_DIR/chameleon.log`).
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

### 2. File Rejected by Size or Extension Policy
- **Symptoms**: `SecurityError` from `validate_file_path()` — the input
  exceeds `CHAMELEON_MAX_FILE_SIZE` (default 524288000 bytes, 500 MiB) or
  its suffix is outside `allowed_extensions`.
- **Action**:
  - Check the effective cap:
    `python -c "from security_validator import SecurityConfig; print(SecurityConfig.from_environment().max_file_size)"`.
  - Raise the cap for this deployment via `CHAMELEON_MAX_FILE_SIZE` (bytes),
    or split the source into files under the limit.
- **Audit**: The rejection and its reason are written to `chameleon.log`.

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
  - Re-run the job with `--max-workers 2` or lower (or `--no-parallel`).
- **Audit**: Capture updated job parameters in the audit log.

## Recovery Workflow

```python
import logging
from datetime import datetime, timezone
from security_validator import SecurityValidator, SecurityError

validator = SecurityValidator()
audit = logging.getLogger("chameleon")  # file handler set by setup_logging()

def guarded_operation(operation_name, func, *args, **kwargs):
    attempts = 0
    max_attempts = 2

    while attempts < max_attempts:
        try:
            return func(*args, **kwargs)
        except SecurityError as exc:
            audit.warning(
                "security_error operation=%s error=%s",
                operation_name, exc,
            )
            raise
        except OSError as exc:
            attempts += 1
            audit.warning(
                "retry operation=%s attempt=%d error=%s",
                operation_name, attempts, exc,
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
