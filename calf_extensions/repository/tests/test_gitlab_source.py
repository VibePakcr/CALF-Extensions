"""H3 Git-backed API fixtures and actual owned HTTP raw-byte/cancellation checks."""
from dataclasses import replace
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from . import test_git_contract as gitfixtures
from . import test_navigation as navfixtures
from . import test_github_source as ghfixtures
from . import test_hosted_h1 as httpfixtures
from ..analyze import analyze_snapshot
from ..capture import Store
from ..http_reader import Budget,HTTPError,HTTPReader,RequestSpec
from ..model import RepositoryError,canonical,digest,git_blob_oid,path_record
from ..providers.gitlab import GitLabSource
from ..providers.local import LocalSource
from ..registrations import Registry


class GitLab(unittest.TestCase):
    setUp=gitfixtures.GitFixtures.setUp
    g=gitfixtures.GitFixtures.g
    commit=gitfixtures.GitFixtures.commit
    reader=gitfixtures.GitFixtures.reader
    fixture=navfixtures.Navigation.fixture
    error=ghfixtures.GitHub.error
    def source(self,modify=None,*,budget=None,page_size=100):
        registry=Registry(self.base/'registry');reg=registry.add('gitlab','https://gitlab.com/group/sub/repo');reg=registry.bind(reg.id,reg.version,{'id':17,'path_with_namespace':'group/sub/repo'})
        fixture=self;calls=[];urls=[]
        class Transport:
            def send(self,payload,cancel,deadline):
                spec=RequestSpec(**payload['spec']);calls.append(spec);urls.append(payload['url']);page=int(parse_qs(urlsplit(payload['url']).query).get('page_token',['1'])[0]);headers={'content-type':'application/json'}
                value=fixture.response(spec);status=200
                if spec.operation=='tree':
                    total=len(value);value=value[(page-1)*page_size:page*page_size]
                    if page*page_size<total:headers['link']='<'+spec.url(reg)+'&page_token='+str(page+1)+'>; rel="next"'
                if modify:status,headers,value=modify(spec,status,headers,value)
                body=value if isinstance(value,bytes) else canonical(value)
                if len(body)>payload['limit']:raise HTTPError('HTTP_RESPONSE_LIMIT')
                return status,headers,body
        reader=HTTPReader(reg,Transport());self.addCleanup(reader.close);source=GitLabSource(reg,reader,budget=budget);source.calls=calls;source.urls=urls;return source
    def response(self,spec):
        if spec.operation=='identity':return {'id':17,'path_with_namespace':'group/sub/repo','empty_repo':False}
        if spec.operation=='branch':return {'name':spec.selector,'commit':{'id':self.g('rev-parse','refs/heads/'+spec.selector).strip().decode()}}
        if spec.operation=='tag':return {'name':spec.selector,'target':self.g('rev-parse','refs/tags/'+spec.selector).strip().decode(),'commit':{'id':self.g('rev-parse','refs/tags/'+spec.selector+'^{commit}').strip().decode()}}
        if spec.operation=='commit':
            data=self.g('cat-file','-p',spec.selector).split(b'\n\n',1)[0].splitlines();return {'id':spec.selector,'parent_ids':[row.split()[1].decode() for row in data if row.startswith(b'parent ')]}
        if spec.operation=='tree':
            value=ghfixtures.GitHub.response(self,spec)
            return [{'id':row['sha'],'name':row['path'].rsplit('/',1)[-1],'path':row['path'],'mode':row['mode'],'type':row['type']} for row in value['tree']]
        if spec.operation=='blob':return self.g('cat-file','blob',spec.selector)
        raise AssertionError(spec)

    # These checks use independently created Git objects; the source/transport above is GitLab.
    test_exact_raw_bytes_paths_modes_and_boundaries=ghfixtures.GitHub.test_exact_bytes_paths_modes_and_content_boundaries
    test_slash_refs_and_invalid_refs_before_requests=ghfixtures.GitHub.test_slash_ref_and_invalid_refs_do_not_enumerate
    test_local_gitlab_graph_and_direct_diff_equivalence=ghfixtures.GitHub.test_local_and_github_graph_diff_equivalence_without_project_execution
    test_large_flat_paginated_tree=ghfixtures.GitHub.test_flat_tree_over_one_thousand_files_uses_no_contents_listing
    test_cancelled_collection_returns_no_snapshot=ghfixtures.GitHub.test_cancelled_collection_returns_no_snapshot

    def test_named_annotated_tag_branch_collision_and_ref_movement(self):
        a=self.commit(b'A\n');self.g('tag','-a','same','-m','annotated',a);self.g('branch','same',a);b=self.commit(b'B\n');self.g('branch','-f','same',b)
        s=self.source();branch=s.pin('branch','same');tag=s.pin('tag','same');self.assertEqual((branch.commit_id,tag.commit_id),(b,a));self.commit(b'C\n');snap=s.snapshot(branch);self.assertEqual(snap.read_content(path_record(b'file.txt')['id']).data,b'B\n')
        self.assertIsNone(branch.tree_oid);self.assertEqual(s.report['tree_oid_reason'],'NOT_EXPOSED_BY_GITLAB_COMMIT_API');self.assertFalse(any(c.operation=='tag_object' for c in s.calls))
    def test_paginated_tree_keeps_pinned_commit_and_numeric_project(self):
        self.fixture();s=self.source(page_size=2);revision=s.pin('branch','main');snap=s.snapshot(revision);self.assertTrue(snap.inventory_complete);self.assertGreater(s.report['tree_pages'],1)
        for spec,url in zip(s.calls,s.urls):
            if spec.operation=='tree':self.assertEqual(spec.selector,revision.commit_id);self.assertIn('/projects/17/repository/tree?',url);self.assertIn('ref='+revision.commit_id,url)
        self.assertEqual(len(snap.entries),6)
    def test_duplicate_page_and_scoped_malicious_links_are_rejected(self):
        self.fixture()
        def overlap(spec,status,headers,value):
            if spec.operation=='tree':value=[{'id':'1'*40,'name':'x','path':'x','type':'blob','mode':'100644'}]
            return status,headers,value
        s=self.source(overlap,page_size=2);self.error('TREE_PAGE_OVERLAP',lambda:s.snapshot(s.pin('branch','main')))
        for replacement,code in [('https://evil.invalid','URL_REFUSED'),('https://gitlab.com/api/v4/projects/99/repository/tree','PAGINATION_REFUSED')]:
            def bad(spec,status,headers,value):
                if spec.operation=='tree':headers['link']='<'+replacement+'>; rel="next"'
                return status,headers,value
            s=self.source(bad,page_size=2);self.error(code,lambda:s.snapshot(s.pin('branch','main')))
    def test_cursor_loop_and_changed_pinned_ref_are_rejected(self):
        self.fixture()
        def loop(spec,status,headers,value):
            if spec.operation=='tree':headers['link']='<'+spec.url(s.registration)+'&page_token=2>; rel="next"'
            return status,headers,value
        s=self.source(loop,page_size=2);self.error('PAGINATION_LOOP',lambda:s.snapshot(s.pin('branch','main')))
        def changed(spec,status,headers,value):
            if spec.operation=='tree':headers['link']='<'+spec.url(s.registration).replace(spec.selector,'0'*40)+'&page_token=2>; rel="next"'
            return status,headers,value
        s=self.source(changed,page_size=2);self.error('PAGINATION_REFUSED',lambda:s.snapshot(s.pin('branch','main')))
    def test_full_page_without_next_metadata_is_incomplete(self):
        self.commit();rows=[{'id':'1'*40,'name':str(i),'path':str(i),'mode':'100644','type':'blob'} for i in range(100)]
        def no_link(spec,status,headers,value):return (status,{'content-type':'application/json'},rows) if spec.operation=='tree' else (status,headers,value)
        s=self.source(no_link);snap=s.snapshot(s.pin('branch','main'),path_ids=set());self.assertFalse(snap.inventory_complete);self.assertIn('PAGINATION_END_UNKNOWN',s.report['reasons']);self.assertEqual(snap.read_content(path_record(b'not-in-list')['id']).availability,'NOT_FETCHED')
    def test_request_budget_keeps_partial_inventory_and_source_gaps(self):
        self.fixture();s=self.source(page_size=2,budget=Budget(limit=5));snap=s.snapshot(s.pin('branch','main'));self.assertFalse(snap.inventory_complete);self.assertIn('REQUEST_LIMIT',s.report['reasons']);self.assertTrue(all(c.data is None for c in snap.contents.values()))
        s=self.source(budget=Budget(limit=5));snap=s.snapshot(s.pin('branch','main'));self.assertTrue(snap.inventory_complete);self.assertTrue(all(c.availability=='NOT_FETCHED' for c in snap.contents.values()))
    def test_empty_tree_and_404_are_distinct(self):
        self.g('commit','--allow-empty','-qm','empty');s=self.source();snap=s.snapshot(s.pin('branch','main'));self.assertTrue(snap.inventory_complete);self.assertEqual(snap.entries,())
        def absent(spec,status,headers,value):return (404,headers,{'message':'not accessible'}) if spec.operation=='tree' else (status,headers,value)
        s=self.source(absent);self.error('ACCESS_UNKNOWN',lambda:s.snapshot(s.pin('branch','main')))
    def test_invalid_path_parent_name_mode_and_page_shape(self):
        self.commit()
        for field,value,code in [('path','../x','PATH_UNREPRESENTABLE'),('path','bad\ufffd','PATH_UNREPRESENTABLE'),('name','other','GITLAB_RESPONSE_INVALID'),('mode','040000','GITLAB_RESPONSE_INVALID')]:
            def bad(spec,status,headers,data):
                if spec.operation=='tree':data[0][field]=value
                return status,headers,data
            s=self.source(bad);self.error(code,lambda:s.snapshot(s.pin('branch','main')))
        def orphan(spec,status,headers,data):
            if spec.operation=='tree':data[0].update(path='missing/file.txt',name='file.txt')
            return status,headers,data
        s=self.source(orphan);self.error('TREE_PARENT_MISSING',lambda:s.snapshot(s.pin('branch','main')))
        def shape(spec,status,headers,data):return (status,headers,{}) if spec.operation=='tree' else (status,headers,data)
        s=self.source(shape);self.error('GITLAB_RESPONSE_INVALID',lambda:s.snapshot(s.pin('branch','main')))
    def test_raw_bytes_not_transcoded_json_and_corruption_is_refused(self):
        raw='한글'.encode('utf-16');self.commit(raw);s=self.source();snap=s.snapshot(s.pin('branch','main'));self.assertEqual(next(iter(snap.contents.values())).data,raw);self.assertTrue(any(url.endswith('/raw') for spec,url in zip(s.calls,s.urls) if spec.operation=='blob'))
        def transcoded(spec,status,headers,data):return (status,headers,'한글'.encode('utf-8')) if spec.operation=='blob' else (status,headers,data)
        s=self.source(transcoded);self.error('BLOB_IDENTITY_MISMATCH',lambda:s.snapshot(s.pin('branch','main')))
    def test_size_total_limits_and_shared_blob_reads(self):
        self.commit(b'x'*(1024*1024+1));s=self.source();snap=s.snapshot(s.pin('branch','main'));self.assertEqual(next(iter(snap.contents.values())).availability,'LIMIT_EXCEEDED')
        self.commit(b'x'*16);(self.root/'alias').write_bytes(b'x'*16);self.g('add','.');self.g('commit','-qm','aliases');s=self.source()
        with patch('calf_extensions.repository.providers.gitlab.TOTAL_SOURCE_LIMIT',20):snap=s.snapshot(s.pin('branch','main'))
        self.assertEqual(sum(c.availability=='READY' for c in snap.contents.values()),1);self.assertEqual(sum(c.reason=='TOTAL_SOURCE_LIMIT' for c in snap.contents.values()),1);self.assertEqual(sum(c.operation=='blob' for c in s.calls),1)
    def test_source_identity_commit_and_tree_null_contract(self):
        self.commit();s=self.source();revision=s.pin('branch','main');self.error('SOURCE_MISMATCH',lambda:s.snapshot(replace(revision,repository_key='0'*64)));self.error('SOURCE_MISMATCH',lambda:s.snapshot(replace(revision,tree_oid='0'*40)))
        def mismatch(spec,status,headers,data):return (status,headers,dict(data,id=99)) if spec.operation=='identity' else (status,headers,data)
        s=self.source(mismatch);self.error('IDENTITY_MISMATCH',lambda:s.pin('branch','main'))
        def stale(spec,status,headers,data):return (status,headers,dict(data,path_with_namespace='changed/repo')) if spec.operation=='identity' else (status,headers,data)
        s=self.source(stale);self.error('REGISTRATION_STALE',lambda:s.pin('branch','main'))
        def wrong(spec,status,headers,data):return (status,headers,dict(data,id='0'*40)) if spec.operation=='commit' else (status,headers,data)
        s=self.source(wrong);self.error('GITLAB_RESPONSE_INVALID',lambda:s.pin('branch','main'))
    def test_selected_sources_roundtrip_without_fictitious_tree_identity(self):
        self.fixture();s=self.source();snap=s.snapshot(s.pin('branch','main'),path_ids={path_record(b'pkg/service.py')['id']});self.assertEqual(s.report['content_ready'],1);self.assertTrue(snap.inventory_complete)
        store=Store(self.base/'retained',create=True);sid=store.save_snapshot(snap);self.assertEqual(store.load_snapshot(sid).manifest(),snap.manifest());self.assertIsNone(snap.revision.tree_oid);self.assertIsNotNone(s.report['inventory_digest'])
    def test_cancel_after_last_blob_prevents_snapshot(self):
        self.commit()
        def cancel(spec,status,headers,data):
            if spec.operation=='blob':s.cancel_event.set()
            return status,headers,data
        s=self.source(cancel);revision=s.pin('branch','main');self.error('CANCELLED',lambda:s.snapshot(revision))


