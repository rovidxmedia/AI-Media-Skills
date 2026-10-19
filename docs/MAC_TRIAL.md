# Mac trial with a fictional show

Use a new project and your own short recording. This trial does not publish or connect social accounts. Start with local CPU processing; Apple Silicon does not require NVIDIA, CUDA, Pinokio or a cloud media subscription.

## Download and tools

Download with GitHub's Code > Download ZIP and extract it, or clone the repository. Open Terminal in that folder. Use an agent session with local file/terminal access.

Install Python and FFmpeg if missing. With an existing Homebrew installation:

```sh
brew install python@3.13 ffmpeg-full
export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"
python3.13 --version
ffmpeg -version
ffprobe -version
```

The full FFmpeg formula is keg-only and includes libass for captions. The Terminal/agent running the helpers needs that PATH setting; an already-open desktop app does not automatically inherit it. Ask the agent to verify its environment or start it from that Terminal. Do not overwrite global shell configuration just for this trial.

Python 3.13 is tested with the pinned audio packages. Core helpers need Python 3.10+; the pinned audio packages may not have wheels for newer Python versions.

Sources: [Homebrew Python](https://formulae.brew.sh/formula/python@3.13), [FFmpeg full](https://formulae.brew.sh/formula/ffmpeg-full), [Codex skill locations](https://developers.openai.com/codex/skills/).

## Install the pack

Run from the downloaded repository:

```sh
SHOW="$HOME/Podcasts/Lantern Workshop"
mkdir -p "$SHOW"
python3.13 scripts/install.py --agent codex --project "$SHOW" --dry-run
python3.13 scripts/install.py --agent codex --project "$SHOW"
python3.13 -m venv "$SHOW/.venv"
"$SHOW/.venv/bin/python" -m pip install -r skills/podcast-audio-repair/requirements.txt
```

These are real copies, not links to another machine. A differing existing installation is preserved. Use `--agent claude` for Claude Code (and change the installed helper paths below from `.agents` to `.claude`); other hosts can use the README table or `--skills-dir`.

## Configure the fictional show

Still in the repository:

```sh
"$SHOW/.venv/bin/python" "$SHOW/.agents/skills/producer/scripts/producer.py" setup   --project "$SHOW" --config examples/fictional-show.json
"$SHOW/.venv/bin/python" "$SHOW/.agents/skills/producer/scripts/producer.py" doctor --project "$SHOW"
```

The example uses Lantern Workshop, hosted by Morgan Vale. It has no destinations or release schedule; publishing is manual and shorts/graphics are off for the first trial. Change its identity/preferences before setup if desired. A later show should have its own project.

Open the show project in your agent and ask it to locate Producer and its specialists. Restart the session if discovery has not refreshed; copied files do not prove native discovery. Private preferences and machine reports stay in `.producer/`. Do not commit them or recordings to the skill repository.

## Make a test recording and produce it

Record a two-to-five-minute test video with natural pauses and a brief retake. Put it in an `inputs/` folder in the show project. Paste:

```text
Use Producer for my Lantern Workshop project.
Read the installed skills and existing .producer/project.json.
Use this recording: <path to my test recording>.
Use the project's .venv Python and verify FFmpeg/ffprobe in your environment.

Production only: no uploads, publishing, scheduling, account connections or paid generation.
Use Natural editing, preserve my source and meaning, and diagnose before repairs.
Keep source resolution/cadence and use CPU processing for this trial.
No radio voice, AI upscaling, graphics or shorts unless I ask later.
Show the proposed edit and an actual preview before the full render.

Create the matched full video and podcast audio, truthful publishing copy,
finished transcript and separately composed square/wide artwork.
Use available image tools or supplied art; explain missing capabilities.
Use this project's fictional identity, not another show's branding.
Deliver clickable files, verification results and unresolved review gaps.
```

## Evaluate the result

- The chosen fictional identity is used consistently.
- Existing setup is reused; unrelated skills and publishing are not triggered.
- The actual preview, final video and audio play with the same spoken edit and synchronized sound.
- Pacing is natural; captions/chapters match the finished timeline.
- Source and editable files are preserved in the test project.
- A later direct specialist request works without restarting Producer onboarding.

If a required model/tool/provider is unavailable, completed independent work and a precise blocker are useful progress, not a completed production. For a bug report include the host, macOS/processor and Python/FFmpeg versions, failed command and sanitized error. Keep personal paths, media and full job reports private.

CI tests installation and generated fixtures. It does not establish native skill discovery in every app, a good spoken edit, or actual listening/motion acceptance on your Mac.
