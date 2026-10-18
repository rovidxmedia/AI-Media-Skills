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

## Order and timing

Detect shot boundaries first. Deinterlace and explicitly handle HDR, normalize sample aspect ratio, stabilize, deflicker/deblock/denoise/deband, adjust selected exposure/color, restore detail, resize, and interpolate. Sharpen at delivery size. Each shot is processed independently so temporal filters do not bridge a detected cut. Cut detection is heuristic; inspect missed fades/cuts and adjust the material or process shorter ranges if necessary.

AI stages use bounded chunks with up to two seconds of neighboring context. Chunk boundaries share a global rational output-frame grid. RIFE uses decoded frame timestamps and arbitrary interpolation timesteps, not a mean-rate assumption. SeedVR2 requires explicit CFR normalization before its upstream OpenCV decoder. The final output is CFR; for detected VFR input, require the user's explicit numeric rate selection. Sparse analysis may miss rare variable intervals; inspect timing when in doubt.

Stabilization computes one transform analysis and one stabilized lossless staging file for the complete shot, so its camera path does not reset per AI chunk. This needs additional disk space proportional to the longest shot. The runner preflights that space; lengthy fixed-camera shots usually need no stabilization. Processing retains bounded RAM, but disk use can be substantial.

HDR-preserve mode uses the CPU path and 10-bit HEVC output, retaining known primaries, transfer, matrix and range. SDR-only engines require explicit HDR-to-SDR tone mapping. Dynamic HDR metadata, Dolby Vision, HDR10+ and mastering-display side data are not preserved by this implementation; explain this before proceeding and retain the source. Do not call the CPU path an HDR archival master.

Audio comes from the source and is packet-copied, retaining every track, codec, sample rate, channel count, title and language. Preview extraction may have sub-packet boundary differences. Check lip sync visually. Subtitles, attachments and chapters are not copied into the enhanced file in v1; the source remains available.

## Limits

This is image/video enhancement, not generative editing. It does not replace faces, objects or backgrounds, repair missing/corrupt frames, undo severe rolling shutter, or guarantee recovery of unreadable text. Telecine and mixed cadence need a dedicated cadence decision rather than automatic deinterlacing. Use a separate audio skill for sound repair.
