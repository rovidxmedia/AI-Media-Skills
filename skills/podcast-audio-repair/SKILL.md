---
name: podcast-audio-repair
description: Repair recorded podcast speech locally, correct low or uneven levels, and deliver measured audio with listening comparisons. Use for noise reduction, uneven speech levels, or a cautious room-echo trial.
---

# Podcast Audio Repair

Use local processing to produce a reviewable speech repair. Keep the user's desired voice, timing, channels, and editorial content. Completion requires real output files and measurements; a success message does not establish good sound.

## Choose a small, appropriate treatment

Identify the input file/audio stream and a new output directory. Inspect the recording and the user's description before choosing operations. Start with about 30 seconds and include the troublesome passage. When the complaint is low volume, make loudness the primary acceptance criterion; denoising alone is not a volume repair. Noise suppression can make little audible difference on an already quiet recording. Avoid applying every effect by default.

- Noise: the bundled RNNoise model with FFmpeg `arnndn` is the tested neural route. Begin at `--noise-mix 0.9`; reduce the amount if words or vocal character suffer. For stationary noise that the model handles poorly, trial `--denoise spectral`; inspect and tune `--noise-floor` and `--noise-reduction`. This is conventional spectral processing, not a second AI model. Compare the actual outputs rather than assuming the neural route is best.
- Uneven levels: `--level` uses conventional dynamic leveling. For independently recorded speakers, inspect and adjust their tracks separately before any final mix; this helper does not isolate overlapping voices.
- Room echo: `--dereverb` uses conventional NARA-WPE and is experimental, especially with one microphone. Show the real result and its limits. Never substitute noise removal and call it echo removal.

Use the [helper](scripts/repair_audio.py) for the tested path. Run `--help` for options. An illustrative call is:

```text
python <skill-directory>/scripts/repair_audio.py <input-file> <new-output-directory> --denoise neural --seconds 30
```

Use `--level` or `--dereverb` only when appropriate. `--start` selects the passage; `--audio-stream` selects an audio stream by its zero-based position. Full-recording execution requires `--full`; use it when the user requests full processing or accepts a sample. Do not treat the default sample export as the complete episode.

## Preserve and verify

The helper writes separate originals, intermediates, repaired audio, constant-gain matched comparisons, and a JSON report. It refuses an existing run directory and records source hashes. It does not delete media, upload recordings, sign into services, synthesize speech, or remove editorial content.

Review the first/last spoken sounds after denoiser and limiter latency compensation. Neural processing may round a partial final frame upward by fewer than 480 samples; the helper records this bounded padding and retains exactly the original frame count. The tested FFmpeg build adds 10 ms for the neural route and 25 ms for the spectral route; the helper measures the delay and fails if it cannot establish it confidently. The input and denoised intermediate use 24-bit PCM because float staging materially changed the neural result in observed testing.

The default `--loudness-mode speech` targets the selected integrated loudness (default -16 LUFS for this stereo workflow) with constant gain and, when peaks require it, explicit oversampled lookahead peak limiting. The helper verifies the result within 0.3 LU and checks true peaks; a completed file alone does not meet the loudness goal. Report the limiting used and review naturalness. This uses fixed gain rather than a loudness rider that increases gain in pauses.

Use `--loudness-mode preserve` when the user wants the original dynamics retained. It applies only constant gain constrained by peak headroom and may remain quiet. Label a missed target clearly as a quieter alternative; do not present it as a completed low-volume repair. A previously observed noise increase from dynamic loudness normalization does not justify silently accepting a substantially missed loudness target.

Deliver both `comparison-actual-volume.mp3` (original and export at their actual levels) and `comparison.mp3` (constant-gain matched for noise and vocal quality). Label their order and purpose; a matched preview deliberately hides most of the volume improvement. Listen to both or have the user review them when audio perception is unavailable. Check words, quiet speech, breaths, overlap, pauses, and naturalness. Provide a specific adjustment if needed. Report technical success and listening approval separately. Do not invent a listening verdict, intelligibility score, or before/after result.

Before calling this reusable on new material, exercise the saved procedure on a different clip. Preserve failed attempts as evidence while producing a clearly identified final candidate. No universal preset or guarantee follows from a successful sample.

## Environment and delivery

Requires FFmpeg/ffprobe, Python, NumPy, SciPy, SoundFile, and click. The small neural model and an MIT-licensed NARA-WPE module subset are bundled. Check actual tool availability; explain necessary setup rather than invoking a hosted substitute. See [provenance and observed limits](references/processing.md) for versions, hashes, sources, and the reasons for the verified processing choices.

Return the comparison and repaired file, source-preservation status, processing/settings report, observed improvement or failure, and any unresolved listening check. Keep unrelated publishing, transcript editing, voice cloning, and composition work outside this repair task.
