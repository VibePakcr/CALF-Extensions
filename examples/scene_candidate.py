"""Create/check one scene candidate; adoption requires an explicit --adopt."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calf_sdk import CalfClient
from calf_extensions.media_ffmpeg.common import read_json, regular
from calf_extensions.media_ffmpeg.integration import prepare_scene, run_scene
from calf_extensions.media_ffmpeg.project import adopt_scene


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['calf','home','project','source','registration','profile']:
        p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--scene',required=True);p.add_argument('--key',required=True)
    p.add_argument('--adopt',action='store_true',help='caller explicitly authorizes selecting a technically validated candidate')
    a=p.parse_args();client=CalfClient(a.calf,a.home,timeout=80)
    ticket=prepare_scene(client,a.project,a.scene,a.source,read_json(regular(a.registration,65536)),a.key,read_json(regular(a.profile,65536)))
    result=run_scene(client,ticket)
    if a.adopt and result.get('outcome')=='SATISFIED':result=adopt_scene(client,a.project,ticket)
    print(json.dumps({'ticket':ticket,'result':result},ensure_ascii=False,indent=2))
    return 0 if result.get('outcome')=='SATISFIED' or 'selected' in result else 2

if __name__=='__main__':sys.exit(main())
