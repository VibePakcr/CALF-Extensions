"""Real local lifecycle qualification in a NEW folder; no model/network/user media."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
from .io import PackError,canonical,read,sha,run
from .store import PackStore
from .build_ffmpeg import build
from .ffmpeg import request,invoke
from .tests.test_lifecycle import ContractTests

def qualify(source,output,environment):
    source=Path(source).resolve(strict=True);output=Path(output)
    if not output.is_absolute() or output.exists():raise PackError('new_qualification_folder_required')
    output.mkdir(parents=True);output=output.resolve(strict=True)
    report={'schema':'calf.pack.qualification.v1','status':'FAIL','checks':[],'modelCalls':0,'network':False}
    def record(name,**extra):report['checks'].append({'check':name,**extra});print(name,flush=True)
    def block(call):
        try:call()
        except (OSError,PackError):return
        raise AssertionError('expected refusal')
    try:
        ContractTests.source=source
        result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
        if not result.wasSuccessful():raise PackError('lifecycle_contract_tests_failed')
        record('metadata/archive/install-recovery contracts',tests=result.testsRun)
        store=PackStore.create(output/'store');built=[];qualified=[]
        for revision in (2,3):
            b=build(source,output/('build-'+str(revision)),'0.1.1-dev.'+str(revision));built.append(b)
            store.stage(b['archive'],b['sha256'],'owner-local-source-qualification')
            q=store.qualify(b['id'],b['version'],'scenes',environment);qualified.append(q)
            record('fresh candidate installation checks',version=b['version'],checks=q['checks'],lock=q['lock'])
        lock1=store.load_lock(qualified[0]['lock']);lock2=store.load_lock(qualified[1]['lock'])
        active1=store.activate(qualified[0]['lock'],'none',experimental=True)
        domain=output/'資料 한글';domain.mkdir();records=output/'r';records.mkdir();project=domain/'project';media=domain/'source.mp4'
        script='import sys,json;sys.path[:0]=[sys.argv[1],sys.argv[2]];from pathlib import Path;from calf_extensions.media_ffmpeg.verify import fixture;from calf_extensions.media_ffmpeg.project import create_project;fixture(sys.argv[3],Path(sys.argv[4]));create_project(sys.argv[5],["scene-1","scene-2","scene-3"])'
        run([environment['python'],'-I','-S','-B','-X','utf8','-c',script,lock1['packRoot'],environment['sdk'],environment['ffmpeg'],str(media),str(project)])
        profile=read(Path(lock1['packRoot'])/'calf_extensions/media_ffmpeg/profile.json')
        bindings=[]
        def prepare(scene,key):
            value=request(store,records=records,project=project,scene=scene,source=media,key=key,profile=profile)
            bindings.append(value);return Path(value['binding']),value['result']
        def satisfied(binding):
            view=invoke(binding,'run');assert view['verified'] and view['outcome']=='SATISFIED' and view['attempt']==1
            return view
        def inspect_project():
            code='import sys,json;sys.path[:0]=[sys.argv[1],sys.argv[2]];from calf_extensions.media_ffmpeg.project import inspect_project;print(json.dumps(inspect_project(sys.argv[3])))'
            return json.loads(run([environment['python'],'-I','-S','-B','-X','utf8','-c',code,lock1['packRoot'],environment['sdk'],str(project)]))
        for i in (1,2,3):
            binding,ticket=prepare('scene-'+str(i),'initial-'+str(i));satisfied(binding);invoke(binding,'adopt')
        original=inspect_project();before={k:v for k,v in original['selected'].items()}
        old_binding,old_ticket=prepare('scene-3','prepared-before-update')
        old_ready=invoke(old_binding,'inspect');assert old_ready['attempt']==0 and old_ready['phase']=='ready'
        record('three approved scenes and old work frozen before update',work=old_ticket['work'],contractDigest=old_ticket['contractDigest'])
        block(lambda:store.activate(qualified[1]['lock'],'none',experimental=True))
        block(lambda:store.activate(qualified[1]['lock'],active1['digest']))
        active2=store.activate(qualified[1]['lock'],active1['digest'],experimental=True)
        after=satisfied(old_binding);assert after['contractDigest']==old_ticket['contractDigest'];invoke(old_binding,'adopt')
        assert read(Path(read(old_binding)['lockFile']))['version']==built[0]['version']
        assert invoke(old_binding,'run')['attempt']==1
        current=inspect_project();assert all(current['selected'][k]==before[k] for k in ('scene-1','scene-2'))
        assert Path(before['scene-3']['path']).is_file() and sha(before['scene-3']['path'])==before['scene-3']['sha256']
        record('update preserves old binding, contract, attempts and approved other scenes',oldWork=after['work'],attempt=after['attempt'])
        new_binding,new_ticket=prepare('scene-3','prepared-after-update')
        assert read(Path(read(new_binding)['lockFile']))['version']==built[1]['version']
        back=store.activate(qualified[0]['lock'],active2['digest'],experimental=True)
        newer=satisfied(new_binding);invoke(new_binding,'adopt');assert newer['contractDigest']==new_ticket['contractDigest']
        record('rollback affects future selection only; newer pending work still completes',work=newer['work'])
        # Actual process interruption, both sides of the active-pointer commit.
        for point,exitcode,wanted,target in [('after',86,'COMMITTED_UNACKNOWLEDGED',qualified[1]['lock']),('before',85,'NOT_APPLIED',qualified[0]['lock'])]:
            active=store.active('calf.media.ffmpeg')
            crash='''import os,sys
sys.path.insert(0,sys.argv[1])
from calf_extensions.packs import store as module
original=module.atomic
def injected(path,*args,**kwargs):
    if path.parent.name=='active' and sys.argv[5]=='before':os._exit(85)
    result=original(path,*args,**kwargs)
    if path.parent.name=='active' and sys.argv[5]=='after':os._exit(86)
    return result
module.atomic=injected
module.PackStore(sys.argv[2]).activate(sys.argv[3],sys.argv[4],experimental=True)
'''
            try:run([str(Path(sys.executable).resolve()),'-I','-S','-B','-X','utf8','-c',crash,str(source),str(store.root),target,active['digest'],point])
            except PackError as e:assert 'tool_failed:'+str(exitcode) in str(e)
            else:raise AssertionError('crash was not injected')
            row=next(r for r in store.recover()['pending'] if r['status']==wanted)
            store.recover(acknowledge=row['operation'])
            record('interrupted activation reconciled '+point+' pointer replacement',status=wanted,operation=row['operation'])
        active=store.active('calf.media.ffmpeg');store.activate(qualified[0]['lock'],active['digest'],experimental=True)
        block(lambda:store.activate(qualified[0]['lock'],'stale-pointer',experimental=True))
        record('stale compare-and-swap refused; original version remains usable')
        # A changed binding input is also a native registered-file identity change.
        bad_binding,bad_ticket=prepare('scene-3','binding-drift-negative')
        frozen=read(bad_binding.parent/'request.json');frozen['scene']='scene-2'
        (bad_binding.parent/'request.json').write_bytes(canonical(frozen)+b'\n')
        block(lambda:satisfied(bad_binding))
        # Inspect via public native API independently of the manager gateway.
        code='import sys,json;sys.path.insert(0,sys.argv[1]);from calf_sdk import CalfClient;print(json.dumps(CalfClient(sys.argv[2],sys.argv[3]).work("inspect",work=sys.argv[4])))'
        native=json.loads(run([environment['python'],'-I','-S','-B','-X','utf8','-c',code,environment['sdk'],environment['calf'],str(records),bad_ticket['work']]))
        assert not (native.get('verified') and native.get('outcome')=='SATISFIED')
        assert all(inspect_project()['selected'][k]==before[k] for k in ('scene-1','scene-2'))
        record('native registered-file guard rejects binding drift',outcome=native.get('outcome'),attempt=native.get('attempt'))
        # Selected-only metadata loading and missing dependency/core cases.
        missing=copy.deepcopy(environment);missing['ffmpeg']=str(output/'absent-tool')
        assert store.check(built[0]['id'],built[0]['version'],'scenes',missing)['status']!='COMPATIBLE'
        wrong=copy.deepcopy(environment);wrong['edition']='workbench' if environment['edition']=='harness' else 'harness'
        assert store.check(built[0]['id'],built[0]['version'],'scenes',wrong)['status']!='COMPATIBLE'
        assert not {'calf_sdk','numpy','cv2'}&set(sys.modules)
        record('missing dependency/wrong edition refused; host imports no SDK or CV modules')
        report.update(status='PASS',platform=lock1['compatibility']['platform'],store=str(store.root),
            active=store.active('calf.media.ffmpeg'),qualified=qualified,built=built,
            nativeBindingDrift={'outcome':native.get('outcome'),'verified':native.get('verified'),'attempt':native.get('attempt')},
            limitations=['Synthetic technical media only; no artistic/production-footage claim',
                'Explicit trusted local artifacts; hashes do not create an OS sandbox',
                'No registry download, automatic migration/uninstall, Workbench pack UI or general dependency solver',
                'Interrupted native work still uses native inspect/reconcile; manager recovery does not clear reservations'])
    except BaseException as error:
        report['failure']=type(error).__name__+':'+str(error)[:1200];raise
    finally:(output/'report.json').write_bytes(canonical(report)+b'\n')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--environment',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(qualify(a.source,a.output,read(a.environment)),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
