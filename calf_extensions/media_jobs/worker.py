"""CALF adapter: copy a returned MP4 unchanged, or independently check it."""
import json
import os
from pathlib import Path
import re
import sys

if len(sys.argv)!=4:raise RuntimeError('sdk_toolchain_request_required')
sys.path.insert(0,str(Path(sys.argv[1])))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'media_ffmpeg'))
from common import (read_work_request, runtime_result, validation_result, emit_work,
                    scene_scope, candidate, sha, digest, toolchain, run_tool, exact,
                    ToolError, MAX_MEDIA_BYTES)
from validator import metadata_violations
from calf_extensions.media_jobs.contracts import delivery_profile, hex_digest


def execute(request):
    exact(request['parameters'],['profile','handoffSha256'],'intake_parameters')
    delivery_profile(request['parameters']['profile']);hex_digest(request['parameters']['handoffSha256'])
    source,_,_=scene_scope(request)
    if len(request['outputs'])!=1 or request['outputs'][0]['id']!='video' or request['outputs'][0]['mediaType']!='video/mp4':
        raise ValueError('one_video_output_required')
    target=candidate(request['outputDirectory'],request['outputs'][0]['path'])
    total=0
    with source.open('rb') as src,target.open('xb') as dst:
        for block in iter(lambda:src.read(32768),b''):
            total+=len(block)
            if total>MAX_MEDIA_BYTES:raise ValueError('intake_size_limit')
            dst.write(block)
        dst.flush();os.fsync(dst.fileno())
    if sha(target)!=sha(source):raise ValueError('intake_copy_changed')
    return runtime_result(request,'succeeded')


def validate(request,tools):
    check=request['extra']['check'];manifest=request['extra']['manifest']
    exact(check['rule']['parameters'],['expected','scopeSha256'],'validator_parameters')
    expected=delivery_profile(check['rule']['parameters']['expected'])
    _,scope,scope_hash=scene_scope(request)
    if scope_hash!=check['rule']['parameters']['scopeSha256']:raise ValueError('scope_hash_mismatch')
    artifacts=manifest['artifacts']['files']
    if len(artifacts)!=1 or artifacts[0]['id']!=check['artifact'] or check['artifact']!='video':
        raise ValueError('one_video_artifact_required')
    target=candidate(request['outputDirectory'],artifacts[0]['path'],existing=True)
    if sha(target)!=artifacts[0]['sha256'] or sha(target)!=scope['sourceSha256']:
        raise ValueError('returned_bytes_changed')
    # Same public technical-receipt shape used by the existing scene selector.
    detail={'schema':'calf.media.ffmpeg.validation.v1','scopeSha256':scope_hash,
            'projectId':scope['projectId'],'sceneId':scope['sceneId'],'baseManifestDigest':scope['baseManifestDigest'],
            'profileSha256':digest(expected),'artifactPath':str(target),'artifactSha256':artifacts[0]['sha256'],
            'checks':[],'measurements':None,'violations':[]}
    probe=[tools['ffprobe']['path'],'-v','error','-threads','2','-protocol_whitelist','file',
           '-format_whitelist','mov','-count_frames','-show_entries',
           'format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration,sample_rate,channels',
           '-of','json',str(target)]
    try:
        raw,_=run_tool(probe)
        failures,actual=metadata_violations(json.loads(raw),expected)
        detail['checks'].append('probe_and_frame_count');detail['measurements']=actual
        if failures:
            detail['violations']=failures;return 'VIOLATED',detail
        decode=[tools['ffmpeg']['path'],'-hide_banner','-nostdin','-nostats','-v','info','-xerror',
                '-err_detect','explode','-threads','2','-filter_threads','1','-protocol_whitelist','file',
                '-format_whitelist','mov','-i',str(target),'-map','0:v:0']
        if expected['audio']:decode+=['-map','0:a:0']
        if expected['maxBlackMs'] is not None:decode+=['-vf','blackdetect=d=0.1:pic_th=0.98:pix_th=0.1']
        if expected['maxSilenceMs'] is not None:decode+=['-af','silencedetect=noise=-50dB:d=0.1']
        _,log=run_tool(decode+['-threads','2','-f','null','-'],stdout_limit=8192)
        detail['checks'].append('full_decode')
    except ToolError as error:
        if error.code!='tool_nonzero':raise
        detail['violations']=['unreadable_or_decode_failed'];return 'VIOLATED',detail
    for key,token,label in [('maxBlackMs','black_duration','blackMs'),('maxSilenceMs','silence_duration','silenceMs')]:
        if expected[key] is None:continue
        maximum=max([float(v)*1000 for v in re.findall(token+r':\s*([0-9]+(?:\.[0-9]+)?)',log)],default=0)
        actual[label]=round(maximum,3);detail['checks'].append(label)
        if maximum>expected[key]+1:detail['violations'].append(label)
    if sha(target)!=artifacts[0]['sha256']:raise ValueError('candidate_changed_during_check')
    return ('VIOLATED' if detail['violations'] else 'SATISFIED'),detail


def main():
    request=read_work_request(sys.argv[-1])
    try:
        if request['operation']=='execute':result=execute(request)
        elif request['operation']=='validate':
            outcome,detail=validate(request,toolchain(sys.argv[-2]))
            reason=json.dumps(detail,ensure_ascii=False,separators=(',',':'),allow_nan=False)
            if len(reason.encode('utf-8'))>2048:raise ValueError('validation_detail_limit')
            result=validation_result(request,outcome,reason)
        else:raise ValueError('execute_or_validate_only')
    except Exception as error:
        if request['operation']=='validate':result=validation_result(request,'UNKNOWN',type(error).__name__+': '+str(error)[:300])
        else:
            print(type(error).__name__+': '+str(error)[:300],file=sys.stderr)
            result=runtime_result(request,'failed')
    emit_work(result)

if __name__=='__main__':main()
