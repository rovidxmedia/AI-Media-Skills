#!/usr/bin/env python3
"""Source-bound cue planning and local compositing of HyperFrames alpha renders.

HyperFrames owns authoring/rendering. This helper installs nothing and makes no network calls.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()


def signature(value): return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def run(args):
    result=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode: raise ValueError(result.stderr[-3000:] or 'Command failed')
    return result.stdout


def ffmpeg(args): return run(['ffmpeg','-hide_banner','-nostdin','-n','-threads','2',*args])


def probe(path): return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))


def video(info):
    return next((s for s in info['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)


def audio(info): return [s for s in info['streams'] if s['codec_type']=='audio']


def frames(path):
    data=json.loads(run(['ffprobe','-v','error','-threads','8','-select_streams','v:0','-count_frames',
                         '-show_entries','stream=nb_read_frames','-of','json',path]))
    return int(data['streams'][0]['nb_read_frames'])


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value): raise ValueError('Expected a finite number')
    return value


def text(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2000 or '\x00' in value:
        raise ValueError('Supply nonempty copy, purpose and evidence; at most 2000 characters per field')
    return value.strip()


def box(value):
    if not isinstance(value,list) or len(value)!=4: raise ValueError('Box must be normalized [x,y,width,height]')
    x,y,w,h=map(number,value)
    if min(x,y)<0 or min(w,h)<=0 or x+w>1+1e-9 or y+h>1+1e-9: raise ValueError('Box escapes its image/frame')
    return [x,y,w,h]


def overlaps(a,b):
    return a[0]<b[0]+b[2]-1e-9 and b[0]<a[0]+a[2]-1e-9 and a[1]<b[1]+b[3]-1e-9 and b[1]<a[1]+a[3]-1e-9


def source_ok(job):
    if digest(job['source']['path'])!=job['source']['sha256']: raise ValueError('Source changed; create a revised job')


def analyze(source,root):
    source,root=Path(source).resolve(),Path(root).resolve()
    info=probe(source); v=video(info)
    if not v: raise ValueError('A video source is required')
    if v.get('color_transfer') in ('smpte2084','arib-std-b67') or v.get('field_order') not in (None,'unknown','progressive'):
        raise ValueError('Prepare progressive SDR explicitly; do not silently convert HDR or interlacing')
    if v.get('color_primaries') not in (None,'unknown','unspecified','bt709'):
        raise ValueError('Prepare a reviewed Rec.709 SDR master before mixing browser graphics with other primaries')
    rotations=[v.get('tags',{}).get('rotate',0)]+[d.get('rotation',0) for d in v.get('side_data_list',[])]
    if any(float(r)%360 for r in rotations) or v.get('sample_aspect_ratio') not in (None,'1:1'):
        raise ValueError('Prepare unrotated square-pixel video before compositing')
    rate=Fraction(v['avg_frame_rate'])
    if rate<=0 or abs(float(rate-Fraction(v['r_frame_rate'])))>.001:
        raise ValueError('Confirm and prepare a constant frame rate before frame-grid cue planning')
    duration=float(info['format']['duration'])
    if not math.isfinite(duration) or duration<=0: raise ValueError('Invalid source duration')
    root.mkdir(parents=True,exist_ok=False)
    job={'schema':1,'source':{'path':str(source),'sha256':digest(source)},'media':info,
         'fps':str(rate),'duration':duration,'width':v['width'],'height':v['height']}
    write(root/'job.json',job)
    return job


def validate_cues(data,job,base):
    if data.get('source_sha256')!=job['source']['sha256']: raise ValueError('Cue sheet must bind to the exact input media')
    if not isinstance(data.get('cues'),list) or not data['cues']: raise ValueError('Supply selected cues')
    reserved=[{'label':text(r['label']),'box':box(r['box'])} for r in data.get('reserved_regions',[])]
    result=[]; ids=set(); warnings=[]; rate=Fraction(job['fps'])
    for raw in data['cues']:
        name=text(raw['id'])
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or name in ids: raise ValueError('Unique kebab-case cue IDs required')
        ids.add(name)
        kind=raw['kind']
        if kind not in ('lower-third','screenshot','key-phrase','steps','diagram','stat'): raise ValueError('Unknown cue kind')
        a,b=number(raw['start']),number(raw['end'])
        if not 0<=a<b<=job['duration']+1e-6: raise ValueError('Cue bounds must lie within the final source timeline')
        first,last=round(a*rate),round(b*rate)
        if last<=first: raise ValueError('Cue needs at least one output frame')
        placement=box(raw['box'])
        if any(overlaps(placement,r['box']) for r in reserved): raise ValueError('Cue covers a reserved face/caption/UI region')
        cue={'id':name,'kind':kind,'start':float(first/rate),'end':float(last/rate),'frames':last-first,
             'box':placement,'copy':text(raw['copy']),'purpose':text(raw['purpose']),
             'evidence':text(raw['evidence']),'allow_overlap':raw.get('allow_overlap',False)}
        if type(cue['allow_overlap']) is not bool: raise ValueError('allow_overlap must be a boolean')
        if kind=='screenshot':
            asset=(base/Path(raw['asset'])).resolve()
            if asset.suffix.lower() not in ('.png','.jpg','.jpeg','.webp') or not asset.is_file(): raise ValueError('Screenshot needs a local raster asset')
            cue.update(asset=str(asset),asset_sha256=digest(asset),asset_origin=text(raw['asset_origin']))
        highlights=[]
        for h in raw.get('highlights',[]):
            if kind!='screenshot': raise ValueError('Screenshot highlights require a screenshot cue')
            begin,end=number(h['start']),number(h['end'])
            if not 0<=begin<end<=(last-first)/float(rate)+1e-6: raise ValueError('Highlight times are local to the cue')
            highlights.append({'box':box(h['box']),'start':begin,'end':end,'text':text(h['text'])})
        cue['highlights']=highlights
        if cue['end']-cue['start']<len(cue['copy'].split())/3+.7:
            warnings.append(name+': short reading hold; inspect at actual playback speed')
        result.append(cue)
    for i,a in enumerate(result):
        for b in result[i+1:]:
            if a['start']<b['end'] and b['start']<a['end'] and overlaps(a['box'],b['box']) and not (a['allow_overlap'] and b['allow_overlap']):
                raise ValueError('Simultaneous graphics collide; separate timing/layout or explicitly review both overlaps')
    return {'source_sha256':job['source']['sha256'],'fps':job['fps'],'width':job['width'],'height':job['height'],
            'reserved_regions':reserved,'cues':result,'warnings':warnings}


def plan(root,cues):
    root=Path(root).resolve(); job=read(root/'job.json'); source_ok(job)
    if (root/'plan.json').exists(): raise ValueError('Plan exists; use a new child job for revised graphics')
    result=validate_cues(read(cues),job,Path(cues).resolve().parent)
    result['signature']=signature(result); write(root/'plan.json',result)
    return result


def load_plan(root):
    job=read(root/'job.json'); source_ok(job); data=read(root/'plan.json')
    if signature({k:v for k,v in data.items() if k!='signature'})!=data['signature']: raise ValueError('Plan changed; create a revised job')
    if data['source_sha256']!=job['source']['sha256']: raise ValueError('Plan source mismatch')
    for cue in data['cues']:
        if 'asset' in cue and digest(cue['asset'])!=cue['asset_sha256']: raise ValueError('Screenshot changed; revise and preview')
    return job,data


def overlay_ok(path,cue,job):
    v=video(probe(path))
    if not v or v.get('codec_name')!='prores' or not v.get('pix_fmt','').startswith('yuva'):
        raise ValueError('Use HyperFrames MOV/ProRes 4444 with alpha; an MP4 or black background is not transparency')
    if (v['width'],v['height'])!=(job['width'],job['height']) or abs(float(Fraction(v['avg_frame_rate'])-Fraction(job['fps'])))>.001:
        raise ValueError('Overlay canvas/frame rate differs from the cue plan')
    if frames(path)!=cue['frames']: raise ValueError('Overlay decoded frame count differs from the cue slot')
    result=subprocess.run(['ffmpeg','-v','error','-ss',str((cue['end']-cue['start'])/2),'-i',str(path),
        '-vf','alphaextract','-frames:v','1','-pix_fmt','gray','-f','rawvideo','-'],capture_output=True)
    if result.returncode or not result.stdout or min(result.stdout)==255 or max(result.stdout)==0:
        raise ValueError('Midpoint alpha must contain both visible graphics and transparent footage area')


def verify(output,job):
    info=probe(output); actual=video(info); original=video(job['media'])
    if not actual or any(actual[k]!=original[k] for k in ('width','height')): raise ValueError('Output geometry changed')
    if abs(float(Fraction(actual['avg_frame_rate'])-Fraction(job['fps'])))>.001: raise ValueError('Output frame rate changed')
    if abs(float(info['format']['duration'])-job['duration'])>.1: raise ValueError('Output duration drift')
    expected,received=frames(job['source']['path']),frames(output)
    if expected!=received: raise ValueError('Joined output lost or added decoded frames')
    before,after=audio(job['media']),audio(info)
    if len(before)!=len(after): raise ValueError('Audio tracks lost')
    origin=float(job['media']['format'].get('start_time',0)); target=float(info['format'].get('start_time',0))
    for a,b in zip(before,after):
        if any(a.get(k)!=b.get(k) for k in ('codec_name','channels','sample_rate')): raise ValueError('Audio format changed')
        for key in ('title','language'):
            before_tag,after_tag=a.get('tags',{}).get(key),b.get('tags',{}).get(key)
            if key=='language' and before_tag in (None,'und') and after_tag in (None,'und'): continue
            if before_tag!=after_tag: raise ValueError('Audio labels changed')
        if abs((float(a.get('start_time',origin))-origin)-(float(b.get('start_time',target))-target))>.05: raise ValueError('Audio synchronization changed')
    run(['ffmpeg','-v','error','-xerror','-threads','8','-i',output,'-map','0:v:0','-map','0:a?','-f','null','-'])
    source_ok(job)
    return {'passed':True,'decoded':True,'frames':received,'audio_tracks':len(after),'source_unchanged':True,
            'human_review':'Motion, copy accuracy, screenshot highlighting, faces, captions and lip sync still require review'}


def composite(root,manifest,output,accepted):
    root,output=Path(root).resolve(),Path(output).resolve(); job,data=load_plan(root)
    if accepted!=data['signature']: raise ValueError('Accept the current cue plan within the user-authorized production scope')
    if output.suffix.lower()!='.mkv' or output.exists(): raise ValueError('Choose a new MKV output; sources and prior exports are preserved')
    report=output.with_suffix('.report.json')
    if report.exists(): raise ValueError('Report already exists; choose a new output')
    inputs=read(manifest)
    if inputs.get('plan_signature')!=data['signature'] or inputs.get('source_sha256')!=job['source']['sha256']:
        raise ValueError('Overlay manifest must match this source and cue plan')
    version=text(inputs.get('hyperframes_version'))
    overlays=inputs['overlays']
    if set(overlays)!={c['id'] for c in data['cues']}: raise ValueError('Export every selected cue, with no unplanned overlays')
    base=Path(manifest).resolve().parent; args=['-copyts','-start_at_zero','-i',job['source']['path']]
    filters=[]; current='0:v:0'; receipts={}
    for i,cue in enumerate(data['cues'],1):
        path=(base/overlays[cue['id']]).resolve(); overlay_ok(path,cue,job)
        args+=['-i',path]
        filters.append(f"[{i}:v:0]setpts=PTS-STARTPTS+{cue['start']:.9f}/TB[o{i}]")
        filters.append(f"[{current}][o{i}]overlay=eof_action=pass:repeatlast=0:format=auto:enable='gte(t,{cue['start']:.9f})*lt(t,{cue['end']:.9f})'[v{i}]")
        current=f'v{i}'; receipts[cue['id']]={'path':str(path),'sha256':digest(path)}
    # Lossless picture master; preserve all audio streams independently of browser rendering.
    v=video(job['media'])
    raw_depth=str(v.get('bits_per_raw_sample',''))
    pixel_depth=re.search(r'p(\d+)(?:le|be)$',v.get('pix_fmt',''))
    depth=int(raw_depth) if raw_depth.isdigit() else (int(pixel_depth.group(1)) if pixel_depth else 8)
    high_depth=depth>8
    required=int(job['width']*job['height']*(6 if high_depth else 3)*float(Fraction(job['fps']))*job['duration'])+256*2**20
    if shutil.disk_usage(output.parent).free<required: raise ValueError('Insufficient storage for conservative lossless master budget')
    color=[]
    for key,flag in (('color_space','-colorspace'),('color_primaries','-color_primaries'),('color_transfer','-color_trc'),('color_range','-color_range')):
        if original_value:=video(job['media']).get(key):
            if original_value not in ('unknown','unspecified','reserved'): color += [flag,original_value]
    ffmpeg([*args,'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map',f'[{current}]','-map','0:a?',
            '-map_metadata','0','-map_chapters','-1','-c:v','ffv1','-level','3','-pix_fmt','yuv444p16le' if high_depth else 'yuv444p','-fps_mode','passthrough',
            *color,'-c:a','copy',output])
    result={'source_sha256':job['source']['sha256'],'plan_signature':data['signature'],'output':str(output),
            'hyperframes_version':version,'ffmpeg_version':run(['ffmpeg','-version']).splitlines()[0],
            'overlays':receipts,'verification':verify(output,job)}
    write(report,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('analyze'); a.add_argument('--input',required=True); a.add_argument('--job',required=True)
    a=sub.add_parser('plan'); a.add_argument('--job',required=True); a.add_argument('--cues',required=True)
    a=sub.add_parser('composite')
    for flag in ('job','overlays','output','accept-plan'): a.add_argument('--'+flag,required=True)
    args=p.parse_args()
    try:
        if args.command=='analyze': result=analyze(args.input,args.job)
        elif args.command=='plan': result=plan(args.job,args.cues)
        else: result=composite(args.job,args.overlays,args.output,args.accept_plan)
        print(json.dumps(result,ensure_ascii=True,indent=2))
    except (ValueError,OSError,KeyError,ZeroDivisionError) as e: raise SystemExit('Motion graphics: '+str(e))


if __name__=='__main__': main()
