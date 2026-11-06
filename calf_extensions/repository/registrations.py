"""Explicit hosted registrations. Credential references only; no discovery or HTTP."""
from contextlib import contextmanager
from dataclasses import asdict,dataclass,replace
import json
import os
from pathlib import Path
import re
from urllib.parse import quote,unquote,urlsplit
import uuid
from .model import RepositoryError,canonical,now

SCHEMA='calf.repository.registrations.v1'
HOSTS={'github':'github.com','gitlab':'gitlab.com'}


def fail(code):raise RepositoryError(code,'Repository registration is unavailable or invalid')


def source_id(value):
    try:
        if not isinstance(value,str) or str(uuid.UUID(value))!=value:fail('INVALID_SOURCE_ID')
    except (ValueError,AttributeError):fail('INVALID_SOURCE_ID')
    return value


def canonical_url(provider,value):
    if provider not in HOSTS or not isinstance(value,str) or len(value)>4096:fail('INVALID_SOURCE_URL')
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.netloc!=HOSTS[provider] or u.query or u.fragment:fail('INVALID_SOURCE_URL')
        raw=u.path.strip('/')
        if raw.endswith('.git'):raw=raw[:-4]
        pieces=[unquote(x,encoding='utf-8',errors='strict') for x in raw.split('/')]
        if len(pieces)<2 or provider=='github' and len(pieces)!=2:fail('INVALID_SOURCE_URL')
        if any(not p or p in {'.','..','-'} or any(c in p for c in '/\\:@?#%') or any(ord(c)<33 or ord(c)==127 for c in p) for p in pieces):fail('INVALID_SOURCE_URL')
        if provider=='github':pieces=[p.lower() for p in pieces]
        return 'https://'+HOSTS[provider]+'/'+('/'.join(quote(p,safe='-._~') for p in pieces))
    except (ValueError,UnicodeError):fail('INVALID_SOURCE_URL')


