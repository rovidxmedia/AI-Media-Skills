import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pack_install', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='media install space é ')
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'fictional show 世界'
        self.skills = self.project / '.agents/skills'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, path, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
        return subprocess.run([sys.executable, str(path), *map(str,args)], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=60, env=env)

    def test_dry_run_writes_nothing(self):
        result = installer.install(self.skills, dry_run=True)
        self.assertFalse(self.project.exists())
        self.assertTrue(result['dry_run'])
        self.assertEqual(len(result['skills']), 8)

    def test_complete_copy_preserves_assets_licenses_and_is_idempotent(self):
        result = installer.install(self.skills)
        self.assertEqual(len(result['skills']), 8)
        for name in installer.SKILLS:
            self.assertEqual(installer.files(ROOT/'skills'/name), installer.files(self.skills/name))
            self.assertFalse((self.skills/name).is_symlink())
            self.assertTrue((self.skills/name/'LICENSE').is_file())
        self.assertTrue((self.skills/'podcast-audio-repair/assets/cb.rnnn').is_file())
        self.assertTrue((self.skills/'podcast-audio-repair/assets/NARA-WPE-LICENSE.txt').is_file())
        again = installer.install(self.skills)
        self.assertTrue(all(x['action']=='unchanged' for x in again['skills']))

    def test_single_skill_stays_focused_and_radio_adds_repair(self):
        installer.install(self.skills, ['podcast-packager'])
        self.assertEqual({p.name for p in self.skills.iterdir()}, {'podcast-packager'})
        target = self.base/'radio-only'
        installer.install(target, ['that-radio-voice'])
        self.assertEqual({p.name for p in target.iterdir()}, {'that-radio-voice','podcast-audio-repair'})

    def test_conflict_preflight_copies_nothing_and_preserves_edits(self):
        conflict = self.skills/'editor'
        conflict.mkdir(parents=True)
        (conflict/'SKILL.md').write_text('User-owned modified editor', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Existing skill differs'):
            installer.install(self.skills)
        self.assertEqual(list(self.skills.iterdir()), [conflict])
        self.assertEqual((conflict/'SKILL.md').read_text(), 'User-owned modified editor')

    def test_invalid_selection_and_source_destinations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown skill'):
            installer.install(self.skills, ['not-a-skill'])
        for target in [ROOT/'skills',ROOT/'skills/producer/nested']:
            with self.assertRaisesRegex(ValueError, 'source tree'):
                installer.install(target)
        self.assertFalse(self.project.exists())

    def test_existing_link_is_not_overwritten(self):
        self.skills.mkdir(parents=True)
        outside = self.base/'existing producer'; outside.mkdir()
        try:
            (self.skills/'producer').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symbolic links is unavailable for this account')
        with self.assertRaisesRegex(ValueError, 'Existing skill is a link'):
            installer.install(self.skills)
        self.assertTrue(outside.is_dir())
        self.assertFalse((self.skills/'editor').exists())

    def test_project_alias_installs_into_the_same_physical_project(self):
        self.project.mkdir(parents=True)
        alias = self.base / 'project alias'
        try:
            alias.symlink_to(self.project, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symbolic links is unavailable for this account')
        target = installer.destination('codex', project=alias)
        installer.install(target, ['podcast-packager'])
        self.assertEqual(target.resolve(), self.skills.resolve())
        self.assertTrue((self.skills / 'podcast-packager/SKILL.md').is_file())

    def test_scope_uses_requested_project_user_or_explicit_directory(self):
        self.assertEqual(installer.destination('codex',self.project),self.project/'.agents/skills')
        self.assertEqual(installer.destination('claude',self.project),self.project/'.claude/skills')
        with patch.object(Path,'home',return_value=self.base/'a different user'):
            self.assertEqual(installer.destination('codex',user=True),self.base/'a different user/.agents/skills')
        with self.assertRaisesRegex(ValueError, 'Antigravity personal paths'):
            installer.destination('antigravity',user=True)
        custom=self.base/'custom host'
        self.assertEqual(installer.destination('codex',skills_dir=custom),custom)

    def test_installed_fictional_show_setup_stays_private_and_manual(self):
        installer.install(self.skills)
        producer=self.skills/'producer/scripts/producer.py'
        result=self.cli(producer,'setup','--project',self.project,'--config',ROOT/'examples/fictional-show.json')
        self.assertEqual(result.returncode,0,result.stderr)
        profile=json.loads((self.project/'.producer/project.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['show']['name'],'Lantern Workshop')
        self.assertEqual(profile['show']['hosts'],['Morgan Vale'])
        self.assertEqual(profile['distribution']['mode'],'manual')
        self.assertEqual(profile['distribution']['destinations'],[])
        self.assertIsNone(profile['distribution']['cadence'])
        self.assertFalse(profile['skills']['video-motion-graphics']['enabled'])
        self.assertEqual((self.project/'.producer/.gitignore').read_text().splitlines()[0],'*')
        result=self.cli(producer,'doctor','--project',self.project)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertFalse(report['gpu_inference_tested'])
        self.assertTrue(all(Path(v).is_relative_to(self.skills) for v in report['skills'].values()))
        self.assertFalse((self.project/'inputs').exists())

    def test_installed_cpu_helpers_find_their_resources(self):
        installer.install(self.skills)
        for script in ['producer/scripts/producer.py','editor/scripts/editor.py',
                       'video-enhance/scripts/video_enhance.py','podcast-packager/scripts/packager.py',
                       'short-form-clips/scripts/shorts.py','video-motion-graphics/scripts/graphics.py']:
            with self.subTest(script=script):
                result=self.cli(self.skills/script,'--help')
                self.assertEqual(result.returncode,0,result.stderr)

    def test_public_files_have_no_machine_paths_links_or_broken_references(self):
        for folder in (ROOT/'skills').iterdir():
            if not folder.is_dir():
                continue
            self.assertIn(folder.name,installer.SKILLS)
            self.assertFalse(installer.linked(folder))
            for p in folder.rglob('*'):
                self.assertFalse(installer.linked(p),str(p))
                if p.is_file() and p.suffix in ('.md','.py','.json','.yaml','.txt'):
                    content=p.read_text(encoding='utf-8-sig')
                    self.assertNotRegex(content,r'[CE]:[/\\]Users[/\\]rob|AAA - DELEGATED|AAA - Music Videos')
                    if p.suffix=='.md':
                        body=re.sub(r'```.*?```','',content,flags=re.S)
                        for raw in re.findall(r'\]\(([^\n]+?)\)',body):
                            target=raw.strip('<>').split('#')[0]
                            if target and not re.match(r'\w+://|mailto:',target) and '<' not in target:
                                self.assertTrue((p.parent/target).exists(),str(p)+': '+target)

if __name__ == '__main__':
    unittest.main()
