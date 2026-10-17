#!/usr/bin/env python3
"""Preview-first, local video repair. Standard library + separately installed FFmpeg."""
from __future__ import annotations

import argparse
import bisect
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time

from engines import (VideoError, absolute, default_cache, digest, free_space, hardware, interpolate_pair, interpolate_directory,
                     resolve, run, seed_video, setup, upscale_frames, write_json)

VERSION = 1
REPAIRS = {"denoise", "exposure", "color", "sharpen", "deblock", "deband",
           "stabilize", "deflicker", "deinterlace"}


def ffmpeg(args, *, log=None, cwd=None):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-threads", "2", *args], log=log, cwd=cwd)


def probe(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]).stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s["codec_type"] == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise VideoError("Input has no ordinary video stream.")
    try:
        duration = float(data["format"].get("duration", video.get("duration", 0)))
        fps = Fraction(video.get("avg_frame_rate", "0/1"))
        if fps <= 0:
            fps = Fraction(video.get("r_frame_rate", "0/1"))
        sar = Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/"))
        if sar <= 0:
            sar = Fraction(1)
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoError("Cannot determine finite duration/frame rate; remux or repair metadata first.") from exc
    if duration <= 0 or fps <= 0 or not math.isfinite(duration):
        raise VideoError("Input needs a positive, finite duration and frame rate.")
    rotation = int(next((d.get("rotation", 0) for d in video.get("side_data_list", []) if "rotation" in d),
                        video.get("tags", {}).get("rotate", 0)))
    width, height = round(video["width"] * sar), video["height"]
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {"duration": duration, "fps": str(fps), "width": width, "height": height,
            "coded_width": video["width"], "coded_height": video["height"], "rotation": rotation,
            "sar": str(sar), "video_index": video["index"], "pix_fmt": video.get("pix_fmt"),
            "field_order": video.get("field_order"), "color_space": video.get("color_space"),
            "color_primaries": video.get("color_primaries"), "color_transfer": video.get("color_transfer"),
            "color_range": video.get("color_range"),
            "hdr": video.get("color_transfer") in ("smpte2084", "arib-std-b67"),
            "audio": [s for s in streams if s["codec_type"] == "audio"], "streams": streams,
            "format": data["format"]}


def fingerprint(path):
    path = absolute(path)
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "sha256": digest(path)}


def check_source(job):
    source = job["source"]
    path = Path(source["path"])
    if not path.is_file() or path.stat().st_size != source["size"] or digest(path) != source["sha256"]:
        raise VideoError("Source changed after analysis. Create a new job and preview.")


def load_job(folder):
    folder = absolute(folder)
    path = folder / "job.json"
    if not path.exists():
        raise VideoError("No job.json. Run analyze --input RECORDING --job NEW_FOLDER.")
    job = json.loads(path.read_text(encoding="utf-8"))
    if job.get("schema_version") != VERSION:
        raise VideoError("Unsupported job schema version.")
    return folder, job


@contextmanager
def job_lock(folder):
    lock = Path(folder) / ".running"
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\n")
    except FileExistsError as exc:
        raise VideoError("Job is already running, or was interrupted. Check its process before removing .running.") from exc
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def doctor(cache):
    result = hardware(cache)
    result["tools"] = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    result["filters"] = []
    if result["tools"]["ffmpeg"]:
        result["ffmpeg_version"] = run(["ffmpeg", "-version"]).stdout.splitlines()[0]
        text = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
        # FFmpeg 9 removed the command-support flag column; identify real filter rows
        # by their I/O signature instead of assuming a fixed number of flags.
        result["filters"] = sorted(set(re.findall(r"^\s*[A-Z.]+\s+(\w+)\s+[AVN|]+->[AVN|]+\s", text, re.M)))
    result["ready_cpu"] = all(result["tools"].values()) and "scale" in result["filters"]
    result["note"] = "Installed is distinct from benchmarked. A successful sample establishes runtime compatibility."
    return result


def scene_cuts(source, info, *, start=0, duration=None, log=None):
    duration = duration if duration is not None else info["duration"] - start
    result = ffmpeg(["-ss", f"{start:.9f}", "-i", source, "-t", f"{duration:.9f}",
                     "-map", f"0:{info['video_index']}", "-an", "-vf",
                     "select='gt(scene,0.35)',showinfo", "-fps_mode", "vfr", "-f", "null", "-"], log=log)
    # Output timestamps are relative to the seek point.
    return sorted({start + float(x) for x in re.findall(r"pts_time:([\d.eE+-]+)", result.stderr)
                   if 0.05 < float(x) < duration - 0.05})


