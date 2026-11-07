"""Immutable content contracts, independent of Git, filesystem paths and HTTP."""
from dataclasses import asdict, dataclass, field
from functools import cached_property
from types import MappingProxyType
from typing import Mapping, Protocol
from urllib.parse import urlsplit
import re
import threading
from ..model import RepositoryError, SOURCE_LIMIT, TOTAL_SOURCE_LIMIT, canonical, classify, digest, git_blob_oid, now, oid, path_bytes, path_record

V2_SCHEMA = 'calf.repository.capture.v2'
AVAILABILITY = {'READY', 'ABSENT', 'NOT_FETCHED', 'UNAVAILABLE', 'LIMIT_EXCEEDED', 'IDENTITY_MISMATCH'}
MODES = {'100644', '100755', '120000', '160000'}


def require(condition, message):
    if not condition:raise RepositoryError('SOURCE_CONTRACT', message)


def sha256(value):
    require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None,'Expected a SHA256 identity')
    return value


@dataclass(frozen=True)
class RepositoryIdentity:
    provider: str
    origin: str | None
    repository_id: str
    label: str

    def __post_init__(self):
        require(self.provider in {'local','github','gitlab'},'Unknown source kind')
        require(isinstance(self.repository_id,str) and 0<len(self.repository_id)<=1024,'Invalid repository identity')
        require(isinstance(self.label,str) and len(self.label)<=8192,'Invalid project label')
        if self.provider=='local':require(self.origin is None,'Local sources have no API origin')
        else:
            require(isinstance(self.origin,str),'Hosted sources need an API origin')
            u=urlsplit(self.origin)
            require(u.scheme=='https' and bool(u.hostname) and u.netloc==u.hostname and not u.path and not u.query and not u.fragment,'Expected a canonical HTTPS API origin')

    @property
    def key(self):return digest(canonical([self.provider,self.origin,self.repository_id]))
    @property
    def project_id(self):return self.repository_id if self.provider=='local' else self.key


@dataclass(frozen=True)
class Capabilities:
    working: bool = False
    index: bool = False
    conflict_stages: bool = False
    immutable_revision: bool = True
    provider_permalink: bool = False
    cached_copy_editor: bool = False
    offline_export: bool = False

    def __post_init__(self):require(all(type(x) is bool for x in asdict(self).values()),'Capabilities must be explicit booleans')
    def as_dict(self):return asdict(self)


@dataclass(frozen=True)
class Revision:
    repository_key: str
    kind: str
    commit_id: str | None = None
    base_commit: str | None = None
    ref_kind: str | None = None
    ref_name: str | None = None
    tree_oid: str | None = None
    object_format: str | None = None
    observed_at: str = field(default_factory=now)

    def __post_init__(self):
        sha256(self.repository_key)
        require(self.kind in {'working','commit'},'Invalid revision kind')
        require(self.object_format in {None,'sha1','sha256'},'Unknown object format')
        require(self.ref_kind in {None,'working','head','branch','tag','commit'},'Invalid ref kind')
        require(self.ref_name is None or isinstance(self.ref_name,str) and 0<len(self.ref_name)<=4096 and '\0' not in self.ref_name,'Invalid requested ref')
        require(isinstance(self.observed_at,str) and bool(self.observed_at),'Revision needs observation time')
        length=40 if self.object_format=='sha1' else 64 if self.object_format=='sha256' else None
        for value in [self.commit_id,self.base_commit,self.tree_oid]:
            if value is not None:oid(value,length)
        require(self.kind!='commit' or self.commit_id is not None and self.base_commit is None,'Pinned revision needs a commit')
        require(self.kind!='working' or self.commit_id is None and self.tree_oid is None,'Working bytes are not an immutable commit')


@dataclass(frozen=True)
class Entry:
    id: str
    path: str
    path_utf8: bool
    mode: str
    blob_oid: str | None = None

    def __post_init__(self):
        require(path_record(path_bytes(self.id))=={'id':self.id,'path':self.path,'path_utf8':self.path_utf8},'Path identity mismatch')
        require(type(self.path_utf8) is bool and self.mode in MODES,'Invalid inventory entry')
        if self.blob_oid is not None:oid(self.blob_oid)
    def as_dict(self):return asdict(self)


