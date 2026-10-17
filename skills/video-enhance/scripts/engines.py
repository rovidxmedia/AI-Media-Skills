"""Optional local engines. No downloads or heavyweight imports at import time."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile


class VideoError(RuntimeError):
    pass


HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parent / "references" / "engines.json"
SEED_COMMIT = "4490bd1f482e026674543386bb2a4d176da245b9"


def absolute(path):
    # Normalize dot segments before resolving junctions (also important in Windows sandbox hosts).
    return Path(os.path.abspath(path)).resolve()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(command, *, cwd=None, timeout=None, log=None, allowed=(0,)):
    """Use argument arrays on every OS, including paths containing shell characters."""
    command = [str(x) for x in command]
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoError(f"Cannot run {Path(command[0]).name}: {exc}") from exc
    if log:
        with Path(log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(command, ensure_ascii=False) + "\n")
            stream.write(result.stdout[-12000:] + result.stderr[-24000:] + "\n")
    if result.returncode not in allowed:
        raise VideoError(f"{Path(command[0]).name} exited {result.returncode}:\n"
                         + (result.stderr or result.stdout)[-6000:])
    return result


def default_cache():
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "ai-media-skills" / "video-enhance"


def system_key():
    return {"Windows": "windows", "Darwin": "macos", "Linux": "ubuntu"}.get(platform.system())


def free_space(path, needed):
    existing = absolute(path)
    while not existing.exists():
        existing = existing.parent
    free = shutil.disk_usage(existing).free
    if free < needed:
        raise VideoError(f"Insufficient storage: need about {needed / 2**30:.2f} GiB, "
                         f"have {free / 2**30:.2f} GiB at {existing}.")
    return free


def safe_extract(archive, destination):
    """Reject traversal, absolute paths, and symlinks before extracting anything."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination) or "\\" in entry.filename:
                raise VideoError("Unsafe archive member: " + entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise VideoError("Archive symlinks are unsupported: " + entry.filename)
        free_space(destination, sum(e.file_size for e in zipped.infolist()) + 32 * 2**20)
        zipped.extractall(destination)


def download(url, path, expected_hash):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and digest(path) == expected_hash:
        return
    partial = path.with_suffix(path.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "AI-Media-Skills/video-enhance"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        if digest(partial) != expected_hash:
            raise VideoError("Download SHA-256 mismatch: " + url)
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def setup_plan(engine, cache, torch_backend=None):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    key = system_key()
    if key is None:
        raise VideoError("Supported systems: Windows, macOS, Linux.")
    if engine == "cpu":
        return {"engine": "cpu", "downloads": [], "requirements": ["Python 3.10+", "FFmpeg", "ffprobe"],
                "license": "FFmpeg build-dependent; installed separately", "cache": str(cache)}
    if engine == "seedvr2":
        if torch_backend not in ("cuda128", "mps"):
            raise VideoError("SeedVR2 setup needs --torch-backend cuda128 or mps. Benchmark before use.")
        if torch_backend == "mps" and sys.platform != "darwin":
            raise VideoError("MPS requires macOS.")
        if sys.version_info < (3, 12):
            raise VideoError("Run SeedVR2 setup with Python 3.12 or 3.13.")
        item = manifest[engine]
        return {"engine": engine, "version": SEED_COMMIT, "downloads": [item],
                "additional_downloads": "Isolated PyTorch/dependencies and selected model weights on first preview",
                "disk_budget_gib": 25, "torch_backend": torch_backend,
                "license": "Apache-2.0 integration; upstream model terms also apply",
                "cache": str(cache), "status": "optional; GPU configuration requires a successful preview"}
    if platform.machine().lower() not in ("amd64", "x86_64") and key != "macos":
        raise VideoError("Pinned NCNN binaries require x86-64 on Windows/Linux; use CPU on this architecture.")
    item = manifest[engine][key]
    return {"engine": engine, "version": item["version"], "downloads": [item],
            "disk_budget_gib": round(item["bytes"] * 4 / 2**30 + 0.2, 2),
            "license": "MIT wrapper; retain included model and dependency notices", "cache": str(cache),
            "status": "Vulkan/MoltenVK availability must be established by a successful preview"}


def setup(engine, cache, *, install=False, torch_backend=None):
    cache = absolute(cache)
    plan = setup_plan(engine, cache, torch_backend)
    if not install or engine == "cpu":
        return plan
    destination = cache / engine / plan["version"]
    receipt = destination / "receipt.json"
    if receipt.exists():
        return {**plan, "installed": json.loads(receipt.read_text(encoding="utf-8"))}
    free_space(cache, int(plan["disk_budget_gib"] * 2**30))
    item = plan["downloads"][0]
    archive = cache / "downloads" / (engine + "-" + plan["version"] + "-" + str(system_key()) + ".zip")
    download(item["url"], archive, item["sha256"])
    destination.mkdir(parents=True, exist_ok=True)
    # A failed setup is recoverable without pretending that an incomplete install is ready.
    safe_extract(archive, destination)
    if engine == "seedvr2":
        source = next(destination.glob("ComfyUI-SeedVR2_VideoUpscaler-*"))
        environment = destination / ".venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        torch_cmd = [python, "-m", "pip", "install", "torch==2.10.0", "torchvision==0.25.0"]
        if torch_backend == "cuda128":
            torch_cmd += ["--index-url", "https://download.pytorch.org/whl/cu128"]
        run(torch_cmd, log=destination / "setup.log")
        run([python, "-m", "pip", "install", "-r", source / "requirements.txt"], log=destination / "setup.log")
        frozen = run([python, "-m", "pip", "freeze"]).stdout
        (destination / "installed-requirements.txt").write_text(frozen, encoding="utf-8")
        result = {"engine": engine, "version": SEED_COMMIT, "python": str(python),
                  "source": str(source), "torch_backend": torch_backend,
                  "models": str(destination / "models"), "archive_sha256": item["sha256"]}
    else:
        basename = "realesrgan-ncnn-vulkan" if engine == "realesrgan" else "rife-ncnn-vulkan"
        executable = next(destination.rglob(basename + (".exe" if os.name == "nt" else "")), None)
        if executable is None:
            raise VideoError("Executable missing from pinned archive.")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        result = {"engine": engine, "version": plan["version"], "executable": str(executable),
                  "executable_sha256": digest(executable), "models": str(executable.parent / "models"),
                  "archive_sha256": item["sha256"]}
        if engine == "rife":
            candidates = list(executable.parent.rglob("rife-v4.6"))
            if not candidates:
                raise VideoError("Pinned archive lacks the required arbitrary-timestep RIFE v4.6 model.")
            result["models"] = str(candidates[0])
    write_json(receipt, result)
    return {**plan, "installed": result}


def resolve(engine, cache):
    if engine == "cpu":
        return {"engine": "cpu", "version": run(["ffmpeg", "-version"]).stdout.splitlines()[0]}
    records = sorted((Path(cache) / engine).glob("*/receipt.json"))
    if not records:
        raise VideoError(f"{engine} is not configured. Run setup --engine {engine} first.")
    # Only use the pinned version, never accidentally select a newer incompatible installation.
    version = SEED_COMMIT if engine == "seedvr2" else json.loads(MANIFEST.read_text())[engine][system_key()]["version"]
    receipt = Path(cache) / engine / version / "receipt.json"
    if not receipt.exists():
        raise VideoError(f"Set up pinned {engine} version {version}.")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    if "executable" in value and digest(value["executable"]) != value["executable_sha256"]:
        raise VideoError("Engine executable changed since setup; inspect and reinstall into a fresh cache.")
    return value


def is_memory_error(message):
    return any(word in str(message).lower() for word in
               ("out of memory", "outofmemory", "vk_error_out_of_device_memory", "failed to allocate", "cuda error: memory"))


def retry_memory(operation, values):
    """Retry only allocation failures, never hide unsupported engines or broken models."""
    attempts = []
    for index, value in enumerate(values):
        try:
            operation(value)
            return {"selected": value, "attempts": attempts}
        except VideoError as exc:
            attempts.append({"value": value, "error": str(exc)[-1500:]})
            if not is_memory_error(exc) or index == len(values) - 1:
                raise


@contextmanager
def frame_workspace(inputs, outputs, cache, pixel_factor=1):
    """Legacy Windows NCNN binaries cannot stat deep directories, even through relative CWDs."""
    inputs, outputs = Path(inputs), Path(outputs)
    if os.name != "nt" or max(len(str(inputs)), len(str(outputs))) < 230:
        yield inputs, outputs
        return
    base = absolute(cache) / "scratch"
    if len(str(base)) > 180:
        raise VideoError("The Windows NCNN binary needs a shorter cache path. Choose --cache on a short, spacious path and make a new job.")
    files = sorted(inputs.glob("*.png"))
    predicted = 0
    for path in files:
        with path.open("rb") as stream:
            header = stream.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise VideoError("Invalid extracted frame: " + path.name)
        width, height = struct.unpack(">II", header[16:24])
        predicted += width * height * 3 * pixel_factor + path.stat().st_size
    free_space(base, int(predicted + 64 * 2**20))
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ncnn-", dir=base) as temporary:
        work = Path(temporary)
        source, target = work / "in", work / "out"
        source.mkdir()
        target.mkdir()
        for path in files:
            try:
                os.link(path, source / path.name)
            except OSError:
                shutil.copyfile(path, source / path.name)
        yield source, target
        for path in target.glob("*.png"):
            shutil.move(str(path), str(outputs / path.name))


def upscale_frames(engine, inputs, outputs, settings, cache, log):
    receipt = resolve(engine, cache)
    outputs.mkdir(parents=True, exist_ok=True)
    if engine == "realesrgan":
        model = "realesrgan-x4plus"
        if not (Path(receipt["models"]) / (model + ".bin")).exists():
            raise VideoError("Required live-action model is missing: " + model)
        with frame_workspace(inputs, outputs, cache, pixel_factor=16) as (source, target):
            def attempt(tile):
                run([receipt["executable"], "-i", source.name, "-o", target.name, "-m", receipt["models"],
                     "-n", model, "-s", "4", "-t", tile, "-j", "1:1:1", "-f", "png"], cwd=source.parent, log=log)
            result = retry_memory(attempt, sorted({settings["tile"], max(32, settings["tile"] // 2), 32}, reverse=True))
        return {"engine": engine, "model": model, "memory": result, "version": receipt["version"]}
    raise VideoError("Frame upscaling adapter unavailable: " + engine)


def seed_backend_available(receipt):
    code = ("import json,torch; print(json.dumps({'cuda':torch.cuda.is_available(),"
            "'mps':bool(hasattr(torch.backends,'mps') and torch.backends.mps.is_available())}))")
    result = json.loads(run([receipt["python"], "-c", code], timeout=60).stdout)
    return result["mps"] if receipt["torch_backend"] == "mps" else result["cuda"]


def seed_video(source, destination, settings, cache, log):
    receipt = resolve("seedvr2", cache)
    if not seed_backend_available(receipt):
        raise VideoError("The isolated SeedVR2 environment cannot use the selected GPU backend. Choose a compatible runtime or another preview; diffusion will not silently run on CPU.")
    model = settings["seed_model"]
    # Ampere GPUs support FP16; select FP16 3B by default rather than assuming native FP8 support.
    def attempt(batch):
        run([receipt["python"], Path(receipt["source"]) / "inference_cli.py", source,
             "--output", destination, "--output_format", "mp4", "--video_backend", "ffmpeg",
             "--resolution", min(settings["width"], settings["height"]), "--max_resolution", max(settings["width"], settings["height"]), "--dit_model", model,
             "--model_dir", receipt["models"], "--batch_size", batch,
             "--chunk_size", max(17, batch * 2 - 1), "--temporal_overlap", "4",
             "--vae_encode_tiled", "--vae_decode_tiled", "--dit_offload_device", "cpu",
             "--vae_offload_device", "cpu", "--tensor_offload_device", "cpu",
             "--blocks_to_swap", 0 if receipt["torch_backend"] == "mps" else settings["blocks_to_swap"],
             "--uniform_batch_size", "--seed", "42"],
            cwd=receipt["source"], log=log)
    result = retry_memory(attempt, sorted({settings["batch"], *[x for x in (9, 5) if x <= settings["batch"]]}, reverse=True))
    return {"engine": "seedvr2", "model": model, "memory": result, "version": receipt["version"]}


def interpolate_pair(left, right, output, timestep, cache, log):
    receipt = resolve("rife", cache)
    with frame_workspace(left.parent, output.parent, cache) as (source, target):
        run([receipt["executable"], "-0", left.name, "-1", right.name, "-o", os.path.relpath(target / output.name, source),
             "-m", receipt["models"], "-s", f"{timestep:.9f}", "-j", "1:1:1"], cwd=source, log=log)


def interpolate_directory(inputs, outputs, count, cache, log):
    receipt = resolve("rife", cache)
    with frame_workspace(inputs, outputs, cache, pixel_factor=count / max(1, len(list(inputs.glob('*.png'))))) as (source, target):
        run([receipt["executable"], "-i", source.name, "-o", target.name, "-n", count,
             "-m", receipt["models"], "-j", "1:1:1", "-f", "%08d.png"], cwd=source.parent, log=log)


def hardware(cache):
    memory = None
    try:
        if os.name == "nt":
            import ctypes
            class Memory(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            status = Memory()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                memory = status.total
        elif sys.platform == "darwin":
            memory = int(run(["sysctl", "-n", "hw.memsize"], timeout=5).stdout)
        else:
            memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, VideoError, AttributeError):
        pass
    nvidia = []
    if shutil.which("nvidia-smi"):
        try:
            result = run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"], timeout=10)
            for line in result.stdout.strip().splitlines():
                name, total, free, driver = [part.strip() for part in line.split(",")]
                nvidia.append({"name": name, "vram_mib": int(total), "free_vram_mib": int(free), "driver": driver})
        except (VideoError, ValueError):
            pass
    installed = {}
    for engine in ("realesrgan", "rife", "seedvr2"):
        try:
            installed[engine] = resolve(engine, cache)
        except (VideoError, OSError, KeyError) as exc:
            installed[engine] = {"ready": False, "reason": str(exc)}
    return {"os": platform.system(), "architecture": platform.machine(), "python": platform.python_version(),
            "logical_cpus": os.cpu_count(), "ram_bytes": memory, "nvidia": nvidia,
            "vulkaninfo": shutil.which("vulkaninfo"),
            "gpu_note": "NVIDIA inventory is advisory. AMD/Intel/MoltenVK and CUDA/MPS compatibility require an engine smoke test.",
            "installed_engines": installed, "cache": str(cache), "cache_free_bytes": free_space(cache, 0)}
