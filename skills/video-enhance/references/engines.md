# Engine setup and compatibility

The Python runner uses the standard library. Python 3.10+ and separately installed FFmpeg/ffprobe are sufficient for conventional processing. Engine availability is determined by a successful preview, not by hardware marketing names.

## Tiers

| Engine | Hardware candidates | Behavior |
| --- | --- | --- |
| CPU / FFmpeg | Windows, macOS, Linux | Denoise, lighting/color correction, sharpening, weak deblocking/debanding, optional interlace/flicker/stabilization repair and conventional motion interpolation. No AI claim. |
| Real-ESRGAN NCNN | Compatible NVIDIA/AMD/Intel Vulkan GPU; macOS via compatible upstream MoltenVK build | Live-action `realesrgan-x4plus`, tiled. Natural blends 35% restored image with 65% prepared original at output size; strong uses full restoration. Neither is face-specific. Individual-frame restoration may shimmer. |
| RIFE NCNN | Compatible Vulkan/MoltenVK runtime | Pinned RIFE v4.6 model. Regular frame grids use one batch process per chunk; irregular timestamps use explicit per-pair timesteps, which can be slower. |
| SeedVR2 | Compatible CUDA or Apple MPS, sufficient GPU/system memory | Optional stronger temporal restoration. FP16 3B default; 7B is opt-in. VAE tiling/offload, fixed seed, batches of at least five frames. CUDA uses BlockSwap; MPS disables it. |

There is no fixed universal VRAM cutoff. Resolution, model, frame batch, tiling, available RAM and other running applications all matter. The doctor reports NVIDIA VRAM when nvidia-smi works and system RAM when obtainable; unavailable inventory is recorded as unknown. AMD/Intel/MPS support must be tested rather than inferred. The selected backend's own errors guide compatibility checks.

## Setup

Run `doctor` and `setup --engine NAME --cache CACHE` to inspect before installation. The setup plan gives the pinned source, exact archive size, disk budget and license note. FFmpeg is not bundled: offer normal platform installation (Windows package manager/official build, Homebrew on macOS, distribution packages on Linux), with the user's permission for system changes. Check actual filter availability, especially `vidstabdetect`/`vidstabtransform`, before offering that repair.

```sh
python scripts/video_enhance.py setup --engine realesrgan --cache "CACHE"
python scripts/video_enhance.py setup --engine realesrgan --cache "CACHE" --install
python scripts/video_enhance.py setup --engine rife --cache "CACHE" --install
```

Paths above are relative to the installed skill directory. Cached artifacts and environments never belong inside the skill folder. Installation validates the SHA-256 values in [engines.json](engines.json), rejects unsafe archive members, retains upstream notices, and writes a local installation receipt. NCNN downloads are about 45–52 MB for restoration and 431–437 MB for interpolation. Source archives are pinned by version; the hashes were computed from official release artifacts. Hashes establish artifact identity, not independent provenance certification.

On Windows/Linux the pinned NCNN executables target x86-64. macOS architecture/runtime support depends on the upstream archive; a successful sample is required, especially on Apple Silicon. Unsupported architectures retain the CPU option. No global PATH edits are performed.

Legacy Windows NCNN binaries can reject long directory paths. The runner stages those frames in a short temporary workspace under the selected cache, checking cache storage first and cleaning it afterward. Choose a short, spacious cache path if its own path is unusually long. The original recording is never moved or changed.

For SeedVR2 use Python 3.12 or 3.13, a compatible driver and a new isolated environment:

```sh
python scripts/video_enhance.py setup --engine seedvr2 --torch-backend cuda128 --cache "CACHE"
python scripts/video_enhance.py setup --engine seedvr2 --torch-backend cuda128 --cache "CACHE" --install
# On compatible Apple hardware choose --torch-backend mps instead.
```

This installs a pinned integration commit, PyTorch 2.10.0/torchvision 0.25.0 and the commit's requirements. Remaining dependencies are resolved at setup time and recorded with `pip freeze`; they are not a fully locked environment. Upstream automatically downloads selected model/VAE weights on the first preview with its own integrity verification. Allow roughly 25 GiB initially and explain the several-GiB model download before first use. A successful install is not a successful GPU inference check. Do not automatically try diffusion on CPU for a full recording.

The adapter checks the isolated PyTorch environment's selected CUDA/MPS backend before inference. If first use downloaded weights, repeat a short preview with cached weights before using its runtime as a full-render estimate; one-time download time is not representative processing speed.

Only allocation failures trigger memory retries. NCNN tiles reduce to 32; SeedVR2 temporal batches reduce to five, never one. Other failures stop with the relevant log. If the selected result still cannot fit, propose a different engine/output and generate a new preview. Completed chunks retain actual model and retry details.

## Maintained source contract

- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)
- [Real-ESRGAN NCNN](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan), using the model-inclusive [20220424 release package](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0)
- [RIFE NCNN 20221029](https://github.com/nihui/rife-ncnn-vulkan/releases/tag/20221029)
- [SeedVR2 integration at the pinned commit](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler/tree/4490bd1f482e026674543386bb2a4d176da245b9)

Read [validation.md](validation.md) for actual tested configurations. Verify updated artifacts and exercise the adapter before changing a pin.
