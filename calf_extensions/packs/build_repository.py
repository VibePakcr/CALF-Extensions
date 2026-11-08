"""Build a retained Local Git candidate; no core, SDK, media or model bundled."""
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
    # Validate the label before it becomes a filename.
    meta=json.loads((source/'specs/pack-v1/examples/repository.json').read_text('utf8'))
    meta.update(version=version,availability='candidate',channel='experimental')
    meta['summary']={'en':'Read-only Local Git capture and project navigation; no core or SDK required.','ko':'코어·SDK 없이 사용하는 읽기 전용 로컬 Git 수집·프로젝트 탐색 팩입니다.'}
    meta['entryPoints'][0].update(status='implemented',targetKind='python-module',target='calf_extensions.repository.cli')
    meta['modes'][0]['status']='implemented'
    meta['verification']['requiredChecks']=['git-contracts','navigation-contracts','limits-contracts']
    meta['verification']['runtimeEvidence']=['REPOSITORY_VERIFICATION.json']
    meta['documentation']={'en':'docs/REPOSITORY_PACK.md','ko':'docs/REPOSITORY_PACK_KR.md'}
    output.mkdir(parents=True);payload=output/'payload';payload.mkdir()
    names=['calf_extensions/__init__.py','LICENSE-EXTENSIONS.txt','REPOSITORY_VERIFICATION.json']
    names += [p.relative_to(source).as_posix() for p in (source/'calf_extensions/repository').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    names += ['docs/'+n for n in ['REPOSITORY_PACK.md','REPOSITORY_PACK_KR.md','REPOSITORY_HISTORY.md','REPOSITORY_HISTORY_KR.md','REPOSITORY_NAVIGATOR.md','REPOSITORY_NAVIGATOR_KR.md','REPOSITORY_LOCAL_GIT_PLAN.md','REPOSITORY_LOCAL_GIT_PLAN_KR.md']]
    for name in sorted(set(names)):
        relative(name);origin=physical(source/name);before=sha(origin);target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,target)
        if sha(target)!=before or sha(origin)!=before:raise ValueError('source_changed_during_build')
    (payload/'pack.json').write_bytes(canonical(meta)+b'\n');manifest(payload/'pack.json')
    (payload/'qualification.json').write_bytes(canonical({'schema':'calf.pack.candidate.v1','lifecycleStatus':'NOT_RUN','requiredChecks':meta['verification']['requiredChecks'],'note':'Local Git inspect lifecycle only; hosted access and browser qualification are separate.'})+b'\n')
    (payload/'README.md').write_text('# Repository local candidate pack\n\n[English](docs/REPOSITORY_PACK.md) · [한국어](docs/REPOSITORY_PACK_KR.md)\n\nStage and qualify this candidate with the local pack manager before activation. No core, SDK or global installation is required.\n',encoding='utf8')
    files=sorted(p for p in payload.rglob('*') if p.is_file())
    (payload/'FILES.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(payload).as_posix()+'\n' for p in files),encoding='utf8',newline='\n')
    archive=output/('CALF-Repository-Pack-'+version+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(payload.rglob('*')):
            if not p.is_file():continue
            info=zipfile.ZipInfo(p.relative_to(payload).as_posix(),(2026,11,7,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            with p.open('rb') as src,z.open(info,'w') as dest:shutil.copyfileobj(src,dest,32768)
    result={'archive':str(archive),'sha256':sha(archive),'id':meta['id'],'version':version,'availability':'candidate'}
    (output/'build.json').write_bytes(canonical(result)+b'\n');return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.version),indent=2))

if __name__=='__main__':main()