def analyze(source, folder, cache):
    source = absolute(source)
    if not source.is_file():
        raise VideoError("Recording does not exist: " + str(source))
    folder = absolute(folder)
    if folder.exists():
        raise VideoError("Choose a new job folder; existing work is never overwritten by analyze.")
    info = probe(source)
    inventory = doctor(cache)
    if not inventory["ready_cpu"]:
        raise VideoError("Install FFmpeg and ffprobe on PATH before analyzing a recording.")
    free_space(folder, 64 * 2**20)
    folder.mkdir(parents=True)
    (folder / "analysis").mkdir()
    samples = []
    sample_length = min(3.0, info["duration"])
    for index, position in enumerate(sorted({0.0, max(0, info["duration"] / 2 - sample_length / 2),
                                            max(0, info["duration"] - sample_length)})):
        frame = folder / "analysis" / f"sample-{index + 1}.jpg"
        ffmpeg(["-ss", str(position), "-i", source, "-map", f"0:{info['video_index']}",
                "-frames:v", "1", "-vf", "scale=960:-2", frame])
        measurement = ffmpeg(["-ss", str(position), "-i", source, "-t", str(sample_length),
                              "-map", f"0:{info['video_index']}", "-an", "-vf",
                              "idet,signalstats,metadata=mode=print", "-f", "null", "-"])
        yavg = [float(x) for x in re.findall(r"lavfi.signalstats.YAVG=([\d.]+)", measurement.stderr)]
        field = re.findall(r"Multi frame detection: TFF:\s*(\d+) BFF:\s*(\d+) Progressive:\s*(\d+) Undetermined:\s*(\d+)", measurement.stderr)
        points = [float(x) for x in re.findall(r"pts_time:([\d.eE+-]+)", measurement.stderr)]
        intervals = [b - a for a, b in zip(points, points[1:]) if b > a]
        variable = bool(intervals and max(intervals) - min(intervals) > max(0.003, 0.1 / float(Fraction(info["fps"]))))
        samples.append({"start": position, "frame": str(frame.relative_to(folder)), "variable_frame_intervals": variable,
                        "mean_luma": sum(yavg) / len(yavg) if yavg else None,
                        "interlace_counts": list(map(int, field[-1])) if field else None})
    suggestions = ["Inspect the sample frames and motion; noise, blur, camera shake and color cast need visual judgment."]
    if any(s["mean_luma"] is not None and s["mean_luma"] < 55 for s in samples):
        suggestions.append("Low average brightness: compare a restrained exposure lift; dark backgrounds may be intentional.")
    if info["field_order"] not in (None, "unknown", "progressive") or any(
            s["interlace_counts"] and sum(s["interlace_counts"][:2]) > s["interlace_counts"][2] * 2 for s in samples):
        suggestions.append("Possible interlacing: confirm field order and motion before selecting deinterlace.")
    if info["hdr"]:
        suggestions.append("HDR source: explicitly choose preserve or tone-map to SDR before processing.")
    info["vfr_detected"] = any(sample["variable_frame_intervals"] for sample in samples)
    if info["vfr_detected"]:
        suggestions.append("Variable frame intervals detected: choose an explicit CFR output rate; elapsed time will be retained.")
    job = {"schema_version": VERSION, "source": fingerprint(source), "media": info,
           "cache": str(absolute(cache)), "analysis": {"samples": samples, "suggestions": suggestions},
           "settings": None, "preview": None, "approval": None}
    write_json(folder / "doctor.json", inventory)
    write_json(folder / "job.json", job)
    return {"job": str(folder / "job.json"), "media": {k: v for k, v in info.items() if k not in ("streams", "format", "audio")},
            "audio_tracks": len(info["audio"]), "samples": samples, "suggestions": suggestions,
            "preferences_needed": ["repairs", "natural/strong look", "resolution", "frame rate", "time/quality budget"]}


