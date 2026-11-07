"""Manage manual video-tool handoffs and returned candidates through CALF."""
import argparse
import json
from pathlib import Path
import sys
from calf_sdk import CalfClient, CalfError
from calf_extensions.media_ffmpeg.common import read_json, regular
from .manager import register, prepare, receive, run, adopt, reconcile, inspect_job, inspect_jobs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--calf',type=Path);p.add_argument('--home',type=Path)
    sub=p.add_subparsers(dest='action',required=True)
    r=sub.add_parser('register')
    for flag in ['configuration','ffmpeg','ffprobe']:r.add_argument('--'+flag,type=Path,required=True)
    for action in ['request','receive','run','adopt','reconcile','status']:
        q=sub.add_parser(action);q.add_argument('--project',type=Path,required=True)
        q.add_argument('--key',required=action!='status')
        if action=='request':
            q.add_argument('--scene',required=True);q.add_argument('--brief',type=Path,required=True)
            q.add_argument('--profile',type=Path,required=True);q.add_argument('--tool',required=True)
            q.add_argument('--reference',type=Path,action='append',default=[]);q.add_argument('--parent')
        if action=='receive':
            q.add_argument('--file',type=Path,required=True);q.add_argument('--registration',type=Path,required=True)
    a=p.parse_args()
    try:
        needs_native=a.action not in ['request','status']
        if needs_native and (a.calf is None or a.home is None):p.error('this action requires --calf and --home')
        if (a.calf is None)!=(a.home is None):p.error('supply --calf and --home together')
        client=CalfClient(a.calf,a.home,timeout=80) if a.calf is not None else None
        if a.action=='register':value=register(client,a.configuration,a.ffmpeg,a.ffprobe)
        elif a.action=='request':
            brief=regular(a.brief,12000).read_text(encoding='utf-8')
            value=prepare(a.project,a.scene,a.key,brief,read_json(regular(a.profile,65536)),a.tool,
                          references=a.reference,parent=a.parent)
        elif a.action=='receive':value=receive(client,a.project,a.key,a.file,read_json(regular(a.registration,65536)))
        elif a.action=='status':value=inspect_job(client,a.project,a.key) if a.key else inspect_jobs(client,a.project)
        else:value={'run':run,'adopt':adopt,'reconcile':reconcile}[a.action](client,a.project,a.key)
        print(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
        return 2 if a.action=='run' and value.get('outcome')!='SATISFIED' else 0
    except (ValueError,OSError,KeyError,CalfError) as e:
        print(json.dumps({'error':type(e).__name__,'message':str(e)[:500]},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
