# Chameleon Project Charter

This charter is the project's north star. It exists because the git history shows a
repeating cycle: ambitious features (quantum, neural, GPU, "enterprise") are added,
then later removed as non-functional. Individual bug fixes do not stop that cycle —
only an explicit, agreed scope does. Read this before adding any feature.

Status: Beta. Honest scope below.

## 1. Job to be done

Chameleon is a **dependency-light, auditable WAV processing CLI** for users who need
deterministic, scriptable batch operations on uncompressed audio with a verifiable
security boundary around file access.

The differentiator is **not** breadth of formats or speed (ffmpeg, sox and librosa win
there). It is: *runs with zero third-party dependencies, validates every path against a
trusted-root policy, and produces reproducible results with a verifiable access record
suitable for locked-down or air-gapped environments.* If a change does not serve that, it
is out of scope.

**What "auditable" means here:** the `SecurityValidator` rejects paths outside configured
trusted roots and logs each access decision. That is the audit trail — not a separate
compliance layer. Do not add a heavier logging system without a concrete requirement;
equally, do not claim richer audit capabilities than this.

## 2. Target user

Someone scripting WAV analysis/normalization/batch/MIDI extraction in an environment
where installing numpy/ffmpeg is undesirable or disallowed, and where "which files did
this touch" must be answerable. Not a general-purpose audio editor user.

## 3. Honest current limitations (do not paper over these)

- **WAV only, by default.** `main.py`'s own `HAS_LIBROSA`/`HAS_SOUNDFILE` gate gives
  MP3/FLAC/OGG support *only* if the `[audio]` extra (soundfile/librosa) is installed, and
  `load_audio` requires numpy. The default install (`requirements.txt`) installs none of
  these, so out of the box the product is WAV-only. Advertise this plainly; do not call it
  "multi-format" without the optional extras.
- **Optional features are genuinely optional.** Anything needing numpy/scipy/librosa/
  pyaudio/mido/fastapi must degrade gracefully and be labelled as requiring extras.
- **The REST API is a thin adapter over the stdlib core**, not an enterprise platform.
  Session auth, audit logging and rate-limiting exist but defend a narrow threat
  model (see §5). There is no per-permission authorization — `require_permission`
  names a permission it does not enforce, and says so.

## 4. Non-goals (anti-scope — reject PRs that add these)

- Quantum / neural / GPU / "AI transcription" / spatial-audio features. (All previously
  added and removed. Do not reintroduce.)
- Marketing-grade "enterprise/production-grade/military" claims unbacked by tests.
- New top-level audio formats implemented from scratch in-tree. Use optional libraries
  behind the existing `HAS_*` capability flags instead.
- Multi-language classifier inflation, fantasy deployment pipelines (k8s/staging/prod
  jobs) that reference scripts which do not exist.
- A second product. Keep the CLI core and the optional API aligned; do not let the API
  grow a divergent feature set.

## 5. Threat model (so security effort stays justified)

The security layer (~1,100 lines across `security_validator.py`, `advanced_validation.py`,
`plugin_system.py`) defends exactly these cases — keep investment proportional to them:

- **Path traversal / untrusted paths**: a caller (e.g. via the API or a batch manifest)
  supplies a path that escapes the configured trusted roots. Mitigation: `SecurityValidator`.
- **Hostile plugins**: third-party plugin code executing outside an AST/import whitelist.
  Mitigation: `plugin_system` sandbox.
- **Resource exhaustion**: oversized files. Mitigation: 500MB size cap.

**Wiring caveat (be honest about what actually runs):** `security_validator.py`
(path/size checks) is wired into the default batch/load paths
(`main.py:_filter_safe_files`, `core.py:BatchProcessor`) and `plugin_system.py` into
plugin loading. As of 2026-06, `advanced_validation.py`'s `DeepFileInspector` is **also**
wired into `main.py:_filter_safe_files`: for files claiming a `.wav` extension it
validates the actual WAV magic number (via `validate_for_processing`, a checksum-free
variant) and rejects containers that are not real WAVs — e.g. an executable renamed to
`.wav`. It gates only on the magic number; suspicious byte patterns inside the payload are
logged, never rejected, because a WAV's PCM data can legitimately contain them. The other
two helpers (`IntegrityVerifier`, `SanitizationEngine`) remain opt-in via
`personal_config.py` by design — they are checksum-manifest / metadata-stripping tools, not
per-request gates — so do not describe them as always-on. Wiring `DeepFileInspector` into
`core.py:BatchProcessor` for parity is an optional follow-up (§9).

Out of model: defending a single user against their own local files. Do not add security
machinery that only makes sense for a hosted multi-tenant service unless the API actually
becomes one (which is itself a Non-goal here).

## 6. Definition of done for any new feature

A change may merge only if it:

1. Serves the Job to be done (§1) and violates no Non-goal (§4).
2. Works — or degrades gracefully with a clear message — under the **default,
   dependency-free install**. No import of a deleted/optional module at top level without
   a guarded `try/except` and a `HAS_*` flag.
3. Ships tests that run in CI under the stdlib-only matrix (`python -m pytest -q`).
4. Updates docs to match reality (no claim without a backing test or working code path).
5. Leaves `python -m compileall -q .`, `python validation_test.py`, and `pytest` green.

## 7. Open strategic questions (decide before large investment)

These follow from a Socratic review of the product's reason to exist; they are recorded
here so the next contributor does not skip them:

- **Reason to exist:** is "zero-dependency auditable WAV batch processing" a real need
  for a real user, or should the project pivot to being a thin, honest wrapper around
  ffmpeg/librosa? Pick one before adding features.
  **Decided (2026-06):** the two are layers, not alternatives. The stdlib WAV core is the
  differentiator (zero-dependency, auditable, air-gap safe). The `[audio]` extra is
  convenience layered on top — it does not change the product's identity. The claim
  "auditable WAV batch processing" belongs to the core only; the extra is not the
  differentiator and should not be marketed as such.
- **Codec gap:** real audio is mostly MP3/FLAC. Either commit to optional-codec support
  as a first-class, documented path, or stay explicitly WAV-only — but stop straddling.
  **Decided (2026-06):** optional-codec is now a first-class, *documented* path via the
  `[audio]` extra. `main.py`'s `SUPPORTED_FORMATS` is gated on the installed backend, so
  MP3/FLAC/OGG input works once `pip install -e .[audio]` is run, while the default
  install stays honestly WAV-only (§3). The straddle is resolved; do not reintroduce a
  static gate that rejects formats the loader can actually decode.
- **CLI vs API:** if the API is not going to be a hosted service, consider trimming its
  enterprise surface to match the local-tool threat model.
  **Decided (2026-06):** the API is a local adapter over the stdlib core, not a hosted
  service. Its session auth / rate-limiting / audit-log exist to defend the §5 threat model
  (path traversal via API callers, resource exhaustion, hostile plugins) — not to build a
  multi-tenant platform. Do not grow the API surface beyond what that model requires. The
  non-goal (§4) against "a second product" applies: the API must stay aligned with the
  CLI core, not develop a divergent feature set.

## 8. Success metrics (is the charter working?)

§6 gates an individual change. These gate the *product*: they measure whether the cycle
this charter exists to stop (fantasy features, claim/reality drift) is actually staying
stopped. Check them at review time; a regression in any is a signal to pause feature work.

1. **Soundness — zero red on the default branch.** Every commit keeps
   `python -m compileall -q .`, `python validation_test.py`, and `python -m pytest -q`
   green under the stdlib-only install. Target: 0 broken commits on the main branch.
2. **Honesty — zero unbacked claims.** Every capability advertised in README / docs maps
   to a passing test or a demonstrably working code path. Each supported format/feature
   has a backing test or documented command. Target: 0 claims without backing.
3. **Activation — first success in under 5 minutes.** A new user goes from clone to a
   successful `analyze` on their own file in <5 min by following QUICKSTART (WAV by
   default; MP3/FLAC via the `[audio]` extra), with no undocumented step.
4. **Scope discipline — zero non-goal regressions.** No §4 non-goal
   (quantum/neural/GPU/"enterprise"/multi-language inflation/fantasy pipelines) is
   reintroduced. Target: 0, watchable by a grep over the tree in review or CI.

## 9. Socratic record

A living log of questions the Socratic review raised and how they were resolved. Update
this section instead of re-litigating closed decisions.

### Resolved questions

**Q: What does "auditable" concretely mean in this codebase?**
A (2026-06): The audit trail is `SecurityValidator`: every file-access attempt is checked
against a trusted-root allowlist, and rejections are logged. That is the full scope of
the claim. There is no separate compliance log; §1 was updated to say "verifiable access
record" rather than "audit-logged results" to match the implementation. See §1 and §5.

**Q: Codec gap — stay WAV-only or commit to optional-codec?**
A (2026-06): Commit to optional-codec as a first-class, *documented* path via `[audio]`
extra. Default install stays WAV-only. `main.py`'s `SUPPORTED_FORMATS` is now dynamic:
gated on the installed backend so the gate matches reality. See §7.

**Q: Reason to exist — differentiator core vs. thin librosa wrapper?**
A (2026-06): Two layers, not a binary choice. The stdlib WAV core is the differentiator.
The `[audio]` extra is layered convenience. Claims of "auditable / zero-dependency"
belong to the core layer only. See §7.

**Q: API ghost parameters — `enable_simd` / `parallel_processing` in request models?**
A (2026-06): Removed. These fields were accepted by `AudioAnalysisRequest` and
`AudioNormalizationRequest` but never forwarded to the processing core. Accepting a
parameter without acting on it is the same structural problem as the fantasy features
this charter exists to prevent: a claim implied by the interface, unbacked by code.

**Q: Does the §5 security layer actually run on the default path?**
A (2026-06): Partly. `security_validator.py` and `plugin_system.py` are wired in;
`advanced_validation.py` is not (only reachable via `personal_config.py`). §5 now states
this caveat explicitly instead of implying all 1,100 lines defend every request. Whether
to integrate `advanced_validation.py` into the default path is an open question below.
`tests/test_security.py` now exercises `SecurityValidator` directly (path shape, trusted
roots, extension allowlist, size limit) rather than relying on `validation_test.py`'s
hand-rolled re-implementation. Extended 2026-09-19 to the raising side:
`validate_file_path`/`validate_directory` rejection reasons, `safe_open_file`'s
`None` contract, `sanitize_filename`, and `SecurityConfig.from_environment`
parsing. Verified while writing them: `validate_*` resolves the path *before*
the shape check, so a raw `..` disappears into the resolved path and is caught
by the trusted-roots check, not the traversal-pattern check — the shape
patterns only fire on suspicious characters surviving into the resolved path.

**Q: Neural / source-separation modules still shipped despite §4?**
A (2026-06): Removed `music_generator.py`, `audio_enhancer.py`, and
`advanced_audio_features.py`. All three were orphaned (referenced only in packaging
metadata, never imported by the CLI/core), untested, and claimed neural networks while
either running `random.choice` placeholders or importing torch unconditionally (breaking
the stdlib install). They were residue of the add-then-remove cycle §4 exists to stop —
removed the same way quantum was.

**Q: How is §8.4 scope discipline actually enforced?**
A (2026-06): By `tests/test_no_fantasy_features.py`, which greps the Python sources for
reintroduced §4 non-goals (torch/tensorflow imports, `nn.Module`/`nn.LSTM`, "neural
network", spleeter, "quantum computing/processing") and fails the suite on a hit, while
allowing lines that document a removal. This runs in the ordinary `pytest` suite, so it
needs no `workflows` permission and executes on every commit.

**Q: Should `advanced_validation.py` run on the default path (§5 gap)?**
A (2026-06): Yes, partially. `DeepFileInspector` is now wired into
`main.py:_filter_safe_files` via a checksum-free `validate_for_processing`, so the default
batch path rejects files whose `.wav` extension lies about their contents. The gate keys
only on the WAV magic number (zero false positives on real audio); suspicious payload
bytes are logged, not rejected. `tests/test_advanced_validation_integration.py` covers the
pass / reject / false-positive-guard cases. `IntegrityVerifier` and `SanitizationEngine`
stay opt-in by design. This makes the §5 claim true instead of merely documented.

**Q: Does the trusted-root check actually contain paths (§5 path-traversal)?**
A (2026-06): It does now. `_is_within_trusted_roots` previously used
`str.startswith`, which wrongly accepted a sibling like `/data/safe-evil` for a
`/data/safe` root (a documented path-containment pitfall — see the Zenn/Qiita
directory-traversal write-ups). Replaced with `os.path.commonpath` (component-wise
containment) plus resolving each root, so prefix-collision siblings are rejected while
genuinely nested files still pass. Regression guards:
`tests/test_security.py::TestTrustedRoots::test_prefix_collision_does_not_bypass_root`
and `test_root_itself_and_nested_file_accepted`.

**Q: CLI exit codes — worth a richer table, or does it conflict with minimalism?**
A (2026-07): Added a small `ExitCode(IntEnum)` in `main.py` — `OK=0`, `ERROR=1`,
`USAGE=2`, `INPUT=3`, `SECURITY=4`, `INTERRUPTED=130` — and mapped every existing
`return`/`exit_code=` site in `main()` to the matching category instead of the prior
0/1-only scheme (this also fixed two bugs found in the process: the `midi generate`
handler returning bare `None` — exit 0 — on a usage error, and `cli()` not catching
`KeyboardInterrupt`, so Ctrl-C surfaced as a traceback instead of exit 130). No new
dependency: `enum` is stdlib, so this doesn't conflict with §3's zero-dependency core.
`tests/test_exit_codes.py` invokes the CLI as a real subprocess and asserts on
`returncode` for each category — the first tests in the suite that exercise the actual
`sys.exit(cli())` path rather than calling `main()`'s Python-level return value.

**Q: Was `codec_support.py` actually the MP3/FLAC/OGG mechanism §3 credited it as?**
A (2026-07): No — and that was a §8.2 honesty bug in the charter's own text, not just in
code. `codec_support.py` was never imported by `main.py` or anything else (only its own
`__main__` demo block and the packaging lists referenced it); the real gating is
`main.py`'s own `HAS_LIBROSA`/`HAS_SOUNDFILE` branches. `codec_support.py` also imported
`numpy` unconditionally at module top level, so it broke import under the stdlib-only
default install — the same defect class as the neural modules removed earlier this
charter. Deleted the file, dropped it from `setup.py`/`pyproject.toml` py-modules, and
corrected §3 to credit the mechanism that actually runs.

**Q: Ghost CLI parameters / unreachable CLI options — same pattern as api_server's?**
A (2026-07): Yes, found by a fresh excess/deficiency audit; fixed the same way the
api_server ghost parameters were (§9, above): removed what nothing implements
(`process --parallel`, `ml enhance --model`, `stream --monitor`), wired what core/main
already supported but argparse never exposed (`--target-peak` on `process`/`batch`
normalize, a `batch effects` operation), and fixed `stream --input-device`/
`--output-device`, which weren't just unreachable but actively broken — `process_stream`'s
parameters were misnamed (`input_callback`/`output_callback`) and never used in the
method body, so device selection silently did nothing regardless of what the CLI passed.
See `tests/test_cli_parity.py`.

**Q: Orphaned module punch list — wire in, or delete, each of the 9?**
A (2026-07): Reviewed individually (user-confirmed per module), rather than a blanket
action:
- **Deleted** (orphaned + duplicate of functionality already implemented and wired
  elsewhere): `realtime_effects.py` (duplicated `main.py`'s already-wired
  `process_stream`/`apply_effects` real-time pyaudio path — keeping two parallel
  real-time engines would itself violate §4's "no second product"),
  `stability_enhancer.py` (duplicated `core.py`'s already-wired `RecoveryManager` /
  `ErrorAnalyzer` / `ServiceDegradationManager` / `StateRecoveryManager`),
  `audio_utils.py` (duplicated `core.py:WAVProcessor`'s already-wired RIFF/WAV parsing,
  which additionally has memory-mapped caching this module lacked), `config_manager.py`
  (duplicated environment-variable config resolution that already exists in *two* other
  places — `core.py` and `main.py:ProcessingConfig.from_environment` — so wiring it in
  would have added a third, divergent source of truth instead of fixing that existing
  fragmentation). All four also imported `numpy`/non-stdlib packages unconditionally
  where guarded imports existed elsewhere, matching the exact defect class that killed
  `codec_support.py`. `tests/test_smoke.py`'s `CORE_MODULES` list and
  `personal_config.py`'s `audio-info` alias (which shelled out to the now-deleted
  `audio_utils.py`, redundant with the existing `audio-analyze` alias) were updated to
  match.
- **User approved wiring in** (real, working, non-duplicative — fills an actual gap):
  `mastering_chain.py`, `ux_improvements.py`, `spectral_utils.py`. Each gets its own
  wiring commit (CLI subcommand/flag + tests) rather than a blanket change.
  - `ux_improvements.py` (2026-07, done): `main.py:AudioProcessor.batch_process` gained
    an opt-in `show_progress` keyword that renders `ProgressBar` as files complete; the
    CLI's `batch` command passes `show_progress=sys.stdout.isatty()` (so captured/piped
    output and tests stay unaffected) and colorizes its final summary line with
    `ColorText.success`/`ColorText.error`. `ErrorFormatter`/`TableFormatter`/
    `SpinnerAnimation` remain real and importable but unused for now — `ErrorFormatter`'s
    suggestion API needs an `Exception` instance, and `batch_process`'s result dicts only
    carry `str(exc)`, so wiring it in would need a wider change to what errors carry
    through the pipeline; left for a future pass rather than forced in. See
    `tests/test_ux_wiring.py`.
  - `spectral_utils.py` (2026-07, done): added `core.py:WAVProcessor.get_samples_for_analysis`
    (module-level `core.get_samples_for_analysis`) — a bounded (default 65,536 samples),
    mono-mixed, *signed* waveform reader built on the same chunked-read pattern as
    `_calculate_levels_safe`. It needed a new `_normalize_amplitude_signed` because the
    existing `_normalize_amplitude` discards sign (`abs(value)`) — correct for peak/RMS,
    wrong for spectral analysis, which needs the real waveform. Exposed as
    `analyze --spectrum`, printing dominant frequencies/bandwidth/RMS via
    `spectral_utils.analyze_spectrum`, guarded behind `HAS_SPECTRAL_UTILS`. Verified
    end-to-end against synthetic tones (a 440Hz/880Hz sine correctly reports its peak
    within 5Hz). Notably this closes a real gap, not just an orphaned-module cleanup:
    `--detailed`'s existing `frequency_range`/`spectral_centroid` fields only populate
    when librosa is installed, so the default stdlib-only install previously had *no*
    spectral analysis at all — `--spectrum` gives it one, matching the differentiator §1
    already claims (deterministic analysis without mandatory heavy dependencies). See
    `tests/test_spectral_wiring.py`.
  - `mastering_chain.py` (2026-07, done): exposed as `process --master
    {default,streaming,cd,vinyl}`, a new operation alongside the existing
    normalize/denoise/effects/convert. Guarded the same way `HAS_LIBROSA`/
    `HAS_SOUNDFILE` already are — `mastering_chain.py` imports `numpy`
    unconditionally, so `try: from mastering_chain import ...` simply fails
    under the stdlib-only default install, exactly like the other optional
    backends; no change needed inside `mastering_chain.py` itself, since scipy
    is already optional *within* it (each processor degrades individually when
    scipy is absent). `_process_single_file`'s existing "requires numpy" error
    for non-analyze/normalize operations covers the `HAS_NUMPY=False` case for
    free. Verified end-to-end: a synthetic tone processed through the
    `streaming` preset produces a valid, playable stereo WAV with reported
    LUFS/peak-change metrics. See `tests/test_mastering_wiring.py`. This
    closes the last item on the wiring-in list from the orphaned-module
    review; all three approved-for-wiring modules
    (`ux_improvements.py`/`spectral_utils.py`/`mastering_chain.py`) are now
    real, tested, importable parts of the CLI rather than unreferenced files.
