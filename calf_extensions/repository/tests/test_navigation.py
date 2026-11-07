import ast
from pathlib import Path
import unittest
from . import test_git_contract as fixtures
from calf_extensions.repository.analyze import analyze
from calf_extensions.repository.capture import Store,scan
from calf_extensions.repository.compare import source,compare
from calf_extensions.repository.model import path_record,RepositoryError

class Navigation(unittest.TestCase):
    setUp=fixtures.GitFixtures.setUp
    g=fixtures.GitFixtures.g
    commit=fixtures.GitFixtures.commit
    reader=fixtures.GitFixtures.reader
    def fixture(self):
        (self.root/'pkg').mkdir()
        (self.root/'pkg/__init__.py').write_text('')
        (self.root/'pkg/helper.py').write_text('"""Helper definitions."""\ndef calculate(x):\n    """Calculate a result."""\n    return x + 1\n')
        (self.root/'pkg/service.py').write_text('"""Orchestration."""\nfrom .helper import calculate\n\ndef run():\n    """Run calculation."""\n    return calculate(2)\n\ndef ambiguous(calculate):\n    return calculate(4)\n')
        (self.root/'README.md').write_text('# Fixture\n[Service](pkg/service.py)\n')
        (self.root/'other.rs').write_text('fn unparsed() {}\n')
        (self.root/'side_effect.py').write_text('from pathlib import Path\nPath('+repr(str(self.base/'must-not-execute'))+').write_text("forbidden")\n')
        self.g('add','.');self.g('commit','-qm','project')
        reader=self.reader();store=Store(self.base/'data',reader);capture=scan(reader,store)
        settings={'label':'Example project','features':[{'id':'calculation','label':'Calculate','definition':'Compute one result.','references':[{'path':'README.md','start_line':1,'end_line':2}],'targets':[{'path':'pkg/service.py','symbol':'run'}]}], 'terms':[{'id':'result','label':'Result','definition':'A computed number.'}]}
        return reader,store,capture,analyze(reader,store,capture,settings)
    def test_project_map_provenance_and_ambiguity(self):
        r,store,capture,graph=self.fixture();self.assertFalse((self.base/'must-not-execute').exists());nodes={n['id']:n for n in graph['nodes']}
        self.assertEqual(len(nodes),len(graph['nodes']));self.assertTrue(any(n['kind']=='feature' for n in nodes.values()));self.assertTrue(any(n['kind']=='term' for n in nodes.values()))
        caller=next(n for n in nodes.values() if n.get('symbol')=='run');callee=next(n for n in nodes.values() if n.get('symbol')=='calculate')
        calls=[e for e in graph['edges'] if e['kind']=='STATIC_CALL'];self.assertEqual(len(calls),1);self.assertEqual((calls[0]['from'],calls[0]['to']),(caller['id'],callee['id']));self.assertEqual(calls[0]['provenance']['start_line'],6)
        self.assertEqual(caller['description'],'Run calculation.');self.assertTrue(any(x.get('line')==9 for x in graph['unresolved']))
        self.assertTrue(any(e['kind']=='DOCUMENTS' and e['label']=='Service' for e in graph['edges']));self.assertFalse(graph['coverage']['runtime_verified'])
        rust=next(n for n in nodes.values() if n.get('path')=='other.rs');self.assertEqual(rust['analysis'],'UNSUPPORTED_LANGUAGE')
        for edge in graph['edges']:self.assertIn(edge['from'],nodes);self.assertIn(edge['to'],nodes)
    def test_three_versions_diff_and_stale_source(self):
        self.commit(b'HEAD\n');self.commit(b'HEAD\n',name='other')
        (self.root/'file.txt').write_bytes(b'INDEX\r\n');self.g('add','file.txt');(self.root/'file.txt').write_bytes(b'WORKING\n')
        r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store);key=path_record(b'file.txt')['id']
        a=source(r,store,capture,key,'head');b=source(r,store,capture,key,'index');c=source(r,store,capture,key,'working')
        self.assertEqual((a['text'],b['text'],c['text']),('HEAD\n','INDEX\r\n','WORKING\n'));self.assertEqual(compare(a,b)['lines'][-1],'+INDEX')
        self.assertNotEqual(a['sha256'],b['sha256']);self.assertNotEqual(b['sha256'],c['sha256']);self.assertEqual(store.load(capture['capture_id'])['capture_id'],capture['capture_id'])
        (self.root/'file.txt').write_bytes(b'later\n')
        with self.assertRaises(RepositoryError) as error:source(r,store,capture,key,'working')
        self.assertEqual(error.exception.code,'SOURCE_CHANGED')
    def test_output_must_stay_outside_repository(self):
        self.commit();r=self.reader()
        with self.assertRaises(RepositoryError):Store(self.root/'output',r)
        self.assertFalse((self.root/'output').exists())
    def test_working_symlink_never_read(self):
        import os
        (self.base/'secret').write_text('outside')
        try:(self.root/'link').symlink_to(self.base/'secret')
        except OSError as error:self.skipTest('Symlinks unavailable: '+str(error.winerror if os.name=='nt' else error.errno))
        self.g('add','link');self.g('commit','-qm','link')
        r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store)
        value=source(r,store,capture,path_record(b'link')['id'],'working');self.assertEqual(value['kind'],'symlink');self.assertIsNone(value['text'])

    def test_conditional_rebinding_is_not_a_static_call(self):
        (self.root/'x.py').write_text('def target():\n    return 1\n\nif True:\n    target = lambda: 2\n\ndef caller():\n    return target()\n')
        self.g('add','.');self.g('commit','-qm','rebound');r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store);graph=analyze(r,store,capture)
        self.assertFalse(any(e['kind']=='STATIC_CALL' for e in graph['edges']))
        self.assertTrue(any(x.get('line')==8 for x in graph['unresolved']))
    def test_project_map_rejects_malformed_and_duplicate_definitions(self):
        from calf_extensions.repository.model import validate_settings
        for value in [{'label':1},{'features':[{'id':'x','label':'X','definition':'X'},{'id':'x','label':'Y','definition':'Y'}]}, {'terms':[{'id':'t','label':'T','definition':'T','targets':[{'path':'../escape'}]}]}]:
            with self.subTest(value=value),self.assertRaises(RepositoryError):validate_settings(value)

    def test_common_repository_registration_separates_worktrees(self):
        self.commit();other=self.base/'other';self.g('worktree','add','-q','-b','topic',str(other))
        first=self.reader();second=self.reader(other)
        store1=Store(self.base/'data',first);store2=Store(self.base/'data',second)
        a=scan(first,store1);b=scan(second,store2)
        self.assertEqual(a['repository']['repository_id'],b['repository']['repository_id'])
        self.assertNotEqual(a['worktree']['worktree_id'],b['worktree']['worktree_id'])

    def test_nested_definitions_and_missing_mapping_evidence(self):
        (self.root/'x.py').write_text('"""A module."""\nclass Outer:\n    """An owner."""\n    def method(self):\n        """A method."""\n        def nested():\n            """Nested help."""\n            return 1\n        return nested()\n')
        self.g('add','.');self.g('commit','-qm','nested');r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store)
        graph=analyze(r,store,capture,{'features':[{'id':'feature','label':'Feature','definition':'Explicit definition.','references':[{'path':'missing.md','start_line':1}]}]})
        nested=next(n for n in graph['nodes'] if n.get('symbol')=='Outer.method.nested')
        self.assertEqual(nested['description'],'Nested help.');self.assertEqual((nested['provenance']['start_line'],nested['provenance']['end_line']),(6,8))
        self.assertTrue(any(x['reason']=='MAPPING_REFERENCE_UNRESOLVED' for x in graph['unresolved']))
    def test_conflict_stages_are_not_a_deleted_index_file(self):
        import subprocess
        self.commit(b'base\n');self.g('checkout','-qb','other');self.commit(b'theirs\n');self.g('checkout','-q','main');self.commit(b'ours\n')
        with self.assertRaises(subprocess.CalledProcessError):self.g('merge','--no-edit','other')
        r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store);key=path_record(b'file.txt')['id']
        self.assertEqual(source(r,store,capture,key,'index')['kind'],'conflict')
        self.assertEqual(source(r,store,capture,key,'stage1')['text'],'base\n')
        self.assertEqual(source(r,store,capture,key,'stage2')['text'],'ours\n')
        self.assertEqual(source(r,store,capture,key,'stage3')['text'],'theirs\n')

    def test_deleted_working_file_cannot_be_used_as_a_fresh_capture(self):
        self.commit(b'existing\n');r=self.reader();store=Store(self.base/'data',r);capture=scan(r,store);(self.root/'file.txt').unlink()
        with self.assertRaises(RepositoryError) as error:source(r,store,capture,path_record(b'file.txt')['id'],'working')
        self.assertEqual(error.exception.code,'SOURCE_CHANGED')
    def test_changed_during_analysis_does_not_replace_the_map(self):
        from unittest.mock import patch
        from calf_extensions.repository.viewer import Project
        from calf_extensions.repository import analyze as module
        (self.root/'x.py').write_text('def original():\n    return 1\n');self.g('add','.');self.g('commit','-qm','original')
        project=Project(self.root,self.base/'app',self.git);old=project.refresh();original=module.source
        def changed(*args,**kwargs):
            (self.root/'x.py').write_text('def changed():\n    return 2\n')
            return original(*args,**kwargs)
        with patch.object(module,'source',side_effect=changed),self.assertRaises(RepositoryError) as error:project.refresh()
        self.assertEqual(error.exception.code,'SOURCE_CHANGED');self.assertEqual(project.graph['capture_id'],old['capture_id'])