def settings_from_args(args, job):
    media = job["media"]
    repairs = sorted(set(filter(None, args.repairs.split(","))))
    unknown = set(repairs) - REPAIRS
    if unknown:
        raise VideoError("Unknown repairs: " + ", ".join(sorted(unknown)))
    height = media["height"] if args.height == "source" else int(args.height)
    width = max(2, round(height * media["width"] / media["height"] / 2) * 2)
    height = round(height / 2) * 2
    if not 64 <= height <= 4320 or width > 8192:
        raise VideoError("Output dimensions must be even, height 64–4320, width at most 8192.")
    native_rate = Fraction(media["fps"]) * (2 if "deinterlace" in repairs else 1)
    if media.get("vfr_detected") and args.fps == "source":
        raise VideoError("Variable frame rate detected. Choose an explicit numeric CFR --fps after reviewing the timing conversion.")
    rate = native_rate if args.fps == "source" else parse_rate(args.fps)
    if args.interpolation != "none" and rate <= native_rate:
        raise VideoError("Interpolation is only relevant above the effective source rate (including deinterlacing).")
    if rate > native_rate and args.interpolation == "none" and not media.get("vfr_detected"):
        raise VideoError("Choose --interpolation rife or motion for a smoother higher frame rate; duplication is not enhancement.")
    if args.engine == "seedvr2" and args.style != "strong":
        raise VideoError("SeedVR2 reconstructs detail; choose strong style and inspect a preview.")
    if media["hdr"] and args.hdr == "ask":
        raise VideoError("HDR requires --hdr preserve or --hdr sdr.")
    if media["hdr"] and args.hdr == "preserve" and (args.engine != "cpu" or args.interpolation == "rife"):
        raise VideoError("These AI adapters are SDR-only. Explicitly choose --hdr sdr or use the CPU preserve path.")
    if media["hdr"] and args.hdr == "preserve" and set(repairs) & {"exposure", "color"}:
        raise VideoError("Exposure/color controls are SDR controls. Choose explicit HDR-to-SDR or omit them.")
    if "deinterlace" in repairs and args.field_order == "auto" and media.get("field_order") in (None, "unknown", "progressive"):
        raise VideoError("Confirm --field-order tff or bff for an unflagged/interpreted progressive source.")
    if args.container == "mp4" and any(a["codec_name"] not in ("aac", "mp3", "ac3", "eac3", "alac") for a in media["audio"]):
        raise VideoError("An audio codec cannot be copied to MP4 reliably. Choose --container mkv to retain every track.")
    if not -2 <= args.exposure <= 2 or not 0.5 <= args.gamma <= 2:
        raise VideoError("Exposure must be -2..2 stops; gamma 0.5..2.")
    if any(not -0.3 <= x <= 0.3 for x in (args.red, args.green, args.blue)):
        raise VideoError("Color channel adjustments must be -0.3..0.3.")
    if not 1 <= args.chunk_seconds <= 60 or not 0 < args.overlap <= 2:
        raise VideoError("Chunk size must be 1..60 seconds; overlap must be >0 and <=2 seconds.")
    if args.batch < 5 or args.batch % 4 != 1 or args.tile < 32:
        raise VideoError("Temporal batch must be 4n+1 and at least 5; tile must be at least 32.")
    settings = {"repairs": repairs, "style": args.style, "engine": args.engine,
                "height": height, "width": width, "fps": str(rate), "native_fps": str(native_rate),
                "interpolation": args.interpolation, "container": args.container,
                "exposure": args.exposure, "gamma": args.gamma,
                "red": args.red, "green": args.green, "blue": args.blue,
                "hdr": args.hdr, "field_order": args.field_order,
                "chunk_seconds": args.chunk_seconds, "overlap": args.overlap,
                "tile": args.tile, "batch": args.batch, "blocks_to_swap": args.blocks_to_swap,
                "seed_model": args.seed_model, "crf": args.crf, "stabilize_zoom": args.stabilize_zoom}
    if settings["crf"] < 0 or settings["crf"] > 28 or not 0 <= settings["stabilize_zoom"] <= 10:
        raise VideoError("CRF must be 0..28; stabilization maximum zoom 0..10 percent.")
    settings["engine_receipts"] = {name: resolve(name, job["cache"]) for name in
                                   ({args.engine} | ({"rife"} if args.interpolation == "rife" else set()))}
    return settings


def parse_rate(value):
    try:
        rate = Fraction(value)
        if not 1 <= rate <= 120:
            raise ValueError()
        return rate
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoError("Frame rate must be 1–120 or a rational such as 60000/1001.") from exc


def signature(job):
    value = {"source": job["source"], "settings": job["settings"], "schema_version": VERSION}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def require_filters(job):
    available = set(doctor(job["cache"])["filters"])
    required = {"scale", "setsar", "trim"}
    mapping = {"denoise": "hqdn3d", "exposure": "eq", "color": "colorbalance", "sharpen": "unsharp",
               "deblock": "deblock", "deband": "deband", "stabilize": "vidstabtransform",
               "deflicker": "deflicker", "deinterlace": "bwdif"}
    required |= {mapping[r] for r in job["settings"]["repairs"]}
    if "stabilize" in job["settings"]["repairs"]:
        required.add("vidstabdetect")
    if job["settings"]["interpolation"] == "motion":
        required.add("minterpolate")
    if job["media"]["hdr"] and job["settings"]["hdr"] == "sdr":
        required |= {"zscale", "tonemap"}
    if required - available:
        raise VideoError("This FFmpeg build is missing selected filters: " + ", ".join(sorted(required - available)))


def prefilters(job, transform=None):
    settings, info = job["settings"], job["media"]
    selected = settings["repairs"]
    filters = []
    if "deinterlace" in selected:
        parity = settings["field_order"]
        if parity == "auto":
            parity = "bff" if info["field_order"] in ("bb", "bt") else "tff"
        filters.append(f"bwdif=mode=send_field:parity={parity}:deint=all")
    if info["hdr"] and settings["hdr"] == "sdr":
        filters += ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
                    "tonemap=tonemap=mobius:desat=0", "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p"]
    filters += ["scale=trunc(iw*sar/2)*2:ih", "setsar=1"]
    if transform:
        filters.append(f"vidstabtransform=input='{transform}':smoothing=10:optzoom=0:crop=black:zoom={settings['stabilize_zoom']}")
    if "deflicker" in selected:
        filters.append("deflicker=size=5:mode=am")
    if "deblock" in selected:
        filters.append("deblock=filter=weak:block=8")
    if "denoise" in selected:
        filters.append("hqdn3d=1.5:1.5:4:4" if settings["style"] == "natural" else "hqdn3d=3:3:6:6")
    if "deband" in selected:
        filters.append("deband=1thr=0.01:2thr=0.01:3thr=0.01:range=16")
    if "exposure" in selected:
        # eq brightness is deliberately bounded; gamma lifts midtones without uniformly lifting the black level.
        filters.append(f"eq=brightness={settings['exposure'] * 0.05:.6f}:gamma={settings['gamma']:.6f}")
    if "color" in selected:
        filters.append(f"colorbalance=rm={settings['red']}:gm={settings['green']}:bm={settings['blue']}:pl=1")
    return filters


