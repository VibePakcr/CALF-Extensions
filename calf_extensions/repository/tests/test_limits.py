"""Same bounded process contract on Windows and POSIX, using installed Python."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from calf_extensions.repository import git_reader
from calf_extensions.repository.git_reader import GitReader
from calf_extensions.repository.model import RepositoryError

def alive(pid):
    if os.name=='nt':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            error=ctypes.get_last_error()
            if error in (87,1168):return False
            raise AssertionError('Cannot confirm owned process state: '+str(error))
        try:
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise AssertionError('Cannot read owned process exit')
            return code.value==259
        finally:kernel.CloseHandle(handle)
    result=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True)
    return bool(result.stdout.strip()) and not result.stdout.lstrip().startswith('Z')

class Limits(unittest.TestCase):
    def test_output_limit_and_owned_process_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();script=root/'process_fixture.py';pidfile=root/'owned-pids.json'
            script.write_text('''import json,os,subprocess,sys,time
from pathlib import Path
if "-s" in sys.argv:
    print("X"*100000)
else:
    child=subprocess.Popen([sys.executable,"-I","-S","-B","-c","import time;time.sleep(60)"])
    Path(os.environ["CALF_LIMIT_PID_FILE"]).write_text(json.dumps({"parent":os.getpid(),"child":child.pid}))
    time.sleep(60)
''',encoding='utf8')
            # Real Git supplies the version probe; only the process fixture argv
            # is substituted. Separate Git contract tests cover fixed Git flags.
            reader=GitReader(root);reader.executable=Path(sys.executable).resolve();reader.output_limit=1024
            reader.env['CALF_LIMIT_PID_FILE']=str(pidfile)
            try:
                with patch.object(git_reader,'FLAGS',['-I','-S','-B',str(script)]):
                    with self.assertRaises(RepositoryError) as error:reader._read(['cat-file','-s','0'*40])
                    self.assertEqual(error.exception.code,'GIT_OUTPUT_LIMIT')
                    reader.timeout=1;start=time.monotonic()
                    with self.assertRaises(RepositoryError) as error:reader._read(['cat-file','blob','0'*40])
                    self.assertEqual(error.exception.code,'GIT_TIMEOUT');self.assertLess(time.monotonic()-start,8 if os.name=='nt' else 5)
                pids=json.loads(pidfile.read_text())
                for _ in range(20):
                    if not any(alive(pid) for pid in pids.values()):break
                    time.sleep(.05)
                self.assertFalse(any(alive(pid) for pid in pids.values()),'Owned parent/child still running')
            finally:
                if pidfile.exists():
                    for pid in json.loads(pidfile.read_text()).values():
                        if alive(pid):
                            if os.name=='nt':subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,timeout=5)
                            else:os.kill(pid,signal.SIGKILL)

if __name__=='__main__':unittest.main()
