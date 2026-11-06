"""Small scene-selection manifest; execution/checks stay in the CALF core.

Version files and old manifests are never overwritten. Selection is a local,
explicit client action with compare-and-swap, not a new execution authority.
"""
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from .common import canonical, digest, sha, read_json, regular, MediaError, MAX_MEDIA_BYTES


def name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value):
        raise MediaError('scene_id_invalid')
    if value.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise MediaError('reserved_portable_name')
    return value

def root_path(value):
    path=Path(value)
    if not path.is_absolute() or path.is_symlink() or path.resolve(strict=True)!=path:
        raise MediaError('physical_project_folder_required')
    return path

def write_new(path, data):
    path=Path(path)
    with path.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())

def json_new(path,value):
    write_new(path,canonical(value)+b'\n')

@contextmanager
def locked(root):
    folder=root/'.scene-selection-lock'
    try:folder.mkdir()
    except FileExistsError:raise MediaError('scene_selection_busy_or_unreconciled') from None
    token=uuid.uuid4().hex
    try:
        json_new(folder/'owner.json',{'token':token,'pid':os.getpid()})
        yield
    finally:
        # Never clear another operation's or a replaced lock.
        if (folder/'owner.json').is_file() and read_json(folder/'owner.json').get('token')==token:
            (folder/'owner.json').unlink();folder.rmdir()


def create_project(path, scene_ids):
    path=Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink():raise MediaError('new_project_folder_required')
    ids=list(scene_ids)
    if not 1<=len(ids)<=32 or len(set(ids))!=len(ids):raise MediaError('scene_count')
    for value in ids:name(value)
    path.mkdir(parents=True,exist_ok=False);root=root_path(path)
    for folder in ['versions','manifests','requests']:(root/folder).mkdir()
    value={'schema':'calf.media.project.v1','projectId':uuid.uuid4().hex,'revision':0,'scenes':{v:None for v in ids}}
    raw=canonical(value)+b'\n';h=hashlib.sha256(raw).hexdigest()
    write_new(root/'manifests'/f'{h}.json',raw);write_new(root/'manifest.json',raw)
    return inspect_project(root)


def read_manifest(root):
    root=root_path(root);file=regular(root/'manifest.json',65536);value=read_json(file)
    if set(value)!= {'schema','projectId','revision','scenes'} or value['schema']!='calf.media.project.v1' or type(value['revision']) is not int:
        raise MediaError('project_manifest_invalid')
    name(value['projectId'])
    if not isinstance(value['scenes'],dict) or not 1<=len(value['scenes'])<=32:raise MediaError('scene_count')
    for scene,version in value['scenes'].items():
        name(scene)
        if version is not None and (not isinstance(version,str) or not re.fullmatch('[0-9a-f]{64}',version)):raise MediaError('scene_version_invalid')
    return value,sha(file)


def version_path(root, scene, version):
    name(scene)
    if not re.fullmatch('[0-9a-f]{64}',version):raise MediaError('version_identity')
    path=root/'versions'/scene/version
    if path.resolve()!=path or not path.resolve().is_relative_to(root):raise MediaError('version_path_changed')
    return path


def validation_detail(view):
    if not view.get('verified') or view.get('outcome')!='SATISFIED' or view.get('stale'):
        raise MediaError('fresh_satisfied_evidence_required')
    receipt=view.get('verification');manifest=view.get('manifest')
    if not receipt or not manifest or receipt['contractDigest']!=view['contractDigest'] or receipt['requestId']!=view['requestId'] or receipt['manifestDigest']!=manifest['digest'] or digest(manifest['artifacts'])!=manifest['digest']:
        raise MediaError('manifest_receipt_binding')
    checks=receipt.get('checks',[])
    if len(checks)!=1 or checks[0]['id']!='media-technical' or checks[0]['outcome']!='SATISFIED' or checks[0]['manifestDigest']!=manifest['digest']:
        raise MediaError('technical_check_required')
    detail=json.loads(checks[0]['detail']['reason'])
    if detail.get('schema')!='calf.media.ffmpeg.validation.v1' or detail.get('violations'):
        raise MediaError('media_validation_detail')
    return detail


def read_version(root, scene, version, *, expected_project=None):
    folder=version_path(root,scene,version);info=read_json(regular(folder/'version.json',65536));video=regular(folder/'video.mp4')
    if info.get('schema')!='calf.media.scene-version.v1' or info.get('sceneId')!=scene or info.get('version')!=version:
        raise MediaError('version_record_identity')
    if expected_project is not None and info['projectId']!=expected_project:raise MediaError('version_project_identity')
    detail=validation_detail(info['validatedView'])
    artifact=info['validatedView']['manifest']['artifacts']['files']
    if len(artifact)!=1 or artifact[0]['id']!='video' or sha(video)!=artifact[0]['sha256'] or video.stat().st_size!=artifact[0]['bytes']:
        raise MediaError('approved_scene_changed')
    if detail['sceneId']!=scene or detail['projectId']!=info['projectId'] or detail['profileSha256']!=digest(info['profile']):
        raise MediaError('approved_scene_provenance')
    return info


def inspect_project(path):
    root=root_path(path);manifest,h=read_manifest(root);selected={}
    for scene,version in manifest['scenes'].items():
        if version is not None:
            info=read_version(root,scene,version,expected_project=manifest['projectId'])
            artifact=info['validatedView']['manifest']['artifacts']['files'][0]
            selected[scene]={'version':version,'path':str(version_path(root,scene,version)/'video.mp4'),'sha256':artifact['sha256'],'work':info['validatedView']['work']}
    return {'manifest':manifest,'digest':h,'selected':selected}


