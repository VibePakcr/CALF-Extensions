"""Foreground-owned identity checks. No map publication or CALF record writes."""
from dataclasses import dataclass,field
import threading
import time
import uuid
from .http_reader import Budget,HTTPError,HTTPReader,RequestSpec
from .model import RepositoryError,now
from .registrations import Registry,source_id

TERMINAL={'SUCCEEDED','FAILED','CANCELLED','SUPERSEDED'}


@dataclass
class Job:
    id: str
    source_id: str
    generation: int
    cancel_event: threading.Event = field(default_factory=threading.Event,repr=False)
    state: str = 'QUEUED'
    phase: str = 'QUEUED'
    started_at: str = field(default_factory=now)
    finished_at: str | None = None
    requests: int = 0
    result: dict | None = None
    error: dict | None = None
    thread: object = field(default=None,repr=False)
    def public(self):return {'id':self.id,'source_id':self.source_id,'generation':self.generation,'operation':'identity_probe','state':self.state,'phase':self.phase,'started_at':self.started_at,'finished_at':self.finished_at,'requests':self.requests,'result':self.result,'error':self.error}


class HostedServices:
    def __init__(self,data_dir,client_factory=None):
        self.registry=Registry(data_dir);self._factory=client_factory or HTTPReader;self._clients={};self._client_lock=threading.Lock();self._lock=threading.RLock();self._jobs={};self._generations={};self._closed=False
    def _client(self,registration):
        with self._client_lock:
            key=registration.connection_key
            if key not in self._clients:self._clients[key]=self._factory(registration)
            return self._clients[key]
    def _job(self,identity):
        source_id(identity)
        if identity not in self._jobs:raise RepositoryError('JOB_NOT_FOUND','Requested job is unavailable')
        return self._jobs[identity]
    def probe(self,identity):
        registration=self.registry.get(identity)
        with self._lock:
            if self._closed:raise RepositoryError('SERVICE_CLOSED','Repository service has stopped')
            if len(self._jobs)>=1000:raise RepositoryError('JOB_LIMIT','Too many retained foreground jobs')
            generation=self._generations.get(identity,0)+1;self._generations[identity]=generation
            for old in self._jobs.values():
                if old.source_id==identity and old.state not in TERMINAL:old.cancel_event.set()
            job=Job(str(uuid.uuid4()),identity,generation);self._jobs[job.id]=job
            job.thread=threading.Thread(target=self._run,args=(job,registration),name='calf-repository-check');job.thread.start();return job.public()
    def _current(self,job):return not job.cancel_event.is_set() and self._generations.get(job.source_id)==job.generation
    def _stopped_state(self,job):return 'SUPERSEDED' if self._generations.get(job.source_id)!=job.generation else 'CANCELLED'
    def _run(self,job,registration):
        budget=Budget()
        try:
            with self._lock:
                if not self._current(job):job.state=self._stopped_state(job);return
                job.state='RUNNING';job.phase='READING_IDENTITY'
            client=self._client(registration);response=client.request(RequestSpec('identity'),job.cancel_event,budget);metadata=response.json()
            if not isinstance(metadata,dict):raise HTTPError('INVALID_IDENTITY_RESPONSE')
            with self._lock:
                if not self._current(job):job.state=self._stopped_state(job);return
                # Cancellation and publication share this short critical section.
                verified=self.registry.bind(registration.id,registration.version,metadata)
                job.result=verified.public();job.state='SUCCEEDED';job.phase='IDENTITY_VERIFIED'
        except RepositoryError as e:
            with self._lock:
                if not self._current(job) or e.code=='CANCELLED':job.state=self._stopped_state(job)
                else:job.state='FAILED';job.error={'code':e.code,'message':'Registered repository check did not complete','retry_at':getattr(e,'retry_at',None)}
        except Exception:
            with self._lock:job.state='FAILED' if self._current(job) else self._stopped_state(job);job.error={'code':'JOB_FAILED','message':'Registered repository check did not complete'}
        finally:
            with self._lock:
                job.requests=budget.used;job.finished_at=now()
                if job.state in {'CANCELLED','SUPERSEDED'}:job.phase=job.state;job.result=None
    def inspect(self,identity):
        with self._lock:return self._job(identity).public()
    def cancel(self,identity):
        with self._lock:
            job=self._job(identity)
            if job.state not in TERMINAL:job.cancel_event.set();job.state='CANCEL_REQUESTED';job.phase='CANCEL_REQUESTED'
            return job.public()
    def wait(self,identity,timeout=130):
        with self._lock:thread=self._job(identity).thread
        thread.join(timeout=timeout)
        if thread.is_alive():raise RepositoryError('JOB_TIMEOUT','Foreground job did not finish')
        return self.inspect(identity)
    def close(self):
        with self._lock:
            self._closed=True;jobs=list(self._jobs.values())
            for job in jobs:
                if job.state not in TERMINAL:job.cancel_event.set()
        deadline=time.monotonic()+12
        for job in jobs:job.thread.join(timeout=max(0,deadline-time.monotonic()))
        if any(job.thread.is_alive() for job in jobs):raise RepositoryError('JOB_CLEANUP_FAILED','Foreground workers did not stop')
        for client in self._clients.values():client.close()

    def get_api(self,path):
        if path=='/api/registrations':return {'sources':[v.public() for v in self.registry.list()]}
        if path.startswith('/api/jobs/') and path.count('/')==3:return self.inspect(path.rsplit('/',1)[-1])
        raise RepositoryError('NOT_FOUND','Repository API is unavailable')
    def post_api(self,path,body):
        if not isinstance(body,dict):raise RepositoryError('INVALID_BODY','Expected a JSON object')
        if path=='/api/registrations' and set(body) in [{'provider','url'},{'provider','url','credential_env'}]:
            return self.registry.add(body['provider'],body['url'],body.get('credential_env')).public()
        if path.startswith('/api/registrations/') and path.endswith('/remove') and path.count('/')==4 and not body:
            return self.registry.remove(path.split('/')[3]).public()
        if path=='/api/jobs/probe' and set(body)=={'source_id'}:return self.probe(body['source_id'])
        if path.startswith('/api/jobs/') and path.endswith('/cancel') and path.count('/')==4 and not body:return self.cancel(path.split('/')[3])
        raise RepositoryError('INVALID_BODY','Unsupported repository request')
