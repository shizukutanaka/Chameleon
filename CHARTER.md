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

- **WAV only, by default.** `codec_support.py` reads MP3/FLAC/OGG *only* if soundfile /
  pydub / ffmpeg are installed, and `load_audio` requires numpy. The default install
  (`requirements.txt`) installs none of these, so out of the box the product is WAV-only.
  Advertise this plainly; do not call it "multi-format" without the optional extras.
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

### Open questions (next contributor: decide before building)

- **advanced_validation.py parity in core**: `DeepFileInspector` now runs in
  `main.py:_filter_safe_files` (the CLI batch path), but `core.py:BatchProcessor` —
  reachable via `core.batch_process_async` — still validates only path/size. Wiring the
  same format check there (or extracting one shared filter) would close the remaining
  parity gap; left optional to keep the stdlib core minimal.

- **Broken active CI workflow**: `.github/workflows/ci-cd.yml` is still the old 409-line
  fantasy pipeline (k8s/staging/prod deploys, a missing `deployment_manager.py`,
  `tests/smoke/` / `tests/health/` that do not exist). A working replacement sits at
  `ci/proposed-ci.yml`; adopting it needs a maintainer with `workflows` permission to run
  the copy documented in `ci/README.md` (the automation account that produced this branch
  cannot push workflow changes).
