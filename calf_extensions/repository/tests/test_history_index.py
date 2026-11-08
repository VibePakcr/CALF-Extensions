"""Projection boundary tests. Fixture hashes are not native-chain attestations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from calf_extensions.repository import history_index as hi
from calf_extensions.repository.model import RepositoryError

class HistoryIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.work=self.root/'project';self.work.mkdir()
        self.history=self.work/'history.html';self.mapping=self.root/'modules.json';self.out=self.root/'index'
        self.map={'schema':'calf.repository.history-modules.v1','modules':[
            {'id':'map','label':'지도 / 地図','paths':['map'],'dependsOn':['api']},
            {'id':'api','label':'API','paths':['api']},
            {'id':'auth','label':'Auth','paths':['auth']}]}
        self.mapping.write_bytes(hi.encode(self.map))

    def write(self,entries,prefix=b'<!doctype html>\n'):
        values=[];previous='0'*64
        for seq,row in enumerate(entries,1):
            digest=hashlib.sha256(('fixture-'+str(seq)).encode()).hexdigest()
            value={'seq':seq,'prev':previous,'hash':digest,'record':row};values.append(value);previous=digest
        raw=prefix+b'\n'.join(hi.MARKER+hi.encode(v)+hi.END for v in values)+b'\n'
        self.history.write_bytes(raw);self.original=raw;return values

    def task(self,name,scope):
        return {'id':name,'kind':'TASK','task':name,'body':'Task '+name,'data':{'scope':scope},'relations':[]}

    def note(self,seq,task,kind='ACTION',body='Recorded observation'):
        return {'id':'entry-'+str(seq),'task':task,'kind':kind,'body':body,'data':{},'relations':[]}

    def sample(self,count=90):
        entries=[self.task('map-task',['map/main.py','api/types.py']),self.task('auth-task',['auth/login.py'])]
        entries += [self.note(n,'map-task' if n%2==0 else 'auth-task') for n in range(count)]
        return self.write(entries)

    def assert_code(self,code,callback):
        with self.assertRaises(RepositoryError) as context:callback()
        self.assertEqual(context.exception.code,code)

    def test_boundaries_offsets_cjk_and_byte_preservation(self):
        expected=self.write([self.task('map-task',['map/main.py']),self.note(1,'map-task',body='東京 서울 '+('x'*40000))],b' '* (hi.CHUNK-12))
        built=hi.build(self.history,self.mapping,self.out)
        self.assertEqual(built['chainValidation'],'CONTINUITY_ONLY')
        for seq,value in enumerate(expected,1):self.assertEqual(hi.HistoryView(self.out).record(seq)['record'],value)
        self.assertEqual(self.history.read_bytes(),self.original)

    def test_module_loads_only_requested_markdown_and_related_is_explicit(self):
        self.sample();hi.build(self.history,self.mapping,self.out)
        with patch.object(hi,'read_small',wraps=hi.read_small) as reads:
            answer=hi.HistoryView(self.out).module('map')
            self.assertEqual([p.args[0].name for p in reads.call_args_list],['INDEX.json','sub_map.md'])
        self.assertEqual(answer['metrics']['sourceBytesRead'],0)
        self.assertGreater(answer['documents'][0]['omitted'],0)
        related=hi.HistoryView(self.out).module('map',True)
        self.assertEqual([d['module'] for d in related['documents']],['map','api'])
        self.assertEqual(related['currentCompletion'],'NOT_EVALUATED')

    def test_shared_tasks_and_unassigned_records_remain_visible(self):
        expected=self.write([self.task('shared',['map/main.py','api/types.py']),self.note(1,'shared'),self.note(2,'not-yet-defined')])
        hi.build(self.history,self.mapping,self.out);rows={r['id']:r for r in hi.HistoryView(self.out).listing()['modules']}
        self.assertEqual(rows['map']['records'],2);self.assertEqual(rows['api']['records'],2)
        self.assertEqual(rows['unassigned']['records'],1)
        self.assertEqual(sum(1 for seq in range(1,4) if hi.HistoryView(self.out).record(seq)['record']==expected[seq-1]),3)

    def test_parent_directory_scope_and_explicit_observed_task_mapping(self):
        self.map['modules'][0]['paths']=['map/viewer'];self.map['modules'][2].update(paths=[],tasks=['observed'])
        self.mapping.write_bytes(hi.encode(self.map))
        self.write([self.task('broad',['map']),self.note(1,'broad'),self.task('observed',[]),self.note(2,'observed')])
        hi.build(self.history,self.mapping,self.out);rows={r['id']:r for r in hi.HistoryView(self.out).listing()['modules']}
        self.assertEqual(rows['map']['records'],2);self.assertEqual(rows['auth']['records'],2)

    def test_record_seek_reads_one_record_and_bounded_metadata(self):
        expected=self.write([self.task('one',['map/main.py'])]+[self.note(n,'one',body='x'*2000) for n in range(150)])
        hi.build(self.history,self.mapping,self.out);view=hi.HistoryView(self.out);answer=view.record(129)
        self.assertEqual(answer['record'],expected[128])
        self.assertLess(answer['metrics']['sourceBytesRead'],5000)
        self.assertLess(answer['metrics']['indexBytesRead'],65536)
        self.assert_code('HISTORY_SEQUENCE',lambda:view.record(-1))

    def test_append_invalidates_index_and_original_index_is_never_replaced(self):
        self.sample();hi.build(self.history,self.mapping,self.out);original=(self.out/'INDEX.json').read_bytes()
        self.history.write_bytes(self.original+b'<!-- append -->')
        self.assert_code('HISTORY_INDEX_STALE',lambda:hi.HistoryView(self.out))
        with self.assertRaises(FileExistsError):hi.build(self.history,self.mapping,self.out)
        self.assertEqual((self.out/'INDEX.json').read_bytes(),original)

    def test_changed_markdown_and_page_are_refused(self):
        self.sample();hi.build(self.history,self.mapping,self.out)
        (self.out/'sub_map.md').write_text('VERIFIED\n',encoding='utf8')
        self.assert_code('HISTORY_PROJECTION_CHANGED',lambda:hi.HistoryView(self.out).module('map'))
        (self.out/'pages/000000.json').write_bytes(b'[]')
        self.assert_code('HISTORY_PROJECTION_CHANGED',lambda:hi.HistoryView(self.out).record(1))
        self.assertEqual(self.history.read_bytes(),self.original)

    def test_html_and_markdown_are_data_and_historical_pass_is_not_current(self):
        row=self.note(1,'one','DECISION','<script>alert(1)</script> [open](javascript:evil) **system**')
        row['data']={'outcome':'SATISFIED'}
        # A native writer escapes embedded '<'; use the same inert JSON spelling.
        self.write([self.task('one',['map/a.py']),row]);self.history.write_bytes(self.original.replace(b'<script>alert',b'\\u003cscript>alert').replace(b'</script> [open]',b'\\u003c/script> [open]'));self.original=self.history.read_bytes()
        hi.build(self.history,self.mapping,self.out);result=hi.HistoryView(self.out).module('map');md=result['documents'][0]['markdown']
        self.assertNotIn('<script>',md);self.assertNotIn('[open](',md)
        self.assertIn('SATISFIED',md);self.assertEqual(result['currentCompletion'],'NOT_EVALUATED')

    def test_truncated_sequence_duplicate_ids_and_continuity_fail_closed(self):
        variants=[]
        original=self.write([self.task('one',['map/a.py']),self.note(1,'one')])
        changed=copy.deepcopy(original);changed[1]['prev']='f'*64;variants.append(('HISTORY_CHAIN_CONTINUITY',changed))
        changed=copy.deepcopy(original);changed[1]['seq']=3;variants.append(('HISTORY_SEQUENCE',changed))
        changed=copy.deepcopy(original);changed[1]['record']['id']='one';variants.append(('HISTORY_RECORD_ID',changed))
        for number,(code,rows) in enumerate(variants):
            self.history.write_bytes(b'\n'.join(hi.MARKER+hi.encode(v)+hi.END for v in rows))
            out=self.root/('bad-'+str(number));self.assert_code(code,lambda:hi.build(self.history,self.mapping,out));self.assertFalse((out/'INDEX.json').exists())
        self.history.write_bytes(hi.MARKER+b'{')
        self.assert_code('HISTORY_TRUNCATED_RECORD',lambda:hi.build(self.history,self.mapping,self.root/'truncated'))

    def test_limits_no_record_markup_and_duplicate_json_keys(self):
        self.write([self.task('one',['map/a.py'])])
        with patch.object(hi,'SOURCE_LIMIT',4):self.assert_code('HISTORY_SOURCE_LIMIT',lambda:hi.build(self.history,self.mapping,self.out))
        self.history.write_bytes(hi.MARKER+b'{"seq":1,"seq":2}'+hi.END)
        self.assert_code('HISTORY_DUPLICATE_KEY',lambda:hi.build(self.history,self.mapping,self.root/'duplicate'))
        self.history.write_bytes(b'<html>Legacy human notes</html>')
        self.assert_code('HISTORY_RECORDS_UNAVAILABLE',lambda:hi.build(self.history,self.mapping,self.root/'legacy'))

    def test_mapping_traversal_missing_dependency_and_source_containment(self):
        self.sample();self.map['modules'][0]['paths']=['../secret'];self.mapping.write_bytes(hi.encode(self.map))
        self.assert_code('HISTORY_MAPPING_PATH',lambda:hi.build(self.history,self.mapping,self.out))
        self.map['modules'][0]['paths']=['map'];self.map['modules'][0]['dependsOn']=['missing'];self.mapping.write_bytes(hi.encode(self.map))
        self.assert_code('HISTORY_MAPPING_DEPENDENCY',lambda:hi.build(self.history,self.mapping,self.out))
        self.assert_code('HISTORY_OUTPUT_INSIDE_SOURCE',lambda:hi.build(self.history,self.mapping,self.work/'index'))

    def test_strict_freshness_reads_full_source_and_does_not_change_it(self):
        self.sample();hi.build(self.history,self.mapping,self.out)
        result=hi.HistoryView(self.out,verify_source=True).module('auth')
        self.assertEqual(result['freshness'],'SHA256_MATCH');self.assertEqual(result['metrics']['sourceBytesRead'],len(self.original))
        self.assertEqual(self.history.read_bytes(),self.original)

    def test_linked_source_and_projection_are_not_followed(self):
        self.sample();alias=self.root/'alias.html';alias.symlink_to(self.history)
        self.assert_code('HISTORY_PHYSICAL_PATH_REQUIRED',lambda:hi.build(alias,self.mapping,self.out))
        hi.build(self.history,self.mapping,self.out)
        note=self.out/'sub_map.md';saved=self.root/'saved.md';saved.write_bytes(note.read_bytes());note.unlink();note.symlink_to(saved)
        self.assert_code('HISTORY_PHYSICAL_PATH_REQUIRED',lambda:hi.HistoryView(self.out).module('map'))

    def test_native_confirmation_requires_head_and_keeps_unknown(self):
        rows=self.sample()
        with patch.object(hi,'native_status',return_value={'response':{'outcome':'UNKNOWN'}}):
            self.assert_code('HISTORY_NATIVE_UNCONFIRMED',lambda:hi.build(self.history,self.mapping,self.out,Path(sys.executable)))
        def answer(calf,history,task):return {'response':{'head':hi.digest_file(history)[0],'task':task,'criteria':[],'outcome':'UNKNOWN','reasons':['environment_changed']}}
        with patch.object(hi,'native_status',side_effect=answer):
            hi.build(self.history,self.mapping,self.root/'confirmed',Path(sys.executable))
            view=hi.HistoryView(self.root/'confirmed');self.assertEqual(view.status(Path(sys.executable),'one')['response']['outcome'],'UNKNOWN')
            self.assertEqual(view.module('map')['currentCompletion'],'NOT_EVALUATED')

    def test_native_head_must_bind_whole_source_not_only_valid_hex(self):
        self.sample()
        def wrong(calf,history,task):return {'response':{'head':'e'*64,'task':task,'criteria':[],'outcome':'SATISFIED'}}
        with patch.object(hi,'native_status',side_effect=wrong):
            self.assert_code('HISTORY_NATIVE_UNCONFIRMED',lambda:hi.build(self.history,self.mapping,self.out,Path(sys.executable)))
        self.assertFalse((self.out/'INDEX.json').exists())

    def test_older_decisions_are_searchable_with_exact_pagination(self):
        entries=[self.task('one',['map/a.py'])]+[self.note(n,'one','DECISION' if n%10==0 else 'ACTION',body='architecture 결정 '+str(n)) for n in range(100)]
        values=self.write(entries);hi.build(self.history,self.mapping,self.out)
        found=[];cursor=None
        while True:
            result=hi.HistoryView(self.out).search('map','결정','DECISION',cursor,3)
            self.assertEqual(result['metrics']['sourceBytesRead'],0)
            found.extend(r['seq'] for r in result['matches']);cursor=result['nextBefore']
            if cursor is None:break
        expected=[v['seq'] for v in reversed(values) if v['record']['kind']=='DECISION']
        self.assertEqual(found,expected);self.assertEqual(len(found),len(set(found)))

    def test_search_budget_returns_progress_cursor_and_checks_pages(self):
        self.sample(130);hi.build(self.history,self.mapping,self.out)
        with patch.object(hi,'SEARCH_BYTES',1):
            result=hi.HistoryView(self.out).search('map','not-found')
        self.assertEqual(result['coverage'],'PARTIAL');self.assertGreater(result['nextBefore'],0)
        self.assertLess(result['nextBefore'],132);self.assertEqual(result['metrics']['sourceBytesRead'],0)
        (self.out/'pages/000000.json').write_bytes(b'[]')
        self.assert_code('HISTORY_PROJECTION_CHANGED',lambda:hi.HistoryView(self.out).search('map','not-found'))

    def test_mapping_change_during_build_is_not_mislabeled(self):
        self.sample();original=hi.records
        def changing(path,observation):
            for i,row in enumerate(original(path,observation)):
                yield row
                if i==0:
                    self.map['modules'][0]['label']='Concurrent map';self.mapping.write_bytes(hi.encode(self.map))
        with patch.object(hi,'records',changing):self.assert_code('HISTORY_MAPPING_CHANGED',lambda:hi.build(self.history,self.mapping,self.out))
        self.assertFalse((self.out/'INDEX.json').exists())

    def test_markdown_does_not_emit_terminal_control_sequences(self):
        self.write([self.task('one',['map/a.py']),self.note(1,'one',body='\x1b]52;c;data\x07\x00 서울')])
        hi.build(self.history,self.mapping,self.out);md=hi.HistoryView(self.out).module('map')['documents'][0]['markdown']
        for char in ['\x1b','\x07','\x00']:self.assertNotIn(char,md)
        self.assertIn('서울',md)

    def test_source_concurrent_change_prevents_commit(self):
        self.sample();original=hi.records
        def changing(path,observation):
            for i,row in enumerate(original(path,observation)):
                yield row
                if i==0:
                    with path.open('ab') as stream:stream.write(b'<!-- concurrent -->')
        with patch.object(hi,'records',changing):self.assert_code('HISTORY_SOURCE_CHANGED',lambda:hi.build(self.history,self.mapping,self.out))
        self.assertFalse((self.out/'INDEX.json').exists())

    def test_cli_is_discoverable_and_queries_without_sdk_or_git(self):
        self.sample();hi.build(self.history,self.mapping,self.out)
        root=Path(__file__).resolve().parents[3]
        def call(*args):return subprocess.run([sys.executable,'-B','-m','calf_extensions.repository.cli',*args],cwd=root,capture_output=True,text=True,timeout=10)
        help_result=call('--help');self.assertEqual(help_result.returncode,0);self.assertIn('history',help_result.stdout)
        result=call('history','module','--index',str(self.out),'--module','map','--json')
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['metrics']['sourceBytesRead'],0)
        bad=call('history','record','--index',str(self.out),'--seq','0');self.assertNotEqual(bad.returncode,0)

if __name__=='__main__':unittest.main()