@dataclass(frozen=True)
class Registration:
    id: str
    provider: str
    url: str
    credential_env: str | None = None
    repository_id: str | None = None
    verified_url: str | None = None
    private: bool | None = None
    empty_repository: bool | None = None
    version: int = 1
    enabled: bool = True
    created_at: str = ''
    verified_at: str | None = None

    def __post_init__(self):
        source_id(self.id)
        if canonical_url(self.provider,self.url)!=self.url:fail('INVALID_SOURCE_URL')
        if self.verified_url is not None and canonical_url(self.provider,self.verified_url)!=self.verified_url:fail('INVALID_SOURCE_URL')
        if self.credential_env is not None and (not isinstance(self.credential_env,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',self.credential_env)):fail('INVALID_CREDENTIAL_REFERENCE')
        if self.repository_id is not None and (not isinstance(self.repository_id,str) or not re.fullmatch('[1-9][0-9]{0,19}',self.repository_id)):fail('INVALID_REPOSITORY_ID')
        if type(self.enabled) is not bool or type(self.version) is not int or self.version<1 or self.private is not None and type(self.private) is not bool:fail('INVALID_REGISTRATION')
        if self.empty_repository is not None and type(self.empty_repository) is not bool:fail('INVALID_REGISTRATION')
        if not isinstance(self.created_at,str) or not self.created_at or self.verified_at is not None and not isinstance(self.verified_at,str):fail('INVALID_REGISTRATION')

    @property
    def effective_url(self):return self.verified_url or self.url
    @property
    def path(self):return urlsplit(self.effective_url).path.lstrip('/')
    @property
    def origin(self):return 'https://api.github.com' if self.provider=='github' else 'https://gitlab.com'
    def public(self):
        return {'id':self.id,'provider':self.provider,'url':self.effective_url,'repository_id':self.repository_id,
                'identity_state':'IDENTITY_VERIFIED' if self.repository_id else 'REGISTERED_UNVERIFIED','credential_configured':self.credential_env is not None,
                'private':self.private,'repository_state':'EMPTY' if self.empty_repository is True else 'NONEMPTY' if self.empty_repository is False else 'UNKNOWN','version':self.version,'enabled':self.enabled,'verified_at':self.verified_at}
    @property
    def connection_key(self):return (self.id,self.provider,self.effective_url,self.repository_id,self.credential_env,self.enabled)


class Registry:
    def __init__(self,data_dir):
        self.data_dir=Path(data_dir).expanduser().resolve();self.root=self.data_dir/'registrations'
    def _check(self):
        if self.root.is_symlink():fail('REGISTRY_PATH_REFUSED')
        if self.root.exists():
            marker=self.root/'schema'
            if not self.root.is_dir() or marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(SCHEMA) or marker.read_bytes()!=SCHEMA.encode():fail('REGISTRY_PATH_REFUSED')
    def _ensure(self):
        for p in [self.data_dir,*self.data_dir.parents]:
            if (p/'.git').exists() or p.name=='.git' or (p/'HEAD').is_file() and ((p/'objects').is_dir() or (p/'commondir').is_file()):fail('OUTPUT_IN_REPOSITORY')
        self._check();self.data_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if not self.root.exists():
            self.root.mkdir(mode=0o700)
            with (self.root/'schema').open('xb') as f:f.write(SCHEMA.encode())
        self._check()
    @contextmanager
    def _locked(self):
        self._ensure();path=self.root/'.lock'
        try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:fail('REGISTRY_BUSY')
        try:yield
        finally:os.close(fd);path.unlink()
    def _read(self,identity):
        self._check();path=self.root/(source_id(identity)+'.json')
        if path.is_symlink():fail('REGISTRY_PATH_REFUSED')
        if not path.is_file():fail('SOURCE_NOT_FOUND')
        if path.stat().st_size>16384:fail('REGISTRY_LIMIT')
        try:data=json.loads(path.read_bytes());result=Registration(**data)
        except (ValueError,TypeError):fail('INVALID_REGISTRATION')
        if result.id!=identity:fail('INVALID_REGISTRATION')
        return result
    def get(self,identity,*,include_disabled=False):
        value=self._read(identity)
        if not include_disabled and not value.enabled:fail('SOURCE_DISABLED')
        return value
    def list(self,*,include_disabled=False):
        self._check()
        if not self.root.exists():return []
        paths=list(self.root.glob('*.json'))
        if len(paths)>1000:fail('REGISTRY_LIMIT')
        result=[self._read(p.stem) for p in sorted(paths)]
        return [v for v in result if include_disabled or v.enabled]
    def _write(self,value,previous=None):
        raw=canonical(asdict(value))
        if len(raw)>16384:fail('REGISTRY_LIMIT')
        if previous is not None:
            history=self.root/'history'
            if history.is_symlink():fail('REGISTRY_PATH_REFUSED')
            history.mkdir(exist_ok=True,mode=0o700);old=canonical(asdict(previous));path=history/(previous.id+'-'+str(previous.version)+'.json')
            try:
                with path.open('xb') as f:f.write(old)
            except FileExistsError:
                if path.read_bytes()!=old:fail('REGISTRY_HISTORY_CONFLICT')
        target=self.root/(value.id+'.json');temp=self.root/('.'+str(uuid.uuid4())+'.tmp')
        try:
            with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(temp,target)
        finally:
            if temp.exists():temp.unlink()
    def add(self,provider,url,credential_env=None):
        url=canonical_url(provider,url);value=Registration(str(uuid.uuid4()),provider,url,credential_env,created_at=now())
        with self._locked():
            for existing in self.list():
                if existing.provider==provider and url in {existing.url,existing.effective_url}:
                    if existing.credential_env!=credential_env:fail('SOURCE_ALREADY_REGISTERED')
                    return existing
            if len(self.list(include_disabled=True))>=1000:fail('REGISTRY_LIMIT')
            self._write(value)
        return value
    def remove(self,identity):
        with self._locked():
            old=self.get(identity,include_disabled=True)
            if not old.enabled:return old
            value=replace(old,enabled=False,version=old.version+1);self._write(value,old);return value
    def bind(self,identity,expected_version,metadata):
        with self._locked():
            old=self.get(identity)
            if old.version!=expected_version:fail('REGISTRY_CHANGED')
            try:
                number=metadata['id'];name=metadata['full_name' if old.provider=='github' else 'path_with_namespace']
                if type(number) is not int or number<=0 or not isinstance(name,str):fail('INVALID_IDENTITY_RESPONSE')
                target=canonical_url(old.provider,'https://'+HOSTS[old.provider]+'/'+name)
                supplied=metadata.get('html_url' if old.provider=='github' else 'web_url')
                if supplied is not None and canonical_url(old.provider,supplied)!=target:fail('INVALID_IDENTITY_RESPONSE')
                if old.repository_id is not None and old.repository_id!=str(number):fail('IDENTITY_MISMATCH')
                private=metadata.get('private') if old.provider=='github' else None if metadata.get('visibility') not in {'public','internal','private'} else metadata['visibility']!='public'
                value=replace(old,repository_id=str(number),verified_url=target,private=private,empty_repository=metadata.get('empty_repo') if old.provider=='gitlab' else None,verified_at=now(),version=old.version+1)
            except (KeyError,TypeError,ValueError):fail('INVALID_IDENTITY_RESPONSE')
            self._write(value,old);return value
