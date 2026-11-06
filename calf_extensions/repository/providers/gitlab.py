"""Explicit GitLab.com pinned snapshots from paginated trees and exact raw blobs."""
import threading
import time
from ..http_reader import Budget,HTTPError,HTTPReader,RequestSpec
from ..model import RepositoryError,SOURCE_LIMIT,TOTAL_SOURCE_LIMIT,canonical,digest,git_blob_oid,oid,path_bytes,path_record
from ..registrations import canonical_url
from .base import Capabilities,Content,Entry,RepositoryIdentity,Revision,Snapshot

CAPABILITIES=Capabilities()
MODES={'100644':'blob','100755':'blob','120000':'blob','160000':'commit','040000':'tree'}
PARTIAL_ERRORS={'REQUEST_LIMIT','HTTP_TIMEOUT','RATE_LIMITED','HTTP_RESPONSE_LIMIT','INVENTORY_LIMIT','METADATA_LIMIT','TREE_DEPTH_LIMIT'}


def check(condition,code='GITLAB_RESPONSE_INVALID'):
    if not condition:raise RepositoryError(code,'GitLab source did not satisfy the pinned read contract')


def sha1(value):return oid(value,40)


def tree_row(item):
    check(isinstance(item,dict));name=item.get('path');mode=item.get('mode')
    check(isinstance(name,str) and '\ufffd' not in name,'PATH_UNREPRESENTABLE')
    try:raw=name.encode('utf-8',errors='strict');record=path_record(raw);path_bytes(record['id'])
    except (UnicodeError,RepositoryError):raise RepositoryError('PATH_UNREPRESENTABLE','GitLab path cannot preserve exact bytes') from None
    check(item.get('name')==name.rsplit('/',1)[-1] and mode in MODES and item.get('type')==MODES[mode])
    check(len(raw.split(b'/'))<=128,'TREE_DEPTH_LIMIT')
    return raw,{'mode':mode,'sha':sha1(item.get('id'))}


