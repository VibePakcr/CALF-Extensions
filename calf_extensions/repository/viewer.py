"""User-opened loopback project portal. Only fixed read APIs and explicit refresh."""
import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from .analyze import analyze
from .capture import Store,scan
from .compare import source,compare
from .git_reader import GitReader
from .model import RepositoryError,canonical,classify,digest,path_bytes,validate_settings

ASSETS=Path(__file__).parent/'assets'


def html(bootstrap):
    data=json.dumps(bootstrap,ensure_ascii=True,allow_nan=False).replace('<','\\u003c')
    return (ASSETS/'portal.html').read_text(encoding='utf-8').replace('/*BOOTSTRAP*/','window.CALF_PORTAL='+data+';').replace('/*STYLE*/',(ASSETS/'portal.css').read_text(encoding='utf-8')).replace('/*SCRIPT*/',(ASSETS/'portal.js').read_text(encoding='utf-8').replace('</script','<\\/script'))

class Project:
    def __init__(self,root,data_dir,git=None,settings=None):
        self.reader=GitReader(root,git);self.reader.discover();self.store=Store(data_dir,self.reader);self.settings=validate_settings({} if settings is None else settings);self.capture=None;self.graph=None;self.lock=threading.RLock()
    def refresh(self):
        capture=scan(self.reader,self.store);graph=analyze(self.reader,self.store,capture,self.settings)
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
        return {'graph':self.graph,'capture':summary}
    def read_source(self,path_id,version='captured'):
        self.ensure();path_bytes(path_id)
        if not any(f['id']==path_id for f in self.capture['files']):raise RepositoryError('PATH_NOT_REGISTERED','Path is outside the selected capture')
        if version=='captured':
            meta=self.graph['source_captures'].get(path_id)
            if not meta or not meta.get('sha256'):return {'kind':'unavailable','text':None,'version':version,'path_id':path_id}
            sha=meta['sha256'];cache=self.store.directory/'sources'/sha
            raw=cache.read_bytes()
            if digest(raw)!=sha:raise RepositoryError('SOURCE_CACHE_CHANGED','Captured source changed')
            return dict(meta,**{'text':classify(raw).get('text'),'version':'captured','snapshot_path':str(cache),'path_id':path_id})
        if version not in ['head','index','working','stage1','stage2','stage3']:raise RepositoryError('INVALID_VERSION','Unknown source version')
        return source(self.reader,self.store,self.capture,path_id,version)

class PortalServer(ThreadingHTTPServer):
    daemon_threads=False
    block_on_close=True
    def __init__(self,project):
        self.project=project;self.token=secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1',0),PortalHandler)
    def server_close(self):
        self.project.reader.cancel_event.set()
        super().server_close()
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
        if query.path=='/':return self.respond(200,html({'mode':'live','token':self.server.token}),'text/html; charset=utf-8')
        values=parse_qs(query.query)
        if any(len(v)!=1 for v in values.values()):return self.respond(400,{'error':'AMBIGUOUS_QUERY'})
        def field(key,default=None):return values.get(key,[default])[0]
        try:
            project=self.server.project
            with project.lock:
                if query.path=='/api/graph':result=project.payload()
                elif query.path=='/api/source':result=project.read_source(field('path'),field('version','captured'))
                elif query.path=='/api/compare':
                    result=compare(project.read_source(field('path'),field('left','head')),project.read_source(field('path'),field('right','captured')))
                    key=digest(canonical([project.capture['capture_id'],field('path'),field('left','head'),field('right','captured')]))
                    folder=project.store.directory/'comparisons';folder.mkdir(exist_ok=True)
                    try:
                        with (folder/(key+'.json')).open('xb') as stream:stream.write(canonical(result))
                    except FileExistsError:pass
                else:return self.respond(404,{'error':'NOT_FOUND'})
                self.respond(200,result)
        except RepositoryError as error:self.respond(409 if error.exit_code==5 else 400,{'error':error.code,'message':str(error)})
        except (ValueError,OSError,KeyError,TypeError):self.respond(400,{'error':'UNAVAILABLE','message':'Requested data is unavailable'})
    def do_POST(self):
        if not self.allowed(True):return self.respond(403,{'error':'REQUEST_REFUSED'})
        if self.path!='/api/refresh' or self.headers.get('Content-Length','0')!='0':return self.respond(400,{'error':'REQUEST_REFUSED'})
        try:
            with self.server.project.lock:
                self.server.project.refresh();self.respond(200,self.server.project.payload())
        except RepositoryError as error:self.respond(409,{'error':error.code,'message':str(error)})
        except (OSError,ValueError):self.respond(400,{'error':'REFRESH_FAILED'})
