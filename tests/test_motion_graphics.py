"""Generated alpha fixtures test the bridge; actual HyperFrames rendering is separate."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('graphics',ROOT/'skills/video-motion-graphics/scripts/graphics.py')
mg=importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='graphics é '); cls.base=Path(cls.tmp.name)
        cls.source=cls.base/'finished source 世界.mkv'
        mg.ffmpeg(['-f','lavfi','-i','color=c=navy:size=320x180:rate=30000/1001:duration=2',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2',
            '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=2',
            '-map','0:v','-map','1:a','-map','2:a','-c:v','libx264','-c:a','pcm_s16le',
            '-metadata:s:a:0','title=Mix','-metadata:s:a:0','language=eng',
            '-metadata:s:a:1','title=Isolated',cls.source])
        cls.overlay=cls.make_overlay('overlay',320,180,30)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    @classmethod
    def make_overlay(cls,name,width,height,count,opaque=False):
        raw=cls.base/(name+'.rgba'); pixels=bytearray(bytes((0,0,0,255 if opaque else 0))*width*height)
        for y in range(height//5,height//2):
            first=(y*width+width//10)*4; last=(y*width+width//2)*4
            pixels[first:last]=bytes((255,0,0,255))*((last-first)//4)
        raw.write_bytes(pixels); output=cls.base/(name+'.mov')
        mg.ffmpeg(['-stream_loop','-1','-f','rawvideo','-pixel_format','rgba','-video_size',f'{width}x{height}',
            '-framerate','30000/1001','-i',raw,'-frames:v',str(count),'-c:v','prores_ks','-profile:v','4',
            '-pix_fmt','yuva444p10le','-alpha_bits','16',output])
        return output

    def setUp(self):
        self.root=self.base/self._testMethodName
        self.job=mg.analyze(self.source,self.root)
        self.cue={'id':'speaker','kind':'lower-third','start':.5,'end':1.5,'box':[.1,.2,.4,.3],
                  'copy':'Test host','purpose':'Identify speaker','evidence':'Synthetic fixture credits'}
        self.data={'source_sha256':self.job['source']['sha256'],'cues':[self.cue]}

    def prepare(self):
        cues=self.root/'cues.json'; mg.write(cues,self.data)
        plan=mg.plan(self.root,cues); manifest=self.root/'overlays.json'
        mg.write(manifest,{'source_sha256':self.job['source']['sha256'],'plan_signature':plan['signature'],
            'hyperframes_version':'synthetic-fixture-not-a-HyperFrames-render','overlays':{'speaker':str(self.overlay)}})
        return plan,manifest

    def test_fractional_grid_exact_alpha_composite_all_audio_and_source(self):
        plan,manifest=self.prepare(); self.assertEqual(plan['cues'][0]['frames'],30)
        self.assertAlmostEqual(plan['cues'][0]['start'],float(Fraction(15015,30000)))
        output=self.root/'master ü.mkv'
        result=mg.composite(self.root,manifest,output,plan['signature'])
        self.assertEqual(result['verification']['frames'],60)
        self.assertEqual(result['verification']['audio_tracks'],2)
        def pixel(at):
            data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(output),
                '-vf','crop=2:2:40:50,format=rgb24','-frames:v','1','-f','rawvideo','-'])
            return list(data[:3])
        early,middle,late=pixel(.2),pixel(.9),pixel(1.8)
        self.assertGreater(early[2],early[0]+60); self.assertGreater(late[2],late[0]+60)
        self.assertGreater(middle[0],200); self.assertLess(middle[2],30)
        self.assertEqual(mg.digest(self.source),self.job['source']['sha256'])
        with self.assertRaisesRegex(ValueError,'new MKV'): mg.composite(self.root,manifest,output,plan['signature'])

    def test_source_plan_assets_and_manifest_binding(self):
        screenshot=self.root/'screen.png'
        mg.ffmpeg(['-f','lavfi','-i','color=size=64x64:color=white','-frames:v','1',screenshot])
        self.cue.update(kind='screenshot',asset='screen.png',asset_origin='Locally generated fixture',
            highlights=[{'box':[.1,.1,.4,.1],'start':.2,'end':.7,'text':'Verified synthetic target'}])
        plan,manifest=self.prepare(); screenshot.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Screenshot changed'): mg.load_plan(self.root)
        with self.assertRaisesRegex(ValueError,'Plan exists'): mg.plan(self.root,self.root/'cues.json')
        wrong=copy.deepcopy(self.job); wrong['source']['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'Source changed'): mg.source_ok(wrong)
        mg.write(self.root/'plan.json',{**plan,'signature':'changed'})
        with self.assertRaisesRegex(ValueError,'Plan changed'): mg.load_plan(self.root)

    def test_bounds_reserved_regions_collisions_and_highlights(self):
        for change in ({'start':float('nan')},{'end':20},{'box':[.9,0,.4,.2]},
                       {'id':'../escape'},{'allow_overlap':'yes'},
                       {'highlights':[{'box':[0,0,1,1],'start':0,'end':1,'text':'x'}]}):
            data=copy.deepcopy(self.data); data['cues'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError): mg.validate_cues(data,self.job,self.root)
        data=copy.deepcopy(self.data); data['reserved_regions']=[{'label':'face','box':[.2,.2,.2,.2]}]
        with self.assertRaisesRegex(ValueError,'reserved'): mg.validate_cues(data,self.job,self.root)
        data=copy.deepcopy(self.data); other={**self.cue,'id':'second'}; data['cues'].append(other)
        with self.assertRaisesRegex(ValueError,'collide'): mg.validate_cues(data,self.job,self.root)
        for c in data['cues']: c['allow_overlap']=True
        self.assertEqual(len(mg.validate_cues(data,self.job,self.root)['cues']),2)
        image=self.root/'screen.png'; image.write_bytes(b'fixture asset')
        data=copy.deepcopy(self.data); data['cues'][0].update(kind='screenshot',asset=str(image),asset_origin='fixture',
            highlights=[{'box':[.95,0,.1,.1],'start':0,'end':.8,'text':'target'}])
        with self.assertRaisesRegex(ValueError,'escapes'): mg.validate_cues(data,self.job,self.root)
        data['cues'][0]['highlights'][0].update(box=[0,0,.1,.1],end=20)
        with self.assertRaisesRegex(ValueError,'local'): mg.validate_cues(data,self.job,self.root)

    def test_overlay_alpha_geometry_frames_storage_and_acceptance_guards(self):
        plan,manifest=self.prepare(); cue=plan['cues'][0]
        for name,w,h,n,opaque,reason in [('opaque',320,180,30,True,'Midpoint'),
             ('small',160,90,30,False,'canvas'),('short',320,180,10,False,'frame count')]:
            overlay=self.make_overlay(name,w,h,n,opaque)
            with self.assertRaisesRegex(ValueError,reason): mg.overlay_ok(overlay,cue,self.job)
        with self.assertRaisesRegex(ValueError,'ProRes'): mg.overlay_ok(self.source,cue,self.job)
        output=self.root/'master.mkv'
        with self.assertRaisesRegex(ValueError,'current cue plan'): mg.composite(self.root,manifest,output,'wrong')
        with patch.object(mg.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
            with self.assertRaisesRegex(ValueError,'storage'): mg.composite(self.root,manifest,output,plan['signature'])
        self.assertFalse(output.exists())
        imported=mg.read(manifest); imported['plan_signature']='wrong'; mg.write(manifest,imported)
        with self.assertRaisesRegex(ValueError,'must match'): mg.composite(self.root,manifest,output,plan['signature'])

    def test_sdr_high_depth_and_undefined_mp4_language(self):
        for kind in ('ten-bit','mp4'):
            source=self.root/(kind+('.mkv' if kind=='ten-bit' else '.mp4'))
            if kind=='ten-bit':
                mg.ffmpeg(['-i',self.source,'-map','0:v:0','-map','0:a:0','-c:v','ffv1','-pix_fmt','yuv420p10le','-c:a','copy',source])
            else:
                mg.ffmpeg(['-i',self.source,'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-metadata:s:a:0','language=und',source])
            root=self.root/kind; job=mg.analyze(source,root)
            cuefile=root/'cues.json'; mg.write(cuefile,{'source_sha256':job['source']['sha256'],'cues':[self.cue]})
            plan=mg.plan(root,cuefile); manifest=root/'overlays.json'
            mg.write(manifest,{'source_sha256':job['source']['sha256'],'plan_signature':plan['signature'],
                'hyperframes_version':'synthetic','overlays':{'speaker':str(self.overlay)}})
            output=root/'output.mkv'; result=mg.composite(root,manifest,output,plan['signature'])
            self.assertEqual(result['verification']['frames'],60)
            if kind=='ten-bit': self.assertEqual(mg.video(mg.probe(output))['pix_fmt'],'yuv444p16le')

    def test_source_preparation_is_explicit(self):
        original=mg.probe(self.source)
        for change in ({'color_transfer':'smpte2084'},{'color_primaries':'bt2020'},
                       {'field_order':'tt'},{'sample_aspect_ratio':'4:3'},
                       {'side_data_list':[{'rotation':90}]},{'avg_frame_rate':'27/1'}):
            info=copy.deepcopy(original); mg.video(info).update(change)
            target=self.root/'unprepared'
            with self.subTest(change=change),patch.object(mg,'probe',return_value=info),self.assertRaises(ValueError):
                mg.analyze(self.source,target)
            self.assertFalse(target.exists())


if __name__=='__main__': unittest.main()
