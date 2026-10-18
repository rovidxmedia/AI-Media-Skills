# Repair selection and processing

The helper offers selected treatments, rather than applying every filter. Use ordinary live-action models for camera footage. Preserve faces, text and intentional studio lighting; no face-specific reconstruction is enabled.

| Problem | Treatment | Controls and review |
| --- | --- | --- |
| Grain/noise | `denoise` | Conservative temporal/spatial hqdn3d in natural mode; stronger in strong mode. Watch for smeared texture and motion trails. |
| Dark or flat image | `exposure` | Start with `--gamma 1.08`–`1.15`. `--exposure` is a bounded brightness control (-2..2, mapped to FFmpeg brightness at 0.05 per unit), **not photographic exposure stops**. Inspect highlights and black levels. |
| Color cast | `color` | `--red`, `--green`, `--blue` adjust midtones in -0.3..0.3, initially zero. Preserve intentional colored lighting. |
| Soft edges | `sharpen` / AI restoration | Mild unsharp at final size; AI may invent detail. Lost focus/motion detail cannot be reliably recovered. |
| Compression blocks / bands | `deblock`, `deband` | Optional weak filters; inspect skin, gradients and text. |
| Handheld shake | `stabilize` | Whole-shot two-pass vidstab. `--stabilize-zoom` sets a fixed 0..10 percent zoom; inspect remaining black borders/crop. Intentional pans may be altered. |
| Brightness flicker | `deflicker` | Five-frame luminance smoothing, reset at detected cuts. Flashes, strobes and intentional exposure changes may be altered. Rolling-shutter LED bands require specialized treatment; no universal fix is promised. |
| Combed interlaced motion | `deinterlace` | bwdif with confirmed TFF/BFF. Produces one frame per field to preserve motion; the effective rate may already be 50/59.94/60. Do not interpolate again unnecessarily. |
| Higher resolution | `--height` | Retain aspect ratio, normalize non-square pixels, handle display rotation. NCNN reconstructs at x4 internally then resizes. Increased dimensions do not prove increased detail. |
| Smoother motion | `--fps`, `--interpolation` | RIFE is neural; `motion` uses conventional motion estimation. Avoid excessive frame-rate increases; review hands, mouth, occlusions and cuts. |

## Output upgrade choices

Offer size and motion upgrades during treatment confirmation, even when cleanup alone is recommended. Include a keep-source option and honor any output choices already supplied. The helper reports candidates in `analyze`'s `output_options` and saves them under `analysis` in the job; they are suggestions, not selected settings or evidence that an engine has passed a benchmark.

| Source | Offer |
| --- | --- |
| 720p (1280×720) | Keep 720p, 1080p (1920×1080), or 4K UHD (3840×2160) |
| 1080p or 1440p | Keep source or upscale within 4K UHD bounds |
| Below 720p | Keep source, 720p, 1080p, or 4K, with realistic detail-recovery limits |
| 4K or larger | Keep source; discuss custom higher dimensions only if requested and supported |
| 24 fps | Keep 24, interpolate to 30, or interpolate to 60 fps |
| 25 or 30 fps | Keep source or offer higher 30/60 targets, excluding rates already reached |
| 50 fps | Keep 50 or interpolate to 60 fps |
| 60 fps or higher | Keep source; do not present a lower rate as an upgrade |

Preserve aspect ratio and orientation. For portrait 720×1280, the corresponding choices are 1080×1920 and 2160×3840; pass `--height 1920` or `--height 3840`, not the landscape heights. Square and ultrawide recordings fit inside the selected delivery bounds without stretching/cropping; display their actual dimensions rather than claiming an exact 16:9 size. UHD here means 3840×2160, not DCI 4096×2160.

For common fractional rates, offer matching-family targets (24000/1001 → 30000/1001 or 60000/1001; 30000/1001 → 60000/1001), labeling them 23.976/29.97/59.94 as appropriate. Exact 30 or 60 remains a user-selectable alternative; record the exact rational rate. For interlaced material, account for bwdif's effective field rate before offering interpolation. For VFR, keeping the nominal rate still means the helper's explicit CFR normalization; explain it before confirmation.

Explain spatial upscaling separately from motion interpolation: CPU scaling enlarges the image conventionally, while optional AI restoration reconstructs detail and may invent it. Higher frame rates use RIFE AI or FFmpeg conventional interpolation; repeated frames do not add smoothness. Both can produce artifacts and increase processing/storage needs. Preview the selected size and rate, measure the actual cost, and compare fine detail at full resolution because the small side-by-side display can hide upscaling artifacts. Do not promise that a larger output is automatically better.

## Order and timing

Detect shot boundaries first. Deinterlace and explicitly handle HDR, normalize sample aspect ratio, stabilize, deflicker/deblock/denoise/deband, adjust selected exposure/color, restore detail, resize, and interpolate. Sharpen at delivery size. Each shot is processed independently so temporal filters do not bridge a detected cut. Cut detection is heuristic; inspect missed fades/cuts and adjust the material or process shorter ranges if necessary.

AI stages use bounded chunks with up to two seconds of neighboring context. Chunk boundaries share a global rational output-frame grid. RIFE uses decoded frame timestamps and arbitrary interpolation timesteps, not a mean-rate assumption. SeedVR2 requires explicit CFR normalization before its upstream OpenCV decoder. The final output is CFR; for detected VFR input, require the user's explicit numeric rate selection. Sparse analysis may miss rare variable intervals; inspect timing when in doubt.

Stabilization computes one transform analysis and one stabilized lossless staging file for the complete shot, so its camera path does not reset per AI chunk. This needs additional disk space proportional to the longest shot. The runner preflights that space; lengthy fixed-camera shots usually need no stabilization. Processing retains bounded RAM, but disk use can be substantial.

HDR-preserve mode uses the CPU path and 10-bit HEVC output, retaining known primaries, transfer, matrix and range. SDR-only engines require explicit HDR-to-SDR tone mapping. Dynamic HDR metadata, Dolby Vision, HDR10+ and mastering-display side data are not preserved by this implementation; explain this before proceeding and retain the source. Do not call the CPU path an HDR archival master.

Audio comes from the source and is packet-copied, retaining every track, codec, sample rate, channel count, title and language. Preview extraction may have sub-packet boundary differences. Check lip sync visually. Subtitles, attachments and chapters are not copied into the enhanced file in v1; the source remains available.

## Limits

This is image/video enhancement, not generative editing. It does not replace faces, objects or backgrounds, repair missing/corrupt frames, undo severe rolling shutter, or guarantee recovery of unreadable text. Telecine and mixed cadence need a dedicated cadence decision rather than automatic deinterlacing. Use a separate audio skill for sound repair.
