"""Explicit GitHub.com pinned snapshots. Never checkout, execute or follow project code."""
import base64
from collections import defaultdict,deque
import hashlib
import threading
import time
from ..http_reader import Budget,HTTPError,HTTPReader,RequestSpec
from ..model import RepositoryError,SOURCE_LIMIT,TOTAL_SOURCE_LIMIT,canonical,git_blob_oid,oid,path_bytes,path_record
from ..registrations import canonical_url
from .base import Capabilities,Content,Entry,RepositoryIdentity,Revision,Snapshot

CAPABILITIES=Capabilities()
MODES={'100644':'blob','100755':'blob','120000':'blob','160000':'commit','040000':'tree'}
PARTIAL_ERRORS={'REQUEST_LIMIT','HTTP_TIMEOUT','RATE_LIMITED','HTTP_RESPONSE_LIMIT','INVENTORY_LIMIT','METADATA_LIMIT','TREE_DEPTH_LIMIT'}


def check(condition,code='GITHUB_RESPONSE_INVALID'):
    if not condition:raise RepositoryError(code,'GitHub source did not satisfy the pinned read contract')


def sha1(value):return oid(value,40)


def tree_rows(value,expected,recursive):
    """Verify complete Git tree bytes, including mode, raw UTF-8 names and order."""
    check(isinstance(value,dict) and value.get('sha')==expected and type(value.get('truncated')) is bool and isinstance(value.get('tree'),list))
    if value['truncated']:return None
    check(len(value['tree'])<=50000,'INVENTORY_LIMIT');rows={}
    for item in value['tree']:
        check(isinstance(item,dict));name=item.get('path');mode=item.get('mode')
        check(isinstance(name,str) and '\ufffd' not in name,'PATH_UNREPRESENTABLE')
        try:raw=name.encode('utf-8',errors='strict');record=path_record(raw);path_bytes(record['id'])
        except (UnicodeError,RepositoryError):raise RepositoryError('PATH_UNREPRESENTABLE','GitHub path cannot preserve exact bytes') from None
        check(recursive or b'/' not in raw);check(raw not in rows and mode in MODES and item.get('type')==MODES[mode])
        identity=sha1(item.get('sha'));size=item.get('size')
        check(size is None or type(size) is int and size>=0)
        rows[raw]={'raw':raw,'mode':mode,'sha':identity,'size':size}
    groups=defaultdict(list);directories={b'':expected}
    for raw,row in rows.items():
        parent,_,name=raw.rpartition(b'/');groups[parent].append((name,row))
        if row['mode']=='040000':directories[raw]=row['sha']
    check(set(groups)<=set(directories))
    for directory,identity in (directories.items() if recursive else [(b'',expected)]):
        children=groups.get(directory,[])
        children.sort(key=lambda item:item[0]+(b'/' if item[1]['mode']=='040000' else b''))
        raw=b''.join((b'40000' if row['mode']=='040000' else row['mode'].encode())+b' '+name+b'\0'+bytes.fromhex(row['sha']) for name,row in children)
        actual=hashlib.sha1(b'tree '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        check(actual==identity,'TREE_IDENTITY_MISMATCH')
    return rows


class GitHubSource:
    capabilities=CAPABILITIES
    def __init__(self,registration,reader=None,*,cancel=None,budget=None):
        check(registration.provider=='github' and registration.enabled and registration.repository_id is not None,'SOURCE_UNVERIFIED')
        self.registration=registration;self.reader=reader or HTTPReader(registration)
        check(self.reader.registration.connection_key==registration.connection_key,'SOURCE_MISMATCH')
        self.cancel_event=cancel if cancel is not None else threading.Event();self.budget=budget or Budget()
        self.identity=RepositoryIdentity('github',registration.origin,registration.repository_id,registration.path)
        self.report={'provider':'github','operation':'pinned_snapshot','inventory_complete':False,'reasons':[],'metadata_bytes':0,'requests':0}
    def close(self):self.reader.close()
    def _active(self):
        if self.cancel_event.is_set():raise HTTPError('CANCELLED')
        if time.monotonic()>=self.budget.deadline:raise HTTPError('HTTP_TIMEOUT')
    def _json(self,spec):
        self._active()
        try:response=self.reader.request(spec,self.cancel_event,self.budget)
        finally:self.report['requests']=self.budget.used
        if spec.operation!='blob':
            self.report['metadata_bytes']+=len(response.body)
            check(self.report['metadata_bytes']<=32*SOURCE_LIMIT,'METADATA_LIMIT')
        return response.json()
    def _identity(self):
        value=self._json(RequestSpec('identity'))
        check(isinstance(value,dict) and type(value.get('id')) is int and str(value['id'])==self.registration.repository_id,'IDENTITY_MISMATCH')
        check(isinstance(value.get('full_name'),str))
        target=canonical_url('github','https://github.com/'+value['full_name'])
        check(target==self.registration.effective_url,'REGISTRATION_STALE')
    def _commit(self,identity):
        value=self._json(RequestSpec('commit',sha1(identity)))
        check(isinstance(value,dict) and value.get('sha')==identity and isinstance(value.get('tree'),dict))
        tree=sha1(value['tree'].get('sha'));parents=value.get('parents');check(isinstance(parents,list) and len(parents)<=1000)
        check(all(isinstance(parent,dict) for parent in parents));self.report['parents']=[sha1(parent.get('sha')) for parent in parents]
        return tree
    def pin(self,ref_kind,ref_name=None):
        check(ref_kind in {'branch','tag','commit'},'INVALID_REF')
        check(isinstance(ref_name,str) and bool(ref_name),'INVALID_REF')
        # Validate typed refs before any provider request.
        spec=RequestSpec(ref_kind,ref_name)
        if ref_kind=='commit':sha1(ref_name)
        else:
            parts=ref_name.split('/')
            check(ref_name!='@' and not ref_name.endswith('.') and '..' not in ref_name and '@{' not in ref_name and not any(c in ref_name for c in ' \\~^:?*[') and all(p and not p.startswith('.') and not p.endswith('.lock') for p in parts),'INVALID_REF')
        self._identity()
        if ref_kind=='commit':identity=sha1(ref_name)
        else:
            value=self._json(spec);check(isinstance(value,dict))
            if ref_kind=='branch':
                check(value.get('name')==ref_name and isinstance(value.get('commit'),dict),'REF_MISMATCH');identity=sha1(value['commit'].get('sha'))
            else:
                check(value.get('ref')=='refs/tags/'+ref_name,'REF_MISMATCH');target=value.get('object');seen=set()
                for _ in range(16):
                    check(isinstance(target,dict));identity=sha1(target.get('sha'));kind=target.get('type')
                    if kind=='commit':break
                    check(kind=='tag' and identity not in seen,'TAG_TARGET_UNSUPPORTED');seen.add(identity)
                    value=self._json(RequestSpec('tag_object',identity));check(isinstance(value,dict) and value.get('sha')==identity)
                    target=value.get('object')
                else:raise RepositoryError('TAG_DEPTH_LIMIT','Annotated tag exceeds the dereference bound')
        tree=self._commit(identity)
        return Revision(self.identity.key,'commit',commit_id=identity,ref_kind=ref_kind,ref_name=ref_name,tree_oid=tree,object_format='sha1')
    def _inventory(self,tree):
        try:
            value=self._json(RequestSpec('tree',tree,True));rows=tree_rows(value,tree,True)
            if rows is not None:self.report['tree_strategy']='RECURSIVE_VERIFIED';return rows,True
            self.report['tree_strategy']='SUBTREE_FALLBACK';queue=deque([(b'',tree,0)]);rows={};cache={};complete=True
            while queue:
                self._active();prefix,identity,depth=queue.popleft();check(depth<=128,'TREE_DEPTH_LIMIT')
                if identity not in cache:cache[identity]=tree_rows(self._json(RequestSpec('tree',identity)),identity,False)
                children=cache[identity]
                if children is None:complete=False;self.report['reasons'].append('TRUNCATED_NONRECURSIVE_TREE');continue
                for name,row in children.items():
                    check(len(rows)<50000,'INVENTORY_LIMIT');path=prefix+b'/'+name if prefix else name;check(path not in rows)
                    rows[path]=dict(row,raw=path)
                    if row['mode']=='040000':queue.append((path,row['sha'],depth+1))
            return rows,complete
        except RepositoryError as error:
            if error.code not in PARTIAL_ERRORS:raise
            self.report['reasons'].append(error.code)
            return locals().get('rows') or {},False
    def _blob(self,row):
        value=self._json(RequestSpec('blob',row['sha']))
        check(isinstance(value,dict) and value.get('sha')==row['sha'],'BLOB_IDENTITY_MISMATCH')
        size=value.get('size');encoded=value.get('content')
        check(type(size) is int and size>=0 and value.get('encoding')=='base64' and isinstance(encoded,str))
        if size>SOURCE_LIMIT:return None,size
        try:raw=base64.b64decode(encoded.replace('\n','').replace('\r',''),validate=True)
        except (ValueError,UnicodeError):raise RepositoryError('BLOB_ENCODING_INVALID','GitHub blob Base64 is invalid') from None
        check(len(raw)==size and (row['size'] is None or row['size']==size),'BLOB_SIZE_MISMATCH')
        check(git_blob_oid(raw,'sha1')==row['sha'],'BLOB_IDENTITY_MISMATCH')
        return raw,size
    def snapshot(self,revision,*,path_ids=None):
        check(isinstance(revision,Revision) and revision.repository_key==self.identity.key and revision.kind=='commit' and revision.object_format=='sha1','SOURCE_MISMATCH')
        sha1(revision.commit_id);sha1(revision.tree_oid)
        if path_ids is not None:
            check(isinstance(path_ids,(set,frozenset)) and len(path_ids)<=50000,'INVALID_PATH_SELECTION')
            for value in path_ids:path_bytes(value)
        check(self._commit(revision.commit_id)==revision.tree_oid,'REVISION_MISMATCH')
        rows,complete=self._inventory(revision.tree_oid);entries=[];contents={};remaining=TOTAL_SOURCE_LIMIT;cache={};stopped=None
        for raw,row in sorted(rows.items()):
            if row['mode']=='040000':continue
            self._active();entry=Entry(**path_record(raw),mode=row['mode'],blob_oid=row['sha']);entries.append(entry)
            metadata={'blob_oid':entry.blob_oid,'mode':entry.mode,'size':row['size']}
            if entry.mode in {'120000','160000'}:
                content=Content(entry.id,'UNAVAILABLE',**metadata,unavailable_kind='symlink' if entry.mode=='120000' else 'submodule',reason='NO_TARGET_TRAVERSAL')
            elif path_ids is not None and entry.id not in path_ids:
                content=Content(entry.id,'NOT_FETCHED',**metadata,reason='NOT_SELECTED')
            elif stopped:content=Content(entry.id,'NOT_FETCHED',**metadata,reason=stopped)
            elif row['size'] is not None and row['size']>min(SOURCE_LIMIT,remaining):
                content=Content(entry.id,'LIMIT_EXCEEDED',**metadata,reason='SOURCE_LIMIT' if row['size']>SOURCE_LIMIT else 'TOTAL_SOURCE_LIMIT')
            else:
                try:
                    if row['sha'] not in cache:cache[row['sha']]=self._blob(row)
                    data,size=cache[row['sha']]
                    check(row['size'] is None or size==row['size'],'BLOB_SIZE_MISMATCH')
                    if data is None or size>remaining:content=Content(entry.id,'LIMIT_EXCEEDED',blob_oid=entry.blob_oid,mode=entry.mode,size=size,reason='SOURCE_LIMIT' if data is None else 'TOTAL_SOURCE_LIMIT')
                    else:content=Content(entry.id,'READY',data,blob_oid=entry.blob_oid,mode=entry.mode,size=size);remaining-=size
                except RepositoryError as error:
                    if error.code not in PARTIAL_ERRORS:raise
                    if error.code!='HTTP_RESPONSE_LIMIT':stopped=error.code
                    self.report['reasons'].append(error.code)
                    content=Content(entry.id,'LIMIT_EXCEEDED' if error.code=='HTTP_RESPONSE_LIMIT' else 'NOT_FETCHED',**metadata,reason=error.code)
            contents[entry.id]=content
        # No active map is replaced here. Identity/cancellation must still hold before return.
        self._active()
        if not stopped and complete:self._identity()
        self.report.update(inventory_complete=complete,files=len(entries),content_ready=sum(c.availability=='READY' for c in contents.values()),content_bytes=TOTAL_SOURCE_LIMIT-remaining)
        self.report['reasons']=list(dict.fromkeys(self.report['reasons']))
        return Snapshot(self.identity,revision,tuple(entries),contents,self.capabilities,complete,cancel_event=self.cancel_event)
