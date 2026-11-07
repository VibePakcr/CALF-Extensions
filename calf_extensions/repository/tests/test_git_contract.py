import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from calf_extensions.repository.git_reader import GitReader
from calf_extensions.repository.model import RepositoryError, git_blob_oid, path_bytes, path_record

class GitFixtures(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'repo';self.root.mkdir()
        self.git=str(Path(shutil.which('git')).resolve());self.env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_AUTHOR_NAME='Fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',GIT_COMMITTER_NAME='Fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid')
        self.g('init','-q','-b','main')
    def g(self,*args,cwd=None):
        return subprocess.check_output([self.git,'-c','commit.gpgsign=false','-c','core.hooksPath='+os.devnull,*args],cwd=cwd or self.root,env=self.env,stderr=subprocess.PIPE)
    def commit(self,content=b'alpha\n',name='file.txt'):
        (self.root/name).write_bytes(content);self.g('add','--',name);self.g('commit','-qm','fixture');return self.g('rev-parse','HEAD').strip().decode()
    def reader(self,root=None):
        reader=GitReader(root or self.root,self.git);reader.discover();return reader
    def test_unborn_normal_detached_and_worktree(self):
        r=self.reader();self.assertEqual(r.info['state'],'unborn');self.assertIsNone(r.info['head'])
        commit=self.commit();r=self.reader();self.assertEqual(r.info['head'],commit);self.assertEqual(r.info['branch'],'main')
        other=self.base/'other';self.g('worktree','add','-q','-b','topic',str(other));a=self.reader(other)
        self.assertTrue(a.info['linked_worktree']);self.assertEqual(a.info['common_dir'],r.info['common_dir']);self.assertNotEqual(a.info['git_dir'],r.info['git_dir'])
        self.g('checkout','--detach','-q');self.assertEqual(self.reader().info['state'],'detached')
    def test_bare_and_promisor_are_refused_before_object_reads(self):
        bare=self.base/'bare';self.g('init','-q','--bare',str(bare))
        with self.assertRaises(RepositoryError) as c:self.reader(bare)
        self.assertEqual(c.exception.code,'BARE_UNSUPPORTED')
        self.commit();self.g('config','remote.origin.url','https://example.invalid/forbidden');self.g('config','remote.origin.promisor','true')
        with self.assertRaises(RepositoryError) as c:self.reader()
        self.assertEqual(c.exception.code,'PARTIAL_CLONE_UNSUPPORTED')
    def test_shallow_boundary(self):
        first=self.commit();self.commit(b'second\n');(self.root/'.git/shallow').write_text(self.g('rev-parse','HEAD').decode())
        r=self.reader();self.assertTrue(r.info['shallow']);history,more=r.history(r.info['head']);self.assertEqual(len(history),1);self.assertFalse(more)
    def test_byte_paths_and_object_formats(self):
        names=['한글 space.txt','-option.txt']+([] if os.name=='nt' else ['tab\tname.txt','line\nname.txt'])
        for name in names:(self.root/name).write_bytes(b'exact\r\n')
        self.g('add','--',*names);self.g('commit','-qm','paths');r=self.reader()
        self.assertEqual({path_bytes(x['id']) for x in r.stages()},{os.fsencode(n) for n in names})
        for x in r.tree(r.info['head']):
            data,size=r.blob(x['oid']);self.assertEqual(data,b'exact\r\n');self.assertEqual(git_blob_oid(data,r.info['object_format']),x['oid'])
        other=self.base/'sha256';other.mkdir();self.g('init','-q','--object-format=sha256','-b','main',cwd=other)
        (other/'a').write_bytes(b'256\n');self.g('add','a',cwd=other);self.g('commit','-qm','256',cwd=other)
        q=self.reader(other);self.assertEqual(q.info['object_format'],'sha256');self.assertEqual(len(q.info['head']),64)
    def test_read_only_and_no_repository_programs(self):
        first=self.commit();self.commit(b'next\n')
        sentinel=self.base/'executed';script=self.base/'sentinel.py';script.write_text('from pathlib import Path\nPath('+repr(str(sentinel))+').write_text("called")\n')
        command='"'+sys.executable+'" "'+str(script)+'"'
        for key in ['core.fsmonitor','diff.external','diff.evil.textconv','filter.evil.clean','filter.evil.process','credential.helper']:self.g('config',key,command)
        (self.root/'.gitattributes').write_text('*.txt filter=evil diff=evil\n')
        hooks=self.root/'.git/hooks';hook=hooks/'post-checkout';hook.write_text('#!/bin/sh\n'+command+'\n');hook.chmod(0o755)
        paths=[self.root/'.git/index',self.root/'.git/config',self.root/'.git/HEAD',self.root/'file.txt',self.root/'.gitattributes',hook]
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        r=self.reader();r.stages();r.tree(first);r.refs();r.history(r.info['head']);r.changed(r.info['head'],first)
        self.assertFalse(sentinel.exists());self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        with self.assertRaises(RepositoryError):r._read(['status','--porcelain'])
        with self.assertRaises(RepositoryError):r._read(['config','core.bare','true'])
    def test_history_pagination_and_rename(self):
        first=self.commit();self.g('mv','file.txt','renamed.txt');self.g('commit','-qm','renamed');r=self.reader()
        page,more=r.history(r.info['head'],limit=1);self.assertTrue(more);self.assertEqual(page[0]['parents'],[first])
        page2,more=r.history(r.info['head'],offset=1,limit=1);self.assertFalse(more);self.assertEqual(page2[0]['id'],first)
        changes=r.changed(r.info['head'],first);self.assertEqual(changes[0]['status'],'R100');self.assertEqual(changes[0]['old']['path'],'file.txt');self.assertEqual(changes[0]['new']['path'],'renamed.txt')
    def test_missing_objects_remain_missing(self):
        self.commit();r=self.reader();entry=r.tree(r.info['head'])[0];blob=entry['oid']
        object_path=self.root/'.git/objects'/blob[:2]/blob[2:]
        # Git for Windows marks loose objects read-only. This is our disposable fixture.
        if os.name=='nt':object_path.chmod(0o600)
        object_path.unlink()
        self.assertFalse(object_path.exists())
        with self.assertRaises(RepositoryError):r.blob(blob)
    def test_raw_path_identity_refuses_traversal(self):
        for raw in [b'../x',b'/x',b'a//b',b'.',b'a/../b']:
            with self.assertRaises(RepositoryError):path_record(raw)
        raw=b'x/\xff';self.assertEqual(path_bytes(path_record(raw)['id']),raw)

if __name__=='__main__':unittest.main()
