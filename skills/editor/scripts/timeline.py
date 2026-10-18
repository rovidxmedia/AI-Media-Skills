"""Deterministic proposal, frame-grid edits and caption mapping for Editor."""
from fractions import Fraction
import hashlib
import html
import json
import math
import re

STYLES = {
    "natural": {"pause_threshold": 0.9, "pause_keep": 0.4, "word_guard": 0.08,
                "filler_confidence": 0.85, "zoom_scale": 1.08, "zoom_spacing": 45.0},
    "tight": {"pause_threshold": 0.55, "pause_keep": 0.22, "word_guard": 0.06,
              "filler_confidence": 0.8, "zoom_scale": 1.12, "zoom_spacing": 25.0},
}


def number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Times and settings must be finite")
    return value


def normalized(text):
    return re.sub(r"[^\w']", "", text.casefold())


def intersect_ranges(left, right):
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if b > a:
            result.append([a, b])
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return result


def validate_words(data, source_hash, scope):
    if data.get("source_sha256") != source_hash:
        raise ValueError("Transcript must identify this source SHA-256; do not reuse another recording's transcript")
    a, b = scope
    coverage = data.get("coverage", [])
    if len(coverage) != 2 or number(coverage[0]) > a + 0.05 or number(coverage[1]) < b - 0.05:
        raise ValueError("Transcript coverage must include the entire analysis scope")
    words, last = [], a
    for raw in data.get("words", []):
        start, end = number(raw["start"]), number(raw["end"])
        probability = number(raw.get("probability", 0))
        if start < a - 0.05 or end > b + 0.05 or start < last - 0.001 or end <= start or not 0 <= probability <= 1:
            raise ValueError("Invalid, overlapping or out-of-scope word timestamps")
        if not isinstance(raw["word"], str) or not raw["word"].strip():
            raise ValueError("Transcript words must contain text")
        words.append({"start": max(a, start), "end": min(b, end), "word": raw["word"].strip(),
                      "probability": probability, "emphasis": bool(raw.get("emphasis", False))})
        last = end
    return words


def propose(words, silences, scope, style="natural"):
    settings = dict(STYLES["natural" if style == "custom" else style])
    cuts, zooms = [], []
    def add(a, b, kind, reason, selected):
        if b - a >= 0.04:
            cuts.append({"id": f"cut-{len(cuts)+1:04d}", "start": a, "end": b,
                         "kind": kind, "reason": reason, "selected": selected})
    guard = settings["word_guard"]
    for a, b in silences:
        a, b = max(a, scope[0]), min(b, scope[1])
        if b - a < settings["pause_threshold"]:
            continue
        edge = a <= scope[0] + 0.02 or b >= scope[1] - 0.02
        keep = 0.2 if edge else settings["pause_keep"]
        left = a if a <= scope[0] + 0.02 else a + keep / 2
        right = b if b >= scope[1] - 0.02 else b - keep / 2
        collision = (left <= scope[0] and right >= scope[1]) or any(w["start"] - guard < right and w["end"] + guard > left for w in words)
        add(left, right, "edge" if edge else "pause", "Quiet interval; verify it is not quiet speech or an intentional pause",
            not collision)
    for i, word in enumerate(words):
        token = normalized(word["word"])
        if token in {"um", "uh", "erm", "er", "hmm"}:
            left = max(scope[0], word["start"] - 0.025, words[i-1]["end"] + guard if i else scope[0])
            right = min(scope[1], word["end"] + 0.025, words[i+1]["start"] - guard if i+1 < len(words) else scope[1])
            clear = left <= word["start"] and right >= word["end"] and word["probability"] >= settings["filler_confidence"]
            # "hmm" may be an intentional response, even with confident transcription.
            add(left, right, "filler", f"Possible hesitation: {word['word']}; listen before accepting", clear and token != "hmm")
        elif token in {"like", "actually", "basically", "so", "well", "youknow"}:
            add(word["start"], word["end"], "context", f"Context-sensitive word: {word['word']}; preserve meaning", False)
        if i + 1 < len(words) and token and token == normalized(words[i+1]["word"]) and words[i+1]["start"] - word["end"] < 0.7:
            add(word["start"], min(words[i+1]["start"] - guard, word["end"]), "repeat", "Repeated word; may be intentional emphasis", False)
        if word["word"].endswith(("-", "—")):
            add(word["start"], word["end"], "false_start", "Possible abandoned word/sentence; inspect surrounding take", False)
        for length in (8, 6, 4, 3):
            if i + 2 * length > len(words):
                continue
            first = [normalized(w["word"]) for w in words[i:i+length]]
            second = [normalized(w["word"]) for w in words[i+length:i+2*length]]
            if first == second and words[i+length]["start"] - words[i+length-1]["end"] < 3:
                add(word["start"], words[i+length]["start"] - guard, "retake", "Repeated phrase; select the complete preferred take after review", False)
                break
        cue = word["emphasis"] or token in {"important", "remember", "crucial"}
        if cue and (not zooms or word["start"] - zooms[-1]["start"] >= settings["zoom_spacing"]):
            zooms.append({"id": f"zoom-{len(zooms)+1:04d}", "start": max(scope[0], word["start"] - 0.2),
                          "end": min(scope[1], word["start"] + 4), "scale": settings["zoom_scale"],
                          "center_x": 0.5, "center_y": 0.4, "selected": True,
                          "reason": "Possible emphasis phrase; agent must verify meaning and framing"})
    return {"style": style, "settings": settings, "cuts": cuts, "zooms": zooms,
            "captions": "off", "highlight_words": [], "crossfade_ms": 8,
            "audio_cleanup": "off", "container": "mkv", "chunk_seconds": 20}


