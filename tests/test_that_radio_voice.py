"""Generated-fixture integration checks for broadcast-style processing.

These verify execution, signal behavior, and preservation, not listening quality.
Run from the repository root: python -m unittest discover -s tests -v
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

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "that-radio-voice"
HELPER = SKILL / "scripts" / "radio_voice.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg and ffprobe must be installed")
class RadioVoiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name).resolve()
        self.assertEqual(self.folder.parent, Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)

    def fixture(self, stereo=True):
        rate, frames = 48000, 9 * 48000 + 137
        t = np.arange(frames) / rate
        tone = sum(np.sin(2 * np.pi * 137 * k * t) / k for k in range(1, 8))
        voice = np.zeros(frames)
        voice[t < 2] = 0.16 * tone[t < 2]
        quiet = (t >= 4.3) & (t < 5.1)
        voice[quiet] = 0.006 * tone[quiet]
        active = t >= 5.5
        voice[active] = 0.11 * tone[active] * (0.6 + 0.4 * np.sin(2 * np.pi * t[active]) ** 2)
        sibilance = (t >= 7) & (t < 7.3)
        voice[sibilance] += 0.025 * np.sin(2 * np.pi * 4800 * t[sibilance])
        voice += np.random.default_rng(211).normal(0, 0.00001, frames)
        audio = np.column_stack([voice, voice * 0.7]) if stereo else voice
        source = self.folder / "input.wav"
        sf.write(source, audio, rate, subtype="PCM_24")
        return source, rate, frames

    def execute(self, source, dest, *options):
        # Deliberately omit --repair-helper: the repository's sibling layout
        # must discover the shared dependency without machine-specific paths.
        return subprocess.run(
            [sys.executable, str(HELPER), str(source), str(dest), "--full",
             "--comparison-start", "0.2", "--comparison-seconds", "2", *options],
            capture_output=True, text=True, timeout=120)

    def test_big_chain_mastering_gate_and_actual_comparison(self):
        source, rate, frames = self.fixture()
        before = digest(source)
        dest = self.folder / "big"
        result = self.execute(source, dest)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((dest / "report.json").read_text())
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(digest(source), before)
        self.assertTrue(report["loudness_goal"]["target_met"])
        self.assertAlmostEqual(report["after"]["input_i"], -14, delta=0.3)
        self.assertLessEqual(report["after"]["input_tp"], -1.5)
        self.assertLess(report["mp3"]["input_tp"], 0)
        info = sf.info(dest / "radio-voice.wav")
        self.assertEqual((info.frames, info.samplerate, info.channels, info.subtype),
                         (frames, rate, 2, "PCM_24"))
        audio, _ = sf.read(dest / "radio-voice.wav", always_2d=True)
        self.assertTrue(np.isfinite(audio).all())
        self.assertLess(float(np.max(abs(audio))), 1)

        def load(name):
            return sf.read(dest / name, always_2d=True)[0]

        def change(a, b, start, end):
            span = slice(round(start * rate), round(end * rate))
            return 20 * np.log10(np.linalg.norm(b[span]) / np.linalg.norm(a[span]))

        staged, gated = load("00-staged.wav"), load("01-gated.wav")
        self.assertLess(change(staged, gated, 3.7, 4.1), -6)
        self.assertGreater(change(staged, gated, 4.7, 5.0), -3)
        tone, compressed = load("02-tone.wav"), load("03-compressed.wav")
        excited = load("04-excited.wav")
        self.assertLess(change(tone, compressed, 0.5, 1.5), -2)
        self.assertGreater(float(np.max(abs(excited - compressed))), 0.0001)
        original = load("input.wav")[round(0.2 * rate):round(2.2 * rate)]
        treated = audio[round(0.2 * rate):round(2.2 * rate)]
        actual = load("comparison-actual-volume.wav")
        np.testing.assert_array_equal(actual[:len(original)], original)
        np.testing.assert_array_equal(actual[len(original) + round(0.75 * rate):], treated)
        self.assertTrue((dest / "comparison.mp3").is_file())
        self.assertTrue((dest / "radio-voice.mp3").is_file())

        output_hash = digest(dest / "radio-voice.wav")
        again = self.execute(source, dest)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stderr)
        self.assertEqual(digest(dest / "radio-voice.wav"), output_hash)

    def test_warm_mono_and_explicit_bypasses(self):
        source, rate, frames = self.fixture(stereo=False)
        dest = self.folder / "warm"
        result = self.execute(source, dest, "--preset", "warm", "--no-gate", "--no-exciter")
        self.assertEqual(result.returncode, 0, result.stderr)
        info = sf.info(dest / "radio-voice.wav")
        self.assertEqual((info.frames, info.samplerate, info.channels), (frames, rate, 1))
        self.assertFalse((dest / "01-gated.wav").exists())
        self.assertFalse((dest / "04-excited.wav").exists())
        report = json.loads((dest / "report.json").read_text())
        self.assertTrue(report["loudness_goal"]["target_met"])

    def test_silence_and_multichannel_rejected_without_source_changes(self):
        for name, audio, message in (("silence", np.zeros((48000 * 3, 2)), "unmeasurable"),
                                     ("surround", np.ones((48000 * 3, 4)) * 0.01, "mono/stereo")):
            with self.subTest(name=name):
                source = self.folder / (name + ".wav")
                sf.write(source, audio, 48000, subtype="PCM_24")
                before = digest(source)
                dest = self.folder / name
                result = self.execute(source, dest)
                self.assertNotEqual(result.returncode, 0)
                report = json.loads((dest / "report.json").read_text())
                self.assertEqual(report["status"], "failed")
                self.assertIn(message, report["error"])
                self.assertEqual(digest(source), before)

    def test_missing_or_outdated_dependency_reports_actionable_error(self):
        source, _, _ = self.fixture()
        missing = self.folder / "missing-helper.py"
        outdated = self.folder / "old-helper.py"
        outdated.write_text("# Deliberately lacks the required utility interface.\n")
        for helper, message in ((missing, "--repair-helper"), (outdated, "Outdated")):
            with self.subTest(helper=helper.name):
                result = self.execute(source, self.folder / helper.stem,
                                      "--repair-helper", str(helper))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
