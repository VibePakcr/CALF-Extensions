"""Qualified foreground navigation; old Local Git inspect bindings are independent."""
import os
from pathlib import Path
import re
import signal
import subprocess
import uuid
from urllib.parse import urlsplit
from .io import PackError,physical,sha,read,canonical,digest,atomic,mutex,run

PACK_ID='calf.repository.navigator'
CHECKS=['local-contracts','source-contracts','hosted-contracts','portal-contracts']
DESTINATIONS=['https://api.github.com','https://gitlab.com']

def observe(package,metadata,mode,environment,report):
    if (mode['id']!='navigate' or mode['status']!='implemented' or mode['supervised']
        or mode['network']!='explicit-remote' or mode.get('remoteDestinations')!=DESTINATIONS
        or set(mode['effects'])!={'observe','export-capture'}):
        report['reasons'].append('navigator_mode_contract_mismatch');return report
    from .repository import observe as local_observe
    result=local_observe(package,metadata,dict(mode,id='inspect',network='none'),environment,report)
    result['networkPolicy']={'loopbackViewer':True,'registeredReadOnlyDestinations':DESTINATIONS,'automaticDiscovery':False}
    return result

def source_root(repo,git):
    repo=physical(repo,directory=True)
    value=run([git,'-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false','-C',str(repo),'rev-parse','--show-toplevel'],limit=65536).decode('utf8').strip()
    return physical(Path(value).resolve(strict=True),directory=True)

def bind(store,*,data,repo=None,project_map=None,manual_root=None):
    data=physical(data,directory=True);repo=physical(repo,directory=True) if repo else None
    if data.is_relative_to(store.root) or store.root.is_relative_to(data):raise PackError('workspace_outside_pack_store_required')
    if repo and (data.is_relative_to(repo) or repo.is_relative_to(store.root) or store.root.is_relative_to(repo)):raise PackError('workspace_outside_source_and_store_required')
    if manual_root:manual_root=physical(manual_root,directory=True)
    with mutex(store.root):
        active=store.active(PACK_ID)['value']
        if active is None:raise PackError('no_active_navigator')
        lock=store.load_lock(active['lock'])
        if lock['id']!=PACK_ID or lock['mode']!='navigate':raise PackError('navigator_lock_required')
        if repo:
            repo=source_root(repo,lock['compatibility']['environment']['git'])
            if data.is_relative_to(repo) or repo.is_relative_to(store.root) or store.root.is_relative_to(repo):raise PackError('workspace_outside_source_and_store_required')
        folder=store.root/'bindings'/uuid.uuid4().hex;folder.mkdir();worker=folder/'worker.py';worker.write_bytes(Path(__file__).with_name('navigator_worker.py').read_bytes())
        mapping=None
        if project_map:
            value=read(physical(project_map));mapping=folder/'project-map.json';atomic(mapping,value,new=True)
        request={'schema':'calf.navigator.binding.v1','store':str(store.root),'lock':active['lock'],'data':str(data),'repo':str(repo) if repo else None,'workerSha256':sha(worker),'projectMapSha256':sha(mapping) if mapping else None,'manualRoot':str(manual_root) if manual_root else None}
        atomic(folder/'request.json',request,new=True);atomic(folder/'binding.json',{'requestSha256':sha(folder/'request.json')},new=True);(folder/'runs').mkdir()
        return {'binding':str(folder/'binding.json'),'lock':active['lock'],'packVersion':lock['version'],'status':'BOUND'}

def load(binding):
    from .store import PackStore
    binding=physical(binding);folder=binding.parent
    if binding.name!='binding.json' or sha(folder/'request.json')!=read(binding)['requestSha256']:raise PackError('navigator_binding_changed')
    request=read(folder/'request.json');store=PackStore(request['store'])
    if folder.parent!=store.root/'bindings' or not re.fullmatch('[0-9a-f]{32}',folder.name) or request['schema']!='calf.navigator.binding.v1':raise PackError('navigator_binding_location')
    if sha(folder/'worker.py')!=request['workerSha256']:raise PackError('navigator_worker_changed')
    if request['projectMapSha256'] and sha(folder/'project-map.json')!=request['projectMapSha256']:raise PackError('navigator_mapping_changed')
    lock=store.load_lock(request['lock'])
    if lock['id']!=PACK_ID or lock['mode']!='navigate':raise PackError('navigator_lock_required')
    physical(request['data'],directory=True)
    if request['repo']:physical(request['repo'],directory=True)
    return folder,request,store,lock

