"""V2 offline projection from retained views; no provider, Git or source-tree reads."""
import base64
import copy
from pathlib import Path
import time
from .capture import Store
from .model import RepositoryError,SOURCE_LIMIT,TOTAL_SOURCE_LIMIT,canonical,digest
from .navigation import ViewStore,identity,outside_git,require

MAX_INLINE=32*1024*1024


def export_view(data_dir,context,destination,include_source=False,include_origin=False):
    from .viewer import html
    require(type(include_source) is bool and type(include_origin) is bool,'INVALID_EXPORT_OPTIONS')
    store=Store(data_dir);view=ViewStore(store).load(identity(context));payload=copy.deepcopy(view.payload());payload['view']['source_key']=view.right.repository.key
    # Repository identity metadata is an explicit projection option, separate from map contents.
    if not include_origin:
        payload['view'].pop('source_url',None);payload['view'].update(ref_kind='commit',ref_name=view.right.revision.commit_id,left_ref_kind='commit' if view.left else 'parent',left_ref_name=view.left.revision.commit_id if view.left else '');payload['capture']['revision'].update(ref_kind='commit',ref_name=view.right.revision.commit_id);payload['capture']['repository']={'provider':view.right.repository.provider,'source_key':view.right.repository.key}
        project=next(n for n in payload['graph']['nodes'] if n['id']==payload['graph']['project']);project['label']='Saved project';project['description']=''
    sources={};comparisons={};changes=copy.deepcopy(view.changes);encoded=len(canonical(payload));raw_bytes=0;excluded=0;deadline=time.monotonic()+120
    def public(value):
        value=copy.deepcopy(value)
        for key in ['snapshot_path','current_path','retained_copy_available']:value.pop(key,None)
        if not include_origin:value.pop('provider_url',None)
        return value
    # Bound changed-path metadata as well; retained completeness and exported availability differ.
    items=[]
    for item in changes['items']:
        size=len(canonical(item))+1
        if encoded+size>MAX_INLINE:break
        items.append(item);encoded+=size
    changes.update(items=items,available=len(items),complete=changes['complete'] and len(items)==changes['total'])
    if include_source:
        for path in view._entries:
            if time.monotonic()>deadline:break
            for role,snapshot in [('right',view.right),('left',view.left)]:
                value=public(view.source(path,role));content=snapshot.read_content(path) if snapshot else None
                size=0
                if content is not None and content.data is not None:
                    size=len(content.data)
                    if size>SOURCE_LIMIT or raw_bytes+size>TOTAL_SOURCE_LIMIT:excluded+=1;continue
                    value['raw_base64']=base64.b64encode(content.data).decode('ascii')
                cost=len(canonical(value))+len(path)+len(role)+8
                if encoded+cost>MAX_INLINE:excluded+=1;continue
                sources[path+':'+role]=value;raw_bytes+=size;encoded+=cost
        for path in view._entries:
            if time.monotonic()>deadline:break
            if path+':right' not in sources or path+':left' not in sources:continue
            value=public(view.comparison(path))
            for side in ['left','right']:
                value[side]=public(value[side]);value[side].pop('text',None)
            cost=len(canonical(value))+len(path)+8
            if encoded+cost>MAX_INLINE:continue
            comparisons[path]=value;encoded+=cost
    expected=len(view._entries)*2 if include_source else 0
    payload['export']={'source_included':include_source,'origin_included':include_origin,'included_source_bytes':raw_bytes,'source_entries':len(sources),'source_entries_excluded':max(excluded,expected-len(sources)),'comparison_entries':len(comparisons),'changed_entries':len(items),'changed_total':view.changes['total'],'absolute_editor_paths':False,'project_paths_and_descriptions':True,'source_encoding':'raw Base64 plus available decoded text'}
    page=html({'mode':'offline','payload':payload,'sources':sources,'comparisons':comparisons,'changes':changes});require(len(page.encode('utf-8'))<=MAX_INLINE+2*1024*1024,'EXPORT_LIMIT')
    output=Path(destination).expanduser().resolve();outside_git(output);require(output!=store.directory and not output.is_relative_to(store.directory),'OUTPUT_IN_DATA');require(not output.exists(),'OUTPUT_EXISTS')
    output.mkdir(parents=True,exist_ok=False);created=[]
    try:
        for name,data in [('START_HERE.html',page.encode('utf-8')),('project-navigation.json',canonical(payload))]:
            (output/name).write_bytes(data);created.append(name)
        manifest={'schema':'calf.repository.export.v2','view_context_id':context,'right_snapshot':view.right.snapshot_id,'left_snapshot':view.left.snapshot_id if view.left else None,'navigation_id':view.graph['navigation_id'],'files':{name:digest((output/name).read_bytes()) for name in created},'coverage':payload['export']}
        (output/'MANIFEST.json').write_bytes(canonical(manifest));created.append('MANIFEST.json')
    except Exception:
        for name in created:(output/name).unlink(missing_ok=True)
        try:output.rmdir()
        except OSError:pass
        raise
    partial=include_source and len(sources)<expected or len(items)<view.changes['total'] or view.coverage()['state']=='PARTIAL'
    return {'state':'PARTIAL' if partial else 'COMPLETE','output':str(output),'manifest':manifest}
