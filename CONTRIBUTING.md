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

## Keep contributions safe to share

Only include media and code you can redistribute. Do not commit client recordings, credentials, generated job reports, personal machine paths, private contact details, caches, or virtual environments. For third-party assets, retain licenses, source links, and hashes where useful.

Open an issue for a reproducible problem or a pull request with the change, intended behavior, validation performed, and remaining limitations. Describe platform-specific failures with tool versions and sanitized errors. Avoid posting a recording or full processing report unless you have checked its contents and have permission to share it.

Original contributions use this repository's MIT license. Identify separately licensed material explicitly.
