"""Project identity, lazy module selection and preservation contracts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from calf_extensions.repository import context as cx, history_index as hi
from calf_extensions.repository.model import RepositoryError

class ContextTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve();self.project=self.root/'project';self.project.mkdir();(self.project/'.git').mkdir()
        self.home=self.root/'context';self.home.mkdir();self.cache=self.root/'cache';self.cache.mkdir()
        (self.root/'records').mkdir();self.history=self.root/'records/history.html';self.mapping=self.root/'modules.json'
        self.mapping.write_bytes(hi.encode({'schema':'calf.repository.history-modules.v1','modules':[
            {'id':'repository','label':'Repository history','paths':['repo'],'tasks':['older-rule']},
            {'id':'auth','label':'Authentication','paths':['auth']}]}))
        entries=[{'id':'older-rule','kind':'TASK','task':'older-rule','body':'KEEP_OLDER_RULE core1.8.8; UNKNOWN remains unknown','data':{'scope':['repo/index.py']},'relations':[]}]
        entries += [{'id':'repo-'+str(i),'kind':'TASK','task':'repo-'+str(i),'body':'Repository observation '+str(i),'data':{'scope':['repo/index.py']},'relations':[]} for i in range(24)]
        entries += [{'id':'auth-only','kind':'TASK','task':'auth-only','body':'UNRELATED_AUTH_RECORD','data':{'scope':['auth/login.py']},'relations':[]}]
        previous='0'*64;rows=[]
        for n,record in enumerate(entries,1):
            digest=hashlib.sha256(('fixture-'+str(n)).encode()).hexdigest();rows.append({'seq':n,'prev':previous,'hash':digest,'record':record});previous=digest
        self.history.write_bytes(b'<!doctype html>\n'+b'\n'.join(hi.MARKER+hi.encode(r)+hi.END for r in rows));self.original=self.history.read_bytes()
        self.binding=cx.bind(self.home,self.project,self.history,self.mapping,self.cache,aliases={'repository':['저장소 기록','기록 조회'],'auth':['인증']})

    def connection(self,cwd=None):return cx.discover(self.home,cwd or self.project)

    def error(self,code,fn):
        with self.assertRaises(RepositoryError) as e:fn()
        self.assertEqual(e.exception.code,code)

    def test_nested_directory_discovers_project_without_history_path(self):
        nested=self.project/'repo'/'nested';nested.mkdir(parents=True)
        self.assertEqual(self.connection(nested).project,self.project)

    def test_unregistered_nested_git_and_sibling_do_not_inherit(self):
        child=self.project/'child';child.mkdir();(child/'.git').write_text('gitdir: not-read\n')
        self.assertIsNone(self.connection(child))
        sibling=self.root/'sibling';sibling.mkdir();self.assertIsNone(self.connection(sibling))

    def test_registration_identity_is_checked_and_not_overwritten(self):
        path=Path(self.binding['binding']);original=path.read_bytes()
        with self.assertRaises(FileExistsError):cx.bind(self.home,self.project,self.history,self.mapping,self.cache)
        self.assertEqual(path.read_bytes(),original)
        value=json.loads(original);value['project']=str(self.root);path.write_bytes(hi.encode(value))
        self.error('CONTEXT_PROJECT_IDENTITY',self.connection)

    def test_discovery_does_not_read_journal_or_notes(self):
        with patch.object(Path,'open',autospec=True,side_effect=Path.open) as opened:
            c=self.connection();self.assertIn('repository',[r['id'] for r in c.catalogue()])
        names=[p.args[0].name for p in opened.call_args_list]
        self.assertNotIn('history.html',names);self.assertFalse(any(n.startswith('sub_') for n in names))

    def test_english_korean_and_file_selection(self):
        c=self.connection()
        self.assertEqual(c.select('Continue repository'),['repository'])
        self.assertEqual(c.select('기록 조회를 이어가자'),['repository'])
        self.assertEqual(c.select(files=['auth/login.py']),['auth'])
        self.assertEqual(c.select('repositorystore'),[])
        self.error('CONTEXT_FILE',lambda:c.select(files=['../auth/login.py']))

    def test_unknown_or_ambiguous_task_reads_no_notes(self):
        c=self.connection()
        for task in ['Continue this work','repository auth']:
            with patch.object(c,'view',side_effect=AssertionError('must not load index')):
                r=c.read(task);self.assertEqual(r['state'],'SELECT_MODULE');self.assertEqual(r['documents'],[])

    def test_only_selected_markdown_is_loaded_and_warm_read_skips_source_body(self):
        c=self.connection();c.read('repository')
        with patch.object(hi,'read_small',wraps=hi.read_small) as reads,patch.object(hi,'build',side_effect=AssertionError('warm cache rebuilt')):
            r=self.connection().read('repository')
        self.assertEqual([d['module'] for d in r['documents']],['repository'])
        self.assertNotIn('UNRELATED_AUTH_RECORD',json.dumps(r));self.assertEqual(r['metrics']['sourceBytesRead'],0)
        self.assertNotIn('sub_auth.md',[p.args[0].name for p in reads.call_args_list]);self.assertEqual(self.history.read_bytes(),self.original)

    def test_older_rule_is_found_and_exact_record_is_scoped(self):
        c=self.connection();self.assertNotIn('KEEP_OLDER_RULE',json.dumps(c.read('repository')))
        found=c.search('repository','KEEP_OLDER_RULE')['matches'];self.assertEqual(found[0]['seq'],1)
        self.assertEqual(c.record('repository',1)['record']['record']['id'],'older-rule')
        self.error('CONTEXT_RECORD_OUTSIDE_MODULE',lambda:c.record('repository',26))

    def test_current_status_requires_bound_native_and_matching_module(self):
        c=self.connection()
        self.error('CONTEXT_NATIVE_NOT_BOUND',lambda:c.status('repository','older-rule'))
        self.error('CONTEXT_TASK_OUTSIDE_MODULE',lambda:c.status('repository','auth-only'))
        self.assertEqual(c.read('repository')['currentCompletion'],'NOT_EVALUATED')

    def test_append_rebuilds_separate_view_preserves_old_and_source(self):
        c=self.connection();first=c.view().root;before={p.relative_to(first):p.read_bytes() for p in first.rglob('*') if p.is_file()}
        self.history.write_bytes(self.original+b'\n<!-- append -->');second=c.view().root
        self.assertNotEqual(first,second);self.assertTrue(all((first/p).read_bytes()==b for p,b in before.items()))
        self.assertEqual(self.history.read_bytes(),self.original+b'\n<!-- append -->')

    def test_changed_note_or_cross_project_cache_is_refused(self):
        c=self.connection();v=c.view();(v.root/'sub_repository.md').write_text('forged success')
        self.error('HISTORY_PROJECTION_CHANGED',lambda:c.read('repository'))
        index=json.loads((v.root/'INDEX.json').read_bytes());other=self.root/'other-history.html';other.write_bytes(self.original)
        index['source'].update(path=str(other),stamp=hi.stamp(other));(v.root/'INDEX.json').write_bytes(hi.encode(index))
        self.error('CONTEXT_MAPPING_CHANGED',lambda:c.read('repository'))

    def test_symlinked_registration_and_cache_inside_source_are_refused(self):
        path=Path(self.binding['binding']);other=self.home/'saved.json';other.write_bytes(path.read_bytes());path.unlink()
        try:path.symlink_to(other)
        except OSError:self.skipTest('OS denied creating a test symlink')
        self.error('HISTORY_PHYSICAL_PATH_REQUIRED',self.connection)
        path.unlink();inside=self.project/'cache';inside.mkdir()
        self.error('CONTEXT_CACHE_INSIDE_SOURCE',lambda:cx.bind(self.home,self.project,self.history,self.mapping,inside))

if __name__=='__main__':unittest.main()
