#!/usr/bin/env python3
"""Local publishing-package assembly; creative copy/art are supplied by the agent."""
import argparse
from contextlib import contextmanager
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''): h.update(block)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temp.replace(path)


def run(command, log=None, cwd=None):
    command = list(map(str, command))
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
    if log:
        with Path(log).open('a', encoding='utf-8') as f: f.write(json.dumps(command, ensure_ascii=False)+'\n'+result.stderr[-8000:]+'\n')
    if result.returncode: raise ValueError(result.stderr[-3000:] or 'Command failed')
    return result.stdout


def ffmpeg(args, **kw):
    return run(['ffmpeg','-hide_banner','-nostdin','-v','error','-n','-threads','2',*args], **kw)


def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',path]))


def video(media):
    return next((s for s in media['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)


def audio(media): return [s for s in media['streams'] if s['codec_type']=='audio']


def number(value):
    value = float(value)
    if not math.isfinite(value): raise ValueError('Numbers must be finite')
    return value


def text(value, label):
    if not isinstance(value,str) or not value.strip() or '\x00' in value: raise ValueError('Missing/invalid '+label)
    return value.strip()


def metadata(data, duration):
    if not isinstance(data,dict): raise ValueError('Metadata must be an object')
    for key in ('tags','alternate_titles','chapters'):
        if key in data and not isinstance(data[key],list): raise ValueError(key+' must be a list')
    result = {k:text(data.get(k),k) for k in ('title','description','show_title','artist','content_summary')}
    result['tags'] = [text(t,'tag') for t in data.get('tags',[])]
    if not result['tags']: raise ValueError('Supply relevant tags')
    result['alternate_titles'] = [text(t,'alternate title') for t in data.get('alternate_titles',[])]
    result['audio_description'] = text(data.get('audio_description',result['description']),'audio description')
    result['video_description'] = text(data.get('video_description',result['description']),'video description')
    result['chapters'], last = [], -1
    for chapter in data.get('chapters',[]):
        start = number(chapter['start'])
        if not 0 <= start < duration or start <= last: raise ValueError('Chapters must be ordered on the final timeline')
        result['chapters'].append({'start':start,'title':text(chapter['title'],'chapter title')})
        last = start
    return result


def doctor():
    tools = {k:shutil.which(k) for k in ('ffmpeg','ffprobe')}
    return {'tools':tools,'ready':all(tools.values()),'dependencies':'Python 3.10+ and FFmpeg/ffprobe; no Python packages or model downloads',
            'artwork':'Agent uses an available image-generation tool or separately designed supplied artwork; this helper formats approved images.'}


def analyze(args):
    source, root = Path(args.input).resolve(), Path(args.job).resolve()
    if not source.is_file(): raise ValueError('Source must be a local media file')
    media = probe(source)
    if not audio(media): raise ValueError('A complete dialogue audio track is required')
    duration = number(media['format']['duration'])
    if duration <= 0: raise ValueError('Invalid source duration')
    v = video(media)
    if v and (v.get('color_transfer') in ('smpte2084','arib-std-b67') or v.get('field_order') not in (None,'unknown','progressive')):
        raise ValueError('Prepare HDR/interlaced footage explicitly before SDR packaging')
    if not 0 <= args.audio_track < len(audio(media)): raise ValueError('Choose an existing dialogue track')
    if audio(media)[args.audio_track].get('channels') not in (1,2): raise ValueError('Prepare a mono/stereo dialogue mix explicitly')
    root.mkdir(parents=True,exist_ok=False)
    job = {'schema':1,'source':{'path':str(source),'sha256':digest(source),'size':source.stat().st_size},
           'media':media,'duration':duration,'audio_track':args.audio_track,'created':time.time()}
    write(root/'job.json',job)
    return {'job':str(root),'duration':duration,'audio_tracks':len(audio(media)),'selected_audio_track':args.audio_track,
            'audio_only':v is None,'next':'Write source-grounded metadata JSON and create separate square/wide artwork, then package.'}


@contextmanager
def lock(root):
    marker = root/'.running'
    try:
        with marker.open('x') as f: f.write(str(__import__('os').getpid()))
    except FileExistsError: raise ValueError('Job is running/interrupted; verify the process stopped before removing .running')
    try: yield
    finally: marker.unlink(missing_ok=True)


def check_source(job):
    source = Path(job['source']['path'])
    if not source.is_file() or source.stat().st_size != job['source']['size'] or digest(source)!=job['source']['sha256']:
        raise ValueError('Source changed; create a new job')


def artwork(source, output, width, height, log):
    media = probe(source)
    v = video(media)
    if not v or abs(v['width']/v['height'] - width/height) > .02:
        raise ValueError('Artwork must already be composed for its target aspect ratio; do not stretch/crop a different layout')
    # Explicit JPEG export is opaque. Record original pixels so resizing is not
    # mistaken for newly generated detail.
    for quality in (2,4,6,9,14,20,26,31):
        output.unlink(missing_ok=True)  # Only this runner-owned temporary file.
        ffmpeg(['-i',source,'-frames:v','1','-vf',f'scale={width}:{height}:flags=lanczos,format=yuvj444p',
                '-q:v',quality,output],log=log)
        if output.stat().st_size <= 2_000_000: break
    if output.stat().st_size > 2_000_000: raise ValueError('Artwork exceeds the conservative 2 MB delivery budget')
    return {'input_dimensions':[v['width'],v['height']],'output_dimensions':[width,height],
            'resized_up':v['width']<width or v['height']<height,'opaque_jpeg':True,'bytes':output.stat().st_size}


def verify(path, duration=None, require_video=False):
    media = probe(path)
    if duration is not None and abs(number(media['format']['duration'])-duration)>.2:
        raise ValueError('Output duration differs from the source')
    if require_video and (not video(media) or not audio(media)): raise ValueError('MP4 must contain picture and sound')
    run(['ffmpeg','-v','error','-i',path,'-map','0:v?','-map','0:a?','-f','null','-'])
    return {'decoded':True,'duration':number(media['format']['duration']),'audio_tracks':len(audio(media))}


def package(args):
    root = Path(args.job).resolve()
    job = json.loads((root/'job.json').read_text(encoding='utf-8'))
    if job.get('schema')!=1: raise ValueError('Unsupported package job')
    with lock(root):
        check_source(job)
        if args.resume:
            config = json.loads((root/'package-config.json').read_text(encoding='utf-8'))
        else:
            if (root/'package-config.json').exists(): raise ValueError('Package already started; use resume or a new job')
            config = {'metadata':metadata(json.loads(Path(args.metadata).read_text(encoding='utf-8')),job['duration']),
                      'square':str(Path(args.square).resolve()),'wide':str(Path(args.wide).resolve())}
            config['asset_hashes'] = {k:digest(config[k]) for k in ('square','wide')}
            write(root/'package-config.json',config)
        for k in ('square','wide'):
            if digest(config[k])!=config['asset_hashes'][k]: raise ValueError('Artwork changed; create a revised job')
        meta, source = config['metadata'],job['source']['path']
        signature = hashlib.sha256(json.dumps({'job':job,'config':config},sort_keys=True).encode()).hexdigest()
        state_path = root/'state.json'
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'signature':signature,'completed':{},'artwork':{},'verified':{}}
        if state['signature']!=signature: raise ValueError('Settings changed; create a revised job')
        write(state_path,state)
        if shutil.disk_usage(root).free < max(256*2**20,int(job['duration']*2*2**20)):
            raise ValueError('Insufficient storage for exports/checkpoints')
        started = time.monotonic()
        log = root/'processing.log'
        for name in ('cover-square.jpg','featured-wide.jpg','episode.mp3','episode.mp4'):
            output = root/name
            if name in state['completed']:
                if not output.is_file() or digest(output)!=state['completed'][name]: raise ValueError('Completed output changed: '+name)
                continue
            if output.exists(): raise ValueError('Refusing to overwrite an untracked output: '+name)
            partial = output.with_name(output.stem+'.partial'+output.suffix)
            partial.unlink(missing_ok=True)
            if name.endswith('.jpg'):
                key,w,h = ('square',3000,3000) if name.startswith('cover') else ('wide',3840,2160)
                state['artwork'][name] = artwork(config[key],partial,w,h,log)
            else:
                tags = ['-map_metadata','-1','-map_chapters','-1','-metadata','title='+meta['title'],
                        '-metadata','artist='+meta['artist'],'-metadata','album='+meta['show_title'],
                        '-metadata','comment='+meta['description']]
                af = ['-af',f"aresample=48000:async=1:first_pts=0,apad,atrim=duration={job['duration']}"]
                if name.endswith('.mp3'):
                    ffmpeg(['-i',source,'-i',root/'cover-square.jpg','-map',f"0:a:{job['audio_track']}",'-map','1:v:0',
                        *af,'-c:a','libmp3lame','-b:a','256k','-c:v','copy','-id3v2_version','3',
                        '-disposition:v:0','attached_pic','-metadata:s:v','title=Album cover','-metadata:s:v','comment=Cover (front)',*tags,partial],log=log)
                else:
                    v = video(job['media'])
                    inputs = ['-i',source] if v else ['-loop','1','-framerate','30','-i',root/'featured-wide.jpg','-i',source]
                    ai = 0 if v else 1
                    vf = 'scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1' if v else 'scale=1920:1080,setsar=1'
                    ffmpeg([*inputs,'-map',f"0:{v['index']}" if v else '0:v:0','-map',f"{ai}:a:{job['audio_track']}",'-vf',vf,*af,
                        '-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
                        '-t',job['duration'],*tags,'-movflags','+faststart',partial],log=log)
                state['verified'][name]=verify(partial,job['duration'],require_video=name.endswith('.mp4'))
            partial.replace(output)
            state['completed'][name] = digest(output)
            write(state_path,state)
        for kind in ('audio','video'):
            (root/(kind+'-publishing.txt')).write_text(meta['title']+'\n\n'+meta[kind+'_description']+
                '\n\nTags: '+', '.join(meta['tags'])+'\n',encoding='utf-8')
        (root/'chapters.txt').write_text('\n'.join(f"{int(c['start']//60):02}:{int(c['start']%60):02} {c['title']}" for c in meta['chapters']),encoding='utf-8')
        write(root/'metadata.json',meta)
        check_source(job)
        report = {'source_unchanged':True,'signature':signature,'audio_track':job['audio_track'],
            'unselected_audio_tracks':len(audio(job['media']))-1,'metadata':meta,'artwork':state['artwork'],
            'files':state['completed'],'verified':state['verified'],'core_elapsed_seconds_this_run':time.monotonic()-started,
            'versions':{'ffmpeg':run(['ffmpeg','-version']).splitlines()[0]},
            'human_review':'Artwork, copy accuracy, sound and lip sync pending; not uploaded or scheduled'}
        write(root/'report.json',report)
        (root/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Podcast package</title>'
            '<style>body{font:18px system-ui;max-width:1100px;margin:30px auto}img{max-width:45%}video{width:100%}</style>'
            '<h1>'+html.escape(meta['title'])+'</h1><p>'+html.escape(meta['description'])+'</p>'
            '<img src="cover-square.jpg" alt="Square cover"><img src="featured-wide.jpg" alt="Wide feature image">'
            '<video controls src="episode.mp4"></video><audio controls src="episode.mp3"></audio>'
            '<p><a href="metadata.json">Metadata</a> · <a href="audio-publishing.txt">Audio copy</a> · '
            '<a href="video-publishing.txt">Video copy</a> · <a href="report.json">Verification</a></p>',encoding='utf-8')
        return {'review':str(root/'review.html'),'mp3':str(root/'episode.mp3'),'mp4':str(root/'episode.mp4'),
                'source_unchanged':True,'human_review':'pending'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    a = sub.add_parser('analyze')
    a.add_argument('--input',required=True); a.add_argument('--job',required=True)
    a.add_argument('--audio-track',type=int,default=0)
    a = sub.add_parser('package')
    for flag in ('job','metadata','square','wide'): a.add_argument('--'+flag,required=True)
    a = sub.add_parser('resume'); a.add_argument('--job',required=True)
    return p


def main():
    args = parser().parse_args()
    try:
        if args.command=='doctor': result=doctor()
        elif args.command=='analyze': result=analyze(args)
        else:
            args.resume=args.command=='resume'
            result=package(args)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as exc: raise SystemExit('Packager: '+str(exc))


if __name__=='__main__': main()
