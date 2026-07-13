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
  RBAC/audit/rate-limiting exist but defend a narrow threat model (see §5).

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
  service. Its RBAC / rate-limiting / audit-log exist to defend the §5 threat model
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
hand-rolled re-implementation.

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
`RealtimeAudioProcessor` are pending direct user confirmation (tooling
prevented getting an answer in this pass); until then both are left as-is and
`gui/README.md`'s own "experimental, unwired" disclosure stands as the
honest label.

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
   does not exist on `BatchProcessor` (only the async
   `_execute_operation_async` does) — every call raises `AttributeError`,
   caught and reported as a per-file failure. **Not fixed** — implementing a
   sync `_execute_operation` is real new work, out of scope for a
   DeepFileInspector parity pass, and the method has no callers to justify
   the risk right now. Left as an open item below; `test_core_batch_deep_inspection.py`
   works around it by asserting result *counts* (proving the filtering
   stage works) rather than per-file success.

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
exists. A true runtime sandbox (restricted globals/builtins during
`exec_module`) would close the remaining gap but is a larger architectural
change, not attempted here.

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
  conversion.

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
- **True-peak oversampling was explicitly descoped.** The open question below
  asked for it "ideally"; only integrated (gated) loudness was built.
  `measure_peak`-style true-peak metering remains a future addition.
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

### Open questions (next contributor: decide before building)

- **True-peak (4× oversampled) metering per BS.1770-4 Annex 2**: still not
  implemented anywhere in the codebase (`mastering_chain.measure_peak` is
  honest sample-peak; `bs1770_loudness.py` reports integrated loudness only).
  A polyphase FIR interpolation using the standard's example taps is
  straightforward where NumPy is already a hard dependency
  (`mastering_chain.py`); a pure-Python version for `bs1770_loudness.py`
  would need to stay bounded to the same sample cap `analyze --loudness`
  already uses, since the filter cost scales with input length.
- **`mastering_chain.LoudnessMeter` still isn't standard-conformant**: it is
  now honestly labelled "approximate" (see the 2026-07 honesty pass above),
  but it could be replaced with `bs1770_loudness`'s exact coefficients (via
  `scipy.signal.lfilter`, single-pass — not the `filtfilt` it currently uses
  for its bandpass approximation, since zero-phase filtering would double the
  K-weighting shelf's gain) to make the `process --master` LUFS figures real
  rather than approximate. Not done here to keep this change corrective.

- **Plugin sandbox is AST-only, not a runtime boundary**: `exec_module()`
  gives plugin code full, unrestricted Python builtins once it passes the
  static AST check above. A determined attacker could still reach dangerous
  functionality through patterns the AST walk doesn't enumerate (e.g.
  building attribute-access strings dynamically, walking live object graphs
  via `type(x).__subclasses__()` chains not literally spelled out in source).
  Closing this fully needs a runtime-restricted execution environment
  (custom `__builtins__`/globals for `exec_module`), which is a real
  architectural project, not a follow-up patch.

- **openapi_spec.yaml — orphaned, stale, and structurally broken**: not
  referenced by any code (`api_server.py` generates its own OpenAPI schema
  live), fails to parse as YAML past line 28 (a second top-level document
  with no `---` separator), and repeats claims already removed elsewhere
  (`government-focused`, `SIMD acceleration`). Candidate for deletion,
  matching the pattern already applied to `codec_support.py` and the other
  orphaned modules — needs the same explicit user confirmation before acting.

- **gui/ scaffold — keep, delete, or actually wire up?** Experimental React/
  TypeScript/Electron app, self-labeled unwired in its own README, not built
  by the Dockerfile. Needs an explicit user decision (asked, not yet
  answered): label honestly and leave as-is, delete like other orphaned
  surfaces, or invest in actually wiring the Electron shell to the CLI/API.

- **core.py's RealtimeAudioProcessor — dead code, delete?** A standalone
  `websockets`-based server (core.py:2809-3195) with zero callers from
  `main.py` or `api_server.py`. Matches the exact orphaned-module pattern
  already resolved for 9 other modules this charter tracked; needs the same
  explicit confirmation before deletion.

- **BatchProcessor.process_directory (sync) is unusable**: calls
  `self._execute_operation(...)`, a method that doesn't exist on the class
  (only `_execute_operation_async` does). Zero callers anywhere in the
  codebase — only `process_directory_async` (via `core.batch_process_async`)
  is reachable/used. Either implement a sync `_execute_operation` to match,
  or delete the dead sync method entirely; needs a decision, not a silent fix.

- **Broken active CI workflow**: `.github/workflows/ci-cd.yml` is still the old 409-line
  fantasy pipeline (k8s/staging/prod deploys, a missing `deployment_manager.py`,
  `tests/smoke/` / `tests/health/` that do not exist). A working replacement sits at
  `ci/proposed-ci.yml`; adopting it needs a maintainer with `workflows` permission to run
  the copy documented in `ci/README.md` (the automation account that produced this branch
  cannot push workflow changes).
