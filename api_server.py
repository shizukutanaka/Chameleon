#!/usr/bin/env python3
"""
Chameleon Audio API Server
A thin, authenticated REST adapter over the stdlib WAV-processing core.
See CHARTER.md §5 for the threat model this defends against.
"""

import os
import asyncio
import logging
import secrets
import hashlib
import hmac
import time
import tempfile
import contextvars
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Deque
import uuid

# Core frameworks
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

# pydantic v1 ではパターン検証に `regex=` を、v2 では `pattern=` を使う。
# プロジェクトは pydantic<2 に固定されているが、誤って pydantic 2 が入った
# 環境（pydantic 2 で `regex=` は削除済み）でも import 時に即死しないよう、
# バージョンに応じたキーワードを選ぶ。
import pydantic as _pydantic

_PATTERN_KW = "pattern" if _pydantic.VERSION.startswith("2") else "regex"
_PYDANTIC_V2 = _pydantic.VERSION.startswith("2")


def _model_to_dict(model):
    """pydantic v1/v2 両対応の dict 変換（v2 の非推奨 .dict() を避ける）。"""
    if _PYDANTIC_V2 and hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _model_to_json(model):
    """pydantic v1/v2 両対応の JSON 変換（v2 の非推奨 .json() を避ける）。"""
    if _PYDANTIC_V2 and hasattr(model, "model_dump_json"):
        return model.model_dump_json()
    return model.json()

try:
    import psutil  # type: ignore
    HAS_PSUTIL = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PSUTIL = False

from security_validator import (
    SecurityValidator as ChameleonSecurityValidator,
    SecurityConfig as ChameleonSecurityConfig,
    SecurityError as ChameleonSecurityError,
    SecureFileOperations,
)

# The audio endpoints run on the standard-library core. These adapters convert
# the core's ProcessingResult into the dict shape the endpoints expect.
import core as _core

async def analyze_audio_fast(file_path) -> Dict[str, Any]:
    """Analyze an audio file using the standard-library core."""
    result = await _core.analyze_async(str(file_path))
    data = result.data or {}
    response: Dict[str, Any] = {
        'success': result.success,
        'processing_time': result.duration_ms / 1000.0,
        'processing_method': 'stdlib-core',
    }
    if result.success:
        response.update({
            'duration': data.get('duration'),
            'sample_rate': data.get('sample_rate'),
            'channels': data.get('channels'),
            'bit_depth': data.get('bit_depth'),
            'peak_level': data.get('peak_level'),
            'rms_level': data.get('rms_level'),
            'file_size': data.get('size_bytes'),
        })
    else:
        response['error'] = result.message
    return response

async def normalize_audio_fast(input_path, output_path, target_peak: float = 0.95) -> Dict[str, Any]:
    """Normalize an audio file using the standard-library core."""
    result = await _core.normalize_async(str(input_path), str(output_path), target_peak)
    data = result.data or {}
    response: Dict[str, Any] = {
        'success': result.success,
        'processing_time': result.duration_ms / 1000.0,
    }
    if result.success:
        response.update({
            'scale_factor': data.get('gain_applied'),
            'original_peak': data.get('original_peak'),
            'target_peak': data.get('target_peak', target_peak),
        })
    else:
        response['error'] = result.message
    return response

# API metadata
API_VERSION = "1.0.0"

# Security configuration
SECURITY_CONFIG = {
    'require_authentication': True,
    'enable_rate_limiting': True,
    'rate_limit_window_seconds': 60,
    'rate_limit_max_requests': 120,
    'max_file_size': 100 * 1024 * 1024,  # 100MB
    # WAV only: analyze_audio_fast/normalize_audio_fast go through the stdlib
    # core, which cannot parse FLAC. Accepting .flac uploads here meant every
    # such upload would predictably fail at analyze/normalize with "Invalid
    # WAV file format" — reject it at the upload boundary instead.
    'allowed_file_types': ['.wav', '.wave'],
    'session_timeout': 3600,  # 1 hour
    'max_session_idle_seconds': 900,
    'max_concurrent_jobs': 10,
    'max_active_sessions': 100,
    'max_job_history': 200,
    'max_job_queue_size': 200,
    'api_key_header': 'X-API-Key',
}

# A batch job awaiting a single file's operation must not sit in
# 'processing' forever when the awaited work never completes (a hung
# executor call, a wedged codec path). Without a bound, one stuck file
# permanently holds a worker permit and the job is indistinguishable from
# a slow one. Bound each file's operation; a timed-out file is recorded
# as a failure like any other per-file error and the job moves on.
# The underlying executor thread cannot be killed mid-call — it may keep
# running — but the job no longer waits on it.
# CHAMELEON_FILE_TIMEOUT=0 disables the bound (like CHAMELEON_TIMEOUT).
def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logging.warning("Ignoring invalid %s=%r; using default %d",
                        name, raw, default)
        return default
    if value < 0:
        logging.warning("Ignoring negative %s=%r; using default %d",
                        name, raw, default)
        return default
    return value


SECURITY_CONFIG['file_timeout_seconds'] = _env_int(
    'CHAMELEON_FILE_TIMEOUT', 300)

# Every bounded structure above caps *one* resource; nothing capped the
# aggregate upload store, so a long-running server accumulated
# UPLOAD_DIRECTORY files + registry entries without limit even though
# each file was individually size-checked. max_uploaded_files bounds the
# tracked set; overflow evicts least-recently-touched files (and their
# disk copies). CHAMELEON_MAX_UPLOADED_FILES=0 disables the cap.
SECURITY_CONFIG['max_uploaded_files'] = _env_int(
    'CHAMELEON_MAX_UPLOADED_FILES', 1000)

# The in-memory audit deque is bounded (max_audit_log_entries); the
# durable file it mirrors was not -- every event appended one JSON line
# to api-audit.log forever. Rotate to a single api-audit.log.1 when the
# file passes the cap, bounding disk at ~2x cap; older history is
# dropped by design (the in-memory tail serves recent reads).
# CHAMELEON_MAX_AUDIT_LOG_BYTES=0 disables rotation.
SECURITY_CONFIG['max_audit_log_bytes'] = _env_int(
    'CHAMELEON_MAX_AUDIT_LOG_BYTES', 50 * 1024 * 1024)

# A batch job's files list had no length cap: each entry fans out into a
# results dict per file, so a job naming the same registered file a
# million times grew job_data['results'] without bound while occupying a
# worker slot. max_batch_files rejects oversized submissions at 413;
# CHAMELEON_MAX_BATCH_FILES=0 disables the bound.
SECURITY_CONFIG['max_batch_files'] = _env_int(
    'CHAMELEON_MAX_BATCH_FILES', 10000)

PRIVILEGED_CLEARANCE = {"SECRET", "TOP_SECRET"}

