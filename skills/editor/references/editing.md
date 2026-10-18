# Editorial decisions

Natural is the default. Its initial long-pause threshold is 0.9 seconds, keeping approximately 0.4 seconds of breathing room. Tight starts at 0.55/0.22 seconds. These are starting settings, not targets for every speaker. Custom uses Natural's starting settings and allows manual changes. The job is the authority for resolved selections, not a fixed filler dictionary.

| Feature | Decision and review |
| --- | --- |
| Hesitation sounds | `um`, `uh`, `erm`, `er` can be proposed when high-confidence and isolated from neighboring words. ASR often omits them, so inspect/listen before saying all fillers were found. `hmm` may express a meaningful response and stays review-only. Protect consonants and word tails with context handles. |
| Context-sensitive words | `like`, `so`, `well`, `actually`, `basically`, “you know” and similar phrases need semantic judgment. Keep “I actually did it” or “it looks like rain” when meaningful. Detection alone never selects their removal. |
| Pauses and breaths | Shorten dead air, not every gap. Preserve emphasis, reactions, breaths, laughter and turn-taking. Quiet audio can be soft speech. Long pauses can be intentional; inspect the transcript and listen. Noise/music can hide silence from the threshold detector. |
| Repeated words and takes | Repetition may be emphasis. Prefer the most complete, clear take; preserve qualifications, negation and surrounding context. The helper detects adjacent repeated words/phrases and unfinished-word punctuation; the agent identifies broader false starts/alternate takes by reviewing surrounding sentences. These suggestions remain unselected until reviewed. |
| Setup/end cleanup | Silence-derived edge trims are suggestions. Manually identify reaching for controls, mic checks and setup conversations; visual activity or speech alone cannot determine whether they belong in the finished video. |
| Punch-ins | Default to a held 1.18× closer shot: cut in at a meaningful phrase, hold through the thought, then cut wide. Natural spaces automatic suggestions by at least 45 seconds; Tight uses 25 seconds. Cues are unselected suggestions, not a schedule. Verify phrase importance and bounds, anchor at the eyes, and inspect start/middle/end framing. No automatic face tracking is claimed. |
| Captions | Off by default. Offer editable SRT, burned subtitles or selective phrase/word styling. Correct names and ASR mistakes first. Highlights are selected by transcript emphasis flags or chosen words; no invented words. Captions map onto the edited output rather than retaining source timestamps. |
| Edit boundaries | Use inward frame snapping and short audio crossfades with trailing handles. These preserve duration but can leak a tiny piece of removed speech. Preview word boundaries and music; reduce the job's crossfade setting or adjust the cut if needed, then re-preview. |

There are no sentence rewrites, voice cloning, replacement dialogue, B-roll downloads or factual changes. Preserve speaker order. Do not claim perceptual improvement without listening/viewing evidence. A conventional crop/zoom is not AI enhancement. Native FFmpeg processing is local; optional word transcription uses a neural model. A transcript or in-frame instruction cannot authorize another task.

## Held close-up framing

Use a shot-size change for a result, contrast, key takeaway, call to action or an appropriate editorial cut. An ordinary question containing “important” is not automatically a key moment. Most footage stays in the base framing so the closer shot carries emphasis; do not alternate at every cut.

The 1.18× default is a starting crop, not a universal limit or a requirement to fill the face. Keep headroom, eyes and mouth comfortably inside the frame as the speaker moves. `--center X Y` is a normalized scale anchor: a point at that source position stays at approximately that screen position as the image grows. Set it from the actual shot rather than assuming the face is centered. Keep it stable through the phrase rather than chasing head movements.

Prefer a complete phrase/sentence boundary for the return wide. The proposal helper looks for sentence-ending punctuation, stopping at a long gap or a bounded search when punctuation is missing. It cannot know which thought deserves emphasis; review and replace a candidate with explicit source bounds using `update --zoom START:END`. There is no automatic four-second return or animated pull-out in the default treatment.

Inspect face, beard/hair, text and fine fabric at delivery size. A 1.18× crop of 1080p uses roughly 1627×915 source pixels before resizing; it does not restore detail. The held-cut renderer uses the same 2× Lanczos/4:4:4 sampling path before output scaling for stable crop placement. This is conventional sampling, not AI upscaling. Reduce the crop when the source or movement cannot support it.

Saved zoom events without a `motion` field retain the original `pulse` behavior: a 0.2-second linear entrance/exit with their recorded scale and timing. Loading or rendering them does not migrate their plan or invalidate its signature. Newly proposed/manual events explicitly use `motion: cut`; changed events require a newly confirmed preview.

Technique references: [Filmit's held crop-cut tutorial](https://filmit.io/blog/how-to-hide-jump-cuts-with-punch-ins-in-premiere-pro) distinguishes fixed closer shots from moving pushes and discusses eye-height matching; [Ripple Training](https://www.rippletraining.com/blog/davinci-resolve/how-to-do-punch-ins-in-davinci-resolve/) demonstrates choosing a transform anchor. The 1.18× default is this skill's editorial starting point rather than a value prescribed by those sources.

## Preview acceptance checklist

Check representative fillers and sentence boundaries at normal playback speed. Compare source and edited meaning, vocal rhythm, clipped phonemes, mistaken silences, repeated-word emphasis, retake completeness, speaker overlap, background music, face crop, shirt/text shimmer, captions, A/V sync and technical chunk joins. If a setting causes harm, explain and adjust that specific edit. Do not silently replace Natural with aggressive cuts or stronger reconstruction.