def color_args(job):
    info, settings = job["media"], job["settings"]
    if info["hdr"] and settings["hdr"] == "sdr":
        return ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    flags = []
    for source, option in (("color_space", "-colorspace"), ("color_primaries", "-color_primaries"),
                           ("color_transfer", "-color_trc"), ("color_range", "-color_range")):
        if info.get(source) not in (None, "unknown", "unspecified", "reserved"):
            flags += [option, info[source]]
    return flags


def encode_args(job, *, lossless=False):
    hdr = job["media"]["hdr"] and job["settings"]["hdr"] == "preserve"
    if lossless:
        return ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv444p16le" if hdr else "yuv444p", *color_args(job)]
    return ["-c:v", "libx265" if hdr else "libx264", "-preset", "medium", "-crf", str(job["settings"]["crf"]),
            "-pix_fmt", "yuv420p10le" if hdr else "yuv420p", "-threads", "2", *color_args(job)]


def plan_segments(start, duration, cuts, settings):
    """Cuts reset temporal state. Artificial chunk boundaries receive real neighboring context."""
    end = start + duration
    boundaries = [start] + [c for c in cuts if start + 1e-6 < c < end - 1e-6] + [end]
    rate = Fraction(settings["fps"])
    segments = []
    for shot, (a, b) in enumerate(zip(boundaries, boundaries[1:])):
        # Align every boundary to a single global output grid, avoiding per-chunk rounding drift.
        first = math.ceil(Fraction(str(a - start)) * rate - Fraction(1, 100000))
        last = math.ceil(Fraction(str(b - start)) * rate - Fraction(1, 100000))
        frames_per_chunk = max(1, round(settings["chunk_seconds"] * float(rate)))
        for begin in range(first, last, frames_per_chunk):
            finish = min(last, begin + frames_per_chunk)
            core_a, core_b = start + float(begin / rate), start + float(finish / rate)
            # Do not cross a scene cut to fill overlap context.
            context_a = max(a, core_a - settings["overlap"])
            context_b = min(b, core_b + settings["overlap"])
            segments.append({"shot": shot, "shot_start": a, "shot_end": b,
                             "start": core_a, "end": core_b, "context_start": context_a,
                             "context_end": context_b, "frames": finish - begin})
    return segments


def storage_budget(job):
    s = job["settings"]
    # Raw-equivalent estimate covers disk frame sequences and multiple temporary video stages.
    duration = s["chunk_seconds"] + 2 * s["overlap"]
    pixels = max(s["width"] * s["height"], job["media"]["width"] * job["media"]["height"])
    # NCNN's x4 restoration temporarily has sixteen times the source pixel count.
    if s["engine"] == "realesrgan":
        pixels = max(pixels, job["media"]["width"] * job["media"]["height"] * 16)
    temporary = pixels * 3 * float(Fraction(s["native_fps"])) * duration * 3
    output = max(job["source"]["size"], s["width"] * s["height"] * float(Fraction(s["fps"])) * job["media"]["duration"] * 0.15)
    return int(temporary + 2 * output + 256 * 2**20)


def stage_shot(job, directory, shot, log):
    """Stabilization transforms cover the entire shot, never individual processing chunks."""
    start, end = shot
    staged = directory / ("shot-" + hashlib.sha256(f"{start:.9f}:{end:.9f}".encode()).hexdigest()[:12] + ".mkv")
    if staged.exists():
        return staged
    transform = "motion.trf"
    ffmpeg(["-ss", str(start), "-i", job["source"]["path"], "-t", str(end - start),
            "-map", f"0:{job['media']['video_index']}", "-an", "-vf",
            ",".join(prefilters({**job, "settings": {**job["settings"], "repairs": [r for r in job["settings"]["repairs"] if r == "deinterlace"]}})
                     + [f"vidstabdetect=shakiness=5:accuracy=9:result={transform}"]),
            "-f", "null", "-"], log=log, cwd=directory)
    filters = prefilters(job, transform)
    ffmpeg(["-ss", str(start), "-i", job["source"]["path"], "-t", str(end - start),
            "-map", f"0:{job['media']['video_index']}", "-an", "-vf", ",".join(filters),
            *encode_args(job, lossless=True), staged], log=log, cwd=directory)
    return staged


def timestamps(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                           "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", path]).stdout)
    return [float(f["best_effort_timestamp_time"]) for f in data["frames"] if "best_effort_timestamp_time" in f]