# Clearance order for capping a self-declared login clearance. The request
# field exists because the API models multi-clearance sessions, but a
# deployment should be able to bound what a session may claim -- otherwise
# the client alone decides its own privilege ceiling. Default keeps the
# historical behavior (any declared level honored).
_CLEARANCE_ORDER = ["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET"]
_MAX_CLAIMABLE_CLEARANCE = os.environ.get(
    'CHAMELEON_API_MAX_CLEARANCE', 'TOP_SECRET')
if _MAX_CLAIMABLE_CLEARANCE not in _CLEARANCE_ORDER:
    # A typo here silently grants the *maximum* cap -- name it.
    logging.warning(
        "Invalid CHAMELEON_API_MAX_CLEARANCE %r; capping at TOP_SECRET",
        _MAX_CLAIMABLE_CLEARANCE,
    )
    _MAX_CLAIMABLE_CLEARANCE = 'TOP_SECRET'


def _cap_clearance(requested: str) -> str:
    """Return min(requested, deployment cap) by clearance order."""
    cap_idx = _CLEARANCE_ORDER.index(_MAX_CLAIMABLE_CLEARANCE)
    req_idx = _CLEARANCE_ORDER.index(requested)
    return _CLEARANCE_ORDER[min(req_idx, cap_idx)]

# The file this points at must exist: the root endpoint advertises it, and for
# a long time it advertised docs/user_manual.md, which does not.
_DEFAULT_DOC_PATH = Path(__file__).resolve().parent / 'docs' / 'api_documentation.md'
if os.environ.get('CHAMELEON_API_DOC'):
    DOCUMENTATION_REFERENCE = os.environ['CHAMELEON_API_DOC']
else:
    DOCUMENTATION_REFERENCE = _DEFAULT_DOC_PATH.as_uri() if _DEFAULT_DOC_PATH.exists() else str(_DEFAULT_DOC_PATH)


def _current_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _get_request_ip(request: Request) -> str:
    """Extract client IP address from request."""
    client = request.client
    return client.host if client else "unknown"


def _enforce_rate_limit(identifier: str) -> None:
    """Enforce simple fixed-window rate limiting per identifier."""
    if not SECURITY_CONFIG.get('enable_rate_limiting', False):
        return

    window_seconds = SECURITY_CONFIG.get('rate_limit_window_seconds', 60)
    max_requests = SECURITY_CONFIG.get('rate_limit_max_requests', 120)
    now = time.time()

    windows = api_state._rate_limit_windows
    window = windows.setdefault(identifier, deque())

    while window and now - window[0] > window_seconds:
        window.popleft()

    if len(window) >= max_requests:
        api_state.stats['rate_limited_requests'] += 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    window.append(now)

    # Opportunistic cleanup: every identifier gets its own deque, and a
    # one-shot caller (e.g. a scanner hitting many usernames) would
    # otherwise leave an entry behind forever. The pop loop only runs for
    # the identifier being called, so a never-returning id keeps a
    # non-empty deque of expired timestamps -- drop every window whose
    # newest entry has aged out, not just ones already empty.
    if len(windows) > max(200, max_requests):
        for stale_id in [k for k, w in windows.items()
                         if not w or now - w[-1] > window_seconds]:
            del windows[stale_id]

# API Models
class AuthenticationRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    clearance_level: str = Field(..., **{_PATTERN_KW: r'^(UNCLASSIFIED|CONFIDENTIAL|SECRET|TOP_SECRET)$'})

class AuthenticationResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None

class AudioAnalysisRequest(BaseModel):
    file_name: str

class AudioAnalysisResponse(BaseModel):
    success: bool
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    peak_level: Optional[float] = None
    rms_level: Optional[float] = None
    file_size: Optional[int] = None
    processing_time: Optional[float] = None
    processing_method: Optional[str] = None
    error: Optional[str] = None

class AudioNormalizationRequest(BaseModel):
    file_name: str
    target_peak: float = Field(0.95, ge=0.1, le=1.0)
    # WAV only: normalize_audio_fast writes through the stdlib core, which has
    # no FLAC encoder. Previously accepted "flac" here produced a file with a
    # .flac extension containing raw WAV bytes — an unbacked capability claim.
    output_format: str = Field('wav', **{_PATTERN_KW: r'^(wav)$'})

class AudioNormalizationResponse(BaseModel):
    success: bool
    output_file: Optional[str] = None
    scale_factor: Optional[float] = None
    original_peak: Optional[float] = None
    target_peak: Optional[float] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None

class BatchJobRequest(BaseModel):
    files: List[str]
    operation: str = Field(..., **{_PATTERN_KW: r'^(analyze|normalize)$'})
    options: Dict[str, Any] = Field(default_factory=dict)

    @_pydantic.root_validator
    def _options_reach_the_operation(cls, values):
        """Reject option keys that no batch operation consumes.

        ``options`` used to be stored and dropped: a normalize job sent
        ``{"options": {"target_peak": 0.5}}`` silently ran at 0.95. An
        accepted-but-ignored field is the same dishonesty class as a dead
        CLI flag, so unknown keys (and normalize's out-of-range values)
        are rejected here at submit time instead.
        """
        operation = values.get('operation')
        options = values.get('options') or {}
        allowed = {'normalize': {'target_peak'}, 'analyze': set()}.get(operation, set())
        unknown = set(options) - allowed
        if unknown:
            raise ValueError(
                f"operation '{operation}' does not accept option(s): "
                f"{', '.join(sorted(unknown))}"
            )
        if 'target_peak' in options:
            value = options['target_peak']
            # bool is an int subclass -- exclude it, "target_peak: true"
            # is a type error, not 1.0.
            if not isinstance(value, (int, float)) or isinstance(value, bool) \
                    or not 0.0 < value <= 1.0:
                raise ValueError("options.target_peak must be a number in (0, 1.0]")
        return values

class BatchJobResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    total_files: Optional[int] = None
    estimated_duration: Optional[float] = None
    error: Optional[str] = None

class BatchJobStatus(BaseModel):
    job_id: str
    status: str  # queued, processing, completed, failed
    progress: float  # 0.0 to 1.0
    completed_files: int
    total_files: int
    current_file: Optional[str] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class SystemStatusResponse(BaseModel):
    status: str
    uptime: float
    active_jobs: int
    queued_jobs: int
    completed_jobs: int
    error_rate: float
    memory_usage: float
    cpu_usage: float
    security_status: str
    version: str
    active_sessions: int
    last_request_timestamp: Optional[str]
    last_job_error: Optional[str]
    circuit_breaker_open: bool
    request_latency_ms: Optional[float]
    request_latency_p95_ms: Optional[float]
    requests_per_minute: float

class AuditLogEntry(BaseModel):
    timestamp: datetime
    user: str
    operation: str
    resource: str
    result: str
    details: str
    ip_address: str
    session_id: str
    request_id: Optional[str] = None

