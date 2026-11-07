"""Build a local candidate wrapper; never modifies the shipped FFmpeg 0.1.0."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile
from .io import physical,sha,canonical,relative
from .metadata import manifest

def build(source,output,version):
    source=physical(source,directory=True);output=Path(output)
    if not output.is_absolute() or output.exists():raise ValueError('new_build_folder_required')
    output.mkdir(parents=True,exist_ok=False);payload=output/'payload';payload.mkdir()
    names=['calf_extensions/__init__.py','VERIFICATION.json','LICENSE-EXTENSIONS.txt','LICENSE-SDK.txt']
    names += ['calf_extensions/media_ffmpeg/'+n for n in ('__init__.py','cli.py','common.py','integration.py','project.py','runtime.py','validator.py','verify.py','test_contract.py','profile.json')]
    names += ['docs/'+n for n in ('FFMPEG.md','FFMPEG_KR.md','AGENTS.md','AGENTS_KR.md','CLAUDE.md','CLAUDE_KR.md')]
    names += ['examples/scene_candidate.py','examples/claude_work.py']
    for name in names:
        relative(name);origin=physical(source/name);target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,target)
    meta=json.loads((source/'specs/pack-v1/examples/ffmpeg.json').read_text('utf8'))
    meta.update(version=version,availability='candidate',channel='experimental')
    (payload/'pack.json').write_bytes(canonical(meta)+b'\n');manifest(payload/'pack.json')
    (payload/'qualification.json').write_bytes(canonical({'schema':'calf.pack.candidate.v1','lifecycleStatus':'NOT_RUN',
        'note':'Local installation checks required. Existing runtime qualification is reused only for explicit platform/core identities.'})+b'\n')
    (payload/'README.md').write_text('# FFmpeg local candidate pack\n\nThis wrapper adds candidate pack metadata to the existing FFmpeg runtime.\nUse the local pack manager to stage, check and qualify it; no global installation is required.\n\n[English](docs/FFMPEG.md) · [한국어](docs/FFMPEG_KR.md)\n',encoding='utf8',newline='\n')
    # The wrapper is intentionally not a new pip distribution or global CLI installation.
    for name in ('FFMPEG.md','FFMPEG_KR.md'):
        p=payload/'docs'/name;s=p.read_text('utf8')
        if name=='FFMPEG.md':s=s.replace('Optional local installation with existing setuptools is `python -m pip install --no-build-isolation --no-deps .`; install the separate SDK into that environment as well.','This candidate wrapper runs from its retained payload directory; pip installation is not part of the pack lifecycle.')
        else:s=s.replace('setuptools가 있는 별도 환경에서는 `python -m pip install --no-build-isolation --no-deps .`로 로컬 설치할 수도 있습니다. 같은 환경에 별도 SDK도 준비해야 합니다.','후보 팩은 보존된 payload 폴더에서 실행합니다. 팩 설치 과정에서 pip 설치나 전역 환경 변경을 수행하지 않습니다.')
        p.write_text(s,encoding='utf8',newline='\n')
    files=sorted(p for p in payload.rglob('*') if p.is_file())
    (payload/'FILES.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(payload).as_posix()+'\n' for p in files),encoding='utf8',newline='\n')
    archive=output/('CALF-FFmpeg-Pack-'+version+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(payload.rglob('*')):
            if p.is_file():
                info=zipfile.ZipInfo(p.relative_to(payload).as_posix(),(2026,11,7,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
                with p.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,32768)
    result={'archive':str(archive),'sha256':sha(archive),'id':meta['id'],'version':version,'availability':'candidate'}
    (output/'build.json').write_bytes(canonical(result)+b'\n');return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.version),indent=2))

if __name__=='__main__':main()
