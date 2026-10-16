# Processing provenance and limits

Checked October 16, 2026. This skill was built for a Rovidx demonstration of an agent operating local audio tools. No audio-service account or upload is required by the helper. This says nothing about the agent host's own connection or billing.

## Tested environment

- Windows; Python 3.13.3.
- FFmpeg 7.0 full build from gyan.dev, already on PATH.
- NumPy 2.2.5, SciPy 1.15.3, SoundFile 0.13.1; click available.
- RNNoise model: [Gregor Richards' conjoined-burgers model](https://github.com/GregorR/rnnoise-models/tree/master/conjoined-burgers-2018-08-28), `cb.rnnn`.
- Model SHA-256: `f1357c4e5be9dee8467bead486dfced2d75b640c26ad0b594fa7f102322371d9`.
- Source project [RNNoise models](https://github.com/GregorR/rnnoise-models) states its model data is not subject to copyright. The model is bundled unmodified.
- NARA-WPE 0.0.11: [official project](https://github.com/fgnt/nara_wpe), downloaded as its public wheel. Unmodified `__init__.py` and `wpe.py` are included in `assets/python/nara_wpe`; the original MIT license is at `assets/NARA-WPE-LICENSE.txt`. No TensorFlow implementation is used.

Other machines may need Python packages installed. Use an appropriate project environment and actual current compatibility checks. Do not run global upgrades or silently replace the user's software.

## Decisions grounded in the tests

- [FFmpeg arnndn](https://ffmpeg.org/ffmpeg-filters.html#arnndn) is neural noise suppression. Its model file is required; it is not supplied automatically by a generic agent prompt.
- In the tested build, staging through a float WAV changed the neural result despite equal decoded sample values. Keep the verified 24-bit input and neural intermediate. Floating intermediates remain useful for WPE and level processing, which can exceed integer headroom before export.
- Neural output lagged input by 480 samples at 48 kHz. A non-integral final 10 ms frame can be rounded up; accept only 0–479 extra samples from this neural path, record the difference, and keep the original exact frame count after alignment. Cross-correlation measures and compensates this delay; it is logged, with a small edge pad. The source remains intact. Preview timing is not proof of alignment for unrelated tools.
- [FFmpeg afftdn](https://ffmpeg.org/ffmpeg-filters.html#afftdn) is the conventional spectral alternative. It added 1,200 samples of delay in the tested build. It was useful on a second recording where the neural setting did not transfer well. The helper logs and compensates the measured delay for either route.
- A dynamic loudness-normalization fallback increased residual noise in a controlled example. That finding supports avoiding an unreviewed loudness rider, not abandoning the requested volume. Speech export now uses measured fixed gain with explicit lookahead peak limiting when required, 4x oversampling, limiter auto-level disabled, and latency compensation enabled. It remeasures the rendered file and requires the selected target within 0.3 LU. Preserve mode retains the old constant-gain-only alternative and reports a target miss separately. Listen for peak distortion and gain recovery around transients; the measured target alone does not establish naturalness. See [FFmpeg alimiter](https://ffmpeg.org/ffmpeg-filters.html#alimiter).
- [Dynamic leveling](https://ffmpeg.org/ffmpeg-filters.html#dynaudnorm) and peak/loudness handling are conventional audio processing, even when an AI agent runs them.
- WPE estimates late-reverberation correction in a 16 kHz analysis signal; the helper adds that correction to the original 48 kHz signal, retaining its high band. It is a conservative trial, not a promise of studio sound or early-reflection removal. Single-microphone results in the controlled demonstration were limited.

## What the evidence can establish

Test actual speech, preserve the sources, log all commands, verify finite unclipped output, and compare timing and length. Controlled examples with known references can support measurements of added-noise/level changes. Label added impairments openly. A reference-similarity measure such as SI-SDR is not a human listening score or proof that all words are intact. A setting that reduces noise in a pause may still damage a word.

Do not put episode-specific samples, private paths, numerical results, or client stories into the reusable skill. Keep those with the corresponding job's report. The helper itself performs no network requests.

Two comparison exports serve separate purposes: actual-volume A/B demonstrates the delivery level; integrated-loudness-matched A/B helps judge noise and voice changes without most of the loudness bias. Matching a full episode does not guarantee equal loudness in every local excerpt after leveling.
