# AI Media Skills

**Put your AI agent to work on your media. Keep the workflow, not another subscription.**

A growing collection of practical skills for Codex, Claude Code, and other agents that support `SKILL.md`. Each skill combines focused instructions with the tools and references needed to do real work.

Created and maintained by [Rovidx](https://www.rovidx.com/).

Start with [Podcast Audio Repair](#start-here-fix-a-short-podcast-sample) for noise and uneven or low levels. Use [That Radio Voice](#that-radio-voice) on clean or repaired speech for a fuller, denser broadcast-style treatment. The two skills can run in sequence.

For the picture, [Video Enhance](#video-enhance) inspects the recording and hardware, offers local CPU repair or optional AI enhancement, and shows a comparison before a full render.

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

Each path below is the **parent directory**; install each selected skill's whole folder inside it. The repair setup prompt installs `podcast-audio-repair/`. [That Radio Voice](#that-radio-voice) needs both skill folders side by side. These setup prompts use project scope so installation stays with the current workspace.

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
| [That Radio Voice](skills/that-radio-voice/SKILL.md) | Give clean speech a fuller, denser radio sound with soft gating, EQ, compression, harmonic excitement, and peak-limited mastering | Big and Warm presets, local Python helper, WAV/MP3 exports, two comparison types, and a settings report; requires Podcast Audio Repair alongside it |
| [Video Enhance](skills/video-enhance/SKILL.md) | Repair grain, poor lighting, softness, shake, flicker and interlacing; optionally upscale or interpolate motion | Portable CPU helper, optional Real-ESRGAN/RIFE/SeedVR2 adapters, hardware checks, preview approval and resumable renders |

Each capability has its own folder under `skills/`. New skills enter this catalog when they have a working, reviewable workflow.

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

## That Radio Voice

[That Radio Voice](skills/that-radio-voice/SKILL.md) gives recorded speech a deliberately produced radio character: more body and presence, denser dynamics, and upper harmonic excitement. It uses conventional local audio processing with FFmpeg. It keeps the speaker's pitch, words, timing, and mono/stereo layout.

Use a clean or repaired WAV. Repair troublesome noise or room echo first; compression and excitement can emphasize problems that remain. A typical workflow is **recording → Podcast Audio Repair → repaired WAV → That Radio Voice**. This does not separate guests or overlapping voices already mixed into one track.

### Set it up with your agent

Paste this in a local agent session:

```text
Install That Radio Voice from:
https://github.com/rovidxmedia/AI-Media-Skills

Read the README and skills/that-radio-voice/SKILL.md. Install the complete
skills/that-radio-voice and skills/podcast-audio-repair folders side by side in
the project skill location documented for this agent. Keep their scripts,
references, licenses, requirements, and assets. Inspect existing installations
before replacing anything; check that the repair helper supports export_loudness.

Use an isolated Python environment and install
skills/podcast-audio-repair/requirements.txt. Check FFmpeg/ffprobe, MP3 encoding,
and the radio helper's required filters. Run both helpers with --help and report
their locations, the Python executable, and any missing dependencies or reload.
Do not process a recording yet.
```

The radio helper shares loudness measurement, mastering, source hashing, and comparison generation with Podcast Audio Repair. Both folders must use the same parent skill directory:

```text
<agent skill directory>/
  podcast-audio-repair/
  that-radio-voice/
```

Use the [skill-location table](#documented-skill-locations) to choose that directory. For manual use from this repository, the folders are already in the right layout under `skills/`. The existing [dependency setup](#1-get-the-repository-and-dependencies) prepares Python for both helpers. Radio-specific filters include `agate`, `equalizer`, `acompressor`, `aexciter`, and `deesser`; mastering also uses `alimiter`, `aresample`, and `loudnorm`. A typical full FFmpeg build supplies these, but the helper checks availability. It encodes MP3 with `libmp3lame`.

If the repair helper lives elsewhere, pass `--repair-helper "<path to repair_audio.py>"`. Copying only the radio skill's `SKILL.md` leaves out its processor and does not supply its dependency.

### Ask for the sound

```text
Use the installed That Radio Voice skill on:
"<full path to my repaired.wav>"

Use the prepared Python environment. Make a 30-second sample with the Big preset,
including soft words, breaths, sibilants, and pauses. Preserve the source, words,
timing, and channels. Give me the radio WAV and MP3, a loudness-matched comparison
for judging tone, an actual-volume comparison, and the settings report.
Let me review the sample before processing the full recording.
```

In Codex you can explicitly select `$that-radio-voice`; the plain-language request above also works with other local agents that have discovered the skill.

| Preset | Starting character |
| --- | --- |
| `big` (default) | Stronger body and presence, 4:1 soft-knee compression, and more harmonic excitement |
| `warm` | Lighter body/presence shaping, 2.5:1 compression, and gentler excitement |

Both presets include rumble filtering, a soft gate with bounded attenuation, and light de-essing when the exciter is enabled. Default delivery targets **-14 LUFS**, verified within 0.3 LU with peak headroom. This is a configurable creative target, not a universal broadcasting requirement. Already compressed recordings may need the lighter preset. Technical checks do not establish that a voice sounds natural or that the effect suits it.

### Run it directly

From the repository root, using the prepared Python environment:

```bash
python skills/that-radio-voice/scripts/radio_voice.py --help

# Compare a short passage with the prominent Big treatment.
python skills/that-radio-voice/scripts/radio_voice.py "repaired.wav" "runs/radio-big-01" --preset big --start 60 --seconds 30

# Try a gentler treatment on the same passage.
python skills/that-radio-voice/scripts/radio_voice.py "repaired.wav" "runs/radio-warm-01" --preset warm --start 60 --seconds 30

# Reduce bass weight and brightness while keeping the Big compressor.
python skills/that-radio-voice/scripts/radio_voice.py "repaired.wav" "runs/radio-tuned-01" --preset big --body-db 2 --presence-db 1 --exciter-amount 0.8

# After listening review, process the complete repaired recording.
python skills/that-radio-voice/scripts/radio_voice.py "repaired.wav" "runs/radio-full-01" --preset big --full --target-lufs -14
```

On Windows, replace `python` with `.\.venv\Scripts\python.exe`. Each run directory must be new. `--full` explicitly selects full processing; with `--start N`, it processes from N seconds to the end. Files must contain exactly one mono or stereo audio stream.

To reduce lost breaths or word endings, lower `--gate-threshold-db` (for example, `-55`), reduce `--gate-reduction-db`, or compare `--no-gate`. The default gate threshold is -50 dBFS **after input staging**, with at most 12 dB attenuation. For harsh brightness, lower `--exciter-amount` or `--presence-db`, or compare `--no-exciter`. For excessive density, reduce `--compression-ratio` or use Warm. `--target-lufs` accepts -20 through -12 LUFS. Judge these changes on a sample rather than stacking every control at once.

### Radio outputs and review

| Output | Purpose |
| --- | --- |
| `radio-voice.wav` | Full selected audio or sample, 48 kHz, 24-bit PCM, original mono/stereo layout |
| `radio-voice.mp3` | 256 kb/s listening copy, measured and decoded for verification |
| `comparison.mp3`, `comparison.wav` | Loudness-matched source first, 0.75-second pause, then radio processing; 20 seconds each by default |
| `comparison-actual-volume.mp3`, `comparison-actual-volume.wav` | Same order and passage at their actual source/output levels |
| `input.wav`, matched WAV pair, numbered intermediates | Preserved extraction and stages for longer review or diagnosis |
| `report.json` | Exact filters, preset/overrides, stage-envelope measurements, loudness/peaks, dependency and source hashes, and listening status |

Use the matched comparison to judge body, presence, and density without most of the volume bias. Use the actual-volume comparison to hear delivery level. Full-file matching does not make every phrase equally loud. Check gate chatter, soft words, breaths, S/SH sounds, pumping, and distortion before accepting a full run. If the agent cannot hear audio, listening approval stays pending. See the [processing reference](skills/that-radio-voice/references/processing.md) for the chain and its limits.

## Video Enhance

[Video Enhance](skills/video-enhance/SKILL.md) provides a preview-first alternative to repeatedly applying enhancement controls in an editor. It uses free local processing engines. It does not claim identical results to CapCut or other proprietary tools; AI reconstruction cannot guarantee recovery of the original detail.

### Install with your agent

```text
Install video-enhance from https://github.com/rovidxmedia/AI-Media-Skills.
Read the README, skills/video-enhance/SKILL.md and its helper scripts.
Install the complete video-enhance folder in the project skill location for
my local agent, following the documented skill-location table. Preserve an
existing installation and explain conflicts before replacing it.

Run the helper's doctor command. Check Python 3.10+, FFmpeg and ffprobe.
Explain missing dependencies and offer compatible setup. Install only selected
AI engines after showing their download requirements, using an isolated cache.
Do not process a full recording during installation.
```

The video skill is independent of the audio skills. Its CPU helper uses only the Python standard library. AI engines are optional downloads and retain their licenses. Media processing is local; the agent host has its own connection and permissions.

### Ask for an enhancement

```text
Use video-enhance on "<full path to my recording>".
Inspect my hardware and sample footage. Recommend relevant repairs and ask me
which enhancement style, resolution, frame rate and processing-time tradeoff
I want. Show a short original/treated comparison and measured render estimate.
Let me review it before processing the whole recording. Preserve my source and
all audio tracks, and put generated files in a new output folder.
```

### Run it directly

From the repository root, using `python3` where appropriate:

```sh
python skills/video-enhance/scripts/video_enhance.py doctor
python skills/video-enhance/scripts/video_enhance.py analyze --input "recording.mkv" --job "runs/video-01"
python skills/video-enhance/scripts/video_enhance.py preview --job "runs/video-01" --engine cpu --style natural --repairs denoise,exposure --gamma 1.12 --height source --fps source --starts 30 --seconds 10
```

Choose an excerpt inside your recording. After reviewing the actual comparison, use `render --job FOLDER --accept-preview SIGNATURE` with the returned preview signature. `resume --job FOLDER` continues an approved interrupted render. Changing settings requires another preview.

Inspect `setup --engine realesrgan` or `setup --engine rife` before adding `--install`. Real-ESRGAN restores live-action detail; RIFE generates intermediate frames. SeedVR2 is a heavier optional reconstruction adapter with an isolated PyTorch environment. See [engine setup](skills/video-enhance/references/engines.md) for package sizes, hardware candidates and model requirements.

`--height 1080 --fps 60 --interpolation rife` requests 1080-high output and neural motion interpolation when that raises the effective frame rate. For fractional footage, choose a rational such as `60000/1001` when appropriate. CPU `--interpolation motion` uses conventional motion estimation. Detected variable-rate footage requires an explicit output rate; HDR requires an explicit color-handling choice.

Jobs contain inspection frames, a muted side-by-side comparison (original left, treated right), an enhanced excerpt with all audio, a review page, settings, benchmark estimates and checkpoints. MKV is the default to preserve audio codecs; MP4 is available for compatible tracks. Review face consistency, texture, text, motion, cuts, crop/borders and lip sync before accepting.

Windows CPU behavior is locally exercised, and macOS/Linux CPU checks have passed in GitHub Actions. Other GPU hardware needs its own successful sample. Consult the [compatibility and validation record](skills/video-enhance/references/validation.md) before relying on a GPU path. [Repair controls](skills/video-enhance/references/repairs.md) explain broader repairs and limits, including stabilization storage, HDR metadata and VFR conversion.

## Contribute a skill

Have a useful, repeatable media workflow? See [CONTRIBUTING.md](CONTRIBUTING.md) for the folder format, evidence expectations, and review checks.

## License and credits

Original repository code and documentation are available under the [MIT License](LICENSE). Bundled third-party material retains its own notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg is installed separately.

## Built by Rovidx

[Rovidx Media & Consulting](https://www.rovidx.com/) builds practical software, automation, and media systems. If your audio workflow needs to connect to a larger publishing operation, explore our [media platforms and publishing workflows](https://www.rovidx.com/services/media-technology-consulting).

Use the skills, adapt them, and keep creating.
