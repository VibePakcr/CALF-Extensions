"""Request/result transport. Native CALF and the existing selector own execution/adoption."""
import os
from pathlib import Path
import sys
import calf_sdk
from calf_sdk.work import adapter_descriptor, input_reference
from calf_extensions.media_ffmpeg.common import (regular, read_json, sha, digest, canonical,
                                                 MAX_MEDIA_BYTES, MediaError, toolchain)
from calf_extensions.media_ffmpeg.project import (root_path, name, locked, json_new,
    write_new, inspect_project, adopt_scene)
from calf_extensions.media_ffmpeg.integration import run_scene
from .contracts import delivery_profile, text


def _copy(source,target,reference):
    total=0
    with source.open('rb') as src,target.open('xb') as dst:
        for block in iter(lambda:src.read(32768),b''):
            total+=len(block)
            if total>MAX_MEDIA_BYTES:raise MediaError('snapshot_size_limit')
            dst.write(block)
        dst.flush();os.fsync(dst.fileno())
    if sha(target)!=reference['sha256'] or sha(source)!=reference['sha256']:
        raise MediaError('snapshot_changed_during_copy')
    target.chmod(0o444)


def register(client,configuration,ffmpeg,ffprobe):
    """Explicitly pin a new intake adapter; never rewrite old registrations."""
    folder=Path(configuration)
    if not folder.is_absolute() or folder.exists() or folder.is_symlink():raise MediaError('new_configuration_folder_required')
    tools={'schema':'calf.media.ffmpeg.toolchain.v1'}
    for key,path in [('ffmpeg',ffmpeg),('ffprobe',ffprobe)]:
        path=regular(Path(path).resolve(strict=True),128*1024*1024)
        tools[key]={'path':str(path),'sha256':sha(path)}
    folder.mkdir(parents=True,exist_ok=False);folder=root_path(folder)
    config=folder/'toolchain.json';json_new(config,tools);toolchain(config)
    here=Path(__file__).resolve().parent;sdk=Path(calf_sdk.__file__).resolve().parent
    files=[here/n for n in ['__init__.py','contracts.py','worker.py']]
    files += [here.parent/'media_ffmpeg'/n for n in ['common.py','validator.py']]
    files += [sdk/n for n in ['__init__.py','client.py','adapter.py','work.py']]
    files += [config,Path(tools['ffmpeg']['path']),Path(tools['ffprobe']['path'])]
    python=Path(sys.executable).resolve(strict=True)
    identity=digest({'files':[{'path':str(p),'sha256':sha(p)} for p in files],
                     'python':{'path':str(python),'sha256':sha(python)}})[:24]
    registration={'schema':'calf.media.jobs.registration.v1','executor':'intake-'+identity,
                  'validator':'intake-check-'+identity,'configuration':str(config)}
    for role,key in [('executor','executor'),('validator','validator')]:
        client.work('register',adapter=adapter_descriptor(registration[key],
            [str(python),'-B',str(here/'worker.py'),str(sdk.parent),str(config)],files,role=role,resource_class='light'))
    json_new(folder/'registration.json',registration)
    return registration


def _folder(project,key):
    root=root_path(project);name(key);folder=root/'handoffs'/key
    if folder.resolve()!=folder:raise MediaError('handoff_path_changed')
    return root,folder


def _request(folder):
    request=read_json(regular(folder/'request.json',65536))
    if request.get('schema')!='calf.media.handoff.v1' or request.get('key')!=folder.name:
        raise MediaError('handoff_identity')
    for ref in request['references']:
        path=regular(ref['path'])
        if path.parent!=folder/'references' or sha(path)!=ref['sha256']:raise MediaError('reference_snapshot_changed')
    return request


def _returned(folder):
    record=read_json(regular(folder/'returned.json',65536));path=regular(folder/'returned.mp4')
    if record['sha256']!=sha(path) or record['bytes']!=path.stat().st_size:raise MediaError('returned_snapshot_changed')
    return record,path


def _ticket(folder):
    value=read_json(regular(folder/'ticket.json',65536))
    if value['handoffSha256']!=sha(folder/'request.json'):raise MediaError('handoff_changed_after_submit')
    return value


