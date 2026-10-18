#!/usr/bin/env python3
"""Render reviewed, source-bound short-form moments locally. Semantic selection belongs to the agent."""
import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()


def signature(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def write(path,data):
    path=Path(path); temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def run(args,cwd=None):
    args=list(map(str,args))
    result=subprocess.run(args,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if cwd:
        with (Path(cwd)/'processing.log').open('a',encoding='utf-8') as f:
            f.write(json.dumps(args,ensure_ascii=False)+'\n'+result.stderr[-6000:]+'\n')
    if result.returncode: raise ValueError(result.stderr[-3000:] or 'Command failed')
    return result.stdout


def ffmpeg(args,**kwargs):
    return run(['ffmpeg','-hide_banner','-nostdin','-v','error','-n','-threads','2',*args],**kwargs)


def probe(path): return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))
def video(media): return next((s for s in media['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)
def audio(media): return [s for s in media['streams'] if s['codec_type']=='audio']


def number(value):
    if isinstance(value,bool): raise ValueError('Boolean is not a time/score')
    value=float(value)
    if not math.isfinite(value): raise ValueError('Numbers must be finite')
    return value


def text(value,label):
    if not isinstance(value,str) or not value.strip() or '\x00' in value: raise ValueError('Missing/invalid '+label)
    return value.strip()


def doctor():
    tools={k:shutil.which(k) for k in ('ffmpeg','ffprobe')}
    filters=run(['ffmpeg','-hide_banner','-filters']) if tools['ffmpeg'] else ''
    return {'tools':tools,'ready':all(tools.values()),'burn_captions':' subtitles ' in filters,
            'dependencies':'Python 3.10+, FFmpeg/ffprobe; libass subtitles for burned captions',
            'transcription':'Import source-bound word JSON, or use optional sibling Editor local transcription workflow.'}


def check_source(job):
    source=Path(job['source']['path'])
    if not source.is_file() or source.stat().st_size!=job['source']['size'] or digest(source)!=job['source']['sha256']:
        raise ValueError('Source changed; analyze a new job')


@contextmanager
def lock(root):
    marker=root/'.running'
    try:
        with marker.open('x') as f: f.write(str(os.getpid()))
    except FileExistsError: raise ValueError('Job running/interrupted; verify the process stopped before removing .running')
    try: yield
    finally: marker.unlink(missing_ok=True)


def analyze(args):
    source=Path(args.input).resolve(); root=Path(args.job).resolve()
    media=probe(source); v=video(media)
    if not v or not audio(media): raise ValueError('Shorts require picture and a complete dialogue mix')
    if v.get('color_transfer') in ('smpte2084','arib-std-b67') or v.get('field_order') not in (None,'unknown','progressive'):
        raise ValueError('Prepare HDR/interlaced media explicitly before SDR short-form export')
    duration=number(media['format']['duration'])
    fps=Fraction(v.get('avg_frame_rate') or v.get('r_frame_rate','0/1'))
    if not 0<float(fps)<=120 or duration<=0: raise ValueError('Unusable duration/frame rate')
    if not 0<=args.audio_track<len(audio(media)): raise ValueError('Choose an existing audio-track index')
    if audio(media)[args.audio_track].get('channels') not in (1,2): raise ValueError('Prepare a mono/stereo dialogue mix explicitly')
    if args.width%2 or args.height%2 or not 90<=args.width<=2160 or not 160<=args.height<=3840 or abs(args.width/args.height-9/16)>.001:
        raise ValueError('Use even 9:16 output dimensions, default 1080x1920')
    job={'schema':1,'source':{'path':str(source),'sha256':digest(source),'size':source.stat().st_size},
         'media':media,'duration':duration,'fps':str(fps),'audio_track':args.audio_track,
         'width':args.width,'height':args.height}
    root.mkdir(parents=True,exist_ok=False); write(root/'job.json',job)
    return {'job':str(root),'duration':duration,'fps':str(fps),'audio_tracks':len(audio(media)),
            'selected_audio_track':args.audio_track,'next':'Obtain word timestamps matching this exact source, then rank candidates semantically.'}


def transcript(data,job):
    if data.get('source_sha256')!=job['source']['sha256']: raise ValueError('Transcript does not match this source')
    coverage=data.get('coverage',[])
    if len(coverage)!=2 or number(coverage[0])<0 or number(coverage[1])>job['duration']+.1 or number(coverage[1])<=number(coverage[0]):
        raise ValueError('Invalid transcript coverage')
    words=[]; last=number(coverage[0])
    for word in data.get('words',[]):
        start,end=number(word['start']),number(word['end'])
        if start<last-.00001 or end<=start or end>number(coverage[1])+.001: raise ValueError('Words must be ordered, nonoverlapping and inside coverage')
        words.append({'word':text(word['word'],'word'),'start':start,'end':end}); last=end
    if not words: raise ValueError('Word-level transcript is required')
    return {'source_sha256':data['source_sha256'],'coverage':list(map(number,coverage)),'words':words}


def candidates(data,words,job):
    if data.get('source_sha256')!=job['source']['sha256']: raise ValueError('Candidates do not match this source')
    clips=[]; ids=set()
    for c in data.get('clips',[]):
        cid=text(c.get('id'),'clip id')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',cid) or cid in ids: raise ValueError('Clip IDs must be unique safe lowercase names')
        ids.add(cid); start,end=number(c['start']),number(c['end'])
        if not 0<=start<end<=job['duration'] or end-start>180: raise ValueError('Clip bounds must be within source and at most 180 seconds')
        if start<words['coverage'][0] or end>words['coverage'][1]+.001: raise ValueError('Transcript must cover each complete clip')
        selected=c.get('selected',False)
        if not isinstance(selected,bool): raise ValueError('selected must be boolean')
        out={k:text(c.get(k),k) for k in ('title','hook','why','payoff','description')}
        out.update(id=cid,start=start,end=end,selected=selected)
        hook=c['hook_evidence']; hs,he=number(hook['start']),number(hook['end'])
        if not start<=hs<he<=min(end,start+3.5): raise ValueError('Spoken hook evidence must begin within the opening 3.5 seconds')
        actual=' '.join(w['word'] for w in words['words'] if w['start']>=hs-.02 and w['end']<=he+.02)
        if not actual or actual!=text(hook['text'],'hook evidence'): raise ValueError('Hook evidence must quote matching timed words exactly')
        if out['hook']!=actual: raise ValueError('hook must equal the quoted spoken evidence')
        out['hook_evidence']={'start':hs,'end':he,'text':actual}
        out['scores']={k:number(c['scores'][k]) for k in ('hook','standalone','payoff','audience')}
        if any(not 0<=v<=5 for v in out['scores'].values()): raise ValueError('Scores must be 0 through 5')
        framing=c.get('framing',{}); mode=framing.get('mode','fit')
        if mode not in ('crop','fit','stacked'): raise ValueError('Framing mode must be crop, fit or stacked')
        x,y=number(framing.get('center_x',.5)),number(framing.get('center_y',.5))
        if not 0<=x<=1 or not 0<=y<=1: raise ValueError('Crop centers must be normalized 0 through 1')
        out['framing']={'mode':mode,'center_x':x,'center_y':y}
        if mode=='stacked': out['framing']=stacked_framing(framing,start,end,job)
        out['captions']=c.get('captions','burn')
        if out['captions'] not in ('burn','srt','off'): raise ValueError('Unknown caption mode')
        if not isinstance(c.get('tags'),list): raise ValueError('tags must be a list')
        out['tags']=[text(t,'tag') for t in c['tags']]
        out['cover_at']=number(c.get('cover_at',start+(end-start)/2))
        if not start<=out['cover_at']<end: raise ValueError('Cover frame must be inside clip')
        clips.append(out)
    if not clips or not any(c['selected'] for c in clips): raise ValueError('Select at least one reviewed candidate')
    return clips


def plan(args):
    root=Path(args.job).resolve(); job=read(root/'job.json')
    with lock(root):
        check_source(job)
        if (root/'preview.json').exists(): raise ValueError('Preview exists; use a new job for revised selections')
        words=transcript(read(args.transcript),job)
        content={'job_signature':signature(job),'transcript':words,'clips':candidates(read(args.candidates),words,job)}
        content['signature']=signature(content); write(root/'plan.json',content)
        rows=''.join('<tr><td>'+html.escape(c['id'])+'</td><td>'+str(c['start'])+'–'+str(c['end'])+
            '</td><td>'+html.escape(c['title'])+'</td><td>'+html.escape(c['hook'])+'</td><td>'+html.escape(c['why'])+
            '</td><td>'+html.escape(c['payoff'])+'</td><td>'+html.escape(str(c['framing']))+'</td></tr>' for c in content['clips'])
        (root/'review-plan.html').write_text('<!doctype html><meta charset="utf-8"><title>Shorts plan</title><h1>Candidate review</h1>'
            '<p>Scores are agent editorial judgments, not predictions of views. Check full context and framing before selecting.</p>'
            '<table border="1"><tr><th>ID</th><th>Source time</th><th>Title</th><th>Spoken hook</th><th>Why</th><th>Payoff</th><th>Framing</th></tr>'+rows+'</table>',encoding='utf-8')
        return {'plan_signature':content['signature'],'review':str(root/'review-plan.html'),
                'selected':[c['id'] for c in content['clips'] if c['selected']]}


def load_plan(root):
    job=read(root/'job.json'); check_source(job); data=read(root/'plan.json')
    sig=data.pop('signature')
    if signature(data)!=sig or data['job_signature']!=signature(job): raise ValueError('Plan/job changed; create a revised plan/job')
    data['signature']=sig
    return job,data


def caption_groups(words,start,end):
    groups=[]; current=[]
    for w in words:
        if w['end']<=start or w['start']>=end: continue
        if current and (len(current)>=4 or w['start']-current[-1]['end']>.45):
            groups.append(current); current=[]
        current.append(w)
        if w['word'].endswith(('.', '?','!')): groups.append(current); current=[]
    if current: groups.append(current)
    return [{'start':max(0,g[0]['start']-start),'end':min(end-start,g[-1]['end']-start),
             'text':' '.join(w['word'] for w in g)} for g in groups]


def stamp(seconds,ass=False):
    ticks=int(round(seconds*(100 if ass else 1000)))
    rate=100 if ass else 1000
    hour,ticks=divmod(ticks,3600*rate); minute,ticks=divmod(ticks,60*rate); sec,sub=divmod(ticks,rate)
    return f'{hour}:{minute:02}:{sec:02}.{sub:02}' if ass else f'{hour:02}:{minute:02}:{sec:02},{sub:03}'


def subtitles(root,groups,width,height,framing=None):
    (root/'captions.srt').write_text('\n\n'.join(f"{i}\n{stamp(g['start'])} --> {stamp(g['end'])}\n{g['text']}" for i,g in enumerate(groups,1))+'\n',encoding='utf-8')
    # Visible full-width substitutions prevent imported ASS override execution.
    def escaped(s): return s.replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',' ').replace('\r',' ')
    stacked=framing and framing['mode']=='stacked'
    left,right,bottom=(.08,.12,framing['caption_bottom']) if stacked else (.1,.18,.23)
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,{max(12,int(width*.058))},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,{max(1,int(width*.003))},0,2,{int(width*left)},{int(width*right)},{int(height*bottom)},1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    (root/'captions.ass').write_text(header+''.join(f"Dialogue: 0,{stamp(g['start'],True)},{stamp(g['end'],True)},Default,,0,0,0,,{escaped(g['text'])}\n" for g in groups),encoding='utf-8')


def framing_filter(job,clip):
    w,h=job['width'],job['height']; f=clip['framing']
    # Normalize sample aspect ratio before applying display-space crop centers.
    base='scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,'
    if f['mode']=='fit': return base+f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    return base+f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='max(0,min(iw-ow,iw*{f['center_x']}-ow/2))':y='max(0,min(ih-oh,ih*{f['center_y']}-oh/2))',scale={w}:{h}:flags=lanczos,setsar=1"


def frame_at(seconds,start,fps):
    return round((Fraction(str(seconds))-Fraction(str(start)))*Fraction(fps))


def stacked_framing(f,start,end,job):
    """Resolve reviewed display-space crops and source-time shot boundaries."""
    def crop(value):
        if not isinstance(value,list) or len(value)!=4: raise ValueError('Stacked crops need [x,y,width,height]')
        x,y,w,h=map(number,value)
        if min(x,y)<0 or min(w,h)<=0 or x+w>1.00000001 or y+h>1.00000001:
            raise ValueError('Stacked crops must fit normalized display space')
        return [x,y,w,h]
    n=frame_at(end,start,job['fps'])
    if n<1: raise ValueError('Stacked clip needs at least one output frame')
    shots=[]; previous=start; last_frame=0
    for s in f.get('speaker_shots',[]):
        a,b=number(s['start']),number(s['end'])
        stop=frame_at(b,start,job['fps'])
        if abs(a-previous)>.00001 or not start<=a<b<=end or stop<=last_frame:
            raise ValueError('Speaker shots must cover the clip without gaps/overlaps or empty frame intervals')
        shots.append({'start':a,'end':b,'crop':crop(s['crop'])}); previous=b; last_frame=stop
    if not shots or abs(previous-end)>.00001 or last_frame!=n:
        raise ValueError('Speaker shots must cover the complete clip')
    g=f.get('graphic',{}); a,b=number(g['start']),number(g['end'])
    if not start<=a<b<=end or not 0<=frame_at(a,start,job['fps'])<frame_at(b,start,job['fps'])<=n:
        raise ValueError('Graphic live interval must contain frames inside the clip')
    # First/last stable graphic frames fill the interval outside the live window.
    graphic={'start':a,'end':b,'crop':crop(g['crop']),'hold_edges':True}
    if g.get('hold_edges',True) is not True: raise ValueError('Stacked graphics require disclosed edge holds')
    layout={k:number(f.get(k,v)) for k,v in {'speaker_height':1000/1920,'graphic_y':1024/1920,
        'graphic_height':810/1920,'caption_bottom':980/1920}.items()}
    sh,gy,gh,cb=(layout[k] for k in ('speaker_height','graphic_y','graphic_height','caption_bottom'))
    if not .25<=sh<=.75 or not sh<=gy<1 or not .1<=gh<=1-gy+.00000001 or not 1-sh+.015<=cb<=.95:
        raise ValueError('Stacked panels must fit without overlap; captions must sit inside the speaker panel')
    result={'mode':'stacked','speaker_shots':shots,'graphic':graphic,**layout}
    # Reject crops too small to survive chroma-aligned pixel rounding.
    for rect in [s['crop'] for s in shots]+[graphic['crop']]: crop_pixels(job,rect)
    return result


def crop_pixels(job,rect):
    v=video(job['media']); w,h=v['width'],v['height']
    ratio=v.get('sample_aspect_ratio')
    sar=Fraction(ratio.replace(':','/')) if ratio not in (None,'N/A','0:1') else Fraction(1)
    if sar<=0: raise ValueError('Prepare invalid sample aspect ratio before stacked composition')
    rotations=[s['rotation'] for s in v.get('side_data_list',[]) if 'rotation' in s]
    rotation=number(rotations[0] if rotations else v.get('tags',{}).get('rotate',0))%360
    if rotation not in (0,90,180,270): raise ValueError('Prepare arbitrary rotation before stacked composition')
    if rotation in (90,270): w,h=h,w; sar=1/sar
    w=int(w*sar)//2*2; h=h//2*2
    x,y,cw,ch=rect
    cw=int(w*cw)//2*2; ch=int(h*ch)//2*2
    if min(cw,ch)<2: raise ValueError('Stacked crop is smaller than two displayed pixels')
    x=min(w-cw,int(w*x)//2*2); y=min(h-ch,int(h*y)//2*2)
    return f'crop={cw}:{ch}:{x}:{y}'


def stacked_filter(job,clip):
    f=clip['framing']; fps=job['fps']; start=clip['start']; w,h=job['width'],job['height']
    n=frame_at(clip['end'],start,fps)
    even=lambda v:max(2,round(v/2)*2)
    sh=even(h*f['speaker_height']); gy=even(h*f['graphic_y']); gh=even(h*f['graphic_height'])
    if sh>gy or gy+gh>h: raise ValueError('Stacked panels overlap after pixel rounding')
    shots=f['speaker_shots']; count=len(shots)
    graph=[f"[0:{video(job['media'])['index']}]scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,fps={fps},split={count+1}"+
           ''.join(f'[in{i}]' for i in range(count+1))]
    for i,s in enumerate(shots):
        a,b=frame_at(s['start'],start,fps),frame_at(s['end'],start,fps)
        graph.append(f'[in{i}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,'+crop_pixels(job,s['crop'])+
            f',scale={w}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{sh},setsar=1[s{i}]')
    graph.append(''.join(f'[s{i}]' for i in range(count))+f'concat=n={count}:v=1:a=0[host]')
    g=f['graphic']; a,b=frame_at(g['start'],start,fps),frame_at(g['end'],start,fps)
    graph.append(f'[in{count}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,'+crop_pixels(job,g['crop'])+
        f',scale={w}:{gh}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,'+
        f'pad={w}:{gh}:(ow-iw)/2:(oh-ih)/2:color=0x0B0E14,setsar=1,'+
        f'tpad=start={a}:stop={n-b}:start_mode=clone:stop_mode=clone,trim=end_frame={n},setpts=N/(({fps})*TB)[graphic]')
    graph.append(f'color=c=0x0B0E14:s={w}x{h}:r={fps},trim=end_frame={n},setpts=N/(({fps})*TB)[bg]')
    graph.append(f'[bg][host]overlay=0:0:eof_action=repeat[base]')
    graph.append(f'[base][graphic]overlay=0:{gy}:eof_action=repeat,'+
        f'drawbox=x=0:y={sh}:w={w}:h={max(1,round(h/320))}:color=0x7C3AED:t=fill,'+
        f'fps={fps},tpad=stop=2:stop_mode=clone,trim=end_frame={n},setpts=N/(({fps})*TB),format=yuv420p[out]')
    return ';'.join(graph),n


def audio_fingerprint(path):
    """Hash encoded audio packets, independent of MP4 mux metadata."""
    return run(['ffmpeg','-v','error','-i',path,'-map','0:a:0','-c','copy','-f','streamhash','-hash','sha256','-']).strip()


def verify_stacked(path,reference,job,clip):
    v=video(probe(path)); expected=frame_at(clip['end'],clip['start'],job['fps'])
    if int(v.get('nb_frames',0))!=expected: raise ValueError('Stacked output frame count mismatch')
    rotations=[s['rotation'] for s in v.get('side_data_list',[]) if 'rotation' in s]
    rotations.append(v.get('tags',{}).get('rotate',0))
    if v.get('sample_aspect_ratio')!='1:1' or any(number(r)%360 for r in rotations):
        raise ValueError('Stacked output display orientation/aspect mismatch')
    a=audio(probe(path))[0]; b=audio(probe(reference))[0]
    if audio_fingerprint(path)!=audio_fingerprint(reference): raise ValueError('Complete audio packets changed during mux/captions')
    for key in ('start_time','duration'):
        if abs(number(a[key])-number(b[key]))>1/48000+.000001: raise ValueError('Stacked audio timing changed')
    return {'frames':expected,'audio_packets_unchanged':True,'audio_timing_unchanged':True,
            'graphic_holds':'First/last reviewed stable graphic frames held outside its live source interval'}


def verify(path,job,duration):
    media=probe(path); v=video(media)
    if not v or [v['width'],v['height']]!=[job['width'],job['height']] or len(audio(media))!=1:
        raise ValueError('Wrong output geometry/audio count')
    if abs(number(media['format']['duration'])-duration)>max(.15,2/float(Fraction(job['fps']))): raise ValueError('Output duration mismatch')
    if abs(float(Fraction(v['avg_frame_rate']))-float(Fraction(job['fps'])))>.001: raise ValueError('Output frame rate mismatch')
    if audio(media)[0]['channels']!=audio(job['media'])[job['audio_track']]['channels']: raise ValueError('Audio channel layout changed')
    ffmpeg(['-i',path,'-f','null','-'])
    return {'decoded':True,'dimensions':[v['width'],v['height']],'duration':number(media['format']['duration']),
            'fps':v['avg_frame_rate'],'audio_tracks':1,'channels':audio(media)[0]['channels']}


def preview(args):
    root=Path(args.job).resolve()
    with lock(root):
        job,data=load_plan(root)
        if not args.resume and args.accept_plan!=data['signature']: raise ValueError('Confirm the exact current plan signature')
        statepath=root/'preview.json'
        state=read(statepath) if statepath.exists() else {'plan_signature':data['signature'],'files':{},'verified':{}}
        if state['plan_signature']!=data['signature']: raise ValueError('Preview plan changed')
        if args.resume and not statepath.exists(): raise ValueError('Start preview before resuming')
        write(statepath,state)
        for name,sha in state['files'].items():
            if not (root/name).is_file() or digest(root/name)!=sha: raise ValueError('Completed output changed: '+name)
        clips=[c for c in data['clips'] if c['selected']]
        if any(c['captions']=='burn' for c in clips) and not doctor()['burn_captions']: raise ValueError('Burned captions need FFmpeg libass/subtitles; install a compatible build or revise the plan')
        if shutil.disk_usage(root).free<max(128*2**20,int(sum(c['end']-c['start'] for c in clips)*3*2**20)):
            raise ValueError('Insufficient storage for clean/captioned preview files')
        started=time.monotonic()
        for c in clips:
            folder=root/c['id']; folder.mkdir(exist_ok=True)
            duration=c['end']-c['start']; clean=folder/'clean.mp4'
            def stage(path,action):
                rel=path.relative_to(root).as_posix()
                if rel in state['files']: return
                if path.exists(): raise ValueError('Refusing to overwrite untracked output: '+rel)
                partial=path.with_name(path.stem+'.partial'+path.suffix); partial.unlink(missing_ok=True)
                action(partial); partial.replace(path); state['files'][rel]=digest(path); write(statepath,state)
            stacked=c['framing']['mode']=='stacked'
            if stacked:
                graph,n=stacked_filter(job,c)
                picture=folder/'picture.mp4'; speech=folder/'audio.m4a'
                # Isolate picture frame limits from audio; overlay EOF must never truncate speech.
                stage(picture,lambda p:ffmpeg(['-ss',c['start'],'-i',job['source']['path'],
                    '-filter_complex_threads','2','-filter_complex',graph,'-map','[out]',
                    '-r',job['fps'],'-fps_mode','cfr','-frames:v',n,'-an','-c:v','libx264',
                    '-preset','fast','-crf','18','-pix_fmt','yuv420p','-map_metadata','-1','-map_chapters','-1',p],cwd=folder))
                stage(speech,lambda p:ffmpeg(['-ss',c['start'],'-i',job['source']['path'],'-t',duration,
                    '-map',f"0:a:{job['audio_track']}",'-vn',
                    '-af',f'aresample=48000:async=1:first_pts=0,apad,atrim=duration={duration}',
                    '-c:a','aac','-b:a','192k','-map_metadata','-1','-map_chapters','-1',p],cwd=folder))
                stage(clean,lambda p:ffmpeg(['-i',picture,'-i',speech,'-map','0:v:0','-map','1:a:0',
                    '-c','copy','-map_metadata','-1','-map_chapters','-1','-movflags','+faststart',p],cwd=folder))
            else:
                stage(clean,lambda p:ffmpeg(['-ss',c['start'],'-i',job['source']['path'],'-t',duration,
                    '-map',f"0:{video(job['media'])['index']}",'-map',f"0:a:{job['audio_track']}",
                    '-vf',framing_filter(job,c)+',fps='+job['fps'],
                    '-af',f'aresample=48000:async=1:first_pts=0,apad,atrim=duration={duration}',
                    '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
                    '-map_metadata','-1','-map_chapters','-1','-movflags','+faststart',p],cwd=folder))
            state['verified'][c['id']+'/clean']=verify(clean,job,duration)
            if stacked: state['verified'][c['id']+'/clean'].update(verify_stacked(clean,speech,job,c))
            groups=caption_groups(data['transcript']['words'],c['start'],c['end'])
            subtitles(folder,groups,job['width'],job['height'],c['framing'])
            final=clean
            if c['captions']=='burn':
                final=folder/'captioned.mp4'
                stage(final,lambda p:ffmpeg(['-i',clean,'-vf','subtitles=filename=captions.ass','-c:v','libx264',
                    '-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',p],cwd=folder))
                state['verified'][c['id']+'/captioned']=verify(final,job,duration)
                if stacked: state['verified'][c['id']+'/captioned'].update(verify_stacked(final,speech,job,c))
            for label,offset in [('cover',c['cover_at']-c['start']),('frame-start',0),('frame-middle',duration/2),('frame-end',max(0,duration-.1))]:
                stage(folder/(label+'.jpg'),lambda p,offset=offset:ffmpeg(['-ss',offset,'-i',clean,'-frames:v','1','-q:v','3',p],cwd=folder))
            if stacked:
                cuts=[s['end'] for s in c['framing']['speaker_shots'][:-1]]
                cuts.extend(c['framing']['graphic'][k] for k in ('start','end'))
                dt=1/float(Fraction(job['fps']))
                for i,t in enumerate(sorted(set(cuts))):
                    for side,delta in [('before',-dt),('after',dt)]:
                        offset=max(0,min(duration-dt,t-c['start']+delta))
                        stage(folder/f'boundary-{i+1}-{side}.jpg',lambda p,offset=offset:ffmpeg(
                            ['-ss',offset,'-i',final,'-frames:v','1','-q:v','3',p],cwd=folder))
            clipmeta={**c,'source_sha256':job['source']['sha256'],'source_interval':[c['start'],c['end']],
                      'output_interval':[0,duration],'output':final.name,'audio_track':job['audio_track'],
                      'timing':'Normalized to nominal source CFR; no optical-flow interpolation','caption_groups':groups}
            write(folder/'metadata.json',clipmeta)
            for platform in ('tiktok','youtube-shorts'):
                (folder/(platform+'.txt')).write_text(c['title']+'\n\n'+c['description']+'\n\n'+', '.join(c['tags'])+'\n',encoding='utf-8')
            write(statepath,state)
        check_source(job)
        state['elapsed_seconds_this_run']=time.monotonic()-started
        state['ffmpeg']=run(['ffmpeg','-version']).splitlines()[0]
        # Receipt binds captions, metadata, copy and images too, not just encoded videos.
        for c in clips:
            for path in (root/c['id']).iterdir():
                if path.suffix in ('.mp4','.m4a','.jpg','.srt','.ass','.json','.txt'):
                    state['files'][path.relative_to(root).as_posix()]=digest(path)
        state['preview_signature']=signature({'plan':data['signature'],'files':state['files']})
        write(statepath,state)
        cards=''.join('<h2>'+html.escape(c['title'])+'</h2><p>'+html.escape(c['hook'])+'</p><video controls src="'+c['id']+'/'+
            ('captioned.mp4' if c['captions']=='burn' else 'clean.mp4')+'"></video><p><a href="'+c['id']+'/clean.mp4">Clean version</a> · <a href="'+c['id']+'/captions.srt">Editable captions</a></p>' for c in clips)
        note='<p>Stacked layouts hold the first/last reviewed graphic frame outside its live source interval. Check host shot changes and boundary images; holds are not new live demonstrations.</p>' if any(c['framing']['mode']=='stacked' for c in clips) else ''
        (root/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Shorts review</title><style>body{font:18px system-ui;max-width:900px;margin:auto}video{max-height:75vh;max-width:100%}</style><h1>Review full short-form drafts</h1><p>Check opening hook, complete payoff, faces, captions, crop and lip sync. No uploads.</p>'+note+cards,encoding='utf-8')
        return {'review':str(root/'review.html'),'preview_signature':state['preview_signature'],'human_review':'pending',
                'clips':[c['id'] for c in clips]}


def render(args):
    root=Path(args.job).resolve()
    with lock(root):
        job,data=load_plan(root); state=read(root/'preview.json')
        expected=signature({'plan':data['signature'],'files':state['files']})
        if state.get('plan_signature')!=data['signature'] or args.accept_preview!=expected or state.get('preview_signature')!=expected:
            raise ValueError('Accept the exact completed preview signature after review')
        for name,sha in state['files'].items():
            if not (root/name).is_file() or digest(root/name)!=sha: raise ValueError('Preview changed; review a revised preview')
        report={'source_unchanged':True,'preview_signature':expected,'files':state['files'],'verified':state['verified'],
                'accepted_at':time.time(),'delivery':'Full-length short drafts accepted in place; no second lossy encode',
                'audio_track':job['audio_track'],'omitted_audio_tracks':len(audio(job['media']))-1,
                'timing':'Source-relative seconds normalized to nominal CFR; human lip sync review required',
                'ffmpeg':state['ffmpeg'],'uploaded':False}
        write(root/'delivery.json',report)
        return {'delivery':str(root/'delivery.json'),'review':str(root/'review.html'),'source_unchanged':True}


def parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    a=sub.add_parser('analyze'); a.add_argument('--input',required=True); a.add_argument('--job',required=True)
    a.add_argument('--audio-track',type=int,default=0); a.add_argument('--width',type=int,default=1080); a.add_argument('--height',type=int,default=1920)
    a=sub.add_parser('plan')
    for flag in ('job','transcript','candidates'): a.add_argument('--'+flag,required=True)
    a=sub.add_parser('preview'); a.add_argument('--job',required=True); a.add_argument('--accept-plan',required=True)
    a=sub.add_parser('resume'); a.add_argument('--job',required=True)
    a=sub.add_parser('render'); a.add_argument('--job',required=True); a.add_argument('--accept-preview',required=True)
    return p


def main():
    args=parser().parse_args()
    try:
        if args.command=='doctor': result=doctor()
        elif args.command=='analyze': result=analyze(args)
        elif args.command=='plan': result=plan(args)
        elif args.command=='render': result=render(args)
        else:
            args.resume=args.command=='resume'; result=preview(args)
        # Reports remain UTF-8; stdout also works on legacy Windows consoles.
        print(json.dumps(result,indent=2,ensure_ascii=True))
    except (ValueError,OSError,KeyError,TypeError,ZeroDivisionError) as exc: raise SystemExit('Shorts: '+str(exc))


if __name__=='__main__': main()
