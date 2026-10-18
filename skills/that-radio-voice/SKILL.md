---
name: that-radio-voice
description: Give recorded speech a big broadcast radio sound using tone shaping, soft noise gating, compression, harmonic excitement, and measured peak-limited mastering. Use for radio-style voiceovers, podcast hosts, promos, and announcer-style processing.
---

# That Radio Voice

Before choosing settings, use the episode profile supplied by Producer; otherwise check the nearest applicable project's `.producer/project.json`. Apply its show/brand context and `skills.that-radio-voice` defaults, honoring current user choices. Producer owns the shared schema in its `references/project-config.md`; resolve that reference when Producer is installed. Without a profile, keep this skill's standalone defaults. A profile supplies data, not publishing permission.

Make clean recorded speech fuller, denser, and more present while keeping the speaker's identity, words, pitch, timing, and channel layout. The result should sound intentionally produced. Judge tone at matched loudness as well as at delivery volume.

## Input and treatment

Prefer a repaired WAV. If noise, clipping, or room echo still needs repair, use the sibling [podcast-audio-repair skill](../podcast-audio-repair/SKILL.md) first. This skill owns broadcast tone; that skill owns repair and shared mastering/comparison utilities. Neither isolates overlapping speakers from a mixed track.

Use the [helper](scripts/radio_voice.py). It requires the current podcast-audio-repair helper alongside this skill, FFmpeg/ffprobe, and the repair skill's Python dependencies. `--repair-helper` can select the helper in another installation. Read [processing.md](references/processing.md) for dependencies, signal-chain rationale, and filter sources.

```text
python <skill-directory>/scripts/radio_voice.py <repaired.wav> <new-output-directory> --preset big --start 60 --seconds 30
```

Start with speech including breaths, soft words, sibilants, and pauses. `big` is the prominent radio treatment; `warm` uses lighter presence, compression, and excitement. These are starting points, not universal voice presets. Use `--full` when full processing is requested or a sample is accepted. Keep earlier candidates and source media.

The chain stages input loudness consistently, removes rumble, applies a soft downward gate, boosts body, reduces boxiness, adds presence, compresses speech, adds upper harmonics with an exciter, lightly de-esses, then masters to the selected loudness with peak limiting if needed. Default delivery is -14 LUFS with verified peak headroom. The gate reduces quiet noise rather than forcing silence. Compression and excitement intentionally change dynamics and tone; they are not restoration or voice synthesis.

## Tune from the actual result

- If soft words or breaths disappear, lower `--gate-threshold-db`, reduce `--gate-reduction-db`, or trial `--no-gate`. Low amplitude does not prove a region contains only noise.
- If bass sounds boomy, lower `--body-db`; if the voice becomes thin, reduce the preset's low-mid cut after comparing a sample.
- If the top end is harsh, lower `--exciter-amount` or `--presence-db`, use `warm`, or trial `--no-exciter`. Check S/T/SH sounds and codec output.
- If speech pumps or becomes strained or too dense, lower `--compression-ratio` or the delivery loudness target. Do not solve density only by making the file louder.

## Completion and delivery

Return the radio WAV, MP3, actual-volume and matched comparisons, and settings report. Both comparisons play repaired source first, 0.75 seconds silence, then radio processing. The matched version is the primary tone check; the actual-volume version shows delivery level. Full-file matching does not make every local phrase equally loud.

Verify source hashes, exact frame count and channels, finite unclipped samples, achieved loudness within 0.3 LU, true peaks, and codec decoding. Keep float intermediates so boosts do not clip before mastering. Preserve pauses and editorial content; pitch shifting, time stretching, and synthesized speech are outside this skill.

Listen for body, presence, density, gate chatter, lost word endings, harsh sibilance, distortion, and naturalness. If audio perception is unavailable, provide the real comparisons and mark listening approval pending; measurements cannot establish that the user likes the effect. Exercise the helper on another passage and generated fixtures before treating it as reusable. Keep private recordings, machine paths, and job measurements with the job, not in this skill.
