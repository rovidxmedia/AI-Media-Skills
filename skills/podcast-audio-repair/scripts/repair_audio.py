"""Local, reviewable speech repair with originals, commands, and comparisons.

Requires FFmpeg/ffprobe, NumPy, SciPy, SoundFile, and click for optional WPE.
No network requests, account access, uploads, deletion, or source overwrites.
"""
from __future__ import annotations

import argparse
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

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
import soundfile as sf
from scipy import signal

SKILL = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(command, report, cwd=None):
    result = subprocess.run([str(v) for v in command], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    report["commands"].append({"argv": [str(v) for v in command], "cwd": str(cwd) if cwd else None, "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError(result.stderr[-8000:])
    return result.stdout, result.stderr


def ffmpeg(args, report):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-n", *args], report, cwd=SKILL)


def measure(path, report):
    _, log = ffmpeg(["-i", path, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], report)
    matches = re.findall(r'\{\s*"input_i".*?\}', log, re.S)
    if not matches:
        raise RuntimeError("FFmpeg did not return loudness measurements")
    values = json.loads(matches[-1])
    return {k: float(v) if k != "normalization_type" else v for k, v in values.items()}


def align_denoised(raw_path, enhanced_path, output_path):
    raw, sr = sf.read(raw_path, always_2d=True)
    enhanced, out_sr = sf.read(enhanced_path, always_2d=True)
    if sr != out_sr or raw.shape != enhanced.shape:
        raise RuntimeError("Denoiser output shape changed unexpectedly")
    if not np.isfinite(enhanced).all() or np.max(np.abs(enhanced)) >= 0.999999:
        raise RuntimeError("Denoised intermediate may have clipped; lower the working input gain before retrying")
    # RNNoise in the tested FFmpeg build adds 480 samples at 48 kHz. Measure
    # rather than assuming the delay across builds, models, or sample content.
    count = min(len(raw), 12 * sr)
    x = raw[:count].mean(axis=1)
    y = enhanced[:count].mean(axis=1)
    corr = signal.correlate(y, x, mode="full", method="fft")
    lags = signal.correlation_lags(len(y), len(x))
    valid = np.abs(lags) <= int(0.040 * sr)
    lag = int(lags[valid][np.argmax(corr[valid])])
    if lag > 0:
        aa, bb = x[:-lag], y[lag:]
    elif lag < 0:
        aa, bb = x[-lag:], y[:lag]
    else:
        aa, bb = x, y
    confidence = float(np.dot(aa, bb) / max(np.linalg.norm(aa) * np.linalg.norm(bb), 1e-20))
    if confidence < 0.35:
        raise RuntimeError("Cannot establish denoiser latency confidently; preserve the intermediate and review timing manually")
    if lag > 0:
        fixed = np.pad(enhanced[lag:], ((0, lag), (0, 0)))
    elif lag < 0:
        fixed = np.pad(enhanced[:lag], ((-lag, 0), (0, 0)))
    else:
        fixed = enhanced
    sf.write(output_path, fixed, sr, subtype="FLOAT")
    return {"samples": lag, "seconds": lag / sr, "correlation": confidence, "edge_padding_samples": abs(lag)}


def dereverberate(source, dest, strength, taps, iterations):
    sys.path.insert(0, str(SKILL / "assets" / "python"))
    from nara_wpe.wpe import wpe_v8

    x, sr = sf.read(source, always_2d=True)
    low = signal.resample_poly(x, 1, 3, axis=0)
    spectra = []
    for channel in low.T:
        _, _, stft = signal.stft(channel, fs=16000, nperseg=512, noverlap=384)
        spectra.append(stft)
    y = np.stack(spectra, axis=1)
    z = wpe_v8(y, taps=taps, delay=3, iterations=iterations, statistics_mode="full")
    clean = []
    for channel in range(x.shape[1]):
        _, waveform = signal.istft(z[:, channel, :], fs=16000, nperseg=512, noverlap=384)
        clean.append(waveform[:len(low)])
    clean = np.stack(clean, axis=1)
    # Keep the original high-frequency band; apply only the WPE correction
    # estimated below 8 kHz. This avoids a 16 kHz low-pass on the whole file.
    correction = signal.resample_poly(low - clean, 3, 1, axis=0)[:len(x)]
    result = x - strength * correction
    if not np.isfinite(result).all():
        raise RuntimeError("Non-finite WPE output; do not use this repair")
    sf.write(dest, result, sr, subtype="FLOAT")
    return {"algorithm": "NARA-WPE 0.0.11; conventional statistical dereverberation", "analysis_rate": 16000, "taps": taps, "delay_frames": 3, "iterations": iterations, "strength": strength, "preserve_original_high_band": True}


def comparisons(before, after, before_stats, after_stats, out, report, seconds, start):
    # Match with constant gain only; no dynamics or noise processing is added
    # to the previews. A low common target avoids clipping either version.
    target = min(-18.0,
                 before_stats["input_i"] + (-2 - before_stats["input_tp"]),
                 after_stats["input_i"] + (-2 - after_stats["input_tp"]))
    for source, stats, name in ((before, before_stats, "input-matched.wav"), (after, after_stats, "output-matched.wav")):
        gain = target - stats["input_i"]
        ffmpeg(["-i", source, "-af", f"volume={gain:.6f}dB", "-c:a", "pcm_s24le", out / name], report)
    a, sr = sf.read(out / "input-matched.wav", always_2d=True)
    b, _ = sf.read(out / "output-matched.wav", always_2d=True)
    offset, n = int(start * sr), int(seconds * sr)
    a, b = a[offset:offset+n], b[offset:offset+n]
    gap = np.zeros((int(0.75 * sr), a.shape[1]))
    sf.write(out / "comparison.wav", np.concatenate([a, gap, b]), sr, subtype="PCM_24")
    ffmpeg(["-i", out / "comparison.wav", "-c:a", "libmp3lame", "-b:a", "160k", out / "comparison.mp3"], report)
    return {"order": "input, 0.75 seconds silence, output", "excerpt_start_seconds": start, "excerpt_seconds_each": len(a) / sr, "whole_file_match_target_lufs": target, "matching": "constant gain using integrated loudness; not a perceptual quality verdict"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--seconds", type=float, default=30, help="Maximum sample length; defaults to 30 seconds")
    parser.add_argument("--full", action="store_true", help="Explicitly process the complete remaining recording")
    parser.add_argument("--audio-stream", type=int, default=0)
    parser.add_argument("--denoise", choices=("off", "neural", "spectral"), default="off")
    parser.add_argument("--noise-mix", type=float, default=0.9)
    parser.add_argument("--noise-reduction", type=float, default=12, help="Maximum spectral noise reduction in dB")
    parser.add_argument("--noise-floor", type=float, default=-36, help="Initial spectral noise floor, dBFS; inspect the recording")
    parser.add_argument("--dereverb", action="store_true", help="Experimental WPE; review separately before using")
    parser.add_argument("--echo-strength", type=float, default=0.8)
    parser.add_argument("--wpe-taps", type=int, default=16)
    parser.add_argument("--wpe-iterations", type=int, default=3)
    parser.add_argument("--level", action="store_true")
    parser.add_argument("--target-lufs", type=float, default=-16, help="Chosen export target, not a universal platform requirement")
    parser.add_argument("--comparison-seconds", type=float, default=10)
    parser.add_argument("--comparison-start", type=float, default=1)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Input file does not exist")
    if args.start < 0 or args.seconds <= 0 or args.comparison_seconds <= 0 or args.comparison_start < 0:
        parser.error("Invalid time range")
    if not (0 <= args.noise_mix <= 1 and 0 <= args.echo_strength <= 1):
        parser.error("Mix/strength must be between zero and one")
    if not (1 <= args.noise_reduction <= 30 and -80 <= args.noise_floor <= -20):
        parser.error("Spectral noise parameters out of supported range")
    if not (-30 <= args.target_lufs <= -10) or not (1 <= args.wpe_taps <= 40) or not (1 <= args.wpe_iterations <= 10):
        parser.error("Unsupported target or WPE configuration")
    for program in ("ffmpeg", "ffprobe"):
        if not shutil.which(program):
            parser.error(f"{program} is not available on PATH")
    if args.denoise == "neural" and not (SKILL / "assets" / "cb.rnnn").is_file():
        parser.error("Bundled RNNoise model is missing")
    source = args.input.resolve()
    out = args.output_dir.resolve()
    if out.exists():
        parser.error("Output directory already exists; choose a new run directory")
    report = {"source": str(source), "source_sha256_before": sha256(source), "arguments": vars(args).copy(), "commands": [], "operations": [], "listening_review": "pending", "warnings": []}
    report["arguments"] = {k: str(v) if isinstance(v, Path) else v for k, v in report["arguments"].items()}
    started = time.monotonic()
    out.mkdir(parents=True)
    try:
        stdout, _ = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", source], report)
        report["source_probe"] = json.loads(stdout)
        streams = [s for s in report["source_probe"]["streams"] if s["codec_type"] == "audio"]
        if args.audio_stream < 0 or args.audio_stream >= len(streams):
            raise ValueError("Selected audio stream is unavailable")
        channels = streams[args.audio_stream]["channels"]
        if channels not in (1, 2):
            raise ValueError("Only mono/stereo input is supported; do not silently downmix multichannel material")
        stdout, _ = run(["ffmpeg", "-version"], report)
        report["ffmpeg_version"] = stdout.splitlines()[0]
        report["python_version"] = sys.version
        report["model_sha256"] = sha256(SKILL / "assets" / "cb.rnnn") if args.denoise == "neural" else None
        sample = out / "input.wav"
        extract = ["-ss", args.start, "-i", source]
        if not args.full:
            extract += ["-t", args.seconds]
        extract += ["-map", f"0:a:{args.audio_stream}", "-vn", "-ar", 48000, "-ac", channels, "-c:a", "pcm_s24le", sample]
        ffmpeg(extract, report)
        current = sample
        if args.denoise != "off":
            neural = out / "01-denoise-with-latency.wav"
            # With the tested FFmpeg 7.0 build, the float WAV encoder changes
            # filter negotiation and materially changes arnndn behavior. The
            # verified 24-bit path is retained; reject near-clipped output.
            if args.denoise == "neural":
                effect = f"arnndn=m=assets/cb.rnnn:mix={args.noise_mix}"
                operation = {"algorithm": "FFmpeg arnndn; recurrent-neural noise suppression", "mix": args.noise_mix}
            else:
                effect = f"afftdn=nr={args.noise_reduction}:nf={args.noise_floor}:tn=1:gs=5"
                operation = {"algorithm": "FFmpeg afftdn; conventional spectral noise reduction", "filter": effect}
            ffmpeg(["-i", current, "-af", effect, "-c:a", "pcm_s24le", neural], report)
            aligned = out / "02-denoise-aligned.wav"
            report["denoise_latency_compensation"] = align_denoised(current, neural, aligned)
            report["operations"].append(operation)
            report["warnings"].append("Denoiser latency compensation trims/pads an edge; check the first/last spoken sounds. The untouched original remains available.")
            current = aligned
        if args.dereverb:
            dest = out / "03-dereverb.wav"
            report["operations"].append(dereverberate(current, dest, args.echo_strength, args.wpe_taps, args.wpe_iterations))
            report["warnings"].append("WPE is experimental on single-channel speech. A completed run does not establish an audible or acceptable repair.")
            current = dest
        if args.level:
            dest = out / "04-levels.wav"
            effect = "dynaudnorm=f=250:g=15:p=0.89:m=8:r=0.12:n=true"
            ffmpeg(["-i", current, "-af", effect, "-c:a", "pcm_f32le", dest], report)
            report["operations"].append({"algorithm": "FFmpeg dynaudnorm; conventional dynamic leveling", "filter": effect})
            current = dest
        stats = measure(current, report)
        if not all(math.isfinite(stats[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh")):
            raise RuntimeError("Silent or unmeasurable sample; no loudness repair produced")
        # A dynamic loudnorm fallback raised quiet residual noise in the first
        # controlled tests. Use constant gain with peak headroom instead. If
        # both requested loudness and the peak ceiling cannot be met, preserve
        # dynamics and report the lower achieved loudness honestly.
        requested_gain = args.target_lufs - stats["input_i"]
        gain = min(requested_gain, -1.6 - stats["input_tp"])
        effect = f"volume={gain:.8f}dB"
        final = out / "repaired.wav"
        ffmpeg(["-i", current, "-af", effect, "-ar", 48000, "-c:a", "pcm_s24le", final], report)
        report["operations"].append({"algorithm": "Measured constant gain; conventional export normalization", "requested_target_lufs": args.target_lufs, "true_peak_ceiling_db": -1.6, "gain_db": gain, "target_limited_by_peak_headroom": gain < requested_gain - 0.01})
        if gain < requested_gain - 0.01:
            report["warnings"].append("Peak headroom limits the export below requested loudness. Dynamics were preserved; do not claim the target was achieved.")
        report["before"] = measure(sample, report)
        report["after"] = measure(final, report)
        audio, sr = sf.read(final, always_2d=True)
        original, _ = sf.read(sample, always_2d=True)
        if not np.isfinite(audio).all() or audio.shape != original.shape or np.max(np.abs(audio)) >= 1:
            raise RuntimeError("Export failed shape, finite-sample, or clipping checks")
        if report["after"]["input_tp"] > -1.0:
            raise RuntimeError("Export true peak exceeds the verification ceiling")
        if args.comparison_start >= len(audio) / sr:
            raise RuntimeError("Comparison start lies outside the sample")
        report["comparison"] = comparisons(sample, final, report["before"], report["after"], out, report, args.comparison_seconds, args.comparison_start)
        report["source_sha256_after"] = sha256(source)
        if report["source_sha256_before"] != report["source_sha256_after"]:
            raise RuntimeError("Source file changed during processing")
        report["source_unchanged"] = True
        report["duration_seconds"] = len(audio) / sr
        report["status"] = "technical_checks_passed_listening_pending"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "status": report["status"], "elapsed_seconds": round(report["elapsed_seconds"], 2), "source_unchanged": True, "loudness_lufs": report["after"]["input_i"], "true_peak_db": report["after"]["input_tp"]}))


if __name__ == "__main__":
    main()
