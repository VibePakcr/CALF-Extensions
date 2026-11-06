"""One Claude Code session over Work MCP. Default: readiness only, no model call.

Uses the CLI control message shapes published by the official Claude Agent SDK.
Install CALF SDK separately. No global config edits, dependency install or daemon.
"""
from pathlib import Path
import argparse
import json
import math
import os
import queue
import re
import signal
import subprocess
import tempfile
import threading
import time
from calf_sdk import CalfClient


def run(args):
    for field in ['claude','calf','home','profile','session_dir']:
        path=Path(getattr(args,field))
        if not path.is_absolute():raise ValueError(field+' requires an absolute path')
    executable=Path(args.claude).resolve(strict=True)
    profile=Path(args.profile).resolve(strict=True)
    if not executable.is_file() or not profile.is_dir():raise ValueError('Select an installed CLI and an existing profile')
    if not re.fullmatch(r'work-[0-9a-f]{64}',args.work):raise ValueError('Invalid work ID')
    if not math.isfinite(args.budget_usd) or not 0<args.budget_usd<=.50:raise ValueError('Budget must be positive and at most USD 0.50')
    if not 10<=args.timeout<=180:raise ValueError('Timeout must be 10–180 seconds')
    folder=Path(args.session_dir);folder.mkdir(parents=True,exist_ok=False);folder=folder.resolve(strict=True)
    client=CalfClient(Path(args.calf).resolve(strict=True),args.home,timeout=80)
    before=client.work('inspect',work=args.work)
    if args.execute and (before.get('phase')!='ready' or before.get('attempt')!=0):
        raise ValueError('Execution requires an unexecuted frozen work; reconcile existing attempts first')
    config={'mcpServers':{'calf':client.work_mcp_server(control=args.execute)}}
    env=dict(os.environ,CLAUDE_CONFIG_DIR=str(profile),DISABLE_TELEMETRY='1',DISABLE_ERROR_REPORTING='1',
             DISABLE_AUTOUPDATER='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
    allowed=['mcp__calf__work_inspect']+(['mcp__calf__work_step'] if args.execute else [])
    command=[str(executable),'-p','--input-format','stream-json','--output-format','stream-json','--verbose',
             '--no-session-persistence','--disable-slash-commands','--no-chrome','--setting-sources','',
             '--mcp-config',json.dumps(config),'--strict-mcp-config','--tools','',
             '--permission-mode','dontAsk','--allowedTools',*allowed,'--max-budget-usd',str(args.budget_usd)]
    messages=queue.Queue(maxsize=64);events=[];sequence=0;deadline=time.monotonic()+args.timeout
    with tempfile.TemporaryFile() as errors:
        child=subprocess.Popen(command,cwd=folder,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=errors,text=True,bufsize=1,start_new_session=os.name!='nt')
        def read():
            size=0
            try:
                for line in child.stdout:
                    size+=len(line.encode('utf-8'))
                    if size>1048576 or len(line)>262144:raise ValueError('CLI output limit')
                    messages.put(json.loads(line))
            except Exception as error:messages.put({'transportError':type(error).__name__})
            finally:messages.put({'transportEOF':True})
        reader_thread=threading.Thread(target=read,daemon=True);reader_thread.start()
        def send(value):
            child.stdin.write(json.dumps(value)+'\n');child.stdin.flush()
        def receive():
            if os.fstat(errors.fileno()).st_size>65536:raise ValueError('CLI diagnostic limit')
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Session limit; inspect work before another request')
            value=messages.get(timeout=remaining);events.append(value)
            if value.get('transportEOF') or value.get('transportError'):raise RuntimeError('Claude connection closed')
            if value.get('type')=='control_request':
                send({'type':'control_response','response':{'subtype':'error','request_id':value['request_id'],
                      'error':'Unexpected request; not authorized by this example'}})
            return value
        def control(request):
            nonlocal sequence
            sequence+=1;identity='calf-ready-'+str(sequence)
            send({'type':'control_request','request_id':identity,'request':request})
            while True:
                value=receive();response=value.get('response',{})
                if value.get('type')=='control_response' and response.get('request_id')==identity:
                    if response.get('subtype')!='success':raise RuntimeError('Claude control request failed')
                    return response.get('response',{})
        try:
            control({'subtype':'initialize','hooks':None})
            startup=min(deadline,time.monotonic()+30)
            while time.monotonic()<startup:
                status=control({'subtype':'mcp_status'})
                server=next((s for s in status.get('mcpServers',[]) if s.get('name')=='calf'),None)
                if server and server.get('status')=='connected':break
                if server and server.get('status')=='failed':raise RuntimeError('CALF MCP failed; no model message sent')
                time.sleep(.5)
            else:raise TimeoutError('CALF MCP not ready; no model message sent')
            report={'mcpReady':True,'modelCalled':False,'work':args.work}
            if not args.execute:return report
            prompt=('For frozen synthetic work '+args.work+', call work_inspect, then work_step exactly once for that same ID, '
                    'then work_inspect. Never submit, retry, cancel or adopt. Report the actual check verdict and manifest digest. '
                    'Renderer exit 0 is not a passed check. Do not claim artistic review.')
            send({'type':'user','message':{'role':'user','content':prompt},'parent_tool_use_id':None,'session_id':'default'})
            while True:
                result=receive()
                if result.get('type')=='result':break
            calls=[c for e in events if e.get('type')=='assistant' for c in e.get('message',{}).get('content',[]) if c.get('type')=='tool_use']
            if result.get('is_error') or not calls or any(c['name'] not in allowed or c.get('input',{}).get('work')!=args.work for c in calls):
                raise RuntimeError('Claude did not complete the permitted tool sequence; inspect native work')
            if sum(c['name']=='mcp__calf__work_step' for c in calls)!=1:raise RuntimeError('Expected exactly one work_step')
            current=client.work('inspect',work=args.work)
            report.update(modelCalled=True,outcome=current.get('outcome'),verified=current.get('verified'),
                          manifestDigest=(current.get('manifest') or {}).get('digest'),
                          toolCalls=[c['name'] for c in calls],reportedCostUSD=result.get('total_cost_usd'),adoption='Not requested')
            return report
        finally:
            try:child.stdin.close()
            except (BrokenPipeError,OSError):pass
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name=='nt':child.terminate()
                else:os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            reader_thread.join(timeout=1)
            child.stdout.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['claude','calf','home','profile','session-dir']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--work',required=True)
    parser.add_argument('--execute',action='store_true',help='explicitly authorize one Claude model session and one work_step')
    parser.add_argument('--budget-usd',type=float,default=.35)
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    report=run(args);print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not args.execute or (report.get('verified') and report.get('outcome')=='SATISFIED') else 2

if __name__=='__main__':raise SystemExit(main())
