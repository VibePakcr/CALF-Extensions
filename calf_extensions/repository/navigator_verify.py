"""Offline installed navigator checks; all repositories are disposable fixtures."""
import argparse,io,json,os,shutil,unittest
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--git',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();git=a.git.resolve(strict=True)
    if git!=a.git or a.output.exists():raise ValueError('new_output_and_physical_git_required')
    a.output.mkdir(parents=True);os.environ['PATH']=str(git.parent)+os.pathsep+os.defpath
    if Path(shutil.which('git')).resolve()!=git:raise ValueError('selected_git_not_used')
    groups=[('local-contracts',['test_git_contract']),('source-contracts',['test_source_contract']),('hosted-contracts',['test_github_source','test_gitlab_source']),('portal-contracts',['test_navigation_h4','test_portal_h4','test_rendering_h5','test_installed_viewer'])];checks=[]
    for name,modules in groups:
        stream=io.StringIO();suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('calf_extensions.repository.tests.'+m) for m in modules);r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(a.output/(name+'.log')).write_text(stream.getvalue(),encoding='utf8');checks.append({'check':name,'tests':r.testsRun,'passed':r.wasSuccessful() and r.testsRun>0,'skipped':len(r.skipped)})
    report={'status':'PASS' if all(c['passed'] and not c['skipped'] for c in checks) else 'UNKNOWN','checks':checks,'git':str(git),'scope':'offline Git-backed fixtures, not live accounts, browser, core or SDK'};(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return 0 if report['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
