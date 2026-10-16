"""Broadcast-style speech processing using the sibling repair skill's utilities."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
import soundfile as sf

PRESETS = {
    "big": dict(body_db=3.5, mud_db=-3.0, presence_db=2.5,
                compression_ratio=4.0, compression_threshold_db=-24.0,
                attack_ms=10, release_ms=130, exciter_amount=1.8,
                exciter_drive=4.5, deess_intensity=0.15),
    "warm": dict(body_db=2.0, mud_db=-2.0, presence_db=1.0,
                 compression_ratio=2.5, compression_threshold_db=-22.0,
                 attack_ms=18, release_ms=160, exciter_amount=0.8,
                 exciter_drive=3.0, deess_intensity=0.12),
}


def load_utilities(path):
    if not path.is_file():
        raise RuntimeError("Install current podcast-audio-repair alongside this skill or select its script with --repair-helper")
    spec = importlib.util.spec_from_file_location("radio_repair_utilities", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("measure", "export_loudness", "comparisons", "ffmpeg", "run", "sha256"):
        if not callable(getattr(module, name, None)):
            raise RuntimeError("Outdated podcast-audio-repair helper: missing " + name)
    return module


def linear(db):
    return 10 ** (db / 20)


def envelope(path):
    """Stream 10 ms windows; these measurements do not detect speech."""
    info = sf.info(path)
    window = info.samplerate // 100
    values, peak = [], 0.0
    for block in sf.blocks(path, blocksize=window * 1000, always_2d=True):
        if not np.isfinite(block).all():
            raise RuntimeError("Non-finite processing samples")
        peak = max(peak, float(np.max(np.abs(block))))
        count = len(block) // window
        if count:
            x = block[:count * window].reshape(count, window, info.channels)
            values.extend(np.sqrt(np.mean(x * x, axis=(1, 2))).tolist())
    if not values:
        raise RuntimeError("Audio is too short to analyze")
    db = 20 * np.log10(np.maximum(values, 1e-12))
    return {"window_seconds": 0.01, "window_rms_dbfs_percentiles": dict(zip(
        ("p5", "p10", "p25", "p50", "p90", "p95"),
        np.percentile(db, [5, 10, 25, 50, 90, 95]).tolist())),
        "sample_peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
        "frames": info.frames, "channels": info.channels}


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--repair-helper", type=Path, default=Path(__file__).resolve().parents[2] / "podcast-audio-repair" / "scripts" / "repair_audio.py")
    parser.add_argument("--preset", choices=PRESETS, default="big")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--target-lufs", type=float, default=-14)
    parser.add_argument("--gate-threshold-db", type=float, default=-50)
    parser.add_argument("--gate-reduction-db", type=float, default=12)
    parser.add_argument("--no-gate", action="store_true")
    parser.add_argument("--no-exciter", action="store_true")
    for name in ("body-db", "presence-db", "compression-ratio", "exciter-amount"):
        parser.add_argument("--" + name, type=float)
    parser.add_argument("--comparison-start", type=float, default=1)
    parser.add_argument("--comparison-seconds", type=float, default=20)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Input audio does not exist")
    if any(not math.isfinite(v) for v in (args.start, args.seconds, args.target_lufs, args.gate_threshold_db, args.gate_reduction_db, args.comparison_start, args.comparison_seconds)):
        parser.error("Numeric arguments must be finite")
    if args.start < 0 or args.seconds <= 0 or args.comparison_start < 0 or args.comparison_seconds <= 0:
        parser.error("Invalid time range")
    if not -20 <= args.target_lufs <= -12:
        parser.error("Choose a target between -20 and -12 LUFS")
    if not -75 <= args.gate_threshold_db <= -30 or not 0 <= args.gate_reduction_db <= 24:
        parser.error("Gate controls outside supported range")
    settings = PRESETS[args.preset].copy()
    for key, limits in dict(body_db=(-3, 6), presence_db=(-3, 6), compression_ratio=(1, 8), exciter_amount=(0, 4)).items():
        value = getattr(args, key)
        if value is not None:
            if not math.isfinite(value) or not limits[0] <= value <= limits[1]:
                parser.error("Unsupported " + key)
            settings[key] = value
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            parser.error(name + " is not available on PATH")
    repair = load_utilities(args.repair_helper.resolve())
    out = args.output_dir.resolve()
    if out.exists():
        parser.error("Output directory already exists; choose a new run directory")
    source = args.input.resolve()
    report = {"source": str(source), "source_sha256_before": repair.sha256(source),
              "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "preset_settings": settings, "dependency_helper_sha256": repair.sha256(args.repair_helper),
              "commands": [], "operations": [], "warnings": [], "listening_review": "pending",
              "stage_envelopes": {}}
    out.mkdir(parents=True)
    started = time.monotonic()
    try:
        stdout, _ = repair.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", source], report)
        streams = [v for v in json.loads(stdout)["streams"] if v["codec_type"] == "audio"]
        if len(streams) != 1 or streams[0]["channels"] not in (1, 2):
            raise RuntimeError("Select mono/stereo audio with exactly one stream; do not silently mix speakers or channels")
        channels = streams[0]["channels"]
        stdout, _ = repair.run(["ffmpeg", "-hide_banner", "-filters"], report)
        available = {line.split()[1] for line in stdout.splitlines() if len(line.split()) >= 3}
        for name in ("volume", "highpass", "agate", "equalizer", "acompressor", "aexciter", "deesser", "alimiter", "aresample", "loudnorm"):
            if name not in available:
                raise RuntimeError("This FFmpeg build lacks " + name)
        stdout, _ = repair.run(["ffmpeg", "-version"], report)
        report["ffmpeg_version"] = stdout.splitlines()[0]
        original = out / "input.wav"
        extract = ["-ss", args.start, "-i", source]
        if not args.full:
            extract += ["-t", args.seconds]
        repair.ffmpeg([*extract, "-map", "0:a:0", "-vn", "-ar", 48000, "-ac", channels, "-c:a", "pcm_s24le", original], report)
        report["before"] = repair.measure(original, report)
        if not math.isfinite(report["before"]["input_i"]):
            raise RuntimeError("Silent or unmeasurable source; no radio master produced")
        input_info = sf.info(original)
        if args.comparison_start >= input_info.duration:
            raise RuntimeError("Comparison starts beyond selected audio")

        def stage(name, source_path, effect, description):
            destination = out / name
            repair.ffmpeg(["-i", source_path, "-af", effect, "-c:a", "pcm_f32le", destination], report)
            info = sf.info(destination)
            if (info.samplerate, info.frames, info.channels) != (input_info.samplerate, input_info.frames, input_info.channels):
                raise RuntimeError("Processing changed timing or channels at " + name)
            report["operations"].append({"stage": name, "description": description, "filter": effect})
            report["stage_envelopes"][name] = envelope(destination)
            return destination

        gain = -20 - report["before"]["input_i"]
        current = stage("00-staged.wav", original, f"volume={gain:.8f}dB,highpass=f=65:p=2", "Constant input gain to -20 LUFS followed by rumble filtering")
        if not args.no_gate:
            effect = f"agate=threshold={linear(args.gate_threshold_db):.10f}:ratio=2.5:range={linear(-args.gate_reduction_db):.10f}:attack=2:release=180:knee=2.828427:link=maximum:detection=rms"
            current = stage("01-gated.wav", current, effect, "Soft linked downward gate with bounded attenuation")
        effect = f"equalizer=f=120:t=q:w=0.7:g={settings['body_db']},equalizer=f=320:t=q:w=0.9:g={settings['mud_db']},equalizer=f=3000:t=q:w=0.7:g={settings['presence_db']}"
        current = stage("02-tone.wav", current, effect, "Body, low-mid cleanup, and presence EQ")
        effect = f"acompressor=threshold={linear(settings['compression_threshold_db']):.10f}:ratio={settings['compression_ratio']}:attack={settings['attack_ms']}:release={settings['release_ms']}:knee=2.828427:makeup=1:link=maximum:detection=rms:mix=1"
        current = stage("03-compressed.wav", current, effect, "Linked soft-knee compression for speech density")
        if not args.no_exciter and settings["exciter_amount"] > 0:
            effect = f"aexciter=amount={settings['exciter_amount']}:drive={settings['exciter_drive']}:blend=0:freq=3500:ceil=12000:level_in=1:level_out=1,deesser=i={settings['deess_intensity']}:m=0.25:f=0.5:s=o"
            current = stage("04-excited.wav", current, effect, "Upper harmonic excitement with light de-essing")
        final = out / "radio-voice.wav"
        print("Mastering the radio chain", flush=True)
        report["after"] = repair.export_loudness(current, final, args.target_lufs, "speech", report)
        info = sf.info(final)
        if (info.samplerate, info.frames, info.channels) != (input_info.samplerate, input_info.frames, input_info.channels):
            raise RuntimeError("Mastering changed exact timing or channel count")
        for block in sf.blocks(final, blocksize=480000, always_2d=True):
            if not np.isfinite(block).all() or np.max(np.abs(block)) >= 1:
                raise RuntimeError("Master contains clipped or non-finite samples")
        report["comparison"] = repair.comparisons(original, final, report["before"], report["after"], out, report, args.comparison_seconds, args.comparison_start)
        print("Encoding the MP3 listening copy", flush=True)
        repair.ffmpeg(["-i", final, "-c:a", "libmp3lame", "-b:a", "256k", out / "radio-voice.mp3"], report)
        report["mp3"] = repair.measure(out / "radio-voice.mp3", report)
        if report["mp3"]["input_tp"] >= 0:
            raise RuntimeError("MP3 true peak exceeds available headroom")
        repair.ffmpeg(["-v", "error", "-xerror", "-i", out / "radio-voice.mp3", "-f", "null", "-"], report)
        report["source_sha256_after"] = repair.sha256(source)
        if report["source_sha256_before"] != report["source_sha256_after"]:
            raise RuntimeError("Source changed during processing")
        report["source_unchanged"] = True
        report["output_sha256"] = {name: repair.sha256(out / name) for name in ("radio-voice.wav", "radio-voice.mp3")}
        report["duration_seconds"] = info.duration
        report["status"] = "technical_and_loudness_checks_passed_listening_pending"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        (out / "report.json").write_text(json.dumps(json_safe(report), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "status": report["status"], "loudness_lufs": report["after"]["input_i"], "true_peak_db": report["after"]["input_tp"], "source_unchanged": True}))


if __name__ == "__main__":
    main()