# Global state management
class APIState:
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.token_index: Dict[str, str] = {}
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_queue: List[str] = []
        # Bounded in-memory audit buffer: every event is also appended
        # to the audit file for durable storage, so the in-memory copy
        # exists only to serve /audit/log reads and must not grow
        # without limit on a long-running server.
        self.audit_log: Deque[AuditLogEntry] = deque(
            maxlen=SECURITY_CONFIG.get('max_audit_log_entries') or 10_000
        )
        self.server_start_time = time.time()
        self.stats = {
            'completed_jobs': 0,
            'failed_jobs': 0,
            'total_requests': 0,
            'rate_limited_requests': 0,
            'last_request_timestamp': None,
            'last_job_error': None,
            'request_latency_ewma_ms': None,
            'request_histogram_ms': [],
        }
        self._rate_limit_windows: Dict[str, deque] = {}
        history_size = SECURITY_CONFIG.get('max_job_history')
        self.job_history: Deque[str] = deque(maxlen=history_size if history_size and history_size > 0 else None)
        self.job_failures_window: Deque[float] = deque()
        self.circuit_breaker_open: bool = False
        self.request_window: Deque[float] = deque()
        self.uploaded_files: Dict[str, Dict[str, Any]] = {}

    def add_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Register a new active session and index its token."""
        self.active_sessions[session_id] = session_data
        token = session_data.get('token')
        if token:
            self.token_index[token] = session_id

    def remove_session(self, session_id: str) -> None:
        """Remove session and associated token index if present."""
        session = self.active_sessions.pop(session_id, None)
        if not session:
            return
        token = session.get('token')
        if token:
            self.token_index.pop(token, None)

    def register_uploaded_file(
        self,
        file_name: str,
        *,
        owner: str,
        size: int,
        original_name: str,
        session_id: str,
    ) -> None:
        """Record metadata for a freshly uploaded file."""
        timestamp = _current_timestamp()
        self.uploaded_files[file_name] = {
            'owner': owner,
            'size': size,
            'original_name': original_name,
            'session_id': session_id,
            'created_at': timestamp,
            'last_modified': timestamp,
            'operation': 'upload',
            'source_files': [],
        }
        self._enforce_upload_cap()

    def _enforce_upload_cap(self) -> None:
        """Evict least-recently-touched files beyond max_uploaded_files.

        Drops both the registry entry and the on-disk copy so the
        aggregate upload store stays bounded; cap of 0 means unbounded.
        """
        cap = SECURITY_CONFIG.get('max_uploaded_files')
        while cap and len(self.uploaded_files) > cap:
            name, meta = min(
                self.uploaded_files.items(),
                key=lambda kv: kv[1].get('last_modified') or '',
            )
            self.uploaded_files.pop(name, None)
            try:
                path = (UPLOAD_DIRECTORY / name).resolve()
                path.relative_to(UPLOAD_DIRECTORY.resolve())
            except (ValueError, OSError):
                logging.warning(
                    "Evicted %s from upload registry; skipping unlink "
                    "(path escaped upload root)", name)
            else:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logging.warning(
                        "Evicted %s from upload registry; disk unlink "
                        "failed", name)
            log_audit_event(
                meta.get('owner', ''), "FILE_EVICTED", name, "SUCCESS",
                "Evicted by upload cap (LRU)", "",
                meta.get('session_id') or "",
            )

    def register_generated_file(
        self,
        file_name: str,
        *,
        owner: str,
        size: int,
        source_files: List[str],
        operation: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Record metadata for files generated by server-side processing."""
        timestamp = _current_timestamp()
        self.uploaded_files[file_name] = {
            'owner': owner,
            'size': size,
            'original_name': file_name,
            'session_id': session_id,
            'created_at': timestamp,
            'last_modified': timestamp,
            'operation': operation,
            'source_files': source_files,
        }
        self._enforce_upload_cap()

    def touch_file_metadata(self, file_name: str) -> None:
        """Update last access timestamp for tracked files."""
        metadata = self.uploaded_files.get(file_name)
        if metadata is not None:
            metadata['last_modified'] = _current_timestamp()

api_state = APIState()


# Hardened audit logging helpers
_AUDIT_VALIDATOR = ChameleonSecurityValidator(
    ChameleonSecurityConfig(
        allowed_extensions={'.log'},
        log_security_events=False,
        max_file_size=10 * 1024 * 1024,
    )
)
_AUDIT_FILES = SecureFileOperations(_AUDIT_VALIDATOR)

_REQUEST_VALIDATOR = ChameleonSecurityValidator(
    ChameleonSecurityConfig(
        # .flac dropped: the stdlib core this API adapts to cannot read or
        # write FLAC (see SECURITY_CONFIG['allowed_file_types'] above).
        allowed_extensions={'.wav', '.wave', '.json', '.zip'},
        log_security_events=False,
    )
)

_UPLOAD_FILES = SecureFileOperations(_REQUEST_VALIDATOR)


def _cleanup_expired_sessions() -> None:
    """Remove expired sessions from active registry."""
    now = datetime.now(timezone.utc)
    idle_timeout = SECURITY_CONFIG.get('max_session_idle_seconds')
    expired_ids: List[str] = []

    for session_id, data in list(api_state.active_sessions.items()):
        expires_at = data.get('expires_at')
        if expires_at and expires_at <= now:
            expired_ids.append(session_id)
            continue

        if idle_timeout:
            last_seen = data.get('last_seen_at')
            if last_seen and (now - last_seen).total_seconds() >= idle_timeout:
                expired_ids.append(session_id)

    for session_id in expired_ids:
        api_state.remove_session(session_id)


def _enforce_session_capacity() -> None:
    """Ensure active session count stays within configured limit."""
    limit = SECURITY_CONFIG.get('max_active_sessions')
    if not limit:
        return

    if len(api_state.active_sessions) >= limit:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        )


def _resolve_upload_directory() -> Path:
    """Resolve and validate upload directory."""
    env_override = os.environ.get('CHAMELEON_UPLOAD_DIR')
    if env_override:
        candidate = Path(env_override)
    else:
        candidate = Path(tempfile.gettempdir()) / 'chameleon' / 'uploads'

    return _REQUEST_VALIDATOR.validate_directory(
        candidate,
        require_exists=False,
        allow_create=True,
    )


def _determine_upload_chunk_size() -> int:
    """Determine upload chunk size with sane bounds."""
    default = 1024 * 1024  # 1MB
    raw_value = os.environ.get('CHAMELEON_UPLOAD_CHUNK_SIZE')
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        logging.warning(
            "Invalid CHAMELEON_UPLOAD_CHUNK_SIZE value '%s'; using default %d bytes",
            raw_value,
            default,
        )
        return default

    minimum = 64 * 1024  # 64KB
    maximum = SECURITY_CONFIG['max_file_size']
    return max(minimum, min(value, maximum))


UPLOAD_DIRECTORY = _resolve_upload_directory()
UPLOAD_CHUNK_SIZE = _determine_upload_chunk_size()

# Request tracing context
REQUEST_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("chameleon_request_id", default=None)
REQUEST_ID_HEADER = "X-Request-ID"

# Concurrency guard for batch jobs
JOB_WORKER_SEMAPHORE = asyncio.Semaphore(SECURITY_CONFIG['max_concurrent_jobs'])

