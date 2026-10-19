# Media work owners

Use for selecting stages in a Producer-managed job. A requested specialist can execute directly; this table is not an instruction to expand every request into a full production.

| Requested production or stage | Work owner |
| --- | --- |
| Recorded speech structure, retakes, fillers, pauses and emphasis crops | Editor; a project-mandated native editor takes precedence |
| Noise, uneven speech levels or a diagnosed echo trial | Podcast Audio Repair |
| Requested broadcast voice treatment | That Radio Voice, retaining its shared audio-helper dependency |
| Diagnosed picture restoration or selected resolution/cadence change | Video Enhance |
| Supporting explanatory graphics on recorded speech | Video Motion Graphics for cues/compositing; HyperFrames for authoring/rendering |
| Full-song music video with the local footage/Higgsfield workflow | Music Video Director; preserve its song map, budget and generation ledger |
| Product promotion or website showcase | HyperFrames router then Product Launch Video |
| Custom video, montage or a general composition | HyperFrames router then its matching workflow, usually General Video |
| Standalone motion asset | HyperFrames router then its matching motion workflow; load a missing workflow deliberately |
| Media assets, generation, transcription or caption resources inside HyperFrames | Media Use; use only needed providers/capabilities |
| Finished podcast exports, artwork and publishing copy | Podcast Packager |
| Selected portrait excerpts, framing, corrected captions and local delivery | Short-form Clips |
| Explicit legacy Bash/FFmpeg edit pipeline | Video Editing Skill; not interchangeable with native Higgsedit |
| Framework structure, motion, mixing, rendering or Studio layout | The corresponding HyperFrames domain skill |

For titles/thumbnails or platform strategy, load the relevant installed marketing skill when needed. A native Google Doc uses the Google Docs skill. These are optional stage dependencies, not a requirement to load the whole catalog.

## Optional skills

This pack contains the eight original production skills listed in the README. HyperFrames and its upstream workflows/domains are separately installed dependencies for requested motion work. Music Video Director, the legacy Bash editor, marketing skills and document connectors are optional capabilities, not bundled promises. Discover their availability before routing. If an optional capability is absent, explain the missing skill/tool and continue supported independent work; do not invent its private commands or silently replace the requested output.

## Choose the state model

For recorded episodes without an existing authoritative workflow, use [project-config.md](project-config.md) and [pipeline.md](pipeline.md). `producer.py` implements that existing episode graph, not a universal video pipeline.

For other media, let the selected workflow own `BRIEF.md`, `STORYBOARD.md`, `project.json`, edit/song maps and its other documented state. Record the overall stage plan, handoffs and final artifact locations in that workflow's existing project notes. Resume those files; do not create a parallel Producer episode ledger or migrate an existing project.

For an established show, read its selected show skill and runbook. Its manifest, actual editor, filenames, branding, output settings, counts, publishing identities and schedule remain authoritative. Producer coordinates the stages without duplicating that runbook or introducing another approval gate.

## Respect real interfaces

Inspect installed command help and the selected project's version pin before executing. Treat the installed specialist's references as the authority for supported arguments; a project preference is not automatically a CLI flag. Resolve incompatible delivery requirements with the selected workflow rather than claiming the helper supports them.

Podcast Packager currently exports a fixed 256 kb/s MP3 and fixed artwork sizes. A show's specified 192 kb/s MP3 or other delivery geometry must use its designated export workflow or an explicitly supported conversion, followed by verification; do not invent a bitrate flag. Preserve the original master and avoid another lossy picture encode where compatible.

When Producer hands a confirmed brief to HyperFrames, reuse known fields and review decisions. Run only missing route-specific discovery. HyperFrames retains the composition contract, route-specific technical work and quality checks. An explicitly selected Music Video Director remains the director rather than being rerouted to the upstream music-to-video workflow.
