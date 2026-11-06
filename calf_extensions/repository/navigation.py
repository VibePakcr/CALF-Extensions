"""Owned collection jobs and immutable navigation over retained provider snapshots."""
from dataclasses import asdict,dataclass,field,replace
import json
import os
from pathlib import Path,PurePosixPath
import re
import threading
import time
from urllib.parse import quote
import uuid
from .analyze import analyze_snapshot
from .capture import Store
from .compare import compare,compare_pair
from .http_reader import Budget,HTTPReader,RequestSpec,strict_json
from .model import RepositoryError,canonical,classify,digest,now,path_bytes,validate_navigation,validate_settings
from .providers.base import Capabilities,ComparisonContext,Content,Snapshot
from .registrations import Registry,canonical_url,source_id

SCHEMA='calf.repository.view.v2'
TERMINAL={'SUCCEEDED','SAVED_PARTIAL','FAILED','CANCELLED','SUPERSEDED'}
PARTIAL={'REQUEST_LIMIT','RATE_LIMITED','HTTP_TIMEOUT','HTTP_RESPONSE_LIMIT','METADATA_LIMIT','INVENTORY_LIMIT'}


def require(value,code='NAVIGATION_CONTRACT'):
    if not value:raise RepositoryError(code,'Navigation request did not satisfy its retained-source contract')


def identity(value):
    require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value),'INVALID_CONTEXT')
    return value


def outside_git(path):
    for parent in [path,*path.parents]:
        require(not ((parent/'.git').exists() or parent.name=='.git' or (parent/'HEAD').is_file() and ((parent/'objects').is_dir() or (parent/'commondir').is_file())),'OUTPUT_IN_REPOSITORY')


def changed_paths(left,right):
    require(left is None or left.repository.key==right.repository.key,'SOURCE_MISMATCH')
    a={e.id:e for e in left.entries} if left else {};b={e.id:e for e in right.entries};complete=right.inventory_complete and (left is None or left.inventory_complete);items=[];unchanged=0
    for key in sorted(set(a)|set(b)):
        x,y=a.get(key),b.get(key)
        if x is None:status='ADD' if left is None or left.inventory_complete else 'UNKNOWN'
        elif y is None:status='DELETE' if right.inventory_complete else 'UNKNOWN'
        elif x.blob_oid and x.blob_oid==y.blob_oid:status='UNCHANGED' if x.mode==y.mode else 'MODE'
        else:status='MODIFY'
        if status=='UNCHANGED':unchanged+=1;continue
        e=y or x;items.append({'id':key,'path':e.path,'status':status,'left_mode':x.mode if x else None,'right_mode':y.mode if y else None,'left_oid':x.blob_oid if x else None,'right_oid':y.blob_oid if y else None})
    adds={};deletes={}
    for item in items:
        if item['status']=='ADD':adds.setdefault(item['right_oid'],[]).append(item)
        if item['status']=='DELETE':deletes.setdefault(item['left_oid'],[]).append(item)
    for oid,values in adds.items():
        if oid and len(values)==1 and len(deletes.get(oid,[]))==1:
            values[0]['same_blob_path_hint']=deletes[oid][0]['path'];deletes[oid][0]['same_blob_path_hint']=values[0]['path']
    return {'complete':complete,'total':len(items),'unchanged':unchanged,'unknown':sum(i['status']=='UNKNOWN' for i in items),'items':items,'basis':'DIRECT_SNAPSHOT'}


