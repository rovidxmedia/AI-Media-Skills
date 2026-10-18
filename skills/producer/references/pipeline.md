# Pipeline, handoffs and recovery

Read each selected specialist's current `SKILL.md` and relevant interface before execution. Find it in the host's installed skill roots or the repository's sibling folders; do not hardcode a user directory. Install missing skills deliberately through the host's normal installer. Producer itself uses only the Python standard library. The host agent coordinates calls; the ledger is not a headless media-rendering or upload service.

## Stage contracts

| Stage | Work owner and input | Record actual outputs |
| --- | --- | --- |
| `diagnose` | Editor/Video Enhance/audio assessment on the raw source; computer inventory and requested deliverables | Combined diagnosis/treatment report |
| `prepare` | Explicit structural preparation when HDR/interlacing blocks editing; otherwise skip with unchanged input | `media`, `report` |
| `edit` | Editor on the prepared media: Natural cuts, reviewed retakes, sparse held punch-ins, source mapping and selected captions | `media`, `report`, `timeline` |
| `audio` | Optional Podcast Audio Repair, then optional That Radio Voice; remux only the chosen finished mix after timing checks | `media`, `report` |
| `enhance` | Optional Video Enhance on retained footage, scene-aware restoration/interpolation and reviewed output choices | `media`, `report` |
| `master` | Agent verifies the finished full program, all intended audio/labels, geometry/rate, duration/decoding and representative lip sync | `media`, `report` |
| `transcript` | Editor ASR workflow on this exact master, verified source-bound import or validated timeline remap; correct names/words | `words`, `report`; optional readable transcript/chapters |
| `package` | Podcast Packager on the final master and matching transcript; optionally marketing/brand guidance | `video`, `audio`, `square`, `wide`, `metadata`, `report` |
| `shorts` | Short-form Clips on the exact final master/transcript; crop/stacked/fit selected from actual footage | `report`, one finished MP4 per selected clip; include clean/caption/cover/copy artifacts as needed |
| `review` | Agent assembles final media/copy/art, quality findings and destination readiness for user review | `report`; completion means ready for final review, not publishing consent |

The dependency graph runs through `transcript`, then allows package/shorts independently before final review. An existing project workflow may own different tools and additional graphics/doc stages; follow its applicable instructions, map verified results to these handoffs, and keep its manifest authoritative. Do not start a second production or copy its schedule/brand/account details into this generic skill. Explicit user changes take precedence.

Preserve the original and source SHA. Select a complete dialogue mix without summing duplicate tracks. Keep all-track edit/restoration masters and track labels until delivery exports deliberately choose the approved mix. Repairing a WAV requires verifying frame count/duration and remuxing with unchanged video/other tracks before marking the media stage finished. Do not confuse an audio-only result with the next stage's video input. Avoid repeated mastering and lossy generations; use verified masters and copy/remux where compatible.

Structural preparation precedes editing when necessary; ordinary enhancement follows cuts to avoid expensive work on discarded footage. Compare new emphasis crops with source softness. After duration-changing work, obtain timings tied to the new master; after duration-preserving remux/enhancement, verify geometry/rate and timestamp mapping and rebind only when actually valid. Never change a transcript's source hash merely to bypass validation. Final chapters, covers and short bounds share the final timeline.

## Commands

Examples abbreviate the installed helper path and use explicit external job directories. The agent gathers setup answers and writes JSON; the user need not hand-author it.

```sh
python scripts/producer.py doctor --project PROJECT --skills-root INSTALLED_SKILLS
python scripts/producer.py setup --project PROJECT --config CHOICES.json
python scripts/producer.py init --project PROJECT --input "raw recording.mkv" --job NEW_EPISODE_JOB
python scripts/producer.py status --job EPISODE_JOB
python scripts/producer.py record --job EPISODE_JOB --stage diagnose --receipt DIAGNOSIS_RECEIPT.json
```

`init --overrides RUN_CHOICES.json` accepts `{"skills": {"editor": {"style": "tight"}}}` or other explicitly chosen per-run skill preferences. It does not change project defaults. Do not initialize a second job just because a render/upload timed out; inspect the existing episode and platform queues first.

## Receipts and lineage

After running and checking a specialist, write a receipt with the **actual input media hash** and output paths. Relative paths resolve from the episode job root:

```json
{
  "input_sha256": "SHA256_OF_THIS_STAGE_INPUT_MEDIA",
  "status": "completed",
  "artifacts": {
    "media": "edit/edited.mkv",
    "report": "edit/report.json",
    "timeline": "edit/timeline.json"
  }
}
```

For `diagnose` and `prepare`, input is the raw source. The next media stage uses the prior stage's `media`. Transcript, package, shorts and final review use `master.media`. Transcript `words` JSON must itself bind to that exact SHA. The specialist owns validation of words, timestamps and quality; the coordinator verifies the lineage rather than pretending to transcribe or inspect media files.

`prepare`, `audio` and `enhance` can record `status: skipped`, a nonempty `reason` and `artifacts.media` pointing to the exact unchanged input. Other required stages cannot be skipped. Shorts may be skipped when configured count is zero, or when the user explicitly declines them: include `selected_count: 0`, a reason and `decision_reference`. For a changed positive selected count, include `selected_count` and its decision reference; record at least that many finished MP4s. A report alone is not a short.

The helper hashes actual nonempty artifacts, binds each stage to prerequisite receipt signatures and saves an integrity-checked `production.json`. `record --replace` deliberately records a revised result, makes dependent results stale and clears release approval. Preserve superseded files/child jobs; never overwrite accepted media just to make a receipt pass. Source changes, missing/changed artifacts, mismatched final transcript, stale prerequisites and untracked publication files block advancement. Files/hashes establish existence and lineage, not media quality or human consent.

Use child `resume` commands only under their unchanged accepted plan and source. Producer `status` identifies the first incomplete/changed/stale handoff; it does not rerun engines or approve a preview. Source-specific plans, chosen settings, versions, benchmarks and any human acceptance belong in the child jobs and episode notes. An interrupted helper leaves `.running`; verify its PID has stopped before removing the stale lock. Do not delete a live lock or automatically discard partial outputs.

## Validation limits

Producer tests use generated local files and simulated publisher readbacks to exercise setup, portability, defaults, lineage, final transcript binding, stale artifacts, review authorization, schedule validation, uncertain retries, destination mismatch and receipt persistence. They do not establish ASR accuracy, good editing, good art, connector authentication or successful real uploads. Specialist suites cover their actual media engines. Review real treatment samples and complete finished deliverables before claiming quality acceptance.
