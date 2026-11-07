"""Copied into each binding; launched explicitly with the pinned interpreter.

Only this file imports the selected SDK/media pack, after host identity checks.
No package command, shell string, settings source or model is accepted.
"""
import json
from pathlib import Path
import sys

def load(path):
    with Path(path).open('rb') as f:raw=f.read(65537)
    if len(raw)>65536:raise ValueError('binding_data_limit')
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('duplicate_key')
            d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs)

def main():
    folder=Path(__file__).resolve().parent;binding=load(folder/'binding.json');lock=load(binding['lockFile'])
    env=lock['compatibility']['environment'];sys.path[:0]=[lock['packRoot'],env['sdk']]
    from calf_sdk import CalfClient
    from calf_extensions.media_ffmpeg.integration import register,prepare_scene,run_scene,reconcile_request
    from calf_extensions.media_ffmpeg.project import adopt_scene
    base=CalfClient(env['calf'],binding['records'],timeout=80)
    class BoundClient:
        def work(self,action,**fields):
            if action=='register':
                fields['adapter']['command'][2:2]=['-X','utf8']
                fields['adapter']['files']+=list(map(str,[folder/'binding.json',folder/'request.json',Path(binding['lockFile']),Path(__file__)]))
            return base.work(action,**fields)
    client=BoundClient();request=load(folder/'request.json');action=sys.argv[1]
    ticket_file=folder/'ticket.json'
    if action=='request':
        if ticket_file.exists():return load(ticket_file)
        configuration=folder/'configuration'
        if configuration.exists():registration=load(configuration/'registration.json')
        else:registration=register(client,configuration,Path(env['ffmpeg']),Path(env['ffprobe']))
        ticket=prepare_scene(client,binding['project'],request['scene'],request['source'],registration,request['key'],request['profile'])
    elif action=='reconcile':
        ticket=reconcile_request(client,binding['project'],request['key'])
    else:
        ticket=load(ticket_file)
        if action=='run':run_scene(client,ticket)
        elif action=='adopt':return adopt_scene(client,binding['project'],ticket)
        elif action!='inspect':raise ValueError('unsupported_bound_action')
        return base.work('inspect',work=ticket['work'])
    # A lost reply can be reconciled from the persisted project request, never resubmitted.
    if not ticket_file.exists():
        with ticket_file.open('x',encoding='utf8') as f:json.dump(ticket,f,ensure_ascii=False,allow_nan=False)
    return ticket

if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False,allow_nan=False))