class RetainedView:
    def __init__(self,context,record,store):
        self.context_id=identity(context);self.record=record;self.store=store
        require(record.get('schema')==SCHEMA and record.get('source_id')==source_id(record.get('source_id')))
        self.right=store.load_snapshot(identity(record['right']));self.left=store.load_snapshot(identity(record['left'])) if record['left'] is not None else None
        require(self.right.repository.provider in {'github','gitlab'} and self.right.revision.kind=='commit')
        require(self.left is None or self.left.repository.key==self.right.repository.key,'SOURCE_MISMATCH')
        self.graph=validate_navigation(record['graph']);require(self.graph['capture_id']==self.right.snapshot_id and self.graph['input_snapshot_id']==self.right.input_id and self.graph['repository_key']==self.right.repository.key)
        require(canonical_url(self.right.repository.provider,record['source_url'])==record['source_url'])
        if self.left is None:require(record['empty_baseline']=={'commit':self.right.revision.commit_id,'parents':[],'basis':'FIRST_PARENT_NONE'} and record['provenance']['right_inventory'].get('parents')==[],'EMPTY_BASELINE_UNPROVEN')
        else:require(record['empty_baseline'] is None)
        self.changes=changed_paths(self.left,self.right);self._entries={e.id:e for s in [self.left,self.right] if s for e in s.entries}
    @property
    def source_id(self):return self.record['source_id']
    def coverage(self):
        regular=lambda s:[c for c in s.contents.values() if c.mode in {'100644','100755'}] if s else []
        a,b=regular(self.left),regular(self.right);expected=len(a)+len(b);ready=sum(c.availability=='READY' for c in [*a,*b])
        complete=self.changes['complete'] and ready==expected
        text_ready=0
        for item in self.changes['items']:
            values=[self.left.read_content(item['id']) if self.left else Content(item['id'],'ABSENT'),self.right.read_content(item['id'])]
            if all(c.availability=='ABSENT' or c.availability=='READY' and classify(c.data).get('text') is not None for c in values):text_ready+=1
        return {'state':'COMPLETE' if complete else 'PARTIAL','inventory':{'right_files':len(self.right.entries),'right_complete':self.right.inventory_complete,'left_files':len(self.left.entries) if self.left else 0,'left_complete':self.left.inventory_complete if self.left else True},'sources':{'ready':ready,'expected_regular':expected,'right_ready':sum(c.availability=='READY' for c in b),'left_ready':sum(c.availability=='READY' for c in a)},'analysis':dict(self.graph['coverage'],runtime_verified=False),'changed_paths':{k:v for k,v in self.changes.items() if k!='items'},'diff':{'basis':'DIRECT_SNAPSHOT','text_comparable':text_ready,'candidates':self.changes['total']},'runtime_verified':False}
    def payload(self):
        coverage=self.coverage();right=self.right.revision;left=self.left.revision if self.left else None
        return {'graph':self.graph,'capture':{'schema':'calf.repository.capture.v2','capture_id':self.right.snapshot_id,'captured_at':self.right.captured_at,'repository':asdict(self.right.repository),'revision':asdict(right),'coverage':coverage},'view':{'context_id':self.context_id,'source_id':self.source_id,'provider':self.right.repository.provider,'source_url':self.record['source_url'],'navigation_id':self.graph['navigation_id'],'right_snapshot':self.right.snapshot_id,'left_snapshot':self.left.snapshot_id if self.left else None,'right_commit':right.commit_id,'left_commit':left.commit_id if left else None,'ref_kind':right.ref_kind,'ref_name':right.ref_name,'comparison_basis':'DIRECT_SNAPSHOT','empty_baseline':self.left is None,'left_ref_kind':self.record.get('comparison_request',{}).get('left_kind') or 'parent','left_ref_name':self.record.get('comparison_request',{}).get('left_ref') or '','coverage':coverage},'source_capabilities':Capabilities(provider_permalink=True,cached_copy_editor=True,offline_export=True).as_dict()}
    def source(self,path,version='captured'):
        path_bytes(path);require(path in self._entries,'PATH_NOT_REGISTERED');require(version in {'captured','left','right'},'INVALID_VERSION')
        snap=self.left if version=='left' else self.right
        value=(snap.read_content(path) if snap else Content(path,'ABSENT')).value(version,snap.revision.commit_id if snap else None,snap.captured_at if snap else self.right.captured_at)
        value.update(path=self._entries[path].path,view_context_id=self.context_id,revision_kind='commit' if snap else 'EMPTY_BASELINE',retained_copy_available=value.get('text') is not None)
        if snap and value['kind']!='absent':value['provider_url']=self.record['source_url']+('/blob/' if snap.repository.provider=='github' else '/-/blob/')+snap.revision.commit_id+'/'+quote(self._entries[path].path,safe='/')
        return value
    def comparison(self,path):
        require(path in self._entries,'PATH_NOT_REGISTERED')
        if self.left:result=compare_pair(ComparisonContext(self.left,self.right),path)
        else:
            result=compare(self.source(path,'left'),self.source(path,'right'));result.update(comparison_basis='DIRECT_SNAPSHOT',context_id=digest(canonical([self.right.repository.key,None,self.right.input_id,self.record['empty_baseline']])),left_snapshot=None,right_snapshot=self.right.snapshot_id)
        result['left'].update(path=self._entries[path].path);result['right'].update(path=self._entries[path].path)
        result.update(view_context_id=self.context_id,mode_changed=result['left'].get('mode') is not None and result['right'].get('mode') is not None and result['left']['mode']!=result['right']['mode'])
        if len(canonical(result))>8*1024*1024:
            result=dict(result,state='PARTIAL',reason='DIFF_RESPONSE_LIMIT',lines=[])
            for side in ['left','right']:result[side]=dict(result[side],text=None,text_omitted_from_response=True)
        return result


