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
trusted-root policy, and produces reproducible, audit-logged results suitable for
locked-down or air-gapped environments.* If a change does not serve that, it is out of
scope.

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
- **Codec gap:** real audio is mostly MP3/FLAC. Either commit to optional-codec support
  as a first-class, documented path, or stay explicitly WAV-only — but stop straddling.
- **CLI vs API:** if the API is not going to be a hosted service, consider trimming its
  enterprise surface to match the local-tool threat model.