def commit(root, expected, manifest):
    _,current=read_manifest(root)
    if current!=expected:raise MediaError('project_manifest_changed')
    raw=canonical(manifest)+b'\n';h=hashlib.sha256(raw).hexdigest();archived=root/'manifests'/f'{h}.json'
    if archived.exists():
        if archived.read_bytes()!=raw:raise MediaError('manifest_archive_conflict')
    else:write_new(archived,raw)
    temporary=root/('.manifest-'+uuid.uuid4().hex+'.tmp')
    write_new(temporary,raw)
    try:
        if sha(root/'manifest.json')!=expected:raise MediaError('project_manifest_changed')
        os.replace(temporary,root/'manifest.json')
    finally:
        if temporary.exists():temporary.unlink()
    return h


def store_version(root, ticket, view, detail):
    artifact=view['manifest']['artifacts']['files'][0]
    source=regular(detail['artifactPath'])
    if sha(source)!=artifact['sha256'] or detail['artifactSha256']!=artifact['sha256']:
        raise MediaError('checked_candidate_changed')
    version=digest({'work':view['work'],'manifest':view['manifest']['digest'],'artifact':artifact['sha256']})
    folder=version_path(root,ticket['sceneId'],version);folder.parent.mkdir(parents=True,exist_ok=True)
    if not folder.exists():folder.mkdir()
    target=folder/'video.mp4'
    if not target.exists():
        with source.open('rb') as src, target.open('xb') as dst:
            for block in iter(lambda:src.read(32768),b''):dst.write(block)
            dst.flush();os.fsync(dst.fileno())
        target.chmod(0o444)
    if sha(target)!=artifact['sha256']:raise MediaError('incomplete_scene_copy_retained')
    # Keep the proof, not the unbounded activity/log projection.
    proof={k:view[k] for k in ['work','requestId','verified','outcome','manifest','verification','contractDigest','adopted','adoptedValid']}
    record={'schema':'calf.media.scene-version.v1','projectId':ticket['projectId'],'sceneId':ticket['sceneId'],
            'version':version,'profile':ticket['profile'],'validatedView':proof,
            'createdAt':datetime.now(timezone.utc).isoformat()}
    if not (folder/'version.json').exists():json_new(folder/'version.json',record)
    read_version(root,ticket['sceneId'],version,expected_project=ticket['projectId'])
    return version


def adopt_scene(client, project, ticket):
    root=root_path(project)
    with locked(root):
        current=inspect_project(root);manifest=current['manifest']
        if ticket['projectId']!=manifest['projectId']:raise MediaError('ticket_project_mismatch')
        if ticket['sceneId'] not in manifest['scenes']:raise MediaError('unknown_scene')
        view=client.work('inspect',work=ticket['work']);detail=validation_detail(view)
        # Do not require extra projection fields such as adapter. The submit-
        # time frozen-contract digest binds the selected executor and checks.
        if view['contractDigest']!=ticket['contractDigest']:
            raise MediaError('ticket_native_contract_changed')
        if view['verification']['checks'][0]['detail']['adapter']!=ticket['validator']:
            raise MediaError('unexpected_media_validator')
        for key in ['sceneId','projectId','baseManifestDigest','scopeSha256']:
            if detail[key]!=ticket[key]:raise MediaError('ticket_scene_scope_mismatch')
        if detail['profileSha256']!=digest(ticket['profile']):raise MediaError('ticket_profile_mismatch')
        wanted=digest({'work':view['work'],'manifest':view['manifest']['digest'],'artifact':view['manifest']['artifacts']['files'][0]['sha256']})
        if manifest['scenes'].get(ticket['sceneId'])==wanted:return current
        if current['digest']!=ticket['baseManifestDigest']:raise MediaError('project_changed_reconcile_before_adoption')
        # A lost response is not retried automatically. A later explicit call
        # can reconcile an already recorded native adoption of the same digest.
        if view.get('adopted') is None:
            view=client.work('adopt',work=ticket['work'],digest=view['manifest']['digest'])
        if not view.get('adoptedValid') or view['adopted']['digest']!=view['manifest']['digest']:
            raise MediaError('native_adoption_not_confirmed')
        version=store_version(root,ticket,view,detail)
        fresh=client.work('inspect',work=ticket['work']);validation_detail(fresh)
        if not fresh.get('adoptedValid') or fresh['manifest']['digest']!=view['manifest']['digest']:
            raise MediaError('candidate_changed_during_adoption')
        # Verify the byte identity of all currently approved scenes again.
        confirmed=inspect_project(root)
        if confirmed['digest']!=current['digest']:raise MediaError('project_changed_during_adoption')
        updated=copy.deepcopy(manifest);updated['revision']+=1;updated['scenes'][ticket['sceneId']]=version
        commit(root,current['digest'],updated)
        return inspect_project(root)


def select_version(project, scene, version, *, expected_manifest):
    """Explicit restoration selects a retained validated copy; no rendering."""
    root=root_path(project)
    with locked(root):
        current=inspect_project(root)
        if current['digest']!=expected_manifest:raise MediaError('project_manifest_changed')
        if scene not in current['manifest']['scenes']:raise MediaError('unknown_scene')
        read_version(root,scene,version,expected_project=current['manifest']['projectId'])
        value=copy.deepcopy(current['manifest']);value['revision']+=1;value['scenes'][scene]=version
        commit(root,current['digest'],value)
        return inspect_project(root)