class ViewStore:
    def __init__(self,store):self.store=store;self.root=store.directory/'navigation-v2'
    def _check(self,create=False):
        require(not self.root.is_symlink(),'VIEW_PATH_REFUSED')
        if not self.root.exists():
            if not create:return False
            self.root.mkdir(mode=0o700);(self.root/'schema').write_bytes(SCHEMA.encode())
        marker=self.root/'schema';require(marker.is_file() and not marker.is_symlink() and marker.stat().st_size==len(SCHEMA) and marker.read_bytes()==SCHEMA.encode(),'VIEW_PATH_REFUSED')
        for name in ['records','summaries','candidates','editor-copies']:
            p=self.root/name;require(not p.is_symlink() and (not p.exists() or p.is_dir()),'VIEW_PATH_REFUSED')
            if create:p.mkdir(exist_ok=True,mode=0o700)
        return True
    def _read(self,path,limit):
        require(not path.is_symlink() and path.is_file() and path.stat().st_size<=limit,'VIEW_PATH_REFUSED');return path.read_bytes()
    def prepare(self,record):
        self._check(True);raw=canonical(record);require(len(raw)<=32*1024*1024,'NAVIGATION_LIMIT');context=digest(raw);candidate=self.root/'candidates'/(str(uuid.uuid4())+'.json')
        with candidate.open('xb') as f:f.write(raw)
        return context,candidate
    def commit(self,context,candidate,view):
        path=self.root/'records'/(identity(context)+'.json')
        try:os.link(candidate,path)
        except FileExistsError:require(self._read(path,32*1024*1024)==candidate.read_bytes(),'VIEW_CONFLICT')
        finally:candidate.unlink(missing_ok=True)
        summary={'context_id':context,'source_id':view.source_id,'captured_at':view.right.captured_at,'right_commit':view.right.revision.commit_id,'left_commit':view.left.revision.commit_id if view.left else None,'navigation_id':view.graph['navigation_id'],'ref_kind':view.right.revision.ref_kind,'ref_name':view.right.revision.ref_name,'state':view.coverage()['state']}
        target=self.root/'summaries'/(context+'.json');raw=canonical(summary)
        try:
            with target.open('xb') as f:f.write(raw)
        except FileExistsError:require(self._read(target,16384)==raw,'VIEW_CONFLICT')
    def load(self,context):
        identity(context);require(self._check(),'VIEW_NOT_FOUND');raw=self._read(self.root/'records'/(context+'.json'),32*1024*1024);require(digest(raw)==context,'VIEW_CHANGED');return RetainedView(context,strict_json(raw),self.store)
    def summaries(self,selected=None):
        if not self._check():return []
        directory=self.root/'summaries';require(not directory.is_symlink(),'VIEW_PATH_REFUSED');paths=list(directory.glob('*.json'));require(len(paths)<=1000,'VIEW_LIMIT');values=[]
        for p in paths:
            value=strict_json(self._read(p,16384));require(value.get('context_id')==identity(p.stem));source_id(value['source_id'])
            if selected is None or value['source_id']==selected:values.append(value)
        return sorted(values,key=lambda v:(v['captured_at'],v['context_id']),reverse=True)
    def editor_copy(self,view,path,version,line):
        value=view.source(path,version);require(value.get('retained_copy_available'),'SOURCE_UNAVAILABLE');require(type(line) is int and 1<=line<=200000,'INVALID_LINE');self._check(True)
        snap=view.left if version=='left' else view.right;content=snap.read_content(path);raw=self.store.read_source_bytes(content.byte_sha256);require(raw==content.data,'SOURCE_CACHE_CHANGED')
        suffix=PurePosixPath(value['path']).suffix.lower();suffix=suffix if suffix in {'.py','.rs','.js','.ts','.md','.txt','.json','.toml','.yaml','.yml','.css','.sh'} else '.txt'
        target=self.root/'editor-copies'/(content.byte_sha256+'-'+str(uuid.uuid4())+suffix)
        require(len(list(target.parent.iterdir()))<1000,'EDITOR_COPY_LIMIT')
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o600);require(digest(target.read_bytes())==content.byte_sha256,'EDITOR_COPY_CHANGED')
        return {'path':str(target),'line':line,'sha256':content.byte_sha256,'commit':value['commit'],'blob_oid':content.blob_oid,'kind':'RETAINED_COPY','view_context_id':view.context_id}


