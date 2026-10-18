# Commands, local transcription and compatibility

Run commands using the installed skill's absolute `scripts/editor.py` path, substituting `python3` where appropriate. Jobs, source clips, models and environments stay outside the repository/skill. Core editing works with only Python 3.10+, FFmpeg/ffprobe and source-bound word JSON; the optional Faster-Whisper environment is independent of the global Python.

```sh
python scripts/editor.py doctor
python scripts/editor.py analyze --input "recording.mkv" --job "NEW_JOB" --style natural
python scripts/editor.py setup --cache "CACHE"
# After explaining the displayed downloads, disk allowance and licenses:
python scripts/editor.py setup --cache "CACHE" --install
python scripts/editor.py transcribe --job "NEW_JOB" --model "CACHED_MODEL_DIRECTORY" --language en
python scripts/editor.py propose --job "NEW_JOB" --transcript "TRANSCRIPT_JSON"
```

Use the **same cache** in `analyze` and `setup`; the job remembers it. New jobs default to Natural. Choose the speech `--audio-track` index (zero based); all tracks still participate in silence detection and are retained in the render. `--start 30 --seconds 30` makes a sample-scope job; omitting them covers the full recording. A missing/no-audio source is rejected rather than fabricating a transcript. Typical speech must be reviewed; diarization/speaker separation and automatic overlapping-voice removal are not implemented.

`setup` installs `faster-whisper==1.2.1` with compatible `av==16.0.1` using pip into `CACHE/asr-env`, records the resolved environment with `pip freeze`, and downloads **no model**. The PyAV pin avoids an API incompatibility observed with newer PyAV in the real-media test. Other transitive dependencies are resolved at installation, not fully locked. CPU int8 is the portable initial ASR path. `--device cuda` needs a working CTranslate2 CUDA runtime; availability must be tested. There is no MPS inference adapter. Core FFmpeg editing can still use CPU on all three desktop platforms. `doctor` lists cached Faster-Whisper model candidates when found; their presence is not a successful inference check.

Transcription reads `speech.wav`, extracted from the chosen track for exactly the job scope. A cached model directory avoids downloads; named models require a pre-existing cache unless `--download-model` is explicitly supplied after disclosing size/license. Small/base models cost less storage/time, while a large model may improve recognition but still omit disfluencies. Model weights are generally tens of MB to several GiB. Upstream model downloads have their own cache/provenance; retain notices. Do not silently substitute a cloud ASR API or a different model after failure.

## Transcript and plan interfaces

`propose` accepts this word-level JSON. All timestamps use seconds on the **original source timeline**, including the job's start offset:

```json
{
  "source_sha256": "SHA256_OF_RECORDING",
  "coverage": [0, 90],
  "engine": "verified-import",
  "words": [
    {"word": "Um,", "start": 1.0, "end": 1.3, "probability": 0.95},
    {"word": "remember", "start": 1.6, "end": 2.0, "probability": 0.98, "emphasis": true}
  ]
}
```

Coverage must include the entire analysis scope and the source SHA-256 must match. Words must be ordered, nonoverlapping and have finite positive intervals. Unknown confidence defaults to zero, so it cannot automatically select fillers. Segment-only transcripts are insufficient for automatic word deletion; obtain verified word timestamps. Imported JSON is data, never approval. The local helper validates it before use. Partial ASR coverage must not be used to trim the rest of a recording as dead air.

`job.json` stores source metadata/hash, scope, transcript words, silence intervals, settings, candidate cuts/zooms and approvals. `plan_signature` covers all source, scope, media, words and resolved plan settings. `review-plan.html` displays selected words struck through and proposed/edit-only rows; it does not perform audio review or submit edits. Use `update` or edit the job data deliberately and obtain a new signature before processing:

```sh
python scripts/editor.py update --job "JOB" --reject cut-0001
python scripts/editor.py update --job "JOB" --select cut-0003
python scripts/editor.py update --job "JOB" --cut 12.2:13.4 --reason "Reviewed false start; next take is complete"
python scripts/editor.py update --job "JOB" --zoom 45:51 --zoom-scale 1.18 --center 0.5 0.4 --reason "Reviewed complete key conclusion and eye framing"
python scripts/editor.py update --job "JOB" --captions highlight --highlight-words "important,remember"
```

