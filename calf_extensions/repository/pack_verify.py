"""Run retained local-reader acceptance tests in disposable repositories only."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import unittest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--git',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    selected=a.git.resolve(strict=True)
    if a.git!=selected or a.output.exists():raise ValueError('new_output_and_physical_git_required')
    a.output.mkdir(parents=True);os.environ['PATH']=str(selected.parent)+os.pathsep+os.defpath
    if Path(shutil.which('git')).resolve()!=selected:raise ValueError('selected_git_not_used')
    groups=[('git-contracts','test_git_contract'),('navigation-contracts','test_navigation'),('limits-contracts','test_limits')]
    checks=[]
    for name,module in groups:
        stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName('calf_extensions.repository.tests.'+module)
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (a.output/(name+'.log')).write_text(stream.getvalue(),encoding='utf8')
        checks.append({'check':name,'tests':result.testsRun,'passed':result.wasSuccessful() and result.testsRun>0,'skipped':len(result.skipped)})
    report={'status':'PASS' if all(c['passed'] and not c['skipped'] for c in checks) else 'UNKNOWN','checks':checks,'git':str(selected),'scope':'disposable local repositories; no model, SDK, native core, hosted API or browser'}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report));return 0 if report['status']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
