# HyperFrames workflow and source-bound helper

Resolve commands from this installed skill's directory. Python 3.10+ and FFmpeg/ffprobe are needed by `scripts/graphics.py`; local HyperFrames additionally needs its supported Node.js (currently 22+), Chromium and selected project packages. Inspect the installed CLI/project pin and help before use. Explain any required package/browser/font download, storage and license first. Use isolated project directories and caches; never update all installed HyperFrames skills as a side effect. The helper installs nothing and uses no network.

## Author and render

Use the host's installed `hyperframes` router and selected workflow. Read `hyperframes-core` before HTML; use `hyperframes-keyframes` for seek-safe motion, `hyperframes-registry` for catalog search/installation, and `hyperframes-cli` for command-specific contracts. Find sibling skills in the actual installation or use the official [HyperFrames skill source](https://github.com/heygen-com/hyperframes). This repository does not bundle them. If unavailable, disclose that blocker and install the chosen supported workflow through the host's normal mechanism; do not claim a cue sheet alone is a rendered video.

Carry the confirmed brief into the selected workflow instead of reopening a generic interview. For longer programs, make one short project/composition per cue or a small reusable batch. Keep each overlay's local time zero aligned to its cue start. Preserve source assets and source/plan hashes. Capture representative screenshots locally or adopt supplied assets; no authenticated provider action is required for local adoption.

Example commands (adapt to the installed version and active workflow):

```sh
npx hyperframes doctor --json
npx hyperframes catalog --query "clean lower third" --json
npx hyperframes init "CUE_PROJECT" --non-interactive --example=blank
npx hyperframes add lt-clean-bar
npx hyperframes check
npx hyperframes snapshot --at 0.4,2,4.4
npx hyperframes preview --background
npx hyperframes render --format mov --fps 30000/1001 --output "cue.mov"
```

Names such as `lt-clean-bar`, `lt-dark-card`, `inline-highlight` and `marker-highlight` were present in the catalog during development; discover them rather than treating that list as a fixed API. Inspect the block's own composition ID and sizing before mounting it. Name/role and screenshot copy must come from verified episode facts, not template defaults.

Keep HTML/body and the composition background transparent. Set explicit root dimensions and duration (`cue.frames / fps`), and author at the actual frame size. Use local dependency/font files for offline rendering, preserving their licenses and recorded versions. Register one paused timeline per composition with seek-safe values; animate an inner wrapper. If the selected version's checks miss a particular layout/mount defect, inspect actual snapshots and the alpha render rather than suppressing the finding. No cloud render, project publish or feedback submission is implied.

Sample the actual animation as well as its reading hold. In the tested 0.8.61 CLI, default evenly spaced checks missed a short entrance and exit around a long steady hold and reported `sweep_static`. Explicit `check --at` times inside those transitions, together with `--at-transitions`, exercised the motion successfully. Inspect snapshots in forward and backward order to confirm seeking works; do not suppress a real timeline failure or add pointless movement merely to satisfy the checker. Discover equivalent flags from the installed CLI when its version differs.

## Cue helper

```sh
python scripts/graphics.py analyze --input "finished SDR master.mkv" --job NEW_GRAPHICS_JOB
python scripts/graphics.py plan --job NEW_GRAPHICS_JOB --cues CUES.json
```

The input must be prepared progressive SDR, unrotated, square-pixel video with consistent nominal rate metadata. The helper rejects metadata suggesting VFR; that check alone cannot prove CFR. Inspect source timestamps when uncertain and prepare the chosen CFR explicitly. Source dimensions/rate are retained. Keep job folders outside the repository/installed skill. `plan` is immutable; revisions get a new child job so accepted media is not silently overwritten.

Minimal cue input (synthetic; replace the hash with the analyzed source SHA):

```json
{
  "source_sha256": "EXACT_INPUT_SHA256",
  "reserved_regions": [{"label": "captions", "box": [0, 0.82, 1, 0.18]}],
  "cues": [{
    "id": "speaker-id", "kind": "lower-third", "start": 3, "end": 8,
    "box": [0.06, 0.64, 0.5, 0.14], "copy": "Verified name | Verified role",
    "purpose": "Identify the speaker at the first substantive appearance",
    "evidence": "User-supplied episode credits"
  }]
}
```

