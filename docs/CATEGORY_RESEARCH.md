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

Progress: 10 / 10 categories complete.

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

## 3. Resampling & bit-depth / dither conversion

Current state: `main.py:_resample_audio` = librosa → scipy.resample_poly →
`np.interp` (aliasing); `resampy` declared but unused; no dithering on bit-depth
reduction.

Sources (GitHub / arXiv / refs):
1. python-soxr — github.com/dofuuz/python-soxr — fast band-limited sinc (VHQ).
2. resampy — github.com/bmcfee/resampy — Kaiser polyphase (kaiser_best -120 dB).
3. libsamplerate / Secret Rabbit Code — github.com/libsndfile/libsamplerate —
   SRC_SINC quality modes.
4. r8brain-free-src — github.com/avaneev/r8brain-free-src — pro non-integer ratios.
5. Audio super-resolution / bandwidth-extension survey — arXiv 2605.16681
   (re-verify id) — ML upsampling alternative.
6. JOS "Digital Audio Resampling" (CCRMA) — bandlimited sinc / antialiasing theory.
7. Lipshitz & Vanderkooy "Dither in Digital Audio" (AES) — TPDF ±1 LSB.
8. SoX (rate/dither, MASH noise shaping) — reference dither implementation.
9. foobar2000 / mda dither DSP — production TPDF + amplitude scaling.
10. scipy.signal.resample_poly vs resample — polyphase vs FFT, cutoff control.

Top improvement points:
- Replace the `np.interp` fallback with **soxr/resampy** (resampy is already a
  declared optional dep) and expose a quality level.
- Implement **TPDF (+ optional noise-shaped) dithering** on bit-depth reduction
  in `mastering_chain.py`/`audio_utils.py` (the `dither` flag is currently unused).
- Expose an **antialiasing cutoff** parameter for resampling quality trade-offs.

## 4. Noise reduction & audio restoration

Current state: `audio_restoration.py` is classic DSP only (click/crackle/hum,
declip, gap repair); no spectral-gating lib, no ML.

Sources (GitHub / arXiv):
1. noisereduce — github.com/timsainb/noisereduce — spectral gating
   (stationary/non-stationary), CPU, no model download.
2. RNNoise — arXiv 1709.08243 + github.com/xiph/rnnoise — hybrid DSP+RNN, real-time.
3. DeepFilterNet2 — arXiv 2205.05474 — full-band 48 kHz, RTF ~0.04 on CPU.
4. Facebook Denoiser ("waveform-domain") — arXiv 2006.12847 +
   github.com/facebookresearch/denoiser — causal, CPU RTF <1.
5. FullSubNet — arXiv 2010.15508 — full+sub-band fusion.
6. FullSubNet+ — arXiv 2203.12188 — complex spectrogram + channel attention.
7. VoiceFixer — arXiv 2109.13731 + github.com/haoheliu/voicefixer — unified
   denoise/declip/dereverb/bandwidth-extension.
8. A-SPADE/S-SPADE sparse declipping — arXiv 1506.01830 — better than current declip.
9. nara_wpe — github.com/fgnt/nara_wpe — WPE dereverberation (offline+online).
10. Diffusion restoration (CQT-Diff arXiv 2210.15228) — high-quality offline
    declip/bandwidth-extension (GPU).

Top improvement points:
- Add **noisereduce** spectral gating as an optional, CPU-only denoiser alongside
  the classic DSP.
- Add an optional **DeepFilterNet2** real-time denoiser (full-band, low CPU).
- Add **dereverberation (WPE)** and improve declipping (A-SPADE); optionally a
  unified **VoiceFixer** restoration path for severely degraded audio.

## 5. Real-time / streaming / low-latency effects

Current state: `realtime_effects.py` = PyAudio + threads + `queue.Queue`,
block-based `process()`; no documented GIL-safety / lock-free design.

Sources (GitHub / arXiv / refs):
1. Spotify pedalboard — github.com/spotify/pedalboard — JUCE backend, releases
   GIL during DSP, VST3/AU, AudioStream.
2. python-sounddevice — PortAudio callback model; callback must not block/alloc.
3. elijahr/ringbuf — github.com/elijahr/ringbuf — lock-free SPSC ring buffer.
4. Timur Doumler "Using locks in real-time audio safely" — RCU, priority inversion.
5. Cython `nogil` — release GIL in per-sample DSP loops.
6. torchaudio.io StreamReader/StreamWriter — streaming I/O + buffer backoff.
7. PortAudio pa_ringbuffer — reference SPSC ring buffer.
8. WebRTC audio processing (AEC/AGC/NS, 10 ms blocks) — latency baseline.
9. bastibe/simple-cython-limiter — worked Cython+nogil real-time limiter example.
10. Sub-millisecond real-time SE (minimum-phase FIR) — arXiv 2409.18239
    (re-verify) — sample-by-sample low-latency.

Top improvement points:
- Keep Python off the audio callback: move parameter updates to a **lock-free
  SPSC ring buffer** + command queue (RCU pattern); document the callback budget.