- **Left orphaned, deliberately** (real and non-duplicative, but wiring in is a product
  scope decision, not a mechanical fix): `spectral_editor.py` (a full interactive
  spectral editor — selection regions, undo, visualization — a larger surface than the
  CLI's batch-WAV job-to-be-done), `audio_restoration.py` (real DSP — click/hum/clip
  repair — but imports numpy/scipy unconditionally and needs the same guard fix plus a
  new CLI subcommand before it could ship), `batch_automation.py` (a genuine DAG/
  scheduler engine, but wiring a generic task-orchestration framework into a
  "dependency-light auditable CLI" risks exactly the §4 "second product" non-goal — its
  own demo workflow references multi-format transcoding and "enhance audio quality" in
  the same illustrative-but-fantasy-adjacent style already removed elsewhere). Recorded
  here rather than turned into an open question, since the user has already decided:
  leave orphaned until someone makes an explicit case for one of them.

**Q: Is the WAV core actually commercial-grade on real-world files?**
A (2026-07): It wasn't — and the failure was silent, the worst kind. Every
data-reading/writing path assumed "data starts at byte 44", so WAVs carrying
LIST/INFO metadata, JUNK padding (routine in DAW exports), fact chunks, or
18/40-byte fmt bodies got wrong peak/RMS analysis and corrupt
normalize/mono/trim output with no error — while three chunk-walking parsers
already existed in the repo with their knowledge discarded. Fixed by making
`_read_wav_header` the canonical chunk-walking parser (fmt 16/18/40,
WAVE_FORMAT_EXTENSIBLE PCM GUID accepted, float32 rejected cleanly, odd-chunk
pad bytes, size clamping), recording `data_offset`/`data_size`/`fmt_offset`
in `AudioInfo`, threading them through every reader/writer, sharing one
header-copy-and-patch helper for writers (input header prefix preserved
verbatim; trailing post-data chunks deliberately dropped — documented), and
fixing frame splits at read-chunk boundaries (CHUNK_SIZE is not a multiple of
24-bit frame sizes). `main._load_wav_basic` got a real decode table (8-bit
offset, 24-bit sign extension, int32-vs-float32 by format tag, EXTENSIBLE via
GUID, clear errors otherwise). `tests/test_wav_chunks.py` pins all of it with
hand-assembled fixtures compared against plain-44-byte twins.

**Q: Commercial-grade CLI behavior — stderr, --version, quiet default?**
A (2026-07): Diagnostics now go to stderr (previously 0 of 76 prints did, so
piping stdout captured error text); `--version` added and the stale "v3.0"
help banner replaced, with pyproject switching to a dynamic version sourced
from `main.VERSION` (one truth, matching setup.py); import-time optional-dep
UserWarnings became debug-level logs (missing extras are the *normal* state
of the honest default install — features raise actionable errors at the point
of use instead); and the tree is deprecation-clean on Python 3.12/3.13
(utcnow → now(timezone.utc), get_event_loop → get_running_loop/asyncio.run).
README/QUICKSTART were re-synced to the actual CLI surface (--spectrum,
--master, --target-peak, batch effects, exit-code table, `chameleon` console
script) — docs had fallen *behind* the code, the inverse of the failure mode
this charter was written against, and QUICKSTART still referenced the deleted
`audio_utils.py`. `tests/test_cli_polish.py` pins the contract.

**Q: What are this product's actual user-facing surfaces (frontend audit)?**
A (2026-07): CLI + a pure-JSON FastAPI REST server. No web UI ships: `gui/`
is a self-labeled experimental React/TypeScript/Electron scaffold ("the
Electron backend integration with the Python CLI is not yet wired up" — its
own README), not built by the Dockerfile, not referenced by `api_server.py`
(no `StaticFiles`/`Jinja2`/`HTMLResponse`). `core.py`'s `RealtimeAudioProcessor`
(~L2809-3195, a standalone `websockets`-based server) has zero callers from
`main.py` or `api_server.py` — dead code. Decisions on removing `gui/` and
`RealtimeAudioProcessor` were pending direct user confirmation (tooling
prevented getting an answer in that pass). `RealtimeAudioProcessor` was
confirmed and deleted on 2026-08-25 (see the entry below); `gui/` is still
awaiting an answer, and `gui/README.md`'s own "experimental, unwired"
disclosure stands as the honest label until it arrives.

**Q: Is api_server.py actually commercial-grade (HTTP-level audit)?**
A (2026-07): It starts cleanly and every route calls a real backing function
(no mocks) — but four handlers caught `HTTPException` inside a bare
`except Exception`, silently flattening real status codes: login's 429
(rate limit)/503 (capacity) became 200, and download/batch-submit/normalize's
404/403 became 500 or 200 with the original HTTPException detail leaked into
the response body. Fixed by re-raising `HTTPException` before the generic
handler in all four (`login`, `download_file`, `submit_batch_job`,
`normalize_audio`), and replacing the leaked `str(e)` in the two truly-generic
branches with a fixed message. Also fixed: two resource leaks (`job_queue`
never dropped a job_id on the circuit-breaker-open early return or the
exception path — only success removed it; `_rate_limit_windows` grew one
entry per distinct identifier forever with no pruning) and a real honesty gap
— `output_format` accepted `"flac"` and `allowed_file_types` accepted `.flac`
uploads, but `normalize_audio_fast`/`analyze_audio_fast` only ever call the
stdlib WAV-only core, so a requested FLAC output was actually a WAV file
wearing a `.flac` extension. Restricted both to WAV, matching what the code
can actually do. Also removed unbacked "government-grade"/"classification:
RESTRICTED" wording (module docstring, FastAPI title/description, `/`
endpoint) — CHARTER §4's exact failure mode, just in prose instead of code —
and corrected README's API section, which advertised a nonexistent
`CHAMELEON_API_KEY_FILE` env var, a `CHAMELEON_MAX_FILE_SIZE` override that
doesn't apply to the API process, a wrong default port (8080 vs the real
8000), and a fabricated on-disk audit-log path (`~/.chameleon/audit/*.log`)
when the audit log is actually in-memory only, retrievable via `GET
/audit/log`. `setup.py`'s `[api]` extra was missing the `pydantic<2` pin that
`pyproject.toml` already enforced — installing via setup.py could pull
pydantic 2, under which `Field(regex=...)` raises at import and the server
never starts; added the same pin.

