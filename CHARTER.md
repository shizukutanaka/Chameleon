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

**Wiring caveat (be honest about what actually runs):** of the three files above, only
`security_validator.py` (path/size checks) is wired into the default batch/load paths
(`main.py:_filter_safe_files`, `core.py:BatchProcessor`) and `plugin_system.py` into
plugin loading. `advanced_validation.py`'s deeper inspection (`DeepFileInspector`,
`IntegrityVerifier`, `SanitizationEngine`) is currently reachable only via
`personal_config.py`, **not** the default processing path — so do not describe it as an
always-on defense. Integrating it into the default path is an open item (§9) and needs
its own tests before being relied upon.

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

### Open questions (next contributor: decide before building)

- **advanced_validation.py integration**: its deep file inspection / integrity / sanitize
  passes are not wired into the default batch/load path. Should they be (closing the gap
  between the §5 claim and the running code), or should the module be trimmed to match
  what is actually used? Either way, add path-traversal and oversize-file unit tests that
  exercise `SecurityValidator` directly — currently `validation_test.py` re-implements the
  checks by hand rather than calling it.

- **CI non-goal guard**: §8.4 says scope discipline is "watchable by a grep in review or
  CI." Should we wire an actual CI step that greps for `quantum|neural|GPU|enterprise`
  and fails if found? If yes, where does the allowlist live?
- **CLI exit codes**: Unix convention maps error categories to distinct exit codes
  (e.g., file-not-found=2, permission=3). Currently the CLI returns 0 or 1 only. Is a
  richer exit-code table worth the added contract, or does it conflict with the
  "minimal dependency surface" identity?
- **API threat model vs. local tool**: §7 notes the API's enterprise surface may be
  larger than a local-tool threat model justifies. If the API is never going to be a
  hosted service, which RBAC/rate-limiting pieces can be simplified without reducing the
  security that *is* needed?