class GitLabSource:
    capabilities=CAPABILITIES
    def __init__(self,registration,reader=None,*,cancel=None,budget=None):
        check(registration.provider=='gitlab' and registration.enabled and registration.repository_id is not None,'SOURCE_UNVERIFIED')
        self.registration=registration;self.reader=reader or HTTPReader(registration)
        check(self.reader.registration.connection_key==registration.connection_key,'SOURCE_MISMATCH')
        self.cancel_event=cancel if cancel is not None else threading.Event();self.budget=budget or Budget()
        self.identity=RepositoryIdentity('gitlab',registration.origin,registration.repository_id,registration.path)
        self.report={'provider':'gitlab','operation':'pinned_snapshot','inventory_complete':False,'reasons':[],'metadata_bytes':0,'requests':0,'tree_pages':0,
                     'tree_oid':None,'tree_oid_reason':'NOT_EXPOSED_BY_GITLAB_COMMIT_API','inventory_verification':'PINNED_API_PAGINATION_AND_PATH_CONSISTENCY'}
    def close(self):self.reader.close()
    def _active(self):
        if self.cancel_event.is_set():raise HTTPError('CANCELLED')
        if time.monotonic()>=self.budget.deadline:raise HTTPError('HTTP_TIMEOUT')
    def _account(self,response):
        if response.spec.operation!='blob':
            self.report['metadata_bytes']+=len(response.body)
            check(self.report['metadata_bytes']<=32*SOURCE_LIMIT,'METADATA_LIMIT')
        return response
    def _request(self,spec):
        self._active()
        try:return self._account(self.reader.request(spec,self.cancel_event,self.budget))
        finally:self.report['requests']=self.budget.used
    def _json(self,spec):return self._request(spec).json()
    def _identity(self):
        value=self._json(RequestSpec('identity'))
        check(isinstance(value,dict) and type(value.get('id')) is int and str(value['id'])==self.registration.repository_id,'IDENTITY_MISMATCH')
        check(isinstance(value.get('path_with_namespace'),str))
        check(canonical_url('gitlab','https://gitlab.com/'+value['path_with_namespace'])==self.registration.effective_url,'REGISTRATION_STALE')
    def _commit(self,identity):
        value=self._json(RequestSpec('commit',sha1(identity)))
        check(isinstance(value,dict) and value.get('id')==identity and isinstance(value.get('parent_ids'),list))
        check(len(value['parent_ids'])<=1000);self.report['parents']=[sha1(v) for v in value['parent_ids']]
    def pin(self,ref_kind,ref_name=None):
        check(ref_kind in {'branch','tag','commit'} and isinstance(ref_name,str) and bool(ref_name),'INVALID_REF')
        spec=RequestSpec(ref_kind,ref_name)
        if ref_kind=='commit':sha1(ref_name)
        else:
            parts=ref_name.split('/')
            check(ref_name!='@' and not ref_name.endswith('.') and '..' not in ref_name and '@{' not in ref_name and not any(c in ref_name for c in ' \\~^:?*[') and all(p and not p.startswith('.') and not p.endswith('.lock') for p in parts),'INVALID_REF')
        self._identity()
        if ref_kind=='commit':identity=ref_name
        else:
            value=self._json(spec)
            check(isinstance(value,dict) and value.get('name')==ref_name and isinstance(value.get('commit'),dict),'REF_MISMATCH')
            # GitLab's tag endpoint exposes the dereferenced commit, including annotated tags.
            identity=sha1(value['commit'].get('id'))
        self._commit(identity)
        return Revision(self.identity.key,'commit',commit_id=identity,ref_kind=ref_kind,ref_name=ref_name,object_format='sha1')
    def _inventory(self,commit):
        rows={};complete=False
        try:
            response=self._request(RequestSpec('tree',commit,True))
            while True:
                self._active();page=response.json();check(isinstance(page,list) and len(page)<=100)
                self.report['tree_pages']+=1
                for item in page:
                    check(len(rows)<50000,'INVENTORY_LIMIT');raw,row=tree_row(item)
                    check(raw not in rows,'TREE_PAGE_OVERLAP');rows[raw]=row
                try:next_page=self.reader.follow_next(response,self.cancel_event,self.budget)
                finally:self.report['requests']=self.budget.used
                if next_page is None:
                    if len(page)==100:self.report['reasons'].append('PAGINATION_END_UNKNOWN')
                    else:complete=True
                    break
                check(bool(page),'PAGINATION_EMPTY_INTERMEDIATE')
                response=self._account(next_page)
        except RepositoryError as error:
            if error.code not in PARTIAL_ERRORS:raise
            self.report['reasons'].append(error.code)
        for raw in rows:
            parent=raw.rpartition(b'/')[0]
            while parent:
                if parent in rows:check(rows[parent]['mode']=='040000','TREE_PATH_CONFLICT')
                else:check(not complete,'TREE_PARENT_MISSING')
                parent=parent.rpartition(b'/')[0]
        self.report['inventory_digest']=digest(canonical([[raw.decode('utf-8'),row['mode'],row['sha']] for raw,row in sorted(rows.items())]))
        return rows,complete
    def _blob(self,identity):
        raw=self._request(RequestSpec('blob',identity)).body
        check(isinstance(raw,bytes) and len(raw)<=SOURCE_LIMIT,'BLOB_SIZE_MISMATCH')
        check(git_blob_oid(raw,'sha1')==identity,'BLOB_IDENTITY_MISMATCH')
        return raw
    def snapshot(self,revision,*,path_ids=None):
        check(isinstance(revision,Revision) and revision.repository_key==self.identity.key and revision.kind=='commit' and revision.object_format=='sha1' and revision.tree_oid is None,'SOURCE_MISMATCH')
        sha1(revision.commit_id)
        if path_ids is not None:
            check(isinstance(path_ids,(set,frozenset)) and len(path_ids)<=50000,'INVALID_PATH_SELECTION')
            for value in path_ids:path_bytes(value)
        self._commit(revision.commit_id);rows,complete=self._inventory(revision.commit_id);entries=[];contents={};remaining=TOTAL_SOURCE_LIMIT;cache={};stopped=None
        for raw,row in sorted(rows.items()):
            if row['mode']=='040000':continue
            self._active();entry=Entry(**path_record(raw),mode=row['mode'],blob_oid=row['sha']);entries.append(entry)
            metadata={'blob_oid':entry.blob_oid,'mode':entry.mode}
            if entry.mode in {'120000','160000'}:
                content=Content(entry.id,'UNAVAILABLE',**metadata,unavailable_kind='symlink' if entry.mode=='120000' else 'submodule',reason='NO_TARGET_TRAVERSAL')
            elif path_ids is not None and entry.id not in path_ids:content=Content(entry.id,'NOT_FETCHED',**metadata,reason='NOT_SELECTED')
            elif stopped:content=Content(entry.id,'NOT_FETCHED',**metadata,reason=stopped)
            elif remaining<=0:content=Content(entry.id,'LIMIT_EXCEEDED',**metadata,reason='TOTAL_SOURCE_LIMIT')
            else:
                try:
                    if row['sha'] not in cache:cache[row['sha']]=self._blob(row['sha'])
                    data=cache[row['sha']];size=len(data)
                    if size>remaining:content=Content(entry.id,'LIMIT_EXCEEDED',**metadata,size=size,reason='TOTAL_SOURCE_LIMIT')
                    else:content=Content(entry.id,'READY',data,**metadata,size=size);remaining-=size
                except RepositoryError as error:
                    if error.code not in PARTIAL_ERRORS:raise
                    if error.code!='HTTP_RESPONSE_LIMIT':stopped=error.code
                    self.report['reasons'].append(error.code)
                    content=Content(entry.id,'LIMIT_EXCEEDED' if error.code=='HTTP_RESPONSE_LIMIT' else 'NOT_FETCHED',**metadata,reason=error.code)
            contents[entry.id]=content
        self._active()
        if not stopped and complete:self._identity()
        self.report.update(inventory_complete=complete,files=len(entries),content_ready=sum(c.availability=='READY' for c in contents.values()),content_bytes=TOTAL_SOURCE_LIMIT-remaining)
        self.report['reasons']=list(dict.fromkeys(self.report['reasons']))
        return Snapshot(self.identity,revision,tuple(entries),contents,self.capabilities,complete,cancel_event=self.cancel_event)
