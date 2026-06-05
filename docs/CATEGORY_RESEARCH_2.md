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

Progress: 3 / 10 categories complete (E1 pending in this wave).

---
<!-- Sections appended below as each completes. -->

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
