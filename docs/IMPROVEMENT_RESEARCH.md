# Chameleon — Improvement Research / 改善研究バックログ

## 概要 (Summary)

本書は、同種の音声処理ソフトウェア（librosa, soundfile, pedalboard, demucs,
basic-pitch, pyloudnorm 等）と arXiv.org の研究を参照し、Chameleon の改善点を
洗い出したものです。各項目は **実コード上の現状** にひも付け、参照（同種ツール /
標準 / arXiv 論文）と概算コスト（CPU/GPU・モデルサイズ）を併記しています。

This is an evidence-based backlog, **not** a list of implemented features. Each
item names the current behaviour in the code, the comparable tool/standard or
arXiv work that demonstrates a better approach, and a realistic integration/cost
note. Everything heavier than stdlib is proposed as an **optional dependency**,
consistent with Chameleon's graceful-degradation design.

### Verified current state (from the code)
- `normalize` (core.py) is **peak-only** (`gain = target_peak / current_peak`).
  `mastering_chain.py` already has a `LoudnessMeter` (claims ITU-R BS.1770) and
  `target_lufs=-14.0`, but the CLI `normalize` path never uses it.
- `main.py:_resample_audio` falls back to **`np.interp`** (linear, no
  anti-aliasing) when librosa/scipy are absent. `resampy` is already listed in
  `enhanced_requirements.txt` but is **never imported**.
- `codec_support.py` already wraps **soundfile + pydub/ffmpeg** (FLAC/MP3/OGG/
  M4A), but the core `analyze`/`process` pipeline is **WAV-only** — codec support
  is a disconnected bolt-on.
- MIDI: pitch is **autocorrelation (monophonic)**; key is
  **Krumhansl-Schmuckler**; chords are **template matching**. No beat/tempo,
  no source separation.
- "Duplicate detection" is **path-only** (`resolve_unique_paths`); there is no
  audio-content fingerprinting.
- `audio_restoration.py` is **classic DSP only** (declick/decrackle/dehum/declip).
- `enhanced_requirements.txt` lists `tensorflow` (and `torch`) that **nothing
  imports** — dependency bloat.

---

## Tier 1 — High impact, low effort, no heavy ML (do first)

These need only small, pure-Python / well-established optional libs and are
directly verifiable.

1. **LUFS / EBU R128 loudness normalization** *(maps to `core.py` normalize +
   `mastering_chain.py`)*
   Peak normalization ignores perceived loudness. Adopt ITU-R BS.1770-4 /
   EBU R128 (integrated LUFS + true-peak limiting) — the standard used by
   Spotify/YouTube/Apple. Use **pyloudnorm** (MIT) to measure, and add a
   `--lufs -14` CLI option alongside the existing `--normalize`. Wire (and
   validate) the existing `LoudnessMeter` against pyloudnorm, or replace it.
   Cost: negligible (single-pass FFT). Refs: ITU-R BS.1770, EBU R128 spec,
   github.com/csteinmetz1/pyloudnorm.

