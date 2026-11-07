"""Build an allowlisted portable media-jobs preview; never activate a live pack."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile

PUBLISHED_VERSIONS=frozenset({'0.1.0-preview.1'})
PACK_ID='calf.media.jobs'
COPY_FILES=['AGENTS.md','LICENSE-EXTENSIONS.txt','LICENSE-SDK.txt','calf_extensions/__init__.py']
COPY_FILES+=['calf_extensions/media_jobs/'+n for n in ['__init__.py','cli.py','contracts.py','manager.py','worker.py','verify.py','README.md','README_KR.md']]
COPY_FILES+=['calf_extensions/media_ffmpeg/'+n for n in ['__init__.py','cli.py','common.py','integration.py','project.py','runtime.py','validator.py','verify.py','test_contract.py','profile.json']]
COPY_FILES+=['docs/'+n for n in ['FFMPEG.md','FFMPEG_KR.md','AGENTS.md','AGENTS_KR.md','CLAUDE.md','CLAUDE_KR.md']]
COPY_FILES+=['examples/scene_candidate.py','examples/claude_work.py']
COPY_FILES+=['docs/media-jobs-manual/'+n for n in ['README.md','README_KR.md','IMAGES.json','SCREENSHOTS.json','CLI_EXAMPLES.json']]
COPY_FILES+=['docs/media-jobs-manual/images/'+n for n in ['finder-handoff.jpg','finder-returned.jpg','finder-version.jpg','finder-revisions.jpg']]
COPY_FILES+=['docs/media-jobs-manual/images/'+n+'-'+lang+'.png' for n in ['01-request','02-review','03-adopt','04-revision'] for lang in ['en','ko']]


def canonical(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(32768),b''):h.update(chunk)
    return h.hexdigest()
def put(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)
def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('documentation_source_changed: '+old[:80])
    return text.replace(old,new,1)


def build(source,output,version):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?",version):raise ValueError("invalid_version")
    if version in PUBLISHED_VERSIONS:raise ValueError("published_version_immutable: use existing qualified release assets")
    VERSION=version;BASE_NAME="CALF-Video-Work-Management-Pack-"+VERSION
    source=Path(source);output=Path(output)
    if not source.is_absolute() or source.resolve(strict=True)!=source:raise ValueError('physical_source_required')
    if not output.is_absolute() or output.exists() or output.is_symlink():raise ValueError('new_build_folder_required')
    inputs=COPY_FILES+['README.md','README_KR.md','INSTALL.md','INSTALL_KR.md','specs/pack-v1/examples/ffmpeg.json','calf_extensions/media_jobs/verify_package.py']
    for name in inputs:
        path=source/name
        if not path.is_file() or path.is_symlink() or path.resolve()!=path or path.stat().st_size>8*1024*1024:
            raise ValueError('invalid_allowlisted_source: '+name)
    output.mkdir(parents=True,exist_ok=False);payload=output/BASE_NAME;payload.mkdir()
    source_hashes={name:sha(source/name) for name in sorted(set(inputs))}
    for name in COPY_FILES:put(payload/name,(source/name).read_bytes())
    put(payload/'VERIFY_PACKAGE.py',(source/'calf_extensions/media_jobs/verify_package.py').read_bytes())
    # Public guides have their own stable locations; do not slice repository landing pages.
    for lang,name,install in [('en','README.md','INSTALL.md'),('ko','README_KR.md','INSTALL_KR.md')]:
        title='# CALF Video Work Management Pack '+VERSION+'\n\n'
        links=('[한국어](README_KR.md) · [Install first](INSTALL.md) · [User guide](docs/media-jobs-manual/README.md)' if lang=='en' else '[English](README.md) · [처음 설치하기](INSTALL_KR.md) · [사용 매뉴얼](docs/media-jobs-manual/README_KR.md)')
        intro=('Manage external video handoffs, returns and revisions. CALF native/SDK and FFmpeg are separate. Run `python3 -B VERIFY_PACKAGE.py` to check payload identity.\n' if lang=='en' else '외부 영상 요청·반환·재수정을 관리합니다. CALF 실행기·SDK와 FFmpeg는 별도로 준비합니다. `python3 -B VERIFY_PACKAGE.py`로 포함 파일의 신원을 확인하세요.\n')
        put(payload/name,(title+links+'\n\n'+intro).encode())
        text=(source/install).read_text(encoding='utf-8')
        text='\n'.join(line for line in text.split('\n') if not (line.startswith('|') and ('Repository Navigator' in line or 'docs/PACKS_GUIDE' in line)))
        text=text.replace('CALF-Extensions/',BASE_NAME+'/').replace('/absolute/path/to/CALF-Extensions','/absolute/path/to/'+BASE_NAME).replace('C:\\Work\\CALF-Extensions','C:\\Work\\'+BASE_NAME)
        # Published download links identify the existing release; candidate version is in pack.json.
        put(payload/install,text.encode())
    for name in ['FFMPEG.md','FFMPEG_KR.md']:
        path=payload/'docs'/name;text=path.read_text(encoding='utf-8')
        if name=='FFMPEG.md':
            text=text.replace('Optional local installation with existing setuptools is `python -m pip install --no-build-isolation --no-deps .`; install the separate SDK into that environment as well.','This portable media-work pack runs from its retained directory; pip installation is not part of its setup.')
        else:
            text=text.replace('setuptools가 있는 별도 환경에서는 `python -m pip install --no-build-isolation --no-deps .`로 로컬 설치할 수도 있습니다. 같은 환경에 별도 SDK도 준비해야 합니다.','이 포터블 영상 관리 팩은 보존한 폴더에서 직접 실행하며 pip 설치를 요구하지 않습니다.')
        path.write_text(text,encoding='utf-8')
    metadata=json.loads((source/'specs/pack-v1/examples/ffmpeg.json').read_text())
    metadata.update(id=PACK_ID,version=VERSION,availability='candidate',channel='preview',summary={'en':'Manage external video requests and byte-preserved returns using existing CALF scene checks.','ko':'외부 영상 요청과 무변환 반환본을 기존 CALF 씬 검사·채택으로 관리합니다.'})
    metadata['entryPoints'][0]['target']='calf_extensions.media_jobs.cli:main'
    metadata['entryPoints'][1]['target']='calf_extensions.media_jobs.manager'
    metadata['modes'][0]['id']='handoffs'
    metadata['resources']['limitsDocument']='calf_extensions/media_jobs/README.md'
    metadata['documentation']={'en':'README.md','ko':'README_KR.md'}
    metadata['verification']['specification']='INSTALL.md'
    metadata['verification']['runtimeEvidence']=['VERIFICATION.json']
    metadata['recovery']['specification']='calf_extensions/media_jobs/README.md'
    put(payload/'pack.json',canonical(metadata))
    put(payload/'qualification.json',canonical({'schema':'calf.pack.candidate.v1','lifecycleStatus':'NOT_RUN','installation':'portable-source','packStoreDriver':'not supplied','note':'Run the included INSTALL instructions for local qualification. No activation of an existing store is performed.'}))
    put(payload/'VERIFICATION.json',canonical({'schema':'calf.media.jobs.distribution-scope.v1','packId':PACK_ID,'version':VERSION,'status':'LOCAL_INSTALL_CHECK_REQUIRED','command':'python3 -B -m calf_extensions.media_jobs.verify','scope':'This payload is immutable. Final archive-specific macOS results are supplied in the accompanying VERIFICATION-REPORT.json; local machine checks remain required.','untested':['Windows/Linux execution of this added pack','4K throughput','production footage','provider API calls','real external agent clients'],'checks':'Fresh local installation executes the documented synthetic acceptance suite; no model or API key is required.'}))
    put(payload/'RELEASE-NOTES.md',('# Video Work Management Pack '+VERSION+'\n\nPortable preview containing external handoff/intake management, bilingual first-time installation and actual Finder/Quick Look captures. Native CALF, SDK and media tools are separate. Existing work is preserved; no PackStore activation, provider call or global setup runs during extraction.\n').encode())
    files=sorted(p for p in payload.rglob('*') if p.is_file())
    if len(files)>1024 or sum(p.stat().st_size for p in files)>32*1024*1024:raise ValueError('payload_limit')
    put(payload/'FILES.sha256',''.join(sha(p)+'  '+p.relative_to(payload).as_posix()+'\n' for p in files).encode())
    for name,h in source_hashes.items():
        if sha(source/name)!=h:raise ValueError('source_changed_during_build')
    archive=output/(BASE_NAME+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in payload.rglob('*') if p.is_file()):
            info=zipfile.ZipInfo(BASE_NAME+'/'+path.relative_to(payload).as_posix(),(2026,11,7,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            with path.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,32768)
    tar_path=output/(BASE_NAME+'.tar.gz')
    with tar_path.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(p for p in payload.rglob('*') if p.is_file()):
            info=tarfile.TarInfo(BASE_NAME+'/'+path.relative_to(payload).as_posix());info.size=path.stat().st_size;info.mode=0o644;info.mtime=0
            with path.open('rb') as src:tar.addfile(info,src)
    artifacts={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in [archive,tar_path]}
    put(output/'SHA256SUMS',''.join(row['sha256']+'  '+name+'\n' for name,row in artifacts.items()).encode())
    result={'id':PACK_ID,'version':VERSION,'payload':str(payload),'files':len(files)+1,'artifacts':artifacts,'sourceFiles':source_hashes,'activationChanged':False}
    put(output/'build.json',canonical(result));return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',required=True,help='New candidate version; published versions cannot be rebuilt')
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.version),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