@dataclass(frozen=True)
class Content:
    path_id: str
    availability: str
    data: bytes | None = field(default=None,repr=False)
    expected_sha256: str | None = None
    blob_oid: str | None = None
    mode: str | None = None
    size: int | None = None
    unavailable_kind: str = 'unavailable'
    reason: str | None = None

    def __post_init__(self):
        path_bytes(self.path_id)
        require(self.availability in AVAILABILITY,'Invalid content availability')
        if self.expected_sha256 is not None:sha256(self.expected_sha256)
        if self.blob_oid is not None:oid(self.blob_oid)
        require(self.mode is None or self.mode in MODES,'Invalid content mode')
        require(self.size is None or type(self.size) is int and self.size>=0,'Invalid content size')
        require(self.unavailable_kind in {'unavailable','unreadable','oversized','symlink','submodule','not_regular'},'Invalid unavailable kind')
        require(self.reason is None or isinstance(self.reason,str) and len(self.reason)<=1024,'Invalid unavailable reason')
        if self.availability=='READY':
            require(isinstance(self.data,bytes) and len(self.data)<=SOURCE_LIMIT,'Ready content needs bounded raw bytes')
            require(self.size is None or self.size==len(self.data),'Raw content size mismatch')
            if self.expected_sha256 is not None and digest(self.data)!=self.expected_sha256:
                raise RepositoryError('SOURCE_CHANGED','Content does not match the expected byte identity',5)
        else:require(self.data is None,'Unavailable content cannot carry bytes')
        if self.availability=='ABSENT':require(self.expected_sha256 is None and self.size is None,'Absence cannot claim file bytes')

    @cached_property
    def byte_sha256(self):return digest(self.data) if self.data is not None else None
    def value(self,version='captured',commit=None,captured_at=None):
        if self.availability=='READY':value=classify(self.data)
        else:value={'kind':'absent' if self.availability=='ABSENT' else 'oversized' if self.availability=='LIMIT_EXCEEDED' else self.unavailable_kind,'text':None,'sha256':None}
        value.setdefault('size',self.size)
        return dict(value,expected_sha256=self.expected_sha256,path_id=self.path_id,version=version,commit=commit,captured_at=captured_at,
                    availability=self.availability,oid=self.blob_oid,mode=self.mode,reason=self.reason)
    def record(self):
        return {'availability':self.availability,'sha256':self.byte_sha256,'expected_sha256':self.expected_sha256,
                'size':len(self.data) if self.data is not None else self.size,'unavailable_kind':self.unavailable_kind,'reason':self.reason}


