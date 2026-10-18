# Stacked host and graphics

Prefer this layout for a visible host alongside a screen share, diagram or other relevant graphic. It uses existing source pixels: a large live host fills the upper panel and the graphic occupies the lower panel. For host-only footage, portrait crop is usually more appropriate. Whole-frame fit remains available when separating the picture would lose essential context.

Inspect the source in motion before choosing crops. Keep the face, gestures and meaningful graphic labels visible. Crops are explicit, not automatic tracking. A source layout change can move the host; specify a new speaker shot at that boundary. Choose the graphic's live interval inside its stable presentation, excluding fades. Outside that interval the first/last graphic frames hold; disclose this and avoid holds that imply a changing value or demonstration is live. If one stable panel cannot represent the complete passage honestly, use another composition.

## Candidate interface

Replace a candidate's `framing` object with this synthetic example for a clip from source seconds 10–40:

```json
{
  "mode": "stacked",
  "speaker_shots": [
    {"start": 10, "end": 18, "crop": [0.1, 0, 0.45, 1]},
    {"start": 18, "end": 32, "crop": [0, 0.1, 0.4, 0.8]},
    {"start": 32, "end": 40, "crop": [0.1, 0, 0.45, 1]}
  ],
  "graphic": {
    "start": 19, "end": 31,
    "crop": [0.45, 0.15, 0.55, 0.7],
    "hold_edges": true
  }
}
```

All times are **absolute source seconds**, including nonzero clip starts. Speaker shots must cover the complete clip consecutively, without gaps, overlaps or intervals shorter than a quantized output frame. The graphic live interval must contain at least one output frame inside the clip. This version supports one continuous graphic interval; edge holds are mandatory and recorded in metadata/review.

Each crop is `[x, y, width, height]`, normalized 0–1 against the displayed image **after autorotation and sample-aspect normalization**. Rectangles must stay inside the image and survive even-pixel rounding. Inspect the resolved composition: the host crop fills its panel with a centered aspect-preserving crop; the entire graphic crop fits its panel with small padding if needed. Choose crop aspect ratios close to their panel ratios to use space well. Neither panel stretches faces or diagrams.

## Layout defaults and overrides

Defaults at 1080×1920: host 1080×1000 at the top, graphic 1080×810 beginning at y1024, dark background and thin violet separator. Captions sit on the host's lower chest, above the graphic, with side clearance. Geometry scales with output dimensions and rounds to even pixels.

Optional fields on `framing`, all fractions of output height:

| Field | Default | Meaning |
| --- | --- | --- |
| `speaker_height` | `0.5208333333333334` | Upper panel height |
| `graphic_y` | `0.5333333333333333` | Lower panel top |
| `graphic_height` | `0.421875` | Lower panel height |
| `caption_bottom` | `0.5104166666666666` | ASS bottom margin, placing the text above the lower panel |

Panels cannot overlap or extend outside the frame. Caption bottom margin must put the baseline inside the host panel; inspect two-line captions, long words and the face in actual playback. Modify the plan in a new job when layout or source bounds change. Existing crop/fit jobs retain their previous layout and signatures.

## Timing, recovery and review

Shot/live bounds are rounded to the nearest nominal-source-CFR frame using the saved rational rate. Picture is explicitly encoded at that rate with exactly `round(clip_duration × fps)` frames. Finite canvas, repeated overlay EOF and final frame padding/trim prevent a missing last frame. Audio is encoded independently for the complete selected source interval, then copied into clean and captioned MP4s; a picture frame limit must never cut off audio packets. Receipts verify frame count, packet identity and audio start/duration against the AAC checkpoint. Speech is never synthesized or rearranged by framing.

`picture.mp4` and `audio.m4a` are independent resumable stages; completed hashes are checked before reuse. Delivered clean/captioned MP4s undergo full decode and geometry/rate/duration/channel checks. Additional `boundary-N-before.jpg` and `boundary-N-after.jpg` images show both sides of speaker and graphic interval boundaries. Review those images **and playback**, especially face continuity, graphic readability, held-frame transitions, captions and lip sync. Automated verification cannot judge those qualities.