def prepare(project,scene,key,instructions,expected,tool_label,*,references=(),parent=None):
    """One reusable handoff, not a claim that a provider has received the job."""
    root,folder=_folder(project,key);name(scene)
    text(instructions,12000,'instructions_required');text(tool_label,160,'tool_label_required')
    expected=delivery_profile(expected)
    references=list(references)
    if len(references)>8:raise MediaError('reference_count')
    refs=[input_reference(regular(Path(p).resolve(strict=True)),str(i),'application/octet-stream') for i,p in enumerate(references)]
    if parent is not None:name(parent)
    intent={'sceneId':scene,'instructions':instructions,'expected':expected,'toolLabel':tool_label,'parent':parent,'references':refs}
    with locked(root):
        current=inspect_project(root)
        if scene not in current['manifest']['scenes']:raise MediaError('unknown_scene')
        if folder.exists():
            if read_json(regular(folder/'intent.json',65536))!=intent:raise MediaError('request_key_conflict')
            if not (folder/'request.json').exists():raise MediaError('incomplete_handoff_reconcile')
            return _request(folder)
        if parent is not None:
            _,parent_folder=_folder(root,parent);previous=_request(parent_folder)
            if previous['sceneId']!=scene or previous['projectId']!=current['manifest']['projectId']:
                raise MediaError('parent_scope_mismatch')
            if not refs and (parent_folder/'returned.json').exists():
                _,path=_returned(parent_folder);refs=[input_reference(path,'0','video/mp4')]
        if not refs and scene in current['selected']:
            refs=[input_reference(current['selected'][scene]['path'],'0','video/mp4')]
        base=root/'handoffs'
        if not base.exists():base.mkdir()
        if base.resolve()!=base:raise MediaError('handoff_path_changed')
        folder.mkdir();json_new(folder/'intent.json',intent);(folder/'references').mkdir()
        snapshots=[]
        for i,ref in enumerate(refs):
            source=regular(ref['path']);suffix=source.suffix.lower()
            if suffix not in ['.mp4','.mov','.png','.jpg','.jpeg','.webp']:suffix='.bin'
            target=folder/'references'/(str(i)+suffix);_copy(source,target,ref)
            snapshots.append({**ref,'id':str(i),'path':str(target),'originalPath':ref['path']})
        request={'schema':'calf.media.handoff.v1','key':key,'projectId':current['manifest']['projectId'],
                 'sceneId':scene,'baseManifestDigest':current['digest'],'baseVersion':current['manifest']['scenes'][scene],
                 'parent':parent,'toolLabel':tool_label,'instructions':instructions,'expected':expected,'references':snapshots}
        if len(canonical(request))>65536:raise MediaError('handoff_size_limit')
        json_new(folder/'request.json',request)
        brief=('Tool: '+tool_label+'\nScene: '+scene+'\nRequest: '+key+'\n\n'+instructions+
               '\n\nDelivery requirements (no conversion on intake):\n'+canonical(expected).decode()+
               '\n\nReference snapshots:\n'+'\n'.join(ref['path'] for ref in snapshots)+'\n')
        write_new(folder/'handoff.txt',brief.encode('utf-8'))
        return request


def _make_ticket(folder,result):
    spec=read_json(regular(folder/'spec.json',65536));plan=read_json(regular(folder/'scene-plan.json',65536))
    return {'schema':'calf.media.scene-ticket.v1','work':result['work'],'contractDigest':result['contractDigest'],
            'sceneId':plan['sceneId'],'projectId':plan['projectId'],'baseManifestDigest':plan['baseManifestDigest'],
            'scopeSha256':sha(folder/'scene-plan.json'),'profile':spec['parameters']['profile'],
            'executor':spec['adapter'],'validator':spec['checks'][0]['rule']['adapter'],
            'handoffSha256':spec['parameters']['handoffSha256']}


def receive(client,project,key,source,registration):
    """Freeze one result; submit a native byte-copy/check work once. Never adopt."""
    root,folder=_folder(project,key);source=regular(Path(source).resolve(strict=True));source_sha=sha(source)
    if registration.get('schema')!='calf.media.jobs.registration.v1':raise MediaError('intake_registration_required')
    with locked(root):
        request=_request(folder);current=inspect_project(root)
        if request['projectId']!=current['manifest']['projectId']:raise MediaError('request_project_mismatch')
        if (folder/'returned.json').exists():
            record,snapshot=_returned(folder)
            if record['sha256']!=source_sha or record['registration']!=registration:raise MediaError('returned_result_conflict')
        else:
            if (folder/'returned.mp4').exists():raise MediaError('incomplete_return_reconcile')
            snapshot=folder/'returned.mp4';_copy(source,snapshot,{'sha256':source_sha})
            json_new(folder/'returned.json',{'schema':'calf.media.returned.v1','originalPath':str(source),
                'sha256':source_sha,'bytes':snapshot.stat().st_size,'registration':registration})
        if (folder/'ticket.json').exists():return _ticket(folder)
        if (folder/'spec.json').exists():raise MediaError('submission_uncertain_reconcile')
        plan={'schema':'calf.media.scene-plan.v1','projectId':request['projectId'],
              'sceneId':request['sceneId'],'baseManifestDigest':request['baseManifestDigest'],'sourceSha256':source_sha}
        if (folder/'scene-plan.json').exists():raise MediaError('incomplete_submission_reconcile')
        json_new(folder/'scene-plan.json',plan);scope_sha=sha(folder/'scene-plan.json')
        spec={'schema':'calf.work.v1','key':'handoff-'+request['projectId']+'-'+key,
              'title':'Returned scene '+request['sceneId']+' / '+key,'adapter':registration['executor'],
              'parameters':{'profile':request['expected'],'handoffSha256':sha(folder/'request.json')},
              'inputs':[input_reference(snapshot,'source','video/mp4'),input_reference(folder/'scene-plan.json','scene-plan','application/json')],
              'outputs':[{'id':'video','path':'video.mp4','mediaType':'video/mp4','minBytes':1,'maxBytes':MAX_MEDIA_BYTES}],
              'checks':[{'id':'media-technical','artifact':'video','kind':'adapter',
                         'rule':{'adapter':registration['validator'],'parameters':{'expected':request['expected'],'scopeSha256':scope_sha}}}],
              'budget':{'maxAttempts':1,'timeoutMs':30000,'maxOutputBytes':MAX_MEDIA_BYTES},'adoption':'manual'}
        json_new(folder/'spec.json',spec)
        result=client.work('submit',spec=spec)
        ticket=_make_ticket(folder,result);json_new(folder/'ticket.json',ticket);return ticket


