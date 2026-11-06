"""H2 GitHub-shaped responses derived independently from disposable real Git objects."""
import base64
from dataclasses import replace
import json
import os
import subprocess
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.parse import unquote,urlsplit
from . import test_git_contract as gitfixtures
from . import test_navigation as navfixtures
from . import test_hosted_h1 as httpfixtures
from ..analyze import analyze_snapshot
from ..capture import Store
from ..compare import compare_pair
from ..http_reader import Budget,HTTPError,HTTPReader,RequestSpec
from ..model import RepositoryError,canonical,digest,path_bytes,path_record
from ..providers.base import ComparisonContext
from ..providers.github import GitHubSource,tree_rows
from ..providers.local import LocalSource
from ..registrations import Registry


class GitHub(unittest.TestCase):
    setUp=gitfixtures.GitFixtures.setUp
    g=gitfixtures.GitFixtures.g
    commit=gitfixtures.GitFixtures.commit
    reader=gitfixtures.GitFixtures.reader
    fixture=navfixtures.Navigation.fixture
    def source(self,modify=None,*,budget=None):
        registry=Registry(self.base/'registry');reg=registry.add('github','https://github.com/fixture/repo');reg=registry.bind(reg.id,reg.version,{'id':42,'full_name':'fixture/repo'})
        fixture=self;calls=[]
        class Reader:
            registration=reg
            def request(self,spec,cancel,budget):
                budget.take(cancel);calls.append(spec);value=fixture.response(spec)
                if modify:value=modify(spec,value)
                class Response:
                    body=canonical(value)
                    def json(self):return value
                return Response()
            def close(self):pass
        result=GitHubSource(reg,Reader(),budget=budget);result.calls=calls;return result
    def response(self,spec):
        if spec.operation=='identity':return {'id':42,'full_name':'fixture/repo'}
        if spec.operation=='branch':return {'name':spec.selector,'commit':{'sha':self.g('rev-parse','refs/heads/'+spec.selector).strip().decode()}}
        if spec.operation=='tag':
            value=self.g('rev-parse','refs/tags/'+spec.selector).strip().decode();return {'ref':'refs/tags/'+spec.selector,'object':{'type':self.g('cat-file','-t',value).strip().decode(),'sha':value}}
        if spec.operation=='tag_object':
            data=self.g('cat-file','-p',spec.selector).splitlines();return {'sha':spec.selector,'object':{'sha':data[0].split()[1].decode(),'type':data[1].split()[1].decode()}}
        if spec.operation=='commit':
            data=self.g('cat-file','-p',spec.selector).split(b'\n\n',1)[0].splitlines();return {'sha':spec.selector,'tree':{'sha':data[0].split()[1].decode()},'parents':[{'sha':row.split()[1].decode()} for row in data if row.startswith(b'parent ')]}
        if spec.operation=='tree':
            args=['ls-tree','-z','-l']+(['-r','-t'] if spec.recursive else [])+[spec.selector];rows=[]
            for record in self.g(*args).split(b'\0'):
                if not record:continue
                info,path=record.split(b'\t',1);mode,kind,identity,size=info.split();row={'path':path.decode('utf-8'),'mode':mode.decode(),'type':kind.decode(),'sha':identity.decode()}
                if size!=b'-':row['size']=int(size)
                rows.append(row)
            return {'sha':spec.selector,'tree':rows,'truncated':False}
        if spec.operation=='blob':
            raw=self.g('cat-file','blob',spec.selector);return {'sha':spec.selector,'size':len(raw),'encoding':'base64','content':base64.encodebytes(raw).decode()}
        raise AssertionError(spec)
    def error(self,code,call):
        with self.assertRaises(RepositoryError) as caught:call()
        self.assertEqual(caught.exception.code,code)
    def test_pin_branch_and_annotated_tag_collision_and_move(self):
        a=self.commit(b'A\n');self.g('tag','-a','same','-m','tag',a);self.g('branch','same',a);b=self.commit(b'B\n');self.g('branch','-f','same',b)
        source=self.source();branch=source.pin('branch','same');tag=source.pin('tag','same');self.assertEqual(branch.commit_id,b);self.assertEqual(tag.commit_id,a)
        self.commit(b'C\n');snapshot=source.snapshot(branch);self.assertEqual(snapshot.read_content(path_record(b'file.txt')['id']).data,b'B\n');self.assertEqual(snapshot.revision.commit_id,b)
        self.assertTrue(any(s.operation=='tag_object' for s in source.calls));self.assertEqual(source.pin('commit',a).commit_id,a)
    def test_slash_ref_and_invalid_refs_do_not_enumerate(self):
        self.commit();self.g('branch','feature/slash');s=self.source();self.assertEqual(s.pin('branch','feature/slash').ref_name,'feature/slash')
        for kind,name in [('branch','x..y'),('branch','x@{y'),('branch','/x'),('tag','x.lock'),('head','main'),('commit','1'*64)]:
            count=len(s.calls)
            with self.assertRaises(RepositoryError):s.pin(kind,name)
            self.assertEqual(len(s.calls),count)
    def test_exact_bytes_paths_modes_and_content_boundaries(self):
        names={'empty.txt':b'','bom.txt':b'\xef\xbb\xbfhello\r\n','binary':b'\x00\xff','non-utf8':b'\xff\xfe','ptr':b'version https://git-lfs.github.com/spec/v1\noid sha256:'+b'1'*64+b'\nsize 123\n','한글 +%#.txt':b'exact\r\n','e\u0301.txt':b'decomposed','é.txt':b'composed','tab\tline\n.txt':b'line'}
        (self.root/'dir').mkdir();(self.root/'dir/child').write_bytes(b'child');self.g('add','.')
        # Insert exact Git path bytes without APFS normalizing composed/decomposed names.
        self.g('config','core.precomposeunicode','false')
        control_rows=[]
        for i,(n,data) in enumerate(names.items()):
            payload=self.base/('blob-'+str(i));payload.write_bytes(data);blob=self.g('hash-object','-w',str(payload)).strip().decode()
            if any(ord(c)<32 for c in n):control_rows.append(b'100644 blob '+blob.encode()+b'\t'+n.encode()+b'\0')
            else:self.g('update-index','--add','--cacheinfo',('100755,' if n=='ptr' else '100644,')+blob+','+n)
        target=self.base/'link-target';target.write_bytes(b'../outside-private-target');self.g('update-index','--add','--cacheinfo','120000,'+self.g('hash-object','-w',str(target)).strip().decode()+',link')
        self.g('update-index','--add','--cacheinfo','160000,'+('1'*40)+',submodule');self.g('commit','-qm','bytes')
        # Native Windows index protection rejects control-byte names. Store the same
        # raw Git path in a tree object; no checkout or weaker index policy is needed.
        if control_rows:
            raw=self.g('ls-tree','-z','HEAD^{tree}')+b''.join(control_rows)
            tree=subprocess.check_output([self.git,'-c','core.hooksPath='+os.devnull,'mktree','-z'],input=raw,cwd=self.root,env=self.env,stderr=subprocess.PIPE).strip().decode()
            commit=self.g('commit-tree',tree,'-p','HEAD','-m','raw path fixture').strip().decode();self.g('update-ref','refs/heads/main',commit)
        s=self.source();snap=s.snapshot(s.pin('branch','main'))
        for n,data in names.items():self.assertEqual(snap.read_content(path_record(n.encode())['id']).data,data)
        self.assertEqual(snap.read_content(path_record(b'empty.txt')['id']).byte_sha256,digest(b''));self.assertTrue(snap.inventory_complete)
        for name,kind in [('link','symlink'),('submodule','submodule')]:self.assertEqual(snap.read_content(path_record(name.encode())['id']).value()['kind'],kind)
        self.assertEqual(snap.read_content(path_record(b'ptr')['id']).value()['kind'],'lfs_pointer');self.assertFalse(snap.capabilities.working)
        link=next(x.blob_oid for x in snap.entries if x.path=='link');self.assertFalse(any(c.operation=='blob' and c.selector==link for c in s.calls))
    def test_truncated_recursive_tree_uses_verified_subtrees(self):
        self.fixture()
        def modify(spec,value):
            if spec.operation=='tree' and spec.recursive:return dict(value,truncated=True,tree=value['tree'][:1])
            return value
        s=self.source(modify);snap=s.snapshot(s.pin('branch','main'));self.assertTrue(snap.inventory_complete);self.assertEqual(s.report['tree_strategy'],'SUBTREE_FALLBACK');self.assertEqual(len(snap.entries),6);self.assertTrue(any(c.operation=='tree' and not c.recursive for c in s.calls))
    def test_nonrecursive_truncation_and_request_limit_cannot_prove_absence(self):
        self.fixture()
        def modify(spec,value):return dict(value,truncated=True) if spec.operation=='tree' else value
        s=self.source(modify);snap=s.snapshot(s.pin('branch','main'));self.assertFalse(snap.inventory_complete);self.assertEqual(snap.read_content(path_record(b'unknown')['id']).availability,'NOT_FETCHED')
        s=self.source(budget=Budget(limit=4));snap=s.snapshot(s.pin('branch','main'));self.assertFalse(snap.inventory_complete);self.assertIn('REQUEST_LIMIT',s.report['reasons']);self.assertEqual(snap.entries,())
    def test_bad_tree_identity_paths_and_missing_metadata_fail(self):
        self.commit()
        def wrong_hash(spec,value):
            if spec.operation=='tree':value['tree'][0]['sha']='0'*40
            return value
        s=self.source(wrong_hash);self.error('TREE_IDENTITY_MISMATCH',lambda:s.snapshot(s.pin('branch','main')))
        for path in ['../escape','replacement\ufffdname']:
            def modify(spec,value):
                if spec.operation=='tree':value['tree'][0]['path']=path
                return value
            s=self.source(modify);self.error('PATH_UNREPRESENTABLE',lambda:s.snapshot(s.pin('branch','main')))
        def no_flag(spec,value):
            if spec.operation=='tree':value.pop('truncated')
            return value
        s=self.source(no_flag);self.error('GITHUB_RESPONSE_INVALID',lambda:s.snapshot(s.pin('branch','main')))
    def test_blob_mismatch_invalid_base64_size_and_empty_are_distinct(self):
        self.commit()
        for field,value,code in [('sha','0'*40,'BLOB_IDENTITY_MISMATCH'),('content','@@@','BLOB_ENCODING_INVALID'),('content',base64.b64encode(b'wrong\n').decode(),'BLOB_IDENTITY_MISMATCH'),('size',0,'BLOB_SIZE_MISMATCH')]:
            def modify(spec,data):return dict(data,**{field:value}) if spec.operation=='blob' else data
            s=self.source(modify);self.error(code,lambda:s.snapshot(s.pin('branch','main')))
    def test_tag_loop_noncommit_target_and_identity_mismatch(self):
        self.commit();self.g('tag','-a','tag','-m','tag');tag=self.g('rev-parse','tag').strip().decode()
        def loop(spec,value):return dict(value,object={'type':'tag','sha':tag}) if spec.operation=='tag_object' else value
        s=self.source(loop);self.error('TAG_TARGET_UNSUPPORTED',lambda:s.pin('tag','tag'))
        def other(spec,value):return dict(value,id=99) if spec.operation=='identity' else value
        s=self.source(other);self.error('IDENTITY_MISMATCH',lambda:s.pin('branch','main'))
    def test_source_revision_and_repo_identity_are_bound(self):
        self.commit();s=self.source();revision=s.pin('branch','main')
        self.error('SOURCE_MISMATCH',lambda:s.snapshot(replace(revision,repository_key='0'*64)))
        self.error('REVISION_MISMATCH',lambda:s.snapshot(replace(revision,tree_oid='0'*40)))
        def stale(spec,value):return dict(value,full_name='other/repo') if spec.operation=='identity' else value
        s=self.source(stale);self.error('REGISTRATION_STALE',lambda:s.pin('branch','main'))
    def test_selective_source_is_not_empty_and_roundtrips_v2(self):
        self.fixture();s=self.source();revision=s.pin('branch','main');selected={path_record(b'pkg/service.py')['id']};snap=s.snapshot(revision,path_ids=selected)
        self.assertTrue(snap.inventory_complete);self.assertEqual(sum(c.availability=='READY' for c in snap.contents.values()),1);self.assertEqual(snap.read_content(path_record(b'README.md')['id']).availability,'NOT_FETCHED')
        store=Store(self.base/'retained',create=True);identity=store.save_snapshot(snap);restored=store.load_snapshot(identity);self.assertEqual(snap.manifest(),restored.manifest());self.assertNotIn('credential',canonical(snap.manifest()).decode())
    def test_file_total_limits_and_request_exhaustion_are_explicit(self):
        self.commit(b'x'*(1024*1024+1));s=self.source();snap=s.snapshot(s.pin('branch','main'));self.assertEqual(snap.entries[0].path,'file.txt');self.assertEqual(next(iter(snap.contents.values())).availability,'LIMIT_EXCEEDED');self.assertFalse(any(c.operation=='blob' for c in s.calls))
        # An aggregate limit must count per-path materialization, even for shared blobs.
        self.commit(b'x'*16);(self.root/'alias').write_bytes(b'x'*16);self.g('add','.');self.g('commit','-qm','two paths');s=self.source()
        with patch('calf_extensions.repository.providers.github.TOTAL_SOURCE_LIMIT',20):snap=s.snapshot(s.pin('branch','main'))
        self.assertEqual(sum(c.availability=='READY' for c in snap.contents.values()),1);self.assertEqual(sum(c.reason=='TOTAL_SOURCE_LIMIT' for c in snap.contents.values()),1)
    def test_flat_tree_over_one_thousand_files_uses_no_contents_listing(self):
        payload=self.base/'payload';payload.write_bytes(b'shared');blob=self.g('hash-object','-w',str(payload)).strip().decode()
        data=b''.join(('100644 '+blob+'\tfile-'+str(i).zfill(4)+'\n').encode() for i in range(1005))
        subprocess.run([self.git,'update-index','--index-info'],input=data,cwd=self.root,env=self.env,check=True,capture_output=True)
        self.g('commit','-qm','large flat tree');s=self.source();snap=s.snapshot(s.pin('branch','main'))
        self.assertTrue(snap.inventory_complete);self.assertEqual(len(snap.entries),1005);self.assertEqual(sum(c.operation=='blob' for c in s.calls),1)
    def test_blob_budget_gap_does_not_become_empty_source(self):
        self.commit();s=self.source(budget=Budget(limit=5));snap=s.snapshot(s.pin('branch','main'))
        self.assertTrue(snap.inventory_complete);self.assertEqual(next(iter(snap.contents.values())).availability,'NOT_FETCHED');self.assertIn('REQUEST_LIMIT',s.report['reasons'])
    def test_cancel_during_final_blob_prevents_snapshot_return(self):
        self.commit()
        def modify(spec,value):
            if spec.operation=='blob':s.cancel_event.set()
            return value
        s=self.source(modify);revision=s.pin('branch','main');self.error('CANCELLED',lambda:s.snapshot(revision))
    def test_snapshot_deduplicates_shared_blob_reads(self):
        self.commit(b'same');(self.root/'another').write_bytes(b'same');self.g('add','.');self.g('commit','-qm','alias');s=self.source();snap=s.snapshot(s.pin('branch','main'));self.assertEqual(sum(c.operation=='blob' for c in s.calls),1);self.assertEqual(len(snap.contents),2)
    def test_cancelled_collection_returns_no_snapshot(self):
        self.commit();s=self.source();revision=s.pin('branch','main');s.cancel_event.set();self.error('CANCELLED',lambda:s.snapshot(revision))
    def test_grouped_import_and_same_line_calls_have_valid_distinct_evidence(self):
        (self.root/'helper.py').write_text('def left(x):\n    return x\ndef right(x):\n    return x\n')
        (self.root/'caller.py').write_text('from helper import left, right\ndef run():\n    return left(1) + left(2)\n')
        self.g('add','.');self.g('commit','-qm','grouped imports');s=self.source();graph=analyze_snapshot(s.snapshot(s.pin('branch','main')))
        self.assertEqual(len(graph['edges']),len({e['id'] for e in graph['edges']}));self.assertEqual(sum(e['kind']=='IMPORTS' for e in graph['edges']),1)
        calls=[e for e in graph['edges'] if e['kind']=='STATIC_CALL'];self.assertEqual(len(calls),2);self.assertEqual(len({e['provenance']['start_column'] for e in calls}),2)
        self.assertEqual(graph['coverage']['analyzers'],['python-ast-v3'])
    def test_local_and_github_graph_diff_equivalence_without_project_execution(self):
        self.fixture();s=self.source();revision=s.pin('branch','main');left=s.snapshot(revision);local=LocalSource.from_reader(self.reader(),Store(self.base/'local',self.reader()));pinned=local.snapshot(local.pin('commit',revision.commit_id))
        settings={'label':'Fixture','features':[{'id':'run','label':'Run','definition':'Do work','targets':[{'path':'pkg/service.py','symbol':'run'}]}]}
        def normalize(graph):
            alias={n['id']:('<root>' if n['kind']=='project' else n['id']) for n in graph['nodes']}
            return sorted(canonical([alias[n['id']],n['kind'],n.get('description'),n.get('path'),n.get('symbol')]) for n in graph['nodes']),sorted(canonical([alias[e['from']],alias[e['to']],e['kind'],e['provenance'].get('start_line'),e['provenance'].get('sha256')]) for e in graph['edges'])
        with patch('subprocess.Popen',side_effect=AssertionError('No process in common analyzer')):self.assertEqual(normalize(analyze_snapshot(left,settings)),normalize(analyze_snapshot(pinned,settings)))
        (self.root/'pkg/service.py').write_text('def run():\n    return 99\n');self.g('add','.');self.g('commit','-qm','next');s2=self.source();right=s2.snapshot(s2.pin('branch','main'));comparison=compare_pair(ComparisonContext(left,right),path_record(b'pkg/service.py')['id']);self.assertEqual(comparison['state'],'COMPLETE');self.assertFalse(comparison['same_bytes']);self.assertFalse((self.base/'must-not-execute').exists())


class HTTPGitHub(unittest.TestCase):
    setUp=httpfixtures.H1.setUp
    stop_http=httpfixtures.H1.stop_http
    transport=httpfixtures.H1.transport
    def test_pinned_annotated_tag_endpoint_uses_owned_transport(self):
        reg=self.registry.add('github','https://github.com/owner/repo');reg=self.registry.bind(reg.id,reg.version,{'id':42,'full_name':'owner/repo'})
        self.http.behavior=lambda request:(200,{}, {'sha':'a'*40,'object':{'type':'commit','sha':'b'*40}})
        reader=HTTPReader(reg,self.transport())
        try:value=reader.request(RequestSpec('tag_object','a'*40)).json();self.assertEqual(value['object']['sha'],'b'*40);self.assertEqual(self.http.seen[0]['path'],'/repos/owner/repo/git/tags/'+('a'*40));self.assertTrue(reader.transport.last_cleanup['stopped'])
        finally:reader.close()
