"""Local pack lifecycle preview; explicit paths, no downloads or global settings."""
import argparse
import json
from pathlib import Path
import sys
from .io import PackError,read
from .metadata import manifest
from .store import PackStore

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--home',type=Path,help='explicit pack-store directory, separate from CALF records')
    sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('inspect');q.add_argument('--manifest',type=Path,required=True)
    sub.add_parser('init')
    q=sub.add_parser('stage');q.add_argument('--archive',type=Path,required=True);q.add_argument('--sha256',required=True);q.add_argument('--source',required=True)
    for name in ('check','qualify'):
        q=sub.add_parser(name);q.add_argument('--id',required=True);q.add_argument('--version',required=True);q.add_argument('--mode',required=True);q.add_argument('--environment',type=Path,required=True)
    for name in ('activate','rollback'):
        q=sub.add_parser(name);q.add_argument('--lock',required=True);q.add_argument('--expected-active',required=True);q.add_argument('--experimental',action='store_true')
    q=sub.add_parser('status');q.add_argument('--id',required=True)
    q=sub.add_parser('recover');q.add_argument('--acknowledge');q.add_argument('--cursor')
    q=sub.add_parser('repo-bind');q.add_argument('--repo',type=Path,required=True);q.add_argument('--data-dir',type=Path,required=True)
    for name in ('repo-run','repo-inspect','repo-export'):
        q=sub.add_parser(name);q.add_argument('--binding',type=Path,required=True)
        if name=='repo-export':q.add_argument('--output',type=Path,required=True);q.add_argument('--include-source',action='store_true')
    q=sub.add_parser('scene-request')
    for field in ('records','project','source','profile'):q.add_argument('--'+field,type=Path,required=True)
    for field in ('scene','key'):q.add_argument('--'+field,required=True)
    for name in ('scene-run','scene-adopt','scene-inspect','scene-reconcile'):
        q=sub.add_parser(name);q.add_argument('--binding',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.action=='inspect':result=manifest(a.manifest)
        elif a.action in ('repo-run','repo-inspect','repo-export'):
            from .repository import invoke
            result=invoke(a.binding,a.action[5:],getattr(a,'output',None),getattr(a,'include_source',False))
        elif a.action.startswith('scene-') and a.action!='scene-request':
            from .ffmpeg import invoke
            result=invoke(a.binding,a.action[6:])
        else:
            if a.home is None:p.error('--home is required for this action')
            store=PackStore.create(a.home) if a.action=='init' else PackStore(a.home)
            if a.action=='init':result={'store':str(store.root),'status':'CREATED'}
            elif a.action=='stage':result=store.stage(a.archive,a.sha256,a.source)
            elif a.action in ('check','qualify'):result=getattr(store,a.action)(a.id,a.version,a.mode,read(a.environment))
            elif a.action in ('activate','rollback'):result=store.activate(a.lock,a.expected_active,experimental=a.experimental)
            elif a.action=='status':
                result=store.active(a.id)
                if result['value']:
                    try:store.load_lock(result['value']['lock']);result['current']=True
                    except (OSError,PackError) as e:result.update(current=False,reason=str(e)[:300])
            elif a.action=='recover':result=store.recover(acknowledge=a.acknowledge,cursor=a.cursor)
            elif a.action=='repo-bind':
                from .repository import request
                result=request(store,repo=a.repo,data=a.data_dir)
            else:
                from .ffmpeg import request
                result=request(store,records=a.records,project=a.project,scene=a.scene,source=a.source,key=a.key,profile=read(a.profile))
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        if a.action=='check' and result.get('status')!='COMPATIBLE':return 2
        if a.action=='scene-run' and not (result.get('verified') and result.get('outcome')=='SATISFIED'):return 2
        if a.action=='status' and result.get('current') is False:return 2
        if a.action=='repo-run' and result.get('status')!='COMPLETE':return 2
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:600]},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
