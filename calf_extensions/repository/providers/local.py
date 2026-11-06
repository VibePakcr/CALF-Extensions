"""Local Git adapter and v1 compatibility. No hosted transport is implemented."""
import os
from pathlib import PurePosixPath
import time
import threading
from .base import Capabilities, Content, Entry, RepositoryIdentity, Revision, Snapshot
from ..capture import Store, scan, stable_read
from ..git_reader import GitReader
from ..model import RepositoryError, SCHEMA, TOTAL_SOURCE_LIMIT, classify, now, oid, path_bytes

LOCAL_CAPABILITIES=Capabilities(working=True,index=True,conflict_stages=True,cached_copy_editor=True,offline_export=True)


class LocalSource:
    capabilities=LOCAL_CAPABILITIES
    def __init__(self,root,data_dir,git=None):
        self.reader=GitReader(root,git);self.reader.discover();self.store=Store(data_dir,self.reader)
    @classmethod
    def from_reader(cls,reader,store):
        result=cls.__new__(cls);result.reader=reader;result.store=store;return result
    def collect_working(self):return scan(self.reader,self.store)
    def read_legacy(self,capture,path_id,version,commit=None):return _read_local_source(self.reader,self.store,capture,path_id,version,commit)
    def analysis_snapshot(self,capture,read_source=None,deadline=None):
        return snapshot_from_v1(capture,self.store,self.reader,read_source,deadline)
    def pin(self,ref_kind,ref_name=None):
        info=self.reader.discover();project=self.store.project(info)
        identity=RepositoryIdentity('local',None,project['repository_id'],PurePosixPath(info['root']).name)
        if ref_kind=='head':
            if ref_name is not None:raise RepositoryError('INVALID_REF','HEAD does not take a name')
            value=info['head']
            if value is None:raise RepositoryError('EMPTY_REPOSITORY','Repository has no commit')
        elif ref_kind=='commit':value=oid(ref_name)
        elif ref_kind in {'branch','tag'}:
            if not isinstance(ref_name,str) or not ref_name or len(ref_name)>4096:raise RepositoryError('INVALID_REF','Expected a named ref')
            full=('refs/heads/' if ref_kind=='branch' else 'refs/tags/')+ref_name
            value=next((item['oid'] for item in self.reader.refs() if item['name']==full),None)
            if value is None:raise RepositoryError('REF_NOT_FOUND','Selected ref was not found')
        else:raise RepositoryError('INVALID_REF','Unsupported ref kind')
        commit=oid(self.reader._read(['rev-parse','--verify',oid(value)+'^{commit}']).strip().decode('ascii'))
        if ref_kind=='commit' and commit!=value:raise RepositoryError('INVALID_REF','Expected a commit, not a tag object')
        tree=oid(self.reader._read(['rev-parse','--verify',commit+'^{tree}']).strip().decode('ascii'))
        return Revision(identity.key,'commit',commit_id=commit,ref_kind=ref_kind,ref_name=ref_name,tree_oid=tree,object_format=info['object_format'])
    def snapshot(self,revision):
        project=self.store.project(self.reader.info);identity=RepositoryIdentity('local',None,project['repository_id'],PurePosixPath(self.reader.info['root']).name)
        if revision.kind!='commit' or revision.repository_key!=identity.key:raise RepositoryError('SOURCE_CONTRACT','Selected revision belongs to another source')
        actual_tree=oid(self.reader._read(['rev-parse','--verify',revision.commit_id+'^{tree}']).strip().decode('ascii'))
        if revision.tree_oid!=actual_tree or revision.object_format!=self.reader.info['object_format']:raise RepositoryError('SOURCE_CONTRACT','Pinned commit/tree format mismatch')
        entries=[];contents={};budget=TOTAL_SOURCE_LIMIT;previous=getattr(self.reader,'total_deadline',float('inf'));self.reader.total_deadline=time.monotonic()+120
        try:
            for value in self.reader.tree(revision.commit_id):
                if self.reader.cancel_event.is_set():raise RepositoryError('CANCELLED','Snapshot collection cancelled',130)
                if time.monotonic()>self.reader.total_deadline:raise RepositoryError('COLLECTION_TIMEOUT','Snapshot collection exceeded its time budget')
                entry=Entry(value['id'],value['path'],value['path_utf8'],value['mode'],value['oid']);entries.append(entry)
                if entry.mode in {'120000','160000'}:
                    content=Content(entry.id,'UNAVAILABLE',blob_oid=entry.blob_oid,mode=entry.mode,unavailable_kind='symlink' if entry.mode=='120000' else 'submodule')
                elif budget<=0:content=Content(entry.id,'LIMIT_EXCEEDED',blob_oid=entry.blob_oid,mode=entry.mode,reason='TOTAL_SOURCE_LIMIT')
                else:
                    raw,size=self.reader.blob(entry.blob_oid)
                    if raw is None or size>budget:content=Content(entry.id,'LIMIT_EXCEEDED',blob_oid=entry.blob_oid,mode=entry.mode,size=size,reason='SOURCE_LIMIT')
                    else:content=Content(entry.id,'READY',raw,blob_oid=entry.blob_oid,mode=entry.mode,size=size);budget-=size
                contents[entry.id]=content
            return Snapshot(identity,revision,tuple(entries),contents,Capabilities(),cancel_event=self.reader.cancel_event)
        finally:self.reader.total_deadline=previous


