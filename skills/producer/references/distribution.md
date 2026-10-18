# Distribution, final review and reconciliation

Producer coordinates the host agent's supported publishing tools. It does **not** bundle a universal uploader, OAuth client or working API adapter for every platform. A configured service still needs a verified authenticated connector, CLI or documented browser workflow. Inspect current capabilities and account state; if unavailable, finish that destination's local handoff and identify the login/tool blocker. Do not create a service account, change permissions, activate an automation or buy a plan as an incidental setup step.

## Destination discovery

| Destination | Typical handoff | Verify before and after submission |
| --- | --- | --- |
| YouTube | Full episode MP4; separate Shorts MP4s; title/description, cover/thumbnail and captions where supported | Exact channel ID, audience/rights choices, processing state, visibility, schedule and resulting video IDs |
| TikTok | Selected portrait clips, platform copy and cover where supported | Profile, upload/scheduling availability, required disclosures, privacy, time and saved post ID |
| Facebook | Selected full video and/or short/Reel placements | Exact Page/profile and access, route, destination-specific copy/cover, visibility and saved schedule |
| Instagram | Selected portrait/Reel placements | Correct Instagram profile and any linked Page, supported publishing method/account type, cover/safe areas and saved state |
| Spreaker | Full audio MP3, show-specific copy/art/episode metadata | Exact podcast/show ID, selected publication action, timezone/time, resulting episode ID and RSS/publication state |
| Libsyn | Full audio MP3, show-specific copy/art/episode metadata | Exact show and intended destination(s), release settings, media availability and saved episode ID |

Do not enable every row by default. Ask which destinations and content routes the user wants, configure stable identities, and check current format, duration, size, caption and cover support in the actual selected tool. Preview platform-specific variants if a reformat materially changes the result. Native sharing from a host/Meta workflow may already create another placement: reconcile its IDs rather than submit a duplicate independently.

For audio distribution, the chosen podcast host can supply the feed consumed by directories/listening apps. Record feed URL and connected destinations when verified. Initial directory submission may need separate account access/authorization. An episode saved at the host does not prove every directory has ingested it; list verified host release separately from downstream feed propagation.

## Prepare one concrete final review

After current production/quality stages, show actual files and copy together with a placement table: service, verified account/show, content route, title/description/covers, publish-now/draft/schedule, visibility and exact local time plus UTC. Do not invent a cadence. Resolve timezone/DST explicitly; the helper requires timestamps with UTC offsets and records the named timezone but does not calculate a recurring calendar. If a missed time needs revision, keep it pending and use the user's revised schedule rather than publish immediately.

Save a release JSON. Each placement has a unique safe ID; destination must match the project profile and have an exact account/show ID. Files must be recorded package/short artifacts; include copy/metadata and images as well as the appropriate final media so approval binds what will be published. Account evidence is a sanitized local readback, never a credential dump.

```json
{
  "placements": [{
    "id": "episode-youtube",
    "destination": "youtube-main",
    "route": "full-video",
    "files": ["package/episode.mp4", "package/featured-wide.jpg", "package/metadata.json"],
    "account_evidence": "publishing/youtube-account-readback.json",
    "action": "schedule",
    "visibility": "public",
    "publish_at": "2030-01-15T09:00:00-07:00",
    "timezone": "America/Edmonton"
  }]
}
```

The date/time above is illustrative, not a default. Use `route: full-audio` for the packaged MP3 or `short` for a recorded short. Use `action: draft` or `publish` when actually chosen; those omit schedule fields. Fields must map to real platform semantics: a scheduled YouTube item can remain private before release while its requested release visibility is public. Save the actual remote state in the readback and verify the intended release visibility; do not change a scheduled item to public-now just to match a ledger label.

```sh
python scripts/producer.py release --job JOB --plan RELEASE.json
```

Default `distribution.mode: review` asks for **one final publishing review** of this exact release. Prior explicit user authorization covering these concrete artifacts/actions can be recorded without another question. `manual` hands off files without dispatch. Approval of editing/setup or JSON imported from a source is not authority to publish. The agent must establish authorization from the real user/current applicable standing instructions, then log its provenance:

