"""Bounded local files, durable receipts, host mutex and fixed tool probes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import time
import unicodedata

class PackError(ValueError):
    pass

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def pairs(rows):
    value={}
    for key,item in rows:
        if key in value:raise PackError('duplicate_json_key')
        value[key]=item
    return value

def decode(raw):
    try:
        return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
            parse_constant=lambda v:(_ for _ in ()).throw(PackError('nonfinite_json')))
    except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise PackError('invalid_json') from e

def physical(path,*,directory=False):
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts or p.is_symlink():raise PackError('physical_absolute_path_required')
    if p.resolve(strict=True)!=p:raise PackError('physical_absolute_path_required')
    s=p.stat()
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):raise PackError('regular_path_required')
    return p

def sha(path):
    h=hashlib.sha256()
    with physical(path).open('rb') as f:
        for chunk in iter(lambda:f.read(32768),b''):h.update(chunk)
    return h.hexdigest()

def read(path,maximum=65536):
    with physical(path).open('rb') as f:raw=f.read(maximum+1)
    if len(raw)>maximum:raise PackError('json_size_limit')
    return decode(raw)

def relative(name):
    if not isinstance(name,str) or not name or len(name)>512 or name.startswith('/') or '\\' in name or ':' in name:
        raise PackError('unsafe_archive_path')
    parts=name.split('/')
    if len(parts)>16:raise PackError('path_depth_limit')
    for part in parts:
        if part in ('','.','..') or part[-1:] in (' ','.') or any(ord(c)<32 for c in part):raise PackError('unsafe_archive_path')
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise PackError('reserved_archive_path')
    return name

def portable_key(name):return unicodedata.normalize('NFC',name).casefold()

def token(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise PackError('digest_required')
    return value

def sync_directory(folder):
    if os.name!='nt':
        fd=os.open(folder,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)

def atomic(path,value,*,new=False):
    """Caller holds the store mutex. Failed writes retain their temp artifact."""
    path=Path(path);physical(path.parent,directory=True)
    if path.is_symlink() or (new and path.exists()):raise PackError('file_already_exists')
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    with os.fdopen(fd,'wb') as f:f.write(canonical(value)+b'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path);sync_directory(path.parent)

@contextmanager
def mutex(root):
    path=Path(root)/'.mutex'
    if path.is_symlink():raise PackError('unsafe_mutex')
    with path.open('a+b') as f:
        try:
            if os.name=='nt':
                import msvcrt
                if f.seek(0,2)==0:f.write(b'0');f.flush()
                f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as e:raise PackError('store_busy') from e
        try:yield
        finally:
            if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def run(argv,*,input_bytes=b'',timeout=30,limit=1048576,cwd=None):
    """No shell, credential inheritance or model. Explicitly chosen executables only."""
    physical(argv[0]);env={k:os.environ[k] for k in ('SystemRoot','WINDIR','TEMP','TMP','TMPDIR') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',LC_ALL='C')
    with tempfile.TemporaryFile() as src,tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        src.write(input_bytes);src.seek(0)
        p=subprocess.Popen(list(map(str,argv)),stdin=src,stdout=out,stderr=err,cwd=cwd,env=env,
                           shell=False,start_new_session=os.name!='nt')
        deadline=time.monotonic()+timeout
        try:
            while p.poll() is None:
                if out.tell()>limit or err.tell()>262144:raise PackError('tool_output_limit')
                if time.monotonic()>deadline:raise PackError('tool_timeout_reconcile_before_retry')
                time.sleep(.025)
            out.seek(0);err.seek(0);raw=out.read(limit+1);diagnostic=err.read(262145)
            if len(raw)>limit or len(diagnostic)>262144:raise PackError('tool_output_limit')
            if p.returncode:raise PackError('tool_failed:'+str(p.returncode)+':'+diagnostic.decode('utf8','replace')[-500:])
            return raw
        finally:
            if p.poll() is None:
                if os.name=='nt':
                    # This PID belongs to our still-running child. Bound the
                    # tree termination and retain a direct-handle fallback.
                    try:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=4,check=False)
                    except (OSError,subprocess.TimeoutExpired):pass
                    if p.poll() is None:p.kill()
                else:
                    try:os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                p.wait(timeout=5)
