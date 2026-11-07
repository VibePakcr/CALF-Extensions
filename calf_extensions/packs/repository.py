"""Local Git driver and immutable work binding; no native/media dependency."""
from pathlib import Path
import re
import uuid
from .io import PackError,physical,sha,decode,run,read,digest,atomic,mutex,token
from .metadata import in_range

PACK_ID='calf.repository.local-git'

def observe(package,metadata,mode,environment,report):
    if mode['id']!='inspect' or mode['status']!='implemented':report['reasons'].append('driver_not_implemented');return report
    if set(mode['dependencies'])!={'python','git'}:
        report['reasons'].append('repository_dependency_contract_mismatch');return report
    if set(environment)!={'python','git'}:raise PackError('explicit_repository_environment_required')
    dependencies={d['id']:d for d in metadata['dependencies']}
    known={'python':{'stdlib','utf8'},'git':{'read-only-contract','no-lazy-fetch','sha1-and-sha256-objects'}}
    for key in mode['dependencies']:
        row={'id':key,'status':'UNKNOWN'}
        try:
            if key not in known:raise PackError('dependency_driver_not_implemented')
            tool=physical(environment[key]);report['fingerprints'][str(tool)]=sha(tool)
            if key=='python':
                data=decode(run([tool,'-I','-S','-B','-X','utf8','-c','import sys,json;print(json.dumps({"version":".".join(map(str,sys.version_info[:3])),"utf8":sys.stdout.encoding}))']))
                version=data['version'];features={'stdlib','utf8'} if data['utf8'].lower()=='utf-8' else {'stdlib'}
                row['featureBasis']='selected interpreter output'
            else:
                text=run([tool,'--version'],limit=65536).decode('ascii')
                match=re.fullmatch(r'git version (\d+\.\d+(?:\.\d+)?)(?:[^\r\n]*)\s*',text)
                if not match:raise PackError('unrecognized_git_version')
                version=match[1];features=known[key]
                row['featureBasis']='fixed read-only driver policy and supported Git version; local behavior must pass qualification'
            supported={'python':{'minInclusive':'3.10.0','maxExclusive':'4.0.0'},'git':{'minInclusive':'2.43.0','maxExclusive':'3.0.0'}}
            row.update(version=version,features=sorted(features),status='COMPATIBLE' if in_range(version,dependencies[key]['versionRange']) and in_range(version,supported[key]) else 'INCOMPATIBLE')
            if set(dependencies[key]['requiredFeatures'])-features:row.update(status='UNKNOWN',reason='capability_not_supported')
        except FileNotFoundError:row.update(status='INCOMPATIBLE',reason='dependency_missing')
        except (OSError,ValueError,KeyError,TypeError) as error:row.update(status='UNKNOWN',reason=str(error)[:160])
        report['dependencies'].append(row)
    if mode['supervised'] or mode['network']!='none':report['reasons'].append('unsupported_repository_mode')
    states=[r['status'] for r in report['dependencies']]
    report['status']='INCOMPATIBLE' if 'INCOMPATIBLE' in states else 'UNKNOWN' if 'UNKNOWN' in states or report['reasons'] else 'COMPATIBLE'
    report['qualificationRequired']=True
    try:changed=any(sha(p)!=h for p,h in report['fingerprints'].items())
    except OSError:changed=True
    if changed:report.update(status='UNKNOWN');report['reasons'].append('dependency_changed_during_probe')
    return report

def request(store,*,repo,data):
    repo=physical(repo,directory=True);data=physical(data,directory=True)
    if data.is_relative_to(repo) or data==repo:raise PackError('repository_data_outside_source_required')
    if any(p.is_relative_to(store.root) or store.root.is_relative_to(p) for p in (repo,data)):raise PackError('repository_data_outside_pack_store_required')
    with mutex(store.root):
        active=store.active(PACK_ID)['value']
        if active is None:raise PackError('no_active_pack')
        lock=store.load_lock(active['lock'])
        if lock['mode']!='inspect':raise PackError('repository_inspect_lock_required')
        folder=store.root/'bindings'/uuid.uuid4().hex;folder.mkdir()
        worker=folder/'worker.py';worker.write_bytes(Path(__file__).with_name('repository_worker.py').read_bytes())
        value={'schema':'calf.repository.binding.v1','store':str(store.root),'lock':active['lock'],'repo':str(repo),'data':str(data),'workerSha256':sha(worker)}
        atomic(folder/'request.json',value,new=True)
        atomic(folder/'binding.json',{'requestSha256':sha(folder/'request.json')},new=True)
        return {'binding':str(folder/'binding.json'),'lock':active['lock'],'status':'BOUND','packVersion':lock['version']}

