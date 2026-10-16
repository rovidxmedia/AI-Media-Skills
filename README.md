# AI Media Skills

**Put your AI agent to work on your media. Keep the workflow, not another subscription.**

A growing collection of practical skills for Codex, Claude Code, and other agents that support `SKILL.md`. Each skill combines focused instructions with the tools and references needed to do real work.

Created and maintained by [Rovidx](https://www.rovidx.com/).

## Available skills

| Skill | What it does | Included |
| --- | --- | --- |
| [Podcast Audio Repair](skills/podcast-audio-repair/SKILL.md) | Reduce background noise, even out speech levels, and cautiously test room-echo treatment | Local Python helper, RNNoise model, optional WPE code, comparison audio, and a settings report |

This repository starts with one working skill. New media skills will get their own folders under `skills/` and an entry in this table when they are ready.

## Start here: fix a short podcast sample

You do not need a new audio-service account to use Podcast Audio Repair. You need an agent that can run local commands, Python, and FFmpeg. The agent directs the work; the bundled helper and audio tools process the recording.

**The helper does not upload your audio.** Your agent host still has its own connection, permissions, and billing. Prompts, paths, and logs may be visible to that host.

### 1. Get the repository and dependencies

Install [Python](https://www.python.org/downloads/), [Git](https://git-scm.com/downloads), and [FFmpeg with ffprobe](https://ffmpeg.org/download.html). Put FFmpeg and ffprobe on your PATH. Neural denoising requires a build with the `arnndn` filter; spectral denoising uses `afftdn`.

The original workflow was tested on Windows with Python 3.13.3 and FFmpeg 7.0. The Python requirements pin that tested dependency set. Other platforms and FFmpeg builds need their own sample check.

**macOS / Linux**

```bash
git clone https://github.com/rovidxmedia/AI-Media-Skills.git
cd AI-Media-Skills
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r skills/podcast-audio-repair/requirements.txt
python skills/podcast-audio-repair/scripts/repair_audio.py --help
```

**Windows PowerShell**

```powershell
git clone https://github.com/rovidxmedia/AI-Media-Skills.git
Set-Location AI-Media-Skills
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r skills/podcast-audio-repair/requirements.txt
.\.venv\Scripts\python.exe skills/podcast-audio-repair/scripts/repair_audio.py --help
```

If your Python launcher uses a different version, select the interpreter you installed. Tell your agent the full path to this virtual environment's Python executable; it should use the same environment when running the helper.

### 2. Give your agent the skill

For a first try, ask your agent to read `skills/podcast-audio-repair/SKILL.md` directly from this clone. To make it discoverable across projects, copy the **whole skill folder**, including its scripts and assets:

| Agent | Personal installation | Project installation |
| --- | --- | --- |
| Codex | `~/.agents/skills/podcast-audio-repair/` | `.agents/skills/podcast-audio-repair/` |
| Claude Code | `~/.claude/skills/podcast-audio-repair/` | `.claude/skills/podcast-audio-repair/` |

For example, from the repository root:

```bash
# Codex personal installation. Stop if you already have this skill.
mkdir -p ~/.agents/skills
test ! -e ~/.agents/skills/podcast-audio-repair &&
  cp -R skills/podcast-audio-repair ~/.agents/skills/

# For Claude Code, use ~/.claude/skills instead.
```

```powershell
# Codex personal installation. Preserve any existing installation.
$skillTarget = Join-Path $HOME '.agents/skills/podcast-audio-repair'
if (Test-Path -LiteralPath $skillTarget) { throw 'Skill already installed; review before replacing it.' }
New-Item -ItemType Directory -Path (Split-Path -Parent $skillTarget) -Force | Out-Null
Copy-Item -LiteralPath 'skills/podcast-audio-repair' -Destination $skillTarget -Recurse

# For Claude Code, use '.claude/skills/podcast-audio-repair' for $skillTarget.
```

Reload or start a new agent session if the skill does not appear. Use the location your installed agent supports; avoid duplicate installations with the same skill name. See the official [Codex skill locations](https://developers.openai.com/codex/skills/) and [Claude Code skills documentation](https://code.claude.com/docs/en/skills).

### 3. Ask for a repair you can judge

In Codex, invoke `$podcast-audio-repair`; in Claude Code, use `/podcast-audio-repair`. Then give it a concrete task:

```text
Use podcast-audio-repair on my recording at <input-file>.
Inspect the available tools and use Python from <virtual-environment>.
Start with 30 seconds containing the problem.
Reduce the background noise without changing my words or vocal character.
Keep my source untouched and use a new output folder.
Give me the original/treated comparison, repaired WAV, and settings report.
Ask me to review the sound before processing the whole recording.
```

If the result damages quieter words or sounds unnatural, ask for a gentler treatment. Test the saved approach on a second clip rather than assuming one preset works everywhere.

## Run the helper directly

Use your virtual environment's Python. These commands run from the repository root:

```bash
# Neural noise reduction: a 30-second sample.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/noise-01" --denoise neural --seconds 30

# Conventional spectral alternative, useful when neural treatment is unsuitable.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/spectral-01" --denoise spectral --noise-floor -36 --noise-reduction 12

# Uneven speech levels, without denoising.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/levels-01" --level

# Experimental echo treatment: listen carefully before keeping it.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/echo-01" --dereverb

# After reviewing a sample, explicitly process the full recording.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/full-01" --denoise neural --full
```

On Windows, replace `python` with `.\.venv\Scripts\python.exe`. Each output directory must be new. Denoising is **off by default**; select a treatment deliberately. Use `--start` to choose a troublesome passage and `--audio-stream` to select an audio stream in a video or multi-stream file. With `--full --start N`, processing begins at N seconds and continues to the end.

## What you get

| Output | Purpose |
| --- | --- |
| `input.wav` | Extracted sample or selected full audio stream; the original source stays where it was |
| `repaired.wav` | Processed 48 kHz, 24-bit WAV |
| `input-matched.wav`, `output-matched.wav` | Constant-gain loudness-matched files for comparison |
| `comparison.mp3`, `comparison.wav` | Original excerpt, 0.75-second pause, then treated excerpt; 10 seconds each by default |
| `report.json` | Commands, settings, measurements, source hashes, warnings, and listening-review status |
| Numbered intermediates | Processing stages retained for diagnosis |

Use the full matched WAV pair for a longer review. Loudness matching helps compare noise treatments; also compare the un-matched files when assessing intended level changes.

## What it can—and cannot—do

- **Noise:** FFmpeg `arnndn` uses a bundled RNNoise model. The `afftdn` alternative is conventional spectral processing.
- **Levels:** conventional dynamic leveling can reduce volume swings. It does not separate overlapping speakers or independently repair guests already mixed into one track.
- **Echo:** NARA-WPE is an experimental statistical treatment. Single-microphone results were limited in the original trials; do not expect every room recording to become studio audio.
- **Preservation:** the helper refuses an existing output directory, checks source hashes, and verifies output shape and peaks. Denoiser alignment can trim/pad an edge; check the first and last spoken sounds.
- **Listening:** technical checks are not a quality verdict. Check words, breaths, quiet speech, pauses, and naturalness yourself.
- **Cost and setup:** this avoids an additional hosted audio service, not every possible cost. Agent access, dependencies, disk space, and processing time still matter.

Mono and stereo input are supported. Multichannel input is rejected rather than silently downmixed. Long recordings use substantially more memory and disk than samples. A requested loudness target may be limited by available peak headroom; the report records the achieved result.

The original development used controlled examples with added impairments and a second-clip revision. It did not establish a universal preset or a professional mastering guarantee. See [processing provenance and observed limits](skills/podcast-audio-repair/references/processing.md).

## Contribute a skill

Have a useful, repeatable media workflow? See [CONTRIBUTING.md](CONTRIBUTING.md) for the folder format, evidence expectations, and review checks.

## License and credits

Original repository code and documentation are available under the [MIT License](LICENSE). Bundled third-party material retains its own notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg is installed separately.

## Built by Rovidx

[Rovidx Media & Consulting](https://www.rovidx.com/) builds practical software, automation, and media systems. If your audio workflow needs to connect to a larger publishing operation, explore our [media platforms and publishing workflows](https://www.rovidx.com/services/media-technology-consulting).

Use the skills, adapt them, and keep creating.