def rife_video(job, staged, destination, scratch, log):
    frames, generated = scratch / "rife-in", scratch / "rife-out"
    frames.mkdir()
    generated.mkdir()
    points = timestamps(staged)
    ffmpeg(["-i", staged, "-an", "-fps_mode", "passthrough", frames / "%08d.png"], log=log)
    files = sorted(frames.glob("*.png"))
    if len(points) != len(files) or not points:
        raise VideoError("RIFE extraction timestamps do not match decoded frames.")
    points = [p - points[0] for p in points]
    info = probe(staged)
    rate = Fraction(job["settings"]["fps"])
    total = math.ceil(info["duration"] * float(rate) - 1e-6)
    native = Fraction(job["settings"]["native_fps"])
    batch_count = len(files) * rate / native
    uniform = len(points) >= 2 and all(abs(p - index / float(native)) <= 0.003 for index, p in enumerate(points))
    batched = uniform and batch_count.denominator == 1
    if batched:
        # The pinned upstream directory adapter uses i * input_count/output_count, matching
        # the target frame grid exactly when input_count * rate/native is integral.
        interpolate_directory(frames, generated, int(batch_count), job["cache"], log)
        produced = sorted(generated.glob("*.png"))
        if len(produced) != int(batch_count):
            raise VideoError("RIFE did not produce every requested intermediate frame.")
        for index in range(len(produced), total):
            shutil.copyfile(produced[-1], generated / f"{index + 1:08d}.png")
    indices = () if batched else range(total)
    for index in indices:
        target = float(index / rate)
        left = min(len(points) - 1, max(0, bisect.bisect_right(points, target) - 1))
        output = generated / f"{index + 1:08d}.png"
        if left == len(points) - 1 or abs(target - points[left]) < 1e-6:
            shutil.copyfile(files[left], output)
        else:
            timestep = (target - points[left]) / (points[left + 1] - points[left])
            interpolate_pair(files[left], files[left + 1], output, timestep, job["cache"], log)
    ffmpeg(["-framerate", str(rate), "-i", generated / "%08d.png", "-an", *encode_args(job, lossless=True), destination], log=log)


def process_segment(job, segment, destination, scratch, staged_shot=None):
    scratch.mkdir(parents=True, exist_ok=False)
    log = scratch.parent / "processing.log"
    s = job["settings"]
    context_a, context_b = segment["context_start"], segment["context_end"]
    source = staged_shot or job["source"]["path"]
    seek = context_a - segment["shot_start"] if staged_shot else context_a
    filters = ([] if staged_shot else prefilters(job)) + ["showinfo", "setpts=PTS-STARTPTS"]
    prepared = scratch / "prepared.mkv"
    preparation = ffmpeg(["-ss", f"{seek:.9f}", "-i", source, "-t", f"{context_b - context_a:.9f}",
            "-map", "0:v:0" if staged_shot else f"0:{job['media']['video_index']}", "-an", "-vf", ",".join(filters),
            "-fps_mode", "passthrough", *encode_args(job, lossless=True), prepared], log=log)
    first_timestamp = re.search(r"pts_time:([\d.eE+-]+)", preparation.stderr)
    source_offset = float(first_timestamp.group(1)) if first_timestamp else 0.0
    current = prepared
    evidence = {"engine": s["engine"], "processing": "conventional" if s["engine"] == "cpu" else "AI"}
    if s["engine"] == "realesrgan":
        inputs, outputs = scratch / "esrgan-in", scratch / "esrgan-out"
        inputs.mkdir()
        points = timestamps(current)
        ffmpeg(["-i", current, "-an", "-fps_mode", "passthrough", inputs / "%08d.png"], log=log)
        evidence = upscale_frames("realesrgan", inputs, outputs, s, job["cache"], log)
        generated = sorted(outputs.glob("*.png"))
        if len(generated) != len(points):
            raise VideoError("Restoration engine did not produce every input frame.")
        # ffconcat durations carry the original VFR timing instead of guessing a mean frame rate.
        manifest = scratch / "restored.ffconcat"
        lines = ["ffconcat version 1.0"]
        for index, path in enumerate(generated):
            # Relative generated filenames contain no user-controlled quote characters.
            lines += [f"file 'esrgan-out/{path.name}'", "option framerate 1000", f"duration {points[index + 1] - points[index] if index + 1 < len(points) else 1 / float(Fraction(s['native_fps'])):.9f}"]
        lines += [f"file 'esrgan-out/{generated[-1].name}'", "option framerate 1000"]
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        current = scratch / "restored.mkv"
        ffmpeg(["-f", "concat", "-safe", "0", "-i", manifest, "-an", "-vf", f"scale={s['width']}:{s['height']}:flags=lanczos,setsar=1",
                "-t", str(probe(prepared)["duration"]), "-fps_mode", "vfr", *encode_args(job, lossless=True), current], log=log)
        if s["style"] == "natural":
            blended = scratch / "blended.mkv"
            ffmpeg(["-i", prepared, "-i", current, "-filter_complex",
                    f"[0:v]scale={s['width']}:{s['height']}:flags=lanczos,setsar=1[a];[a][1:v]blend=all_expr='A*0.65+B*0.35'[v]",
                    "-map", "[v]", "-an", "-fps_mode", "vfr", *encode_args(job, lossless=True), blended], log=log)
            current = blended
            evidence["restoration_blend"] = 0.35
    elif s["engine"] == "seedvr2":
        current = scratch / "restored.mp4"
        # The upstream CLI uses CFR OpenCV input. Normalize explicitly, preserving elapsed time.
        normalized = scratch / "seed-input.mkv"
        ffmpeg(["-i", prepared, "-an", "-vf", f"fps={s['native_fps']}", *encode_args(job, lossless=True), normalized], log=log)
        evidence = seed_video(normalized, current, s, job["cache"], log)
    if s["interpolation"] == "rife":
        interpolated = scratch / "interpolated.mkv"
        rife_video(job, current, interpolated, scratch, log)
        current = interpolated
    final_filters = [f"scale={s['width']}:{s['height']}:flags=lanczos", "setsar=1"]
    if "sharpen" in s["repairs"]:
        final_filters.append("unsharp=5:5:0.3:3:3:0")
    if s["interpolation"] == "motion":
        final_filters.append(f"minterpolate=fps={s['fps']}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff")
    # Pad enough trailing context for minterpolate's latency, then trim to the global output grid.
    # Accurate seeking can start just after the requested point. Account for that offset,
    # then trim by the nearest global-grid frame rather than a rounded fractional timestamp.
    trim_frame = max(0, round((segment["start"] - context_a - source_offset) * float(Fraction(s["fps"]))))
    final_filters += ["tpad=stop_mode=clone:stop_duration=0.2", f"fps={s['fps']}",
                      f"trim=start_frame={trim_frame}", "setpts=PTS-STARTPTS"]
    ffmpeg(["-i", current, "-an", "-vf", ",".join(final_filters), "-frames:v", str(segment["frames"]),
            "-r", s["fps"], "-video_track_timescale", "120000", *encode_args(job), destination], log=log)
    return evidence