# Circuit breaker configuration for background workers
CIRCUIT_BREAKER_THRESHOLD_FAILURES = SECURITY_CONFIG.get('circuit_breaker_failure_threshold', 5)
CIRCUIT_BREAKER_WINDOW_SECONDS = SECURITY_CONFIG.get('circuit_breaker_window_seconds', 60)
CIRCUIT_BREAKER_RESET_SECONDS = SECURITY_CONFIG.get('circuit_breaker_reset_seconds', 120)
REQUEST_LATENCY_SMOOTHING = 0.2


def _validate_upload_extension(filename: str) -> None:
    """Validate extension of uploaded files."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SECURITY_CONFIG['allowed_file_types']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type",
        )


def _sanitize_uploaded_name(name: str) -> str:
    """Sanitize uploaded file name to prevent path traversal attacks."""
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File name is required")

    if any(sep in normalized for sep in ("/", "\\")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Nested paths are not permitted")

    sanitized = _REQUEST_VALIDATOR.sanitize_filename(normalized)
    if sanitized != normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File name contained disallowed characters")

    return sanitized


def _load_dev_credentials() -> tuple[Optional[str], Optional[str]]:
    """Load developer fallback credentials from environment."""
    username = os.environ.get('CHAMELEON_DEV_USERNAME')
    password_hash = os.environ.get('CHAMELEON_DEV_PASSWORD_HASH')
    return username, password_hash


_DEV_USERNAME, _DEV_PASSWORD_HASH = _load_dev_credentials()


async def _persist_upload(file: UploadFile, destination: Path) -> int:
    """Persist upload safely to destination."""
    try:
        target_path = _REQUEST_VALIDATOR.validate_file_path(destination, operation="create")
    except ChameleonSecurityError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    total_bytes = 0
    try:
        with _UPLOAD_FILES.secure_open(target_path, 'wb') as buffer:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > SECURITY_CONFIG['max_file_size']:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large",
                    )
                buffer.write(chunk)
    except HTTPException:
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                logging.warning("Failed to remove partial upload: %s", target_path)
        raise
    except Exception as exc:
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                logging.warning("Failed to remove partial upload: %s", target_path)
        logging.error("Unexpected error while persisting upload: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload persistence failed") from exc
    finally:
        await file.close()

    return total_bytes

def _resolve_uploaded_path(name: str) -> Path:
    """Resolve uploaded file path within the secure upload directory."""
    sanitized = _sanitize_uploaded_name(name)
    candidate = (UPLOAD_DIRECTORY / sanitized).resolve(strict=False)

    upload_root = UPLOAD_DIRECTORY.resolve(strict=False)
    if candidate.parent != upload_root:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File reference outside upload area")

    try:
        _REQUEST_VALIDATOR.validate_file_path(candidate, operation="read")
    except ChameleonSecurityError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not candidate.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    return candidate


def _get_authorized_file_path(file_name: str, user: dict, allow_privileged: bool = True) -> Path:
    """Authorize access to user file and return secure resolved path."""
    metadata = api_state.uploaded_files.get(file_name)
    if metadata is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not registered")

    is_owner = metadata.get('owner') == user.get('username')
    has_privilege = allow_privileged and user.get('clearance_level') in PRIVILEGED_CLEARANCE
    if not (is_owner or has_privilege):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Access denied for requested file")

    path = _resolve_uploaded_path(file_name)
    api_state.touch_file_metadata(file_name)
    return path


def _validate_cors_origin(origin: str) -> str:
    """Validate a CORS origin (scheme://host[:port]) and return it normalized.

    Only http/https origins with a host and no path/query/fragment are allowed.
    Raises ChameleonSecurityError for anything else.
    """
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ChameleonSecurityError(f"Invalid origin scheme or host: {origin}")
    if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ChameleonSecurityError(f"Origin must not contain a path or query: {origin}")
    # Reconstruct from validated components to drop any trailing slash/credentials.
    netloc = parsed.hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}"


def _get_allowed_origins() -> list[str]:
    raw_origins = os.environ.get('CHAMELEON_ALLOWED_ORIGINS', 'https://localhost:3000').split(',')
    sanitized: List[str] = []
    for origin in raw_origins:
        origin = origin.strip()
        if not origin:
            continue
        try:
            sanitized.append(_validate_cors_origin(origin))
        except ChameleonSecurityError:
            logging.warning("Invalid origin supplied: %s", origin)
            continue
    return sanitized or ['https://localhost:3000']


def _resolve_audit_log_path() -> Path:
    """Return secure audit log path with directory validation."""
    preferred_dir = Path.home() / '.chameleon' / 'logs'

    try:
        log_dir = _AUDIT_VALIDATOR.validate_directory(
            preferred_dir,
            require_exists=False,
            allow_create=True,
        )
    except ChameleonSecurityError:
        fallback = Path(tempfile.gettempdir()) / 'chameleon' / 'logs'
        log_dir = _AUDIT_VALIDATOR.validate_directory(
            fallback,
            require_exists=False,
            allow_create=True,
        )

    return log_dir / 'api-audit.log'

# FastAPI app initialization
app = FastAPI(
    title="Chameleon Audio API",
    description="Authenticated REST API over the Chameleon stdlib WAV-processing core.",
    version=API_VERSION,
    docs_url="/docs" if not SECURITY_CONFIG['require_authentication'] else None,
    redoc_url="/redoc" if not SECURITY_CONFIG['require_authentication'] else None,
    openapi_url="/openapi.json",
)

# Security middleware
allowed_hosts_env = os.environ.get("CHAMELEON_ALLOWED_HOSTS")
if allowed_hosts_env:
    allowed_hosts = [host.strip() for host in allowed_hosts_env.split(",") if host.strip()]
else:
    allowed_hosts = ["localhost", "127.0.0.1"]

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Inject strict transport and content security headers in responses."""
    response = await call_next(request)

    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Assign per-request correlation IDs and expose them in responses."""
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    token = REQUEST_ID_CTX.set(request_id)
    start_time = time.time()
    try:
        response = await call_next(request)
    finally:
        REQUEST_ID_CTX.reset(token)

    end_time = time.time()
    response.headers.setdefault(REQUEST_ID_HEADER, request_id)

    elapsed_ms = (end_time - start_time) * 1000
    prev = api_state.stats['request_latency_ewma_ms']
    if prev is None:
        api_state.stats['request_latency_ewma_ms'] = elapsed_ms
    else:
        api_state.stats['request_latency_ewma_ms'] = (REQUEST_LATENCY_SMOOTHING * elapsed_ms) + ((1 - REQUEST_LATENCY_SMOOTHING) * prev)
    histogram = api_state.stats['request_histogram_ms']
    histogram.append(elapsed_ms)
    if len(histogram) > 1000:
        histogram.pop(0)

    req_window = api_state.request_window
    req_window.append(end_time)
    cutoff = end_time - 60
    while req_window and req_window[0] < cutoff:
        req_window.popleft()
    return response


# Security schemes
security = HTTPBearer()
api_key_header_name = SECURITY_CONFIG.get('api_key_header')
API_KEY_SCHEME = APIKeyHeader(name=api_key_header_name, auto_error=False) if api_key_header_name else None

# Utility functions

def generate_secure_token() -> str:
    """Generate cryptographically secure API token"""
    return secrets.token_urlsafe(32)


def _compute_token_signature(token: str, secret: str) -> str:
    """Compute deterministic HMAC signature for issued tokens."""
    return hmac.new(secret.encode('utf-8'), token.encode('utf-8'), hashlib.sha256).hexdigest()


def hash_password(password: str, salt: bytes) -> bytes:
    """Hash password using PBKDF2"""
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)


def verify_token_signature(token: str, secret: str, expected_signature: str) -> bool:
    """Verify HMAC signature of token using constant time comparison."""
    if not token or not secret or not expected_signature:
        return False
    try:
        computed = _compute_token_signature(token, secret)
        return hmac.compare_digest(computed, expected_signature)
    except Exception:
        return False


def _derive_session_secret(username: str, session_id: str) -> str:
    """Derive a session-specific secret for token validation."""
    seed = f"{username}:{session_id}:{SECURITY_CONFIG['session_timeout']}"
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()


def _audit_denied(user: dict, operation: str, resource: str,
                  exc: HTTPException, http_request: Request) -> None:
    """Record refused requests. A log that only shows successes cannot
    reveal filename probing or permission escalation attempts."""
    try:
        log_audit_event(
            user.get('username', 'unknown'), operation, resource, "DENIED",
            f"HTTP {exc.status_code}: {exc.detail}",
            _get_request_ip(http_request), user.get('session_id', ''),
        )
    except Exception:
        logging.debug("denied-request audit write failed", exc_info=True)


def log_audit_event(user: str, operation: str, resource: str, result: str,
                   details: str, ip_address: str, session_id: str):
    """Log security audit event"""
    request_id = REQUEST_ID_CTX.get()
    entry = AuditLogEntry(
        timestamp=datetime.now(timezone.utc),
        user=user,
        operation=operation,
        resource=resource,
        result=result,
        details=details,
        ip_address=ip_address,
        session_id=session_id,
        request_id=request_id,
    )
    api_state.audit_log.append(entry)

    # Also log to file for persistent storage
    try:
        log_file = _resolve_audit_log_path()
        max_bytes = SECURITY_CONFIG.get('max_audit_log_bytes')
        if max_bytes:
            try:
                if log_file.stat().st_size >= max_bytes:
                    os.replace(log_file, log_file.with_suffix('.log.1'))
            except OSError:
                pass
        with _AUDIT_FILES.secure_open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{_model_to_json(entry)}\n")
    except Exception as e:
        logging.error(f"Failed to write audit log: {e}")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = REQUEST_ID_CTX.get()
    logging.warning("Validation error for %s: %s", request.url.path, exc)
    payload = {
        "detail": "Invalid request payload",
        "errors": exc.errors(),
    }
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = REQUEST_ID_CTX.get()
    logging.exception("Unhandled server error for %s", request.url.path)
    payload = {"detail": "Internal server error"}
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def _update_circuit_breaker(success: bool) -> None:
    """Update circuit breaker state based on job outcomes."""
    now = time.time()

    window = api_state.job_failures_window

    # Remove expired failure entries
    while window and (now - window[0]) > CIRCUIT_BREAKER_WINDOW_SECONDS:
        window.popleft()

    if success:
        if api_state.circuit_breaker_open and (not window or (now - window[-1]) > CIRCUIT_BREAKER_RESET_SECONDS):
            api_state.circuit_breaker_open = False
        return

    # Record current failure
    window.append(now)

    if len(window) >= CIRCUIT_BREAKER_THRESHOLD_FAILURES:
        api_state.circuit_breaker_open = True


def _record_job_completion(job_id: str) -> None:
    """Track completed job history and prune old entries."""
    maxlen = api_state.job_history.maxlen
    stale_id: Optional[str] = None
    if maxlen and len(api_state.job_history) == maxlen:
        stale_id = api_state.job_history[0]

    api_state.job_history.append(job_id)

    if stale_id:
        stale_job = api_state.active_jobs.get(stale_id)
        if stale_job and stale_job.get('status') in {'completed', 'failed'}:
            api_state.active_jobs.pop(stale_id, None)


# Authentication dependency
async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate authentication token and return user info"""
    api_state.stats['total_requests'] += 1
    api_state.stats['last_request_timestamp'] = datetime.now(timezone.utc).isoformat()
    _cleanup_expired_sessions()

    # No bypass branch: SECURITY_CONFIG['require_authentication'] is always
    # True. A `if not ...: return SECRET-clearance mock user` escape hatch
    # lived here -- unreachable today, but an auth bypass one config edit
    # away from live. Dead code that grants privilege is worse than no code.
    #
    # Optional API key verification layered on top of JWT/session auth
    if API_KEY_SCHEME is not None:
        api_key = request.headers.get(api_key_header_name)
        expected_key = os.environ.get('CHAMELEON_API_KEY')
        if expected_key:
            if not api_key or not hmac.compare_digest(api_key, expected_key):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    token = credentials.credentials
    client_id = _get_request_ip(request)
    _enforce_rate_limit(f"auth:{client_id}")

    session_id = api_state.token_index.get(token)
    session_data = api_state.active_sessions.get(session_id) if session_id else None

    if session_data is None:
        # Backwards compatibility: fall back to search and re-index token
        for candidate_id, candidate_data in api_state.active_sessions.items():
            stored = candidate_data.get('token')
            if stored is not None and hmac.compare_digest(stored, token):
                session_id = candidate_id
                session_data = candidate_data
                api_state.token_index[token] = candidate_id
                break

    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )

    # datetime.min is naive; comparing it to the aware "now" would TypeError
    # if expires_at were ever absent, so the default must be tz-aware.
    if datetime.now(timezone.utc) > session_data.get(
            'expires_at', datetime.min.replace(tzinfo=timezone.utc)):
        api_state.remove_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )

    session_secret = session_data.get('secret') or _derive_session_secret(session_data['username'], session_id)
    expected_signature = session_data.get('token_signature')
    if not verify_token_signature(token, session_secret, expected_signature):
        api_state.remove_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature invalid"
        )

    session_data['secret'] = session_secret
    session_data['last_seen_at'] = datetime.now(timezone.utc)

    return {
        'username': session_data['username'],
        'clearance_level': session_data['clearance_level'],
        'session_id': session_id
    }

