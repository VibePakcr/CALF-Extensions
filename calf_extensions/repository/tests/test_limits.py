import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from calf_extensions.repository.git_reader import GitReader
from calf_extensions.repository.model import RepositoryError

class Limits(unittest.TestCase):
    def test_output_limit_and_owned_process_timeout(self):
        if os.name=='nt':self.skipTest('POSIX executable fixture; Windows executable lifecycle is qualified separately')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);binary=root/'git-fixture'
            binary.write_text('#!'+sys.executable+'\nimport sys,time,subprocess\nif "--version" in sys.argv: print("git version 2.54.0")\nelif "-s" in sys.argv: print("X"*100000)\nelse:\n child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\n open('+repr(str(root/'child.pid'))+',"w").write(str(child.pid))\n time.sleep(60)\n')
            binary.chmod(0o700);reader=GitReader(root,binary,timeout=5,output_limit=1024);reader.timeout=1
            with self.assertRaises(RepositoryError) as error:reader._read(['cat-file','-s','0'*40])
            self.assertEqual(error.exception.code,'GIT_OUTPUT_LIMIT')
            start=time.monotonic()
            with self.assertRaises(RepositoryError) as error:reader._read(['cat-file','blob','0'*40])
            self.assertEqual(error.exception.code,'GIT_TIMEOUT');self.assertLess(time.monotonic()-start,5)
            pid=int((root/'child.pid').read_text());time.sleep(.05)
            # A killed child can briefly remain a zombie pending its OS parent reaper.
            result=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True)
            self.assertTrue(not result.stdout.strip() or result.stdout.lstrip().startswith('Z'))
