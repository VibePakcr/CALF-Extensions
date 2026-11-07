"""Bind new media work once; later operations use the retained binding."""
from pathlib import Path
from .io import PackError,read,physical,sha,atomic,run,decode
from .store import PackStore

def request(store,*,records,project,scene,source,key,profile):
    binding=store.bind('calf.media.ffmpeg',records=records,project=project)
    atomic(binding.parent/'request.json',{'scene':scene,'source':str(physical(source)),'key':key,'profile':profile},new=True)
    return {'binding':str(binding),'result':invoke(binding,'request')}

def invoke(binding,action):
    if action not in ('request','run','adopt','inspect','reconcile'):raise PackError('unsupported_bound_action')
    path=physical(binding);value=read(path);store=PackStore(value['store'])
    if path.name!='binding.json' or path.parent.parent!=store.root/'bindings':raise PackError('binding_outside_store')
    lock=store.load_lock(value['lock'])
    if value['lockFile']!=str(store.root/'locks'/(value['lock']+'.json')) or value['workerSha256']!=sha(path.parent/'worker.py'):raise PackError('binding_identity_changed')
    raw=run([lock['compatibility']['environment']['python'],'-I','-S','-B','-X','utf8',str(path.parent/'worker.py'),action],timeout=100,limit=1048576,cwd=path.parent)
    return decode(raw)
