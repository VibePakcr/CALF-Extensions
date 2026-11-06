"""User-opened loopback project portal. Only fixed read APIs and explicit refresh."""
import hmac
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from .analyze import analyze
from .compare import compare
from .providers.local import LocalSource
from .hosted import HostedServices
from .navigation import NavigationHub
from .http_reader import strict_json
from .model import RepositoryError,canonical,classify,digest,path_bytes,validate_settings

ASSETS=Path(__file__).parent/'assets'


def html(bootstrap):
    data=json.dumps(bootstrap,ensure_ascii=True,allow_nan=False).replace('<','\\u003c')
    slots={'BOOTSTRAP':'window.CALF_PORTAL='+data+';','STYLE':(ASSETS/'portal.css').read_text(encoding='utf-8'),'SCRIPT':(ASSETS/'portal.js').read_text(encoding='utf-8').replace('</script','<\\/script')}
    # Substitute template slots once; inserted source/asset text is never a template.
    return re.sub(r'/\*(BOOTSTRAP|STYLE|SCRIPT)\*/',lambda match:slots[match.group(1)],(ASSETS/'portal.html').read_text(encoding='utf-8'))

class Project:
    def __init__(self,root,data_dir,git=None,settings=None):
        self.source=LocalSource(root,data_dir,git);self.reader=self.source.reader;self.store=self.source.store;self.settings=validate_settings({} if settings is None else settings);self.capture=None;self.graph=None;self.lock=threading.RLock()
    def refresh(self):
        capture=self.source.collect_working();graph=analyze(self.reader,self.store,capture,self.settings,source_reader=self.source)
        # Publish the pair only after both operations succeed.
        directory=self.store.directory/'navigation';directory.mkdir(exist_ok=True)
        raw=canonical({'graph':graph,'capture':capture})
        if len(raw)>32*1024*1024:raise RepositoryError('NAVIGATION_LIMIT','Project map exceeds metadata bound',3)
        with (directory/(capture['capture_id']+'.json')).open('xb') as stream:stream.write(raw)
        self.capture,self.graph=capture,graph
        return graph
    def ensure(self):
        return self.graph if self.graph is not None else self.refresh()
    def payload(self):
        self.ensure()
        summary={key:self.capture[key] for key in ['capture_id','captured_at','repository','worktree','summary','coverage']}
        return {'graph':self.graph,'capture':summary,'source_capabilities':self.source.capabilities.as_dict()}
    def read_source(self,path_id,version='captured'):
        self.ensure();path_bytes(path_id)
        if not any(f['id']==path_id for f in self.capture['files']):raise RepositoryError('PATH_NOT_REGISTERED','Path is outside the selected capture')
        if version=='captured':
            meta=self.graph['source_captures'].get(path_id)
            if not meta or not meta.get('sha256'):return {'kind':'unavailable','text':None,'version':version,'path_id':path_id}
            sha=meta['sha256'];cache=self.store.directory/'sources'/sha
            raw=self.store.read_source_bytes(sha)
            return dict(meta,**{'text':classify(raw).get('text'),'version':'captured','snapshot_path':str(cache),'path_id':path_id})
        if version not in ['head','index','working','stage1','stage2','stage3']:raise RepositoryError('INVALID_VERSION','Unknown source version')
        return self.source.read_legacy(self.capture,path_id,version)

class PortalServer(ThreadingHTTPServer):
    daemon_threads=False
    block_on_close=True
    def __init__(self,project=None,hosted=None,*,data_dir=None,settings=None,source_factory=None):
        directory=project.store.directory if project else data_dir
        self.hosted=hosted or HostedServices(directory)
        self.navigation=NavigationHub(directory,project,self.hosted,settings,source_factory)
        self.initial_job=None
        self.project=project;self.token=secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1',0),PortalHandler)
    def server_close(self):
        if self.project is not None:self.project.reader.cancel_event.set()
        try:self.navigation.close()
        finally:
            try:self.hosted.close()
            finally:super().server_close()
    @property
    def origin(self):return 'http://127.0.0.1:'+str(self.server_port)

class PortalHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(2)
    def log_message(self,*args):pass
    def respond(self,status,data,kind='application/json; charset=utf-8'):
        raw=data.encode('utf-8') if isinstance(data,str) else canonical(data)
        if len(raw)>16*1024*1024:
            status=413;raw=canonical({'error':'RESPONSE_LIMIT'})
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(raw)
    def allowed(self,api):
        if self.headers.get('Host')!=self.server.origin.removeprefix('http://'):return False
        if self.headers.get('Origin') not in (None,self.server.origin):return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return False
        return not api or hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token)
    def do_GET(self):
        query=urlsplit(self.path)
        if not self.allowed(query.path not in ['/','/favicon.ico']):return self.respond(403,{'error':'REQUEST_REFUSED'})
        if query.path=='/favicon.ico':
            self.send_response(204);self.end_headers();return
        if query.path=='/':return self.respond(200,html({'mode':'live','token':self.server.token,'supports_sources':True,'initial_job':self.server.initial_job}),'text/html; charset=utf-8')
        if query.path=='/api/registrations' or query.path.startswith('/api/jobs/'):
            if query.query:return self.respond(400,{'error':'REQUEST_REFUSED'})
            try:return self.respond(200,self.server.hosted.get_api(query.path))
            except RepositoryError as e:return self.respond(400,{'error':e.code,'message':'Repository request did not complete'})
            except (ValueError,OSError,TypeError):return self.respond(400,{'error':'UNAVAILABLE'})
        values=parse_qs(query.query)
        if any(len(v)!=1 for v in values.values()):return self.respond(400,{'error':'AMBIGUOUS_QUERY'})
        def field(key,default=None):return values.get(key,[default])[0]
        if query.path.startswith('/api/nav/'):
            try:return self.respond(200,self.server.navigation.get_api(query.path,{k:v[0] for k,v in values.items()}))
            except RepositoryError as e:return self.respond(409,{'error':e.code,'message':'Navigation request did not complete'})
            except (OSError,ValueError,TypeError,KeyError):return self.respond(400,{'error':'UNAVAILABLE'})
        try:
            navigation=self.server.navigation
            if query.path=='/api/graph':result=navigation.payload()
            elif query.path=='/api/source':result=navigation.source(field('path'),field('version','captured'),field('context'))
            elif query.path=='/api/compare':
                result=navigation.comparison(field('path'),field('left','head'),field('right','captured'),field('context'))
                # Keep historical v1 cached comparison/export behavior.
                if navigation.active is None and self.server.project is not None:
                    project=self.server.project
                    with project.lock:
                        key=digest(canonical([project.capture['capture_id'],field('path'),field('left','head'),field('right','captured')]))
                        folder=project.store.directory/'comparisons';folder.mkdir(exist_ok=True)
                        try:
                            with (folder/(key+'.json')).open('xb') as stream:stream.write(canonical(result))
                        except FileExistsError:pass
            else:return self.respond(404,{'error':'NOT_FOUND'})
            self.respond(200,result)
        except RepositoryError as error:self.respond(409 if error.exit_code==5 or error.code=='CONTEXT_CHANGED' else 400,{'error':error.code,'message':str(error)})
        except (ValueError,OSError,KeyError,TypeError):self.respond(400,{'error':'UNAVAILABLE','message':'Requested data is unavailable'})
    def read_json_body(self):
        values=self.headers.get_all('Content-Length',[])
        if len(values)!=1 or self.headers.get('Transfer-Encoding') or not values[0].isdigit() or not 0<int(values[0])<=8192 or self.headers.get('Content-Type','').split(';',1)[0].lower()!='application/json':raise RepositoryError('INVALID_BODY','Expected bounded JSON')
        raw=self.rfile.read(int(values[0]))
        if len(raw)!=int(values[0]):raise RepositoryError('INVALID_BODY','Incomplete body')
        return strict_json(raw)
    def do_POST(self):
        if not self.allowed(True):return self.respond(403,{'error':'REQUEST_REFUSED'})
        if self.path.startswith('/api/registrations') or self.path.startswith('/api/jobs/') or self.path.startswith('/api/nav/'):
            try:
                body=self.read_json_body();handler=self.server.navigation if self.path.startswith('/api/nav/') else self.server.hosted
                return self.respond(200,handler.post_api(self.path,body))
            except RepositoryError as e:return self.respond(400,{'error':e.code,'message':'Repository request did not complete'})
            except (OSError,ValueError,TypeError,KeyError):return self.respond(400,{'error':'INVALID_BODY'})
        if self.path!='/api/refresh' or self.headers.get('Content-Length','0')!='0':return self.respond(400,{'error':'REQUEST_REFUSED'})
        try:
            if self.server.project is None:raise RepositoryError('NO_LOCAL_PROJECT','Attach a local project before local refresh')
            self.server.navigation.select(source='local')
            with self.server.project.lock:
                self.server.project.refresh()
            self.respond(200,self.server.navigation.payload())
        except RepositoryError as error:self.respond(409,{'error':error.code,'message':str(error)})
        except (OSError,ValueError):self.respond(400,{'error':'REFRESH_FAILED'})
