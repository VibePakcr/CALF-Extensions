"""Explicit scene requests over the existing CALF SDK. No daemon or AI model."""
from pathlib import Path
import sys
import calf_sdk
from .common import profile, regular, sha, digest, read_json, toolchain, MediaError, MAX_MEDIA_BYTES
from .project import root_path, inspect_project, name, json_new, locked
from calf_sdk.work import adapter_descriptor, input_reference


def register(client, configuration, ffmpeg, ffprobe):
    """Pin user-selected installed tools and this example's complete Python code."""
    folder=Path(configuration)
    if not folder.is_absolute() or folder.exists() or folder.is_symlink():
        raise MediaError('new_configuration_folder_required')
    tools={'schema':'calf.media.ffmpeg.toolchain.v1'}
    for key,value in [('ffmpeg',ffmpeg),('ffprobe',ffprobe)]:
        path=Path(value).resolve(strict=True);regular(path,128*1024*1024)
        tools[key]={'path':str(path),'sha256':sha(path)}
    folder.mkdir(parents=True,exist_ok=False);folder=root_path(folder)
    config=folder/'toolchain.json';json_new(config,tools);toolchain(config)
    here=Path(__file__).resolve().parent;sdk=Path(calf_sdk.__file__).resolve().parent
    files=[here/n for n in ['common.py','runtime.py','validator.py']]
    files += [sdk/n for n in ['__init__.py','client.py','adapter.py','work.py']]
    files += [config,Path(tools['ffmpeg']['path']),Path(tools['ffprobe']['path'])]
    python=Path(sys.executable).resolve(strict=True)
    identity=digest({'files':[{ 'path':str(p),'sha256':sha(p)} for p in files],
                     'python':{'path':str(python),'sha256':sha(python)}})[:24]
    registration={'schema':'calf.media.ffmpeg.registration.v1','executor':'ffmpeg-'+identity,
                  'validator':'ffprobe-'+identity,'configuration':str(config)}
    # Registration only pins code. It neither submits nor executes media work.
    for role,script,key in [('executor','runtime.py','executor'),('validator','validator.py','validator')]:
        descriptor=adapter_descriptor(registration[key],[str(python),'-B',str(here/script),str(sdk.parent),str(config)],
                                      files,role=role,resource_class='light')
        client.work('register',adapter=descriptor)
    json_new(folder/'registration.json',registration)
    return registration


def prepare_scene(client, project, scene, source, registration, request_key, settings, *, expected=None):
    """Freeze one scene request. Same key recovers its exact existing ticket.

    A new candidate requires a new key. A lost submit response is never retried
    here; reconcile_request performs a read-only lookup instead.
    """
    root=root_path(project);name(scene);name(request_key)
    source=regular(Path(source).resolve(strict=True))
    producer=profile(settings);checker=profile(expected if expected is not None else settings)
    intent={'sceneId':scene,'source':input_reference(source,'source','video/mp4'),
            'profile':producer,'expected':checker,'executor':registration['executor'],'validator':registration['validator']}
    folder=root/'requests'/request_key
    with locked(root):
        current=inspect_project(root)
        if scene not in current['manifest']['scenes']:raise MediaError('unknown_scene')
        if folder.exists():
            saved=read_json(regular(folder/'intent.json',65536))
            if saved!=intent:raise MediaError('request_key_conflict')
            if not (folder/'ticket.json').exists():raise MediaError('submission_uncertain_reconcile_request')
            return read_json(regular(folder/'ticket.json',65536))
        folder.mkdir();json_new(folder/'intent.json',intent)
        plan={'schema':'calf.media.scene-plan.v1','projectId':current['manifest']['projectId'],
              'baseManifestDigest':current['digest'],'sceneId':scene,'sourceSha256':intent['source']['sha256']}
        json_new(folder/'scene-plan.json',plan);scope_sha=sha(folder/'scene-plan.json')
        spec={'schema':'calf.work.v1','key':'media-'+plan['projectId']+'-'+request_key,
              'title':'Scene '+scene+' / '+request_key,'adapter':registration['executor'],
              'parameters':{'profile':producer},
              'inputs':[intent['source'],input_reference(folder/'scene-plan.json','scene-plan','application/json')],
              'outputs':[{'id':'video','path':'video.mp4','mediaType':'video/mp4','minBytes':1,'maxBytes':MAX_MEDIA_BYTES}],
              'checks':[{'id':'media-technical','artifact':'video','kind':'adapter',
                         'rule':{'adapter':registration['validator'],'parameters':{'expected':checker,'scopeSha256':scope_sha}}}],
              'budget':{'maxAttempts':1,'timeoutMs':30000,'maxOutputBytes':MAX_MEDIA_BYTES},'adoption':'manual'}
        json_new(folder/'spec.json',spec)
        # Persist intent before the single submit. Never infer failure from a timeout.
        result=client.work('submit',spec=spec)
        ticket=_ticket(spec,result,checker,plan,scope_sha,registration)
        json_new(folder/'ticket.json',ticket)
        return ticket


def _ticket(spec,result,checker,plan,scope_sha,registration):
    return {'schema':'calf.media.scene-ticket.v1','work':result['work'],'contractDigest':result['contractDigest'],
            'sceneId':plan['sceneId'],'projectId':plan['projectId'],'baseManifestDigest':plan['baseManifestDigest'],
            'scopeSha256':scope_sha,'profile':checker,'executor':registration['executor'],'validator':registration['validator']}


def reconcile_request(client, project, request_key):
    """Recover a persisted submit using read-only public APIs. Never resubmit."""
    root=root_path(project);name(request_key);folder=root/'requests'/request_key
    with locked(root):
        if (folder/'ticket.json').exists():return read_json(regular(folder/'ticket.json',65536))
        spec=read_json(regular(folder/'spec.json',65536));plan=read_json(regular(folder/'scene-plan.json',65536))
        matches=[r for r in client.work('list')['works'] if r['key']==spec['key']]
        if len(matches)!=1:raise MediaError('submission_not_confirmed_do_not_resubmit')
        view=client.work('inspect',work=matches[0]['work'])
        ticket=_ticket(spec,view,spec['checks'][0]['rule']['parameters']['expected'],plan,sha(folder/'scene-plan.json'),
                       {'executor':spec['adapter'],'validator':spec['checks'][0]['rule']['adapter']})
        json_new(folder/'ticket.json',ticket);return ticket


def run_scene(client, ticket):
    """One native step. Rendering success alone never selects an approved scene."""
    view=client.work('inspect',work=ticket['work'])
    if view['phase']=='ready':return client.work('step',work=ticket['work'])
    return view
