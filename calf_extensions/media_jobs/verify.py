"""Isolated management acceptance checks; no provider calls or user media."""
import argparse
import json
from pathlib import Path

from calf_sdk import CalfClient
from calf_extensions.media_ffmpeg.common import sha, MediaError
from calf_extensions.media_ffmpeg.project import create_project, inspect_project, select_version
from calf_extensions.media_ffmpeg.verify import fixture
from calf_extensions.media_jobs.manager import (register, prepare, receive, run, adopt,
                                                inspect_job, reconcile, inspect_jobs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['calf','ffmpeg','ffprobe','output']:p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();out=a.output
    if not out.is_absolute():p.error('absolute new output directory required')
    out.mkdir(parents=True,exist_ok=False);out=out.resolve(strict=True)
    report={'status':'FAIL','checks':[], 'providerCalls':0, 'AI':False,
            'limits':['synthetic local media; no external provider/client qualification',
                      'technical checks and byte preservation; human visual review remains required']}
    def record(label,**data):
        report['checks'].append({'check':label,**data});print(label,flush=True)
    def refused(fn,code):
        try:fn()
        except MediaError as e:assert code in str(e),(code,str(e))
        else:raise AssertionError('expected refusal: '+code)
    try:
        client=CalfClient(a.calf,out/'records',timeout=80)
        report['native']=client.version()
        reg=register(client,out/'tools',a.ffmpeg,a.ffprobe)
        project=out/'scenes';create_project(project,['scene-1','scene-2'])
        original=inspect_project(project)
        inputs=out/'inputs';inputs.mkdir()
        good=inputs/'good.mp4';fixture(str(a.ffmpeg),good)
        black=inputs/'black.mp4';fixture(str(a.ffmpeg),black,color='black')
        settings={'width':320,'height':180,'fps':25,'startMs':0,'durationMs':1000,
                  'audio':True,'maxBlackMs':100,'maxSilenceMs':100}
        def request(key,scene='scene-1',**kw):
            return prepare(project,scene,key,'Change the sign; preserve the camera motion.',
                           settings,'Manual external video tool',**kw)
        first=request('first',references=[good])
        assert first==request('first',references=[good])
        assert inspect_job(None,project,'first')['state']=='awaiting_result'
        assert inspect_project(project)==original
        refused(lambda:prepare(project,'scene-1','first','Different instructions',settings,'Manual external video tool',references=[good]),'request_key_conflict')
        record('request handoff is idempotent; changed intent refused; no native or provider submission')
        from calf_extensions.media_jobs.contracts import delivery_profile
        for override in [{'startMs':1},{'width':3842},{'fps':True},{'durationMs':1001},
                         {'audio':False,'maxSilenceMs':100},{'extraFlags':'-y'}]:
            try:delivery_profile({**settings,**override})
            except ValueError:pass
            else:raise AssertionError('invalid delivery contract accepted: '+repr(override))
        record('intake rejects implicit trimming, oversized/ambiguous requirements and extra tool flags')

        ticket=receive(client,project,'first',good,reg)
        assert receive(client,project,'first',good,reg)==ticket
        refused(lambda:receive(client,project,'first',black,reg),'returned_result_conflict')
        before=client.work('inspect',work=ticket['work']);view=run(client,project,'first')
        assert view['outcome']=='SATISFIED',view
        assert run(client,project,'first')['calls']==view['calls']
        assert inspect_job(client,project,'first')['state']=='ready_for_review'
        assert inspect_project(project)==original
        selected=adopt(client,project,'first');old=selected['selected']['scene-1']
        assert sha(old['path'])==sha(good)
        assert inspect_job(client,project,'first')['state']=='selected'
        assert adopt(client,project,'first')==selected
        record('native copy/check/review/adopt uses exact returned bytes; repeated calls do not rerender',work=ticket['work'])

        second=request('second',scene='scene-2');receive(client,project,'second',good,reg)
        assert run(client,project,'second')['outcome']=='SATISFIED'
        baseline=adopt(client,project,'second')
        assert baseline['selected']['scene-1']==old
        revision=request('revision',parent='first')
        assert revision['parent']=='first'
        assert revision['baseVersion']==old['version']
        assert revision['references'][0]['sha256']==sha(good)
        receive(client,project,'revision',good,reg);assert run(client,project,'revision')['outcome']=='SATISFIED'
        updated=adopt(client,project,'revision')
        assert updated['selected']['scene-2']==baseline['selected']['scene-2']
        assert sha(old['path'])==sha(good)
        restored=select_version(project,'scene-1',old['version'],expected_manifest=updated['digest'])
        assert restored['selected']['scene-1']==old
        assert inspect_job(client,project,'revision')['state']=='retained_version'
        record('revision links previous job/result and current base; only target scene changes; restoration retains old bytes')

        request('bad');receive(client,project,'bad',black,reg)
        assert run(client,project,'bad')['outcome']=='VIOLATED'
        refused(lambda:adopt(client,project,'bad'),'fresh_satisfied_evidence_required')
        assert inspect_job(client,project,'bad')['state']=='needs_attention'
        assert inspect_project(project)==restored
        record('returned black video fails existing technical criterion and cannot replace approved scene')

        request('late');receive(client,project,'late',good,reg)
        assert run(client,project,'late')['outcome']=='SATISFIED'
        request('newer');receive(client,project,'newer',good,reg);run(client,project,'newer');latest=adopt(client,project,'newer')
        assert inspect_job(client,project,'late')['projectChanged']
        refused(lambda:adopt(client,project,'late'),'project_changed_reconcile_before_adoption')
        assert inspect_project(project)==latest
        record('late return is retained; changed project prevents stale adoption')

        request('lost')
        class LostResponse:
            def work(self,action,**kw):
                value=client.work(action,**kw)
                if action=='submit':raise OSError('simulated response loss AFTER real native submit')
                return value
        try:receive(LostResponse(),project,'lost',good,reg)
        except OSError:pass
        else:raise AssertionError('lost response not exercised')
        count=len(client.work('list')['works'])
        refused(lambda:receive(client,project,'lost',good,reg),'submission_uncertain_reconcile')
        recovered=reconcile(client,project,'lost')
        assert recovered==receive(client,project,'lost',good,reg)
        assert len(client.work('list')['works'])==count
        assert run(client,project,'lost')['outcome']=='SATISFIED'
        record('lost submit response recovers same native work by read-only reconciliation; no new submission')

        # A full-HD result must remain byte-for-byte identical: no scaler/encoder.
        hd=inputs/'hd.mp4'
        from calf_extensions.media_ffmpeg.common import run_tool
        run_tool([str(a.ffmpeg),'-hide_banner','-nostdin','-v','error','-n','-filter_threads','1',
                  '-f','lavfi','-i','testsrc2=size=1920x1080:rate=25','-t','1',
                  '-an','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',str(hd)])
        hd_settings={**settings,'width':1920,'height':1080,'audio':False,'maxSilenceMs':None}
        prepare(project,'scene-1','hd','Review full-HD return',hd_settings,'Manual external video tool')
        hd_ticket=receive(client,project,'hd',hd,reg);v=run(client,project,'hd');assert v['outcome']=='SATISFIED',v
        result=adopt(client,project,'hd');assert sha(result['selected']['scene-1']['path'])==sha(hd)
        assert result['selected']['scene-2']==baseline['selected']['scene-2']
        record('1920x1080 return is independently decoded/checked and adopted with identical file hash',sourceSha256=sha(hd),work=hd_ticket['work'])

        # Later edits of a saved return must be detected before further action.
        request('tamper');t=receive(client,project,'tamper',good,reg)
        path=project/'handoffs/tamper/returned.mp4';path.chmod(0o644)
        with path.open('ab') as f:f.write(b'changed')
        refused(lambda:inspect_job(client,project,'tamper'),'returned_snapshot_changed')
        assert inspect_project(project)==result
        record('changed intake snapshot is detected; selected media is unchanged')
        board=inspect_jobs(None,project)
        assert len(board['jobs'])==9
        assert all('request' not in row for row in board['jobs'])
        assert next(row for row in board['jobs'] if row['key']=='tamper')['state']=='unresolved'
        assert 'verification' not in inspect_job(client,project,'hd')['native']
        record('list polling omits full prompts/receipts/logs; one corrupt job remains visibly unresolved')
        report['status']='PASS'
    finally:
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
