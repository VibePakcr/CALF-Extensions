"""Bounded local I/O and the extension's explicit technical contract."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import time

# CALF clears PYTHONPATH for registered processes. Registration passes the
# physical SDK root explicitly and pins every imported SDK source file.
if not __package__:
    if len(sys.argv)!=4:
        raise RuntimeError('adapter_requires_sdk_toolchain_and_request')
    sdk=Path(sys.argv[1])
    if not sdk.is_absolute() or sdk.resolve(strict=True)!=sdk or not sdk.is_dir():
        raise RuntimeError('physical_sdk_root_required')
    sys.path.insert(0,str(sdk))
from calf_sdk.client import _json
from calf_sdk.work import read_work_request, runtime_result, validation_result, emit_work

MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 65536
MAX_DURATION_MS = 30000
PROCESS_TIMEOUT = 25

class MediaError(ValueError):
    pass

class ToolError(RuntimeError):
    def __init__(self, code, diagnostic=''):
        super().__init__(code)
        self.code = code
        self.diagnostic = diagnostic

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(32768), b''):
            h.update(chunk)
    return h.hexdigest()

def read_json(path, maximum=MAX_JSON_BYTES):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise MediaError('json_size_limit')
    return _json(raw)

def exact(value, names, code):
    if not isinstance(value, dict) or set(value) != set(names):
        raise MediaError(code)

def integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        raise MediaError(code)
    return value

def profile(value):
    exact(value, ['width', 'height', 'fps', 'startMs', 'durationMs', 'audio', 'maxBlackMs', 'maxSilenceMs'], 'profile_fields')
    for field, bound in [('width',1280), ('height',720)]:
        integer(value[field], 16, bound, field+'_range')
        if value[field] % 2:
            raise MediaError(field+'_must_be_even')
    if type(value['fps']) is not int or value['fps'] not in (24,25,30):
        raise MediaError('fps_unsupported')
    integer(value['startMs'], 0, 3600000, 'start_range')
    integer(value['durationMs'], 100, MAX_DURATION_MS, 'duration_range')
    if value['durationMs'] * value['fps'] % 1000:
        raise MediaError('duration_must_cover_whole_frames')
    if type(value['audio']) is not bool:
        raise MediaError('audio_boolean_required')
    for name in ['maxBlackMs','maxSilenceMs']:
        if value[name] is not None:
            integer(value[name], 100, value['durationMs'], name+'_range')
    if not value['audio'] and value['maxSilenceMs'] is not None:
        raise MediaError('silence_check_requires_audio')
    return dict(value)

def regular(path, maximum=MAX_MEDIA_BYTES):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or path.is_symlink():
        raise MediaError('physical_absolute_file_required')
    resolved = path.resolve(strict=True)
    if resolved != path or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > maximum:
        raise MediaError('file_type_or_size')
    return path

def toolchain(path):
    value = read_json(path)
    exact(value, ['schema','ffmpeg','ffprobe'], 'toolchain_fields')
    if value['schema'] != 'calf.media.ffmpeg.toolchain.v1':
        raise MediaError('toolchain_schema')
    for name in ['ffmpeg','ffprobe']:
        row = value[name]
        exact(row, ['path','sha256'], 'tool_identity_fields')
        tool = regular(row['path'], 128 * 1024 * 1024)
        if sha(tool) != row['sha256']:
            raise MediaError('tool_identity_changed')
    return value

def run_tool(argv, *, timeout=PROCESS_TIMEOUT, stdout_limit=262144, stderr_limit=65536):
    """Spool bounded diagnostics. Child stays in CALF's existing process group/job."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(list(map(str,argv)), stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, shell=False)
        deadline = time.monotonic() + timeout
        try:
            while True:
                if os.fstat(out.fileno()).st_size > stdout_limit or os.fstat(err.fileno()).st_size > stderr_limit:
                    raise ToolError('tool_output_limit')
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ToolError('tool_timeout')
                try:
                    code = child.wait(timeout=min(.05,remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            raise
        out.seek(0);err.seek(0)
        stdout=out.read(stdout_limit+1);stderr=err.read(stderr_limit+1)
        if len(stdout)>stdout_limit or len(stderr)>stderr_limit:
            raise ToolError('tool_output_limit')
        if code:
            raise ToolError('tool_nonzero',stderr.decode('utf-8','replace')[-1500:])
        return stdout,stderr.decode('utf-8','replace')

def candidate(root, relative, *, existing=False):
    root=Path(root).resolve(strict=True)
    parts=PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(x in ['.','..'] for x in parts.parts) or '\\' in relative:
        raise MediaError('candidate_path')
    target=root.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(root):
        raise MediaError('candidate_escape')
    if existing:
        return regular(target)
    if target.exists() or target.is_symlink():
        raise MediaError('candidate_already_exists')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.parent.resolve().is_relative_to(root):
        raise MediaError('candidate_parent_escape')
    return target

def scene_scope(request):
    refs={v['id']:v for v in request['inputs']}
    if set(refs) != {'source','scene-plan'}:
        raise MediaError('source_and_scene_plan_required')
    source=regular(refs['source']['path'])
    plan_file=regular(refs['scene-plan']['path'],MAX_JSON_BYTES)
    if sha(source)!=refs['source']['sha256'] or sha(plan_file)!=refs['scene-plan']['sha256']:
        raise MediaError('input_hash_mismatch')
    plan=read_json(plan_file)
    exact(plan, ['schema','projectId','baseManifestDigest','sceneId','sourceSha256'], 'scene_plan_fields')
    if not isinstance(plan['projectId'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',plan['projectId']):
        raise MediaError('project_identity')
    if plan['schema']!='calf.media.scene-plan.v1' or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',plan['sceneId']):
        raise MediaError('scene_plan_schema')
    if plan['sourceSha256']!=refs['source']['sha256']:
        raise MediaError('scene_source_mismatch')
    for k in ['baseManifestDigest','sourceSha256']:
        if not isinstance(plan[k],str) or not re.fullmatch(r'[0-9a-f]{64}',plan[k]):
            raise MediaError('scene_digest')
    return source,plan,refs['scene-plan']['sha256']
