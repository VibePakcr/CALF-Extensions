import hashlib
import json
from pathlib import Path
import threading
import unittest
import urllib.request
import urllib.error
from . import test_navigation as fixtures
from . import test_git_contract as gitfixtures
from calf_extensions.repository.viewer import Project,PortalServer
from calf_extensions.repository.export import export_capture
from calf_extensions.repository.model import path_record,RepositoryError

class Portal(unittest.TestCase):
    setUp=gitfixtures.GitFixtures.setUp
    g=gitfixtures.GitFixtures.g
    commit=gitfixtures.GitFixtures.commit
    reader=gitfixtures.GitFixtures.reader
    fixture=fixtures.Navigation.fixture
    def request(self,server,path,token=True,origin=None,method='GET'):
        headers={'Authorization':'Bearer '+server.token} if token else {}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(server.origin+path,headers=headers,method=method),timeout=10)
    def test_actual_read_api_and_export_without_repo(self):
        reader,store,capture,graph=self.fixture();project=Project(self.root,self.base/'live',self.git,{'label':'Portal fixture'})
        server=PortalServer(project);worker=threading.Thread(target=server.serve_forever);worker.start()
        try:
            with self.request(server,'/',token=False) as r:
                page=r.read().decode();self.assertIn('source-map',page);self.assertIn('inspector',page);self.assertIn('frame-ancestors',r.headers['Content-Security-Policy'])
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(server,'/api/graph',token=False)
            self.assertEqual(e.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(server,'/api/graph',origin='https://example.invalid')
            self.assertEqual(e.exception.code,403)
            with self.request(server,'/api/graph') as r:payload=json.load(r)
            key=path_record(b'pkg/service.py')['id']
            with self.request(server,'/api/source?path='+key+'&version=captured') as r:source=json.load(r)
            self.assertIn('def run',source['text'])
            with self.request(server,'/api/compare?path='+key+'&left=head&right=captured') as r:comparison=json.load(r)
            self.assertTrue(comparison['same_bytes'])
            with self.assertRaises(urllib.error.HTTPError):self.request(server,'/api/source?path=..%2Fsecret')
            cid=payload['capture']['capture_id'];old=(project.store.directory/'captures'/(cid+'.json')).read_bytes()
            (self.root/'pkg/service.py').write_text('def changed():\n    return 4\n')
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(server,'/api/source?path='+key+'&version=working')
            self.assertEqual(e.exception.code,409)
            with self.request(server,'/api/refresh',method='POST') as r:new=json.load(r)
            self.assertNotEqual(new['capture']['capture_id'],cid);self.assertEqual((project.store.directory/'captures'/(cid+'.json')).read_bytes(),old)
            # Hide the repository: offline export may only use retained app data.
            moved=self.base/'repository-hidden';self.root.rename(moved)
            result=export_capture(project.store.directory,cid,self.base/'export',True)
            page=(self.base/'export/START_HERE.html').read_text(encoding='utf-8');self.assertNotIn(str(self.root),page);self.assertNotIn(str(project.store.directory),page);self.assertNotIn(server.token,page);self.assertIn('def run',page);self.assertEqual(result['state'],'COMPLETE')
            no_source=export_capture(project.store.directory,cid,self.base/'metadata-only')
            value=json.loads((self.base/'metadata-only/project-navigation.json').read_text(encoding='utf-8'));self.assertFalse(value['export']['source_included'])
            with self.assertRaises(FileExistsError):export_capture(project.store.directory,cid,self.base/'export',True)
        finally:
            server.shutdown();worker.join(timeout=5);server.server_close();self.assertFalse(worker.is_alive())
    def test_invalid_export_data_creates_no_directories(self):
        missing=self.base/'not-created'
        with self.assertRaises(RepositoryError):export_capture(missing,'0'*64,self.base/'export')
        self.assertFalse(missing.exists())
