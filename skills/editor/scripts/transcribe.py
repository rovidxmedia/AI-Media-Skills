"""Run only inside the optional isolated Faster-Whisper environment."""
import argparse
import importlib.metadata
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    for name in ("audio", "output", "source-sha256", "model", "cache"):
        p.add_argument("--"+name, required=True)
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--language")
    p.add_argument("--download-model", action="store_true")
    args = p.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device,
        compute_type="int8" if args.device == "cpu" else "float16",
        download_root=args.cache, local_files_only=not args.download_model)
    segments, info = model.transcribe(args.audio, word_timestamps=True, language=args.language,
                                      vad_filter=False, condition_on_previous_text=False, beam_size=5)
    words = []
    for segment in segments:
        for w in segment.words or []:
            if w.end > w.start:
                words.append({"word": w.word.strip(), "start": w.start+args.start,
                              "end": min(args.end, w.end+args.start), "probability": w.probability})
    data = {"source_sha256": args.source_sha256, "coverage": [args.start, args.end], "words": words,
            "engine": "faster-whisper", "provenance": {"version": importlib.metadata.version("faster-whisper"),
                "model": args.model, "device": args.device, "language": info.language,
                "warning": "ASR may omit fillers or hallucinate words; word timing/probability is not proof of a safe edit"}}
    Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
