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

Progress: 6 / 10 categories complete.

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