class HTTPGitLab(unittest.TestCase):
    setUp=httpfixtures.H1.setUp
    stop_http=httpfixtures.H1.stop_http
    transport=httpfixtures.H1.transport
    def source(self):
        raw=b'\xff\xfeA\x00\r\n';blob=git_blob_oid(raw,'sha1');commit='a'*40
        reg=self.registry.add('gitlab','https://gitlab.com/group/sub/repo');reg=self.registry.bind(reg.id,reg.version,{'id':17,'path_with_namespace':'group/sub/repo'})
        def behavior(request):
            path=request['path']
            if path.endswith('/raw'):return 200,{'Content-Type':'application/json'},raw
            if path.endswith('/17'):return 200,{}, {'id':17,'path_with_namespace':'group/sub/repo'}
            if '/commits/' in path:return 200,{}, {'id':commit,'parent_ids':[]}
            if '/tree?' in path:return 200,{}, [{'id':blob,'path':'raw.bin','name':'raw.bin','mode':'100644','type':'blob'}]
            raise AssertionError(path)
        self.http.behavior=behavior;reader=HTTPReader(reg,self.transport());self.addCleanup(reader.close);return GitLabSource(reg,reader),commit,raw,behavior
    def test_owned_http_raw_bytes_are_not_json_decoded(self):
        source,commit,raw,_=self.source();snap=source.snapshot(source.pin('commit',commit));self.assertEqual(next(iter(snap.contents.values())).data,raw);self.assertTrue(source.reader.transport.last_cleanup['threads_stopped']);self.assertTrue(all('/projects/17' in r['path'] for r in self.http.seen))
    def test_cancel_during_actual_raw_read_stops_owned_worker(self):
        source,commit,raw,behavior=self.source();revision=source.pin('commit',commit);reached=threading.Event();release=threading.Event();errors=[];snapshots=[]
        def slow(request):
            if request['path'].endswith('/raw'):reached.set();release.wait(5)
            return behavior(request)
        self.http.behavior=slow
        def collect():
            try:snapshots.append(source.snapshot(revision))
            except RepositoryError as e:errors.append(e.code)
        thread=threading.Thread(target=collect);thread.start()
        try:
            self.assertTrue(reached.wait(3));start=time.monotonic();source.cancel_event.set();thread.join(3);self.assertFalse(thread.is_alive());self.assertLess(time.monotonic()-start,3);self.assertEqual(errors,['CANCELLED']);self.assertEqual(snapshots,[]);self.assertTrue(source.reader.transport.last_cleanup['stopped']);self.assertTrue(source.reader.transport.last_cleanup['threads_stopped'])
        finally:release.set();thread.join(3)
