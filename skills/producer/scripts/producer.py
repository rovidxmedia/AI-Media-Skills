#!/usr/bin/env python3
"""Project setup and resumable production/distribution receipts. Media work belongs to specialist skills."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time


SKILLS=('editor','video-enhance','podcast-audio-repair','that-radio-voice','podcast-packager','short-form-clips','video-motion-graphics')
DEPS={'diagnose':(), 'prepare':('diagnose',), 'edit':('prepare',), 'audio':('edit',),
      'enhance':('audio',), 'master':('enhance',), 'transcript':('master',),
      'package':('master','transcript'), 'shorts':('master','transcript'), 'review':('package','shorts')}
INPUT={'diagnose':None,'prepare':None,'edit':'prepare','audio':'edit','enhance':'audio',
       'master':'enhance','transcript':'master','package':'master','shorts':'master','review':'master'}
REQUIRED={'diagnose':{'report'},'prepare':{'media','report'},'edit':{'media','report','timeline'},
          'audio':{'media','report'},'enhance':{'media','report'},'master':{'media','report'},
          'transcript':{'words','report'},'package':{'video','audio','square','wide','metadata','report'},
          'shorts':{'report'},'review':{'report'},'graphics':{'media','report','cue-sheet','project'}}
OPTIONAL={'prepare','audio','enhance','shorts'}


def read(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict): raise ValueError('Expected JSON object: '+str(path))
    return data
def sig(data): return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def write(path,data):
    path=Path(path); tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8'); tmp.replace(path)
def text(value,label):
    if not isinstance(value,str) or not value.strip() or '\x00' in value: raise ValueError('Missing/invalid '+label)
    return value.strip()
def identifier(value):
    value=text(value,'ID')
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',value): raise ValueError('Use unique lowercase filename-safe IDs')
    return value
def artifact(path,base):
    p=Path(path); p=(base/p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_file() or not p.stat().st_size: raise ValueError('Missing/empty artifact: '+str(p))
    return {'path':str(p),'sha256':digest(p),'size':p.stat().st_size}
def unchanged(item,cache=None):
    cache={} if cache is None else cache
    p=Path(item['path'])
    if not p.is_file() or p.stat().st_size!=item['size']: return False
    if str(p) not in cache: cache[str(p)]=digest(p)
    return cache[str(p)]==item['sha256']


@contextmanager
def lock(root):
    marker=root/'.running'
    try:
        with marker.open('x') as f: f.write(str(os.getpid()))
    except FileExistsError: raise ValueError('Operation running/interrupted; verify PID stopped before removing .running')
    try: yield
    finally: marker.unlink(missing_ok=True)


def command(args):
    try:
        r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8)
        return r.stdout.strip() if r.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): return None


def doctor(project,roots=()):
    roots=[Path(r).resolve() for r in roots] or [Path(__file__).resolve().parents[2]]
    found={name:next((str(r/name/'SKILL.md') for r in roots if (r/name/'SKILL.md').is_file()),None) for name in SKILLS}
    tools={name:shutil.which(name) for name in ('ffmpeg','ffprobe')}
    versions={name:(command([path,'-version']) or '').splitlines()[:1] if path else [] for name,path in tools.items()}
    ram=None
    try:
        if os.name=='nt':
            import ctypes
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
                    ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
            m=Memory(); m.length=ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): ram=m.total
        elif platform.system()=='Darwin': ram=int(command(['sysctl','-n','hw.memsize']) or 0) or None
        else: ram=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    except (OSError,ValueError,AttributeError): pass
    nvidia=shutil.which('nvidia-smi')
    gpu=command([nvidia,'--query-gpu=name,memory.total','--format=csv,noheader']) if nvidia else None
    if not gpu and os.name=='nt':
        gpu=command(['powershell','-NoProfile','-NonInteractive','-Command',
            'Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress'])
    if not gpu and platform.system()=='Darwin': gpu=command(['system_profiler','SPDisplaysDataType','-json'])
    project=Path(project).resolve(); existing=project
    while not existing.exists(): existing=existing.parent
    return {'schema':1,'checked_at':time.time(),'system':platform.system(),'release':platform.release(),
            'python':platform.python_version(),'cpu':platform.processor() or None,'logical_cpus':os.cpu_count(),
            'ram_bytes':ram,'free_storage_bytes':shutil.disk_usage(existing).free,
            'gpu_inventory':gpu,'gpu_inference_tested':False,'tools':tools,'versions':versions,'skills':found,
            'core_available':bool(tools['ffmpeg'] and tools['ffprobe'] and found['editor'] and found['podcast-packager']),
            'note':'Inventory is not an AI benchmark or proof of publisher authentication; no tools/models installed.'}


def project_config(data):
    if data.get('schema',1)!=1: raise ValueError('Unsupported project schema')
    show=data.get('show',{})
    if not isinstance(show,dict): raise ValueError('Show settings must be an object')
    show={**show,**{k:text(show.get(k), 'show '+k) for k in ('name','description','language')}}
    if show.get('format') not in ('podcast','youtube','both'): raise ValueError('Choose show format: podcast, youtube or both')
    if not isinstance(show.get('hosts'),list): raise ValueError('Supply hosts list; [] is allowed for deliberately anonymous shows')
    show['hosts']=[text(v,'host') for v in show['hosts']]
    defaults={'editor':{'style':'natural','captions':'off'},'video-enhance':{'enabled':'if-needed','style':'natural','resolution':'source','fps':'source'},
              'podcast-audio-repair':{'enabled':'if-needed'},'that-radio-voice':{'enabled':False},
              'podcast-packager':{},'short-form-clips':{'count':3,'width':1080,'height':1920,'captions':'burn','framing':'content-aware'},
              'video-motion-graphics':{'enabled':False,'style':'restrained'}}
    overrides=data.get('skills',{})
    if not isinstance(overrides,dict) or set(overrides)-set(SKILLS): raise ValueError('Unknown skill preferences')
    for k,v in overrides.items():
        if not isinstance(v,dict): raise ValueError('Skill preferences must be objects')
        defaults[k].update(v)
    if defaults['editor']['style'] not in ('natural','tight','custom'): raise ValueError('Unknown editing style')
    graphics=defaults['video-motion-graphics']
    if type(graphics['enabled']) is not bool: raise ValueError('Motion graphics enabled must be true or false')
    if graphics['style'] not in ('restrained','explainer','custom'): raise ValueError('Unknown motion graphics style')
    count=defaults['short-form-clips']['count']
    if isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=20: raise ValueError('Short count must be 0 through 20')
    distribution=data.get('distribution',{})
    if not isinstance(distribution,dict) or not isinstance(data.get('brand',{}),dict) or not isinstance(data.get('paths',{}),dict):
        raise ValueError('Distribution, brand and paths must be objects')
    if distribution.get('mode','review') not in ('review','manual'): raise ValueError('Publishing mode must be review or manual')
    destinations=distribution.get('destinations',[])
    if not isinstance(destinations,list): raise ValueError('Destinations must be a list')
    ids=set(); targets=[]
    for d in destinations:
        name=identifier(d['id'])
        if name in ids: raise ValueError('Duplicate destination ID')
        ids.add(name)
        routes=d.get('routes',[])
        if not isinstance(routes,list) or not routes or set(routes)-{'full-video','full-audio','short'}: raise ValueError('Choose destination content routes')
        account=d.get('account_id')
        if account is not None: account=text(account,'account ID')
        targets.append({'id':name,'platform':text(d['platform'],'platform'),'account_id':account,
                        'label':text(d.get('label',name),'destination label'),'routes':routes})
    paths={'output':'production',**data.get('paths',{})}; text(paths['output'],'output path')
    result={'schema':1,'show':show,'brand':data.get('brand',{}),'paths':paths,
            'skills':defaults,'distribution':{**distribution,'mode':distribution.get('mode','review'),'destinations':targets}}
    # Credentials belong to the host credential manager, never a shared profile.
    def secrets(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if re.search(r'password|access_token|refresh_token|api_key|client_secret|authorization',k,re.I):
                    raise ValueError('Keep credentials out of Producer configuration')
                secrets(v)
        elif isinstance(value,list):
            for v in value: secrets(v)
    secrets(result); return result


def setup(project,config,update=False,roots=()):
    project=Path(project).resolve(); folder=project/'.producer'; path=folder/'project.json'
    profile=project_config(read(config)); folder.mkdir(parents=True,exist_ok=True)
    # This directory contains private identities, machine paths, plans and receipts.
    ignore=folder/'.gitignore'
    if not ignore.exists(): ignore.write_text('*\n!.gitignore\n',encoding='utf-8')
    with lock(folder):
        if path.exists() and not update: raise ValueError('Project already configured; resume or use setup --update deliberately')
        if path.exists():
            history=folder/'config-history'; history.mkdir(exist_ok=True)
            backup=history/(str(time.time_ns())+'-'+digest(path)[:12]+'.json'); shutil.copyfile(path,backup)
        write(path,profile)
        machines=folder/'machines'; machines.mkdir(exist_ok=True)
        machine=hashlib.sha256(platform.node().encode()).hexdigest()[:12]
        report=doctor(project,roots); write(machines/(machine+'.json'),report)
    return {'config':str(path),'machine_report':str(machines/(machine+'.json')),'doctor':report,
            'next':'Resolve missing skills/tools; analyze footage and present a coordinated treatment. Setup does not grant publishing permission.'}


def init(source,root,project,overrides=None):
    root=Path(root).resolve(); project=Path(project).resolve()
    if root.is_relative_to(Path(__file__).resolve().parents[2]): raise ValueError('Keep production jobs outside installed/repository skills')
    profile=project_config(read(project/'.producer/project.json'))
    if overrides:
        patch=read(overrides)
        if set(patch)-{'skills'}: raise ValueError('Per-run overrides support skill preferences; update the project for show/destination changes')
        for k,v in patch.get('skills',{}).items():
            if k not in SKILLS or not isinstance(v,dict): raise ValueError('Unknown skill override')
            profile['skills'][k].update(v)
        profile=project_config(profile)
    item=artifact(source,Path.cwd()); root.mkdir(parents=True,exist_ok=False)
    job={'schema':1,'project':str(project),'profile':profile,'source':item,'created_at':time.time(),
         'stages':{},'release':None,'approval':None,'placements':{}}
    save(root,job); return status(root)


def save(root,job):
    body={k:v for k,v in job.items() if k!='integrity'}; body['integrity']=sig(body); write(root/'production.json',body)
def load(root):
    job=read(root/'production.json'); integrity=job.pop('integrity',None)
    if sig(job)!=integrity: raise ValueError('Production manifest changed outside the helper')
    if not unchanged(job['source']): raise ValueError('Original source changed; preserve evidence and resolve before resuming')
    return job


def stage_graph(job):
    # Existing manifests without this preference retain their original graph and receipts.
    enabled=job['profile']['skills'].get('video-motion-graphics',{}).get('enabled',False)
    graph={}
    for name,deps in DEPS.items():
        if name=='master' and enabled:
            graph['graphics']=('enhance',)
            deps=('graphics',)
        graph[name]=deps
    return graph


def stage_input(job,stage):
    return 'graphics' if stage=='master' and 'graphics' in stage_graph(job) else ('enhance' if stage=='graphics' else INPUT[stage])


def graphics_preferences(root,settings,decision):
    with lock(root):
        job=load(root)
        if job['placements']: raise ValueError('Distribution already started; reconcile releases before revising production')
        patch=read(settings)
        if not isinstance(patch,dict) or set(patch)-{'enabled','style'}: raise ValueError('Supply only graphics enabled/style preferences')
        previous=job['profile']['skills'].get('video-motion-graphics',{'enabled':False,'style':'restrained'})
        profile=project_config(job['profile'])
        profile['skills']['video-motion-graphics'].update(patch); profile=project_config(profile)
        chosen=profile['skills']['video-motion-graphics']
        if chosen==previous: return status(root)
        job.setdefault('graphics_revisions',[]).append({'previous':previous,'selected':chosen,
            'decision_reference':text(decision,'user decision reference'),'previous_receipt':job['stages'].pop('graphics',None)})
        job['profile']=profile; job['approval']=None; save(root,job)
    return status(root)


def stages(job):
    states={}; hashes={}; cache={}
    for stage,deps in stage_graph(job).items():
        r=job['stages'].get(stage)
        parents=all(states[d] in ('completed','skipped') for d in deps)
        if not r: states[stage]='ready' if parents else 'pending'; continue
        if not parents or r['dependencies']!={d:hashes[d] for d in deps}:
            states[stage]='stale'; continue
        if any(not unchanged(a,cache) for a in r['artifacts'].values()): states[stage]='changed'; continue
        states[stage]=r['status']; hashes[stage]=sig(r)
    return states,hashes


def record(root,stage,receipt,replace=False):
    with lock(root):
        job=load(root); states,hashes=stages(job); data=read(receipt)
        graph=stage_graph(job)
        if stage not in graph: raise ValueError('Motion graphics must be requested in the saved episode preferences before this stage')
        if stage in job['stages'] and not replace: raise ValueError('Stage exists; use --replace for an intentional revised result')
        if any(states[d] not in ('completed','skipped') for d in graph[stage]): raise ValueError('Complete valid prerequisite stages first')
        parent=stage_input(job,stage); source=job['source'] if parent is None else job['stages'][parent]['artifacts']['media']
        if data.get('input_sha256')!=source['sha256']: raise ValueError('Receipt input does not match the current stage media')
        state=data.get('status','completed'); reason=data.get('reason','')
        if state not in ('completed','skipped'): raise ValueError('Stage result must be completed or skipped')
        if state=='skipped' and (stage not in OPTIONAL or not reason): raise ValueError('Only optional stages can be skipped with a reason')
        if state=='skipped': reason=text(reason,'skip reason')
        if stage=='shorts' and state=='skipped' and job['profile']['skills']['short-form-clips']['count']!=0 and not (
            data.get('selected_count')==0 and data.get('decision_reference')):
            raise ValueError('Shorts are requested in the profile; record results or explicitly revise the project/run')
        if not isinstance(data.get('artifacts',{}),dict): raise ValueError('Artifacts must be an object of named paths')
        artifacts={identifier(k):artifact(v,root) for k,v in data.get('artifacts',{}).items()}
        required=({'media'} if stage in ('prepare','audio','enhance') else set()) if state=='skipped' else REQUIRED[stage]
        if not required<=artifacts.keys(): raise ValueError('Missing required artifacts: '+', '.join(sorted(required-artifacts.keys())))
        if state=='skipped' and 'media' in artifacts and artifacts['media']['sha256']!=source['sha256']:
            raise ValueError('Skipped media stage must pass through its exact input')
        if stage=='transcript' and read(artifacts['words']['path']).get('source_sha256')!=source['sha256']:
            raise ValueError('Final transcript must be bound to the final master, not the raw recording')
        if stage=='shorts' and state=='completed':
            count=data.get('selected_count',job['profile']['skills']['short-form-clips']['count'])
            if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=20: raise ValueError('Record the selected short count')
            if count!=job['profile']['skills']['short-form-clips']['count'] and not data.get('decision_reference'):
                raise ValueError('Reference the user choice when changing the configured short count')
            if sum(Path(a['path']).suffix.lower()=='.mp4' for a in artifacts.values())<count:
                raise ValueError('Record each selected finished short, not just a report')
        job['stages'][stage]={'status':state,'reason':reason,'input_sha256':source['sha256'],
            'dependencies':{d:hashes[d] for d in graph[stage]},'artifacts':artifacts,'recorded_at':time.time()}
        if stage=='shorts':
            job['stages'][stage].update(selected_count=data.get('selected_count',job['profile']['skills']['short-form-clips']['count']),
                                        decision_reference=data.get('decision_reference'))
        job['approval']=None; save(root,job)
    return status(root)


def utc(value):
    d=datetime.fromisoformat(text(value,'release timestamp').replace('Z','+00:00'))
    if d.tzinfo is None or d.utcoffset() is None: raise ValueError('Release timestamp needs an explicit UTC offset')
    return d.astimezone(timezone.utc).isoformat()


def release(root,plan,replace=False,append=False,refresh_destinations=False):
    with lock(root):
        job=load(root); states,hashes=stages(job)
        if states['review']!='completed': raise ValueError('Finish current production and quality review before preparing release')
        if replace and append: raise ValueError('Choose replace or append, not both')
        if job['placements'] and not append: raise ValueError('Distribution started; reconcile existing remote IDs instead of creating a new release')
        if append and not job['release']: raise ValueError('Prepare the initial release before appending placements')
        if job['release'] and not (replace or append): raise ValueError('Release exists; use --replace for a revised review')
        if append and job['release']['stages']!=hashes: raise ValueError('Cannot append to stale production; reconcile existing publications first')
        if refresh_destinations:
            job['profile']['distribution']=project_config(read(Path(job['project'])/'.producer/project.json'))['distribution']
        available={a['path']:a for s in ('package','shorts') for a in job['stages'][s]['artifacts'].values()}
        targets={d['id']:d for d in job['profile']['distribution']['destinations']}
        placements=list(job['release']['placements']) if append else []
        ids={p['id'] for p in placements}; added=[]
        for p in read(plan).get('placements',[]):
            pid=identifier(p['id']); target=targets.get(p['destination'])
            if pid in ids: raise ValueError('Duplicate placement ID')
            ids.add(pid)
            added.append(pid)
            if not target or not target.get('account_id'): raise ValueError('Configure the exact publishing account/show before release')
            if p['route'] not in target['routes']: raise ValueError('Content route does not belong to this destination')
            action=p['action']
            if action not in ('draft','schedule','publish'): raise ValueError('Unknown publishing action')
            files=[artifact(v,root) for v in p['files']]
            if not files or any(available.get(a['path'])!=a for a in files): raise ValueError('Release files must be current recorded production artifacts')
            main={'full-video':'video','full-audio':'audio'}.get(p['route'])
            if main and job['stages']['package']['artifacts'][main] not in files: raise ValueError('Include the packaged media for this content route')
            if p['route']=='short' and not any(a in job['stages']['shorts']['artifacts'].values() and Path(a['path']).suffix.lower()=='.mp4' for a in files):
                raise ValueError('Include a finished short for a short placement')
            item={'id':pid,'destination':target,'route':p['route'],'action':action,'files':files,
                  'visibility':text(p['visibility'],'visibility'),'account_evidence':artifact(p['account_evidence'],root)}
            if action=='schedule':
                item.update(publish_at=utc(p['publish_at']),timezone=text(p['timezone'],'timezone'))
                if datetime.fromisoformat(item['publish_at'])<=datetime.now(timezone.utc): raise ValueError('Choose a future release; never substitute publish-now')
            placements.append(item)
        if not added: raise ValueError('Choose at least one new concrete placement')
        body={'stages':hashes,'placements':placements}; body['signature']=sig(body)
        job['release']=body; job['approval']=None; save(root,job)
    return {'release_signature':body['signature'],'placements':placements,'added':added,
            'next':'Review new/revised placements; retained remote IDs must not be uploaded again.'}


def current_release(job):
    r=job['release']; states,hashes=stages(job)
    if not r or states['review']!='completed' or r['stages']!=hashes: raise ValueError('Release is missing/stale; review current outputs')
    if sig({k:v for k,v in r.items() if k!='signature'})!=r['signature']: raise ValueError('Release changed')
    for p in r['placements']:
        if not unchanged(p['account_evidence']): raise ValueError('Account evidence changed; prepare a revised release')
    return r


def approve(root,evidence):
    with lock(root):
        job=load(root); r=current_release(job); data=read(evidence)
        if data.get('release_signature')!=r['signature']: raise ValueError('Approval must match the exact release signature')
        if data.get('kind') not in ('user-message','standing-instruction'): raise ValueError('Record trusted user authorization provenance')
        job['approval']={'release_signature':r['signature'],'kind':data['kind'],'reference':text(data.get('reference'),'authorization reference'),
                         'quote':text(data.get('quote'),'authorization quote'),'recorded_at':time.time()}
        save(root,job)
    return {'recorded':True,'note':'This receipt logs authority the agent verified; imported JSON cannot supply consent.'}


def intent(root,placement):
    with lock(root):
        job=load(root); r=current_release(job); a=job['approval']
        if job['profile']['distribution']['mode']=='manual': raise ValueError('Manual delivery mode does not dispatch publishing operations')
        if not a or a['release_signature']!=r['signature']: raise ValueError('Final release approval is required')
        p=next((p for p in r['placements'] if p['id']==placement),None)
        if not p: raise ValueError('Unknown placement')
        old=job['placements'].get(placement)
        if old and old['status']!='not-found': raise ValueError('Placement already attempted; reconcile remote state before retrying')
        if p['action']=='schedule' and datetime.fromisoformat(p['publish_at'])<=datetime.now(timezone.utc):
            raise ValueError('Release time passed; revise schedule with the user, never publish immediately')
        key=old['operation_key'] if old else sig({'release':r['signature'],'placement':placement})
        job['placements'][placement]={'status':'submitting','operation_key':key,'attempts':(old['attempts'] if old else 0)+1,
            'results':old.get('results',[]) if old else [],'started_at':time.time()}
        save(root,job)
    return {'operation_key':key,'placement':p,'next':'Use a supported connector/CLI/browser; this helper made no upload. On uncertainty, query the destination before retrying.'}


def receipt(root,placement,result):
    with lock(root):
        job=load(root); r=job['release']; entry=job['placements'].get(placement)
        if not r or not entry: raise ValueError('Record intent before a publishing result')
        p=next(p for p in r['placements'] if p['id']==placement); data=read(result)
        state=data['status']
        if state not in ('draft','scheduled','published','unknown','not-found'): raise ValueError('Unknown publishing result')
        proof=artifact(data['readback'],root)
        actual={'status':state,'platform':text(data['platform'],'actual platform'),'account_id':text(data['account_id'],'actual account'),
                'readback':proof,'checked_at':time.time()}
        expected={'draft':'draft','schedule':'scheduled','publish':'published'}[p['action']]
        matches=actual['platform']==p['destination']['platform'] and actual['account_id']==p['destination']['account_id']
        if state in ('draft','scheduled','published'):
            actual.update(remote_id=text(data.get('remote_id'),'remote ID'),url=text(data.get('url'),'remote URL'),
                          visibility=text(data.get('visibility'),'actual visibility'))
            matches=matches and actual['visibility']==p['visibility'] and state==expected
        if state=='scheduled':
            actual['publish_at']=utc(data['publish_at']); matches=matches and actual['publish_at']==p.get('publish_at')
        # Save unexpected remote identities/IDs too, so a mismatch never causes a blind duplicate upload.
        already_confirmed=any(v['status'] in ('draft','scheduled','published') for v in entry['results'])
        entry['status']=state if matches and not (already_confirmed and state=='not-found') else 'needs-attention'
        entry['results'].append(actual); save(root,job)
    return {'placement':placement,'status':entry['status'],'verified':entry['status']==expected}


def status(root):
    job=load(root); states,_=stages(job)
    try: current_release(job); release_current=True
    except ValueError: release_current=False
    graph=stage_graph(job)
    return {'job':str(root),'stages':states,'next':[s for s in graph if states[s] in ('ready','stale','changed') and
        all(states[d] in ('completed','skipped') for d in graph[s])],
        'placements':{k:(v['status'] if all(unchanged(r['readback']) for r in v['results']) else 'evidence-changed') for k,v in job['placements'].items()},
        'release_signature':job['release']['signature'] if job['release'] else None,
        'release_current':release_current,
        'publishing_permission_recorded':bool(job['approval']),
        'note':'Resume the first incomplete/stale specialist stage; reconcile submitting/unknown placements. This helper runs no media or upload engine.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    for name in ('doctor','setup'):
        a=sub.add_parser(name); a.add_argument('--project',required=True); a.add_argument('--skills-root',action='append',default=[])
        if name=='setup': a.add_argument('--config',required=True); a.add_argument('--update',action='store_true')
    a=sub.add_parser('init'); a.add_argument('--project',required=True); a.add_argument('--input',required=True); a.add_argument('--job',required=True)
    a.add_argument('--overrides')
    sub.add_parser('status').add_argument('--job',required=True)
    a=sub.add_parser('record'); a.add_argument('--job',required=True); a.add_argument('--stage',choices=(*DEPS,'graphics'),required=True)
    a.add_argument('--receipt',required=True); a.add_argument('--replace',action='store_true')
    a=sub.add_parser('graphics-preferences'); a.add_argument('--job',required=True); a.add_argument('--settings',required=True)
    a.add_argument('--decision-reference',required=True)
    a=sub.add_parser('release'); a.add_argument('--job',required=True); a.add_argument('--plan',required=True); a.add_argument('--replace',action='store_true')
    a.add_argument('--append',action='store_true'); a.add_argument('--refresh-destinations',action='store_true')
    a=sub.add_parser('approve'); a.add_argument('--job',required=True); a.add_argument('--evidence',required=True)
    for name in ('intent','receipt'):
        a=sub.add_parser(name); a.add_argument('--job',required=True); a.add_argument('--placement',required=True)
        if name=='receipt': a.add_argument('--result',required=True)
    args=p.parse_args()
    try:
        if args.command=='doctor': out=doctor(args.project,args.skills_root)
        elif args.command=='graphics-preferences': out=graphics_preferences(Path(args.job).resolve(),args.settings,args.decision_reference)
        elif args.command=='setup': out=setup(args.project,args.config,args.update,args.skills_root)
        elif args.command=='init': out=init(args.input,args.job,args.project,args.overrides)
        else:
            root=Path(args.job).resolve()
            if args.command=='status': out=status(root)
            elif args.command=='record': out=record(root,args.stage,args.receipt,args.replace)
            elif args.command=='release': out=release(root,args.plan,args.replace,args.append,args.refresh_destinations)
            elif args.command=='approve': out=approve(root,args.evidence)
            elif args.command=='intent': out=intent(root,args.placement)
            else: out=receipt(root,args.placement,args.result)
        print(json.dumps(out,indent=2,ensure_ascii=True,allow_nan=False))
    except (OSError,ValueError,KeyError,TypeError) as exc: raise SystemExit('Producer: '+str(exc))


if __name__=='__main__': main()
