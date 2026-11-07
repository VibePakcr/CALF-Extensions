"""Exercise pack installation/update/recovery in a new local synthetic workspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from .io import PackError,physical,sha,read,atomic,canonical,run
from .store import PackStore
from .repository import request,invoke,inspect,PACK_ID

def alive(pid):
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            if ctypes.get_last_error() in (87,1168):return False
            raise AssertionError('Cannot query owned child')
        try:
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise AssertionError('Cannot read owned child exit')
            return code.value==259
        finally:kernel.CloseHandle(handle)
    result=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True)
    return bool(result.stdout.strip()) and not result.stdout.lstrip().startswith('Z')

def verify(output,base,base_sha,next_archive,next_sha,python,git):
    output=Path(output)
    if not output.is_absolute() or output.exists():raise PackError('new_verification_folder_required')
    python=physical(python);git=physical(git);base=physical(base);next_archive=physical(next_archive)
    if sha(base)!=base_sha or sha(next_archive)!=next_sha:raise PackError('verification_archive_identity')
    output.mkdir(parents=True);checks=[];qualifications=[]
    report={'status':'INCOMPLETE','platform':sys.platform,'machine':platform.machine(),'python':platform.python_version(),
            'git':subprocess.check_output([str(git),'--version'],text=True).strip(),'checks':checks,'qualifications':qualifications,
            'archives':{'base':base_sha,'next':next_sha},'existingRecordsOrHostSettingsWritten':False,'modelCalls':0}
    def record(name,**details):
        checks.append({'check':name,**details});(output/'progress.json').write_bytes(canonical({'lastCheck':name,'passed':len(checks)})+b'\n')
    def files(folder):return {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file() and not p.is_symlink()}
    try:
        # Run manager contracts separately from the candidate's domain checks.
        import io
        stream=io.StringIO();suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ['calf_extensions.packs.tests.test_lifecycle','calf_extensions.packs.tests.test_repository'])
        tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (output/'manager-tests.log').write_text(stream.getvalue(),encoding='utf8')
        if not tested.wasSuccessful() or tested.testsRun!=20 or tested.skipped:raise PackError('manager_contract_tests_incomplete')
        record('manager-contracts',tests=tested.testsRun,skipped=0)
        # Exercise the manager's own timeout boundary, not just the Git reader.
        import time
        fixture=output/'manager_process.py';pidfile=output/'manager-owned-pids.json'
        fixture.write_text('import json,os,subprocess,sys,time\nfrom pathlib import Path\nif sys.argv[1]=="output":print("x"*100000)\nelse:\n child=subprocess.Popen([sys.executable,"-I","-S","-B","-c","import time;time.sleep(60)"])\n Path(sys.argv[1]).write_text(json.dumps({"parent":os.getpid(),"child":child.pid}))\n time.sleep(60)\n',encoding='utf8')
        try:
            try:run([python,'-I','-S','-B',fixture,'output'],limit=1024);raise AssertionError('output bound ignored')
            except PackError as error:
                if str(error)!='tool_output_limit':raise
            try:run([python,'-I','-S','-B',fixture,pidfile],timeout=1);raise AssertionError('timeout ignored')
            except PackError as error:
                if str(error)!='tool_timeout_reconcile_before_retry':raise
            pids=json.loads(pidfile.read_text())
            for _ in range(20):
                if not any(alive(pid) for pid in pids.values()):break
                time.sleep(.05)
            if any(alive(pid) for pid in pids.values()):raise PackError('manager_owned_process_not_reaped')
        finally:
            if pidfile.exists():
                for pid in json.loads(pidfile.read_text()).values():
                    if alive(pid):
                        if os.name=='nt':subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,timeout=5)
                        else:
                            import signal
                            os.kill(pid,signal.SIGKILL)
        record('manager-output-limit-and-timeout-owned-tree-cleanup')
        store=PackStore.create(output/'store');env={'python':str(python),'git':str(git)};locks=[];versions=[]
        for archive,expected in [(base,base_sha),(next_archive,next_sha)]:
            staged=store.stage(archive,expected,'explicit-reviewed-verification-candidate');versions.append(staged['version'])
            if store.stage(archive,expected,'same-candidate')!=staged:raise PackError('stage_not_idempotent')
            observed=store.check(PACK_ID,staged['version'],'inspect',env)
            if observed['status']!='COMPATIBLE' or observed['coreStatus']!='NOT_REQUIRED':raise PackError('standalone_compatibility_not_established')
            qualified=store.qualify(PACK_ID,staged['version'],'inspect',env);locks.append(qualified['lock'])
            lock=store.load_lock(qualified['lock']);receipt=read(store.root/'operations'/lock['qualification']/'result.json');domain=read(receipt['reportPath'])
            if [(r['check'],r['tests'],r['skipped']) for r in domain['checks']]!=[('git-contracts',8,0),('navigation-contracts',11,0),('limits-contracts',1,0)]:raise PackError('domain_checks_incomplete')
            qualifications.append({'version':staged['version'],'tests':20,'skipped':0,'lock':qualified['lock'],'reportSha256':sha(receipt['reportPath'])})
        record('two-versions-stage-and-qualify',versions=versions)
        old=store.activate(locks[0],'none',experimental=True);record('first-install')
        repo=output/'project';repo.mkdir();git_env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        git_env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_AUTHOR_NAME='Fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',GIT_COMMITTER_NAME='Fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid')
        def g(*args):return subprocess.check_output([str(git),'-c','commit.gpgsign=false','-c','core.hooksPath='+os.devnull,*args],cwd=repo,env=git_env,stderr=subprocess.PIPE)
        g('init','-q','-b','main');(repo/'한글.py').write_text('def greeting():\n    return "서울 東京 München"\n',encoding='utf8');(repo/'README.md').write_text('# Fixture\n',encoding='utf8');g('add','--','한글.py','README.md');g('commit','-qm','fixture');(repo/'untracked.txt').write_bytes(b'original untracked bytes\n')
        original=files(repo);data=output/'captures';data.mkdir();first=request(store,repo=repo,data=data)
        new=store.activate(locks[1],old['digest'],experimental=True)
        result=invoke(Path(first['binding']),'run')
        if result['status']!='COMPLETE' or result['packVersion']!=versions[0] or result['sameActivePack']:raise PackError('pending_binding_version_changed')
        if files(repo)!=original:raise PackError('source_repository_changed')
        record('pending-work-pinned-across-update')
        retained=files(data);again=invoke(Path(first['binding']),'run')
        if result!=again or files(data)!=retained:raise PackError('repeat_binding_rescanned')
        second=request(store,repo=repo,data=data);next_result=invoke(Path(second['binding']),'run')
        if next_result['packVersion']!=versions[1]:raise PackError('new_binding_not_updated')
        store.activate(locks[0],new['digest'],experimental=True)
        after=inspect(Path(second['binding']))
        if after['receiptSha256']!=next_result['receiptSha256'] or after['sameActivePack']:raise PackError('rollback_changed_existing_work')
        record('repeat-and-rollback-preserve-receipts')
        active=store.active(PACK_ID)
        try:store.activate(locks[1],'none',experimental=True);raise AssertionError('stale activation accepted')
        except PackError as error:
            if str(error)!='active_version_changed':raise
        if store.active(PACK_ID)!=active:raise PackError('cas_changed_pointer')
        record('stale-active-pointer-refused')
        # The original repository is deliberately unavailable for this export.
        repo.rename(output/'source-offline');retained=files(data);export=output/'offline-map';invoke(Path(first['binding']),'export',export,True)
        page=(export/'START_HERE.html').read_text('utf8');offset=page.index('window.CALF_PORTAL=')+len('window.CALF_PORTAL=');boot,_=json.JSONDecoder().raw_decode(page,offset)
        if not any('서울 東京 München' in v.get('text','') for v in boot['sources'].values()) or str(repo) in json.dumps(boot,ensure_ascii=False):raise PackError('offline_cjk_or_path_identity')
        if files(data)!=retained:raise PackError('export_changed_capture')
        record('offline-export-cjk-without-source-access')
        # Terminate real processes around the actual durable pointer/metadata writes.
        crash='''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from calf_extensions.packs import store as m
old=m.atomic
def atomic(path,*args,**kw):
 if sys.argv[6]=='stage' and Path(path).name=='install.json':os._exit(67)
 if sys.argv[6]=='activate' and Path(path).parent.name=='active':
  if sys.argv[5]=='after':old(path,*args,**kw)
  os._exit(67)
 return old(path,*args,**kw)
m.atomic=atomic
s=m.PackStore(Path(sys.argv[2]))
if sys.argv[6]=='stage':s.stage(Path(sys.argv[3]),sys.argv[4],'process-crash-fixture')
else:s.activate(sys.argv[3],sys.argv[4],experimental=True)
'''
        source=str(Path(__file__).resolve().parents[2])
        for side,expected in [('before','NOT_APPLIED'),('after','COMMITTED_UNACKNOWLEDGED')]:
            active=store.active(PACK_ID);target=locks[1] if active['value']['lock']==locks[0] else locks[0]
            p=subprocess.run([str(python),'-I','-S','-B','-X','utf8','-c',crash,source,str(store.root),target,active['digest'],side,'activate'],capture_output=True,timeout=30)
            if p.returncode!=67:raise PackError('activation_crash_not_observed')
            pending=store.recover()['pending']
            if len(pending)!=1 or pending[0]['status']!=expected:raise PackError('activation_crash_state_mismatch')
            before=files(data);store.recover(acknowledge=pending[0]['operation'])
            if files(data)!=before:raise PackError('recovery_changed_captures')
        record('actual-activation-crashes-before-and-after-replacement')
        separate=PackStore.create(output/'stage-recovery')
        p=subprocess.run([str(python),'-I','-S','-B','-X','utf8','-c',crash,source,str(separate.root),str(base),base_sha,'before','stage'],capture_output=True,timeout=30)
        if p.returncode!=67:raise PackError('stage_crash_not_observed')
        pending=separate.recover()['pending']
        if len(pending)!=1 or pending[0]['status']!='RESUMABLE_STAGE':raise PackError('stage_recovery_state')
        separate.recover(acknowledge=pending[0]['operation']);separate.package(PACK_ID,versions[0]);record('actual-stage-crash-and-metadata-recovery')
        incomplete=request(store,repo=output/'source-offline',data=data);binding=Path(incomplete['binding']);atomic(binding.parent/'started.json',{'test':'lost receipt simulation'},new=True)
        if inspect(binding)['status']!='UNKNOWN':raise PackError('missing_receipt_not_unknown')
        try:invoke(binding,'run');raise AssertionError('uncertain work resubmitted')
        except PackError as error:
            if str(error)!='repository_attempt_unresolved_inspect_before_retry':raise
        record('missing-receipt-remains-unknown-without-resubmission',simulation=True)
        altered=request(store,repo=output/'source-offline',data=data);binding=Path(altered['binding']);(binding.parent/'worker.py').write_bytes(b'# deliberate synthetic corruption')
        try:inspect(binding);raise AssertionError('altered worker accepted')
        except PackError as error:
            if str(error)!='repository_worker_changed':raise
        if files(output/'source-offline')!=original:raise PackError('source_bytes_changed')
        record('altered-worker-refused-and-source-preserved')
        report.update(status='PASS',packVersions=versions,sourceFilesPreserved=True,expectedUnknownTestBindingsRetained=2)
    except BaseException as error:
        report.update(status='FAIL',firstError={'type':type(error).__name__,'message':str(error)[:1200]})
        (output/'report.json').write_bytes(canonical(report)+b'\n');raise
    (output/'report.json').write_bytes(canonical(report)+b'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output','base','next','python','git']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['base-sha256','next-sha256']:p.add_argument('--'+name,required=True)
    a=p.parse_args()
    try:result=verify(a.output,a.base,a.base_sha256,a.next,a.next_sha256,a.python,a.git);print(json.dumps(result,ensure_ascii=True));return 0
    except (OSError,ValueError,AssertionError,subprocess.SubprocessError) as error:print(json.dumps({'status':'FAIL','error':type(error).__name__,'message':str(error)[:500]},ensure_ascii=True),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
