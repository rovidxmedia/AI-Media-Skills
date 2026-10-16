"""Portable execution checks using generated audio, never private recordings.

Run: python -m unittest discover -s tests -v
Requires the skill's Python dependencies and FFmpeg/ffprobe.
These checks do not assess perceptual speech quality.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "podcast-audio-repair"
HELPER = SKILL / "scripts" / "repair_audio.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg and ffprobe must be installed")
class RepairIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def fixture(self, stereo=False):
        rate = 48000
        t = np.arange(rate * 4) / rate
        envelope = np.sin(np.pi * np.minimum(t % 0.8 / 0.55, 1)) ** 2
        tone = sum(np.sin(2 * np.pi * 137 * n * t) / n
                   for n in range(1, 7))
        voice = 0.10 * envelope * tone
        noise = np.random.default_rng(52).normal(0, 0.003, len(t))
        audio = voice + noise
        if stereo:
            audio = np.column_stack((audio, audio * 0.5))
        source = self.folder / "input.wav"
        sf.write(source, audio, rate, subtype="PCM_24")
        return source, rate, audio.shape

    def execute(self, source, dest, *options):
        return subprocess.run(
            [sys.executable, str(HELPER), str(source), str(dest),
             "--seconds", "3", "--comparison-start", "0.2",
             "--comparison-seconds", "1", *options],
            capture_output=True, text=True, timeout=90)

    def check_export(self, dest, channels, expected_frames):
        report = json.loads((dest / "report.json").read_text())
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(report["source_sha256_before"],
                         report["source_sha256_after"])
        self.assertEqual(report["status"],
                         "technical_checks_passed_listening_pending")
        info = sf.info(dest / "repaired.wav")
        self.assertEqual(info.samplerate, 48000)
        self.assertEqual(info.channels, channels)
        self.assertEqual(info.frames, expected_frames)
        audio, _ = sf.read(dest / "repaired.wav", always_2d=True)
        self.assertTrue(np.isfinite(audio).all())
        self.assertLess(float(np.max(np.abs(audio))), 1)
        self.assertLessEqual(report["after"]["input_tp"], -1.0)
        self.assertTrue((dest / "comparison.mp3").is_file())
        self.assertTrue((dest / "comparison-actual-volume.mp3").is_file())
        return report

    def peak_fixture(self):
        source, rate, _ = self.fixture(stereo=True)
        audio, _ = sf.read(source, always_2d=True)
        audio[rate:rate + 8] = [0.85, 0.7]
        sf.write(source, audio, rate, subtype="PCM_24")
        return source, rate

    def test_speech_master_meets_target_and_preserves_preview_levels(self):
        source, rate = self.peak_fixture()
        dest = self.folder / "speech"
        result = self.execute(source, dest)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.check_export(dest, 2, 3 * rate)
        self.assertTrue(report["loudness_goal"]["target_met"])
        self.assertAlmostEqual(report["after"]["input_i"], -16, delta=0.3)
        self.assertLessEqual(report["after"]["input_tp"], -1.5)
        self.assertTrue(any("peak limiting" in item["algorithm"]
                            for item in report["operations"]))
        original, _ = sf.read(dest / "input.wav", start=round(0.2 * rate),
                              frames=rate, always_2d=True)
        repaired, _ = sf.read(dest / "repaired.wav", start=round(0.2 * rate),
                              frames=rate, always_2d=True)
        preview, _ = sf.read(dest / "comparison-actual-volume.wav", always_2d=True)
        np.testing.assert_array_equal(preview[:rate], original)
        np.testing.assert_array_equal(preview[rate + round(0.75 * rate):], repaired)
        a, _ = sf.read(dest / "input.wav", always_2d=True)
        b, _ = sf.read(dest / "repaired.wav", always_2d=True)
        correlation = signal.correlate(b[:, 0], a[:, 0], method="fft")
        lags = signal.correlation_lags(len(b), len(a))
        near = np.abs(lags) <= 480
        self.assertEqual(int(lags[near][np.argmax(correlation[near])]), 0)

    def test_preserve_mode_reports_peak_constrained_target_miss(self):
        source, _ = self.peak_fixture()
        dest = self.folder / "preserve"
        result = self.execute(source, dest, "--loudness-mode", "preserve")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((dest / "report.json").read_text())
        self.assertFalse(report["loudness_goal"]["target_met"])
        self.assertIn("target_not_met", report["status"])
        self.assertTrue(report["source_unchanged"])
        self.assertFalse(any("peak limiting" in item["algorithm"]
                             for item in report["operations"]))

    def test_neural_partial_frame_keeps_exact_duration(self):
        source, rate, _ = self.fixture(stereo=True)
        dest = self.folder / "partial-frame"
        result = self.execute(source, dest, "--denoise", "neural", "--seconds", "3.007")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.check_export(dest, 2, round(3.007 * rate))
        latency = report["denoise_latency_compensation"]
        self.assertGreaterEqual(latency["denoiser_extra_frame_samples"], 0)
        self.assertLess(latency["denoiser_extra_frame_samples"], 480)
        self.assertTrue(latency["partial_final_frame_handled"])

    def test_silence_is_not_a_successful_loudness_repair(self):
        source = self.folder / "silence.wav"
        sf.write(source, np.zeros((48000 * 3, 2)), 48000, subtype="PCM_24")
        before = digest(source)
        dest = self.folder / "silent-run"
        result = self.execute(source, dest)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((dest / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIn("unmeasurable", report["error"])
        self.assertEqual(digest(source), before)

    def test_mono_spectral_export_and_original_preserved(self):
        source, rate, _ = self.fixture()
        before = digest(source)
        dest = self.folder / "spectral"
        result = self.execute(source, dest, "--denoise", "spectral")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(digest(source), before)
        self.check_export(dest, 1, 3 * rate)

    def test_stereo_levels_preserve_channels_and_refuse_overwrite(self):
        source, rate, _ = self.fixture(stereo=True)
        dest = self.folder / "levels"
        before = digest(source)
        result = self.execute(source, dest, "--level")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.check_export(dest, 2, 3 * rate)
        output_hash = digest(dest / "repaired.wav")
        again = self.execute(source, dest, "--level")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stderr)
        self.assertEqual(digest(dest / "repaired.wav"), output_hash)
        self.assertEqual(digest(source), before)

    def test_multichannel_rejected_without_touching_source(self):
        source = self.folder / "surround.wav"
        sf.write(source, np.ones((48000 * 2, 4)) * 0.01,
                 48000, subtype="PCM_24")
        before = digest(source)
        dest = self.folder / "rejected"
        result = self.execute(source, dest)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((dest / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIn("mono/stereo", report["error"])
        self.assertEqual(digest(source), before)


if __name__ == "__main__":
    unittest.main()