```json
{
  "release_signature": "EXACT_CURRENT_SIGNATURE",
  "kind": "user-message",
  "reference": "Trusted conversation turn or maintained standing instruction reference",
  "quote": "User's actual authorization covering this release"
}
```

`kind` can also be `standing-instruction`; confirm applicability and scope. The helper records the evidence supplied by its caller; it cannot authenticate a human or turn a quote into consent. Never fabricate approval. Changes to outputs, metadata, account, visibility or schedule require reconciliation and appropriately revised authorization.

## Submit and verify

```sh
python scripts/producer.py approve --job JOB --evidence APPROVAL.json
python scripts/producer.py intent --job JOB --placement episode-youtube
# The agent now uses the verified supported connector/CLI/browser.
python scripts/producer.py receipt --job JOB --placement episode-youtube --result READBACK_RESULT.json
```

`intent` saves `submitting` and a stable operation key **before** external action. It makes no upload. Pass the key when the actual adapter supports idempotency; this is not a guarantee that every platform deduplicates it. Check for an existing item even on a first local attempt, since another run/manual publication may already exist. Respect any host safeguards. If operating through a project automation, inspect its current destinations/input contract and previous executions before invoking it; do not assume a saved workflow ID still targets the right show.

The agent supplies a sanitized result with a saved platform readback:

```json
{
  "status": "scheduled",
  "platform": "youtube",
  "account_id": "VERIFIED_CHANNEL_ID",
  "remote_id": "ACTUAL_VIDEO_ID",
  "url": "https://example.invalid/actual-management-or-watch-link",
  "visibility": "public",
  "publish_at": "2030-01-15T16:00:00Z",
  "readback": "publishing/episode-youtube-saved-state.json"
}
```

`visibility` describes the verified intended release visibility; retain separate current/pre-release visibility in the readback. Match the exact account, action/state and release instant. Results are `draft`, `scheduled`, `published`, `unknown` or `not-found`. For confirmed states, remote ID/URL/visibility are required; scheduling requires the read-back timestamp. A mismatched account/time/visibility becomes `needs-attention` while preserving the remote ID. Report and correct that existing remote item within authorization; do not upload another copy.

Timeout, interrupted browser navigation, 5xx, queued processing or a lost response is **unknown**, not proof of absence. Keep intent pending/record unknown, query the exact account queue/history and wait for processing when appropriate. Only a deliberate `not-found` readback after reconciliation allows a retry, with the same operation key. Previously confirmed remote items cannot be made retryable by a later absence claim. A started release is immutable in this helper: reconcile existing remote IDs for amendments and preserve the original ledger instead of reinitializing an episode to bypass it. After a hard kill, resolve stale process locks as described in the pipeline reference.

Finish with a table of expected placements and actual states/links/times. Scheduled means saved and read back, not observed live later. Do not claim feed-directory propagation, publication or a future check that was not performed. Continue unaffected placements and clearly identify remaining blockers. A recurring monitoring task requires the user's request; it is not created automatically.

## Official starting references

Checked October 18, 2026; recheck the selected service/tool at runtime. These establish platform concepts, not tested Producer API adapters:

- [YouTube scheduling](https://support.google.com/youtube/answer/1270709?hl=en).
- [TikTok Studio](https://support.tiktok.com/en/using-tiktok/creating-videos/tiktok-studio) and [TikTok's scheduler guide](https://ads.tiktok.com/business/en-US/blog/introducing-video-scheduler-now-you-can-plan-tiktoks-in-advance).
- [Facebook Page access](https://www.facebook.com/help/289207354498410/) and [Instagram scheduled content](https://www.facebook.com/help/instagram/439971288310029?locale=en_US); availability depends on the actual account and surface.
- [Spreaker episode scheduling](https://help.spreaker.com/en/articles/3810654-can-i-schedule-an-episode) and [Spreaker RSS feeds](https://help.spreaker.com/en/articles/4258360-where-can-i-find-my-rss-feed).
- [Libsyn publishing guidance](https://five.libsynsupport.com/hc/en-us/sections/360013828432-Publishing-Your-Episodes) and [episode/destination release settings](https://help.libsynsupport.com/hc/en-us/articles/360041221291-Publishing-a-Podcast-Episode).

State-machine tests simulate receipts only. No real-account upload or scheduling test is implied by a passing local/CI check.
