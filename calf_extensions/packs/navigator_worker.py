"""Installed foreground worker; stdin-only inputs and workspace-owned lifetime lock."""
from contextlib import contextmanager
import hashlib,json,os
from pathlib import Path
import signal,sys

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def result(path,value):
    raw=json.dumps(value,ensure_ascii=True,allow_nan=False).encode();tmp=path.with_suffix('.tmp')
    with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
@contextmanager
def workspace_lock(root):
    path=root/'.navigator-session.lock'
    if path.is_symlink():raise ValueError('workspace_lock_refused')
    with path.open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            if f.seek(0,2)==0:f.write(b'0');f.flush()
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def main():
    root=Path(sys.argv[1]);request_path=Path(sys.argv[2]);run=Path(sys.argv[3]);request=json.loads(request_path.read_bytes());request_sha=sha(request_path);code=1;status='FAILED'
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError('navigator_input_limit')
        packet=json.loads(raw);args=packet['arguments'];references=packet['credentialReferences'];intent=json.loads((run/'intent.json').read_bytes())
        canonical=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
        if hashlib.sha256(canonical(args)).hexdigest()!=intent['argumentsSha256'] or intent['requestSha256']!=request_sha:raise ValueError('navigator_intent_changed')
        for name,value in references.items():os.environ[name]=value
        lock=json.loads((Path(request['store'])/'locks'/(request['lock']+'.json')).read_bytes());git=lock['compatibility']['environment']['git'];command=args[0]
        extra=[] if command=='--help' else ['--data-dir',request['data']]
        if command in {'open','scan','probe'}:
            if not any(v in {'--source','--view','--sources'} or v.startswith(('--source=','--view=')) for v in args):
                if request['repo']:extra+=['--repo',request['repo']]
                elif command=='open':extra+=['--sources']
            if command in {'open','scan','probe'}:extra+=['--git',git]
            if command in {'open','scan'} and request['projectMapSha256']:extra+=['--project-map',str(request_path.parent/'project-map.json')]
        sys.path.insert(0,str(root));from calf_extensions.repository.cli import main as cli
        if hasattr(signal,'SIGBREAK'):signal.signal(signal.SIGBREAK,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
        installation={'id':lock['id'],'version':lock['version'],'lock':request['lock']}
        sys.argv=['calf-repo',*args,*extra]
        with workspace_lock(Path(request['data'])):code=cli(installation=installation,manual_root=request['manualRoot'])
        status='EXITED' if code==0 else 'PARTIAL' if code==3 else 'INTERRUPTED' if code==130 else 'FAILED'
    except SystemExit as error:code=error.code if isinstance(error.code,int) else 1;status='EXITED' if code==0 else 'FAILED'
    except KeyboardInterrupt:code=130;status='INTERRUPTED'
    except Exception:sys.stderr.write('Installed navigator could not complete; inspect the retained launch.\n')
    finally:
        for name in locals().get('references',{}):os.environ.pop(name,None)
        result(run/'result.json',{'schema':'calf.navigator.exit.v1','requestSha256':request_sha,'exitCode':code,'status':status})
    return code
if __name__=='__main__':raise SystemExit(main())
