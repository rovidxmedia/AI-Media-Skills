# Commands and metadata

Use the installed helper's absolute path; examples abbreviate it. Python 3.10+ and FFmpeg/ffprobe must be on PATH. `doctor` checks discovery; actual encoding exercises codec availability. Explain any selected system-tool download and license first. No pip install is needed.

```sh
python scripts/packager.py doctor
python scripts/packager.py analyze --input "finished episode.mkv" --job "NEW_JOB" --audio-track 0
python scripts/packager.py package --job "NEW_JOB" --metadata "metadata-input.json" --square "square-layout.png" --wide "wide-layout.png"
python scripts/packager.py resume --job "NEW_JOB"
```

`analyze` hashes the source and records streams/duration and zero-based audio selection. Existing job folders are refused. Agent content review drives copy; the helper validates structure/timing, not factual accuracy. Keep jobs, media and transcripts outside Git.

```json
{
  "title": "A source-grounded title",
  "show_title": "Your show",
  "artist": "Your host",
  "description": "Verified episode summary.",
  "audio_description": "Podcast copy with verified links if available.",
  "video_description": "Video copy with verified links if available.",
  "content_summary": "What was actually discussed; retain supporting notes privately.",
  "tags": ["relevant topic"],
  "alternate_titles": ["Another truthful angle"],
  "chapters": [{"start": 0, "title": "Opening"}]
}
```

Alternate titles and chapters are optional; audio/video descriptions fall back to description. Chapter starts are ordered seconds within the finished source. `chapters.txt` is a timestamped text list, not a guarantee of each platform's chapter eligibility. Chapters are not embedded. The title/artist/show/description are embedded in media; tags are supplied as text/JSON.

Outputs: `cover-square.jpg`, `featured-wide.jpg`, `episode.mp3`, `episode.mp4`, `metadata.json`, `audio-publishing.txt`, `video-publishing.txt`, `chapters.txt`, `report.json`, `review.html`. The MP3 has attached square artwork; MP4 has a separate featured image. No RSS fields are automatically changed.

MP3 is 256 kb/s/48 kHz; MP4 defaults to libx264 CRF18, AAC192 kb/s/48 kHz. Optional `package --video-mode h264-copy` retains an already finished H.264 picture without another lossy video encode. It requires unrotated progressive SDR, yuv420p and square pixels; incompatible sources fail rather than silently convert. Selected-mix AAC encoding, tags, fast start, artwork and MP3 still run. Copy mode verifies unchanged dimensions and exact decoded video frame count; resume retains the saved choice. Prepare a mono/stereo dialogue mix deliberately; export does not master loudness. Only the selected mix is exported; other source tracks remain untouched. The default encode mode uses FFmpeg autorotation and sample-aspect normalization to preserve display shape; inspect unusual orientation/color/VFR in a sample. Audio-only input becomes static 1920×1080/30 video.

SHA-256 checkpoints protect completed outputs. `resume` regenerates interrupted temporary stages but rejects changed completed files, source, settings or artwork. A revised look needs a new job. `.running` prevents concurrent writers: after a hard kill verify the saved process stopped before removing only the stale lock. Storage preflight is conservative. Each encoded media output is decoded and duration checked within 0.2 seconds, and source hash is checked before/after. These checks do not establish listening/artwork quality.
