# Chameleon — Category Research Round 2: Engineering & Product axes

Round 1 (`CATEGORY_RESEARCH.md`) covered the 10 **audio/DSP** categories. This
Round 2 covers 10 **engineering & product** categories — the cross-cutting
software-quality dimensions of the product — again with ~10 arXiv/GitHub/docs
sources each and improvement points mapped to Chameleon modules.

## The 10 categories (Round 2)
E1. CLI & UX design
E2. REST API & web-service architecture
E3. Packaging, distribution & dependency management
E4. Testing, fuzzing & test quality
E5. Performance, parallelism & memory efficiency
E6. Observability: logging, metrics, audit & error handling
E7. Configuration, plugin architecture & extensibility
E8. Metadata & DAW / interoperability
E9. Documentation, i18n & developer experience
E10. Deployment, containers & cross-platform distribution

Progress: 10 / 10 categories complete.

---
<!-- Sections appended below as each completes. -->

## E1. CLI & UX design

Current state: argparse CLI (`main.py`); partial `--dry-run`/JSON; no progress
bars, shell completion, config file, or fully consistent exit codes.

Sources (GitHub / docs):
1. Click — github.com/pallets/click — decorator subcommands, composition.
2. Typer — github.com/fastapi/typer — type-hint native, validation.
3. rich — github.com/Textualize/rich — progress bars, tables, consistent console.
4. tqdm — github.com/tqdm/tqdm — lightweight progress.
5. argcomplete — github.com/kislyuk/argcomplete — bash/zsh completion for argparse.
6. clig.dev — Command Line Interface Guidelines (output/help/errors).
7. tomllib (stdlib 3.11+) — TOML config files.
8. pydantic-settings — env+file settings with validation/merge precedence.
9. Dry-run / idempotency UX patterns (clig.dev, XDG base dirs).
10. sysexits.h — POSIX semantic exit codes (64 usage, 65 data, 74 I/O).

Top improvement points:
- **Standardized semantic exit codes** + structured errors in a new `cli_utils.py`
  (low effort, enables shell chaining); expand `--dry-run` to all mutating commands.
- **Progress bars** (rich/tqdm) for batch ops; consistent console output.
- **Config file** (`~/.chameleon/config.toml`, tomllib/pydantic-settings) with
  CLI>env>file>default precedence; shell completion via argcomplete. (Click/Typer
  migration is a larger, optional v2 step.)

## E2. REST API & web-service architecture

Current state: optional FastAPI `api_server.py` with HMAC tokens/audit/sessions
but no magic-byte validation, no readiness probe, list-based job queue, manual
deque rate limiting.