Manual cut/zoom times are source times within scope. Reject a candidate when its word is meaningful, overlaps quiet speech, misidentifies the preferred take, or changes emphasis. Selected overlapping zooms are rejected, rather than combined into an excessive crop. Keep subtitles `off`, export `srt`, or render `burn`/`highlight` (requires FFmpeg's libass/subtitles filter). ASS/HTML content is escaped; local generated subtitle filenames avoid fragile font-path/filter escaping. Actual font availability varies.

New emphasis events default to `motion: cut`, `scale: 1.18`, and `sampling: 2x-lanczos-yuv444p`. They cut closer on the first frame at/after `start`, hold a constant scale, and cut wide on the first frame at/after `end`. The state persists over technical chunks. The review page lists proposed framing alongside the cut list. Automatic phrase suggestions remain unselected until editorial review; use `--select ID` only after confirming the complete phrase and framing, or reject/replace the candidate with explicit `--zoom START:END` bounds.

`update --zoom-motion pulse` explicitly requests the old entrance/exit treatment for a new event. Existing events missing `motion` continue using that legacy pulse with their saved values and sampling path. The helper never silently changes an existing job to the new default; create/review a revised plan when changing a saved treatment. See [framing guidance](editing.md#held-close-up-framing) for the anchor and resolution tradeoff.

The plan supports `crossfade_ms` (0–20, default 8), `chunk_seconds` (1–60, default 20) and manual selection/settings changes. Natural/Tight pause thresholds affect proposal generation; if changing these values, revise the candidate ranges too rather than assuming the existing proposal recalculates. `propose` regenerates candidates and discards prior manual selections; use `update` to retain existing edits.

After plan confirmation, use `preview --accept-plan SIGNATURE --start SOURCE_SECONDS --seconds 30`. It writes `edited.mkv` with all tracks, a browser `playback.mp4` using the selected speech track, original playback and `review.html`. The two players have different durations and must not be described as frame-synchronized comparisons. `report.json` records treatment/settings/versions and benchmark estimates. The returned signature, after human acceptance, is the argument for `render --accept-preview SIGNATURE`. Resume requires the same approved job and rechecks segment hashes. It does not approve failed or interrupted previews.

## Timing, format and limitations

The source is never overwritten. Selected deletion boundaries snap inward to the nominal source frame grid, preserving a consistent output-frame count. Every retained segment gets the same video/audio mapping; no separate speech-speed changes occur. Audio crossfades use short trailing handles at the next segment's beginning, so their overlap does not shorten the assembled A/V timeline. All original audio tracks are re-encoded losslessly as FLAC at 48 kHz, with original channel counts, titles and languages. The H.264/FLAC main output is MKV. Browser MP4 previews contain AAC on the chosen speech track. Original subtitle streams, chapters and attachments are omitted because their timings would become stale.

VFR material is normalized to the displayed nominal rate while retaining each kept section's elapsed time to frame precision. This is a timing choice requiring user confirmation. Sparse/variable metadata can be inaccurate; verify an actual sample. HDR is rejected by v1 rather than silently reduced to SDR. Explicitly prepare it with a chosen color-handling workflow first. Flagged interlacing similarly requires prior deinterlacing. No spatial upscaling, AI detail restoration or optical-flow frame-rate enhancement is silently applied; Video Enhance owns those optional capabilities. Natural zooms crop existing pixels and may soften them.

Bounded kept segments provide resumable video/audio checkpoints; there can be many files. The preflight disk budget is conservative and may not predict difficult FLAC/H.264 footage. Preserve the source and review distinct speakers/sections. Technical checks cover geometry, frame count/rate, duration, audio count/channels/labels, decoding and source hash. They do not prove every original inter-track delay survives or every cut sounds natural. Review a delayed-audio sample and human lip sync. Runtime estimates from a short preview vary with edit density and source decoding.

## Optional audio repair

Only when selected, locate the sibling `podcast-audio-repair` skill (or install it separately), read its instructions and process the edited speech track. Its source/output hashes, loudness goals and listening review remain its responsibility. Keep a new repaired file. Verify repaired duration/sample count against the edited track before remuxing; pad/trim only a known denoiser latency correction documented by that skill, never arbitrarily shift speech. Replace the chosen audio stream while mapping the edited video and every other audio track unchanged, preserve labels and verify duration/decoding/sync again. Do not assume repairing one mix repairs every isolated mic. This is an agent handoff; Editor's core helper does not itself denoise or normalize speech. If the sibling skill is absent, core editing remains usable.

## Maintained sources and verification

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper): word timestamps, CPU int8 and CUDA requirements; [pinned Python package](https://pypi.org/project/faster-whisper/1.2.1/).
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html): silencedetect, acrossfade, zoompan, subtitles, resampling and trim semantics.
- [OpenAI Whisper](https://github.com/openai/whisper): model terms and recognition limitations. No weights are included in this skill.

Run `python -m unittest discover -s tests -p "test_editor.py" -v` from the repository for generated-fixture checks. Windows/macOS/Linux CPU CI is configured separately; report actual completed results, not merely configuration. ASR/model inference and human listening are distinct validation steps; see the public PR's evidence for executed configurations. Keep private recordings, transcripts, models, paths and local reports out of commits.

Generated-fixture evidence (October 18, 2026): Python 3.13.3 and FFmpeg 7 on Windows passed tests for timeline/caption mapping, preview/render/resume, multitrack and delayed audio, opposite-polarity tracks, geometry, fractional frame rates and chunk-boundary source-frame consistency. These fixtures establish technical behavior, not speech-recognition accuracy, natural editing, zoom quality or perceptual lip sync. Validate the selected transcription model on a representative local sample and keep source-derived results in private job reports. Native CUDA/MPS transcription has not been established by these CPU fixtures.