`tests/test_api_routes.py` adds the first HTTP-level test coverage this file
has ever had (11 tests via FastAPI's `TestClient`): health/root, the dev
login flow, the 429/404 regressions above, and the FLAC rejections. Requires
`httpx<0.24` (pinned in the `dev` extra — newer httpx dropped the `app=`
shortcut this project's pinned fastapi/starlette version needs) and skips
cleanly without it, matching `test_api_fallback.py`'s existing
`importorskip("fastapi")` convention.

**Q: Fictional contact domains in packaging/spec metadata?**
A (2026-07): Removed. `pyproject.toml`'s `authors`/`maintainers` and
`openapi_spec.yaml`'s `info.contact` both listed
`{name}@chameleon-audio.com` — a domain nobody registered or specified,
asserting a support channel that doesn't exist. Dropped the `email` fields
(kept the team-name labels; PEP 621 doesn't require `email`). While fixing
this, found `openapi_spec.yaml` itself is orphaned (`grep` for
`openapi_spec` across all `*.py` returns zero references — `api_server.py`
serves its own live-generated OpenAPI schema via FastAPI, not this file) and
structurally invalid YAML (a second top-level document starts at line 28
with no `---` separator — pre-existing, confirmed via `git stash` that it
predates this fix). It also repeats the "Government-focused"/hardened
wording already removed from `api_server.py` and documents `SIMD
acceleration`, a ghost parameter deleted from the API back in an earlier
pass. Recorded as an open question below rather than fixed outright — it's a
larger, orphaned-artifact call like the modules in the punch list above, not
a one-line domain fix.

**Q: advanced_validation.py parity in core — was `core.py:BatchProcessor` ever
wired up?**
A (2026-07): Yes. `DeepFileInspector` already ran in `main.py:_filter_safe_files`
(the CLI batch path) but not in `core.py:BatchProcessor.process_directory`/
`process_directory_async` (reachable via `core.batch_process_async`, the
module's own public batch API) — the last item on the parity list. Wired the
same check (magic-number gate only, suspicious-pattern warnings logged not
rejected — identical contract to main.py's side) into both the sync and
async file-gathering loops, guarded by a new `core.HAS_DEEP_INSPECTOR` flag
mirroring main.py's. See `tests/test_core_batch_deep_inspection.py`.

While wiring this, found two pre-existing, unrelated bugs in
`BatchProcessor.process_directory` (the *sync* method — not the async one
actually used by `core.batch_process_async`, and confirmed to have zero
callers anywhere in the codebase):
1. It never returned `results` — fell off the end of the function, so every
   call silently returned `None` regardless of outcome. Fixed (a one-line
   `return results` restores the function's own declared
   `-> List[ProcessingResult]` contract).
2. Its per-file path calls `self._execute_operation(...)`, a method that
   did not exist on `BatchProcessor` (only the async
   `_execute_operation_async` did) — every call raised `AttributeError`,
   caught and reported as a per-file failure. **Fixed (2026-07).** A sync
   `_execute_operation` now exists, returning the `(result, attempts)` tuple
   the loop unpacks; it shares operation dispatch with the async twin via a
   new `_build_operation_runner` helper so the two can't drift. Fixing it
   surfaced a second, latent crash — the post-loop code assumed
   `result.data` was always a dict (true only while every file *failed*),
   so a *successful* `analyze` (whose data is an `AudioInfo`) raised
   "argument of type 'AudioInfo' is not iterable"; guarded with `isinstance`.
   And a third: `_execute_operation_async` returned `recovery.execute`'s
   `(result, attempts)` tuple verbatim, so `batch_process_async` leaked
   tuples despite its `List[ProcessingResult]` annotation (tests indexed
   `[0][0]`); it now returns the `ProcessingResult` alone. Tests assert
   per-file success and the un-tupled shape.

**Q: Is the plugin sandbox (§5's threat model) actually a security boundary?**
A (2026-07): It had a critical gap, now empirically verified and fixed.
`_check_module_safety` only walked `ast.Import`/`ast.ImportFrom` nodes, so a
plugin using `__import__("os")` — a builtin, no `import` statement required
— loaded and ran completely unrestricted code at `exec_module()` time (i.e.
at *load* time, before any sandboxed method was even called). Proof-of-concept:
a plugin file with zero literal `import os`/`import subprocess` text wrote to
disk and read `os.getpid()` successfully through `PluginLoader.load_plugin`.
Also bypassable via `importlib.import_module("os")` (`importlib` itself was
never on the restricted-modules list). Fixed by extending the AST walk to
also reject calls to `__import__`/`eval`/`exec`/`compile`, calls to
`importlib.import_module`/`importlib.__import__`, and attribute access to
`__globals__`/`__builtins__`/`__subclasses__`/`__mro__`/`__bases__` (common
sandbox-escape primitives). **This remains static AST analysis, not a
runtime sandbox** — `exec_module()` still runs plugins with normal,
unrestricted Python builtins; the fix closes the specific known bypasses,
not arbitrarily obfuscated equivalents. Documented that limitation directly
in the method's docstring rather than implying a stronger guarantee than
exists. Amended 2026-09: adversarial probing found three more bypass
classes that audit-PASSED — Name *references* to dangerous builtins
(`e = eval` never appears in Call position), `globals()`/`locals()`/
`vars()` reaching the namespace dict, and `getattr` with a computed or
dangerous literal attribute (`getattr(__builtins__, "ev"+"al")`). All now
rejected; the residual gap is genuinely dynamic code (bytecode payloads),
which no static pass can close — that is what the P4 runtime sandbox item
exists for: restricted globals/builtins during `exec_module`, a larger
architectural change not attempted here.

While investigating this, found two more pre-existing, unrelated bugs:
`plugin_system.py` called `importlib.util.spec_from_file_location` while
only ever doing `import importlib` (not `import importlib.util`) — worked by
accident whenever something else in the process happened to import
`importlib.util` first, and failed with `module 'importlib' has no attribute
'util'` when the CLI's plugin command ran as a genuinely fresh entry point.
Fixed with an explicit `import importlib.util`. Separately, 3 of the 5
shipped `demo_plugins/` (`spectrum_analyzer.py`, `simple_reverb.py`,
`tone_generator.py`) failed the product's own `plugins audit` command — they
carried legacy `sys.path.append(...)` boilerplate (for standalone-script
execution, unneeded since `PluginLoader` loads by direct file path) that
imported `os`/`sys`, both on the restricted-modules blocklist. Removed the
dead boilerplate; `python main.py plugins --directory demo_plugins audit`
now reports all 5 as `PASSED` instead of 3 `FAILED`. `tests/test_plugins.py`
gained 7 new tests covering the bypass fixes and a false-positive guard.

**Q: Does the container image actually work (packaging/deployment audit)?**
A (2026-07): It didn't. `Dockerfile` referenced `chameleon_enhanced.py` and
`enterprise_config.py` (classes `EnhancedChameleon`/`EnterpriseConfiguration`)
— names that appear nowhere else in this repository, ever; not deleted this
session, they never existed. The embedded health-check ran under `set -e`
and `sys.exit(1)`'d on the resulting `ImportError`, so **every** container
invocation failed regardless of `CMD` (`server`/`cli`/anything). It also
carried the same "Enterprise Edition"/"National-level"/"military-grade
security" marketing language already removed from `api_server.py` — CHARTER
§4's exact failure mode, in a different file. Rewrote the Dockerfile to run
the real entry points (`main.py`, which already wraps `api_server.py` via
its own `server` subcommand), removed the marketing language and an unread
`production.yaml` (`enable_authentication`/`enable_encryption`/
`enable_audit_logging` toggles that no code ever checked), fixed the stale
`ARG VERSION=2.0.0` (real value: `main.VERSION` = `1.0.0`), dropped `EXPOSE
9090` (a "metrics" port with no corresponding endpoint anywhere), and
switched `COPY . .` to an explicit file list matching `setup.py`'s
`py_modules` (avoids bundling `.git`/`tests`/`docs`/`gui`/dev artifacts into
a "production" image; added a `.dockerignore` too as defense-in-depth).

While auditing this, found `advanced_validation.py` — the module
`DeepFileInspector` lives in, wired into the default batch path per an
earlier §9 entry — was missing from both `setup.py` and `pyproject.toml`'s
`py-modules` lists. A non-editable `pip install chameleon-audio` from a
built wheel would have silently shipped without it. Added it to both lists
(and the Dockerfile's COPY list).

Also found and removed two requirements files that actively contradicted
`pyproject.toml` (the established single source of truth for dependencies,
per an earlier §9 entry): `api_requirements.txt` pinned `pydantic==2.5.0`
(breaks `api_server.py`'s pydantic-v1-only `Field(regex=...)` syntax at
import) and had its own "Government-grade" header comment; `enhanced_requirements.txt`
carried torch/tensorflow/GPU packages for the already-deleted neural
modules. `main.py`'s own missing-uvicorn error message pointed users at the
now-removed `api_requirements.txt` — fixed to point at `pip install -e
.[api]`. Also removed `pyproject.toml`'s `[ml]` extra (torch): zero
consumers anywhere in the codebase since the neural modules were deleted.

**Research-backed DSP accuracy (2026-07, standards + literature review).** A
review of the current DSP against the relevant standards and literature
(ITU-R BS.1770-5 [2023-11], EBU R128, the YIN/pYIN pitch literature, window
functions, spectral-subtraction musical noise) found accuracy and honesty
gaps in *already-shipped* features — the kind of "claim outruns
implementation" this charter exists to stop — and they were closed without
adding any new capability:

- **Spectral analysis had no window function** (`spectral_utils.analyze_spectrum`,
  rectangular window ⇒ spectral leakage) and snapped peaks to the nearest bin.
  Added a Hann window before the transform (the de-facto default) and
  parabolic interpolation for sub-bin frequency accuracy. Pure stdlib; RMS/DC
  are still measured on the raw buffer. Covered by `tests/test_dsp_accuracy.py`.
- **Pitch detection was a global-maximum autocorrelation** (`midi_analysis._estimate_pitch`),
  which is prone to octave errors. Replaced with YIN (difference function →
  cumulative mean normalisation → absolute threshold → parabolic interpolation).
  YIN is the signal-processing gold standard for monophonic pitch (≈91% raw
  pitch accuracy, on par with the CREPE neural model) and is pure stdlib, so
  it fits the deterministic, dependency-free core rather than pulling in ML.
  A regression test asserts it locks onto the fundamental even when a harmonic
  is louder (the classic octave-error case).
- **Denoise noise-window frame count was ~2× too long** (`main.py:remove_noise`
  used `int(0.5*sr/512)` while `stft(nperseg=2048)`'s default hop is 1024).
  Derived the count from the actual hop.
- **Honesty: the loudness meter claimed "ITU-R BS.1770 / K-weighting"** but is
  a 200–2000 Hz band-pass (BS.1770-5 K-weighting is a high-pass stage plus a
  +4 dB high-shelf at 2 kHz). Relabelled `LoudnessMeter` and its methods as an
  *approximate* meter (not certified LUFS, sample-peak not true-peak, LRA is a
  placeholder), and softened the CLI's `--master` output to `~X LUFS (approx)`.
  This is §8.2 (honesty) applied to a numeric claim.
- **Honesty: `linear_resample` has no anti-aliasing filter** — documented that
  downsampling will alias, and pointed at the `[audio]` extra for band-limited
  conversion. *(Follow-up 2026-08-08: this caveat turned out to be attached to
  the wrong function — `spectral_utils.linear_resample` has no callers. The
  resampler that actually shipped, `main._resample_audio`'s fallback, aliased
  with no warning at all. Now fixed; see the conversion-quality entry below.)*

One item was deliberately *not* changed: the lookahead **limiter**
(`mastering_chain._process_mono`) was re-inspected and found correct: it
emits the delayed sample `extended[i]` while its peak window `extended[i:i+lookahead]`
covers that sample through its lookahead-ahead neighbours, so gain reduction
lands before a transient — no change made.

**Pure-Python ITU-R BS.1770 integrated loudness — implemented (2026-07,
"C1").** The item above deferred this as the top follow-up; it has since
been built as `bs1770_loudness.py` and wired in via `analyze --loudness`.
K-weighting is two biquad IIR stages, implemented from the BS.1770-4 Annex 1
formulas and verified against the standard's published reference
coefficients at 48 kHz (locked in by `tests/test_bs1770_loudness.py`). The
gated-loudness algorithm (400 ms blocks, 75% overlap, −70 LUFS absolute gate,
−10 dB relative gate) matches the standard's structure. Two scope decisions,
recorded honestly rather than silently gapped:
- **True-peak oversampling — initially descoped, later added (2026-07).** The
  BS.1770 module (`bs1770_loudness.py`) still reports integrated loudness only.
  True-peak (dBTP) landed instead in `mastering_chain.LoudnessMeter.measure_true_peak`,
  where numpy/scipy are already hard dependencies: it applies Annex 2's
  oversample-then-peak method via scipy's 4× polyphase resampler and is
  exposed as `true_peak_db` in `analyze()` and in `process --master` output.
  Scoped honestly as an accurate *estimate* — it uses scipy's Kaiser-windowed
  resampler rather than transcribing the standard's *example* FIR coefficients
  (which the review pass could not verify against an authoritative source, and
  which the standard itself treats as one conformant example, not the only
  one). See the resolved entry replacing the old open question below.
- **Mono-downmix under-read — fixed (2026-07, same pass).** `core.get_samples_for_analysis`
  gained an opt-in `separate_channels=True` mode (the frame-decode loop
  already reads channels individually before it averages them to mono — this
  just skips that step) and `bs1770_loudness` gained
  `measure_integrated_loudness_multichannel`, which sums each channel's
  post-filter energy per block instead of averaging raw samples to mono
  before filtering. `analyze --loudness` now uses this path unconditionally
  (it's mathematically identical to the mono path for real mono files, so no
  branching needed). A regression test verifies the fix against the exact
  theoretical prediction: identical-content stereo now reads `10*log10(2)`
  ≈ 3.01 dB louder than the old mono-downmix figure. Standard multi-channel
  weighting for surround layouts beyond L/R (e.g. a +1.5 dB Ls/Rs boost)
  remains out of scope — every channel is weighted equally.
- A first version of the stage-2 (RLB high-pass) coefficients normalized the
  numerator by `a0`, which is a mathematically valid alternate normalization
  but does not reproduce the standard's published table (which — matching
  the widely-used libebur128 reference implementation — leaves the numerator
  unnormalized at `[1.0, -2.0, 1.0]`). Caught by a fresh audit before this
  landed on `main`; fixed to match the reference exactly (measured effect was
  small, ~0.04 LU, but conformance to the published values is the point of a
  "standard-conformant" claim).

**`mastering_chain.LoudnessMeter` is now standard-conformant — resolved
(2026-07, same pass).** The open question directly below this used to read
"not done here to keep this change corrective"; it has since been done.
`measure_lufs` reuses `bs1770_loudness`'s exact BS.1770-4 coefficients via a
single-pass `scipy.signal.lfilter` (verified to match the pure-Python
reference to 1e-6 LUFS on identical input) when SciPy + `bs1770_loudness`
are both available, replacing the `filtfilt`-based approximate band-pass;
falls back to the RMS approximation otherwise. Three more bugs surfaced and
were fixed by a dedicated adversarial-review pass on this change before it
landed:
- `setup_filters` expected a `ValueError` from `bs1770_loudness`'s *private*
  coefficient functions to catch sample rates below the ~8kHz stability
  floor, but those functions don't validate (only the public
  `apply_k_weighting` wrapper does) — so the guard was dead code, and a
  sub-8kHz `MasteringChain` would silently measure `inf`/garbage LUFS (or,
  for `sample_rate=0`, crash with an uncaught `ZeroDivisionError`). Fixed
  with an explicit rate check before calling the coefficient functions.
- A single NaN sample anywhere in the input would silently corrupt
  `measure_lufs`/`measure_range` to a plausible-but-wrong result (the causal
  IIR filter's NaN state contaminates every later sample, and NaN blocks
  simply fail the gate's `>=` comparison and get silently dropped) rather
  than surfacing as an error — demonstrated to shift a reading by 25 dB with
  zero indication anything was wrong. Both methods now check for NaN input
  explicitly and return NaN rather than a corrupted number.
- `auto_adjust` computes `target_lufs - current_lufs`; for a clip too
  short/quiet to form one gated block (`current_lufs == -inf`), that's
  `+inf`, which was added straight into `compressor.makeup_gain` and then
  propagated NaN through the compressor/limiter into the mastered audio.
  This was invisible in this session's own prior test runs because SciPy
  wasn't installed, so `measure_lufs` was always using the RMS fallback
  (which never returns `-inf`) — installing SciPy specifically to verify
  this fix is what surfaced it. Fixed by skipping the gain adjustment when
  `current_lufs` isn't finite.
`measure_range` (LRA) was also corrected to use a 100ms hop (matching the
standard's short-term-loudness update rate) rather than an initial 1s hop
that would have under-sampled the short-term loudness distribution.

**The CLI hid half the dependency-free core (2026-08-08).** Applying the
"make the requirements less dumb" step of Musk's algorithm — question the
requirement before optimising anything — to §1's central claim: the product
exists because its core runs with no third-party packages.

`core.py` has always implemented **four** such operations. `analyze`,
`normalize`, `to_mono` and `trim_silence` are all pure standard library, all
listed in `ALLOWED_BATCH_OPERATIONS`, all covered by core's own tests. The CLI
exposed **two**. There was no `--mono`, no `--trim`, and `batch` would not
accept either — so half the differentiator was reachable only from the Python
API, while users were pushed toward numpy-requiring paths for work the stdlib
core already did.

That is a dumb requirement, not a missing feature: the capability was written,
tested and free. Both are now exposed on `process` and `batch`, routed through
core whether or not numpy is present — the stdlib path is the reference
behaviour, not a degraded fallback. `tests/test_stdlib_operations.py` runs the
real CLI as a subprocess with numpy, scipy, librosa and soundfile all made
unimportable, so a future change that quietly adds a dependency to these
operations fails the suite. It also pins the flip side: `--denoise` must still
fail with a message naming the extra.

The general lesson worth keeping: before optimising or deleting anything, check
whether the product is simply failing to ship what it already has.

**Cross-validated the loudness meter against pyloudnorm (2026-08-08).** Every
check on `bs1770_loudness` up to now was either our own test or a
first-principles invariant. Neither can catch a *shared* misreading of the
standard, so this pass compared against an independent implementation —
`pyloudnorm`, written by other people from the same document.

Integrated loudness agrees to **0.043 LU** across sines (100 Hz / 1 kHz /
5 kHz), noise, and programme material spanning the relative gate. Tech 3341
allows ±0.1 LU, so both are conformant.

The residual is worth recording because it is not scatter: a constant
+0.041 LU on every signal, flat across frequency (+0.043 dB above 500 Hz,
tapering to 0 at 20 Hz). That rules out a filter-shape difference and points
at passband gain, and tracing it confirmed our K-weighted RMS is exactly
0.0414 dB hotter — same −0.691 constant, same gating, same channel weights.
The cause is coefficient precision in the stage-1 high shelf: against the
BS.1770-4 published table at 48 kHz our error is ~1e-12, pyloudnorm's ~1e-4,
because they derive from the analog prototype where we use the printed table.

So the gap is theirs, and a test now asserts our error is the smaller one —
specifically so a future reader who spots the discrepancy does not "correct"
ours toward the reference. `pyloudnorm` is test-only and deliberately in no
install extra; the suite was run with it blocked to confirm it skips rather
than fails.

**Tempo was four times too slow (2026-08-08).** `analyze_rhythm` computed
`60 / (interval * 4)` where the beat-per-minute definition gives `60 /
interval`, so every tempo came out at exactly a quarter of its true value —
notes half a second apart, plainly 120 BPM, were reported as 30.

Its interval histogram also bucketed with `round(interval * 16) / 16`. The
comment called that "quantize to 16th notes", but it quantizes to sixteenths
of a *second*. Note values cannot be recovered without the tempo, which is the
quantity being estimated, so an absolute grid cannot express the stated
intent; the practical effect was resolution that varied with tempo, snapping
100 ms onsets to 125 ms and dragging the tempo 25% with them. Intervals are
now grouped on a log scale (48 buckets per octave), giving equal precision at
every tempo.

Onset spacing fixes the beat period only up to a factor of two, so the result
is folded into the 40–240 BPM range — the conventional way to settle a
metrical level the data cannot determine. Same principle as the Am7/C6
tie-break above: where the evidence genuinely underdetermines the answer, say
so in the design rather than picking silently.

Checked and left alone: the chord-progression suggester is a fixed Markov
table and already declares itself one in both its docstring and the CLI
output — honestly scoped, not a prediction claim.

**Key detection was rotated backwards; sevenths collapsed to triads
(2026-08-08).** The music-theory analysis had two bugs, both invisible from
reading the code and obvious the moment known-answer musical input was fed in.

`detect_key` rotated the Krumhansl-Schmuckler profile the wrong way. The
profile is indexed relative to the tonic while the pitch-class histogram is
absolute, so the weight for pitch class `pc` must come from
`profile[(pc − tonic) % 12]`; the code computed `profile[(pc + tonic) % 12]`.
The two coincide only at tonic 0, so C major was right and every other key was
reported as its inverse — G major as F, D as A#, A as D#. **11 of 12 keys were
wrong.** The profile *values* match Krumhansl & Kessler (1982) and were left
alone; only the alignment was broken.

`_analyze_chord` scored templates by `matches / len(template)`, which asks only
how much of the template is present and never penalises notes it cannot
explain. C-E-G-B scored 1.0 against the three-note "major" template just as
against "maj7", and dictionary order broke the tie, so **every seventh chord
was reported as its bare triad**. Jaccard overlap (divide by the union) makes
the unexplained note cost the triad.

That surfaced a genuine ambiguity rather than a bug: A-C-E-G is Am7 or C6
depending only on the bass, and pitch-class content cannot distinguish them.
Ties now go to the lowest sounding note — the information that actually
decides it. Worth recording as the general lesson: when two answers are
equally consistent with the data, the fix is to bring in the missing
information, not to pick one and call it resolved.

**Denoise estimated its noise profile from the signal (2026-08-08).**
`remove_noise` took the noise profile from the first half second of the file,
which assumes every recording opens with silence. On material starting
straight into music — the common case — the "noise" it measured *was* the
music, and the subtraction attacked the signal: a tone beginning at t=0 came
out 20.0 dB down, the whole file 19.4 dB quieter. The only thing preventing
total erasure was the `0.1*magnitude` floor bounding per-bin attenuation at
20 dB.

Replaced with a per-**bin** 10th percentile over time. Real material leaves
every bin quiet at some point, so the low quantile of a bin's history is its
noise floor regardless of where the quiet moments fall. Per-bin is the part
that matters: selecting whole quiet *frames* was tried first and still failed,
because a steady level makes every frame equally loud.

A low quantile under-reads, so it is scaled to a level estimate by a *derived*
constant rather than a tuned one: a complex-Gaussian bin's magnitude is
Rayleigh distributed with quantiles `σ·sqrt(−2·ln(1−p))`, so
`median/p10 = sqrt(2 ln2)/sqrt(−2 ln0.9) ≈ 2.56`. A sweep confirmed higher
percentiles (30, 50) restore reduction only by re-attacking the signal
(−20.0 dB on the tone again). Net: the broken case goes −19.4 dB → −0.1 dB
while the case that already worked keeps its reduction (8.7 → 8.3 dB).

**Compressor soft knee was non-monotonic (2026-08-08).** Continuing the DSP
audit, the compressor's static gain computer mixed two knee conventions — a
quadratic knee over `[0, W]` above the threshold, plus the above-knee reduction
formula for a knee *centred* on the threshold. The pieces did not meet: on the
transfer curve (threshold −20, ratio 4, knee 6) the output went −16.25 dB at
in=−14 then −18.25 dB at in=−13, so a 1 dB rise in input dropped the output
2 dB. A compression curve that is non-monotonic across its knee is simply
wrong. Replaced with the standard centred quadratic soft knee (Giannoulis,
Massberg & Reiss, JAES 2012), which is continuous by construction. Verified by
property — monotonic, above-knee slope exactly 1/ratio, 0 dBFS asymptote on the
ratio line at −15 dB. The gain computer was also duplicated verbatim in the
mono and stereo paths; both now call one helper. The limiter was **not**
touched — it was re-inspected earlier and found correct.

**Both equalizers were destructive; RBJ biquads (2026-08-08).** A literature
sweep of the remaining DSP paths found that both EQ implementations were built
on `scipy.iirpeak` — a **band-pass resonator**, not a peaking EQ. Filtering
with it and scaling the result replaces the signal with its own narrow band,
so asking for a boost deleted everything outside it. Measured:
`main.apply_effects` with "+3 dB at 1 kHz" attenuated 200 Hz by 24.6 dB and
3 kHz by 15.3 dB. `ParametricEQ` was worse — its combining step
`result + (filtered − result)·(gain−1)` is unity at the centre and `2−g`
outside, so a "+6 dB at 1 kHz" request produced **0.00 dB of boost** while
annihilating the rest of the spectrum. This shipped in the
streaming/cd/vinyl presets, where every requested boost came out as
attenuation (streaming asks +0.5/+0.3/+0.8 dB, measured −1.26/−1.16/−0.83).

Replaced with the standard RBJ *Audio EQ Cookbook* bilinear-transform designs,
implemented once in `mastering_chain` and reused by `main.py`. Applied with a
single `lfilter` pass, because `filtfilt` runs the filter twice and would
double the requested dB gain; the high/low-pass bands keep `filtfilt` since
unity passband gain makes zero-phase free there, and were left untouched.

Verified by property rather than by transcription — the cookbook text was not
retrievable here, and in any case the properties are stronger evidence: unity
at DC and Nyquist, exactly the requested gain at the centre frequency, a shelf
at half its gain on the corner, and a +G boost followed by a −G cut restoring
the original to below −60 dB RMS error. Each holds to within 0.01 dB.

Also seeded the reverb impulse response: it is synthetic decaying noise, and
an unseeded generator made every run differ, contradicting the reproducibility
§1 sells the tool on — the same reasoning that kept dither opt-in.

*Two paths were audited and deliberately left alone,* which is worth recording
so the next pass does not redo the work. **YIN** (`midi_analysis.py:185-267`)
is faithful to de Cheveigné & Kawahara (2002): difference function, cumulative
mean normalisation, absolute threshold at 0.1 taking the *first* dip and
descending to its local minimum, parabolic interpolation, and a global-minimum
fallback rejected above 0.5 for non-periodicity. **Mastering dither**
(`mastering_chain.py`) hardcodes a 16-bit scale factor, which is correct for
the 16-bit output this path actually writes; "shaped" is now implemented
(first-order error feedback) and unknown values still fall back to TPDF
with a warning rather than silently doing nothing.

**Conversion quality: anti-aliasing, rounding, opt-in dither (2026-08-08).**
With the measurement side settled, this pass audited §1's other half —
transforming audio without damaging it — and found three defects on the
`--convert` path.

*Aliasing where the honesty note wasn't.* An earlier pass documented that
`spectral_utils.linear_resample` aliases. That function has **no callers**.
The resampler that actually ships is `main._resample_audio`, whose fallback
branch was `np.interp` — linear interpolation, no anti-aliasing, no warning,
no docstring caveat. Downsampling folded everything above the new Nyquist into
the audible band. Replaced with a windowed-sinc resampler whose cutoff is
`min(1, target/source)`: the sinc widens so its cutoff lands on the lower of
the two Nyquist frequencies, with the support widened to match. Same Blackman
/ unit-DC-gain construction as the true-peak oversampler in
`bs1770_loudness`, which never needed the cutoff term because it interpolates
without ever decimating. Measured on a 15 kHz tone at 48k→16k: −5.69 dBFS of
alias before, −62.70 after, against scipy's −62.63 — a 57 dB improvement that
lands 0.07 dB from the reference implementation. The librosa and scipy
branches were already correct and were not touched.

*Truncation instead of rounding.* `_save_wav_basic` quantised with
`.astype(np.int16)`, which truncates toward zero — a −0.4999 LSB DC bias on
single-signed material and a full-LSB worst case. Rounding takes the mean
error to −0.0002 LSB and halves the worst case.

*Dither, and why it is off by default.* Nothing on this path dithered, and
`ProcessingConfig.apply_dither` was a flag no code read. It now applies 2 LSB
peak-to-peak TPDF dither — triangular specifically so the quantisation error
becomes independent of the signal. **Default off**, decided with the user:
§1 sells this tool on deterministic, reproducible output, and dither is noise
from a random source, so enabling it by default would break a documented
differentiator and change every existing user's output bytes. Opting in is a
deliberate trade, and the docstring states the trade rather than hiding it.
The test for it doubles as the argument for dither: a constant that falls
between two codes quantises to the same wrong code every time (mean error
−0.4277 LSB), while dithered it averages onto the true value (+0.0002 LSB).

*A documentation error of our own.* The previous pass's rewritten command
references listed `--convert` and `--denoise` under "Core commands" with no
dependency note, but only `analyze` and `normalize` run without numpy
(`main.py:1093-1101`, verified by running each operation with numpy blocked).
Corrected in both languages, with per-flag dependency columns and the
resampler backends' anti-aliasing status documented.

**Loudness range (LRA) completes EBU Mode (2026-08-08).** Tech 3341 defines
EBU Mode as M + S + I + **LRA**, so the previous entry's M/S work still left
the set incomplete — and `PRODUCT_ANALYSIS.md` had already called it done,
which was an overclaim by this same automation and is corrected there.
`bs1770_loudness.measure_loudness_range` now supplies the missing piece in
pure stdlib, reusing the short-term series (3 s / 100 ms is exactly the
geometry Tech 3342 wants) with a **-20 LU** relative gate — not the
integrated meter's -10 LU, so `_gate_and_convert_to_lufs` could not be reused
as-is — and returning P95 − P10. It returns NaN, not 0.0, when nothing can be
measured, so "no measurement" stays distinguishable from a real 0 LU.

Same verification stance as M/S: the primary Tech 3342 PDF was unreachable
(egress proxy blocks tech.ebu.ch, its mirrors, and mathworks.com), so no
claim of conformance to text we could not read. Two independent checks stand
in. First, an invariant that follows from the definition rather than any
table: a signal alternating between two amplitudes must have an LRA equal to
their dB difference — measured 6.021 LU for 6.021 dB, 12.041 for 12.041,
20.000 for 20.000, and 0.000 for a steady tone. Second, cross-implementation
agreement: `mastering_chain.LoudnessMeter.measure_range` computes LRA
independently via scipy filtering and `np.percentile`, and the two agree to
**0.000 LU** on every test signal. The stdlib percentile deliberately uses
linear interpolation (numpy's default estimator) to make that comparison
meaningful.

*Why two LRA implementations is layering, not the duplication this project
treats as a defect.* The preceding audit flagged triplicated spectral
subtraction as a defect, so the distinction matters. Duplication is when two
copies serve the same caller on the same install and can silently diverge;
layering is when the stdlib core must work with **zero** third-party packages
(§1, the differentiator) and the numpy path exists for callers who already
have numpy. `bs1770_loudness` cannot import scipy and `mastering_chain`
cannot drop it, so neither can be expressed in terms of the other. This is
the precedent already set for true-peak. The two are kept honest by a test
that asserts they agree — which duplication-by-accident never has.

*Honesty in the output.* Tech 3342 asks meters to flag an LRA as unstable
during the first 60 s, and `analyze --loudness` reads a bounded prefix (15 s
by default), so the CLI says so in the line itself rather than presenting a
settled figure. Separately, `MasteringChain.analyze()` had been computing a
loudness range that `main.py` never threaded out of the result and so could
never display; `process --master` now shows it, which makes the chain's own
effect visible (a 12.0 LU test file reads 3.0 LU after mastering).

**First-principles audit (2026-08-08).** Instead of asking what an audio tool
usually has, this pass derived the necessary feature set from §1 and measured
the tree against it. Two conclusions.

*Excess:* ~1 line in 4 of shipped Python is unreachable from the CLI (9,367
reachable / 3,121 orphaned, plus `RealtimeAudioProcessor`). `performance_optimizer.py`
is ~100% duplication of `core.py`/`main.py` facilities (deleted 2026-08-25); spectral subtraction
exists in three places; `api_server.py:52-54` imports three modules that have
never existed, permanently pinning `HAS_SECURE_MODULES` to False and making
the `skipif`s in `tests/test_api_fallback.py` no-ops (that last one was deleted
on 2026-08-25 — see the entry below). **Nothing was deleted at the time** —
the deletion rule requires explicit per-item confirmation, and asking produced
no answer, so all of it is recorded in `PRODUCT_ANALYSIS.md` §1b for a later
decision rather than acted on.

*Missing:* the real gaps were honesty and standards coverage, not features.
The bilingual command reference documented ~18 commands with no `add_parser`
anywhere (plus a configuration file and `config` sub-command that do not
exist) — fiction sitting at the first touchpoint a user has. Rewritten against
the actual argparse, with every example executed before being written down.
`analyze --loudness` reported only Integrated loudness, an incomplete
EBU-Mode reading; Momentary/Short-term added (below). Also fixed: README's
public-API example was built on an orphaned module, README listed the deleted
`stability_enhancer.py`, `setup.py`'s extras diverged from pyproject
(advertising a `mido` dependency nothing imports while omitting the `audio`
and `dev` extras the README tells users to install), and
`personal_config.py`'s podcast/music workflows printed "ready!" while doing no
work at all — now raising `NotImplementedError` that names the real commands.

**EBU Mode momentary/short-term loudness (2026-08-08).** `bs1770_loudness.py`
gained M (400 ms) and S (3 s) ungated sliding-window meters plus Max-M/Max-S,
wired into `analyze --loudness` and `--export`. Implemented by generalizing
`_block_summed_mean_squares` with block/hop parameters rather than duplicating
the windowing — deliberately, since the same pass flags triplicated DSP as a
defect. No new coefficients.

Honesty note worth preserving: the primary EBU Tech 3341 PDF **could not be
retrieved** here (the egress proxy blocks `tech.ebu.ch` and the mirrors), so
the window lengths and the ungated property come from agreeing secondary
sources, not the standard's text, and the code says so. Following the
true-peak precedent, correctness is instead pinned by first-principles
invariants: a stationary signal must give M == S == I (measured Δ 0.0000 LU),
M must react faster than S after a level step, quiet windows must survive
(ungated), and two identical channels must sum to +3.01 LU.

**Agent docs + honesty pass (2026-07-18).** Added the first agent-facing
documentation set — `CLAUDE.md` (working agreement), `PRODUCT_ANALYSIS.md`
(strengths/weaknesses/backlog, cited to `file:line`), and
`docs/agents/{OPUS,SONNET}.md` — so future sessions inherit scope and
conventions. The analysis surfaced three docstring/metadata overclaims,
fixed in the same pass (text only): `advanced_validation.py` no longer claims
"malware detection" (it does structure/integrity/tamper checks);
`gui/package.json` dropped "Government-Grade"/"Chameleon Security
Team"/`"RESTRICTED"` for an honest experimental description, "Chameleon
contributors", and `MIT` (matching the repo license); `batch_automation.py`
dropped "Intelligent …" for a plain description that also records its
orphaned status. No behavior change.

**Fantasy-code removal (2026-07, user-confirmed).** A fresh audit found three
orphaned pieces in `core.py` that repeat the "quantum"/neural-module pattern
this charter exists to stop — a claimed capability with no real
implementation behind it, never imported by any other file:

- `AIMusicAnalyzer` (`analyze_music_style`/`suggest_music_generation`,
  called "AI-powered music analysis" / "AI music generation") — every
  feature extractor returned hardcoded literals (`# Placeholder`) and never
  read the audio file; style classification was a fixed score table.
- Six `*FeatureExtractor` classes (`SpectralFeatureExtractor`,
  `TemporalFeatureExtractor`, `HarmonicFeatureExtractor`,
  `RhythmicFeatureExtractor`, `EmotionalFeatureExtractor`,
  `StylisticFeatureExtractor`) — zero callers, librosa-gated, ~150 lines.
- `AudioFormatSupport` — zero callers, depended on `pydub` which was never a
  declared dependency (contradicting the stdlib-only-core story), ~245 lines.

Deleted, along with the module-level `_ai_analyzer` singleton and its two
public wrapper functions. `core.py`'s dead `RealtimeAudioProcessor` (itself
already unreachable — needs an undeclared `websockets` dependency, zero
callers) referenced the deleted `_ai_analyzer`; its `self.ai_analyzer`
assignment was set to `None` (matching the existing `self.ai_generator =
None  # removed in cleanup` line right next to it) rather than left dangling
— a necessary consequence of the deletion, not a decision to keep or remove
`RealtimeAudioProcessor` itself, which remains a separate, still-open
question below. Net: `core.py` 3,266 → 2,738 lines (528 removed). No test
changes needed — zero tests referenced any of the removed symbols.

**`personal_config.py` — considered for deletion, kept.** Initially assumed
dead (no other `.py` file imports it), but a closer check found it isn't:
`quick_install.sh`/`quick_install.ps1` document `python personal_config.py
setup` as the personal-use onboarding flow, and it's the one deliberately
documented entry point for `advanced_validation.py`'s
`IntegrityVerifier`/`SanitizationEngine` (see the entry above this in this
file, and `PROJECT_STATUS.md`'s "left alone deliberately" note) — a real,
working backup/library-scan tool, not a placeholder. It is missing from
`pyproject.toml`/`setup.py`/`Dockerfile`'s module lists, which is a genuine
packaging gap (a non-editable install loses this documented feature
silently) but is a reason to *fix packaging*, not delete the file. **Fixed
in the same pass this was found** — added to all three lists.

**`api_server.py`'s phantom secure modules — deleted (2026-08-25).** The file
opened with a `try: from government_auth import ... / from secure_core import
... / from high_performance_core import ...`, setting `HAS_SECURE_MODULES`.
None of those three modules has ever existed in this repository, in any commit,
so the `except ImportError` was the only reachable path and the flag was pinned
to `False` for the lifetime of the project. Six `if HAS_SECURE_MODULES:`
branches — a service-instantiation block, a permission check, a login path, an
upload validation step, and a startup log — were therefore **structurally
unreachable**, and the three `skipif(api_server.HAS_SECURE_MODULES)` guards in
`tests/test_api_fallback.py` could never fire, so three tests that looked
conditional were unconditional and one branch of each conditional was never
exercised by anything.

Deleted with explicit user confirmation naming this item. What was reachable is
now unconditional: the stdlib-core adapters are top-level, login checks the
configured credentials directly, and `require_permission` carries a docstring
saying plainly what it does — require a session, and *name* a permission it
does not enforce. That is the honest description of the behaviour that was
already shipping; the deleted branch was the only thing suggesting otherwise.
Note also that the "government" naming is exactly the unverifiable
institutional claim §4 forbids.

Two knock-on fixes in the same commit: `tests/test_api_fallback.py`'s four
tests now actually run (they were being reported as skipped-or-passed depending
on a flag that meant nothing), and `import uvicorn` moved from module scope
into the `__main__` block — it is needed to *run* the server, never to import
`app`, so importing the module under gunicorn or in a test no longer requires
it. `api_server.py` 1,637 → 1,565 lines.

**`core.py`'s `RealtimeAudioProcessor` — deleted (2026-08-25).** 393 lines
(the whole tail of `core.py`) implementing a WebSocket streaming server:
client registry, per-client queues, an event-handler table, session state and
a `websockets.serve` loop. Zero callers — not `main.py`, not `api_server.py`,
not a single test, not even another orphaned module. It could not have run in
a default install either: `websockets` is in no extra of `pyproject.toml`, so
its constructor raised `ImportError` unconditionally for anyone who found it.

Two prior passes recorded it as an open question rather than acting (the
deletion rule requires per-item confirmation and none had been given). That
confirmation arrived, naming this item, so it is gone.

Real-time streaming is not in §1's scope: Chameleon is a file-in/file-out CLI
with a REST server. A streaming server is a different product with a different
threat model — none of the path-validation layer that justifies §1's "secure"
claim applies to a socket. Keeping a stub of one implied a capability the
project has no intention of finishing.

Deleting it also let the `try: import websockets ...` block at the top of
`core.py` go. That block was itself a trap: it imported `asyncio`, then
`websockets`, then `json`, `threading`, `queue`, `typing` and `time`. Because
Python stops a `try` body at the first exception, an environment without
`websockets` skipped the five imports *after* it. Every one of those except
`queue` happens to be imported unconditionally at the top of the file, so
nothing broke — but the block was one reordering away from a
`NameError` in the stdlib core. `core.py` 2,780 → 2,367 lines.

**`performance_optimizer.py` — deleted (2026-08-25).** 324 lines,
zero importers. Every facility in it already existed, better, in code that
actually runs:

| In `performance_optimizer.py` | The version that ships |
|---|---|
| `get_optimal_worker_count` | `main.py`'s `ProcessingConfig.from_environment` (this made it the *third* implementation) |
| `get_optimal_chunk_size` | `core.py`'s `_determine_chunk_size` / `CHUNK_SIZE` |
| `CacheManager` | `core.py`'s `MemoryManager` — byte-accounted LRU with mmap, versus a plain dict |
| `MemoryOptimizer` | same |
| `SIMDOperations` | the equivalent loops in `core.py`'s WAV path |

The decisive evidence is not the duplication but a defect. `SIMDOperations.
normalize_int16` computed its scale factor as `int((target_peak * 32767) /
peak)` — integer truncation of a value that is below 1.0 for any peak above
about 34% of full scale, so the function returned **digital silence** for
essentially all real audio. `array('h', [32000, -16000, 8000])` normalizes to
`[0, 0, 0]`. A normalizer that silences its input cannot have been run even
once, by anyone, ever. That is what an orphaned module is: not merely unused,
but unexamined, and therefore untrustworthy on the day someone finally wires
it in.

This is the same argument that retired `config_manager.py`, applied to the
same evidence. Deleted with explicit per-item confirmation; removed from
`setup.py`, `pyproject.toml`, the `Dockerfile` COPY list, `README.md` and
`docs/agents/SONNET.md` in the same commit.

**Orphan modules are now a CI failure, not a doc entry (2026-08-25).**
`tests/test_no_orphan_modules.py` parses `pyproject.toml`'s `py-modules`,
walks the import graph from the two entry points a user can actually invoke
(`main` for the console script, `api_server` for `chameleon server`), and
fails on any packaged module nothing reaches. The walk covers the whole AST,
not just module-level statements, because `main.py` deliberately imports
`mastering_chain` / `bs1770_loudness` / `midi_analysis` inside functions to
keep the stdlib core importable without numpy.

Four modules are allow-listed with written justifications:
`audio_restoration` (seven classes of real DSP nothing else implements, a
candidate for CLI wiring), `personal_config` (reachable by a *user* via
`quick_install.sh`, just not by an import), and `batch_automation` /
`spectral_editor` (kept by explicit user decision on 2026-08-25, over a
recommendation to delete). A companion test fails if an allow-list entry
becomes stale, so the list cannot decay into folklore. Two further tests
catch the other half of a botched deletion: a `py-modules` name with no file
behind it, and drift between `setup.py`'s list and `pyproject.toml`'s.

This is the `test_no_fantasy_features.py` pattern applied to a second failure
mode. §4 violations were already mechanized; accumulation of unreachable code
now is too.

**Deleting dead code did not make anything faster — and that is the point
(2026-08-25).** Measured across the three deletions above: 15,273 → 14,484
lines of product Python (789 removed, 5.2%), while `compileall` stayed at
0.17 s, `import core` at ~70 ms and the test suite at ~58 s, all within
run-to-run noise. Of course: unreachable code has no runtime cost, which is
exactly why it survives so long. Its cost is that it looks available —
it ships in the wheel, it imports, its docstring makes a promise — so the
next person to wire it up inherits however many years of unexercised bugs.
`performance_optimizer.normalize_int16` returning silence is that cost made
concrete. Anyone justifying a deletion here should argue comprehension and
trust, not milliseconds; claiming a speedup we did not measure would be the
same overclaiming §8 forbids everywhere else.

**`audio_restoration.py` wired into the CLI — but only the half that works
(2026-08-25).** 530 lines of restoration DSP that no entry point reached. The
recommendation had been to keep it because it was the one orphan that was
*capability* rather than duplication. Wiring it up meant auditing it first,
and the `performance_optimizer` lesson held: unexercised code is untrustworthy.

Measured, before anything was exposed:

| Class | Verdict |
|---|---|
| `HumRemover` | works — 60 Hz cut 30 dB, 440 Hz unchanged |
| `DeclippingProcessor` | **destroyed clean audio** — see the entry above |
| `ClickRemover` | improves smooth material, but no trustworthy detector exists |
| `CrackleRemover` | benign but unverified |
| `AdaptiveDenoiser` / `SpectralRepairer` | silent no-ops without librosa |

So `process --declip` and `process --dehum` ship, and nothing else does. The
declipper and the hum detector were both fixed first (separate entries above);
`--declick` is deliberately absent, because both candidate detectors have a
regime where they wreck the audio: the shipped envelope/z-score one reports
354 clicks in one second of white noise and pulls its peak from 0.473 to
0.325, while a second-difference/MAD detector reports 1,764 in hard-clipped
material — one per clipping corner, which is a derivative discontinuity that
looks exactly like an impulse. Distinguishing a click from a clipping corner
needs a model of what the signal *should* be doing, which is the AR-prediction
approach the old comment falsely claimed. Shipping a third mediocre detector
would have been the error Musk's algorithm warns about: optimizing a part that
should not exist yet.

Two findings from wiring it up that were not visible from reading it:

*Order is not the user's to choose.* Damage must be undone in the reverse of
the order it happened, and clipping comes last in a recording chain. On a
220 Hz tone recorded with hum and then hard-clipped, declip→dehum lands 6.8 dB
closer to the undamaged tone than dehum→declip (-28.2 dB vs -21.5 dB). Worse,
dehumming first ripples the plateaus just enough that declipping then finds
**0** of the 720 clipped regions, and the peak it appears to recover is the
notch filter ringing on the clipping corners. `RESTORATION_REPAIRS` fixes the
order; command-line flag order is ignored, and a test asserts both facts.

*The hum detector needed an absolute floor, not just prominence.* Comparing a
bin against its neighbourhood median is necessary but not sufficient: the
quantisation noise of a periodic signal is itself periodic, so it forms lines
at the signal's harmonics and leaves the 50/60 Hz neighbourhood at the
numerical floor, where any bin beats the median tenfold while representing
1e-13 of amplitude. A real 16-bit file of a clean 440 Hz tone therefore
"contained" both 50 and 60 Hz hum. Detection now also requires roughly
-80 dBFS of actual level. Verified across float and 16-bit clean tones, hum at
0.1 and 0.003, inaudible hum at 1e-5, a musical 55 Hz bass note (which sits
between the two power-line frequencies), white noise and silence.

`audio_restoration` leaves `tests/test_no_orphan_modules.py`'s allow-list as a
result — one fewer standing exception. Its import-time librosa warning was
also dropped: librosa is in no extra, so its absence is the normal case, the
two classes needing it now raise clearly, and the warning was printing on CLI
runs for a feature nobody had asked for.

**The test suite could not run on the install the product is defined by
(2026-08-25).** Chameleon's differentiator is a core needing no third-party
packages. Twelve test modules did a bare `import numpy` at module scope, so on
a genuinely bare install `pytest` failed at *collection* with twelve errors and
ran nothing at all. Verifying the dependency-free core required first
installing the dependency it is defined by not needing. All twelve now use
`np = pytest.importorskip("numpy")`, and `tests/test_cli_parity.py`'s
effects-batch case — which drives a numpy-only operation through a subprocess,
so it never imported numpy itself — is skipped when numpy is absent.

Three configurations now pass, and the numbers are the point:

| Install | Result |
|---|---|
| stdlib only | 259 passed, 21 skipped |
| + numpy | 300 passed, 25 skipped |
| + numpy + scipy | 410 passed, 2 skipped |

Finding this also revealed that `ci/proposed-ci.yml` installed numpy but not
scipy, so adopting it would have produced a green tick while ~90 tests
silently skipped — and, worse, three tests in `tests/test_eq_quality.py`
actually *failed* there, meaning the proposed replacement CI was red. Both are
fixed; the workflow now runs a `stdlib-only` job (which refuses to start if an
audio package leaked into the environment, since otherwise it proves nothing)
and an `audio-extra` job across Python 3.9–3.12 including a
`-W error::RuntimeWarning` DSP pass. Every step was executed locally against a
clean copy of the tree before being written down.

Re-confirmed the same day that this project's automation account still cannot
adopt it: `git push` is refused with *"refusing to allow a GitHub App to create
or update workflow `.github/workflows/ci-cd.yml` without `workflows`
permission"*, and the REST contents API returns 403. A maintainer must run the
one `cp` in `ci/README.md`. What changed is that the file they will copy is now
known-good rather than merely plausible.

**Two silent no-ops and a contradictory exit, found by running the CLI the way
CI would (2026-08-25).**

*`apply_effects` skipped effects it could not apply.* Each effect was guarded
by its dependency — `if "eq" in effects and HAS_SCIPY and ...` — and simply did
nothing when the guard was false. On an install without scipy,
`process --effects eq.json` wrote an output file, printed a success line, and
applied no EQ; nothing distinguished that from an EQ that had been applied and
happened to be subtle. It now raises, naming the effect and the extra that
fixes it. This is the same defect class as the restoration pipeline reporting a
denoising step it had skipped: the tool was not wrong about the audio, it was
wrong about itself.

*`--mono` on an already-mono file printed "Error: Already mono", wrote no
output, and exited 0.* Three things wrong at once: an error message on a
success exit, a request treated as a failure when it was already satisfied, and
a promised output file that did not exist — so a batch over mixed material left
a pipeline believing it had files it did not have. Converting mono to mono is a
satisfied request; the file is now copied through and reported as such, which
makes `--mono` idempotent.

**`personal_config.py` covered (2026-08-25).** The last zero-coverage module,
and the one a user touches *first*: both `quick_install` scripts point new
users at `python personal_config.py setup`. Eighteen tests found three defects
in the two functions that flow hits:

- `PersonalConfig.load` did `cls(**data)` straight from the JSON, so a config
  written by any other version of Chameleon — or hand-edited, which is the
  entire point of a personal config file — raised `TypeError: __init__() got an
  unexpected keyword argument` and the tool would not start. Unknown keys are
  now logged and ignored.
- Malformed JSON raised `json.JSONDecodeError` with no indication of which file
  was at fault. It now raises a `ValueError` naming the path and saying what to
  do, and deliberately does *not* overwrite the file with defaults — silently
  discarding someone's settings is worse than refusing to start.
- `create_playlist` stamped every playlist with `Path.home().stat().st_mtime`,
  the home *directory's* modification time: the same value for every playlist
  ever created, unrelated to when any of them was made.

Being unimported is not the same as being unexercised, and the allow-list entry
now says so.

**The security scan cried wolf on ordinary audio (2026-08-25).**
`DeepFileInspector._scan_for_suspicious_content` searched the whole file — up
to 10 MB, PCM payload included — for every entry in one flat pattern list. Two
of those entries are two bytes long (`MZ`, `#!`), so in 16-bit audio each has
roughly a 1-in-65,536 chance at every offset: not a rare event in a recording,
a near-certainty. Measured on ordinary content before the change, three of four
test files reported `Suspicious pattern: #!` — a one-second sine, a ten-second
sine and ten seconds of white noise. It was visible in this session's own CLI
output on nearly every command run.

This matters more here than a stray log line usually would. §1 offers a
path-validation security layer as a reason to trust this tool. A check that
fires on almost everything does not merely waste attention — it hides the real
hit, which arrives looking exactly like the thousand false ones before it, and
it teaches the user that the validation layer is noise.

The fix was to aim the check, not to loosen it. The patterns were never
interchangeable: `MZ`, `\x7fELF` and `#!` make a file executable and only do so
**at offset 0**; markup and code fragments matter in the container's *text*
regions — RIFF `LIST`/`INFO` chunks a player might read and render — and never
inside `data`, whose contents are arbitrary sample values by definition. A file
that is not RIFF at all still gets its whole scanned prefix searched, since
none of it is audio.

The result reports strictly *more* information than before, not less: zero
warnings across sine tones at 100/440/1000 Hz, ten-second tones, white noise
and a `data` chunk deliberately spelling out `MZ \x7fELF #! <?php <script
import os; eval( exec( system( <html`; and it still catches a shebang, an ELF
header or an `MZ` at offset 0, `<script>` spliced into a `LIST/INFO` chunk, and
markup in a non-RIFF file. Because the surviving warnings mean something, the
CLI now logs them at WARNING rather than INFO, where they had been filed
precisely because they were noise.

Four tests cover hostile input directly — an empty file, a truncated RIFF
header, a chunk declaring size `0xFFFFFFF0`, and a zero-length chunk — because
a scanner whose entire job is untrusted files must not be walkable off the end
of its own mapping or into a loop.

**`analyze --detailed` printed two dataclass defaults as measurements
(2026-08-25).** Found by reading the output of the CLI integration step while
validating the proposed CI, which is a reminder that reading a tool's own
output is a form of testing nothing else replaces.

`AudioMetadata.frequency_range` defaults to `(0.0, 0.0)` and is populated only
inside `if HAS_LIBROSA:`. librosa is in no extra of this project, so on
essentially every install the command reported `Frequency Range: 0.0-0.0Hz`
for a 440 Hz sine — not an approximation and not a stated limitation, but a
default dressed as a result. It now says `not measured (use --spectrum)`, and
says nothing at all when `--spectrum` is already running. `analyze --spectrum`
measures the same quantity for real via `spectral_utils`' pure-Python DFT and
reports 419.9–452.2 Hz for that file, on every install.

`dynamic_range` was the worse of the two, because the answer was already in
hand. It is the crest factor, `20*log10(peak/rms)`, and the standard-library
core reports both peak and RMS — but only the numpy path performed the
division, so the dependency-free install, the one §1 leads with, printed
`Dynamic Range: 0.0dB` for a signal whose crest factor is 3.01 dB. The stdlib
path now computes it, guarding the zero-signal case so silence reports 0.0 dB
rather than an inf or a NaN.

Both belong to the pattern this branch has been closing throughout: the tool
was not wrong about the audio, it was wrong about itself. A default that
reaches the user as a number is indistinguishable from a measurement, and
costs more trust than a missing line ever would.

**The `ml` command deleted (2026-08-25).** `main.py` exposed a top-level
command named `ml`. Its one operation, `enhance`, was:

```python
enhanced = processor.remove_noise(audio, sr)     # spectral subtraction
enhanced = processor.normalize_audio(enhanced)   # peak normalization
```

Two pieces of deterministic DSP. No model, no training, no inference — and
exactly `process --denoise --normalize`, which was already documented. A
duplicate command whose only distinguishing feature was a false name.

Two details make it worse than an oversight. The handler's own comment said
that classify/separate/transcribe had been removed as §4 non-goals, while
leaving the command called `ml`. And `docs/{en,ja}/commands.md` carried a
"naming note" stating that the subcommand *does not perform machine learning*.
The project knew, and answered a false name with a footnote. A caveat under a
claim does not retract the claim; it just moves the reader's work to them.

Deleted with explicit per-item confirmation. `process --denoise --normalize`
does the same work under a name that is true.

**§4 is now mechanized on the CLI surface, not just the sources
(2026-08-25).** `tests/test_no_fantasy_features.py` greps `.py` files for
`torch` / `neural network` / `quantum`, which is why a command literally called
`ml` passed cleanly for its entire life. The guard now also runs the real CLI
and reads what argparse prints — every subcommand name and every `help=` string
— because that is the surface a user actually reads, and a §4 claim on the
first screen is more visible than one buried in a source file, not less.

The parser is built inline inside `main()` and is not importable; the guard
therefore shells out to `main.py --help` and `<cmd> --help`, reusing the
`_run` pattern from `tests/test_cli_parity.py`. Refactoring product code to
suit a test would have been the wrong way round. Negative-tested by
reintroducing an `ml` subparser with the help text "Audio enhancement using
machine learning": both new tests fail, then pass again once it is removed.

**Deleting the instance is not fixing the cause (2026-08-25).**
`ml enhance` on the dependency-free install produced
`AttributeError: 'NoneType' object has no attribute 'frombuffer'` — `np` bound
to `None`, discovered ninety lines from the cause inside `_load_wav_basic`.
Deleting the command removed the first *reachable* instance. `midi extract` and
`midi analyze` still reached it.

`AudioProcessor.load_audio` returns an ndarray from every one of its backends,
so it cannot succeed without numpy; the check belongs there, where the
requirement is, not at each call site where it would need re-adding for every
future caller. It now raises the same actionable message the rest of the CLI
uses.

That exposed the layer above: `cli()` caught only `KeyboardInterrupt`, so
errors this CLI raises *deliberately* — unsupported file type, missing file,
missing optional dependency — reached the terminal as tracebacks with the one
useful line buried inside. It now prints those, and **still does not catch
`Exception`**. Turning a genuine bug into a tidy "Error:" line would make the
tool wrong about itself in a new way, which is the failure mode this branch has
spent its length undoing. A test asserts the distinction, stripping comments
first — the handler explains why it does not catch `Exception`, and the first
version of that test matched its own explanation.

**Every claim in `PRODUCT_ANALYSIS.md` was re-checked; eight were false
(2026-08-25).** That document opens by saying its claims are "cited to
`file:line` so it can be re-verified, not trusted". Taking it at its word and
actually re-running them found:

| Claim | Reality |
|---|---|
| "211 passing, 3 skipped" | 313 / 354 / 443 across three dependency configurations |
| "215 tests, up from 22" | stale by 228 |
| zero-dependency core includes `midi` | `midi extract` / `analyze` exit 1 without numpy; only `compose` / `generate` are stdlib |
| the §4 guard greps "Python sources" | it now reads the CLI surface too |
| orphaned = 3,121 lines / 22.2% | 2,296 / 16.1% |
| `audio_restoration` "blocked on a CLI surface" | wired on 2026-08-25 |
| orphan list of six | three, measured |
| §4's four "fast checks" | **all four return zero hits** |

The last row is the one worth remembering. Those greps looked for
`malware detection`, `Government-Grade` in `gui/package.json`, and unguarded
numpy/scipy imports — every one of which had been fixed, some months earlier.
A maintenance checklist whose items always pass is not verification; it is the
*appearance* of verification, and it is more dangerous than no checklist
because it is reassuring. They are replaced with commands that yield a number
to compare against a recorded one, so drift shows up as a mismatch rather than
as a silent pass.

The same shape has now appeared three times in this branch: the security scan
that fired on everything (PR #26), the guard that never looked at the CLI
surface (this pass), and a checklist that could no longer fail. A check is only
worth its line if you can say what would make it fail — and, ideally, have
watched it do so.

Also corrected here: the "zero-dependency core" strength had listed `midi`
without qualification for months. `midi extract` and `midi analyze` load audio
into arrays. Verified by running every subcommand with numpy blocked and
reading exit codes, which is the kind of check the section now prescribes.

**The three front-door documents, re-verified: thirteen findings, one root
cause (2026-08-25).** After `PRODUCT_ANALYSIS.md` (eight false claims, entry
above), the same question went to the documents a newcomer reads *first* —
`README.md` for people, `PROJECT_STATUS.md` and `CLAUDE.md` for agents.

Three security words the code does not back, all in README: "**ML
processing**" as an optional capability (the `ml` command was deleted the same
day, and §4 forbids the claim regardless); "**RBAC**" for an API whose own
`require_permission` docstring says there is no per-permission authorization
— and this charter's §1 and §5 repeated the word; and "**Sandboxed** plugin
execution", which this section had already conceded is "AST-only, not a
runtime boundary". A project whose stated discipline is honest labelling had
three overclaims in the vocabulary that matters most, on its front page.
"MIDI extraction and analysis" also sat under *Core (standard library)* when
`midi extract`/`analyze` exit 1 without numpy.

The root cause of the rest is a single fact: **the same test count was
hand-carried in four files and read 147, 211, 215 and 443 at the same
time.** Not one of the four was lying when written. Each was a snapshot
nobody was responsible for refreshing, in a file that presented it as current.
Step 2 of Musk's algorithm applies to numbers as much as to code: the fix is
not to correct four copies but to have one. Counts now live only in the dated
header of `PRODUCT_ANALYSIS.md`, which already says "re-run, do not re-read";
`CLAUDE.md`, `PROJECT_STATUS.md` and `README.md` point at the command instead.

Smaller: `api_server`'s root endpoint advertised `docs/user_manual.md` as its
documentation reference. The file does not exist. It now points at
`docs/api_documentation.md`, which does. And `PROJECT_STATUS.md` §4a still
described `personal_config`'s packaging gap as open, months after this section
recorded it fixed.

The §4 guard's third extension follows the same pattern as the first two —
prompted by a real miss, not by foresight. It scanned sources; `ml` lived in
argparse. It scanned the CLI; "ML processing" lived in README. It now scans
`README.md`, `QUICKSTART.md` and `docs/` too, with the same removal-record
exemption, and was negative-tested by re-planting the exact README line.
A claim does not become true by moving to a file the guard skips.

**The suite was mutation-checked, and it holds (2026-08-25).** This branch has
spent its length asking what a claim would look like if it were false. The
claim it had not yet turned on itself is the one underwriting all the others:
*"445 tests pass, therefore the product works."* Passing tests are evidence
only if they would fail when the code breaks, and nothing had established that.

Six fixes from this branch were reverted in the source one at a time, each
followed by a run of only its own test file and a restore: the declipper's
unbalanced crossfade, the resampler's anti-aliasing cutoff, the key-profile
rotation, `--mono`'s idempotency, the quantiser's rounding, and a K-weighting
coefficient nudged by 0.1%. **All six failed exactly the test written for
them**, and `git status` came back empty afterwards.

A static audit in the same pass found no vacuous tests across the suite: no
`assert True`, no `x == x`, no handler swallowing the body it guards. Three
tests have no `assert` statement, and all three are "must not raise" checks
where the call under test is itself the assertion — `_check_module_safety` on a
benign plugin, and the plain-import smoke test.

The procedure is recorded in `PRODUCT_ANALYSIS.md` §4 as the deep check, with
the six revert/test pairs, rather than being automated. Mutating source in CI
is a poor trade — slow, and a failed restore is worse than no check — but the
pairs are cheap to re-run by hand and are the only thing that distinguishes a
suite that defends the code from one that merely accompanies it.

**Nine documentation files described a product that does not exist
(2026-08-25).** The audit that had covered `PRODUCT_ANALYSIS.md`, then the
front-door documents, then the test suite itself, finally reached `docs/`. It
found the same defect `api_server.py` carried until PR #23, in a worse place.

Seven files told the reader to `import chameleon_audio`; one used `audio_tool`;
three invoked `python enterprise_cli.py`, `python chameleon_cli.py` or
`python security_tools.py`. **None of those modules or scripts has ever existed
in this repository, in any commit** — confirmed with
`git log --all --diff-filter=A`. Several pages carried "Enterprise Edition",
"Commercial Release" and "Enterprise Ready: ✅", which is precisely the
vocabulary `README.md` says this charter exists to stop.

In `api_server.py` the phantom imports were dead code behind a permanently
false flag: inert. In documentation they are not inert. Someone copies the
block into a terminal, it fails, and the failure looks like their mistake
rather than ours. That is the argument for deleting rather than annotating,
and it is why a warning banner was rejected — the same footnote-under-a-false-
claim pattern already rejected for the `ml` command.

Deleted with explicit per-item confirmation, 2,240 lines across nine files, all
of them linked from nothing: `security_logs`, `test_cases` and `ui_enhancement`
in both languages, plus the Japanese halves of `batch_processing`,
`performance_benchmarks` and `error_recovery` whose English counterparts are
honest. `docs/en/performance_benchmarks.md` is the model the others should have
followed: it quotes no invented numbers and tells the reader how to measure
their own.

`docs/en/error_recovery.md` was kept and repaired rather than deleted, and the
repair is worth recording because the first description of it was wrong. It was
presented as needing one stale line changed; it actually invoked a nonexistent
`security_tools.py` three times and a nonexistent log file. Its *structure* —
symptom, action, audit — is sound, so the invented commands were replaced with
real ones (`$CHAMELEON_TRUSTED_ROOTS` for path containment,
`~/.chameleon/logs/chameleon.log` for the log that is actually written).

`tests/test_docs_reference_reality.py` now fails if any documented module or
script is absent from the tree. It is deliberately narrower than the §4
vocabulary guard: purely mechanical, checking existence rather than judgement.
Negative-tested with a probe file carrying the exact first code block of the
deleted pages.

The lesson repeats one already in this record. The first scan of these files
looked for two ghost scripts by name and reported `error_recovery.md` as merely
"overclaim"; broadening it to *every* `python X.py` in every document found
three more references in that same file. A check finds what it looks for, and
the gap is never where you already looked.

**The Kubernetes manifest could never have worked (2026-08-25).** Having
audited the analysis document, the front-door documents, the test suite and
`docs/`, the last unexamined user-facing artifact was `k8s-deployment.yaml`.
It is not documentation drift; it is a broken shipped artifact.

All three probes — liveness, readiness and startup — requested `/health` on
port `http`, declared as `containerPort: 8080`. The container's entrypoint runs
`main.py server --port "${CHAMELEON_PORT:-8000}"`, and the Dockerfile says
`EXPOSE 8000`. **Every probe would have failed and no pod would ever have
become ready.** Alongside that: a `metrics` port 9090 with
`prometheus.io/path: /metrics`, a `ServiceMonitor` and a `PrometheusRule` whose
four alert rules queried metrics the API has never exported (`grep -c "/metrics"
api_server.py` → 0); `image: chameleon/audio-tool:v2.0.0` for a project at
1.1.0; and five `CHAMELEON_*` environment variables no code reads.

Fixed rather than deleted, by explicit decision: port 8000, image v1.1.0, the
two Prometheus documents and the metrics port removed, phantom variables
dropped. 18 YAML documents → 16, and the result is verified programmatically
against `api_server.py` and the `Dockerfile` rather than by eye. The header now
states plainly that it is verified against the code and **not** against a live
cluster, because nobody has applied it from this repository and that limit
should be visible to whoever does.

Two things worth keeping from how this went. The HPA's `metrics:` block and the
`metrics.k8s.io` API group are legitimate Kubernetes APIs that a careless
find-and-replace on "metrics" would have destroyed; the resource-metrics
autoscaler is intact and asserted. And the first verification script reported
two failures that were the script's fault, not the manifest's — it flagged
`/metrics` appearing in a comment recording its own removal, and flagged
`POD_NAME`/`POD_NAMESPACE`/`NODE_NAME`, which are downward-API values carried
by `valueFrom` and are k8s convention rather than application config. A check
that is too strict is not safer than one that is too loose; both report
something other than the truth.

`DEPLOYMENT_GUIDE.md` was repaired in the same pass. Its "Monitoring Setup"
configured a Prometheus scrape of `/metrics` and a Grafana dashboard querying
`chameleon_processing_duration_seconds`, `chameleon_queue_length` and
`chameleon_errors_total` — none of which exist, so the scrape 404s and every
panel stays empty. Replaced with the endpoints that do exist (`/health`,
`/system/status`, `/audit/log`) and the two log files actually written. Its
"Database Optimization" section tuned a PostgreSQL `audit_log` table; the
project contains no database code of any kind and the audit trail is a plain
file, so the section was deleted — "(if using)" hedged a capability that exists
in no configuration.

The guide's use of port 8080 is *not* an error and was left alone: it passes
`--port 8080` explicitly, `server --port` is a real flag, and its firewall and
curl examples agree. The manifest was broken precisely because it changed the
port without passing the argument that would have made it true.

**`openapi_spec.yaml` deleted (2026-09-07).** The last of the long-standing
`PROJECT_STATUS.md` §4 deletion candidates, sitting unactioned since it was
first flagged in 2026-07. Re-verified before acting rather than trusted:
still failed to parse (`yaml.safe_load_all` errors at line 28, a second
top-level document with no `---` separator), still referenced by zero code
(`api_server.py` serves its own live OpenAPI schema via FastAPI at
`/openapi.json`), and still carried "Government-focused audio processing
REST API", "authenticate user with government credentials and security
clearance", and an `enable_simd` parameter — all vocabulary or functionality
already removed from `api_server.py` itself in PR #23. It also claimed
version 1.0.0 for a project at 1.1.0.

Repairing 680 lines of hand-maintained, unparseable spec to duplicate a spec
FastAPI already generates correctly and automatically would have been
optimizing something that should not exist. Deleted with explicit per-item
confirmation, alongside the same confirmation that `gui/` should **not** be
touched: unlike the spec, `gui/`'s own README discloses "experimental / not
yet wired up" — an honest label, not a broken artifact, and CHARTER §9's
standing position is that disclosed-unfinished work is not itself a defect.

**The documented onboarding flow itself was broken (2026-09-14).** With
`openapi_spec.yaml` gone, the next unverified artifact was
`personal_config.py`'s `quick_setup()` — what `python personal_config.py
setup` runs, which is the exact command `quick_install.sh` and
`quick_install.ps1` tell a new user to type. It had two defects, both
invisible to the 18 tests added for this module in an earlier pass, because
none of them called `quick_setup()` or `create_quick_commands()` at all.

First, its "Quick Start Commands" printed `python main.py personal analyze`,
`python main.py personal process --normalize`, `python main.py personal
batch`. `main.py` has no `personal` subcommand — confirmed by running it:
argparse rejects it with "invalid choice", exit 2. Every command the setup
wizard recommended to a first-time user failed.

Second, `create_quick_commands()` — which writes `~/.chameleon/aliases.sh`
and `.ps1`, the file `quick_install.sh`'s own next documented step tells you
to `source` — was called only from the bare `python personal_config.py`
branch of `__main__`, never from the `setup` command. A user following the
documented flow exactly would have hit "no such file" at the step right
after the phantom commands.

Fixed by having `quick_setup()` call `create_quick_commands()` itself and
print commands that were actually run, not guessed at, before being written
down: verified end-to-end in an isolated `$HOME`, including sourcing the
generated `aliases.sh` in a real (non-interactive) shell and running
`audio-analyze` against a real WAV file. Five new tests in
`tests/test_personal_config.py` cover it, including one full subprocess
run of `personal_config.py setup` piped blank input, followed by sourcing
its output and using it — no mocking — and one that reads `main.py`'s real
subcommand list from `--help` rather than hardcoding it, so a future rename
cannot silently drift out of sync with this test the way it drifted out of
sync with `quick_setup()` itself.

The building itself briefly harbored one instance of the exact failure mode
it exists to prevent: a first draft of the new subcommand-checking test
contained a dead placeholder line (`... if False else None  # placeholder,
replaced below`) that looked load-bearing but did nothing. Caught before
commit by re-reading the diff rather than trusting that a green run meant
the test was checking what its name claimed; removed and replaced with the
`--help`-derived check described above.

**`docs/agents/SONNET.md`'s own task list was stale (2026-09-14).** Reading
it while looking for the next thing to verify: its "Tasks this session is
well-suited for" section named three specific "honesty pass" targets
(`advanced_validation.py:4`, `gui/package.json`, `batch_automation.py:4`) and
an "import-guard hygiene" task for `spectral_editor.py`/`audio_restoration.py`.
All five were checked directly against the current files. **All five were
already fixed** — the docstrings are honest, `gui/package.json` already
discloses "Experimental... not yet wired", and both modules already guard
their numpy/scipy imports (confirmed by grepping for the `try:`/`except
ImportError` pattern, present in both). The test-coverage bullet also still
named `audio_restoration` and `personal_config` as zero-coverage; both have
been covered since PR #24 and the onboarding-flow fix immediately above this
entry.

This is the same defect class as `PRODUCT_ANALYSIS.md`'s eight false claims
and `README.md`'s three security overclaims, in a file with a narrower and
more specific kind of cost: it exists specifically to direct what a future
Sonnet session works on next, so a stale task list there doesn't just misinform
a reader, it actively steers the next session's effort at problems that no
longer exist.

Fixed by removing the specific stale claims rather than replacing them with a
fresher hardcoded list, which would only rot again the same way. The section
now points at `PRODUCT_ANALYSIS.md` §3's live backlog table and its
Coverage-gaps section as the source of truth, states explicitly that P4 items
are `OPUS.md`'s to take (they need judgment, not just execution — that
division was already implicit in both files but never stated), and names this
exact incident as the reason not to hardcode the next one.

**The generated quick commands invoked a `python` that may not exist, and
the librosa denoiser subtracted the signal itself (2026-09-19).** Two bugs
surfaced by the same method — running the verification gate on a machine
whose environment differed from the one the suite was written in.

First, `test_the_full_documented_flow_works_end_to_end` failed on a host with
no `python` binary at all: `personal_config.py`'s `create_quick_commands`
wrote `python {cwd}/main.py ...` into every alias in `aliases.sh` and every
function in `aliases.ps1`. `quick_install.sh` goes out of its way to support
python3-only systems for its own steps, but the artifacts `setup` produces
then failed in every shell that did not have a `python` on PATH — which
includes a fresh shell with no venv activated, the exact situation the
aliases exist for. Fixed by generating `sys.executable` (quoted): the
interpreter that ran setup is the one command guaranteed to exist and to see
the right site-packages. In the same function, `~/.chameleon/` was only ever
created as a side effect of `PersonalConfig.save()` — calling
`create_quick_commands` standalone crashed with FileNotFoundError; it now
makes the directory itself. The PowerShell heredoc also emitted
`SyntaxWarning: invalid escape sequence` for its literal `\m`/`\S` backslash
sequences; it is now a raw f-string with identical output.

Second, installing librosa — a package in the `[audio]` extra that none of
the three documented test configurations installs — turned the suite red on
`test_restoring_clean_audio_changes_nothing`: `AudioRestorer.restore()` on a
clean sine returned it ~14 dB down. Root cause in
`AdaptiveDenoiser.estimate_noise_profile`: it defines "quiet sections" as the
decile of frames with the lowest RMS and averages their STFT magnitude into
the noise profile. On stationary material the quietest decile is not noise —
it is the content — so `denoise` subtracted 0.8× of the signal's own
spectrum. The `np.ones` fallback the docstring claimed removed was still
present, producing the same blanket −20 dB when the strict `<` selected no
frames at all. Fixed the way the module already handles missing librosa:
refuse with a named reason when the quietest decile is within ~6 dB of the
loudest (no real quiet sections exist), and let `restore()` report the step
as skipped rather than applied. Material with genuine quiet sections still
denoises; a clean sine now passes through bit-exactly.

Both are the same lesson the file keeps re-teaching: an environment is part
of the test. The alias bug was invisible where `python` exists; the denoiser
bug was invisible where librosa is absent. The fix for the second is also a
reminder that `PRODUCT_ANALYSIS.md`'s "three dependency configurations" does
not exercise the `[audio]` extra's librosa path — a gap worth knowing rather
than closing (the denoiser is deliberately unexposed on the CLI; see
`tests/test_restoration_cli.py`'s rationale).

**Q: What should the CLI exit when pre-flight rejects every supplied file?**
A (2026-09-19): The sentinel `batch_process` returned for an all-filtered
input list carried only `{"error": ...}`, and `analyze`'s error branch read
`result['file']` — a `KeyError` traceback and exit 1 where the documented
table (and the `ExitCode` docstring) promises INPUT(3) for a supplied path
that fails pre-flight validation and SECURITY(4) for a policy rejection.
Two subprocess tests had pinned `== 1`, i.e. they were asserting the crash's
side effect, not the contract. `_filter_safe_files` now returns
`(safe, rejections)` with each rejection tagged `"input"` (suffix, missing,
failed WAV inspection) or `"security"` (trusted roots, size cap); the
sentinel carries `exit_code` — SECURITY if any security rejection occurred,
else INPUT — and `analyze`, `process` and `batch` return it instead of
indexing into a file-less dict. Mixed batches (some files rejected, some
processed) keep the existing per-file-warning + normal-results behavior.

**Q: Should vinyl mode report its own step vocabulary?**
A (2026-09-19): No — `VinylRestorer.restore` returned `steps_applied` /
`steps_skipped` with `{"step", "reason"}` entries, which `AudioRestorer.
restore(mode="vinyl")` merged into a dict already keyed `applied_processes` /
`skipped_processes` with `{"process", "reason"}`. A caller reading the
documented keys saw `applied_processes == []` for a vinyl restore whose
repairs all ran — under-reporting, the same defect class the module's
honesty tests exist to prevent. `VinylRestorer` is internal: its only
caller is `AudioRestorer.restore`, so it now emits the shared keys directly
rather than translating at the seam. `snr_improvement` stays as a
vinyl-specific extra.

**Q: `apply_effects` "compression" — keep the waveshaper or route to the real
compressor?**
A (2026-09-19): Routed to `mastering_chain.Compressor`. The per-sample dB
remap it replaced is soft-clipping — it reshapes each waveform period, which
measurably adds harmonics (3rd at −13 dB rel. fundamental on a 0.8 sine at
−20 dB/4:1). The name "compression" and its threshold/ratio parameters
promise dynamics control, and the project already owns a correct one
(envelope follower, centred soft knee, gain smoothing, stereo linking), so
reusing it is the DRY fix as well as the honest one. New optional params
`attack`/`release`/`knee`/`makeup_gain` expose the existing config surface.
`"compression"` joined `_EFFECT_REQUIREMENTS` (numpy) so a numpy-less
install gets the same named refusal the other guarded effects get instead
of a silent skip.

**Q: How far to take the "errors must exit nonzero" sweep?**
A (2026-09-19): Through `stream` and `midi`. `stream` printed its "Starting
real-time audio stream" banner unconditionally before the call that always
fails when PyAudio is absent — now gated on `HAS_PYAUDIO` so the claim is
only made when it can be true. The same rule later caught `server`, which
printed "Starting API server on ..." before the uvicorn import that
decides whether a server can start at all — the banner moved inside the
success branch. `midi`'s failure paths printed to stdout and
fell through to exit 0 (`Analysis error: …`, "Failed to generate
composition/demo", and three `generate_midi` write failures that printed
nothing at all); they now go to stderr with `ExitCode.ERROR`. The `batch`
command's all-rejected case was folded into the same day's exit-code fix.
Deliberately untouched: `midi extract` finding zero notes stays exit 0 —
"processed, found nothing" is a result, not an error.

**Q: Should the three spectral-subtraction implementations be consolidated?**
A (2026-09-19): No — evaluated and declined. They look like three copies but
are not: `main.remove_noise` auto-estimates the floor per bin (10th
percentile + Rayleigh rescale) via scipy, `audio_restoration.AdaptiveDenoiser`
estimates from the quietest decile with an honest refusal on stationary
material via librosa, and `spectral_editor.noise_reduce_selection` subtracts
a *user-selected* noise print via its own SpectralProcessor. The only real
duplication is the 4-line magnitude-subtract-floor-reconstruct kernel; a
shared helper would save ~4 lines while coupling three working DSP paths and
three different STFT backends. That is the unnecessary abstraction this
charter exists to prevent. The backlog row is closed as declined.

**Q: Should dither get a `--dither` CLI flag or become default?**
A (2026-09-19): Neither. Dither stays opt-in through
`ProcessingConfig.apply_dither`; deterministic-by-default output is the
recorded decision and there is no user demand for a flag. Reopen only on a
real request.

**Q: Why does the effects-file loader warn on unknown names instead of erroring?**
A (2026-09-19): `_load_effects` (shared by `process`, `stream`, `batch`)
rejects malformed shapes as `ExitCode.INPUT` — an unvalidated file either
silently no-oped (non-object top level) or leaked an AttributeError
(non-object params). Unknown *names* warn rather than fail because a typo in
an optional extras' effect should not hard-fail on an install that lacks the
package anyway; the warning tells the user the effect was ignored, which is
the honest answer. Amended same day: the first cut required every effect
value to be an object, but `eq`'s schema has always been a *list* of band
objects — the validator rejected the only input that could ever run, and a
dict-shaped eq crashed downstream instead. Per-effect shapes are now
validated (`eq` = non-empty list of `{frequency, gain, [q]}` objects;
`reverb`/`compression` = objects). Lesson recorded: validating shape without
checking each effect's real schema swaps one lie for another.

**Q: Declip restores crests above ±1.0 but the writer clamps to [-1, 1] —
who wins?**
A (2026-09): Attenuation, not re-clipping. `repair_audio` used to return
peaks >1.0 into a `save_audio` that `np.clip`s, so a file clipped *at* the
rail came back bit-identical — the repair ran and was then destroyed at
write time. A repair whose result cannot be represented is a silent no-op,
which is the same class of dishonesty §4 exists to prevent. Repaired audio
with peak >0.999 is now scaled to fit; the shape is kept, the plateau is
gone. The alternative — writing 32-bit float — would have preserved level
but changed the output format for every caller; fitting the format the user
asked for is the smaller surprise. Note the test gap that hid this: every
declip test clipped *below* the rail, where the clamp never bites. The
realistic case (rail clipping) is now pinned by
`test_a_clip_at_the_file_rail_is_repaired_not_reclipped`.

**Q: What does a noise estimate mean for a bin that never goes quiet?**
A (2026-09): Nothing — there is no observation to estimate from.
`remove_noise` derived each bin's noise floor from its p10 magnitude,
which works while every bin is empty at some point and fails silently on
a sustained tone: p10 is then the tone itself, and the scaled "noise"
exceeds the bin's own p90, so subtraction drove a held note down ~21 dB.
Bins whose estimate exceeds their p90 are now skipped entirely. Same
lesson as the rail-clip fix above, one cycle later: every suite fixture
used *changing* content, so the degenerate input — the one the feature
exists for, in both cases — was untested. When a property is pinned,
also pin the pathological input the property is supposed to survive.

**Q (2026-09-19, cycle 42): Should a flag the docs place after a
subcommand be rejected for being "in the wrong place"?**
`docs/*/commands.md` showed `plugins list --json` but argparse put
`--json`/`--directory` on the parent `plugins` parser, so the
documented order errored with "unrecognized arguments". Two honest
fixes existed: correct the docs, or accept both positions. We accepted
both — the docs' order is the one users will type. Implementation
detail worth recording: sharing the parent's `dest` on the subparser
fails twice over — the subparser's default silently clobbers the
already-parsed value, and `action="append"` then drops earlier
`--directory` values. Separate dests (`plugins_sub_*`) merged at
dispatch avoid both. Generalization: when docs and the parser disagree
about where a flag goes, the flag's *advertised* position is a claim
that must hold — verify the documented spelling actually parses.

**Q (2026-09-19, cycle 44): What about flags accepted on the wrong
operation?**
`batch dir normalize --sample-rate 22050` used to parse fine and drop
the value — the flag lived on the shared subparser, its consumer only
ran for `convert`. The same shape in `process` (`--threshold` without
`--trim`, `--convert-*` without `--convert`). An accepted flag that
names a different operation is a claim, and a claim with no consumer is
a lie. All such flags now reject with USAGE(2) and name the operation
they belong to. Pattern for future flags: if a flag only feeds one
operation, the dispatch must reject it everywhere else — argparse
cannot express per-operation flags on a shared parser, so the
validation lives in the dispatcher, next to the consumers.

**Q (2026-09-19, cycle 45): Is a success-only audit log an audit
log?**
Every API endpoint logged exactly once — on success. The 403 on
someone else's file, the 404 while probing filenames, the 429 throttle
on login: all invisible. An audit trail that records compliance and
skips violations answers "who did what" but never "who tried what" —
the second question is the one a security log exists for. DENIED
entries now record the attempted resource and the refusing status for
every guarded endpoint. LOGIN already logged FAILED; it was the model
the rest of the file failed to follow.

**Q (2026-09-19, cycle 51): Did the cycle-44 rule reach every flat flag
namespace?**
`midi` was the last subcommand whose flags all live on one shared
parser, and it had the same disease: `midi analyze --tempo 90` parsed
and discarded the value, `midi generate --length 30` ignored the bound
and wrote the fixed one-octave demo anyway, `midi compose --input f`
dropped the file. Six flags, four operations, zero scope checks. The
fix reused the cycle-44 shape (a per-operation owner map, USAGE(2)
rejection naming the owning operations) plus one new ingredient:
`--mode`/`--tempo`/`--length` had parser-level defaults, which makes
"user typed it" indistinguishable from "default". Their defaults moved
to the consumers (`args.tempo or 120.0` at the call site) — a flag
whose default you cannot see is a flag whose scope you cannot enforce.

**Q (2026-09-19, cycle 52): Does a parsed number mean a valid number?**
`--tempo 0` divided by zero inside `generate_midi_file`, `--tempo 2`
overflowed the 24-bit us-per-quarter field, `--length -5` died in the
generator, and `server --port -1` surfaced a uvicorn OverflowError
traceback. argparse proves a flag *parsed*; nothing proves it *fits the
domain it feeds*. The domain here is physical/binary — the MIDI tempo
field is 24 bits, so BPM has a real floor (~3.6), and a socket port has
a real ceiling (65535). Range checks belong next to the same dispatcher
scope checks from cycles 44/51: the answer to "is this value usable" is
INPUT(3), not a translated exception.

**Q (2026-09-19, cycle 53): Are structured config inputs held to the
same standard as flags?**
The effects JSON file is a user-typed parameter surface just like
argv — and it failed the same three ways: shape was validated but
values weren't (-100 Hz eq band silently dropped, ratio -1 accepted),
unknown keys died silently ("treshold", and a `damping` knob nothing
reads), and the DSP's Nyquist guard skipped bands without a word.
`_load_effects` now checks value domains per effect and warns on
unconsumed keys. Rule of thumb for the next structured input: if a
caller can type it, a validator must own it — and "validator" means
values and names, not just JSON shape.

**Q (2026-09-19, cycle 54): Does every user-supplied output path get an
input-error answer?**
`analyze --export /dev/null/x.json` used to end in a NotADirectoryError
traceback — `cli()` catches ValueError and FileNotFoundError, but
IsADirectoryError, NotADirectoryError and PermissionError are OSError
siblings that sailed straight through. An output path the user types is
the same kind of input as an input file; the write now validates it
(`_sanitize_cli_input`) and maps every OSError to INPUT(3). Audit rule:
wherever the CLI opens a path the user supplied, the failure answer is
"Error: ..." + INPUT(3), never a traceback — and the exception class to
catch is OSError, not whichever subclass happened to fire first.

**Q (2026-09-19, cycle 58): Does a processed file have to match its
input's length?**
`process --denoise` produced output 888 samples longer than the input —
`signal.istft` emits frame-aligned output, so its boundary extension
pads the tail to a full hop. A 2-second file came back with +20 ms of
dead air: harmless to listen to, but it silently breaks sync with any
asset aligned to the original timeline, and it makes "Processed" a
lie about what the operation did. The fix is one slice
(`[..., :audio.shape[-1]]`); the rule it generalizes is that an
operation which does not change duration must return exactly the
input's duration — not approximately, exactly. All other istft paths
(librosa in `audio_restoration`, `spectral_editor`) already take a
`length` argument; scipy's does not, which is why this one survived
input-validation and flag-consumer audits alike — it needed a
measured output, not a code read.

**Q (2026-09-19, cycle 59): Is saturation on write a warning-worthy
event?**
`save_audio` ran `np.clip(audio, -1, 1)` and said nothing — so an
effects chain that overdrove the signal (+12 dB EQ on a 0.37-peak
tone) produced measurably wrong output (+10 dB delivered) with a
perfectly happy "Processed" line. Hard-clipping at the integer-PCM
boundary is the correct *behavior*; hiding it is the defect. The
writer now counts overrange samples and warns once per file with the
count and the path. Audit rule: a lossy guard that fires is
information the user needs — silent clamps protect nobody.

**Q (2026-09-19, cycle 61): What does "shaped" dither minimally mean?**
The config documented `dither_type="shaped"` but the code fell back to
TPDF — an honest warning, still an unimplemented promise. The catch:
`_apply_dither` only *adds* noise; real noise shaping needs the
quantization error, which doesn't exist until the int16 write. The fix
quantizes on the 16-bit grid inside the dither stage (values land
exactly on the grid, so the later PCM write is transparent) and feeds
`v - q` back with a +1 tap — a (1 - z^-1) high-pass on the error.
Subtlety worth keeping: the fed-back error must exclude the dither
(`v = x + e`, quantize `v + d`), or the white dither gets shaped too
and the error spectrum stays almost flat (measured HF/LF 1.6 vs 26.0
after the fix). Error feedback is inherently serial — the loop is
scalar Python, acceptable on an opt-in mastering path.

**Q (2026-09-19, cycle 63): Is a mid-pipeline parse failure an input
error or an internal one?**
The deep inspector checks the magic number, so a file with a valid
RIFF header but a truncated fmt chunk sailed through pre-flight and
then died mid-parse — as ERROR(1), the internal-failure code, or
worse, as a raw `struct.error` ("unpack requires a buffer of 16
bytes"). Exit-code semantics are part of the API contract: INPUT means
"fix your input", ERROR means "we broke". A corrupt WAV is never "we
broke". The fix tags each per-file failure with a kind at the catch
site (ValueError/FileNotFoundError = input, the rest = internal) and
downgrades the exit code to INPUT(3) only when every failure was an
input failure — mixed internal+input still answers ERROR. One related
honesty fix in the same pass: a data chunk shorter than its declared
size used to be analyzed silently; it now logs a truncation warning,
because a shorter-than-declared file is a fact about the input.

**Q (2026-09-19, cycle 65): Does "file written" mean "file a reader
can read"?**
`midi extract` reported "1 MIDI notes: A4" and saved a file with a
valid MThd header — and a note-off delta encoded as `04 84 80`, which
no MIDI parser can read. `_write_variable_length` built the varint
LSB-group-first with the continuation bit on the wrong byte; only
deltas < 128 ticks survived, and nearly every real note is longer.
Three commands (extract/compose/generate) claimed success on corrupt
output. The lesson generalizes past MIDI: a serializer's contract is
"the next reader accepts this", not "I wrote bytes". Test that reads
the artifact back would have caught this on day one — every binary
writer should have a round-trip parse test, not just a byte-shape
assertion.

**Q (2026-09-19, cycle 66): Round-tripped bytes can still be wrong --
whose clock does a delta tick on?**
The varint fix made MIDI files *parseable*; the same test then showed
they were *wrong*: a 1 s note encoded as 480 ticks plays back 0.5 s at
120 BPM and 1.0 s at 60 BPM, because `seconds * 480` assumed 1 second =
1 quarter note. The unit error was invisible until the tempo meta event
(cycle 50) made tempo a real input -- the writer silently hard-coded
tempo=60-equivalent scaling while the header claimed another. A file
format's delta fields carry an implied unit (here, "beats", not
"seconds"); whenever a header field changes the unit's meaning
(`tempo`, `tpq`), every delta must be computed in the derived unit, not
the raw input's. A round-trip test that only parses bytes won't catch
this -- it has to check the value *means* the right thing.

**Q (2026-09-19, cycle 68): Same key, same meaning -- across install
tiers?**
`analyze --export` on the numpy path reported `size_bytes` =
audio.nbytes (the decoded float array), `format` = "array", `bit_depth`
hardcoded 16 -- while the stdlib path reported the real file's values
for the same keys. Two configs, same JSON schema, different semantics;
anyone diffing exports across installs would chase phantom changes.
The fix is the rule: file-derived fields must come from the file
(backfill after array analysis), and a field a tier doesn't measure
serializes null -- never a default tuple or 0.0 that reads as data.
Audit rule #10: when two code paths emit the same schema, diff the
values on identical input, not just the keys.

**Q (2026-09-19, cycle 69): Is truncation a quantization rule?**
`core._apply_gain_safe` wrote `int(sample * gain)` -- truncation toward
zero. Every PCM writer worth the name rounds to nearest; truncation is
a systematic ~0.5-LSB inward bias on every sample, inaudible but
provably wrong against the math. One word changed (`int(round(...))`)
and the stdlib path became sample-exact against the ideal, even
*ahead* of the float32 numpy path's ±1-LSB wobble on .5 boundaries.
`int()` on a float destined for a quantization step is a rounding
decision whether or not you meant to make one -- say which rule.

**Q (2026-09-19, cycle 70): What does the denominator in "2/2" count?**
A batch over 2 good + 2 corrupt files printed "Processed 2/2 files
successfully" and exited 0. The 2 refused files had been filtered at
pre-flight inspection -- so they existed in *no* tally: not attempted,
not failed, not counted. `process` on the same file answers INPUT(3);
`batch` made it disappear. "N/M succeeded" is only honest if M is
*inputs*, not *inputs that survived a filter the report doesn't
mention*. Pre-flight rejections are now appended to the results so the
denominator is the input count and the exit code classifies them the
same way the all-rejected sentinel already did.

### Open questions (next contributor: decide before building)
- **True-peak (4× oversampled) metering — RESOLVED (2026-07).** Implemented in
  both meters: `mastering_chain.LoudnessMeter.measure_true_peak` (scipy
  polyphase resampler) and, added in the same cycle,
  `bs1770_loudness.measure_true_peak` / `measure_true_peak_multichannel` — a
  pure-Python (no numpy) version wired into `analyze --loudness`, bounded to
  the same sample cap (~0.4s/65k samples). The coefficient-verification
  concern was resolved not by transcribing the standard's example FIR table
  (still deliberately avoided — an unverified "standard" table is exactly the
  unfalsifiable claim §8 forbids) but by *generating* a windowed-sinc
  polyphase filter from first principles and validating it against scipy's
  independent resampler (agreement <0.05 dB). Both are labelled accurate
  estimates, not certified-coefficient measurements.

- **Plugin sandbox is AST-only, not a runtime boundary**: `exec_module()`
  gives plugin code full, unrestricted Python builtins once it passes the
  static AST check above. A determined attacker could still reach dangerous
  functionality through patterns the AST walk doesn't enumerate (e.g.
  building attribute-access strings dynamically, walking live object graphs
  via `type(x).__subclasses__()` chains not literally spelled out in source).
  Closing this fully needs a runtime-restricted execution environment
  (custom `__builtins__`/globals for `exec_module`), which is a real
  architectural project, not a follow-up patch.

- **openapi_spec.yaml — RESOLVED (2026-09-07): deleted.** Confirmation was
  given naming this item; see the resolved entry below.

- **gui/ scaffold — keep, delete, or actually wire up?** Experimental React/
  TypeScript/Electron app, self-labeled unwired in its own README, not built
  by the Dockerfile. Needs an explicit user decision (asked, not yet
  answered): label honestly and leave as-is, delete like other orphaned
  surfaces, or invest in actually wiring the Electron shell to the CLI/API.

- **core.py's RealtimeAudioProcessor — RESOLVED (2026-08-25): deleted.**
  Confirmation was given naming this item; see the resolved entry above.

- **BatchProcessor.process_directory (sync) — RESOLVED (2026-07):** the sync
  `_execute_operation` was implemented (rather than deleting the sync path),
  along with two latent crashes it exposed (dict-only `result.data`
  assumption; async tuple leak). See the "Decisions Made" entry above.

- **Broken active CI workflow**: `.github/workflows/ci-cd.yml` is still the old 409-line
  fantasy pipeline (k8s/staging/prod deploys, a missing `deployment_manager.py`,
  `tests/smoke/` / `tests/health/` that do not exist). A working replacement sits at
  `ci/proposed-ci.yml`; adopting it needs a maintainer with `workflows` permission to run
  the copy documented in `ci/README.md` (the automation account that produced this branch
  cannot push workflow changes).

**Q: `batch --quality` offers four tiers — do four behaviors exist?**
A (2026-09-19): No — the knob was a fantasy tier list. `config.quality` had
exactly one consumer (`normalize` applies a soft clipper only when
`quality == "high"`); `low`/`medium`/`lossless` were accepted, stored, and
did nothing distinguishable. An option whose values cannot be told apart is
the §4 sin in miniature — it promises a dial that is not connected. The
flag now offers the two real behaviors (`standard`/`high`); the legacy
names are still accepted but map to `standard` with a stderr note, so
scripts keep running while the docs stop lying about what the knob does.
Deleting the flag outright was rejected: `high`'s soft clipper is real
behavior users may want off, and a boolean-ish choice is the smallest
honest surface that keeps it reachable.

**Q: `midi --key`/`--mode`/`--quality` are real flags — are they wired?**
A (2026-09-19): Two of three were dials connected to nothing. A
consumer-audit of every CLI flag found `midi compose`/`generate`
hard-coded C major while accepting `--key`/`--mode` (documented in both
docs and help), and `batch --quality` offered four tiers where only
`high` had any effect. The midi flags are now wired (transposition,
flat spellings, a real i-v-VI-iv minor progression, unknown key →
INPUT); --quality collapsed to `standard`/`high` with legacy values
aliased with a note. The audit pattern that found them — "accepting an
argument without a consumer is a claim, not a convenience" — is the same
one that caught the eq-schema regression: verify a flag by tracing it to
a consumer, not by reading the help text.

**Q: `--target-peak 2.0` succeeds and writes a file — is that honest?**
A (2026-09-19): No — closed by intake validation. The numpy normalize path
applied the requested gain and let the soft clipper silently crush the
overshoot, so a physically impossible target "succeeded" at peak 1.0 while
the help text advertised "0.0-1.0". The stdlib `core.normalize` and the
API (`Field(ge=0.1, le=1.0)`) already rejected the same input — the numpy
CLI was the odd surface out. `process` and `batch` now reject out-of-range
values as INPUT before any work starts. Same audit pattern as the
--key/--mode and --quality findings: where the advertised contract and
the code diverge, either enforce the contract or fix the text.

**Q: The API accepts `options` on batch submit — does it reach anything?**
A (2026-09-19): It did not — stored in job_data, never read. A normalize
job sent `options.target_peak` and ran the default 0.95. Same defect
class as the dead CLI flags found the same day: an accepted field with
no consumer is a promise the API does not keep. `target_peak` is now
wired into the normalize call, unknown option keys are rejected 422 at
submit time, and the (0,1.0] range is validated there too. The rule for
future fields: a request field without a consumer either gets wired or
rejected — never stored-and-dropped.

**Q: Do config schemas hold dead claims too (`use_gpu`, `audit_logging`)?**
A (2026-09-19): Yes — `ProcessingConfig.use_gpu` existed with zero
consumers (a §4 GPU claim inside the config schema, invisible to the CLI
help-grep that caught the CLI-level offenders), `remove_dc_offset` was
the same dead dial, and `SECURITY_CONFIG['audit_logging']` promised a
switchable audit log while events logged unconditionally. All three
removed; the fantasy-features test now source-greps GPU-toggle names so
they cannot return on a non-CLI surface. Auditing rule extended: a claim
is a claim whether it lives on a flag, a field, or a config key.

**Q: `/auth/login` accepts a client-declared `clearance_level` — who
bounds it?**
A (2026-09-19): Nobody did. A client claiming TOP_SECRET received it,
and privileged paths (cross-owner file access, others' job status) key
off that session field. The single-credential dev auth means it cannot
cross users today, but the model grants whatever is asked with no
server-side bound — latent the day a second credential exists. Fixed by
cap: `CHAMELEON_API_MAX_CLEARANCE` (default TOP_SECRET, preserving
current deployments) bounds claimable clearance, and the response and
audit log now report the granted level rather than the claimed one.
Removing the field outright was rejected — it is a documented request
field and the privilege model itself is legitimate; the defect was the
absence of a server-side bound.

**Q: Is dormant privileged code acceptable if unreachable today?**
A (2026-09-19): No — `get_current_user` carried a mock-user branch behind
`require_authentication` (always True): unreachable, but a single dict
edit from a live SECRET bypass. Dead code that grants privilege is worse
than no code; removed. Also fixed a latent crash in the same function:
the expiry default `datetime.min` is naive and would TypeError against
an aware `now` if `expires_at` were ever absent. Per-request expiry and
idle cleanup were then verified end to end (expired session -> 401 and
removed from the registry).

**Q: Should `midi analyze` reject a .mid input with "Unsupported file type"?**
A (2026-09-20): The natural input for a command named `midi analyze` is a
.mid file, but these ops analyze *audio* for musical content. "Unsupported
file type" + ERROR(1) left the user guessing which part was wrong and
mis-claimed an internal failure. Pattern: when a command's name invites an
input its implementation can't take, the refusal must name the trap, not
the type. Now INPUT(3) with "this command analyzes audio".

**Q: What should a 0-frame WAV do -- crash, empty output, or rejection?**
A (2026-09-20): Follow the stdlib path's existing convention: transforms
whose purpose needs content answer INPUT(3) "No audio signal found"
(normalize, trim, master already did); analyze reports all-zero stats.
The numpy path violated this both ways -- raw reduction tracebacks
(declip/dehum/denoise) and silent empty writes (normalize/convert).
Same file, same answer across tiers is the standing rule. Buffer-level
transforms still return identity on empty (a buffer isn't a file a
user pointed at), so the dispatch guard carries the file-level refusal.

**Q: Two inputs, one output path -- reject, rename, or warn?**
A (2026-09-20): Warn. Rejecting breaks legitimate same-name workflows
(cp and mv overwrite too); renaming changes a documented naming scheme
scripts may parse. But "Processed x2, output x1" without a word is a
silent clobber -- the guard that fires is information. Warning names the
colliding stems and the directory so the user can act.

**Q: Why did Ctrl-C do nothing during a batch?**
A (2026-09-20): asyncio.Runner installs a SIGINT handler that *cancels the
main task* -- a cancellation deliverable only where the coroutine
suspends. All processing is synchronous inside that coroutine, so the
interrupt queued behind work that never awaited and evaporated when it
returned: Ctrl-C produced exit 0 with every file processed. Two fixes:
restore `default_int_handler` at the top of main() (the KeyboardInterrupt
must be a real exception wherever it lands), and on BaseException shut
the executor down with cancel_futures=True -- the default
shutdown(wait=True) would otherwise run every queued file to completion
even after the interrupt propagated.

**Q: Is a valid-but-undecodable file "invalid input"?**
A (2026-09-20): No. The PCM-only parser collapsed "non-PCM encoding" into
the same None as genuine corruption, so a perfectly valid float32 WAV was
reported "Invalid WAV file format" -- a lie about the user's file that
sends them debugging the wrong thing. The parser now records a rejection
reason ("Unsupported WAV encoding (format tag N) ... install the audio
extra") which flows through every caller, and the CLI maps it to
"internal" kind: a capability gap is ERROR(1), not INPUT(3) -- the same
rule as the missing-extra case.

**Q: Should an extra include a tool that conflicts with another extra?**
A (2026-09-20): No -- check the conflict before listing, not after. Adding
`safety` to [dev] silently upgraded pydantic to v2 and broke the [api]
extra's pin (fastapi 0.99 needs pydantic<2). `pip check` after installing
is the verification step that catches transitive dep conflicts; an extra
that can't coexist with a sibling extra doesn't belong -- the Makefile's
`|| true` already treats safety as best-effort.

**Q: CLI flag vs env var -- same value, same strictness?**
A (2026-09-20): No -- an explicit flag is a claim in an argv; an env var is
ambient configuration. `--max-workers 0` gets a hard INPUT(3) rejection,
matching --sample-rate. But `CHAMELEON_MAX_WORKERS=-3` gets a warning and
the default: env vars feed a dataclass factory with no exit-code channel,
and refusing to start over a stray shell variable is worse than warning.
The shared rule: never let a bad value through *silently* -- the user must
either be stopped (argv) or told (ambient config).

**Q: A parameter is a float -- is it validated?**
A (2026-09-20): No -- isinstance(x, float) admits NaN and Infinity, which
defeat every domain comparison (NaN <= 0 is False; 0 <= NaN <= 1 is False).
json.loads accepts the literals NaN/Infinity by default, so a JSON config
file can smuggle them into any "numeric" field. The check is
isinstance(x, (int, float)) AND math.isfinite(x), in that order, before
any range assertion.
- Verify the gate is the gate: `advanced_validation.py` exiting 0 was treated
  as the third verification step for many cycles, but it is the production
  module (`DeepFileInspector`) whose `__main__` prints a demo — the documented
  gate is `validation_test.py`. A green run of the wrong script is not a green
  gate; match the command to the document before trusting it.
- A deleted command can survive in a doc's `{a,b,c}` usage synopsis because no
  fantasy-feature grep matches a comma-list token. Compare the docs' choice
  list to the parser's actual subcommands — pattern scans don't see lists.
- A loader that collapses exceptions to None loses the failure's *kind*: the
  sandbox's SecurityError reached stderr but `load_failures` could only store
  a generic string. Re-raise the exceptions whose type is the information
  (security), swallow only the kind already conveyed by "no plugin loaded".
- Channel weighting needs the layout: implementing BS.1770 surround weighting
  by *guessing* a layout from the channel count would read wrong on quad/
  ambisonic material. The WAV dwChannelMask is the only honest source; when
  it's absent every channel stays at 1.0 and the label says "no surround
  weighting" rather than pretending. If you can't identify it, don't guess it.
- A blocklist covers what it names, not the escape set: the plugin audit
  blocked `__globals__`/`__subclasses__`/`__mro__` but left `__class__`,
  `__dict__`, `__base__`, `__code__`, `__getattribute__`, `__func__` and
  `__self__` -- the introspection dunders that make the dangerous ones
  reachable. Add the whole sibling set, or a motivated reader just takes
  the next step. And keep the docstring honest: this is static analysis
  that raises the bar, never a runtime boundary -- `exec_module` still
  runs with host builtins, so the prose says "audit", not "sandbox".
- Enumerating badness admits everything unenumerated: the plugin audit's
  module list named os/sys/subprocess/etc., so `import pathlib` sailed
  through and `Path(...).write_text()` wrote a file with zero flagged
  constructs (verified end to end). A sandbox import check must be
  deny-by-default -- an allowlist of pure-computation modules -- because
  the set of dangerous capabilities is open-ended (io, shutil, wave,
  sqlite3, gc, inspect, logging file handlers, ctypes, threading all
  reach the same host). The escape hatch is PluginConfig.allowed_imports
  or sandbox_mode=False for deliberately trusted code.
- Frame objects are builtins' back door: `e.__traceback__.tb_frame.
  f_globals` reaches `__builtins__` with no import and no dunder a naive
  scan blocks (verified). Any object graph edge that lands on a frame --
  exception tracebacks, generator gi_frame, coroutine cr_frame/ag_frame,
  tb_next walking -- must be on the attribute blocklist alongside
  __globals__, or the dunder list is a door with a wall missing.
- Limits that only wrap some plugin code are no limits: the sandbox
  already enforced max_execution_time around execute_plugin() calls --
  but `plugins list` runs module top-level code and initialize() at LOAD
  time, unbounded, and a plugin whose initialize slept 120s hung the CLI
  outright (verified: SIGTERM needed). Whatever runs plugin bytes must
  run them inside the limit. Also: a TimeoutError swallowed into the
  generic except-None path loses the failure's kind -- a timed-out plugin
  is not "no valid plugin class". Re-raise it like SecurityError so
  load_failures names the real reason.
- State files are written like state files: open('w') truncates first, so
  a kill mid-write produced a truncated JSON that the next load reported
  as *user* corruption -- the crash was ours, the blame theirs. Every
  state write (config, library db, generated scripts) goes through a
  sibling temp file + os.replace now: readers see the old file or the
  new one, never a partial write.
- A requirement check keys on presence, not on work: `apply_effects` flagged
  `{"eq": []}` as needing scipy because the *key* was present, though zero
  bands compute nothing. Requirements should attach to the work requested,
  not the key naming it -- but only where emptiness really is nothing:
  `{"compression": {}}` is still a request because it runs on documented
  defaults, while `{"eq": []}` has no defaults to run.
- A feature's own help text can outlive the feature: --loudness shipped
  surround weighting and true-peak, docs were updated, and its argparse
  help still said "omits" both -- understating is the same drift class as
  overstating. When a capability lands, its --help string is a doc too.
- A second entry point is still an entry point: `python core.py`'s mini-CLI
  ships alongside main.py's, and its unguarded float() plus fall-through
  exit 0 were the same defect classes main.py already fixed -- a sweep
  that ends at the primary front door leaves the side door open.
- A library's warning channel is part of your UI: librosa printed three
  UserWarnings with source snippets on a 100-sample input, because every
  call ran with the default 2048-sample window. If the input is below the
  analysis floor, skip it and report unmeasured -- the alternative is
  stderr noise the user cannot act on dressed as a diagnostic.
- A gate on the wrapper is not a gate on the parts: AudioRestorer's
  constructor checked deps, but repair_audio built DeclippingProcessor/
  HumRemover directly and bypassed it -- on numpy-only installs declip died
  on `interpolate` mid-DSP (clipped input) or wrote input-identical
  "success" (clean input). Check dependency gates at the point the
  dependency is actually consumed, not only at the facade.
- A config flag nothing consumes is a control that lies, and defaults are
  a claim about safety: RestorationConfig defaulted click_removal/
  decrackle on even though the project's own measurements found those
  detectors rewrite click-free noise, and shipped three flags
  (gap_filling/spectral_repair/adaptive_mode) wired to nothing. If the CLI
  refuses to expose a stage because it is unmeasured, the library's
  default pipeline must not run it either.
- "Orphan" modules still ship, so they still have to work:
  spectral_editor is deliberately not wired into the CLI, but it is a
  packaged library API -- and five stacked defects meant none of its
  operations had ever functioned on the default install (the manual STFT
  path serves everyone, because `import librosa.display` pulls in
  matplotlib which [audio] does not install). An allowed orphan is a
  maintenance exemption, not a correctness exemption -- exercise the
  library paths or they rot invisibly.
- A verification step that only re-checks its inputs can never fail on
  its outputs: backup_workflow built a manifest of SOURCE paths, copied
  the files, then "verified" by re-inspecting the sources -- any number
  of corrupt or missing copies still reported success. Verify the thing
  you produced, not the thing you copied.
- An interface adapter is part of the contract: batch_automation's
  builtin task type resolved real allowlisted callables but the executor
  only ever invoked them as `fn(**inputs)`, and the whole allowlist is
  positional-only C functions -- the documented path failed 100% of the
  time while looking supported. Similarly a scheduler that registers a
  job it cannot schedule made "scheduled" mean "never": when a requested
  form is unsupported, refuse before recording success.
- The same datum rendered two ways is a defect in the weaker rendering:
  the CLI printed the detected key through the note table while the
  library's analyze_harmony dict shipped the raw pitch-class integer
  ("0 major"). A value that has a human-facing name should never surface
  as its enum/int elsewhere.
- RIFF pad rules apply to skipped chunks, not just copied ones: the
  sanitizer consumed a chunk's bytes but not its pad when rejecting it,
  desynced the walk, and stripped the data chunk. Any walker that treats
  "keep" and "drop" differently must still honor the format's padding
  on both paths.
- A "lightweight fallback" that silently shrinks its input domain is a
  data-loss bug: the stdlib DFT transformed the first 4096 samples while
  the caller asked about all of them, and the equaliser zeroed the tail.
  Fallbacks must degrade fidelity, not coverage -- and a gain stage that
  re-normalises to full scale is an attenuator that lies.
- A complexity cap is not a size cap: the template evaluator limited AST
  node count yet "x" * 500_000_000 -- three nodes -- allocated 500 MB.
  Any sandbox or safe-evaluator must bound the *materialised* value, and
  the check must precede the allocation, not just the return.
- A safety mechanism is not real until its updater is wired: the circuit
  breaker had a threshold, a window, a reset timer, a status field, and a
  gate in the job loop -- everything except the one call that records a
  failure. Audit the whole feedback loop, not just the read side.
- Durable storage and the read cache are different resources: the audit
  log persisted every event to disk yet the in-memory copy grew without
  bound. Any unbounded in-process structure in a long-running server is
  a leak -- bound it, and bound it where eviction cannot break a live
  contract.
- A capability that cannot be enabled must not fail silently: the batch
  scheduler guarded on a package present in no extra, then returned
  success through a log line. Unavailable means refuse loudly -- a
  warning is not a contract.
- A "stereo" code path that accepts a multichannel array is a data-loss
  bug, not a generalisation: the compressor and limiter wrote only rows
  0-1 and returned a (4, N)-shaped array with two silent channels. Gate
  arity at the entry point -- silence downstream is indistinguishable
  from silence in the mix.
- A scaling flag that cannot be honoured must not exist: --workers N
  spawned processes that cannot share sessions, so the default made the
  API forget logins 3 times out of 4. If a knob is only honest at one
  value, accept only that value and say why.
- A selection-scoped operation that writes whole rows leaks beyond the
  selection: harmonic_enhance_selection multiplied full frequency rows
  when any frame of a row was selected. An operation named for a
  selection must prove its writes stay inside the mask -- check
  coordinates on both axes, not just membership.
- An output encoder must produce a file the project's own readers can
  parse: --convert-bit-depth 32 mapped to soundfile's FLOAT subtype, and
  the artifact was rejected by the dependency-free parser it ships with.
  Verify writer output against the first-party reader, not just the
  library's subtype list.

**Q (2026-09-21, continued):** The README sells `core.BatchProcessor` as
the directory-batch engine and `batch_process_async` as "an asyncio
variant". One class, two loops -- does the async variant keep the
documented contract?
**A:** No, and the drift had already cost real fixes. Three batch engines
exist -- `AudioProcessor.batch_process` (the CLI), the API's
`process_batch_job` loop, and `core.BatchProcessor`/`batch_process_async`
(the library surface the README documents). The async sibling diverged
from its own sync twin: no trailing summary row (the README's stated
shape), no state snapshot, no degradation evaluation, and `skip_errors`/
the wall-clock timeout were accepted kwargs that did nothing. Each
silently-different surface is where drift accumulates (the strict-bounds
gap fixed on another branch was the same class). The async path now
emits the summary row, records state, and evaluates degradation
identically; what concurrency cannot honour is now written down instead
of silently swallowed. Related edge, same audit: `batch --output-dir`
inside the scanned tree feeds last run's outputs back as inputs on every
re-run; the scan happens upfront so the current run is correct, but the
CLI now warns at submission time -- refusal would break the legitimate
"normalize a directory in place with a suffix" use.

**Q (2026-09-21, continued):** `advanced_validation.py` also has a
__main__ self-test. Same question as personal_config -- does asking it
anything (or just running it) leave traces or destroy data?
**A:** Running it wrote `test_manifest.json` into ~/.chameleon/manifests
permanently and wrote `test_validation.wav`/`test_sanitized.wav` into the
CWD -- overwriting a same-named user file before deleting the evidence.
The manifest dir default (Path.home()/".chameleon"/manifests) is the
IntegrityVerifier's documented state location; the demo was leaking into
it. The self-test now runs entirely inside a TemporaryDirectory -- same
coverage (inspect, create+verify manifest, sanitize), zero persistence.
Also audited this cycle and found honest: `midi generate` writes the
requested key/mode/tempo byte-exactly (G natural minor at 90 BPM ->
pitches 67,69,70,72,74,75,77,79 and us-per-quarter 666667); the CLI's
env-tunable 500MB cap and the API's fixed 100MB upload cap are both
enforced and the README already documents the divergence; `analyze
--loudness` reports "below measurement gate" for too-short material
rather than fabricating LUFS.

**Q (2026-09-21, audit 35): Do LOOP and CONDITIONAL workflows honor the
honest-failure rule the DAG fix applied?**
**A:** Two defects of the same class. _execute_loop read
metadata['iterations'] unchecked: 0, -2, and True silently produced {}
(a workflow reporting success having run nothing), and '3' crashed with
TypeError. It now requires a positive int and raises ValueError naming
the bad value. _execute_conditional's 'simple' condition returned True
when its task_id had no result -- a guard on a nonexistent or unreached
task was treated as satisfied. It now returns False unless the task ran
and completed; conditions can only look backward. Verified honest:
IntegrityVerifier verify_manifest catches intact/tampered/missing
correctly (note create_manifest always appends .json -- 'x.json' yields
'x.json.json'), --master validates its preset via argparse choices,
verify_manifest round-trips sha256+size.
