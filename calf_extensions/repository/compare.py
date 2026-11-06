"""Exact source versions and textual comparisons, never Git worktree conversions."""
import difflib
from .model import RepositoryError


def source(reader,store,capture,path_id,version,commit=None):
    """Compatibility entry point for exact Local Git source versions."""
    from .providers.local import _read_local_source
    return _read_local_source(reader,store,capture,path_id,version,commit)


def compare(left,right):
    result={'left':left,'right':right,'basis':'raw byte identities; text hunks with newline metadata','lines':[]}
    valid={'text','lfs_pointer','absent'}
    if any(v.get('availability') not in {None,'READY','ABSENT'} for v in [left,right]) or left['kind'] not in valid or right['kind'] not in valid:return dict(result,state='UNAVAILABLE')
    a=left.get('text') or '';b=right.get('text') or ''
    if len(a.splitlines())+len(b.splitlines())>20000:return dict(result,state='PARTIAL',reason='DIFF_LINE_LIMIT')
    lines=list(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile=left['version'],tofile=right['version'],lineterm=''))
    return dict(result,state='COMPLETE',same_bytes=left.get('sha256')==right.get('sha256') and left['kind']==right['kind'],
                newline_or_encoding_only=not lines and left['kind']!='absent' and right['kind']!='absent' and left.get('sha256')!=right.get('sha256'),lines=lines)


def compare_pair(context,path_id):
    """Compare exact snapshot content; absence requires complete inventory evidence."""
    from .providers.base import ComparisonContext
    if not isinstance(context,ComparisonContext):raise RepositoryError('SOURCE_CONTRACT','Expected an explicit comparison context')
    if not any(e.id==path_id for snapshot in [context.left,context.right] for e in snapshot.entries):raise RepositoryError('PATH_NOT_REGISTERED','Path is outside the comparison')
    values=[s.read_content(path_id).value('commit:'+s.revision.commit_id if s.revision.commit_id else 'snapshot:'+s.snapshot_id,s.revision.commit_id,s.captured_at) for s in [context.left,context.right]]
    return dict(compare(*values),context_id=context.context_id,comparison_basis=context.basis,
                left_snapshot=context.left.snapshot_id,right_snapshot=context.right.snapshot_id,
                left_input=context.left.input_id,right_input=context.right.input_id)
