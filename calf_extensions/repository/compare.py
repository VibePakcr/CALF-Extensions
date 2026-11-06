"""Exact source versions and textual comparisons, never Git worktree conversions."""
import difflib
import os
from .capture import stable_read
from .model import RepositoryError, classify, now, oid, path_bytes


def source(reader,store,capture,path_id,version,commit=None):
    rawpath=path_bytes(path_id);record=next((f for f in capture['files'] if f['id']==path_id),None)
    identity={'path_id':path_id,'version':version,'commit':commit,'captured_at':now()};entry=None
    if version=='commit':
        commit=oid(commit);identity['commit']=commit;entry=next((x for x in reader.tree(commit) if x['id']==path_id),None)
    elif record is None:raise RepositoryError('PATH_NOT_REGISTERED','Path is outside the capture')
    elif version=='head':entry=record['head'];identity['commit']=capture['repository']['head']
    elif version in ['index','stage1','stage2','stage3']:entry=record['index'].get('0' if version=='index' else version[-1])
    elif version!='working':raise RepositoryError('INVALID_VERSION','Unknown source version')
    if version=='index' and record and any(stage!='0' for stage in record['index']):
        return dict(identity,kind='conflict',text=None,sha256=None,stages=sorted(record['index']))
    if version=='working':
        data,kind=stable_read(reader.root,rawpath)
        if data is None:
            if record['working'].get('sha256') or record['working'].get('kind')!=kind:
                raise RepositoryError('SOURCE_CHANGED','Working file differs from captured state; refresh explicitly',5)
            return dict(identity,kind=kind,text=None,sha256=None)
        value=classify(data)
        if record['working'].get('sha256')!=value['sha256']:raise RepositoryError('SOURCE_CHANGED','Working file differs from captured bytes; refresh explicitly',5)
        identity['current_path']=str(reader.root/os.fsdecode(rawpath))
    elif entry is None:return dict(identity,kind='absent',text=None,sha256=None)
    elif entry['mode'] in ['120000','160000']:
        return dict(identity,kind='symlink' if entry['mode']=='120000' else 'submodule',text=None,oid=entry['oid'],sha256=None)
    else:
        data,size=reader.blob(entry['oid']);identity.update(oid=entry['oid'],mode=entry['mode'])
        if data is None:return dict(identity,kind='oversized',text=None,size=size,sha256=None)
        value=classify(data)
    return dict(identity,**value,snapshot_path=store.source(data))


def compare(left,right):
    result={'left':left,'right':right,'basis':'raw byte identities; text hunks with newline metadata','lines':[]}
    valid={'text','lfs_pointer','absent'}
    if left['kind'] not in valid or right['kind'] not in valid:return dict(result,state='UNAVAILABLE')
    a=left.get('text') or '';b=right.get('text') or ''
    if len(a.splitlines())+len(b.splitlines())>20000:return dict(result,state='PARTIAL',reason='DIFF_LINE_LIMIT')
    lines=list(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile=left['version'],tofile=right['version'],lineterm=''))
    return dict(result,state='COMPLETE',same_bytes=left.get('sha256')==right.get('sha256') and left['kind']==right['kind'],
                newline_or_encoding_only=not lines and left.get('sha256')!=right.get('sha256'),lines=lines)