@dataclass(frozen=True)
class Snapshot:
    repository: RepositoryIdentity
    revision: Revision
    entries: tuple[Entry,...]
    contents: Mapping[str,Content] = field(repr=False)
    capabilities: Capabilities = field(default_factory=Capabilities)
    inventory_complete: bool = True
    captured_at: str = field(default_factory=now)
    legacy_capture_id: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event,compare=False,repr=False)

    def __post_init__(self):
        require(self.revision.repository_key==self.repository.key,'Revision belongs to another repository')
        require(type(self.inventory_complete) is bool,'Inventory completeness must be explicit')
        require(isinstance(self.captured_at,str) and bool(self.captured_at),'Snapshot needs capture time')
        entries=tuple(self.entries);require(len(entries)<=50000 and all(isinstance(e,Entry) for e in entries),'Invalid inventory')
        ids=[e.id for e in entries];require(len(ids)==len(set(ids)),'Duplicate inventory identity')
        contents=dict(self.contents);require(set(contents)<=set(ids),'Content outside inventory')
        total=0
        for entry in entries:
            value=contents.setdefault(entry.id,Content(entry.id,'NOT_FETCHED'))
            require(isinstance(value,Content) and value.path_id==entry.id,'Content path mismatch')
            require(value.mode in {None,entry.mode} and value.blob_oid in {None,entry.blob_oid},'Content object mismatch')
            require(self.revision.kind=='working' or value.availability!='ABSENT','Inventoried committed content cannot be absent')
            if value.data is not None:
                require(self.revision.kind=='working' or entry.mode not in {'120000','160000'},'Link and submodule contents cannot become ordinary committed source')
                total+=len(value.data)
                if entry.blob_oid and self.revision.object_format and git_blob_oid(value.data,self.revision.object_format)!=entry.blob_oid:
                    raise RepositoryError('SOURCE_CHANGED','Raw bytes do not match the Git blob identity',5)
        require(total<=TOTAL_SOURCE_LIMIT,'Snapshot content budget exceeded')
        if self.repository.provider!='local':
            require(self.revision.kind=='commit' and not any([self.capabilities.working,self.capabilities.index,self.capabilities.conflict_stages]),'Hosted snapshots cannot claim local working/index state')
        if self.legacy_capture_id is not None:sha256(self.legacy_capture_id);require(self.repository.provider=='local','Legacy capture is local only')
        object.__setattr__(self,'entries',entries);object.__setattr__(self,'contents',MappingProxyType(contents))

    @cached_property
    def input_id(self):return digest(canonical(self.manifest()))
    @cached_property
    def snapshot_id(self):return self.legacy_capture_id or self.input_id
    def read_content(self,path_id):
        if self.cancel_event.is_set():raise RepositoryError('CANCELLED','Snapshot read cancelled',130)
        path_bytes(path_id)
        return self.contents.get(path_id,Content(path_id,'ABSENT' if self.inventory_complete else 'NOT_FETCHED'))
    def manifest(self):
        return {'schema':V2_SCHEMA,'repository':asdict(self.repository),'revision':asdict(self.revision),'capabilities':self.capabilities.as_dict(),
                'captured_at':self.captured_at,'inventory_complete':self.inventory_complete,
                'files':[dict(e.as_dict(),content=self.contents[e.id].record()) for e in self.entries]}

    @classmethod
    def from_manifest(cls,data,load_bytes):
        require(isinstance(data,dict) and set(data)=={'schema','repository','revision','capabilities','captured_at','inventory_complete','files'} and data['schema']==V2_SCHEMA,'Invalid v2 snapshot schema')
        require(isinstance(data['files'],list) and len(data['files'])<=50000,'Invalid v2 inventory')
        try:
            repository=RepositoryIdentity(**data['repository']);revision=Revision(**data['revision']);caps=Capabilities(**data['capabilities']);entries=[];contents={};total=0
            for item in data['files']:
                require(isinstance(item,dict) and set(item)=={'id','path','path_utf8','mode','blob_oid','content'},'Invalid v2 entry')
                record=dict(item['content']);require(set(record)=={'availability','sha256','expected_sha256','size','unavailable_kind','reason'},'Invalid content record')
                entry=Entry(**{k:v for k,v in item.items() if k!='content'});require(entry.id not in contents,'Duplicate content identity');entries.append(entry)
                if record['availability']=='READY':
                    require(type(record['size']) is int and 0<=record['size']<=SOURCE_LIMIT,'Invalid retained source size')
                    total+=record['size'];require(total<=TOTAL_SOURCE_LIMIT,'Retained snapshot content budget exceeded')
                raw=load_bytes(sha256(record['sha256'])) if record['availability']=='READY' else None
                require(raw is not None or record['sha256'] is None,'Unavailable content has a raw identity')
                value=Content(entry.id,record['availability'],raw,record['expected_sha256'],entry.blob_oid,entry.mode,record['size'],record['unavailable_kind'],record['reason'])
                require(value.byte_sha256==record['sha256'],'Cached source identity mismatch');contents[entry.id]=value
            result=cls(repository,revision,tuple(entries),contents,caps,data['inventory_complete'],data['captured_at'])
            require(result.manifest()==data,'Noncanonical snapshot metadata')
            return result
        except (TypeError,KeyError,ValueError) as error:raise RepositoryError('SOURCE_CONTRACT','Malformed snapshot fields') from error


class SourceReader(Protocol):
    capabilities: Capabilities
    def pin(self,ref_kind: str,ref_name: str | None=None) -> Revision: ...
    def snapshot(self,revision: Revision) -> Snapshot: ...


@dataclass(frozen=True)
class ComparisonContext:
    left: Snapshot
    right: Snapshot
    basis: str = 'DIRECT_SNAPSHOT'

    def __post_init__(self):
        require(self.left.repository.key==self.right.repository.key,'Comparison belongs to different repositories')
        require(self.basis=='DIRECT_SNAPSHOT','Unsupported comparison basis')
    @property
    def context_id(self):return digest(canonical([self.left.repository.key,self.left.input_id,self.right.input_id,self.basis]))