def verify(path, job, duration, expected_frames=None, start=0):
    result = probe(path)
    s = job["settings"]
    tolerance = max(0.08, 2 / float(Fraction(s["fps"])))
    errors = []
    if (result["width"], result["height"]) != (s["width"], s["height"]):
        errors.append("Output dimensions differ from the selected dimensions.")
    if abs(float(Fraction(result["fps"])) - float(Fraction(s["fps"]))) > 0.01:
        errors.append("Output frame rate differs from the selected rate.")
    if abs(result["duration"] - duration) > tolerance:
        errors.append(f"Duration drift: expected {duration:.6f}, got {result['duration']:.6f}.")
    if len(result["audio"]) != len(job["media"]["audio"]):
        errors.append("Audio track count changed.")
    for original, actual in zip(job["media"]["audio"], result["audio"]):
        if any(original.get(k) != actual.get(k) for k in ("codec_name", "sample_rate", "channels")):
            errors.append("Audio codec, sample rate, or channel count changed.")
        for tag in ("title", "language"):
            if original.get("tags", {}).get(tag) and original["tags"][tag] != actual.get("tags", {}).get(tag):
                errors.append("Audio label changed: " + tag)
        expected_start = max(0, float(original.get("start_time", 0)) - float(job["media"]["format"].get("start_time", 0)) - start)
        if abs(float(actual.get("start_time", 0)) - expected_start) > 0.15:
            errors.append("Audio start offset differs from the source timeline; inspect synchronization.")
    counts = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "json", path]).stdout)
    frame_count = int(counts["streams"][0]["nb_read_frames"])
    if expected_frames is not None and frame_count != expected_frames:
        errors.append(f"Frame count differs: {frame_count} versus {expected_frames}.")
    ffmpeg(["-v", "error", "-i", path, "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"])
    if errors:
        raise VideoError("Output verification failed: " + " ".join(errors))
    return {"passed": True, "duration": result["duration"], "frames": frame_count,
            "fps": result["fps"], "audio_tracks": len(result["audio"]), "decoded": True,
            "sync_note": "Timing checks passed; verify lip sync visually before accepting the preview."}


