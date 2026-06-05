# Chameleon — Category-by-Category Research (arXiv + GitHub)

Goal: enumerate **10 product categories** and, for each, gather ~10 related
sources from arXiv.org and GitHub, then extract concrete improvement points
mapped to Chameleon's modules. This complements `IMPROVEMENT_RESEARCH.md`
(Part 1/2) with a systematic, source-by-source survey.

Sources are cited as GitHub repos or arXiv ids. Citations are verified where
practical; bleeding-edge (2025–2026) ids should be re-checked before adopting.

## The 10 categories
1. Audio I/O & multi-format codec support
2. Loudness normalization & mastering (dynamics)
3. Resampling & bit-depth / dither conversion
4. Noise reduction & audio restoration
5. Real-time / streaming / low-latency effects
6. Spectral analysis & editing
7. Audio-to-MIDI transcription (pitch / polyphonic)
8. Music IR (key / chord / beat / tempo / structure) & symbolic generation
9. Music source separation (stems)
10. Security, parser robustness & plugin sandboxing

Progress: 2 / 10 categories complete.

---
<!-- Category sections are appended below as each iteration completes. -->

## 1. Audio I/O & multi-format codec support

Current state: WAV-only core (`struct` parser, 500 MB cap); `codec_support.py`
wraps soundfile+pydub/ffmpeg but is not wired into `analyze`/`process`.

Sources (GitHub / arXiv):
1. python-soundfile — github.com/bastibe/python-soundfile — libsndfile wrapper,
   block/streaming I/O, 16+ formats → replace struct parsing for non-PCM.
2. libsndfile — github.com/libsndfile/libsndfile — codec engine behind soundfile.
3. audioread — github.com/beetbox/audioread — backend negotiation
   (GStreamer/FFmpeg/MAD/stdlib) → robust auto-detect fallback.
4. PyAV — github.com/PyAV-Org/PyAV — libav* bindings → chunked/streaming decode
   without pydub subprocess.
5. miniaudio / pyminiaudio — github.com/mackron/miniaudio,
   github.com/irmen/pyminiaudio — single-file lightweight fallback decoder.
6. librosa — github.com/librosa/librosa — `librosa.load` unified format I/O ref.
7. EnCodec — arXiv 2210.13438 + github.com/facebookresearch/encodec — optional
   neural low-bitrate export.
8. WaveNet — arXiv 1609.03499 — foundational raw-audio modeling (context only).
9. RF64 / MBWF (EBU TECH 3306 / ITU-R BS.2088) — >4 GB / broadcast WAV → extend
   parser beyond 4 GB limit.
10. stdlib `mimetypes` + `filetype` (PyPI) — magic-number content detection →
    catch misnamed files instead of trusting extensions.

Top improvement points:
- Wire **audioread**-style backend negotiation into `codec_support.py` and route
  core `analyze`/`process` through it so all commands accept non-WAV input.
- Add **streaming/chunked decode** (PyAV or libsndfile block API) for large files
  instead of struct-parsing whole-file loads.
- Add **RF64** support + **magic-byte** format detection (`filetype`/python-magic).

## 2. Loudness normalization & mastering (dynamics)

Current state: `normalize` is naive peak gain; `mastering_chain.py` has a custom
`LoudnessMeter` (claims BS.1770) + `target_lufs=-14` and EQ/comp/limiter, unused
by the CLI normalize path.

Sources (standards / GitHub / arXiv):
1. ITU-R BS.1770-5 — itu.int/rec/R-REC-BS.1770 — K-weighting, dual gating,
   true-peak (4× oversampling).
2. EBU R128 (+ Tech 3341/3342) — tech.ebu.ch/publications/r128 — momentary/
   short-term/integrated, LRA, -1 dBTP.
3. pyloudnorm — github.com/csteinmetz1/pyloudnorm — validated BS.1770-4 meter →
   use instead of the custom LoudnessMeter.
4. FFmpeg `loudnorm` — two-pass LUFS+TP+LRA pipeline → model the analyze→apply flow.
5. Matchering 2.0 — github.com/sergree/matchering — reference-matching mastering
   (spectral + loudness + stereo) → "master like this file" mode.
6. DeepAFx — github.com/adobe-research/DeepAFx (ICASSP 2021) — differentiable
   effects / learned auto-mastering direction.
7. ReplayGain 2.0 spec — hydrogenaudio — per-track gain + metadata tags.
8. Streaming targets (Spotify -14, Apple -16, YouTube -14, Deezer -15) → platform
   presets.
9. True-peak / inter-sample-peak limiting (4× oversampling, lookahead) →
   upgrade the limiter to true-peak compliant.
10. CCRMA DSP notes (compressor soft-knee, attack/release, TPDF vs shaped dither)
    → improve compressor knee + shaped dithering.

Top improvement points:
- **LUFS normalization** in core `normalize` (two-pass: measure integrated LUFS +
  true-peak, then loudness-matched gain + limiting); `--target-lufs` with
  platform presets. Prefer **pyloudnorm** over the custom meter.
- **True-peak limiting** (4× oversampling, -1 dBTP) in `mastering_chain.py`.
- Optional **reference-matching** mastering mode (Matchering-style) and
  ReplayGain-2.0 metadata tagging.