def load(binding):
    from .store import PackStore
    binding=physical(binding);folder=binding.parent
    if binding.name!='binding.json' or sha(folder/'request.json')!=read(binding)['requestSha256']:raise PackError('repository_binding_changed')
    value=read(folder/'request.json');store=PackStore(value['store'])
    if folder.parent!=store.root/'bindings' or not re.fullmatch('[0-9a-f]{32}',folder.name):raise PackError('repository_binding_location')
    if value['schema']!='calf.repository.binding.v1' or sha(folder/'worker.py')!=value['workerSha256']:raise PackError('repository_worker_changed')
    lock=store.load_lock(value['lock'])
    if lock['id']!=PACK_ID or lock['mode']!='inspect':raise PackError('repository_inspect_lock_required')
    return folder,value,store,lock

def inspect(binding):
    folder,value,store,lock=load(binding)
    if not (folder/'receipt.json').exists():return {'status':'UNKNOWN' if (folder/'started.json').exists() else 'READY','binding':str(binding),'lock':value['lock']}
    receipt=read(folder/'receipt.json');cid=token(receipt['capture'])
    if receipt['requestSha256']!=sha(folder/'request.json'):raise PackError('repository_receipt_identity')
    data=physical(value['data'],directory=True)
    capture=data/'captures'/(cid+'.json');graph=data/'navigation'/(cid+'.json')
    if sha(capture)!=cid or sha(graph)!=receipt['navigationSha256']:raise PackError('repository_evidence_changed')
    captured=read(capture,32*1024*1024);mapped=read(graph,32*1024*1024)
    expected_status='COMPLETE' if captured['coverage']['state']=='COMPLETE' else 'PARTIAL'
    if (receipt.get('schema')!='calf.repository.receipt.v1' or receipt['status']!=expected_status
        or receipt['coverage']!=captured['coverage'] or mapped['capture']['capture_id']!=cid
        or mapped['graph']['capture_id']!=cid or mapped['graph']['coverage']!=receipt['navigationCoverage']):raise PackError('repository_receipt_content_mismatch')
    available=sorted({r['sha256'] for r in mapped['graph']['source_captures'].values() if r.get('sha256') and (data/'sources'/r['sha256']).is_file()})
    if receipt['sourceDigests']!=available:raise PackError('repository_source_inventory_mismatch')
    for key in receipt['sourceDigests']:
        token(key)
        if sha(data/'sources'/key)!=key:raise PackError('repository_source_changed')
    active=store.active(PACK_ID)['value']
    return {'status':receipt['status'],'capture':cid,'lock':value['lock'],'packVersion':lock['version'],'receipt':str(folder/'receipt.json'),
            'receiptSha256':sha(folder/'receipt.json'),'coverage':receipt['coverage'],'navigationCoverage':receipt['navigationCoverage'],
            'sameActivePack':active is not None and active['lock']==value['lock']}

def invoke(binding,action,output=None,include_source=False):
    folder,value,store,lock=load(binding)
    if action=='inspect':return inspect(binding)
    with mutex(store.root):
        if action=='run' and (folder/'receipt.json').exists():return inspect(binding)
        if action=='run':
            if (folder/'started.json').exists():raise PackError('repository_attempt_unresolved_inspect_before_retry')
            atomic(folder/'started.json',{'requestSha256':sha(folder/'request.json'),'lock':value['lock']},new=True)
        elif action=='export':
            if inspect(binding)['status'] not in ('COMPLETE','PARTIAL'):raise PackError('repository_capture_required')
            if output is None or not Path(output).is_absolute():raise PackError('explicit_export_path_required')
        else:raise PackError('repository_action_invalid')
        env=lock['compatibility']['environment']
        argv=[env['python'],'-I','-S','-B','-X','utf8',str(folder/'worker.py'),lock['packRoot'],str(folder/'request.json'),action]
        if action=='export':argv += [str(output),'include-source' if include_source else 'metadata-only']
        run(argv,timeout=120,limit=1048576,cwd=folder)
        # Validate the exact retained files independently of worker stdout/exit.
        if action=='run':return inspect(binding)
        manifest=read(Path(output)/'MANIFEST.json');capture=inspect(binding)['capture']
        if (manifest['capture_id']!=capture or set(manifest['files'])!={'START_HERE.html','project-navigation.json'}
            or manifest['coverage']['source_included']!=include_source
            or any(sha(Path(output)/name)!=expected for name,expected in manifest['files'].items())):raise PackError('repository_export_identity')
        return {'status':'EXPORTED','output':str(output),'manifestSha256':sha(Path(output)/'MANIFEST.json'),'capture':capture}