def arguments(values):
    values=list(values)
    if values[:1]==['--']:values.pop(0)
    if not values or values[0] not in {'open','scan','probe','sources','export','--help'} or len(values)>100 or sum(len(v) for v in values)>16384:raise PackError('navigator_arguments_required')
    reserved=['--repo','--data-dir','--git','--project-map']
    for i,value in enumerate(values):
        key=value.split('=',1)[0]
        if key.startswith('--') and any(r.startswith(key) for r in reserved):raise PackError('use_a_new_binding_to_change_paths')
        if key in {'--token','--password','--credential'}:raise PackError('credential_reference_only')
        if key=='--url' or value.startswith('--url='):
            url=value.split('=',1)[1] if '=' in value else values[i+1] if i+1<len(values) else ''
            u=urlsplit(url)
            if u.scheme!='https' or u.hostname not in {'github.com','gitlab.com'} or u.username or u.password or u.query or u.fragment:raise PackError('registered_repository_url_required')
    return values

def child_environment(git):
    # Windows os.environ canonicalizes keys to uppercase, including SYSTEMROOT.
    allowed={'PATH','SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','TMPDIR','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','SSL_CERT_FILE','SSL_CERT_DIR'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    env['PATH']=str(Path(git).parent)+os.pathsep+os.defpath
    return env

def launch(binding,values,credential_env=()):
    folder,request,store,lock=load(binding);values=arguments(values);references={}
    for name in credential_env:
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',name) or name in references or len(references)>=8:raise PackError('credential_reference_invalid')
        if name.upper() in {'PATH','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','TMPDIR','BROWSER'} or name.upper().startswith(('PYTHON','GIT_','NODE_','LD_','DYLD_','SSL_')):raise PackError('operational_variable_is_not_a_credential_reference')
        value=os.environ.get(name)
        if not value or len(value)>8192 or not value.isascii() or any(ord(c)<33 or ord(c)==127 for c in value):raise PackError('credential_reference_missing_or_invalid')
        references[name]=value
    packet=canonical({'arguments':values,'credentialReferences':references})
    if len(packet)>65536:raise PackError('navigator_input_limit')
    with mutex(folder):
        run_folder=folder/'runs'/uuid.uuid4().hex;run_folder.mkdir();atomic(run_folder/'intent.json',{'schema':'calf.navigator.launch.v1','requestSha256':sha(folder/'request.json'),'argumentsSha256':digest(values),'command':values[0],'credentialReferenceNames':list(references)},new=True)
    env=child_environment(lock['compatibility']['environment']['git'])
    command=[lock['compatibility']['environment']['python'],'-I','-S','-B','-X','utf8',str(folder/'worker.py'),lock['packRoot'],str(folder/'request.json'),str(run_folder)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,env=env,start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
    try:
        try:process.stdin.write(packet);process.stdin.close()
        except (BrokenPipeError,OSError):pass
        try:code=process.wait()
        except KeyboardInterrupt:
            if os.name!='nt':os.killpg(process.pid,signal.SIGINT)
            else:process.send_signal(signal.CTRL_BREAK_EVENT)
            try:code=process.wait(timeout=15)
            except subprocess.TimeoutExpired:raise PackError('navigator_cleanup_unconfirmed')
    finally:
        if process.poll() is None:
            if os.name!='nt':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
            process.wait(timeout=5)
    store.load_lock(request['lock'])
    receipt=read(run_folder/'result.json') if (run_folder/'result.json').exists() else {'status':'UNKNOWN','exitCode':code}
    if receipt.get('requestSha256')!=sha(folder/'request.json'):raise PackError('navigator_exit_receipt_missing_or_changed')
    return {'binding':str(binding),'run':run_folder.name,'status':receipt['status'],'exitCode':code,'packVersion':lock['version'],'lock':request['lock']}

def inspect(binding):
    folder,request,store,lock=load(binding);runs=sorted((folder/'runs').iterdir(),key=lambda p:p.stat().st_mtime,reverse=True);items=[]
    for p in runs[:64]:
        if not re.fullmatch('[0-9a-f]{32}',p.name):raise PackError('invalid_navigator_run')
        intent=read(p/'intent.json');value=read(p/'result.json') if (p/'result.json').exists() else {'status':'UNKNOWN'}
        items.append({'run':p.name,'command':intent['command'],'status':value['status'],'exitCode':value.get('exitCode')})
    return {'binding':str(binding),'packVersion':lock['version'],'lock':request['lock'],'runs':items,'pageOnly':len(runs)>64}