- Move hot per-sample loops (delay/reverb/compressor) into **Cython `nogil`** (or
  adopt a pedalboard backend) for true parallelism and lower latency.
- Adopt **sounddevice/StreamReader** streaming patterns and surface xrun handling;
  wire streaming into `api_server.py`.

## 6. Spectral analysis & editing

Current state: `spectral_editor.py`/`spectral_utils.py` STFT-based;
`advanced_audio_features.py` features.

Sources (GitHub / arXiv):
1. nnAudio — github.com/KinWaiCheuk/nnAudio — GPU STFT/CQT/Mel, trainable kernels.
2. "Beyond Griffin-Lim" fast phase retrieval — arXiv 2205.05496 — <10-iter phase.
3. scipy ShortTimeFFT — NOLA vs COLA invertibility; validate windows.
4. Phase-aware HPSS — arXiv 1807.11298 — magnitude+phase masking.
5. pyrubberband — github.com/bmcfee/pyrubberband — phase-vocoder time/pitch.
6. TorchSpectralGating — GPU spectral gating (stationary/non-stationary).
7. torchaudio.transforms — differentiable Spectrogram/GriffinLim/masking.
8. Mel vs Bark critical bands — arXiv 1206.1450 — perceptual filterbanks.
9. Reassigned spectrogram / instantaneous freq — github.com/bzamecnik/tfr —
   sharper time-frequency localization.
10. librosa core (STFT/CQT/spectral features) — reference to cross-validate.

Top improvement points:
- Guarantee **invertible STFT** (validate COLA/NOLA; correct overlap-add) and add
  a **fast Griffin-Lim** phase reconstruction for magnitude-only edits.
- Add **HPSS** and perceptually-motivated (Bark critical-band) spectral
  gating/masking for cleaner spectral repair.
- Offer an optional **GPU STFT/CQT** backend (nnAudio/torchaudio) and
  phase-vocoder **time-stretch/pitch-shift** (pyrubberband).

## 7. Audio-to-MIDI transcription (pitch / polyphonic)

Current state: `midi_analysis.py` = monophonic autocorrelation pitch + custom
MIDI writing.

Sources (GitHub / arXiv):
1. Spotify basic-pitch — arXiv 2203.09893 + github.com/spotify/basic-pitch —
   lightweight polyphonic + pitch-bend, CPU.
2. Onsets and Frames — arXiv 1710.11153 — split onset vs frame stacks for timing.
3. MT3 — arXiv 2111.03017 — multi-instrument transcription (GPU).
4. CREPE — arXiv 1802.06182 + github.com/marl/crepe — robust monophonic pitch CNN.
5. librosa.pyin — probabilistic YIN with voicing confidence (drop-in for
   autocorrelation).
6. pretty_midi — github.com/craffel/pretty-midi — robust MIDI I/O (velocity,
   bends, tempo).
7. mido — github.com/mido/mido — MIDI messages + live port streaming.
8. MAESTRO — arXiv 1810.12247 — aligned audio/MIDI dataset (train/eval).
9. MELODIA — UPF MTG — predominant-melody extraction for polyphonic mixes.
10. Drum transcription (e.g. Inverse Drum Machine, arXiv 2505.03337, re-verify) —
    multi-voice drums.

Top improvement points:
- Replace monophonic autocorrelation with **basic-pitch** (polyphonic) and/or
  **CREPE**/`librosa.pyin` (confident monophonic).
