# Compatibility and validation

Core: Python 3.10+ standard library, FFmpeg/ffprobe with libx264/libmp3lame/AAC. No GPU. Windows, macOS and Linux are design targets with a synthetic publishing CI matrix; distinguish configured jobs from actual successful runs. Image generation depends on the host or a separately selected engine. The helper makes no network calls. Optional transcription uses Editor's separately maintained setup.

Tests generate a multitrack video and audio-only source. They check source preservation, image geometry, MP3 attached cover, selected mix, MP4 decoding/duration, invalid metadata, Unicode/spaces, storage failure and resume/tampering. Fixtures establish technical execution, not aesthetic quality, speech clarity or long-episode lip sync. Review actual publication assets before use. Job reports record the FFmpeg version; private media, transcripts and publication assets stay outside Git.

Optional H.264 copy export also checks decoded frame counts, dimensions and selected audio. Generated-fixture tests compare every decoded picture hash with the source and reject video requiring rotation, HDR, interlace, pixel-format or sample-aspect conversion. Copy export still needs FFmpeg and no GPU.
