"""Private create-only captures outside inspected repositories and CALF records."""
import hashlib
import errno
import json
import os
import stat
import uuid
import time
from pathlib import Path
from .model import SCHEMA, SOURCE_LIMIT, TOTAL_SOURCE_LIMIT, RepositoryError, canonical, classify, digest, git_blob_oid, now, path_bytes


def stable_read(root, raw, limit=SOURCE_LIMIT):
    """Open each directory without following links on POSIX; reject reparse paths on Windows."""
    pieces=raw.split(b'/');fds=[]
    try:
        if os.name!='nt':
            directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY);fds.append(directory)
            for piece in pieces[:-1]:
                directory=os.open(piece,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);fds.append(directory)
            fd=os.open(pieces[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        else:
            path=Path(root)
            for piece in pieces:
                path=path/os.fsdecode(piece);info=path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:
                    return None,'symlink'
            fd=os.open(path,os.O_RDONLY|os.O_BINARY)
        fds.append(fd);before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):return None,'not_regular'
        if before.st_size>limit:return None,'oversized'
        if os.name=='nt':
            import ctypes,msvcrt
            buffer=ctypes.create_unicode_buffer(32768)
            function=ctypes.windll.kernel32.GetFinalPathNameByHandleW
            function.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong]
            count=function(msvcrt.get_osfhandle(fd),buffer,len(buffer),0)
            if not count or count>=len(buffer):raise RepositoryError('PATH_CHECK_FAILED','Could not validate opened file')
            actual=Path(buffer.value.removeprefix('\\\\?\\')).resolve()
            if not actual.is_relative_to(Path(root)):raise RepositoryError('INVALID_PATH','Opened file escaped repository')
        chunks=[];size=0
        while True:
            chunk=os.read(fd,min(65536,limit+1-size))
            if not chunk:break
            chunks.append(chunk);size+=len(chunk)
            if size>limit:return None,'oversized'
        after=os.fstat(fd)
        if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise RepositoryError('SOURCE_CHANGED','File changed during its read',5)
        return b''.join(chunks),'regular'
    except FileNotFoundError:return None,'absent'
    except OSError as error:
        if error.errno in (errno.ENOTDIR,errno.ELOOP):return None,'symlink'
        return None,'unreadable'
    finally:
        for fd in reversed(fds):os.close(fd)

