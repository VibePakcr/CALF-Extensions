"""Real local CALF + FFmpeg acceptance test in a NEW, explicitly named folder.

Fixtures are generated without models/network/user media. This is not evidence
of ComfyUI, Remotion, external provider or aesthetic validation support.
"""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

from calf_sdk import CalfClient
from .common import run_tool, sha, read_json, MediaError
from .integration import register, prepare_scene, run_scene, reconcile_request
from .project import create_project, inspect_project, adopt_scene, select_version, validation_detail
from .test_contract import BASE, ContractTests


def fixture(ffmpeg, path, *, color=None, frequency=440, silent=False):
    video='testsrc2=size=320x180:rate=25' if color is None else f'color=c={color}:size=320x180:rate=25'
    audio='anullsrc=r=48000:cl=stereo' if silent else f'sine=frequency={frequency}:sample_rate=48000'
    run_tool([ffmpeg,'-hide_banner','-nostdin','-v','error','-n','-filter_threads','1',
              '-f','lavfi','-i',video,'-f','lavfi','-i',audio,'-t','1',
              '-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',
              '-movflags','+faststart',str(path)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calf',required=True,type=Path)
    parser.add_argument('--ffmpeg',required=True,type=Path)
    parser.add_argument('--ffprobe',required=True,type=Path)
    parser.add_argument('--workbench',type=Path,help='optional second native core for shared-record inspection')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    output=args.output
    if not output.is_absolute():parser.error('--output must be absolute')
    output.mkdir(parents=True,exist_ok=False);output=output.resolve(strict=True)
    report={'status':'FAIL','platform':platform.platform(),'network':False,'AI':False,'checks':[],
            'limitations':['synthetic one-second MP4 clips; not production media certification',
                          'technical validation only; aesthetic/semantic review not implemented',
                          'no OS sandbox against an unrelated process with the same filesystem rights']}
    def record(label,**fields):
        report['checks'].append({'check':label,**fields});print(label,flush=True)
    def evidence(label,value):
        (output/(label+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def blocked(call,expected):
        try:call()
        except MediaError as error:
            if expected not in str(error):raise
        else:raise AssertionError('expected refusal: '+expected)
    try:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful();record('bounded contract unit tests',tests=result.testsRun)
        client=CalfClient(args.calf.resolve(strict=True),output/'records',timeout=80)
        report['calf']=client.version();report['coreSha256']=client.binary_sha256()
        registration=register(client,output/'configuration',args.ffmpeg,args.ffprobe)
        report['tools']=read_json(output/'configuration'/'toolchain.json')
        sources=output/'inputs';sources.mkdir()
        for filename,options in [('one',{'color':'red'}),('two',{'color':'blue','frequency':550}),
                                 ('three',{'frequency':660}),('replacement',{'color':'green','frequency':770}),
                                 ('black',{'color':'black'}),('silent',{'silent':True})]:
            fixture(str(args.ffmpeg),sources/(filename+'.mp4'),**options)
        project=output/'scene-project';create_project(project,['scene-1','scene-2','scene-3'])
        def prepare(scene,source,key,**kw):
            return prepare_scene(client,project,scene,sources/(source+'.mp4'),registration,key,BASE,**kw)
        initial={}
        for number,source in [(1,'one'),(2,'two'),(3,'three')]:
            scene=f'scene-{number}';ticket=prepare(scene,source,'initial-'+str(number));view=run_scene(client,ticket)
            evidence('initial-'+str(number),view)
            assert view['outcome']=='SATISFIED',view
            selected=adopt_scene(client,project,ticket)
            initial[scene]=selected['selected'][scene]
        evidence('initial-approved',selected)
        record('three scenes independently rendered, checked and selected',versions={s:v['version'] for s,v in initial.items()})

        ticket=prepare('scene-3','replacement','edit-three')
        view=run_scene(client,ticket);evidence('edit-three',view);assert view['outcome']=='SATISFIED',view
        updated=adopt_scene(client,project,ticket);evidence('after-edit',updated)
        for scene in ['scene-1','scene-2']:
            assert updated['selected'][scene]==initial[scene]
            assert sha(initial[scene]['path'])==initial[scene]['sha256']
        assert updated['selected']['scene-3']['version']!=initial['scene-3']['version']
        assert sha(initial['scene-3']['path'])==initial['scene-3']['sha256']
        record('edit scene 3 only; scene 1/2 hashes and pointers unchanged; old scene 3 retained')

        repeated=prepare('scene-3','replacement','edit-three')
        assert repeated==ticket
        again=run_scene(client,repeated);assert again['calls']==view['calls'] and again['attempt']==1
        assert adopt_scene(client,project,ticket)==updated
        blocked(lambda:adopt_scene(client,project,{**ticket,'sceneId':'scene-1'}),'ticket_scene_scope_mismatch')
        blocked(lambda:prepare('scene-3','one','edit-three'),'request_key_conflict')
        record('same logical request is idempotent; changed intent rejected; no extra render')

        # A producer exits successfully, but the frozen independent requirement
        # intentionally expects a different width. Exit 0 must not select it.
        invalid=prepare('scene-3','replacement','wrong-width',expected={**BASE,'width':322})
        wrong=run_scene(client,invalid);evidence('wrong-width',wrong)
        assert wrong['outcome']=='VIOLATED',wrong
        assert 'width' in json.loads(wrong['verification']['checks'][0]['detail']['reason'])['violations']
        blocked(lambda:adopt_scene(client,project,invalid),'fresh_satisfied_evidence_required')
        assert inspect_project(project)==updated
        record('successful render with wrong width is rejected; approved selections preserved')
        for source,token in [('black','blackMs'),('silent','silenceMs')]:
            failed=prepare('scene-3',source,'reject-'+source);view=run_scene(client,failed);evidence('reject-'+source,view)
            assert view['outcome']=='VIOLATED',view
            reason=json.loads(view['verification']['checks'][0]['detail']['reason'])
            assert token in reason['violations'],reason
            blocked(lambda:adopt_scene(client,project,failed),'fresh_satisfied_evidence_required')
            assert inspect_project(project)==updated
            record(source+' contract violation preserves approved scene',measurements=reason['measurements'])

        drift=prepare('scene-3','replacement','drift');view=run_scene(client,drift)
        assert view['outcome']=='SATISFIED',view
        candidate=Path(validation_detail(view)['artifactPath'])
        with candidate.open('ab') as stream:stream.write(b'after-check-change')
        stale=client.work('inspect',work=drift['work']);evidence('drift',stale)
        assert stale['outcome']=='UNKNOWN' and stale['stale']
        blocked(lambda:adopt_scene(client,project,drift),'fresh_satisfied_evidence_required')
        assert inspect_project(project)==updated
        record('candidate byte change invalidates native evidence; no adoption')

        pending=prepare('scene-3','replacement','stale-project');view=run_scene(client,pending)
        assert view['outcome']=='SATISFIED',view
        before_calls={r['work']:client.work('inspect',work=r['work'])['calls'] for r in client.work('list')['works']}
        restored=select_version(project,'scene-3',initial['scene-3']['version'],expected_manifest=updated['digest'])
        evidence('restored',restored)
        assert restored['selected']==initial
        after_calls={r['work']:client.work('inspect',work=r['work'])['calls'] for r in client.work('list')['works']}
        assert before_calls==after_calls
        blocked(lambda:adopt_scene(client,project,pending),'project_changed_reconcile_before_adoption')
        assert inspect_project(project)==restored
        record('restore selects retained approved scene; no rendering; stale project candidate refused')

        # Simulate a lost submit response after native acceptance. Only read-only
        # list/inspect are available to this reconciliation client.
        recovery=prepare('scene-3','replacement','recover-ticket')
        ticket_file=project/'requests'/'recover-ticket'/'ticket.json'
        ticket_file.rename(ticket_file.with_suffix('.received.json'))
        class ReadOnly:
            def work(self,action,**kw):
                assert action in ['list','inspect'];return client.work(action,**kw)
        assert reconcile_request(ReadOnly(),project,'recover-ticket')==recovery
        assert client.work('inspect',work=recovery['work'])['attempt']==0
        record('lost-response ticket recovered read-only; no resubmission')

        # A model-independent stdio MCP session, not a Claude model/service test.
        launch=client.work_mcp_server()
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'media-extension-test','version':'0.1.0'}}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'work_inspect','arguments':{'work':initial['scene-1']['work']}}},
                  {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'work_step','arguments':{'work':recovery['work']}}}]
        with tempfile.TemporaryFile() as incoming,tempfile.TemporaryFile() as outgoing,tempfile.TemporaryFile() as errors:
            incoming.write((''.join(json.dumps(m)+'\n' for m in messages)).encode());incoming.seek(0)
            process=subprocess.run([launch['command'],*launch['args']],stdin=incoming,stdout=outgoing,stderr=errors,timeout=15)
            outgoing.seek(0);raw=outgoing.read(262145);assert len(raw)<=262144 and process.returncode==0
        replies=[json.loads(line) for line in raw.splitlines()];evidence('mcp',{'responses':replies})
        assert [r['id'] for r in replies]==[1,2,3,4]
        assert {t['name'] for t in replies[1]['result']['tools']}=={'work_list','work_inspect','work_adapters'}
        inspected=replies[2]['result']['structuredContent']
        assert inspected['outcome']=='SATISFIED' and inspected['adoptedValid']
        assert 'error' in replies[3]
        assert client.work('inspect',work=recovery['work'])['attempt']==0
        record('model-independent read-only MCP observes media proof; execution tool refused')

        # Detect an out-of-band write in a separate disposable project copy.
        # This is detection, not an OS sandbox against a same-user process.
        tampered=output/'tampered-project';shutil.copytree(project,tampered)
        approved=Path(inspect_project(tampered)['selected']['scene-1']['path'])
        approved.chmod(0o644)
        with approved.open('ab') as stream:stream.write(b'out-of-band-change')
        unchanged=sha(tampered/'manifest.json')
        blocked(lambda:inspect_project(tampered),'approved_scene_changed')
        blocked(lambda:select_version(tampered,'scene-3',initial['scene-3']['version'],expected_manifest=unchanged),'approved_scene_changed')
        assert sha(tampered/'manifest.json')==unchanged
        record('out-of-band approved-file edit detected; selection change refused')
        if args.workbench:
            other=CalfClient(args.workbench.resolve(strict=True),output/'records',timeout=80)
            report['secondCore']={'version':other.version(),'sha256':other.binary_sha256()}
            for row in client.work('list')['works']:
                left=client.work('inspect',work=row['work']);right=other.work('inspect',work=row['work'])
                for field in ['work','contractDigest','outcome','manifest','verification','adoptedValid']:
                    assert left.get(field)==right.get(field),(row['work'],field)
            record('second native core reads identical media contracts, verdicts and adoption proof')
        report.update(status='PASS',finalProject=inspect_project(project),works=len(client.work('list')['works']))
    except BaseException as error:
        report['failure']=type(error).__name__+': '+str(error)[:2000]
        raise
    finally:
        evidence('report',report)

if __name__=='__main__':main()
