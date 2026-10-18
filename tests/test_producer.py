"""Producer orchestration contracts with synthetic files and simulated publisher readbacks.

These checks do not run media engines, authenticate or exercise real uploads.
"""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('producer',ROOT/'skills/producer/scripts/producer.py')
pr=importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='producer space é '); self.base=Path(self.temp.name)
        self.project=self.base/'show 世界'; self.project.mkdir()
        self.source=self.base/'raw recording.mkv'; self.source.write_bytes(b'synthetic source; not a decoded video')
        self.config={'show':{'name':'Synthetic show','description':'A generated test production.','hosts':['Test host'],
                             'format':'both','language':'en'},
                     'skills':{'short-form-clips':{'count':1}},
                     'distribution':{'mode':'review','destinations':[
                         {'id':'youtube','platform':'youtube','account_id':'channel-test','routes':['full-video','short']},
                         {'id':'podcast','platform':'spreaker','account_id':'show-test','routes':['full-audio']}]}}
        self.configfile=self.base/'setup.json'; pr.write(self.configfile,self.config)
        with patch.object(pr,'doctor',return_value={'gpu_inference_tested':False,'tools':{},'skills':{}}):
            pr.setup(self.project,self.configfile)
        self.job=self.base/'episode'; pr.init(self.source,self.job,self.project)

    def tearDown(self): self.temp.cleanup()

    def file(self,name,data=None):
        p=self.job/name; p.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(data,dict): pr.write(p,data)
        else: p.write_bytes(data or ('synthetic '+name).encode())
        return p

    def stage(self,name,replace=False,extra=None):
        job=pr.load(self.job); parent=pr.stage_input(job,name)
        source=job['source'] if parent is None else job['stages'][parent]['artifacts']['media']
        artifacts={}
        for key in pr.REQUIRED[name]:
            ext={('package','video'):'.mp4',('package','audio'):'.mp3',('package','square'):'.jpg',('package','wide'):'.jpg'}.get((name,key),'.json' if key!='media' else '.mkv')
            data={'source_sha256':source['sha256']} if key=='words' else None
            artifacts[key]=str(self.file(name+'/'+key+ext,data))
        if name=='shorts': artifacts['short-01']=str(self.file(name+'/clip.mp4'))
        data={'input_sha256':source['sha256'],'artifacts':artifacts,**(extra or {})}
        path=self.file('receipt-'+name+'.json',data); return pr.record(self.job,name,path,replace)

    def all_stages(self):
        for name in pr.stage_graph(pr.load(self.job)): self.stage(name)

    def test_graphics_only_runs_when_requested_and_blocks_downstream_until_done(self):
        self.assertNotIn('graphics',pr.status(self.job)['stages'])
        self.all_stages()
        with self.assertRaisesRegex(ValueError,'must be requested'):
            self.stage('graphics')
        settings=self.file('graphics-settings.json',{'enabled':True,'style':'restrained'})
        result=pr.graphics_preferences(self.job,settings,'test-user-request-graphics')
        self.assertEqual(result['next'],['graphics'])
        self.assertEqual(result['stages']['master'],'stale')
        pending=self.file('pending-master.json',{})
        with self.assertRaisesRegex(ValueError,'prerequisite'): pr.record(self.job,'master',pending,replace=True)
        self.stage('graphics')
        self.stage('master',replace=True)
        job=pr.load(self.job)
        self.assertEqual(job['stages']['master']['input_sha256'],job['stages']['graphics']['artifacts']['media']['sha256'])
        self.assertEqual(pr.status(self.job)['stages']['transcript'],'stale')
        self.assertFalse(pr.read(self.project/'.producer/project.json')['skills']['video-motion-graphics']['enabled'])
        self.assertEqual(job['graphics_revisions'][0]['decision_reference'],'test-user-request-graphics')
        self.assertIn('project',job['stages']['graphics']['artifacts'])

    def test_legacy_episode_graph_and_graphics_revision_guards(self):
        self.all_stages(); job=pr.load(self.job)
        del job['profile']['skills']['video-motion-graphics']; pr.save(self.job,job)
        self.assertTrue(all(s=='completed' for s in pr.status(self.job)['stages'].values()))
        for setting in ({'enabled':'if-needed'},{'enabled':True,'style':'random'},{'unrelated':True}):
            path=self.file('bad-graphics.json',setting)
            with self.assertRaises(ValueError): pr.graphics_preferences(self.job,path,'test-request')
        chosen=self.file('graphics-settings.json',{'enabled':True})
        pr.graphics_preferences(self.job,chosen,'test-request'); self.stage('graphics')
        old=pr.load(self.job)['stages']['graphics']['artifacts']['media']['path']
        style=self.file('graphics-style.json',{'style':'explainer'})
        pr.graphics_preferences(self.job,style,'test-style-change')
        job=pr.load(self.job)
        self.assertNotIn('graphics',job['stages']); self.assertTrue(Path(old).exists())
        self.assertIsNotNone(job['graphics_revisions'][-1]['previous_receipt'])
        job['placements']={'existing':{}}; pr.save(self.job,job)
        with self.assertRaisesRegex(ValueError,'Distribution already started'):
            pr.graphics_preferences(self.job,chosen,'test-request')

    def plan(self,action='schedule',placement='episode-video'):
        job=pr.load(self.job); arts=job['stages']['package']['artifacts']
        self.publish_at=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
        item={'id':placement,'destination':'youtube','route':'full-video','action':action,'visibility':'public',
              'files':[arts[k]['path'] for k in ('video','wide','metadata')],
              'account_evidence':str(self.file('account-readback.json',{'platform':'youtube','channel_id':'channel-test'})),
              'publish_at':self.publish_at,'timezone':'Etc/UTC'}
        return self.file('release-plan.json',{'placements':[item]})

    def authorize(self,signature):
        evidence=self.file('approval.json',{'release_signature':signature,'kind':'user-message',
            'reference':'simulated-test-message-1','quote':'Approved: schedule these exact synthetic files.'})
        pr.approve(self.job,evidence)

    def result(self,status,**kwargs):
        data={'status':status,'platform':'youtube','account_id':'channel-test',
              'readback':str(self.file('readback-'+status+'.json',{'simulated_platform_state':status})),
              'remote_id':'remote-test-1','url':'https://example.invalid/video/test','visibility':'public',
              'publish_at':self.publish_at,**kwargs}
        return self.file('result-'+status+'.json',data)

    def test_setup_defaults_machine_separation_update_and_doctor(self):
        profile=pr.read(self.project/'.producer/project.json')
        self.assertEqual(profile['skills']['editor']['style'],'natural')
        self.assertFalse(profile['skills']['that-radio-voice']['enabled'])
        self.assertEqual(profile['distribution']['mode'],'review')
        self.assertNotIn('gpu_inventory',profile)
        self.assertIn('*',(self.project/'.producer/.gitignore').read_text())
        with self.assertRaisesRegex(ValueError,'already configured'): pr.setup(self.project,self.configfile)
        changed=copy.deepcopy(self.config); changed['show']['name']='New name'; pr.write(self.configfile,changed)
        with patch.object(pr,'doctor',return_value={'gpu_inference_tested':False}): pr.setup(self.project,self.configfile,update=True)
        self.assertEqual(len(list((self.project/'.producer/config-history').glob('*.json'))),1)
        self.assertEqual(pr.load(self.job)['profile']['show']['name'],'Synthetic show')
        with patch.object(pr.shutil,'which',return_value=None),patch.object(pr,'command',return_value=None):
            inventory=pr.doctor(self.project,[ROOT/'skills'])
        self.assertFalse(inventory['core_available']); self.assertFalse(inventory['gpu_inference_tested'])
        self.assertTrue(all(inventory['skills'].values())); self.assertGreater(inventory['free_storage_bytes'],0)

    def test_profile_validation_credentials_and_run_overrides(self):
        for change in ({'show':{}},{'skills':{'editor':{'style':'mystery'}}},
                       {'skills':{'unknown':{}}},{'skills':{'short-form-clips':{'count':True}}},
                       {'brand':{'api_key':'do-not-store'}},{'distribution':{'mode':'auto'}},
                       {'distribution':{'destinations':[{'id':'unsafe/ID','platform':'youtube','routes':['short']}]}}):
            with self.subTest(change=change),self.assertRaises(ValueError): pr.project_config({**self.config,**change})
        overrides=self.file('overrides.json',{'skills':{'editor':{'style':'tight'}}})
        other=self.base/'other episode'; pr.init(self.source,other,self.project,overrides)
        self.assertEqual(pr.load(other)['profile']['skills']['editor']['style'],'tight')
        self.assertEqual(pr.read(self.project/'.producer/project.json')['skills']['editor']['style'],'natural')

    def test_stages_resume_and_lineage_invalidation(self):
        self.assertEqual(pr.status(self.job)['next'],['diagnose'])
        with self.assertRaisesRegex(ValueError,'prerequisite'):
            pr.record(self.job,'edit',self.file('premature.json',{'input_sha256':pr.digest(self.source),'artifacts':{}}))
        self.all_stages(); self.assertEqual(pr.status(self.job)['stages']['review'],'completed')
        before=pr.load(self.job)['stages']['edit']['artifacts']['media']['sha256']
        with self.assertRaisesRegex(ValueError,'Stage exists'): self.stage('edit')
        self.stage('edit',replace=True)
        status=pr.status(self.job)
        self.assertEqual(status['next'],['audio']); self.assertEqual(status['stages']['transcript'],'stale')
        self.assertEqual(pr.load(self.job)['stages']['edit']['artifacts']['media']['sha256'],before)
        # Re-recording is deliberate even if bytes match; downstream decisions need reconciliation.
        self.assertFalse(status['publishing_permission_recorded'])

    def test_source_plan_and_completed_artifact_mutation_guards(self):
        self.stage('diagnose'); report=pr.load(self.job)['stages']['diagnose']['artifacts']['report']
        Path(report['path']).write_bytes(b'changed')
        self.assertEqual(pr.status(self.job)['stages']['diagnose'],'changed')
        with self.assertRaisesRegex(ValueError,'prerequisite'): self.stage('prepare')
        self.source.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError,'source changed'): pr.status(self.job)
        other=self.base/'manifest job'; pr.init(self.source,other,self.project)
        data=pr.read(other/'production.json'); data['profile']['show']['name']='tamper'; pr.write(other/'production.json',data)
        with self.assertRaisesRegex(ValueError,'manifest changed'): pr.status(other)

    def test_final_transcript_is_bound_to_master(self):
        for name in ('diagnose','prepare','edit','audio','enhance','master'): self.stage(name)
        data={'input_sha256':pr.digest(self.source),'artifacts':{}}
        with self.assertRaisesRegex(ValueError,'input does not match'): pr.record(self.job,'transcript',self.file('wrong.json',data))
        job=pr.load(self.job); source=job['stages']['master']['artifacts']['media']
        data={'input_sha256':source['sha256'],'artifacts':{'words':str(self.file('wrong-words.json',{'source_sha256':pr.digest(self.source)})),
              'report':str(self.file('transcript report.json'))}}
        with self.assertRaisesRegex(ValueError,'Final transcript'): pr.record(self.job,'transcript',self.file('wrong.json',data))

    def test_optional_stages_passthrough_and_actual_short_artifacts(self):
        self.stage('diagnose')
        data={'input_sha256':pr.digest(self.source),'status':'skipped','reason':'Already progressive SDR',
              'artifacts':{'media':str(self.source)}}
        pr.record(self.job,'prepare',self.file('skip.json',data))
        self.assertEqual(pr.status(self.job)['stages']['prepare'],'skipped')
        for name in ('edit','audio','enhance','master','transcript','package'): self.stage(name)
        source=pr.load(self.job)['stages']['master']['artifacts']['media']
        data={'input_sha256':source['sha256'],'artifacts':{'report':str(self.file('shorts report.json'))}}
        with self.assertRaisesRegex(ValueError,'each selected finished short'): pr.record(self.job,'shorts',self.file('shorts receipt.json',data))
        data.update(status='skipped',reason='User declined shorts',selected_count=0,decision_reference='simulated-user-choice')
        pr.record(self.job,'shorts',self.file('shorts receipt.json',data)); self.stage('review')
        self.assertEqual(pr.status(self.job)['stages']['review'],'completed')

    def test_final_approval_intent_unknown_reconcile_and_complete(self):
        self.all_stages(); release=pr.release(self.job,self.plan())
        with self.assertRaisesRegex(ValueError,'approval'): pr.intent(self.job,'episode-video')
        self.authorize(release['release_signature']); first=pr.intent(self.job,'episode-video')
        self.assertEqual(pr.status(self.job)['placements']['episode-video'],'submitting')
        with self.assertRaisesRegex(ValueError,'already attempted'): pr.intent(self.job,'episode-video')
        pr.receipt(self.job,'episode-video',self.result('unknown'))
        with self.assertRaisesRegex(ValueError,'reconcile'): pr.intent(self.job,'episode-video')
        pr.receipt(self.job,'episode-video',self.result('not-found'))
        retry=pr.intent(self.job,'episode-video'); self.assertEqual(first['operation_key'],retry['operation_key'])
        result=pr.receipt(self.job,'episode-video',self.result('scheduled')); self.assertTrue(result['verified'])
        with self.assertRaisesRegex(ValueError,'already attempted'): pr.intent(self.job,'episode-video')
        with self.assertRaisesRegex(ValueError,'Distribution started'): pr.release(self.job,self.plan(),replace=True)
        pr.receipt(self.job,'episode-video',self.result('not-found'))
        self.assertEqual(pr.status(self.job)['placements']['episode-video'],'needs-attention')

    def test_unexpected_account_schedule_and_remote_ids_are_retained(self):
        self.all_stages(); release=pr.release(self.job,self.plan()); self.authorize(release['release_signature'])
        pr.intent(self.job,'episode-video')
        result=pr.receipt(self.job,'episode-video',self.result('scheduled',account_id='wrong-channel'))
        self.assertEqual(result['status'],'needs-attention')
        entry=pr.load(self.job)['placements']['episode-video']
        self.assertEqual(entry['results'][0]['remote_id'],'remote-test-1')
        with self.assertRaisesRegex(ValueError,'already attempted'): pr.intent(self.job,'episode-video')
        result=pr.receipt(self.job,'episode-video',self.result('scheduled',publish_at=(datetime.now(timezone.utc)+timedelta(days=31)).isoformat()))
        self.assertFalse(result['verified'])
        self.assertTrue(pr.receipt(self.job,'episode-video',self.result('scheduled'))['verified'])

    def test_release_files_source_changes_and_schedule_guards(self):
        self.all_stages(); plan=self.plan(); data=pr.read(plan)
        data['placements'][0]['files']=[str(self.source)]; pr.write(plan,data)
        with self.assertRaisesRegex(ValueError,'recorded production artifacts'): pr.release(self.job,plan)
        plan=self.plan(); data=pr.read(plan); data['placements'][0]['publish_at']='2000-01-01T00:00:00Z'; pr.write(plan,data)
        with self.assertRaisesRegex(ValueError,'future release'): pr.release(self.job,plan)
        plan=self.plan(); data=pr.read(plan); data['placements'][0]['publish_at']='2030-01-01T00:00:00'; pr.write(plan,data)
        with self.assertRaisesRegex(ValueError,'UTC offset'): pr.release(self.job,plan)
        release=pr.release(self.job,self.plan()); self.authorize(release['release_signature'])
        media=pr.load(self.job)['stages']['package']['artifacts']['video']['path']; Path(media).write_bytes(b'changed delivery')
        self.assertFalse(pr.status(self.job)['release_current'])
        with self.assertRaisesRegex(ValueError,'stale'): pr.intent(self.job,'episode-video')

    def test_manual_mode_and_approval_signature_guards(self):
        self.config['distribution']['mode']='manual'; pr.write(self.configfile,self.config)
        with patch.object(pr,'doctor',return_value={}): pr.setup(self.project,self.configfile,update=True)
        self.job=self.base/'manual episode'; pr.init(self.source,self.job,self.project); self.all_stages()
        release=pr.release(self.job,self.plan(action='draft')); self.authorize(release['release_signature'])
        with self.assertRaisesRegex(ValueError,'Manual delivery'): pr.intent(self.job,'episode-video')
        wrong=self.file('approval wrong.json',{'release_signature':'wrong','kind':'user-message'})
        with self.assertRaisesRegex(ValueError,'exact release'): pr.approve(self.job,wrong)

    def test_interrupted_lock_and_unicode_cli(self):
        (self.job/'.running').write_text('123456')
        with self.assertRaisesRegex(ValueError,'verify PID'): self.stage('diagnose')
        self.assertTrue((self.job/'.running').exists()); (self.job/'.running').unlink()
        env={**os.environ,'PYTHONIOENCODING':'ascii'}
        r=subprocess.run([sys.executable,pr.__file__,'status','--job',str(self.job)],env=env,capture_output=True,text=True,encoding='ascii')
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(json.loads(r.stdout)['next'],['diagnose'])

    def test_configured_platform_routes_keep_independent_receipts(self):
        platforms=('youtube','tiktok','facebook','instagram','spreaker','libsyn')
        routes=('full-video','short','short','short','full-audio','full-audio')
        self.config['distribution']['destinations']=[{'id':p,'platform':p,'account_id':p+'-test','routes':[r]} for p,r in zip(platforms,routes)]
        pr.write(self.configfile,self.config)
        with patch.object(pr,'doctor',return_value={}): pr.setup(self.project,self.configfile,update=True)
        self.job=self.base/'multi-platform'; pr.init(self.source,self.job,self.project); self.all_stages()
        job=pr.load(self.job); package=job['stages']['package']['artifacts']; short=job['stages']['shorts']['artifacts']['short-01']
        at=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(); placements=[]
        for platform,route in zip(platforms,routes):
            media=package['video'] if route=='full-video' else package['audio'] if route=='full-audio' else short
            placements.append({'id':platform,'destination':platform,'route':route,'action':'schedule','visibility':'public',
                'files':[media['path'],package['metadata']['path']],
                'account_evidence':str(self.file(platform+'/account.json',{'simulated_account':platform+'-test'})),
                'publish_at':at,'timezone':'Etc/UTC'})
        release=pr.release(self.job,self.file('six destinations.json',{'placements':placements})); self.authorize(release['release_signature'])
        keys=[]
        for platform in platforms:
            keys.append(pr.intent(self.job,platform)['operation_key'])
            result=self.file(platform+'/result.json',{'status':'scheduled','platform':platform,'account_id':platform+'-test',
                'remote_id':platform+'-remote','url':'https://example.invalid/'+platform,'visibility':'public','publish_at':at,
                'readback':str(self.file(platform+'/readback.json',{'simulated_status':'scheduled'}))})
            self.assertTrue(pr.receipt(self.job,platform,result)['verified'])
        self.assertEqual(len(set(keys)),6); self.assertEqual(set(pr.status(self.job)['placements'].values()),{'scheduled'})
        (self.job/'youtube/readback.json').write_bytes(b'changed')
        self.assertEqual(pr.status(self.job)['placements']['youtube'],'evidence-changed')

    def test_passed_release_time_never_dispatches_publish_now(self):
        self.all_stages(); release=pr.release(self.job,self.plan()); self.authorize(release['release_signature'])
        class Later(datetime):
            @classmethod
            def now(cls,tz=None): return datetime.now(timezone.utc)+timedelta(days=31)
        with patch.object(pr,'datetime',Later):
            with self.assertRaisesRegex(ValueError,'Release time passed'): pr.intent(self.job,'episode-video')
        self.assertEqual(pr.status(self.job)['placements'],{})

    def test_append_newly_connected_destination_preserves_confirmed_release(self):
        self.all_stages(); first=pr.release(self.job,self.plan()); self.authorize(first['release_signature'])
        key=pr.intent(self.job,'episode-video')['operation_key']
        pr.receipt(self.job,'episode-video',self.result('scheduled'))
        original=copy.deepcopy(pr.load(self.job)['placements']['episode-video'])
        self.config['distribution']['destinations'][1]['account_id']='newly-connected-show'
        pr.write(self.configfile,self.config)
        with patch.object(pr,'doctor',return_value={}): pr.setup(self.project,self.configfile,update=True)
        job=pr.load(self.job); package=job['stages']['package']['artifacts']
        additional=self.file('additional placement.json',{'placements':[{'id':'episode-audio','destination':'podcast','route':'full-audio',
            'action':'schedule','visibility':'public','publish_at':self.publish_at,'timezone':'Etc/UTC',
            'files':[package['audio']['path'],package['metadata']['path']],
            'account_evidence':str(self.file('podcast account.json',{'simulated_show':'newly-connected-show'}))}]})
        revised=pr.release(self.job,additional,append=True,refresh_destinations=True)
        self.assertEqual(revised['added'],['episode-audio']); self.assertEqual(len(revised['placements']),2)
        self.assertEqual(pr.load(self.job)['placements']['episode-video'],original)
        self.assertFalse(pr.status(self.job)['publishing_permission_recorded'])
        with self.assertRaisesRegex(ValueError,'approval'): pr.intent(self.job,'episode-audio')
        self.authorize(revised['release_signature'])
        with self.assertRaisesRegex(ValueError,'already attempted'): pr.intent(self.job,'episode-video')
        second=pr.intent(self.job,'episode-audio')
        self.assertNotEqual(key,second['operation_key'])
        self.assertEqual(second['placement']['destination']['account_id'],'newly-connected-show')
        with self.assertRaisesRegex(ValueError,'Duplicate placement'): pr.release(self.job,additional,append=True)


if __name__=='__main__': unittest.main()