class Store:
    def __init__(self,directory,reader=None,*,create=False):
        self.directory=Path(directory).expanduser().resolve()
        if reader:
            for name in ('root','git_dir','common_dir'):
                protected=Path(reader.info[name])
                if self.directory==protected or self.directory.is_relative_to(protected):
                    raise RepositoryError('OUTPUT_IN_REPOSITORY','Data directory must be outside repository and Git directories')
        if reader or create:
            self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            for name in ['projects','captures','sources']: (self.directory/name).mkdir(exist_ok=True,mode=0o700)
        elif not self.directory.is_dir():
            raise RepositoryError('DATA_MISSING','Select an existing extension data directory')
    def project(self,info):
        key=digest(canonical([info['root'],info['git_dir'],info['common_dir']]))
        destination=self.directory/'projects'/(key+'.json')
        existing=json.loads(destination.read_bytes()) if destination.exists() else None
        common_key=digest(canonical([info['common_dir'],info['object_format']]))
        common_path=self.directory/'projects'/('repository-'+common_key+'.json')
        common={'repository_id':existing['repository_id'] if existing else str(uuid.uuid4()),'common_dir':info['common_dir']}
        try:
            with common_path.open('x',encoding='utf-8') as stream:stream.write(canonical(common).decode())
        except FileExistsError:common=json.loads(common_path.read_bytes())
        data={'repository_id':common['repository_id'],'worktree_id':str(uuid.uuid4()),'root':info['root'],'git_dir':info['git_dir'],'common_dir':info['common_dir']}
        try:
            with destination.open('x',encoding='utf-8') as stream:stream.write(canonical(data).decode())
        except FileExistsError:
            data=json.loads(destination.read_bytes())
            if any(data[k]!=info[k] for k in ['root','git_dir','common_dir']) or data['repository_id']!=common['repository_id']:
                raise RepositoryError('PROJECT_MISMATCH','Registered project does not match selected paths')
        return data
    def save(self,data):
        raw=canonical(data)
        if len(raw)>32*1024*1024:raise RepositoryError('CAPTURE_LIMIT','Capture metadata exceeds bound',3)
        identity=digest(raw);destination=self.directory/'captures'/(identity+'.json')
        try:
            with destination.open('xb') as stream:stream.write(raw)
        except FileExistsError:
            if destination.read_bytes()!=raw:raise RepositoryError('CAPTURE_CONFLICT','Capture identity conflict')
        return dict(data,capture_id=identity)
    def load(self,identity):
        if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):raise RepositoryError('INVALID_CAPTURE','Invalid capture identity')
        path=self.directory/'captures'/(identity+'.json')
        if not path.exists():path=self.directory/'captures-v2'/(identity+'.json')
        if path.stat().st_size>32*1024*1024:raise RepositoryError('CAPTURE_LIMIT','Capture metadata too large',3)
        raw=path.read_bytes()
        if digest(raw)!=identity:raise RepositoryError('CAPTURE_CHANGED','Capture bytes do not match identity')
        data=json.loads(raw)
        if data.get('schema') not in {SCHEMA,'calf.repository.capture.v2'}:raise RepositoryError('CAPTURE_SCHEMA','Unknown capture schema')
        return dict(data,capture_id=identity)
    def read_source_bytes(self,key):
        if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise RepositoryError('INVALID_SOURCE','Invalid source cache identity')
        raw,kind=stable_read(self.directory/'sources',key.encode('ascii'))
        if kind=='absent':raise FileNotFoundError('Retained source is missing')
        if raw is None or digest(raw)!=key:raise RepositoryError('SOURCE_CACHE_CHANGED','Retained source does not match its byte identity')
        return raw
    def save_snapshot(self,snapshot):
        from .providers.base import Snapshot
        if not isinstance(snapshot,Snapshot) or snapshot.legacy_capture_id is not None:
            raise RepositoryError('SOURCE_CONTRACT','Save a new v2 snapshot; legacy captures are never migrated in place')
        data=snapshot.manifest();raw=canonical(data)
        if len(raw)>32*1024*1024:raise RepositoryError('CAPTURE_LIMIT','Snapshot metadata exceeds bound',3)
        for value in snapshot.contents.values():
            if value.data is not None:self.source(value.data)
        directory=self.directory/'captures-v2';directory.mkdir(exist_ok=True,mode=0o700)
        identity=digest(raw);path=directory/(identity+'.json')
        try:
            with path.open('xb') as stream:stream.write(raw)
        except FileExistsError:
            if path.read_bytes()!=raw:raise RepositoryError('CAPTURE_CONFLICT','Snapshot identity conflict')
        return identity
    def load_snapshot(self,identity):
        from .providers.base import Snapshot
        data=self.load(identity)
        if data['schema']==SCHEMA:
            from .providers.local import snapshot_from_v1
            return snapshot_from_v1(data,self)
        manifest={k:v for k,v in data.items() if k!='capture_id'}
        try:return Snapshot.from_manifest(manifest,self.read_source_bytes)
        except FileNotFoundError as error:raise RepositoryError('SOURCE_CACHE_MISSING','Snapshot references missing retained bytes') from error

    def source(self,data):
        key=digest(data);path=self.directory/'sources'/key
        try:
            with path.open('xb') as stream:stream.write(data)
            path.chmod(0o444)
        except FileExistsError:
            if path.read_bytes()!=data:raise RepositoryError('SOURCE_CACHE_CHANGED','Source capture bytes changed')
        return str(path)


