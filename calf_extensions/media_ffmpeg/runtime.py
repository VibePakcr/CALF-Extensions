"""One CPU-bounded, synchronous transcode. No shell or arbitrary FFmpeg flags."""
import json
from pathlib import Path
import sys
from common import (read_work_request, runtime_result, emit_work, toolchain, profile,
                    scene_scope, candidate, run_tool, exact)

def execute(request, tools):
    if request['operation']!='execute':
        raise ValueError('execute_only')
    exact(request['parameters'],['profile'],'runtime_parameters')
    p=profile(request['parameters']['profile'])
    source,_,_=scene_scope(request)
    if len(request['outputs'])!=1 or request['outputs'][0]['id']!='video' or request['outputs'][0]['mediaType']!='video/mp4':
        raise ValueError('one_mp4_output_required')
    target=candidate(request['outputDirectory'],request['outputs'][0]['path'])
    filters=(f"scale={p['width']}:{p['height']}:force_original_aspect_ratio=decrease,"
             f"pad={p['width']}:{p['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={p['fps']}")
    argv=[tools['ffmpeg']['path'],'-hide_banner','-nostdin','-v','error','-n',
          '-threads','2','-filter_threads','1','-filter_complex_threads','1',
          '-protocol_whitelist','file','-format_whitelist','mov','-i',str(source),
          '-ss',f"{p['startMs']/1000:.3f}",'-t',f"{p['durationMs']/1000:.3f}",
          '-map','0:v:0','-sn','-dn','-map_metadata','-1','-map_chapters','-1',
          '-vf',filters,'-c:v','libx264','-preset','veryfast','-crf','23',
          '-pix_fmt','yuv420p','-threads','2']
    if p['audio']:
        argv+=['-map','0:a:0','-c:a','aac','-ar','48000','-ac','2','-b:a','128k']
    else:
        argv+=['-an']
    argv+=['-movflags','+faststart','-fs','67108864','-f','mp4',str(target)]
    run_tool(argv)
    return runtime_result(request,'succeeded')

def main():
    request=read_work_request(sys.argv[-1])
    try:
        result=execute(request,toolchain(sys.argv[-2]))
    except Exception as error:
        print('FFmpeg adapter stopped: '+type(error).__name__+': '+str(error)[:200],file=sys.stderr)
        result=runtime_result(request,'failed')
    emit_work(result)

if __name__=='__main__':main()
