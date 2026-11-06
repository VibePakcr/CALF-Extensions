"""H0 contract fixtures: no hosted networking, accounts or project execution."""
from dataclasses import FrozenInstanceError,replace
import hashlib
import json
import unittest
from unittest.mock import patch
from . import test_git_contract as gitfixtures
from . import test_navigation as navfixtures
from ..analyze import analyze_snapshot
from ..capture import Store
from ..compare import compare_pair
from ..model import RepositoryError,canonical,digest,path_record
from ..providers.base import Capabilities,ComparisonContext,Content,Entry,RepositoryIdentity,Revision,Snapshot
from ..providers.local import LocalSource


class SourceContracts(unittest.TestCase):
    setUp=gitfixtures.GitFixtures.setUp
    g=gitfixtures.GitFixtures.g
    commit=gitfixtures.GitFixtures.commit
    reader=gitfixtures.GitFixtures.reader
    fixture=navfixtures.Navigation.fixture

    def tiny(self,files,complete=True,provider='github',repo_id='42',commit='1'*40):
        identity=RepositoryIdentity(provider,'https://api.github.com' if provider=='github' else 'https://gitlab.com',repo_id,'Fixture')
        entries=[];contents={}
        for path,raw in files.items():
            key=path_record(path.encode());entries.append(Entry(**key,mode='100644'));contents[key['id']]=Content(key['id'],'READY',raw)
        return Snapshot(identity,Revision(identity.key,'commit',commit_id=commit),tuple(entries),contents,inventory_complete=complete)

    def test_content_states_and_immutability(self):
        key=path_record(b'empty.py')['id'];empty=Content(key,'READY',b'');self.assertEqual(empty.byte_sha256,hashlib.sha256(b'').hexdigest());self.assertEqual(empty.value()['text'],'')
        for state in ['ABSENT','NOT_FETCHED','UNAVAILABLE','LIMIT_EXCEEDED','IDENTITY_MISMATCH']:
            value=Content(key,state);self.assertIsNone(value.value()['text']);self.assertIsNone(value.byte_sha256)
            with self.subTest(state=state),self.assertRaises(RepositoryError):Content(key,state,b'')
        with self.assertRaises(RepositoryError):Content(key,'READY',b'x',expected_sha256='0'*64)
        with self.assertRaises(RepositoryError):Content(key,'READY',b'x'*(1024*1024+1))
        with self.assertRaises(FrozenInstanceError):empty.data=b'changed'
        snapshot=self.tiny({'empty.py':b''});original=snapshot.contents.copy()
        with self.assertRaises(TypeError):snapshot.contents[key]=Content(key,'ABSENT')
        self.assertEqual(snapshot.contents,original)
        with self.assertRaises(RepositoryError):replace(snapshot,entries=snapshot.entries*2)
        with self.assertRaises(RepositoryError):replace(snapshot,capabilities=Capabilities(working=True))

    def test_named_refs_pin_commit_and_tree_without_checkout(self):
        a=self.commit(b'A\n');r=self.reader();backend=LocalSource.from_reader(r,Store(self.base/'data',r));revision=backend.pin('branch','main')
        self.g('tag','-a','same','-m','annotated',a);self.g('branch','same',a);b=self.commit(b'B\n');self.g('branch','-f','same',b)
        before=self.g('rev-parse','HEAD');snapshot=backend.snapshot(revision)
        self.assertEqual(snapshot.revision.commit_id,a);self.assertEqual(snapshot.read_content(path_record(b'file.txt')['id']).data,b'A\n');self.assertEqual(self.g('rev-parse','HEAD'),before)
        self.assertEqual(backend.pin('branch','same').commit_id,b);self.assertEqual(backend.pin('tag','same').commit_id,a)
        self.assertEqual(backend.pin('commit',a).commit_id,a)
        with self.assertRaises(RepositoryError):backend.pin('branch','main^{tree}')
        with self.assertRaises(RepositoryError):backend.snapshot(replace(revision,tree_oid='0'*40))

    def test_independent_memory_sources_produce_same_graph(self):
        reader,store,capture,old_graph=self.fixture();backend=LocalSource.from_reader(reader,store);working=backend.analysis_snapshot(capture);pinned=backend.snapshot(backend.pin('head'))
        variants=[working,pinned]
        for provider,origin in [('github','https://api.github.com'),('gitlab','https://gitlab.com')]:
            identity=RepositoryIdentity(provider,origin,'42','repo');variants.append(Snapshot(identity,replace(pinned.revision,repository_key=identity.key),pinned.entries,pinned.contents))
        settings={'label':'Example project','features':[{'id':'calculation','label':'Calculate','definition':'Compute one result.','targets':[{'path':'pkg/service.py','symbol':'run'}]}]}
        def normalized(graph):
            alias={n['id']:('<project>' if n['kind']=='project' else n['id']) for n in graph['nodes']}
            nodes=sorted(canonical([alias[n['id']],n['kind'],n.get('path'),n.get('symbol'),n.get('description'),n.get('analysis')]) for n in graph['nodes'])
            edges=sorted(canonical([alias[e['from']],alias[e['to']],e['kind'],e['provenance'].get('path'),e['provenance'].get('start_line'),e['provenance'].get('end_line'),e['provenance'].get('sha256')]) for e in graph['edges'])
            return nodes,edges
        with patch('subprocess.Popen',side_effect=AssertionError('No process during snapshot analysis')),patch('socket.socket',side_effect=AssertionError('No HTTP transport in H0')):
            graphs=[analyze_snapshot(s,settings) for s in variants]
        for graph in graphs:
            self.assertEqual(normalized(graph),normalized(graphs[0]));self.assertEqual(len([e for e in graph['edges'] if e['kind']=='STATIC_CALL']),1)
            edge=next(e for e in graph['edges'] if e['kind']=='STATIC_CALL');self.assertEqual(edge['provenance']['start_line'],6)
            self.assertFalse(graph['coverage']['runtime_verified'])
        self.assertFalse((self.base/'must-not-execute').exists());self.assertNotEqual(variants[2].repository.key,variants[3].repository.key)

    def test_v1_load_is_read_only_and_works_without_repository(self):
        reader,store,capture,graph=self.fixture();path=store.directory/'captures'/(capture['capture_id']+'.json');before=path.read_bytes();listing={str(p):p.read_bytes() for p in store.directory.rglob('*') if p.is_file()}
        self.root.rename(self.base/'hidden');snapshot=store.load_snapshot(capture['capture_id'])
        self.assertEqual(snapshot.snapshot_id,capture['capture_id']);self.assertIn(b'def run',snapshot.read_content(path_record(b'pkg/service.py')['id']).data);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(listing,{str(p):p.read_bytes() for p in store.directory.rglob('*') if p.is_file()})
        with self.assertRaises(RepositoryError):store.save_snapshot(snapshot)
        self.assertFalse((store.directory/'captures-v2').exists())

    def test_v1_missing_retained_bytes_are_not_empty_source(self):
        self.commit(b'not retained\n');r=self.reader();store=Store(self.base/'data',r);backend=LocalSource.from_reader(r,store);capture=backend.collect_working()
        snapshot=store.load_snapshot(capture['capture_id']);content=snapshot.read_content(path_record(b'file.txt')['id'])
        self.assertEqual(content.availability,'NOT_FETCHED');self.assertIsNone(content.data);self.assertIsNotNone(content.expected_sha256)
        full_snapshot=backend.analysis_snapshot(capture);self.assertNotEqual(ComparisonContext(snapshot,snapshot).context_id,ComparisonContext(full_snapshot,full_snapshot).context_id);partial=analyze_snapshot(snapshot);full=analyze_snapshot(full_snapshot);self.assertEqual(partial['capture_id'],full['capture_id']);self.assertNotEqual(partial['input_snapshot_id'],full['input_snapshot_id']);self.assertNotEqual(partial['navigation_id'],full['navigation_id'])

    def test_v2_persistence_has_no_fictitious_local_paths(self):
        snapshot=self.tiny({'pkg/a.py':b'def a():\n    return 1\n','empty.txt':b''});store=Store(self.base/'app',create=True);identity=store.save_snapshot(snapshot);file=store.directory/'captures-v2'/(identity+'.json');raw=file.read_bytes();stamp=file.stat().st_mtime_ns
        self.assertEqual(identity,snapshot.snapshot_id);self.assertEqual(store.save_snapshot(snapshot),identity);self.assertEqual(file.stat().st_mtime_ns,stamp)
        self.assertNotIn(b'git_dir',raw);self.assertNotIn(b'worktree',raw);self.assertNotIn(b'credential',raw)
        loaded=store.load_snapshot(identity);self.assertEqual(loaded.snapshot_id,identity);self.assertEqual(loaded.read_content(path_record(b'empty.txt')['id']).data,b'');self.assertEqual(file.read_bytes(),raw)
        manifest=json.loads(raw);manifest['repository']['root']='/invented/local/path'
        with self.assertRaises(RepositoryError):Snapshot.from_manifest(manifest,store.read_source_bytes)
        manifest=json.loads(raw);manifest['files'].append(manifest['files'][0])
        with self.assertRaises(RepositoryError):Snapshot.from_manifest(manifest,store.read_source_bytes)

    def test_corrupted_v2_cache_cannot_become_valid_content(self):
        snapshot=self.tiny({'a.py':b'original\n'});store=Store(self.base/'app',create=True);identity=store.save_snapshot(snapshot);meta=(store.directory/'captures-v2'/(identity+'.json')).read_bytes();value=next(iter(snapshot.contents.values()));cache=store.directory/'sources'/value.byte_sha256;cache.chmod(0o600);cache.write_bytes(b'corrupt\n')
        with self.assertRaises(RepositoryError) as error:store.load_snapshot(identity)
        self.assertEqual(error.exception.code,'SOURCE_CACHE_CHANGED');self.assertEqual((store.directory/'captures-v2'/(identity+'.json')).read_bytes(),meta)

    def test_snapshot_pair_distinguishes_absent_unknown_and_empty(self):
        left=self.tiny({'empty.txt':b''});key=path_record(b'empty.txt')['id'];right=self.tiny({},commit='2'*40);pair=ComparisonContext(left,right);value=compare_pair(pair,key)
        self.assertEqual(value['state'],'COMPLETE');self.assertFalse(value['same_bytes']);self.assertFalse(value['newline_or_encoding_only']);self.assertEqual(value['right']['availability'],'ABSENT')
        crlf=self.tiny({'empty.txt':b'line\r\n'},commit='3'*40);lf=self.tiny({'empty.txt':b'line\n'},commit='4'*40);self.assertTrue(compare_pair(ComparisonContext(crlf,lf),key)['newline_or_encoding_only'])
        partial=self.tiny({},complete=False,commit='2'*40);value=compare_pair(ComparisonContext(left,partial),key);self.assertEqual(value['state'],'UNAVAILABLE');self.assertEqual(value['right']['availability'],'NOT_FETCHED')
        with self.assertRaises(RepositoryError):ComparisonContext(left,self.tiny({},repo_id='99'))
        with self.assertRaises(RepositoryError):ComparisonContext(left,right,basis='MERGE_BASE')
        with self.assertRaises(RepositoryError):compare_pair(pair,path_record(b'outside')['id'])

    def test_navigation_identity_is_separate_from_snapshot(self):
        snapshot=self.tiny({'a.py':b'def a():\n    return 1\n'});settings={'features':[{'id':'x','label':'X','definition':'Explicit','references':[{'path':'missing.md','start_line':1}]}]};a=analyze_snapshot(snapshot,settings);a_bytes=canonical(a);settings['features'][0]['references'][0]['path']='changed.md';b=analyze_snapshot(snapshot,settings)
        self.assertEqual(a['capture_id'],b['capture_id']);self.assertNotEqual(a['navigation_id'],b['navigation_id']);self.assertEqual(canonical(a),a_bytes);self.assertEqual(b['navigation_id'],analyze_snapshot(snapshot,settings)['navigation_id'])
        snapshot.cancel_event.set()
        with self.assertRaises(RepositoryError) as error:analyze_snapshot(snapshot)
        self.assertEqual(error.exception.code,'CANCELLED')

    def test_local_type_change_does_not_follow_link_target(self):
        import os
        secret=self.base/'secret';secret.write_text('private target')
        try:(self.root/'former.py').symlink_to(secret)
        except OSError:self.skipTest('Symlinks unavailable on this host')
        self.g('add','.');self.g('commit','-qm','link');(self.root/'former.py').unlink();(self.root/'former.py').write_bytes(b'def local():\n    return 1\n')
        r=self.reader();backend=LocalSource.from_reader(r,Store(self.base/'app',r));capture=backend.collect_working();snapshot=backend.analysis_snapshot(capture);self.assertIn(b'def local',snapshot.read_content(path_record(b'former.py')['id']).data);self.assertEqual(secret.read_text(),'private target')

    def test_unsupported_symbol_mapping_is_unresolved_without_python(self):
        snapshot=self.tiny({'only.rs':b'fn exists() {}\n'});graph=analyze_snapshot(snapshot,{'features':[{'id':'x','label':'X','definition':'Explicit','targets':[{'path':'only.rs','symbol':'exists'}]}]})
        self.assertTrue(any(x['reason']=='MAPPING_TARGET_UNRESOLVED' for x in graph['unresolved']));self.assertFalse(any(n['kind']=='symbol' for n in graph['nodes']))

    def test_invalid_absence_and_streamed_manifest_budget_are_refused(self):
        from ..model import SOURCE_LIMIT,TOTAL_SOURCE_LIMIT
        snap=self.tiny({'a.py':b''});key=path_record(b'a.py')['id']
        with self.assertRaises(RepositoryError):replace(snap,contents={key:Content(key,'ABSENT')})
        data=b'x'*SOURCE_LIMIT;manifest=self.tiny({'a.py':data}).manifest();record=manifest['files'][0];manifest['files']=[]
        for i in range(TOTAL_SOURCE_LIMIT//SOURCE_LIMIT+1):
            item=dict(record,**path_record(('file'+str(i)).encode()));manifest['files'].append(item)
        calls=[]
        def load(key):calls.append(key);return data
        with self.assertRaises(RepositoryError):Snapshot.from_manifest(manifest,load)
        self.assertEqual(len(calls),TOTAL_SOURCE_LIMIT//SOURCE_LIMIT)
        store=Store(self.base/'missing-cache',create=True);sid=store.save_snapshot(snap);cache=store.directory/'sources'/digest(b'');cache.chmod(0o600);cache.unlink()
        with self.assertRaises(RepositoryError) as error:store.load_snapshot(sid)
        self.assertEqual(error.exception.code,'SOURCE_CACHE_MISSING')
