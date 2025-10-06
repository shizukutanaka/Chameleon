# Error Recovery Playbook - Chameleon Audio Tool

## Purpose

This guide documents practical recovery steps for CLI-based deployments. The focus is on deterministic handling of file-system, network, and configuration failures while preserving auditability.

## Core Principles

- **Fail Fast**: Detect invalid paths or URLs through `security_validator.py` before heavy processing begins.
- **Recover Predictably**: Retry only idempotent operations and record all attempts through `SecurityValidator.audit_log()`.
- **Protect Evidence**: Preserve logs and temporary artifacts required for post-incident review.

## Common Failure Scenarios

### 1. Directory Validation Failure
- **Symptoms**: `SecurityError` mentioning missing directory or improper permissions.
- **Action**:
  ```bash
  python security_tools.py validate-directory --path /absolute/path/output
  sudo chmod 750 /absolute/path/output
  ```
- **Audit**: Confirm new permissions in `~/.chameleon/logs/chameleon_security.log` and note the corrective action.

### 2. Network URL Rejection
- **Symptoms**: URL rejected by `validate_url()` due to scheme or host.
- **Action**:
  - Verify the domain is present in the allowlist controlled by `CHAMELEON_ALLOWED_ORIGINS`.
  - Re-run the operation after updating the allowlist through change control.
- **Audit**: Log the allowlist modification and attach change ticket identifiers.

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
  - Re-run the job with `--workers 2` or lower.
- **Audit**: Capture updated job parameters in the audit log.

## Recovery Workflow

```python
import logging
from datetime import datetime, timezone
from security_validator import SecurityValidator, SecurityError

validator = SecurityValidator()

def guarded_operation(operation_name, func, *args, **kwargs):
    attempts = 0
    max_attempts = 2

    while attempts < max_attempts:
        try:
            return func(*args, **kwargs)
        except SecurityError as exc:
            validator.audit_log(
                event="operation.security_error",
                details={
                    "operation": operation_name,
                    "attempt": attempts,
                    "error": str(exc)
                },
                level="WARNING"
            )
            raise
        except OSError as exc:
            attempts += 1
            validator.audit_log(
                event="operation.retry",
                details={
                    "operation": operation_name,
                    "attempt": attempts,
                    "error": str(exc)
                },
                level="WARNING"
            )
            if attempts >= max_attempts:
                raise

    raise RuntimeError("Guarded operation failed to retry correctly")
```

## Checklist Before Restarting Jobs

- **Validate Paths**: `python security_tools.py validate-directory --path /absolute/path/input`
- **Confirm URLs**: `python security_tools.py validate-url --url "$CHAMELEON_ASSET_URL"`
- **Review Logs**: `tail -n 50 ~/.chameleon/logs/enterprise_cli.log`
- **Clear Stale Temp Data** (POSIX):
  ```bash
  sudo find /tmp -maxdepth 1 -type f -name 'chameleon_*' -mmin +30 -delete
  ```

## Escalation Guidance
- If repeated failures occur in the same workflow, pause operations and open an incident report.
- Attach relevant log excerpts and validator audit entries.
- Clearly state whether input data or configuration changed between attempts.

Use this playbook to maintain predictable recovery behavior and to ensure every remediation action remains documented for compliance auditing.
