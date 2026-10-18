# Compatibility and limits

Core: standard-library Python 3.10+, FFmpeg/ffprobe with libx264/AAC. Burned captions need libass/subtitles and an installed font. No GPU, API key or model is needed for timed imports. Windows/macOS/Linux are targets with generated-fixture CI; distinguish actual run outcomes from configured coverage. Optional transcription follows Editor's separately maintained ASR setup and needs recognition review.

On macOS, the standard Homebrew `ffmpeg` build observed in CI omitted libass. Use [ffmpeg-full](https://formulae.brew.sh/formula/ffmpeg-full) for burned captions and put its `bin` directory first on PATH (the formula is keg-only). Installing the standalone libass library does not add a missing compiled FFmpeg filter. Run `doctor` and an actual captioned sample against the selected executable. CI explicitly selects the full build rather than skipping caption tests.

The helper has no automatic semantic scoring, face tracking, speaker switching, voice synthesis, background music or publishing. The agent selects moments from verified transcript/video context. Static crop and whole-frame fit are the implemented layouts.

Tests exercise source/transcript/candidate validation, unsafe IDs, crop/fit, portrait output, captions, fractional rates, multiple source audio streams, interrupted recovery, storage failures and output tampering. They establish technical behavior, not strong hooks, accurate speech comprehension or human lip sync. Versions are recorded in each private receipt. Keep source/transcripts/models and publication assets outside Git.
