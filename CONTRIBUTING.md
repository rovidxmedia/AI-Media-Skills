# Contributing

AI Media Skills is a collection of working media capabilities. A new skill should solve a concrete task and produce something a person can inspect.

## Add one capability per folder

```text
skills/
  your-skill-name/
    SKILL.md
    scripts/           # Only when executable helpers are useful
    references/        # Sources, technical details, observed limits
    assets/            # Models or other required reusable resources
    agents/openai.yaml # Optional agent UI metadata
    requirements.txt  # If Python dependencies are needed
```

Use lowercase, hyphenated names. The `SKILL.md` frontmatter needs a matching `name` and a concise `description` of when to use it. Keep the main instructions focused on the outcome, meaningful constraints, and completion evidence. Put substantial conditional detail in linked references.

Do not add empty skill folders to advertise planned work. Add ready skills to the README catalog with an honest description and setup requirements.

## Make the workflow portable

- Use paths relative to the skill, not your machine or a private project.
- Declare tools, versions tested, dependencies, and any network/account requirements.
- Preserve source media by default and separate output names from input names.
- Keep substantive references in one maintained place rather than duplicating instructions.
- Keep branding in project documentation. Do not make a skill insert advertisements into users' media.

## Provide evidence

Exercise new or changed processing on a representative sample and a different clip. Explain what succeeded, what failed, and what still needs listening or visual review. Distinguish neural processing, conventional processing, measurements, and human judgments.

For Podcast Audio Repair and That Radio Voice, run the integration checks from the repository root:

```bash
python -m unittest discover -s tests -v
```

Install `skills/podcast-audio-repair/requirements.txt` and FFmpeg first; That Radio Voice shares those Python dependencies and requires the sibling repair helper. These synthetic-fixture checks verify execution and source/output handling; they do not establish good speech quality. Each skill's processing reference records its tested environment.

For Video Enhance, the CPU checks require only Python, FFmpeg and ffprobe:

```bash
python -m unittest discover -s tests -p "test_video_enhance.py" -v
```

Keep GPU downloads out of ordinary CPU CI. Record tested hardware, model/version, actual inference results and unverified platforms in its validation reference. Inspect a real comparison before claiming perceptual improvement.

For Editor, run `python -m unittest discover -s tests -p "test_editor.py" -v` with Python and FFmpeg/ffprobe. The generated tests need neither a model nor network access. Test local transcription separately in its isolated optional environment; do not infer recognition quality or safe word cuts from technical timing checks. Keep all real transcripts, source-bound job files and model caches outside Git.

## Keep contributions safe to share

Only include media and code you can redistribute. Do not commit client recordings, credentials, generated job reports, personal machine paths, private contact details, caches, or virtual environments. For third-party assets, retain licenses, source links, and hashes where useful.

Open an issue for a reproducible problem or a pull request with the change, intended behavior, validation performed, and remaining limitations. Describe platform-specific failures with tool versions and sanitized errors. Avoid posting a recording or full processing report unless you have checked its contents and have permission to share it.

Original contributions use this repository's MIT license. Identify separately licensed material explicitly.

For Video Motion Graphics, run `python -m unittest discover -s tests -p "test_motion_graphics.py" -v` with Python and FFmpeg/ffprobe. Generated ProRes-alpha fixtures exercise cue/source/asset binding, fractional timing, protected regions, alpha/geometry/frame guards, all-track audio and lossless compositing. They do not run HyperFrames. Separately exercise actual pinned HyperFrames compositions, checks, seeked snapshots and alpha exports; inspect the composites in motion on representative footage. Record source links, versions, hardware/platform limits and actual human review separately. Keep upstream registry/runtime/font downloads and private screenshots out of the contribution.

## Publishing and short-form checks

Run `python -m unittest discover -s tests -p "test_publishing.py" -v` with Python and FFmpeg/ffprobe (libx264, libmp3lame, AAC and libass/subtitles). These tests generate their own source fixtures and need no model/network. They exercise packaging, audio-only video, multitrack selection, captions, portrait layouts, fractional rates, invalid imports, storage failures, interrupted resume and hash receipts. Run the full existing suite before submitting. Keep semantic-selection judgments, speech/visual review and actual ASR/image-engine validation separate from these technical checks. Do not commit private episode text, media, job reports or output assets.

For Producer, run `python -m unittest discover -s tests -p "test_producer.py" -v` with standard-library Python 3.10+. Generated files and simulated publisher readbacks exercise first-run setup, shared profiles, machine separation, lineage, final transcript binding, review records, exact account/schedule checks and uncertain retry handling. These are orchestration checks, not real media or live-upload tests. Maintain the shared profile schema in Producer; specialist skills only route to the applicable profile. Keep real project profiles, credentials, machine inventories and release receipts outside public commits.

## Portable pack changes

Run `python -m unittest discover -s tests -p "test_install.py" -v` after installer, packaging or profile changes. These checks copy to a temporary project with spaces/non-ASCII paths, preserve conflicts, verify assets/licenses, exercise installed helpers and configure a fictional show without publishing.

Keep the installer standard-library-only and free of network, shell-profile changes, package installs and media processing. Keep private installations, junctions and machine inventories out of Git. Optional skills must not become undisclosed requirements of the base pack.
