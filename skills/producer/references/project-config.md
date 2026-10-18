# First-run setup and shared configuration

Producer owns this configuration. Specialist skills read their relevant fields; their own references remain authoritative for processing parameters and tool setup. A profile supplies preferences, not executable commands or external-action permission. Explicit user choices govern. Prefer a running episode's saved profile over a newly changed project default.

## Onboard once per project

1. Look for a project-designated profile or `.producer/project.json` in the project/nearest applicable ancestor. Avoid choosing a neighboring show's profile merely because a source lives nearby. Look for an existing manifest and show workflow before creating a new one.
2. Run `producer.py doctor --project PROJECT` to inspect OS, CPU/cores, accessible RAM/GPU inventory, storage, Python, FFmpeg/ffprobe and the six sibling skills. Use repeated `--skills-root` for installations in different locations. Inspect model/runtime inventories through the chosen specialists. GPU inventory is not successful inference. No dependencies, models, sign-ins or publisher changes occur during this check.
3. Ask in a single manageable exchange for missing show name/description, host(s), podcast/YouTube/both, language, audience, brand assets/voice and deliverables. An intentionally anonymous show can use `hosts: []`. Do not invent names or branding. Reuse applicable maintained resources instead of copying another show's details.
4. Recommend Natural editing, source size/rate unless upgrades are selected, optional repair only when needed, natural voice unless a broadcast treatment is requested, and about three complete shorts. Determine whether the project also needs graphics, transcript documents or other deliverables. Record such requirements in `show`/`brand` and follow the selected project's workflow; these optional capabilities are not bundled engines.
5. Ask which services/accounts should receive full video, audio and shorts. First-class guidance covers YouTube, TikTok, Facebook, Instagram, Spreaker and Libsyn. Store stable channel/Page/profile/show IDs when verified; an unset account can remain `null` until connected. For podcast directories, distinguish hosting the episode from subscribing to its RSS feed. Ask for publish-now versus schedule, timezone and cadence without imposing another user's calendar. Default publishing mode is `review`: one final publishing review before distribution. `manual` produces a handoff instead.
6. Write the selected JSON outside the skill and run `setup --project PROJECT --config CHOICES.json`. The helper creates `.producer/project.json`, an ignore file and `.producer/machines/<machine-id>.json`. It preserves an existing profile unless `--update` is explicitly selected; updates archive the prior profile. Explain missing dependencies/downloads and install only the chosen specialist requirements into appropriate caches/environments. Setup does not upload an episode or grant publication permission.

## Portable profile example

This is a synthetic starting example, not a ready publishing account. The helper fills omitted specialist defaults. Store no passwords, tokens, API keys or cookies here; use supported connector/browser/CLI authentication.

```json
{
  "schema": 1,
  "show": {
    "name": "Example Show",
    "description": "Practical conversations about the show's actual subject.",
    "hosts": ["Example Host"],
    "format": "both",
    "language": "en",
    "audience": "The audience chosen during setup"
  },
  "brand": {
    "assets": ["brand/logo.png", "brand/show-art.jpg"],
    "voice": "Clear and conversational",
    "links": []
  },
  "paths": {"output": "production"},
  "skills": {
    "editor": {"style": "natural", "captions": "off"},
    "video-enhance": {"enabled": "if-needed", "style": "natural", "resolution": "source", "fps": "source"},
    "podcast-audio-repair": {"enabled": "if-needed"},
    "that-radio-voice": {"enabled": false},
    "podcast-packager": {},
    "short-form-clips": {"count": 3, "width": 1080, "height": 1920, "captions": "burn", "framing": "content-aware"}
  },
  "distribution": {
    "mode": "review",
    "timezone": null,
    "cadence": null,
    "destinations": [
      {"id": "youtube-main", "platform": "youtube", "account_id": null, "label": "Chosen channel", "routes": ["full-video", "short"]},
      {"id": "podcast-host", "platform": "spreaker", "account_id": null, "label": "Chosen show", "routes": ["full-audio"]},
      {"id": "tiktok", "platform": "tiktok", "account_id": null, "routes": ["short"]},
      {"id": "facebook", "platform": "facebook", "account_id": null, "routes": ["full-video", "short"]},
      {"id": "instagram", "platform": "instagram", "account_id": null, "routes": ["short"]}
    ]
  }
}
```

Use `libsyn` instead of `spreaker` when that is the selected host, or explicit distinct destinations if the user intentionally uses both. Other platform names can be configured, but require a verified supported publishing method. A destination entry is a request, not proof that an upload integration exists.

## Settings ownership and reuse

`show` owns identity/content/audience; `brand` points to maintained assets and voice/link choices; relative asset/output paths resolve from the project root. `skills[skill-name]` owns relevant defaults. Values such as `if-needed`, `content-aware` and `resolution: source` express decisions for the agent to resolve using that specialist's diagnosis/interface; do not pass them blindly as CLI flags. Keep specialist-specific additional options with that skill's object and verify they exist before applying them.

On each specialist invocation: use the Producer job's saved profile if supplied, otherwise the nearest applicable project profile, apply only relevant preferences, and honor current user overrides. If Producer is not installed, a specialist can still read the structured defaults and run independently; no shared runtime import is required. A missing profile preserves the specialist's existing standalone behavior.

`init` snapshots the validated profile into the episode manifest. `--overrides FILE` merges per-episode `skills` objects without changing project defaults. Setup updates affect subsequent episodes. To change a running episode's creative settings, use the specialist's revised plan/preview and record the replacement stage; do not silently rewrite an accepted result to match a later profile. A changed number of selected shorts can be recorded with `selected_count` and the trusted user decision reference.

Computer-specific absolute paths, GPU inventory, tool versions and test results belong in `.producer/machines/` or external caches, not the portable profile. Recheck the machine on a new host or material tool/hardware change and save the new inventory there. Prefer an existing verified cache; successful GPU trials remain engine/version-specific. Keep private project data, jobs and large media/models out of the public skill repository. The generated ignore file protects new Producer data; it does not untrack files someone already committed.