Sources (GitHub / docs):
1. FastAPI streaming uploads (#8167) — chunked read + running byte counter.
2. slowapi — github.com/laurentS/slowapi — Redis-backed distributed rate limiting.
3. starlette-exporter — Prometheus middleware + `/metrics`.
4. K8s liveness/readiness probe patterns — split `/health/live` + `/health/ready`.
5. file-validator / python-magic / puremagic — magic-byte upload validation.
6. FastAPI OAuth2-JWT guide — access+refresh tokens, revocation (JTI).
7. Taskiq — github.com/taskiq-python/taskiq — async distributed task queue.
8. python-rq — Redis job queue (POST→job_id, GET /jobs/{id}).
9. pydantic v2 validation — typed upload metadata models + validators.
10. asyncio.Queue(maxsize=…) — bounded queue with backpressure.

Top improvement points:
- **Magic-byte + streaming size validation** on uploads (reject non-audio/oversized
  mid-stream) and Pydantic-typed request models.
- **Async, persistent job queue** (Taskiq/RQ) for long ops, replacing the
  list-based queue + manual rate limiting (slowapi).
- **Observability endpoints**: split liveness/readiness + Prometheus `/metrics`.

## E3. Packaging, distribution & dependency management

Current state: flat layout; setup.py + pyproject.toml (version read from main.py
via regex — sync risk); three unpinned requirements files; single-stage Dockerfile.

Sources (PEPs / docs / GitHub):
1. PEP 621 — pyproject [project] metadata standard.
2. setuptools dependency-management guide — optional-dependencies/extras.
3. PyPA "writing pyproject.toml" — declarative config, drop setup.py.
4. uv — docs.astral.sh/uv — fast resolver + `uv.lock`.
5. pip-tools — pip-compile lock + hashes from `.in` files.
6. pip-audit (+ supply-chain hardening, SBOM/CycloneDX).
7. Multi-stage Docker for Python (wheels in builder → slim runtime).
8. twine + `python -m build` — release workflow.
9. PEP 517/518 — explicit `[build-system]`.
10. PyPA src-layout vs flat-layout discussion.

Top improvement points:
- **Single-source metadata/version** in `pyproject.toml` (`[tool.setuptools.dynamic]`),
  retire setup.py duplication.
- **Lock dependencies** (uv or pip-tools `.in`→pinned+hashed) and commit lockfiles;
  structure extras as `api`/`enhanced`/`dev`.
- **Multi-stage Docker** (build wheels → slim runtime) + **pip-audit/SBOM** in CI.

## E4. Testing, fuzzing & test quality

Current state: test_core.py + tests/ smoke + validation_test.py; no
property-based tests, fuzzing, coverage gate, or perf regression tests; hand-rolled
struct WAV parser.

Sources (GitHub / docs / papers):
1. Hypothesis — property-based tests (generate valid + malformed WAV specs).
2. atheris — github.com/google/atheris — coverage-guided fuzzing of the WAV parser.
3. pytest fixtures/parametrize — consolidate channel/op matrices.
4. pytest-benchmark — perf regression gate on analyze/normalize/trim.
5. syrupy — snapshot testing of WAV output bytes.
6. Harness-generation for binary parsers — arXiv 2306.15596 — structure-aware fuzz.
7. mutmut / cosmic-ray — mutation testing to validate test strength.
8. tox / nox — Python 3.9–3.13 matrices (struct/endianness consistency).
9. numpy.testing.assert_allclose — tolerance-based DSP numerical tests.
10. audio round-trip/snapshot testing — verify duration/rate/channels preserved.

Top improvement points:
- **Fuzz the WAV parser** (atheris) + **property tests** (Hypothesis) — highest ROI
  for a hand-rolled binary parser.
- Add **coverage gate** + **snapshot/round-trip** output tests (not just
  `result.success`), with numpy tolerance checks for DSP.
- **pytest-benchmark** perf gate and **tox/nox** multi-version matrix in CI.

## E5. Performance, parallelism & memory efficiency

Current state: `performance_optimizer.py` (ParallelProcessor, ThreadPool/Process,
`SIMDOperations` using stdlib `array`), MemoryManager LRU, chunked WAV; numpy optional.

Sources (GitHub / docs / PEPs):
1. NumPy vectorization/broadcasting — SIMD without interpreter overhead.
2. Numba JIT — numba.pydata.org — @njit for tight DSP loops.
3. Free-threading / no-GIL — PEP 703 (Python 3.13+) — thread scaling.
4. Sub-interpreters — PEP 734 — per-interpreter GIL middle ground.
5. multiprocessing vs threading (RealPython) — CPU-bound needs processes.
6. joblib (loky) — auto-memmap >1MB, safe oversubscription.
7. numpy.memmap / mmap — random-access large audio without RAM blowup.
8. Scalene / py-spy / line_profiler — find Python vs native hotspots.
9. ProcessPoolExecutor pitfalls — pickle only paths, load audio in worker.
10. Chunked/streaming bounded memory — adaptive chunk size by available RAM.

Top improvement points:
- **Vectorize `SIMDOperations`** with NumPy (and optional **numba** JIT) — the
  current stdlib-`array` loops lose SIMD; 10–100× on DSP hot paths (numpy-gated).
- **Pass file paths, not audio buffers**, to process pools; consider **joblib
  loky + memmap** for large files; add `CHAMELEON_MAX_MEMORY_MB` adaptive chunking.
- Add a `--profile` (Scalene) path and validate **free-threading (3.13+)** scaling.

## E6. Observability: logging, metrics, audit & error handling

Current state: stdlib logging (RotatingFileHandler), custom StructuredLogger,
audit logs, ~78 broad try/except (some bare).

Sources (GitHub / docs):
1. structlog — github.com/hynek/structlog — processor-pipeline structured logs.
2. python-json-logger — JSON formatter for stdlib logging.
3. OpenTelemetry Python — traces/metrics/logs, auto-instrumentation.
4. prometheus client_python — Counter/Histogram, multiprocess mode + `/metrics`.
5. Sentry SDK — error aggregation/dedup with context.
6. asgi-correlation-id — request/correlation IDs across async.
7. tamper-evident append-only audit (hash-chain/HMAC) — audit integrity.
8. secret/PII redaction in logs (MaskerLogger) — never log secrets.
9. logging dictConfig — declarative config, runtime levels.
10. bare-except guidance (pylint) — specific exception taxonomy.

Top improvement points:
- Replace the custom JSON logger with **structlog/python-json-logger** and use
  **dictConfig**; add **secret/PII redaction**.
- **Exception taxonomy**: eliminate bare `except:`, catch specific types; optional
  Sentry; correlation IDs in `api_server.py`.
- **Metrics** (Prometheus `/metrics`) + **tamper-evident audit log** (HMAC/hash-chain).

## E7. Configuration, plugin architecture & extensibility

Current state: `plugin_system.py` AST-allowlist + resource limits, in-process,
filesystem discovery; `config_manager.py` manual coercion.

Sources (GitHub / docs):
1. pluggy — github.com/pytest-dev/pluggy — hookspec/hookimpl plugin contracts.
2. stevedore — entry-point plugin discovery (OpenStack).
3. PyPA "creating & discovering plugins" — entry_points/importlib.metadata.
4. RestrictedPython docs — AST sandbox is NOT a security boundary.
5. Figma "containers and seccomp" — isolation tiers comparison.
6. nsjail — namespaces+cgroups+seccomp, <100 ms startup.
7. pydantic JSON Schema — typed/validated plugin config + param schemas.
8. python-semver — enforce plugin API version compatibility.
9. wasmtime/WASI — hard-isolation sandbox for untrusted plugins.
10. Python Stable ABI (PEP 384) — version-independent C-extension plugins.

Top improvement points:
- **Entry-point plugin discovery** (importlib.metadata/pluggy) so plugins ship via
  PyPI, replacing fragile filesystem scanning.
- **Document the AST sandbox is resource-control only**, add optional
  **subprocess+seccomp/nsjail/WASM** isolation modes for untrusted plugins.
- **Pydantic-validated config** + **semver API compatibility** checks at load time.

## E8. Metadata & DAW / interoperability

Current state: `mutagen` declared but unused; no BWF/iXML/cue/loudness metadata;
metadata dropped across batch; MIDI via custom writer.

Sources (GitHub / standards):
1. mutagen — ID3v2/RIFF-INFO (no bext/iXML/cue) — use what it can.
2. EBU Tech 3285 (BWF/bext) — broadcast metadata + loudness fields.
3. wave-bwf-rf64 — github.com/nrkno/wave-bwf-rf64 — bext/RF64/levl/chna read-write.
4. wavinfo — github.com/iluvcapra/wavinfo — read bext/iXML/cue/ADM.
5. loudgain — github.com/Moonbase59/loudgain — ReplayGain/EBU R128 (libebur128).
6. BWFMetaEdit — github.com/MediaArea/BWFMetaEdit — validation rules reference.
7. Essentia — Chromaprint + descriptors for fingerprint metadata.
8. music21 — metadata-preserving MIDI + MusicXML export for DAWs.
9. Chromaprint/AcoustID — fingerprint → MusicBrainz metadata lookup.
10. Sidecar `.meta.json` pattern — portable metadata across lossy ops.

Top improvement points:
- New **`metadata.py`** unifying read/write of tags + **BWF bext / iXML / cue /
  loudness** (wave-bwf-rf64 + wavinfo + mutagen).
- **Preserve metadata across batch** (extract→sidecar JSON→re-embed) and add EBU
  R128 loudness tagging (loudgain/libebur128).
- Use **music21** for metadata-preserving MIDI + **MusicXML** export (DAW interop).

## E9. Documentation, i18n & developer experience

Current state: scattered README/QUICKSTART/DEPLOYMENT_GUIDE/MIDI_USAGE +
docs/en & docs/ja (partial stubs) + openapi_spec.yaml; no docs site, no
CONTRIBUTING, no auto API docs.

Sources (tools / docs):
1. Sphinx + autodoc + napoleon — auto API docs from docstrings.
2. MkDocs Material — github.com/squidfunk/mkdocs-material — docs site + search.
3. Read the Docs — hosting, PR previews, versioned docs.
4. Diátaxis — diataxis.fr — tutorial/how-to/reference/explanation structure.
5. Redoc — render openapi_spec.yaml as interactive API reference.
6. doctest — executable examples keep docs in sync.
7. mkdocs-static-i18n — github.com/ultrabug/mkdocs-static-i18n — complete ja/ docs.
8. towncrier — news-fragment changelog automation (avoids merge conflicts).
9. GitHub community files — CONTRIBUTING/CODE_OF_CONDUCT/issue templates.
10. pdoc3 — zero-config interim API docs.

Top improvement points:
- Adopt a **docs site** (MkDocs Material) structured by **Diátaxis**, hosted on
  Read the Docs; render the **OpenAPI** spec via Redoc/FastAPI `/docs`.
- **Standardize docstrings** (Google/NumPy) + autodoc + **doctest** so examples
  are tested; complete the **ja/** translations via mkdocs-static-i18n.
- Add **CONTRIBUTING/CODE_OF_CONDUCT/issue templates** and **towncrier** changelog.

## E10. Deployment, containers & cross-platform distribution

Current state: Dockerfile + k8s-deployment.yaml + DEPLOYMENT_GUIDE.md; needs
audio system libs (libsndfile/portaudio/ffmpeg); k8s has hardcoded base64 secrets.

Sources (docs / GitHub):
1. Docker Python best practices — multi-stage, non-root USER, .dockerignore, HEALTHCHECK.
2. Kubernetes liveness/readiness/startup probes — tune for audio-lib init time.
3. Chainguard/distroless Python images — near-zero-CVE runtime + SBOM.
4. hadolint — github.com/hadolint/hadolint — Dockerfile linting in CI.
5. Trivy / Grype — image vulnerability scanning.
6. Syft — github.com/anchore/syft — SBOM (SPDX/CycloneDX) generation.
7. Reproducible Docker builds — pinned digest, locked deps, SOURCE_DATE_EPOCH.
8. PyInstaller / Nuitka — standalone Windows/macOS CLI binaries.
9. conda-forge / Homebrew / pipx — cross-platform install channels.
10. Sigstore/cosign — keyless image signing + admission verification.

Top improvement points:
- Harden the image: **non-root user, .dockerignore, HEALTHCHECK, pinned digest**,
  multi-stage wheels; consider **distroless/Chainguard** runtime.
- Add **image scanning (Trivy) + SBOM (Syft) + signing (cosign)** to CI; move the
  **hardcoded k8s secrets** to external secret management.
- Broaden distribution: **pipx**, **conda-forge/Homebrew**, optional
  **PyInstaller** binaries; tune **k8s probes** for audio-lib startup.

---

## Round 2 synthesis — highest-leverage engineering improvements

Ranked by value ÷ effort:

1. **Harden + fuzz the WAV parser** (E4) — also a security item; atheris +
   Hypothesis on the hand-rolled `struct` parser is the top engineering risk.
2. **Single-source packaging + dependency locking** (E3) — retire setup.py
   duplication, lock deps (uv/pip-tools), structure extras; fixes a real
   version-sync footgun.
3. **CLI polish** (E1) — semantic exit codes + `--dry-run` everywhere + progress
   bars: cheap, high day-to-day UX gain.
4. **Vectorize hot DSP loops** (E5) — NumPy/numba replacing stdlib-`array` loops
   (numpy-gated) for large speedups.
5. **Observability hygiene** (E6) — kill bare-except, structured logging + secret
   redaction; metrics endpoint for the API.
6. **API hardening + async jobs** (E2) and **container scanning/SBOM/signing**
   (E10) for production readiness.
7. **Metadata preservation** (E8), **entry-point + isolated plugins** (E7), and a
   **Diátaxis docs site with finished ja/ translations** (E9).

Cross-link: several items reinforce Round 1 / IMPROVEMENT_RESEARCH (WAV parser
hardening, metadata/BWF, quality metrics, plugin isolation). All heavier tools
remain optional dependencies with graceful degradation.
