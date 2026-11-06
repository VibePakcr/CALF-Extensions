"""Bounded read-only API transport. No provider enumeration or collection adapters."""
from collections import OrderedDict,deque
from dataclasses import asdict,dataclass,field,replace
import base64
import hmac
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from types import MappingProxyType
from urllib.parse import parse_qsl,quote,unquote,urlencode,urljoin,urlsplit
import uuid
from .model import RepositoryError,SOURCE_LIMIT,canonical,oid
from .registrations import Registration

API_VERSION='2026-03-10'
SAFE_HEADERS={'content-type','etag','link','location','retry-after','x-ratelimit-remaining','x-ratelimit-reset','ratelimit-remaining','ratelimit-reset'}

class HTTPError(RepositoryError):
    def __init__(self,code,retry_at=None):
        super().__init__(code,'Registered repository read did not complete');self.retry_at=retry_at
    def public(self):return {'code':self.code,'message':str(self),'retry_at':self.retry_at}


def strict_json(raw):
    def pairs(values):
        out={}
        for key,value in values:
            if key in out:raise HTTPError('INVALID_JSON')
            out[key]=value
        return out
    try:return json.loads(raw.decode('utf-8') if isinstance(raw,bytes) else raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError):raise HTTPError('INVALID_JSON') from None


@dataclass(frozen=True)
class RequestSpec:
    operation: str
    selector: str | None = None
    recursive: bool = False
    method: str = 'GET'
    def __post_init__(self):
        if self.operation not in {'identity','branch','tag','tag_object','commit','tree','blob'} or self.method not in {'GET','HEAD'} or type(self.recursive) is not bool:raise HTTPError('REQUEST_REFUSED')
        if self.operation=='identity':
            if self.selector is not None or self.recursive:raise HTTPError('REQUEST_REFUSED')
        elif self.operation in {'commit','tree','blob','tag_object'}:oid(self.selector)
        elif not isinstance(self.selector,str) or not self.selector or len(self.selector)>4096 or any(ord(c)<32 or c=='\x7f' for c in self.selector):raise HTTPError('INVALID_REF')
        if self.recursive and self.operation!='tree':raise HTTPError('REQUEST_REFUSED')
    def url(self,registration):
        if not registration.enabled:raise HTTPError('SOURCE_DISABLED')
        if self.operation!='identity' and registration.repository_id is None:raise HTTPError('SOURCE_UNVERIFIED')
        gh=registration.provider=='github';origin=registration.origin
        if self.operation=='identity':
            path=('/repositories/'+registration.repository_id if registration.repository_id else '/repos/'+registration.path) if gh else '/api/v4/projects/'+(registration.repository_id or quote(unquote(registration.path,encoding='utf-8',errors='strict'),safe=''))
            return origin+path
        base='/repos/'+registration.path if gh else '/api/v4/projects/'+registration.repository_id
        selector=quote(self.selector,safe='')
        if self.operation=='branch':return origin+base+('/branches/' if gh else '/repository/branches/')+selector
        if self.operation=='tag':return origin+base+('/git/ref/tags/' if gh else '/repository/tags/')+selector
        if self.operation=='tag_object':
            if not gh:raise HTTPError('REQUEST_REFUSED')
            return origin+base+'/git/tags/'+selector
        if self.operation=='commit':return origin+base+('/git/commits/' if gh else '/repository/commits/')+selector
        if self.operation=='blob':return origin+base+('/git/blobs/' if gh else '/repository/blobs/')+selector+('' if gh else '/raw')
        return origin+base+('/git/trees/'+selector+('?recursive=1' if self.recursive else '') if gh else '/repository/tree?'+urlencode({'ref':self.selector,'recursive':str(self.recursive).lower(),'pagination':'keyset','per_page':'100'}))
    def response_limit(self,registration):return (2*SOURCE_LIMIT if registration.provider=='github' else SOURCE_LIMIT) if self.operation=='blob' else 16*SOURCE_LIMIT
    def expects_json(self,registration):return not (self.operation=='blob' and registration.provider=='gitlab') and self.method!='HEAD'