def reconcile(client,project,key):
    root,folder=_folder(project,key)
    with locked(root):
        _request(folder);_returned(folder)
        if (folder/'ticket.json').exists():return _ticket(folder)
        spec=read_json(regular(folder/'spec.json',65536))
        matches=[w for w in client.work('list')['works'] if w['key']==spec['key']]
        if len(matches)!=1:raise MediaError('submission_not_confirmed_do_not_resubmit')
        ticket=_make_ticket(folder,client.work('inspect',work=matches[0]['work']))
        if ticket['handoffSha256']!=sha(folder/'request.json'):raise MediaError('handoff_changed_after_submit')
        json_new(folder/'ticket.json',ticket);return ticket


def run(client,project,key):
    _,folder=_folder(project,key);_request(folder);_returned(folder)
    return run_scene(client,_ticket(folder))


def adopt(client,project,key):
    _,folder=_folder(project,key);_request(folder);_returned(folder)
    return adopt_scene(client,project,_ticket(folder))


def inspect_job(client,project,key):
    root,folder=_folder(project,key);request=_request(folder);current=inspect_project(root)
    result={'request':request,'handoffPath':str(folder/'handoff.txt'),'state':'awaiting_result',
            'externalExecution':'not_observed','projectChanged':current['digest']!=request['baseManifestDigest'],'native':None}
    if not (folder/'returned.json').exists():return result
    returned,_=_returned(folder);result['returned']=returned
    if not (folder/'ticket.json').exists():
        result['state']='submission_unresolved' if (folder/'spec.json').exists() else 'returned_not_submitted'
        return result
    ticket=_ticket(folder);result['work']=ticket['work']
    if client is None:result['state']='native_status_unavailable';return result
    view=client.work('inspect',work=ticket['work'])
    # Keep routine agent polling small. Full receipts/logs remain in native CALF
    # and adoption always fetches fresh evidence through the existing selector.
    result['native']={k:view.get(k) for k in ['work','phase','outcome','verified','stale','attempt','calls']}
    result['native']['manifestDigest']=(view.get('manifest') or {}).get('digest')
    result['state']='needs_attention'
    if view.get('stale') or view.get('outcome') not in ['SATISFIED','UNKNOWN']:return result
    if not view.get('verified'):
        result['state']='ready_to_check' if view.get('phase')=='ready' else 'unresolved';return result
    if view.get('outcome')!='SATISFIED':return result
    selected=current['selected'].get(request['sceneId'])
    if selected and selected['work']==ticket['work']:result['state']='selected'
    elif view.get('adoptedValid'):result['state']='retained_version'
    else:result['state']='ready_for_review'
    return result


def inspect_jobs(client,project):
    root=root_path(project);inspect_project(root);base=root/'handoffs';jobs=[]
    if base.exists():
        if base.resolve()!=base:raise MediaError('handoff_path_changed')
        for folder in sorted(base.iterdir()):
            if folder.is_dir():
                try:
                    job=inspect_job(client,root,folder.name);request=job['request']
                    row={k:job[k] for k in ['state','externalExecution','projectChanged','native']}
                    row.update({k:request[k] for k in ['key','sceneId','parent','toolLabel']})
                    row['work']=job.get('work');row['returnedSha256']=job.get('returned',{}).get('sha256')
                    jobs.append(row)
                except (ValueError,OSError,KeyError) as e:
                    jobs.append({'key':folder.name,'state':'unresolved','error':str(e)[:300]})
    return {'project':str(root),'jobs':jobs}
