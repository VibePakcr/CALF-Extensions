"""H4 state/publication and retained source contracts; all repositories are disposable."""
from dataclasses import replace
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from . import test_gitlab_source as glfixtures
from ..analyze import analyze_snapshot
from ..capture import Store
from ..hosted import HostedServices
from ..http_reader import HTTPReader
from ..model import RepositoryError,canonical,digest,path_record
from ..navigation import NavigationHub,RetainedView,ViewStore,changed_paths
from ..providers.base import Content,Entry,RepositoryIdentity,Revision,Snapshot
from ..providers.gitlab import GitLabSource
from ..viewer import Project


class NavigationH4(unittest.TestCase):
    setUp=glfixtures.GitLab.setUp
    g=glfixtures.GitLab.g
    commit=glfixtures.GitLab.commit
    reader=glfixtures.GitLab.reader
    response=glfixtures.GitLab.response
    fixture=glfixtures.GitLab.fixture
    error=glfixtures.GitLab.error
    def hub(self,local=False,factory=None):
        hosted=HostedServices(self.base/'portal');reg=hosted.registry.add('gitlab','https://gitlab.com/group/sub/repo');reg=hosted.registry.bind(reg.id,reg.version,{'id':17,'path_with_namespace':'group/sub/repo'})
        template=glfixtures.GitLab.source(self)
        def source(registration,cancel,budget):return GitLabSource(registration,HTTPReader(registration,template.reader.transport),cancel=cancel,budget=budget)
        project=Project(self.root,self.base/'portal') if local else None
        if project:project.refresh()
        hub=NavigationHub(self.base/'portal',project,hosted,source_factory=factory or source);self.addCleanup(hosted.close);self.addCleanup(hub.close);hub.registration=reg;return hub
    def collect(self,hub,**extra):return hub.wait(hub.collect(hub.registration.id,'branch','main',**extra)['id'])
    def test_first_parent_pair_and_source_capabilities(self):
        a=self.commit(b'A\n');b=self.commit(b'B\n');hub=self.hub();job=self.collect(hub);self.assertEqual(job['state'],'SUCCEEDED',job);payload=hub.payload();view=payload['view'];self.assertEqual((view['left_commit'],view['right_commit']),(a,b));self.assertFalse(payload['source_capabilities']['working']);self.assertTrue(payload['source_capabilities']['cached_copy_editor'])
        path=path_record(b'file.txt')['id'];self.assertEqual(hub.source(path,'left',view['context_id'])['text'],'A\n');diff=hub.comparison(path,'left','right',view['context_id']);self.assertEqual(diff['comparison_basis'],'DIRECT_SNAPSHOT');self.assertIn('+B',diff['lines']);self.assertNotIn('snapshot_path',hub.source(path,'right'))
    def test_parentless_commit_has_explicit_empty_baseline(self):
        commit=self.commit(b'first\n');hub=self.hub();job=self.collect(hub);self.assertEqual(job['state'],'SUCCEEDED',job);view=hub.active;self.assertIsNone(view.left);self.assertEqual(view.record['empty_baseline']['commit'],commit);path=path_record(b'file.txt')['id'];diff=view.comparison(path);self.assertEqual(diff['left']['kind'],'absent');self.assertIsNone(diff['left']['commit']);self.assertEqual(diff['left']['revision_kind'],'EMPTY_BASELINE');self.assertIn('+first',diff['lines'])
    def test_cancel_and_late_generation_never_publish_a_view(self):
        self.commit();entered=threading.Event();release=threading.Event()
        normal=self.hub();factory=normal._factory
        def slow(reg,cancel,budget):
            source=factory(reg,cancel,budget);pin=source.pin
            def wait(*args):entered.set();release.wait(3);return pin(*args)
            source.pin=wait;return source
        normal._factory=slow;before=normal.payload();job=normal.collect(normal.registration.id,'branch','main');self.assertTrue(entered.wait(2));normal.cancel(job['id']);release.set();result=normal.wait(job['id']);self.assertEqual(result['state'],'CANCELLED');self.assertEqual(normal.views.summaries(),[]);self.assertEqual(normal.payload()['view'],before['view']);self.assertEqual(normal.payload()['graph'],before['graph'])
    def test_source_selection_supersedes_inflight_collection(self):
        self.commit();hub=self.hub(local=True);entered=threading.Event();release=threading.Event();factory=hub._factory
        def slow(reg,cancel,budget):
            source=factory(reg,cancel,budget);pin=source.pin
            def wait(*args):entered.set();release.wait(3);return pin(*args)
            source.pin=wait;return source
        hub._factory=slow;job=hub.collect(hub.registration.id,'branch','main');self.assertTrue(entered.wait(2));hub.select(source='local');release.set();self.assertEqual(hub.wait(job['id'])['state'],'SUPERSEDED');self.assertEqual(hub.payload()['view']['source_id'],'local');self.assertEqual(hub.views.summaries(),[])
    def test_partial_capture_is_retained_but_requires_explicit_selection(self):
        self.commit();hub=self.hub(local=True);before=hub.payload()['view'];factory=hub._factory
        def partial(reg,cancel,budget):
            source=factory(reg,cancel,budget);snapshot=source.snapshot
            def read(revision,**kwargs):
                value=snapshot(revision,**kwargs)
                if not kwargs:value=replace(value,contents={e.id:Content(e.id,'NOT_FETCHED',blob_oid=e.blob_oid,mode=e.mode) for e in value.entries})
                return value
            source.snapshot=read;return source
        hub._factory=partial;job=self.collect(hub);self.assertEqual(job['state'],'SAVED_PARTIAL',job);self.assertEqual(hub.payload()['view'],before);hub.select(source=hub.registration.id);self.assertEqual(hub.payload()['view'],before)
        hub.select(context=job['result']['context_id']);self.assertEqual(hub.payload()['view']['coverage']['state'],'PARTIAL')
    def test_changed_inventory_over_350_and_deleted_code(self):
        for i in range(351):(self.root/('f'+str(i)+'.txt')).write_text('before\n')
        self.g('add','.');self.g('commit','-qm','old');a=self.g('rev-parse','HEAD').strip().decode()
        for i in range(351):(self.root/('f'+str(i)+'.txt')).write_text('after\n')
        (self.root/'f0.txt').unlink();self.g('add','.');self.g('commit','-qm','new');hub=self.hub();job=self.collect(hub);self.assertEqual(job['state'],'SUCCEEDED',job);changes=hub.active.changes;self.assertTrue(changes['complete']);self.assertEqual(changes['total'],351)
        key=path_record(b'f0.txt')['id'];self.assertEqual(hub.active.source(key,'left')['commit'],a);self.assertEqual(hub.active.source(key,'right')['kind'],'absent');self.assertIn('-before',hub.active.comparison(key)['lines'])
    def test_explicit_pair_is_direct_and_not_merge_base(self):
        base=self.commit(b'base\n');self.g('branch','left');right=self.commit(b'right\n');self.g('checkout','-q','left');left=self.commit(b'left\n');self.g('checkout','-q','main');hub=self.hub();job=self.collect(hub,left_kind='branch',left_name='left');self.assertEqual(job['state'],'SUCCEEDED',job);self.assertEqual(hub.active.left.revision.commit_id,left);self.assertEqual(hub.active.right.revision.commit_id,right);self.assertNotEqual(left,base)
        diff=hub.active.comparison(path_record(b'file.txt')['id']);self.assertIn('-left',diff['lines']);self.assertNotIn('-base',diff['lines'])
    def test_cached_reopen_no_network_and_context_guard(self):
        self.commit();hub=self.hub();job=self.collect(hub);context=job['result']['context_id'];expected=hub.payload();hub.active=None
        with patch('subprocess.Popen',side_effect=AssertionError('No Git/HTTP when reopening retained view')):hub.select(context=context);self.assertEqual(hub.payload(),expected)
        self.error('CONTEXT_CHANGED',lambda:hub.source(path_record(b'file.txt')['id'],'right','0'*64))
    def test_editor_copy_has_exact_bytes_safe_name_and_no_cache_edit(self):
        self.commit(b'original\n',name='unsafe +#.py');hub=self.hub();self.collect(hub);path=path_record(b'unsafe +#.py')['id'];context=hub.active.context_id;copy=hub.views.editor_copy(hub.active,path,'right',1);p=Path(copy['path']);self.assertEqual(p.read_bytes(),b'original\n');self.assertEqual(copy['kind'],'RETAINED_COPY');self.assertNotIn('unsafe',p.name);p.write_bytes(b'owner edit');self.assertEqual(hub.active.source(path,'right')['text'],'original\n');self.assertEqual(hub.store.read_source_bytes(digest(b'original\n')),b'original\n')
        self.assertIn('/-/blob/'+hub.active.right.revision.commit_id+'/unsafe%20%2B%23.py',hub.active.source(path,'right')['provider_url'])
    def test_registry_change_prevents_publication_and_failure_keeps_local(self):
        self.commit();hub=self.hub(local=True);factory=hub._factory
        def removed(reg,cancel,budget):
            source=factory(reg,cancel,budget);snapshot=source.snapshot
            def read(revision,**kwargs):
                value=snapshot(revision,**kwargs)
                if not kwargs:hub.hosted.registry.remove(reg.id)
                return value
            source.snapshot=read;return source
        hub._factory=removed;job=self.collect(hub);self.assertEqual(job['state'],'FAILED');self.assertEqual(hub.payload()['view']['source_id'],'local');self.assertEqual(hub.views.summaries(),[])
    def test_namespace_and_source_version_refusals(self):
        self.commit();hub=self.hub();self.collect(hub);self.error('INVALID_VERSION',lambda:hub.active.source(path_record(b'file.txt')['id'],'working'));self.error('INVALID_VERSION',lambda:hub.comparison(path_record(b'file.txt')['id'],'head','working',hub.active.context_id));(hub.views.root/'schema').write_bytes(b'foreign');self.error('VIEW_PATH_REFUSED',lambda:hub.views.load(hub.active.context_id))
    def test_partial_inventory_cannot_claim_complete_changes(self):
        key=path_record(b'x');repo=RepositoryIdentity('github','https://api.github.com','42','Fixture');a=Snapshot(repo,Revision(repo.key,'commit',commit_id='a'*40),(),{},inventory_complete=False);b=Snapshot(repo,Revision(repo.key,'commit',commit_id='b'*40),(Entry(**key,mode='100644',blob_oid='c'*40),),{})
        result=changed_paths(a,b);self.assertFalse(result['complete']);self.assertEqual(result['items'][0]['status'],'UNKNOWN')