Kinds: `lower-third`, `screenshot`, `key-phrase`, `steps`, `diagram`, `stat`. `box` is normalized canvas x/y/width/height; copy/evidence/purpose remain editorial data. Times are input-program seconds, snapped to the output frame grid. Intentional overlapping graphics require `allow_overlap: true` on both cues; reserved regions still cannot be covered. The helper cannot detect a moving face, understand source evidence or establish safe margins automatically.

A screenshot cue also needs `asset` (local PNG/JPEG/WebP, relative to the cue JSON), `asset_origin` (source/capture and usage context) and optional `highlights`: `[{"box":[0.1,0.2,0.5,0.1],"start":1,"end":3,"text":"Exact visible passage"}]`. Highlight boxes are normalized **screenshot-image coordinates** and highlight times are local to the cue. Authoring must map them through image contain/crop transforms. Asset hashes bind the plan; changed screenshots require revision. Treat privacy/redaction and evidence review as editorial work, not something a JSON validator proves.

## Composite and verify

After actual HyperFrames checks/rendering, write this external manifest:

```json
{
  "source_sha256": "EXACT_INPUT_SHA256",
  "plan_signature": "SIGNATURE_FROM_PLAN",
  "hyperframes_version": "ACTUAL_RENDERED_VERSION",
  "overlays": {"speaker-id": "speaker-id/overlay.mov"}
}
```

```sh
python scripts/graphics.py composite --job NEW_GRAPHICS_JOB --overlays OVERLAYS.json --output "new graphics master.mkv" --accept-plan PLAN_SIGNATURE
```

The acceptance argument records the agent's selected plan; imported JSON/flags cannot grant user consent. Resolve any user-reserved preview checkpoint before a full render. Render representative excerpt child jobs first, with cue times rebased to that excerpt and its own source hash; do not submit a ten-second preview as the full episode.

The compositor verifies every MOV's alpha-capable ProRes format, canvas, rational rate, exact decoded slot frames and a nonblank/partly transparent midpoint. The midpoint test is only a smoke check, not proof of every frame's alpha. It then composites all cues in one FFmpeg pass, copies every source audio track, and writes a new FFV1/yuv444p MKV picture master (16-bit yuv444p16le when the SDR source exceeds eight bits). Known non-Rec.709 primaries require reviewed preparation; missing color tags require the agent's source/color diagnosis rather than an automatic claim of correctness. The conservative disk preflight budgets an uncompressed-equivalent master; use a spacious external working directory. There is no automatic low-memory fallback, chunked browser rendering or claim of unlimited concurrent overlays: benchmark a representative plan, keep cue projects short, and use the upstream workflow for a different reviewed render strategy when needed.

The final `.report.json` binds source, cue plan, overlay hashes and versions, and verifies exact decoded picture frames, full decoding, geometry/rate/duration, audio formats/count/labels/start timing and source preservation. Original chapters are deliberately not carried into the master; Producer/Packager owns verified final chapters. Semantic accuracy, motion quality and perceptual lip sync require review. Preserve failed/partial evidence; the helper refuses existing outputs and has no resumable full-episode encoder. Completed HyperFrames cue exports can be reused when their source/plan/assets remain unchanged.

For an excerpt review, offer before/after playback at the same timestamp with only one version playing. A browser-friendly MP4 can use a reviewed complete audio mix while the lossless master retains every track; label that distinction. Encode both comparison sides with the same settings, verify their frame counts and decoding, and provide the cue sheet, verification report and editable project alongside them. Keep raw/master preservation evidence separately from the user's visual acceptance. Decoded audio stream hashes can confirm that compositing preserved each track exactly; they do not establish perceptual lip sync.

For Producer, also retain a project manifest listing editable HTML, assets, local dependency/font licenses, project lockfiles, their hashes and verified HyperFrames version. Record the cue JSON as `cue-sheet`, the project manifest as `project`, finished MKV as `media` and the verification report as `report`.
