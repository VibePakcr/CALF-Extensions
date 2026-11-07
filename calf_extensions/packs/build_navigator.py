"""Build one runtime pack and a portable installer bundle; no global installation."""
import argparse,json,shutil,zipfile
from pathlib import Path
from .io import physical,sha,canonical,relative
from .metadata import manifest
from .navigator import PACK_ID,CHECKS

def archive(folder,path):
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if not p.is_file():continue
            info=zipfile.ZipInfo(p.relative_to(folder).as_posix(),(2026,11,7,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            with p.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,32768)

def copy(source,destination,name):
    relative(name);src=physical(source/name);before=sha(src);p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
    if sha(p)!=before or sha(src)!=before:raise ValueError('source_changed_during_build')

def build(source,output,version):
    source=physical(source,directory=True);output=Path(output);relative(version)
    if not output.is_absolute() or output.exists():raise ValueError('new_build_folder_required')
    output.mkdir(parents=True);payload=output/'payload';payload.mkdir();meta=json.loads((source/'specs/pack-v1/examples/navigator.json').read_text())
    meta.update(id=PACK_ID,version=version,availability='candidate',channel='experimental');meta['modes'][0]['status']='implemented'
    for entry in meta['entryPoints']:entry.update(status='implemented',targetKind='python-module',target='calf_extensions.repository.cli')
    names=['calf_extensions/__init__.py','LICENSE-EXTENSIONS.txt','LICENSE-SDK.txt','docs/NAVIGATOR_PACK.md','docs/NAVIGATOR_PACK_KR.md']
    names += [p.relative_to(source).as_posix() for p in (source/'calf_extensions/repository').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.html','.css','.js','.json'} and p.name!='pack_verify.py']
    for name in sorted(set(names)):copy(source,payload,name)
    (payload/'pack.json').write_bytes(canonical(meta)+b'\n');manifest(payload/'pack.json');(payload/'qualification.json').write_bytes(canonical({'schema':'calf.pack.candidate.v1','lifecycleStatus':'NOT_RUN','requiredChecks':CHECKS,'note':'Offline installation fixtures; actual provider/browser qualification is separate.'})+b'\n')
    (payload/'README.md').write_text('# CALF Repository Navigator\n\nFree preview. Local Git, GitHub and GitLab share one foreground map/code/Diff viewer.\n\n[English](docs/NAVIGATOR_PACK.md) · [한국어](docs/NAVIGATOR_PACK_KR.md)\n',encoding='utf8')
    files=sorted(p for p in payload.rglob('*') if p.is_file());(payload/'FILES.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(payload).as_posix()+'\n' for p in files),encoding='utf8')
    target=output/('CALF-Repository-Navigator-Pack-'+version+'.zip');archive(payload,target);result={'archive':str(target),'sha256':sha(target),'id':PACK_ID,'version':version};(output/'build.json').write_bytes(canonical(result)+b'\n');return result

def bundle(source,runtime,output,manuals=None):
    source=physical(source,directory=True);runtime=physical(runtime,directory=True);output=Path(output)
    if not output.is_absolute() or output.exists():raise ValueError('new_bundle_folder_required')
    output.mkdir(parents=True);build=json.loads((runtime/'build.json').read_text());pack=Path(build['archive']);assert sha(pack)==build['sha256'];(output/'packs').mkdir();shutil.copyfile(pack,output/'packs'/pack.name)
    names=['calf_extensions/__init__.py','LICENSE-EXTENSIONS.txt','LICENSE-SDK.txt','docs/NAVIGATOR_PACK.md','docs/NAVIGATOR_PACK_KR.md','docs/REPOSITORY_NAVIGATOR.md','docs/REPOSITORY_NAVIGATOR_KR.md'];names += [p.relative_to(source).as_posix() for p in (source/'calf_extensions/packs').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json'} and 'tests' not in p.parts]
    for name in names:copy(source,output,name)
    if manuals:shutil.copytree(physical(manuals,directory=True),output/'manuals')
    else:
        (output/'manuals').mkdir()
        for lang in ['en','ko']:(output/'manuals'/(lang+'.html')).write_text('<!doctype html><meta charset="utf-8"><title>CALF Navigator</title><h1>CALF Repository Navigator</h1><p>Illustrated guide is being prepared for this preview.</p>',encoding='utf8')
    from .navigator_install import START_SOURCE
    (output/'START_NAVIGATOR.py').write_text(START_SOURCE,encoding='utf8');(output/'README.txt').write_text('CALF Repository Navigator - free preview\n\n1. Python 3.10+ and Git 2.43+ are required.\n2. python START_NAVIGATOR.py install --home STORE --data-dir DATA --preview\n3. python START_NAVIGATOR.py open --home STORE\n\nOpen manuals/en.html or manuals/ko.html for illustrated instructions. No core, SDK, model or global installation is required.\n',encoding='utf8')
    return seal_bundle(output,build)

def seal_bundle(folder,build=None):
    folder=physical(folder,directory=True)
    if build is None:build=json.loads((folder/'bundle.json').read_text())['pack']
    else:build=dict(build,archive='packs/'+Path(build['archive']).name)
    files={p.relative_to(folder).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in {'bundle.json','SHA256SUMS'} and '__pycache__' not in p.parts}
    value={'schema':'calf.navigator.bundle.v1','pack':build,'files':files};(folder/'bundle.json').write_bytes(canonical(value)+b'\n');(folder/'SHA256SUMS').write_text(''.join(sha(folder/n)+'  '+n+'\n' for n in [*files,'bundle.json']),encoding='utf8');return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',default='0.1.0-dev.1');a=p.parse_args();print(json.dumps(build(a.source,a.output,a.version),indent=2))
if __name__=='__main__':main()