def signature(job):
    fields = {k: job[k] for k in ("schema_version", "source", "scope", "media", "words", "plan")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_plan(job):
    plan, scope = job["plan"], job["scope"]
    if plan["style"] not in ("natural", "tight", "custom") or plan["captions"] not in ("off", "srt", "burn", "highlight"):
        raise ValueError("Invalid style or caption mode")
    if plan["container"] != "mkv":
        raise ValueError("The main edited output is MKV; use the separate browser MP4 for playback")
    if plan.get("audio_cleanup", "off") != "off":
        raise ValueError("Use the documented companion workflow for optional audio repair")
    if not 0 <= number(plan["crossfade_ms"]) <= 20 or not 1 <= number(plan["chunk_seconds"]) <= 60:
        raise ValueError("Crossfade must be 0–20 ms and chunks 1–60 seconds")
    if plan["captions"] != "off" and not job["words"]:
        raise ValueError("Captions require a source-bound word transcript")
    for kind in ("cuts", "zooms"):
        for item in plan[kind]:
            a, b = number(item["start"]), number(item["end"])
            if not scope[0] <= a < b <= scope[1]:
                raise ValueError("Edit outside job scope")
            if type(item.get("selected")) is not bool:
                raise ValueError("selected must be a boolean")
            if kind == "zooms" and (not 1 <= number(item["scale"]) <= 1.25 or
                    not all(0 <= number(item[k]) <= 1 for k in ("center_x", "center_y"))):
                raise ValueError("Invalid zoom scale/center")
    zooms = sorted((z for z in plan["zooms"] if z["selected"]), key=lambda z: z["start"])
    if any(a["end"] > b["start"] for a, b in zip(zooms, zooms[1:])):
        raise ValueError("Selected zooms overlap; combine or reject one")


def timeline(job, scope=None):
    """Snap deletions inward; keep a global integer frame grid without drift."""
    validate_plan(job)
    rate = Fraction(job["media"]["fps"])
    origin = job["scope"][0]
    a, b = scope or job["scope"]
    first = math.ceil((a-origin) * float(rate) - 1e-7)
    last = math.floor((b-origin) * float(rate) + 1e-7)
    cuts = []
    for c in job["plan"]["cuts"]:
        if c["selected"]:
            left = max(first, math.ceil((c["start"]-origin) * float(rate) - 1e-7))
            right = min(last, math.floor((c["end"]-origin) * float(rate) + 1e-7))
            if right > left:
                cuts.append((left, right))
    merged = []
    for left, right in sorted(cuts):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    ranges, cursor = [], first
    for left, right in [*merged, (last, last)]:
        if left > cursor:
            ranges.append((cursor, left))
        cursor = max(cursor, right)
    result, output_frame = [], 0
    chunk = max(1, round(job["plan"]["chunk_seconds"] * float(rate)))
    for left, right in ranges:
        for frame in range(left, right, chunk):
            end = min(right, frame + chunk)
            result.append({"start": origin + float(Fraction(frame, 1)/rate),
                           "end": origin + float(Fraction(end, 1)/rate),
                           "frames": end-frame, "output_frame": output_frame})
            output_frame += end-frame
    if not result:
        raise ValueError("Selected cuts remove the entire scope")
    return result


def mapped_words(job, pieces):
    rate = float(Fraction(job["media"]["fps"]))
    result = []
    for word in job["words"]:
        overlaps = [(max(word["start"], p["start"]), min(word["end"], p["end"]), p) for p in pieces
                    if word["start"] < p["end"] and word["end"] > p["start"]]
        if not overlaps:
            continue
        # A word crossing a technical chunk boundary remains one caption token.
        start = overlaps[0][2]["output_frame"] / rate + overlaps[0][0] - overlaps[0][2]["start"]
        a, b, piece = overlaps[-1]
        end = piece["output_frame"] / rate + b - piece["start"]
        kept = sum(b-a for a, b, _ in overlaps)
        if kept < 0.5 * (word["end"] - word["start"]):
            continue
        result.append({**word, "start": start, "end": end})
    return result


def stamp(seconds, ass=False):
    scale = 100 if ass else 1000
    ticks = max(0, round(seconds * scale))
    whole, fraction = divmod(ticks, scale)
    minute, second = divmod(whole, 60)
    hour, minute = divmod(minute, 60)
    return f"{hour}:{minute:02}:{second:02}.{fraction:02}" if ass else f"{hour:02}:{minute:02}:{second:02},{fraction:03}"


def captions(job, pieces):
    words, groups, group = mapped_words(job, pieces), [], []
    for word in words:
        if group and (len(group) >= 7 or word["start"] - group[-1]["end"] > 0.7 or group[-1]["word"].endswith((".", "!", "?"))):
            groups.append(group)
            group = []
        group.append(word)
    if group:
        groups.append(group)
    srt, ass = [], ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {job['media']['width']}",
        f"PlayResY: {job['media']['height']}", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{max(12, round(job['media']['height']*.045))},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,24,1",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    emphasis = {normalized(w) for w in job["plan"]["highlight_words"]}
    for index, group in enumerate(groups, 1):
        start, end = group[0]["start"], group[-1]["end"]
        text = " ".join(w["word"] for w in group).replace("\n", " ").replace("\r", " ").replace("-->", "→")
        srt.append(f"{index}\n{stamp(start)} --> {stamp(end)}\n{text}\n")
        marked = []
        for word in group:
            safe = word["word"].replace("\\", "＼").replace("{", "(").replace("}", ")").replace("\n", " ").replace("\r", " ")
            if job["plan"]["captions"] == "highlight" and (word["emphasis"] or normalized(word["word"]) in emphasis):
                safe = r"{\c&H00FFFF&\b1}" + safe + r"{\r}"
            marked.append(safe)
        ass.append(f"Dialogue: 0,{stamp(start, True)},{stamp(end, True)},Default,,0,0,0,," + " ".join(marked))
    return "\n".join(srt), "\n".join(ass) + "\n"


def review_html(job, pieces=None):
    cuts = job["plan"]["cuts"]
    rows = "".join(f"<tr><td>{html.escape(c['id'])}</td><td>{c['start']:.3f}–{c['end']:.3f}</td><td>{'proposed cut' if c['selected'] else 'review only'}</td><td>{html.escape(c['reason'])}</td></tr>" for c in cuts)
    words = []
    for w in job["words"]:
        removed = any(c["selected"] and c["start"] <= (w["start"]+w["end"])/2 < c["end"] for c in cuts)
        text = html.escape(w["word"])
        words.append(f'<span title="{w["start"]:.3f}s">' + (f"<del>{text}</del>" if removed else text) + "</span>")
    videos = ('<h2>Original excerpt</h2><video controls src="original.mp4"></video>'
              '<h2>Edited excerpt (shorter timeline)</h2><video controls src="playback.mp4"></video>'
              '<p>Players are independent because cuts change timing. Playback uses the first audio track; edited.mkv retains all tracks.</p>') if pieces else ""
    return ('<!doctype html><meta charset="utf-8"><title>Editor review</title>'
            '<style>body{font:18px system-ui;max-width:1100px;margin:30px auto;background:#151515;color:#eee}video{width:100%}td,th{padding:8px;text-align:left}del{color:#f99}span{line-height:1.8}</style>'
            '<h1>Editor: proposed transcript and cuts</h1>' + videos + '<p>' + " ".join(words) + '</p>'
            '<table><tr><th>ID</th><th>Source seconds</th><th>Selection</th><th>Reason</th></tr>' + rows + '</table>')