def follow_url(registration,spec,current,target,*,pagination=False):
    if not isinstance(target,str) or len(target)>8192:raise HTTPError('URL_REFUSED')
    resolved=urljoin(current,target);u=urlsplit(resolved);base=urlsplit(spec.url(registration))
    if u.scheme!='https' or u.netloc!=urlsplit(registration.origin).netloc or u.fragment or u.username or u.password:raise HTTPError('URL_REFUSED')
    if not pagination:
        if resolved==current:return resolved
        pattern=r'/repositories/([1-9][0-9]{0,19})' if registration.provider=='github' else r'/api/v4/projects/([1-9][0-9]{0,19})'
        match=re.fullmatch(pattern,u.path)
        if spec.operation!='identity' or u.query or not match or registration.repository_id is not None and registration.repository_id!=match.group(1):raise HTTPError('REDIRECT_REFUSED')
        return resolved
    if registration.provider!='gitlab' or spec.operation!='tree' or u.path!=base.path:raise HTTPError('PAGINATION_REFUSED')
    pairs=parse_qsl(u.query,keep_blank_values=True);values=dict(pairs);expected=dict(parse_qsl(base.query))
    if len(values)!=len(pairs) or set(values)-set(expected)-{'page_token','page'}:raise HTTPError('PAGINATION_REFUSED')
    if any(values.get(k)!=v for k,v in expected.items()):raise HTTPError('PAGINATION_REFUSED')
    if 'page_token' in values and (not values['page_token'] or len(values['page_token'])>4096):raise HTTPError('PAGINATION_REFUSED')
    if 'page' in values and not re.fullmatch('[1-9][0-9]{0,6}',values['page']):raise HTTPError('PAGINATION_REFUSED')
    if ('page_token' in values)==('page' in values):raise HTTPError('PAGINATION_REFUSED')
    return resolved


@dataclass
class Budget:
    limit: int = 300
    deadline: float = field(default_factory=lambda:time.monotonic()+120)
    used: int = 0
    def take(self,cancel):
        if cancel.is_set():raise HTTPError('CANCELLED')
        if time.monotonic()>=self.deadline:raise HTTPError('HTTP_TIMEOUT')
        if self.used>=self.limit:raise HTTPError('REQUEST_LIMIT')
        self.used+=1


def child_environment():
    allow={'PATH','SYSTEMROOT','WINDIR','COMSPEC','TMP','TEMP','TMPDIR','SSL_CERT_FILE','SSL_CERT_DIR','PYTHONPYCACHEPREFIX'}
    env={k:v for k,v in os.environ.items() if k.upper() in allow}
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(Path(__file__).parents[2]))
    return env


class WorkerTransport:
    """One owned request process; even stalled DNS/TLS is terminated by the parent."""
    def __init__(self,command=None):
        self.command=tuple(command or [sys.executable,'-m','calf_extensions.repository.http_worker']);self.last_cleanup=None
    @staticmethod
    def _stop(process):
        if os.name!='nt':
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        elif process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=4,check=False)
        if process.poll() is None:process.kill()
        process.wait(timeout=4)
    def send(self,payload,cancel,deadline):
        raw=canonical(payload)
        if len(raw)>65536:raise HTTPError('REQUEST_LIMIT')
        process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=Path(__file__).parent,
                                 env=child_environment(),start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        chunks=[];sizes=[0,0];overflow=threading.Event();bound=payload['limit']*4//3+65536
        def read(stream,index):
            while True:
                block=stream.read(65536)
                if not block:break
                sizes[index]+=len(block)
                if sizes[index]>(bound if index==0 else 8192):overflow.set();break
                if index==0:chunks.append(block)
        def write():
            try:process.stdin.write(raw);process.stdin.close()
            except (OSError,ValueError):pass
        threads=[threading.Thread(target=read,args=(process.stdout,0)),threading.Thread(target=read,args=(process.stderr,1)),threading.Thread(target=write)]
        for thread in threads:thread.start()
        try:
            end=min(deadline,time.monotonic()+10)
            while process.poll() is None:
                if cancel.is_set():raise HTTPError('CANCELLED')
                if overflow.is_set():raise HTTPError('HTTP_RESPONSE_LIMIT')
                if time.monotonic()>=end:raise HTTPError('HTTP_TIMEOUT')
                time.sleep(.02)
            if cancel.is_set():raise HTTPError('CANCELLED')
            if process.returncode:raise HTTPError('HTTP_IO')
        finally:
            self._stop(process)
            for thread in threads:thread.join(timeout=2)
            self.last_cleanup={'stopped':process.poll() is not None,'threads_stopped':all(not t.is_alive() for t in threads)}
            for stream in [process.stdin,process.stdout,process.stderr]:stream.close()
        if overflow.is_set():raise HTTPError('HTTP_RESPONSE_LIMIT')
        if not self.last_cleanup['threads_stopped']:raise HTTPError('HTTP_CLEANUP_FAILED')
        result=strict_json(b''.join(chunks))
        if not isinstance(result,dict) or set(result)-{'status','headers','body','error'}:raise HTTPError('HTTP_INVALID_RESPONSE')
        if result.get('error'):raise HTTPError(result['error'] if result['error'] in {'HTTP_IO','HTTP_RESPONSE_LIMIT','REQUEST_REFUSED'} else 'HTTP_IO')
        try:
            status=result['status'];headers=result['headers'];body=base64.b64decode(result['body'],validate=True)
            if type(status) is not int or not 100<=status<=599 or not isinstance(headers,dict) or set(headers)-SAFE_HEADERS or any(not isinstance(v,str) or len(v)>8192 for v in headers.values()) or len(body)>payload['limit']:raise HTTPError('HTTP_INVALID_RESPONSE')
            return status,headers,body
        except (ValueError,KeyError,TypeError):raise HTTPError('HTTP_INVALID_RESPONSE') from None


