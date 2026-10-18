"""Generated-fixture Editor checks; no model, network or private footage needed."""
import array
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/"skills"/"editor"/"scripts"
sys.path.insert(0, str(SCRIPTS))
import editor
import timeline as tl


def word(text, a, b, probability=0.99, **extra):
    return {"word": text, "start": a, "end": b, "probability": probability, "emphasis": False, **extra}


def fake_job():
    words = [word("I", .2, .4), word("um", .8, 1), word("actually", 1.4, 1.8),
             word("remember", 4.2, 4.6), word("this.", 4.8, 5.2)]
    return {"schema_version": 1, "source": {"sha256": "test"}, "scope": [0, 6],
            "media": {"fps": "24", "width": 160, "height": 90}, "words": words,
            "plan": tl.propose(words, [[2, 3.5]], [0, 6])}


class TimelineTests(unittest.TestCase):
    def test_natural_preserves_context_words_and_useful_pauses(self):
        job = fake_job()
        self.assertEqual(job["plan"]["style"], "natural")
        cuts = job["plan"]["cuts"]
        self.assertTrue(next(c for c in cuts if c["kind"] == "filler")["selected"])
        self.assertFalse(next(c for c in cuts if c["kind"] == "context")["selected"])
        pause = next(c for c in cuts if c["kind"] == "pause")
        self.assertAlmostEqual(1.5-(pause["end"]-pause["start"]), .4)
        self.assertFalse(tl.propose([], [[1, 1.5]], [0, 6])["cuts"])

    def test_quiet_words_and_close_neighbors_prevent_auto_cuts(self):
        p = tl.propose([word("quiet", 2.4, 2.6)], [[2, 3.5]], [0, 6])
        self.assertFalse(p["cuts"][0]["selected"])
        p = tl.propose([word("before", .5, .79), word("uh", .8, 1), word("after", 1.01, 1.4)], [], [0, 6])
        self.assertFalse(p["cuts"][0]["selected"])

    def test_retake_and_repeat_are_review_only(self):
        words = [word(w, i*.4, i*.4+.2) for i, w in enumerate(["we", "should", "try", "we", "should", "try", "try", "incom-"])]
        p = tl.propose(words, [], [0, 6])
        self.assertTrue({"retake", "repeat", "false_start"}.issubset({c["kind"] for c in p["cuts"]}))
        self.assertTrue(all(not c["selected"] for c in p["cuts"]))

    def test_zoom_spacing_and_framing_guard(self):
        words = [word("important", i, i+.3) for i in (1, 10, 50)]
        p = tl.propose(words, [], [0, 60])
        self.assertEqual(len(p["zooms"]), 2)
        self.assertEqual(p["zooms"][0]["scale"], 1.08)
        job = fake_job()
        job["plan"]["zooms"][0]["scale"] = 2
        with self.assertRaisesRegex(ValueError, "zoom"):
            tl.timeline(job)

    def test_frame_grid_merges_overlaps_and_caption_map_follows_cuts(self):
        job = fake_job()
        job["plan"]["cuts"] = [{"start": .7, "end": 1.1, "selected": True},
                                {"start": .9, "end": 1.2, "selected": True}]
        pieces = tl.timeline(job)
        self.assertEqual(sum(p["frames"] for p in pieces), 144-11)
        mapped = tl.mapped_words(job, pieces)
        self.assertNotIn("um", [w["word"] for w in mapped])
        self.assertLess(next(w["start"] for w in mapped if w["word"] == "remember"), 4.2)
        job["plan"]["captions"] = "highlight"
        job["plan"]["highlight_words"] = ["remember"]
        srt, ass = tl.captions(job, pieces)
        self.assertNotIn("um", srt)
        self.assertIn(r"{\c&H00FFFF&\b1}remember", ass)

    def test_caption_word_crossing_technical_chunk_is_not_duplicated(self):
        job = fake_job()
        job["plan"]["cuts"] = []
        job["plan"]["chunk_seconds"] = 1
        job["words"] = [word("boundary", .8, 1.2)]
        mapped = tl.mapped_words(job, tl.timeline(job))
        self.assertEqual(len(mapped), 1)
        self.assertAlmostEqual(mapped[0]["end"], 1.2)

    def test_nonfinite_bad_transcript_and_empty_render_are_rejected(self):
        for data in ({"source_sha256": "other", "coverage": [0, 6], "words": []},
                     {"source_sha256": "test", "coverage": [0, 2], "words": []},
                     {"source_sha256": "test", "coverage": [0, 6], "words": [word("bad", float('nan'), 2)]}):
            with self.assertRaises(ValueError):
                tl.validate_words(data, "test", [0, 6])
        job = fake_job()
        job["plan"]["cuts"] = [{"start": 0, "end": 6, "selected": True}]
        with self.assertRaisesRegex(ValueError, "entire"):
            tl.timeline(job)

    def test_signature_covers_caption_transcript_zoom_and_selection_changes(self):
        job = fake_job()
        original = tl.signature(job)
        for field in ("caption", "word", "zoom", "cut"):
            changed = copy.deepcopy(job)
            if field == "caption": changed["plan"]["captions"] = "srt"
            elif field == "word": changed["words"][0]["word"] = "Changed"
            elif field == "zoom": changed["plan"]["zooms"][0]["center_x"] = .3
            else: changed["plan"]["cuts"][0]["selected"] = False
            self.assertNotEqual(tl.signature(changed), original)

    def test_html_and_subtitle_text_are_escaped(self):
        job = fake_job()
        job["words"] = [word('<script>{\\bad}</script>', 1, 2)]
        job["plan"]["cuts"] = []
        self.assertNotIn('<script>', tl.review_html(job))
        self.assertNotIn(r'{\bad}', tl.captions(job, tl.timeline(job))[1])

    def test_setup_dry_run_does_not_install(self):
        with tempfile.TemporaryDirectory() as root, patch.object(editor.venv, "EnvBuilder") as creator:
            result = editor.setup(root)
            self.assertFalse(result["installed"])
            creator.assert_not_called()
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_windows_cache_is_stable_across_sandbox_localappdata_overrides(self):
        with patch.object(editor.sys, "platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "ephemeral-run-cache"}):
            self.assertEqual(editor.cache_default(), Path.home()/"AppData"/"Local"/"ai-media-skills"/"editor")

    def test_silence_intersection_and_wholly_quiet_recording(self):
        self.assertEqual(tl.intersect_ranges([[0, 2], [4, 8]], [[1, 5], [6, 9]]), [[1, 2], [4, 5], [6, 8]])
        self.assertFalse(tl.propose([], [[0, 6]], [0, 6])["cuts"][0]["selected"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Install FFmpeg and ffprobe")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="editor-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.source = cls.base/"recording spaced ü & $ quote'.mkv"
        signal = "aevalsrc=if(between(t\\,2\\,3.5)\\,0\\,0.2*sin(2*PI*440*t)):s=48000:d=6"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=6",
                       "-f", "lavfi", "-i", signal, "-f", "lavfi", "-i", signal,
                       "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-c:a", "flac",
                       "-metadata:s:a:0", "title=Mix", "-metadata:s:a:0", "language=eng",
                       "-metadata:s:a:1", "title=Mic", cls.source])
        cls.template = cls.base/"template"
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(cls.source), "--job", str(cls.template)]))
        _, job = editor.load(cls.template)
        job["words"] = fake_job()["words"]
        job["plan"] = tl.propose(job["words"], job["silences"], job["scope"])
        job["plan"]["chunk_seconds"] = 2
        editor.write(cls.template/"job.json", job)

    def setUp(self):
        self.folder = self.base/self._testMethodName
        shutil.copytree(self.template, self.folder)
        _, self.job = editor.load(self.folder)

    def args(self, command, *rest):
        return editor.parser().parse_args([command, "--job", str(self.folder), *rest])

    def preview(self):
        return editor.preview(self.args("preview", "--accept-plan", tl.signature(self.job), "--seconds", "6"))

    def test_preview_render_and_resume_preserve_source_tracks_and_timeline(self):
        before = editor.digest(self.source)
        result = self.preview()
        self.assertEqual(result["verification"]["audio_tracks"], 2)
        self.assertLess(result["verification"]["duration"], 6)
        self.assertTrue(Path(result["playback"]).is_file())
        original, calls = editor.segment, []
        def interrupt(*args):
            calls.append(1)
            if len(calls) == 2: raise ValueError("interrupted")
            return original(*args)
        with patch.object(editor, "segment", side_effect=interrupt):
            with self.assertRaisesRegex(ValueError, "interrupted"):
                editor.render(self.args("render", "--accept-preview", result["signature"]))
        first = self.folder/"render"/"segment-000000.mkv"
        stamp = first.stat().st_mtime_ns
        final = editor.render(self.args("resume"), resume=True)
        self.assertEqual(first.stat().st_mtime_ns, stamp)
        self.assertTrue(final["source_unchanged"])
        self.assertEqual(before, editor.digest(self.source))
        self.assertEqual(editor.probe(final["output"])["audio"][1]["tags"]["title"], "Mic")

    def test_approval_gates_and_stale_preview(self):
        with self.assertRaisesRegex(ValueError, "confirm"):
            editor.preview(self.args("preview", "--accept-plan", "wrong"))
        with self.assertRaisesRegex(ValueError, "preview"):
            editor.render(self.args("render", "--accept-preview", "wrong"))
        result = self.preview()
        _, job = editor.load(self.folder)
        job["plan"]["zooms"][0]["scale"] = 1.1
        editor.write(self.folder/"job.json", job)
        with self.assertRaisesRegex(ValueError, "current preview"):
            editor.render(self.args("render", "--accept-preview", result["signature"]))

    def test_burned_highlight_captions_and_zoom_render(self):
        filters = editor.run(["ffmpeg", "-hide_banner", "-filters"])
        if not re_search_subtitles(filters): self.skipTest("FFmpeg lacks subtitles/libass")
        self.job["plan"]["captions"] = "highlight"
        self.job["plan"]["highlight_words"] = ["remember"]
        editor.write(self.folder/"job.json", self.job)
        result = self.preview()
        root = Path(result["output"]).parent
        self.assertTrue((root/"captions.srt").is_file())
        self.assertIn(r"{\c&H00FFFF&\b1}remember", (root/"captions.ass").read_text(encoding="utf-8"))

    def test_storage_and_source_mutation_fail(self):
        with patch.object(editor.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(10, 9, 1)):
            with self.assertRaisesRegex(ValueError, "storage"):
                self.preview()
        self.job["source"]["sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "Source changed"):
            editor.check_source(self.job)

    def test_missing_transcriber_does_not_download_or_use_cloud(self):
        self.job["cache"] = str(self.folder/"absent-cache")
        editor.write(self.folder/"job.json", self.job)
        with self.assertRaisesRegex(ValueError, "isolated ASR"):
            editor.transcribe(self.args("transcribe", "--model", "small.en"))
        self.assertFalse((self.folder/"absent-cache").exists())

    def test_update_rejects_unknown_ids_and_preserves_manual_choices(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            editor.update(self.args("update", "--reject", "missing"))
        key = self.job["plan"]["cuts"][0]["id"]
        result = editor.update(self.args("update", "--reject", key, "--cut", "5.6:5.8"))
        _, job = editor.load(self.folder)
        self.assertFalse(job["plan"]["cuts"][0]["selected"])
        self.assertEqual(job["plan"]["cuts"][-1]["kind"], "manual")
        self.assertEqual(result["plan_signature"], tl.signature(job))

    def test_silence_on_one_track_does_not_remove_another_speaker(self):
        source, target = self.folder/"overlap.mkv", self.folder/"overlap-job"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=3",
                       "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-f", "lavfi", "-i", "sine=frequency=550:duration=3",
                       "-map", "0:v", "-map", "1:a", "-map", "2:a", "-t", "3", "-c:v", "libx264", "-c:a", "flac", source])
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        self.assertEqual(job["silences"], [])
        self.assertEqual(job["plan"]["cuts"], [])

    def test_out_of_phase_tracks_are_not_mistaken_for_silence(self):
        source, target = self.folder/"phase.mkv", self.folder/"phase-job"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=2",
                       "-f", "lavfi", "-i", "aevalsrc=0.2*sin(2*PI*440*t):s=48000:d=2",
                       "-f", "lavfi", "-i", "aevalsrc=-0.2*sin(2*PI*440*t):s=48000:d=2",
                       "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-c:a", "flac", source])
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        self.assertEqual(job["silences"], [])

    def test_portrait_fractional_render_and_fractional_captions(self):
        source, target = self.folder/"portrait.mkv", self.folder/"portrait-job"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x160:rate=30000/1001:duration=2",
                       "-f", "lavfi", "-i", "sine=frequency=550:duration=2", "-c:v", "libx264", "-c:a", "flac", source])
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        job["plan"]["cuts"] = [{"id": "manual", "kind": "manual", "reason": "fixture", "start": .4, "end": .7, "selected": True}]
        job["plan"]["chunk_seconds"] = 1
        editor.write(target/"job.json", job)
        args = self.args("preview", "--accept-plan", tl.signature(job), "--seconds", "2")
        args.job = target
        result = editor.preview(args)
        actual = editor.probe(result["output"])
        self.assertEqual((actual["width"], actual["height"]), (96, 160))
        self.assertAlmostEqual(float(editor.Fraction(actual["fps"])), 30000/1001, places=2)

    def test_crossfades_keep_audio_on_the_video_cut_timeline(self):
        source, target = self.folder/"ramp.mkv", self.folder/"ramp-job"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=4",
                       "-f", "lavfi", "-i", "aevalsrc=t*0.1:s=48000:d=4", "-c:v", "libx264", "-c:a", "flac", source])
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        job["plan"]["cuts"] = [{"id": "cut", "kind": "manual", "reason": "fixture", "start": 1, "end": 1.5, "selected": True}]
        job["plan"]["zooms"] = []
        editor.write(target/"job.json", job)
        args = self.args("preview", "--accept-plan", tl.signature(job), "--seconds", "4")
        args.job = target
        result = editor.preview(args)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", result["output"], "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
        samples = array.array('f', raw)
        for output_time, source_time in ((.5, .5), (1.2, 1.7), (2.5, 3.0)):
            self.assertAlmostEqual(samples[round(output_time*48000)], source_time*.1, delta=.002)

    def test_fractional_chunks_keep_the_same_source_frame_sequence(self):
        source, target = self.folder/"frame-colors.mkv", self.folder/"frame-colors-job"
        editor.ffmpeg(["-f", "lavfi", "-i", "nullsrc=size=160x96:rate=30000/1001:duration=2,geq=lum='N*3+20':cb=128:cr=128",
                       "-f", "lavfi", "-i", "sine=frequency=550:duration=2", "-c:v", "libx264", "-crf", "0", "-c:a", "flac", source])
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        job["plan"]["cuts"] = [{"id": "grid-cut", "kind": "manual", "reason": "fixture", "start": .3, "end": .7, "selected": True}]
        job["plan"]["chunk_seconds"] = 1
        chunked = editor.process(job, target/"chunked", job["scope"])["output"]
        job["plan"]["chunk_seconds"] = 3
        continuous = editor.process(job, target/"continuous", job["scope"])["output"]
        def pixels(path):
            return subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v", "-vf", "scale=1:1:flags=area,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        left, right = pixels(chunked), pixels(continuous)
        self.assertEqual(len(left), len(right))
        self.assertLessEqual(max(abs(a-b) for a, b in zip(left, right)), 1)

    def test_delayed_audio_silence_is_retained(self):
        source = self.folder/"delayed.mkv"
        editor.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=3",
                       "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                       "-filter_complex", "[1:a]adelay=1000|1000[a]", "-map", "0:v", "-map", "[a]",
                       "-c:v", "libx264", "-c:a", "flac", source])
        target = self.folder/"delay-job"
        editor.analyze(editor.parser().parse_args(["analyze", "--input", str(source), "--job", str(target)]))
        _, job = editor.load(target)
        job["plan"]["cuts"] = []
        editor.write(target/"job.json", job)
        args = self.args("preview", "--accept-plan", tl.signature(job), "--seconds", "3")
        args.job = target
        result = editor.preview(args)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", result["output"], "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
        samples = array.array('f', pcm)
        self.assertLess(max(abs(x) for x in samples[:43000]), 1e-5)
        self.assertGreater(max(abs(x) for x in samples[50000:60000]), .01)


def re_search_subtitles(text):
    import re
    return re.search(r"\bsubtitles\s+V->V", text)


if __name__ == "__main__":
    unittest.main()