# Permission checking
def require_permission(permission: str):
    """Require an authenticated session, and name the permission involved.

    Honest scope: there is **no per-permission authorization** here. Any valid
    session may call any endpoint. The `permission` argument documents what an
    endpoint does -- it is not enforced. Chameleon has a single class of API
    user; adding real roles means adding a permission store, not re-reading
    this argument.
    """
    def permission_check(user: dict = Depends(get_current_user)):
        return user
    return permission_check

# API Endpoints

@app.get("/", response_class=JSONResponse)
async def root():
    """API root endpoint with basic information"""
    return {
        "service": "Chameleon Audio API",
        "version": API_VERSION,
        "status": "operational",
        "documentation": DOCUMENTATION_REFERENCE,
        "authentication_required": SECURITY_CONFIG['require_authentication'],
    }


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Lightweight health check for orchestration systems."""
    return {
        "status": "ok",
        "uptime_seconds": time.time() - api_state.server_start_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.post("/auth/login", response_model=AuthenticationResponse)
async def login(request: AuthenticationRequest, http_request: Request):
    """Authenticate user and create session"""
    try:
        api_state.stats['total_requests'] += 1
        _cleanup_expired_sessions()
        _enforce_session_capacity()
        client_ip = _get_request_ip(http_request)
        _enforce_rate_limit(f"login:{client_ip}:{request.username}")

        # Single-user credential check against the configured environment.
        if not (_DEV_USERNAME and _DEV_PASSWORD_HASH):
            logging.error("API credentials are not configured; refusing to authenticate")
            return AuthenticationResponse(
                success=False,
                error="Authentication unavailable"
            )

        provided_hash = hashlib.sha256(request.password.encode('utf-8')).hexdigest()

        if not (
            hmac.compare_digest(request.username, _DEV_USERNAME)
            and hmac.compare_digest(provided_hash, _DEV_PASSWORD_HASH)
        ):
            log_audit_event(
                request.username,
                "LOGIN",
                "API",
                "FAILED",
                "Invalid credentials",
                client_ip,
                "",
            )
            return AuthenticationResponse(
                success=False,
                error="Invalid credentials"
            )

        # Create session
        session_id = str(uuid.uuid4())
        token = generate_secure_token()
        secret = _derive_session_secret(request.username, session_id)
        token_signature = _compute_token_signature(token, secret)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=SECURITY_CONFIG['session_timeout'])

        session_data = {
            'username': request.username,
            # The request's clearance is self-declared; honor it only up
            # to the deployment's configured ceiling.
            'clearance_level': _cap_clearance(request.clearance_level),
            'token': token,
            'expires_at': expires_at,
            'created_at': datetime.now(timezone.utc),
            'secret': secret,
            'token_signature': token_signature,
            'last_seen_at': datetime.now(timezone.utc),
            'client_ip': client_ip,
        }

        api_state.add_session(session_id, session_data)

        log_audit_event(
            request.username, "LOGIN", "API", "SUCCESS",
            f"User authenticated with {session_data['clearance_level']} clearance",
            client_ip, session_id
        )

        return AuthenticationResponse(
            success=True,
            token=token,
            user_info={
                'username': request.username,
                'clearance_level': session_data['clearance_level'],
                'session_id': session_id
            },
            expires_at=expires_at
        )

    except HTTPException as exc:
        _audit_denied({'username': request.username, 'session_id': ''},
                      "LOGIN", "API", exc, http_request)
        raise  # preserve 429 (rate limit) / 503 (capacity) status codes
    except Exception as e:
        logging.error(f"Login error: {e}")
        return AuthenticationResponse(
            success=False,
            error="Authentication service error"
        )

@app.post("/auth/logout")
async def logout(http_request: Request, user: dict = Depends(get_current_user)):
    """Logout user and invalidate session"""
    session_id = user['session_id']

    api_state.remove_session(session_id)

    client_ip = _get_request_ip(http_request)

    log_audit_event(
        user['username'], "LOGOUT", "API", "SUCCESS",
        "User logged out", client_ip, session_id
    )

    return {"success": True, "message": "Logged out successfully"}

@app.post("/audio/upload")
async def upload_audio_file(
    http_request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("process"))
):
    """Upload audio file for processing"""
    try:
        _validate_upload_extension(file.filename)

        sanitized_name = _REQUEST_VALIDATOR.sanitize_filename(Path(file.filename).name)
        unique_name = f"{uuid.uuid4().hex}_{sanitized_name}"
        destination = (UPLOAD_DIRECTORY / unique_name).resolve(strict=False)
        upload_root = UPLOAD_DIRECTORY.resolve(strict=False)
        if destination.parent != upload_root:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid upload destination")

        total_bytes = await _persist_upload(file, destination)

        api_state.register_uploaded_file(
            unique_name,
            owner=user['username'],
            size=total_bytes,
            original_name=sanitized_name,
            session_id=user['session_id'],
        )

        client_ip = _get_request_ip(http_request)

        log_audit_event(
            user['username'],
            "UPLOAD",
            unique_name,
            "SUCCESS",
            f"Stored {total_bytes} bytes",
            client_ip,
            user['session_id'],
        )

        return {
            "success": True,
            "message": "File uploaded successfully",
            "stored_name": unique_name,
            "size": total_bytes,
        }
    except HTTPException as exc:
        _audit_denied(user, "UPLOAD", sanitized_name if 'sanitized_name' in dir() else
                      getattr(file, 'filename', '?'), exc, http_request)
        raise
    except Exception as exc:
        logging.error("Upload error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed") from exc

@app.post("/audio/analyze", response_model=AudioAnalysisResponse)
async def process_audio(
    payload: AudioAnalysisRequest,
    http_request: Request,
    user: dict = Depends(require_permission("process"))
):
    """Process audio analysis"""
    try:
        # Reject remote URLs; only previously uploaded files are processable.
        if payload.file_name.lower().startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Remote URLs are not supported; upload the file first."
            )

        file_path = _get_authorized_file_path(payload.file_name, user)

        file_timeout = SECURITY_CONFIG.get('file_timeout_seconds') or None
        try:
            result = await asyncio.wait_for(
                analyze_audio_fast(file_path), file_timeout)
        except TimeoutError:
            result = {
                'success': False,
                'error': f'timed out after {file_timeout}s',
            }

        client_ip = _get_request_ip(http_request)

        log_audit_event(
            user['username'], "ANALYZE", str(file_path),
            "SUCCESS" if result.get('success') else "FAILED",
            "Audio analysis completed", client_ip, user['session_id']
        )

        if result.get('success'):
            return AudioAnalysisResponse(
                success=True,
                duration=result.get('duration'),
                sample_rate=result.get('sample_rate'),
                channels=result.get('channels'),
                bit_depth=result.get('bit_depth'),
                peak_level=result.get('peak_level'),
                rms_level=result.get('rms_level'),
                file_size=result.get('file_size'),
                processing_time=result.get('processing_time'),
                processing_method=result.get('processing_method')
            )
        return AudioAnalysisResponse(success=False, error=result.get('error', 'Analysis failed'))

    except HTTPException:
        raise
    except Exception as exc:
        logging.error("Analysis error: %s", exc)
        return AudioAnalysisResponse(success=False, error="Analysis failed")

@app.post("/audio/normalize", response_model=AudioNormalizationResponse)
async def normalize_audio(
    payload: AudioNormalizationRequest,
    http_request: Request,
    user: dict = Depends(require_permission("process"))
):
    """Normalize audio file"""
    try:
        input_path = _get_authorized_file_path(payload.file_name, user)

        output_name = f"normalized_{uuid.uuid4().hex}.{payload.output_format}"
        output_path = (UPLOAD_DIRECTORY / output_name).resolve(strict=False)
        upload_root = UPLOAD_DIRECTORY.resolve(strict=False)
        if output_path.parent != upload_root:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid output destination")

        try:
            _REQUEST_VALIDATOR.validate_file_path(output_path, operation="create")
        except ChameleonSecurityError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        # Use high-performance processor
        file_timeout = SECURITY_CONFIG.get('file_timeout_seconds') or None
        try:
            result = await asyncio.wait_for(
                normalize_audio_fast(input_path, output_path,
                                     payload.target_peak),
                file_timeout,
            )
        except TimeoutError:
            result = {
                'success': False,
                'error': f'timed out after {file_timeout}s',
            }

        client_ip = _get_request_ip(http_request)

        log_audit_event(
            user['username'], "NORMALIZE", str(input_path),
            "SUCCESS" if result.get('success') else "FAILED",
            "Audio normalization completed", client_ip, user['session_id']
        )

        if result.get('success'):
            try:
                output_size = output_path.stat().st_size
            except FileNotFoundError:
                output_size = 0

            api_state.register_generated_file(
                output_name,
                owner=user['username'],
                size=output_size,
                source_files=[payload.file_name],
                operation='normalize',
                session_id=user['session_id'],
            )

            return AudioNormalizationResponse(
                success=True,
                output_file=output_name,
                scale_factor=result.get('scale_factor'),
                original_peak=result.get('original_peak'),
                target_peak=result.get('target_peak'),
                processing_time=result.get('processing_time')
            )
        else:
            return AudioNormalizationResponse(
                success=False,
                error=result.get('error', 'Normalization failed')
            )

    except HTTPException as exc:
        _audit_denied(user, "NORMALIZE", payload.file_name, exc, http_request)
        raise  # preserve 400 (invalid destination) / 404 / 403 status codes
    except Exception as e:
        logging.error(f"Normalization error: {e}")
        return AudioNormalizationResponse(
            success=False,
            error="Normalization failed"
        )

@app.get("/audio/download/{file_name}")
async def download_file(
    file_name: str,
    http_request: Request,
    user: dict = Depends(require_permission("read"))
):
    """Download processed audio file"""
    try:
        file_path = _get_authorized_file_path(file_name, user)

        client_ip = _get_request_ip(http_request)

        log_audit_event(
            user['username'], "DOWNLOAD", str(file_path), "SUCCESS",
            f"File downloaded: {file_name}", client_ip, user['session_id']
        )

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type='application/octet-stream'
        )

    except HTTPException as exc:
        _audit_denied(user, "DOWNLOAD", file_name, exc, http_request)
        raise  # preserve 404 (not found) / 403 (unauthorized path) status codes
    except Exception as e:
        logging.error(f"Download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Download failed"
        )

@app.post("/batch/submit", response_model=BatchJobResponse)
async def submit_batch_job(
    payload: BatchJobRequest,
    http_request: Request,
    user: dict = Depends(require_permission("process"))
):
    """Submit batch processing job"""
    try:
        job_id = str(uuid.uuid4())

        queue_limit = SECURITY_CONFIG.get('max_job_queue_size')
        if queue_limit and len(api_state.job_queue) >= queue_limit:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Batch queue is at capacity; try again later",
            )

        files_limit = SECURITY_CONFIG.get('max_batch_files')
        if files_limit and len(payload.files) > files_limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Batch job exceeds max_batch_files ({files_limit})",
            )

        # Validate all files exist
        for file_name in payload.files:
            _get_authorized_file_path(file_name, user)

        # Create job
        job_data = {
            'job_id': job_id,
            'user': user['username'],
            'operation': payload.operation,
            'files': payload.files,
            'options': payload.options,
            'status': 'queued',
            'progress': 0.0,
            'completed_files': 0,
            'total_files': len(payload.files),
            'created_at': datetime.now(timezone.utc),
            'results': [],
            'started_at': None,
            'updated_at': None,
            'completed_at': None,
            'owner_clearance': user['clearance_level'],
            'owner_session_id': user['session_id'],
        }

        api_state.active_jobs[job_id] = job_data
        api_state.job_queue.append(job_id)

        client_ip = _get_request_ip(http_request)

        log_audit_event(
            user['username'], "BATCH_SUBMIT", job_id, "SUCCESS",
            f"Batch job submitted: {len(payload.files)} files",
            client_ip, user['session_id']
        )

        # Start background processing
        asyncio.create_task(process_batch_job(job_id))

        return BatchJobResponse(
            success=True,
            job_id=job_id,
            total_files=len(payload.files),
            estimated_duration=len(payload.files) * 5.0  # Estimate 5 seconds per file
        )

    except HTTPException as exc:
        _audit_denied(user, "BATCH_SUBMIT",
                      f"{len(payload.files)} files", exc, http_request)
        raise  # preserve 404 (missing file) / 403 (unauthorized) / 503 (queue full)
    except Exception as e:
        logging.error(f"Batch job submission error: {e}")
        return BatchJobResponse(
            success=False,
            error="Batch job submission failed"
        )

@app.get("/batch/status/{job_id}", response_model=BatchJobStatus)
async def get_batch_status(
    job_id: str,
    http_request: Request,
    user: dict = Depends(get_current_user)
):
    """Get batch job status"""
    if job_id not in api_state.active_jobs:
        _audit_denied(user, "BATCH_STATUS", job_id,
                      HTTPException(status.HTTP_404_NOT_FOUND, "Job not found"),
                      http_request)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    job_data = api_state.active_jobs[job_id]

    # Check if user owns this job or has admin privileges
    if (job_data['user'] != user['username'] and
        user['clearance_level'] not in PRIVILEGED_CLEARANCE):
        _audit_denied(user, "BATCH_STATUS", job_id,
                      HTTPException(status.HTTP_403_FORBIDDEN, "Access denied"),
                      http_request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    client_ip = _get_request_ip(http_request)
    log_audit_event(
        user['username'], "BATCH_STATUS", job_id, "SUCCESS",
        "Batch status retrieved", client_ip, user.get('session_id', '')
    )

    return BatchJobStatus(**job_data)

@app.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(http_request: Request, user: dict = Depends(require_permission("read"))):
    """Get system status and metrics"""
    uptime = time.time() - api_state.server_start_time

    memory_usage = 0.0
    cpu_usage = 0.0
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        with process.oneshot():
            memory_usage = process.memory_info().rss / (1024 * 1024)
            cpu_usage = process.cpu_percent(interval=0.1)

    histogram = api_state.stats['request_histogram_ms']
    p95_latency = None
    if histogram:
        sorted_hist = sorted(histogram)
        index = max(0, int(0.95 * (len(sorted_hist) - 1)))
        p95_latency = sorted_hist[index]

    requests_per_minute = float(len(api_state.request_window))

    response = SystemStatusResponse(
        status="operational",
        uptime=uptime,
        active_jobs=len([j for j in api_state.active_jobs.values() if j['status'] == 'processing']),
        queued_jobs=len(api_state.job_queue),
        completed_jobs=api_state.stats['completed_jobs'],
        error_rate=api_state.stats['failed_jobs'] / max(1, api_state.stats['total_requests']),
        memory_usage=memory_usage,
        cpu_usage=cpu_usage,
        # Derived, not a constant: a hardcoded "secure" would keep
        # reporting secure while the circuit breaker is open.
        security_status=(
            "degraded" if api_state.circuit_breaker_open else "secure"
        ),
        version=API_VERSION,
        active_sessions=len(api_state.active_sessions),
        last_request_timestamp=api_state.stats['last_request_timestamp'],
        last_job_error=api_state.stats['last_job_error'],
        circuit_breaker_open=api_state.circuit_breaker_open,
        request_latency_ms=api_state.stats['request_latency_ewma_ms'],
        request_latency_p95_ms=p95_latency,
        requests_per_minute=requests_per_minute,
    )

    client_ip = _get_request_ip(http_request)
    log_audit_event(
        user['username'], "SYSTEM_STATUS", "system", "SUCCESS",
        "System status inspected", client_ip, user['session_id']
    )

    return response

@app.get("/audit/log")
async def get_audit_log(
    http_request: Request,
    limit: int = Query(100, ge=1),
    user: dict = Depends(require_permission("audit"))
):
    """Get audit log entries"""
    entries = list(api_state.audit_log)[-limit:]

    client_ip = _get_request_ip(http_request)
    log_audit_event(
        user['username'], "AUDIT_READ", "audit_log", "SUCCESS",
        f"Fetched last {len(entries)} entries", client_ip, user['session_id']
    )

    return {
        "entries": [_model_to_dict(entry) for entry in entries],
        "total": len(api_state.audit_log)
    }

# Background job processing
async def process_batch_job(job_id: str):
    """Process batch job in background"""
    try:
        job_data = api_state.active_jobs[job_id]

        if api_state.circuit_breaker_open:
            job_data['status'] = 'failed'
            job_data['error'] = 'Circuit breaker open due to recent failures'
            job_data['completed_at'] = datetime.now(timezone.utc)
            api_state.stats['failed_jobs'] += 1
            if job_id in api_state.job_queue:
                api_state.job_queue.remove(job_id)
            _record_job_completion(job_id)
            return

        async with JOB_WORKER_SEMAPHORE:
            job_data['status'] = 'processing'
            job_data['started_at'] = datetime.now(timezone.utc)

            for i, file_name in enumerate(job_data['files']):
                file_path = _resolve_uploaded_path(file_name)
                job_data['current_file'] = file_name
                job_data['updated_at'] = datetime.now(timezone.utc)

                file_timeout = SECURITY_CONFIG.get('file_timeout_seconds') or None

                # Process file based on operation
                if job_data['operation'] == 'analyze':
                    try:
                        result = await asyncio.wait_for(
                            analyze_audio_fast(file_path), file_timeout)
                    except TimeoutError:
                        result = {
                            'success': False,
                            'error': f'timed out after {file_timeout}s',
                        }
                elif job_data['operation'] == 'normalize':
                    output_name = f"normalized_{uuid.uuid4().hex}_{file_name}"
                    sanitized_output = _sanitize_uploaded_name(output_name)
                    output_path = UPLOAD_DIRECTORY / sanitized_output
                    try:
                        _REQUEST_VALIDATOR.validate_file_path(output_path, operation="create")
                    except ChameleonSecurityError as exc:
                        result = {'success': False, 'error': str(exc)}
                    else:
                        try:
                            result = await asyncio.wait_for(
                                normalize_audio_fast(
                                    file_path, output_path,
                                    target_peak=job_data['options'].get(
                                        'target_peak', 0.95),
                                ),
                                file_timeout,
                            )
                        except TimeoutError:
                            result = {
                                'success': False,
                                'error': f'timed out after {file_timeout}s',
                            }
                        if result.get('success'):
                            try:
                                output_size = output_path.stat().st_size
                            except FileNotFoundError:
                                output_size = 0
                            api_state.register_generated_file(
                                sanitized_output,
                                owner=job_data['user'],
                                size=output_size,
                                source_files=[file_name],
                                operation='normalize',
                                session_id=job_data.get('owner_session_id'),
                            )
                            # Without this the output is registered for
                            # download under a name the client never learns.
                            result['output_file'] = sanitized_output
                else:
                    result = {'success': False, 'error': 'Unknown operation'}

                job_data['results'].append({
                    'file': file_name,
                    'result': result
                })
                _update_circuit_breaker(bool(result.get('success')))

                job_data['completed_files'] = i + 1
                job_data['progress'] = (i + 1) / job_data['total_files']

                # Pace between files, not after the last one -- a trailing
                # sleep delays the 'completed' write for no benefit (and
                # under a request-driven loop may never resume at all).
                if i + 1 < job_data['total_files']:
                    await asyncio.sleep(0.1)

            job_data['status'] = 'completed'
            job_data['completed_at'] = datetime.now(timezone.utc)
            api_state.stats['completed_jobs'] += 1

            # Remove from queue
            if job_id in api_state.job_queue:
                api_state.job_queue.remove(job_id)

            _record_job_completion(job_id)

    except asyncio.CancelledError:
        # A cancelled task must still leave an honest terminal state:
        # CancelledError is BaseException, so without this branch a
        # server-shutdown/teardown cancellation leaves the job stuck at
        # 'processing' forever -- indistinguishable from work in flight.
        job_data = api_state.active_jobs.get(job_id, {})
        job_data['status'] = 'failed'
        job_data['error'] = 'job cancelled'
        job_data['completed_at'] = datetime.now(timezone.utc)
        api_state.stats['failed_jobs'] += 1
        if job_id in api_state.job_queue:
            api_state.job_queue.remove(job_id)
        _record_job_completion(job_id)
        raise
    except Exception as e:
        logging.error(f"Batch job processing error: {e}")
        job_data['status'] = 'failed'
        job_data['error'] = str(e)
        api_state.stats['failed_jobs'] += 1
        if job_id in api_state.job_queue:
            api_state.job_queue.remove(job_id)
        _update_circuit_breaker(False)
        _record_job_completion(job_id)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize API server"""
    logging.basicConfig(level=logging.INFO)
    logging.info("Chameleon Audio API starting up...")

    # Create necessary directories
    try:
        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.error("Failed to establish upload directory: %s", exc)
        raise


# Main execution
if __name__ == "__main__":
    # Imported here, not at module scope: uvicorn is only needed to *run* the
    # server. Importing `app` (under gunicorn, or in tests) must not require it.
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        ssl_keyfile=None,  # In production: path to SSL key
        ssl_certfile=None,  # In production: path to SSL certificate
        log_level="info"
    )