"""Real processing from a fresh copied installation; generated media only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
try:
    import numpy as np
    import soundfile as sf
except ImportError:
    np = sf = None

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('install_media',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

@unittest.skipUnless(np is not None and shutil.which('ffmpeg') and shutil.which('ffprobe'),
                     'Installed-media checks require audio requirements and FFmpeg/ffprobe')
class InstalledMediaTests(unittest.TestCase):
    def test_generated_audio_and_video_export_from_a_clean_install(self):
        with tempfile.TemporaryDirectory(prefix='installed media é ') as temp:
            base=Path(temp);skills=base/'show/.agents/skills'
            installer.install(skills)
            source=base/'synthetic.wav';rate=48000
            t=np.arange(rate*3)/rate
            envelope=np.sin(np.pi*np.minimum(t%0.8/0.55,1))**2
            tone=sum(np.sin(2*np.pi*137*n*t)/n for n in range(1,7))
            sf.write(source,0.1*envelope*tone+np.random.default_rng(52).normal(0,0.003,len(t)),rate,subtype='PCM_24')
            original=hashlib.sha256(source.read_bytes()).hexdigest()
            def run(*args):
                result=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
                self.assertEqual(result.returncode,0,result.stderr)
                return result
            repair=skills/'podcast-audio-repair/scripts/repair_audio.py'
            run(sys.executable,repair,source,base/'repair','--denoise','neural','--seconds','3',
                '--comparison-start','0.2','--comparison-seconds','1')
            report=json.loads((base/'repair/report.json').read_text(encoding='utf-8'))
            self.assertTrue(report['source_unchanged'])
            self.assertEqual(report['status'],'technical_checks_passed_listening_pending')
            self.assertEqual(sf.info(base/'repair/repaired.wav').frames,rate*3)
            square,wide=base/'square.png',base/'wide.png'
            for path,size in [(square,'100x100'),(wide,'160x90')]:
                run('ffmpeg','-v','error','-f','lavfi','-i','color=c=navy:s='+size,'-frames:v','1',path)
            metadata=base/'metadata.json'
            metadata.write_text(json.dumps({'title':'Fictional fixture','show_title':'Lantern Workshop','artist':'Morgan Vale',
                'description':'Generated test fixture, not speech.','content_summary':'Synthetic audio and supplied art.','tags':['test']}),encoding='utf-8')
            packager=skills/'podcast-packager/scripts/packager.py';job=base/'package'
            run(sys.executable,packager,'analyze','--input',base/'repair/repaired.wav','--job',job)
            run(sys.executable,packager,'package','--job',job,'--metadata',metadata,'--square',square,'--wide',wide)
            for filename in ['episode.mp3','episode.mp4','cover-square.jpg','featured-wide.jpg']:
                self.assertGreater((job/filename).stat().st_size,0)
            run('ffmpeg','-v','error','-i',job/'episode.mp4','-f','null','-')
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),original)

if __name__ == '__main__':
    unittest.main()
