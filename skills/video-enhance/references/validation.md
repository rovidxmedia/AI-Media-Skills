# Validation and review

Run from the repository root:

```sh
python -m unittest discover -s tests -p "test_video_enhance.py" -v
```

The video tests need only FFmpeg, ffprobe and Python. They generate redistributable synthetic media; GPU downloads are not required. The existing audio tests additionally need their declared dependencies. The GitHub Actions video workflow runs the same CPU tests on Windows, macOS and Linux. A configured workflow does not establish that it has run successfully.

## Compatibility evidence

| Configuration | Evidence |
| --- | --- |
| Windows, Python 3.13, FFmpeg 7.0 | Local CPU integration checks, including preview, full render/resume, audio labels, fractional rate and portrait geometry |
| Windows RTX A4500, NCNN/Vulkan | Real-ESRGAN and RIFE inference passed on private live-action footage, a degraded open movie excerpt, and the opt-in integration fixture |
| macOS CPU | Native Apple Silicon GitHub Actions CPU tests passed with Python 3.12 and Homebrew FFmpeg 9; optional filters depend on the installed build |
| Linux CPU | Native Ubuntu GitHub Actions CPU tests passed with Python 3.12 and distribution FFmpeg |
| AMD/Intel Vulkan, Apple MoltenVK | Upstream candidates; no local GPU inference evidence |
| SeedVR2 CUDA/MPS | No native inference run. Source/CLI contract inspected; memory retry and unavailable-GPU behavior exercised with controlled stubs. Install and sample-test before recommending it. |

## What the checks establish

The helper verifies dimensions, selected frame rate, exact decoded frame count, duration tolerance, complete decoding, audio count/codecs/rates/channels/labels, audio start timing and unchanged source SHA-256. Resume validates chunk hashes and the source/settings/engine signature. It tests allocation-retry selection, missing filters, insufficient disk, unsafe archives, integrity failures, and approval gating.

Technical checks do not establish visual improvement. Review the muted comparison and the all-track enhanced clip. Check mouth/eyes/teeth, skin, hair, hands, printed text, patterns, occlusions, scene cuts, noise trails, flicker, stabilization crop/borders and lip sync. Ten-second preview estimates carry a broad range; initialization and scene complexity affect long renders.

Private source media and generated reports are not distributed. Keep development observations here sanitized: versions, relevant hardware, durations, selected treatments, measured results and known limitations. Never add a private recording path or claim an unexecuted platform test passed.

## Development verification — October 17, 2026

Windows host, Python 3.13.3, FFmpeg 7.0, RTX A4500 with approximately 19 GiB exposed VRAM and 64 GiB system RAM. Pinned archives for all three target operating systems were downloaded and their hashes computed; executing their binaries was tested on Windows only.

- Two ten-second 1920×1080/30 live-action excerpts: conventional denoising, restrained gamma lift and mild sharpening. Each decoded to 300 frames and retained all three AAC tracks. Processing took approximately 28 and 30 seconds, excluding comparison generation. The face was modestly brighter in inspected frames; the dark studio lighting remained. Human motion and lip-sync review remains necessary.
- A one-second 1920×1080 live-action excerpt: natural Real-ESRGAN restoration plus RIFE 30→60, with 60 decoded frames and three audio tracks retained. A first implementation took roughly 391 seconds using per-pair model loading; regular grids now use batched RIFE. This initial number is not a benchmark for the final batch implementation.
- Repeating that live-action benchmark with batched RIFE and a 256-pixel restoration tile took approximately 249 seconds, again producing 60 frames and preserving three audio tracks. This model internally reconstructs 8K frames before resizing to 1080p; a full episode can still take days. Do not recommend this path for a short turnaround without an actual source-specific benchmark.
- Ten-second degraded open-movie excerpt: 320×180/24 to 640×360/48, strong live-action Real-ESRGAN model, denoise/exposure/deblock and RIFE. Four scene/chunk segments produced 480 frames, one retained audio track and no duration drift beyond audio packet padding. Measured processing was approximately 110 seconds; startup and concurrent load limit its value as a general hardware benchmark.
- Generated fixtures exercise actual interlacing, brightness flicker, shake, sharp cuts, VFR, rotation, portrait geometry, fractional rates, multiple/labeled audio tracks, an intentional audio delay, interruption/resume, and stale approval rejection. The opt-in NCNN test also exercises the Windows long-path workspace fallback and batched interpolation.
- A lossless per-frame-color fixture at 30000/1001 verifies that chunked and continuous processing produce identical decoded frame hashes. This guards against a one-frame jump caused by fractional seek offsets at chunk boundaries.

The open-movie test uses **Big Buck Bunny**, (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org, under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). [Official source and license](https://peach.blender.org/about/), [download directory](https://download.blender.org/peach/bigbuckbunny_movies/). The test added grain, darkened/compressed an excerpt, then restored/upscaled/interpolated it. No movie files are bundled here.

To opt in to the installed GPU-engine integration check, set `VIDEO_ENHANCE_TEST_CACHE` to the configured cache directory before running the tests. Leave it unset for ordinary cross-platform CPU CI.

The complete local repository suite passed 32 tests, including the opt-in GPU check. Skill format validation, reference resolution and Git whitespace checks also passed. Human motion/lip-sync review and native SeedVR2 inference remain outstanding validation tasks.
