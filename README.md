# AI Media Skills

**Put your AI agent to work on your media. Keep the workflow, not another subscription.**

A growing collection of practical skills for Codex, Claude Code, and other agents that support `SKILL.md`. Each skill combines focused instructions with the tools and references needed to do real work.

Created and maintained by [Rovidx](https://www.rovidx.com/).

## Quickstart: let your agent set it up

Open your podcast project or a working folder in **Codex, Claude Code, Cursor Agent, Antigravity, or GitHub Copilot's local agent mode in VS Code**. Use a session that can read/write local files and run terminal commands.

### 1. Paste this setup prompt

The same prompt works across these environments; the agent uses the table below to choose its installation location.

```text
Install the podcast-audio-repair skill from:
https://github.com/rovidxmedia/AI-Media-Skills

Fetch the repository into a separate local folder, preserving any existing checkout.
Read its README, skills/podcast-audio-repair/SKILL.md, and helper script before running it.

Use the README's documented skill-location table to install the complete
skills/podcast-audio-repair folder for the agent I am currently using in this
workspace. Choose the project location, not a global installation. Preserve all
scripts, references, licenses, and assets. Do not overwrite an existing skill;
inspect it and explain any conflict first.

Check Python, FFmpeg, ffprobe, and the required audio filters. Set up an isolated
Python environment and install the skill's requirements.txt there. If a required
system tool is missing, explain what I need to install.

Run the installed helper with --help using that environment's Python. Confirm the
bundled model and supporting files exist. Report the skill location, Python
executable, and any missing requirements or session reload needed. Distinguish
files installed successfully from the agent actually discovering the skill.

Do not process any recordings yet.
```

### 2. Paste your first repair request

Replace the recording path, and describe the problem if you know it. This plain-language prompt avoids environment-specific slash commands.

```text
Use the installed podcast-audio-repair skill on:
"<full path to my recording>"

Use the Python environment prepared during setup. Start with a 30-second sample
containing the problem. Reduce background noise conservatively and preserve my
words, timing, and natural voice. Keep the original untouched and write to a new
output folder.

Give me the original/treated comparison, repaired WAV, settings report, and any
limitations. Let me review the sample before processing the whole recording.
```

### Documented skill locations

Each path below is the **parent directory**; install the whole `podcast-audio-repair/` folder inside it. The setup prompt uses project scope so the installation stays with the current workspace.

| Environment | Project location used by the prompt | Optional personal/global location | Official documentation |
| --- | --- | --- | --- |
| Codex | `.agents/skills/` | `~/.agents/skills/` | [Codex skills](https://developers.openai.com/codex/skills/) |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Cursor Agent | `.agents/skills/` (also supports `.cursor/skills/`) | `~/.agents/skills/` or `~/.cursor/skills/` | [Cursor Agent Skills](https://cursor.com/docs/skills) |
| Antigravity App / IDE / CLI | `.agents/skills/` | App / IDE: `~/.gemini/config/skills/`; CLI: `~/.gemini/antigravity-cli/skills/` | [Antigravity skills by surface](https://antigravity.google/docs/skills) |
| GitHub Copilot in VS Code | `.agents/skills/` (also supports `.github/skills/`) | `~/.agents/skills/` or `~/.copilot/skills/` | [VS Code Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills) |

**Choose the agent, not just the editor or model name.** For example, a Codex extension running inside Cursor still uses Codex's discovery rules. If the agent cannot identify its host, tell it which one you are using.

These prompts target local agent sessions. Browser-only chat and remote/cloud agents need different access and setup; a cloud session cannot automatically use recordings on your computer. Other local agents can follow the workflow if they support skill folders and command execution, using their own documented locations.

Locations were checked against official documentation on October 16, 2026. The audio helper was exercised through Codex; installation and skill discovery have not been tested end to end in every listed product.

Prefer manual setup? Continue with the [step-by-step instructions](#start-here-fix-a-short-podcast-sample) below.

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

Use the [documented skill locations](#documented-skill-locations) above for Codex, Claude Code, Cursor, Antigravity, and Copilot. Copy the folder into the selected parent directory; copying just `SKILL.md` leaves out required code and assets.

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

Use the shared [first repair request](#2-paste-your-first-repair-request) above. You can also explicitly select the skill: in Codex, use `$podcast-audio-repair`; in Claude Code or Cursor, select `/podcast-audio-repair` from the skill menu. Antigravity App / CLI also document slash-command invocation. Plain-language requests work without making these shortcuts part of the shared prompt.

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

# Low volume: meet the selected speech loudness with peak limiting when needed.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/loudness-01" --loudness-mode speech --target-lufs -16

# Retain the original dynamics using constant gain only; may remain quieter.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/preserve-01" --loudness-mode preserve

# Experimental echo treatment: listen carefully before keeping it.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/echo-01" --dereverb

# After reviewing a sample, explicitly process the full recording.
python skills/podcast-audio-repair/scripts/repair_audio.py "recording.wav" "runs/full-01" --denoise neural --full
```

On Windows, replace `python` with `.\.venv\Scripts\python.exe`. Each output directory must be new. Denoising is **off by default**; select a treatment deliberately. Use `--start` to choose a troublesome passage and `--audio-stream` to select an audio stream in a video or multi-stream file. With `--full --start N`, processing begins at N seconds and continues to the end.

The default `--loudness-mode speech` aims for **-16 LUFS**, a configurable export target rather than a universal platform requirement. When constant gain cannot reach it safely, the helper uses explicit oversampled lookahead peak limiting, then verifies the rendered loudness within 0.3 LU and checks true peaks. This changes peak dynamics; review the sound. Use `--loudness-mode preserve` for constant gain only. That alternative can miss the target, and its report marks the target as unmet.

## What you get

| Output | Purpose |
| --- | --- |
| `input.wav` | Extracted sample or selected full audio stream; the original source stays where it was |
| `repaired.wav` | Processed 48 kHz, 24-bit WAV |
| `input-matched.wav`, `output-matched.wav` | Constant-gain loudness-matched files for comparison |
| `comparison.mp3`, `comparison.wav` | Loudness-matched original excerpt, 0.75-second pause, then matched treated excerpt; 10 seconds each by default |
| `comparison-actual-volume.mp3`, `comparison-actual-volume.wav` | Original and treated excerpts at their actual export levels, with the same pause and order |
| `report.json` | Commands, settings, measurements, source hashes, warnings, and listening-review status |
| Numbered intermediates | Processing stages retained for diagnosis |

Use the actual-volume preview to assess the intended volume increase. Use the matched preview or full matched WAV pair to assess noise and voice changes without most of the loudness bias. Full-episode matching does not guarantee equal loudness in every excerpt after speech leveling.

## What it can—and cannot—do

- **Noise:** FFmpeg `arnndn` uses a bundled RNNoise model. The `afftdn` alternative is conventional spectral processing.
- **Levels:** conventional dynamic leveling can reduce volume swings. It does not separate overlapping speakers or independently repair guests already mixed into one track.
- **Echo:** NARA-WPE is an experimental statistical treatment. Single-microphone results were limited in the original trials; do not expect every room recording to become studio audio.
- **Preservation:** the helper refuses an existing output directory, checks source hashes, and verifies output shape and peaks. Denoiser alignment can trim/pad an edge; check the first and last spoken sounds.
- **Listening:** technical checks are not a quality verdict. Check words, breaths, quiet speech, pauses, and naturalness yourself.
- **Cost and setup:** this avoids an additional hosted audio service, not every possible cost. Agent access, dependencies, disk space, and processing time still matter.

Mono and stereo input are supported. Multichannel input is rejected rather than silently downmixed. Long recordings use more disk than samples. Speech mode verifies the selected loudness target; preserve mode can remain below it when peak headroom is limited. The report records the achieved loudness and whether the target was met. Neural processing can pad a partial final frame; the helper bounds that padding, measures latency, and retains the exact original frame count.

The original development used controlled examples with added impairments and a second-clip revision. It did not establish a universal preset or a professional mastering guarantee. See [processing provenance and observed limits](skills/podcast-audio-repair/references/processing.md).

## Contribute a skill

Have a useful, repeatable media workflow? See [CONTRIBUTING.md](CONTRIBUTING.md) for the folder format, evidence expectations, and review checks.

## License and credits

Original repository code and documentation are available under the [MIT License](LICENSE). Bundled third-party material retains its own notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg is installed separately.

## Built by Rovidx

[Rovidx Media & Consulting](https://www.rovidx.com/) builds practical software, automation, and media systems. If your audio workflow needs to connect to a larger publishing operation, explore our [media platforms and publishing workflows](https://www.rovidx.com/services/media-technology-consulting).

Use the skills, adapt them, and keep creating.
