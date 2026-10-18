"""Generated publishing/short-form fixtures; no models, network or private media."""
import argparse
import array
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


pk=load('packager','skills/podcast-packager/scripts/packager.py')
sc=load('shorts','skills/short-form-clips/scripts/shorts.py')
NS=argparse.Namespace


def tone_frequency(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ss','0.3','-t','1',
                                 '-ac','1','-ar','8000','-f','s16le','-'])
    samples=array.array('h',raw)
    return sum(a<0<=b for a,b in zip(samples,samples[1:]))


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'): raise unittest.SkipTest('FFmpeg required')
        cls.temp=tempfile.TemporaryDirectory(prefix='publishing space é ')
        cls.root=Path(cls.temp.name)
        cls.source=cls.root/'finished recording é.mkv'
        pk.ffmpeg(['-f','lavfi','-i','testsrc2=size=320x180:rate=30000/1001:duration=4',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4',
            '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=4',
            '-map','0:v','-map','1:a','-map','2:a','-filter:a:1','pan=stereo|c0=c0|c1=c0','-c:v','libx264','-c:a','pcm_s16le',
            '-metadata:s:a:0','title=Isolated microphone','-metadata:s:a:1','title=Approved mix',cls.source])
        cls.source_hash=pk.digest(cls.source)
        cls.square=cls.root/'square art.png'; cls.wide=cls.root/'wide art.png'
        for path,size in ((cls.square,'100x100'),(cls.wide,'160x90')):
            pk.ffmpeg(['-f','lavfi','-i','color=c=navy:s='+size,'-frames:v','1',path])

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def folder(self,name): return self.root/(self._testMethodName+'-'+name)


class PackagerTests(Fixture):
    def config(self,source=None,name='job'):
        root=self.folder(name)
        pk.analyze(NS(input=str(source or self.source),job=str(root),audio_track=1 if source is None else 0))
        meta=self.folder(name+'-metadata.json')
        pk.write(meta,{'title':'Synthetic episode','show_title':'Fixture show','artist':'Test host',
                       'description':'Generated fixture only.','content_summary':'Tone and test pattern.',
                       'tags':['test'],'chapters':[{'start':0,'title':'Opening'}]})
        return NS(job=str(root),metadata=str(meta),square=str(self.square),wide=str(self.wide),resume=False)

    def test_video_package_embeds_art_and_exports_selected_mix(self):
        args=self.config(); result=pk.package(args); root=Path(args.job)
        for filename,dimensions in [('cover-square.jpg',[3000,3000]),('featured-wide.jpg',[3840,2160])]:
            v=pk.video(pk.probe(root/filename)); self.assertEqual([v['width'],v['height']],dimensions)
            self.assertLess((root/filename).stat().st_size,2_000_001)
        mp3=pk.probe(root/'episode.mp3')
        self.assertTrue(any(s.get('disposition',{}).get('attached_pic') for s in mp3['streams']))
        self.assertEqual(mp3['format']['tags']['title'],'Synthetic episode')
        self.assertAlmostEqual(tone_frequency(root/'episode.mp3'),880,delta=12)
        self.assertAlmostEqual(tone_frequency(root/'episode.mp4'),880,delta=12)
        self.assertTrue(result['source_unchanged']); self.assertEqual(pk.digest(self.source),self.source_hash)
        report=json.loads((root/'report.json').read_text())
        self.assertEqual(report['unselected_audio_tracks'],1)
        self.assertTrue(report['verified']['episode.mp4']['decoded'])
        self.assertEqual(pk.audio(pk.probe(root/'episode.mp4'))[0]['channels'],2)
        before={n:pk.digest(root/n) for n in report['files']}
        args.resume=True; pk.package(args)
        self.assertEqual(before,{n:pk.digest(root/n) for n in before})
        (root/'episode.mp3').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'): pk.package(args)

    def test_audio_only_creates_static_video(self):
        source=self.folder('audio.wav')
        pk.ffmpeg(['-f','lavfi','-i','sine=frequency=330:duration=1.5',source])
        args=self.config(source); pk.package(args)
        v=pk.video(pk.probe(Path(args.job)/'episode.mp4'))
        self.assertEqual([v['width'],v['height']],[1920,1080]); self.assertEqual(v['avg_frame_rate'],'30/1')

    def test_interrupted_stage_resumes_without_replacing_completed_art(self):
        args=self.config(); original=pk.ffmpeg
        def interrupted(values,**kwargs):
            if str(values[-1]).endswith('.mp3'): raise OSError('simulated interruption')
            return original(values,**kwargs)
        with patch.object(pk,'ffmpeg',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'interruption'): pk.package(args)
        root=Path(args.job); art_hash=pk.digest(root/'cover-square.jpg')
        self.assertFalse((root/'.running').exists())
        args.resume=True; pk.package(args)
        self.assertEqual(art_hash,pk.digest(root/'cover-square.jpg'))

    def test_storage_source_and_existing_job_guards(self):
        args=self.config()
        with patch.object(pk.shutil,'disk_usage',return_value=NS(free=0)):
            with self.assertRaisesRegex(ValueError,'storage'): pk.package(args)
        self.assertFalse((Path(args.job)/'episode.mp3').exists())
        with self.assertRaises(FileExistsError): pk.analyze(NS(input=str(self.source),job=args.job,audio_track=0))
        job=json.loads((Path(args.job)/'job.json').read_text()); job['source']['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'Source changed'): pk.check_source(job)

    def test_bad_metadata_wrong_art_and_missing_tools(self):
        base={'title':'a','description':'b','show_title':'c','artist':'d','content_summary':'e','tags':['topic']}
        for extra in ({'tags':'not a list'},{'chapters':[{'start':float('nan'),'title':'x'}]},
                      {'chapters':[{'start':1,'title':'x'},{'start':0,'title':'y'}]}):
            with self.assertRaises(ValueError): pk.metadata({**base,**extra},4)
        with self.assertRaisesRegex(ValueError,'aspect ratio'):
            pk.artwork(self.square,self.folder('bad.jpg'),3840,2160,None)
        with patch.object(pk.shutil,'which',return_value=None): self.assertFalse(pk.doctor()['ready'])

    def test_cli_unicode_paths_on_legacy_console(self):
        env={**os.environ,'PYTHONIOENCODING':'ascii'}
        for name,script in (('package',pk.__file__),('shorts',sc.__file__)):
            job=self.folder(name+'-\u4e16\u754c')
            result=subprocess.run([sys.executable,script,'analyze','--input',str(self.source),'--job',str(job)],
                                  env=env,capture_output=True,text=True,encoding='ascii')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['job'],str(job.resolve()))