- Adopt **onset/frame separation** for better note timing.
- Use **pretty_midi**/**mido** for standard MIDI I/O + optional live streaming.

## 8. Music IR (key/chord/beat/tempo/structure) & symbolic generation

Current state: Krumhansl-Schmuckler key + chord templates; no beat/tempo/
structure; basic `music_generator.py`.

Sources (GitHub / arXiv):
1. Directional-CNN key/tempo — arXiv 1903.10839 — learned key/tempo.
2. madmom — arXiv 1605.07008 + github.com/CPJKU/madmom — beat/downbeat/tempo, CPU.
3. Beat This! — arXiv 2407.21658 + github.com/CPJKU/beat_this — SOTA beat tracking.
4. All-In-One — arXiv 2307.16425 + github.com/mir-aidj/all-in-one — beat+structure.
5. Essentia — essentia.upf.edu + github.com/MTG/essentia — 600+ descriptors,
   neural key/genre.
6. music21 — github.com/cuthbertLab/music21 — chord/scale/Roman-numeral analysis.
7. MusPy — arXiv 2008.01951 + github.com/salu133445/muspy — symbolic I/O + eval.
8. Music Transformer — arXiv 1809.04281 — long-term coherent generation.
9. MuseGAN — arXiv 1709.06298 + github.com/salu133445/musegan — multi-track gen.
10. librosa — chroma_cqt / beat_track baselines + cross-validation.

Top improvement points:
- Add **beat/downbeat/tempo** (madmom or Beat This!) and **structure
  segmentation** (All-In-One) — currently absent.
- Upgrade key to **learned CNN** and chords to **music21/Essentia** functional
  analysis instead of templates.
- Strengthen `music_generator.py` with **music21** theory + (optionally) a
  Transformer/MuseGAN backend, evaluated via **MusPy**.

## 9. Music source separation (stems)

Current state: none. (Improves transcription/key/chord accuracy as preprocessing.)

Sources (GitHub / arXiv):
1. Hybrid Transformer Demucs — arXiv 2211.08553 + github.com/facebookresearch/demucs
   — SOTA-ish 4-stem, MIT.
2. Open-Unmix — github.com/sigsep/open-unmix-pytorch — lightweight LSTM, CPU.
3. Spleeter — github.com/deezer/spleeter — fast 2/4/5-stem, TF.
4. Asteroid — github.com/asteroid-team/asteroid — modular separation toolkit.
5. Band-Split RNN — arXiv 2209.15174 — strong frequency-domain model.
6. Conv-TasNet — arXiv 1809.07454 — low-latency time-domain.
7. Ultimate Vocal Remover — github.com/Anjok07/ultimatevocalremovergui —
   production vocal isolation (MDX/Demucs).
8. MUSDB18 + museval — github.com/sigsep — benchmark + SDR/SIR/SAR metrics.
9. BS-RoFormer — arXiv 2309.02612 — SDX23 winner, top SDR (heavier).
10. Mel-Band RoFormer — arXiv 2310.01809 — arbitrary stem counts.

Top improvement points:
- Add an optional **`audio_separation.py`** with a pluggable backend (Demucs
  default; Open-Unmix/Spleeter lightweight) + GPU/CPU fallback; CLI `separate`.
- Use stems as **preprocessing** to boost MIDI/key/chord accuracy on mixes.
- Benchmark with **MUSDB18/museval**; enable karaoke/backing-track export.

## 10. Security, parser robustness & plugin sandboxing

Current state: hand-rolled `struct` WAV parser without chunk-vs-file bounds
checks (verified); in-process AST-allowlist plugin sandbox; FastAPI uploads.

Sources (CVE / GitHub / arXiv):
1. CVE-2021-3246 (libsndfile WAV heap overflow) — nvd.nist.gov — bound chunk sizes.
2. CVE-2014-9496 (libsndfile OOB read) — loop-bounds before each read.
3. CVE-2017-8363 (libsndfile integer-overflow over-read) — safe size arithmetic.
4. RestrictedPython advisory GHSA-wqc8-x2pr-7jqh — AST sandboxes are escapable.
5. atheris — github.com/google/atheris — coverage-guided fuzzing of the parser.
6. nsjail — github.com/google/nsjail — namespaces+seccomp real plugin isolation.
7. python-magic — github.com/ahupp/python-magic — magic-byte upload validation.
8. pip-audit / safety — PyPI — supply-chain dependency scanning in CI.
9. FastAPI secure-upload patterns — size limits, uuid filenames, temp dirs, async.
10. ML-audio security research — arXiv 2410.16341 (re-verify) — validate computed
    features (NaN/Inf, ranges).

Top improvement points:
- **Harden the WAV parser**: validate `offset + chunk_size <= file_size`,
  overflow-safe arithmetic, bounded reads, format whitelist (core.py/audio_utils.py).
- **Don't trust the AST sandbox** as a boundary: document it and add an optional
  **subprocess + seccomp / nsjail** strict isolation mode (plugin_system.py).
- **Validate uploads** by magic bytes + size, random filenames, async jobs in
  `api_server.py`; add **pip-audit** + **atheris fuzzing** to CI.

---

## Synthesis — highest-leverage improvements across categories

Ranked by value ÷ effort, grounded in verified current behaviour:

1. **LUFS/EBU R128 loudness normalization** (cat 2) — the core `normalize` is
   non-compliant peak gain; pyloudnorm is cheap and validatable.
2. **Harden + fuzz the hand-rolled WAV parser** (cat 10) — real CVE class;
   bounded reads + atheris/Hypothesis.
3. **Unify multi-format I/O** through `codec_support` (cat 1) — make all commands
   accept FLAC/MP3/OGG, not just WAV.
4. **High-quality resampling + dithering** (cat 3) — replace `np.interp`, add TPDF.
5. **Polyphonic audio-to-MIDI** via basic-pitch + **beat/tempo** via madmom
   (cats 7–8) — biggest functional upgrade to the music features.
6. **Optional ML denoiser** (DeepFilterNet2/noisereduce) and **source
   separation** (Demucs) as optional deps (cats 4, 9).
7. **Real-time hardening** (lock-free + Cython nogil) and **objective quality
   metrics** for regression-testing processing (cats 5, plus IMPROVEMENT_RESEARCH P6).

All ML items are proposed as **optional dependencies** with graceful
degradation, matching the project's design. arXiv ids for established work were
verified; 2025–2026 ids marked "re-verify" should be confirmed before pinning.
