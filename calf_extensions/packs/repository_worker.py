"""Retained worker for one explicit Local Git binding; no service or hosted calls."""
import hashlib
import json
from pathlib import Path
import sys

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(32768),b''):h.update(b)
    return h.hexdigest()

def main():
    root=Path(sys.argv[1]);request=Path(sys.argv[2]);action=sys.argv[3];value=json.loads(request.read_bytes());folder=request.parent
    sys.path.insert(0,str(root))
    from calf_extensions.repository.export import export_capture
    if action=='export':
        receipt=json.loads((folder/'receipt.json').read_bytes())
        result=export_capture(value['data'],receipt['capture'],Path(sys.argv[4]),sys.argv[5]=='include-source');print(json.dumps(result));return
    from calf_extensions.repository.viewer import Project
    lock=json.loads((Path(value['store'])/'locks'/(value['lock']+'.json')).read_bytes())
    project=Project(Path(value['repo']),Path(value['data']),lock['compatibility']['environment']['git'])
    graph=project.refresh();cid=project.capture['capture_id'];data=Path(value['data'])
    sources=sorted({r['sha256'] for r in graph['source_captures'].values() if r.get('sha256') and (data/'sources'/r['sha256']).is_file()})
    receipt={'schema':'calf.repository.receipt.v1','requestSha256':sha(request),'capture':cid,'navigationSha256':sha(data/'navigation'/(cid+'.json')),
             'sourceDigests':sources,'coverage':project.capture['coverage'],'navigationCoverage':graph['coverage'],
             'status':'COMPLETE' if project.capture['coverage']['state']=='COMPLETE' else 'PARTIAL'}
    with (folder/'receipt.json').open('x',encoding='utf8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n');f.flush()
    print(json.dumps({'capture':cid,'status':receipt['status']}))

if __name__=='__main__':main()
