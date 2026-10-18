#!/usr/bin/env python3
"""Local, reviewable speech editing. Core requires Python 3.10+ and FFmpeg."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import csv
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import venv

from timeline import (captions, intersect_ranges, number, propose, review_html, signature, timeline,
                      validate_plan, validate_words)

HERE = Path(__file__).resolve().parent


def absolute(value):
    return Path(os.path.abspath(value)).resolve()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def run(command, *, cwd=None, log=None):
    command = list(map(str, command))
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if log:
        with Path(log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(command, ensure_ascii=False) + "\n" + result.stderr[-12000:] + "\n")
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} failed:\n" + (result.stderr or result.stdout)[-4000:])
    return result.stdout


def ffmpeg(args, **kw):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-n", "-threads", "2", *args], **kw)


def probe(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))
    video = next((s for s in data["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    if not video:
        raise ValueError("Editor needs a recording with a video stream")
    rate = Fraction(video.get("avg_frame_rate", "0/1"))
    if rate <= 0:
        rate = Fraction(video.get("r_frame_rate", "0/1"))
    duration = number(data["format"].get("duration", 0))
    if rate <= 0 or duration <= 0:
        raise ValueError("Cannot determine duration/frame rate")
    sar = Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/"))
    if sar <= 0:
        sar = Fraction(1)
    width, height = round(video["width"]*sar/2)*2, video["height"]//2*2
    rotation = int(next((d["rotation"] for d in video.get("side_data_list", []) if "rotation" in d), video.get("tags", {}).get("rotate", 0)))
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {"duration": duration, "fps": str(rate), "width": width, "height": height,
            "video_index": video["index"], "rotation": rotation,
            "field_order": video.get("field_order"),
            "hdr": video.get("color_transfer") in ("smpte2084", "arib-std-b67"),
            "color": {k: video.get(k) for k in ("color_space", "color_primaries", "color_transfer", "color_range")},
            "audio": [s for s in data["streams"] if s["codec_type"] == "audio"]}


def cache_default():
    # Some local-agent sandboxes replace LOCALAPPDATA with a per-run directory.
    # Keep installed environments discoverable across turns; --cache remains an
    # explicit override for redirected profiles or a different storage drive.
    if sys.platform == "win32":
        base = Path.home()/"AppData"/"Local"
    elif sys.platform == "darwin":
        base = Path.home()/"Library"/"Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home()/".cache"))
    return base / "ai-media-skills" / "editor"


def cache_python(cache):
    return absolute(cache) / "asr-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def doctor(cache):
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    candidates = [str(p.parent) for p in (Path.home()/".cache"/"huggingface"/"hub").glob("models--Systran--faster-whisper*/snapshots/*/model.bin")]
    model_root = absolute(cache)/"models"
    if model_root.exists():
        candidates += [str(p.parent) for p in model_root.rglob("model.bin")]
    return {"python": sys.version.split()[0], "tools": tools, "ready_core": all(tools.values()),
            "asr_python": str(cache_python(cache)), "asr_installed": cache_python(cache).is_file(),
            "cached_model_candidates": candidates,
            "note": "ASR is optional; imported source-bound word timestamps also work. No media upload is needed."}


def space(path, needed):
    path = absolute(path)
    while not path.exists():
        path = path.parent
    if shutil.disk_usage(path).free < needed:
        raise ValueError(f"Insufficient storage: allow at least {needed/2**30:.2f} GiB")


def setup(cache, install=False):
    cache = absolute(cache)
    result = {"environment": str(cache/"asr-env"), "package": "faster-whisper==1.2.1",
              "compatibility_pin": "av==16.0.1",
              "license": "MIT; separately installed CTranslate2, PyAV and model weights retain their licenses",
              "download": "Python wheels and dependencies, typically hundreds of MB; model weights are separate",
              "models": "No model is downloaded by setup. transcribe requires cached weights or explicit --download-model.",
              "disk_allowance_gib": 5, "installed": False}
    if install:
        if cache_python(cache).exists():
            raise ValueError("ASR environment already exists; inspect/reuse it rather than replacing it")
        space(cache, 5*2**30)
        cache.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(cache/"asr-env")
        run([cache_python(cache), "-m", "pip", "install", "-r", HERE.parent/"requirements-asr.txt"], log=cache/"setup.log")
        (cache/"asr-packages.txt").write_text(run([cache_python(cache), "-m", "pip", "freeze"]), encoding="utf-8")
        result["installed"] = True
        write(cache/"setup.json", result)
    return result


def load(folder):
    folder = absolute(folder)
    job = json.loads((folder/"job.json").read_text(encoding="utf-8"))
    if job.get("schema_version") != 1:
        raise ValueError("Unsupported Editor job version")
    return folder, job


@contextmanager
def lock(folder):
    path = folder/".running"
    try:
        with path.open("x") as stream:
            stream.write(f"pid={os.getpid()}\n")
    except FileExistsError:
        raise ValueError("Job is running or interrupted; verify the process stopped before removing its .running lock")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def check_source(job):
    source = job["source"]
    path = Path(source["path"])
    if not path.is_file() or path.stat().st_size != source["size"] or digest(path) != source["sha256"]:
        raise ValueError("Source changed; analyze it again in a new job")


def describe(folder, job):
    pieces = timeline(job)
    kept = sum(p["frames"] for p in pieces)/float(Fraction(job["media"]["fps"]))
    (folder/"review-plan.html").write_text(review_html(job), encoding="utf-8")
    with (folder/"edit-decisions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "start", "end", "kind", "selected", "reason"])
        for item in job["plan"]["cuts"]:
            writer.writerow([item[k] for k in ("id", "start", "end", "kind", "selected", "reason")])
    return {"job": str(folder/"job.json"), "plan_signature": signature(job),
            "style": job["plan"]["style"], "scope": job["scope"], "selected_cuts": sum(c["selected"] for c in job["plan"]["cuts"]),
            "review_only": sum(not c["selected"] for c in job["plan"]["cuts"]),
            "selected_zooms": sum(z["selected"] for z in job["plan"]["zooms"]),
            "estimated_edited_seconds": kept, "seconds_removed": job["scope"][1]-job["scope"][0]-kept,
            "transcript_words": len(job["words"]), "review": str(folder/"review-plan.html"),
            "next": "Review the transcript, listen to proposed cuts, confirm this plan, then preview with --accept-plan SIGNATURE"}


def analyze(args):
    source, folder = absolute(args.input), absolute(args.job)
    if folder.exists():
        raise ValueError("Use a new job folder; existing work is never replaced")
    if not doctor(args.cache)["ready_core"]:
        raise ValueError("Install FFmpeg and ffprobe before analysis")
    media = probe(source)
    if media["hdr"]:
        raise ValueError("Editor v1 exports SDR. Choose an explicit HDR-to-SDR workflow before editing; source remains untouched")
    if media["field_order"] not in (None, "unknown", "progressive"):
        raise ValueError("Deinterlace with a confirmed field-order decision before editing this source")
    if not 0 <= args.audio_track < len(media["audio"]):
        raise ValueError("Choose an existing speech audio track (zero based)")
    start, end = number(args.start), media["duration"] if args.seconds is None else min(media["duration"], number(args.start)+number(args.seconds))
    if not 0 <= start < end <= media["duration"] or end-start < 0.2:
        raise ValueError("Invalid analysis scope")
    space(folder, 200*2**20)
    folder.mkdir(parents=True)
    stamp = {"path": str(source), "size": source.stat().st_size, "sha256": digest(source)}
    audio = folder/"speech.wav"
    ffmpeg(["-ss", start, "-i", source, "-t", end-start, "-map", f"0:a:{args.audio_track}", "-vn", "-ac", "1", "-ar", "16000", audio], log=folder/"analysis.log")
    # Intersect per-track quiet intervals rather than mixing waveforms: summing
    # out-of-phase mics can cancel real speech and falsely look like silence.
    silence = None
    for i in range(len(media["audio"])):
        command = ["ffmpeg", "-hide_banner", "-nostdin", "-ss", str(start), "-i", str(source), "-t", str(end-start),
                   "-map", f"0:a:{i}", "-af", "aresample=16000:async=1:first_pts=0,apad,silencedetect=noise=-38dB:d=0.35", "-f", "null", "-"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise ValueError("Silence analysis failed: " + result.stderr[-3000:])
        (folder/f"silence-track-{i}.log").write_text(result.stderr, encoding="utf-8")
        quiet, pending = [], None
        for kind, value in re.findall(r"silence_(start|end):\s*([\d.eE+-]+)", result.stderr):
            point = max(start, min(end, start+float(value)))
            if kind == "start":
                pending = point
            elif pending is not None:
                quiet.append([pending, point])
                pending = None
        if pending is not None:
            quiet.append([pending, end])
        silence = quiet if silence is None else intersect_ranges(silence, quiet)
    job = {"schema_version": 1, "source": stamp, "scope": [start, end], "media": media,
           "cache": str(absolute(args.cache)), "speech_track": args.audio_track, "analysis_audio_sha256": digest(audio), "silences": silence,
           "words": [], "plan": propose([], silence, [start, end], args.style),
           "plan_approval": None, "preview": None, "render_approval": None,
           "versions": {"ffmpeg": run(["ffmpeg", "-version"]).splitlines()[0], "python": sys.version.split()[0]}}
    check_source(job)
    write(folder/"job.json", job)
    info = describe(folder, job)
    info["warning"] = "Silence is a candidate, not proof of dead air. Transcribe/import words before filler/retake editing. Output is CFR at the displayed nominal source rate; confirm VFR conversion if applicable."
    return info


def transcribe(args):
    folder, job = load(args.job)
    with lock(folder):
        check_source(job)
        if digest(folder/"speech.wav") != job["analysis_audio_sha256"]:
            raise ValueError("Analysis audio changed; create a new analysis job before transcription")
        python = cache_python(job["cache"])
        if not python.exists():
            raise ValueError("Run setup --install for the optional isolated ASR environment, or import a timed transcript with propose")
        path = folder/f"transcript-{time.time_ns()}.json"
        cmd = [python, HERE/"transcribe.py", "--audio", folder/"speech.wav", "--output", path,
               "--source-sha256", job["source"]["sha256"], "--start", job["scope"][0], "--end", job["scope"][1],
               "--model", args.model, "--cache", Path(job["cache"])/"models", "--device", args.device]
        if args.language:
            cmd += ["--language", args.language]
        if args.download_model:
            cmd += ["--download-model"]
        run(cmd, log=folder/"transcription.log")
        return {"transcript": str(path), "next": "Review word text/timestamps, then run propose --transcript PATH"}


def make_plan(args):
    folder, job = load(args.job)
    with lock(folder):
        check_source(job)
        if args.transcript:
            data = json.loads(absolute(args.transcript).read_text(encoding="utf-8"))
            job["words"] = validate_words(data, job["source"]["sha256"], job["scope"])
            job["transcription"] = {"sha256": digest(args.transcript), "engine": data.get("engine", "imported"), "provenance": data.get("provenance", {})}
        job["plan"] = propose(job["words"], job["silences"], job["scope"], args.style or job["plan"]["style"])
        job["plan_approval"] = job["preview"] = job["render_approval"] = None
        write(folder/"job.json", job)
        return describe(folder, job)


def update(args):
    folder, job = load(args.job)
    with lock(folder):
        check_source(job)
        items = {i["id"]: i for kind in ("cuts", "zooms") for i in job["plan"][kind]}
        for flag, selected in ((args.select, True), (args.reject, False)):
            for key in flag:
                if key not in items:
                    raise ValueError("Unknown edit ID: " + key)
                items[key]["selected"] = selected
        for kind, values in (("cuts", args.cut), ("zooms", args.zoom)):
            for raw in values:
                start, end = map(number, raw.split(":"))
                item = {"id": f"manual-{kind}-{time.time_ns()}", "start": start, "end": end,
                        "selected": True, "reason": args.reason}
                if kind == "cuts":
                    item["kind"] = "manual"
                else:
                    item.update(scale=args.zoom_scale, motion=args.zoom_motion,
                                center_x=args.center[0], center_y=args.center[1])
                    if args.zoom_motion == "cut":
                        item["sampling"] = "2x-lanczos-yuv444p"
                job["plan"][kind].append(item)
        if args.captions:
            job["plan"]["captions"] = args.captions
        if args.highlight_words is not None:
            job["plan"]["highlight_words"] = args.highlight_words.split(",")
        validate_plan(job)
        timeline(job)
        job["plan_approval"] = job["preview"] = job["render_approval"] = None
        write(folder/"job.json", job)
        return describe(folder, job)


def color_args(media):
    options = {"color_space": "-colorspace", "color_primaries": "-color_primaries", "color_transfer": "-color_trc", "color_range": "-color_range"}
    result = []
    for key, option in options.items():
        value = media["color"].get(key)
        if value and value not in ("unknown", "unspecified", "reserved"):
            result += [option, value]
    return result


def zoom_filter(job, piece):
    active = [z for z in job["plan"]["zooms"] if z["selected"] and
              z["start"] < piece["end"] and z["end"] > piece["start"]]
    if any(z.get("motion", "pulse") == "cut" for z in active):
        expression, cx, cy = "1", "0.5", "0.4"
        rate = float(Fraction(job["media"]["fps"]))
        for z in active:
            if z.get("motion", "pulse") == "cut":
                # Half-open frame intervals: hard cut in, hold, then cut wide.
                # Relative frame numbers preserve the state over chunk joins.
                a = math.ceil((z["start"]-piece["start"])*rate-1e-7)
                b = math.ceil((z["end"]-piece["start"])*rate-1e-7)
                gate = f"gte(on,{a})*lt(on,{b})"
                value = str(z["scale"])
            else:
                a, b = z["start"]-piece["start"], z["end"]-piece["start"]
                gate = f"between(in_time,{a:.9f},{b:.9f})"
                value = f"1+({z['scale']}-1)*max(0,min(1,min((in_time-{a:.9f})/0.2,({b:.9f}-in_time)/0.2)))"
            expression = f"if({gate},{value},{expression})"
            cx = f"if({gate},{z['center_x']},{cx})"
            cy = f"if({gate},{z['center_y']},{cy})"
        m = job["media"]
        return [f"scale={m['width']*2}:{m['height']*2}:flags=lanczos", "format=yuv444p",
                f"zoompan=z='{expression}':x='(iw-iw/zoom)*({cx})':y='(ih-ih/zoom)*({cy})':d=1:s={m['width']}x{m['height']}:fps={m['fps']}",
                "format=yuv420p"]
    # Keep the original pulse and sampling path for saved jobs without motion.
    expression = "1"
    for z in job["plan"]["zooms"]:
        if not z["selected"] or z["start"] >= piece["end"] or z["end"] <= piece["start"]:
            continue
        a, b = z["start"]-piece["start"], z["end"]-piece["start"]
        expression += f"+({z['scale']}-1)*if(between(in_time,{a:.9f},{b:.9f}),max(0,min(1,min((in_time-{a:.9f})/0.2,({b:.9f}-in_time)/0.2))),0)"
    if expression == "1":
        return []
    # Centers are validated normalized crop positions; multiple non-overlapping
    # emphasis markers may use distinct framing in a single technical chunk.
    cx, cy = "0.5", "0.4"
    for z in job["plan"]["zooms"]:
        if z["selected"]:
            a, b = z["start"]-piece["start"], z["end"]-piece["start"]
            cx = f"if(between(in_time,{a:.9f},{b:.9f}),{z['center_x']},{cx})"
            cy = f"if(between(in_time,{a:.9f},{b:.9f}),{z['center_y']},{cy})"
    m = job["media"]
    return [f"zoompan=z='{expression}':x='(iw-iw/zoom)*({cx})':y='(ih-ih/zoom)*({cy})':d=1:s={m['width']}x{m['height']}:fps={m['fps']}"]


def segment(job, piece, previous, output, log):
    m, plan = job["media"], job["plan"]
    duration = piece["frames"]/float(Fraction(m["fps"]))
    fade = min(plan["crossfade_ms"]/1000, duration/4) if previous else 0
    # Decode video/audio independently. A short trimmed video branch can signal
    # EOF before a shared input supplies its last audio packet on FFmpeg 7.
    video_path, audio_path = output.with_suffix(".video.mp4"), output.with_suffix(".audio.mka")
    for temporary in (video_path, audio_path):
        temporary.unlink(missing_ok=True)
    filters = ["setpts=PTS-STARTPTS", f"fps={m['fps']}", f"scale={m['width']}:{m['height']}:flags=lanczos", "setsar=1",
               *zoom_filter(job, piece), "tpad=stop_mode=clone:stop_duration=0.1", f"trim=end_frame={piece['frames']}", "setpts=PTS-STARTPTS"]
    ffmpeg(["-ss", piece["start"], "-i", job["source"]["path"], "-map", f"0:{m['video_index']}",
            "-an", "-vf", ",".join(filters), "-r", m["fps"], "-fps_mode", "cfr", "-c:v", "libx264", "-preset", "fast",
            "-crf", "18", "-pix_fmt", "yuv420p", *color_args(m), "-metadata:s:v:0", "rotate=0", video_path], log=log)
    command = ["-ss", piece["start"], "-i", job["source"]["path"]]
    if fade:
        command += ["-ss", previous["end"], "-i", job["source"]["path"]]
    audio_filters = []
    for i in range(len(m["audio"])):
        audio_filters.append(f"[0:a:{i}]aresample=48000:async=1:first_pts=0,aformat=sample_fmts=fltp,apad,atrim=duration={duration:.9f}[body{i}]")
        if fade:
            samples = max(1, round(fade*48000))
            audio_filters.append(f"[1:a:{i}]aresample=48000:async=1:first_pts=0,aformat=sample_fmts=fltp,apad,atrim=end_sample={samples},asetnsamples=n={samples}:p=1[tail{i}]")
            audio_filters.append(f"[tail{i}][body{i}]acrossfade=ns={samples}:c1=tri:c2=tri[a{i}]")
        else:
            audio_filters.append(f"[body{i}]anull[a{i}]")
    command += ["-filter_complex", ";".join(audio_filters)]
    for i, audio in enumerate(m["audio"]):
        command += ["-map", f"[a{i}]", f"-metadata:s:a:{i}", "title="+audio.get("tags", {}).get("title", f"Track {i+1}"),
                    f"-metadata:s:a:{i}", "language="+audio.get("tags", {}).get("language", "und")]
    command += ["-c:a", "flac", "-map_metadata", "-1", audio_path]
    ffmpeg(command, log=log)
    ffmpeg(["-i", video_path, "-i", audio_path, "-map", "0:v", "-map", "1:a", "-map_metadata", "1", "-c", "copy", output], log=log)
    video_path.unlink()
    audio_path.unlink()


def verify(path, job, frames):
    m, actual = job["media"], probe(path)
    expected = frames/float(Fraction(m["fps"]))
    count = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "json", path]))["streams"][0]["nb_read_frames"]
    if int(count) != frames or abs(actual["duration"]-expected) > 0.08:
        raise ValueError("Output frame count or duration failed verification")
    if (actual["width"], actual["height"]) != (m["width"], m["height"]) or abs(float(Fraction(actual["fps"]))-float(Fraction(m["fps"]))) > 0.01:
        raise ValueError(f"Output geometry/frame rate differs from plan: expected {m['width']}x{m['height']}/{m['fps']}, got {actual['width']}x{actual['height']}/{actual['fps']}")
    if len(actual["audio"]) != len(m["audio"]):
        raise ValueError("An audio track was lost")
    for original, audio in zip(m["audio"], actual["audio"]):
        if audio["channels"] != original["channels"] or audio["sample_rate"] != "48000":
            raise ValueError("Audio channel count/sample rate failed verification")
        if abs(float(audio.get("start_time", 0))) > 0.08:
            raise ValueError("Unexpected output audio start offset")
        for key in ("title", "language"):
            expected_label = original.get("tags", {}).get(key)
            if expected_label and audio.get("tags", {}).get(key) != expected_label:
                raise ValueError("Audio track label changed: " + key)
    run(["ffmpeg", "-v", "error", "-xerror", "-err_detect", "explode", "-i", path, "-map", "0:v", "-map", "0:a", "-f", "null", "-"])
    return {"passed": True, "frames": frames, "duration": actual["duration"], "fps": actual["fps"],
            "audio_tracks": len(actual["audio"]), "decoded": True,
            "note": "Timing/container checks cannot establish natural cuts or perceptual lip sync; human review remains required."}


def process(job, root, scope, resume=False):
    root.mkdir(parents=True, exist_ok=True)
    pieces = timeline(job, scope)
    total_frames = sum(p["frames"] for p in pieces)
    rate = float(Fraction(job["media"]["fps"]))
    space(root, max(300*2**20, int(total_frames/rate*8*2**20)))
    state_path = root/"state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"signature": signature(job), "scope": scope, "completed": {}, "elapsed_seconds": 0}
    if state["signature"] != signature(job) or state["scope"] != scope:
        raise ValueError("Checkpoint settings changed; create a new preview/job")
    if state["completed"] and not resume:
        raise ValueError("Use resume for an interrupted render")
    started, prior = time.monotonic(), state["elapsed_seconds"]
    for i, piece in enumerate(pieces):
        output = root/f"segment-{i:06d}.mkv"
        done = state["completed"].get(str(i))
        if done and output.exists() and digest(output) == done["sha256"]:
            continue
        # Only this exact runner-owned partial file can be replaced on resume.
        if output.exists():
            output.unlink()
        print(f"Editor segment {i+1}/{len(pieces)}: {piece['start']:.3f}–{piece['end']:.3f}s", file=sys.stderr, flush=True)
        segment(job, piece, pieces[i-1] if i else None, output, root/"processing.log")
        if abs(probe(output)["duration"] - piece["frames"]/rate) > 0.08:
            raise ValueError("Segment duration failed verification")
        state["completed"][str(i)] = {"sha256": digest(output), "piece": piece}
        state["elapsed_seconds"] = prior + time.monotonic()-started
        write(state_path, state)
    manifest = "ffconcat version 1.0\n" + "".join(f"file 'segment-{i:06d}.mkv'\nduration {p['frames']/rate:.12f}\n" for i, p in enumerate(pieces))
    (root/"segments.ffconcat").write_text(manifest, encoding="utf-8")
    srt, ass = captions(job, pieces)
    if job["plan"]["captions"] != "off":
        (root/"captions.srt").write_text(srt, encoding="utf-8")
        (root/"captions.ass").write_text(ass, encoding="utf-8")
    destination = root/"edited.mkv"
    if destination.exists():
        destination.unlink()
    command = ["-f", "concat", "-safe", "1", "-i", "segments.ffconcat", "-map", "0:v", "-map", "0:a", "-map_metadata", "0"]
    if job["plan"]["captions"] in ("burn", "highlight"):
        command += ["-vf", "subtitles=captions.ass", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", *color_args(job["media"]), "-c:a", "copy"]
    else:
        command += ["-c", "copy"]
    command += ["-t", total_frames/rate, destination.name]
    ffmpeg(command, cwd=root, log=root/"processing.log")
    verification = verify(destination, job, total_frames)
    check_source(job)
    (root/"timeline.json").write_text(json.dumps(pieces, indent=2), encoding="utf-8")
    state.update(output=str(destination), verification=verification, source_unchanged=True,
                 elapsed_seconds=prior+time.monotonic()-started,
                 removed_seconds=scope[1]-scope[0]-total_frames/rate)
    write(state_path, state)
    return state


def preview(args):
    folder, job = load(args.job)
    with lock(folder):
        check_source(job)
        if args.accept_plan != signature(job):
            raise ValueError("Review and confirm the current plan signature before preview")
        start = job["scope"][0] if args.start is None else number(args.start)
        end = min(job["scope"][1], start+number(args.seconds))
        if not job["scope"][0] <= start < end <= job["scope"][1] or not 0.2 <= end-start <= 60:
            raise ValueError("Preview must be 0.2–60 seconds within the analyzed scope")
        job["plan_approval"] = signature(job)
        job["render_approval"] = job["preview"] = None
        write(folder/"job.json", job)
        root = folder/f"preview-{time.time_ns()}"
        state = process(job, root, [start, end])
        # Browser copies are AAC with the chosen speech track only; the main MKV
        # retains every original audio track and its labels.
        ffmpeg(["-i", state["output"], "-map", "0:v", "-map", f"0:a:{job['speech_track']}", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", root/"playback.mp4"])
        ffmpeg(["-ss", start, "-i", job["source"]["path"], "-t", end-start, "-map", f"0:{job['media']['video_index']}",
                "-map", f"0:a:{job['speech_track']}", "-vf", "scale=-2:540,setsar=1", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", root/"original.mp4"])
        pieces = timeline(job, [start, end])
        (root/"review.html").write_text(review_html(job, pieces), encoding="utf-8")
        ratio = (job["scope"][1]-job["scope"][0])/(end-start)
        job["preview"] = {"signature": signature(job), "scope": [start, end], "output": state["output"],
            "playback": str(root/"playback.mp4"), "original": str(root/"original.mp4"), "review": str(root/"review.html"),
            "verification": state["verification"], "elapsed_seconds": state["elapsed_seconds"],
            "estimated_full_seconds": state["elapsed_seconds"]*ratio,
            "estimated_full_bytes": int(Path(state["output"]).stat().st_size*ratio),
            "status": "human_motion_listening_and_edit_review_pending"}
        write(folder/"job.json", job)
        write(root/"report.json", {"source": job["source"], "plan": job["plan"], "preview": job["preview"], "versions": job["versions"]})
        return job["preview"]


def render(args, resume=False):
    folder, job = load(args.job)
    with lock(folder):
        check_source(job)
        current = signature(job)
        if not job["preview"] or job["preview"]["signature"] != current or job["plan_approval"] != current:
            raise ValueError("A successful current preview is required")
        if resume:
            if job["render_approval"] != current:
                raise ValueError("Resume requires prior full-render approval for these exact settings")
        elif args.accept_preview != current:
            raise ValueError("Accept the actual current preview before rendering")
        job["render_approval"] = current
        write(folder/"job.json", job)
        result = process(job, folder/"render", job["scope"], resume=resume)
        write(folder/"render"/"report.json", {"result": result, "plan": job["plan"], "versions": job["versions"]})
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("doctor", "setup"):
        q = sub.add_parser(name)
        q.add_argument("--cache", default=str(cache_default()))
        if name == "setup":
            q.add_argument("--install", action="store_true")
    q = sub.add_parser("analyze")
    q.add_argument("--input", required=True)
    q.add_argument("--job", required=True)
    q.add_argument("--cache", default=str(cache_default()))
    q.add_argument("--start", type=float, default=0)
    q.add_argument("--seconds", type=float)
    q.add_argument("--audio-track", type=int, default=0)
    q.add_argument("--style", choices=("natural", "tight", "custom"), default="natural")
    q = sub.add_parser("transcribe")
    q.add_argument("--job", required=True)
    q.add_argument("--model", required=True, help="Cached model directory or Faster-Whisper model name")
    q.add_argument("--language")
    q.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    q.add_argument("--download-model", action="store_true")
    q = sub.add_parser("propose")
    q.add_argument("--job", required=True)
    q.add_argument("--transcript")
    q.add_argument("--style", choices=("natural", "tight", "custom"))
    q = sub.add_parser("update")
    q.add_argument("--job", required=True)
    q.add_argument("--select", action="append", default=[])
    q.add_argument("--reject", action="append", default=[])
    q.add_argument("--cut", action="append", default=[], help="START:END source seconds")
    q.add_argument("--zoom", action="append", default=[], help="START:END source seconds")
    q.add_argument("--zoom-scale", type=float, default=1.18)
    q.add_argument("--zoom-motion", choices=("cut", "pulse"), default="cut")
    q.add_argument("--center", nargs=2, type=float, default=[0.5, 0.4])
    q.add_argument("--reason", default="Reviewed manual edit")
    q.add_argument("--captions", choices=("off", "srt", "burn", "highlight"))
    q.add_argument("--highlight-words")
    for name in ("preview", "render", "resume"):
        q = sub.add_parser(name)
        q.add_argument("--job", required=True)
        if name == "preview":
            q.add_argument("--accept-plan", required=True)
            q.add_argument("--start", type=float)
            q.add_argument("--seconds", type=float, default=30)
        elif name == "render":
            q.add_argument("--accept-preview", required=True)
    return p


def main():
    args = parser().parse_args()
    try:
        if args.command == "doctor": result = doctor(args.cache)
        elif args.command == "setup": result = setup(args.cache, args.install)
        elif args.command == "analyze": result = analyze(args)
        elif args.command == "transcribe": result = transcribe(args)
        elif args.command == "propose": result = make_plan(args)
        elif args.command == "update": result = update(args)
        elif args.command == "preview": result = preview(args)
        else: result = render(args, args.command == "resume")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print("Editor: " + str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