@dataclass(frozen=True)
class Response:
    status: int
    headers: object = field(repr=False)
    body: bytes = field(repr=False)
    spec: RequestSpec
    owner: str = field(repr=False)
    url: str = field(repr=False)
    chain: tuple = field(repr=False)
    cached: bool = False
    budget: object = field(default=None,repr=False,compare=False)
    cancel_event: object = field(default=None,repr=False,compare=False)
    def json(self):return strict_json(self.body)


_HOST_LOCK=threading.Lock()
_HOST_GATES={}
def host_gate(origin):
    with _HOST_LOCK:return _HOST_GATES.setdefault(origin,threading.Lock())


class HTTPReader:
    def __init__(self,registration,transport=None):
        self.registration=registration;self.transport=transport or WorkerTransport();self._lock=threading.RLock();self._token=None;self._partition=str(uuid.uuid4());self._cache=OrderedDict();self._cache_bytes=0;self._retry_at=0;self._witness=deque(maxlen=1000)
    @property
    def witness(self):return tuple(dict(x) for x in self._witness)
    def _credential(self):
        ref=self.registration.credential_env;token=os.environ.get(ref) if ref else None
        if ref and (not token or len(token)>8192 or not token.isascii() or any(ord(c)<33 or ord(c)==127 for c in token)):raise HTTPError('CREDENTIAL_MISSING_OR_INVALID')
        if (self._token is None)!=(token is None) or self._token is not None and not hmac.compare_digest(self._token,token):
            self._partition=str(uuid.uuid4());self._cache.clear();self._cache_bytes=0;self._retry_at=0
        self._token=token;return token
    def close(self):
        with self._lock:self._token=None;self._cache.clear();self._cache_bytes=0
    def request(self,spec,cancel=None,budget=None):return self._request(spec,spec.url(self.registration),cancel or threading.Event(),budget or Budget(),())
    def _request(self,spec,url,cancel,budget,chain):
        while not self._lock.acquire(timeout=.05):
            if cancel.is_set():raise HTTPError('CANCELLED')
            if time.monotonic()>=budget.deadline:raise HTTPError('HTTP_TIMEOUT')
        try:
            if cancel.is_set():raise HTTPError('CANCELLED')
            token=self._credential();key=(self._partition,spec.method,url);cached=self._cache.get(key);redirects=0;attempt=0;visited=tuple(chain)
            while True:
                if cancel.is_set():raise HTTPError('CANCELLED')
                if time.time()<self._retry_at:raise HTTPError('RATE_LIMITED',self._retry_at)
                gate=host_gate(self.registration.origin)
                while not gate.acquire(timeout=.05):
                    if cancel.is_set():raise HTTPError('CANCELLED')
                    if time.monotonic()>=budget.deadline:raise HTTPError('HTTP_TIMEOUT')
                try:
                    budget.take(cancel)
                    payload={'registration':asdict(replace(self.registration,credential_env=None)),'spec':asdict(spec),'url':url,'token':token,'etag':cached[0] if cached else None,'limit':spec.response_limit(self.registration),'timeout':5}
                    status,headers,body=self.transport.send(payload,cancel,budget.deadline)
                except HTTPError as e:
                    if e.code!='HTTP_IO' or attempt>=2:raise
                    attempt+=1
                    if cancel.wait(.2*attempt):raise HTTPError('CANCELLED')
                    continue
                finally:gate.release()
                if token and (token.encode() in body or any(token in v for v in headers.values())):raise HTTPError('CREDENTIAL_ECHO')
                self._witness.append({'operation':spec.operation,'method':spec.method,'status':status,'bytes':len(body),'request_count':budget.used})
                if status in {301,302,303,307,308}:
                    if redirects>=3:raise HTTPError('REDIRECT_LIMIT')
                    target=follow_url(self.registration,spec,url,headers.get('location'))
                    if target in visited or target==url:raise HTTPError('REDIRECT_LOOP')
                    visited+= (url,);url=target;redirects+=1;cached=None;key=(self._partition,spec.method,url);continue
                remaining=headers.get('x-ratelimit-remaining',headers.get('ratelimit-remaining'))
                throttled=status==429 or status==403 and ('retry-after' in headers or remaining=='0' or b'rate limit' in body.lower())
                if throttled:
                    self._retry_at=retry_time(headers);raise HTTPError('RATE_LIMITED',self._retry_at)
                if status in {500,502,503,504}:
                    if attempt>=2:raise HTTPError('HTTP_UNAVAILABLE')
                    delay=max(.2*(attempt+1),retry_time(headers)-time.time() if 'retry-after' in headers else 0)
                    if time.monotonic()+delay>=budget.deadline:raise HTTPError('HTTP_UNAVAILABLE',time.time()+delay)
                    attempt+=1
                    if cancel.wait(delay):raise HTTPError('CANCELLED')
                    continue
                if status==401:raise HTTPError('AUTH_REQUIRED')
                if status==403:raise HTTPError('ACCESS_DENIED')
                if status==404:raise HTTPError('ACCESS_UNKNOWN')
                if remaining=='0' and status==304:self._retry_at=retry_time(headers)
                if status==304:
                    if not cached:raise HTTPError('CACHE_MISSING')
                    return Response(200,MappingProxyType(dict(cached[1])),cached[2],spec,self._partition,url,visited+(url,),True,budget,cancel)
                if status!=200:raise HTTPError('HTTP_UNAVAILABLE')
                if spec.expects_json(self.registration):
                    content_type=headers.get('content-type','').split(';',1)[0].lower()
                    if content_type!='application/json' and not content_type.endswith('+json'):raise HTTPError('HTTP_INVALID_CONTENT_TYPE')
                    strict_json(body)
                if remaining=='0':self._retry_at=retry_time(headers)
                if spec.method=='GET' and headers.get('etag'):
                    if key in self._cache:self._cache_bytes-=len(self._cache.pop(key)[2])
                    self._cache[key]=(headers['etag'],dict(headers),body);self._cache_bytes+=len(body)
                    while self._cache_bytes>64*SOURCE_LIMIT:self._cache_bytes-=len(self._cache.popitem(last=False)[1][2])
                return Response(status,MappingProxyType(dict(headers)),body,spec,self._partition,url,visited+(url,),False,budget,cancel)
        finally:self._lock.release()
    def follow_next(self,response,cancel=None,budget=None):
        with self._lock:self._credential()
        if response.owner!=self._partition:raise HTTPError('CACHE_PARTITION_MISMATCH')
        header=response.headers.get('link')
        if not header:return None
        next_links=[]
        for part in re.split(r',\s*(?=<)',header):
            match=re.fullmatch(r'\s*<([^<>]+)>((?:;[^,]*)*)\s*',part)
            if not match:raise HTTPError('PAGINATION_INVALID')
            rel=re.search(r';\s*rel=(?:"([^"]+)"|([^;\s]+))',match.group(2))
            if rel and 'next' in (rel.group(1) or rel.group(2)).split():next_links.append(match.group(1))
        if len(next_links)>1:raise HTTPError('PAGINATION_INVALID')
        if not next_links:return None
        target=follow_url(self.registration,response.spec,response.url,next_links[0],pagination=True)
        if target in response.chain:raise HTTPError('PAGINATION_LOOP')
        if len(response.chain)>=300:raise HTTPError('REQUEST_LIMIT')
        return self._request(response.spec,target,cancel or response.cancel_event or threading.Event(),budget or response.budget or Budget(),response.chain)


def retry_time(headers):
    from email.utils import parsedate_to_datetime
    current=time.time();values=[]
    retry=headers.get('retry-after')
    if retry:
        try:
            delay=float(retry);value=current+max(0,delay)
        except ValueError:
            try:value=parsedate_to_datetime(retry).timestamp()
            except (ValueError,TypeError,OverflowError):value=current+60
        if math.isfinite(value):values.append(value)
    for name in ['x-ratelimit-reset','ratelimit-reset']:
        try:
            value=float(headers[name])
            if math.isfinite(value):values.append(value)
        except (KeyError,ValueError):pass
    return max([current,*values]) if values else current+60
