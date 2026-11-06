"""H1 independent HTTP/registry/job fixtures; no real provider or owner credentials."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from ..hosted import HostedServices
from ..http_reader import API_VERSION,Budget,HTTPError,HTTPReader,RequestSpec,Response,WorkerTransport,follow_url,strict_json
from ..model import RepositoryError,canonical
from ..registrations import Registry
from ..viewer import Project,PortalServer
from . import test_git_contract as gitfixtures

TOKEN='fixture-only-canary-credential-20261107'
META={'id':42,'full_name':'Owner/Repo','html_url':'https://github.com/Owner/Repo','private':True}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        seen={'path':self.path,'headers':dict(self.headers)}
        with self.server.guard:self.server.seen.append(seen);behavior=self.server.behavior
        status,headers,body=behavior(seen)
        if not isinstance(body,bytes):body=canonical(body)
        self.send_response(status)
        for key,value in headers.items():self.send_header(key,value)
        if not any(k.lower()=='content-type' for k in headers):self.send_header('Content-Type','application/json')
        if not any(k.lower()=='content-length' for k in headers):self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass


class H1(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.registry=Registry(self.base/'app');self.patch=patch.dict(os.environ,{'H1_FIXTURE_TOKEN':TOKEN});self.patch.start();self.addCleanup(self.patch.stop)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Fixture);self.http.daemon_threads=True;self.http.guard=threading.Lock();self.http.seen=[];self.http.behavior=lambda request:(200,{},META)
        self.thread=threading.Thread(target=self.http.serve_forever);self.thread.start();self.addCleanup(self.stop_http)
    def stop_http(self):self.http.shutdown();self.http.server_close();self.thread.join(timeout=3)
    def registration(self,provider='github',bound=False,credential=True):
        reg=self.registry.add(provider,'https://github.com/Owner/Repo' if provider=='github' else 'https://gitlab.com/group/sub/repo','H1_FIXTURE_TOKEN' if credential else None)
        if bound:
            data=META if provider=='github' else {'id':17,'path_with_namespace':'group/sub/repo','web_url':'https://gitlab.com/group/sub/repo','visibility':'private'}
            reg=self.registry.bind(reg.id,reg.version,data)
        return reg
    def transport(self,mode='http'):
        return WorkerTransport([sys.executable,'-m','calf_extensions.repository.tests._http_fixture_worker',str(self.http.server_port),mode])
    def reader(self,reg=None,mode='http'):
        value=HTTPReader(reg or self.registration(),self.transport(mode));self.addCleanup(value.close);return value
    def error(self,code,call):
        with self.assertRaises(RepositoryError) as caught:call()
        self.assertEqual(caught.exception.code,code);self.assertNotIn(TOKEN,str(caught.exception));return caught.exception

    def test_registration_is_explicit_local_and_reference_only(self):
        self.assertEqual(self.registry.list(),[]);self.assertFalse(self.registry.root.exists())
        with patch.object(os.environ,'get',side_effect=AssertionError('No credential lookup while registering')):reg=self.registration()
        raw=(self.registry.root/(reg.id+'.json')).read_text();self.assertIn('H1_FIXTURE_TOKEN',raw);self.assertNotIn(TOKEN,raw);self.assertIsNone(reg.repository_id);self.assertEqual(self.http.seen,[])
        self.assertEqual(self.registration().id,reg.id);self.assertNotIn('credential_env',reg.public())
    def test_registration_url_and_environment_constraints(self):
        for url in ['http://github.com/o/r','https://user:secret@github.com/o/r','https://github.com/o/r/tree/main','https://github.com/o/r?token=secret','https://evil.invalid/o/r','https://gitlab.com/g/%2e%2e/r']:
            with self.subTest(url=url),self.assertRaises(RepositoryError):self.registry.add('gitlab' if 'gitlab' in url else 'github',url)
        self.error('INVALID_CREDENTIAL_REFERENCE',lambda:self.registry.add('github','https://github.com/o/r','TOKEN=secret'))
        gl=self.registration('gitlab');self.assertIn('group/sub/repo',gl.url)
    def test_gitlab_namespace_is_encoded_once(self):
        reg=self.registry.add('gitlab','https://gitlab.com/team/한글+sub/repo')
        self.http.behavior=lambda request:(200,{}, {'id':17,'path_with_namespace':'team/한글+sub/repo'})
        self.reader(reg).request(RequestSpec('identity'))
        self.assertEqual(self.http.seen[0]['path'],'/api/v4/projects/team%2F%ED%95%9C%EA%B8%80%2Bsub%2Frepo')
        self.assertEqual(self.registry.bind(reg.id,reg.version,{'id':17,'path_with_namespace':'team/한글+sub/repo'}).repository_id,'17')
    def test_truncated_http_body_is_not_successful_metadata(self):
        self.http.behavior=lambda request:(200,{'Content-Length':'100','Connection':'close'},b'{"id":42}')
        reader=self.reader();self.error('HTTP_IO',lambda:reader.request(RequestSpec('identity')))
        self.assertFalse(reader._cache);self.assertEqual(len(self.http.seen),3)
    def test_registration_history_removal_and_identity_conflicts(self):
        reg=self.registration();bound=self.registry.bind(reg.id,reg.version,META);raw=(self.registry.root/(reg.id+'.json')).read_bytes()
        self.error('IDENTITY_MISMATCH',lambda:self.registry.bind(reg.id,bound.version,dict(META,id=99)))
        self.assertEqual((self.registry.root/(reg.id+'.json')).read_bytes(),raw)
        renamed=self.registry.bind(reg.id,bound.version,dict(META,full_name='Owner/Renamed',html_url='https://github.com/owner/renamed'))
        self.assertEqual(renamed.repository_id,'42');self.assertEqual(renamed.effective_url,'https://github.com/owner/renamed')
        captured=self.registry.data_dir/'captures';captured.mkdir();(captured/'retained').write_bytes(b'unchanged');self.registry.remove(reg.id);self.assertEqual(self.registry.list(),[]);self.assertEqual((captured/'retained').read_bytes(),b'unchanged');self.assertTrue((self.registry.root/'history'/(reg.id+'-1.json')).exists())
    def test_registry_refuses_git_and_foreign_namespace(self):
        project=self.base/'repo';project.mkdir();(project/'.git').mkdir();self.error('OUTPUT_IN_REPOSITORY',lambda:Registry(project/'data').add('github','https://github.com/o/r'))
        foreign=self.base/'foreign';(foreign/'registrations').mkdir(parents=True);self.error('REGISTRY_PATH_REFUSED',lambda:Registry(foreign).add('github','https://github.com/o/r'))
    def test_endpoint_policy_is_registered_and_read_only(self):
        reg=self.registration();self.error('SOURCE_UNVERIFIED',lambda:RequestSpec('blob','1'*40).url(reg))
        for op in ['health','users','projects','write','compare']:
            self.error('REQUEST_REFUSED',lambda:RequestSpec(op))
        self.error('REQUEST_REFUSED',lambda:RequestSpec('identity',method='POST'))
        gl=self.registration('gitlab',True);url=RequestSpec('tree','a'*40,True).url(gl);self.assertTrue(url.startswith('https://gitlab.com/api/v4/projects/17/repository/tree?'));self.assertIn('ref='+('a'*40),url)
    def test_owned_worker_keeps_credentials_out_of_argv_env_and_witness(self):
        reader=self.reader();result=reader.request(RequestSpec('identity'));self.assertEqual(result.json()['id'],42);request=self.http.seen[0]
        self.assertEqual(request['headers']['Authorization'],'Bearer '+TOKEN);self.assertEqual(request['headers']['X-GitHub-Api-Version'],API_VERSION)
        self.assertNotIn(TOKEN,' '.join(reader.transport.command));self.assertNotIn(TOKEN,str(reader.witness));self.assertTrue(reader.transport.last_cleanup['stopped']);self.assertTrue(reader.transport.last_cleanup['threads_stopped'])
    def test_gitlab_token_is_bound_to_its_header_and_scope(self):
        reg=self.registration('gitlab');self.http.behavior=lambda request:(200,{}, {'id':17,'path_with_namespace':'group/sub/repo','visibility':'private'})
        self.reader(reg).request(RequestSpec('identity'));headers=self.http.seen[0]['headers'];self.assertEqual(headers['PRIVATE-TOKEN'],TOKEN);self.assertNotIn('Authorization',headers);self.assertIn('group%2Fsub%2Frepo',self.http.seen[0]['path'])
    def test_credential_absence_and_echo_never_become_cached_data(self):
        reader=self.reader();os.environ.pop('H1_FIXTURE_TOKEN');self.error('CREDENTIAL_MISSING_OR_INVALID',lambda:reader.request(RequestSpec('identity')));self.assertEqual(self.http.seen,[])
        os.environ['H1_FIXTURE_TOKEN']=TOKEN;self.http.behavior=lambda req:(200,{'ETag':'"echo"'},dict(META,message=TOKEN));self.error('CREDENTIAL_ECHO',lambda:reader.request(RequestSpec('identity')));self.assertFalse(reader._cache);self.assertNotIn(TOKEN,str(reader.witness))
    def test_etag_and_auth_rotation_partition_cache(self):
        count=[]
        def behavior(request):
            count.append(request)
            return (304,{},b'') if request['headers'].get('If-None-Match') else (200,{'ETag':'"v1"'},META)
        self.http.behavior=behavior;reader=self.reader();a=reader.request(RequestSpec('identity'));b=reader.request(RequestSpec('identity'));self.assertTrue(b.cached);self.assertEqual(a.body,b.body)
        os.environ['H1_FIXTURE_TOKEN']=TOKEN+'-rotated';c=reader.request(RequestSpec('identity'));self.assertFalse(c.cached);self.assertNotIn('If-None-Match',count[-1]['headers'])
    def test_304_without_cache_is_not_an_empty_repository(self):
        self.http.behavior=lambda req:(304,{},b'');self.error('CACHE_MISSING',lambda:self.reader().request(RequestSpec('identity')))
    def test_auth_denial_and_rate_limit_are_distinct(self):
        reader=self.reader()
        for status,code in [(401,'AUTH_REQUIRED'),(403,'ACCESS_DENIED'),(404,'ACCESS_UNKNOWN')]:
            self.http.behavior=lambda req,status=status:(status,{}, {'message':'unavailable'});self.error(code,lambda:reader.request(RequestSpec('identity')))
        self.http.behavior=lambda req:(429,{'Retry-After':'60'},{'message':'limited'});first=self.error('RATE_LIMITED',lambda:reader.request(RequestSpec('identity')));count=len(self.http.seen);self.error('RATE_LIMITED',lambda:reader.request(RequestSpec('identity')));self.assertEqual(len(self.http.seen),count);self.assertGreater(first.retry_at,time.time()+50)
    def test_retry_and_budget_are_bounded(self):
        calls=[]
        def behavior(req):calls.append(1);return (503,{},b'') if len(calls)<3 else (200,{},META)
        self.http.behavior=behavior;self.assertEqual(self.reader().request(RequestSpec('identity')).json()['id'],42);self.assertEqual(len(calls),3)
        self.http.behavior=lambda req:(503,{},b'');self.error('REQUEST_LIMIT',lambda:self.reader().request(RequestSpec('identity'),budget=Budget(limit=2)))
    def test_foreign_redirect_and_identity_change_are_refused(self):
        self.http.behavior=lambda req:(302,{'Location':'https://evil.invalid/stolen'},b'');self.error('URL_REFUSED',lambda:self.reader().request(RequestSpec('identity')));self.assertEqual(len(self.http.seen),1)
        bound=self.registry.bind(self.registry.list()[0].id,1,META);self.http.behavior=lambda req:(301,{'Location':'https://api.github.com/repositories/99'},b'');self.error('REDIRECT_REFUSED',lambda:self.reader(bound).request(RequestSpec('identity')))
    def test_same_identity_redirect_is_resolved_without_enumeration(self):
        self.http.behavior=lambda req:(301,{'Location':'https://api.github.com/repositories/42'},b'') if req['path'].startswith('/repos/') else (200,{},META)
        result=self.reader().request(RequestSpec('identity'));self.assertEqual(result.json()['id'],42);self.assertEqual([x['path'] for x in self.http.seen],['/repos/owner/repo','/repositories/42'])
    def test_pagination_keeps_commit_repository_and_auth_partition(self):
        reg=self.registration('gitlab',True);spec=RequestSpec('tree','a'*40,True);url=spec.url(reg);next_url=url+'&page_token=next'
        self.http.behavior=lambda req:(200,{'Link':'<'+next_url+'>; rel="next"'},[]);reader=self.reader(reg);a=reader.request(spec);b=reader.follow_next(a);self.assertEqual(b.json(),[]);self.error('PAGINATION_LOOP',lambda:reader.follow_next(b))
        for bad in [next_url.replace('/17/','/18/'),next_url.replace('a'*40,'b'*40),next_url.replace('gitlab.com','evil.invalid'),next_url+'&unknown=true']:
            with self.assertRaises(RepositoryError):follow_url(reg,spec,url,bad,pagination=True)
        os.environ['H1_FIXTURE_TOKEN']=TOKEN+'-next';self.error('CACHE_PARTITION_MISMATCH',lambda:reader.follow_next(a))
    def test_bad_json_html_and_oversized_blob_are_explicit(self):
        reader=self.reader()
        for headers,body,code in [({'Content-Type':'text/html'},b'<html>login</html>','HTTP_INVALID_CONTENT_TYPE'),({},b'{"x":1,"x":2}','INVALID_JSON'),({},b'{"x":NaN}','INVALID_JSON')]:
            self.http.behavior=lambda req,headers=headers,body=body:(200,headers,body);self.error(code,lambda:reader.request(RequestSpec('identity')))
        reg=self.registration('gitlab',True);self.http.behavior=lambda req:(200,{'Content-Type':'application/octet-stream'},b'x'*(1024*1024+1));self.error('HTTP_RESPONSE_LIMIT',lambda:self.reader(reg).request(RequestSpec('blob','a'*40)))
    def test_cancel_stalled_worker_stops_owned_process_and_threads(self):
        reader=self.reader(mode='hang');cancel=threading.Event();errors=[]
        def run():
            try:reader.request(RequestSpec('identity'),cancel)
            except RepositoryError as e:errors.append(e.code)
        thread=threading.Thread(target=run);thread.start();time.sleep(.15);start=time.monotonic();cancel.set();thread.join(3);self.assertFalse(thread.is_alive());self.assertLess(time.monotonic()-start,3);self.assertEqual(errors,['CANCELLED']);self.assertTrue(reader.transport.last_cleanup['threads_stopped']);self.assertTrue(reader.transport.last_cleanup['stopped'])
    def test_worker_deadline_and_output_bounds(self):
        self.error('HTTP_TIMEOUT',lambda:self.reader(mode='hang').request(RequestSpec('identity'),budget=Budget(deadline=time.monotonic()+.2)))
        reg=self.registration('gitlab',True);reader=self.reader(reg,mode='overflow');self.error('HTTP_RESPONSE_LIMIT',lambda:reader.request(RequestSpec('blob','a'*40)));self.assertTrue(reader.transport.last_cleanup['stopped'])
    def test_real_tls_rejects_untrusted_test_certificate(self):
        executable=shutil.which('openssl')
        if not executable:self.skipTest('Native openssl unavailable for negative TLS fixture')
        key=self.base/'test-key.pem';cert=self.base/'test-cert.pem'
        p=subprocess.run([executable,'req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost'],capture_output=True,timeout=15);self.assertEqual(p.returncode,0)
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);server.seen=[];server.guard=threading.Lock();server.behavior=lambda req:(200,{},META);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key);server.socket=context.wrap_socket(server.socket,server_side=True);thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            transport=WorkerTransport([sys.executable,'-m','calf_extensions.repository.tests._http_fixture_worker',str(server.server_port),'tls']);self.error('HTTP_IO',lambda:HTTPReader(self.registration(),transport).request(RequestSpec('identity')));self.assertEqual(server.seen,[])
        finally:server.shutdown();server.server_close();thread.join(3)
    def test_pagination_reuses_its_original_request_budget(self):
        reg=self.registration('gitlab',True);spec=RequestSpec('tree','a'*40,True);url=spec.url(reg);calls=[]
        def behavior(request):
            calls.append(1);return 200,{'Link':'<'+url+'&page_token='+str(len(calls))+'>; rel="next"'},[]
        self.http.behavior=behavior;reader=self.reader(reg);a=reader.request(spec,budget=Budget(limit=2));b=reader.follow_next(a);self.error('REQUEST_LIMIT',lambda:reader.follow_next(b));self.assertEqual(len(calls),2)
    def test_empty_repository_is_not_inferred_from_zero_size(self):
        gh=self.registration();gh=self.registry.bind(gh.id,gh.version,dict(META,size=0));self.assertEqual(gh.public()['repository_state'],'UNKNOWN')
        gl=self.registration('gitlab');gl=self.registry.bind(gl.id,gl.version,{'id':17,'path_with_namespace':'group/sub/repo','empty_repo':True});self.assertEqual(gl.public()['repository_state'],'EMPTY')
    def test_cli_registration_commands_work_without_provider_access(self):
        root=str(Path(__file__).parents[3]);env=dict(os.environ,PYTHONPATH=root)
        def cli(*args):return subprocess.run([sys.executable,'-m','calf_extensions.repository.cli',*args],env=env,cwd=self.base,capture_output=True)
        data=str(self.base/'cli-data');p=cli('sources','add','--provider','github','--url','https://github.com/owner/repo','--credential-env','H1_FIXTURE_TOKEN','--data-dir',data);self.assertEqual(p.returncode,0,p.stderr.decode());sid=json.loads(p.stdout)['id']
        p=cli('sources','list','--data-dir',data);self.assertEqual(p.returncode,0);self.assertEqual(len(json.loads(p.stdout)['sources']),1);self.assertNotIn(TOKEN,p.stdout.decode());p=cli('sources','remove',sid,'--data-dir',data);self.assertEqual(p.returncode,0);self.assertEqual(self.http.seen,[])


class Jobs(unittest.TestCase):
    setUp=H1.setUp
    stop_http=H1.stop_http
    registration=H1.registration
    transport=H1.transport
    reader=H1.reader
    error=H1.error
    # Do not inherit H1 test methods a second time.
    def test_cancel_does_not_bind_or_publish_identity(self):
        services=HostedServices(self.base/'jobs',lambda reg:HTTPReader(reg,self.transport('hang')));reg=services.registry.add('github','https://github.com/owner/repo','H1_FIXTURE_TOKEN');job=services.probe(reg.id);time.sleep(.15);start=time.monotonic();services.cancel(job['id']);result=services.wait(job['id'],3);self.assertEqual(result['state'],'CANCELLED');self.assertIsNone(result['result']);self.assertIsNone(services.registry.get(reg.id).repository_id);services.close();self.assertLess(time.monotonic()-start,3)
    def test_late_old_response_cannot_replace_new_job(self):
        first=threading.Event();release=threading.Event();guard=threading.Lock();calls=[]
        class FakeClient:
            def request(self,spec,cancel,budget):
                with guard:calls.append(1);number=len(calls)
                if number==1:first.set();release.wait(3)
                class Value:
                    def json(self):return dict(META,id=99 if number==1 else 42)
                return Value()
            def close(self):pass
        services=HostedServices(self.base/'jobs',lambda reg:FakeClient());reg=services.registry.add('github','https://github.com/owner/repo');old=services.probe(reg.id);self.assertTrue(first.wait(2));new=services.probe(reg.id);self.assertEqual(services.wait(new['id'])['state'],'SUCCEEDED');release.set();self.assertEqual(services.wait(old['id'])['state'],'SUPERSEDED');self.assertEqual(services.registry.get(reg.id).repository_id,'42');services.close()


class PortalH1(unittest.TestCase):
    setUp=H1.setUp
    stop_http=H1.stop_http
    transport=H1.transport
    def portal(self):
        root=self.base/'local';root.mkdir();(root/'a.py').write_text('def a():\n    return 1\n');env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')};env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
        def git(*args):subprocess.run(['git','-c','core.hooksPath='+os.devnull,'-c','commit.gpgsign=false','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',*args],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        git('init','-q','-b','main');git('add','.');git('commit','-qm','fixture');project=Project(root,self.base/'live');project.refresh();services=HostedServices(project.store.directory,lambda reg:HTTPReader(reg,self.transport()));server=PortalServer(project,services);thread=threading.Thread(target=server.serve_forever);thread.start()
        def close():server.shutdown();server.server_close();thread.join(3)
        self.addCleanup(close);return project,services,server
    def api(self,server,path,body=None,token=True,origin=None,raw=None):
        headers={'Authorization':'Bearer '+server.token} if token else {}
        if origin:headers['Origin']=origin
        data=raw if raw is not None else canonical(body) if body is not None else None
        if data is not None:headers['Content-Type']='application/json'
        with urllib.request.urlopen(urllib.request.Request(server.origin+path,data=data,headers=headers),timeout=3) as response:return json.load(response)
    def test_loopback_auth_bounded_json_and_credential_output(self):
        project,services,server=self.portal()
        for token,origin in [(False,None),(True,'https://evil.invalid')]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.api(server,'/api/registrations',token=token,origin=origin)
            self.assertEqual(e.exception.code,403)
        for data in [b'{"provider":"github","provider":"gitlab","url":"https://github.com/o/r"}',b'x'*8193,canonical({'provider':'github','url':'https://github.com/o/r','token':TOKEN})]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.api(server,'/api/registrations',raw=data)
            self.assertNotIn(TOKEN,error.exception.read().decode())
        reg=self.api(server,'/api/registrations',{'provider':'github','url':'https://github.com/owner/repo','credential_env':'H1_FIXTURE_TOKEN'});self.assertTrue(reg['credential_configured']);self.assertNotIn('credential_env',reg);self.assertNotIn(TOKEN,str(self.api(server,'/api/registrations')));self.assertEqual(self.http.seen,[])
        removed=self.api(server,'/api/registrations/'+reg['id']+'/remove',{});self.assertFalse(removed['enabled'])
    def test_slow_probe_is_cancellable_and_keeps_local_map_available(self):
        project,services,server=self.portal();before=canonical(project.payload());reached=threading.Event();release=threading.Event()
        def behavior(request):reached.set();release.wait(5);return 200,{},META
        self.http.behavior=behavior
        try:
            reg=self.api(server,'/api/registrations',{'provider':'github','url':'https://github.com/owner/repo','credential_env':'H1_FIXTURE_TOKEN'});job=self.api(server,'/api/jobs/probe',{'source_id':reg['id']});self.assertTrue(reached.wait(3));start=time.monotonic();self.api(server,'/api/graph');self.assertLess(time.monotonic()-start,1)
            self.assertEqual(self.api(server,'/api/jobs/'+job['id'])['state'],'RUNNING');self.api(server,'/api/jobs/'+job['id']+'/cancel',{});result=services.wait(job['id'],3);self.assertEqual(result['state'],'CANCELLED');self.assertIsNone(services.registry.get(reg['id']).repository_id);self.assertEqual(canonical(project.payload()),before)
        finally:release.set()