def scan(reader,store,limit=200):
    previous=getattr(reader,'total_deadline',float('inf'))
    reader.total_deadline=time.monotonic()+120
    try:return _scan(reader,store,limit)
    finally:reader.total_deadline=previous

def _scan(reader,store,limit=200):
    info=dict(reader.discover());project=store.project(info);before_refs=reader.refs();stages=reader.stages();before=digest(canonical(stages))
    head=reader.tree(info['head']) if info['head'] else [];files={}
    for x in head:files[x['id']]=dict(id=x['id'],path=x['path'],path_utf8=x['path_utf8'],head=x,index={},working=None)
    for x in stages:
        entry=files.setdefault(x['id'],dict(id=x['id'],path=x['path'],path_utf8=x['path_utf8'],head=None,index={},working=None))
        entry['index'][str(x['stage'])]=x
    budget=TOTAL_SOURCE_LIMIT;unknown=0;raw_changed=0;staged=0;conflicts=0
    for entry in files.values():
        if reader.cancel_event.is_set():raise RepositoryError('CANCELLED','Collection cancelled',130)
        if time.monotonic()>reader.total_deadline:raise RepositoryError('COLLECTION_TIMEOUT','Metadata collection exceeded its time budget')
        stage=entry['index'].get('0');previous=entry['head']
        entry['staged']='conflict' if any(k!='0' for k in entry['index']) else 'added' if stage and not previous else 'deleted' if previous and not stage else 'modified' if stage and previous and (stage['oid'],stage['mode'])!=(previous['oid'],previous['mode']) else 'unchanged'
        if entry['staged']=='conflict':conflicts+=1
        elif entry['staged']!='unchanged':staged+=1
        if stage and stage['mode']=='160000':entry['working']={'kind':'submodule','captured_at':now()};continue
        raw,kind=stable_read(reader.root,path_bytes(entry['id']),min(SOURCE_LIMIT,max(0,budget)))
        if raw is None:
            entry['working']={'kind':kind,'captured_at':now(),'status':'absent' if kind=='absent' else 'unknown'};unknown+=kind!='absent';raw_changed+=kind=='absent' and stage is not None;continue
        budget-=len(raw);value=classify(raw);value.pop('text',None)
        value.update(captured_at=now(),blob_oid=git_blob_oid(raw,info['object_format']),status='raw_same' if stage and git_blob_oid(raw,info['object_format'])==stage['oid'] else 'raw_changed')
        entry['working']=value;raw_changed+=value['status']=='raw_changed'
    history,more=reader.history(info['head'],limit=limit) if info['head'] else ([],False)
    after=reader.discover()
    if after['head']!=info['head'] or reader.refs()!=before_refs or digest(canonical(reader.stages()))!=before:
        raise RepositoryError('SOURCE_CHANGED','Repository metadata changed during collection',5)
    data={'schema':SCHEMA,'extension_version':'0.1.0.dev0','captured_at':now(),'repository':dict(info,repository_id=project['repository_id']),
          'worktree':{'worktree_id':project['worktree_id'],'index_digest':before},'refs':before_refs,
          'files':list(files.values()),'history':history,'nodes':[],'edges':[],
          'summary':{'staged':staged,'conflicts':conflicts,'raw_changed':raw_changed,'working_unknown':unknown,'status_basis':'RAW_BYTES'},
          'coverage':{'history_limit':limit,'history_has_more':more,'shallow':info['shallow'],'files':len(files),'working_unknown':unknown,'untracked_included':False,'source_bytes_hashed':TOTAL_SOURCE_LIMIT-budget,'state':'PARTIAL' if unknown else 'COMPLETE'}}
    for c in history:
        data['nodes'].append({'id':c['id'],'kind':'commit','label':c['subject']})
        for parent in c['parents']:data['edges'].append({'from':c['id'],'to':parent,'kind':'COMMIT_PARENT','boundary':parent not in {x['id'] for x in history}})
    return store.save(data)