@dataclass
class Collection:
    id: str
    source_id: str
    generation: int
    cancel: threading.Event=field(default_factory=threading.Event,repr=False)
    state: str='QUEUED'
    phase: str='QUEUED'
    started_at: str=field(default_factory=now)
    finished_at: str | None=None
    reader: object=field(default=None,repr=False)
    thread: object=field(default=None,repr=False)
    result: dict | None=None
    error: dict | None=None
    def public(self):
        report=self.reader.report if self.reader is not None else {}
        return {'id':self.id,'source_id':self.source_id,'state':self.state,'phase':self.phase,'started_at':self.started_at,'finished_at':self.finished_at,'requests':report.get('requests',0),'files':report.get('files',0),'content_ready':report.get('content_ready',0),'result':self.result,'error':self.error}


class NavigationHub:
    def __init__(self,data_dir,local=None,hosted=None,settings=None,source_factory=None):
        from .hosted import HostedServices
        directory=Path(data_dir).expanduser().resolve();outside_git(directory);self.store=local.store if local else Store(directory,create=True);self.views=ViewStore(self.store);self.local=local;self.hosted=hosted or HostedServices(directory);self.settings=validate_settings(settings if settings is not None else local.settings if local else {});self._factory=source_factory or self._provider;self.lock=threading.RLock();self.jobs={};self.generation=0;self.selected='local' if local else None;self.active=None;self.closed=False
    @staticmethod
    def _provider(registration,cancel,budget):
        if registration.provider=='github':
            from .providers.github import GitHubSource
            return GitHubSource(registration,cancel=cancel,budget=budget)
        from .providers.gitlab import GitLabSource
        return GitLabSource(registration,cancel=cancel,budget=budget)
    def _bump(self):
        require(not self.closed,'SERVICE_CLOSED');self.generation+=1
        for job in self.jobs.values():
            if job.state not in TERMINAL:job.cancel.set()
    def sources(self):
        values=[dict(r.public(),kind='hosted') for r in self.hosted.registry.list(include_disabled=True)]
        if self.local:values.insert(0,{'id':'local','provider':'local','url':str(self.local.reader.root),'kind':'local','enabled':True})
        with self.lock:return {'sources':values,'selected':self.selected,'active_source':self.active.source_id if self.active else 'local' if self.local else None}
    def select(self,source=None,context=None):
        view=None
        if context is not None:view=self.views.load(context);self.hosted.registry.get(view.source_id,include_disabled=True);source=view.source_id
        elif source=='local':require(self.local is not None,'SOURCE_NOT_FOUND')
        else:
            self.hosted.registry.get(source,include_disabled=True);summaries=self.views.summaries(source)
            complete=[item for item in summaries if item['state']=='COMPLETE']
            if complete:view=self.views.load(complete[0]['context_id'])
        with self.lock:
            self._bump();self.selected=source
            if view is not None:self.active=view
            elif source=='local':self.active=None
        return self.payload()
    def _current(self,job):return not job.cancel.is_set() and not self.closed and job.generation==self.generation
    def _require_job(self,job):require(self._current(job),'CANCELLED')
    def _phase(self,job,phase):
        with self.lock:self._require_job(job);job.phase=phase
    def collect(self,source,kind,name,left_kind=None,left_name=None):
        registration=self.hosted.registry.get(source);require(kind in {'branch','tag','commit'} and isinstance(name,str) and 0<len(name)<=4096,'INVALID_REF');require((left_kind is None)==(left_name is None) and (left_kind is None or left_kind in {'branch','tag','commit'} and isinstance(left_name,str) and 0<len(left_name)<=4096),'INVALID_REF')
        with self.lock:
            require(len(self.jobs)<1000 and sum(j.state not in TERMINAL for j in self.jobs.values())<8,'JOB_LIMIT');self._bump();self.selected=source;job=Collection(str(uuid.uuid4()),source,self.generation);self.jobs[job.id]=job;job.thread=threading.Thread(target=self._run,args=(job,registration,kind,name,left_kind,left_name),name='calf-navigation-collection');job.thread.start();return job.public()
    def _verify(self,job,registration,budget):
        if registration.repository_id is not None:return registration
        client=self.hosted._factory(registration)
        try:metadata=client.request(RequestSpec('identity'),job.cancel,budget).json()
        finally:client.close()
        with self.lock:self._require_job(job);return self.hosted.registry.bind(registration.id,registration.version,metadata)
    def _materialize(self,reader,revision,inventory):
        try:full=reader.snapshot(revision)
        except RepositoryError as error:
            if error.code not in PARTIAL:raise
            return inventory
        a={e.id:e for e in inventory.entries};b={e.id:e for e in full.entries}
        for key in set(a)&set(b):require(a[key]==b[key],'REVISION_MISMATCH')
        if inventory.inventory_complete:require(set(b)<=set(a),'REVISION_MISMATCH')
        if full.inventory_complete:require(set(a)<=set(b),'REVISION_MISMATCH')
        entries={**a,**b};require(len(entries)<=50000,'INVENTORY_LIMIT')
        return replace(full,entries=tuple(sorted(entries.values(),key=lambda e:e.id)),contents={key:full.contents.get(key,inventory.contents.get(key,Content(key,'NOT_FETCHED'))) for key in entries},inventory_complete=inventory.inventory_complete or full.inventory_complete)
    def _run(self,job,registration,kind,name,left_kind,left_name):
        candidate=None;reader=None;reader_closed=False;start=time.monotonic()
        try:
            job.state='RUNNING';self._phase(job,'VERIFYING_IDENTITY');budget=Budget(deadline=time.monotonic()+120);registration=self._verify(job,registration,budget);reader=self._factory(registration,job.cancel,budget);job.reader=reader
            self._phase(job,'PINNING_RIGHT');right_revision=reader.pin(kind,name);right=reader.snapshot(right_revision,path_ids=set());parents=reader.report.get('parents');require(isinstance(parents,list),'PARENT_METADATA_MISSING');right_report=json.loads(canonical(reader.report));proof=None
            self._phase(job,'PINNING_LEFT')
            if left_kind is None and not parents:left=None;left_revision=None;proof={'commit':right_revision.commit_id,'parents':[],'basis':'FIRST_PARENT_NONE'}
            else:
                left_revision=reader.pin(left_kind or 'commit',left_name if left_kind else parents[0]);left=reader.snapshot(left_revision,path_ids=set())
            self._phase(job,'READING_RIGHT_SOURCE');right=self._materialize(reader,right_revision,right)
            if left is not None:
                self._phase(job,'READING_LEFT_SOURCE');left=right if left_revision.commit_id==right_revision.commit_id else self._materialize(reader,left_revision,left)
            reader.close();reader_closed=True
            self._phase(job,'ANALYZING');graph=analyze_snapshot(right,self.settings,deadline=min(start+300,time.monotonic()+180));require(len(canonical(graph))<=14*1024*1024,'NAVIGATION_LIMIT');self._phase(job,'RETAINING')
            rid=self.store.save_snapshot(right);lid=self.store.save_snapshot(left) if left is not None else None
            with self.lock:self._require_job(job);predecessor=self.active.context_id if self.active and self.active.source_id==registration.id else None
            record={'schema':SCHEMA,'source_id':registration.id,'right':rid,'left':lid,'empty_baseline':proof,'graph':graph,'source_url':registration.effective_url,'comparison_request':{'left_kind':left_kind,'left_ref':left_name},'provenance':{'right_inventory':right_report,'collection':json.loads(canonical(reader.report))},'predecessor':predecessor}
            context,candidate=self.views.prepare(record);view=RetainedView(context,record,self.store);coverage=view.coverage()
            with self.lock:
                self._require_job(job);current=self.hosted.registry.get(registration.id);require(current.connection_key==registration.connection_key,'REGISTRY_CHANGED');self.views.commit(context,candidate,view);candidate=None
                complete=coverage['state']=='COMPLETE'
                if complete:self.active=view
                job.result={'context_id':context,'capture_id':rid,'navigation_id':graph['navigation_id'],'coverage':coverage,'activated':complete};job.state='SUCCEEDED' if complete else 'SAVED_PARTIAL';job.phase=job.state
        except RepositoryError as error:
            with self.lock:
                job.state=('SUPERSEDED' if job.generation!=self.generation else 'CANCELLED') if not self._current(job) or error.code=='CANCELLED' else 'FAILED';job.error=None if job.state in {'CANCELLED','SUPERSEDED'} else {'code':error.code,'message':'Source collection did not complete','retry_at':getattr(error,'retry_at',None)};job.phase=job.state
        except Exception:
            with self.lock:
                job.state='FAILED' if self._current(job) else 'SUPERSEDED' if job.generation!=self.generation else 'CANCELLED';job.phase=job.state;job.error={'code':'COLLECTION_FAILED','message':'Source collection did not complete'} if job.state=='FAILED' else None
        finally:
            if reader is not None and not reader_closed:
                try:reader.close()
                except Exception:
                    with self.lock:job.state='FAILED';job.phase=job.state;job.error={'code':'JOB_CLEANUP_FAILED','message':'Owned source client did not stop'}
            if candidate is not None:candidate.unlink(missing_ok=True)
            with self.lock:job.finished_at=now()
    def inspect(self,key):
        source_id(key)
        with self.lock:require(key in self.jobs,'JOB_NOT_FOUND');return self.jobs[key].public()
    def cancel(self,key):
        source_id(key)
        with self.lock:
            require(key in self.jobs,'JOB_NOT_FOUND');job=self.jobs[key]
            if job.state not in TERMINAL:job.cancel.set();job.state='CANCEL_REQUESTED';job.phase=job.state
            return job.public()
    def wait(self,key,timeout=315):
        with self.lock:require(key in self.jobs,'JOB_NOT_FOUND');thread=self.jobs[key].thread
        thread.join(timeout);require(not thread.is_alive(),'JOB_TIMEOUT');return self.inspect(key)
    def close(self):
        with self.lock:self.closed=True;jobs=list(self.jobs.values());[j.cancel.set() for j in jobs if j.state not in TERMINAL]
        deadline=time.monotonic()+12
        for job in jobs:job.thread.join(max(0,deadline-time.monotonic()))
        require(all(not j.thread.is_alive() for j in jobs),'JOB_CLEANUP_FAILED')
    def payload(self):
        with self.lock:active=self.active;selected=self.selected
        if active:payload=active.payload()
        elif self.local:
            with self.local.lock:payload=self.local.payload()
            graph=payload['graph'];payload['view']={'source_id':'local','provider':'local','context_id':digest(canonical([graph['capture_id'],graph['navigation_id']])),'navigation_id':graph['navigation_id']}
        else:payload={'graph':None,'capture':None,'view':None}
        payload['selection']={'source_id':selected};return payload
    def _active(self,context=None):
        with self.lock:active=self.active
        if active:require(context is None or context==active.context_id,'CONTEXT_CHANGED')
        elif context is not None:
            require(self.local is not None,'NO_ACTIVE_VIEW');require(context==self.payload()['view']['context_id'],'CONTEXT_CHANGED')
        return active
    def source(self,path,version,context=None):
        active=self._active(context)
        if active:return active.source(path,version)
        require(self.local is not None,'NO_ACTIVE_VIEW')
        with self.local.lock:return self.local.read_source(path,version)
    def comparison(self,path,left,right,context=None):
        active=self._active(context)
        if active:
            require(left=='left' and right=='right','INVALID_VERSION');return active.comparison(path)
        require(self.local is not None,'NO_ACTIVE_VIEW')
        with self.local.lock:return compare(self.local.read_source(path,left),self.local.read_source(path,right))
    def get_api(self,path,values):
        if path=='/api/nav/sources':require(not values,'INVALID_QUERY');return self.sources()
        if path=='/api/nav/history':require(set(values)<={'source'},'INVALID_QUERY');return {'views':self.views.summaries(values.get('source'))}
        if path.startswith('/api/nav/jobs/') and path.count('/')==4:require(not values,'INVALID_QUERY');return self.inspect(path.rsplit('/',1)[-1])
        if path=='/api/nav/changes':
            require(set(values)<={'context','offset','limit'},'INVALID_QUERY');active=self._active(values.get('context'));require(active is not None,'NO_HOSTED_VIEW');offset=int(values.get('offset',0));limit=int(values.get('limit',100));require(0<=offset<=100000 and 1<=limit<=500,'INVALID_QUERY');return dict(active.changes,items=active.changes['items'][offset:offset+limit],offset=offset,limit=limit,context_id=active.context_id)
        raise RepositoryError('NOT_FOUND','Navigation API is unavailable')
    def post_api(self,path,body):
        require(isinstance(body,dict),'INVALID_BODY')
        if path=='/api/nav/select' and set(body)=={'source_id'}:return self.select(source=body['source_id'])
        if path=='/api/nav/select' and set(body)=={'context_id'}:return self.select(context=body['context_id'])
        if path=='/api/nav/collect' and set(body) in [{'source_id','ref_kind','ref_name'},{'source_id','ref_kind','ref_name','left_kind','left_ref'}]:return self.collect(body['source_id'],body['ref_kind'],body['ref_name'],body.get('left_kind'),body.get('left_ref'))
        if path.startswith('/api/nav/jobs/') and path.endswith('/cancel') and path.count('/')==5 and not body:return self.cancel(path.split('/')[4])
        if path=='/api/nav/editor' and set(body)=={'context_id','path','version','line'}:
            active=self._active(body['context_id']);require(active is not None,'NO_HOSTED_VIEW');return self.views.editor_copy(active,body['path'],body['version'],body['line'])
        raise RepositoryError('INVALID_BODY','Unsupported navigation request')