class ShortsTests(Fixture):
    def config(self,name='job',source=None,mode='crop',captions='burn'):
        root=self.folder(name)
        sc.analyze(NS(input=str(source or self.source),job=str(root),audio_track=1 if source is None else 0,width=180,height=320))
        job=sc.read(root/'job.json'); sha=job['source']['sha256']
        words={'source_sha256':sha,'coverage':[0,job['duration']],
               'words':[{'word':w,'start':a,'end':b} for w,a,b in [('Try',.2,.4),('this.',.4,.7),
                    ('Keep',1,1.2),('context',1.2,1.6),('complete.',1.6,2.1)]]}
        candidate={'id':'clip-01','start':0,'end':2.5,'title':'Fixture idea','hook':'Try this.',
            'hook_evidence':{'start':.2,'end':.7,'text':'Try this.'},'why':'Complete generated example.',
            'payoff':'Keep context complete.','scores':dict(hook=4,standalone=5,payoff=4,audience=3),'selected':True,
            'framing':{'mode':mode,'center_x':.55,'center_y':.4},'captions':captions,
            'description':'Synthetic source only.','tags':['test'],'cover_at':1}
        wordsfile=self.folder(name+'-words.json'); candidatesfile=self.folder(name+'-candidates.json')
        sc.write(wordsfile,words); sc.write(candidatesfile,{'source_sha256':sha,'clips':[candidate]})
        plan=sc.plan(NS(job=str(root),transcript=str(wordsfile),candidates=str(candidatesfile)))
        return root,job,words,candidate,plan['plan_signature']

    def test_crop_burn_preview_delivery_and_tamper_guard(self):
        root,job,words,candidate,sig=self.config()
        result=sc.preview(NS(job=str(root),accept_plan=sig,resume=False))
        folder=root/'clip-01'; self.assertTrue((folder/'captioned.mp4').exists())
        self.assertIn('Try this.',(folder/'captions.srt').read_text())
        self.assertAlmostEqual(tone_frequency(folder/'clean.mp4'),880,delta=12)
        meta=sc.read(folder/'metadata.json'); self.assertEqual(meta['source_interval'],[0,2.5])
        self.assertEqual(meta['output_interval'],[0,2.5])
        self.assertEqual(sc.verify(folder/'captioned.mp4',job,2.5)['fps'],'30000/1001')
        self.assertEqual(sc.digest(self.source),self.source_hash)
        delivery=sc.render(NS(job=str(root),accept_preview=result['preview_signature']))
        self.assertFalse(sc.read(delivery['delivery'])['uploaded'])
        self.assertEqual(result['preview_signature'],sc.preview(NS(job=str(root),resume=True))['preview_signature'])
        (folder/'youtube-shorts.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'): sc.render(NS(job=str(root),accept_preview=result['preview_signature']))

    def test_portrait_fit_sidecar_and_nonzero_mapping(self):
        source=self.folder('portrait.mp4')
        sc.ffmpeg(['-f','lavfi','-i','testsrc2=size=90x160:rate=24:duration=4',
            '-f','lavfi','-i','sine=frequency=330:duration=4','-c:v','libx264','-c:a','aac',source])
        root,job,words,candidate,sig=self.config(source=source,mode='fit',captions='srt')
        candidate.update(start=.8,end=3.3,hook='Keep context complete.',hook_evidence={'start':1,'end':2.1,'text':'Keep context complete.'})
        cf=self.folder('revised-candidates.json'); wf=self.folder('revised-words.json')
        sc.write(cf,{'source_sha256':job['source']['sha256'],'clips':[candidate]}); sc.write(wf,words)
        sig=sc.plan(NS(job=str(root),transcript=str(wf),candidates=str(cf)))['plan_signature']
        sc.preview(NS(job=str(root),accept_plan=sig,resume=False))
        self.assertEqual(sc.verify(root/'clip-01/clean.mp4',job,2.5)['fps'],'24/1')
        self.assertFalse((root/'clip-01/captioned.mp4').exists())
        self.assertIn('00:00:00,200',(root/'clip-01/captions.srt').read_text())
        groups=sc.caption_groups(words['words'],1,2.5)
        self.assertEqual(groups[0]['start'],0); self.assertEqual(groups[0]['text'],'Keep context complete.')

    def test_interrupted_preview_resume_and_storage(self):
        root,job,words,candidate,sig=self.config(captions='srt')
        with patch.object(sc.shutil,'disk_usage',return_value=NS(free=0)):
            with self.assertRaisesRegex(ValueError,'storage'): sc.preview(NS(job=str(root),accept_plan=sig,resume=False))
        original=sc.ffmpeg
        def interrupted(values,**kwargs):
            if str(values[-1]).endswith('.jpg'): raise OSError('simulated interruption')
            return original(values,**kwargs)
        with patch.object(sc,'ffmpeg',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'interruption'): sc.preview(NS(job=str(root),resume=True))
        clean=root/'clip-01/clean.mp4'; before=sc.digest(clean)
        result=sc.preview(NS(job=str(root),resume=True)); self.assertEqual(before,sc.digest(clean))
        self.assertTrue(result['preview_signature'])

    def test_transcript_bounds_hook_and_filename_validation(self):
        root,job,words,candidate,sig=self.config()
        bad=copy.deepcopy(words); bad['source_sha256']='other'
        with self.assertRaisesRegex(ValueError,'match'): sc.transcript(bad,job)
        bad=copy.deepcopy(words); bad['words'][1]['start']=.3
        with self.assertRaisesRegex(ValueError,'nonoverlapping'): sc.transcript(bad,job)
        for change in ({'id':'../outside'},{'end':999},{'selected':'yes'},
                       {'hook':'fabricated'},{'scores':dict(hook=float('nan'),standalone=4,payoff=4,audience=4)},
                       {'framing':{'mode':'tracking'}},{'tags':'bad'}):
            with self.assertRaises(ValueError): sc.candidates({'source_sha256':job['source']['sha256'],'clips':[{**candidate,**change}]},words,job)
        with self.assertRaisesRegex(ValueError,'signature'): sc.preview(NS(job=str(root),accept_plan='other',resume=False))
        with patch.object(sc.shutil,'which',return_value=None): self.assertFalse(sc.doctor()['ready'])

    def test_caption_escape_and_source_plan_binding(self):
        root,job,words,candidate,sig=self.config()
        groups=[{'start':0,'end':1,'text':r'{\pos(0,0)} text'}]
        sc.subtitles(root,groups,180,320)
        ass=(root/'captions.ass').read_text(encoding='utf-8')
        self.assertNotIn(r'{\pos',ass); self.assertIn(r'{\pos',(root/'captions.srt').read_text())
        plan=sc.read(root/'plan.json'); plan['clips'][0]['end']=3; sc.write(root/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'changed'): sc.load_plan(root)


if __name__=='__main__': unittest.main()
