"""Small explicit CLI for the FFmpeg scene extension preview."""
import argparse
import json
import sys
from pathlib import Path
from .common import read_json, regular
from .integration import register, prepare_scene, run_scene, reconcile_request
from .project import create_project, inspect_project, adopt_scene, select_version
from calf_sdk import CalfClient, CalfError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calf',type=Path,help='absolute path to the native CALF executable')
    parser.add_argument('--home',type=Path,help='explicit CALF records folder; never inferred')
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('register');p.add_argument('--configuration',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,required=True);p.add_argument('--ffprobe',type=Path,required=True)
    p=sub.add_parser('init');p.add_argument('--project',type=Path,required=True);p.add_argument('--scenes',nargs='+',required=True)
    p=sub.add_parser('request');p.add_argument('--project',type=Path,required=True)
    p.add_argument('--scene',required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--registration',type=Path,required=True);p.add_argument('--key',required=True)
    p.add_argument('--profile',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--ticket',type=Path,required=True)
    p=sub.add_parser('adopt');p.add_argument('--project',type=Path,required=True);p.add_argument('--ticket',type=Path,required=True)
    p=sub.add_parser('reconcile');p.add_argument('--project',type=Path,required=True);p.add_argument('--key',required=True)
    p=sub.add_parser('inspect');p.add_argument('--project',type=Path,required=True)
    p=sub.add_parser('restore');p.add_argument('--project',type=Path,required=True)
    p.add_argument('--scene',required=True);p.add_argument('--version',required=True);p.add_argument('--expected-manifest',required=True)
    args=parser.parse_args()
    def load(path):return read_json(regular(path,65536))
    try:
        if args.action in ['register','request','run','adopt','reconcile']:
            if args.calf is None or args.home is None:parser.error('this action requires --calf and --home')
            client=CalfClient(args.calf,args.home,timeout=80)
        if args.action=='register':value=register(client,args.configuration,args.ffmpeg,args.ffprobe)
        elif args.action=='init':value=create_project(args.project,args.scenes)
        elif args.action=='request':value=prepare_scene(client,args.project,args.scene,args.source,load(args.registration),args.key,load(args.profile))
        elif args.action=='run':value=run_scene(client,load(args.ticket))
        elif args.action=='adopt':value=adopt_scene(client,args.project,load(args.ticket))
        elif args.action=='reconcile':value=reconcile_request(client,args.project,args.key)
        elif args.action=='inspect':value=inspect_project(args.project)
        else:value=select_version(args.project,args.scene,args.version,expected_manifest=args.expected_manifest)
        print(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
        if args.action=='run' and value.get('outcome')!='SATISFIED':return 2
        return 0
    except (ValueError,OSError,KeyError,CalfError) as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:500]},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