2. **Unify multi-format I/O through codec_support** *(`core.py`/`main.py` ↔
   `codec_support.py`)*
   `codec_support.py` can already read FLAC/MP3/OGG/M4A but `analyze`/`process`
   only accept WAV. Route core loading through a single backend layer so all
   commands work on non-WAV input. Pattern reference: librosa/**audioread**
   backend negotiation. Cost: refactor only. Refs: python-soundfile docs,
   pydub, beetbox/audioread.

3. **High-quality resampling** *(`main.py:_resample_audio`)*
   Replace the `np.interp` fallback (aliasing) with **soxr** (VHQ, band-limited
   sinc) or **resampy** (already a declared optional dep). Expose a quality
   level. Cost: ~3-5% CPU. Refs: github.com/dofuuz/python-soxr, resampy docs.

4. **Better monophonic pitch via pYIN** *(`midi_analysis.py`)*
   Replace the autocorrelation `_estimate_pitch` with **`librosa.pyin`**
   (probabilistic YIN: Viterbi-decoded F0 + voicing confidence, handles
   vibrato). Cost: ~0.1× RT, CPU. Ref: librosa.pyin docs.

5. **Richer MIDI I/O via pretty_midi** *(`midi_analysis.py`/`music_generator.py`)*
   Replace hand-rolled MIDI writing with **pretty_midi** (velocities, pitch
   bends, time/key signatures; FluidSynth render). Cost: negligible. Ref:
   github.com/craffel/pretty-midi.

6. **Spectral noise reduction** *(`audio_restoration.py`)*
   Add **noisereduce** (spectral gating, stationary & non-stationary, no model
   download) as an optional denoiser alongside the classic DSP. Cost: light,
   CPU. Ref: github.com/timsainb/noisereduce.

7. **Dithering on bit-depth reduction** *(`mastering_chain.py` —
   `dither_enabled` flag exists but is unimplemented)*
   Apply TPDF/shaped-noise dither when reducing bit depth (e.g. 24→16) to avoid
   quantization distortion. Cost: trivial. Ref: standard mastering practice,
   soxr/FFmpeg resampler docs.

8. **Benchmarks + drop dead deps** *(new `benchmarks/`, `enhanced_requirements.txt`)*
   Add objective benchmarks (loudness accuracy vs pyloudnorm, resampling SNR,
   I/O speed vs soundfile/pydub). Remove unused `tensorflow`/`torch` from the
   default optional set. Ref: faroit/python_audio_loading_benchmark.

---

## Tier 2 — Medium effort, optional ML (pip-installable, CPU-capable)

9. **Polyphonic audio-to-MIDI** *(`midi_analysis.py`)*
   The current transcription is monophonic. Integrate Spotify **basic-pitch**
   (instrument-agnostic polyphonic note + pitch-bend transcription; reads
   WAV/MP3/FLAC/OGG; emits MIDI). CPU ~0.5-2× RT, ~model a few hundred MB,
   no TF dependency by default. arXiv: **2202.06183** (Bittner et al., ICASSP
   2022); github.com/spotify/basic-pitch. (Baseline reference:
   Onsets-and-Frames, arXiv 1710.11153.)

10. **Learned key + beat/tempo tracking** *(`midi_analysis.py`)*
    Replace heuristic key detection with a learned CNN (**key-cnn**; arXiv
    **1903.10839 / 1706.02921**). Add beat/downbeat/tempo via **madmom**
    (mature, CPU, arXiv **1605.07008**) or **Beat This!** (SOTA, arXiv
    **2407.21658**). Cost: small models, CPU-feasible.

11. **Audio fingerprinting → real duplicate detection** *(new
    `audio_fingerprinting.py` + `batch_automation.py`)*
    Today's "dedup" is path-only. Add perceptual fingerprinting via
    **Chromaprint/AcoustID** (`pyacoustid`, MIT) — robust to format/bitrate
    changes, <100 ms/track, ~2.5 KB/track. Ref: acoustid.org,
    github.com/beetbox/pyacoustid.

12. **Real-time-capable deep denoiser** *(`audio_restoration.py`)*
    Add **DeepFilterNet2** as an optional full-band 48 kHz denoiser; runs
    real-time on CPU (~0.04 RTF on a desktop core), ~5 MB. arXiv:
    **2205.05474**. Fallback: Facebook Denoiser, arXiv 2006.12847.

---

## Tier 3 — Heavier / GPU-leaning (optional, advanced)

13. **Music source separation** *(new `audio_separation.py` + CLI `separate`)*
    Add **Demucs / Hybrid-Transformer Demucs** (vocals/drums/bass/other, 9.2 dB
    SDR). Also improves key/chord/transcription accuracy as a pre-step. CPU
    feasible for batch, GPU ~1× RT. arXiv: **2211.08553 / 1911.13254**;
    github.com/facebookresearch/demucs. Lighter alt: Open-Unmix.

14. **Multitrack transcription & structure analysis**
    **MT3** multi-instrument transcription (arXiv **2111.03017**, JAX/TF, GPU)
    and **All-In-One** beat+functional structure (intro/verse/chorus; arXiv
    **2307.16425**) for richer `analyze` output.

15. **Unified neural restoration**
    **VoiceFixer** (denoise + dereverb + declip + bandwidth extension /
    super-resolution) for `audio_restoration.py`. GPU-preferred, CPU batch OK.
    arXiv: **2109.13731 / 2204.05841**.

16. **Neural codecs** *(`codec_support.py`)*
    Optional **EnCodec** (arXiv **2210.13438**) / Descript-Audio-Codec for
    low-bitrate neural compression and as a representation layer. ~200 MB, CPU
    ~real-time at 24 kHz. (Niche; lower priority.)

17. **Pro effects backend & real-time hardening** *(`mastering_chain.py`,
    `realtime_effects.py`)*
    Consider an optional **pedalboard** (Spotify, JUCE) backend for EQ/comp/
    limiter/reverb and VST3/AU hosting (much faster than pure-Python DSP).
    Separately, harden the real-time path: keep Python off the audio callback,
    use a lock-free ring buffer and parameter queue (sounddevice callback +
    `queue.SimpleQueue`). Ref: spotify/pedalboard.

---

## Cross-cutting / architecture notes
- **Single I/O abstraction**: introduce one backend-negotiating loader (soundfile
  → pydub/ffmpeg → stdlib WAV) so every command degrades gracefully and supports
  all formats — mirrors librosa/audioread.
- **Consistent optional-dependency pattern**: each ML feature should import
  lazily and report "unavailable" cleanly when its package is missing, matching
  the existing `HAS_NUMPY`/`HAS_WEBSOCKETS` style.
- **Caveat on citations**: the arXiv IDs above for well-established work
  (basic-pitch, Demucs, EnCodec, DeepFilterNet, MT3, Onsets-and-Frames,
  pyloudnorm/BS.1770) are stable; a few very recent (2025-2026) chord/IIR papers
  surfaced during research are promising but should be re-verified before being
  adopted as dependencies.

## Suggested first PRs (smallest valuable slices)
1. `--lufs` loudness normalization via pyloudnorm (Tier 1 #1) — validatable, no
   heavy deps, directly improves a core command.
2. Wire `codec_support` into `analyze`/`process` so non-WAV input works (#2).
3. Swap the `np.interp` resample fallback for soxr/resampy (#3).