def process_range(job, root, start, duration, *, resume=False):
    root.mkdir(parents=True, exist_ok=True)
    state_file = root / "state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not resume or state["signature"] != signature(job) or state["start"] != start or state["duration"] != duration:
            raise VideoError("Run exists or settings changed. Use resume for the same approved job, or make a new preview.")
    else:
        state = {"signature": signature(job), "start": start, "duration": duration, "completed": {}}
    free_space(root, storage_budget(job))
    cuts = state.get("cuts")
    if cuts is None:
        cuts = scene_cuts(job["source"]["path"], job["media"], start=start, duration=duration, log=root / "processing.log")
        state["cuts"] = cuts
        write_json(state_file, state)
    if "stabilize" in job["settings"]["repairs"]:
        boundaries = [start, *cuts, start + duration]
        longest = max(b - a for a, b in zip(boundaries, boundaries[1:]))
        source_pixels = job["media"]["width"] * job["media"]["height"]
        staging = source_pixels * (6 if job["media"]["hdr"] else 3) * float(Fraction(job["settings"]["native_fps"])) * longest
        free_space(root, storage_budget(job) + int(staging))
    segments = plan_segments(start, duration, cuts, job["settings"])
    begun = time.monotonic()
    total_seconds = state.get("elapsed_seconds", 0)
    for index, segment in enumerate(segments):
        key = str(index)
        output = root / f"chunk-{index:06d}.mp4"
        completed = state["completed"].get(key)
        if completed and output.exists() and digest(output) == completed["sha256"]:
            continue
        scratch = root / f"scratch-{index:06d}"
        if scratch.exists():
            # Only runner-created scratch within this job may be discarded on resume.
            if not scratch.resolve().is_relative_to(root.resolve()):
                raise VideoError("Scratch path escaped the job directory.")
            shutil.rmtree(scratch)
        shot_source = None
        if "stabilize" in job["settings"]["repairs"]:
            shot_source = stage_shot(job, root, (segment["shot_start"], segment["shot_end"]), root / "processing.log")
        print(f"Processing segment {index + 1}/{len(segments)} ({segment['start']:.2f}–{segment['end']:.2f}s)", file=sys.stderr, flush=True)
        evidence = process_segment(job, segment, output, scratch, shot_source)
        # Failed/corrupt chunks are never marked complete.
        measured = probe(output)
        if abs(measured["duration"] - segment["frames"] / float(Fraction(job["settings"]["fps"]))) > 0.08:
            raise VideoError("Chunk duration failed verification.")
        state["completed"][key] = {"sha256": digest(output), "segment": segment, "evidence": evidence}
        state["elapsed_seconds"] = total_seconds + time.monotonic() - begun
        write_json(state_file, state)
        shutil.rmtree(scratch)
        if shot_source and (index == len(segments) - 1 or segments[index + 1]["shot"] != segment["shot"]):
            Path(shot_source).unlink(missing_ok=True)
    concatenation = root / "chunks.ffconcat"
    concatenation.write_text("ffconcat version 1.0\n" + "\n".join(f"file 'chunk-{i:06d}.mp4'" for i in range(len(segments))) + "\n", encoding="utf-8")
    destination = root / ("enhanced." + job["settings"]["container"])
    # Output-side audio seeking discards preceding packets; input-side stream-copy seeking can
    # retain pre-roll and shift a short preview's entire timeline by the seek amount.
    audio_source = job["source"]["path"]
    if job["media"]["audio"]:
        audio_source = root / "original-audio.mka"
        ffmpeg(["-i", job["source"]["path"], "-ss", f"{start:.9f}", "-t", f"{duration:.9f}",
                "-map", "0:a", "-map_metadata", "0", "-map_chapters", "-1", "-c:a", "copy",
                "-avoid_negative_ts", "disabled", audio_source], log=root / "processing.log")
    ffmpeg(["-copyts", "-f", "concat", "-safe", "1", "-i", concatenation,
            "-i", audio_source, "-map", "0:v:0", "-map", "1:a?", "-map_metadata", "1",
            "-map_chapters", "-1", "-c", "copy", "-t", f"{duration:.9f}", "-avoid_negative_ts", "disabled",
            "-metadata:s:v:0", "rotate=0", destination], log=root / "processing.log")
    verification = verify(destination, job, duration, sum(s["frames"] for s in segments), start=start)
    state["output"] = str(destination)
    state["verification"] = verification
    state["elapsed_seconds"] = total_seconds + time.monotonic() - begun
    write_json(state_file, state)
    return state


