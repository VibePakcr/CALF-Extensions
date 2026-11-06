"""Actual loopback common APIs and offline privacy/byte coverage contracts."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import signal
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from . import test_navigation_h4 as fixtures
from ..model import canonical,digest,path_record
from ..offline import export_view
from ..viewer import PortalServer


class PortalH4(unittest.TestCase):
    setUp=fixtures.NavigationH4.setUp
    g=fixtures.NavigationH4.g
    commit=fixtures.NavigationH4.commit
    reader=fixtures.NavigationH4.reader
    response=fixtures.NavigationH4.response
    fixture=fixtures.NavigationH4.fixture
    error=fixtures.NavigationH4.error
    hub=fixtures.NavigationH4.hub
    collect=fixtures.NavigationH4.collect
    def api(self,server,route,body=None,auth=True):
        headers={'Authorization':'Bearer '+server.token} if auth else {}
        if body is not None:headers['Content-Type']='application/json'
        with urllib.request.urlopen(urllib.request.Request(server.origin+'/api/'+route,data=canonical(body) if body is not None else None,headers=headers),timeout=5) as response:return json.load(response)
    def portal(self):
        hub=self.hub(local=True);server=PortalServer(hub.local,hub.hosted,source_factory=hub._factory);thread=threading.Thread(target=server.serve_forever);thread.start()
        def close():server.shutdown();server.server_close();thread.join(4);self.assertFalse(thread.is_alive())
        self.addCleanup(close);return hub,server
    def test_common_api_collect_switch_history_source_diff_and_guard(self):
        a=self.commit(b'A\n');b=self.commit(b'B\n');hub,server=self.portal();local=self.api(server,'graph');self.assertEqual(local['view']['source_id'],'local')
        self.assertTrue(self.api(server,'nav/sources')['sources']);job=self.api(server,'nav/collect',{'source_id':hub.registration.id,'ref_kind':'branch','ref_name':'main'});result=server.navigation.wait(job['id']);self.assertEqual(result['state'],'SUCCEEDED',result)
        active=self.api(server,'graph');self.assertEqual(active['view']['right_commit'],b);self.assertEqual(active['view']['left_commit'],a);context=active['view']['context_id'];key=path_record(b'file.txt')['id'];right=self.api(server,'source?path='+key+'&version=right&context='+context);self.assertEqual(right['text'],'B\n')
        self.assertIn('+B',self.api(server,'compare?path='+key+'&left=left&right=right&context='+context)['lines']);self.assertEqual(self.api(server,'nav/changes?context='+context)['total'],1)
        self.api(server,'nav/select',{'source_id':'local'});self.assertEqual(self.api(server,'graph')['view']['source_id'],'local');self.api(server,'nav/select',{'context_id':context});self.assertEqual(self.api(server,'graph')['view']['context_id'],context)
        with self.assertRaises(urllib.error.HTTPError) as e:self.api(server,'source?path='+key+'&version=right&context='+('0'*64))
        self.assertEqual(e.exception.code,409);self.assertEqual(json.loads(e.exception.read())['error'],'CONTEXT_CHANGED');self.assertEqual(len(self.api(server,'nav/history?source='+hub.registration.id)['views']),1)
    def test_loopback_auth_typed_json_no_token_or_url_proxy(self):
        self.commit();hub,server=self.portal()
        with self.assertRaises(urllib.error.HTTPError) as e:self.api(server,'nav/sources',auth=False)
        self.assertEqual(e.exception.code,403)
        for body in [{'source_id':hub.registration.id,'ref_kind':'branch','ref_name':'main','token':'fixture-private-token'}, {'url':'https://evil.invalid'}, []]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.api(server,'nav/collect',body)
            self.assertNotIn('fixture-private-token',e.exception.read().decode())
        self.assertEqual(server.navigation.views.summaries(),[])
    def test_source_request_does_not_wait_for_slow_collection(self):
        self.commit();hub,server=self.portal();entered=threading.Event();release=threading.Event();factory=server.navigation._factory
        def slow(reg,cancel,budget):
            source=factory(reg,cancel,budget);pin=source.pin
            def wait(*args):entered.set();release.wait(4);return pin(*args)
            source.pin=wait;return source
        server.navigation._factory=slow;old=self.api(server,'graph');job=self.api(server,'nav/collect',{'source_id':hub.registration.id,'ref_kind':'branch','ref_name':'main'});self.assertTrue(entered.wait(2))
        try:
            import time
            start=time.monotonic();self.assertEqual(self.api(server,'graph')['view'],old['view']);self.assertLess(time.monotonic()-start,1);self.api(server,'nav/jobs/'+job['id']+'/cancel',{});release.set();self.assertEqual(server.navigation.wait(job['id'])['state'],'CANCELLED')
        finally:release.set()
    def test_v2_export_opt_in_origins_raw_bytes_and_diff_without_originals(self):
        self.commit(b'old\r\n',name='file.py');self.commit(b'\xef\xbb\xbfnew\n',name='file.py');hub=self.hub();job=self.collect(hub);context=job['result']['context_id'];self.root.rename(self.base/'hidden-original');key=path_record(b'file.py')['id']
        with patch('subprocess.Popen',side_effect=AssertionError('No Git/provider during retained export')):
            result=export_view(hub.store.directory,context,self.base/'offline',True,False)
        self.assertEqual(result['state'],'COMPLETE');page=(self.base/'offline/START_HERE.html').read_text();self.assertNotIn('https://gitlab.com/group/sub/repo',page);self.assertNotIn(str(hub.store.directory),page)
        marker='window.CALF_PORTAL=';bootstrap=json.loads(page.split(marker,1)[1].split(';</script>',1)[0]);self.assertNotIn('snapshot_path',json.dumps(bootstrap));self.assertNotIn('current_path',json.dumps(bootstrap));self.assertEqual(base64.b64decode(bootstrap['sources'][key+':right']['raw_base64']),b'\xef\xbb\xbfnew\n');self.assertEqual(base64.b64decode(bootstrap['sources'][key+':left']['raw_base64']),b'old\r\n');self.assertTrue(bootstrap['comparisons'][key]['lines']);self.assertFalse(bootstrap['payload']['export']['origin_included']);self.assertNotIn('provider_url',bootstrap['sources'][key+':right'])
        manifest=json.loads((self.base/'offline/MANIFEST.json').read_text())
        for name,expected in manifest['files'].items():self.assertEqual(hashlib.sha256((self.base/'offline'/name).read_bytes()).hexdigest(),expected)
        result=export_view(hub.store.directory,context,self.base/'origin',False,True);page=(self.base/'origin/START_HERE.html').read_text();self.assertIn('https://gitlab.com/group/sub/repo',page);self.assertNotIn('raw_base64',page.split(marker,1)[1].split(';</script>',1)[0]);self.assertEqual(result['manifest']['coverage']['source_entries'],0)
    def test_default_offline_has_no_sources_or_editor_paths_and_escapes_html(self):
        self.commit(b'"""<script>window.H4_ATTACK=true</script>"""\n',name='a.py');hub=self.hub();job=self.collect(hub);result=export_view(hub.store.directory,job['result']['context_id'],self.base/'plain');self.assertEqual(result['manifest']['coverage']['source_entries'],0);text=(self.base/'plain/START_HERE.html').read_text();self.assertNotIn('<script>window.H4_ATTACK=true</script>',text);self.assertIn('\\u003cscript',text)
    def test_export_destination_refusals_create_no_output_in_source(self):
        self.commit();hub=self.hub();job=self.collect(hub);context=job['result']['context_id'];self.error('OUTPUT_IN_REPOSITORY',lambda:export_view(hub.store.directory,context,self.root/'forbidden'));self.assertFalse((self.root/'forbidden').exists());self.error('OUTPUT_IN_DATA',lambda:export_view(hub.store.directory,context,hub.store.directory/'export'))
    def test_view_corruption_and_empty_baseline_proof_are_refused(self):
        self.commit();hub=self.hub();job=self.collect(hub);context=job['result']['context_id'];record=dict(hub.active.record,empty_baseline={'commit':'0'*40,'parents':[],'basis':'FIRST_PARENT_NONE'});self.error('EMPTY_BASELINE_UNPROVEN',lambda:fixtures.RetainedView(digest(canonical(record)),record,hub.store))
        path=hub.views.root/'records'/(context+'.json');path.write_bytes(b'{}');self.error('VIEW_CHANGED',lambda:hub.views.load(context))
    def test_cli_cached_view_and_export_do_not_need_repository_or_provider(self):
        self.commit();hub=self.hub();job=self.collect(hub);context=job['result']['context_id'];output=self.base/'cli-export'
        result=subprocess.run([sys.executable,'-m','calf_extensions.repository.cli','export','--data-dir',str(hub.store.directory),'--view',context,'--output',str(output),'--include-source'],capture_output=True,text=True,cwd=Path(__file__).parents[3],timeout=20);self.assertEqual(result.returncode,0,result.stderr);self.assertTrue((output/'START_HERE.html').is_file())

        # Exercise the actual hosted-only foreground CLI, without the source worktree.
        self.root.rename(self.base/'hidden-original')
        process=subprocess.Popen([sys.executable,'-m','calf_extensions.repository.cli','open','--data-dir',str(hub.store.directory),'--view',context,'--no-browser'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=Path(__file__).parents[3])
        ready=[];thread=threading.Thread(target=lambda:ready.append(process.stdout.readline()));thread.start()
        try:
            thread.join(10);self.assertFalse(thread.is_alive(),'Foreground CLI did not become ready');line=json.loads(ready[0]);self.assertEqual(line['state'],'READY');origin=line['url']
            with urllib.request.urlopen(origin,timeout=3) as response:page=response.read().decode()
            token=json.loads(page.split('window.CALF_PORTAL=',1)[1].split(';</script>',1)[0])['token']
            with urllib.request.urlopen(urllib.request.Request(origin+'/api/graph',headers={'Authorization':'Bearer '+token}),timeout=3) as response:self.assertEqual(json.load(response)['view']['context_id'],context)
        finally:
            if process.poll() is None:
                if sys.platform=='win32':process.terminate()
                else:process.send_signal(signal.SIGINT)
            try:process.communicate(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.communicate();self.fail('Foreground CLI did not stop')
            thread.join(2)
        # Windows TerminateProcess is owned cleanup, not a graceful console Ctrl+C proof.
        self.assertEqual(process.returncode,1 if sys.platform=='win32' else 0)
        from urllib.parse import urlsplit
        address=urlsplit(origin);connection=socket.socket();connection.settimeout(.25)
        try:self.assertNotEqual(connection.connect_ex((address.hostname,address.port)),0)
        finally:connection.close()