def snapshot_from_v1(capture,store,reader=None,read_source=None,deadline=None):
    if capture.get('schema')!=SCHEMA:raise RepositoryError('CAPTURE_SCHEMA','Expected a legacy local capture')
    info=capture['repository'];identity=RepositoryIdentity('local',None,info['repository_id'],PurePosixPath(info['root']).name)
    revision=Revision(identity.key,'working',base_commit=info['head'],ref_kind='working',object_format=info['object_format'],observed_at=capture['captured_at'])
    entries=[];contents={};deadline=deadline if deadline is not None else time.monotonic()+120
    for file in capture['files']:
        if reader is not None and reader.cancel_event.is_set():raise RepositoryError('CANCELLED','Source collection cancelled',130)
        if time.monotonic()>deadline:raise RepositoryError('ANALYSIS_TIMEOUT','Source collection exceeded its time budget')
        value=file['working'];entry_info=file['index'].get('0') or file['head'] or next(iter(file['index'].values()),None)
        if entry_info is None:raise RepositoryError('SOURCE_CONTRACT','Legacy file has no mode identity')
        entry=Entry(file['id'],file['path'],file['path_utf8'],entry_info['mode'],value.get('blob_oid'));entries.append(entry)
        raw=None;expected=value.get('sha256');kind=value.get('kind')
        if expected:
            if reader is not None:
                loaded=(read_source or _read_local_source)(reader,store,capture,entry.id,'working')
                raw=store.read_source_bytes(loaded['sha256'])
            else:
                try:raw=store.read_source_bytes(expected)
                except FileNotFoundError:pass
            content=Content(entry.id,'READY' if raw is not None else 'NOT_FETCHED',raw,expected,entry.blob_oid,entry.mode,value.get('size'))
        else:
            availability='ABSENT' if kind=='absent' else 'LIMIT_EXCEEDED' if kind=='oversized' else 'UNAVAILABLE'
            content=Content(entry.id,availability,blob_oid=entry.blob_oid,mode=entry.mode,unavailable_kind=kind if kind in {'unreadable','oversized','symlink','submodule','not_regular'} else 'unavailable')
        contents[entry.id]=content
    return Snapshot(identity,revision,tuple(entries),contents,LOCAL_CAPABILITIES,True,capture['captured_at'],capture['capture_id'],reader.cancel_event if reader else threading.Event())


def _read_local_source(reader,store,capture,path_id,version,commit=None):
    rawpath=path_bytes(path_id);record=next((f for f in capture['files'] if f['id']==path_id),None)
    identity={'path_id':path_id,'version':version,'commit':commit,'captured_at':now()};entry=None
    if version=='commit':
        commit=oid(commit);identity['commit']=commit;entry=next((x for x in reader.tree(commit) if x['id']==path_id),None)
    elif record is None:raise RepositoryError('PATH_NOT_REGISTERED','Path is outside the capture')
    elif version=='head':entry=record['head'];identity['commit']=capture['repository']['head']
    elif version in ['index','stage1','stage2','stage3']:entry=record['index'].get('0' if version=='index' else version[-1])
    elif version!='working':raise RepositoryError('INVALID_VERSION','Unknown source version')
    if version=='index' and record and any(stage!='0' for stage in record['index']):
        return dict(identity,kind='conflict',text=None,sha256=None,stages=sorted(record['index']))
    if version=='working':
        data,kind=stable_read(reader.root,rawpath)
        if data is None:
            if record['working'].get('sha256') or record['working'].get('kind')!=kind:
                raise RepositoryError('SOURCE_CHANGED','Working file differs from captured state; refresh explicitly',5)
            return dict(identity,kind=kind,text=None,sha256=None)
        value=classify(data)
        if record['working'].get('sha256')!=value['sha256']:raise RepositoryError('SOURCE_CHANGED','Working file differs from captured bytes; refresh explicitly',5)
        identity['current_path']=str(reader.root/os.fsdecode(rawpath))
    elif entry is None:return dict(identity,kind='absent',text=None,sha256=None)
    elif entry['mode'] in ['120000','160000']:
        return dict(identity,kind='symlink' if entry['mode']=='120000' else 'submodule',text=None,oid=entry['oid'],sha256=None)
    else:
        data,size=reader.blob(entry['oid']);identity.update(oid=entry['oid'],mode=entry['mode'])
        if data is None:return dict(identity,kind='oversized',text=None,size=size,sha256=None)
        value=classify(data)
    return dict(identity,**value,snapshot_path=store.source(data))
