"""Bounded transport to the shared native GCN/MCL core; no policy fallback."""
import json
import subprocess
import tempfile
import time
from pathlib import Path
from . import history_index as hi
from .model import RepositoryError


def invoke(native, request):
    hi.require(isinstance(native, dict) and set(native) == {'path', 'sha256'}, 'CONTEXT_NATIVE_NOT_BOUND')
    binary = hi.physical(native['path'])
    hi.require(hi.digest_file(binary)[0] == native['sha256'], 'CONTEXT_NATIVE_CHANGED')
    raw = hi.encode(request)
    hi.require(len(raw) <= 65536, 'CONTEXT_CORE_INPUT_LIMIT')
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        child = subprocess.Popen([str(binary), 'gcn'], stdin=subprocess.PIPE,
                                 stdout=output, stderr=errors, shell=False)
        try:
            child.stdin.write(raw)
            child.stdin.close()
            deadline = time.monotonic() + 15
            while child.poll() is None:
                hi.require(time.monotonic() < deadline, 'CONTEXT_CORE_TIMEOUT')
                hi.require(output.tell() <= 262144 and errors.tell() <= 65536, 'CONTEXT_CORE_OUTPUT_LIMIT')
                time.sleep(0.01)
            hi.require(output.tell() <= 262144 and errors.tell() <= 65536, 'CONTEXT_CORE_OUTPUT_LIMIT')
            hi.require(child.returncode == 0, 'CONTEXT_CORE_GCN_UNAVAILABLE')
            output.seek(0)
            result = hi.decode(output.read(262145))
        finally:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=2)
    hi.require(hi.digest_file(binary)[0] == native['sha256'], 'CONTEXT_NATIVE_CHANGED')
    hi.require(isinstance(result, dict) and result.get('controlEngine') == 'CALF-native'
               and result.get('controlCompute') == 'CPU' and result.get('executionAuthority') == 'UNCHANGED',
               'CONTEXT_CORE_RESPONSE')
    return result


def request(plan, modules, op, native, **fields):
    return invoke(native, dict(op=op, plan=plan, moduleIds=list(modules), **fields))


def validate(plan, modules, native=None):
    result = request(plan, modules, 'validate', native)
    hi.require(result.get('state') == 'VALID', 'CONTEXT_CORE_RESPONSE')
    return result


def project(plan, modules, lane, native=None):
    return request(plan, modules, 'project', native, lane=lane)


def guard(connection, lane, module):
    return request(connection.value.get('lanes'), connection.modules, 'guard',
                   connection.value['native'], lane=lane, module=module)


def gate(connection, lane):
    project_root = hi.physical(connection.project, directory=True)
    workspace = hi.physical(Path(connection.value['history']).parent, directory=True)
    result = request(connection.value.get('lanes'), connection.modules, 'gate', connection.value['native'],
                     lane=lane, projectRoot=str(project_root), recordWorkspace=str(workspace))
    hi.require(result.get('state') in ['WAIT', 'READY'] and Path(result.get('projectRoot', '')) == project_root
               and Path(result.get('recordWorkspace', '')) == workspace, 'CONTEXT_CORE_RESPONSE')
    return result
