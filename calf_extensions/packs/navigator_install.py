"""Offline installer and foreground entry point for the free navigator bundle."""
import argparse,json
from pathlib import Path
import shutil,sys
from .io import PackError,physical,sha,read,atomic
from .store import PackStore
from .navigator import PACK_ID,bind,launch,inspect,source_root

START_SOURCE='''"""Verify the downloaded bundle, then run its local installer."""
import hashlib,json,sys
from pathlib import Path,PurePosixPath
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
try:
 raw=(root/'bundle.json').read_bytes()
 if len(raw)>1048576:raise ValueError('bundle manifest limit')
 meta=json.loads(raw)
 if meta['schema']!='calf.navigator.bundle.v1':raise ValueError('bundle schema')
 for name,expected in meta['files'].items():
  p=PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts or '\\\\' in name:raise ValueError('bundle path')
  path=root.joinpath(*p.parts)
  if path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('bundle integrity')
 sys.path.insert(0,str(root))
 from calf_extensions.packs.navigator_install import main
 raise SystemExit(main(root))
except (OSError,ValueError,KeyError):
 sys.stderr.write('Navigator bundle verification failed. Extract a trusted copy into a new folder.\\n')
 raise SystemExit(1)
'''

def main(bundle_root=None):
    root=physical(bundle_root or Path(__file__).parents[2],directory=True);meta=read(root/'bundle.json',1048576);p=argparse.ArgumentParser(description='CALF Repository Navigator - free local preview');sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('install');q.add_argument('--home',type=Path,required=True);q.add_argument('--data-dir',type=Path,required=True);q.add_argument('--python',type=Path);q.add_argument('--git',type=Path);q.add_argument('--repo',type=Path);q.add_argument('--preview',action='store_true');q.add_argument('--expected-active',default='none')
    q=sub.add_parser('open');q.add_argument('--home',type=Path);q.add_argument('--binding',type=Path);q.add_argument('--repo',type=Path);q.add_argument('--project-map',type=Path);q.add_argument('--credential-env',action='append',default=[]);q.add_argument('--no-browser',action='store_true')
    q=sub.add_parser('run');q.add_argument('--binding',type=Path,required=True);q.add_argument('--credential-env',action='append',default=[]);q.add_argument('arguments',nargs=argparse.REMAINDER)
    q=sub.add_parser('inspect');q.add_argument('--binding',type=Path,required=True)
    q=sub.add_parser('status');q.add_argument('--home',type=Path,required=True)
    q=sub.add_parser('rollback');q.add_argument('--home',type=Path,required=True);q.add_argument('--lock',required=True);q.add_argument('--expected-active',required=True);q.add_argument('--preview',action='store_true')
    a=p.parse_args()
    try:
        if a.action=='install':
            if not a.preview:raise PackError('explicit_preview_required')
            home=a.home.resolve();data=a.data_dir.resolve();python=(a.python or Path(sys.executable)).resolve(strict=True);git=(a.git or Path(shutil.which('git') or 'git')).resolve(strict=True);repo=source_root(a.repo.resolve(strict=True),git) if a.repo else None
            if data==home or data.is_relative_to(home) or home.is_relative_to(data) or repo and (data.is_relative_to(repo) or home.is_relative_to(repo) or repo.is_relative_to(home)):raise PackError('separate_workspace_and_store_required')
            data.mkdir(parents=True,exist_ok=True);physical(data,directory=True)
            store=PackStore(home) if home.exists() else PackStore.create(home);settings=home/'navigator.json'
            config={'data':str(data),'repo':str(repo) if repo else None}
            if settings.exists() and read(settings)!=config:raise PackError('existing_workspace_selection_must_be_preserved')
            pack=meta['pack'];archive=physical(root/pack['archive']);store.stage(archive,pack['sha256'],'verified-navigator-bundle')
            qualified=store.qualify(PACK_ID,pack['version'],'navigate',{'python':str(python),'git':str(git)})
            activated=store.activate(qualified['lock'],a.expected_active,experimental=True)
            data.mkdir(parents=True,exist_ok=True)
            if not settings.exists():atomic(settings,config,new=True)
            value={'status':'INSTALLED','home':str(home),'data':str(data),'version':pack['version'],'lock':qualified['lock'],'active':activated,'openCommand':['python','START_NAVIGATOR.py','open','--home',str(home)]}
        elif a.action=='open':
            if a.binding:binding=a.binding.resolve(strict=True)
            else:
                if a.home is None:raise PackError('home_or_binding_required')
                store=PackStore(a.home.resolve());settings=read(store.root/'navigator.json');r=bind(store,data=settings['data'],repo=a.repo.resolve(strict=True) if a.repo else settings['repo'],project_map=a.project_map.resolve(strict=True) if a.project_map else None,manual_root=root/'manuals');binding=Path(r['binding'])
            value=launch(binding,['open']+(['--no-browser'] if a.no_browser else []),a.credential_env);print(json.dumps(value,indent=2));return value['exitCode']
        elif a.action=='run':
            value=launch(a.binding.resolve(strict=True),a.arguments,a.credential_env);print(json.dumps(value,indent=2));return value['exitCode']
        elif a.action=='inspect':value=inspect(a.binding.resolve(strict=True))
        elif a.action=='status':value=PackStore(a.home.resolve()).active(PACK_ID)
        else:
            if not a.preview:raise PackError('explicit_preview_required')
            store=PackStore(a.home.resolve());lock=store.load_lock(a.lock)
            if lock['id']!=PACK_ID:raise PackError('navigator_lock_required')
            value=store.activate(a.lock,a.expected_active,experimental=True)
        print(json.dumps(value,indent=2));return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps({'status':'FAILED','error':str(error)[:200]}),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
