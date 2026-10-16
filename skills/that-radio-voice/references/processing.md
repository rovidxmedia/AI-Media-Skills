# Processing and dependencies

Conventional local DSP, directed by an agent. No hosted audio service, voice cloning, or synthesis is used. Source media is preserved and each output directory must be new.

## Shared utility owner

Install `podcast-audio-repair` alongside `that-radio-voice`. Its current `scripts/repair_audio.py` must expose `measure`, `export_loudness`, `comparisons`, `ffmpeg`, `run`, and `sha256`. Reuse these so mastering, comparison generation, source hashing, and target verification stay in one maintained home. Each run records the dependency helper's SHA-256. `--repair-helper` supports another layout without a personal machine path in this skill.

Use the repair skill's Python dependencies: NumPy, SciPy, SoundFile, and click for its optional WPE path. FFmpeg/ffprobe must be on PATH. The radio chain needs `volume`, `highpass`, `agate`, `equalizer`, `acompressor`, `aexciter`, `deesser`, `alimiter`, `aresample`, `loudnorm`, and MP3 encoding through `libmp3lame`. Required filters are checked before processing.

## Chain rationale

Preset values live in the helper. Stage input to -20 LUFS with constant gain so thresholds behave consistently. High-pass at 65 Hz to reduce rumble. Float intermediates retain headroom through tonal boosts.

The linked RMS gate uses a soft knee, cautious -50 dBFS threshold after input staging, and at most 12 dB attenuation. It is a downward expander with a bounded noise floor, not a voice detector. Breaths and tails may need a lower threshold or disabled gate.

Broad EQ adds body near 120 Hz, reduces boxiness near 320 Hz, and adds presence near 3 kHz. It changes timbre without altering fundamental pitch. Soft-knee linked compression shapes density before makeup mastering. The master uses fixed gain rather than a loudness rider that rises during pauses.

The exciter generates upper harmonics above 3.5 kHz with a 12 kHz upper limit. Light de-essing follows. Excitement can exaggerate hiss and sibilance; judge the matched comparison. This is distinct from simply boosting treble.

Shared mastering targets -14 LUFS by default, a configurable creative target rather than a universal radio transmission standard. Oversampled lookahead limiting uses latency compensation and disables auto-level. Remeasure the rendered file. Already mastered input may sound overprocessed; reduce compression or excitement or use the lighter preset.

Stage envelope statistics describe amplitude, not intelligibility or audible quality. Review first/last sounds, gate behavior, sibilance, and the MP3 even when duration and clipping checks pass.

## Primary references

- [FFmpeg agate](https://ffmpeg.org/ffmpeg-filters.html#agate): attenuation range, soft knee, detector, timing, and linking.
- [FFmpeg acompressor](https://ffmpeg.org/ffmpeg-filters.html#acompressor): threshold, ratio, attack, release, knee, and linking.
- [FFmpeg aexciter](https://ffmpeg.org/ffmpeg-filters.html#aexciter): harmonic generation and frequency limits.
- [FFmpeg deesser](https://ffmpeg.org/ffmpeg-filters.html#deesser): intensity and treble ducking.
- [FFmpeg alimiter](https://ffmpeg.org/ffmpeg-filters.html#alimiter): oversampling, lookahead, auto-level, and latency compensation.

Initial implementation exercised on Windows with Python 3.13.3, FFmpeg 7.0, NumPy 2.2.5, SciPy 1.15.3, and SoundFile 0.13.1. Other versions require their own sample check. Job-specific results belong in job reports. Execution and measurements cannot guarantee pleasing sound.
