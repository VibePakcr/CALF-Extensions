"""Installed entry metadata, bounded local manual assets and authenticated shutdown."""
import json
from pathlib import Path
import socket,tempfile,threading,unittest
import urllib.error,urllib.request
from ..viewer import PortalServer
from ..http_reader import HTTPError

class InstalledViewer(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();manuals=self.root/'manuals';manuals.mkdir();(manuals/'ko.html').write_text('<meta charset="utf-8">한글 안내',encoding='utf8');(manuals/'shot.png').write_bytes(b'PNG-FIXTURE')
        self.server=PortalServer(data_dir=self.root/'data',installation={'id':'calf.repository.navigator','version':'0.1.0-dev.1','lock':'a'*64},manual_root=manuals);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start();self.addCleanup(self.close)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(3);self.assertFalse(self.thread.is_alive())
    def get(self,path,body=None,auth=False):
        headers={'Authorization':'Bearer '+self.server.token} if auth else {}
        if body is not None:headers['Content-Type']='application/json'
        return urllib.request.urlopen(urllib.request.Request(self.server.origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers),timeout=3)
    def test_installation_manuals_and_public_paths(self):
        with self.get('/') as r:page=r.read().decode()
        boot=json.loads(page.split('window.CALF_PORTAL=',1)[1].split(';</script>',1)[0]);self.assertEqual(boot['installation']['id'],'calf.repository.navigator');self.assertTrue(boot['manuals_available']);self.assertNotIn(str(self.root),json.dumps(boot))
        with self.get('/manual/ko.html') as r:self.assertIn('한글',r.read().decode());self.assertIn("img-src 'self'",r.headers['Content-Security-Policy'])
        with self.get('/manual/shot.png') as r:self.assertEqual(r.read(),b'PNG-FIXTURE');self.assertEqual(r.headers['Content-Type'],'image/png')
        for path in ['/manual/../private.html','/manual/%2e%2e/private.html','/manual/ko.html?token=x','/manual/unknown.json']:
            with self.assertRaises(urllib.error.HTTPError):self.get(path)
    def test_stop_requires_authentication_and_empty_body(self):
        for body,auth,code in [({},False,403),({'extra':True},True,400)]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.get('/api/stop',body,auth)
            self.assertEqual(e.exception.code,code);self.assertTrue(self.thread.is_alive())
        address=self.server.server_address
        with self.get('/api/stop',{},True) as r:self.assertEqual(json.load(r)['state'],'STOPPING')
        self.thread.join(3);self.assertFalse(self.thread.is_alive());self.server.server_close();s=socket.socket();s.settimeout(.1)
        try:self.assertNotEqual(s.connect_ex(address),0)
        finally:s.close()
    def test_stop_cancels_owned_collection_without_publication(self):
        entered=threading.Event()
        class Source:
            report={}
            def __init__(self,cancel):self.cancel=cancel
            def pin(self,*args):entered.set();self.cancel.wait(5);raise HTTPError('CANCELLED')
            def close(self):pass
        reg=self.server.hosted.registry.add('github','https://github.com/fixture/repo');reg=self.server.hosted.registry.bind(reg.id,reg.version,{'id':42,'full_name':'fixture/repo'});self.server.navigation._factory=lambda reg,cancel,budget:Source(cancel);job=self.server.navigation.collect(reg.id,'branch','main');self.assertTrue(entered.wait(2))
        with self.get('/api/stop',{},True) as r:self.assertEqual(r.status,200)
        self.thread.join(3);self.server.server_close();self.assertEqual(self.server.navigation.inspect(job['id'])['state'],'CANCELLED');self.assertEqual(self.server.navigation.views.summaries(),[])
