"""Portable generated-fixture checks. No private recording or GPU is needed."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "video-enhance" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import engines
import video_enhance as video


class EngineUnitTests(unittest.TestCase):
    def test_memory_retry_only_for_allocation_errors(self):
        attempts = []
        def allocate(size):
            attempts.append(size)
            if size > 32:
                raise engines.VideoError("VK_ERROR_OUT_OF_DEVICE_MEMORY")
        result = engines.retry_memory(allocate, [128, 64, 32])
        self.assertEqual(attempts, [128, 64, 32])
        self.assertEqual(result["selected"], 32)
        with self.assertRaisesRegex(engines.VideoError, "model"):
            engines.retry_memory(lambda _: (_ for _ in ()).throw(engines.VideoError("broken model")), [128, 32])

    def test_storage_failure_and_archive_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(engines.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(100, 99, 1)):
                with self.assertRaisesRegex(engines.VideoError, "Insufficient storage"):
                    engines.free_space(temp, 2)
            path = Path(temp) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escaped", b"no")
            with self.assertRaisesRegex(engines.VideoError, "Unsafe archive"):
                engines.safe_extract(path, Path(temp) / "dest")
            self.assertFalse((Path(temp) / "escaped").exists())

    def test_download_integrity_failure_leaves_no_install(self):
        import io
        with tempfile.TemporaryDirectory() as temp, patch.object(engines.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
            path = Path(temp) / "artifact.zip"
            with self.assertRaisesRegex(engines.VideoError, "SHA-256"):
                engines.download("https://example.invalid/engine", path, "0" * 64)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(".zip.partial").exists())

    def test_setup_dry_run_never_downloads(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(engines, "download") as download:
            result = engines.setup("realesrgan", temp)
            self.assertEqual(len(result["downloads"][0]["sha256"]), 64)
            download.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_scene_and_chunk_plan_has_no_rounding_drift(self):
        settings = {"fps": "60000/1001", "chunk_seconds": 1, "overlap": 0.5}
        result = video.plan_segments(0, 10.01, [3.003, 7.007], settings)
        self.assertEqual(sum(x["frames"] for x in result), 600)
        for item in result:
            self.assertGreaterEqual(item["context_start"], item["shot_start"])
            self.assertLessEqual(item["context_end"], item["shot_end"])

    def test_seed_memory_retries_retain_temporal_context_and_mps_disables_swap(self):
        calls = []
        def invocation(command, **_):
            batch = int(command[command.index("--batch_size") + 1])
            calls.append((batch, command[command.index("--blocks_to_swap") + 1]))
            if batch > 5:
                raise engines.VideoError("MPS backend out of memory")
        receipt = {"python": "isolated-python", "source": ".", "models": "models", "version": "pinned", "torch_backend": "mps"}
        settings = {"height": 1080, "width": 1920, "seed_model": "seedvr2_ema_3b_fp16.safetensors", "batch": 17, "blocks_to_swap": 16}
        with patch.object(engines, "resolve", return_value=receipt), patch.object(engines, "seed_backend_available", return_value=True), patch.object(engines, "run", side_effect=invocation):
            result = engines.seed_video("source.mkv", "output.mp4", settings, "cache", None)
        self.assertEqual(calls, [(17, 0), (9, 0), (5, 0)])
        self.assertEqual(result["memory"]["selected"], 5)

    def test_seed_missing_gpu_does_not_download_weights_or_fall_back_to_cpu(self):
        with patch.object(engines, "resolve", return_value={"engine": "seedvr2"}), patch.object(engines, "seed_backend_available", return_value=False), patch.object(engines, "run") as invocation:
            with self.assertRaisesRegex(engines.VideoError, "silently run on CPU"):
                engines.seed_video("source", "output", {}, "cache", None)
            invocation.assert_not_called()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Install FFmpeg and ffprobe")
class VideoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="video-enhance-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.source = cls.base / "recording spaced ü & $ quote'.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=160x96:rate=12:duration=2.5",
                      "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2.5",
                      "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=2.5",
                      "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-crf", "16",
                      "-c:a", "aac", "-metadata:s:a:0", "title=Mix", "-metadata:s:a:0", "language=eng",
                      "-metadata:s:a:1", "title=Microphone", cls.source])
        cls.source_hash = engines.digest(cls.source)
        cls.template = cls.base / "template"
        video.analyze(cls.source, cls.template, cls.base / "cache")

    def setUp(self):
        self.folder = self.base / self._testMethodName
        shutil.copytree(self.template, self.folder)

    def args(self, *options):
        return video.parser().parse_args(["preview", "--job", str(self.folder), "--engine", "cpu",
                                           "--style", "natural", "--starts", "0.25", "--seconds", "1.5",
                                           "--chunk-seconds", "1", *options])

    def test_preview_render_audio_labels_source_and_resume(self):
        preview = video.preview(self.args("--repairs", "denoise,exposure,color,sharpen,deblock,deband",
                                          "--gamma", "1.1", "--fps", "24", "--interpolation", "motion"))
        self.assertEqual(preview["status"], "visual_review_pending")
        self.assertTrue(Path(preview["samples"][0]["comparison"]).exists())
        args = video.parser().parse_args(["render", "--job", str(self.folder), "--accept-preview", preview["signature"]])
        original = video.process_segment
        calls = []
        def interrupted(job, segment, destination, *rest):
            calls.append(segment["start"])
            if len(calls) == 2:
                raise engines.VideoError("simulated interrupted process")
            return original(job, segment, destination, *rest)
        with patch.object(video, "process_segment", side_effect=interrupted):
            with self.assertRaisesRegex(engines.VideoError, "interrupted"):
                video.render(args)
        first = self.folder / "render" / "chunk-000000.mp4"
        timestamp = first.stat().st_mtime_ns
        resumed = video.render(video.parser().parse_args(["resume", "--job", str(self.folder)]), resume=True)
        self.assertTrue(resumed["source_unchanged"])
        self.assertEqual(first.stat().st_mtime_ns, timestamp)
        self.assertEqual(resumed["verification"]["audio_tracks"], 2)
        self.assertEqual(engines.digest(self.source), self.source_hash)
        actual = video.probe(resumed["output"])
        self.assertEqual(actual["audio"][1]["tags"]["title"], "Microphone")

    def test_stale_preview_source_changes_and_missing_filters_fail(self):
        args = video.parser().parse_args(["render", "--job", str(self.folder), "--accept-preview", "anything"])
        with self.assertRaisesRegex(engines.VideoError, "preview"):
            video.render(args)
        _, job = video.load_job(self.folder)
        job["settings"] = video.settings_from_args(self.args("--repairs", "denoise"), job)
        with patch.object(video, "doctor", return_value={"filters": []}):
            with self.assertRaisesRegex(engines.VideoError, "missing selected filters"):
                video.require_filters(job)
        job["source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(engines.VideoError, "Source changed"):
            video.check_source(job)

    def test_fractional_frame_rate_and_portrait_geometry(self):
        portrait = self.base / "portrait.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x160:rate=30000/1001:duration=1.5", "-an", "-c:v", "libx264", portrait])
        target = self.base / "portrait-job"
        video.analyze(portrait, target, self.base / "cache")
        args = self.args("--fps", "60000/1001", "--interpolation", "motion", "--height", "128", "--starts", "0", "--seconds", "1")
        args.job = target
        result = video.preview(args)
        output = video.probe(result["samples"][0]["output"])
        self.assertEqual((output["width"], output["height"]), (76, 128))
        self.assertAlmostEqual(float(video.Fraction(output["fps"])), 60000 / 1001, places=2)

    def test_interlace_and_flicker_stabilization(self):
        filters = set(video.doctor(self.base / "cache")["filters"])
        if not {"vidstabdetect", "vidstabtransform", "deflicker", "bwdif"} <= filters:
            self.skipTest("This FFmpeg build lacks optional repair filters")
        result = video.preview(self.args("--repairs", "deinterlace,deflicker,stabilize", "--field-order", "tff", "--starts", "0"))
        self.assertEqual(result["samples"][0]["verification"]["fps"], "24")

    def test_hdr_requires_explicit_handling_and_limits_ai(self):
        _, job = video.load_job(self.folder)
        job["media"]["hdr"] = True
        with self.assertRaisesRegex(engines.VideoError, "HDR requires"):
            video.settings_from_args(self.args(), job)
        args = self.args("--hdr", "preserve", "--engine", "realesrgan")
        with self.assertRaisesRegex(engines.VideoError, "SDR-only"):
            video.settings_from_args(args, job)

    def test_no_implicit_interpolation_or_unconfirmed_field_order(self):
        _, job = video.load_job(self.folder)
        with self.assertRaisesRegex(engines.VideoError, "duplication"):
            video.settings_from_args(self.args("--fps", "60"), job)
        job["media"]["field_order"] = "progressive"
        with self.assertRaisesRegex(engines.VideoError, "field-order"):
            video.settings_from_args(self.args("--repairs", "deinterlace"), job)

    def test_scene_cut_never_interpolates_between_unrelated_shots(self):
        source = self.base / "red-blue.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "color=red:size=160x96:rate=12:duration=1",
                      "-f", "lavfi", "-i", "color=blue:size=160x96:rate=12:duration=1",
                      "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", source])
        target = self.base / "cuts-job"
        video.analyze(source, target, self.base / "cache")
        args = self.args("--repairs", "deflicker", "--fps", "24", "--interpolation", "motion", "--starts", "0", "--seconds", "2")
        args.job = target
        result = video.preview(args)
        output = result["samples"][0]["output"]
        state = json.loads((Path(output).parent / "state.json").read_text())
        self.assertEqual(len(state["cuts"]), 1)
        raw = engines.run(["ffmpeg", "-hide_banner", "-i", output, "-vf", "signalstats,metadata=print", "-f", "null", "-"]).stderr
        saturation = [float(x) for x in video.re.findall(r"lavfi.signalstats.SATAVG=([\d.]+)", raw)]
        self.assertTrue(saturation)
        # Red/blue remain strongly saturated across the cut; no mixed transition frames are produced.
        self.assertGreater(min(saturation), 80)

    def test_variable_frame_intervals_require_explicit_output_rate(self):
        source = self.base / "vfr.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=160x96:rate=12:duration=2.5",
                      "-vf", "select='if(lt(t,1),1,not(mod(n,2)))'", "-fps_mode", "vfr", "-an", "-c:v", "libx264", source])
        target = self.base / "vfr-job"
        video.analyze(source, target, self.base / "cache")
        _, job = video.load_job(target)
        self.assertTrue(job["media"]["vfr_detected"])
        with self.assertRaisesRegex(engines.VideoError, "explicit numeric"):
            video.settings_from_args(self.args(), job)
        args = self.args("--fps", "12", "--starts", "0", "--seconds", "2")
        args.job = target
        result = video.preview(args)
        self.assertAlmostEqual(result["samples"][0]["verification"]["duration"], 2, delta=0.08)

    def test_rotation_metadata_does_not_rotate_output_twice(self):
        source = self.base / "rotated.mp4"
        video.ffmpeg(["-i", self.source, "-map", "0:v:0", "-an", "-c:v", "copy", "-metadata:s:v:0", "rotate=90", source])
        if video.probe(source)["rotation"] == 0:
            # Recent FFmpeg builds use the explicit input display-matrix override.
            video.ffmpeg(["-display_rotation", "90", "-i", self.source, "-map", "0:v:0", "-an", "-c:v", "copy", source])
        target = self.base / "rotated-job"
        video.analyze(source, target, self.base / "cache")
        args = self.args("--height", "160", "--starts", "0", "--seconds", "1")
        args.job = target
        result = video.preview(args)
        info = video.probe(result["samples"][0]["output"])
        self.assertEqual((info["width"], info["height"], info["rotation"]), (96, 160, 0))

    def test_generated_interlaced_shaky_flickering_fixture(self):
        filters = set(video.doctor(self.base / "cache")["filters"])
        if not {"vidstabdetect", "vidstabtransform"} <= filters:
            self.skipTest("Optional stabilization unavailable")
        source = self.base / "interlaced-flicker.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=176x112:rate=24:duration=2",
                      "-vf", "crop=160:96:x='8+4*sin(n)':y='8+4*cos(n)',eq=brightness='0.03*sin(n)':eval=frame,tinterlace=mode=interleave_top",
                      "-an", "-c:v", "libx264", "-flags", "+ilme+ildct", "-top", "1", source])
        target = self.base / "actual-repairs-job"
        video.analyze(source, target, self.base / "cache")
        args = self.args("--repairs", "deinterlace,deflicker,stabilize", "--field-order", "tff", "--fps", "24", "--starts", "0", "--seconds", "1.5")
        args.job = target
        result = video.preview(args)
        self.assertEqual(result["samples"][0]["verification"]["frames"], 36)

    def test_settings_mutation_invalidates_previously_successful_preview(self):
        result = video.preview(self.args("--starts", "0", "--seconds", "0.5"))
        _, job = video.load_job(self.folder)
        job["settings"]["height"] = 128
        engines.write_json(self.folder / "job.json", job)
        args = video.parser().parse_args(["render", "--job", str(self.folder), "--accept-preview", result["signature"]])
        with self.assertRaisesRegex(engines.VideoError, "matching these settings"):
            video.render(args)

    def test_deliberately_delayed_audio_stays_delayed(self):
        source = self.base / "delayed-audio.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=160x96:rate=12:duration=3",
                      "-itsoffset", "0.6", "-f", "lavfi", "-i", "sine=frequency=600:sample_rate=48000:duration=2",
                      "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac", source])
        target = self.base / "delayed-audio-job"
        video.analyze(source, target, self.base / "cache")
        args = self.args("--starts", "0.25", "--seconds", "2")
        args.job = target
        result = video.preview(args)
        actual = video.probe(result["samples"][0]["output"])
        self.assertAlmostEqual(float(actual["audio"][0]["start_time"]), 0.6 - 0.25, delta=0.04)

    @unittest.skipUnless(os.environ.get("VIDEO_ENHANCE_TEST_CACHE"), "Set VIDEO_ENHANCE_TEST_CACHE for opt-in GPU inference")
    def test_opt_in_ncnn_restoration_and_batched_interpolation(self):
        _, job = video.load_job(self.folder)
        job["cache"] = os.environ["VIDEO_ENHANCE_TEST_CACHE"]
        engines.write_json(self.folder / "job.json", job)
        result = video.preview(self.args("--engine", "realesrgan", "--fps", "24", "--interpolation", "rife",
                                         "--starts", "0", "--seconds", "0.5"))
        self.assertEqual(result["samples"][0]["verification"]["frames"], 12)
        log = (Path(result["samples"][0]["output"]).parent / "processing.log").read_text(encoding="utf-8")
        self.assertIn('"-n", "12"', log)

    def test_fractional_rate_chunk_boundaries_keep_the_same_source_frames(self):
        source = self.base / "fractional-frame-colors.mkv"
        video.ffmpeg(["-f", "lavfi", "-i", "nullsrc=size=160x96:rate=30000/1001:duration=2,geq=lum='N*3+20':cb=128:cr=128",
                      "-an", "-c:v", "libx264", "-crf", "0", source])
        target = self.base / "fractional-boundary-job"
        video.analyze(source, target, self.base / "cache")
        args = self.args("--starts", "0", "--seconds", "1.8", "--crf", "0")
        args.job = target
        chunked = video.preview(args)["samples"][0]["output"]
        args.chunk_seconds = 5
        continuous = video.preview(args)["samples"][0]["output"]
        def hashes(path):
            text = engines.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-f", "framemd5", "-"]).stdout
            return [line.rsplit(",", 1)[-1].strip() for line in text.splitlines() if not line.startswith("#")]
        self.assertEqual(hashes(chunked), hashes(continuous))


if __name__ == "__main__":
    unittest.main()