def comparison(job, treated, root, start, duration):
    original = root / "original.mp4"
    ffmpeg(["-ss", str(start), "-i", job["source"]["path"], "-t", str(duration),
            "-map", f"0:{job['media']['video_index']}", "-an", "-vf", "scale=-2:360,setsar=1",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", original])
    compare = root / "comparison.mp4"
    # Both halves show the same instants and geometry. Text labeling is in the HTML, avoiding font dependencies.
    ffmpeg(["-i", original, "-i", treated, "-filter_complex",
            "[0:v]scale=-2:360,setsar=1[left];[1:v]scale=-2:360,setsar=1[right];[left][right]hstack=shortest=1[v]",
            "-map", "[v]", "-an", "-t", str(duration), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", compare])
    (root / "review.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Enhancement preview</title>'
        '<style>body{font:18px system-ui;background:#161616;color:#eee;max-width:1200px;margin:32px auto}video{width:100%}</style>'
        '<h1>Original (left) / Enhanced (right)</h1><video controls loop src="comparison.mp4"></video>'
        '<p>Compare faces, skin, text, fine patterns, motion and scene cuts. This comparison is muted; '
        'the enhanced file retains every source audio track. Check lip sync in that file.</p>', encoding="utf-8")
    return str(compare)


def preview(args):
    folder, job = load_job(args.job)
    with job_lock(folder):
        check_source(job)
        job["settings"] = settings_from_args(args, job)
        job["approval"] = None
        job["preview"] = None
        require_filters(job)
        write_json(folder / "job.json", job)
        starts = [float(x) for x in args.starts.split(",")]
        if not starts or any(not math.isfinite(x) or x < 0 or x >= job["media"]["duration"] for x in starts):
            raise VideoError("Preview start times must lie within the recording.")
        if not 0.2 <= args.seconds <= 30:
            raise VideoError("Preview duration must be 0.2–30 seconds.")
        root = folder / ("preview-" + signature(job)[:12] + "-" + str(time.time_ns()))
        records = []
        for index, start in enumerate(starts):
            duration = min(args.seconds, job["media"]["duration"] - start)
            target = root / f"sample-{index + 1}"
            state = process_range(job, target, start, duration)
            compare = comparison(job, state["output"], target, start, duration)
            records.append({"start": start, "seconds": duration, "output": state["output"],
                            "comparison": compare, "review": str(target / "review.html"),
                            "elapsed_seconds": state["elapsed_seconds"], "bytes": Path(state["output"]).stat().st_size,
                            "verification": state["verification"]})
        elapsed, seconds = sum(r["elapsed_seconds"] for r in records), sum(r["seconds"] for r in records)
        estimated = elapsed / seconds * job["media"]["duration"]
        job["preview"] = {"signature": signature(job), "samples": records,
                          "estimated_full_seconds": estimated, "estimate_range_seconds": [estimated * 0.7, estimated * 1.8],
                          "estimated_output_bytes": int(sum(r["bytes"] for r in records) / seconds * job["media"]["duration"]),
                          "peak_storage_budget_bytes": storage_budget(job), "status": "visual_review_pending",
                          "note": "Estimate includes sample processing; GPU load, startup and shot complexity affect full renders."}
        check_source(job)
        write_json(folder / "job.json", job)
        write_json(root / "report.json", job)
        return job["preview"]


def render(args, resume=False):
    folder, job = load_job(args.job)
    with job_lock(folder):
        check_source(job)
        preview_info = job.get("preview")
        current = signature(job)
        if not preview_info or preview_info["signature"] != current:
            raise VideoError("A successful preview matching these settings is required.")
        if resume:
            if job.get("approval") != current:
                raise VideoError("No matching full-render approval was saved.")
        elif args.accept_preview != current:
            raise VideoError("After user review, pass --accept-preview with the preview signature.")
        # A replacement binary/model environment requires a fresh preview.
        for name, old in job["settings"]["engine_receipts"].items():
            if resolve(name, job["cache"]) != old:
                raise VideoError("Engine installation changed. Create and review a new preview.")
        require_filters(job)
        job["approval"] = current
        write_json(folder / "job.json", job)
        state = process_range(job, folder / "render", 0, job["media"]["duration"], resume=resume)
        check_source(job)
        report = {"status": "technical_checks_passed_visual_review_pending", "source_unchanged": True,
                  "source_sha256": job["source"]["sha256"], "settings": job["settings"],
                  "preview_signature": current, **state}
        write_json(folder / "render" / "report.json", report)
        return report


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    d = commands.add_parser("doctor", help="Inspect tools, hardware and optional engine receipts")
    d.add_argument("--cache", type=Path, default=default_cache())
    s = commands.add_parser("setup", help="Print a setup plan; --install performs the selected setup")
    s.add_argument("--engine", choices=("cpu", "realesrgan", "rife", "seedvr2"), required=True)
    s.add_argument("--cache", type=Path, default=default_cache())
    s.add_argument("--install", action="store_true")
    s.add_argument("--torch-backend", choices=("cuda128", "mps"))
    a = commands.add_parser("analyze", help="Create a new job, sample frames and repair suggestions")
    a.add_argument("--input", type=Path, required=True)
    a.add_argument("--job", type=Path, required=True)
    a.add_argument("--cache", type=Path, default=default_cache())
    p = commands.add_parser("preview", help="Process comparison excerpts, never the full recording")
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--style", choices=("natural", "strong"), required=True)
    p.add_argument("--engine", choices=("cpu", "realesrgan", "seedvr2"), required=True)
    p.add_argument("--repairs", default="", help="Comma-separated selected repairs; none applied implicitly")
    p.add_argument("--height", default="source", help="source, 720, 1080, 2160, or another target height")
    p.add_argument("--fps", default="source", help="source, 60, 60000/1001, etc.")
    p.add_argument("--interpolation", choices=("none", "motion", "rife"), default="none")
    p.add_argument("--container", choices=("mkv", "mp4"), default="mkv")
    p.add_argument("--starts", default="0", help="Comma-separated excerpt starts in seconds")
    p.add_argument("--seconds", type=float, default=10)
    p.add_argument("--exposure", type=float, default=0, help="Restrained brightness lift, -2..2; see repair reference")
    p.add_argument("--gamma", type=float, default=1)
    for channel in ("red", "green", "blue"):
        p.add_argument("--" + channel, type=float, default=0)
    p.add_argument("--hdr", choices=("ask", "preserve", "sdr"), default="ask")
    p.add_argument("--field-order", choices=("auto", "tff", "bff"), default="auto")
    p.add_argument("--chunk-seconds", type=float, default=5)
    p.add_argument("--overlap", type=float, default=0.5)
    p.add_argument("--tile", type=int, default=128)
    p.add_argument("--batch", type=int, default=17)
    p.add_argument("--blocks-to-swap", type=int, default=16)
    p.add_argument("--seed-model", choices=("seedvr2_ema_3b_fp16.safetensors", "seedvr2_ema_7b_fp16.safetensors"),
                   default="seedvr2_ema_3b_fp16.safetensors")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--stabilize-zoom", type=float, default=2)
    r = commands.add_parser("render", help="Render only after the exact preview was accepted")
    r.add_argument("--job", type=Path, required=True)
    r.add_argument("--accept-preview", required=True)
    r = commands.add_parser("resume", help="Resume the same approved full render")
    r.add_argument("--job", type=Path, required=True)
    return root


def main():
    args = parser().parse_args()
    try:
        if args.command == "doctor":
            value = doctor(args.cache)
        elif args.command == "setup":
            value = setup(args.engine, args.cache, install=args.install, torch_backend=args.torch_backend)
        elif args.command == "analyze":
            value = analyze(args.input, args.job, args.cache)
        elif args.command == "preview":
            value = preview(args)
        else:
            value = render(args, resume=args.command == "resume")
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return 0
    except (VideoError, OSError, ValueError, KeyError, StopIteration) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
