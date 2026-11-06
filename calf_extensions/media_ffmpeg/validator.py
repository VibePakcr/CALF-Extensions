"""Independent ffprobe/full-decode validator; does not import the producer."""
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import sys
from common import (read_work_request, validation_result, emit_work, toolchain, profile,
                    scene_scope, candidate, run_tool, sha, digest, exact, ToolError, MediaError)


def metadata_violations(data, expected):
    """Requirements come from the frozen check, not producer-reported metadata."""
    failures=[]
    streams=data.get('streams',[])
    video=[s for s in streams if s.get('codec_type')=='video']
    audio=[s for s in streams if s.get('codec_type')=='audio']
    if len(video)!=1 or len(audio)!=(1 if expected['audio'] else 0) or len(streams)!=len(video)+len(audio):
        return ['stream_inventory'],{}
    v=video[0];fmt=data.get('format',{});wanted_frames=expected['durationMs']*expected['fps']//1000
    actual={'width':v.get('width'),'height':v.get('height'),'fps':v.get('avg_frame_rate'),
            'frames':v.get('nb_read_frames'),'audio':bool(audio),'durationMs':None,'blackMs':None,'silenceMs':None}
    for field in ['width','height']:
        if type(v.get(field)) is not int or v[field]!=expected[field]:failures.append(field)
    if v.get('codec_name')!='h264':failures.append('video_codec')
    if v.get('pix_fmt')!='yuv420p':failures.append('pixel_format')
    try:
        if Fraction(v.get('avg_frame_rate','0/1'))!=expected['fps']:failures.append('frame_rate')
        if int(v.get('nb_read_frames','-1'))!=wanted_frames:failures.append('frame_count')
    except (ValueError,ZeroDivisionError,TypeError):failures.append('frame_metadata')
    durations=[]
    for observed in [fmt.get('duration'),v.get('duration')]:
        try:
            milliseconds=float(observed)*1000
            if not math.isfinite(milliseconds) or abs(milliseconds-expected['durationMs'])>50:failures.append('duration')
            durations.append(milliseconds)
        except (ValueError,TypeError):failures.append('duration_metadata')
    if durations:actual['durationMs']=round(durations[0],3)
    if 'mp4' not in fmt.get('format_name','').split(',') or fmt.get('tags',{}).get('major_brand','').strip() not in ['isom','iso2','mp41','mp42','avc1']:
        failures.append('mp4_container')
    if audio:
        a=audio[0]
        if a.get('codec_name')!='aac' or a.get('sample_rate')!='48000' or a.get('channels')!=2:
            failures.append('audio_specification')
    return sorted(set(failures)),actual


def validate(request, tools):
    if request['operation']!='validate':raise MediaError('validate_only')
    check=request['extra']['check'];manifest=request['extra']['manifest']
    exact(check['rule']['parameters'],['expected','scopeSha256'],'validator_parameters')
    expected=profile(check['rule']['parameters']['expected'])
    _,scope,scope_hash=scene_scope(request)
    if scope_hash!=check['rule']['parameters']['scopeSha256']:raise MediaError('scope_hash_mismatch')
    artifacts=manifest['artifacts']['files']
    if len(artifacts)!=1 or artifacts[0]['id']!=check['artifact'] or artifacts[0]['id']!='video':raise MediaError('video_artifact_required')
    target=candidate(request['outputDirectory'],artifacts[0]['path'],existing=True)
    if sha(target)!=artifacts[0]['sha256']:raise MediaError('candidate_version_changed')
    base={'schema':'calf.media.ffmpeg.validation.v1','scopeSha256':scope_hash,
          'projectId':scope['projectId'],'sceneId':scope['sceneId'],'baseManifestDigest':scope['baseManifestDigest'],
          'profileSha256':digest(expected),'artifactPath':str(target),'artifactSha256':artifacts[0]['sha256'],'checks':[],'measurements':None,'violations':[]}
    argv=[tools['ffprobe']['path'],'-v','error','-threads','2','-protocol_whitelist','file',
          '-format_whitelist','mov','-count_frames','-show_entries',
          'format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration,sample_rate,channels',
          '-of','json',str(target)]
    try:
        raw,_=run_tool(argv)
    except ToolError as error:
        if error.code!='tool_nonzero':raise
        base['violations']=['unreadable_media'];return 'VIOLATED',base
    data=json.loads(raw)
    failures,actual=metadata_violations(data,expected);base['measurements']=actual;base['checks'].append('probe_and_frame_count')
    if failures:
        base['violations']=failures;return 'VIOLATED',base
    # Always decode the entire candidate, with decoder errors fatal. Detection is
    # optional and its absence is reported as null, never as measured zero.
    args=[tools['ffmpeg']['path'],'-hide_banner','-nostdin','-nostats','-v','info','-xerror',
          '-err_detect','explode','-threads','2','-filter_threads','1','-protocol_whitelist','file',
          '-format_whitelist','mov','-i',str(target),'-map','0:v:0']
    if expected['audio']:args+=['-map','0:a:0']
    if expected['maxBlackMs'] is not None:args+=['-vf','blackdetect=d=0.1:pic_th=0.98:pix_th=0.1']
    if expected['maxSilenceMs'] is not None:args+=['-af','silencedetect=noise=-50dB:d=0.1']
    args+=['-threads','2','-f','null','-']
    try:
        _,log=run_tool(args,stdout_limit=8192)
    except ToolError as error:
        if error.code!='tool_nonzero':raise
        base['violations']=['full_decode'];return 'VIOLATED',base
    base['checks'].append('full_decode')
    for key,token in [('maxBlackMs','black_duration'),('maxSilenceMs','silence_duration')]:
        if expected[key] is None:continue
        observed=[float(v)*1000 for v in re.findall(token+r':\s*([0-9]+(?:\.[0-9]+)?)',log)]
        maximum=max(observed,default=0)
        label='blackMs' if key=='maxBlackMs' else 'silenceMs'
        actual[label]=round(maximum,3);base['checks'].append(label)
        if maximum>expected[key]+1:base['violations'].append(label)
    if sha(target)!=artifacts[0]['sha256']:raise MediaError('candidate_changed_during_check')
    return ('VIOLATED' if base['violations'] else 'SATISFIED'),base


def main():
    request=read_work_request(sys.argv[-1])
    try:
        outcome,detail=validate(request,toolchain(sys.argv[-2]))
        reason=json.dumps(detail,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        if len(reason.encode('utf-8'))>2048:raise MediaError('validation_detail_limit')
        result=validation_result(request,outcome,reason)
    except Exception as error:
        result=validation_result(request,'UNKNOWN','Media validation unavailable: '+type(error).__name__+': '+str(error)[:300])
    emit_work(result)

if __name__=='__main__':main()
