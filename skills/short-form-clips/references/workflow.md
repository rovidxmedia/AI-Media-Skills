# Commands and source-bound interfaces

Use Python 3.10+ with the installed helper's absolute path; examples abbreviate it. FFmpeg/ffprobe must be on PATH. Burned captions need a libass-enabled subtitles filter. Explain any selected tool download/license before setup. The helper has no network or pip operations.

For Homebrew on macOS, use `brew install ffmpeg-full` and prepend `$(brew --prefix ffmpeg-full)/bin` to PATH for this session. The regular formula may lack libass; see [compatibility](compatibility.md). Do not replace a working system installation just to rename it.

```sh
python scripts/shorts.py doctor
python scripts/shorts.py analyze --input "finished episode.mp4" --job "NEW_JOB" --audio-track 0
python scripts/shorts.py plan --job "NEW_JOB" --transcript "words.json" --candidates "candidates.json"
# After selection/framing approval or explicit delegation:
python scripts/shorts.py preview --job "NEW_JOB" --accept-plan "CURRENT_PLAN_SIGNATURE"
python scripts/shorts.py resume --job "NEW_JOB"
# After acceptance of complete short drafts:
python scripts/shorts.py render --job "NEW_JOB" --accept-preview "CURRENT_PREVIEW_SIGNATURE"
```

## Word timestamps

Accept Editor-compatible word JSON:

```json
{
  "source_sha256": "SHA256_OF_FINISHED_INPUT",
  "coverage": [0, 90],
  "words": [
    {"word": "Try", "start": 10.2, "end": 10.4},
    {"word": "this.", "start": 10.4, "end": 10.7}
  ]
}
```

Coverage must contain each complete proposed interval. Words must be ordered, nonoverlapping, finite and inside coverage. Structure checks cannot prove recognition accuracy. Text-only/segment-only imports are insufficient for timed captions.

Without timings, optionally locate the sibling `editor` skill and read its `references/workflow.md`, which owns ASR setup/cache/model/license guidance. Use its `analyze` on this **same finished input** with the same selected speech track, then `transcribe` with a cached model. No Editor render/cut proposal is needed. Pass the returned source-bound word JSON here. If Editor is absent, install it separately or import compatible local timings. Do not silently download models or substitute cloud ASR. Editor is not required for supplied timings.

## Agent-authored candidates

The agent reviews meaning and frames; the helper does not implement semantic scoring. Example against the 90-second source above:

```json
{
  "source_sha256": "SHA256_OF_FINISHED_INPUT",
  "clips": [{
    "id": "clip-01", "start": 10, "end": 40,
    "title": "An honest title from the passage",
    "hook": "Try this.",
    "hook_evidence": {"start": 10.2, "end": 10.7, "text": "Try this."},
    "why": "A practical demonstration for the intended audience.",
    "payoff": "The actual conclusion; retain evidence in private review notes.",
    "scores": {"hook": 4, "standalone": 4, "payoff": 5, "audience": 4},
    "selected": true,
    "framing": {"mode": "fit", "center_x": 0.5, "center_y": 0.5},
    "captions": "burn", "description": "Source-grounded short description.",
    "tags": ["relevant topic"], "cover_at": 20
  }]
}
```

IDs are unique lowercase filename-safe names; bounds and cover time use source seconds. Each clip is at most 180 seconds. Hook evidence must exactly quote timed words in the opening 3.5 seconds. `selected` defaults false; select at least one. Crop/fit centers are 0–1. For host-plus-graphics footage, prefer [stacked framing](stacked-framing.md), which replaces the `framing` object with reviewed crops and shot boundaries. Caption modes: `burn` (default), `srt`, `off`. Clean MP4 and SRT are always retained; off uses the clean version without subtitle application. Tags and scores are validated, not automatically invented.

Default dimensions 1080×1920; `analyze --width N --height N` accepts smaller even 9:16 dimensions for explicit preferences/tests. Fractional nominal rates are retained as CFR, without optical flow. VFR normalization, source audio delays and unusual codecs need sample review.

## Outputs, approval and recovery

`review-plan.html` lists candidates. `preview` generates **complete short drafts**, not a full-episode render. Each selected folder has `clean.mp4`, optional `captioned.mp4`, `captions.srt`, `captions.ass`, `cover.jpg`, start/middle/end check images, `metadata.json`, `tiktok.txt`, and `youtube-shorts.txt`. H.264 CRF18/AAC192 kb/s/48 kHz retains selected channel count. Prepare a mono/stereo mix deliberately. Other tracks/subtitles/chapters/attachments are omitted from excerpts and recorded as such, never deleted from source.

The receipt binds plan, videos, captions, images and copy by hashes. `render` accepts the exact preview signature after user review or explicit prior delegation and writes `delivery.json`, finalizing reviewed files in place. A signature alone is not human consent. Jobs freeze when previews begin; changed crop/bounds/transcript require a new job. `resume` rejects changed completed outputs, checks source, and rebuilds interrupted temporary stages. After a hard kill, verify the PID stopped before removing a stale `.running` lock. Do not remove active locks.

Every delivered MP4 is decoded and checked for geometry/rate/channel count and duration within 0.15 seconds or two frames, whichever is greater. Stacked mode also checks exact picture frame count and unchanged complete audio packets/start/duration against its independent AAC checkpoint. Its video-only `picture.mp4` and `audio.m4a` stages are resumable and hash-bound; retain them until final delivery verification. Source hash is checked on entry/completion. Storage estimates are conservative. These checks do not establish speech quality, subtitle accuracy or perceptual lip sync; review complete drafts.
